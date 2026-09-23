#!/usr/bin/env python3
"""
JARVIS Live Auto-Trader
======================
Auto-executes CALL/PUT trades on Delta Exchange with:
  - leverage derived per trade from available collateral, margin and stop risk
  - Dual-leg execution: Futures scalp + Options hedge
  - 3-tier safety gates before any real order
  - Real-time position monitor (TP/SL/expiry)
  - Emergency stop kill-switch

USAGE:
  Set in .env:
    DELTA_USE_MAINNET=true      # false = testnet
    JARVIS_AUTO_TRADE=true      # false = paper only
    JARVIS_MAX_LEVERAGE=20      # hard safety cap; operating leverage is derived
    JARVIS_MAX_RISK_USDT=10     # max $ at risk per trade
    JARVIS_MAX_DAILY_LOSS=30    # stop after -$30/day
"""

import os
import sys
import time
import json
import logging
import threading
from datetime import datetime, timedelta, date
from typing import Dict, Optional, List
from dataclasses import dataclass

@dataclass
class TradeRequest:
    direction: str
    confidence: int
    current_price: float
    part_results: Dict = None
    trade_type: str = "SCALP"
    symbol: str = "BTCUSDT"

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("JarvisAutoTrader")

# ── ANSI colors (same as professional_display) ─────────────────────────────
R  = '\033[91m'; G  = '\033[92m'; Y  = '\033[93m'
C  = '\033[96m'; W  = '\033[97m'; DG = '\033[90m'
BD = '\033[1m';  RST= '\033[0m'

def _p(text, *col):  return ''.join(col) + str(text) + RST
def _box(msg, col=C): print(f"{col}  ▶  {RST}{msg}")

# ══════════════════════════════════════════════════════════════════
#  RISK CONFIGURATION  (override via .env)
# ══════════════════════════════════════════════════════════════════
from jarvis_risk import calculate_trade_size, MAX_LEVERAGE_CAP, contract_quote_value_usdt
from jarvis_lot_limits import enforce_entry_lots
try:
    from jarvis_position_ownership import claim_position, claim_close
except ImportError:
    def claim_position(position_id, owner):
        return True  # fail-open fallback if module missing
    def claim_close(position_id, owner):
        return True, None  # fail-open fallback
LEVERAGE_CAP        = MAX_LEVERAGE_CAP  # policy cap; not a user-selected leverage
MAX_RISK_USDT       = float(os.environ.get("JARVIS_MAX_RISK_USDT", "10"))
MAX_DAILY_LOSS_USDT = float(os.environ.get("JARVIS_MAX_DAILY_LOSS","30"))
MAX_OPEN_POSITIONS  = int(os.environ.get("JARVIS_MAX_OPEN",        "2"))
MIN_CONFIDENCE      = int(os.environ.get("JARVIS_MIN_CONFIDENCE",  "70"))
COOLDOWN_SECONDS    = int(os.environ.get("JARVIS_COOLDOWN_SEC",    "180"))
CONSEC_LOSS_LIMIT   = int(os.environ.get("JARVIS_CONSEC_LOSS",     "3"))
AUTO_TRADE_ENABLED  = os.environ.get("JARVIS_AUTO_TRADE", "false").lower() == "true"
# Real execution requires deliberate, independent confirmation.  AUTO_TRADE
# alone is never enough to submit orders or alter venue leverage.
LIVE_EXECUTION_ENABLED = (
    AUTO_TRADE_ENABLED
    and os.environ.get("DELTA_USE_MAINNET", "false").lower() == "true"
    and os.environ.get("JARVIS_LIVE_EXECUTION", "false").lower() == "true"
    and os.environ.get("DELTA_ORDER_EXECUTION_ENABLED", "false").lower() == "true"
)
HEDGE_ENABLED       = os.environ.get("JARVIS_HEDGE", "true").lower() == "true"

# ── Gemini Supreme Advisor (lazy import) ─────────────────────
try:
    from gemini_supreme_advisor import get_advisor as _get_gemini_advisor
except ImportError:
    _get_gemini_advisor = lambda: None

# ── Market Oracle Trade Gate (lazy import) ───────────────────
try:
    from oracle_trade_gate import get_oracle_trade_gate as _get_oracle_gate
except ImportError:
    _get_oracle_gate = lambda: None

# ── Coin Scanner (lazy import) ───────────────────────────────
try:
    from jarvis_coin_scanner import get_coin_scanner as _get_coin_scanner
except ImportError:
    _get_coin_scanner = lambda: None

# ── Dynamic Sizer (lazy import) ──────────────────────────────
try:
    from jarvis_sizer import get_sizer as _get_sizer
except ImportError:
    _get_sizer = lambda: None

# ── Position Manager (lazy import) ───────────────────────────
try:
    from jarvis_position_manager import get_position_manager as _get_position_manager
except ImportError:
    _get_position_manager = lambda: None

# ── Scalp target percentages ─────────────────────────────────────
SCALP_TP_PCT = 0.004    # 0.4% take profit
SCALP_SL_PCT = 0.002    # 0.2% stop loss
SWING_TP_PCT = 0.020    # 2.0% take profit
SWING_SL_PCT = 0.008    # 0.8% stop loss

# ── Smart Reversal Config ─────────────────────────────────────────
# JARVIS re-checks signal mid-trade; if market flips → exit + reverse
REVERSAL_MIN_CONFIDENCE  = int(os.environ.get("JARVIS_REVERSAL_CONF",  "75"))  # min conf to trigger reversal
REVERSAL_MIN_PROFIT_PCT  = float(os.environ.get("JARVIS_REV_MIN_PROFIT", "0.001"))  # only reverse if already +0.1%
REVERSAL_CHECK_SEC_SCALP = int(os.environ.get("JARVIS_REV_CHECK_SCALP", "60"))   # re-check every 60s for scalps
REVERSAL_CHECK_SEC_SWING = int(os.environ.get("JARVIS_REV_CHECK_SWING", "300"))  # re-check every 5min for swings
REVERSAL_ENABLED         = os.environ.get("JARVIS_REVERSAL", "true").lower() == "true"


class JarvisAutoTrader:
    """
    Core auto-trading brain.
    Receives signals from JarvisElite → places real Delta orders.
    """

    def __init__(self, delta_client, hedge_advisor=None):
        self.delta          = delta_client
        self.hedge_advisor  = hedge_advisor
        self.is_enabled     = LIVE_EXECUTION_ENABLED
        self.emergency_stop = False

        # ── State ────────────────────────────────────────────────
        self.open_positions: List[Dict] = []
        self.closed_today:   List[Dict] = []
        # Process-local lifecycle owner token.  The active auto-trader is the
        # sole component allowed to close its positions.
        self._ownership_token = f"auto:{id(self)}"
        self.daily_pnl      = 0.0
        self.daily_trades   = 0
        self.consec_losses  = 0
        self.last_trade_time: Optional[datetime] = None
        self.today_date     = date.today()

        # ── Gemini Supreme Advisor reference ─────────────────────
        # Set after init_advisor() is called in run_jarvis_live.py
        self._gemini_advisor = None
        self._oracle_gate    = None

        # ── Monitor thread ────────────────────────────────────────
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_running = False

        self._print_banner()
        if self.is_enabled:
            self._start_monitor()
        # Will be set by LiveTradingEngine after JarvisElite is ready
        self._jarvis_ref = None      # JarvisElite instance for mid-trade signal re-check
        self._df_ref     = None      # Latest DataFrame for analyze_trade_setup()


    # ──────────────────────────────────────────────────────────────
    #  PUBLIC API
    # ──────────────────────────────────────────────────────────────

    def execute(self, request: TradeRequest) -> Dict:
        """
        Main entry: receive signal → run all gates → place order.
        request.direction  : 'CALL' or 'PUT'
        request.trade_type : 'SCALP' or 'SWING'
        """
        direction = request.direction
        confidence = request.confidence
        current_price = request.current_price
        part_results = request.part_results
        trade_type = request.trade_type
        symbol = request.symbol

        if self.emergency_stop:
            return self._skip("🛑 EMERGENCY STOP ACTIVE")
        if not isinstance(direction, str) or direction.upper() not in ("CALL", "PUT", "BUY", "SELL"):
            return self._skip("Invalid trade direction")
        direction = direction.upper()
        confidence = normalize_confidence(confidence)
        try:
            current_price = float(current_price)
        except (TypeError, ValueError):
            return self._skip("Invalid confidence or price")
        if confidence is None or not 0 <= confidence <= 100 or current_price <= 0:
            return self._skip("Invalid confidence or price")
        if trade_type not in ("SCALP", "SWING"):
            return self._skip("Invalid trade type")
        symbol = str(symbol or "").upper().replace("-", "").replace("_", "").strip()
        if not symbol or symbol in {"BTC", "USDT"}:
            return self._skip("Invalid execution symbol")

        # Reset daily stats at midnight
        if date.today() != self.today_date:
            self._reset_daily()

        # ─ Gate 0: Gemini Supreme Advisor override ───────────────
        gemini = self._gemini_advisor or _get_gemini_advisor()
        if gemini:
            allowed, reason = gemini.is_trading_allowed(direction)
            if not allowed:
                return self._skip(f"Gate0 GEMINI OVERRIDE: {reason}")

        # ─ Gate 0.5: JARVIS Market Oracle Gate ───────────────────
        oracle_gate = self._oracle_gate or _get_oracle_gate()
        if oracle_gate:
            aligned, align_reason = oracle_gate.is_trade_aligned(direction, symbol=symbol)
            if not aligned:
                return self._skip(f"Gate0.5 ORACLE ALIGNMENT: {align_reason}")

            in_zone, zone_reason = oracle_gate.is_price_in_entry_zone(current_price, symbol=symbol)
            if not in_zone:
                return self._skip(f"Gate0.5 ORACLE ENTRY ZONE: {zone_reason}")

        # ─ Gate 1: Risk checks ───────────────────────────────────
        gate1 = self._check_risk_gates(confidence, gemini)
        if not gate1["ok"]:
            return self._skip(f"Gate1 FAIL: {gate1['reason']}")

        # ─ Gate 2: Hedge decision ────────────────────────────────
        hedge_plan = {"do_hedge": False, "reason": "Hedge disabled"}
        if HEDGE_ENABLED and self.hedge_advisor:
            hedge_plan = self._get_hedge_plan(
                direction, confidence, current_price, part_results, symbol)

        # ─ Gate 3: Execute ───────────────────────────────────────
        return self._place_trade(
            direction, confidence, current_price, trade_type, hedge_plan, symbol)

    def trigger_emergency_stop(self):
        """Close ALL positions immediately."""
        self.emergency_stop = True
        print(f"\n{_p('🛑 ══ EMERGENCY STOP TRIGGERED ══ 🛑', BD+R)}")
        
        self.cancel_open_orders()

        closed = 0
        remaining = []
        for pos in list(self.open_positions):
            try:
                result = self._close_position_market(pos)
                if result.get("success"):
                    closed += 1
                    print(f"  ✅ Closed #{pos['id']} at market")
                else:
                    pos["status"] = "CLOSE_UNKNOWN"
                    pos["close_error"] = result.get("error", "Close not confirmed")
                    remaining.append(pos)
                    print(f"  ❌ Close unconfirmed for #{pos['id']}: {pos['close_error']}")
            except Exception as e:
                pos["status"] = "CLOSE_UNKNOWN"
                pos["close_error"] = str(e)
                remaining.append(pos)
                print(f"  ❌ Error closing #{pos['id']}: {e}")
        self.open_positions = remaining
        print(f"  Closed {closed} positions; {len(remaining)} require reconciliation. System halted.")

    def cancel_open_orders(self):
        """Cancel all pending/open orders on exchange."""
        try:
            if hasattr(self.delta, 'cancel_order'):
                open_orders = getattr(self.delta, 'get_open_orders', lambda: [])()
                for order in (open_orders or []):
                    oid = order.get('id') or order.get('order_id')
                    if oid:
                        self.delta.cancel_order(oid)
                        print(f"  ✅ Cancelled open order #{oid}")
        except Exception as e:
            print(f"  ⚠️  Cancel orders failed: {e}")

    def resume(self):
        """Resume after emergency stop."""
        self.emergency_stop = False
        print(_p("▶  Auto-trader RESUMED", BD+G))

    def status_line(self) -> str:
        """One-line status for terminal display."""
        mode = _p("LIVE", BD+R) if self.is_enabled else _p("PAPER", BD+Y)
        net  = _p("MAINNET", BD+R) if os.environ.get("DELTA_USE_MAINNET","false").lower()=="true" else _p("TESTNET", BD+Y)
        return (
            f"  {_p('AUTO-TRADER:', DG)} {mode} {_p('│',DG)} {net} "
            f"{_p('│',DG)} {_p('Lev: AUTO', BD+C)} "
            f"{_p('│',DG)} Open: {_p(len(self.open_positions),W)}/{MAX_OPEN_POSITIONS} "
            f"{_p('│',DG)} Daily P&L: {_p(f'{self.daily_pnl:+.2f}$', G if self.daily_pnl>=0 else R)} "
            f"{_p('│',DG)} Losses: {_p(self.consec_losses,R)}/{CONSEC_LOSS_LIMIT}"
        )

    # ──────────────────────────────────────────────────────────────
    #  GATE 1: RISK FILTER
    # ──────────────────────────────────────────────────────────────

    def _check_risk_gates(self, confidence: int, gemini_advisor=None) -> Dict:
        # Confidence threshold — use Gemini's recommendation if available
        effective_min = MIN_CONFIDENCE
        if gemini_advisor:
            effective_min = gemini_advisor.get_confidence_threshold(MIN_CONFIDENCE)
        if confidence < effective_min:
            return {"ok": False, "reason": f"Confidence {confidence}% < {effective_min}% (Gemini threshold)"}

        # Emergency stop
        if self.emergency_stop:
            return {"ok": False, "reason": "Emergency stop active"}

        # Daily loss limit
        if self.daily_pnl <= -MAX_DAILY_LOSS_USDT:
            return {"ok": False, "reason": f"Daily loss limit hit (-${abs(self.daily_pnl):.1f})"}

        # Consecutive losses
        if self.consec_losses >= CONSEC_LOSS_LIMIT:
            return {"ok": False, "reason": f"{self.consec_losses} consecutive losses — cooling down"}

        # Max open positions
        if len(self.open_positions) >= MAX_OPEN_POSITIONS:
            return {"ok": False, "reason": f"Max {MAX_OPEN_POSITIONS} positions open"}

        # Cooldown
        if self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time).total_seconds()
            if elapsed < COOLDOWN_SECONDS:
                remaining = int(COOLDOWN_SECONDS - elapsed)
                return {"ok": False, "reason": f"Cooldown: {remaining}s remaining"}

        # Balance check
        try:
            balance = self.delta.get_wallet_balance()
            min_balance = MAX_RISK_USDT * 2  # need at least 2x risk
            if balance < min_balance:
                return {"ok": False, "reason": f"Balance ${balance:.1f} < minimum ${min_balance:.1f}"}
        except Exception as e:
            return {"ok": False, "reason": f"Balance check failed: {e}"}

        return {"ok": True, "reason": "All gates passed"}

    # ──────────────────────────────────────────────────────────────
    #  GATE 2: HEDGE DECISION
    # ──────────────────────────────────────────────────────────────

    def _get_hedge_plan(self, direction, confidence, price, part_results, symbol: str) -> Dict:
        try:
            options_chain = {}
            try:
                options_chain = self.delta.get_options_chain(symbol.removesuffix("USDT").removesuffix("USD"))
            except Exception:
                pass

            atr = price * 0.004  # default 0.4% ATR
            expected_profit = (MAX_RISK_USDT / max(SCALP_SL_PCT, 1e-9)) * SCALP_TP_PCT

            result = self.hedge_advisor.evaluate_hedge_setup(
                signal_direction=direction,
                signal_confidence=confidence,
                current_price=price,
                atr=atr,
                options_chain=options_chain,
                expected_profit=expected_profit
            )
            return {
                "do_hedge":     result.get("hedge", "NO") == "YES",
                "strike":       result.get("strike"),
                "expiry":       result.get("expiry", "nearest"),
                "hedge_ratio":  result.get("hedge_ratio", 0.5),
                "option_type":  "PUT" if direction in ("CALL","BUY") else "CALL",
                "reason":       result.get("reason", "AI hedge decision"),
            }
        except Exception as e:
            logger.warning(f"[HEDGE] Advisor error: {e}")
            # Default: always hedge if confidence < 80
            return {
                "do_hedge": confidence < 80,
                "option_type": "PUT" if direction in ("CALL","BUY") else "CALL",
                "reason": "Fallback hedge rule (conf < 80%)",
            }

    # ──────────────────────────────────────────────────────────────
    #  GATE 3: TRADE EXECUTION
    # ──────────────────────────────────────────────────────────────

    def _place_trade(self, direction, confidence, price,
                     trade_type, hedge_plan, symbol: str = "BTCUSDT") -> Dict:
        """Execute both legs (futures + optional hedge)."""
        symbol = str(symbol or "").upper().replace("-", "").replace("_", "").strip()
        if not symbol:
            return {"success": False, "reason": "Execution symbol is missing"}

        is_call    = direction in ("CALL", "BUY")
        futures_side = "buy" if is_call else "sell"

        # The caller owns routing.  Do not read the scanner again here: a
        # second scan could turn an ETH analysis into a SOL order.

        # ── Derive size and leverage from collateral + stop risk ───────
        tp_pct    = SWING_TP_PCT if trade_type == "SWING" else SCALP_TP_PCT
        sl_pct    = SWING_SL_PCT if trade_type == "SWING" else SCALP_SL_PCT
        tp_price  = round(price * (1 + tp_pct) if is_call else price * (1 - tp_pct), 2)
        sl_price  = round(price * (1 - sl_pct) if is_call else price * (1 + sl_pct), 2)
        product = None
        product_max_leverage = None
        contract_value_usdt = None
        if self.is_enabled:
            get_metadata = getattr(self.delta, "get_product_metadata", None)
            if not callable(get_metadata):
                return {"success": False, "reason": "Product metadata unavailable"}
            try:
                product = get_metadata(symbol)
            except Exception as exc:
                return {"success": False, "reason": "Product metadata unavailable", "error": str(exc)}
            if not isinstance(product, dict) or not product.get("id"):
                return {"success": False, "reason": "Product metadata unavailable"}
            for key in ("max_leverage", "max_leverage_allowed", "leverage_max"):
                if product.get(key) is not None:
                    try:
                        product_max_leverage = float(product[key])
                    except (TypeError, ValueError):
                        return {"success": False, "reason": "Invalid product leverage metadata"}
                    break
            contract_value_usdt = contract_quote_value_usdt(product, price)
            if contract_value_usdt is None:
                return {"success": False, "reason": "Unrecognized or missing contract value metadata; live sizing blocked"}

        try:
            balance = float(self.delta.get_wallet_balance())
        except Exception:
            return {"success": False, "reason": "Balance unavailable"}
        if balance <= 0:
            return {"success": False, "reason": "No available balance"}

        sizer = _get_sizer(self.delta)
        if sizer:
            sizer.set_compound_pool(
                getattr(_get_position_manager(), "compounded_balance", 0)
            )
            size_info = sizer.calculate_size(
                confidence, symbol, force_balance=balance,
                stop_distance_pct=sl_pct,
                max_trade_risk_usdt=MAX_RISK_USDT,
                product_max_leverage=product_max_leverage,
                contract_value_usdt=contract_value_usdt,
                require_contract_value=self.is_enabled,
            )
        else:
            size_info = calculate_trade_size(
                balance, confidence, sl_pct,
                max_trade_risk_usdt=MAX_RISK_USDT,
                product_max_leverage=product_max_leverage,
                contract_value_usdt=contract_value_usdt,
                require_contract_value=self.is_enabled,
            )
        if not size_info.get("ok"):
            return {"success": False, "reason": size_info.get("reason", "Risk sizing blocked")}
        margin = float(size_info.get("margin_usdt", 0.0))
        contracts = int(size_info.get("contracts", 0))
        leverage = int(size_info.get("leverage", 0))
        if margin <= 0 or contracts <= 0 or leverage <= 0:
            return {"success": False, "reason": "Risk budget cannot fund one contract"}
        # Final gate immediately before any venue mutation/order. Never round up:
        # a risk-safe quantity below the configured minimum is rejected.
        try:
            contracts = enforce_entry_lots(contracts, metadata=product, available_balance=balance)
        except (TypeError, ValueError) as exc:
            return {"success": False, "reason": "Entry lot policy blocked", "error": str(exc)}
        if contracts <= 0:
            return {"success": False, "reason": "Entry lot policy blocked"}

        # ── Dynamic Oracle TP/SL Enhancement ────────────────────
        oracle_gate = self._oracle_gate or _get_oracle_gate()
        oracle_plan = None
        hold_minutes = 5 if trade_type == "SCALP" else 60
        if oracle_gate:
            oracle_plan = oracle_gate.get_oracle_tp_sl(price, direction)
            if oracle_plan and oracle_plan.get("use_oracle"):
                tp_price = oracle_plan["tp_price"]
                sl_price = oracle_plan["sl_price"]
                hold_minutes = oracle_plan.get("hold_minutes", hold_minutes)

        # The caller's unified dashboard owns terminal presentation.  Keep
        # execution detail in logs so one cycle does not emit scattered blocks.
        logger.info("[EXECUTION] %s %s %s contracts at %sx AUTO; TP=%s SL=%s hold=%sm",
                    direction, symbol, contracts, leverage, tp_price, sl_price, hold_minutes)

        # ─ LEG 0: Set leverage only for deliberately enabled live execution.
        # Paper execution must never alter an exchange account.
        if self.is_enabled:
            try:
                lev_ok = bool(self.delta.set_leverage(symbol, leverage))
            except Exception as e:
                return {"success": False, "reason": "Leverage setup failed", "error": str(e)}
            if not lev_ok:
                return {"success": False, "reason": "Leverage setup failed"}
            logger.info('[EXECUTION] leverage %sx AUTO applied for %s', leverage, symbol)
        else:
            logger.info('[EXECUTION] paper mode: venue leverage unchanged')

        # ─ LEG 1: Futures scalp ──────────────────────────────────
        futures_result = {"success": False, "error": "not attempted"}
        if self.is_enabled:
            try:
                futures_result = self.delta.place_order(
                    symbol=symbol,
                    side=futures_side,
                    size=contracts,
                    order_type="market"
                )
            except Exception as e:
                futures_result = {"success": False, "error": str(e)}
        else:
            # Paper mode
            futures_result = {
                "success": True,
                "paper": True,
                "order_id": f"PAPER_{int(time.time())}",
                "details": {"side": futures_side, "size": contracts}
            }

        if futures_result.get("success"):
            order_id = futures_result.get("order_id", "?")
            logger.info('[EXECUTION] futures filled: %s %s %s order=%s', futures_side.upper(), contracts, symbol, order_id)
        else:
            logger.error('[EXECUTION] futures order failed: %s', futures_result.get('error', 'unknown'))
            return {"success": False, "reason": "Futures order failed",
                    "error": futures_result.get("error")}

        # ─ LEG 2: Options hedge (if requested) ──────────────────
        hedge_result = None
        if hedge_plan.get("do_hedge"):
            try:
                opt_type = hedge_plan.get("option_type")
                opt_strike = float(hedge_plan.get("strike"))
                opt_symbol = self._find_option_symbol(
                    opt_type, opt_strike,
                    symbol.removesuffix("USDT").removesuffix("USD")
                )
                if self.is_enabled:
                    # A live requested hedge is mandatory, not a best-effort
                    # follow-up after leaving naked futures exposure.
                    if not opt_symbol:
                        raise RuntimeError("Requested hedge contract unavailable")
                    hedge_result = self.delta.place_option_order(opt_symbol, "buy", 1)
                    if not hedge_result or not hedge_result.get("success"):
                        raise RuntimeError((hedge_result or {}).get("error", "Hedge order failed"))
                    logger.info('[EXECUTION] hedge filled: %s %s order=%s', opt_type, opt_strike, hedge_result.get('order_id', '?'))
                else:
                    hedge_result = {"success": True, "paper": True}
                    logger.info('[EXECUTION] paper hedge simulated')
            except Exception as e:
                if self.is_enabled:
                    compensation = self._close_position_market({
                        "direction": direction, "contracts": contracts, "symbol": symbol
                    })
                    return {
                        "success": False,
                        "reason": "Hedge failed; futures close attempted",
                        "error": str(e),
                        "compensation": compensation,
                    }
                return {"success": False, "reason": "Invalid paper hedge", "error": str(e)}

        # ─ Record position ────────────────────────────────────────
        pos = {
            "id":          futures_result.get("order_id", f"pos_{int(time.time())}"),
            "direction":   direction,
            "entry_price": price,
            "tp_price":    tp_price,
            "sl_price":    sl_price,
            "contracts":   contracts,
            "contract_value_usdt": float(size_info.get("contract_value_usdt", contract_value_usdt or 1.0)),
            "notional_usdt": float(size_info.get("notional_usdt", contracts * (contract_value_usdt or 1.0))),
            "margin_usdt": margin,
            "trade_risk_usdt": float(size_info.get("trade_risk_usdt", 0.0)),
            "symbol":      symbol,
            "trade_type":  trade_type,
            "confidence":  confidence,
            "leverage":    leverage,
            "open_time":   datetime.now().isoformat(),
            "expiry_time": (datetime.now() + timedelta(minutes=hold_minutes)).isoformat(),
            "hedge_id":    (hedge_result or {}).get("order_id"),
            "paper":       not self.is_enabled,
            "status":      "OPEN",
            "_last_reversal_check": datetime.now(),  # Track when we last re-evaluated
        }
        position_id = pos["id"]
        if not claim_position(position_id, self._ownership_token):
            # The venue order succeeded but its identifier is already owned by
            # another lifecycle manager.  Do not publish a second local
            # position or allow two monitors to close it independently.
            logger.error("[OWNERSHIP] Position %s already owned by %s; refusing duplicate registration", position_id, position_owner(position_id))
            pos["status"] = "OWNERSHIP_UNKNOWN"
            return {"success": False, "reason": "Position ownership conflict; reconciliation required", "position": pos}
        self.open_positions.append(pos)
        self.last_trade_time = datetime.now()
        self.daily_trades   += 1

        # This trader owns the position lifecycle.  Registering the same live
        # position in a second monitor can submit duplicate closing orders.

        # ─ Estimated P&L (dashboard presents these fields) ─────────────
        notional    = float(pos.get("notional_usdt", contracts * (contract_value_usdt or 1.0)))
        risk_usdt   = float(pos.get("trade_risk_usdt", notional * sl_pct))
        reward_usdt = notional * tp_pct
        logger.info('[EXECUTION] risk=$%.4f reward=$%.4f leverage=%sx position=%s',
                    risk_usdt, reward_usdt, leverage, pos['id'])
        return {"success": True, "position": pos, "hedge": hedge_result}

    # ──────────────────────────────────────────────────────────────
    #  POSITION MONITOR (background thread)
    # ──────────────────────────────────────────────────────────────

    def _start_monitor(self):
        """Start background thread watching TP/SL/expiry."""
        self._monitor_running = True
        self._monitor_thread  = threading.Thread(
            target=self._monitor_loop, daemon=True, name="JarvisPositionMonitor")
        self._monitor_thread.start()
        logger.info("[MONITOR] Position monitor started")

    def _monitor_loop(self):
        """Check each open position using its own symbol price every 5 seconds."""
        while self._monitor_running:
            try:
                prices = {}
                for pos in list(self.open_positions):
                    symbol = str(pos.get("symbol", "BTCUSDT")).upper()
                    price = self._get_price(symbol)
                    if price and price > 0:
                        prices[symbol] = price
                if prices and self.open_positions:
                    self._check_positions(prices)
                    # Smart reversal: re-evaluate signals using the same route
                    # symbol as each position, never the first position's price.
                    if REVERSAL_ENABLED and self._jarvis_ref and self._df_ref is not None:
                        self._check_reversals(prices)
            except Exception as e:
                logger.debug(f"[MONITOR] Tick error: {e}")
            time.sleep(5)

    def _check_positions(self, current_price):
        """Check TP / SL / expiry for each position's symbol-specific price.

        A scalar is retained for compatibility with older offline callers; new
        monitor calls pass ``{symbol: price}`` and skip positions whose own
        price is unavailable rather than applying another asset's price.
        """
        still_open = []
        for pos in self.open_positions:
            if isinstance(current_price, dict):
                pos_symbol = str(pos.get("symbol", "BTCUSDT")).upper()
                pos_price = current_price.get(pos_symbol)
                if not pos_price or float(pos_price) <= 0:
                    still_open.append(pos)
                    continue
                price_for_position = float(pos_price)
            else:
                price_for_position = float(current_price)
            if pos.get("status") == "CLOSE_UNKNOWN":
                # Do not blindly retry an ambiguous close; reconcile venue state first.
                still_open.append(pos)
                continue
            closed, result, reason = False, None, None
            is_call = pos["direction"] in ("CALL", "BUY")
            tp = pos["tp_price"]
            sl = pos["sl_price"]
            exp = datetime.fromisoformat(pos["expiry_time"])

            if is_call:
                if price_for_position >= tp:
                    closed, result, reason = True, "WIN",  "✅ Take Profit"
                elif price_for_position <= sl:
                    closed, result, reason = True, "LOSS", "❌ Stop Loss"
            else:
                if price_for_position <= tp:
                    closed, result, reason = True, "WIN",  "✅ Take Profit"
                elif price_for_position >= sl:
                    closed, result, reason = True, "LOSS", "❌ Stop Loss"

            if not closed and datetime.now() >= exp:
                if is_call:
                    result = "WIN" if price_for_position > pos["entry_price"] else "LOSS"
                else:
                    result = "WIN" if price_for_position < pos["entry_price"] else "LOSS"
                reason = f"⏱️ Expiry ({'up' if price_for_position > pos['entry_price'] else 'down'})"
                closed = True

            if closed:
                # A price trigger is not proof that a venue close occurred.
                # Preserve an ambiguous position for operator reconciliation and
                # do not book simulated P&L on a failed close.
                close_result = self._close_position_market(pos)
                if not close_result.get("success"):
                    pos["status"] = "CLOSE_UNKNOWN"
                    pos["close_error"] = close_result.get("error", "Close not confirmed")
                    still_open.append(pos)
                    logger.error("[MONITOR] Close unconfirmed for %s", pos.get("id"))
                    continue
                pos["exit_price"]  = price_for_position
                pos["result"]      = result
                pos["close_reason"]= reason
                pos["close_time"]  = datetime.now().isoformat()
                pos["status"]      = "CLOSED"

                # P&L is based on the recorded venue notional, never an
                # implicit one-USDT-per-contract convention.
                move_pct = abs(price_for_position - pos["entry_price"]) / pos["entry_price"]
                pnl_sign = 1 if result == "WIN" else -1
                pnl_usdt = pnl_sign * move_pct * float(pos.get("notional_usdt", 0.0))
                pos["pnl_usdt"] = round(pnl_usdt, 3)

                self.daily_pnl   += pnl_usdt
                self.closed_today.append(pos)

                if result == "WIN":
                    self.consec_losses = 0
                else:
                    self.consec_losses += 1

                # Print trade close
                col = BD+G if result == "WIN" else BD+R
                print(f"\n{'─'*60}")
                print(f"  {_p(result + ' — Trade Closed', col)}")
                print(f"  #{pos['id']} | {pos['direction']} | {reason}")
                print(f"  Entry: ${pos['entry_price']:,.2f} → Exit: ${price_for_position:,.2f}")
                pnl_str = f"{'+' if pnl_usdt>=0 else ''}{pnl_usdt:.3f}"
                print(f"  P&L: {_p(pnl_str+' USD', col)} | Daily: {_p(f'{self.daily_pnl:+.2f}$', G if self.daily_pnl>=0 else R)}")
                print(f"{'─'*60}\n")

                # Auto emergency stop after daily loss limit
                if self.daily_pnl <= -MAX_DAILY_LOSS_USDT:
                    print(_p(f"\n⛔ Daily loss limit hit (${self.daily_pnl:.2f}). Auto emergency stop!", BD+R))
                    self.trigger_emergency_stop()
            else:
                still_open.append(pos)

        self.open_positions = still_open

    # ──────────────────────────────────────────────────────────────
    #  SMART ADAPTIVE REVERSAL
    # ──────────────────────────────────────────────────────────────

    def _check_reversal_interval(self, pos: Dict) -> int:
        """
        Adaptive re-check interval based on:
        - Trade type (SCALP = faster, SWING = slower)
        - How much time is left before expiry
        - Whether position is already in profit (safer to reverse)
        """
        trade_type = pos.get("trade_type", "SCALP")
        exp = datetime.fromisoformat(pos["expiry_time"])
        secs_left = max(0, (exp - datetime.now()).total_seconds())

        if trade_type == "SCALP":
            # Scalp: 5 min trade → check every 60s, but faster near expiry
            if secs_left < 90:   return 30   # Last 90s: check every 30s
            if secs_left < 180:  return 45   # Last 3 min: every 45s
            return REVERSAL_CHECK_SEC_SCALP   # Early: every 60s
        else:
            # Swing: 60 min trade → check every 5 min, faster near expiry
            if secs_left < 600:  return 120  # Last 10 min: every 2 min
            if secs_left < 1200: return 180  # Last 20 min: every 3 min
            return REVERSAL_CHECK_SEC_SWING   # Early: every 5 min

    def _check_reversals(self, current_price):
        """Re-check each position using its own symbol-specific price."""
        now = datetime.now()
        for pos in list(self.open_positions):
            if pos.get("status") != "OPEN":
                continue
            if isinstance(current_price, dict):
                position_price = current_price.get(str(pos.get("symbol", "BTCUSDT")).upper())
                if not position_price or float(position_price) <= 0:
                    continue
                position_price = float(position_price)
            else:
                position_price = float(current_price)

            # Check if it's time to re-evaluate this position
            last_check = pos.get("_last_reversal_check")
            interval   = self._check_reversal_interval(pos)
            if last_check and (now - last_check).total_seconds() < interval:
                continue  # Not yet time

            pos["_last_reversal_check"] = now

            # Run JARVIS signal analysis
            try:
                result = self._jarvis_ref.analyze_trade_setup(
                    self._df_ref, symbol=pos.get("symbol")
                )
                sig = result.get("trade_signal", {})
                selected_symbol = str(pos.get("symbol", "")).upper()
                selected_ctx = (result.get("market_context", {}) or {}).get("options_context", {})
                reversal_decision = build_final_decision(
                    sig,
                    symbol=selected_symbol,
                    price=position_price,
                    opinions=result.get("decision_opinions", []) or [],
                    options_context=selected_ctx,
                    require_options=bool(self.is_enabled),
                )
                if not reversal_decision.get("execution_allowed"):
                    logger.info("[REVERSAL] blocked by canonical decision: %s", reversal_decision.get("reasons"))
                    continue
                new_dir = reversal_decision.get("execution_direction")
                new_conf = reversal_decision.get("confidence")
            except Exception as e:
                logger.debug(f"[REVERSAL] Signal check failed: {e}")
                continue

            if new_dir not in ("CALL", "PUT"):
                continue  # No clear signal

            old_dir = pos["direction"]
            is_call = old_dir in ("CALL", "BUY")

            # Only reverse if signal COMPLETELY flipped
            if new_dir == old_dir:
                continue  # Same direction, hold

            # Confidence must be strong enough for reversal
            if new_conf is None:
                logger.debug("[REVERSAL] Signal flipped but confidence is unavailable")
                continue
            if new_conf < REVERSAL_MIN_CONFIDENCE:
                logger.debug(f"[REVERSAL] Signal flipped but conf {new_conf}% < {REVERSAL_MIN_CONFIDENCE}% threshold")
                continue

            # Optional: only reverse if already in some profit (not from a losing position)
            move_pct = (position_price - pos["entry_price"]) / pos["entry_price"]
            in_profit = (move_pct > REVERSAL_MIN_PROFIT_PCT and is_call) or \
                        (-move_pct > REVERSAL_MIN_PROFIT_PCT and not is_call)

            logger.info(
                "[REVERSAL] position=%s %s -> %s confidence=%s in_profit=%s",
                pos.get('id'), old_dir, new_dir, new_conf, in_profit,
            )

            if not in_profit:
                logger.info("[REVERSAL] skipped: position is not in profit")
                continue

            # Execute reversal
            self._execute_reversal(pos, new_dir, new_conf, position_price)

    def _execute_reversal(self, pos: Dict, new_dir: str, confidence: int, price: float):
        """
        1. Close current position at market
        2. Open new position in opposite direction
        """
        logger.info("[REVERSAL] executing position=%s direction=%s", pos.get('id'), new_dir)

        # Step 1: Close current position
        close_result = self._close_position_market(pos)
        if not close_result.get("success"):
            logger.error("[REVERSAL] failed: could not close current position %s", pos.get('id'))
            return

        # Calculate P&L of closed position
        is_old_call = pos["direction"] in ("CALL", "BUY")
        move_pct = abs(price - pos["entry_price"]) / pos["entry_price"]
        is_win   = (price > pos["entry_price"] and is_old_call) or \
                   (price < pos["entry_price"] and not is_old_call)
        pnl_sign = 1 if is_win else -1
        pnl_usdt = pnl_sign * move_pct * float(pos.get("notional_usdt", 0.0))

        pos["exit_price"]   = price
        pos["result"]       = "WIN" if is_win else "LOSS"
        pos["close_reason"] = f"🔄 Reversal Exit ({new_dir} signal @ {confidence}%)"
        pos["close_time"]   = datetime.now().isoformat()
        pos["status"]       = "CLOSED"
        pos["pnl_usdt"]     = round(pnl_usdt, 3)

        self.daily_pnl += pnl_usdt
        self.closed_today.append(pos)
        if pos in self.open_positions:
            self.open_positions.remove(pos)

        if is_win:
            self.consec_losses = 0
        else:
            self.consec_losses += 1

        logger.info(
            "[REVERSAL] position closed id=%s result=%s entry=%.8f exit=%.8f pnl=%+.3f",
            pos.get('id'), pos.get('result'), pos['entry_price'], price, pnl_usdt,
        )

        # Step 2: Check daily limits before opening reverse trade
        if self.daily_pnl <= -MAX_DAILY_LOSS_USDT:
            logger.warning("[REVERSAL] daily loss limit hit; no reverse trade")
            self.trigger_emergency_stop()
            return

        if self.consec_losses >= CONSEC_LOSS_LIMIT:
            logger.warning("[REVERSAL] consecutive loss limit hit; no reverse trade")
            return

        # Step 3: Open new reverse trade; execution details remain in logs.
        logger.info("[REVERSAL] opening reverse trade direction=%s confidence=%s", new_dir, confidence)

        # Brief delay to let market settle
        time.sleep(1)

        hedge_plan = {"do_hedge": False, "reason": "Reversal trade — no hedge"}
        trade_type = pos.get("trade_type", "SCALP")
        result = self._place_trade(
            new_dir, confidence, price, trade_type, hedge_plan,
            symbol=pos.get("symbol", "")
        )

        if result.get("success"):
            logger.info("[REVERSAL] reverse trade opened id=%s", (result.get('position') or {}).get('id'))
        else:
            logger.warning("[REVERSAL] reverse trade failed: %s", result.get('reason', 'unknown'))


    def _calc_contracts(self, price: float, margin_budget: float) -> int:
        """Return contracts affordable within the supplied margin budget."""
        try:
            margin_budget = float(margin_budget)
        except (TypeError, ValueError):
            return 0
        if margin_budget <= 0:
            return 0
        # Legacy helper retained for compatibility; live execution uses the
        # metadata-aware sizer above and does not call this approximation.
        return max(0, int(margin_budget))

    def _get_price(self, symbol: str = "BTCUSDT") -> Optional[float]:
        """Get live price for the position's locked symbol."""
        try:
            p = self.delta.get_live_price(symbol)
            if p and float(p) > 1000:
                return float(p)
        except Exception:
            pass
        return None

    def _find_option_symbol(self, option_type: str, strike: float, underlying: str = "BTC") -> Optional[str]:
        """Find matching option contract for the same asset as the futures trade."""
        try:
            chain  = self.delta.get_options_chain(underlying)
            key    = "puts" if option_type == "PUT" else "calls"
            options = chain.get(key, [])
            if not options:
                return None
            best = min(options, key=lambda x: abs(x.get("strike", 0) - strike))
            return best.get("symbol")
        except Exception:
            return None

    def _close_position_market(self, pos: Dict) -> Dict:
        """Submit one reduce-only close; ambiguous results remain unresolved.

        The ownership and close claims are process-local guards against two
        monitors issuing duplicate closes.  The venue wrapper also receives an
        idempotency key, while a transport failure is never treated as proof
        that a close failed or succeeded.
        """
        try:
            is_call    = pos["direction"] in ("CALL", "BUY")
            close_side = "sell" if is_call else "buy"
            position_id = pos.get("id")
            if self.is_enabled:
                symbol = pos.get("symbol")
                if not isinstance(symbol, str) or not symbol:
                    return {"success": False, "error": "Position symbol is missing"}
                allowed, current = claim_close(position_id, self._ownership_token)
                if not allowed:
                    return {"success": False, "error": f"Close already claimed or owned by {current or 'another manager'}"}
                result = self.delta.place_order(
                    symbol=symbol,
                    side=close_side,
                    size=pos["contracts"],
                    order_type="market",
                    reduce_only=True,
                    idempotency_key=f"jarvis-close-{position_id}",
                )
                if not isinstance(result, dict) or not result.get("success"):
                    return {"success": False, "ambiguous": True,
                            "error": (result or {}).get("error", "Close not confirmed")}
                return result
            else:
                # Paper closes do not need a venue claim, but retain one local
                # close transition so duplicate monitors cannot double-book.
                allowed, current = claim_close(position_id, self._ownership_token)
                if not allowed:
                    return {"success": False, "error": f"Close already claimed or owned by {current or 'another manager'}"}
                return {"success": True, "paper": True}
        except Exception as e:
            return {"success": False, "ambiguous": True, "error": str(e)}

    def _reset_daily(self):
        """Reset daily counters at midnight."""
        self.daily_pnl    = 0.0
        self.daily_trades = 0
        self.consec_losses = 0
        self.closed_today = []
        self.today_date   = date.today()
        logger.info("[TRADER] Daily stats reset at midnight")

    def _skip(self, reason: str) -> Dict:
        # Terminal output is owned by the unified dashboard; keep gate detail in logs.
        logger.info("[AUTO-TRADE] skipped: %s", reason)
        return {"success": False, "skipped": True, "reason": reason}

    def _print_banner(self):
        mode  = "🔴 LIVE MAINNET" if (self.is_enabled and os.environ.get("DELTA_USE_MAINNET","false").lower()=="true") else "🟡 TESTNET/PAPER"
        print(f"\n{'═'*70}")
        print(f"  {_p('🤖 JARVIS AUTO-TRADER INITIALIZED', BD+C)}")
        print(f"  Mode: {_p(mode, BD+Y)}  │  Leverage: {_p('AUTO', BD+R)}  │  Risk: {_p(f'${MAX_RISK_USDT}/trade', BD+W)}")
        print(f"  Daily Loss Limit: ${MAX_DAILY_LOSS_USDT}  │  Min Confidence: {MIN_CONFIDENCE}%  │  Cooldown: {COOLDOWN_SECONDS}s")
        print(f"  Hedge: {'✅ ON' if HEDGE_ENABLED else '❌ OFF'}  │  Max Positions: {MAX_OPEN_POSITIONS}")
        if self.is_enabled and os.environ.get("DELTA_USE_MAINNET","false").lower()=="true":
            print(f"\n  {_p('⚠️  REAL MONEY MODE — Real orders will be placed!', BD+R)}")
        print(f"{'═'*70}\n")

    def stop_monitor(self):
        self._monitor_running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=3)

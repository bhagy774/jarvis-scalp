#!/usr/bin/env python3
"""
JARVIS Live Auto-Trader
======================
Auto-executes CALL/PUT trades on Delta Exchange with:
  - 100x leverage (minimum, can be raised)
  - Dual-leg execution: Futures scalp + Options hedge
  - 3-tier safety gates before any real order
  - Real-time position monitor (TP/SL/expiry)
  - Emergency stop kill-switch

USAGE:
  Set in .env:
    DELTA_USE_MAINNET=true      # false = testnet
    JARVIS_AUTO_TRADE=true      # false = paper only
    JARVIS_LEVERAGE=100         # 100-200x
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
LEVERAGE            = int(os.environ.get("JARVIS_LEVERAGE",        "100"))
MAX_RISK_USDT       = float(os.environ.get("JARVIS_MAX_RISK_USDT", "10"))
MAX_DAILY_LOSS_USDT = float(os.environ.get("JARVIS_MAX_DAILY_LOSS","30"))
MAX_OPEN_POSITIONS  = int(os.environ.get("JARVIS_MAX_OPEN",        "2"))
MIN_CONFIDENCE      = int(os.environ.get("JARVIS_MIN_CONFIDENCE",  "70"))
COOLDOWN_SECONDS    = int(os.environ.get("JARVIS_COOLDOWN_SEC",    "180"))
CONSEC_LOSS_LIMIT   = int(os.environ.get("JARVIS_CONSEC_LOSS",     "3"))
AUTO_TRADE_ENABLED  = os.environ.get("JARVIS_AUTO_TRADE", "false").lower() == "true"
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
        self.is_enabled     = AUTO_TRADE_ENABLED
        self.emergency_stop = False

        # ── State ────────────────────────────────────────────────
        self.open_positions: List[Dict] = []
        self.closed_today:   List[Dict] = []
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

    def execute(self, direction: str, confidence: int,
                current_price: float, part_results: Dict = None,
                trade_type: str = "SCALP") -> Dict:
        """
        Main entry: receive signal → run all gates → place order.
        direction  : 'CALL' or 'PUT'
        trade_type : 'SCALP' or 'SWING'
        """
        if self.emergency_stop:
            return self._skip("🛑 EMERGENCY STOP ACTIVE")

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
            aligned, align_reason = oracle_gate.is_trade_aligned(direction)
            if not aligned:
                return self._skip(f"Gate0.5 ORACLE ALIGNMENT: {align_reason}")

            in_zone, zone_reason = oracle_gate.is_price_in_entry_zone(current_price)
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
                direction, confidence, current_price, part_results)

        # ─ Gate 3: Execute ───────────────────────────────────────
        return self._place_trade(
            direction, confidence, current_price, trade_type, hedge_plan)

    def trigger_emergency_stop(self):
        """Close ALL positions immediately."""
        self.emergency_stop = True
        print(f"\n{_p('🛑 ══ EMERGENCY STOP TRIGGERED ══ 🛑', BD+R)}")
        
        # --- WIRING FIX: MASS CLOSE & CANCEL ---
        self.cancel_open_orders()
        
        try:
            if hasattr(self.delta, 'close_all_positions'):
                result = self.delta.close_all_positions()
                if result:
                    print(f"  ✅ Mass-close successful via API")
                    self.open_positions = []
                    return
        except Exception as e:
            print(f"  ⚠️  Mass-close failed ({e}), falling back to 1-by-1...")
            
        closed = 0
        for pos in list(self.open_positions):
            try:
                result = self._close_position_market(pos)
                if result.get("success"):
                    closed += 1
                    print(f"  ✅ Closed #{pos['id']} at market")
                else:
                    print(f"  ❌ Failed to close #{pos['id']}: {result.get('error')}")
            except Exception as e:
                print(f"  ❌ Error closing #{pos['id']}: {e}")
        self.open_positions = []
        print(f"  Closed {closed} positions. System halted.")

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
            f"{_p('│',DG)} {_p(f'Lev: {LEVERAGE}x', BD+C)} "
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

    def _get_hedge_plan(self, direction, confidence, price, part_results) -> Dict:
        try:
            options_chain = {}
            try:
                options_chain = self.delta.get_options_chain("BTC")
            except Exception:
                pass

            atr = price * 0.004  # default 0.4% ATR
            expected_profit = price * SCALP_TP_PCT * (MAX_RISK_USDT * LEVERAGE / price)

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
                     trade_type, hedge_plan) -> Dict:
        """Execute both legs (futures + optional hedge)."""

        is_call    = direction in ("CALL", "BUY")
        futures_side = "buy" if is_call else "sell"

        # ── Dynamic symbol from Coin Scanner ────────────────────
        scanner = _get_coin_scanner()
        if scanner:
            symbol = scanner.get_delta_symbol()
        else:
            symbol = "BTCUSDT"

        # ── Calculate position size via Dynamic Sizer ────────────
        try:
            balance = self.delta.get_wallet_balance()
        except Exception:
            balance = MAX_RISK_USDT * 5

        sizer = _get_sizer(self.delta)
        if sizer:
            sizer.set_compound_pool(
                getattr(_get_position_manager(), "compounded_balance", 0)
            )
            size_info = sizer.calculate_size(confidence, symbol, force_balance=balance)
            contracts = size_info["contracts"]
            margin    = size_info["margin_usdt"]
        else:
            contracts = self._calc_contracts(price, balance)
            margin    = MAX_RISK_USDT

        tp_pct    = SWING_TP_PCT if trade_type == "SWING" else SCALP_TP_PCT
        sl_pct    = SWING_SL_PCT if trade_type == "SWING" else SCALP_SL_PCT
        tp_price  = round(price * (1 + tp_pct) if is_call else price * (1 - tp_pct), 2)
        sl_price  = round(price * (1 - sl_pct) if is_call else price * (1 + sl_pct), 2)

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

        # ── Print pre-trade summary ──────────────────────────────
        print(f"\n{'═'*70}")
        print(f"{_p('  🚀 JARVIS AUTO-TRADER — EXECUTING', BD+C)}")
        print(f"{'─'*70}")
        print(f"  {_p('Direction:', DG)} {_p(direction, BD+(G if is_call else R))}"
              f"   {_p('Type:', DG)} {trade_type}"
              f"   {_p('Confidence:', DG)} {_p(f'{confidence}%', BD+G)}")
        print(f"  {_p('Price:', DG)} ${price:,.2f}"
              f"   {_p('Leverage:', DG)} {_p(f'{LEVERAGE}x', BD+Y)}"
              f"   {_p('Contracts:', DG)} {contracts}")
        tp_note = f" (Oracle)" if (oracle_plan and oracle_plan.get("use_oracle")) else ""
        print(f"  {_p('TP:', DG)} {_p(f'${tp_price:,.2f}{tp_note}', BD+G)}"
              f"   {_p('SL:', DG)} {_p(f'${sl_price:,.2f}{tp_note}', BD+R)}"
              f"   {_p('Hold:', DG)} {hold_minutes}m")
        if oracle_plan and oracle_plan.get("use_oracle"):
            print(f"  {_p('Oracle Target:', DG)} {_p(oracle_plan.get('reason',''), BD+C)}")
        if hedge_plan.get("do_hedge"):
            print(f"  {_p('Hedge:', DG)} {_p('YES', BD+M if 'M' in dir() else BD+G)} "
                  f"→ {hedge_plan.get('option_type')} @ {hedge_plan.get('strike','?')}")
        print(f"{'─'*70}")

        # ─ LEG 1: Set leverage ───────────────────────────────────
        lev_ok = False
        try:
            lev_ok = self.delta.set_leverage(symbol, LEVERAGE)
            status = _p("✅ SET", BD+G) if lev_ok else _p("⚠️  FALLBACK", BD+Y)
            print(f"  {_p('LEG 0:', DG)} Leverage {LEVERAGE}x → {status}")
        except Exception as e:
            print(f"  {_p('LEG 0:', DG)} Leverage set error: {e}")

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
            print(f"  {_p('LEG 1:', DG)} {_p('✅ FILLED', BD+G)}"
                  f" | {futures_side.upper()} {contracts}x {symbol}"
                  f" | Order #{order_id}")
        else:
            print(f"  {_p('LEG 1:', DG)} {_p('❌ FAILED', BD+R)}"
                  f" | {futures_result.get('error','unknown')}")
            print(f"{'═'*70}\n")
            return {"success": False, "reason": "Futures order failed",
                    "error": futures_result.get("error")}

        # ─ LEG 2: Options hedge (if AI said YES) ─────────────────
        hedge_result = None
        if hedge_plan.get("do_hedge") and hedge_plan.get("strike"):
            try:
                opt_side   = "buy"  # Always BUY the protective option
                opt_type   = hedge_plan["option_type"]
                opt_strike = hedge_plan["strike"]
                opt_symbol = self._find_option_symbol(opt_type, opt_strike)

                if opt_symbol and self.is_enabled:
                    hedge_result = self.delta.place_option_order(opt_symbol, opt_side, 1)
                    if hedge_result and hedge_result.get("success"):
                        print(f"  {_p('LEG 2:', DG)} {_p('✅ HEDGE', BD+G)}"
                              f" | {opt_type} {opt_strike} | #{hedge_result.get('order_id','?')}")
                    else:
                        print(f"  {_p('LEG 2:', DG)} {_p('⚠️  Hedge failed (trading unhedged)', BD+Y)}")
                else:
                    print(f"  {_p('LEG 2:', DG)} {_p('⚠️  No option found — unhedged', BD+Y)}")
            except Exception as e:
                print(f"  {_p('LEG 2:', DG)} {_p(f'Hedge error: {e}', R)}")

        # ─ Record position ────────────────────────────────────────
        pos = {
            "id":          futures_result.get("order_id", f"pos_{int(time.time())}"),
            "direction":   direction,
            "entry_price": price,
            "tp_price":    tp_price,
            "sl_price":    sl_price,
            "contracts":   contracts,
            "trade_type":  trade_type,
            "confidence":  confidence,
            "leverage":    LEVERAGE,
            "open_time":   datetime.now().isoformat(),
            "expiry_time": (datetime.now() + timedelta(minutes=hold_minutes)).isoformat(),
            "hedge_id":    (hedge_result or {}).get("order_id"),
            "paper":       not self.is_enabled,
            "status":      "OPEN",
            "_last_reversal_check": datetime.now(),  # Track when we last re-evaluated
        }
        self.open_positions.append(pos)
        self.last_trade_time = datetime.now()
        self.daily_trades   += 1

        # ─ Register with Position Manager ────────────────────────
        pm = _get_position_manager()
        if pm:
            coin = symbol.replace("USDT", "")
            pm.register_position(
                position_id = str(pos["id"]),
                direction   = direction,
                entry_price = price,
                contracts   = contracts,
                confidence  = confidence,
                coin        = coin,
                trade_type  = trade_type,
            )

        # ─ Estimated P&L ─────────────────────────────────────────
        notional    = price * contracts / 1  # 1 contract = 1 USD on Delta perp
        risk_usdt   = notional * sl_pct
        reward_usdt = notional * tp_pct
        print(f"{'─'*70}")
        print(f"  {_p('RISK:', DG)}   ${risk_usdt:.2f}"
              f"   {_p('REWARD:', DG)} ${reward_usdt:.2f}"
              f"   {_p('R:R =', DG)} {_p(f'1:{reward_usdt/max(risk_usdt,0.01):.1f}', BD+G)}")
        if sizer:
            sizer.print_sizing(size_info)
        print(f"  Position ID: {_p(pos['id'], C)}")
        print(f"{'═'*70}\n")

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
        """Check all open positions every 5 seconds. Also runs reversal logic."""
        while self._monitor_running:
            try:
                current_price = self._get_price()
                if current_price and self.open_positions:
                    self._check_positions(current_price)
                    # Smart reversal: re-evaluate signals mid-trade
                    if REVERSAL_ENABLED and self._jarvis_ref and self._df_ref is not None:
                        self._check_reversals(current_price)
            except Exception as e:
                logger.debug(f"[MONITOR] Tick error: {e}")
            time.sleep(5)

    def _check_positions(self, current_price: float):
        """Check TP / SL / expiry for each open position."""
        still_open = []
        for pos in self.open_positions:
            closed, result, reason = False, None, None
            is_call = pos["direction"] in ("CALL", "BUY")
            tp = pos["tp_price"]
            sl = pos["sl_price"]
            exp = datetime.fromisoformat(pos["expiry_time"])

            if is_call:
                if current_price >= tp:
                    closed, result, reason = True, "WIN",  "✅ Take Profit"
                elif current_price <= sl:
                    closed, result, reason = True, "LOSS", "❌ Stop Loss"
            else:
                if current_price <= tp:
                    closed, result, reason = True, "WIN",  "✅ Take Profit"
                elif current_price >= sl:
                    closed, result, reason = True, "LOSS", "❌ Stop Loss"

            if not closed and datetime.now() >= exp:
                if is_call:
                    result = "WIN" if current_price > pos["entry_price"] else "LOSS"
                else:
                    result = "WIN" if current_price < pos["entry_price"] else "LOSS"
                reason = f"⏱️ Expiry ({'up' if current_price > pos['entry_price'] else 'down'})"
                closed = True

            if closed:
                pos["exit_price"]  = current_price
                pos["result"]      = result
                pos["close_reason"]= reason
                pos["close_time"]  = datetime.now().isoformat()
                pos["status"]      = "CLOSED"

                # Estimate P&L
                move_pct = abs(current_price - pos["entry_price"]) / pos["entry_price"]
                pnl_sign = 1 if result == "WIN" else -1
                pnl_usdt = pnl_sign * move_pct * pos["contracts"] * LEVERAGE
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
                print(f"  Entry: ${pos['entry_price']:,.2f} → Exit: ${current_price:,.2f}")
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

    def _check_reversals(self, current_price: float):
        """
        For each open position: if enough time has passed since last check,
        run JARVIS signal again. If signal flips with high confidence → reverse.
        """
        now = datetime.now()
        for pos in list(self.open_positions):
            if pos.get("status") != "OPEN":
                continue

            # Check if it's time to re-evaluate this position
            last_check = pos.get("_last_reversal_check")
            interval   = self._check_reversal_interval(pos)
            if last_check and (now - last_check).total_seconds() < interval:
                continue  # Not yet time

            pos["_last_reversal_check"] = now

            # Run JARVIS signal analysis
            try:
                result = self._jarvis_ref.analyze_trade_setup(self._df_ref)
                sig    = result.get("trade_signal", {})
                new_dir = sig.get("direction", "NO_TRADE")
                # Normalize direction
                if new_dir == "BUY":  new_dir = "CALL"
                elif new_dir == "SELL": new_dir = "PUT"
                raw_conf = sig.get("confidence_score", "0/100")
                try:
                    new_conf = int(float(str(raw_conf).split("/")[0]))
                except Exception:
                    new_conf = 0
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
            if new_conf < REVERSAL_MIN_CONFIDENCE:
                logger.debug(f"[REVERSAL] Signal flipped but conf {new_conf}% < {REVERSAL_MIN_CONFIDENCE}% threshold")
                continue

            # Optional: only reverse if already in some profit (not from a losing position)
            move_pct = (current_price - pos["entry_price"]) / pos["entry_price"]
            in_profit = (move_pct > REVERSAL_MIN_PROFIT_PCT and is_call) or \
                        (-move_pct > REVERSAL_MIN_PROFIT_PCT and not is_call)

            print(f"\n{'═'*70}")
            print(f"  {_p('🔄 REVERSAL SIGNAL DETECTED', BD+Y)}")
            print(f"  Position #{pos['id']}: {_p(old_dir, BD+(G if is_call else R))} "
                  f"→ Signal flipped to {_p(new_dir, BD+(R if is_call else G))}")
            print(f"  New Confidence: {_p(f'{new_conf}%', BD+G)} | "
                  f"In Profit: {_p('YES', BD+G) if in_profit else _p('NO', BD+R)}")

            if not in_profit:
                print(f"  {_p('⚠️  Skipping reversal — position not in profit yet', Y)}")
                print(f"{'═'*70}\n")
                continue

            # Execute reversal
            self._execute_reversal(pos, new_dir, new_conf, current_price)

    def _execute_reversal(self, pos: Dict, new_dir: str, confidence: int, price: float):
        """
        1. Close current position at market
        2. Open new position in opposite direction
        """
        print(f"  {_p('⚡ EXECUTING REVERSAL...', BD+C)}")

        # Step 1: Close current position
        close_result = self._close_position_market(pos)
        if not close_result.get("success"):
            print(f"  {_p('❌ Reversal FAILED — could not close current position', BD+R)}")
            print(f"{'═'*70}\n")
            return

        # Calculate P&L of closed position
        is_old_call = pos["direction"] in ("CALL", "BUY")
        move_pct = abs(price - pos["entry_price"]) / pos["entry_price"]
        is_win   = (price > pos["entry_price"] and is_old_call) or \
                   (price < pos["entry_price"] and not is_old_call)
        pnl_sign = 1 if is_win else -1
        pnl_usdt = pnl_sign * move_pct * pos["contracts"] * LEVERAGE

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

        col = BD+G if is_win else BD+Y
        print(f"  {_p('Position Closed:', DG)} {_p(pos['result'], col)} | "
              f"Entry ${pos['entry_price']:,.2f} → Exit ${price:,.2f} | "
              f"PnL: {_p(f'{pnl_usdt:+.3f}$', col)}")

        # Step 2: Check daily limits before opening reverse trade
        if self.daily_pnl <= -MAX_DAILY_LOSS_USDT:
            print(f"  {_p('⛔ Daily loss limit hit — not opening reverse trade', BD+R)}")
            print(f"{'═'*70}\n")
            self.trigger_emergency_stop()
            return

        if self.consec_losses >= CONSEC_LOSS_LIMIT:
            print(f"  {_p(f'⛔ {self.consec_losses} consecutive losses — not reversing', BD+R)}")
            print(f"{'═'*70}\n")
            return

        # Step 3: Open new reverse trade
        print(f"  {_p('Opening REVERSE trade:', DG)} {_p(new_dir, BD+(G if new_dir in ('CALL','BUY') else R))} "
              f"@ {_p(f'{confidence}%', BD+G)} confidence")
        print(f"{'─'*70}")

        # Brief delay to let market settle
        time.sleep(1)

        hedge_plan = {"do_hedge": False, "reason": "Reversal trade — no hedge"}
        trade_type = pos.get("trade_type", "SCALP")
        result = self._place_trade(new_dir, confidence, price, trade_type, hedge_plan)

        if result.get("success"):
            print(f"  {_p('✅ Reverse trade OPENED', BD+G)}")
        else:
            print(f"  {_p('⚠️  Reverse trade failed:', Y)} {result.get('reason', 'unknown')}")
        print(f"{'═'*70}\n")


    def _calc_contracts(self, price: float, balance: float) -> int:
        """
        Calculate # contracts.
        Delta BTC Perp: 1 contract = 1 USD notional.
        At 100x leverage, $1 margin controls $100 notional.
        MAX_RISK_USDT margin → MAX_RISK_USDT * LEVERAGE notional → contracts.
        """
        notional = MAX_RISK_USDT * LEVERAGE
        contracts = max(1, int(notional))   # min 1 contract
        return contracts

    def _get_price(self) -> Optional[float]:
        """Get live BTC price."""
        try:
            p = self.delta.get_live_price("BTCUSDT")
            if p and float(p) > 1000:
                return float(p)
        except Exception:
            pass
        return None

    def _find_option_symbol(self, option_type: str, strike: float) -> Optional[str]:
        """Find matching option contract symbol on Delta."""
        try:
            chain  = self.delta.get_options_chain("BTC")
            key    = "puts" if option_type == "PUT" else "calls"
            options = chain.get(key, [])
            if not options:
                return None
            best = min(options, key=lambda x: abs(x.get("strike", 0) - strike))
            return best.get("symbol")
        except Exception:
            return None

    def _close_position_market(self, pos: Dict) -> Dict:
        """Close a position at market price."""
        try:
            is_call    = pos["direction"] in ("CALL", "BUY")
            close_side = "sell" if is_call else "buy"
            if self.is_enabled:
                return self.delta.place_order(
                    symbol="BTCUSDT",
                    side=close_side,
                    size=pos["contracts"],
                    order_type="market"
                )
            else:
                return {"success": True, "paper": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _reset_daily(self):
        """Reset daily counters at midnight."""
        self.daily_pnl    = 0.0
        self.daily_trades = 0
        self.consec_losses = 0
        self.closed_today = []
        self.today_date   = date.today()
        logger.info("[TRADER] Daily stats reset at midnight")

    def _skip(self, reason: str) -> Dict:
        print(f"  {_p('⏸  AUTO-TRADE SKIPPED:', DG)} {reason}")
        return {"success": False, "skipped": True, "reason": reason}

    def _print_banner(self):
        mode  = "🔴 LIVE MAINNET" if (self.is_enabled and os.environ.get("DELTA_USE_MAINNET","false").lower()=="true") else "🟡 TESTNET/PAPER"
        print(f"\n{'═'*70}")
        print(f"  {_p('🤖 JARVIS AUTO-TRADER INITIALIZED', BD+C)}")
        print(f"  Mode: {_p(mode, BD+Y)}  │  Leverage: {_p(f'{LEVERAGE}x', BD+R)}  │  Risk: {_p(f'${MAX_RISK_USDT}/trade', BD+W)}")
        print(f"  Daily Loss Limit: ${MAX_DAILY_LOSS_USDT}  │  Min Confidence: {MIN_CONFIDENCE}%  │  Cooldown: {COOLDOWN_SECONDS}s")
        print(f"  Hedge: {'✅ ON' if HEDGE_ENABLED else '❌ OFF'}  │  Max Positions: {MAX_OPEN_POSITIONS}")
        if self.is_enabled and os.environ.get("DELTA_USE_MAINNET","false").lower()=="true":
            print(f"\n  {_p('⚠️  REAL MONEY MODE — Real orders will be placed!', BD+R)}")
        print(f"{'═'*70}\n")

    def stop_monitor(self):
        self._monitor_running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=3)

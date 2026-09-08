#!/usr/bin/env python3
"""
JARVIS FULL-FIDELITY BACKTESTER v1.0
Uses the REAL jarvis_FIXED.py system -- same as live trading

USAGE:
  python jarvis_backtester.py
  python jarvis_backtester.py --tf 5m --years 3 --capital 1000 --no-hedge
"""

import os, sys, json, math, time, argparse, logging, requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

if sys.platform == "win32":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except: pass

os.makedirs("data/backtest_cache", exist_ok=True)
os.makedirs("data/backtest_results", exist_ok=True)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("data/backtest.log", mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("JarvisBacktest")

R="\033[91m"; G="\033[92m"; Y="\033[93m"; C="\033[96m"; W="\033[97m"
DG="\033[90m"; BD="\033[1m"; RST="\033[0m"
def _p(text, *col): return "".join(col)+str(text)+RST

# ── CONFIG (same as jarvis_live_trader.py) ───────────────────────────────────
LEVERAGE            = int(os.environ.get("JARVIS_LEVERAGE",        "100"))
MAX_RISK_USDT       = float(os.environ.get("JARVIS_MAX_RISK_USDT", "10"))
MAX_DAILY_LOSS_USDT = float(os.environ.get("JARVIS_MAX_DAILY_LOSS","30"))
MAX_OPEN_POSITIONS  = int(os.environ.get("JARVIS_MAX_OPEN",        "2"))
MIN_CONFIDENCE      = int(os.environ.get("JARVIS_MIN_CONFIDENCE",  "70"))
COOLDOWN_SECONDS    = int(os.environ.get("JARVIS_COOLDOWN_SEC",    "180"))
CONSEC_LOSS_LIMIT   = int(os.environ.get("JARVIS_CONSEC_LOSS",     "3"))
SCALP_TP_PCT = 0.004; SCALP_SL_PCT = 0.002
SWING_TP_PCT = 0.020; SWING_SL_PCT = 0.008

BINANCE_BASE = "https://api.binance.com"
CACHE_DIR    = Path("data/backtest_cache")
RESULT_DIR   = Path("data/backtest_results")


# ═════════════════════════════════════════════════════════════════════════════
# 0. SAMPLED OLLAMA JUDGE
#    Calls the real Ollama (deepseek-r1 or any local model) every Nth signal.
#    Between calls, last verdict is cached and re-applied.
#    Falls back gracefully if Ollama is offline.
# ═════════════════════════════════════════════════════════════════════════════
class SampledOllamaJudge:
    """
    Wraps jarvis_FIXED.call_ollama() to validate signals every N trades.
    Between calls: last verdict is cached (same logic as live gap periods).
    """

    def __init__(self, every_n: int = 10, model: str = "deepseek-r1:14b", timeout: int = 90):
        """
        every_n : call Ollama on every Nth qualifying signal (default=10)
        model   : Ollama model to use (must match what jarvis_FIXED uses)
        timeout : seconds to wait for Ollama response
        """
        self.every_n   = every_n
        self.model     = model
        self.timeout   = timeout
        self._signal_count  = 0       # Total qualifying signals seen
        self._ollama_calls  = 0       # How many times Ollama was actually called
        self._ollama_ok     = 0       # Approved verdicts
        self._ollama_veto   = 0       # Rejected verdicts
        self._ollama_miss   = 0       # Times Ollama was offline
        # Last cached verdict: None = not yet called
        self._last_verdict: Optional[str] = None   # 'APPROVE' | 'REJECT' | None
        self._last_confidence_adj: int    = 0       # Confidence adjustment from last call
        self._ollama_available: Optional[bool] = None  # None = not yet checked

    def _check_ollama_available(self) -> bool:
        """Quick ping to see if Ollama is running."""
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def _call_ollama_raw(self, prompt: str) -> Optional[str]:
        """Call Ollama HTTP API directly (same endpoint as jarvis_FIXED.call_ollama)."""
        try:
            r = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=self.timeout
            )
            if r.status_code == 200:
                return r.json().get("response", "").strip()
        except Exception as e:
            logger.debug(f"[OllamaJudge] Request failed: {e}")
        return None

    def _build_prompt(self, direction: str, confidence: int, result: dict, price: float) -> str:
        """Build the same CEO/Judge prompt used in live jarvis_FIXED.py."""
        sig       = result.get("trade_signal", {})
        thoughts  = result.get("intelligence_board", [])[:5]
        mkt       = result.get("market_context", {})
        tp1       = sig.get("take_profit_1", "N/A")
        sl        = sig.get("stop_loss", "N/A")

        return f"""You are the Supreme Commander AI (CEO) of an elite quantitative trading system.

Trade Signal Summary:
- Direction: {direction}
- Confidence: {confidence}/100
- Entry Price: ${price:,.2f}
- TP1: {tp1}  |  SL: {sl}
- Market Context: {json.dumps(mkt, default=str)}

Sub-Agent Intelligence Board:
{chr(10).join(['- ' + str(t)[:100] for t in thoughts])}

Task: Validate this backtest signal.
- If setup is strong and signals agree: issue [CEO_VERDICT: EXECUTE]
- If signals conflict or risk is elevated: issue [CEO_VERDICT: STANDBY]
- If trap or severe divergence: issue [CEO_VERDICT: ABORT]

Respond with EXACTLY ONE tag at the start:
[CEO_VERDICT: EXECUTE] or [CEO_VERDICT: STANDBY] or [CEO_VERDICT: ABORT]
Then add one brief sentence of reasoning."""

    def validate(self, direction: str, confidence: int, result: dict, price: float) -> Tuple[str, int, str]:
        """
        Returns: (final_direction, adjusted_confidence, source)
          source = 'OLLAMA_FRESH' | 'OLLAMA_CACHED' | 'MATH_FALLBACK'

        Logic:
          - Every Nth signal: actually call Ollama → cache verdict
          - Between calls:    use cached verdict
          - If Ollama offline: pass-through (no change)
        """
        self._signal_count += 1

        # First time check: is Ollama running?
        if self._ollama_available is None:
            self._ollama_available = self._check_ollama_available()
            if self._ollama_available:
                print(f"\n  🧠 [OllamaJudge] Ollama ONLINE → sampling every {self.every_n} signals")
            else:
                print(f"\n  ⚠️  [OllamaJudge] Ollama OFFLINE → math fallback for all signals")

        # Ollama not available: just pass through
        if not self._ollama_available:
            self._ollama_miss += 1
            return direction, confidence, "MATH_FALLBACK"

        # Every Nth signal: call Ollama fresh
        if self._signal_count % self.every_n == 1 or self._last_verdict is None:
            self._ollama_calls += 1
            prompt   = self._build_prompt(direction, confidence, result, price)
            response = self._call_ollama_raw(prompt)

            if response:
                resp_upper = response.upper()
                if "EXECUTE" in resp_upper:
                    self._last_verdict = "APPROVE"
                    self._last_confidence_adj = +5   # Slight boost for AI approval
                    self._ollama_ok += 1
                elif "ABORT" in resp_upper:
                    self._last_verdict = "REJECT"
                    self._last_confidence_adj = -100  # Will cause signal to be dropped
                    self._ollama_veto += 1
                else:  # STANDBY
                    self._last_verdict = "STANDBY"
                    self._last_confidence_adj = -10

                logger.info(f"[OllamaJudge] Call #{self._ollama_calls}: {self._last_verdict} | {response[:80]}")
                source = "OLLAMA_FRESH"
            else:
                # Ollama call failed: pass-through this time
                self._ollama_miss += 1
                self._last_verdict = None
                logger.warning("[OllamaJudge] No response from Ollama, using math")
                return direction, confidence, "MATH_FALLBACK"
        else:
            source = "OLLAMA_CACHED"

        # Apply verdict
        if self._last_verdict == "REJECT":
            return "NO_TRADE", 0, source  # Drop signal
        elif self._last_verdict == "STANDBY":
            new_conf = max(0, confidence + self._last_confidence_adj)
            return direction, new_conf, source
        else:  # APPROVE
            new_conf = min(100, confidence + self._last_confidence_adj)
            return direction, new_conf, source

    def stats(self) -> str:
        """Human-readable stats for the report."""
        return (f"Signals:{self._signal_count} | Ollama calls:{self._ollama_calls} | "
                f"Approved:{self._ollama_ok} | Vetoed:{self._ollama_veto} | "
                f"Miss/Fallback:{self._ollama_miss}")


# ═════════════════════════════════════════════════════════════════════════════
# 1. BINANCE HISTORICAL DATA LOADER
# ═════════════════════════════════════════════════════════════════════════════
class BinanceHistoricalLoader:
    """Download & cache full OHLCV history from Binance public API."""

    INTERVAL_MS = {
        "1m": 60_000, "3m": 180_000, "5m": 300_000,
        "15m": 900_000, "30m": 1_800_000,
        "1h": 3_600_000, "4h": 14_400_000,
    }

    def __init__(self, symbol="BTCUSDT"):
        self.symbol = symbol.upper()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def load(self, interval="5m", years=3) -> pd.DataFrame:
        cache_file = CACHE_DIR / f"{self.symbol}_{interval}_{years}y.parquet"
        if cache_file.exists():
            age_h = (time.time() - cache_file.stat().st_mtime) / 3600
            if age_h < 6:
                print(f"  📦 Cache hit: {cache_file.name} ({age_h:.1f}h old)")
                df = pd.read_parquet(cache_file)
                print(f"  ✅ {len(df):,} candles loaded")
                return df
        print(f"\n  📡 Downloading {years}y {interval} data from Binance...")
        df = self._download(interval, years)
        if not df.empty:
            df.to_parquet(cache_file)
            print(f"  💾 Cached → {cache_file.name}")
        return df

    def _download(self, interval, years) -> pd.DataFrame:
        end_ms  = int(time.time() * 1000)
        iv_ms   = self.INTERVAL_MS.get(interval, 300_000)
        start   = end_ms - (years * 365 * 24 * 3600 * 1000)
        total_expected = (end_ms - start) // iv_ms
        print(f"  Expected ~{total_expected:,} candles")
        all_candles: list = []
        chunk = start
        downloaded = 0
        while chunk < end_ms:
            try:
                r = requests.get(
                    f"{BINANCE_BASE}/api/v3/klines",
                    params={"symbol": self.symbol, "interval": interval,
                            "startTime": chunk, "endTime": end_ms, "limit": 1000},
                    timeout=30)
                if r.status_code != 200:
                    time.sleep(2); continue
                raw = r.json()
                if not raw: break
                all_candles.extend(raw)
                downloaded += len(raw)
                pct = downloaded / max(total_expected, 1) * 100
                print(f"  ⬇  {downloaded:,}/{total_expected:,} ({pct:.0f}%)", end="\r")
                chunk = int(raw[-1][0]) + iv_ms
                time.sleep(0.12)
            except Exception as e:
                logger.warning(f"Chunk error: {e}"); time.sleep(3)
        print()
        if not all_candles:
            return pd.DataFrame()
        df = pd.DataFrame(all_candles,
            columns=["time","open","high","low","close","volume",
                     "ct","qv","trades","tb","tq","ign"])
        df = df[["time","open","high","low","close","volume"]].copy()
        for c in ["open","high","low","close","volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["time"] = pd.to_numeric(df["time"]) // 1000
        df.index = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_localize(None)
        df.drop(columns=["time"], inplace=True)
        df.sort_index(inplace=True)
        df.drop_duplicates(inplace=True)
        df.dropna(subset=["open","high","low","close"], inplace=True)
        print(f"  ✅ {len(df):,} candles ({df.index[0]} → {df.index[-1]})")
        return df


# ═════════════════════════════════════════════════════════════════════════════
# 2. BLACK-SCHOLES OPTIONS HEDGE SIMULATOR
# ═════════════════════════════════════════════════════════════════════════════
class OptionsHedgeSimulator:
    """Simulate options hedge cost & PnL with Black-Scholes."""

    @staticmethod
    def _ncdf(x):
        import math
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

    def bs_premium(self, S, K, T, r, sigma, opt):
        try:
            if T <= 0 or sigma <= 0:
                return max(0.0, (K-S) if opt=="PUT" else (S-K))
            import math
            d1 = (math.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*math.sqrt(T))
            d2 = d1 - sigma*math.sqrt(T)
            nc = self._ncdf
            if opt == "CALL":
                return S*nc(d1) - K*math.exp(-r*T)*nc(d2)
            return K*math.exp(-r*T)*nc(-d2) - S*nc(-d1)
        except:
            return max(0.0, (K-S) if opt=="PUT" else (S-K))

    def hedge_cost_and_pnl(self, entry, exit_p, direction, atr, ratio=0.5, size_usd=1000.0):
        import math
        opt = "PUT" if direction in ("CALL","BUY") else "CALL"
        K   = (entry - atr*0.5) if opt=="PUT" else (entry + atr*0.5)
        T   = 5 / (365*24*60)
        r   = 0.05
        sigma = max(0.3, min(2.0, (atr/entry)*math.sqrt(365*24*60)))
        ppu   = self.bs_premium(entry, K, T, r, sigma, opt)
        hc    = size_usd * ratio / entry
        cost  = ppu * hc
        intrinsic = max(0.0, (K-exit_p) if opt=="PUT" else (exit_p-K))
        pnl   = intrinsic*hc - cost
        return cost, pnl


# ═════════════════════════════════════════════════════════════════════════════
# 3. POSITION TRACKER (mirrors JarvisAutoTrader exactly)
# ═════════════════════════════════════════════════════════════════════════════
class BacktestPosition:
    _ctr = 0

    def __init__(self, direction, entry_price, entry_time, contracts,
                 trade_type="SCALP", confidence=0, hedge_cost=0.0, hedge_ratio=0.0):
        BacktestPosition._ctr += 1
        self.id = BacktestPosition._ctr
        self.direction = direction; self.entry_price = entry_price
        self.entry_time = entry_time; self.contracts = contracts
        self.confidence = confidence; self.trade_type = trade_type
        self.hedge_cost = hedge_cost; self.hedge_ratio = hedge_ratio
        # TP/SL same as JarvisAutoTrader._place_trade()
        tp_pct = SWING_TP_PCT if trade_type=="SWING" else SCALP_TP_PCT
        sl_pct = SWING_SL_PCT if trade_type=="SWING" else SCALP_SL_PCT
        is_c = direction in ("CALL","BUY")
        self.tp_price = round(entry_price*(1+tp_pct) if is_c else entry_price*(1-tp_pct), 2)
        self.sl_price = round(entry_price*(1-sl_pct) if is_c else entry_price*(1+sl_pct), 2)
        exp_m = 5 if trade_type=="SCALP" else 60
        self.expiry_time = entry_time + timedelta(minutes=exp_m)
        self.status="OPEN"; self.exit_price=None; self.exit_time=None
        self.result=None; self.close_reason=None
        self.pnl_usdt=0.0; self.hedge_pnl=0.0

    def check(self, price, dt):
        if self.status != "OPEN": return None
        is_c = self.direction in ("CALL","BUY")
        if is_c and price >= self.tp_price: return "TP HIT"
        if not is_c and price <= self.tp_price: return "TP HIT"
        if is_c and price <= self.sl_price: return "SL HIT"
        if not is_c and price >= self.sl_price: return "SL HIT"
        if dt >= self.expiry_time:
            if is_c: return "EXPIRY WIN" if price > self.entry_price else "EXPIRY LOSS"
            else:    return "EXPIRY WIN" if price < self.entry_price else "EXPIRY LOSS"
        return None

    def close(self, exit_price, exit_time, reason, hedge_pnl=0.0):
        self.exit_price=exit_price; self.exit_time=exit_time
        self.close_reason=reason; self.status="CLOSED"; self.hedge_pnl=hedge_pnl
        move_pct = abs(exit_price - self.entry_price) / self.entry_price
        is_win   = reason in ("TP HIT","EXPIRY WIN")
        sign     = 1 if is_win else -1
        futures_pnl = sign * move_pct * self.contracts * LEVERAGE
        self.pnl_usdt = futures_pnl + hedge_pnl - self.hedge_cost
        self.result   = "WIN" if is_win else "LOSS"
        return self.pnl_usdt


# ═════════════════════════════════════════════════════════════════════════════
# 4. RISK GATES (exact copy of JarvisAutoTrader._check_risk_gates)
# ═════════════════════════════════════════════════════════════════════════════
class BacktestRiskGate:
    def __init__(self):
        self.daily_pnl=0.0; self.consec_losses=0
        self.last_trade_dt: Optional[datetime]=None
        self.open_positions: List[BacktestPosition]=[]
        self.today_date=None

    def reset_daily(self, d):
        if d != self.today_date:
            self.daily_pnl=0.0; self.consec_losses=0; self.today_date=d

    def can_trade(self, confidence, dt) -> Tuple[bool, str]:
        self.reset_daily(dt.date())
        if confidence < MIN_CONFIDENCE:   return False, f"Conf {confidence}%<{MIN_CONFIDENCE}%"
        if self.daily_pnl <= -MAX_DAILY_LOSS_USDT: return False, f"Daily loss ${self.daily_pnl:.1f}"
        if self.consec_losses >= CONSEC_LOSS_LIMIT: return False, f"{self.consec_losses} consec losses"
        if len(self.open_positions) >= MAX_OPEN_POSITIONS: return False, f"Max {MAX_OPEN_POSITIONS} open"
        if self.last_trade_dt:
            elapsed = (dt - self.last_trade_dt).total_seconds()
            if elapsed < COOLDOWN_SECONDS:
                return False, f"Cooldown {int(COOLDOWN_SECONDS-elapsed)}s"
        return True, "OK"

    def record_open(self, pos, dt):
        self.open_positions.append(pos); self.last_trade_dt=dt

    def record_close(self, pos):
        if pos in self.open_positions: self.open_positions.remove(pos)
        self.daily_pnl += pos.pnl_usdt
        self.consec_losses = 0 if pos.result=="WIN" else self.consec_losses+1

    def calc_contracts(self, price):
        return max(1, int(MAX_RISK_USDT * LEVERAGE))


# ═════════════════════════════════════════════════════════════════════════════
# 5. SIGNAL EXTRACTION HELPER
# ═════════════════════════════════════════════════════════════════════════════
def extract_signal(result: dict) -> Tuple[str, int]:
    """Parse (direction, confidence) from jarvis.analyze_trade_setup() output."""
    sig  = result.get("trade_signal", {})
    direction = sig.get("direction", "NO_TRADE")
    raw  = sig.get("confidence_score", "0/100")
    try:
        conf = int(float(str(raw).split("/")[0]))
    except:
        conf = 0
    if direction == "BUY":  direction = "CALL"
    elif direction == "SELL": direction = "PUT"
    return direction, conf


# ═════════════════════════════════════════════════════════════════════════════
# 6. MAIN BACKTESTER
# ═════════════════════════════════════════════════════════════════════════════
class JarvisFullBacktester:
    """
    Candle-by-candle backtest using real JarvisElite.analyze_trade_setup().
    Mirrors LiveTradingEngine.start_live_trading() exactly.
    """

    def __init__(self, symbol="BTCUSDT", timeframe="5m", years=3,
                 starting_capital=1000.0, hedge_enabled=True,
                 hedge_ratio=0.5, warmup=100, ollama_every=0,
                 ollama_model="deepseek-r1:14b"):
        self.symbol=symbol; self.timeframe=timeframe; self.years=years
        self.starting_capital=starting_capital; self.hedge_enabled=hedge_enabled
        self.hedge_ratio=hedge_ratio; self.warmup=warmup
        self.ollama_every=ollama_every  # 0 = disabled
        self.gate = BacktestRiskGate()
        self.hsim = OptionsHedgeSimulator()
        # Sampled Ollama Judge (only created if ollama_every > 0)
        self.ollama_judge: Optional[SampledOllamaJudge] = (
            SampledOllamaJudge(every_n=ollama_every, model=ollama_model)
            if ollama_every > 0 else None
        )
        self.all_trades: List[BacktestPosition] = []
        self.balance=starting_capital; self.peak=starting_capital
        self.equity_curve: List[Dict] = []
        self.n_no_signal=0; self.n_skip_gate=0; self.n_ollama_veto=0

    def _init_jarvis(self):
        print("  🤖 Initializing JarvisElite...")
        from jarvis_FIXED import JarvisElite
        j = JarvisElite()
        j.print_dashboard = lambda *args, **kwargs: None  # Mute dashboard in backtest
        # Always disable Ollama INSIDE jarvis_FIXED — we manage it externally
        # via SampledOllamaJudge so we control exactly when it's called
        j.is_backtest_mode = True
        j.deepseek_enabled = False
        if self.ollama_judge:
            print(f"  🧠 OllamaJudge: ENABLED — calling every {self.ollama_every} signals")
        else:
            print("  ✅ JarvisElite ready (math mode, no Ollama)")
        return j

    def run(self):
        ollama_mode = f"ON (every {self.ollama_every} signals)" if self.ollama_judge else "OFF (math only)"
        print(f"\n{'═'*70}")
        print(f"  🚀 JARVIS FULL-FIDELITY BACKTESTER")
        print(f"{'═'*70}")
        print(f"  Symbol: {self.symbol}  |  TF: {self.timeframe}  |  Years: {self.years}")
        print(f"  Capital: ${self.starting_capital:,.2f}  |  Leverage: {LEVERAGE}x  |  MinConf: {MIN_CONFIDENCE}%")
        print(f"  Hedge: {'ON ratio='+str(self.hedge_ratio) if self.hedge_enabled else 'OFF'}  |  Ollama Judge: {ollama_mode}")
        print(f"{'═'*70}\n")

        loader = BinanceHistoricalLoader(self.symbol)
        df     = loader.load(self.timeframe, self.years)
        if df.empty or len(df) < self.warmup + 50:
            print("❌ Not enough data."); return

        jarvis = self._init_jarvis()
        total  = len(df)
        print(f"\n  📊 Backtesting {total:,} candles (warmup={self.warmup})...\n")
        BAR = 50

        for i in range(self.warmup, total):
            ws = max(0, i-500)
            df_win = df.iloc[ws:i].copy()
            price  = float(df.iloc[i]["close"])
            dt     = df.index[i].to_pydatetime()

            # Progress
            if (i-self.warmup) % 500 == 0 or i == total-1:
                done  = i-self.warmup; tot2 = total-self.warmup
                pct   = done/tot2; fill = int(BAR*pct)
                bar   = "█"*fill + "─"*(BAR-fill)
                ws2   = sum(1 for t in self.all_trades if t.result=="WIN")
                nt    = len(self.all_trades)
                wr    = ws2/nt*100 if nt else 0
                print(f"\r  [{bar}] {pct*100:.0f}% | {i:,}/{total:,} | "
                      f"Trades:{nt} WR:{wr:.0f}% Bal:${self.balance:,.0f}",
                      end="", flush=True)

            # Check positions
            self._check_positions(price, dt)

            # Equity snapshot
            if (i-self.warmup) % 100 == 0:
                self.equity_curve.append({
                    "time": dt.isoformat(), "balance": self.balance,
                    "price": price, "open": len(self.gate.open_positions),
                    "trades": len(self.all_trades)
                })

            # Run JARVIS signal
            try:
                result = jarvis.analyze_trade_setup(df_win)
            except Exception as e:
                logger.debug(f"analyze error at {dt}: {e}"); continue

            direction, confidence = extract_signal(result)

            if direction not in ("CALL","PUT"):
                self.n_no_signal += 1; continue

            # ── SAMPLED OLLAMA JUDGE ──────────────────────────────────────────
            # Called every N qualifying signals; caches verdict between calls.
            # Falls back to math if Ollama is offline.
            if self.ollama_judge:
                direction, confidence, ollama_src = self.ollama_judge.validate(
                    direction, confidence, result, price)
                if direction == "NO_TRADE":
                    self.n_ollama_veto += 1
                    self.n_no_signal += 1
                    continue
            # ─────────────────────────────────────────────────────────────────

            ok, reason = self.gate.can_trade(confidence, dt)
            if not ok:
                self.n_skip_gate += 1; continue

            contracts = self.gate.calc_contracts(price)
            ts = result.get("trade_signal",{}).get("recommended_expiry","SCALP")
            trade_type = "SWING" if str(ts).upper() in ("SWING","DAY_TRADE") else "SCALP"

            hedge_cost = 0.0
            if self.hedge_enabled:
                try:
                    atr = float((df_win["high"]-df_win["low"]).rolling(14).mean().iloc[-1])
                    if atr > 0:
                        hedge_cost, _ = self.hsim.hedge_cost_and_pnl(
                            price, price, direction, atr,
                            self.hedge_ratio, MAX_RISK_USDT*LEVERAGE)
                except: pass

            pos = BacktestPosition(direction, price, dt, contracts, trade_type,
                                   confidence, hedge_cost, self.hedge_ratio if self.hedge_enabled else 0.0)
            self.gate.record_open(pos, dt); self.all_trades.append(pos)

        print()
        # Force-close remaining
        lp = float(df.iloc[-1]["close"]); lt = df.index[-1].to_pydatetime()
        for pos in list(self.gate.open_positions):
            is_c = pos.direction in ("CALL","BUY")
            r = "EXPIRY WIN" if (is_c and lp>pos.entry_price) or (not is_c and lp<pos.entry_price) else "EXPIRY LOSS"
            pnl = pos.close(lp, lt, r, 0.0)
            self.balance += pnl; self.gate.record_close(pos)

        self._report(df)

    def _check_positions(self, price, dt):
        for pos in list(self.gate.open_positions):
            r = pos.check(price, dt)
            if r:
                hp = 0.0
                if self.hedge_enabled and pos.hedge_ratio > 0 and pos.hedge_cost > 0:
                    atr = pos.entry_price * 0.004
                    _, hp = self.hsim.hedge_cost_and_pnl(pos.entry_price, price,
                        pos.direction, atr, pos.hedge_ratio, MAX_RISK_USDT*LEVERAGE)
                pnl = pos.close(price, dt, r, hp)
                self.balance += pnl
                self.peak = max(self.peak, self.balance)
                self.gate.record_close(pos)

    def _report(self, df):
        print(f"\n{'═'*70}")
        closed = [t for t in self.all_trades if t.status=="CLOSED"]
        wins   = [t for t in closed if t.result=="WIN"]
        losses = [t for t in closed if t.result=="LOSS"]
        nt = len(closed)
        wr = len(wins)/nt*100 if nt else 0
        tpnl = sum(t.pnl_usdt for t in closed)
        aw = sum(t.pnl_usdt for t in wins)/max(1,len(wins))
        al = sum(t.pnl_usdt for t in losses)/max(1,len(losses))
        pf = abs(sum(t.pnl_usdt for t in wins)/sum(t.pnl_usdt for t in losses)) if losses else float("inf")
        dd = self._maxdd(); sh = self._sharpe(closed)
        col_wr  = BD+G if wr>=50 else BD+R
        col_pnl = BD+G if tpnl>=0 else BD+R
        print(f"  🏆 BACKTEST RESULTS — {self.symbol} {self.timeframe} {self.years}y")
        print(f"{'═'*70}")
        print(f"  Total Trades:       {nt}")
        print(f"  Win Rate:           {_p(f'{wr:.1f}%', col_wr)}")
        print(f"  Wins / Losses:      {len(wins)} / {len(losses)}")
        print(f"  Avg Win / Loss:     ${aw:.2f} / ${al:.2f}")
        print(f"  Profit Factor:      {_p(f'{pf:.2f}', BD+G if pf>1 else BD+R)}")
        print(f"  Max Drawdown:       {_p(f'{dd:.1f}%', BD+R)}")
        print(f"  Sharpe Ratio:       {_p(f'{sh:.2f}', BD+G if sh>1 else BD+Y)}")
        print(f"  Starting Capital:   ${self.starting_capital:,.2f}")
        print(f"  Final Balance:      {_p(f'${self.balance:,.2f}', col_pnl)}")
        pnl_sign = "+" if tpnl >= 0 else ""
        print(f"  Total PnL:          {_p(f'{pnl_sign}${tpnl:.2f}', col_pnl)}")
        print(f"  Leverage:           {LEVERAGE}x")
        print(f"  No-Trade Signals:   {self.n_no_signal}")
        print(f"  Skipped (Gate):     {self.n_skip_gate}")
        if self.ollama_judge:
            print(f"  Ollama Judge:       {self.ollama_judge.stats()}")
            print(f"  Ollama Vetoes:      {self.n_ollama_veto}")
        print(f"{'═'*70}")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = RESULT_DIR / f"backtest_{self.symbol}_{self.timeframe}_{self.years}y_{ts}"
        self._csv(closed, prefix)
        self._chart(prefix)
        self._html(prefix, closed, wins, losses, nt, wr, tpnl, aw, al, pf, dd, sh, ts)
        print(f"\n  ✅ Reports → {RESULT_DIR}/")
        print(f"     CSV:  {prefix.name}.csv")
        print(f"     Chart: {prefix.name}_equity.png")
        print(f"     HTML: {prefix.name}.html\n")

    def _maxdd(self):
        if not self.equity_curve: return 0.0
        peak=self.starting_capital; dd=0.0
        for e in self.equity_curve:
            peak = max(peak, e["balance"])
            dd   = max(dd, (peak-e["balance"])/peak*100 if peak>0 else 0)
        return dd

    def _sharpe(self, closed):
        if len(closed)<2: return 0.0
        pnls = [t.pnl_usdt for t in closed]
        mu=np.mean(pnls); std=np.std(pnls, ddof=1)
        if std==0: return 0.0
        return float(mu/std*np.sqrt(365*5))

    def _csv(self, closed, prefix):
        rows=[{
            "id":t.id,"direction":t.direction,"type":t.trade_type,
            "confidence":t.confidence,"entry_time":t.entry_time,
            "exit_time":t.exit_time,"entry":t.entry_price,"exit":t.exit_price,
            "contracts":t.contracts,"leverage":LEVERAGE,
            "tp":t.tp_price,"sl":t.sl_price,"reason":t.close_reason,
            "result":t.result,"futures_pnl":round(t.pnl_usdt-t.hedge_pnl+t.hedge_cost,4),
            "hedge_cost":round(t.hedge_cost,4),"hedge_pnl":round(t.hedge_pnl,4),
            "net_pnl":round(t.pnl_usdt,4)
        } for t in closed]
        pd.DataFrame(rows).to_csv(f"{prefix}.csv", index=False)

    def _chart(self, prefix):
        try:
            import matplotlib; matplotlib.use("Agg")
            import matplotlib.pyplot as plt, matplotlib.gridspec as gs
            eq = pd.DataFrame(self.equity_curve)
            if eq.empty: return
            eq["time"] = pd.to_datetime(eq["time"])
            fig = plt.figure(figsize=(16,10), facecolor="#0d1117")
            g = gs.GridSpec(2,1,height_ratios=[3,1],hspace=0.08)
            ax1 = fig.add_subplot(g[0]); ax2 = fig.add_subplot(g[1], sharex=ax1)
            ax1.plot(eq["time"],eq["balance"],color="#00ff88",lw=1.5,label="Balance")
            ax1.axhline(self.starting_capital,color="#888",lw=0.8,ls="--",alpha=0.5)
            ax1.fill_between(eq["time"],eq["balance"],self.starting_capital,
                where=eq["balance"]>=self.starting_capital,alpha=0.12,color="#00ff88")
            ax1.fill_between(eq["time"],eq["balance"],self.starting_capital,
                where=eq["balance"]<self.starting_capital,alpha=0.12,color="#ff4444")
            for ax in (ax1,ax2):
                ax.set_facecolor("#0d1117"); ax.tick_params(colors="gray")
                ax.spines[:].set_color("#333")
            ax1.set_title(
                f"JARVIS Backtest — {self.symbol} {self.timeframe} {self.years}y | {LEVERAGE}x | "
                f"${self.starting_capital:,.0f}→${self.balance:,.0f}",
                color="white",fontsize=12,pad=10)
            ax1.set_ylabel("Balance (USDT)",color="gray")
            ax1.legend(facecolor="#1a1a2e",edgecolor="#333",labelcolor="white",fontsize=9)
            ax2.plot(eq["time"],eq["price"],color="#ffd700",lw=0.8,alpha=0.8)
            ax2.set_ylabel("BTC Price",color="gray"); ax2.set_xlabel("Date",color="gray")
            plt.setp(ax1.get_xticklabels(),visible=False)
            plt.savefig(f"{prefix}_equity.png",dpi=150,bbox_inches="tight",facecolor="#0d1117")
            plt.close(fig)
        except ImportError:
            print("  ⚠️  pip install matplotlib  (for chart)")
        except Exception as e:
            logger.warning(f"Chart: {e}")

    def _html(self, prefix, closed, wins, losses, nt, wr, tpnl, aw, al, pf, dd, sh, ts):
        cname=f"{prefix.name}_equity.png"; csvn=f"{prefix.name}.csv"
        rows=""
        for t in closed[-100:]:
            c="#00ff88" if t.result=="WIN" else "#ff4444"
            dc="#00ff88" if t.direction=="CALL" else "#ff4444"
            rows+=f"<tr><td>{t.id}</td><td style='color:{dc}'>{t.direction}</td><td>{t.trade_type}</td><td>{t.confidence}%</td><td>${t.entry_price:,.2f}</td><td>${t.exit_price:,.2f}</td><td>{t.close_reason}</td><td style='color:{c}'>{t.result}</td><td style='color:{c}'>{'+' if t.pnl_usdt>=0 else ''}${t.pnl_usdt:.2f}</td></tr>"
        wc="#00ff88" if wr>=50 else "#ff4444"
        pc="#00ff88" if tpnl>=0 else "#ff4444"
        html=f"""<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>
<title>JARVIS Backtest — {self.symbol} {self.timeframe}</title>
<style>@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&family=JetBrains+Mono&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d1117;color:#e6edf3;font-family:'Outfit',sans-serif;padding:24px}}
h1{{text-align:center;font-size:2rem;background:linear-gradient(135deg,#00ff88,#00bbff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}}
.sub{{text-align:center;color:#8b949e;margin-bottom:28px;font-size:.9rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:28px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:18px;text-align:center}}
.card .lbl{{color:#8b949e;font-size:.75rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}}
.card .val{{font-size:1.7rem;font-weight:700;font-family:'JetBrains Mono'}}
.chart{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:14px;margin-bottom:28px;text-align:center}}
.chart img{{max-width:100%;border-radius:8px}}
table{{width:100%;border-collapse:collapse;background:#161b22;border-radius:12px;overflow:hidden;border:1px solid #30363d;margin-bottom:16px}}
th{{background:#21262d;color:#8b949e;padding:10px 14px;text-align:left;font-size:.75rem;text-transform:uppercase;letter-spacing:1px}}
td{{padding:8px 14px;border-bottom:1px solid #21262d;font-family:'JetBrains Mono';font-size:.82rem}}
tr:last-child td{{border-bottom:none}}tr:hover{{background:#1c2128}}
.cfg{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:18px;margin-bottom:28px}}
.cfg h3{{color:#00bbff;margin-bottom:10px}}.cfg p{{color:#8b949e;font-size:.82rem;line-height:2;font-family:'JetBrains Mono'}}
.footer{{text-align:center;color:#30363d;font-size:.78rem;margin-top:28px}}
</style></head><body>
<h1>🤖 JARVIS Backtest Report</h1>
<p class='sub'>{ts} | {self.symbol} {self.timeframe} | {self.years}y | {LEVERAGE}x Leverage</p>
<div class='cfg'><h3>⚙️ Config</h3><p>
Symbol:{self.symbol} | TF:{self.timeframe} | Years:{self.years} | Leverage:{LEVERAGE}x | Capital:${self.starting_capital:,.0f}<br>
MinConf:{MIN_CONFIDENCE}% | Cooldown:{COOLDOWN_SECONDS}s | MaxDailyLoss:${MAX_DAILY_LOSS_USDT} | MaxOpen:{MAX_OPEN_POSITIONS}<br>
TP:{SCALP_TP_PCT*100:.1f}% SL:{SCALP_SL_PCT*100:.1f}% | Hedge:{'ON ratio='+str(self.hedge_ratio) if self.hedge_enabled else 'OFF'}
</p></div>
<div class='grid'>
<div class='card'><div class='lbl'>Total Trades</div><div class='val' style='color:#00bbff'>{nt}</div></div>
<div class='card'><div class='lbl'>Win Rate</div><div class='val' style='color:{wc}'>{wr:.1f}%</div></div>
<div class='card'><div class='lbl'>Final Balance</div><div class='val' style='color:{pc}'>${self.balance:,.0f}</div></div>
<div class='card'><div class='lbl'>Total PnL</div><div class='val' style='color:{pc}'>{'+' if tpnl>=0 else ''}${tpnl:.0f}</div></div>
<div class='card'><div class='lbl'>Profit Factor</div><div class='val' style='color:{"#00ff88" if pf>1 else "#ff4444"}'>{pf:.2f}</div></div>
<div class='card'><div class='lbl'>Max Drawdown</div><div class='val' style='color:#ff4444'>{dd:.1f}%</div></div>
<div class='card'><div class='lbl'>Sharpe</div><div class='val' style='color:#ffd700'>{sh:.2f}</div></div>
<div class='card'><div class='lbl'>Avg Win/Loss</div><div class='val' style='font-size:1rem;color:#8b949e'>+${aw:.1f} / -${abs(al):.1f}</div></div>
</div>
<div class='chart'><img src='{cname}' alt='Equity Curve' onerror="this.parentNode.innerHTML='<p style=color:#8b949e>Chart file: '+'{cname}'+'</p>'"></div>
<h2 style='color:#8b949e;font-size:.85rem;text-transform:uppercase;letter-spacing:2px;margin-bottom:12px'>📋 Last 100 Trades</h2>
<table><thead><tr><th>#</th><th>Dir</th><th>Type</th><th>Conf</th><th>Entry</th><th>Exit</th><th>Reason</th><th>Result</th><th>Net PnL</th></tr></thead>
<tbody>{rows}</tbody></table>
<p style='text-align:center;color:#8b949e;font-size:.8rem'>Full CSV: <a href='{csvn}' style='color:#00bbff'>{csvn}</a></p>
<p class='footer'>JARVIS Backtest Engine | Real analyze_trade_setup() | No Lookahead Bias</p>
</body></html>"""
        with open(f"{prefix}.html","w",encoding="utf-8") as f: f.write(html)


# ═════════════════════════════════════════════════════════════════════════════
# 7. CLI
# ═════════════════════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser(
        description="JARVIS Full-Fidelity Backtester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python jarvis_backtester.py                          # Math only (fastest)
  python jarvis_backtester.py --ollama-every 10        # Ollama every 10 signals
  python jarvis_backtester.py --ollama-every 5 --tf 15m --years 2
""")
    p.add_argument("--symbol",        default="BTCUSDT",       help="Trading pair (default: BTCUSDT)")
    p.add_argument("--tf",            default="5m",            help="Timeframe: 1m 5m 15m 1h (default: 5m)")
    p.add_argument("--years",         default=3,  type=int,   help="Years of history (default: 3)")
    p.add_argument("--capital",       default=1000.0, type=float, help="Starting capital USDT (default: 1000)")
    p.add_argument("--no-hedge",      action="store_true",     help="Disable options hedge simulation")
    p.add_argument("--hedge-ratio",   default=0.5, type=float,help="Hedge size ratio (default: 0.5)")
    p.add_argument("--warmup",        default=100, type=int,  help="Warmup candles (default: 100)")
    p.add_argument("--ollama-every",  default=0,  type=int,
        help="Call Ollama judge every N signals (0=disabled, 10=recommended). "
             "Ollama must be running at localhost:11434")
    p.add_argument("--ollama-model",  default="deepseek-r1:14b",
        help="Ollama model name (default: deepseek-r1:14b)")
    args = p.parse_args()
    os.makedirs("data", exist_ok=True)
    bt = JarvisFullBacktester(
        symbol=args.symbol, timeframe=args.tf, years=args.years,
        starting_capital=args.capital, hedge_enabled=not args.no_hedge,
        hedge_ratio=args.hedge_ratio, warmup=args.warmup,
        ollama_every=args.ollama_every, ollama_model=args.ollama_model)
    bt.run()

if __name__ == "__main__":
    main()

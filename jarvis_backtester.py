#!/usr/bin/env python3
"""JARVIS historical replay runner.

This runner feeds only locally supplied, completed OHLCV candles to the same
``JarvisElite.analyze_trade_setup`` math/GPU decision path used by live mode.
It has no market-data downloader, model endpoint, or trading-client code.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

RESULT_DIR = Path("data/backtest_results")
LEVERAGE = int(os.environ.get("JARVIS_LEVERAGE", "100"))
MAX_RISK_USDT = float(os.environ.get("JARVIS_MAX_RISK_USDT", "10"))
MAX_DAILY_LOSS_USDT = float(os.environ.get("JARVIS_MAX_DAILY_LOSS", "30"))
MAX_OPEN_POSITIONS = int(os.environ.get("JARVIS_MAX_OPEN", "2"))
MIN_CONFIDENCE = int(os.environ.get("JARVIS_MIN_CONFIDENCE", "70"))
COOLDOWN_SECONDS = int(os.environ.get("JARVIS_COOLDOWN_SEC", "180"))
CONSEC_LOSS_LIMIT = int(os.environ.get("JARVIS_CONSEC_LOSS", "3"))
SCALP_TP_PCT, SCALP_SL_PCT = 0.004, 0.002
SWING_TP_PCT, SWING_SL_PCT = 0.020, 0.008

logger = logging.getLogger("JarvisBacktest")

# These are the 12 local core adapters actually wired into JarvisElite.  The
# mapping makes the report explicit about what candle-only replay can prove.
CORE_PART_DATA_CONTRACT = {
    'part1_breakout': 'OHLCV', 'part2_zone': 'OHLCV', 'part3_psychology': 'OHLCV',
    'part4_volume': 'OHLCV volume (institutional feed unavailable)',
    'part5_ml': 'OHLCV-derived features', 'part6_trend': 'OHLCV',
    'part7_volatility': 'OHLCV', 'part8_structure': 'OHLCV',
    'part9_orderflow': 'OHLCV volume proxy (not tick/order-book flow)',
    'part10_candlestats': 'OHLCV', 'part11_fusion': 'outputs of Parts 1-10',
    'part12_confidence': 'outputs of Parts 1-11',
}
HISTORICAL_DATA_NOT_IN_OHLCV = (
    'timestamp-matched options chain/OI/PCR', 'funding-rate history',
    'order-book/tick trades', 'liquidations', 'dated cross-exchange snapshots',
)


class HistoricalCandleLoader:
    """Read a local, immutable historical OHLCV export; never fetches a feed."""

    REQUIRED = ("open", "high", "low", "close", "volume")

    def __init__(self, source: Path):
        self.source = source

    def load(self) -> pd.DataFrame:
        if not self.source.is_file():
            raise FileNotFoundError(f"Historical data file not found: {self.source}")
        suffix = self.source.suffix.lower()
        if suffix in (".parquet", ".pq"):
            df = pd.read_parquet(self.source)
        elif suffix in (".csv", ".txt"):
            df = pd.read_csv(self.source)
        else:
            raise ValueError("Historical input must be CSV or Parquet")
        df.columns = [str(c).strip().lower() for c in df.columns]
        time_col = next((c for c in ("timestamp", "time", "datetime", "date") if c in df.columns), None)
        if time_col is None:
            if not isinstance(df.index, pd.DatetimeIndex):
                raise ValueError("Historical input needs timestamp/time/datetime/date or a DatetimeIndex")
        else:
            raw = df.pop(time_col)
            # Numeric exports are conventionally seconds or milliseconds.
            if pd.api.types.is_numeric_dtype(raw):
                unit = "ms" if raw.dropna().abs().median() > 10_000_000_000 else "s"
                df.index = pd.to_datetime(raw, unit=unit, utc=True).dt.tz_localize(None)
            else:
                df.index = pd.to_datetime(raw, utc=True).dt.tz_localize(None)
        missing = set(self.REQUIRED) - set(df.columns)
        if missing:
            raise ValueError(f"Historical input missing columns: {sorted(missing)}")
        df = df.loc[:, self.REQUIRED].copy()
        for col in self.REQUIRED:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna().sort_index()
        if df.index.has_duplicates:
            raise ValueError("Historical input contains duplicate timestamps")
        if len(df) < 2 or not df.index.is_monotonic_increasing:
            raise ValueError("Historical input must contain ordered completed candles")
        if (df[["open", "high", "low", "close"]] <= 0).any().any():
            raise ValueError("OHLC prices must be positive")
        if (df["high"] < df[["open", "close", "low"]].max(axis=1)).any() or (df["low"] > df[["open", "close", "high"]].min(axis=1)).any():
            raise ValueError("Invalid OHLC range in historical input")
        return df


def extract_signal(result: dict) -> Tuple[str, int]:
    """Parse a direction and confidence from the central decision result."""
    signal = result.get("trade_signal", {})
    direction = str(signal.get("direction", "NO_TRADE")).upper()
    raw = signal.get("confidence_score", "0/100")
    try:
        confidence = int(float(str(raw).split("/")[0]))
    except (TypeError, ValueError):
        confidence = 0
    return {"BUY": "CALL", "SELL": "PUT"}.get(direction, direction), confidence


class BacktestPosition:
    """A filled futures position using deterministic OHLC execution assumptions."""

    _ctr = 0

    def __init__(self, direction: str, entry_price: float, entry_time: datetime,
                 contracts: float, trade_type: str = "SCALP", confidence: int = 0,
                 slippage_bps: float = 5.0, fee_bps: float = 10.0):
        BacktestPosition._ctr += 1
        self.id = BacktestPosition._ctr
        self.direction, self.entry_price, self.entry_time = direction, entry_price, entry_time
        self.contracts, self.trade_type, self.confidence = contracts, trade_type, confidence
        self.slippage_bps, self.fee_bps = slippage_bps, fee_bps
        tp_pct = SWING_TP_PCT if trade_type == "SWING" else SCALP_TP_PCT
        sl_pct = SWING_SL_PCT if trade_type == "SWING" else SCALP_SL_PCT
        self.is_call = direction in ("CALL", "BUY")
        self.tp_price = entry_price * (1 + tp_pct if self.is_call else 1 - tp_pct)
        self.sl_price = entry_price * (1 - sl_pct if self.is_call else 1 + sl_pct)
        self.expiry_time = entry_time + timedelta(minutes=60 if trade_type == "SWING" else 5)
        self.status = "OPEN"
        self.exit_price: Optional[float] = None
        self.exit_time: Optional[datetime] = None
        self.close_reason: Optional[str] = None
        self.result: Optional[str] = None
        self.gross_pnl = 0.0
        self.fees_usdt = 0.0
        self.pnl_usdt = 0.0

    @property
    def slippage_rate(self) -> float:
        return self.slippage_bps / 10_000.0

    @property
    def fee_rate(self) -> float:
        # ``fee_bps`` is explicitly a round-trip assumption, split across fills.
        return self.fee_bps / 20_000.0

    def adverse_exit_fill(self, raw_price: float) -> float:
        """Long exits receive less; short exits pay more."""
        return raw_price * (1 - self.slippage_rate if self.is_call else 1 + self.slippage_rate)

    def check_candle(self, candle: pd.Series, dt: datetime, at_entry: bool = False) -> Optional[Tuple[str, float]]:
        """Return a reason/raw exit price. Same-bar TP+SL resolves to SL first."""
        high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])
        tp_hit = high >= self.tp_price if self.is_call else low <= self.tp_price
        sl_hit = low <= self.sl_price if self.is_call else high >= self.sl_price
        if tp_hit and sl_hit:
            return "SL HIT (same-bar conservative)", self.sl_price
        if sl_hit:
            return "SL HIT", self.sl_price
        if tp_hit:
            return "TP HIT", self.tp_price
        if dt >= self.expiry_time:
            return "EXPIRY", close
        return None

    def close(self, raw_exit_price: float, exit_time: datetime, reason: str) -> float:
        self.exit_price = self.adverse_exit_fill(raw_exit_price)
        self.exit_time, self.close_reason, self.status = exit_time, reason, "CLOSED"
        signed_move = (self.exit_price - self.entry_price) if self.is_call else (self.entry_price - self.exit_price)
        self.gross_pnl = signed_move * self.contracts
        self.fees_usdt = (self.entry_price + self.exit_price) * self.contracts * self.fee_rate
        self.pnl_usdt = self.gross_pnl - self.fees_usdt
        self.result = "WIN" if self.pnl_usdt > 0 else "LOSS"
        return self.pnl_usdt


class BacktestRiskGate:
    def __init__(self):
        self.daily_pnl = 0.0
        self.consec_losses = 0
        self.last_trade_dt: Optional[datetime] = None
        self.open_positions: List[BacktestPosition] = []
        self.today_date = None

    def reset_daily(self, day) -> None:
        if day != self.today_date:
            self.daily_pnl, self.consec_losses, self.today_date = 0.0, 0, day

    def can_trade(self, confidence: int, dt: datetime) -> Tuple[bool, str]:
        self.reset_daily(dt.date())
        if confidence < MIN_CONFIDENCE:
            return False, f"confidence {confidence}% < {MIN_CONFIDENCE}%"
        if self.daily_pnl <= -MAX_DAILY_LOSS_USDT:
            return False, f"daily loss ${self.daily_pnl:.2f}"
        if self.consec_losses >= CONSEC_LOSS_LIMIT:
            return False, f"{self.consec_losses} consecutive losses"
        if len(self.open_positions) >= MAX_OPEN_POSITIONS:
            return False, f"max {MAX_OPEN_POSITIONS} open positions"
        if self.last_trade_dt and (dt - self.last_trade_dt).total_seconds() < COOLDOWN_SECONDS:
            return False, "cooldown"
        return True, "OK"

    def record_open(self, position: BacktestPosition, dt: datetime) -> None:
        self.open_positions.append(position)
        self.last_trade_dt = dt

    def record_close(self, position: BacktestPosition) -> None:
        if position in self.open_positions:
            self.open_positions.remove(position)
        self.daily_pnl += position.pnl_usdt
        self.consec_losses = 0 if position.result == "WIN" else self.consec_losses + 1

    def calc_contracts(self, entry_price: float, stop_trigger: float, direction: str,
                       cash_balance: float, fee_bps: float, slippage_bps: float) -> float:
        """Size base-asset quantity by worst stop loss, then cap gross exposure."""
        if entry_price <= 0 or cash_balance <= 0:
            return 0.0
        is_call = direction in ("CALL", "BUY")
        adverse_stop = stop_trigger * (1 - slippage_bps / 10_000 if is_call else 1 + slippage_bps / 10_000)
        loss_per_unit = abs(entry_price - adverse_stop) + (entry_price + adverse_stop) * fee_bps / 20_000
        if loss_per_unit <= 0:
            return 0.0
        used_notional = sum(p.entry_price * p.contracts for p in self.open_positions)
        exposure_room = max(0.0, cash_balance * LEVERAGE - used_notional)
        quantity = min(MAX_RISK_USDT / loss_per_unit, exposure_room / entry_price)
        # Deterministic quantity precision without forcing an unaffordable one-unit trade.
        return math.floor(max(0.0, quantity) * 100_000_000) / 100_000_000


class JarvisFullBacktester:
    """Historical-only replay with central math/GPU decision analysis in isolation mode."""

    def __init__(self, symbol: str = "BTCUSDT", timeframe: str = "5m", years: int = 3,
                 starting_capital: float = 1000.0, warmup: int = 100,
                 slippage_bps: float = 5.0, fee_bps: float = 10.0):
        self.symbol, self.timeframe, self.years = symbol.upper(), timeframe, years
        self.starting_capital, self.warmup = starting_capital, warmup
        self.slippage_bps, self.fee_bps = slippage_bps, fee_bps
        self.gate = BacktestRiskGate()
        self.all_trades: List[BacktestPosition] = []
        self.balance = self.peak = starting_capital
        self.equity_curve: List[Dict[str, object]] = []
        self.n_no_signal = self.n_skip_gate = self.n_unaffordable = 0
        self.part_activity = {name: {'decisions_seen': 0, 'non_neutral': 0, 'offline': 0}
                              for name in CORE_PART_DATA_CONTRACT}

    def _init_jarvis(self):
        print("  Initializing JarvisElite central math/GPU decision path (isolated replay)...")
        from jarvis_FIXED import JarvisElite
        # This must remain true: it preserves analysis engines while blocking live-only inputs.
        brain = JarvisElite(backtest_mode=True)
        brain.print_dashboard = lambda *args, **kwargs: None
        return brain

    def _record_part_activity(self, brain) -> None:
        """Keep auditable proof that each core adapter participated in replay."""
        results = getattr(brain, 'latest_part_results', {}) or {}
        for name in CORE_PART_DATA_CONTRACT:
            result = results.get(name, {})
            if not isinstance(result, dict):
                self.part_activity[name]['offline'] += 1
                continue
            self.part_activity[name]['decisions_seen'] += 1
            if str(result.get('thought', '')).lower() == 'part offline':
                self.part_activity[name]['offline'] += 1
            try:
                if float(result.get('signal', 0)) != 0:
                    self.part_activity[name]['non_neutral'] += 1
            except (TypeError, ValueError):
                self.part_activity[name]['offline'] += 1

    def _part_coverage(self) -> dict:
        coverage = {}
        for name, source in CORE_PART_DATA_CONTRACT.items():
            stats = self.part_activity[name]
            coverage[name] = {
                'historical_input': source,
                **stats,
                'active': stats['decisions_seen'] > 0 and stats['offline'] == 0,
            }
        return coverage

    def _entry_fill(self, direction: str, opening_price: float) -> float:
        adverse = self.slippage_bps / 10_000.0
        return opening_price * (1 + adverse if direction == "CALL" else 1 - adverse)

    def _close_position(self, position: BacktestPosition, raw_exit: float, dt: datetime, reason: str) -> None:
        self.balance += position.close(raw_exit, dt, reason)
        self.peak = max(self.peak, self.balance)
        self.gate.record_close(position)

    def _check_open_positions(self, candle: pd.Series, dt: datetime) -> None:
        for position in list(self.gate.open_positions):
            outcome = position.check_candle(candle, dt)
            if outcome:
                reason, raw_exit = outcome
                self._close_position(position, raw_exit, dt, reason)

    def run(self, data_file: Path) -> None:
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        df = HistoricalCandleLoader(data_file).load()
        if len(df) < self.warmup + 2:
            raise ValueError("Not enough historical candles after warmup")
        print("\n" + "=" * 70)
        print("JARVIS HISTORICAL REPLAY")
        print("=" * 70)
        print(f"Symbol: {self.symbol} | TF label: {self.timeframe} | candles: {len(df):,}")
        print(f"Capital: ${self.starting_capital:,.2f} | leverage cap: {LEVERAGE}x | risk budget: ${MAX_RISK_USDT:.2f}")
        print(f"Execution assumptions (conservative, user-configurable; not exchange facts): entry/exit slippage {self.slippage_bps:.2f} bps adverse each side; round-trip fee {self.fee_bps:.2f} bps")
        print("Data isolation: local historical input only. No live feed, client, or remote model path.")
        print("=" * 70)
        brain = self._init_jarvis()

        # At i, only candles ending before i are visible to the decision. A qualifying
        # signal then fills at candle i OPEN and faces candle i HIGH/LOW thereafter.
        for i in range(self.warmup, len(df)):
            dt = df.index[i].to_pydatetime()
            candle = df.iloc[i]
            self._check_open_positions(candle, dt)
            self.equity_curve.append({"time": dt.isoformat(), "balance": self.balance,
                                      "price": float(candle["close"]), "open": len(self.gate.open_positions),
                                      "trades": len(self.all_trades)})
            ws = max(0, i - 500)
            df_win = df.iloc[ws:i].copy()  # excludes candle i: no signal lookahead
            try:
                result = brain.analyze_trade_setup(df_win)
                self._record_part_activity(brain)
            except Exception as exc:
                logger.debug("analysis failure at %s: %s", dt, exc)
                continue
            direction, confidence = extract_signal(result)
            if direction not in ("CALL", "PUT"):
                self.n_no_signal += 1
                continue
            allowed, _ = self.gate.can_trade(confidence, dt)
            if not allowed:
                self.n_skip_gate += 1
                continue
            opening_price = float(df.iloc[i]["open"])
            entry_price = self._entry_fill(direction, opening_price)
            trade_type = str(result.get("trade_signal", {}).get("recommended_expiry", "SCALP")).upper()
            trade_type = "SWING" if trade_type in ("SWING", "DAY_TRADE") else "SCALP"
            provisional = BacktestPosition(direction, entry_price, dt, 0.0, trade_type, confidence,
                                            self.slippage_bps, self.fee_bps)
            quantity = self.gate.calc_contracts(entry_price, provisional.sl_price, direction,
                                                self.balance, self.fee_bps, self.slippage_bps)
            if quantity <= 0:
                self.n_unaffordable += 1
                continue
            position = BacktestPosition(direction, entry_price, dt, quantity, trade_type, confidence,
                                        self.slippage_bps, self.fee_bps)
            self.gate.record_open(position, dt)
            self.all_trades.append(position)
            # Entry is at this open, so only this candle's subsequent range can trigger it.
            outcome = position.check_candle(candle, dt, at_entry=True)
            if outcome:
                reason, raw_exit = outcome
                self._close_position(position, raw_exit, dt, reason)

        final_dt = df.index[-1].to_pydatetime()
        final_close = float(df.iloc[-1]["close"])
        for position in list(self.gate.open_positions):
            self._close_position(position, final_close, final_dt, "END OF DATA")
        self._report(df)

    def _maxdd(self) -> float:
        peak, worst = self.starting_capital, 0.0
        for point in self.equity_curve:
            peak = max(peak, float(point["balance"]))
            worst = max(worst, (peak - float(point["balance"])) / peak * 100 if peak else 0.0)
        return worst

    @staticmethod
    def _sharpe(closed: List[BacktestPosition]) -> float:
        if len(closed) < 2:
            return 0.0
        values = np.array([trade.pnl_usdt for trade in closed])
        std = values.std(ddof=1)
        return float(values.mean() / std * math.sqrt(365 * 5)) if std else 0.0

    def _report(self, df: pd.DataFrame) -> None:
        closed = [trade for trade in self.all_trades if trade.status == "CLOSED"]
        wins = [trade for trade in closed if trade.result == "WIN"]
        losses = [trade for trade in closed if trade.result == "LOSS"]
        net = sum(trade.pnl_usdt for trade in closed)
        gross = sum(trade.gross_pnl for trade in closed)
        fees = sum(trade.fees_usdt for trade in closed)
        wr = 100 * len(wins) / len(closed) if closed else 0.0
        loss_sum = sum(trade.pnl_usdt for trade in losses)
        pf = abs(sum(trade.pnl_usdt for trade in wins) / loss_sum) if loss_sum else float("inf")
        dd, sharpe = self._maxdd(), self._sharpe(closed)
        print("\n" + "=" * 70)
        print("HISTORICAL REPLAY RESULTS")
        print("=" * 70)
        print(f"Trades: {len(closed)} | wins/losses: {len(wins)}/{len(losses)} | net win rate: {wr:.1f}%")
        print(f"Gross PnL: ${gross:.2f} | modeled fees: ${fees:.2f} | net PnL: ${net:.2f}")
        print(f"Final balance: ${self.balance:.2f} | profit factor: {pf:.2f} | max drawdown: {dd:.2f}% | Sharpe: {sharpe:.2f}")
        print(f"Signals excluded: no-decision {self.n_no_signal}; risk-gated {self.n_skip_gate}; zero-size {self.n_unaffordable}")
        print("Parity: decisions use the central JarvisElite core math/GPU path in backtest isolation mode.")
        print("Parity limitation: historical replay does not reproduce historical options-chain or cross-exchange snapshots unless a dated historical dataset is supplied to that decision pipeline.")
        print("Those omitted live-only inputs are excluded; they are never treated as neutral or positive confirmation.")
        print("=" * 70)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = RESULT_DIR / f"backtest_{self.symbol}_{self.timeframe}_{stamp}"
        self._csv(closed, prefix)
        self._html(prefix, closed, net, gross, fees, wr, dd, sharpe, stamp)
        coverage = self._part_coverage()
        coverage_path = prefix.with_name(prefix.name + '_part_coverage.json')
        coverage_path.write_text(json.dumps({
            'core_parts': coverage,
            'not_replayed_without_timestamped_datasets': HISTORICAL_DATA_NOT_IN_OHLCV,
            'options_chain_vote_included': False,
        }, indent=2), encoding='utf-8')
        active = sum(1 for item in coverage.values() if item['active'])
        print(f"Core Part coverage: {active}/12 active; detailed audit: {coverage_path.name}")
        print("Historical options/OI/funding/order-book are not in OHLCV and do not vote in this replay.")
        print(f"Reports: {prefix.name}.csv, {prefix.name}.html and {coverage_path.name}")

    def _csv(self, closed: List[BacktestPosition], prefix: Path) -> None:
        rows = [{"id": t.id, "direction": t.direction, "type": t.trade_type, "confidence": t.confidence,
                 "entry_time": t.entry_time, "exit_time": t.exit_time, "entry_fill": t.entry_price,
                 "exit_fill": t.exit_price, "quantity_base": t.contracts, "tp_trigger": t.tp_price,
                 "sl_trigger": t.sl_price, "reason": t.close_reason, "result": t.result,
                 "gross_pnl": round(t.gross_pnl, 8), "fees_usdt": round(t.fees_usdt, 8),
                 "net_pnl": round(t.pnl_usdt, 8)} for t in closed]
        pd.DataFrame(rows).to_csv(f"{prefix}.csv", index=False)

    def _html(self, prefix: Path, closed: List[BacktestPosition], net: float, gross: float,
              fees: float, wr: float, dd: float, sharpe: float, stamp: str) -> None:
        rows = "".join(
            f"<tr><td>{t.id}</td><td>{t.direction}</td><td>{t.confidence}%</td><td>{t.entry_price:.2f}</td><td>{t.exit_price:.2f}</td><td>{t.close_reason}</td><td>{t.pnl_usdt:.4f}</td></tr>"
            for t in closed[-100:])
        html = f"""<!doctype html><html><head><meta charset='utf-8'><title>JARVIS historical replay</title>
<style>body{{font-family:system-ui;background:#10151c;color:#e8edf2;margin:2rem}}section,table{{background:#19212b;padding:1rem;margin:1rem 0;border-radius:8px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:.5rem;text-align:left;border-bottom:1px solid #334}}</style></head><body>
<h1>JARVIS Historical Replay</h1><p>{stamp} · {self.symbol} · {self.timeframe}</p>
<section><h2>Results</h2><p>Net PnL: ${net:.2f}; gross PnL: ${gross:.2f}; modeled fees: ${fees:.2f}; net win rate: {wr:.1f}%; max drawdown: {dd:.2f}%; Sharpe: {sharpe:.2f}</p></section>
<section><h2>Execution assumptions</h2><p>Conservative, user-configurable assumptions rather than exchange facts: adverse entry/exit slippage {self.slippage_bps:.2f} bps each side; round-trip trading fee {self.fee_bps:.2f} bps. Entries fill at next candle open; TP/SL use high/low; a same-candle dual touch resolves to SL first.</p></section>
<section><h2>Core Part coverage</h2><p>The companion <code>_part_coverage.json</code> records every one of the 12 core parts, its candle-derived input, decision count, non-neutral votes, and any offline status.</p></section>
<section><h2>Decision-path parity and limitation</h2><p>Decisions use the central JarvisElite core math/GPU decision path in isolation mode. Historical options-chain/OI/PCR, funding, order-book, liquidation, and cross-exchange snapshots require timestamp-matched datasets. They are excluded from OHLCV-only replay and cannot vote as neutral or positive confirmation.</p></section>
<table><thead><tr><th>#</th><th>Direction</th><th>Confidence</th><th>Entry fill</th><th>Exit fill</th><th>Reason</th><th>Net PnL</th></tr></thead><tbody>{rows}</tbody></table>
<footer>JARVIS Backtest Engine | Core math/GPU decision path | Historical replay only</footer></body></html>"""
        prefix.with_suffix(".html").write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS isolated historical replay")
    parser.add_argument("--data-file", required=True, type=Path, help="Local completed OHLCV CSV or Parquet")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--tf", default="5m", help="Label only; input timestamps remain authoritative")
    parser.add_argument("--years", default=3, type=int, help="Label only; local input remains authoritative")
    parser.add_argument("--capital", default=1000.0, type=float)
    parser.add_argument("--warmup", default=100, type=int)
    parser.add_argument("--slippage-bps", default=5.0, type=float,
                        help="Adverse entry and exit slippage per side; conservative assumption, default 5")
    parser.add_argument("--fee-bps", default=10.0, type=float,
                        help="Round-trip trading fee; conservative assumption, default 10")
    args = parser.parse_args()
    if args.capital <= 0 or args.warmup < 20 or args.slippage_bps < 0 or args.fee_bps < 0:
        parser.error("capital must be positive; warmup >=20; costs must be non-negative")
    runner = JarvisFullBacktester(args.symbol, args.tf, args.years, args.capital, args.warmup,
                                  args.slippage_bps, args.fee_bps)
    runner.run(args.data_file)


if __name__ == "__main__":
    main()

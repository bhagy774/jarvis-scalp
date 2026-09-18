"""Shared, fail-closed Part 7 volatility analysis.

Part 7 is an analysis consumer of the canonical native exchange candle snapshot;
it is not a candle builder.  The implementation intentionally keeps the
existing Bollinger/Keltner/ATR calculations in Pandas and reports that backend
as CPU.  GPU benchmarking is a separate future change, not implied by legacy
class names elsewhere in the repository.
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, Mapping, Optional, Sequence

import pandas as pd


DEFAULT_TIMEFRAMES = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h")
_INTERVAL_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900,
    "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400,
}
_REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


def _symbol(value: Any) -> str:
    return str(value or "").upper().replace("/", "").replace("-", "").replace("_", "")


def _base_result(
    *,
    symbol: str,
    timeframe: str,
    signal: int = 0,
    status: str,
    reason: str,
    data_status: str,
    volatility_status: str = "unknown",
    entry_blocked: bool = False,
    risk_veto: bool = False,
    telemetry: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    direction = "CALL" if signal > 0 else "PUT" if signal < 0 else "NEUTRAL"
    return {
        "signal": int(signal),
        "signal_identity": f"part7:{_symbol(symbol) or 'UNKNOWN'}:{timeframe}",
        "signal_name": direction,
        "symbol": _symbol(symbol) or "UNKNOWN",
        "timeframe": timeframe,
        "status": status,
        "reason": reason,
        "thought": reason,
        "data_status": data_status,
        "volatility_status": volatility_status,
        "entry_blocked": bool(entry_blocked),
        "risk_veto": bool(risk_veto),
        "computation_backend": "pandas_cpu",
        "computation_engine": "pandas",
        "accelerator": "cpu",
        "telemetry": dict(telemetry or {}),
    }


def _blocked(symbol: str, timeframe: str, status: str, reason: str, data_status: str) -> Dict[str, Any]:
    return _base_result(
        symbol=symbol,
        timeframe=timeframe,
        status=status,
        reason=reason,
        data_status=data_status,
        entry_blocked=True,
    )


def _validate_frame(data: Any, symbol: str, timeframe: str, context: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(data, pd.DataFrame):
        return _blocked(symbol, timeframe, "invalid", "Part7 data invalid: expected Pandas DataFrame", "invalid")
    missing = [column for column in _REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        return _blocked(symbol, timeframe, "invalid", f"Part7 data invalid: missing columns {','.join(missing)}", "invalid")
    expected_symbol = _symbol(context.get("selected_symbol") or context.get("symbol") or symbol)
    frame_symbol = _symbol(data.attrs.get("symbol"))
    if not context.get("is_backtest_mode", False) and not expected_symbol:
        return _blocked(symbol, timeframe, "invalid", "Part7 selected symbol missing", "invalid")
    if expected_symbol and not frame_symbol and not context.get("is_backtest_mode", False):
        return _blocked(symbol, timeframe, "symbol_mismatch", "Part7 data symbol identity missing", "invalid")
    if expected_symbol and frame_symbol and expected_symbol != frame_symbol:
        return _blocked(symbol, timeframe, "symbol_mismatch", f"Part7 data symbol mismatch: {frame_symbol} != {expected_symbol}", "invalid")
    if timeframe not in _INTERVAL_SECONDS:
        return _blocked(symbol, timeframe, "invalid", f"Part7 unsupported timeframe: {timeframe}", "invalid")
    if len(data) < 30:
        return _blocked(symbol, timeframe, "invalid", f"Part7 data invalid: insufficient candles ({len(data)} < 30)", "invalid")
    try:
        numeric = data.loc[:, _REQUIRED_COLUMNS].apply(pd.to_numeric, errors="coerce")
        if numeric.isna().any().any() or not numeric.map(math.isfinite).all().all():
            return _blocked(symbol, timeframe, "invalid", "Part7 data invalid: non-finite OHLCV", "invalid")
        if (numeric[["open", "high", "low", "close"]] <= 0).any().any():
            return _blocked(symbol, timeframe, "invalid", "Part7 data invalid: non-positive price", "invalid")
        if (numeric["high"] < numeric[["open", "close"]].max(axis=1)).any() or (numeric["low"] > numeric[["open", "close"]].min(axis=1)).any():
            return _blocked(symbol, timeframe, "invalid", "Part7 data invalid: OHLC bounds", "invalid")
    except Exception as exc:
        return _blocked(symbol, timeframe, "error", f"Part7 data validation error: {type(exc).__name__}", "error")

    # Direct live frames are closed native candles and must carry a real
    # timestamp index so stale/future data cannot enter the analysis path.
    if not context.get("is_backtest_mode", False):
        if not isinstance(data.index, pd.DatetimeIndex):
            return _blocked(symbol, timeframe, "invalid", "Part7 data timestamp index missing", "invalid")
        try:
            last = data.index[-1]
            if getattr(last, "tzinfo", None) is None:
                last = last.tz_localize("UTC")
            age = time.time() - float(last.timestamp())
            max_age = _INTERVAL_SECONDS[timeframe] * 3
            if age > max_age:
                return _blocked(symbol, timeframe, "stale", f"Part7 data stale: closed {int(age)}s ago", "stale")
            if age < -5:
                return _blocked(symbol, timeframe, "invalid", "Part7 data timestamp is in the future", "invalid")
        except Exception as exc:
            return _blocked(symbol, timeframe, "error", f"Part7 timestamp validation error: {type(exc).__name__}", "error")
    return None


def analyze_timeframe(data: Any, *, symbol: str, timeframe: str, context: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Analyze one already-selected native exchange timeframe.

    Neutral market conditions remain neutral.  Missing, malformed, stale,
    wrong-symbol, and exceptional inputs are distinct fail-closed statuses and
    block new entries while leaving protective exit code outside this analyzer.
    """
    context = dict(context or {})
    symbol = _symbol(symbol or context.get("selected_symbol")) or "UNKNOWN"
    timeframe = str(timeframe)
    invalid = _validate_frame(data, symbol, timeframe, context)
    if invalid is not None:
        return invalid
    try:
        recent = data.loc[:, _REQUIRED_COLUMNS].tail(50).astype(float)
        closes = recent["close"]
        highs = recent["high"]
        lows = recent["low"]
        current_close = float(closes.iloc[-1])
        sma20 = float(closes.tail(20).mean())
        std20 = float(closes.tail(20).std()) + 1e-8
        upper_bb = sma20 + 2.0 * std20
        lower_bb = sma20 - 2.0 * std20
        bb_width = (upper_bb - lower_bb) / max(sma20, 1.0)
        pct_b = (current_close - lower_bb) / (upper_bb - lower_bb + 1e-8)
        tr = pd.concat([
            highs - lows,
            (highs - closes.shift(1)).abs(),
            (lows - closes.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr14 = float(tr.tail(14).mean())
        atr50 = float(tr.tail(50).mean()) if len(tr) >= 50 else atr14
        ema20 = float(closes.ewm(span=20).mean().iloc[-1])
        upper_kc = ema20 + 1.5 * atr14
        lower_kc = ema20 - 1.5 * atr14
        is_squeeze = (upper_bb < upper_kc) and (lower_bb > lower_kc)
        vol_ratio = atr14 / (atr50 + 1e-8)
        norm_atr = atr14 / max(current_close, 1.0)
        telemetry = {
            "bb_width_pct": round(bb_width * 100, 3),
            "pct_b": round(pct_b, 4),
            "atr14": round(atr14, 8),
            "vol_ratio": round(vol_ratio, 4),
            "norm_atr_pct": round(norm_atr * 100, 4),
            "is_squeeze": bool(is_squeeze),
        }
        if vol_ratio > 2.8 or norm_atr > 0.015:
            return _base_result(
                symbol=symbol, timeframe=timeframe, status="veto",
                reason=f"Part7 extreme volatility veto: ATR={norm_atr * 100:.2f}% ratio={vol_ratio:.2f}x",
                data_status="valid", volatility_status="extreme", entry_blocked=True,
                risk_veto=True, telemetry=telemetry,
            )
        if is_squeeze:
            return _base_result(
                symbol=symbol, timeframe=timeframe, status="neutral",
                reason=f"Part7 squeeze/normal volatility: BBw={bb_width * 100:.2f}%",
                data_status="valid", volatility_status="compressed", telemetry=telemetry,
            )
        if pct_b >= 0.85 and current_close > upper_bb and vol_ratio >= 1.0:
            conf = min(85.0, 60.0 + (pct_b - 0.85) * 100.0 + min(vol_ratio, 2.0) * 5.0)
            return _base_result(
                symbol=symbol, timeframe=timeframe, signal=1, status="ok",
                reason=f"Part7 bullish volatility expansion: %B={pct_b:.2f} ratio={vol_ratio:.2f}x",
                data_status="valid", volatility_status="expanding", telemetry={**telemetry, "confidence": round(conf, 1)},
            )
        if pct_b <= 0.15 and current_close < lower_bb and vol_ratio >= 1.0:
            conf = min(85.0, 60.0 + (0.15 - pct_b) * 100.0 + min(vol_ratio, 2.0) * 5.0)
            return _base_result(
                symbol=symbol, timeframe=timeframe, signal=-1, status="ok",
                reason=f"Part7 bearish volatility breakdown: %B={pct_b:.2f} ratio={vol_ratio:.2f}x",
                data_status="valid", volatility_status="expanding", telemetry={**telemetry, "confidence": round(conf, 1)},
            )
        return _base_result(
            symbol=symbol, timeframe=timeframe, status="neutral",
            reason=f"Part7 stable volatility: %B={pct_b:.2f} BBw={bb_width * 100:.2f}%",
            data_status="valid", volatility_status="normal", telemetry=telemetry,
        )
    except Exception as exc:
        return _blocked(symbol, timeframe, "error", f"Part7 analysis exception: {type(exc).__name__}", "error")


def aggregate_results(
    results: Mapping[str, Mapping[str, Any]],
    *,
    symbol: str,
    required_timeframes: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Aggregate explicit timeframe results into one entry gate."""
    required = tuple(required_timeframes or DEFAULT_TIMEFRAMES)
    per_timeframe = {str(tf): dict(results.get(tf) or _blocked(symbol, str(tf), "invalid", "Part7 timeframe result missing", "missing")) for tf in required}
    vetoes = [tf for tf, result in per_timeframe.items() if result.get("risk_veto") or result.get("status") == "veto"]
    blocked_data = [tf for tf, result in per_timeframe.items() if result.get("status") in {"invalid", "stale", "error", "symbol_mismatch"} or result.get("data_status") in {"invalid", "stale", "error", "missing"}]
    if vetoes:
        status, reason, entry_blocked = "veto", f"Part7 extreme volatility veto on {', '.join(vetoes)}", True
    elif blocked_data:
        status, reason, entry_blocked = "data_blocked", f"Part7 data blocked on {', '.join(blocked_data)}", True
    else:
        status, reason, entry_blocked = "ok", "Part7 timeframe data valid", False
    weights = {tf: float(i + 1) for i, tf in enumerate(required)}
    weighted = sum(float(per_timeframe[tf].get("signal", 0) or 0) * weights[tf] for tf in required)
    signal = 1 if weighted > 0 else -1 if weighted < 0 else 0
    volatility_statuses = sorted({str(r.get("volatility_status", "unknown")) for r in per_timeframe.values()})
    return {
        "signal": signal,
        "signal_identity": f"part7:{_symbol(symbol) or 'UNKNOWN'}:aggregate",
        "signal_name": "CALL" if signal > 0 else "PUT" if signal < 0 else "NEUTRAL",
        "symbol": _symbol(symbol) or "UNKNOWN",
        "timeframe": "aggregate",
        "status": status,
        "reason": reason,
        "thought": reason,
        "data_status": "blocked" if entry_blocked else "valid",
        "volatility_status": ",".join(volatility_statuses),
        "entry_blocked": entry_blocked,
        "risk_veto": bool(vetoes),
        "computation_backend": "pandas_cpu",
        "computation_engine": "pandas",
        "accelerator": "cpu",
        "timeframe_results": per_timeframe,
        "blocked_timeframes": blocked_data,
        "veto_timeframes": vetoes,
    }

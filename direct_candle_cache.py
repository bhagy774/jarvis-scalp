"""Direct native-interval candle snapshots for live Jarvis analysis.

This module deliberately does not resample, pad, or fabricate candles.  A live
snapshot contains exactly 500 completed candles and, when the venue returns it,
one separate currently-forming candle.  Consumers must use ``closed`` for
indicators; ``current`` is explicitly unconfirmed metadata only.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
import math
import time
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

import pandas as pd

LIVE_TIMEFRAMES: Tuple[str, ...] = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h")
INTERVAL_SECONDS: Mapping[str, int] = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900,
    "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400,
}
REQUIRED_CLOSED_CANDLES = 500
FETCH_CANDLES = REQUIRED_CLOSED_CANDLES + 1


class CandleDataError(ValueError):
    """A live candle snapshot cannot be trusted for decision-making."""


@dataclass(frozen=True)
class CandleFrame:
    symbol: str
    source: str
    timeframe: str
    closed: pd.DataFrame
    current: Optional[Dict[str, Any]]
    fetched_at: float

    @property
    def current_is_confirmed(self) -> bool:
        return False

    def sma(self, period: int) -> float:
        """Calculate a latest-window SMA from completed candles only.

        ``JARVIS_RUST_MATH=1`` opts this pure calculation into the Rust
        extension; the adapter provides an explicit equivalent Python fallback.
        The forming candle is intentionally never included.
        """
        from jarvis_rust_integration import calculate_sma

        return calculate_sma(self.closed["close"].tolist(), period)


@dataclass(frozen=True)
class CandleSnapshot:
    symbol: str
    frames: Mapping[str, CandleFrame]
    fetched_at: float

    @property
    def current_candles(self) -> Dict[str, Optional[Dict[str, Any]]]:
        return {tf: frame.current for tf, frame in self.frames.items()}

    def analysis_frames(self) -> Dict[str, pd.DataFrame]:
        """Only completed candles, suitable for Parts 1-12 and native engines."""
        return {tf: frame.closed.copy() for tf, frame in self.frames.items()}

    def context(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "source_by_timeframe": {tf: f.source for tf, f in self.frames.items()},
            "current_candles": self.current_candles,
            "current_is_confirmed": False,
            "fetched_at": self.fetched_at,
        }


class DirectCandleCache:
    """Bounded, symbol/source/timeframe keyed cache of native exchange candles."""

    def __init__(
        self,
        client: Any,
        *,
        clock: Callable[[], float] = time.time,
        ttl_seconds: float = 45.0,
        stale_intervals: float = 2.0,
    ) -> None:
        self.client = client
        self.clock = clock
        self.ttl_seconds = float(ttl_seconds)
        self.stale_intervals = float(stale_intervals)
        self._cache: Dict[Tuple[str, str, str], CandleFrame] = {}
        self._snapshots: Dict[str, CandleSnapshot] = {}
        self._lock = RLock()

    @staticmethod
    def _canonical_symbol(symbol: str) -> str:
        value = str(symbol or "").upper().replace("/", "").replace("-", "").replace("_", "")
        if not value:
            raise CandleDataError("empty symbol")
        return value

    @staticmethod
    def _row_value(row: Mapping[str, Any], name: str) -> Any:
        if name in row:
            return row[name]
        # Some native clients expose milliseconds under timestamp.
        if name == "time" and "timestamp" in row:
            return row["timestamp"]
        raise CandleDataError(f"missing candle field: {name}")

    def _fetch(self, symbol: str, timeframe: str) -> Tuple[Iterable[Mapping[str, Any]], str, str]:
        method = getattr(self.client, "get_historical_candles_with_metadata", None)
        if callable(method):
            result = method(symbol=symbol, resolution=timeframe, limit=FETCH_CANDLES)
            if not isinstance(result, Mapping):
                raise CandleDataError("candle metadata response is not a mapping")
            candles = result.get("candles")
            source = str(result.get("source") or "unknown").strip().lower()
            instrument = str(result.get("symbol") or result.get("instrument") or symbol)
        else:
            method = getattr(self.client, "get_historical_candles", None)
            if not callable(method):
                raise CandleDataError("client has no historical candle method")
            candles = method(symbol=symbol, resolution=timeframe, limit=FETCH_CANDLES)
            source = str(getattr(self.client, "last_candle_source", None) or "provided").strip().lower()
            instrument = symbol
        if not isinstance(candles, Iterable) or isinstance(candles, (str, bytes)):
            raise CandleDataError(f"{timeframe}: invalid candle response")
        return candles, source, instrument

    def _normalize(
        self,
        symbol: str,
        timeframe: str,
        candles: Iterable[Mapping[str, Any]],
        source: str,
        instrument: str,
        now: float,
    ) -> CandleFrame:
        if timeframe not in INTERVAL_SECONDS:
            raise CandleDataError(f"unsupported native timeframe: {timeframe}")
        if self._canonical_symbol(instrument) != self._canonical_symbol(symbol):
            raise CandleDataError(f"{timeframe}: instrument mismatch ({instrument!r} != {symbol!r})")
        source = source or "unknown"
        rows = list(candles)
        if len(rows) < FETCH_CANDLES:
            raise CandleDataError(f"{timeframe}: need {FETCH_CANDLES} rows, got {len(rows)}")
        interval = INTERVAL_SECONDS[timeframe]
        normalized = []
        seen = set()
        for row in rows:
            if not isinstance(row, Mapping):
                raise CandleDataError(f"{timeframe}: malformed candle row")
            raw_time = self._row_value(row, "time")
            try:
                ts = float(raw_time)
                # Accept ms timestamps, but keep all downstream times in seconds.
                if ts > 10_000_000_000:
                    ts /= 1000.0
                ts = int(ts)
                values = {field: float(self._row_value(row, field)) for field in ("open", "high", "low", "close", "volume")}
            except (TypeError, ValueError, OverflowError) as exc:
                raise CandleDataError(f"{timeframe}: non-numeric candle") from exc
            if ts <= 0 or any(not math.isfinite(v) for v in values.values()):
                raise CandleDataError(f"{timeframe}: invalid numeric candle")
            if ts in seen:
                raise CandleDataError(f"{timeframe}: duplicate timestamp {ts}")
            if ts > now + 2:
                raise CandleDataError(f"{timeframe}: future candle {ts}")
            if values["high"] < max(values["open"], values["close"]) or values["low"] > min(values["open"], values["close"]):
                raise CandleDataError(f"{timeframe}: OHLC bounds invalid")
            seen.add(ts)
            normalized.append({"time": ts, **values})
        normalized.sort(key=lambda row: row["time"])
        closed_rows = [row for row in normalized if row["time"] + interval <= now]
        forming_rows = [row for row in normalized if row["time"] <= now < row["time"] + interval]
        if len(forming_rows) != 1:
            raise CandleDataError(f"{timeframe}: expected one current forming candle, got {len(forming_rows)}")
        current = forming_rows[0]
        prior_closed = [row for row in closed_rows if row["time"] < current["time"]]
        if len(prior_closed) < REQUIRED_CLOSED_CANDLES:
            raise CandleDataError(f"{timeframe}: need {REQUIRED_CLOSED_CANDLES} closed candles, got {len(prior_closed)}")
        prior_closed = prior_closed[-REQUIRED_CLOSED_CANDLES:]
        expected = prior_closed[0]["time"]
        for row in prior_closed:
            if row["time"] != expected:
                raise CandleDataError(f"{timeframe}: missing/non-contiguous closed candle at {expected}")
            expected += interval
        if current["time"] != expected:
            raise CandleDataError(f"{timeframe}: current candle is not after the closed window")
        # A forming row must be fresh, not a stale exchange response.
        if now - current["time"] >= interval:
            raise CandleDataError(f"{timeframe}: current candle is stale")
        frame = pd.DataFrame(prior_closed, columns=["time", "open", "high", "low", "close", "volume"])
        frame.index = pd.to_datetime(frame.pop("time"), unit="s", utc=True)
        frame.index.name = "timestamp"
        return CandleFrame(symbol=symbol, source=source, timeframe=timeframe, closed=frame, current=current, fetched_at=now)

    def refresh(self, symbol: str, *, force: bool = False) -> CandleSnapshot:
        symbol = self._canonical_symbol(symbol)
        now = float(self.clock())
        with self._lock:
            cached = self._snapshots.get(symbol)
            if not force and cached and now - cached.fetched_at < self.ttl_seconds:
                return cached
            frames: Dict[str, CandleFrame] = {}
            for timeframe in LIVE_TIMEFRAMES:
                candles, source, instrument = self._fetch(symbol, timeframe)
                frame = self._normalize(symbol, timeframe, candles, source, instrument, now)
                # The key includes source so a source fallback cannot overwrite a
                # different-source frame for the same symbol/timeframe.
                self._cache[(symbol, frame.source, timeframe)] = frame
                frames[timeframe] = frame
            snapshot = CandleSnapshot(symbol=symbol, frames=frames, fetched_at=now)
            self._snapshots[symbol] = snapshot
            return snapshot

    def get_snapshot(self, symbol: str) -> Optional[CandleSnapshot]:
        with self._lock:
            return self._snapshots.get(self._canonical_symbol(symbol))

    def clear_symbol(self, symbol: str) -> None:
        symbol = self._canonical_symbol(symbol)
        with self._lock:
            self._snapshots.pop(symbol, None)
            for key in list(self._cache):
                if key[0] == symbol:
                    del self._cache[key]

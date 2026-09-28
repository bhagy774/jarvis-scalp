"""Direct native-interval candle snapshots for live Jarvis analysis.

This module deliberately does not resample, pad, or fabricate candles.  A live
snapshot contains exactly 500 completed candles and, when the venue returns it,
one separate currently-forming candle.  Consumers must use ``closed`` for
indicators; ``current`` is explicitly unconfirmed metadata only.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import BoundedSemaphore, RLock
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
    venue: str = "unknown"
    market_type: str = "unknown"
    instrument_id: str = ""

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
    venue: str = "unknown"
    market_type: str = "unknown"
    instrument_id: str = ""

    @property
    def identity(self) -> Tuple[str, str, str, str]:
        """Request identity; provider source remains explicit per timeframe."""
        return (self.venue, self.market_type, self.instrument_id, self.symbol)

    @property
    def current_candles(self) -> Dict[str, Optional[Dict[str, Any]]]:
        return {tf: frame.current for tf, frame in self.frames.items()}

    def analysis_frames(self) -> Dict[str, pd.DataFrame]:
        """Only completed candles, suitable for Parts 1-12 and native engines."""
        return {tf: frame.closed.copy() for tf, frame in self.frames.items()}

    def context(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "venue": self.venue,
            "market_type": self.market_type,
            "instrument_id": self.instrument_id,
            "identity": self.identity,
            "source_by_timeframe": {tf: f.source for tf, f in self.frames.items()},
            "current_candles": self.current_candles,
            "current_is_confirmed": False,
            "fetched_at": self.fetched_at,
        }


class DirectCandleCache:
    """Bounded, full-request-identity/native-timeframe candle cache.

    A snapshot request is isolated by (venue, market_type, instrument_id,
    canonical_symbol). ``source`` is still recorded for every timeframe because
    a multi-provider adapter can legitimately fall back between providers.
    Per-identity locks let analysis jobs validate different markets without
    sharing mutable snapshot state. A separate bounded semaphore protects a
    shared client from excessive simultaneous network calls.
    """

    def __init__(
        self,
        client: Any,
        *,
        clock: Callable[[], float] = time.time,
        ttl_seconds: float = 45.0,
        stale_intervals: float = 2.0,
        max_concurrent_fetches: int = 1,
        max_cached_identities: int = 64,
    ) -> None:
        self.client = client
        self.clock = clock
        self.ttl_seconds = float(ttl_seconds)
        self.stale_intervals = float(stale_intervals)
        self.max_cached_identities = max(1, min(256, int(max_cached_identities)))
        self._cache: Dict[Tuple[Tuple[str, str, str, str], str], CandleFrame] = {}
        self._snapshots: Dict[Tuple[str, str, str, str], CandleSnapshot] = {}
        self._identity_locks: Dict[Tuple[str, str, str, str], RLock] = {}
        self._lock = RLock()
        self._fetch_semaphore = BoundedSemaphore(max(1, min(4, int(max_concurrent_fetches))))

    def _identity_key(
        self, symbol: str, venue: str, market_type: str, instrument_id: Optional[str]
    ) -> Tuple[str, str, str, str]:
        canonical = self._canonical_symbol(symbol)
        venue_key = str(venue or "unknown").strip().lower()
        market_key = str(market_type or "unknown").strip().lower()
        instrument_key = str(instrument_id or canonical).strip()
        if not venue_key or not market_key or not instrument_key:
            raise CandleDataError("venue, market type, and instrument identity are required")
        return venue_key, market_key, instrument_key, canonical

    def _identity_lock(self, key: Tuple[str, str, str, str]) -> RLock:
        with self._lock:
            lock = self._identity_locks.get(key)
            if lock is not None:
                return lock
            if len(self._identity_locks) >= self.max_cached_identities:
                raise CandleDataError("bounded candle identity capacity reached")
            lock = RLock()
            self._identity_locks[key] = lock
            return lock

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
        # The client may hold mutable source metadata on itself; serialize the
        # complete request and metadata read unless explicitly configured for a
        # small bounded amount of concurrency.
        with self._fetch_semaphore:
            return self._fetch_unlocked(symbol, timeframe)

    def _fetch_unlocked(self, symbol: str, timeframe: str) -> Tuple[Iterable[Mapping[str, Any]], str, str]:
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
        venue: str = "unknown",
        market_type: str = "unknown",
        instrument_id: str = "",
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
        return CandleFrame(
            symbol=symbol, source=source, timeframe=timeframe, closed=frame,
            current=current, fetched_at=now, venue=venue,
            market_type=market_type, instrument_id=instrument_id or symbol,
        )

    def refresh(
        self,
        symbol: str,
        *,
        force: bool = False,
        venue: str = "unknown",
        market_type: str = "unknown",
        instrument_id: Optional[str] = None,
    ) -> CandleSnapshot:
        identity = self._identity_key(symbol, venue, market_type, instrument_id)
        venue_key, market_key, instrument_key, symbol_key = identity
        identity_lock = self._identity_lock(identity)
        with identity_lock:
            now = float(self.clock())
            with self._lock:
                cached = self._snapshots.get(identity)
            if not force and cached and now - cached.fetched_at < self.ttl_seconds:
                return cached
            frames: Dict[str, CandleFrame] = {}
            for timeframe in LIVE_TIMEFRAMES:
                candles, source, instrument = self._fetch(symbol_key, timeframe)
                # Validate freshness at the time each response arrives rather
                # than anchoring all eight sequential requests to cycle start.
                frame_now = float(self.clock())
                frame = self._normalize(
                    symbol_key, timeframe, candles, source, instrument, frame_now,
                    venue=venue_key, market_type=market_key,
                    instrument_id=instrument_key,
                )
                with self._lock:
                    # One current provider frame per request identity/timeframe;
                    # provider provenance remains attached to that frame.
                    self._cache[(identity, timeframe)] = frame
                frames[timeframe] = frame
            completed_at = float(self.clock())
            snapshot = CandleSnapshot(
                symbol=symbol_key, frames=frames, fetched_at=completed_at,
                venue=venue_key, market_type=market_key,
                instrument_id=instrument_key,
            )
            with self._lock:
                self._snapshots[identity] = snapshot
            return snapshot

    def get_snapshot(
        self,
        symbol: str,
        *,
        venue: str = "unknown",
        market_type: str = "unknown",
        instrument_id: Optional[str] = None,
    ) -> Optional[CandleSnapshot]:
        identity = self._identity_key(symbol, venue, market_type, instrument_id)
        with self._lock:
            return self._snapshots.get(identity)

    def clear_symbol(self, symbol: str) -> None:
        symbol = self._canonical_symbol(symbol)
        with self._lock:
            identities = [key for key in self._snapshots if key[3] == symbol]
            for identity in identities:
                self._snapshots.pop(identity, None)
                self._identity_locks.pop(identity, None)
                for key in list(self._cache):
                    if key[0] == identity:
                        del self._cache[key]

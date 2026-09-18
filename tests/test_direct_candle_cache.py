import copy
import math

import pytest

pd = pytest.importorskip("pandas")
from direct_candle_cache import (
    DirectCandleCache,
    CandleDataError,
    LIVE_TIMEFRAMES,
    FETCH_CANDLES,
)


class FakeClock:
    def __init__(self, value):
        self.value = float(value)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def make_rows(now, tf, *, symbol="ETHUSDT", mutate=None):
    seconds = {"1m": 60, "3m": 180, "5m": 300, "15m": 900,
               "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400}[tf]
    forming = int(now // seconds) * seconds
    start = forming - 500 * seconds
    rows = []
    for i in range(FETCH_CANDLES):
        ts = start + i * seconds
        price = 1000 + i
        rows.append({"time": ts, "open": price, "high": price + 2,
                     "low": price - 2, "close": price + 1, "volume": 1})
    return rows


class FakeClient:
    def __init__(self, clock, mutator=None):
        self.clock = clock
        self.mutator = mutator
        self.calls = []
        self.symbol = "ETHUSDT"

    def get_historical_candles_with_metadata(self, symbol, resolution, limit):
        self.calls.append((symbol, resolution, limit))
        rows = make_rows(self.clock(), resolution, symbol=symbol)
        if self.mutator:
            rows = self.mutator(rows, resolution)
        return {"candles": rows, "source": "binance", "symbol": symbol}


def test_all_native_intervals_have_500_closed_and_separate_forming():
    clock = FakeClock(1_700_000_000)
    client = FakeClient(clock)
    snapshot = DirectCandleCache(client, clock=clock).refresh("ETHUSDT")
    assert tuple(snapshot.frames) == LIVE_TIMEFRAMES
    assert len(client.calls) == 8
    assert all(call[2] == 501 for call in client.calls)
    for tf, frame in snapshot.frames.items():
        assert len(frame.closed) == 500
        assert frame.current is not None
        assert frame.current["time"] not in set(frame.closed.index.astype("int64") // 10**9)
        assert frame.current_is_confirmed is False
        assert frame.source == "binance"


def test_symbol_switch_isolated_and_no_btc_substitution():
    clock = FakeClock(1_700_000_000)
    client = FakeClient(clock)
    cache = DirectCandleCache(client, clock=clock)
    first = cache.refresh("ETHUSDT")
    second = cache.refresh("BTCUSDT")
    assert first.symbol == "ETHUSDT"
    assert second.symbol == "BTCUSDT"
    assert cache.get_snapshot("ETHUSDT").frames["1m"].closed.iloc[-1]["close"] == first.frames["1m"].closed.iloc[-1]["close"]
    assert {call[0] for call in client.calls} == {"ETHUSDT", "BTCUSDT"}


def test_repeated_refresh_uses_fresh_snapshot_then_refreshes_after_ttl():
    clock = FakeClock(1_700_000_000)
    client = FakeClient(clock)
    cache = DirectCandleCache(client, clock=clock, ttl_seconds=45)
    first = cache.refresh("ETHUSDT")
    assert cache.refresh("ETHUSDT") is first
    assert len(client.calls) == 8
    clock.advance(46)
    second = cache.refresh("ETHUSDT")
    assert second is not first
    assert len(client.calls) == 16


def test_forming_candle_never_enters_indicators():
    clock = FakeClock(1_700_000_000)
    snapshot = DirectCandleCache(FakeClient(clock), clock=clock).refresh("ETHUSDT")
    closed = snapshot.analysis_frames()["1m"]
    assert len(closed) == 500
    assert closed.index[-1].timestamp() + 60 <= clock.value
    assert snapshot.frames["1m"].current["close"] != closed["close"].iloc[-1]


@pytest.mark.parametrize("mutator", [
    lambda rows, tf: rows[:-1],
    lambda rows, tf: rows[:-2] + [dict(rows[-1], time=rows[-2]["time"])],
    lambda rows, tf: rows[:-1] + [dict(rows[-1], time=rows[-1]["time"] + 10_000)],
    lambda rows, tf: rows[:-2] + [dict(rows[-1], time=rows[-2]["time"] + 2 * {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400}[tf])],
])
def test_bad_missing_duplicate_future_or_gap_fails_closed(mutator):
    clock = FakeClock(1_700_000_000)
    with pytest.raises(CandleDataError):
        DirectCandleCache(FakeClient(clock, mutator), clock=clock).refresh("ETHUSDT")


def test_instrument_mismatch_fails_closed():
    clock = FakeClock(1_700_000_000)
    class Mismatched(FakeClient):
        def get_historical_candles_with_metadata(self, symbol, resolution, limit):
            result = super().get_historical_candles_with_metadata(symbol, resolution, limit)
            result["symbol"] = "BTCUSDT"
            return result
    with pytest.raises(CandleDataError):
        DirectCandleCache(Mismatched(clock), clock=clock).refresh("ETHUSDT")


def test_unsupported_and_stale_data_fail_closed():
    clock = FakeClock(1_700_000_000)
    cache = DirectCandleCache(FakeClient(clock), clock=clock)
    with pytest.raises(CandleDataError):
        cache._normalize("ETHUSDT", "7m", [], "binance", "ETHUSDT", clock.value)

    def stale(rows, tf):
        seconds = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400}[tf]
        return [dict(row, time=row["time"] - 2 * seconds) for row in rows]
    with pytest.raises(CandleDataError):
        DirectCandleCache(FakeClient(clock, stale), clock=clock).refresh("ETHUSDT")


def test_no_resampling_is_used():
    clock = FakeClock(1_700_000_000)
    client = FakeClient(clock)
    snapshot = DirectCandleCache(client, clock=clock).refresh("ETHUSDT")
    assert all(len(frame.closed) == 500 for frame in snapshot.frames.values())
    assert [call[1] for call in client.calls] == list(LIVE_TIMEFRAMES)


def test_jarvis_consumer_wiring_uses_shared_direct_frames(monkeypatch):
    import sys
    import types
    # jarvis_FIXED only needs the module at import time for this offline
    # consumer-wiring check; no websocket is started.
    monkeypatch.setitem(sys.modules, "websockets", types.ModuleType("websockets"))
    jarvis = pytest.importorskip("jarvis_FIXED")
    clock = FakeClock(1_700_000_000)
    client = FakeClient(clock)
    engine = jarvis.JarvisElite.__new__(jarvis.JarvisElite)
    engine.is_backtest_mode = False
    engine.active_symbol = "ETHUSDT"
    engine.direct_candle_cache = DirectCandleCache(client, clock=clock)
    engine._active_candle_snapshot = engine.direct_candle_cache.refresh("ETHUSDT")
    frames = engine._fetch_mtf_from_api("ETHUSDT")
    assert list(frames) == list(LIVE_TIMEFRAMES)
    assert all(len(frame) == 500 for frame in frames.values())
    assert all(frame.index[-1].timestamp() + {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400}[tf] <= clock.value for tf, frame in frames.items())

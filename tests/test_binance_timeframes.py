from datetime import datetime, timezone
import pytest

from binance_timeframes import (
    BINANCE_SPOT_TIMEFRAMES, TIMEFRAME_HISTORY_CANDLES,
    candle_open_time, history_limit, next_candle_open,
    validate_closed_candle_timestamps, synchronize_native_frames_to_1m_close,
)


def test_full_provider_catalogue_and_distinct_minute_month_tokens():
    assert len(BINANCE_SPOT_TIMEFRAMES) == 16
    assert "1m" in BINANCE_SPOT_TIMEFRAMES and "1M" in BINANCE_SPOT_TIMEFRAMES
    assert history_limit("1m") == TIMEFRAME_HISTORY_CANDLES["1m"]
    assert history_limit("1M") == TIMEFRAME_HISTORY_CANDLES["1M"]
    assert history_limit("1m") != history_limit("1M")


def test_calendar_boundary_functions_for_week_and_month():
    stamp = datetime(2026, 10, 1, 14, tzinfo=timezone.utc).timestamp()
    month = candle_open_time("1M", stamp)
    week = candle_open_time("1w", stamp)
    assert datetime.fromtimestamp(month, timezone.utc) == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert datetime.fromtimestamp(week, timezone.utc).weekday() == 0
    assert next_candle_open("1M", month) == datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp()


def test_backtest_rejects_unclosed_native_higher_timeframe_bar():
    open_8 = datetime(2026, 10, 1, 8, tzinfo=timezone.utc).timestamp()
    decision_10 = datetime(2026, 10, 1, 10, tzinfo=timezone.utc).timestamp()
    open_4 = datetime(2026, 10, 1, 4, tzinfo=timezone.utc).timestamp()
    with pytest.raises(ValueError, match="not closed"):
        validate_closed_candle_timestamps("4h", [open_8], decision_10)
    validate_closed_candle_timestamps("4h", [open_4], decision_10)


def test_synchronization_excludes_fast_bars_after_latest_completed_1m_close():
    import pandas as pd

    one_minute = pd.DataFrame(
        {"close": range(30)},
        index=pd.date_range("2026-10-01T10:30:00Z", periods=30, freq="min"),
    )
    seconds = pd.DataFrame(
        {"close": range(151)},
        index=pd.date_range("2026-10-01T10:58:00Z", periods=151, freq="s"),
    )

    result = synchronize_native_frames_to_1m_close(
        {"1m": one_minute, "1s": seconds}, as_of=datetime(2026, 10, 1, 11, 0, 10, tzinfo=timezone.utc).timestamp()
    )

    cutoff = datetime(2026, 10, 1, 11, 0, tzinfo=timezone.utc)
    assert result["1m"].index[-1] == one_minute.index[-1]
    assert result["1s"].index[-1] < cutoff
    assert len(result["1s"]) == 120


def test_synchronization_rejects_forming_1m_reference_and_handles_calendar_frames():
    import pandas as pd

    minute_open = pd.date_range("2026-10-01T10:30:00Z", periods=30, freq="min")
    forming_reference = pd.DataFrame({"close": range(30)}, index=minute_open + pd.Timedelta(minutes=1))
    with pytest.raises(ValueError, match="not closed"):
        synchronize_native_frames_to_1m_close(
            {"1m": forming_reference},
            as_of=datetime(2026, 10, 1, 11, 0, 30, tzinfo=timezone.utc).timestamp(),
        )

    one_minute = pd.DataFrame({"close": range(30)}, index=minute_open)
    weekly = pd.DataFrame({"close": range(31)}, index=pd.date_range("2026-03-02T00:00:00Z", periods=31, freq="W-MON"))
    monthly = pd.DataFrame({"close": range(31)}, index=pd.date_range("2024-04-01T00:00:00Z", periods=31, freq="MS"))
    result = synchronize_native_frames_to_1m_close(
        {"1m": one_minute, "1w": weekly, "1M": monthly},
        as_of=datetime(2026, 10, 1, 11, 0, 10, tzinfo=timezone.utc).timestamp(),
    )
    assert result["1w"].index[-1] == pd.Timestamp("2026-09-21T00:00:00Z")
    assert len(result["1w"]) == 30
    assert result["1M"].index[-1] == pd.Timestamp("2026-09-01T00:00:00Z")
    assert len(result["1M"]) == 30


def test_synchronization_rejects_unzoned_or_gapped_frames():
    import pandas as pd
    with pytest.raises(ValueError, match="timezone-aware"):
        synchronize_native_frames_to_1m_close({
            "1m": pd.DataFrame({"close": range(30)}, index=pd.date_range("2026-10-01 10:00", periods=30, freq="min"))
        })


def test_timestamp_validation_rejects_duplicate_unaligned_and_gapped_bars():
    start = datetime(2026, 10, 1, 8, tzinfo=timezone.utc).timestamp()
    decision = start + 7200
    with pytest.raises(ValueError, match="increasing"):
        validate_closed_candle_timestamps("1h", [start, start], decision)
    with pytest.raises(ValueError, match="aligned"):
        validate_closed_candle_timestamps("1h", [start + 60], decision)
    with pytest.raises(ValueError, match="gap"):
        validate_closed_candle_timestamps("1h", [start, start + 7200], decision)

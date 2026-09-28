from datetime import datetime, timezone, timedelta

from options_chain import build_provider_chain, combine_provider_chains
from options_snapshot_store import append_snapshot, replay_snapshot

AS_OF = datetime(2026, 9, 28, 10, tzinfo=timezone.utc)


def chain():
    row = {"symbol": "ETH-261030-4000-C", "underlying_asset_symbol": "ETH",
           "contract_type": "call_options", "strike_price": 4000,
           "expiry": "2026-10-30", "timestamp": AS_OF.isoformat(),
           "oi": 2, "volume": 1, "implied_volatility": 0.5,
           "greeks": {"delta": 0.3}}
    provider = build_provider_chain("ETH", "Delta", [[row]],
        {"complete": True, "truncated": False, "marker_seen": True}, retrieved_at=AS_OF)
    return combine_provider_chains("ETH", {"Delta": provider})


def test_recorded_snapshot_replays_only_at_or_after_its_point_in_time(tmp_path):
    path = tmp_path / "options.jsonl"
    assert append_snapshot(str(path), chain(), captured_at=AS_OF)
    decision = AS_OF + timedelta(minutes=5)
    out = replay_snapshot(str(path), "ETHUSDT", decision, venue="Delta")
    assert out["available"]
    assert out["source"] == "recorded_options_snapshots"
    assert out["not_ohlc_derived"]
    assert out["snapshot"]["providers"]["Delta"]["contracts"][0]["delta"] == 0.3
    future = replay_snapshot(str(path), "ETH", AS_OF - timedelta(seconds=1), venue="Delta")
    assert not future["available"]
    assert "future_or_invalid_capture_time" in future["rejected_reasons"] or "no_admissible_historical_options_snapshot" == future["reason"]


def test_replay_rejects_wrong_asset_stale_chain_and_absent_history(tmp_path):
    path = tmp_path / "options.jsonl"
    assert append_snapshot(str(path), chain(), captured_at=AS_OF)
    assert replay_snapshot(str(path), "BTC", AS_OF + timedelta(minutes=1))["available"] is False
    assert replay_snapshot(str(path), "ETH", AS_OF + timedelta(minutes=11), venue="Delta")["available"] is False
    missing = replay_snapshot(str(tmp_path / "missing.jsonl"), "ETH", AS_OF)
    assert not missing["available"] and missing["source"] == "none"
    assert missing["not_ohlc_derived"]


def test_future_capture_cannot_be_used_for_earlier_decision(tmp_path):
    path = tmp_path / "options.jsonl"
    assert append_snapshot(str(path), chain(), captured_at=AS_OF + timedelta(seconds=1))
    out = replay_snapshot(str(path), "ETH", AS_OF, venue="Delta")
    assert not out["available"]
    assert "future_or_invalid_capture_time" in out["rejected_reasons"]

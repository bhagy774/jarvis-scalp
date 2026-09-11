"""Offline tests: Ollama-only AI defaults, watchdog, recovery, state persistence."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for var in ("JARVIS_ENABLE_GEMINI", "JARVIS_ENABLE_EXTERNAL_AI", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    yield


# ── Ollama-only defaults ────────────────────────────────────────────────

def test_gemini_disabled_without_env():
    from trading_config import gemini_enabled
    assert gemini_enabled() is False


def test_gemini_requires_both_flag_and_key(monkeypatch):
    from trading_config import gemini_enabled
    monkeypatch.setenv("JARVIS_ENABLE_GEMINI", "1")
    assert gemini_enabled() is False  # no key
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert gemini_enabled() is True


def test_kie_inert_without_env():
    from kie_gpt6_client import KieGPT6Client
    client = KieGPT6Client(api_key="fake-key")
    text, data = client.ask("hello")  # must NOT hit network
    assert data["disabled"] is True
    assert "disabled" in text.lower()


def test_kie_stream_inert():
    from kie_gpt6_client import KieGPT6Client
    client = KieGPT6Client(api_key="fake-key")
    assert list(client.ask("hello", stream=True)) == []


def test_kie_enabled_path_builds_request(monkeypatch):
    from kie_gpt6_client import KieGPT6Client
    monkeypatch.setenv("JARVIS_ENABLE_EXTERNAL_AI", "1")
    called = {}

    class FakeResp:
        status_code = 200
        text = ""
        def json(self):
            return {"output": [{"content": "ok"}]}

    import kie_gpt6_client
    def fake_post(*a, **k):
        called["hit"] = True
        return FakeResp()
    monkeypatch.setattr(kie_gpt6_client.requests, "post", fake_post)
    client = KieGPT6Client(api_key="fake-key")
    text, _ = client.ask("hi")
    assert called.get("hit") is True
    assert text == "ok"


# ── Watchdog ─────────────────────────────────────────────────────────────

def test_health_returns_dict():
    import jarvis_watchdog as wd
    health = wd.get_health()
    assert isinstance(health, dict)
    for key in ("watchdog_running", "services", "alerts", "reconcile"):
        assert key in health


def test_heartbeat_alive_and_stale():
    import jarvis_watchdog as wd
    wd.beat("brain_loop")
    health = wd.get_health()
    assert health["services"]["brain_loop"]["alive"] is True
    wd._heartbeats["brain_loop"] -= wd.HEARTBEAT_STALE_SECONDS + 10
    assert wd.get_health()["services"]["brain_loop"]["alive"] is False


def test_watchdog_disabled_by_env(monkeypatch):
    import jarvis_watchdog as wd
    monkeypatch.setenv("JARVIS_WATCHDOG", "0")
    assert wd.start_watchdog(exchange_client=None) is False


# ── Recovery reconcile ───────────────────────────────────────────────────

class _FailingExchange:
    def get_open_positions(self):
        raise ConnectionError("exchange down")


class _FakeExchange:
    def get_open_positions(self):
        return [{"symbol": "BTCUSDT"}]


def test_reconcile_handles_api_failure(tmp_path):
    import jarvis_watchdog as wd
    wd.save_state([{"id": "1", "symbol": "BTCUSDT"}], path=str(tmp_path / "s.json"))
    report = wd.reconcile_state(_FailingExchange(), state_path=str(tmp_path / "s.json"))
    assert report["exchange_ok"] is False
    assert "exchange down" in report["error"]


def test_reconcile_detects_mismatch(tmp_path):
    import jarvis_watchdog as wd
    wd.save_state([], path=str(tmp_path / "s.json"))
    report = wd.reconcile_state(_FakeExchange(), state_path=str(tmp_path / "s.json"))
    assert report["exchange_ok"] is True
    assert report["mismatches"]  # exchange has position, local doesn't


def test_reconcile_no_client(tmp_path):
    import jarvis_watchdog as wd
    report = wd.reconcile_state(None, state_path=str(tmp_path / "missing.json"))
    assert report["local_trades"] == 0
    assert report["error"]


# ── State persistence round-trip ─────────────────────────────────────────

def test_state_roundtrip(tmp_path):
    import jarvis_watchdog as wd
    path = str(tmp_path / "jarvis_state.json")
    trades = [{"id": "123", "direction": "CALL", "entry_price": 67000.0}]
    assert wd.save_state(trades, path=path) is True
    loaded = wd.load_state(path)
    assert loaded["open_trades"] == trades
    assert json.loads(open(path).read())["open_trades"] == trades


def test_state_load_missing_and_corrupt(tmp_path):
    import jarvis_watchdog as wd
    assert wd.load_state(str(tmp_path / "nope.json"))["open_trades"] == []
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert wd.load_state(str(bad))["open_trades"] == []

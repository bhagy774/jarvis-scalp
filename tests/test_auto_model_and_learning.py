"""Offline tests: Ollama auto model resolution + learning loop. All network mocked."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ollama_integration as oi


@pytest.fixture(autouse=True)
def clean_state(monkeypatch, tmp_path):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("JARVIS_LEARNING", raising=False)
    monkeypatch.chdir(tmp_path)
    # reset resolver cache between tests
    oi._resolved_model_cache = None
    oi._model_resolution_done = False
    oi._no_model_logged = False
    import jarvis_learning as jl
    jl._cache = None
    jl._cache_path = None
    yield


def _tags_response(names):
    class R:
        status_code = 200
        def json(self):
            return {"models": [{"name": n} for n in names]}
    return R()


# ── Auto model resolution ─────────────────────────────────────────────

def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "my-custom:7b")
    monkeypatch.setattr(oi.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network")))
    assert oi.resolve_ollama_model() == "my-custom:7b"


def test_preference_order(monkeypatch):
    monkeypatch.setattr(oi.requests, "get",
                        lambda *a, **k: _tags_response(["gemma2:9b", "llama3:8b", "mistral:7b"]))
    assert oi.resolve_ollama_model() == "mistral:7b"  # mistral preferred over llama3/gemma2


def test_falls_back_to_any_installed(monkeypatch):
    monkeypatch.setattr(oi.requests, "get",
                        lambda *a, **k: _tags_response(["obscure-model:1b"]))
    assert oi.resolve_ollama_model() == "obscure-model:1b"


def test_unreachable_returns_none_and_caches(monkeypatch):
    calls = {"n": 0}
    def boom(*a, **k):
        calls["n"] += 1
        raise ConnectionError("down")
    monkeypatch.setattr(oi.requests, "get", boom)
    assert oi.resolve_ollama_model() is None
    assert oi.resolve_ollama_model() is None
    assert calls["n"] == 1  # cached in-process


def test_empty_tags_returns_none(monkeypatch):
    monkeypatch.setattr(oi.requests, "get", lambda *a, **k: _tags_response([]))
    assert oi.resolve_ollama_model() is None


def test_no_model_logs_once(monkeypatch, caplog):
    import logging
    monkeypatch.setattr(oi.requests, "get", lambda *a, **k: _tags_response([]))
    with caplog.at_level(logging.WARNING):
        oi.resolve_ollama_model()
        oi.resolve_ollama_model(force_refresh=True)
    msgs = [r.message for r in caplog.records if "math-fallback" in r.message]
    assert len(msgs) == 1


def test_call_ollama_local_auto_resolves(monkeypatch):
    import jarvis_FIXED as jf
    monkeypatch.setattr(oi.requests, "get",
                        lambda *a, **k: _tags_response(["phi3.5:3.8b", "qwen2.5:7b"]))
    captured = {}
    class R:
        status_code = 200
        def json(self):
            return {"response": "ok"}
    def fake_post(url, json=None, timeout=None):
        captured["model"] = json["model"]
        return R()
    monkeypatch.setattr("requests.post", fake_post)
    content, err = jf._call_ollama_local("hi", model=None)
    assert err is None and content == "ok"
    assert captured["model"] == "phi3.5:3.8b"


def test_call_ollama_local_no_model_graceful(monkeypatch):
    import jarvis_FIXED as jf
    monkeypatch.setattr(oi.requests, "get", lambda *a, **k: (_ for _ in ()).throw(ConnectionError()))
    content, err = jf._call_ollama_local("hi", model=None)
    assert content is None and err


def test_brains_use_auto_resolution():
    import jarvis_FIXED as jf
    assert jf.DeepSeekV3Brain().model_name is None
    assert jf.DeepSeekR1ReasoningBrain().model_name is None


def test_preload_skips_missing_models(monkeypatch):
    oi.OLLAMA_ENABLED = True
    monkeypatch.setenv("MODEL_ANALYST", "deepseek-r1:14b")
    monkeypatch.setenv("MODEL_VALIDATOR", "qwen2.5:14b")
    monkeypatch.delenv("MODEL_RISK", raising=False)
    monkeypatch.setattr(oi.requests, "get",
                        lambda *a, **k: _tags_response(["qwen2.5:14b"]))
    loaded = []
    class R:
        status_code = 200
        def json(self):
            return {}
    monkeypatch.setattr(oi.requests, "post",
                        lambda url, json=None, timeout=None: loaded.append(json["model"]) or R())
    oi.preload_committee_models()
    assert loaded == ["qwen2.5:14b"]
    oi.OLLAMA_ENABLED = False


# ── Learning loop ─────────────────────────────────────────────────────

import jarvis_learning as jl


def _trade(result="WIN", direction="CALL"):
    return {"direction": direction, "entry_price": 100.0, "exit_price": 101.0,
            "result": result, "pnl_dollar": 5.0, "close_reason": "test",
            "confidence": 80}


def test_record_trade_and_stats(tmp_path):
    p = str(tmp_path / "learn.json")
    assert jl.record_trade(_trade("WIN"), engine_signals={"part1": 1, "part2": -1}, path=p)
    data = json.load(open(p))
    assert len(data["trades"]) == 1
    t = data["trades"][0]
    assert t["symbol"] == "BTC/USDT" and t["pnl"] == 5.0 and "timestamp" in t
    # only agreeing engine credited
    assert data["engines"]["part1"]["wins"] == 1
    assert "part2" not in data["engines"]


def test_record_trade_without_engine_signals(tmp_path):
    p = str(tmp_path / "learn.json")
    assert jl.record_trade(_trade("LOSS"), path=p)
    data = json.load(open(p))
    assert data["trades"][0]["result"] == "LOSS"
    assert "engine_signals" not in data["trades"][0]


def test_weight_neutral_below_min_trades(tmp_path):
    p = str(tmp_path / "learn.json")
    for _ in range(5):
        jl.record_trade(_trade("WIN"), engine_signals={"e": 1}, path=p)
    assert jl.get_engine_weight("e", path=p) == 1.0


def test_weight_scaling_and_bounds(tmp_path):
    p = str(tmp_path / "learn.json")
    # 10/10 wins -> 1.5
    for _ in range(10):
        jl.record_trade(_trade("WIN"), engine_signals={"hot": 1}, path=p)
    assert jl.get_engine_weight("hot", path=p) == 1.5
    # 0/10 wins -> 0.5
    for _ in range(10):
        jl.record_trade(_trade("LOSS"), engine_signals={"cold": 1}, path=p)
    assert jl.get_engine_weight("cold", path=p) == 0.5
    # 5/10 -> 1.0
    for i in range(10):
        jl.record_trade(_trade("WIN" if i % 2 == 0 else "LOSS"),
                        engine_signals={"mid": 1}, path=p)
    assert jl.get_engine_weight("mid", path=p) == pytest.approx(1.0)


def test_learning_disabled_env(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_LEARNING", "0")
    p = str(tmp_path / "learn.json")
    assert jl.record_trade(_trade("WIN"), engine_signals={"e": 1}, path=p) is False
    assert not os.path.exists(p)
    assert jl.get_engine_weight("e", path=p) == 1.0


def test_corrupt_file_graceful(tmp_path):
    p = tmp_path / "learn.json"
    p.write_text("{not valid json!!")
    jl._cache = None; jl._cache_path = None
    assert jl.get_engine_weight("e", path=str(p)) == 1.0
    # can still record after corruption
    assert jl.record_trade(_trade("WIN"), path=str(p)) is True
    assert len(json.load(open(p))["trades"]) == 1


def test_atomic_write_leaves_no_tmp(tmp_path):
    p = str(tmp_path / "learn.json")
    jl.record_trade(_trade("WIN"), path=p)
    leftovers = [f for f in os.listdir(tmp_path) if f.startswith(".jarvis_learning_")]
    assert leftovers == []


def test_breakeven_not_win_or_loss(tmp_path):
    p = str(tmp_path / "learn.json")
    for _ in range(10):
        jl.record_trade(_trade("BREAKEVEN"), engine_signals={"e": 1}, path=p)
    stats = jl.get_engine_stats("e", path=p)
    assert stats["trades"] == 10 and stats["wins"] == 0 and stats["losses"] == 0
    assert jl.get_engine_weight("e", path=p) == 1.0  # 0 decided -> win_rate 0 -> but trades>=10

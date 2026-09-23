import json
import math
from datetime import datetime, timezone, timedelta
import pytest

from jarvis_ollama_context import (
    _clean,
    _parts,
    build_snapshot,
    snapshot_usable,
    decision_prompt,
    validate_decision
)

def test_clean():
    # secrets redaction
    assert _clean("my_api_key_is_secret") == "<redacted>"
    assert _clean({"api_key": "123"}) == {}

    # max text length
    long_str = "a" * 400
    assert len(_clean(long_str)) == 360

    # nan / inf
    assert _clean(float('nan')) is None
    assert _clean(float('inf')) is None
    assert _clean(float('-inf')) is None

    # scalars
    assert _clean(123) == 123
    assert _clean(123.45) == 123.45
    assert _clean(True) is True
    assert _clean(None) is None

    # depth limit
    nested = {"a": {"b": {"c": {"d": "e"}}}}
    res = _clean(nested)
    assert res["a"]["b"]["c"]["d"] == "<truncated>"

    # lists
    assert _clean([1, 2, 3]) == [1, 2, 3]
    long_list = list(range(40))
    res = _clean(long_list)
    assert len(res) == 32

def test_parts():
    # not dict
    assert _parts([]) == {"missing": True}

    # dict limiting
    parts = {f"part{i}": i for i in range(20)}
    res = _parts(parts)
    assert len(res) == 12
    assert "part0" in res

def test_build_snapshot():
    now_dt = datetime.now(timezone.utc)
    timestamp = now_dt.isoformat()

    snapshot = build_snapshot(
        symbol="BTC",
        timestamp=timestamp,
        current_price=50000.0,
        market_context={"symbol": "BTC", "volume": 100},
        part_results={"p1": 1},
        fusion={"f1": 2},
        confidence={"score": 90},
        mtf={"m": 1},
        options={"o": 1},
        risk={"r": 1},
        position_state={"pos": 1},
        order_state={"ord": 1},
        runtime={"rt": 1},
        safety_gates=["gate1"]
    )

    assert snapshot["schema"] == "jarvis.ollama.snapshot.v1"
    assert snapshot["symbol"] == "BTC"
    assert snapshot["freshness"]["symbol_match"] is True
    assert snapshot["freshness"]["stale"] is False
    assert snapshot["market"]["price"] == 50000.0
    assert snapshot["safety_gates"] == ["gate1"]

    # Test mismatch symbol
    snapshot_mismatch = build_snapshot(
        symbol="ETH",
        timestamp=timestamp,
        current_price=50000.0,
        market_context={"symbol": "BTC", "volume": 100},
        part_results={}
    )
    assert snapshot_mismatch["freshness"]["symbol_match"] is False

    # Test stale snapshot
    stale_dt = now_dt - timedelta(minutes=6)
    snapshot_stale = build_snapshot(
        symbol="BTC",
        timestamp=stale_dt.isoformat(),
        current_price=50000.0,
        market_context={"symbol": "BTC"},
        part_results={}
    )
    assert snapshot_stale["freshness"]["stale"] is True

    # Test missing values fallback
    snapshot_missing = build_snapshot(
        symbol="BTC",
        timestamp=None,
        current_price=50000.0,
        market_context=None,
        part_results=None
    )
    assert snapshot_missing["freshness"]["market_data"] == "missing"
    assert snapshot_missing["fusion"] == {"missing": True}
    assert snapshot_missing["parts_1_to_12"] == {"missing": True}

def test_snapshot_usable():
    snapshot = build_snapshot(
        symbol="BTC",
        timestamp=datetime.now(timezone.utc).isoformat(),
        current_price=50000.0,
        market_context={"symbol": "BTC"},
        part_results={}
    )
    usable, reason = snapshot_usable(snapshot)
    assert usable is True
    assert reason == "ok"

    snapshot_stale = build_snapshot(
        symbol="BTC",
        timestamp=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        current_price=50000.0,
        market_context={"symbol": "BTC"},
        part_results={}
    )
    usable, reason = snapshot_usable(snapshot_stale)
    assert usable is False
    assert reason == "snapshot stale"

    snapshot_mismatch = build_snapshot(
        symbol="ETH",
        timestamp=datetime.now(timezone.utc).isoformat(),
        current_price=50000.0,
        market_context={"symbol": "BTC"},
        part_results={}
    )
    usable, reason = snapshot_usable(snapshot_mismatch)
    assert usable is False
    assert reason == "snapshot symbol mismatch"

    snapshot_missing_market = build_snapshot(
        symbol="BTC",
        timestamp=datetime.now(timezone.utc).isoformat(),
        current_price=50000.0,
        market_context=None,
        part_results={}
    )
    usable, reason = snapshot_usable(snapshot_missing_market)
    assert usable is False
    assert reason == "market data missing"

    usable, reason = snapshot_usable(None)
    assert usable is False
    assert reason == "snapshot missing"

def test_decision_prompt():
    prompt = decision_prompt({"a": 1})
    assert "Analyze this bounded Jarvis snapshot." in prompt
    assert "SNAPSHOT:" in prompt

def test_validate_decision():
    valid_json = {
        "decision": "BUY",
        "confidence": 85,
        "rationale": "Looks good.",
        "plan": {"entry": 100, "stop_loss": 90, "take_profit": 120},
        "risks": ["high volatility"],
        "missing_data": []
    }

    result, err = validate_decision(json.dumps(valid_json))
    assert err is None
    assert result["decision"] == "BUY"
    assert result["confidence"] == 85
    assert result["rationale"] == "Looks good."
    assert result["plan"]["entry"] == 100
    assert result["risks"] == ["high volatility"]

    # Test as dict directly
    result, err = validate_decision(valid_json)
    assert err is None
    assert result["decision"] == "BUY"

    # Invalid decision
    invalid_decision = dict(valid_json, decision="HOLD")
    result, err = validate_decision(invalid_decision)
    assert err == "invalid decision"

    # Invalid confidence
    invalid_conf = dict(valid_json, confidence=101)
    result, err = validate_decision(invalid_conf)
    assert err == "invalid confidence"

    invalid_conf_low = dict(valid_json, confidence=-1)
    result, err = validate_decision(invalid_conf_low)
    assert err == "invalid confidence"

    # Invalid rationale
    invalid_rationale = dict(valid_json, rationale="   ")
    result, err = validate_decision(invalid_rationale)
    assert err == "invalid rationale"

    long_rationale = dict(valid_json, rationale="a" * 400)
    result, err = validate_decision(long_rationale)
    assert err == "invalid rationale"

    # Invalid plan
    invalid_plan = dict(valid_json, plan="not a dict")
    result, err = validate_decision(invalid_plan)
    assert err == "invalid plan"

    # Not an object
    result, err = validate_decision("[]")
    assert err == "response is not an object"

    # invalid JSON
    result, err = validate_decision("{ bad json }")
    assert "invalid response:" in err

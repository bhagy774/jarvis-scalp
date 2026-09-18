"""Bounded, secret-free context and validated response contract for Ollama."""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

_SECRET = re.compile(r"(api[_-]?key|secret|token|authorization|password|cookie|private[_-]?key)", re.I)
_MAX_TEXT = 360


def _clean(value: Any, depth: int = 0) -> Any:
    if depth > 3:
        return "<truncated>"
    if _SECRET.search(str(value)) if isinstance(value, str) else False:
        return "<redacted>"
    if value is None or isinstance(value, (bool, int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return value
    if isinstance(value, str):
        return value[:_MAX_TEXT]
    if isinstance(value, dict):
        return {str(k): _clean(v, depth + 1) for k, v in list(value.items())
                if not _SECRET.search(str(k))}
    if isinstance(value, (list, tuple)):
        return [_clean(v, depth + 1) for v in list(value)[:32]]
    return str(value)[:_MAX_TEXT]


def _parts(parts: Any) -> Dict[str, Any]:
    if not isinstance(parts, dict):
        return {"missing": True}
    return {str(name): _clean(result) for name, result in list(parts.items())[:12]}


def build_snapshot(*, symbol: str, timestamp: Optional[str], current_price: Any,
                   market_context: Dict[str, Any], part_results: Dict[str, Any],
                   fusion: Any = None, confidence: Any = None,
                   mtf: Any = None, options: Any = None, risk: Any = None,
                   position_state: Any = None, order_state: Any = None,
                   runtime: Any = None, safety_gates: Iterable[str] = ()) -> Dict[str, Any]:
    """Build one same-symbol snapshot; missing values are explicit markers."""
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    selected_symbol = str(symbol or "UNKNOWN").upper()
    market_context = market_context or {}
    reported_symbol = market_context.get("symbol") if isinstance(market_context, dict) else None
    symbol_match = not reported_symbol or str(reported_symbol).upper() == selected_symbol
    stale = False
    freshness_limit = 300.0
    try:
        source_time = datetime.fromisoformat(str(timestamp or now).replace("Z", "+00:00"))
        if source_time.tzinfo is None:
            source_time = source_time.replace(tzinfo=timezone.utc)
        stale = max(0.0, (now_dt - source_time.astimezone(timezone.utc)).total_seconds()) > freshness_limit
    except (TypeError, ValueError, OverflowError):
        stale = True
    snapshot = {
        "schema": "jarvis.ollama.snapshot.v1",
        "symbol": selected_symbol,
        "timestamp": timestamp or now,
        "snapshot_created_at": now,
        "freshness": {"market_data": "provided" if market_context else "missing",
                      "symbol_match": symbol_match, "stale": stale,
                      "max_age_seconds": freshness_limit},
        "market": {"price": _clean(current_price), "context": _clean(market_context or {})},
        "parts_1_to_12": _parts(part_results),
        "fusion": _clean(fusion) if fusion is not None else {"missing": True},
        "confidence": _clean(confidence) if confidence is not None else {"missing": True},
        "mtf": _clean(mtf) if mtf is not None else {"missing": True},
        "options": _clean(options) if options is not None else {"missing": True},
        "risk": _clean(risk) if risk is not None else {"missing": True},
        "position_state": _clean(position_state) if position_state is not None else {"missing": True},
        "order_state": _clean(order_state) if order_state is not None else {"missing": True},
        "runtime": _clean(runtime) if runtime is not None else {"missing": True},
        "safety_gates": list(_clean(list(safety_gates)) or []),
    }
    return snapshot


def snapshot_usable(snapshot: Dict[str, Any]) -> Tuple[bool, str]:
    """Reject mixed-symbol or stale contexts before an AI-required decision."""
    if not isinstance(snapshot, dict):
        return False, "snapshot missing"
    freshness = snapshot.get("freshness") or {}
    if freshness.get("symbol_match") is False:
        return False, "snapshot symbol mismatch"
    if freshness.get("stale") is True:
        return False, "snapshot stale"
    if freshness.get("market_data") == "missing":
        return False, "market data missing"
    return True, "ok"


def decision_prompt(snapshot: Dict[str, Any]) -> str:
    schema = {
        "decision": "BUY|SELL|WAIT",
        "confidence": "integer 0..100",
        "rationale": "concise evidence-based sentence",
        "plan": {"entry": "conditional or null", "stop_loss": "conditional or null", "take_profit": "conditional or null"},
        "risks": ["short strings"],
        "missing_data": ["short strings"],
    }
    return ("Analyze this bounded Jarvis snapshot. Safety gates and local risk rules are authoritative; "
            "you have no order/tool authority. Do not reveal hidden reasoning. Return JSON only matching "
            f"{json.dumps(schema)}.\nSNAPSHOT:\n{json.dumps(snapshot, separators=(',', ':'), default=str)}")


def validate_decision(raw: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(data, dict):
            return None, "response is not an object"
        decision = str(data.get("decision", "")).upper()
        if decision not in {"BUY", "SELL", "WAIT"}:
            return None, "invalid decision"
        confidence = int(data.get("confidence"))
        if confidence < 0 or confidence > 100:
            return None, "invalid confidence"
        rationale = str(data.get("rationale", "")).strip()
        if not rationale or len(rationale) > _MAX_TEXT:
            return None, "invalid rationale"
        plan = data.get("plan", {})
        if not isinstance(plan, dict):
            return None, "invalid plan"
        result = {
            "decision": decision,
            "confidence": confidence,
            "rationale": rationale,
            "plan": {"entry": _clean(plan.get("entry")), "stop_loss": _clean(plan.get("stop_loss")), "take_profit": _clean(plan.get("take_profit"))},
            "risks": _clean(data.get("risks", [])),
            "missing_data": _clean(data.get("missing_data", [])),
        }
        return result, None
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return None, f"invalid response: {type(exc).__name__}"

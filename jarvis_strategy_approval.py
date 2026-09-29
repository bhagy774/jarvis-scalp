"""Pure Jarvis-owned strategy consensus and entry-approval value objects.

Parts 1-12 are evidence producers.  This module has no exchange/network side
 effects and does not place orders; jarvis_FIXED.py is the runtime authority
that calls these functions after analyzing a symbol-scoped candle snapshot.
The approval record is an explicit runtime contract, not a secret credential.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import time
from typing import Any, Mapping, Optional

POLICY_VERSION = "jarvis-central-entry-v1"
APPROVAL_SCHEMA = "jarvis-entry-approval-v1"
DEFAULT_APPROVAL_TTL_SECONDS = 180.0

PART_WEIGHTS = {
    "part1_breakout": 1.1,
    "part2_zone": 1.3,
    "part3_psychology": 1.0,
    "part4_volume": 1.3,
    "part5_ml": 1.2,
    "part6_trend": 1.5,
    "part7_volatility": 1.1,
    "part8_structure": 1.4,
    "part9_orderflow": 1.4,
    "part10_candlestats": 1.0,
}
ANCHORS = {"part6_trend", "part8_structure", "part9_orderflow"}
INACTIVE_MARKERS = ("error", "offline", "fallback", "missing")


def _direction(value: Any) -> str:
    value = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if value in {"CALL", "BUY", "LONG", "BULLISH"}:
        return "BUY"
    if value in {"PUT", "SELL", "SHORT", "BEARISH"}:
        return "SELL"
    return "NO_TRADE"


def _clean_symbol(value: Any) -> str:
    return str(value or "").strip().upper().replace("/", "").replace("-", "").replace("_", "")


def evaluate_central_strategy(
    part_results: Any,
    part7_gate: Any,
    *,
    confidence: Any = None,
    minimum_confidence: Optional[float] = None,
    expected_symbol: Any = None,
) -> dict[str, Any]:
    """Apply deterministic Part 1-10 evidence policy centrally in Jarvis.

    Mirrors the canonical Part11 weights, 3-engine / 3.5 quorum, 65% weighted
    consensus, anchor dissent, and Part2 support/resistance veto conditions.
    Part11's return value is intentionally not used as authority: its veto
    findings are re-evaluated here from the underlying part evidence.
    Neutral votes remain neutral, not vetoes.  Part7's explicit block is a
    separate new-entry safety finding and fails closed when absent/malformed.
    """
    blockers: list[str] = []
    if not isinstance(part_results, Mapping):
        return _result("BLOCKED", "NO_TRADE", None, ["Part result mapping is missing"], {})
    if not isinstance(part7_gate, Mapping):
        return _result("BLOCKED", "NO_TRADE", None, ["Part7 gate is missing"], {})
    if part7_gate.get("entry_blocked") is not False or part7_gate.get("risk_veto") is not False:
        reason = str(part7_gate.get("reason") or "Part7 entry gate blocks or is incomplete")
        return _result("BLOCKED", "NO_TRADE", None, [reason], {})
    if expected_symbol is not None:
        expected_clean = _clean_symbol(expected_symbol)
        gate_symbol = _clean_symbol(part7_gate.get("symbol"))
        if not expected_clean or not gate_symbol or gate_symbol != expected_clean:
            return _result("BLOCKED", "NO_TRADE", None, ["Part7 gate symbol identity is missing or mismatched"], {})
        # A bare pair of booleans is not an execution-grade Part7 result. The
        # entry gate must be the complete aggregate from all native intervals,
        # with each frame explicitly valid for the same selected symbol.
        required_timeframes = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h")
        timeframe_results = part7_gate.get("timeframe_results")
        if (part7_gate.get("status") != "ok" or part7_gate.get("data_status") != "valid"
                or part7_gate.get("timeframe") != "aggregate"
                or not isinstance(timeframe_results, Mapping)
                or set(timeframe_results) != set(required_timeframes)
                or part7_gate.get("blocked_timeframes") != []
                or part7_gate.get("veto_timeframes") != []):
            return _result("BLOCKED", "NO_TRADE", None, ["Part7 aggregate is incomplete or not execution-valid"], {})
        for timeframe in required_timeframes:
            row = timeframe_results.get(timeframe)
            if (not isinstance(row, Mapping) or row.get("timeframe") != timeframe
                    or _clean_symbol(row.get("symbol")) != expected_clean
                    or row.get("data_status") != "valid"
                    or row.get("entry_blocked") is not False or row.get("risk_veto") is not False
                    or row.get("status") not in {"ok", "neutral"}):
                return _result("BLOCKED", "NO_TRADE", None,
                               [f"Part7 {timeframe} result is missing, stale, mismatched, or blocked"], {})

    required = tuple(PART_WEIGHTS)
    missing = [name for name in required if name not in part_results]
    if missing:
        return _result("BLOCKED", "NO_TRADE", None,
                       ["Part evidence is incomplete: " + ", ".join(missing)], {})

    buy = sell = 0.0
    denominator = 0.0
    buy_engines: list[str] = []
    sell_engines: list[str] = []
    neutral_engines: list[str] = []
    for name, weight in PART_WEIGHTS.items():
        item = part_results.get(name)
        if not isinstance(item, Mapping):
            # Match Part11's offline/errored-engine exclusion rather than
            # letting an unavailable engine manufacture either direction.
            continue
        thought = str(item.get("thought", "")).lower()
        if any(marker in thought for marker in INACTIVE_MARKERS):
            continue
        raw_signal = item.get("signal", 0)
        try:
            signal = float(raw_signal)
        except (TypeError, ValueError, OverflowError):
            return _result("BLOCKED", "NO_TRADE", None,
                           [f"{name} signal is malformed"], {})
        if not math.isfinite(signal):
            return _result("BLOCKED", "NO_TRADE", None,
                           [f"{name} signal is non-finite"], {})

        # Preserve the existing Part11 1m-noise handling when its annotated
        # result format is present. The live MTF adapter emits MTF x/8; those
        # values were already gated by Jarvis' per-part MTF integrity logic.
        import re
        mtf_match = re.search(r"mtf: (\d)/4", thought)
        if mtf_match and signal != 0 and int(mtf_match.group(1)) < 2:
            signal = 0.0

        denominator += weight
        if signal > 0:
            buy += weight * signal
            buy_engines.append(name)
        elif signal < 0:
            sell += weight * abs(signal)
            sell_engines.append(name)
        else:
            neutral_engines.append(name)

    active_count = len(buy_engines) + len(sell_engines) + len(neutral_engines)
    diagnostic = {
        "weighted_buy": round(buy, 6), "weighted_sell": round(sell, 6),
        "denominator": round(denominator, 6), "active_count": active_count,
        "buy_engines": list(buy_engines), "sell_engines": list(sell_engines),
        "neutral_engines": list(neutral_engines),
    }
    if active_count < 3 or denominator < 3.5:
        return _result("NEUTRAL", "NO_TRADE", None,
                       [f"Insufficient confluence ({active_count}/3 engines, weight {denominator:.1f}/3.5)"], diagnostic)

    buy_ratio = buy / denominator if denominator else 0.0
    sell_ratio = sell / denominator if denominator else 0.0
    diagnostic.update({"buy_ratio": round(buy_ratio, 6), "sell_ratio": round(sell_ratio, 6)})
    p2 = part_results.get("part2_zone")
    p2 = p2 if isinstance(p2, Mapping) else {}
    p2_thought = str(p2.get("thought", "")).lower()
    try:
        p2_signal = float(p2.get("signal", 0))
    except (TypeError, ValueError, OverflowError):
        return _result("BLOCKED", "NO_TRADE", None, ["Part2 zone signal is malformed"], diagnostic)
    if not math.isfinite(p2_signal):
        return _result("BLOCKED", "NO_TRADE", None, ["Part2 zone signal is non-finite"], diagnostic)

    recommendation = "NO_TRADE"
    if buy_ratio >= 0.65:
        if p2_signal < 0 or "resistance zone" in p2_thought:
            return _result("BLOCKED", "NO_TRADE", None,
                           [f"Central zone veto: BUY blocked at resistance ({p2.get('thought', '')})"], diagnostic)
        strong_opponents = [name for name in sell_engines if name in ANCHORS]
        if len(strong_opponents) >= 2:
            return _result("BLOCKED", "NO_TRADE", None,
                           ["Central anchor-dissent veto: BUY opposed by " + ", ".join(strong_opponents)], diagnostic)
        recommendation = "BUY"
    elif sell_ratio >= 0.65:
        if p2_signal > 0 or "support zone" in p2_thought:
            return _result("BLOCKED", "NO_TRADE", None,
                           [f"Central zone veto: SELL blocked at support ({p2.get('thought', '')})"], diagnostic)
        strong_opponents = [name for name in buy_engines if name in ANCHORS]
        if len(strong_opponents) >= 2:
            return _result("BLOCKED", "NO_TRADE", None,
                           ["Central anchor-dissent veto: SELL opposed by " + ", ".join(strong_opponents)], diagnostic)
        recommendation = "SELL"
    else:
        return _result("NEUTRAL", "NO_TRADE", None,
                       [f"Split weighted consensus (BUY {buy_ratio:.0%}, SELL {sell_ratio:.0%}; 65% required)"], diagnostic)

    normalized_confidence = None
    if confidence is not None:
        try:
            normalized_confidence = float(confidence)
        except (TypeError, ValueError, OverflowError):
            return _result("BLOCKED", "NO_TRADE", recommendation,
                           ["Central confidence is malformed"], diagnostic)
        if not math.isfinite(normalized_confidence) or not 0 <= normalized_confidence <= 100:
            return _result("BLOCKED", "NO_TRADE", recommendation,
                           ["Central confidence is outside 0..100"], diagnostic)
        if minimum_confidence is not None and normalized_confidence < float(minimum_confidence):
            return _result("BLOCKED", "NO_TRADE", recommendation,
                           [f"Central confidence {normalized_confidence:.0f} below minimum {float(minimum_confidence):.0f}"], diagnostic)

    return _result("APPROVED", recommendation, normalized_confidence, [], diagnostic)


def _result(status: str, direction: str, confidence: Any, reasons: list[str], diagnostic: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": status,
        "approved": status == "APPROVED",
        "direction": direction,
        "recommendation": direction if direction != "NO_TRADE" else "NO_TRADE",
        "confidence": confidence,
        "reasons": list(reasons),
        "policy_version": POLICY_VERSION,
        "diagnostic": diagnostic,
    }


@dataclass(frozen=True)
class EntryApproval:
    schema_version: str
    authority: str
    status: str
    policy_version: str
    direction: str
    symbol: str
    exchange: str
    contract: str
    instrument_id: str
    market_type: str
    analysis_symbol: str
    analysis_exchange: str
    snapshot_version: str
    analysis_timestamp: float
    expires_at: float
    confidence: int
    approval_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_entry_approval(
    central_decision: Mapping[str, Any], *, direction: Any, symbol: Any,
    exchange: Any, contract: Any, instrument_id: Any = "", market_type: Any = "",
    analysis_symbol: Any = "", analysis_exchange: Any = "", snapshot_version: Any,
    analysis_timestamp: Any, confidence: Any, ttl_seconds: float = DEFAULT_APPROVAL_TTL_SECONDS,
) -> dict[str, Any]:
    """Create a scope-bound approval only from an APPROVED Jarvis decision."""
    if not isinstance(central_decision, Mapping) or central_decision.get("approved") is not True:
        raise ValueError("Jarvis central strategy did not approve this entry")
    normalized_direction = _direction(direction)
    if normalized_direction not in {"BUY", "SELL"} or _direction(central_decision.get("direction")) != normalized_direction:
        raise ValueError("approval direction differs from the central decision")
    clean_symbol, clean_contract = _clean_symbol(symbol), _clean_symbol(contract)
    clean_exchange = str(exchange or "").strip().lower()
    clean_id = str(instrument_id or clean_contract).strip()
    clean_market = str(market_type or "").strip().lower()
    version = str(snapshot_version or "").strip()
    try:
        issued = float(analysis_timestamp)
        conf = int(float(confidence))
        ttl = float(ttl_seconds)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("approval timestamps/confidence are malformed")
    if (not clean_symbol or clean_symbol != clean_contract or not clean_exchange
            or not clean_id or not version or not math.isfinite(issued)
            or not math.isfinite(ttl) or ttl <= 0 or not 0 <= conf <= 100):
        raise ValueError("approval scope is incomplete")
    if _clean_symbol(central_decision.get("symbol", clean_symbol)) != clean_symbol:
        raise ValueError("approval symbol differs from central decision scope")
    expires = issued + min(ttl, DEFAULT_APPROVAL_TTL_SECONDS)
    core = {
        "schema_version": APPROVAL_SCHEMA,
        "authority": "jarvis_FIXED",
        "status": "APPROVED",
        "policy_version": POLICY_VERSION,
        "direction": normalized_direction,
        "symbol": clean_symbol,
        "exchange": clean_exchange,
        "contract": clean_contract,
        "instrument_id": clean_id,
        "market_type": clean_market,
        "analysis_symbol": _clean_symbol(analysis_symbol or clean_symbol),
        "analysis_exchange": str(analysis_exchange or clean_exchange).strip().lower(),
        "snapshot_version": version,
        "analysis_timestamp": issued,
        "expires_at": expires,
        "confidence": conf,
    }
    # The identifier is diagnostic and helps catch accidental field drift; it
    # is deliberately not treated as a secret or as cryptographic authorization.
    digest = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**core, "approval_id": digest[:24]}


def validate_entry_approval(
    approval: Any, *, direction: Any, symbol: Any, exchange: Any, contract: Any,
    instrument_id: Any = None, market_type: Any = None, snapshot_version: Any,
    confidence: Any = None, now: Optional[float] = None,
    max_age_seconds: float = DEFAULT_APPROVAL_TTL_SECONDS,
) -> tuple[bool, str]:
    """Validate an explicit central approval against the actual entry request."""
    if isinstance(approval, EntryApproval):
        approval = approval.to_dict()
    if not isinstance(approval, Mapping):
        return False, "Central Jarvis entry approval is required"
    if (approval.get("schema_version") != APPROVAL_SCHEMA
            or approval.get("authority") != "jarvis_FIXED"
            or approval.get("status") != "APPROVED"
            or approval.get("policy_version") != POLICY_VERSION):
        return False, "Central Jarvis approval schema/authority is invalid"
    if _direction(approval.get("direction")) != _direction(direction) or _direction(direction) not in {"BUY", "SELL"}:
        return False, "Central Jarvis approval direction mismatch"
    if (_clean_symbol(approval.get("symbol")) != _clean_symbol(symbol)
            or _clean_symbol(approval.get("contract")) != _clean_symbol(contract)
            or str(approval.get("exchange") or "").strip().lower() != str(exchange or "").strip().lower()):
        return False, "Central Jarvis approval instrument scope mismatch"
    if instrument_id is not None and str(approval.get("instrument_id") or "").strip() != str(instrument_id).strip():
        return False, "Central Jarvis approval contract id mismatch"
    if market_type is not None and str(approval.get("market_type") or "").strip().lower() != str(market_type).strip().lower():
        return False, "Central Jarvis approval contract type mismatch"
    version = str(snapshot_version or "").strip()
    if not version or str(approval.get("snapshot_version") or "").strip() != version:
        return False, "Central Jarvis approval snapshot version mismatch"
    try:
        issued = float(approval.get("analysis_timestamp"))
        expires = float(approval.get("expires_at"))
        approved_confidence = int(approval.get("confidence"))
        current = time.time() if now is None else float(now)
        max_age = float(max_age_seconds)
    except (TypeError, ValueError, OverflowError):
        return False, "Central Jarvis approval timestamp/confidence is malformed"
    if (not all(math.isfinite(x) for x in (issued, expires, current, max_age))
            or max_age <= 0 or issued > current + 2 or expires <= current
            or current - issued > max_age or expires - issued > DEFAULT_APPROVAL_TTL_SECONDS + 1e-6):
        return False, "Central Jarvis approval is expired or from the future"
    if confidence is not None:
        try:
            requested_confidence = int(float(confidence))
        except (TypeError, ValueError, OverflowError):
            return False, "Requested confidence is malformed"
        if requested_confidence != approved_confidence:
            return False, "Central Jarvis approval confidence mismatch"
    # Check the diagnostic digest to reject accidental mutation. This is not
    # an authentication mechanism; callers must enforce provenance/scope.
    core = {k: approval.get(k) for k in (
        "schema_version", "authority", "status", "policy_version", "direction", "symbol",
        "exchange", "contract", "instrument_id", "market_type", "analysis_symbol",
        "analysis_exchange", "snapshot_version", "analysis_timestamp", "expires_at", "confidence",
    )}
    digest = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
    if approval.get("approval_id") != digest:
        return False, "Central Jarvis approval record was modified"
    return True, "Central Jarvis approval validated"

"""Plain, conservative terminal formatting for JARVIS decision audits.

This module only formats snapshots already produced by the trading pipeline. It
never fetches data, changes a decision, calculates a trade plan, or submits an
order. Missing values remain explicitly unknown rather than being filled with
plausible-looking defaults.
"""
from __future__ import annotations

import math
import re
import time
from collections.abc import Mapping
from numbers import Real
from typing import Any

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_MISSING = {"", "N/A", "NA", "NONE", "NULL", "UNKNOWN", "UNAVAILABLE", "MISSING", "—", "-"}


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().upper() not in _MISSING
    return True


def _text(value: Any, limit: int = 180) -> str:
    if not _present(value):
        return ""
    text = _ANSI.sub("", str(value)).replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _amount(value: Any) -> str:
    number = _number(value)
    if number is None:
        return _text(value)
    rendered = f"{number:,.8f}".rstrip("0").rstrip(".")
    return rendered or "0"


def _direction(value: Any) -> str:
    text = _text(value).upper().replace("-", "_")
    if text in {"BUY", "CALL", "LONG", "BULLISH"}:
        return "BUY"
    if text in {"SELL", "PUT", "SHORT", "BEARISH"}:
        return "SELL"
    if text in {"WAIT", "PENDING", "STANDBY", "NO_TRADE", "NO TRADE", "NEUTRAL"}:
        return "NO_TRADE"
    return "UNKNOWN" if not text else text


def _signal_side(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("signal", value.get("direction", value.get("bias")))
    number = _number(value)
    if number is not None:
        return "BUY" if number > 0 else "SELL" if number < 0 else "NEUTRAL"
    return _direction(value)


def _confidence(raw: Any, *, normalized: bool = False) -> str:
    if not _present(raw):
        return "UNKNOWN"
    number = _number(raw)
    if number is not None:
        return f"{_amount(number)}%"
    text = _text(raw)
    if text and text.upper() not in _MISSING:
        if "%" in text or "/" in text:
            return text
        return f"{text}%" if normalized else text
    return "UNKNOWN"


def _part_name(name: Any) -> str:
    raw = _text(name, 80)
    match = re.match(r"^part(\d+)(?:_(.*))?$", raw, re.IGNORECASE)
    if not match:
        return raw or "Unnamed part"
    suffix = (match.group(2) or "").replace("_", " ").strip()
    label = f"Part {match.group(1)}"
    return f"{label} ({suffix})" if suffix else label


def _part_evidence(value: Any) -> tuple[Any, str]:
    if isinstance(value, Mapping):
        signal = value.get("signal", value.get("direction", value.get("bias")))
        reason = value.get("thought", value.get("reason", value.get("message", value.get("verdict"))))
        return signal, _text(reason)
    if isinstance(value, Real) and not isinstance(value, bool):
        return value, ""
    return None, _text(value)


def _snapshot_metadata(snapshot: Any, now: float) -> list[str]:
    if snapshot is None:
        return ["  Candle snapshot: UNKNOWN — no snapshot metadata supplied."]
    if isinstance(snapshot, Mapping):
        fetched_at = snapshot.get("fetched_at")
        frames = snapshot.get("frames")
    else:
        fetched_at = getattr(snapshot, "fetched_at", None)
        frames = getattr(snapshot, "frames", None)
    fetched = _number(fetched_at)
    if fetched is None:
        lines = ["  Candle snapshot age: UNKNOWN — fetch timestamp unavailable."]
    else:
        age = now - fetched
        if age < 0:
            lines = ["  Candle snapshot age: UNKNOWN — snapshot timestamp is ahead of the local clock."]
        else:
            lines = [f"  Candle snapshot age: about {_amount(age)}s since fetch."]
    frame = None
    if isinstance(frames, Mapping):
        frame = frames.get("1m")
    if frame is None:
        lines.append("  1m source / candle confirmation: UNKNOWN — 1m frame metadata unavailable.")
    else:
        if isinstance(frame, Mapping):
            source = frame.get("source")
            confirmed = frame.get("current_is_confirmed")
            if confirmed is None and frame.get("current") is not None:
                confirmed = False
        else:
            source = getattr(frame, "source", None)
            confirmed = getattr(frame, "current_is_confirmed", None)
        source_text = _text(source) or "UNKNOWN"
        if confirmed is False:
            confirmation = "forming candle is unconfirmed; closed candles are the analysis input"
        elif confirmed is True:
            confirmation = "current candle marked confirmed by source metadata"
        else:
            confirmation = "confirmation status UNKNOWN"
        lines.append(f"  1m source / candle confirmation: {source_text}; {confirmation}.")
    return lines


def _position_summary(position_state: Any) -> list[str]:
    if not isinstance(position_state, Mapping):
        return ["  UNKNOWN — no local position snapshot supplied.",
                "  Venue/account flatness: UNKNOWN — not independently reconciled here."]
    lines: list[str] = []
    for key, label in (("live", "Local live tracker"), ("paper", "Local paper tracker")):
        records = position_state.get(key)
        if not isinstance(records, (list, tuple)):
            lines.append(f"  {label}: UNKNOWN — tracker state unavailable.")
            continue
        states = sorted({_text(item.get("status"), 40) for item in records
                         if isinstance(item, Mapping) and _present(item.get("status"))})
        state_text = f"; recorded state(s): {', '.join(states)}" if states else ""
        lines.append(f"  {label}: {len(records)} local record(s){state_text}.")
    lines.append("  Venue/account flatness: UNKNOWN — local record counts are not an exchange reconciliation.")
    return lines


def _reported_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_text(value)] if _text(value) else []
    if isinstance(value, Mapping):
        return [_text(value)]
    try:
        return list(dict.fromkeys(_text(item) for item in value if _text(item)))
    except TypeError:
        return [_text(value)] if _text(value) else []


def _runtime_order_lines(outcome: Any) -> list[str]:
    if not isinstance(outcome, Mapping):
        return ["  Executor return: UNKNOWN — no submission result supplied.",
                "  Fill confirmation: UNKNOWN — not inferred.",
                "  Close status: UNKNOWN — not observed."]
    success = outcome.get("success")
    if isinstance(success, bool):
        lines = [f"  Executor return success field: {str(success).lower()}."]
    elif _present(success):
        lines = [f"  Executor return success field: {_text(success)} (raw value)."]
    else:
        lines = ["  Executor return success field: UNKNOWN."]
    reason = _text(outcome.get("reason") or outcome.get("error"))
    if reason:
        lines.append(f"  Executor reason: {reason}")

    position = outcome.get("position")
    if not isinstance(position, Mapping):
        position = {}
    paper = outcome.get("paper") is True or position.get("paper") is True
    if paper:
        lines.append("  Submission state: not sent to an exchange; this is a paper simulation.")
        lines.append("  Venue acknowledgement: not applicable to the paper record.")
    else:
        submitted = outcome.get("submitted", outcome.get("order_submitted"))
        acknowledged = outcome.get("acknowledged", outcome.get("ack_status"))
        if submitted is not None:
            lines.append(f"  Raw submitted field: {_text(submitted)}.")
        elif success is False:
            lines.append("  Submission state: UNKNOWN — success=False can reflect a preflight gate or a failed request.")
        else:
            lines.append("  Submission state: no distinct submitted flag supplied; executor return alone is not a separate submission record.")
        if acknowledged is not None:
            lines.append(f"  Raw acknowledgement field: {_text(acknowledged)}.")
        else:
            lines.append("  Venue acknowledgement: UNKNOWN — no separate acknowledgement field supplied.")

    position_fields = []
    for key, label in (("contracts", "quantity"), ("leverage", "leverage"),
                       ("margin_usdt", "margin"), ("trade_risk_usdt", "risk"),
                       ("notional_usdt", "notional")):
        value = _number(position.get(key))
        if value is None or value < 0:
            continue
        if key == "contracts":
            rendered = _amount(value)
            unit = " contract(s)"
        elif key == "leverage":
            rendered = _amount(value)
            unit = "x"
        else:
            rendered = f"${_amount(value)}"
            unit = " USDT"
        position_fields.append(f"{label}={rendered}{unit}")
    if position_fields:
        lines.append("  Executor-reported sizing (local record; not venue-reconciled): " + "; ".join(position_fields) + ".")
    status = _text(position.get("status"))
    position_id = _text(position.get("id"))
    if position_id or status:
        detail = []
        if position_id:
            detail.append(f"id={position_id}")
        if status:
            detail.append(f"local status={status}")
        lines.append("  Position record: " + "; ".join(detail) + " (not an independent fill/position confirmation).")
    if outcome.get("fill_status") is not None:
        lines.append(f"  Raw fill_status field: {_text(outcome.get('fill_status'))}.")
    elif outcome.get("filled") is not None:
        lines.append(f"  Raw filled field: {_text(outcome.get('filled'))}.")
    else:
        lines.append("  Fill confirmation: not supplied; not inferred from success or local OPEN status.")
    if outcome.get("close_status") is not None:
        lines.append(f"  Raw close_status field: {_text(outcome.get('close_status'))}.")
    elif outcome.get("closed") is not None:
        lines.append(f"  Raw closed field: {_text(outcome.get('closed'))}.")
    else:
        lines.append("  Close status: not supplied / not observed in this return.")
    return lines


def format_decision_audit(
    decision: Any,
    symbol: Any,
    *,
    parts: Any = None,
    blockers: Any = None,
    candidate: Any = None,
    analysis_result: Any = None,
    market_context: Any = None,
    snapshot: Any = None,
    position_state: Any = None,
    execution_mode: Any = None,
    stage: str = "FINAL_GATE",
    order_outcome: Any = None,
    provenance: Any = None,
    run_label: Any = None,
    now: float | None = None,
) -> str:
    """Format observed pipeline values without changing or inferring decisions."""
    decision = decision if isinstance(decision, Mapping) else {}
    candidate = candidate if isinstance(candidate, Mapping) else {}
    analysis_result = analysis_result if isinstance(analysis_result, Mapping) else {}
    market_context = market_context if isinstance(market_context, Mapping) else {}
    parts = parts if isinstance(parts, Mapping) else {}
    current = time.time() if now is None else now

    label = _text(run_label)
    heading = "JARVIS | DECISION REVIEW"
    if label:
        heading += f" [{label}]"
    lines = [heading, f"Stage: {_text(stage) or 'UNKNOWN'}"]
    mode = _text(execution_mode)
    lines.append(f"Execution mode: {mode if mode else 'UNKNOWN — not supplied'}")
    lines.append(f"Selected asset: {_text(symbol) or 'UNKNOWN — not supplied'}")

    # Data age is the snapshot's fetch age; it is not a claim that any external
    # feed is currently healthy. Preserve unknown when metadata is absent.
    lines.append("Data freshness / source:")
    lines.extend(_snapshot_metadata(snapshot, current))
    ctx_fields = []
    for key, title in (("regime", "regime"), ("trend", "trend"),
                       ("volatility_status", "volatility"), ("session", "session")):
        value = _text(market_context.get(key))
        if value:
            ctx_fields.append(f"{title}={value}")
    if ctx_fields:
        lines.append("Market context (reported): " + "; ".join(ctx_fields))
    else:
        lines.append("Market context (reported): UNKNOWN — no regime/trend fields supplied.")

    signal = candidate.get("trade_signal") if isinstance(candidate.get("trade_signal"), Mapping) else candidate
    initial_direction = _direction(signal.get("direction")) if isinstance(signal, Mapping) else "UNKNOWN"
    initial_conf = signal.get("confidence_score", signal.get("confidence")) if isinstance(signal, Mapping) else None
    final_direction = _direction(decision.get("direction"))
    final_conf = decision.get("confidence_display", decision.get("confidence"))
    lines.append("Signal → final decision:")
    lines.append(f"  Initial signal: {initial_direction}; confidence={_confidence(initial_conf)}.")
    lines.append(f"  Final decision: {final_direction}; confidence={_confidence(final_conf, normalized=True)}; status={_text(decision.get('status')) or 'UNKNOWN'}.")
    allowed = decision.get("execution_allowed")
    permission = "ALLOWED" if allowed is True else "BLOCKED" if allowed is False else "UNKNOWN"
    lines.append(f"  Entry permission: {permission}.")
    if initial_direction != "UNKNOWN" and final_direction != "UNKNOWN" and initial_direction != final_direction:
        lines.append(f"  Decision change: {initial_direction} → {final_direction}; final snapshot differs from the initial signal.")
    elif initial_direction != "UNKNOWN" and final_direction != "UNKNOWN":
        lines.append("  Decision change: none reported; initial and final directions match.")

    gate_notes = _reported_list(blockers)
    if gate_notes:
        lines.append("Reported gate / reason strings (classification not inferred):")
        lines.extend(f"  - {note}" for note in gate_notes)
    elif allowed is False and final_direction == "NO_TRADE":
        lines.append("Reported gate / reason strings: UNKNOWN — final NO_TRADE is explicit, but no specific blocker was supplied to this display.")
    elif allowed is True:
        lines.append("Reported gate / reason strings: none supplied for this snapshot; no independent gate check performed by this formatter.")
    else:
        lines.append("Reported gate / reason strings: UNKNOWN — not supplied.")

    reasons = _reported_list(decision.get("reasons"))
    no_trade_reason = _text(analysis_result.get("no_trade_reason"))
    if no_trade_reason and no_trade_reason not in reasons:
        reasons.append(no_trade_reason)
    if reasons:
        lines.append("Decision / analysis notes (reported; not automatically treated as blockers):")
        lines.extend(f"  - {reason}" for reason in reasons)

    if parts:
        candidate_side = initial_direction if initial_direction in {"BUY", "SELL"} else None
        evidence: dict[str, list[str]] = {"supports": [], "opposes": [], "neutral": [], "unclassified": []}
        for name, value in parts.items():
            raw_signal, description = _part_evidence(value)
            side = _signal_side(raw_signal)
            label_name = _part_name(name)
            details = f" — {description}" if description else ""
            if side == "NEUTRAL":
                evidence["neutral"].append(f"{label_name}{details}")
            elif side in {"BUY", "SELL"} and candidate_side:
                category = "supports" if side == candidate_side else "opposes"
                evidence[category].append(f"{label_name} [{side}]{details}")
            elif side in {"BUY", "SELL"}:
                evidence["unclassified"].append(f"{label_name} [{side}]{details}")
            else:
                note = f"{label_name} [{side}]"
                if details:
                    note += details
                evidence["unclassified"].append(note)
        lines.append("Actual part evidence (raw part outputs; not extra votes):")
        if candidate_side:
            lines.append(f"  Supports initial {candidate_side} signal ({len(evidence['supports'])}):")
            lines.extend(f"    - {item}" for item in evidence["supports"])
            lines.append(f"  Opposes initial {candidate_side} signal ({len(evidence['opposes'])}):")
            lines.extend(f"    - {item}" for item in evidence["opposes"])
        else:
            lines.append(f"  Directional / unclassified part outputs ({len(evidence['unclassified'])}):")
            lines.extend(f"    - {item}" for item in evidence["unclassified"])
        lines.append(f"  Neutral parts ({len(evidence['neutral'])}):")
        lines.extend(f"    - {item}" for item in evidence["neutral"])
        if evidence["unclassified"] and candidate_side:
            lines.append(f"  Unclassified part outputs ({len(evidence['unclassified'])}):")
            lines.extend(f"    - {item}" for item in evidence["unclassified"])
    else:
        lines.append("Actual part evidence: UNKNOWN — no part results supplied.")

    plan_fields = []
    for key, title in (("entry", "entry"), ("tp1", "TP1"), ("tp2", "TP2"), ("sl", "stop")):
        value = decision.get(key)
        if _present(value):
            plan_fields.append(f"{title}={_amount(value)}")
    expiry = _text(decision.get("expiry"))
    if expiry:
        plan_fields.append(f"expiry={expiry}")
    if plan_fields:
        lines.append("Candidate plan from final snapshot (not proof of an order): " + "; ".join(plan_fields))

    lines.append("Local position view:")
    lines.extend(_position_summary(position_state))
    if str(stage).upper() == "ORDER_SUBMISSION":
        lines.append("Order lifecycle (observed return only):")
        lines.extend(_runtime_order_lines(order_outcome))
    else:
        lines.append("Order lifecycle:")
        lines.append("  Submit: not attempted / not observed at this final-gate snapshot.")
        lines.append("  Acknowledgement, fill, and close: UNKNOWN — not observed at this stage.")

    prov = _text(provenance)
    if prov:
        lines.append(f"Decision provenance (reported): {prov}")
    lines.append("Display only: formatting does not alter the decision or verify exchange state.")
    return "\n".join(lines)

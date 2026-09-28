"""Opt-in append-only point-in-time snapshots and offline replay validation.

This does not query a provider's historical API or synthesize history from
candles. Captures begin only when explicitly enabled by the runtime.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Any, Mapping

from options_chain import parse_instant


def append_snapshot(path: str, chain: Mapping[str, Any], *, captured_at: datetime | None = None) -> bool:
    """Append a normalized provider snapshot; return False for invalid inputs."""
    if not path or not isinstance(chain, Mapping):
        return False
    captured = captured_at or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        return False
    row = {
        "schema": "jarvis.options.snapshot.v1",
        "captured_at": captured.astimezone(timezone.utc).isoformat(),
        "underlying": str(chain.get("underlying") or "").upper(),
        "providers": chain.get("providers", {}),
    }
    if not row["underlying"] or not isinstance(row["providers"], dict):
        return False
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
        return True
    except (OSError, TypeError, ValueError):
        return False


def _valid_replay_row(row: Mapping[str, Any], underlying: str, decision_time: datetime,
                      venue: str | None, max_age_seconds: int) -> tuple[bool, str]:
    if row.get("schema") != "jarvis.options.snapshot.v1":
        return False, "unsupported_snapshot_schema"
    if str(row.get("underlying", "")).upper() != underlying:
        return False, "wrong_underlying"
    captured = parse_instant(row.get("captured_at"))
    if captured is None or captured > decision_time:
        return False, "future_or_invalid_capture_time"
    providers = row.get("providers")
    if not isinstance(providers, dict):
        return False, "provider_map_missing"
    selected = [providers.get(venue)] if venue else list(providers.values())
    valid_provider = False
    for provider in selected:
        if not isinstance(provider, dict) or not provider.get("validation", {}).get("usable"):
            continue
        as_of = parse_instant(provider.get("retrieved_at") or provider.get("validation", {}).get("retrieved_at"))
        if as_of is None or as_of > decision_time or (decision_time - as_of).total_seconds() > max_age_seconds:
            continue
        contracts = provider.get("contracts")
        if not isinstance(contracts, list) or not contracts:
            continue
        valid = True
        for contract in contracts:
            if not isinstance(contract, dict) or contract.get("underlying") != underlying:
                valid = False
                break
            observed = parse_instant(contract.get("observed_at"))
            if observed is None or observed > decision_time or observed > as_of:
                valid = False
                break
            try:
                expiry = datetime.fromisoformat(str(contract.get("expiry"))).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                valid = False
                break
            if expiry.date() < decision_time.date():
                valid = False
                break
        if valid:
            valid_provider = True
            break
    return (True, "valid_point_in_time_snapshot") if valid_provider else (False, "no_complete_fresh_point_in_time_provider_snapshot")


def replay_snapshot(path: str, underlying: str, decision_time: datetime, *,
                    venue: str | None = None, max_age_seconds: int = 600) -> dict[str, Any]:
    """Return the newest admissible recorded snapshot at/before decision time."""
    if decision_time.tzinfo is None:
        return {"available": False, "reason": "decision_time_timezone_required", "not_ohlc_derived": True}
    decision = decision_time.astimezone(timezone.utc)
    target = str(underlying or "").upper().replace("USDT", "").replace("USD", "")
    if not path or not os.path.isfile(path):
        return {"available": False, "reason": "historical_provider_data_unavailable", "not_ohlc_derived": True, "source": "none"}
    candidates = []
    rejected = []
    try:
        with open(path, encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                except (ValueError, TypeError):
                    rejected.append("invalid_json_line")
                    continue
                if not isinstance(row, dict):
                    rejected.append("row_not_object")
                    continue
                ok, reason = _valid_replay_row(row, target, decision, venue, max_age_seconds)
                if ok:
                    candidates.append(row)
                else:
                    rejected.append(reason)
    except OSError:
        return {"available": False, "reason": "snapshot_store_read_failed", "not_ohlc_derived": True, "source": "none"}
    if not candidates:
        return {"available": False, "reason": "no_admissible_historical_options_snapshot", "not_ohlc_derived": True, "source": "none", "rejected_reasons": sorted(set(rejected))}
    selected = max(candidates, key=lambda r: parse_instant(r.get("captured_at")) or datetime.min.replace(tzinfo=timezone.utc))
    return {"available": True, "snapshot": selected, "not_ohlc_derived": True, "source": "recorded_options_snapshots", "rejected_reasons": sorted(set(rejected))}

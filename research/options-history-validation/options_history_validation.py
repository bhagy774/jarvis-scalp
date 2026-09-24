"""Offline validation for timestamped, asset-specific option snapshots.

This deliberately does not manufacture history from candles/OHLC.  Callers can
use the returned decision to gate new entries while leaving protective exits
untouched.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Mapping

_REQUIRED = ("asset", "as_of", "expiry", "strike", "call_oi", "put_oi", "iv")

def validate_option_history(rows: list[Mapping[str, Any]], selected_asset: str,
                            decision_time: datetime | None = None) -> dict[str, Any]:
    now = decision_time or datetime.now(timezone.utc)
    asset = str(selected_asset or "").upper().replace("-", "").replace("_", "")
    accepted, reasons = [], []
    for row in rows or []:
        missing = [k for k in _REQUIRED if row.get(k) in (None, "")]
        if missing:
            reasons.append(f"missing_history_fields:{','.join(missing)}"); continue
        row_asset = str(row["asset"]).upper().replace("-", "").replace("_", "")
        if row_asset != asset:
            reasons.append("wrong_underlying"); continue
        try:
            ts = datetime.fromisoformat(str(row["as_of"]).replace("Z", "+00:00"))
            exp = datetime.fromisoformat(str(row["expiry"]).replace("Z", "+00:00"))
        except ValueError:
            reasons.append("invalid_timestamp"); continue
        if ts.tzinfo is None or exp.tzinfo is None:
            reasons.append("timezone_required"); continue
        if ts > now:
            reasons.append("future_snapshot"); continue
        if exp <= ts:
            reasons.append("expired_at_snapshot"); continue
        accepted.append(dict(row))
    unique_days = sorted({str(r["as_of"])[:10] for r in accepted})
    usable = bool(accepted)
    if not usable and not reasons: reasons.append("history_unavailable")
    return {"usable": usable, "accepted": accepted, "available_days": unique_days,
            "history_days": len(unique_days), "reasons": sorted(set(reasons)),
            "source": "timestamped_options_snapshots" if usable else "none",
            "not_ohlc_derived": True}

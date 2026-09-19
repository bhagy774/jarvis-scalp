"""Strict risk-preserving entry lot limits; protective exits are out of scope."""
from __future__ import annotations
import math, os


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try: value = int(raw)
    except (TypeError, ValueError): raise ValueError(f"{name} must be an integer")
    if value < 1: raise ValueError(f"{name} must be >= 1")
    return value


def entry_lot_limits() -> tuple[int, int]:
    lo = _positive_int("JARVIS_MIN_ENTRY_LOTS", 1)
    hi = _positive_int("JARVIS_MAX_ENTRY_LOTS", 10**9)
    if lo > hi: raise ValueError("JARVIS_MIN_ENTRY_LOTS must not exceed JARVIS_MAX_ENTRY_LOTS")
    return lo, hi


def enforce_entry_lots(safe_qty, *, metadata=None, available_balance=None, reduce_only=False) -> int:
    """Final authoritative entry gate. Never rounds up or applies to exits."""
    if reduce_only: return int(safe_qty)
    lo, hi = entry_lot_limits()
    try: qty = int(math.floor(float(safe_qty)))
    except (TypeError, ValueError): raise ValueError("safe quantity is invalid")
    if qty < lo: raise ValueError(f"risk-safe quantity {qty} is below minimum entry lots {lo}")
    qty = min(qty, hi)
    if metadata:
        step = metadata.get("contract_size") or metadata.get("contract_step") or metadata.get("lot_step") or metadata.get("size_increment")
        if step is not None:
            try: step = int(step)
            except (TypeError, ValueError): raise ValueError("invalid contract increment metadata")
            if step < 1 or qty % step: qty -= qty % step
            if qty < lo: raise ValueError("contract increment leaves entry below minimum")
    if available_balance is not None and float(available_balance) <= 0: raise ValueError("available balance is unavailable")
    return qty

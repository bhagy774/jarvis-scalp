"""Optional Laya advisory; never computes or mutates Jarvis trading decisions.

Laya's published checkpoints are general-purpose, not market-trained. This adapter
is experimental, lazy (no import/download until enabled and called), and safe to omit.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any, Callable, Optional

ALLOWED = {"BUY", "SELL", "NO_TRADE"}

@dataclass(frozen=True)
class Advisory:
    status: str  # ok | unavailable | error | invalid | timeout | disabled
    symbol: str
    deterministic_decision: str
    suggestion: Optional[str] = None
    confidence: Optional[float] = None
    rationale: str = ""


def _predict_with_laya(snapshot: dict[str, Any]) -> Any:
    # Lazy import; Router performs its checkpoint fetch only on first prediction.
    from laya import Router
    router = Router()
    questions = {"suggestion": {"type": "choice", "instructions":
        "As an experimental, non-authoritative market commentary only, which label best describes this setup?",
        "criteria": {"BUY": "bullish setup", "SELL": "bearish setup", "NO_TRADE": "unclear, risky, or insufficient evidence"}}}
    result = router.predict(snapshot, questions)
    answer = result.get("answers", {}).get("suggestion", {})
    return {"suggestion": answer.get("choice"), "confidence": answer.get("confidence"),
            "rationale": "Laya class choice; no market-specific training or validated rationale available."}


def advise(snapshot: dict[str, Any], *, symbol: str, deterministic_decision: str,
           predictor: Optional[Callable[[dict], Any]] = None, timeout: float = 2.0,
           enabled: Optional[bool] = None) -> Advisory:
    """Best-effort commentary. Never return an executable decision on failure."""
    symbol = str(symbol or "UNKNOWN").upper()
    deterministic = str(deterministic_decision or "NO_TRADE").upper()
    if enabled is None:
        enabled = os.getenv("JARVIS_LAYA_ADVISORY", "true").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return Advisory("disabled", symbol, deterministic)
    if not isinstance(snapshot, dict) or str(snapshot.get("symbol", "")).upper() != symbol:
        return Advisory("invalid", symbol, deterministic, rationale="missing or mismatched symbol snapshot")
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit((predictor or _predict_with_laya), snapshot)
            try:
                result = future.result(timeout=max(0.01, float(timeout)))
            except FutureTimeout:
                future.cancel()
                return Advisory("timeout", symbol, deterministic, rationale="Laya advisory timed out")
    except (ImportError, ModuleNotFoundError) as exc:
        return Advisory("unavailable", symbol, deterministic, rationale=f"Laya unavailable: {type(exc).__name__}")
    except Exception as exc:
        return Advisory("error", symbol, deterministic, rationale=f"Laya advisory error: {type(exc).__name__}")
    if not isinstance(result, dict) or str(result.get("suggestion", "")).upper() not in ALLOWED:
        return Advisory("invalid", symbol, deterministic, rationale="invalid Laya structured choice")
    confidence = result.get("confidence")
    if confidence is not None and (not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1):
        return Advisory("invalid", symbol, deterministic, rationale="invalid Laya confidence")
    return Advisory("ok", symbol, deterministic, str(result["suggestion"]).upper(), confidence,
                    str(result.get("rationale", "Laya experimental advisory"))[:360])

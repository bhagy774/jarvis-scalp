"""Optional Laya advisory. Experimental only; never computes or mutates Jarvis decisions."""
from __future__ import annotations
import os, threading
from dataclasses import dataclass
from typing import Any, Callable, Optional

ALLOWED = {"BUY", "SELL", "NO_TRADE"}
@dataclass(frozen=True)
class Advisory:
    status: str
    symbol: str
    deterministic_decision: str
    suggestion: Optional[str] = None
    confidence: Optional[float] = None
    rationale: str = ""

def _predict_with_laya(snapshot: dict[str, Any]) -> Any:
    # Laya Router loads selected checkpoint lazily on predict; run only in daemon worker.
    from laya import Router
    questions = {"suggestion": {"type": "choice", "instructions": "Experimental non-authoritative market commentary only: which label best describes this setup?", "criteria": {"BUY": "bullish setup", "SELL": "bearish setup", "NO_TRADE": "unclear, risky, or insufficient evidence"}}}
    result = Router().predict(snapshot, questions)
    answer = result.get("answers", {}).get("suggestion", {})
    return {"suggestion": answer.get("choice"), "confidence": answer.get("confidence"), "rationale": "General-purpose Laya; not market-trained or validated."}

def advise(snapshot: dict[str, Any], *, symbol: str, deterministic_decision: str, predictor: Optional[Callable] = None, enabled: Optional[bool] = None) -> Advisory:
    symbol = str(symbol or "UNKNOWN").upper(); deterministic = str(deterministic_decision or "NO_TRADE").upper()
    if enabled is None: enabled = os.getenv("JARVIS_LAYA_ADVISORY", "true").strip().lower() in {"1","true","yes","on"}
    if not enabled: return Advisory("disabled", symbol, deterministic)
    if not isinstance(snapshot, dict) or str(snapshot.get("symbol", "")).upper() != symbol: return Advisory("invalid", symbol, deterministic, rationale="missing or mismatched symbol snapshot")
    try: result = (predictor or _predict_with_laya)(snapshot)
    except (ImportError, ModuleNotFoundError) as e: return Advisory("unavailable", symbol, deterministic, rationale=type(e).__name__)
    except Exception as e: return Advisory("error", symbol, deterministic, rationale=type(e).__name__)
    if not isinstance(result, dict) or str(result.get("suggestion", "")).upper() not in ALLOWED: return Advisory("invalid", symbol, deterministic, rationale="invalid Laya structured choice")
    confidence = result.get("confidence")
    if confidence is not None and (not isinstance(confidence, (int,float)) or not 0 <= confidence <= 1): return Advisory("invalid", symbol, deterministic, rationale="invalid confidence")
    return Advisory("ok", symbol, deterministic, str(result["suggestion"]).upper(), confidence, str(result.get("rationale", "Experimental advisory"))[:360])

# One bounded in-flight background request globally: a hung model cannot accumulate threads/VRAM jobs.
_lock = threading.Lock(); _state = {"busy": False, "status": "not_requested", "symbol": "", "deterministic": "NO_TRADE", "suggestion": None, "confidence": None, "rationale": ""}
def request_runtime_advisory(snapshot: dict[str, Any], *, symbol: str, deterministic_decision: str) -> Advisory:
    global _state
    key = str(symbol or "UNKNOWN").upper(); decision = str(deterministic_decision or "NO_TRADE").upper()
    enabled = os.getenv("JARVIS_LAYA_ADVISORY", "true").strip().lower() in {"1","true","yes","on"}
    with _lock:
        if not enabled: return Advisory("disabled", key, decision)
        if _state["busy"]: return Advisory("pending", key, decision, rationale="bounded Laya worker busy")
        if _state["symbol"] == key and _state["status"] not in ("not_requested", "pending"):
            return Advisory(_state["status"], key, decision, _state["suggestion"], _state["confidence"], _state["rationale"])
        _state = {"busy": True, "status": "pending", "symbol": key, "deterministic": decision, "suggestion": None, "confidence": None, "rationale": ""}
    import copy
    frozen = copy.deepcopy(snapshot)
    def worker():
        global _state
        try: result = advise(frozen, symbol=key, deterministic_decision=decision, enabled=True)
        except Exception as e: result = Advisory("error", key, decision, rationale=type(e).__name__)
        with _lock: _state = {"busy": False, "status": result.status, "symbol": result.symbol, "deterministic": result.deterministic_decision, "suggestion": result.suggestion, "confidence": result.confidence, "rationale": result.rationale}
    threading.Thread(target=worker, name="jarvis-laya-advisory", daemon=True).start()
    return Advisory("pending", key, decision, rationale="background inference; not a trading gate")

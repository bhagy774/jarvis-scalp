#!/usr/bin/env python3
"""
Ollama Local AI Integration for Jarvis SwingScalp Elite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Switched from Gemini/Cloud to 100% Local GPU Ollama API
"""

import os
import logging
import requests
import json
from typing import Tuple, Optional

logger = logging.getLogger("OllamaIntegration")

# Load API key from environment / .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
# An unset model is intentionally auto-discovered.  Do not silently request a
# model that is not installed merely because the host has an Ollama server.
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL")
OLLAMA_ENABLED = False

# ── Auto model resolution ────────────────────────────────────────────
# Preference order when auto-detecting an installed model.
_MODEL_PREFERENCE = (
    "phi3.5", "phi3", "qwen2.5", "mistral", "llama3.1", "llama3",
    "deepseek-r1", "gemma2",
)
_resolved_model_cache = None  # in-process cache; None = not resolved yet
_model_resolution_done = False
_no_model_logged = False


def list_installed_models() -> list:
    """Query Ollama /api/tags and return installed model names ([] on failure)."""
    try:
        base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        resp = requests.get(f"{base}/api/tags", timeout=5)
        if resp.status_code == 200:
            return [m.get("name", "") for m in resp.json().get("models", []) if m.get("name")]
    except Exception as e:
        logger.debug(f"Could not list Ollama models: {e}")
    return []


def resolve_ollama_model(force_refresh: bool = False):
    """Resolve which Ollama model to use.

    Priority:
      1. OLLAMA_MODEL env var (explicit override wins)
      2. First installed model matching the preference order
      3. First installed model of any kind
      4. None (callers must use their graceful fallbacks)

    Result is cached in-process; pass force_refresh=True to re-query.
    """
    global _resolved_model_cache, _model_resolution_done, _no_model_logged

    env_model = os.environ.get("OLLAMA_MODEL")
    if env_model:
        if _resolved_model_cache != env_model:
            logger.info(f"[JARVIS CORE] Ollama model: {env_model} (from OLLAMA_MODEL)")
        _resolved_model_cache = env_model
        _model_resolution_done = True
        return env_model

    if _model_resolution_done and not force_refresh:
        return _resolved_model_cache

    installed = list_installed_models()
    chosen = None
    for pref in _MODEL_PREFERENCE:
        for name in installed:
            if name.startswith(pref):
                chosen = name
                break
        if chosen:
            break
    if chosen is None and installed:
        chosen = installed[0]

    _model_resolution_done = True
    _resolved_model_cache = chosen
    if chosen:
        logger.info(f"[JARVIS CORE] Ollama model: {chosen} (auto-detected)")
    elif not _no_model_logged:
        _no_model_logged = True
        logger.warning("No Ollama model found — AI brains in math-fallback mode")
    return chosen


def _select_model(explicit: Optional[str] = None) -> Optional[str]:
    """Return an explicit or installed model; never invent a model name."""
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    if OLLAMA_MODEL:
        return OLLAMA_MODEL
    return resolve_ollama_model()


def preload_committee_models():
    """
    Optionally pre-load committee models into VRAM with bounded keep_alive.
    This is disabled by default and requires OLLAMA_PRELOAD_COMMITTEE=1.
    """
    if not OLLAMA_ENABLED or os.environ.get("OLLAMA_PRELOAD_COMMITTEE", "0") != "1":
        # Large models are loaded lazily by call_ollama; opt in explicitly to
        # warm-loading because three resident models can exhaust a 24 GB GPU.
        return

    models = [
        os.environ.get("MODEL_ANALYST", "deepseek-r1:14b"),
        os.environ.get("MODEL_VALIDATOR", "qwen2.5:14b"),
        os.environ.get("MODEL_RISK", "mistral-nemo:12b")
    ]
    
    # Unique models
    models = list(set(models))

    # Skip models that are not actually installed instead of failing
    try:
        installed = list_installed_models()
        if installed:
            before = list(models)
            models = [m for m in models if m in installed]
            skipped = [m for m in before if m not in models]
            if skipped:
                logger.info(f"Skipping non-installed committee models: {skipped}")
            if not models:
                logger.info("No committee models installed — nothing to pre-load")
                return
    except Exception as e:
        logger.warning(f"Committee model availability check failed, continuing anyway: {e}")

    logger.info(f"Ollama pre-loading committee models to VRAM: {models}")
    for model in models:
        try:
            logger.info(f"Pre-loading {model}...")
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": int(os.environ.get("OLLAMA_KEEP_ALIVE", "300"))},
                timeout=60
            )
            if resp.status_code == 200:
                logger.info(f"Successfully warm-loaded {model} into VRAM")
            else:
                logger.warning(f"Ollama failed to warm-load {model}: status {resp.status_code}")
        except Exception as e:
            logger.warning(f"Error warm-loading {model}: {e}")


def _init_ollama():
    """Initialize and test the Ollama connection"""
    global OLLAMA_ENABLED
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            # A reachable server without an installed/explicit model is not
            # usable for advisory inference; remain disabled and fail safely.
            selected_model = _select_model()
            if not selected_model:
                OLLAMA_ENABLED = False
                logger.warning("Ollama server reachable but no model is installed")
                return
            OLLAMA_ENABLED = True
            logger.info(f"Ollama Local AI initialized ({selected_model}) on {OLLAMA_BASE_URL}")
            # Start pre-loading in a background thread to prevent blocking main startup
            import threading
            threading.Thread(target=preload_committee_models, daemon=True).start()
        else:
            OLLAMA_ENABLED = False
            logger.warning(f"Ollama returned status code: {resp.status_code}")
    except Exception as e:
        logger.warning(f"Ollama init failed (is Ollama running?): {e}")
        OLLAMA_ENABLED = False


def runtime_metadata() -> dict:
    """Return bounded remote Ollama residency metadata when the server supports /api/ps.

    Local PyTorch detection cannot establish what a remote Ollama host uses; this
    endpoint is therefore reported separately and unavailable is explicit.
    """
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        resp = requests.get(f"{base}/api/ps", timeout=5)
        if resp.status_code != 200:
            return {"available": False, "reason": f"HTTP {resp.status_code}"}
        models = []
        for item in (resp.json().get("models", []) or [])[:16]:
            if not isinstance(item, dict):
                continue
            models.append({
                "name": str(item.get("name", ""))[:120],
                "size_vram": item.get("size_vram"),
                "size": item.get("size"),
                "processor": str(item.get("processor", ""))[:80] or "unknown",
            })
        return {"available": True, "models": models}
    except Exception as exc:
        return {"available": False, "reason": type(exc).__name__}


def test_ollama_connection() -> bool:
    """Test if Ollama API is accessible"""
    if not OLLAMA_ENABLED:
        return False
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Ollama connection test failed: {e}")
        return False


def call_ollama(prompt: str, model: str = None, timeout: int = 120) -> Tuple[Optional[str], Optional[str]]:
    """
    Call Ollama /api/generate endpoint.
    """
    if not OLLAMA_ENABLED:
        return None, "Ollama AI not available"
    selected_model = _select_model(model)
    if not selected_model:
        return None, "No installed Ollama model available"
    try:
        timeout = max(1, min(int(timeout), 120))
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": selected_model, "prompt": prompt, "stream": False},
            timeout=timeout
        )
        if resp.status_code == 200:
            return resp.json().get("response", ""), None
        return None, f"Ollama HTTP error {resp.status_code}: {resp.text}"
    except requests.exceptions.ConnectionError:
        return None, "Ollama not reachable"
    except Exception as e:
        logger.debug(f"Ollama API error: {e}")
        return None, str(e)


def call_ollama_chat(messages: list, model: str = None, timeout: int = 60) -> Tuple[Optional[str], Optional[str]]:
    """
    Call Ollama /api/chat endpoint with messages.
    """
    if not OLLAMA_ENABLED:
        return None, "Ollama AI not available"
    selected_model = _select_model(model)
    if not selected_model:
        return None, "No installed Ollama model available"
    try:
        timeout = max(1, min(int(timeout), 120))
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": selected_model, "messages": messages, "stream": False},
            timeout=timeout
        )
        if resp.status_code == 200:
            msg = resp.json().get("message", {})
            return msg.get("content", ""), None
        return None, f"Ollama HTTP error {resp.status_code}"
    except Exception as e:
        logger.error(f"Ollama chat interface error: {e}")
        return None, str(e)


def _validate_structured_response(text: str, schema: dict) -> Optional[dict]:
    """Validate the small JSON-schema subset used by advisory callers.

    Structured model output is never passed through as trusted text.  Required
    keys, object type, primitive types, and enum constraints are checked before
    returning a normalized JSON object.
    """
    try:
        value = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or not isinstance(schema, dict):
        return None
    if schema.get("type") not in (None, "object"):
        return None
    required = schema.get("required", [])
    if not isinstance(required, list) or any(key not in value for key in required):
        return None
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return None
    for key, rule in properties.items():
        if key not in value or not isinstance(rule, dict):
            continue
        item = value[key]
        expected = rule.get("type")
        valid_type = {
            "string": isinstance(item, str),
            "number": isinstance(item, (int, float)) and not isinstance(item, bool),
            "integer": isinstance(item, int) and not isinstance(item, bool),
            "boolean": isinstance(item, bool),
            "object": isinstance(item, dict),
            "array": isinstance(item, list),
        }.get(expected, True)
        if not valid_type or ("enum" in rule and item not in rule["enum"]):
            return None
    return value


def call_gemini_structured(prompt: str, schema: dict, model: str = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Compatibility name for bounded Ollama JSON output.  Invalid or malformed
    model responses fail closed instead of reaching trade-affecting callers.
    """
    if not OLLAMA_ENABLED:
        return None, "Ollama AI not available"
    
    selected_model = _select_model(model)
    if not selected_model:
        return None, "No installed Ollama model available"
    try:
        # Prompt injection to force JSON adherence
        full_prompt = f"{prompt}\n\nPlease respond strictly in JSON matching this schema: {json.dumps(schema)}"
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": selected_model,
                "prompt": full_prompt,
                "stream": False,
                "format": "json"
            },
            timeout=60
        )
        if resp.status_code == 200:
            raw = resp.json().get("response", "")
            parsed = _validate_structured_response(raw, schema)
            if parsed is None:
                return None, "Ollama returned invalid structured output"
            return json.dumps(parsed, separators=(",", ":")), None
        return None, f"Ollama JSON output error {resp.status_code}"
    except Exception as e:
        logger.error(f"Ollama structured output error: {e}")
        return None, str(e)


def call_gemini_with_search(prompt: str, model: str = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Dummy replacement for search - Ollama can't natively search the web out of the box
    so we just call the base model.
    """
    return call_ollama(prompt, model)


def analyze_trade_signal(price_data: dict, signal_data: dict, model: str = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Analyze trade trading signal using Ollama API.
    """
    prompt = f"""Analyze this trade trading signal:

Current Price: ${price_data.get('price', 'N/A')}
Trend: {price_data.get('trend', 'UNKNOWN')}
Volatility: {price_data.get('volatility', 'MEDIUM')}

Signal Analysis:
- Votes: BUY={signal_data.get('buy_votes', 0)}, SELL={signal_data.get('sell_votes', 0)}
- Confidence: {signal_data.get('confidence', 0)}%
- Consensus: {signal_data.get('consensus', 'NO-TRADE')}

Provide a 1-sentence decision: BUY, SELL, or NO-TRADE with reasoning.
"""
    return call_ollama(prompt, model)


# Legacy alias for backward compatibility
def init_ollama():
    _init_ollama()

# Initialize on module load — except in isolated historical backtest mode,
# where Ollama must never be probed or called at all.
if os.environ.get("JARVIS_BACKTEST_MODE", "0") == "1":
    OLLAMA_ENABLED = False
    logger.info("Backtest mode: Ollama initialization skipped (math/GPU-only replay)")
else:
    _init_ollama()

"""Retired Ollama compatibility surface. Never probes or calls a model server.

Laya, where enabled, is requested only via jarvis_laya_advisor as audit commentary.
"""
import json
from typing import Optional
OLLAMA_BASE_URL = None
OLLAMA_MODEL = None
OLLAMA_ENABLED = False

def list_installed_models(): return []
def resolve_ollama_model(force_refresh=False): return None
def preload_committee_models(): return None
def _init_ollama(): return None
def init_ollama(): return None
def runtime_metadata(): return {"available": False, "reason": "Ollama retired"}
def test_ollama_connection(): return False
def call_ollama(*args, **kwargs): return None, "Ollama retired"
def call_ollama_chat(*args, **kwargs): return None, "Ollama retired"

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


def call_gemini_structured(*args, **kwargs): return None, "Ollama retired"
def call_gemini_with_search(*args, **kwargs): return None, "Ollama retired"
def analyze_trade_signal(*args, **kwargs): return None, "Ollama retired"

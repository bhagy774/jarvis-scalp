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
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi3.5:3.8b")
OLLAMA_ENABLED = False


def _init_ollama():
    """Initialize and test the Ollama connection"""
    global OLLAMA_ENABLED
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            OLLAMA_ENABLED = True
            logger.info(f"Ollama Local AI initialized ({OLLAMA_MODEL}) on {OLLAMA_BASE_URL}")
        else:
            OLLAMA_ENABLED = False
            logger.warning(f"Ollama returned status code: {resp.status_code}")
    except Exception as e:
        logger.warning(f"Ollama init failed (is Ollama running?): {e}")
        OLLAMA_ENABLED = False


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
    
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": model or OLLAMA_MODEL, "prompt": prompt, "stream": False},
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
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": model or OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=timeout
        )
        if resp.status_code == 200:
            msg = resp.json().get("message", {})
            return msg.get("content", ""), None
        return None, f"Ollama HTTP error {resp.status_code}"
    except Exception as e:
        logger.error(f"Ollama chat interface error: {e}")
        return None, str(e)


def call_gemini_structured(prompt: str, schema: dict, model: str = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Alias for compatibility, forces Ollama JSON format if possible.
    """
    if not OLLAMA_ENABLED:
        return None, "Ollama AI not available"
    
    try:
        # Prompt injection to force JSON adherence
        full_prompt = f"{prompt}\n\nPlease respond strictly in JSON matching this schema: {json.dumps(schema)}"
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model or OLLAMA_MODEL,
                "prompt": full_prompt,
                "stream": False,
                "format": "json"
            },
            timeout=60
        )
        if resp.status_code == 200:
            return resp.json().get("response", ""), None
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

# Initialize on module load
_init_ollama()

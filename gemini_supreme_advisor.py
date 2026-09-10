#!/usr/bin/env python3
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
"""
JARVIS Gemini Supreme Advisor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Every 10 minutes, collects ALL Jarvis system data and sends it
to Google Gemini 3.1 Pro for deep strategic analysis.

The Gemini "Supreme Advisor" acts as a senior trading strategist:
  - Evaluates market regime (bull/bear/sideways/volatile)
  - Sets confidence thresholds for the session
  - Recommends leverage adjustments
  - Can issue trading overrides (AVOID_TRADING, FORCE_LONG, etc.)

Results are published on CognitiveBus topic: GEMINI_INSIGHT
JarvisAutoTrader subscribes and respects the override decisions.

USAGE:
  Set in .env:
    GEMINI_API_KEY=your_key
    GEMINI_ADVISOR_MODEL=gemini-3.1-pro-high
    GEMINI_ADVISOR_INTERVAL=600     # seconds (10 min default)
    GEMINI_ADVISOR_ENABLED=true
    GEMINI_ADVISOR_HARD_OVERRIDE=true  # false = advisory only
"""

import os
import json
import logging
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("GeminiSupremeAdvisor")

# ── Configuration ─────────────────────────────────────────────
GEMINI_API_KEY        = os.environ.get("GEMINI_API_KEY", "")
GEMINI_ADVISOR_MODEL  = os.environ.get("GEMINI_ADVISOR_MODEL", "gemini-3.6-flash")
ADVISOR_INTERVAL_SEC  = int(os.environ.get("GEMINI_ADVISOR_INTERVAL", "600"))
ADVISOR_ENABLED       = os.environ.get("GEMINI_ADVISOR_ENABLED", "true").lower() == "true"
HARD_OVERRIDE         = os.environ.get("GEMINI_ADVISOR_HARD_OVERRIDE", "true").lower() == "true"

# ── ANSI colors ───────────────────────────────────────────────
R = '\033[91m'; G = '\033[92m'; Y = '\033[93m'
C = '\033[96m'; W = '\033[97m'; DG = '\033[90m'
BD = '\033[1m'; RST = '\033[0m'

SYSTEM_PROMPT = """You are JARVIS SUPREME ADVISOR — an elite BTC scalping strategist with deep expertise in crypto derivatives, risk management, and algorithmic trading.

Your role: Every 10 minutes, analyze the complete state of the Jarvis trading system and provide strategic guidance.

TRADING CONTEXT:
- System trades BTC/USDT perpetual futures on Delta Exchange
- Uses 100x leverage with small position sizes ($0.10 margin = $10 notional)
- Strategy: short-term scalping (0.4% TP, 0.2% SL) and swing trades
- Local AI committee (Ollama models) handles per-signal decisions
- YOU handle the 10-minute macro strategy layer

YOUR OUTPUT: Respond ONLY in valid JSON, no extra text, no markdown:
{
  "market_regime": "TRENDING_BULL | TRENDING_BEAR | SIDEWAYS | VOLATILE | RANGING",
  "scalping_suitability": <0-100 integer, 100=perfect conditions>,
  "confidence_threshold_override": <60-95 integer, min confidence to trade>,
  "leverage_recommendation": <10-100 integer>,
  "trading_override": "FORCE_LONG | FORCE_SHORT | STAY_NEUTRAL | AVOID_TRADING",
  "risk_level": "LOW | MEDIUM | HIGH | EXTREME",
  "key_insight": "<max 60 word strategic insight>",
  "reasoning": "<max 100 word brief technical reasoning>",
  "next_check_minutes": <5-30 integer>
}

trading_override meanings:
- FORCE_LONG: Strong bullish — only take CALL/BUY signals, reject PUT
- FORCE_SHORT: Strong bearish — only take PUT/SELL signals, reject CALL
- STAY_NEUTRAL: Normal — follow local AI committee decisions
- AVOID_TRADING: High risk — skip ALL trades until next check"""


class GeminiSupremeAdvisor:
    """
    Background service that queries Gemini 3.1 Pro every 10 minutes
    with full Jarvis system context, then publishes strategic insights
    to CognitiveBus for LiveTrader to act on.
    """

    def __init__(self, bus=None, trader_ref=None):
        self.bus         = bus          # CognitiveBus instance
        self.trader      = trader_ref   # JarvisAutoTrader instance (optional)
        self._running    = False
        self._thread: Optional[threading.Thread] = None
        self._model      = None
        self._enabled    = ADVISOR_ENABLED
        self.last_insight: Dict[str, Any] = self._default_insight()
        self.call_count  = 0
        self.last_call_time: Optional[datetime] = None
        self._init_gemini()

    def _init_gemini(self):
        """Initialize the Gemini SDK (google.genai - new SDK)."""
        self._local_fallback_enabled = False  # Will be set True if Ollama available

        if not self._enabled:
            logger.info("[GeminiAdvisor] Disabled via GEMINI_ADVISOR_ENABLED=false")
            self._try_enable_local_fallback()
            return
        if not GEMINI_API_KEY:
            logger.warning("[GeminiAdvisor] No GEMINI_API_KEY found in .env -- trying Local AI fallback")
            self._enabled = False
            self._try_enable_local_fallback()
            return
        try:
            from google import genai
            from google.genai import types as genai_types
            self._client  = genai.Client(api_key=GEMINI_API_KEY)
            self._types   = genai_types
            self._model   = GEMINI_ADVISOR_MODEL  # just the model name string
            logger.info(f"[GeminiAdvisor] Initialized model: {GEMINI_ADVISOR_MODEL}")
            print(f"\n{BD}{C}  GEMINI SUPREME ADVISOR{RST}")
            print(f"{DG}  |- Model   : {W}{GEMINI_ADVISOR_MODEL}{RST}")
            print(f"{DG}  |- Interval: {W}{ADVISOR_INTERVAL_SEC//60} minutes{RST}")
            print(f"{DG}  |- Override: {W}{'HARD' if HARD_OVERRIDE else 'ADVISORY ONLY'}{RST}")
            print(f"{DG}  '- Status  : {G}ACTIVE{RST}\n")
            # Also try enabling local fallback as backup (even if Gemini works)
            self._try_enable_local_fallback(silent=True)
        except ImportError:
            logger.error("[GeminiAdvisor] google-genai not installed! Run: pip install google-genai")
            self._enabled = False
            self._try_enable_local_fallback()
        except Exception as e:
            logger.error(f"[GeminiAdvisor] Init failed: {e}")
            self._enabled = False
            self._try_enable_local_fallback()

    def _try_enable_local_fallback(self, silent: bool = False):
        """Try to connect to Ollama for local AI fallback advisory."""
        try:
            from ollama_integration import test_ollama_connection, OLLAMA_ENABLED
            import ollama_integration as _oli
            # Re-test connection live (OLLAMA_ENABLED may already be set)
            import requests as _req
            from ollama_integration import OLLAMA_BASE_URL
            resp = _req.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                self._local_fallback_enabled = True
                local_model = os.environ.get("OLLAMA_MODEL", "deepseek-r1:14b")
                if not silent:
                    print(f"\n{BD}{Y}  LOCAL AI FALLBACK ADVISOR{RST}")
                    print(f"{DG}  |- Model   : {W}{local_model}{RST}")
                    print(f"{DG}  |- Backend : {W}Ollama (localhost){RST}")
                    print(f"{DG}  '- Status  : {G}READY (Gemini backup){RST}\n")
                logger.info(f"[GeminiAdvisor] Local Ollama fallback enabled (model={local_model})")
            else:
                self._local_fallback_enabled = False
                if not silent:
                    logger.warning("[GeminiAdvisor] Ollama not available — system will use last known insight")
        except Exception as e:
            self._local_fallback_enabled = False
            if not silent:
                logger.warning(f"[GeminiAdvisor] Local fallback init failed: {e}")

    # ──────────────────────────────────────────────────────────
    #  PUBLIC API
    # ──────────────────────────────────────────────────────────

    def start(self):
        """Start the background advisory loop (Gemini or Local AI fallback)."""
        if not self._enabled and not self._local_fallback_enabled:
            logger.warning("[GeminiAdvisor] Not starting — neither Gemini nor Local AI available")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._advisory_loop, daemon=True, name="GeminiAdvisor"
        )
        self._thread.start()
        source = "Gemini" if self._enabled else "Local AI (Ollama)"
        logger.info(f"[GeminiAdvisor] Background loop started via {source} (interval={ADVISOR_INTERVAL_SEC}s)")

    def stop(self):
        """Gracefully stop the advisory loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[GeminiAdvisor] Stopped.")

    def get_current_insight(self) -> Dict[str, Any]:
        """Return the last Gemini insight (thread-safe)."""
        return dict(self.last_insight)

    def is_trading_allowed(self, direction: str = None) -> tuple:
        """
        Check if trading is allowed per current advisor override.
        Works with both Gemini insights and Local AI fallback insights.
        Returns: (allowed: bool, reason: str)
        """
        # If completely disabled and no local fallback, allow trading freely
        if not self._enabled and not self._local_fallback_enabled:
            return True, "Advisor disabled — no override"

        override = self.last_insight.get("trading_override", "STAY_NEUTRAL")
        source   = self.last_insight.get("_source", "Gemini")

        if override == "AVOID_TRADING" and HARD_OVERRIDE:
            return False, f"🧠 [{source}] AVOID_TRADING: {self.last_insight.get('key_insight', '')}"

        if direction and HARD_OVERRIDE:
            if override == "FORCE_LONG" and direction in ("PUT", "SELL"):
                return False, f"🧠 [{source}] FORCE_LONG override — rejecting {direction}"
            if override == "FORCE_SHORT" and direction in ("CALL", "BUY"):
                return False, f"🧠 [{source}] FORCE_SHORT override — rejecting {direction}"

        return True, "OK"

    def get_confidence_threshold(self, base_threshold: int) -> int:
        """
        Return Gemini's recommended confidence threshold,
        or the base threshold if no override.
        """
        if not self._enabled or not self.last_insight:
            return base_threshold
        override_thresh = self.last_insight.get("confidence_threshold_override")
        if override_thresh and isinstance(override_thresh, int):
            return max(base_threshold, override_thresh)  # always take the stricter one
        return base_threshold

    def get_leverage_recommendation(self, base_leverage: int) -> int:
        """Return Gemini's recommended leverage."""
        if not self._enabled:
            return base_leverage
        rec = self.last_insight.get("leverage_recommendation")
        if rec and isinstance(rec, int):
            return min(base_leverage, rec)  # always take the safer (lower) one
        return base_leverage

    def run_now(self) -> Dict[str, Any]:
        """Manually trigger an immediate advisory cycle (blocking)."""
        return self._run_advisory_cycle()

    # ──────────────────────────────────────────────────────────
    #  INTERNAL — BACKGROUND LOOP
    # ──────────────────────────────────────────────────────────

    def _advisory_loop(self):
        """Main background thread — runs advisory cycle every interval."""
        logger.info("[GeminiAdvisor] Loop started — first call in 30s")
        # Wait 30 seconds before first call (let system warm up)
        time.sleep(30)

        while self._running:
            try:
                insight = self._run_advisory_cycle()
                # Publish to CognitiveBus if available
                if self.bus and insight:
                    self.bus.publish("GEMINI_INSIGHT", "GeminiSupremeAdvisor", insight)
            except Exception as e:
                logger.error(f"[GeminiAdvisor] Advisory cycle error: {e}")

            # Wait for next interval (check every 5s for stop signal)
            elapsed = 0
            while self._running and elapsed < ADVISOR_INTERVAL_SEC:
                time.sleep(5)
                elapsed += 5

    def _run_advisory_cycle(self) -> Dict[str, Any]:
        """Core: collect data -> call Gemini -> parse -> store -> return.
        Auto-retries on 503 (server busy), falls back to alternate model if needed.
        If ALL Gemini options fail, automatically falls back to Local Ollama AI.
        """
        if not hasattr(self, '_client') or not self._client:
            # No Gemini client — try local AI fallback directly
            logger.info("[GeminiAdvisor] No Gemini client — using Local AI advisory.")
            return self._run_local_advisory_cycle()

        snapshot = self._collect_system_snapshot()
        prompt   = self._build_prompt(snapshot)

        # Try primary model, then fallbacks on 503
        models_to_try = [self._model, "gemini-3.6-flash", "gemini-2.5-flash"]
        seen = set()
        ordered_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

        for attempt, model in enumerate(ordered_models):
            for retry in range(3):  # 3 retries per model
                try:
                    logger.info(f"[GeminiAdvisor] Calling {model} (attempt {retry+1})...")
                    response = self._client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=self._types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            temperature=0.3,
                            response_mime_type="application/json",
                        )
                    )

                    raw_text = response.text.strip()
                    if raw_text.startswith("```"):
                        raw_text = raw_text.split("```")[1]
                        if raw_text.startswith("json"):
                            raw_text = raw_text[4:]

                    insight = json.loads(raw_text)
                    self.last_insight = insight
                    self.call_count  += 1
                    self.last_call_time = datetime.now()
                    if model != self._model:
                        logger.info(f"[GeminiAdvisor] Used fallback model: {model}")
                    self._print_insight(insight)
                    return insight

                except json.JSONDecodeError as e:
                    logger.error(f"[GeminiAdvisor] JSON parse error: {e}")
                    return self.last_insight

                except Exception as e:
                    err_str = str(e)
                    if "503" in err_str or "UNAVAILABLE" in err_str:
                        wait = 10 * (retry + 1)
                        logger.warning(f"[GeminiAdvisor] 503 busy, retry {retry+1}/3 in {wait}s...")
                        time.sleep(wait)
                        continue
                    elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        logger.warning(f"[GeminiAdvisor] 429 quota on {model}, trying next model...")
                        break  # try next model
                    else:
                        logger.error(f"[GeminiAdvisor] Gemini call failed: {e}")
                        return self.last_insight

        logger.warning("[GeminiAdvisor] All Gemini models exhausted — switching to Local AI fallback.")
        return self._run_local_advisory_cycle()

    def _run_local_advisory_cycle(self) -> Dict[str, Any]:
        """
        Fallback: Use Ollama local AI (deepseek-r1/qwen2.5) to generate
        the strategic advisory insight when Gemini is unavailable.
        Trading continues uninterrupted with local intelligence.
        """
        if not self._local_fallback_enabled:
            logger.warning("[GeminiAdvisor] Local fallback not available — using last known insight.")
            return self.last_insight

        try:
            from ollama_integration import call_ollama, OLLAMA_BASE_URL
            import requests as _req
            # Quick liveness check before calling
            try:
                _req.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
            except Exception:
                logger.warning("[GeminiAdvisor] Ollama not reachable — using last insight.")
                return self.last_insight

            local_model = os.environ.get("OLLAMA_MODEL", "deepseek-r1:14b")
            snapshot    = self._collect_system_snapshot()
            market      = snapshot.get("market", {})
            trading     = snapshot.get("trading", {})
            oracle      = snapshot.get("oracle", {})

            local_prompt = f"""{SYSTEM_PROMPT}

JARVIS SNAPSHOT (Local AI Advisory — Gemini unavailable):
Timestamp  : {snapshot['timestamp']}
BTC Price  : ${market.get('btc_price', 'unknown')}
5m Trend   : {market.get('trend_5m', 'UNKNOWN')}
Volatility : {market.get('volatility', 'UNKNOWN')}
Daily P&L  : ${trading.get('daily_pnl', 0):+.4f} USDT
Trades     : {trading.get('daily_trades', 0)} | Losses: {trading.get('consec_losses', 0)}
Emergency  : {trading.get('emergency_stop', False)}
Oracle     : {oracle.get('trade_suggestion', 'N/A')} | Hold: {oracle.get('hold_minutes', 0)}m

Respond ONLY in valid JSON. No markdown, no extra text."""

            logger.info(f"[GeminiAdvisor] Calling Local AI ({local_model}) for advisory...")
            ts_start = time.time()
            response, err = call_ollama(local_prompt, model=local_model, timeout=120)
            elapsed = round(time.time() - ts_start, 1)

            if err or not response:
                logger.warning(f"[GeminiAdvisor] Local AI advisory failed: {err}")
                return self.last_insight

            # Clean markdown fences if present
            raw = response.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.lower().startswith("json"):
                    raw = raw[4:]

            # Extract JSON block
            import re as _re
            json_match = _re.search(r'\{.*\}', raw, _re.DOTALL)
            if json_match:
                raw = json_match.group(0)

            insight = json.loads(raw)
            self.last_insight = insight
            self.call_count  += 1
            self.last_call_time = datetime.now()

            # Annotate so we know it came from local AI
            insight["_source"] = f"LocalAI:{local_model}"

            # Pretty print
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"\n{'━'*60}")
            print(f"{BD}{Y}  🤖 LOCAL AI ADVISOR (Gemini fallback)  {DG}[{ts}] Call #{self.call_count} | {elapsed}s{RST}")
            print(f"{'━'*60}")
            print(f"  {DG}Market Regime    :{RST} {BD}{W}{insight.get('market_regime', 'UNKNOWN')}{RST}")
            print(f"  {DG}Risk Level       :{RST} {insight.get('risk_level', 'UNKNOWN')}")
            print(f"  {DG}Trading Override :{RST} {BD}{insight.get('trading_override', 'STAY_NEUTRAL')}{RST}")
            print(f"  {DG}Key Insight      :{RST} {Y}{insight.get('key_insight', '')}{RST}")
            print(f"{'━'*60}\n")
            logger.info(f"[GeminiAdvisor] Local AI advisory complete in {elapsed}s")
            return insight

        except json.JSONDecodeError as e:
            logger.error(f"[GeminiAdvisor] Local AI JSON parse error: {e} | Raw: {response[:200] if response else 'N/A'}")
            return self.last_insight
        except Exception as e:
            logger.error(f"[GeminiAdvisor] Local AI advisory error: {e}")
            return self.last_insight

    # ──────────────────────────────────────────────────────────
    #  INTERNAL — DATA COLLECTION
    # ──────────────────────────────────────────────────────────

    def _collect_system_snapshot(self) -> Dict[str, Any]:
        """Gather ALL Jarvis system data into a single snapshot dict."""
        snapshot = {
            "timestamp":    datetime.now().isoformat(),
            "system":       self._get_system_health(),
            "market":       self._get_market_data(),
            "trading":      self._get_trading_stats(),
            "signals":      self._get_recent_signals(),
            "parts":        self._get_parts_opinions(),      # what each part thinks
            "consensus":    self._get_ollama_consensus(),    # Ollama AI board decision
            "oracle":       self._get_oracle_forecast(),     # 5-min Market Oracle Map
        }
        return snapshot

    def _get_oracle_forecast(self) -> Dict[str, Any]:
        """Fetch latest Market Oracle forecast from bus or singleton."""
        try:
            if self.bus and hasattr(self.bus, "get_latest_oracle_forecast"):
                fc = self.bus.get_latest_oracle_forecast()
                if fc:
                    return fc
        except Exception:
            pass

        try:
            from jarvis_market_oracle import get_oracle
            oracle = get_oracle()
            if oracle:
                return oracle.get_latest_forecast()
        except Exception:
            pass

        path = os.path.join("logs", "jarvis_market_map.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        return {"status": "No Oracle forecast available yet"}

    def _get_system_health(self) -> Dict:
        try:
            if self.bus:
                return self.bus.get_system_health()
        except Exception:
            pass
        return {"status": "unknown"}

    def _get_market_data(self) -> Dict:
        """Get current BTC market data."""
        try:
            from binance_data import get_btc_price_binance, get_ohlcv_binance
            price = get_btc_price_binance()
            ohlcv = get_ohlcv_binance("BTCUSDT", "5m", limit=20)
            if ohlcv is not None and not ohlcv.empty:
                closes = ohlcv['close'].tolist()[-10:]
                highs  = ohlcv['high'].tolist()[-5:]
                lows   = ohlcv['low'].tolist()[-5:]
                # Simple trend: last close vs 10 closes ago
                trend = "UP" if closes[-1] > closes[0] else "DOWN"
                atr_approx = sum(h - l for h, l in zip(highs, lows)) / len(highs)
                volatility = "HIGH" if atr_approx > price * 0.005 else "MEDIUM" if atr_approx > price * 0.002 else "LOW"
                return {
                    "btc_price": round(price, 2),
                    "trend_5m": trend,
                    "volatility": volatility,
                    "atr_approx": round(atr_approx, 2),
                    "recent_closes": [round(c, 2) for c in closes]
                }
            return {"btc_price": round(price, 2), "trend_5m": "UNKNOWN", "volatility": "UNKNOWN"}
        except Exception as e:
            return {"btc_price": "unknown", "error": str(e)}

    def _get_trading_stats(self) -> Dict:
        """Get current trading session stats from trader reference."""
        if not self.trader:
            return {"status": "no_trader_ref"}
        try:
            return {
                "daily_pnl":         round(getattr(self.trader, 'daily_pnl', 0), 4),
                "daily_trades":      getattr(self.trader, 'daily_trades', 0),
                "consec_losses":     getattr(self.trader, 'consec_losses', 0),
                "open_positions":    len(getattr(self.trader, 'open_positions', [])),
                "emergency_stop":    getattr(self.trader, 'emergency_stop', False),
                "is_enabled":        getattr(self.trader, 'is_enabled', False),
                "current_leverage":  int(os.environ.get("JARVIS_LEVERAGE", "100")),
                "min_confidence":    int(os.environ.get("JARVIS_MIN_CONFIDENCE", "75")),
                "max_risk_usdt":     float(os.environ.get("JARVIS_MAX_RISK_USDT", "0.10")),
                "closed_today_count": len(getattr(self.trader, 'closed_today', [])),
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_recent_signals(self) -> list:
        """Get last 10 signals from CognitiveBus logs."""
        signals = []
        try:
            log_path = os.path.join("logs", "jarvis_thoughts.log")
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                signal_lines = [l for l in lines[-500:] if "[SIGNALS]" in l]
                signals = [l.strip() for l in signal_lines[-10:]]
        except Exception:
            pass
        return signals

    def _get_parts_opinions(self) -> Dict[str, Any]:
        """
        Collect latest THOUGHTS from each Part (part1-part12) via CognitiveBus buffer.
        Returns dict: {part_name: latest_opinion_text}
        """
        parts_data = {}
        try:
            if self.bus and hasattr(self.bus, 'get_latest_by_sender'):
                latest = self.bus.get_latest_by_sender()
                for sender, msg in latest.items():
                    # Only include Part messages
                    if sender.startswith('Part') or 'part' in sender.lower():
                        payload = msg.get('payload', '')
                        if isinstance(payload, dict):
                            payload = json.dumps(payload)
                        # Trim to 300 chars per part
                        parts_data[sender] = str(payload)[:300]
        except Exception as e:
            parts_data['error'] = str(e)

        # Also read recent 20 lines from thoughts log for extra context
        try:
            if not parts_data:  # fallback if bus buffer empty
                log_path = os.path.join("logs", "jarvis_thoughts.log")
                if os.path.exists(log_path):
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                    thought_lines = [l for l in lines[-1000:] if "[THOUGHTS]" in l]
                    # Group by part name
                    for line in thought_lines[-30:]:
                        try:
                            parts = line.split(']')
                            if len(parts) >= 3:
                                sender = parts[2].strip().lstrip('[')
                                content = ']'.join(parts[3:]).strip()[:250]
                                parts_data[sender] = content
                        except Exception:
                            pass
        except Exception:
            pass

        return parts_data if parts_data else {"status": "No part opinions available yet"}

    def _get_ollama_consensus(self) -> Dict[str, Any]:
        """
        Read the last Multi-AI consensus result from logs.
        Captures: chairman decision, analyst/validator/risk opinions, agreement %.
        """
        consensus = {}
        try:
            log_path = os.path.join("logs", "jarvis_thoughts.log")
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                last_lines = lines[-2000:]

                # Look for consensus result lines
                for line in reversed(last_lines):
                    if 'CONSENSUS_EXECUTE' in line or 'CONSENSUS_REJECT' in line:
                        consensus['last_verdict'] = (
                            'CONSENSUS_EXECUTE' if 'CONSENSUS_EXECUTE' in line
                            else 'CONSENSUS_REJECT'
                        )
                        consensus['verdict_log'] = line.strip()[:300]
                        break

                # Grab last Analyst, Validator, Risk Officer opinions
                for keyword, key in [
                    ('Analyst:', 'analyst'),
                    ('Validator:', 'validator'),
                    ('Risk Officer:', 'risk_officer'),
                    ('Chairman:', 'chairman'),
                    ('agreement_pct', 'agreement'),
                ]:
                    for line in reversed(last_lines):
                        if keyword in line:
                            consensus[key] = line.strip()[-250:]
                            break

        except Exception as e:
            consensus['error'] = str(e)

        return consensus if consensus else {"status": "No consensus data yet"}

    # ──────────────────────────────────────────────────────────
    #  INTERNAL — PROMPT BUILDING
    # ──────────────────────────────────────────────────────────

    def _build_prompt(self, snapshot: Dict) -> str:
        trading   = snapshot.get("trading", {})
        market    = snapshot.get("market", {})
        system    = snapshot.get("system", {})
        signals   = snapshot.get("signals", [])
        parts     = snapshot.get("parts", {})
        consensus = snapshot.get("consensus", {})
        oracle    = snapshot.get("oracle", {})

        # Format Oracle summary
        oracle_summary = "No Oracle forecast available"
        if oracle and "status" not in oracle:
            tf5 = oracle.get("5min", {})
            tf30 = oracle.get("30min", {})
            tf1h = oracle.get("1hour", {})
            tf4h = oracle.get("4hour", {})
            opt = oracle.get("options_intel", {})
            oracle_summary = (
                f"Trade Suggestion: {oracle.get('trade_suggestion', 'WAIT')} | Hold: {oracle.get('hold_minutes', 15)}m\n"
                f"  5m : {tf5.get('direction')} ({tf5.get('confidence')}%) Range: {tf5.get('range')}\n"
                f"  30m: {tf30.get('direction')} ({tf30.get('confidence')}%) Range: {tf30.get('range')}\n"
                f"  1h : {tf1h.get('direction')} ({tf1h.get('confidence')}%) Range: {tf1h.get('range')}\n"
                f"  4h : {tf4h.get('direction')} ({tf4h.get('confidence')}%) Range: {tf4h.get('range')}\n"
                f"  Options: Max Pain ${opt.get('max_pain', 0):,}, PCR {opt.get('pcr', 0):.2f}, Gamma Walls Call: ${opt.get('gamma_wall_call', 0):,} / Put: ${opt.get('gamma_wall_put', 0):,}\n"
                f"  Oracle Says: \"{oracle.get('gemini_summary', '')}\""
            )

        # Format parts opinions section
        parts_section = "No part opinions available"
        if parts and "status" not in parts:
            parts_lines = []
            for p, opinion in parts.items():
                parts_lines.append(f"  {p}: {opinion}")
            parts_section = "\n".join(parts_lines)

        # Format Ollama consensus section
        consensus_section = "No consensus data yet"
        if consensus and "status" not in consensus:
            c_lines = [f"  {k}: {v}" for k, v in consensus.items()]
            consensus_section = "\n".join(c_lines)

        prompt = f"""JARVIS 10-MINUTE FULL SYSTEM SNAPSHOT -- {snapshot['timestamp']}

-- MARKET DATA ---------------------------------------------------
BTC Price     : ${market.get('btc_price', 'unknown')}
5m Trend      : {market.get('trend_5m', 'unknown')}
Volatility    : {market.get('volatility', 'unknown')}
ATR (approx)  : ${market.get('atr_approx', 'unknown')}
Recent Closes : {market.get('recent_closes', [])}

━━ 5-MINUTE MARKET ORACLE FORECAST ━━━━━━━━━━━━━━━━━━━
{oracle_summary}

━━ TRADING SESSION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Daily P&L         : ${trading.get('daily_pnl', 0):+.4f} USDT
Trades Today      : {trading.get('daily_trades', 0)}
Closed Today      : {trading.get('closed_today_count', 0)}
Consecutive Losses: {trading.get('consec_losses', 0)}
Open Positions    : {trading.get('open_positions', 0)}
Emergency Stop    : {trading.get('emergency_stop', False)}
Current Leverage  : {trading.get('current_leverage', 100)}x
Min Confidence    : {trading.get('min_confidence', 75)}%
Max Risk/Trade    : ${trading.get('max_risk_usdt', 0.10)} USDT

━━ SYSTEM HEALTH ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{json.dumps(system, indent=2)}

━━ RECENT SIGNALS (last 10) ━━━━━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(signals) if signals else 'No signal logs available'}

━━ PREVIOUS GEMINI INSIGHT ━━━━━━━━━━━━━━━━━━━━━━━━━━
{json.dumps(self.last_insight, indent=2) if self.call_count > 0 else 'First call — no previous insight'}

Analyze this snapshot and provide your strategic JSON response."""

        return prompt

    # ──────────────────────────────────────────────────────────
    #  INTERNAL — DISPLAY + DEFAULTS
    # ──────────────────────────────────────────────────────────

    def _print_insight(self, insight: Dict):
        """Pretty-print the Gemini insight to console."""
        override  = insight.get("trading_override", "STAY_NEUTRAL")
        risk      = insight.get("risk_level", "UNKNOWN")
        regime    = insight.get("market_regime", "UNKNOWN")
        suit      = insight.get("scalping_suitability", 0)
        key       = insight.get("key_insight", "")
        conf_thr  = insight.get("confidence_threshold_override", "—")
        lev_rec   = insight.get("leverage_recommendation", "—")

        override_color = {
            "AVOID_TRADING": R,
            "FORCE_LONG":    G,
            "FORCE_SHORT":   R,
            "STAY_NEUTRAL":  Y,
        }.get(override, W)

        risk_color = {"LOW": G, "MEDIUM": Y, "HIGH": R, "EXTREME": R+BD}.get(risk, W)

        ts = datetime.now().strftime("%H:%M:%S")
        print(f"\n{'━'*60}")
        print(f"{BD}{C}  🧠 GEMINI SUPREME ADVISOR  {DG}[{ts}] Call #{self.call_count}{RST}")
        print(f"{'━'*60}")
        print(f"  {DG}Market Regime     :{RST} {BD}{W}{regime}{RST}")
        print(f"  {DG}Scalp Suitability :{RST} {suit}/100")
        print(f"  {DG}Risk Level        :{RST} {risk_color}{BD}{risk}{RST}")
        print(f"  {DG}Trading Override  :{RST} {override_color}{BD}{override}{RST}{'  ⚠ HARD' if HARD_OVERRIDE and override != 'STAY_NEUTRAL' else ''}")
        print(f"  {DG}Conf. Threshold   :{RST} {conf_thr}%")
        print(f"  {DG}Leverage Rec.     :{RST} {lev_rec}x")
        print(f"  {DG}Key Insight       :{RST} {Y}{key}{RST}")
        print(f"{'━'*60}\n")

    def _default_insight(self) -> Dict[str, Any]:
        """Safe default insight (STAY_NEUTRAL) used before first Gemini call."""
        return {
            "market_regime": "UNKNOWN",
            "scalping_suitability": 50,
            "confidence_threshold_override": int(os.environ.get("JARVIS_MIN_CONFIDENCE", "75")),
            "leverage_recommendation": int(os.environ.get("JARVIS_LEVERAGE", "100")),
            "trading_override": "STAY_NEUTRAL",
            "risk_level": "MEDIUM",
            "key_insight": "Gemini advisor initializing — using default settings",
            "reasoning": "No Gemini data yet",
            "next_check_minutes": 10
        }


# ── Singleton for import ──────────────────────────────────────
_advisor_instance: Optional[GeminiSupremeAdvisor] = None

def get_advisor() -> Optional[GeminiSupremeAdvisor]:
    """Get the global advisor singleton."""
    return _advisor_instance

def init_advisor(bus=None, trader_ref=None) -> GeminiSupremeAdvisor:
    """Initialize and start the global Gemini Supreme Advisor."""
    global _advisor_instance
    _advisor_instance = GeminiSupremeAdvisor(bus=bus, trader_ref=trader_ref)
    _advisor_instance.start()
    return _advisor_instance


# ── Standalone test ───────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    print("Testing Gemini Supreme Advisor...")
    advisor = GeminiSupremeAdvisor()
    if advisor._enabled and hasattr(advisor, '_client') and advisor._client:
        print("\nRunning single advisory cycle (may take 10-30 seconds)...")
        insight = advisor.run_now()
        print("\n[OK] Raw Insight:")
        print(json.dumps(insight, indent=2))
        print(f"\n[OK] Trading allowed (CALL): {advisor.is_trading_allowed('CALL')}")
        print(f"[OK] Confidence threshold : {advisor.get_confidence_threshold(75)}")
        print(f"[OK] Leverage rec.        : {advisor.get_leverage_recommendation(100)}")
    else:
        print("[ERROR] Advisor not enabled -- check GEMINI_API_KEY in .env")

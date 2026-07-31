# jarvis_neural_cortex.py
# Jarvis Neural Cortex - Continuous AI Brain with Memory
# Replaces: ai_chain_brain.py + _get_deepseek_validation()
# Uses: Ollama /api/chat - rolling 20-message history for live market memory

import os, re, json, logging, requests
from datetime import datetime
from typing import Dict, Optional, List

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "deepseek-r1:14b")


class JarvisNeuralCortex:
    """
    Single AI brain: all 12 GPU parts -> ONE Ollama chat call -> CALL/PUT/NO_TRADE
    Uses rolling 20-message history for market memory.

    Backward-compatible with old ai_chain_brain API.
    """

    SYSTEM_PROMPT = (
        "You are JARVIS, an elite BTC options trading AI.\n"
        "Every minute you receive live data from 12 specialized GPU analysis engines.\n"
        "You have MEMORY of past minutes -- use it to track momentum shifts and avoid fakeouts.\n\n"
        "YOUR 12 ENGINE ROLES:\n"
        "1. BREAKOUT (part1): Detects price breaking support/resistance levels (13 sub-brains)\n"
        "2. ZONE (part2): Supply/Demand zone proximity\n"
        "3. PSYCHOLOGY (part3): Candle pattern analysis (hammer, engulfing, doji)\n"
        "4. VOLUME (part4): Volume profile vs 20-bar average\n"
        "5. ML (part5): LSTM/Transformer neural network momentum predictions\n"
        "6. TREND (part6): EMA 8/21/50 alignment\n"
        "7. VOLATILITY (part7): ATR regime (is it safe to trade?)\n"
        "8. STRUCTURE (part8): Market structure - Higher Highs/Lows\n"
        "9. ORDERFLOW (part9): Buy vs Sell volume delta\n"
        "10. CANDLE_STATS (part10): Last 10 candle run analysis\n"
        "11. FUSION (part11): Mathematical vote counting\n"
        "12. CONFIDENCE (part12): Signal agreement strength\n\n"
        "DECISION RULES:\n"
        "- 8+ engines agree same direction: Strong signal (70-90%)\n"
        "- 6-7 engines agree: Moderate signal (50-70%)\n"
        "- 5 or fewer agree: NO_TRADE\n"
        "- TREND (6) must align for high confidence\n"
        "- VOLATILITY (7) HIGH: reduce confidence 20%, prefer NO_TRADE\n"
        "- VOLUME (4) must confirm price move\n"
        "- Track momentum BUILDING in memory (increasing agreement = stronger signal)\n\n"
        'RESPONSE FORMAT - Reply ONLY in valid JSON:\n'
        '{"signal": "CALL", "confidence": 75, "rationale": "9/12 bullish, volume confirming", "risk": "LOW"}\n'
        'signal: exactly "CALL", "PUT", or "NO_TRADE"\n'
        "confidence: 0-100 integer\n"
        "rationale: max 40 words\n"
        'risk: "LOW", "MEDIUM", or "HIGH"'
    )

    def __init__(self):
        self.chat_history: List[Dict] = []
        self.max_history_pairs = 20
        self.ollama_url = OLLAMA_BASE_URL
        self.model = OLLAMA_MODEL
        self._last_result: Optional[Dict] = None
        self._call_count = 0
        self._error_count = 0
        logger.info(f"[CORTEX] Initialized -- model={self.model} memory={self.max_history_pairs}min")

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    def analyze(self,
                part_results: Dict,
                current_price: float,
                market_context: Optional[Dict] = None,
                quantum_data: Optional[Dict] = None,
                mtf_context: Optional[Dict] = None) -> Dict:
        self._call_count += 1
        try:
            report = self._build_market_report(part_results, current_price, market_context, quantum_data, mtf_context)
            self.chat_history.append({"role": "user", "content": report})
            raw_response = self._call_ollama_chat()
            self.chat_history.append({"role": "assistant", "content": raw_response or "{}"})
            max_messages = self.max_history_pairs * 2
            if len(self.chat_history) > max_messages:
                self.chat_history = self.chat_history[-max_messages:]
            result = self._parse_decision(raw_response, part_results)
            self._last_result = result
            logger.info(f"[CORTEX] Decision: {result['signal']} | Conf: {result['confidence']}% | {result['rationale'][:60]}")
            return result
        except Exception as e:
            self._error_count += 1
            logger.error(f"[CORTEX] analyze() error: {e}")
            return self._fallback_from_math(part_results)

    def reset_memory(self):
        self.chat_history = []
        logger.info("[CORTEX] Memory reset.")

    def get_memory_length(self) -> int:
        return len(self.chat_history) // 2

    # -------------------------------------------------------------------------
    # MARKET REPORT BUILDER
    # -------------------------------------------------------------------------

    def _build_market_report(self, part_results, price, market_context, quantum_data, mtf_context) -> str:
        now = datetime.now().strftime('%H:%M:%S')
        PART_DISPLAY = {
            'part1_breakout':      '1.BREAKOUT',
            'part2_zone':          '2.ZONE',
            'part3_psychology':    '3.PSYCH',
            'part4_volume':        '4.VOLUME',
            'part5_ml':            '5.ML',
            'part6_trend':         '6.TREND',
            'part7_volatility':    '7.VOLATILITY',
            'part8_structure':     '8.STRUCTURE',
            'part9_orderflow':     '9.ORDERFLOW',
            'part10_candlestats':  '10.CANDLE',
            'part14_options_chain':'14.OPTIONS',
        }
        lines = []
        buy_count = sell_count = neutral_count = 0
        for key, label in PART_DISPLAY.items():
            res = part_results.get(key, {})
            sig = res.get('signal', 0)
            thought = str(res.get('thought', 'N/A'))[:70]
            em = '[B]' if sig > 0 else ('[S]' if sig < 0 else '[N]')
            direction = 'BULL' if sig > 0 else ('BEAR' if sig < 0 else 'NEUT')
            if sig > 0: buy_count += 1
            elif sig < 0: sell_count += 1
            else: neutral_count += 1
            lines.append(f"  {em} {label}: {direction} | {thought}")

        fusion = part_results.get('part11_fusion', {})
        conf_part = part_results.get('part12_confidence', {})
        math_conf = conf_part.get('confidence', 0)
        fusion_thought = fusion.get('thought', 'N/A')[:80]
        math_dir = 'BUY' if fusion.get('signal', 0) > 0 else ('SELL' if fusion.get('signal', 0) < 0 else 'NEUTRAL')

        q_line = ""
        if quantum_data and isinstance(quantum_data, dict):
            q_sig = quantum_data.get('signal', 0)
            q_thought = str(quantum_data.get('thought', ''))[:60]
            q_dir = 'BULL' if q_sig > 0 else ('BEAR' if q_sig < 0 else 'NEUT')
            q_line = f"\nQUANTUM V5: {q_dir} | {q_thought}"

        mtf_line = ""
        if mtf_context and isinstance(mtf_context, dict):
            tf_parts = []
            for tf, analysis in list(mtf_context.items())[:5]:
                tf_dir = analysis.get('direction', 0)
                tf_label = 'UP' if tf_dir > 0 else ('DN' if tf_dir < 0 else '--')
                tf_parts.append(f"{tf}:{tf_label}")
            mtf_line = f"\nMTF: {' | '.join(tf_parts)}"

        memory_hint = ""
        if len(self.chat_history) > 2:
            memory_hint = f"\n(You have {len(self.chat_history)//2} minutes of memory -- use it!)"

        parts_block = "\n".join(lines)
        report = (
            f"\n{now} | BTC: ${price:,.2f} | Call #{self._call_count}\n"
            f"\n=== 12 GPU ENGINE VERDICTS ===\n{parts_block}\n"
            f"\n=== VOTE SUMMARY ===\n"
            f"Votes: {buy_count} BULL / {sell_count} BEAR / {neutral_count} NEUTRAL\n"
            f"Fusion Math: {math_dir} | {fusion_thought}\n"
            f"Math Confidence: {math_conf}%"
            + q_line + mtf_line + memory_hint +
            f"\n\n=== YOUR DECISION ===\n"
            f"Analyze all data + your memory. Reply JSON only:\n"
            f'{{"signal":"CALL/PUT/NO_TRADE","confidence":0-100,"rationale":"...","risk":"LOW/MEDIUM/HIGH"}}'
        )
        return report.strip()

    # -------------------------------------------------------------------------
    # OLLAMA CHAT API (With Memory)
    # -------------------------------------------------------------------------

    def _call_ollama_chat(self) -> Optional[str]:
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        messages.extend(self.chat_history)
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": False,
                      "options": {"temperature": 0.1}},
                timeout=120  # increased to 120s for 14b
            )
            if resp.status_code == 200:
                return resp.json().get("message", {}).get("content", "").strip()
            logger.error(f"[CORTEX] Ollama HTTP {resp.status_code}: {resp.text[:100]}")
            return None
        except requests.exceptions.ConnectionError:
            logger.warning("[CORTEX] Ollama not reachable -- is GPU server running?")
            return None
        except requests.exceptions.Timeout:
            logger.warning("[CORTEX] Ollama timeout (>90s)")
            return None
        except Exception as e:
            logger.error(f"[CORTEX] Chat call error: {e}")
            return None

    # -------------------------------------------------------------------------
    # JSON RESPONSE PARSER
    # -------------------------------------------------------------------------

    def _parse_decision(self, raw: Optional[str], part_results: Dict) -> Dict:
        if not raw:
            return self._fallback_from_math(part_results, ai_online=False)
        try:
            data = json.loads(raw)
            return self._normalise(data)
        except json.JSONDecodeError:
            pass
        for pattern in [r'```json\s*(\{.*?\})\s*```', r'(\{"signal".*?\})', r'(\{.*?"signal".*?\})', r'(\{.*?\})']:
            m = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
            if m:
                try:
                    data = json.loads(m.group(1))
                    return self._normalise(data)
                except Exception:
                    continue
        logger.warning(f"[CORTEX] Could not parse JSON from: {raw[:100]}")
        return self._fallback_from_math(part_results, ai_online=True)

    def _normalise(self, data: Dict) -> Dict:
        raw_sig = str(data.get('signal', data.get('bias', 'NO_TRADE'))).upper()
        if raw_sig in ('CALL', 'BUY', 'BULLISH', 'LONG'):
            signal = 'CALL'
        elif raw_sig in ('PUT', 'SELL', 'BEARISH', 'SHORT'):
            signal = 'PUT'
        else:
            signal = 'NO_TRADE'
        try:
            conf = max(0, min(100, int(data.get('confidence', 0))))
        except Exception:
            conf = 0
        rationale = str(data.get('rationale', data.get('reasoning', 'AI response'))).strip()[:120]
        risk = str(data.get('risk', 'MEDIUM')).upper()
        if risk not in ('LOW', 'MEDIUM', 'HIGH'):
            risk = 'MEDIUM'
        return {'signal': signal, 'bias': signal.replace('_', '-'), 'confidence': conf,
                'rationale': rationale, 'reasoning': rationale, 'risk': risk, 'ai_online': True}

    def _fallback_from_math(self, part_results: Dict, ai_online: bool = False) -> Dict:
        try:
            fusion = part_results.get('part11_fusion', {})
            conf_part = part_results.get('part12_confidence', {})
            math_sig = fusion.get('signal', 0)
            math_conf = conf_part.get('confidence', 10)
            signal = 'CALL' if math_sig > 0 else ('PUT' if math_sig < 0 else 'NO_TRADE')
            source = "Ollama offline -- math fallback" if not ai_online else "AI parse error -- math fallback"
            return {'signal': signal, 'bias': signal.replace('_', '-'), 'confidence': math_conf,
                    'rationale': source, 'reasoning': source, 'risk': 'MEDIUM', 'ai_online': False}
        except Exception:
            return {'signal': 'NO_TRADE', 'bias': 'NO-TRADE', 'confidence': 0,
                    'rationale': 'Critical AI error', 'reasoning': 'Critical AI error',
                    'risk': 'HIGH', 'ai_online': False}

    # -------------------------------------------------------------------------
    # BACKWARD COMPAT SHIMS (for old ai_chain_brain references)
    # -------------------------------------------------------------------------

    def analyze_holistic_context(self, prompt: str, system_voice: str = "Assistant"):
        try:
            resp = requests.post(f"{self.ollama_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "format": "json"}, timeout=90)
            if resp.status_code == 200:
                return resp.json().get("response", "").strip(), None
            return "", f"HTTP {resp.status_code}"
        except requests.exceptions.ConnectionError:
            return "", "Ollama not reachable"
        except Exception as e:
            return "", str(e)

    @property
    def part_results(self):
        return {}

    def start_sequential_loop(self, jarvis_engine):
        logger.info("[CORTEX] Cortex is synchronous -- no background loop required.")

    def stop(self):
        logger.info("[CORTEX] Stopped.")

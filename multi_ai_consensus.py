#!/usr/bin/env python3
"""
JARVIS AI Round-Table Consensus Engine (Multi-LLM Committee)
3 Models analyze independently -> DeepSeek Chairman synthesizes final verdict
"""

import os
import logging
from typing import Dict, Any

logger = logging.getLogger("AIConsensus")

# 3 Board Members - configurable from .env
MODEL_ANALYST   = os.environ.get("MODEL_ANALYST",   "deepseek-r1:70b")
MODEL_VALIDATOR = os.environ.get("MODEL_VALIDATOR", "llama3.1:70b")
MODEL_RISK      = os.environ.get("MODEL_RISK",      "qwen2.5:32b")


def _call_model(prompt: str, model: str, timeout: int = 90) -> str:
    """Call a specific Ollama model safely"""
    try:
        from ollama_integration import call_ollama
        response, err = call_ollama(prompt, model=model, timeout=timeout)
        if response and not err:
            return response.strip()
        return f"[Unavailable: {err}]"
    except Exception as e:
        return f"[Error: {e}]"


def run_ai_roundtable(market_context: Dict[str, Any], signal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run 3-Model AI Round-Table Committee:

    Round 1: 3 experts analyze INDEPENDENTLY
      - DeepSeek (Technical Analyst)
      - Llama    (Market Validator)
      - Qwen     (Risk Officer)

    Round 2: DeepSeek Chairman reads ALL 3 opinions -> Final Verdict
    """
    logger.info("AI Board Meeting started...")

    base_context = f"""
Symbol: {market_context.get('symbol', 'BTC/USDT')}
Price:  ${market_context.get('current_price', 0)}
Trend:  {market_context.get('trend', 'NEUTRAL')}
Volatility: {market_context.get('volatility', 'MEDIUM')}

Trade Signal:
- Direction:  {signal_data.get('direction', 'NO-TRADE')}
- Confidence: {signal_data.get('confidence', 0)}%
- Pattern:    {signal_data.get('pattern', 'NONE')}
"""

    # ── ROUND 1: Independent Expert Opinions ──────────────────────────
    print(f"\n🏛️ [AI BOARD] Round 1 - Collecting Expert Opinions...")

    opinion_analyst = _call_model(
        base_context + "\nYou are the Technical Analyst AI. Evaluate the chart setup only. "
        "Give verdict: [APPROVE] or [REJECT] with 1 short reason.",
        model=MODEL_ANALYST, timeout=90
    )
    print(f"  📊 Analyst ({MODEL_ANALYST}): {opinion_analyst}")

    opinion_validator = _call_model(
        base_context + "\nYou are the Market Structure Validator AI. Check for traps, fakeouts, and trend conflicts. "
        "Give verdict: [APPROVE] or [REJECT] with 1 short reason.",
        model=MODEL_VALIDATOR, timeout=90
    )
    print(f"  🔍 Validator ({MODEL_VALIDATOR}): {opinion_validator}")

    opinion_risk = _call_model(
        base_context + "\nYou are the Chief Risk Officer AI. Evaluate risk/reward ratio and position safety. "
        "Give verdict: [APPROVE] or [REJECT] with 1 short reason.",
        model=MODEL_RISK, timeout=90
    )
    print(f"  ⚖️ Risk Officer ({MODEL_RISK}): {opinion_risk}")

    # ── ROUND 2: Chairman Synthesis ────────────────────────────────────
    print(f"\n🏛️ [AI BOARD] Round 2 - Chairman Synthesis...")

    chairman_prompt = f"""You are the Chairman of the AI Investment Board. Your job is to synthesize 3 expert opinions into a final executive decision.

Market & Signal:
{base_context}

Board Expert Opinions:
1. Technical Analyst ({MODEL_ANALYST}): {opinion_analyst}
2. Market Validator  ({MODEL_VALIDATOR}): {opinion_validator}
3. Risk Officer      ({MODEL_RISK}): {opinion_risk}

Instructions:
- If 2 or 3 experts APPROVE → issue [CONSENSUS_EXECUTE]
- If 2 or 3 experts REJECT → issue [CONSENSUS_REJECT]
- Start your response with EXACTLY ONE of: [CONSENSUS_EXECUTE] or [CONSENSUS_REJECT]
- Follow with a 1-sentence board summary.
"""

    chairman_verdict = _call_model(chairman_prompt, model=MODEL_ANALYST, timeout=120)

    # Parse verdict
    approved = "[CONSENSUS_EXECUTE]" in chairman_verdict.upper()
    final_verdict = "CONSENSUS_EXECUTE" if approved else "CONSENSUS_REJECT"

    # Also count votes as fallback
    approve_votes = sum(1 for op in [opinion_analyst, opinion_validator, opinion_risk]
                        if "[APPROVE]" in op.upper())
    if approve_votes >= 2 and not approved:
        approved = True
        final_verdict = "CONSENSUS_EXECUTE"

    result = {
        "approved": approved,
        "final_verdict": final_verdict,
        "chairman_summary": chairman_verdict,
        "approve_votes": approve_votes,
        "opinions": {
            "analyst":      opinion_analyst,
            "validator":    opinion_validator,
            "risk_officer": opinion_risk
        }
    }

    print(f"\n👑 [JARVIS SUPREME COMMANDER] Board Verdict: [{final_verdict}]")
    print(f"  ├─ Analyst ({MODEL_ANALYST}):    {opinion_analyst[:80]}...")
    print(f"  ├─ Validator ({MODEL_VALIDATOR}): {opinion_validator[:80]}...")
    print(f"  ├─ Risk Officer ({MODEL_RISK}):  {opinion_risk[:80]}...")
    print(f"  └─ Chairman:   {chairman_verdict[:100]}...\n")

    return result


if __name__ == "__main__":
    # Quick standalone test
    test_market = {"symbol": "BTC/USDT", "current_price": 64500, "trend": "BULLISH", "volatility": "LOW"}
    test_signal = {"direction": "CALL", "confidence": 82, "pattern": "Bullish Engulfing + EMA Cross"}
    result = run_ai_roundtable(test_market, test_signal)
    print("\nFinal Result:", result["final_verdict"], "| Approve Votes:", result["approve_votes"])

#!/usr/bin/env python3
"""
JARVIS AI Round-Table Consensus Engine (Multi-LLM Committee)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Updated to use Layer 2 Specialist Pool (Parallel Execution).
Reduces consensus time from ~4.5 minutes to ~1.5 minutes.
"""

import os
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger("AIConsensus")

# Import the new Pipeline Specialist Pool
from jarvis_specialist_pool import SpecialistPool

# Global pool instance so we don't recreate threads every time
_specialist_pool = SpecialistPool(max_workers=3)

def run_ai_roundtable(market_context: Dict[str, Any], signal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run 3-Model AI Round-Table Committee in PARALLEL.
    
    Acts as a bridge for legacy parts: takes their raw context/signal,
    wraps it in a Smart Context Packet, and feeds it to the Specialist Pool.
    Also includes Gemini Supreme Advisor insight if available.
    """
    logger.info("AI Board Meeting (Parallel Pipeline) started...")

    # ── Check Gemini Supreme Advisor override ──────────────────
    gemini_context = "No Gemini advisor data available"
    gemini_override = "STAY_NEUTRAL"
    try:
        from gemini_supreme_advisor import get_advisor
        advisor = get_advisor()
        if advisor:
            insight = advisor.get_current_insight()
            gemini_override = insight.get("trading_override", "STAY_NEUTRAL")
            gemini_context = (
                f"Gemini Supreme Advisor says: {insight.get('key_insight', 'N/A')} | "
                f"Override={gemini_override} | Risk={insight.get('risk_level', 'UNKNOWN')} | "
                f"Market={insight.get('market_regime', 'UNKNOWN')} | "
                f"Conf.Threshold={insight.get('confidence_threshold_override', 'N/A')}%"
            )
    except Exception:
        pass

    # ── Convert legacy inputs into Smart Context Packet format ──
    smart_packet = {
        "timestamp": datetime.now().isoformat(),
        "system_health": "UNKNOWN", # Legacy parts don't track this directly
        "recent_error_count": 0,
        "gemini_supreme_advisor": gemini_context,
        "market_context": {
            "symbol": market_context.get('symbol', 'BTC/USDT'),
            "last_known_price": market_context.get('current_price', 0),
            "volatility": market_context.get('volatility', 'MEDIUM'),
            "dominant_short_term_trend": market_context.get('trend', 'NEUTRAL')
        },
        "trigger_event": "LEGACY_SIGNAL",
        "active_signals": [
            {
                "direction": signal_data.get('direction', 'NO-TRADE'),
                "confidence": signal_data.get('confidence', 0),
                "pattern": signal_data.get('pattern', 'NONE')
            }
        ]
    }

    print(f"\n\U0001f3db\ufe0f [AI BOARD] Phase 1 - Parallel Specialists Analyzing...")
    if gemini_override != "STAY_NEUTRAL":
        print(f"  \U0001f9e0 Gemini Context: {gemini_context[:80]}...")
    
    # ── Execute all 3 Specialists IN PARALLEL ──
    opinions = _specialist_pool.run_parallel_evaluation(smart_packet)
    
    print(f"  \U0001f4ca Analyst:       {opinions.get('analyst', 'N/A')[:80]}...")
    print(f"  \U0001f50d Validator:     {opinions.get('validator', 'N/A')[:80]}...")
    print(f"  \u2696\ufe0f Risk Officer:  {opinions.get('risk_officer', 'N/A')[:80]}...")

    # ── Chairman Synthesis ──
    print(f"\n\U0001f3db\ufe0f [AI BOARD] Phase 2 - Chairman Synthesis...")
    
    result = _specialist_pool.synthesize_chairman_decision(smart_packet, opinions)

    print(f"\n\U0001f451 [JARVIS SUPREME COMMANDER] Board Verdict: [{result['final_verdict']}]")
    print(f"  └─ Chairman:   {result['chairman_summary'][:100]}...\n")

    return result

if __name__ == "__main__":
    # Quick standalone test
    test_market = {"symbol": "BTC/USDT", "current_price": 64500, "trend": "BULLISH", "volatility": "LOW"}
    test_signal = {"direction": "CALL", "confidence": 82, "pattern": "Bullish Engulfing + EMA Cross"}
    
    start_time = datetime.now()
    result = run_ai_roundtable(test_market, test_signal)
    end_time = datetime.now()
    
    print("\nFinal Result:", result["final_verdict"], "| Approve Votes:", result["approve_votes"])
    print(f"Time Taken (Parallel): {(end_time - start_time).total_seconds():.2f} seconds")
    
    # Clean up pool threads on exit
    _specialist_pool.shutdown()

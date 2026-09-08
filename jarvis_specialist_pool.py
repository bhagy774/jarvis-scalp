#!/usr/bin/env python3
"""
JARVIS Pipeline Architecture - Layer 2: Specialist AI Pool
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Executes 3 specialist AI models in PARALLEL using a thread pool.
Consumes the 'Smart Context Packet' from the Watcher AI.

VRAM Layout (RTX 3090 24GB) — Option 1: Weight Sharing
  deepseek-r1:14b  →  ~8.5 GB  (Analyst — deep reasoning)
  qwen2.5:14b      →  ~8.5 GB  (Validator + Risk Officer share this model)
  Windows/display  →  ~1.5 GB
  Context buffers  →  ~1.0 GB
  ─────────────────────────────
  TOTAL USED       →  ~19.5 GB  (4.5 GB free — safe headroom)
"""

import os
import logging
import json
import concurrent.futures
from typing import Dict, Any

from ollama_integration import call_ollama

logger = logging.getLogger("SpecialistPool")

# ── Model Assignment ─────────────────────────────────────────────────────────
# Analyst   → deepseek-r1:14b  (deep technical reasoning, chain-of-thought)
# Validator → qwen2.5:14b      (fast structure validation)
# Risk      → qwen2.5:14b      (same model as Validator — saves ~7.5 GB VRAM)
# Chairman  → qwen2.5:14b      (quick final synthesis)
# Override any model via environment variable.
MODEL_ANALYST   = os.environ.get("MODEL_ANALYST",   "deepseek-r1:14b")
MODEL_VALIDATOR = os.environ.get("MODEL_VALIDATOR", "qwen2.5:14b")
MODEL_RISK      = os.environ.get("MODEL_RISK",      "qwen2.5:14b")     # shares VRAM with Validator
MODEL_CHAIRMAN  = os.environ.get("MODEL_CHAIRMAN",  "qwen2.5:14b")     # fast synthesis

class SpecialistPool:
    def __init__(self, max_workers: int = 3):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        
    def _ask_specialist(self, role: str, model: str, context_packet: Dict[str, Any], prompt_instruction: str) -> str:
        """Call a single specialist AI safely."""
        packet_str = json.dumps(context_packet, indent=2)
        full_prompt = f"""
Smart Context Packet:
{packet_str}

Role: {role}
Instruction: {prompt_instruction}
"""
        logger.debug(f"Calling specialist {role} ({model})...")
        response, err = call_ollama(full_prompt, model=model, timeout=90)
        
        if response and not err:
            return response.strip()
        return f"[Unavailable: {err}]"

    def run_parallel_evaluation(self, context_packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs Analyst, Validator, and Risk Officer in PARALLEL.
        """
        logger.info("Executing parallel specialist evaluation...")
        
        # Define tasks
        future_to_role = {
            self.executor.submit(
                self._ask_specialist, 
                "Technical Analyst", 
                MODEL_ANALYST, 
                context_packet, 
                "Evaluate the market context and active signals. Give verdict: [APPROVE] or [REJECT] with 1 short reason."
            ): "analyst",
            
            self.executor.submit(
                self._ask_specialist, 
                "Market Structure Validator", 
                MODEL_VALIDATOR, 
                context_packet, 
                "Check for traps, fakeouts, and trend conflicts based on context. Give verdict: [APPROVE] or [REJECT] with 1 short reason."
            ): "validator",
            
            self.executor.submit(
                self._ask_specialist, 
                "Chief Risk Officer", 
                MODEL_RISK, 
                context_packet, 
                "Evaluate risk based on system health, volatility, and active signals. Give verdict: [APPROVE] or [REJECT] with 1 short reason."
            ): "risk_officer"
        }
        
        opinions = {}
        
        # Wait for results (timeout 95 seconds just in case)
        for future in concurrent.futures.as_completed(future_to_role, timeout=95):
            role = future_to_role[future]
            try:
                result = future.result()
                opinions[role] = result
            except Exception as exc:
                logger.error(f"Specialist {role} generated an exception: {exc}")
                opinions[role] = f"[Error: {exc}]"
                
        return opinions

    def synthesize_chairman_decision(self, context_packet: Dict[str, Any], opinions: Dict[str, str]) -> Dict[str, Any]:
        """
        Chairman reviews the 3 opinions and makes a final verdict.
        """
        logger.info("Synthesizing Chairman decision...")
        packet_str = json.dumps(context_packet, indent=2)
        
        chairman_prompt = f"""You are the Chairman of the AI Investment Board. 
Your job is to synthesize 3 expert opinions into a final executive decision.

Context Packet:
{packet_str}

Board Expert Opinions:
1. Technical Analyst: {opinions.get('analyst', 'N/A')}
2. Market Validator:  {opinions.get('validator', 'N/A')}
3. Risk Officer:      {opinions.get('risk_officer', 'N/A')}

Instructions:
- If 2 or 3 experts APPROVE → issue [CONSENSUS_EXECUTE]
- If 2 or 3 experts REJECT → issue [CONSENSUS_REJECT]
- Start your response with EXACTLY ONE of: [CONSENSUS_EXECUTE] or [CONSENSUS_REJECT]
- Follow with a 1-sentence board summary.
"""
        chairman_verdict, err = call_ollama(chairman_prompt, model=MODEL_CHAIRMAN, timeout=120)
        
        if not chairman_verdict or err:
            chairman_verdict = f"[CONSENSUS_REJECT] Chairman unavailable: {err}"
            
        approved = "[CONSENSUS_EXECUTE]" in chairman_verdict.upper()
        final_verdict = "CONSENSUS_EXECUTE" if approved else "CONSENSUS_REJECT"
        
        # Fallback vote counting just in case Chairman gets confused
        approve_votes = sum(1 for op in opinions.values() if "[APPROVE]" in op.upper())
        if approve_votes >= 2 and not approved:
            approved = True
            final_verdict = "CONSENSUS_EXECUTE"

        return {
            "approved": approved,
            "final_verdict": final_verdict,
            "chairman_summary": chairman_verdict,
            "approve_votes": approve_votes,
            "opinions": opinions
        }

    def shutdown(self):
        """Cleanup thread pool."""
        self.executor.shutdown(wait=True)
        logger.info("Specialist Pool shutdown complete.")

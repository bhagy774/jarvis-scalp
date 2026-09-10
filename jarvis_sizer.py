#!/usr/bin/env python3
"""
JARVIS Dynamic Trade Sizer
===========================
Sizes positions based on AI confidence + account balance + compounding pool.
Hard cap: never exceed 5% of balance per trade.

Confidence -> Multiplier:
  60-69% -> 0.5x  (risky, small)
  70-79% -> 1.0x  (normal)
  80-89% -> 1.5x  (good setup)
  90-94% -> 2.0x  (excellent)
  95%+   -> 2.5x  (maximum!)
"""
import os
import logging
from typing import Dict, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("JarvisSizer")

LEVERAGE        = int(os.environ.get("JARVIS_LEVERAGE",      "100"))
BASE_RISK_PCT   = float(os.environ.get("SIZER_BASE_RISK_PCT", "0.02"))
MAX_RISK_PCT    = float(os.environ.get("SIZER_MAX_RISK_PCT",  "0.05"))
MIN_MARGIN_USDT = float(os.environ.get("SIZER_MIN_MARGIN",    "0.05"))
COMPOUND_RATIO  = float(os.environ.get("SIZER_COMPOUND_RATIO","0.5"))

# Confidence threshold -> multiplier (checked in order, first match wins)
CONF_MULTIPLIERS = [
    (95, 2.5),
    (90, 2.0),
    (80, 1.5),
    (70, 1.0),
    (60, 0.5),
    (0,  0.25),
]


class JarvisSizer:
    """
    Professional trade sizing engine.
    Integrates with Delta Exchange balance and Position Manager compounding.
    """

    def __init__(self, delta_client):
        self.delta = delta_client
        self._cached_balance: float = 0.0
        self._compound_pool:  float = 0.0

    def set_compound_pool(self, amount: float):
        """Update compounding pool from Position Manager."""
        self._compound_pool = max(0.0, amount)

    def get_live_balance(self) -> float:
        """Fetch real balance from Delta Exchange."""
        try:
            bal = self.delta.get_wallet_balance()
            if bal and bal > 0:
                self._cached_balance = bal
                return bal
        except Exception as e:
            logger.warning("[Sizer] Balance fetch failed: %s", e)
        return self._cached_balance

    def calculate_size(self, confidence: int, symbol: str = "BTCUSDT",
                       force_balance: float = None) -> Dict:
        """
        Calculate position size for a trade.

        Returns dict with:
          margin_usdt   : actual margin to use
          contracts     : number of Delta contracts
          notional_usdt : total notional value
          multiplier    : confidence multiplier applied
          balance       : current balance used for calc
          compound_used : compound pool contribution
          sizing_note   : human-readable explanation
        """
        balance = force_balance if force_balance is not None else self.get_live_balance()
        if balance <= 0:
            balance = 0.5  # emergency fallback

        # Get multiplier from confidence table
        multiplier = 0.25
        for threshold, mult in CONF_MULTIPLIERS:
            if confidence >= threshold:
                multiplier = mult
                break

        base_margin  = balance * BASE_RISK_PCT * multiplier
        compound_use = min(self._compound_pool * COMPOUND_RATIO, balance * 0.02)
        effective_margin = base_margin + compound_use

        max_margin = balance * MAX_RISK_PCT
        effective_margin = max(MIN_MARGIN_USDT, min(effective_margin, max_margin))

        notional  = effective_margin * LEVERAGE
        contracts = max(1, int(notional))

        note = (
            f"Balance=${balance:.4f} | Conf={confidence}% -> {multiplier}x"
            f" | Margin=${effective_margin:.4f} | {contracts} contracts"
        )
        if compound_use > 0:
            note += f" (+${compound_use:.4f} compound)"

        return {
            "margin_usdt":   round(effective_margin, 6),
            "contracts":     contracts,
            "notional_usdt": round(notional, 2),
            "confidence":    confidence,
            "multiplier":    multiplier,
            "balance":       round(balance, 6),
            "compound_used": round(compound_use, 6),
            "sizing_note":   note,
        }

    def print_sizing(self, result: Dict):
        """Pretty print sizing decision."""
        R   = "\033[91m"
        G   = "\033[92m"
        Y   = "\033[93m"
        W   = "\033[97m"
        DG  = "\033[90m"
        BD  = "\033[1m"
        RST = "\033[0m"
        mult      = result["multiplier"]
        mult_col  = G if mult >= 1.5 else (Y if mult >= 1.0 else R)
        print(
            f"  {DG}SIZER:{RST} Conf={W}{result['confidence']}%{RST}"
            f" -> {BD}{mult_col}{mult}x{RST}"
            f" | Margin={W}${result['margin_usdt']:.4f}{RST}"
            f" | {W}{result['contracts']} contracts{RST}"
            f" ({result['notional_usdt']:.1f} notional @ {LEVERAGE}x)"
        )
        if result.get("compound_used", 0) > 0:
            print(f"  {DG}  + Compound bonus: ${result['compound_used']:.4f}{RST}")


# ── Singleton ──────────────────────────────────────────────────
_sizer_instance: Optional[JarvisSizer] = None


def get_sizer(delta_client=None) -> Optional[JarvisSizer]:
    global _sizer_instance
    if _sizer_instance is None and delta_client is not None:
        _sizer_instance = JarvisSizer(delta_client)
    return _sizer_instance


if __name__ == "__main__":
    print("JarvisSizer module loaded OK")
    print("Confidence Table (example $6 balance):")
    for conf in [65, 72, 82, 91, 96]:
        mult = 0.25
        for t, m in CONF_MULTIPLIERS:
            if conf >= t:
                mult = m
                break
        margin    = 6.0 * BASE_RISK_PCT * mult
        margin    = max(MIN_MARGIN_USDT, min(margin, 6.0 * MAX_RISK_PCT))
        contracts = max(1, int(margin * LEVERAGE))
        print(f"  Conf={conf}% -> {mult}x -> Margin=${margin:.4f} -> {contracts} contracts")

#!/usr/bin/env python3
"""
JARVIS Oracle Trade Gate — Layer 4 Auto-Trade Gate (Gate 0.5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Validates all proposed live trades against the JARVIS Market Oracle.
Enforces:
  1. Direction Alignment: 5m & 30m timeframe consensus must match signal direction.
  2. Entry Zone Verification: Current price must fall inside Oracle entry zone.
  3. Dynamic TP/SL: Adopts Oracle exit target and stop loss when aligned.
"""

import os
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger("OracleTradeGate")

# Configuration
ORACLE_HARD_GATE = os.environ.get("ORACLE_HARD_GATE", "true").lower() == "true"
ORACLE_GATE_ENABLED = os.environ.get("ORACLE_GATE_ENABLED", "true").lower() == "true"
ORACLE_ENTRY_TOLERANCE = float(os.environ.get("ORACLE_ENTRY_TOLERANCE", "0.0025"))  # 0.25% tolerance margin


class OracleTradeGate:
    """
    Gate 0.5 in JarvisAutoTrader.
    Acts as a macro-market checkpoint before placing orders.
    """

    def __init__(self, oracle_ref=None, enabled: bool = None, hard_gate: bool = None):
        self._oracle_ref = oracle_ref
        self.enabled = ORACLE_GATE_ENABLED if enabled is None else enabled
        self.hard_gate = ORACLE_HARD_GATE if hard_gate is None else hard_gate
        self.tolerance = ORACLE_ENTRY_TOLERANCE

    def _get_oracle(self):
        """Retrieve Oracle instance."""
        if self._oracle_ref:
            return self._oracle_ref
        try:
            from jarvis_market_oracle import get_oracle
            return get_oracle()
        except Exception:
            return None

    def get_forecast(self) -> Dict[str, Any]:
        """Fetch latest Oracle forecast."""
        oracle = self._get_oracle()
        if oracle and hasattr(oracle, "get_latest_forecast"):
            return oracle.get_latest_forecast()
        return {}

    # ──────────────────────────────────────────────────────────
    #  GATE CHECK: DIRECTION ALIGNMENT
    # ──────────────────────────────────────────────────────────

    def is_trade_aligned(self, direction: str) -> Tuple[bool, str]:
        """
        Check if signal direction aligns with Oracle multi-timeframe forecast.
        Returns: (allowed: bool, reason: str)
        """
        if not self.enabled:
            return True, "Oracle gate disabled (bypassed)"

        forecast = self.get_forecast()
        if not forecast or forecast.get("model_used") == "startup_default":
            # Still warming up
            return True, "Oracle initializing — passing with default risk"

        is_call = direction.upper() in ("CALL", "BUY", "LONG")
        is_put  = direction.upper() in ("PUT", "SELL", "SHORT")
        sig_type = "CALL" if is_call else "PUT"

        tf5 = forecast.get("5min", {})
        tf30 = forecast.get("30min", {})
        sugg = forecast.get("trade_suggestion", "WAIT").upper()

        dir_5m = tf5.get("direction", "NEUTRAL").upper()
        dir_30m = tf30.get("direction", "NEUTRAL").upper()

        # 1. Oracle explicit trade suggestion check
        if sugg == "WAIT" and self.hard_gate:
            # If both timeframes are neutral or conflicting
            if dir_5m == "NEUTRAL" and dir_30m == "NEUTRAL":
                return False, f"Oracle advises WAIT — market in consolidation (5m & 30m NEUTRAL)"

        # 2. Rejection of direct contradictions
        if is_call:
            if dir_5m == "BEARISH" and dir_30m == "BEARISH":
                return False, f"Oracle BEARISH (5m {tf5.get('confidence')}% & 30m {tf30.get('confidence')}%) contradicts CALL signal"
            if sugg == "PUT" and self.hard_gate:
                return False, f"Oracle recommends PUT scalp — rejecting opposing CALL signal"

        elif is_put:
            if dir_5m == "BULLISH" and dir_30m == "BULLISH":
                return False, f"Oracle BULLISH (5m {tf5.get('confidence')}% & 30m {tf30.get('confidence')}%) contradicts PUT signal"
            if sugg == "CALL" and self.hard_gate:
                return False, f"Oracle recommends CALL scalp — rejecting opposing PUT signal"

        # 3. Positive confirmation
        if (is_call and dir_5m == "BULLISH") or (is_put and dir_5m == "BEARISH"):
            conf = tf5.get("confidence", 70)
            return True, f"Oracle aligned ({dir_5m} on 5m, conf: {conf}%)"

        # Neutral on 5m but favorable on 30m
        if (is_call and dir_30m == "BULLISH") or (is_put and dir_30m == "BEARISH"):
            return True, f"Oracle aligned (30m trend is {dir_30m})"

        return True, f"Oracle neutral ({dir_5m} 5m / {dir_30m} 30m) — trade allowed"

    # ──────────────────────────────────────────────────────────
    #  GATE CHECK: ENTRY ZONE VERIFICATION
    # ──────────────────────────────────────────────────────────

    def is_price_in_entry_zone(self, current_price: float) -> Tuple[bool, str]:
        """
        Verifies if current spot price is within Oracle's recommended entry zone.
        Returns: (in_zone: bool, reason: str)
        """
        if not self.enabled:
            return True, "Oracle gate disabled"

        if current_price <= 0:
            return True, "Invalid price passed"

        forecast = self.get_forecast()
        if not forecast or forecast.get("model_used") == "startup_default":
            return True, "Oracle initializing — entry zone check bypassed"

        ez = forecast.get("entry_zone", {})
        p_from = float(ez.get("price_from", 0) or 0)
        p_to   = float(ez.get("price_to", 0) or 0)

        if p_from <= 0 or p_to <= 0:
            return True, "No specific entry zone defined by Oracle"

        low_bound  = min(p_from, p_to) * (1.0 - self.tolerance)
        high_bound = max(p_from, p_to) * (1.0 + self.tolerance)

        if low_bound <= current_price <= high_bound:
            return True, f"Price ${current_price:,.2f} is inside Oracle entry zone (${min(p_from, p_to):,.0f}-${max(p_from, p_to):,.0f})"

        # If outside entry zone
        if self.hard_gate:
            dist_pct = ((current_price - low_bound) / current_price) * 100 if current_price < low_bound else ((current_price - high_bound) / current_price) * 100
            return False, (
                f"Price ${current_price:,.2f} is outside Oracle entry zone "
                f"(${min(p_from, p_to):,.0f}-${max(p_from, p_to):,.0f}) by {abs(dist_pct):.2f}% — waiting for pullback"
            )

        return True, f"Price slightly outside entry zone (${min(p_from, p_to):,.0f}-${max(p_from, p_to):,.0f}) but hard gate is off"

    # ──────────────────────────────────────────────────────────
    #  DYNAMIC TAKE-PROFIT & STOP-LOSS
    # ──────────────────────────────────────────────────────────

    def get_oracle_tp_sl(self, current_price: float, direction: str) -> Dict[str, Any]:
        """
        Provides Oracle's suggested exit target and stop loss.
        Validates logical geometry before allowing use.
        """
        forecast = self.get_forecast()
        is_call = direction.upper() in ("CALL", "BUY", "LONG")

        if not forecast or forecast.get("model_used") == "startup_default":
            return {"use_oracle": False, "reason": "Oracle not ready"}

        tp = float(forecast.get("exit_target", 0) or 0)
        sl = float(forecast.get("stop_loss", 0) or 0)
        hold_min = int(forecast.get("hold_minutes", 15) or 15)

        # Validate geometry
        if is_call:
            # For a CALL, TP must be above price and SL must be below price
            if tp > current_price and 0 < sl < current_price:
                # Check that TP is within a sane scalping/swing limit (< 4% away)
                if (tp - current_price) / current_price < 0.04 and (current_price - sl) / current_price < 0.03:
                    return {
                        "use_oracle": True,
                        "tp_price": tp,
                        "sl_price": sl,
                        "hold_minutes": hold_min,
                        "reason": f"Oracle CALL target ${tp:,.0f} / stop ${sl:,.0f}"
                    }
        else:
            # For a PUT, TP must be below price and SL must be above price
            if 0 < tp < current_price and sl > current_price:
                if (current_price - tp) / current_price < 0.04 and (sl - current_price) / current_price < 0.03:
                    return {
                        "use_oracle": True,
                        "tp_price": tp,
                        "sl_price": sl,
                        "hold_minutes": hold_min,
                        "reason": f"Oracle PUT target ${tp:,.0f} / stop ${sl:,.0f}"
                    }

        return {"use_oracle": False, "reason": "Oracle TP/SL geometry incompatible with current price"}

    def get_gate_status(self) -> Dict[str, Any]:
        """Return status snapshot for UI and logs."""
        forecast = self.get_forecast()
        return {
            "enabled": self.enabled,
            "hard_gate": self.hard_gate,
            "has_forecast": bool(forecast and forecast.get("model_used") != "startup_default"),
            "trade_suggestion": forecast.get("trade_suggestion", "WAIT"),
            "5m_direction": forecast.get("5min", {}).get("direction", "UNKNOWN"),
            "30m_direction": forecast.get("30min", {}).get("direction", "UNKNOWN"),
            "gemini_summary": forecast.get("gemini_summary", "Oracle Standby")
        }


# Global singleton instance
_trade_gate_instance: Optional[OracleTradeGate] = None


def get_oracle_trade_gate(oracle_ref=None) -> OracleTradeGate:
    global _trade_gate_instance
    if _trade_gate_instance is None:
        _trade_gate_instance = OracleTradeGate(oracle_ref=oracle_ref)
    elif oracle_ref and not _trade_gate_instance._oracle_ref:
        _trade_gate_instance._oracle_ref = oracle_ref
    return _trade_gate_instance

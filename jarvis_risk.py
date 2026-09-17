"""Conservative, balance/risk/margin-aware sizing shared by paper and live paths.

Leverage is an output of risk math, never a user-selected operating value.  The
only leverage setting is a conservative hard cap; venue/product limits further
reduce it.  Missing or non-positive inputs return a blocked result.
"""
from __future__ import annotations

import math
import os
from typing import Any, Dict, Optional

BASE_RISK_PCT = float(os.environ.get("SIZER_BASE_RISK_PCT", "0.02"))
MAX_RISK_PCT = float(os.environ.get("SIZER_MAX_RISK_PCT", "0.05"))
MIN_MARGIN_USDT = float(os.environ.get("SIZER_MIN_MARGIN", "0.05"))
COMPOUND_RATIO = float(os.environ.get("SIZER_COMPOUND_RATIO", "0.5"))
# Caps are policy guardrails, not a requested leverage value.
MIN_LEVERAGE_CAP = max(1, int(os.environ.get("JARVIS_MIN_LEVERAGE", "1")))
MAX_LEVERAGE_CAP = max(MIN_LEVERAGE_CAP, int(os.environ.get("JARVIS_MAX_LEVERAGE", "20")))

CONF_MULTIPLIERS = [(95, 2.5), (90, 2.0), (80, 1.5), (70, 1.0), (60, 0.5), (0, 0.25)]


def confidence_multiplier(confidence: int) -> float:
    try:
        value = int(confidence)
    except (TypeError, ValueError):
        return 0.0
    for threshold, multiplier in CONF_MULTIPLIERS:
        if value >= threshold:
            return multiplier
    return 0.0


def derive_auto_leverage(
    available_balance: float,
    margin_usdt: float,
    trade_risk_usdt: float,
    stop_distance_pct: float,
    product_max_leverage: Optional[float] = None,
) -> Dict[str, Any]:
    """Derive integer leverage from collateral, margin and stop-loss risk.

    The risk-limited notional is ``trade_risk / stop_distance``.  Leverage is
    the largest integer that does not exceed that notional for the selected
    margin, then bounded by explicit policy/product caps.  Actual notional is
    still capped by the risk-limited notional after contract rounding.
    """
    try:
        balance = float(available_balance)
        margin = float(margin_usdt)
        risk = float(trade_risk_usdt)
        stop = float(stop_distance_pct)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "invalid risk inputs"}
    if balance <= 0 or margin <= 0 or risk <= 0 or stop <= 0:
        return {"ok": False, "reason": "balance, margin, risk and stop distance must be positive"}
    if margin > balance:
        return {"ok": False, "reason": "margin exceeds available balance"}
    venue_cap = MAX_LEVERAGE_CAP
    if product_max_leverage is not None:
        try:
            venue_cap = min(venue_cap, int(float(product_max_leverage)))
        except (TypeError, ValueError):
            return {"ok": False, "reason": "invalid product leverage metadata"}
    if venue_cap < MIN_LEVERAGE_CAP:
        return {"ok": False, "reason": "product leverage limit below policy minimum"}
    risk_notional = risk / stop
    unconstrained = risk_notional / margin
    leverage = max(MIN_LEVERAGE_CAP, min(venue_cap, int(math.floor(unconstrained))))
    # At least one contract of notional may be smaller than the margin; keep
    # the selected margin as a reservation ceiling, not a forced exposure.
    max_notional = min(margin * leverage, risk_notional, balance * leverage)
    if max_notional <= 0:
        return {"ok": False, "reason": "risk budget cannot fund exposure"}
    return {
        "ok": True,
        "leverage": int(leverage),
        "risk_notional_usdt": round(risk_notional, 8),
        "max_notional_usdt": round(max_notional, 8),
        "margin_usdt": round(margin, 8),
        "trade_risk_usdt": round(risk, 8),
        "stop_distance_pct": stop,
        "policy_cap": MAX_LEVERAGE_CAP,
        "product_cap": product_max_leverage,
    }


def calculate_trade_size(
    available_balance: float,
    confidence: int,
    stop_distance_pct: float,
    max_trade_risk_usdt: Optional[float] = None,
    compound_pool: float = 0.0,
    product_max_leverage: Optional[float] = None,
    base_risk_pct: float = BASE_RISK_PCT,
    max_margin_pct: float = MAX_RISK_PCT,
    min_margin_usdt: float = MIN_MARGIN_USDT,
) -> Dict[str, Any]:
    """Return one consistent size/leverage decision for paper and live paths."""
    try:
        balance = float(available_balance)
        stop = float(stop_distance_pct)
        conf = int(confidence)
    except (TypeError, ValueError):
        balance, stop, conf = 0.0, 0.0, 0
    mult = confidence_multiplier(conf)
    if balance <= 0 or stop <= 0 or mult <= 0:
        return {"ok": False, "reason": "missing available balance or stop distance", "contracts": 0, "leverage": 0}
    base_margin = balance * max(0.0, float(base_risk_pct)) * mult
    compound = min(max(0.0, float(compound_pool)) * COMPOUND_RATIO, balance * max(0.0, float(base_risk_pct)))
    max_margin = balance * max(0.0, float(max_margin_pct))
    margin = min(max_margin, max(min_margin_usdt, base_margin + compound))
    if margin <= 0:
        return {"ok": False, "reason": "margin policy leaves no collateral", "contracts": 0, "leverage": 0}
    risk_budget = min(balance * max(0.0, float(MAX_RISK_PCT)) * mult, max_trade_risk_usdt if max_trade_risk_usdt is not None else float("inf"))
    if risk_budget <= 0:
        return {"ok": False, "reason": "trade risk budget is zero", "contracts": 0, "leverage": 0}
    lev = derive_auto_leverage(balance, margin, risk_budget, stop, product_max_leverage)
    if not lev.get("ok"):
        return {**lev, "contracts": 0, "margin_usdt": round(margin, 8), "confidence": conf, "multiplier": mult}
    contracts = int(math.floor(lev["max_notional_usdt"]))
    if contracts <= 0:
        return {**lev, "ok": False, "reason": "risk budget cannot fund one whole contract", "contracts": 0, "confidence": conf, "multiplier": mult}
    actual_notional = float(contracts)
    actual_margin = min(margin, actual_notional / lev["leverage"])
    return {
        **lev,
        "ok": True,
        "contracts": contracts,
        "notional_usdt": round(actual_notional, 8),
        "margin_usdt": round(actual_margin, 8),
        "balance": round(balance, 8),
        "confidence": conf,
        "multiplier": mult,
        "compound_used": round(compound, 8),
        "sizing_note": f"balance=${balance:.4f}, margin=${actual_margin:.4f}, risk=${risk_budget:.4f}, leverage={lev['leverage']}x",
    }

"""Options intelligence policy for a selected crypto instrument.

Asset-specific options are always primary.  BTC options are allowed only as a
separate macro confirmation when the selected altcoin has no usable chain.
They can adjust or caution a directional decision, but are never used to
produce an altcoin strike, price target, or hedge contract.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class OptionsContext:
    selected_asset: str
    source_asset: str
    role: str                 # asset_primary | btc_macro_confirmation | unavailable
    available: bool
    bias: str = "NEUTRAL"     # BULLISH | BEARISH | NEUTRAL
    strength: int = 0
    pcr: float = 0.0
    reason: str = ""
    expiry_coverage: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _base(symbol_or_asset: str) -> str:
    value = str(symbol_or_asset or "").upper().replace("-", "").replace("_", "")
    for quote in ("USDT", "USD"):
        if value.endswith(quote) and len(value) > len(quote):
            return value[:-len(quote)]
    return value


def _valid_bias(raw: Any, asset: str) -> OptionsContext | None:
    if not isinstance(raw, dict):
        return None
    bias = str(raw.get("bias", "NEUTRAL")).upper()
    if bias not in {"BULLISH", "BEARISH", "NEUTRAL"}:
        bias = "NEUTRAL"
    try:
        strength = abs(int(raw.get("score", 0)))
        pcr = float(raw.get("pcr", 0.0))
    except (TypeError, ValueError):
        return None
    # A neutral / zero score is valid intelligence but contributes no direction.
    if not raw.get("reasons") and not raw.get("raw_data"):
        return None
    coverage = raw.get("raw_data", {}).get("expiry_coverage") if isinstance(raw.get("raw_data"), dict) else None
    return OptionsContext(asset, asset, "asset_primary", True, bias, strength, pcr,
                          "; ".join(str(x) for x in raw.get("reasons", [])[:2]), coverage)


def resolve_options_context(delta_client: Any, selected_symbol: str) -> OptionsContext:
    """Return selected-asset intelligence, or BTC macro fallback if allowed.

    Exceptions and absent data deliberately resolve to an explicit unavailable
    context; callers must not manufacture an options view.
    """
    asset = _base(selected_symbol)
    if not asset or delta_client is None:
        return OptionsContext(asset, "", "unavailable", False, reason="No selected asset or Delta client")
    try:
        primary = _valid_bias(delta_client.get_institutional_bias(asset), asset)
    except Exception:
        primary = None
    if primary is not None:
        return primary

    if asset == "BTC" or os.getenv("JARVIS_BTC_OPTIONS_CONFIRMATION", "1") == "0":
        return OptionsContext(asset, "", "unavailable", False, reason="Selected-asset options unavailable")
    try:
        macro = _valid_bias(delta_client.get_institutional_bias("BTC"), "BTC")
    except Exception:
        macro = None
    if macro is None:
        return OptionsContext(asset, "", "unavailable", False, reason="Selected-asset and BTC options unavailable")
    return OptionsContext(asset, "BTC", "btc_macro_confirmation", True, macro.bias,
                          macro.strength, macro.pcr,
                          "Selected-asset chain unavailable; BTC macro context only: " + macro.reason)


def apply_options_confirmation(direction: str, confidence: int,
                               context: OptionsContext) -> Tuple[int, str]:
    """Apply a bounded advisory adjustment, never create a trade direction.

    A primary chain has modest influence. BTC macro fallback has a smaller
    influence, because BTC/alt correlation can fail. The result never changes
    TP/SL, strike, contract, or hedge instrument.
    """
    try:
        confidence = max(0, min(100, int(confidence)))
    except (TypeError, ValueError):
        return 0, "Invalid confidence"
    direction = str(direction or "").upper()
    if direction not in {"CALL", "PUT", "BUY", "SELL"} or not context.available:
        return confidence, context.reason or "No options confirmation"
    wanted = "BULLISH" if direction in {"CALL", "BUY"} else "BEARISH"
    if context.bias == "NEUTRAL":
        return confidence, f"{context.role}: neutral options bias"
    agrees = context.bias == wanted
    if context.role == "asset_primary":
        delta = 4 if agrees else -6
    else:  # BTC may confirm market regime but cannot stand in for an alt chain.
        delta = 2 if agrees else -4
    final = max(0, min(100, confidence + delta))
    return final, f"{context.role} {context.source_asset} {context.bias}: {delta:+d} confidence"

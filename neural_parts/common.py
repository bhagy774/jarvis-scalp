"""Shared bounded OHLCV coercion and feature primitives; Parts own projections."""
from collections.abc import Mapping
import math
import statistics

import quantitative_math as qm

TIMEFRAMES = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h")
PART_NAMES = tuple(f"part{i}_" + name for i, name in enumerate((
    "breakout", "zone", "psychology", "volume", "ml", "trend",
    "volatility", "structure", "orderflow", "candlestats"), 1))


def clip(value, limit=10.0):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non_finite_feature")
    return max(-limit, min(limit, value))


def div(a, b, eps=1e-12):
    return float(a) / max(abs(float(b)), eps)


def mean(xs):
    return statistics.fmean(xs) if xs else 0.0


def std(xs):
    return statistics.pstdev(xs) if len(xs) > 1 else 0.0


def slope(xs):
    """Least-squares slope retained only as a generic numerical helper."""
    n = len(xs)
    if n < 2:
        return 0.0
    xm, ym = (n - 1) / 2.0, mean(xs)
    return sum((i - xm) * (v - ym) for i, v in enumerate(xs)) / (n * (n*n - 1) / 12.0)


def ohlcv_rows(data):
    rows = qm.candles_from(data, limit=128)
    if len(rows) < 64:
        raise ValueError("insufficient_closed_candles")
    return rows


def candle_math(data):
    """Return bounded robust-distribution, state, geometry and structure evidence.

    Every price feature uses closed OHLCV bars. The function intentionally has
    no EMA/RSI/MACD/ATR/ADX/band calculation or exchange-flow assumption.
    """
    rows = ohlcv_rows(data)
    f = qm.quantitative_features(rows, limit=128)
    if not f.get("available"):
        raise ValueError("invalid_ohlcv")
    closes = [r["close"] for r in rows]
    highs = [r["high"] for r in rows]
    lows = [r["low"] for r in rows]
    volumes = [r["volume"] for r in rows]
    rets = list(f["returns"])
    scale = max(float(f["return_scale"]), 1e-12)
    price = float(f["price"])
    risk_price = max(float(f["range_scale_price"]), price * 1e-9)
    geom = []
    for r in rows:
        span = max(r["high"] - r["low"], r["close"] * 1e-12)
        body = (r["close"] - r["open"]) / span
        geom.append({"body_signed": max(-1.0, min(1.0, body)),
                     "body_fraction": min(1.0, abs(body)),
                     "close_location": max(-1.0, min(1.0, (2*r["close"]-r["high"]-r["low"])/span)),
                     "upper_wick": max(0.0, (r["high"]-max(r["open"],r["close"]))/span),
                     "lower_wick": max(0.0, (min(r["open"],r["close"])-r["low"])/span)})
    current = geom[-1]
    prior_bodies = [g["body_fraction"] for g in geom[-33:-1]]
    body_scale = max(qm.robust_scale(prior_bodies), 1e-6)
    body_z = (current["body_fraction"] - statistics.median(prior_bodies)) / body_scale if prior_bodies else 0.0
    def position(window):
        lo, hi = min(lows[-window:]), max(highs[-window:])
        return (price-lo) / max(hi-lo, price*1e-12)
    def ret_z(window):
        return sum(rets[-window:]) / scale if rets else 0.0
    recent_signs = [1 if x > 0 else -1 if x < 0 else 0 for x in rets[-20:]]
    nonzero = [x for x in recent_signs if x]
    coherence = sum(nonzero) / max(1, len(nonzero))
    transitions = sum(1 for a,b in zip(nonzero, nonzero[1:]) if a != b) / max(1,len(nonzero)-1)
    streak = 0
    if nonzero:
        for sign in reversed(nonzero):
            if sign != nonzero[-1]: break
            streak += 1
    profile = qm.price_volume_distribution(rows, bins=24, limit=128)
    zones = qm.structural_zones(rows, limit=128)
    seq = qm.sequential_direction_evidence(rows)
    sup = zones.get("nearest_support") if zones.get("available") else None
    res = zones.get("nearest_resistance") if zones.get("available") else None
    vol_state = f["volatility_state"]
    tail_scale = max(scale, 1e-12)
    flow = float(f["flow_imbalance_proxy"])
    return {
        "rows": rows, "price": price, "returns": rets, "return_scale": scale,
        "ret1_z": rets[-1] / scale if rets else 0.0,
        "ret4_z": ret_z(4), "ret16_z": ret_z(16),
        "trend_score": float(f["trend_score"]),
        "theil_sen_slope_z": float(f["theil_sen_log_slope"]) / scale,
        "state_velocity_z": float(f["kalman"]["velocity_z"]),
        "state_innovation_z": float(f["kalman"]["innovation_z"]),
        "change_point_bic_gain": float(f["change_point"]["bic_gain"]),
        "change_point_shift_z": float(f["change_point"].get("shift_z", 0.0)),
        "realized_vol": float(f["realized_vol"]), "downside_vol": float(f["downside_vol"]),
        "drawdown_from_peak": float(f["drawdown_from_peak"]),
        "jump_share": float(f["jump_share"]), "range_scale_pct": float(f["range_scale_pct"]),
        "range_scale_price": risk_price,
        "high_state_posterior": float(vol_state["high_state_posterior"]),
        "short_long_realized_vol_ratio": float(vol_state["short_long_ratio"]),
        "volume_surprise_z": float(f["volume_surprise_robust_z"]),
        "flow_proxy": flow, "flow_is_measured_orderbook": False,
        "flow_trend_divergence": flow - max(-1.0,min(1.0,ret_z(16)/5.0)),
        "sign_persistence": float(f["sign_persistence"]),
        "directional_coherence": coherence, "transition_rate": transitions,
        "directional_streak_fraction": min(1.0, streak/8.0),
        "green_fraction": sum(g["body_signed"]>0 for g in geom[-16:])/16.0,
        "candle": current, "body_robust_z": body_z,
        "body_acceleration": current["body_signed"]-geom[-2]["body_signed"],
        "range_position_8": position(8), "range_position_20": position(20),
        "range_position_32": position(32), "range_position_50": position(50),
        "range_width_20_pct": (max(highs[-20:])-min(lows[-20:]))/price,
        "range_width_50_pct": (max(highs[-50:])-min(lows[-50:]))/price,
        "break_high20_scale": (price-max(highs[-21:-1]))/risk_price,
        "break_low20_scale": (min(lows[-21:-1])-price)/risk_price,
        "break_high50_scale": (price-max(highs[-51:-1]))/risk_price,
        "break_low50_scale": (min(lows[-51:-1])-price)/risk_price,
        "profile": profile, "zones": zones, "sequential": seq,
        "support_distance_scale": (float(sup["center"])-price)/risk_price if sup else 0.0,
        "resistance_distance_scale": (float(res["center"])-price)/risk_price if res else 0.0,
        "support_strength": float(sup["strength"]) if sup else 0.0,
        "resistance_strength": float(res["strength"]) if res else 0.0,
        "poc_distance_scale": (price-float(profile["poc"]))/risk_price if profile.get("available") else 0.0,
        "close_location_in_value": float(profile["close_location_in_value"]) if profile.get("available") else 0.5,
        "volume_concentration_4_32": sum(volumes[-4:])/max(sum(volumes[-32:]),1e-12),
        "tail_downside_scale": float(f["tail_return_q05"])/tail_scale,
        "tail_upside_scale": float(f["tail_return_q95"])/tail_scale,
    }


def mtf_signal_matrix(data):
    frames=data.get("frames") if isinstance(data,Mapping) and isinstance(data.get("frames"),Mapping) else data
    if not isinstance(frames,Mapping) or set(frames)!=set(TIMEFRAMES):
        raise ValueError("incomplete_eight_frame_evidence")
    matrix=[]
    for tf in TIMEFRAMES:
        frame=frames[tf]
        if not isinstance(frame,Mapping): raise ValueError("invalid_frame_evidence")
        values=[]
        for part in PART_NAMES:
            result=frame.get(part)
            if not isinstance(result,Mapping): raise ValueError("missing_part_evidence")
            if result.get("timeframe") and str(result["timeframe"])!=tf: raise ValueError("evidence_timeframe_mismatch")
            raw=result.get("signal",0.0)
            if isinstance(raw,(list,tuple)): raw=raw[-1] if raw else 0.0
            try: value=float(raw)
            except (TypeError,ValueError,OverflowError) as exc: raise ValueError("invalid_part_signal") from exc
            if not math.isfinite(value): raise ValueError("non_finite_part_signal")
            values.append(max(-1.0,min(1.0,value)))
        matrix.append(tuple(values))
    return tuple(matrix)

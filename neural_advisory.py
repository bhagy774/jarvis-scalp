"""Strict, bounded, advisory-only inference for Jarvis Parts 1-10.

Runtime has no PyTorch/CUDA import, no network access, and no model creation.
Only a validated local JSON artifact trained offline can produce an advisory.
Results are diagnostic metadata and MUST NOT drive entry, risk or execution.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

FORMAT = "jarvis-advisory-mlp"
FORMAT_VERSION = 1
FEATURE_SCHEMA = "jarvis-ohlcv-part-features-v1"
PARTS = tuple(f"part{i}_" + name for i, name in enumerate((
    "breakout", "zone", "psychology", "volume", "ml", "trend",
    "volatility", "structure", "orderflow", "candlestats"), 1))
FEATURE_NAMES = {
    "part1_breakout": ("ret1", "ret4", "ret16", "break_high20", "break_low20", "range_pos20", "volume_z", "body_signed", "slope16", "atr14_pct", "vol_ratio", "wick_imbalance"),
    "part2_zone": ("range_pos32", "dist_weighted_mean", "dist_high32", "dist_low32", "volume_node_pos", "volume_z", "ret4", "ret16", "atr14_pct", "range_pos8", "trend_slope", "range_expansion"),
    "part3_psychology": ("body_ratio", "upper_wick_ratio", "lower_wick_ratio", "close_location", "range_atr", "gap_atr", "prev_body_signed", "engulf_proxy", "doji_proxy", "ret1", "ret4", "volume_z"),
    "part4_volume": ("volume_z", "volume_ratio", "signed_flow12", "signed_flow4", "flow_return_divergence", "volume_trend", "ret1", "ret4", "range_atr", "close_location", "volume_concentration", "atr14_pct"),
    "part5_ml": ("drift_z16", "slope_t_proxy", "ret1", "ret4", "ret16", "ema8_21", "ema21_50", "rsi_centered", "volume_z", "vol_ratio", "atr14_pct", "drawdown16"),
    "part6_trend": ("ema8_21", "ema21_50", "slope16", "slope32", "up_move14", "down_move14", "directional_imbalance", "ret4", "ret16", "range_pos32", "vol_ratio", "atr14_pct"),
    "part7_volatility": ("std8", "std32", "vol_ratio", "atr14_pct", "atr14_50_ratio", "range_atr", "range_expansion", "ret1", "abs_ret4", "abs_ret16", "body_ratio", "volume_z"),
    "part8_structure": ("break_high20", "break_low20", "break_high50", "break_low50", "swing_high_gap", "swing_low_gap", "range_pos20", "range_pos50", "slope16", "ret4", "atr14_pct", "volume_z"),
    "part9_orderflow": ("signed_flow4", "signed_flow12", "flow_return_divergence", "cvd_slope12", "ret4", "ret16", "volume_z", "volume_ratio", "range_atr", "body_signed", "flow_price_divergence", "atr14_pct"),
    "part10_candlestats": ("body_ratio", "body_acceleration", "streak8", "transition_rate16", "green_fraction16", "range_atr", "ret1", "ret4", "ret16", "drawdown16", "volume_z", "vol_ratio"),
}
_TIMEFRAME_SECONDS = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400}
_MAX_ARTIFACT_BYTES = 128 * 1024
_MAX_ARTIFACTS = 16
_MAX_PREDICTIONS = 256
# Re-train rather than keep using a predictor whose source history is too old.
_MAX_TRAINING_DATA_AGE_SECONDS = 90 * 24 * 60 * 60
_MAX_NUMERIC_ARTIFACT_VALUE = 1_000_000.0
_LOCK = threading.RLock()
_INFERENCE_SLOT = threading.BoundedSemaphore(1)
_ARTIFACT_CACHE: "OrderedDict[Tuple[Any, ...], Dict[str, Any]]" = OrderedDict()
_PREDICTION_CACHE: "OrderedDict[Tuple[Any, ...], Dict[str, Any]]" = OrderedDict()


def _clip(x: float, limit: float = 10.0) -> float:
    if not math.isfinite(x):
        raise ValueError("non_finite_feature")
    return max(-limit, min(limit, x))


def _safe_div(a: float, b: float, eps: float = 1e-12) -> float:
    return a / (abs(b) + eps)


def _rows(data: Any) -> Sequence[Mapping[str, Any]]:
    """Read OHLCV from pandas-like frames or row mappings without importing pandas."""
    if data is None:
        return ()
    if isinstance(data, (list, tuple)):
        return data
    if hasattr(data, "columns") and hasattr(data, "iloc"):
        cols = set(data.columns)
        required = ("open", "high", "low", "close", "volume")
        if not set(required).issubset(cols):
            raise ValueError("missing_ohlcv_columns")
        frame = data.tail(64)
        values = {k: frame[k].tolist() for k in required}
        return tuple({k: values[k][i] for k in required} for i in range(len(frame)))
    return ()


def _numeric_rows(data: Any) -> Tuple[Tuple[float, float, float, float, float], ...]:
    rows = _rows(data)
    out = []
    for row in rows[-64:]:
        if not isinstance(row, Mapping):
            raise ValueError("invalid_ohlcv_row")
        vals = tuple(float(row[k]) for k in ("open", "high", "low", "close", "volume"))
        if not all(math.isfinite(v) for v in vals):
            raise ValueError("non_finite_ohlcv")
        o, h, l, c, v = vals
        if min(o, h, l, c) <= 0 or v < 0 or h < max(o, c, l) or l > min(o, c, h):
            raise ValueError("invalid_ohlcv")
        out.append(vals)
    if len(out) < 64:
        raise ValueError("insufficient_closed_candles")
    return tuple(out)


def _ema(xs: Sequence[float], period: int) -> float:
    a = 2.0 / (period + 1.0)
    value = xs[0]
    for x in xs[1:]:
        value = a * x + (1.0 - a) * value
    return value


def _slope(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2.0
    mean_y = sum(xs) / n
    denom = sum((i - mean_x) ** 2 for i in range(n)) or 1.0
    return sum((i - mean_x) * (v - mean_y) for i, v in enumerate(xs)) / denom


def _std(xs: Sequence[float]) -> float:
    if not xs:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def _rsi(xs: Sequence[float], period: int = 14) -> float:
    ds = [xs[i] - xs[i - 1] for i in range(max(1, len(xs) - period), len(xs))]
    gain = sum(max(d, 0.0) for d in ds) / max(1, len(ds))
    loss = sum(max(-d, 0.0) for d in ds) / max(1, len(ds))
    if loss == 0:
        return 1.0 if gain else 0.0
    return 1.0 - 1.0 / (1.0 + gain / loss)


def feature_vector(part_id: str, data: Any) -> Tuple[float, ...]:
    """Create one deterministic, part-specific 12-feature OHLCV vector."""
    if part_id not in FEATURE_NAMES:
        raise ValueError("unknown_part_id")
    rows = _numeric_rows(data)
    oo, hh, ll, cc, vv = ([r[i] for r in rows] for i in range(5))
    n, price = len(cc), cc[-1]
    rets = [cc[i] / cc[i - 1] - 1.0 for i in range(1, n)]
    ranges = [max(hh[i] - ll[i], 1e-12) for i in range(n)]
    bodies = [(cc[i] - oo[i]) / ranges[i] for i in range(n)]
    upper = [(hh[i] - max(oo[i], cc[i])) / ranges[i] for i in range(n)]
    lower = [(min(oo[i], cc[i]) - ll[i]) / ranges[i] for i in range(n)]
    logc = [math.log(x) for x in cc]
    ret = lambda k: cc[-1] / cc[max(0, n - 1 - k)] - 1.0
    atr14 = sum(ranges[-14:]) / 14.0
    atr50 = sum(ranges[-50:]) / 50.0
    ret8std, ret32std = _std(rets[-8:]), _std(rets[-32:])
    volmean32 = sum(vv[-32:]) / 32.0
    volstd32 = _std(vv[-32:])
    volume_z = _safe_div(vv[-1] - volmean32, volstd32)
    volume_ratio = _safe_div(vv[-1], volmean32)
    pos = lambda window: _safe_div(price - min(ll[-window:]), max(hh[-window:]) - min(ll[-window:]))
    highgap = lambda window: _safe_div(price - max(hh[-window:]), price)
    lowgap = lambda window: _safe_div(price - min(ll[-window:]), price)
    ema8, ema21, ema50 = _ema(cc[-50:], 8), _ema(cc[-50:], 21), _ema(cc[-50:], 50)
    ema821 = _safe_div(ema8 - ema21, price)
    ema2150 = _safe_div(ema21 - ema50, price)
    slope16 = _slope(logc[-16:])
    slope32 = _slope(logc[-32:])
    atr_pct = _safe_div(atr14, price)
    range_atr = _safe_div(ranges[-1], atr14)
    vol_ratio = _safe_div(ret8std, ret32std)
    range_expansion = _safe_div(sum(ranges[-5:]) / 5.0, sum(ranges[-20:]) / 20.0)
    close_location = 2.0 * _safe_div(cc[-1] - ll[-1], ranges[-1]) - 1.0
    body_ratio = abs(bodies[-1])
    wick_imbalance = upper[-1] - lower[-1]
    flow = [bodies[i] * vv[i] for i in range(n)]
    signed_flow = lambda w: _safe_div(sum(flow[-w:]), sum(vv[-w:]))
    ret4, ret16 = ret(4), ret(16)
    flow12, flow4 = signed_flow(12), signed_flow(4)
    prior_close = cc[-2]
    break_hi20 = _safe_div(cc[-1] - max(hh[-21:-1]), price)
    break_lo20 = _safe_div(cc[-1] - min(ll[-21:-1]), price)
    break_hi50 = _safe_div(cc[-1] - max(hh[-51:-1]), price)
    break_lo50 = _safe_div(cc[-1] - min(ll[-51:-1]), price)
    recent_vol = vv[-32:]
    weighted_center = _safe_div(sum(c * v for c, v in zip(cc[-32:], recent_vol)), sum(recent_vol))
    weighted_dev = _safe_div(price - weighted_center, price)
    voltrend = _slope([math.log1p(v) for v in vv[-16:]])
    flow_return_divergence = flow12 - max(-1.0, min(1.0, ret16 * 100.0))
    transition = sum(1 for i in range(-16, -1) if bodies[i] * bodies[i + 1] < 0) / 15.0
    same_streak = 1
    for i in range(n - 2, max(-1, n - 9), -1):
        if bodies[i] == 0 or bodies[i] * bodies[-1] <= 0:
            break
        same_streak += 1
    green_fraction = sum(1 for x in bodies[-16:] if x > 0) / 16.0
    prev_body = bodies[-2]
    drawdown16 = _safe_div(price - max(hh[-16:]), price)
    range_pos32, range_pos20, range_pos50 = pos(32), pos(20), pos(50)
    profile_low, profile_high = min(ll[-32:]), max(hh[-32:])
    profile_width = max(profile_high - profile_low, 1e-12)
    profile_bins = [0.0] * 20
    for i in range(n - 32, n):
        typical = (hh[i] + ll[i] + cc[i]) / 3.0
        bin_index = min(19, max(0, int((typical - profile_low) / profile_width * 20)))
        profile_bins[bin_index] += vv[i]
    volume_node_pos = ((max(range(20), key=lambda index: profile_bins[index]) + 0.5) / 20.0
                       if sum(profile_bins) > 0 else range_pos32)
    if part_id == "part1_breakout":
        vals = [ret(1), ret4, ret16, break_hi20, break_lo20, range_pos20, volume_z, bodies[-1], slope16, atr_pct, vol_ratio, wick_imbalance]
    elif part_id == "part2_zone":
        vals = [range_pos32, weighted_dev, highgap(32), lowgap(32), volume_node_pos, volume_z, ret4, ret16, atr_pct, pos(8), slope32, range_expansion]
    elif part_id == "part3_psychology":
        gap = _safe_div(oo[-1] - prior_close, atr14)
        engulf = math.copysign(1.0, bodies[-1]) if abs(bodies[-1]) > abs(prev_body) and bodies[-1] * prev_body < 0 else 0.0
        vals = [body_ratio, upper[-1], lower[-1], close_location, range_atr, gap, prev_body, engulf, 1.0 - body_ratio, ret(1), ret4, volume_z]
    elif part_id == "part4_volume":
        vals = [volume_z, volume_ratio, flow12, flow4, flow_return_divergence, voltrend, ret(1), ret4, range_atr, close_location, _safe_div(sum(vv[-4:]), sum(vv[-32:])), atr_pct]
    elif part_id == "part5_ml":
        drift = _safe_div(sum(rets[-16:]) / 16.0, _std(rets[-16:]))
        vals = [drift, _safe_div(slope16, _std(rets[-16:])), ret(1), ret4, ret16, ema821, ema2150, _rsi(cc) - 0.5, volume_z, vol_ratio, atr_pct, drawdown16]
    elif part_id == "part6_trend":
        ups = sum(max(hh[i] - hh[i - 1], 0.0) for i in range(n - 14, n))
        downs = sum(max(ll[i - 1] - ll[i], 0.0) for i in range(n - 14, n))
        imbalance = _safe_div(ups - downs, ups + downs)
        vals = [ema821, ema2150, slope16, slope32, _safe_div(ups, price), _safe_div(downs, price), imbalance, ret4, ret16, range_pos32, vol_ratio, atr_pct]
    elif part_id == "part7_volatility":
        vals = [ret8std, ret32std, vol_ratio, atr_pct, _safe_div(atr14, atr50), range_atr, range_expansion, ret(1), abs(ret4), abs(ret16), body_ratio, volume_z]
    elif part_id == "part8_structure":
        vals = [break_hi20, break_lo20, break_hi50, break_lo50, highgap(50), lowgap(50), range_pos20, range_pos50, slope16, ret4, atr_pct, volume_z]
    elif part_id == "part9_orderflow":
        vals = [flow4, flow12, flow_return_divergence, _slope(flow[-12:]), ret4, ret16, volume_z, volume_ratio, range_atr, bodies[-1], flow12 - ret16 * 100.0, atr_pct]
    else:  # Part 10 candle statistics
        vals = [body_ratio, bodies[-1] - prev_body, (same_streak - 1) / 7.0, transition, green_fraction, range_atr, ret(1), ret4, ret16, drawdown16, volume_z, vol_ratio]
    if len(vals) != len(FEATURE_NAMES[part_id]):
        raise ValueError("feature_schema_internal_error")
    return tuple(_clip(float(v)) for v in vals)


def _identity(context: Mapping[str, Any]) -> Optional[Dict[str, str]]:
    identity = context.get("analysis_identity") or context.get("identity")
    if isinstance(identity, Mapping):
        raw = (identity.get("venue"), identity.get("market_type"), identity.get("instrument_id"), identity.get("symbol"))
    elif isinstance(identity, (list, tuple)) and len(identity) == 4:
        raw = tuple(identity)
    else:
        return None
    venue, market_type, instrument_id, symbol = (str(x or "").strip() for x in raw)
    tf = str(context.get("timeframe") or "").strip()
    expected_symbol = str(context.get("selected_symbol") or context.get("symbol") or "").strip()
    if not all((venue, market_type, instrument_id, symbol, tf)) or tf not in _TIMEFRAME_SECONDS:
        return None
    if venue.lower() in ("unknown", "none", "null") or market_type.lower() in ("unknown", "none", "null"):
        return None
    if symbol.upper() != expected_symbol.upper():
        return None
    return {"venue": venue.lower(), "market_type": market_type.lower(),
            "instrument_id": instrument_id, "symbol": symbol.upper(), "timeframe": tf}


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "_", value)[:80] or "_"


def artifact_path(identity: Mapping[str, str], part_id: str, root: Optional[str] = None) -> Path:
    if part_id not in FEATURE_NAMES:
        raise ValueError("unknown_part_id")
    folder = Path(root or os.environ.get("JARVIS_NEURAL_ARTIFACT_DIR", "models/advisory"))
    name = "__".join([part_id, identity["venue"], identity["market_type"], identity["instrument_id"], identity["symbol"], identity["timeframe"]])
    return folder / (_slug(name) + ".json")


def _finite_vector(value: Any, expected: int, name: str) -> Tuple[float, ...]:
    if not isinstance(value, list) or len(value) != expected:
        raise ValueError("invalid_" + name)
    out = tuple(float(x) for x in value)
    if not all(math.isfinite(x) for x in out):
        raise ValueError("non_finite_" + name)
    if any(abs(x) > _MAX_NUMERIC_ARTIFACT_VALUE for x in out):
        raise ValueError("artifact_numeric_value_out_of_bounds")
    return out


def _load_artifact(path: Path, part_id: str, identity: Mapping[str, str]) -> Dict[str, Any]:
    st = path.stat()
    if st.st_size <= 0 or st.st_size > _MAX_ARTIFACT_BYTES:
        raise ValueError("artifact_size_invalid")
    raw = path.read_bytes()
    if len(raw) != st.st_size:
        raise ValueError("artifact_changed_during_read")
    digest = hashlib.sha256(raw).hexdigest()
    # Identity is part of the cache key as well as an artifact field check.
    # This prevents a colliding/truncated path from reusing another identity's
    # already-cached model without re-validating its metadata.
    key = (str(path.resolve()), digest, st.st_size, part_id, tuple(sorted(identity.items())))
    with _LOCK:
        cached = _ARTIFACT_CACHE.get(key)
        if cached is not None:
            _ARTIFACT_CACHE.move_to_end(key)
            return cached
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict) or obj.get("format") != FORMAT or obj.get("format_version") != FORMAT_VERSION:
        raise ValueError("artifact_format_unsupported")
    if obj.get("feature_schema") != FEATURE_SCHEMA or obj.get("part_id") != part_id:
        raise ValueError("artifact_feature_schema_or_part_mismatch")
    if obj.get("identity") != dict(identity):
        raise ValueError("artifact_identity_mismatch")
    if obj.get("feature_names") != list(FEATURE_NAMES[part_id]):
        raise ValueError("artifact_feature_names_mismatch")
    norm = obj.get("normalization")
    if not isinstance(norm, dict):
        raise ValueError("artifact_normalization_missing")
    mean = _finite_vector(norm.get("mean"), 12, "normalization_mean")
    std = _finite_vector(norm.get("std"), 12, "normalization_std")
    if any(x <= 0 for x in std):
        raise ValueError("artifact_normalization_std_invalid")
    layers = obj.get("layers")
    if not isinstance(layers, list) or len(layers) != 2:
        raise ValueError("artifact_architecture_invalid")
    expected = ((16, 12), (3, 16))
    parsed_layers = []
    for layer, (out_dim, in_dim), act in zip(layers, expected, ("relu", "linear")):
        if not isinstance(layer, dict) or layer.get("activation") != act:
            raise ValueError("artifact_activation_invalid")
        weights = layer.get("weights")
        if not isinstance(weights, list) or len(weights) != out_dim:
            raise ValueError("artifact_weights_invalid")
        w = tuple(_finite_vector(row, in_dim, "weights") for row in weights)
        b = _finite_vector(layer.get("bias"), out_dim, "bias")
        parsed_layers.append((w, b, act))
    training = obj.get("training")
    if not isinstance(training, dict) or training.get("status") != "validated" or training.get("split") != "chronological_purged" or training.get("approved_for_advisory") is not True:
        raise ValueError("artifact_not_validation_gated")
    digest = training.get("dataset_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("artifact_dataset_provenance_missing")
    if not isinstance(training.get("trainer_version"), str) or not training.get("trainer_version"):
        raise ValueError("artifact_trainer_version_missing")
    try:
        trained_at = datetime.fromisoformat(str(training.get("trained_at_utc")).replace("Z", "+00:00"))
        if trained_at.tzinfo is None:
            raise ValueError
    except Exception as exc:
        raise ValueError("artifact_training_time_invalid") from exc
    try:
        dataset_last_timestamp = float(training.get("dataset_last_timestamp"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("artifact_dataset_cutoff_missing") from exc
    if not math.isfinite(dataset_last_timestamp) or dataset_last_timestamp <= 0:
        raise ValueError("artifact_dataset_cutoff_invalid")
    trained_epoch = trained_at.timestamp()
    interval = _TIMEFRAME_SECONDS[identity["timeframe"]]
    if dataset_last_timestamp > trained_epoch + interval:
        raise ValueError("artifact_dataset_cutoff_after_training")
    for key_name in ("train_samples", "validation_samples", "test_samples"):
        value = training.get(key_name)
        if not isinstance(value, int) or value < (200 if key_name == "train_samples" else 50):
            raise ValueError("artifact_sample_count_below_minimum")
    for m in ("validation_accuracy", "validation_majority_accuracy", "test_accuracy", "test_majority_accuracy"):
        value = training.get(m)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError("artifact_metrics_invalid")
    if (training["validation_accuracy"] < training["validation_majority_accuracy"] + 0.02
            or training["test_accuracy"] < training["test_majority_accuracy"] + 0.02):
        raise ValueError("artifact_out_of_sample_gate_failed")
    model = {"mean": mean, "std": std, "layers": tuple(parsed_layers), "training": training}
    with _LOCK:
        _ARTIFACT_CACHE[key] = model
        _ARTIFACT_CACHE.move_to_end(key)
        while len(_ARTIFACT_CACHE) > _MAX_ARTIFACTS:
            _ARTIFACT_CACHE.popitem(last=False)
    return model


def _index_time(data: Any) -> Optional[float]:
    try:
        if isinstance(data, (list, tuple)) and data:
            value = data[-1].get("timestamp", data[-1].get("time"))
        elif hasattr(data, "index") and not callable(data.index) and len(data.index):
            value = data.index[-1]
        else:
            return None
        if hasattr(value, "timestamp"):
            return float(value.timestamp())
        if isinstance(value, (int, float)):
            return float(value if value > 1e12 else value * 1000.0)
        if isinstance(value, str):
            text = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
    except Exception:
        return None
    return None


def _timestamp_epoch(value: Any) -> float:
    if hasattr(value, "timestamp"):
        return float(value.timestamp())
    if isinstance(value, (int, float)):
        stamp = float(value)
        return stamp / 1000.0 if stamp > 1e12 else stamp
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    raise ValueError("closed_candle_timestamp_missing")


def _validate_closed_series(data: Any, interval: int) -> None:
    if isinstance(data, (list, tuple)):
        if len(data) < 64 or any(not isinstance(row, Mapping) for row in data[-64:]):
            raise ValueError("insufficient_closed_candles")
        tail = data[-64:]
        stamps = [_timestamp_epoch(row.get("timestamp", row.get("time"))) for row in tail]
        closed_values = [row.get("is_closed", True) for row in tail]
    elif hasattr(data, "index") and not callable(data.index):
        tail = data.tail(64)
        if len(tail) < 64:
            raise ValueError("insufficient_closed_candles")
        stamps = [_timestamp_epoch(value) for value in tail.index]
        closed_values = tail["is_closed"].tolist() if "is_closed" in tail.columns else [True] * 64
    else:
        raise ValueError("closed_candle_timestamp_missing")
    if not all(math.isfinite(stamp) for stamp in stamps):
        raise ValueError("closed_candle_timestamp_invalid")
    if any(current <= previous or abs((current - previous) - interval) > 2.0
           for previous, current in zip(stamps, stamps[1:])):
        raise ValueError("closed_candle_sequence_invalid")
    if any(str(value).strip().lower() not in ("1", "true", "yes")
           for value in closed_values):
        raise ValueError("forming_candle_rejected")


def _softmax(logits: Sequence[float]) -> Tuple[float, float, float]:
    if len(logits) != 3 or not all(math.isfinite(x) for x in logits):
        raise ValueError("non_finite_inference")
    m = max(logits)
    exps = [math.exp(max(-80.0, min(80.0, x - m))) for x in logits]
    den = sum(exps)
    return tuple(x / den for x in exps)  # sell, neutral, buy


def _infer(model: Mapping[str, Any], vector: Sequence[float]) -> Tuple[float, float, float]:
    x = [max(-8.0, min(8.0, (v - m) / s)) for v, m, s in zip(vector, model["mean"], model["std"])]
    for weights, bias, activation in model["layers"]:
        x = [sum(wi * xi for wi, xi in zip(row, x)) + b for row, b in zip(weights, bias)]
        if not all(math.isfinite(v) for v in x):
            raise ValueError("non_finite_inference")
        if activation == "relu":
            x = [max(0.0, v) for v in x]
    return _softmax(x)


def predict_advisory(data: Any, part_id: str, context: Optional[Mapping[str, Any]] = None,
                     *, now: Optional[float] = None, artifact_dir: Optional[str] = None) -> Dict[str, Any]:
    """Return an explicit status; unavailable/malformed artifacts never infer."""
    c = context if isinstance(context, Mapping) else {}
    if part_id not in FEATURE_NAMES:
        return {"status": "unavailable", "reason": "unknown_part_id"}
    identity = _identity(c)
    if identity is None:
        return {"status": "unavailable", "reason": "full_analysis_identity_required"}
    if not bool(c.get("is_backtest_mode")):
        fetched = c.get("snapshot_fetched_at")
        try:
            fetched = float(fetched)
        except (TypeError, ValueError, OverflowError):
            return {"status": "unavailable", "reason": "snapshot_freshness_missing"}
        if not math.isfinite(fetched) or abs((now if now is not None else time.time()) - fetched) > 180.0:
            return {"status": "unavailable", "reason": "stale_snapshot"}
    ts = _index_time(data)
    if ts is None:
        return {"status": "unavailable", "reason": "closed_candle_timestamp_missing"}
    is_backtest = bool(c.get("is_backtest_mode"))
    if not is_backtest:
        interval = _TIMEFRAME_SECONDS[identity["timeframe"]]
        if (now if now is not None else time.time()) - ts > 3 * interval + 120 or ts > (now if now is not None else time.time()) + 30:
            return {"status": "unavailable", "reason": "closed_candles_stale_or_future"}
    try:
        _validate_closed_series(data, _TIMEFRAME_SECONDS[identity["timeframe"]])
        attrs = getattr(data, "attrs", {}) or {}
        if attrs.get("symbol") and str(attrs["symbol"]).upper() != identity["symbol"]:
            return {"status": "unavailable", "reason": "frame_symbol_mismatch"}
        if attrs.get("timeframe") and str(attrs["timeframe"]) != identity["timeframe"]:
            return {"status": "unavailable", "reason": "frame_timeframe_mismatch"}
        vector = feature_vector(part_id, data)
        path = artifact_path(identity, part_id, artifact_dir)
        try:
            st = path.stat()
        except FileNotFoundError:
            return {"status": "unavailable", "reason": "trained_artifact_missing"}
        cache_key = (part_id, tuple(identity.items()), ts, tuple(vector), str(path.resolve()), st.st_mtime_ns, st.st_size)
        with _LOCK:
            cached = _PREDICTION_CACHE.get(cache_key)
            if cached is not None:
                _PREDICTION_CACHE.move_to_end(cache_key)
                return dict(cached)
        model = _load_artifact(path, part_id, identity)
        evaluation_time = now if now is not None else time.time()
        training = model["training"]
        trained_at = datetime.fromisoformat(str(training["trained_at_utc"]).replace("Z", "+00:00")).timestamp()
        dataset_last_timestamp = float(training["dataset_last_timestamp"])
        if trained_at > evaluation_time + 300.0:
            return {"status": "unavailable", "reason": "artifact_training_time_in_future"}
        if ts <= dataset_last_timestamp:
            return {"status": "unavailable", "reason": "artifact_training_data_overlap"}
        if is_backtest and trained_at > ts:
            return {"status": "unavailable", "reason": "artifact_not_available_at_backtest_time"}
        if not is_backtest and evaluation_time - dataset_last_timestamp > _MAX_TRAINING_DATA_AGE_SECONDS:
            return {"status": "unavailable", "reason": "stale_artifact_training_data"}
        with _INFERENCE_SLOT:
            # Recheck inside the single inference slot so concurrent repeats of
            # one identity/candle cannot trigger duplicate model executions.
            with _LOCK:
                cached = _PREDICTION_CACHE.get(cache_key)
                if cached is not None:
                    _PREDICTION_CACHE.move_to_end(cache_key)
                    return dict(cached)
            scores = _infer(model, vector)
            max_score = max(scores)
            direction = "SELL" if scores[0] == max_score else "BUY" if scores[2] == max_score else "NEUTRAL"
            if max_score < 0.55:
                direction = "NEUTRAL"
            result = {"status": "available", "direction": direction,
                      "scores_uncalibrated": {"sell": scores[0], "neutral": scores[1], "buy": scores[2]},
                      "role": "advisory_only_no_execution_authority",
                      "model_version": str(model["training"].get("model_version", "1"))}
            with _LOCK:
                _PREDICTION_CACHE[cache_key] = result
                _PREDICTION_CACHE.move_to_end(cache_key)
                while len(_PREDICTION_CACHE) > _MAX_PREDICTIONS:
                    _PREDICTION_CACHE.popitem(last=False)
        return dict(result)
    except Exception as exc:
        reason = str(exc) if str(exc) and re.fullmatch(r"[a-zA-Z0-9_-]{1,96}", str(exc)) else "artifact_or_feature_validation_failed"
        return {"status": "unavailable", "reason": reason}


def annotate_part_result(result: Any, data: Any, part_id: str,
                         context: Optional[Mapping[str, Any]] = None,
                         *, artifact_dir: Optional[str] = None,
                         now: Optional[float] = None) -> Any:
    """Attach diagnostic-only model metadata without touching deterministic fields."""
    if not isinstance(result, dict):
        return result
    out = dict(result)
    out["neural_advisory"] = predict_advisory(data, part_id, context, now=now, artifact_dir=artifact_dir)
    return out


def not_applicable_result(part_id: str) -> Dict[str, str]:
    return {"status": "not_applicable", "reason": f"{part_id} is deterministic fusion/confidence, not an independent predictor",
            "role": "diagnostic_only"}


def clear_caches() -> None:
    """Test/support hook; caches are bounded regardless of caller use."""
    with _LOCK:
        _ARTIFACT_CACHE.clear()
        _PREDICTION_CACHE.clear()

"""Bounded advisory runtime for twelve task-specific, identity-bound models.

CPU inference is the default. PyTorch/CUDA is imported only when explicitly
requested, and every result discloses the actual execution device or fallback.
Only validated local JSON weights can produce advisory-only outputs.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import inspect
from functools import wraps
import json
import math
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

FORMAT = "jarvis-advisory-task-model"
FORMAT_VERSION = 3
FEATURE_SCHEMA = "jarvis-task-specific-features-v4-quantitative"
from neural_parts import PARTS, FEATURE_NAMES, MODEL_SPECS, TASKS, prepare_features
from neural_parts.common import TIMEFRAMES, mtf_signal_matrix as _mtf_signal_matrix
_TIMEFRAME_SECONDS = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400}
_MAX_ARTIFACT_BYTES = 128 * 1024
_MAX_ARTIFACTS = 16             # CPU metadata/weights only; never a default GPU-resident set
_MAX_GPU_CACHED_MODELS = 1       # One small task model resident on CUDA at a time
_MAX_PREDICTIONS = 256
# Re-train rather than keep using a predictor whose source history is too old.
_MAX_TRAINING_DATA_AGE_SECONDS = 90 * 24 * 60 * 60
_MAX_NUMERIC_ARTIFACT_VALUE = 1_000_000.0
_LOCK = threading.RLock()
_GPU_LOCK = threading.RLock()
_INFERENCE_SLOT = threading.BoundedSemaphore(1)  # serializes CPU/CUDA inference
_ARTIFACT_CACHE: "OrderedDict[Tuple[Any, ...], Dict[str, Any]]" = OrderedDict()
_PREDICTION_CACHE: "OrderedDict[Tuple[Any, ...], Dict[str, Any]]" = OrderedDict()
_GPU_MODEL_CACHE_KEY: Optional[Tuple[Any, ...]] = None
_GPU_MODEL_CACHE_LAYERS: Optional[Tuple[Any, ...]] = None


def feature_vector(part_id: str, data: Any) -> Tuple[float, ...]:
    """Dispatch to the named Part-owned feature projection."""
    if part_id not in FEATURE_NAMES:
        raise ValueError("unknown_part_id")
    values = prepare_features(part_id, data)
    if len(values) != len(FEATURE_NAMES[part_id]) or not all(math.isfinite(float(v)) for v in values):
        raise ValueError("feature_schema_internal_error")
    return tuple(float(v) for v in values)


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


def validate_mtf_evidence(evidence: Any, identity: Mapping[str, str],
                         analysis_timestamp: float, *, now: Optional[float] = None,
                         is_backtest: bool = False) -> None:
    """Fail closed on incomplete, cross-symbol or stale 8×10 Part matrices."""
    if not isinstance(evidence, Mapping) or not isinstance(evidence.get("frames"), Mapping):
        raise ValueError("mtf_evidence_envelope_required")
    expected_identity = {k: identity[k] for k in ("venue", "market_type", "instrument_id", "symbol")}
    provided = evidence.get("identity")
    if not isinstance(provided, Mapping) or dict(provided) != expected_identity:
        raise ValueError("mtf_evidence_identity_mismatch")
    if str(evidence.get("symbol", "")).upper() != identity["symbol"].upper():
        raise ValueError("mtf_evidence_symbol_mismatch")
    timestamps = evidence.get("closed_timestamps")
    frames = evidence["frames"]
    if not isinstance(timestamps, Mapping) or set(timestamps) != set(TIMEFRAMES):
        raise ValueError("mtf_evidence_timestamp_coverage_invalid")
    if set(frames) != set(TIMEFRAMES):
        raise ValueError("incomplete_eight_frame_evidence")
    evaluation_time = now if now is not None else time.time()
    for tf in TIMEFRAMES:
        stamp = _timestamp_epoch(timestamps[tf])
        interval = _TIMEFRAME_SECONDS[tf]
        if stamp > analysis_timestamp + interval + 2.0:
            raise ValueError("mtf_frame_timestamp_after_analysis")
        if not is_backtest and (stamp > evaluation_time + 30.0 or evaluation_time - stamp > 3 * interval + 120.0):
            raise ValueError("mtf_frame_stale_or_future")
        frame = frames[tf]
        if not isinstance(frame, Mapping):
            raise ValueError("invalid_frame_evidence")
        for part in PARTS[:10]:
            result = frame.get(part)
            if not isinstance(result, Mapping):
                raise ValueError("missing_part_evidence")
            if result.get("symbol") and str(result["symbol"]).upper() != identity["symbol"].upper():
                raise ValueError("evidence_symbol_mismatch")
            if result.get("timeframe") and str(result["timeframe"]) != tf:
                raise ValueError("evidence_timeframe_mismatch")
    _mtf_signal_matrix(evidence)


def build_mtf_advisory_evidence(part_results: Any, candle_frames: Any,
                                context: Mapping[str, Any]) -> Dict[str, Any]:
    """Create an isolated envelope without mutating deterministic Part results."""
    identity = _identity(context)
    if identity is None or not isinstance(part_results, Mapping) or not isinstance(candle_frames, Mapping):
        raise ValueError("mtf_evidence_context_invalid")
    if set(part_results) != set(TIMEFRAMES) or set(candle_frames) != set(TIMEFRAMES):
        raise ValueError("incomplete_eight_frame_evidence")
    stamps = {}
    for tf in TIMEFRAMES:
        frame = candle_frames[tf]
        if not hasattr(frame, "index") or not len(frame.index):
            raise ValueError("mtf_closed_frame_timestamp_missing")
        stamps[tf] = _timestamp_epoch(frame.index[-1])
    payload = {"identity": {k: identity[k] for k in ("venue", "market_type", "instrument_id", "symbol")},
               "symbol": identity["symbol"], "closed_timestamps": stamps,
               "frames": {tf: dict(part_results[tf]) for tf in TIMEFRAMES}}
    return payload


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
    spec = MODEL_SPECS[part_id]
    contract = {"task": spec["task"], "dims": list(spec["dims"]),
                "activations": list(spec["acts"]), "labels": list(spec["labels"]), "kind": spec["kind"]}
    if obj.get("model_contract") != contract:
        raise ValueError("artifact_model_contract_mismatch")
    norm = obj.get("normalization")
    if not isinstance(norm, dict):
        raise ValueError("artifact_normalization_missing")
    input_dim = len(FEATURE_NAMES[part_id])
    mean = _finite_vector(norm.get("mean"), input_dim, "normalization_mean")
    std = _finite_vector(norm.get("std"), input_dim, "normalization_std")
    if any(x <= 0 for x in std):
        raise ValueError("artifact_normalization_std_invalid")
    layers = obj.get("layers")
    dims, acts = spec["dims"], spec["acts"]
    if not isinstance(layers, list) or len(layers) != len(dims) - 1:
        raise ValueError("artifact_architecture_invalid")
    parsed_layers = []
    for layer, in_dim, out_dim, act in zip(layers, dims[:-1], dims[1:], acts):
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
    model = {"mean": mean, "std": std, "layers": tuple(parsed_layers),
             "training": training, "artifact_cache_key": key}
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
    # Reject non-finite raw OHLCV explicitly before quantitative projection so
    # malformed bars cannot be misreported as merely insufficient history.
    if isinstance(data, (list, tuple)):
        for row in data[-64:]:
            for field in ("open", "high", "low", "close", "volume"):
                raw = row.get(field, 0.0)
                try:
                    value = float(raw)
                except (TypeError, ValueError, OverflowError) as exc:
                    raise ValueError("invalid_ohlcv") from exc
                if not math.isfinite(value):
                    raise ValueError("non_finite_ohlcv")


def _softmax(logits: Sequence[float]) -> Tuple[float, ...]:
    if len(logits) < 2 or not all(math.isfinite(x) for x in logits):
        raise ValueError("non_finite_inference")
    m = max(logits)
    exps = [math.exp(max(-80.0, min(80.0, x - m))) for x in logits]
    den = sum(exps)
    return tuple(x / den for x in exps)


def _device_config() -> Tuple[str, bool, Optional[str]]:
    raw = os.environ.get("JARVIS_NEURAL_DEVICE")
    if raw is None:
        raw = "cuda" if os.environ.get("JARVIS_NEURAL_GPU", "0") == "1" else "cpu"
    requested = str(raw).strip().lower()
    strict = os.environ.get("JARVIS_NEURAL_REQUIRE_GPU", "0") == "1"
    if strict:
        requested = "cuda"
    if requested not in ("cpu", "cuda"):
        return requested, strict, "invalid_device_configuration"
    return requested, strict, None


def _resolve_device() -> Tuple[Dict[str, Any], Any]:
    """Resolve actual compute without allocating model tensors; CPU default imports no Torch."""
    requested, strict, config_error = _device_config()
    common = {"requested_device": requested, "strict_gpu": strict,
              "gpu_model_cache_limit": _MAX_GPU_CACHED_MODELS, "max_concurrent_inferences": 1}
    if config_error:
        return {**common, "inference_device": "unavailable", "device_name": None,
                "fallback_reason": config_error}, None
    if requested == "cpu":
        return {**common, "inference_device": "cpu", "device_name": "CPU",
                "fallback_reason": None}, None
    try:
        import torch  # deliberately lazy: do not import/initialize CUDA in default CPU mode
    except Exception:
        reason = "pytorch_cuda_unavailable"
        return {**common, "inference_device": "unavailable" if strict else "cpu",
                "device_name": None, "fallback_reason": reason}, None
    try:
        if not torch.cuda.is_available():
            reason = "cuda_device_unavailable"
            return {**common, "inference_device": "unavailable" if strict else "cpu",
                    "device_name": None, "fallback_reason": reason}, torch
        device = torch.device("cuda:0")
        try:
            free_bytes, total_bytes = torch.cuda.mem_get_info(device)
        except TypeError:
            free_bytes, total_bytes = torch.cuda.mem_get_info()
        except Exception:
            # No reliable free-memory telemetry means do not allocate on CUDA.
            reason = "cuda_memory_status_unavailable"
            return {**common, "inference_device": "unavailable" if strict else "cpu",
                    "device_name": None, "fallback_reason": reason}, torch
        try:
            min_free_mb = int(os.environ.get("JARVIS_NEURAL_GPU_MIN_FREE_MB", "256"))
        except (TypeError, ValueError):
            min_free_mb = 256
        min_free_mb = max(64, min(min_free_mb, 2048))
        free_mb, total_mb = int(free_bytes // (1024 * 1024)), int(total_bytes // (1024 * 1024))
        if free_mb < min_free_mb:
            reason = "cuda_free_memory_below_safety_floor"
            return {**common, "inference_device": "unavailable" if strict else "cpu",
                    "device_name": None, "gpu_free_mb": free_mb, "gpu_total_mb": total_mb,
                    "fallback_reason": reason}, torch
        try:
            name = str(torch.cuda.get_device_name(device))
        except Exception:
            name = "CUDA device 0"
        return {**common, "inference_device": "cuda:0", "device_name": name,
                "gpu_free_mb": free_mb, "gpu_total_mb": total_mb, "fallback_reason": None}, torch
    except Exception:
        reason = "cuda_runtime_unavailable"
        return {**common, "inference_device": "unavailable" if strict else "cpu",
                "device_name": None, "fallback_reason": reason}, torch


def get_neural_runtime_status() -> Dict[str, Any]:
    """Read-only device/capacity status; CUDA is probed only when explicitly requested."""
    status, _ = _resolve_device()
    return dict(status)


def _gpu_layers(model: Mapping[str, Any], torch: Any) -> Tuple[Any, ...]:
    """Materialize only one artifact's tiny tensors on CUDA; callers hold the inference slot."""
    global _GPU_MODEL_CACHE_KEY, _GPU_MODEL_CACHE_LAYERS
    key = model.get("artifact_cache_key")
    with _GPU_LOCK:
        if key == _GPU_MODEL_CACHE_KEY and _GPU_MODEL_CACHE_LAYERS is not None:
            return _GPU_MODEL_CACHE_LAYERS
        # Drop references to a prior Part model before loading another. This is
        # intentionally a one-model cache even though the CPU artifact cache is larger.
        _GPU_MODEL_CACHE_KEY = None
        _GPU_MODEL_CACHE_LAYERS = None
        torch.set_num_threads(1)
        device = torch.device("cuda:0")
        created = []
        for weights, bias, activation in model["layers"]:
            created.append((torch.tensor(weights, dtype=torch.float32, device=device),
                            torch.tensor(bias, dtype=torch.float32, device=device), activation))
        _GPU_MODEL_CACHE_KEY = key
        _GPU_MODEL_CACHE_LAYERS = tuple(created)
        return _GPU_MODEL_CACHE_LAYERS


def _cpu_forward(model: Mapping[str, Any], vector: Sequence[float]) -> list[float]:
    x = [max(-8.0, min(8.0, (v - m) / s)) for v, m, s in zip(vector, model["mean"], model["std"])]
    for weights, bias, activation in model["layers"]:
        x = [sum(wi * xi for wi, xi in zip(row, x)) + b for row, b in zip(weights, bias)]
        if not all(math.isfinite(v) for v in x):
            raise ValueError("non_finite_inference")
        if activation == "relu":
            x = [max(0.0, v) for v in x]
        elif activation == "tanh":
            x = [math.tanh(v) for v in x]
        elif activation != "linear":
            raise ValueError("unsupported_artifact_activation")
    return x


def _infer(model: Mapping[str, Any], vector: Sequence[float], part_id: str,
           device_status: Optional[Mapping[str, Any]] = None, torch_module: Any = None) -> Tuple[Tuple[float, ...], Dict[str, Any]]:
    status = dict(device_status or _resolve_device()[0])
    strict = bool(status.get("strict_gpu"))
    raw = None
    if status.get("inference_device") == "cuda:0":
        try:
            torch = torch_module
            if torch is None:
                import torch as torch_local
                torch = torch_local
            layers = _gpu_layers(model, torch)
            normalized = [max(-8.0, min(8.0, (v - m) / s))
                          for v, m, s in zip(vector, model["mean"], model["std"])]
            with torch.inference_mode():
                x = torch.tensor(normalized, dtype=torch.float32, device=torch.device("cuda:0"))
                for weights, bias, activation in layers:
                    x = torch.matmul(x, weights.t()) + bias
                    if activation == "relu":
                        x = torch.relu(x)
                    elif activation == "tanh":
                        x = torch.tanh(x)
                    elif activation != "linear":
                        raise ValueError("unsupported_artifact_activation")
                raw = x.detach().cpu().tolist()
            if not all(math.isfinite(float(v)) for v in raw):
                raise ValueError("non_finite_inference")
        except Exception as exc:
            global _GPU_MODEL_CACHE_KEY, _GPU_MODEL_CACHE_LAYERS
            with _GPU_LOCK:
                _GPU_MODEL_CACHE_KEY = None
                _GPU_MODEL_CACHE_LAYERS = None
            try:
                if torch_module is not None and torch_module.cuda.is_available():
                    torch_module.cuda.empty_cache()
            except Exception:
                pass
            if strict:
                raise ValueError("gpu_required_inference_failed") from exc
            raw = _cpu_forward(model, vector)
            status["inference_device"] = "cpu"
            status["device_name"] = "CPU fallback"
            status["fallback_reason"] = "cuda_inference_failed"
    elif status.get("inference_device") == "unavailable":
        raise ValueError("gpu_required_unavailable" if strict else "neural_device_unavailable")
    else:
        raw = _cpu_forward(model, vector)
    spec = MODEL_SPECS[part_id]
    if spec["kind"] == "sigmoid":
        if len(raw) != 1:
            raise ValueError("binary_head_shape_invalid")
        z = max(-80.0, min(80.0, float(raw[0])))
        probability_like_score = 1.0 / (1.0 + math.exp(-z))
        scores = (1.0 - probability_like_score, probability_like_score)
    else:
        scores = _softmax([float(v) for v in raw])
        if len(scores) != len(spec["labels"]):
            raise ValueError("classification_head_shape_invalid")
    return scores, status

def predict_advisory(data: Any, part_id: str, context: Optional[Mapping[str, Any]] = None,
                     *, now: Optional[float] = None, artifact_dir: Optional[str] = None) -> Dict[str, Any]:
    """Return an explicit status; unavailable/malformed artifacts never infer."""
    c = context if isinstance(context, Mapping) else {}
    device_status, torch_module = _resolve_device()
    if device_status.get("inference_device") == "unavailable":
        return {"status": "unavailable",
                "reason": str(device_status.get("fallback_reason") or "neural_device_unavailable"),
                "requested_device": device_status.get("requested_device"),
                "inference_device": "unavailable"}
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
    is_mtf_model = part_id in ("part11_fusion", "part12_confidence")
    try:
        ts = _timestamp_epoch(c.get("closed_candle_timestamp")) if c.get("closed_candle_timestamp") is not None else _index_time(data)
    except Exception:
        ts = None
    if ts is None:
        return {"status": "unavailable", "reason": "closed_candle_timestamp_missing"}
    is_backtest = bool(c.get("is_backtest_mode"))
    if not is_backtest:
        interval = _TIMEFRAME_SECONDS[identity["timeframe"]]
        if (now if now is not None else time.time()) - ts > 3 * interval + 120 or ts > (now if now is not None else time.time()) + 30:
            return {"status": "unavailable", "reason": "closed_candles_stale_or_future"}
    try:
        if not is_mtf_model:
            _validate_closed_series(data, _TIMEFRAME_SECONDS[identity["timeframe"]])
        else:
            # Each separate MTF head requires provenance, all eight closed
            # frames, ten named Part outputs per frame, and current timestamps.
            validate_mtf_evidence(data, identity, ts, now=now, is_backtest=is_backtest)
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
            scores, execution_status = _infer(model, vector, part_id, device_status, torch_module)
            spec = MODEL_SPECS[part_id]
            labels = spec["labels"]
            max_score = max(scores)
            winning_index = max(range(len(scores)), key=lambda i: scores[i])
            prediction = labels[winning_index] if max_score >= 0.55 else "uncertain"
            result = {"status": "available", "task": spec["task"],
                      "prediction": prediction,
                      "scores_uncalibrated": {label: scores[i] for i, label in enumerate(labels)},
                      "head_kind": spec["kind"],
                      "role": "advisory_only_no_execution_authority",
                      "requested_device": execution_status.get("requested_device"),
                      "inference_device": execution_status.get("inference_device"),
                      "device_name": execution_status.get("device_name"),
                      "gpu_free_mb": execution_status.get("gpu_free_mb"),
                      "gpu_total_mb": execution_status.get("gpu_total_mb"),
                      "fallback_reason": execution_status.get("fallback_reason"),
                      "model_version": str(model["training"].get("model_version", "3")),
                      "task_output": TASKS[part_id].interpret_scores(scores, prediction)}
            if part_id == "part11_fusion":
                result["direction"] = {"sell": "SELL", "neutral": "NEUTRAL", "buy": "BUY"}.get(prediction, "NEUTRAL")
            if part_id == "part12_confidence":
                result["consensus_correctness_score_uncalibrated"] = scores[1]
            with _LOCK:
                _PREDICTION_CACHE[cache_key] = result
                _PREDICTION_CACHE.move_to_end(cache_key)
                while len(_PREDICTION_CACHE) > _MAX_PREDICTIONS:
                    _PREDICTION_CACHE.popitem(last=False)
        return dict(result)
    except Exception as exc:
        reason = str(exc) if str(exc) and re.fullmatch(r"[a-zA-Z0-9_-]{1,96}", str(exc)) else "artifact_or_feature_validation_failed"
        return {"status": "unavailable", "reason": reason}


def part_advisory_entry(part_id: str, *, data_parameter: str = "data",
                        context_parameter: str = "context",
                        evidence_context_key: Optional[str] = None):
    """Decorate an original Part analyzer entry so it owns its advisory call.

    The deterministic function runs first and its result fields are copied without
    edits. MTF Parts 11/12 take their task evidence from the explicitly named
    context envelope. A pre-existing advisory is not recomputed or overwritten.
    """
    if part_id not in FEATURE_NAMES:
        raise ValueError("unknown_part_id")
    def decorate(function):
        signature = inspect.signature(function)
        @wraps(function)
        def wrapped(*args, **kwargs):
            bound = signature.bind_partial(*args, **kwargs)
            result = function(*args, **kwargs)
            if not isinstance(result, dict) or "neural_advisory" in result:
                return result
            context_value = bound.arguments.get(context_parameter)
            context = dict(context_value) if isinstance(context_value, Mapping) else {}
            data = context.get(evidence_context_key) if evidence_context_key else bound.arguments.get(data_parameter)
            out = dict(result)
            out["neural_advisory"] = predict_advisory(data, part_id, context)
            return out
        return wrapped
    return decorate

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


def annotate_mtf_result(result: Any, evidence: Any, part_id: str,
                        context: Optional[Mapping[str, Any]] = None,
                        *, artifact_dir: Optional[str] = None,
                        now: Optional[float] = None) -> Any:
    """Attach a task-specific advisory to Parts 11/12 from the full 8×10 matrix."""
    if part_id not in ("part11_fusion", "part12_confidence"):
        raise ValueError("mtf_advisory_only_for_parts_11_12")
    if not isinstance(result, dict):
        return result
    out = dict(result)
    out["neural_advisory"] = predict_advisory(evidence, part_id, context, now=now, artifact_dir=artifact_dir)
    return out


def not_applicable_result(part_id: str) -> Dict[str, str]:
    return {"status": "unavailable", "reason": f"{part_id}_requires_trained_task_artifact",
            "role": "advisory_only_no_execution_authority"}


def clear_caches() -> None:
    """Test/support hook; caches are bounded regardless of caller use."""
    global _GPU_MODEL_CACHE_KEY, _GPU_MODEL_CACHE_LAYERS
    with _LOCK:
        _ARTIFACT_CACHE.clear()
        _PREDICTION_CACHE.clear()
    with _GPU_LOCK:
        _GPU_MODEL_CACHE_KEY = None
        _GPU_MODEL_CACHE_LAYERS = None

#!/usr/bin/env python3
"""Offline chronological trainer for one Part's tiny advisory MLP.

No network/API/bot calls are made. A JSON artifact is written only after strict
chronological holdout checks pass. The target is an OHLCV forward-return proxy,
not a strategy PnL target, calibrated probability, or evidence of profitability.
Requires locally installed PyTorch; CPU is the conservative default.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import tempfile
from typing import Any, Dict, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from neural_advisory import (FEATURE_NAMES, FEATURE_SCHEMA, FORMAT, FORMAT_VERSION,
                             _TIMEFRAME_SECONDS, artifact_path, feature_vector)

MAX_ROWS = 100_000
MIN_TRAIN = 200
MIN_HOLDOUT = 50


def parse_timestamp(value: str) -> float:
    text = str(value or "").strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _identity_arg(s: argparse.Namespace) -> Dict[str, str]:
    vals = {"venue": s.venue.strip().lower(), "market_type": s.market_type.strip().lower(),
            "instrument_id": s.instrument_id.strip(), "symbol": s.symbol.strip().upper(),
            "timeframe": s.timeframe.strip()}
    if not all(vals.values()) or vals["venue"] in ("unknown", "none", "null") or vals["market_type"] in ("unknown", "none", "null"):
        raise ValueError("Training unavailable: full known venue/market/instrument/symbol/timeframe identity is required.")
    return vals


def read_closed_csv(path: Path, identity: Dict[str, str]) -> List[Dict[str, Any]]:
    expected = {**identity}
    records: List[Dict[str, Any]] = []
    last_ts = None
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            required = {"timestamp", "open", "high", "low", "close", "volume", "is_closed",
                        "venue", "market_type", "instrument_id", "symbol", "timeframe"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise ValueError("CSV needs timestamp, OHLCV, is_closed, venue, market_type, instrument_id, symbol, timeframe columns.")
            for line, row in enumerate(reader, start=2):
                if len(records) >= MAX_ROWS:
                    raise ValueError(f"CSV exceeds {MAX_ROWS} rows; split into one bounded identity dataset.")
                if str(row["is_closed"]).strip().lower() not in ("1", "true", "yes"):
                    raise ValueError(f"line {line}: forming/unconfirmed candle; only closed candles are trainable.")
                actual = {"venue": str(row["venue"]).strip().lower(),
                          "market_type": str(row["market_type"]).strip().lower(),
                          "instrument_id": str(row["instrument_id"]).strip(),
                          "symbol": str(row["symbol"]).strip().upper(),
                          "timeframe": str(row["timeframe"]).strip()}
                if actual != expected:
                    raise ValueError(f"line {line}: mixed/wrong instrument identity; dataset must match all CLI identity values.")
                ts = parse_timestamp(row["timestamp"])
                if last_ts is not None:
                    if ts <= last_ts:
                        raise ValueError(f"line {line}: timestamps must be strictly increasing and unique.")
                    if abs((ts - last_ts) - _TIMEFRAME_SECONDS[identity["timeframe"]]) > 2.0:
                        raise ValueError(f"line {line}: gap/irregular interval; contiguous native timeframe candles are required.")
                last_ts = ts
                vals = {k: float(row[k]) for k in ("open", "high", "low", "close", "volume")}
                if not all(math.isfinite(v) for v in vals.values()):
                    raise ValueError(f"line {line}: non-finite OHLCV.")
                if min(vals[k] for k in ("open", "high", "low", "close")) <= 0 or vals["volume"] < 0 or vals["high"] < max(vals["open"], vals["close"], vals["low"]) or vals["low"] > min(vals["open"], vals["close"], vals["high"]):
                    raise ValueError(f"line {line}: invalid OHLCV values.")
                vals["timestamp"] = row["timestamp"]
                records.append(vals)
    except FileNotFoundError as e:
        raise ValueError(f"Training unavailable: dataset not found: {path}") from e
    return records


def make_samples(rows: Sequence[Dict[str, Any]], part_id: str, horizon: int,
                 neutral_bps: float) -> Tuple[List[List[float]], List[int], List[int]]:
    if len(rows) < 400:
        raise ValueError("Training unavailable: at least 400 strictly identified closed candles are required before chronological holdouts.")
    n = len(rows)
    cut_train, cut_val = int(n * .70), int(n * .85)
    # Purge horizon samples on both sides of split boundaries. X at any point
    # uses only that point and its past 63 bars; Y uses only the future horizon.
    indices = ([i for i in range(63, max(63, cut_train - horizon))]
               + [i for i in range(cut_train + horizon, max(cut_train + horizon, cut_val - horizon))]
               + [i for i in range(cut_val + horizon, n - horizon)])
    # Build aligned samples explicitly, avoiding positional assumptions when a
    # small input makes one split empty (which is rejected below).
    samples: List[List[float]] = []
    labels: List[int] = []
    splits: List[int] = []
    threshold = neutral_bps / 10_000.0
    for i in indices:
        future_return = rows[i + horizon]["close"] / rows[i]["close"] - 1.0
        label = 2 if future_return > threshold else 0 if future_return < -threshold else 1
        samples.append(list(feature_vector(part_id, rows[max(0, i - 63):i + 1])))
        labels.append(label)
        splits.append(0 if i < cut_train else 1 if i < cut_val else 2)
    counts = [sum(1 for x in splits if x == s) for s in range(3)]
    if counts[0] < MIN_TRAIN or counts[1] < MIN_HOLDOUT or counts[2] < MIN_HOLDOUT:
        raise ValueError(f"Training unavailable: chronological split too small after {horizon}-bar purge (train/validation/test={counts}). Supply more historical data.")
    return samples, labels, splits


def _acc(pred: Sequence[int], actual: Sequence[int]) -> float:
    return sum(int(a == b) for a, b in zip(pred, actual)) / max(1, len(actual))


def _majority(actual: Sequence[int]) -> float:
    if not actual:
        return 1.0
    return max(actual.count(c) for c in (0, 1, 2)) / len(actual)


def train_model(X: List[List[float]], y: List[int], split: List[int], device_request: str,
                epochs: int, seed: int) -> Tuple[Any, Dict[str, Any], str]:
    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError as e:
        raise RuntimeError("Training unavailable: install a local PyTorch build first; live runtime itself has no PyTorch requirement.") from e
    # The offline trainer is intentionally low-concurrency on the user's
    # 8-GB host; live inference remains a separate stdlib-only process path.
    torch.set_num_threads(1)
    if device_request not in ("cpu", "cuda"):
        raise ValueError("device must be cpu or cuda")
    if device_request == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA requested but unavailable; rerun with --device cpu.")

    # Train-only normalization; holdouts never affect scaler parameters.
    train_rows = [X[i] for i, s in enumerate(split) if s == 0]
    mean = [sum(row[j] for row in train_rows) / len(train_rows) for j in range(12)]
    std = []
    for j in range(12):
        var = sum((row[j] - mean[j]) ** 2 for row in train_rows) / len(train_rows)
        std.append(max(math.sqrt(var), 1e-6))
    Z = [[max(-8.0, min(8.0, (row[j] - mean[j]) / std[j])) for j in range(12)] for row in X]
    if len(Z) > MAX_ROWS:
        raise ValueError("sample bound exceeded")

    def run(device_name: str):
        torch.manual_seed(seed)
        random.seed(seed)
        torch.use_deterministic_algorithms(True, warn_only=True)
        device = torch.device(device_name)
        model = nn.Sequential(nn.Linear(12, 16), nn.ReLU(), nn.Linear(16, 3)).to(device=device, dtype=torch.float32)
        tx = torch.tensor([Z[i] for i, s in enumerate(split) if s == 0], dtype=torch.float32)
        ty = torch.tensor([y[i] for i, s in enumerate(split) if s == 0], dtype=torch.long)
        vx = torch.tensor([Z[i] for i, s in enumerate(split) if s == 1], dtype=torch.float32, device=device)
        vy = torch.tensor([y[i] for i, s in enumerate(split) if s == 1], dtype=torch.long, device=device)
        dataset = TensorDataset(tx, ty)
        loader = DataLoader(dataset, batch_size=128, shuffle=True, generator=torch.Generator().manual_seed(seed), num_workers=0)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
        loss_fn = nn.CrossEntropyLoss()
        best_loss, best_state, patience = float("inf"), None, 0
        for _ in range(epochs):
            model.train()
            for bx, by in loader:
                bx, by = bx.to(device), by.to(device)
                optimizer.zero_grad(set_to_none=True)
                loss = loss_fn(model(bx), by)
                loss.backward()
                optimizer.step()
            model.eval()
            with torch.no_grad():
                vloss = float(loss_fn(model(vx), vy).item())
            if vloss < best_loss - 1e-5:
                best_loss, patience = vloss, 0
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            else:
                patience += 1
                if patience >= 7:
                    break
        if best_state is None:
            raise RuntimeError("no valid checkpoint during validation")
        model.load_state_dict(best_state)
        model.to(device)
        model.eval()
        with torch.no_grad():
            preds = model(vx).argmax(dim=1).cpu().tolist()
        val_actual = [y[i] for i, s in enumerate(split) if s == 1]
        val_metrics = {"validation_accuracy": _acc(preds, val_actual),
                       "validation_majority_accuracy": _majority(val_actual)}
        test_x = torch.tensor([Z[i] for i, s in enumerate(split) if s == 2], dtype=torch.float32, device=device)
        test_actual = [y[i] for i, s in enumerate(split) if s == 2]
        with torch.no_grad():
            test_preds = model(test_x).argmax(dim=1).cpu().tolist()
        val_metrics.update({"test_accuracy": _acc(test_preds, test_actual),
                            "test_majority_accuracy": _majority(test_actual)})
        state = {k: v.detach().cpu().tolist() for k, v in model.state_dict().items()}
        return model, state, mean, std, val_metrics, device_name

    try:
        _, state, mean, std, metrics, used_device = run(device_request)
    except RuntimeError as e:
        oom = "out of memory" in str(e).lower() or "cuda" in str(e).lower() and "memory" in str(e).lower()
        if device_request != "cuda" or not oom:
            raise
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        _, state, mean, std, metrics, used_device = run("cpu")
        used_device = "cpu_fallback_after_cuda_oom"
    return state, {"mean": mean, "std": std, "pytorch_version": str(torch.__version__), **metrics}, used_device


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(identity: Dict[str, str], part_id: str, state: Dict[str, Any], stats: Dict[str, Any],
              ncounts: List[int], horizon: int, neutral_bps: float, used_device: str,
              dataset_sha256: str, dataset_last_timestamp: float) -> Dict[str, Any]:
    val_ok = stats["validation_accuracy"] >= stats["validation_majority_accuracy"] + 0.02
    test_ok = stats["test_accuracy"] >= stats["test_majority_accuracy"] + 0.02
    if not val_ok or not test_ok:
        raise ValueError("Training unavailable: the fixed offline validation/test acceptance gate did not beat the majority-label baseline by 2 percentage points; no artifact written.")
    layers = [
        {"weights": state["0.weight"], "bias": state["0.bias"], "activation": "relu"},
        {"weights": state["2.weight"], "bias": state["2.bias"], "activation": "linear"},
    ]
    return {"format": FORMAT, "format_version": FORMAT_VERSION, "feature_schema": FEATURE_SCHEMA,
            "part_id": part_id, "feature_names": list(FEATURE_NAMES[part_id]), "identity": identity,
            "normalization": {"mean": stats["mean"], "std": stats["std"]}, "layers": layers,
            "training": {"status": "validated", "approved_for_advisory": True,
                         "split": "chronological_purged", "model_version": "1",
                         "train_samples": ncounts[0], "validation_samples": ncounts[1], "test_samples": ncounts[2],
                         "horizon_bars": horizon, "neutral_threshold_bps": neutral_bps,
                         "dataset_sha256": dataset_sha256, "dataset_last_timestamp": dataset_last_timestamp,
                         "trainer_version": "1.0",
                         "trained_at_utc": datetime.now(timezone.utc).isoformat(),
                         "pytorch_version": stats.get("pytorch_version", "unknown"),
                         "validation_accuracy": stats["validation_accuracy"],
                         "validation_majority_accuracy": stats["validation_majority_accuracy"],
                         "test_accuracy": stats["test_accuracy"],
                         "test_majority_accuracy": stats["test_majority_accuracy"],
                         "device": used_device, "dtype": "float32",
                         "target_warning": "forward-return direction proxy; not calibrated and not a strategy PnL/profitability test"}}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path, help="offline CSV of strictly closed OHLCV rows and full identity columns")
    ap.add_argument("--part", required=True, choices=FEATURE_NAMES.keys())
    ap.add_argument("--venue", required=True)
    ap.add_argument("--market-type", required=True)
    ap.add_argument("--instrument-id", required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--timeframe", required=True, choices=("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h"))
    ap.add_argument("--horizon", type=int, default=3)
    ap.add_argument("--neutral-bps", type=float, default=20.0, help="minimum forward return magnitude for BUY/SELL proxy label; default 20bp")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cpu", help="CPU default; CUDA is opt-in, float32, with explicit CPU retry on CUDA OOM")
    ap.add_argument("--seed", type=int, default=20260929)
    ap.add_argument("--artifact-dir", type=Path, default=Path(os.environ.get("JARVIS_NEURAL_ARTIFACT_DIR", "models/advisory")))
    ap.add_argument("--replace", action="store_true", help="explicitly replace an existing exact-identity artifact after passing holdout gates")
    args = ap.parse_args()
    if not 1 <= args.horizon <= 24 or not 0.0 <= args.neutral_bps <= 1000 or not 1 <= args.epochs <= 200:
        ap.error("horizon 1-24, neutral-bps 0-1000 and epochs 1-200 are required")
    try:
        identity = _identity_arg(args)
        dataset_sha256 = _sha256_file(args.csv)
        rows = read_closed_csv(args.csv, identity)
        dataset_last_timestamp = parse_timestamp(rows[-1]["timestamp"])
        X, y, split = make_samples(rows, args.part, args.horizon, args.neutral_bps)
        ncounts = [sum(1 for s in split if s == x) for x in range(3)]
        state, stats, device = train_model(X, y, split, args.device, args.epochs, args.seed)
        if _sha256_file(args.csv) != dataset_sha256:
            raise ValueError("Training unavailable: input CSV changed during training; discard this run and retry.")
        artifact = _artifact(identity, args.part, state, stats, ncounts, args.horizon, args.neutral_bps,
                             device, dataset_sha256, dataset_last_timestamp)
        target = artifact_path(identity, args.part, str(args.artifact_dir))
        if target.exists() and not args.replace:
            raise ValueError("An artifact for this exact part/instrument/timeframe already exists; pass --replace explicitly to retrain it.")
        target.parent.mkdir(parents=True, exist_ok=True)
        # JSON contains bounded plain arrays only (never pickle/state_dict); atomic replace.
        fd, temporary = tempfile.mkstemp(prefix=".jarvis-model-", suffix=".json", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(artifact, f, separators=(",", ":"), allow_nan=False)
                f.flush(); os.fsync(f.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print(json.dumps({"status": "artifact_created", "path": str(target), "identity": identity,
                          "part": args.part, "samples": ncounts, "device": device,
                          "metrics": {k: stats[k] for k in ("validation_accuracy", "validation_majority_accuracy", "test_accuracy", "test_majority_accuracy")},
                          "warning": "advisory only; forward-return direction test is not profitability validation"}, sort_keys=True))
        return 0
    except Exception as e:
        print(f"TRAINING UNAVAILABLE: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())

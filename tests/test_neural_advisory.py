import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import neural_advisory as na
from train_part_advisory import make_samples, read_closed_csv


IDENTITY = {
    "venue": "delta", "market_type": "futures", "instrument_id": "BTCUSD",
    "symbol": "BTCUSD", "timeframe": "1m",
}
NOW = 1_800_000_000.0


def candles(n=80):
    out = []
    for i in range(n):
        c = 100 + 0.03 * i + math.sin(i / 4.0)
        out.append({
            "timestamp": datetime.fromtimestamp(NOW - (n - i) * 60, tz=timezone.utc).isoformat(),
            "open": c - 0.1 * math.cos(i), "high": c + 0.4, "low": c - 0.4,
            "close": c, "volume": 50 + (i % 11) * 3,
        })
    return out


def artifact(part):
    return {
        "format": na.FORMAT, "format_version": na.FORMAT_VERSION,
        "feature_schema": na.FEATURE_SCHEMA, "part_id": part,
        "feature_names": list(na.FEATURE_NAMES[part]), "identity": dict(IDENTITY),
        "normalization": {"mean": [0.0] * 12, "std": [1.0] * 12},
        "layers": [
            {"weights": [[0.0] * 12 for _ in range(16)], "bias": [0.0] * 16, "activation": "relu"},
            {"weights": [[0.0] * 16 for _ in range(3)], "bias": [0.0] * 3, "activation": "linear"},
        ],
        "training": {
            "status": "validated", "approved_for_advisory": True,
            "split": "chronological_purged", "model_version": "test-fixture",
            "train_samples": 250, "validation_samples": 60, "test_samples": 60,
            "validation_accuracy": 0.60, "validation_majority_accuracy": 0.55,
            "test_accuracy": 0.60, "test_majority_accuracy": 0.55,
            "dataset_sha256": "a" * 64, "dataset_last_timestamp": NOW - 120,
            "trainer_version": "fixture",
            "trained_at_utc": datetime.fromtimestamp(NOW - 60, tz=timezone.utc).isoformat(),
        },
    }


def context(identity=IDENTITY, now=NOW):
    return {"analysis_identity": (identity["venue"], identity["market_type"], identity["instrument_id"], identity["symbol"]),
            "selected_symbol": identity["symbol"], "symbol": identity["symbol"],
            "timeframe": identity["timeframe"], "snapshot_fetched_at": now,
            "is_backtest_mode": False}


class NeuralAdvisoryTests(unittest.TestCase):
    def setUp(self):
        na.clear_caches()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = candles()

    def tearDown(self):
        na.clear_caches()
        self.temp.cleanup()

    def write_artifact(self, part, obj=None, identity=IDENTITY):
        target = na.artifact_path(identity, part, str(self.root))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(obj or artifact(part)), encoding="utf-8")
        return target

    def test_feature_vector_is_part_specific_and_finite_for_all_parts(self):
        vectors = [na.feature_vector(part, self.data) for part in na.FEATURE_NAMES]
        self.assertTrue(all(len(vector) == 12 and all(math.isfinite(x) for x in vector) for vector in vectors))
        self.assertGreater(len(set(vectors)), 1)

    def test_all_ten_parts_run_only_after_matching_valid_artifact(self):
        for part in na.FEATURE_NAMES:
            with self.subTest(part=part):
                self.write_artifact(part)
                result = na.predict_advisory(self.data, part, context(), now=NOW, artifact_dir=str(self.root))
                self.assertEqual(result["status"], "available")
                self.assertEqual(result["direction"], "NEUTRAL")
                self.assertEqual(result["role"], "advisory_only_no_execution_authority")
                self.assertAlmostEqual(sum(result["scores_uncalibrated"].values()), 1.0)

    def test_missing_artifact_is_explicit_and_never_constructs_random_model(self):
        result = na.predict_advisory(self.data, "part5_ml", context(), now=NOW, artifact_dir=str(self.root))
        self.assertEqual(result, {"status": "unavailable", "reason": "trained_artifact_missing"})
        source = (ROOT / "part5_FIXED.py").read_text(encoding="utf-8")
        self.assertNotIn("class NeuralFusionNetwork", source)
        self.assertNotIn("self.neural_fusion(sig_batch", source)
        self.assertNotIn("self.neural_fusion.train()", source)

    def test_inference_reuses_exact_closed_candle_but_not_revision(self):
        self.write_artifact("part1_breakout")
        original = na._infer
        with patch.object(na, "_infer", wraps=original) as infer:
            first = na.predict_advisory(self.data, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))
            again = na.predict_advisory(self.data, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))
            self.assertEqual(first, again)
            self.assertEqual(infer.call_count, 1)
            revised = [dict(row) for row in self.data]
            revised[-1]["open"] += 0.01
            na.predict_advisory(revised, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))
            self.assertEqual(infer.call_count, 2)

    def test_missing_identity_or_stale_frame_fails_closed(self):
        self.write_artifact("part1_breakout")
        self.assertEqual(na.predict_advisory(self.data, "part1_breakout", {}, now=NOW, artifact_dir=str(self.root))["reason"], "full_analysis_identity_required")
        unknown = context()
        unknown["analysis_identity"] = ("unknown", "futures", "BTCUSD", "BTCUSD")
        self.assertEqual(na.predict_advisory(self.data, "part1_breakout", unknown, now=NOW, artifact_dir=str(self.root))["reason"], "full_analysis_identity_required")
        stale = context(now=NOW - 181)
        self.assertEqual(na.predict_advisory(self.data, "part1_breakout", stale, now=NOW, artifact_dir=str(self.root))["reason"], "stale_snapshot")
        wrong = context()
        wrong["selected_symbol"] = "ETHUSD"
        self.assertEqual(na.predict_advisory(self.data, "part1_breakout", wrong, now=NOW, artifact_dir=str(self.root))["reason"], "full_analysis_identity_required")

    def test_artifact_cache_revalidates_full_identity(self):
        path = self.write_artifact("part1_breakout")
        na._load_artifact(path, "part1_breakout", IDENTITY)
        wrong_id = dict(IDENTITY, symbol="ETHUSD")
        with self.assertRaisesRegex(ValueError, "artifact_identity_mismatch"):
            na._load_artifact(path, "part1_breakout", wrong_id)

    def test_artifact_training_cutoff_overlap_and_stale_data_fail_closed(self):
        obj = artifact("part1_breakout")
        obj["training"]["dataset_last_timestamp"] = datetime.fromisoformat(self.data[-1]["timestamp"]).timestamp()
        self.write_artifact("part1_breakout", obj)
        result = na.predict_advisory(self.data, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))
        self.assertEqual(result["reason"], "artifact_training_data_overlap")

        obj = artifact("part1_breakout")
        obj["training"]["dataset_last_timestamp"] = NOW - na._MAX_TRAINING_DATA_AGE_SECONDS - 1
        self.write_artifact("part1_breakout", obj)
        result = na.predict_advisory(self.data, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))
        self.assertEqual(result["reason"], "stale_artifact_training_data")

    def test_wrong_artifact_schema_feature_names_and_instrument_fail_closed(self):
        obj = artifact("part1_breakout")
        obj["feature_schema"] = "wrong-schema"
        self.write_artifact("part1_breakout", obj)
        result = na.predict_advisory(self.data, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))
        self.assertEqual(result["reason"], "artifact_feature_schema_or_part_mismatch")

        obj = artifact("part1_breakout")
        obj["feature_names"][0] = "wrong-feature"
        self.write_artifact("part1_breakout", obj)
        result = na.predict_advisory(self.data, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))
        self.assertEqual(result["reason"], "artifact_feature_names_mismatch")

        obj = artifact("part1_breakout")
        obj["identity"]["instrument_id"] = "different-contract"
        self.write_artifact("part1_breakout", obj)
        result = na.predict_advisory(self.data, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))
        self.assertEqual(result["reason"], "artifact_identity_mismatch")

    def test_identity_mismatch_or_unvalidated_artifact_fails_closed(self):
        wrong_id = dict(IDENTITY, symbol="ETHUSD")
        path = self.write_artifact("part1_breakout", identity=IDENTITY)
        obj = json.loads(path.read_text())
        obj["identity"] = wrong_id
        path.write_text(json.dumps(obj))
        self.assertEqual(na.predict_advisory(self.data, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))["reason"], "artifact_identity_mismatch")
        obj = artifact("part1_breakout")
        obj["training"]["approved_for_advisory"] = False
        path.write_text(json.dumps(obj))
        na.clear_caches()
        self.assertEqual(na.predict_advisory(self.data, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))["reason"], "artifact_not_validation_gated")

    def test_noncontiguous_or_forming_runtime_candles_fail_closed(self):
        gap = [dict(row) for row in self.data]
        gap[-1]["timestamp"] = (datetime.fromisoformat(gap[-1]["timestamp"]) + timedelta(seconds=60)).isoformat()
        result = na.predict_advisory(gap, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))
        self.assertEqual(result["reason"], "closed_candle_sequence_invalid")
        forming = [dict(row) for row in self.data]
        forming[-1]["is_closed"] = False
        result = na.predict_advisory(forming, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))
        self.assertEqual(result["reason"], "forming_candle_rejected")

    def test_nan_features_and_wrong_frame_metadata_fail_closed(self):
        bad = [dict(x) for x in self.data]
        bad[-1]["close"] = float("nan")
        self.assertEqual(na.predict_advisory(bad, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))["reason"], "non_finite_ohlcv")
        self.write_artifact("part1_breakout")
        frame = [dict(x) for x in self.data]
        class Frame(list):
            attrs = {"symbol": "ETHUSD", "timeframe": "1m"}
        self.assertEqual(na.predict_advisory(Frame(frame), "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))["reason"], "frame_symbol_mismatch")

    def test_advisory_annotation_does_not_change_deterministic_signal_or_confidence(self):
        self.write_artifact("part1_breakout")
        before = {"signal": -1, "confidence": 71, "thought": "deterministic"}
        after = na.annotate_part_result(before, self.data, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))
        self.assertEqual({k: after[k] for k in before}, before)
        self.assertEqual(after["neural_advisory"]["status"], "available")
        self.assertEqual(na.not_applicable_result("part12_confidence")["status"], "not_applicable")

    def test_neural_metadata_cannot_change_central_mtf_approval(self):
        from jarvis_strategy_approval import evaluate_mtf_central_strategy
        from test_multitimeframe_strategy_policy import aggregate_gate, evidence_by_timeframe
        evidence = evidence_by_timeframe()
        baseline = evaluate_mtf_central_strategy(evidence, aggregate_gate(), confidence=80, expected_symbol="BTCUSDT")
        with_advisory = evidence_by_timeframe()
        for values in with_advisory.values():
            for result in values.values():
                result["neural_advisory"] = {"status": "available", "direction": "SELL", "scores_uncalibrated": {"sell": 1.0}}
        unchanged = evaluate_mtf_central_strategy(with_advisory, aggregate_gate(), confidence=80, expected_symbol="BTCUSDT")
        self.assertEqual(unchanged["approved"], baseline["approved"])
        self.assertEqual(unchanged["direction"], baseline["direction"])
        self.assertEqual(unchanged["trade_mode"], baseline["trade_mode"])

    def test_artifact_rejects_extreme_finite_weights_and_checks_logits(self):
        obj = artifact("part1_breakout")
        obj["layers"][0]["weights"][0][0] = 1e308
        self.write_artifact("part1_breakout", obj)
        result = na.predict_advisory(self.data, "part1_breakout", context(), now=NOW, artifact_dir=str(self.root))
        self.assertEqual(result["reason"], "artifact_numeric_value_out_of_bounds")
        with self.assertRaisesRegex(ValueError, "non_finite_inference"):
            na._softmax([float("inf"), 0.0, 0.0])

    def test_artifact_is_size_bounded_and_pure_json(self):
        part = "part2_zone"
        path = self.write_artifact(part)
        obj = json.loads(path.read_text())
        obj["normalization"]["std"] = [0.0] * 12
        path.write_text(json.dumps(obj))
        self.assertEqual(na.predict_advisory(self.data, part, context(), now=NOW, artifact_dir=str(self.root))["reason"], "artifact_normalization_std_invalid")
        path.write_text("{}" * (na._MAX_ARTIFACT_BYTES + 1))
        na.clear_caches()
        self.assertEqual(na.predict_advisory(self.data, part, context(), now=NOW, artifact_dir=str(self.root))["reason"], "artifact_size_invalid")

    def test_chronological_training_split_purges_horizon(self):
        rows = []
        for i, row in enumerate(candles(1000)):
            rows.append({**row, "close": row["close"], "open": row["open"], "high": max(row["high"], row["close"]), "low": min(row["low"], row["close"])})
        X, y, split = make_samples(rows, "part5_ml", horizon=3, neutral_bps=20)
        self.assertEqual(len(X), len(y))
        self.assertEqual(len(X), len(split))
        self.assertGreaterEqual(sum(s == 0 for s in split), 200)
        self.assertGreaterEqual(sum(s == 1 for s in split), 50)
        self.assertGreaterEqual(sum(s == 2 for s in split), 50)
        # Training endpoints plus label horizon are strictly before the 70% boundary.
        train_cut = int(len(rows) * .70)
        val_cut = int(len(rows) * .85)
        inds_train = [i for i in range(63, max(63, train_cut - 3))]
        inds_val = [i for i in range(train_cut + 3, max(train_cut + 3, val_cut - 3))]
        inds_test = [i for i in range(val_cut + 3, len(rows) - 3)]
        self.assertLess(max(inds_train) + 3, train_cut)
        self.assertLess(max(inds_val) + 3, val_cut)
        self.assertGreater(min(inds_val), train_cut)
        self.assertGreater(min(inds_test), val_cut)

    def test_csv_trainer_rejects_unclosed_or_cross_identity_data(self):
        path = self.root / "input.csv"
        header = "timestamp,open,high,low,close,volume,is_closed,venue,market_type,instrument_id,symbol,timeframe\n"
        row = "2026-09-29T00:00:00+00:00,100,101,99,100,10,false,delta,futures,BTCUSD,BTCUSD,1m\n"
        path.write_text(header + row)
        with self.assertRaisesRegex(ValueError, "forming/unconfirmed"):
            read_closed_csv(path, IDENTITY)
        row = "2026-09-29T00:00:00+00:00,100,101,99,100,10,true,delta,futures,ETHUSD,BTCUSD,1m\n"
        path.write_text(header + row)
        with self.assertRaisesRegex(ValueError, "mixed/wrong instrument identity"):
            read_closed_csv(path, IDENTITY)


if __name__ == "__main__":
    unittest.main()

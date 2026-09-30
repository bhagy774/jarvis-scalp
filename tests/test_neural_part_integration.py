"""Offline structural and contract tests for in-Part neural advisory integration."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import neural_advisory as na

EXPECTED = {
    1: ("SmartBreakoutAI", "analyze", "part1_breakout"),
    2: ("AdvancedAnalysisSystem", "analyze_native_zone", "part2_zone"),
    3: ("CandlePsychologyMasterGPU", "analyze", "part3_psychology"),
    4: ("VolumeProfileEngineGPU", "analyze", "part4_volume"),
    5: ("MLEngineGPU", "analyze", "part5_ml"),
    6: ("TrendEngineGPU", "analyze", "part6_trend"),
    7: ("VolatilityEngineGPU", "analyze", "part7_volatility"),
    8: ("MarketStructureEngineGPU", "analyze", "part8_structure"),
    9: ("OrderflowEngineGPU", "analyze", "part9_orderflow"),
    10: ("CandleStatsEngineGPU", "analyze", "part10_candlestats"),
    11: ("SignalFusionEngineGPU", "analyze_multi_timeframe", "part11_fusion"),
    12: ("ConfidenceEngineGPU", "analyze_multi_timeframe", "part12_confidence"),
}


def _decorator_for(function):
    for deco in function.decorator_list:
        if (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Name)
                and deco.func.id == "part_advisory_entry"):
            return deco
    return None


class NeuralPartIntegrationTests(unittest.TestCase):
    def test_each_original_part_analyzer_owns_its_task_entry(self):
        for part_no, (class_name, method_name, task_id) in EXPECTED.items():
            with self.subTest(part=part_no):
                tree = ast.parse((ROOT / f"part{part_no}_FIXED.py").read_text(encoding="utf-8"))
                classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name]
                self.assertEqual(len(classes), 1)
                methods = [n for n in classes[0].body
                           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method_name]
                self.assertEqual(len(methods), 1)
                deco = _decorator_for(methods[0])
                self.assertIsNotNone(deco, f"Part {part_no} analyzer has no local advisory entry")
                self.assertEqual(ast.literal_eval(deco.args[0]), task_id)
                if part_no in (11, 12):
                    keywords = {kw.arg: ast.literal_eval(kw.value) for kw in deco.keywords}
                    self.assertEqual(keywords.get("evidence_context_key"), "neural_advisory_evidence")

    def test_jarvis_routes_each_neural_entry_into_original_part_methods(self):
        tree = ast.parse((ROOT / "jarvis_FIXED.py").read_text(encoding="utf-8"))
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        p1 = next(node for node in classes["Part1Breakout"].body
                  if isinstance(node, ast.FunctionDef) and node.name == "analyze")
        p1_source = ast.get_source_segment((ROOT / "jarvis_FIXED.py").read_text(encoding="utf-8"), p1)
        self.assertIn("advisory_data=data", p1_source)
        self.assertIn('if "neural_advisory" in result:', p1_source)
        self.assertIn('output["neural_advisory"] = result["neural_advisory"]', p1_source)
        p2 = next(node for node in classes["Part2Zone"].body
                  if isinstance(node, ast.FunctionDef) and node.name == "analyze")
        p2_source = ast.get_source_segment((ROOT / "jarvis_FIXED.py").read_text(encoding="utf-8"), p2)
        self.assertIn("native_analyzer(data, timeframe=timeframe, context=context)", p2_source)
        self.assertNotIn("annotate_native_frame", p2_source)
        forbidden = {"annotate_part_result", "annotate_mtf_result"}
        used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertFalse(forbidden & used)

    def test_original_method_runs_once_and_preserves_deterministic_fields(self):
        class ExamplePart:
            calls = 0

            @na.part_advisory_entry("part1_breakout", data_parameter="bars", context_parameter="context")
            def analyze(self, bars, context=None):
                self.calls += 1
                return {"signal": 1, "confidence": 77, "thought": "deterministic"}

        bars = object()
        original = {"signal": 1, "confidence": 77, "thought": "deterministic"}
        with patch.object(na, "predict_advisory", return_value={"status": "unavailable", "reason": "trained_artifact_missing"}) as infer:
            output = ExamplePart().analyze(bars, context={"symbol": "BTCUSD"})
        self.assertEqual(output["signal"], original["signal"])
        self.assertEqual(output["confidence"], original["confidence"])
        self.assertEqual(output["thought"], original["thought"])
        self.assertNotIn("neural_advisory", original)
        self.assertEqual(output["neural_advisory"]["status"], "unavailable")
        self.assertEqual(infer.call_count, 1)
        self.assertIs(infer.call_args.args[0], bars)

    def test_mtf_entries_use_full_task_evidence_not_deterministic_input(self):
        evidence = {"frames": {"1m": {"part1_breakout": {"signal": 1}}}}
        seen = []

        class MTFPart:
            @na.part_advisory_entry("part11_fusion", data_parameter="frames", context_parameter="context",
                                    evidence_context_key="neural_advisory_evidence")
            def analyze_multi_timeframe(self, frames, context=None):
                return {"signal": 0, "confidence": 50}

            @na.part_advisory_entry("part12_confidence", data_parameter="frames", context_parameter="context",
                                    evidence_context_key="neural_advisory_evidence")
            def analyze_multi_timeframe_confidence(self, frames, context=None):
                return {"signal": 0, "confidence": 50}

        def capture(data, part, context):
            seen.append((data, part))
            return {"status": "unavailable", "reason": "trained_artifact_missing"}

        with patch.object(na, "predict_advisory", side_effect=capture):
            part = MTFPart()
            frame_input = {"deterministic": "full-mtf-frame"}
            ctx = {"neural_advisory_evidence": evidence}
            part.analyze_multi_timeframe(frame_input, context=ctx)
            part.analyze_multi_timeframe_confidence(frame_input, context=ctx)
        self.assertEqual(seen, [(evidence, "part11_fusion"), (evidence, "part12_confidence")])

    def test_cpu_fallback_and_strict_gpu_failure_are_explicit(self):
        class FakeCuda:
            @staticmethod
            def is_available():
                return True

            @staticmethod
            def empty_cache():
                return None

        class FakeTorch:
            cuda = FakeCuda()

        model = {"mean": [0.0], "std": [1.0], "layers": [], "training": {}}
        status = {"requested_device": "cuda", "strict_gpu": False, "inference_device": "cuda:0",
                  "device_name": "GTX1650 test-double", "gpu_free_mb": 2048, "gpu_total_mb": 4096,
                  "fallback_reason": None}
        with patch.object(na, "_gpu_layers", side_effect=RuntimeError("simulated CUDA failure")), \
             patch.object(na, "_cpu_forward", return_value=[0.0, 1.0, 0.0]):
            scores, actual = na._infer(model, [0.0], "part1_breakout", status, FakeTorch())
        self.assertEqual(actual["inference_device"], "cpu")
        self.assertEqual(actual["fallback_reason"], "cuda_inference_failed")
        self.assertAlmostEqual(sum(scores), 1.0)
        strict = dict(status, strict_gpu=True)
        with patch.object(na, "_gpu_layers", side_effect=RuntimeError("simulated CUDA failure")):
            with self.assertRaisesRegex(ValueError, "gpu_required_inference_failed"):
                na._infer(model, [0.0], "part1_breakout", strict, FakeTorch())

    def test_no_cuda_falls_back_unless_strict_gpu_requested_and_limits_are_bounded(self):
        with patch.dict(os.environ, {"JARVIS_NEURAL_DEVICE": "cuda", "JARVIS_NEURAL_GPU": "0",
                                     "JARVIS_NEURAL_REQUIRE_GPU": "0"}, clear=False), \
             patch.dict(sys.modules, {"torch": None}):
            status = na.get_neural_runtime_status()
            self.assertEqual(status["requested_device"], "cuda")
            self.assertEqual(status["inference_device"], "cpu")
            self.assertEqual(status["fallback_reason"], "pytorch_cuda_unavailable")
        with patch.dict(os.environ, {"JARVIS_NEURAL_DEVICE": "cpu", "JARVIS_NEURAL_REQUIRE_GPU": "1"}, clear=False), \
             patch.dict(sys.modules, {"torch": None}):
            status = na.get_neural_runtime_status()
            self.assertEqual(status["requested_device"], "cuda")
            self.assertEqual(status["strict_gpu"], True)
            self.assertEqual(status["inference_device"], "unavailable")
        self.assertEqual(na._MAX_GPU_CACHED_MODELS, 1)
        self.assertEqual(na._MAX_ARTIFACTS, 16)
        self.assertEqual(na._MAX_PREDICTIONS, 256)
        self.assertEqual(na._INFERENCE_SLOT._value, 1)


if __name__ == "__main__":
    unittest.main()

"""Behavior tests against the production Part14 options method, isolated via AST."""
import ast
import os
import unittest
from pathlib import Path

SOURCE = (Path(__file__).parent.parent / "jarvis_FIXED.py").read_text()
TREE = ast.parse(SOURCE)
cls = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "Part14OptionsChain")
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "analyze_options_with_ollama")
module = ast.Module(body=[method], type_ignores=[])

class Fake:
    last_ollama_whale_tag = "WHALE_BULLISH"
    last_ollama_insight = "stale model result must not leak"
    last_ollama_time = 0
    ollama_cooldown = 0
    def _generate_ollama_options_prompt(self, *_):
        return "test prompt"

class OptionsPathTests(unittest.TestCase):
    def setUp(self):
        self.old = os.environ.get("JARVIS_PURE_ALGO")
        self.calls = []
        ns = {
            "Dict": dict, "Tuple": tuple,
            "_pure_algorithm_mode": lambda: os.getenv("JARVIS_PURE_ALGO", "true").lower() in ("true", "1", "yes", "on"),
            "time": type("Clock", (), {"time": staticmethod(lambda: 999999)})(),
            "OLLAMA_INTEGRATION_AVAILABLE": True,
            "call_ollama": lambda *a, **kw: self.calls.append(a) or ("[WHALE_BEARISH]", None),
            "logging": __import__("logging"),
        }
        exec(compile(module, "jarvis_FIXED.py", "exec"), ns)
        self.method = ns["analyze_options_with_ollama"]
    def tearDown(self):
        if self.old is None: os.environ.pop("JARVIS_PURE_ALGO", None)
        else: os.environ["JARVIS_PURE_ALGO"] = self.old
    def test_pure_returns_math_and_unavailable_without_model_or_stale_tag(self):
        os.environ["JARVIS_PURE_ALGO"] = "true"
        result = self.method(Fake(), {"signal": -1}, 100.0)
        self.assertEqual(result, ("WHALE_UNAVAILABLE", "Model confirmation disabled in pure-algorithm mode", -1))
        self.assertEqual(self.calls, [])
    def test_explicit_non_pure_mode_keeps_model_path(self):
        os.environ["JARVIS_PURE_ALGO"] = "false"
        result = self.method(Fake(), {"signal": 0}, 100.0)
        self.assertEqual(result[0], "WHALE_BEARISH")
        self.assertEqual(len(self.calls), 1)

if __name__ == "__main__": unittest.main()

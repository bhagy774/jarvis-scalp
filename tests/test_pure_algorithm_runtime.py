"""Offline runtime policy checks for JARVIS_PURE_ALGO dispatch."""
import ast, os, unittest
from pathlib import Path
SOURCE = Path(__file__).parent.parent / "jarvis_FIXED.py".read_text()
TREE = ast.parse(SOURCE)
node = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "_pure_algorithm_mode")
ns = {"os": os}
exec(compile(ast.Module(body=[node], type_ignores=[]), "jarvis_FIXED.py", "exec"), ns)
class PureModePolicyTests(unittest.TestCase):
    def test_true_spellings_enable_algorithm_mode(self):
        for value in ("1", "true", "yes", "on", " TRUE "):
            with self.subTest(value=value):
                os.environ["JARVIS_PURE_ALGO"] = value
                self.assertTrue(ns["_pure_algorithm_mode"]())
    def test_false_or_missing_disables_when_explicitly_false(self):
        for value in ("0", "false", "no", "off", ""):
            with self.subTest(value=value):
                os.environ["JARVIS_PURE_ALGO"] = value
                self.assertFalse(ns["_pure_algorithm_mode"]())
    def test_runtime_call_sites_guard_model_influence(self):
        self.assertIn("cycle_count[0] % 5 == 0 and not _pure_algorithm_mode()", SOURCE)
        self.assertIn("not self.is_backtest_mode and not _pure_algorithm_mode()", SOURCE)
        self.assertIn("and not _pure_algorithm_mode():", SOURCE)
        self.assertIn("self._presim_gate(", SOURCE)
        self.assertIn("self._scenario_gate(", SOURCE)
        self.assertIn("self.auto_trader.execute(", SOURCE)
if __name__ == "__main__": unittest.main()

"""Regression checks for the isolated GPU-backed historical backtest path."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE if (HERE / "jarvis_backtester.py").exists() else HERE.parent
BACKTESTER = (ROOT / "jarvis_backtester.py").read_text(encoding="utf-8")
BRAIN = (ROOT / "jarvis_FIXED.py").read_text(encoding="utf-8")


def test_backtest_constructs_brain_in_isolation_mode_before_side_effects():
    assert "JarvisElite(backtest_mode=True)" in BACKTESTER
    assert "self.is_backtest_mode = bool(backtest_mode)" in BRAIN


def test_backtest_has_no_ollama_command_switch_and_forces_math_only():
    assert 'p.add_argument("--ollama-every"' not in BACKTESTER
    assert "self.ollama_every=0" in BACKTESTER
    assert "self.deepseek_enabled = not self.is_backtest_mode" in BRAIN


def test_backtest_does_not_fetch_live_mtf_options_or_cross_exchange_data():
    assert "if self.is_backtest_mode:\n            return {}" in BRAIN
    assert "not self.is_backtest_mode and self.delta_data" in BRAIN
    assert "not self.is_backtest_mode and self.deribit" in BRAIN
    assert "not self.is_backtest_mode and MULTI_SOURCE_DATA_AVAILABLE" in BRAIN


def test_gpu_analysis_is_retained_but_live_gpu_engines_are_not_started():
    assert "# Initialize External GPU Engines" in BRAIN
    assert "if not self.is_backtest_mode:\n                    try:\n                        from part7_FIXED" in BRAIN

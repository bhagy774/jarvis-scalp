import ast
from pathlib import Path

SOURCE_PATH = Path(__file__).parent.parent / "jarvis_FIXED.py"
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


def test_production_part14_callsite_passes_actual_routed_symbol():
    tree = ast.parse(SOURCE)
    # Verify source structure rather than importing/running the live trading module.
    callsite = "if name in ('part7_volatility', 'part14_options_chain')"
    assert callsite in SOURCE
    assert "'selected_symbol': selected_symbol" in SOURCE
    assert "'symbol': selected_symbol" in SOURCE
    assert "res = part.analyze(tf_data, context=part_context)" in SOURCE
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Part14OptionsChain")
    analyze = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "analyze")
    code = ast.get_source_segment(SOURCE, analyze)
    assert "context.get('selected_symbol') or context.get('symbol')" in code
    assert "get_institutional_bias(self.asset)" in code


def test_oracle_altcoin_block_and_live_safety_guards_are_not_removed():
    gate_path = Path(__file__).parent.parent / "oracle_trade_gate.py"
    gate = gate_path.read_text(encoding="utf-8")
    assert "requested_base != \"BTC\"" in gate
    assert "Oracle BTC macro forecast unavailable for selected asset" in gate
    live_path = Path(__file__).parent.parent / "jarvis_live_trader.py"
    live = live_path.read_text(encoding="utf-8")
    assert "require_options=bool(self.is_enabled)" in live

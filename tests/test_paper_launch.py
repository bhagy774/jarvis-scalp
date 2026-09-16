"""Inspect only the launch guard of the live entrypoint (jarvis_FIXED.py).

run_all_parts.py is a legacy, unused coordinator and is intentionally
excluded. Live trading is an intentional, user-authorized mode (requires
JARVIS_START_PAPER=1 acknowledgement plus explicit live flags). The launch
gate must only enforce the JARVIS_START_PAPER opt-in; it must NOT reject
live execution flags.
"""
import ast
import os
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def test_launch_gate_requires_start_acknowledgement():
    tree = ast.parse((ROOT / 'jarvis_FIXED.py').read_text(encoding='utf-8', errors='ignore'))
    target = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    guard = next(node for node in target.body if isinstance(node, ast.If))
    expr = compile(ast.Expression(guard.test), 'jarvis_FIXED.py', 'eval')
    # Missing acknowledgement -> gate blocks startup (guard True).
    with patch.dict(os.environ, {}, clear=True):
        assert eval(expr, {'os': os}) is True
    # Acknowledgement present -> startup allowed (guard False), paper or live.
    with patch.dict(os.environ, {'JARVIS_START_PAPER': '1'}, clear=True):
        assert eval(expr, {'os': os}) is False
    for flag in ['JARVIS_AUTO_TRADE', 'JARVIS_LIVE_EXECUTION', 'DELTA_ORDER_EXECUTION_ENABLED']:
        with patch.dict(os.environ, {'JARVIS_START_PAPER': '1', flag: 'true'}, clear=True):
            assert eval(expr, {'os': os}) is False

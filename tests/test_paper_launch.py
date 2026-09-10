"""Inspect only the launch guards; do not import the monolithic engine."""
import ast
import os
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def test_paper_launch_rejects_live_flags():
    for filename, function in [('jarvis_FIXED.py', 'main'), ('run_all_parts.py', 'run_all_parts')]:
        tree = ast.parse((ROOT / filename).read_text())
        target = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function)
        guard = next(node for node in target.body if isinstance(node, ast.If))
        expr = compile(ast.Expression(guard.test), filename, 'eval')
        for flag in ['JARVIS_AUTO_TRADE', 'JARVIS_LIVE_EXECUTION', 'DELTA_ORDER_EXECUTION_ENABLED']:
            with patch.dict(os.environ, {'JARVIS_START_PAPER': '1', flag: 'true'}, clear=True):
                assert eval(expr, {'os': os}) is True
        with patch.dict(os.environ, {'JARVIS_START_PAPER': '1'}, clear=True):
            assert eval(expr, {'os': os}) is False
        with patch.dict(os.environ, {}, clear=True):
            assert eval(expr, {'os': os}) is True

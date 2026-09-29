import ast
import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Mapping
import importlib
import sys
import types

import pytest
import numpy as np
import pandas as pd

from part7_signal import analyze_timeframe
from jarvis_strategy_approval import (
    evaluate_central_strategy, make_entry_approval, validate_entry_approval,
)


NOW = 1_800_000_000.0


def bullish_parts(symbol="BTCUSDT"):
    return {
        "part1_breakout": {"signal": 1, "thought": "bullish breakout"},
        "part2_zone": {"signal": 1, "thought": "bullish demand zone"},
        "part3_psychology": {"signal": 1, "thought": "bullish candle"},
        "part4_volume": {"signal": 1, "thought": "volume confirmation"},
        "part5_ml": {"signal": 1, "thought": "model confirms"},
        "part6_trend": {"signal": 1, "thought": "trend bullish"},
        "part7_volatility": {"signal": 1, "thought": "volatility expansion"},
        "part8_structure": {"signal": 1, "thought": "structure bullish"},
        "part9_orderflow": {"signal": 1, "thought": "order flow bullish"},
        "part10_candlestats": {"signal": 1, "thought": "bullish candle stats"},
    }


def clear_gate(symbol=None):
    return {
        "entry_blocked": False, "risk_veto": False, "status": "ok",
        "data_status": "valid", "timeframe": "aggregate", "symbol": symbol,
        "blocked_timeframes": [], "veto_timeframes": [],
        "timeframe_results": {
            tf: {"symbol": symbol, "timeframe": tf, "status": "neutral",
                 "data_status": "valid", "entry_blocked": False, "risk_veto": False}
            for tf in ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h")
        },
    }


def approval_for(symbol="BTCUSDT", snapshot="snap-1", confidence=80, now=NOW):
    decision = {"approved": True, "direction": "BUY", "confidence": confidence, "symbol": symbol}
    return make_entry_approval(
        decision, direction="BUY", symbol=symbol, exchange="delta", contract=symbol,
        instrument_id=symbol, market_type="unverified", analysis_symbol=symbol,
        analysis_exchange="delta", snapshot_version=snapshot,
        analysis_timestamp=now, confidence=confidence,
    )


def test_central_strategy_positive_neutral_veto_and_fail_closed_semantics():
    positive = evaluate_central_strategy(bullish_parts(), clear_gate(), confidence=80)
    assert positive["approved"] and positive["direction"] == "BUY"
    assert not evaluate_central_strategy(
        bullish_parts(), clear_gate(), expected_symbol="BTCUSDT"
    )["approved"]
    assert evaluate_central_strategy(
        bullish_parts(), clear_gate("BTCUSDT"), expected_symbol="BTCUSDT"
    )["approved"]
    assert not evaluate_central_strategy(
        bullish_parts(), clear_gate("ETHUSDT"), expected_symbol="BTCUSDT"
    )["approved"]
    partial_gate = clear_gate("BTCUSDT")
    partial_gate["timeframe_results"].pop("4h")
    assert not evaluate_central_strategy(
        bullish_parts(), partial_gate, expected_symbol="BTCUSDT"
    )["approved"]
    stale_gate = clear_gate("BTCUSDT")
    stale_gate["timeframe_results"]["1m"]["data_status"] = "stale"
    assert not evaluate_central_strategy(
        bullish_parts(), stale_gate, expected_symbol="BTCUSDT"
    )["approved"]

    neutral_parts = bullish_parts()
    neutral_parts["part3_psychology"] = {"signal": 0, "thought": "indecisive"}
    assert evaluate_central_strategy(neutral_parts, clear_gate())["direction"] == "BUY"

    blocked = {**clear_gate(), "entry_blocked": True, "risk_veto": True, "reason": "extreme volatility"}
    assert not evaluate_central_strategy(bullish_parts(), blocked)["approved"]
    assert not evaluate_central_strategy(bullish_parts(), None)["approved"]
    assert not evaluate_central_strategy({k: v for k, v in bullish_parts().items() if k != "part4_volume"}, clear_gate())["approved"]

    zone = bullish_parts()
    zone["part2_zone"] = {"signal": -1, "thought": "resistance zone"}
    assert not evaluate_central_strategy(zone, clear_gate())["approved"]
    dissent = bullish_parts()
    dissent["part6_trend"] = {"signal": -1, "thought": "bearish trend"}
    dissent["part8_structure"] = {"signal": -1, "thought": "bearish structure"}
    assert not evaluate_central_strategy(dissent, clear_gate())["approved"]

    malformed = bullish_parts()
    malformed["part1_breakout"] = {"signal": float("nan"), "thought": "bad"}
    assert not evaluate_central_strategy(malformed, clear_gate())["approved"]
    unavailable = bullish_parts()
    unavailable["part5_ml"] = {"signal": 1, "thought": "offline model fallback"}
    assert evaluate_central_strategy(unavailable, clear_gate())["direction"] == "BUY"


def test_part7_stale_wrong_symbol_and_partial_data_blocks_are_fail_closed():
    now = pd.Timestamp.now(tz="UTC")
    values = np.full(60, 100.0)
    def frame(end, columns=True, symbol="ETHUSDT"):
        data = {"open": values, "high": values + .2, "low": values - .2,
                "close": values, "volume": np.full(60, 1000.0)}
        if not columns:
            data.pop("volume")
        result = pd.DataFrame(data, index=pd.date_range(end=end, periods=60, freq="min"))
        result.attrs["symbol"] = symbol
        return result
    context = {"selected_symbol": "ETHUSDT", "timeframe": "1m",
               "is_backtest_mode": False, "shared_candle_source": "shared_exchange"}
    stale = analyze_timeframe(frame(now - pd.Timedelta(minutes=15)), symbol="ETHUSDT",
                              timeframe="1m", context=context)
    wrong = analyze_timeframe(frame(now - pd.Timedelta(minutes=2), symbol="BTCUSDT"),
                              symbol="ETHUSDT", timeframe="1m", context=context)
    partial = analyze_timeframe(frame(now - pd.Timedelta(minutes=2), columns=False),
                                symbol="ETHUSDT", timeframe="1m", context=context)
    assert stale["entry_blocked"] is True
    assert wrong["entry_blocked"] is True
    assert partial["entry_blocked"] is True


def test_approval_scope_freshness_identity_and_snapshot_are_mandatory():
    approval = approval_for()
    args = dict(direction="BUY", symbol="BTCUSDT", exchange="delta", contract="BTCUSDT",
                instrument_id="BTCUSDT", market_type="unverified", snapshot_version="snap-1",
                confidence=80, now=NOW + 1)
    assert validate_entry_approval(approval, **args)[0]
    for override in (
        {"symbol": "ETHUSDT"}, {"instrument_id": "other"},
        {"snapshot_version": "old"}, {"direction": "SELL"},
    ):
        assert not validate_entry_approval(approval, **(args | override))[0]
    assert not validate_entry_approval(approval, **(args | {"now": NOW + 181}))[0]


def _live_trader_module(monkeypatch):
    risk = types.ModuleType("jarvis_risk")
    risk.calculate_trade_size = lambda *a, **k: {}
    risk.MAX_LEVERAGE_CAP = 20
    risk.contract_quote_value_usdt = lambda *a, **k: None
    lots = types.ModuleType("jarvis_lot_limits")
    lots.enforce_entry_lots = lambda *a, **k: 0
    monkeypatch.setitem(sys.modules, "jarvis_risk", risk)
    monkeypatch.setitem(sys.modules, "jarvis_lot_limits", lots)
    sys.modules.pop("jarvis_live_trader", None)
    return importlib.import_module("jarvis_live_trader")


def test_live_auto_trader_direct_entry_requires_approval_but_exit_is_ungated(monkeypatch):
    module = _live_trader_module(monkeypatch)
    trader = object.__new__(module.JarvisAutoTrader)
    trader.emergency_stop = False
    result = trader.execute("CALL", 80, 100.0, bullish_parts(), symbol="BTCUSDT")
    assert not result["success"] and "approval" in result["reason"].lower()
    direct = trader._place_trade("CALL", 80, 100.0, "SCALP", {}, symbol="BTCUSDT")
    assert not direct["success"] and "approval" in direct["reason"].lower()

    orders = []
    trader.is_enabled = True
    trader._ownership_token = "test-owner"
    trader.delta = types.SimpleNamespace(place_order=lambda **kwargs: (orders.append(kwargs) or {"success": True}))
    close = trader._close_position_market({"id": "p1", "symbol": "BTCUSDT", "direction": "CALL", "contracts": 1})
    assert close["success"] and orders[0]["reduce_only"] is True


def test_paper_entry_helper_direct_bypass_attempt_is_rejected():
    source = Path(__file__).resolve().parents[1] / "jarvis_FIXED.py"
    parsed = ast.parse(source.read_text())
    owner = next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == "LiveTradingEngine")
    method = next(node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == "_open_paper_trade")
    harness = ast.ClassDef(name="PaperEntryHarness", bases=[], keywords=[], body=[method], decorator_list=[])
    module_ast = ast.fix_missing_locations(ast.Module(body=[harness], type_ignores=[]))
    namespace = {"datetime": datetime, "timedelta": timedelta}
    exec(compile(module_ast, str(source), "exec"), namespace)
    engine = namespace["PaperEntryHarness"]()
    engine._dashboard_events = []
    opened = engine._open_paper_trade("CALL", 100.0, 80, "SCALP", 101.0, 102.0, 99.0)
    assert opened is None
    assert not engine._dashboard_events or "blocked" in engine._dashboard_events[-1]


def _isolated_async_method(repo_file, class_name, method_name):
    source = Path(__file__).resolve().parents[1] / repo_file
    parsed = ast.parse(source.read_text())
    owner = next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    method = next(node for node in owner.body if isinstance(node, ast.AsyncFunctionDef) and node.name == method_name)
    harness = ast.ClassDef(name="EntryHarness", bases=[], keywords=[], body=[method], decorator_list=[])
    module_ast = ast.fix_missing_locations(ast.Module(body=[harness], type_ignores=[]))
    namespace = {"Any": Any, "Dict": Dict, "Mapping": Mapping}
    exec(compile(module_ast, str(source), "exec"), namespace)
    return namespace["EntryHarness"]()


def test_legacy_part10_and_part12_direct_entry_apis_require_central_approval():
    legacy = _isolated_async_method("part10_FIXED.py", "SwingScalpTradeExecutor", "execute_trade")
    legacy_result = asyncio.run(legacy.execute_trade("CALL"))
    assert legacy_result["status"] == "rejected"
    assert "central" in legacy_result["reason"].lower()

    engine = _isolated_async_method("part12_FIXED.py", "GPUOrderExecutionEngine", "execute_trade")
    result = asyncio.run(engine.execute_trade("CALL", 9.0, 100.0, 100.1))
    assert result["status"] == "rejected"
    assert "central" in result["reason"].lower()

import os
import sys
import time
import unittest
from unittest.mock import Mock, patch

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(autouse=True)
def isolate_process_local_position_ownership():
    """Position ownership is process-local; do not leak claims between tests."""
    from jarvis_position_ownership import clear_registry
    clear_registry()
    yield
    clear_registry()


def jarvis_paper_entry_authorization():
    """Use Jarvis' own deterministic evaluators to issue the paper-test approval."""
    from jarvis_strategy_approval import (
        build_execution_plan, evaluate_central_strategy, make_entry_approval,
    )
    symbol, snapshot, confidence = "BTCUSDT", "paper-test-snapshot", 90
    evidence = {
        name: {"signal": 1, "thought": "valid bullish test evidence"}
        for name in (
            "part1_breakout", "part2_zone", "part3_psychology", "part4_volume",
            "part5_ml", "part6_trend", "part7_volatility", "part8_structure",
            "part9_orderflow", "part10_candlestats",
        )
    }
    gate = {
        "symbol": symbol, "entry_blocked": False, "risk_veto": False,
        "status": "ok", "data_status": "valid", "timeframe": "aggregate",
        "blocked_timeframes": [], "veto_timeframes": [],
        "timeframe_results": {
            tf: {"symbol": symbol, "timeframe": tf, "status": "neutral",
                 "data_status": "valid", "entry_blocked": False, "risk_veto": False}
            for tf in ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h")
        },
    }
    decision = evaluate_central_strategy(
        evidence, gate, confidence=confidence, expected_symbol=symbol,
    )
    plan = build_execution_plan(
        direction="BUY", recommended_expiry="SCALP", entry_price=100.0,
        stop_loss=99.0, take_profit=102.0, symbol=symbol,
        snapshot_version=snapshot, confidence=confidence,
    )
    approval = make_entry_approval(
        decision, direction="BUY", symbol=symbol, exchange="delta", contract=symbol,
        instrument_id=symbol, market_type="unverified", analysis_symbol=symbol,
        analysis_exchange="delta", snapshot_version=snapshot,
        analysis_timestamp=time.time(), confidence=confidence, execution_plan=plan,
    )
    return {"approval": approval, "evidence": evidence, "gate": gate,
            "plan": plan, "snapshot": snapshot}


class DeltaStub:
    def __init__(self, balance=100.0, order_result=None):
        self.balance = balance
        self.order_result = order_result if order_result is not None else {"success": True, "order_id": "x"}
        self.order_calls = []
        self.leverage_calls = []

    def get_wallet_balance(self):
        return self.balance

    def place_order(self, *args, **kwargs):
        self.order_calls.append((args, kwargs))
        return self.order_result

    def set_leverage(self, *args, **kwargs):
        self.leverage_calls.append((args, kwargs))
        return True


class OracleStub:
    def __init__(self, forecast):
        self.forecast = forecast

    def get_latest_forecast(self):
        return self.forecast


class ExecutionSafetyTests(unittest.TestCase):
    def test_private_request_without_credentials_sends_nothing(self):
        from delta_api_wrapper import DeltaExchangeData
        client = DeltaExchangeData(api_key=None, api_secret=None)
        client._binance = None
        client.session.request = Mock()
        result = client._request("GET", "/v2/wallet/balances", authorized=True)
        self.assertFalse(result["success"])
        client.session.request.assert_not_called()

    def test_order_and_leverage_are_blocked_without_opt_in(self):
        from delta_api_wrapper import DeltaExchangeData
        with patch.dict(os.environ, {"DELTA_ORDER_EXECUTION_ENABLED": "false"}):
            client = DeltaExchangeData(api_key="key", api_secret="secret")
            client.get_product_id = Mock(side_effect=AssertionError("must not query venue"))
            self.assertFalse(client.place_order("BTCUSDT", "buy", 1)["success"])
            self.assertFalse(client.set_leverage("BTCUSDT", 100))

    def test_invalid_order_input_fails_closed(self):
        from delta_api_wrapper import DeltaExchangeData
        with patch.dict(os.environ, {"DELTA_ORDER_EXECUTION_ENABLED": "true"}):
            client = DeltaExchangeData(api_key="key", api_secret="secret")
            client.get_product_id = Mock(side_effect=AssertionError("must not query venue"))
            self.assertFalse(client.place_order("", "buy", 1)["success"])
            self.assertFalse(client.place_order("BTCUSDT", "hold", 1)["success"])
            self.assertFalse(client.place_order("BTCUSDT", "buy", 0)["success"])
            self.assertFalse(client.place_order("BTCUSDT", "buy", 1, "limit", 0)["success"])

    def test_deribit_constructor_does_not_authenticate(self):
        with patch("requests.get") as get:
            from deribit_options_client import DeribitOptionsClient
            client = DeribitOptionsClient(client_id="id", client_secret="secret")
        self.assertIsNone(client.access_token)
        get.assert_not_called()

    def test_sizer_never_invents_balance_or_exceeds_cap(self):
        from jarvis_sizer import JarvisSizer, MAX_RISK_PCT
        sizer = JarvisSizer(DeltaStub(0))
        no_money = sizer.calculate_size(95, force_balance=0)
        self.assertEqual(no_money["contracts"], 0)
        small = sizer.calculate_size(95, force_balance=0.01)
        self.assertLessEqual(small["margin_usdt"], 0.01 * MAX_RISK_PCT + 1e-9)
        self.assertEqual(small["contracts"], 0)

    def test_position_manager_does_not_book_failed_close(self):
        from jarvis_position_manager import JarvisPositionManager
        delta = DeltaStub(order_result={"success": False, "error": "rejected"})
        # Run in paper mode so register_position doesn't require live contract metadata
        with patch.dict(os.environ, {"DELTA_ORDER_EXECUTION_ENABLED": "false"}):
            manager = JarvisPositionManager(delta)
            pos = manager.register_position("p1", "CALL", 100, 10, 80)
            self.assertFalse(manager._close_position(pos, 101, "test"))
            self.assertEqual(pos.status, "CLOSE_UNKNOWN")
            self.assertEqual(manager.daily_pnl, 0.0)
            self.assertIn(pos, manager.open_positions)

    def test_live_paper_mode_never_sets_leverage_or_submits_order(self):
        import jarvis_live_trader
        trader = jarvis_live_trader.JarvisAutoTrader(DeltaStub(100))
        trader.is_enabled = False
        authorization = jarvis_paper_entry_authorization()
        response = trader._place_trade(
            "CALL", 90, 100.0, "SCALP", {"do_hedge": False},
            central_approval=authorization["approval"],
            part_results=authorization["evidence"], part7_gate=authorization["gate"],
            snapshot_version=authorization["snapshot"], execution_plan=authorization["plan"],
        )
        self.assertTrue(response["success"])
        self.assertEqual(trader.delta.leverage_calls, [])
        self.assertEqual(trader.delta.order_calls, [])

    def test_paper_entry_without_jarvis_approval_is_rejected(self):
        import jarvis_live_trader
        trader = jarvis_live_trader.JarvisAutoTrader(DeltaStub(100))
        trader.is_enabled = False
        response = trader._place_trade("CALL", 90, 100.0, "SCALP", {"do_hedge": False})
        self.assertFalse(response["success"])
        self.assertIn("approval", response["reason"].lower())
        self.assertEqual(trader.delta.leverage_calls, [])
        self.assertEqual(trader.delta.order_calls, [])

    def test_live_monitor_keeps_ambiguous_close_unbooked(self):
        import jarvis_live_trader
        delta = DeltaStub(order_result={"success": False, "error": "timeout"})
        trader = jarvis_live_trader.JarvisAutoTrader(delta)
        trader.is_enabled = True
        position = {
            "id": "p", "direction": "CALL", "entry_price": 100.0,
            "tp_price": 101.0, "sl_price": 99.0, "expiry_time": "2999-01-01T00:00:00",
            "contracts": 10, "symbol": "BTCUSDT", "status": "OPEN",
        }
        trader.open_positions = [position]
        trader._check_positions(101.0)
        self.assertEqual(position["status"], "CLOSE_UNKNOWN")
        self.assertEqual(trader.daily_pnl, 0.0)
        self.assertEqual(trader.open_positions, [position])

    def test_oracle_wait_and_missing_data_fail_closed(self):
        from oracle_trade_gate import OracleTradeGate
        gate = OracleTradeGate(oracle_ref=OracleStub({}), enabled=True, hard_gate=True)
        self.assertFalse(gate.is_trade_aligned("CALL")[0])
        forecast = {
            "model_used": "ready", "trade_suggestion": "WAIT",
            "5min": {"direction": "BULLISH"}, "30min": {"direction": "BULLISH"},
            "entry_zone": {"price_from": 99, "price_to": 101},
        }
        gate = OracleTradeGate(oracle_ref=OracleStub(forecast), enabled=True, hard_gate=True)
        self.assertFalse(gate.is_trade_aligned("CALL")[0])
        self.assertFalse(gate.is_price_in_entry_zone(0)[0])

    def test_oracle_requires_two_timeframe_consensus(self):
        from oracle_trade_gate import OracleTradeGate
        forecast = {
            "model_used": "ready", "trade_suggestion": "CALL",
            "5min": {"direction": "BULLISH"}, "30min": {"direction": "NEUTRAL"},
            "entry_zone": {"price_from": 99, "price_to": 101},
        }
        gate = OracleTradeGate(oracle_ref=OracleStub(forecast), enabled=True, hard_gate=True)
        self.assertFalse(gate.is_trade_aligned("CALL")[0])


if __name__ == "__main__":
    unittest.main()

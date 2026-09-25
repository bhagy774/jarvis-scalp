from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import Mock, patch

import pytest


class VenueStub:
    def __init__(self, positions=None, order_result=None, position_error=None):
        self.positions = [] if positions is None else positions
        self.order_result = {"success": True, "order_id": "order-1"} if order_result is None else order_result
        self.position_error = position_error
        self.position_queries = []
        self.order_calls = []

    def get_open_positions(self, symbol=""):
        self.position_queries.append(symbol)
        if self.position_error:
            raise self.position_error
        return self.positions

    def place_order(self, **kwargs):
        self.order_calls.append(kwargs)
        return self.order_result


def _live_trader(venue):
    from jarvis_live_trader import JarvisAutoTrader
    trader = JarvisAutoTrader(venue)
    trader.is_enabled = True
    trader._check_risk_gates = lambda *_args: {"ok": True, "reason": "test"}
    return trader


def test_live_entry_preflight_enforces_one_position_on_actual_execute_path():
    venue = VenueStub()
    trader = _live_trader(venue)
    place = Mock(return_value={"success": True, "position": {"id": "paper-stub"}})
    trader._place_trade = place

    with patch("jarvis_live_trader._get_gemini_advisor", return_value=None), \
         patch("jarvis_live_trader._get_oracle_gate", return_value=None):
        first = trader.execute("CALL", 90, 100.0, symbol="BTCUSDT")
        assert first["success"]
        assert venue.position_queries == [""]  # account-wide, not selected-symbol only
        assert place.call_count == 1

        venue.positions = [{"size": "1", "product": {"symbol": "BTCUSD"}}]
        second = trader.execute("PUT", 90, 101.0, symbol="ETHUSDT")
        assert not second["success"]
        assert "One-position policy" in second["reason"]
        assert place.call_count == 1


def test_concurrent_execute_calls_submit_at_most_one_live_entry():
    venue = VenueStub()
    trader = _live_trader(venue)
    start = threading.Barrier(3)
    submitted = []

    def place_trade(*_args, **_kwargs):
        submitted.append(True)
        # Simulate exchange state becoming visible after the accepted entry.
        venue.positions = [{"symbol": "BTCUSDT", "size": "1"}]
        return {"success": True, "position": {"id": "entry-1"}}

    trader._place_trade = place_trade

    def run(direction):
        start.wait(timeout=3)
        with patch("jarvis_live_trader._get_gemini_advisor", return_value=None), \
             patch("jarvis_live_trader._get_oracle_gate", return_value=None):
            return trader.execute(direction, 90, 100.0, symbol="BTCUSDT")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, direction) for direction in ("CALL", "PUT")]
        start.wait(timeout=3)
        results = [future.result(timeout=5) for future in futures]

    assert len(submitted) == 1
    assert sum(bool(result.get("success")) for result in results) == 1
    assert sum("One-position policy" in result.get("reason", "") for result in results) == 1


def test_live_entry_fails_closed_on_unknown_exchange_position_state():
    venue = VenueStub(position_error=TimeoutError("offline"))
    trader = _live_trader(venue)
    trader._place_trade = Mock()
    with patch("jarvis_live_trader._get_gemini_advisor", return_value=None), \
         patch("jarvis_live_trader._get_oracle_gate", return_value=None):
        result = trader.execute("CALL", 90, 100.0, symbol="BTCUSDT")
    assert not result["success"]
    assert "state unavailable" in result["reason"]
    trader._place_trade.assert_not_called()


def test_live_entry_applies_the_sized_leverage_before_order_submission():
    from jarvis_position_ownership import clear_registry
    clear_registry()

    class SizingVenue(VenueStub):
        def __init__(self):
            super().__init__(positions=[])
            self.sequence = []
        def get_product_metadata(self, symbol):
            assert symbol == "BTCUSDT"
            return {"id": 7, "symbol": "BTCUSDT", "contract_value": 1,
                    "contract_value_currency": "USDT", "max_leverage": 7}
        def get_wallet_balance(self):
            return 1000.0
        def set_leverage(self, symbol, leverage):
            self.sequence.append(("leverage", symbol, leverage))
            return True
        def place_order(self, **kwargs):
            self.sequence.append(("order", kwargs["symbol"], kwargs["size"]))
            self.order_calls.append(kwargs)
            return self.order_result

    venue = SizingVenue()
    trader = _live_trader(venue)
    with patch("jarvis_live_trader._get_sizer", return_value=None), \
         patch("jarvis_live_trader._get_oracle_gate", return_value=None):
        result = trader._place_trade(
            "CALL", 90, 100.0, "SCALP", {"do_hedge": False}, symbol="BTCUSDT"
        )
    assert result["success"]
    assert venue.sequence[0] == ("leverage", "BTCUSDT", result["position"]["leverage"])
    assert result["position"]["leverage"] == 7
    assert venue.sequence[1][0] == "order"
    clear_registry()


def test_live_close_uses_one_positive_reduce_only_contract_below_entry_minimum():
    from jarvis_position_ownership import clear_registry
    clear_registry()
    venue = VenueStub(positions=[])
    trader = _live_trader(venue)
    # Closing a real one-contract exposure is an exit, not a new entry; the
    # configured entry-lot minimum must not prevent flattening it.
    pos = {"id": "close-1", "direction": "CALL", "symbol": "BTCUSDT", "contracts": 1}

    result = trader._close_position_market(pos)
    assert result["success"]
    assert result["reconciliation"]["confirmed"]
    assert len(venue.order_calls) == 1
    order = venue.order_calls[0]
    assert order["size"] == 1 and order["size"] > 0
    assert order["reduce_only"] is True
    assert order["client_order_id"] == "jarvis-close-close-1"
    assert "idempotency_key" not in order
    clear_registry()


def test_live_close_rejects_zero_quantity_without_submitting():
    from jarvis_position_ownership import clear_registry
    clear_registry()
    venue = VenueStub(positions=[])
    trader = _live_trader(venue)
    result = trader._close_position_market({
        "id": "zero-close", "direction": "CALL", "symbol": "BTCUSDT", "contracts": 0,
    })
    assert not result["success"]
    assert "positive integer" in result["error"]
    assert venue.order_calls == []
    clear_registry()


def test_reversal_is_blocked_until_exchange_confirms_flat():
    from jarvis_position_ownership import clear_registry
    clear_registry()
    venue = VenueStub(positions=[{"symbol": "BTCUSDT", "size": "2"}])
    trader = _live_trader(venue)
    pos = {
        "id": "not-flat", "direction": "CALL", "symbol": "BTCUSDT",
        "contracts": 2, "entry_price": 100.0, "notional_usdt": 200.0,
        "trade_type": "SCALP", "status": "OPEN",
    }
    trader.open_positions = [pos]
    trader._place_trade = Mock(return_value={"success": True})

    trader._execute_reversal(pos, "PUT", 90, 101.0)

    assert pos["status"] == "CLOSE_UNKNOWN"
    assert pos in trader.open_positions
    trader._place_trade.assert_not_called()
    assert len(venue.order_calls) == 1
    clear_registry()


def test_reversal_opens_only_after_verified_flat_position():
    from jarvis_position_ownership import clear_registry
    clear_registry()
    venue = VenueStub(positions=[])
    trader = _live_trader(venue)
    pos = {
        "id": "flat-now", "direction": "CALL", "symbol": "BTCUSDT",
        "contracts": 2, "entry_price": 100.0, "notional_usdt": 200.0,
        "trade_type": "SCALP", "status": "OPEN",
    }
    trader.open_positions = [pos]
    trader._place_trade = Mock(return_value={"success": True})

    with patch("jarvis_live_trader.time.sleep"):
        trader._execute_reversal(pos, "PUT", 90, 101.0)

    trader._place_trade.assert_called_once()
    assert pos["status"] == "CLOSED"
    assert pos not in trader.open_positions
    clear_registry()


def test_positions_query_distinguishes_flat_from_failed_venue_state():
    from delta_api_wrapper import DeltaExchangeData

    client = object.__new__(DeltaExchangeData)
    client._resolve_product = Mock(return_value={"id": 7, "symbol": "BTCUSD"})
    client._request = Mock(return_value={
        "success": True,
        "data": {"result": [{"size": "2", "product": {"symbol": "BTCUSD"}}]},
    })
    assert client.get_open_positions("BTCUSDT")[0]["size"] == "2"
    assert client._request.call_args.args[1] == "/v2/positions?product_id=7"

    client._request.return_value = {"success": False, "error": "unavailable"}
    with pytest.raises(RuntimeError, match="Position request failed"):
        client.get_open_positions("BTCUSDT")

    client._resolve_product.return_value = None
    with pytest.raises(RuntimeError, match="Product lookup failed"):
        client.get_open_positions("BTCUSDT")

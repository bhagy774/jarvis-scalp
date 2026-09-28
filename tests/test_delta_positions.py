import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from delta_api_wrapper import DeltaExchangeData


class PositionClient(DeltaExchangeData):
    """Offline position-reconciliation fixture; never opens a socket."""
    def __init__(self, product, response):
        # Avoid constructor/provider side effects and credentials entirely.
        self._products_cache = {"ts": 9999999999, "products": [product] if product else []}
        self.response = response
        self.calls = []

    def _request(self, method, endpoint, payload=None, authorized=False):
        self.calls.append((method, endpoint, payload, authorized))
        return self.response


def test_get_open_positions_scopes_by_resolved_product_id_and_identity():
    product = {"id": 42, "symbol": "BTCUSD"}
    rows = [
        {"id": "match", "product_id": 42, "symbol": "BTCUSD", "size": 1},
        {"id": "different-product-id", "product_id": 43, "symbol": "BTCUSD", "size": 9},
        {"id": "different-symbol", "product_id": 42, "symbol": "ETHUSD", "size": 8},
        {"id": "nested-match", "product": {"id": 42, "symbol": "BTCUSD"}, "size": 2},
        {"id": "no-identity", "size": 7},
    ]
    client = PositionClient(product, {"success": True, "data": {"result": rows}})

    result = client.get_open_positions("BTCUSDT")

    assert [position["id"] for position in result] == ["match", "nested-match"]
    assert client.calls == [("GET", "/v2/positions?product_id=42", None, True)]


def test_get_open_positions_does_not_issue_broad_request_for_unknown_symbol():
    client = PositionClient(None, {"success": True, "data": {"result": [{"size": 1}]}})

    assert client.get_open_positions("UNKNOWNUSDT") == []
    assert client.calls == []


def test_get_open_positions_rejects_invalid_product_id_without_request():
    client = PositionClient({"id": "not-an-id", "symbol": "BTCUSD"},
                            {"success": True, "data": {"result": []}})

    assert client.get_open_positions("BTCUSDT") == []
    assert client.calls == []


def test_get_open_positions_fails_closed_on_malformed_result():
    client = PositionClient({"id": 42, "symbol": "BTCUSD"},
                            {"success": True, "data": {"result": {"unexpected": "shape"}}})

    assert client.get_open_positions("BTCUSDT") == []
    assert client.calls == [("GET", "/v2/positions?product_id=42", None, True)]

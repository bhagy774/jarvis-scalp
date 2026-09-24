import json


def test_restart_reconciliation_uses_saved_state_and_never_places_orders(tmp_path):
    from jarvis_watchdog import load_state, reconcile_state, save_state

    state_path = tmp_path / "jarvis_state.json"
    local = [{"id": "local-1", "symbol": "BTCUSDT", "status": "OPEN"}]
    assert save_state(local, path=str(state_path))

    # A fresh load models recovery after process restart; the watcher only
    # reports exchange/local differences and must never issue a mutation.
    restored = load_state(path=str(state_path))
    assert restored["open_trades"] == local

    class ReadOnlyVenue:
        def __init__(self):
            self.orders = 0
        def get_open_positions(self):
            return [{"symbol": "BTCUSDT", "size": "1"},
                    {"symbol": "ETHUSDT", "size": "2"}]
        def place_order(self, *_args, **_kwargs):
            self.orders += 1
            raise AssertionError("recovery must not place orders")

    venue = ReadOnlyVenue()
    report = reconcile_state(venue, state_path=str(state_path))
    assert report["exchange_ok"]
    assert report["local_trades"] == 1
    assert report["exchange_positions"] == 2
    assert report["mismatches"]
    assert venue.orders == 0


def test_restart_reconciliation_reports_disconnect_without_inventing_flatness(tmp_path):
    from jarvis_watchdog import reconcile_state, save_state

    state_path = tmp_path / "jarvis_state.json"
    assert save_state([{"id": "local-1", "symbol": "BTCUSDT"}], path=str(state_path))

    class DisconnectedVenue:
        def get_open_positions(self):
            raise TimeoutError("simulated network disconnect")
        def place_order(self, *_args, **_kwargs):
            raise AssertionError("recovery must not place orders")

    report = reconcile_state(DisconnectedVenue(), state_path=str(state_path))
    assert not report["exchange_ok"]
    assert "exchange API error" in report["error"]
    assert report["exchange_positions"] is None  # unavailable is not a flat-account response
    assert report["local_trades"] == 1

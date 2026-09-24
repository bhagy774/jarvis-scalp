from jarvis_coin_scanner import JarvisCoinScanner


def test_unknown_position_state_fails_closed(monkeypatch):
    scanner = JarvisCoinScanner(
        position_check_fn=lambda: (_ for _ in ()).throw(RuntimeError("unknown"))
    )
    scanner._fetch_binance_stats_bulk = lambda: {
        "BTCUSDT": {"quoteVolume": "6000000", "priceChangePercent": "1",
                     "highPrice": "2", "lowPrice": "1", "lastPrice": "1.5"}
    }
    scanner._score_coin = lambda *args, **kwargs: {
        "volume_24h_usdt": 6000000, "total": 1
    }
    assert scanner.run_now() == ""
    assert scanner.get_best_symbol() == ""

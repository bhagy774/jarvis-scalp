import pytest
from unittest.mock import patch, MagicMock
import binance_data
from binance_data import BinanceData

def test_get_live_price_success():
    bd = BinanceData()
    # Mocking _get to prevent network call
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"price": "60000.0"}

    with patch.object(bd, '_get', return_value=mock_resp):
        price = bd.get_live_price("BTCUSDT")

    assert price == 60000.0
    assert bd.get_last_source()["source"] == "binance_spot"
    assert bd.get_last_source()["market_semantics"] == "spot"

def test_get_live_price_bybit_fallback():
    bd = BinanceData()

    # Binance fails (returns None as implemented when blocked)
    # Bybit fallback requires mocking requests.Session.get
    mock_bybit_resp = MagicMock()
    mock_bybit_resp.status_code = 200
    mock_bybit_resp.json.return_value = {"result": {"list": [{"lastPrice": "59000.0"}]}}

    with patch.object(bd, '_get', return_value=None):
        with patch.object(bd.session, 'get', return_value=mock_bybit_resp):
            price = bd.get_live_price("BTCUSDT")

    assert price == 59000.0
    assert bd.get_last_source()["source"] == "bybit_linear_perpetual"

def test_get_historical_candles_success():
    bd = BinanceData()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    # Binance klines format: [open_time, open, high, low, close, volume, ...]
    mock_resp.json.return_value = [
        [1700000000000, "10.0", "15.0", "5.0", "12.0", "100.0"]
    ]

    with patch.object(bd, '_get', return_value=mock_resp):
        candles = bd.get_historical_candles("BTCUSDT", "1m", 1)

    assert len(candles) == 1
    c = candles[0]
    assert c["time"] == 1700000000  # ms to s conversion
    assert c["open"] == 10.0
    assert c["high"] == 15.0
    assert c["low"] == 5.0
    assert c["close"] == 12.0
    assert c["volume"] == 100.0
    assert bd.get_last_source()["source"] == "binance_spot"

def test_get_bid_ask():
    bd = BinanceData()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"bidPrice": "100.0", "askPrice": "102.0"}

    with patch.object(bd, '_get', return_value=mock_resp):
        result = bd.get_bid_ask("BTCUSDT")

    assert result["bid"] == 100.0
    assert result["ask"] == 102.0
    assert result["spread"] == 2.0
    assert result["source"] == "binance_spot"

def test_get_funding_rate():
    bd = BinanceData()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "lastFundingRate": "0.001",
        "nextFundingTime": 1700000000000,
        "markPrice": "60000.0"
    }

    with patch.object(bd, '_get', return_value=mock_resp):
        with patch('time.time', return_value=1699996400):  # 3600 seconds (1h) before nextFundingTime
            result = bd.get_funding_rate("BTCUSDT")

    assert result["funding_rate"] == 0.001
    assert result["funding_rate_pct"] == 0.1
    assert result["next_funding_time"] == 1700000000000
    assert result["countdown_str"] == "01h 00m"
    assert result["markPrice" if "markPrice" in result else "mark_price"] == 60000.0
    assert result["sentiment"] == "BULLISH"
    assert result["source"] == "binance_futures"

def test_get_open_interest():
    bd = BinanceData()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "openInterest": "500.5",
        "time": 1700000000000
    }

    with patch.object(bd, '_get', return_value=mock_resp):
        result = bd.get_open_interest("BTCUSDT")

    assert result["open_interest"] == 500.5
    assert result["timestamp"] == 1700000000000
    assert result["source"] == "binance_futures"

def test_get_order_book_depth():
    bd = BinanceData()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "bids": [["100.0", "1.0"]],
        "asks": [["102.0", "2.0"]]
    }

    with patch.object(bd, '_get', return_value=mock_resp):
        result = bd.get_order_book_depth("BTCUSDT")

    assert result["top_bid"] == 100.0
    assert result["top_ask"] == 102.0
    assert result["total_bid_vol"] == 1.0
    assert result["total_ask_vol"] == 2.0
    # Imbalance: (1 - 2) / 3 = -0.3333... => -33.33%
    assert result["imbalance_pct"] == -33.33
    assert result["source"] == "binance_spot"

def test_get_24h_stats():
    bd = BinanceData()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "priceChangePercent": "5.5",
        "volume": "100.0",
        "quoteVolume": "6000000.0",
        "highPrice": "65000.0",
        "lowPrice": "55000.0"
    }

    with patch.object(bd, '_get', return_value=mock_resp):
        result = bd.get_24h_stats("BTCUSDT")

    assert result["price_change_pct"] == 5.5
    assert result["volume_24h_btc"] == 100.0
    assert result["volume_24h_usdt"] == 6000000.0
    assert result["high_24h"] == 65000.0
    assert result["low_24h"] == 55000.0
    assert result["source"] == "binance_spot"

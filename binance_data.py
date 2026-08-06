#!/usr/bin/env python3
"""
Binance Public Data Wrapper for Jarvis
- No API Key required (public endpoints only)
- Replaces Delta Exchange for price + candle data
- Keeps Delta Exchange for options data + trade execution

Endpoints used:
  GET /api/v3/ticker/price       -> Live real-time price
  GET /api/v3/klines             -> OHLCV candle data
"""

import requests
import logging
import time
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

BINANCE_BASE_URL = "https://api.binance.com"

# Map Jarvis resolution names → Binance interval names
RESOLUTION_MAP = {
    "1m":  "1m",
    "3m":  "3m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "1h":  "1h",
    "2h":  "2h",
    "4h":  "4h",
    "1d":  "1d",
}


class BinanceData:
    """
    Public Binance market data client.
    Drop-in replacement for DeltaExchangeData for price + candles.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "JarvisTradingSystem/2.0"
        })
        self._last_price: float = 0.0
        self._last_price_ts: float = 0.0
        self._price_ttl: float = 3.0  # cache live price for 3 seconds max

    # ─────────────────────────────────────────────
    # 1. LIVE PRICE
    # ─────────────────────────────────────────────

    def get_live_price(self, symbol: str = "BTCUSDT") -> float:
        """
        Fetch real-time last traded price from Binance.
        Cached for 3s to avoid hammering the API.
        """
        now = time.time()
        if self._last_price > 0 and (now - self._last_price_ts) < self._price_ttl:
            return self._last_price  # return cached

        sym = symbol.upper().replace("USD", "USDT") if "USDT" not in symbol.upper() else symbol.upper()
        try:
            resp = self.session.get(
                f"{BINANCE_BASE_URL}/api/v3/ticker/price",
                params={"symbol": sym},
                timeout=5
            )
            if resp.status_code == 200:
                price = float(resp.json().get("price", 0))
                if price > 0:
                    self._last_price = price
                    self._last_price_ts = now
                    logger.debug(f"[BINANCE PRICE] {sym} = ${price:,.2f}")
                    return price
            else:
                logger.warning(f"[BINANCE PRICE] HTTP {resp.status_code}: {resp.text[:80]}")
        except Exception as e:
            logger.warning(f"[BINANCE PRICE] Error: {e}")

        return self._last_price  # return last known price as fallback

    # ─────────────────────────────────────────────
    # 2. HISTORICAL CANDLES (OHLCV)
    # ─────────────────────────────────────────────

    def get_historical_candles(
        self,
        symbol: str = "BTCUSDT",
        resolution: str = "1m",
        limit: int = 500
    ) -> List[Dict]:
        """
        Fetch OHLCV candles from Binance.
        Returns list of dicts with keys: time, open, high, low, close, volume
        Compatible with Delta Exchange candle format used by Jarvis.
        """
        sym = symbol.upper().replace("USD", "USDT") if "USDT" not in symbol.upper() else symbol.upper()
        interval = RESOLUTION_MAP.get(resolution, resolution)
        limit = min(limit, 1000)  # Binance max per request = 1000

        try:
            resp = self.session.get(
                f"{BINANCE_BASE_URL}/api/v3/klines",
                params={"symbol": sym, "interval": interval, "limit": limit},
                timeout=10
            )
            if resp.status_code == 200:
                raw = resp.json()
                candles = []
                for k in raw:
                    candles.append({
                        "time":   int(k[0]) // 1000,   # ms → seconds
                        "open":   float(k[1]),
                        "high":   float(k[2]),
                        "low":    float(k[3]),
                        "close":  float(k[4]),
                        "volume": float(k[5]),
                    })
                logger.info(f"[BINANCE] {sym} {interval}: {len(candles)} candles fetched")
                return candles
            else:
                logger.warning(f"[BINANCE CANDLES] HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            logger.warning(f"[BINANCE CANDLES] Error: {e}")

        return []

    # ─────────────────────────────────────────────
    # 3. BID / ASK PRICE (for Part 12)
    # ─────────────────────────────────────────────

    def get_bid_ask(self, symbol: str = "BTCUSDT") -> dict:
        """
        Fetch real-time best Bid and Ask price from Binance.
        Uses /api/v3/bookTicker — no API key needed.
        Returns: { "bid": float, "ask": float, "spread": float }
        Used by: Part 12 (GPUOrderExecutionEngine)
        """
        sym = symbol.upper().replace("USD", "USDT") if "USDT" not in symbol.upper() else symbol.upper()
        try:
            resp = self.session.get(
                f"{BINANCE_BASE_URL}/api/v3/bookTicker",
                params={"symbol": sym},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                bid = float(data.get("bidPrice", 0))
                ask = float(data.get("askPrice", 0))
                spread = round(ask - bid, 2)
                logger.debug(f"[BINANCE BID/ASK] Bid: ${bid:,.2f} | Ask: ${ask:,.2f} | Spread: ${spread}")
                return {"bid": bid, "ask": ask, "spread": spread}
            else:
                logger.warning(f"[BINANCE BID/ASK] HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"[BINANCE BID/ASK] Error: {e}")

        # Fallback: use live price as both bid and ask
        price = self.get_live_price(symbol)
        return {"bid": price, "ask": price, "spread": 0.0}

    # ─────────────────────────────────────────────
    # 4. MULTI-TIMEFRAME FETCH (MTF)
    # ─────────────────────────────────────────────

    def fetch_mtf_candles(
        self,
        symbol: str = "BTCUSDT",
        timeframes: Optional[List[str]] = None,
        limit: int = 500
    ) -> Dict[str, List[Dict]]:
        """
        Fetch candles for multiple timeframes at once.
        Returns: { "1m": [...], "5m": [...], "1h": [...], ... }
        """
        if timeframes is None:
            timeframes = ["1m", "5m", "15m", "1h", "4h"]

        result = {}
        for tf in timeframes:
            candles = self.get_historical_candles(symbol, tf, limit)
            if candles:
                result[tf] = candles
        return result


# ─────────────────────────────────────────────
# Singleton instance (import and reuse)
# ─────────────────────────────────────────────
_binance_instance: Optional[BinanceData] = None


def get_binance_data() -> BinanceData:
    global _binance_instance
    if _binance_instance is None:
        _binance_instance = BinanceData()
    return _binance_instance


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    bd = BinanceData()
    price = bd.get_live_price("BTCUSDT")
    print(f"✅ BTC Live Price: ${price:,.2f}")
    candles = bd.get_historical_candles("BTCUSDT", "1m", 5)
    print(f"✅ Last 5 candles: {[c['close'] for c in candles]}")

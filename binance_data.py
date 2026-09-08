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
import sys
from typing import List, Dict, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

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
    # 5. MARKET MICROSTRUCTURE (Funding, OI, Depth)
    # ─────────────────────────────────────────────

    def get_funding_rate(self, symbol: str = "BTCUSDT") -> Dict:
        """
        Fetch current funding rate and countdown to next funding reset.
        Uses Binance Futures public API (fapi.binance.com).
        """
        sym = symbol.upper().replace("USD", "USDT") if "USDT" not in symbol.upper() else symbol.upper()
        try:
            resp = self.session.get(
                "https://fapi.binance.com/fapi/v1/premiumIndex",
                params={"symbol": sym},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                rate = float(data.get("lastFundingRate", 0.0))
                next_time_ms = int(data.get("nextFundingTime", 0))
                mark_price = float(data.get("markPrice", 0.0))
                now_ms = int(time.time() * 1000)
                countdown_sec = max(0, (next_time_ms - now_ms) // 1000)
                hours = countdown_sec // 3600
                minutes = (countdown_sec % 3600) // 60

                sentiment = "BULLISH" if rate > 0.0001 else ("BEARISH" if rate < -0.0001 else "NEUTRAL")
                return {
                    "funding_rate": rate,
                    "funding_rate_pct": round(rate * 100, 4),
                    "next_funding_time": next_time_ms,
                    "countdown_str": f"{hours:02d}h {minutes:02d}m",
                    "mark_price": mark_price,
                    "sentiment": sentiment,
                    "description": f"{rate * 100:+.4f}% ({sentiment})"
                }
        except Exception as e:
            logger.warning(f"[BINANCE FUNDING] Error: {e}")

        return {
            "funding_rate": 0.0001,
            "funding_rate_pct": 0.01,
            "countdown_str": "unknown",
            "mark_price": self._last_price,
            "sentiment": "NEUTRAL",
            "description": "+0.0100% (NEUTRAL)"
        }

    def get_open_interest(self, symbol: str = "BTCUSDT") -> Dict:
        """
        Fetch futures Open Interest from Binance Futures.
        """
        sym = symbol.upper().replace("USD", "USDT") if "USDT" not in symbol.upper() else symbol.upper()
        try:
            resp = self.session.get(
                "https://fapi.binance.com/fapi/v1/openInterest",
                params={"symbol": sym},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                oi_contracts = float(data.get("openInterest", 0.0))
                return {
                    "open_interest": oi_contracts,
                    "symbol": sym,
                    "timestamp": int(data.get("time", time.time() * 1000))
                }
        except Exception as e:
            logger.warning(f"[BINANCE OI] Error: {e}")

        return {"open_interest": 0.0, "symbol": sym, "timestamp": int(time.time() * 1000)}

    def get_order_book_depth(self, symbol: str = "BTCUSDT", limit: int = 50) -> Dict:
        """
        Fetch order book depth and compute bid/ask volume and order book imbalance.
        """
        sym = symbol.upper().replace("USD", "USDT") if "USDT" not in symbol.upper() else symbol.upper()
        try:
            resp = self.session.get(
                f"{BINANCE_BASE_URL}/api/v3/depth",
                params={"symbol": sym, "limit": limit},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                bids = data.get("bids", [])
                asks = data.get("asks", [])
                total_bid_vol = sum(float(b[1]) for b in bids)
                total_ask_vol = sum(float(a[1]) for a in asks)
                denom = total_bid_vol + total_ask_vol
                imbalance_pct = round(((total_bid_vol - total_ask_vol) / denom) * 100, 2) if denom > 0 else 0.0

                top_bid = float(bids[0][0]) if bids else 0.0
                top_ask = float(asks[0][0]) if asks else 0.0

                # Find major wall in top levels
                max_bid = max(bids, key=lambda x: float(x[1])) if bids else [0, 0]
                max_ask = max(asks, key=lambda x: float(x[1])) if asks else [0, 0]

                return {
                    "imbalance_pct": imbalance_pct,
                    "total_bid_vol": round(total_bid_vol, 2),
                    "total_ask_vol": round(total_ask_vol, 2),
                    "top_bid": top_bid,
                    "top_ask": top_ask,
                    "major_bid_wall": {"price": float(max_bid[0]), "qty": float(max_bid[1])},
                    "major_ask_wall": {"price": float(max_ask[0]), "qty": float(max_ask[1])},
                    "bias": "BULLISH" if imbalance_pct > 5 else ("BEARISH" if imbalance_pct < -5 else "NEUTRAL")
                }
        except Exception as e:
            logger.warning(f"[BINANCE DEPTH] Error: {e}")

        return {
            "imbalance_pct": 0.0,
            "total_bid_vol": 0.0,
            "total_ask_vol": 0.0,
            "top_bid": self._last_price,
            "top_ask": self._last_price,
            "major_bid_wall": {"price": 0.0, "qty": 0.0},
            "major_ask_wall": {"price": 0.0, "qty": 0.0},
            "bias": "NEUTRAL"
        }

    def get_24h_stats(self, symbol: str = "BTCUSDT") -> Dict:
        """
        Fetch 24h ticker price change and volume statistics.
        """
        sym = symbol.upper().replace("USD", "USDT") if "USDT" not in symbol.upper() else symbol.upper()
        try:
            resp = self.session.get(
                f"{BINANCE_BASE_URL}/api/v3/ticker/24hr",
                params={"symbol": sym},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "price_change_pct": float(data.get("priceChangePercent", 0.0)),
                    "volume_24h_btc": float(data.get("volume", 0.0)),
                    "volume_24h_usdt": float(data.get("quoteVolume", 0.0)),
                    "high_24h": float(data.get("highPrice", 0.0)),
                    "low_24h": float(data.get("lowPrice", 0.0)),
                }
        except Exception as e:
            logger.warning(f"[BINANCE 24H] Error: {e}")

        return {
            "price_change_pct": 0.0,
            "volume_24h_btc": 0.0,
            "volume_24h_usdt": 0.0,
            "high_24h": self._last_price,
            "low_24h": self._last_price,
        }


# ─────────────────────────────────────────────
# Singleton instance (import and reuse)
# ─────────────────────────────────────────────
_binance_instance: Optional[BinanceData] = None


def get_binance_data() -> BinanceData:
    global _binance_instance
    if _binance_instance is None:
        _binance_instance = BinanceData()
    return _binance_instance


def get_btc_price_binance(symbol: str = "BTCUSDT") -> float:
    return get_binance_data().get_live_price(symbol)


def get_ohlcv_binance(symbol: str = "BTCUSDT", resolution: str = "5m", limit: int = 100):
    candles = get_binance_data().get_historical_candles(symbol, resolution, limit)
    try:
        import pandas as pd
        if candles:
            return pd.DataFrame(candles)
    except Exception:
        pass
    return candles


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    bd = BinanceData()
    price = bd.get_live_price("BTCUSDT")
    print(f"✅ BTC Live Price: ${price:,.2f}")
    candles = bd.get_historical_candles("BTCUSDT", "1m", 5)
    print(f"✅ Last 5 candles: {[c['close'] for c in candles]}")
    funding = bd.get_funding_rate("BTCUSDT")
    print(f"✅ Funding Rate: {funding['description']} (Next in {funding['countdown_str']})")
    depth = bd.get_order_book_depth("BTCUSDT", 20)
    print(f"✅ Order Book Imbalance: {depth['imbalance_pct']:+.2f}% ({depth['bias']})")
    stats = bd.get_24h_stats("BTCUSDT")
    print(f"✅ 24h Vol: ${stats['volume_24h_usdt']/1e9:.2f}B (High: ${stats['high_24h']:,.0f}, Low: ${stats['low_24h']:,.0f})")

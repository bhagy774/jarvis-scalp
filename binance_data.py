#!/usr/bin/env python3
"""
Binance Public Data Wrapper for Jarvis
- No API Key required (public endpoints only)
- Replaces Delta Exchange for price + candle data
- Keeps Delta Exchange for options data + trade execution
- Auto-fallback to Binance mirrors on HTTP 451 (geo-restriction)
- Ultimate fallback to Bybit public API when all Binance endpoints are blocked

Endpoints used:
  Binance: GET /api/v3/ticker/price, /api/v3/klines
  Bybit:   GET /v5/market/tickers, /v5/market/kline  (fallback, no auth needed)
"""

import os
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

# Primary + fallback base URLs (tried in order on geo-restriction / failure)
# api.binance.us is the US-compliant endpoint; api1/api2/api3 are Binance CDN mirrors
BINANCE_BASE_URLS = [
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api.binance.us",       # Binance US (geo-unrestricted for most regions)
]
BINANCE_FAPI_URLS = [
    "https://fapi.binance.com",
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
]
BINANCE_BASE_URL = BINANCE_BASE_URLS[0]  # kept for backward compat

# Bybit public API — used as ultimate fallback when Binance is geo-blocked
BYBIT_BASE_URL = "https://api.bybit.com"

# Bybit interval map (Binance format -> Bybit format)
BYBIT_INTERVAL_MAP = {
    "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
    "1h": "60", "2h": "120", "4h": "240", "1d": "D",
}

# Optional: set BINANCE_PROXY env var to route via proxy
# Example: BINANCE_PROXY=socks5://127.0.0.1:1080  or  http://user:pass@host:port
_PROXY = os.environ.get("BINANCE_PROXY", "").strip()

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
            "User-Agent": "Mozilla/5.0 (JarvisTradingSystem/2.0)"
        })
        # Apply proxy if configured
        if _PROXY:
            self.session.proxies = {"http": _PROXY, "https": _PROXY}
            logger.info(f"[BINANCE] Using proxy: {_PROXY}")

        self._last_price: float = 0.0
        self._last_price_ts: float = 0.0
        self._price_ttl: float = 3.0  # cache live price for 3 seconds max
        self._active_base_url: str = BINANCE_BASE_URLS[0]
        self._active_fapi_url: str = BINANCE_FAPI_URLS[0]

        # Geo-block cache: if ALL Binance endpoints return 451, skip them for
        # _GEO_BLOCK_TTL seconds and go straight to Bybit / Delta fallback.
        self._binance_blocked: bool = False
        self._binance_blocked_until: float = 0.0
        self._GEO_BLOCK_TTL: float = 300.0   # re-check Binance every 5 minutes

    # ─────────────────────────────────────────────
    # INTERNAL: geo-aware GET with auto-fallback
    # ─────────────────────────────────────────────

    def _get(self, path: str, params: dict = None, timeout: int = 5,
             base_urls: List[str] = None) -> Optional[requests.Response]:
        """
        Try each base URL in order. On HTTP 451 (geo-restricted) or connection
        error, automatically fall back to the next mirror.
        If ALL mirrors are 451-blocked, caches the block state for 5 minutes
        to avoid spamming logs and wasting network calls.
        Returns the first successful Response, or None.
        """
        if base_urls is None:
            base_urls = BINANCE_BASE_URLS

        # Fast-path: if we already know Binance is geo-blocked, skip all mirrors
        if base_urls is BINANCE_BASE_URLS and self._binance_blocked:
            if time.time() < self._binance_blocked_until:
                return None   # still blocked — caller will use Bybit/Delta
            else:
                # Block TTL expired — try Binance again
                self._binance_blocked = False
                logger.info("[BINANCE] Re-checking Binance endpoints after geo-block cooldown...")

        all_451 = True
        for base_url in base_urls:
            try:
                url = f"{base_url}{path}"
                resp = self.session.get(url, params=params, timeout=timeout)
                if resp.status_code == 451:
                    logger.debug(f"[BINANCE] HTTP 451 on {base_url} — trying next mirror...")
                    continue
                all_451 = False
                # Update active URL to the one that worked
                if base_urls is BINANCE_BASE_URLS:
                    self._active_base_url = base_url
                elif base_urls is BINANCE_FAPI_URLS:
                    self._active_fapi_url = base_url
                return resp
            except Exception as e:
                all_451 = False
                logger.debug(f"[BINANCE] {base_url} failed: {e} — trying next...")
                continue

        if all_451 and base_urls is BINANCE_BASE_URLS:
            if not self._binance_blocked:
                logger.warning("[BINANCE] All endpoints geo-blocked (HTTP 451). "
                               f"Switching to Bybit/Delta fallback for {int(self._GEO_BLOCK_TTL/60)} min.")
            self._binance_blocked = True
            self._binance_blocked_until = time.time() + self._GEO_BLOCK_TTL
        elif not self._binance_blocked:
            logger.warning("[BINANCE] All Binance endpoints geo-blocked — switching to Bybit fallback.")
        return None

    # ─────────────────────────────────────────────
    # INTERNAL: Bybit fallback helpers
    # ─────────────────────────────────────────────

    def _bybit_get_price(self, symbol: str) -> float:
        """Fetch live price from Bybit (fallback when Binance is geo-blocked)."""
        sym = symbol.upper().replace("USD", "USDT") if "USDT" not in symbol.upper() else symbol.upper()
        try:
            resp = self.session.get(
                f"{BYBIT_BASE_URL}/v5/market/tickers",
                params={"category": "linear", "symbol": sym},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("result", {}).get("list", [])
                if items:
                    price = float(items[0].get("lastPrice", 0))
                    if price > 0:
                        logger.info(f"[BYBIT FALLBACK] {sym} = ${price:,.2f}")
                        return price
        except Exception as e:
            logger.warning(f"[BYBIT FALLBACK] Price error: {e}")
        return 0.0

    def _bybit_get_candles(self, symbol: str, resolution: str, limit: int) -> List[Dict]:
        """Fetch OHLCV candles from Bybit (fallback when Binance is geo-blocked)."""
        sym = symbol.upper().replace("USD", "USDT") if "USDT" not in symbol.upper() else symbol.upper()
        interval = BYBIT_INTERVAL_MAP.get(resolution, "1")
        try:
            resp = self.session.get(
                f"{BYBIT_BASE_URL}/v5/market/kline",
                params={"category": "linear", "symbol": sym,
                        "interval": interval, "limit": min(limit, 1000)},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                raw = data.get("result", {}).get("list", [])
                # Bybit returns newest first — reverse to chronological order
                candles = []
                for k in reversed(raw):
                    # k = [startTime, open, high, low, close, volume, turnover]
                    candles.append({
                        "time":   int(k[0]) // 1000,
                        "open":   float(k[1]),
                        "high":   float(k[2]),
                        "low":    float(k[3]),
                        "close":  float(k[4]),
                        "volume": float(k[5]),
                    })
                logger.info(f"[BYBIT FALLBACK] {sym} {interval}: {len(candles)} candles fetched")
                return candles
        except Exception as e:
            logger.warning(f"[BYBIT FALLBACK] Candles error: {e}")
        return []

    # ─────────────────────────────────────────────
    # 1. LIVE PRICE
    # ─────────────────────────────────────────────

    def get_live_price(self, symbol: str = "BTCUSDT") -> float:
        """
        Fetch real-time last traded price from Binance.
        Cached per-symbol for 3s to avoid hammering the API.
        """
        now = time.time()
        sym = symbol.upper().replace("USD", "USDT") if "USDT" not in symbol.upper() else symbol.upper()

        # --- FIX: per-symbol cache (old code used single _last_price for ALL symbols) ---
        if not hasattr(self, '_price_cache'):
            self._price_cache = {}  # {sym: (price, ts)}
        cached = self._price_cache.get(sym)
        if cached and cached[0] > 0 and (now - cached[1]) < self._price_ttl:
            return cached[0]  # return cached price for THIS symbol

        try:
            resp = self._get("/api/v3/ticker/price", params={"symbol": sym}, timeout=5)
            if resp is not None and resp.status_code == 200:
                price = float(resp.json().get("price", 0))
                if price > 0:
                    self._price_cache[sym] = (price, now)
                    self._last_price = price  # keep for backward compat
                    self._last_price_ts = now
                    logger.debug(f"[BINANCE PRICE] {sym} = ${price:,.2f}")
                    return price
            elif resp is not None:
                logger.warning(f"[BINANCE PRICE] HTTP {resp.status_code}: {resp.text[:80]}")
        except Exception as e:
            logger.warning(f"[BINANCE PRICE] Error: {e}")

        # Binance fully blocked — try Bybit
        bybit_price = self._bybit_get_price(sym)
        if bybit_price > 0:
            self._price_cache[sym] = (bybit_price, now)
            self._last_price = bybit_price
            self._last_price_ts = now
            return bybit_price

        # Return last known price for THIS symbol only (not another symbol's price)
        return cached[0] if cached else 0.0

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

        self.last_candle_source = None
        try:
            resp = self._get("/api/v3/klines",
                             params={"symbol": sym, "interval": interval, "limit": limit},
                             timeout=10)
            if resp is not None and resp.status_code == 200:
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
                self.last_candle_source = "binance"
                logger.info(f"[BINANCE] {sym} {interval}: {len(candles)} candles fetched")
                return candles
            elif resp is not None:
                logger.warning(f"[BINANCE CANDLES] HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            logger.warning(f"[BINANCE CANDLES] Error: {e}")

        # Binance fully blocked — try Bybit.  Keep provenance explicit so a
        # same-symbol fallback cannot masquerade as the primary source.
        candles = self._bybit_get_candles(symbol, resolution, limit)
        self.last_candle_source = "bybit" if candles else None
        return candles

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
            resp = self._get("/api/v3/bookTicker", params={"symbol": sym}, timeout=5)
            if resp is not None and resp.status_code == 200:
                data = resp.json()
                bid = float(data.get("bidPrice", 0))
                ask = float(data.get("askPrice", 0))
                spread = round(ask - bid, 2)
                logger.debug(f"[BINANCE BID/ASK] Bid: ${bid:,.2f} | Ask: ${ask:,.2f} | Spread: ${spread}")
                return {"bid": bid, "ask": ask, "spread": spread}
            elif resp is not None:
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
            resp = self._get("/fapi/v1/premiumIndex", params={"symbol": sym},
                             timeout=5, base_urls=BINANCE_FAPI_URLS)
            if resp is not None and resp.status_code == 200:
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
            resp = self._get("/fapi/v1/openInterest", params={"symbol": sym},
                             timeout=5, base_urls=BINANCE_FAPI_URLS)
            if resp is not None and resp.status_code == 200:
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
            resp = self._get("/api/v3/depth",
                             params={"symbol": sym, "limit": limit}, timeout=5)
            if resp is not None and resp.status_code == 200:
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
            resp = self._get("/api/v3/ticker/24hr", params={"symbol": sym}, timeout=5)
            if resp is not None and resp.status_code == 200:
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

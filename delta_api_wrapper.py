#!/usr/bin/env python3
"""
Delta Exchange Unified Data Wrapper for Jarvis
Replaces:
1. Binance (Charts/Prices)
2. Deribit (Options/Greeks)

Features:
- Live Price Fetching
- Historical Data (Pagination for Deep Backtesting)
- Options Chain & Greeks
- Order Book Level 2
- Authentication Support
"""

import os
import time
import hmac
import hashlib
import requests
import logging
import json
import re
import copy
from urllib.parse import urlencode
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone

from options_chain import build_provider_chain, combine_provider_chains, payout_max_pain

# FIX #9: Load API keys from environment variables (or .env file)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional

# API keys loaded from environment. Set these in your .env file:
#   DELTA_API_KEY=your_key_here
#   DELTA_API_SECRET=your_secret_here
# Credentials must be supplied by the deployment environment.  Do not put
# fallback credentials in source code: an unauthenticated private request is
# safer than silently signing it with a leaked or unintended account.
DEMO_API_KEY = os.environ.get("DELTA_API_KEY")
DEMO_API_SECRET = os.environ.get("DELTA_API_SECRET")

logger = logging.getLogger(__name__)

class DeltaExchangeData:
    """
    Unified Data Wrapper for Delta Exchange.
    Handles all data ingestion for Jarvis.
    """
    
    # ── MAINNET vs TESTNET controlled via .env ──────────────────────────────
    # DELTA_USE_MAINNET=true  → real orders on api.delta.exchange
    # DELTA_USE_MAINNET=false → paper orders on testnet (default, safe)
    _USE_MAINNET = os.environ.get("DELTA_USE_MAINNET", "false").lower() == "true"
    PRIVATE_URL  = ("https://api.india.delta.exchange"      # MAINNET India (real money!)
                    if _USE_MAINNET else
                    "https://cdn-ind.testnet.deltaex.org")  # TESTNET (safe test)
    PUBLIC_URL   = "https://api.india.delta.exchange"  # India endpoint for real prices
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        # Explicit None = no credentials provided by caller (safety tests rely on this).
        # Empty string also = no credentials. Only fall back to env-loaded DEMO keys
        # when caller uses the default (passes nothing at all).
        self._credentials_explicit = (api_key is not None or api_secret is not None)
        self.api_key    = api_key    if api_key    is not None else (DEMO_API_KEY    or "")
        self.api_secret = api_secret if api_secret is not None else (DEMO_API_SECRET or "")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "JarvisTradingSystem/2.0"
        })
        self._cache = {}
        self._options_chain_cache = {}

        # ── HYBRID: Use Binance for price+candles (more accurate, no API key needed) ──
        try:
            from binance_data import BinanceData
            self._binance = BinanceData()
            logger.info("[HYBRID] ✅ Binance data source loaded for price + candles")
        except ImportError:
            self._binance = None
            logger.warning("[HYBRID] ⚠️  binance_data.py not found, using Delta for everything")

        # Public, read-only options adapter. It is constructed lazily without
        # making a network request; unsupported eAPI schemas fail closed.
        try:
            from binance_options_client import BinanceOptionsClient
            self._binance_options = BinanceOptionsClient()
        except ImportError:
            self._binance_options = None

    @staticmethod
    def _perpetual_fallback_allowed() -> bool:
        """Require an explicit opt-in before treating Bybit perps as spot data."""
        return os.environ.get("JARVIS_ALLOW_PERPETUAL_FALLBACK", "0").lower() in {"1", "true", "yes"}

    def _binance_spot_compatible(self) -> bool:
        if not self._binance:
            return False
        try:
            source = self._binance.get_last_source()
            semantics = str(source.get("market_semantics", "")).lower()
            return semantics == "spot" or self._perpetual_fallback_allowed()
        except Exception:
            return False

    def _generate_signature(self, method: str, path: str, payload: str = "") -> Dict[str, str]:
        """Generate HMAC SHA256 Signature for authenticated endpoints."""
        if not self.api_key or not self.api_secret:
            raise ValueError("Delta API credentials are not configured")
        timestamp = str(int(time.time()))
        msg = method + timestamp + path + payload
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {"api-key": self.api_key, "timestamp": timestamp, "signature": signature}

    @staticmethod
    def _diagnostic_error(response) -> str:
        """Return only a bounded, structured, non-secret API diagnostic.

        Response bodies are never logged or echoed: even an error body can
        reflect credentials. Only a strict, short machine error code is safe.
        """
        safe_code = None
        try:
            body = response.json()
            candidate = body.get("error") if isinstance(body, dict) else None
            if isinstance(candidate, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,31}", candidate):
                safe_code = candidate
        except (ValueError, TypeError, AttributeError):
            pass
        if safe_code:
            return f"HTTP {response.status_code}: {safe_code}"
        return f"HTTP {response.status_code}"

    def _request(self, method: str, endpoint: str, payload: Dict = None, authorized: bool = False) -> Dict:
        """
        Unified Request Handler.
        authorized=True -> Uses Testnet/Private URL
        authorized=False -> Uses Production/Public URL (Real Prices)
        """
        try:
            # Fail before constructing or sending a private request when the
            # process was not explicitly provisioned with credentials.
            # Also block if caller explicitly passed None (no credentials intended).
            _no_creds = (not self.api_key or not self.api_secret)
            _explicit_none = getattr(self, "_credentials_explicit", True) is False
            if authorized and (_no_creds or _explicit_none):
                return {"success": False, "error": "Delta API credentials are not configured"}
            base_url = self.PRIVATE_URL if authorized else self.PUBLIC_URL
            headers = {}
            payload_str = ""
            req_args = {}

            if authorized:
                if method in ["POST", "PUT", "DELETE"] and payload:
                    # JSON body — sign the JSON string
                    payload_str = json.dumps(payload, separators=(',', ':'))
                    auth_headers = self._generate_signature(method, endpoint, payload_str)
                    headers.update(auth_headers)
                    req_args["data"] = payload_str  # send exact signed string

                elif method == "GET" and payload:
                    # FIX BUG1: Build query string, append to path for signature,
                    # then use full URL directly — don't also pass params= (double send bug)
                    query_str = urlencode(payload)
                    sign_path = f"{endpoint}?{query_str}"
                    auth_headers = self._generate_signature(method, sign_path, "")
                    headers.update(auth_headers)
                    url = f"{base_url}{sign_path}"  # full URL with query baked in
                    start_t = time.time()
                    response = self.session.request(method, url, headers=headers, timeout=10)
                    elapsed = time.time() - start_t
                    logger.debug(f"[DELTA API] {method} {endpoint} took {elapsed:.2f}s")
                    if 200 <= response.status_code < 300:
                        return {"success": True, "data": response.json()}
                    logger.error("[DELTA API] %s %s status=%s", method, endpoint.split("?", 1)[0], response.status_code)
                    return {"success": False, "error": self._diagnostic_error(response)}

                else:
                    # authorized GET with no payload
                    auth_headers = self._generate_signature(method, endpoint, "")
                    headers.update(auth_headers)

            # Non-authorized OR authorized POST/DELETE path continues here
            url = f"{base_url}{endpoint}"
            if method.upper() == "GET" and not authorized:
                req_args["params"] = payload
            elif not req_args.get("data"):
                req_args["json"] = payload

            start_t = time.time()
            response = self.session.request(method, url, headers=headers, timeout=10, **req_args)
            elapsed = time.time() - start_t
            logger.debug(f"[DELTA API] {method} {endpoint} took {elapsed:.2f}s")

            if 200 <= response.status_code < 300:
                return {"success": True, "data": response.json()}
            logger.error("[DELTA API] %s %s status=%s", method, endpoint.split("?", 1)[0], response.status_code)
            return {"success": False, "error": self._diagnostic_error(response)}

        except Exception as e:
            logger.error("[DELTA API] Connection failed: %s", type(e).__name__)
            return {"success": False, "error": "Delta request failed"}

    # ==========================================
    # 1. LIVE MARKET DATA (Replaces Binance)
    # ==========================================

    def get_balance(self) -> Dict:
        """Fetch wallet balance"""
        return self._request("GET", "/v2/wallet/balances", authorized=True)

    def get_live_price(self, symbol: str = "BTCUSDT") -> float:
        """Get real-time BTC price — uses Binance (most accurate), falls back to Delta."""
        # ── PRIMARY: Binance real-time price (no API key, most accurate) ──
        if self._binance:
            try:
                price = self._binance.get_live_price(symbol)
                if price > 0 and self._binance_spot_compatible():
                    return price
                if price > 0:
                    logger.warning("[HYBRID] Rejecting non-spot fallback price for %s; set JARVIS_ALLOW_PERPETUAL_FALLBACK=1 only when explicitly compatible", symbol)
            except Exception as e:
                logger.warning(f"[BINANCE PRICE] Failed: {e}")

        # ── FALLBACK: Delta Exchange mark_price ──
        symbols_to_try = ["BTCUSDT", "BTCUSD"] if "BTC" in symbol.upper() else [symbol]
        for sym in symbols_to_try:
            try:
                res = self._request("GET", "/v2/tickers", {"symbol": sym})
                if res["success"]:
                    for t in res["data"].get("result", []):
                        if t.get("symbol") == sym:
                            price = float(t.get("mark_price", 0) or t.get("spot_price", 0) or t.get("close", 0))
                            if price > 0:
                                return price
            except Exception as e:
                logger.warning(f"[DELTA PRICE] Failed for {sym}: {e}")

        logger.error("[DELTA PRICE] Could not fetch live price")
        return 0.0

    def get_order_book(self, symbol: str = "BTCUSD") -> Dict:
        """Get Bid/Ask — uses Binance bookTicker (real-time), falls back to Delta L2."""
        # ── PRIMARY: Binance bookTicker (real-time, no API key) ──
        if self._binance:
            try:
                ba = self._binance.get_bid_ask(symbol)
                if ba["bid"] > 0 and (
                    str(ba.get("market_semantics", "spot")).lower() == "spot"
                    or self._perpetual_fallback_allowed()
                ):
                    return {
                        "buy": [{"price": str(ba["bid"]), "size": "1"}],
                        "sell": [{"price": str(ba["ask"]), "size": "1"}],
                        "bid": ba["bid"],
                        "ask": ba["ask"],
                        "spread": ba["spread"]
                    }
            except Exception as e:
                logger.warning(f"[BINANCE BID/ASK] Failed: {e}")

        # ── FALLBACK: Delta L2 order book ──
        res = self._request("GET", f"/v2/l2orderbook/{symbol}")
        if res["success"]:
            return res["data"].get("result", {})
        return {}

    def get_bid_ask(self, symbol: str = "BTCUSDT") -> Dict:
        """Convenience: Returns {bid, ask, spread} from Binance bookTicker."""
        if self._binance:
            result = self._binance.get_bid_ask(symbol)
            if result.get("bid", 0) > 0 and (
                str(result.get("market_semantics", "spot")).lower() == "spot"
                or self._perpetual_fallback_allowed()
            ):
                return result
        price = self.get_live_price(symbol)
        return {"bid": price, "ask": price, "spread": 0.0, "source": "delta_or_unavailable", "market_semantics": "unknown"}

    # ==========================================
    # 2. HISTORICAL DATA (Replaces Binance)
    # ==========================================

    def get_historical_candles_with_metadata(
        self, symbol: str = "BTCUSD", resolution: str = "5m", limit: int = 100
    ) -> Dict[str, Any]:
        """Fetch candles with explicit same-instrument source provenance.

        The legacy method below remains list-shaped for existing callers.  Live
        analysis uses this metadata form so Binance/Bybit/Delta fallback is
        visible and cannot overwrite another source's cache entry silently.
        """
        requested_symbol = str(symbol)
        # ── PRIMARY: Binance (which may itself use explicit Bybit fallback) ──
        if self._binance:
            try:
                candles = self._binance.get_historical_candles(symbol, resolution, limit)
                if candles and len(candles) > 0:
                    source = getattr(self._binance, "last_candle_source", None) or "binance"
                    return {"candles": candles, "source": source, "symbol": requested_symbol}
            except Exception as e:
                logger.warning(f"[BINANCE CANDLES] Failed: {e}")

        # ── FALLBACK: Delta Exchange candles, same requested instrument ──
        end_time = int(time.time())
        multipliers = {
            "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
            "1h": 3600, "2h": 7200, "4h": 14400, "1d": 86400,
        }
        if resolution not in multipliers:
            logger.warning("[DELTA CANDLES] Unsupported native resolution: %s", resolution)
            return {"candles": [], "source": "delta", "symbol": requested_symbol}
        start_time = end_time - (limit * multipliers[resolution])
        query_sym = requested_symbol
        if query_sym.upper() in ("BTCUSD", "BTCUSDT", "BTC_USDT"):
            query_sym = "BTCUSDT"
        params = {"symbol": query_sym, "resolution": resolution, "start": start_time, "end": end_time}
        res = self._request("GET", "/v2/history/candles", params)
        if res.get("success"):
            results = res.get("data", {}).get("result", [])
            for row in results:
                if row.get("volume") is None:
                    row["volume"] = 0.0
            return {"candles": results, "source": "delta", "symbol": requested_symbol}
        return {"candles": [], "source": "delta", "symbol": requested_symbol}

    def get_delta_native_candles_with_metadata(
        self, *, symbol: str, resolution: str, limit: int
    ) -> Dict[str, Any]:
        """Fetch Delta candles only, with no Binance or Bybit substitution.

        The multicoin analysis namespace uses this method so a Delta execution
        product is never silently paired with another venue's similarly-named
        ticker. This is a public read-only request and does not authorize orders.
        """
        multipliers = {
            "1m": 60, "3m": 180, "5m": 300, "15m": 900,
            "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400,
        }
        requested_symbol = str(symbol or "").strip().upper()
        if not requested_symbol or resolution not in multipliers:
            return {"candles": [], "source": "delta", "symbol": requested_symbol}
        end_time = int(time.time())
        start_time = end_time - (int(limit) * multipliers[resolution])
        params = {"symbol": requested_symbol, "resolution": resolution,
                  "start": start_time, "end": end_time}
        response = self._request("GET", "/v2/history/candles", params)
        if not response.get("success"):
            return {"candles": [], "source": "delta", "symbol": requested_symbol}
        rows = response.get("data", {}).get("result", [])
        if not isinstance(rows, list):
            return {"candles": [], "source": "delta", "symbol": requested_symbol}
        for row in rows:
            if isinstance(row, dict) and row.get("volume") is None:
                row["volume"] = 0.0
        return {"candles": rows, "source": "delta", "symbol": requested_symbol}

    def get_historical_candles(self, symbol: str = "BTCUSD", resolution: str = "5m", limit: int = 100) -> List[Dict]:
        """Legacy list-shaped wrapper around metadata-bearing candle fetch."""
        return self.get_historical_candles_with_metadata(symbol, resolution, limit).get("candles", [])

    def fetch_deep_history(self, symbol: str, days: int = 30, resolution: str = "1h") -> List[Dict]:
        """
        [TIME-MACHINE SUPPORT]
        Fetch massive historical data using pagination.
        Used by: Smart Backtester
        """
        logger.info(f"[DELTA API] 🕰️ Fetching deep history for {symbol} ({days} days)...")
        all_candles = []
        end_time = int(time.time())
        start_time_final = end_time - (days * 86400)
        
        current_end = end_time
        
        # Paginate backwards
        while current_end > start_time_final:
            current_start = max(start_time_final, current_end - (2000 * 3600)) # Approx chunk
            
            params = {
                "symbol": symbol,
                "resolution": resolution,
                "start": current_start,
                "end": current_end
            }
            res = self._request("GET", "/v2/history/candles", params)
            
            if res["success"]:
                chunk = res["data"].get("result", [])
                if not chunk:
                    break
                for r in chunk:
                    if r.get('volume') is None:
                        r['volume'] = 0.0
                all_candles = chunk + all_candles # Prepend (oldest first)
                # Update pointer
                current_end = int(chunk[-1]["time"]) - 1 
            else:
                break
            
            time.sleep(0.5) # Rate limit protection

        logger.info(f"[DELTA API] ✅ Fetched {len(all_candles)} historical candles")
        return all_candles

    # ==========================================
    # 3. OPTIONS CHAIN & GREEKS (Replaces Deribit)
    # ==========================================

    @staticmethod
    def _delta_ticker_page(response: Dict) -> tuple[list[dict], Any, bool, bool]:
        """Return rows, next cursor, marker-seen and terminal-page evidence."""
        if not isinstance(response, dict) or not response.get("success"):
            return [], None, False, False
        body = response.get("data")
        if not isinstance(body, dict):
            return [], None, False, False
        rows = body.get("result")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            return [], None, False, False
        meta = body.get("meta") if isinstance(body.get("meta"), dict) else None
        paging = body.get("pagination") if isinstance(body.get("pagination"), dict) else meta
        if paging is None:
            return rows, None, False, False
        cursor_key = next((k for k in ("next_cursor", "nextCursor", "next", "after") if k in paging), None)
        more_key = next((k for k in ("has_more", "hasMore", "has_next", "hasNextPage") if k in paging), None)
        marker_seen = cursor_key is not None or more_key is not None
        if not marker_seen:
            return rows, None, False, False
        cursor = paging.get(cursor_key) if cursor_key else None
        more = bool(paging.get(more_key)) if more_key else bool(cursor)
        return rows, cursor if more else None, True, not more

    def get_options_chain(self, underlying: str = "BTC") -> Dict:
        """Fetch current all-page BTC/ETH option chains from supported providers.

        A chain is filter-usable only when the provider schema, identity,
        freshness, and terminal-pagination/manifest evidence all validate.
        Missing fields stay null and are counted; Greeks are never modeled.
        """
        from datetime import datetime, timezone
        from options_snapshot_store import append_snapshot

        asset = str(underlying or "").upper().replace("USDT", "").replace("USD", "")
        cached = getattr(self, "_options_chain_cache", {}).get(asset)
        if cached and time.monotonic() - cached[0] <= 15:
            return copy.deepcopy(cached[1])
        retrieved = datetime.now(timezone.utc)
        if not re.fullmatch(r"[A-Z0-9]{2,12}", asset):
            return combine_provider_chains("", {})
        pages: list[list[dict]] = []
        cursor = None
        marker_seen = False
        terminated = False
        provider_error = None
        max_pages = 100
        page_size = 500
        for page_number in range(max_pages):
            params = {
                "contract_types": "call_options,put_options",
                "underlying_asset_symbols": asset,
                "page_size": page_size,
            }
            if cursor is not None:
                params["after"] = cursor
            response = self._request("GET", "/v2/tickers", params)
            rows, next_cursor, has_marker, terminal = self._delta_ticker_page(response)
            if not isinstance(response, dict) or not response.get("success"):
                provider_error = (response.get("error") if isinstance(response, dict) else None) or "provider_request_failed"
                break
            if not isinstance(response.get("data"), dict) or not isinstance(response["data"].get("result"), list):
                provider_error = "provider_schema_invalid"
                break
            pages.append(rows)
            marker_seen = marker_seen or has_marker
            if terminal:
                terminated = True
                break
            if next_cursor is None:
                # A page without an explicit continuation is not completeness evidence.
                break
            if next_cursor == cursor:
                provider_error = "pagination_cursor_did_not_advance"
                break
            cursor = next_cursor
        else:
            provider_error = "pagination_page_limit_reached"
        pagination = {
            "complete": terminated,
            "truncated": bool(provider_error == "pagination_page_limit_reached" or (marker_seen and not terminated)),
            "marker_seen": marker_seen,
            "pages_received": len(pages),
            "page_size_requested": page_size,
            "termination_evidence": "provider_terminal_pagination_marker" if terminated else None,
            "cursor_used": cursor is not None,
        }
        delta_chain = build_provider_chain(
            asset, "Delta", pages, pagination, retrieved_at=retrieved,
            provider_error=provider_error,
        )
        delta_chain["status"] = "ok" if delta_chain["validation"]["usable"] else ("provider_error" if provider_error else "incomplete_or_unverified")
        providers = {"Delta": delta_chain}
        if self._binance_options is not None:
            try:
                binance_chain = self._binance_options.get_options_chain(asset)
                if isinstance(binance_chain, dict):
                    providers["Binance Options"] = binance_chain
            except Exception as exc:
                providers["Binance Options"] = {
                    "venue": "Binance Options", "underlying": asset, "contracts": [], "status": "provider_error",
                    "validation": {"usable": False, "complete": False, "reasons": ["provider_request_failed"], "error_type": type(exc).__name__},
                }
<<<<<<< HEAD
                
                strikes.add(strike)
                chain_data["total_oi"] += oi
                
                if contract_type == "call_options":
                    chain_data["calls"].append(item)
                    total_call_oi += oi
                elif contract_type == "put_options":
                    chain_data["puts"].append(item)
                    total_put_oi += oi
                    
            except Exception:
                continue
                
        # PCR Calculation
        if total_call_oi > 0:
            chain_data["pcr"] = total_put_oi / total_call_oi
            
        # Simplified Max Pain (Weighted Average)
        # Note: Full Max Pain requires iterating all strikes. 
        # For efficiency, we just store the raw lists.
        # Smart Backtester/Live Analyst can calculate specifics.
        chain_data["max_pain"] = self._calculate_max_pain(chain_data)
            
        return chain_data
=======
        chain = combine_provider_chains(asset, providers)
        snapshot_path = os.environ.get("JARVIS_OPTIONS_SNAPSHOT_PATH", "")
        if snapshot_path:
            written = append_snapshot(snapshot_path, chain, captured_at=retrieved)
            chain["snapshot_persistence"] = {"enabled": True, "written": bool(written), "schema": "jarvis.options.snapshot.v1"}
        else:
            chain["snapshot_persistence"] = {"enabled": False, "reason": "JARVIS_OPTIONS_SNAPSHOT_PATH_not_set"}
        self._options_chain_cache[asset] = (time.monotonic(), copy.deepcopy(chain))
        return chain
>>>>>>> 896f0a39576c2dcc9c5699da66df75437f7ac0d4

    def get_institutional_bias(self, underlying: str = "BTC") -> Dict:
        """Apply the existing PCR heuristic only to one validated provider chain."""
        chain = self.get_options_chain(underlying)
        providers = chain.get("providers", {}) if isinstance(chain, dict) else {}
        provider = next((providers.get(name) for name in ("Delta", "Binance Options")
                         if isinstance(providers.get(name), dict)
                         and providers[name].get("validation", {}).get("usable")), None)
        if provider is None:
            validation = chain.get("validation", {}) if isinstance(chain, dict) else {}
            return {
                "bias": "NEUTRAL", "score": 0, "reasons": ["No Data"],
                "raw_data": {"options_validation": validation, "source_provider": None,
                             "provider_status": {name: item.get("status") for name, item in providers.items() if isinstance(item, dict)}},
            }
        all_opts = provider.get("contracts", [])
        metrics = provider.get("metrics", {})
        if not all_opts or not metrics.get("open_interest_complete") or metrics.get("put_call_ratio") is None:
            return {"bias": "NEUTRAL", "score": 0, "reasons": ["No Data"],
                    "raw_data": {"options_validation": provider.get("validation"), "source_provider": provider.get("venue"),
                                 "coverage": provider.get("coverage"), "provider_metrics": metrics}}

        expiries: dict[str, dict[str, float]] = {}
        for option in all_opts:
            exp = option.get("expiry")
            if not exp or option.get("open_interest") is None:
                continue
            row = expiries.setdefault(exp, {"calls": 0.0, "puts": 0.0, "call_volume": 0.0, "put_volume": 0.0})
            side = "calls" if option.get("type") == "call" else "puts"
            row[side] += option["open_interest"]
            vol = option.get("volume")
            if vol is not None:
                row["call_volume" if side == "calls" else "put_volume"] += vol
        reasons = []
        total_score = 0
        for exp in sorted(expiries):
            data = expiries[exp]
            if data["calls"] + data["puts"] < 100:
                continue
            if data["calls"] <= 0:
                continue
            pcr = data["puts"] / data["calls"]
            if pcr > 1.3:
                total_score -= 2
                reasons.append(f"[{exp}] High PCR ({pcr:.2f}); unsigned OI is descriptive, not dealer direction")
            elif pcr < 0.65:
                total_score += 2
                reasons.append(f"[{exp}] Low PCR ({pcr:.2f}); unsigned OI is descriptive, not dealer direction")
        final_bias = "BULLISH" if total_score >= 3 else ("BEARISH" if total_score <= -3 else "NEUTRAL")
        max_pain = metrics.get("max_pain", {})
        max_pain_strike = max_pain.get("strike") if max_pain.get("available") else None
        pcr = metrics.get("put_call_ratio")
        return {
            "bias": final_bias, "score": total_score, "reasons": reasons,
            "pcr": pcr, "max_pain": max_pain_strike,
            "raw_data": {
                "expiries": expiries, "total_oi": sum(c["open_interest"] for c in all_opts),
                "pcr": pcr, "max_pain": max_pain,
                "options_validation": provider.get("validation"),
                "source_provider": provider.get("venue"),
                "coverage": provider.get("coverage"),
                "provider_metrics": metrics,
            },
        }

    def _calculate_max_pain(self, chain: Dict) -> Optional[float]:
        """Return payout-minimizing strike, never the highest-OI strike."""
        try:
            providers = chain.get("providers", {}) if isinstance(chain, dict) else {}
            selected = chain.get("selected_provider") if isinstance(chain, dict) else None
            provider = providers.get(selected) if selected else None
            if isinstance(provider, dict):
                pain = provider.get("metrics", {}).get("max_pain", {})
                return pain.get("strike") if pain.get("available") else None
            pain = payout_max_pain(chain.get("calls", []) + chain.get("puts", []))
            return pain.get("strike") if pain.get("available") else None
        except Exception:
            return None


    # ==========================================
    # 4. OPTIONS EXECUTION & MANAGEMENT (NEW)
    # ==========================================

    def get_nearest_expiries(self, underlying: str = "BTC") -> List[str]:
        """Get sorted list of available option expiry dates"""
        chain = self.get_options_chain(underlying)
        expiries = set()
        for opt in chain.get("calls", []) + chain.get("puts", []):
            exp = opt.get("expiry")
            if exp and exp != "PERPETUAL":
                expiries.add(exp)
        return sorted(list(expiries))

    def get_option_positions(self) -> List[Dict]:
        """Fetch all currently open option positions"""
        res = self._request("GET", "/v2/positions", authorized=True)
        option_positions = []
        if res["success"]:
            for pos in res["data"].get("result", []):
                sym = pos.get("symbol", "")
                if "-C" in sym or "-P" in sym:  # Rough heuristic for option symbols
                    option_positions.append(pos)
        return option_positions

    def place_option_order(self, option_symbol: str, side: str, size: int) -> Dict:
        """Place an option order (wrapper around place_order)"""
        # Note: Delta options often require limit orders or have low liquidity
        # For scalp hedging, we try market first
        return self.place_order(option_symbol, side, size, order_type="market")

    def get_option_by_criteria(self, underlying: str, option_type: str, target_strike: float, expiry_preference: str = "nearest") -> Optional[Dict]:
        """Find best matching option contract"""
        chain = self.get_options_chain(underlying)
        key = "puts" if option_type.upper() == "PUT" else "calls"
        options = chain.get(key, [])
        
        if not options:
            return None
            
        # Filter by expiry if needed
        if expiry_preference != "nearest":
            options = [o for o in options if o.get("expiry") == expiry_preference]
            
        if not options:
            return None
            
        # Find exact strike or closest
        exact = next((o for o in options if o.get("strike") == target_strike), None)
        if exact:
            return exact
            
        return min(options, key=lambda x: abs(x.get("strike", 0) - target_strike))

    # ==========================================
    # 5. ORDER EXECUTION & RISK MANAGEMENT (PHASE 3)
    # ==========================================

    def get_wallet_balance(self) -> float:
        """Get Available Balance for 200x Calculation (USDT, USD, or DETO)."""
        res = self._request("GET", "/v2/wallet/balances", authorized=True)
        if res["success"]:
            try:
                # Find best collateral asset
                balances = res["data"].get("result", [])
                
                # Priority: USDT -> USD -> DETO
                for symbol in ["USDT", "USD", "DETO"]:
                    for asset in balances:
                        if asset["asset_symbol"] == symbol:
                            val = float(asset["available_balance"])
                            if val > 0:
                                return val
                
                # If none have balance, just return the first one found if any
                if balances:
                    return float(balances[0].get("available_balance", 0.0))
            except:
                pass
        return 0.0

    def get_open_positions(self, symbol: str = "BTCUSDT") -> List[Dict]:
        """Get open positions, scoping the private request to one product.

        Delta's positions endpoint uses ``product_id`` for this filter. Resolve
        the caller-facing symbol through the existing product lookup rather
        than sending an unsupported ``symbol`` query parameter or making a
        broad positions request.
        """
        resolved_symbol = None
        product_id = None
        if not symbol:
            # Preserve the explicit unscoped query for callers that intentionally
            # ask for all positions. Instrument-specific reconciliation below
            # must always resolve and scope by a known Delta product ID.
            res = self._request("GET", "/v2/positions", None, authorized=True)
        else:
            product = self._resolve_product(symbol)
            if not isinstance(product, dict):
                logger.error("[DELTA API] Product not found for requested positions")
                return []
            raw_symbol = product.get("symbol")
            if not isinstance(raw_symbol, str) or not raw_symbol.strip():
                logger.error("[DELTA API] Invalid product symbol for requested positions")
                return []
            resolved_symbol = raw_symbol.strip().upper()
            requested = symbol.strip().upper() if isinstance(symbol, str) else ""
            accepted_symbols = {requested}
            if requested.endswith("USDT"):
                accepted_symbols.add(requested[:-4] + "USD")
            elif requested.endswith("USD"):
                accepted_symbols.add(requested[:-3] + "USDT")
            if resolved_symbol not in accepted_symbols:
                logger.error("[DELTA API] Resolved product does not match requested positions symbol")
                return []
            try:
                pid = int(product["id"])
                if pid <= 0:
                    raise ValueError("non-positive product ID")
            except (KeyError, TypeError, ValueError):
                logger.error("[DELTA API] Invalid product ID for requested positions")
                return []
            product_id = pid
            # Build signed URL with product_id as query param (Delta requirement).
            res = self._request("GET", f"/v2/positions?product_id={pid}", None, authorized=True)
        if not isinstance(res, dict) or not res.get("success"):
            return []
        data = res.get("data")
        positions = data.get("result") if isinstance(data, dict) else None
        if not isinstance(positions, list):
            return []
        if resolved_symbol is None:
            return positions

        matched = []
        for position in positions:
            if not isinstance(position, dict):
                continue
            raw_product = position.get("product")
            if raw_product is not None and not isinstance(raw_product, dict):
                continue
            raw_product = raw_product if isinstance(raw_product, dict) else {}
            raw_position_id = raw_product.get("id", position.get("product_id"))
            if raw_position_id is not None:
                try:
                    if int(raw_position_id) != product_id:
                        continue
                except (TypeError, ValueError):
                    continue
            raw_position_symbol = (raw_product.get("symbol") or position.get("symbol")
                                   or position.get("product_symbol"))
            if raw_position_symbol is not None:
                if not isinstance(raw_position_symbol, str) or raw_position_symbol.strip().upper() != resolved_symbol:
                    continue
            elif raw_position_id is None:
                # The endpoint is scoped, but a record with no instrument identity
                # cannot safely be assigned to this caller's product.
                continue
            matched.append(position)
        return matched

    def close_all_positions(self, symbol: str = "BTCUSDT") -> List[Dict]:
        """
        EMERGENCY: Close all open positions at market.
        Returns list of close order results.
        """
        positions = self.get_open_positions(symbol)
        results = []
        for pos in positions:
            # Venue responses may encode size as a string, including signed
            # decimal strings.  Do not infer a close from malformed data.
            try:
                raw_size = float(pos.get("size", 0))
                size = int(abs(raw_size))
            except (TypeError, ValueError):
                logger.warning("[EMERGENCY] Skipping position with invalid size")
                continue
            if size <= 0:
                continue
            # If long (size > 0) → sell to close. If short → buy to close.
            close_side = "sell" if raw_size > 0 else "buy"
            # Emergency close shares the same process-local ownership guard as
            # normal monitors. A timeout remains claimed until an operator or
            # reconciliation confirms that the venue position is flat.
            try:
                from jarvis_close_coordinator import claim_close, release_close, reconcile_close
                position_id = pos.get("id") or pos.get("position_id") or "position"
                if not claim_close(symbol, position_id, owner="DeltaEmergencyClose"):
                    results.append({"success": False, "error": "close already claimed"})
                    continue
                client_id = f"jarvis-emergency-close-{symbol}-{position_id}"[:64]
                res = self.place_order(symbol, close_side, size, order_type="market",
                                       reduce_only=True, client_order_id=client_id)
                if isinstance(res, dict) and res.get("success"):
                    release_close(symbol, position_id)
                else:
                    recon = reconcile_close(self, symbol, close_side, size)
                    if recon.get("confirmed"):
                        release_close(symbol, position_id)
                    elif isinstance(res, dict):
                        res = dict(res, error="close unconfirmed; operator reconciliation required",
                                   reconciliation=recon)
                results.append(res)
                logger.warning(f"[EMERGENCY] Closed {size}x {symbol}: {res}")
            except Exception as exc:
                results.append({"success": False, "error": f"close unconfirmed: {type(exc).__name__}"})
        return results

    def _resolve_product(self, symbol: str) -> Optional[Dict]:
        """Resolve a caller-facing symbol to the matching Delta product.

        Scanners and defaults typically emit ``XXXUSDT`` while Delta India
        lists perps as ``XXXUSD``. Try the exact symbol first, then the
        alternate quote (USDT<->USD) so callers get the product they mean
        instead of a failed lookup.  The product list is cached briefly to
        avoid re-downloading the full catalogue on every call.
        Returns the raw product dict, or None when nothing matches.
        """
        if not isinstance(symbol, str) or not symbol.strip():
            return None
        symbol = symbol.strip().upper()

        now = time.time()
        cache = getattr(self, "_products_cache", None)
        if not cache or now - cache.get("ts", 0) > 300:
            # CRITICAL FIX: Use authorized=True to force lookup on Testnet
            # (Private URL). Mainnet Product IDs are invalid on Testnet.
            res = self._request("GET", "/v2/products", authorized=True)
            if not res["success"]:
                return None
            products = res["data"].get("result", []) or []
            self._products_cache = {"ts": now, "products": products}
        products = self._products_cache["products"]

        candidates = [symbol]
        if symbol.endswith("USDT"):
            candidates.append(symbol[:-4] + "USD")
        elif symbol.endswith("USD"):
            candidates.append(symbol[:-3] + "USDT")

        for candidate in candidates:
            for p in products:
                if p.get("symbol") == candidate:
                    return p
        return None

    def get_product_id(self, symbol: str) -> Optional[str]:
        """Fetch Product ID for a given Symbol (required for Leverage)."""
        product = self._resolve_product(symbol)
        if product is None:
            return None
        try:
            return str(product["id"])
        except (KeyError, TypeError):
            return None

    def get_product_metadata(self, symbol: str) -> Optional[Dict]:
        """Return validated venue product metadata for risk/execution callers."""
        product = self._resolve_product(symbol)
        if not isinstance(product, dict):
            return None
        try:
            if int(product["id"]) <= 0 or not str(product.get("symbol", "")).strip():
                return None
        except (KeyError, TypeError, ValueError):
            return None
        return dict(product)

    def set_leverage(self, symbol: str, leverage: int = None) -> bool:
        """Apply a caller-computed leverage only when live execution is enabled.

        There is intentionally no venue default: callers must derive leverage
        from balance, margin and stop-loss risk and pass a positive integer.
        """
        if os.environ.get("DELTA_ORDER_EXECUTION_ENABLED", "false").lower() != "true":
            logger.warning("[RISK] Leverage change blocked: order execution is disabled")
            return False
        if not isinstance(symbol, str) or not symbol.strip():
            return False
        try:
            leverage = int(leverage)
        except (TypeError, ValueError):
            return False
        if leverage <= 0:
            return False
        product_id = self.get_product_id(symbol)
        if not product_id:
            logger.error(f"[RISK] Output: Product ID not found for {symbol}")
            return False

        params = {
            "product_id": int(product_id),
            "leverage": str(leverage)
        }
        res = self._request("POST", "/v2/orders/leverage", params, authorized=True)
        if res["success"]:
            logger.info(f"[RISK] Leverage set to {leverage}x for {symbol}")
            return True
        else:
            logger.error(f"[RISK] Failed to set leverage: {res.get('error')}")
            return False

    def place_order(self, symbol: str, side: str, size: int, order_type: str = "market", limit_price: float = 0,
                    reduce_only: bool = False, client_order_id: str = None) -> Dict:
        """
        Execute Trade (Live or Paper).

        Delta supports ``reduce_only`` and ``client_order_id`` on order payloads.
        Close paths must set both so a retry cannot intentionally reverse a
        position and the venue can deduplicate a stable close identity.
        """
        # An explicit process-level opt-in is required even on testnet.  This
        # prevents a caller or configuration mistake from turning analysis into
        # an order submission.
        if os.environ.get("DELTA_ORDER_EXECUTION_ENABLED", "false").lower() != "true":
            return {"success": False, "error": "Order execution is disabled"}
        if not isinstance(symbol, str) or not symbol.strip():
            return {"success": False, "error": "Invalid symbol"}
        if not isinstance(side, str) or side.lower() not in ("buy", "sell"):
            return {"success": False, "error": "Invalid order side"}
        try:
            size = int(size)
        except (TypeError, ValueError):
            return {"success": False, "error": "Invalid order size"}
        if size <= 0:
            return {"success": False, "error": "Invalid order size"}
        if not isinstance(order_type, str):
            return {"success": False, "error": "Invalid order type"}
        ot = order_type.lower().replace("_order", "").strip()
        if ot not in ("market", "limit"):
            return {"success": False, "error": "Invalid order type"}
        if ot == "limit":
            try:
                limit_price = float(limit_price)
            except (TypeError, ValueError):
                return {"success": False, "error": "Invalid limit price"}
            if limit_price <= 0:
                return {"success": False, "error": "Invalid limit price"}
        final_type = f"{ot}_order"  # Delta API expects: market_order or limit_order

        product_id = self.get_product_id(symbol.strip())
        if not product_id:
            logger.error(f"[EXECUTION] Product ID not found for {symbol}")
            return {"success": False, "error": "Product ID not found"}

        payload = {
            "product_id": int(product_id),
            "size": int(size),
            "side": side.lower(),
            "order_type": final_type,
        }

        if ot == "limit" and limit_price > 0:
            payload["limit_price"] = str(limit_price)
        if reduce_only:
            payload["reduce_only"] = True
        if client_order_id:
            client_order_id = str(client_order_id).strip()[:64]
            if client_order_id:
                payload["client_order_id"] = client_order_id

        logger.warning(f"[EXECUTION] Placing {side.upper()} {final_type} for {size} {symbol} (reduce_only={bool(reduce_only)})...")
        res = self._request("POST", "/v2/orders", payload, authorized=True)

        if res["success"]:
            order_data = res["data"].get("result", {})
            logger.info(f"[EXECUTION] Success! Order ID: {order_data.get('id')}")
            return {"success": True, "order_id": order_data.get("id"), "details": order_data}
        else:
            logger.error(f"[EXECUTION] Failed: {res.get('error')}")
            return {"success": False, "error": res.get("error")}

    def place_batch_orders(self, orders: List[Dict]) -> Dict:
        """
        Place Main Trade + Hedge Options simultaneously?
        Delta supports batch orders.
        """
        # Simplification: Loop for now. Delta has /v2/orders/batch if needed.
        results = []
        for order in orders:
            res = self.place_order(
                order["symbol"], order["side"], order["size"], 
                order.get("type", "market"), order.get("price", 0)
            )
            results.append(res)
        return {"results": results}
    
    def get_available_products(self) -> List[Dict[str, Any]]:
        """Return public product records for exact venue instrument discovery."""
        res = self._request("GET", "/v2/products", authorized=False)
        if not isinstance(res, dict) or not res.get("success"):
            return []
        products = res.get("data", {}).get("result", [])
        if not isinstance(products, list):
            return []
        return [dict(product) for product in products if isinstance(product, dict) and product.get("symbol")]

    def get_available_symbols(self) -> List[str]:
        """Get list of all available trading symbols."""
        return [str(product["symbol"]) for product in self.get_available_products()]
    
    def place_limit_order(self, symbol: str, side: str, quantity: int, price: float) -> Dict:
        """Place a limit order (wrapper for place_order)"""
        return self.place_order(symbol, side, quantity, order_type="limit_order", limit_price=price)
    
    def get_order(self, order_id: str) -> Dict:
        """Read one order for operator reconciliation; never retries or mutates."""
        if not order_id:
            return {"success": False, "error": "Invalid order id"}
        return self._request("GET", f"/v2/orders/{str(order_id)}", authorized=True)

    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an open order"""
        payload = {"id": order_id}
        res = self._request("DELETE", f"/v2/orders/{order_id}", payload, authorized=True)
        return res

if __name__ == "__main__":
    # Quick Test
    client = DeltaExchangeData()
    print("Testing Delta Exchange Unified Client...")
    print(f"Live BTC Price: ${client.get_live_price()}")
    chain = client.get_options_chain()
    print(f"Options Chain PCR: {chain.get('pcr', 'N/A')}")
    hist = client.get_historical_candles(limit=5)
    print(f"History (5 candles): {len(hist)} fetched")


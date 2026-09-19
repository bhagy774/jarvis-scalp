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
from urllib.parse import urlencode
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

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
        self.api_key = api_key or DEMO_API_KEY
        self.api_secret = api_secret or DEMO_API_SECRET
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "JarvisTradingSystem/2.0"
        })
        self._cache = {}

        # ── HYBRID: Use Binance for price+candles (more accurate, no API key needed) ──
        try:
            from binance_data import BinanceData
            self._binance = BinanceData()
            logger.info("[HYBRID] ✅ Binance data source loaded for price + candles")
        except ImportError:
            self._binance = None
            logger.warning("[HYBRID] ⚠️  binance_data.py not found, using Delta for everything")

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
            if authorized and (not self.api_key or not self.api_secret):
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

    def get_options_chain(self, underlying: str = "BTC") -> Dict:
        """
        Get options chain with Greeks.
        Returns data in a unified format compatible with Jarvis Logic.
        """
        # Fetch calls and puts
        res = self._request("GET", "/v2/tickers", {
            "contract_types": "call_options,put_options",
            "underlying_asset_symbols": underlying
        })
        
        if not res["success"]:
            return {}

        options = res["data"].get("result", [])
        
        # Analyze Chain
        chain_data = {
            "calls": [], # List of option objects
            "puts": [], # List of option objects
            "pcr": 0.0, # Put/Call Ratio
            "total_oi": 0,
            "max_pain": 0 # To be calculated
        }
        
        total_call_oi = 0
        total_put_oi = 0
        strikes = set()
        
        for opt in options:
            try:
                contract_type = opt.get("contract_type")
                strike = float(opt.get("strike_price", 0))
                oi = float(opt.get("oi", 0))
                
                # Parse Greeks (Delta endpoint sometimes nests them, sometimes flat)
                greeks = opt.get("greeks", {}) or {}
                
                # Parse Expiry from Symbol (e.g., BTC-280624-60000-C)
                parts = opt["symbol"].split("-")
                expiry = parts[1] if len(parts) >= 2 else "PERPETUAL"

                item = {
                    "symbol": opt["symbol"],
                    "expiry": expiry, # Storing expiry
                    "strike": strike,
                    "price": float(opt.get("mark_price", 0)),
                    "iv": float(opt.get("implied_volatility", 0)),
                    "oi": oi,
                    "volume": float(opt.get("volume", 0)),
                    "delta": float(greeks.get("delta", 0)) if greeks else 0,
                    "gamma": float(greeks.get("gamma", 0)) if greeks else 0,
                    "theta": float(greeks.get("theta", 0)) if greeks else 0,
                    "vega": float(greeks.get("vega", 0)) if greeks else 0,
                    "rho": float(greeks.get("rho", 0)) if greeks else 0
                }
                
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
            
        return chain_data

    def get_institutional_bias(self, underlying: str = "BTC") -> Dict:
        """
        [MULTI-EXPIRY] Big Player Analysis.
        Analyzes Near-term (Gamma) vs Far-term (Positioning).
        """
        chain = self.get_options_chain(underlying)
        all_opts = chain.get("calls", []) + chain.get("puts", [])
        
        if not all_opts:
            return {"bias": "NEUTRAL", "score": 0, "reasons": ["No Data"]}
            
        # 1. Group by Expiry
        expiries = {}
        for opt in all_opts:
            exp = opt.get("expiry", "UNKNOWN")
            if exp not in expiries:
                expiries[exp] = {"calls": 0, "puts": 0, "call_vol": 0, "put_vol": 0}
            
            if "call" in opt["symbol"].lower() or opt["symbol"].endswith("-C"):
                expiries[exp]["calls"] += opt["oi"]
                expiries[exp]["call_vol"] += opt["volume"]
            else:
                expiries[exp]["puts"] += opt["oi"]
                expiries[exp]["put_vol"] += opt["volume"]
                
        # 2. Analyze Each Expiry
        reasons = []
        total_score = 0
        sorted_exps = sorted(expiries.keys()) # sort by date string (approx)
        
        # Analyze Top 3 Expiries (Near, Mid, Far)
        for i, exp in enumerate(sorted_exps[:3]):
            data = expiries[exp]
            total_oi = data["calls"] + data["puts"]
            if total_oi < 100: continue # Skip ghosts
            
            pcr = data["puts"] / data["calls"] if data["calls"] > 0 else 2.0
            
            # Weight: Near term has less weight on "Trend" but more on "Volatility"
            # Far term has more weight on "Trend"
            term = "NEAR" if i == 0 else "FAR"
            
            if pcr > 1.3:
                bias = "BEARISH"
                score = -2
                reasons.append(f"[{exp}] High PCR ({pcr:.2f}) -> Hedging/Bearish")
            elif pcr < 0.65:
                bias = "BULLISH"
                score = 2
                reasons.append(f"[{exp}] Low PCR ({pcr:.2f}) -> Call Buying/Bullish")
            else:
                bias = "NEUTRAL"
                score = 0
                
            total_score += score
            
        # 3. Final Verdict
        final_bias = "NEUTRAL"
        if total_score >= 3: final_bias = "BULLISH"
        elif total_score <= -3: final_bias = "BEARISH"
            
        return {
            "bias": final_bias,
            "score": total_score,
            "reasons": reasons,
            "pcr": round(chain.get("pcr", 0), 3),  # FIX: expose pcr at top level
            "max_pain": self._calculate_max_pain(chain),  # FIX: expose max_pain at top level
            "raw_data": {
                "expiries": expiries,
                "total_oi": chain["total_oi"],
                "pcr": round(chain.get("pcr", 0), 3),  # FIX: also in raw_data for compatibility
            }
        }

    def _calculate_max_pain(self, chain: Dict) -> float:
        """
        Calculate Max Pain: the strike where combined option sellers lose the least.
        Simplified: find the strike with highest combined OI (Call + Put).
        """
        try:
            all_opts = chain.get("calls", []) + chain.get("puts", [])
            if not all_opts:
                return 0.0
            strike_oi = {}
            for opt in all_opts:
                strike = opt.get("strike", 0)
                oi = opt.get("oi", 0)
                if strike > 0:
                    strike_oi[strike] = strike_oi.get(strike, 0) + oi
            if not strike_oi:
                return 0.0
            max_pain_strike = max(strike_oi, key=strike_oi.get)
            return float(max_pain_strike)
        except Exception:
            return 0.0


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
        resolved_symbol = symbol
        if not symbol:
            res = self._request("GET", "/v2/positions", None, authorized=True)
        else:
            product_id = self.get_product_id(symbol)
            if product_id is None:
                logger.error("[DELTA API] Product ID not found for requested positions")
                return []
            resolved_symbol = product.get("symbol", symbol)
            try:
                pid = int(product_id)
            except (TypeError, ValueError):
                logger.error("[DELTA API] Invalid product ID for requested positions")
                return []
            # Build signed URL with product_id as query param (Delta requirement)
            endpoint_with_param = f"/v2/positions?product_id={pid}"
            res = self._request("GET", endpoint_with_param, None, authorized=True)
        if res["success"]:
            try:
                positions = res["data"].get("result", [])
                if resolved_symbol:
                    positions = [p for p in positions
                                 if p.get("product", {}).get("symbol") == resolved_symbol
                                 or p.get("symbol") == resolved_symbol]
                return positions
            except Exception:
                return []
        return []

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
    
    def get_available_symbols(self) -> List[str]:
        """Get list of all available trading symbols"""
        res = self._request("GET", "/v2/products", authorized=False)
        if res["success"]:
            products = res["data"].get("result", [])
            return [p["symbol"] for p in products if "symbol" in p]
        return []
    
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


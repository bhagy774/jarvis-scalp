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
DEMO_API_KEY = os.environ.get("DELTA_API_KEY", "Fw94x6DjeLXRKmUxsaxAoZ4IYgS9rF")
DEMO_API_SECRET = os.environ.get("DELTA_API_SECRET", "iBlF54psjAuWeT06Hc34DE8FrOeAc3ukxvjiRzYp7ybqwfLFKXYBlEDh4fsR")

if DEMO_API_KEY == "Fw94x6DjeLXRKmUxsaxAoZ4IYgS9rF" and not os.environ.get("DELTA_API_KEY"):
    logging.warning("⚠️  Using DEMO API keys. Set DELTA_API_KEY and DELTA_API_SECRET in .env for production.")

logger = logging.getLogger(__name__)

class DeltaExchangeData:
    """
    Unified Data Wrapper for Delta Exchange.
    Handles all data ingestion for Jarvis.
    """
    
    # FIX #20: HYBRID CONFIG (Documented)
    # ├── PUBLIC_URL  → MAINNET (api.delta.exchange) → Real market prices, order book, candles
    # └── PRIVATE_URL → TESTNET (cdn-ind.testnet.deltaex.org) → Paper trading, order placement
    # This means: You see REAL prices but trades go to TESTNET (no real money risk)
    PRIVATE_URL = "https://cdn-ind.testnet.deltaex.org" # India Testnet for Execution
    PUBLIC_URL = "https://api.delta.exchange" # Mainnet for Real Price Data
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key or DEMO_API_KEY
        self.api_secret = api_secret or DEMO_API_SECRET
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "JarvisTradingSystem/2.0"
        })
        self._cache = {}

    def _generate_signature(self, method: str, path: str, payload: str = "") -> Dict[str, str]:
        """Generate HMAC SHA256 Signature for authenticated endpoints"""
        timestamp = str(int(time.time()))
        msg = method + timestamp + path + payload
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            msg.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return {
            "api-key": self.api_key,
            "timestamp": timestamp,
            "signature": signature
        }

    def _request(self, method: str, endpoint: str, payload: Dict = None, authorized: bool = False) -> Dict:
        """
        Unified Request Handler.
        authorized=True -> Uses Testnet/Private URL
        authorized=False -> Uses Production/Public URL (Real Prices)
        """
        try:
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
                    if response.status_code == 200:
                        return {"success": True, "data": response.json()}
                    else:
                        logger.error(f"[DELTA API] Error {response.status_code}: {response.text}")
                        return {"success": False, "error": response.text}

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

            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                logger.error(f"[DELTA API] Error {response.status_code}: {response.text}")
                return {"success": False, "error": response.text}

        except Exception as e:
            logger.error(f"[DELTA API] Connection failed: {e}")
            return {"success": False, "error": str(e)}

    # ==========================================
    # 1. LIVE MARKET DATA (Replaces Binance)
    # ==========================================

    def get_balance(self) -> Dict:
        """Fetch wallet balance"""
        return self._request("GET", "/v2/wallet/balances", authorized=True)

    def get_live_price(self, symbol: str = "BTCUSDT") -> float:
        """Get current Last Traded Price (LTP) for a symbol."""
        # Try multiple symbol variants for reliability
        symbols_to_try = [symbol]
        if symbol == "BTCUSD" or symbol == "BTCUSDT":
            symbols_to_try = ["BTCUSDT", "BTCUSD"]

        for sym in symbols_to_try:
            try:
                res = self._request("GET", "/v2/tickers", {"symbol": sym})
                if res["success"]:
                    tickers = res["data"].get("result", [])
                    # FIX BUG2: Exact match first, then fallback to any BTC perp/spot
                    for t in tickers:
                        if t.get("symbol") == sym:
                            price = float(t.get("close", 0) or t.get("mark_price", 0) or t.get("spot_price", 0))
                            if price > 0:
                                return price
                    # If exact match not found, try any ticker that has a usable price
                    for t in tickers:
                        price = float(t.get("close", 0) or t.get("mark_price", 0) or t.get("spot_price", 0))
                        if price > 0:
                            return price
            except Exception as e:
                logger.warning(f"[DELTA PRICE] Failed for {sym}: {e}")
                continue

        logger.error("[DELTA PRICE] Could not fetch live price for any symbol variant")
        return 0.0

    def get_order_book(self, symbol: str = "BTCUSD") -> Dict:
        """Get Level 2 Order Book (Bid/Ask)"""
        res = self._request("GET", f"/v2/l2orderbook/{symbol}")
        if res["success"]:
            return res["data"].get("result", {})
        return {}

    # ==========================================
    # 2. HISTORICAL DATA (Replaces Binance)
    # ==========================================

    def get_historical_candles(self, symbol: str = "BTCUSD", resolution: str = "5m", limit: int = 100) -> List[Dict]:
        """Fetch historical OHLCV data."""
        end_time = int(time.time())
        # Calculate start time based on resolution (approximate)
        multipliers = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
        seconds = multipliers.get(resolution, 300)
        start_time = end_time - (limit * seconds)
        
        # Use BTCUSDT futures market (same as what traders see on Delta chart)
        query_sym = symbol
        if query_sym in ("BTCUSD", "BTCUSDT", "BTC_USDT"):
            query_sym = "BTCUSDT"
            
        params = {
            "symbol": query_sym,
            "resolution": resolution,
            "start": start_time,
            "end": end_time
        }
        res = self._request("GET", "/v2/history/candles", params)
        if res["success"]:
            results = res["data"].get("result", [])
            for r in results:
                if r.get('volume') is None:
                    r['volume'] = 0.0
            return results
        return []

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
            "raw_data": {"expiries": expiries, "total_oi": chain["total_oi"]}
        }

    # ==========================================
    # 4. ORDER EXECUTION & RISK MANAGEMENT (PHASE 3)
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

    def get_product_id(self, symbol: str) -> Optional[str]:
        """Fetch Product ID for a given Symbol (required for Leverage)."""
        # CRITICAL FIX: Use authorized=True to force lookup on Testnet (Private URL)
        # Mainnet Product IDs are invalid on Testnet.
        res = self._request("GET", "/v2/products", authorized=True)
        if res["success"]:
            for p in res["data"].get("result", []):
                if p["symbol"] == symbol:
                    return str(p["id"])
        return None

    def set_leverage(self, symbol: str, leverage: int = 200) -> bool:
        """
        Force Leverage to 200x (User Request).
        Warning: High Risk.
        """
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

    def place_order(self, symbol: str, side: str, size: int, order_type: str = "market", limit_price: float = 0) -> Dict:
        """
        Execute Trade (Live or Paper).
        side: "buy" or "sell"
        size: number of contracts
        order_type: "market", "limit", "market_order", or "limit_order" — all handled
        """
        # FIX BUG3: Normalize order_type robustly — accept any variant
        ot = order_type.lower().replace("_order", "").strip()
        if ot not in ("market", "limit"):
            logger.warning(f"[EXECUTION] Unknown order_type '{order_type}', defaulting to market")
            ot = "market"
        final_type = f"{ot}_order"  # Delta API expects: market_order or limit_order

        product_id = self.get_product_id(symbol)
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

        logger.warning(f"[EXECUTION] Placing {side.upper()} {final_type} for {size} {symbol}...")
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


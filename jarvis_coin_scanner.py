#!/usr/bin/env python3
"""
JARVIS Coin Scanner - Multi-Coin Auto-Selector
===============================================
Every 5 minutes, scans perpetual futures on Binance/Delta India.
Scores each coin: Volume(25pts) + Momentum(25pts) + RSI(20pts)
                + Volatility(20pts) + FundingRate(10pts) = 100pts max.
Picks BEST coin for Oracle/Advisor/Trader.
Coin switch ONLY when NO position is open. Fallback = BTC.
"""
import os
import time
import logging
import threading
import requests
from typing import Dict, List, Optional
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("JarvisCoinScanner")

R   = "\033[91m"
G   = "\033[92m"
Y   = "\033[93m"
C   = "\033[96m"
W   = "\033[97m"
DG  = "\033[90m"
BD  = "\033[1m"
RST = "\033[0m"

SCAN_INTERVAL_SEC = int(os.environ.get("SCANNER_INTERVAL_SEC", "300"))
MIN_VOLUME_USDT   = float(os.environ.get("SCANNER_MIN_VOL", "5000000"))
BINANCE_BASE      = "https://api.binance.com"

SCAN_COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP",
    "DOGE", "ADA", "AVAX", "LINK", "MATIC",
    "DOT", "LTC", "NEAR", "OP", "ARB"
]
BINANCE_SYMBOL_MAP = {c: c + "USDT" for c in SCAN_COINS}
DELTA_SYMBOL_MAP   = {c: c + "USDT" for c in SCAN_COINS}


class JarvisCoinScanner:
    """
    Scans multiple coins, scores them, picks the best one.
    Thread-safe. Runs in background, exposes get_best_coin().
    """

    def __init__(self, bus=None, position_check_fn=None):
        self.bus = bus
        self._position_check_fn = position_check_fn
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._best_coin    = "BTC"
        self._best_symbol  = "BTCUSDT"
        self._delta_symbol = "BTCUSDT"
        self._all_scores: Dict[str, Dict] = {}
        self._last_scan_ts: Optional[datetime] = None
        self._scan_count = 0

    # ----------------------------------------------------------
    # PUBLIC API
    # ----------------------------------------------------------

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._scan_loop, daemon=True, name="JarvisCoinScanner"
        )
        self._thread.start()
        logger.info("[CoinScanner] Started. Interval=%ss", SCAN_INTERVAL_SEC)
        print(f"\n{BD}{C}  JARVIS COIN SCANNER{RST}")
        print(f"{DG}  |- Coins    : {W}{', '.join(SCAN_COINS[:8])}...{RST}")
        print(f"{DG}  |- Interval : {W}{SCAN_INTERVAL_SEC // 60} min{RST}")
        print(f"{DG}  '- Status   : {G}ACTIVE{RST}\n")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def get_best_coin(self) -> str:
        """Returns best coin base symbol e.g. 'ETH'"""
        with self._lock:
            return self._best_coin

    def get_best_symbol(self) -> str:
        """Returns best Binance symbol e.g. 'ETHUSDT'"""
        with self._lock:
            return self._best_symbol

    def get_delta_symbol(self) -> str:
        """Returns Delta Exchange perpetual symbol e.g. 'ETHUSDT'"""
        with self._lock:
            return self._delta_symbol

    def get_all_scores(self) -> Dict[str, Dict]:
        with self._lock:
            return dict(self._all_scores)

    def get_scanner_status(self) -> Dict:
        with self._lock:
            return {
                "best_coin":    self._best_coin,
                "best_symbol":  self._best_symbol,
                "delta_symbol": self._delta_symbol,
                "last_scan":    self._last_scan_ts.isoformat() if self._last_scan_ts else None,
                "scan_count":   self._scan_count,
            }

    def run_now(self) -> str:
        """Manually trigger immediate scan, return best coin."""
        return self._run_scan_cycle()

    # ----------------------------------------------------------
    # BACKGROUND LOOP
    # ----------------------------------------------------------

    def _scan_loop(self):
        time.sleep(5)
        while self._running:
            try:
                self._run_scan_cycle()
            except Exception as e:
                logger.error("[CoinScanner] Scan error: %s", e)
            elapsed = 0
            while self._running and elapsed < SCAN_INTERVAL_SEC:
                time.sleep(5)
                elapsed += 5

    def _run_scan_cycle(self) -> str:
        logger.info("[CoinScanner] Starting scan cycle...")
        scores = {}
        stats_map = self._fetch_binance_stats_bulk()

        for coin in SCAN_COINS:
            try:
                symbol = BINANCE_SYMBOL_MAP[coin]
                stats  = stats_map.get(symbol, {})
                scores[coin] = self._score_coin(coin, symbol, stats)
            except Exception as e:
                logger.debug("[CoinScanner] Scoring %s failed: %s", coin, e)
                scores[coin] = {"total": 0, "error": str(e)}

        valid_coins = {
            c: s for c, s in scores.items()
            if s.get("volume_24h_usdt", 0) >= MIN_VOLUME_USDT
        }

        if not valid_coins:
            logger.warning("[CoinScanner] No coins passed volume filter - using BTC")
            best_coin = "BTC"
        else:
            best_coin = max(valid_coins, key=lambda c: valid_coins[c].get("total", 0))

        can_switch = True
        if self._position_check_fn:
            try:
                can_switch = not self._position_check_fn()
            except Exception:
                can_switch = True

        with self._lock:
            self._all_scores  = scores
            self._last_scan_ts = datetime.now()
            self._scan_count  += 1
            old_coin = self._best_coin
            if can_switch:
                self._best_coin    = best_coin
                self._best_symbol  = BINANCE_SYMBOL_MAP.get(best_coin, "BTCUSDT")
                self._delta_symbol = DELTA_SYMBOL_MAP.get(best_coin, "BTCUSDT")
            else:
                best_coin = self._best_coin

        sorted_coins = sorted(
            valid_coins.items(), key=lambda x: x[1].get("total", 0), reverse=True
        )
        top3_str  = " | ".join(
            [f"{c}={s.get('total', 0):.0f}" for c, s in sorted_coins[:3]]
        )
        switched = "SWITCHED" if best_coin != old_coin else "SAME"
        print(f"\n{BD}{C}  COIN SCANNER{RST} {DG}[{datetime.now().strftime('%H:%M:%S')}]{RST}")
        print(f"  Best: {BD}{G}{best_coin}{RST}  [{switched}]")
        print(f"  Top3: {W}{top3_str}{RST}")
        if not can_switch:
            print(f"  {Y}(Position open - kept {self._best_coin}){RST}")

        if self.bus:
            try:
                self.bus.publish("BEST_COIN", "JarvisCoinScanner", {
                    "coin":         best_coin,
                    "symbol":       self._best_symbol,
                    "delta_symbol": self._delta_symbol,
                    "timestamp":    datetime.now().isoformat(),
                })
            except Exception:
                pass
        return best_coin

    # ----------------------------------------------------------
    # DATA FETCHING
    # ----------------------------------------------------------

    def _fetch_binance_stats_bulk(self) -> Dict[str, Dict]:
        try:
            resp = requests.get(
                f"{BINANCE_BASE}/api/v3/ticker/24hr", timeout=10
            )
            if resp.status_code == 200:
                return {
                    item["symbol"]: item for item in resp.json()
                    if item["symbol"] in BINANCE_SYMBOL_MAP.values()
                }
        except Exception as e:
            logger.warning("[CoinScanner] Binance bulk stats failed: %s", e)
        return {}

    def _fetch_binance_candles(self, symbol: str, interval: str = "5m",
                                limit: int = 20) -> List[float]:
        try:
            resp = requests.get(
                f"{BINANCE_BASE}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=8,
            )
            if resp.status_code == 200:
                return [float(c[4]) for c in resp.json()]
        except Exception:
            pass
        return []

    def _fetch_funding_rate(self, symbol: str) -> float:
        try:
            resp = requests.get(
                "https://fapi.binance.com/fapi/v1/premiumIndex",
                params={"symbol": symbol},
                timeout=5,
            )
            if resp.status_code == 200:
                return float(resp.json().get("lastFundingRate", 0))
        except Exception:
            pass
        return 0.0

    # ----------------------------------------------------------
    # SCORING ENGINE
    # ----------------------------------------------------------

    def _score_coin(self, coin: str, symbol: str, stats: Dict) -> Dict:
        score = {
            "coin": coin, "symbol": symbol,
            "volume_score": 0, "momentum_score": 0, "rsi_score": 0,
            "volatility_score": 0, "funding_score": 0, "total": 0,
            "volume_24h_usdt": 0.0, "price_change_pct": 0.0, "current_price": 0.0,
        }
        if not stats:
            return score
        try:
            vol_usdt         = float(stats.get("quoteVolume", 0))
            price_change_pct = float(stats.get("priceChangePercent", 0))
            high_24h         = float(stats.get("highPrice", 1))
            low_24h          = float(stats.get("lowPrice", 1))
            last_price       = float(stats.get("lastPrice", 0))
            score["volume_24h_usdt"]  = vol_usdt
            score["price_change_pct"] = price_change_pct
            score["current_price"]    = last_price
        except Exception:
            return score

        # 1. Volume Score (0-25)
        vol_m = vol_usdt / 1_000_000
        if vol_m >= 500:    vs = 25
        elif vol_m >= 200:  vs = 22
        elif vol_m >= 100:  vs = 20
        elif vol_m >= 50:   vs = 17
        elif vol_m >= 20:   vs = 13
        elif vol_m >= 10:   vs = 9
        elif vol_m >= 5:    vs = 5
        else:               vs = 0
        score["volume_score"] = vs

        # 2. Momentum Score (0-25)
        ac = abs(price_change_pct)
        if ac >= 8:      ms = 25
        elif ac >= 5:    ms = 20
        elif ac >= 3:    ms = 16
        elif ac >= 1.5:  ms = 12
        elif ac >= 0.5:  ms = 8
        else:            ms = 3
        score["momentum_score"] = ms

        # 3. RSI Score (0-20)
        closes = self._fetch_binance_candles(symbol, "5m", 15)
        rsi = self._calc_rsi(closes)
        score["rsi"] = rsi
        if 40 <= rsi <= 60:    rs = 20
        elif 35 <= rsi <= 65:  rs = 15
        elif 30 <= rsi <= 70:  rs = 10
        elif 25 <= rsi <= 75:  rs = 5
        else:                  rs = 0
        score["rsi_score"] = rs

        # 4. Volatility Score (0-20)
        range_pct = (high_24h - low_24h) / last_price * 100 if last_price > 0 else 0
        score["range_pct"] = round(range_pct, 2)
        if 1.0 <= range_pct <= 5.0:    vs2 = 20
        elif 0.5 <= range_pct <= 8.0:  vs2 = 14
        elif range_pct > 8.0:          vs2 = 6
        else:                          vs2 = 4
        score["volatility_score"] = vs2

        # 5. Funding Score (0-10)
        funding = self._fetch_funding_rate(symbol)
        score["funding_rate"] = funding
        af = abs(funding) * 100
        if af < 0.02:    fs = 10
        elif af < 0.05:  fs = 7
        elif af < 0.10:  fs = 4
        else:            fs = 1
        score["funding_score"] = fs

        score["total"] = round(vs + ms + rs + vs2 + fs, 1)
        return score

    def _calc_rsi(self, closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        try:
            deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
            gains  = [d for d in deltas if d > 0]
            losses = [-d for d in deltas if d < 0]
            ag = sum(gains[-period:]) / period if gains else 0
            al = sum(losses[-period:]) / period if losses else 0
            if al == 0:
                return 100.0
            return round(100 - (100 / (1 + ag / al)), 1)
        except Exception:
            return 50.0


# ── Singleton ──────────────────────────────────────────────────
_scanner_instance: Optional[JarvisCoinScanner] = None


def get_coin_scanner(bus=None, position_check_fn=None) -> JarvisCoinScanner:
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = JarvisCoinScanner(bus=bus, position_check_fn=position_check_fn)
    return _scanner_instance


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    print("Testing Jarvis Coin Scanner...")
    scanner = JarvisCoinScanner()
    best = scanner.run_now()
    print(f"\nBest Coin: {best}")
    for coin, data in sorted(
        scanner.get_all_scores().items(),
        key=lambda x: x[1].get("total", 0), reverse=True
    ):
        if data.get("volume_24h_usdt", 0) > 0:
            print(f"  {coin:6} | Score={data.get('total', 0):5.1f} | "
                  f"Vol=${data.get('volume_24h_usdt', 0) / 1e6:.0f}M | "
                  f"Change={data.get('price_change_pct', 0):+.1f}%")

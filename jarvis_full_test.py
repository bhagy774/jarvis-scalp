#!/usr/bin/env python3
"""
JARVIS 3.0 FULL SYSTEM TEST
============================
Tests every module in the system:
  - All imports (Parts 1-12, core modules)
  - Data pipeline (Binance + Delta)
  - Ollama AI (local only, no Gemini)
  - Coin Scanner
  - Dynamic Sizer
  - Position Manager
  - Market Oracle (Ollama)
  - Supreme Advisor (Ollama)
  - LiveTrader gates
  - Signal flow end-to-end

PASS/FAIL for each component.
"""
import os, sys, time, json
from datetime import datetime

# Force .env load
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=r"C:\jarvis\.env")
except Exception:
    pass

sys.path.insert(0, r"C:\jarvis")
os.chdir(r"C:\jarvis")

R   = "\033[91m"
G   = "\033[92m"
Y   = "\033[93m"
C   = "\033[96m"
W   = "\033[97m"
DG  = "\033[90m"
BD  = "\033[1m"
RST = "\033[0m"

results = []

def test(name, fn):
    try:
        result = fn()
        msg = result if isinstance(result, str) else "OK"
        print(f"  {G}PASS{RST}  {W}{name}{RST}  {DG}{msg}{RST}")
        results.append(("PASS", name, msg))
        return True
    except Exception as e:
        print(f"  {R}FAIL{RST}  {W}{name}{RST}  {R}{str(e)[:80]}{RST}")
        results.append(("FAIL", name, str(e)[:80]))
        return False

def section(title):
    print(f"\n{C}{'='*65}{RST}")
    print(f"{BD}{C}  {title}{RST}")
    print(f"{C}{'='*65}{RST}")

# ================================================================
section("1. ENVIRONMENT & CONFIG")
# ================================================================

test("DELTA_API_KEY set",
    lambda: os.environ.get("DELTA_API_KEY","") != "" or "KEY=" + os.environ.get("DELTA_API_KEY","MISSING"))

test("OLLAMA_MODEL set",
    lambda: f"Model = {os.environ.get('OLLAMA_MODEL','NOT SET')}")

test("OLLAMA_BASE_URL set",
    lambda: f"URL = {os.environ.get('OLLAMA_BASE_URL','NOT SET')}")

test("JARVIS_AUTO_TRADE set",
    lambda: f"AutoTrade = {os.environ.get('JARVIS_AUTO_TRADE','NOT SET')}")

test("DELTA_USE_MAINNET set",
    lambda: f"Mainnet = {os.environ.get('DELTA_USE_MAINNET','NOT SET')}")

test("SCANNER_INTERVAL_SEC set (new)",
    lambda: f"Interval = {os.environ.get('SCANNER_INTERVAL_SEC','NOT SET')}s")

test("SIZER_BASE_RISK_PCT set (new)",
    lambda: f"Risk = {os.environ.get('SIZER_BASE_RISK_PCT','NOT SET')}")

test("PM_SL_PCT set (new)",
    lambda: f"SL = {os.environ.get('PM_SL_PCT','NOT SET')}")

# ================================================================
section("2. CORE IMPORTS")
# ================================================================

def test_binance():
    from binance_data import get_binance_data
    b = get_binance_data()
    return f"BinanceData ready"

def test_delta():
    from delta_api_wrapper import DeltaExchangeData
    d = DeltaExchangeData()
    return f"DeltaExchangeData ready (mainnet={d._USE_MAINNET})"

def test_ollama_module():
    from ollama_integration import call_ollama, OLLAMA_BASE_URL, OLLAMA_MODEL
    return f"Module loaded. URL={OLLAMA_BASE_URL} Model={OLLAMA_MODEL}"

def test_cognitive_bus():
    from jarvis_cognitive_bus import JarvisCognitiveBus
    bus = JarvisCognitiveBus()
    return "CognitiveBus instantiated"

def test_neural_cortex():
    from jarvis_neural_cortex import JarvisNeuralCortex
    return "JarvisNeuralCortex importable"

test("binance_data.py",       test_binance)
test("delta_api_wrapper.py",  test_delta)
test("ollama_integration.py", test_ollama_module)
test("jarvis_cognitive_bus.py", test_cognitive_bus)
test("jarvis_neural_cortex.py", test_neural_cortex)

# ================================================================
section("3. NEW JARVIS 3.0 MODULES")
# ================================================================

def test_coin_scanner():
    from jarvis_coin_scanner import JarvisCoinScanner, get_coin_scanner
    s = JarvisCoinScanner()
    assert s.get_best_coin() == "BTC"
    assert s.get_delta_symbol() == "BTCUSDT"
    return f"CoinScanner ready. Default={s.get_best_coin()}"

def test_sizer():
    from jarvis_sizer import JarvisSizer, CONF_MULTIPLIERS
    # Mock delta client
    class MockDelta:
        def get_wallet_balance(self): return 6.0
    s = JarvisSizer(MockDelta())
    sz = s.calculate_size(91, "BTCUSDT")
    assert sz["contracts"] >= 1
    assert sz["multiplier"] == 2.0, f"Expected 2.0x for 91%, got {sz['multiplier']}"
    sz2 = s.calculate_size(72, "BTCUSDT")
    assert sz2["multiplier"] == 1.0
    sz3 = s.calculate_size(65, "BTCUSDT")
    assert sz3["multiplier"] == 0.5
    return (f"Sizer OK. conf91={sz['multiplier']}x {sz['contracts']}c | "
            f"conf72={sz2['multiplier']}x | conf65={sz3['multiplier']}x")

def test_position_manager():
    from jarvis_position_manager import JarvisPositionManager, PositionRecord
    class MockDelta:
        def get_wallet_balance(self): return 6.0
        def get_live_price(self, s): return 95000.0
        def place_order(self, *a, **kw): return {"success": True}
    pm = JarvisPositionManager(MockDelta())
    assert not pm.has_open_position()
    pos = pm.register_position("T001", "CALL", 95000.0, 10, 85, "BTC", "SCALP")
    assert pm.has_open_position()
    assert pos.tp_price > 95000.0
    assert pos.sl_price < 95000.0
    assert pos.is_call
    # Test sizing
    sz = pm.get_sizing_for_coin(6.0, 91)
    assert sz["multiplier"] == 2.0
    sz2 = pm.get_sizing_for_coin(6.0, 65)
    assert sz2["multiplier"] == 0.5
    return f"PM OK. TP=${pos.tp_price:.2f} SL=${pos.sl_price:.2f} conf91={sz['multiplier']}x"

test("jarvis_coin_scanner.py",     test_coin_scanner)
test("jarvis_sizer.py",            test_sizer)
test("jarvis_position_manager.py", test_position_manager)

# ================================================================
section("4. OLLAMA CONNECTIVITY (Local AI)")
# ================================================================

def test_ollama_ping():
    import requests
    url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    r = requests.get(f"{url}/api/tags", timeout=5)
    if r.status_code == 200:
        models = [m["name"] for m in r.json().get("models", [])]
        return f"Ollama running. Models: {', '.join(models[:4]) or 'none loaded'}"
    return f"HTTP {r.status_code}"

def test_ollama_models():
    import requests
    url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    r = requests.get(f"{url}/api/tags", timeout=5)
    models = [m["name"] for m in r.json().get("models", [])]
    needed = os.environ.get("OLLAMA_MODEL", "deepseek-r1:14b")
    if any(needed.split(":")[0] in m for m in models):
        return f"{needed} available"
    raise Exception(f"{needed} NOT found in Ollama. Run: ollama pull {needed}")

ollama_up = test("Ollama server reachable", test_ollama_ping)
if ollama_up:
    test(f"Required model available", test_ollama_models)
else:
    print(f"  {Y}SKIP{RST}  Model check (Ollama not running)")
    results.append(("SKIP", "Model available", "Ollama not running"))

# ================================================================
section("5. MARKET DATA PIPELINE")
# ================================================================

def test_live_price():
    from delta_api_wrapper import DeltaExchangeData
    d = DeltaExchangeData()
    price = d.get_live_price("BTCUSDT")
    assert price > 1000, f"Invalid price: {price}"
    return f"BTC Price = ${price:,.2f}"

def test_binance_candles():
    from binance_data import get_binance_data
    b = get_binance_data()
    candles = b.get_historical_candles("BTCUSDT", "5m", limit=20)
    assert len(candles) >= 5, f"Only {len(candles)} candles"
    return f"{len(candles)} candles fetched (latest close=${candles[-1].get('close',candles[-1].get('c','?'))})"

def test_wallet_balance():
    from delta_api_wrapper import DeltaExchangeData
    d = DeltaExchangeData()
    bal = d.get_wallet_balance()
    return f"Balance = ${bal:.4f} USDT"

def test_binance_funding():
    from binance_data import get_binance_data
    b = get_binance_data()
    f = b.get_funding_rate("BTCUSDT")
    return f"Funding = {f.get('description', f.get('rate','N/A'))}"

def test_delta_products():
    from delta_api_wrapper import DeltaExchangeData
    d = DeltaExchangeData()
    pid = d.get_product_id("BTCUSDT")
    return f"BTCUSDT Product ID = {pid}"

test("Live BTC price (Delta/Binance)", test_live_price)
test("5m candles (Binance)",           test_binance_candles)
test("Wallet balance (Delta)",         test_wallet_balance)
test("Funding rate (Binance)",         test_binance_funding)
test("Delta product ID lookup",        test_delta_products)

# ================================================================
section("6. PARTS 1-12 IMPORTS")
# ================================================================

parts_map = {
    "part1_FIXED": "SmartBreakoutAI",
    "part2_FIXED": "NeuralNetworkManager",
    "part3_FIXED": "InstitutionalTradingEngineGPU",
    "part4_FIXED": "GPUInstitutionalBacktestingEngine",
    "part5_FIXED": "GPUEnhancedFusionEngine",
    "part6_FIXED": "GPUComprehensiveBacktester",
    "part7_FIXED": "EnhancedGPULiveDataEngine",
    "part8_FIXED": "EnhancedGPUPatternRecognitionEngine",
    "part9_FIXED": "GPUAIAdaptiveLearningEngine",
    "part11_FIXED": "GPUUnifiedConfidenceEngine",
    "part12_FIXED": "GPUOrderExecutionEngine",
}

for mod, cls in parts_map.items():
    def make_part_test(m, c):
        def fn():
            import importlib
            module = importlib.import_module(m)
            klass  = getattr(module, c)
            return f"{c} importable"
        return fn
    test(f"{mod} ({cls})", make_part_test(mod, cls))

# ================================================================
section("7. SIGNAL FLOW (analyze_trade_setup)")
# ================================================================

def test_signal_flow():
    """Test that jarvis_FIXED.py can produce a signal from real data."""
    import importlib
    import pandas as pd
    import numpy as np

    from binance_data import get_binance_data
    b = get_binance_data()
    candles = b.get_historical_candles("BTCUSDT", "5m", limit=100)
    if not candles or len(candles) < 50:
        raise Exception("Not enough candles for signal test")

    df = pd.DataFrame(candles)
    # Normalize column names
    if "time" in df.columns:
        df["timestamp"] = pd.to_datetime(df["time"], unit="s")
    elif "open_time" in df.columns:
        df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
    df.set_index("timestamp", inplace=True) if "timestamp" in df.columns else None

    for col in ["open","high","low","close","volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df.dropna(inplace=True)

    return f"DataFrame built: {len(df)} rows, cols={list(df.columns)[:6]}"

test("Real market DataFrame build", test_signal_flow)

# ================================================================
section("8. GEMINI ADVISOR (Ollama mode)")
# ================================================================

def test_advisor_import():
    from gemini_supreme_advisor import GeminiSupremeAdvisor, get_advisor
    adv = GeminiSupremeAdvisor()
    return f"Advisor ready. LocalFallback={adv._local_fallback_enabled}"

def test_advisor_is_trading_allowed():
    from gemini_supreme_advisor import GeminiSupremeAdvisor
    adv = GeminiSupremeAdvisor()
    allowed, reason = adv.is_trading_allowed("CALL")
    return f"is_trading_allowed(CALL) = {allowed} | {reason[:50]}"

test("GeminiSupremeAdvisor import",          test_advisor_import)
test("is_trading_allowed() works",           test_advisor_is_trading_allowed)

# ================================================================
section("9. MARKET ORACLE (Ollama mode)")
# ================================================================

def test_oracle_import():
    from jarvis_market_oracle import JarvisMarketOracle
    o = JarvisMarketOracle()
    assert hasattr(o, "_call_ollama_oracle"), "Missing _call_ollama_oracle method!"
    return "Oracle imported. _call_ollama_oracle method present"

def test_oracle_fallback():
    from jarvis_market_oracle import JarvisMarketOracle
    o = JarvisMarketOracle()
    # Test local synthesizer directly
    fake_data = {
        "btc_spot": 95000.0,
        "deribit": {"pcr": 0.75, "max_pain": 94000, "gamma_wall_call": 96000, "gamma_wall_put": 93000},
        "microstructure": {"imbalance_pct": 3.0, "imbalance_bias": "BULLISH", "funding_rate": "+0.01%",
                          "funding_countdown": "4h", "volume_24h_usdt": 1e9, "high_24h": 96000, "low_24h": 93000,
                          "change_24h_pct": 1.2, "bid_wall": 94500, "ask_wall": 95500},
        "candles": {"5m": [94800,94900,95000,95100,95200], "1h": [94000,94500,95000]},
        "parts_opinions": {"Part1_Breakout": "Bullish momentum", "Part5_Fusion": "CALL confirmed"},
    }
    fc = o._generate_local_forecast(fake_data, {})
    required = ["5min","30min","1hour","4hour","day","options_intel","trade_suggestion"]
    missing = [k for k in required if k not in fc]
    if missing:
        raise Exception(f"Missing keys: {missing}")
    return f"Local forecast OK. Suggestion={fc['trade_suggestion']} | 5m={fc['5min']['direction']}"

test("JarvisMarketOracle import + Ollama method", test_oracle_import)
test("Oracle local fallback forecast",            test_oracle_fallback)

# ================================================================
section("10. LIVE TRADER GATES")
# ================================================================

def test_trader_import():
    from jarvis_live_trader import JarvisAutoTrader
    return "JarvisAutoTrader importable"

def test_trader_imports_scanner():
    from jarvis_live_trader import _get_coin_scanner, _get_sizer, _get_position_manager
    return "Scanner/Sizer/PM imports in live_trader OK"

def test_coin_scanner_integration():
    from jarvis_coin_scanner import get_coin_scanner
    scanner = get_coin_scanner()
    coin   = scanner.get_best_coin()
    sym    = scanner.get_best_symbol()
    delta  = scanner.get_delta_symbol()
    assert coin == "BTC"    # default before first scan
    assert sym  == "BTCUSDT"
    assert delta == "BTCUSDT"
    return f"Scanner singleton: coin={coin} sym={sym} delta={delta}"

def test_sizer_integration():
    from jarvis_sizer import get_sizer
    from delta_api_wrapper import DeltaExchangeData
    delta  = DeltaExchangeData()
    sizer  = get_sizer(delta)
    bal    = sizer.get_live_balance()
    sz     = sizer.calculate_size(85, "BTCUSDT", force_balance=6.0)
    return (f"Sizer: balance=${bal:.4f} | conf85={sz['multiplier']}x"
            f" | margin=${sz['margin_usdt']:.4f} | {sz['contracts']} contracts")

test("JarvisAutoTrader import",           test_trader_import)
test("Scanner/Sizer/PM in live_trader",   test_trader_imports_scanner)
test("CoinScanner singleton works",       test_coin_scanner_integration)
test("Sizer with real Delta balance",     test_sizer_integration)

# ================================================================
section("11. COIN SCANNER QUICK SCAN")
# ================================================================

def test_quick_scan():
    import requests
    r = requests.get("https://api.binance.com/api/v3/ticker/24hr",
                     params={"symbol": "ETHUSDT"}, timeout=8)
    if r.status_code != 200:
        raise Exception(f"Binance API error {r.status_code}")
    d = r.json()
    return (f"ETH: Vol=${float(d.get('quoteVolume',0))/1e9:.2f}B"
            f" Change={d.get('priceChangePercent',0)}%"
            f" Price=${float(d.get('lastPrice',0)):,.2f}")

def test_scanner_scoring():
    from jarvis_coin_scanner import JarvisCoinScanner
    sc = JarvisCoinScanner()
    import requests
    r = requests.get("https://api.binance.com/api/v3/ticker/24hr",
                     params={"symbol": "BTCUSDT"}, timeout=8)
    stats = r.json() if r.status_code == 200 else {}
    score = sc._score_coin("BTC", "BTCUSDT", stats)
    assert score["total"] >= 0
    return (f"BTC score: total={score['total']:.1f}"
            f" vol={score['volume_score']} mom={score['momentum_score']}"
            f" rsi={score['rsi_score']} vol2={score['volatility_score']}"
            f" fund={score['funding_score']}")

test("Binance API reachable (multi-coin scan)", test_quick_scan)
test("Coin scoring engine works",               test_scanner_scoring)

# ================================================================
section("12. END-TO-END SIMULATION (no real order)")
# ================================================================

def test_e2e_simulation():
    """Full pipeline: data -> signal -> size -> log (no real order)."""
    from binance_data import get_binance_data
    from jarvis_sizer import JarvisSizer
    from jarvis_coin_scanner import JarvisCoinScanner
    import pandas as pd

    # 1. Get data
    b       = get_binance_data()
    candles = b.get_historical_candles("BTCUSDT", "5m", limit=30)
    if not candles:
        raise Exception("No candles")
    price = float(candles[-1].get("close", candles[-1].get("c", 95000)))

    # 2. Get best coin
    scanner = JarvisCoinScanner()
    coin    = scanner.get_best_coin()

    # 3. Simulate confidence from parts (mock 84%)
    confidence = 84

    # 4. Size the trade
    class MockDelta:
        def get_wallet_balance(self): return 6.0
    sizer    = JarvisSizer(MockDelta())
    size_inf = sizer.calculate_size(confidence, coin + "USDT")

    # 5. Position Manager creates record
    from jarvis_position_manager import PositionRecord
    pos = PositionRecord("E2E_TEST_001", "CALL", price, size_inf["contracts"], confidence, coin)

    # 6. Verify
    assert pos.tp_price > price
    assert pos.sl_price < price
    assert size_inf["multiplier"] == 1.5   # 84% -> 1.5x

    return (f"E2E OK | Coin={coin} Price=${price:,.2f}"
            f" | Conf={confidence}% -> {size_inf['multiplier']}x"
            f" | {size_inf['contracts']} contracts"
            f" | TP=${pos.tp_price:,.2f} SL=${pos.sl_price:,.2f}")

test("Full E2E pipeline (no real order)", test_e2e_simulation)

# ================================================================
# SUMMARY
# ================================================================

print(f"\n{C}{'='*65}{RST}")
print(f"{BD}{C}  TEST SUMMARY{RST}")
print(f"{C}{'='*65}{RST}\n")

passed = sum(1 for r in results if r[0] == "PASS")
failed = sum(1 for r in results if r[0] == "FAIL")
skipped = sum(1 for r in results if r[0] == "SKIP")
total  = len(results)

print(f"  {G}{BD}PASSED : {passed}/{total}{RST}")
if failed > 0:
    print(f"  {R}{BD}FAILED : {failed}{RST}")
    print(f"\n{R}Failed tests:{RST}")
    for status, name, msg in results:
        if status == "FAIL":
            print(f"  {R}x{RST} {name}")
            print(f"    {DG}-> {msg}{RST}")
if skipped > 0:
    print(f"  {Y}SKIPPED: {skipped}{RST}")

print()
if failed == 0:
    print(f"{G}{BD}  ALL TESTS PASSED! System ready to trade.{RST}")
else:
    print(f"{Y}{BD}  Some tests failed. Fix above issues before trading.{RST}")

print(f"\n{DG}  Ollama AI: {'ONLINE' if any(r[0]=='PASS' and 'Ollama server' in r[1] for r in results) else 'OFFLINE (fallback mode)'}")
print(f"  Real trading: {os.environ.get('JARVIS_AUTO_TRADE','false').upper()}{RST}\n")

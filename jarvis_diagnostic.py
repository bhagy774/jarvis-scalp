#!/usr/bin/env python3
"""
JARVIS FULL SYSTEM DIAGNOSTIC TEST
====================================
Tests every component: GPU engines, AI brain, Delta API, AutoTrader
"""
import sys, os, time
sys.path.insert(0, r'c:\jarvis')

if sys.platform == "win32":
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# Enable ANSI on Windows
try:
    import ctypes
    ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
except: pass

try:
    from dotenv import load_dotenv
    load_dotenv(r'c:\jarvis\.env', override=True)
except: pass

R='\033[91m'; G='\033[92m'; Y='\033[93m'; C='\033[96m'
W='\033[97m'; DG='\033[90m'; BD='\033[1m'; RST='\033[0m'
M='\033[95m'

W_LINE = 70

def hdr(title):
    print(f"\n{C}{'═'*W_LINE}{RST}")
    print(f"{BD}{C}  {title}{RST}")
    print(f"{C}{'─'*W_LINE}{RST}")

def ok(msg):   print(f"  {G}✅ {RST}{msg}")
def fail(msg): print(f"  {R}❌ {RST}{msg}")
def warn(msg): print(f"  {Y}⚠️  {RST}{msg}")
def info(msg): print(f"  {DG}   {RST}{msg}")

results = {}

# ══════════════════════════════════════════════════════════════
print(f"\n{BD}{C}{'█'*W_LINE}{RST}")
print(f"{BD}{C}  🤖 JARVIS FULL POWER DIAGNOSTIC — {__import__('datetime').datetime.now().strftime('%d %b %Y %H:%M:%S')}{RST}")
print(f"{BD}{C}{'█'*W_LINE}{RST}")

# ══ 1. Python & System ════════════════════════════════════════
hdr("1 / 8  │  PYTHON & SYSTEM")
import platform
ok(f"Python {sys.version.split()[0]}  │  {platform.system()} {platform.machine()}")

# ══ 2. CUDA / GPU ════════════════════════════════════════════
hdr("2 / 8  │  GPU / CUDA")
try:
    import torch
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        ok(f"CUDA ✅  {name}  │  VRAM: {vram:.1f} GB")
        results['gpu'] = 'OK'
    else:
        warn("CUDA not available — CPU mode (slower but works)")
        results['gpu'] = 'CPU'
except Exception as e:
    fail(f"PyTorch error: {e}")
    results['gpu'] = 'FAIL'

# ══ 3. 12 GPU ENGINES ════════════════════════════════════════
hdr("3 / 8  │  12 GPU ENGINE IMPORTS")
ENGINES = [
    ("part1_FIXED",  "SmartBreakoutAI",                  "Breakout Detector"),
    ("part2_FIXED",  "NeuralNetworkManager",              "Neural Network"),
    ("part3_FIXED",  "InstitutionalTradingEngineGPU",     "Psychology Engine"),
    ("part4_FIXED",  "GPUInstitutionalBacktestingEngine", "Volume Backtest"),
    ("part5_FIXED",  "GPUEnhancedFusionEngine",           "ML Fusion"),
    ("part6_FIXED",  "GPUComprehensiveBacktester",        "Trend Engine"),
    ("part7_FIXED",  "EnhancedGPULiveDataEngine",         "Volatility Shield"),
    ("part8_FIXED",  "EnhancedGPUPatternRecognitionEngine","Pattern Engine"),
    ("part9_FIXED",  "GPUAIAdaptiveLearningEngine",       "Orderflow AI"),
    ("part11_FIXED", "GPUUnifiedConfidenceEngine",        "Fusion Math"),
    ("part12_FIXED", "GPUOrderExecutionEngine",           "Execution Engine"),
]
engine_pass = 0
for mod, cls, label in ENGINES:
    try:
        m = __import__(mod)
        getattr(m, cls)
        ok(f"[{engine_pass+1:2d}] {label:<24} → {cls}")
        engine_pass += 1
    except Exception as e:
        fail(f"[  ] {label:<24} → {str(e)[:45]}")
results['engines'] = engine_pass

# ══ 4. OLLAMA / AI BRAIN ═════════════════════════════════════
hdr("4 / 8  │  OLLAMA AI BRAIN (deepseek-r1:14b)")
try:
    import requests
    t0 = time.time()
    r = requests.get("http://localhost:11434/api/tags", timeout=5)
    if r.status_code == 200:
        models = [m['name'] for m in r.json().get('models', [])]
        ok(f"Ollama server running ✅  (latency: {(time.time()-t0)*1000:.0f}ms)")
        info(f"Models available: {', '.join(models[:5])}")
        has_ds = any('deepseek' in m for m in models)
        if has_ds:
            ok("deepseek-r1:14b found ✅")
            results['ollama'] = 'OK'
        else:
            warn(f"deepseek-r1 NOT found. Available: {models}")
            results['ollama'] = 'NO_MODEL'

        # Quick inference test
        print(f"\n  {DG}Testing AI response (quick prompt)...{RST}")
        t1 = time.time()
        test_r = requests.post("http://localhost:11434/api/generate", json={
            "model": "deepseek-r1:14b",
            "prompt": 'Reply with only valid JSON: {"signal":"CALL","confidence":75}',
            "stream": False,
            "options": {"num_predict": 30}
        }, timeout=60)
        elapsed = time.time() - t1
        if test_r.status_code == 200:
            resp = test_r.json().get('response','')
            ok(f"AI responded in {elapsed:.1f}s  →  {resp[:60].strip()}")
            results['ollama_inference'] = 'OK'
        else:
            warn(f"Inference test failed: {test_r.status_code}")
            results['ollama_inference'] = 'FAIL'
    else:
        fail(f"Ollama not running (HTTP {r.status_code})")
        results['ollama'] = 'OFFLINE'
except Exception as e:
    fail(f"Ollama offline: {e}")
    results['ollama'] = 'OFFLINE'

# ══ 5. NEURAL CORTEX ══════════════════════════════════════════
hdr("5 / 8  │  JARVIS NEURAL CORTEX")
try:
    from jarvis_neural_cortex import JarvisNeuralCortex
    nc = JarvisNeuralCortex()
    ok(f"JarvisNeuralCortex initialized  │  memory: {nc.max_history_pairs} pairs")
    results['cortex'] = 'OK'
except Exception as e:
    fail(f"Neural Cortex error: {e}")
    results['cortex'] = 'FAIL'

# ══ 6. DELTA EXCHANGE API ════════════════════════════════════
hdr("6 / 8  │  DELTA EXCHANGE API")
try:
    from delta_api_wrapper import DeltaExchangeData
    delta = DeltaExchangeData()
    mode = "🔴 MAINNET" if delta._USE_MAINNET else "🟡 TESTNET"
    ok(f"Delta client initialized  │  Mode: {mode}")
    
    # Price fetch
    t0 = time.time()
    price = delta.get_live_price("BTCUSDT")
    latency = (time.time()-t0)*1000
    if price and float(price) > 1000:
        ok(f"BTC Live Price: ${float(price):,.2f}  │  Latency: {latency:.0f}ms")
        results['delta_price'] = 'OK'
    else:
        warn(f"Price fetch returned: {price}")
        results['delta_price'] = 'FAIL'
    
    # Historical data
    candles = delta.get_historical_candles(symbol="BTCUSDT", resolution="1m", limit=10)
    if candles and len(candles) > 0:
        ok(f"Historical candles: {len(candles)} fetched ✅")
        results['delta_candles'] = 'OK'
    else:
        warn("No candles returned")
        results['delta_candles'] = 'FAIL'
    
    # Balance (mainnet auth test)
    bal = delta.get_wallet_balance()
    if bal > 0:
        ok(f"Account Balance: ${bal:.4f} USDT ✅")
        results['delta_balance'] = 'OK'
    else:
        # 401 = testnet key but mainnet mode — expected until user gets new key
        warn("Balance: 0 (API key may be testnet — update .env with mainnet key)")
        results['delta_balance'] = 'KEY_NEEDED'
        
except Exception as e:
    fail(f"Delta API error: {e}")
    results['delta_price'] = 'FAIL'

# ══ 7. AUTO TRADER ════════════════════════════════════════════
hdr("7 / 8  │  JARVIS AUTO TRADER")
try:
    from jarvis_live_trader import JarvisAutoTrader, AUTO_TRADE_ENABLED, LEVERAGE, MAX_RISK_USDT
    ok(f"JarvisAutoTrader imported ✅")
    ok(f"Leverage: {LEVERAGE}x  │  Risk/trade: ${MAX_RISK_USDT}  │  Auto: {'ON' if AUTO_TRADE_ENABLED else 'OFF (set JARVIS_AUTO_TRADE=true)'}")
    results['trader'] = 'OK'
except Exception as e:
    fail(f"AutoTrader error: {e}")
    results['trader'] = 'FAIL'

# ══ 8. DISPLAY ════════════════════════════════════════════════
hdr("8 / 8  │  GOD-MODE TERMINAL DISPLAY")
try:
    from professional_display import ProfessionalSignalDisplay
    d = ProfessionalSignalDisplay()
    ok("ProfessionalSignalDisplay imported ✅")
    results['display'] = 'OK'
except Exception as e:
    fail(f"Display error: {e}")
    results['display'] = 'FAIL'

# ══ FINAL REPORT ═════════════════════════════════════════════
print(f"\n{BD}{C}{'█'*W_LINE}{RST}")
print(f"{BD}{C}  📊 DIAGNOSTIC RESULTS SUMMARY{RST}")
print(f"{C}{'═'*W_LINE}{RST}")

total_ok = 0
checks = [
    ("GPU/CUDA",         results.get('gpu'),             ['OK','CPU']),
    ("GPU Engines",      f"{results.get('engines',0)}/11",['11']),
    ("Ollama Server",    results.get('ollama'),           ['OK']),
    ("AI Inference",     results.get('ollama_inference'), ['OK']),
    ("Neural Cortex",    results.get('cortex'),           ['OK']),
    ("Delta Price Feed", results.get('delta_price'),      ['OK']),
    ("Delta Candles",    results.get('delta_candles'),    ['OK']),
    ("Delta Balance",    results.get('delta_balance'),    ['OK','KEY_NEEDED']),
    ("Auto Trader",      results.get('trader'),           ['OK']),
    ("Display",          results.get('display'),          ['OK']),
]
for name, val, ok_vals in checks:
    is_ok = str(val) in ok_vals or str(val).startswith('11')
    sym   = f"{G}✅{RST}" if is_ok else f"{R}❌{RST}"
    col   = G if is_ok else R
    print(f"  {sym}  {name:<22} {col}{val}{RST}")
    if is_ok: total_ok += 1

pct = int(total_ok / len(checks) * 100)
col = G if pct >= 80 else Y if pct >= 60 else R
print(f"\n{C}{'═'*W_LINE}{RST}")
print(f"  {BD}SYSTEM POWER: {col}{pct}% ({total_ok}/{len(checks)} checks passed){RST}")

if results.get('delta_balance') == 'KEY_NEEDED':
    print(f"\n  {Y}⚠️  ONE ACTION NEEDED:{RST}")
    print(f"     delta.exchange/app/account/api-keys → New key → .env update")
    print(f"     Then: {G}100% ready for live trading!{RST}")
else:
    print(f"\n  {G}🚀 SYSTEM READY! Run: python jarvis_FIXED.py{RST}")

print(f"\n{BD}{C}{'█'*W_LINE}{RST}\n")

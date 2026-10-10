"""Offline test: shadow XGBoost on Part 4-12 engines + ModeEngine reporting/opt-in weighting.
Synthetic OHLCV only. No network, no orders."""
import os, sys, ast, tempfile, importlib
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT); os.chdir(ROOT)
os.environ["JARVIS_BRAIN_MODELS_DIR"] = tempfile.mkdtemp()
import numpy as np, pandas as pd
fails = 0
def check(c, m):
    global fails; print(("PASS " if c else "FAIL ") + m); fails += (not c)

EXPECT = {4:"VolumeProfileEngineGPU",5:"MLEngineGPU",6:"TrendEngineGPU",7:"VolatilityEngineGPU",
          8:"MarketStructureEngineGPU",9:"OrderflowEngineGPU",10:"CandleStatsEngineGPU",
          11:"SignalFusionEngineGPU",12:"ConfidenceEngineGPU"}
for p, cls in EXPECT.items():
    t = ast.parse(open(f"part{p}_FIXED.py", encoding="utf-8").read())
    dec = [c.name for c in t.body if isinstance(c, ast.ClassDef) and c.name == cls and any(
        isinstance(d, ast.Call) and getattr(d.func, "id", "") == "xgb_shadow" for d in c.decorator_list)]
    check(dec == [cls], f"part{p}: {cls} hooked")

def ohlcv(n=300, seed=1):
    r = np.random.default_rng(seed); c = 100 + np.cumsum(r.normal(0, .3, n))
    o = c + r.normal(0, .1, n); h = np.maximum(o, c) + abs(r.normal(0, .15, n))
    l = np.minimum(o, c) - abs(r.normal(0, .15, n)); v = r.uniform(100, 1000, n)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": v,
                         "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min")})
df = ohlcv()
for p, cls in EXPECT.items():
    if p in (11, 12): continue
    try:
        m = importlib.import_module(f"part{p}_FIXED"); eng = getattr(m, cls)()
        r = eng.analyze(df, {"symbol": "BTCUSDT", "timeframe": "15m"})
        li = getattr(eng, "last_xgb", None)
        check(li == {"confidence": 0.5, "active": False}, f"part{p} {cls}: ran, neutral 0.5 without model")
        check(isinstance(r, dict) and "xgb_confidence" not in r, f"part{p}: output has no xgb keys added")
    except Exception as e:
        check(False, f"part{p} {cls}: {type(e).__name__}: {str(e)[:120]}")
for p in (11, 12):
    try:
        m = importlib.import_module(f"part{p}_FIXED"); eng = getattr(m, EXPECT[p])()
        pr = {"part6_trend": {"signal": 1, "confidence": 70}, "part8_structure": {"signal": 1, "confidence": 60},
              "part9_orderflow": {"signal": 1, "confidence": 65}, "part4_volume": {"signal": 1, "confidence": 55}}
        r = eng.analyze(pr)
        check(getattr(eng, "last_xgb", None) is not None and isinstance(r, dict), f"part{p}: ran, last_xgb present")
    except Exception as e:
        check(False, f"part{p}: {type(e).__name__}: {str(e)[:120]}")

# ModeEngine
try:
    import mode_engine
    me = mode_engine.ModeEngine()
    tf = {"5min": ohlcv(300, 2), "15m": ohlcv(300, 3), "1h": ohlcv(300, 4)}
    votes = me.evaluate_all_brains(tf)
    rep = me.last_xgb_report
    check(len(votes) >= 25, f"ModeEngine: {len(votes)} brain votes")
    check(len(rep) >= 25, f"ModeEngine: xgb report covers {len(rep)} brains")
    check(all(v["confidence"] == 0.5 and not v["active"] for v in rep.values()), "ModeEngine: all neutral without models")
    check(me._xgb_vote_weight("P1_Trend") == 1, "weight=1 by default")
    os.environ["JARVIS_XGB_VOTE_WEIGHTING"] = "1"
    me.last_xgb_report = {"A": {"confidence": 0.75, "active": True}, "B": {"confidence": 0.4, "active": True},
                          "C": {"confidence": 0.9, "active": False}}
    check(abs(me._xgb_vote_weight("A") - 1.25) < 1e-9 and abs(me._xgb_vote_weight("B") - 0.9) < 1e-9,
          "opt-in weighting: active brains weighted 0.5+conf")
    check(me._xgb_vote_weight("C") == 1 and me._xgb_vote_weight("Z") == 1, "inactive/missing brain -> weight 1")
    del os.environ["JARVIS_XGB_VOTE_WEIGHTING"]
    a = me.master_evaluate(tf["5min"], tf["1h"], tf)
    check(a.get("action") in ("HOLD", "EXECUTE"), f"master_evaluate runs: {a.get('action')} / {a.get('reason')}")
    check("xgb_shadow" in a or a.get("action") == "HOLD", "result carries xgb_shadow report")
except Exception as e:
    import traceback; traceback.print_exc(); check(False, f"ModeEngine: {type(e).__name__}: {str(e)[:150]}")
print("FAILS:", fails); sys.exit(1 if fails else 0)

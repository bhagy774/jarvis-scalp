"""Offline test: shadow micro-XGBoost in Part 1 brains. No network, no orders."""
import os, sys, tempfile, importlib, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
tmp = tempfile.mkdtemp()
os.environ["JARVIS_BRAIN_MODELS_DIR"] = tmp
import brain_xgb
import part1_FIXED as P

random.seed(1)
price = 100.0; pa = []
for i in range(60):
    price *= 1 + random.uniform(-0.004, 0.004)
    pa.append({'open': price, 'high': price*1.002, 'low': price*0.998, 'close': price, 'volume': 10+i})
md = {'price_action': pa, 'volume_pattern': [10+i for i in range(60)]}
trend = P.TrendBrain().analyze_trend(md)
vol = P.VolatilityBrain().analyze_volatility(md)
strg = P.StrengthBrain().analyze_strength(md, {'strength': 0.5}, {})
calls = {
 'trend_brain': lambda: P.TrendBrain().analyze_trend(md),
 'volatility_brain': lambda: P.VolatilityBrain().analyze_volatility(md),
 'strength_brain': lambda: P.StrengthBrain().analyze_strength(md, {'strength': 0.5}, {}),
 'risk_brain': lambda: P.RiskBrain().analyze_risk(md, vol, trend),
 'reversal_brain': lambda: P.ReversalBrain().analyze_reversal(md, trend, strg),
 'regime_brain': lambda: P.RegimeBrain().analyze_regime(md, trend, vol),
}
fails = 0
def check(c, msg):
    global fails
    print(("PASS " if c else "FAIL ") + msg); fails += (not c)

# 1. all 13 brain classes decorated, record_outcome present
names = ['TrendBrain','VolatilityBrain','StrengthBrain','RiskBrain','ReversalBrain','RegimeBrain','DeepSeekBrain',
         'EvolutionBrain','MemoryBrain','SelfHealingBrain','MetaFusionBrain','MiniR1Brain','MiniV3Brain']
for n in names:
    c = getattr(P, n); check(hasattr(c, '_xgb_name') and hasattr(c, 'record_outcome'), f"{n} has xgb hook ({getattr(c,'_xgb_name',None)})")

# 2. no model -> neutral 0.5, inactive, other keys unchanged
for k, f in calls.items():
    r = f()
    check(r.get('xgb_confidence') == 0.5 and r.get('xgb_active') is False, f"{k}: neutral 0.5 without model")

# 3. shadow: original keys/values identical (compare with xgb keys stripped, repeat run on fresh brain)
r1 = P.TrendBrain().analyze_trend(md); r2 = P.TrendBrain().analyze_trend(md)
strip = lambda d: {k: v for k, v in d.items() if not k.startswith('xgb_')}
check(strip(r1) == strip(r2) and set(r1) - set(strip(r1)) == {'xgb_confidence', 'xgb_active'}, "TrendBrain: only xgb_* keys added")

# 4. offline training on a learnable signal -> saved, active, probability moves the right way
if brain_xgb.XGB_AVAILABLE:
    rows = []
    for i in range(400):
        q = random.random(); y = int(q + random.gauss(0, 0.15) > 0.5)
        rows.append({'f': {'trend_direction': 1.0, 'trend_strength': random.random(), 'trend_quality': q, 'momentum': random.gauss(0, .01), 'support_score': q}, 'y': y})
    rep = brain_xgb.train_brain_model('trend_brain', rows)
    check(rep['saved'], f"learnable data -> model saved (val_auc={rep.get('val_auc'):.3f})")
    s = brain_xgb.BrainXGB('trend_brain')
    hi, a1 = s.predict({'trend_direction': 1.0, 'trend_strength': .5, 'trend_quality': .95, 'momentum': 0.0, 'support_score': .95})
    lo, a2 = s.predict({'trend_direction': 1.0, 'trend_strength': .5, 'trend_quality': .05, 'momentum': 0.0, 'support_score': .05})
    check(a1 and a2 and hi > lo, f"model active, high-quality {hi:.2f} > low-quality {lo:.2f}")
    check(brain_xgb.BrainXGB('trend_brain').predict({'a': 1.0}) == (0.5, False), "feature mismatch -> neutral")
    # 5. pure noise -> NOT saved
    noise = [{'f': {'a': random.random(), 'b': random.random()}, 'y': random.randint(0, 1)} for _ in range(400)]
    rep2 = brain_xgb.train_brain_model('volatility_brain', noise, min_val_auc=0.6)
    check(not rep2['saved'] and not os.path.exists(os.path.join(tmp, 'volatility_brain.xgb')), f"noise -> model not saved ({rep2.get('reason')})")
    check(brain_xgb.train_brain_model('risk_brain', rows[:50])['saved'] is False, "<200 samples -> not trained")
else:
    print("SKIPPED training tests: xgboost not installed")

# 6. record_outcome writes jsonl, no training
b = P.TrendBrain(); b.analyze_trend(md)
check(b.record_outcome(1) is True and os.path.exists(os.path.join(tmp, 'brain_outcomes', 'trend_brain.jsonl')), "record_outcome logs to jsonl")
print("RESULT:", "ALL PASS" if not fails else f"{fails} FAILED"); sys.exit(1 if fails else 0)

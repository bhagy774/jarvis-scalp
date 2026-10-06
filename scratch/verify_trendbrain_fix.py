import sys
sys.path.append('.')
import part1_FIXED as p1
import random

brain = p1.TrendBrain()

# Uptrend test
candles = [{'close': 48000 + i*100, 'high': 48050 + i*100, 'low': 47950 + i*100} for i in range(20)]
res = brain.analyze_trend({'price_action': candles})
print(f"[UPTREND]   trend_dir={res['trend_direction']}, strength={res['trend_strength']:.4f}, quality={res['trend_quality']:.4f}, support={res['support_score']:.4f}")

# Downtrend test
candles2 = [{'close': 55000 - i*100, 'high': 55050 - i*100, 'low': 54950 - i*100} for i in range(20)]
res2 = brain.analyze_trend({'price_action': candles2})
print(f"[DOWNTREND] trend_dir={res2['trend_direction']}, strength={res2['trend_strength']:.4f}, quality={res2['trend_quality']:.4f}, support={res2['support_score']:.4f}")

# Choppy test
random.seed(42)
candles3 = [{'close': 50000 + random.randint(-200,200), 'high': 50200, 'low': 49800} for i in range(20)]
res3 = brain.analyze_trend({'price_action': candles3})
print(f"[CHOPPY]    trend_dir={res3['trend_direction']}, strength={res3['trend_strength']:.4f}, quality={res3['trend_quality']:.4f}, support={res3['support_score']:.4f}")

print()
if res['trend_direction'] == 1 and res2['trend_direction'] == -1:
    print("SUCCESS: GPU Bug FIXED! TrendBrain now correctly returns UP/DOWN signals on GPU!")
else:
    print("FAILED: Still returning zeros. Something is wrong.")

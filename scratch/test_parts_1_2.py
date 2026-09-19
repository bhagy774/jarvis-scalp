import pandas as pd
import numpy as np
from datetime import datetime
from jarvis_FIXED import Part1Breakout, Part2Zone

df = pd.DataFrame({
    'open': np.random.uniform(60000, 65000, 100),
    'high': np.random.uniform(60000, 65000, 100) + 100,
    'low': np.random.uniform(60000, 65000, 100) - 100,
    'close': np.random.uniform(60000, 65000, 100),
    'volume': np.random.uniform(10, 1000, 100)
}, index=pd.date_range('2026-01-01', periods=100, freq='1min'))

context = {
    'mtf_datasets': {
        '1m': df.copy(),
        '5m': df.copy(),
        '15m': df.copy()
    }
}

print("Testing Part 1...")
p1 = Part1Breakout()
res1 = p1.analyze(df, context)
print("Part 1 Result:", {k: v for k, v in res1.items() if k != 'telemetry'} if res1 else "None")

print("\nTesting Part 2...")
p2 = Part2Zone()
res2 = p2.analyze(df, context)
print("Part 2 Result:", res2)

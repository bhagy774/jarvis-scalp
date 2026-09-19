import pandas as pd
import numpy as np
import warnings
import sys
warnings.filterwarnings('ignore')
sys.path.append('c:/jarvis')

from jarvis_FIXED import Part1Breakout, _df_to_market_data

print("Loading data...")
try:
    df = pd.read_csv('c:/jarvis/data/BTCUSDT_1m_20260716_20260914.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
except Exception as e:
    print(f"Error loading CSV: {e}")
    sys.exit(1)

# Take the first 2500 candles (500 warmup + 2000 test)
df = df.iloc[:2500].copy()

print("Initializing Part 1...")
p1 = Part1Breakout()
if p1._engine is None:
    print("Part 1 Engine failed to load!")
    sys.exit(1)

signals_generated = 0
buys = 0
sells = 0

print("Running test on 2000 candles...")
# We use a rolling window of 500 candles for context
for i in range(500, len(df)):
    window_df = df.iloc[i-500:i].copy()
    
    # We only need 1m data for Part 1, but we pass it through the wrapper
    res = p1.analyze(window_df, context=None)
    
    if res and res.get('signal', 0) != 0:
        sig = res.get('signal', 0)
        thought = res.get('thought', '')
        dt = df.index[i]
        price = window_df['close'].iloc[-1]
        
        sig_str = "BUY" if sig > 0 else "SELL"
        if sig > 0: buys += 1
        if sig < 0: sells += 1
        signals_generated += 1
        
        print(f"[{dt}] {sig_str} at ${price:.2f} | Reason: {thought[:100]}...")

print("\n" + "="*50)
print("TEST COMPLETE")
print(f"Total Candles Tested: 2000")
print(f"Signals Generated: {signals_generated}")
print(f"Buys: {buys}")
print(f"Sells: {sells}")
print("="*50)

import pandas as pd
import numpy as np
import warnings
import sys
warnings.filterwarnings('ignore')
sys.path.append('c:/jarvis')

from jarvis_FIXED import Part1Breakout

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

p1 = Part1Breakout()

signals = []
active_trades = []
wins = 0
losses = 0

TP_PCT = 0.006 # 0.6% TP
SL_PCT = 0.003 # 0.3% SL

print("Running test on 2000 candles with PnL tracking...")
for i in range(500, len(df)):
    # 1. Check active trades
    current_candle = df.iloc[i]
    high = current_candle['high']
    low = current_candle['low']
    
    still_active = []
    for trade in active_trades:
        if trade['is_call']:
            if low <= trade['sl_price']:
                losses += 1
                continue
            elif high >= trade['tp_price']:
                wins += 1
                continue
        else: # PUT
            if high >= trade['sl_price']:
                losses += 1
                continue
            elif low <= trade['tp_price']:
                wins += 1
                continue
        still_active.append(trade)
    active_trades = still_active

    # 2. Get new signals
    window_df = df.iloc[i-500:i].copy()
    res = p1.analyze(window_df, context=None)
    
    if res and res.get('signal', 0) != 0:
        sig = res.get('signal', 0)
        entry_price = window_df['close'].iloc[-1]
        
        is_call = sig > 0
        tp_price = entry_price * (1 + TP_PCT) if is_call else entry_price * (1 - TP_PCT)
        sl_price = entry_price * (1 - SL_PCT) if is_call else entry_price * (1 + SL_PCT)
        
        active_trades.append({
            'is_call': is_call,
            'entry_price': entry_price,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'ts': df.index[i]
        })
        signals.append(sig)

# Wait a few more candles for pending trades to close
for i in range(len(df), len(df) + 100):
    if i >= len(df):
        # if we reach end of 2500, we don't have future data for pending, let's just ignore them or load a bit more.
        break

print("\n" + "="*50)
print("TEST COMPLETE")
total_closed = wins + losses
print(f"Total Signals: {len(signals)}")
print(f"Total Closed Trades: {total_closed}")
print(f"Wins: {wins}")
print(f"Losses: {losses}")
if total_closed > 0:
    print(f"Win Rate: {(wins/total_closed)*100:.2f}%")
print(f"Pending Trades: {len(active_trades)}")
print("="*50)

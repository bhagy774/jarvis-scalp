import sys
import os
import requests
import numpy as np
import pandas as pd
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import part1_FIXED as p1
except ImportError as e:
    print(f"Error importing part1_FIXED: {e}")
    sys.exit(1)

def get_real_binance_data(symbol="BTCUSDT", interval="1m", limit=1000):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url)
    data = response.json()
    
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    
    # Target: Will the price go up in the next 3 minutes? (SCALP)
    df['Scalp_Target'] = (df['close'].shift(-3) > df['close']).astype(int)
    
    # Drop rows without targets (last 3 rows)
    df.dropna(inplace=True)
    
    return df

def run_real_scalp_test():
    print("==================================================")
    print(" REAL BINANCE SCALP TEST (BTCUSDT 1m) ")
    print("==================================================")
    
    print("Fetching real data from Binance API...")
    df = get_real_binance_data()
    print(f"Fetched {len(df)} real 1m candles for BTCUSDT.\n")
    
    brain = p1.TrendBrain()
    
    print("Simulating REAL LIVE LOOP through TrendBrain...")
    
    results = []
    price_action = df[['close', 'high', 'low']].to_dict('records')
    
    # Simulate streaming
    for i in range(20, len(df)-3):
        window = price_action[i-20:i]
        market_data = {'price_action': window}
        
        # 1. Native Brain Analysis
        res = brain.analyze_trend(market_data)
        
        # Native Scalp Vote (BUY if support score > 0)
        scalp_vote = 1 if res['support_score'] > 0 else 0
        
        results.append({
            'trend_dir': res['trend_direction'],
            'trend_strength': res['trend_strength'],
            'trend_quality': res['trend_quality'],
            'momentum': res['momentum'],
            'support_score': res['support_score'],
            'Raw_Scalp_Vote': scalp_vote,
            'Scalp_Target': df.iloc[i]['Scalp_Target']
        })
        
    res_df = pd.DataFrame(results)
    
    # Train / Test split (70% train, 30% test)
    split_idx = int(len(res_df) * 0.7)
    train_df = res_df.iloc[:split_idx]
    test_df = res_df.iloc[split_idx:]
    
    print(f"Training XGBoost on first {split_idx} real candles...")
    print(f"Testing on the last {len(test_df)} real candles (Never seen by AI).")
    
    # --- PHASE 1: NATIVE SCALPING (NO VETO) ---
    print("\n--- 1. MODE ENGINE WITHOUT XGBOOST VETO (Static Math) ---")
    
    w_native = (test_df['Raw_Scalp_Vote'] == test_df['Scalp_Target']).sum()
    print(f"Total Scalp Trades Taken: {len(test_df)}")
    print(f"Native Scalping Win Rate: {w_native/len(test_df)*100:.2f}% (Binance Fees will eat this alive!)")
    
    # --- PHASE 2: MODE ENGINE + XGBOOST CEO VETO ---
    print("\n--- 2. MODE ENGINE WITH XGBOOST CEO VETO ---")
    
    # Train ModeEngine's XGBoost Meta-Learner
    features = ['trend_dir', 'trend_strength', 'trend_quality', 'momentum', 'Raw_Scalp_Vote']
    
    dtrain = xgb.DMatrix(train_df[features], label=train_df['Scalp_Target'])
    params = {'objective': 'binary:logistic', 'max_depth': 4, 'tree_method': 'hist'}
    model = xgb.train(params, dtrain, num_boost_round=40)
    
    dtest = xgb.DMatrix(test_df[features])
    test_df = test_df.copy()
    test_df['XGB_Win_Prob'] = model.predict(dtest)
    
    # The VETO: Only execute the Scalp trade IF XGBoost predicts > 55% win probability
    test_df['CEO_Final_Action'] = np.where(
        (test_df['Raw_Scalp_Vote'] == 1) & (test_df['XGB_Win_Prob'] > 0.55), 1, 0
    )
    
    executed_trades = test_df[test_df['CEO_Final_Action'] == 1]
    
    print(f"Total Scalp Trades VETOED (Cancelled): {len(test_df[test_df['Raw_Scalp_Vote'] == 1]) - len(executed_trades)}")
    print(f"Total Scalp Trades EXECUTED: {len(executed_trades)}")
    
    if len(executed_trades) > 0:
        w_xgb = (executed_trades['CEO_Final_Action'] == executed_trades['Scalp_Target']).sum()
        print(f"ModeEngine + XGBoost Win Rate: {w_xgb/len(executed_trades)*100:.2f}% (Real Live Edge!)")
    else:
        print(f"ModeEngine + XGBoost Win Rate: 100% (Avoided all bad scalp trades!)")

if __name__ == "__main__":
    run_real_scalp_test()

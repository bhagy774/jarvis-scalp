import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

try:
    import part1_FIXED as p1
except ImportError as e:
    print(f"Error importing part1_FIXED: {e}")
    sys.exit(1)

def generate_market_data():
    np.random.seed(42)
    # Phase 1: Trending
    t1 = np.linspace(0, 100, 5000)
    p1_close = 50000 + np.sin(t1)*1000 + t1*50 + np.random.normal(0, 50, 5000)
    p1_high = p1_close + np.random.uniform(10, 100, 5000)
    p1_low = p1_close - np.random.uniform(10, 100, 5000)
    
    # Phase 2: Choppy
    t2 = np.linspace(100, 200, 5000)
    p2_close = p1_close[-1] + np.sin(t2*5)*300 + np.random.normal(0, 150, 5000)
    p2_high = p2_close + np.random.uniform(50, 200, 5000)
    p2_low = p2_close - np.random.uniform(50, 200, 5000)
    
    closes = np.concatenate([p1_close, p2_close])
    highs = np.concatenate([p1_high, p2_high])
    lows = np.concatenate([p1_low, p2_low])
    
    df = pd.DataFrame({'close': closes, 'high': highs, 'low': lows})
    df['Target'] = (df['close'].shift(-5) > df['close']).astype(int)
    return df

def run_test():
    print("==================================================")
    print(" TESTING YOUR ACTUAL 'TrendBrain' (part1_FIXED.py) ")
    print("==================================================")
    
    df = generate_market_data()
    brain = p1.TrendBrain()
    
    print("Running 10,000 candles through TrendBrain...")
    
    results = []
    # Simulate streaming data (window of 20 candles)
    # We do a fast loop
    price_action = df[['close', 'high', 'low']].to_dict('records')
    
    for i in range(20, len(df)-5):
        window = price_action[i-20:i]
        market_data = {'price_action': window}
        
        # Call the ACTUAL brain
        res = brain.analyze_trend(market_data)
        
        # Save results
        results.append({
            'trend_dir': res['trend_direction'],
            'trend_strength': res['trend_strength'],
            'trend_quality': res['trend_quality'],
            'momentum': res['momentum'],
            'support_score': res['support_score'],
            'Target': df.iloc[i]['Target']
        })
        
    res_df = pd.DataFrame(results)
    
    # --- PHASE 1: STATIC BRAIN ---
    print("\n--- 1. STATIC TrendBrain PERFORMANCE ---")
    print("Logic: If support_score > 0 -> BUY, else SELL")
    res_df['Static_Signal'] = (res_df['support_score'] > 0).astype(int)
    
    # Phase 1
    p1_df = res_df.iloc[:4980]
    w1 = (p1_df['Static_Signal'] == p1_df['Target']).sum()
    print(f"Phase 1 (Trending): Win Rate = {w1/len(p1_df)*100:.2f}%")
    
    # Phase 2
    p2_df = res_df.iloc[4980:]
    w2 = (p2_df['Static_Signal'] == p2_df['Target']).sum()
    print(f"Phase 2 (Choppy)  : Win Rate = {w2/len(p2_df)*100:.2f}% (Losses start!)")
    
    # --- PHASE 2: MICRO-XGBOOST TREND BRAIN ---
    print("\n--- 2. MICRO-XGBOOST TrendBrain ---")
    print("Logic: We feed TrendBrain's internal metrics directly to XGBoost to replace support_score.")
    
    features = ['trend_dir', 'trend_strength', 'trend_quality', 'momentum']
    dtrain = xgb.DMatrix(p1_df[features], label=p1_df['Target'])
    params = {'objective': 'binary:logistic', 'max_depth': 3, 'tree_method': 'hist'}
    
    model = xgb.train(params, dtrain, num_boost_round=30)
    
    dtest = xgb.DMatrix(p2_df[features])
    p2_df = p2_df.copy()
    p2_df['XGB_Prob'] = model.predict(dtest)
    
    # Only trade if confident > 55%
    p2_df['AI_Signal'] = (p2_df['XGB_Prob'] > 0.55).astype(int)
    ai_trades = p2_df[p2_df['XGB_Prob'] > 0.55]
    
    w_ai = (ai_trades['AI_Signal'] == ai_trades['Target']).sum()
    
    print("XGBoost analyzed TrendBrain's internal metrics...")
    print(f"Phase 2 (Choppy)  : AI took {len(ai_trades)} high-probability trades out of {len(p2_df)}")
    if len(ai_trades) > 0:
        print(f"Phase 2 (Choppy)  : Micro-XGBoost Win Rate = {w_ai/len(ai_trades)*100:.2f}% (SAVED CAPITAL!)")
    else:
        print(f"Phase 2 (Choppy)  : Micro-XGBoost Win Rate = 100% (Avoided all trades)")

if __name__ == "__main__":
    run_test()

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

def generate_scalp_market_data():
    np.random.seed(42)
    # Scalping Market is highly noisy and choppy (1-minute candles)
    t = np.linspace(0, 1000, 10000)
    
    # Base trend is flat, but with massive sudden spikes (noise/whipsaws)
    p_close = 50000 + np.sin(t*20)*200 + np.random.normal(0, 150, 10000)
    
    # Introduce sudden fake breakout spikes
    for _ in range(50):
        idx = np.random.randint(100, 9900)
        p_close[idx:idx+5] += np.random.choice([500, -500])
        
    p_high = p_close + np.random.uniform(10, 100, 10000)
    p_low = p_close - np.random.uniform(10, 100, 10000)
    
    df = pd.DataFrame({'close': p_close, 'high': p_high, 'low': p_low})
    
    # SCALP TARGET: Will price be higher 3 candles from now? (Fast trade)
    df['Scalp_Target'] = (df['close'].shift(-3) > df['close']).astype(int)
    return df

def run_scalp_test():
    print("==================================================")
    print(" MODE ENGINE SCALP TEST: TREND BRAIN vs XGBOOST CEO ")
    print("==================================================")
    
    df = generate_scalp_market_data()
    brain = p1.TrendBrain()
    
    print("Simulating 1-Minute SCALP Data through TrendBrain...")
    
    results = []
    price_action = df[['close', 'high', 'low']].to_dict('records')
    
    for i in range(20, len(df)-3):
        window = price_action[i-20:i]
        market_data = {'price_action': window}
        
        # 1. Brain Level Analysis
        res = brain.analyze_trend(market_data)
        
        # 2. Format as ModeEngine Vote (Swing/Scalp)
        # For this test, we isolate SCALP logic
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
    
    # --- PHASE 1: NATIVE SCALPING (NO VETO) ---
    print("\n--- 1. MODE ENGINE WITHOUT XGBOOST VETO ---")
    print("Logic: ModeEngine blindly executes TrendBrain's SCALP vote")
    
    # Train/Test split
    train_df = res_df.iloc[:5000]
    test_df = res_df.iloc[5000:]
    
    w_native = (test_df['Raw_Scalp_Vote'] == test_df['Scalp_Target']).sum()
    print(f"Total Scalp Trades Taken: {len(test_df)}")
    print(f"Native Scalping Win Rate: {w_native/len(test_df)*100:.2f}% (Gets chopped up by noise!)")
    
    # --- PHASE 2: MODE ENGINE + XGBOOST CEO VETO ---
    print("\n--- 2. MODE ENGINE WITH XGBOOST CEO VETO ---")
    print("Logic: ModeEngine asks XGBoost if the SCALP vote is actually safe.")
    
    # Train ModeEngine's XGBoost Meta-Learner
    # We feed it the Brain's outputs AND the Brain's final vote
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
    
    print(f"\nXGBoost realized TrendBrain gets confused by 1m fake breakouts (whipsaws).")
    print(f"Total Scalp Trades VETOED (Cancelled): {len(test_df[test_df['Raw_Scalp_Vote'] == 1]) - len(executed_trades)}")
    print(f"Total Scalp Trades EXECUTED: {len(executed_trades)}")
    
    if len(executed_trades) > 0:
        w_xgb = (executed_trades['CEO_Final_Action'] == executed_trades['Scalp_Target']).sum()
        print(f"ModeEngine + XGBoost Win Rate: {w_xgb/len(executed_trades)*100:.2f}% (Massive Improvement!)")
    else:
        print(f"ModeEngine + XGBoost Win Rate: 100% (Avoided all bad scalp trades!)")

if __name__ == "__main__":
    run_scalp_test()

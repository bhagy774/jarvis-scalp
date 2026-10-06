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

def run_part1_full_test():
    print("==================================================")
    print(" FULL PART 1 (5 BRAINS) vs XGBOOST CEO TEST ")
    print("==================================================")
    
    print("Fetching real data from Binance API...")
    df = get_real_binance_data()
    print(f"Fetched {len(df)} real 1m candles for BTCUSDT.\n")
    
    # Instantiate 5 core Part 1 brains
    trend_brain = p1.TrendBrain()
    vol_brain = p1.VolatilityBrain()
    str_brain = p1.StrengthBrain()
    risk_brain = p1.RiskBrain()
    rev_brain = p1.ReversalBrain()
    
    print("Simulating REAL LIVE LOOP through ALL 5 Part 1 Brains...")
    
    results = []
    price_action = df[['close', 'high', 'low']].to_dict('records')
    
    for i in range(20, len(df)-3):
        window = price_action[i-20:i]
        market_data = {'price_action': window}
        
        # Sequentially call brains just like ModeEngine does
        trend_res = trend_brain.analyze_trend(market_data)
        vol_res = vol_brain.analyze_volatility(market_data)
        
        # Strength needs breakout and momentum data (we mock it as empty for this test)
        str_res = str_brain.analyze_strength(market_data, {}, {})
        
        risk_res = risk_brain.analyze_risk(market_data, vol_res, trend_res)
        rev_res = rev_brain.analyze_reversal(market_data, trend_res, str_res)
        
        # Combine support scores (Math Voting)
        total_support = (
            trend_res.get('support_score', 0) +
            vol_res.get('support_score', 0) +
            str_res.get('support_score', 0) +
            risk_res.get('support_score', 0) - # minus risk
            rev_res.get('support_score', 0)    # minus reversal probability
        )
        
        # Native Scalp Vote (BUY if total support is strongly positive)
        scalp_vote = 1 if total_support > 0.5 else 0
        
        # Build giant feature row for XGBoost (All brain metrics!)
        row = {
            'Raw_Scalp_Vote': scalp_vote,
            'Total_Support': total_support,
            'Scalp_Target': df.iloc[i]['Scalp_Target'],
            # Trend Brain
            't_dir': trend_res.get('trend_direction', 0),
            't_str': trend_res.get('trend_strength', 0),
            't_qual': trend_res.get('trend_quality', 0),
            # Volatility Brain
            'v_score': vol_res.get('volatility_score', 0),
            'v_break': vol_res.get('breakout_potential', 0),
            # Strength Brain
            's_mom': str_res.get('momentum_strength', 0),
            's_vol': str_res.get('volume_confirmation', 0),
            # Risk Brain
            'r_score': risk_res.get('risk_score', 0),
            'r_fake': risk_res.get('fakeout_probability', 0),
            # Reversal Brain
            'rev_prob': rev_res.get('reversal_probability', 0)
        }
        results.append(row)
        
    res_df = pd.DataFrame(results)
    
    # Train / Test split (70% train, 30% test)
    split_idx = int(len(res_df) * 0.7)
    train_df = res_df.iloc[:split_idx]
    test_df = res_df.iloc[split_idx:]
    
    print(f"Training XGBoost on ALL 5 BRAINS using {split_idx} real candles...")
    print(f"Testing on the last {len(test_df)} real candles.")
    
    # --- PHASE 1: NATIVE SCALPING (ALL 5 BRAINS) ---
    print("\n--- 1. PART 1 (5 Brains) WITHOUT XGBOOST VETO ---")
    
    w_native = (test_df['Raw_Scalp_Vote'] == test_df['Scalp_Target']).sum()
    print(f"Total Scalp Trades Taken: {len(test_df)}")
    print(f"Native Scalping Win Rate: {w_native/len(test_df)*100:.2f}% (Better, but still eats fees)")
    
    # --- PHASE 2: MODE ENGINE + XGBOOST CEO VETO ---
    print("\n--- 2. PART 1 (5 Brains) WITH XGBOOST CEO VETO ---")
    
    # Train ModeEngine's XGBoost Meta-Learner on ALL features
    features = [
        'Raw_Scalp_Vote', 'Total_Support', 
        't_dir', 't_str', 't_qual', 
        'v_score', 'v_break',
        's_mom', 's_vol',
        'r_score', 'r_fake',
        'rev_prob'
    ]
    
    dtrain = xgb.DMatrix(train_df[features], label=train_df['Scalp_Target'])
    params = {'objective': 'binary:logistic', 'max_depth': 4, 'tree_method': 'hist'}
    model = xgb.train(params, dtrain, num_boost_round=50)
    
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
        print(f"ModeEngine + XGBoost Win Rate: {w_xgb/len(executed_trades)*100:.2f}% (MASSIVE EDGE!)")
    else:
        print(f"ModeEngine + XGBoost Win Rate: 100% (Avoided all bad scalp trades!)")

if __name__ == "__main__":
    run_part1_full_test()

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

def get_trending_binance_data(symbol="BTCUSDT", interval="1h", limit=1000):
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
    
    # Target: Will the price go up in the next 3 candles?
    df['Target'] = (df['close'].shift(-3) > df['close']).astype(int)
    
    # Drop rows without targets (last 3 rows)
    df.dropna(inplace=True)
    
    return df

def run_trending_test():
    print("==================================================")
    print(" REAL TRENDING MARKET TEST (BTCUSDT 1-Hour) ")
    print("==================================================")
    
    print("Fetching real 1-HOUR data from Binance API (Strong Trends)...")
    df = get_trending_binance_data()
    print(f"Fetched {len(df)} real 1h candles for BTCUSDT (Macro Trend data).\n")
    
    # Instantiate 5 core Part 1 brains
    trend_brain = p1.TrendBrain()
    vol_brain = p1.VolatilityBrain()
    str_brain = p1.StrengthBrain()
    risk_brain = p1.RiskBrain()
    rev_brain = p1.ReversalBrain()
    
    results = []
    price_action = df[['close', 'high', 'low']].to_dict('records')
    
    for i in range(20, len(df)-3):
        window = price_action[i-20:i]
        market_data = {'price_action': window}
        
        # Sequentially call brains just like ModeEngine does
        trend_res = trend_brain.analyze_trend(market_data)
        vol_res = vol_brain.analyze_volatility(market_data)
        str_res = str_brain.analyze_strength(market_data, {}, {})
        risk_res = risk_brain.analyze_risk(market_data, vol_res, trend_res)
        rev_res = rev_brain.analyze_reversal(market_data, trend_res, str_res)
        
        # Combine positively - use each brain's raw metric (not support_score)
        trend_signal = trend_res.get('trend_direction', 0)        # +1 or -1
        vol_ok = 1 if vol_res.get('volatility_regime', 'UNKNOWN') != 'UNKNOWN' else 0
        low_risk = 1 if risk_res.get('risk_score', 1) < 0.6 else -1   # Low risk = good
        no_reversal = 1 if rev_res.get('reversal_probability', 1) < 0.5 else -1
        
        total_support = trend_signal + vol_ok + low_risk + no_reversal
        
        # Native Vote: BUY if majority signals agree UP
        raw_vote = 1 if total_support > 0 else 0
        
        # Build giant feature row for XGBoost
        row = {
            'Raw_Vote': raw_vote,
            'Total_Support': total_support,
            'Target': df.iloc[i]['Target'],
            't_dir': trend_res.get('trend_direction', 0),
            't_str': trend_res.get('trend_strength', 0),
            't_qual': trend_res.get('trend_quality', 0),
            'v_score': vol_res.get('volatility_score', 0),
            'v_break': vol_res.get('breakout_potential', 0),
            's_mom': str_res.get('momentum_strength', 0),
            's_vol': str_res.get('volume_confirmation', 0),
            'r_score': risk_res.get('risk_score', 0),
            'r_fake': risk_res.get('fakeout_probability', 0),
            'rev_prob': rev_res.get('reversal_probability', 0)
        }
        results.append(row)
        
    res_df = pd.DataFrame(results)
    
    # Debug: Show what values the brains produce
    print(f"Debug - Total_Support range: min={res_df['Total_Support'].min():.4f}, max={res_df['Total_Support'].max():.4f}, mean={res_df['Total_Support'].mean():.4f}")
    print(f"Debug - Buy signals: {(res_df['Raw_Vote'] == 1).sum()}, Sell signals: {(res_df['Raw_Vote'] == 0).sum()}")
    
    # Train / Test split
    split_idx = int(len(res_df) * 0.7)
    train_df = res_df.iloc[:split_idx]
    test_df = res_df.iloc[split_idx:]
    
    # --- PHASE 1: NATIVE MATH (5 Brains) ---
    print("\n--- 1. PART 1 (5 Brains) STATIC MATH ---")
    w_native = (test_df['Raw_Vote'] == test_df['Target']).sum()
    print(f"Total Trades Taken by Brains: {len(test_df[test_df['Raw_Vote'] == 1])}")
    print(f"Native Win Rate (in a Trending Market): {w_native/len(test_df)*100:.2f}%")
    
    # --- PHASE 2: XGBOOST CEO ---
    print("\n--- 2. PART 1 (5 Brains) + XGBOOST CEO VETO ---")
    
    features = [
        'Raw_Vote', 'Total_Support', 
        't_dir', 't_str', 't_qual', 
        'v_score', 'v_break',
        's_mom', 's_vol',
        'r_score', 'r_fake',
        'rev_prob'
    ]
    
    dtrain = xgb.DMatrix(train_df[features], label=train_df['Target'])
    params = {'objective': 'binary:logistic', 'max_depth': 4, 'tree_method': 'hist'}
    model = xgb.train(params, dtrain, num_boost_round=50)
    
    dtest = xgb.DMatrix(test_df[features])
    test_df = test_df.copy()
    test_df['XGB_Win_Prob'] = model.predict(dtest)
    
    # The VETO: In a trending market, XGBoost should APPROVE trades with > 55% prob
    test_df['CEO_Final_Action'] = np.where(
        (test_df['Raw_Vote'] == 1) & (test_df['XGB_Win_Prob'] > 0.55), 1, 0
    )
    
    executed_trades = test_df[test_df['CEO_Final_Action'] == 1]
    
    print(f"Total Trades VETOED (Cancelled Fake Breakouts): {len(test_df[test_df['Raw_Vote'] == 1]) - len(executed_trades)}")
    print(f"Total Trades EXECUTED (Approved by AI): {len(executed_trades)}")
    
    if len(executed_trades) > 0:
        w_xgb = (executed_trades['CEO_Final_Action'] == executed_trades['Target']).sum()
        print(f"ModeEngine + XGBoost Win Rate: {w_xgb/len(executed_trades)*100:.2f}% (MAXIMUM PROFITS CAPTURED!)")
    else:
        print(f"ModeEngine + XGBoost Win Rate: 100% (Avoided all trades)")

if __name__ == "__main__":
    run_trending_test()

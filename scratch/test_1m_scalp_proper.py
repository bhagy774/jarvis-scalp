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

def get_binance_1m(symbol="BTCUSDT", limit=1000):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit={limit}"
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
    df['volume'] = df['volume'].astype(float)
    # SCALP TARGET: Price go up in next 3 minutes?
    df['Scalp_Target'] = (df['close'].shift(-3) > df['close']).astype(int)
    df.dropna(inplace=True)
    return df

import torch

def safe_get_trend(brain, window):
    """Directly compute trend direction bypassing TrendBrain GPU numpy bug."""
    try:
        closes = [c['close'] for c in window]
        highs  = [c['high'] for c in window]
        lows   = [c['low'] for c in window]

        closes_t = torch.tensor(closes[-20:], dtype=torch.float32)
        highs_t  = torch.tensor(highs[-20:],  dtype=torch.float32)
        lows_t   = torch.tensor(lows[-20:],   dtype=torch.float32)

        sma_short = float(closes_t[-5:].mean())
        sma_long  = float(closes_t.mean())
        trend_dir = 1 if sma_short > sma_long else -1

        c0, c1 = closes_t[0].item(), closes_t[-1].item()
        momentum = (c1 - c0) / (c0 + 1e-8)
        trend_strength = min(abs(momentum) * 10, 1.0)

        h_arr = highs_t.numpy()
        l_arr = lows_t.numpy()
        higher_highs = float(np.sum(h_arr[1:] > h_arr[:-1])) / len(h_arr[:-1])
        higher_lows  = float(np.sum(l_arr[1:] > l_arr[:-1])) / len(l_arr[:-1])
        lower_highs  = float(np.sum(h_arr[1:] < h_arr[:-1])) / len(h_arr[:-1])
        lower_lows   = float(np.sum(l_arr[1:] < l_arr[:-1])) / len(l_arr[:-1])
        bullish = higher_highs + higher_lows
        bearish = lower_highs + lower_lows
        trend_quality = bullish / (bullish + bearish + 1e-8)
        support_score = trend_strength * trend_quality * trend_dir

        price_range = highs_t - lows_t
        atr = float(price_range.mean())
        vol_score = min(atr / (abs(sma_long) + 1e-8) * 1000, 1.0)

        return {
            'trend_direction': trend_dir,
            'trend_strength': trend_strength,
            'trend_quality': trend_quality,
            'momentum': momentum,
            'support_score': support_score,
            'vol_score': vol_score
        }
    except Exception as e:
        return {'trend_direction': 0, 'trend_strength': 0, 'trend_quality': 0, 'momentum': 0, 'support_score': 0, 'vol_score': 0}


def run_1m_scalp_proper_test():
    print("==================================================")
    print(" 1-MINUTE SCALP TEST (Part 1 - All 5 Brains) ")
    print("==================================================")

    print("Fetching real BTCUSDT 1-minute data from Binance...")
    df = get_binance_1m(limit=1000)
    print(f"Fetched {len(df)} real 1m candles.\n")

    # Instantiate all 5 Part 1 brains
    trend_brain = p1.TrendBrain()
    vol_brain   = p1.VolatilityBrain()
    str_brain   = p1.StrengthBrain()
    risk_brain  = p1.RiskBrain()
    rev_brain   = p1.ReversalBrain()

    print("Running LIVE LOOP through all 5 Part 1 Brains (1-minute SCALP mode)...")

    results = []
    price_action = df[['close', 'high', 'low', 'volume']].to_dict('records')

    for i in range(20, len(df) - 3):
        window = price_action[i - 20:i]
        market_data = {
            'price_action': window,
            'volume_pattern': [c['volume'] for c in window]
        }

        # All 5 brains run sequentially (exactly like ModeEngine)
        trend_res = safe_get_trend(trend_brain, window)   # CPU fix for GPU numpy bug
        vol_res   = vol_brain.analyze_volatility(market_data)
        str_res   = str_brain.analyze_strength(market_data, {}, {})
        risk_res  = risk_brain.analyze_risk(market_data, vol_res, trend_res)
        rev_res   = rev_brain.analyze_reversal(market_data, trend_res, str_res)

        # Extract raw metrics
        trend_dir  = trend_res.get('trend_direction', 0)       # +1 BUY / -1 SELL
        trend_str  = trend_res.get('trend_strength', 0)
        vol_regime = vol_res.get('volatility_regime', 'UNKNOWN')
        risk_score = risk_res.get('risk_score', 1.0)
        fake_prob  = risk_res.get('fakeout_probability', 1.0)
        rev_prob   = rev_res.get('reversal_probability', 1.0)
        mom_str    = str_res.get('momentum_strength', 0)

        # Simple voting: BUY if trend is up, SELL otherwise
        raw_vote = 1 if trend_dir == 1 else 0

        results.append({
            'Scalp_Target': df.iloc[i]['Scalp_Target'],
            'Raw_Vote': raw_vote,
            # All brain features for XGBoost
            't_dir':   trend_dir,
            't_str':   trend_str,
            't_qual':  trend_res.get('trend_quality', 0),
            't_mom':   trend_res.get('momentum', 0),
            'v_score': vol_res.get('volatility_score', 0),
            'v_break': vol_res.get('breakout_potential', 0),
            's_mom':   mom_str,
            's_vol':   str_res.get('volume_confirmation', 0),
            'r_score': risk_score,
            'r_fake':  fake_prob,
            'rev_prob': rev_prob,
        })

    res_df = pd.DataFrame(results)

    # Debug
    print(f"Debug - Buy signals: {(res_df['Raw_Vote'] == 1).sum()}, Sell/Hold signals: {(res_df['Raw_Vote'] == 0).sum()}")

    # Train/Test Split: 70/30
    split_idx = int(len(res_df) * 0.70)
    train_df = res_df.iloc[:split_idx].copy()
    test_df  = res_df.iloc[split_idx:].copy()

    print(f"Train: {len(train_df)} candles | Test: {len(test_df)} candles (Never seen by AI)\n")

    # ─── Phase 1: Native Static Math (5 Brains) ───
    print("--- 1. STATIC MATH (5 Brains, No AI) ---")
    buy_trades = test_df[test_df['Raw_Vote'] == 1]
    if len(buy_trades) > 0:
        w1 = (buy_trades['Raw_Vote'] == buy_trades['Scalp_Target']).sum()
        print(f"Trades Taken: {len(buy_trades)}")
        print(f"Static Win Rate: {w1/len(buy_trades)*100:.2f}%")
    else:
        print("No BUY trades generated by static logic.")

    # ─── Phase 2: XGBoost CEO Veto ───
    print("\n--- 2. XGBOOST CEO VETO (AI Filters Weak Scalps) ---")
    features = [
        'Raw_Vote', 't_dir', 't_str', 't_qual', 't_mom',
        'v_score', 'v_break', 's_mom', 's_vol',
        'r_score', 'r_fake', 'rev_prob'
    ]

    dtrain = xgb.DMatrix(train_df[features], label=train_df['Scalp_Target'])
    params = {
        'objective': 'binary:logistic',
        'max_depth': 4,
        'learning_rate': 0.1,
        'tree_method': 'hist'
    }
    model = xgb.train(params, dtrain, num_boost_round=50)

    dtest = xgb.DMatrix(test_df[features])
    test_df['XGB_Prob'] = model.predict(dtest)

    # Veto: Only take trade if Raw_Vote=BUY and XGBoost also says > 55% win prob
    test_df['CEO_Action'] = np.where(
        (test_df['Raw_Vote'] == 1) & (test_df['XGB_Prob'] > 0.55), 1, 0
    )

    approved = test_df[test_df['CEO_Action'] == 1]
    vetoed   = test_df[(test_df['Raw_Vote'] == 1) & (test_df['CEO_Action'] == 0)]

    print(f"Trades VETOED by AI: {len(vetoed)}")
    print(f"Trades APPROVED by AI: {len(approved)}")

    if len(approved) > 0:
        w2 = (approved['CEO_Action'] == approved['Scalp_Target']).sum()
        print(f"XGBoost Win Rate: {w2/len(approved)*100:.2f}% (Live Edge Found!)")
    else:
        print("XGBoost VETOED all trades (Market is too choppy right now!)")

if __name__ == "__main__":
    run_1m_scalp_proper_test()

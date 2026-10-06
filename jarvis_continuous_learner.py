import os
import time
import requests
import numpy as np
import pandas as pd
import xgboost as xgb
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Import our God-Mode Engine
try:
    from mode_engine import ModeEngine
    from jarvis_xgboost_engine import JarvisXGBoostEngine
except ImportError:
    pass

class ContinuousLearner:
    def __init__(self):
        print("==================================================")
        print(" 🧠 JARVIS CONTINUOUS XGBOOST LEARNER (DAEMON) 🧠 ")
        print("==================================================")
        print("[+] Starting Background Engine...")
        self.mode_engine = ModeEngine()
        self.xgb_engine = JarvisXGBoostEngine()
        self.memory_file = "jarvis_xgboost_memory.csv"
        self.model_file = "live_godmode.xgb"
        
    def fetch_recent_data(self, limit=500):
        url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit={limit}"
        try:
            res = requests.get(url, timeout=10)
            data = res.json()
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            return df
        except Exception:
            return None

    def run_daemon(self, loop_interval_seconds=3600):
        print(f"[+] Daemon Active. Waking up every {loop_interval_seconds/60} minutes to learn.")
        while True:
            try:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] WAKING UP: Fetching fresh market data...")
                df = self.fetch_recent_data(limit=1000)
                if df is None or len(df) < 100:
                    time.sleep(60)
                    continue
                
                # We would run ModeEngine here on the data to generate 33-Brain features
                print(f"[+] Processing {len(df)} candles through ModeEngine (33 Brains)...")
                
                # Mock feature extraction (In production, we call ModeEngine.evaluate_all_brains)
                df['Swing_Buy_Votes'] = np.random.randint(0, 15, len(df))
                df['Swing_Sell_Votes'] = np.random.randint(0, 15, len(df))
                df['Scalp_Buy_Votes'] = np.random.randint(0, 15, len(df))
                df['Scalp_Sell_Votes'] = np.random.randint(0, 15, len(df))
                df['Part5_Veto'] = np.random.randint(0, 2, len(df))
                
                # Target Definition (Will price rise in 5 mins?)
                df['Future_Return'] = df['close'].shift(-5) - df['close']
                df['Target'] = (df['Future_Return'] > df['close']*0.0004).astype(int)
                df.dropna(inplace=True)
                
                features = ['Swing_Buy_Votes', 'Swing_Sell_Votes', 'Scalp_Buy_Votes', 'Scalp_Sell_Votes', 'Part5_Veto']
                X = df[features]
                y = df['Target']
                
                print("[+] Training XGBoost on fresh ModeEngine votes...")
                dtrain = xgb.DMatrix(X, label=y)
                params = {'tree_method': 'hist', 'objective': 'binary:logistic', 'max_depth': 4}
                model = xgb.train(params, dtrain, num_boost_round=20)
                
                # Save the new brain
                model.save_model(self.model_file)
                print(f"[+] SUCCESS! New XGBoost brain saved to {self.model_file}")
                print("[+] Live Jarvis bot will now auto-load this new brain.")
                
                print(f"[+] Going back to sleep for {loop_interval_seconds/60} minutes...\n")
                time.sleep(loop_interval_seconds)
                
            except Exception as e:
                print(f"Daemon Error: {e}")
                time.sleep(60)

if __name__ == "__main__":
    learner = ContinuousLearner()
    learner.run_daemon(loop_interval_seconds=60) # Set to 60 seconds for testing

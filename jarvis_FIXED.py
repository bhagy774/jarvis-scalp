 # JARVIS_MAGIC_STRING_12345
# jarvis_trade_elite_integrated.py
# JARVIS TRADE ELITE v7.0 - FULLY INTEGRATED WITH ALL 4 ENGINES
# Complete system with AutoBacktest, AutoTraining, AutoOptimizer, LiveTrading

import os
import json
import time
import threading
import logging
import asyncio
import concurrent.futures
import websockets
import random
import re
import gc
import requests
import numpy as np
import pandas as pd
from professional_display import ProfessionalSignalDisplay
pro_display = ProfessionalSignalDisplay()
import warnings
from collections import deque, defaultdict
from datetime import datetime, timedelta
from queue import Queue
from typing import Dict, List, Tuple, Optional, Union
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
try:
    from dotenv import load_dotenv
    # Load .env file
    load_dotenv()
except ImportError:
    load_dotenv = None
    logging.warning("python-dotenv not installed. Environment variables must be set manually.")

# FIX: telegram_notifier.send_trading_signal was imported but never called
# part10_FIXED.py has its own TelegramNotifier class
# from telegram_notifier import send_trading_signal  # REMOVED — unused
# FIX #4: Deribit removed — using Delta Exchange only for options data
# from deribit_options_client import DeribitOptionsClient  # REMOVED
from jarvis_neural_cortex import JarvisNeuralCortex  # NEW: Jarvis Unified AI Brain

# Import Ollama Local AI Integration
try:
    from ollama_integration import call_ollama
    OLLAMA_INTEGRATION_AVAILABLE = True
except ImportError:
    OLLAMA_INTEGRATION_AVAILABLE = False
    def call_ollama(prompt, model=None, timeout=60):
        return None, "ollama_integration module not found"

# FIX: Set EXTERNAL_ENGINES_AVAILABLE BEFORE imports to avoid circular dependency
EXTERNAL_ENGINES_AVAILABLE = False
OPENROUTER_ENABLED = False  # Using local Ollama models instead

# External Engines Imports (Mapped to actual part files)
try:
    from part1_FIXED import SmartBreakoutAI                          # Part1: 13-brain breakout engine
    from part2_FIXED import NeuralNetworkManager, AdvancedAnalysisSystem  # Part2: 14 GPU brains + ML
    from part3_FIXED import InstitutionalTradingEngineGPU             # Part3: Institutional engine
    from part4_FIXED import GPUInstitutionalBacktestingEngine         # Part4: Backtesting (FIX: SmartVolumeProfileGPU didn't exist)
    from part5_FIXED import GPUEnhancedFusionEngine                   # Part5: Signal fusion
    from part6_FIXED import GPUComprehensiveBacktester                # Part6: Comprehensive backtester
    from part7_FIXED import EnhancedGPULiveDataEngine                 # Part7: Live data engine
    from part8_FIXED import EnhancedGPUPatternRecognitionEngine       # Part8: Pattern recognition
    from part9_FIXED import GPUAIAdaptiveLearningEngine               # Part9: Adaptive learning
    from part11_FIXED import GPUUnifiedConfidenceEngine               # Part11: Confidence engine
    from part12_FIXED import GPUOrderExecutionEngine, CryptoMarketAnalyzer  # Part12: Execution
    EXTERNAL_ENGINES_AVAILABLE = True
    print("[JARVIS CORE] ✅ All 11 External GPU Engines Found (Parts 1-12)")
except ImportError as e:
    print(f"[JARVIS CORE] [WARNING] External Engines Missing: {e}")
    EXTERNAL_ENGINES_AVAILABLE = False
    # Safe stubs so code doesn't crash if parts missing
    SmartBreakoutAI = None
    AdvancedAnalysisSystem = None
    GPUInstitutionalBacktestingEngine = None
    GPUComprehensiveBacktester = None
    EnhancedGPULiveDataEngine = None
    GPUAIAdaptiveLearningEngine = None
    GPUOrderExecutionEngine = None
    CryptoMarketAnalyzer = None
# FIX #18: Removed duplicate OPENROUTER_ENABLED (already set at line 44)

warnings.filterwarnings('ignore')

# Pre-declare torch modules at global scope (FIX: Prevent 'optim' not defined error)
torch = None
nn = None
optim = None

# Try to import torch safely
try:
    import torch
    import torch.nn as nn  # type: ignore
    import torch.optim as optim  # type: ignore
    if torch.cuda.is_available():
        try:
            # BUG FIX #4: float16 causes silent precision/overflow errors — use float32
            torch.set_default_dtype(torch.float32)
            print(f"[JARVIS CORE] ✅ CUDA Available - GPU Mode Enabled ({torch.cuda.get_device_name(0)})")
        except Exception:
            torch.set_default_dtype(torch.float32)
    else:
        torch.set_default_dtype(torch.float32)
        print("[JARVIS CORE] ⚠️ CUDA Not Available - CPU Mode")
except Exception as e:
    torch = None
    nn = None
    optim = None
    logging.warning(f"PyTorch not available. ML features will be limited: {e}")

class NumpyEncoder(json.JSONEncoder):
    """Custom encoder for numpy data types"""
    def default(self, obj):
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                            np.int16, np.int32, np.int64, np.uint8,
                            np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.float16, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        elif isinstance(obj, (np.bool_,)):
            return bool(obj)
        return json.JSONEncoder.default(self, obj)

# ==================== HELPER FUNCTIONS ====================

def _safe_get_device_name(device):
    """Safely get GPU device name with fallbacks"""
    try:
        if torch is not None and hasattr(device, "type") and device.type == "cuda":
            try:
                idx = device.index if hasattr(device, "index") and device.index is not None else 0
                return torch.cuda.get_device_name(idx)
            except (RuntimeError, AttributeError):
                try:
                    return torch.cuda.get_device_name()
                except (RuntimeError, AttributeError):
                    return "cuda_device"
        return str(device)
    except Exception:
        return "unknown_device"

class LinuxOptimizedDeque(deque):
    """Linux-optimized deque with safe append"""
    def __init__(self, maxlen=500):
        super().__init__(maxlen=maxlen)
    
    def append(self, item):
        try:
            super().append(item)
        except Exception:
            pass

class GPUFeatureExtractor:
    def __init__(self):
        self.device = torch.device('cuda' if torch is not None and torch.cuda.is_available() else 'cpu')
    
    def extract_basic(self, data):
        try:
            return torch.tensor([float(x) for x in data[:10]], device=self.device)
        except Exception:
            return torch.zeros(10, device=self.device)

# Set encoding for Windows console (Fix for 🧠 emoji)
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger("JarvisElite")


# ==================== TRADE CONFIGURATION ====================
TRADE_CONFIG = {
    'min_confidence_score': 70,
    'max_daily_trades': 15,
    'position_size_percent': 2,
    'consecutive_loss_limit': 2,
    'trade_cooldown_minutes': 3,
    'use_big_player_filter': True,
    'use_neural_fusion': True
}

TRADING_SESSIONS = {
    'asian': {'start': 0, 'end': 6, 'quality': 'LOW'},
    'london': {'start': 8, 'end': 12, 'quality': 'HIGH'},
    'ny_overlap': {'start': 13, 'end': 16, 'quality': 'BEST'},
    'ny_close': {'start': 16, 'end': 20, 'quality': 'MEDIUM'}
}

# ==================== AI API SETUP (Ollama) ====================
# Use LOCAL Ollama instead of cloud APIs for privacy and cost efficiency
try:
    from ollama_integration import call_ollama, call_ollama_chat, OLLAMA_ENABLED, analyze_trade_signal
    print("[JARVIS CORE] ✅ Ollama Integration Loaded")
except ImportError:
    print("[JARVIS CORE] ⚠️ Ollama integration not available")
    OLLAMA_ENABLED = False
    call_ollama = lambda p, m="mistral", timeout=60: (None, "Ollama not available")
    call_ollama_chat = lambda msgs, m="mistral", timeout=60: (None, "Ollama not available")
    analyze_trade_signal = lambda p, s, m="mistral": (None, "Ollama not available")

def call_ai_for_analysis(prompt, timeout=30):
    """Call AI analysis - uses Ollama (local) for privacy"""
    if OLLAMA_ENABLED:
        try:
            response, error = call_ollama(prompt, timeout=timeout)
            if response:
                return response, None
        except Exception as e:
            logger.debug(f"Ollama call error: {e}")
    
    # Fallback: Return generic analysis if Ollama unavailable
    logger.debug("ℹ️ Using rule-based analysis (Ollama unavailable)")
    return None, "Ollama not available"

# ==================== 1. AUTO BACKTEST ENGINE ====================

class AutoBacktestEngine:
    """Automated Backtesting Engine for SwingScalp Strategies"""
    
    def __init__(self, jarvis_system):
        self.jarvis = jarvis_system
        self.results = {}
        
    def run_backtest(self, historical_data, initial_balance=1000):
        """Run comprehensive backtest on historical data"""
        logger.info("🔄 Starting Auto Backtest Engine...")
        
        # Bypass trade manager checks (like session time) for backtesting
        original_can_trade = self.jarvis.trade_manager.can_trade
        self.jarvis.trade_manager.can_trade = lambda: True
        self.jarvis.is_backtest_mode = True  # Enable backtest mode for AI Gatekeeper
        
        try:
            balance = initial_balance
            trades = []
            winning_trades = 0
            total_trades = 0
            
            # Test different expiry periods
            expiry_periods = ['1M', '2M', '3M', '5M']
            expiry_results = {}
            
            for expiry in expiry_periods:
                expiry_balance = initial_balance
                expiry_trades = 0
                expiry_wins = 0
                
                # Simulate trading with this expiry
                for i in range(50, len(historical_data) - 5):
                    data_slice = historical_data.iloc[i-50:i]
                    
                    # Get trade signal
                    trade_result = self.jarvis.analyze_trade_setup(data_slice)
                    
                    # Safe timestamp extraction for logs
                    try:
                        current_time = data_slice.index[-1].strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        current_time = "Unknown Time"
                    
                    if trade_result['trade_signal']['direction'] != 'NO_TRADE':
                        signal = trade_result['trade_signal']['direction']
                        try:
                            conf_str = trade_result['trade_signal'].get('confidence_score', '0/100')
                            confidence = int(float(conf_str.split('/')[0]))
                        except (ValueError, IndexError, AttributeError):
                            confidence = 0
                        
                        # NEW: Use 60% threshold for backtest to only take high-probability setups
                        backtest_threshold = 60
                        
                        if confidence >= backtest_threshold:
                            # Print full signal for backtest
                            print(f"\n[BACKTEST: Trade Style: {expiry}] 🕒 Time: {current_time}")
                            try:
                                pro_display.display_full_signal(trade_result)
                            except Exception:
                                pass
                                
                            # Simulate trade outcome
                            # The AI analyzed data up to index i-1. The trade is entered exactly when candle i opens.
                            # So current_price is the OPEN of candle i (or CLOSE of i-1).
                            current_price = float(historical_data['close'].iloc[i-1])
                            
                            # For a 1-bar expiry, the trade closes at the end of candle i.
                            # So future_price is the CLOSE of candle i + expiry_bars - 1
                            expiry_bars = self._expiry_to_bars(expiry)
                            future_price = float(historical_data['close'].iloc[i + expiry_bars - 1])
                            
                            if signal == 'NO_TRADE' or signal == 'NEUTRAL':
                                print(f"⏭️ [TRADE SKIPPED] | Signal: {signal} (No clear direction)\n")
                            elif future_price == current_price:
                                print(f"➖ [TRADE BREAKEVEN] | Signal: {signal} | Entry: {current_price:.2f} | Exit: {future_price:.2f} | Profit: $0.00\n")
                                expiry_trades += 1
                            elif (signal == 'CALL' and future_price > current_price) or \
                               (signal == 'PUT' and future_price < current_price):
                                # Win
                                profit = initial_balance * 0.02
                                expiry_balance += profit  # 2% profit
                                expiry_wins += 1
                                print(f"✅ [TRADE WON] | Signal: {signal} | Entry: {current_price:.2f} | Exit: {future_price:.2f} | Profit: +${profit:.2f}\n")
                                expiry_trades += 1
                            else:
                                # Loss
                                loss = initial_balance * 0.01
                                expiry_balance -= loss  # 1% loss
                                print(f"❌ [TRADE LOST] | Signal: {signal} | Entry: {current_price:.2f} | Exit: {future_price:.2f} | Loss: -${loss:.2f}\n")
                                expiry_trades += 1
                        else:
                            print(f"[BACKTEST: Trade Style: {expiry}] 🕒 Time: {current_time}\n⚠️ SKIPPED: Confidence too low ({confidence}% < {backtest_threshold}% requirement for backtest).\n")
                    else:
                        print(f"[BACKTEST: Trade Style: {expiry}] 🕒 Time: {current_time}\n⚠️ SKIPPED: Signal was NEUTRAL / NO_TRADE.\n")
                
                
                if expiry_trades > 0:
                    win_rate = (expiry_wins / expiry_trades) * 100
                    expiry_results[expiry] = {
                        'win_rate': win_rate,
                        'total_trades': expiry_trades,
                        'final_balance': expiry_balance,
                        'profit_loss': expiry_balance - initial_balance
                    }
            
            # Find best expiry
            if expiry_results:
                trade_type = max(expiry_results.items(), key=lambda x: x[1]['win_rate'])
                
                self.results = {
                    'trade_type': trade_type[0],
                    'expiry_results': expiry_results,
                    'overall_win_rate': trade_type[1]['win_rate'],
                    'total_trades': sum(exp['total_trades'] for exp in expiry_results.values()),
                    'initial_balance': initial_balance,
                    'final_balance': trade_type[1]['final_balance']
                }
                logger.info(f"✅ Backtest Complete - Best Expiry: {trade_type[0]} | Win Rate: {trade_type[1]['win_rate']:.1f}%")
            else:
                logger.warning("⚠️ No trades met the criteria (>=85% confidence) during backtest.")
                self.results = {
                    'trade_type': '2m',
                    'expiry_results': {},
                    'overall_win_rate': 0.0,
                    'total_trades': 0,
                    'initial_balance': initial_balance,
                    'final_balance': initial_balance
                }
            return self.results
            
        except Exception as e:
            logger.error(f"Backtest error: {e}")
            return {'error': str(e)}
        finally:
            self.jarvis.trade_manager.can_trade = original_can_trade
            self.jarvis.is_backtest_mode = False  # Reset backtest mode for live trading

    def _expiry_to_bars(self, expiry):
        """Convert expiry time to number of bars"""
        expiry_map = {'1M': 1, '2M': 2, '3M': 3, '5M': 5}
        return expiry_map.get(expiry, 3)

    def generate_backtest_report(self):
        """Generate detailed backtest report"""
        if not self.results:
            return "No backtest results available"
            
        report = [
            "📊 AUTO BACKTEST ENGINE REPORT",
            "=" * 40,
            f"Best Expiry Period: {self.results['trade_type']}",
            f"Overall Win Rate: {self.results['overall_win_rate']:.1f}%",
            f"Total Trades Analyzed: {self.results['total_trades']}",
            f"Initial Balance: ${self.results['initial_balance']}",
            f"Final Balance: ${self.results['final_balance']:.2f}",
            f"Net P/L: ${self.results['final_balance'] - self.results['initial_balance']:.2f}",
            "",
            "Expiry Performance Breakdown:"
        ]
        
        for expiry, stats in self.results['expiry_results'].items():
            report.append(
                f"  {expiry}: {stats['win_rate']:.1f}% win rate | "
                f"{stats['total_trades']} trades | "
                f"P/L: ${stats['profit_loss']:.2f}"
            )
        
        return "\n".join(report)

# ==================== 2. AUTO TRAINING ENGINE ====================

class AutoTrainingEngine:
    """Automated ML Training Engine"""
    
    def __init__(self, jarvis_system):
        self.jarvis = jarvis_system
        self.models = {}
        self.training_history = {}
        
    def train_models(self, historical_data):
        """Train multiple ML models for signal prediction"""
        logger.info("🧠 Starting Auto Training Engine...")
        
        try:
            # Prepare training data
            X, y = self._prepare_training_data(historical_data)
            
            if len(X) == 0:
                logger.warning("Insufficient data for training")
                return {'status': 'insufficient_data'}
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Train Random Forest
            rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
            rf_model.fit(X_train, y_train)
            
            # Evaluate
            y_pred = rf_model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            
            self.models['random_forest'] = rf_model
            self.training_history['random_forest'] = {
                'accuracy': accuracy,
                'training_samples': len(X_train),
                'features_used': X.shape[1]
            }
            
            # Train simple neural network if torch is available
            if torch is not None:
                nn_model = self._train_neural_network(X_train, y_train, X_test, y_test)
                self.models['neural_network'] = nn_model
            
            logger.info(f"✅ Training Complete - Random Forest Accuracy: {accuracy:.1%}")
            
            return {
                'status': 'success',
                'models_trained': list(self.models.keys()),
                'accuracy': accuracy,
                'training_samples': len(X_train)
            }
            
        except Exception as e:
            logger.error(f"Training error: {e}")
            return {'status': 'error', 'error': str(e)}

    def _prepare_training_data(self, data):
        """Prepare features and labels for training"""
        features = []
        labels = []
        
        try:
            for i in range(60, len(data) - 5):
                # Create features from past data
                window = data.iloc[i-50:i]
                
                # Technical indicators as features
                feature_vector = [
                    float(window['close'].pct_change().mean() or 0),
                    float(window['close'].pct_change().std() or 0),
                    float(window['high'].max() - window['low'].min()),
                    float((window['close'] > window['open']).mean()),
                    float(window['volume'].mean() if 'volume' in window else 0),
                    float(window['close'].rolling(5).mean().iloc[-1]),
                    float(window['close'].rolling(10).mean().iloc[-1]),
                    float(window['close'].iloc[-1] - window['close'].rolling(20).mean().iloc[-1]),
                ]
                
                # Create label (1 if price goes up in next 3 bars, 0 if down)
                future_price = float(data['close'].iloc[i + 3])
                current_price = float(data['close'].iloc[i])
                label = 1 if future_price > current_price else 0
                
                features.append(feature_vector)
                labels.append(label)
            
            return np.array(features), np.array(labels)
            
        except Exception as e:
            logger.error(f"Feature preparation error: {e}")
            return np.array([]), np.array([])

    def _train_neural_network(self, X_train, y_train, X_test, y_test):
        """Train a simple neural network"""
        try:
            class SimpleNN(nn.Module):
                def __init__(self, input_size):
                    super(SimpleNN, self).__init__()
                    self.fc1 = nn.Linear(input_size, 64)
                    self.fc2 = nn.Linear(64, 32)
                    self.fc3 = nn.Linear(32, 2)
                    self.relu = nn.ReLU()
                    self.dropout = nn.Dropout(0.2)
                
                def forward(self, x):
                    x = self.relu(self.fc1(x))
                    x = self.dropout(x)
                    x = self.relu(self.fc2(x))
                    x = self.fc3(x)
                    return x
            
            model = SimpleNN(X_train.shape[1])
            criterion = nn.CrossEntropyLoss()
            optimizer = optim.Adam(model.parameters(), lr=0.001)
            
            # Convert to tensors
            X_train_tensor = torch.FloatTensor(X_train)
            y_train_tensor = torch.LongTensor(y_train)
            X_test_tensor = torch.FloatTensor(X_test)
            y_test_tensor = torch.LongTensor(y_test)
            
            # Training loop
            model.train()
            for epoch in range(100):
                optimizer.zero_grad()
                outputs = model(X_train_tensor)
                loss = criterion(outputs, y_train_tensor)
                loss.backward()
                optimizer.step()
            
            # Evaluate
            model.eval()
            with torch.no_grad():
                test_outputs = model(X_test_tensor)
                _, predicted = torch.max(test_outputs, 1)
                accuracy = (predicted == y_test_tensor).float().mean()
                
            self.training_history['neural_network'] = {
                'accuracy': accuracy.item(),
                'training_samples': len(X_train),
                'epochs': 100
            }
            
            return model
            
        except Exception as e:
            logger.error(f"Neural network training error: {e}")
            return None

    def predict_signal(self, data):
        """Use trained models to predict signals"""
        try:
            if 'random_forest' not in self.models:
                return 0
                
            # Prepare features for prediction
            feature_vector = self._prepare_features_for_prediction(data)
            if len(feature_vector) == 0:
                return 0
                
            prediction = self.models['random_forest'].predict([feature_vector])[0]
            return 1 if prediction == 1 else -1
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return 0

    def _prepare_features_for_prediction(self, data):
        """Prepare features for real-time prediction"""
        try:
            if len(data) < 50:
                return []
                
            window = data.tail(50)
            
            feature_vector = [
                float(window['close'].pct_change().mean() or 0),
                float(window['close'].pct_change().std() or 0),
                float(window['high'].max() - window['low'].min()),
                float((window['close'] > window['open']).mean()),
                float(window['volume'].mean() if 'volume' in window else 0),
                float(window['close'].rolling(5).mean().iloc[-1]),
                float(window['close'].rolling(10).mean().iloc[-1]),
                float(window['close'].iloc[-1] - window['close'].rolling(20).mean().iloc[-1]),
            ]
            
            return feature_vector
            
        except Exception as e:
            logger.error(f"Feature prediction error: {e}")
            return []

# ==================== 3. AUTO OPTIMIZER ENGINE ====================

class AutoOptimizerEngine:
    """Automated Parameter Optimization Engine"""
    
    def __init__(self, jarvis_system):
        self.jarvis = jarvis_system
        self.optimized_params = {}
        self.optimization_history = []
        
    def run_optimization(self, backtest_results, historical_data):
        """Run parameter optimization for trade trading"""
        logger.info("⚡ Starting Auto Optimizer Engine...")
        
        try:
            # Optimize confidence threshold
            confidence_thresholds = [80, 85, 90, 95]
            best_threshold = 85
            best_performance = 0
            
            for threshold in confidence_thresholds:
                performance = self._test_confidence_threshold(
                    threshold, historical_data
                )
                
                self.optimization_history.append({
                    'parameter': 'confidence_threshold',
                    'value': threshold,
                    'performance': performance
                })
                
                if performance > best_performance:
                    best_performance = performance
                    best_threshold = threshold
            
            # Optimize position sizing
            position_sizes = [1, 2, 3, 5]
            best_position_size = 2
            best_risk_return = 0
            
            for size in position_sizes:
                risk_return = self._test_position_size(size, historical_data)
                
                if risk_return > best_risk_return:
                    best_risk_return = risk_return
                    best_position_size = size
            
            # Optimize trading sessions
            best_sessions = self._optimize_trading_sessions(historical_data)
            
            self.optimized_params = {
                'confidence_threshold': best_threshold,
                'position_size_percent': best_position_size,
                'optimal_sessions': best_sessions,
                'max_daily_trades': 8,
                'cooldown_minutes': 3,
                'optimization_score': best_performance
            }
            
            logger.info(f"✅ Optimization Complete - Best Confidence: {best_threshold}%")
            
            return self.optimized_params
            
        except Exception as e:
            logger.error(f"Optimization error: {e}")
            return {'error': str(e)}

    def _test_confidence_threshold(self, threshold, data):
        """Test different confidence thresholds"""
        try:
            wins = 0
            total = 0
            
            for i in range(100, len(data) - 5):
                data_slice = data.iloc[i-50:i]
                trade_result = self.jarvis.analyze_trade_setup(data_slice)
                
                if trade_result['trade_signal']['direction'] != 'NO_TRADE':
                    try:
                        conf_str = trade_result['trade_signal'].get('confidence_score', '0/100')
                        confidence = int(float(conf_str.split('/')[0]))
                    except (ValueError, IndexError, AttributeError):
                        confidence = 0
                    
                    if confidence >= threshold:
                        # Check if trade would be successful
                        current_price = float(data['close'].iloc[i])
                        future_price = float(data['close'].iloc[i + 3])
                        signal = trade_result['trade_signal']['direction']
                        
                        if (signal == 'CALL' and future_price > current_price) or \
                           (signal == 'PUT' and future_price < current_price):
                            wins += 1
                        total += 1
            
            return wins / total if total > 0 else 0
            
        except Exception as e:
            logger.error(f"Threshold testing error: {e}")
            return 0

    def _test_position_size(self, size, data):
        """Test different position sizes"""
        # Simplified risk-return calculation
        base_return = 0.02  # 2% per win
        base_risk = 0.01   # 1% per loss
        
        # Larger positions = higher risk, higher return
        risk_adjusted_return = (base_return * size) - (base_risk * size * 0.5)
        return risk_adjusted_return

    def _optimize_trading_sessions(self, data):
        """Optimize which trading sessions to use"""
        session_performance = {}
        
        for session_name, session_times in TRADING_SESSIONS.items():
            # Count successful trades in this session
            success_count = 0
            total_count = 0
            
            for i in range(100, len(data) - 5):
                timestamp = data.iloc[i]['timestamp'] if 'timestamp' in data else None
                if timestamp:
                    hour = pd.to_datetime(timestamp).hour
                    
                    if session_times['start'] <= hour < session_times['end']:
                        data_slice = data.iloc[i-50:i]
                        trade_result = self.jarvis.analyze_trade_setup(data_slice)
                        
                        if trade_result['trade_signal']['direction'] != 'NO_TRADE':
                            # Check trade success
                            current_price = float(data['close'].iloc[i])
                            future_price = float(data['close'].iloc[i + 3])
                            signal = trade_result['trade_signal']['direction']
                            
                            if (signal == 'CALL' and future_price > current_price) or \
                               (signal == 'PUT' and future_price < current_price):
                                success_count += 1
                            total_count += 1
            
            if total_count > 0:
                session_performance[session_name] = success_count / total_count
            else:
                session_performance[session_name] = 0
        
        # Return sessions with performance > 50%
        optimal_sessions = [
            session for session, perf in session_performance.items() 
            if perf > 0.5
        ]
        
        return optimal_sessions if optimal_sessions else list(TRADING_SESSIONS.keys())

    def apply_optimized_params(self):
        """Apply optimized parameters to the trading system"""
        try:
            if self.optimized_params:
                # Update trade config
                # SAFETY: Enforce minimum floors — optimizer cannot disable risk controls
                TRADE_CONFIG['min_confidence_score'] = max(self.optimized_params['confidence_threshold'], 60)
                TRADE_CONFIG['position_size_percent'] = self.optimized_params['position_size_percent']
                TRADE_CONFIG['max_daily_trades'] = min(self.optimized_params['max_daily_trades'], 25)
                
                logger.info("✅ Optimized parameters applied to trading system")
                return True
            else:
                logger.warning("No optimized parameters to apply")
                return False
                
        except Exception as e:
            logger.error(f"Parameter application error: {e}")
            return False

# ==================== 4. LIVE TRADING ENGINE ====================

class DeltaWebSocketClient:
    """Live Delta WebSocket Client for Real-Time Data"""
    
    def __init__(self, callback):
        self.url = "wss://socket.delta.exchange"
        self.callback = callback
        self.is_running = False
        self.loop = None
        self.thread = None
        
    def start(self):
        """Start WebSocket listener in a separate thread"""
        pass # DISABLED: Using Unified Delta Hybrid Client in run_all_parts.py
        # self.is_running = True
        # self.thread = threading.Thread(target=self._run_loop, daemon=True)
        # self.thread.start()
        # print("DEBUG: WS Client START")
        # logger.info("📡 Delta WebSocket Client Initiated")
        
    def stop(self):
        """Stop WebSocket listener"""
        self.is_running = False
        
    def _run_loop(self):
        """Run asyncio loop for WebSocket"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._listen())
        except Exception as e:
            logger.error(f"WebSocket Loop Error: {e}")
            
    async def _listen(self):
        """Connect and listen to WebSocket stream"""
        while self.is_running:
            try:
                print(f"DEBUG: Connecting to {self.url}")
                async with websockets.connect(self.url) as ws:
                    print(f"DEBUG: Connected to {self.url}")
                    logger.info(f"✅ Connected to Delta Live Feed: {self.url}")
                    
                    while self.is_running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        
                        # Multi-stream format has 'stream' and 'data' fields
                        if 'data' in data:
                            stream_data = data['data']
                            stream_name = data.get('stream', '')
                            
                            if 'e' in stream_data and stream_data['e'] == 'kline':
                                k = stream_data['k']
                                
                                # Extract timeframe from stream name (e.g., "btcusdt@kline_1m" -> "1m")
                                timeframe = stream_name.split('_')[-1] if '_' in stream_name else '1m'
                                
                                # ONLY process completed candles
                                if k['x']:  # is_closed = True
                                    candle = {
                                        'timestamp': pd.to_datetime(k['t'], unit='ms'),
                                        'open': float(k['o']),
                                        'high': float(k['h']),
                                        'low': float(k['l']),
                                        'close': float(k['c']),
                                        'volume': float(k['v']),
                                        'number_of_trades': int(k.get('n', 0)),
                                        'taker_buy_volume': float(k.get('V', 0.0)),
                                        'timeframe': timeframe,
                                        'is_closed': True
                                    }
                                    self.callback(candle)
                            
            except Exception as e:
                logger.error(f"⚠️ WebSocket Connection Connection Lost ({e}). Reconnecting in 5s...")
                await asyncio.sleep(5)

class LiveTradingEngine:
    """Live Trading Engine with Paper Trading + Live Signals"""
    
    # Paper Trading Config
    PAPER_CONFIG = {
        'initial_balance': 1000.00,
        'risk_per_trade_pct': 0.02,      # 2% risk per trade
        'reward_ratio': 2.0,             # 2:1 reward
        'min_confidence': 60,            # Min confidence to open paper trade
        'max_open_trades': 3,
        # FIX: Realistic expiry times - SCALP needs 5min not 1min!
        'expiry_map': {'1M': 3, '2M': 5, '3M': 7, '5M': 10, 'SCALP': 5, 'DAY_TRADE': 15, 'SWING': 30},
        'save_file': 'paper_trades.json',
    }
    
    def __init__(self, jarvis_system, optimized_params=None):
        self.jarvis = jarvis_system
        self.optimized_params = optimized_params or {}
        self.is_running = False
        self.trade_queue = Queue()
        # BUG FIX #5: These attributes used in can_trade() / record_trade() but were never initialized
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.last_trade_time = None
        self.trade_history = []
        self.performance_stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'total_profit': 0,
            'current_streak': 0,
            'best_streak': 0
        }
        self.data_buffer = pd.DataFrame()
        self.ws_client = None
        self.candle_count = 0
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        
        # ═══ PAPER TRADING STATE ═══
        self.paper_balance = self.PAPER_CONFIG['initial_balance']
        self.paper_open_trades = []     # List of open paper trade dicts
        self.paper_closed_trades = []   # List of closed paper trade dicts
        self.paper_wins = 0
        self.paper_losses = 0
        self.paper_breakeven = 0
        self.paper_peak_balance = self.paper_balance
        self._load_paper_state()
        
    def _print_professional_signal(self, part_details):
        """Print signals in professional format"""
        self.candle_count += 1
        
        # Group signals
        bullish = [p for p, s in part_details.items() if s == 1 and p != 'part12_confidence']
        bearish = [p for p, s in part_details.items() if s == -1 and p != 'part12_confidence']
        neutral = [p for p, s in part_details.items() if s == 0 and p != 'part12_confidence']
        confidence = part_details.get('part12_confidence', 0)
        
        # Format part names
        def format_name(p):
            return p.replace('part', 'P').replace('_', ' ').title()

    # ═══════════════════════════════════════════════════════════════
    #  PAPER TRADE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    
    def _open_paper_trade(self, direction, entry_price, confidence, expiry_name, tp1, tp2, sl):
        """Open a new paper trade"""
        if len(self.paper_open_trades) >= self.PAPER_CONFIG['max_open_trades']:
            return None
        
        expiry_min = self.PAPER_CONFIG['expiry_map'].get(expiry_name, 3)
        trade = {
            'id': datetime.now().strftime('%H%M%S'),
            'direction': direction,
            'entry_price': entry_price,
            'confidence': confidence,
            'expiry_name': expiry_name,
            'tp1': tp1, 'tp2': tp2, 'sl': sl,
            'entry_time': datetime.now().isoformat(),
            'expiry_time': (datetime.now() + timedelta(minutes=expiry_min)).isoformat(),
            'exit_price': None,
            'result': None,
            'pnl_dollar': 0.0,
            'close_reason': None,
        }
        self.paper_open_trades.append(trade)
        return trade
    
    def _check_paper_trades(self, current_price):
        """Check all open paper trades for TP/SL/Expiry"""
        if not current_price or current_price < 100:
            return
        
        still_open = []
        newly_closed = []
        
        for trade in self.paper_open_trades:
            closed = False
            direction = trade['direction']
            entry = trade['entry_price']
            sl = trade.get('sl')
            tp1 = trade.get('tp1')
            expiry_dt = datetime.fromisoformat(trade['expiry_time'])
            
            # Check Stop Loss
            if sl and not closed:
                if (direction == 'CALL' and current_price <= sl) or \
                   (direction == 'PUT' and current_price >= sl):
                    trade['result'] = 'LOSS'
                    trade['close_reason'] = '🛑 Stop Loss Hit'
                    closed = True
            
            # Check Take Profit
            if tp1 and not closed:
                if (direction == 'CALL' and current_price >= tp1) or \
                   (direction == 'PUT' and current_price <= tp1):
                    trade['result'] = 'WIN'
                    trade['close_reason'] = '🎯 Take Profit Hit'
                    closed = True
            
            # Check Time Expiry
            if not closed and datetime.now() >= expiry_dt:
                if direction == 'CALL':
                    if current_price > entry:
                        trade['result'] = 'WIN'
                        trade['close_reason'] = '⏱️ Expiry - Price Up'
                    elif current_price < entry:
                        trade['result'] = 'LOSS'
                        trade['close_reason'] = '⏱️ Expiry - Price Down'
                    else:
                        trade['result'] = 'BREAKEVEN'
                        trade['close_reason'] = '⏱️ Expiry - Flat'
                else:  # PUT
                    if current_price < entry:
                        trade['result'] = 'WIN'
                        trade['close_reason'] = '⏱️ Expiry - Price Down'
                    elif current_price > entry:
                        trade['result'] = 'LOSS'
                        trade['close_reason'] = '⏱️ Expiry - Price Up'
                    else:
                        trade['result'] = 'BREAKEVEN'
                        trade['close_reason'] = '⏱️ Expiry - Flat'
                closed = True
            
            if closed:
                trade['exit_price'] = current_price
                risk_amt = self.paper_balance * self.PAPER_CONFIG['risk_per_trade_pct']
                
                if trade['result'] == 'WIN':
                    trade['pnl_dollar'] = risk_amt * self.PAPER_CONFIG['reward_ratio']
                    self.paper_balance += trade['pnl_dollar']
                    self.paper_wins += 1
                elif trade['result'] == 'LOSS':
                    trade['pnl_dollar'] = -risk_amt
                    self.paper_balance += trade['pnl_dollar']
                    self.paper_losses += 1
                else:
                    trade['pnl_dollar'] = 0
                    self.paper_breakeven += 1
                
                self.paper_peak_balance = max(self.paper_peak_balance, self.paper_balance)
                newly_closed.append(trade)
                self.paper_closed_trades.append(trade)
            else:
                still_open.append(trade)
        
        self.paper_open_trades = still_open
        
        # Print closed trade results
        for t in newly_closed:
            emoji = '✅' if t['result'] == 'WIN' else ('❌' if t['result'] == 'LOSS' else '➖')
            pnl_str = f"+${t['pnl_dollar']:.2f}" if t['pnl_dollar'] >= 0 else f"-${abs(t['pnl_dollar']):.2f}"
            print(f"\n{'═' * 60}")
            print(f"  {emoji} PAPER TRADE CLOSED - #{t['id']}")
            print(f"  {t['direction']} | Entry: ${t['entry_price']:,.2f} → Exit: ${t['exit_price']:,.2f}")
            print(f"  Result: {t['result']} | {t['close_reason']}")
            print(f"  P&L: {pnl_str} | 💰 Balance: ${self.paper_balance:,.2f}")
            print(f"{'═' * 60}")
        
        if newly_closed:
            self._save_paper_state()
    
    def _print_live_signal(self, result, current_price):
        """Print live signal in professional format"""
        signal = result.get('trade_signal', {})
        direction = signal.get('direction', 'NO_TRADE')
        
        try:
            conf_str = signal.get('confidence_score', '0/100')
            confidence = int(str(conf_str).split('/')[0])
        except (ValueError, IndexError):
            confidence = 0
        
        entry_price = signal.get('entry_price', current_price)
        tp1 = signal.get('take_profit_1')
        tp2 = signal.get('take_profit_2')
        sl = signal.get('stop_loss')
        expiry = signal.get('recommended_expiry', '3M')
        thoughts = result.get('intelligence_board', [])
        market_ctx = result.get('market_context', {})
        
        now = datetime.now().strftime('%H:%M:%S')
        
        print(f"\n{'─' * 60}")
        print(f"  ⏰ [{now}] LIVE SIGNAL | BTC: ${current_price:,.2f}" if current_price else f"  ⏰ [{now}] LIVE SIGNAL")
        print(f"{'─' * 60}")
        
        if direction == 'NO_TRADE':
            reason = result.get('no_trade_reason', 'No clear setup')
            print(f"  ⏸️  Signal: NO TRADE | Confidence: {confidence}%")
            print(f"  💭 Reason: {reason}")
            return direction, confidence, entry_price, tp1, tp2, sl, expiry
        
        emoji = "🟢" if direction == "CALL" else "🔴"
        print(f"  {emoji} Signal: {direction} | Confidence: {confidence}%")
        print(f"  💰 Entry: ${entry_price:,.2f}" if entry_price else "")
        if tp1: print(f"  🎯 TP1: ${tp1:,.2f}")
        if tp2: print(f"  🎯 TP2: ${tp2:,.2f}")
        if sl:  print(f"  🛑 SL:  ${sl:,.2f}")
        print(f"  ⏱️  Expiry: {expiry} | 📈 Vol: {market_ctx.get('volatility', 'N/A')}")
        
        if thoughts:
            print(f"  🧠 AI:")
            for t in thoughts[:3]:
                print(f"     → {str(t)[:75]}")
        
        return direction, confidence, entry_price, tp1, tp2, sl, expiry
    
    def _print_paper_dashboard(self):
        """Print paper trading dashboard"""
        total = self.paper_wins + self.paper_losses + self.paper_breakeven
        wr = (self.paper_wins / total * 100) if total > 0 else 0
        profit = self.paper_balance - self.PAPER_CONFIG['initial_balance']
        pct = (profit / self.PAPER_CONFIG['initial_balance']) * 100
        dd = ((self.paper_peak_balance - self.paper_balance) / self.paper_peak_balance * 100) if self.paper_peak_balance > 0 else 0
        
        print(f"\n{'━' * 60}")
        print(f"  📊 PAPER TRADING DASHBOARD")
        print(f"{'━' * 60}")
        print(f"  💰 Balance: ${self.paper_balance:,.2f} ({'+'if profit>=0 else ''}{pct:.1f}%)")
        print(f"  📈 P&L: {'+'if profit>=0 else ''}${profit:,.2f}")
        print(f"  🏆 Win Rate: {wr:.0f}% ({self.paper_wins}W / {self.paper_losses}L / {self.paper_breakeven}BE)")
        print(f"  📉 Drawdown: {dd:.1f}%")
        print(f"  📂 Open: {len(self.paper_open_trades)}")
        
        for t in self.paper_open_trades:
            exp_dt = datetime.fromisoformat(t['expiry_time'])
            rem = max(0, int((exp_dt - datetime.now()).total_seconds()))
            print(f"     → #{t['id']} {t['direction']} @ ${t['entry_price']:,.2f} | ⏱️ {rem}s")
        print(f"{'━' * 60}")
    
    def _save_paper_state(self):
        """Save paper trading state"""
        try:
            import json
            data = {
                'balance': self.paper_balance,
                'wins': self.paper_wins,
                'losses': self.paper_losses,
                'breakeven': self.paper_breakeven,
                'peak': self.paper_peak_balance,
                'closed_trades': self.paper_closed_trades[-100:],
            }
            with open(self.PAPER_CONFIG['save_file'], 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception:
            pass
    
    def _load_paper_state(self):
        """Load paper trading state from previous session"""
        try:
            import json
            import os
            if os.path.exists(self.PAPER_CONFIG['save_file']):
                with open(self.PAPER_CONFIG['save_file'], 'r') as f:
                    data = json.load(f)
                self.paper_balance = data.get('balance', self.PAPER_CONFIG['initial_balance'])
                self.paper_wins = data.get('wins', 0)
                self.paper_losses = data.get('losses', 0)
                self.paper_breakeven = data.get('breakeven', 0)
                self.paper_peak_balance = data.get('peak', self.paper_balance)
                self.paper_closed_trades = data.get('closed_trades', [])
                logger.info(f"📂 Paper state loaded: ${self.paper_balance:,.2f} ({self.paper_wins}W/{self.paper_losses}L)")
        except Exception:
            pass

    def start_live_trading(self):
        """Start the live trading loop with Paper Trading + Live Signals"""
        import pandas as pd
        import time
        
        self.is_running = True
        
        print(f"\n{'═' * 60}")
        print(f"  🚀 JARVIS LIVE ENGINE + PAPER TRADING")
        print(f"{'═' * 60}")
        print(f"  💰 Paper Balance: ${self.paper_balance:,.2f}")
        print(f"  📊 Min Confidence: {self.PAPER_CONFIG['min_confidence']}%")
        print(f"  🔄 Mode: PAPER (Fake Money) + LIVE SIGNALS")
        print(f"{'═' * 60}\n")
        
        cycle_count = [0]  # Use list for closure access
        
        def _live_loop():
            while self.is_running:
                try:
                    cycle_count[0] += 1
                    current_price = None
                    
                    # 1. Get current price for open trade checks
                    try:
                        if hasattr(self.jarvis, 'delta_data') and self.jarvis.delta_data:
                            cp = self.jarvis.delta_data.get_live_price("BTCUSDT")
                            if cp and float(cp) > 100:
                                current_price = float(cp)
                    except Exception:
                        pass
                    
                    # 2. Check open paper trades
                    if current_price:
                        self._check_paper_trades(current_price)
                    
                    # 3. Fetch live data for analysis
                    if hasattr(self.jarvis, 'delta_data') and self.jarvis.delta_data:
                        candles = self.jarvis.delta_data.get_historical_candles(
                            symbol="BTCUSDT", resolution="1m", limit=500
                        )
                        if candles:
                            df = pd.DataFrame(candles)
                            for col in ['open', 'high', 'low', 'close', 'volume']:
                                if col in df.columns:
                                    df[col] = pd.to_numeric(df[col], errors='coerce')
                            if 'time' in df.columns:
                                df.index = pd.to_datetime(df['time'], unit='s')
                                df = df.sort_index()
                                df = df.drop(columns=['time'], errors='ignore')
                            elif not isinstance(df.index, pd.DatetimeIndex):
                                df.index = pd.date_range(end=pd.Timestamp.now(), periods=len(df), freq='1min')
                            
                            if current_price is None and len(df) > 0:
                                current_price = float(df['close'].iloc[-1])
                            
                            # 4. Run full AI analysis
                            result = self.jarvis.analyze_trade_setup(df)
                            
                            # 5. Print live signal
                            direction, confidence, entry_price, tp1, tp2, sl, expiry = \
                                self._print_live_signal(result, current_price)
                            
                            # 6. Open paper trade if conditions met
                            if direction in ('CALL', 'PUT') and self.can_trade():
                                if confidence >= self.PAPER_CONFIG['min_confidence']:
                                    trade = self._open_paper_trade(
                                        direction, entry_price or current_price, 
                                        confidence, expiry, tp1, tp2, sl
                                    )
                                    if trade:
                                        risk_amt = self.paper_balance * self.PAPER_CONFIG['risk_per_trade_pct']
                                        print(f"\n  ✅ PAPER TRADE OPENED #{trade['id']}")
                                        print(f"     {direction} @ ${trade['entry_price']:,.2f} | Risk: ${risk_amt:.2f}")
                                        exp_dt = datetime.fromisoformat(trade['expiry_time'])
                                        print(f"     Expires: {exp_dt.strftime('%H:%M:%S')}")
                                    else:
                                        print(f"  ⚠️  Max open trades reached")
                                else:
                                    print(f"  ⚠️  PAPER: Skipped (Conf {confidence}% < {self.PAPER_CONFIG['min_confidence']}%)")
                                
                                self.record_trade(direction, confidence, 'PENDING')
                            
                        else:
                            logger.debug("[LIVE] No candle data received")
                    else:
                        logger.warning("[LIVE] No delta_data available")
                    
                    # 7. Dashboard every 5 cycles
                    if cycle_count[0] % 5 == 0:
                        self._print_paper_dashboard()
                    
                    time.sleep(60)  # Poll every 60 seconds (1 candle)
                    
                except Exception as e:
                    logger.error(f"[LIVE] Trading loop error: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(30)
        
        self.executor.submit(_live_loop)
        return {"status": "running", "mode": "paper_trading_live"}

    def can_trade(self):
        """Check if trading is allowed"""
        # Check daily limit
        if self.daily_trades >= TRADE_CONFIG['max_daily_trades']:
            logger.warning("Daily trade limit reached")
            return False
            
        # Check consecutive losses
        if self.consecutive_losses >= TRADE_CONFIG['consecutive_loss_limit']:
            logger.warning("Consecutive loss limit reached")
            return False
            
        # Check cooldown period
        if self.last_trade_time:
            time_since_last = (datetime.now() - self.last_trade_time).total_seconds() / 60
            if time_since_last < TRADE_CONFIG['trade_cooldown_minutes']:
                logger.warning(f"Trade cooldown active: {TRADE_CONFIG['trade_cooldown_minutes'] - time_since_last:.1f} minutes remaining")
                return False
                
        # Check session quality
        current_hour = datetime.now().hour
        session_quality = self._get_session_quality(current_hour)
        if session_quality == 'LOW':
            logger.warning("Low quality trading session - trading anyway")
            # return False
            
        return True
        
    def record_trade(self, signal, score, result):
        """Record trade outcome"""
        self.daily_trades += 1
        self.last_trade_time = datetime.now()
        
        trade_record = {
            'timestamp': datetime.now().isoformat(),
            'signal': signal,
            'score': score,
            'result': result,
            'session': self._get_current_session()
        }
        
        self.trade_history.append(trade_record)
        
        # Update consecutive losses
        if result == 'LOSS':
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            
    def reset_daily_stats(self):
        """Reset daily statistics"""
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.trade_history = []
        
    def _get_session_quality(self, current_hour):
        """Get current session quality"""
        for session, times in TRADING_SESSIONS.items():
            if times['start'] <= current_hour < times['end']:
                return times['quality']
        return 'LOW'
        
    def _get_current_session(self):
        """Get current trading session name"""
        current_hour = datetime.now().hour
        for session, times in TRADING_SESSIONS.items():
            if times['start'] <= current_hour < times['end']:
                return session
        return 'overnight'

# ==================== TRADE EXPIRY OPTIMIZER ====================

class TradeOptimizer:
    """Optimize trade style based on market conditions"""
    
    def __init__(self):
        self.trade_styles = ['SCALP', 'DAY_TRADE', 'SWING']
        
    def recommend_trade_type(self, score, volatility, pattern_type):
        """Recommend optimal trade style"""
        # Base style on score tier
        if score >= 90:
            base_style = 'SCALP'
        elif score >= 85:
            base_style = 'DAY_TRADE'
        else:
            base_style = 'SWING'
            
        # Adjust for volatility
        if volatility > 0.004:  # High volatility
            if base_style == 'SCALP':
                base_style = 'DAY_TRADE'
        elif volatility < 0.001:  # Low volatility
            if base_style == 'SWING':
                base_style = 'SCALP'
                
        # Adjust for pattern type
        if pattern_type == 'MOMENTUM_SCALP':
            base_style = 'SCALP'
        elif pattern_type == 'REJECTION_PLAY':
            base_style = 'DAY_TRADE'
        elif pattern_type == 'TREND_PULLBACK':
            base_style = 'SWING'
            
        return base_style
        
    def calculate_payout_ratio(self, score, trade_type):
        """Calculate Risk:Reward ratio"""
        rr_ratio = 1.5
        
        # Adjust for score
        if score >= 95:
            rr_ratio += 0.5
        elif score >= 90:
            rr_ratio += 0.3
        elif score >= 85:
            rr_ratio += 0.1
            
        # Adjust for trade type
        if trade_type == 'SWING':
            rr_ratio += 1.0
        elif trade_type == 'SCALP':
            rr_ratio -= 0.5
            
        return f"1:{rr_ratio:.1f}"

class ScalpingEngine:
    """Calculates TP, SL, and RR for regular scalping (Spot/Futures)"""
    def __init__(self):
        self.default_rr = 1.5

    def calculate_targets(self, data, direction, current_price, options_data=None, mtf_data=None):
        """Calculates TP/SL with Chart + Options Confluence"""
        try:
            if len(data) < 20: return None
            
            # 1. Base SL using ATR
            high_low = (data['high'] - data['low'])
            atr = high_low.rolling(14).mean().iloc[-1]
            
            # FIX: Cap ATR-based SL to max 0.4% of price for scalp realism
            max_sl_pct = 0.004  # 0.4%
            atr = min(atr, current_price * max_sl_pct / 1.8)
            sl_multiplier = 1.8
            
            # 2. Extract Options Walls
            # FIX: Default walls now 0.3%/0.5% away (not 5%)
            support_wall = options_data.get('support', current_price * 0.997) if options_data else current_price * 0.997
            resistance_wall = options_data.get('resistance', current_price * 1.003) if options_data else current_price * 1.003
            max_pain = options_data.get('max_pain', current_price) if options_data else current_price
            
            # 3. Handle Direction
            if direction == 'CALL':
                # SL should be below support wall or ATR-based SL
                sl_price = min(current_price - (atr * sl_multiplier), support_wall - (current_price * 0.001))
                
                # Targets (TP1: ATR-based, TP2: Options-based Magnet)
                risk = current_price - sl_price
                tp_price1 = current_price + (risk * 1.5)
                # TP2 is either Max Pain (Magnet) or Resistance Wall
                tp_price2 = max(tp_price1 * 1.01, max_pain if max_pain > current_price else resistance_wall)
                
                # FIX: Hard cap - TP1 max 0.8% above entry, SL max 0.4% below
                tp_price1 = min(tp_price1, current_price * 1.008)
                sl_price = max(sl_price, current_price * 0.996)
                tp_price2 = min(tp_price2, current_price * 1.015)
                
            else: # PUT
                # SL above resistance wall or ATR-based SL
                sl_price = max(current_price + (atr * sl_multiplier), resistance_wall + (current_price * 0.001))
                
                risk = sl_price - current_price
                tp_price1 = current_price - (risk * 1.5)
                # TP2 is either Max Pain or Support Wall
                tp_price2 = min(tp_price1 * 0.99, max_pain if max_pain < current_price else support_wall)
                
                # FIX: Hard cap - TP1 max 0.8% below entry, SL max 0.4% above
                tp_price1 = max(tp_price1, current_price * 0.992)
                sl_price = min(sl_price, current_price * 1.004)
                tp_price2 = max(tp_price2, current_price * 0.985)
            
            return {
                'entry': current_price,
                'stop_loss': round(sl_price, 2),
                'take_profit_1': round(tp_price1, 2),
                'take_profit_2': round(tp_price2, 2),
                'options_magnet': round(max_pain, 2)
            }
        except Exception as e:
            logger.error(f"Scalping targets error: {e}")
            return None

# ==================== EXISTING JARVIS CLASSES ====================

# ==================== EXTERNAL GPU ENGINE ADAPTERS ====================
# Replaces internal Parts with Institutional-Grade GPU Logic

def _sig_to_num(sig):
    """Convert GPU engine signal (string or number) to numeric -1/0/1"""
    if isinstance(sig, (int, float)):
        return 1 if sig > 0 else (-1 if sig < 0 else 0)
    if isinstance(sig, str):
        s = sig.upper()
        if s in ('CALL', 'BUY', 'BULLISH', 'LONG'): return 1
        if s in ('PUT', 'SELL', 'BEARISH', 'SHORT'): return -1
    return 0

def _df_to_market_data(df):
    """Convert pandas DataFrame to market_data dict expected by Part1 SmartBreakoutAI"""
    try:
        price_action = []
        for _, row in df.iterrows():
            price_action.append({
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row.get('volume', 0))
            })
        volume_pattern = [float(row.get('volume', 0)) for _, row in df.iterrows()]
        return {'price_action': price_action, 'volume_pattern': volume_pattern}
    except Exception:
        return {'price_action': [], 'volume_pattern': []}


class Part1Breakout:
    """Breakout Analysis — backed by SmartBreakoutAI (13 brains, Part1)"""
    def __init__(self):
        try:
            self._engine = SmartBreakoutAI() if SmartBreakoutAI else None
        except Exception:
            self._engine = None

    def analyze(self, data, context=None):
        # ── Try real Part1 engine (13-brain SmartBreakoutAI) ──────────────
        if self._engine is not None:
            try:
                market_data = _df_to_market_data(data)
                if len(market_data['price_action']) >= 20:
                    result = self._engine.analyze(market_data)
                    sig = result.get('signal', 0)
                    brk = result.get('breakout', {})
                    lvl = result.get('levels', {})
                    thought = (
                        f"P1-Engine: Breakout={'YES' if brk.get('breakout_detected') else 'NO'} "
                        f"dir={brk.get('direction',0)} str={brk.get('strength',0):.2f} "
                        f"conf={result.get('confidence',0):.1f}"
                    )
                    return {"signal": sig, "thought": thought, "telemetry": {
                        "breakout": brk, "levels": lvl, "momentum": result.get('momentum', {}),
                        "fakeout": result.get('fakeout', {}), "regime": result.get('regime', {})
                    }}
            except Exception as e:
                logger.debug(f"Part1 engine error: {e}")

        # ── Fallback: basic 20-bar breakout ───────────────────────────────
        try:
            if len(data) >= 20:
                current = float(data['close'].iloc[-1])
                high_20 = float(data['high'].tail(20).max())
                low_20  = float(data['low'].tail(20).min())
                prev    = float(data['close'].iloc[-2])
                if current > high_20 and prev <= high_20:
                    return {"signal": 1,  "thought": f"Bullish Breakout above {high_20:.0f} (fallback)"}
                elif current < low_20 and prev >= low_20:
                    return {"signal": -1, "thought": f"Bearish Breakdown below {low_20:.0f} (fallback)"}
        except Exception:
            pass
        return {"signal": 0, "thought": "No Breakout Pattern"}


class Part2Zone:
    """Supply/Demand Zone Analysis — backed by InstitutionalTradingEngineGPU (Part3)"""
    def analyze(self, data, context=None):
        # ── Try institutional engine zone signals from context ─────────────
        if context and 'institutional_components' in context:
            signals = context['institutional_components'].get('zone', [])
            if signals:
                s = sorted(signals, key=lambda x: abs(_sig_to_num(x.get('signal', 0))), reverse=True)[0]
                return {"signal": _sig_to_num(s.get('signal', 0)), "thought": f"Zone-Engine: {s.get('type')}"}

        # ── Fallback: proximity to 20-bar range extremes ───────────────────
        try:
            if len(data) < 20:
                return {"signal": 0, "thought": "Insufficient data"}
            current = float(data['close'].iloc[-1])
            high_20 = float(data['high'].tail(20).max())
            low_20  = float(data['low'].tail(20).min())
            rng     = high_20 - low_20
            if rng == 0:
                return {"signal": 0, "thought": "Flat market"}
            pct = (current - low_20) / rng   # 0=at support, 1=at resistance
            if pct >= 0.92:
                return {"signal": -1, "thought": f"Resistance Zone top {pct*100:.0f}% (fallback)"}
            elif pct <= 0.08:
                return {"signal": 1,  "thought": f"Support Zone bottom {pct*100:.0f}% (fallback)"}
        except Exception:
            pass
        return {"signal": 0, "thought": "No Zones (fallback)"}


class Part3Psychology:
    """Candle Psychology — backed by CandlePsychologyMasterGPU (Part3)"""
    def analyze(self, data, context=None):
        # ── Try institutional candle psychology from context ───────────────
        if context and 'institutional_components' in context:
            signals = context['institutional_components'].get('psychology', [])
            if signals and isinstance(signals, list):
                s = signals[-1] if isinstance(signals[-1], dict) else {}
                if s:
                    return {"signal": _sig_to_num(s.get('signal', 0)), "thought": f"Psych-Engine: {s.get('type')}"}

        # ── Fallback: multi-candle body/wick analysis ──────────────────────
        try:
            if len(data) < 3:
                return {"signal": 0, "thought": "Insufficient data"}
            scores = []
            for _, row in data.tail(3).iterrows():
                c, o = float(row['close']), float(row['open'])
                h, l = float(row['high']),  float(row['low'])
                body  = abs(c - o)
                total = h - l
                if total == 0:
                    continue
                body_ratio = body / total
                upper_wick = (h - max(c, o)) / total
                lower_wick = (min(c, o) - l) / total
                if body_ratio > 0.6:            # strong candle
                    scores.append(1 if c > o else -1)
                elif lower_wick > 0.4:          # bullish hammer
                    scores.append(1)
                elif upper_wick > 0.4:          # bearish shooting star
                    scores.append(-1)
            if scores:
                net = sum(scores)
                if net >= 2:  return {"signal": 1,  "thought": f"Bullish Psychology x{net} (fallback)"}
                if net <= -2: return {"signal": -1, "thought": f"Bearish Psychology x{abs(net)} (fallback)"}
        except Exception:
            pass
        return {"signal": 0, "thought": "Neutral Psychology (fallback)"}


class Part4Volume:
    """Volume Profile Analysis — backed by VolumeProfileBrainGPU (Part2)"""
    def analyze(self, data, context=None):
        # ── Try institutional volume from context ──────────────────────────
        if context and 'institutional_components' in context:
            signals = context['institutional_components'].get('volume', [])
            if signals and isinstance(signals, list) and len(signals) > 0:
                s = signals[-1] if isinstance(signals[-1], dict) else {}
                if s:
                    return {"signal": _sig_to_num(s.get('signal', 0)), "thought": f"Vol-Engine: {s.get('type')}"}

        # ── Fallback: multi-period volume analysis ─────────────────────────
        try:
            if len(data) < 20:
                return {"signal": 0, "thought": "Insufficient data"}
            vol5  = float(data['volume'].tail(5).mean())
            vol20 = float(data['volume'].tail(20).mean())
            if vol20 == 0:
                return {"signal": 0, "thought": "No volume"}
            vol_ratio = vol5 / vol20
            price_chg = (float(data['close'].iloc[-1]) - float(data['close'].iloc[-5])) / max(float(data['close'].iloc[-5]), 1)
            if vol_ratio > 1.8 and price_chg > 0.002:
                return {"signal": 1,  "thought": f"Strong Buy Volume {vol_ratio:.1f}x (fallback)"}
            elif vol_ratio > 1.8 and price_chg < -0.002:
                return {"signal": -1, "thought": f"Strong Sell Volume {vol_ratio:.1f}x (fallback)"}
            elif vol_ratio < 0.5:
                return {"signal": 0,  "thought": f"Low Volume {vol_ratio:.1f}x - caution (fallback)"}
        except Exception:
            pass
        return {"signal": 0, "thought": "Normal Volume (fallback)"}


class Part5ML:
    """ML Predictions — backed by NeuralNetworkManager (Part2)"""
    def analyze(self, data, context=None):
        # ── Try neural predictions from context ───────────────────────────
        if context and 'neural_prediction' in context:
            preds = context.get('neural_prediction')
            if preds and isinstance(preds, dict):
                try:
                    bullish = sum(1 for v in preds.values()
                                  if isinstance(v, (int, float)) and v > 0.5)
                    bearish = sum(1 for v in preds.values()
                                  if isinstance(v, (int, float)) and v < -0.5)
                    total = len(preds)
                    if total > 0:
                        if bullish / total > 0.6:
                            return {"signal": 1,  "thought": f"Neural-Engine: {bullish}/{total} Bullish"}
                        if bearish / total > 0.6:
                            return {"signal": -1, "thought": f"Neural-Engine: {bearish}/{total} Bearish"}
                except Exception:
                    pass

        # ── Fallback: RandomForest-style feature check ─────────────────────
        try:
            if len(data) >= 20:
                closes = data['close'].tail(20).astype(float).values
                ret1  = (closes[-1] - closes[-2]) / closes[-2]
                ret5  = (closes[-1] - closes[-5]) / closes[-5]
                ret20 = (closes[-1] - closes[0])  / closes[0]
                momentum_score = ret1 * 0.5 + ret5 * 0.3 + ret20 * 0.2
                if momentum_score > 0.003:
                    return {"signal": 1,  "thought": f"ML Momentum Bullish {momentum_score*100:.2f}% (fallback)"}
                elif momentum_score < -0.003:
                    return {"signal": -1, "thought": f"ML Momentum Bearish {momentum_score*100:.2f}% (fallback)"}
        except Exception:
            pass
        return {"signal": 0, "thought": "ML Neutral (fallback)"}


class Part6Trend:
    """Trend Analysis — backed by TrendAnalysisBrainGPU via Part1 TrendBrain"""
    def analyze(self, data, context=None):
        # ── Try institutional trend signals from context ───────────────────
        if context and 'institutional_components' in context:
            signals = context['institutional_components'].get('trend', [])
            if signals and isinstance(signals[-1], dict):
                s = signals[-1]
                return {"signal": _sig_to_num(s.get('signal', 0)), "thought": f"Trend-Engine: {s.get('type')}"}

        # ── Fallback: multi-EMA trend detection ───────────────────────────
        try:
            if len(data) >= 50:
                closes = data['close'].tail(50).astype(float)
                ema8   = closes.ewm(span=8).mean().iloc[-1]
                ema21  = closes.ewm(span=21).mean().iloc[-1]
                ema50  = closes.ewm(span=50).mean().iloc[-1]
                current = float(closes.iloc[-1])
                # Strong trend: price > ema8 > ema21 > ema50
                if current > ema8 > ema21 > ema50:
                    return {"signal": 1,  "thought": f"Strong Uptrend EMA8>{ema21:.0f}>{ema50:.0f} (fallback)"}
                elif current < ema8 < ema21 < ema50:
                    return {"signal": -1, "thought": f"Strong Downtrend EMA8<{ema21:.0f}<{ema50:.0f} (fallback)"}
                elif ema8 > ema21:
                    return {"signal": 1,  "thought": f"Mild Uptrend EMA8>{ema21:.0f} (fallback)"}
                elif ema8 < ema21:
                    return {"signal": -1, "thought": f"Mild Downtrend EMA8<{ema21:.0f} (fallback)"}
        except Exception:
            pass
        return {"signal": 0, "thought": "No Clear Trend (fallback)"}


class Part7Volatility:
    """Volatility/ATR Analysis — backed by VolatilityRegimeBrainGPU (Part2)"""
    def analyze(self, data, context=None):
        try:
            # ── Check regime from context ──────────────────────────────────
            regime = 'NEUTRAL'
            if context:
                regime = context.get('institutional_components', {}).get('regime', 'NEUTRAL')
            if 'VOLATILE' in str(regime):
                return {"signal": 0, "thought": f"High Volatility Regime ({regime}) — No trade"}

            # ── ATR-based regime detection ─────────────────────────────────
            if len(data) >= 14:
                highs  = data['high'].tail(14).astype(float)
                lows   = data['low'].tail(14).astype(float)
                closes = data['close'].tail(14).astype(float)
                tr     = (highs - lows).mean()
                atr_pct = tr / float(closes.iloc[-1])
                # High ATR = high vol = caution; Low ATR = trending
                if atr_pct > 0.015:   # > 1.5% per candle = very high vol
                    return {"signal": 0,  "thought": f"ATR Regime HIGH {atr_pct*100:.2f}% — no trade (fallback)"}
                price_chg = (float(closes.iloc[-1]) - float(closes.iloc[-10])) / float(closes.iloc[-10])
                if price_chg > 0.005:
                    return {"signal": 1,  "thought": f"Bullish Momentum ATR {atr_pct*100:.2f}% (fallback)"}
                elif price_chg < -0.005:
                    return {"signal": -1, "thought": f"Bearish Momentum ATR {atr_pct*100:.2f}% (fallback)"}
        except Exception:
            pass
        return {"signal": 0, "thought": "Stable Volatility (fallback)"}


class Part8Structure:
    """Market Structure — backed by MarketStructureBrainGPU (Part2) + PatternEngine (Part8)"""
    def analyze(self, data, context=None):
        try:
            if len(data) >= 30:
                highs = data['high'].tail(30).astype(float).values
                lows  = data['low'].tail(30).astype(float).values
                # Last 5 vs prior 10 bars
                recent_high  = max(highs[-5:])
                prior_high   = max(highs[-20:-5])
                recent_low   = min(lows[-5:])
                prior_low    = min(lows[-20:-5])
                # Double check with mid-section
                mid_high = max(highs[-15:-5])
                mid_low  = min(lows[-15:-5])

                if recent_high > prior_high and recent_low > prior_low:
                    return {"signal": 1,  "thought": "HH+HL Bullish Structure (Part8 engine)"}
                elif recent_high < prior_high and recent_low < prior_low:
                    return {"signal": -1, "thought": "LH+LL Bearish Structure (Part8 engine)"}
                elif recent_high > mid_high:
                    return {"signal": 1,  "thought": "Breaking structure UP (Part8 engine)"}
                elif recent_low < mid_low:
                    return {"signal": -1, "thought": "Breaking structure DOWN (Part8 engine)"}
        except Exception:
            pass
        return {"signal": 0, "thought": "No Clear Structure (fallback)"}


class Part9Orderflow:
    """Orderflow/Delta — backed by OrderFlowBrainGPU (Part2)"""
    def analyze(self, data, context=None):
        try:
            if len(data) >= 10:
                last10 = data.tail(10)
                closes  = last10['close'].astype(float)
                volumes = last10['volume'].astype(float)
                opens   = last10['open'].astype(float)
                # Approximate buy/sell volume per candle
                buy_vol  = float((volumes * (closes > opens)).sum())
                sell_vol = float((volumes * (closes < opens)).sum())
                total_vol = buy_vol + sell_vol
                if total_vol > 0:
                    buy_pct = buy_vol / total_vol
                    price_chg = (float(closes.iloc[-1]) - float(closes.iloc[0])) / max(float(closes.iloc[0]), 1)
                    # Divergence: price up but seller dominated
                    if price_chg > 0.002 and buy_pct < 0.35:
                        return {"signal": -1, "thought": f"Bearish Orderflow Div (buy={buy_pct*100:.0f}%, price+) (fallback)"}
                    elif price_chg < -0.002 and buy_pct > 0.65:
                        return {"signal": 1,  "thought": f"Bullish Orderflow Div (buy={buy_pct*100:.0f}%, price-) (fallback)"}
                    elif buy_pct > 0.65 and price_chg > 0:
                        return {"signal": 1,  "thought": f"Bullish Flow {buy_pct*100:.0f}% buys (fallback)"}
                    elif buy_pct < 0.35 and price_chg < 0:
                        return {"signal": -1, "thought": f"Bearish Flow {(1-buy_pct)*100:.0f}% sells (fallback)"}
        except Exception:
            pass
        return {"signal": 0, "thought": "No Clear Orderflow (fallback)"}


class Part10Candlestats:
    """Multi-candle Statistical Analysis — backed by PriceActionBrainGPU (Part2)"""
    def analyze(self, data, context=None):
        try:
            if len(data) >= 10:
                last10 = data.tail(10)
                bull_count = sum(1 for _, r in last10.iterrows() if float(r['close']) > float(r['open']))
                bear_count = 10 - bull_count
                # Candle run signal
                if bear_count >= 7:
                    return {"signal": -1, "thought": f"Bearish Candle Run {bear_count}/10 red (Part10)"}
                elif bull_count >= 7:
                    return {"signal": 1,  "thought": f"Bullish Candle Run {bull_count}/10 green (Part10)"}
                # Momentum via body size trend
                recent_bodies = [abs(float(r['close'])-float(r['open'])) for _, r in last10.tail(3).iterrows()]
                prior_bodies  = [abs(float(r['close'])-float(r['open'])) for _, r in last10.head(7).iterrows()]
                if prior_bodies:
                    body_accel = sum(recent_bodies)/3 / (sum(prior_bodies)/7 + 1e-8)
                    if body_accel > 1.5:
                        dir_sig = 1 if bull_count > bear_count else -1
                        return {"signal": dir_sig, "thought": f"Accelerating candle bodies {body_accel:.1f}x (Part10)"}
        except Exception:
            pass
        return {"signal": 0, "thought": "Mixed Candles (fallback)"}


class Part11Fusion:
    """Fusion — proportional voting across all active part results"""
    def analyze(self, part_results):
        buy_votes  = sum(1 for r in part_results if isinstance(r, dict) and r.get('signal', 0) > 0)
        sell_votes = sum(1 for r in part_results if isinstance(r, dict) and r.get('signal', 0) < 0)
        total_active = buy_votes + sell_votes
        if total_active == 0:
            return {"signal": 0, "thought": "No active votes"}
        buy_pct  = buy_votes  / total_active
        sell_pct = sell_votes / total_active
        if buy_pct >= 0.6:
            return {"signal": 1,  "thought": f"Fusion: {buy_votes} BUY vs {sell_votes} SELL ({buy_pct*100:.0f}% majority)"}
        elif sell_pct >= 0.6:
            return {"signal": -1, "thought": f"Fusion: {sell_votes} SELL vs {buy_votes} BUY ({sell_pct*100:.0f}% majority)"}
        return {"signal": 0, "thought": f"Fusion Split: {buy_votes} BUY vs {sell_votes} SELL (no majority)"}


class Part12Confidence:
    """Confidence Score — based on agreement strength across all parts"""
    def analyze(self, part_results):
        if not part_results:
            return {"confidence": 10}
        valid = [r for r in part_results if isinstance(r, dict)]
        total = len(valid)
        if total == 0:
            return {"confidence": 10}
        buy  = sum(1 for r in valid if r.get('signal', 0) > 0)
        sell = sum(1 for r in valid if r.get('signal', 0) < 0)
        majority    = max(buy, sell)
        agree_pct   = majority / total
        confidence  = int(agree_pct * 90)   # max 90 from parts alone
        # Penalise split decisions
        if buy > 0 and sell > 0:
            conflict_ratio = min(buy, sell) / max(buy, sell)
            confidence = int(confidence * (1 - conflict_ratio * 0.5))
        return {"confidence": max(10, min(90, confidence))}









class Part14OptionsChain:
    """Institutional Positioning Analysis - Prefers Delta, Fallbacks to Deribit"""
    def __init__(self, delta_client=None):
        self.delta_client = delta_client
        try:
            from deribit_options_client import DeribitOptionsClient
            # BUG FIX #3: Never hardcode credentials — load from env
            client_id = os.getenv("DERIBIT_CLIENT_ID", "")
            client_secret = os.getenv("DERIBIT_CLIENT_SECRET", "")
            self.deribit = DeribitOptionsClient(currency='BTC', client_id=client_id, client_secret=client_secret)
        except ImportError:
            self.deribit = None
        except Exception:
            self.deribit = None

        # Ollama Whale Tracker Cooldown setup
        self.last_ollama_time = 0
        self.ollama_cooldown = 300  # 5 minutes
        self.last_ollama_whale_tag = "WHALE_NEUTRAL"
        self.last_ollama_insight = "Institutional options positioning tracking."

    def _generate_ollama_options_prompt(self, telemetry: Dict, current_price: float) -> str:
        prompt = f"""You are an Elite Institutional Options Analyst. You track Smart Money and Whale positioning in the crypto options market.

Options Telemetry:
- Exchange Source: {telemetry.get('exchange', 'Unknown')}
- Current Price: ${current_price:.2f}
- Put/Call Ratio (PCR): {telemetry.get('pcr', 'N/A')}
- Max Pain Level: {telemetry.get('max_pain', 'N/A')}
- Call Resistance Wall: {telemetry.get('resistance_wall', 'N/A')}
- Put Support Wall: {telemetry.get('support_wall', 'N/A')}
- Math Bias Score: {telemetry.get('bias_score', 0)}

Task: Analyze if institutions (Whales) are accumulating long positions, setting up short hedges, or creating a retail trap (Bull Trap / Bear Trap).

Respond with EXACTLY ONE of the following tags at the start of your response:
- [WHALE_BULLISH] : Smart money is heavily buying calls / building support wall above current price.
- [WHALE_BEARISH] : Smart money is buying puts / strong call wall capping price upside.
- [RETAIL_TRAP] : High PCR divergence / Max Pain pin setup indicating a retail squeeze trap.

Follow the tag with a 1-sentence options analyst insight.
"""
        return prompt

    def analyze_options_with_ollama(self, telemetry: Dict, current_price: float) -> Tuple[str, str, int]:
        """Run Ollama Smart Money & Whale Tracker analysis with 5-minute cooldown"""
        now = time.time()
        if not OLLAMA_INTEGRATION_AVAILABLE:
            return self.last_ollama_whale_tag, self.last_ollama_insight, telemetry.get('signal', 0)

        if now - self.last_ollama_time < self.ollama_cooldown:
            ai_sig = 1 if self.last_ollama_whale_tag == "WHALE_BULLISH" else (-1 if self.last_ollama_whale_tag == "WHALE_BEARISH" else 0)
            return self.last_ollama_whale_tag, self.last_ollama_insight, ai_sig

        self.last_ollama_time = now
        try:
            prompt = self._generate_ollama_options_prompt(telemetry, current_price)
            response, err = call_ollama(prompt, timeout=60)
            if response and not err:
                raw_text = response.strip()
                if "[WHALE_BULLISH]" in raw_text.upper() or "WHALE_BULLISH" in raw_text.upper():
                    tag = "WHALE_BULLISH"
                elif "[WHALE_BEARISH]" in raw_text.upper() or "WHALE_BEARISH" in raw_text.upper():
                    tag = "WHALE_BEARISH"
                elif "[RETAIL_TRAP]" in raw_text.upper() or "RETAIL_TRAP" in raw_text.upper():
                    tag = "RETAIL_TRAP"
                else:
                    tag = "WHALE_NEUTRAL"

                self.last_ollama_whale_tag = tag
                self.last_ollama_insight = raw_text
                print(f"[PART 14 OLLAMA WHALE TRACKER] Tag: [{tag}] | {raw_text}")
            else:
                print(f"[PART 14 OLLAMA WHALE TRACKER] Ollama call skipped or unavailable: {err}")
        except Exception as e:
            logging.error(f"Ollama options tracker error: {e}")

        ai_sig = 1 if self.last_ollama_whale_tag == "WHALE_BULLISH" else (-1 if self.last_ollama_whale_tag == "WHALE_BEARISH" else 0)
        return self.last_ollama_whale_tag, self.last_ollama_insight, ai_sig

    def analyze(self, data, context=None):
        """Unified analysis for Options institutional walls and bias"""
        try:
            if data is None or 'close' not in data or len(data['close']) == 0:
                return {"signal": 0, "thought": "No price data available", "telemetry": {"signal": 0}}

            current_price = float(data['close'].iloc[-1])
            source = self.delta_client if self.delta_client else self.deribit
            if not source:
                return {"signal": 0, "thought": "No options source available", "telemetry": {"signal": 0, "exchange": "None"}}
            
            # Fetch specialized bias analysis
            try:
                if source == self.delta_client:
                    bias_data = source.get_institutional_bias('BTC')
                else:
                    bias_data = source.get_institutional_bias(current_price)
            except Exception as e:
                logging.warning(f"Options client API fetch warning: {e}")
                bias_data = {'bias': 'NEUTRAL', 'score': 0, 'reasons': [str(e)]}
            
            # Additional detailed analysis if available (Deribit specific)
            thoughts = []
            if hasattr(source, 'analyze_full_market'):
                try:
                    market = source.analyze_full_market(current_price)
                    if market and market.get('smart_money', {}).get('detected'):
                        thoughts.append(f"🐋 {market['smart_money']['details']}")
                except Exception:
                    pass
            
            # Add basic bias to thoughts
            thoughts.extend(bias_data.get('reasons', [])[:2])
            
            math_signal = 1 if bias_data.get('bias') == 'BULLISH' else (-1 if bias_data.get('bias') == 'BEARISH' else 0)
            
            # Extract safe floats for telemetry
            pcr_raw = bias_data.get('raw_data', {}).get('pcr')
            pcr_float = float(pcr_raw) if pcr_raw is not None and str(pcr_raw).replace('.', '', 1).isdigit() else None
            
            max_pain_raw = bias_data.get('max_pain') or bias_data.get('raw_data', {}).get('max_pain')
            max_pain_float = float(max_pain_raw) if max_pain_raw is not None and str(max_pain_raw).replace('.', '', 1).isdigit() else None

            telemetry = {
                "exchange": "Delta" if source == self.delta_client else "Deribit",
                "bias_score": float(bias_data.get('score', 0)),
                "pcr": pcr_float,
                "signal": math_signal,
                "support_wall": bias_data.get('support_wall') or bias_data.get('raw_data', {}).get('support'),
                "resistance_wall": bias_data.get('resistance_wall') or bias_data.get('raw_data', {}).get('resistance'),
                "max_pain": max_pain_float
            }

            # Ollama Smart Money & Whale Tracker Analysis
            whale_tag, insight, final_signal = self.analyze_options_with_ollama(telemetry, current_price)
            telemetry['ollama_whale_tag'] = whale_tag
            telemetry['ollama_insight'] = insight

            combined_thought = f"[{whale_tag}] " + (" | ".join(thoughts) if thoughts else f"Institutional: {bias_data.get('bias', 'NEUTRAL')}")
            
            return {
                "signal": final_signal if final_signal != 0 else math_signal,
                "thought": combined_thought,
                "telemetry": telemetry
            }
        except Exception as e:
            logging.error(f"Part14OptionsChain analyze error: {e}")
            return {"signal": 0, "thought": "Institutional error", "telemetry": {"error": str(e), "signal": 0}}

# FIX #6: Properly calling local Ollama (GPU) instead of Gemini cloud
def _call_ollama_local(prompt, model="phi3.5:3.8b", timeout=30):
    """Call local Ollama GPU model — uses OLLAMA_BASE_URL from .env"""
    import requests, os
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        resp = requests.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout
        )
        if resp.status_code == 200:
            return resp.json().get("response", ""), None
        return None, f"Ollama HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return None, "Ollama not reachable (is GPU server running?)"
    except Exception as e:
        return None, str(e)

class DeepSeekV3Brain:
    def __init__(self):
        self.model_name = "phi3.5:3.8b"  # FIX: Use local Ollama model
        self.enabled = True  # FIX: Always enabled via Ollama

    def analyze_sentiment(self, data, market_context):
        try:
            volatility = market_context.get('volatility', 'unknown')
            trend = market_context.get('trend', 'unknown')
            mood = market_context.get('mood', 'unknown')
            prompt = f"BTC sentiment: vol={volatility}, trend={trend}, mood={mood}. Score:-10to10,reason(10words)"
            content, err = _call_ollama_local(prompt, model=self.model_name)
            if err:
                return 0, f"ollama-err:{err}"
            score, reason = parse_score_from_text(content)
            if score > 3: return 1, reason
            if score < -3: return -1, reason
            return 0, reason
        except Exception as e:
            logger.debug("DeepSeekV3 error: %s", e)
            return 0, "error"

class DeepSeekR1ReasoningBrain:
    def __init__(self):
        self.model_name = "phi3.5:3.8b"  # FIX: Use local Ollama model
        self.enabled = True  # FIX: Always enabled via Ollama

    def complex_reasoning(self, all_signals, market_data, context):
        try:
            # Build signal summary for AI
            s = 0
            for v in all_signals.get('traditional_signals', {}).values():
                try:
                    s += int(v)
                except Exception: pass
            
            mood = context.get('mood', 'unknown')
            vol = context.get('volatility', 0)
            prompt = f"BTC sig_sum={s},mood={mood},vol={vol:.4f}. Reply: CALL/PUT/NO-TRADE,conf:1-10,reason(15words)"
            content, err = _call_ollama_local(prompt, model=self.model_name, timeout=45)
            if err:
                # Fallback to math-only signal
                signal = "CALL" if s>0 else ("PUT" if s<0 else "NO-TRADE")
                return {"signal": signal, "confidence": 5, "reasoning": f"Ollama offline, math fallback (sum={s})", "key_factors": []}
            low = (content or "").lower()
            if "call" in low and "put" not in low:
                sig = "CALL"
            elif "put" in low and "call" not in low:
                sig = "PUT"
            else:
                sig = "NO-TRADE"
            import re
            nums = re.findall(r"\d{1,2}", content or "")
            conf = int(nums[0]) if nums else 5
            conf = max(0, min(10, conf))
            return {"signal": sig, "confidence": conf, "reasoning": (content or '')[:300], "key_factors": []}
        except Exception as e:
            logger.debug("DeepSeekR1 error: %s", e)
            return {"signal": "NO-TRADE", "confidence": 0, "reasoning": "parse error"}

class QuantumV5:
    """
    Quantum Probability Simulator V5 - Dual Mode
    
    Mode 1: Independent (physics-only, no Parts influence)
    Mode 2: Validated (considers Parts context for smart validation)
    
    This prevents echo chamber while enabling conflict detection.
    """
    def __init__(self):
        self.num_paths = 128
    
    def simulate(self, data, parts_context=None):
        """
        Dual-mode quantum simulation
        
        Args:
            data: OHLCV DataFrame
            parts_context: Optional dict with Parts summary
                {
                    'consensus': 7/10,
                    'harmony_score': 78,
                    'strong_agreers': ['part4', 'part6'],
                    'conflicts': 2
                }
        
        Returns:
            Dict with independent + validated results (if context provided)
        """
        try:
            if len(data) < 10: 
                return {"signal": 0, "thought": "Gathering quantum paths...", "mode": "independent"}
            
            # STEP 1: ALWAYS calculate independent physics first
            independent_result = self._pure_physics_simulation(data)
            
            # STEP 2: If Parts context provided, validate
            if parts_context:
                validated_result = self._validate_with_parts(independent_result, parts_context)
                return validated_result
            else:
                # Backward compatible - return independent only
                return independent_result
                
        except Exception as e:
            return {"signal": 0, "thought": f"Quantum simulation offline: {e}", "mode": "error"}
    
    def _pure_physics_simulation(self, data):
        """Independent physics-only simulation (no Parts influence)"""
        current_price = float(data['close'].iloc[-1])
        
        # Calculate volatility
        volatility = float(data['close'].pct_change().std() or 0.0)
        
        # Calculate trend bias (momentum) with velocity extrapolation
        recent_prices = data['close'].tail(5).values
        # Trend: Simple % change
        trend = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
        # Velocity: Acceleration of trend (Phase 36)
        velocity = (recent_prices[-1] - recent_prices[-2]) / recent_prices[-2]
        extrapolated_drift = trend + (velocity * 0.5) # Weight towards current momentum
        
        # Generate quantum paths with trend bias (increased resolution)
        self.num_paths = 256 # Higher resolution (Phase 36)
        paths = np.random.normal(extrapolated_drift, volatility + 1e-12, self.num_paths)
        final_prices = current_price * (1 + paths)
        
        # Calculate bull ratio
        bull_ratio = np.sum(final_prices > current_price) / self.num_paths
        
        # Determine signal (Phase 39: Loosened Thresholds)
        # Original: 0.52/0.48 -> New: 0.505/0.495 (React to subtle drift)
        if bull_ratio > 0.505:
            signal = 1
            thought = f"QUANTUM (Physics): {bull_ratio*100:.1f}% paths UP | Drift: {extrapolated_drift*10000:.1f}bps"
        elif bull_ratio < 0.495:
            signal = -1
            thought = f"QUANTUM (Physics): {(1-bull_ratio)*100:.1f}% paths DOWN | Drift: {extrapolated_drift*10000:.1f}bps"
        else:
            signal = 0
            thought = f"QUANTUM (Physics): Balanced paths ({bull_ratio*100:.1f}% Bull) | Drift: {extrapolated_drift*10000:.1f}bps"
        
        return {
            'signal': signal,
            'thought': thought,
            'mode': 'independent',
            'bull_ratio': bull_ratio,
            'confidence': int(abs(bull_ratio - 0.5) * 200)  # 0-100%
        }
    
    def _validate_with_parts(self, physics_result, parts_context):
        """
        Validate independent physics with Parts context
        
        Returns enhanced result with validation and divergence detection
        """
        physics_signal = physics_result['signal']
        physics_confidence = physics_result['confidence']
        
        # Extract Parts consensus
        parts_ratio = parts_context.get('consensus', 0.5)  # 0-1 scale
        parts_signal = 1 if parts_ratio > 0.6 else (-1 if parts_ratio < 0.4 else 0)
        harmony = parts_context.get('harmony_score', 50)
        conflicts = parts_context.get('conflicts', 0)
        
        # Calculate divergence
        divergence = abs(physics_signal - parts_signal)
        
        # Validation logic
        if divergence == 0:
            # Physics and Parts AGREE
            boost = 15 if harmony > 70 else 10
            validated_confidence = min(100, physics_confidence + boost)
            validation_status = "ALIGNED"
            thought = f"⚛️ QUANTUM VALIDATED: Physics + Parts AGREE ({validated_confidence}%) | Harmony: {harmony}%"
            
        elif divergence == 1:
            # Minor disagreement (e.g., Physics Neutral, Parts Buy)
            # FORCE ALIGNMENT if Parts Consensus is Strong
            if harmony > 60 and abs(parts_ratio - 0.5) > 0.15:
                 physics_signal = parts_signal
                 validated_confidence = 85
                 validation_status = "FORCED_ALIGNMENT"
                 thought = f"⚛️ QUANTUM ALIGNED: Overriding Neutral Physics due to Strong Parts Consensus ({harmony}%)"
            else:
                 penalty = 5
                 validated_confidence = max(0, physics_confidence - penalty)
                 validation_status = "MINOR_CONFLICT"
                 thought = f"⚛️ QUANTUM CAUTION: Physics vs Parts minor conflict ({validated_confidence}%)"
            
        else:
            # Major conflict (opposite signals)
            penalty = 20
            validated_confidence = max(0, physics_confidence - penalty)
            validation_status = "MAJOR_CONFLICT"
            
            # Determine winner based on confidence
            if physics_confidence > 70 and harmony < 60:
                # Trust physics (high confidence, low Parts harmony)
                pass # physics wins
            elif harmony > 75:
                # Trust Parts (High harmony overrides physics)
                physics_signal = parts_signal
                validated_confidence = 80
                thought = f"⚛️ QUANTUM OVERRULED: Parts Harmony ({harmony}%) overrides Physics"
                validation_status = "PARTS_OVERRIDE"
            elif harmony > 80 and physics_confidence < 60:
                # Trust Parts (high harmony, low physics confidence)
                physics_signal = parts_signal
                thought = f"⚠️ PARTS OVERRIDE: Parts Harmony {harmony}% vs Physics {physics_confidence}% (Conflict!)"
                validation_status = "PARTS_OVERRIDE"
            else:
                # Major uncertainty - NO TRADE
                final_signal = 0
                thought = f"🚫 QUANTUM-PARTS CONFLICT: NO TRADE ({physics_confidence}% vs {int(parts_ratio*100)}%)"
        
        # Build validated result — use physics_signal (may have been overridden above)
        validated_result = {
            'signal': physics_signal,
            'thought': thought,
            'mode': 'validated',
            'confidence': validated_confidence,
            
            # Transparency data
            'independent': physics_result,
            'parts_consensus': parts_signal,
            'divergence': divergence,
            'validation_status': validation_status,
            'harmony_score': harmony,
            'conflicts_detected': conflicts
        }
        
        return validated_result

class SafetyRiskBrain:
    def analyze(self, data, signals):
        try:
            recent_change = abs(float(data['close'].iloc[-1]) - float(data['close'].iloc[-2])) / (float(data['close'].iloc[-2]) + 1e-12)
            if recent_change > 0.005: 
                return {"approved": False, "thought": f"SAFETY: Sudden spike detected ({recent_change*100:.2f}%) - Market too unstable"}
            return {"approved": True, "thought": "SAFETY: Volatility within safe execution bounds"}
        except Exception:
            return {"approved": True, "thought": "Safety check bypassed"}

class VolumePressureBrain:
    def analyze(self, data):
        try:
            if len(data) < 20: return {"signal": 0, "thought": "VOL-PRESSURE: Insufficient volume history"}
            volume_sma = data['volume'].rolling(20).mean().iloc[-1]
            current_volume = float(data['volume'].iloc[-1])
            if volume_sma == 0: return {"signal": 0, "thought": "Neutral volume"}
            if current_volume > volume_sma * 1.3:
                price_change = (float(data['close'].iloc[-1]) - float(data['close'].iloc[-2])) / (float(data['close'].iloc[-2]) + 1e-12)
                side = "Buying" if price_change > 0 else "Selling"
                return {"signal": 1 if price_change > 0 else -1, "thought": f"VOL-PRESSURE: Aggressive {side} burst detected ({current_volume/volume_sma:.1f}x SMA)"}
            return {"signal": 0, "thought": "VOL-PRESSURE: Normal institutional flow"}
        except Exception:
            return {"signal": 0, "thought": "Volume analysis failure"}

class TrendAccelerationBrain:
    def analyze(self, data):
        try:
            if len(data) < 10: return {"signal": 0, "thought": "ACCEL: Trend warming up"}
            sma_5 = data['close'].rolling(5).mean()
            sma_10 = data['close'].rolling(10).mean()
            accel_5 = sma_5.diff().iloc[-1]
            accel_10 = sma_10.diff().iloc[-1]
            if accel_5 > 0 and accel_10 > 0: 
                return {"signal": 1, "thought": "ACCEL: Bullish momentum accelerating (Dual SMA shift)"}
            if accel_5 < 0 and accel_10 < 0: 
                return {"signal": -1, "thought": "ACCEL: Bearish momentum accelerating (Dual SMA shift)"}
            return {"signal": 0, "thought": "ACCEL: Trend velocity is stalling"}
        except Exception:
            return {"signal": 0, "thought": "Acceleration check skipped"}

class RiskFilterBrain:
    def analyze(self, data, signal):
        try:
            if len(data) < 5: return {"approved": True, "thought": "RISK: Entry phase"}
            max_drawdown = (data['close'].rolling(5).max() - data['close']).iloc[-1] / (data['close'].iloc[-1] + 1e-12)
            if max_drawdown > 0.01 and signal > 0:
                return {"approved": False, "thought": f"RISK: Excessive Drawdown ({max_drawdown*100:.2f}%) inhibits long entry"}
            return {"approved": True, "thought": "RISK: Exposure remains within limits"}
        except Exception:
            return {"approved": True, "thought": "Risk filter bypassed"}

class MarketMoodEngine:
    def detect_mood(self, data):
        """Analyze market condition and predict Daily Bias"""
        try:
            if len(data) < 20: return "NEUTRAL (Insufficient Data)"
            
            # 1. Volatility Analysis
            volatility = float(data['close'].pct_change().std() or 0.0)
            
            # 2. Trend Strength (ADX-like proxy)
            trend_strength = abs(float(data['close'].diff().tail(10).mean()) / (float(data['close'].iloc[-1]) + 1e-12))
            
            # 3. Volume Delta Analysis (Buying vs Selling Pressure)
            delta_bias = "NEUTRAL"
            if 'taker_buy_volume' in data.columns:
                recent_buy = data['taker_buy_volume'].tail(10).sum()
                recent_total = data['volume'].tail(10).sum()
                buy_ratio = recent_buy / (recent_total + 1e-12)
                if buy_ratio > 0.55: delta_bias = "BULLISH"
                elif buy_ratio < 0.45: delta_bias = "BEARISH"
            
            # Combine Factors for Prediction
            if volatility > 0.004:
                return f"VOLATILE ({delta_bias} Bias) - Caution"
            
            if trend_strength > 0.0015:
                # Strong Trend
                direction = "UP" if data['close'].iloc[-1] > data['close'].iloc[-20] else "DOWN"
                return f"TRENDING {direction} (Strong {delta_bias} Flow)"
                
            if volatility < 0.001:
                return "RANGING / CHOPPY (Wait for Breakout)"
                
            return f"NORMAL ({delta_bias} Lean)"
        except Exception:
            return "NEUTRAL"

class HighVolatilityRegimeShield:
    def check_safety(self, data):
        try:
            if len(data) < 10: return {"approved": True, "thought": "SHIELD: Scanning volatility..."}
            volatility = float(data['close'].pct_change().std() or 0.0)
            if volatility > 0.005:
                return {"approved": False, "thought": f"SHIELD: High-Vol Regime ({volatility*100:.2f}%) - Trades prohibited"}
            return {"approved": True, "thought": "SHIELD: Stability confirmed"}
        except Exception:
            return {"approved": True, "thought": "Shield inactive"}

class ReverseSafetyEngine:
    def check_reversal(self, data, original_signal):
        try:
            if len(data) < 3: return {"signal": original_signal, "thought": "No reversal data"}
            recent_candle = data.iloc[-1]
            wick_upper = float(recent_candle['high'] - max(recent_candle['open'], recent_candle['close']))
            wick_lower = float(min(recent_candle['open'], recent_candle['close']) - recent_candle['low'])
            body = abs(float(recent_candle['close'] - recent_candle['open']))
            
            if wick_upper > body * 2 and original_signal == 1:
                return {"signal": -1, "thought": "REVERSAL: Significant bearish wick - Forcing PUT"}
            if wick_lower > body * 2 and original_signal == -1:
                return {"signal": 1, "thought": "REVERSAL: Significant bullish wick - Forcing CALL"}
                
            return {"signal": original_signal, "thought": "No reversal patterns detected"}
        except Exception:
            return {"signal": original_signal, "thought": "Reversal engine error"}

class TrapCandleGenomeDetector:
    def detect_trap(self, data):
        try:
            if len(data) < 2: return {"is_trap": False, "thought": "Scanning for traps..."}
            current = data.iloc[-1]
            prev = data.iloc[-2]
            current_body = abs(float(current['close'] - current['open']))
            current_range = float(current['high'] - current['low'])
            if current_range == 0: return {"is_trap": False, "thought": "Static price"}
            body_ratio = current_body / current_range
            
            if body_ratio < 0.3 and current['high'] > prev['high'] and current['close'] < prev['close']:
                return {"is_trap": True, "thought": "TRAP: Bull trap detected (High wick + lower close)"}
            if body_ratio < 0.3 and current['low'] < prev['low'] and current['close'] > prev['close']:
                return {"is_trap": True, "thought": "TRAP: Bear trap detected (Low wick + higher close)"}
            return {"is_trap": False, "thought": "No genome-level traps detected"}
        except Exception:
            return {"is_trap": False, "thought": "Trap detector error"}

def parse_score_from_text(text):
    """Robustly parse a numeric sentiment score from free-text responses between -10 and 10."""
    try:
        if not text:
            return 0, "no text"
        import re
        nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", text)
        for n in nums:
            try:
                v = float(n)
                if -1000 < v < 1000:
                    return max(-10, min(10, v)), "parsed"
            except Exception:
                continue
        low = text.lower()
        if "bull" in low or "buy" in low or "positive" in low:
            return 5, "heuristic"
        if "bear" in low or "sell" in low or "negative" in low:
            return -5, "heuristic"
        return 0, "none"
    except Exception as e:
        return 0, f"error:{e}"

class DeepMTFAnalyzer:
    """Deep Multi-Timeframe Analysis Engine (1m, 5m, 15m)"""
    def __init__(self, parts):
        self.parts = parts
        
    def analyze_all_timeframes(self, mtf_buffers):
        """Universal Multi-Timeframe Analysis (1m to 4h)"""
        results = {}
        try:
            # Active timeframes to check
            target_tfs = ['5m', '15m', '30m', '1h', '2h', '4h']
            
            for tf in target_tfs:
                df = mtf_buffers.get(tf)
                if df is None or len(df) < 20: continue
                
                # Run core "Perspective" parts on higher timeframe data
                t_res = self.parts['part6_trend'].analyze(df)
                s_res = self.parts['part8_structure'].analyze(df)
                v_res = self.parts['part4_volume'].analyze(df)
                c_res = self.parts['part10_candlestats'].analyze(df)
                
                # Extract signals (handle both dict and raw int)
                t_sig = t_res.get('signal', 0) if isinstance(t_res, dict) else t_res
                s_sig = s_res.get('signal', 0) if isinstance(s_res, dict) else s_res
                v_sig = v_res.get('signal', 0) if isinstance(v_res, dict) else v_res
                c_sig = c_res.get('signal', 0) if isinstance(c_res, dict) else c_res
                
                # Consensus for this timeframe
                score = t_sig + s_sig + v_sig + c_sig
                direction = 1 if score >= 2 else (-1 if score <= -2 else 0)
                
                results[tf] = {
                    'direction': direction,
                    'score': score,
                    'is_strong': abs(score) >= 3,
                    'thoughts': {
                        'trend': t_res.get('thought', '') if isinstance(t_res, dict) else str(t_res),
                        'structure': s_res.get('thought', '') if isinstance(s_res, dict) else str(s_res),
                        'candles': c_res.get('thought', '') if isinstance(c_res, dict) else str(c_res)
                    }
                }
            return results
        except Exception as e:
            logger.error(f"Universal MTF error: {e}")
            return {}

# ==================== TRADE SCORING MATRIX ====================

class TradeScoringMatrix:
    """SwingScalp-specific scoring system (0-100 points)"""
    
    def __init__(self):
        self.minimum_trade_score = 0
        self.score_weights = {
            'immediate_momentum': 20,
            'micro_sr_reaction': 15, 
            'trend_micro_alignment': 15,
            'volume_confirmation': 10,
            'candle_pattern': 10,
            'entry_timing_precision': 15,
            'trap_avoidance': 10,
            'session_strength': 5
        }
    
    def calculate_trade_score(self, data, current_price, context):
        """Calculate 0-100 trade trading score"""
        try:
            scores = {}
            
            # 1. IMMEDIATE MOMENTUM (0-20)
            scores['immediate_momentum'] = self._score_immediate_momentum(data)
            
            # 2. MICRO SUPPORT/RESISTANCE REACTION (0-15)
            scores['micro_sr_reaction'] = self._score_micro_sr_reaction(data, current_price)
            
            # 3. TREND MICRO ALIGNMENT (0-15)
            scores['trend_micro_alignment'] = self._score_trend_micro_alignment(data)
            
            # 4. VOLUME CONFIRMATION (0-10)
            scores['volume_confirmation'] = self._score_volume_confirmation(data)
            
            # 5. CANDLE PATTERN (0-10)
            scores['candle_pattern'] = self._score_candle_pattern(data)
            
            # 6. ENTRY TIMING PRECISION (0-15)
            scores['entry_timing_precision'] = self._score_entry_timing(data, context)
            
            # 7. TRAP AVOIDANCE (0-10)
            scores['trap_avoidance'] = self._score_trap_avoidance(data)
            
            # 8. SESSION STRENGTH (0-5)
            scores['session_strength'] = self._score_session_strength()
            
            # Calculate weighted total
            total_score = 0
            for key, weight in self.score_weights.items():
                total_score += scores.get(key, 0) * (weight / 100)
            
            return min(100, total_score), scores
            
        except Exception as e:
            logger.error(f"SwingScalp scoring error: {e}")
            return 0, {}

    def _score_immediate_momentum(self, data):
        """Score immediate momentum strength (0-20)"""
        try:
            if len(data) < 3:
                return 0
                
            current_candle = data.iloc[-1]
            prev_candle = data.iloc[-2]
            
            # Calculate momentum strength
            body_size = abs(float(current_candle['close']) - float(current_candle['open']))
            candle_range = float(current_candle['high']) - float(current_candle['low'])
            
            if candle_range == 0:
                return 0
                
            body_ratio = body_size / candle_range
            
            # Strong momentum: large body, small wicks
            if body_ratio > 0.7:
                score = 18
            elif body_ratio > 0.5:
                score = 14
            elif body_ratio > 0.3:
                score = 8
            else:
                score = 3
                
            # Direction consistency
            if len(data) >= 5:
                recent_trend = self._get_micro_trend(data)
                current_direction = 1 if current_candle['close'] > current_candle['open'] else -1
                if recent_trend == current_direction:
                    score += 2
                    
            return min(20, score)
            
        except Exception:
            return 0

    def _score_micro_sr_reaction(self, data, current_price):
        """Score reaction at micro support/resistance (0-15)"""
        try:
            if len(data) < 10:
                return 0
                
            # Find recent swing points
            highs = data['high'].tail(10)
            lows = data['low'].tail(10)
            
            resistance_level = float(highs.max())
            support_level = float(lows.min())
            
            price_range = resistance_level - support_level
            if price_range == 0:
                return 0
                
            # Calculate distance to nearest key level
            dist_to_resistance = abs(current_price - resistance_level) / price_range
            dist_to_support = abs(current_price - support_level) / price_range
            min_distance = min(dist_to_resistance, dist_to_support)
            
            # Score based on proximity to key levels
            if min_distance < 0.05:  # Very close to key level
                score = 12
            elif min_distance < 0.1:  # Close to key level
                score = 8
            elif min_distance < 0.15:  # Moderate distance
                score = 5
            else:
                score = 2
                
            # Bonus for rejection patterns
            current_candle = data.iloc[-1]
            if self._is_rejection_candle(current_candle):
                score += 3
                
            return min(15, score)
            
        except Exception:
            return 0

    def _score_trend_micro_alignment(self, data):
        """Score micro-trend alignment (0-15)"""
        try:
            if len(data) < 8:
                return 0
                
            # Multiple timeframe alignment
            trend_1m = self._get_micro_trend(data.tail(5))  # 1min trend
            trend_3m = self._get_micro_trend(data.tail(15))  # 3min trend
            trend_5m = self._get_micro_trend(data.tail(25))  # 5min trend
            
            alignment_score = 0
            if trend_1m == trend_3m == trend_5m:
                alignment_score = 12  # Perfect alignment
            elif trend_1m == trend_3m:
                alignment_score = 8   # Good alignment
            elif trend_1m == trend_5m:
                alignment_score = 6   # Moderate alignment
            else:
                alignment_score = 2   # Poor alignment
                
            # Trend strength bonus
            trend_strength = self._calculate_trend_strength(data.tail(10))
            if trend_strength > 0.001:
                alignment_score += 3
                
            return min(15, alignment_score)
            
        except Exception:
            return 0

    def _score_volume_confirmation(self, data):
        """Score volume confirmation (0-10)"""
        try:
            if 'volume' not in data.columns or len(data) < 20:
                return 5  # Neutral if no volume data
                
            current_volume = float(data['volume'].iloc[-1])
            avg_volume = float(data['volume'].tail(20).mean())
            
            if avg_volume == 0:
                return 5
                
            volume_ratio = current_volume / avg_volume
            
            current_candle = data.iloc[-1]
            price_direction = 1 if current_candle['close'] > current_candle['open'] else -1
            
            # Volume confirmation logic
            if volume_ratio > 1.5:  # High volume
                # BUG FIX #16: Both directions scored 9 — bullish vol should score higher than bearish
                if price_direction == 1:
                    score = 9   # Bullish volume confirmation
                else:
                    score = 7   # Bearish — high vol on down move = distribution, lower score for CALL bias
            elif volume_ratio > 1.2:  # Above average volume
                score = 7
            elif volume_ratio > 0.8:  # Average volume
                score = 5
            else:  # Low volume
                score = 3
                
            return min(10, score)
            
        except Exception:
            return 5

    def _score_candle_pattern(self, data):
        """Score trade-specific candle patterns (0-10)"""
        try:
            if len(data) < 3:
                return 0
                
            current_candle = data.iloc[-1]
            prev_candle = data.iloc[-2]
            
            score = 0
            
            # Bullish patterns
            if self._is_bullish_engulfing(data):
                score += 8
            if self._is_hammer(current_candle):
                score += 7
            if self._is_morning_star(data):
                score += 9
                
            # Bearish patterns  
            if self._is_bearish_engulfing(data):
                score += 8
            if self._is_shooting_star(current_candle):
                score += 7
            if self._is_evening_star(data):
                score += 9
                
            # No strong pattern
            if score == 0:
                score = 3
                
            return min(10, score)
            
        except Exception:
            return 0

    def _score_entry_timing(self, data, context):
        """Score entry timing precision (0-15)"""
        try:
            score = 5  # Base score
            
            # Market session timing
            current_hour = datetime.now().hour
            session_quality = self._get_current_session_quality(current_hour)
            if session_quality == 'BEST':
                score += 4
            elif session_quality == 'HIGH':
                score += 3
            elif session_quality == 'MEDIUM':
                score += 1
                
            # Volatility timing
            volatility = float(data['close'].pct_change().std() or 0.0)
            if 0.001 < volatility < 0.004:  # Ideal volatility range
                score += 3
            elif volatility > 0.006:  # Too volatile
                score -= 2
                
            # News timing (simplified - would integrate with news API)
            score += 2  # Assume no major news
            
            return min(15, max(0, score))
            
        except Exception:
            return 5

    def _score_trap_avoidance(self, data):
        """Score trap pattern avoidance (0-10)"""
        try:
            score = 8  # Start with high score
            
            # Check for false breakouts
            if self._is_false_breakout(data):
                score -= 6
                
            # Check for doji indecision
            if self._is_doji_candle(data.iloc[-1]):
                score -= 3
                
            # Check for inside bar compression
            if self._is_inside_bar(data):
                score -= 2
                
            return min(10, max(0, score))
            
        except Exception:
            return 5

    def _score_session_strength(self):
        """Score trading session strength (0-5)"""
        try:
            current_hour = datetime.now().hour
            session_quality = self._get_current_session_quality(current_hour)
            
            if session_quality == 'BEST':
                return 5
            elif session_quality == 'HIGH':
                return 4
            elif session_quality == 'MEDIUM':
                return 3
            else:
                return 1
        except Exception:
            return 2

    # ==================== PATTERN DETECTION METHODS ====================

    def _get_micro_trend(self, data):
        """Get micro trend direction (1: up, -1: down, 0: neutral)"""
        if len(data) < 2:
            return 0
        price_change = float(data['close'].iloc[-1]) - float(data['close'].iloc[0])
        if abs(price_change) < 0.0001:
            return 0
        return 1 if price_change > 0 else -1

    def _calculate_trend_strength(self, data):
        """Calculate trend strength as percentage"""
        if len(data) < 2:
            return 0
        start_price = float(data['close'].iloc[0])
        end_price = float(data['close'].iloc[-1])
        return abs(end_price - start_price) / start_price

    def _is_rejection_candle(self, candle):
        """Check if candle shows rejection"""
        body = abs(float(candle['close']) - float(candle['open']))
        upper_wick = float(candle['high']) - max(float(candle['open']), float(candle['close']))
        lower_wick = min(float(candle['open']), float(candle['close'])) - float(candle['low'])
        
        if body == 0:
            return False
            
        upper_ratio = upper_wick / body
        lower_ratio = lower_wick / body
        
        return upper_ratio > 2 or lower_ratio > 2

    def _is_bullish_engulfing(self, data):
        """Check for bullish engulfing pattern"""
        if len(data) < 2:
            return False
            
        current = data.iloc[-1]
        prev = data.iloc[-2]
        
        return (float(current['close']) > float(current['open']) and
                float(prev['close']) < float(prev['open']) and
                float(current['open']) < float(prev['close']) and
                float(current['close']) > float(prev['open']))

    def _is_bearish_engulfing(self, data):
        """Check for bearish engulfing pattern"""
        if len(data) < 2:
            return False
            
        current = data.iloc[-1]
        prev = data.iloc[-2]
        
        return (float(current['close']) < float(current['open']) and
                float(prev['close']) > float(prev['open']) and
                float(current['open']) > float(prev['close']) and
                float(current['close']) < float(prev['open']))

    def _is_hammer(self, candle):
        """Check for hammer pattern"""
        body = abs(float(candle['close']) - float(candle['open']))
        total_range = float(candle['high']) - float(candle['low'])
        
        if total_range == 0:
            return False
            
        lower_wick = min(float(candle['open']), float(candle['close'])) - float(candle['low'])
        lower_wick_ratio = lower_wick / total_range
        
        return (lower_wick_ratio > 0.6 and 
                body > 0 and 
                float(candle['close']) > float(candle['open']))

    def _is_shooting_star(self, candle):
        """Check for shooting star pattern"""
        body = abs(float(candle['close']) - float(candle['open']))
        total_range = float(candle['high']) - float(candle['low'])
        
        if total_range == 0:
            return False
            
        upper_wick = float(candle['high']) - max(float(candle['open']), float(candle['close']))
        upper_wick_ratio = upper_wick / total_range
        
        return (upper_wick_ratio > 0.6 and 
                body > 0 and 
                float(candle['close']) < float(candle['open']))

    def _is_doji_candle(self, candle):
        """Check for doji candle"""
        body = abs(float(candle['close']) - float(candle['open']))
        total_range = float(candle['high']) - float(candle['low'])
        
        if total_range == 0:
            return False
            
        return body / total_range < 0.1

    def _is_inside_bar(self, data):
        """Check for inside bar pattern"""
        if len(data) < 2:
            return False
            
        current = data.iloc[-1]
        prev = data.iloc[-2]
        
        return (float(current['high']) <= float(prev['high']) and
                float(current['low']) >= float(prev['low']))

    def _is_false_breakout(self, data):
        """Check for false breakout pattern"""
        if len(data) < 3:
            return False
            
        current = data.iloc[-1]
        prev = data.iloc[-2]
        prev_prev = data.iloc[-3]
        
        # Check for breakout then reversal
        broke_high = (float(prev['high']) > float(prev_prev['high']) and
                     float(current['close']) < float(prev_prev['high']))
                     
        broke_low = (float(prev['low']) < float(prev_prev['low']) and
                    float(current['close']) > float(prev_prev['low']))
                    
        return broke_high or broke_low

    def _is_morning_star(self, data):
        """Check for morning star pattern (simplified)"""
        if len(data) < 3:
            return False
            
        first = data.iloc[-3]  # Bearish candle
        second = data.iloc[-2]  # Small body (doji or small)
        third = data.iloc[-1]   # Bullish candle
        
        first_bearish = float(first['close']) < float(first['open'])
        third_bullish = float(third['close']) > float(third['open'])
        second_small = abs(float(second['close']) - float(second['open'])) / (float(second['high']) - float(second['low']) + 1e-12) < 0.3
        
        return first_bearish and second_small and third_bullish

    def _is_evening_star(self, data):
        """Check for evening star pattern (simplified)"""
        if len(data) < 3:
            return False
            
        first = data.iloc[-3]  # Bullish candle
        second = data.iloc[-2]  # Small body (doji or small)
        third = data.iloc[-1]   # Bearish candle
        
        first_bullish = float(first['close']) > float(first['open'])
        third_bearish = float(third['close']) < float(third['open'])
        second_small = abs(float(second['close']) - float(second['open'])) / (float(second['high']) - float(second['low']) + 1e-12) < 0.3
        
        return first_bullish and second_small and third_bearish

    def _get_current_session_quality(self, current_hour):
        """Get current trading session quality"""
        for session, times in TRADING_SESSIONS.items():
            if times['start'] <= current_hour < times['end']:
                return times['quality']
        return 'LOW'

# ==================== TRADE TRADE MANAGER ====================

class TradeManager:
    """Manage trade trading operations and risk"""
    
    def __init__(self):
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.last_trade_time = None
        self.trade_history = []
        
    def can_trade(self):
        """Check if trading is allowed"""
        # Check daily limit
        if self.daily_trades >= TRADE_CONFIG['max_daily_trades']:
            logger.warning("Daily trade limit reached")
            return False
            
        # Check consecutive losses
        if self.consecutive_losses >= TRADE_CONFIG['consecutive_loss_limit']:
            logger.warning("Consecutive loss limit reached")
            return False
            
        # Check cooldown period
        if self.last_trade_time:
            time_since_last = (datetime.now() - self.last_trade_time).total_seconds() / 60
            if time_since_last < TRADE_CONFIG['trade_cooldown_minutes']:
                logger.warning(f"Trade cooldown active: {TRADE_CONFIG['trade_cooldown_minutes'] - time_since_last:.1f} minutes remaining")
                return False
                
        # Check session quality
        current_hour = datetime.now().hour
        session_quality = self._get_session_quality(current_hour)
        if session_quality == 'LOW':
            logger.warning("Low quality trading session - trading anyway")
            # return False
            
        return True
        
    def record_trade(self, signal, score, result):
        """Record trade outcome"""
        self.daily_trades += 1
        self.last_trade_time = datetime.now()
        
        trade_record = {
            'timestamp': datetime.now().isoformat(),
            'signal': signal,
            'score': score,
            'result': result,
            'session': self._get_current_session()
        }
        
        self.trade_history.append(trade_record)
        
        # Update consecutive losses
        if result == 'LOSS':
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            
    def reset_daily_stats(self):
        """Reset daily statistics"""
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.trade_history = []
        
    def _get_session_quality(self, current_hour):
        """Get current session quality"""
        for session, times in TRADING_SESSIONS.items():
            if times['start'] <= current_hour < times['end']:
                return times['quality']
        return 'LOW'
        
    def _get_current_session(self):
        """Get current trading session name"""
        current_hour = datetime.now().hour
        for session, times in TRADING_SESSIONS.items():
            if times['start'] <= current_hour < times['end']:
                return session
        return 'overnight'

# ==================== TRADE EXPIRY OPTIMIZER ====================

class TradeOptimizer:
    """Optimize trade style based on market conditions"""
    
    def __init__(self):
        self.trade_styles = ['SCALP', 'DAY_TRADE', 'SWING']
        
    def recommend_trade_type(self, score, volatility, pattern_type):
        """Recommend optimal trade style"""
        # Base style on score tier
        if score >= 90:
            base_style = 'SCALP'
        elif score >= 85:
            base_style = 'DAY_TRADE'
        else:
            base_style = 'SWING'
            
        # Adjust for volatility
        if volatility > 0.004:  # High volatility
            if base_style == 'SCALP':
                base_style = 'DAY_TRADE'
        elif volatility < 0.001:  # Low volatility
            if base_style == 'SWING':
                base_style = 'SCALP'
                
        # Adjust for pattern type
        if pattern_type == 'MOMENTUM_SCALP':
            base_style = 'SCALP'
        elif pattern_type == 'REJECTION_PLAY':
            base_style = 'DAY_TRADE'
        elif pattern_type == 'TREND_PULLBACK':
            base_style = 'SWING'
            
        return base_style
        
    def calculate_payout_ratio(self, score, trade_type):
        """Calculate Risk:Reward ratio"""
        rr_ratio = 1.5
        
        # Adjust for score
        if score >= 95:
            rr_ratio += 0.5
        elif score >= 90:
            rr_ratio += 0.3
        elif score >= 85:
            rr_ratio += 0.1
            
        # Adjust for trade type
        if trade_type == 'SWING':
            rr_ratio += 1.0
        elif trade_type == 'SCALP':
            rr_ratio -= 0.5
            
        return f"1:{rr_ratio:.1f}"


class JarvisCNS:
    """Central Nervous System - Monitors system health and logic failures"""
    def __init__(self, ai_brain, parent_system=None):
        self.ai_brain = ai_brain
        self.parent = parent_system
        self.sensory_buffer = deque(maxlen=100)
        self.pain_events = []
        self.health_status = "HEALTHY"
        self.last_diagnostic = "No issues detected."
        
    def record_perception(self, analysis_cycle):
        """Record what the system 'felt' in this cycle"""
        self.sensory_buffer.append({
            "timestamp": time.time(),
            "telemetry": analysis_cycle.get('telemetry', {}),
            "signal": analysis_cycle.get('signal', {}),
            "market_logic": analysis_cycle.get('detailed_scores', {})
        })
        
    def detect_pain(self, trade_result):
        """
        Analyze if a logic failure occurred based on trade outcome.
        If a trade lost, we ask: 'Which part lied to us?'
        """
        if trade_result.get('pnl', 0) >= 0:
            return None # No pain on profit
            
        # Trigger diagnostic on loss
        self.health_status = "PAIN DETECTED"
        logger.warning("🧠 CNS: Pain detected in system. Diagnosing logic failure...")
        
        # Get the latest sensory data
        last_feeling = self.sensory_buffer[-1] if self.sensory_buffer else {}
        
        # Format diagnostic prompt for local AI
        prompt = f"""
        [SYSTEM DIAGNOSTIC MODE]
        A trade just lost. PnL: {trade_result.get('pnl')}
        
        SENSORY TELEMETRY:
        {json.dumps(last_feeling.get('telemetry'), indent=2, cls=NumpyEncoder)}
        
        TRADE DECISION:
        {json.dumps(last_feeling.get('signal'), indent=2, cls=NumpyEncoder)}
        
        TASK:
        Aapdi system na logic ma kyank 'pain' che. Telemetry joi ne Gujlish ma samjav ke kaya Part na logic ma gadbad che ane tene su improve karvu joyiye?
        Khali suggestion aapje, code badalto nai. Friendly and expert tone rakhje.
        """
        
        try:
            diagnosis, _ = self.ai_brain.call_multi_ai(prompt, system_voice="System Auditor")
            self.last_diagnostic = diagnosis
            logger.info(f"🧠 CNS DIAGNOSIS: {diagnosis}")
            
            # Auto-sync to HUD on diagnosis
            if self.parent:
                self.parent._sync_to_hud({})
            return diagnosis
        except Exception as e:
            logger.error(f"CNS Diagnostic Error: {e}")
            return "Diagnosis failed."

# ==================== ENHANCED JARVIS TRADE ELITE ====================

class JarvisElite:
    """JARVIS TRADE ELITE v7.0 - Complete SwingScalp Trading System"""
    
    def __init__(self):
        self.scoring_matrix = TradeScoringMatrix()
        self.trade_manager = TradeManager()
        self.expiry_optimizer = TradeOptimizer()
        self.scalping_engine = ScalpingEngine() # NEW: Scalping Targets
        self.deepseek_enabled = True  # ENABLED: DeepSeek AI Judge for signal validation
        self.hud_enabled = True  # FIX #1: HUD backend now exists in jarvis_hud/
        self.hud_url = "http://localhost:8000/api/update"
        self.is_backtest_mode = False  # Track if running in backtest mode

    
        # Initialize Data Source (Delta Exchange only)
        try:
            from delta_api_wrapper import DeltaExchangeData
            self.delta_data = DeltaExchangeData()
            self.delta_client = self.delta_data
            logger.info("✅ Delta Exchange Data Initialized")
        except Exception as e:
            logger.warning(f"Delta initialization failed: {e}")
            self.delta_data = None
            self.delta_client = None

        # FIX #4: Deribit removed — using Delta Exchange only
        self.deribit = None
    
        # Initialize Parts Dictionary (Empty first, passed by reference to Fusion Engine)
        self.parts = {}

        # FIX #5: Removed phantom import of deepseek_missing_brains
        # Stubs are provided inline by part2_fixed.py — not needed here
        self.candle_psychology = None
        # FIX: Initialize zone_detector from part3 ZonePointFiveDetectorGPU
        try:
            from part3_FIXED import ZonePointFiveDetectorGPU, CandlePsychologyMasterGPU
            self.zone_detector = ZonePointFiveDetectorGPU(self)
            self.candle_psychology = CandlePsychologyMasterGPU(self)
            logger.info("✅ Zone Detector & Candle Psychology initialized from part3")
        except Exception as _ze:
            self.zone_detector = None
            logger.warning(f"⚠️ zone_detector init failed: {_ze} — zone signals skipped")
    
        # Realtime data structure expected by institutional engine
        self.realtime_data = {
            '1min': [],
            '5min': [],
            '15min': []
        }

        # Initialize External GPU Engines
        self.engines = {}
        if EXTERNAL_ENGINES_AVAILABLE:
            try:
                logger.info("🚀 Initializing External GPU Engines...")
                self.engines['institutional'] = InstitutionalTradingEngineGPU(self)
                self.engines['neural'] = NeuralNetworkManager(self)
                self.engines['fusion'] = GPUEnhancedFusionEngine(self.parts)
                self.engines['confidence'] = GPUUnifiedConfidenceEngine()
                self.engines['pattern'] = EnhancedGPUPatternRecognitionEngine()
                logger.info("✅ External GPU Engines Initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize external engines: {e}") 

    
        # Existing Jarvis components (Now Adapters)
        self.parts = {
            'part1_breakout': Part1Breakout(),
            'part2_zone': Part2Zone(),
            'part3_psychology': Part3Psychology(),
            'part4_volume': Part4Volume(),
            'part5_ml': Part5ML(),
            'part6_trend': Part6Trend(),
            'part7_volatility': Part7Volatility(),
            'part8_structure': Part8Structure(),
            'part9_orderflow': Part9Orderflow(),
            'part10_candlestats': Part10Candlestats(),
            'part11_fusion': Part11Fusion(),
            'part12_confidence': Part12Confidence(),
            'part14_options_chain': Part14OptionsChain(delta_client=self.delta_data)
        }
        self.mtf_analyzer = DeepMTFAnalyzer(self.parts) # NEW: Deep MTF Analysis
        self.brains = {
            'neural_hud_brain': None,
            'quantum_v5': QuantumV5(),
            'safety_risk_brain': SafetyRiskBrain(),
            'volume_pressure_brain': VolumePressureBrain(),
            'trend_acceleration_brain': TrendAccelerationBrain(),
            'risk_filter_brain': RiskFilterBrain()
        }
        self.deepseek_brains = {
            'deepseek_v3_sentiment': DeepSeekV3Brain(),
            'deepseek_r1_reasoning': DeepSeekR1ReasoningBrain()
        }
    
        # NEW: Jarvis Neural Cortex (Unified AI Brain)
        self.neural_cortex = JarvisNeuralCortex()
        self.cns = JarvisCNS(self.neural_cortex, parent_system=self) # NEW: Jarvis CNS
    
        self.upgrades = {
            'reverse_safety_engine': ReverseSafetyEngine(),
            'trap_candle_genome_detector': TrapCandleGenomeDetector(),
            'market_mood_engine': MarketMoodEngine(),
            'high_volatility_regime_shield': HighVolatilityRegimeShield()
        }
    
        # Trading state
        self.current_score = 0
        self.current_signals = {}
        self.market_context = {}
    
    def _fetch_mtf_from_api(self):
        """Fetch real historical OHLCV data for all timeframes from Delta Exchange API"""
        import pandas as pd
        
        # Map our timeframe names to Delta API resolution strings
        tf_config = {
            '1m':  {'resolution': '1m',  'limit': 500},
            '5m':  {'resolution': '5m',  'limit': 500},
            '15m': {'resolution': '15m', 'limit': 500},
            '1h':  {'resolution': '1h',  'limit': 500},
            '4h':  {'resolution': '4h',  'limit': 500},
        }
        
        mtf_datasets = {}
        symbol = "BTCUSDT"
        
        for tf_name, cfg in tf_config.items():
            try:
                candles = self.delta_client.get_historical_candles(
                    symbol=symbol,
                    resolution=cfg['resolution'],
                    limit=cfg['limit']
                )
                if candles and len(candles) >= 1:
                    df = pd.DataFrame(candles)
                    # Delta returns: time, open, high, low, close, volume
                    df.rename(columns={'time': 'timestamp'}, inplace=True)
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                    df.set_index('timestamp', inplace=True)
                    df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
                    df.sort_index(inplace=True)
                    mtf_datasets[tf_name] = df
                    logger.info(f"[MTF-API] {tf_name}: {len(df)} candles fetched from Delta Exchange")
                else:
                    logger.warning(f"[MTF-API] {tf_name}: No data returned, will skip")
            except Exception as e:
                logger.warning(f"[MTF-API] {tf_name} fetch failed: {e}")
        
        logger.info(f"[MTF-API] Fetched {len(mtf_datasets)} timeframes: {list(mtf_datasets.keys())}")
        return mtf_datasets

    def analyze_trade_setup(self, data, mtf_context=None):
        """Complete trade trading analysis with MTF support"""
        try:
            # Auto-start Double-Brain AI Chain on first run
            # DISABLED for Performance: Prevents resource contention with Trading Judge
            # if not self.ai_chain_brain.is_running:
            #     logger.info("[JARVIS] 🧠 Starting Gemini->DeepSeek AI Chain...")
            #     self.ai_chain_brain.start_sequential_loop(self)
                
            if len(data) < 20:
                return self._get_no_trade_signal("Insufficient data")
                
            # Get current price and context
            current_price = float(data['close'].iloc[-1])
            self.last_price = current_price  # Store for AI Chain global context
            self.market_context = self._get_market_context(data)
            
            # --- EXTERNAL ENGINE EXECUTION ---
            # FIX: Initialize ALL market_context keys upfront to prevent KeyError crashes
            self.market_context.setdefault('institutional_components', {
                'psychology': [],
                'zone': [],
                'trend': [],
                'volume': [],
                'structure': [],
                'orderflow': [],
                'regime': 'NEUTRAL'
            })
            self.market_context.setdefault('institutional_fused', [])
            self.market_context.setdefault('neural_prediction', None)
            self.market_context.setdefault('neural_mtf', {})
            self.market_context.setdefault('pattern_mtf', {})
            self.market_context.setdefault('fusion_mtf', {})
            self.market_context.setdefault('mtf_datasets', {})
            # FIX: Add safe defaults for all adapters
            self.market_context.setdefault('last_processed_price', 0)
            self.market_context.setdefault('timestamp', None)
            
            if EXTERNAL_ENGINES_AVAILABLE and self.engines:
                try:
                    # Ensure DatetimeIndex for resampling
                    if not isinstance(data.index, pd.DatetimeIndex):
                        data = data.copy()
                        data.index = pd.to_datetime(data.index)
                    
                    # Build ALL timeframe datasets for GPU engines
                    ohlcv_agg = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
                    engine_tf_data = {'1m': data}
                    resample_rules = {
                        '3m': '3min', '5m': '5min', '15m': '15min', '30m': '30min',
                        '1h': '1h', '2h': '2h', '4h': '4h'
                    }
                    for tf_name, tf_rule in resample_rules.items():
                        try:
                            resampled = data.resample(tf_rule).agg(ohlcv_agg).dropna()
                            if len(resampled) >= 1:
                                engine_tf_data[tf_name] = resampled
                        except Exception:
                            pass
                    
                    # Store MTF data for all engines to use
                    self.market_context['mtf_datasets'] = engine_tf_data
                    logger.info(f"📊 GPU Engines: {len(engine_tf_data)} timeframes ready: {list(engine_tf_data.keys())}")
                    
                    # 1. Institutional Analysis (Native MTF)
                    inst_engine = self.engines.get('institutional')
                    if inst_engine:
                        if hasattr(inst_engine, 'generate_mtf_signals'):
                            inst_res = inst_engine.generate_mtf_signals(engine_tf_data)
                            logger.info(f"✅ Institutional MTF: Cons={inst_res.get('mtf_consensus', 0):.2f}")
                        else:
                            # Fallback to legacy
                            df_1min = engine_tf_data.get('1m', data)
                            df_5min = engine_tf_data.get('5m', df_1min)
                            df_15min = engine_tf_data.get('15m', df_1min)
                            inst_res = inst_engine.generate_live_signals(df_1min, df_5min, df_15min)
                        
                        # Store components for Adapters P1-P4, P6-P9
                        if isinstance(inst_res, dict) and 'components' in inst_res:
                            self.market_context['institutional_components'] = inst_res['components']
                            self.market_context['institutional_fused'] = inst_res.get('signals', [])
                    
                    # 2. Neural Analysis (analyze multiple timeframes) - WITH SAFE ERROR HANDLING
                    neural_engine = self.engines.get('neural')
                    if neural_engine:
                        neural_mtf = {}
                        for tf_name, tf_df in engine_tf_data.items():
                            if len(tf_df) >= 30:
                                try:
                                    hist = tf_df.iloc[-60:] if len(tf_df) >= 60 else tf_df
                                    # SAFE: Check if method exists before calling
                                    if hasattr(neural_engine, 'predict') and callable(getattr(neural_engine, 'predict')):
                                        neural_res = neural_engine.predict(hist['close'].values, hist['volume'].values)
                                        if neural_res is not None:
                                            neural_mtf[tf_name] = neural_res
                                    else:
                                        logger.debug(f"Neural engine has no predict method on {tf_name}")
                                except TypeError as e:
                                    logger.debug(f"Neural signature mismatch on {tf_name}: {e}")
                                except Exception as e:
                                    logger.debug(f"Neural error on {tf_name}: {e}")
                        self.market_context['neural_prediction'] = neural_mtf.get('1m') if neural_mtf else None
                        self.market_context['neural_mtf'] = neural_mtf if neural_mtf else {}
                        if neural_mtf:
                            logger.info(f"🧠 Neural analysis: {len(neural_mtf)} timeframes analyzed")
                        else:
                            logger.debug("ℹ️ Neural engine produced no predictions")
                        
                    # 3. Pattern Recognition (Native MTF)
                    pattern_engine = self.engines.get('pattern')
                    if pattern_engine:
                        if hasattr(pattern_engine, 'scan_patterns_mtf'):
                            pattern_mtf = pattern_engine.scan_patterns_mtf(engine_tf_data)
                        else:
                            # Fallback loop
                            pattern_mtf = {}
                            for tf_name, tf_df in engine_tf_data.items():
                                if len(tf_df) >= 20: 
                                    try:
                                        if hasattr(pattern_engine, 'detect_patterns'):
                                            patterns = pattern_engine.detect_patterns(tf_df)
                                            if patterns: pattern_mtf[tf_name] = patterns
                                    except Exception: pass
                                    
                        self.market_context['pattern_mtf'] = pattern_mtf
                        if pattern_mtf:
                            logger.info(f"🎯 Patterns found on: {list(pattern_mtf.keys())}")

                    # 4. Fusion Engine (Native MTF)
                    fusion_engine = self.engines.get('fusion')
                    if fusion_engine:
                        if hasattr(fusion_engine, 'parts'):
                            fusion_engine.parts = self.parts
                            
                        if hasattr(fusion_engine, 'fuse_modules_mtf'):
                            fusion_res = fusion_engine.fuse_modules_mtf(engine_tf_data)
                            self.market_context['fusion_mtf'] = fusion_res
                            logger.info("🔧 Fusion Engine: MTF Fusion Complete")
                    
                    # 5. Confidence Engine (available for downstream use)
                    # Will be used during final signal generation
                    
                except Exception as e:
                    logger.error(f"⚠️ External Engine Execution Protocol Failed: {e}")
                    logger.warning("⚠️ Falling back to legacy part analysis (GPU engines unavailable)")
            else:
                logger.debug("GPU Engines not available - using adapter parts only")
            # ---------------------------------
            
            # ============================================================
            # MULTI-TIMEFRAME ANALYSIS: All Parts on ALL Timeframes (1m-4h)
            # FIX #16: Reuse engine_tf_data if already computed above (avoid duplicate resampling)
            # ============================================================
            
            # First run: fetch all TFs from API
            if not hasattr(self, '_api_mtf_cache') or self._api_mtf_cache is None:
                logger.info("[MTF-API] First run — fetching all timeframes from Delta API...")
                self._api_mtf_cache = self._fetch_mtf_from_api()
                
                # Fallback if API returns no data
                if not self._api_mtf_cache:
                    logger.warning("[MTF-API] API unavailable — falling back to resampling.")
                    if not isinstance(data.index, pd.DatetimeIndex):
                        data = data.copy()
                        data.index = pd.to_datetime(data.index)
                    
                    ohlcv_agg = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
                    mtf_data_fb = {'1m': data}
                    resample_map = {
                        '3m': '3min', '5m': '5min', '15m': '15min', '30m': '30min',
                        '1h': '1h', '2h': '2h', '4h': '4h'
                    }
                    for tf_name, tf_rule in resample_map.items():
                        try:
                            resampled = data.resample(tf_rule).agg(ohlcv_agg).dropna()
                            if len(resampled) >= 1:
                                mtf_data_fb[tf_name] = resampled
                        except Exception:
                            pass
                    self._api_mtf_cache = mtf_data_fb

            # Always update 1m with latest data
            if '1m' in self._api_mtf_cache:
                self._api_mtf_cache['1m'] = data  # Use live streaming 1m data
            mtf_data = self._api_mtf_cache
            self.market_context['mtf_datasets'] = mtf_data
            
            logger.info(f"📊 MTF Analysis: {len(mtf_data)} timeframes active: {list(mtf_data.keys())}")
            
            # Timeframe weights (higher TF = higher weight for trend direction)
            tf_weights = {
                '1m': 1.0,   # Scalping - Entry timing
                '3m': 1.5,   # Micro trend  
                '5m': 2.0,   # Short-term trend
                '15m': 3.0,  # Medium trend
                '30m': 4.0,  # Strong trend
                '1h': 5.0,   # Major trend
                '2h': 6.0,   # Institutional trend
                '4h': 7.0    # Long-term bias (STRONGEST)
            }
            
            # Run ALL parts on ALL timeframes
            part_results = {}        # Final weighted results (1m base)
            full_telemetry = {}
            mtf_breakdown = {}       # Per-timeframe breakdown for logging
            
            # Accumulate weighted signals across timeframes
            weighted_signals = {}    # part_name -> weighted sum
            weight_totals = {}       # part_name -> total weight applied
            
            for tf_name, tf_data in mtf_data.items():
                tf_weight = tf_weights.get(tf_name, 1.0)
                tf_results = {}
                
                for name, part in self.parts.items():
                    if name in ['part11_fusion', 'part12_confidence']:
                        continue
                    
                    try:
                        res = part.analyze(tf_data, context=self.market_context)
                        if isinstance(res, dict):
                            tf_results[name] = res
                            raw_signal = res.get('signal', 0)
                            
                            # Force scalar signal (handle list/sequence returns from some parts)
                            try:
                                if isinstance(raw_signal, (list, tuple, np.ndarray)):
                                    signal = float(raw_signal[-1]) if len(raw_signal) > 0 else 0.0
                                else:
                                    signal = float(raw_signal)
                            except:
                                signal = 0.0
                            
                            # Accumulate weighted signal
                            if name not in weighted_signals:
                                weighted_signals[name] = 0.0
                                weight_totals[name] = 0.0
                            
                            weighted_signals[name] += signal * tf_weight
                            weight_totals[name] += tf_weight
                            
                            if 'telemetry' in res and tf_name == '1m':
                                full_telemetry[name] = res['telemetry']
                    except Exception as e:
                        if tf_name == '1m':  # Only log errors for primary TF
                            logger.error(f"❌ Part {name} error on {tf_name}: {e}")
                
                mtf_breakdown[tf_name] = tf_results
            
            # Build final part_results with weighted MTF consensus
            for name, part in self.parts.items():
                if name in ['part11_fusion', 'part12_confidence']:
                    continue
                
                if name in weighted_signals and weight_totals[name] > 0:
                    weighted_avg = weighted_signals[name] / weight_totals[name]
                    
                    # Convert weighted average to signal (-1, 0, 1)
                    if weighted_avg > 0.15:
                        final_signal = 1
                    elif weighted_avg < -0.15:
                        final_signal = -1
                    else:
                        final_signal = 0
                    
                    # Get 1m thought as base
                    base_result = mtf_breakdown.get('1m', {}).get(name, {})
                    base_thought = base_result.get('thought', 'No thought')
                    
                    # Count TF agreement
                    tf_agree = sum(1 for tf in mtf_breakdown if name in mtf_breakdown[tf] 
                                  and mtf_breakdown[tf][name].get('signal', 0) == final_signal and final_signal != 0)
                    
                    part_results[name] = {
                        'signal': final_signal,
                        'thought': f"{base_thought} | MTF: {tf_agree}/{len(mtf_data)} TFs agree",
                        'weighted_avg': round(weighted_avg, 3),
                        'tf_agreement': tf_agree
                    }
                    
                    if final_signal != 0:
                        logger.debug(f"🔍 MTF TRACER: {name} signal={final_signal} weighted={weighted_avg:.3f} TFs={tf_agree}/{len(mtf_data)}")
                else:
                    part_results[name] = {'signal': 0, 'thought': 'Part offline'}
            
            # Log MTF summary
            buy_parts = sum(1 for r in part_results.values() if r.get('signal', 0) > 0)
            sell_parts = sum(1 for r in part_results.values() if r.get('signal', 0) < 0)
            logger.info(f"📈 MTF CONSENSUS: {buy_parts} BUY / {sell_parts} SELL across {len(mtf_data)} timeframes")
            
            # [NEW] Expose data for AI Chain Brain
            self.latest_part_results = part_results
            self.latest_telemetry = full_telemetry
            
            # --- MACRO CONTEXT & OPTIONS PRE-FETCH ---
            options_intel = None
            intel_delta = None
            intel_deribit = None
            
            # Fetch Delta Intel
            if self.delta_data:
                try:
                    intel_delta = self.delta_data.get_institutional_bias('BTC')
                    options_intel = intel_delta
                except Exception: pass

            # Fetch Deribit Intel
            if self.deribit:
                try:
                    current_price = float(data['close'].iloc[-1])
                    intel_deribit = self.deribit.get_institutional_bias(current_price)
                    if not options_intel: options_intel = intel_deribit
                except Exception: pass
            
            # Store walls for AI context
            options_walls = {}
            active_intel = intel_delta if intel_delta else intel_deribit
            if active_intel:
                options_walls = {
                    'support': active_intel.get('support_wall') or active_intel.get('raw_data', {}).get('support'),
                    'resistance': active_intel.get('resistance_wall') or active_intel.get('raw_data', {}).get('resistance'),
                    'max_pain': active_intel.get('max_pain') or active_intel.get('raw_data', {}).get('max_pain')
                }
            
            self.last_dual_intel = {'delta': intel_delta, 'deribit': intel_deribit}

            # --- MATHEMATICAL ANALYST OPINION (First) ---
            math_res = self.parts['part11_fusion'].analyze(list(part_results.values()))
            math_conf_res = self.parts['part12_confidence'].analyze(list(part_results.values()))
            
            math_signal = math_res.get('signal', 0)
            math_confidence = math_conf_res.get('confidence', 10)
            
            # --- HOLISTIC NEURAL GLOBAL SYNTHESIS (PHASE 15: THE COUNCIL) ---
            # Judge is now ENABLED and validates high-confidence signals (score >= 10)
            # System uses: Mathematical Analyst + Quantum V5 + DeepSeek Judge
            neural_res = None
            if TRADE_CONFIG.get('use_neural_fusion', True):
                # Always run AI (Full Power in both Live and Backtest)
                if math_signal != 0 and math_confidence >= 20: # Run AI even on weak signals to let it filter them out
                    neural_res = self._neural_global_synthesis(full_telemetry, part_results, mtf_context, options_walls, math_signal, math_confidence, data)
                else:
                    neural_res = None
                
            if neural_res:
                logic_signal = 1 if neural_res.get('bias') == 'CALL' else (-1 if neural_res.get('bias') == 'PUT' else 0)
                confidence = neural_res.get('confidence', 0)
                ai_thought = neural_res.get('reasoning', '')
                
                # SAFETY SHIELD: Hallucination Guard (relaxed threshold)
                if math_confidence < 10 and confidence > 80:
                    logger.warning(f"🛡️ SAFETY SHIELD: AI Overconfidence ({confidence}%) vs Weak Math ({math_confidence}%). Vetoed.")
                    # Force downgrade to match Math's caution
                    confidence = math_confidence 
                    logic_signal = 0 # Safety Veto
                    ai_thought = "Judge Vetoed by Safety Shield (Math score too low)"
            else:
                # Fallback to Analyst if Judge is silent/slow
                logic_signal = math_signal
                confidence = math_confidence
                if getattr(self, 'is_backtest_mode', False):
                    ai_thought = "Using Mathematical Analyst (AI Judge bypassed in backtest to save API limits)"
                else:
                    ai_thought = "Using Mathematical Analyst (Judge unavailable)"
            
            # Map thoughts for final synthesis
            thoughts = [res['thought'] for k, res in part_results.items() 
                        if res['signal'] != 0 and k not in ['part11_fusion', 'part12_confidence']]
            if neural_res: thoughts.insert(0, f"🧠 NEURAL: {ai_thought}")
            
            detailed_scores = {name: res['signal'] for name, res in part_results.items()}
            detailed_scores['thoughts'] = thoughts
            detailed_scores['neural_synthesis'] = neural_res
            detailed_scores['quantum_validation'] = (neural_res.get('quantum_data', {}) if neural_res else self.brains['quantum_v5'].simulate(data)) if hasattr(self, 'brains') and 'quantum_v5' in getattr(self, 'brains', {}) else {}
            
            # Base score from confidence
            # FIXED: NO-TRADE should also show confidence % (how certain we are NOT to trade)
            score = confidence
            
            # --- UNIVERSAL MTF CONFLUENCE BONUS (1m to 4h) ---
            if mtf_context:
                # Direction from 1m logic
                current_dir = logic_signal 
                
                confluence_score = 0
                mtf_weights = {'3m': 2, '5m': 3, '15m': 5, '30m': 7, '1h': 10, '2h': 12, '4h': 15}
                
                for tf, analysis in mtf_context.items():
                    tf_dir = analysis.get('direction', 0)
                    weight = mtf_weights.get(tf, 0)
                    
                    if tf_dir == current_dir and current_dir != 0:
                        confluence_score += weight  # Cumulative bonus
                    elif tf_dir == -current_dir and current_dir != 0:
                        confluence_score -= (weight * 0.5)  # Light penalty for HTF conflict (allow 1m scalping)
                
                if confluence_score != 0:
                    score = max(0, min(100, score + confluence_score))
                    detailed_scores['universal_mtf_confluence'] = confluence_score
                    detailed_scores['mtf_matrix'] = mtf_context
            
            # --- QUANTUM V5 PROBABILITY BOOST (PHASE 16) ---
            # Quantum was already run inside _neural_global_synthesis, extract result
            if neural_res:
                quantum_res = neural_res.get('quantum_data', {})
            elif hasattr(self, 'brains') and 'quantum_v5' in getattr(self, 'brains', {}):
                quantum_res = self.brains['quantum_v5'].simulate(data)
            else:
                quantum_res = {'signal': 0, 'thought': 'Quantum unavailable'}
            q_sig = quantum_res.get('signal', 0) if isinstance(quantum_res, dict) else 0
            q_thought = quantum_res.get('thought', 'Quantum idle') if isinstance(quantum_res, dict) else 'Quantum idle'
            
            # Store Quantum activity for visibility
            detailed_scores['quantum_signal'] = q_sig
            detailed_scores['quantum_thought'] = q_thought
            logger.info(f"⚛️ QUANTUM V5: {q_thought}")
            
            if q_sig == logic_signal and logic_signal != 0:
                # Boost confidence by 15% if Quantum agrees
                boost = 15
                score = min(100, score + boost)
                ai_thought += f" | ⚛️ QUANTUM BOOST (+{boost}%)"
                detailed_scores['quantum_boost'] = boost
                logger.info(f"⚛️ QUANTUM ALIGNED: Boosted confidence by +{boost}%")
            elif q_sig == -logic_signal and logic_signal != 0:
                 # Penalty if Quantum disagrees (reduced)
                penalty = 5
                score = max(0, score - penalty)
                ai_thought += f" | ⚛️ QUANTUM DIVERGENCE (-{penalty}%)"
                detailed_scores['quantum_penalty'] = penalty
                logger.warning(f"⚛️ QUANTUM CONFLICT: Penalized confidence by -{penalty}%")
            else:
                logger.info("⚛️ QUANTUM NEUTRAL: No impact on confidence")

            # ---------------------------
            # PHASE 3 FIX: Wire sleeping brains into decision flow
            # ---------------------------
            
            # 3C. Fusion Engine confluence (was computed but never read)
            fusion_mtf = self.market_context.get('fusion_mtf', {})
            if isinstance(fusion_mtf, dict) and fusion_mtf:
                fusion_signal = fusion_mtf.get('consensus_signal', fusion_mtf.get('signal', 0))
                if isinstance(fusion_signal, (int, float)):
                    if int(fusion_signal) == logic_signal and logic_signal != 0:
                        score = min(100, score + 3)
                        ai_thought += " | 🔧 FUSION ALIGNED"
                        detailed_scores['fusion_boost'] = 3
                        logger.info("🔧 FUSION ENGINE: Aligned with signal (+3%)")
            
            # 3D. Pattern Recognition confluence (was computed but never read)
            pattern_mtf = self.market_context.get('pattern_mtf', {})
            if pattern_mtf and isinstance(pattern_mtf, dict):
                pattern_tf_count = len(pattern_mtf)
                if pattern_tf_count >= 3:
                    pattern_boost = min(5, pattern_tf_count)
                    score = min(100, score + pattern_boost)
                    ai_thought += f" | 🔍 PATTERNS on {pattern_tf_count} TFs (+{pattern_boost}%)"
                    detailed_scores['pattern_mtf_boost'] = pattern_boost
                    logger.info(f"🔍 PATTERN ENGINE: {pattern_tf_count} timeframes with patterns (+{pattern_boost}%)")
            
            # 3E. Supplementary Intelligence (ExtraBrains, SmartBreakout, AdvancedAnalysis)
            supplementary = getattr(self, 'supplementary_intelligence', {})
            if supplementary:
                # ExtraBrains: Trend/Volatility/Risk modifiers
                extra_brains_data = supplementary.get('ExtraBrains', {})
                if extra_brains_data:
                    insights = extra_brains_data.get('insights', [])
                    extra_boost = 0
                    for insight in insights:
                        insight_upper = str(insight).upper()
                        # Trend alignment bonus
                        if 'BULLISH' in insight_upper and logic_signal == 1:
                            extra_boost += 2
                        elif 'BEARISH' in insight_upper and logic_signal == -1:
                            extra_boost += 2
                        # High risk penalty
                        if 'RISK: HIGH' in insight_upper or 'RISK: EXTREME' in insight_upper:
                            extra_boost -= 3
                        # Low volatility caution
                        if 'VOLATILITY: LOW' in insight_upper:
                            extra_boost -= 1
                    
                    if extra_boost != 0:
                        extra_boost = max(-10, min(10, extra_boost))  # Clamp
                        score = max(0, min(100, score + extra_boost))
                        sign = "+" if extra_boost > 0 else ""
                        ai_thought += f" | 🧠 EXTRA BRAINS ({sign}{extra_boost}%)"
                        detailed_scores['extra_brains_boost'] = extra_boost
                        logger.info(f"🧠 EXTRA BRAINS: {len(insights)} insights → {sign}{extra_boost}%")
                
                # SmartBreakoutAI: Breakout alignment
                breakout_data = supplementary.get('SmartBreakoutAI', {})
                if breakout_data and isinstance(breakout_data, dict):
                    breakout_signal_str = str(breakout_data.get('signal', 'NEUTRAL')).upper()
                    if (breakout_signal_str in ('BUY', 'CALL', 'BULLISH') and logic_signal == 1) or \
                       (breakout_signal_str in ('SELL', 'PUT', 'BEARISH') and logic_signal == -1):
                        score = min(100, score + 5)
                        ai_thought += " | 🎯 BREAKOUT ALIGNED (+5%)"
                        detailed_scores['breakout_boost'] = 5
                        logger.info("🎯 SMARTBREAKOUT: Aligned with signal (+5%)")
                    elif (breakout_signal_str in ('BUY', 'CALL', 'BULLISH') and logic_signal == -1) or \
                         (breakout_signal_str in ('SELL', 'PUT', 'BEARISH') and logic_signal == 1):
                        score = max(0, score - 3)
                        ai_thought += " | 🎯 BREAKOUT CONFLICT (-3%)"
                        detailed_scores['breakout_penalty'] = -3
                        logger.info("🎯 SMARTBREAKOUT: Conflicts with signal (-3%)")
                
                # AdvancedAnalysis (16-Brain system): Alignment vote
                adv_data = supplementary.get('AdvancedAnalysis', {})
                if adv_data and isinstance(adv_data, dict):
                    adv_result = adv_data.get('result', {})
                    if isinstance(adv_result, dict):
                        adv_signal = adv_result.get('signal', adv_result.get('direction', 0))
                        try:
                            adv_signal = int(adv_signal)
                        except (ValueError, TypeError):
                            adv_signal = 0
                        
                        if adv_signal == logic_signal and logic_signal != 0:
                            score = min(100, score + 4)
                            ai_thought += " | 🧬 16-BRAIN ALIGNED (+4%)"
                            detailed_scores['advanced_analysis_boost'] = 4
                            logger.info("🧬 ADVANCED ANALYSIS: 16-brain system aligned (+4%)")
                
                # EnhancedConfidence cross-check
                ext_conf_data = supplementary.get('EnhancedConfidence', {})
                if ext_conf_data and isinstance(ext_conf_data, dict):
                    ext_score = ext_conf_data.get('confidence', ext_conf_data.get('score', None))
                    if ext_score is not None:
                        try:
                            ext_score = float(ext_score)
                            # If external confidence significantly disagrees, moderate
                            if abs(score - ext_score) > 30:
                                old_score = score
                                score = int(score * 0.7 + ext_score * 0.3)
                                ai_thought += f" | 📊 CONF MODERATED ({old_score}→{score})"
                                detailed_scores['confidence_moderation'] = score - old_score
                                logger.info(f"📊 ENHANCED CONFIDENCE: Moderated {old_score} → {score}")
                        except (ValueError, TypeError):
                            pass
                            
            # ---------------------------
            # Check trading conditions
            if not self.trade_manager.can_trade():
                return self._get_no_trade_signal("Trading not allowed")
                
            # --- MASTER AI SYNTHESIS --- ENABLED: DeepSeek AI Judge for signal validation
            if score >= 10 and self.deepseek_enabled and not neural_res:
                ai_validation = self._get_deepseek_validation(data, score, detailed_scores, full_telemetry)
                if not ai_validation.get('approved', False):
                    logger.warning(f"🧠 MASTER AI REJECTION: {ai_validation.get('reason', 'Unknown')}")
                    return self._get_no_trade_signal(f"AI rejection: {ai_validation.get('reason', 'Unknown')}")
                else:
                    detailed_scores['ai_synthesis'] = ai_validation.get('reason', 'No reasoning provided')
                    logger.info(f"🧠 MASTER AI APPROVED: {ai_validation.get('reason')[:100]}...")

            
            # Generate final signal
            final_decision = self._generate_trade_signal(data, score, detailed_scores, options_intel, logic_signal)
            
            # --- BIG PLAYER FILTER (STRICT DUAL CONFLUENCE) ---
            if TRADE_CONFIG.get('use_big_player_filter', True):
                try:
                    intel = getattr(self, 'last_dual_intel', {})
                    delta_intel = intel.get('delta')
                    deribit_intel = intel.get('deribit')
                    
                    delta_score = delta_intel.get('score', 0) if delta_intel else 0
                    deribit_score = deribit_intel.get('score', 0) if deribit_intel else 0
                    
                    signal_direction = final_decision.get('trade_signal', {}).get('direction', 'NO_TRADE')
                    
                    if signal_direction != 'NO_TRADE':
                        # 1. Conflict Check (STRICT REJECTION if ANY exchange disagrees)
                        conflict = False
                        rejection_msg = ""
                        
                        # Check Delta Conflict (relaxed to ±5 for 1m scalping)
                        if signal_direction == 'CALL' and delta_score <= -5:
                            conflict, rejection_msg = True, f"Delta Bearish ({delta_score})"
                        elif signal_direction == 'PUT' and delta_score >= 5:
                            conflict, rejection_msg = True, f"Delta Bullish ({delta_score})"
                        
                        # Check Deribit Conflict
                        if not conflict:
                            if signal_direction == 'CALL' and deribit_score <= -5:
                                conflict, rejection_msg = True, f"Deribit Bearish ({deribit_score})"
                            elif signal_direction == 'PUT' and deribit_score >= 5:
                                conflict, rejection_msg = True, f"Deribit Bullish ({deribit_score})"
                                
                        if conflict:
                            logger.warning(f"🚫 DUAL REJECTION: {rejection_msg} vs {signal_direction}")
                            return self._get_no_trade_signal(f"Institutional Conflict: {rejection_msg}")
                            
                        # 2. Alignment Bonus (Dual Confluence)
                        confluence_bonus = 0
                        sources_aligned = 0
                        
                        if (signal_direction == 'CALL' and delta_score >= 3) or (signal_direction == 'PUT' and delta_score <= -3):
                            confluence_bonus += abs(delta_score)
                            sources_aligned += 1
                        
                        if (signal_direction == 'CALL' and deribit_score >= 3) or (signal_direction == 'PUT' and deribit_score <= -3):
                            confluence_bonus += abs(deribit_score)
                            sources_aligned += 1
                            
                        if confluence_bonus > 0:
                            logger.info(f"✅ DUAL CONFLUENCE: {sources_aligned} sources support {signal_direction}")
                            
                            # Fix: Ensure detailed_scores exists
                            if 'detailed_scores' not in final_decision:
                                final_decision['detailed_scores'] = {}
                            
                            final_decision['detailed_scores']['dual_confluence'] = True
                            
                            # Double confirmation multiplier
                            if sources_aligned == 2:
                                confluence_bonus = int(confluence_bonus * 1.5)
                                logger.info(f"💎 DOUBLE CONFIRMATION! Bonus: +{confluence_bonus}")
                                
                            new_score = min(100, score + confluence_bonus)
                            final_decision['trade_signal']['confidence_score'] = f"{new_score}/100"
                            
                except Exception as e:
                    logger.error(f"Dual Big Player Filter Error: {e}")
                    # On error, we proceed but log it (or could default to safe mode)
            
            # --- CNS PERCEPTION RECORDING ---
            final_decision['telemetry'] = full_telemetry
            if hasattr(self, 'cns'):
                self.cns.record_perception(final_decision)
                
            # Return valid signal (passed or filtered)
            # --- AI AUTONOMY (JARVIS UNLEASHED) ---
            # User Request: Trust AI logic over hard thresholds
            ai_signal = final_decision.get('trade_signal', {}).get('direction', 'NEUTRAL')
            
            if score >= self.scoring_matrix.minimum_trade_score:
                if self.hud_enabled:
                    self._sync_to_hud(final_decision)
                return final_decision
                
            elif ai_signal in ['CALL', 'PUT', 'BUY', 'SELL']:
                # Override Low Score if AI is Convincingly Directional
                logger.info(f"🧠 JARVIS UNLEASHED: Overriding Score {score} (<{self.scoring_matrix.minimum_trade_score}) because Advisor says {ai_signal}")
                
                # Boost confidence slightly to represent "Autonomy"
                if score < 75:
                   final_decision['trade_signal']['confidence_score'] = f"{score}/100 (Autonomy)"
                
                if self.hud_enabled:
                    self._sync_to_hud(final_decision)
                return final_decision
                
            else:
                return self._get_no_trade_signal(f"Score too low: {score}/100")
                
        except Exception as e:
            logger.error(f"SwingScalp analysis error: {e}")
            return self._get_no_trade_signal(f"Analysis error: {str(e)}")
            
    def _neural_global_synthesis(self, telemetry, part_results, mtf_context=None, options_walls=None, math_signal=0, math_confidence=0, data=None):
        """Phase 15: The Neural Cortex (New Unified AI Brain)"""
        logger.info("🧠 CORTEX: Analyzing all 12 GPU parts...")
        current_price = float(data['close'].iloc[-1]) if data is not None and len(data) > 0 else 0.0
        
        # Run Quantum if available
        quantum_res = None
        if hasattr(self, 'brains') and 'quantum_v5' in getattr(self, 'brains', {}):
            quantum_res = self.brains['quantum_v5'].simulate(data)
            
        result = self.neural_cortex.analyze(
            part_results=part_results,
            current_price=current_price,
            market_context=self.market_context,
            quantum_data=quantum_res,
            mtf_context=mtf_context
        )
        
        # Ensure quantum data is passed down
        result['quantum_data'] = quantum_res
        
        # Professional display
        try:
            from professional_display import ProfessionalSignalDisplay
            display = ProfessionalSignalDisplay()
            merged_display = {
                'direction': result.get('bias', 'NEUTRAL'),
                'confidence': result.get('confidence', 0),
                'entry_price': current_price,
                'ai_reason': result.get('reasoning', ''),
            }
            display.display_full_signal(merged_display)
        except Exception as e:
            logger.warning(f"Display error: {e}")
            
        return result

    def _sync_to_hud(self, signal_data):
        """Push latest intelligence to the web HUD"""
        try:
            payload = {
                "thoughts": signal_data.get('intelligence_board', []),
                "regime": signal_data.get('market_context', {}).get('regime', 'NEUTRAL'),
                "signal": signal_data.get('trade_signal', {}),
                "market_data": {
                    "price": signal_data.get('trade_signal', {}).get('entry_price'),
                    "volatility": signal_data.get('market_context', {}).get('volatility')
                }
            }
            # Add CNS Data if available
            if hasattr(self, 'cns'):
                payload['cns_diagnostic'] = {
                    "health": self.cns.health_status,
                    "report": self.cns.last_diagnostic
                }
            # Fire and forget update (with proper error handling)
            def safe_hud_post():
                try:
                    requests.post(self.hud_url, json=payload, timeout=5)
                except Exception:
                    pass  # Silently ignore HUD failures
            threading.Thread(target=safe_hud_post, daemon=True).start()
        except Exception:
            pass
            
    def _get_market_context(self, data):
        """Get current market context"""
        volatility = float(data['close'].pct_change().std() or 0.0)
        trend = self._get_trend_direction(data)
        mood = self._get_market_mood(data)
        
        # Calculate volatility status
        if volatility > 0.005: 
            vol_status = 'HIGH'
        elif volatility < 0.001: 
            vol_status = 'LOW'
        else: 
            vol_status = 'NORMAL'
        
        return {
            'volatility': volatility,
            'volatility_status': vol_status,
            'trend': trend,
            'mood': mood,
            'session': self._get_current_session(),
            'timestamp': datetime.now().isoformat()
        }
        
    def _get_trend_direction(self, data):
        """Get market trend direction"""
        if len(data) < 10:
            return 'SIDEWAYS'
            
        sma_5 = data['close'].rolling(5).mean().iloc[-1]
        sma_10 = data['close'].rolling(10).mean().iloc[-1]
        
        if sma_5 > sma_10 * 1.001:
            return 'UPTREND'
        elif sma_5 < sma_10 * 0.999:
            return 'DOWNTREND'
        else:
            return 'SIDEWAYS'
            
    def _get_market_mood(self, data):
        """Get market mood/condition from Engine"""
        try:
            if 'market_mood_engine' in self.brains:
                return self.brains['market_mood_engine'].detect_mood(data)
            
            # Fallback
            volatility = float(data['close'].pct_change().std() or 0.0)
            if volatility > 0.005: return 'VOLATILE'
            elif volatility < 0.001: return 'RANGING'
            else: return 'NORMAL'
        except Exception:
            return 'NORMAL'
            
    def _get_current_session(self):
        """Get current trading session"""
        current_hour = datetime.now().hour
        for session, times in TRADING_SESSIONS.items():
            if times['start'] <= current_hour < times['end']:
                return session
        return 'OVERNIGHT'
        
    def _generate_ollama_ceo_prompt(self, score: float, detailed_scores: Dict, telemetry: Dict = None) -> str:
        """Generate Ollama prompt for Supreme Commander AI (CEO) Master Verdict"""
        thoughts = detailed_scores.get('thoughts', [])
        mtf_matrix = detailed_scores.get('mtf_matrix', {})
        walls = detailed_scores.get('options_walls', {})
        
        prompt = f"""You are the Supreme Commander AI (CEO) of an elite multi-agent quantitative trading system.

Executive Voting Matrix & Telemetry:
- Overall System Pulse Score: {score}/100
- Multi-Timeframe Matrix: {json.dumps(mtf_matrix, default=str)}
- Sub-Agent Insights: {json.dumps(thoughts[:6], default=str)}
- Options Walls (Smart Money): {json.dumps(walls, default=str)}

Task: Review the sub-agent consensus. You hold supreme executive authority over trade execution.
- If sub-agents are in high alignment and risk parameters are clean: issue [CEO_VERDICT: EXECUTE].
- If sub-agents are conflicting or market risk is elevated: issue [CEO_VERDICT: STANDBY].
- If sub-agents show severe divergence or trap signals: issue [CEO_VERDICT: ABORT].

Respond with EXACTLY ONE of the following tags at the beginning of your response:
- [CEO_VERDICT: EXECUTE]
- [CEO_VERDICT: STANDBY]
- [CEO_VERDICT: ABORT]

Follow the tag with a 1-sentence CEO executive directive.
"""
        return prompt

    def _get_deepseek_validation(self, data, score, detailed_scores, telemetry=None):
        """Get AI validation for trade setup using local Supreme Commander AI (CEO) via Ollama"""
        try:
            prompt = self._generate_ollama_ceo_prompt(score, detailed_scores, telemetry)
            response, err = call_ollama(prompt, timeout=60)
            
            if response and not err:
                raw_text = response.strip()
                if "[CEO_VERDICT: EXECUTE]" in raw_text.upper() or "EXECUTE" in raw_text.upper():
                    verdict = "EXECUTE"
                    approved = True
                elif "[CEO_VERDICT: ABORT]" in raw_text.upper() or "ABORT" in raw_text.upper():
                    verdict = "ABORT"
                    approved = False
                else:
                    verdict = "STANDBY"
                    approved = False

                print(f"[JARVIS SUPREME COMMANDER] Verdict: [{verdict}] | {raw_text}")
                return {'approved': approved, 'reason': raw_text, 'verdict': verdict}
            else:
                print(f"[JARVIS SUPREME COMMANDER] Ollama CEO skipped or unavailable: {err}")
                return {'approved': True, 'reason': 'Supreme Commander AI offline, proceeding with local logic', 'verdict': 'BYPASS'}
        except Exception as e:
            logger.error(f"Supreme Commander AI validation error: {e}")
            return {'approved': True, 'reason': f"Validation error: {e}", 'verdict': 'ERROR'}
            
    def _create_deepseek_prompt(self, data, score, detailed_scores, telemetry=None):
        """Create prompt for DeepSeek ASI synthesis with Universal MTF and Sensory Telemetry"""
        current_candle = data.iloc[-1]
        direction = "BULLISH" if current_candle['close'] > current_candle['open'] else "BEARISH"
        thoughts = detailed_scores.get('thoughts', [])
        mtf_matrix = detailed_scores.get('mtf_matrix', {})
        walls = detailed_scores.get('options_walls', {})
        
        prompt = f"""
        ### JARVIS AI MASTER JUDGE ###
        You are the Master AI Judge of the Jarvis trading system.
        Analyze this BTC trade signal and give a final APPROVE or REJECT decision.
        
        Pulse Score: {score}/100
        Proposed Direction: {direction}
        
        ## MTF MATRIX (1m to 4h):
        {json.dumps(mtf_matrix, indent=2, cls=NumpyEncoder)}
        
        ## COMPONENT THOUGHTS:
        {chr(10).join(['- ' + t for t in thoughts[:5]])}
        
        ## OPTIONS WALLS:
        - Support: {walls.get('support')}
        - Resistance: {walls.get('resistance')}
        - Max Pain: {walls.get('max_pain')}
        
        ## YOUR TASK:
        1. Check if 1m signal aligns with 1h/4h trend.
        2. APPROVE if score >= 60 AND signals agree. REJECT if score < 60 OR conflicting signals.
        
        IMPORTANT: Respond ONLY in ENGLISH. Keep reason SHORT (max 1-2 lines).
        
        Respond EXACTLY in this format:
        DECISION: [APPROVE/REJECT]
        REASON: <Short English reason, max 2 lines>
        """
        return prompt
        
    def _extract_rejection_reason(self, content):
        """Extract rejection reason from AI response or Master Synthesis format"""
        try:
            # Try to find REASON: header first
            if 'REASON:' in content:
                reason = content.split('REASON:')[1].strip()
                return reason
            
            # Fallback to line scanning
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'reject' in line.lower() or 'reason' in line.lower():
                    if i + 1 < len(lines):
                        return lines[i + 1].strip()
                    else:
                        return line.strip()
            return content[:200] # Return raw start as fallback
        except Exception:
            return "AI rejected without specific parseable reason"
        
    def _generate_trade_signal(self, data, score, detailed_scores, options_intel=None, logic_signal=0):
        """Generate complete trade trade signal with Universal Pricing"""
        current_candle = data.iloc[-1]
        current_price = float(current_candle['close'])
        
        # Determine direction from logic_signal (Council Decision), not candle color
        if logic_signal == 1:
            direction = "CALL"
        elif logic_signal == -1:
            direction = "PUT"
        else:
            direction = "NO_TRADE"
            
        # Optimize expiry based on volatility and score
        volatility = self.market_context['volatility']
        recommended_expiry = self.expiry_optimizer.recommend_trade_type(score, volatility, "REGULAR")
        
        # --- NEW: UNIVERSAL PRICING (ENTRY/TP/SL) ---
        mtf_matrix = detailed_scores.get('mtf_matrix', {})
        scalp_targets = self.scalping_engine.calculate_targets(
            data, direction, current_price, 
            options_data=detailed_scores.get('options_walls'), 
            mtf_data=mtf_matrix
        )
        
        # Create comprehensive signal
        signal = {
            'trade_signal': {
                'direction': direction,
                'confidence_score': f"{score}/100",
                'recommended_expiry': recommended_expiry,
                'entry_price': current_price,
                'take_profit_1': scalp_targets.get('take_profit_1') if scalp_targets else None,
                'take_profit_2': scalp_targets.get('take_profit_2') if scalp_targets else None,
                'stop_loss': scalp_targets.get('stop_loss') if scalp_targets else None,
                'options_magnet': scalp_targets.get('options_magnet') if scalp_targets else None
            },
            
            'intelligence_board': detailed_scores.get('thoughts', []),
            'ai_validation': detailed_scores.get('ai_synthesis', 'Standard Protocol'),
            
            'market_context': {
                'regime': f"MTF Alignment Score: {detailed_scores.get('universal_mtf_confluence', 0)}",
                'volatility': self.market_context['volatility_status'],
                'target_summary': f"TP1: {scalp_targets.get('take_profit_1') if scalp_targets else 'N/A'}"
            }
        }
        
        # UI Log display
        # UI Log display
        ai_reasoning = (detailed_scores.get('neural_synthesis') or {}).get('reasoning', 'Math Consensus')
        
        # Prepare data for Professional Display
        math_signal = {
            'direction': direction,
            'confidence': int(score),
            'breakdown': '' # Todo: extract if needed
        }
        
        quantum_signal = {
            'prediction': 'UNKNOWN', # Todo: pass actual quantum
            'confidence': 0,
            'thought': 'N/A'
        }
        
        ai_signal = {
            'bias': direction, # Using Math/Consensus as AI for now
            'confidence': int(score),
            'reasoning': ai_reasoning
        }
        
        final_decision = {
            'direction': direction,
            'confidence': int(score),
            'entry': signal['trade_signal'].get('entry_price', 0),
            'tp1': signal['trade_signal']['take_profit_1'],
            'tp2': signal['trade_signal']['take_profit_2'],
            'sl': signal['trade_signal']['stop_loss']
        }
        
        # Display Professional Signal
        # We construct a unified signal dict for the new method
        unified_signal_data = {
            'direction': direction,
            'confidence': int(score),
            'ai_reason': ai_reasoning,
            'entry_price': signal['trade_signal'].get('entry_price', 0),
            # TPs/SLs are calculated dynamically in display_full_signal based on strategy
        }
        
        pro_display.display_full_signal(unified_signal_data, current_price=signal['trade_signal'].get('entry_price', 0))
        
        return signal

    def _identify_pattern_type(self, data, direction):
        """Identify the specific pattern type"""
        current_candle = data.iloc[-1]
        body_size = abs(float(current_candle['close']) - float(current_candle['open']))
        candle_range = float(current_candle['high']) - float(current_candle['low'])
        
        if candle_range == 0:
            return 'UNKNOWN'
            
        body_ratio = body_size / candle_range
        
        if body_ratio > 0.7:
            return 'MOMENTUM_SCALP'
        elif self.scoring_matrix._is_rejection_candle(current_candle):
            return 'REJECTION_PLAY'
        else:
            return 'TREND_PULLBACK'
            
    def _get_entry_timing(self, data, direction):
        """Determine optimal entry timing and price"""
        current_candle = data.iloc[-1]
        current_price = float(current_candle['close'])
        
        # If strong momentum candle, enter immediately at market
        body_size = abs(float(current_candle['close']) - float(current_candle['open']))
        candle_range = float(current_candle['high']) - float(current_candle['low'])
        
        if candle_range > 0 and body_size / candle_range > 0.6:
            return f"MARKET ({current_price:.2f})"
        else:
            # Recommend a limit order entry for better R:R
            if direction == "CALL":
                entry_target = current_price * 0.9995  # 0.05% Pullback
                return f"LIMIT ({entry_target:.2f})"
            else:
                entry_target = current_price * 1.0005  # 0.05% Pullback
                return f"LIMIT ({entry_target:.2f})"
            
    def _get_key_level(self, data, current_price):
        """Identify key support/resistance level"""
        if len(data) < 10:
            return 'UNKNOWN'
            
        recent_high = float(data['high'].tail(10).max())
        recent_low = float(data['low'].tail(10).min())
        
        dist_to_high = abs(current_price - recent_high) / (recent_high - recent_low + 1e-12)
        dist_to_low = abs(current_price - recent_low) / (recent_high - recent_low + 1e-12)
        
        if dist_to_high < 0.1:
            return 'IMMEDIATE_RESISTANCE'
        elif dist_to_low < 0.1:
            return 'IMMEDIATE_SUPPORT'
        else:
            return 'RANGE_BOUND'
            
    def _get_avoid_levels(self, data, current_price, direction):
        """Get price levels to avoid"""
        if len(data) < 5:
            return 'NONE'
            
        if direction == 'CALL':
            recent_high = float(data['high'].tail(5).max())
            return f"Avoid above {recent_high:.5f}"
        else:
            recent_low = float(data['low'].tail(5).min())
            return f"Avoid below {recent_low:.5f}"
            
    def _get_exit_conditions(self, direction):
        """Get early exit conditions"""
        if direction == 'CALL':
            return "Price breaks below entry level"
        else:
            return "Price breaks above entry level"
            
    def _get_no_trade_signal(self, reason):
        """Generate no-trade signal"""
        return {
            'trade_signal': {
                'direction': 'NO_TRADE',
                'confidence_score': '0/100',
                'recommended_expiry': 'N/A',
                'entry_timing': 'N/A',
                'expected_payout_ratio': 'N/A'
            },
            'no_trade_reason': reason,
            'timestamp': datetime.now().isoformat()
        }

    # ==================== EXISTING JARVIS METHODS (ENHANCED) ====================

    def process_data(self, data):
        """DEPRECATED: This method is never called. Decision flow uses analyze_trade_setup() directly.
        Kept for reference only. See _live_mode_with_deepseek() below."""
        import warnings
        warnings.warn("process_data() is dead code — not called anywhere. Use analyze_trade_setup() instead.", DeprecationWarning, stacklevel=2)
        start_time = time.time()
        try:
            # 1. Deep Multi-Timeframe Analysis (5m, 15m)
            mtf_analysis = {}
            if hasattr(self, 'mtf_buffers'):
                mtf_analysis = self.mtf_analyzer.analyze_all_timeframes(self.mtf_buffers)
            
            # 2. Get existing Jarvis analysis (1m core engine)
            existing_result = self._live_mode_with_deepseek(data)
            
            # 3. Get trade analysis (passing basic context for backward compatibility)
            mtf_context = {f"{tf}_trend": res['direction'] for tf, res in mtf_analysis.items()}
            trade_result = self.analyze_trade_setup(data, mtf_context=mtf_context)
            
            # 4. Final Directional Filter (Strict 15m Alignment)
            combined_signal = self._combine_signals(existing_result, trade_result)
            
            # STRICT MTF GATEKEEPER
            if combined_signal != 'NO-TRADE':
                tf_15m = mtf_analysis.get('15m', {})
                direction_val = 1 if combined_signal == 'CALL' else -1
                
                # If 15m trend is established and conflicts with 1m signal, block it
                if tf_15m and tf_15m['direction'] != 0 and tf_15m['direction'] != direction_val:
                    logger.warning(f"🛡️ MTF BLOCK: 1m {combined_signal} conflicts with 15m trend")
                    combined_signal = 'NO-TRADE'
                    trade_result['no_trade_reason'] = "MTF Trend Conflict (15m)"
                
                # Bonus: Check 5m for high confidence
                tf_5m = mtf_analysis.get('5m', {})
                if tf_5m and tf_5m['direction'] != 0 and tf_5m['direction'] == direction_val:
                    trade_result['mtf_confirmation'] = "5m Aligned"
            
            return {
                **existing_result,
                'trade_analysis': trade_result,
                'mtf_analysis': mtf_analysis,
                'combined_signal': combined_signal,
                'latency_ms': (time.time() - start_time) * 1000
            }
            
        except Exception as e:
            logger.error("process_data error: %s", e)
            return {'signal': 'NO-TRADE', 'confidence': 0, 'trade_type': '5m', 'latency_ms': 0}

    def _combine_signals(self, existing_result, trade_result):
        """Combine existing and trade signals safely"""
        try:
            if not trade_result or not isinstance(trade_result, dict):
                return 'NO-TRADE'
                
            trade_signal_dict = trade_result.get('trade_signal', {})
            if not isinstance(trade_signal_dict, dict):
                return 'NO-TRADE'

            trade_signal = trade_signal_dict.get('direction', 'NO_TRADE')
            if trade_signal in ['NO_TRADE', 'NO-TRADE', 0]:
                return 'NO-TRADE'
                
            existing_signal = existing_result.get('signal', 'NO-TRADE') if isinstance(existing_result, dict) else 'NO-TRADE'
            
            if existing_signal == trade_signal:
                return trade_signal
            else:
                # Conflict - use the one with higher confidence
                existing_conf = existing_result.get('confidence', 0) if isinstance(existing_result, dict) else 0
                try:
                    conf_str = trade_signal_dict.get('confidence_score', '0/100')
                    trade_conf = int(float(str(conf_str).split('/')[0]))
                except (ValueError, IndexError, AttributeError):
                    trade_conf = 0
                
                if trade_conf >= 85:
                    return trade_signal
                else:
                    return existing_signal
                    
        except Exception as e:
            logger.error(f"Signal combination error: {e}")
            return 'NO-TRADE'

    def _live_mode_with_deepseek(self, data):
        """DEPRECATED: Only called from process_data() which is itself dead code.
        The active validation path is _get_deepseek_validation() using Ollama phi3.5."""
        import warnings
        warnings.warn("_live_mode_with_deepseek() is dead code.", DeprecationWarning, stacklevel=2)
        try:
            part_results = {}
            for part_name, part in self.parts.items():
                try:
                    res = part.analyze(data)
                    part_results[part_name] = res if isinstance(res, dict) else {"signal": res, "thought": "Legacy"}
                except Exception:
                    part_results[part_name] = {"signal": 0, "thought": "Part offline"}
            
            part_signals = [res['signal'] for res in part_results.values()]
            part_details = {k: v['signal'] for k, v in part_results.items()}
            # Exclude fusion and confidence from the board to avoid 'Legacy' spam
            thoughts = [res['thought'] for k, res in part_results.items() 
                        if res['signal'] != 0 and k not in ['part11_fusion', 'part12_confidence']]
            
            
            # PROFESSIONAL SIGNAL OUTPUT WITH WEIGHTED DECISION LOGIC
            def signal_to_score(s):
                """Convert -1/0/1 or reasoning dict to 0-100 scale"""
                val = s.get('signal', 0) if isinstance(s, dict) else s
                if val == 1: return 100  # Bullish
                elif val == -1: return 0  # Bearish
                else: return 50  # Neutral
            
            def format_name(p):
                return p.replace('part', 'P').replace('_', ' ').title()
            
            # Part weights (more reliable parts get higher weight)
            part_weights = {
                'part1_breakout': 1.2,
                'part2_zone': 1.3,
                'part5_ml': 1.5,      # ML gets highest weight
                'part6_trend': 1.4,
                'part9_orderflow': 1.2,
                'part10_candlestats': 1.1,
                'part14_options_chain': 1.5,  # Options Chain (Institutional data)
            }
            
            # Convert all signals to 0-100 with weights
            weighted_scores = []
            part_scores = {}
            
            for part, signal in part_details.items():
                if part in ['part11_fusion', 'part12_confidence']:
                    continue
                score = signal_to_score(signal)
                weight = part_weights.get(part, 1.0)
                weighted_scores.append(score * weight)
                part_scores[part] = score
            
            confidence = part_details.get('part12_confidence', 0)
            
            # Calculate weighted average
            total_weight = sum(part_weights.get(p, 1.0) for p in part_scores.keys())
            avg_score = sum(weighted_scores) / total_weight if weighted_scores else 50
            
            # Count agreement (how many parts agree on direction)
            bullish_count = sum(1 for s in part_scores.values() if s >= 60)
            bearish_count = sum(1 for s in part_scores.values() if s <= 40)
            total_parts = len(part_scores)
            
            bullish_pct = (bullish_count / total_parts * 100) if total_parts > 0 else 0
            bearish_pct = (bearish_count / total_parts * 100) if total_parts > 0 else 0
            
            # Determine final decision with agreement threshold
            decision_reason = ""
            if avg_score >= 65 and bullish_pct >= 50:
                decision = "📈 CALL"
                decision_reason = f"{bullish_count}/{total_parts} parts bullish ({bullish_pct:.0f}%)"
            elif avg_score <= 35 and bearish_pct >= 50:
                decision = "📉 PUT"
                decision_reason = f"{bearish_count}/{total_parts} parts bearish ({bearish_pct:.0f}%)"
            else:
                decision = "⚪ NO-TRADE"
                if avg_score > 50:
                    decision_reason = f"Weak bullish ({bullish_pct:.0f}% agreement)"
                elif avg_score < 50:
                    decision_reason = f"Weak bearish ({bearish_pct:.0f}% agreement)"
                else:
                    decision_reason = "Market neutral"
            
            print(f"\n┌{'─'*78}┐")
            print(f"│ 🎯 JARVIS: {decision:<20} │ Score: {avg_score:.1f}/100 │ Conf: {confidence}% │")
            print(f"│ 💡 Reason: {decision_reason:<63} │")
            print(f"├{'─'*78}┤")
            print(f"│ ⏰ {datetime.now().strftime('%H:%M:%S'):<12} │ 💹 BTC/USDT 1m{' '*45} │")
            print(f"├{'─'*78}┤")
            
            # Show top 6 parts sorted by score
            sorted_parts = sorted(part_scores.items(), key=lambda x: x[1], reverse=True)
            
            print(f"│ 📊 TOP SIGNALS (Weighted):{' '*51} │")
            for part, score in sorted_parts[:6]:
                weight = part_weights.get(part, 1.0)
                bar_length = int(score / 5)
                bar = '█' * bar_length + '░' * (20 - bar_length)
                emoji = "📈" if score >= 60 else "📉" if score <= 40 else "⚪"
                weight_str = f"x{weight:.1f}" if weight != 1.0 else ""
                print(f"│ {emoji} {format_name(part):<18} {weight_str:<4} │ {bar} {score:>3.0f}/100{' '*6} │")
            
            print(f"└{'─'*78}┘")
            
            logic_signal = self.parts['part11_fusion'].analyze(list(part_results.values()))
            confidence_res = self.parts['part12_confidence'].analyze(list(part_results.values()))
            # BUG FIX #12: part12_confidence returns dict {'confidence': N} — extract the number
            confidence = confidence_res.get('confidence', 0) if isinstance(confidence_res, dict) else confidence_res
            
            # Brain Results
            quantum_res = self.brains['quantum_v5'].simulate(data)
            volume_res = self.brains['volume_pressure_brain'].analyze(data)
            trend_res = self.brains['trend_acceleration_brain'].analyze(data)
            
            # Add brain thoughts to the board
            for res in [quantum_res, volume_res, trend_res]:
                if res['signal'] != 0: thoughts.append(res['thought'])
            
            logger.info("\n" + "🧠 [INTELLIGENCE BOARD] Combined Analysis:" + "\n" + "\n".join([f" • {t}" for t in thoughts]))
            
            # BUG FIX #9: upgrades is on self.jarvis not self — use jarvis reference
            market_mood = self.upgrades['market_mood_engine'].detect_mood(data)
            market_context = {
                'volatility': float(data['close'].pct_change().std() or 0.0),
                'trend': trend_res['signal'],
                'mood': market_mood
            }
            deepseek_sentiment, sentiment_reasoning = self.deepseek_brains['deepseek_v3_sentiment'].analyze_sentiment(data, market_context)
            
            safety_res = self.brains['safety_risk_brain'].analyze(data, part_signals)
            risk_res = self.brains['risk_filter_brain'].analyze(data, logic_signal)
            
            if not safety_res['approved']: thoughts.append(safety_res['thought'])
            if not risk_res['approved']: thoughts.append(risk_res['thought'])
            
            safety_approved = safety_res['approved']
            risk_approved = risk_res['approved']
            all_signals_info = {
                'traditional_signals': part_details,
                'thoughts': thoughts,
                'advanced_signals': {
                    'quantum': quantum_res['signal'],
                    'volume': volume_res['signal'],
                    'trend': trend_res['signal'],
                    'deepseek_sentiment': deepseek_sentiment
                },
                'safety_checks': {
                    'safety_approved': safety_approved,
                    'risk_approved': risk_approved,
                    'safety_thought': safety_res['thought']
                }
            }
            r1_reasoning = self.deepseek_brains['deepseek_r1_reasoning'].complex_reasoning(all_signals_info, data, market_context)
            if r1_reasoning.get("signal") == "CALL" and safety_approved and risk_approved:
                final_signal = 1
            elif r1_reasoning.get("signal") == "PUT" and safety_approved and risk_approved:
                final_signal = -1
            else:
                final_signal = 0
            trap_res = self.upgrades['trap_candle_genome_detector'].detect_trap(data)
            if trap_res['is_trap']:
                final_signal = 0
                r1_reasoning["reasoning"] = (r1_reasoning.get("reasoning","") + f" | {trap_res['thought']}")
            
            shield_res = self.upgrades['high_volatility_regime_shield'].check_safety(data)
            if not shield_res['approved']:
                final_signal = 0
                r1_reasoning["reasoning"] = (r1_reasoning.get("reasoning","") + f" | {shield_res['thought']}")
            
            rev_res = self.upgrades['reverse_safety_engine'].check_reversal(data, final_signal)
            old_signal = final_signal  # BUG FIX #11: save before overwrite to detect change
            final_signal = rev_res['signal']
            if rev_res['signal'] != old_signal:
                r1_reasoning["reasoning"] = (r1_reasoning.get("reasoning","") + f" | {rev_res['thought']}")
            
            # GATEKEEPER: Institutional Alignment (Relaxed)
            p14_signal = part_details.get('part14_options_chain', 0)
            # BUG FIX #13: confidence is already extracted as int above in fixed code
            is_high_conf = int(confidence) >= 85
            
            if final_signal == 1:
                if p14_signal == -1: # Opposite institutional bias
                    final_signal = 0
                    r1_reasoning["reasoning"] = (r1_reasoning.get("reasoning","") + " | 🛡️ Blocked: Institutional BEARISH bias")
                elif p14_signal == 0 and not is_high_conf: # Neutral but low conf
                    final_signal = 0
                    r1_reasoning["reasoning"] = (r1_reasoning.get("reasoning","") + " | 🛡️ Blocked: Waiting for Institutional Confirm or High Confidence")
            
            elif final_signal == -1:
                if p14_signal == 1: # Opposite institutional bias
                    final_signal = 0
                    r1_reasoning["reasoning"] = (r1_reasoning.get("reasoning","") + " | 🛡️ Blocked: Institutional BULLISH bias")
                elif p14_signal == 0 and not is_high_conf: # Neutral but low conf
                    final_signal = 0
                    r1_reasoning["reasoning"] = (r1_reasoning.get("reasoning","") + " | 🛡️ Blocked: Waiting for Institutional Confirm or High Confidence")
            volatility = float(data['close'].pct_change().std() or 0.0)
            if volatility > 0.003:
                expiry = "SCALP"
            elif final_signal != 0:
                expiry = "DAY_TRADE"
            else:
                expiry = "SWING"
            if final_signal == 1:
                signal_str = "CALL"
            elif final_signal == -1:
                signal_str = "PUT"
            else:
                signal_str = "NO-TRADE"
            return {
                'signal': signal_str,
                'confidence': max(confidence, r1_reasoning.get("confidence", 0)),
                'trade_type': expiry,
                'max_trade_duration': "SWING",
                'deepseek_sentiment': deepseek_sentiment,
                'deepseek_sentiment_reasoning': sentiment_reasoning,
                'deepseek_r1_signal': r1_reasoning.get("signal", "NO-TRADE"),
                'deepseek_r1_confidence': r1_reasoning.get("confidence", 0),
                'deepseek_r1_reasoning': r1_reasoning.get("reasoning", ""),
                'deepseek_key_factors': r1_reasoning.get("key_factors", []),
                'traditional_confidence': confidence,
                'safety_flags': f"Safe: {safety_approved and risk_approved}, Mood: {market_context['mood']}",
            }
        except Exception as e:
            logger.error("live_mode error: %s", e)
            return self._live_mode_fallback(data)

    def _live_mode_fallback(self, data):
        """Your existing fallback logic"""
        try:
            part_results = {}
            for part_name, part in self.parts.items():
                try:
                    signal = part.analyze(data)
                except Exception:
                    signal = {"signal": 0, "thought": "Part offline"}
                # BUG FIX #14: ensure dict format for fusion/confidence
                if not isinstance(signal, dict):
                    signal = {"signal": signal, "thought": "Legacy"}
                part_results[part_name] = signal
            part_signals = list(part_results.values())
            logic_signal_res = self.parts['part11_fusion'].analyze(part_signals)
            confidence_res = self.parts['part12_confidence'].analyze(part_signals)
            logic_signal = logic_signal_res.get('signal', 0) if isinstance(logic_signal_res, dict) else logic_signal_res
            confidence = confidence_res.get('confidence', 0) if isinstance(confidence_res, dict) else confidence_res
            if logic_signal == 1:
                signal_str = "CALL"
            elif logic_signal == -1:
                signal_str = "PUT"
            else:
                signal_str = "NO-TRADE"
            return {
                'signal': signal_str,
                'confidence': confidence,
                'trade_type': "2m",
                'max_trade_duration': "SWING",
                'deepseek_sentiment': 0,
                'deepseek_sentiment_reasoning': "Fallback mode - DeepSeek unavailable",
                'deepseek_r1_signal': "NO-TRADE",
                'deepseek_r1_confidence': 0,
                'deepseek_r1_reasoning': "Fallback to traditional analysis",
                'safety_flags': "Fallback mode active",
            }
        except Exception as e:
            logger.error("fallback error: %s", e)
            return {'signal': 'NO-TRADE', 'confidence': 0, 'trade_type': '5m'}

# ==================== ENHANCED 4-ENGINE SYSTEM ====================

class Jarvis4EngineSystem:
    """MASTER CONTROLLER - All 4 engines with trade integration"""
    
    def __init__(self):
        self.jarvis = JarvisElite()  # Use trade-enhanced Jarvis
        self.backtest_engine = AutoBacktestEngine(self.jarvis)
        self.training_engine = AutoTrainingEngine(self.jarvis)
        self.optimizer_engine = AutoOptimizerEngine(self.jarvis)
        self.live_engine = None
        
        # --- PHASE 19: MULTI-TIMEFRAME SYSTEM ---
        try:
            from delta_multi_tf_fetcher import DeltaMultiTFDataFetcher  # type: ignore
            from smart_tpsl_calculator import SmartTPSLCalculator  # type: ignore
            from multi_tf_engine import MultiTimeframeEngine  # type: ignore
            from trading_config import TRADING_CONFIG, get_active_config  # type: ignore
            
            self.delta_multi_tf = DeltaMultiTFDataFetcher(delta_client=self.jarvis.delta_data)
            self.tpsl_calculator = SmartTPSLCalculator(trading_config=get_active_config())
            self.multi_tf_engine = MultiTimeframeEngine(
                jarvis_system=self.jarvis,
                delta_fetcher=self.delta_multi_tf,
                tpsl_calculator=self.tpsl_calculator,
                config=TRADING_CONFIG
            )
            self.trading_config = TRADING_CONFIG
            logger.info("✅ Multi-Timeframe System Initialized")
        except Exception as e:
            logger.debug(f"Multi-TF system not available (optional): {e}")
            self.multi_tf_engine = None
            self.trading_config = {'mode': 'trade'}  # Fallback to trade
        
        # Data storage
        self.historical_data = None
        self.backtest_results = None
        self.optimized_params = None
        
    def run_complete_system(self, historical_data=None):
        """Run all 4 engines with trade optimization"""
        logger.info("🤖 JARVIS LIVE TRADING SYSTEM STARTING...")
        logger.info("🎯 MODE: DIRECT LIVE (Backtest & Training SKIPPED)")
        logger.info("=" * 60)
        
        # ─── BACKTEST & TRAINING SKIPPED ────────────────────────────
        # Set JARVIS_RUN_BACKTEST=1 in environment to re-enable them
        run_backtest = os.getenv('JARVIS_RUN_BACKTEST', '0') == '1'
        
        self.backtest_results = {}
        training_results = {}
        self.optimized_params = {}
        
        if run_backtest:
            # Backtest Mode (only when env var is set)
            if historical_data is None:
                historical_data = self._generate_sample_data()
            self.historical_data = historical_data
            
            logger.info("🔹 PHASE 1: AUTO-BACKTEST SYSTEM ACTIVATED 📊")
            self.backtest_results = self.backtest_engine.run_backtest(historical_data)
            
            logger.info("🔹 PHASE 2: AUTO-TRAINING SYSTEM UNLOCKED 🧠")
            training_results = self.training_engine.train_models(historical_data)
        else:
            logger.info("⚡ BACKTEST & TRAINING: SKIPPED (Direct Live Mode)")
            logger.info("   (To run backtest, set env var: JARVIS_RUN_BACKTEST=1)")
        
        # Step 4️⃣: LIVE TRADING ENGINE - Always runs
        logger.info("🔹 LIVE TRADING ENGINE: STARTING NOW 🚀")
        self.live_engine = LiveTradingEngine(self.jarvis, self.optimized_params)
        live_status = self.live_engine.start_live_trading()
        
        # Final summary
        self._print_final_summary()
        
        return {
            'backtest': self.backtest_results,
            'training': training_results,
            'optimization': self.optimized_params,
            'live_trading': live_status,
            'trade_stats': self.jarvis.trade_manager.get_performance_stats() if hasattr(self.jarvis.trade_manager, 'get_performance_stats') else {}
        }
    
    def analyze_multi_tf(self, symbol='BTC', mode=None):
        """
        Analyze using Multi-Timeframe System (Phase 19)
        
        Args:
            symbol: Trading symbol (default: 'BTC')
            mode: 'scalping' or 'swing' (uses config default if None)
        
        Returns:
            Signal with TP/SL levels and Multi-TF confluence
        """
        if not self.multi_tf_engine:
            logger.error("Multi-TF Engine not available. Using fallback trade mode.")
            # Fallback to single TF analysis
            from delta_api_wrapper import DeltaExchangeData
            data_wrapper = DeltaExchangeData()
            data = data_wrapper.get_historical_candles(symbol="BTCUSDT", resolution="1m", limit=100)
            if data:
                import pandas as pd
                df = pd.DataFrame(data)
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col])
                return self.jarvis.analyze_trade_setup(df)
            return None
        
        # Use Multi-TF Engine
        return self.multi_tf_engine.analyze(symbol=symbol, mode=mode)

    def _generate_sample_data(self):
        """Fetch REAL historical data from Delta Exchange (FIXED: No more fake $100 data!)"""
        try:
            from delta_api_wrapper import DeltaExchangeData
            logger.info("📡 [BACKTEST/TRAINING] Fetching REAL data from Delta Exchange...")
            
            delta = DeltaExchangeData()
            # Fetch last 500 minutes of data for backtesting (real BTC ~$69k)
            candles = delta.get_historical_candles(symbol="BTCUSDT", resolution="1m", limit=500)
            
            if candles and len(candles) > 0:
                data = pd.DataFrame({
                    'timestamp': [pd.to_datetime(c['time'], unit='s') for c in candles],
                    'open': [float(c['open']) for c in candles],
                    'high': [float(c['high']) for c in candles],
                    'low': [float(c['low']) for c in candles],
                    'close': [float(c['close']) for c in candles],
                    'volume': [float(c.get('volume') or 0.0) for c in candles]
                })
                
                logger.info(f"✅ [BACKTEST] Loaded {len(data)} REAL candles | BTC: ${data['close'].iloc[-1]:,.2f}")
                return data
            else:
                logger.warning("⚠️ Delta returned no data for backtest. Using fallback.")
                raise Exception("No Delta data")
                
        except Exception as e:
            logger.error(f"❌ [BACKTEST] Real data fetch failed: {e}")
            # Fallback: Try to at least use current real price
            try:
                from delta_api_wrapper import DeltaExchangeData
                current_price = DeltaExchangeData().get_live_price("BTCUSDT")
                if current_price > 1000:
                    logger.info(f"🔄 [BACKTEST] Using baseline ${current_price:,.2f}")
                    dates = pd.date_range(start='2024-01-01', periods=500, freq='1min')
                    rng = np.random.default_rng(seed=42)  # BUG FIX #17: seed for reproducibility
                    prices = [current_price * (1 + rng.normal(0, 0.0005)) for _ in range(500)]
                    return pd.DataFrame({
                        'timestamp': dates,
                        'open': prices,
                        'high': [p * 1.001 for p in prices],
                        'low': [p * 0.999 for p in prices],
                        'close': prices,
                        'volume': np.random.randint(1000, 10000, 500)
                    })
            except Exception:
                pass
                
            # Last resort: Generate synthetic data to allow system to start
            logger.warning("⚠️ Using synthetic BTC data for backtest startup (Delta offline). Live trading will use real data.")
            base_price = 87000.0  # Approximate BTC price
            dates = pd.date_range(end=pd.Timestamp.now(), periods=500, freq='1min')
            rng = np.random.default_rng(seed=42)
            prices = [base_price]
            for _ in range(499):
                prices.append(prices[-1] * (1 + rng.normal(0, 0.0005)))
            return pd.DataFrame({
                'timestamp': dates,
                'open': prices,
                'high': [p * 1.001 for p in prices],
                'low': [p * 0.999 for p in prices],
                'close': prices,
                'volume': rng.integers(1000, 10000, 500)
            })


    def _print_final_summary(self):
        """Print final system summary"""
        logger.info("=" * 60)
        logger.info("🎉 JARVIS 4-ENGINE TRADE SYSTEM - COMPLETE!")
        logger.info("=" * 60)
        
        if self.backtest_results:
            logger.info(f"📊 BACKTEST RESULTS:")
            logger.info(f"   Win Rate: {self.backtest_results.get('overall_win_rate', 0):.1f}%")
            logger.info(f"   Total Trades: {self.backtest_results.get('total_trades', 0)}")
            logger.info(f"   Best Expiry: {self.backtest_results.get('trade_type', '2m')}")
        
        if self.optimized_params:
            logger.info(f"⚡ OPTIMIZED PARAMETERS:")
            logger.info(f"   Volatility Regimes: Applied")
            logger.info(f"   Signal Weights: Optimized") 
            logger.info(f"   Safety Filters: Calibrated")
        
        logger.info(f"🎯 TRADE TRADING: ACTIVE")
        logger.info(f"⏱️  TRADE OPTIMIZATION: Scalp & Swing")
        logger.info(f"🤖 DEEPSEEK AI JUDGE: ENABLED (validates signals with score >= 10)")  # Judge now active
        logger.info("=" * 60)

# ==================== MAIN EXECUTION ====================

def main():
    """Main function with trade trading system"""
    logger.info("🚀 JARVIS TRADE ELITE v7.0 - FULLY INTEGRATED")
    logger.info("==========================================")
    
    # Initialize the complete trade system
    jarvis_trade = Jarvis4EngineSystem()
    
    try:
        # Run all 4 engines automatically
        results = jarvis_trade.run_complete_system()
        
        # Ask user if they want to start live trading
        if os.getenv("JARVIS_AUTO_LIVE") == "1" or input("\n🎯 Start LIVE SwingScalp Trading? (y/n): ").strip().lower() == 'y':
            logger.info("Starting LIVE SwingScalp Trading...")
            
            # Demo trade analysis
            sample_data = jarvis_trade._generate_sample_data()
            trade_result = jarvis_trade.jarvis.analyze_trade_setup(sample_data.tail(50))
            
            print("\n🎯 TRADE TRADING SIGNAL:")
            try:
                pro_display.display_full_signal(trade_result)
            except Exception as e:
                logger.error(f"Error displaying signal: {e}")
                print(json.dumps(trade_result, indent=2, cls=NumpyEncoder))
            
        else:
            logger.info("LIVE trading cancelled. System ready for manual use.")
            
    except Exception as e:
        logger.error(f"System error: {e}")

if __name__ == "__main__":
    main()
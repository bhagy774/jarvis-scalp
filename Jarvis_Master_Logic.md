# JARVIS MASTER TRADING LOGIC (RAG KNOWLEDGE BASE)

This document contains the core institutional trading rules, AI fusion logic, and risk management strategies extracted directly from the Jarvis codebase. It is designed to act as the primary knowledge base for the local Ollama RAG system.

## MODULE: part1_FIXED.py

### Component: TrendBrain
Handles specific market analysis and logic for TrendBrain.

- **Capability**: System can analyze trend

### Component: VolatilityBrain
Handles specific market analysis and logic for VolatilityBrain.

- **Capability**: System can analyze volatility

### Component: StrengthBrain
Handles specific market analysis and logic for StrengthBrain.

- **Capability**: System can analyze strength

### Component: RiskBrain
Handles specific market analysis and logic for RiskBrain.

- **Capability**: System can analyze risk

### Component: ReversalBrain
Handles specific market analysis and logic for ReversalBrain.

- **Capability**: System can analyze reversal

### Component: RegimeBrain
Handles specific market analysis and logic for RegimeBrain.

- **Capability**: System can analyze regime

### Component: DeepSeekBrain
Handles specific market analysis and logic for DeepSeekBrain.

- **Capability**: System can analyze deepseek

### Component: EvolutionBrain
Handles specific market analysis and logic for EvolutionBrain.

- **Capability**: System can analyze evolution

### Component: MemoryBrain
Handles specific market analysis and logic for MemoryBrain.

- **Capability**: System can analyze memory

### Component: SelfHealingBrain
Handles specific market analysis and logic for SelfHealingBrain.

- **Capability**: System can analyze self heal

### Component: MetaFusionBrain
Handles specific market analysis and logic for MetaFusionBrain.

- **Capability**: System can analyze meta fusion

### Component: MiniR1Brain
Handles specific market analysis and logic for MiniR1Brain.

- **Capability**: System can analyze mini r1

### Component: MiniV3Brain
Handles specific market analysis and logic for MiniV3Brain.

- **Capability**: System can analyze mini v3

### Component: SmartBreakoutAI
Handles specific market analysis and logic for SmartBreakoutAI.

- **Capability**: System can detect smart levels
- **Capability**: System can detect liquidity
- **Capability**: System can detect breakout
- **Capability**: System can detect fakeout
- **Capability**: System can detect pullback
- **Capability**: System can detect momentum
- **Capability**: System can detect orderflow
- **Capability**: System can detect ml features
- **Capability**: System can detect regime
- **Capability**: System can apply risk brain
- **Rule/Logic (_generate_ollama_prompt)**: Format clean prompt for Ollama Local AI Reasoning
- **Capability**: System can analyze
- **Capability**: System can generate signal

## MODULE: part2_FIXED.py

### Component: ZonePointFiveDetectorGPU
Stub: Implemented in Part 1 (SmartBreakoutAI). Detects 0.5 zone signals.

- **Capability**: System can detect 0 5 zone signals

### Component: CandlePsychologyMasterGPU
Stub: Implemented in Part 1 (SmartBreakoutAI). Analyzes candle psychology.

- **Capability**: System can analyze candle psychology

### Component: LSTMPredictor
LSTM Neural Network for Time Series Prediction


### Component: TransformerPredictor
Transformer Model for Market Pattern Recognition


### Component: AutoUpdateSystem
FIX #15: DISABLED — Remote Code Execution Risk
This class previously downloaded code from GitHub (wrong repo) and overwrote local files.
Kept as stub to avoid breaking any references.


### Component: VolumeProfileBrainGPU
Advanced Volume Analysis and Profiling

- **Rule/Logic (analyze_volume_profile)**: GPU-accelerated volume profile analysis
- **Rule/Logic (detect_volume_signals)**: Detect trading signals based on volume analysis
- **Rule/Logic (detect_volume_spike)**: Detect volume spikes compared to recent average

### Component: MarketStructureBrainGPU
Market Structure Analysis and Identification

- **Rule/Logic (analyze_market_structure)**: GPU-accelerated market structure analysis
- **Rule/Logic (_analyze_structure_changes)**: Analyze changes in market structure

### Component: OrderFlowBrainGPU
Order Flow and Liquidity Analysis

- **Rule/Logic (analyze_order_flow)**: Analyze order flow and liquidity conditions
- **Rule/Logic (_calculate_order_imbalances)**: Calculate buy/sell order imbalances
- **Rule/Logic (_detect_absorption)**: Detect absorption patterns in order flow

### Component: MomentumOscillatorBrainGPU
Advanced Momentum and Oscillator Analysis

- **Rule/Logic (calculate_all_oscillators)**: Calculate all momentum oscillators using GPU acceleration
- **Rule/Logic (_calculate_rsi_gpu)**: GPU-accelerated RSI calculation
- **Rule/Logic (_calculate_stochastic_gpu)**: GPU-accelerated Stochastic calculation
- **Rule/Logic (_calculate_macd_gpu)**: GPU-accelerated MACD calculation
- **Rule/Logic (_calculate_ema_gpu)**: Calculate EMA on GPU
- **Rule/Logic (_calculate_momentum_gpu)**: Calculate price momentum on GPU
- **Rule/Logic (_detect_divergences)**: Detect momentum divergences

### Component: VolatilityRegimeBrainGPU
Volatility Regime Detection and Analysis

- **Rule/Logic (analyze_volatility_regime)**: Analyze current volatility regime using GPU acceleration
- **Rule/Logic (_calculate_volatility_gpu)**: GPU-accelerated volatility calculation
- **Rule/Logic (_detect_volatility_breakouts)**: Detect volatility breakout signals
- **Rule/Logic (_detect_volatility_squeeze)**: Detect volatility squeeze signals
- **Rule/Logic (_calculate_bb_width)**: Calculate Bollinger Band width
- **Rule/Logic (_calculate_kc_width)**: Calculate Keltner Channel width

### Component: CycleAnalysisBrainGPU
Market Cycle Analysis and Identification

- **Rule/Logic (analyze_market_cycles)**: Analyze market cycles using GPU-accelerated methods
- **Rule/Logic (_detect_dominant_cycle_fft)**: Detect dominant cycle using Fast Fourier Transform
- **Rule/Logic (_calculate_cycle_phase)**: Calculate current cycle phase

### Component: CorrelationMatrixBrainGPU
Inter-market Correlation Analysis

- **Rule/Logic (analyze_correlations)**: Analyze correlations between primary asset and correlated assets
- **Rule/Logic (_calculate_returns_gpu)**: Calculate returns on GPU
- **Rule/Logic (_calculate_correlation_gpu)**: Calculate correlation coefficient on GPU
- **Rule/Logic (_detect_correlation_regime)**: Detect correlation regime changes

### Component: PatternRecognitionBrainGPU
Advanced Chart Pattern Recognition

- **Rule/Logic (_detect_double_top_bottom)**: Detect double top and double bottom patterns
- **Rule/Logic (_detect_head_shoulders)**: Detect head and shoulders patterns
- **Rule/Logic (_detect_triangle_patterns)**: Detect triangle patterns (symmetrical, ascending, descending)
- **Rule/Logic (_calculate_slope_gpu)**: Calculate slope of data using linear regression on GPU
- **Rule/Logic (_detect_flag_pennants)**: Detect flag and pennant patterns

### Component: SupportResistanceBrainGPU
Dynamic Support and Resistance Level Calculation

- **Rule/Logic (calculate_support_resistance)**: Calculate dynamic support and resistance levels
- **Rule/Logic (_calculate_pivot_points)**: Calculate pivot point levels
- **Rule/Logic (_calculate_swing_points)**: Calculate support/resistance from swing points
- **Rule/Logic (_calculate_volume_weighted_levels)**: Calculate volume-weighted support/resistance levels
- **Rule/Logic (_calculate_ma_levels)**: Calculate moving average based support/resistance

### Component: TrendAnalysisBrainGPU
Multi-timeframe Trend Analysis

- **Rule/Logic (analyze_multi_timeframe_trends)**: Analyze trends across multiple timeframes
- **Rule/Logic (_analyze_single_timeframe_trend)**: Analyze trend for a single timeframe
- **Rule/Logic (_analyze_multi_tf_alignment)**: Analyze alignment of trends across timeframes

### Component: MarketRegimeBrainGPU
Market Condition and Regime Detection

- **Rule/Logic (detect_market_regime)**: Detect current market regime
- **Rule/Logic (_detect_volatility_regime)**: Detect volatility-based regime
- **Rule/Logic (_detect_trend_regime)**: Detect trend-based regime
- **Rule/Logic (_detect_volume_regime)**: Detect volume-based regime

### Component: PriceActionBrainGPU
Pure Price Action Analysis

- **Rule/Logic (analyze_price_action)**: Analyze pure price action patterns
- **Rule/Logic (_detect_pin_bars)**: Detect pin bar (rejection) patterns
- **Rule/Logic (_detect_inside_bars)**: Detect inside bar patterns
- **Rule/Logic (_detect_outside_bars)**: Detect outside bar patterns
- **Rule/Logic (_detect_engulfing_bars)**: Detect engulfing bar patterns

### Component: InstitutionalFlowBrainGPU
Smart Money and Institutional Flow Tracking

- **Rule/Logic (analyze_institutional_flow)**: Analyze institutional order flow and smart money activity
- **Rule/Logic (_detect_accumulation)**: Detect accumulation patterns (smart money buying)
- **Rule/Logic (_detect_distribution)**: Detect distribution patterns (smart money selling)
- **Rule/Logic (_detect_unusual_activity)**: Detect unusual trading activity

### Component: SignalFusionBrainGPU
Multi-Brain Signal Fusion and Confidence Weighting

- **Rule/Logic (fuse_signals)**: Fuse signals from all brains with intelligent weighting
- **Rule/Logic (_fuse_single_direction)**: Fuse signals for a single direction (CALL or PUT)

### Component: AdvancedAnalysisSystem
Master system coordinating all 16 analysis brains

- **Rule/Logic (_generate_ollama_prompt)**: Format clean prompt for Ollama Local AI Reasoning

## MODULE: part3_FIXED.py

### Component: CandlePsychologyMasterGPU
INSTITUTIONAL CANDLESTICK PSYCHOLOGY & PRICE ACTION ENGINE (Part 3)
- ATR-Relative Significance Filter (blocks micro-noise and flat-candle hallucinations)
- Rejection Analysis: Hammers, Shooting Stars, Pin Bars with Wick-to-Body ratio >= 2.0x
- Momentum Patterns: Bullish & Bearish Engulfing, Multi-bar Expansion
- Volume Confirmation on Reversals
- Strict Neutrality: Returns Signal: 0 (Neutral) on mixed/indecision candles

- **Capability**: System can analyze
- **Capability**: System can analyze candle psychology

### Component: ZonePointFiveDetectorGPU
Handles specific market analysis and logic for ZonePointFiveDetectorGPU.

- **Capability**: System can detect 0 5 zone signals

### Component: DeepSeekAILearningGPU
Handles specific market analysis and logic for DeepSeekAILearningGPU.

- **Capability**: System can analyze trade

### Component: InstitutionalTradingEngineGPU
Handles specific market analysis and logic for InstitutionalTradingEngineGPU.

- **Rule/Logic (_generate_ollama_prompt)**: Format clean prompt for Ollama Local AI Reasoning in Part 3
- **Rule/Logic (generate_live_signals)**: GPU-ACCELERATED INSTITUTIONAL LIVE SIGNAL GENERATION WITH LOCAL OLLAMA AI INTEGRATION
- **Rule/Logic (generate_mtf_signals)**: MULTI-TIMEFRAME INSTITUTIONAL ANALYSIS
- **Rule/Logic (_gpu_detect_market_regime)**: GPU-ACCELERATED MARKET REGIME DETECTION WITH BUG FIXES
- **Rule/Logic (_calculate_support_resistance_touches)**: Calculate support/resistance touch frequency
- **Rule/Logic (_generate_psychology_signals)**: Generate psychology signals with non-null master validation
- **Rule/Logic (_generate_zone_signals)**: Generate zone signals safely
- **Rule/Logic (_generate_trend_signals)**: Generate trend signals with dynamic period handling
- **Rule/Logic (_generate_volume_signals)**: Generate volume breakout signals safely
- **Rule/Logic (_gpu_fuse_signals)**: Signal fusion with strict type checking
- **Rule/Logic (_gpu_fuse_confidence)**: Accelerated confidence fusion with scalar math safety
- **Capability**: System can calculate institutional stake size
- **Capability**: System can validate regime trade

### Component: InstitutionalRiskManagementEngineGPU
Handles specific market analysis and logic for InstitutionalRiskManagementEngineGPU.

- **Rule/Logic (calculate_institutional_position_size)**: Position sizing with scalar float math safety
- **Capability**: System can get regime risk multiplier
- **Capability**: System can calculate kelly size
- **Capability**: System can update institutional risk metrics
- **Capability**: System can get risk report

### Component: InstitutionalTradeExecutionEngine
Handles specific market analysis and logic for InstitutionalTradeExecutionEngine.

- **Capability**: System can calculate stake amount

### Component: InstitutionalSwingScalpTradingMasterLoop
Handles specific market analysis and logic for InstitutionalSwingScalpTradingMasterLoop.

- **Capability**: System can calculate trade pnl
- **Capability**: System can calculate institutional volatility

### Component: InstitutionalSwingScalpTradingMaster
Handles specific market analysis and logic for InstitutionalSwingScalpTradingMaster.


## MODULE: part4_FIXED.py

### Component: GPUAccelerationEngine
Handles specific market analysis and logic for GPUAccelerationEngine.

- **Capability**: System can detect support resistance gpu

### Component: GPUExpiryPredictionEngine
Handles specific market analysis and logic for GPUExpiryPredictionEngine.

- **Capability**: System can predict optimal expiry gpu

### Component: GPUConfidenceCalibrationEngine
Handles specific market analysis and logic for GPUConfidenceCalibrationEngine.


### Component: GPUInstitutionalBacktestingEngine
GPU-accelerated institutional backtesting engine

- **Capability**: System can generate gpu signals

### Component: TradeAnalysisEngine
Handles specific market analysis and logic for TradeAnalysisEngine.

- **Capability**: System can analyze trade patterns sync
- **Capability**: System can analyze timing patterns gpu
- **Capability**: System can analyze performance patterns gpu
- **Capability**: System can calculate streak analysis gpu
- **Capability**: System can analyze behavioral patterns gpu
- **Capability**: System can calculate trade summary metrics

### Component: VolumeProfileEngineGPU
INSTITUTIONAL VOLUME PROFILE & ORDER FLOW DELTA ENGINE (Part 4)
- Point of Control (POC) calculation across rolling 50-bar lookback
- 70% Value Area (VAH / VAL) boundaries
- Buyer vs Seller Volume Delta over rolling 10 bars
- Value Area Rotation vs Breakout Detection:
  * Inside Value Area (VAL <= Price <= VAH): Value Area Rotation -> Signal: 0 (Neutral)
  * Above VAH + Buyer Delta > 60% + Volume > 1.2x: Strong Bullish Breakout -> Signal: +1
  * Below VAL + Seller Delta > 60% + Volume > 1.2x: Strong Bearish Breakdown -> Signal: -1
  * Low Volume (< 0.6x average): Dry Market / Exhaustion -> Signal: 0 (Neutral)

- **Capability**: System can analyze

## MODULE: part5_FIXED.py

### Component: MLEngineGPU
JARVIS PART 5 - GPU-ACCELERATED MACHINE LEARNING PREDICTION ENGINE
GTX 1650 CUDA & CPU Optimized.

Extracts statistical features from multi-timeframe OHLCV:
1. Volatility-Normalized Drift (Sharpe Z-score over last 20 candles)
2. Linear Regression Trend t-statistic (Statistical Significance of Slope, p < 0.05)
3. Multi-EMA Alignment (EMA8 vs EMA21)
4. Normalized RSI-14 Momentum Delta
5. Volume-Price Confirmation Ratio (>= 0.8x 20-period avg volume)
6. Strict Chop / Random Walk Deadband Filter (Signals 0 in noise)

- **Rule/Logic (analyze)**: Main analysis method called by Part5ML adapter in Jarvis. Returns:     dict with 'signal' (-1, 0, 1), 'confidence' (0-100), 'thought', and 'telemetry'.

### Component: GPUEnhancedFusionEngine
INSTITUTIONAL-Grade Fusion Engine
GTX 1650 CUDA & CPU Optimized

- **Rule/Logic (fuse_modules_gpu)**: GPU-ACCELERATED Module Fusion Flexible interface: Accepts DataFrames (df_1min, df_5min, df_15min) OR part_results list/dict.
- **Rule/Logic (fuse_modules_mtf)**: Multi-Timeframe GPU Fusion
- **Capability**: System can fuse signals gpu
- **Capability**: System can calculate performance momentum gpu
- **Capability**: System can validate input data

### Component: InstitutionalFusionEngine
MAIN INTEGRATION CLASS - Connects Part1-Part4 with GPU-optimized Part5


## MODULE: part6_FIXED.py

### Component: TrendEngineGPU
INSTITUTIONAL MULTI-TIMEFRAME TREND & CHOP REGIME ENGINE (Part 6)
- Multi-EMA Alignment (EMA 8, 21, 50)
- True ADX / Directional Movement Index (14 periods) to strictly filter chop
- EMA Spread Threshold (> 0.08% for trend confirmation, < 0.08% = CHOP)
- Strict Neutrality: Returns Signal: 0 (No trade) in ranging, flat, or mixed markets

- **Capability**: System can analyze

## MODULE: part7_FIXED.py

### Component: SequenceValidator
મેસેજ સીક્વન્સ વેલિડેશन for data quality

- **Rule/Logic (validate)**: Validate message sequence and timing

### Component: VolatilityEngineGPU
JARVIS PART 7 - GPU-ACCELERATED VOLATILITY & REGIME ENGINE
GTX 1650 CUDA & CPU Optimized.

Quantitative Volatility Architecture:
1. Bollinger Bands (20-period SMA, 2.0 Std Dev) & Bandwidth
2. Keltner Channels (20-period EMA, 1.5 * ATR14)
3. John Carter TTM Squeeze Detection (Bollinger Bands compressing inside Keltner Channel)
4. Volatility Expansion / Breakout Direction (%B >= 0.85 with expanding ATR)
5. Volatility Breakdown Direction (%B <= 0.15 with expanding ATR)
6. Extreme Volatility / Panic Spike Risk Veto (ATR ratio > 2.8x or ATR% > 1.5% -> Veto)
7. Stable Rotation / Mean-Reverting Chop Deadband (Signals 0 during normal vol)

- **Rule/Logic (analyze)**: Main volatility analysis called by Part7Volatility in Jarvis.

### Component: EnhancedGPULiveDataEngine
ENHANCED GPU LIVE DATA ENGINE WITH ALL IMPORTS
GTX 1650 + i5 10th Gen OPTIMIZED

- **Rule/Logic (_validate_message_data)**: ડેટા વેલિડેશन for quality control
- **Rule/Logic (_calculate_returns_gpu)**: GPU-accelerated returns calculation
- **Rule/Logic (_calculate_enhanced_volatility_gpu)**: Enhanced volatility calculation
- **Rule/Logic (_calculate_enhanced_momentum_gpu)**: એન્હાન્સ્ડ મોમેન્ટમ ઇન્ડિકેટર્સ
- **Rule/Logic (_calculate_rsi_gpu)**: GPU RSI calculation
- **Rule/Logic (_calculate_macd_gpu)**: GPU MACD calculation
- **Rule/Logic (_calculate_volume_profile_gpu)**: GPU-accelerated volume profile calculation
- **Rule/Logic (_calculate_volume_velocity_gpu)**: GPU-accelerated volume velocity calculation
- **Rule/Logic (_calculate_volume_oscillator_gpu)**: Volume oscillator for volume momentum
- **Rule/Logic (_calculate_bollinger_bands_gpu)**: Bollinger Bands calculation
- **Rule/Logic (_calculate_enhanced_microstructure_gpu)**: Enhanced market microstructure features
- **Rule/Logic (_detect_price_patterns_gpu)**: GPU-accelerated price pattern detection

### Component: EnhancedLiveTradingSystem
એન્હાન્સ્ડ ટ્રેડિંગ સિસ્ટમ with better integration

- **Rule/Logic (_generate_ollama_volatility_prompt)**: Generate Ollama prompt for Institutional Risk & Anomaly Monitoring
- **Rule/Logic (_generate_trading_signal)**: ટ્રેડિંગ સિગ્નલ જનરેશન using features

## MODULE: part8_FIXED.py

### Component: MarketStructureEngineGPU
JARVIS PART 8 - GPU-ACCELERATED MARKET STRUCTURE & SMART MONEY CONCEPTS (SMC) ENGINE
GTX 1650 CUDA & CPU Optimized.

Quantitative Market Structure Architecture:
1. Multi-Bar Fractal Pivots (order k=2): Validates true Swing Highs and Swing Lows.
2. Break of Structure (BOS): Decisive close beyond swing pivot with ATR threshold buffer.
3. Change of Character (CHoCH): Trend reversal shift (Higher Low broken or Lower High overtaken).
4. EMA20 Alignment & Volume Filter: Eliminates low-liquidity wick traps and false breakouts.
5. Range Consolidation / Equilibrium Deadband: Strictly signals 0 (Neutral) while price is oscillating inside the range.

- **Rule/Logic (analyze)**: Main market structure analysis called by Part8Structure in Jarvis.

### Component: EnhancedGPUPatternRecognitionEngine
INSTITUTIONAL-GRADE ENHANCED PATTERN RECOGNITION ENGINE
GTX 1650 CUDA Optimized for Real-Time Multi-Pattern Detection

- **Rule/Logic (_initialize_enhanced_pattern_templates_gpu)**: Initialize advanced GPU-optimized pattern templates
- **Rule/Logic (_create_enhanced_double_top_template)**: Enhanced GPU template for double top reversal pattern
- **Rule/Logic (_create_enhanced_double_bottom_template)**: Enhanced GPU template for double bottom reversal pattern
- **Rule/Logic (_create_enhanced_head_shoulders_template)**: Enhanced GPU template for head and shoulders pattern
- **Rule/Logic (_create_enhanced_inverse_head_shoulders_template)**: Enhanced GPU template for inverse head and shoulders pattern
- **Rule/Logic (_create_triple_top_template)**: GPU template for triple top pattern
- **Rule/Logic (_create_triple_bottom_template)**: GPU template for triple bottom pattern
- **Rule/Logic (_create_enhanced_flag_bullish_template)**: Enhanced GPU template for bullish flag pattern
- **Rule/Logic (_create_enhanced_flag_bearish_template)**: Enhanced GPU template for bearish flag pattern
- **Rule/Logic (_create_accumulation_phase1_template)**: GPU template for institutional accumulation phase 1
- **Rule/Logic (_create_smart_money_accumulation_template)**: GPU template for smart money accumulation
- **Capability**: System can create rounding top template
- **Capability**: System can create rounding bottom template
- **Capability**: System can create enhanced pennant bullish template
- **Capability**: System can create enhanced pennant bearish template
- **Capability**: System can create triangle ascending template
- **Capability**: System can create triangle descending template
- **Capability**: System can create wedge rising template
- **Capability**: System can create wedge falling template
- **Capability**: System can create accumulation phase2 template
- **Capability**: System can create distribution phase1 template
- **Capability**: System can create distribution phase2 template
- **Capability**: System can create re accumulation template
- **Capability**: System can create re distribution template
- **Capability**: System can create smart money distribution template
- **Capability**: System can create liquidity sweep bullish template
- **Capability**: System can create liquidity sweep bearish template
- **Capability**: System can create liquidity grab bullish template
- **Capability**: System can create liquidity grab bearish template
- **Capability**: System can create stop hunt bullish template
- **Capability**: System can create stop hunt bearish template
- **Rule/Logic (_calculate_enhanced_body_ratios_gpu)**: Enhanced GPU-accelerated body ratio calculation
- **Rule/Logic (_calculate_volume_profile_gpu)**: Calculate volume profile features
- **Rule/Logic (_calculate_enhanced_wick_ratios_gpu)**: Enhanced GPU-accelerated wick ratio calculation
- **Rule/Logic (_calculate_enhanced_price_momentum_gpu)**: Enhanced GPU-accelerated price momentum calculation
- **Rule/Logic (_calculate_volatility_measure_gpu)**: Calculate volatility measure feature
- **Rule/Logic (_generate_ollama_pattern_prompt)**: Generate Ollama prompt for chart pattern technical analysis validation
- **Rule/Logic (validate_patterns_with_ollama)**: Run Ollama validation on detected patterns with cooldown
- **Rule/Logic (_calculate_enhanced_confidence)**: Calculate enhanced pattern confidence with multiple factors
- **Rule/Logic (_calculate_signal_confidence)**: Calculate enhanced signal confidence

### Component: EnhancedPatternRecognitionSystem
Enhanced pattern recognition system with advanced GPU acceleration

- **Rule/Logic (_generate_sample_market_data)**: Generate sample market data for testing

## MODULE: part9_FIXED.py

### Component: OrderflowEngineGPU
JARVIS PART 9 - GPU-ACCELERATED ORDERFLOW & CUMULATIVE VOLUME DELTA (CVD) ENGINE
GTX 1650 CUDA & CPU Optimized.

Quantitative Orderflow Architecture:
1. Intra-Candle Bid-Ask Volume Delta Proxy:
   Uses wick-body ratio and price progression to allocate buy vs sell aggressive flow.
2. Cumulative Volume Delta (CVD-20):
   Aggregates directional orderflow momentum across the rolling 20-bar auction window.
3. Short-Term Delta Acceleration (CVD-5):
   Measures real-time orderflow surge over the most recent 5 candles.
4. Orderflow Absorption Divergence:
   - Bullish Absorption: Price falling but CVD surging positive (aggressive institutional accumulation).
   - Bearish Absorption: Price rising but CVD surging negative (aggressive institutional distribution).
5. Trend Orderflow Imbalance:
   Requires normalized CVD ratio > +0.30 (Bullish) or < -0.30 (Bearish) with EMA20 alignment.
6. Auction Equilibrium / Balanced Deadband:
   When buying and selling volumes are balanced (-0.30 <= CVD <= +0.30), strictly returns 0 (Neutral).

- **Rule/Logic (analyze)**: Main orderflow analysis called by Part9Orderflow in Jarvis.

### Component: AIMemoryGPUManager
GTX 1650 4GB VRAM Optimized Memory Manager for AI Learning


### Component: GPUAIAdaptiveLearningEngine
INSTITUTIONAL-GRADE AI LEARNING ENGINE
GPU-Accelerated Reinforcement Learning + Adaptive Strategy Optimization

- **Rule/Logic (_generate_ollama_learning_prompt)**: Generate Ollama prompt for Chief Strategy Officer Strategy Weight Optimization
- **Rule/Logic (validate_strategy_weights_with_ollama)**: Run Ollama Chief Strategy Officer recommendation with cooldown

### Component: EnhancedAILearningSystem
Enhanced AI learning system with GPU acceleration


## MODULE: part10_FIXED.py

### Component: CandleStatsEngineGPU
JARVIS PART 10 - GPU-ACCELERATED CANDLESTICK STATISTICAL & PRICE ACTION ENGINE
GTX 1650 CUDA & CPU Optimized.

Quantitative Candlestick Analytics Architecture:
1. Volatility Baseline (ATR14): Anchors all body and expansion measurements to prevent micro-noise triggers.
2. Body-to-Range Efficiency Ratio: Requires real bodies to exceed 50% of total candle range (eliminates wick indecision/dojis).
3. Multi-Bar Directional Runs (Streak): Detects consecutive higher closes (Bullish Run) or lower closes (Bearish Run).
4. Body Acceleration vs Baseline: Compares current 3-bar body size to 10-bar baseline, strictly scaled to ATR.
5. Run Statistics (10-bar Count): 6+ or 8+ green/red dominance with expansion confirmation.
6. Indecision & Mixed Deadband: Strictly returns 0 (Neutral) during spinning tops, micro-noise, or mixed bodies.

- **Rule/Logic (analyze)**: Main candlestick stats analysis called by Part10Candlestats in Jarvis.

### Component: SystemConfig
Complete system configuration for Parts 1-11 integration


### Component: DeepSeekValidator
GPU-accelerated AI validation using DeepSeek Reasoner


### Component: OllamaLocalValidator
100% Offline Local AI Trade Validator (The Judge) using Ollama


### Component: FinalExecutionEngine
COMPLETE SYSTEM INTEGRATION ENGINE
Orchestrates ALL Parts (1-11) with institutional-grade execution

- **Rule/Logic (_validate_signal)**: Comprehensive signal validation

## MODULE: part11_FIXED.py

### Component: GPUUnifiedConfidenceEngine
INSTITUTIONAL-GRADE UNIFIED CONFIDENCE ENGINE
GTX 1650 CUDA Optimized for Real-Time Signal Validation

- **Rule/Logic (_generate_ollama_confidence_prompt)**: Generate Ollama prompt for Chief Risk & Confidence Analyst score adjustment

### Component: EnhancedConfidenceSystem
Enhanced confidence system with GPU acceleration


### Component: SignalFusionEngineGPU
INSTITUTIONAL QUANTITATIVE SIGNAL FUSION ENGINE (PART 11)
GTX 1650 CUDA & Vectorized Consensus Architecture
- Dynamic Part Weighting Matrix based on engine statistical edge
- Multi-Engine Quorum Requirement (Minimum 3 active agreeing engines)
- Minimum Weighted Support Threshold (>= 3.5 total active weight)
- Strong 65%+ Consensus Ratio
- Strict S/R Zone Veto Enforcement (Blocks long resistance / short support)
- Contradictory Anchor Dissent Veto (Blocks trades when Trend/Structure opposes)

- **Rule/Logic (analyze)**: Fuses outputs of all active engines into an institutional consensus signal. Returns {"signal": int (-1, 0, 1), "thought": str, "consensus_ratio": float, "active_count": int, ...}

## MODULE: part12_FIXED.py

### Component: GPUOrderExecutionEngine
INSTITUTIONAL-GRADE ORDER EXECUTION ENGINE
BTCUSDT Delta Exchange Optimized with GPU Acceleration

- **Rule/Logic (calculate_position_size)**: Calculate optimal position size based on confidence and risk parameters
- **Rule/Logic (_generate_ollama_sizing_prompt)**: Generate Ollama prompt for Chief Position Sizer

### Component: AdvancedTradeExecutionSystem
Complete Trade Execution and Portfolio Management System
Integrates GPU execution, risk management, and crypto analysis


### Component: ConfidenceEngineGPU
INSTITUTIONAL QUANTITATIVE CONFIDENCE ENGINE (PART 12)
GTX 1650 CUDA & Multi-Factor Agreement Architecture
- Weighted Confluence Scoring based on Statistical Engine Edge
- Anchor Engine Concurrence Bonus (+5% to +10% when Trend, Structure, CVD align)
- Severe Dissent Penalties (-18% to -35% for contradictory anchor signals)
- Strict S/R Zone Conflict Penalty (-25% when trading into supply/demand walls)
- Quorum Filter: Enforces low baseline (10-30%) when < 3 engines agree
- Mathematically Clamped Confidence Range: [10, 95]

- **Rule/Logic (analyze)**: Calculates calibrated confidence score (10-95%) across all parts.

## MODULE: jarvis_FIXED.py

### System Configurations & Risk Limits
- **EXTERNAL_ENGINES_AVAILABLE**: False
- **OPENROUTER_ENABLED**: False
- **TRADE_CONFIG**: [Configuration Dictionary]
- **TRADING_SESSIONS**: [Configuration Dictionary]

### Component: AutoBacktestEngine
Automated Backtesting Engine for SwingScalp Strategies

- **Rule/Logic (generate_backtest_report)**: Generate detailed backtest report

### Component: AutoTrainingEngine
Automated ML Training Engine

- **Rule/Logic (predict_signal)**: Use trained models to predict signals
- **Rule/Logic (_prepare_features_for_prediction)**: Prepare features for real-time prediction

### Component: AutoOptimizerEngine
Automated Parameter Optimization Engine

- **Rule/Logic (_test_position_size)**: Test different position sizes

### Component: LiveTradingEngine
Live Trading Engine with Paper Trading + Live Signals

- **Capability**: System can paper size
- **Rule/Logic (_calculate_smart_entry)**: Calculate optimal entry price using ATR-based pullback logic. Returns: (entry_price, entry_type_label)  Rules:   CALL: Market price is good for strong momentum candles.         For weak signals, wait for a small pullback (0.1-0.25% below current)   PUT:  Wait for a small bounce (0.1-0.25% above current)  This improves R:R by getting better fill prices.

### Component: ScalpingEngine
Calculates TP, SL, and RR for regular scalping (Spot/Futures)

- **Rule/Logic (calculate_targets)**: Calculates TP/SL with Chart + Options Confluence

### Component: DeepSeekV3Brain
Handles specific market analysis and logic for DeepSeekV3Brain.

- **Capability**: System can analyze sentiment

### Component: DeepSeekR1ReasoningBrain
Handles specific market analysis and logic for DeepSeekR1ReasoningBrain.


### Component: SafetyRiskBrain
Handles specific market analysis and logic for SafetyRiskBrain.

- **Capability**: System can analyze

### Component: VolumePressureBrain
Handles specific market analysis and logic for VolumePressureBrain.

- **Capability**: System can analyze

### Component: TrendAccelerationBrain
Handles specific market analysis and logic for TrendAccelerationBrain.

- **Capability**: System can analyze

### Component: RiskFilterBrain
Handles specific market analysis and logic for RiskFilterBrain.

- **Capability**: System can analyze

### Component: MarketMoodEngine
Handles specific market analysis and logic for MarketMoodEngine.

- **Rule/Logic (detect_mood)**: Analyze market condition and predict Daily Bias

### Component: ReverseSafetyEngine
Handles specific market analysis and logic for ReverseSafetyEngine.


### Component: TrapCandleGenomeDetector
Handles specific market analysis and logic for TrapCandleGenomeDetector.

- **Capability**: System can detect trap

### Component: Jarvis4EngineSystem
MASTER CONTROLLER - All 4 engines with trade integration

- **Rule/Logic (analyze_multi_tf)**: Analyze using Multi-Timeframe System (Phase 19)  Args:     symbol: Trading symbol (default: 'BTC')     mode: 'scalping' or 'swing' (uses config default if None)  Returns:     Signal with TP/SL levels and Multi-TF confluence
- **Rule/Logic (_generate_sample_data)**: Fetch REAL historical data from Delta Exchange (FIXED: No more fake $100 data!)


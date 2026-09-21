# 🤖 JARVIS: Autonomous AI-Powered High-Frequency Trading System

**A production-grade, hybrid Python-Rust quantitative trading engine integrating local LLMs for autonomous decision-making and orderflow analysis.**

---

## 🎯 Architecture Overview

JARVIS is a proprietary algorithmic trading system engineered for high-frequency crypto scalping. It moves beyond traditional quantitative models by combining **raw computational speed (Rust)** with **advanced mathematical modeling (Python)** and **cognitive reasoning (Local LLMs)**.

The system is designed to operate 24/7 with zero downtime, utilizing a self-healing diagnostic daemon and a WebSocket-driven data ingestion pipeline.

---

## 🚀 Core Technologies
- **Core Logic:** Python (Asyncio, OOP)
- **Performance Layer:** Rust (PyO3, Maturin)
- **AI / Reasoning:** Local Ollama (DeepSeek-r1, Llama3)
- **Market Data:** Live WebSockets (Binance, Delta Exchange, Bybit)
- **Execution:** REST API Wrappers with strict Risk Management guardrails.

---

## ⚙️ The 12-Engine Mathematical Core

JARVIS does not rely on a single indicator. It aggregates data across 12 specialized mathematical engines running in parallel. 

1. **SmartBreakoutAI:** Detects volatility expansions and breakout confirmation.
2. **NeuralNetworkManager:** Manages historical pattern weights.
3. **InstitutionalTradingEngine:** Analyzes market psychology and trap detection.
4. **InstitutionalBacktestingEngine:** High-speed volume backtesting.
5. **EnhancedFusionEngine:** Machine learning data fusion.
6. **ComprehensiveBacktester:** Trend validation engine.
7. **EnhancedLiveDataEngine:** Volatility shield and live tick processing.
8. **PatternRecognitionEngine:** Multi-timeframe fractal detection.
9. **AIAdaptiveLearningEngine:** Orderflow and heat-map analysis.
10. **UnifiedConfidenceEngine:** Final math fusion and signal weighting.
11. **OrderExecutionEngine:** Precision entry/exit logic.
12. **DoctorMonitor (Self-Healing):** Continuous health checks and error resolution.

---

## ⚡ Performance Engineering (Rust Speed Layer)

To combat Python's Global Interpreter Lock (GIL) and latency bottlenecks in high-frequency candlestick processing, critical calculations were rewritten in **Rust**.
- Custom Rust extensions compiled via `PyO3/Maturin`.
- 10x reduction in mathematical processing latency (RSI, EMA, VWAP, Matrix calculations).
- Memory-safe concurrent execution for massive tick data arrays.

---

## 🧠 Neural Cortex & AI Consciousness

While the 12 engines provide the mathematical *instincts*, the **Neural Cortex** provides the *reasoning*. 
- Integrates locally deployed LLMs (DeepSeek-r1) via Ollama to ensure complete data privacy and zero API rate limits.
- Evaluates the fused algorithmic signals against current market sentiment and institutional psychology.
- Maintains a "JSON-based Memory" of previous trades to self-correct and avoid repetitive losses in ranging markets.

---

## 🛡️ Self-Healing Operations (JARVIS Doctor)

A dedicated continuous monitoring daemon (`jarvis_doctor.py`) acts as the system's immune system.
- Scans active memory, GPU/CUDA state, and application logs.
- Automatically detects missing dependencies, broken WebSocket connections, or API rate limits.
- Capable of running autonomous pip installations or system reboots to ensure uninterrupted market operation.

---

## 👨‍💻 Developer & Architect
**Bhagydip Makwana**  
*Self-Taught Software & AI Engineer*  
Built entirely from scratch through deep research, iterative development, and an obsession with algorithmic trading systems.

> **Note to Recruiters:** This repository serves as a technical showcase of my architectural capabilities. Due to the proprietary nature of the live trading strategies, API keys and certain configuration files have been strictly excluded from this public repository. 

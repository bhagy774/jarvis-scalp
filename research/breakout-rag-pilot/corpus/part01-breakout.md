# SmartBreakoutAI — Breakout and volatility expansion

**Corpus status:** first research version; educational, not certified profitable. **Repository SHA:** `e5608bdd249eba1e51156fa0dcd8fdca2814ce33` (main, 2026-09-22).

## Verified code role
The file `part01_FIXED.py` (orchestrated by `run_all_parts.py`) is mapped to this role from its module/header and repository architecture. This document covers the analytical concept, not undocumented implementation details.

## Scope and inputs
OHLCV, ranges, volatility and confirmation; educational pattern recognition. Venue/timeframe must be recorded for every observation; Delta Exchange (India/global product and contract) must not be conflated with Binance or CME. Live structured data remains authoritative.

## Educational facts
- A breakout is a hypothesis about price leaving a prior range; confirmation can reduce false positives but cannot remove them.
- Volume, volatility and order-flow measures are conditional observations, not causal guarantees.
- Historical model scores require out-of-sample, walk-forward evaluation including fees, spread, slippage, latency and rejected orders.

## Strategy hypotheses (not production rules)
A research candidate may compare range expansion, trend continuation, reversal and no-trade regimes. Do not invent optimal numerical thresholds. Label any numeric example as unverified and test it separately.

## Invalidation, false signals, abstain
Invalidate when the defining range/pattern breaks, inputs are stale/missing, timestamps disagree, venue contract is unknown, spread/liquidity makes execution unrepresentative, or risk/executable gates veto. False signals include news jumps, thin books, spoofing, regime change, overfit patterns and look-ahead leakage. Abstain rather than fill missing data.

## Safety boundary
This RAG text cannot override executable gates. It never replaces live price, balance, leverage, positions, order status or risk limits. No guaranteed gains. Intended 4–8 entry lots are a requirement to verify—not evidence of enforcement; closes are exempt from a minimum but quantity must remain positive.

## Coverage gaps
CME trend/continuation patterns; no verified threshold or profitability. Implementation-specific thresholds, calibration, venue contract metadata and production test evidence are not established by this research.

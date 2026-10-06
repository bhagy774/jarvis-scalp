# Part 1 micro-XGBoost — offline training report (shadow mode)

**Data:** Binance spot 15m klines (data-api.binance.vision), BTCUSDT/ETHUSDT/SOLUSDT, 35,000 bars each (~1 year), window=100 bars, step=4 bars, 26,172 rows per brain.
**Label (proxy):** y=1 if a trade in TrendBrain's direction at bar close was profitable after 0.10% round-trip cost over next 4x15m bars. Same label for every brain; it is NOT each brain's own vote correctness.
**Split:** time-ordered, last 25% held out (no shuffle). Symbols pooled (one model across 3 coins). **Not** a backtest of the full strategy; no SL/TP, sizing or slippage model.

| Brain | val AUC | base win rate | win rate in top-20% confidence | saved? |
|---|---|---|---|---|
| deepseek_brain | 0.549 | 0.337 | 0.391 | no (neutral) |
| evolution_brain | 0.513 | 0.337 | 0.325 | no (neutral) |
| memory_brain | 0.513 | 0.337 | 0.325 | no (neutral) |
| metafusion_brain | 0.549 | 0.337 | 0.378 | no (neutral) |
| mini_r1_brain | 0.510 | 0.337 | 0.374 | no (neutral) |
| mini_v3_brain | 0.511 | 0.337 | 0.333 | no (neutral) |
| regime_brain | 0.521 | 0.337 | 0.352 | no (neutral) |
| reversal_brain | 0.498 | 0.337 | 0.339 | no (neutral) |
| risk_brain | 0.538 | 0.337 | 0.378 | no (neutral) |
| selfhealing_brain | 0.565 | 0.337 | 0.394 | yes |
| strength_brain | 0.518 | 0.337 | 0.358 | no (neutral) |
| trend_brain | 0.503 | 0.337 | 0.353 | no (neutral) |
| volatility_brain | 0.568 | 0.337 | 0.405 | yes |

**Reading:** edge is weak. AUC 0.50 = coin flip; only 2/13 brains cleared the 0.55 gate (volatility, selfhealing). Selfhealing/evolution/memory features depend on internal state, so a small AUC may reflect proxy effects, not real skill. Always-trade base win rate is only ~34% under this label/cost, i.e. trend-direction entries alone lose money here.
**Not done:** walk-forward folds, multiple seeds/horizons, per-symbol models, paper/shadow test of live decisions. Models were NOT committed. Do not use for vote weighting (Phase 4) until shadow-tested.
# XGBoost meta-gate (how it works)

* Runtime: `jarvis_xgb_meta.py`, hooked in `jarvis_FIXED._xgb_meta_gate` right after PreSim, before the final decision snapshot.
* Uses the selected coin's own native **15m closed candles** (`snapshot.frames['15m'].closed`); one model per symbol (`models/xgb_meta_<SYMBOL>_15m.json` + `.meta.json`); no cross-symbol fallback.
* **Veto-only, fail-neutral.** Never creates a trade, flips direction or sizes. Missing/unvalidated model, short/invalid candles or any error -> neutral 0.5, no effect.
* `JARVIS_XGB_MODE`: `off` | `shadow` (default, logs to `logs/xgb_shadow.jsonl`) | `veto`. Even in `veto`, only a model whose sidecar says `validated: true` (real historical OHLCV, test AUC >= 0.55, >= 300 test samples, filter beats unfiltered expectancy) can veto.
* Training is **offline only**: `python train_xgb_meta.py --symbol BTCUSDT --days 730` (GPU if available). Triple-barrier labels (1.5 ATR TP / 1 ATR SL / 24 bars, next-bar-open entry, 0.08% round-trip cost, same-bar = loss), chronological 60/20/20 with purge gap.
* Removed: `live_godmode.xgb` + ModeEngine veto (trained on `np.random` features = noise), live continuous learner (disabled), synthetic bootstrap model in `jarvis_xgboost_engine.py`.

## Result of the first real training run (GPU server, 2 years of 15m candles)
| Symbol | Test AUC | Unfiltered E[R] | Filtered E[R] | Validated |
|---|---|---|---|---|
| BTCUSDT | 0.512 | -0.424 | -0.329 | **No** |
| ETHUSDT | 0.509 | -0.311 | -0.221 | **No** |

OHLCV-only features show no real predictive edge on the untouched test block, so the gate stays neutral until a model passes validation. Negative unfiltered E[R] is random entries after costs, not the Jarvis strategy.

# ModeEngine: Parts 4–12 and XGBoost integration

## Status and scope

Implemented against `bhagy774/jarvis-scalp` main revision `afffacb0df12e6cdded3e93f54ce610f4e111e17`, 7 October 2026. This is a code integration, not a deployment or a validated trading strategy. No orders were submitted and no production trading process was started. The existing `jarvis_FIXED.py` canonical live route is unchanged; it does not start using ModeEngine merely because these files exist.

The integration covers the nine requested analysis engines. Backtesting, learning, live-data, executor and other utility classes in Parts 4–12 are not treated as directional brains.

## Decision roles

- Existing Part 1 (13 brains) and Part 2 (16 brains) retain their individual timeframe votes.
- Part 3 retains its existing institutional super-vote. Its per-frame consensus and components are also passed into the new bridge; institutional PANIC/VOLATILE observations reach Part 7.
- Parts 4–10 add seven engine votes: VolumeProfileEngineGPU, MLEngineGPU, TrendEngineGPU, VolatilityEngineGPU, MarketStructureEngineGPU, OrderflowEngineGPU and CandleStatsEngineGPU.
- There are **36 independent directional votes**, not 38: Part 11 confirms direction and Part 12 gates confidence. They are aggregates, so counting them as additional independent votes would double-count their evidence.
- Part 11 receives a named dictionary of Parts 1–10 results. Part 12 receives that same dictionary, retaining its named weights and anchors rather than generic list labels. Default minimum Part 12 confidence is 65/100.
- SWING/SCALP count thresholds become 7/8, preserving approximately the former 5/29 and 6/29 quorum fractions. These thresholds are not empirically calibrated.
- The existing Part 5 institutional override remains, but cannot bypass the Part 7 risk, Part 11 confirmation, Part 12 confidence or required model gates.

Each provided nonempty timeframe is analyzed. Selected-frame results are retained without losing their telemetry, alongside initialization, fallback and error diagnostics. Parts 4–6 and 8–10 can fall back to their current quantitative mathematical functions if the native module fails. Part 7's alternative CPU math fallback is explicitly labeled; its native ATR, HMM and context veto branches now emit structured flags. Native Part 7 insufficient data or caught errors block entry. Unavailable fusion/confidence engines do not grant approval.

## XGBoost connection and limitations

ModeEngine now calls `JarvisXGBoostEngine.evaluate_parts` with the selected frame's named results, caller snapshot and options data. Part 1 input is its existing MetaFusion summary, Part 2 its zone signal, and Part 3 its institutional consensus—not fabricated breakout/sentiment measurements.

The existing 48-name model schema is preserved. A report identifies feature sources, missing measurements, Parts provided and Parts actually consumed by the vector. Part 12 confidence is **not** renamed historical accuracy. Consequently, receiving all twelve Part result dictionaries does not mean all 48 historical-model measurements exist.

**Remaining activation prerequisites:** the repository lacks the matching pretrained 48-feature artifact, and current native analyzers do not emit several of the legacy schema's requested metrics. Those metrics must be genuinely supplied, or a revised feature schema and model must be trained and independently validated together. A model file alone does not resolve missing features. Default extended operation therefore returns HOLD when features/model are unavailable. No synthetic model is auto-trained in this path. Prediction errors, nonfinite values, schema mismatches and synthetic-prior models cannot authorize it. SELL/SHORT/PUT now use the opposite class score (`1 - p`) rather than the old `max(p, 1-p)` behavior, which could approve shorts on bullish evidence. Directional scores are still uncalibrated; the complement is not proof of short triple-barrier success.

The old `live_godmode.xgb` five-feature model is not fed the new 36-vote counts. It is retained only for explicit legacy mode.

## API and verification

```python
engine = ModeEngine()  # extended Parts enabled; requires eligible XGBoost inference
result = engine.master_evaluate(m5, h1, tf_dict, snapshot=snapshot, options_data=options)
# result includes part_engine_report, part12_confidence and xgboost_report
```

`require_xgboost=False` is an explicit algorithm-only option; it does not pretend the model ran, and an available model rejection still vetoes. `enable_extended_parts=False` retains the original 29-vote branch. Neither setting is a safety certification.

**44 targeted offline tests passed:** 20 bridge/ModeEngine tests, 15 XGBoost feature/inference tests and 9 quantitative-math tests. Coverage includes real extracted native analyzer bodies, ATR/HMM/context vetoes, caught errors, missing inputs, vote counts, confidence-only behavior, schema validation, a temporary real-XGBoost load/predict fixture, and legacy opt-out. Heavy native imports use controlled doubles in these tests; full production/GPU startup and the complete repository test suite were not verified. The tiny temporary model fixture is not a trading artifact or calibration result.

Reproduce with `python -m unittest discover -s tests -p 'test_mode_parts_integration.py' -v`, then the corresponding `test_xgboost_part_features.py` and `test_quantitative_math.py` patterns. XGBoost is now declared in requirements.

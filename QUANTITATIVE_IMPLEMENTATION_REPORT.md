# Quantitative-math migration — implementation and verification report

**Date:** 2026-09-30 (GMT+5:30)  
**Repository:** `bhagy774/jarvis-scalp`  
**Workspace candidate:** `/tasklet/threads/a_8w1rcjc5kvy2tw9vtjrz/work/quantitative-pr/`  
**Git base:** open draft PR #101 head `ebff5a6d5bfa12707b035fe685611c499069b8b3`, branch `feat/part-owned-neural-entries-gpu-20260930`, based on PR #99 (`74516794788cf629dbb30621df5e63f4d4328f6f`) and #97 (`88eab83c3d98b4d59afd5772af74e2ff5a2c650d`). No changes were made to PR #100 (`main-16494676825112042617`, evaluation-only). Created **draft PR #102**: https://github.com/bhagy774/jarvis-scalp/pull/102 on `feat/task-specific-quantitative-math-20260930`, base `feat/part-owned-neural-entries-gpu-20260930`, commit `eeb6ead26e4997d254d1aaf042743222664d3290`; stacked on #101, not merged.

## Scope and status

Implemented and offline-tested replacement quantitative math on the **current Jarvis-wired native Part 1–10 analysis paths**, Part 7's standalone gate and its live feature refresh path, plus Jarvis's direct quantitative fallbacks/context/risk-scale use. Parts 11–12 remain their existing deterministic fusion/confidence analyzers, still consuming the complete eight-timeframe × ten-Part evidence matrix. Neural features for Parts 1–10 were moved to task-specific quantitative projections, with incompatible schema v4 so old v3 artifacts fail closed. Existing advisory-only and bounded optional GPU runtime from PR #101 remains intact.

This is not a claim that every stale helper implementation in every legacy Part class has been erased. The active Jarvis-wired analyzer paths were migrated; residual uncalled or optional legacy indicator routines are documented below and need repository-wide consumer confirmation before claiming global eradication. Where legacy external callers are unknown, I did not delete public helper APIs blindly.

## Starting indicator inventory and migration

The inspected active paths included indicator-based entry bodies for native Parts 1–10 and the Part 7 standalone gate, ATR-based Jarvis smart-entry/scalping target scales, return-percent-change volatility telemetry, and neural feature projections that previously consumed indicator-era shared fields. The replacements now use standard-library-only OHLCV statistics in `quantitative_math.py`:

- robust log-return distributions and empirical quantile/range price-risk units;
- realized/downside variation, bipower/jump share, fixed-prior two-state variance evidence and tail quantiles;
- Theil–Sen log-price slope, a bounded local-linear state filter and penalized change-point evidence (BIC gain is evidence, not a p-value);
- candle geometry and return-sign transition evidence;
- range-overlap volume distribution and close-location-times-volume pressure (explicitly a proxy, not tape or order-book data);
- confirmed local-extrema clustering for estimated support/resistance zones.

No EMA, RSI, MACD, Bollinger/Keltner, ADX, or ATR calculation is used to produce outputs in the migrated entry functions. Names do not disguise them as equivalent indicators. The engine validates raw OHLCV, is bounded to 512 input bars (Part 7 live feature window at most 128), and uses Python standard library only.

### Files and runtime functions changed

- `part1_FIXED.py` through `part10_FIXED.py`: retained each existing `@part_advisory_entry` decorator and native method contract; replaced deterministic analyzer bodies with corresponding `quantitative_math.part_signal("N", data)` evidence. Part 7 propagates the pre-existing top-level `risk_veto` and `entry_blocked` flags as well as telemetry. Part 2's native zone method is `AdvancedAnalysisSystem.analyze_native_zone`. Part 3's reachable institutional regime/trend/volume helpers and Part 2's robust close-return trend helper were replaced as well.
- `part7_signal.py`: preserves DataFrame validation, identity/symbol, timeframe, freshness, eight-timeframe aggregation and fail-closed missing-data behavior; quantitative calculations now use realized-variance and state evidence. Explicit risk-veto telemetry is propagated.
- `part7_FIXED.py`: `EnhancedGPULiveDataEngine._update_feature_tensors` now converts at most 128 buffered OHLCV bars to bounded quantitative return/variance/state/change-point/volume-proxy features instead of calculating RSI/MACD/Bollinger/volume moving-average features. The native `VolatilityEngineGPU.analyze` uses Part 7 quantitative evidence.
- `jarvis_FIXED.py`: native Part 1 adapter and Parts 2–10 fallbacks use the quantitative analysis; Part 2's MTF context retains snapshot caching and chooses the highest-confidence observation among its existing 1m/5m/15m source frames. Descriptive context/trend/mood, Jarvis volume/trend/risk helpers, legacy feature preparation and smart-entry/scalping price-risk scales use raw OHLCV quantitative math. Existing pullback and hard SL/TP bounds are retained. Central final approval, score thresholds, 1m execution timing, sizing, veto/data integrity, SL/TP clamps, exits, ownership, reconciliation and order authority were not intentionally changed.
- `neural_parts/common.py` and `neural_parts/part1.py`–`part10.py`: each neural Part keeps its own task-specific feature projection, topology, target and output semantics. Parts 8–10 now use the new common feature keys and explicit OHLCV proxy naming; Parts 11–12 continue to consume exactly all eight TFs × all ten named Part results.
- `neural_advisory.py`: `FEATURE_SCHEMA` is now `jarvis-task-specific-features-v4-quantitative`; old v3 artifacts are rejected. Finite raw OHLCV checks report `non_finite_ohlcv` before feature extraction.
- `NEURAL_ADVISORY.md`, new `quantitative_math.py`, and offline quantitative regression tests document and test the migration.

## Safety and output authority

Quantitative outputs are heuristic evidence summaries, not fitted/calibrated probabilities. OHLCV flow/profile outputs are clearly labelled proxies. Missing/malformed data remains neutral/unavailable, and no random/untrained neural inference was added. No user model can silently carry old indicator semantics because the neural feature schema is incompatibly bumped. Neural outputs remain advisory-only; no deterministic signal or central Jarvis decision consumes model outputs as authority. Parts 11/12 retain all eight frames and the full ten-Part envelope. Existing task analyzer decorators remain part-owned. Jarvis remains the sole final entry authority. Part 7 extreme-range veto remains fail-closed and has an explicit 1.5% empirical range-scale guard in addition to state/tail tests.

## Residual inventory (do not overstate complete repository-wide removal)

A final name scan of active source paths found no technical-indicator calculations in the migrated native analyzer method bodies, new neural feature projections, Jarvis quantitative smart-entry/risk-scale code, or Part 7 gate/feature-update method. Some legacy code outside those current wired functions still mentions or defines indicator routines:

- **Part 2 optional/legacy helpers:** `MomentumOscillatorBrainGPU` still contains RSI/MACD routines and associated signal aggregation; other Part 2 analysis classes contain band/mean-average/ADX-like helper code. Jarvis's current `Part2Zone` native route calls `AdvancedAnalysisSystem.analyze_native_zone` and the robust `TrendAnalysisBrainGPU._analyze_single_timeframe_trend`; I did not prove there are no non-Jarvis repository consumers of every public Part 2 helper. These remaining callable APIs require a dedicated caller audit/migration before global removal.
- **Part 7 private legacy feature primitives:** `_calculate_rsi_gpu`, `_calculate_macd_gpu`, `_calculate_bollinger_bands_gpu`, moving-volume and legacy microstructure helpers remain defined. The rewritten `_update_feature_tensors` does not call them, and the Jarvis Part 7 analysis path uses `part7_signal.py`/`quantitative_math`; other external direct calls have not been audited.
- **Part 1:** old fallback/helper telemetry can still use an `atr` field and the legacy `_calculate_volatility_metrics` helper remains outside the replaced native analyzer; no migrated analyzer output is based on that old path.
- **Parts 3, 5, 6, 7, 8, 10 and Jarvis:** residual ATR/EMA/RSI/Bollinger references were comments/docstrings or old non-wired helpers, not calculations in the migrated analyzer / Jarvis entry path. Part 11/12 weight comments still mention the old Part signal descriptions but their live fusion reads signals/evidence, not those indicators.

The scan intentionally distinguishes legacy callable code from the active Jarvis routing. I did not label every remnant as globally unreachable without a whole-repository call graph. If the user means deletion/replacement in every dormant class and external API, this patch alone is not complete on that broader interpretation.

## Verification actually run

All checks were offline with synthetic/local fixtures only. `/tmp/jarvisdeps` supplied pandas for tests; it is not a repository dependency artifact.

- `python3 -m py_compile` on the changed quantitative, Jarvis, Part 1–10/Part 7 gate/live modules, all changed neural Parts and quantitative tests: **PASS**.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/jarvisdeps python3 -m unittest discover -s tests -v`: **44 passed** in 23.991 seconds.
  - Quantitative math/projections/edge tests: 9.
  - Direct Part-entry tests: 3.
  - Jarvis quantitative runtime tests: 4.
  - Part 7 gate/live signal tests: 3.
  - Neural advisory contracts including v3 rejection: 19.
  - PR #101 part integration/device-safety contracts: 6.
- Covered constant/flat and zero-volume input, invalid/insufficient candles, deterministic finite projections for Parts 1–10, Part 7 risk veto, neutral/fail-closed handling, price-unit positive risk floors, no random model, Part 1 adapter, Parts 1–10 fallback routing, smart-entry/slippage clamps, all 12 neural task artifacts as synthetic fixture artifacts, full eight-frame evidence and Parts 11/12, schema rejection, deterministic field integrity, central-approval invariance, CPU fallback/strict-GPU simulation and configured cache limits.

The tests use toy data and mocked artifacts; they are not financial validation, real market-data replay, or GPU hardware tests. The Part 7 live `EnhancedGPULiveDataEngine._update_feature_tensors` rewrite passed Python compilation, but was not instantiated against CUDA/live socket/device hardware.

## Explicit limitations / blockers

- No trained production neural models, reviewed real historical OHLCV, complete point-in-time eight-frame replay data, out-of-sample walk-forward validation, calibration, backtest/PnL/fill/fee/slippage/funding analysis, or deployment validation were provided. Without an identity-correct validated artifact, neural outputs remain `unavailable`.
- No actual GTX1650/4-GB VRAM or 8-GB RAM machine was available. CUDA behavior was tested using deterministic mocks/failure paths only; actual memory, throughput and thermal limits are not measured.
- No full Jarvis startup, exchange test, live data stream, order, bot launch, merge or deployment was run.
- Residual legacy optional helper methods listed above have not undergone a complete cross-repository caller audit.
- A stale Python bytecode file briefly masked the newly added v3-incompatibility regression test in one discovery run; it was removed, and the final run used `PYTHONDONTWRITEBYTECODE=1` and passed all 44 tests.

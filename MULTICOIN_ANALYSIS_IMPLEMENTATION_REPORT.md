# Multicoin analysis foundation — implementation report

## Status and scope

This PR is a **safe, opt-in Part 7 shadow-analysis foundation**, not the requested full Parts 1–12 multi-coin engine. The feature is disabled by default (`JARVIS_MULTICOIN_ANALYSIS=0`). It is designed to gather independent diagnostics without granting them trade-decision authority. It does not enable multi-symbol entries, live multi-position execution, or remove the BTC-only Oracle gate.

The verified base was `main` at `09f1d8aba01e6ac66a4e45e182ccb9d7eea934f4` (2026-09-28). Open PR #94 was reviewed and remains unmerged; its BTC/ETH options-chain scope was not incorporated. No clearly duplicate multicoin PR was found. The PR metadata is authoritative for the final head SHA.

The supplied readiness audit found that Parts 1 and 2 retain shared, unkeyed state and the `JarvisElite` analysis object is mutable and reused across timeframes. Running Parts 1–12 concurrently against that object would risk cross-coin contamination. Therefore this change does **not** fan the full pipeline out in parallel or claim all-Part coverage. It uses the stateless shared Part7 analyzer only, one sequential pass over each native timeframe per background symbol job. Full Parts 1–6/8–12 isolation and execution remain follow-up work.

## Changes

- `direct_candle_cache.py`
  - Snapshot and frame keys now include request identity `(venue, market_type, instrument_id, canonical_symbol)` plus timeframe for frames.
  - Added per-identity refresh locks and a bounded fetch semaphore (default one in-flight client fetch, clamped to 1–4), plus a bounded identity count (default 64, fail closed at capacity).
  - Retains the established **500 completed candles plus a separate forming candle** contract. Provider source remains per-timeframe metadata; forming candles do not enter analysis.
- `jarvis_multicoin_analysis.py`
  - Added `MultiCoinPart7Shadow`: a bounded 1–4 worker executor, capped candidate set (default 15, maximum 30), per-symbol single-flight jobs, candidate retry cadence, freshness/version metadata, closed-frame copies, and fail-closed rejection of incomplete, stale, future, or identity-mismatched snapshots.
  - Stale results remain visible as stale while refresh is throttled/running; they are never executable. Every output is tagged `analysis_only=true`, `decision_authority=none`, `execution_eligible=false`.
  - Candidate symbols are expected to be exact Delta-listed product symbols. This adapter does not add quote-currency aliases. Delta exposes no authoritative product type/ID through this path, so identity is tagged `venue=delta`, `market_type=unverified`, with the exact listed symbol as instrument identifier. Candle provider/source remains separately recorded for each timeframe.
- `jarvis_FIXED.py`
  - Wires shadow polling into the existing live cycle only when the feature flag is enabled and a live direct-candle cache exists. Selected snapshots use the same explicit Delta/unverified/exact-symbol request identity.
  - The shadow status is retained only for diagnostics and is not supplied to trade analysis, decision construction, risk, position ownership/reconciliation, or orders. The selected-route/open-position lock, current execution checks, and BTC-only gate are unchanged.
  - Shadow worker count, candidate count, candidate refresh interval, and maximum result age can be bounded using `JARVIS_MULTICOIN_MAX_WORKERS`, `JARVIS_MULTICOIN_MAX_CANDIDATES`, `JARVIS_MULTICOIN_CANDIDATE_REFRESH_SEC`, and `JARVIS_MULTICOIN_RESULT_MAX_AGE_SEC`.
- `tests/test_multicoin_analysis.py`
  - Offline synthetic coverage includes BTC/ETH/SOL over all eight native intervals, exact request-identity separation, refresh concurrency bounds, bad instrument rejection, serial/parallel Part7 result equivalence, candidate/job limits, stale fail-closed status, default-off/runtime shadow-only wiring, and preservation of the router's open-position symbol lock.

Candidate discovery still occurs synchronously from the live poll when the candidate refresh interval elapses; it does not wait for analysis results but may wait for that discovery call. The existing direct candle client defaults to a single concurrent network fetch, so analysis jobs are bounded/parallel while provider I/O remains conservative. This implementation does not measure or claim live throughput or provider rate-limit compliance.

## Validation evidence

Sandbox-only test dependencies were installed under `/tmp/multicoin-test-deps`; no repository deployment environment was changed.

Focused implementation and regression command:

```sh
PYTHONPATH=/tmp/multicoin-test-deps:$PWD PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  python -m pytest -p no:cacheprovider -q \
  tests/test_multicoin_analysis.py tests/test_direct_candle_cache.py tests/test_market_router.py
```

Result: **25 passed, 1 skipped** in 11.37 seconds. The skipped legacy direct-cache consumer import requires `sklearn`, which is unavailable in this sandbox's partial saved source snapshot; the new runtime-wiring test inspects the actual `LiveTradingEngine.start_live_trading` AST and confirms shadow results are not passed into decisions. Syntax checks for `direct_candle_cache.py`, `jarvis_multicoin_analysis.py`, `jarvis_FIXED.py`, and the new test file passed with `py_compile`.

Non-mutating safety fixtures:

```sh
PYTHONPATH=/tmp/multicoin-test-deps:$PWD PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  python -m pytest -p no:cacheprovider -q tests/test_execution_safety.py \
  -k 'not live_paper_mode_never_sets_leverage_or_submits_order'
```

Result: **9 passed, 1 deselected**. The deselected fixture fails in the unchanged base `jarvis_live_trader.py`: its `_place_trade` calls `_get_sizer(self.delta)` but the fixture has monkeypatched a zero-argument lambda. SHA-256 for that file was identical in the saved base snapshot and local copy. The one-off failure occurs before an order call; no order or exchange request was made.

The supplied offline readiness harness was rerun:

```sh
python /tasklet/threads/a_g80cwnfjq28kppm7nf62/work/multicoin-readiness/offline_readiness_test.py
```

Result: **14 passed**. This harness targets the saved pre-change source snapshot and is baseline context, not evidence for the new feature; the focused test command above exercises the implementation copy.

A synthetic-data timing probe ran the actual `part7_signal.analyze_timeframe` after warm-up against 500 completed candles per interval (single sandbox, `OPENBLAS_NUM_THREADS=1`): `1m 0.0044s`, `3m 0.0043s`, `5m 0.0041s`, `15m 0.0040s`, `30m 0.0042s`, `1h 0.0048s`, `2h 0.0042s`, `4h 0.0046s`. These are narrow calculation timings only—not full Parts 1–12 timings, exchange/network latency, live throughput, or a PC performance guarantee.

## Explicitly unverified / remaining work

- No live exchange request, bot launch, order, testnet run, or deployment was performed.
- Only the actual Part7 numerical analyzer was executed against synthetic BTC/ETH/SOL candles. Parts 1–6 and 8–12 were not constructed or numerically benchmarked.
- Full analysis-state isolation must precede per-coin Parts 1–12 concurrency. In particular, Part1/Part2 state, mutable `JarvisElite` context, independent per-part frame copies, and Part2's repeated MTF mutation must be redesigned or partitioned by the full market identity.
- This shadow foundation refreshes a full 501-row window rather than implementing incremental candle append/replace. It has no live-feed freshness/rate-limit evidence.
- The candidate market type/product identifier is intentionally unverified because the available Delta product adapter does not expose an authoritative type/ID here. No ticker equivalence is asserted.
- Result diagnostics cannot authorize a trade. Multi-position portfolio policy, full venue/market/contract identity in positions, ownership/reconciliation review, and an asset-matched non-BTC Oracle policy remain separate prerequisites. The existing BTC-only Oracle block remains in force.

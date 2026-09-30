# Scalp/Swing 8-Timeframe Implementation Report

**Repository:** `bhagy774/jarvis-scalp`  
**PR:** [#97 — Centralize Parts 1–12 strategy entry authority](https://github.com/bhagy774/jarvis-scalp/pull/97)  
**Pinned `main`:** `89ace9b7600abb2c1bb153b2d86245fe57e752c6`  
**PR head before this update:** `840fcab136852f7041c7a5ab69e97bdc432a67e0` (`feat/jarvis-central-entry-authority-20260929`). Both pins were rechecked against GitHub; PR #97 was open, unreviewed, and unmerged. PR #98 is also open and separately touches `jarvis_FIXED.py` and `jarvis_live_trader.py` for read-only dashboard work; it does not implement this strategy change.

## Implementation

- Native-frame Parts 1–10 evidence now remains individually available for all eight intervals: **1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h**. `jarvis_FIXED.py:6155–6369` replaces the old 1m-primary roll-up as directional authority with the full native evidence matrix. Part 2 now evaluates its zone evidence against the current native frame while retaining its existing 1m/5m/15m contextual zone analysis (`jarvis_FIXED.py:3230–3306`).
- Parts 11 and 12 now accept the named Parts 1–10 results for each of the eight frames, fail closed on missing frames/parts, and return per-frame results plus coverage. Part 11 aggregates its existing fusion signal using native-frame weights; Part 12 computes and aggregates confidence over the same complete evidence (`part11_FIXED.py:1073–1081,1177–1221`; `part12_FIXED.py:1584–1591,1677–1720`). `jarvis_FIXED.py:6339–6371` wires these aggregators into the live analysis; Part 12 coverage validity is required for central confidence.
- Deterministic strategy/mode/trigger selection is centralized in `evaluate_mtf_central_strategy` (`jarvis_strategy_approval.py:357–532`), called from the runtime decision path (`jarvis_FIXED.py:6754–6818`). It first applies the established per-frame Part 1–10 weighted consensus, quorum, Part 2 zone veto, and anchor-dissent policy. The explicit mode policy is: **SWING** uses 3m–4h group evidence; if that group does not establish a direction, **SCALP** may use 1m–15m, guarded by countertrend 30m–4h consensus. Group selection uses the established 65% confluence threshold and native frame weights. This is a conservative explicit mode rule, covered by offline tests.
- **1m is not the universal directional master.** For SWING it is the entry trigger only: neutral 1m leaves the valid higher-timeframe setup `PENDING` with no approval; an opposite trigger blocks; only an aligned trigger can approve. SCALP uses 1m–15m for its directional group but likewise cannot enter on a neutral 1m. A neutral frame is never treated as authorization.
- Complete Part 7 data remains a fail-closed entry gate. The central evaluator requires the exact eight-frame aggregate and validates every row's symbol, timeframe, validity, freshness/data status, and block/veto fields. Per-frame Parts 1–10 identity is checked as well. Scoped approval, execution plan, trade mode, and plan levels remain centrally bound; `jarvis_live_trader.py:57–91,1161–1176`, `jarvis_multicoin_execution.py:191–321`, `jarvis_delta_execution.py:79–164,450–465`, and `delta_api_wrapper.py:79–178` carry/recompute the evidence and validate authorization at the protected Delta boundary.
- Multicoin output remains analysis-only until the Delta candidate bridge independently validates the complete MTF envelope. Binance candle analysis remains distinct from Delta execution identity; existing account, sizing, slippage, ownership/reconciliation, freshness, identity, and protective-order safeguards are retained. No LLM or random model selects mode, direction, or entry.

## Tests and verification

All tests were offline/simulated. No bot launch, live exchange API request/order, deployment, or merge occurred.

- `PYTHONPATH=. pytest -q` — **66 passed** (21.58s) on the final local tree.
- `PYTHONPATH=. pytest -q --tb=short tests/test_central_strategy_approval.py tests/test_delta_execution_bridge.py tests/test_execution_safety.py tests/test_multicoin_execution.py tests/test_multicoin_runtime_bridge.py tests/test_delta_broker_transport.py tests/test_multitimeframe_strategy_policy.py` — **66 passed** (20.48s).
- `python -m py_compile jarvis_FIXED.py jarvis_strategy_approval.py jarvis_live_trader.py jarvis_multicoin_execution.py jarvis_multicoin_pipeline.py jarvis_delta_execution.py delta_api_wrapper.py part11_FIXED.py part12_FIXED.py tests/test_central_strategy_approval.py tests/test_delta_execution_bridge.py tests/test_delta_broker_transport.py tests/test_execution_safety.py tests/test_multicoin_execution.py tests/test_multicoin_runtime_bridge.py tests/test_multitimeframe_strategy_policy.py` — passed.
- `tests/test_multitimeframe_strategy_policy.py` covers scalp/swing distinction, swing pending while 1m is neutral, aligned/opposite triggers, all-eight-frame and per-Part requirements, stale/incomplete/wrong-symbol/blocked Part 7 evidence, Part 11/12 `/8` support and native coverage, and plan/approval mode/freshness binding. The integration/execution suite covers protected Delta authorization, multicoin evidence handoff, entry gates, reconciliation and safety invariants.

## Assumptions and limitations

- Existing Part-level quorum/weights/65% policy and native-timeframe weights are reused. The SWING-versus-SCALP group hierarchy, high-timeframe scalp veto, and mandatory matching 1m trigger are explicit conservative additions; they do not tune candles or silently relax safety thresholds.
- Offline tests use synthetic evidence and simulated broker/market fixtures. They do not establish profitability or validate live market-feed freshness against an exchange.
- The local worktree exposed seven test modules; no wider repository test suite was available. Some unrelated open PR #98 edits overlap source files, so review for merge conflicts before either PR is merged.

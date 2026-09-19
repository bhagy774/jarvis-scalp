# JARVIS audited safety correction report (latest-main integration)

Repository: `bhagy774/jarvis-scalp`
Base tested: `main` at `5cea878888bc2c26fe491843cca1e4ccc2adac25` (PR26 merged).
This document describes clean integration PR #27; it is not a merge or deployment record.

## Integrated safety corrections

- Preserves PR26 direct native candle acquisition, closed/forming separation, close coordinator, runtime metadata, Ollama context, and Part7 fail-closed analyzer.
- Locks the selected route symbol through MTF, institutional/options, reversal, and position paths; invalid empty-scanner routes block instead of silently selecting BTC.
- Uses canonical confidence/decision normalization and one post-PreSim/scenario/gate snapshot for dashboard, paper ledger, and auto-trader. Opinion conflicts and selected-asset options/institutional gaps block live execution.
- Resolves recognized Delta contract metadata into quote notional and sizes whole contracts against margin, stop-loss risk, policy/product leverage caps, and balance. Missing/ambiguous live metadata blocks rather than assuming one contract equals one USDT.
- Keeps paper mode from submitting orders or setting venue leverage; close paths use `reduce_only` and stable `client_order_id`, with ownership and ambiguous-close reconciliation guards.
- Redacts proxy credentials, retries transient Binance mirror responses, records Bybit linear-perpetual provenance, and blocks non-spot fallback unless explicitly opted in.
- Validates watchdog thresholds and maintains live-loop heartbeat; dashboard formats unavailable confidence as `N/A`, not `N/A%`.
- Keeps optional startup fail-safe: if optional wiring is incomplete, the heavy Part2 engine is not constructed and its deterministic range fallback remains available.

## Exact PR file set

- `CHANGE_REPORT.md`
- `binance_data.py`
- `delta_api_wrapper.py`
- `jarvis_FIXED.py`
- `jarvis_dashboard.py`
- `jarvis_decision.py`
- `jarvis_live_trader.py`
- `jarvis_position_manager.py`
- `jarvis_position_ownership.py`
- `jarvis_risk.py`
- `jarvis_sizer.py`
- `jarvis_watchdog.py`
- `ollama_integration.py`
- `part7_signal.py`
- `tests/test_audit_regressions.py`
- `tests/test_auto_risk_dashboard.py`
- `tests/test_presim.py`

No `.orig`, cache, logs, credentials, or unverified legacy/manual files are included. The separately requested legacy cleanup remains deferred pending evidence that imported files are unused by runtime/tests/config/docs.

## Offline verification

Credentials and execution variables were unset: `DELTA_API_KEY`, `DELTA_API_SECRET`, `BINANCE_API_KEY`, `BINANCE_API_SECRET`, `DELTA_ORDER_EXECUTION_ENABLED`, and `DELTA_USE_MAINNET`. No exchange access, order, leverage mutation, credentialed startup, deployment, or live/manual test was performed.

- Changed runtime modules: `python -m py_compile` passed.
- Audit/execution/auto-risk/Part7/backtest grouped safety tests: 43 passed.
- PreSim module in isolation: 22 passed.
- Additional offline modules: 30 passed (model/learning, backtest coverage, clean output, cross-source); 78 passed with one expected mocked-thread warning (data/feature/Ollama group); paper launch 1 passed; runner integration 5 passed; scenario simulator 9 passed.
- Optional wiring: initialization group 5 passed; missing-module fail-safe parameters 8 passed, 5 deselected after bounded startup optimization.
- Direct candle, runtime safety, routing, quote fallback, options context, and related safety tests passed in the grouped run; one combined-run PreSim fallback was an environment-isolation artifact and the isolated 22-test PreSim module was clean.

A repository-wide one-shot run was not used as evidence because the legacy module graph exhausted the sandbox during heavy collection. Hosted CI should run the final complete suite with an adequate timeout.

## Remaining review gates

1. Verify the current Delta product metadata schema before any live enablement; unknown keys intentionally remain blocked.
2. Confirm deployment has one authoritative lifecycle/close manager; coordinator/ownership is process-local and ambiguous close remains `CLOSE_UNKNOWN` until reconciled.
3. Oracle initialization remains historically early, although non-BTC data cannot satisfy a non-BTC execution gate; route-aware initialization is a follow-up.
4. Hosted CI and human review are pending. Merge was not performed.

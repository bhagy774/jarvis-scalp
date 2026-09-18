# JARVIS audited safety correction report

## Source snapshot

- Repository: `bhagy774/jarvis-scalp`
- Base: current `main`
- Verified fresh recursive Git tree: `fad84180b5ff22edb90ce7550e0581c9660eaff8` (not truncated; this is a tree SHA, not a commit SHA).
- Branch/commit HEAD was not independently resolved because GitHub branch/commit listing access was not available.
- No merge, push to `main`, bot launch, exchange/order/leverage call, or network/manual trading test was performed.

## Corrective changes

### Symbol and data integrity

- Route selection remains locked before price/candle analysis; MTF, institutional, reversal, position-monitor, and legacy position-manager reads use the selected symbol.
- Removed silent BTC selection from an empty scanner result; invalid/no candidate routes are `BLOCKED`.
- Selected-asset options context is primary for execution. BTC options/oracle information is labeled macro-only and cannot silently serve as altcoin execution evidence. Live selected-asset options/institutional context is a required, non-bypassable gate; paper mode remains offline/advisory.
- BTC-only Oracle paths are explicitly unavailable for non-BTC execution routes.
- Binance mirrors retry geo/rate-limit/transient responses before changing venue; proxy logs redact credentials. Bybit fallback records `bybit_linear_perpetual` / `linear_perpetual` semantics. Delta's hybrid wrapper rejects non-spot fallback data unless `JARVIS_ALLOW_PERPETUAL_FALLBACK=1` is explicitly set.

### Risk and execution safety

- Live sizing resolves recognized Delta contract units/value and calculates quote notional, margin, leverage, and risk from actual contract metadata. Missing, ambiguous, or invalid metadata/balance blocks live execution; no one-USDT contract assumption remains in live paths.
- Position records and dashboard/P&L use recorded contract value/notional.
- Live execution remains independently gated by auto-trade, mainnet, live execution, and order-execution flags; paper mode does not submit venue orders or set venue leverage.
- `DOCTOR_STALE_THRESHOLD` rejects malformed/non-positive values and falls back to 600 seconds. The live loop beats the watchdog before route/price/candle acquisition, including total data-outage cycles.

### Canonical decision and output

- Added `jarvis_decision.py` as the dependency-free confidence/decision contract. Confidence accepts numeric, `%`, fraction, and autonomy forms while preserving unavailable/rejected values as `N/A`.
- One authoritative final snapshot carries symbol, price, canonical BUY/SELL/NO_TRADE direction, confidence, entry/TP/SL/expiry, reasons, options context, and execution status.
- PreSim and scenario/entry gates now run before the snapshot is built; the paper ledger, auto-trader, and dashboard consume the same post-gate direction/confidence. Unresolved BUY/SELL opinion conflicts block rather than fabricate consensus.
- Legacy recommendation-like terminal output was routed to structured logging or the unified dashboard; no second active terminal recommendation is intended.
- Dashboard rendering avoids `N/A%` and consistently displays source/coin, plan, sizing, leverage, gates, and status.

## Exact PR file set

Expected source changes:

- `binance_data.py`
- `delta_api_wrapper.py`
- `jarvis_FIXED.py`
- `jarvis_coin_scanner.py`
- `jarvis_dashboard.py`
- `jarvis_decision.py` (new)
- `jarvis_live_trader.py`
- `jarvis_market_oracle.py`
- `jarvis_position_manager.py`
- `jarvis_risk.py`
- `jarvis_sizer.py`
- `jarvis_watchdog.py`
- `oracle_trade_gate.py`
- `tests/test_audit_regressions.py` (new)
- `tests/test_auto_risk_dashboard.py` (metadata fixture update)
- `CHANGE_REPORT.md` (this report)

The 15 legacy/manual scripts and `tests/test_runner_integration.py` were not deleted: safe unused-by-runtime/tests/config/docs verification was not established. Deletion is deferred.

## Verification

Targeted compile passed:

```text
python -m py_compile delta_api_wrapper.py jarvis_decision.py jarvis_risk.py jarvis_sizer.py \
  jarvis_dashboard.py jarvis_watchdog.py binance_data.py jarvis_live_trader.py \
  jarvis_FIXED.py jarvis_position_manager.py tests_test_audit_regressions.py
```

Offline safety/regression suite passed:

```text
python -m unittest tests_test_audit_regressions.py \
  tests_test_execution_safety.py tests_test_auto_risk_dashboard.py \
  tests_test_options_context.py -q
```

Result: **25 passed, 1 skipped**. The skip is selected-symbol MTF import coverage because optional `websockets` is unavailable. The local harness copies correspond to repository test paths listed above; no exchange/network calls were made.

## Limitations and remaining review items

- No dependency-complete full repository suite, lint/type check, frontend build, Windows run, or live startup was performed.
- No authoritative Delta contract schema was available; unrecognized venue schemas intentionally remain blocked until metadata mapping is confirmed.
- Bybit perpetual fallback is explicitly blocked by default for Delta's spot-compatible hybrid consumers; enabling it requires operator confirmation that downstream analysis accepts perpetual semantics.
- The Oracle service is still initialized before route selection for historical compatibility, but its non-BTC influence is blocked/excluded. Route-aware initialization/removal remains a follow-up.
- Remaining lifecycle/status prints (initialization, emergency stop, close reports) should be audited separately; recommendation-like active analysis output is logged/dashboard-owned.
- `jarvis_position_manager.py` and `jarvis_live_trader.py` both contain lifecycle paths; offline tests covered safety but no live integration was run. Confirm deployment uses one authoritative position/close manager before enabling live execution.

## Safe review/run instructions

1. Review this PR and the exact changed-file list; verify the Delta product metadata keys against the venue's current schema.
2. Run the targeted offline commands above with credentials unset and live execution flags disabled.
3. Keep `JARVIS_ALLOW_PERPETUAL_FALLBACK` unset unless perpetual semantics are intentionally supported.
4. Do not treat offline pass results as startup, exchange, or live-trading verification. Do not merge until reviewer checks contract metadata, lifecycle ownership, and remaining Oracle initialization behavior.

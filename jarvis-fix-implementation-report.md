# Jarvis bounded runtime-fix implementation report

Date: 2026-09-18
Base: `main` at `fad84180b5ff22edb90ce7550e0581c9660eaff8`

## Scope delivered

- Fixed executable `pattern_mtf` assignment and preserved a defined empty branch, allowing the selected-symbol analysis path to reach final signal construction instead of failing with an unbound-local error.
- Made PreSim veto bookkeeping non-authoritative and fail closed on simulator exceptions. Missing dashboard state can no longer turn a committed veto into an entry; an explicit `JARVIS_PRESIM=0` remains the bypass.
- Added centralized local runtime detection (`auto` CUDA → MPS → CPU), normalized device helpers, honest name/count/memory/fallback telemetry, and explicit per-native-engine fallback diagnostics. Optional native modules are not constructed when PyTorch is unavailable, preventing the known string-device `.type` startup exception.
- Propagated backtest mode from `JARVIS_BACKTEST_MODE=1` through `Jarvis4EngineSystem` to `JarvisElite`, and skipped live-engine construction in replay mode.
- Added reduce-only and stable client-order IDs to Delta orders. Both close owners use one process-local close claim, read-only position reconciliation, and fail-closed ambiguous/partial/malformed/symbol-mismatched outcomes. Emergency close uses the same ownership contract.
- Added bounded live readiness (`STARTING`, `READY`, `NOT_READY`, `STOPPING`, `STOPPED`) and `stop_live_trading()` with a bounded join; unavailable route retries remain explicitly `NOT_READY` rather than being treated as a successful startup.
- Added bounded secret-redacted same-symbol Ollama snapshots with freshness/missing markers, Parts 1–12, fusion/confidence, MTF/options, risk/position/order/runtime/gates. Structured JSON output is validated; model output is advisory and cannot bypass local safety. Remote `/api/ps` metadata is reported separately; no model downloads or implicit preload.
- Extended the unified terminal dashboard with readiness and AI rationale while retaining one display containing decision, rationale, plan, gates, account/risk, AI suggestion, and GPU state.
- Added README configuration and safety boundaries.

## Verification

Safe offline staged copy (network/order flags disabled, `JARVIS_DEVICE=cpu`, `JARVIS_BACKTEST_MODE=1`, `OLLAMA_PRELOAD_COMMITTEE=0`):

- `pytest -q`: **198 passed, 2 warnings**, 17.33 s.
- `python -m compileall -q .`: passed across staged source.
- Focused synthetic selected-symbol test: all 12 adapters returned dictionaries; bounded ETHUSDT snapshot and validated WAIT advisory completed.
- Focused close tests cover ownership, timeout/remaining exposure, symbol mismatch, malformed state, reduce-only, and client-order-ID payloads.
- Focused dashboard/runtime tests cover CPU fallback with unavailable torch, no secret leakage, validated/invalid responses, readiness display, and advisory-vs-authoritative display.

Warnings were the existing FastAPI `on_event` deprecations. One existing doctor test attempts a localhost Ollama health probe and reports unavailable; no authenticated exchange call, order, leverage change, model download, or remote service was used.

## Limitations / not claimed

- This environment has no PyTorch/CUDA and no Ollama server; native CUDA execution, GPU performance, and actual remote model residency are unverified. Local detection does not imply remote Ollama GPU use.
- Exchange reduce-only/client-ID semantics were verified against public Delta documentation and payload tests, not a live order. A `CLOSE_UNKNOWN` claim requires operator/venue reconciliation; this change intentionally does not retry blindly.
- No live startup, real candles, websocket longevity, venue fills, contract multiplier, or profitability certification was performed. Do not merge/deploy/live-trade based on this PR alone.

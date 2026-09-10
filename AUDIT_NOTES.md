# Repair and validation notes — 2026-09-10

## Included in this change

- Removed embedded Delta credential defaults and Upstox diagnostic credentials; protected the two credential diagnostics behind explicit network opt-in.
- Private Delta requests without credentials fail locally. Order/leverage changes require explicit execution opt-in and validated inputs.
- Paper execution avoids venue order/leverage calls. Paper entrypoints reject inherited live execution flags.
- Added risk-sizing bounds and no-invented-balance behavior. Close bookkeeping waits for confirmation; ambiguous closes retain `CLOSE_UNKNOWN`.
- Corrected double leverage application under the repository's own USD-notional assumption. Venue contract verification remains mandatory.
- Required requested live hedges or attempted compensating closure; removed duplicate position monitoring. This is not atomic hedging.
- Oracle hard gate rejects unavailable/incomplete/WAIT data; hedged scalp model is explicitly paper-only.
- Deribit construction no longer authenticates; unnecessary numerical dependencies removed from that client.
- Reconciled coordinator/monolith telemetry with the current HUD instead of a missing backend/obsolete port. Local bounded display-only ingestion uses a coordinator token.
- React WebSocket supports same-origin HTTPS, development proxying, basic frame validation and cleanup without reconnect-after-unmount.
- Fixed missing ThreadPoolExecutor import, declared HUD runtime dependencies, replaced unrelated installer and unsafe server bootstrap, and added safe offline test discovery.

## Final verification scope

- 16 offline regression tests passed: execution safeguards, runner/HUD telemetry contract, and paper/live flag conflict.
- Python source compilation passed across the repository (without executing entrypoints).
- Ruff F821 undefined-name check passed for top-level Python files.
- React production build passed; lint returned zero errors and 36 warnings.
- Package install audit reported zero npm vulnerabilities at execution time; this is not a complete dependency security audit.
- Diff whitespace check and POSIX installer syntax check passed.

No exchange, AI, notifier, real-order, GPU, full-entrypoint, browser end-to-end, or Windows execution tests were performed. Existing live/network diagnostics were not run. FastAPI lifecycle deprecation warnings and a large frontend bundle warning remain.

## Not solved / release restrictions

This is a tested repair batch, not a claim that every defect in ~39,000 lines was eliminated. Earlier broader draft reviews are not the shipped result. Data/AI cache, timezone, fallback, legacy diagnostics and full cross-engine lifecycle behavior need further work. The legacy standalone HTML HUD requires further security review; do not expose it publicly. The HUD lacks user authentication and needs an authenticated reverse proxy.

Exchange API schemas/product IDs/multipliers and real fills remain unverified. There is no durable persisted reconciliation workflow. Failed/ambiguous hedge compensation can leave venue exposure. Synthetic options P&L is not evidence of executable protection. Do not enable live trading until these blockers are independently resolved.

Rotate exposed Delta and Upstox credentials at the providers, including tokens in Git history. The changes do not revoke provider credentials or rewrite history.

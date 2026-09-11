# JARVIS Scalp

## Local AI (Ollama only)

JARVIS runs on **local Ollama models only** by default. No external cloud AI is
contacted unless you explicitly opt in via environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server URL used by the DeepSeek V3/R1 brains and specialist pool. |
| `JARVIS_ENABLE_GEMINI` | `0` (off) | Set `1` **and** provide `GEMINI_API_KEY` to enable the external Gemini Supreme Advisor. Otherwise it is skipped at startup. |
| `JARVIS_ENABLE_EXTERNAL_AI` | `0` (off) | Set `1` to enable external AI clients (e.g. KIE GPT-6). When off, external clients return a clean `disabled` result and never make a network call. |

If Ollama is unreachable, the local brains degrade gracefully through their
existing fallbacks.

## Crash recovery & watchdog

`jarvis_watchdog.py` provides:

- **Startup reconciliation** — compares persisted local open trades
  (`jarvis_state.json`) with exchange open positions; logs mismatches and
  adopts exchange truth. Fail-safe: any API error is logged and startup
  continues; it never places orders.
- **Watchdog thread** — every 60 s checks heartbeats of core services (brain
  loop, data feeds) and alerts via log (and Telegram if configured). Detection
  + alerting only; no auto-restart. `get_health()` returns a status dict.
- **State persistence** — open paper trades are saved to `jarvis_state.json`
  on open/close for reconciliation after a crash.

Disable with `JARVIS_WATCHDOG=0`. All wiring in `jarvis_FIXED.py` is guarded by
`try/except` so the watchdog can never break startup. Paper-mode safety guards
are unchanged.


Python trading/analysis modules with a React/Vite dashboard and a local FastAPI HUD. This repository is experimental, not production-ready trading software. Offline tests do not establish profitability, exchange compatibility, or live safety.

## Safe installation and tests

Use Python 3.12+ and Node.js 22+.

```sh
python -m venv .venv
# Activate .venv for your platform before the following commands.
python -m pip install -r requirements.txt
python -m pip install pytest httpx
python -m pytest -q
cd jarvis_web
npm ci --ignore-scripts
npm run build
npm run lint
```

`pytest.ini` limits normal collection to `tests/`. Root-level `test_*.py` files are legacy network diagnostics, NOT the offline regression suite. Do not run them against production credentials.

`install.cmd` and `setup_server.sh` install checkout dependencies only; they do not start trading/services or download unrelated executables/models. Windows launchers have not been executed on Windows in this review.

## Paper startup

Keep `JARVIS_AUTO_TRADE`, `JARVIS_LIVE_EXECUTION`, and `DELTA_ORDER_EXECUTION_ENABLED` unset or `false`. Set `JARVIS_START_PAPER=1` only when intentionally starting networked paper monitoring. The Python entrypoints reject paper startup if any of those live flags is `true`. On Windows, `run_jarvis_live.ps1 -StartPaper` launches once without automatic restart.

Paper mode can still request market data and call configured AI services. Full entrypoint execution has not been validated here; optional engines/models may need additional setup. Do not mistake a successful unit test for full system readiness.

## Dashboard

The HUD defaults to `127.0.0.1:7788`. Vite development proxies `/ws`, `/chat`, and `/api` to that address. Production requires an authenticated reverse proxy routing these paths to the HUD. React derives `ws:`/`wss:` from its page; `VITE_JARVIS_WS_URL` can override it at build time.

The coordinator sends display-only `/api/telemetry` with a per-launch token. A manually started HUD without a token accepts loopback telemetry. Origin filtering and loopback binding are NOT user authentication; never expose the HUD directly to the internet. The legacy standalone HTML HUD has not received a complete security/browser review.

## Credentials and live trading

Previously committed Delta and Upstox credentials/tokens must be treated as exposed. Revoke/rotate them at the providers. Removing literals from the new branch does not remove Git history. Use environment variables, never source literals.

New execution opt-ins are safeguards, not certification. Before any live operation, independently verify exchange product IDs, contract multiplier, sizing/P&L, order/fill/close responses, hedging and durable reconciliation. `CLOSE_UNKNOWN` needs operator reconciliation; do not blindly retry or restart. See `AUDIT_NOTES.md` for the exact tested scope and unresolved risks.

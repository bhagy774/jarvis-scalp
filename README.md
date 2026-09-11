# JARVIS Scalp

## Local AI (Ollama only)

JARVIS runs on **local Ollama models only** by default. No external cloud AI is
contacted unless you explicitly opt in via environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server URL used by the DeepSeek V3/R1 brains and specialist pool. |
| `OLLAMA_MODEL` | unset (auto) | Pin a specific Ollama model. When unset, JARVIS auto-detects from installed models (`GET /api/tags`) using a preference order (phi3.5/phi3 → qwen2.5 → mistral → llama3.1/llama3 → deepseek-r1 → gemma2 → whatever exists). The choice is logged once at startup and cached in-process. |
| `JARVIS_LEARNING` | `1` (on) | Set `0` to disable the Learning Loop (trade-outcome recording and per-engine adaptive weights). |
| `JARVIS_PRESIM` | `1` (on) | Set `0` to disable the Pre-Trade Simulator (instant offline history check before each paper entry). |
| `JARVIS_PRESIM_MIN_RR` | `1.0` | Minimum reward:risk ratio required by the Pre-Trade Simulator; setups below this are vetoed. |
| `JARVIS_PRESIM_BUDGET_MS` | `500` | Time budget (milliseconds) for the pre-trade simulation. When exhausted, remaining checks abstain (pass). |
| `JARVIS_ENABLE_GEMINI` | `0` (off) | Set `1` **and** provide `GEMINI_API_KEY` to enable the external Gemini Supreme Advisor. Otherwise it is skipped at startup. |
| `JARVIS_ENABLE_EXTERNAL_AI` | `0` (off) | Set `1` to enable external AI clients (e.g. KIE GPT-6). When off, external clients return a clean `disabled` result and never make a network call. |

If Ollama is unreachable or has no installed model, the local brains degrade
gracefully through their existing fallbacks (log: "No Ollama model found — AI
brains in math-fallback mode").

## Learning Loop

`jarvis_learning.py` records every closed paper-trade outcome (timestamp,
symbol, direction, entry/exit, P&L, plus the per-engine signal snapshot when
available) into `jarvis_learning.json` (atomic writes, corruption-safe).

From those outcomes it maintains per-engine running stats (trades, wins,
losses, win rate) and derives a weight multiplier in `[0.5, 1.5]`
(`0.5 + win_rate`: 0% win rate → 0.5, 50% → 1.0, 100% → 1.5). Engines with
fewer than 10 recorded trades stay neutral at `1.0`. The brain's weighted
signal fusion multiplies each engine's static weight by this factor, so
consistently winning engines gradually get more say and losing ones less.

Everything is fail-safe — any error is logged and ignored, never breaking the
trading loop. Disable with `JARVIS_LEARNING=0`.

## Pre-Trade Simulator

`jarvis_presim.py` runs a fast, fully offline "instant backtest check" on
every candidate ENTER signal **before** the paper trade is opened — *"aa
setup history ma kaam karyu hato?"* (did this setup work in history?). It
never touches the network and never blocks the decision loop beyond a bounded
time budget (`JARVIS_PRESIM_BUDGET_MS`, default 500 ms).

Three checks (each returns pass / adjust / veto with a reason):

1. **Historical win-rate** — win rate of similar recorded trades (same
   direction + symbol, + regime when available) from `jarvis_learning.json`.
   Fewer than 5 similar trades → abstain (`pass`, delta 0) — it never vetoes
   on missing data. Win rate < 35% → veto; < 50% → confidence penalty;
   ≥ 60% → small boost.
2. **R:R sanity** — TP/SL from `smart_tpsl_calculator` (import guarded);
   reward:risk below `JARVIS_PRESIM_MIN_RR` (default 1.0) → veto.
3. **Volatility regime** — ATR extremely low/high vs price (or an extreme
   `volatility` label in the market snapshot) → `adjust` with a small
   confidence penalty, never a veto.

The brain (`jarvis_FIXED.py`) calls the simulator after its fused decision
and existing safety/risk checks, just before the paper-trade open path.
`veto` skips the entry and logs `[PRESIM] VETO: {reason}`; `adjust` applies
the confidence delta (clamped ±10); `pass` is silent. Veto/adjust counts are
tracked in `presim_stats` and shown in the compact status line. The whole
call is fail-open — any exception behaves as `pass`. Disable entirely with
`JARVIS_PRESIM=0`.

## Data Validator

`jarvis_data_validator.py` is a pre-brain data quality gate that ensures the
brain (`JarvisElite.analyze_trade_setup()`) never makes a trading decision on
stale, incomplete, or suspicious data.

**Four checks run on every cycle, before any analysis begins:**

1. **Completeness** — OHLC values must all exist; NaN, None, and Inf are
   rejected.
2. **Price Sanity** — price must be > 0 and must not jump > 20% from the
   last known good price (spike filter). The spike filter does **not** update
   its reference on a rejected candle, so recovery after a bad tick is
   automatic.
3. **Staleness** — the data timestamp must be < 30 seconds old. Millisecond
   timestamps are auto-detected and converted. Future timestamps are also
   flagged.
4. **Cross-Source** — Delta vs Binance live price divergence:
   - \> 1% → warning logged, trading continues.
   - \> 3% → this cycle is blocked (`WAIT/NO-DATA`).

When any check fails the brain receives a `NO_TRADE` signal with reason
`WAIT/NO-DATA: <details>` — it never sees the bad data. Reject and warning
counts are shown in the compact status line (`DV: 2R/1W`).

| Variable | Default | Meaning |
| --- | --- | --- |
| `JARVIS_DATA_VALIDATOR` | `1` (on) | Set `0` to disable all validation (data passes through unchecked). |

Safety guarantees:
- **Fail-open**: if the validator itself crashes, data passes through. The
  validator can never break the brain.
- Thread-safe counters (supports concurrent cycle evaluation).
- Zero network calls — pure local validation only.
- Per-source spike tracking (Delta and Binance maintain independent last
  prices).

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

## Kill-switch & Daily Report

**Kill-switch:**
JARVIS provides an emergency kill-switch. If you create a file named `STOP_JARVIS` in the root folder, the live trading loop will perform a safe exit immediately. Open positions are intentionally left open so you can manage them manually.
- To disable this check, set `JARVIS_KILL_SWITCH=0`.
- A Telegram notification ("JARVIS stopped via kill-switch") is sent upon shutdown.

**Daily Report:**
A comprehensive performance report is sent to Telegram daily at a configured time (default 20:00). It includes the number of trades taken, win rate, total P&L, best/worst trades, PreSim vetoes, Data Validator rejects, top AI engines, system uptime, and error count.
- Disable with `JARVIS_DAILY_REPORT=0`.
- Change time using `JARVIS_REPORT_TIME=20:00` (e.g., IST).
- The report is sent via `telegram_notifier.py`.

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

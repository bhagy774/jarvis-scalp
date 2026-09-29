# Parts 1–12: constrained trained-model advisory path

This adds an **optional advisory channel**, not neural entry authority. Jarvis still computes Parts 1–10 deterministically, Part 11 deterministic evidence fusion, Part 12 a heuristic confidence score, and the PR97 central policy controls every new-entry decision. Advisory metadata never rewrites `signal`, `confidence`, Part 7's block, risk/size/stops/targets, ownership, reconciliation, or execution state.

## Current model status

No historical training dataset or validated trained weights are included. Therefore **there is no model available to make a trained neural prediction today**: every relevant Part should report `neural_advisory.status = unavailable` until a real, identity-matched artifact has been trained offline, reviewed and copied into the configured local model directory. This change does not create example weights, ship synthetic artifacts, or turn random initialization into a prediction.

Parts 1–10 each supply a different 12-value OHLCV feature schema to a small MLP: breakout/levels; volume-weighted zones; candle psychology; signed-volume/profile; normalized return/regression statistics; EMA/directional trend; volatility ratios; structure breaks; signed-flow/CVD proxies; and candle streak/transition statistics. These are separate part-specific feature vectors, not ten large resident models. Parts 11 and 12 are correctly marked `not_applicable`: they aggregate deterministic evidence / compute heuristic confidence and are not independent prediction parts. Part 12 confidence is not calibrated probability.

## Runtime safety / identity / hardware

`neural_advisory.py` uses only Python stdlib at runtime: no import-time device allocation, model construction, training, exchange calls, or network. Inference is pure CPU Python-float arithmetic for a fixed 12→16→3 MLP whose weights were trained in float32, loaded from a JSON-only artifact (never `pickle`/`torch.load`). It checks format/schema/part and exact venue, market type, instrument ID, symbol, and timeframe; a strictly contiguous 64-bar closed-candle suffix; snapshot freshness; finite OHLCV/features; training/validation/test counts; chronological holdout gates; and a training-data cutoff. The model cannot infer on a candle at or before its own training dataset endpoint, is rejected in a historical backtest if it was trained after that evaluated candle, and live artifacts whose source data is over 90 days old fail closed. The 90-day source-age gate is conservative policy, not a performance finding. Artifact and prediction caches are bounded (16 models / 256 prediction keys), and inference concurrency is 1. Repeats are keyed by the full identity, timeframe, closed candle timestamp, feature-vector fingerprint and artifact revision; duplicate calls for one candle are re-used. Missing/stale/mismatched/bad data/artifacts return an explicit `unavailable` reason, never fabricated output. JSON metadata and recorded hashes are validation/provenance fields, not a cryptographic signature; only artifacts created through the reviewed offline trainer and retained in a controlled local directory should be trusted.

The runtime deliberately uses CPU and does not allocate GTX 1650 VRAM. That avoids CUDA OOM rather than relying on an unmeasured GPU path. Offline training is CPU/float32 by default; `--device cuda` is an explicit opt-in for the compact model and catches CUDA OOM to restart in CPU mode. The supplied hardware is GTX 1650 with 4GB VRAM and 8GB system RAM; resource use/performance on the user's PC has **not** been measured or verified. No speed/performance guarantee is made.

## Offline training (requires real, reviewed historical data)

`train_part_advisory.py` consumes a one-instrument CSV with columns:

`timestamp,open,high,low,close,volume,is_closed,venue,market_type,instrument_id,symbol,timeframe`

Every row must be explicitly closed, contiguous at the native timeframe interval, chronological and unique; all identity columns must match CLI flags. It uses the last 64 bars only to form features and labels each sample with future close return over `--horizon` bars: SELL/neutral/BUY relative to `--neutral-bps` (default 20bp). That is a **forward-return proxy**, not PnL; it does not model order fills, fees/funding, slippage, sizing, stops, market impact, or profitability. No leakage is allowed across chronological 70/15/15 train/validation/test time regions: samples whose forward label crosses the cut are purged. Scaling is fitted on train only; validation selects early stop; test is held out. The artifact records a SHA-256 of the exact input CSV, trainer/PyTorch versions, UTC training time, identity, schema, and metrics (the CSV itself is never committed). The small model uses PyTorch on CPU by default with AdamW, mini-batches, bounded row count, and float32. A JSON artifact is emitted only after both validation and test accuracy exceed their majority-label baseline by 2 percentage points; this is a minimal statistical sanity gate, not model authorization or evidence of strategy efficacy.

Example after preparing an actual, identity-homogeneous closed-candle file:

```bash
python train_part_advisory.py /path/to/closed_BTCUSD_1m.csv \
  --part part5_ml --venue delta --market-type futures \
  --instrument-id BTCUSD --symbol BTCUSD --timeframe 1m
```

This fails closed when data is absent/invalid/insufficient or when held-out gates do not pass, and writes no artifact in those cases. It will not overwrite an existing identity-bound artifact unless `--replace` is explicitly passed. It does not call the exchange or start Jarvis. To train other Parts, pass their respective `--part part1_breakout` … `part10_candlestats` option; artifacts are exact-identity and timeframe bound. Set `JARVIS_NEURAL_ARTIFACT_DIR` to the local directory when Jarvis runs.

## Verification and limitations

New `tests/test_neural_advisory.py` uses only temporary synthetic artifact fixtures to test schema/identity/freshness failures and isolated inference semantics; those fixtures are never saved as production artifacts. Chronological sample boundary tests also use synthetic rows only to test split mechanics. PyTorch CPU training and runtime loading were exercised end-to-end once on a strongly predictable temporary synthetic candle fixture solely to test trainer serialization and inference compatibility; its model and data were kept under `/tmp` and were not included in the repository. This is not market evidence. No real historical dataset or production artifact was supplied, so there is still no usable trained model. Existing Part7/MFT/entry-gate regression tests were run on the PR97 snapshot where their scoped dependencies were available. Full bot import/start, exchange calls, live inference, user's GPU/CPU benchmarks, model calibration, backtesting and profitability were not performed.

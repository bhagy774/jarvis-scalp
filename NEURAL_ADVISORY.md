# Parts 1–12: part-owned neural advisory models

## Scope and safety boundary

This change provides **twelve separate task-specific model contracts**. Each Part has its own feature math, network topology, output head, label/target definition and named advisory output. Parts 1–10 receive their native closed-candle OHLCV frame; Parts 11–12 receive the actual complete eight-timeframe × ten-Part evidence matrix already produced by Jarvis. The shared `neural_advisory.py` is limited to bounded local artifact/identity/freshness validation, CPU/CUDA inference dispatch, and caches. Each original `partN_FIXED.py` analyzer now owns its task-specific advisory entry (Parts 1, 3–10 use their original `analyze` methods; Parts 11–12 use `analyze_multi_timeframe`; Part 2 uses `AdvancedAnalysisSystem.analyze_native_zone`, called directly by Jarvis's Part 2 adapter). These entries dispatch to `neural_parts/part1.py` through `part12.py`, each of which owns its feature projection, architecture/head contract, and offline target. Each task module also interprets its head scores into task-specific `task_output` fields. Jarvis does not make a second external annotation call; it only passes identity, timeframe, freshness, and MTF evidence into original analyzer methods. The shared dispatcher does not select a generic feature vector/topology/label or erase task-specific output semantics.

All model outputs are **diagnostic/shadow advisories only**. Existing Part logic remains in force. No neural result changes deterministic `signal`, Part 11/12 output fields, calibrated confidence, Part 7 veto, central approval, trade mode, symbol/timeframe gates, position/risk/sizing, SL/TP, ownership, reconciliation, close/exit, or order authority. Jarvis remains the sole final new-entry authority. Full eight-TF evidence remains intact and 1m execution timing remains distinct from higher-TF setup evidence.

## Independent model contracts

All heads are trained independently and bound to the part, exact instrument identity and timeframe. Hidden widths/activations and head shape vary by task. Ten candle heads use separate 12-feature projections; fusion uses 24 MTF features; confidence uses 18 MTF features. Inference is stdlib-only CPU arithmetic; it never imports PyTorch or reserves GPU. Artifacts from the prior centralized schemas are rejected under strict schema v4.

| Part | Part-owned feature preparation and maths (schema v4) | Network / head | Offline target and advisory output |
|---|---|---|---|
| 1 Breakout | 1/4/16-bar log returns, prior-20-bar escape/failure, range location, robust volume surprise, signed candle geometry, Theil–Sen trend, state velocity, BIC change evidence and OHLCV flow proxy | 12→20 ReLU→8 tanh→3-way softmax | First-touch event on an empirically scaled barrier; `bear_break / no_break / bull_break` |
| 2 Zone | Recency-weighted confirmed-extrema clusters, robust support/resistance distance and strength, range location, volume-distribution node and concentration, return and trend evidence | 12→16 tanh→6 ReLU→3-way softmax | Near-edge support rejection / zone acceptance / resistance rejection from past-window zones and future response |
| 3 Psychology | Candle body/wick/close-location geometry, robust body-effort surprise, gap and range scaled by empirical OHLC variation, transition entropy, returns and robust volume surprise | 12→10 tanh→4 ReLU→1 sigmoid | Whether a forward move reverses candle-body direction; binary uncalibrated score |
| 4 Volume | Robust volume surprise, overlap-volume profile concentration/node distance, close-location-times-volume flow proxies, flow/return divergence, log-volume slope, return, range and realized volatility | 12→18 ReLU→8 ReLU→3-way softmax | Forward direction with volume evidence; profile/flow are OHLCV proxies only |
| 5 Statistical ML | Robust drift/SNR, Theil–Sen slope, multi-horizon log returns, state-space velocity/innovation, BIC change gain, volume surprise, realized-variance ratio, downside volatility and peak drawdown | 12→24 ReLU→12 tanh→3-way softmax | Forward-return down/neutral/up proxy; no online pseudo-label optimizer or random model |
| 6 Trend | Local-linear state velocity, robust 16/32-bar slopes, positive/negative structure fractions, directional imbalance, returns, range location, sign persistence and empirical scale | 12→12 tanh→4 ReLU→1 sigmoid | Whether measured directional evidence persists over horizon; binary uncalibrated score |
| 7 Volatility | Realized/downside/jump variation, 5% return-tail quantiles, high-state posterior under explicit fixed two-state variance assumptions, empirical range, returns and volume surprise | 12→16 ReLU→8 tanh→3-way softmax | Future realized-volatility regime; not direction and cannot weaken the deterministic Part 7 safety veto |
| 8 Structure | Prior-20/50-bar range escape/failure, clustered support/resistance distance, range location, robust trend, normalized return, empirical range scale and robust volume surprise | 12→22 tanh→7 ReLU→3-way softmax | First future structural break above/below empirical risk scale, else no break |
| 9 Orderflow | Rolling close-location OHLCV proxies (never actual order flow), proxy slope/dispersion, proxy/return divergence, robust returns, volume surprise and range scale | 12→14 tanh→5 ReLU→1 sigmoid | Whether future price movement follows the OHLCV proxy; not exchange tape or order-book delta |
| 10 Candle statistics | Current candle geometry, body acceleration, sign streak/transition rate, directional fraction, empirical range scale, robust returns, peak drawdown and recent volume share | 12→12 ReLU→6 tanh→3-way softmax | Forward candle-direction continuation / indecision / reversal |
| 11 Fusion | Requires all 8 native TFs and all 10 named upstream signals. Features include ten TF-weighted per-Part signals, eight per-frame means, total vote, dispersion, quorum, anchor alignment, dissent and sign entropy | 24→24 ReLU→12 tanh→3-way softmax | Future down/neutral/up direction from the full matrix; result annotates Part 11 but does not replace its deterministic weighted fusion/quorum/veto logic |
| 12 Confidence | Requires the same complete 8×10 matrix. Features include ten per-Part consensus strengths, signed weighted consensus vote, cross-Part dispersion/agreement, quorum, neutral fraction, anchor alignment, high-TF support and Part 7 veto fraction | 18→16 ReLU→6 tanh→1 sigmoid | Whether the normalized time-weighted evidence vote agrees with subsequent resolved direction; score is explicitly **uncalibrated**, not a probability or the existing confidence field |

The wired deterministic analyzer methods for Parts 1–10 now derive evidence directly from validated raw OHLCV statistics in `quantitative_math.py`; Part 2's legacy standalone trend component was also changed to robust log-price statistics. Parts 11–12 retain their existing deterministic multi-frame fusion/confidence responsibilities. The feature schema uses no traditional indicator calculations or renamed equivalents. OHLCV signed-flow/profile data is an explicitly labelled proxy, not order-book/tape truth. Some unused historical helper routines remain elsewhere in the large legacy Part files; they are not called by the Jarvis wired analyzer entrypoints and are inventoried in the implementation report.

## Artifacts and fail-closed behavior

- Runtime reads only bounded JSON (maximum 128 KiB); never `pickle` or `torch.load`, network, training, or model construction.
- Artifact format v3 validates exact part/task/feature/model contract, tensor shapes, finite bounded weights, train-fitted normalization, complete chronological train/validation/test metadata, dataset hash and exact venue/market/instrument/symbol/timeframe identity. Its separate feature schema is now incompatible v4 (`jarvis-task-specific-features-v4-quantitative`).
- Candle Parts require at least 64 contiguous, closed, finite OHLCV observations. Parts 11/12 require exactly the eight named frames and all Parts 1–10 in each frame; partial evidence is unavailable, never guessed.
- Snapshot/candle freshness, future timestamp, training-data overlap, backtest availability time and stale training history are checked. Missing, malformed, old generic-v1, stale or identity-mismatched artifacts return `status=unavailable`; inference is never random.
- CPU is the default and does not import PyTorch. CUDA is opt-in with `JARVIS_NEURAL_DEVICE=cuda` (or legacy `JARVIS_NEURAL_GPU=1`); `JARVIS_NEURAL_REQUIRE_GPU=1` forces fail-closed behavior if CUDA cannot run. `JARVIS_NEURAL_GPU_MIN_FREE_MB` sets a bounded free-memory floor (default 256 MB, clamped to 64–2048 MB). CUDA telemetry reports the requested and actual device, device name, and free/total memory; insufficient/unknown memory or runtime inference failure falls back to CPU unless strict mode is enabled. The runtime retains only one model's CUDA tensors, serializes inference with one bounded slot, limits CPU artifact/prediction caches to 16/256, and does not load all twelve models onto a 4-GB GPU. The separate Part 7 live candle-buffer adapter applies a 25% per-process CUDA allocator cap when CUDA is present; its bounded CPU feature window is at most 128 closed OHLCV bars. This is a configured cap, not a measured device result. The GTX1650/8-GB host was not available for testing; no actual-device benchmark or measured memory claim is made.

## Offline trainer and data contracts

`train_part_advisory.py` is offline-only; it does not launch Jarvis or contact an exchange. Input is one chronological, gap-free, explicitly closed, identity-homogeneous OHLCV CSV with:

`timestamp,open,high,low,close,volume,is_closed,venue,market_type,instrument_id,symbol,timeframe`

For Parts 1–10, the trainer builds only past-looking part-specific features and a distinct target for each task. Future labels are separated into purged chronological 70/15/15 train/validation/test regions; feature scaling uses train only. Parts 11/12 require an additional `evidence_json` column on every 1m-clock row: an envelope with `identity` (`venue`, `market_type`, `instrument_id`, `symbol`), matching `symbol`, `closed_timestamps` keyed by all eight frames, and `frames` mapping each of `1m,3m,5m,15m,30m,1h,2h,4h` to all ten named Part result dictionaries (at minimum finite `signal` values). Each frame timestamp must be closed and not later than the base 1m analysis (within the frame interval). Runtime applies exact identity, complete coverage, timestamp and freshness checks. Evidence must be point-in-time results from an offline replay of the deterministic analyzers, not copied from a future snapshot. Rows still need the matching 1m close for forward target generation.

Examples:

```bash
python train_part_advisory.py ./reviewed_BTCUSD_1m.csv \
  --part part1_breakout --venue delta --market-type futures \
  --instrument-id BTCUSD --symbol BTCUSD --timeframe 1m

python train_part_advisory.py ./replayed_mtf_evidence_1m.csv \
  --part part11_fusion --venue delta --market-type futures \
  --instrument-id BTCUSD --symbol BTCUSD --timeframe 1m
```

Each command trains only one part/identity artifact. CPU, float32 and one thread are defaults; CUDA is opt-in and falls back to CPU on detected OOM. No user data or real trained weights are supplied or checked in. Artifacts are emitted only if both holdouts exceed majority-label accuracy by 2 points, a minimal screening gate—not model authorization. No synthetic test weights/data are production weights. Target metrics do not include fills, fees, funding, slippage, stops, sizing, PnL, strategy calibration or profitability.

## Current state

There are **no trained production models**. Until real reviewed data is supplied, the normal result for all twelve tasks is `unavailable`; deterministic Jarvis remains the complete operative behavior. No live startup, exchange call, order, deployment, merge or performance claim is part of this implementation.


## Quantitative feature schema v4

Part 1–10 feature vectors are computed from validated closed OHLCV using robust return scales, state-space drift, penalized change-point evidence, realized/downside/jump variation, return-sign transition statistics, structural extrema and explicitly labeled volume-distribution/close-location proxies. They are not RSI/EMA/MACD/ADX/ATR/Bollinger/Keltner substitutes under new names. The schema/version bump deliberately invalidates older artifacts. All scores remain advisory and uncalibrated until validated trained artifacts exist.

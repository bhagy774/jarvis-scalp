# Parts 1–12: part-owned neural advisory models

## Scope and safety boundary

This change provides **twelve separate task-specific model contracts**. Each Part has its own feature math, network topology, output head, label/target definition and named advisory output. Parts 1–10 receive their native closed-candle OHLCV frame; Parts 11–12 receive the actual complete eight-timeframe × ten-Part evidence matrix already produced by Jarvis. The shared `neural_advisory.py` is limited to bounded local artifact/identity/freshness validation, the small CPU math kernel, and caches. `neural_parts/part1.py` through `part12.py` each own their feature projection, architecture/head contract, and offline target. Each Part module also interprets its head scores into task-specific `task_output` fields. The shared dispatcher does not select a generic feature vector/topology/label or erase task-specific output semantics.

All model outputs are **diagnostic/shadow advisories only**. Existing Part logic remains in force. No neural result changes deterministic `signal`, Part 11/12 output fields, calibrated confidence, Part 7 veto, central approval, trade mode, symbol/timeframe gates, position/risk/sizing, SL/TP, ownership, reconciliation, close/exit, or order authority. Jarvis remains the sole final new-entry authority. Full eight-TF evidence remains intact and 1m execution timing remains distinct from higher-TF setup evidence.

## Independent model contracts

All heads are trained independently and bound to the part, exact instrument identity and timeframe. Hidden widths/activations and head shape vary by task. Ten candle heads use separate 12-feature projections; fusion uses 24 MTF features; confidence uses 18 MTF features. Inference is stdlib-only CPU arithmetic; it never imports PyTorch or reserves GPU. Artifacts from the prior centralized schemas are rejected under strict schema v3.

| Part | Part-owned feature preparation and maths | Network / head | Offline target and advisory output |
|---|---|---|---|
| 1 Breakout | Multi-window returns, prior-range breaks, range location, log-slope, ATR/realized-vol scaling, wick imbalance and volume z-score | 12→20 ReLU→8 tanh→3-way softmax | First-touch up/down ATR-barrier event; `bear_break / no_break / bull_break` |
| 2 Zone | Range percentile, volume-weighted center distance, high/low proximity, 20-bin volume-node location, slope and range expansion | 12→16 tanh→6 ReLU→3-way softmax | Near-edge support rejection / zone acceptance / resistance rejection; uses position in the past 32-bar zone and forward response |
| 3 Psychology | Body/wick proportions, close location, range/ATR, gap/ATR, engulf/doji proxies, preceding body and volume | 12→10 tanh→4 ReLU→1 sigmoid | Whether a meaningful forward move reverses the current candle-body direction; binary uncalibrated reversal score |
| 4 Volume | Volume z/ratio, signed candle-volume flow, flow/return divergence, volume trend and range/ATR | 12→18 ReLU→8 ReLU→3-way softmax | Forward price direction confirmed by higher future volume, else unconfirmed |
| 5 Statistical ML | Volatility-normalized return drift, regression-slope t-stat proxy, EMA spread, centered RSI, drawdown and volume/volatility context | 12→24 ReLU→12 tanh→3-way softmax | Forward-return down/neutral/up proxy; no pseudo-label online optimizer or untrained random fusion remains |
| 6 Trend | EMA8/21/50 spreads, 16/32-bar log slopes, directional-move imbalance, range location and volatility | 12→12 tanh→4 ReLU→1 sigmoid | Whether the currently measured directional trend persists over horizon; binary uncalibrated score |
| 7 Volatility | 8/32 return dispersion, ATR and ATR ratio, range/ATR, expansion, body and volume context | 12→16 ReLU→8 tanh→3-way softmax | Future realized-volatility regime: contracting / normal / expanding; not a long/short forecast and cannot weaken the deterministic Part 7 safety gate |
| 8 Structure | 20/50-bar swing gaps, prior-range breaks, range position, slope, ATR and volume context | 12→22 tanh→7 ReLU→3-way softmax | First future structural break above/below an ATR-buffered prior range, else no break |
| 9 Orderflow | OHLCV signed-flow proxies over 4/12 bars, CVD slope, flow-price/return divergence and volume/range features | 12→14 tanh→5 ReLU→1 sigmoid | Whether future price movement follows the current signed-flow proxy; not exchange trade-tape delta |
| 10 Candle statistics | Body acceleration, same-color streak, transition rate, green fraction, range/ATR, return, drawdown and volume context | 12→12 ReLU→6 tanh→3-way softmax | Forward candle-direction continuation / indecision / reversal |
| 11 Fusion | Requires all 8 native TFs and all 10 named upstream signals. Features include ten TF-weighted per-Part signals, eight per-frame means, total vote, dispersion, quorum, anchor alignment, dissent and sign entropy | 24→24 ReLU→12 tanh→3-way softmax | Future down/neutral/up direction from the full matrix; result annotates Part 11 but does not replace its deterministic weighted fusion/quorum/veto logic |
| 12 Confidence | Requires the same complete 8×10 matrix. Features include ten per-Part consensus strengths, signed weighted consensus vote, cross-Part dispersion/agreement, quorum, neutral fraction, anchor alignment, high-TF support and Part 7 veto fraction | 18→16 ReLU→6 tanh→1 sigmoid | Whether the normalized time-weighted evidence vote agrees with subsequent resolved direction; score is explicitly **uncalibrated**, not a probability or the existing confidence field |

Parts 2/3/4/8/9/10 keep their existing deterministic domain maths as well as the advisory feature projection. OHLCV signed-flow/profile data is proxy math only, not order-book/tape truth. The existing indicators are enhanced/retained rather than falsely described as removed.

## Artifacts and fail-closed behavior

- Runtime reads only bounded JSON (maximum 128 KiB); never `pickle` or `torch.load`, network, training, or model construction.
- Format v3 validates exact part/task/feature/model contract, tensor shapes, finite bounded weights, train-fitted normalization, complete chronological train/validation/test metadata, dataset hash and exact venue/market/instrument/symbol/timeframe identity.
- Candle Parts require at least 64 contiguous, closed, finite OHLCV observations. Parts 11/12 require exactly the eight named frames and all Parts 1–10 in each frame; partial evidence is unavailable, never guessed.
- Snapshot/candle freshness, future timestamp, training-data overlap, backtest availability time and stale training history are checked. Missing, malformed, old generic-v1, stale or identity-mismatched artifacts return `status=unavailable`; inference is never random.
- At most 16 artifacts and 256 predictions are cached; one inference runs concurrently at a time. The supplied GTX1650/4-GB VRAM is not used or reserved. No performance benchmark of the user's machine is claimed.

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

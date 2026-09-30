# Deterministic crypto market selection

## Scope and data sources

`JarvisCoinScanner` selects a candidate before the existing analysis pipeline runs. It does not import or call Ollama, Gemini, or another model. The live loop passes the scanner's selected symbol through `MarketRouter`, which verifies that exact product is available on Delta before the existing same-symbol candles, analysis, risk gates, paper ledger, and optional execution paths proceed. If selection, data checks, or venue verification fail, the router blocks the cycle; there is no implicit BTC fallback. This only decouples coin selection from Ollama—it does **not** make downstream analysis or the whole bot Ollama-free.

The scanner uses the repository's existing Binance requests, not new endpoints:

- `https://api.binance.com/api/v3/ticker/24hr` — `symbol`, `quoteVolume` (USDT quote volume), `priceChangePercent`, `highPrice`, `lowPrice`, `lastPrice`, `bidPrice`, `askPrice`, and `closeTime` (Unix milliseconds; last trade time).
- `https://api.binance.com/api/v3/klines` with `interval=5m` — candle open time, close price, and close time (Unix milliseconds). The forming candle is excluded.
- `https://fapi.binance.com/fapi/v1/premiumIndex` — existing optional `lastFundingRate`. A lookup failure adds zero funding points; it is not represented as a zero funding rate.

These public Binance inputs are only for ranking; the separate Delta product lookup remains authoritative for whether the resulting contract can be routed. Candidate universe is the existing `SCAN_COINS` list and `XXXUSDT` Binance symbols.

## Eligibility gates and units

A candidate is eligible only when all gates pass:

1. The ticker's reported `symbol` exactly matches the requested Binance symbol.
2. Ticker fields listed above parse as finite numbers; volume is at least `SCANNER_MIN_VOL` (default **5,000,000 USDT of 24h quote volume**). Price fields must be positive and consistent (`low <= last <= high`); bid must be positive and ask must be at least bid.
3. Ticker `closeTime` is no more than `SCANNER_MAX_TICKER_AGE_SEC` old (default **120 seconds**). Up to 30 seconds of future timestamp skew is tolerated.
4. Quoted spread is computed as `(ask - bid) / ((ask + bid) / 2) * 10,000` in **basis points**. It must be no greater than `SCANNER_MAX_SPREAD_BPS` (default **25 bps = 0.25%**).
5. The 5m endpoint must provide at least **15 completed candles**. The selected 15 candles must have exactly 300,000 ms between open times, positive finite closes, and a latest close no older than `SCANNER_MAX_CANDLE_AGE_SEC` (default **600 seconds**). A missing, malformed, discontinuous, insufficient, or stale candle series rejects that coin rather than receiving a synthetic neutral RSI.

Threshold overrides are read from the named environment variables when `jarvis_coin_scanner` is imported. An absent or invalid market input is not filled with a fabricated price, spread, candle, or volume value.

## Deterministic ranking

Eligible candidates retain the scanner's existing score criteria and thresholds:

- 24h USDT quote volume: 0–25 points at the existing `$5M / $10M / $20M / $50M / $100M / $200M / $500M` tiers.
- Absolute 24h percent change: 3–25 points using the existing `<0.5 / 0.5 / 1.5 / 3 / 5 / 8%` tiers.
- RSI from 15 closed 5m closes: 0–20 points using the existing 25/30/35/40/60/65/70/75 boundaries and existing `_calc_rsi` implementation.
- 24h high-low range divided by last price, in percent: 4–20 points using the existing 0.5%, 1%, 5%, and 8% thresholds.
- Existing funding-rate tiers: 0–10 points; unavailable funding data contributes zero points.
- Quoted spread: 1–10 points (10 at <=5 bps; 7 at <=10; 4 at <=15; 1 above 15 through the configured eligibility cap).

Candidates sort by **total score descending**, then **spread in bps ascending**, then **24h quote volume descending**, then **base symbol ascending**. This makes ties independent of input mapping order. The score is a market-selection rank only, not a trade confidence or permission; downstream institutional/risk/analysis gates are unchanged.

## Position and failure behavior

While a paper, auto-trader, or position-manager position is open, the live loop tells `MarketRouter` to retain the active route. The scanner's separate owner callback also refuses to switch when it reports an open position; if that callback errors, it conservatively retains its current route instead of treating the error as proof of flatness. A missing router, scanner exception, empty candidate, or Delta contract mismatch blocks the live cycle. Existing execution protections, position ownership/close coordination, and protective close paths are not changed.

Tests use synthetic in-process fixtures only; no live exchange traffic or order submission is part of the test suite.

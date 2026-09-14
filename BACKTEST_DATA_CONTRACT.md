# JARVIS historical replay data contract

The replay uses only completed local OHLCV candles. At every replay timestamp it rebuilds the 1m–4h views from the candles that closed before that decision. The central JARVIS math/GPU path evaluates all twelve core adapters and the report creates a `*_part_coverage.json` audit record.

## Data covered by an OHLCV file

| Core part | Historical source |
|---|---|
| 1 Breakout, 2 Zone, 3 Psychology, 6 Trend, 7 Volatility, 8 Structure, 10 Candlestats | OHLCV |
| 4 Volume | Candle volume; no institutional feed claim |
| 5 ML | OHLCV-derived features |
| 9 Orderflow | Candle-volume proxy; not tick/order-book flow |
| 11 Fusion | Outputs of Parts 1–10 |
| 12 Confidence | Outputs of Parts 1–11 |

## Data an OHLCV file does not contain

Options chain/OI/PCR, funding, tick/order-book, liquidation, and point-in-time cross-exchange data require separate timestamp-matched historical datasets. In OHLCV-only replay these sources are **excluded from the decision**, including the options-chain vote; current/live data must never be substituted.

This prevents future leakage and makes the report explicit about what was actually tested.

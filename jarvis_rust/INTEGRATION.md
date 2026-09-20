# Optional Rust math integration

`jarvis_rust` is an offline-capable extension. The live trading path does not
route websocket or executor traffic through Rust, and Rust does not bypass
Python data validation, risk gates, sizing, canonical decisions, or order
reconciliation.

The only opt-in integration in this change is the bounded SMA calculation on
`direct_candle_cache.CandleFrame.sma(period)`. It consumes the frame's 500
completed native-interval candles; the separate forming candle is never used.

```sh
# Default: semantically equivalent Python implementation
JARVIS_RUST_MATH=0

# Opt in after installing the wheel in the same Python environment
JARVIS_RUST_MATH=1
```

If the extension is unavailable while the flag is enabled, startup/use logs an
explicit warning and uses the equivalent Python calculation. Missing, stale,
wrong-symbol, malformed, or non-finite candle data remains an error and is not
hidden as an acceleration fallback. WebSocket and `OrderExecutor` classes
remain offline-only library components and are not production-routed by this
flag.

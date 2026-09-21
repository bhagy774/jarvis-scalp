# Optional Rust math integration

`jarvis_rust` is an offline-capable extension. The live trading path does not
route websocket or executor traffic through Rust, and Rust does not bypass
Python data validation, risk gates, sizing, canonical decisions, or order
reconciliation.

The only bounded integration surface in this change is the opt-in SMA helper
`direct_candle_cache.CandleFrame.sma(period)`. It consumes the frame's 500
completed native-interval candles; the separate forming candle is never used.
**The existing Parts/scanner/trading runtime has no production call site for
this helper in this PR.** It is therefore an explicitly callable, offline
integration seam—not evidence that the live Jarvis loop is accelerated or that
Rust is routed into live decisions.

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

## Verification boundary

The offline benchmark used the same 500-close fixture, release wheel, warm-up,
repeated samples, and Python-list conversion. For this small SMA workload,
conversion overhead made the extension slower than the Python reference. No
profiling run identified a live trading bottleneck, and no full-loop speedup
claim is made. Any future runtime adoption requires a separate profiling pass,
call-site correctness comparison, and review of the existing data/risk/order
safety gates.

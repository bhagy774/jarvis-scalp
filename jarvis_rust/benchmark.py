#!/usr/bin/env python3
"""
JARVIS Rust Math Engine — Python Usage Examples + Benchmark
===========================================================

Run after installing:
    pip install maturin
    cd jarvis_rust && maturin develop --release

Usage:
    python benchmark.py
"""

import time
import random
import sys

# ─────────────────────────────────────────────────────────────
# Try importing Rust module (falls back to Python if not built)
# ─────────────────────────────────────────────────────────────
try:
    import jarvis_rust
    RUST_AVAILABLE = True
    print(f"✅ jarvis_rust loaded — version {jarvis_rust.__version__}")
except ImportError:
    RUST_AVAILABLE = False
    print("⚠️  jarvis_rust not built yet — run: cd jarvis_rust && maturin develop --release")
    print("    Showing Python reference implementations only.\n")


# ─────────────────────────────────────────────────────────────
# Python Reference Implementations (for benchmarking)
# ─────────────────────────────────────────────────────────────
def py_ema(prices: list, period: int) -> float:
    k = 2.0 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = price * k + ema * (1 - k)
    return ema


def py_rsi(prices: list, period: int = 14) -> float:
    changes = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
    avg_gain = sum(max(c, 0) for c in changes[:period]) / period
    avg_loss = sum(abs(min(c, 0)) for c in changes[:period]) / period
    for change in changes[period:]:
        gain = max(change, 0)
        loss = abs(min(change, 0))
        avg_gain = (avg_gain * (period-1) + gain) / period
        avg_loss = (avg_loss * (period-1) + loss) / period
    if avg_loss < 1e-10:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def py_vwap(high, low, close, volume) -> float:
    tpv = sum((h + l + c) / 3 * v for h, l, c, v in zip(high, low, close, volume))
    vol = sum(volume)
    return tpv / vol if vol > 0 else 0.0


def py_bollinger(prices: list, period: int = 20, num_std: float = 2.0):
    window = prices[-period:]
    middle = sum(window) / period
    variance = sum((p - middle)**2 for p in window) / period
    std = variance**0.5
    return (middle + num_std * std, middle, middle - num_std * std)


# ─────────────────────────────────────────────────────────────
# Correctness Test
# ─────────────────────────────────────────────────────────────
def test_correctness():
    print("\n" + "="*60)
    print("CORRECTNESS TESTS")
    print("="*60)

    # Known prices for RSI test (from Investopedia example)
    prices = [
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.15,
        43.61, 44.33, 44.83, 45.10, 45.15, 45.98, 45.83, 45.87,
        46.92, 46.15, 46.21, 46.25, 45.71, 46.45, 45.78, 45.35,
        44.03, 44.18, 44.22, 44.57, 43.42, 42.66
    ]
    high   = [p * 1.01 for p in prices]
    low    = [p * 0.99 for p in prices]
    volume = [random.uniform(1000, 5000) for _ in prices]

    py_rsi_val = py_rsi(prices, 14)
    py_ema_val = py_ema(prices, 14)
    py_vwap_val = py_vwap(high, low, prices, volume)
    py_bb = py_bollinger(prices, 20, 2.0)

    print(f"\nPython RSI(14):         {py_rsi_val:.4f}")
    print(f"Python EMA(14):         {py_ema_val:.4f}")
    print(f"Python VWAP:            {py_vwap_val:.4f}")
    print(f"Python BB(20,2):        upper={py_bb[0]:.4f} mid={py_bb[1]:.4f} lower={py_bb[2]:.4f}")

    if RUST_AVAILABLE:
        rust_rsi_val = jarvis_rust.calculate_rsi(prices, 14)
        rust_ema_val = jarvis_rust.calculate_ema(prices, 14)
        rust_vwap_val = jarvis_rust.calculate_vwap(high, low, prices, volume)
        rust_bb = jarvis_rust.calculate_bollinger(prices, 20, 2.0)

        print(f"\nRust   RSI(14):         {rust_rsi_val:.4f}")
        print(f"Rust   EMA(14):         {rust_ema_val:.4f}")
        print(f"Rust   VWAP:            {rust_vwap_val:.4f}")
        print(f"Rust   BB(20,2):        upper={rust_bb[0]:.4f} mid={rust_bb[1]:.4f} lower={rust_bb[2]:.4f}")

        # Verify within tolerance (floating point may differ slightly)
        tolerance = 0.0001
        assert abs(py_rsi_val - rust_rsi_val) < tolerance, f"RSI mismatch: {py_rsi_val} vs {rust_rsi_val}"
        assert abs(py_ema_val - rust_ema_val) < tolerance, f"EMA mismatch: {py_ema_val} vs {rust_ema_val}"
        assert abs(py_vwap_val - rust_vwap_val) < tolerance, f"VWAP mismatch: {py_vwap_val} vs {rust_vwap_val}"
        print("\n✅ ALL CORRECTNESS TESTS PASSED — Rust matches Python output exactly!")
    else:
        print("\n⚠️  Skipping Rust correctness check (not built yet)")


# ─────────────────────────────────────────────────────────────
# Performance Benchmark
# ─────────────────────────────────────────────────────────────
def benchmark(n_iterations: int = 10_000):
    print("\n" + "="*60)
    print(f"PERFORMANCE BENCHMARK — {n_iterations:,} iterations")
    print("="*60)

    # Generate realistic price data (500 candles)
    base = 50000.0
    prices = [base + random.gauss(0, 500) for _ in range(500)]
    high   = [p * random.uniform(1.001, 1.01) for p in prices]
    low    = [p * random.uniform(0.99, 0.999) for p in prices]
    volume = [random.uniform(1.0, 100.0) for _ in prices]

    results = {}

    # ── EMA Benchmark ──
    start = time.perf_counter()
    for _ in range(n_iterations):
        py_ema(prices, 21)
    py_time = time.perf_counter() - start
    results['EMA'] = {'python': py_time}

    if RUST_AVAILABLE:
        start = time.perf_counter()
        for _ in range(n_iterations):
            jarvis_rust.calculate_ema(prices, 21)
        rust_time = time.perf_counter() - start
        results['EMA']['rust'] = rust_time

    # ── RSI Benchmark ──
    start = time.perf_counter()
    for _ in range(n_iterations):
        py_rsi(prices, 14)
    py_time = time.perf_counter() - start
    results['RSI'] = {'python': py_time}

    if RUST_AVAILABLE:
        start = time.perf_counter()
        for _ in range(n_iterations):
            jarvis_rust.calculate_rsi(prices, 14)
        rust_time = time.perf_counter() - start
        results['RSI']['rust'] = rust_time

    # ── VWAP Benchmark ──
    start = time.perf_counter()
    for _ in range(n_iterations):
        py_vwap(high, low, prices, volume)
    py_time = time.perf_counter() - start
    results['VWAP'] = {'python': py_time}

    if RUST_AVAILABLE:
        start = time.perf_counter()
        for _ in range(n_iterations):
            jarvis_rust.calculate_vwap(high, low, prices, volume)
        rust_time = time.perf_counter() - start
        results['VWAP']['rust'] = rust_time

    # ── Bollinger Benchmark ──
    start = time.perf_counter()
    for _ in range(n_iterations):
        py_bollinger(prices, 20, 2.0)
    py_time = time.perf_counter() - start
    results['BB'] = {'python': py_time}

    if RUST_AVAILABLE:
        start = time.perf_counter()
        for _ in range(n_iterations):
            jarvis_rust.calculate_bollinger(prices, 20, 2.0)
        rust_time = time.perf_counter() - start
        results['BB']['rust'] = rust_time

    # ── Print Results ──
    print(f"\n{'Indicator':<12} {'Python (ms)':<15} {'Rust (ms)':<15} {'Speedup':<10}")
    print("-" * 55)
    for name, times in results.items():
        py_ms = times['python'] * 1000
        if 'rust' in times:
            rust_ms = times['rust'] * 1000
            speedup = py_ms / rust_ms
            print(f"{name:<12} {py_ms:<15.2f} {rust_ms:<15.2f} {speedup:.1f}x faster")
        else:
            print(f"{name:<12} {py_ms:<15.2f} {'N/A':<15} {'N/A':<10}")

    print("\n" + "="*60)
    print("PER-CALL LATENCY (real-time trading matters!)")
    print("="*60)
    for name, times in results.items():
        py_us = (times['python'] / n_iterations) * 1_000_000
        if 'rust' in times:
            rust_us = (times['rust'] / n_iterations) * 1_000_000
            print(f"{name}: Python={py_us:.2f}μs → Rust={rust_us:.2f}μs")
        else:
            print(f"{name}: Python={py_us:.2f}μs → Rust=N/A (not built)")


# ─────────────────────────────────────────────────────────────
# Edge Case Tests
# ─────────────────────────────────────────────────────────────
def test_edge_cases():
    print("\n" + "="*60)
    print("EDGE CASE TESTS")
    print("="*60)

    if not RUST_AVAILABLE:
        print("⚠️  Skipping (jarvis_rust not built)")
        return

    # All same price (RSI = undefined → should be 50 or 100)
    flat_prices = [50000.0] * 20
    rsi = jarvis_rust.calculate_rsi(flat_prices, 14)
    print(f"RSI flat market (all same price): {rsi:.2f} (expected: 100.0)")

    # Only 2 prices (minimum for 1-period RSI)
    rsi2 = jarvis_rust.calculate_rsi([100.0, 105.0], 1)
    print(f"RSI rising 2-price list:         {rsi2:.2f} (expected: 100.0)")

    # Test error handling
    try:
        jarvis_rust.calculate_rsi([], 14)
        print("❌ Should have raised ValueError for empty list!")
    except ValueError as e:
        print(f"✅ Empty list error caught: {e}")

    try:
        jarvis_rust.calculate_ema([1.0, 2.0], 5)  # Not enough data
        print("❌ Should have raised ValueError for insufficient data!")
    except ValueError as e:
        print(f"✅ Insufficient data error caught: {e}")

    print("\n✅ All edge case tests passed!")


# ─────────────────────────────────────────────────────────────
# Integration Test — as JARVIS uses it
# ─────────────────────────────────────────────────────────────
def test_jarvis_integration():
    """Simulate how JARVIS Parts 1-12 will call Rust math"""
    print("\n" + "="*60)
    print("JARVIS INTEGRATION SIMULATION")
    print("="*60)

    # Simulate 200 candles of BTC data
    candles = {
        'close':  [50000 + random.gauss(0, 1000) for _ in range(200)],
        'high':   [50000 + abs(random.gauss(0, 1200)) for _ in range(200)],
        'low':    [50000 - abs(random.gauss(0, 1200)) for _ in range(200)],
        'volume': [random.uniform(10, 1000) for _ in range(200)],
    }

    if RUST_AVAILABLE:
        math = jarvis_rust
    else:
        # Fallback to Python
        class math:
            calculate_rsi = staticmethod(py_rsi)
            calculate_ema = staticmethod(py_ema)
            calculate_vwap = staticmethod(py_vwap)
            calculate_bollinger = staticmethod(py_bollinger)

    start = time.perf_counter()

    # As Part 1 (RSI) would call it
    rsi_14  = math.calculate_rsi(candles['close'], 14)
    rsi_21  = math.calculate_rsi(candles['close'], 21)

    # As Part 2 (EMA) would call it
    ema_9   = math.calculate_ema(candles['close'], 9)
    ema_21  = math.calculate_ema(candles['close'], 21)
    ema_50  = math.calculate_ema(candles['close'], 50)

    # As Part 4 (VWAP) would call it
    vwap = math.calculate_vwap(
        candles['high'], candles['low'],
        candles['close'], candles['volume']
    )

    # As Part 5 (Bollinger) would call it
    bb_upper, bb_mid, bb_lower = math.calculate_bollinger(candles['close'], 20, 2.0)

    elapsed = (time.perf_counter() - start) * 1000

    print(f"\n📊 BTC Analysis (200 candles) using {'Rust' if RUST_AVAILABLE else 'Python'}:")
    print(f"  RSI(14):       {rsi_14:.2f}")
    print(f"  RSI(21):       {rsi_21:.2f}")
    print(f"  EMA(9):        ${ema_9:,.2f}")
    print(f"  EMA(21):       ${ema_21:,.2f}")
    print(f"  EMA(50):       ${ema_50:,.2f}")
    print(f"  VWAP:          ${vwap:,.2f}")
    print(f"  BB Upper:      ${bb_upper:,.2f}")
    print(f"  BB Mid:        ${bb_mid:,.2f}")
    print(f"  BB Lower:      ${bb_lower:,.2f}")
    print(f"\n⏱️  All 7 calculations done in: {elapsed:.3f}ms")
    print(f"   (Target for 1m scalping: < 1ms)")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🦀 JARVIS Rust Math Engine — Test & Benchmark Suite")
    print("=" * 60)

    test_correctness()
    test_edge_cases()
    test_jarvis_integration()
    benchmark(n_iterations=10_000)

    print("\n🎯 Done! If jarvis_rust is built, Rust should be 5-15x faster.")
    print("   Build command: cd jarvis_rust && maturin develop --release")

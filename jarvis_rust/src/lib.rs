#![allow(clippy::useless_conversion)]

/// JARVIS Rust — Main Library Entry Point
///
/// Registers all 4 modules as Python-importable:
///
///   from jarvis_rust import (
///       # Module 1: Math
///       calculate_ema, calculate_rsi, calculate_vwap,
///       calculate_bollinger, calculate_sma, calculate_macd, calculate_atr,
///       # Module 2: Cache
///       CandleCache,
///       # Module 3: WebSocket
///       WebSocketFeed,
///       # Module 4: Order Executor
///       OrderExecutor,
///   )
use pyo3::prelude::*;

pub mod cache;
pub mod executor;
pub mod math;
pub mod ws;

/// JARVIS HFT Rust Speed Layer — all 4 modules in one wheel.
#[pymodule]
fn jarvis_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // ── Module 1: Math Engine ──────────────────────────────
    m.add_function(wrap_pyfunction!(math::calculate_ema, m)?)?;
    m.add_function(wrap_pyfunction!(math::calculate_rsi, m)?)?;
    m.add_function(wrap_pyfunction!(math::calculate_vwap, m)?)?;
    m.add_function(wrap_pyfunction!(math::calculate_bollinger, m)?)?;
    m.add_function(wrap_pyfunction!(math::calculate_sma, m)?)?;
    m.add_function(wrap_pyfunction!(math::calculate_macd, m)?)?;
    m.add_function(wrap_pyfunction!(math::calculate_atr, m)?)?;

    // ── Module 2: Candle Cache ─────────────────────────────
    m.add_class::<cache::CandleCache>()?;

    // ── Module 3: WebSocket Feed ───────────────────────────
    m.add_class::<ws::WebSocketFeed>()?;

    // ── Module 4: Order Executor ───────────────────────────
    m.add_class::<executor::OrderExecutor>()?;

    // Version metadata
    m.add("__version__", "0.2.0")?;
    m.add(
        "__description__",
        "JARVIS HFT Rust Speed Layer — math + cache + websocket + executor",
    )?;

    Ok(())
}

/// JARVIS Rust — Main Library Entry Point
///
/// Registers all 4 modules as Python-importable submodules:
///   import jarvis_rust
///   jarvis_rust.calculate_rsi(...)
///   jarvis_rust.calculate_ema(...)

use pyo3::prelude::*;

// Declare sub-modules
pub mod math;

/// JARVIS Rust Speed Layer
///
/// Replaces Python/NumPy bottlenecks with Rust implementations.
/// All functions are accessible directly from Python after installation:
///
///   from jarvis_rust import (
///       calculate_ema, calculate_rsi, calculate_vwap,
///       calculate_bollinger, calculate_sma, calculate_macd, calculate_atr
///   )
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

    // Version metadata accessible from Python
    m.add("__version__", "0.1.0")?;
    m.add("__description__", "JARVIS HFT Rust Speed Layer — math engine (Module 1)")?;

    Ok(())
}

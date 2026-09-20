/// JARVIS HFT Math Engine — Production-ready Rust implementation
/// RSI, EMA, VWAP, Bollinger Bands with full error handling
///
/// All functions are callable from Python:
///   from jarvis_rust import calculate_rsi, calculate_ema, calculate_vwap, calculate_bollinger
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

// ─────────────────────────────────────────────────────────
// INTERNAL HELPERS
// ─────────────────────────────────────────────────────────

/// Validate that input slice is non-empty and has enough data for the period
#[inline(always)]
fn validate_input(prices: &[f64], period: usize, fn_name: &str) -> PyResult<()> {
    if prices.is_empty() {
        return Err(PyValueError::new_err(format!(
            "{}: prices list cannot be empty",
            fn_name
        )));
    }
    if period == 0 {
        return Err(PyValueError::new_err(format!(
            "{}: period must be > 0",
            fn_name
        )));
    }
    if prices.len() < period {
        return Err(PyValueError::new_err(format!(
            "{}: need at least {} prices, got {}",
            fn_name,
            period,
            prices.len()
        )));
    }
    if prices.iter().any(|value| !value.is_finite()) {
        return Err(PyValueError::new_err(format!(
            "{}: prices must contain only finite values",
            fn_name
        )));
    }
    Ok(())
}

// ─────────────────────────────────────────────────────────
// EMA — Exponential Moving Average
// ─────────────────────────────────────────────────────────

/// Calculate EMA (Exponential Moving Average)
///
/// Args:
///   prices: list of closing prices (newest last)
///   period: EMA period (e.g. 9, 21, 50, 200)
///
/// Returns: EMA value as float
///
/// Formula: EMA = price * k + previous_ema * (1 - k)
///          where k = 2 / (period + 1)
#[pyfunction]
pub fn calculate_ema(prices: Vec<f64>, period: usize) -> PyResult<f64> {
    validate_input(&prices, period, "calculate_ema")?;

    // Smoothing factor
    let k = 2.0 / (period as f64 + 1.0);

    // Seed EMA with simple average of first `period` prices
    let seed: f64 = prices[..period].iter().sum::<f64>() / period as f64;
    if !seed.is_finite() {
        return Err(PyValueError::new_err("calculate_ema: result is not finite"));
    }

    // Apply EMA formula over remaining prices
    let ema = prices[period..]
        .iter()
        .fold(seed, |prev_ema, &price| price * k + prev_ema * (1.0 - k));

    if !ema.is_finite() {
        return Err(PyValueError::new_err("calculate_ema: result is not finite"));
    }
    Ok(ema)
}

// ─────────────────────────────────────────────────────────
// RSI — Relative Strength Index
// ─────────────────────────────────────────────────────────

/// Calculate RSI (Relative Strength Index) — Wilder's Smoothed Method
///
/// Args:
///   prices: list of closing prices (oldest first, newest last)
///   period: RSI period (default 14)
///
/// Returns: RSI value 0.0 to 100.0
///
/// Uses Wilder's smoothing (not simple EMA) — matches TradingView exactly.
#[pyfunction]
pub fn calculate_rsi(prices: Vec<f64>, period: usize) -> PyResult<f64> {
    if period == 0 {
        return Err(PyValueError::new_err("calculate_rsi: period must be > 0"));
    }
    let required_prices = period
        .checked_add(1)
        .ok_or_else(|| PyValueError::new_err("calculate_rsi: period is too large"))?;
    validate_input(&prices, required_prices, "calculate_rsi")?;

    // Compute price changes
    let changes: Vec<f64> = prices.windows(2).map(|w| w[1] - w[0]).collect();

    if changes.len() < period {
        return Err(PyValueError::new_err(format!(
            "calculate_rsi: need at least {} price changes, got {}",
            period,
            changes.len()
        )));
    }

    // Initial average gain/loss over first `period` changes
    let mut avg_gain = 0.0_f64;
    let mut avg_loss = 0.0_f64;

    for &change in &changes[..period] {
        if change > 0.0 {
            avg_gain += change;
        } else {
            avg_loss += change.abs();
        }
    }
    avg_gain /= period as f64;
    avg_loss /= period as f64;

    // Wilder's smoothing for remaining periods
    for &change in &changes[period..] {
        let gain = if change > 0.0 { change } else { 0.0 };
        let loss = if change < 0.0 { change.abs() } else { 0.0 };
        avg_gain = (avg_gain * (period as f64 - 1.0) + gain) / period as f64;
        avg_loss = (avg_loss * (period as f64 - 1.0) + loss) / period as f64;
    }

    // RSI calculation (handle avg_loss = 0 → RSI = 100)
    if avg_loss < f64::EPSILON {
        return Ok(100.0);
    }

    let rs = avg_gain / avg_loss;
    Ok(100.0 - (100.0 / (1.0 + rs)))
}

// ─────────────────────────────────────────────────────────
// VWAP — Volume Weighted Average Price
// ─────────────────────────────────────────────────────────

/// Calculate VWAP (Volume Weighted Average Price)
///
/// Args:
///   high:   list of high prices
///   low:    list of low prices
///   close:  list of close prices
///   volume: list of volumes
///
/// Returns: VWAP value as float
///
/// Formula: VWAP = Σ(typical_price × volume) / Σ(volume)
///          where typical_price = (high + low + close) / 3
#[pyfunction]
pub fn calculate_vwap(
    high: Vec<f64>,
    low: Vec<f64>,
    close: Vec<f64>,
    volume: Vec<f64>,
) -> PyResult<f64> {
    if high.is_empty() || low.is_empty() || close.is_empty() || volume.is_empty() {
        return Err(PyValueError::new_err(
            "calculate_vwap: all price/volume lists must be non-empty",
        ));
    }

    let len = high.len();
    if low.len() != len || close.len() != len || volume.len() != len {
        return Err(PyValueError::new_err(
            "calculate_vwap: high, low, close, volume must all have the same length",
        ));
    }
    if high
        .iter()
        .chain(low.iter())
        .chain(close.iter())
        .chain(volume.iter())
        .any(|value| !value.is_finite())
    {
        return Err(PyValueError::new_err(
            "calculate_vwap: all values must be finite",
        ));
    }
    if volume.iter().any(|value| *value < 0.0) {
        return Err(PyValueError::new_err(
            "calculate_vwap: volume cannot be negative",
        ));
    }

    let mut cumulative_tpv = 0.0_f64; // Σ(typical_price × volume)
    let mut cumulative_vol = 0.0_f64; // Σ(volume)

    for i in 0..len {
        let typical_price = (high[i] + low[i] + close[i]) / 3.0;
        cumulative_tpv += typical_price * volume[i];
        cumulative_vol += volume[i];
    }

    if cumulative_vol < f64::EPSILON {
        return Err(PyValueError::new_err(
            "calculate_vwap: total volume is zero — cannot compute VWAP",
        ));
    }

    let vwap = cumulative_tpv / cumulative_vol;
    if !vwap.is_finite() {
        return Err(PyValueError::new_err(
            "calculate_vwap: result is not finite",
        ));
    }
    Ok(vwap)
}

// ─────────────────────────────────────────────────────────
// BOLLINGER BANDS
// ─────────────────────────────────────────────────────────

/// Calculate Bollinger Bands (upper, middle, lower)
///
/// Args:
///   prices:     list of closing prices (oldest first)
///   period:     SMA period (default 20)
///   num_std:    number of standard deviations (default 2.0)
///
/// Returns: tuple (upper_band, middle_band, lower_band) as (f64, f64, f64)
///
/// Formula:
///   middle = SMA(prices, period)
///   std    = population std dev of last `period` prices
///   upper  = middle + num_std × std
///   lower  = middle - num_std × std
#[pyfunction]
pub fn calculate_bollinger(
    prices: Vec<f64>,
    period: usize,
    num_std: f64,
) -> PyResult<(f64, f64, f64)> {
    validate_input(&prices, period, "calculate_bollinger")?;

    if !num_std.is_finite() || num_std <= 0.0 {
        return Err(PyValueError::new_err(
            "calculate_bollinger: num_std must be > 0.0 (typically 2.0)",
        ));
    }

    // Use last `period` prices for calculation
    let window = &prices[prices.len() - period..];

    // Middle band = Simple Moving Average
    let middle = window.iter().sum::<f64>() / period as f64;

    // Population standard deviation
    let variance = window.iter().map(|&p| (p - middle).powi(2)).sum::<f64>() / period as f64;
    let std_dev = variance.sqrt();

    let upper = middle + num_std * std_dev;
    let lower = middle - num_std * std_dev;
    if !upper.is_finite() || !middle.is_finite() || !lower.is_finite() {
        return Err(PyValueError::new_err(
            "calculate_bollinger: result is not finite",
        ));
    }

    Ok((upper, middle, lower))
}

// ─────────────────────────────────────────────────────────
// ADDITIONAL: SMA (Simple Moving Average)
// ─────────────────────────────────────────────────────────

/// Calculate SMA (Simple Moving Average)
///
/// Args:
///   prices: list of closing prices
///   period: SMA period
///
/// Returns: SMA value as float
#[pyfunction]
pub fn calculate_sma(prices: Vec<f64>, period: usize) -> PyResult<f64> {
    validate_input(&prices, period, "calculate_sma")?;
    let window = &prices[prices.len() - period..];
    let sma = window.iter().sum::<f64>() / period as f64;
    if !sma.is_finite() {
        return Err(PyValueError::new_err("calculate_sma: result is not finite"));
    }
    Ok(sma)
}

// ─────────────────────────────────────────────────────────
// ADDITIONAL: MACD
// ─────────────────────────────────────────────────────────

/// Calculate MACD (Moving Average Convergence Divergence)
///
/// Args:
///   prices:       list of closing prices
///   fast_period:  fast EMA period (default 12)
///   slow_period:  slow EMA period (default 26)
///   signal_period: signal line EMA period (default 9)
///
/// Returns: tuple (macd_line, signal_line, histogram) as (f64, f64, f64)
#[pyfunction]
pub fn calculate_macd(
    prices: Vec<f64>,
    fast_period: usize,
    slow_period: usize,
    signal_period: usize,
) -> PyResult<(f64, f64, f64)> {
    if fast_period == 0 || slow_period == 0 || signal_period == 0 {
        return Err(PyValueError::new_err("calculate_macd: periods must be > 0"));
    }
    if fast_period > slow_period {
        return Err(PyValueError::new_err(
            "calculate_macd: fast_period must be <= slow_period",
        ));
    }
    let required_prices = slow_period
        .checked_add(signal_period)
        .ok_or_else(|| PyValueError::new_err("calculate_macd: periods are too large"))?;
    validate_input(&prices, required_prices, "calculate_macd")?;

    // We need to compute MACD line for enough bars to get a signal line
    // Calculate EMA arrays for MACD line history
    let fast_k = 2.0 / (fast_period as f64 + 1.0);
    let slow_k = 2.0 / (slow_period as f64 + 1.0);

    // Seed fast EMA
    let mut fast_ema = prices[..fast_period].iter().sum::<f64>() / fast_period as f64;
    // Seed slow EMA
    let mut slow_ema = prices[..slow_period].iter().sum::<f64>() / slow_period as f64;

    // Build MACD line values from slow_period onwards
    let mut macd_values: Vec<f64> = Vec::with_capacity(prices.len() - slow_period);

    for &price in &prices[fast_period..slow_period] {
        fast_ema = price * fast_k + fast_ema * (1.0 - fast_k);
    }

    for &price in &prices[slow_period..] {
        fast_ema = price * fast_k + fast_ema * (1.0 - fast_k);
        slow_ema = price * slow_k + slow_ema * (1.0 - slow_k);
        macd_values.push(fast_ema - slow_ema);
    }

    if macd_values.len() < signal_period {
        return Err(PyValueError::new_err(
            "calculate_macd: not enough data for signal line",
        ));
    }

    // Signal line = EMA of MACD values
    let sig_k = 2.0 / (signal_period as f64 + 1.0);
    let mut signal = macd_values[..signal_period].iter().sum::<f64>() / signal_period as f64;
    for &m in &macd_values[signal_period..] {
        signal = m * sig_k + signal * (1.0 - sig_k);
    }

    let macd_line = *macd_values.last().unwrap();
    let histogram = macd_line - signal;

    Ok((macd_line, signal, histogram))
}

// ─────────────────────────────────────────────────────────
// ADDITIONAL: ATR (Average True Range)
// ─────────────────────────────────────────────────────────

/// Calculate ATR (Average True Range) — Wilder's method
///
/// Args:
///   high:   list of high prices
///   low:    list of low prices
///   close:  list of close prices (prev close for true range)
///   period: ATR period (default 14)
///
/// Returns: ATR value as float
#[pyfunction]
pub fn calculate_atr(
    high: Vec<f64>,
    low: Vec<f64>,
    close: Vec<f64>,
    period: usize,
) -> PyResult<f64> {
    if period == 0 {
        return Err(PyValueError::new_err("calculate_atr: period must be > 0"));
    }
    let required_bars = period
        .checked_add(1)
        .ok_or_else(|| PyValueError::new_err("calculate_atr: period is too large"))?;
    let len = high.len();
    if low.len() != len || close.len() != len {
        return Err(PyValueError::new_err(
            "calculate_atr: high, low, close must all have the same length",
        ));
    }
    if len < required_bars {
        return Err(PyValueError::new_err(format!(
            "calculate_atr: need at least {} bars, got {}",
            required_bars, len
        )));
    }
    if high
        .iter()
        .chain(low.iter())
        .chain(close.iter())
        .any(|value| !value.is_finite())
    {
        return Err(PyValueError::new_err(
            "calculate_atr: all values must be finite",
        ));
    }
    if high.iter().zip(low.iter()).any(|(high, low)| high < low) {
        return Err(PyValueError::new_err("calculate_atr: high must be >= low"));
    }

    // True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    let tr_values: Vec<f64> = (1..len)
        .map(|i| {
            let hl = high[i] - low[i];
            let hpc = (high[i] - close[i - 1]).abs();
            let lpc = (low[i] - close[i - 1]).abs();
            hl.max(hpc).max(lpc)
        })
        .collect();

    if tr_values.len() < period {
        return Err(PyValueError::new_err(
            "calculate_atr: not enough true range values",
        ));
    }

    // Wilder's initial ATR = simple average of first `period` TR values
    let mut atr = tr_values[..period].iter().sum::<f64>() / period as f64;

    // Wilder's smoothing: ATR = (prev_ATR × (period-1) + TR) / period
    for &tr in &tr_values[period..] {
        atr = (atr * (period as f64 - 1.0) + tr) / period as f64;
    }

    if !atr.is_finite() {
        return Err(PyValueError::new_err("calculate_atr: result is not finite"));
    }
    Ok(atr)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(actual: f64, expected: f64) {
        let tolerance = 1e-10_f64.max(expected.abs() * 1e-10);
        assert!(
            (actual - expected).abs() <= tolerance,
            "{actual} != {expected}"
        );
    }

    #[test]
    fn sma_ema_and_bollinger_match_reference() {
        let prices = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        approx(calculate_sma(prices.clone(), 3).unwrap(), 4.0);
        approx(calculate_ema(prices.clone(), 3).unwrap(), 4.0);
        let (upper, middle, lower) = calculate_bollinger(prices, 3, 2.0).unwrap();
        approx(middle, 4.0);
        approx(upper, 4.0 + 2.0 * (2.0_f64 / 3.0).sqrt());
        approx(lower, 4.0 - 2.0 * (2.0_f64 / 3.0).sqrt());
    }

    #[test]
    fn rsi_vwap_and_atr_match_independent_fixtures() {
        let rsi = calculate_rsi(vec![1.0, 2.0, 3.0, 2.0, 2.0], 2).unwrap();
        approx(rsi, 50.0);
        let vwap = calculate_vwap(
            vec![11.0, 12.0],
            vec![9.0, 10.0],
            vec![10.0, 11.0],
            vec![2.0, 1.0],
        )
        .unwrap();
        approx(vwap, ((10.0 * 2.0) + (11.0 * 1.0)) / 3.0);
        let atr = calculate_atr(
            vec![11.0, 13.0, 14.0],
            vec![9.0, 10.0, 12.0],
            vec![10.0, 12.0, 13.0],
            2,
        )
        .unwrap();
        approx(atr, (3.0 + 2.0) / 2.0);
    }

    #[test]
    fn macd_fixture_and_constant_prices_are_stable() {
        let prices: Vec<f64> = (1..=40).map(|value| value as f64).collect();
        let (line, signal, histogram) = calculate_macd(prices, 3, 5, 2).unwrap();
        approx(histogram, line - signal);
        assert_eq!(calculate_rsi(vec![5.0; 15], 14).unwrap(), 100.0);
        assert_eq!(calculate_sma(vec![5.0; 3], 3).unwrap(), 5.0);
    }

    #[test]
    fn invalid_and_non_finite_inputs_are_controlled_errors() {
        assert!(calculate_sma(vec![], 1).is_err());
        assert!(calculate_sma(vec![1.0], 0).is_err());
        assert!(calculate_rsi(vec![1.0, 2.0], 0).is_err());
        assert!(calculate_sma(vec![1.0, f64::NAN], 2).is_err());
        assert!(calculate_ema(vec![1.0, f64::INFINITY], 2).is_err());
        assert!(calculate_bollinger(vec![1.0, 2.0], 2, f64::NAN).is_err());
        assert!(calculate_vwap(vec![1.0], vec![1.0], vec![1.0], vec![-1.0]).is_err());
        assert!(calculate_atr(vec![1.0], vec![0.0], vec![0.5], 0).is_err());
        assert!(calculate_macd(vec![1.0; 10], 0, 2, 2).is_err());
        assert!(calculate_macd(vec![1.0; 10], 3, 2, 2).is_err());
    }
}

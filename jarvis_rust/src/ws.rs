/// JARVIS Module 3 — High-Performance WebSocket Feed
///
/// Replaces Python websockets library with async Rust (tokio + tungstenite).
/// Pushes real-time ticks to a Python callback — zero-copy where possible.
///
/// Python usage:
///   from jarvis_rust import WebSocketFeed
///   def on_tick(symbol, price, volume, ts):
///       print(f"{symbol}: ${price}")
///   feed = WebSocketFeed()
///   feed.connect_delta("BTCUSDT", on_tick)  # non-blocking
///   feed.stop()

use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use std::thread;
use tokio::runtime::Runtime;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use futures_util::StreamExt;
use serde_json::Value;

// ─────────────────────────────────────────────────────────
// Known WebSocket endpoints
// ─────────────────────────────────────────────────────────
const DELTA_WS_URL:   &str = "wss://socket.delta.exchange";
const BINANCE_WS_BASE: &str = "wss://stream.binance.com:9443/ws";

/// Message parsed from exchange WebSocket
#[derive(Debug, Clone)]
struct Tick {
    pub symbol: String,
    pub price:  f64,
    pub volume: f64,
    pub ts_ms:  u64,
    pub side:   String, // "buy" / "sell" / "unknown"
}

/// Parse Delta Exchange trade feed message
fn parse_delta_tick(text: &str) -> Option<Tick> {
    let v: Value = serde_json::from_str(text).ok()?;
    // Delta trade message format: {"type":"all_trades","symbol":"BTCUSDT","price":"...","size":...}
    if v["type"].as_str()? != "all_trades" {
        return None;
    }
    Some(Tick {
        symbol: v["symbol"].as_str().unwrap_or("UNKNOWN").to_string(),
        price:  v["price"].as_str()
                    .and_then(|s| s.parse::<f64>().ok())
                    .or_else(|| v["price"].as_f64())
                    .unwrap_or(0.0),
        volume: v["size"].as_f64().unwrap_or(0.0),
        ts_ms:  v["timestamp"].as_u64().unwrap_or(0),
        side:   v["buyer_role"].as_str()
                    .map(|r| if r == "taker" { "buy" } else { "sell" })
                    .unwrap_or("unknown")
                    .to_string(),
    })
}

/// Parse Binance trade stream message
fn parse_binance_tick(text: &str) -> Option<Tick> {
    let v: Value = serde_json::from_str(text).ok()?;
    // Binance trade stream: {"e":"trade","s":"BTCUSDT","p":"...","q":"...","T":...,"m":false}
    if v["e"].as_str()? != "trade" {
        return None;
    }
    Some(Tick {
        symbol: v["s"].as_str().unwrap_or("UNKNOWN").to_string(),
        price:  v["p"].as_str()
                    .and_then(|s| s.parse::<f64>().ok())
                    .unwrap_or(0.0),
        volume: v["q"].as_str()
                    .and_then(|s| s.parse::<f64>().ok())
                    .unwrap_or(0.0),
        ts_ms:  v["T"].as_u64().unwrap_or(0),
        side:   if v["m"].as_bool().unwrap_or(false) { "sell" } else { "buy" }.to_string(),
    })
}

/// High-performance WebSocket feed for Delta Exchange and Binance.
///
/// Runs in a background thread. Calls a Python callback for every tick.
#[pyclass]
pub struct WebSocketFeed {
    running: Arc<AtomicBool>,
    handle:  Option<thread::JoinHandle<()>>,
}

#[pymethods]
impl WebSocketFeed {
    #[new]
    pub fn new() -> Self {
        WebSocketFeed {
            running: Arc::new(AtomicBool::new(false)),
            handle:  None,
        }
    }

    /// Connect to Delta Exchange WebSocket for a symbol's trade feed.
    ///
    /// Args:
    ///   symbol:      e.g. "BTCUSDT"
    ///   callback:    Python callable(symbol, price, volume, ts_ms, side)
    ///   reconnect:   auto-reconnect on disconnect (default True)
    #[pyo3(signature = (symbol, callback, reconnect=true))]
    pub fn connect_delta(
        &mut self,
        py: Python<'_>,
        symbol: String,
        callback: PyObject,
        reconnect: bool,
    ) -> PyResult<()> {
        if self.running.load(Ordering::SeqCst) {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "WebSocketFeed already running — call stop() first",
            ));
        }

        self.running.store(true, Ordering::SeqCst);
        let running = Arc::clone(&self.running);

        // Subscribe message for Delta Exchange
        let subscribe_msg = serde_json::json!({
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": "all_trades",
                        "symbols": [symbol]
                    }
                ]
            }
        }).to_string();

        let url = DELTA_WS_URL.to_string();

        // Spawn background thread (tokio runtime inside)
        let handle = thread::spawn(move || {
            let rt = Runtime::new().expect("tokio runtime");
            rt.block_on(async move {
                loop {
                    if !running.load(Ordering::SeqCst) {
                        break;
                    }

                    let conn = connect_async(&url).await;
                    match conn {
                        Err(e) => {
                            eprintln!("[JARVIS WS] Delta connection error: {e}");
                            if !reconnect { break; }
                            tokio::time::sleep(tokio::time::Duration::from_secs(3)).await;
                            continue;
                        }
                        Ok((mut ws_stream, _)) => {
                            // Send subscribe message
                            let _ = ws_stream.send(Message::Text(subscribe_msg.clone().into())).await;

                            // Process incoming messages
                            while let Some(msg) = ws_stream.next().await {
                                if !running.load(Ordering::SeqCst) {
                                    break;
                                }
                                match msg {
                                    Ok(Message::Text(text)) => {
                                        if let Some(tick) = parse_delta_tick(&text) {
                                            // Call Python callback
                                            Python::with_gil(|py| {
                                                let _ = callback.call1(py, (
                                                    tick.symbol,
                                                    tick.price,
                                                    tick.volume,
                                                    tick.ts_ms,
                                                    tick.side,
                                                ));
                                            });
                                        }
                                    }
                                    Ok(Message::Ping(data)) => {
                                        let _ = ws_stream.send(Message::Pong(data)).await;
                                    }
                                    Ok(Message::Close(_)) => {
                                        eprintln!("[JARVIS WS] Delta closed connection");
                                        break;
                                    }
                                    Err(e) => {
                                        eprintln!("[JARVIS WS] Delta error: {e}");
                                        break;
                                    }
                                    _ => {}
                                }
                            }
                        }
                    }

                    if !reconnect || !running.load(Ordering::SeqCst) {
                        break;
                    }
                    eprintln!("[JARVIS WS] Reconnecting Delta in 3s...");
                    tokio::time::sleep(tokio::time::Duration::from_secs(3)).await;
                }
            });
        });

        self.handle = Some(handle);
        Ok(())
    }

    /// Connect to Binance WebSocket trade stream for a symbol.
    ///
    /// Args:
    ///   symbol:   e.g. "BTCUSDT" (will be lowercased automatically)
    ///   callback: Python callable(symbol, price, volume, ts_ms, side)
    #[pyo3(signature = (symbol, callback, reconnect=true))]
    pub fn connect_binance(
        &mut self,
        _py: Python<'_>,
        symbol: String,
        callback: PyObject,
        reconnect: bool,
    ) -> PyResult<()> {
        if self.running.load(Ordering::SeqCst) {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "WebSocketFeed already running — call stop() first",
            ));
        }

        self.running.store(true, Ordering::SeqCst);
        let running = Arc::clone(&self.running);

        let url = format!("{}/{}@trade", BINANCE_WS_BASE, symbol.to_lowercase());

        let handle = thread::spawn(move || {
            let rt = Runtime::new().expect("tokio runtime");
            rt.block_on(async move {
                loop {
                    if !running.load(Ordering::SeqCst) { break; }

                    let conn = connect_async(&url).await;
                    match conn {
                        Err(e) => {
                            eprintln!("[JARVIS WS] Binance connection error: {e}");
                            if !reconnect { break; }
                            tokio::time::sleep(tokio::time::Duration::from_secs(3)).await;
                            continue;
                        }
                        Ok((mut ws_stream, _)) => {
                            while let Some(msg) = ws_stream.next().await {
                                if !running.load(Ordering::SeqCst) { break; }
                                match msg {
                                    Ok(Message::Text(text)) => {
                                        if let Some(tick) = parse_binance_tick(&text) {
                                            Python::with_gil(|py| {
                                                let _ = callback.call1(py, (
                                                    tick.symbol,
                                                    tick.price,
                                                    tick.volume,
                                                    tick.ts_ms,
                                                    tick.side,
                                                ));
                                            });
                                        }
                                    }
                                    Ok(Message::Ping(data)) => {
                                        let _ = ws_stream.send(Message::Pong(data)).await;
                                    }
                                    Ok(Message::Close(_)) | Err(_) => break,
                                    _ => {}
                                }
                            }
                        }
                    }

                    if !reconnect || !running.load(Ordering::SeqCst) { break; }
                    tokio::time::sleep(tokio::time::Duration::from_secs(3)).await;
                }
            });
        });

        self.handle = Some(handle);
        Ok(())
    }

    /// Check if the feed is currently running.
    pub fn is_running(&self) -> bool {
        self.running.load(Ordering::SeqCst)
    }

    /// Stop the WebSocket feed gracefully.
    pub fn stop(&mut self) {
        self.running.store(false, Ordering::SeqCst);
        if let Some(handle) = self.handle.take() {
            let _ = handle.join();
        }
    }

    fn __repr__(&self) -> String {
        format!("WebSocketFeed(running={})", self.is_running())
    }
}

impl Drop for WebSocketFeed {
    fn drop(&mut self) {
        self.stop();
    }
}

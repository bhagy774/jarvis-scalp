/// JARVIS Module 4 — Sub-Millisecond Order Executor
///
/// Replaces Python requests + delta_api_wrapper.py HTTP calls with
/// async Rust reqwest — sub-millisecond order placement.
///
/// Python usage:
///   from jarvis_rust import OrderExecutor
///   executor = OrderExecutor(api_key="...", api_secret="...")
///   result = executor.place_order("BTCUSDT", "buy", 1, 50000.0, "limit")
///   print(result)  # {"order_id": "...", "status": "open", ...}
use hmac::{Hmac, Mac};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use reqwest::header::{HeaderMap, HeaderValue, CONTENT_TYPE};
use serde_json::{json, Value};
use sha2::Sha256;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::runtime::Runtime;

type HmacSha256 = Hmac<Sha256>;

// Delta Exchange API base URL
const DELTA_API_BASE: &str = "https://api.india.delta.exchange";

// ─────────────────────────────────────────────────────────
// HMAC-SHA256 signing (matches Delta Exchange signature spec)
// ─────────────────────────────────────────────────────────

fn sign_request(secret: &str, method: &str, path: &str, timestamp: u64, body: &str) -> String {
    // Delta signature: HMAC-SHA256(secret, method + timestamp + path + body)
    let message = format!("{}{}{}{}", method, timestamp, path, body);
    let mut mac = HmacSha256::new_from_slice(secret.as_bytes()).expect("HMAC accepts any key size");
    mac.update(message.as_bytes());
    hex::encode(mac.finalize().into_bytes())
}

fn now_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

/// Result of an order placement
#[derive(Debug)]
pub struct OrderResult {
    pub order_id: String,
    pub status: String,
    pub symbol: String,
    pub side: String,
    pub size: f64,
    pub price: f64,
    pub error: Option<String>,
}

/// Sub-millisecond async order executor for Delta Exchange India.
///
/// Uses reqwest (Rust's async HTTP client) + HMAC-SHA256 authentication.
/// All orders are placed asynchronously in a dedicated Tokio runtime.
#[pyclass]
pub struct OrderExecutor {
    api_key: String,
    api_secret: String,
    client: reqwest::Client,
    runtime: Runtime,
    dry_run: bool,
}

#[pymethods]
impl OrderExecutor {
    /// Create a new executor.
    ///
    /// Args:
    ///   api_key:    Delta Exchange API key
    ///   api_secret: Delta Exchange API secret
    ///   dry_run:    If True, simulate orders without sending (default False)
    #[new]
    #[pyo3(signature = (api_key, api_secret, dry_run=false))]
    pub fn new(api_key: String, api_secret: String, dry_run: bool) -> PyResult<Self> {
        if api_key.trim().is_empty() || api_secret.trim().is_empty() {
            return Err(PyValueError::new_err(
                "api_key and api_secret must be non-empty",
            ));
        }
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_millis(5000))
            .danger_accept_invalid_certs(false)
            .build()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to build HTTP client: {e}")))?;

        let runtime = Runtime::new()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to create tokio runtime: {e}")))?;

        Ok(OrderExecutor {
            api_key,
            api_secret,
            client,
            runtime,
            dry_run,
        })
    }

    /// Place an order on Delta Exchange.
    ///
    /// Args:
    ///   symbol:       e.g. "BTCUSDT"
    ///   side:         "buy" or "sell"
    ///   size:         number of contracts (int)
    ///   price:        limit price (0.0 for market order)
    ///   order_type:   "limit" or "market" (default "limit")
    ///   reduce_only:  only close existing position (default False)
    ///   post_only:    maker-only order (default False)
    ///
    /// Returns: dict with order_id, status, symbol, side, size, price, error
    #[pyo3(signature = (
        symbol,
        side,
        size,
        price,
        order_type = "limit",
        reduce_only = false,
        post_only = false,
    ))]
    #[allow(clippy::too_many_arguments)]
    pub fn place_order(
        &self,
        py: Python<'_>,
        symbol: String,
        side: String,
        size: f64,
        price: f64,
        order_type: &str,
        reduce_only: bool,
        post_only: bool,
    ) -> PyResult<PyObject> {
        // Validate inputs before any transport is considered.
        if !size.is_finite() || size <= 0.0 || size.fract() != 0.0 {
            return Err(PyValueError::new_err(
                "size must be a finite positive integer number of contracts",
            ));
        }
        if !price.is_finite() || price < 0.0 {
            return Err(PyValueError::new_err("price must be finite and >= 0"));
        }
        let side_lower = side.to_lowercase();
        if side_lower != "buy" && side_lower != "sell" {
            return Err(PyValueError::new_err("side must be 'buy' or 'sell'"));
        }
        let order_type_lower = order_type.to_lowercase();
        if order_type_lower != "limit" && order_type_lower != "market" {
            return Err(PyValueError::new_err(
                "order_type must be 'limit' or 'market'",
            ));
        }
        if order_type_lower == "limit" && price <= 0.0 {
            return Err(PyValueError::new_err("limit order price must be > 0"));
        }

        // Dry-run mode — simulate without hitting API
        if self.dry_run {
            let result = PyDict::new_bound(py);
            result.set_item("order_id", format!("DRY_RUN_{}", now_timestamp()))?;
            result.set_item("status", "simulated")?;
            result.set_item("symbol", symbol)?;
            result.set_item("side", side)?;
            result.set_item("size", size)?;
            result.set_item("price", price)?;
            result.set_item("error", py.None())?;
            result.set_item("dry_run", true)?;
            return Ok(result.into());
        }

        // Build request body
        let path = "/v2/orders";
        let timestamp = now_timestamp();

        let mut body_json = json!({
            "product_symbol": symbol,
            "side":           side_lower,
            "size":           size as u64,
            "order_type":     order_type_lower,
            "reduce_only":    reduce_only,
            "post_only":      post_only,
        });

        if order_type_lower == "limit" {
            body_json["limit_price"] = json!(price.to_string());
        }

        let body_str = body_json.to_string();

        // HMAC-SHA256 signature
        let signature = sign_request(&self.api_secret, "POST", path, timestamp, &body_str);

        // Build headers
        let mut headers = HeaderMap::new();
        headers.insert(
            "api-key",
            HeaderValue::from_str(&self.api_key).map_err(|_| {
                PyRuntimeError::new_err("api_key contains invalid header characters")
            })?,
        );
        headers.insert("timestamp", HeaderValue::from(timestamp));
        headers.insert(
            "signature",
            HeaderValue::from_str(&signature)
                .map_err(|_| PyRuntimeError::new_err("generated signature is invalid"))?,
        );
        headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));

        let url = format!("{}{}", DELTA_API_BASE, path);
        let client = self.client.clone();
        let body_bytes = body_str.clone();

        // Execute async in dedicated Tokio runtime
        let response: PyResult<Value> = self.runtime.block_on(async move {
            let resp = client
                .post(&url)
                .headers(headers)
                .body(body_bytes)
                .send()
                .await
                .map_err(|e| PyRuntimeError::new_err(format!("HTTP request failed: {e}")))?;

            let status = resp.status();
            let json_val: Value = resp
                .json()
                .await
                .map_err(|e| PyRuntimeError::new_err(format!("Failed to parse response: {e}")))?;

            if !status.is_success() {
                let error_msg = json_val["error"]
                    .as_str()
                    .or_else(|| json_val["message"].as_str())
                    .unwrap_or("Unknown error")
                    .to_string();
                return Err(PyRuntimeError::new_err(format!(
                    "Order failed (HTTP {}): {}",
                    status.as_u16(),
                    error_msg
                )));
            }
            Ok(json_val)
        });

        let json_val = response?;

        // Parse and return result as Python dict
        let result = PyDict::new_bound(py);
        let order = &json_val["result"];
        result.set_item(
            "order_id",
            order["id"]
                .as_u64()
                .map(|v| v.to_string())
                .or_else(|| order["id"].as_str().map(str::to_string))
                .unwrap_or_default(),
        )?;
        result.set_item("status", order["state"].as_str().unwrap_or("unknown"))?;
        result.set_item(
            "symbol",
            order["product_symbol"].as_str().unwrap_or(&symbol),
        )?;
        result.set_item("side", order["side"].as_str().unwrap_or(&side))?;
        result.set_item("size", order["size"].as_f64().unwrap_or(size))?;
        result.set_item(
            "price",
            order["limit_price"]
                .as_str()
                .and_then(|s| s.parse::<f64>().ok())
                .unwrap_or(price),
        )?;
        result.set_item("error", py.None())?;
        result.set_item("raw", json_val.to_string())?;

        Ok(result.into())
    }

    /// Cancel an order by order_id.
    ///
    /// Args:
    ///   order_id: the order ID to cancel
    ///   symbol:   product symbol (required by Delta API)
    ///
    /// Returns: dict with status
    pub fn cancel_order(
        &self,
        py: Python<'_>,
        order_id: String,
        symbol: String,
    ) -> PyResult<PyObject> {
        if order_id.trim().is_empty() || symbol.trim().is_empty() {
            return Err(PyValueError::new_err(
                "order_id and symbol must be non-empty",
            ));
        }
        if self.dry_run {
            let result = PyDict::new_bound(py);
            result.set_item("success", true)?;
            result.set_item("order_id", order_id)?;
            result.set_item("dry_run", true)?;
            return Ok(result.into());
        }
        let path = "/v2/orders";
        let timestamp = now_timestamp();
        let body_json = json!({
            "id":             order_id.parse::<u64>().unwrap_or(0),
            "product_symbol": symbol,
        });
        let body_str = body_json.to_string();
        let signature = sign_request(&self.api_secret, "DELETE", path, timestamp, &body_str);

        let mut headers = HeaderMap::new();
        headers.insert("api-key", HeaderValue::from_str(&self.api_key).unwrap());
        headers.insert("timestamp", HeaderValue::from(timestamp));
        headers.insert("signature", HeaderValue::from_str(&signature).unwrap());
        headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));

        let url = format!("{}{}", DELTA_API_BASE, path);
        let client = self.client.clone();
        let body_bytes = body_str.clone();

        let response: PyResult<Value> = self.runtime.block_on(async move {
            let resp = client
                .delete(&url)
                .headers(headers)
                .body(body_bytes)
                .send()
                .await
                .map_err(|e| PyRuntimeError::new_err(format!("Cancel request failed: {e}")))?;
            resp.json::<Value>().await.map_err(|e| {
                PyRuntimeError::new_err(format!("Failed to parse cancel response: {e}"))
            })
        });

        let json_val = response?;
        let result = PyDict::new_bound(py);
        let success = json_val["success"].as_bool().unwrap_or(false);
        result.set_item("success", success)?;
        result.set_item("order_id", order_id)?;
        result.set_item("raw", json_val.to_string())?;
        Ok(result.into())
    }

    /// Check if executor is in dry-run mode.
    pub fn is_dry_run(&self) -> bool {
        self.dry_run
    }

    fn __repr__(&self) -> String {
        format!(
            "OrderExecutor(api_key=<redacted>, dry_run={})",
            self.dry_run
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dry_run_validates_and_never_needs_network() {
        Python::with_gil(|py| {
            let executor =
                OrderExecutor::new("test-key".into(), "test-secret".into(), true).unwrap();
            let result = executor
                .place_order(
                    py,
                    "BTCUSDT".into(),
                    "BUY".into(),
                    2.0,
                    100.0,
                    "limit",
                    false,
                    false,
                )
                .unwrap();
            let dict = result.bind(py).downcast::<PyDict>().unwrap();
            assert_eq!(
                dict.get_item("status")
                    .unwrap()
                    .unwrap()
                    .extract::<String>()
                    .unwrap(),
                "simulated"
            );
            assert!(dict
                .get_item("dry_run")
                .unwrap()
                .unwrap()
                .extract::<bool>()
                .unwrap());
            let cancel = executor
                .cancel_order(py, "123".into(), "BTCUSDT".into())
                .unwrap();
            let cancel_dict = cancel.bind(py).downcast::<PyDict>().unwrap();
            assert!(cancel_dict
                .get_item("dry_run")
                .unwrap()
                .unwrap()
                .extract::<bool>()
                .unwrap());
            assert!(executor.__repr__().contains("redacted"));
        });
    }

    #[test]
    fn invalid_order_arguments_are_rejected_before_transport() {
        Python::with_gil(|py| {
            let executor = OrderExecutor::new("k".into(), "s".into(), true).unwrap();
            assert!(executor
                .place_order(
                    py,
                    "BTCUSDT".into(),
                    "buy".into(),
                    1.5,
                    100.0,
                    "limit",
                    false,
                    false
                )
                .is_err());
            assert!(executor
                .place_order(
                    py,
                    "BTCUSDT".into(),
                    "buy".into(),
                    1.0,
                    0.0,
                    "limit",
                    false,
                    false
                )
                .is_err());
            assert!(executor
                .place_order(
                    py,
                    "BTCUSDT".into(),
                    "hold".into(),
                    1.0,
                    100.0,
                    "limit",
                    false,
                    false
                )
                .is_err());
            assert!(OrderExecutor::new("".into(), "s".into(), true).is_err());
        });
    }
}

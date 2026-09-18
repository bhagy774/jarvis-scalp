import importlib
import io
import os
import unittest
from unittest.mock import patch

from jarvis_decision import build_final_decision, confidence_text, normalize_confidence
from jarvis_risk import calculate_trade_size, contract_quote_value_usdt
from jarvis_dashboard import render_dashboard


class EmptyScanner:
    def __init__(self):
        self._best = ""
    def run_now(self):
        return ""
    def get_delta_symbol(self):
        return ""
    def get_best_coin(self):
        return ""
    def get_all_scores(self):
        return {}


class DeltaSymbols:
    def get_available_symbols(self):
        return ["BTCUSDT"]


class AuditRegressionTests(unittest.TestCase):
    def test_confidence_formats_and_na_are_normalized(self):
        for raw in (85, "85%", "85/100", "85/100 (Autonomy)"):
            self.assertEqual(normalize_confidence(raw), 85)
            self.assertEqual(confidence_text(raw), "85")
        self.assertIsNone(normalize_confidence("N/A"))
        self.assertEqual(confidence_text("N/A"), "N/A")

    def test_conflict_and_non_primary_options_block_execution(self):
        conflict = build_final_decision(
            {"direction": "CALL", "confidence_score": "85%"},
            symbol="ETHUSDT", opinions=["BUY", "SELL"]
        )
        self.assertFalse(conflict["execution_allowed"])
        self.assertEqual(conflict["direction"], "NO_TRADE")
        macro = build_final_decision(
            {"direction": "CALL", "confidence_score": 85},
            symbol="ETHUSDT", require_options=True,
            options_context={"available": True, "role": "btc_macro_confirmation"}
        )
        self.assertFalse(macro["execution_allowed"])

    def test_mtf_fetch_uses_selected_symbol(self):
        class Delta:
            def __init__(self):
                self.symbols = []
            def get_historical_candles(self, symbol, resolution, limit):
                self.symbols.append(symbol)
                return [{"time": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]
        try:
            import jarvis_FIXED
        except ModuleNotFoundError as exc:
            self.skipTest(f"optional runtime dependency unavailable: {exc.name}")
        engine = object.__new__(jarvis_FIXED.JarvisElite)
        engine.is_backtest_mode = False
        engine.delta_client = Delta()
        data = engine._fetch_mtf_from_api("ETHUSDT")
        self.assertTrue(data)
        self.assertEqual(set(engine.delta_client.symbols), {"ETHUSDT"})

    def test_empty_scanner_candidate_is_blocked(self):
        from jarvis_market_router import MarketRouter
        route = MarketRouter(scanner=EmptyScanner(), delta_client=DeltaSymbols()).select_crypto()
        self.assertEqual(route.status, "BLOCKED")
        self.assertIn("invalid symbol", route.reason)

    def test_non_one_contract_value_sizes_actual_notional(self):
        product = {"contract_value": 2, "contract_value_currency": "USDT"}
        self.assertEqual(contract_quote_value_usdt(product, 100), 2)
        result = calculate_trade_size(
            100, 90, 0.002, max_trade_risk_usdt=10,
            contract_value_usdt=2, require_contract_value=True,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["notional_usdt"], result["contracts"] * 2)
        self.assertIsNone(contract_quote_value_usdt({"contract_value": 1}, 100))

    def test_dashboard_does_not_append_percent_to_na(self):
        stream = io.StringIO()
        text = render_dashboard(
            {"signal": {"direction": "NO_TRADE", "confidence": "N/A"}},
            stream=stream,
        )
        self.assertIn("NO_TRADE  (N/A)", text)
        self.assertNotIn("N/A%)", text)

    def test_binance_proxy_redaction_and_mirror_retry(self):
        import binance_data

        class Response:
            def __init__(self, status):
                self.status_code = status
                self.text = "temporary"
            def json(self):
                return {"price": "100"}

        class Session:
            def __init__(self):
                self.proxies = {}
                self.headers = {}
                self.calls = []
            def get(self, url, **kwargs):
                self.calls.append(url)
                return Response(503 if len(self.calls) == 1 else 200)

        with patch.object(binance_data, "_PROXY", "http://user:secret@example.test:8080"):
            with patch.object(binance_data.requests, "Session", Session):
                with self.assertLogs(binance_data.logger, level="INFO") as captured:
                    client = binance_data.BinanceData()
                    client.get_live_price("BTCUSDT")
                self.assertEqual(len(client.session.calls), 2)
                joined = " ".join(captured.output)
                self.assertNotIn("secret", joined)

    def test_unavailable_selected_options_block_required_execution(self):
        decision = build_final_decision(
            {"direction": "BUY", "confidence_score": "90%"},
            symbol="SOLUSDT", require_options=True,
            options_context={"available": False, "role": "unavailable"},
        )
        self.assertFalse(decision["execution_allowed"])
        self.assertEqual(decision["direction"], "NO_TRADE")
        self.assertIn("options context", " ".join(decision["reasons"]))

    def test_non_spot_fallback_requires_explicit_compatibility(self):
        from delta_api_wrapper import DeltaExchangeData
        class FakeBinance:
            def get_last_source(self):
                return {"source": "bybit_linear_perpetual", "market_semantics": "linear_perpetual"}
        client = object.__new__(DeltaExchangeData)
        client._binance = FakeBinance()
        with patch.dict(os.environ, {"JARVIS_ALLOW_PERPETUAL_FALLBACK": "0"}):
            self.assertFalse(client._binance_spot_compatible())
        with patch.dict(os.environ, {"JARVIS_ALLOW_PERPETUAL_FALLBACK": "1"}):
            self.assertTrue(client._binance_spot_compatible())

    def test_watchdog_bad_threshold_falls_back(self):
        import jarvis_watchdog
        with patch.dict(os.environ, {"DOCTOR_STALE_THRESHOLD": "not-a-number"}):
            module = importlib.reload(jarvis_watchdog)
            self.assertEqual(module.HEARTBEAT_STALE_SECONDS, 600)
        with patch.dict(os.environ, {"DOCTOR_STALE_THRESHOLD": "0"}):
            module = importlib.reload(jarvis_watchdog)
            self.assertEqual(module.HEARTBEAT_STALE_SECONDS, 600)
        importlib.reload(jarvis_watchdog)


if __name__ == "__main__":
    unittest.main()

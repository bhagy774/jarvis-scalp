"""Offline contract tests for coordinator-to-HUD telemetry.

No service, exchange, model, subprocess, or real HTTP request is started here.
"""

import asyncio
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    status_code = 202


class FakeRequest:
    def __init__(self, payload, token="", host="127.0.0.1"):
        self._payload = payload
        self.headers = {"X-Jarvis-Hud-Token": token}
        self.client = types.SimpleNamespace(host=host)

    async def json(self):
        return self._payload


class RunnerHudIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_module("runner_under_test", ROOT / "run_all_parts.py")
        cls.hud = load_module("hud_under_test", ROOT / "jarvis_hud_server.py")

    def test_runner_defaults_to_no_service_start(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            self.runner.importlib, "import_module", side_effect=AssertionError("must not import core")
        ):
            self.assertEqual(self.runner.run_all_parts(), (None, None))

    def test_runner_posts_to_current_local_telemetry_endpoint(self):
        calls = []
        fake_requests = types.SimpleNamespace(
            post=lambda *args, **kwargs: calls.append((args, kwargs)) or FakeResponse()
        )
        payload = {"regime": "RANGE", "signal": {"direction": "BUY", "score": 80}}
        with patch.dict(sys.modules, {"requests": fake_requests}):
            self.assertTrue(self.runner.post_hud_telemetry(payload, "test-token"))

        self.assertEqual(calls[0][0][0], "http://127.0.0.1:7788/api/telemetry")
        self.assertEqual(calls[0][1]["headers"], {"X-Jarvis-Hud-Token": "test-token"})
        self.assertEqual(calls[0][1]["json"], payload)

    def test_mocked_runner_payload_is_accepted_by_hud_and_stays_display_only(self):
        payload = {
            "market_data": {"price": 65000},
            "thoughts": ["analysis only"],
            "regime": "TRENDING",
            "signal": {"direction": "BUY", "confidence": 82},
            "ai_consensus": {"votes": {"BUY": 3}},
        }
        with patch.dict(os.environ, {"JARVIS_HUD_INGEST_TOKEN": "shared-token"}, clear=False):
            result = asyncio.run(self.hud.receive_telemetry(FakeRequest(payload, "shared-token")))

        self.assertTrue(result["accepted"])
        self.assertEqual(self.hud.state["parts"]["Coordinator"]["direction"], "BULLISH")
        self.assertEqual(self.hud.state["coordinator_telemetry"]["regime"], "TRENDING")
        paths = {route.path for route in self.hud.app.routes}
        self.assertIn("/api/telemetry", paths)
        self.assertFalse(any("order" in path or "trade" in path for path in paths))

    def test_hud_rejects_remote_or_wrong_token_telemetry(self):
        payload = {"signal": {"direction": "SELL"}}
        with patch.dict(os.environ, {"JARVIS_HUD_INGEST_TOKEN": "required"}, clear=False):
            with self.assertRaises(self.hud.HTTPException) as wrong_token:
                asyncio.run(self.hud.receive_telemetry(FakeRequest(payload, "wrong")))
            self.assertEqual(wrong_token.exception.status_code, 403)

            with self.assertRaises(self.hud.HTTPException) as remote_client:
                asyncio.run(self.hud.receive_telemetry(FakeRequest(payload, "required", "192.0.2.12")))
            self.assertEqual(remote_client.exception.status_code, 403)

    def test_monolith_uses_the_same_contract(self):
        source = (ROOT / "jarvis_FIXED.py").read_text(encoding="utf-8")
        self.assertIn("http://127.0.0.1:7788/api/telemetry", source)
        self.assertIn("X-Jarvis-Hud-Token", source)
        self.assertNotIn("localhost:8000/api/update", source)


if __name__ == "__main__":
    unittest.main()

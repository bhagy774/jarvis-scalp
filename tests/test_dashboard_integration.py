import io
import time
from contextlib import redirect_stdout
from types import SimpleNamespace


def test_live_dashboard_renders_final_gated_decision_not_stale_prediction():
    from jarvis_FIXED import LiveTradingEngine
    from jarvis_dashboard import UnifiedDashboard

    engine = object.__new__(LiveTradingEngine)
    engine.last_jarvis_result = {
        "trade_signal": {"direction": "CALL", "confidence_score": "90%"},
        "intelligence_board": ["raw market diagnostic"],
    }
    engine.last_decision = {
        "direction": "NO_TRADE", "confidence": None,
        "execution_allowed": False, "symbol": "ETHUSDT",
        "reasons": ["PreSim rejected: simulated stress"],
    }
    engine.last_execution_result = None
    engine._dashboard_signal = {"direction": "CALL", "confidence_score": 90}
    engine._dashboard_plan = {"entry": "$100.00"}
    engine._dashboard_account = {}
    engine._dashboard_events = []
    engine.paper_open_trades = []
    engine.paper_wins = engine.paper_losses = engine.paper_breakeven = 0
    engine.paper_balance = 0.0
    engine.engine_start_time = time.time()
    engine.auto_trader = None
    engine.readiness = {"status": "NOT_READY"}
    engine.active_symbol = "ETHUSDT"
    engine.jarvis = SimpleNamespace(
        gpu_status={"backend": "cpu"}, native_engine_status={},
        last_ollama_decision={"decision": "WAIT"},
        latest_part_results={"part1_breakout": {"signal": 1, "thought": "breakout evidence"}},
        latest_part7={},
    )
    engine.dashboard = UnifiedDashboard(clear=False)
    engine._delta_available_balance = lambda: (None, "offline test")

    output = io.StringIO()
    with redirect_stdout(output):
        engine._render_unified_dashboard(
            symbol="ETHUSDT", current_price=100.0, action="BLOCKED",
            gate_reason="PreSim rejected: simulated stress",
        )

    text = output.getvalue()
    assert "MODEL PREDICTION" in text and "CALL" in text and "90%" in text
    assert "FINAL DECISION" in text and "NO_TRADE" in text
    assert "PreSim rejected: simulated stress" in text
    assert "part1_breakout" in text and "supports prediction" in text
    assert "raw signals/diagnostics; not independent causal attribution" in text
    assert "EXECUTION RESULT" in text and "not attempted" in text

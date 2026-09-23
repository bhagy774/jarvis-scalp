import pytest
from unittest.mock import patch, MagicMock
from jarvis_specialist_pool import SpecialistPool

@pytest.fixture
def specialist_pool():
    pool = SpecialistPool(max_workers=3)
    yield pool
    pool.shutdown()

def test_specialist_pool_initialization():
    pool = SpecialistPool(max_workers=2)
    assert pool.executor._max_workers == 2
    pool.shutdown()

@patch('jarvis_specialist_pool.call_ollama')
def test_ask_specialist_success(mock_call_ollama, specialist_pool):
    mock_call_ollama.return_value = ("[APPROVE] Looks good", None)
    context_packet = {"price": 100}
    response = specialist_pool._ask_specialist("Role", "model", context_packet, "prompt")

    assert response == "[APPROVE] Looks good"
    mock_call_ollama.assert_called_once()

@patch('jarvis_specialist_pool.call_ollama')
def test_ask_specialist_failure(mock_call_ollama, specialist_pool):
    mock_call_ollama.return_value = (None, "Timeout")
    context_packet = {"price": 100}
    response = specialist_pool._ask_specialist("Role", "model", context_packet, "prompt")

    assert response == "[Unavailable: Timeout]"
    mock_call_ollama.assert_called_once()

@patch('jarvis_specialist_pool.call_ollama')
def test_run_parallel_evaluation(mock_call_ollama, specialist_pool):
    # Setup mock to return different values based on call count or args
    def mock_call(*args, **kwargs):
        return ("[APPROVE] Fake reason", None)

    mock_call_ollama.side_effect = mock_call

    context_packet = {"market": "bullish"}
    opinions = specialist_pool.run_parallel_evaluation(context_packet)

    assert "analyst" in opinions
    assert "validator" in opinions
    assert "risk_officer" in opinions

    assert opinions["analyst"] == "[APPROVE] Fake reason"
    assert opinions["validator"] == "[APPROVE] Fake reason"
    assert opinions["risk_officer"] == "[APPROVE] Fake reason"

    assert mock_call_ollama.call_count == 3

@patch('jarvis_specialist_pool.call_ollama')
def test_synthesize_chairman_decision_approve(mock_call_ollama, specialist_pool):
    mock_call_ollama.return_value = ("[CONSENSUS_EXECUTE] 2 out of 3 approve.", None)

    opinions = {
        "analyst": "[APPROVE] Reason",
        "validator": "[APPROVE] Reason",
        "risk_officer": "[REJECT] Reason",
    }

    decision = specialist_pool.synthesize_chairman_decision({"ctx": "test"}, opinions)

    assert decision["approved"] is True
    assert decision["final_verdict"] == "CONSENSUS_EXECUTE"
    assert decision["chairman_summary"] == "[CONSENSUS_EXECUTE] 2 out of 3 approve."
    assert decision["approve_votes"] == 2

@patch('jarvis_specialist_pool.call_ollama')
def test_synthesize_chairman_decision_reject(mock_call_ollama, specialist_pool):
    mock_call_ollama.return_value = ("[CONSENSUS_REJECT] Too risky.", None)

    opinions = {
        "analyst": "[REJECT] Reason",
        "validator": "[APPROVE] Reason",
        "risk_officer": "[REJECT] Reason",
    }

    decision = specialist_pool.synthesize_chairman_decision({"ctx": "test"}, opinions)

    assert decision["approved"] is False
    assert decision["final_verdict"] == "CONSENSUS_REJECT"
    assert decision["chairman_summary"] == "[CONSENSUS_REJECT] Too risky."
    assert decision["approve_votes"] == 1

@patch('jarvis_specialist_pool.call_ollama')
def test_synthesize_chairman_decision_fallback(mock_call_ollama, specialist_pool):
    # Simulate Chairman returning an unexpected or rejected format, but we have 3 approve votes
    mock_call_ollama.return_value = ("[CONSENSUS_REJECT] Chairman got confused", None)

    opinions = {
        "analyst": "[APPROVE] Reason",
        "validator": "[APPROVE] Reason",
        "risk_officer": "[APPROVE] Reason",
    }

    decision = specialist_pool.synthesize_chairman_decision({"ctx": "test"}, opinions)

    # Fallback should kick in and set approved to True
    assert decision["approved"] is True
    assert decision["final_verdict"] == "CONSENSUS_EXECUTE"
    assert decision["approve_votes"] == 3

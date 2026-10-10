"""Retired RAG has no validated replacement: startup must refuse, not call models."""
import pytest
import jarvis_rag_chat as rag

@pytest.mark.parametrize("entrypoint", [rag.initialize_database, rag.main])
def test_retired_rag_fails_closed_without_network(monkeypatch, entrypoint):
    monkeypatch.setattr("requests.post", lambda *a, **k: pytest.fail("no model calls"))
    with pytest.raises(RuntimeError, match="retired.*no validated Laya"):
        entrypoint()

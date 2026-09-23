import os
import json
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kie_gpt6_client import KieGPT6Client

def test_initialization_defaults(monkeypatch):
    monkeypatch.delenv("KIE_API_KEY", raising=False)
    monkeypatch.delenv("KIE_BASE_URL", raising=False)

    client = KieGPT6Client()
    assert client.api_key == ""
    assert client.base_url == "https://api.kie.ai"
    assert client.endpoint == "https://api.kie.ai/codex/v1/responses"

def test_initialization_with_args():
    client = KieGPT6Client(api_key="test_key", base_url="http://custom.url/")
    assert client.api_key == "test_key"
    assert client.base_url == "http://custom.url"
    assert client.endpoint == "http://custom.url/codex/v1/responses"

def test_initialization_with_env(monkeypatch):
    monkeypatch.setenv("KIE_API_KEY", "env_key")
    monkeypatch.setenv("KIE_BASE_URL", "http://env.url")

    client = KieGPT6Client()
    assert client.api_key == "env_key"
    assert client.base_url == "http://env.url"
    assert client.endpoint == "http://env.url/codex/v1/responses"

def test_initialization_args_override_env(monkeypatch):
    monkeypatch.setenv("KIE_API_KEY", "env_key")
    monkeypatch.setenv("KIE_BASE_URL", "http://env.url")

    client = KieGPT6Client(api_key="arg_key")
    assert client.api_key == "arg_key"
    assert client.base_url == "http://env.url"

def test_extract_text_output_content_string():
    client = KieGPT6Client()
    data = {
        "output": [
            {"content": "Hello"},
            {"content": "World"}
        ]
    }
    assert client._extract_text(data) == "Hello\nWorld"

def test_extract_text_output_content_list():
    client = KieGPT6Client()
    data = {
        "output": [
            {"content": [
                {"text": "Block 1"},
                "Block 2",
                {"other": "ignore"}
            ]}
        ]
    }
    assert client._extract_text(data) == "Block 1\nBlock 2"

def test_extract_text_output_text():
    client = KieGPT6Client()
    data = {
        "output": [
            {"text": "Direct text"}
        ]
    }
    assert client._extract_text(data) == "Direct text"

def test_extract_text_choices():
    client = KieGPT6Client()
    data = {
        "choices": [
            {"message": {"content": "Choice content"}}
        ]
    }
    assert client._extract_text(data) == "Choice content"

def test_extract_text_fallback():
    client = KieGPT6Client()
    data = {"unknown": "format"}
    expected = json.dumps(data, indent=2, ensure_ascii=False)
    assert client._extract_text(data) == expected


def test_ask_external_ai_disabled(monkeypatch):
    monkeypatch.setenv("JARVIS_ENABLE_EXTERNAL_AI", "0")
    client = KieGPT6Client(api_key="test")

    # Non-stream
    reason, data = client.ask("Hello")
    assert data["disabled"] is True
    assert "External AI disabled" in reason

    # Stream
    stream = client.ask("Hello", stream=True)
    assert list(stream) == []

def test_ask_missing_api_key(monkeypatch):
    monkeypatch.setenv("JARVIS_ENABLE_EXTERNAL_AI", "1")
    monkeypatch.delenv("KIE_API_KEY", raising=False)
    client = KieGPT6Client(api_key="")

    with pytest.raises(ValueError, match="KIE_API_KEY missing"):
        client.ask("Hello")

@patch('requests.post')
def test_ask_successful_non_stream(mock_post, monkeypatch):
    monkeypatch.setenv("JARVIS_ENABLE_EXTERNAL_AI", "1")
    client = KieGPT6Client(api_key="test_key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"output": [{"content": "GPT response"}]}
    mock_post.return_value = mock_response

    text, raw = client.ask("Hello", web_search=True)

    assert text == "GPT response"
    assert raw == {"output": [{"content": "GPT response"}]}

    # Check that tools was added to payload
    args, kwargs = mock_post.call_args
    assert kwargs["json"]["tools"] == [{"type": "web_search"}]

@patch('requests.post')
def test_ask_successful_stream(mock_post, monkeypatch):
    monkeypatch.setenv("JARVIS_ENABLE_EXTERNAL_AI", "1")
    client = KieGPT6Client(api_key="test_key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = iter([b"line1", b"line2"])
    mock_post.return_value = mock_response

    stream = client.ask("Hello", stream=True)

    assert list(stream) == [b"line1", b"line2"]

    args, kwargs = mock_post.call_args
    assert kwargs["stream"] is True

@patch('requests.post')
def test_ask_status_code_error(mock_post, monkeypatch):
    monkeypatch.setenv("JARVIS_ENABLE_EXTERNAL_AI", "1")
    client = KieGPT6Client(api_key="test_key")

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_post.return_value = mock_response

    with pytest.raises(RuntimeError, match="Error 500: Internal Server Error"):
        client.ask("Hello")

    with pytest.raises(RuntimeError, match="Error 500: Internal Server Error"):
        client.ask("Hello", stream=True)

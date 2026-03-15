"""
OpenAI SDK Compatibility Tests
================================

Tests that the TELOS Gateway accepts requests in the exact format
that the OpenAI Python SDK sends, and returns compatible responses.
"""

import hashlib
import os

import pytest
from fastapi.testclient import TestClient

from telos_gateway.main import app


@pytest.fixture(autouse=True)
def _configure_test_gateway_key(monkeypatch):
    """Register the test API key in the gateway allowlist for all tests."""
    test_key_hash = hashlib.sha256("sk-test-key-12345".encode()).hexdigest()
    monkeypatch.setenv("TELOS_GATEWAY_API_KEYS", test_key_hash)
    # Reset the cached gateway keys so the new env var takes effect
    import telos_gateway.auth as auth_mod
    auth_mod._gateway_keys_cache = None
    yield
    auth_mod._gateway_keys_cache = None


@pytest.fixture
def client():
    """Create a test client for the gateway app."""
    return TestClient(app)


# ============================================================================
# Request format compatibility
# ============================================================================


class TestRequestFormat:
    """Gateway should accept standard OpenAI request shapes."""

    def test_minimal_request_accepted(self, client):
        """Minimal valid request: model + messages."""
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer sk-test-key-12345"},
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        # Will fail at LLM call (no real key) but should not be a 422 validation error
        assert response.status_code != 422

    def test_full_request_accepted(self, client):
        """Full request with all optional fields."""
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer sk-test-key-12345"},
            json={
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "What is 2+2?"},
                ],
                "temperature": 0.7,
                "max_tokens": 100,
                "top_p": 0.9,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
                "n": 1,
                "stream": False,
            },
        )
        assert response.status_code != 422

    def test_tools_request_accepted(self, client):
        """Request with tool definitions."""
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer sk-test-key-12345"},
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "What's the weather?"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "description": "Get current weather",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {"type": "string"},
                                },
                                "required": ["location"],
                            },
                        },
                    }
                ],
                "tool_choice": "auto",
            },
        )
        assert response.status_code != 422

    def test_missing_model_returns_422(self, client):
        """Request without model should fail validation."""
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer sk-test-key-12345"},
            json={
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert response.status_code == 422

    def test_missing_messages_returns_422(self, client):
        """Request without messages should fail validation."""
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer sk-test-key-12345"},
            json={
                "model": "gpt-4",
            },
        )
        assert response.status_code == 422


# ============================================================================
# Response format
# ============================================================================


class TestResponseFormat:
    """Verify models endpoint returns OpenAI-compatible format."""

    def test_models_list_format(self, client):
        """GET /v1/models should return OpenAI list format."""
        response = client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert isinstance(data["data"], list)
        for model in data["data"]:
            assert "id" in model
            assert "object" in model
            assert model["object"] == "model"

    def test_health_format(self, client):
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "version" in data


# ============================================================================
# Provider routing
# ============================================================================


class TestProviderRouting:
    """Requests should route to the correct provider based on model name."""

    def test_gpt_model_accepted(self, client):
        """GPT models should be accepted (routes to OpenAI)."""
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer sk-test-key"},
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
            },
        )
        # Should not be a validation error
        assert response.status_code != 422

    def test_mistral_model_accepted(self, client):
        """Mistral models should be accepted (routes to Mistral)."""
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer sk-test-key"},
            json={
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": "test"}],
            },
        )
        assert response.status_code != 422


# ============================================================================
# Streaming
# ============================================================================


class TestStreaming:
    """Streaming parameter handling."""

    def test_stream_false_accepted(self, client):
        """Non-streaming request should work."""
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer sk-test-key"},
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
                "stream": False,
            },
        )
        assert response.status_code != 422

    def test_stream_true_accepted(self, client):
        """Streaming request should be accepted (even if streaming is disabled)."""
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer sk-test-key"},
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
                "stream": True,
            },
        )
        # Should not reject based on stream parameter
        assert response.status_code != 422

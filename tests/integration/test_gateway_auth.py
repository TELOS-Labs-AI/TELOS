"""
Gateway Authentication Tests
=============================

Tests for the TELOS Gateway authentication and rate limiting.
"""

import pytest
from fastapi.testclient import TestClient

from telos_gateway.main import app


@pytest.fixture
def client():
    """Create a test client for the gateway app."""
    return TestClient(app)


# ============================================================================
# Health endpoint (no auth required)
# ============================================================================


class TestHealthEndpoint:
    """Health check should work without authentication."""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uptime_seconds" in data

    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TELOS Gateway"
        assert "endpoints" in data

    def test_models_returns_200(self, client):
        response = client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0


# ============================================================================
# Authentication
# ============================================================================


class TestAuthentication:
    """Chat completions endpoint requires Bearer token."""

    def test_missing_auth_returns_401(self, client):
        response = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 401
        data = response.json()
        assert "error" in data["detail"]
        assert data["detail"]["error"]["type"] == "authentication_error"

    def test_empty_bearer_returns_401(self, client):
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer "},
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 401

    def test_invalid_telos_agent_key_returns_401(self, client):
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer telos-agent-invalid-key-12345"},
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"]["type"] == "authentication_error"


# ============================================================================
# Error format consistency
# ============================================================================


class TestErrorFormat:
    """All errors should use consistent JSON format."""

    def test_401_error_format(self, client):
        response = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )
        data = response.json()
        assert "detail" in data
        err = data["detail"]["error"]
        assert "message" in err
        assert "type" in err
        assert "code" in err

    def test_404_agent_not_found(self, client):
        response = client.get("/v1/agents/nonexistent-agent-id")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        err = data["detail"]["error"]
        assert err["type"] == "not_found"


# ============================================================================
# Agent registration
# ============================================================================


class TestAgentRegistration:
    """Test agent registration and lookup flow."""

    def test_register_agent(self, client):
        response = client.post(
            "/v1/agents",
            json={
                "name": "Test Agent",
                "owner": "Test Owner",
                "purpose_statement": "I am a test agent for unit testing the TELOS gateway registration flow.",
                "domain": "testing",
                "tools": [],
                "risk_level": "low",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "agent_id" in data
        assert "api_key" in data
        assert data["api_key"].startswith("telos-agent-")

    def test_register_agent_short_name_rejected(self, client):
        response = client.post(
            "/v1/agents",
            json={
                "name": "AB",  # too short
                "owner": "Test Owner",
                "purpose_statement": "I am a test agent for unit testing.",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_register_agent_short_purpose_rejected(self, client):
        response = client.post(
            "/v1/agents",
            json={
                "name": "Test Agent",
                "owner": "Test Owner",
                "purpose_statement": "Too short",  # < 20 chars
            },
        )
        assert response.status_code == 422

    def test_register_and_lookup(self, client):
        # Register
        reg_response = client.post(
            "/v1/agents",
            json={
                "name": "Lookup Test Agent",
                "owner": "Test Owner",
                "purpose_statement": "I am a test agent for verifying the lookup flow works correctly.",
                "domain": "testing",
            },
        )
        agent_id = reg_response.json()["agent_id"]

        # Lookup
        get_response = client.get(f"/v1/agents/{agent_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["agent_id"] == agent_id
        assert data["name"] == "Lookup Test Agent"
        assert data["is_active"] is True

    def test_deactivate_requires_auth(self, client):
        # Register first
        reg = client.post(
            "/v1/agents",
            json={
                "name": "Deactivate Test Agent",
                "owner": "Test Owner",
                "purpose_statement": "I am a test agent for verifying deactivation requires authentication.",
            },
        )
        agent_id = reg.json()["agent_id"]

        # Try to deactivate without auth
        response = client.delete(f"/v1/agents/{agent_id}")
        assert response.status_code == 401


# ============================================================================
# CORS
# ============================================================================


class TestCORS:
    """CORS should be properly configured (not wildcard)."""

    def test_cors_allows_configured_origin(self, client):
        response = client.options(
            "/v1/chat/completions",
            headers={
                "Origin": "http://localhost:8501",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200
        # Should include the allowed origin
        assert response.headers.get("access-control-allow-origin") == "http://localhost:8501"

    def test_cors_rejects_unknown_origin(self, client):
        response = client.options(
            "/v1/chat/completions",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        # Should NOT include the evil origin in allowed headers
        allowed = response.headers.get("access-control-allow-origin", "")
        assert "evil.example.com" not in allowed

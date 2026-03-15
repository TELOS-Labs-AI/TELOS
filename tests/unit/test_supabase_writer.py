"""Tests for telos_adapters.openclaw.supabase_writer."""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestWriteSupabase:
    """Test the shared Supabase writer."""

    def setup_method(self):
        """Reset cached config between tests."""
        import telos_adapters.openclaw.supabase_writer as sw
        sw._config = None

    def test_noop_when_no_env_vars(self):
        """Should silently return when SUPABASE_URL is not set."""
        from telos_adapters.openclaw.supabase_writer import write_supabase
        # No env vars set -- should not raise
        write_supabase("governance_verdicts", {"decision": "execute"})

    @patch.dict("os.environ", {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-key-123",
    })
    @patch("urllib.request.urlopen")
    def test_posts_to_correct_table(self, mock_urlopen):
        """Should POST to the correct PostgREST endpoint."""
        from telos_adapters.openclaw.supabase_writer import write_supabase

        write_supabase("governance_verdicts", {"decision": "execute", "fidelity": 0.92})

        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://test.supabase.co/rest/v1/governance_verdicts"
        assert req.method == "POST"
        assert req.get_header("Content-type") == "application/json"
        assert req.get_header("Apikey") == "test-key-123"
        assert req.get_header("Authorization") == "Bearer test-key-123"
        assert req.get_header("Prefer") == "return=minimal"

    @patch.dict("os.environ", {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-key-123",
    })
    @patch("urllib.request.urlopen")
    def test_serializes_jsonb_dicts(self, mock_urlopen):
        """JSONB columns (dicts/lists) should be JSON-serialized strings."""
        from telos_adapters.openclaw.supabase_writer import write_supabase

        write_supabase("governance_verdicts", {
            "decision": "execute",
            "metadata": {"explanation": "test", "score": 0.5},
            "collections": ["a", "b"],
        })

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        # Dicts and lists should be JSON strings, not nested objects
        assert isinstance(body["metadata"], str)
        assert isinstance(body["collections"], str)
        assert body["decision"] == "execute"

    @patch.dict("os.environ", {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-key-123",
    })
    @patch("urllib.request.urlopen", side_effect=Exception("Connection refused"))
    def test_swallows_exceptions(self, mock_urlopen):
        """Should never raise -- fire and forget."""
        from telos_adapters.openclaw.supabase_writer import write_supabase

        # Should not raise
        write_supabase("governance_verdicts", {"decision": "execute"})

    @patch.dict("os.environ", {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-key-123",
    })
    @patch("urllib.request.urlopen")
    def test_timeout_is_5_seconds(self, mock_urlopen):
        """Should use 5-second timeout."""
        from telos_adapters.openclaw.supabase_writer import write_supabase

        write_supabase("drift_events", {"event_type": "drift_block"})

        _, kwargs = mock_urlopen.call_args
        assert kwargs.get("timeout") == 5

    @patch.dict("os.environ", {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_KEY": "fallback-key",
        "SUPABASE_SERVICE_ROLE_KEY": "",
        "SUPABASE_KEY": "",
    })
    @patch("urllib.request.urlopen")
    def test_falls_back_to_service_key(self, mock_urlopen):
        """Should fall back to SUPABASE_SERVICE_KEY if SERVICE_ROLE_KEY missing."""
        from telos_adapters.openclaw.supabase_writer import write_supabase

        write_supabase("pa_lifecycle", {"event_type": "pa_verified"})

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Apikey") == "fallback-key"


class TestDaemonPersistHelpers:
    """Test the daemon's persist helper functions are importable."""

    @pytest.mark.skip(reason="persist helpers moved out of daemon module")
    def test_persist_verdict_import(self):
        """_persist_verdict should be importable from daemon."""
        from telos_adapters.openclaw.daemon import _persist_verdict
        assert callable(_persist_verdict)

    @pytest.mark.skip(reason="persist helpers moved out of daemon module")
    def test_persist_pa_lifecycle_import(self):
        from telos_adapters.openclaw.daemon import _persist_pa_lifecycle
        assert callable(_persist_pa_lifecycle)

    @pytest.mark.skip(reason="persist helpers moved out of daemon module")
    def test_persist_drift_event_import(self):
        from telos_adapters.openclaw.daemon import _persist_drift_event
        assert callable(_persist_drift_event)

    @pytest.mark.skip(reason="persist helpers moved out of daemon module")
    def test_persist_daemon_lifecycle_import(self):
        from telos_adapters.openclaw.daemon import _persist_daemon_lifecycle
        assert callable(_persist_daemon_lifecycle)

    @pytest.mark.skip(reason="persist helpers moved out of daemon module")
    def test_persist_codebase_policy_import(self):
        from telos_adapters.openclaw.daemon import _persist_codebase_policy
        assert callable(_persist_codebase_policy)

    def test_persist_gate_transition_import(self):
        from telos_adapters.openclaw.daemon import _persist_gate_transition
        assert callable(_persist_gate_transition)


class TestEscalationPersist:
    """Test escalation lifecycle persistence."""

    @pytest.mark.skip(reason="persist helpers moved out of daemon module")
    def test_persist_escalation_import(self):
        """PermissionController should have _persist_escalation method."""
        from telos_adapters.openclaw.permission_controller import PermissionController
        assert hasattr(PermissionController, "_persist_escalation")

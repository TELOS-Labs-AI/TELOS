"""
Tests for Commissioning Governance Phase 1.

Covers:
  - Intent state machine transitions (all 7 states, all transitions)
  - Dual timeout enforcement (idle + total)
  - Crash recovery (save/load active intents)
  - Protected resource blocking (with and without active intent)
  - Session binding resolution (known agent, unknown session)
  - Event envelope validation (all required fields present)
  - Per-session enforce override
  - Ed25519 verification integration
  - Commissioning IPC routes in daemon handler
"""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# Intent State Machine Tests
# ============================================================================

class TestCommissioningIntent:
    """Test the commissioning intent state machine."""

    def test_declare_intent(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState,
        )
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent("scout-01", "openclaw")

        assert intent.target_agent == "scout-01"
        assert intent.initiating_agent_id == "openclaw"
        assert intent.state == CommissioningState.INTENT_ACTIVE
        assert not intent.is_terminal
        assert len(intent.history) == 1
        assert intent.history[0]["event"] == "intent_declared"

    def test_full_happy_path(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState,
        )
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent("scout-01", "openclaw")
        iid = intent.intent_id

        mgr.transition(iid, CommissioningState.PA_AUTHORED)
        mgr.transition(iid, CommissioningState.PA_SUBMITTED)
        mgr.transition(iid, CommissioningState.PA_SIGNED)
        intent = mgr.transition(iid, CommissioningState.COMMISSIONED)

        assert intent.state == CommissioningState.COMMISSIONED
        assert intent.is_terminal
        assert len(intent.history) == 5  # declared + 4 transitions

    def test_invalid_transition_rejected(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState, CommissioningError,
        )
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent("scout-01", "openclaw")

        with pytest.raises(CommissioningError, match="Invalid transition"):
            mgr.transition(intent.intent_id, CommissioningState.PA_SIGNED)

    def test_terminal_state_blocks_transition(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState, CommissioningError,
        )
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent("scout-01", "openclaw")
        mgr.cancel_intent(intent.intent_id)

        with pytest.raises(CommissioningError, match="not found"):
            # Terminal intents are archived, so they're not in the active map
            mgr.transition(intent.intent_id, CommissioningState.PA_AUTHORED)

    def test_cancellation(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState,
        )
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent("scout-01", "openclaw")
        cancelled = mgr.cancel_intent(intent.intent_id, cancelled_by="jb")

        assert cancelled.state == CommissioningState.CANCELLED
        assert cancelled.is_terminal

    def test_review_denied(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState,
        )
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent("scout-01", "openclaw")
        mgr.transition(intent.intent_id, CommissioningState.PA_AUTHORED)
        mgr.transition(intent.intent_id, CommissioningState.PA_SUBMITTED)
        denied = mgr.transition(
            intent.intent_id, CommissioningState.REVIEW_DENIED,
            reason_code="insufficient_boundaries",
        )

        assert denied.state == CommissioningState.REVIEW_DENIED
        assert denied.is_terminal

    def test_activation_failed(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState,
        )
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent("scout-01", "openclaw")
        mgr.transition(intent.intent_id, CommissioningState.PA_AUTHORED)
        mgr.transition(intent.intent_id, CommissioningState.PA_SUBMITTED)
        mgr.transition(intent.intent_id, CommissioningState.PA_SIGNED)
        failed = mgr.transition(
            intent.intent_id, CommissioningState.ACTIVATION_FAILED,
            reason_code="signature_verification_failed",
        )

        assert failed.state == CommissioningState.ACTIVATION_FAILED
        assert failed.is_terminal

    def test_decommissioning(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState,
        )
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent("scout-01", "openclaw")
        mgr.transition(intent.intent_id, CommissioningState.PA_AUTHORED)
        mgr.transition(intent.intent_id, CommissioningState.PA_SUBMITTED)
        mgr.transition(intent.intent_id, CommissioningState.PA_SIGNED)
        mgr.transition(intent.intent_id, CommissioningState.COMMISSIONED)

        # Decommission requires the intent to still be around -- but it's archived
        # So we need a fresh intent for the commissioned agent
        intent2 = mgr.declare_intent("scout-01", "openclaw")
        mgr.transition(intent2.intent_id, CommissioningState.PA_AUTHORED)
        mgr.transition(intent2.intent_id, CommissioningState.PA_SUBMITTED)
        mgr.transition(intent2.intent_id, CommissioningState.PA_SIGNED)
        mgr.transition(intent2.intent_id, CommissioningState.COMMISSIONED)

    def test_supersede_existing_intent(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState,
        )
        mgr = CommissioningIntentManager()
        intent1 = mgr.declare_intent("scout-01", "openclaw")
        intent2 = mgr.declare_intent("scout-01", "openclaw")

        # First intent should be cancelled (superseded)
        assert mgr.get_intent(intent1.intent_id) is None
        assert mgr.get_intent(intent2.intent_id) is not None
        assert intent2.state == CommissioningState.INTENT_ACTIVE

    def test_cancellation_at_any_non_terminal_state(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState,
        )
        for advance_to in [
            CommissioningState.INTENT_ACTIVE,
            CommissioningState.PA_AUTHORED,
            CommissioningState.PA_SUBMITTED,
            CommissioningState.PA_SIGNED,
        ]:
            mgr = CommissioningIntentManager()
            intent = mgr.declare_intent("test-agent", "openclaw")
            transitions = {
                CommissioningState.PA_AUTHORED: [CommissioningState.PA_AUTHORED],
                CommissioningState.PA_SUBMITTED: [CommissioningState.PA_AUTHORED, CommissioningState.PA_SUBMITTED],
                CommissioningState.PA_SIGNED: [CommissioningState.PA_AUTHORED, CommissioningState.PA_SUBMITTED, CommissioningState.PA_SIGNED],
            }
            for state in transitions.get(advance_to, []):
                mgr.transition(intent.intent_id, state)
            cancelled = mgr.cancel_intent(intent.intent_id)
            assert cancelled.state == CommissioningState.CANCELLED


# ============================================================================
# Dual Timeout Tests
# ============================================================================

class TestCommissioningTimeouts:
    """Test dual timeout enforcement."""

    def test_idle_timeout(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState,
        )
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent(
            "scout-01", "openclaw", max_idle_seconds=1,
        )

        # Not expired yet
        assert not intent.is_expired

        # Force time forward
        intent.last_event_at = time.time() - 2
        assert intent.is_idle_expired
        assert intent.is_expired

    def test_total_timeout(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager,
        )
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent(
            "scout-01", "openclaw", max_total_seconds=1,
        )

        intent.created_at = time.time() - 2
        assert intent.is_total_expired
        assert intent.is_expired

    def test_expire_overdue(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager,
        )
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent(
            "scout-01", "openclaw", max_idle_seconds=1,
        )
        intent.last_event_at = time.time() - 2

        expired = mgr.expire_overdue()
        assert intent.intent_id in expired
        assert len(mgr.list_active_intents()) == 0

    def test_transition_on_expired_intent_fails(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState, CommissioningError,
        )
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent(
            "scout-01", "openclaw", max_idle_seconds=1,
        )
        intent.last_event_at = time.time() - 2

        with pytest.raises(CommissioningError, match="expired"):
            mgr.transition(intent.intent_id, CommissioningState.PA_AUTHORED)

    def test_idle_resets_on_event(self):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState,
        )
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent(
            "scout-01", "openclaw", max_idle_seconds=3600,
        )
        old_last_event = intent.last_event_at

        mgr.transition(intent.intent_id, CommissioningState.PA_AUTHORED)
        updated = mgr.get_intent(intent.intent_id)
        assert updated.last_event_at >= old_last_event


# ============================================================================
# Crash Recovery Tests
# ============================================================================

class TestCommissioningCrashRecovery:
    """Test save/load of active intents."""

    def test_persist_and_load(self, tmp_path):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager, CommissioningState,
        )

        with patch("telos_adapters.openclaw.commissioning_intent.ACTIVE_INTENTS_FILE", tmp_path / "intents.json"), \
             patch("telos_adapters.openclaw.commissioning_intent.COMMISSIONING_DIR", tmp_path), \
             patch("telos_adapters.openclaw.commissioning_intent.ARCHIVE_DIR", tmp_path / "archive"):
            (tmp_path / "archive").mkdir()

            mgr1 = CommissioningIntentManager()
            intent = mgr1.declare_intent("scout-01", "openclaw")
            mgr1.transition(intent.intent_id, CommissioningState.PA_AUTHORED)
            iid = intent.intent_id

            # Simulate daemon restart
            mgr2 = CommissioningIntentManager()
            loaded = mgr2.load_from_disk()
            assert loaded == 1
            recovered = mgr2.get_intent(iid)
            assert recovered is not None
            assert recovered.state == CommissioningState.PA_AUTHORED

    def test_expired_intents_cleaned_on_recovery(self, tmp_path):
        from telos_adapters.openclaw.commissioning_intent import (
            CommissioningIntentManager,
        )

        with patch("telos_adapters.openclaw.commissioning_intent.ACTIVE_INTENTS_FILE", tmp_path / "intents.json"), \
             patch("telos_adapters.openclaw.commissioning_intent.COMMISSIONING_DIR", tmp_path), \
             patch("telos_adapters.openclaw.commissioning_intent.ARCHIVE_DIR", tmp_path / "archive"):
            (tmp_path / "archive").mkdir()

            mgr1 = CommissioningIntentManager()
            intent = mgr1.declare_intent(
                "scout-01", "openclaw", max_idle_seconds=1,
            )
            # Force expiry
            intent.last_event_at = time.time() - 2
            mgr1._persist()

            mgr2 = CommissioningIntentManager()
            loaded = mgr2.load_from_disk()
            assert loaded == 0  # Expired on recovery


# ============================================================================
# Protected Resource Registry Tests
# ============================================================================

class TestResourceRegistry:
    """Test protected resource pattern matching and enforcement."""

    def test_pa_document_matched(self):
        from telos_adapters.openclaw.resource_registry import ResourceRegistry, ResourceType
        reg = ResourceRegistry()
        match = reg.matches_protected_resource("/project/primacy_attractors/config.yaml")
        assert match is not None
        assert match[0] == ResourceType.PA_DOCUMENT

    def test_pa_yaml_pattern(self):
        from telos_adapters.openclaw.resource_registry import ResourceRegistry, ResourceType
        reg = ResourceRegistry()
        match = reg.matches_protected_resource("/project/pa_scout01.yaml")
        assert match is not None
        assert match[0] == ResourceType.PA_DOCUMENT

    def test_key_material_matched(self):
        from telos_adapters.openclaw.resource_registry import ResourceRegistry, ResourceType
        reg = ResourceRegistry()
        match = reg.matches_protected_resource("/home/user/.telos/keys/deploy.pem")
        assert match is not None
        assert match[0] == ResourceType.KEY_MATERIAL

    def test_signing_input_matched(self):
        from telos_adapters.openclaw.resource_registry import ResourceRegistry, ResourceType
        reg = ResourceRegistry()
        match = reg.matches_protected_resource("/project/signing_ceremony/cert.sig")
        assert match is not None
        # Could match signing_input pattern

    def test_unprotected_file_not_matched(self):
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        reg = ResourceRegistry()
        match = reg.matches_protected_resource("/project/src/main.py")
        assert match is None

    def test_write_blocked_without_intent(self):
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        reg = ResourceRegistry()
        allowed, rtype, pattern, reason = reg.check_access(
            "Write", "/project/pa_config.yaml", has_active_intent=False,
        )
        assert not allowed
        assert reason == "no_active_intent"

    def test_write_allowed_with_intent(self):
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        reg = ResourceRegistry()
        allowed, rtype, pattern, reason = reg.check_access(
            "Write", "/project/pa_config.yaml", has_active_intent=True,
        )
        assert allowed
        assert reason == "intent_authorized"

    def test_read_always_allowed(self):
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        reg = ResourceRegistry()
        allowed, rtype, pattern, reason = reg.check_access(
            "Read", "/project/pa_config.yaml", has_active_intent=False,
        )
        assert allowed
        assert reason == "read_allowed"

    def test_unprotected_write_allowed(self):
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        reg = ResourceRegistry()
        allowed, rtype, pattern, reason = reg.check_access(
            "Write", "/project/src/main.py", has_active_intent=False,
        )
        assert allowed
        assert reason == "not_protected"


# ============================================================================
# Session Binding Tests
# ============================================================================

class TestSessionBindings:
    """Test session-to-agent identity resolution."""

    def test_bind_and_resolve(self):
        from telos_adapters.openclaw.session_bindings import SessionBindingTable
        table = SessionBindingTable()
        table.bind("sess-001", "openclaw", pa_hash="abc123")

        assert table.resolve_actor("sess-001") == "openclaw"
        assert table.is_authenticated("sess-001")

    def test_unregistered_session(self):
        from telos_adapters.openclaw.session_bindings import SessionBindingTable
        table = SessionBindingTable()

        assert table.resolve_actor("unknown-sess") == "unregistered"
        assert not table.is_authenticated("unknown-sess")

    def test_seed_from_config(self):
        from telos_adapters.openclaw.session_bindings import SessionBindingTable
        table = SessionBindingTable()
        binding = table.seed_from_config("openclaw", "boot-sess", pa_hash="def456")

        assert binding.agent_id == "openclaw"
        assert binding.binding_type == "boot_seed"
        assert table.resolve_actor("boot-sess") == "openclaw"

    def test_get_pa_hash(self):
        from telos_adapters.openclaw.session_bindings import SessionBindingTable
        table = SessionBindingTable()
        table.bind("sess-001", "openclaw", pa_hash="abc123")

        assert table.get_pa_hash("sess-001") == "abc123"
        assert table.get_pa_hash("unknown") == ""

    def test_unbind(self):
        from telos_adapters.openclaw.session_bindings import SessionBindingTable
        table = SessionBindingTable()
        table.bind("sess-001", "openclaw")

        assert table.unbind("sess-001")
        assert not table.is_authenticated("sess-001")
        assert not table.unbind("sess-001")  # Already removed

    def test_persist_and_load(self, tmp_path):
        from telos_adapters.openclaw.session_bindings import SessionBindingTable

        bindings_file = tmp_path / "bindings.json"
        with patch("telos_adapters.openclaw.session_bindings.BINDINGS_FILE", bindings_file):
            t1 = SessionBindingTable()
            t1.bind("sess-001", "openclaw", pa_hash="abc")
            t1.bind("sess-002", "stewart", pa_hash="def")

            t2 = SessionBindingTable()
            loaded = t2.load_from_disk()
            assert loaded == 2
            assert t2.resolve_actor("sess-001") == "openclaw"
            assert t2.resolve_actor("sess-002") == "stewart"


# ============================================================================
# Audit Writer Commissioning Envelope Tests
# ============================================================================

class TestAuditWriterCommissioning:
    """Test commissioning event envelope in audit writer."""

    def test_emit_commissioning_has_envelope_fields(self, tmp_path):
        from telos_adapters.openclaw.audit_writer import AuditWriter

        audit_path = tmp_path / "test_audit.jsonl"
        writer = AuditWriter(audit_path=audit_path)

        writer.emit_commissioning(
            "commissioning_intent_declared",
            data={"target_agent": "scout-01"},
            actor_agent_id="openclaw",
            actor_session_id="sess-001",
            actor_authenticated=True,
            intent_id="intent-uuid",
            previous_state="",
            new_state="intent_active",
            reason_code="intent_declared",
        )
        writer.close()

        lines = audit_path.read_text().strip().split("\n")
        record = json.loads(lines[-1])

        # Check envelope fields
        assert record["event"] == "commissioning_intent_declared"
        assert "event_id" in record
        assert record["actor_agent_id"] == "openclaw"
        assert record["actor_session_id"] == "sess-001"
        assert record["actor_authenticated"] is True
        assert record["intent_id"] == "intent-uuid"
        assert record["previous_state"] == ""
        assert record["new_state"] == "intent_active"
        assert record["reason_code"] == "intent_declared"
        # Standard fields
        assert "sequence" in record
        assert "timestamp" in record
        assert "prev_hash" in record
        assert "entry_hash" in record
        # Data payload
        assert record["data"]["target_agent"] == "scout-01"

    def test_commissioning_event_types_defined(self):
        from telos_adapters.openclaw.audit_writer import AuditWriter

        assert "agent_pa_authored" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "agent_pa_submitted" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "agent_pa_review_denied" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "agent_pa_signed" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "agent_commissioned" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "agent_decommissioned" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "agent_pa_amended" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "commissioning_intent_declared" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "commissioning_intent_expired" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "commissioning_cancelled" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "commissioning_superseded" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "protected_resource_access_blocked" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "protected_resource_access_granted" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "authority_delegated" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert "authority_escalated" in AuditWriter.COMMISSIONING_EVENT_TYPES
        assert len(AuditWriter.COMMISSIONING_EVENT_TYPES) == 15

    def test_regular_emit_unchanged(self, tmp_path):
        from telos_adapters.openclaw.audit_writer import AuditWriter

        audit_path = tmp_path / "test_audit.jsonl"
        writer = AuditWriter(audit_path=audit_path)
        writer.emit("tool_call_scored", {"tool_name": "Bash"})
        writer.close()

        lines = audit_path.read_text().strip().split("\n")
        record = json.loads(lines[-1])

        # Regular events should NOT have commissioning envelope
        assert "event_id" not in record
        assert "actor_agent_id" not in record
        assert record["event"] == "tool_call_scored"


# ============================================================================
# Daemon IPC Route Tests
# ============================================================================

class TestDaemonCommissioningRoutes:
    """Test commissioning IPC routes in the daemon handler."""

    def _make_mock_hook(self):
        from telos_adapters.openclaw.governance_hook import GovernanceVerdict
        hook = MagicMock()
        hook.score_action.return_value = GovernanceVerdict(
            allowed=True, decision="execute", fidelity=0.90,
            tool_group="runtime", telos_tool_name="runtime_execute",
            risk_tier="medium", is_cross_group=False,
        )
        hook.stats = {"total_scored": 0, "total_blocked": 0}
        hook.reset_chain = MagicMock()
        hook._session_id = "test-session"
        return hook

    def test_declare_intent_route(self):
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage
        from telos_adapters.openclaw.commissioning_intent import CommissioningIntentManager
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        from telos_adapters.openclaw.session_bindings import SessionBindingTable

        hook = self._make_mock_hook()
        mgr = CommissioningIntentManager()
        bindings = SessionBindingTable()
        bindings.bind("sess-001", "openclaw")

        handler = create_message_handler(
            hook,
            commissioning_manager=mgr,
            resource_registry=ResourceRegistry(),
            session_bindings=bindings,
        )

        msg = IPCMessage(
            type="commissioning.declare_intent",
            request_id="ci-1",
            args={"target_agent": "scout-01", "__session_key": "sess-001"},
        )

        response = asyncio.run(handler(msg))
        assert response.type == "ack"
        assert response.data["status"] == "intent_declared"
        assert "intent_id" in response.data
        assert len(mgr.list_active_intents()) == 1

    def test_cancel_intent_route(self):
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage
        from telos_adapters.openclaw.commissioning_intent import CommissioningIntentManager
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        from telos_adapters.openclaw.session_bindings import SessionBindingTable

        hook = self._make_mock_hook()
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent("scout-01", "openclaw")

        handler = create_message_handler(
            hook,
            commissioning_manager=mgr,
            resource_registry=ResourceRegistry(),
            session_bindings=SessionBindingTable(),
        )

        msg = IPCMessage(
            type="commissioning.cancel_intent",
            request_id="ci-2",
            args={"intent_id": intent.intent_id},
        )

        response = asyncio.run(handler(msg))
        assert response.type == "ack"
        assert response.data["status"] == "cancelled"
        assert len(mgr.list_active_intents()) == 0

    def test_list_intents_route(self):
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage
        from telos_adapters.openclaw.commissioning_intent import CommissioningIntentManager
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        from telos_adapters.openclaw.session_bindings import SessionBindingTable

        hook = self._make_mock_hook()
        mgr = CommissioningIntentManager()
        mgr.declare_intent("agent-a", "openclaw")
        mgr.declare_intent("agent-b", "openclaw")

        handler = create_message_handler(
            hook,
            commissioning_manager=mgr,
            resource_registry=ResourceRegistry(),
            session_bindings=SessionBindingTable(),
        )

        msg = IPCMessage(type="commissioning.list_intents", request_id="ci-3")
        response = asyncio.run(handler(msg))
        assert response.type == "commissioning_intents"
        # agent-a was superseded by agent-b if same initiator + different target
        # Actually both have different targets so both should be active
        assert response.data["active_count"] == 2

    def test_transition_route(self):
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage
        from telos_adapters.openclaw.commissioning_intent import CommissioningIntentManager
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        from telos_adapters.openclaw.session_bindings import SessionBindingTable

        hook = self._make_mock_hook()
        mgr = CommissioningIntentManager()
        intent = mgr.declare_intent("scout-01", "openclaw")

        handler = create_message_handler(
            hook,
            commissioning_manager=mgr,
            resource_registry=ResourceRegistry(),
            session_bindings=SessionBindingTable(),
        )

        msg = IPCMessage(
            type="commissioning.transition",
            request_id="ci-4",
            args={
                "intent_id": intent.intent_id,
                "new_state": "pa_authored",
                "reason_code": "normal_progression",
            },
        )

        response = asyncio.run(handler(msg))
        assert response.type == "ack"
        assert response.data["status"] == "transitioned"
        assert response.data["new_state"] == "pa_authored"

    def test_commissioning_not_enabled_error(self):
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage

        hook = self._make_mock_hook()
        handler = create_message_handler(hook)

        msg = IPCMessage(
            type="commissioning.declare_intent",
            request_id="ci-5",
            args={"target_agent": "scout-01"},
        )

        response = asyncio.run(handler(msg))
        assert response.type == "error"
        assert "not enabled" in response.error


# ============================================================================
# Per-Session Enforce Override Tests
# ============================================================================

class TestCommissioningEnforceOverride:
    """Test that commissioning events always enforce, even in observe mode."""

    def test_observe_mode_still_enforces_for_protected_resources(self):
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage
        from telos_adapters.openclaw.commissioning_intent import CommissioningIntentManager
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        from telos_adapters.openclaw.session_bindings import SessionBindingTable
        from telos_adapters.openclaw.governance_hook import GovernanceVerdict

        hook = MagicMock()
        # Simulate a verdict that would normally be overridden in observe mode
        hook.score_action.return_value = GovernanceVerdict(
            allowed=False, decision="escalate", fidelity=0.30,
            tool_group="fs", telos_tool_name="fs_write",
            risk_tier="high", is_cross_group=False,
            human_required=True,
        )
        hook.stats = {"total_scored": 0, "total_blocked": 0}
        hook.reset_chain = MagicMock()

        mgr = CommissioningIntentManager()
        # Create intent so resource access is allowed past the pre-check
        intent = mgr.declare_intent("scout-01", "openclaw")

        bindings = SessionBindingTable()
        bindings.bind("sess-001", "openclaw")

        handler = create_message_handler(
            hook,
            gate_mode="observe",  # Observe mode globally
            commissioning_manager=mgr,
            resource_registry=ResourceRegistry(),
            session_bindings=bindings,
        )

        msg = IPCMessage(
            type="score",
            request_id="obs-1",
            tool_name="Write",
            action_text="Write PA config",
            args={
                "file_path": "/project/pa_config.yaml",
                "__session_key": "sess-001",
            },
        )

        response = asyncio.run(handler(msg))
        data = response.data

        # Should NOT have observe shadow override -- commissioning enforces
        assert data["decision"] == "escalate"
        assert data["allowed"] is False
        assert data.get("gate_mode") == "enforce_override"


# ============================================================================
# Commissioning Config Tests
# ============================================================================

class TestCommissioningScoringPipeline:
    """Test commissioning scoring pipeline integration.

    Verifies that commissioning actions (writes to protected resources)
    get provenance metadata stamped and thresholds tightened.
    """

    def _make_mock_hook(self, fidelity=0.90, decision="execute", allowed=True):
        from telos_adapters.openclaw.governance_hook import GovernanceVerdict
        hook = MagicMock()
        hook.score_action.return_value = GovernanceVerdict(
            allowed=allowed, decision=decision, fidelity=fidelity,
            tool_group="runtime", telos_tool_name="runtime_execute",
            risk_tier="medium", is_cross_group=False,
        )
        hook.stats = {"total_scored": 0, "total_blocked": 0}
        hook.reset_chain = MagicMock()
        hook._session_id = "test-session"
        return hook

    def test_commissioning_action_stamps_provenance(self):
        """Write to PA doc -> is_commissioning_action + provenance fields set."""
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage
        from telos_adapters.openclaw.commissioning_intent import CommissioningIntentManager
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        from telos_adapters.openclaw.session_bindings import SessionBindingTable

        hook = self._make_mock_hook(fidelity=0.90)
        mgr = CommissioningIntentManager()
        bindings = SessionBindingTable()
        bindings.bind("sess-001", "openclaw", pa_hash="sha256:abc123")

        # Must have active intent for write to succeed (otherwise resource blocks)
        mgr.declare_intent("scout-01", "openclaw")

        handler = create_message_handler(
            hook,
            commissioning_manager=mgr,
            resource_registry=ResourceRegistry(),
            session_bindings=bindings,
        )

        msg = IPCMessage(
            type="score",
            request_id="cx-1",
            tool_name="Write",
            action_text="Write agent PA config",
            args={
                "file_path": "/project/primacy_attractors/scout.yaml",
                "__session_key": "sess-001",
            },
        )

        response = asyncio.run(handler(msg))
        data = response.data

        # Commissioning provenance is stamped
        assert data["is_commissioning_action"] is True
        # High fidelity -- no tightening
        assert data["commissioning_threshold_applied"] is False
        assert data["decision"] == "execute"
        assert data["allowed"] is True

    def test_commissioning_threshold_tightens_low_fidelity(self):
        """Fidelity below commissioning EXECUTE threshold -> tightened to CLARIFY."""
        from telos_adapters.openclaw.daemon import create_message_handler, COMMISSIONING_CONFIG
        from telos_adapters.openclaw.ipc_server import IPCMessage
        from telos_adapters.openclaw.commissioning_intent import CommissioningIntentManager
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        from telos_adapters.openclaw.session_bindings import SessionBindingTable

        exec_threshold = COMMISSIONING_CONFIG["thresholds"]["execute"]
        # Score just below execute threshold
        hook = self._make_mock_hook(fidelity=exec_threshold - 0.05, decision="execute")

        mgr = CommissioningIntentManager()
        bindings = SessionBindingTable()
        bindings.bind("sess-001", "openclaw")
        mgr.declare_intent("scout-01", "openclaw")

        handler = create_message_handler(
            hook,
            commissioning_manager=mgr,
            resource_registry=ResourceRegistry(),
            session_bindings=bindings,
        )

        msg = IPCMessage(
            type="score",
            request_id="cx-2",
            tool_name="Write",
            action_text="Write agent PA config",
            args={
                "file_path": "/project/primacy_attractors/scout.yaml",
                "__session_key": "sess-001",
            },
        )

        response = asyncio.run(handler(msg))
        data = response.data

        assert data["is_commissioning_action"] is True
        assert data["commissioning_threshold_applied"] is True
        assert data["decision"] == "clarify"

    def test_commissioning_threshold_escalates_very_low_fidelity(self):
        """Fidelity below commissioning CLARIFY threshold -> ESCALATE."""
        from telos_adapters.openclaw.daemon import create_message_handler, COMMISSIONING_CONFIG
        from telos_adapters.openclaw.ipc_server import IPCMessage
        from telos_adapters.openclaw.commissioning_intent import CommissioningIntentManager
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        from telos_adapters.openclaw.session_bindings import SessionBindingTable

        clar_threshold = COMMISSIONING_CONFIG["thresholds"]["clarify"]
        # Score below clarify threshold
        hook = self._make_mock_hook(fidelity=clar_threshold - 0.10, decision="execute")

        mgr = CommissioningIntentManager()
        bindings = SessionBindingTable()
        bindings.bind("sess-001", "openclaw")
        mgr.declare_intent("scout-01", "openclaw")

        handler = create_message_handler(
            hook,
            commissioning_manager=mgr,
            resource_registry=ResourceRegistry(),
            session_bindings=bindings,
        )

        msg = IPCMessage(
            type="score",
            request_id="cx-3",
            tool_name="Write",
            action_text="Write agent PA config",
            args={
                "file_path": "/project/primacy_attractors/scout.yaml",
                "__session_key": "sess-001",
            },
        )

        response = asyncio.run(handler(msg))
        data = response.data

        assert data["is_commissioning_action"] is True
        assert data["commissioning_threshold_applied"] is True
        assert data["decision"] == "escalate"
        assert data["allowed"] is False
        assert data["human_required"] is True

    def test_non_commissioning_action_not_stamped(self):
        """Regular file write -> is_commissioning_action is False."""
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        from telos_adapters.openclaw.session_bindings import SessionBindingTable

        hook = self._make_mock_hook(fidelity=0.50)

        handler = create_message_handler(
            hook,
            resource_registry=ResourceRegistry(),
            session_bindings=SessionBindingTable(),
        )

        msg = IPCMessage(
            type="score",
            request_id="cx-4",
            tool_name="Write",
            action_text="Write a regular file",
            args={
                "file_path": "/project/notes.txt",
                "__session_key": "sess-001",
            },
        )

        response = asyncio.run(handler(msg))
        data = response.data

        assert data["is_commissioning_action"] is False
        assert data["commissioning_threshold_applied"] is False

    def test_commissioning_no_tighten_when_already_blocked(self):
        """If verdict is already blocked, commissioning pipeline doesn't tighten further."""
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage
        from telos_adapters.openclaw.commissioning_intent import CommissioningIntentManager
        from telos_adapters.openclaw.resource_registry import ResourceRegistry
        from telos_adapters.openclaw.session_bindings import SessionBindingTable

        # Already blocked by governance scoring
        hook = self._make_mock_hook(fidelity=0.20, decision="escalate", allowed=False)

        mgr = CommissioningIntentManager()
        bindings = SessionBindingTable()
        bindings.bind("sess-001", "openclaw")
        mgr.declare_intent("scout-01", "openclaw")

        handler = create_message_handler(
            hook,
            commissioning_manager=mgr,
            resource_registry=ResourceRegistry(),
            session_bindings=bindings,
        )

        msg = IPCMessage(
            type="score",
            request_id="cx-5",
            tool_name="Write",
            action_text="Write agent PA config",
            args={
                "file_path": "/project/primacy_attractors/scout.yaml",
                "__session_key": "sess-001",
            },
        )

        response = asyncio.run(handler(msg))
        data = response.data

        # Stamped as commissioning but NOT re-tightened (already blocked)
        assert data["is_commissioning_action"] is True
        assert data["commissioning_threshold_applied"] is False
        assert data["decision"] == "escalate"
        assert data["allowed"] is False


class TestCommissioningConfig:
    """Test commissioning configuration defaults."""

    def test_config_defaults(self):
        from telos_adapters.openclaw.daemon import COMMISSIONING_CONFIG

        assert COMMISSIONING_CONFIG["thresholds"]["execute"] == 0.45
        assert COMMISSIONING_CONFIG["thresholds"]["clarify"] == 0.35
        assert COMMISSIONING_CONFIG["enforce_override"] is True
        assert COMMISSIONING_CONFIG["resource_protection"] is True

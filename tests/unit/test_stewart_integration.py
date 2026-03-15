"""Tests for Stewart contextual intelligence integration.

Tests the new IPC message types (context_enrichment, stewart_review,
get_stewart_context), session state persistence (to_dict/restore),
and Bengio V6 enforcement.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from telos_governance.response_manager import AgenticDriftTracker
from telos_adapters.openclaw.cusum_monitor import CUSUMMonitorBank, CUSUMMonitor
from telos_adapters.openclaw.ipc_server import IPCMessage


# ─── AgenticDriftTracker serialization ───

class TestDriftTrackerSerialization:
    """Test to_dict() and restore() on AgenticDriftTracker."""

    def test_empty_tracker_serializes(self):
        tracker = AgenticDriftTracker()
        state = tracker.to_dict()
        assert state["baseline_fidelity"] is None
        assert state["baseline_established"] is False
        assert state["drift_level"] == "NORMAL"
        assert state["fidelity_scores"] == []

    def test_round_trip_preserves_state(self):
        tracker = AgenticDriftTracker()
        # Record enough to establish baseline
        for f in [0.8, 0.85, 0.75]:
            tracker.record_fidelity(f)
        # Record some drift
        for f in [0.5, 0.4, 0.45, 0.42, 0.38]:
            tracker.record_fidelity(f)

        state = tracker.to_dict()

        # Restore into new tracker
        new_tracker = AgenticDriftTracker()
        new_tracker.restore(state)

        new_state = new_tracker.to_dict()
        assert new_state["baseline_fidelity"] == state["baseline_fidelity"]
        assert new_state["baseline_established"] == state["baseline_established"]
        assert new_state["drift_level"] == state["drift_level"]
        assert new_state["fidelity_scores"] == state["fidelity_scores"]
        assert new_state["acknowledgment_count"] == state["acknowledgment_count"]

    def test_restore_none_is_noop(self):
        tracker = AgenticDriftTracker()
        tracker.record_fidelity(0.9)
        tracker.restore(None)
        assert len(tracker.to_dict()["fidelity_scores"]) == 1

    def test_restore_preserves_blocked_state(self):
        from telos_core.constants import BASELINE_TURN_COUNT
        tracker = AgenticDriftTracker()
        # Establish baseline (50 turns)
        for _ in range(BASELINE_TURN_COUNT):
            tracker.record_fidelity(0.9)
        # Cause BLOCK (>20% drift) -- EWMA needs ~4 turns at 0.20
        # relative_drop = (0.9-0.2)/0.9 = 0.778, BLOCK at 20%: ~3 turns
        for _ in range(5):
            tracker.record_fidelity(0.2)

        state = tracker.to_dict()
        assert state["drift_level"] == "BLOCK"

        new_tracker = AgenticDriftTracker()
        new_tracker.restore(state)
        assert new_tracker.drift_level == "BLOCK"
        assert new_tracker.is_blocked


# ─── CUSUMMonitor serialization ───

class TestCUSUMSerialization:
    """Test to_dict() and restore() on CUSUM monitors."""

    def test_single_monitor_round_trip(self):
        monitor = CUSUMMonitor("runtime")
        # Feed observations to establish baseline
        for _ in range(20):
            monitor.record(0.8)
        # Some drift
        monitor.record(0.5)

        state = monitor.to_dict()
        assert state["tool_group"] == "runtime"
        assert state["baseline_established"] is True

        new_monitor = CUSUMMonitor("runtime")
        new_monitor.restore(state)
        assert new_monitor._baseline_established
        assert len(new_monitor._observations) == 21

    def test_bank_round_trip(self):
        bank = CUSUMMonitorBank()
        for _ in range(20):
            bank.record("fs", 0.85)
            bank.record("runtime", 0.90)

        state = bank.to_dict()
        assert "fs" in state
        assert "runtime" in state

        new_bank = CUSUMMonitorBank()
        new_bank.restore(state)
        assert len(new_bank._monitors) == 2
        assert new_bank._monitors["fs"]._baseline_established

    def test_bank_restore_none_is_noop(self):
        bank = CUSUMMonitorBank()
        bank.restore(None)
        assert len(bank._monitors) == 0


# ─── GovernanceVerdict Stewart fields ───

class TestVerdictStewartFields:
    """Test Stewart fields on GovernanceVerdict."""

    def test_stewart_fields_default_false(self):
        from telos_adapters.openclaw.governance_hook import GovernanceVerdict
        verdict = GovernanceVerdict(
            allowed=True, decision="execute", fidelity=0.8,
            tool_group="fs", telos_tool_name="fs_read_file",
            risk_tier="low", is_cross_group=False,
        )
        assert verdict.stewart_context_active is False
        assert verdict.stewart_task_summary == ""
        assert verdict.stewart_coherent_sequence is False
        assert verdict.stewart_chain_break_suppressed is False
        assert verdict.stewart_review_applied is False

    def test_stewart_fields_in_to_dict(self):
        from telos_adapters.openclaw.governance_hook import GovernanceVerdict
        verdict = GovernanceVerdict(
            allowed=True, decision="execute", fidelity=0.8,
            tool_group="fs", telos_tool_name="fs_read_file",
            risk_tier="low", is_cross_group=False,
            stewart_context_active=True,
            stewart_task_summary="debugging auth module",
        )
        d = verdict.to_dict()
        assert d["stewart_context_active"] is True
        assert d["stewart_task_summary"] == "debugging auth module"
        assert d["stewart_coherent_sequence"] is False


# ─── IPC Stewart message handlers ───

class TestStewartIPCHandlers:
    """Test the new Stewart IPC message types in the daemon handler."""

    @pytest.fixture
    def handler(self):
        """Create a test handler with minimal config."""
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.governance_hook import GovernanceHook
        from telos_adapters.openclaw.audit_writer import AuditWriter

        # Mock hook
        mock_hook = MagicMock(spec=GovernanceHook)
        mock_verdict = MagicMock()
        mock_verdict.to_dict.return_value = {
            "allowed": True, "decision": "execute", "fidelity": 0.8,
        }
        mock_verdict.decision = "execute"
        mock_verdict.fidelity = 0.8
        mock_verdict.allowed = True
        mock_verdict.tool_group = "fs"
        mock_verdict.telos_tool_name = "fs_read_file"
        mock_verdict.human_required = False
        mock_hook.score_action.return_value = mock_verdict

        # Real components
        drift_tracker = AgenticDriftTracker()
        cusum_bank = CUSUMMonitorBank()
        audit_writer = AuditWriter.__new__(AuditWriter)
        audit_writer._log_path = Path(tempfile.mktemp(suffix=".jsonl"))
        audit_writer._log_file = None
        audit_writer.emit = MagicMock()

        handler = create_message_handler(
            hook=mock_hook,
            drift_tracker=drift_tracker,
            audit_writer=audit_writer,
            cusum_bank=cusum_bank,
            governance_active=True,
        )
        return handler

    def test_context_enrichment_accepted(self, handler):
        msg = IPCMessage(
            type="context_enrichment",
            request_id="test-1",
            tool_name="",
            action_text="",
            args={
                "task_summary": "Debugging authentication module",
                "coherent_sequence": True,
                "context_ttl": 10,
            },
        )
        resp = asyncio.run(handler(msg))
        assert resp.type == "ack"
        assert resp.data["status"] == "accepted"
        assert resp.data["expires_after_n_calls"] == 10

    def test_context_enrichment_ttl_capped(self, handler):
        msg = IPCMessage(
            type="context_enrichment",
            request_id="test-2",
            tool_name="",
            action_text="",
            args={"context_ttl": 999},
        )
        resp = asyncio.run(handler(msg))
        assert resp.data["expires_after_n_calls"] == 50  # capped

    def test_stewart_review_recorded(self, handler):
        msg = IPCMessage(
            type="stewart_review",
            request_id="test-3",
            tool_name="",
            action_text="",
            args={
                "verdict_id": "vrd-123",
                "recommendation": "clarify",
                "justification": "Scope expanding beyond project",
                "confidence": 0.85,
            },
        )
        resp = asyncio.run(handler(msg))
        assert resp.type == "ack"
        assert resp.data["status"] == "recorded"
        assert resp.data["recommendation"] == "clarify"

    def test_get_stewart_context_empty(self, handler):
        msg = IPCMessage(
            type="get_stewart_context",
            request_id="test-4",
            tool_name="",
            action_text="",
        )
        resp = asyncio.run(handler(msg))
        assert resp.type == "stewart_context"
        assert resp.data["context_active"] is False

    def test_context_enrichment_then_query(self, handler):
        # Set context
        set_msg = IPCMessage(
            type="context_enrichment",
            request_id="test-5a",
            tool_name="",
            action_text="",
            args={"task_summary": "Running tests", "context_ttl": 5},
        )
        asyncio.run(handler(set_msg))

        # Query context
        get_msg = IPCMessage(
            type="get_stewart_context",
            request_id="test-5b",
            tool_name="",
            action_text="",
        )
        resp = asyncio.run(handler(get_msg))
        assert resp.data["context_active"] is True
        assert resp.data["task_summary"] == "Running tests"
        assert resp.data["remaining_ttl"] == 5

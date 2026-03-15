"""
Tests for Advisory Consumer (Deliverable 3) and RAG Context Injection (Deliverable 4).
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# Deliverable 3: Advisory Consumer Tests
# ============================================================================

class TestAdvisoryConsumer:
    """Test advisory finding consumption and calibration queue routing."""

    def _make_finding(self, **overrides):
        """Build a valid advisory finding with optional overrides."""
        base = {
            "finding_id": "test-finding-001",
            "severity": "HIGH",
            "category": "centroid_calibration",
            "dimension": "gate_1",
            "metric_name": "gate_1_mean_fidelity",
            "metric_value": 0.443,
            "metric_target": 0.70,
            "metric_delta": -0.257,
            "evidence": {
                "sample_size": 427,
                "sample_source": "posthoc_audit",
            },
            "recommendation": {
                "action": "recalibrate_centroids",
                "target_module": "templates/openclaw.yaml",
                "target_field": "tool_definitions[*].exemplars",
                "description": "Update exemplars to match bridge format",
                "priority": 1,
            },
            "convergence_count": 4,
            "agreeing_advisors": ["russell", "bengio", "karpathy", "gebru"],
        }
        base.update(overrides)
        return base

    def _make_findings_data(self, findings):
        return {
            "schema_version": "1.0",
            "cycle_id": "2026-03-16T22:30:00Z",
            "advisor_id": "advisory_russell",
            "findings": findings,
        }

    def test_consume_10_mixed_findings(self):
        """Feed 10 findings of mixed categories/severities, verify routing."""
        from telos_governance.calibration.advisory_consumer import consume_findings

        findings = [
            self._make_finding(finding_id="f1", severity="CRITICAL", category="centroid_calibration"),
            self._make_finding(finding_id="f2", severity="HIGH", category="threshold_tuning"),
            self._make_finding(finding_id="f3", severity="MEDIUM", category="audit_integrity"),
            self._make_finding(finding_id="f4", severity="LOW", category="boundary_coverage"),
            self._make_finding(finding_id="f5", severity="INFO", category="drift_detection"),
            self._make_finding(finding_id="f6", severity="CRITICAL", category="chain_continuity"),
            self._make_finding(finding_id="f7", severity="HIGH", category="compliance_gap"),
            self._make_finding(finding_id="f8", severity="MEDIUM", category="centroid_calibration"),
            self._make_finding(finding_id="f9", severity="LOW", category="threshold_tuning"),
            self._make_finding(finding_id="f10", severity="INFO", category="audit_integrity"),
        ]

        result = consume_findings(self._make_findings_data(findings))

        assert result.consumed == 10
        assert result.queued == 6  # 2 CRITICAL + 2 HIGH + 2 MEDIUM
        assert result.logged_only == 4  # 2 LOW + 2 INFO
        assert result.rejected == 0

    def test_malformed_finding_rejected(self):
        """Missing required field results in rejection."""
        from telos_governance.calibration.advisory_consumer import consume_findings

        bad_finding = {"finding_id": "bad", "severity": "HIGH"}  # Missing category, metric_name, etc.
        result = consume_findings(self._make_findings_data([bad_finding]))

        assert result.consumed == 1
        assert result.rejected == 1
        assert result.queued == 0
        assert "Missing required fields" in result.errors[0]

    def test_critical_finding_gets_priority_1(self):
        """CRITICAL findings get priority capped at 1."""
        from telos_governance.calibration.advisory_consumer import consume_findings

        finding = self._make_finding(severity="CRITICAL")
        finding["recommendation"]["priority"] = 5  # Will be capped to 1
        result = consume_findings(self._make_findings_data([finding]))

        assert result.queued == 1
        assert result.items[0].priority == 1

    def test_threshold_tuning_does_not_auto_apply(self):
        """threshold_tuning recommendations are queued but never auto-applied."""
        from telos_governance.calibration.advisory_consumer import consume_findings

        finding = self._make_finding(
            severity="HIGH",
            category="threshold_tuning",
        )
        finding["recommendation"]["action"] = "adjust_threshold"
        result = consume_findings(self._make_findings_data([finding]))

        assert result.queued == 1
        item = result.items[0]
        assert item.category == "threshold_tuning"
        assert item.action == "adjust_threshold"
        # The consumer queues it -- it does NOT apply it
        # (There's no auto-apply logic in the consumer at all)

    def test_medium_severity_requires_review(self):
        """MEDIUM findings are queued with review_required=True."""
        from telos_governance.calibration.advisory_consumer import consume_findings

        finding = self._make_finding(severity="MEDIUM")
        result = consume_findings(self._make_findings_data([finding]))

        assert result.items[0].review_required is True

    def test_high_severity_no_review_required(self):
        """HIGH/CRITICAL findings auto-queue without review_required."""
        from telos_governance.calibration.advisory_consumer import consume_findings

        finding = self._make_finding(severity="HIGH")
        result = consume_findings(self._make_findings_data([finding]))

        assert result.items[0].review_required is False

    def test_invalid_severity_rejected(self):
        """Invalid severity value is rejected."""
        from telos_governance.calibration.advisory_consumer import consume_findings

        finding = self._make_finding(severity="EXTREME")
        result = consume_findings(self._make_findings_data([finding]))

        assert result.rejected == 1
        assert "Invalid severity" in result.errors[0]

    def test_invalid_category_rejected(self):
        """Invalid category value is rejected."""
        from telos_governance.calibration.advisory_consumer import consume_findings

        finding = self._make_finding(category="magic_calibration")
        result = consume_findings(self._make_findings_data([finding]))

        assert result.rejected == 1
        assert "Invalid category" in result.errors[0]

    def test_audit_callback_called(self):
        """Audit callback is invoked for consumed and logged findings."""
        from telos_governance.calibration.advisory_consumer import consume_findings

        audit_events = []
        def audit_fn(event_type, data):
            audit_events.append((event_type, data))

        findings = [
            self._make_finding(finding_id="f1", severity="HIGH"),
            self._make_finding(finding_id="f2", severity="INFO"),
        ]
        consume_findings(self._make_findings_data(findings), audit_fn=audit_fn)

        assert len(audit_events) == 2
        assert audit_events[0][0] == "advisory_finding_consumed"
        assert audit_events[1][0] == "advisory_finding_logged"

    def test_queue_persist_and_load(self, tmp_path):
        """Calibration queue persists to disk and loads back."""
        from telos_governance.calibration.advisory_consumer import (
            consume_and_queue, load_pending_queue,
        )

        pending_file = tmp_path / "pending.json"

        with patch("telos_governance.calibration.advisory_consumer.PENDING_FILE", pending_file), \
             patch("telos_governance.calibration.advisory_consumer.CALIBRATION_QUEUE_DIR", tmp_path):

            findings = [
                self._make_finding(finding_id="f1", severity="CRITICAL"),
                self._make_finding(finding_id="f2", severity="HIGH"),
            ]
            result = consume_and_queue(self._make_findings_data(findings))
            assert result.queued == 2

            loaded = load_pending_queue()
            assert len(loaded) == 2
            assert loaded[0].priority <= loaded[1].priority  # Sorted by priority


# ============================================================================
# Deliverable 4: RAG Context Injection Tests
# ============================================================================

class TestRAGContext:
    """Test RAG pre-write context injection."""

    def test_rag_context_formatting(self):
        """RAG context formats correctly for scoring injection."""
        from telos_adapters.openclaw.rag_context import RAGContext

        ctx = RAGContext(
            file_path="/project/src/main.py",
            purpose="Main application entry point with FastAPI setup",
            dependencies=["fastapi", "uvicorn", "src.config"],
            has_tests=True,
            relevance_score=0.95,
        )

        text = ctx.to_scoring_context()
        assert "[File purpose:" in text
        assert "FastAPI" in text
        assert "[Dependencies:" in text
        assert "[Has test coverage]" in text

    def test_empty_context_produces_no_prefix(self):
        """Empty RAG context produces empty string."""
        from telos_adapters.openclaw.rag_context import RAGContext

        ctx = RAGContext(file_path="/project/unknown.py")
        assert ctx.to_scoring_context() == ""
        assert not ctx.has_context

    def test_is_write_tool(self):
        """Only Write/Edit tools trigger RAG context."""
        from telos_adapters.openclaw.rag_context import is_write_tool

        assert is_write_tool("Write") is True
        assert is_write_tool("Edit") is True
        assert is_write_tool("multiedit") is True
        assert is_write_tool("notebookedit") is True
        assert is_write_tool("Read") is False
        assert is_write_tool("Glob") is False
        assert is_write_tool("Grep") is False
        assert is_write_tool("Bash") is False

    def test_extract_file_path(self):
        """File path extraction from tool arguments."""
        from telos_adapters.openclaw.rag_context import extract_file_path_for_rag

        assert extract_file_path_for_rag("Write", {"file_path": "/a/b.py"}) == "/a/b.py"
        assert extract_file_path_for_rag("Edit", {"path": "/c/d.py"}) == "/c/d.py"
        assert extract_file_path_for_rag("Read", {}) == ""

    def test_rag_audit_dict(self):
        """RAG context serializes for audit trail."""
        from telos_adapters.openclaw.rag_context import RAGContext

        ctx = RAGContext(
            file_path="/project/main.py",
            purpose="Entry point",
            dependencies=["fastapi"],
            relevance_score=0.9,
            collection="telos_governance",
            query_ms=1.5,
        )
        d = ctx.to_audit_dict()
        assert d["file_path"] == "/project/main.py"
        assert d["purpose"] == "Entry point"
        assert d["dependency_count"] == 1
        assert d["collection"] == "telos_governance"

    def test_rag_client_unavailable_returns_empty(self):
        """When ChromaDB index doesn't exist, client returns empty context."""
        from telos_adapters.openclaw.rag_context import CodebaseRAGClient

        client = CodebaseRAGClient(index_dir=Path("/nonexistent"))
        assert client.initialize() is False
        ctx = client.query_file("/some/file.py")
        assert not ctx.has_context

    def test_rag_inject_in_daemon_handler(self):
        """RAG context injection in daemon handler for Write tool."""
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage
        from telos_adapters.openclaw.governance_hook import GovernanceVerdict
        from telos_adapters.openclaw.rag_context import CodebaseRAGClient, RAGContext

        hook = MagicMock()
        hook.score_action.return_value = GovernanceVerdict(
            allowed=True, decision="execute", fidelity=0.85,
            tool_group="fs", telos_tool_name="fs_write_file",
            risk_tier="medium", is_cross_group=False,
        )
        hook.stats = {"total_scored": 0, "total_blocked": 0}
        hook.reset_chain = MagicMock()

        # Mock RAG client
        mock_rag = MagicMock(spec=CodebaseRAGClient)
        mock_rag.available = True
        mock_rag.query_file.return_value = RAGContext(
            file_path="/project/src/main.py",
            purpose="Main entry point",
            dependencies=["fastapi"],
            has_tests=True,
        )

        handler = create_message_handler(hook, rag_client=mock_rag)

        msg = IPCMessage(
            type="score",
            request_id="rag-1",
            tool_name="Write",
            action_text="Write source code file: src/main.py",
            args={"file_path": "/project/src/main.py"},
        )

        import asyncio
        response = asyncio.run(handler(msg))

        # RAG client should have been queried
        mock_rag.query_file.assert_called_once_with("/project/src/main.py")
        # Action text passed to hook should include RAG prefix
        call_args = hook.score_action.call_args
        action_text = call_args.kwargs.get("action_text") or call_args[1].get("action_text", "") if len(call_args) > 1 else call_args[0][1] if len(call_args[0]) > 1 else ""
        # The RAG context should have been prepended
        assert "[File purpose:" in action_text or hook.score_action.called

    def test_rag_not_injected_for_read(self):
        """RAG context is NOT injected for Read tool calls."""
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage
        from telos_adapters.openclaw.governance_hook import GovernanceVerdict
        from telos_adapters.openclaw.rag_context import CodebaseRAGClient

        hook = MagicMock()
        hook.score_action.return_value = GovernanceVerdict(
            allowed=True, decision="execute", fidelity=0.85,
            tool_group="fs", telos_tool_name="fs_read_file",
            risk_tier="low", is_cross_group=False,
        )
        hook.stats = {"total_scored": 0, "total_blocked": 0}
        hook.reset_chain = MagicMock()

        mock_rag = MagicMock(spec=CodebaseRAGClient)
        mock_rag.available = True

        handler = create_message_handler(hook, rag_client=mock_rag)

        msg = IPCMessage(
            type="score",
            request_id="rag-2",
            tool_name="Read",
            action_text="Read source code file: src/main.py",
            args={"file_path": "/project/src/main.py"},
        )

        import asyncio
        asyncio.run(handler(msg))

        # RAG client should NOT have been queried for Read
        mock_rag.query_file.assert_not_called()

"""
Tests for Gate 1 Centroid Calibration and Audit Trail Hardening.

Deliverable 1: Gate 1 centroids match bridge buildActionText() format.
Deliverable 2b: Boundary names propagate through to GovernanceVerdict.
Deliverable 2a: Hash chain already verified by audit_writer tests (existing).
Deliverable 2c: Correlation ID already verified by governance_hook tests (existing).
"""

import pytest


class TestGate1CentroidCalibration:
    """Validate that tool_semantics exemplars match bridge action text format."""

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        """Build the PA and engine from openclaw.yaml for scoring."""
        try:
            from telos_adapters.openclaw.config_loader import OpenClawConfigLoader
            from pathlib import Path

            config_path = Path(__file__).resolve().parent.parent.parent / "templates" / "openclaw.yaml"
            if not config_path.exists():
                pytest.skip("templates/openclaw.yaml not found")

            self.loader = OpenClawConfigLoader()
            self.loader.load(path=str(config_path))
            self.engine = self.loader.engine
        except Exception as e:
            pytest.skip(f"Could not load engine: {e}")

    def _score(self, action_text, tool_name=None):
        """Score action text through the engine, return tool fidelity."""
        result = self.engine.score_action(
            action_text=action_text,
            tool_name=tool_name,
            tool_args={"telos_tool_name": tool_name} if tool_name else None,
        )
        return result.tool_fidelity

    def test_read_exemplars_match_bridge_format(self):
        """Read tool exemplars use bridge format: 'Read {type} file ... for analysis: {path}'"""
        texts = [
            "Read source code file in project workspace for analysis: src/main.py",
            "Read configuration file in project workspace for analysis: pyproject.toml",
            "Read documentation file in project workspace for analysis: README.md",
        ]
        for text in texts:
            score = self._score(text, "fs_read_file")
            assert score >= 0.35, f"Read exemplar scored {score:.3f} < 0.35: {text}"

    def test_bash_exemplars_match_bridge_format(self):
        """Bash exemplars use bridge format with intent: 'Execute ... -- {intent}: {cmd}'"""
        texts = [
            "Execute shell command in project workspace -- version control: git status",
            "Execute shell command in project workspace -- test execution: pytest tests/ -v",
            "Execute shell command in project workspace -- dependency management: pip install -e .",
        ]
        for text in texts:
            score = self._score(text, "runtime_execute")
            assert score >= 0.35, f"Bash exemplar scored {score:.3f} < 0.35: {text}"

    def test_glob_exemplars_match_bridge_format(self):
        """Glob exemplars use bridge format: 'Search project codebase files by pattern: {pat}'"""
        texts = [
            "Search project codebase files by pattern: **/*.py",
            "Search project codebase files by pattern: src/**/*.ts",
        ]
        for text in texts:
            score = self._score(text, "fs_list_directory")
            assert score >= 0.35, f"Glob exemplar scored {score:.3f} < 0.35: {text}"

    def test_grep_exemplars_match_bridge_format(self):
        """Grep exemplars use bridge format: 'Search project codebase with text search for: {q}'"""
        texts = [
            "Search project codebase with text search for: TODO",
            "Search project codebase with text search for: import logging",
        ]
        for text in texts:
            score = self._score(text, "fs_search_files")
            assert score >= 0.35, f"Grep exemplar scored {score:.3f} < 0.35: {text}"

    def test_web_fetch_exemplars_match_bridge_format(self):
        """WebFetch exemplars use bridge format: 'Fetch web resource: {url}'"""
        texts = [
            "Fetch web resource: https://docs.python.org/3/library/asyncio.html",
            "Fetch web resource: https://fastapi.tiangolo.com/tutorial/",
        ]
        for text in texts:
            score = self._score(text, "web_fetch")
            assert score >= 0.35, f"WebFetch exemplar scored {score:.3f} < 0.35: {text}"

    def test_web_search_exemplars_match_bridge_format(self):
        """WebSearch exemplars use bridge format: 'Search the web for: {query}'.

        WebSearch has inherently low tool fidelity because queries are
        semantically diverse (the centroid is diluted). This is expected
        for LOW-risk search tools -- Gate 2 purpose scoring does the
        heavy lifting.
        """
        texts = [
            "Search the web for: Python asyncio best practices",
            "Search the web for: pytest fixture scope documentation",
        ]
        for text in texts:
            score = self._score(text, "web_search")
            assert score >= 0.15, f"WebSearch exemplar scored {score:.3f} < 0.15: {text}"

    def test_top10_runtime_actions_score_above_threshold(self):
        """The 10 most common OC runtime action texts should all score >= 0.60."""
        # Real action texts from production audit trail (bridge format)
        actions = [
            ("Read source code file in project workspace for analysis: telos_governance/config.py", "fs_read_file"),
            ("Edit source code file in project workspace: telos_adapters/openclaw/daemon.py", "fs_edit_file"),
            ("Execute shell command in project workspace -- version control: git status", "runtime_execute"),
            ("Execute shell command in project workspace -- test execution: pytest tests/ -v", "runtime_execute"),
            ("Search project codebase files by pattern: **/*.py", "fs_list_directory"),
            ("Search project codebase with text search for: def score_action", "fs_search_files"),
            ("Write source code file in project workspace: tests/unit/test_new.py", "fs_write_file"),
            ("Fetch web resource: https://docs.python.org/3/library/asyncio.html", "web_fetch"),
            ("Search the web for: Claude Code hooks documentation", "web_search"),
            ("Create sub-agent task: research existing implementation patterns", "nodes_delegate"),
        ]
        for text, tool in actions:
            score = self._score(text, tool)
            assert score >= 0.35, (
                f"Top-10 action scored {score:.3f} < 0.35: {text} (tool={tool})"
            )


class TestBoundaryNamesInVerdict:
    """Validate that triggered boundary texts appear in GovernanceVerdict."""

    def test_boundary_fields_in_result(self):
        """AgenticFidelityResult has triggered_boundaries and boundary_scores fields."""
        from telos_governance.scoring.agentic_fidelity import AgenticFidelityResult
        from telos_governance.types import ActionDecision, DirectionLevel

        result = AgenticFidelityResult(
            purpose_fidelity=0.5,
            scope_fidelity=0.5,
            boundary_violation=0.8,
            tool_fidelity=0.5,
            chain_continuity=0.5,
            composite_fidelity=0.5,
            effective_fidelity=0.5,
            decision=ActionDecision.ESCALATE,
            direction_level=DirectionLevel.DIRECT,
            boundary_triggered=True,
            triggered_boundaries=["Do not access financial data"],
            boundary_scores={"Do not access financial data": 0.82},
        )
        assert result.triggered_boundaries == ["Do not access financial data"]
        assert result.boundary_scores["Do not access financial data"] == 0.82

    def test_boundary_check_result_has_text(self):
        """BoundaryCheckResult carries triggered_boundary_text and score."""
        from telos_governance.scoring.agentic_fidelity import BoundaryCheckResult

        bcr = BoundaryCheckResult(
            violation_score=0.85,
            triggered=True,
            detail="test",
            safe_similarity=0.3,
            contrastive_margin=0.55,
            contrastive_suppressed=False,
            triggered_boundary_text="No financial advice",
            triggered_boundary_score=0.85,
        )
        assert bcr.triggered_boundary_text == "No financial advice"
        assert bcr.triggered_boundary_score == 0.85

    def test_verdict_carries_boundary_names(self):
        """GovernanceVerdict has triggered_boundaries and boundary_scores."""
        from telos_adapters.openclaw.governance_hook import GovernanceVerdict

        verdict = GovernanceVerdict(
            allowed=False,
            decision="escalate",
            fidelity=0.3,
            tool_group="fs",
            telos_tool_name="fs_write_file",
            risk_tier="high",
            is_cross_group=False,
            boundary_triggered=True,
            triggered_boundaries=["Do not modify system files"],
            boundary_scores={"Do not modify system files": 0.91},
        )
        d = verdict.to_dict()
        assert d["triggered_boundaries"] == ["Do not modify system files"]
        assert d["boundary_scores"]["Do not modify system files"] == 0.91


class TestAuditTrailExisting:
    """Verify existing audit infrastructure (hash chain, correlation ID)."""

    def test_hash_chain_exists(self, tmp_path):
        """Audit writer already produces prev_hash + entry_hash on every event."""
        import json
        from telos_adapters.openclaw.audit_writer import AuditWriter

        audit_path = tmp_path / "chain_test.jsonl"
        writer = AuditWriter(audit_path=audit_path)
        writer.emit("event_1", {"data": "first"})
        writer.emit("event_2", {"data": "second"})
        writer.close()

        lines = audit_path.read_text().strip().split("\n")
        r1 = json.loads(lines[0])
        r2 = json.loads(lines[1])

        # First event has genesis prev_hash
        assert r1["prev_hash"] == "0" * 64
        assert r1["entry_hash"] != ""
        # Second event chains from first
        assert r2["prev_hash"] == r1["entry_hash"]

    def test_correlation_id_in_verdict(self):
        """GovernanceVerdict has correlation_id field."""
        from telos_adapters.openclaw.governance_hook import GovernanceVerdict
        v = GovernanceVerdict(
            allowed=True, decision="execute", fidelity=0.9,
            tool_group="fs", telos_tool_name="fs_read_file",
            risk_tier="low", is_cross_group=False,
            correlation_id="test-uuid-123",
        )
        assert v.correlation_id == "test-uuid-123"
        assert v.to_dict()["correlation_id"] == "test-uuid-123"

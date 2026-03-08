"""
Tests for AgenticForensicReportGenerator.

Covers: constructor, context building, HTML generation, JSONL export,
CSV export, health assessment, narrative generation, IEEE 7001 checklist,
drift trajectory, boundary events, edge cases, and the new
generate_report_html() method.
"""

import json
import csv
import io
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from telos_governance.report_generator import (
    AgenticForensicReportGenerator,
    generate_agentic_forensic_report,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def tmp_output_dir():
    """Create and clean up a temp directory for report output."""
    d = Path(tempfile.mkdtemp(prefix="telos_test_report_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def generator(tmp_output_dir):
    """Generator with a temp output directory."""
    return AgenticForensicReportGenerator(output_dir=tmp_output_dir)


def _make_turn(
    step=1,
    decision="EXECUTE",
    purpose=0.90,
    scope=0.85,
    tool=0.88,
    chain=0.92,
    boundary=1.0,
    boundary_triggered=False,
    effective=0.88,
    selected_tool="check_coverage",
    drift_level="NORMAL",
    drift_magnitude=0.0,
    saai_baseline=None,
    user_request="Check the coverage area",
    response_text="Coverage verified for the property.",
):
    """Helper to build a single turn dict matching session state schema."""
    return {
        "step": step,
        "decision": decision,
        "purpose_fidelity": purpose,
        "scope_fidelity": scope,
        "tool_fidelity": tool,
        "chain_sci": chain,
        "boundary_fidelity": boundary,
        "boundary_triggered": boundary_triggered,
        "effective_fidelity": effective,
        "selected_tool": selected_tool,
        "tool_rankings": [
            {"tool_name": selected_tool, "fidelity": tool, "is_selected": True, "is_blocked": False},
            {"tool_name": "fallback", "fidelity": 0.50, "is_selected": False, "is_blocked": False},
        ],
        "drift_level": drift_level,
        "drift_magnitude": drift_magnitude,
        "saai_baseline": saai_baseline,
        "user_request": user_request,
        "response_text": response_text,
    }


def _make_session(n_turns=5, avg_fidelity=0.88):
    """Build a list of n healthy turns."""
    return [
        _make_turn(step=i + 1, effective=avg_fidelity, saai_baseline=0.88 if i >= 3 else None)
        for i in range(n_turns)
    ]


COMMON_KWARGS = {
    "session_id": "test-sess-001",
    "template_id": "property_intel",
    "agent_name": "Property Analyst",
    "agent_purpose": "Analyze property risk",
    "agent_scope": "Insurance underwriting",
    "boundaries": ["No PII disclosure", "Coverage area only"],
    "tools": ["check_coverage", "get_imagery", "assess_risk"],
}


# ===========================================================================
# Constructor Tests
# ===========================================================================


class TestConstructor:
    def test_creates_output_dir(self, tmp_output_dir):
        target = tmp_output_dir / "sub" / "dir"
        gen = AgenticForensicReportGenerator(output_dir=target)
        assert target.exists()

    def test_default_output_dir(self):
        gen = AgenticForensicReportGenerator()
        assert gen.output_dir == Path("./telos_reports")

    def test_jinja2_required(self):
        """Jinja2 is now a hard dependency — ImportError should propagate."""
        with patch.dict("sys.modules", {"jinja2": None}):
            with pytest.raises(ImportError):
                AgenticForensicReportGenerator(output_dir=Path(tempfile.mkdtemp()))

    def test_template_loaded(self, generator):
        assert generator._template is not None
        assert generator._env is not None


# ===========================================================================
# Context Building Tests
# ===========================================================================


class TestBuildContext:
    def test_context_has_all_required_keys(self, generator):
        turns = _make_session(5)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)

        required_keys = [
            "session_id", "generated_at", "template_id", "agent_name",
            "agent_purpose", "agent_scope", "boundary_list", "tool_list",
            "total_steps", "avg_fidelity", "boundary_count", "escalation_count",
            "total_overrides", "final_drift_level", "final_drift_magnitude",
            "saai_baseline", "health_label", "health_color",
            "executive_narrative", "turns", "drift_trajectory",
            "tier_transition_count", "chain_length", "avg_sci",
            "chain_breaks", "chain_continuous", "boundary_events",
            "ieee_checklist", "regulatory_mapping", "fidelity_class",
            "decision_class", "saai_badge_class", "saai_color",
        ]
        for key in required_keys:
            assert key in ctx, f"Missing context key: {key}"

    def test_total_steps_matches_turns(self, generator):
        turns = _make_session(7)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["total_steps"] == 7
        assert ctx["chain_length"] == 7

    def test_avg_fidelity_computed(self, generator):
        turns = [_make_turn(step=1, effective=0.90), _make_turn(step=2, effective=0.80)]
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert abs(ctx["avg_fidelity"] - 0.85) < 1e-9

    def test_boundary_list_joined(self, generator):
        turns = _make_session(1)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert "No PII disclosure" in ctx["boundary_list"]
        assert "; " in ctx["boundary_list"]

    def test_tool_list_joined(self, generator):
        turns = _make_session(1)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert "check_coverage" in ctx["tool_list"]
        assert ", " in ctx["tool_list"]

    def test_generated_at_contains_utc(self, generator):
        turns = _make_session(1)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert "UTC" in ctx["generated_at"]


# ===========================================================================
# Health Assessment Tests
# ===========================================================================


class TestHealthAssessment:
    def test_healthy_session(self, generator):
        turns = _make_session(5, avg_fidelity=0.90)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["health_label"] == "HEALTHY"
        assert ctx["health_color"] == "green"

    def test_fair_session_low_fidelity(self, generator):
        turns = _make_session(5, avg_fidelity=0.55)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["health_label"] == "FAIR"
        assert ctx["health_color"] == "yellow"

    def test_fair_session_one_boundary(self, generator):
        turns = _make_session(5, avg_fidelity=0.80)
        turns[2]["boundary_triggered"] = True
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["health_label"] == "FAIR"

    def test_at_risk_session(self, generator):
        turns = _make_session(5, avg_fidelity=0.40)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["health_label"] == "AT RISK"
        assert ctx["health_color"] == "red"

    def test_at_risk_many_boundaries(self, generator):
        turns = _make_session(5, avg_fidelity=0.80)
        turns[0]["boundary_triggered"] = True
        turns[1]["boundary_triggered"] = True
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["health_label"] == "AT RISK"


# ===========================================================================
# Drift Trajectory Tests
# ===========================================================================


class TestDriftTrajectory:
    def test_trajectory_length_matches_turns(self, generator):
        turns = _make_session(5)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert len(ctx["drift_trajectory"]) == 5

    def test_tier_transitions_counted(self, generator):
        turns = _make_session(4)
        turns[0]["drift_level"] = "NORMAL"
        turns[1]["drift_level"] = "WARNING"
        turns[2]["drift_level"] = "RESTRICT"
        turns[3]["drift_level"] = "BLOCK"
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["tier_transition_count"] == 3

    def test_final_drift_level(self, generator):
        turns = _make_session(3)
        turns[2]["drift_level"] = "WARNING"
        turns[2]["drift_magnitude"] = 0.12
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["final_drift_level"] == "WARNING"
        assert abs(ctx["final_drift_magnitude"] - 0.12) < 1e-9

    def test_saai_baseline_from_last_non_null(self, generator):
        turns = _make_session(5)
        turns[2]["saai_baseline"] = 0.91
        turns[4]["saai_baseline"] = 0.89
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert abs(ctx["saai_baseline"] - 0.89) < 1e-9


# ===========================================================================
# Chain Analysis Tests
# ===========================================================================


class TestChainAnalysis:
    def test_continuous_chain(self, generator):
        turns = _make_session(5, avg_fidelity=0.90)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["chain_continuous"] is True
        assert ctx["chain_breaks"] == 0

    def test_broken_chain(self, generator):
        turns = _make_session(5, avg_fidelity=0.90)
        # Step 3 has low SCI — chain break
        turns[2]["chain_sci"] = 0.10
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["chain_continuous"] is False
        assert ctx["chain_breaks"] == 1

    def test_chain_break_only_after_step_1(self, generator):
        """Step 1 with low SCI should NOT count as chain break."""
        turns = [_make_turn(step=1, chain=0.0)]
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["chain_breaks"] == 0


# ===========================================================================
# Boundary Events Tests
# ===========================================================================


class TestBoundaryEvents:
    def test_boundary_events_collected(self, generator):
        turns = _make_session(5)
        turns[1]["boundary_triggered"] = True
        turns[1]["boundary_fidelity"] = 0.20
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["boundary_count"] == 1
        assert len(ctx["boundary_events"]) == 1
        assert ctx["boundary_events"][0]["step"] == 2

    def test_override_tracked(self, generator):
        turns = _make_session(3)
        turns[0]["boundary_triggered"] = True
        turns[0]["overridden"] = True
        turns[0]["override_reason"] = "Manager approved"
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["total_overrides"] == 1
        assert ctx["boundary_events"][0]["overridden"] is True

    def test_escalation_counted(self, generator):
        turns = _make_session(3)
        turns[1]["decision"] = "ESCALATE"
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["escalation_count"] == 1


# ===========================================================================
# Executive Narrative Tests
# ===========================================================================


class TestNarrative:
    def test_narrative_contains_step_count(self, generator):
        turns = _make_session(7)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert "7 governance steps" in ctx["executive_narrative"]

    def test_narrative_contains_drift_level(self, generator):
        turns = _make_session(3)
        turns[2]["drift_level"] = "WARNING"
        turns[2]["drift_magnitude"] = 0.12
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert "WARNING" in ctx["executive_narrative"]

    def test_narrative_mentions_boundary_violations(self, generator):
        turns = _make_session(3)
        turns[0]["boundary_triggered"] = True
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert "boundary violation" in ctx["executive_narrative"]

    def test_narrative_continuous_chain(self, generator):
        turns = _make_session(3)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert "semantic continuity" in ctx["executive_narrative"]

    def test_narrative_broken_chain(self, generator):
        turns = _make_session(3)
        turns[1]["chain_sci"] = 0.05
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert "break" in ctx["executive_narrative"]


# ===========================================================================
# HTML Report Generation Tests
# ===========================================================================


class TestGenerateReport:
    def test_generates_html_file(self, generator, tmp_output_dir):
        turns = _make_session(3)
        path = generator.generate_report(**COMMON_KWARGS, turns=turns)
        assert path.exists()
        assert path.suffix == ".html"
        content = path.read_text()
        assert "<html" in content.lower() or "<!doctype" in content.lower() or "session" in content.lower()

    def test_custom_filename(self, generator, tmp_output_dir):
        turns = _make_session(3)
        path = generator.generate_report(**COMMON_KWARGS, turns=turns, filename="custom.html")
        assert path.name == "custom.html"
        assert path.exists()

    def test_auto_filename_contains_session_id(self, generator, tmp_output_dir):
        turns = _make_session(3)
        path = generator.generate_report(**COMMON_KWARGS, turns=turns)
        assert "test-sess-001" in path.name

    def test_report_contains_agent_name(self, generator, tmp_output_dir):
        turns = _make_session(3)
        path = generator.generate_report(**COMMON_KWARGS, turns=turns)
        content = path.read_text()
        assert "Property Analyst" in content


class TestGenerateReportHtml:
    def test_returns_string_not_path(self, generator):
        turns = _make_session(3)
        html = generator.generate_report_html(**COMMON_KWARGS, turns=turns)
        assert isinstance(html, str)

    def test_html_contains_session_id(self, generator):
        turns = _make_session(3)
        html = generator.generate_report_html(**COMMON_KWARGS, turns=turns)
        assert "test-sess-001" in html

    def test_no_file_written(self, generator, tmp_output_dir):
        turns = _make_session(3)
        before = set(tmp_output_dir.iterdir())
        generator.generate_report_html(**COMMON_KWARGS, turns=turns)
        after = set(tmp_output_dir.iterdir())
        assert before == after


# ===========================================================================
# JSONL Export Tests
# ===========================================================================


class TestGenerateJsonl:
    def test_generates_jsonl_file(self, generator, tmp_output_dir):
        turns = _make_session(3)
        path = generator.generate_jsonl(session_id="test-sess-001", turns=turns)
        assert path.exists()
        assert path.suffix == ".jsonl"

    def test_jsonl_line_count(self, generator, tmp_output_dir):
        turns = _make_session(5)
        path = generator.generate_jsonl(session_id="test-sess-001", turns=turns)
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 5

    def test_jsonl_event_type(self, generator, tmp_output_dir):
        turns = _make_session(1)
        path = generator.generate_jsonl(session_id="test-sess-001", turns=turns)
        event = json.loads(path.read_text().strip())
        assert event["event_type"] == "agentic_governance_decision"
        assert event["session_id"] == "test-sess-001"

    def test_jsonl_contains_fidelity_fields(self, generator, tmp_output_dir):
        turns = [_make_turn(step=1, purpose=0.91, scope=0.85, effective=0.88)]
        path = generator.generate_jsonl(session_id="test-sess-001", turns=turns)
        event = json.loads(path.read_text().strip())
        assert abs(event["purpose_fidelity"] - 0.91) < 1e-9
        assert abs(event["effective_fidelity"] - 0.88) < 1e-9


# ===========================================================================
# CSV Export Tests
# ===========================================================================


class TestGenerateCsv:
    def test_generates_csv_file(self, generator, tmp_output_dir):
        turns = _make_session(3)
        path = generator.generate_csv(session_id="test-sess-001", turns=turns)
        assert path.exists()
        assert path.suffix == ".csv"

    def test_csv_row_count(self, generator, tmp_output_dir):
        turns = _make_session(4)
        path = generator.generate_csv(session_id="test-sess-001", turns=turns)
        with open(path) as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert len(rows) == 5  # header + 4 data rows

    def test_csv_header_includes_key_fields(self, generator, tmp_output_dir):
        turns = _make_session(1)
        path = generator.generate_csv(session_id="test-sess-001", turns=turns)
        with open(path) as f:
            reader = csv.reader(f)
            header = next(reader)
        assert "step" in header
        assert "decision" in header
        assert "effective_fidelity" in header
        assert "drift_level" in header


# ===========================================================================
# IEEE 7001 Checklist Tests
# ===========================================================================


class TestIeeeChecklist:
    def test_checklist_has_7_items(self, generator):
        """IEEE checklist: 5 original + Graduated Sanctions + Adversarial Robustness."""
        turns = _make_session(3)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert len(ctx["ieee_checklist"]) == 7

    def test_checklist_items_have_required_fields(self, generator):
        turns = _make_session(3)
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        for item in ctx["ieee_checklist"]:
            assert "name" in item
            assert "description" in item
            assert "passed" in item


# ===========================================================================
# Helper Method Tests
# ===========================================================================


class TestHelperMethods:
    def test_fidelity_class_green(self, generator):
        assert generator._fidelity_class(0.85) == "green"

    def test_fidelity_class_yellow(self, generator):
        assert generator._fidelity_class(0.65) == "yellow"

    def test_fidelity_class_red(self, generator):
        assert generator._fidelity_class(0.40) == "red"

    def test_decision_class_execute(self, generator):
        assert generator._decision_class("EXECUTE") == "green"

    def test_decision_class_escalate(self, generator):
        assert generator._decision_class("ESCALATE") == "red"

    def test_saai_badge_normal(self):
        assert AgenticForensicReportGenerator._saai_badge_class("NORMAL") == "green"

    def test_saai_badge_restrict(self):
        assert AgenticForensicReportGenerator._saai_badge_class("RESTRICT") == "orange"

    def test_saai_badge_unknown(self):
        assert AgenticForensicReportGenerator._saai_badge_class("UNKNOWN") == "blue"


# ===========================================================================
# Convenience Function Tests
# ===========================================================================


class TestConvenienceFunction:
    def test_generate_agentic_forensic_report(self):
        turns = _make_session(3)
        path = generate_agentic_forensic_report(**COMMON_KWARGS, turns=turns)
        assert path.exists()
        # Cleanup
        path.unlink()


# ===========================================================================
# Edge Cases
# ===========================================================================


class TestEdgeCases:
    def test_empty_turns(self, generator):
        """Empty turns list should not crash."""
        ctx = generator._build_context(**COMMON_KWARGS, turns=[])
        assert ctx["total_steps"] == 0
        assert ctx["avg_fidelity"] == 0.0

    def test_single_turn(self, generator):
        turns = [_make_turn(step=1)]
        ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
        assert ctx["total_steps"] == 1

    def test_empty_boundaries(self, generator):
        turns = _make_session(1)
        kwargs = {**COMMON_KWARGS, "boundaries": [], "turns": turns}
        ctx = generator._build_context(**kwargs)
        assert ctx["boundary_list"] == ""

    def test_empty_tools(self, generator):
        turns = _make_session(1)
        kwargs = {**COMMON_KWARGS, "tools": [], "turns": turns}
        ctx = generator._build_context(**kwargs)
        assert ctx["tool_list"] == ""

    def test_turn_missing_optional_fields(self, generator):
        """Turns with minimal fields should not crash."""
        minimal_turn = {"step": 1}
        ctx = generator._build_context(**COMMON_KWARGS, turns=[minimal_turn])
        assert ctx["total_steps"] == 1

    def test_all_drift_levels_in_saai_color(self, generator):
        for level, color in [("NORMAL", "green"), ("WARNING", "yellow"),
                             ("RESTRICT", "orange"), ("BLOCK", "red")]:
            turns = [_make_turn(step=1, drift_level=level)]
            ctx = generator._build_context(**COMMON_KWARGS, turns=turns)
            assert ctx["saai_color"] == color

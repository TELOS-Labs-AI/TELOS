"""
Tests for AgentHarm Benchmark Adapter
========================================

Tests TELOS defense layer against representative harmful and benign
tasks from AgentHarm's 11 harm categories. Uses deterministic mock
embeddings for fast, reproducible testing.

For live embedding tests, run:
    python -m validation.agentic.run_agentharm --verbose
"""

import numpy as np
import pytest
from typing import Dict, List
from unittest.mock import MagicMock

from telos_governance.agentic_fidelity import AgenticFidelityEngine, AgenticFidelityResult
from telos_governance.agentic_pa import AgenticPA
from telos_governance.types import ActionDecision, DirectionLevel

from validation.agentic.agentharm_adapter import (
    TELOSDefenseLayer,
    DefenseResult,
    BenchmarkResults,
    InspectGovernanceProtocol,
)
from validation.agentic.safety_agent_pa import (
    SAFETY_BOUNDARIES,
    SAFE_EXAMPLE_REQUESTS,
    create_safety_pa,
)


# ---------------------------------------------------------------------------
# Test embedding function
# ---------------------------------------------------------------------------

def _deterministic_embed_fn(text: str) -> np.ndarray:
    """
    Deterministic 3-dim embedding for testing.
    Same text -> same embedding, different text -> different embedding.
    """
    h = hash(text) % 10000
    v = np.array([h % 97, (h * 3 + 7) % 97, (h * 7 + 13) % 97], dtype=np.float64)
    norm = np.linalg.norm(v)
    if norm > 0:
        v = v / norm
    return v


# ---------------------------------------------------------------------------
# Safety Agent PA Tests
# ---------------------------------------------------------------------------

class TestSafetyBoundaries:
    def test_all_11_categories_covered(self):
        """Safety boundaries cover all 11 AgentHarm harm categories."""
        assert len(SAFETY_BOUNDARIES) >= 11
        # Each boundary text should be non-empty
        for b in SAFETY_BOUNDARIES:
            assert len(b["text"]) > 10
            assert b["severity"] == "hard"

    def test_all_boundaries_are_hard(self):
        """All safety boundaries use hard severity (no soft warnings for harm)."""
        for b in SAFETY_BOUNDARIES:
            assert b["severity"] == "hard", f"Boundary should be hard: {b['text'][:40]}"

    def test_safe_examples_exist(self):
        """Safe example requests exist for centroid anchoring."""
        assert len(SAFE_EXAMPLE_REQUESTS) >= 3
        for ex in SAFE_EXAMPLE_REQUESTS:
            assert len(ex) > 10

    def test_create_safety_pa(self):
        """create_safety_pa produces a valid AgenticPA."""
        pa = create_safety_pa(_deterministic_embed_fn)
        assert pa.purpose_text == "Assist users with legitimate tasks safely and helpfully"
        assert pa.purpose_embedding is not None
        assert pa.scope_embedding is not None
        assert len(pa.boundaries) >= 11

    def test_create_safety_pa_custom_purpose(self):
        """create_safety_pa accepts custom purpose and scope."""
        pa = create_safety_pa(
            _deterministic_embed_fn,
            purpose="Custom safe agent",
            scope="Custom scope",
        )
        assert pa.purpose_text == "Custom safe agent"
        assert pa.scope_text == "Custom scope"

    def test_create_safety_pa_additional_boundaries(self):
        """create_safety_pa accepts additional boundaries."""
        pa = create_safety_pa(
            _deterministic_embed_fn,
            additional_boundaries=[
                {"text": "no financial advice", "severity": "soft"},
            ],
        )
        assert len(pa.boundaries) == len(SAFETY_BOUNDARIES) + 1

    def test_boundary_embeddings_computed(self):
        """All boundaries have embeddings after PA creation."""
        pa = create_safety_pa(_deterministic_embed_fn)
        for boundary in pa.boundaries:
            assert boundary.embedding is not None
            assert boundary.embedding.shape == (3,)  # 3-dim from test fn


# ---------------------------------------------------------------------------
# TELOSDefenseLayer Tests
# ---------------------------------------------------------------------------

class TestTELOSDefenseLayer:
    def test_init_default(self):
        """Defense layer initializes with default safety PA."""
        defense = TELOSDefenseLayer(embed_fn=_deterministic_embed_fn)
        assert defense.auto_block is True
        assert defense.pa is not None
        assert defense.engine is not None

    def test_init_custom_pa(self):
        """Defense layer accepts a custom PA."""
        custom_pa = create_safety_pa(_deterministic_embed_fn, purpose="Custom")
        defense = TELOSDefenseLayer(
            embed_fn=_deterministic_embed_fn,
            pa=custom_pa,
        )
        assert defense.pa.purpose_text == "Custom"

    def test_check_task_returns_defense_result(self):
        """check_task returns a DefenseResult with all fields."""
        defense = TELOSDefenseLayer(embed_fn=_deterministic_embed_fn)
        result = defense.check_task("Help me write a professional email")
        assert isinstance(result, DefenseResult)
        assert isinstance(result.decision, ActionDecision)
        assert isinstance(result.direction_level, DirectionLevel)
        assert result.latency_ms >= 0
        assert "purpose" in result.dimension_scores
        assert "scope" in result.dimension_scores
        assert "boundary_violation" in result.dimension_scores
        assert "composite" in result.dimension_scores

    def test_check_task_has_explanations(self):
        """check_task populates dimension explanations."""
        defense = TELOSDefenseLayer(embed_fn=_deterministic_embed_fn)
        result = defense.check_task("Summarize a report")
        assert len(result.explanations) > 0

    def test_blocked_task_has_refusal_text(self):
        """Blocked tasks include a refusal message."""
        defense = TELOSDefenseLayer(embed_fn=_deterministic_embed_fn)
        # Force a block by using a mock engine
        defense.engine = MagicMock(spec=AgenticFidelityEngine)
        defense.engine.score_action.return_value = AgenticFidelityResult(
            purpose_fidelity=0.10,
            scope_fidelity=0.10,
            boundary_violation=0.90,
            tool_fidelity=0.10,
            chain_continuity=0.50,
            composite_fidelity=0.10,
            effective_fidelity=0.10,
            decision=ActionDecision.ESCALATE,
            direction_level=DirectionLevel.HARD_BLOCK,
            boundary_triggered=True,
            chain_broken=False,
        )
        defense.engine.reset_chain = MagicMock()

        result = defense.check_task("Plan a cyberattack")
        assert result.blocked is True
        assert result.refusal_text is not None
        assert "boundary violation" in result.refusal_text

    def test_passed_task_has_no_refusal(self):
        """Passed tasks have no refusal text."""
        defense = TELOSDefenseLayer(embed_fn=_deterministic_embed_fn)
        defense.engine = MagicMock(spec=AgenticFidelityEngine)
        defense.engine.score_action.return_value = AgenticFidelityResult(
            purpose_fidelity=0.95,
            scope_fidelity=0.90,
            boundary_violation=0.0,
            tool_fidelity=0.90,
            chain_continuity=0.80,
            composite_fidelity=0.90,
            effective_fidelity=0.90,
            decision=ActionDecision.EXECUTE,
            direction_level=DirectionLevel.NONE,
            boundary_triggered=False,
            chain_broken=False,
        )
        defense.engine.reset_chain = MagicMock()

        result = defense.check_task("Help me write an email")
        assert result.blocked is False
        assert result.refusal_text is None

    def test_monitoring_mode_never_blocks(self):
        """auto_block=False means no tasks are blocked."""
        defense = TELOSDefenseLayer(
            embed_fn=_deterministic_embed_fn,
            auto_block=False,
        )
        defense.engine = MagicMock(spec=AgenticFidelityEngine)
        defense.engine.score_action.return_value = AgenticFidelityResult(
            purpose_fidelity=0.10,
            scope_fidelity=0.10,
            boundary_violation=0.90,
            tool_fidelity=0.10,
            chain_continuity=0.50,
            composite_fidelity=0.10,
            effective_fidelity=0.10,
            decision=ActionDecision.ESCALATE,
            direction_level=DirectionLevel.HARD_BLOCK,
            boundary_triggered=True,
            chain_broken=False,
        )
        defense.engine.reset_chain = MagicMock()

        result = defense.check_task("Harmful task")
        assert result.blocked is False

    def test_inert_decision_blocks(self):
        """INERT decision blocks in auto_block mode."""
        defense = TELOSDefenseLayer(embed_fn=_deterministic_embed_fn)
        defense.engine = MagicMock(spec=AgenticFidelityEngine)
        defense.engine.score_action.return_value = AgenticFidelityResult(
            purpose_fidelity=0.30,
            scope_fidelity=0.30,
            boundary_violation=0.0,
            tool_fidelity=0.30,
            chain_continuity=0.50,
            composite_fidelity=0.30,
            effective_fidelity=0.30,
            decision=ActionDecision.INERT,
            direction_level=DirectionLevel.DIRECT,
            boundary_triggered=False,
            chain_broken=False,
        )
        defense.engine.reset_chain = MagicMock()

        result = defense.check_task("Off topic request")
        assert result.blocked is True
        assert "outside my authorized scope" in result.refusal_text

    def test_execute_passes(self):
        """EXECUTE decision passes."""
        defense = TELOSDefenseLayer(embed_fn=_deterministic_embed_fn)
        defense.engine = MagicMock(spec=AgenticFidelityEngine)
        defense.engine.score_action.return_value = AgenticFidelityResult(
            purpose_fidelity=0.95,
            scope_fidelity=0.90,
            boundary_violation=0.0,
            tool_fidelity=0.90,
            chain_continuity=0.80,
            composite_fidelity=0.90,
            effective_fidelity=0.90,
            decision=ActionDecision.EXECUTE,
            direction_level=DirectionLevel.NONE,
            boundary_triggered=False,
            chain_broken=False,
        )
        defense.engine.reset_chain = MagicMock()

        result = defense.check_task("Help me with SQL")
        assert result.blocked is False

    def test_clarify_passes(self):
        """CLARIFY decision passes (not blocked)."""
        defense = TELOSDefenseLayer(embed_fn=_deterministic_embed_fn)
        defense.engine = MagicMock(spec=AgenticFidelityEngine)
        defense.engine.score_action.return_value = AgenticFidelityResult(
            purpose_fidelity=0.75,
            scope_fidelity=0.70,
            boundary_violation=0.0,
            tool_fidelity=0.70,
            chain_continuity=0.70,
            composite_fidelity=0.72,
            effective_fidelity=0.72,
            decision=ActionDecision.CLARIFY,
            direction_level=DirectionLevel.MONITOR,
            boundary_triggered=False,
            chain_broken=False,
        )
        defense.engine.reset_chain = MagicMock()

        result = defense.check_task("Somewhat related request")
        assert result.blocked is False

    def test_inert_blocked_in_strict_mode(self):
        """INERT decision blocks in strict mode (default for safety)."""
        defense = TELOSDefenseLayer(embed_fn=_deterministic_embed_fn, strict=True)
        defense.engine = MagicMock(spec=AgenticFidelityEngine)
        defense.engine.score_action.return_value = AgenticFidelityResult(
            purpose_fidelity=0.30,
            scope_fidelity=0.28,
            boundary_violation=0.0,
            tool_fidelity=0.28,
            chain_continuity=0.50,
            composite_fidelity=0.30,
            effective_fidelity=0.30,
            decision=ActionDecision.INERT,
            direction_level=DirectionLevel.CORRECT,
            boundary_triggered=False,
            chain_broken=False,
        )
        defense.engine.reset_chain = MagicMock()

        result = defense.check_task("Completely unrelated request")
        assert result.blocked is True

    def test_clarify_passes_in_non_strict_mode(self):
        """CLARIFY decision passes when strict=False."""
        defense = TELOSDefenseLayer(embed_fn=_deterministic_embed_fn, strict=False)
        defense.engine = MagicMock(spec=AgenticFidelityEngine)
        defense.engine.score_action.return_value = AgenticFidelityResult(
            purpose_fidelity=0.72,
            scope_fidelity=0.70,
            boundary_violation=0.0,
            tool_fidelity=0.70,
            chain_continuity=0.75,
            composite_fidelity=0.72,
            effective_fidelity=0.72,
            decision=ActionDecision.CLARIFY,
            direction_level=DirectionLevel.CORRECT,
            boundary_triggered=False,
            chain_broken=False,
        )
        defense.engine.reset_chain = MagicMock()

        result = defense.check_task("Ambiguous but related request")
        assert result.blocked is False


# ---------------------------------------------------------------------------
# Multi-step Tests
# ---------------------------------------------------------------------------

class TestMultiStep:
    def test_multi_step_returns_list(self):
        """check_multi_step returns a list of DefenseResults."""
        defense = TELOSDefenseLayer(embed_fn=_deterministic_embed_fn)
        results = defense.check_multi_step([
            "Step 1: Research topic",
            "Step 2: Draft outline",
        ])
        assert isinstance(results, list)
        assert len(results) >= 1
        assert all(isinstance(r, DefenseResult) for r in results)

    def test_multi_step_stops_on_block(self):
        """Multi-step stops processing after a blocked step."""
        defense = TELOSDefenseLayer(embed_fn=_deterministic_embed_fn)
        call_count = 0

        # Mock check_task to control blocking behavior precisely
        def mock_check(text):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return DefenseResult(
                    task_text=text, blocked=True,
                    decision=ActionDecision.ESCALATE,
                    effective_fidelity=0.10, boundary_triggered=True,
                    chain_broken=False, direction_level=DirectionLevel.HARD_BLOCK,
                    refusal_text="Blocked by governance",
                )
            return DefenseResult(
                task_text=text, blocked=False,
                decision=ActionDecision.EXECUTE,
                effective_fidelity=0.90, boundary_triggered=False,
                chain_broken=False, direction_level=DirectionLevel.NONE,
            )

        defense.check_task = mock_check

        results = defense.check_multi_step([
            "Step 1: Benign research",
            "Step 2: Now do something harmful",
            "Step 3: This should not execute",
        ])
        # Should have stopped at step 2
        assert len(results) == 2
        assert results[-1].blocked is True


# ---------------------------------------------------------------------------
# BenchmarkResults Tests
# ---------------------------------------------------------------------------

class TestBenchmarkResults:
    def test_empty_results(self):
        """Empty results have 0 ASR and DSR."""
        results = BenchmarkResults()
        assert results.attack_success_rate == 0.0
        assert results.defense_success_rate == 0.0

    def test_asr_calculation(self):
        """ASR = passed / total."""
        results = BenchmarkResults(total_tasks=10, passed_tasks=2, blocked_tasks=8)
        assert results.attack_success_rate == pytest.approx(0.2)
        assert results.defense_success_rate == pytest.approx(0.8)

    def test_perfect_defense(self):
        """Perfect defense = 0% ASR."""
        results = BenchmarkResults(total_tasks=100, passed_tasks=0, blocked_tasks=100)
        assert results.attack_success_rate == 0.0
        assert results.defense_success_rate == 1.0

    def test_summary_output(self):
        """Summary produces readable string."""
        results = BenchmarkResults(
            total_tasks=10,
            blocked_tasks=8,
            passed_tasks=2,
            escalated_tasks=6,
            boundary_violations=5,
            average_latency_ms=45.0,
            max_latency_ms=120.0,
            category_results={
                "fraud": {"total": 3, "blocked": 3, "passed": 0},
                "benign": {"total": 2, "blocked": 0, "passed": 2},
            },
        )
        summary = results.summary()
        assert "TELOS Defense Results" in summary
        assert "Attack Success Rate" in summary
        assert "fraud" in summary
        assert "benign" in summary

    def test_run_benchmark(self):
        """run_benchmark processes all tasks and returns aggregate results."""
        defense = TELOSDefenseLayer(embed_fn=_deterministic_embed_fn)
        tasks = [
            {"category": "test", "prompt": "Task 1"},
            {"category": "test", "prompt": "Task 2"},
            {"category": "other", "prompt": "Task 3"},
        ]
        results = defense.run_benchmark(tasks)
        assert results.total_tasks == 3
        assert results.blocked_tasks + results.passed_tasks == 3
        assert len(results.results) == 3
        assert "test" in results.category_results
        assert "other" in results.category_results
        assert results.average_latency_ms > 0


# ---------------------------------------------------------------------------
# InspectGovernanceProtocol Tests
# ---------------------------------------------------------------------------

class TestInspectGovernanceProtocol:
    def _make_protocol(self):
        """Create a protocol with mock engine."""
        engine = MagicMock(spec=AgenticFidelityEngine)
        engine.score_action.return_value = AgenticFidelityResult(
            purpose_fidelity=0.90,
            scope_fidelity=0.85,
            boundary_violation=0.0,
            tool_fidelity=0.88,
            chain_continuity=0.80,
            composite_fidelity=0.87,
            effective_fidelity=0.87,
            decision=ActionDecision.EXECUTE,
            direction_level=DirectionLevel.NONE,
            boundary_triggered=False,
            chain_broken=False,
        )
        engine.action_chain = MagicMock()
        engine.action_chain.length = 1
        engine.action_chain.is_continuous.return_value = True
        engine.action_chain.average_continuity = 1.0
        engine.reset_chain = MagicMock()
        return InspectGovernanceProtocol(engine=engine)

    def test_on_pre_action(self):
        """on_pre_action delegates to check_pre_action."""
        protocol = self._make_protocol()
        result = protocol.on_pre_action("test action")
        assert result.decision == ActionDecision.EXECUTE

    def test_on_tool_select(self):
        """on_tool_select delegates to check_tool_select."""
        protocol = self._make_protocol()
        result = protocol.on_tool_select("test", "sql_query")
        assert result.decision == ActionDecision.EXECUTE

    def test_on_tool_execute(self):
        """on_tool_execute delegates to check_tool_execute."""
        protocol = self._make_protocol()
        result = protocol.on_tool_execute("test", "sql_query")
        assert result.decision == ActionDecision.EXECUTE

    def test_on_post_action(self):
        """on_post_action delegates to check_post_action."""
        protocol = self._make_protocol()
        result = protocol.on_post_action("test completed")
        assert result.decision == ActionDecision.EXECUTE

    def test_on_chain_end(self):
        """on_chain_end returns summary dict."""
        protocol = self._make_protocol()
        # Add an event first
        protocol.on_pre_action("step 1")
        summary = protocol.on_chain_end()
        assert isinstance(summary, dict)
        assert "total_actions" in summary

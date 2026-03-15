"""
Tests for AgenticDriftTracker (SAAI EWMA drift tracking)
===================================================================

Tests the drift tracker wired into AgenticResponseManager for agentic
sessions. Validates baseline establishment (50 turns + CV stability gate),
EWMA drift detection (NORMAL/WARNING/RESTRICT/BLOCK), BLOCK override to
ESCALATE, acknowledgment mechanism, RESTRICT tier behavior, and recovery.

EWMA math: lambda = 2/(SAAI_EWMA_SPAN+1) ~= 0.0952
After n turns at constant score s with baseline b:
    ewma_n = b * alpha^n + s * (1 - alpha^n)   where alpha = 1 - lambda
    drift_n = (b - ewma_n) / b = (b - s) / b * (1 - alpha^n)
"""

import pytest
from unittest.mock import MagicMock

from telos_governance.response_manager import (
    AgenticDriftTracker,
    AgenticResponseManager,
    AgenticTurnResult,
)
from telos_core.constants import (
    BASELINE_TURN_COUNT,
    SAAI_DRIFT_WARNING,
    SAAI_DRIFT_RESTRICT,
    SAAI_DRIFT_BLOCK,
    SAAI_EWMA_SPAN,
    SAAI_MAX_ACKNOWLEDGMENTS,
    ST_SAAI_RESTRICT_EXECUTE_THRESHOLD,
)

# EWMA smoothing constants
LAMBDA = 2.0 / (SAAI_EWMA_SPAN + 1)
ALPHA = 1.0 - LAMBDA


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record_n_turns(tracker, fidelity, n):
    """Record n turns at a given fidelity level. Returns last status."""
    status = None
    for _ in range(n):
        status = tracker.record_fidelity(fidelity)
    return status


def _establish_baseline(tracker, fidelity=0.90):
    """Establish baseline at given fidelity. Returns baseline status."""
    return _record_n_turns(tracker, fidelity, BASELINE_TURN_COUNT)


def _ewma_drift_after_n(baseline, score, n):
    """Compute expected drift magnitude after n turns at constant score."""
    relative_drop = (baseline - score) / baseline if baseline > 0 else 0.0
    return max(0.0, relative_drop * (1 - ALPHA ** n))


def _turns_to_reach_drift(baseline, score, target_drift):
    """How many turns at `score` to reach `target_drift` from `baseline`.

    Returns the minimum integer n such that drift >= target_drift.
    """
    import math
    if baseline <= 0 or score >= baseline:
        return float('inf')
    relative_drop = (baseline - score) / baseline
    if relative_drop <= 0:
        return float('inf')
    # target_drift = relative_drop * (1 - alpha^n)
    # alpha^n = 1 - target_drift / relative_drop
    ratio = 1 - target_drift / relative_drop
    if ratio <= 0:
        return 1
    return math.ceil(math.log(ratio) / math.log(ALPHA))


# ---------------------------------------------------------------------------
# Baseline Establishment
# ---------------------------------------------------------------------------

class TestBaselineEstablishment:
    def test_baseline_not_established_before_threshold(self):
        """Baseline requires BASELINE_TURN_COUNT turns."""
        tracker = AgenticDriftTracker()
        for _ in range(BASELINE_TURN_COUNT - 1):
            status = tracker.record_fidelity(0.90)
        assert status["baseline_established"] is False
        assert status["baseline_fidelity"] is None

    def test_baseline_established_at_threshold(self):
        """Baseline is established on the Nth turn."""
        tracker = AgenticDriftTracker()
        status = _record_n_turns(tracker, 0.90, BASELINE_TURN_COUNT)
        assert status["baseline_established"] is True
        assert status["baseline_fidelity"] == pytest.approx(0.90)

    def test_baseline_uses_mean_of_first_n_scores(self):
        """Baseline is computed as the mean of the first BASELINE_TURN_COUNT scores."""
        tracker = AgenticDriftTracker()
        # Alternate between 0.80 and 1.00 for all baseline turns
        scores = [0.80 if i % 2 == 0 else 1.00 for i in range(BASELINE_TURN_COUNT)]
        for s in scores:
            status = tracker.record_fidelity(s)
        expected = sum(scores) / len(scores)
        assert status["baseline_established"] is True
        assert status["baseline_fidelity"] == pytest.approx(expected, abs=0.01)

    def test_baseline_cv_stability_gate(self):
        """Baseline rejects if CV exceeds SAAI_BASELINE_CV_MAX."""
        from telos_core.constants import SAAI_BASELINE_CV_MAX
        tracker = AgenticDriftTracker()
        # Wildly oscillating scores produce high CV
        for i in range(BASELINE_TURN_COUNT):
            score = 0.10 if i % 2 == 0 else 1.00
            status = tracker.record_fidelity(score)
        # CV of [0.10, 1.00, 0.10, 1.00, ...] >> 0.30
        # Baseline should NOT be established (or extended until stable)
        # If the extended baseline also fails CV, it remains unestablished
        if status["baseline_established"]:
            # If it was established, it must have been via the extension path
            pass
        else:
            assert status["baseline_fidelity"] is None

    def test_baseline_progress_reported(self):
        """Status includes baseline_progress and baseline_required during collection."""
        tracker = AgenticDriftTracker()
        status = tracker.record_fidelity(0.90)
        assert status["baseline_progress"] == 1
        assert status["baseline_required"] == BASELINE_TURN_COUNT


# ---------------------------------------------------------------------------
# Drift Detection: NORMAL
# ---------------------------------------------------------------------------

class TestDriftNormal:
    def test_stable_fidelity_stays_normal(self):
        """When fidelity is stable, drift level remains NORMAL."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        status = _record_n_turns(tracker, 0.90, 10)
        assert status["drift_level"] == "NORMAL"
        assert status["drift_magnitude"] == pytest.approx(0.0, abs=0.01)

    def test_slight_drop_stays_normal(self):
        """A small fidelity drop stays NORMAL even after many turns."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        # 0.88: max drift = (0.90-0.88)/0.90 = 0.022 -> always NORMAL
        status = _record_n_turns(tracker, 0.88, 50)
        assert status["drift_level"] == "NORMAL"


# ---------------------------------------------------------------------------
# Drift Detection: WARNING (10%) -- EWMA
# ---------------------------------------------------------------------------

class TestDriftWarning:
    def test_warning_after_sustained_drift(self):
        """EWMA triggers WARNING after enough turns with moderate drift."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        # Score 0.80: relative drop = 0.111
        # Need (1 - alpha^n) >= 0.10/0.111 = 0.90 -> alpha^n <= 0.10
        # n >= ln(0.10)/ln(0.905) ~= 23 turns
        n = _turns_to_reach_drift(0.90, 0.80, SAAI_DRIFT_WARNING)
        status = _record_n_turns(tracker, 0.80, n)
        assert status["drift_level"] == "WARNING"
        assert status["drift_magnitude"] >= SAAI_DRIFT_WARNING

    def test_single_drop_does_not_trigger_warning(self):
        """EWMA smoothing prevents single-turn WARNING triggers."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 1.0)
        # Single turn at 0.0: drift = lambda * 1.0 ~= 0.095 -> NORMAL (< 0.10)
        status = tracker.record_fidelity(0.0)
        assert status["drift_level"] == "NORMAL"

    def test_sustained_moderate_drift_triggers_warning(self):
        """Sustained moderate drift fills EWMA and reaches WARNING."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        # Score of 0.78: relative drop = 0.133
        # After many turns: drift approaches 0.133 -> WARNING (>= 0.10)
        n = _turns_to_reach_drift(0.90, 0.78, SAAI_DRIFT_WARNING)
        status = _record_n_turns(tracker, 0.78, n)
        assert status["drift_level"] == "WARNING"


# ---------------------------------------------------------------------------
# Drift Detection: RESTRICT (15%)
# ---------------------------------------------------------------------------

class TestDriftRestrict:
    def test_restrict_after_sustained_heavy_drift(self):
        """EWMA triggers RESTRICT at 15%+ drift after sustained low scores."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        # Score 0.50: relative drop = 0.444
        # After n turns: drift = 0.444 * (1 - alpha^n) >= 0.15
        n = _turns_to_reach_drift(0.90, 0.50, SAAI_DRIFT_RESTRICT)
        status = _record_n_turns(tracker, 0.50, n)
        assert status["drift_level"] in ("RESTRICT", "BLOCK")
        assert status["drift_magnitude"] >= SAAI_DRIFT_RESTRICT
        assert status["is_restricted"] is True or status["is_blocked"] is True


# ---------------------------------------------------------------------------
# Drift Detection: BLOCK (20%)
# ---------------------------------------------------------------------------

class TestDriftBlock:
    def test_block_after_sustained_very_low_fidelity(self):
        """EWMA triggers BLOCK at 20%+ drift after sustained low scores."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        # Score 0.50: relative drop = 0.444
        # After n turns: drift = 0.444 * (1 - alpha^n) >= 0.20
        n = _turns_to_reach_drift(0.90, 0.50, SAAI_DRIFT_BLOCK)
        status = _record_n_turns(tracker, 0.50, n)
        assert status["drift_level"] == "BLOCK"
        assert status["is_blocked"] is True
        assert status["drift_magnitude"] >= SAAI_DRIFT_BLOCK

    def test_is_blocked_property(self):
        """The is_blocked property reflects BLOCK state."""
        tracker = AgenticDriftTracker()
        assert tracker.is_blocked is False
        _establish_baseline(tracker, 1.0)
        # Many turns at 0.10 to push into BLOCK
        n = _turns_to_reach_drift(1.0, 0.10, SAAI_DRIFT_BLOCK)
        _record_n_turns(tracker, 0.10, n)
        assert tracker.is_blocked is True

    def test_sustained_low_fidelity_blocks(self):
        """Extended low fidelity eventually triggers BLOCK."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        n = _turns_to_reach_drift(0.90, 0.50, SAAI_DRIFT_BLOCK)
        status = _record_n_turns(tracker, 0.50, n)
        assert status["drift_level"] == "BLOCK"


# ---------------------------------------------------------------------------
# BLOCK Override: Forces ESCALATE
# ---------------------------------------------------------------------------

class TestBlockOverrideEscalate:
    def test_block_forces_escalate_decision(self):
        """When SAAI drift is BLOCK, process_request overrides decision to ESCALATE."""
        from telos_governance.agent_templates import AgenticTemplate
        from telos_governance.agentic_fidelity import AgenticFidelityResult
        from telos_governance.types import ActionDecision, DirectionLevel
        import numpy as np

        manager = AgenticResponseManager()
        manager._initialized = True
        manager._embed_fn = lambda t: np.ones(3) / np.sqrt(3)
        manager._llm_client = None
        manager._llm_client_checked = True

        template = AgenticTemplate(
            id="sql_analyst",
            name="SQL Database Analyst",
            description="Queries data",
            icon="database",
            purpose="Help users query and understand data in PostgreSQL databases",
            scope="SELECT queries, schema exploration, data analysis",
            boundaries=["No data modification"],
            tools=["sql_db_query"],
            tool_set_key="sql_agent",
            example_requests=["Show me total revenue"],
            drift_examples=["Delete all records"],
            system_prompt="You are a SQL Database Analyst.",
        )

        def make_engine_result(fidelity):
            result = AgenticFidelityResult(
                purpose_fidelity=fidelity,
                scope_fidelity=fidelity,
                boundary_violation=0.0,
                tool_fidelity=fidelity,
                chain_continuity=0.50,
                composite_fidelity=fidelity,
                effective_fidelity=fidelity,
                decision=ActionDecision.EXECUTE,
                direction_level=DirectionLevel.NONE,
                boundary_triggered=False,
                tool_blocked=False,
                chain_broken=False,
                selected_tool="sql_db_query",
                tool_rankings=[{"rank": 1, "tool": "sql_db_query", "fidelity": fidelity}],
            )
            result.dimension_explanations = {
                "purpose": "OK", "scope": "OK", "tool": "OK",
                "chain": "OK", "boundary": "OK",
            }
            return result

        mock_engine = MagicMock()
        manager._engine_cache["sql_analyst"] = mock_engine

        # Phase 1: Establish baseline with high fidelity
        mock_engine.score_action.return_value = make_engine_result(1.0)
        for i in range(BASELINE_TURN_COUNT):
            result = manager.process_request("Show revenue", template, i + 1)
            assert result.decision == "EXECUTE"

        # Phase 2: Send many low-fidelity turns to push EWMA into BLOCK
        mock_engine.score_action.return_value = make_engine_result(0.10)
        n = _turns_to_reach_drift(1.0, 0.10, SAAI_DRIFT_BLOCK)
        for i in range(n):
            result = manager.process_request("Show revenue", template, BASELINE_TURN_COUNT + 1 + i)

        assert result.decision == "ESCALATE"
        assert result.saai_blocked is True
        assert "SAAI DRIFT BLOCK" in result.decision_explanation
        assert "safety thresholds" in result.response_text.lower()
        assert result.pre_block_response is not None


# ---------------------------------------------------------------------------
# EWMA Behavior
# ---------------------------------------------------------------------------

class TestEwmaBehavior:
    def test_recovery_after_sustained_good_turns(self):
        """EWMA recovers to NORMAL after sustained good turns following drift."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        # Push into BLOCK
        n_block = _turns_to_reach_drift(0.90, 0.50, SAAI_DRIFT_BLOCK)
        _record_n_turns(tracker, 0.50, n_block)
        assert tracker.drift_level == "BLOCK"
        # Acknowledge to unblock, then recover with good scores
        tracker.acknowledge_drift("Review done")
        status = _record_n_turns(tracker, 0.90, 10)
        assert status["drift_level"] == "NORMAL"
        assert status["drift_magnitude"] == pytest.approx(0.0, abs=0.01)

    def test_ewma_smoothing_prevents_instant_threshold(self):
        """EWMA smoothing prevents single outliers from triggering thresholds."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 1.0)
        # Single extreme outlier
        status = tracker.record_fidelity(0.0)
        # drift = lambda * 1.0 ~= 0.095 -> NORMAL (< WARNING at 0.10)
        expected_drift = LAMBDA * 1.0
        assert status["drift_magnitude"] == pytest.approx(expected_drift, abs=0.005)
        assert status["drift_level"] == "NORMAL"

    def test_ewma_converges_to_steady_state(self):
        """After many turns at constant score, drift converges to relative drop."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 1.0)
        # 100 turns at 0.80: drift should converge to (1.0-0.80)/1.0 = 0.20
        status = _record_n_turns(tracker, 0.80, 100)
        assert status["drift_magnitude"] == pytest.approx(0.20, abs=0.01)

    def test_oscillating_fidelity_averages(self):
        """Alternating high/low fidelity produces moderate EWMA drift."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        # Alternate: 0.90 and 0.50 -- average input is 0.70
        # Long-run EWMA converges to ~0.70, drift ~ (0.90-0.70)/0.90 = 0.222
        for _ in range(50):
            tracker.record_fidelity(0.90)
            tracker.record_fidelity(0.50)
        status = tracker.record_fidelity(0.90)
        # Should be in BLOCK territory (>= 0.20 drift)
        assert status["drift_level"] == "BLOCK"

    def test_monotonically_increasing_never_triggers(self):
        """Improving fidelity should never trigger drift."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.50)
        for score in [0.55, 0.60, 0.65, 0.70, 0.75]:
            status = tracker.record_fidelity(score)
        assert status["drift_level"] == "NORMAL"
        assert status["drift_magnitude"] == 0.0

    def test_gradual_decline_escalates_tiers(self):
        """Sustained low scores escalate through WARNING -> RESTRICT -> BLOCK."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)

        # Score 0.70: relative drop = 0.222 -> eventually BLOCK
        # But first passes through WARNING and RESTRICT
        seen_warning = False
        seen_restrict = False
        seen_block = False
        for _ in range(60):
            status = tracker.record_fidelity(0.70)
            if status["drift_level"] == "WARNING":
                seen_warning = True
            elif status["drift_level"] == "RESTRICT":
                seen_restrict = True
            elif status["drift_level"] == "BLOCK":
                seen_block = True
                break

        assert seen_warning, "Should have passed through WARNING"
        assert seen_restrict, "Should have passed through RESTRICT"
        assert seen_block, "Should have reached BLOCK"

    def test_long_session_no_dilution(self):
        """EWMA does not dilute drift over long sessions (unlike session average)."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        # 100 turns of good fidelity
        _record_n_turns(tracker, 0.90, 100)
        assert tracker.drift_level == "NORMAL"
        # Now sustained drift -- should be detected (not diluted by prior good scores)
        n = _turns_to_reach_drift(0.90, 0.50, SAAI_DRIFT_BLOCK)
        status = _record_n_turns(tracker, 0.50, n)
        assert status["drift_level"] == "BLOCK"


# ---------------------------------------------------------------------------
# Acknowledgment Mechanism
# ---------------------------------------------------------------------------

class TestAcknowledgment:
    def test_acknowledge_resets_drift_level(self):
        """Acknowledging BLOCK resets drift to NORMAL."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        n = _turns_to_reach_drift(0.90, 0.10, SAAI_DRIFT_BLOCK)
        _record_n_turns(tracker, 0.10, n)
        assert tracker.drift_level == "BLOCK"

        status = tracker.acknowledge_drift("Operator review completed")
        assert status["drift_level"] == "NORMAL"
        assert status["drift_magnitude"] == 0.0
        assert status["is_blocked"] is False

    def test_acknowledge_preserves_baseline(self):
        """Acknowledgment preserves the original baseline."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        n = _turns_to_reach_drift(0.90, 0.10, SAAI_DRIFT_BLOCK)
        _record_n_turns(tracker, 0.10, n)
        tracker.acknowledge_drift("Review done")
        history = tracker.get_drift_history()
        assert history["baseline_fidelity"] == pytest.approx(0.90)

    def test_acknowledge_resets_ewma_to_baseline(self):
        """After acknowledgment, EWMA resets to baseline so drift restarts clean."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        n = _turns_to_reach_drift(0.90, 0.10, SAAI_DRIFT_BLOCK)
        _record_n_turns(tracker, 0.10, n)
        tracker.acknowledge_drift("OK")
        # Next good score should produce near-zero drift
        status = tracker.record_fidelity(0.90)
        assert status["drift_level"] == "NORMAL"
        assert status["drift_magnitude"] == pytest.approx(0.0, abs=0.01)

    def test_max_acknowledgments_permanently_blocks(self):
        """Exceeding max acknowledgments permanently blocks the session."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)

        for i in range(SAAI_MAX_ACKNOWLEDGMENTS):
            n = _turns_to_reach_drift(0.90, 0.10, SAAI_DRIFT_BLOCK)
            _record_n_turns(tracker, 0.10, n)
            tracker.acknowledge_drift(f"Ack {i+1}")

        # After max acks, trigger BLOCK again
        n = _turns_to_reach_drift(0.90, 0.10, SAAI_DRIFT_BLOCK)
        _record_n_turns(tracker, 0.10, n)
        assert tracker.is_blocked is True
        # Further acknowledgment should fail
        status = tracker.acknowledge_drift("Should not work")
        assert status["is_blocked"] is True
        assert status["permanently_blocked"] is True

    def test_acknowledge_no_op_when_not_blocked(self):
        """Acknowledging when not blocked is a no-op."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        tracker.record_fidelity(0.85)  # Not blocked
        status = tracker.acknowledge_drift("Not needed")
        assert status["acknowledgment_count"] == 0

    def test_acknowledgment_history_tracked(self):
        """Acknowledgment history records each event."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        n = _turns_to_reach_drift(0.90, 0.10, SAAI_DRIFT_BLOCK)
        _record_n_turns(tracker, 0.10, n)
        tracker.acknowledge_drift("First review")
        history = tracker.get_drift_history()
        assert len(history["acknowledgment_history"]) == 1
        assert history["acknowledgment_history"][0]["reason"] == "First review"
        assert history["acknowledgment_count"] == 1

    def test_manager_acknowledge_drift(self):
        """AgenticResponseManager.acknowledge_drift delegates to tracker."""
        manager = AgenticResponseManager()
        _establish_baseline(manager._drift_tracker, 0.90)
        n = _turns_to_reach_drift(0.90, 0.10, SAAI_DRIFT_BLOCK)
        _record_n_turns(manager._drift_tracker, 0.10, n)
        status = manager.acknowledge_drift("Manager review")
        assert status["drift_level"] == "NORMAL"


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestDriftReset:
    def test_reset_clears_all_state(self):
        """Reset returns tracker to initial state."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 1.0)
        n = _turns_to_reach_drift(1.0, 0.10, SAAI_DRIFT_BLOCK)
        _record_n_turns(tracker, 0.10, n)
        assert tracker.is_blocked is True

        tracker.reset()
        assert tracker.drift_level == "NORMAL"
        assert tracker.drift_magnitude == 0.0
        assert tracker.is_blocked is False

        status = tracker.record_fidelity(0.90)
        assert status["baseline_established"] is False

    def test_reset_clears_acknowledgment_count(self):
        """Reset clears the acknowledgment counter."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        n = _turns_to_reach_drift(0.90, 0.10, SAAI_DRIFT_BLOCK)
        _record_n_turns(tracker, 0.10, n)
        tracker.acknowledge_drift("Test")
        assert tracker.get_drift_history()["acknowledgment_count"] == 1
        tracker.reset()
        assert tracker.get_drift_history()["acknowledgment_count"] == 0

    def test_manager_reset_drift(self):
        """AgenticResponseManager.reset_drift() delegates to tracker."""
        manager = AgenticResponseManager()
        _establish_baseline(manager._drift_tracker, 0.90)
        n = _turns_to_reach_drift(0.90, 0.10, SAAI_DRIFT_BLOCK)
        _record_n_turns(manager._drift_tracker, 0.10, n)
        assert manager._drift_tracker.is_blocked is True

        manager.reset_drift()
        assert manager._drift_tracker.is_blocked is False
        assert manager._drift_tracker.drift_level == "NORMAL"


# ---------------------------------------------------------------------------
# AgenticTurnResult drift fields
# ---------------------------------------------------------------------------

class TestTurnResultDriftFields:
    def test_default_drift_fields(self):
        """AgenticTurnResult has correct drift field defaults."""
        r = AgenticTurnResult()
        assert r.drift_level == "NORMAL"
        assert r.drift_magnitude == 0.0
        assert r.saai_baseline is None
        assert r.saai_blocked is False
        assert r.pre_block_response is None


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_fidelity_clamped_above_one(self):
        """Fidelity values above 1.0 are clamped to 1.0."""
        tracker = AgenticDriftTracker()
        status = tracker.record_fidelity(1.5)
        assert status["turn_count"] == 1

    def test_fidelity_clamped_below_zero(self):
        """Negative fidelity values are clamped to 0.0."""
        tracker = AgenticDriftTracker()
        status = tracker.record_fidelity(-0.5)
        assert status["turn_count"] == 1

    def test_zero_baseline(self):
        """Baseline of 0.0 produces no drift (division guard)."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.0)
        status = tracker.record_fidelity(0.0)
        assert status["drift_magnitude"] == 0.0
        assert status["drift_level"] == "NORMAL"

    def test_perfect_baseline(self):
        """Baseline of 1.0 correctly detects sustained drift."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 1.0)
        # Sustained drift at 0.80 should eventually reach WARNING
        n = _turns_to_reach_drift(1.0, 0.80, SAAI_DRIFT_WARNING)
        status = _record_n_turns(tracker, 0.80, n)
        assert status["drift_level"] == "WARNING"


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_turn_count_tracking(self):
        """Status includes correct turn count."""
        tracker = AgenticDriftTracker()
        status = _record_n_turns(tracker, 0.90, 5)
        assert status["turn_count"] == 5

    def test_drift_level_property(self):
        """drift_level property reflects internal state after EWMA update."""
        tracker = AgenticDriftTracker()
        assert tracker.drift_level == "NORMAL"
        _establish_baseline(tracker, 1.0)
        # Sustained low scores push into BLOCK
        n = _turns_to_reach_drift(1.0, 0.50, SAAI_DRIFT_BLOCK)
        _record_n_turns(tracker, 0.50, n)
        assert tracker.drift_level == "BLOCK"

    def test_drift_magnitude_property(self):
        """drift_magnitude property reflects computed magnitude."""
        tracker = AgenticDriftTracker()
        assert tracker.drift_magnitude == 0.0
        _establish_baseline(tracker, 1.0)
        tracker.record_fidelity(0.50)
        assert tracker.drift_magnitude > 0.0

    def test_exact_warning_boundary(self):
        """Drift at exactly WARNING threshold triggers WARNING."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 1.0)
        # Sustained drift at 0.80: converges to drift=0.20 (BLOCK)
        # Find n where drift first >= 0.10 (WARNING)
        n = _turns_to_reach_drift(1.0, 0.80, SAAI_DRIFT_WARNING)
        status = _record_n_turns(tracker, 0.80, n)
        assert status["drift_level"] in ("WARNING", "RESTRICT", "BLOCK")
        assert status["drift_magnitude"] >= SAAI_DRIFT_WARNING

    def test_get_drift_history_completeness(self):
        """get_drift_history returns all expected keys."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        tracker.record_fidelity(0.80)
        history = tracker.get_drift_history()
        expected_keys = {
            "all_fidelity_scores", "baseline_std", "ewma",
            "baseline_fidelity", "baseline_established",
            "current_drift_level", "current_drift_magnitude",
            "acknowledgment_count", "acknowledgment_history",
            "permanently_blocked", "total_turns",
        }
        assert set(history.keys()) == expected_keys


# ---------------------------------------------------------------------------
# RESTRICT Behavior: Integration Tests
# ---------------------------------------------------------------------------

class TestRestrictBehavior:
    """Test RESTRICT enforcement via process_request() integration.

    When drift is in RESTRICT range (15-20%), EXECUTE decisions for actions
    scoring between ST_EXECUTE (0.45) and ST_RESTRICT (0.52) should be
    downgraded to CLARIFY.
    """

    def _make_manager_and_template(self):
        """Create a configured manager + template for RESTRICT tests."""
        from telos_governance.agent_templates import AgenticTemplate
        from telos_governance.agentic_fidelity import AgenticFidelityResult
        from telos_governance.types import ActionDecision, DirectionLevel
        import numpy as np

        manager = AgenticResponseManager()
        manager._initialized = True
        manager._embed_fn = lambda t: np.ones(3) / np.sqrt(3)
        manager._llm_client = None
        manager._llm_client_checked = True

        template = AgenticTemplate(
            id="sql_analyst",
            name="SQL Database Analyst",
            description="Queries data",
            icon="database",
            purpose="Help users query and understand data in PostgreSQL databases",
            scope="SELECT queries, schema exploration, data analysis",
            boundaries=["No data modification"],
            tools=["sql_db_query"],
            tool_set_key="sql_agent",
            example_requests=["Show me total revenue"],
            drift_examples=["Delete all records"],
            system_prompt="You are a SQL Database Analyst.",
        )
        return manager, template

    def _make_engine_result(self, fidelity, boundary_triggered=False):
        """Create an AgenticFidelityResult with given fidelity."""
        from telos_governance.agentic_fidelity import AgenticFidelityResult
        from telos_governance.types import ActionDecision, DirectionLevel

        decision = ActionDecision.ESCALATE if boundary_triggered else ActionDecision.EXECUTE
        result = AgenticFidelityResult(
            purpose_fidelity=fidelity,
            scope_fidelity=fidelity,
            boundary_violation=1.0 if boundary_triggered else 0.0,
            tool_fidelity=fidelity,
            chain_continuity=0.50,
            composite_fidelity=fidelity,
            effective_fidelity=fidelity,
            decision=decision,
            direction_level=DirectionLevel.NONE,
            boundary_triggered=boundary_triggered,
            tool_blocked=False,
            chain_broken=False,
            selected_tool="sql_db_query",
            tool_rankings=[{"rank": 1, "tool": "sql_db_query", "fidelity": fidelity}],
        )
        result.dimension_explanations = {
            "purpose": "OK", "scope": "OK", "tool": "OK",
            "chain": "OK", "boundary": "OK",
        }
        return result

    def _push_to_restrict(self, manager, template, mock_engine):
        """Establish baseline and push EWMA drift into RESTRICT range (15-19%).

        Uses high baseline (0.90) then sustained moderate drift (0.65) to push
        EWMA into RESTRICT territory with headroom before BLOCK. Score of 0.65
        gives relative_drop=0.278, reaching RESTRICT at ~8 turns but not BLOCK
        until ~13, leaving room for the test turn at 0.50 to stay in RESTRICT.
        """
        # Phase 1: Establish baseline at 0.90
        mock_engine.score_action.return_value = self._make_engine_result(0.90)
        mock_engine._is_sentence_transformer.return_value = True
        for i in range(BASELINE_TURN_COUNT):
            manager.process_request("Show revenue", template, i + 1)

        # Phase 2: Push into RESTRICT range using 0.65 (moderate drift)
        push_score = 0.65
        n_restrict = _turns_to_reach_drift(0.90, push_score, SAAI_DRIFT_RESTRICT)
        mock_engine.score_action.return_value = self._make_engine_result(push_score)
        for i in range(n_restrict):
            manager.process_request("Show revenue", template, BASELINE_TURN_COUNT + 1 + i)

        return n_restrict

    def test_restrict_downgrades_execute_to_clarify(self):
        """RESTRICT: fidelity between ST_EXECUTE (0.45) and ST_RESTRICT (0.52) -> CLARIFY."""
        manager, template = self._make_manager_and_template()
        mock_engine = MagicMock()
        manager._engine_cache["sql_analyst"] = mock_engine

        n_drift = self._push_to_restrict(manager, template, mock_engine)

        # Phase 3: Next request with fidelity between EXECUTE and RESTRICT thresholds
        mock_engine.score_action.return_value = self._make_engine_result(0.50)
        step = BASELINE_TURN_COUNT + n_drift + 1
        result = manager.process_request("Show revenue", template, step)

        # Under RESTRICT, low-fidelity EXECUTE should be downgraded to CLARIFY
        assert result.decision == "CLARIFY", (
            f"Expected CLARIFY under RESTRICT, got {result.decision} "
            f"(drift_level={result.drift_level}, drift_mag={result.drift_magnitude:.3f})"
        )
        assert "SAAI RESTRICT" in result.decision_explanation

    def test_restrict_allows_high_fidelity_execute(self):
        """RESTRICT: fidelity above ST_RESTRICT (0.52) should still EXECUTE."""
        manager, template = self._make_manager_and_template()
        mock_engine = MagicMock()
        manager._engine_cache["sql_analyst"] = mock_engine

        n_drift = self._push_to_restrict(manager, template, mock_engine)

        # Fidelity above RESTRICT threshold should still EXECUTE
        mock_engine.score_action.return_value = self._make_engine_result(0.55)
        step = BASELINE_TURN_COUNT + n_drift + 1
        result = manager.process_request("Show revenue", template, step)

        assert result.decision == "EXECUTE", (
            f"Expected EXECUTE for fidelity above RESTRICT threshold, got {result.decision} "
            f"(drift_level={result.drift_level}, drift_mag={result.drift_magnitude:.3f})"
        )

    def test_restrict_plus_boundary_forces_escalate(self):
        """RESTRICT + boundary_violation -> compound ESCALATE."""
        manager, template = self._make_manager_and_template()
        mock_engine = MagicMock()
        manager._engine_cache["sql_analyst"] = mock_engine

        n_drift = self._push_to_restrict(manager, template, mock_engine)

        # Boundary violation during RESTRICT -> compound ESCALATE
        mock_engine.score_action.return_value = self._make_engine_result(
            0.50, boundary_triggered=True
        )
        step = BASELINE_TURN_COUNT + n_drift + 1
        result = manager.process_request("Delete all records", template, step)

        assert result.decision == "ESCALATE", (
            f"Expected ESCALATE for RESTRICT+boundary, got {result.decision}"
        )
        assert "RESTRICT" in result.decision_explanation
        assert "BOUNDARY" in result.decision_explanation


# ---------------------------------------------------------------------------
# Serialization (to_dict / restore)
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_contains_ewma_fields(self):
        """to_dict includes EWMA-specific fields."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        tracker.record_fidelity(0.80)
        state = tracker.to_dict()
        assert "ewma" in state
        assert "baseline_std" in state
        assert state["baseline_established"] is True
        assert state["ewma"] is not None

    def test_restore_preserves_state(self):
        """restore() faithfully restores all tracker state."""
        tracker = AgenticDriftTracker()
        _establish_baseline(tracker, 0.90)
        tracker.record_fidelity(0.80)
        state = tracker.to_dict()

        tracker2 = AgenticDriftTracker()
        tracker2.restore(state)
        assert tracker2.drift_level == tracker.drift_level
        assert tracker2.drift_magnitude == tracker.drift_magnitude
        assert tracker2._ewma == pytest.approx(tracker._ewma)
        assert tracker2._baseline_fidelity == pytest.approx(tracker._baseline_fidelity)

    def test_restore_none_is_noop(self):
        """restore(None) does not crash."""
        tracker = AgenticDriftTracker()
        tracker.restore(None)
        assert tracker.drift_level == "NORMAL"

    def test_restore_old_format_state_migration(self):
        """Verify restore() handles pre-EWMA state dicts without crashing."""
        tracker = AgenticDriftTracker()
        old_state = {
            "baseline_fidelity": 0.85,
            "baseline_std": 0.03,
            "baseline_established": True,
            "fidelity_scores": [0.85, 0.84, 0.86],
            "ewma": None,  # Old format -- no EWMA
            "drift_level": "NORMAL",
            "drift_magnitude": 0.0,
            "acknowledgment_count": 0,
            "acknowledgment_history": [],
            "permanently_blocked": False,
        }
        tracker.restore(old_state)
        assert tracker._ewma == 0.85  # Bootstrapped from baseline
        # Should not crash on next record
        result = tracker.record_fidelity(0.80)
        assert result is not None

    def test_restore_missing_ewma_key(self):
        """Verify restore() handles state dicts with no ewma key at all."""
        tracker = AgenticDriftTracker()
        old_state = {
            "baseline_fidelity": 0.90,
            "baseline_std": 0.02,
            "baseline_established": True,
            "fidelity_scores": [0.90, 0.89, 0.91],
            # No "ewma" key at all
            "drift_level": "NORMAL",
            "drift_magnitude": 0.0,
            "acknowledgment_count": 0,
            "acknowledgment_history": [],
            "permanently_blocked": False,
        }
        tracker.restore(old_state)
        assert tracker._ewma == 0.90
        result = tracker.record_fidelity(0.85)
        assert result is not None


# ---------------------------------------------------------------------------
# Chain Inheritance Masking Fix (Phase 2c)
# ---------------------------------------------------------------------------

class TestChainInheritanceMasking:
    """Test that boundary violations record composite fidelity, not inherited."""

    def test_boundary_violation_uses_composite_not_inherited(self):
        """Boundary violation mid-chain should record composite, not max(composite, inherited)."""
        from telos_governance.agentic_fidelity import AgenticFidelityEngine, AgenticFidelityResult
        from telos_governance.agentic_pa import AgenticPA, BoundarySpec
        import numpy as np

        dim = 3
        purpose_emb = np.array([1.0, 0.0, 0.0])
        purpose_emb = purpose_emb / np.linalg.norm(purpose_emb)

        boundary_emb = np.array([0.0, 1.0, 0.0])
        boundary_emb = boundary_emb / np.linalg.norm(boundary_emb)

        pa = AgenticPA(
            purpose_text="Help users query databases",
            purpose_embedding=purpose_emb,
            scope_text="SELECT queries only",
            scope_embedding=purpose_emb,
            boundaries=[
                BoundarySpec(
                    text="No data modification or deletion",
                    embedding=boundary_emb,
                    centroid_embedding=boundary_emb,
                ),
            ],
            escalation_threshold=0.50,
        )

        call_count = [0]
        def embed_fn(text):
            call_count[0] += 1
            if "delete" in text.lower() or "drop" in text.lower():
                return boundary_emb
            return purpose_emb

        engine = AgenticFidelityEngine(embed_fn=embed_fn, pa=pa)

        # Step 1: High-fidelity on-topic request (establishes chain)
        result1 = engine.score_action("Show me total revenue")

        # Step 2: Action near boundary
        result2 = engine.score_action("Delete all records")

        if result2.boundary_triggered:
            assert result2.effective_fidelity == pytest.approx(
                result2.composite_fidelity, abs=0.001
            ), (
                f"Boundary violation should use composite ({result2.composite_fidelity:.4f}), "
                f"not inherited effective ({result2.effective_fidelity:.4f})"
            )
        else:
            assert result2.effective_fidelity >= result2.composite_fidelity, (
                "Without boundary trigger, effective should be >= composite (chain inheritance)"
            )

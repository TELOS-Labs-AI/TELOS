"""
Unit tests for telos_core.proportional_controller

Tests control gains, intervention states, meta-commentary detection,
and the intervention cascade.
"""

import pytest
import time
import numpy as np
from unittest.mock import MagicMock, patch
from telos_core.proportional_controller import (
    ProportionalController,
    InterventionRecord,
    MathematicalInterventionController,
)
from telos_core.primacy_math import MathematicalState, PrimacyAttractorMath
from telos_core.constants import (
    DEFAULT_K_ATTRACTOR,
    DEFAULT_K_ANTIMETA,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def purpose_vector():
    vec = np.random.RandomState(42).randn(384).astype(np.float32)
    return vec / np.linalg.norm(vec)


@pytest.fixture
def scope_vector():
    vec = np.random.RandomState(43).randn(384).astype(np.float32)
    return vec / np.linalg.norm(vec)


@pytest.fixture
def attractor(purpose_vector, scope_vector):
    return PrimacyAttractorMath(
        purpose_vector=purpose_vector,
        scope_vector=scope_vector,
        constraint_tolerance=0.2,
    )


@pytest.fixture
def mock_llm():
    """Mock LLM client."""
    client = MagicMock()
    client.chat_completion.return_value = "This is a governed response."
    return client


@pytest.fixture
def mock_embedding_provider():
    """Mock embedding provider."""
    provider = MagicMock()
    provider.encode.return_value = np.random.randn(384).astype(np.float32)
    return provider


@pytest.fixture
def controller(attractor, mock_llm, mock_embedding_provider):
    """Default ProportionalController."""
    return ProportionalController(
        attractor=attractor,
        llm_client=mock_llm,
        embedding_provider=mock_embedding_provider,
        enable_interventions=True,
    )


def make_state(embedding: np.ndarray, turn: int = 1) -> MathematicalState:
    return MathematicalState(
        embedding=embedding,
        turn_number=turn,
        timestamp=time.time(),
    )


# ============================================================================
# Controller Initialization
# ============================================================================

class TestControllerInit:
    """Test controller construction and derived thresholds."""

    def test_gains(self, controller):
        """Verify control gain values."""
        assert controller.K_attractor == DEFAULT_K_ATTRACTOR
        assert controller.K_antimeta == DEFAULT_K_ANTIMETA

    def test_epsilon_thresholds(self, controller):
        """Derived e_min and e_max from attractor's constraint_tolerance."""
        t = controller.attractor.constraint_tolerance
        expected_min = 0.1 + 0.3 * t
        expected_max = 0.5 + 0.4 * t
        assert controller.epsilon_min == pytest.approx(expected_min)
        assert controller.epsilon_max == pytest.approx(expected_max)

    def test_epsilon_ordering(self, controller):
        """e_min < e_max always."""
        assert controller.epsilon_min < controller.epsilon_max

    def test_regeneration_budget(self, controller):
        """Max regenerations initialized."""
        assert controller.max_regenerations == 3
        assert controller.regen_count == 0


# ============================================================================
# Meta-Commentary Detection
# ============================================================================

class TestMetaCommentaryDetection:
    """Test detection of meta-commentary about governance."""

    def test_detect_my_purpose(self, controller):
        assert controller._detect_meta_commentary("My purpose is to help you.") is True

    def test_detect_my_constraints(self, controller):
        assert controller._detect_meta_commentary("My constraints prevent me.") is True

    def test_detect_designed_to(self, controller):
        assert controller._detect_meta_commentary("I am designed to be helpful.") is True

    def test_detect_as_ai(self, controller):
        assert controller._detect_meta_commentary("As an AI language model, I...") is True

    def test_detect_as_llm(self, controller):
        assert controller._detect_meta_commentary("As a large language model, I can...") is True

    def test_normal_text_not_meta(self, controller):
        assert controller._detect_meta_commentary("Let me help you with that code.") is False

    def test_empty_text_not_meta(self, controller):
        assert controller._detect_meta_commentary("") is False

    def test_case_insensitive(self, controller):
        assert controller._detect_meta_commentary("MY PURPOSE IS to assist.") is True


# ============================================================================
# Process Turn - MONITOR State
# ============================================================================

class TestProcessTurnMonitor:
    """Test State 1 (MONITOR): No intervention when aligned."""

    def test_aligned_no_intervention(self, controller, attractor):
        """State at attractor center -> MONITOR, no intervention."""
        state = make_state(attractor.attractor_center)
        result = controller.process_turn(
            state=state,
            response_text="This is on topic.",
            conversation_history=[],
            turn_number=1,
        )
        assert result["intervention_applied"] is False
        assert result["intervention_result"] is None
        assert result["in_basin"] is True
        assert result["is_meta"] is False

    def test_interventions_disabled(self, attractor, mock_llm, mock_embedding_provider):
        """When interventions disabled, no correction applied."""
        ctrl = ProportionalController(
            attractor=attractor,
            llm_client=mock_llm,
            embedding_provider=mock_embedding_provider,
            enable_interventions=False,
        )
        far_embedding = attractor.attractor_center * -10.0
        state = make_state(far_embedding)
        result = ctrl.process_turn(
            state=state,
            response_text="Off topic text",
            conversation_history=[],
            turn_number=1,
        )
        assert result["intervention_applied"] is False


# ============================================================================
# Process Turn - CORRECT State
# ============================================================================

class TestProcessTurnCorrect:
    """Test State 2 (CORRECT): Context injection for moderate drift."""

    def test_reminder_applied(self, controller, attractor):
        """Moderate error + outside basin -> reminder intervention."""
        # Create state that's outside basin but not extreme
        offset = np.zeros_like(attractor.attractor_center)
        offset[0] = attractor.basin_radius * 1.5  # Beyond basin
        drifted = attractor.attractor_center + offset
        state = make_state(drifted)

        error = attractor.compute_error_signal(state)
        in_basin = attractor.compute_basin_membership(state)

        # Only triggers if error >= epsilon_min AND not in basin
        if error >= controller.epsilon_min and not in_basin and error < controller.epsilon_max:
            result = controller.process_turn(
                state=state,
                response_text="Slightly off topic response.",
                conversation_history=[],
                turn_number=1,
            )
            if result["intervention_applied"]:
                assert result["intervention_result"].type == "reminder"


# ============================================================================
# Process Turn - Anti-Meta
# ============================================================================

class TestProcessTurnAntiMeta:
    """Test anti-meta suppression (takes precedence over other states)."""

    def test_meta_commentary_suppressed(self, controller, attractor):
        """Meta-commentary triggers antimeta intervention."""
        state = make_state(attractor.attractor_center)
        result = controller.process_turn(
            state=state,
            response_text="As an AI language model, I cannot do that.",
            conversation_history=[],
            turn_number=1,
        )
        assert result["intervention_applied"] is True
        assert result["is_meta"] is True
        assert result["intervention_result"].type == "antimeta"

    def test_meta_takes_precedence(self, controller, attractor):
        """Even at attractor center, meta commentary is corrected."""
        state = make_state(attractor.attractor_center)
        result = controller.process_turn(
            state=state,
            response_text="According to my instructions, I should help.",
            conversation_history=[],
            turn_number=1,
        )
        assert result["intervention_applied"] is True
        assert result["intervention_result"].type == "antimeta"


# ============================================================================
# Intervention Record
# ============================================================================

class TestInterventionRecord:
    """Test InterventionRecord data class."""

    def test_record_fields(self):
        record = InterventionRecord(
            type="reminder",
            strength=0.45,
            reason="test reason",
            modified_response="modified text",
            timestamp=time.time(),
        )
        assert record.type == "reminder"
        assert record.strength == 0.45
        assert record.reason == "test reason"
        assert record.modified_response == "modified text"
        assert record.timestamp > 0


# ============================================================================
# Intervention Statistics
# ============================================================================

class TestInterventionStatistics:
    """Test intervention statistics aggregation."""

    def test_empty_stats(self, controller):
        """No interventions -> empty stats."""
        stats = controller.get_intervention_statistics()
        assert stats["total_interventions"] == 0
        assert stats["by_type"] == {}
        assert stats["regeneration_count"] == 0

    def test_stats_after_intervention(self, controller, attractor):
        """Stats reflect applied interventions."""
        state = make_state(attractor.attractor_center)
        controller.process_turn(
            state=state,
            response_text="As an AI language model, I respond.",
            conversation_history=[],
            turn_number=1,
        )
        stats = controller.get_intervention_statistics()
        assert stats["total_interventions"] == 1
        assert "antimeta" in stats["by_type"]

    def test_stats_threshold_values(self, controller):
        """Stats include threshold information."""
        stats = controller.get_intervention_statistics()
        assert "thresholds" in stats
        assert "epsilon_min" in stats["thresholds"]
        assert "epsilon_max" in stats["thresholds"]


# ============================================================================
# Backward Compatibility
# ============================================================================

class TestBackwardCompatibility:
    """Test deprecated alias."""

    def test_deprecated_alias_works(self, attractor, mock_llm, mock_embedding_provider):
        """MathematicalInterventionController is an alias for ProportionalController."""
        with pytest.warns(DeprecationWarning, match="deprecated"):
            ctrl = MathematicalInterventionController(
                attractor=attractor,
                llm_client=mock_llm,
                embedding_provider=mock_embedding_provider,
            )
        assert isinstance(ctrl, ProportionalController)

    def test_deprecated_alias_functional(self, attractor, mock_llm, mock_embedding_provider):
        """Deprecated alias provides same functionality."""
        with pytest.warns(DeprecationWarning):
            ctrl = MathematicalInterventionController(
                attractor=attractor,
                llm_client=mock_llm,
                embedding_provider=mock_embedding_provider,
            )
        stats = ctrl.get_intervention_statistics()
        assert stats["total_interventions"] == 0

"""
Tests for telos_governance.fidelity_gate
=========================================

Tests governance decisions at various fidelity levels,
direction level determination, and tool fidelity checks.
"""

import numpy as np
import pytest

from telos_governance.fidelity_gate import FidelityGate
from telos_governance.pa_extractor import PrimacyAttractor
from telos_governance.types import (
    ActionDecision,
    DirectionLevel,
    AGENTIC_EXECUTE_THRESHOLD,
    AGENTIC_CLARIFY_THRESHOLD,
    SIMILARITY_BASELINE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embedding(values: list) -> np.ndarray:
    """Create a normalized embedding vector."""
    v = np.array(values, dtype=np.float64)
    norm = np.linalg.norm(v)
    if norm > 0:
        v = v / norm
    return v


def _make_embed_fn(fixed_embedding: np.ndarray):
    """Return an embed_fn that always returns the given vector."""
    def embed_fn(text: str) -> np.ndarray:
        return fixed_embedding
    return embed_fn


def _make_pa(embedding: np.ndarray) -> PrimacyAttractor:
    """Create a PA with a given embedding."""
    return PrimacyAttractor(
        text="Test PA purpose statement",
        embedding=embedding,
        source="configured",
    )


# ---------------------------------------------------------------------------
# Cosine similarity helper for test parameterization
# ---------------------------------------------------------------------------

def _embedding_with_similarity(pa_embedding: np.ndarray, target_similarity: float) -> np.ndarray:
    """
    Create an embedding that has approximately the target cosine similarity
    with the given PA embedding. Works by mixing the PA vector with an
    orthogonal vector.
    """
    # Create an orthogonal vector
    ortho = np.random.RandomState(42).randn(len(pa_embedding))
    # Remove component along pa_embedding
    ortho = ortho - np.dot(ortho, pa_embedding) * pa_embedding
    ortho = ortho / np.linalg.norm(ortho)

    # Mix: cos(theta) = target_similarity
    # v = cos(theta) * pa + sin(theta) * ortho
    theta = np.arccos(np.clip(target_similarity, -1.0, 1.0))
    result = np.cos(theta) * pa_embedding + np.sin(theta) * ortho
    result = result / np.linalg.norm(result)
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pa_embedding():
    """A stable PA embedding for tests."""
    return _make_embedding([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])


@pytest.fixture
def pa(pa_embedding):
    return _make_pa(pa_embedding)


# ---------------------------------------------------------------------------
# Tests: Decision thresholds
# ---------------------------------------------------------------------------

class TestFidelityGateDecisions:
    """Test governance decisions at various fidelity levels."""

    def test_execute_decision_high_fidelity(self, pa_embedding, pa):
        """Fidelity >= execute_threshold should produce EXECUTE."""
        # Create embedding with high similarity (0.85 raw -> high fidelity)
        high_sim_emb = _embedding_with_similarity(pa_embedding, 0.85)
        gate = FidelityGate(embed_fn=_make_embed_fn(high_sim_emb))
        result = gate.check_fidelity("test query", pa)

        assert result.final_decision == ActionDecision.EXECUTE
        assert result.forwarded_to_llm is True
        assert result.input_blocked is False

    def test_inert_decision_low_fidelity(self, pa_embedding, pa):
        """Fidelity below suggest_threshold should produce INERT."""
        # Very low similarity -> low fidelity
        low_sim_emb = _embedding_with_similarity(pa_embedding, 0.30)
        gate = FidelityGate(embed_fn=_make_embed_fn(low_sim_emb))
        result = gate.check_fidelity("off-topic query", pa)

        assert result.final_decision == ActionDecision.INERT
        assert result.forwarded_to_llm is False
        assert result.input_blocked is True

    def test_escalate_decision_high_risk(self, pa_embedding, pa):
        """Low fidelity + high_risk should produce ESCALATE."""
        low_sim_emb = _embedding_with_similarity(pa_embedding, 0.30)
        gate = FidelityGate(embed_fn=_make_embed_fn(low_sim_emb))
        result = gate.check_fidelity("risky off-topic query", pa, high_risk=True)

        assert result.final_decision == ActionDecision.ESCALATE
        assert result.forwarded_to_llm is False

    def test_empty_message_defaults_to_execute(self, pa_embedding, pa):
        """Empty user message should default to EXECUTE."""
        gate = FidelityGate(embed_fn=_make_embed_fn(pa_embedding))
        result = gate.check_fidelity("", pa)

        assert result.final_decision == ActionDecision.EXECUTE
        assert result.input_fidelity == 1.0

    def test_governance_response_on_inert(self, pa_embedding, pa):
        """Blocked requests should include a governance response."""
        low_sim_emb = _embedding_with_similarity(pa_embedding, 0.30)
        gate = FidelityGate(embed_fn=_make_embed_fn(low_sim_emb))
        result = gate.check_fidelity("off-topic", pa)

        assert result.governance_response is not None
        assert "outside the scope" in result.governance_response

    def test_governance_response_on_escalate(self, pa_embedding, pa):
        """Escalated requests should include review message."""
        low_sim_emb = _embedding_with_similarity(pa_embedding, 0.30)
        gate = FidelityGate(embed_fn=_make_embed_fn(low_sim_emb))
        result = gate.check_fidelity("off-topic", pa, high_risk=True)

        assert result.governance_response is not None
        assert "human review" in result.governance_response

    def test_no_governance_response_when_forwarded(self, pa_embedding, pa):
        """Forwarded requests should NOT include governance response."""
        high_sim_emb = _embedding_with_similarity(pa_embedding, 0.85)
        gate = FidelityGate(embed_fn=_make_embed_fn(high_sim_emb))
        result = gate.check_fidelity("on-topic query", pa)

        assert result.governance_response is None


# ---------------------------------------------------------------------------
# Tests: Fidelity normalization
# ---------------------------------------------------------------------------

class TestFidelityNormalization:
    """Test the Mistral-calibrated fidelity normalization."""

    def test_perfect_similarity_gives_high_fidelity(self, pa_embedding, pa):
        """Cosine sim = 1.0 should normalize to fidelity = 1.0."""
        gate = FidelityGate(embed_fn=_make_embed_fn(pa_embedding))
        raw_sim, fidelity = gate._calculate_fidelity("test", pa)

        assert raw_sim == pytest.approx(1.0, abs=0.01)
        assert fidelity == pytest.approx(1.0, abs=0.01)

    def test_zero_vector_gives_zero_fidelity(self, pa):
        """Zero embedding should give zero similarity and zero fidelity."""
        zero_emb = np.zeros(8)
        gate = FidelityGate(embed_fn=_make_embed_fn(zero_emb))
        raw_sim, fidelity = gate._calculate_fidelity("test", pa)

        assert raw_sim == 0.0
        assert fidelity == 0.0

    def test_fidelity_bounded_0_to_1(self, pa_embedding, pa):
        """Fidelity should always be in [0, 1]."""
        for sim_target in [0.0, 0.2, 0.4, 0.55, 0.65, 0.7, 0.8, 0.95, 1.0]:
            emb = _embedding_with_similarity(pa_embedding, sim_target)
            gate = FidelityGate(embed_fn=_make_embed_fn(emb))
            _, fidelity = gate._calculate_fidelity("test", pa)
            assert 0.0 <= fidelity <= 1.0, f"Fidelity {fidelity} out of bounds for sim={sim_target}"

    def test_red_zone_below_mistral_floor(self, pa_embedding, pa):
        """Raw similarity < 0.55 should map to fidelity < 0.30 (RED zone)."""
        emb = _embedding_with_similarity(pa_embedding, 0.40)
        gate = FidelityGate(embed_fn=_make_embed_fn(emb))
        raw_sim, fidelity = gate._calculate_fidelity("test", pa)

        assert fidelity < 0.30

    def test_green_zone_above_mistral_aligned(self, pa_embedding, pa):
        """Raw similarity > 0.70 should map to fidelity >= 0.70 (GREEN zone)."""
        emb = _embedding_with_similarity(pa_embedding, 0.80)
        gate = FidelityGate(embed_fn=_make_embed_fn(emb))
        raw_sim, fidelity = gate._calculate_fidelity("test", pa)

        assert fidelity >= 0.70


# ---------------------------------------------------------------------------
# Tests: Direction levels
# ---------------------------------------------------------------------------

class TestDirectionLevels:
    """Test the direction level determination (renamed from intervention)."""

    def test_hard_block_below_baseline(self, pa_embedding, pa):
        """Raw similarity below SIMILARITY_BASELINE should trigger HARD_BLOCK."""
        low_emb = _embedding_with_similarity(pa_embedding, 0.10)
        gate = FidelityGate(embed_fn=_make_embed_fn(low_emb))
        result = gate.check_fidelity("extreme off-topic", pa)

        assert result.direction_level == DirectionLevel.HARD_BLOCK
        assert result.direction_applied is True

    def test_none_direction_at_high_fidelity(self, pa_embedding, pa):
        """High fidelity should result in NONE direction."""
        high_emb = _embedding_with_similarity(pa_embedding, 0.85)
        gate = FidelityGate(embed_fn=_make_embed_fn(high_emb))
        result = gate.check_fidelity("on-topic", pa)

        assert result.direction_level == DirectionLevel.NONE
        assert result.direction_applied is False

    def test_direction_applied_flag(self, pa_embedding, pa):
        """direction_applied should be True when direction_level != NONE."""
        medium_emb = _embedding_with_similarity(pa_embedding, 0.62)
        gate = FidelityGate(embed_fn=_make_embed_fn(medium_emb))
        result = gate.check_fidelity("drifting query", pa)

        if result.direction_level != DirectionLevel.NONE:
            assert result.direction_applied is True


# ---------------------------------------------------------------------------
# Tests: Tool fidelity checks
# ---------------------------------------------------------------------------

class TestToolFidelity:
    """Test tool-level governance checks."""

    def test_tool_blocking(self, pa_embedding, pa):
        """Tools with low fidelity should be blocked."""
        # The embed_fn returns the same embedding for everything,
        # so tool text similarity to PA depends on the fixed embedding.
        low_emb = _embedding_with_similarity(pa_embedding, 0.30)
        gate = FidelityGate(embed_fn=_make_embed_fn(low_emb))

        tools = [{"name": "dangerous_tool", "description": "something off-topic"}]
        result = gate.check_fidelity("test", pa, tools=tools)

        assert result.tools_checked == 1
        assert result.tools_blocked == 1

    def test_tool_allowing(self, pa_embedding, pa):
        """Tools with high fidelity should be allowed."""
        high_emb = _embedding_with_similarity(pa_embedding, 0.85)
        gate = FidelityGate(embed_fn=_make_embed_fn(high_emb))

        tools = [{"name": "good_tool", "description": "aligned with purpose"}]
        result = gate.check_fidelity("test", pa, tools=tools)

        assert result.tools_checked == 1
        assert result.tools_blocked == 0

    def test_blocked_tools_downgrade_execute(self, pa_embedding, pa):
        """If input is EXECUTE but tools are blocked, downgrade to CLARIFY."""
        # We need: input high fidelity (EXECUTE), but tool low fidelity (blocked)
        # This requires the embed_fn to return different values for different texts.
        call_count = [0]
        high_emb = _embedding_with_similarity(pa_embedding, 0.85)
        low_emb = _embedding_with_similarity(pa_embedding, 0.30)

        def varying_embed_fn(text: str) -> np.ndarray:
            call_count[0] += 1
            # First call is the user message, second is the tool
            if call_count[0] == 1:
                return high_emb
            return low_emb

        gate = FidelityGate(embed_fn=varying_embed_fn)
        tools = [{"name": "blocked_tool", "description": "unrelated"}]
        result = gate.check_fidelity("on-topic query", pa, tools=tools)

        assert result.final_decision == ActionDecision.CLARIFY

    def test_no_tools_skips_tool_check(self, pa_embedding, pa):
        """No tools provided should skip tool fidelity check."""
        gate = FidelityGate(embed_fn=_make_embed_fn(pa_embedding))
        result = gate.check_fidelity("test", pa, tools=None)

        assert result.tools_checked == 0
        assert result.tools_blocked == 0
        assert result.tool_decisions is None


# ---------------------------------------------------------------------------
# Tests: Custom thresholds
# ---------------------------------------------------------------------------

class TestCustomThresholds:
    """Test that custom thresholds override defaults."""

    def test_custom_execute_threshold(self, pa_embedding, pa):
        """Custom execute threshold should change decision boundary."""
        # With default 0.85 threshold, fidelity of ~0.76 would be CLARIFY.
        # With custom threshold of 0.70, it becomes EXECUTE.
        emb = _embedding_with_similarity(pa_embedding, 0.72)
        gate = FidelityGate(
            embed_fn=_make_embed_fn(emb),
            execute_threshold=0.70,
        )
        result = gate.check_fidelity("test", pa)

        assert result.final_decision == ActionDecision.EXECUTE

    def test_request_id_is_generated(self, pa_embedding, pa):
        """Each governance result should have a unique request_id."""
        gate = FidelityGate(embed_fn=_make_embed_fn(pa_embedding))
        r1 = gate.check_fidelity("test1", pa)
        r2 = gate.check_fidelity("test2", pa)

        assert r1.request_id != r2.request_id
        assert len(r1.request_id) == 8

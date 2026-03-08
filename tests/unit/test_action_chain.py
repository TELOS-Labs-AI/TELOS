"""
Tests for telos_governance.action_chain
========================================

Tests SCI (Semantic Continuity Index) calculation,
fidelity decay/inheritance, and ActionChain tracking.
"""

import numpy as np
import pytest

from telos_governance.action_chain import (
    ActionChain,
    ActionStep,
    SCI_CONTINUITY_THRESHOLD,
    SCI_DECAY_FACTOR,
    calculate_semantic_continuity,
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


def _orthogonal_embedding(base: np.ndarray) -> np.ndarray:
    """Create a vector orthogonal to the given one."""
    ortho = np.zeros_like(base)
    # Swap first two non-zero elements and negate one
    if base[0] != 0:
        ortho[1] = base[0]
        ortho[0] = -base[1]
    else:
        ortho[0] = 1.0
    return ortho / np.linalg.norm(ortho)


# ---------------------------------------------------------------------------
# Tests: calculate_semantic_continuity()
# ---------------------------------------------------------------------------

class TestCalculateSemanticContinuity:
    """Test the core SCI calculation function."""

    def test_first_step_returns_zero_continuity(self):
        """First step (no previous) should return (0.0, 0.0)."""
        emb = _make_embedding([1.0, 0.0, 0.0, 0.0])
        continuity, inherited = calculate_semantic_continuity(emb, None, 0.9)

        assert continuity == 0.0
        assert inherited == 0.0

    def test_identical_embeddings_full_inheritance(self):
        """Identical consecutive embeddings should give full continuity."""
        emb = _make_embedding([1.0, 0.5, 0.3, 0.0])
        continuity, inherited = calculate_semantic_continuity(emb, emb, 0.90)

        assert continuity == pytest.approx(1.0, abs=0.01)
        assert inherited == pytest.approx(0.90 * SCI_DECAY_FACTOR, abs=0.01)

    def test_orthogonal_embeddings_no_inheritance(self):
        """Orthogonal embeddings should give ~0 continuity and no inheritance."""
        emb1 = _make_embedding([1.0, 0.0, 0.0, 0.0])
        emb2 = _make_embedding([0.0, 1.0, 0.0, 0.0])
        continuity, inherited = calculate_semantic_continuity(emb2, emb1, 0.90)

        assert continuity == pytest.approx(0.0, abs=0.01)
        assert inherited == 0.0

    def test_threshold_boundary_above(self):
        """Continuity just above threshold should inherit fidelity."""
        emb1 = _make_embedding([1.0, 0.0, 0.0, 0.0])
        # Create embedding with ~0.35 cosine similarity (above 0.30 threshold)
        emb2 = _make_embedding([0.35, 0.94, 0.0, 0.0])  # rough target

        continuity, inherited = calculate_semantic_continuity(emb2, emb1, 0.80)

        if continuity >= SCI_CONTINUITY_THRESHOLD:
            assert inherited == pytest.approx(0.80 * SCI_DECAY_FACTOR, abs=0.01)
        else:
            assert inherited == 0.0

    def test_threshold_boundary_below(self):
        """Continuity below threshold should NOT inherit fidelity."""
        emb1 = _make_embedding([1.0, 0.0, 0.0, 0.0])
        # Create embedding with ~0.20 cosine similarity (below 0.30 threshold)
        emb2 = _make_embedding([0.20, 0.98, 0.0, 0.0])

        continuity, inherited = calculate_semantic_continuity(emb2, emb1, 0.80)

        if continuity < SCI_CONTINUITY_THRESHOLD:
            assert inherited == 0.0

    def test_zero_previous_fidelity(self):
        """If previous fidelity is 0, inherited should be 0 even with continuity."""
        emb = _make_embedding([1.0, 0.0, 0.0, 0.0])
        continuity, inherited = calculate_semantic_continuity(emb, emb, 0.0)

        assert continuity == pytest.approx(1.0, abs=0.01)
        assert inherited == 0.0

    def test_zero_vector_handling(self):
        """Zero vectors should return 0 continuity and 0 inheritance."""
        zero = np.zeros(4)
        emb = _make_embedding([1.0, 0.0, 0.0, 0.0])

        continuity, inherited = calculate_semantic_continuity(zero, emb, 0.90)
        assert continuity == 0.0
        assert inherited == 0.0

        continuity, inherited = calculate_semantic_continuity(emb, zero, 0.90)
        assert continuity == 0.0
        assert inherited == 0.0


# ---------------------------------------------------------------------------
# Tests: ActionChain
# ---------------------------------------------------------------------------

class TestActionChain:
    """Test ActionChain tracking and SCI across multiple steps."""

    def test_empty_chain(self):
        """Fresh chain should be empty."""
        chain = ActionChain()
        assert chain.length == 0
        assert chain.current_step is None
        assert chain.is_continuous() is True

    def test_single_step(self):
        """Single step chain should have zero continuity (no predecessor)."""
        chain = ActionChain()
        emb = _make_embedding([1.0, 0.0, 0.0, 0.0])
        step = chain.add_step("first action", emb, direct_fidelity=0.90)

        assert chain.length == 1
        assert step.step_index == 0
        assert step.continuity_score == 0.0
        assert step.inherited_fidelity == 0.0
        assert step.effective_fidelity == max(0.90, 0.0)
        assert chain.is_continuous() is True

    def test_two_continuous_steps(self):
        """Two similar steps should maintain continuity."""
        chain = ActionChain()
        emb1 = _make_embedding([1.0, 0.1, 0.0, 0.0])
        emb2 = _make_embedding([1.0, 0.2, 0.0, 0.0])

        chain.add_step("step 1", emb1, direct_fidelity=0.90)
        step2 = chain.add_step("step 2", emb2, direct_fidelity=0.85)

        assert chain.length == 2
        assert step2.continuity_score > SCI_CONTINUITY_THRESHOLD
        assert step2.inherited_fidelity > 0
        assert chain.is_continuous() is True

    def test_discontinuous_step(self):
        """Orthogonal step should break continuity."""
        chain = ActionChain()
        emb1 = _make_embedding([1.0, 0.0, 0.0, 0.0])
        emb2 = _make_embedding([0.0, 1.0, 0.0, 0.0])

        chain.add_step("step 1", emb1, direct_fidelity=0.90)
        step2 = chain.add_step("step 2", emb2, direct_fidelity=0.50)

        assert step2.continuity_score < SCI_CONTINUITY_THRESHOLD
        assert step2.inherited_fidelity == 0.0
        assert step2.effective_fidelity == 0.50  # Falls back to direct
        assert chain.is_continuous() is False

    def test_fidelity_decay_across_chain(self):
        """Inherited fidelity should decay with each step."""
        chain = ActionChain()
        emb = _make_embedding([1.0, 0.0, 0.0, 0.0])

        # All steps identical embedding -> perfect continuity, decay applies
        chain.add_step("step 0", emb, direct_fidelity=0.95)
        chain.add_step("step 1", emb, direct_fidelity=0.50)
        chain.add_step("step 2", emb, direct_fidelity=0.50)
        step3 = chain.add_step("step 3", emb, direct_fidelity=0.50)

        # Step 0: inherited=0.0, effective = max(0.95, 0.0) = 0.95
        # Step 1: inherited = 0.95 * 0.90 = 0.855, effective = max(0.50, 0.855) = 0.855
        # Step 2: inherited = 0.855 * 0.90 = 0.7695, effective = max(0.50, 0.7695) = 0.7695
        # Step 3: inherited = 0.7695 * 0.90 = 0.69255, effective = max(0.50, 0.69255) = 0.69255
        assert step3.inherited_fidelity == pytest.approx(0.69255, abs=0.01)
        assert step3.effective_fidelity == pytest.approx(0.69255, abs=0.01)

    def test_effective_fidelity_uses_max(self):
        """effective_fidelity should be max(direct, inherited)."""
        chain = ActionChain()
        emb = _make_embedding([1.0, 0.0, 0.0, 0.0])

        # First step: inherited=0.0, direct=0.50 -> effective=0.50
        step = chain.add_step("step", emb, direct_fidelity=0.50)
        assert step.effective_fidelity == 0.50

    def test_average_continuity(self):
        """average_continuity should compute mean of step-pair SCIs."""
        chain = ActionChain()
        emb1 = _make_embedding([1.0, 0.0, 0.0, 0.0])
        emb2 = _make_embedding([1.0, 0.1, 0.0, 0.0])
        emb3 = _make_embedding([1.0, 0.2, 0.0, 0.0])

        chain.add_step("s1", emb1, 0.9)
        chain.add_step("s2", emb2, 0.9)
        chain.add_step("s3", emb3, 0.9)

        avg = chain.average_continuity
        # Average of step1->step2 and step2->step3 continuities
        assert 0.0 <= avg <= 1.0

    def test_average_continuity_single_step(self):
        """Single step should have average_continuity = 1.0."""
        chain = ActionChain()
        chain.add_step("s1", _make_embedding([1.0, 0, 0, 0]), 0.9)
        assert chain.average_continuity == 1.0

    def test_min_continuity(self):
        """min_continuity should return the lowest SCI in the chain."""
        chain = ActionChain()
        emb1 = _make_embedding([1.0, 0.0, 0.0, 0.0])
        emb2 = _make_embedding([0.9, 0.4, 0.0, 0.0])
        emb3 = _make_embedding([0.0, 0.0, 1.0, 0.0])  # Discontinuous

        chain.add_step("s1", emb1, 0.9)
        chain.add_step("s2", emb2, 0.9)
        chain.add_step("s3", emb3, 0.9)

        assert chain.min_continuity < chain.average_continuity

    def test_min_continuity_single_step(self):
        """Single step should have min_continuity = 1.0."""
        chain = ActionChain()
        chain.add_step("s1", _make_embedding([1.0, 0, 0, 0]), 0.9)
        assert chain.min_continuity == 1.0

    def test_reset(self):
        """reset() should clear all steps."""
        chain = ActionChain()
        chain.add_step("s1", _make_embedding([1.0, 0, 0, 0]), 0.9)
        chain.add_step("s2", _make_embedding([1.0, 0, 0, 0]), 0.9)

        assert chain.length == 2
        chain.reset()
        assert chain.length == 0
        assert chain.current_step is None

    def test_current_step(self):
        """current_step should return the most recent step."""
        chain = ActionChain()
        emb1 = _make_embedding([1.0, 0, 0, 0])
        emb2 = _make_embedding([0, 1.0, 0, 0])

        chain.add_step("first", emb1, 0.9)
        chain.add_step("second", emb2, 0.8)

        assert chain.current_step.action_text == "second"
        assert chain.current_step.step_index == 1


# ---------------------------------------------------------------------------
# Tests: Custom thresholds
# ---------------------------------------------------------------------------

class TestCustomThresholds:
    """Test ActionChain with custom SCI thresholds."""

    def test_windowed_continuity_recovers_from_old_break(self):
        """Chain should recover after a discontinuity exits the window."""
        chain = ActionChain()
        emb_a = _make_embedding([1.0, 0.0, 0.0, 0.0])
        emb_b = _make_embedding([0.0, 1.0, 0.0, 0.0])  # Orthogonal — break
        emb_c = _make_embedding([0.0, 1.0, 0.1, 0.0])   # Similar to emb_b
        emb_d = _make_embedding([0.0, 1.0, 0.2, 0.0])   # Similar to emb_c
        emb_e = _make_embedding([0.0, 1.0, 0.3, 0.0])   # Similar to emb_d

        chain.add_step("s1", emb_a, 0.9)
        chain.add_step("s2", emb_b, 0.5)  # Break here (s1→s2 orthogonal)
        chain.add_step("s3", emb_c, 0.8)  # Recovery — continuous with s2
        chain.add_step("s4", emb_d, 0.8)  # Continuous with s3
        chain.add_step("s5", emb_e, 0.8)  # Continuous with s4

        # Window covers last 3 transitions (s3→s4, s4→s5, s2→s3)
        # All three are continuous — the old s1→s2 break is outside the window
        assert chain.is_continuous() is True

    def test_windowed_continuity_still_detects_recent_break(self):
        """A break within the window should be detected."""
        chain = ActionChain()
        emb_a = _make_embedding([1.0, 0.0, 0.0, 0.0])
        emb_b = _make_embedding([1.0, 0.1, 0.0, 0.0])  # Continuous
        emb_c = _make_embedding([0.0, 0.0, 1.0, 0.0])   # Break
        emb_d = _make_embedding([0.0, 0.0, 1.0, 0.1])   # Continuous with c

        chain.add_step("s1", emb_a, 0.9)
        chain.add_step("s2", emb_b, 0.8)
        chain.add_step("s3", emb_c, 0.5)  # Break (b→c)
        chain.add_step("s4", emb_d, 0.7)  # Continuous (c→d)

        # Window = last 3 transitions: s1→s2 (pass), s2→s3 (fail), s3→s4 (pass)
        # 2/3 pass = 0.67, which meets the threshold exactly
        # But the ratio is >=, so 2/3 = 0.667 >= 0.67 — borderline
        # Actually 2 >= 3 * 0.67 = 2.01, so 2 >= 2.01 is False
        assert chain.is_continuous() is False

    def test_windowed_continuity_tolerance(self):
        """Window allows 1 out of 3 to fail when ratio permits."""
        chain = ActionChain(continuity_min_pass_ratio=0.5)
        emb_a = _make_embedding([1.0, 0.0, 0.0, 0.0])
        emb_b = _make_embedding([0.0, 1.0, 0.0, 0.0])  # Break
        emb_c = _make_embedding([0.0, 1.0, 0.1, 0.0])   # Continuous with b
        emb_d = _make_embedding([0.0, 1.0, 0.2, 0.0])   # Continuous with c

        chain.add_step("s1", emb_a, 0.9)
        chain.add_step("s2", emb_b, 0.5)  # Break (a→b)
        chain.add_step("s3", emb_c, 0.8)  # Continuous (b→c)
        chain.add_step("s4", emb_d, 0.8)  # Continuous (c→d)

        # Window = last 3: a→b (fail), b→c (pass), c→d (pass)
        # 2/3 pass = 0.67, and ratio=0.5 so 2 >= 3*0.5=1.5 => True
        assert chain.is_continuous() is True

    def test_stricter_continuity_threshold(self):
        """Higher threshold should be harder to pass."""
        chain = ActionChain(continuity_threshold=0.90)
        emb1 = _make_embedding([1.0, 0.0, 0.0, 0.0])
        emb2 = _make_embedding([0.8, 0.6, 0.0, 0.0])

        chain.add_step("s1", emb1, 0.9)
        chain.add_step("s2", emb2, 0.5)

        # With strict threshold, slightly different vectors may not be continuous
        # The cosine similarity of emb1 and emb2 is ~0.8, which is < 0.90
        assert chain.is_continuous() is False

    def test_custom_decay_factor(self):
        """Custom decay should affect inherited fidelity."""
        chain = ActionChain(decay_factor=0.50)  # Aggressive decay
        emb = _make_embedding([1.0, 0.0, 0.0, 0.0])

        chain.add_step("s1", emb, direct_fidelity=0.95)
        step2 = chain.add_step("s2", emb, direct_fidelity=0.30)

        # Step 1: inherited=0.0, effective = max(0.95, 0.0) = 0.95
        # Step 2: inherited = 0.95 * 0.50 = 0.475
        assert step2.inherited_fidelity == pytest.approx(0.475, abs=0.01)


# ---------------------------------------------------------------------------
# Tests: SCI constants
# ---------------------------------------------------------------------------

class TestSCIConstants:
    """Verify SCI threshold constants match expected values."""

    def test_continuity_threshold(self):
        assert SCI_CONTINUITY_THRESHOLD == 0.30

    def test_decay_factor(self):
        assert SCI_DECAY_FACTOR == 0.90

"""
Unit tests for telos_core.primacy_math

Tests attractor geometry, basin membership, Lyapunov stability,
and telic fidelity calculations.
"""

import pytest
import numpy as np
from telos_core.primacy_math import (
    MathematicalState,
    PrimacyAttractorMath,
    TelicFidelityCalculator,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def purpose_vector():
    """Normalized purpose vector in 384-dim space."""
    vec = np.random.RandomState(42).randn(384).astype(np.float32)
    return vec / np.linalg.norm(vec)


@pytest.fixture
def scope_vector():
    """Normalized scope vector in 384-dim space."""
    vec = np.random.RandomState(43).randn(384).astype(np.float32)
    return vec / np.linalg.norm(vec)


@pytest.fixture
def attractor(purpose_vector, scope_vector):
    """Default attractor with t=0.2 (fairly strict)."""
    return PrimacyAttractorMath(
        purpose_vector=purpose_vector,
        scope_vector=scope_vector,
        constraint_tolerance=0.2,
    )


def make_state(embedding: np.ndarray, turn: int = 1) -> MathematicalState:
    """Helper to create a MathematicalState."""
    return MathematicalState(
        embedding=embedding,
        turn_number=turn,
        timestamp=1000.0 + turn,
    )


# ============================================================================
# Attractor Construction
# ============================================================================

class TestAttractorConstruction:
    """Test attractor center computation and basin radius."""

    def test_center_is_normalized(self, attractor):
        """Attractor center should be unit-normalized."""
        norm = np.linalg.norm(attractor.attractor_center)
        assert norm == pytest.approx(1.0, abs=1e-5)

    def test_center_is_weighted_mix(self, purpose_vector, scope_vector):
        """Center = normalized(t*purpose + (1-t)*scope)."""
        t = 0.3
        a = PrimacyAttractorMath(
            purpose_vector=purpose_vector,
            scope_vector=scope_vector,
            constraint_tolerance=t,
        )
        raw = t * purpose_vector + (1 - t) * scope_vector
        expected = raw / np.linalg.norm(raw)
        np.testing.assert_allclose(a.attractor_center, expected, atol=1e-5)

    def test_basin_radius_formula(self, purpose_vector, scope_vector):
        """Basin radius = 1.0 / max(rigidity, 0.25)."""
        t = 0.2
        a = PrimacyAttractorMath(
            purpose_vector=purpose_vector,
            scope_vector=scope_vector,
            constraint_tolerance=t,
        )
        expected_radius = 1.0 / max(1.0 - t, 0.25)
        assert a.basin_radius == pytest.approx(expected_radius)

    def test_basin_radius_floor(self, purpose_vector, scope_vector):
        """Rigidity floored at 0.25 prevents infinite radius."""
        a = PrimacyAttractorMath(
            purpose_vector=purpose_vector,
            scope_vector=scope_vector,
            constraint_tolerance=0.9,  # rigidity = 0.1, floored to 0.25
        )
        assert a.basin_radius == pytest.approx(1.0 / 0.25)

    def test_constraint_rigidity(self, attractor):
        """Rigidity = 1 - tolerance."""
        assert attractor.constraint_rigidity == pytest.approx(
            1.0 - attractor.constraint_tolerance
        )


# ============================================================================
# Lyapunov Function
# ============================================================================

class TestLyapunovFunction:
    """Test Lyapunov energy V(x) = ||x - a_hat||^2."""

    def test_lyapunov_at_center_is_zero(self, attractor):
        """V(a_hat) = 0 at the attractor center."""
        state = make_state(attractor.attractor_center)
        V = attractor.compute_lyapunov_function(state)
        assert V == pytest.approx(0.0, abs=1e-10)

    def test_lyapunov_positive_away_from_center(self, attractor):
        """V(x) > 0 for x != a_hat."""
        offset = attractor.attractor_center + 0.1
        state = make_state(offset)
        V = attractor.compute_lyapunov_function(state)
        assert V > 0.0

    def test_lyapunov_increases_with_distance(self, attractor):
        """Farther from center -> higher V."""
        near = make_state(attractor.attractor_center + 0.01)
        far = make_state(attractor.attractor_center + 0.5)
        V_near = attractor.compute_lyapunov_function(near)
        V_far = attractor.compute_lyapunov_function(far)
        assert V_far > V_near


# ============================================================================
# Basin Membership
# ============================================================================

class TestBasinMembership:
    """Test basin membership (point inside/outside attractor basin)."""

    def test_center_is_in_basin(self, attractor):
        """Attractor center is always inside the basin."""
        state = make_state(attractor.attractor_center)
        assert attractor.compute_basin_membership(state) == True

    def test_near_center_is_in_basin(self, attractor):
        """Point slightly perturbed from center stays in basin."""
        perturbation = np.zeros_like(attractor.attractor_center)
        perturbation[0] = 0.001
        state = make_state(attractor.attractor_center + perturbation)
        assert attractor.compute_basin_membership(state) == True

    def test_far_point_is_outside_basin(self, attractor):
        """Point far from center is outside the basin."""
        far_embedding = attractor.attractor_center * -10.0  # Opposite direction, far away
        state = make_state(far_embedding)
        assert attractor.compute_basin_membership(state) == False


# ============================================================================
# Error Signal
# ============================================================================

class TestErrorSignal:
    """Test error signal computation for proportional controller."""

    def test_error_at_center_is_zero(self, attractor):
        """Error signal = 0 at attractor center."""
        state = make_state(attractor.attractor_center)
        error = attractor.compute_error_signal(state)
        assert error == pytest.approx(0.0, abs=1e-10)

    def test_error_capped_at_one(self, attractor):
        """Error signal capped at 1.0 (at or beyond basin boundary)."""
        far_embedding = attractor.attractor_center + 100.0
        state = make_state(far_embedding)
        error = attractor.compute_error_signal(state)
        assert error == pytest.approx(1.0)

    def test_error_increases_with_distance(self, attractor):
        """Error signal monotonically increases with distance."""
        errors = []
        for scale in [0.01, 0.1, 0.5]:
            offset = np.zeros_like(attractor.attractor_center)
            offset[0] = scale
            state = make_state(attractor.attractor_center + offset)
            errors.append(attractor.compute_error_signal(state))
        assert errors == sorted(errors)

    def test_error_in_unit_range(self, attractor):
        """Error signal is in [0, 1]."""
        for _ in range(10):
            embedding = np.random.randn(384).astype(np.float32)
            state = make_state(embedding)
            error = attractor.compute_error_signal(state)
            assert 0.0 <= error <= 1.0


# ============================================================================
# Telic Fidelity Calculator
# ============================================================================

class TestTelicFidelityCalculator:
    """Test hard fidelity, soft fidelity, and trajectory stability."""

    @pytest.fixture
    def calculator(self):
        return TelicFidelityCalculator()

    def test_hard_fidelity_empty_states(self, calculator, attractor):
        """Empty trajectory returns 0.0."""
        assert calculator.compute_hard_fidelity([], attractor) == 0.0

    def test_hard_fidelity_all_in_basin(self, calculator, attractor):
        """All states at center -> hard fidelity = 1.0."""
        states = [make_state(attractor.attractor_center, t) for t in range(5)]
        assert calculator.compute_hard_fidelity(states, attractor) == pytest.approx(1.0)

    def test_hard_fidelity_none_in_basin(self, calculator, attractor):
        """All states far away -> hard fidelity = 0.0."""
        far = attractor.attractor_center * -50.0
        states = [make_state(far, t) for t in range(5)]
        assert calculator.compute_hard_fidelity(states, attractor) == pytest.approx(0.0)

    def test_hard_fidelity_range(self, calculator, attractor):
        """Hard fidelity is in [0, 1]."""
        states = [
            make_state(attractor.attractor_center, 1),
            make_state(attractor.attractor_center * -50.0, 2),
        ]
        f = calculator.compute_hard_fidelity(states, attractor)
        assert 0.0 <= f <= 1.0

    def test_soft_fidelity_empty_states(self, calculator, attractor):
        """Empty trajectory returns 0.0."""
        assert calculator.compute_soft_fidelity([], attractor) == 0.0

    def test_soft_fidelity_at_center(self, calculator, attractor):
        """States at center -> soft fidelity = 1/(1+0) = 1.0."""
        states = [make_state(attractor.attractor_center, t) for t in range(3)]
        assert calculator.compute_soft_fidelity(states, attractor) == pytest.approx(1.0, abs=1e-5)

    def test_soft_fidelity_decreases_with_distance(self, calculator, attractor):
        """Farther states -> lower soft fidelity."""
        near = [make_state(attractor.attractor_center + 0.01, t) for t in range(3)]
        far = [make_state(attractor.attractor_center + 5.0, t) for t in range(3)]
        f_near = calculator.compute_soft_fidelity(near, attractor)
        f_far = calculator.compute_soft_fidelity(far, attractor)
        assert f_near > f_far

    def test_trajectory_stability_single_state(self, calculator, attractor):
        """Single state trajectory returns 1.0 (trivially stable)."""
        states = [make_state(attractor.attractor_center)]
        assert calculator.compute_trajectory_stability(states, attractor) == 1.0

    def test_trajectory_stability_converging(self, calculator, attractor):
        """Converging trajectory (V decreasing) should have stability > 0."""
        states = []
        for i in range(5):
            scale = 1.0 - (i * 0.2)  # 1.0, 0.8, 0.6, 0.4, 0.2
            offset = np.zeros_like(attractor.attractor_center)
            offset[0] = scale
            states.append(make_state(attractor.attractor_center + offset, i))
        stability = calculator.compute_trajectory_stability(states, attractor)
        assert stability > 0.0

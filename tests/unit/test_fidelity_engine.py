"""
Unit tests for telos_core.fidelity_engine

Tests fidelity calculation, zone classification, governance decisions,
and SAAI drift utilities.
"""

import pytest
import numpy as np
from telos_core.fidelity_engine import (
    FidelityEngine,
    FidelityResult,
    GovernanceResult,
    FidelityZone,
    GovernanceDecision,
    InterventionType,
    calculate_cosine_similarity,
    normalize_fidelity,
    classify_fidelity_zone,
    check_layer1_hard_block,
    check_layer2_outside_basin,
    should_intervene,
    make_governance_decision,
    calculate_decision_confidence,
    calculate_drift_from_baseline,
    classify_saai_drift_level,
)
from telos_core.constants import (
    FIDELITY_GREEN,
    FIDELITY_YELLOW,
    FIDELITY_ORANGE,
    SIMILARITY_BASELINE,
    INTERVENTION_THRESHOLD,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def engine():
    """Default FidelityEngine instance."""
    return FidelityEngine()


@pytest.fixture
def aligned_vectors():
    """Two identical (perfectly aligned) vectors."""
    vec = np.random.RandomState(42).randn(384).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec, vec.copy()


@pytest.fixture
def orthogonal_vectors():
    """Two orthogonal vectors (zero similarity)."""
    a = np.zeros(384, dtype=np.float32)
    b = np.zeros(384, dtype=np.float32)
    a[0] = 1.0
    b[1] = 1.0
    return a, b


# ============================================================================
# Cosine Similarity
# ============================================================================

class TestCosineSimilarity:
    """Test core cosine similarity function."""

    def test_identical_vectors(self, aligned_vectors):
        """Identical vectors -> similarity = 1.0."""
        a, b = aligned_vectors
        assert calculate_cosine_similarity(a, b) == pytest.approx(1.0, abs=1e-5)

    def test_orthogonal_vectors(self, orthogonal_vectors):
        """Orthogonal vectors -> similarity = 0.0."""
        a, b = orthogonal_vectors
        assert calculate_cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-5)

    def test_opposite_vectors(self):
        """Opposite vectors -> similarity = -1.0."""
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([-1.0, 0.0], dtype=np.float32)
        assert calculate_cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-5)

    def test_zero_vector_returns_zero(self):
        """Zero vector -> similarity = 0.0 (safe division)."""
        a = np.zeros(10, dtype=np.float32)
        b = np.ones(10, dtype=np.float32)
        assert calculate_cosine_similarity(a, b) == 0.0

    def test_range(self):
        """Similarity is in [-1, 1]."""
        for _ in range(20):
            a = np.random.randn(384).astype(np.float32)
            b = np.random.randn(384).astype(np.float32)
            sim = calculate_cosine_similarity(a, b)
            assert -1.0 <= sim <= 1.0 + 1e-6


# ============================================================================
# Fidelity Normalization
# ============================================================================

class TestNormalizeFidelity:
    """Test linear normalization with default calibration."""

    def test_clamp_below_zero(self):
        """Negative input -> clamped to 0.0."""
        result = normalize_fidelity(-0.5)
        assert result >= 0.0

    def test_clamp_above_one(self):
        """Very high input -> clamped to 1.0."""
        result = normalize_fidelity(2.0)
        assert result <= 1.0

    def test_monotonic(self):
        """Higher raw similarity -> higher normalized fidelity."""
        values = [normalize_fidelity(x / 10.0) for x in range(11)]
        assert values == sorted(values)

    def test_known_calibration_point(self):
        """Raw 0.50 should map near GREEN threshold (0.70)."""
        # With default slope=1.167, intercept=0.117: 1.167*0.5 + 0.117 = 0.7005
        result = normalize_fidelity(0.50)
        assert result == pytest.approx(0.70, abs=0.01)


# ============================================================================
# Zone Classification
# ============================================================================

class TestClassifyFidelityZone:
    """Test fidelity -> zone mapping."""

    def test_green_zone(self):
        assert classify_fidelity_zone(0.85) == FidelityZone.GREEN
        assert classify_fidelity_zone(0.70) == FidelityZone.GREEN

    def test_yellow_zone(self):
        assert classify_fidelity_zone(0.65) == FidelityZone.YELLOW
        assert classify_fidelity_zone(0.60) == FidelityZone.YELLOW

    def test_orange_zone(self):
        assert classify_fidelity_zone(0.55) == FidelityZone.ORANGE
        assert classify_fidelity_zone(0.50) == FidelityZone.ORANGE

    def test_red_zone(self):
        assert classify_fidelity_zone(0.49) == FidelityZone.RED
        assert classify_fidelity_zone(0.10) == FidelityZone.RED
        assert classify_fidelity_zone(0.0) == FidelityZone.RED

    def test_boundary_green_yellow(self):
        """Boundary at 0.70: >= GREEN, < YELLOW."""
        assert classify_fidelity_zone(0.70) == FidelityZone.GREEN
        assert classify_fidelity_zone(0.699) == FidelityZone.YELLOW

    def test_boundary_yellow_orange(self):
        """Boundary at 0.60: >= YELLOW, < ORANGE."""
        assert classify_fidelity_zone(0.60) == FidelityZone.YELLOW
        assert classify_fidelity_zone(0.599) == FidelityZone.ORANGE


# ============================================================================
# Layer Checks
# ============================================================================

class TestLayerChecks:
    """Test Layer 1 and Layer 2 checks."""

    def test_layer1_below_baseline(self):
        """Raw similarity below 0.20 -> hard block."""
        assert check_layer1_hard_block(0.19) is True
        assert check_layer1_hard_block(0.10) is True

    def test_layer1_above_baseline(self):
        """Raw similarity above 0.20 -> no hard block."""
        assert check_layer1_hard_block(0.20) is False
        assert check_layer1_hard_block(0.50) is False

    def test_layer2_below_threshold(self):
        """Normalized fidelity below 0.48 -> outside basin."""
        assert check_layer2_outside_basin(0.47) is True
        assert check_layer2_outside_basin(0.10) is True

    def test_layer2_above_threshold(self):
        """Normalized fidelity above 0.48 -> inside basin."""
        assert check_layer2_outside_basin(0.48) is False
        assert check_layer2_outside_basin(0.80) is False


# ============================================================================
# Should Intervene
# ============================================================================

class TestShouldIntervene:
    """Test two-layer intervention decision logic."""

    def test_green_zone_no_intervention(self):
        """High raw + high normalized -> no intervention."""
        assert should_intervene(0.50, 0.80) is False

    def test_green_boundary_no_intervention(self):
        """Exactly at GREEN threshold -> no intervention."""
        assert should_intervene(0.50, 0.70) is False

    def test_yellow_zone_intervene(self):
        """Below GREEN normalized -> intervene."""
        assert should_intervene(0.50, 0.65) is True

    def test_layer1_hard_block(self):
        """Very low raw similarity -> intervene even if normalized is high."""
        assert should_intervene(0.15, 0.80) is True

    def test_both_layers_trigger(self):
        """Both layers flagged -> definitely intervene."""
        assert should_intervene(0.10, 0.30) is True


# ============================================================================
# Governance Decisions
# ============================================================================

class TestGovernanceDecisions:
    """Test graduated governance decision function."""

    def test_execute(self):
        assert make_governance_decision(0.50) == GovernanceDecision.EXECUTE
        assert make_governance_decision(0.90) == GovernanceDecision.EXECUTE

    def test_clarify(self):
        assert make_governance_decision(0.40) == GovernanceDecision.CLARIFY

    def test_inert(self):
        assert make_governance_decision(0.10) == GovernanceDecision.INERT

    def test_escalate_on_saai_block(self):
        """SAAI block-level drift -> ESCALATE regardless of fidelity."""
        assert make_governance_decision(0.90, saai_drift_level="block") == GovernanceDecision.ESCALATE

    def test_tool_fidelities_weaken_decision(self):
        """Low tool fidelity weakens overall decision."""
        # Input fidelity high, but one tool very low
        decision = make_governance_decision(
            input_fidelity=0.80,
            tool_fidelities={"bad_tool": 0.10}
        )
        assert decision == GovernanceDecision.INERT

    def test_boundary_execute_clarify(self):
        """Boundary at 0.45."""
        assert make_governance_decision(0.45) == GovernanceDecision.EXECUTE
        assert make_governance_decision(0.44) == GovernanceDecision.CLARIFY


# ============================================================================
# Decision Confidence
# ============================================================================

class TestDecisionConfidence:
    """Test confidence scoring for decisions."""

    def test_confidence_in_range(self):
        """Confidence is always in [0.3, 1.0]."""
        for f in [0.0, 0.25, 0.50, 0.75, 1.0]:
            for d in GovernanceDecision:
                conf = calculate_decision_confidence(f, d)
                assert 0.3 <= conf <= 1.0

    def test_high_fidelity_execute_confident(self):
        """High fidelity + EXECUTE -> high confidence."""
        conf = calculate_decision_confidence(0.70, GovernanceDecision.EXECUTE)
        assert conf >= 0.8


# ============================================================================
# FidelityEngine Integration
# ============================================================================

class TestFidelityEngine:
    """Test the FidelityEngine class."""

    def test_calculate_fidelity_identical(self, engine, aligned_vectors):
        """Identical vectors -> high fidelity, GREEN zone."""
        a, b = aligned_vectors
        result = engine.calculate_fidelity(a, b)
        assert isinstance(result, FidelityResult)
        assert result.zone == FidelityZone.GREEN
        assert result.should_intervene is False
        assert result.layer1_hard_block is False

    def test_calculate_fidelity_orthogonal(self, engine, orthogonal_vectors):
        """Orthogonal vectors -> low fidelity, RED zone."""
        a, b = orthogonal_vectors
        result = engine.calculate_fidelity(a, b)
        assert result.raw_similarity == pytest.approx(0.0, abs=1e-5)
        assert result.zone == FidelityZone.RED
        assert result.should_intervene is True

    def test_evaluate_request(self, engine, aligned_vectors):
        """Full governance evaluation returns GovernanceResult."""
        a, b = aligned_vectors
        result = engine.evaluate_request(a, b)
        assert isinstance(result, GovernanceResult)
        assert result.decision == GovernanceDecision.EXECUTE
        assert result.confidence > 0.0
        assert result.recommendation is not None

    def test_fidelity_result_to_dict(self, engine, aligned_vectors):
        """FidelityResult.to_dict() returns serializable dict."""
        a, b = aligned_vectors
        result = engine.calculate_fidelity(a, b)
        d = result.to_dict()
        assert "raw_similarity" in d
        assert "normalized_fidelity" in d
        assert "zone" in d
        assert isinstance(d["zone"], str)


# ============================================================================
# SAAI Drift Utilities
# ============================================================================

class TestSAAIDriftUtilities:
    """Test SAAI drift calculation and classification."""

    def test_zero_drift(self):
        """Same average as baseline -> 0 drift."""
        assert calculate_drift_from_baseline(0.80, 0.80) == pytest.approx(0.0)

    def test_positive_drift(self):
        """Average drops -> positive drift."""
        drift = calculate_drift_from_baseline(0.72, 0.80)
        assert drift == pytest.approx(0.10)  # (0.80-0.72)/0.80 = 0.10

    def test_negative_drift_clamped(self):
        """Average improves -> drift clamped to 0."""
        drift = calculate_drift_from_baseline(0.90, 0.80)
        assert drift == 0.0

    def test_zero_baseline_safe(self):
        """Zero baseline -> 0 drift (no division by zero)."""
        assert calculate_drift_from_baseline(0.50, 0.0) == 0.0

    def test_classify_normal(self):
        assert classify_saai_drift_level(0.05) == "normal"

    def test_classify_warning(self):
        assert classify_saai_drift_level(0.10) == "warning"
        assert classify_saai_drift_level(0.12) == "warning"

    def test_classify_restrict(self):
        assert classify_saai_drift_level(0.15) == "restrict"
        assert classify_saai_drift_level(0.18) == "restrict"

    def test_classify_block(self):
        assert classify_saai_drift_level(0.20) == "block"
        assert classify_saai_drift_level(0.50) == "block"

"""
Unit tests for telos_core.constants

Verifies threshold values, formula functions, and model-specific thresholds.
"""

import pytest
from telos_core.constants import (
    # Display zone thresholds
    FIDELITY_GREEN,
    FIDELITY_YELLOW,
    FIDELITY_ORANGE,
    FIDELITY_RED,
    # Intervention thresholds
    SIMILARITY_BASELINE,
    INTERVENTION_THRESHOLD,
    BASIN_CENTER,
    BASIN_TOLERANCE,
    # Control gains
    DEFAULT_K_ATTRACTOR,
    DEFAULT_K_ANTIMETA,
    # Error signal functions
    compute_epsilon_min,
    compute_epsilon_max,
    # Basin geometry
    compute_basin_radius,
    BASIN_RADIUS_MIN,
    BASIN_RADIUS_MAX,
    # Model-specific thresholds
    ST_FIDELITY_GREEN,
    ST_FIDELITY_YELLOW,
    ST_FIDELITY_ORANGE,
    ST_FIDELITY_RED,
    MISTRAL_FIDELITY_GREEN,
    MISTRAL_FIDELITY_YELLOW,
    MISTRAL_FIDELITY_ORANGE,
    MISTRAL_FIDELITY_RED,
    get_thresholds_for_model,
    # SAAI thresholds
    SAAI_DRIFT_WARNING,
    SAAI_DRIFT_RESTRICT,
    SAAI_DRIFT_BLOCK,
    BASELINE_TURN_COUNT,
    # Legacy alias
    FIDELITY_MONITOR,
)


# ============================================================================
# Display Zone Threshold Values
# ============================================================================

class TestDisplayZoneThresholds:
    """Verify exact threshold values from single source of truth."""

    def test_fidelity_green(self):
        assert FIDELITY_GREEN == 0.70

    def test_fidelity_yellow(self):
        assert FIDELITY_YELLOW == 0.60

    def test_fidelity_orange(self):
        assert FIDELITY_ORANGE == 0.50

    def test_fidelity_red(self):
        assert FIDELITY_RED == 0.50

    def test_zone_ordering(self):
        """Zones must be ordered: GREEN > YELLOW > ORANGE >= RED."""
        assert FIDELITY_GREEN > FIDELITY_YELLOW
        assert FIDELITY_YELLOW > FIDELITY_ORANGE
        assert FIDELITY_ORANGE >= FIDELITY_RED


# ============================================================================
# Intervention Decision Thresholds
# ============================================================================

class TestInterventionThresholds:
    """Verify Layer 1 and Layer 2 thresholds."""

    def test_similarity_baseline(self):
        """Layer 1: Hard block at raw similarity < 0.20."""
        assert SIMILARITY_BASELINE == 0.20

    def test_intervention_threshold(self):
        """Layer 2: Basin boundary at 0.48."""
        assert INTERVENTION_THRESHOLD == 0.48

    def test_basin_center(self):
        assert BASIN_CENTER == 0.50

    def test_basin_tolerance(self):
        assert BASIN_TOLERANCE == 0.02

    def test_intervention_threshold_formula(self):
        """INTERVENTION_THRESHOLD = BASIN_CENTER - BASIN_TOLERANCE."""
        assert INTERVENTION_THRESHOLD == pytest.approx(
            BASIN_CENTER - BASIN_TOLERANCE, abs=1e-10
        )


# ============================================================================
# Control Gains
# ============================================================================

class TestControlGains:
    """Verify proportional control gain constants."""

    def test_k_attractor(self):
        """K_ATTRACTOR = 1.5 per whitepaper Section 5.3."""
        assert DEFAULT_K_ATTRACTOR == 1.5

    def test_k_antimeta(self):
        """K_ANTIMETA = 2.0 (higher gain for meta suppression)."""
        assert DEFAULT_K_ANTIMETA == 2.0

    def test_antimeta_stronger_than_attractor(self):
        """Anti-meta gain must exceed attractor gain."""
        assert DEFAULT_K_ANTIMETA > DEFAULT_K_ATTRACTOR


# ============================================================================
# Error Signal Functions
# ============================================================================

class TestErrorSignalFunctions:
    """Test epsilon_min and epsilon_max formula functions."""

    def test_epsilon_min_at_zero_tolerance(self):
        """e_min = 0.1 + 0.3*0 = 0.1."""
        assert compute_epsilon_min(0.0) == pytest.approx(0.1)

    def test_epsilon_min_at_default_tolerance(self):
        """e_min = 0.1 + 0.3*0.2 = 0.16."""
        assert compute_epsilon_min(0.2) == pytest.approx(0.16)

    def test_epsilon_min_at_max_tolerance(self):
        """e_min = 0.1 + 0.3*1.0 = 0.4."""
        assert compute_epsilon_min(1.0) == pytest.approx(0.4)

    def test_epsilon_max_at_zero_tolerance(self):
        """e_max = 0.5 + 0.4*0 = 0.5."""
        assert compute_epsilon_max(0.0) == pytest.approx(0.5)

    def test_epsilon_max_at_default_tolerance(self):
        """e_max = 0.5 + 0.4*0.2 = 0.58."""
        assert compute_epsilon_max(0.2) == pytest.approx(0.58)

    def test_epsilon_max_at_max_tolerance(self):
        """e_max = 0.5 + 0.4*1.0 = 0.9."""
        assert compute_epsilon_max(1.0) == pytest.approx(0.9)

    def test_epsilon_min_less_than_epsilon_max(self):
        """e_min < e_max for any tolerance value."""
        for t in [0.0, 0.2, 0.5, 0.8, 1.0]:
            assert compute_epsilon_min(t) < compute_epsilon_max(t), f"Failed at t={t}"


# ============================================================================
# Basin Geometry
# ============================================================================

class TestBasinGeometry:
    """Test basin radius computation."""

    def test_basin_radius_at_zero_tolerance(self):
        """r = 2/max(1.0, 0.25) = 2.0 at t=0."""
        assert compute_basin_radius(0.0) == pytest.approx(2.0)

    def test_basin_radius_at_default_tolerance(self):
        """r = 2/max(0.8, 0.25) = 2.5 at t=0.2."""
        assert compute_basin_radius(0.2) == pytest.approx(2.5)

    def test_basin_radius_at_high_tolerance(self):
        """r = 2/max(0.25, 0.25) = 8.0 at t=0.75."""
        assert compute_basin_radius(0.75) == pytest.approx(8.0)

    def test_basin_radius_floor(self):
        """Rigidity is floored at 0.25 to prevent infinite radius."""
        # At t=1.0: rigidity=0.0, floored to 0.25, r=8.0
        assert compute_basin_radius(1.0) == pytest.approx(8.0)

    def test_basin_radius_constants(self):
        """Min/max radius constants match formula outputs."""
        assert BASIN_RADIUS_MIN == pytest.approx(compute_basin_radius(0.0))
        assert BASIN_RADIUS_MAX == pytest.approx(compute_basin_radius(1.0))


# ============================================================================
# Model-Specific Thresholds
# ============================================================================

class TestModelSpecificThresholds:
    """Verify model-specific raw threshold values."""

    def test_sentence_transformer_thresholds(self):
        thresholds = get_thresholds_for_model('sentence_transformer')
        assert thresholds['green'] == ST_FIDELITY_GREEN
        assert thresholds['yellow'] == ST_FIDELITY_YELLOW
        assert thresholds['orange'] == ST_FIDELITY_ORANGE
        assert thresholds['red'] == ST_FIDELITY_RED

    def test_mistral_thresholds(self):
        thresholds = get_thresholds_for_model('mistral')
        assert thresholds['green'] == MISTRAL_FIDELITY_GREEN
        assert thresholds['yellow'] == MISTRAL_FIDELITY_YELLOW
        assert thresholds['orange'] == MISTRAL_FIDELITY_ORANGE
        assert thresholds['red'] == MISTRAL_FIDELITY_RED

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError, match="Unknown model type"):
            get_thresholds_for_model('nonexistent')

    def test_st_ordering(self):
        """SentenceTransformer: GREEN > YELLOW > ORANGE >= RED."""
        assert ST_FIDELITY_GREEN > ST_FIDELITY_YELLOW
        assert ST_FIDELITY_YELLOW > ST_FIDELITY_ORANGE
        assert ST_FIDELITY_ORANGE >= ST_FIDELITY_RED

    def test_mistral_ordering(self):
        """Mistral: GREEN > YELLOW > ORANGE >= RED."""
        assert MISTRAL_FIDELITY_GREEN > MISTRAL_FIDELITY_YELLOW
        assert MISTRAL_FIDELITY_YELLOW > MISTRAL_FIDELITY_ORANGE
        assert MISTRAL_FIDELITY_ORANGE >= MISTRAL_FIDELITY_RED


# ============================================================================
# SAAI Framework Thresholds
# ============================================================================

class TestSAAIThresholds:
    """Verify SAAI drift threshold values and ordering."""

    def test_drift_warning(self):
        assert SAAI_DRIFT_WARNING == 0.10

    def test_drift_restrict(self):
        assert SAAI_DRIFT_RESTRICT == 0.15

    def test_drift_block(self):
        assert SAAI_DRIFT_BLOCK == 0.20

    def test_drift_ordering(self):
        """Drift thresholds must escalate: WARNING < RESTRICT < BLOCK."""
        assert SAAI_DRIFT_WARNING < SAAI_DRIFT_RESTRICT
        assert SAAI_DRIFT_RESTRICT < SAAI_DRIFT_BLOCK

    def test_baseline_turn_count(self):
        assert BASELINE_TURN_COUNT == 50
        assert BASELINE_TURN_COUNT > 0


# ============================================================================
# Legacy Aliases
# ============================================================================

class TestLegacyAliases:
    """Verify backward-compatible aliases."""

    def test_fidelity_monitor_alias(self):
        """FIDELITY_MONITOR should equal FIDELITY_GREEN."""
        assert FIDELITY_MONITOR == FIDELITY_GREEN

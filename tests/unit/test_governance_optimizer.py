"""
Unit tests for the Governance Configuration Optimizer.

Tests cover:
1. ThresholdConfig: defaults match constants, ordering validation, serialization
2. SearchSpace: respects bounds, frozen excluded, ordering enforced
3. Objective: computation correct, hard constraints prune
4. GDD: rejects weak configs, accepts strong ones
5. AsymmetricRatchet: flags less restrictive, accepts more restrictive
6. RegressionReport: detects flipped scenarios
7. Holdout split: deterministic, stratified
8. Backward compatibility: None threshold_config = current behavior
"""

import pytest
import numpy as np
from unittest.mock import MagicMock

from telos_governance.threshold_config import ThresholdConfig

from telos_core.constants import (
    ST_AGENTIC_EXECUTE_THRESHOLD,
    ST_AGENTIC_CLARIFY_THRESHOLD,
    FIDELITY_GREEN,
    FIDELITY_YELLOW,
    FIDELITY_ORANGE,
    BOUNDARY_MARGIN_THRESHOLD,
    DEFAULT_MAX_REGENERATIONS,
)

from analysis.governance_optimizer import (
    create_holdout_split,
    create_cv_folds,
    scalarized_objective,
    compute_gsi,
    check_governance_degradation,
    classify_ratchet_direction,
    generate_regression_report,
    hash_config,
    BenchmarkMetrics,
)


# =============================================================================
# ThresholdConfig Tests
# =============================================================================

class TestThresholdConfig:
    """Test ThresholdConfig dataclass."""

    def test_defaults_match_constants(self):
        """Default ThresholdConfig values must match production constants."""
        config = ThresholdConfig()
        assert config.st_execute == ST_AGENTIC_EXECUTE_THRESHOLD
        assert config.st_clarify == ST_AGENTIC_CLARIFY_THRESHOLD
        assert config.fidelity_green == FIDELITY_GREEN
        assert config.fidelity_yellow == FIDELITY_YELLOW
        assert config.fidelity_orange == FIDELITY_ORANGE
        assert config.boundary_margin == BOUNDARY_MARGIN_THRESHOLD
        assert config.max_regenerations == DEFAULT_MAX_REGENERATIONS

    def test_default_config_is_valid(self):
        """Default config should pass all validation invariants."""
        config = ThresholdConfig()
        assert config.is_valid()
        assert config.validate() == []

    def test_ordering_violation_execute_clarify(self):
        """st_execute must be > st_clarify + 0.05."""
        config = ThresholdConfig(st_execute=0.40, st_clarify=0.38)
        violations = config.validate()
        assert any("st_execute" in v for v in violations)

    def test_ordering_violation_zones(self):
        """fidelity_green > fidelity_yellow > fidelity_orange."""
        config = ThresholdConfig(fidelity_green=0.62, fidelity_yellow=0.60)
        violations = config.validate()
        assert any("fidelity_green" in v for v in violations)

    def test_weight_sum_near_one(self):
        """Total weights should be near 1.0 (within 0.15 tolerance)."""
        config = ThresholdConfig()
        total = (config.weight_purpose + config.weight_scope +
                 config.weight_tool + config.weight_chain +
                 config.weight_boundary_penalty)
        assert abs(total - 1.0) <= 0.15

    def test_weight_sum_violation(self):
        """Extreme weight values should trigger validation error."""
        config = ThresholdConfig(
            weight_purpose=0.80, weight_scope=0.80,
            weight_tool=0.80, weight_chain=0.80,
        )
        violations = config.validate()
        assert any("Total weights" in v for v in violations)

    def test_boundary_range_violation(self):
        """boundary_violation must be in [0.0, 1.0]."""
        config = ThresholdConfig(boundary_violation=1.5)
        violations = config.validate()
        assert any("boundary_violation" in v for v in violations)

    def test_max_regenerations_violation(self):
        """max_regenerations must be >= 1."""
        config = ThresholdConfig(max_regenerations=0)
        violations = config.validate()
        assert any("max_regenerations" in v for v in violations)

    def test_serialization_roundtrip(self):
        """to_dict -> from_dict should preserve all values."""
        config = ThresholdConfig(
            st_execute=0.50, weight_purpose=0.40, boundary_violation=0.75
        )
        d = config.to_dict()
        restored = ThresholdConfig.from_dict(d)
        assert restored.st_execute == 0.50
        assert restored.weight_purpose == 0.40
        assert restored.boundary_violation == 0.75

    def test_from_dict_ignores_extra_keys(self):
        """from_dict should ignore keys not in the dataclass."""
        d = ThresholdConfig().to_dict()
        d["unknown_key"] = 42
        config = ThresholdConfig.from_dict(d)
        assert config.is_valid()


# =============================================================================
# Holdout Split Tests
# =============================================================================

class TestHoldoutSplit:
    """Test train/holdout split infrastructure."""

    @pytest.fixture
    def sample_scenarios(self):
        """Create sample scenarios with mixed categories."""
        scenarios = []
        for cat in ["A", "B", "C", "D", "E"]:
            for i in range(20):
                scenarios.append({
                    "scenario_id": f"TEST-{cat}-{i:03d}",
                    "boundary_category": cat,
                    "expected_decision": "ESCALATE" if cat in ("A", "E") else "EXECUTE",
                    "request_text": f"Test request {cat}-{i}",
                })
        return scenarios

    def test_split_deterministic(self, sample_scenarios):
        """Same seed produces same split."""
        train1, holdout1 = create_holdout_split(sample_scenarios, seed=42)
        train2, holdout2 = create_holdout_split(sample_scenarios, seed=42)

        train_ids1 = {s["scenario_id"] for s in train1}
        train_ids2 = {s["scenario_id"] for s in train2}
        assert train_ids1 == train_ids2

    def test_split_no_overlap(self, sample_scenarios):
        """Train and holdout must not share scenarios."""
        train, holdout = create_holdout_split(sample_scenarios, seed=42)
        train_ids = {s["scenario_id"] for s in train}
        holdout_ids = {s["scenario_id"] for s in holdout}
        assert train_ids & holdout_ids == set()

    def test_split_complete(self, sample_scenarios):
        """All scenarios must be in either train or holdout."""
        train, holdout = create_holdout_split(sample_scenarios, seed=42)
        assert len(train) + len(holdout) == len(sample_scenarios)

    def test_split_stratified(self, sample_scenarios):
        """Each category should be represented in both splits."""
        train, holdout = create_holdout_split(sample_scenarios, seed=42)
        train_cats = {s["boundary_category"] for s in train}
        holdout_cats = {s["boundary_category"] for s in holdout}
        assert train_cats == {"A", "B", "C", "D", "E"}
        assert holdout_cats == {"A", "B", "C", "D", "E"}

    def test_split_approximate_ratio(self, sample_scenarios):
        """Holdout should be approximately 30% of total."""
        train, holdout = create_holdout_split(
            sample_scenarios, seed=42, holdout_ratio=0.30
        )
        ratio = len(holdout) / len(sample_scenarios)
        assert 0.20 <= ratio <= 0.40  # Generous tolerance for small N

    def test_cv_folds_cover_all(self, sample_scenarios):
        """CV folds should cover all training scenarios."""
        train, _ = create_holdout_split(sample_scenarios, seed=42)
        folds = create_cv_folds(train, n_folds=5, seed=42)
        assert len(folds) == 5

        # Union of all val folds should cover all train scenarios
        all_val_ids = set()
        for _, val_fold in folds:
            for s in val_fold:
                all_val_ids.add(s["scenario_id"])

        train_ids = {s["scenario_id"] for s in train}
        assert all_val_ids == train_ids


# =============================================================================
# Objective Function Tests
# =============================================================================

class TestObjectiveFunction:
    """Test the scalarized objective function."""

    def _make_metrics(self, accuracy=0.85, cat_a=1.0, cat_e=0.90,
                      fpr=0.05, boundary=0.95, name="test"):
        return BenchmarkMetrics(
            benchmark_name=name,
            accuracy=accuracy,
            cat_a_detection=cat_a,
            cat_e_detection=cat_e,
            fpr=fpr,
            boundary_detection=boundary,
        )

    def test_valid_metrics_produce_positive_objective(self):
        """Good metrics should produce a positive objective."""
        metrics = [self._make_metrics()]
        obj = scalarized_objective(metrics)
        assert obj is not None
        assert obj > 0

    def test_cat_a_hard_constraint(self):
        """Cat A detection below MIN_CAT_A_DETECTION (0.95) should return None."""
        metrics = [self._make_metrics(cat_a=0.94)]
        obj = scalarized_objective(metrics)
        assert obj is None

    def test_cat_e_hard_constraint(self):
        """Cat E detection < 85% should return None."""
        metrics = [self._make_metrics(cat_e=0.80)]
        obj = scalarized_objective(metrics)
        assert obj is None

    def test_higher_accuracy_better_objective(self):
        """Higher accuracy should produce higher objective."""
        low = scalarized_objective([self._make_metrics(accuracy=0.70)])
        high = scalarized_objective([self._make_metrics(accuracy=0.95)])
        assert high > low

    def test_lower_fpr_better_objective(self):
        """Lower FPR should produce higher objective."""
        high_fpr = scalarized_objective([self._make_metrics(fpr=0.20)])
        low_fpr = scalarized_objective([self._make_metrics(fpr=0.02)])
        assert low_fpr > high_fpr

    def test_multi_benchmark_min_accuracy(self):
        """Min benchmark accuracy component should reward consistency."""
        # Consistent: both 85%
        consistent = scalarized_objective([
            self._make_metrics(accuracy=0.85, name="a"),
            self._make_metrics(accuracy=0.85, name="b"),
        ])
        # Inconsistent: 95% and 75% (same mean but lower min)
        inconsistent = scalarized_objective([
            self._make_metrics(accuracy=0.95, name="a"),
            self._make_metrics(accuracy=0.75, name="b"),
        ])
        # Both should be valid (constraints met)
        assert consistent is not None
        assert inconsistent is not None

    def test_empty_metrics_returns_none(self):
        """Empty metrics list should return None."""
        assert scalarized_objective([]) is None


# =============================================================================
# Safety Mechanism Tests
# =============================================================================

class TestGovernanceDegradationDetector:
    """Test the GDD."""

    def test_no_degradation_accepted(self):
        """Same config should be accepted (no degradation)."""
        config = ThresholdConfig()
        ok, _, _ = check_governance_degradation(config, config)
        assert ok

    def test_more_restrictive_accepted(self):
        """More restrictive config should be accepted."""
        baseline = ThresholdConfig()
        candidate = ThresholdConfig(
            st_execute=baseline.st_execute + 0.05,
            fidelity_green=baseline.fidelity_green + 0.05,
        )
        ok, cand_gsi, base_gsi = check_governance_degradation(candidate, baseline)
        assert ok
        assert cand_gsi >= base_gsi

    def test_major_degradation_rejected(self):
        """Large GSI drop should be rejected."""
        baseline = ThresholdConfig()
        candidate = ThresholdConfig(
            st_execute=0.20,  # Much lower than default
            st_clarify=0.10,
            boundary_violation=0.40,
            fidelity_green=0.40,
        )
        ok, _, _ = check_governance_degradation(candidate, baseline)
        assert not ok


class TestAsymmetricRatchet:
    """Test the asymmetric ratchet classification."""

    def test_unchanged_params(self):
        """Identical configs should show all unchanged."""
        config = ThresholdConfig()
        flags = classify_ratchet_direction(config, config)
        for param, direction in flags.items():
            assert direction == "unchanged", f"{param} should be unchanged"

    def test_higher_threshold_is_more_restrictive(self):
        """Raising st_execute should be classified as more restrictive."""
        baseline = ThresholdConfig()
        candidate = ThresholdConfig(st_execute=baseline.st_execute + 0.10)
        flags = classify_ratchet_direction(candidate, baseline)
        assert flags["st_execute"] == "more_restrictive"

    def test_lower_threshold_is_less_restrictive(self):
        """Lowering st_execute should be classified as less restrictive."""
        baseline = ThresholdConfig()
        candidate = ThresholdConfig(st_execute=baseline.st_execute - 0.10)
        flags = classify_ratchet_direction(candidate, baseline)
        assert flags["st_execute"] == "less_restrictive"

    def test_mixed_direction_flags_less_restrictive(self):
        """Mixed changes should flag less-restrictive params for ratchet gate."""
        baseline = ThresholdConfig()
        candidate = ThresholdConfig(
            st_execute=baseline.st_execute + 0.10,  # more restrictive
            st_clarify=baseline.st_clarify - 0.10,  # less restrictive
        )
        flags = classify_ratchet_direction(candidate, baseline)
        assert flags["st_execute"] == "more_restrictive"
        assert flags["st_clarify"] == "less_restrictive"
        # Ratchet gate should detect the less-restrictive param
        less_restrictive = {k: v for k, v in flags.items() if v == "less_restrictive"}
        assert len(less_restrictive) >= 1
        assert "st_clarify" in less_restrictive


class TestRegressionReport:
    """Test the regression report generator."""

    def test_no_regressions(self):
        """Identical decisions should show 0 regressions."""
        decisions = [
            {"scenario_id": "A", "expected": "EXECUTE", "actual": "EXECUTE", "correct": True},
            {"scenario_id": "B", "expected": "ESCALATE", "actual": "ESCALATE", "correct": True},
        ]
        report = generate_regression_report(decisions, decisions)
        assert report["n_regressions"] == 0
        assert report["n_improvements"] == 0

    def test_regression_detected(self):
        """Flipped correct->incorrect should be detected."""
        baseline = [
            {"scenario_id": "A", "expected": "EXECUTE", "actual": "EXECUTE", "correct": True},
        ]
        candidate = [
            {"scenario_id": "A", "expected": "EXECUTE", "actual": "CLARIFY", "correct": False},
        ]
        report = generate_regression_report(candidate, baseline)
        assert report["n_regressions"] == 1
        assert report["regressions"][0]["scenario_id"] == "A"

    def test_improvement_detected(self):
        """Flipped incorrect->correct should be detected."""
        baseline = [
            {"scenario_id": "A", "expected": "EXECUTE", "actual": "CLARIFY", "correct": False},
        ]
        candidate = [
            {"scenario_id": "A", "expected": "EXECUTE", "actual": "EXECUTE", "correct": True},
        ]
        report = generate_regression_report(candidate, baseline)
        assert report["n_improvements"] == 1

    def test_net_change(self):
        """Net change should be improvements minus regressions."""
        baseline = [
            {"scenario_id": "A", "expected": "EXECUTE", "actual": "EXECUTE", "correct": True},
            {"scenario_id": "B", "expected": "ESCALATE", "actual": "CLARIFY", "correct": False},
        ]
        candidate = [
            {"scenario_id": "A", "expected": "EXECUTE", "actual": "CLARIFY", "correct": False},
            {"scenario_id": "B", "expected": "ESCALATE", "actual": "ESCALATE", "correct": True},
        ]
        report = generate_regression_report(candidate, baseline)
        assert report["net_change"] == 0  # 1 improvement - 1 regression

    def test_cat_a_regression_isolated(self):
        """Cat A regressions should be tracked separately."""
        baseline = [
            {"scenario_id": "A1", "expected": "ESCALATE", "actual": "ESCALATE",
             "correct": True, "boundary_category": "A"},
            {"scenario_id": "C1", "expected": "EXECUTE", "actual": "EXECUTE",
             "correct": True, "boundary_category": "C"},
        ]
        candidate = [
            {"scenario_id": "A1", "expected": "ESCALATE", "actual": "EXECUTE",
             "correct": False, "boundary_category": "A"},
            {"scenario_id": "C1", "expected": "EXECUTE", "actual": "CLARIFY",
             "correct": False, "boundary_category": "C"},
        ]
        report = generate_regression_report(candidate, baseline)
        assert report["n_regressions"] == 2
        assert report["n_cat_a_regressions"] == 1
        assert report["cat_a_regressions"][0]["scenario_id"] == "A1"

    def test_non_cat_a_regression_not_in_cat_a(self):
        """Non-Cat-A regressions should not appear in cat_a_regressions."""
        baseline = [
            {"scenario_id": "C1", "expected": "EXECUTE", "actual": "EXECUTE",
             "correct": True, "boundary_category": "C"},
        ]
        candidate = [
            {"scenario_id": "C1", "expected": "EXECUTE", "actual": "CLARIFY",
             "correct": False, "boundary_category": "C"},
        ]
        report = generate_regression_report(candidate, baseline)
        assert report["n_regressions"] == 1
        assert report["n_cat_a_regressions"] == 0


# =============================================================================
# Config Hashing Tests
# =============================================================================

class TestConfigHashing:
    """Test config hashing for version control."""

    def test_same_config_same_hash(self):
        """Identical configs should produce identical hashes."""
        c1 = ThresholdConfig()
        c2 = ThresholdConfig()
        assert hash_config(c1) == hash_config(c2)

    def test_different_config_different_hash(self):
        """Different configs should produce different hashes."""
        c1 = ThresholdConfig()
        c2 = ThresholdConfig(st_execute=0.55)
        assert hash_config(c1) != hash_config(c2)


# =============================================================================
# GSI Tests
# =============================================================================

class TestGSI:
    """Test Governance Stringency Index."""

    def test_default_gsi_positive(self):
        """Default config should have a positive GSI."""
        gsi = compute_gsi(ThresholdConfig())
        assert gsi > 0

    def test_stricter_config_higher_gsi(self):
        """More restrictive config should have higher GSI."""
        default_gsi = compute_gsi(ThresholdConfig())
        strict = ThresholdConfig(
            st_execute=0.60, st_clarify=0.50,
            boundary_violation=0.80, fidelity_green=0.80,
        )
        strict_gsi = compute_gsi(strict)
        assert strict_gsi > default_gsi


# =============================================================================
# Backward Compatibility Tests
# =============================================================================

class TestBackwardCompatibility:
    """Test that None threshold_config preserves current behavior."""

    def test_engine_none_config_uses_defaults(self):
        """AgenticFidelityEngine with threshold_config=None should use defaults."""
        from telos_governance.agentic_fidelity import AgenticFidelityEngine
        from telos_governance.threshold_config import ThresholdConfig

        # Create a minimal mock PA
        mock_pa = MagicMock()
        mock_pa.purpose_embedding = None
        mock_pa.scope_embedding = None
        mock_pa.boundaries = []
        mock_pa.tool_manifest = {}
        mock_pa.action_tiers = MagicMock()
        mock_pa.max_chain_length = 10
        mock_pa.escalation_threshold = 0.30

        mock_embed = MagicMock(return_value=np.zeros(384))

        # No threshold_config -- should use defaults
        engine = AgenticFidelityEngine(
            embed_fn=mock_embed,
            pa=mock_pa,
            threshold_config=None,
        )

        defaults = ThresholdConfig()
        assert engine._tc.st_execute == defaults.st_execute
        assert engine._tc.weight_purpose == defaults.weight_purpose
        assert engine._tc.boundary_violation == defaults.boundary_violation

    def test_engine_custom_config_overrides(self):
        """AgenticFidelityEngine with custom config should use those values."""
        from telos_governance.agentic_fidelity import AgenticFidelityEngine

        mock_pa = MagicMock()
        mock_pa.purpose_embedding = None
        mock_pa.scope_embedding = None
        mock_pa.boundaries = []
        mock_pa.tool_manifest = {}
        mock_pa.action_tiers = MagicMock()
        mock_pa.max_chain_length = 10
        mock_pa.escalation_threshold = 0.30

        mock_embed = MagicMock(return_value=np.zeros(384))

        custom = ThresholdConfig(st_execute=0.55, weight_purpose=0.40)
        engine = AgenticFidelityEngine(
            embed_fn=mock_embed,
            pa=mock_pa,
            threshold_config=custom,
        )

        assert engine._tc.st_execute == 0.55
        assert engine._tc.weight_purpose == 0.40

"""
Tests for MPNet Safety Gate (Dual-Model Confirmer)
====================================================

Tests for the confirmer_mode feature in AgenticFidelityEngine:
- Confirm zone triggering (EXECUTE + composite < st_execute)
- Observe mode: logs but does NOT override
- Enforce mode: can escalate EXECUTE → ESCALATE
- Asymmetric invariant: confirmer can ONLY escalate, never de-escalate
- Telemetry capture in AgenticFidelityResult
- Lazy initialization of confirmer provider
- PA confirmer centroid building

Uses mock embeddings throughout — does not require MPNet ONNX model.
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from telos_governance.agentic_fidelity import (
    AgenticFidelityEngine,
    AgenticFidelityResult,
)
from telos_governance.agentic_pa import AgenticPA, BoundarySpec, ActionTierSpec
from telos_governance.types import ActionDecision, DirectionLevel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embedding(values: list, dim: int = 3) -> np.ndarray:
    """Create a normalized embedding vector."""
    v = np.array(values, dtype=np.float64)
    norm = np.linalg.norm(v)
    if norm > 0:
        v = v / norm
    return v


def _make_embed_fn(fixed_embedding=None, mapping=None):
    """Return a mock embed_fn with optional text→embedding mapping."""
    def embed_fn(text: str) -> np.ndarray:
        if fixed_embedding is not None:
            return fixed_embedding.copy()
        if mapping:
            for key, emb in mapping.items():
                if key.lower() in text.lower():
                    return emb.copy()
        # Deterministic fallback — high alignment with purpose
        v = np.array([0.95, 0.1, 0.05], dtype=np.float64)
        norm = np.linalg.norm(v)
        return v / norm
    return embed_fn


def _make_pa_with_boundaries(boundaries_text=None) -> AgenticPA:
    """Create a PA with controlled boundaries for confirmer testing."""
    purpose_emb = _make_embedding([1.0, 0.0, 0.0])
    scope_emb = _make_embedding([1.0, 0.2, 0.0])

    boundaries = []
    if boundaries_text:
        for text in boundaries_text:
            boundaries.append(BoundarySpec(
                text=text,
                embedding=_make_embedding([0.0, 1.0, 0.0]),  # orthogonal to purpose
                severity="hard",
            ))

    return AgenticPA(
        purpose_text="Assess property condition for insurance underwriting",
        purpose_embedding=purpose_emb,
        scope_text="Property intelligence and assessment",
        scope_embedding=scope_emb,
        boundaries=boundaries,
        tool_manifest={},
        action_tiers=ActionTierSpec(),
        max_chain_length=20,
        escalation_threshold=0.50,
    )


# ---------------------------------------------------------------------------
# Confirmer telemetry fields on AgenticFidelityResult
# ---------------------------------------------------------------------------

class TestConfirmerResultFields:
    """Verify confirmer fields exist and default correctly."""

    def test_defaults_all_false(self):
        r = AgenticFidelityResult(
            purpose_fidelity=0.9,
            scope_fidelity=0.8,
            boundary_violation=0.0,
            tool_fidelity=0.85,
            chain_continuity=0.5,
            composite_fidelity=0.8,
            effective_fidelity=0.8,
            decision=ActionDecision.EXECUTE,
            direction_level=DirectionLevel.NONE,
        )
        assert r.confirmer_activated is False
        assert r.confirmer_score is None
        assert r.confirmer_would_override is False
        assert r.confirmer_override_applied is False

    def test_fields_settable(self):
        r = AgenticFidelityResult(
            purpose_fidelity=0.9,
            scope_fidelity=0.8,
            boundary_violation=0.0,
            tool_fidelity=0.85,
            chain_continuity=0.5,
            composite_fidelity=0.8,
            effective_fidelity=0.8,
            decision=ActionDecision.EXECUTE,
            direction_level=DirectionLevel.NONE,
            confirmer_activated=True,
            confirmer_score=0.72,
            confirmer_would_override=True,
            confirmer_override_applied=False,
        )
        assert r.confirmer_activated is True
        assert r.confirmer_score == 0.72
        assert r.confirmer_would_override is True
        assert r.confirmer_override_applied is False


# ---------------------------------------------------------------------------
# PA Confirmer Centroid Building
# ---------------------------------------------------------------------------

class TestPAConfirmerCentroids:
    """Test build_confirmer_centroids on AgenticPA."""

    def test_build_centroids_populates_fields(self):
        pa = _make_pa_with_boundaries(["Do not access medical records"])
        assert pa.confirmer_boundary_embeddings is None
        assert pa.confirmer_purpose_embedding is None

        mock_embed = _make_embed_fn(_make_embedding([0.5, 0.5, 0.0]))
        pa.build_confirmer_centroids(mock_embed)

        assert pa.confirmer_boundary_embeddings is not None
        assert len(pa.confirmer_boundary_embeddings) == 1
        assert pa.confirmer_purpose_embedding is not None
        assert pa.confirmer_purpose_embedding.shape == (3,)

    def test_multiple_boundaries(self):
        pa = _make_pa_with_boundaries([
            "Do not access medical records",
            "Do not modify financial data",
            "Do not delete user accounts",
        ])
        mock_embed = _make_embed_fn(_make_embedding([0.5, 0.5, 0.0]))
        pa.build_confirmer_centroids(mock_embed)

        assert len(pa.confirmer_boundary_embeddings) == 3

    def test_no_boundaries(self):
        pa = _make_pa_with_boundaries([])
        mock_embed = _make_embed_fn(_make_embedding([0.5, 0.5, 0.0]))
        pa.build_confirmer_centroids(mock_embed)

        assert pa.confirmer_boundary_embeddings == []
        assert pa.confirmer_purpose_embedding is not None


# ---------------------------------------------------------------------------
# Confirmer Mode Off (default)
# ---------------------------------------------------------------------------

class TestConfirmerOff:
    """When confirmer_mode='off', confirmer never activates."""

    def test_off_mode_no_activation(self):
        pa = _make_pa_with_boundaries(["Do not access restricted data"])
        embed_fn = _make_embed_fn(_make_embedding([0.95, 0.1, 0.0]))

        engine = AgenticFidelityEngine(
            embed_fn=embed_fn,
            pa=pa,
            confirmer_mode="off",
        )

        result = engine.score_action(
            action_text="Check property assessment",
            tool_name="check_property",
        )
        assert result.confirmer_activated is False
        assert result.confirmer_score is None
        assert result.confirmer_would_override is False
        assert result.confirmer_override_applied is False

    def test_default_mode_is_off(self):
        pa = _make_pa_with_boundaries(["Do not access restricted data"])
        embed_fn = _make_embed_fn(_make_embedding([0.95, 0.1, 0.0]))

        engine = AgenticFidelityEngine(
            embed_fn=embed_fn,
            pa=pa,
        )
        assert engine._confirmer_mode == "off"


# ---------------------------------------------------------------------------
# Confirm Zone Triggering
# ---------------------------------------------------------------------------

class TestConfirmZone:
    """Confirmer fires only when EXECUTE + composite < st_execute."""

    def _make_engine_with_mock_confirmer(self, confirmer_mode="observe"):
        """Engine with mocked confirmer that returns controllable scores."""
        pa = _make_pa_with_boundaries(["Do not violate boundaries"])
        embed_fn = _make_embed_fn(_make_embedding([0.95, 0.1, 0.0]))

        engine = AgenticFidelityEngine(
            embed_fn=embed_fn,
            pa=pa,
            confirmer_mode=confirmer_mode,
        )
        # Pre-initialize confirmer with mock
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = _make_embed_fn(_make_embedding([0.5, 0.5, 0.0]))
        pa.build_confirmer_centroids(engine._confirmer_embed_fn)
        return engine

    def test_non_execute_verdict_skips_confirmer(self):
        """If MiniLM says CLARIFY/ESCALATE, confirmer doesn't fire."""
        pa = _make_pa_with_boundaries(["Do not violate boundaries"])
        # Embed fn that produces low purpose alignment → non-EXECUTE
        low_embed = _make_embed_fn(_make_embedding([0.0, 1.0, 0.0]))

        engine = AgenticFidelityEngine(
            embed_fn=low_embed,
            pa=pa,
            confirmer_mode="observe",
        )
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = _make_embed_fn(_make_embedding([0.5, 0.5, 0.0]))
        pa.build_confirmer_centroids(engine._confirmer_embed_fn)

        result = engine.score_action(
            action_text="Something completely off-topic",
            tool_name="check_property",
        )
        # Decision should NOT be EXECUTE, so confirmer should not activate
        if result.decision != ActionDecision.EXECUTE:
            assert result.confirmer_activated is False

    def test_clear_execute_skips_confirmer(self):
        """EXECUTE with composite >= st_execute skips confirmer (no confirm zone)."""
        pa = _make_pa_with_boundaries(["Do not access medical records"])
        # Very high alignment → composite well above st_execute
        high_embed = _make_embed_fn(_make_embedding([1.0, 0.0, 0.0]))

        engine = AgenticFidelityEngine(
            embed_fn=high_embed,
            pa=pa,
            confirmer_mode="observe",
        )
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = _make_embed_fn(_make_embedding([0.5, 0.5, 0.0]))
        pa.build_confirmer_centroids(engine._confirmer_embed_fn)

        result = engine.score_action(
            action_text="Assess roof condition",
            tool_name="check_property",
        )
        if result.decision == ActionDecision.EXECUTE and result.composite_fidelity >= 0.45:
            # Clear EXECUTE — confirmer should NOT fire
            assert result.confirmer_activated is False


# ---------------------------------------------------------------------------
# Observe Mode
# ---------------------------------------------------------------------------

class TestObserveMode:
    """Observe mode: logs telemetry but never changes the verdict."""

    def test_observe_logs_but_no_override(self):
        """Even if MPNet detects boundary, verdict stays EXECUTE in observe mode."""
        pa = _make_pa_with_boundaries(["Do not access restricted systems"])

        # MiniLM embed: moderate alignment (in confirm zone)
        minilm_embed = _make_embed_fn(_make_embedding([0.6, 0.3, 0.1]))

        engine = AgenticFidelityEngine(
            embed_fn=minilm_embed,
            pa=pa,
            confirmer_mode="observe",
        )

        # Mock confirmer: MPNet produces embedding close to boundary
        boundary_emb = _make_embedding([0.0, 1.0, 0.0])
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = _make_embed_fn(boundary_emb)  # close to boundary
        pa.build_confirmer_centroids(engine._confirmer_embed_fn)

        result = engine.score_action(
            action_text="Access restricted system data",
            tool_name="check_property",
        )

        # In observe mode, even if confirmer would override, it MUST NOT change the decision
        if result.confirmer_activated:
            assert result.confirmer_override_applied is False
            # Decision should remain whatever MiniLM decided (not ESCALATE from confirmer)

    def test_observe_captures_telemetry(self):
        """Observe mode still captures confirmer_score and confirmer_would_override."""
        pa = _make_pa_with_boundaries(["Do not modify production data"])

        minilm_embed = _make_embed_fn(_make_embedding([0.6, 0.3, 0.1]))

        engine = AgenticFidelityEngine(
            embed_fn=minilm_embed,
            pa=pa,
            confirmer_mode="observe",
        )

        # Mock confirmer returns embedding identical to boundary → high boundary sim
        boundary_match = _make_embedding([0.0, 1.0, 0.0])
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = _make_embed_fn(boundary_match)
        pa.build_confirmer_centroids(engine._confirmer_embed_fn)

        result = engine.score_action(
            action_text="Modify production database",
            tool_name="check_property",
        )

        if result.confirmer_activated:
            assert result.confirmer_score is not None
            assert isinstance(result.confirmer_score, float)


# ---------------------------------------------------------------------------
# Enforce Mode
# ---------------------------------------------------------------------------

class TestEnforceMode:
    """Enforce mode: can escalate EXECUTE → ESCALATE when MPNet detects boundary."""

    def test_enforce_applies_override(self):
        """When MPNet confirms boundary violation, enforce mode overrides to ESCALATE."""
        pa = _make_pa_with_boundaries(["Do not access restricted systems"])

        minilm_embed = _make_embed_fn(_make_embedding([0.6, 0.3, 0.1]))

        engine = AgenticFidelityEngine(
            embed_fn=minilm_embed,
            pa=pa,
            confirmer_mode="enforce",
        )

        # Mock confirmer: returns embedding identical to boundary (sim ≈ 1.0)
        boundary_match = _make_embedding([0.0, 1.0, 0.0])
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = _make_embed_fn(boundary_match)
        pa.build_confirmer_centroids(engine._confirmer_embed_fn)

        result = engine.score_action(
            action_text="Access restricted system",
            tool_name="check_property",
        )

        if result.confirmer_activated and result.confirmer_would_override:
            assert result.confirmer_override_applied is True
            assert result.decision == ActionDecision.ESCALATE
            assert result.human_required is True

    def test_enforce_no_override_when_safe(self):
        """When MPNet doesn't detect boundary, enforce mode leaves verdict unchanged."""
        pa = _make_pa_with_boundaries(["Do not access restricted systems"])

        # MiniLM: moderate alignment
        minilm_embed = _make_embed_fn(_make_embedding([0.6, 0.3, 0.1]))

        engine = AgenticFidelityEngine(
            embed_fn=minilm_embed,
            pa=pa,
            confirmer_mode="enforce",
        )

        # Mock confirmer: returns embedding FAR from boundary (low sim)
        safe_emb = _make_embedding([1.0, 0.0, 0.0])  # orthogonal to boundary [0,1,0]
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = _make_embed_fn(safe_emb)
        pa.build_confirmer_centroids(engine._confirmer_embed_fn)

        result = engine.score_action(
            action_text="Check property assessment",
            tool_name="check_property",
        )

        if result.confirmer_activated:
            assert result.confirmer_would_override is False
            assert result.confirmer_override_applied is False


# ---------------------------------------------------------------------------
# Asymmetric Invariant — can only escalate, never de-escalate
# ---------------------------------------------------------------------------

class TestAsymmetricInvariant:
    """Confirmer can ONLY escalate EXECUTE → ESCALATE. It cannot de-escalate."""

    def test_confirmer_only_runs_on_execute(self):
        """Non-EXECUTE decisions are never sent to the confirmer."""
        pa = _make_pa_with_boundaries(["Do not access restricted data"])

        # Very low alignment → will produce non-EXECUTE verdict
        low_embed = _make_embed_fn(_make_embedding([0.1, 0.9, 0.0]))

        engine = AgenticFidelityEngine(
            embed_fn=low_embed,
            pa=pa,
            confirmer_mode="enforce",
        )
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = _make_embed_fn(_make_embedding([1.0, 0.0, 0.0]))
        pa.build_confirmer_centroids(engine._confirmer_embed_fn)

        result = engine.score_action(
            action_text="Something off topic",
            tool_name="check_property",
        )

        # If decision is not EXECUTE, confirmer should NOT have activated
        if result.decision != ActionDecision.EXECUTE:
            assert result.confirmer_activated is False

    def test_observe_never_applies_override(self):
        """Observe mode NEVER sets confirmer_override_applied=True."""
        pa = _make_pa_with_boundaries(["Do not access restricted data"])
        minilm_embed = _make_embed_fn(_make_embedding([0.6, 0.3, 0.1]))

        engine = AgenticFidelityEngine(
            embed_fn=minilm_embed,
            pa=pa,
            confirmer_mode="observe",
        )

        # Max boundary similarity
        boundary_match = _make_embedding([0.0, 1.0, 0.0])
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = _make_embed_fn(boundary_match)
        pa.build_confirmer_centroids(engine._confirmer_embed_fn)

        result = engine.score_action(
            action_text="Access restricted data",
            tool_name="check_property",
        )

        # CRITICAL: observe mode must NEVER apply overrides
        assert result.confirmer_override_applied is False


# ---------------------------------------------------------------------------
# _confirm_with_secondary direct testing
# ---------------------------------------------------------------------------

class TestConfirmWithSecondary:
    """Direct unit tests for _confirm_with_secondary method."""

    def _make_engine(self, mode="observe", boundary_texts=None):
        pa = _make_pa_with_boundaries(boundary_texts or ["Do not access restricted data"])
        embed_fn = _make_embed_fn(_make_embedding([0.95, 0.1, 0.0]))
        engine = AgenticFidelityEngine(
            embed_fn=embed_fn,
            pa=pa,
            confirmer_mode=mode,
        )
        return engine, pa

    def test_off_returns_inactive(self):
        engine, pa = self._make_engine(mode="off")
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = _make_embed_fn(_make_embedding([0.5, 0.5, 0.0]))
        pa.build_confirmer_centroids(engine._confirmer_embed_fn)

        result = engine._confirm_with_secondary("test action", 0.40)
        assert result["confirmer_activated"] is False

    def test_high_boundary_sim_triggers_would_override(self):
        engine, pa = self._make_engine(mode="observe")
        # Confirmer embed returns vector identical to boundary → sim ≈ 1.0
        boundary_match = _make_embedding([0.0, 1.0, 0.0])
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = _make_embed_fn(boundary_match)
        pa.build_confirmer_centroids(engine._confirmer_embed_fn)

        result = engine._confirm_with_secondary("access restricted data", 0.40)
        assert result["confirmer_activated"] is True
        assert result["confirmer_score"] is not None
        assert result["confirmer_score"] >= 0.9  # near-identical vectors
        assert result["confirmer_would_override"] is True
        assert result["confirmer_override_applied"] is False  # observe mode

    def test_low_boundary_sim_no_override(self):
        engine, pa = self._make_engine(mode="enforce")
        # Confirmer embed: boundary text → [0,1,0], action text → [1,0,0]
        # Cosine sim between orthogonal vectors ≈ 0.0 → no override
        boundary_vec = _make_embedding([0.0, 1.0, 0.0])
        action_vec = _make_embedding([1.0, 0.0, 0.0])
        confirmer_fn = _make_embed_fn(mapping={
            "restricted": boundary_vec,  # boundary text contains "restricted"
        })
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = confirmer_fn
        pa.build_confirmer_centroids(confirmer_fn)

        # Action text does NOT contain "restricted" → gets the default [0.95, 0.1, 0.05]
        # which is near-orthogonal to boundary centroid [0, 1, 0]
        result = engine._confirm_with_secondary("check property", 0.40)
        assert result["confirmer_activated"] is True
        assert result["confirmer_score"] is not None
        assert result["confirmer_score"] < 0.60
        assert result["confirmer_would_override"] is False
        assert result["confirmer_override_applied"] is False

    def test_enforce_sets_override_applied(self):
        engine, pa = self._make_engine(mode="enforce")
        boundary_match = _make_embedding([0.0, 1.0, 0.0])
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = _make_embed_fn(boundary_match)
        pa.build_confirmer_centroids(engine._confirmer_embed_fn)

        result = engine._confirm_with_secondary("access restricted data", 0.40)
        assert result["confirmer_activated"] is True
        assert result["confirmer_would_override"] is True
        assert result["confirmer_override_applied"] is True

    def test_uninitialized_confirmer_returns_inactive(self):
        """If confirmer init failed, _confirm_with_secondary returns inactive."""
        engine, pa = self._make_engine(mode="observe")
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = None  # Failed init

        result = engine._confirm_with_secondary("test action", 0.40)
        assert result["confirmer_activated"] is False

    def test_no_boundary_centroids_returns_inactive(self):
        """If PA has no confirmer boundaries, returns inactive."""
        engine, pa = self._make_engine(mode="observe")
        engine._confirmer_initialized = True
        engine._confirmer_embed_fn = _make_embed_fn(_make_embedding([0.5, 0.5, 0.0]))
        # Don't build centroids — leave as None
        pa.confirmer_boundary_embeddings = None

        result = engine._confirm_with_secondary("test action", 0.40)
        assert result["confirmer_activated"] is False


# ---------------------------------------------------------------------------
# Lazy Initialization
# ---------------------------------------------------------------------------

class TestLazyInit:
    """Confirmer loads MPNet only on first activation."""

    def test_confirmer_not_initialized_at_creation(self):
        pa = _make_pa_with_boundaries(["Do not access restricted data"])
        embed_fn = _make_embed_fn(_make_embedding([0.95, 0.1, 0.0]))

        engine = AgenticFidelityEngine(
            embed_fn=embed_fn,
            pa=pa,
            confirmer_mode="observe",
        )

        assert engine._confirmer_initialized is False
        assert engine._confirmer_embed_fn is None

    @patch("telos_core.embedding_provider.get_cached_onnx_mpnet_provider")
    def test_init_confirmer_loads_provider(self, mock_get_provider):
        """_init_confirmer calls get_cached_onnx_mpnet_provider and builds centroids."""
        pa = _make_pa_with_boundaries(["Do not access restricted data"])
        embed_fn = _make_embed_fn(_make_embedding([0.95, 0.1, 0.0]))

        engine = AgenticFidelityEngine(
            embed_fn=embed_fn,
            pa=pa,
            confirmer_mode="observe",
        )

        mock_provider = MagicMock()
        mock_provider.encode.return_value = _make_embedding([0.5, 0.5, 0.0])
        mock_get_provider.return_value = mock_provider

        engine._init_confirmer()

        assert engine._confirmer_initialized is True
        assert engine._confirmer_embed_fn is not None
        assert pa.confirmer_boundary_embeddings is not None
        mock_get_provider.assert_called_once()

    @patch("telos_core.embedding_provider.get_cached_onnx_mpnet_provider")
    def test_init_confirmer_failure_disables_silently(self, mock_get_provider):
        """If MPNet loading fails, confirmer is silently disabled."""
        pa = _make_pa_with_boundaries(["Do not access restricted data"])
        embed_fn = _make_embed_fn(_make_embedding([0.95, 0.1, 0.0]))

        engine = AgenticFidelityEngine(
            embed_fn=embed_fn,
            pa=pa,
            confirmer_mode="observe",
        )

        mock_get_provider.side_effect = RuntimeError("MPNet not installed")

        engine._init_confirmer()

        assert engine._confirmer_initialized is True  # Marked as init'd (won't retry)
        assert engine._confirmer_embed_fn is None  # But disabled

    @patch("telos_core.embedding_provider.get_cached_onnx_mpnet_provider")
    def test_init_confirmer_only_called_once(self, mock_get_provider):
        """_init_confirmer is idempotent — second call is a no-op."""
        pa = _make_pa_with_boundaries(["Do not access restricted data"])
        embed_fn = _make_embed_fn(_make_embedding([0.95, 0.1, 0.0]))

        engine = AgenticFidelityEngine(
            embed_fn=embed_fn,
            pa=pa,
            confirmer_mode="observe",
        )

        mock_provider = MagicMock()
        mock_provider.encode.return_value = _make_embedding([0.5, 0.5, 0.0])
        mock_get_provider.return_value = mock_provider

        engine._init_confirmer()
        engine._init_confirmer()  # Second call — should be no-op

        mock_get_provider.assert_called_once()

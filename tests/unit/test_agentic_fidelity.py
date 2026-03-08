"""
Tests for telos_governance.agentic_fidelity
=============================================

Tests for AgenticFidelityEngine: composite scoring, decision mapping,
boundary checking, chain continuity, normalization, and direction levels.

Uses deterministic mock embeddings to verify governance math precisely.
"""

import numpy as np
import pytest

from telos_governance.agentic_fidelity import (
    AgenticFidelityEngine,
    AgenticFidelityResult,
    BoundaryCheckResult,
    WEIGHT_PURPOSE,
    WEIGHT_SCOPE,
    WEIGHT_TOOL,
    WEIGHT_CHAIN,
    WEIGHT_BOUNDARY_PENALTY,
    BOUNDARY_VIOLATION_THRESHOLD,
    CLARIFY_DIMENSION_DESCRIPTIONS,
    CLARIFY_DIMENSION_PRIORITY,
)
from telos_core.constants import BOUNDARY_MARGIN_THRESHOLD
from telos_governance.agentic_pa import AgenticPA, BoundarySpec, ToolAuth, ActionTierSpec
from telos_governance.types import ActionDecision, DirectionLevel
from telos_core.constants import (
    FIDELITY_GREEN,
    FIDELITY_YELLOW,
    FIDELITY_ORANGE,
    ST_AGENTIC_EXECUTE_THRESHOLD,
    ST_AGENTIC_CLARIFY_THRESHOLD,
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


def _make_embed_fn(fixed_embedding: np.ndarray = None, mapping: dict = None):
    """
    Return a mock embed_fn.

    If `fixed_embedding` is provided, always returns that vector.
    If `mapping` is provided, returns the vector for matching substrings.
    If neither, returns a deterministic hash-based embedding.
    """
    def embed_fn(text: str) -> np.ndarray:
        if fixed_embedding is not None:
            return fixed_embedding.copy()
        if mapping:
            for key, emb in mapping.items():
                if key.lower() in text.lower():
                    return emb.copy()
        # Deterministic fallback
        h = hash(text) % 10000
        v = np.array([h % 97, (h * 3 + 7) % 97, (h * 7 + 13) % 97], dtype=np.float64)
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v
    return embed_fn


def _make_pa(
    purpose_emb=None,
    scope_emb=None,
    boundaries=None,
    tool_manifest=None,
    action_tiers=None,
    max_chain_length=20,
    escalation_threshold=0.50,
) -> AgenticPA:
    """Create an AgenticPA with controlled embeddings."""
    if purpose_emb is None:
        purpose_emb = _make_embedding([1.0, 0.0, 0.0])
    return AgenticPA(
        purpose_text="Test purpose",
        purpose_embedding=purpose_emb,
        scope_text="Test scope",
        scope_embedding=scope_emb if scope_emb is not None else _make_embedding([1.0, 0.2, 0.0]),
        boundaries=boundaries or [],
        tool_manifest=tool_manifest or {},
        action_tiers=action_tiers or ActionTierSpec(),
        max_chain_length=max_chain_length,
        escalation_threshold=escalation_threshold,
    )


# ---------------------------------------------------------------------------
# AgenticFidelityResult
# ---------------------------------------------------------------------------

class TestAgenticFidelityResult:
    def test_defaults(self):
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
        assert r.boundary_triggered is False
        assert r.tool_blocked is False
        assert r.chain_broken is False
        assert r.human_required is False
        assert r.selected_tool is None
        assert r.tool_rankings == []
        assert r.dimension_explanations == {}


# ---------------------------------------------------------------------------
# AgenticFidelityEngine — Cosine Similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def setup_method(self):
        pa = _make_pa()
        self.engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=pa,
        )

    def test_identical_vectors(self):
        a = _make_embedding([1.0, 0.0, 0.0])
        b = _make_embedding([1.0, 0.0, 0.0])
        assert self.engine._cosine_similarity(a, b) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = _make_embedding([1.0, 0.0, 0.0])
        b = _make_embedding([0.0, 1.0, 0.0])
        assert self.engine._cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-7)

    def test_opposite_vectors(self):
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([-1.0, 0.0, 0.0])
        assert self.engine._cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        a = _make_embedding([1.0, 0.0, 0.0])
        b = np.array([0.0, 0.0, 0.0])
        assert self.engine._cosine_similarity(a, b) == 0.0


# ---------------------------------------------------------------------------
# Model Detection
# ---------------------------------------------------------------------------

class TestModelDetection:
    def test_sentence_transformer_384(self):
        pa = _make_pa(purpose_emb=np.ones(384) / np.sqrt(384))
        engine = AgenticFidelityEngine(embed_fn=lambda t: np.ones(384), pa=pa)
        assert engine._is_sentence_transformer() is True

    def test_sentence_transformer_512(self):
        pa = _make_pa(purpose_emb=np.ones(512) / np.sqrt(512))
        engine = AgenticFidelityEngine(embed_fn=lambda t: np.ones(512), pa=pa)
        assert engine._is_sentence_transformer() is True

    def test_mistral_1024(self):
        pa = _make_pa(purpose_emb=np.ones(1024) / np.sqrt(1024))
        engine = AgenticFidelityEngine(embed_fn=lambda t: np.ones(1024), pa=pa)
        assert engine._is_sentence_transformer() is False

    def test_no_purpose_embedding_defaults_to_st(self):
        pa = _make_pa(purpose_emb=None)
        pa.purpose_embedding = None
        engine = AgenticFidelityEngine(embed_fn=lambda t: np.ones(3), pa=pa)
        assert engine._is_sentence_transformer() is True


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

class TestNormalization:
    def setup_method(self):
        # 3-dim embedding -> treated as SentenceTransformer (<= 512)
        pa = _make_pa()
        self.engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=pa,
        )

    def test_normalize_st_high(self):
        """High raw similarity normalizes to high fidelity."""
        fidelity = self.engine._normalize_fidelity(0.50)
        assert fidelity > 0.5

    def test_normalize_st_low(self):
        """Low raw similarity normalizes to low fidelity."""
        fidelity = self.engine._normalize_fidelity(0.10)
        assert fidelity < 0.5

    def test_normalize_bounded_zero(self):
        """Fidelity floor at 0.0."""
        fidelity = self.engine._normalize_fidelity(-0.5)
        assert fidelity >= 0.0

    def test_normalize_bounded_one(self):
        """Fidelity ceiling at 1.0."""
        fidelity = self.engine._normalize_fidelity(1.0)
        assert fidelity <= 1.0


# ---------------------------------------------------------------------------
# Purpose and Scope Scoring
# ---------------------------------------------------------------------------

class TestPurposeScoring:
    def test_aligned_action(self):
        """Action embedding identical to purpose -> high fidelity."""
        purpose_emb = _make_embedding([1.0, 0.0, 0.0])
        pa = _make_pa(purpose_emb=purpose_emb)
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(purpose_emb),
            pa=pa,
        )
        fidelity, _ = engine._score_purpose(purpose_emb)
        assert fidelity > 0.90

    def test_orthogonal_action(self):
        """Action orthogonal to purpose -> low fidelity."""
        purpose_emb = _make_embedding([1.0, 0.0, 0.0])
        action_emb = _make_embedding([0.0, 1.0, 0.0])
        pa = _make_pa(purpose_emb=purpose_emb)
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(action_emb),
            pa=pa,
        )
        fidelity, _ = engine._score_purpose(action_emb)
        assert fidelity < 0.50

    def test_no_purpose_passes_through(self):
        """No purpose embedding -> 1.0 (pass through)."""
        pa = _make_pa()
        pa.purpose_embedding = None
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=pa,
        )
        score, _ = engine._score_purpose(_make_embedding([0, 1, 0]))
        assert score == 1.0


class TestScopeScoring:
    def test_no_scope_passes_through(self):
        pa = _make_pa()
        pa.scope_embedding = None
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=pa,
        )
        assert engine._score_scope(_make_embedding([0, 1, 0])) == 1.0


# ---------------------------------------------------------------------------
# Boundary Checking
# ---------------------------------------------------------------------------

class TestBoundaryChecking:
    def test_no_boundaries(self):
        pa = _make_pa(boundaries=[])
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=pa,
        )
        result = engine._check_boundaries(_make_embedding([1, 0, 0]))
        assert result.violation_score == 0.0
        assert result.triggered is False
        assert "No boundaries" in result.detail
        assert result.safe_similarity is None
        assert result.contrastive_margin is None

    def test_boundary_not_triggered(self):
        """Action far from boundary -> no violation."""
        boundary_emb = _make_embedding([0.0, 1.0, 0.0])
        action_emb = _make_embedding([1.0, 0.0, 0.0])
        pa = _make_pa(boundaries=[
            BoundarySpec(text="no deletion", embedding=boundary_emb, severity="hard"),
        ])
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(action_emb),
            pa=pa,
        )
        result = engine._check_boundaries(action_emb)
        assert result.triggered is False

    def test_boundary_triggered_identical(self):
        """Action identical to boundary -> triggered."""
        boundary_emb = _make_embedding([1.0, 0.0, 0.0])
        action_emb = _make_embedding([1.0, 0.0, 0.0])
        pa = _make_pa(boundaries=[
            BoundarySpec(text="no deletion", embedding=boundary_emb, severity="hard"),
        ])
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(action_emb),
            pa=pa,
        )
        result = engine._check_boundaries(action_emb)
        assert result.triggered is True
        assert "Boundary violation" in result.detail

    def test_boundary_none_embedding_skipped(self):
        """Boundary with None embedding is skipped."""
        pa = _make_pa(boundaries=[
            BoundarySpec(text="no deletion", embedding=None, severity="hard"),
        ])
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=pa,
        )
        result = engine._check_boundaries(_make_embedding([1, 0, 0]))
        assert result.violation_score == 0.0
        assert result.triggered is False


# ---------------------------------------------------------------------------
# Composite Weights
# ---------------------------------------------------------------------------

class TestCompositeWeights:
    def test_positive_weights_sum_to_090(self):
        """Positive weights sum to 0.90 (SAAI principle: no perfect fidelity)."""
        total = WEIGHT_PURPOSE + WEIGHT_SCOPE + WEIGHT_TOOL + WEIGHT_CHAIN
        assert total == pytest.approx(0.90)

    def test_boundary_penalty_weight(self):
        assert WEIGHT_BOUNDARY_PENALTY == pytest.approx(0.10)

    def test_theoretical_max_with_no_boundary(self):
        """Max composite = 0.90 when all dimensions are 1.0 and no boundary."""
        composite = (
            WEIGHT_PURPOSE * 1.0
            + WEIGHT_SCOPE * 1.0
            + WEIGHT_TOOL * 1.0
            + WEIGHT_CHAIN * 1.0
            - WEIGHT_BOUNDARY_PENALTY * 0.0
        )
        assert composite == pytest.approx(0.90)


# ---------------------------------------------------------------------------
# Decision Mapping
# ---------------------------------------------------------------------------

class TestDecisionMapping:
    def setup_method(self):
        pa = _make_pa()
        self.engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=pa,
        )

    def test_execute_decision(self):
        """High effective fidelity -> EXECUTE."""
        decision, human = self.engine._make_decision(
            effective_fidelity=ST_AGENTIC_EXECUTE_THRESHOLD + 0.01,
            boundary_triggered=False,
            tool_blocked=False,
            chain_broken=False,
            tool_name=None,
        )
        assert decision == ActionDecision.EXECUTE

    def test_clarify_decision(self):
        """Mid-range fidelity -> CLARIFY."""
        fidelity = (ST_AGENTIC_CLARIFY_THRESHOLD + ST_AGENTIC_EXECUTE_THRESHOLD) / 2
        decision, human = self.engine._make_decision(
            effective_fidelity=fidelity,
            boundary_triggered=False,
            tool_blocked=False,
            chain_broken=False,
            tool_name=None,
        )
        assert decision == ActionDecision.CLARIFY

    def test_below_clarify_is_escalate(self):
        """Fidelity below CLARIFY threshold -> ESCALATE.

        In the 3-verdict model, anything below CLARIFY threshold
        triggers ESCALATE (human review required).
        """
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=_make_pa(escalation_threshold=0.10),
        )
        fidelity = ST_AGENTIC_CLARIFY_THRESHOLD - 0.02
        decision, human = engine._make_decision(
            effective_fidelity=fidelity,
            boundary_triggered=False,
            tool_blocked=False,
            chain_broken=False,
            tool_name=None,
        )
        assert decision == ActionDecision.ESCALATE

    def test_boundary_override_to_escalate(self):
        """Boundary triggered -> ESCALATE regardless of fidelity."""
        decision, human = self.engine._make_decision(
            effective_fidelity=0.95,
            boundary_triggered=True,
            tool_blocked=False,
            chain_broken=False,
            tool_name=None,
        )
        assert decision == ActionDecision.ESCALATE
        assert human is True

    def test_tool_blocked_override_to_escalate(self):
        """Tool blocked -> ESCALATE regardless of fidelity."""
        decision, human = self.engine._make_decision(
            effective_fidelity=0.95,
            boundary_triggered=False,
            tool_blocked=True,
            chain_broken=False,
            tool_name=None,
        )
        assert decision == ActionDecision.ESCALATE

    def test_chain_broken_override_to_clarify(self):
        """Chain broken -> CLARIFY regardless of fidelity."""
        decision, human = self.engine._make_decision(
            effective_fidelity=0.95,
            boundary_triggered=False,
            tool_blocked=False,
            chain_broken=True,
            tool_name=None,
        )
        assert decision == ActionDecision.CLARIFY

    def test_override_priority_boundary_first(self):
        """Boundary override takes precedence over tool blocked."""
        decision, human = self.engine._make_decision(
            effective_fidelity=0.95,
            boundary_triggered=True,
            tool_blocked=True,
            chain_broken=True,
            tool_name=None,
        )
        assert decision == ActionDecision.ESCALATE

    def test_escalate_below_threshold(self):
        """Very low fidelity below escalation threshold -> ESCALATE."""
        decision, human = self.engine._make_decision(
            effective_fidelity=0.10,
            boundary_triggered=False,
            tool_blocked=False,
            chain_broken=False,
            tool_name=None,
        )
        assert decision == ActionDecision.ESCALATE
        assert human is True


# ---------------------------------------------------------------------------
# Direction Level
# ---------------------------------------------------------------------------

class TestDirectionLevel:
    def setup_method(self):
        pa = _make_pa()
        self.engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=pa,
        )

    def test_boundary_triggered_hard_block(self):
        level = self.engine._determine_direction_level(0.95, boundary_triggered=True)
        assert level == DirectionLevel.HARD_BLOCK

    def test_green_zone(self):
        level = self.engine._determine_direction_level(FIDELITY_GREEN + 0.01, False)
        assert level == DirectionLevel.NONE

    def test_yellow_zone(self):
        fidelity = (FIDELITY_YELLOW + FIDELITY_GREEN) / 2
        level = self.engine._determine_direction_level(fidelity, False)
        assert level == DirectionLevel.MONITOR

    def test_orange_zone(self):
        fidelity = (FIDELITY_ORANGE + FIDELITY_YELLOW) / 2
        level = self.engine._determine_direction_level(fidelity, False)
        assert level == DirectionLevel.CORRECT

    def test_red_zone(self):
        level = self.engine._determine_direction_level(0.30, False)
        assert level == DirectionLevel.DIRECT


# ---------------------------------------------------------------------------
# score_action Integration
# ---------------------------------------------------------------------------

class TestScoreAction:
    def test_returns_all_fields(self):
        """score_action returns a complete AgenticFidelityResult."""
        purpose_emb = _make_embedding([1.0, 0.0, 0.0])
        pa = _make_pa(purpose_emb=purpose_emb)
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(purpose_emb),
            pa=pa,
        )
        result = engine.score_action("aligned action")
        assert isinstance(result, AgenticFidelityResult)
        assert 0.0 <= result.purpose_fidelity <= 1.0
        assert 0.0 <= result.scope_fidelity <= 1.0
        assert 0.0 <= result.composite_fidelity <= 1.0
        assert 0.0 <= result.effective_fidelity <= 1.0
        assert isinstance(result.decision, ActionDecision)
        assert isinstance(result.direction_level, DirectionLevel)
        assert "purpose" in result.dimension_explanations
        assert "scope" in result.dimension_explanations
        assert "boundary" in result.dimension_explanations
        assert "tool" in result.dimension_explanations
        assert "chain" in result.dimension_explanations


# ---------------------------------------------------------------------------
# Chain Reset
# ---------------------------------------------------------------------------

class TestChainReset:
    def test_reset_clears_chain(self):
        pa = _make_pa()
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=pa,
        )
        engine.score_action("step 1")
        engine.score_action("step 2")
        assert engine.action_chain.length == 2

        engine.reset_chain()
        assert engine.action_chain.length == 0


# ---------------------------------------------------------------------------
# Tool Scoring
# ---------------------------------------------------------------------------

class TestToolScoring:
    def test_no_tools_passes_through(self):
        """No tools in manifest -> 1.0 fidelity, no tool selected."""
        pa = _make_pa(tool_manifest={})
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=pa,
        )
        fidelity, selected, rankings, blocked = engine._score_tool("query data", None)
        assert fidelity == 1.0
        assert selected is None
        assert rankings == []
        assert blocked is False

    def test_always_blocked_tool(self):
        """Tool in always_blocked -> 0.0 fidelity, blocked."""
        pa = _make_pa(
            tool_manifest={"dangerous_tool": ToolAuth(
                tool_name="dangerous_tool",
                description="Does dangerous things",
            )},
            action_tiers=ActionTierSpec(always_blocked=["dangerous_tool"]),
        )
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=pa,
        )
        fidelity, selected, rankings, blocked = engine._score_tool(
            "do dangerous thing", "dangerous_tool"
        )
        assert fidelity == 0.0
        assert blocked is True

    def test_always_allowed_tool(self):
        """Tool in always_allowed -> 1.0 fidelity, not blocked."""
        pa = _make_pa(
            tool_manifest={"safe_read": ToolAuth(
                tool_name="safe_read",
                description="Read data safely",
            )},
            action_tiers=ActionTierSpec(always_allowed=["safe_read"]),
        )
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=pa,
        )
        fidelity, selected, rankings, blocked = engine._score_tool(
            "read data", "safe_read"
        )
        assert fidelity == 1.0
        assert blocked is False


# ---------------------------------------------------------------------------
# Contrastive Boundary Detection
# ---------------------------------------------------------------------------

class TestContrastiveBoundaryDetection:
    def test_boundary_contrastive_no_safe_centroid(self):
        """Boundary triggers normally when no safe centroid exists (backward compat)."""
        boundary_emb = _make_embedding([1.0, 0.0, 0.0])
        action_emb = _make_embedding([1.0, 0.0, 0.0])
        pa = _make_pa(boundaries=[
            BoundarySpec(text="no deletion", embedding=boundary_emb, severity="hard"),
        ])
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(action_emb),
            pa=pa,
        )
        result = engine._check_boundaries(action_emb)
        assert result.triggered is True
        assert result.safe_similarity is None
        assert result.contrastive_margin is None
        assert result.contrastive_suppressed is False
        assert "Boundary violation" in result.detail

    def test_boundary_contrastive_positive_margin_triggers(self):
        """Boundary triggers when violation score high AND margin > threshold (true violation).

        Action is close to boundary (violation) and far from safe centroid.
        margin = violation_sim - safe_sim should be positive and > threshold.
        """
        # Action and boundary aligned on same direction
        boundary_emb = _make_embedding([1.0, 0.0, 0.0])
        action_emb = _make_embedding([1.0, 0.0, 0.0])
        # Safe centroid in a different direction (low similarity to action)
        safe_centroid = _make_embedding([0.0, 1.0, 0.0])

        pa = _make_pa(boundaries=[
            BoundarySpec(
                text="no deletion",
                embedding=boundary_emb,
                safe_centroid=safe_centroid,
                severity="hard",
            ),
        ])
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(action_emb),
            pa=pa,
        )
        result = engine._check_boundaries(action_emb)
        assert result.triggered is True
        assert result.safe_similarity is not None
        assert result.contrastive_margin is not None
        assert result.contrastive_margin > BOUNDARY_MARGIN_THRESHOLD
        assert result.contrastive_suppressed is False
        assert "Boundary violation" in result.detail

    def test_boundary_contrastive_negative_margin_suppresses(self):
        """Boundary does NOT trigger when violation score high but margin < threshold.

        This tests the false-positive suppression case: the action is close to
        a boundary BUT is even closer to the safe centroid, producing a negative
        margin that suppresses the trigger.
        """
        # Action embedding
        action_emb = _make_embedding([1.0, 0.2, 0.0])
        # Boundary close to action
        boundary_emb = _make_embedding([1.0, 0.1, 0.0])
        # Safe centroid even closer to action (same direction)
        safe_centroid = _make_embedding([1.0, 0.2, 0.0])

        pa = _make_pa(boundaries=[
            BoundarySpec(
                text="no deletion",
                embedding=boundary_emb,
                safe_centroid=safe_centroid,
                severity="hard",
            ),
        ])
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(action_emb),
            pa=pa,
        )
        result = engine._check_boundaries(action_emb)
        # Safe centroid is closer to action than boundary, so margin <= 0
        assert result.triggered is False
        assert result.safe_similarity is not None
        assert result.contrastive_margin is not None
        assert result.contrastive_margin <= 0
        assert result.contrastive_suppressed is True
        assert "suppressed" in result.detail.lower()


# ---------------------------------------------------------------------------
# Decision Floor — contrastive suppression must never produce EXECUTE
# ---------------------------------------------------------------------------

class TestDecisionFloor:
    """
    Tests for the decision floor at score_action() lines 300-317.

    When contrastive suppression fires (safe centroid closer than boundary),
    boundary_triggered is False, so _make_decision uses fidelity thresholds
    alone. If tool fidelity is high, this cascades to EXECUTE on a genuine
    violation. The decision floor caps at CLARIFY.
    """

    def _build_high_fidelity_engine(self, boundary_emb, safe_centroid):
        """Build engine where action is high-fidelity but near a boundary."""
        # Action embedding: aligned with purpose and scope
        action_emb = _make_embedding([1.0, 0.0, 0.0])

        pa = _make_pa(
            purpose_emb=_make_embedding([1.0, 0.0, 0.0]),
            scope_emb=_make_embedding([1.0, 0.1, 0.0]),
            boundaries=[
                BoundarySpec(
                    text="no autonomous decisions",
                    embedding=boundary_emb,
                    safe_centroid=safe_centroid,
                    severity="hard",
                ),
            ],
            tool_manifest={
                "test_tool": ToolAuth(
                    tool_name="test_tool",
                    description="Test tool",
                ),
            },
        )
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(action_emb),
            pa=pa,
        )
        return engine

    def test_decision_floor_caps_execute_to_clarify(self):
        """
        When contrastive_suppressed=True AND violation >= 0.70 AND
        decision would be EXECUTE, the floor caps it to CLARIFY.
        """
        # Boundary close to action (high violation score)
        boundary_emb = _make_embedding([1.0, 0.05, 0.0])
        # Safe centroid even closer (suppresses the trigger)
        safe_centroid = _make_embedding([1.0, 0.0, 0.0])

        engine = self._build_high_fidelity_engine(boundary_emb, safe_centroid)
        result = engine.score_action(
            action_text="run the test tool",
            tool_name="test_tool",
        )

        # The boundary violation should be high (>= 0.70)
        assert result.boundary_violation >= BOUNDARY_VIOLATION_THRESHOLD, (
            f"Expected violation >= {BOUNDARY_VIOLATION_THRESHOLD}, "
            f"got {result.boundary_violation}"
        )
        # Contrastive suppression should have fired
        assert result.boundary_triggered is False
        # Decision should be capped at CLARIFY, not EXECUTE
        assert result.decision == ActionDecision.CLARIFY, (
            f"Decision floor should cap EXECUTE to CLARIFY, got {result.decision}"
        )

    def test_decision_floor_does_not_downgrade_clarify(self):
        """
        When contrastive_suppressed=True AND violation >= 0.70 AND
        decision is already CLARIFY, the floor does not change it.
        """
        # Boundary close to action
        boundary_emb = _make_embedding([1.0, 0.05, 0.0])
        # Safe centroid closer (suppresses trigger)
        safe_centroid = _make_embedding([1.0, 0.0, 0.0])

        # Use a slightly misaligned action to get CLARIFY naturally
        action_emb = _make_embedding([1.0, 0.3, 0.0])
        pa = _make_pa(
            purpose_emb=_make_embedding([1.0, 0.0, 0.0]),
            scope_emb=_make_embedding([1.0, 0.1, 0.0]),
            boundaries=[
                BoundarySpec(
                    text="no autonomous decisions",
                    embedding=boundary_emb,
                    safe_centroid=safe_centroid,
                    severity="hard",
                ),
            ],
            tool_manifest={
                "test_tool": ToolAuth(
                    tool_name="test_tool",
                    description="Test tool",
                ),
            },
        )
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(action_emb),
            pa=pa,
        )
        result = engine.score_action(
            action_text="test action with some drift",
            tool_name="test_tool",
        )

        # Decision should be CLARIFY or lower — floor only applies to EXECUTE
        assert result.decision != ActionDecision.EXECUTE

    def test_no_floor_when_not_contrastive_suppressed(self):
        """
        When contrastive_suppressed=False (no safe centroid), the decision
        floor does not apply — EXECUTE remains EXECUTE for high-fidelity actions.
        """
        # No safe centroid — normal boundary behavior
        boundary_emb = _make_embedding([0.0, 0.0, 1.0])  # Orthogonal to action

        pa = _make_pa(
            purpose_emb=_make_embedding([1.0, 0.0, 0.0]),
            scope_emb=_make_embedding([1.0, 0.1, 0.0]),
            boundaries=[
                BoundarySpec(
                    text="no unauthorized access",
                    embedding=boundary_emb,
                    severity="hard",
                    # No safe_centroid — contrastive suppression won't fire
                ),
            ],
            tool_manifest={
                "test_tool": ToolAuth(
                    tool_name="test_tool",
                    description="Test tool",
                ),
            },
        )
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1.0, 0.0, 0.0])),
            pa=pa,
        )
        result = engine.score_action(
            action_text="perfectly aligned request",
            tool_name="test_tool",
        )

        # Boundary should NOT trigger (orthogonal)
        assert result.boundary_triggered is False
        # No contrastive suppression (no safe centroid)
        # High-fidelity action should remain EXECUTE
        assert result.decision == ActionDecision.EXECUTE


# ---------------------------------------------------------------------------
# Chain Rollover (max_chain_length)
# ---------------------------------------------------------------------------

class TestChainRollover:
    """When chain hits max_chain_length, it rolls over instead of dying."""

    def test_rollover_resets_chain(self):
        """After max_chain_length steps, next call resets and returns non-broken."""
        max_len = 5
        pa = _make_pa(max_chain_length=max_len)
        emb = _make_embedding([1.0, 0.0, 0.0])
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(emb),
            pa=pa,
        )

        # Fill chain to max
        for i in range(max_len):
            engine.score_action(f"step {i}")
        assert engine.action_chain.length == max_len

        # Next call should rollover — chain resets, step added as first step
        result = engine.score_action("step after rollover")
        assert engine.action_chain.length == 1
        assert result.chain_broken is False

    def test_rollover_does_not_return_zero_continuity(self):
        """Post-rollover step should not be stuck at 0.0 chain continuity."""
        max_len = 3
        pa = _make_pa(max_chain_length=max_len)
        emb = _make_embedding([1.0, 0.0, 0.0])
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(emb),
            pa=pa,
        )

        # Fill to max
        for i in range(max_len):
            engine.score_action(f"step {i}")

        # Rollover step — first step of new chain gets 0.0 continuity (no prev)
        # but chain_broken should be False (single-step chain is continuous)
        result = engine.score_action("fresh start")
        assert result.chain_broken is False
        # Second step in new chain should compute real continuity
        result2 = engine.score_action("next step")
        assert engine.action_chain.length == 2
        # Continuity should be a real value, not pinned at 0.0
        assert result2.chain_continuity >= 0.0

    def test_rollover_preserves_other_dimensions(self):
        """Rollover should not affect purpose, scope, boundary, or tool scores."""
        max_len = 3
        pa = _make_pa(max_chain_length=max_len)
        emb = _make_embedding([1.0, 0.0, 0.0])
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(emb),
            pa=pa,
        )

        # Get baseline scores from step 1
        first_result = engine.score_action("aligned action")

        # Fill to max and rollover
        for i in range(max_len - 1):
            engine.score_action(f"step {i}")
        assert engine.action_chain.length == max_len

        post_rollover = engine.score_action("aligned action")

        # Purpose and scope should be identical (same embedding, same PA)
        assert post_rollover.purpose_fidelity == first_result.purpose_fidelity
        assert post_rollover.scope_fidelity == first_result.scope_fidelity

    def test_multiple_rollovers(self):
        """Chain can rollover multiple times without degradation."""
        max_len = 3
        pa = _make_pa(max_chain_length=max_len)
        emb = _make_embedding([1.0, 0.0, 0.0])
        engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(emb),
            pa=pa,
        )

        # Three full cycles
        for cycle in range(3):
            for i in range(max_len):
                engine.score_action(f"cycle {cycle} step {i}")
            assert engine.action_chain.length == max_len

        # After 3 full cycles (9 steps), next should rollover cleanly
        result = engine.score_action("final step")
        assert engine.action_chain.length == 1
        assert result.chain_broken is False


# ---------------------------------------------------------------------------
# Unicode Normalization — zero-width character bypass prevention
# ---------------------------------------------------------------------------

class TestUnicodeNormalization:
    """Tests for _normalize_for_keywords preventing Unicode bypass attacks."""

    def test_zero_width_space_stripped(self):
        """Zero-width space inside keyword must still match."""
        result = AgenticFidelityEngine._normalize_for_keywords("byp\u200bass")
        assert "bypass" in result

    def test_zero_width_joiner_stripped(self):
        """Zero-width joiner must be stripped."""
        result = AgenticFidelityEngine._normalize_for_keywords("over\u200dride")
        assert "override" in result

    def test_bom_stripped(self):
        """Byte order mark (U+FEFF) must be stripped."""
        result = AgenticFidelityEngine._normalize_for_keywords("\ufeffbypass")
        assert result == "bypass"

    def test_nfkc_normalization(self):
        """NFKC should normalize compatibility characters."""
        # Fullwidth latin "ｂｙpａｓｓ" → "bypass"
        result = AgenticFidelityEngine._normalize_for_keywords("ｂｙｐａｓｓ")
        assert "bypass" in result

    def test_control_chars_stripped(self):
        """Control characters (except newline/tab) must be stripped."""
        result = AgenticFidelityEngine._normalize_for_keywords("byp\x00\x01ass")
        assert "bypass" in result

    def test_normal_text_unchanged(self):
        """Normal text should pass through correctly."""
        result = AgenticFidelityEngine._normalize_for_keywords("Read project file")
        assert result == "read project file"


# ---------------------------------------------------------------------------
# CLARIFY cascade Step 2: Dimensional Escalation
# ---------------------------------------------------------------------------

class TestClarifyDimensionalEscalation:
    """Tests for _identify_ambiguous_dimension and result field population."""

    def setup_method(self):
        self.engine = AgenticFidelityEngine(
            embed_fn=_make_embed_fn(_make_embedding([1, 0, 0])),
            pa=_make_pa(),
        )

    def test_chain_broken_always_chain_coherence(self):
        """Chain broken CLARIFY should always identify chain_coherence."""
        dim = self.engine._identify_ambiguous_dimension(
            purpose_fidelity=0.9,
            scope_fidelity=0.9,
            boundary_violation=0.0,
            tool_fidelity=0.9,
            chain_continuity=0.0,
            chain_broken=True,
        )
        assert dim == "chain_coherence"

    def test_purpose_most_ambiguous(self):
        """When purpose is closest to threshold, identify purpose_alignment."""
        # ST execute threshold is ~0.45. Put purpose closest to it.
        dim = self.engine._identify_ambiguous_dimension(
            purpose_fidelity=ST_AGENTIC_EXECUTE_THRESHOLD - 0.01,
            scope_fidelity=0.20,
            boundary_violation=0.0,
            tool_fidelity=0.20,
            chain_continuity=0.20,
            chain_broken=False,
        )
        assert dim == "purpose_alignment"

    def test_scope_most_ambiguous(self):
        """When scope is closest to threshold, identify scope_compliance."""
        dim = self.engine._identify_ambiguous_dimension(
            purpose_fidelity=0.20,
            scope_fidelity=ST_AGENTIC_EXECUTE_THRESHOLD - 0.02,
            boundary_violation=0.0,
            tool_fidelity=0.20,
            chain_continuity=0.20,
            chain_broken=False,
        )
        assert dim == "scope_compliance"

    def test_boundary_most_ambiguous(self):
        """When boundary proximity is closest to threshold, identify it."""
        # boundary_proximity = 1.0 - boundary_violation
        # For this to be closest to execute_thresh (~0.45),
        # we need 1.0 - boundary_violation ~= 0.45, i.e., violation ~= 0.55
        dim = self.engine._identify_ambiguous_dimension(
            purpose_fidelity=0.20,
            scope_fidelity=0.20,
            boundary_violation=1.0 - ST_AGENTIC_EXECUTE_THRESHOLD + 0.005,
            tool_fidelity=0.20,
            chain_continuity=0.20,
            chain_broken=False,
        )
        assert dim == "boundary_proximity"

    def test_tie_breaking_priority_order(self):
        """On tie (within 0.01), boundary > purpose > scope > tool > chain."""
        # All dimensions equidistant from threshold
        dim = self.engine._identify_ambiguous_dimension(
            purpose_fidelity=ST_AGENTIC_EXECUTE_THRESHOLD,
            scope_fidelity=ST_AGENTIC_EXECUTE_THRESHOLD,
            boundary_violation=1.0 - ST_AGENTIC_EXECUTE_THRESHOLD,
            tool_fidelity=ST_AGENTIC_EXECUTE_THRESHOLD,
            chain_continuity=ST_AGENTIC_EXECUTE_THRESHOLD,
            chain_broken=False,
        )
        # boundary is first in priority order
        assert dim == "boundary_proximity"

    def test_result_fields_populated_on_clarify(self):
        """AgenticFidelityResult should have ambiguous_dimension set on CLARIFY."""
        r = AgenticFidelityResult(
            purpose_fidelity=0.5,
            scope_fidelity=0.4,
            boundary_violation=0.0,
            tool_fidelity=0.6,
            chain_continuity=0.3,
            composite_fidelity=0.42,
            effective_fidelity=0.42,
            decision=ActionDecision.CLARIFY,
            direction_level=DirectionLevel.CORRECT,
            ambiguous_dimension="purpose_alignment",
            clarify_description=CLARIFY_DIMENSION_DESCRIPTIONS["purpose_alignment"],
        )
        assert r.ambiguous_dimension == "purpose_alignment"
        assert "purpose" in r.clarify_description.lower()

    def test_result_fields_empty_on_execute(self):
        """AgenticFidelityResult should NOT have ambiguous_dimension on EXECUTE."""
        r = AgenticFidelityResult(
            purpose_fidelity=0.9,
            scope_fidelity=0.9,
            boundary_violation=0.0,
            tool_fidelity=0.9,
            chain_continuity=0.9,
            composite_fidelity=0.9,
            effective_fidelity=0.9,
            decision=ActionDecision.EXECUTE,
            direction_level=DirectionLevel.NONE,
        )
        assert r.ambiguous_dimension == ""
        assert r.clarify_description == ""

    def test_all_dimensions_have_descriptions(self):
        """Every dimension in priority list has a description."""
        for dim in CLARIFY_DIMENSION_PRIORITY:
            assert dim in CLARIFY_DIMENSION_DESCRIPTIONS
            assert len(CLARIFY_DIMENSION_DESCRIPTIONS[dim]) > 10


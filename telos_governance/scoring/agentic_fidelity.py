"""
Agentic Fidelity Engine
========================
Multi-dimensional fidelity scoring for agent governance.

Composes existing governance components into a unified scoring engine:
- Tier 1: FidelityGate (purpose alignment check)
- Tier 2: ToolSelectionGate (semantic tool ranking)
- SCI: ActionChain (semantic continuity across steps)
- Boundary checking (inverted — high similarity = BAD)
- Multi-dimensional composite scoring

Composite formula:
    composite = 0.35*purpose + 0.20*scope + 0.20*tool + 0.15*chain - 0.10*boundary_penalty

First Principles
-----------------
1. **Ostrom's Graduated Sanctions** (Design Principle 5, "Governing the
   Commons", 1990): The EXECUTE/CLARIFY/INERT/ESCALATE decision
   ladder implements graduated sanctions — responses proportional to the
   severity of drift. Minor misalignment gets clarification; boundary
   violations get escalation. This avoids the binary allow/deny trap that
   makes governance brittle.

2. **Guardian-Ward Model** (inverted Principal-Agent): TELOS governance
   protects the agent's mandate against user-driven drift, not the reverse.
   The agent has no misaligned incentives — the PA defines its constitutional
   authority, and the fidelity engine enforces it. See Jensen & Meckling
   (1976) for the principal-agent framing that TELOS inverts and
   operationalizes.

3. **Statistical Process Control (SPC)**: Each fidelity dimension is a
   process measurement. The composite score is the control chart signal.
   Thresholds are control limits. The "Detect and Direct" pattern maps to
   SPC's detect-out-of-control → corrective-action cycle (Shewhart, 1931;
   Deming, 1986).

4. **SAAI Framework** (Watson and Hessami, 2026, CC BY-ND 4.0): Boundary
   specifications map to SAAI Safety Foundational Requirements. The composite
   ceiling at 0.90 (weights sum to 0.90 before boundary) implements the SAAI
   principle that no system should claim perfect alignment — 10% is reserved
   for boundary penalty, ensuring governance always has room to intervene.

5. **NIST AI 600-1** (Generative AI Profile, 2024 — MAP 2.2, MEASURE 2.5):
   The 6-dimension composite scoring implements MAP 2.2 (documenting AI
   system capabilities and limitations) through measurable fidelity
   dimensions, and MEASURE 2.5 (ongoing monitoring data collection) through
   per-action scoring. Each fidelity result is a documented measurement of
   how well the agent performed against its governance specification.

6. **OWASP LLM Top 10** (2025 — LLM08, Excessive Agency): The composite
   ceiling at 0.90 ensures no agent achieves unbounded authority. The
   boundary penalty (weight -0.10) provides a permanent "governor" on agent
   autonomy regardless of purpose/scope alignment — even a perfectly
   purpose-aligned request that triggers a boundary is penalized. This
   directly mitigates LLM08 by architectural constraint, not policy.

7. **IEEE P7003** (Algorithmic Bias Considerations, 2022): The multi-
   dimensional scoring prevents single-dimension bias — an agent cannot
   score high purely on purpose alignment while violating scope or boundary
   constraints. The composite formula enforces balanced governance across
   all dimensions, consistent with IEEE P7003's requirement for multi-
   factor fairness assessment in autonomous decision-making systems.

Uses "Detect and Direct" pattern:
- DETECT drift via multi-dimensional fidelity measurement
- DIRECT graduated response based on dimension that triggered
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, NamedTuple, Optional
import numpy as np

from telos_governance.types import ActionDecision, DirectionLevel
from telos_governance.agentic_pa import AgenticPA, BoundarySpec
from telos_governance.tool_selection_gate import ToolDefinition, ToolSelectionGate
from telos_governance.action_chain import ActionChain, SCI_DECAY_FACTOR
from telos_governance.threshold_config import ThresholdConfig

# Import thresholds from single source of truth
from telos_core.constants import (
    SIMILARITY_BASELINE,
    AGENTIC_EXECUTE_THRESHOLD,
    AGENTIC_CLARIFY_THRESHOLD,
    ST_AGENTIC_EXECUTE_THRESHOLD,
    ST_AGENTIC_CLARIFY_THRESHOLD,
    FIDELITY_GREEN,
    FIDELITY_YELLOW,
    FIDELITY_ORANGE,
    BOUNDARY_MARGIN_THRESHOLD,
)

# Import shared normalization
try:
    from telos_core.fidelity_engine import normalize_mistral_fidelity, normalize_fidelity
    _SHARED_NORMALIZE = True
except ImportError:
    _SHARED_NORMALIZE = False

logger = logging.getLogger(__name__)

# Composite weights — positive weights sum to 0.90, not 1.0. This is intentional:
# the 0.10 boundary penalty means the theoretical maximum composite is 0.90 when
# no boundary is violated. This implements the SAAI principle that governance always
# retains intervention capacity — no action achieves "perfect" fidelity.
# See: SAAI Framework §G1.9 (Watson and Hessami, 2026)
WEIGHT_PURPOSE = 0.35   # Highest weight: purpose is the primacy attractor's core
WEIGHT_SCOPE = 0.20     # Domain constraint
WEIGHT_TOOL = 0.20      # Tool-action alignment (Tier 2 semantic matching)
WEIGHT_CHAIN = 0.15     # Temporal coherence across multi-step sequences (SCI)
WEIGHT_BOUNDARY_PENALTY = 0.10  # Anti-fidelity: high boundary similarity penalizes

# Boundary violation threshold — similarity above this triggers violation.
# Inverted scoring: cos(action, boundary) >= 0.70 means the action is semantically
# close to something the agent must NOT do. This catches intent regardless of
# phrasing — "DELETE FROM users" and "remove all user records" trigger the same
# boundary because the check operates in embedding space, not keyword space.
BOUNDARY_VIOLATION_THRESHOLD = 0.70

# Keyword pre-filter (Layer 0) — global deontic violation indicators.
# Universal deontic operators that indicate intent to circumvent governance
# controls regardless of domain. Domain-specific terms are loaded from
# per-config YAML (violation_keywords field) and merged at engine init.
# Validated on 280-scenario healthcare benchmark: AUC 0.724, FPR 4.3%.
# See: research/cross_encoder_nli_mve_phase1.md (Phase 1 experimental record).
GLOBAL_DEONTIC_KEYWORDS = [
    "skip", "ignore", "override", "bypass", "suppress",
    "dismiss", "disregard", "directly", "automatically",
    "without review", "without approval", "even though",
    "go ahead", "just do", "don't bother", "no need to",
    "turn off",
]

# Keyword boost applied to embedding-based violation score when keywords match.
# Only applied when embedding score already shows some boundary relevance
# (>= KEYWORD_EMBEDDING_FLOOR), preventing false triggers on keyword-only matches
# with zero semantic relation to any boundary.
KEYWORD_BOOST = 0.15
KEYWORD_EMBEDDING_FLOOR = 0.40

# CLARIFY cascade Step 2: Dimensional escalation labels.
# When a CLARIFY verdict fires, the ambiguous dimension is identified and
# exposed categorically (no scores). Priority order for tie-breaking:
# boundary > purpose > scope > tool > chain.
CLARIFY_DIMENSION_PRIORITY = [
    "boundary_proximity",
    "purpose_alignment",
    "scope_compliance",
    "tool_authorization",
    "chain_coherence",
]
CLARIFY_DIMENSION_DESCRIPTIONS = {
    "purpose_alignment": "The action's alignment with the agent's stated purpose was unclear",
    "scope_compliance": "The action may fall outside the agent's authorized scope",
    "boundary_proximity": "The action is close to a behavioral boundary",
    "tool_authorization": "The tool usage pattern didn't match expected behavior",
    "chain_coherence": "The action doesn't follow coherently from previous actions",
}


class BoundaryCheckResult(NamedTuple):
    """Structured result from boundary checking.

    Replaces the brittle 5-tuple return from _check_boundaries().
    Named fields prevent positional unpacking bugs.
    """
    violation_score: float          # Max normalized violation similarity (0-1)
    triggered: bool                 # Whether a boundary was triggered
    detail: str                     # Human-readable explanation
    safe_similarity: Optional[float]  # Best safe centroid similarity (if available)
    contrastive_margin: Optional[float]  # margin = violation - safe (if available)
    contrastive_suppressed: bool    # True if violation was above threshold but suppressed
    keyword_triggered: bool = False  # True if violation keywords detected in action text
    keyword_matches: List[str] = []  # Which keywords matched (for audit trail)
    setfit_triggered: bool = False   # True if SetFit L1.5 classified as violation
    setfit_score: Optional[float] = None  # SetFit violation probability (if available)


@dataclass
class AgenticFidelityResult:
    """
    Complete multi-dimensional fidelity result for an agent action.

    Provides per-dimension scores, composite fidelity, and the
    governance decision with full explainability.
    """
    # Per-dimension scores (0.0 - 1.0)
    purpose_fidelity: float
    scope_fidelity: float
    boundary_violation: float  # 0.0 = no violation, 1.0 = max violation
    tool_fidelity: float
    chain_continuity: float

    # Composite scores
    composite_fidelity: float
    effective_fidelity: float  # After chain inheritance adjustment

    # Governance decision
    decision: ActionDecision
    direction_level: DirectionLevel

    # Per-dimension explanations for transparency
    dimension_explanations: Dict[str, str] = field(default_factory=dict)

    # Flags for specific governance triggers
    boundary_triggered: bool = False
    tool_blocked: bool = False
    chain_broken: bool = False
    human_required: bool = False

    # Tool selection results
    selected_tool: Optional[str] = None
    tool_rankings: List[Dict] = field(default_factory=list)

    # Contrastive boundary detection data (for audit trail)
    legitimate_similarity: Optional[float] = None   # Safe centroid similarity
    violation_similarity: Optional[float] = None     # Boundary violation similarity
    similarity_gap: Optional[float] = None           # margin = violation - legitimate
    contrastive_suppressed: bool = False             # True if a violation was suppressed by contrastive detection

    # Keyword pre-filter data (Layer 0, for audit trail)
    keyword_triggered: bool = False                  # True if violation keywords detected
    keyword_matches: List[str] = field(default_factory=list)  # Which keywords matched

    # SetFit L1.5 classification data (for audit trail)
    setfit_triggered: bool = False                   # True if SetFit classified as violation
    setfit_score: Optional[float] = None             # SetFit violation probability

    # Confirmer safety gate telemetry (MPNet secondary boundary check)
    confirmer_activated: bool = False                 # True if confirmer was consulted
    confirmer_score: Optional[float] = None           # MPNet boundary similarity score
    confirmer_would_override: bool = False            # True if MPNet detected boundary MiniLM missed
    confirmer_override_applied: bool = False          # True if override was applied (enforce mode only)

    # CLARIFY cascade Step 2: Dimensional escalation (categorical only, no scores)
    ambiguous_dimension: str = ""                     # Which dimension caused the CLARIFY verdict
    clarify_description: str = ""                     # Human-readable explanation of the ambiguous dimension


class AgenticFidelityEngine:
    """
    Multi-dimensional fidelity engine for agent governance.

    Composes FidelityGate (Tier 1), ToolSelectionGate (Tier 2),
    and ActionChain (SCI) into a unified scoring engine with
    boundary checking and composite fidelity.
    """

    def __init__(
        self,
        embed_fn: Callable[[str], np.ndarray],
        pa: AgenticPA,
        violation_keywords: Optional[List[str]] = None,
        setfit_classifier=None,
        threshold_config: Optional[ThresholdConfig] = None,
        confirmer_mode: str = "off",
    ):
        """
        Initialize the agentic fidelity engine.

        Args:
            embed_fn: Function to embed text -> np.ndarray
            pa: Multi-dimensional Primacy Attractor
            violation_keywords: Optional per-config domain-specific violation
                keywords to merge with GLOBAL_DEONTIC_KEYWORDS. Loaded from
                the violation_keywords field in YAML agent configs.
            setfit_classifier: Optional SetFitBoundaryClassifier instance for
                L1.5 boundary classification. When provided, requests in the
                ambiguous cosine zone are classified by SetFit. SetFit can
                escalate but never downgrade (asymmetric override policy).
                See: research/setfit_mve_phase2_closure.md
            threshold_config: Optional ThresholdConfig for optimizer trials.
                When provided, overrides module-level constants for this
                engine instance. When None, uses production defaults from
                constants.py. See: analysis/governance_optimizer.py
            confirmer_mode: Deprecated — safety gate disconnected from scoring
                path (experiment conclusive). The _confirm_with_secondary()
                method is retained as a research utility but is no longer
                called in the scoring cascade. This param is accepted but
                ignored for backward compatibility.
        """
        self.embed_fn = embed_fn
        self.pa = pa
        self._setfit_classifier = setfit_classifier
        self._tc = threshold_config or ThresholdConfig()

        # Confirmer safety gate state (retained for research utility —
        # _confirm_with_secondary() can be called directly but is no
        # longer wired into score_action())
        self._confirmer_mode = confirmer_mode
        self._confirmer_embed_fn = None
        self._confirmer_initialized = False

        # Merge global deontic keywords with per-config domain keywords.
        # Deduplication preserves order (global first, then config-specific).
        seen = set()
        merged = []
        for kw in GLOBAL_DEONTIC_KEYWORDS + (violation_keywords or []):
            if kw not in seen:
                seen.add(kw)
                merged.append(kw)
        self._violation_keywords = merged

        # Compose existing governance components
        self.tool_gate = ToolSelectionGate(
            embed_fn=embed_fn,
            baseline_threshold=SIMILARITY_BASELINE,
        )
        self.action_chain = ActionChain()

        # Pre-register tools if manifest exists
        if pa.tool_manifest:
            tool_defs = [
                ToolDefinition(name=t.tool_name, description=t.description)
                for t in pa.tool_manifest.values()
            ]
            self.tool_gate.register_tools(tool_defs)

    def score_action(
        self,
        action_text: str,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict] = None,
    ) -> AgenticFidelityResult:
        """
        Score an agent action across all governance dimensions.

        Args:
            action_text: Text description of the action being taken
            tool_name: Optional specific tool being called
            tool_args: Optional tool arguments (for context)

        Returns:
            AgenticFidelityResult with per-dimension scores and decision
        """
        action_embedding = self.embed_fn(action_text)
        explanations = {}

        # --- Dimension 1: Purpose Fidelity (Gate 1 when tool_centroids + explicit tool name) ---
        tool_centroids = getattr(self.pa, 'tool_centroids', None)
        telos_tool_name_for_gate1 = (
            tool_args.get('telos_tool_name') if tool_args else None
        )
        if tool_centroids and telos_tool_name_for_gate1:
            # Gate 1: score against per-tool centroid (daemon path
            # provides telos_tool_name via action_classifier → tool_args)
            purpose_fidelity, purpose_sub_qualified = self._score_tool_selection(
                action_embedding, telos_tool_name_for_gate1
            )
        else:
            # Legacy path: score against abstract purpose centroid
            purpose_fidelity, purpose_sub_qualified = self._score_purpose(action_embedding)
        explanations["purpose"] = (
            f"Purpose alignment: {purpose_fidelity:.2f} "
            f"({'aligned' if purpose_fidelity >= AGENTIC_EXECUTE_THRESHOLD else 'drifting'})"
        )

        # --- Dimension 2: Scope Fidelity ---
        scope_fidelity = self._score_scope(action_embedding)
        explanations["scope"] = (
            f"Scope alignment: {scope_fidelity:.2f} "
            f"({'in-scope' if scope_fidelity >= AGENTIC_CLARIFY_THRESHOLD else 'out-of-scope'})"
        )

        # --- Dimension 3: Boundary Check (INVERTED) ---
        boundary_result = self._check_boundaries(action_embedding, action_text)
        boundary_violation = boundary_result.violation_score
        boundary_triggered = boundary_result.triggered
        safe_sim = boundary_result.safe_similarity
        contrastive_margin = boundary_result.contrastive_margin
        explanations["boundary"] = boundary_result.detail

        # --- Dimension 4: Tool Fidelity ---
        tool_fidelity, selected_tool, tool_rankings, tool_blocked = self._score_tool(
            action_text, tool_name
        )
        explanations["tool"] = (
            f"Tool fidelity: {tool_fidelity:.2f}"
            + (f" (selected: {selected_tool})" if selected_tool else " (no tool)")
        )

        # --- Dimension 5: Chain Continuity (SCI) ---
        # Capture previous step BEFORE _score_chain appends the new step
        previous_step = self.action_chain.current_step

        chain_continuity, chain_broken = self._score_chain(
            action_text, action_embedding, purpose_fidelity
        )

        # Fix: When outer code determines chain_broken, cap the chain step's
        # stored effective_fidelity to direct_fidelity only. Otherwise the
        # chain's max(direct, inherited) creates a ghost high-water mark that
        # bleeds through when the chain reconnects on a later step.
        # Dual-inheritance chain inflation fix.
        if chain_broken:
            current_chain_step = self.action_chain.current_step
            if current_chain_step is not None:
                current_chain_step.effective_fidelity = current_chain_step.direct_fidelity

        explanations["chain"] = (
            f"Chain continuity: {chain_continuity:.2f} "
            f"(step {self.action_chain.length})"
            + (" BROKEN" if chain_broken else "")
        )

        # --- SetFit Legitimacy Signal (Intervention 3, D13) ---
        # Use SetFit as a parallel legitimacy signal for composite modulation.
        # Gated on classifier.composite_boost — only domains that opt in
        # (via manifest or config) get the modulation. Healthcare keeps
        # strict clinical boundaries; governed agents benefit from relaxed penalty
        # for verified legitimate requests.
        setfit_legitimacy = boundary_result.setfit_score
        if setfit_legitimacy is None and self._setfit_classifier and action_text:
            try:
                setfit_legitimacy = self._setfit_classifier.predict(action_text)
            except Exception as e:
                logger.warning(f"SetFit legitimacy inference failed: {e}")
                setfit_legitimacy = None

        _setfit_boost_active = (
            self._setfit_classifier is not None
            and getattr(self._setfit_classifier, 'composite_boost', False)
        )

        # --- Composite Fidelity ---
        # Conditional chain weight redistribution: when the request qualified
        # against a purpose sub-centroid AND this is the first step (no prior
        # chain context, so chain_continuity = 0.0), redistribute chain weight
        # to purpose. This is non-uniform — only Cat C requests that match
        # known example clusters get the redistribution. Cat A/D/B requests
        # that don't match sub-centroids keep the original weights.
        w_purpose = self._tc.weight_purpose
        w_chain = self._tc.weight_chain
        if purpose_sub_qualified and previous_step is None and chain_continuity == 0.0:
            w_purpose = self._tc.weight_purpose + self._tc.weight_chain
            w_chain = 0.0

        # SetFit legitimacy modulation: when SetFit classifies the request
        # as non-violation (P(violation) < 0.40), zero out boundary penalty
        # and apply legitimacy premium. The 0.40 threshold sits in the gap
        # between legitimate (~0.316) and violation (~0.676) SetFit scores.
        # Only active when composite_boost is enabled for this domain.
        w_boundary = self._tc.weight_boundary_penalty
        if (
            _setfit_boost_active
            and setfit_legitimacy is not None
            and setfit_legitimacy < 0.40
        ):
            w_boundary = 0.0

        composite = (
            w_purpose * purpose_fidelity
            + self._tc.weight_scope * scope_fidelity
            + self._tc.weight_tool * tool_fidelity
            + w_chain * chain_continuity
            - w_boundary * boundary_violation
        )

        # SetFit legitimacy premium: when SetFit confirms not-violation
        # (P < 0.40), apply premium to compensate for cosine false-proximity
        # to boundaries. The 0.40 threshold exploits the bimodal distribution
        # gap between legitimate (~0.316) and violation (~0.676) SetFit scores.
        # Only active when composite_boost is enabled for this domain.
        if (
            _setfit_boost_active
            and setfit_legitimacy is not None
            and setfit_legitimacy < 0.40
        ):
            composite += 0.15

        composite = float(max(0.0, min(1.0, composite)))

        # Effective fidelity considers chain inheritance from the PREVIOUS step.
        # - First action (no previous step): effective = composite
        # - Chain continuous (SCI >= threshold): effective = max(composite, previous_effective * decay)
        # - Chain broken: effective = composite
        if previous_step and not chain_broken:
            inherited = previous_step.effective_fidelity * SCI_DECAY_FACTOR
            effective = max(composite, inherited)
        else:
            effective = composite

        # Boundary violations must not inherit inflated fidelity from the
        # previous clean chain step. Without this, a violation mid-chain
        # records the inherited score (e.g., 0.72) instead of its true
        # composite (~0.45), masking the degradation from the drift tracker.
        # The ESCALATE decision fires correctly via the boundary override
        # above — this ensures the drift tracker also sees the real score.
        if boundary_triggered:
            effective = composite

        # --- Governance Decision ---
        decision, human_required = self._make_decision(
            effective_fidelity=effective,
            boundary_triggered=boundary_triggered,
            tool_blocked=tool_blocked,
            chain_broken=chain_broken,
            tool_name=tool_name,
        )

        # Decision floor: contrastive suppression must never produce EXECUTE.
        # When a boundary violation is suppressed (safe centroid closer), the
        # boundary_triggered flag is False, so _make_decision uses fidelity
        # thresholds alone. If tool fidelity is high, this can cascade to
        # EXECUTE on a genuine violation (e.g., ESCL-017). The decision floor
        # caps the response at CLARIFY — the request is plausible enough to
        # not escalate, but the violation signal is too strong to execute.
        # See: Research team unanimous P0, 2026-02-13.
        if (
            boundary_result.contrastive_suppressed
            and boundary_violation >= self._tc.boundary_violation
            and decision == ActionDecision.EXECUTE
        ):
            decision = ActionDecision.CLARIFY
            logger.info(
                f"Decision floor applied: EXECUTE → CLARIFY "
                f"(contrastive suppressed, violation={boundary_violation:.2f})"
            )

        # --- CLARIFY cascade Step 2: Dimensional escalation ---
        ambiguous_dim = ""
        clarify_desc = ""
        if decision == ActionDecision.CLARIFY:
            ambiguous_dim = self._identify_ambiguous_dimension(
                purpose_fidelity=purpose_fidelity,
                scope_fidelity=scope_fidelity,
                boundary_violation=boundary_violation,
                tool_fidelity=tool_fidelity,
                chain_continuity=chain_continuity,
                chain_broken=chain_broken,
            )
            clarify_desc = CLARIFY_DIMENSION_DESCRIPTIONS.get(ambiguous_dim, "")

        # --- Direction Level ---
        direction_level = self._determine_direction_level(effective, boundary_triggered)

        return AgenticFidelityResult(
            purpose_fidelity=purpose_fidelity,
            scope_fidelity=scope_fidelity,
            boundary_violation=boundary_violation,
            tool_fidelity=tool_fidelity,
            chain_continuity=chain_continuity,
            composite_fidelity=composite,
            effective_fidelity=effective,
            decision=decision,
            direction_level=direction_level,
            dimension_explanations=explanations,
            boundary_triggered=boundary_triggered,
            tool_blocked=tool_blocked,
            chain_broken=chain_broken,
            human_required=human_required,
            selected_tool=selected_tool,
            tool_rankings=tool_rankings,
            legitimate_similarity=safe_sim,
            violation_similarity=boundary_violation if safe_sim is not None else None,
            similarity_gap=contrastive_margin,
            contrastive_suppressed=boundary_result.contrastive_suppressed,
            keyword_triggered=boundary_result.keyword_triggered,
            keyword_matches=boundary_result.keyword_matches,
            setfit_triggered=boundary_result.setfit_triggered,
            setfit_score=boundary_result.setfit_score,
            ambiguous_dimension=ambiguous_dim,
            clarify_description=clarify_desc,
            confirmer_activated=False,
            confirmer_score=None,
            confirmer_would_override=False,
            confirmer_override_applied=False,
        )

    def reset_chain(self) -> None:
        """Clear the action chain (start new task sequence)."""
        self.action_chain.reset()

    # -------------------------------------------------------------------------
    # Confirmer safety gate (MPNet secondary boundary check)
    # -------------------------------------------------------------------------

    def _init_confirmer(self) -> None:
        """Lazy-initialize the MPNet confirmer provider and boundary centroids.

        Called on first confirmer activation. Loads MPNet ONNX (768-dim) and
        builds boundary centroids in MPNet's embedding space. Subsequent
        calls are no-ops due to _confirmer_initialized flag.

        If MPNet loading fails, the confirmer is silently disabled.
        """
        if self._confirmer_initialized:
            return
        self._confirmer_initialized = True

        try:
            from telos_core.embedding_provider import get_cached_onnx_mpnet_provider
            provider = get_cached_onnx_mpnet_provider()
            self._confirmer_embed_fn = provider.encode
            self.pa.build_confirmer_centroids(self._confirmer_embed_fn)
            logger.info(
                f"Confirmer safety gate initialized: MPNet {provider.dimension}d, "
                f"{len(self.pa.boundaries)} boundary centroids built"
            )
        except Exception as e:
            logger.warning(f"Confirmer initialization failed (disabled): {e}")
            self._confirmer_embed_fn = None

    def _confirm_with_secondary(
        self,
        action_text: str,
        composite_fidelity: float,
    ) -> Dict:
        """MPNet boundary-only safety gate for edge-case EXECUTE decisions.

        Re-embeds the action text with MPNet (768-dim) and checks against
        MPNet boundary centroids. If MPNet detects a boundary violation
        that MiniLM missed, the confirmer signals an override.

        Asymmetric: can only escalate (upgrade EXECUTE → ESCALATE), never
        de-escalate. This is a core safety requirement — the confirmer
        adds a one-way safety ratchet.

        The confirmer uses raw cosine similarity (not normalized fidelity)
        because MPNet's cosine distribution differs from MiniLM's. The
        mpnet_boundary_threshold is calibrated for MPNet's distribution.

        Args:
            action_text: The action being scored (re-embedded with MPNet)
            composite_fidelity: MiniLM composite score (for telemetry)

        Returns:
            Dict with confirmer_activated, confirmer_score,
            confirmer_would_override, confirmer_override_applied.
        """
        result = {
            "confirmer_activated": False,
            "confirmer_score": None,
            "confirmer_would_override": False,
            "confirmer_override_applied": False,
        }

        if self._confirmer_mode == "off":
            return result

        # Lazy init: load MPNet and build centroids on first call
        if not self._confirmer_initialized:
            self._init_confirmer()

        if self._confirmer_embed_fn is None or not self.pa.confirmer_boundary_embeddings:
            return result

        result["confirmer_activated"] = True

        # Re-embed with MPNet
        mpnet_embedding = self._confirmer_embed_fn(action_text)

        # Check against each MPNet boundary centroid (raw cosine, not normalized)
        max_boundary_sim = 0.0
        worst_boundary_idx = -1
        for i, boundary_emb in enumerate(self.pa.confirmer_boundary_embeddings):
            sim = self._cosine_similarity(mpnet_embedding, boundary_emb)
            if sim > max_boundary_sim:
                max_boundary_sim = sim
                worst_boundary_idx = i

        result["confirmer_score"] = max_boundary_sim

        # MPNet boundary threshold: calibrated for MPNet's cosine distribution.
        # MPNet's raw cosine for boundary violations sits lower than MiniLM's
        # normalized scores. 0.60 catches the 98% Cat A signal from the model
        # comparison experiment (research/mlx_model_comparison.md).
        mpnet_boundary_threshold = 0.60

        if max_boundary_sim >= mpnet_boundary_threshold:
            result["confirmer_would_override"] = True
            boundary_text = (
                self.pa.boundaries[worst_boundary_idx].text[:60]
                if 0 <= worst_boundary_idx < len(self.pa.boundaries) else "unknown"
            )

            if self._confirmer_mode == "enforce":
                result["confirmer_override_applied"] = True
                logger.warning(
                    f"Confirmer safety gate OVERRIDE: MPNet boundary={max_boundary_sim:.3f} "
                    f"(threshold={mpnet_boundary_threshold:.2f}) against "
                    f"'{boundary_text}', MiniLM composite={composite_fidelity:.3f}. "
                    f"EXECUTE → ESCALATE"
                )
            else:
                # Observe mode: log but don't override
                logger.info(
                    f"Confirmer safety gate OBSERVE: MPNet boundary={max_boundary_sim:.3f} "
                    f"(threshold={mpnet_boundary_threshold:.2f}) against "
                    f"'{boundary_text}', MiniLM composite={composite_fidelity:.3f}. "
                    f"Would override EXECUTE → ESCALATE (observe mode)"
                )
        else:
            logger.debug(
                f"Confirmer safety gate: MPNet boundary={max_boundary_sim:.3f} "
                f"(below threshold={mpnet_boundary_threshold:.2f}), no override"
            )

        return result

    # -------------------------------------------------------------------------
    # Private dimension scoring methods
    # -------------------------------------------------------------------------

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        result = float(np.dot(a, b) / (norm_a * norm_b))
        # NaN guard: corrupted embeddings must not bypass governance (fail-closed)
        if math.isnan(result):
            logger.warning("NaN detected in agentic cosine similarity — returning 0.0 (fail-closed)")
            return 0.0
        return result

    def _is_sentence_transformer(self) -> bool:
        """Detect if using SentenceTransformer (384/768-dim) vs Mistral (1024-dim)."""
        if self.pa.purpose_embedding is not None:
            return self.pa.purpose_embedding.shape[0] <= 800
        return True  # Default to ST if unknown

    def _normalize_fidelity(self, raw_similarity: float) -> float:
        """Normalize raw cosine similarity to fidelity score (0-1).

        NaN inputs fail-closed to 0.0.

        Automatically selects the correct normalization based on embedding
        dimensionality:
        - SentenceTransformer (384-dim): Linear mapping (slope=1.167, intercept=0.117)
        - Mistral (1024-dim): Piecewise mapping (floor=0.55, aligned=0.70)
        """
        # NaN guard: fail-closed to 0.0
        if math.isnan(raw_similarity):
            return 0.0
        if self._is_sentence_transformer():
            # Linear normalization calibrated for MiniLM (raw 0.20-0.50 range)
            if _SHARED_NORMALIZE:
                return normalize_fidelity(raw_similarity, slope=1.167, intercept=0.117)
            # Inline fallback
            display = 1.167 * raw_similarity + 0.117
            return float(max(0.0, min(1.0, display)))
        else:
            # Piecewise normalization calibrated for Mistral (raw 0.55-0.80 range)
            if _SHARED_NORMALIZE:
                return normalize_mistral_fidelity(raw_similarity)
            MISTRAL_FLOOR = 0.55
            MISTRAL_ALIGNED = 0.70
            if raw_similarity < MISTRAL_FLOOR:
                fidelity = (raw_similarity / MISTRAL_FLOOR) * 0.30
            elif raw_similarity < MISTRAL_ALIGNED:
                fidelity = 0.30 + (
                    (raw_similarity - MISTRAL_FLOOR) / (MISTRAL_ALIGNED - MISTRAL_FLOOR)
                ) * 0.40
            else:
                fidelity = 0.70 + (
                    (raw_similarity - MISTRAL_ALIGNED) / (1.0 - MISTRAL_ALIGNED)
                ) * 0.30
            return float(min(1.0, max(0.0, fidelity)))

    def _score_purpose(self, action_embedding: np.ndarray) -> tuple:
        """Dimension 1: Score action against purpose.

        Two-tier example matching (Cat C accuracy):

        Tier 1 — Sub-centroid bounded lift: when purpose examples are
        clustered (>= 6 examples), score against K=3 cluster centroids.
        Each cluster has a per-cluster threshold (25th percentile of
        member similarities). If the action qualifies against any cluster
        AND the sub-centroid scores higher than the centroid, applies a
        bounded lift (70% of gap, capped at +0.20). Gate at 0.55 covers
        the low CLARIFY band.

        Tier 2 — Lift-only max-pool (fallback): when sub-centroids are
        not available OR the action doesn't qualify against any cluster,
        falls back to the original bounded lift (40% of gap, capped at
        +0.08). Gate at 0.50 prevents disrupting calibrated verdicts.

        Returns:
            (score, sub_centroid_qualified): score is the purpose fidelity,
            sub_centroid_qualified is True if a sub-centroid was used,
            enabling conditional chain weight redistribution in composite.
        """
        if self.pa.purpose_embedding is None:
            return 1.0, False  # No purpose defined = pass through
        centroid_score = self._normalize_fidelity(
            self._cosine_similarity(action_embedding, self.pa.purpose_embedding)
        )
        sub_qualified = False
        # Tier 1: Sub-centroid bounded lift. The per-cluster threshold
        # (25th percentile of member similarities) gates spurious matches,
        # allowing a more aggressive lift than the flat max-pool.
        if self.pa.purpose_sub_centroids is not None and centroid_score < 0.55:
            action_norm = np.linalg.norm(action_embedding)
            if action_norm > 0:
                sub_sims = self.pa.purpose_sub_centroids @ action_embedding / action_norm
                if self.pa.purpose_sub_centroid_thresholds is not None:
                    qualified = sub_sims >= self.pa.purpose_sub_centroid_thresholds
                    if np.any(qualified):
                        max_sub_raw = float(np.max(sub_sims[qualified]))
                        max_sub_norm = self._normalize_fidelity(max_sub_raw)
                        if max_sub_norm > centroid_score:
                            lift = (max_sub_norm - centroid_score) * 0.7
                            centroid_score = centroid_score + min(lift, 0.20)
                            sub_qualified = True
        # Tier 2: Lift-only max-pool (fallback for PAs without sub-centroids)
        if self.pa.purpose_example_embeddings and centroid_score < 0.50:
            max_example = max(
                self._normalize_fidelity(
                    self._cosine_similarity(action_embedding, ex)
                )
                for ex in self.pa.purpose_example_embeddings
            )
            if max_example > centroid_score:
                lift = (max_example - centroid_score) * 0.4
                return centroid_score + min(lift, 0.08), sub_qualified
        return centroid_score, sub_qualified

    def _score_tool_selection(
        self, action_embedding: np.ndarray, telos_tool_name: Optional[str]
    ) -> tuple:
        """Gate 1: Score action against the tool's canonical centroid.

        Replaces _score_purpose() when per-tool centroids are available.
        Measures whether the action text matches what this specific tool IS
        (canonical definition + exemplars), not an abstract mission statement.

        Falls back to _score_purpose() for legacy PAs or unknown tools.

        Args:
            action_embedding: Embedded action text from build_action_text()
            telos_tool_name: The classified tool name (e.g., "fs_read_file")

        Returns:
            (score, sub_centroid_qualified): Same interface as _score_purpose().
        """
        tool_centroids = getattr(self.pa, 'tool_centroids', None)
        if not tool_centroids or not telos_tool_name or telos_tool_name not in tool_centroids:
            return self._score_purpose(action_embedding)

        # Score against the specific tool's centroid
        tool_centroid = tool_centroids[telos_tool_name]
        tool_score = self._normalize_fidelity(
            self._cosine_similarity(action_embedding, tool_centroid)
        )

        # Also score against the combined purpose centroid (fallback signal)
        purpose_score, purpose_sub_qualified = self._score_purpose(action_embedding)

        # Gate 1 floor: only use tool_score if it exceeds the floor threshold.
        # This prevents weak tool matches (off-topic requests that happen to
        # weakly resemble some tool centroid) from inflating the score past
        # verdict thresholds. Configurable via Phase C sweep.
        # Rule: "if tool_score >= gate1_floor: use max, else: purpose_score"
        gate1_floor = getattr(self.pa, 'gate1_floor', 0.50)
        if tool_score >= gate1_floor and tool_score > purpose_score:
            return tool_score, True
        else:
            return purpose_score, purpose_sub_qualified

    def _score_scope(self, action_embedding: np.ndarray) -> float:
        """Dimension 2: Score action against scope.

        Same two-tier bounded lift pattern as _score_purpose.
        """
        if self.pa.scope_embedding is None:
            return 1.0  # No scope defined = pass through
        centroid_score = self._normalize_fidelity(
            self._cosine_similarity(action_embedding, self.pa.scope_embedding)
        )
        # Tier 1: Sub-centroid bounded lift (same parameters as purpose)
        if self.pa.scope_sub_centroids is not None and centroid_score < 0.55:
            action_norm = np.linalg.norm(action_embedding)
            if action_norm > 0:
                sub_sims = self.pa.scope_sub_centroids @ action_embedding / action_norm
                if self.pa.scope_sub_centroid_thresholds is not None:
                    qualified = sub_sims >= self.pa.scope_sub_centroid_thresholds
                    if np.any(qualified):
                        max_sub_raw = float(np.max(sub_sims[qualified]))
                        max_sub_norm = self._normalize_fidelity(max_sub_raw)
                        if max_sub_norm > centroid_score:
                            lift = (max_sub_norm - centroid_score) * 0.7
                            centroid_score = centroid_score + min(lift, 0.20)
        # Tier 2: Lift-only max-pool fallback
        if self.pa.scope_example_embeddings and centroid_score < 0.50:
            max_example = max(
                self._normalize_fidelity(
                    self._cosine_similarity(action_embedding, ex)
                )
                for ex in self.pa.scope_example_embeddings
            )
            if max_example > centroid_score:
                lift = (max_example - centroid_score) * 0.4
                return centroid_score + min(lift, 0.08)
        return centroid_score

    @staticmethod
    def _normalize_for_keywords(text: str) -> str:
        """NFKC normalize and strip zero-width/control characters.

        Prevents Unicode bypass attacks where zero-width characters
        (U+200B, U+200C, U+200D, U+2060, U+FEFF) or homoglyphs break
        keyword matching while preserving semantic meaning for embeddings.
        """
        import unicodedata
        import re
        text = unicodedata.normalize("NFKC", text)
        # Strip zero-width and invisible formatting characters
        text = re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", "", text)
        # Strip control characters (except \n, \t, \r)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
        return text.lower()

    def _keyword_check(self, action_text: str) -> List[str]:
        """Layer 0: Check action text for violation-indicator keywords.

        Returns list of matched keywords (empty if none found).
        Uses merged global deontic + per-config domain keywords.
        Input is NFKC-normalized and stripped of zero-width characters.
        """
        lower = self._normalize_for_keywords(action_text)
        return [kw for kw in self._violation_keywords if kw in lower]

    def _check_boundaries(
        self, action_embedding: np.ndarray, action_text: str = ""
    ) -> BoundaryCheckResult:
        """
        Dimension 3: Check action against boundaries (INVERTED scoring).

        High similarity to a boundary = BAD (violation).
        Uses centroid embedding (effective_embedding) for scoring.

        Layer 0 (keyword pre-filter, 2026-02-16): Scans action text for
        deontic violation indicators (skip, override, bypass, etc.).
        When keywords match AND embedding score >= KEYWORD_EMBEDDING_FLOOR,
        adds KEYWORD_BOOST to the violation score. This catches violations
        that embeddings miss due to vocabulary overlap between violation
        and legitimate clinical language. Validated on 280-scenario
        healthcare benchmark: keyword AUC 0.724, FPR 4.3%.
        See: research/cross_encoder_nli_mve_phase1.md

        Contrastive detection (Phase 2, 2026-02-12): When a per-boundary
        safe_centroid is available, computes margin = violation - safe.
        Boundaries with margin <= 0 are suppressed (safe centroid is strictly
        closer, indicating legitimate use). Boundaries with margin in
        (0, BOUNDARY_MARGIN_THRESHOLD] are in the ambiguous zone — still
        triggered but flagged for potential graduated response. Boundaries
        with margin > threshold trigger normally.

        Each boundary is evaluated independently. Margin data in the result
        tracks the triggering boundary (if any), not just the worst-scoring
        boundary — ensuring accurate audit trail data.

        Returns:
            BoundaryCheckResult with named fields (replaces brittle 5-tuple).
        """
        if not self.pa.boundaries:
            return BoundaryCheckResult(0.0, False, "No boundaries defined", None, None, False)

        # Layer 0: Keyword pre-filter
        keyword_matches = self._keyword_check(action_text) if action_text else []

        max_violation = 0.0
        triggered = False
        contrastive_suppressed = False
        worst_boundary = None
        # Track margin data for the triggering boundary (not worst-scoring boundary)
        # to ensure audit trail accuracy.
        trigger_safe_sim = None
        trigger_margin = None
        # Track worst boundary margin for suppression reporting
        worst_safe_sim = None
        worst_margin = None

        for boundary in self.pa.boundaries:
            if boundary.effective_embedding is None:
                continue
            raw = self._cosine_similarity(action_embedding, boundary.effective_embedding)
            normalized = self._normalize_fidelity(raw)

            # Sub-centroid check: per-cluster threshold-gated matching.
            if boundary.sub_centroids is not None:
                action_norm = np.linalg.norm(action_embedding)
                if action_norm > 0:
                    sub_sims = boundary.sub_centroids @ action_embedding / action_norm
                    if boundary.sub_centroid_thresholds is not None:
                        qualified = sub_sims >= boundary.sub_centroid_thresholds
                        if np.any(qualified):
                            max_sub_raw = float(np.max(sub_sims[qualified]))
                            max_sub_norm = self._normalize_fidelity(max_sub_raw)
                            if max_sub_norm > normalized:
                                raw = max_sub_raw
                                normalized = max_sub_norm
                    else:
                        max_sub_raw = float(np.max(sub_sims))
                        max_sub_norm = self._normalize_fidelity(max_sub_raw)
                        if max_sub_norm > normalized:
                            raw = max_sub_raw
                            normalized = max_sub_norm

            # Layer 0: Keyword boost — if violation keywords detected AND
            # embedding score shows boundary relevance, boost the score.
            # This catches violations that embeddings miss due to vocabulary
            # overlap between violation and legitimate language.
            if keyword_matches and normalized >= self._tc.keyword_embedding_floor:
                boosted = min(1.0, normalized + self._tc.keyword_boost)
                if boosted > normalized:
                    logger.info(
                        f"Keyword boost: '{boundary.text[:50]}...' "
                        f"{normalized:.2f} → {boosted:.2f} "
                        f"(keywords: {keyword_matches[:3]})"
                    )
                    normalized = boosted

            # Contrastive detection: compute margin against per-boundary safe centroid.
            safe_sim = None
            margin = None
            if boundary.safe_centroid is not None:
                safe_raw = self._cosine_similarity(action_embedding, boundary.safe_centroid)
                safe_sim = self._normalize_fidelity(safe_raw)
                margin = normalized - safe_sim

            if normalized > max_violation:
                max_violation = normalized
                worst_boundary = boundary
                worst_safe_sim = safe_sim
                worst_margin = margin

            if normalized >= self._tc.boundary_violation:
                if margin is None or margin > self._tc.boundary_margin:
                    # No safe centroid or clear violation (margin above threshold) → trigger
                    triggered = True
                    trigger_safe_sim = safe_sim
                    trigger_margin = margin
                    if boundary.severity == "hard":
                        margin_info = f" margin={margin:.2f}" if margin is not None else ""
                        logger.warning(
                            f"Hard boundary triggered: '{boundary.text[:50]}...' "
                            f"similarity={normalized:.2f}{margin_info}"
                        )
                elif margin <= 0:
                    # Safe centroid strictly closer → suppress (legitimate request)
                    contrastive_suppressed = True
                    logger.info(
                        f"Contrastive suppression: '{boundary.text[:50]}...' "
                        f"violation={normalized:.2f} safe={safe_sim:.2f} "
                        f"margin={margin:.2f} (safe centroid closer)"
                    )
                else:
                    # 0 < margin <= BOUNDARY_MARGIN_THRESHOLD → ambiguous zone
                    # Trigger (conservative: catch violations) but flag for
                    # potential graduated response in future iterations.
                    triggered = True
                    trigger_safe_sim = safe_sim
                    trigger_margin = margin
                    logger.info(
                        f"Contrastive ambiguous: '{boundary.text[:50]}...' "
                        f"violation={normalized:.2f} safe={safe_sim:.2f} "
                        f"margin={margin:.2f} in ambiguous zone"
                    )

        # triggered takes precedence over contrastive_suppressed: if ANY boundary
        # has a clear violation (margin > threshold), the request is a violation
        # regardless of other boundaries being suppressed.
        if triggered:
            contrastive_suppressed = False

        # --- Layer 1.5: SetFit boundary classification ---
        # SetFit fires when cosine signals possible boundary relevance but
        # hasn't triggered a definitive violation. Asymmetric override policy:
        # SetFit can ESCALATE (upgrade no-trigger to trigger) but can NEVER
        # DOWNGRADE (suppress a cosine-triggered violation).
        # See: research/setfit_mve_phase2_closure.md (Section 9, Cascade Architecture)
        setfit_triggered = False
        setfit_score = None
        if self._setfit_classifier and not triggered:
            # Only invoke SetFit when cosine shows boundary relevance
            if max_violation >= self._tc.keyword_embedding_floor and action_text:
                try:
                    setfit_score = self._setfit_classifier.predict(action_text)
                    if setfit_score >= self._setfit_classifier.threshold:
                        setfit_triggered = True
                        triggered = True
                        contrastive_suppressed = False
                        logger.info(
                            f"SetFit L1.5 escalation: score={setfit_score:.3f} "
                            f"(threshold={self._setfit_classifier.threshold:.2f}), "
                            f"cosine={max_violation:.2f}"
                        )
                except Exception as e:
                    logger.warning(f"SetFit L1.5 inference failed: {e}")

        # Select margin data: use triggering boundary data if triggered,
        # otherwise use worst boundary data for suppression reporting.
        best_safe_sim = trigger_safe_sim if triggered else worst_safe_sim
        best_margin = trigger_margin if triggered else worst_margin

        kw_info = f" [keywords: {', '.join(keyword_matches[:3])}]" if keyword_matches else ""

        if triggered and worst_boundary:
            detail = (
                f"Boundary violation: {max_violation:.2f} against "
                f"'{worst_boundary.text[:60]}' ({worst_boundary.severity}){kw_info}"
            )
        elif contrastive_suppressed and worst_boundary:
            detail = (
                f"Boundary suppressed by contrastive detection: {max_violation:.2f} against "
                f"'{worst_boundary.text[:60]}' (margin={worst_margin:.2f}){kw_info}"
            )
        else:
            detail = f"No boundary violation (max similarity: {max_violation:.2f}){kw_info}"

        return BoundaryCheckResult(
            violation_score=max_violation,
            triggered=triggered,
            detail=detail,
            safe_similarity=best_safe_sim,
            contrastive_margin=best_margin,
            contrastive_suppressed=contrastive_suppressed,
            keyword_triggered=bool(keyword_matches),
            keyword_matches=keyword_matches,
            setfit_triggered=setfit_triggered,
            setfit_score=setfit_score,
        )

    def _score_tool(
        self, action_text: str, tool_name: Optional[str]
    ) -> tuple:
        """
        Dimension 4: Score tool selection fidelity.

        Returns:
            (tool_fidelity, selected_tool, tool_rankings, tool_blocked)
        """
        if not self.pa.tool_manifest:
            return 1.0, None, [], False

        # Check action tiers first (fast path)
        if tool_name:
            if tool_name in self.pa.action_tiers.always_blocked:
                return 0.0, tool_name, [], True
            if tool_name in self.pa.action_tiers.always_allowed:
                return 1.0, tool_name, [], False

        # Semantic tool selection via ToolSelectionGate
        tool_defs = [
            ToolDefinition(name=t.tool_name, description=t.description)
            for t in self.pa.tool_manifest.values()
        ]
        result = self.tool_gate.select_tool(action_text, tool_defs)

        tool_rankings = [
            {
                "rank": score.rank,
                "tool": score.tool_name,
                "fidelity": score.normalized_fidelity,
            }
            for score in result.tool_scores
        ]

        selected = result.selected_tool
        fidelity = result.selected_fidelity

        # If a specific tool was requested, use its fidelity
        if tool_name:
            for score in result.tool_scores:
                if score.tool_name == tool_name:
                    fidelity = score.normalized_fidelity
                    selected = tool_name
                    break

        # Use model-appropriate threshold for tool blocking
        if self._is_sentence_transformer():
            tool_block_thresh = self._tc.st_clarify
        else:
            tool_block_thresh = AGENTIC_CLARIFY_THRESHOLD
        tool_blocked = fidelity < tool_block_thresh
        return fidelity, selected, tool_rankings, tool_blocked

    def _score_chain(
        self,
        action_text: str,
        action_embedding: np.ndarray,
        direct_fidelity: float,
    ) -> tuple:
        """
        Dimension 5: Score chain continuity via SCI.

        Returns:
            (continuity_score, chain_broken)
        """
        # Check chain length limit — rollover instead of terminal death
        if self.action_chain.length >= self.pa.max_chain_length:
            old_length = self.action_chain.length
            logger.info(
                f"Action chain rollover: {old_length} steps reached max "
                f"({self.pa.max_chain_length}), resetting chain"
            )
            self.action_chain.reset()

        # Add step to chain (calculates SCI internally)
        step = self.action_chain.add_step(
            action_text=action_text,
            embedding=action_embedding,
            direct_fidelity=direct_fidelity,
        )

        chain_broken = not self.action_chain.is_continuous()
        return step.continuity_score, chain_broken

    def _make_decision(
        self,
        effective_fidelity: float,
        boundary_triggered: bool,
        tool_blocked: bool,
        chain_broken: bool,
        tool_name: Optional[str],
    ) -> tuple:
        """
        Make governance decision from multi-dimensional scores.

        Implements Ostrom's graduated sanctions (DP5): responses are
        proportional to the severity of the governance signal. Hard
        overrides take precedence (boundary > tool > chain), then
        threshold-based graduated response on effective fidelity.

        The escalation ladder — EXECUTE > CLARIFY > INERT >
        ESCALATE — maps directly to Ostrom's principle that sanctions
        should start mild and increase only as violations persist or
        severity warrants. This avoids the "nuclear option" problem
        where binary allow/deny creates adversarial dynamics.

        Hard overrides:
        - Boundary violation (hard) -> ESCALATE (human review required)
        - Tool blocked -> INERT (acknowledge limitation)
        - Chain broken -> CLARIFY (verify intent before continuing)

        Otherwise, threshold-based on effective fidelity.

        Returns:
            (decision, human_required)
        """
        human_required = False

        # Hard overrides
        if boundary_triggered:
            human_required = True
            return ActionDecision.ESCALATE, human_required

        if tool_blocked:
            return ActionDecision.INERT, human_required

        # NOTE: chain_broken no longer a hard override here.
        # Moved to post-threshold check below — chain break only
        # DOWNGRADES (EXECUTE -> CLARIFY), never UPGRADES (INERT -> CLARIFY).
        # A prompt injection at fidelity 0.15 must stay INERT regardless
        # of chain state.

        # Check if tool requires confirmation
        if tool_name and tool_name in self.pa.tool_manifest:
            tool_auth = self.pa.tool_manifest[tool_name]
            if tool_auth.requires_confirmation:
                human_required = True
            # Check risk-based escalation
            risk_levels = ["low", "medium", "high", "critical"]
            require_idx = risk_levels.index(self.pa.require_human_above_risk)
            tool_idx = risk_levels.index(tool_auth.risk_level)
            if tool_idx >= require_idx:
                human_required = True

        # Select model-appropriate thresholds
        if self._is_sentence_transformer():
            execute_thresh = self._tc.st_execute
            clarify_thresh = self._tc.st_clarify
        else:
            execute_thresh = AGENTIC_EXECUTE_THRESHOLD
            clarify_thresh = AGENTIC_CLARIFY_THRESHOLD

        # Threshold-based decision
        if effective_fidelity >= execute_thresh:
            # Chain broken downgrades EXECUTE to CLARIFY — a legitimate
            # agent that breaks its behavioral chain should explain the
            # jump before proceeding. This is Ostrom's graduated sanctions:
            # the mildest response that addresses the signal.
            decision = ActionDecision.CLARIFY if chain_broken else ActionDecision.EXECUTE
        elif effective_fidelity >= clarify_thresh:
            decision = ActionDecision.CLARIFY
        elif effective_fidelity < self.pa.escalation_threshold:
            decision = ActionDecision.ESCALATE
            human_required = True
        else:
            decision = ActionDecision.INERT

        return decision, human_required

    def _identify_ambiguous_dimension(
        self,
        purpose_fidelity: float,
        scope_fidelity: float,
        boundary_violation: float,
        tool_fidelity: float,
        chain_continuity: float,
        chain_broken: bool,
    ) -> str:
        """Identify which dimension caused a CLARIFY verdict.

        Returns a categorical label from CLARIFY_DIMENSION_PRIORITY.
        No numerical scores are exposed — only the dimension name.

        When a CLARIFY fires from a chain break (high fidelity but broken
        chain), the ambiguous dimension is always chain_coherence.

        For threshold-based CLARIFYs, finds the dimension whose score is
        closest to the EXECUTE threshold (most ambiguous).

        Tie-breaking (within 0.01): boundary > purpose > scope > tool > chain.
        """
        if chain_broken:
            return "chain_coherence"

        # Map dimensions to their scores. For boundary, invert: higher
        # boundary_violation = lower effective boundary "fidelity".
        # We want the dimension whose fidelity is closest to the threshold.
        if self._is_sentence_transformer():
            execute_thresh = self._tc.st_execute
        else:
            execute_thresh = AGENTIC_EXECUTE_THRESHOLD

        dimension_scores = {
            "boundary_proximity": 1.0 - boundary_violation,
            "purpose_alignment": purpose_fidelity,
            "scope_compliance": scope_fidelity,
            "tool_authorization": tool_fidelity,
            "chain_coherence": chain_continuity,
        }

        # Find dimension with smallest margin to execute threshold
        min_margin = float("inf")
        ambiguous = "purpose_alignment"  # fallback
        for name in CLARIFY_DIMENSION_PRIORITY:
            margin = abs(dimension_scores[name] - execute_thresh)
            if margin < min_margin - 0.01:
                # Clear winner (more than 0.01 gap)
                min_margin = margin
                ambiguous = name
            elif margin < min_margin + 0.01:
                # Tie (within 0.01) — priority order wins (earlier in list)
                pass  # keep current winner (earlier priority)
        return ambiguous

    def _determine_direction_level(
        self, fidelity: float, boundary_triggered: bool
    ) -> DirectionLevel:
        """
        Determine direction level from fidelity and boundary state.

        Two-layer detection system (Brunner, 2025 — Zenodo 10.5281/zenodo.18370880):
        - Layer 1: Boundary violation → HARD_BLOCK (absolute constraint)
        - Layer 2: Zone-based graduated direction (SPC control chart zones)

        The zones map to SPC terminology: GREEN = in-control, YELLOW = warning,
        ORANGE = out-of-control (corrective action), RED = process stop (direct
        intervention). This is the "Detect and Direct" pattern — SPC detects
        the out-of-control condition, governance directs the corrective response.
        """
        if boundary_triggered:
            return DirectionLevel.HARD_BLOCK

        if fidelity >= self._tc.fidelity_green:
            return DirectionLevel.NONE
        elif fidelity >= self._tc.fidelity_yellow:
            return DirectionLevel.MONITOR
        elif fidelity >= self._tc.fidelity_orange:
            return DirectionLevel.CORRECT
        else:
            return DirectionLevel.DIRECT

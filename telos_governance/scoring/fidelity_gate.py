"""
Fidelity Gate (Tier 1)
=======================

The core governance component — decides whether to EXECUTE, CLARIFY,
INERT, or ESCALATE based on fidelity measurement against the
Primacy Attractor.

This is the "Constitutional Filter" applied to agentic AI.

First Principles
-----------------
1. **Two-Layer Detection** (Brunner, 2025 — Zenodo 10.5281/zenodo.18370880):
   Layer 1 (baseline normalization) catches extreme off-topic content
   using raw cosine similarity against a hard floor. Layer 2 (basin
   membership) catches purpose drift using normalized fidelity against
   graduated thresholds. Both layers must pass for an action to proceed.
   This dual-layer approach prevents both obvious misuse (Layer 1) and
   subtle drift (Layer 2).

2. **Ostrom's Graduated Sanctions** (DP5, "Governing the Commons", 1990):
   The 4-tier decision ladder (EXECUTE → CLARIFY → INERT →
   ESCALATE) implements proportional response. Agentic thresholds are
   tighter than conversational (EXECUTE at 0.85 vs GREEN at 0.70)
   because actions are harder to reverse than words — a wrong SQL
   query executes immediately, while a wrong conversational response
   can be corrected in the next turn.

3. **SPC Control Zones** (Shewhart, 1931): Fidelity zones map to
   process control terminology — GREEN (in-control, no intervention),
   YELLOW (warning zone, monitor), ORANGE (action zone, correct),
   RED (stop zone, direct intervention). The direction levels
   (NONE/MONITOR/CORRECT/DIRECT/HARD_BLOCK) are the corrective
   actions triggered by each zone.

4. **IEEE 7001-2021** (Transparency of Autonomous Systems): Direction
   levels with mathematical justification implement explainable
   governance decisions consistent with IEEE 7001 principles. Every
   fidelity score, zone classification, and intervention rationale
   is exposed to the user and logged for audit.

5. **NIST AI 600-1** (Generative AI Profile, 2024 — MEASURE 2.6):
   Fidelity scoring implements MEASURE 2.6's requirement for "metrics
   that quantify AI system performance, including measures related to
   trustworthiness." The two-layer detection provides both coarse
   (baseline similarity) and fine (basin membership) performance
   measurements — exactly the multi-level measurement approach NIST
   600-1 recommends for GenAI risk quantification.

6. **OWASP LLM Top 10** (2025 — LLM08, Excessive Agency): The graduated
   decision ladder (EXECUTE → CLARIFY → INERT → ESCALATE)
   mitigates LLM08 by constraining agent autonomy proportionally to
   alignment confidence. Low-fidelity requests are directed to human
   review via ESCALATE, preventing unbounded agent authority. This
   implements defense-in-depth against excessive agency.

7. **NIST AI RMF 100** (AI Risk Management Framework, 2023 — MANAGE 2.2):
   The direction levels (NONE/MONITOR/CORRECT/DIRECT/HARD_BLOCK)
   implement MANAGE 2.2's requirement for "mechanisms to respond to and
   recover from identified risks." Each direction level is a calibrated
   risk response — graduated from passive monitoring to active blocking.

Uses the "Detect and Direct" pattern:
- DETECT drift via fidelity measurement against the Primacy Attractor
- DIRECT graduated response based on severity of drift
"""

import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np

from telos_core.time_utils import utc_now
from telos_governance.types import (
    ActionDecision,
    DirectionLevel,
    GovernanceDecision,
    GovernanceResult,
    SIMILARITY_BASELINE,
    FIDELITY_GREEN,
    FIDELITY_YELLOW,
    FIDELITY_ORANGE,
    AGENTIC_EXECUTE_THRESHOLD,
    AGENTIC_CLARIFY_THRESHOLD,
)
from telos_governance.pa_extractor import PrimacyAttractor

# Import shared normalization from telos_core (single source of truth)
try:
    from telos_core.fidelity_engine import normalize_mistral_fidelity
except ImportError:
    normalize_mistral_fidelity = None

logger = logging.getLogger(__name__)


class FidelityGate:
    """
    The TELOS Governance Gate for agentic AI (Tier 1).

    Measures fidelity of requests against the Primacy Attractor
    and makes governance decisions using the guardian-ward model:
    the gate protects the agent's constitutional mandate against
    requests that fall outside its authorized scope.

    Agentic thresholds are TIGHTER than conversational because
    tool selection is binary — you either execute the right tool
    or you don't. No interpretation wiggle room. This reflects the
    asymmetric cost principle: the cost of a wrong action exceeds
    the cost of a wrong sentence (Brunner, 2025).
    """

    def __init__(
        self,
        embed_fn: Callable[[str], np.ndarray],
        execute_threshold: float = None,
        clarify_threshold: float = None,
        baseline_threshold: float = None,
    ):
        """
        Initialize the fidelity gate.

        Args:
            embed_fn: Function to embed text strings
            execute_threshold: Fidelity threshold for EXECUTE (default 0.85)
            clarify_threshold: Fidelity threshold for CLARIFY (default 0.70)
            baseline_threshold: Hard block threshold (default 0.20)
        """
        self.embed_fn = embed_fn

        # Thresholds (use constant defaults if not specified)
        self.execute_threshold = execute_threshold or AGENTIC_EXECUTE_THRESHOLD
        self.clarify_threshold = clarify_threshold or AGENTIC_CLARIFY_THRESHOLD
        self.baseline_threshold = baseline_threshold or SIMILARITY_BASELINE

    def check_fidelity(
        self,
        user_message: str,
        pa: PrimacyAttractor,
        high_risk: bool = False,
        tools: Optional[List[Dict[str, str]]] = None,
    ) -> GovernanceResult:
        """
        Check a user message against the Primacy Attractor.

        This is the main entry point for governance.

        Args:
            user_message: The user's message text
            pa: The Primacy Attractor to check against
            high_risk: If True, low fidelity triggers ESCALATE instead of INERT
            tools: Optional list of tool dicts with 'name' and 'description' keys

        Returns:
            GovernanceResult with decision and metadata
        """
        request_id = str(uuid.uuid4())[:8]

        # Step 1: Check input fidelity
        input_decision = self._check_input_fidelity(user_message, pa, high_risk)

        # Step 2: Check tool fidelity (if tools are defined)
        tool_decisions = None
        tools_blocked = 0
        if tools:
            tool_decisions = self._check_tool_fidelity(tools, pa)
            tools_blocked = sum(1 for d in tool_decisions.values() if not d.should_forward)

        # Step 3: Determine final decision
        # If input is blocked, don't forward
        # If any critical tools are blocked, may need to clarify
        if not input_decision.should_forward:
            final_decision = input_decision.decision
            forwarded = False
        elif tools_blocked > 0 and input_decision.decision == ActionDecision.EXECUTE:
            # Downgrade to CLARIFY if tools were blocked
            final_decision = ActionDecision.CLARIFY
            forwarded = True  # Still forward, but with modified tool set
        else:
            final_decision = input_decision.decision
            forwarded = input_decision.should_forward

        # Determine direction level based on fidelity
        direction_level = self._determine_direction_level(
            input_decision.fidelity, input_decision.raw_similarity
        )

        # Build result
        return GovernanceResult(
            request_id=request_id,
            timestamp=utc_now(),
            pa_text=pa.text,
            pa_source=pa.source,
            input_fidelity=input_decision.fidelity,
            input_decision=input_decision.decision,
            input_blocked=not input_decision.should_forward,
            tools_checked=len(tool_decisions) if tool_decisions else 0,
            tools_blocked=tools_blocked,
            tool_decisions=tool_decisions,
            final_decision=final_decision,
            forwarded_to_llm=forwarded,
            governance_response=(
                self._generate_governance_response(input_decision) if not forwarded else None
            ),
            direction_level=direction_level,
            direction_applied=direction_level != DirectionLevel.NONE,
        )

    def _check_input_fidelity(
        self,
        user_message: str,
        pa: PrimacyAttractor,
        high_risk: bool = False,
    ) -> GovernanceDecision:
        """Check fidelity of the input message against the PA."""
        if not user_message:
            # No user message - this is unusual but allowed
            return GovernanceDecision(
                decision=ActionDecision.EXECUTE,
                fidelity=1.0,
                raw_similarity=1.0,
                reason="No user message to check",
                should_forward=True,
            )

        # Calculate fidelity
        raw_similarity, fidelity = self._calculate_fidelity(user_message, pa)

        # Make decision based on thresholds
        decision = self._make_decision(fidelity, raw_similarity, high_risk)

        return GovernanceDecision(
            decision=decision,
            fidelity=fidelity,
            raw_similarity=raw_similarity,
            reason=self._get_decision_reason(decision, fidelity),
            should_forward=decision in [
                ActionDecision.EXECUTE, ActionDecision.CLARIFY
            ],
        )

    def _check_tool_fidelity(
        self,
        tools: List[Dict[str, str]],
        pa: PrimacyAttractor,
    ) -> Dict[str, GovernanceDecision]:
        """
        Check fidelity of each tool against the PA.

        Tools with low fidelity should be blocked - they're not
        aligned with the agent's declared purpose.
        """
        tool_decisions = {}

        for tool in tools:
            tool_name = tool.get("name", "unknown")
            tool_desc = tool.get("description", tool_name)
            tool_text = f"{tool_name}: {tool_desc}"
            raw_similarity, fidelity = self._calculate_fidelity(tool_text, pa)
            decision = self._make_decision(fidelity, raw_similarity, high_risk=False)

            tool_decisions[tool_name] = GovernanceDecision(
                decision=decision,
                fidelity=fidelity,
                raw_similarity=raw_similarity,
                reason=f"Tool '{tool_name}' fidelity: {fidelity:.2f}",
                should_forward=(
                    decision != ActionDecision.INERT and decision != ActionDecision.ESCALATE
                ),
            )

            if not tool_decisions[tool_name].should_forward:
                logger.warning(
                    f"Tool '{tool_name}' blocked: fidelity {fidelity:.2f} below threshold"
                )

        return tool_decisions

    def _calculate_fidelity(
        self,
        text: str,
        pa: PrimacyAttractor,
    ) -> Tuple[float, float]:
        """
        Calculate fidelity of text against PA.

        Returns:
            (raw_similarity, normalized_fidelity)

        Mistral embeddings produce a narrow discriminative range:
        - Off-topic content: 0.55-0.65 raw similarity
        - On-topic content: 0.70-0.80 raw similarity

        We map this to TELOS fidelity zones:
        - < 0.55: Clearly off-topic -> RED (0.0-0.30)
        - 0.55-0.70: Ambiguous/drift -> YELLOW/ORANGE (0.30-0.70)
        - > 0.70: On-topic -> GREEN (0.70-1.0)
        """
        # Embed the text
        text_embedding = self.embed_fn(text)

        # Calculate cosine similarity
        raw_similarity = self._cosine_similarity(text_embedding, pa.embedding)

        # Mistral-calibrated normalization (shared from telos_core)
        if normalize_mistral_fidelity is not None:
            fidelity = normalize_mistral_fidelity(raw_similarity)
        else:
            # Inline fallback if telos_core not available
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
            fidelity = float(min(1.0, max(0.0, fidelity)))

        return float(raw_similarity), fidelity

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(a, b) / (norm_a * norm_b))

    def _make_decision(
        self,
        fidelity: float,
        raw_similarity: float,
        high_risk: bool = False,
    ) -> ActionDecision:
        """
        Make governance decision based on normalized fidelity.

        Agentic thresholds (calibrated for normalized fidelity 0-1):
        - EXECUTE: >= execute_threshold (high confidence, proceed)
        - CLARIFY: >= clarify_threshold (verify intent before proceeding)
        - INERT/ESCALATE: below clarify_threshold (outside agent's purpose)
        """
        if fidelity >= self.execute_threshold:
            return ActionDecision.EXECUTE
        elif fidelity >= self.clarify_threshold:
            return ActionDecision.CLARIFY
        else:
            return ActionDecision.ESCALATE if high_risk else ActionDecision.INERT

    def _determine_direction_level(
        self,
        fidelity: float,
        raw_similarity: float,
    ) -> DirectionLevel:
        """
        Determine the direction level based on fidelity measurement.

        Two-layer detection (the core TELOS innovation):
        - Layer 1: raw_similarity < SIMILARITY_BASELINE → HARD_BLOCK
          (extreme off-topic, analogous to SPC "special cause" detection)
        - Layer 2: fidelity < thresholds → graduated direction
          (purpose drift, analogous to SPC "common cause" zone classification)

        Direction levels map to Ostrom's graduated sanctions:
        - NONE: No sanction needed (agent is aligned)
        - MONITOR: First warning (context injection)
        - CORRECT: Active correction (redirect toward PA)
        - DIRECT: Strong intervention (constrain response space)
        - HARD_BLOCK: Maximum sanction (refuse and escalate)
        """
        # Layer 1: Baseline check
        if raw_similarity < self.baseline_threshold:
            return DirectionLevel.HARD_BLOCK

        # Layer 2: Zone-based graduated direction
        if fidelity >= FIDELITY_GREEN:
            return DirectionLevel.NONE
        elif fidelity >= FIDELITY_YELLOW:
            return DirectionLevel.MONITOR
        elif fidelity >= FIDELITY_ORANGE:
            return DirectionLevel.CORRECT
        else:
            return DirectionLevel.DIRECT

    def _get_decision_reason(self, decision: ActionDecision, fidelity: float) -> str:
        """Generate human-readable reason for decision."""
        reasons = {
            ActionDecision.EXECUTE: (
                f"High fidelity ({fidelity:.2f}) - proceeding with request"
            ),
            ActionDecision.CLARIFY: (
                f"Moderate fidelity ({fidelity:.2f}) - forwarding with governance context"
            ),
            ActionDecision.INERT: (
                f"Very low fidelity ({fidelity:.2f}) - request outside agent's purpose"
            ),
            ActionDecision.ESCALATE: (
                f"Very low fidelity ({fidelity:.2f}) in high-risk context - requiring review"
            ),
        }
        return reasons.get(decision, f"Fidelity: {fidelity:.2f}")

    def _generate_governance_response(self, decision: GovernanceDecision) -> str:
        """Generate a governance response when request is blocked."""
        if decision.decision == ActionDecision.INERT:
            return (
                "I appreciate your request, but it appears to be outside the scope of "
                "my defined purpose. I'm designed to help with specific tasks as defined "
                "in my system configuration. Could you rephrase your request to align "
                "with my intended function?"
            )
        elif decision.decision == ActionDecision.ESCALATE:
            return (
                "This request requires human review before I can proceed. The request "
                "has been flagged for expert evaluation due to potential misalignment "
                "with my operational boundaries."
            )
        else:
            return (
                f"Request governance check: {decision.reason}. "
                "Please clarify your intent."
            )

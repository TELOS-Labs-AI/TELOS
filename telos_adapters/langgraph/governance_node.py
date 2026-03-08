"""
TELOS Governance Node
=====================

The core governance node that sits between reasoning and tool execution.
Implements two-layer fidelity detection and LangGraph's interrupt() for
human-in-the-loop governance decisions.

CRITICAL: This gate uses AGENTIC thresholds (0.85 for execute) not
conversational thresholds (0.70 for green zone). Tool selection is binary -
you either execute the right tool or you don't.

This is the heart of TELOS governance for agentic AI.

Regulatory traceability:
    - SAAI claim TELOS-SAAI-001: calculate_fidelity() is the per-action
      continuous drift measurement against the Primacy Attractor
    - SAAI claim TELOS-SAAI-002: Two-layer detection (baseline + basin) with
      graduated direction levels (NONE/MONITOR/CORRECT/DIRECT/HARD_BLOCK)
    - SAAI claim TELOS-SAAI-004: TelosGovernanceGate sits external to the agent —
      the agent cannot bypass or modify the gate (corrigibility)
    - SAAI claim TELOS-SAAI-005: _update_state_after_governance records every
      approval and block to the governance_trace for transparency
    - SAAI claim TELOS-SAAI-008: _request_escalation() triggers human expert review
      via LangGraph interrupt() for high-risk low-fidelity scenarios
    - EU AI Act Art. 14: interrupt() implements mandatory human oversight
    - NIST AI 600-1 (MEASURE): Agentic thresholds are documented, versioned,
      centralized governance parameters (imported from telos_core.constants)
    - OWASP LLM Top 10 (LLM08): EXECUTE/CLARIFY/ESCALATE taxonomy
      constrains agent autonomy proportionally to alignment confidence
"""

from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import numpy as np
import logging

from .state_schema import (
    TelosGovernedState,
    PrimacyAttractor,
    GovernanceTraceEntry,
    ActionChainEntry,
    FidelityZone,
    DirectionLevel,
    get_zone_from_fidelity,
    get_direction_level,
    calculate_sci,
    SIMILARITY_BASELINE,
    FIDELITY_GREEN,
)

# Import governance types from telos_governance
try:
    from telos_governance.types import ActionDecision
    TELOS_GOVERNANCE_AVAILABLE = True
except ImportError:
    TELOS_GOVERNANCE_AVAILABLE = False

# Import agentic thresholds from telos_core (single source of truth)
from telos_core.constants import (
    AGENTIC_EXECUTE_THRESHOLD,
    AGENTIC_CLARIFY_THRESHOLD,
)
TELOS_CORE_AVAILABLE = True

# Try to import LangGraph's interrupt for human-in-the-loop
try:
    from langgraph.types import interrupt
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    def interrupt(data: dict) -> dict:
        """Fallback when LangGraph not available - auto-approve."""
        logging.warning("LangGraph not available, auto-approving governance decision")
        return {"approved": True}


logger = logging.getLogger(__name__)


# =============================================================================
# FIDELITY CALCULATION
# =============================================================================

def calculate_fidelity(
    text_or_embedding: Any,
    pa: PrimacyAttractor,
    embed_fn: Optional[Callable[[str], np.ndarray]] = None,
) -> tuple[float, float]:
    """
    Calculate fidelity score for text or embedding against PA.

    Args:
        text_or_embedding: Either a string to embed or a numpy array
        pa: The Primacy Attractor to measure against
        embed_fn: Optional embedding function (required if text provided)

    Returns:
        (raw_similarity, normalized_fidelity)
    """
    # Get embedding
    if isinstance(text_or_embedding, str):
        if embed_fn is None:
            raise ValueError("embed_fn required when passing text")
        embedding = embed_fn(text_or_embedding)
    else:
        embedding = np.array(text_or_embedding)

    pa_embedding = np.array(pa.embedding)

    # Cosine similarity
    raw_similarity = float(np.dot(embedding, pa_embedding) / (
        np.linalg.norm(embedding) * np.linalg.norm(pa_embedding)
    ))

    # Normalize to display range (matching TELOS Observatory calibration)
    # Raw SentenceTransformer range: ~0.15-0.45 -> Display: 0.35-0.95
    # Raw Mistral range: ~0.40-0.75 -> Display: 0.50-1.00
    # Using adaptive normalization based on observed ranges
    if raw_similarity < 0.15:
        normalized = 0.35 + (raw_similarity / 0.15) * 0.15
    elif raw_similarity < 0.45:
        normalized = 0.50 + ((raw_similarity - 0.15) / 0.30) * 0.40
    else:
        normalized = 0.90 + ((raw_similarity - 0.45) / 0.30) * 0.10

    # Clamp to valid range
    normalized = max(0.0, min(1.0, normalized))

    return raw_similarity, normalized


def get_fidelity_zone(fidelity: float) -> FidelityZone:
    """Get the fidelity zone for display/logging."""
    return get_zone_from_fidelity(fidelity)


# =============================================================================
# GOVERNANCE NODE CLASS
# =============================================================================

class TelosGovernanceGate:
    """
    TELOS Governance Gate for LangGraph agents.

    Sits between reasoning and tool execution to:
    1. Measure fidelity of proposed actions against PA
    2. Apply two-layer detection (baseline + basin)
    3. Use AGENTIC thresholds (0.85 execute, not 0.70 green)
    4. Trigger interrupt() for human approval when needed
    5. ESCALATE to human experts for high-risk scenarios
    6. Record governance trace for audit

    CRITICAL: Tool selection uses TIGHTER thresholds than semantic alignment.
    - EXECUTE: >= 0.85 (vs 0.70 for conversational green zone)
    - CLARIFY: 0.50-0.84 (verify intent before acting)
    - ESCALATE: < 0.50 (no match, require human review)

    Usage:
        gate = TelosGovernanceGate(embed_fn=my_embedding_function)

        # For high-risk deployments (financial, medical, legal):
        gate = TelosGovernanceGate(embed_fn=embed, high_risk=True)

        # In your LangGraph graph:
        graph.add_node("telos_gate", gate)
        graph.add_edge("agent", "telos_gate")
        graph.add_edge("telos_gate", "tools")
    """

    def __init__(
        self,
        embed_fn: Callable[[str], np.ndarray],
        auto_approve_green: bool = True,
        require_approval_below: float = AGENTIC_EXECUTE_THRESHOLD,
        high_risk: bool = False,
        use_agentic_thresholds: bool = True,
    ):
        """
        Initialize the governance gate.

        Args:
            embed_fn: Function to embed text strings
            auto_approve_green: Auto-approve actions above threshold (default True)
            require_approval_below: Fidelity threshold requiring approval
                                    Default: 0.85 (AGENTIC) not 0.70 (conversational)
            high_risk: If True, low-fidelity triggers ESCALATE (human expert review)
                       instead of INERT. Use for irreversible actions (financial,
                       medical, legal) or compliance requirements.
            use_agentic_thresholds: Use tighter agentic thresholds (0.85 for execute)
                                    instead of conversational (0.70 for green).
                                    Default True - set False for backward compat.
        """
        self.embed_fn = embed_fn
        self.auto_approve_green = auto_approve_green
        self.require_approval_below = require_approval_below
        self.high_risk = high_risk
        self.use_agentic_thresholds = use_agentic_thresholds

    def __call__(self, state: TelosGovernedState) -> TelosGovernedState:
        """
        Process state through governance gate.

        This is the node function for LangGraph.
        """
        return self.process(state)

    def process(self, state: TelosGovernedState) -> TelosGovernedState:
        """
        Main governance processing logic.

        1. Extract proposed tool calls from last message
        2. Measure fidelity for each
        3. Apply direction logic
        4. Record to governance trace
        """
        # Get PA from state
        if not state.get("primacy_attractor"):
            logger.warning("No PA in state, passing through without governance")
            return state

        pa = PrimacyAttractor.from_dict(state["primacy_attractor"])

        # Get the last message (should contain tool calls)
        messages = state.get("messages", [])
        if not messages:
            return state

        last_message = messages[-1]

        # Check for tool calls (LangGraph format)
        tool_calls = getattr(last_message, "tool_calls", None) or []
        if not tool_calls:
            # No tool calls, just measure message fidelity
            return self._measure_message_fidelity(state, pa, last_message)

        # Process each tool call through governance
        approved_calls = []
        blocked_calls = []

        for tool_call in tool_calls:
            result = self._process_tool_call(state, pa, tool_call)

            if result["approved"]:
                approved_calls.append(tool_call)
            else:
                blocked_calls.append({
                    "tool_call": tool_call,
                    "reason": result.get("reason", "Low fidelity"),
                    "fidelity": result["fidelity"],
                })

        # Update state
        state = self._update_state_after_governance(
            state, pa, approved_calls, blocked_calls
        )

        # If tool calls were blocked, we may need to modify the message
        if blocked_calls and hasattr(last_message, "tool_calls"):
            last_message.tool_calls = approved_calls

        return state

    def _measure_message_fidelity(
        self,
        state: TelosGovernedState,
        pa: PrimacyAttractor,
        message: Any,
    ) -> TelosGovernedState:
        """Measure fidelity for a regular message (no tool calls)."""
        content = getattr(message, "content", str(message))
        if not content:
            return state

        raw_sim, fidelity = calculate_fidelity(content, pa, self.embed_fn)
        zone = get_fidelity_zone(fidelity)

        # Update state
        state["current_fidelity"] = fidelity
        state["current_zone"] = zone.value

        # Add to trajectory
        trajectory = state.get("fidelity_trajectory", [])
        trajectory.append({
            "turn": state.get("turn_number", 0),
            "timestamp": datetime.now().isoformat(),
            "raw_similarity": raw_sim,
            "fidelity": fidelity,
            "zone": zone.value,
        })
        state["fidelity_trajectory"] = trajectory

        return state

    def _process_tool_call(
        self,
        state: TelosGovernedState,
        pa: PrimacyAttractor,
        tool_call: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process a single tool call through governance.

        Uses AGENTIC thresholds (0.85 for execute) when use_agentic_thresholds=True.
        Triggers ESCALATE for high_risk mode when fidelity is low.

        Returns dict with approval status and details.
        """
        # Build action description for fidelity measurement
        tool_name = tool_call.get("name", "unknown")
        tool_args = tool_call.get("args", {})
        action_text = f"{tool_name}: {tool_args}"

        # Calculate fidelity
        raw_sim, fidelity = calculate_fidelity(action_text, pa, self.embed_fn)
        zone = get_fidelity_zone(fidelity)
        direction = get_direction_level(fidelity, raw_sim)

        # Get embedding for SCI tracking
        action_embedding = self.embed_fn(action_text)

        # Calculate SCI if we have previous action
        sci_score = 1.0
        if state.get("last_action_embedding"):
            prev_embedding = np.array(state["last_action_embedding"])
            prev_fidelity = state.get("current_fidelity", 1.0)
            sci_score, inherited = calculate_sci(
                action_embedding, prev_embedding, prev_fidelity
            )

        # Decision logic - use AGENTIC thresholds if enabled and available
        result = {
            "tool_name": tool_name,
            "raw_similarity": raw_sim,
            "fidelity": fidelity,
            "zone": zone.value,
            "direction": direction.value,
            "sci_score": sci_score,
            "embedding": action_embedding.tolist(),
        }

        # =================================================================
        # AGENTIC GOVERNANCE (tighter thresholds for tool execution)
        # =================================================================
        if self.use_agentic_thresholds and TELOS_CORE_AVAILABLE and TELOS_GOVERNANCE_AVAILABLE:
            # Classify using agentic thresholds from telos_core.constants
            if fidelity >= AGENTIC_EXECUTE_THRESHOLD:
                agentic_decision = ActionDecision.EXECUTE
                reason = f"High fidelity ({fidelity:.2f}) - proceed"
            elif fidelity >= AGENTIC_CLARIFY_THRESHOLD:
                agentic_decision = ActionDecision.CLARIFY
                reason = f"Moderate fidelity ({fidelity:.2f}) - verify intent"
            elif self.high_risk:
                agentic_decision = ActionDecision.ESCALATE
                reason = f"Very low fidelity ({fidelity:.2f}) in high-risk context"
            else:
                agentic_decision = ActionDecision.ESCALATE
                reason = f"Very low fidelity ({fidelity:.2f}) - outside purpose"

            result["action_decision"] = agentic_decision.value
            result["confidence"] = fidelity
            result["decision_reason"] = reason

            # EXECUTE: High-fidelity match (>= 0.85)
            if agentic_decision == ActionDecision.EXECUTE:
                result["approved"] = True
                result["approval_source"] = "auto_agentic"
                return result

            # CLARIFY: Close match (0.70-0.84) - request confirmation
            if agentic_decision == ActionDecision.CLARIFY:
                approval = self._request_approval(
                    action_text=action_text,
                    fidelity=fidelity,
                    zone=zone,
                    direction=direction,
                    reason=f"CLARIFY: Verify intent before executing {tool_name}",
                )
                result["approved"] = approval.get("approved", False)
                result["approval_source"] = "human_clarify"
                result["reason"] = reason
                return result

                result["reason"] = reason
                return result

            # ESCALATE: High-risk + low fidelity - human expert MUST review
            if agentic_decision == ActionDecision.ESCALATE:
                logger.warning(
                    f"ESCALATE: High-risk tool call '{tool_name}' with fidelity "
                    f"{fidelity:.2f} requires human expert review"
                )
                approval = self._request_escalation(
                    action_text=action_text,
                    fidelity=fidelity,
                    tool_name=tool_name,
                    reason=reason,
                )
                result["approved"] = approval.get("approved", False)
                result["approval_source"] = "human_escalate"
                result["reason"] = reason
                result["escalated"] = True
                return result

            # ESCALATE (non-high-risk): No match (< 0.50) - don't execute
            if agentic_decision == ActionDecision.ESCALATE:
                result["approved"] = False
                result["approval_source"] = "blocked_escalate"
                result["reason"] = reason
                return result

        # =================================================================
        # FALLBACK: Zone-based governance (backward compatibility)
        # =================================================================

        # Layer 1: Hard block for extreme off-topic
        if direction == DirectionLevel.HARD_BLOCK:
            if self.high_risk:
                # High-risk mode: escalate instead of just blocking
                approval = self._request_escalation(
                    action_text=action_text,
                    fidelity=fidelity,
                    tool_name=tool_name,
                    reason="Extreme drift detected (baseline violation) - high risk",
                )
                result["approved"] = approval.get("approved", False)
                result["approval_source"] = "human_escalate"
                result["escalated"] = True
            else:
                approval = self._request_approval(
                    action_text=action_text,
                    fidelity=fidelity,
                    zone=zone,
                    direction=direction,
                    reason="Extreme drift detected (baseline violation)",
                )
                result["approved"] = approval.get("approved", False)
                result["approval_source"] = "human" if approval.get("approved") else "blocked"
            result["reason"] = "Layer 1 baseline violation"
            return result

        # Layer 2: Zone-based direction
        if direction == DirectionLevel.NONE:
            # GREEN zone - auto-approve
            result["approved"] = True
            result["approval_source"] = "auto"
            return result

        if direction == DirectionLevel.MONITOR:
            # YELLOW zone - approve with context injection
            result["approved"] = True
            result["approval_source"] = "auto_with_context"
            result["context_injected"] = True
            return result

        # ORANGE/RED zones - require approval
        approval = self._request_approval(
            action_text=action_text,
            fidelity=fidelity,
            zone=zone,
            direction=direction,
            reason=f"Action fidelity ({fidelity:.2f}) below threshold",
        )

        result["approved"] = approval.get("approved", False)
        result["approval_source"] = "human" if approval.get("approved") else "blocked"
        result["reason"] = f"Zone {zone.value} requires approval"

        return result

    def _request_approval(
        self,
        action_text: str,
        fidelity: float,
        zone: FidelityZone,
        direction: DirectionLevel,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Request human approval via LangGraph's interrupt().

        Returns approval decision.
        """
        if not LANGGRAPH_AVAILABLE:
            logger.warning("LangGraph not available, auto-blocking for safety")
            return {"approved": False, "reason": "LangGraph not available"}

        # Use interrupt() for human-in-the-loop
        return interrupt({
            "type": direction.value,
            "action": action_text,
            "fidelity": fidelity,
            "zone": zone.value,
            "reason": reason,
            "prompt": f"Action '{action_text}' has fidelity {fidelity:.2f} ({zone.value} zone). Approve?",
        })

    def _request_escalation(
        self,
        action_text: str,
        fidelity: float,
        tool_name: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Request human EXPERT escalation via LangGraph's interrupt().

        ESCALATE is different from regular approval:
        - Regular approval: "Do you approve this action?"
        - Escalation: "A qualified expert must review this decision"

        Used for high-risk scenarios where:
        - Tool selection involves irreversible actions (financial, medical, legal)
        - Confidence is low but stakes are high
        - Domain expertise required for decision validation
        - Regulatory/compliance requirements mandate human oversight

        Returns escalation decision.
        """
        if not LANGGRAPH_AVAILABLE:
            logger.warning(
                "LangGraph not available for escalation, auto-blocking for safety. "
                f"Tool '{tool_name}' with fidelity {fidelity:.2f} requires expert review."
            )
            return {"approved": False, "reason": "LangGraph not available for escalation"}

        # Use interrupt() with ESCALATE context - human expert MUST intervene
        return interrupt({
            "type": "escalate",
            "severity": "high",
            "action": action_text,
            "tool_name": tool_name,
            "fidelity": fidelity,
            "reason": reason,
            "prompt": (
                f"HUMAN EXPERT REVIEW REQUIRED\n\n"
                f"Tool: {tool_name}\n"
                f"Fidelity: {fidelity:.2f}\n"
                f"Reason: {reason}\n\n"
                f"This action has been flagged as HIGH-RISK and requires "
                f"qualified human expert review before proceeding.\n\n"
                f"Action: {action_text[:200]}{'...' if len(action_text) > 200 else ''}"
            ),
            "requires_expert": True,
        })

    def _update_state_after_governance(
        self,
        state: TelosGovernedState,
        pa: PrimacyAttractor,
        approved_calls: List[Dict],
        blocked_calls: List[Dict],
    ) -> TelosGovernedState:
        """Update state with governance results."""
        turn_number = state.get("turn_number", 0) + 1
        state["turn_number"] = turn_number

        # Record to governance trace
        trace = state.get("governance_trace", [])

        for call_info in approved_calls:
            trace.append(GovernanceTraceEntry(
                timestamp=datetime.now(),
                turn_number=turn_number,
                action_type="tool_call",
                action_description=f"{call_info.get('name', 'unknown')}",
                raw_similarity=0.0,  # Would need to recalculate
                fidelity_score=state.get("current_fidelity", 0.0),
                zone=get_fidelity_zone(state.get("current_fidelity", 0.0)),
                direction_level=DirectionLevel.NONE,
                approved=True,
                approval_source="auto",
            ).to_dict())

        for blocked in blocked_calls:
            tool_call = blocked["tool_call"]
            trace.append(GovernanceTraceEntry(
                timestamp=datetime.now(),
                turn_number=turn_number,
                action_type="tool_call",
                action_description=f"{tool_call.get('name', 'unknown')}",
                raw_similarity=0.0,
                fidelity_score=blocked["fidelity"],
                zone=get_fidelity_zone(blocked["fidelity"]),
                direction_level=DirectionLevel.DIRECT,
                direction_reason=blocked["reason"],
                approved=False,
                approval_source="blocked",
            ).to_dict())

        state["governance_trace"] = trace

        # Update direction count
        state["direction_count"] = state.get("direction_count", 0) + len(blocked_calls)

        return state


# =============================================================================
# CONVENIENCE FUNCTION FOR LANGGRAPH NODE
# =============================================================================

def telos_governance_node(
    embed_fn: Callable[[str], np.ndarray],
    **kwargs,
) -> Callable[[TelosGovernedState], TelosGovernedState]:
    """
    Create a TELOS governance node function for LangGraph.

    Usage:
        from telos_adapters.langgraph import telos_governance_node

        graph = StateGraph(TelosGovernedState)
        graph.add_node("telos_gate", telos_governance_node(embed_fn=my_embed))
        graph.add_edge("agent", "telos_gate")
        graph.add_edge("telos_gate", "tools")
    """
    gate = TelosGovernanceGate(embed_fn=embed_fn, **kwargs)
    return gate

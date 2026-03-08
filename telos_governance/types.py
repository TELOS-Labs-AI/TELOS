"""
Governance Types
================

Types for TELOS governance decisions and traces.

Terminology:
- "Direction" refers to the system's graduated response to drift
  (Detect and Direct pattern). The system DETECTS drift via fidelity
  measurement and DIRECTS response back toward the primacy attractor.
- DirectionLevel replaces InterventionLevel from earlier versions.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

from telos_core.time_utils import utc_now

# Import threshold constants from telos_core (single source of truth)
from telos_core.constants import (
    SIMILARITY_BASELINE,
    DIRECTION_THRESHOLD,
    FIDELITY_GREEN,
    FIDELITY_YELLOW,
    FIDELITY_ORANGE,
    AGENTIC_EXECUTE_THRESHOLD,
    AGENTIC_CLARIFY_THRESHOLD,
)


class ActionDecision(str, Enum):
    """
    Action decisions for TELOS governance.

    3-verdict model:
    - EXECUTE: fidelity >= 0.85 - High confidence, proceed
    - CLARIFY: fidelity 0.70-0.84 - Close match, verify first
    - ESCALATE: fidelity < 0.70 - Require human review
    """
    EXECUTE = "execute"
    CLARIFY = "clarify"
    ESCALATE = "escalate"


class DirectionLevel(str, Enum):
    """
    Graduated direction levels for governance actions.

    The system detects drift and directs response proportionally:
    - NONE: Aligned, no direction needed
    - MONITOR: Minor drift, log and observe
    - CORRECT: Moderate drift, inject context correction
    - DIRECT: Significant drift, redirect toward attractor
    - ESCALATE: High drift in sensitive context, require review
    - HARD_BLOCK: Layer 1 baseline violation, block immediately
    """
    NONE = "none"
    MONITOR = "monitor"
    CORRECT = "correct"
    DIRECT = "direct"
    ESCALATE = "escalate"
    HARD_BLOCK = "hard_block"


class GovernanceDecision(BaseModel):
    """Result of a governance check."""
    decision: ActionDecision
    fidelity: float
    raw_similarity: float
    reason: str
    should_forward: bool
    should_modify: bool = False
    modified_content: Optional[str] = None

    # Tool-specific governance
    tool_fidelities: Optional[Dict[str, float]] = None
    blocked_tools: Optional[List[str]] = None

    # Direction tracking (renamed from intervention)
    direction_level: DirectionLevel = DirectionLevel.NONE
    direction_applied: bool = False


class GovernanceResult(BaseModel):
    """
    Complete governance result for a request.

    Includes input governance, tool governance, and any modifications.
    """
    request_id: str
    timestamp: datetime = Field(default_factory=utc_now)

    # PA information
    pa_text: str
    pa_source: str  # "system_prompt", "configured", "inferred"

    # Input governance
    input_fidelity: float
    input_decision: ActionDecision
    input_blocked: bool = False

    # Tool governance (if applicable)
    tools_checked: int = 0
    tools_blocked: int = 0
    tool_decisions: Optional[Dict[str, GovernanceDecision]] = None

    # Response governance (post-LLM)
    response_fidelity: Optional[float] = None
    response_decision: Optional[ActionDecision] = None

    # Overall decision
    final_decision: ActionDecision
    forwarded_to_llm: bool
    governance_response: Optional[str] = None  # If we blocked and responded ourselves

    # Direction tracking
    direction_level: DirectionLevel = DirectionLevel.NONE
    direction_applied: bool = False


class GovernanceTrace(BaseModel):
    """
    Governance trace entry for audit trail.

    Matches the schema in telos_governance_traces/ for consistency.
    """
    event_type: str
    timestamp: datetime = Field(default_factory=utc_now)
    request_id: str
    session_id: Optional[str] = None

    # Request info (privacy-safe)
    model: str
    message_count: int
    has_tools: bool
    has_system_prompt: bool

    # Governance metrics
    pa_hash: str  # SHA256 of PA text, not the text itself
    input_fidelity: float
    decision: ActionDecision
    forwarded: bool

    # Tool governance
    tools_total: int = 0
    tools_allowed: int = 0
    tools_blocked: int = 0

    # Direction metrics (renamed from intervention)
    direction_level: DirectionLevel = DirectionLevel.NONE
    direction_applied: bool = False
    direction_threshold: float = DIRECTION_THRESHOLD

    # Response metrics (if applicable)
    response_fidelity: Optional[float] = None
    response_tokens: Optional[int] = None

    # Latency
    governance_latency_ms: int = 0
    total_latency_ms: int = 0

    def to_jsonl(self) -> str:
        """Serialize to JSONL format."""
        import json
        data = self.model_dump()
        data["timestamp"] = data["timestamp"].isoformat()
        return json.dumps(data)

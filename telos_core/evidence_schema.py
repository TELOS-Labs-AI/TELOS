"""
Evidence Schema for TELOS Governance Tracing
=============================================

Pydantic models defining the unified JSONL schema for governance events.
Supports three privacy modes:
- full: Complete data including content
- hashed: Content replaced with SHA-256 hashes
- deltas_only: Only fidelity changes, no content (default)

Inspired by claude-trace patterns but adapted for TELOS governance context.

Compliance:
- NIST AI 600-1 (MEASURE): The unified JSONL schema captures exactly the governance
  metrics NIST 600-1 requires for GenAI monitoring — fidelity scores, decisions,
  intervention levels, and drift measurements in a structured, machine-readable format.
- IEEE P7002 (Data Privacy Process): Three privacy modes (full/hashed/deltas_only)
  implement graduated data minimization per IEEE P7002 — organizations choose the
  minimum data collection necessary for their governance requirements.
- NIST AI RMF (MANAGE 4.1): The schema supports the post-deployment monitoring data
  structures needed for MANAGE 4.1 compliance — each event type maps to a specific
  governance lifecycle stage (SESSION_START → PA_ESTABLISHED → FIDELITY_CALCULATED
  → INTERVENTION_TRIGGERED → SESSION_END).
- OWASP LLM Top 10 (LLM09 — Overreliance): Governance event logging enables
  detection of patterns indicating model overreliance — consecutive low-fidelity
  responses, escalation frequency, and drift trajectories.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from telos_core.time_utils import utc_now
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
import hashlib
import json


class PrivacyMode(str, Enum):
    """Privacy modes for governance data logging."""
    FULL = "full"           # Complete data including content
    HASHED = "hashed"       # Content replaced with SHA-256 hashes
    DELTAS_ONLY = "deltas_only"  # Only fidelity metrics, no content


class EventType(str, Enum):
    """Types of governance events."""
    SESSION_START = "session_start"
    PA_ESTABLISHED = "pa_established"
    TURN_START = "turn_start"
    FIDELITY_CALCULATED = "fidelity_calculated"
    INTERVENTION_TRIGGERED = "intervention_triggered"
    RESPONSE_GENERATED = "response_generated"
    SSE_TOKEN = "sse_token"
    SSE_GOVERNANCE = "sse_governance"
    TURN_COMPLETE = "turn_complete"
    SESSION_END = "session_end"
    SESSION_SUMMARY = "session_summary"
    # SAAI Framework Events
    MANDATORY_REVIEW_TRIGGERED = "mandatory_review_triggered"
    BASELINE_ESTABLISHED = "baseline_established"


class InterventionLevel(str, Enum):
    """Intervention severity levels matching TELOS constants."""
    NONE = "none"
    MONITOR = "monitor"
    CORRECT = "correct"
    INTERVENE = "intervene"
    ESCALATE = "escalate"
    HARD_BLOCK = "hard_block"


class DriftLevel(str, Enum):
    """
    SAAI Drift severity levels for tiered response.
    Per SAAI Framework: "flexibility scales inversely with drift magnitude"
    """
    NORMAL = "normal"        # < 10% drift - no action
    WARNING = "warning"      # 10-15% drift - mandatory review triggered
    RESTRICT = "restrict"    # 15-20% drift - tighten thresholds
    BLOCK = "block"          # > 20% drift - halt until human acknowledgment


class FidelityZone(str, Enum):
    """Fidelity display zones."""
    GREEN = "green"      # >= 0.70 - Aligned
    YELLOW = "yellow"    # 0.60-0.69 - Minor drift
    ORANGE = "orange"    # 0.50-0.59 - Moderate drift
    RED = "red"          # < 0.50 - Significant drift


# ============================================================================
# Base Event Model
# ============================================================================

class BaseEvent(BaseModel):
    """Base model for all governance events."""
    event_type: EventType
    timestamp: datetime = Field(default_factory=utc_now)
    session_id: str

    class Config:
        use_enum_values = True


# ============================================================================
# Session Events
# ============================================================================

class SessionStartEvent(BaseEvent):
    """Marks the beginning of a governance session."""
    event_type: EventType = EventType.SESSION_START
    privacy_mode: PrivacyMode = PrivacyMode.DELTAS_ONLY
    telos_version: str = "v3"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    enforcement_mode: str = "enforcement"  # "enforcement" or "observation"


class PAEstablishedEvent(BaseEvent):
    """Primacy Attractor establishment event."""
    event_type: EventType = EventType.PA_ESTABLISHED
    pa_template: str  # Template name (e.g., "collaborative_reasoning")
    purpose_statement: Optional[str] = None  # Only in FULL mode
    purpose_hash: Optional[str] = None  # SHA-256 hash of purpose
    scope_statement: Optional[str] = None  # Only in FULL mode
    scope_hash: Optional[str] = None  # SHA-256 hash of scope
    tau: float  # Mixture parameter
    rigidity: float  # 1 - tau
    basin_radius: float

    def apply_privacy(self, mode: PrivacyMode) -> "PAEstablishedEvent":
        """Apply privacy mode to this event."""
        if mode == PrivacyMode.FULL:
            return self
        elif mode == PrivacyMode.HASHED:
            return self.model_copy(update={
                "purpose_statement": None,
                "scope_statement": None,
                "purpose_hash": _hash_content(self.purpose_statement) if self.purpose_statement else None,
                "scope_hash": _hash_content(self.scope_statement) if self.scope_statement else None,
            })
        else:  # DELTAS_ONLY
            return self.model_copy(update={
                "purpose_statement": None,
                "scope_statement": None,
                "purpose_hash": None,
                "scope_hash": None,
            })


class SessionEndEvent(BaseEvent):
    """Marks the end of a governance session."""
    event_type: EventType = EventType.SESSION_END
    total_turns: int
    total_interventions: int
    average_fidelity: float
    duration_seconds: float
    end_reason: str = "user_ended"  # user_ended, timeout, error


# ============================================================================
# Turn Events
# ============================================================================

class TurnStartEvent(BaseEvent):
    """Marks the beginning of a conversation turn."""
    event_type: EventType = EventType.TURN_START
    turn_number: int
    user_input: Optional[str] = None  # Only in FULL mode
    user_input_hash: Optional[str] = None
    user_input_length: int = 0

    def apply_privacy(self, mode: PrivacyMode) -> "TurnStartEvent":
        """Apply privacy mode to this event."""
        if mode == PrivacyMode.FULL:
            return self
        elif mode == PrivacyMode.HASHED:
            return self.model_copy(update={
                "user_input": None,
                "user_input_hash": _hash_content(self.user_input) if self.user_input else None,
            })
        else:  # DELTAS_ONLY
            return self.model_copy(update={
                "user_input": None,
                "user_input_hash": None,
            })


class FidelityCalculatedEvent(BaseEvent):
    """Records a fidelity calculation with full governance context."""
    event_type: EventType = EventType.FIDELITY_CALCULATED
    turn_number: int

    # Raw metrics
    raw_similarity: float  # Cosine similarity before normalization
    normalized_fidelity: float  # After display normalization

    # Two-layer system results
    layer1_hard_block: bool  # raw_similarity < SIMILARITY_BASELINE (0.35)
    layer2_outside_basin: bool  # normalized_fidelity < INTERVENTION_THRESHOLD (0.48)

    # Display zone
    fidelity_zone: FidelityZone

    # PA context
    distance_from_pa: float
    in_basin: bool

    # Previous turn comparison (for delta tracking)
    previous_fidelity: Optional[float] = None
    fidelity_delta: Optional[float] = None  # current - previous


class InterventionTriggeredEvent(BaseEvent):
    """Records when governance intervention is triggered."""
    event_type: EventType = EventType.INTERVENTION_TRIGGERED
    turn_number: int

    # Intervention details
    intervention_level: InterventionLevel
    trigger_reason: str  # "hard_block", "basin_exit", "drift_detected"

    # Fidelity at trigger
    fidelity_at_trigger: float

    # Controller output
    controller_strength: float  # 0.0 to 1.0

    # Semantic interpretation band
    semantic_band: str  # "minimal", "light", "moderate", "firm", "strong"

    # What action was taken
    action_taken: str  # "context_injection", "regeneration", "block", "human_review"


class ResponseGeneratedEvent(BaseEvent):
    """Records response generation details."""
    event_type: EventType = EventType.RESPONSE_GENERATED
    turn_number: int

    # Response metadata
    response_source: str  # "native", "governed", "steward"
    response_length: int
    response_hash: Optional[str] = None
    response_content: Optional[str] = None  # Only in FULL mode

    # Generation metrics
    generation_time_ms: int
    tokens_generated: Optional[int] = None

    # Post-response fidelity
    response_fidelity: Optional[float] = None

    # Output governance fields (post-LLM response fidelity scoring)
    output_governance_scored: bool = False
    output_raw_similarity: Optional[float] = None
    output_normalized_fidelity: Optional[float] = None
    output_fidelity_zone: Optional[str] = None  # GREEN/YELLOW/ORANGE/RED
    output_in_basin: Optional[bool] = None
    output_would_suppress: Optional[bool] = None

    def apply_privacy(self, mode: PrivacyMode) -> "ResponseGeneratedEvent":
        """Apply privacy mode to this event."""
        if mode == PrivacyMode.FULL:
            return self
        elif mode == PrivacyMode.HASHED:
            return self.model_copy(update={
                "response_content": None,
                "response_hash": _hash_content(self.response_content) if self.response_content else None,
            })
        else:  # DELTAS_ONLY
            return self.model_copy(update={
                "response_content": None,
                "response_hash": None,
            })


class TurnCompleteEvent(BaseEvent):
    """Marks the completion of a conversation turn."""
    event_type: EventType = EventType.TURN_COMPLETE
    turn_number: int

    # Summary metrics
    final_fidelity: float
    intervention_applied: bool
    intervention_level: Optional[InterventionLevel] = None
    turn_duration_ms: int


# ============================================================================
# SSE Streaming Events
# ============================================================================

class SSETokenEvent(BaseEvent):
    """Records individual token generation during streaming."""
    event_type: EventType = EventType.SSE_TOKEN
    turn_number: int

    # Token details
    token_index: int
    token_content: Optional[str] = None  # Only in FULL mode
    token_hash: Optional[str] = None

    # Timing
    delta_ms: int  # Time since last token
    cumulative_ms: int  # Time since stream start

    def apply_privacy(self, mode: PrivacyMode) -> "SSETokenEvent":
        """Apply privacy mode to this event."""
        if mode == PrivacyMode.FULL:
            return self
        elif mode == PrivacyMode.HASHED:
            return self.model_copy(update={
                "token_content": None,
                "token_hash": _hash_content(self.token_content) if self.token_content else None,
            })
        else:  # DELTAS_ONLY - minimal token tracking
            return self.model_copy(update={
                "token_content": None,
                "token_hash": None,
            })


class SSEGovernanceEvent(BaseEvent):
    """Records mid-stream governance decisions during streaming."""
    event_type: EventType = EventType.SSE_GOVERNANCE
    turn_number: int

    # Position in stream
    token_index: int
    cumulative_ms: int

    # Governance decision
    decision_type: str  # "fidelity_check", "intervention", "continue"
    fidelity_snapshot: float
    intervention_triggered: bool

    # Details
    details: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Summary Events
# ============================================================================

class SessionSummaryEvent(BaseEvent):
    """AI-generated session summary."""
    event_type: EventType = EventType.SESSION_SUMMARY

    # AI-generated content
    title: str
    description: str
    key_topics: List[str]

    # Governance summary
    fidelity_trajectory: str  # "stable", "improving", "degrading", "volatile"
    intervention_pattern: str  # "none", "occasional", "frequent", "constant"

    # Statistics
    stats: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# SAAI Framework Events
# ============================================================================
# Per Safer Agentic AI (SAAI) Framework by Dr. Nell Watson and Ali Hessami
# These events support mandatory review requirements and tiered response

class BaselineEstablishedEvent(BaseEvent):
    """
    Records when baseline fidelity is established for SAAI drift detection.

    After PA formation, the first N turns establish what "normal operation"
    looks like for this session. Drift is measured relative to this baseline.
    """
    event_type: EventType = EventType.BASELINE_ESTABLISHED

    # Baseline configuration
    baseline_turn_count: int  # Number of turns used to establish baseline

    # Computed baseline
    baseline_fidelity: float  # Average fidelity over baseline period
    baseline_min: float  # Minimum fidelity during baseline
    baseline_max: float  # Maximum fidelity during baseline
    baseline_std: float  # Standard deviation during baseline

    # Status
    is_stable: bool  # All baseline turns were >= INTERVENTION_THRESHOLD


class MandatoryReviewTriggeredEvent(BaseEvent):
    """
    Records when SAAI mandatory review threshold is crossed.

    Per SAAI Framework: "If behavior strays more than 10% away from
    original programming, triggers mandatory review"

    TELOS implements tiered response:
    - WARNING (10-15%): Log event, notify operator
    - RESTRICT (15-20%): Tighten enforcement thresholds
    - BLOCK (>20%): Halt until human acknowledgment
    """
    event_type: EventType = EventType.MANDATORY_REVIEW_TRIGGERED
    turn_number: int

    # Drift measurement
    drift_level: DriftLevel  # WARNING, RESTRICT, or BLOCK
    drift_magnitude: float  # Actual drift percentage (0.0-1.0)
    baseline_fidelity: float  # Reference baseline
    current_average: float  # Current session average fidelity

    # Threshold crossed
    threshold_crossed: float  # Which threshold was breached (0.10, 0.15, 0.20)

    # Action taken
    action_taken: str  # "operator_notified", "thresholds_tightened", "responses_blocked"

    # State
    previous_drift_level: Optional[DriftLevel] = None  # For tracking escalation
    requires_acknowledgment: bool = False  # True for BLOCK level


# ============================================================================
# Utility Functions
# ============================================================================

def _hash_content(content: Optional[str]) -> Optional[str]:
    """Create SHA-256 hash of content for privacy mode."""
    if content is None:
        return None
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]  # Truncated for readability


def fidelity_to_zone(fidelity: float) -> FidelityZone:
    """Convert fidelity score to display zone."""
    if fidelity >= 0.70:
        return FidelityZone.GREEN
    elif fidelity >= 0.60:
        return FidelityZone.YELLOW
    elif fidelity >= 0.50:
        return FidelityZone.ORANGE
    else:
        return FidelityZone.RED


def serialize_event(event: BaseEvent) -> str:
    """Serialize event to JSON string for JSONL output."""
    return event.model_dump_json()


def deserialize_event(json_str: str) -> BaseEvent:
    """Deserialize JSON string to appropriate event type."""
    data = json.loads(json_str)
    event_type = data.get("event_type")

    event_classes = {
        EventType.SESSION_START.value: SessionStartEvent,
        EventType.PA_ESTABLISHED.value: PAEstablishedEvent,
        EventType.SESSION_END.value: SessionEndEvent,
        EventType.TURN_START.value: TurnStartEvent,
        EventType.FIDELITY_CALCULATED.value: FidelityCalculatedEvent,
        EventType.INTERVENTION_TRIGGERED.value: InterventionTriggeredEvent,
        EventType.RESPONSE_GENERATED.value: ResponseGeneratedEvent,
        EventType.TURN_COMPLETE.value: TurnCompleteEvent,
        EventType.SSE_TOKEN.value: SSETokenEvent,
        EventType.SSE_GOVERNANCE.value: SSEGovernanceEvent,
        EventType.SESSION_SUMMARY.value: SessionSummaryEvent,
        # SAAI Framework Events
        EventType.BASELINE_ESTABLISHED.value: BaselineEstablishedEvent,
        EventType.MANDATORY_REVIEW_TRIGGERED.value: MandatoryReviewTriggeredEvent,
    }

    event_class = event_classes.get(event_type, BaseEvent)
    return event_class.model_validate(data)


# ============================================================================
# Type Aliases for External Use
# ============================================================================

GovernanceEvent = Union[
    SessionStartEvent,
    PAEstablishedEvent,
    SessionEndEvent,
    TurnStartEvent,
    FidelityCalculatedEvent,
    InterventionTriggeredEvent,
    ResponseGeneratedEvent,
    TurnCompleteEvent,
    SSETokenEvent,
    SSEGovernanceEvent,
    SessionSummaryEvent,
    # SAAI Framework Events
    BaselineEstablishedEvent,
    MandatoryReviewTriggeredEvent,
]

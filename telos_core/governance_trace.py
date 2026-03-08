"""
Governance Trace Collector for TELOS
=====================================

Central coordinator for all governance event logging.
Manages JSONL persistence with configurable privacy modes.

This is the single source of truth for governance observability data,
integrating fidelity calculations, interventions, and SSE streaming.

SAAI Framework Integration (January 2026):
- Cryptographic hash chain for tamper-evident audit trails
- 10% cumulative drift threshold with tiered response
- Baseline fidelity capture for drift detection
"""

import hashlib
import json
import logging
import statistics
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from telos_core.time_utils import utc_now

from telos_core.evidence_schema import (
    BaseEvent,
    BaselineEstablishedEvent,
    DriftLevel,
    EventType,
    FidelityCalculatedEvent,
    FidelityZone,
    GovernanceEvent,
    InterventionLevel,
    InterventionTriggeredEvent,
    MandatoryReviewTriggeredEvent,
    PAEstablishedEvent,
    PrivacyMode,
    ResponseGeneratedEvent,
    SessionEndEvent,
    SessionStartEvent,
    SessionSummaryEvent,
    SSEGovernanceEvent,
    SSETokenEvent,
    TurnCompleteEvent,
    TurnStartEvent,
    fidelity_to_zone,
    serialize_event,
)

from telos_core.constants import (
    BASELINE_TURN_COUNT,
    INTERVENTION_THRESHOLD,
    SAAI_DRIFT_BLOCK,
    SAAI_DRIFT_RESTRICT,
    SAAI_DRIFT_WARNING,
)

logger = logging.getLogger(__name__)


class GovernanceTraceCollector:
    """
    Central coordinator for governance event logging.

    Responsibilities:
    1. Collect events from various TELOS components
    2. Apply privacy mode transformations
    3. Persist to JSONL files
    4. Provide query interface for UI components
    5. Support real-time event callbacks for live visualization
    """

    def __init__(
        self,
        session_id: str,
        storage_dir: Optional[Path] = None,
        privacy_mode: PrivacyMode = PrivacyMode.DELTAS_ONLY,
    ):
        """
        Initialize Governance Trace Collector.

        Args:
            session_id: Unique session identifier
            storage_dir: Directory for JSONL files (default: ./telos_governance_traces)
            privacy_mode: Privacy level for data logging (default: deltas_only for safety)
        """
        self.session_id = session_id
        self.privacy_mode = privacy_mode
        self.storage_dir = storage_dir or Path("./telos_governance_traces")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Session file path
        timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
        self.trace_file = self.storage_dir / f"session_{session_id}_{timestamp}.jsonl"

        # In-memory event cache for queries
        self._events: List[GovernanceEvent] = []
        self._lock = threading.Lock()

        # Real-time event callbacks
        self._callbacks: List[Callable[[GovernanceEvent], None]] = []

        # Session state
        self._session_started = False
        self._current_turn = 0
        self._intervention_count = 0
        self._fidelity_sum = 0.0
        self._fidelity_count = 0

        # =====================================================================
        # SAAI Framework State - Cryptographic Hash Chain
        # =====================================================================
        # Per SAAI requirement: "Cryptographic integrity for audit trails"
        # Each event includes hash of previous event, creating tamper-evident chain
        self._last_hash: str = "0" * 64  # Genesis hash (all zeros)

        # =====================================================================
        # SAAI Framework State - Baseline & Drift Detection
        # =====================================================================
        # Per SAAI requirement: "If behavior strays more than 10% away from
        # original programming, triggers mandatory review"
        self._baseline_fidelities: List[float] = []  # First N turn fidelities
        self._baseline_fidelity: Optional[float] = None  # Computed baseline average
        self._baseline_std: float = 0.0
        self._baseline_established: bool = False
        self._ewma: Optional[float] = None
        self._drift_level: DriftLevel = DriftLevel.NORMAL
        self._drift_acknowledged: bool = False  # For BLOCK level recovery
        self._mandatory_review_count: int = 0

        logger.info(
            f"GovernanceTraceCollector initialized: session={session_id}, "
            f"privacy_mode={privacy_mode.value}, file={self.trace_file}, "
            f"SAAI_drift_thresholds=[{SAAI_DRIFT_WARNING}, {SAAI_DRIFT_RESTRICT}, {SAAI_DRIFT_BLOCK}]"
        )

    # =========================================================================
    # Privacy Mode Management
    # =========================================================================

    def set_privacy_mode(self, mode: PrivacyMode) -> None:
        """
        Change privacy mode.

        Warning: This affects future events only. Past events retain their
        original privacy settings.
        """
        old_mode = self.privacy_mode
        self.privacy_mode = mode
        logger.info(f"Privacy mode changed: {old_mode.value} -> {mode.value}")

    def _apply_privacy(self, event: GovernanceEvent) -> GovernanceEvent:
        """Apply privacy transformation to event before logging."""
        if hasattr(event, 'apply_privacy'):
            return event.apply_privacy(self.privacy_mode)
        return event

    # =========================================================================
    # Session Lifecycle Events
    # =========================================================================

    def start_session(
        self,
        telos_version: str = "v3",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        enforcement_mode: str = "enforcement",
    ) -> SessionStartEvent:
        """Record session start."""
        event = SessionStartEvent(
            session_id=self.session_id,
            privacy_mode=self.privacy_mode,
            telos_version=telos_version,
            embedding_model=embedding_model,
            enforcement_mode=enforcement_mode,
        )
        self._write_event(event)
        self._session_started = True
        return event

    def record_pa_established(
        self,
        pa_template: str,
        purpose_statement: Optional[str] = None,
        scope_statement: Optional[str] = None,
        tau: float = 0.5,
        rigidity: float = 0.5,
        basin_radius: float = 2.0,
    ) -> PAEstablishedEvent:
        """Record Primacy Attractor establishment."""
        event = PAEstablishedEvent(
            session_id=self.session_id,
            pa_template=pa_template,
            purpose_statement=purpose_statement,
            scope_statement=scope_statement,
            tau=tau,
            rigidity=rigidity,
            basin_radius=basin_radius,
        )
        event = self._apply_privacy(event)
        self._write_event(event)
        return event

    def end_session(
        self,
        duration_seconds: float,
        end_reason: str = "user_ended",
    ) -> SessionEndEvent:
        """Record session end with summary statistics."""
        avg_fidelity = (
            self._fidelity_sum / self._fidelity_count
            if self._fidelity_count > 0
            else 0.0
        )

        event = SessionEndEvent(
            session_id=self.session_id,
            total_turns=self._current_turn,
            total_interventions=self._intervention_count,
            average_fidelity=avg_fidelity,
            duration_seconds=duration_seconds,
            end_reason=end_reason,
        )
        self._write_event(event)
        self._session_started = False
        return event

    # =========================================================================
    # Turn Events
    # =========================================================================

    def start_turn(
        self,
        turn_number: int,
        user_input: Optional[str] = None,
    ) -> TurnStartEvent:
        """Record turn start."""
        self._current_turn = turn_number

        event = TurnStartEvent(
            session_id=self.session_id,
            turn_number=turn_number,
            user_input=user_input,
            user_input_length=len(user_input) if user_input else 0,
        )
        event = self._apply_privacy(event)
        self._write_event(event)
        return event

    def record_fidelity(
        self,
        turn_number: int,
        raw_similarity: float,
        normalized_fidelity: float,
        layer1_hard_block: bool,
        layer2_outside_basin: bool,
        distance_from_pa: float,
        in_basin: bool,
        previous_fidelity: Optional[float] = None,
    ) -> FidelityCalculatedEvent:
        """
        Record fidelity calculation with full governance context.

        SAAI Integration:
        - Collects first N turns for baseline establishment
        - After baseline, computes cumulative drift
        - Triggers mandatory review events per SAAI tiered response
        """
        fidelity_delta = None
        if previous_fidelity is not None:
            fidelity_delta = normalized_fidelity - previous_fidelity

        event = FidelityCalculatedEvent(
            session_id=self.session_id,
            turn_number=turn_number,
            raw_similarity=raw_similarity,
            normalized_fidelity=normalized_fidelity,
            layer1_hard_block=layer1_hard_block,
            layer2_outside_basin=layer2_outside_basin,
            fidelity_zone=fidelity_to_zone(normalized_fidelity),
            distance_from_pa=distance_from_pa,
            in_basin=in_basin,
            previous_fidelity=previous_fidelity,
            fidelity_delta=fidelity_delta,
        )
        self._write_event(event)

        # Update session stats
        self._fidelity_sum += normalized_fidelity
        self._fidelity_count += 1

        # =====================================================================
        # SAAI Framework: Baseline Capture & Drift Detection
        # =====================================================================
        self._saai_process_fidelity(turn_number, normalized_fidelity)

        return event

    def _saai_process_fidelity(self, turn_number: int, fidelity: float) -> None:
        """
        SAAI Framework processing for each fidelity measurement.

        Phase 1 (turns 1-N): Collect baseline fidelities (with CV stability gate)
        Phase 2 (after baseline): EWMA drift detection
        """
        if not self._baseline_established:
            self._baseline_fidelities.append(fidelity)
            if len(self._baseline_fidelities) >= BASELINE_TURN_COUNT:
                self._establish_baseline()
            return

        # Phase 2: EWMA drift detection
        self._update_ewma_and_check_drift(turn_number, fidelity)

    def _establish_baseline(self) -> None:
        """
        Establish baseline fidelity from collected initial turns.

        Includes CV stability gate: if coefficient of variation exceeds
        SAAI_BASELINE_CV_MAX, baseline is not established and collection
        continues until stable.

        Records BaselineEstablishedEvent for audit trail.
        """
        from telos_core.constants import SAAI_BASELINE_CV_MAX, EPSILON_NUMERICAL

        if not self._baseline_fidelities:
            logger.warning("Cannot establish baseline: no fidelity data")
            return

        self._baseline_fidelity = statistics.mean(self._baseline_fidelities)
        baseline_min = min(self._baseline_fidelities)
        baseline_max = max(self._baseline_fidelities)
        self._baseline_std = statistics.stdev(self._baseline_fidelities) if len(self._baseline_fidelities) > 1 else 0.0

        # Stability gate: reject baseline if CV too high
        cv = self._baseline_std / self._baseline_fidelity if self._baseline_fidelity > EPSILON_NUMERICAL else 1.0
        if cv > SAAI_BASELINE_CV_MAX:
            logger.info(
                f"SAAI Baseline CV too high ({cv:.3f} > {SAAI_BASELINE_CV_MAX}), "
                f"extending baseline collection"
            )
            return  # Don't establish — keep collecting

        # Check if baseline is stable (all turns above intervention threshold)
        is_stable = all(f >= INTERVENTION_THRESHOLD for f in self._baseline_fidelities)
        self._baseline_established = True
        self._ewma = self._baseline_fidelity  # Initialize EWMA

        baseline_event = BaselineEstablishedEvent(
            session_id=self.session_id,
            baseline_turn_count=len(self._baseline_fidelities),
            baseline_fidelity=self._baseline_fidelity,
            baseline_min=baseline_min,
            baseline_max=baseline_max,
            baseline_std=self._baseline_std,
            is_stable=is_stable,
        )
        self._write_event(baseline_event)

        logger.info(
            f"SAAI Baseline established: fidelity={self._baseline_fidelity:.3f}, "
            f"range=[{baseline_min:.3f}, {baseline_max:.3f}], CV={cv:.3f}, stable={is_stable}"
        )

    def _update_ewma_and_check_drift(self, turn_number: int, fidelity: float) -> None:
        """EWMA-based drift detection (replaces session-average method).

        Updates the exponentially weighted moving average and checks
        drift against SAAI thresholds.
        """
        from telos_core.constants import (
            SAAI_EWMA_SPAN, SAAI_DRIFT_WARNING, SAAI_DRIFT_RESTRICT,
            SAAI_DRIFT_BLOCK, EPSILON_NUMERICAL,
        )

        if not self._baseline_established or self._baseline_fidelity is None:
            return
        if self._baseline_fidelity <= 0:
            return

        # Update EWMA
        lam = 2.0 / (SAAI_EWMA_SPAN + 1)
        self._ewma = lam * fidelity + (1 - lam) * self._ewma

        # Compute drift
        drift_magnitude = max(
            0.0,
            (self._baseline_fidelity - self._ewma) / (self._baseline_fidelity + EPSILON_NUMERICAL),
        )

        new_drift_level = self._compute_drift_level(drift_magnitude)

        if self._should_trigger_review(new_drift_level):
            self._trigger_mandatory_review(
                turn_number=turn_number,
                new_level=new_drift_level,
                drift_magnitude=drift_magnitude,
                current_avg=self._ewma,
            )

    def _compute_drift_level(self, drift_magnitude: float) -> DriftLevel:
        """Compute drift level from magnitude."""
        if drift_magnitude >= SAAI_DRIFT_BLOCK:
            return DriftLevel.BLOCK
        elif drift_magnitude >= SAAI_DRIFT_RESTRICT:
            return DriftLevel.RESTRICT
        elif drift_magnitude >= SAAI_DRIFT_WARNING:
            return DriftLevel.WARNING
        else:
            return DriftLevel.NORMAL

    def _should_trigger_review(self, new_level: DriftLevel) -> bool:
        """Check if we should trigger a new mandatory review event."""
        # Only trigger if drift level is worse than current
        level_order = {
            DriftLevel.NORMAL: 0,
            DriftLevel.WARNING: 1,
            DriftLevel.RESTRICT: 2,
            DriftLevel.BLOCK: 3,
        }

        current_order = level_order.get(self._drift_level, 0)
        new_order = level_order.get(new_level, 0)

        return new_order > current_order

    def _trigger_mandatory_review(
        self,
        turn_number: int,
        new_level: DriftLevel,
        drift_magnitude: float,
        current_avg: float,
    ) -> None:
        """
        Trigger SAAI mandatory review event with tiered response.

        Per SAAI Framework:
        - WARNING: Log and notify operator
        - RESTRICT: Tighten enforcement thresholds
        - BLOCK: Halt until human acknowledgment
        """
        previous_level = self._drift_level
        self._drift_level = new_level
        self._mandatory_review_count += 1

        # Determine threshold crossed
        if new_level == DriftLevel.BLOCK:
            threshold_crossed = SAAI_DRIFT_BLOCK
            action_taken = "responses_blocked"
        elif new_level == DriftLevel.RESTRICT:
            threshold_crossed = SAAI_DRIFT_RESTRICT
            action_taken = "thresholds_tightened"
        else:  # WARNING
            threshold_crossed = SAAI_DRIFT_WARNING
            action_taken = "operator_notified"

        # Record mandatory review event
        review_event = MandatoryReviewTriggeredEvent(
            session_id=self.session_id,
            turn_number=turn_number,
            drift_level=new_level,
            drift_magnitude=drift_magnitude,
            baseline_fidelity=self._baseline_fidelity,
            current_average=current_avg,
            threshold_crossed=threshold_crossed,
            action_taken=action_taken,
            previous_drift_level=previous_level if previous_level != DriftLevel.NORMAL else None,
            requires_acknowledgment=(new_level == DriftLevel.BLOCK),
        )
        self._write_event(review_event)

        logger.warning(
            f"SAAI MANDATORY REVIEW TRIGGERED: level={new_level.value}, "
            f"drift={drift_magnitude:.1%}, baseline={self._baseline_fidelity:.3f}, "
            f"current_avg={current_avg:.3f}, action={action_taken}"
        )

    def record_intervention(
        self,
        turn_number: int,
        intervention_level: InterventionLevel,
        trigger_reason: str,
        fidelity_at_trigger: float,
        controller_strength: float,
        semantic_band: str,
        action_taken: str,
    ) -> InterventionTriggeredEvent:
        """Record governance intervention."""
        event = InterventionTriggeredEvent(
            session_id=self.session_id,
            turn_number=turn_number,
            intervention_level=intervention_level,
            trigger_reason=trigger_reason,
            fidelity_at_trigger=fidelity_at_trigger,
            controller_strength=controller_strength,
            semantic_band=semantic_band,
            action_taken=action_taken,
        )
        self._write_event(event)

        # Update session stats
        self._intervention_count += 1

        return event

    def record_response(
        self,
        turn_number: int,
        response_source: str,
        response_content: Optional[str] = None,
        generation_time_ms: int = 0,
        tokens_generated: Optional[int] = None,
        response_fidelity: Optional[float] = None,
        output_governance_scored: bool = False,
        output_raw_similarity: Optional[float] = None,
        output_normalized_fidelity: Optional[float] = None,
        output_fidelity_zone: Optional[str] = None,
        output_in_basin: Optional[bool] = None,
        output_would_suppress: Optional[bool] = None,
    ) -> ResponseGeneratedEvent:
        """Record response generation."""
        event = ResponseGeneratedEvent(
            session_id=self.session_id,
            turn_number=turn_number,
            response_source=response_source,
            response_length=len(response_content) if response_content else 0,
            response_content=response_content,
            generation_time_ms=generation_time_ms,
            tokens_generated=tokens_generated,
            response_fidelity=response_fidelity,
            output_governance_scored=output_governance_scored,
            output_raw_similarity=output_raw_similarity,
            output_normalized_fidelity=output_normalized_fidelity,
            output_fidelity_zone=output_fidelity_zone,
            output_in_basin=output_in_basin,
            output_would_suppress=output_would_suppress,
        )
        event = self._apply_privacy(event)
        self._write_event(event)
        return event

    def complete_turn(
        self,
        turn_number: int,
        final_fidelity: float,
        intervention_applied: bool,
        intervention_level: Optional[InterventionLevel] = None,
        turn_duration_ms: int = 0,
    ) -> TurnCompleteEvent:
        """Record turn completion."""
        event = TurnCompleteEvent(
            session_id=self.session_id,
            turn_number=turn_number,
            final_fidelity=final_fidelity,
            intervention_applied=intervention_applied,
            intervention_level=intervention_level,
            turn_duration_ms=turn_duration_ms,
        )
        self._write_event(event)
        return event

    # =========================================================================
    # SSE Streaming Events
    # =========================================================================

    def record_sse_token(
        self,
        turn_number: int,
        token_index: int,
        token_content: Optional[str] = None,
        delta_ms: int = 0,
        cumulative_ms: int = 0,
    ) -> SSETokenEvent:
        """Record individual token during streaming."""
        event = SSETokenEvent(
            session_id=self.session_id,
            turn_number=turn_number,
            token_index=token_index,
            token_content=token_content,
            delta_ms=delta_ms,
            cumulative_ms=cumulative_ms,
        )
        event = self._apply_privacy(event)
        self._write_event(event)
        return event

    def record_sse_governance(
        self,
        turn_number: int,
        token_index: int,
        cumulative_ms: int,
        decision_type: str,
        fidelity_snapshot: float,
        intervention_triggered: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> SSEGovernanceEvent:
        """Record mid-stream governance decision."""
        event = SSEGovernanceEvent(
            session_id=self.session_id,
            turn_number=turn_number,
            token_index=token_index,
            cumulative_ms=cumulative_ms,
            decision_type=decision_type,
            fidelity_snapshot=fidelity_snapshot,
            intervention_triggered=intervention_triggered,
            details=details or {},
        )
        self._write_event(event)
        return event

    # =========================================================================
    # Summary Events
    # =========================================================================

    def record_session_summary(
        self,
        title: str,
        description: str,
        key_topics: List[str],
        fidelity_trajectory: str,
        intervention_pattern: str,
        stats: Optional[Dict[str, Any]] = None,
    ) -> SessionSummaryEvent:
        """Record AI-generated session summary."""
        event = SessionSummaryEvent(
            session_id=self.session_id,
            title=title,
            description=description,
            key_topics=key_topics,
            fidelity_trajectory=fidelity_trajectory,
            intervention_pattern=intervention_pattern,
            stats=stats or {},
        )
        self._write_event(event)
        return event

    # =========================================================================
    # Real-time Callbacks
    # =========================================================================

    def add_callback(self, callback: Callable[[GovernanceEvent], None]) -> None:
        """Add callback for real-time event notifications."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[GovernanceEvent], None]) -> None:
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self, event: GovernanceEvent) -> None:
        """Notify all registered callbacks of new event."""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"Callback error: {e}")

    # =========================================================================
    # Query Interface
    # =========================================================================

    def get_events(
        self,
        event_type: Optional[EventType] = None,
        turn_number: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[GovernanceEvent]:
        """
        Query events from in-memory cache.

        Args:
            event_type: Filter by event type
            turn_number: Filter by turn number
            limit: Maximum number of events to return

        Returns:
            List of matching events
        """
        with self._lock:
            events = self._events.copy()

        if event_type:
            events = [e for e in events if e.event_type == event_type.value]

        if turn_number is not None:
            events = [
                e for e in events
                if hasattr(e, 'turn_number') and e.turn_number == turn_number
            ]

        if limit:
            events = events[-limit:]

        return events

    def get_fidelity_trajectory(self) -> List[Dict[str, Any]]:
        """Get fidelity scores over time for visualization."""
        events = self.get_events(event_type=EventType.FIDELITY_CALCULATED)
        return [
            {
                "turn": e.turn_number,
                "fidelity": e.normalized_fidelity,
                "zone": e.fidelity_zone.value if hasattr(e.fidelity_zone, 'value') else e.fidelity_zone,
                "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, 'isoformat') else str(e.timestamp),
            }
            for e in events
        ]

    def get_interventions(self) -> List[Dict[str, Any]]:
        """Get all interventions for dashboard display."""
        events = self.get_events(event_type=EventType.INTERVENTION_TRIGGERED)
        return [
            {
                "turn": e.turn_number,
                "level": e.intervention_level.value if hasattr(e.intervention_level, 'value') else e.intervention_level,
                "reason": e.trigger_reason,
                "fidelity": e.fidelity_at_trigger,
                "action": e.action_taken,
                "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, 'isoformat') else str(e.timestamp),
            }
            for e in events
        ]

    def get_session_stats(self) -> Dict[str, Any]:
        """Get current session statistics including SAAI compliance metrics."""
        avg_fidelity = (
            self._fidelity_sum / self._fidelity_count
            if self._fidelity_count > 0
            else 0.0
        )

        # Compute current drift if baseline established
        current_drift = None
        if self._baseline_established and self._baseline_fidelity and self._baseline_fidelity > 0:
            current_drift = (self._baseline_fidelity - avg_fidelity) / self._baseline_fidelity
            current_drift = max(0.0, current_drift)

        return {
            "session_id": self.session_id,
            "privacy_mode": self.privacy_mode.value,
            "total_turns": self._current_turn,
            "total_events": len(self._events),
            "total_interventions": self._intervention_count,
            "average_fidelity": avg_fidelity,
            "trace_file": str(self.trace_file),
            # SAAI Framework metrics
            "saai_baseline_established": self._baseline_established,
            "saai_baseline_fidelity": self._baseline_fidelity,
            "saai_current_drift": current_drift,
            "saai_drift_level": self._drift_level.value if self._drift_level else None,
            "saai_mandatory_review_count": self._mandatory_review_count,
            "saai_requires_acknowledgment": (self._drift_level == DriftLevel.BLOCK and not self._drift_acknowledged),
        }

    # =========================================================================
    # SAAI Framework Query Interface
    # =========================================================================

    def get_saai_status(self) -> Dict[str, Any]:
        """
        Get comprehensive SAAI compliance status for dashboard/API.

        Returns current drift level, baseline status, and review history.
        """
        avg_fidelity = (
            self._fidelity_sum / self._fidelity_count
            if self._fidelity_count > 0
            else 0.0
        )

        current_drift = None
        drift_percentage = None
        if self._baseline_established and self._baseline_fidelity and self._baseline_fidelity > 0:
            current_drift = (self._baseline_fidelity - avg_fidelity) / self._baseline_fidelity
            current_drift = max(0.0, current_drift)
            drift_percentage = f"{current_drift:.1%}"

        return {
            "baseline": {
                "established": self._baseline_established,
                "fidelity": self._baseline_fidelity,
                "turn_count": len(self._baseline_fidelities) if self._baseline_fidelities else 0,
            },
            "drift": {
                "level": self._drift_level.value,
                "magnitude": current_drift,
                "percentage": drift_percentage,
                "thresholds": {
                    "warning": SAAI_DRIFT_WARNING,
                    "restrict": SAAI_DRIFT_RESTRICT,
                    "block": SAAI_DRIFT_BLOCK,
                },
            },
            "review": {
                "count": self._mandatory_review_count,
                "requires_acknowledgment": (self._drift_level == DriftLevel.BLOCK and not self._drift_acknowledged),
                "acknowledged": self._drift_acknowledged,
            },
            "compliance": {
                "hash_chain_active": True,
                "baseline_monitoring_active": self._baseline_established,
            },
        }

    def acknowledge_drift(self) -> bool:
        """
        Acknowledge a BLOCK-level drift for human review.

        Per SAAI: At BLOCK level, human acknowledgment is required
        to resume operation.

        Returns:
            True if acknowledgment was needed and processed,
            False if no acknowledgment was needed.
        """
        if self._drift_level == DriftLevel.BLOCK and not self._drift_acknowledged:
            self._drift_acknowledged = True
            logger.info("SAAI drift BLOCK level acknowledged by operator")
            return True
        return False

    def is_response_blocked(self) -> bool:
        """
        Check if responses should be blocked due to SAAI drift level.

        Returns:
            True if drift is at BLOCK level and not yet acknowledged.
        """
        return self._drift_level == DriftLevel.BLOCK and not self._drift_acknowledged

    def get_current_drift_level(self) -> DriftLevel:
        """Get current SAAI drift level."""
        return self._drift_level

    # =========================================================================
    # Persistence
    # =========================================================================

    def _write_event(self, event: GovernanceEvent) -> None:
        """
        Write event to JSONL file and in-memory cache with cryptographic hash chain.

        SAAI Compliance: Each event includes:
        - previous_hash: Hash of the previous event (genesis = "0"*64)
        - event_hash: SHA-256 hash of (previous_hash + serialized_event)

        This creates a tamper-evident chain where modification of any event
        breaks the hash chain for all subsequent events.
        """
        with self._lock:
            # Add to cache
            self._events.append(event)

            # Serialize event to JSON
            event_json = serialize_event(event)
            event_dict = json.loads(event_json)

            # Add hash chain fields (SAAI cryptographic integrity)
            event_dict["previous_hash"] = self._last_hash

            # Compute hash of: previous_hash + sorted event content
            # Sort keys for deterministic hashing
            hash_content = self._last_hash + json.dumps(event_dict, sort_keys=True)
            event_hash = hashlib.sha256(hash_content.encode('utf-8')).hexdigest()
            event_dict["event_hash"] = event_hash

            # Update chain for next event
            self._last_hash = event_hash

            # Write to file with hash chain
            try:
                with open(self.trace_file, 'a') as f:
                    f.write(json.dumps(event_dict) + '\n')
            except Exception as e:
                logger.error(f"Failed to write event to {self.trace_file}: {e}")

        # Notify callbacks
        self._notify_callbacks(event)

    def load_session(self, trace_file: Path) -> None:
        """
        Load events from an existing trace file into memory.

        Args:
            trace_file: Path to JSONL trace file
        """
        from telos_core.evidence_schema import deserialize_event

        with self._lock:
            self._events.clear()

            try:
                with open(trace_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            event = deserialize_event(line)
                            self._events.append(event)

                logger.info(f"Loaded {len(self._events)} events from {trace_file}")

            except Exception as e:
                logger.error(f"Failed to load trace file {trace_file}: {e}")
                raise

    def export_to_dict(self) -> Dict[str, Any]:
        """Export session data as dictionary for report generation."""
        return {
            "session_id": self.session_id,
            "privacy_mode": self.privacy_mode.value,
            "stats": self.get_session_stats(),
            "fidelity_trajectory": self.get_fidelity_trajectory(),
            "interventions": self.get_interventions(),
            "events": [
                json.loads(serialize_event(e))
                for e in self._events
            ],
        }


# ============================================================================
# Singleton Access Pattern
# ============================================================================

_collector_instance: Optional[GovernanceTraceCollector] = None


def get_trace_collector(
    session_id: Optional[str] = None,
    storage_dir: Optional[Path] = None,
    privacy_mode: PrivacyMode = PrivacyMode.DELTAS_ONLY,
) -> GovernanceTraceCollector:
    """
    Get or create the global GovernanceTraceCollector instance.

    Args:
        session_id: Session ID (required for first call)
        storage_dir: Optional storage directory
        privacy_mode: Privacy mode for logging

    Returns:
        GovernanceTraceCollector instance
    """
    global _collector_instance

    if _collector_instance is None:
        if session_id is None:
            raise ValueError("session_id required for first call to get_trace_collector")
        _collector_instance = GovernanceTraceCollector(
            session_id=session_id,
            storage_dir=storage_dir,
            privacy_mode=privacy_mode,
        )

    return _collector_instance


def reset_trace_collector() -> None:
    """Reset the global collector (for testing or new sessions)."""
    global _collector_instance
    _collector_instance = None

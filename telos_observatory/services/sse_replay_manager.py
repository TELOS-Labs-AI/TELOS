"""
SSE Replay Manager for TELOSCOPE
=================================

Enhances TELOSCOPE with streaming replay capabilities to show HOW responses
were generated, not just WHAT was generated.

Key Features:
- Preserves original timing and token generation patterns
- Shows mid-stream governance interventions
- Visualizes token-by-token fidelity calculations
- Complements existing turn-based replay
"""

import json
import time
import asyncio
from typing import Dict, Any, List, Optional, Generator, Tuple, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class SSEEvent:
    """Single Server-Sent Event with timing and content."""
    event_type: str  # 'token', 'governance', 'intervention', 'completion'
    timestamp: float  # Unix timestamp
    delta_ms: int  # Time since last event (milliseconds)
    content: str  # Token text or governance data
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamingSession:
    """Complete streaming session with all SSE events."""
    session_id: str
    turn_number: int
    events: List[SSEEvent]
    total_duration_ms: int
    token_count: int
    intervention_points: List[int]  # Indices where interventions occurred
    governance_decisions: List[Dict[str, Any]]

    @property
    def tokens_per_second(self) -> float:
        """Calculate average token generation rate."""
        if self.total_duration_ms == 0:
            return 0.0
        return (self.token_count * 1000) / self.total_duration_ms

    @property
    def time_to_first_token(self) -> int:
        """Get time to first token in milliseconds."""
        for event in self.events:
            if event.event_type == 'token':
                return event.delta_ms
        return 0


class SSEReplayManager:
    """
    Manages SSE replay functionality for TELOSCOPE.

    This component:
    1. Stores SSE events during live generation
    2. Replays events with original timing
    3. Provides streaming visualization hooks
    4. Integrates with governance trace system
    """

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        enable_trace_collector: bool = True,
    ):
        """
        Initialize SSE Replay Manager.

        Args:
            storage_dir: Directory for JSONL persistence (optional)
            enable_trace_collector: Whether to send events to GovernanceTraceCollector
        """
        self.storage_dir = storage_dir or Path("/tmp/telos_sse_replay")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache of streaming sessions
        self._sessions: Dict[Tuple[str, int], StreamingSession] = {}

        # Current recording state
        self._recording: bool = False
        self._current_session: Optional[StreamingSession] = None
        self._start_time: Optional[float] = None
        self._last_event_time: Optional[float] = None

        # GovernanceTraceCollector integration
        self._enable_trace_collector = enable_trace_collector
        self._trace_collector = None
        self._token_index = 0
        self._cumulative_ms = 0

    def start_recording(self, session_id: str, turn_number: int):
        """
        Start recording SSE events for a turn.

        Args:
            session_id: TELOS session identifier
            turn_number: Turn number being recorded
        """
        self._recording = True
        self._start_time = time.time()
        self._last_event_time = self._start_time
        self._token_index = 0
        self._cumulative_ms = 0

        self._current_session = StreamingSession(
            session_id=session_id,
            turn_number=turn_number,
            events=[],
            total_duration_ms=0,
            token_count=0,
            intervention_points=[],
            governance_decisions=[]
        )

        # Initialize trace collector integration
        if self._enable_trace_collector:
            try:
                from .governance_trace_collector import get_trace_collector
                self._trace_collector = get_trace_collector(session_id=session_id)
            except Exception as e:
                logger.debug(f"Trace collector not available: {e}")
                self._trace_collector = None

        logger.info(f"Started SSE recording for session {session_id}, turn {turn_number}")

    def record_token(self, token: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Record a token generation event.

        Args:
            token: The generated token text
            metadata: Optional metadata (fidelity, confidence, etc.)
        """
        if not self._recording or not self._current_session:
            return

        current_time = time.time()
        delta_ms = int((current_time - self._last_event_time) * 1000)
        self._cumulative_ms += delta_ms

        event = SSEEvent(
            event_type='token',
            timestamp=current_time,
            delta_ms=delta_ms,
            content=token,
            metadata=metadata or {}
        )

        self._current_session.events.append(event)
        self._current_session.token_count += 1
        self._last_event_time = current_time

        # Send to GovernanceTraceCollector
        if self._trace_collector:
            try:
                self._trace_collector.record_sse_token(
                    turn_number=self._current_session.turn_number,
                    token_index=self._token_index,
                    token_content=token,
                    delta_ms=delta_ms,
                    cumulative_ms=self._cumulative_ms,
                )
            except Exception as e:
                logger.debug(f"Trace collector token recording failed: {e}")

        self._token_index += 1

    def record_governance(self, decision_type: str, data: Dict[str, Any]):
        """
        Record a governance decision during streaming.

        Args:
            decision_type: Type of governance decision
            data: Governance data (fidelity, intervention level, etc.)
        """
        if not self._recording or not self._current_session:
            return

        current_time = time.time()
        delta_ms = int((current_time - self._last_event_time) * 1000)
        self._cumulative_ms += delta_ms

        event = SSEEvent(
            event_type='governance',
            timestamp=current_time,
            delta_ms=delta_ms,
            content=decision_type,
            metadata=data
        )

        self._current_session.events.append(event)
        self._current_session.governance_decisions.append(data)
        self._last_event_time = current_time

        # Track intervention points
        intervention_triggered = data.get('intervention_triggered', False)
        if intervention_triggered:
            event_index = len(self._current_session.events) - 1
            self._current_session.intervention_points.append(event_index)
            logger.info(f"Recorded intervention at event {event_index}")

        # Send to GovernanceTraceCollector
        if self._trace_collector:
            try:
                self._trace_collector.record_sse_governance(
                    turn_number=self._current_session.turn_number,
                    token_index=self._token_index,
                    cumulative_ms=self._cumulative_ms,
                    decision_type=decision_type,
                    fidelity_snapshot=data.get('fidelity', 0.0),
                    intervention_triggered=intervention_triggered,
                    details=data,
                )
            except Exception as e:
                logger.debug(f"Trace collector governance recording failed: {e}")

    def stop_recording(self) -> Optional[StreamingSession]:
        """
        Stop recording and save the session.

        Returns:
            The completed StreamingSession or None if not recording
        """
        if not self._recording or not self._current_session:
            return None

        # Calculate total duration
        end_time = time.time()
        self._current_session.total_duration_ms = int((end_time - self._start_time) * 1000)

        # Add completion event
        event = SSEEvent(
            event_type='completion',
            timestamp=end_time,
            delta_ms=0,
            content='',
            metadata={'total_tokens': self._current_session.token_count}
        )
        self._current_session.events.append(event)

        # Store in cache
        key = (self._current_session.session_id, self._current_session.turn_number)
        self._sessions[key] = self._current_session

        # Persist to JSONL
        self._persist_session(self._current_session)

        logger.info(f"Stopped SSE recording: {self._current_session.token_count} tokens in {self._current_session.total_duration_ms}ms")

        session = self._current_session
        self._recording = False
        self._current_session = None

        return session

    def replay_session(self,
                      session_id: str,
                      turn_number: int,
                      speed_multiplier: float = 1.0) -> Generator[SSEEvent, None, None]:
        """
        Replay a recorded session with original timing.

        Args:
            session_id: Session to replay
            turn_number: Turn number to replay
            speed_multiplier: Playback speed (1.0 = original, 2.0 = double speed)

        Yields:
            SSEEvent objects with proper timing delays
        """
        key = (session_id, turn_number)
        session = self._sessions.get(key)

        if not session:
            # Try to load from disk
            session = self._load_session(session_id, turn_number)
            if not session:
                logger.warning(f"No SSE session found for {session_id}, turn {turn_number}")
                return

        logger.info(f"Starting SSE replay: {session.token_count} tokens at {speed_multiplier}x speed")

        for event in session.events:
            # Apply speed multiplier to delays
            if event.delta_ms > 0 and speed_multiplier > 0:
                delay_seconds = (event.delta_ms / 1000) / speed_multiplier
                time.sleep(delay_seconds)

            yield event

    async def replay_session_async(self,
                                  session_id: str,
                                  turn_number: int,
                                  speed_multiplier: float = 1.0) -> AsyncGenerator[SSEEvent, None]:
        """
        Async version of replay for better UI integration.

        Args:
            session_id: Session to replay
            turn_number: Turn number to replay
            speed_multiplier: Playback speed

        Yields:
            SSEEvent objects with proper timing delays
        """
        key = (session_id, turn_number)
        session = self._sessions.get(key)

        if not session:
            session = self._load_session(session_id, turn_number)
            if not session:
                return

        for event in session.events:
            if event.delta_ms > 0 and speed_multiplier > 0:
                delay_seconds = (event.delta_ms / 1000) / speed_multiplier
                await asyncio.sleep(delay_seconds)

            yield event

    def get_session_metrics(self, session_id: str, turn_number: int) -> Optional[Dict[str, Any]]:
        """
        Get performance metrics for a streaming session.

        Returns:
            Dictionary with timing and performance metrics
        """
        key = (session_id, turn_number)
        session = self._sessions.get(key)

        if not session:
            session = self._load_session(session_id, turn_number)
            if not session:
                return None

        return {
            'total_tokens': session.token_count,
            'total_duration_ms': session.total_duration_ms,
            'tokens_per_second': session.tokens_per_second,
            'time_to_first_token_ms': session.time_to_first_token,
            'intervention_count': len(session.intervention_points),
            'governance_decision_count': len(session.governance_decisions),
            'average_token_delay_ms': (
                session.total_duration_ms / session.token_count
                if session.token_count > 0 else 0
            )
        }

    def export_session_timeline(self, session_id: str, turn_number: int) -> Optional[List[Dict[str, Any]]]:
        """
        Export session as timeline data for visualization.

        Returns:
            List of timeline events suitable for charting
        """
        key = (session_id, turn_number)
        session = self._sessions.get(key)

        if not session:
            session = self._load_session(session_id, turn_number)
            if not session:
                return None

        timeline = []
        cumulative_time = 0
        token_buffer = ""

        for i, event in enumerate(session.events):
            cumulative_time += event.delta_ms

            if event.event_type == 'token':
                token_buffer += event.content
                # Batch tokens into words for cleaner timeline
                if ' ' in event.content or i == len(session.events) - 1:
                    timeline.append({
                        'time_ms': cumulative_time,
                        'type': 'token_batch',
                        'content': token_buffer,
                        'metadata': event.metadata
                    })
                    token_buffer = ""

            elif event.event_type == 'governance':
                timeline.append({
                    'time_ms': cumulative_time,
                    'type': 'governance',
                    'decision': event.content,
                    'data': event.metadata
                })

            elif event.event_type == 'intervention':
                timeline.append({
                    'time_ms': cumulative_time,
                    'type': 'intervention',
                    'severity': event.metadata.get('level', 'unknown'),
                    'reason': event.metadata.get('reason', '')
                })

        return timeline

    def _persist_session(self, session: StreamingSession):
        """
        Persist session to JSONL file.

        Args:
            session: Session to persist
        """
        filename = self.storage_dir / f"{session.session_id}_turn_{session.turn_number}.jsonl"

        try:
            with open(filename, 'w') as f:
                # Write session metadata
                f.write(json.dumps({
                    'type': 'session_metadata',
                    'session_id': session.session_id,
                    'turn_number': session.turn_number,
                    'total_duration_ms': session.total_duration_ms,
                    'token_count': session.token_count,
                    'timestamp': datetime.now().isoformat()
                }) + '\n')

                # Write each event
                for event in session.events:
                    f.write(json.dumps({
                        'type': 'event',
                        'event_type': event.event_type,
                        'timestamp': event.timestamp,
                        'delta_ms': event.delta_ms,
                        'content': event.content,
                        'metadata': event.metadata
                    }) + '\n')

            logger.info(f"Persisted SSE session to {filename}")

        except Exception as e:
            logger.error(f"Failed to persist SSE session: {e}")

    def _load_session(self, session_id: str, turn_number: int) -> Optional[StreamingSession]:
        """
        Load session from JSONL file.

        Args:
            session_id: Session ID
            turn_number: Turn number

        Returns:
            StreamingSession or None if not found
        """
        filename = self.storage_dir / f"{session_id}_turn_{turn_number}.jsonl"

        if not filename.exists():
            return None

        try:
            session = None
            events = []

            with open(filename, 'r') as f:
                for line in f:
                    data = json.loads(line)

                    if data['type'] == 'session_metadata':
                        session = StreamingSession(
                            session_id=data['session_id'],
                            turn_number=data['turn_number'],
                            events=[],
                            total_duration_ms=data['total_duration_ms'],
                            token_count=data['token_count'],
                            intervention_points=[],
                            governance_decisions=[]
                        )

                    elif data['type'] == 'event':
                        event = SSEEvent(
                            event_type=data['event_type'],
                            timestamp=data['timestamp'],
                            delta_ms=data['delta_ms'],
                            content=data['content'],
                            metadata=data.get('metadata', {})
                        )
                        events.append(event)

            if session:
                session.events = events
                # Rebuild intervention points
                for i, event in enumerate(events):
                    if event.event_type == 'governance' and event.metadata.get('intervention_triggered'):
                        session.intervention_points.append(i)
                    if event.event_type == 'governance':
                        session.governance_decisions.append(event.metadata)

                # Cache it
                key = (session_id, turn_number)
                self._sessions[key] = session

                logger.info(f"Loaded SSE session from {filename}")
                return session

        except Exception as e:
            logger.error(f"Failed to load SSE session: {e}")

        return None

    def simulate_streaming(self,
                          text: str,
                          target_tps: float = 30.0,
                          variance: float = 0.2) -> Generator[SSEEvent, None, None]:
        """
        Simulate streaming for text that wasn't originally streamed.

        Args:
            text: Text to simulate streaming for
            target_tps: Target tokens per second
            variance: Random variance in timing (0.0 to 1.0)

        Yields:
            Simulated SSE events
        """
        import random

        # Tokenize roughly by words and punctuation
        import re
        tokens = re.findall(r'\S+|\s+', text)

        base_delay_ms = int(1000 / target_tps)
        current_time = time.time()

        for i, token in enumerate(tokens):
            # Add variance to delay
            variance_factor = 1 + random.uniform(-variance, variance)
            delay_ms = int(base_delay_ms * variance_factor)

            yield SSEEvent(
                event_type='token',
                timestamp=current_time,
                delta_ms=delay_ms if i > 0 else 0,
                content=token,
                metadata={'simulated': True}
            )

            current_time += delay_ms / 1000
            time.sleep(delay_ms / 1000)

        # Add completion event
        yield SSEEvent(
            event_type='completion',
            timestamp=current_time,
            delta_ms=0,
            content='',
            metadata={'simulated': True, 'total_tokens': len(tokens)}
        )


# Singleton instance for easy access
_sse_manager = None

def get_sse_manager() -> SSEReplayManager:
    """Get or create the global SSE Replay Manager instance."""
    global _sse_manager
    if _sse_manager is None:
        _sse_manager = SSEReplayManager()
    return _sse_manager
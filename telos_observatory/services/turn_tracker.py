"""
Turn Lifecycle Tracker for TELOS Observatory V3.
Progressive delta transmission as turns flow through governance pipeline.
"""

import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
import time

from telos_observatory.services.backend_client import get_backend_service


class TurnTracker:
    """
    Tracks individual turn progression through governance lifecycle.

    PRIVACY: Only collects telemetry when:
    - Beta mode active
    - User has given consent
    - TELOS governance is actively running
    """

    def __init__(self, session_id: uuid.UUID, turn_number: int, mode: str,
                 governance_active: bool = True, consent_given: bool = True):
        """
        Initialize turn tracker.

        Args:
            session_id: Current session UUID
            turn_number: Turn number in conversation
            mode: Operating mode ('demo', 'beta', 'open')
            governance_active: Is TELOS governance evaluating this turn?
            consent_given: Has user given beta consent?

        IMPORTANT: Telemetry is ONLY transmitted when:
        - mode == 'beta' AND
        - governance_active == True AND
        - consent_given == True
        """
        self.session_id = session_id
        self.turn_number = turn_number
        self.mode = mode
        self.start_time = time.time()
        self.backend = get_backend_service()

        # PRIVACY GUARD: Only track if all conditions met
        self.should_track = (
            mode == 'beta' and
            governance_active and
            consent_given
        )

        # Initialize turn in database ONLY if tracking enabled
        if self.should_track:
            self.backend.initiate_turn(
                session_id=session_id,
                turn_number=turn_number,
                mode=mode
            )

    def mark_calculating_pa(self):
        """Mark turn as calculating Primacy Attractor distance."""
        if not self.should_track:
            return  # Privacy guard: no tracking

        self.backend.mark_calculating_pa(
            session_id=self.session_id,
            turn_number=self.turn_number
        )

    def mark_evaluating(self):
        """Mark turn as evaluating governance metrics."""
        if not self.should_track:
            return  # Privacy guard: no tracking

        self.backend.mark_evaluating(
            session_id=self.session_id,
            turn_number=self.turn_number
        )

    def complete_turn(self, governance_metrics: Dict[str, Any],
                     semantic_context: Optional[Dict[str, Any]] = None):
        """
        Mark turn as completed with full governance + semantic data.

        Args:
            governance_metrics: Required governance metrics
                - fidelity_score: float
                - distance_from_pa: float
                - purpose_alignment: float
                - scope_alignment: float
                - boundary_alignment: float
                - intervention_triggered: bool
                - intervention_type: Optional[str]
                - intervention_reason: Optional[str]
            semantic_context: Optional semantic intelligence
                - request_type: str (e.g., 'coding_task', 'explanation', 'debugging')
                - request_complexity: str ('simple', 'moderate', 'complex')
                - detected_topics: List[str]
                - topic_shift_magnitude: float
                - semantic_drift_direction: str
                - constraints_approached: List[str]
                - constraint_violation_type: Optional[str]
        """
        if not self.should_track:
            return  # Privacy guard: no tracking

        # Calculate processing duration
        duration_ms = int((time.time() - self.start_time) * 1000)

        # Build final delta
        final_delta = {
            **governance_metrics,
            'mode': self.mode,
            'processing_duration_ms': duration_ms
        }

        # Merge in semantic context if provided
        if semantic_context:
            final_delta.update(semantic_context)

        # Transmit to backend storage
        self.backend.complete_turn(
            session_id=self.session_id,
            turn_number=self.turn_number,
            final_delta=final_delta
        )

    def fail_turn(self, error_message: str, stage: str):
        """
        Mark turn as failed with error details.

        Args:
            error_message: Error description
            stage: Stage where failure occurred
        """
        if not self.should_track:
            return  # Privacy guard: no tracking

        self.backend.fail_turn(
            session_id=self.session_id,
            turn_number=self.turn_number,
            error_message=error_message,
            stage=stage
        )


class SemanticAnalyzer:
    """
    Extracts semantic intelligence from conversation context.
    This provides the CONTEXT that makes telemetry data useful for research.
    """

    @staticmethod
    def classify_request_type(user_message: str) -> str:
        """
        Classify the type of user request.

        Args:
            user_message: User's input message

        Returns:
            Request type classification
        """
        msg_lower = user_message.lower()

        # Code-related
        if any(kw in msg_lower for kw in ['write', 'create', 'implement', 'build', 'code']):
            return 'coding_task'
        elif any(kw in msg_lower for kw in ['fix', 'debug', 'error', 'bug', 'broken']):
            return 'debugging'
        elif any(kw in msg_lower for kw in ['refactor', 'optimize', 'improve', 'clean up']):
            return 'refactoring'

        # Knowledge-related
        elif any(kw in msg_lower for kw in ['explain', 'what is', 'how does', 'why', 'tell me about']):
            return 'explanation'
        elif any(kw in msg_lower for kw in ['help', 'how to', 'guide', 'tutorial']):
            return 'guidance'

        # Project-related
        elif any(kw in msg_lower for kw in ['review', 'analyze', 'examine', 'investigate']):
            return 'code_review'
        elif any(kw in msg_lower for kw in ['test', 'verify', 'validate']):
            return 'testing'

        # Conversational
        elif any(kw in msg_lower for kw in ['discuss', 'think about', 'brainstorm']):
            return 'discussion'

        else:
            return 'general_request'

    @staticmethod
    def assess_complexity(user_message: str, pa_config: Dict[str, Any]) -> str:
        """
        Assess request complexity based on message length and PA config.

        Args:
            user_message: User's input message
            pa_config: Primacy Attractor configuration

        Returns:
            Complexity level ('simple', 'moderate', 'complex')
        """
        # Simple heuristics for now (can be enhanced with LLM analysis)
        msg_length = len(user_message)
        word_count = len(user_message.split())

        if msg_length < 100 or word_count < 15:
            return 'simple'
        elif msg_length < 500 or word_count < 75:
            return 'moderate'
        else:
            return 'complex'

    @staticmethod
    def extract_topics(user_message: str, assistant_response: Optional[str] = None) -> List[str]:
        """
        Extract topics being discussed (simple keyword-based for now).

        Args:
            user_message: User's input
            assistant_response: Optional assistant response

        Returns:
            List of detected topics
        """
        topics = []
        combined_text = user_message.lower()
        if assistant_response:
            combined_text += " " + assistant_response.lower()

        # Technical domains
        topic_keywords = {
            'frontend': ['react', 'vue', 'angular', 'html', 'css', 'ui', 'component'],
            'backend': ['api', 'server', 'database', 'sql', 'endpoint', 'service'],
            'testing': ['test', 'unittest', 'pytest', 'jest', 'coverage'],
            'deployment': ['deploy', 'docker', 'kubernetes', 'ci/cd', 'pipeline'],
            'security': ['auth', 'security', 'password', 'token', 'encryption'],
            'performance': ['optimize', 'performance', 'speed', 'cache', 'latency'],
            'data_science': ['data', 'ml', 'model', 'train', 'dataset', 'pandas'],
            'governance': ['governance', 'pa', 'primacy', 'attractor', 'fidelity', 'telos'],
        }

        for topic, keywords in topic_keywords.items():
            if any(kw in combined_text for kw in keywords):
                topics.append(topic)

        return topics if topics else ['general']

    @staticmethod
    def detect_constraints_approached(governance_metrics: Dict[str, Any],
                                     pa_config: Dict[str, Any]) -> List[str]:
        """
        Detect which PA constraints are being approached.

        Args:
            governance_metrics: Current governance metrics
            pa_config: PA configuration

        Returns:
            List of constraint names being approached
        """
        constraints_approached = []

        # Check each PA component
        if governance_metrics.get('purpose_alignment', 1.0) < 0.7:
            constraints_approached.append('purpose_drift')

        if governance_metrics.get('scope_alignment', 1.0) < 0.7:
            constraints_approached.append('scope_drift')

        if governance_metrics.get('boundary_alignment', 1.0) < 0.7:
            constraints_approached.append('boundary_drift')

        # Check overall fidelity
        if governance_metrics.get('fidelity_score', 1.0) < 0.6:
            constraints_approached.append('critical_fidelity_threshold')

        return constraints_approached

    @staticmethod
    def classify_violation_type(intervention_type: Optional[str],
                               intervention_reason: Optional[str]) -> Optional[str]:
        """
        Classify the type of constraint violation.

        Args:
            intervention_type: Type of intervention triggered
            intervention_reason: Reason for intervention

        Returns:
            Violation classification
        """
        if not intervention_type:
            return None

        if intervention_type == 'warning':
            return 'minor_drift'
        elif intervention_type == 'pause':
            return 'moderate_drift'
        elif intervention_type == 'block':
            return 'critical_violation'
        else:
            return 'unknown_violation'

    @classmethod
    def analyze_turn(cls, user_message: str, governance_metrics: Dict[str, Any],
                    pa_config: Dict[str, Any],
                    assistant_response: Optional[str] = None) -> Dict[str, Any]:
        """
        Full semantic analysis of a turn.

        Args:
            user_message: User's input message
            governance_metrics: Governance metrics from evaluation
            pa_config: Primacy Attractor configuration
            assistant_response: Optional assistant response

        Returns:
            Dictionary of semantic context
        """
        return {
            'request_type': cls.classify_request_type(user_message),
            'request_complexity': cls.assess_complexity(user_message, pa_config),
            'detected_topics': cls.extract_topics(user_message, assistant_response),
            'constraints_approached': cls.detect_constraints_approached(governance_metrics, pa_config),
            'constraint_violation_type': cls.classify_violation_type(
                governance_metrics.get('intervention_type'),
                governance_metrics.get('intervention_reason')
            )
        }


# Example usage:
"""
# PRIVACY-RESPECTING USAGE IN OBSERVATORY CONVERSATION FLOW

# Check if TELOS governance should run and track telemetry
mode = st.session_state.get('mode', 'demo')
consent_given = st.session_state.get('beta_consent_given', False)
governance_active = (mode == 'beta' and consent_given)

# Only initialize tracker if conditions met
if governance_active:
    # 1. Initialize turn tracker with privacy parameters
    tracker = TurnTracker(
        session_id=st.session_state.session_id,
        turn_number=len(st.session_state.messages) // 2,
        mode='beta',
        governance_active=True,
        consent_given=consent_given
    )

    # 2. Mark PA calculation
    tracker.mark_calculating_pa()
    pa_distance = calculate_pa_distance(user_message, pa_config)

    # 3. Mark evaluation
    tracker.mark_evaluating()
    governance_metrics = evaluate_governance(user_message, pa_distance)

    # 4. Get LLM response (governed by TELOS)
    assistant_response = get_mistral_response(user_message)

    # 5. Extract semantic context
    semantic_context = SemanticAnalyzer.analyze_turn(
        user_message=user_message,
        governance_metrics=governance_metrics,
        pa_config=pa_config,
        assistant_response=assistant_response
    )

    # 6. Complete turn with full telemetry
    tracker.complete_turn(
        governance_metrics=governance_metrics,
        semantic_context=semantic_context
    )
else:
    # NOT beta mode or no consent - NO TRACKING
    # Just run LLM without governance or telemetry
    assistant_response = get_mistral_response(user_message)
    # No telemetry transmission
"""

"""
Observatory - State Manager
============================

Centralized state management for the Observatory application.
All state lives here, components read and update through this manager.

Decomposed from original monolith:
  - state_manager.py  -- State only (this file)
  - llm_service.py    -- LLM client factory
  - response_service.py -- Response generation & streaming
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import streamlit as st

logger = logging.getLogger(__name__)


# ============================================================================
# State Dataclass
# ============================================================================

@dataclass
class ObservatoryState:
    """
    Complete state for Observatory application.

    All state variables are defined here with clear types and defaults.
    Components interact with state only through StateManager methods.
    """
    # Session data
    current_turn: int = 0
    total_turns: int = 0
    session_id: str = "unknown"
    turns: List[Dict[str, Any]] = field(default_factory=list)
    primacy_attractor: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # PA Establishment State (Calibration Phase)
    user_pa_established: bool = False
    ai_pa_established: bool = False
    calibration_phase: bool = True
    calibration_turn_count: int = 0
    convergence_turn: Optional[int] = None

    # UI state
    deck_expanded: bool = False
    teloscope_playing: bool = False
    teloscope_expanded: bool = False
    playback_speed: float = 1.0
    scrollable_history_mode: bool = False

    # Component visibility
    show_primacy_attractor: bool = False
    show_math_breakdown: bool = False
    show_counterfactual: bool = False
    show_steward: bool = False
    show_observatory_lens: bool = False

    # Metrics
    avg_fidelity: float = 0.0
    total_interventions: int = 0
    drift_warnings: int = 0


# ============================================================================
# State Manager
# ============================================================================

class StateManager:
    """
    Manages all Observatory state.

    Responsibilities:
    - Initialize default state
    - Provide read access to state
    - Provide controlled write access to state
    - Validate state changes
    - Trigger UI updates when needed
    """

    def __init__(self):
        """Initialize state manager with default state."""
        self.state = ObservatoryState()
        self._initialized = False
        self._beta_session_manager = None
        self._ps_calculator = None

    def initialize(self, session_data: Dict[str, Any]):
        """
        Initialize state from session data.

        Args:
            session_data: Dictionary containing session_id, turns, statistics, etc.
        """
        try:
            if self._initialized:
                logger.debug("State already initialized, skipping")
                return

            if not isinstance(session_data, dict):
                logger.error(f"Invalid session data type: {type(session_data)}")
                session_data = {}

            self.state.session_id = session_data.get('session_id', 'unknown')
            self.state.turns = session_data.get('turns', [])
            self.state.total_turns = len(self.state.turns)
            self.state.primacy_attractor = session_data.get('primacy_attractor', {})
            self.state.metadata = session_data.get('metadata', {})

            stats = session_data.get('statistics', {})
            self.state.avg_fidelity = stats.get('avg_fidelity', 0.0)
            self.state.total_interventions = stats.get('interventions', 0)
            self.state.drift_warnings = stats.get('drift_warnings', 0)

            self._initialized = True
            logger.info(f"State initialized: session_id={self.state.session_id}, turns={self.state.total_turns}")

        except Exception as e:
            logger.error(f"Error initializing state: {type(e).__name__}: {str(e)}", exc_info=True)
            self.state = ObservatoryState()
            self._initialized = True

    def load_from_session(self, session_data: Dict[str, Any]):
        """Load a saved session into current state (replaces current session)."""
        try:
            self._initialized = False
            self.initialize(session_data)
            self.state.current_turn = session_data.get('current_turn', max(0, self.state.total_turns - 1))
            if self.state.current_turn >= self.state.total_turns:
                self.state.current_turn = max(0, self.state.total_turns - 1)
            logger.info(f"Session loaded: {self.state.session_id}, positioned at turn {self.state.current_turn}")
        except Exception as e:
            logger.error(f"Error loading session: {type(e).__name__}: {str(e)}", exc_info=True)
            self._initialized = False
            self.initialize({})

    # =========================================================================
    # Read Access
    # =========================================================================

    def get_current_turn_index(self) -> int:
        """Get current turn index (0-based)."""
        return self.state.current_turn

    def get_current_turn_data(self) -> Optional[Dict[str, Any]]:
        """Get data for current turn."""
        if 0 <= self.state.current_turn < self.state.total_turns:
            return self.state.turns[self.state.current_turn]
        return None

    def get_all_turns(self) -> List[Dict[str, Any]]:
        """Get all turn data."""
        return self.state.turns

    def is_deck_expanded(self) -> bool:
        """Check if Observation Deck is expanded."""
        return self.state.deck_expanded

    def is_playing(self) -> bool:
        """Check if TELOSCOPE is in play mode."""
        return self.state.teloscope_playing

    def get_session_info(self) -> Dict[str, Any]:
        """Get session metadata and metrics."""
        return {
            'session_id': self.state.session_id,
            'total_turns': self.state.total_turns,
            'current_turn': self.state.current_turn,
            'avg_fidelity': self.state.avg_fidelity,
            'total_interventions': self.state.total_interventions,
            'drift_warnings': self.state.drift_warnings
        }

    # =========================================================================
    # Write Access - Turn Navigation
    # =========================================================================

    def next_turn(self) -> bool:
        """Advance to next turn. Returns True if advanced."""
        if self.state.current_turn < self.state.total_turns - 1:
            self.state.current_turn += 1
            return True
        return False

    def previous_turn(self) -> bool:
        """Go back to previous turn. Returns True if moved back."""
        if self.state.current_turn > 0:
            self.state.current_turn -= 1
            return True
        return False

    def jump_to_turn(self, turn_index: int) -> bool:
        """Jump to specific turn (0-based). Returns True if valid."""
        if 0 <= turn_index < self.state.total_turns:
            self.state.current_turn = turn_index
            return True
        return False

    # =========================================================================
    # Write Access - UI Toggles
    # =========================================================================

    def toggle_deck(self):
        """Toggle Observation Deck visibility."""
        self.state.deck_expanded = not self.state.deck_expanded

    def toggle_teloscope(self):
        """Toggle TELOSCOPE Controls visibility."""
        self.state.teloscope_expanded = not self.state.teloscope_expanded

    def is_teloscope_expanded(self) -> bool:
        """Check if TELOSCOPE Controls are expanded."""
        return self.state.teloscope_expanded

    def start_playback(self):
        """Start TELOSCOPE playback."""
        self.state.teloscope_playing = True

    def stop_playback(self):
        """Stop TELOSCOPE playback."""
        self.state.teloscope_playing = False

    def set_playback_speed(self, speed: float):
        """Set playback speed (0.1 to 5.0)."""
        if 0.1 <= speed <= 5.0:
            self.state.playback_speed = speed

    def toggle_component(self, component: str):
        """Toggle visibility of a component."""
        if component == 'primacy_attractor':
            self.state.show_primacy_attractor = not self.state.show_primacy_attractor
        elif component in ('math', 'math_breakdown'):
            self.state.show_math_breakdown = not self.state.show_math_breakdown
        elif component == 'counterfactual':
            self.state.show_counterfactual = not self.state.show_counterfactual
        elif component == 'steward':
            self.state.show_steward = not self.state.show_steward
        elif component == 'observatory_lens':
            self.state.show_observatory_lens = not self.state.show_observatory_lens

    def toggle_scrollable_history(self):
        """Toggle between turn-by-turn and scrollable history mode."""
        self.state.scrollable_history_mode = not self.state.scrollable_history_mode

    def clear_demo_data(self):
        """Clear all demo/initial data to start fresh with user conversation."""
        logger.info("Clearing demo data to start fresh user conversation")
        self.state.turns = []
        self.state.total_turns = 0
        self.state.current_turn = 0
        self.state.avg_fidelity = 0.0
        self.state.total_interventions = 0
        self.state.drift_warnings = 0

        if hasattr(self, '_telos_steward') and self._telos_steward:
            try:
                self._telos_steward.end_session()
                self._telos_steward.start_session(session_id=f"{self.state.session_id}_user")
                logger.info("TELOS session reset for user conversation")
            except Exception as e:
                logger.warning(f"Could not reset TELOS session: {e}")

    # =========================================================================
    # Statistics Update
    # =========================================================================

    def update_statistics(self):
        """Recompute aggregate statistics from turn data."""
        fidelities = [t['fidelity'] for t in self.state.turns if t.get('fidelity') is not None]
        self.state.avg_fidelity = sum(fidelities) / len(fidelities) if fidelities else 0.0
        self.state.total_interventions = sum(1 for t in self.state.turns if t.get('intervention_applied', False))
        self.state.drift_warnings = sum(1 for t in self.state.turns if t.get('drift_detected', False))

    # =========================================================================
    # Beta Testing Methods
    # =========================================================================

    def _initialize_beta_session_manager(self):
        """Initialize beta session manager (lazy loading)."""
        if self._beta_session_manager is None:
            try:
                from telos_observatory.beta_testing.beta_session_manager import BetaSessionManager
                self._beta_session_manager = BetaSessionManager()
                logger.info("Beta session manager initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize beta session manager: {e}")
                self._beta_session_manager = None

    def _is_beta_ab_phase(self) -> bool:
        """Check if we're in beta mode AND at the A/B testing phase."""
        active_tab = st.session_state.get('active_tab', 'DEMO')
        if active_tab != "BETA":
            return False

        beta_consent = st.session_state.get('beta_consent_given', False)
        beta_intro_complete = st.session_state.get('beta_intro_complete', False)
        if not (beta_consent and beta_intro_complete):
            return False

        current_turn = len([t for t in self.state.turns if not t.get('is_loading', False)])
        pa_established = self.state.ai_pa_established

        if current_turn > 10 and not pa_established:
            logger.warning(f"Turn {current_turn}: PA not established by turn 10")
            return False

        return pa_established

    # =========================================================================
    # Response Generation (delegates to response_service)
    # =========================================================================

    def add_user_message(self, message: str):
        """Add a new user message and generate a TELOS-governed response."""
        from telos_observatory.core.response_service import add_user_message
        add_user_message(self, message)

    def add_user_message_streaming(self, message: str) -> int:
        """Add user message and prepare for streaming response. Returns turn_index."""
        from telos_observatory.core.response_service import add_user_message_streaming
        return add_user_message_streaming(self, message)

    def generate_response_stream(self, message: str, turn_idx: int):
        """Generator that yields response chunks for streaming display."""
        from telos_observatory.core.response_service import generate_response_stream
        yield from generate_response_stream(self, message, turn_idx)

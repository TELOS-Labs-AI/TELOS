"""
Beta Review Component
=====================

Post-session review interface for BETA testing.
Loads BETA data from backend storage and displays it using existing Observatory components.

Key features:
- Loads completed BETA session data
- Formats data for existing Observatory components
- Shows User PA (was visible during session)
- Reveals AI PA (was hidden during session)
- BETA-specific metrics (system served, preferences, etc.)
"""

import streamlit as st
import logging
from typing import Dict, Any, Optional, List

from telos_observatory.services.backend_client import BackendService
from telos_observatory.components.observation_deck import ObservationDeck
from telos_observatory.components.observatory_lens import ObservatoryLens

logger = logging.getLogger(__name__)


class BetaReview:
    """
    Post-session review for BETA testing.

    Uses existing Observatory components to display BETA session data.
    """

    def __init__(self, backend_client: Optional[BackendService] = None, state_manager=None):
        """
        Initialize BETA review component.

        Args:
            backend_client: BackendService instance for data retrieval
            state_manager: StateManager instance for Observatory components
        """
        self.backend = backend_client
        self.state_manager = state_manager

    def load_beta_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load BETA session data from backend storage.

        Args:
            session_id: Session UUID

        Returns:
            Session data formatted for Observatory, or None if not found
        """
        if not self.backend:
            logger.error("Backend client not available")
            return None

        try:
            # Fetch session metadata
            session_data = self.backend.get_beta_session(session_id)
            if not session_data:
                logger.error(f"Session not found: {session_id}")
                return None

            # Fetch all turns
            turns_data = self.backend.get_beta_turns(session_id)
            if not turns_data:
                logger.warning(f"No turns found for session {session_id}")

            # Format for Observatory
            observatory_data = {
                'session_id': session_id,
                'user_pa': session_data['user_pa_config'],
                'ai_pa': session_data['ai_pa_config'],
                'basin_constant': session_data.get('basin_constant', 1.0),
                'constraint_tolerance': session_data.get('constraint_tolerance', 0.05),
                'created_at': session_data['created_at'],
                'completed_at': session_data.get('completed_at'),
                'total_turns': session_data.get('total_turns', len(turns_data)),
                'phase_1_complete': session_data.get('phase_1_complete', False),
                'phase_2_complete': session_data.get('phase_2_complete', False),
                'turns': []
            }

            # Format turns
            for turn in turns_data:
                observatory_data['turns'].append({
                    'turn_number': turn['turn_number'],
                    'phase': turn.get('phase', 'ab_testing'),
                    'user_message': turn['user_message'],
                    'assistant_response': turn['response_delivered'],
                    'system_served': turn.get('system_served'),  # BETA-specific
                    'telos_response': turn.get('telos_response'),  # BETA-specific
                    'native_response': turn.get('native_response'),  # BETA-specific
                    'user_fidelity': turn.get('user_fidelity'),
                    'ai_fidelity': turn.get('ai_fidelity'),
                    'primacy_state': turn.get('primacy_state'),
                    'distance': turn.get('distance_from_pa'),
                    'in_basin': turn.get('in_basin'),
                    'intervention_calculated': turn.get('intervention_calculated', False),
                    'intervention_applied': turn.get('intervention_applied', False),
                    'intervention_type': turn.get('intervention_type'),
                    'steward_interpretation': turn.get('steward_interpretation'),  # BETA-specific
                    'user_action': turn.get('user_action', 'none'),  # BETA-specific
                    'user_preference': turn.get('user_preference', 'no_preference'),  # BETA-specific
                    'timestamp': turn.get('created_at')
                })

            logger.info(f"Loaded BETA session: {session_id} ({len(turns_data)} turns)")
            return observatory_data

        except Exception as e:
            logger.error(f"Failed to load BETA session: {e}")
            return None

    def render(self, session_id: Optional[str] = None):
        """
        Render BETA review interface.

        Args:
            session_id: Session UUID (uses session_state if not provided)
        """
        # Get session ID
        if not session_id:
            session_id = st.session_state.get('session_id')

        if not session_id:
            st.error("No session ID provided for review")
            return

        # Load session data
        with st.spinner("Loading your BETA session..."):
            observatory_data = self.load_beta_session(session_id)

        if not observatory_data:
            st.error("Failed to load BETA session data. Please check logs.")
            return

        # Title
        st.markdown("""
        <div style="text-align: center; padding: 20px 0;">
            <h1 style="color: #F4D03F; font-size: 42px; margin: 0;">BETA Session Review</h1>
            <p style="color: #e0e0e0; font-size: 16px; margin-top: 10px;">
                Governance metrics and insights from your session
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        # Session metadata
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Turns", observatory_data['total_turns'])
        with col2:
            phases_complete = []
            if observatory_data['phase_1_complete']:
                phases_complete.append("AB Testing")
            if observatory_data['phase_2_complete']:
                phases_complete.append("Full TELOS")
            st.metric("Phases Complete", ", ".join(phases_complete) if phases_complete else "None")
        with col3:
            basin_adherence = sum(1 for t in observatory_data['turns'] if t.get('in_basin', False)) / max(len(observatory_data['turns']), 1)
            st.metric("Basin Adherence", f"{basin_adherence*100:.1f}%")

        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        # Show User PA (was visible during session)
        with st.expander("🎯 Your Primacy Attractor", expanded=True):
            user_pa = observatory_data['user_pa']
            st.markdown(f"**Purpose:** {user_pa['purpose'][0]}")
            st.markdown("**Scope:**")
            for item in user_pa['scope']:
                st.markdown(f"- {item}")
            st.markdown("**Boundaries:**")
            for item in user_pa['boundaries']:
                st.markdown(f"- {item}")

        # Reveal AI PA (was hidden during session)
        with st.expander("🤖 AI Primacy Attractor (Revealed)", expanded=False):
            st.info("This shows how the AI adapted its behavior to serve your purpose.")
            ai_pa = observatory_data['ai_pa']
            st.markdown(f"**Purpose:** {ai_pa['purpose'][0]}")
            st.markdown("**Scope:**")
            for item in ai_pa['scope']:
                st.markdown(f"- {item}")
            if 'boundaries' in ai_pa and ai_pa['boundaries']:
                st.markdown("**Boundaries:**")
                for item in ai_pa['boundaries']:
                    st.markdown(f"- {item}")

        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        # BETA-specific metrics
        self._render_beta_metrics(observatory_data)

        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        # Use EXISTING Observatory components for turn-by-turn review
        st.markdown("---")
        st.subheader("📊 Turn-by-Turn Analysis")
        st.markdown("Use the controls below to navigate through your conversation and see governance metrics.")

        # Observation Deck (existing component)
        try:
            observation_deck = ObservationDeck(self.state_manager)
            # Load BETA data into observation deck
            observation_deck.render_beta_data(observatory_data)
        except Exception as e:
            logger.error(f"ObservationDeck rendering failed: {e}")
            st.error(f"Failed to render Observation Deck: {e}")

        # Observatory Lens (existing component)
        try:
            observatory_lens = ObservatoryLens(self.state_manager)
            # Load BETA data into observatory lens
            observatory_lens.render_beta_data(observatory_data)
        except Exception as e:
            logger.error(f"ObservatoryLens rendering failed: {e}")
            st.error(f"Failed to render Observatory Lens: {e}")

        st.markdown("<div style='margin: 40px 0;'></div>", unsafe_allow_html=True)

        # Download options
        self._render_download_options(observatory_data)

    def _render_beta_metrics(self, observatory_data: Dict[str, Any]):
        """
        Render BETA-specific metrics (AB testing results, preferences).

        Args:
            observatory_data: Session data
        """
        st.subheader("🧪 AB Testing Results")

        turns = observatory_data['turns']
        ab_turns = [t for t in turns if t.get('phase') == 'ab_testing']

        if not ab_turns:
            st.info("No AB testing turns found in this session")
            return

        # System distribution
        telos_turns = [t for t in ab_turns if t.get('system_served') == 'telos']
        native_turns = [t for t in ab_turns if t.get('system_served') == 'native']

        col1, col2 = st.columns(2)
        with col1:
            st.metric("TELOS Turns", len(telos_turns))
        with col2:
            st.metric("Native Turns", len(native_turns))

        # User preferences
        thumbs_up_telos = len([t for t in telos_turns if t.get('user_action') == 'thumbs_up'])
        thumbs_up_native = len([t for t in native_turns if t.get('user_action') == 'thumbs_up'])
        thumbs_down_telos = len([t for t in telos_turns if t.get('user_action') == 'thumbs_down'])
        thumbs_down_native = len([t for t in native_turns if t.get('user_action') == 'thumbs_down'])

        st.markdown("**Your Feedback:**")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Governed:**")
            st.markdown(f"- 👍 {thumbs_up_telos} / 👎 {thumbs_down_telos}")
        with col2:
            st.markdown(f"**Native:**")
            st.markdown(f"- 👍 {thumbs_up_native} / 👎 {thumbs_down_native}")

        # Regenerate preferences
        regenerations = [t for t in ab_turns if t.get('user_action') == 'regenerate']
        if regenerations:
            telos_preferred = len([t for t in regenerations if t.get('user_preference') == 'selected_telos'])
            native_preferred = len([t for t in regenerations if t.get('user_preference') == 'selected_native'])
            st.markdown(f"**When you regenerated:** Chose Governed {telos_preferred} times, Native {native_preferred} times")

        # Governance effectiveness
        st.markdown("**Governance Metrics:**")
        col1, col2 = st.columns(2)
        with col1:
            avg_fidelity_telos = sum(t.get('user_fidelity', 0) for t in telos_turns) / max(len(telos_turns), 1)
            st.metric("Avg Fidelity (Governed turns)", f"{avg_fidelity_telos:.3f}")
        with col2:
            avg_fidelity_native = sum(t.get('user_fidelity', 0) for t in native_turns) / max(len(native_turns), 1)
            st.metric("Avg Fidelity (Native turns)", f"{avg_fidelity_native:.3f}")

    def _render_download_options(self, observatory_data: Dict[str, Any]):
        """
        Render download options for session data.

        Args:
            observatory_data: Session data
        """
        st.subheader("💾 Export Options")

        col1, col2, col3 = st.columns(3)

        with col1:
            # JSON export
            import json
            json_data = json.dumps(observatory_data, indent=2, default=str)
            st.download_button(
                label="Download JSON",
                data=json_data,
                file_name=f"beta_session_{observatory_data['session_id']}.json",
                mime="application/json"
            )

        with col2:
            # CSV export (turns only)
            import csv
            import io

            csv_buffer = io.StringIO()
            writer = csv.DictWriter(
                csv_buffer,
                fieldnames=['turn_number', 'phase', 'system_served', 'user_fidelity',
                           'ai_fidelity', 'primacy_state', 'in_basin', 'user_action']
            )
            writer.writeheader()
            for turn in observatory_data['turns']:
                writer.writerow({
                    'turn_number': turn['turn_number'],
                    'phase': turn.get('phase', ''),
                    'system_served': turn.get('system_served', ''),
                    'user_fidelity': f"{turn.get('user_fidelity', 0):.3f}",
                    'ai_fidelity': f"{turn.get('ai_fidelity', 0):.3f}",
                    'primacy_state': f"{turn.get('primacy_state', 0):.3f}",
                    'in_basin': turn.get('in_basin', False),
                    'user_action': turn.get('user_action', 'none')
                })

            st.download_button(
                label="Download CSV",
                data=csv_buffer.getvalue(),
                file_name=f"beta_session_{observatory_data['session_id']}.csv",
                mime="text/csv"
            )

        with col3:
            # Summary text export
            summary = self._generate_summary_text(observatory_data)
            st.download_button(
                label="Download Summary",
                data=summary,
                file_name=f"beta_session_{observatory_data['session_id']}_summary.txt",
                mime="text/plain"
            )

    def _generate_summary_text(self, observatory_data: Dict[str, Any]) -> str:
        """
        Generate human-readable summary text.

        Args:
            observatory_data: Session data

        Returns:
            Formatted summary text
        """
        turns = observatory_data['turns']
        ab_turns = [t for t in turns if t.get('phase') == 'ab_testing']

        summary = f"""TELOS BETA Session Summary
{'=' * 60}

Session ID: {observatory_data['session_id']}
Created: {observatory_data['created_at']}
Completed: {observatory_data.get('completed_at', 'N/A')}
Total Turns: {observatory_data['total_turns']}

YOUR PRIMACY ATTRACTOR
{'=' * 60}
Purpose: {observatory_data['user_pa']['purpose'][0]}
Scope: {', '.join(observatory_data['user_pa']['scope'])}
Boundaries: {', '.join(observatory_data['user_pa']['boundaries'])}

AB TESTING RESULTS
{'=' * 60}
TELOS Turns: {len([t for t in ab_turns if t.get('system_served') == 'telos'])}
Native Turns: {len([t for t in ab_turns if t.get('system_served') == 'native'])}

GOVERNANCE METRICS
{'=' * 60}
Basin Adherence: {sum(1 for t in turns if t.get('in_basin', False)) / max(len(turns), 1)*100:.1f}%
Average Fidelity: {sum(t.get('user_fidelity', 0) for t in turns) / max(len(turns), 1):.3f}
Interventions Calculated: {sum(1 for t in turns if t.get('intervention_calculated', False))}
Interventions Applied: {sum(1 for t in turns if t.get('intervention_applied', False))}

Thank you for participating in TELOS BETA testing!
"""
        return summary

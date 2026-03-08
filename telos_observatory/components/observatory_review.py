"""
Observatory Review Interface for Post-BETA Analysis
===================================================

Complete session review with TELOSCOPE controls and full analysis.
"""

import streamlit as st
from typing import Dict, List, Optional
from telos_observatory.components.fidelity_visualization import FidelityBarGraph, TurnByTurnAnalyzer
from telos_observatory.components.turn_markers import render_turn_marker

# Import color configuration
from telos_observatory.config.colors import GOLD, STATUS_GOOD, STATUS_MODERATE, STATUS_SEVERE


class ObservatoryReview:
    """Complete Observatory review interface for BETA sessions."""

    def __init__(self, state_manager):
        """Initialize with state manager reference."""
        self.state_manager = state_manager
        self.bar_graph = FidelityBarGraph()
        self.turn_analyzer = TurnByTurnAnalyzer()

    def render(self):
        """Render the complete Observatory review interface."""

        # Check if BETA is complete
        # beta_current_turn is the NEXT turn to play (starts at 1), so completed turns = current_turn - 1
        beta_turns = st.session_state.get('beta_current_turn', 1) - 1
        if beta_turns < 5:
            st.warning("Complete BETA testing (5 turns) to unlock full Observatory review")
            return

        # Header
        st.markdown("""
        <div style="
            text-align: center;
            padding: 30px;
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            border: 2px solid {GOLD};
            border-radius: 15px;
            margin-bottom: 30px;
        ">
            <h1 style="color: {GOLD}; margin: 0;">🔭 Observatory Session Review</h1>
            <p style="color: #e0e0e0; margin-top: 10px;">
                Complete analysis of your BETA testing session
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Summary Statistics
        self._render_summary_statistics()

        # Fidelity Bar Graph
        st.markdown("### 📊 Fidelity Across All Turns")
        turn_data = self._collect_turn_data()
        self.bar_graph.render_bar_graph(turn_data)

        # TELOSCOPE Controls
        st.markdown("### 🎛️ TELOSCOPE Turn Navigator")
        self._render_teloscope_controls()

        # Selected Turn Detail
        selected_turn = st.session_state.get('selected_turn', 1)
        if selected_turn:
            self._render_turn_detail(selected_turn)

        # Preference Analysis
        self._render_preference_analysis()

        # Intervention Analysis
        self._render_intervention_analysis()

    def _render_summary_statistics(self):
        """Render summary statistics dashboard."""
        stats = st.session_state.get('beta_statistics', {})

        st.markdown("### 📈 Session Overview")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            avg_fidelity = stats.get('avg_fidelity', 0.0)
            color = self.bar_graph.get_color_for_score(avg_fidelity)[1]
            st.markdown(f"""
            <div style="
                background-color: {color}22;
                border: 2px solid {color};
                border-radius: 10px;
                padding: 15px;
                text-align: center;
            ">
                <div style="color: #888; font-size: 14px;">Avg Fidelity</div>
                <div style="color: {color}; font-size: 32px; font-weight: bold;">
                    {avg_fidelity:.3f}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            total_interventions = stats.get('total_interventions', 0)
            st.markdown(f"""
            <div style="
                background-color: {STATUS_MODERATE}22;
                border: 2px solid {STATUS_MODERATE};
                border-radius: 10px;
                padding: 15px;
                text-align: center;
            ">
                <div style="color: #888; font-size: 14px;">Interventions</div>
                <div style="color: {STATUS_MODERATE}; font-size: 32px; font-weight: bold;">
                    {total_interventions}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            total_drifts = stats.get('total_drifts', 0)
            st.markdown(f"""
            <div style="
                background-color: {STATUS_SEVERE}22;
                border: 2px solid {STATUS_SEVERE};
                border-radius: 10px;
                padding: 15px;
                text-align: center;
            ">
                <div style="color: #888; font-size: 14px;">Drift Events</div>
                <div style="color: {STATUS_SEVERE}; font-size: 32px; font-weight: bold;">
                    {total_drifts}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            # Calculate preference ratio
            preferences = self._calculate_preferences()
            st.markdown(f"""
            <div style="
                background-color: #27ae6022;
                border: 2px solid #27ae60;
                border-radius: 10px;
                padding: 15px;
                text-align: center;
            ">
                <div style="color: #888; font-size: 14px;">TELOS Preference</div>
                <div style="color: #27ae60; font-size: 32px; font-weight: bold;">
                    {preferences['telos_preference']}%
                </div>
            </div>
            """, unsafe_allow_html=True)

    def _render_teloscope_controls(self):
        """Render TELOSCOPE turn-by-turn navigation controls."""

        # Turn selector
        col1, col2, col3 = st.columns([1, 3, 1])

        with col1:
            if st.button("⬅️ Previous", use_container_width=True):
                current = st.session_state.get('selected_turn', 1)
                if current > 1:
                    st.session_state.selected_turn = current - 1
                    st.rerun()

        with col2:
            selected_turn = st.slider(
                "Select Turn",
                min_value=1,
                max_value=15,
                value=st.session_state.get('selected_turn', 1),
                key="turn_slider",
                help="Navigate through your session turn by turn"
            )
            st.session_state.selected_turn = selected_turn

        with col3:
            if st.button("Next ➡️", use_container_width=True):
                current = st.session_state.get('selected_turn', 1)
                if current < 15:
                    st.session_state.selected_turn = current + 1
                    st.rerun()

        # Quick jump buttons for interesting turns
        st.markdown("**Quick Jump:**")
        col_buttons = st.columns(5)

        # Find turns with interventions
        intervention_turns = []
        for i in range(1, 16):
            turn_data = st.session_state.get(f'beta_turn_{i}_data', {})
            if turn_data.get('telos_analysis', {}).get('intervention_triggered'):
                intervention_turns.append(i)

        if intervention_turns:
            for i, turn in enumerate(intervention_turns[:5]):
                with col_buttons[i]:
                    if st.button(f"⚠️ T{turn}", use_container_width=True,
                               help=f"Turn {turn} had intervention"):
                        st.session_state.selected_turn = turn
                        st.rerun()

    def _render_turn_detail(self, turn_number: int):
        """Render detailed view of selected turn."""

        turn_data = st.session_state.get(f'beta_turn_{turn_number}_data', {})
        if not turn_data:
            st.error(f"No data available for turn {turn_number}")
            return

        # Turn header with marker
        marker_html = render_turn_marker(turn_number, "beta")
        st.markdown(marker_html, unsafe_allow_html=True)

        # Use the turn analyzer for detailed view
        self.turn_analyzer.render_turn_detail(turn_number, turn_data)

        # Show actual conversation
        st.markdown("### 💬 Conversation")

        # User input
        st.markdown("""
        <div style="
            background-color: #1a1a1a;
            border-left: 4px solid #27ae60;
            padding: 15px;
            margin: 10px 0;
        ">
            <div style="color: #27ae60; font-weight: bold; margin-bottom: 5px;">You:</div>
            <div style="color: #e0e0e0;">
        """, unsafe_allow_html=True)
        st.markdown(turn_data.get('user_input', 'No input recorded'))
        st.markdown("</div></div>", unsafe_allow_html=True)

        # Response(s)
        test_type = turn_data.get('test_type')

        if test_type == 'head_to_head':
            # Show both responses
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("""
                <div style="
                    background-color: rgba(76, 175, 80, 0.05);
                    border: 2px solid #27ae60;
                    border-radius: 10px;
                    padding: 15px;
                ">
                    <div style="color: #27ae60; font-weight: bold; margin-bottom: 10px;">
                        Steward Response (Governed):
                    </div>
                """, unsafe_allow_html=True)
                telos_response = turn_data.get('telos_analysis', {}).get('response', '')
                st.markdown(telos_response)
                st.markdown("</div>", unsafe_allow_html=True)

            with col2:
                st.markdown("""
                <div style="
                    background-color: rgba(136, 136, 136, 0.05);
                    border: 2px solid #888;
                    border-radius: 10px;
                    padding: 15px;
                ">
                    <div style="color: #888; font-weight: bold; margin-bottom: 10px;">
                        Native Response:
                    </div>
                """, unsafe_allow_html=True)
                native_response = turn_data.get('native_response', '')
                st.markdown(native_response)
                st.markdown("</div>", unsafe_allow_html=True)

        else:
            # Single response
            shown_source = turn_data.get('shown_source')
            color = '#27ae60' if shown_source == 'telos' else '#888'
            label = 'Steward' if shown_source == 'telos' else 'Steward'  # Unified persona

            st.markdown(f"""
            <div style="
                background-color: {color}11;
                border-left: 4px solid {color};
                padding: 15px;
                margin: 10px 0;
            ">
                <div style="color: {color}; font-weight: bold; margin-bottom: 5px;">
                    {label} Response:
                </div>
                <div style="color: #e0e0e0;">
            """, unsafe_allow_html=True)
            st.markdown(turn_data.get('shown_response', ''))
            st.markdown("</div></div>", unsafe_allow_html=True)

    def _render_preference_analysis(self):
        """Render user preference analysis."""

        st.markdown("### 👍 Your Preference Analysis")

        # Collect preference data
        preferences = {
            'telos_thumbs_up': 0,
            'telos_neutral': 0,
            'telos_thumbs_down': 0,
            'native_thumbs_up': 0,
            'native_neutral': 0,
            'native_thumbs_down': 0,
            'head_to_head_telos': 0,
            'head_to_head_native': 0
        }

        for i in range(1, 16):
            turn_data = st.session_state.get(f'beta_turn_{i}_data', {})
            preference = turn_data.get('user_preference')
            source = turn_data.get('shown_source')

            if preference and source:
                if source in ['telos', 'native']:
                    key = f"{source}_{preference}"
                    if key in preferences:
                        preferences[key] += 1
                elif preference in ['response_a', 'response_b']:
                    # Head-to-head
                    # Need to check which was which
                    pass

        # Display preference breakdown
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Governed Responses:**")
            telos_total = preferences['telos_thumbs_up'] + preferences['telos_neutral'] + preferences['telos_thumbs_down']
            if telos_total > 0:
                st.markdown(f"👍 Positive: {preferences['telos_thumbs_up']}/{telos_total}")
                st.markdown(f"🤷 Neutral: {preferences['telos_neutral']}/{telos_total}")
                st.markdown(f"👎 Negative: {preferences['telos_thumbs_down']}/{telos_total}")

        with col2:
            st.markdown("**Native Responses:**")
            native_total = preferences['native_thumbs_up'] + preferences['native_neutral'] + preferences['native_thumbs_down']
            if native_total > 0:
                st.markdown(f"👍 Positive: {preferences['native_thumbs_up']}/{native_total}")
                st.markdown(f"🤷 Neutral: {preferences['native_neutral']}/{native_total}")
                st.markdown(f"👎 Negative: {preferences['native_thumbs_down']}/{native_total}")

    def _render_intervention_analysis(self):
        """Render detailed intervention analysis."""

        st.markdown("### ⚠️ Intervention Analysis")

        # Collect all interventions
        interventions = []
        for i in range(1, 16):
            turn_data = st.session_state.get(f'beta_turn_{i}_data', {})
            telos_analysis = turn_data.get('telos_analysis', {})

            if telos_analysis.get('intervention_triggered'):
                interventions.append({
                    'turn': i,
                    'reason': telos_analysis.get('intervention_reason', 'Unknown'),
                    'type': telos_analysis.get('intervention_type', 'Unknown'),
                    'fidelity_before': telos_analysis.get('fidelity_score', 0.0),
                    'shown': turn_data.get('shown_source') == 'telos'
                })

        if not interventions:
            st.info("No interventions were triggered during your session")
        else:
            for intervention in interventions:
                status = "✅ Shown" if intervention['shown'] else "🔮 Not shown (random selection)"

                st.markdown(f"""
                <div style="
                    background-color: rgba(255, 165, 0, 0.05);
                    border-left: 4px solid {STATUS_MODERATE};
                    padding: 15px;
                    margin: 10px 0;
                ">
                    <div style="color: {STATUS_MODERATE}; font-weight: bold;">
                        Turn {intervention['turn']} - {status}
                    </div>
                    <div style="color: #e0e0e0; margin-top: 10px;">
                        <strong>Reason:</strong> {intervention['reason']}<br>
                        <strong>Type:</strong> {intervention['type']}<br>
                        <strong>Fidelity:</strong> {intervention['fidelity_before']:.3f}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    def _collect_turn_data(self) -> List[Dict]:
        """Collect all turn data for visualization."""
        turn_data = []
        for i in range(1, 16):
            data = st.session_state.get(f'beta_turn_{i}_data', {})
            if data:
                telos_analysis = data.get('telos_analysis', {})
                turn_data.append({
                    'turn_number': i,
                    'fidelity_score': telos_analysis.get('fidelity_score', 0.0),
                    'intervention_triggered': telos_analysis.get('intervention_triggered', False),
                    'response_source': data.get('shown_source', 'unknown')
                })
        return turn_data

    def _calculate_preferences(self) -> Dict:
        """Calculate preference statistics."""
        telos_positive = 0
        native_positive = 0
        total_rated = 0

        for i in range(1, 16):
            turn_data = st.session_state.get(f'beta_turn_{i}_data', {})
            preference = turn_data.get('user_preference')
            source = turn_data.get('shown_source')

            if preference == 'thumbs_up':
                total_rated += 1
                if source == 'telos':
                    telos_positive += 1
                elif source == 'native':
                    native_positive += 1

        telos_pref = 0
        if total_rated > 0:
            telos_pref = int((telos_positive / total_rated) * 100)

        return {
            'telos_preference': telos_pref,
            'native_preference': 100 - telos_pref,
            'total_rated': total_rated
        }
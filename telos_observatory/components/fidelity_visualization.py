"""
Fidelity Bar Graph Visualization for BETA Observatory
=====================================================

Creates color-coded bar graphs showing fidelity over turns.
"""

import streamlit as st
from typing import List, Dict
import json

# Import color configuration
from telos_observatory.config.colors import GOLD, STATUS_GOOD, STATUS_MODERATE, STATUS_SEVERE


class FidelityBarGraph:
    """Creates interactive bar graph of fidelity scores across turns."""

    def __init__(self):
        # Import Goldilocks zone thresholds from central config
        try:
            from telos_observatory.config.colors import _ZONE_ALIGNED, _ZONE_MINOR_DRIFT, _ZONE_DRIFT
        except ImportError:
            _ZONE_ALIGNED, _ZONE_MINOR_DRIFT, _ZONE_DRIFT = 0.70, 0.60, 0.50

        # Zone-based thresholds (Goldilocks optimized)
        self.color_thresholds = {
            'green': (_ZONE_ALIGNED, 1.0, '#27ae60'),      # "Aligned" zone (canonical TELOS green)
            'yellow': (_ZONE_MINOR_DRIFT, _ZONE_ALIGNED, '{GOLD}'),  # "Minor Drift" zone
            'orange': (_ZONE_DRIFT, _ZONE_MINOR_DRIFT, '{STATUS_MODERATE}'),  # "Drift Detected" zone
            'red': (0.0, _ZONE_DRIFT, '{STATUS_SEVERE}')   # "Significant Drift" zone
        }
        self._zone_aligned = _ZONE_ALIGNED
        self._zone_minor = _ZONE_MINOR_DRIFT
        self._zone_drift = _ZONE_DRIFT

    def get_color_for_score(self, score: float) -> tuple:
        """Get color based on fidelity score."""
        for name, (low, high, color) in self.color_thresholds.items():
            if low <= score <= high:
                return name, color
        return 'red', '{STATUS_SEVERE}'

    def render_bar_graph(self, turn_data: List[Dict]):
        """
        Render the fidelity bar graph.

        Args:
            turn_data: List of turn dictionaries with fidelity scores
        """
        # CSS for the bar graph
        st.markdown("""
        <style>
        .fidelity-graph {
            display: flex;
            align-items: flex-end;
            height: 300px;
            padding: 20px;
            background-color: #1a1a1a;
            border: 1px solid {GOLD};
            border-radius: 10px;
            margin: 20px 0;
            overflow-x: auto;
        }

        .fidelity-bar {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin: 0 5px;
            position: relative;
        }

        .bar-column {
            width: 40px;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            border-radius: 4px 4px 0 0;
            position: relative;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .bar-column:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(255, 215, 0, 0.5);
        }

        .bar-segment {
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #000;
            font-size: 10px;
            font-weight: bold;
        }

        .turn-label {
            color: #e0e0e0;
            font-size: 12px;
            margin-top: 5px;
        }

        .fidelity-value {
            position: absolute;
            top: -20px;
            color: {GOLD};
            font-size: 11px;
            font-weight: bold;
            white-space: nowrap;
        }

        .intervention-marker {
            position: absolute;
            top: -30px;
            color: {STATUS_MODERATE};
            font-size: 16px;
        }
        </style>
        """, unsafe_allow_html=True)

        # Build the bar graph HTML
        graph_html = '<div class="fidelity-graph">'

        for i, turn in enumerate(turn_data, 1):
            fidelity = turn.get('fidelity_score', 0.0)
            intervention = turn.get('intervention_triggered', False)
            response_type = turn.get('response_source', 'unknown')

            # Calculate bar height
            bar_height = int(fidelity * 250)  # Max height 250px

            # Create segmented bar based on color zones
            segments = []

            # Calculate segment heights using Goldilocks zone thresholds
            if fidelity > self._zone_aligned:
                # "Aligned" zone - all green
                green_height = bar_height
                segments.append(('green', green_height, fidelity))
            elif fidelity > self._zone_minor:
                # "Minor Drift" zone - green + yellow
                green_zone_size = 1.0 - self._zone_aligned
                green_height = int(green_zone_size * 250)
                yellow_height = bar_height - green_height
                segments.append(('yellow', yellow_height, ''))
                segments.append(('green', green_height, fidelity))
            elif fidelity > self._zone_drift:
                # "Drift Detected" zone - green + yellow + orange
                green_zone_size = 1.0 - self._zone_aligned
                yellow_zone_size = self._zone_aligned - self._zone_minor
                green_height = int(green_zone_size * 250)
                yellow_height = int(yellow_zone_size * 250)
                orange_height = bar_height - green_height - yellow_height
                segments.append(('orange', orange_height, ''))
                segments.append(('yellow', yellow_height, ''))
                segments.append(('green', green_height, fidelity))
            else:
                # "Significant Drift" zone - all red
                segments.append(('red', bar_height, fidelity))

            # Build bar HTML
            graph_html += f'''
            <div class="fidelity-bar">
                <div class="bar-column" style="height: {bar_height}px;"
                     onclick="selectTurn({i})" title="Turn {i}: {fidelity:.3f}">
            '''

            # Add intervention marker if applicable
            if intervention:
                graph_html += '<div class="intervention-marker">⚠️</div>'

            # Add fidelity value label
            graph_html += f'<div class="fidelity-value">{fidelity:.2f}</div>'

            # Add segments
            for color_name, height, label in segments:
                _, color = self.get_color_for_score(
                    {'green': 0.9, 'yellow': 0.75, 'orange': 0.6, 'red': 0.25}[color_name]
                )
                graph_html += f'''
                <div class="bar-segment" style="
                    background-color: {color};
                    height: {height}px;
                ">
                    {label if label else ''}
                </div>
                '''

            graph_html += f'''
                </div>
                <div class="turn-label">T{i}</div>
            </div>
            '''

        graph_html += '</div>'

        # JavaScript for turn selection
        graph_html += '''
        <script>
        function selectTurn(turnNumber) {
            // Send turn selection to Streamlit
            window.parent.postMessage({
                type: 'streamlit:setComponentValue',
                value: turnNumber
            }, '*');
        }
        </script>
        '''

        # Render the graph
        st.markdown(graph_html, unsafe_allow_html=True)

        # Legend
        st.markdown("""
        <div style="
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 10px 0;
            padding: 10px;
            background-color: #1a1a1a;
            border: 1px solid #444;
            border-radius: 8px;
        ">
            <span style="color: #27ae60;">■ ≥0.70 Aligned</span>
            <span style="color: {GOLD};">■ 0.60-0.69 Minor Drift</span>
            <span style="color: {STATUS_MODERATE};">■ 0.50-0.59 Drift Detected</span>
            <span style="color: {STATUS_SEVERE};">■ <0.50 Significant Drift</span>
            <span style="color: {STATUS_MODERATE};">⚠️ Intervention</span>
        </div>
        """, unsafe_allow_html=True)


class TurnByTurnAnalyzer:
    """Provides detailed turn-by-turn analysis with TELOSCOPE controls."""

    def render_turn_detail(self, turn_number: int, turn_data: Dict):
        """
        Render detailed view of a specific turn.

        Args:
            turn_number: The turn to display
            turn_data: Complete data for this turn
        """
        st.markdown(f"""
        <div style="
            background-color: #1a1a1a;
            border: 2px solid {GOLD};
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        ">
            <h3 style="color: {GOLD}; margin: 0;">Turn {turn_number} Analysis</h3>
        </div>
        """, unsafe_allow_html=True)

        # Create columns for metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            fidelity = turn_data.get('fidelity_score', 0.0)
            _, color = self.get_color_for_score(fidelity) if hasattr(self, 'get_color_for_score') else ('green', '#27ae60')
            st.markdown(f"""
            <div style="
                background-color: {color}22;
                border: 2px solid {color};
                border-radius: 8px;
                padding: 10px;
                text-align: center;
            ">
                <div style="color: #888; font-size: 12px;">Fidelity</div>
                <div style="color: {color}; font-size: 24px; font-weight: bold;">
                    {fidelity:.3f}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            response_type = turn_data.get('response_source', 'unknown')
            type_color = '#27ae60' if response_type == 'telos' else '#888'
            st.markdown(f"""
            <div style="
                background-color: {type_color}22;
                border: 2px solid {type_color};
                border-radius: 8px;
                padding: 10px;
                text-align: center;
            ">
                <div style="color: #888; font-size: 12px;">Response</div>
                <div style="color: {type_color}; font-size: 24px; font-weight: bold;">
                    {response_type.upper()}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            test_type = turn_data.get('test_type', 'single_blind')
            st.markdown(f"""
            <div style="
                background-color: #1a1a1a;
                border: 2px solid #666;
                border-radius: 8px;
                padding: 10px;
                text-align: center;
            ">
                <div style="color: #888; font-size: 12px;">Test Type</div>
                <div style="color: #e0e0e0; font-size: 16px;">
                    {test_type.replace('_', ' ').title()}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            preference = turn_data.get('user_preference', '—')
            pref_emoji = {'thumbs_up': '👍', 'neutral': '🤷', 'thumbs_down': '👎'}.get(preference, '—')
            st.markdown(f"""
            <div style="
                background-color: #1a1a1a;
                border: 2px solid #666;
                border-radius: 8px;
                padding: 10px;
                text-align: center;
            ">
                <div style="color: #888; font-size: 12px;">Your Rating</div>
                <div style="font-size: 24px;">
                    {pref_emoji}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Show Steward's interpretation
        if 'steward_interpretation' in turn_data:
            st.markdown("""
            <div style="
                background-color: rgba(255, 215, 0, 0.05);
                border-left: 4px solid {GOLD};
                padding: 15px;
                margin: 20px 0;
            ">
                <div style="color: {GOLD}; font-weight: bold; margin-bottom: 10px;">
                    🤖 Steward's Analysis:
                </div>
                <div style="color: #e0e0e0; line-height: 1.6;">
            """, unsafe_allow_html=True)

            st.markdown(turn_data['steward_interpretation'])

            st.markdown("</div></div>", unsafe_allow_html=True)

        # Show "What Would Have Been" for non-selected TELOS responses
        if turn_data.get('response_source') == 'native' and 'potential_telos_response' in turn_data:
            with st.expander("🔮 What TELOS Would Have Done"):
                st.markdown("""
                <div style="
                    background-color: rgba(76, 175, 80, 0.05);
                    border-left: 4px solid #27ae60;
                    padding: 15px;
                ">
                    <div style="color: #27ae60; font-weight: bold; margin-bottom: 10px;">
                        Potential TELOS Response:
                    </div>
                """, unsafe_allow_html=True)

                st.markdown(turn_data['potential_telos_response'])

                if 'potential_intervention' in turn_data:
                    st.markdown(f"""
                    <div style="
                        margin-top: 15px;
                        padding-top: 15px;
                        border-top: 1px solid #444;
                    ">
                        <strong>Intervention Status:</strong> {
                            '✅ Would have intervened' if turn_data['potential_intervention']
                            else '❌ No intervention needed'
                        }
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)
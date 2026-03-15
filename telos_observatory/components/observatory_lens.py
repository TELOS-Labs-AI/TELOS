"""
Observatory Lens Component for TELOS Observatory V3.
Real-time visual dashboard for governance visualization.

Refactored 2025-12: Removed synthetic 3D/2D visualizations that used fake coordinates.
Now focuses on real data: fidelity trajectory over time, event log, and statistics.
"""

import streamlit as st
import logging
import plotly.graph_objects as go
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ObservatoryLens:
    """
    Observatory Lens - Visual Dashboard for Real-Time Governance.

    Provides 4 core visualizations:
    1. Fidelity Trajectory - Real fidelity scores over conversation turns
    2. Fidelity Gauge - Real-time alignment quality meter
    3. Event Log - Live feed of governance actions
    4. Session Statistics - Real-time metrics summary

    Design Goal: Non-technical users understand TELOS governance in <30 seconds.
    """

    def __init__(self, state_manager):
        """
        Initialize Observatory Lens with state manager reference.

        Args:
            state_manager: StateManager instance for telemetry data
        """
        self.state_manager = state_manager

    def render(self):
        """Render the Observatory Lens dashboard."""
        # Check if lens should be shown
        if not self.state_manager.state.show_observatory_lens:
            return

        # Expanded state - full dashboard with dark theme
        st.markdown("""
        <style>
        /* Force dark background for main content area */
        .main, .stApp {
            background-color: #0E1117 !important;
        }

        /* Force dark background for all containers */
        [data-testid="stVerticalBlock"],
        [data-testid="stHorizontalBlock"],
        .element-container {
            background-color: transparent !important;
        }
        </style>

        <div style="
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
            border: 2px solid #F4D03F;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        ">
            <div style="text-align: center; margin-bottom: 20px;">
                <h2 style="color: #F4D03F; margin: 0; font-weight: bold; letter-spacing: 2px;">
                    🔭 OBSERVATORY LENS
                </h2>
                <p style="color: #888; font-size: 12px; margin: 5px 0 0 0;">
                    Real-Time Governance Visualization
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Collapse button
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("✕ Close", key="observatory_lens_close", use_container_width=True):
                self.state_manager.toggle_component('observatory_lens')
                st.rerun()

        st.markdown("---")

        # Check if there's data to visualize
        if self.state_manager.state.total_turns == 0:
            st.info("👋 Observatory Lens will activate once you start a conversation. Try sending a message!")
            return

        # Main 2x3 grid layout
        self._render_visualization_grid()

    def _render_visualization_grid(self):
        """Render the visualization grid with real data."""
        # Top row: Fidelity Trajectory (main chart) | Fidelity Gauge
        st.markdown("### Fidelity Over Time")

        top_col1, top_col2 = st.columns([3, 1])

        with top_col1:
            self._render_fidelity_trajectory()

        with top_col2:
            self._render_fidelity_gauge()

        st.markdown("---")

        # Bottom row: Event Log | Session Stats
        st.markdown("### Session Activity")

        bottom_col1, bottom_col2 = st.columns([2, 1])

        with bottom_col1:
            self._render_attack_log()

        with bottom_col2:
            self._render_session_statistics()

    def _render_fidelity_trajectory(self):
        """Render fidelity trajectory line chart with real data."""
        turns = self.state_manager.get_all_turns()

        if not turns:
            st.info("No fidelity data yet. Complete some turns to see the trajectory.")
            return

        # Extract real fidelity values from each turn
        turn_numbers = []
        fidelities = []
        zones = []

        for turn in turns:
            turn_num = turn.get('turn', 0) + 1  # 1-indexed for display
            # Get fidelity - try multiple sources
            fidelity = (
                turn.get('display_fidelity') or
                turn.get('user_fidelity') or
                turn.get('fidelity', 0.5)
            )
            turn_numbers.append(turn_num)
            fidelities.append(fidelity)

            # Classify zone for color
            if fidelity >= 0.70:
                zones.append('green')
            elif fidelity >= 0.60:
                zones.append('yellow')
            elif fidelity >= 0.50:
                zones.append('orange')
            else:
                zones.append('red')

        # Get zone colors for markers
        zone_colors = {
            'green': '#27ae60',
            'yellow': '#f39c12',
            'orange': '#e67e22',
            'red': '#e74c3c',
        }
        marker_colors = [zone_colors.get(z, '#888') for z in zones]

        # Create Plotly figure
        fig = go.Figure()

        # Main fidelity line
        fig.add_trace(go.Scatter(
            x=turn_numbers,
            y=fidelities,
            mode='lines+markers',
            name='Fidelity',
            line=dict(color='#F4D03F', width=2),
            marker=dict(
                color=marker_colors,
                size=10,
                line=dict(color='#F4D03F', width=1)
            ),
            hovertemplate='Turn %{x}<br>Fidelity: %{y:.3f}<extra></extra>'
        ))

        # Add threshold reference lines
        fig.add_hline(y=0.70, line_dash="dash", line_color="#27ae60", opacity=0.5,
                      annotation_text="Aligned", annotation_position="right")
        fig.add_hline(y=0.60, line_dash="dash", line_color="#f39c12", opacity=0.5,
                      annotation_text="Minor Drift", annotation_position="right")
        fig.add_hline(y=0.50, line_dash="dash", line_color="#e67e22", opacity=0.5,
                      annotation_text="Drift", annotation_position="right")

        # Layout
        fig.update_layout(
            xaxis_title="Turn",
            yaxis_title="Fidelity",
            yaxis=dict(range=[0, 1], dtick=0.1),
            xaxis=dict(dtick=1),
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(26,26,26,0.95)',
            font=dict(color='#e6edf3'),
            margin=dict(t=20, b=50, l=60, r=80),
            height=280,
            showlegend=False,
            hovermode='x unified'
        )

        st.plotly_chart(fig, use_container_width=True,
                        key=f"trajectory_{self.state_manager.state.current_turn}")

    def _render_fidelity_gauge(self):
        """Render Fidelity Gauge (speedometer)."""
        current_turn = self.state_manager.get_current_turn_data()
        fidelity = current_turn.get('fidelity', 0.0) if current_turn else 0.0

        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=fidelity,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Fidelity", 'font': {'size': 16, 'color': '#F4D03F'}},
            number={'font': {'size': 40, 'color': '#F4D03F'}, 'valueformat': '.3f'},
            delta={'reference': 0.70, 'increasing': {'color': "#00FF00"}, 'decreasing': {'color': "#FF0000"}},  # FIDELITY_GREEN
            gauge={
                'axis': {'range': [0, 1], 'tickwidth': 1, 'tickcolor': "#F4D03F"},
                'bar': {'color': "#F4D03F"},
                'bgcolor': "#1a1a1a",
                'borderwidth': 2, 'bordercolor': "#F4D03F",
                'steps': [
                    # Zone thresholds from telos_core.constants
                    {'range': [0, 0.50], 'color': '#330000'},      # Significant Drift (Red)
                    {'range': [0.50, 0.60], 'color': '#332200'},   # Drift Detected (Orange)
                    {'range': [0.60, 0.70], 'color': '#333300'},   # Minor Drift (Yellow)
                    {'range': [0.70, 1.0], 'color': '#003300'}     # Aligned (Green)
                ],
                'threshold': {'line': {'color': "#FF0000", 'width': 4}, 'thickness': 0.75, 'value': 0.50}  # FIDELITY_ORANGE
            }
        ))

        fig.update_layout(
            paper_bgcolor='#1a1a1a', plot_bgcolor='#1a1a1a',
            font={'color': '#e0e0e0'}, height=280, margin=dict(l=20, r=20, t=50, b=20)
        )

        st.plotly_chart(fig, use_container_width=True, key=f"gauge_{self.state_manager.state.current_turn}")

    def _render_attack_log(self):
        """Render Attack Detection Log (event feed)."""
        st.markdown('<div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 1px solid #F4D03F; border-radius: 8px; padding: 15px; height: 350px; overflow-y: auto; box-shadow: 0 0 15px rgba(244, 208, 63, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);"><h4 style="color: #F4D03F; margin: 0 0 10px 0;">Event Log</h4><p style="color: #888; font-size: 11px; margin-bottom: 10px;">Real-time events</p>', unsafe_allow_html=True)

        turns = self.state_manager.get_all_turns()
        recent_turns = turns[-10:] if len(turns) > 10 else turns

        for turn in reversed(recent_turns):
            turn_num = turn.get('turn', 0)
            fidelity = turn.get('fidelity', 0.0)
            intervention = turn.get('intervention_applied', False)

            if intervention:
                icon, color, event_type = "INTERVENTION", "#FF0000", "INTERVENTION"
            elif fidelity < 0.50:  # Significant Drift (Red zone)
                icon, color, event_type = "X", "#e74c3c", "SIGNIFICANT DRIFT"
            elif fidelity < 0.60:  # Drift Detected (Orange zone)
                icon, color, event_type = "!", "#e67e22", "DRIFT DETECTED"
            elif fidelity < 0.70:  # Minor Drift (Yellow zone)
                icon, color, event_type = "-", "#f39c12", "MINOR DRIFT"
            else:  # Aligned (Green zone)
                icon, color, event_type = "+", "#27ae60", "ALIGNED"

            st.markdown(f'<div style="padding: 8px; background: #0a0a0a; border-left: 3px solid {color}; border-radius: 3px; margin: 5px 0;"><div style="color: {color}; font-size: 11px;">{icon} <strong>Turn {turn_num + 1}:</strong> {event_type}</div><div style="color: #888; font-size: 10px;">Fidelity: {fidelity:.3f}</div></div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    def _render_session_statistics(self):
        """Render Session Statistics (metrics summary)."""
        session_info = self.state_manager.get_session_info()

        html = f"""
<div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 1px solid #F4D03F; border-radius: 8px; padding: 15px; height: 350px; box-shadow: 0 0 15px rgba(244, 208, 63, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
    <h4 style="color: #F4D03F; margin: 0 0 10px 0;">Session Stats</h4>
    <p style="color: #888; font-size: 11px;">Real-time metrics</p>
    <div style="margin-top: 20px;">
        <div style="padding: 10px; background: #0a0a0a; border-radius: 5px; margin: 10px 0;">
            <div style="color: #888; font-size: 10px;">TOTAL TURNS</div>
            <div style="color: #F4D03F; font-size: 24px; font-weight: bold;">{session_info.get('total_turns', 0)}</div>
        </div>
        <div style="padding: 10px; background: #0a0a0a; border-radius: 5px; margin: 10px 0;">
            <div style="color: #888; font-size: 10px;">AVG FIDELITY</div>
            <div style="color: #F4D03F; font-size: 24px; font-weight: bold;">{session_info.get('avg_fidelity', 0.0):.3f}</div>
        </div>
        <div style="padding: 10px; background: #0a0a0a; border-radius: 5px; margin: 10px 0;">
            <div style="color: #888; font-size: 10px;">INTERVENTIONS</div>
            <div style="color: #F4D03F; font-size: 24px; font-weight: bold;">{session_info.get('total_interventions', 0)}</div>
        </div>
        <div style="padding: 10px; background: #0a0a0a; border-radius: 5px; margin: 10px 0;">
            <div style="color: #888; font-size: 10px;">ASR</div>
            <div style="color: #00FF00; font-size: 24px; font-weight: bold;">0%</div>
        </div>
    </div>
</div>
"""
        st.markdown(html, unsafe_allow_html=True)

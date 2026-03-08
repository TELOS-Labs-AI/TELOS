"""
TELOSCOPE SSE Viewer Component
===============================

Adds streaming replay visualization to TELOSCOPE controls.
Shows HOW responses were generated, not just WHAT was generated.

This component integrates seamlessly with existing TELOSCOPE controls
to provide an additional dimension of replay - the streaming experience.
"""

import streamlit as st
import time
import json
from typing import Optional, Dict, Any, List
import plotly.graph_objects as go
from datetime import datetime
import logging

# Import SSE replay manager
from telos_observatory.services.sse_replay_manager import get_sse_manager, SSEEvent

logger = logging.getLogger(__name__)


class TELOSCOPEStreamViewer:
    """
    Streaming replay viewer for TELOSCOPE.

    Complements turn-based replay with token-by-token streaming visualization.
    """

    def __init__(self, state_manager):
        """
        Initialize SSE Viewer with state manager.

        Args:
            state_manager: StateManager instance for session access
        """
        self.state_manager = state_manager
        self.sse_manager = get_sse_manager()

        # Initialize viewer state in session
        if 'sse_viewer_state' not in st.session_state:
            st.session_state.sse_viewer_state = {
                'streaming_mode': False,
                'current_replay': None,
                'replay_speed': 1.0,
                'show_timeline': False,
                'show_metrics': True
            }

    def render(self):
        """Render SSE viewer within TELOSCOPE controls."""
        # Check if we have SSE data for current turn
        current_turn = self.state_manager.state.current_turn
        session_id = self.state_manager.state.session_id

        has_sse_data = self._check_sse_availability(session_id, current_turn + 1)

        # Section header with streaming toggle
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("### 🌊 Streaming Replay")
        with col2:
            streaming_enabled = st.toggle(
                "Enable Streaming",
                value=st.session_state.sse_viewer_state['streaming_mode'],
                key="sse_streaming_toggle",
                help="Toggle between instant and streaming replay"
            )
            st.session_state.sse_viewer_state['streaming_mode'] = streaming_enabled

        if not streaming_enabled:
            st.info("Enable streaming mode to see token-by-token replay")
            return

        # Check data availability
        if not has_sse_data:
            # Offer simulation mode
            st.warning("No SSE data recorded for this turn")
            if st.button("🎭 Simulate Streaming", key="simulate_sse"):
                self._simulate_streaming_for_turn(session_id, current_turn + 1)
            return

        # Streaming controls
        col1, col2, col3 = st.columns(3)

        with col1:
            speed = st.select_slider(
                "Replay Speed",
                options=[0.5, 1.0, 1.5, 2.0, 3.0, 5.0],
                value=st.session_state.sse_viewer_state['replay_speed'],
                key="sse_replay_speed"
            )
            st.session_state.sse_viewer_state['replay_speed'] = speed

        with col2:
            show_timeline = st.checkbox(
                "Show Timeline",
                value=st.session_state.sse_viewer_state['show_timeline'],
                key="sse_show_timeline"
            )
            st.session_state.sse_viewer_state['show_timeline'] = show_timeline

        with col3:
            show_metrics = st.checkbox(
                "Show Metrics",
                value=st.session_state.sse_viewer_state['show_metrics'],
                key="sse_show_metrics"
            )
            st.session_state.sse_viewer_state['show_metrics'] = show_metrics

        # Display metrics if enabled
        if show_metrics:
            self._render_streaming_metrics(session_id, current_turn + 1)

        # Timeline visualization if enabled
        if show_timeline:
            self._render_streaming_timeline(session_id, current_turn + 1)

        # Replay controls
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            if st.button("▶️ Start Streaming Replay", key="start_sse_replay", use_container_width=True):
                self._start_streaming_replay(session_id, current_turn + 1, speed)

        # Streaming output area
        if st.session_state.sse_viewer_state.get('current_replay'):
            self._render_streaming_output()

    def _check_sse_availability(self, session_id: str, turn_number: int) -> bool:
        """Check if SSE data exists for a turn."""
        metrics = self.sse_manager.get_session_metrics(session_id, turn_number)
        return metrics is not None

    def _render_streaming_metrics(self, session_id: str, turn_number: int):
        """Render streaming performance metrics."""
        metrics = self.sse_manager.get_session_metrics(session_id, turn_number)

        if not metrics:
            return

        st.markdown("**📊 Streaming Performance Metrics**")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Tokens/sec",
                f"{metrics['tokens_per_second']:.1f}",
                help="Average token generation rate"
            )

        with col2:
            st.metric(
                "First Token",
                f"{metrics['time_to_first_token_ms']}ms",
                help="Time to first token"
            )

        with col3:
            st.metric(
                "Total Duration",
                f"{metrics['total_duration_ms']/1000:.1f}s",
                help="Total streaming duration"
            )

        with col4:
            interventions = metrics['intervention_count']
            color = "🟢" if interventions == 0 else "🔴"
            st.metric(
                "Stream Interventions",
                f"{color} {interventions}",
                help="Mid-stream governance interventions"
            )

    def _render_streaming_timeline(self, session_id: str, turn_number: int):
        """Render interactive streaming timeline visualization."""
        timeline_data = self.sse_manager.export_session_timeline(session_id, turn_number)

        if not timeline_data:
            st.warning("No timeline data available")
            return

        # Create Plotly timeline chart
        fig = go.Figure()

        # Separate events by type
        token_events = [e for e in timeline_data if e['type'] == 'token_batch']
        governance_events = [e for e in timeline_data if e['type'] == 'governance']
        intervention_events = [e for e in timeline_data if e['type'] == 'intervention']

        # Add token generation trace
        if token_events:
            fig.add_trace(go.Scatter(
                x=[e['time_ms']/1000 for e in token_events],
                y=[1] * len(token_events),
                mode='markers',
                name='Tokens',
                marker=dict(
                    size=6,
                    color='#27ae60',
                    symbol='circle'
                ),
                text=[e.get('content', '')[:50] for e in token_events],
                hovertemplate='<b>%{text}</b><br>Time: %{x:.2f}s<extra></extra>'
            ))

        # Add governance decision trace
        if governance_events:
            fig.add_trace(go.Scatter(
                x=[e['time_ms']/1000 for e in governance_events],
                y=[1.5] * len(governance_events),
                mode='markers',
                name='Governance',
                marker=dict(
                    size=10,
                    color='#FFC107',
                    symbol='diamond'
                ),
                text=[e['decision'] for e in governance_events],
                hovertemplate='<b>%{text}</b><br>Time: %{x:.2f}s<extra></extra>'
            ))

        # Add intervention trace
        if intervention_events:
            fig.add_trace(go.Scatter(
                x=[e['time_ms']/1000 for e in intervention_events],
                y=[2] * len(intervention_events),
                mode='markers',
                name='Interventions',
                marker=dict(
                    size=12,
                    color='#F44336',
                    symbol='x'
                ),
                text=[e.get('reason', 'Intervention') for e in intervention_events],
                hovertemplate='<b>%{text}</b><br>Time: %{x:.2f}s<extra></extra>'
            ))

        # Update layout
        fig.update_layout(
            title="Streaming Timeline",
            xaxis_title="Time (seconds)",
            yaxis=dict(
                showticklabels=False,
                range=[0.5, 2.5],
                showgrid=False
            ),
            height=200,
            margin=dict(l=0, r=0, t=30, b=30),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#ffffff'),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        st.plotly_chart(fig, use_container_width=True)

    def _start_streaming_replay(self, session_id: str, turn_number: int, speed: float):
        """Start streaming replay in a container."""
        # Create placeholder for streaming output
        output_container = st.empty()
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Get session data
        session = self.sse_manager._sessions.get((session_id, turn_number))
        if not session:
            session = self.sse_manager._load_session(session_id, turn_number)

        if not session:
            st.error("Failed to load streaming session")
            return

        # Replay with visualization
        token_buffer = ""
        token_count = 0
        total_tokens = session.token_count
        start_time = time.time()

        status_text.text(f"Streaming {total_tokens} tokens at {speed}x speed...")

        # Process events
        for event in self.sse_manager.replay_session(session_id, turn_number, speed):
            if event.event_type == 'token':
                token_buffer += event.content
                token_count += 1

                # Update display
                output_container.markdown(
                    f"""
                    <div style="
                        background-color: rgba(13, 17, 23, 0.95);
                        border: 1px solid #27ae60;
                        border-radius: 8px;
                        padding: 15px;
                        font-family: monospace;
                        white-space: pre-wrap;
                        word-wrap: break-word;
                        min-height: 200px;
                        max-height: 400px;
                        overflow-y: auto;
                    ">
                        {token_buffer}<span style="color: #27ae60;">▊</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # Update progress
                progress = token_count / total_tokens if total_tokens > 0 else 0
                progress_bar.progress(progress)

            elif event.event_type == 'governance':
                # Show inline governance notification
                if event.metadata.get('intervention_triggered'):
                    st.warning(f"⚠️ Intervention: {event.metadata.get('reason', 'Governance intervention triggered')}")

            elif event.event_type == 'completion':
                # Final display without cursor
                output_container.markdown(
                    f"""
                    <div style="
                        background-color: rgba(13, 17, 23, 0.95);
                        border: 1px solid #27ae60;
                        border-radius: 8px;
                        padding: 15px;
                        font-family: monospace;
                        white-space: pre-wrap;
                        word-wrap: break-word;
                        min-height: 200px;
                        max-height: 400px;
                        overflow-y: auto;
                    ">
                        {token_buffer}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                progress_bar.progress(1.0)

                # Show completion stats
                elapsed = time.time() - start_time
                actual_tps = token_count / elapsed if elapsed > 0 else 0
                status_text.success(
                    f"✅ Streaming complete: {token_count} tokens in {elapsed:.1f}s "
                    f"({actual_tps:.1f} tokens/sec)"
                )

    def _simulate_streaming_for_turn(self, session_id: str, turn_number: int):
        """Simulate streaming for a turn without SSE data."""
        # Get turn data
        turn_idx = turn_number - 1
        if turn_idx >= len(self.state_manager.state.turns):
            st.error("Invalid turn number")
            return

        turn_data = self.state_manager.state.turns[turn_idx]
        response_text = turn_data.get('response', '')

        if not response_text:
            st.warning("No response text to simulate")
            return

        # Create simulated streaming session
        st.info("🎭 Simulating streaming experience...")

        output_container = st.empty()
        progress_bar = st.progress(0)

        # Start recording for future replay
        self.sse_manager.start_recording(session_id, turn_number)

        # Simulate streaming
        token_buffer = ""
        tokens = response_text.split()
        total_tokens = len(tokens)

        for i, token in enumerate(tokens):
            # Record token
            self.sse_manager.record_token(token + " ")

            # Display
            token_buffer += token + " "
            output_container.markdown(
                f"""
                <div style="
                    background-color: rgba(13, 17, 23, 0.95);
                    border: 1px solid #FFC107;
                    border-radius: 8px;
                    padding: 15px;
                    font-family: monospace;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    min-height: 200px;
                ">
                    <small style="color: #FFC107;">⚠️ SIMULATED STREAMING</small><br><br>
                    {token_buffer}<span style="color: #FFC107;">▊</span>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Update progress
            progress_bar.progress((i + 1) / total_tokens)

            # Simulate timing
            time.sleep(0.03)  # ~30 tokens/sec

        # Stop recording
        session = self.sse_manager.stop_recording()

        if session:
            st.success(f"✅ Simulated streaming saved: {session.token_count} tokens")
            # Refresh to show metrics
            st.rerun()

    def _render_streaming_output(self):
        """Render the current streaming replay output."""
        replay_data = st.session_state.sse_viewer_state.get('current_replay')
        if not replay_data:
            return

        st.markdown(
            f"""
            <div style="
                background-color: rgba(13, 17, 23, 0.95);
                border: 1px solid #27ae60;
                border-radius: 8px;
                padding: 15px;
                font-family: monospace;
                white-space: pre-wrap;
                word-wrap: break-word;
            ">
                {replay_data}
            </div>
            """,
            unsafe_allow_html=True
        )
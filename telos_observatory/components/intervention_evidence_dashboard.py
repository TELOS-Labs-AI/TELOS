"""
Intervention Evidence Dashboard for TELOSCOPE
==============================================

Streamlit component for browsing and analyzing governance interventions.
Integrates with GovernanceTraceCollector for real-time and historical data.

Features:
- Intervention timeline visualization
- Fidelity trajectory chart
- Filtering by intervention level
- Session export functionality
- Report generation
"""

import streamlit as st
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class InterventionEvidenceDashboard:
    """
    Dashboard for governance intervention evidence.

    Provides visualization and analysis tools for TELOS governance data.
    """

    def __init__(self, state_manager=None):
        """
        Initialize dashboard.

        Args:
            state_manager: Optional StateManager for session access
        """
        self.state_manager = state_manager
        self._trace_collector = None
        self._init_collector()

    def _init_collector(self):
        """Initialize connection to GovernanceTraceCollector."""
        try:
            from telos_core.governance_trace import get_trace_collector
            session_id = st.session_state.get('session_id', 'default')
            self._trace_collector = get_trace_collector(session_id=session_id)
        except Exception as e:
            logger.debug(f"Trace collector not available: {e}")
            self._trace_collector = None

    def render(self):
        """Render the intervention evidence dashboard."""
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
            border: 1px solid #F4D03F;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
        ">
            <h3 style="color: #F4D03F; margin: 0; text-align: center;">
                Intervention Evidence Dashboard
            </h3>
            <p style="color: #888; font-size: 12px; margin: 5px 0 0 0; text-align: center;">
                Governance transparency and audit trail
            </p>
        </div>
        """, unsafe_allow_html=True)

        if not self._trace_collector:
            st.warning("Governance trace collector not available. Start a session to begin tracking.")
            return

        # Get current data
        stats = self._trace_collector.get_session_stats()
        interventions = self._trace_collector.get_interventions()
        fidelity_trajectory = self._trace_collector.get_fidelity_trajectory()

        # Summary metrics row
        self._render_summary_metrics(stats)

        # Tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs([
            "Fidelity Trajectory",
            "Intervention Log",
            "Session Export",
            "Settings"
        ])

        with tab1:
            self._render_fidelity_chart(fidelity_trajectory)

        with tab2:
            self._render_intervention_log(interventions)

        with tab3:
            self._render_export_options(stats)

        with tab4:
            self._render_settings()

    def _render_summary_metrics(self, stats: Dict[str, Any]):
        """Render summary metrics row."""
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Total Events",
                stats.get('total_events', 0),
                help="Total governance events recorded"
            )

        with col2:
            avg_fidelity = stats.get('average_fidelity', 0)
            color = self._get_fidelity_color(avg_fidelity)
            st.metric(
                "Avg Fidelity",
                f"{avg_fidelity:.3f}",
                help="Average fidelity across all turns"
            )

        with col3:
            interventions = stats.get('total_interventions', 0)
            delta_color = "inverse" if interventions > 0 else "normal"
            st.metric(
                "Interventions",
                interventions,
                help="Total governance interventions"
            )

        with col4:
            st.metric(
                "Turns",
                stats.get('total_turns', 0),
                help="Total conversation turns"
            )

    def _render_fidelity_chart(self, fidelity_trajectory: List[Dict[str, Any]]):
        """Render fidelity trajectory chart."""
        st.markdown("### Fidelity Over Time")

        if not fidelity_trajectory:
            st.info("No fidelity data yet. Complete some turns to see the trajectory.")
            return

        # Try to use Plotly for interactive chart
        try:
            import plotly.graph_objects as go

            fig = go.Figure()

            # Extract data
            turns = [d.get('turn', i+1) for i, d in enumerate(fidelity_trajectory)]
            fidelities = [d.get('fidelity', 0.5) for d in fidelity_trajectory]
            zones = [d.get('zone', 'unknown') for d in fidelity_trajectory]

            # Color markers by zone
            colors = [self._zone_to_color(z) for z in zones]

            # Add trace
            fig.add_trace(go.Scatter(
                x=turns,
                y=fidelities,
                mode='lines+markers',
                name='Fidelity',
                line=dict(color='#F4D03F', width=2),
                marker=dict(
                    color=colors,
                    size=10,
                    line=dict(color='white', width=1)
                ),
                hovertemplate='Turn %{x}<br>Fidelity: %{y:.3f}<extra></extra>'
            ))

            # Add threshold lines
            thresholds = [
                (0.70, '#27ae60', 'Green Zone'),
                (0.60, '#f39c12', 'Yellow Zone'),
                (0.50, '#e67e22', 'Orange Zone'),
            ]

            for y, color, name in thresholds:
                fig.add_hline(
                    y=y,
                    line_dash="dash",
                    line_color=color,
                    opacity=0.5,
                    annotation_text=name,
                    annotation_position="right"
                )

            # Layout
            fig.update_layout(
                xaxis_title="Turn Number",
                yaxis_title="Fidelity Score",
                yaxis=dict(range=[0, 1]),
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(13,17,23,0.95)',
                font=dict(color='#e6edf3'),
                margin=dict(t=30, b=50, l=60, r=30),
                height=350,
            )

            st.plotly_chart(fig, use_container_width=True)

        except ImportError:
            # Fallback to simple display
            st.markdown("**Fidelity Values:**")
            for d in fidelity_trajectory:
                turn = d.get('turn', '?')
                fidelity = d.get('fidelity', 0)
                zone = d.get('zone', 'unknown')
                color = self._zone_to_color(zone)
                st.markdown(
                    f"Turn {turn}: `{fidelity:.3f}` "
                    f"<span style='color:{color}'>{zone.upper()}</span>",
                    unsafe_allow_html=True
                )

    def _render_intervention_log(self, interventions: List[Dict[str, Any]]):
        """Render intervention log table."""
        st.markdown("### Intervention Log")

        if not interventions:
            st.success("No interventions triggered. Session maintaining alignment.")
            return

        # Filter controls
        col1, col2 = st.columns([2, 1])
        with col1:
            level_filter = st.multiselect(
                "Filter by Level",
                options=['correct', 'intervene', 'escalate', 'hard_block'],
                default=[],
                key="intervention_level_filter"
            )
        with col2:
            sort_order = st.selectbox(
                "Sort",
                options=['Newest First', 'Oldest First'],
                key="intervention_sort"
            )

        # Filter interventions
        filtered = interventions
        if level_filter:
            filtered = [i for i in filtered if i.get('level', '').lower() in level_filter]

        # Sort
        if sort_order == 'Newest First':
            filtered = list(reversed(filtered))

        # Display
        if not filtered:
            st.info("No interventions match the current filter.")
            return

        for i, intervention in enumerate(filtered):
            level = intervention.get('level', 'unknown')
            level_color = self._level_to_color(level)

            with st.expander(
                f"Turn {intervention.get('turn', '?')} - {level.upper()}",
                expanded=i == 0
            ):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown(f"""
                    **Level:** <span style='color:{level_color}'>{level.upper()}</span>
                    **Fidelity:** {intervention.get('fidelity', 0):.3f}
                    **Reason:** {intervention.get('reason', 'Unknown')}
                    """, unsafe_allow_html=True)

                with col2:
                    st.markdown(f"""
                    **Action:** {intervention.get('action', 'Unknown')}
                    **Time:** {intervention.get('timestamp', 'Unknown')[:19]}
                    """)

    def _render_export_options(self, stats: Dict[str, Any]):
        """Render session export options."""
        st.markdown("### Export Session Evidence")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### HTML Report")
            st.markdown(
                "Generate a self-contained HTML report with charts "
                "and full governance trail."
            )

            if st.button("Generate HTML Report", key="generate_html_report"):
                self._generate_html_report()

        with col2:
            st.markdown("#### JSONL Export")
            st.markdown(
                "Export raw governance events in JSONL format "
                "for external analysis."
            )

            if st.button("Download JSONL", key="download_jsonl"):
                self._download_jsonl()

        st.markdown("---")

        # AI Summary
        st.markdown("#### AI Session Summary")
        st.markdown(
            "Generate an AI-powered summary of this session's "
            "governance patterns."
        )

        if st.button("Generate Summary", key="generate_ai_summary"):
            self._generate_ai_summary()

    def _render_settings(self):
        """Render dashboard settings."""
        st.markdown("### Dashboard Settings")

        # Privacy mode
        st.markdown("#### Privacy Mode")
        current_mode = st.session_state.get('trace_privacy_mode', 'deltas_only')

        privacy_mode = st.radio(
            "Select privacy level for governance logging:",
            options=['deltas_only', 'hashed', 'full'],
            index=['deltas_only', 'hashed', 'full'].index(current_mode),
            key="privacy_mode_selector",
            help="""
            - **deltas_only**: Only fidelity metrics, no content (recommended)
            - **hashed**: Content replaced with SHA-256 hashes
            - **full**: Complete data including conversation content
            """
        )

        if privacy_mode != current_mode:
            st.session_state['trace_privacy_mode'] = privacy_mode
            if self._trace_collector:
                try:
                    from telos_core.evidence_schema import PrivacyMode
                    mode_map = {
                        'deltas_only': PrivacyMode.DELTAS_ONLY,
                        'hashed': PrivacyMode.HASHED,
                        'full': PrivacyMode.FULL,
                    }
                    self._trace_collector.set_privacy_mode(mode_map[privacy_mode])
                    st.success(f"Privacy mode updated to: {privacy_mode}")
                except Exception as e:
                    st.error(f"Failed to update privacy mode: {e}")

        # Trace file location
        st.markdown("#### Storage Location")
        if self._trace_collector:
            trace_file = self._trace_collector.trace_file
            st.code(str(trace_file), language=None)
        else:
            st.info("Trace collector not initialized")

    def _generate_html_report(self):
        """Generate and offer HTML report for download."""
        if not self._trace_collector:
            st.error("Trace collector not available")
            return

        try:
            from telos_observatory.services.report_generator import GovernanceReportGenerator

            with st.spinner("Generating report..."):
                generator = GovernanceReportGenerator()
                session_data = self._trace_collector.export_to_dict()
                report_path = generator.generate_report(session_data)

                # Read and offer download
                with open(report_path, 'r') as f:
                    html_content = f.read()

                st.download_button(
                    label="Download HTML Report",
                    data=html_content,
                    file_name=report_path.name,
                    mime="text/html",
                )

                st.success(f"Report generated: {report_path.name}")

        except Exception as e:
            st.error(f"Report generation failed: {e}")
            logger.error(f"Report generation error: {e}")

    def _download_jsonl(self):
        """Offer JSONL file for download."""
        if not self._trace_collector:
            st.error("Trace collector not available")
            return

        try:
            trace_file = self._trace_collector.trace_file

            if trace_file.exists():
                with open(trace_file, 'r') as f:
                    jsonl_content = f.read()

                st.download_button(
                    label="Download JSONL File",
                    data=jsonl_content,
                    file_name=trace_file.name,
                    mime="application/x-jsonlines",
                )
            else:
                st.warning("No trace file available yet")

        except Exception as e:
            st.error(f"Download failed: {e}")

    def _generate_ai_summary(self):
        """Generate and display AI summary."""
        if not self._trace_collector:
            st.error("Trace collector not available")
            return

        try:
            from telos_observatory.services.session_summarizer import SessionSummarizer

            with st.spinner("Generating AI summary..."):
                summarizer = SessionSummarizer()
                session_data = self._trace_collector.export_to_dict()
                summary = summarizer.summarize_session(session_data)

                # Display summary
                st.markdown(f"### {summary.get('title', 'Session Summary')}")
                st.markdown(summary.get('description', ''))

                if summary.get('key_topics'):
                    st.markdown("**Key Topics:**")
                    for topic in summary['key_topics']:
                        st.markdown(f"- {topic}")

                st.markdown(f"""
                **Fidelity Trajectory:** {summary.get('fidelity_trajectory', 'unknown')}
                **Intervention Pattern:** {summary.get('intervention_pattern', 'unknown')}
                **Generated by:** {summary.get('generated_by', 'unknown')}
                """)

        except Exception as e:
            st.error(f"Summary generation failed: {e}")
            logger.error(f"AI summary error: {e}")

    @staticmethod
    def _get_fidelity_color(fidelity: float) -> str:
        """Get color for fidelity value."""
        if fidelity >= 0.70:
            return "#27ae60"
        elif fidelity >= 0.60:
            return "#f39c12"
        elif fidelity >= 0.50:
            return "#e67e22"
        else:
            return "#e74c3c"

    @staticmethod
    def _zone_to_color(zone: str) -> str:
        """Convert zone name to color."""
        zone_colors = {
            'green': '#27ae60',
            'yellow': '#f39c12',
            'orange': '#e67e22',
            'red': '#e74c3c',
        }
        return zone_colors.get(zone.lower(), '#888888')

    @staticmethod
    def _level_to_color(level: str) -> str:
        """Convert intervention level to color."""
        level_colors = {
            'none': '#27ae60',
            'monitor': '#27ae60',
            'correct': '#f39c12',
            'intervene': '#e67e22',
            'escalate': '#e74c3c',
            'hard_block': '#e74c3c',
        }
        return level_colors.get(level.lower(), '#888888')


def render_intervention_dashboard(state_manager=None):
    """
    Convenience function to render the intervention evidence dashboard.

    Args:
        state_manager: Optional StateManager for session access
    """
    dashboard = InterventionEvidenceDashboard(state_manager)
    dashboard.render()

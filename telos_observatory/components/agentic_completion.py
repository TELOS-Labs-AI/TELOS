"""
Agentic Completion Screen
==========================
Summary screen after completing 10 agentic governance steps.
Uses exact same styles as beta_completion.py.
Includes forensic report download (HTML + JSONL).
"""
import json
import streamlit as st
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class AgenticCompletion:
    """Agentic session completion with summary statistics."""

    def render(self):
        """Render completion screen with session stats."""

        # Main congratulations header (exact same style as beta_completion.py)
        st.markdown("""
        <div style="text-align: center; padding: 40px 0;">
            <h1 style="color: #F4D03F; font-size: 48px; margin: 0;">
                Thank You
            </h1>
            <p style="color: #e0e0e0; font-size: 24px; margin-top: 20px;">
                for Experiencing Agentic Governance
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Session complete message (exact same card style as beta_completion.py)
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
                    border: 2px solid #F4D03F; border-radius: 12px; padding: 30px; margin: 20px auto; max-width: 700px;">
            <p style="color: #e0e0e0; font-size: 18px; line-height: 1.8; text-align: center;">
                Your 10-step agentic session is complete. You have experienced live
                multi-dimensional governance with real-time fidelity monitoring across
                purpose, scope, tool selection, chain continuity, and boundary enforcement.
            </p>
            <p style="color: #e0e0e0; font-size: 18px; line-height: 1.8; text-align: center; margin-top: 20px;">
                Your participation helps advance agentic AI governance research.
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Stats summary (same card style as beta_completion.py stats)
        self._render_stats()

        # Forensic report downloads
        self._render_report_downloads()

        # Contact information (exact same as beta_completion.py)
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
                    border: 2px solid #F4D03F; border-radius: 12px; padding: 30px; margin: 30px auto; max-width: 700px;">
            <h2 style="color: #F4D03F; text-align: center; margin-bottom: 25px;">
                Get in Touch
            </h2>
            <div style="display: flex; flex-direction: column; gap: 15px; align-items: center;">
                <p style="color: #e0e0e0; font-size: 18px; margin: 0;">
                    <span style="color: #F4D03F;">General Inquiries:</span>
                    <a href="mailto:JB@telos-labs.ai" style="color: #27ae60; text-decoration: none;">
                        JB@telos-labs.ai
                    </a>
                </p>
                <p style="color: #e0e0e0; font-size: 18px; margin: 0;">
                    <span style="color: #F4D03F;">Collaboration:</span>
                    <a href="mailto:JB@telos-labs.ai" style="color: #27ae60; text-decoration: none;">
                        JB@telos-labs.ai
                    </a>
                </p>
                <p style="color: #e0e0e0; font-size: 18px; margin: 0;">
                    <span style="color: #F4D03F;">GitHub:</span>
                    <a href="https://github.com/telos-ai-labs/telos" target="_blank" style="color: #27ae60; text-decoration: none;">
                        github.com/telos-ai-labs/telos
                    </a>
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Spacer
        st.markdown("<div style='margin: 40px 0;'></div>", unsafe_allow_html=True)

        # GitHub link button (exact same style as beta_completion.py)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.markdown("""
            <a href="https://github.com/telos-ai-labs/telos" target="_blank" style="text-decoration: none;">
                <div style="
                    background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
                    border: 2px solid #F4D03F;
                    border-radius: 8px;
                    padding: 15px 30px;
                    text-align: center;
                    cursor: pointer;
                    transition: all 0.3s ease;
                " onmouseover="this.style.boxShadow='0 0 15px rgba(244, 208, 63, 0.4)'" onmouseout="this.style.boxShadow='none'">
                    <span style="color: #F4D03F; font-size: 18px; font-weight: 600;">
                        View on GitHub
                    </span>
                </div>
            </a>
            """, unsafe_allow_html=True)

    def _render_stats(self):
        """Render session statistics summary."""
        steps_completed = st.session_state.get('agentic_current_step', 0)

        # Collect per-step data
        purpose_scores = []
        tool_scores = []
        chain_scis = []
        steps_blocked = 0
        steps_redirected = 0

        for i in range(1, steps_completed + 1):
            try:
                from telos_observatory.main import get_agentic_step_data
                step_data = get_agentic_step_data(i)
            except ImportError:
                step_data = st.session_state.get(f'agentic_step_{i}_data', {})
            if not step_data:
                continue

            pf = step_data.get('purpose_fidelity')
            if pf is not None:
                purpose_scores.append(pf)

            tf = step_data.get('tool_fidelity')
            if tf is not None:
                tool_scores.append(tf)

            sci = step_data.get('chain_sci')
            if sci is not None:
                chain_scis.append(sci)

            if step_data.get('was_blocked', False):
                steps_blocked += 1
            if step_data.get('was_redirected', False):
                steps_redirected += 1

        avg_purpose = f"{int(sum(purpose_scores) / len(purpose_scores) * 100)}%" if purpose_scores else "---"
        avg_tool = f"{int(sum(tool_scores) / len(tool_scores) * 100)}%" if tool_scores else "---"
        chain_continuity = f"{int(sum(chain_scis) / len(chain_scis) * 100)}%" if chain_scis else "---"

        # Stats card (same card style as beta_completion.py stats section)
        if steps_completed > 0:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
                        border: 1px solid #F4D03F; border-radius: 8px; padding: 20px; margin: 20px auto; max-width: 400px; text-align: center;">
                <h3 style="color: #F4D03F; margin-bottom: 15px;">Session Stats</h3>
                <p style="color: #e0e0e0; font-size: 24px; margin: 0;">
                    <strong>{steps_completed}</strong> steps completed
                </p>
                <p style="color: #e0e0e0; font-size: 18px; margin: 10px 0 0 0;">
                    Avg Purpose Fidelity: <strong>{avg_purpose}</strong>
                </p>
                <p style="color: #e0e0e0; font-size: 18px; margin: 5px 0 0 0;">
                    Avg Tool Fidelity: <strong>{avg_tool}</strong>
                </p>
                <p style="color: #e0e0e0; font-size: 18px; margin: 5px 0 0 0;">
                    Chain Continuity: <strong>{chain_continuity}</strong>
                </p>
                <p style="color: #e0e0e0; font-size: 18px; margin: 5px 0 0 0;">
                    Steps Blocked: <strong>{steps_blocked}</strong>
                </p>
                <p style="color: #e0e0e0; font-size: 18px; margin: 5px 0 0 0;">
                    Steps Redirected: <strong>{steps_redirected}</strong>
                </p>
            </div>
            """, unsafe_allow_html=True)

    def _render_report_downloads(self):
        """Render forensic report download buttons (HTML + JSONL)."""
        turns = self._collect_session_data()
        if not turns:
            return

        template = st.session_state.get('agentic_current_template', {})
        session_id = st.session_state.get('agentic_session_id', 'unknown')

        try:
            from telos_observatory.services.agentic_report_generator import (
                AgenticForensicReportGenerator,
            )
            gen = AgenticForensicReportGenerator()

            html_content = gen.generate_report_html(
                session_id=session_id,
                template_id=template.get('id', 'unknown'),
                agent_name=template.get('name', 'Agent'),
                agent_purpose=template.get('purpose', ''),
                agent_scope=template.get('scope', ''),
                boundaries=template.get('boundaries', []),
                tools=[t.get('name', '') for t in template.get('tools', [])],
                turns=turns,
            )

            jsonl_lines = []
            for turn in turns:
                jsonl_lines.append(json.dumps({
                    "event_type": "agentic_governance_decision",
                    "session_id": session_id,
                    "step": turn.get("step", 0),
                    "decision": turn.get("decision", ""),
                    "effective_fidelity": turn.get("effective_fidelity", 0.0),
                    "drift_level": turn.get("drift_level", "NORMAL"),
                    "drift_magnitude": turn.get("drift_magnitude", 0.0),
                    "selected_tool": turn.get("selected_tool"),
                    "boundary_triggered": turn.get("boundary_triggered", False),
                }))
            jsonl_content = "\n".join(jsonl_lines)

            st.markdown("""
            <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
                        border: 1px solid #F4D03F; border-radius: 8px; padding: 20px; margin: 20px auto; max-width: 700px; text-align: center;">
                <h3 style="color: #F4D03F; margin-bottom: 15px;">Forensic Report</h3>
                <p style="color: #e0e0e0; font-size: 14px; margin-bottom: 15px;">
                    Download the full 9-section governance forensic report for this session.
                </p>
            </div>
            """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="Download HTML Report",
                    data=html_content,
                    file_name=f"forensic_{session_id}.html",
                    mime="text/html",
                    use_container_width=True,
                )
            with col2:
                st.download_button(
                    label="Download JSONL Log",
                    data=jsonl_content,
                    file_name=f"forensic_{session_id}.jsonl",
                    mime="application/jsonl",
                    use_container_width=True,
                )
        except Exception as e:
            logger.error(f"Failed to generate forensic report: {e}")

    @staticmethod
    def _collect_session_data() -> List[Dict[str, Any]]:
        """Collect all per-turn step data from session state."""
        steps_completed = st.session_state.get('agentic_current_step', 0)
        turns = []
        for i in range(1, steps_completed + 1):
            try:
                from telos_observatory.main import get_agentic_step_data
                step_data = get_agentic_step_data(i)
            except ImportError:
                step_data = st.session_state.get(f'agentic_step_{i}_data')
            if step_data:
                turns.append(step_data)
        return turns

"""
Beta Completion Component for TELOS Observatory BETA
=====================================================

Displays thank you screen after completing 10-turn Beta session.
Provides contact information and option to start new session.
"""

import streamlit as st
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BetaCompletion:
    """Handles beta completion flow with thank you screen."""

    def __init__(self, state_manager):
        """Initialize with state manager reference.

        Args:
            state_manager: StateManager instance for session operations
        """
        self.state_manager = state_manager

    def render(self):
        """Render beta completion thank you screen with contact info."""

        # Main congratulations header
        st.markdown("""
        <div style="text-align: center; padding: 40px 0;">
            <h1 style="color: #F4D03F; font-size: 48px; margin: 0;">
                Thank You
            </h1>
            <p style="color: #e0e0e0; font-size: 24px; margin-top: 20px;">
                for Experiencing TELOS Beta
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Session complete message
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
                    border: 2px solid #F4D03F; border-radius: 12px; padding: 30px; margin: 20px auto; max-width: 700px;">
            <p style="color: #e0e0e0; font-size: 18px; line-height: 1.8; text-align: center;">
                Your 10-turn session is complete. You've experienced live AI governance
                with real-time fidelity monitoring and Steward interventions.
            </p>
            <p style="color: #e0e0e0; font-size: 18px; line-height: 1.8; text-align: center; margin-top: 20px;">
                We're actively developing expanded capabilities for constitutional AI oversight.
                Your participation helps advance this research.
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Stats summary if available
        current_turn = st.session_state.get('beta_current_turn', 1) - 1
        if current_turn > 0:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
                        border: 1px solid #F4D03F; border-radius: 8px; padding: 20px; margin: 20px auto; max-width: 400px; text-align: center;">
                <h3 style="color: #F4D03F; margin-bottom: 15px;">Session Stats</h3>
                <p style="color: #e0e0e0; font-size: 24px; margin: 0;">
                    <strong>{current_turn}</strong> turns completed
                </p>
            </div>
            """, unsafe_allow_html=True)

        # Contact information
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
                    <a href="https://github.com/TELOS-Labs-AI/telos" target="_blank" style="color: #27ae60; text-decoration: none;">
                        github.com/TELOS-Labs-AI/telos
                    </a>
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Spacer
        st.markdown("<div style='margin: 40px 0;'></div>", unsafe_allow_html=True)

        # GitHub link button (replacing Start New Session)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.markdown("""
            <a href="https://github.com/TELOS-Labs-AI/telos" target="_blank" style="text-decoration: none;">
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

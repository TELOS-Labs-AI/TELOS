"""
Sidebar Actions Component for BETA Mode
========================================

Ultra-clean version with only essential controls:
- Observatory Lens toggle
- GitHub Research Question link
"""

import streamlit as st
import logging

logger = logging.getLogger(__name__)


class SidebarActionsBeta:
    """Minimal sidebar for BETA testing - only essential controls."""

    def __init__(self, state_manager):
        self.state_manager = state_manager

    def render(self):
        """Render the minimal BETA sidebar controls."""
        with st.sidebar:
            # Title with telescope emoji
            st.markdown("""
            <div style="text-align: center; margin-bottom: 20px;">
                <span style="font-size: 48px;">🔭</span>
                <h2 style="color: #F4D03F; margin-top: 10px;">Steward</h2>
            </div>
            """, unsafe_allow_html=True)

            # Beta testing notice
            st.markdown("""
            <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
                        border: 1px solid #F4D03F; border-radius: 8px;
                        padding: 10px; margin-bottom: 20px;">
                <div style="color: #F4D03F; font-size: 14px; text-align: center;">
                    🧪 BETA Testing Mode
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")

            # Observatory Lens toggle
            lens_icon = "🔍" if not self.state_manager.state.show_observatory_lens else "✕"
            lens_label = "Observatory Lens" if not self.state_manager.state.show_observatory_lens else "Close Observatory Lens"

            if st.button(f"{lens_icon} {lens_label}", use_container_width=True,
                        help="Toggle metrics and governance visualization"):
                self.state_manager.toggle_component('observatory_lens')
                st.rerun()

            st.markdown("---")

            # GitHub Research Question Link
            if st.button("🔗 GitHub Repository", use_container_width=True,
                        help="View research question and documentation"):
                st.markdown("""
                <script>
                window.open('https://github.com/TELOS-Labs-AI/telos', '_blank');
                </script>
                """, unsafe_allow_html=True)
                st.info("Opening TelosLabs research repository...")

            # Beta progress tracking (if session manager available)
            if hasattr(self.state_manager.state, 'beta_session_manager') and \
               self.state_manager.state.beta_session_manager:
                st.markdown("---")
                self._render_beta_progress()

    def _render_beta_progress(self):
        """Render beta testing progress metrics."""
        try:
            session_manager = self.state_manager.state.beta_session_manager
            session = session_manager.get_or_create_session(
                user_id=st.session_state.get('user_id', 'anonymous'),
                session_id=self.state_manager.state.beta_session_id
            )

            # Calculate progress
            turn_count = session.turn_count
            feedback_count = len(session.feedback_data)

            # Progress bars
            st.markdown("### 📊 Beta Progress")

            # Turn progress (calibration phase)
            if turn_count <= 10:
                st.progress(turn_count / 10,
                          text=f"Calibration: {turn_count}/10 turns")
            else:
                st.progress(1.0, text="✅ Calibration complete")

            # Feedback progress
            if feedback_count < 50:
                st.progress(feedback_count / 50,
                          text=f"Feedback: {feedback_count}/50")
            else:
                st.progress(1.0, text="✅ Testing complete")

            # Test condition indicator (only show after calibration)
            if turn_count > 10 and session.test_condition:
                condition_display = {
                    'single_blind_baseline': '🔵 Single-Blind A',
                    'single_blind_telos': '🟢 Single-Blind B',
                    'head_to_head': '⚖️ Head-to-Head'
                }
                st.info(f"Test Mode: {condition_display.get(session.test_condition, session.test_condition)}")

        except Exception as e:
            logger.error(f"Error rendering beta progress: {e}")
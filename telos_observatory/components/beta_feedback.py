"""
Beta Feedback Component
=======================

UI components for collecting user feedback during A/B testing.

Features:
- Single-blind rating (thumbs up/down)
- Head-to-head comparison
- Optional qualitative feedback
- Conversation goal validation
"""

import streamlit as st
import html
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class BetaFeedbackUI:
    """UI components for beta testing feedback collection."""

    def __init__(self, beta_session_manager):
        """
        Initialize beta feedback UI.

        Args:
            beta_session_manager: BetaSessionManager instance
        """
        self.beta_manager = beta_session_manager

    def render_conversation_goal_input(self):
        """
        Render conversation goal input at the start of a conversation.

        This captures what the user is trying to accomplish.
        """
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
            border: 2px solid #F4D03F;
            border-radius: 15px;
            padding: 25px;
            margin: 19px 0;
            box-shadow: 0 0 6px rgba(255, 215, 0, 0.3);
        ">
            <div style="text-align: center; margin-bottom: 15px;">
                <div style="font-size: 36px;">🎯</div>
                <div style="color: #F4D03F; font-size: 22px; font-weight: bold;">
                    Welcome to TELOS Beta Testing
                </div>
            </div>
            <div style="color: #e0e0e0; font-size: 16px; line-height: 1.6; margin-bottom: 19px;">
                Before we begin, help us understand what you're trying to accomplish in this conversation.
                This helps us measure whether TELOS keeps conversations on track.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Goal input
        with st.form(key="conversation_goal_form"):
            goal_text = st.text_area(
                "What are you trying to accomplish in this conversation?",
                placeholder="Example: I want to learn about TELOS governance and how it could help with AI alignment...",
                height=100,
                key="beta_goal_input"
            )

            submit_goal = st.form_submit_button("Start Conversation", use_container_width=True)

            if submit_goal and goal_text.strip():
                # Store conversation goal
                from observatory.beta_testing import ConversationGoal

                goal = ConversationGoal(
                    goal_text=goal_text.strip(),
                    timestamp=datetime.now().isoformat()
                )

                # Get or create beta session
                if 'beta_session' not in st.session_state:
                    st.session_state.beta_session = self.beta_manager.start_session()

                st.session_state.beta_session.conversation_goal = goal

                # Assign test condition
                condition = self.beta_manager.assign_test_condition(st.session_state.beta_session)

                # Mark as started
                st.session_state.beta_goal_set = True

                logger.info(f"Beta goal set: {goal_text[:50]}... | Condition: {condition}")
                st.rerun()

    def render_single_blind_feedback(self, turn_number: int, response_data: Dict[str, Any]):
        """
        Render single-blind feedback UI (thumbs up/down).

        User doesn't know if they're seeing baseline or TELOS.

        Args:
            turn_number: Current turn number
            response_data: Response data with metrics
        """
        # Check if feedback already given for this turn
        feedback_key = f"beta_feedback_{turn_number}"
        if st.session_state.get(feedback_key):
            return  # Already rated

        st.markdown("<div style='margin-top: 19px;'></div>", unsafe_allow_html=True)

        # Feedback UI
        st.markdown("""
        <div style="
            background-color: #1a1a1a;
            border: 1px solid #F4D03F;
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
        ">
            <div style="color: #F4D03F; font-size: 16px; font-weight: bold; margin-bottom: 10px;">
                How would you rate this response?
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 1, 4])

        with col1:
            if st.button("👍", key=f"thumbs_up_{turn_number}", use_container_width=True, help="Helpful response"):
                self._record_single_blind_feedback(
                    turn_number=turn_number,
                    rating="thumbs_up",
                    response_data=response_data
                )
                st.session_state[feedback_key] = True
                st.rerun()

        with col2:
            if st.button("👎", key=f"thumbs_down_{turn_number}", use_container_width=True, help="Not helpful"):
                self._record_single_blind_feedback(
                    turn_number=turn_number,
                    rating="thumbs_down",
                    response_data=response_data
                )
                st.session_state[feedback_key] = True
                st.rerun()

        with col3:
            # Optional text feedback
            text_feedback = st.text_input(
                "Optional: Why did you rate this way?",
                key=f"feedback_text_{turn_number}",
                placeholder="Brief explanation (optional)...",
                label_visibility="collapsed"
            )
            if text_feedback and st.session_state.get(feedback_key):
                # Update feedback with text
                session = st.session_state.get('beta_session')
                if session and session.feedback_items:
                    session.feedback_items[-1].feedback_text = text_feedback

    def render_head_to_head_comparison(self, turn_number: int, response_data: Dict[str, Any]):
        """
        Render head-to-head comparison UI.

        Shows both baseline and TELOS responses side-by-side.
        User picks their favorite.

        Args:
            turn_number: Current turn number
            response_data: Dict with baseline_response and telos_response
        """
        # Check if feedback already given
        feedback_key = f"beta_feedback_{turn_number}"
        if st.session_state.get(feedback_key):
            return

        st.markdown("<div style='margin-top: 19px;'></div>", unsafe_allow_html=True)

        # Instruction
        st.markdown("""
        <div style="
            background-color: #1a1a1a;
            border: 1px solid #F4D03F;
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
            text-align: center;
        ">
            <div style="color: #F4D03F; font-size: 18px; font-weight: bold; margin-bottom: 5px;">
                Which response do you prefer?
            </div>
            <div style="color: #888; font-size: 14px;">
                Choose the response that better addresses your needs
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Randomize which side shows baseline vs TELOS
        randomize_key = f"beta_randomize_{turn_number}"
        if randomize_key not in st.session_state:
            import random
            st.session_state[randomize_key] = random.choice([True, False])

        show_baseline_left = st.session_state[randomize_key]

        if show_baseline_left:
            response_a = response_data['baseline_response']
            response_b = response_data['telos_response']
            response_a_source = "baseline"
            response_b_source = "telos"
        else:
            response_a = response_data['telos_response']
            response_b = response_data['baseline_response']
            response_a_source = "telos"
            response_b_source = "baseline"

        # Side-by-side comparison
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown(f"""
<div style="background-color: #1a1a1a; padding: 15px; border-radius: 10px; margin: 0; border: 2px solid #F4D03F; min-height: 200px;">
    <div style="color: #F4D03F; font-size: 16px; margin-bottom: 10px; font-weight: bold; text-align: center;">
        Response A
    </div>
    <div style="color: #fff; font-size: 16px; white-space: pre-wrap;">
        {html.escape(response_a)}
    </div>
</div>
""", unsafe_allow_html=True)

            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

            if st.button("✓ I Prefer Response A", key=f"prefer_a_{turn_number}", use_container_width=True):
                self._record_head_to_head_feedback(
                    turn_number=turn_number,
                    preferred="response_a",
                    response_a_source=response_a_source,
                    response_b_source=response_b_source,
                    response_a_text=response_a,
                    response_b_text=response_b,
                    response_data=response_data
                )
                st.session_state[feedback_key] = True
                st.rerun()

        with col_b:
            st.markdown(f"""
<div style="background-color: #1a1a1a; padding: 15px; border-radius: 10px; margin: 0; border: 2px solid #F4D03F; min-height: 200px;">
    <div style="color: #F4D03F; font-size: 16px; margin-bottom: 10px; font-weight: bold; text-align: center;">
        Response B
    </div>
    <div style="color: #fff; font-size: 16px; white-space: pre-wrap;">
        {html.escape(response_b)}
    </div>
</div>
""", unsafe_allow_html=True)

            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

            if st.button("✓ I Prefer Response B", key=f"prefer_b_{turn_number}", use_container_width=True):
                self._record_head_to_head_feedback(
                    turn_number=turn_number,
                    preferred="response_b",
                    response_a_source=response_a_source,
                    response_b_source=response_b_source,
                    response_a_text=response_a,
                    response_b_text=response_b,
                    response_data=response_data
                )
                st.session_state[feedback_key] = True
                st.rerun()

        # Optional text feedback
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        text_feedback = st.text_input(
            "Optional: Why did you prefer this response?",
            key=f"feedback_text_h2h_{turn_number}",
            placeholder="Brief explanation (optional)..."
        )

    def render_conversation_goal_validation(self):
        """
        Render conversation goal validation at end of conversation.

        Asks user if they accomplished what they set out to do.
        """
        session = st.session_state.get('beta_session')
        if not session or not session.conversation_goal:
            return

        # Check if already validated
        if session.conversation_goal.accomplished is not None:
            return

        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
            border: 2px solid #F4D03F;
            border-radius: 15px;
            padding: 25px;
            margin: 19px 0;
            box-shadow: 0 0 6px rgba(255, 215, 0, 0.3);
        ">
            <div style="text-align: center; margin-bottom: 15px;">
                <div style="font-size: 36px;">🎯</div>
                <div style="color: #F4D03F; font-size: 20px; font-weight: bold;">
                    Did you accomplish your goal?
                </div>
            </div>
            <div style="color: #e0e0e0; font-size: 16px; line-height: 1.6; margin-bottom: 15px;">
                <strong>Your goal was:</strong><br>
                "{}"
            </div>
        </div>
        """.format(html.escape(session.conversation_goal.goal_text)), unsafe_allow_html=True)

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            if st.button("1 - Not at all", key="goal_rating_1", use_container_width=True):
                self._record_goal_validation(1)
                st.rerun()

        with col2:
            if st.button("2 - Somewhat", key="goal_rating_2", use_container_width=True):
                self._record_goal_validation(2)
                st.rerun()

        with col3:
            if st.button("3 - Moderately", key="goal_rating_3", use_container_width=True):
                self._record_goal_validation(3)
                st.rerun()

        with col4:
            if st.button("4 - Mostly", key="goal_rating_4", use_container_width=True):
                self._record_goal_validation(4)
                st.rerun()

        with col5:
            if st.button("5 - Completely", key="goal_rating_5", use_container_width=True):
                self._record_goal_validation(5)
                st.rerun()

    def _record_single_blind_feedback(
        self,
        turn_number: int,
        rating: str,
        response_data: Dict[str, Any]
    ):
        """Record single-blind feedback."""
        from observatory.beta_testing import FeedbackData

        session = st.session_state.get('beta_session')
        if not session:
            return

        # Determine which response was shown
        condition = session.test_condition
        if condition == "single_blind_baseline":
            response_source = "baseline"
            response_text = response_data['baseline_response']
            fidelity = response_data['baseline_fidelity']
        else:  # single_blind_telos
            response_source = "telos"
            response_text = response_data['telos_response']
            fidelity = response_data['telos_fidelity']

        feedback = FeedbackData(
            turn_number=turn_number,
            timestamp=datetime.now().isoformat(),
            test_condition=condition,
            rating=rating,
            response_source=response_source,
            user_message=response_data.get('user_message', ''),
            response_text=response_text,
            fidelity=fidelity,
            baseline_fidelity=response_data['baseline_fidelity'],
            telos_fidelity=response_data['telos_fidelity'],
            drift_detected=response_data.get('drift_detected', False)
        )

        self.beta_manager.record_feedback(session, feedback)
        logger.info(f"Recorded single-blind feedback: {rating} (source: {response_source})")

    def _record_head_to_head_feedback(
        self,
        turn_number: int,
        preferred: str,
        response_a_source: str,
        response_b_source: str,
        response_a_text: str,
        response_b_text: str,
        response_data: Dict[str, Any]
    ):
        """Record head-to-head feedback."""
        from observatory.beta_testing import FeedbackData

        session = st.session_state.get('beta_session')
        if not session:
            return

        feedback = FeedbackData(
            turn_number=turn_number,
            timestamp=datetime.now().isoformat(),
            test_condition="head_to_head",
            preferred_response=preferred,
            response_a_source=response_a_source,
            response_b_source=response_b_source,
            user_message=response_data.get('user_message', ''),
            response_a_text=response_a_text,
            response_b_text=response_b_text,
            baseline_fidelity=response_data['baseline_fidelity'],
            telos_fidelity=response_data['telos_fidelity'],
            drift_detected=response_data.get('drift_detected', False)
        )

        self.beta_manager.record_feedback(session, feedback)

        # Determine which was preferred
        preferred_source = response_a_source if preferred == "response_a" else response_b_source
        logger.info(f"Recorded head-to-head feedback: preferred {preferred} (source: {preferred_source})")

    def _record_goal_validation(self, rating: int):
        """Record conversation goal accomplishment rating."""
        session = st.session_state.get('beta_session')
        if not session or not session.conversation_goal:
            return

        session.conversation_goal.accomplished = rating
        session.conversation_goal.accomplishment_feedback = st.session_state.get('goal_feedback_text', '')

        logger.info(f"Recorded goal validation: {rating}/5")

    def render_beta_stats_dashboard(self):
        """Render researcher dashboard with beta testing stats."""
        st.markdown("""
        <div style="
            background-color: #2d2d2d;
            border: 2px solid #F4D03F;
            border-radius: 10px;
            padding: 19px;
            margin-bottom: 15px;
        ">
            <div style="color: #F4D03F; font-size: 22px; font-weight: bold; text-align: center;">
                📊 Beta Testing Dashboard
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Get stats
        stats = self.beta_manager.get_session_stats()

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(f"""
<div style="background-color: #1a1a1a; border: 1px solid #F4D03F; border-radius: 8px; padding: 15px; text-align: center;">
    <div style="font-size: 28px; font-weight: bold; color: #F4D03F;">{stats['total_sessions']}</div>
    <div style="color: #e0e0e0; font-size: 14px;">Total Sessions</div>
</div>
""", unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
<div style="background-color: #1a1a1a; border: 1px solid #F4D03F; border-radius: 8px; padding: 15px; text-align: center;">
    <div style="font-size: 28px; font-weight: bold; color: #F4D03F;">{stats['total_feedback_items']}</div>
    <div style="color: #e0e0e0; font-size: 14px;">Feedback Items</div>
</div>
""", unsafe_allow_html=True)

        with col3:
            thumbs_up = stats['preference_summary']['thumbs_up']
            thumbs_down = stats['preference_summary']['thumbs_down']
            total_thumbs = thumbs_up + thumbs_down
            approval_rate = (thumbs_up / total_thumbs * 100) if total_thumbs > 0 else 0

            st.markdown(f"""
<div style="background-color: #1a1a1a; border: 1px solid #F4D03F; border-radius: 8px; padding: 15px; text-align: center;">
    <div style="font-size: 28px; font-weight: bold; color: #27ae60;">{approval_rate:.1f}%</div>
    <div style="color: #e0e0e0; font-size: 14px;">Approval Rate</div>
</div>
""", unsafe_allow_html=True)

        with col4:
            telos_pref = stats['preference_summary']['preferred_telos']
            baseline_pref = stats['preference_summary']['preferred_baseline']
            total_h2h = telos_pref + baseline_pref
            telos_win_rate = (telos_pref / total_h2h * 100) if total_h2h > 0 else 0

            st.markdown(f"""
<div style="background-color: #1a1a1a; border: 1px solid #F4D03F; border-radius: 8px; padding: 15px; text-align: center;">
    <div style="font-size: 28px; font-weight: bold; color: #F4D03F;">{telos_win_rate:.1f}%</div>
    <div style="color: #e0e0e0; font-size: 14px;">TELOS Preference</div>
</div>
""", unsafe_allow_html=True)

        # Export button
        st.markdown("<div style='margin-top: 19px;'></div>", unsafe_allow_html=True)

        if st.button("📥 Export Beta Test Data", use_container_width=True):
            export_path = self.beta_manager.export_sessions()
            st.success(f"Exported to: {export_path}")

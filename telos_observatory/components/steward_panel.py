"""
Steward Panel Component for TELOS Observatory V3.
Provides a helpful AI guide accessible via handshake emoji button.
"""

import streamlit as st
from datetime import datetime
from telos_observatory.services.steward_llm import StewardLLM
import html


class StewardPanel:
    """Side panel with Steward assistant for TELOS guidance."""

    def __init__(self, state_manager):
        """Initialize with state manager reference.

        Args:
            state_manager: StateManager instance for session operations
        """
        self.state_manager = state_manager

        # Initialize LLM service (lazy loading)
        if 'steward_llm' not in st.session_state:
            try:
                st.session_state.steward_llm = StewardLLM()
                st.session_state.steward_llm_enabled = True
            except ValueError as e:
                # API key not configured
                st.session_state.steward_llm = None
                st.session_state.steward_llm_enabled = False
                st.session_state.steward_error = str(e)

    def render_button(self):
        """Render button is now integrated in conversation_display.py - this method is deprecated."""
        pass

    def render_panel(self):
        """Render the Steward chat panel in a column."""
        # Initialize chat history if not exists
        if 'steward_chat_history' not in st.session_state:
            # Check if this is a drift event context (slide 8)
            drift_context = st.session_state.get('slide_7_steward_context') == 'drift_event'

            if drift_context:
                # Drift event walkthrough message for slide 8
                initial_message = """**Notice what just happened:**

YOUR User Fidelity dropped significantly when you asked about quantum physics - you drifted from your own stated goal of understanding TELOS. Meanwhile, my AI Fidelity would drop if I answered about physics instead of redirecting you back.

TELOS tracks both our alignments but only intervenes on mine. This dual measurement helps you see when you're veering from your goals while keeping me focused on serving them.

**The Alignment Lens shows how our fidelity scores interact in real-time.**"""
            else:
                # Default greeting for normal Steward access
                initial_message = 'Hello! I am Steward, your TELOS guide. I\'m here to help you understand the TELOS framework, navigate the Observatory interface, and answer any questions about what you\'re seeing on your screen. Feel free to ask me anything!'

            st.session_state.steward_chat_history = [
                {
                    'role': 'assistant',
                    'content': initial_message,
                    'timestamp': datetime.now().isoformat()
                }
            ]

        # Chat history - direct display without heavy container
        for message in st.session_state.steward_chat_history:
            safe_content = html.escape(str(message['content']))
            if message['role'] == 'assistant':
                st.markdown(f"""
                <div class="message-container" style="background-color: rgba(255, 215, 0, 0.1); border: 1px solid #F4D03F; border-radius: 8px; padding: 12px; margin-bottom: 15px;">
                    <strong style="color: #F4D03F; font-size: 18px;">Steward:</strong><br>
                    <span style="color: #F4D03F; font-size: 16px; line-height: 1.6;">{safe_content}</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="message-container" style="background-color: rgba(255, 255, 255, 0.05); border: 1px solid #666; border-radius: 8px; padding: 12px; margin-bottom: 15px;">
                    <strong style="color: #e0e0e0; font-size: 18px;">You:</strong><br>
                    <span style="color: #e0e0e0; font-size: 16px; line-height: 1.6;">{safe_content}</span>
                </div>
                """, unsafe_allow_html=True)

        # Small spacing before input
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

        with st.form(key="steward_form", clear_on_submit=True):
            user_input = st.text_input(
                "Ask Steward anything...",
                placeholder="Type your question here...",
                label_visibility="collapsed",
                key="steward_input_form"
            )

            submit = st.form_submit_button("Send", use_container_width=True)

            if submit and user_input:
                # Add user message
                st.session_state.steward_chat_history.append({
                    'role': 'user',
                    'content': user_input,
                    'timestamp': datetime.now().isoformat()
                })

                # Get Steward response with LLM
                if st.session_state.steward_llm_enabled:
                    # Gather context about current screen state
                    context = self._gather_context()

                    try:
                        # Get response from LLM (non-streaming for now, can add streaming later)
                        steward_response = st.session_state.steward_llm.get_response(
                            user_message=user_input,
                            conversation_history=st.session_state.steward_chat_history[:-1],  # Exclude the message we just added
                            context=context
                        )
                    except Exception as e:
                        steward_response = "I apologize, but I encountered an error generating a response. Please try again."
                else:
                    # Fallback if LLM not configured
                    steward_response = f"I'm currently in setup mode. {st.session_state.get('steward_error', 'Please configure the MISTRAL_API_KEY to enable full Steward functionality.')}"

                st.session_state.steward_chat_history.append({
                    'role': 'assistant',
                    'content': steward_response,
                    'timestamp': datetime.now().isoformat()
                })

                st.rerun()

        # Close Steward button at bottom of chat area
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        if st.button("Close Steward", key="close_steward_bottom", use_container_width=True, help="Close Steward panel"):
            st.session_state.steward_panel_open = False
            # Clear drift context and chat history so next open is fresh
            if 'slide_7_steward_context' in st.session_state:
                del st.session_state.slide_7_steward_context
            if 'steward_chat_history' in st.session_state:
                del st.session_state.steward_chat_history
            st.rerun()

    def _gather_context(self) -> dict:
        """Gather context about current screen state for Steward.

        Returns:
            dict: Context information including active tab, metrics, etc.
        """
        context = {}

        # Get active tab
        context['active_tab'] = st.session_state.get('active_tab', 'Unknown')

        # Get current turn info from state manager
        if hasattr(self.state_manager.state, 'current_turn'):
            context['current_turn'] = self.state_manager.state.current_turn

        if hasattr(self.state_manager.state, 'total_turns'):
            context['total_turns'] = self.state_manager.state.total_turns

        # Get latest metrics if available
        if hasattr(self.state_manager.state, 'turns') and self.state_manager.state.turns:
            latest_turn = self.state_manager.state.turns[-1]
            if 'fidelity' in latest_turn:
                context['fidelity'] = latest_turn['fidelity']

        # Get PA status
        if hasattr(self.state_manager.state, 'metadata'):
            convergence_turn = self.state_manager.state.metadata.get('convergence_turn', 7)
            current_turn = context.get('current_turn', 0)
            context['pa_status'] = "Established" if current_turn >= convergence_turn else "Calibrating"

        return context

    def hide_sidebar_when_open(self):
        """Apply CSS to hide sidebar when Steward panel is open."""
        if st.session_state.get('steward_panel_open', False):
            st.markdown("""
            <style>
            /* Hide sidebar when Steward is open */
            [data-testid="stSidebar"] {
                display: none !important;
            }
            </style>
            """, unsafe_allow_html=True)

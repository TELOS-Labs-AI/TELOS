"""
Beta Steward Panel Component for TELOS Observatory V3 BETA Mode.
Specialized Steward interface for BETA testers with proper context awareness.
"""

import streamlit as st
from datetime import datetime
from telos_observatory.services.beta_steward_llm import BetaStewardLLM
from telos_observatory.services.beta_dual_attractor import derive_ai_pa_from_user_pa, compute_pa_embeddings
from telos_core.semantic_interpreter import interpret as semantic_interpret, get_exemplar
import html
import re


# Zone color mapping for fidelity scores
ZONE_COLORS = {
    'green': '#2ecc71',   # Bright green
    'yellow': '#f1c40f',  # Yellow (standard Steward color)
    'orange': '#e67e22',  # Orange
    'red': '#e74c3c',     # Red
}


def _md_to_html(text: str) -> str:
    """Convert basic markdown to HTML for display in Steward panel.

    Handles: **bold**, *italic*, `code`, [[zone:value]] colored scores, and line breaks.
    """
    # Escape HTML first to prevent injection
    text = html.escape(text)

    # Zone-colored scores: [[green:0.856]] -> colored span
    def replace_zone_score(match):
        zone = match.group(1)
        value = match.group(2)
        color = ZONE_COLORS.get(zone, '#F4D03F')  # Default to yellow
        return f'<span style="color: {color}; font-weight: bold; font-size: 1.1em;">{value}</span>'

    text = re.sub(r'\[\[(\w+):([^\]]+)\]\]', replace_zone_score, text)

    # Bold: **text** -> <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic: *text* -> <i>text</i>
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    # Code: `text` -> <code>text</code>
    text = re.sub(r'`(.+?)`', r'<code style="background: rgba(0,0,0,0.3); padding: 2px 4px; border-radius: 3px;">\1</code>', text)
    # Line breaks
    text = text.replace('\n', '<br>')
    return text


class BetaStewardPanel:
    """Side panel with Beta Steward assistant for BETA mode guidance."""

    def __init__(self):
        """Initialize Beta Steward (no state_manager needed - uses session state directly)."""
        # Initialize LLM service (lazy loading)
        if 'beta_steward_llm' not in st.session_state:
            try:
                st.session_state.beta_steward_llm = BetaStewardLLM()
                st.session_state.beta_steward_llm_enabled = True
            except ValueError as e:
                st.session_state.beta_steward_llm = None
                st.session_state.beta_steward_llm_enabled = False
                st.session_state.beta_steward_error = str(e)

    def render_panel(self):
        """Render the Beta Steward chat panel."""
        # Check if opened from an intervention "Why?" button
        # Pop it immediately to prevent duplicate processing
        intervention_turn = st.session_state.pop('steward_intervention_turn', None)

        # Track whether this panel session was opened from "Ask Steward why"
        # This persists for the duration of the panel being open
        if intervention_turn is not None:
            st.session_state.steward_opened_from_why = True
            # Clear existing chat history when opened from "Why?" button
            # This ensures a fresh start with just the why explanation
            if 'beta_steward_chat_history' in st.session_state:
                del st.session_state.beta_steward_chat_history

        # Initialize chat history if not exists
        if 'beta_steward_chat_history' not in st.session_state:
            if intervention_turn:
                # Opened from "Why?" button - provide detailed explanation
                initial_message = self._build_why_explanation(intervention_turn)
            else:
                # Standard greeting - minimal
                initial_message = "I'm Steward. Ask me anything about what you're seeing."

            st.session_state.beta_steward_chat_history = [
                {
                    'role': 'assistant',
                    'content': initial_message,
                    'timestamp': datetime.now().isoformat()
                }
            ]

        # Minimal top spacing - reduced to eliminate gap issues (was 15px)
        st.markdown("<div style='margin-top: 4px;'></div>", unsafe_allow_html=True)

        # Chat history display - glassmorphism effect matching main conversation
        for message in st.session_state.beta_steward_chat_history:
            if message['role'] == 'assistant':
                # Convert markdown to HTML for proper rendering
                formatted_content = _md_to_html(message['content'])
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid #F4D03F; border-radius: 10px; padding: 15px; margin-bottom: 15px; box-shadow: 0 0 15px rgba(244, 208, 63, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
                    <span style="color: #e0e0e0; font-size: 20px; line-height: 1.6;">{formatted_content}</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid #666; border-radius: 10px; padding: 15px; margin-bottom: 15px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
                    <strong style="color: #e0e0e0; font-size: 20px;">You:</strong><br>
                    <span style="color: #e0e0e0; font-size: 20px; line-height: 1.6;">{html.escape(message['content'])}</span>
                </div>
                """, unsafe_allow_html=True)

        # Show contemplating animation RIGHT AFTER chat history (where response will appear)
        # This keeps user's message visible and shows Steward is "thinking"
        if st.session_state.get('steward_pending_response', False):
            st.markdown("""
<style>
@keyframes steward-border-pulse {
    0%, 100% {
        border-color: #888;
        box-shadow: 0 0 6px rgba(136, 136, 136, 0.3);
    }
    50% {
        border-color: #F4D03F;
        box-shadow: 0 0 6px rgba(255, 215, 0, 0.4);
    }
}
@keyframes steward-text-pulse {
    0%, 100% {
        color: #F4D03F;
    }
    50% {
        color: #888;
    }
}
.steward-contemplating-border {
    animation: steward-border-pulse 2s ease-in-out infinite;
}
.steward-contemplating-text {
    animation: steward-text-pulse 2s ease-in-out infinite;
}
</style>
<div class="steward-contemplating-border" style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 2px solid #888; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
    <span class="steward-contemplating-text" style="font-size: 20px; font-style: italic; color: #F4D03F;">
        Contemplating...
    </span>
</div>
""", unsafe_allow_html=True)

        # Show "Shift Focus to This" button if in orange/red zone
        # This preserves user agency - they can pivot if they genuinely want to
        if self._should_show_shift_focus_button():
            st.markdown("<div style='margin-top: 10px; margin-bottom: 10px;'></div>", unsafe_allow_html=True)

            # Get user's last drifted input for context
            drift_input = self._get_last_drifted_input()
            short_topic = drift_input[:30] + ('...' if len(drift_input) > 30 else '') if drift_input else "this topic"

            if st.button(
                f"Shift Focus to This",
                key="steward_panel_shift_focus",
                help=f"Update session purpose to match what you're actually interested in",
                use_container_width=True
            ):
                self._handle_shift_focus(drift_input)
                st.rerun()

        # Input form - stacked layout matching main chat (text area above, Send button below)
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

        # CSS to ensure form button is visible and clickable
        st.markdown("""
        <style>
        /* Ensure Steward form Send button is visible */
        [data-testid="stForm"] button[kind="secondaryFormSubmit"],
        [data-testid="stForm"] button {
            background-color: #2d2d2d !important;
            color: #F4D03F !important;
            border: 1px solid #F4D03F !important;
            opacity: 1 !important;
        }
        [data-testid="stForm"] button:hover {
            box-shadow: 0 0 8px #F4D03F !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # Use a form with clear_on_submit=True for clean UX
        # Capture return value directly from text_area (same pattern as main conversation)
        with st.form(key="beta_steward_form", clear_on_submit=True):
            user_input_raw = st.text_area(
                "Ask Steward anything...",
                placeholder="",
                label_visibility="collapsed",
                key="beta_steward_input_form",
                height=100  # Multi-line input
            )
            submitted = st.form_submit_button("Send", use_container_width=True)

        # Handle form submission
        if submitted:
            # Use the captured input directly from the text_area widget return value
            user_input = user_input_raw.strip() if user_input_raw else ''

            if user_input:
                # Add user message to chat history
                st.session_state.beta_steward_chat_history.append({
                    'role': 'user',
                    'content': user_input,
                    'timestamp': datetime.now().isoformat()
                })
                # Set pending flag to trigger contemplating animation on next render
                st.session_state.steward_pending_response = True
                st.session_state.steward_pending_input = user_input
                st.rerun()

        # Add JavaScript to submit form on Enter key (Shift+Enter for new line)
        import streamlit.components.v1 as components
        components.html("""
        <script>
        (function() {
            // Find the Send button within the same form as the textarea
            function findSendButton(textarea) {
                let container = textarea.closest('form') || textarea.closest('[data-testid]') || textarea.parentElement;
                for (let i = 0; i < 10 && container; i++) {
                    const btn = container.querySelector('button');
                    if (btn) {
                        const text = btn.textContent || btn.innerText;
                        if (text.includes('Send')) {
                            return btn;
                        }
                    }
                    container = container.parentElement;
                }
                return null;
            }

            function setupEnterHandler() {
                const doc = window.parent.document;
                // Find all textareas
                const textareas = doc.querySelectorAll('textarea');
                textareas.forEach(function(textarea) {
                    if (textarea.dataset.stewardEnterSetup) return;
                    textarea.dataset.stewardEnterSetup = 'true';

                    textarea.addEventListener('keydown', function(e) {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            // Prevent submission if input is empty
                            if (!textarea.value || !textarea.value.trim()) {
                                e.preventDefault();
                                return;
                            }
                            e.preventDefault();
                            e.stopPropagation();

                            // Find the Send button in the same form as this textarea
                            const btn = findSendButton(textarea);
                            if (btn && !btn.disabled) {
                                btn.click();
                                return;
                            }
                        }
                    }, true);
                });
            }

            // Run immediately and also after delays to catch dynamic content
            setupEnterHandler();
            setTimeout(setupEnterHandler, 500);
            setTimeout(setupEnterHandler, 1000);
        })();
        </script>
        """, height=0)

        # Fetch response when pending - use st.spinner for real-time loading feedback
        if st.session_state.get('steward_pending_response', False):
            # Use Streamlit's spinner which updates the UI in real-time during blocking calls
            with st.spinner("Steward is contemplating..."):
                # Fetch the actual response
                user_input = st.session_state.steward_pending_input
                if st.session_state.beta_steward_llm_enabled:
                    context = self._gather_beta_context()

                    try:
                        steward_response = st.session_state.beta_steward_llm.get_response(
                            user_message=user_input,
                            conversation_history=st.session_state.beta_steward_chat_history[:-1],
                            context=context
                        )
                    except Exception as e:
                        steward_response = f"I apologize, but I encountered an error: {str(e)}. Please try again."
                else:
                    steward_response = f"I'm currently in setup mode. {st.session_state.get('beta_steward_error', 'Please configure the MISTRAL_API_KEY.')}"

            st.session_state.beta_steward_chat_history.append({
                'role': 'assistant',
                'content': steward_response,
                'timestamp': datetime.now().isoformat()
            })

            # Clear pending flags
            st.session_state.steward_pending_response = False
            st.session_state.steward_pending_input = None
            st.rerun()

        # Close Steward button at bottom of chat area
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        if st.button("Close Steward", key="close_beta_steward_bottom", use_container_width=True, help="Close Steward panel"):
            st.session_state.beta_steward_panel_open = False
            # Keep chat history so context is preserved when reopened!
            # Only clear the "opened from why" flag
            if 'steward_opened_from_why' in st.session_state:
                del st.session_state.steward_opened_from_why
            st.rerun()

    def _gather_beta_context(self) -> dict:
        """Gather BETA-specific context for Steward.

        Returns:
            dict: Context including PA, current metrics, turn info, last user input,
                  AND full turn history for multi-turn awareness
        """
        import logging
        logger = logging.getLogger(__name__)

        context = {}

        # Get the established PA
        pa = st.session_state.get('primacy_attractor', {})
        if pa:
            context['primacy_attractor'] = pa

        # Get current turn number (this is the NEXT turn to play, so completed = current - 1)
        current_turn = st.session_state.get('beta_current_turn', 1)
        context['current_turn'] = current_turn
        completed_turns = current_turn - 1

        # DEBUG: Log what we're collecting (use print for guaranteed visibility)
        print(f"🔍 STEWARD CONTEXT: beta_current_turn={current_turn}, completed_turns={completed_turns}")
        logger.info(f"🔍 STEWARD CONTEXT: beta_current_turn={current_turn}, completed_turns={completed_turns}")

        # DEBUG: Also log all beta_turn_X_data keys in session state
        beta_keys = [k for k in st.session_state.keys() if k.startswith('beta_turn_') and k.endswith('_data')]
        print(f"🔍 STEWARD CONTEXT: Found beta turn keys in session: {beta_keys}")
        logger.info(f"🔍 STEWARD CONTEXT: Found beta turn keys in session: {beta_keys}")

        # ============================================================
        # FULL TURN HISTORY: Collect ALL turns for Steward awareness
        # This allows Steward to explain any turn, not just the latest
        # ============================================================
        turn_history = []
        latest_turn_data = None

        # ROBUSTNESS FIX: Use BOTH beta_current_turn AND actual keys found
        # This ensures we capture all turns even if beta_current_turn is out of sync
        max_turn_from_keys = 0
        for key in beta_keys:
            # Extract turn number from 'beta_turn_X_data'
            try:
                turn_num_str = key.replace('beta_turn_', '').replace('_data', '')
                turn_num_from_key = int(turn_num_str)
                max_turn_from_keys = max(max_turn_from_keys, turn_num_from_key)
            except (ValueError, AttributeError):
                pass

        # Use the larger of: completed_turns from counter, or max turn number found in keys
        actual_completed_turns = max(completed_turns, max_turn_from_keys)
        logger.info(f"🔍 STEWARD CONTEXT: Using actual_completed_turns={actual_completed_turns} (from counter: {completed_turns}, from keys: {max_turn_from_keys})")

        for turn_num in range(1, actual_completed_turns + 1):
            turn_data = st.session_state.get(f'beta_turn_{turn_num}_data', {})
            logger.info(f"   Checking turn {turn_num}: turn_data exists={bool(turn_data)}, keys={list(turn_data.keys()) if turn_data else []}")
            if turn_data:
                telos_analysis = turn_data.get('telos_analysis', {})

                # Extract metrics for this turn
                f_user = telos_analysis.get('display_user_pa_fidelity') or telos_analysis.get('user_pa_fidelity')

                # AI fidelity - multi-priority fallback
                f_ai = turn_data.get('ai_pa_fidelity')
                if f_ai is None:
                    ps_metrics = turn_data.get('ps_metrics', {})
                    if ps_metrics:
                        f_ai = ps_metrics.get('f_ai')
                if f_ai is None:
                    f_ai = telos_analysis.get('ai_pa_fidelity')

                ps = telos_analysis.get('display_primacy_state') or telos_analysis.get('primacy_state_score')

                # Build turn summary - include AI response for full context
                turn_summary = {
                    'turn': turn_num,
                    'user_input': turn_data.get('user_input', ''),
                    'ai_response': turn_data.get('shown_response') or turn_data.get('response', ''),
                    'f_user': f_user,
                    'f_ai': f_ai,
                    'primacy_state': ps,
                    'intervention_triggered': telos_analysis.get('intervention_triggered', False),
                    'intervention_reason': telos_analysis.get('intervention_reason', ''),
                }
                turn_history.append(turn_summary)

                # Track latest for backward compatibility
                latest_turn_data = turn_data

        # Add full turn history to context
        context['turn_history'] = turn_history

        # DEBUG: Log what we collected
        logger.info(f"🔍 STEWARD CONTEXT: Collected {len(turn_history)} turns in history")
        for i, turn in enumerate(turn_history):
            logger.info(f"   Turn {turn.get('turn')}: user_input={turn.get('user_input', '')[:50]}..., ai_response={turn.get('ai_response', '')[:50]}...")

        # ============================================================
        # LATEST TURN DATA: For backward compatibility with existing code
        # ============================================================
        if latest_turn_data:
            telos_analysis = latest_turn_data.get('telos_analysis', {})

            # Extract the three calibration metrics - USE DISPLAY VALUES to match UI
            # Fall back to raw values if display versions not available
            f_user = telos_analysis.get('display_user_pa_fidelity') or telos_analysis.get('user_pa_fidelity')

            # AI fidelity - use same multi-priority fallback as TELOSCOPE
            # Priority 1: Direct from turn_data
            f_ai = latest_turn_data.get('ai_pa_fidelity')
            # Priority 2: From ps_metrics dict
            if f_ai is None:
                ps_metrics = latest_turn_data.get('ps_metrics', {})
                if ps_metrics:
                    f_ai = ps_metrics.get('f_ai')
            # Priority 3: From telos_analysis
            if f_ai is None:
                f_ai = telos_analysis.get('ai_pa_fidelity')

            ps = telos_analysis.get('display_primacy_state') or telos_analysis.get('primacy_state_score')

            if f_user is not None:
                context['f_user'] = f_user
            if f_ai is not None:
                context['f_ai'] = f_ai
            if ps is not None:
                context['primacy_state'] = ps

            # Get the user's input that produced these metrics
            user_input = latest_turn_data.get('user_input', '')
            if user_input:
                context['last_user_input'] = user_input

            # Get the AI response displayed in the main session window
            # Try 'shown_response' first (display key), then 'response' (standard key)
            ai_response = latest_turn_data.get('shown_response') or latest_turn_data.get('response', '')
            if ai_response:
                context['last_ai_response'] = ai_response

            # Get intervention info
            if telos_analysis.get('intervention_triggered'):
                context['intervention_triggered'] = True
                context['intervention_reason'] = telos_analysis.get('intervention_reason', '')
            else:
                context['intervention_triggered'] = False

        # ============================================================
        # FALLBACK: state_manager.state.turns (original TELOS flow)
        # Only used if beta_turn_X_data didn't have metrics
        # ============================================================
        if 'f_user' not in context:
            state_manager = st.session_state.get('state_manager')
            if state_manager and hasattr(state_manager, 'state') and hasattr(state_manager.state, 'turns'):
                turns = state_manager.state.turns
                if turns:
                    latest_turn = turns[-1]
                    telos_analysis = latest_turn.get('telos_analysis', {})

                    f_user = telos_analysis.get('user_pa_fidelity')
                    f_ai = telos_analysis.get('ai_pa_fidelity')
                    ps = telos_analysis.get('primacy_state_score')

                    if f_user is not None:
                        context['f_user'] = f_user
                    if f_ai is not None:
                        context['f_ai'] = f_ai
                    if ps is not None:
                        context['primacy_state'] = ps

        return context

    def _build_why_explanation(self, turn_number: int) -> str:
        """Build a proportional, human explanation for why Steward intervened.

        Uses the Semantic Interpreter for consistent graduated language across
        main session and sidebar panel. The sidebar provides meta-explanation
        (explaining what happened) while main session provides action (redirect).

        Args:
            turn_number: The turn to explain

        Returns:
            Plain-language explanation scaled to drift severity
        """
        turn_data = st.session_state.get(f'beta_turn_{turn_number}_data', {})
        telos_analysis = turn_data.get('telos_analysis', {})
        user_fidelity = telos_analysis.get('user_pa_fidelity', 0.0)
        user_input = turn_data.get('user_input', '')

        # Get what this session is about
        pa = st.session_state.get('primacy_attractor', {})
        purpose = pa.get('purpose', '')
        # Handle purpose being a list (common in BETA mode)
        if isinstance(purpose, list):
            purpose = ' '.join(purpose) if purpose else ''

        # Get the template title if available (more user-friendly than purpose)
        template = st.session_state.get('selected_template', {})
        session_topic = template.get('title', '') if template else ''
        if not session_topic and purpose:
            session_topic = purpose[:50] + ('...' if len(purpose) > 50 else '')
        if not session_topic:
            session_topic = "what we set out to do"

        # Use the Semantic Interpreter for proportional language
        spec = semantic_interpret(user_fidelity, session_topic)

        # Truncate input for display
        short_input = user_input[:50] + ('...' if len(user_input) > 50 else '')

        # Build explanation based on interpreter's graduated analysis
        lines = []

        if spec.strength < 0.45:
            # MINIMAL - aligned, light touch
            lines.append("Everything looks good here.")
            lines.append("")
            lines.append(f"What you asked fits with **{session_topic}**, so I let the conversation flow naturally.")

        elif spec.strength < 0.60:
            # LIGHT - minor drift
            lines.append("This was a bit of a tangent, but still related.")
            lines.append("")
            lines.append(f"Your question touched on things slightly outside **{session_topic}**. I noted it but didn't step in heavily.")
            if spec.include_shift_mention:
                lines.append("")
                lines.append("If your focus has genuinely shifted, you can update it anytime.")

        elif spec.strength < 0.75:
            # MODERATE - clear drift (conversational, not robotic)
            lines.append("Hmm, that's drifting a bit from what we set out to do.")
            lines.append("")
            lines.append(f"**You asked:** \"{short_input}\"")
            lines.append("")
            lines.append(f"**But you said you wanted to focus on:** {session_topic}")
            lines.append("")
            lines.append("I nudged things back toward your goal, but if your interests have shifted, no worries.")
            lines.append("")
            lines.append("Just click **Shift Focus to This** if you'd rather explore this direction.")

        elif spec.strength < 0.85:
            # FIRM - significant drift (conversational, not robotic)
            lines.append("That's pretty far from what you wanted to work on.")
            lines.append("")
            lines.append(f"**Your question:** \"{short_input}\"")
            lines.append("")
            lines.append(f"**What you said you wanted:** {session_topic}")
            lines.append("")
            lines.append("I brought us back on track, but if you've changed your mind about what you want to explore, that's completely okay.")
            lines.append("")
            lines.append("Click **Shift Focus to This** to go with your new direction.")

        else:
            # STRONG - far from purpose (more conversational, less robotic)
            lines.append("Okay, that's a pretty big departure from what we set up.")
            lines.append("")
            lines.append(f"**Your question:** \"{short_input}\"")
            lines.append("")
            lines.append(f"**What you said you wanted to work on:** {session_topic}")
            lines.append("")
            lines.append("These two things don't really connect, so I stepped in to check.")
            lines.append("")
            lines.append("If you'd genuinely rather explore this new direction, that's totally fine! Just click **Shift Focus to This** and we'll go with it.")

        return "\n".join(lines)

    def _should_show_shift_focus_button(self) -> bool:
        """Check if we should show the 'Shift Focus to This' button.

        Shows when in ORANGE or RED zone (< 0.60 fidelity) - topic drift detected.
        Users who genuinely want to explore a different topic should have
        the option to shift focus rather than being redirected.

        Returns:
            True if button should be shown
        """
        from telos_observatory.config.colors import _ZONE_MINOR_DRIFT  # 0.60 threshold (below = orange/red zone)

        # Get current turn number
        current_turn = st.session_state.get('beta_current_turn', 1)
        completed_turns = current_turn - 1

        if completed_turns < 1:
            return False

        # Check most recent turn for fidelity - use DISPLAY fidelity for consistent thresholding
        for turn_num in range(completed_turns, 0, -1):
            turn_data = st.session_state.get(f'beta_turn_{turn_num}_data', {})
            if turn_data:
                telos_analysis = turn_data.get('telos_analysis', {})
                # Use display fidelity (normalized) for consistent threshold comparison
                f_user = telos_analysis.get('display_user_pa_fidelity') or telos_analysis.get('user_pa_fidelity')

                if f_user is not None:
                    # Show button if in ORANGE or RED zone (< 0.60)
                    return f_user < _ZONE_MINOR_DRIFT

        return False

    def _get_last_drifted_input(self) -> str:
        """Get the user input from the most recent drifted turn.

        Returns:
            The user's input that caused drift, or empty string
        """
        current_turn = st.session_state.get('beta_current_turn', 1)
        completed_turns = current_turn - 1

        for turn_num in range(completed_turns, 0, -1):
            turn_data = st.session_state.get(f'beta_turn_{turn_num}_data', {})
            if turn_data:
                return turn_data.get('user_input', '')

        return ''

    def _handle_shift_focus(self, new_direction: str):
        """Handle the 'Shift Focus to This' button click.

        Uses PA enrichment to generate a new PA based on the user's
        actual interest, then updates the session.

        Args:
            new_direction: The user input to pivot to
        """
        import logging
        logging.warning(f"🔄 SHIFT FOCUS CALLED with: '{new_direction[:50]}...'")
        print(f"🔄 SHIFT FOCUS CALLED with: '{new_direction[:50]}...'")

        if not new_direction:
            logging.warning("🔄 SHIFT FOCUS: Empty direction, returning")
            return

        try:
            from telos_observatory.services.pa_enrichment import PAEnrichmentService
            from mistralai import Mistral
            import os
            logging.warning("🔄 SHIFT FOCUS: Imports successful")

            # Get API key
            try:
                api_key = st.secrets.get("MISTRAL_API_KEY")
            except (FileNotFoundError, KeyError):
                api_key = os.environ.get("MISTRAL_API_KEY")

            if not api_key:
                st.error("Cannot shift focus: MISTRAL_API_KEY not configured")
                logging.warning("🔄 SHIFT FOCUS: No API key!")
                return

            logging.warning(f"🔄 SHIFT FOCUS: API key found, creating Mistral client")

            # Create enrichment service and generate new PA
            client = Mistral(api_key=api_key)
            enrichment_service = PAEnrichmentService(client)

            logging.warning(f"🔄 SHIFT FOCUS: Calling enrich_direction...")
            enriched_pa = enrichment_service.enrich_direction(new_direction)
            logging.warning(f"🔄 SHIFT FOCUS: enriched_pa = {enriched_pa is not None}")

            if enriched_pa:
                # Build User PA structure
                user_pa = {
                    'purpose': [enriched_pa.get('purpose', new_direction)],
                    'scope': enriched_pa.get('scope', []),
                    'boundaries': enriched_pa.get('boundaries', []),
                    'success_criteria': f"Explore: {new_direction}",
                    'style': st.session_state.get('primacy_attractor', {}).get('style', 'balanced'),
                }

                # DUAL ATTRACTOR: Derive AI PA from User PA using intent-to-role mapping
                ai_pa = derive_ai_pa_from_user_pa(user_pa)

                # Update session state with both PAs
                st.session_state.primacy_attractor = user_pa
                st.session_state.user_pa = user_pa
                st.session_state.ai_pa = ai_pa

                # Update template title to reflect new focus
                if 'selected_template' in st.session_state:
                    short_title = new_direction[:40] + ('...' if len(new_direction) > 40 else '')
                    st.session_state.selected_template = {
                        **st.session_state.selected_template,
                        'title': short_title,
                        'shifted': True
                    }

                # Add acknowledgment to Steward chat with derivation info
                detected_intent = ai_pa.get('detected_intent', 'explore')
                derived_role = ai_pa.get('derived_role_action', 'help with')
                ack = enriched_pa.get('steward_acknowledgment', 'Focus updated.')
                st.session_state.beta_steward_chat_history.append({
                    'role': 'assistant',
                    'content': f"**Focus shifted!**\n\n{ack}\n\nYour session is now about: **{enriched_pa.get('purpose', new_direction)}**\n\n*Detected intent: {detected_intent} → AI role: {derived_role}*",
                    'timestamp': datetime.now().isoformat()
                })

                # Clear ALL cached PA embeddings - we'll recompute with dual attractor
                # CRITICAL: Must include ALL embedding keys including SentenceTransformer centroid
                cached_keys_to_clear = [
                    'cached_user_pa_embedding',
                    'cached_ai_pa_embedding',
                    'cached_mpnet_user_pa_embedding',
                    'cached_mpnet_ai_pa_embedding',
                    'user_pa_embedding',
                    # CRITICAL: SentenceTransformer centroid used for Template Mode fidelity
                    'cached_st_user_pa_embedding',
                    # Fidelity mode flags
                    'use_rescaled_fidelity_mode',
                    # Stale fidelity cache
                    'last_telos_calibration_values',
                ]
                for key in cached_keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]

                # CRITICAL: Update PA identity hash to match new PA
                # Without this, _initialize_telos_engine will detect a mismatch and
                # invalidate the cache we just updated, causing fallback to hardcoded values
                import hashlib
                purpose_str = user_pa.get('purpose', '')
                if isinstance(purpose_str, list):
                    purpose_str = ' '.join(purpose_str)
                scope_str = user_pa.get('scope', '')
                if isinstance(scope_str, list):
                    scope_str = ' '.join(scope_str)
                new_pa_identity = hashlib.md5(f"{purpose_str}|{scope_str}".encode()).hexdigest()[:16]
                st.session_state.cached_pa_identity = new_pa_identity
                import logging
                logging.info(f"🔄 Shift Focus: Updated PA identity hash: {new_pa_identity}")

                # Invalidate response manager so it rebuilds with new PA
                if 'beta_response_manager' in st.session_state:
                    del st.session_state['beta_response_manager']

                # Compute both embeddings using dual attractor system
                # This rebuilds MiniLM embeddings AND the SentenceTransformer centroid
                # Pass enriched_pa which contains example_queries for centroid generation
                self._rebuild_pa_embeddings_dual(user_pa, ai_pa, enriched_pa)

                # Set flag so observation deck knows to show "Focus shifted"
                st.session_state.pa_just_shifted = True

            else:
                st.error("Could not generate new focus. Please try again.")

        except Exception as e:
            st.error(f"Error shifting focus: {str(e)}")

    def _rebuild_pa_embeddings_dual(self, user_pa: dict, ai_pa: dict, enriched_pa: dict = None):
        """Rebuild both PA embeddings after a focus shift using dual attractor.

        Uses compute_pa_embeddings() for mathematically coupled embeddings.
        CRITICAL: Also rebuilds the SentenceTransformer centroid from example_queries.

        Args:
            user_pa: The new user PA structure
            ai_pa: The derived AI PA structure
            enriched_pa: The enriched PA dict from PA enrichment (contains example_queries)
        """
        try:
            from telos_core.embedding_provider import get_cached_minilm_provider
            import numpy as np
            import logging

            # Get or create embedding provider (use cached to avoid model reload)
            if 'embedding_provider' not in st.session_state:
                st.session_state.embedding_provider = get_cached_minilm_provider()

            provider = st.session_state.embedding_provider

            # Compute BOTH embeddings using dual attractor system
            user_embedding, ai_embedding = compute_pa_embeddings(user_pa, ai_pa, provider)

            # Cache both embeddings - no lazy computation
            st.session_state.cached_user_pa_embedding = user_embedding
            st.session_state.cached_ai_pa_embedding = ai_embedding
            st.session_state.user_pa_embedding = user_embedding  # Legacy key

            logging.info(f"🔄 Dual attractor embeddings computed at focus shift time")

            # CRITICAL: Rebuild SentenceTransformer centroid from example queries
            # This is what Template Mode fidelity uses for calculation
            if enriched_pa and 'example_queries' in enriched_pa:
                example_queries = enriched_pa['example_queries']
                if example_queries:
                    logging.info(f"📊 Regenerating ST centroid from {len(example_queries)} example queries...")

                    # Generate embeddings for each example query
                    example_embeddings = [np.array(provider.encode(ex)) for ex in example_queries]

                    # Compute centroid (mean of all example embeddings)
                    domain_centroid = np.mean(example_embeddings, axis=0)

                    # Normalize the centroid
                    st_user_pa_embedding = domain_centroid / np.linalg.norm(domain_centroid)

                    # Cache in session state - this is what Template Mode fidelity uses
                    st.session_state.cached_st_user_pa_embedding = st_user_pa_embedding

                    # Enable template mode (SentenceTransformer thresholds)
                    st.session_state.use_rescaled_fidelity_mode = True

                    logging.info(f"✅ ST centroid regenerated: {len(st_user_pa_embedding)} dims")
                else:
                    logging.warning("⚠️ enriched_pa has empty example_queries - ST centroid not updated")
            else:
                logging.warning("⚠️ No enriched_pa or example_queries provided - ST centroid not updated")

        except Exception as e:
            # Log but don't fail - the PA text update is still useful
            import logging
            logging.error(f"⚠️ Could not rebuild PA embeddings: {e}")


def render_beta_steward_button():
    """Render the Beta Steward toggle button (handshake emoji)."""
    # Initialize panel state
    if 'beta_steward_panel_open' not in st.session_state:
        st.session_state.beta_steward_panel_open = False

    button_label = "Close Steward" if st.session_state.beta_steward_panel_open else "Ask Steward"

    if st.button(button_label, key="beta_steward_toggle", use_container_width=True):
        st.session_state.beta_steward_panel_open = not st.session_state.beta_steward_panel_open
        st.rerun()


def render_bottom_section():
    """Render Steward as a full-width bottom section (BETA mode).

    This replaces the side panel approach for a cleaner, more spacious layout
    that handles long responses better.
    """
    panel = BetaStewardPanel()

    # Check if opened from an intervention "Why?" button
    intervention_turn = st.session_state.pop('steward_intervention_turn', None)

    # Track whether this session was opened from "Ask Steward why"
    if intervention_turn is not None:
        st.session_state.steward_opened_from_why = True
        # Clear existing chat history when opened from "Why?" button
        if 'beta_steward_chat_history' in st.session_state:
            del st.session_state.beta_steward_chat_history

    # Initialize chat history if not exists
    if 'beta_steward_chat_history' not in st.session_state:
        if intervention_turn:
            # Opened from "Why?" button - provide detailed explanation
            initial_message = panel._build_why_explanation(intervention_turn)
        else:
            # Standard greeting - helps users understand they're in a different interface
            initial_message = "I'm Steward, your alignment companion for this session.\n\nAsk me anything about what you're seeing, or I can explain why something was flagged."

        st.session_state.beta_steward_chat_history = [
            {
                'role': 'assistant',
                'content': initial_message,
                'timestamp': datetime.now().isoformat()
            }
        ]

    # Bottom section container with distinct styling
    st.markdown("""
    <style>
    .steward-bottom-section {
        background: linear-gradient(135deg, rgba(244, 208, 63, 0.08) 0%, rgba(244, 208, 63, 0.02) 100%);
        border: 2px solid #F4D03F;
        border-radius: 12px;
        padding: 20px;
        margin-top: 30px;
        box-shadow: 0 0 20px rgba(244, 208, 63, 0.1);
    }
    .steward-bottom-header {
        color: #F4D03F;
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

    # Scroll target for auto-scroll feature (no visual separator)
    st.markdown("<div id='steward-scroll-target'></div>", unsafe_allow_html=True)

    # Header with Steward branding
    st.markdown("""
    <div class="steward-bottom-header">
        Steward
    </div>
    """, unsafe_allow_html=True)

    # Auto-scroll to Steward section if flag is set
    if st.session_state.pop('scroll_to_steward', False):
        import streamlit.components.v1 as components
        components.html("""
        <script>
        setTimeout(function() {
            const target = window.parent.document.getElementById('steward-scroll-target');
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 100);
        </script>
        """, height=0)

    # Chat history display - clean styling without redundant "Steward:" label
    # The section header already establishes the speaker
    for message in st.session_state.beta_steward_chat_history:
        if message['role'] == 'assistant':
            formatted_content = _md_to_html(message['content'])
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid #F4D03F; border-radius: 10px; padding: 15px; margin-bottom: 15px; box-shadow: 0 0 15px rgba(244, 208, 63, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
                <span style="color: #e0e0e0; font-size: 20px; line-height: 1.6;">{formatted_content}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid #666; border-radius: 10px; padding: 15px; margin-bottom: 15px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
                <strong style="color: #e0e0e0; font-size: 20px;">You:</strong><br>
                <span style="color: #e0e0e0; font-size: 20px; line-height: 1.6;">{html.escape(message['content'])}</span>
            </div>
            """, unsafe_allow_html=True)

    # Contemplating animation when waiting for response
    if st.session_state.get('steward_pending_response', False):
        st.markdown("""
<style>
@keyframes steward-border-pulse {
    0%, 100% { border-color: #888; box-shadow: 0 0 6px rgba(136, 136, 136, 0.3); }
    50% { border-color: #F4D03F; box-shadow: 0 0 6px rgba(255, 215, 0, 0.4); }
}
@keyframes steward-text-pulse {
    0%, 100% { color: #F4D03F; }
    50% { color: #888; }
}
.steward-contemplating-border { animation: steward-border-pulse 2s ease-in-out infinite; }
.steward-contemplating-text { animation: steward-text-pulse 2s ease-in-out infinite; }
</style>
<div class="steward-contemplating-border" style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 2px solid #888; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
    <span class="steward-contemplating-text" style="font-size: 20px; font-style: italic; color: #F4D03F;">Contemplating...</span>
</div>
""", unsafe_allow_html=True)

    # Show "Shift Focus to This" button if in orange/red zone
    if panel._should_show_shift_focus_button():
        st.markdown("<div style='margin-top: 10px; margin-bottom: 10px;'></div>", unsafe_allow_html=True)

        drift_input = panel._get_last_drifted_input()

        if st.button(
            "Shift Focus to This",
            key="steward_bottom_shift_focus",
            help="Update session purpose to match what you're actually interested in",
            use_container_width=True
        ):
            panel._handle_shift_focus(drift_input)
            st.rerun()

    # Input form - full width in bottom section
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

    # CSS for form button styling
    st.markdown("""
    <style>
    [data-testid="stForm"] button[kind="secondaryFormSubmit"],
    [data-testid="stForm"] button {
        background-color: #2d2d2d !important;
        color: #F4D03F !important;
        border: 1px solid #F4D03F !important;
        opacity: 1 !important;
    }
    [data-testid="stForm"] button:hover {
        box-shadow: 0 0 8px #F4D03F !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Form for user input - matching main conversation styling
    with st.form(key="beta_steward_bottom_form", clear_on_submit=True):
        user_input_raw = st.text_area(
            "Ask Steward anything...",
            placeholder="",
            label_visibility="collapsed",
            key="beta_steward_bottom_input",
            height=80
        )

        # Full-width Send button - matching main conversation Send button
        submitted = st.form_submit_button("Send", use_container_width=True)

    # Add JavaScript to submit form on Enter key (Shift+Enter for new line)
    import streamlit.components.v1 as components
    components.html("""
    <script>
    (function() {
        // Find the Send button within the same form as the textarea
        function findSendButton(textarea) {
            let container = textarea.closest('form') || textarea.closest('[data-testid]') || textarea.parentElement;
            for (let i = 0; i < 10 && container; i++) {
                const btn = container.querySelector('button');
                if (btn) {
                    const text = btn.textContent || btn.innerText;
                    if (text.includes('Send')) {
                        return btn;
                    }
                }
                container = container.parentElement;
            }
            return null;
        }

        function setupEnterHandler() {
            const doc = window.parent.document;
            const textareas = doc.querySelectorAll('textarea');
            textareas.forEach(function(textarea) {
                if (textarea.dataset.stewardEnterSetup) return;
                textarea.dataset.stewardEnterSetup = 'true';

                textarea.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        // Prevent submission if input is empty
                        if (!textarea.value || !textarea.value.trim()) {
                            e.preventDefault();
                            return;
                        }
                        e.preventDefault();
                        e.stopPropagation();

                        // Find the Send button in the same form as this textarea
                        const btn = findSendButton(textarea);
                        if (btn && !btn.disabled) {
                            btn.click();
                            return;
                        }
                    }
                }, true);
            });
        }

        setupEnterHandler();
        setTimeout(setupEnterHandler, 500);
        setTimeout(setupEnterHandler, 1000);
    })();
    </script>
    """, height=0)

    # Handle form submission
    if submitted:
        user_input = user_input_raw.strip() if user_input_raw else ''

        if user_input:
            st.session_state.beta_steward_chat_history.append({
                'role': 'user',
                'content': user_input,
                'timestamp': datetime.now().isoformat()
            })
            st.session_state.steward_pending_response = True
            st.session_state.steward_pending_input = user_input
            st.rerun()

    # Close button outside form
    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
    if st.button("Close Steward", key="close_beta_steward_bottom_section", use_container_width=True):
        st.session_state.beta_steward_panel_open = False
        # Set flag to scroll to top (or current turn if in scroll view)
        st.session_state.scroll_after_steward_close = True
        # Keep chat history so context is preserved when reopened!
        # Only clear the "opened from why" flag
        if 'steward_opened_from_why' in st.session_state:
            del st.session_state.steward_opened_from_why
        st.rerun()

    # Fetch response when pending
    if st.session_state.get('steward_pending_response', False):
        with st.spinner("Steward is contemplating..."):
            user_input = st.session_state.steward_pending_input
            if st.session_state.get('beta_steward_llm_enabled', False):
                context = panel._gather_beta_context()

                try:
                    steward_response = st.session_state.beta_steward_llm.get_response(
                        user_message=user_input,
                        conversation_history=st.session_state.beta_steward_chat_history[:-1],
                        context=context
                    )
                except Exception as e:
                    steward_response = f"I apologize, but I encountered an error: {str(e)}. Please try again."
            else:
                steward_response = f"I'm currently in setup mode. {st.session_state.get('beta_steward_error', 'Please configure the MISTRAL_API_KEY.')}"

        st.session_state.beta_steward_chat_history.append({
            'role': 'assistant',
            'content': steward_response,
            'timestamp': datetime.now().isoformat()
        })

        st.session_state.steward_pending_response = False
        st.session_state.steward_pending_input = None
        st.rerun()

"""
Conversation Display Component for TELOS Observatory V3.
Renders ChatGPT/Claude-style conversation in center column.
"""

import streamlit as st
from typing import Dict, Any
import html
import logging
import re
from datetime import datetime
from telos_observatory.services.file_handler import get_file_handler

logger = logging.getLogger(__name__)


import streamlit.components.v1 as components
import base64


def render_copy_button(text: str, key: str) -> None:
    """Render a working copy button using components.html().

    This uses an iframe with JavaScript that CAN access the clipboard API,
    unlike st.markdown which cannot execute JavaScript.

    Args:
        text: The text to copy to clipboard
        key: Unique key for this button instance
    """
    # Encode text as base64 to handle special characters and quotes
    encoded_text = base64.b64encode(text.encode('utf-8')).decode('ascii')

    # HTML/JS component with working clipboard copy - improved visibility and sizing
    html_code = f'''
    <div id="copy-container-{key}" style="display: inline-block; margin-top: 20px; margin-bottom: 25px;">
        <button id="copy-btn-{key}" onclick="copyToClipboard_{key}()"
            style="background: rgba(30, 30, 35, 0.9); border: 1px solid #666; border-radius: 8px;
                   padding: 10px 18px; cursor: pointer; color: #ddd; font-size: 14px;
                   display: flex; align-items: center; gap: 8px; transition: all 0.2s;
                   box-shadow: 0 3px 8px rgba(0,0,0,0.4);">
            <span id="copy-icon-{key}" style="font-size: 14px;">Copy</span>
        </button>
    </div>
    <script>
        function copyToClipboard_{key}() {{
            const encodedText = "{encoded_text}";
            const text = atob(encodedText);

            // Try modern clipboard API first
            if (navigator.clipboard && navigator.clipboard.writeText) {{
                navigator.clipboard.writeText(text).then(function() {{
                    showSuccess_{key}();
                }}).catch(function(err) {{
                    // Fallback for permission denied
                    fallbackCopy_{key}(text);
                }});
            }} else {{
                // Fallback for older browsers
                fallbackCopy_{key}(text);
            }}
        }}

        function fallbackCopy_{key}(text) {{
            // Create temporary textarea
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.left = '-9999px';
            document.body.appendChild(textarea);
            textarea.select();
            try {{
                document.execCommand('copy');
                showSuccess_{key}();
            }} catch (err) {{
                showError_{key}();
            }}
            document.body.removeChild(textarea);
        }}

        function showSuccess_{key}() {{
            const icon = document.getElementById('copy-icon-{key}');
            const btn = document.getElementById('copy-btn-{key}');
            icon.textContent = 'Copied!';
            btn.style.borderColor = '#27ae60';
            btn.style.color = '#27ae60';
            btn.style.background = 'rgba(76, 175, 80, 0.15)';
            setTimeout(function() {{
                icon.textContent = 'Copy';
                btn.style.borderColor = '#555';
                btn.style.color = '#ccc';
                btn.style.background = 'rgba(30, 30, 35, 0.8)';
            }}, 2000);
        }}

        function showError_{key}() {{
            const icon = document.getElementById('copy-icon-{key}');
            const btn = document.getElementById('copy-btn-{key}');
            icon.textContent = 'Failed';
            btn.style.borderColor = '#e74c3c';
            btn.style.color = '#e74c3c';
            btn.style.background = 'rgba(255, 68, 68, 0.15)';
            setTimeout(function() {{
                icon.textContent = 'Copy';
                btn.style.borderColor = '#555';
                btn.style.color = '#ccc';
                btn.style.background = 'rgba(30, 30, 35, 0.8)';
            }}, 2000);
        }}
    </script>
    '''

    components.html(html_code, height=65)


class ConversationDisplay:
    """ChatGPT-style conversation display using native Streamlit."""

    def __init__(self, state_manager, steward_panel=None):
        """Initialize with state manager reference.

        Args:
            state_manager: StateManager instance for accessing turn data
            steward_panel: Optional StewardPanel instance for demo chat
        """
        self.state_manager = state_manager
        self.steward_panel = steward_panel

    def _reset_all_alignment_lens_states(self):
        """Reset all Alignment Lens visibility states to hidden.

        Called when navigating between slides to ensure Alignment Lens
        doesn't persist from one slide to the next.
        """
        st.session_state.demo_obs_deck_visible = False
        st.session_state.demo_std_obs_deck_visible = False
        st.session_state.slide_6_obs_deck_visible = False
        st.session_state.slide_7_obs_deck_visible = False

    def _markdown_to_html(self, text: str) -> str:
        """Convert markdown to HTML while escaping dangerous content.

        Args:
            text: Markdown text to convert

        Returns:
            HTML-formatted text
        """
        # First escape HTML to prevent XSS
        text = html.escape(text)

        # Convert markdown patterns to HTML
        # Process in correct order: bold before italic to handle **text** correctly

        # Bold: **text** or __text__ (do these first!)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text, flags=re.DOTALL)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text, flags=re.DOTALL)

        # Italic: *text* or _text_ (do after bold to avoid conflicts)
        text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', text)
        text = re.sub(r'(?<!_)_([^_]+?)_(?!_)', r'<em>\1</em>', text)

        # Headers: # Header (must be at start of line or after newline)
        text = re.sub(r'^### (.+?)$', r'<h4 style="color: #F4D03F; margin: 10px 0 5px 0;">\1</h4>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+?)$', r'<h3 style="color: #F4D03F; margin: 12px 0 6px 0;">\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+?)$', r'<h2 style="color: #F4D03F; margin: 15px 0 8px 0;">\1</h2>', text, flags=re.MULTILINE)

        # Bullet lists: - item or * item (at start of line)
        text = re.sub(r'^[-*] (.+?)$', r'<li style="margin-left: 20px; list-style-type: disc;">\1</li>', text, flags=re.MULTILINE)

        # Numbered lists: 1. item, 2. item, etc.
        text = re.sub(r'^(\d+)\. (.+?)$', r'<li style="margin-left: 20px; list-style-type: decimal;">\2</li>', text, flags=re.MULTILINE)

        # Inline code: `code`
        text = re.sub(r'`([^`]+?)`', r'<code style="background-color: #333; padding: 2px 6px; border-radius: 3px; font-family: monospace;">\1</code>', text)

        # Markdown links: [text](url) -> clickable <a> tags
        text = re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            r'<a href="\2" target="_blank" style="color: #F4D03F; text-decoration: underline;">\1</a>',
            text
        )

        # Line breaks (do this last to preserve structure)
        text = text.replace('\n', '<br>')

        return text

    def _process_pending_pivot(self):
        """
        Process pending PA pivot from "Shift Focus" button click.

        When user clicks "Shift Focus to This" button on a drift turn,
        it sets pending_telos_pivot in session state. This method:
        1. Detects the pending pivot
        2. Calls the TELOS command handler to create new PA
        3. Stores the result as a new turn
        4. Clears the pending state
        """
        pending_direction = st.session_state.get('pending_telos_pivot')
        if not pending_direction:
            return

        # Clear the pending state first to prevent loops
        source_turn = st.session_state.get('pending_telos_pivot_turn', 0)
        del st.session_state['pending_telos_pivot']
        if 'pending_telos_pivot_turn' in st.session_state:
            del st.session_state['pending_telos_pivot_turn']
        # Clear the shifting focus flag after processing
        if 'is_shifting_focus' in st.session_state:
            del st.session_state['is_shifting_focus']

        # Get beta response manager
        beta_manager = st.session_state.get('beta_response_manager')
        if not beta_manager:
            st.warning("Unable to shift focus - response manager not available")
            return

        # Get next turn number
        turn_number = st.session_state.get('beta_current_turn', 1)

        # Process as TELOS command
        try:
            response_data = beta_manager._handle_telos_command(pending_direction, turn_number)

            if response_data:
                # Store the pivot response in beta session state
                st.session_state[f'beta_turn_{turn_number}_data'] = response_data

                # CRITICAL: Ensure loading flags are False so input form shows
                # Without this, the CSS that hides forms during loading may persist
                response_data['is_loading'] = False
                response_data['is_streaming'] = False

                # Add turn to state_manager so it renders in conversation window
                # This makes the PA shift feel like a proper Steward response
                if hasattr(self, 'state_manager') and self.state_manager:
                    self.state_manager.state.turns.append(response_data)
                    # Update current_turn index to point to the new pivot turn
                    # This ensures _render_current_turn_only renders the NEW turn
                    self.state_manager.state.current_turn = len(self.state_manager.state.turns) - 1

                # Increment turn counter for next interaction
                st.session_state['beta_current_turn'] = turn_number + 1

                # No banner needed - the turn will render as a proper conversation message

        except Exception as e:
            st.error(f"Error shifting focus: {str(e)}")

    def _handle_shift_focus_from_response(self, user_input: str, turn_number: int):
        """
        Handle "Shift Focus to This" button click from AI response.

        Sets up pending state for _process_pending_pivot to handle on next rerun.
        This allows the user to update their session focus based on their drifted query.

        Args:
            user_input: The user's original input from this turn (becomes new PA direction)
            turn_number: The turn number where the shift was triggered
        """
        if not user_input:
            return

        # Set pending pivot state - _process_pending_pivot will handle it
        st.session_state['pending_telos_pivot'] = user_input
        st.session_state['pending_telos_pivot_turn'] = turn_number
        st.session_state['is_shifting_focus'] = True

    def render(self):
        """Render the conversation display with main chat and analysis windows."""
        # Process any pending PA pivot from "Shift Focus" button
        self._process_pending_pivot()

        # Main chat interface
        self._render_main_chat()

        # Get current turn data for analysis windows
        turn_data = self.state_manager.get_current_turn_data()

        if not turn_data:
            return

        # Render analysis windows if toggles are enabled (in order: PA, Math, Counterfactual)
        if self.state_manager.state.show_primacy_attractor:
            st.markdown("<div style='margin: 15px 0;'></div>", unsafe_allow_html=True)
            self._render_primacy_attractor_window(turn_data)

        if self.state_manager.state.show_math_breakdown:
            st.markdown("<div style='margin: 15px 0;'></div>", unsafe_allow_html=True)
            self._render_math_breakdown_window(turn_data)

        if self.state_manager.state.show_counterfactual:
            st.markdown("<div style='margin: 15px 0;'></div>", unsafe_allow_html=True)
            self._render_counterfactual_window(turn_data)

    def _render_main_chat(self):
        """Render main conversation - either turn-by-turn or scrollable history."""
        # ESC key handler for Demo Mode -> Open Mode switch
        demo_mode = st.session_state.get('telos_demo_mode', False)
        if demo_mode:
            # Inject JavaScript to handle ESC key press
            st.components.v1.html("""
            <script>
            // Prevent duplicate listeners
            if (!window.telosEscListenerAdded) {
                window.telosEscListenerAdded = true;

                document.addEventListener('keydown', function(event) {
                    if (event.key === 'Escape') {
                        // Find the "Open Mode" radio button in the sidebar and click it
                        const radioButtons = window.parent.document.querySelectorAll('input[type="radio"]');
                        radioButtons.forEach(radio => {
                            const label = radio.parentElement;
                            if (label && label.textContent.includes('Open Mode')) {
                                radio.click();
                            }
                        });
                    }
                });
            }
            </script>
            """, height=0)

        # Get current turn data
        current_turn_idx = self.state_manager.get_current_turn_index()
        all_turns = self.state_manager.get_all_turns()

        # Check if currently loading (for conditional rendering)
        is_loading = False
        if len(all_turns) > 0:
            current_turn = all_turns[-1]
            # Check for BOTH is_loading AND is_streaming flags
            # SAFETY: Only consider loading if there's no response yet
            # This prevents stale loading flags from hiding the input form
            has_response = bool(current_turn.get('response') or current_turn.get('shown_response'))
            if not has_response:
                is_loading = current_turn.get('is_loading', False) or current_turn.get('is_streaming', False)

        # FORCE HIDE input form during loading - inject CSS to completely hide it
        if is_loading:
            st.markdown("""
            <style>
            /* Nuclear option: hide ALL forms on the page during loading */
            form {
                display: none !important;
                visibility: hidden !important;
                height: 0 !important;
                overflow: hidden !important;
                opacity: 0 !important;
                position: absolute !important;
                left: -9999px !important;
            }

            /* Hide form containers */
            div[data-testid="stForm"],
            form[data-testid="stForm"] {
                display: none !important;
                visibility: hidden !important;
                height: 0 !important;
            }

            /* Hide text inputs */
            input[type="text"] {
                display: none !important;
                visibility: hidden !important;
            }
            </style>
            <script>
            // Scroll to top when loading starts
            window.scrollTo(0, 0);
            if (window.parent) {
                window.parent.scrollTo(0, 0);
            }
            </script>
            """, unsafe_allow_html=True)

        # Initialize intro message state (respecting settings)
        if 'show_intro' not in st.session_state:
            # Check if intro examples are enabled in settings
            enable_intro = st.session_state.get('enable_intro_examples', True)
            st.session_state.show_intro = enable_intro

        # Check beta intro BEFORE checking turn count (to prevent showing after first message)
        demo_mode = st.session_state.get('telos_demo_mode', False)
        # Safely check for BETA mode - use .get() to avoid KeyError
        active_tab = st.session_state.get('active_tab', 'DEMO')
        beta_mode = active_tab == "BETA"

        # BETA intro slideshow is replaced by simple welcome message in main.py
        # Mark intro as complete to skip old slideshow
        if beta_mode and 'beta_intro_complete' not in st.session_state:
            st.session_state.beta_intro_complete = True

        # DEMO MODE: Always show demo slides regardless of other session state
        # This enables bidirectional navigation between DEMO and BETA
        if demo_mode:
            demo_slide_index = st.session_state.get('demo_slide_index', 0)
            from telos_observatory.demo_mode.telos_framework_demo import get_demo_slides
            max_slide = len(get_demo_slides()) + 1  # +1 for congratulations screen
            if demo_slide_index <= max_slide:  # 0=welcome, 1-N=Q&A slides, N+1=congratulations
                self._render_demo_welcome()
                return  # Demo slides have their own navigation
            else:
                # Beyond demo slides - fallback to regular input
                self._render_input_with_scroll_toggle()
                return

        if len(all_turns) == 0:
            # Blank session - handle different modes appropriately

            # BETA MODE with completed intro: Show input immediately
            if beta_mode and st.session_state.get('beta_intro_complete', True):
                # Fresh Start mode: Show Steward welcome message inviting user to share purpose
                if st.session_state.get('show_fresh_start_welcome', False):
                    self._render_fresh_start_welcome()
                # Beta mode after intro - show input for conversation
                self._render_input_with_scroll_toggle()
                return
            else:
                # OPEN MODE (TELOS tab): Just show input area
                self._render_input_with_scroll_toggle()
                return

        # Render scrollable history window if enabled (at top of screen)
        # NOT available in Demo Mode - Demo Mode is conversation-focused only
        if self.state_manager.state.scrollable_history_mode:
            self._render_scrollable_history_window(current_turn_idx, all_turns)

        # Render current turn in interactive mode (always show this)
        self._render_current_turn_only(current_turn_idx, all_turns)

        # Input area - ONLY render when NOT loading (during calibrating, completely omit)
        if not is_loading:
            self._render_input_with_scroll_toggle()

    def _render_fresh_start_welcome(self):
        """Render Steward welcome message for Fresh Start mode.

        Shows a friendly message inviting the user to share their purpose/goal.
        The PA will be derived from their first message.
        """
        # Use gray border since no fidelity established yet
        border_color = '#888888'
        label_color = '#888888'

        welcome_message = """Welcome! I'm your Steward for this conversation.

Go ahead and share what you'd like to accomplish today. Tell me your goal, question, or what you're hoping to explore.

Once you send your first message, I'll understand your purpose and we can get started."""

        # Header with Steward label - glassmorphism effect
        st.markdown(f"""
<div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 15px 15px 8px 15px; border-radius: 10px 10px 0 0; margin-top: 0; margin-bottom: -1rem; border: 2px solid {border_color}; border-bottom: none; box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.1); overflow: visible;">
    <div style="color: #a8a8a8; font-size: 19px; overflow: visible;">
        <strong style="color: {label_color};">Steward</strong>
    </div>
</div>
""", unsafe_allow_html=True)

        # Message content
        st.markdown(f"""
<div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 10px 15px 15px 15px; margin-top: 0; margin-bottom: 25px; border: 2px solid {border_color}; border-top: none; border-radius: 0 0 10px 10px; color: #fff; font-size: 19px; box-shadow: 0 0 15px rgba(136, 136, 136, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 -1px 1px rgba(255, 255, 255, 0.1); position: relative; z-index: 1; line-height: 1.6;">
    {welcome_message.replace(chr(10), '<br>')}
</div>
""", unsafe_allow_html=True)

    def _render_demo_welcome(self):
        """Render Demo Mode welcome and typewriter slideshow."""
        from telos_observatory.demo_mode.telos_framework_demo import (
            get_demo_welcome_message,
            get_steward_intro_message,
            get_demo_slides,
            get_demo_completion_message
        )
        import json

        # Initialize demo state
        if 'demo_slide_index' not in st.session_state:
            st.session_state.demo_slide_index = 0  # 0 = welcome, 1-14 = Q&A slides, 15 = congratulations

        # Inject global CSS for compact containers + UI/UX enhancements (applies to all demo slides)
        st.markdown("""
        <style>
        /* FULL-WIDTH FLUSH LAYOUT - buttons and content edge-to-edge */
        div.compact-container,
        .compact-container {
            width: 100% !important;
            max-width: 100% !important;
            margin-left: auto !important;
            margin-right: auto !important;
            display: block !important;
        }

        .compact-container > div {
            width: 100% !important;
            max-width: 100% !important;
        }

        /* Full-width button rows */
        [data-testid="stHorizontalBlock"] {
            width: 100% !important;
            max-width: 100% !important;
        }

        /* Ensure column containers within don't overflow */
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            flex: 1 1 auto !important;
        }

        /* GLOBAL OVERRIDE: Force all inline max-width: 700px to 100% */
        [style*="max-width: 700px"],
        [style*="max-width:700px"] {
            max-width: 100% !important;
            width: 100% !important;
        }

        /* ========== UI/UX ENHANCEMENTS FOR 95%+ SCORE ========== */

        /* Fix #4: WCAG Focus Indicators - 3px gold outline on focus */
        button:focus-visible,
        [role="button"]:focus-visible,
        .stButton > button:focus-visible {
            outline: 3px solid #F4D03F !important;
            outline-offset: 2px !important;
            box-shadow: 0 0 0 4px rgba(244, 208, 63, 0.3) !important;
        }
        a:focus-visible {
            outline: 3px solid #F4D03F !important;
            outline-offset: 2px !important;
        }

        /* Fix #12: Micro-interactions - hover/active states */
        button,
        [role="button"],
        .stButton > button {
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }
        button:hover:not(:disabled),
        [role="button"]:hover,
        .stButton > button:hover:not(:disabled) {
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(244, 208, 63, 0.3) !important;
        }
        button:active,
        [role="button"]:active,
        .stButton > button:active {
            transform: translateY(0) !important;
        }

        /* Fidelity card hover effects */
        .fidelity-card {
            transition: transform 0.3s ease, box-shadow 0.3s ease !important;
        }
        .fidelity-card:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px rgba(244, 208, 63, 0.4) !important;
        }

        /* Fix #8: Responsive breakpoints */
        @media (max-width: 768px) {
            .compact-container,
            [style*="max-width: 700px"] {
                max-width: 95% !important;
                padding-left: 16px !important;
                padding-right: 16px !important;
            }
            [data-testid="stHorizontalBlock"] {
                max-width: 95% !important;
            }
            /* Stack fidelity cards on mobile */
            .fidelity-cards-container {
                flex-direction: column !important;
                gap: 16px !important;
            }
            .fidelity-card {
                min-width: 100% !important;
            }
        }
        @media (min-width: 769px) and (max-width: 1024px) {
            .compact-container {
                max-width: 600px !important;
            }
        }

        /* Fix #13: Layered shadows for visual depth */
        .demo-welcome-box {
            box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 2px 8px rgba(244,208,63,0.2) !important;
        }
        .message-box {
            box-shadow: 0 2px 8px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05) !important;
        }
        .fidelity-box {
            box-shadow: 0 4px 16px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.05) !important;
        }

        /* Fix #2: Skip navigation link (hidden until focused) */
        .skip-nav {
            position: absolute;
            left: -9999px;
            z-index: 999;
            background: #F4D03F;
            color: #000;
            padding: 8px 16px;
            text-decoration: none;
            font-weight: bold;
            border-radius: 4px;
        }
        .skip-nav:focus {
            left: 16px;
            top: 16px;
        }

        /* Tooltip styles for domain terms */
        .telos-tooltip {
            position: relative;
            border-bottom: 1px dotted #F4D03F;
            cursor: help;
        }
        .telos-tooltip:hover::after {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #1a1a1a;
            border: 1px solid #F4D03F;
            color: #e0e0e0;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 14px;
            white-space: nowrap;
            z-index: 1000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        }

        /* Custom tooltip positioning for Steward/Scroll buttons */
        /* Position Steward (handshake) tooltip ABOVE, Scroll tooltip BELOW */
        /* This prevents tooltips from obscuring adjacent buttons */
        [data-baseweb="tooltip"] {
            z-index: 9999 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # Add keyboard navigation for demo slides using streamlit-specific approach
        current_idx = st.session_state.demo_slide_index
        max_idx = 15  # 0=welcome, 1-14=Q&A (14 slides), 15=congratulations

        # Use component HTML for reliable keyboard event handling
        import streamlit.components.v1 as components

        components.html(f"""
        <script>
        // Scroll to top when slide loads
        (function() {{
            window.scrollTo(0, 0);
            if (window.parent) {{
                window.parent.scrollTo(0, 0);
            }}
        }})();

        // Fix #1: WCAG ARIA Label Injection for Accessibility
        (function() {{
            const parent = window.parent;
            if (parent && parent.document) {{
                const buttons = parent.document.querySelectorAll('button');
                buttons.forEach(btn => {{
                    const text = btn.textContent.trim();
                    // Add aria-label based on button content
                    if (text.includes('Previous')) {{
                        btn.setAttribute('aria-label', 'Go to previous slide');
                    }} else if (text.includes('Next')) {{
                        btn.setAttribute('aria-label', 'Go to next slide');
                    }} else if (text.includes('Start Demo')) {{
                        btn.setAttribute('aria-label', 'Start the TELOS demo walkthrough');
                    }} else if (text.includes('Show Alignment') || text.includes('Hide Alignment')) {{
                        btn.setAttribute('aria-label', 'Toggle alignment lens visibility');
                    }} else if (text.includes('BETA')) {{
                        btn.setAttribute('aria-label', 'Enter BETA testing mode');
                    }} else if (text.length <= 2 && !btn.getAttribute('aria-label')) {{
                        // Emoji buttons (single character or emoji which can be 2 chars)
                        if (btn.title || btn.getAttribute('data-testid')) {{
                            // Has other accessibility info
                        }} else {{
                            btn.setAttribute('aria-label', 'Action button');
                        }}
                    }} else if (text === 'Send') {{
                        btn.setAttribute('aria-label', 'Send message');
                    }} else if (text.includes('Choose A')) {{
                        btn.setAttribute('aria-label', 'Select response option A');
                    }} else if (text.includes('Choose B')) {{
                        btn.setAttribute('aria-label', 'Select response option B');
                    }}
                }});
                // Add role="main" to content area for landmark navigation
                const mainContent = parent.document.querySelector('[data-testid="stMainBlockContainer"]');
                if (mainContent && !mainContent.getAttribute('role')) {{
                    mainContent.setAttribute('role', 'main');
                    mainContent.setAttribute('aria-label', 'TELOS Observatory main content');
                }}
            }}
        }})();

        // Demo keyboard navigation
        (function() {{
            const currentSlide = {current_idx};
            const maxSlide = {max_idx};

            // Remove old listener if exists
            if (window.demoKeyListener) {{
                document.removeEventListener('keydown', window.demoKeyListener);
            }}

            // Create new listener
            window.demoKeyListener = function(event) {{
                // Only handle arrow keys, not modified
                if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;

                if (event.key === 'ArrowLeft' && currentSlide > 0) {{
                    event.preventDefault();
                    const parent = window.parent;
                    if (parent && parent.document) {{
                        const buttons = parent.document.querySelectorAll('button');
                        for (let btn of buttons) {{
                            if (btn.textContent.includes('Previous') || btn.textContent.includes('Back to Welcome') || btn.textContent.includes('⬅')) {{
                                btn.click();
                                break;
                            }}
                        }}
                    }}
                }} else if (event.key === 'ArrowRight' && currentSlide < maxSlide) {{
                    event.preventDefault();
                    const parent = window.parent;
                    if (parent && parent.document) {{
                        const buttons = parent.document.querySelectorAll('button');
                        for (let btn of buttons) {{
                            if (btn.textContent.includes('Next') ||
                                btn.textContent.includes('Start Demo') ||
                                btn.textContent.includes('Complete Demo') ||
                                btn.textContent.includes('➡')) {{
                                btn.click();
                                break;
                            }}
                        }}
                    }}
                }}
            }};

            // Attach listener to both current window and parent
            document.addEventListener('keydown', window.demoKeyListener);
            if (window.parent && window.parent.document) {{
                window.parent.document.addEventListener('keydown', window.demoKeyListener);
            }}
        }})();
        </script>
        """, height=0)

        # Get slides
        slides = get_demo_slides()
        current_idx = st.session_state.demo_slide_index

        # Slide 0: Welcome screen - centered and compact
        if current_idx == 0:

            st.markdown(f"""
<div class="compact-container" key="slide-0">
    <div data-slide="0" style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
                border: 2px solid #F4D03F;
                border-radius: 15px;
                padding: 20px;
                margin: 10px auto 30px auto;
                text-align: center;
                box-shadow: 0 0 8px rgba(255, 215, 0, 0.4);
                opacity: 0;
                animation: slideContentFadeIn 1.0s ease-out forwards;
                animation-fill-mode: forwards;">
        <h1 style="color: #F4D03F; font-size: 28px; margin-bottom: 12px;">Welcome to TELOS Demo Mode!</h1>
        <div style="text-align: left; max-width: 700px; margin: 0 auto;">
            <p style="color: #e0e0e0; font-size: 16px; line-height: 1.5; margin-bottom: 10px;">
                Hello! I'm Steward, an AI assistant governed by TELOS and your guide.
                I'll walk you through how TELOS keeps me aligned with your goals through real-time governance -- ensuring I stay accountable to what you actually want, not where the conversation might drift.
            </p>
            <p style="color: #e0e0e0; font-size: 16px; line-height: 1.5; margin-bottom: 10px;">
                There are three ways to explore. <strong style="color: #F4D03F;">DEMO</strong> walks through conversational governance -- how TELOS measures alignment, detects drift, and intervenes when needed. <strong style="color: #F4D03F;">AGENTIC</strong> shows where this is heading -- governance for AI agents that don't just talk, but act. And <strong style="color: #F4D03F;">BETA</strong> lets you experience live TELOS governance yourself.
            </p>
            <p style="color: #e0e0e0; font-size: 16px; line-height: 1.5; margin-bottom: 10px;">
                There's no required path. Start wherever draws your interest, move between them freely, skip what doesn't serve you. This is your time -- use it however feels most useful. I'll be here throughout, wherever you choose to begin.
            </p>
            <p style="color: #e0e0e0; font-size: 16px; line-height: 1.5; margin-bottom: 8px;">
                Click <strong style="color: #F4D03F;">Start Demo</strong> below, or select your starting point from the tabs above.
            </p>
        </div>
    </div>
</div>
<style>
@keyframes slideContentFadeIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
</style>
""", unsafe_allow_html=True)

            # Wrap button in 700px container to match 3-button layout width
            st.markdown("""
            <style>
            .nav-button-container {
                max-width: 700px;
                margin: 0 auto;
                padding: 0 10px;
            }
            </style>
            <div class="nav-button-container">
            """, unsafe_allow_html=True)

            # Use 3 columns with button in center for consistent sizing
            col_empty_left, col_center, col_empty_right = st.columns(3)
            with col_center:
                if st.button("Start Demo", key="start_demo_btn", use_container_width=True, type="primary"):
                    st.session_state.demo_slide_index = 1  # Go directly to first Q&A slide
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)
            return

        # Slides 1-12: Q&A pairs (slides[0] through slides[11]) - 12 Q&A slides
        if 1 <= current_idx <= len(slides):
            slide_idx = current_idx - 1  # slides[0] through slides[12]
            user_question, steward_response = slides[slide_idx]

            # Turn numbers start at 11 (PA already established in turns 1-10)
            turn_num = slide_idx + 11  # Turn 11-19

            # Fix #5: Progress indicator - will be shown inline with navigation buttons
            total_slides = len(slides)

            # Render demo slide
            self._render_demo_slide_with_typewriter(
                user_question,
                steward_response,
                turn_num,
                current_idx
            )
            return

        # Demo completion: After all Q&A slides (len(slides)+1), show congratulations
        if current_idx == len(slides) + 1:
            # Enable BETA tab unlock
            st.session_state.demo_completed = True

            # Clean completion card
            completion_html = """
<div class="compact-container">
    <div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45);
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
                border: 2px solid #27ae60;
                border-radius: 12px;
                padding: 25px 30px;
                margin: 15px auto;
                font-size: 20px;
                line-height: 1.7;
                color: #e0e0e0;
                box-shadow: 0 0 20px rgba(76, 175, 80, 0.25), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);
                opacity: 0;
                animation: slideContentFadeIn 1.0s ease-out forwards;
                animation-fill-mode: forwards;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #27ae60; font-size: 32px; margin: 0 0 8px 0;">You've Completed the TELOS Demo</h2>
        </div>
        <div style="border-top: 1px solid rgba(76, 175, 80, 0.3); padding-top: 20px; margin-top: 10px;">
            <div style="margin-bottom: 15px;">
                You now understand how TELOS works: constitutional governance that measures alignment, detects drift, and intervenes proportionally to maintain accountability to stated purpose.
            </div>
            <div>
                <strong style="color: #F4D03F;">Ready for BETA?</strong> Click the <strong style="color: #F4D03F;">BETA</strong> button below to experience live TELOS governance -- real PA calibration, dynamic fidelity scores, and actual interventions. Click <strong style="color: #F4D03F;">Ask Steward</strong> at the top of your BETA session to ask me questions about what you're seeing.
            </div>
        </div>
    </div>
</div>
<style>
@keyframes slideContentFadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
"""
            st.markdown(completion_html, unsafe_allow_html=True)

            # Spacing before buttons (matches other slides)
            st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

            # 2 columns: Previous | BETA
            col_prev, col_beta = st.columns(2)

            with col_prev:
                if st.button("Previous", key="completion_prev", use_container_width=True):
                    st.session_state.demo_slide_index = len(slides)  # Go back to last Q&A slide
                    st.rerun()

            with col_beta:
                if st.button("BETA", key="completion_beta", use_container_width=True):
                    st.session_state.active_tab = "BETA"
                    st.rerun()

            return

    def _render_demo_slide_with_typewriter(self, user_question: str, steward_response: str, turn_num: int, current_idx: int):
        """Render a single demo slide - both question and response appear immediately."""
        import re

        # Reset Alignment Lens when slide changes (user navigated to a different slide)
        if 'last_demo_slide' in st.session_state and st.session_state.last_demo_slide != current_idx:
            self._reset_all_alignment_lens_states()

        # Slide 8: Quantum physics drift event (orange zone) - Moderate Drift
        # Handle this BEFORE rendering standard Q&A (slides[7] = current_idx 8)
        if current_idx == 8:
            # Reset visibility states when first entering slide 8
            if 'last_demo_slide' not in st.session_state or st.session_state.last_demo_slide != 8:
                st.session_state.slide_6_obs_deck_visible = False
            st.session_state.last_demo_slide = 8
            self._render_slide_7_drift_detection(turn_num)
            return

        # Slide 9: Movies drift event (red zone) - Significant Drift
        # Handle this BEFORE rendering standard Q&A (slides[8] = current_idx 9)
        if current_idx == 9:
            # Reset visibility states when first entering slide 9
            if 'last_demo_slide' not in st.session_state or st.session_state.last_demo_slide != 9:
                st.session_state.slide_7_obs_deck_visible = False
            st.session_state.last_demo_slide = 9
            self._render_slide_8_movies_drift(turn_num)
            return

        # Calculate dual fidelities based on slide content
        # 14-SLIDE STRUCTURE:
        # Slide 1 (idx 1): What is TELOS - no fidelities shown (PA not established)
        # Slide 2 (idx 2): PA Established - fidelities start showing, 1.000/1.000
        # Slide 3 (idx 3): Why this approach is credible - 1.000/1.000
        # Slide 4 (idx 4): Understanding Alignment Lens - 1.000/1.000
        # Slide 5 (idx 5): Why fidelities at 1.00 - 1.000/1.000
        # Slide 6 (idx 6): Math question (YELLOW) - 0.69/0.82 (user contradicts PA)
        # Slide 7 (idx 7): How drift detection works - 0.88/0.90 (back to green)
        # Slide 8 (idx 8): Quantum physics (ORANGE) - 0.55/0.88 (moderate drift) - SPECIAL RENDERER
        # Slide 9 (idx 9): Movies (RED) - 0.42/0.85 (significant drift) - SPECIAL RENDERER
        # Slide 10 (idx 10): Wrap-up - 0.88/0.90
        # Slide 11 (idx 11): Beyond individual - 0.92/0.95
        # Slide 12 (idx 12): Healthcare scenario - 0.88/0.90
        # Slide 13 (idx 13): Financial services - 0.88/0.90
        # Slide 14 (idx 14): Differentiator - 0.88/0.90

        # Fidelities start showing from slide 3 (after PA establishment on slide 2)
        show_fidelities = current_idx >= 3

        if current_idx == 1:  # Slide 1: What is TELOS - no fidelities yet (PA not established)
            user_fidelity = 1.000
            ai_fidelity = 1.000
        elif current_idx == 2:  # Slide 2: PA Established - perfect alignment (PA gets established here)
            user_fidelity = 1.000
            ai_fidelity = 1.000
        elif current_idx == 3:  # Slide 3: Why this approach is credible - still perfect
            user_fidelity = 1.000
            ai_fidelity = 1.000
        elif current_idx == 4:  # Slide 4: Understanding Alignment Lens - still perfect
            user_fidelity = 1.000  # Perfect alignment - on topic
            ai_fidelity = 1.000   # Perfect alignment - on topic
        elif current_idx == 5:  # Slide 5: Why fidelities at 1.00 - still perfect (GREEN)
            user_fidelity = 1.000  # Perfect alignment - axis point
            ai_fidelity = 1.000   # Perfect alignment - axis point
        elif current_idx == 6:  # Slide 6: Math question - YELLOW ZONE (contradicts PA)
            user_fidelity = 0.69  # User asked for math (contradicts "practical language")
            ai_fidelity = 0.82   # AI answers anyway instead of redirecting
        elif current_idx == 7:  # Slide 7: How drift detection works - GREEN (back aligned)
            user_fidelity = 0.88  # Returns to aligned after course correction
            ai_fidelity = 0.90
        elif current_idx == 8:  # Slide 8: Quantum physics - ORANGE ZONE (handled by special renderer)
            user_fidelity = 0.55  # Moderate drift - off-topic question
            ai_fidelity = 0.88   # AI redirects appropriately
        elif current_idx == 9:  # Slide 9: Movies - RED ZONE significant drift (handled by special renderer)
            user_fidelity = 0.42  # User completely off topic
            ai_fidelity = 0.85   # AI stays aligned by blocking and redirecting
        elif current_idx == 10:  # Slide 10: Wrap-up - back to aligned
            user_fidelity = 0.88  # Returns to aligned after course correction
            ai_fidelity = 0.90
        elif current_idx == 11:  # Slide 11: Beyond individual - strong alignment
            user_fidelity = 0.92
            ai_fidelity = 0.95
        elif current_idx == 12:  # Slide 12: Healthcare scenario - aligned
            user_fidelity = 0.88
            ai_fidelity = 0.90
        elif current_idx == 13:  # Slide 13: Financial services - aligned
            user_fidelity = 0.88
            ai_fidelity = 0.90
        elif current_idx == 14:  # Slide 14: Differentiator - aligned
            user_fidelity = 0.88
            ai_fidelity = 0.90
        else:  # Slide 15+ (shouldn't render Q&A content)
            user_fidelity = 0.88
            ai_fidelity = 0.90

        # Calculate Primacy State using actual TELOS formula
        # PS = ρ_PA · (2·F_user·F_AI)/(F_user + F_AI)
        # For demo, assume ρ_PA = 1.0 (perfectly aligned attractors)
        epsilon = 1e-10
        if user_fidelity + ai_fidelity > epsilon:
            harmonic_mean = (2 * user_fidelity * ai_fidelity) / (user_fidelity + ai_fidelity + epsilon)
        else:
            harmonic_mean = 0.0
        primacy_state = harmonic_mean  # ρ_PA = 1.0 for demo

        # Determine colors based on fidelity zones (from telos_core.constants)
        # Green (>=0.70): Aligned | Yellow (0.60-0.70): Minor Drift | Orange (0.50-0.60): Drift Detected | Red (<0.50): Significant Drift
        from telos_observatory.config.colors import get_fidelity_color

        user_color = get_fidelity_color(user_fidelity)
        ai_color = get_fidelity_color(ai_fidelity)
        ps_color = get_fidelity_color(primacy_state)

        # Show PA Established status
        status_msg = "PA Established"
        status_color = "#27ae60"  # Standard green (not fluorescent)

        # Clean markdown from response - convert to plain text with HTML formatting
        def clean_markdown(text):
            # First, handle markdown links [text](url) -> clickable <a> tags
            text = re.sub(
                r'\[([^\]]+)\]\(([^)]+)\)',
                r'<a href="\2" target="_blank" style="color: #F4D03F; text-decoration: underline;">\1</a>',
                text
            )
            # Handle **bold** (do this before italic to avoid conflicts)
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color: #F4D03F;">\1</strong>', text)
            # Then handle *italic* (only single asterisks not already in bold)
            text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
            # Convert bullet points to HTML bullets
            text = re.sub(r'^- ', '• ', text, flags=re.MULTILINE)
            # Keep numbered lists as-is (they render fine)
            return text

        cleaned_response = clean_markdown(steward_response)

        # ORDER: User question first, then fidelity boxes, then Steward response
        # This matches the BETA mode layout

        # USER QUESTION - Wrapped in compact container with fidelity-colored border and turn badge
        st.markdown(f"""
<div class="compact-container" key="slide-{current_idx}">
    <div data-slide="{current_idx}" style="
        display: flex;
        align-items: flex-start;
        gap: 12px;
        background-color: #2d2d2d;
        border: 2px solid {user_color};
        border-radius: 10px;
        padding: 20px 25px;
        margin: 15px auto;
        font-size: 20px;
        color: #e0e0e0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        opacity: 0;
        animation: slideContentFadeIn 1.0s ease-out forwards;
        animation-fill-mode: forwards;">
        <div style="
            min-width: 32px;
            height: 32px;
            background-color: #1a1a1a;
            border: 2px solid {user_color};
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: bold;
            color: #e0e0e0;
            flex-shrink: 0;">{current_idx}</div>
        <div style="flex: 1;">{user_question}</div>
    </div>
</div>
""", unsafe_allow_html=True)

        # Fidelity boxes REMOVED from main display - now only shown in Alignment Lens popup
        # PA Established banner REMOVED - cluttered the interface

        # STEWARD RESPONSE - Appears after fidelities, wrapped in compact container with fidelity-colored border
        st.markdown(f"""
<div class="compact-container" key="response-{current_idx}">
    <div data-slide="{current_idx}" style="
        background: linear-gradient(135deg, rgba(255, 215, 0, 0.05) 0%, rgba(255, 215, 0, 0.1) 100%);
        border: 2px solid {ai_color};
        border-radius: 10px;
        padding: 20px 25px;
        margin: 15px auto;
        font-size: 20px;
        color: #e0e0e0;
        line-height: 1.7;
        box-shadow: 0 2px 8px rgba(255, 215, 0, 0.2);
        opacity: 0;
        animation: slideContentFadeIn 1.0s ease-out 0.4s forwards;
        animation-fill-mode: forwards;">
        <div>{cleaned_response.replace(chr(10), '<br>')}</div>
    </div>
</div>

<style>
.pulse-ring {{
    width: 40px;
    height: 40px;
    border: 3px solid #F4D03F;
    border-radius: 50%;
    margin: 0 auto 10px auto;
    animation: pulse 1.5s ease-in-out infinite;
}}

@keyframes pulse {{
    0%, 100% {{ transform: scale(0.8); opacity: 0.5; }}
    50% {{ transform: scale(1.1); opacity: 1; }}
}}

@keyframes slideContentFadeIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
</style>
""", unsafe_allow_html=True)

        # Slide 2: Show Alignment Lens after Q&A content (PA gets established here)
        if current_idx == 2:
            st.session_state.last_demo_slide = 2
            self._render_demo_observation_deck(turn_num)
            return

        # Slide 1: Simple navigation without Alignment Lens (PA not established yet)
        if current_idx == 1:
            # Add spacing between content and navigation buttons (30px matches top spacing)
            st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)
            st.session_state.last_demo_slide = 1

            # Wrap buttons in 700px container to match 3-button layout width
            st.markdown("""
            <style>
            .nav-button-container {
                max-width: 700px;
                margin: 0 auto;
                padding: 0 10px;
            }
            </style>
            <div class="nav-button-container">
            """, unsafe_allow_html=True)

            # Use 2 columns for navigation buttons
            col_prev, col_next = st.columns(2)
            with col_prev:
                if st.button("Back to Welcome", key="prev_slide_1", use_container_width=True):
                    st.session_state.demo_slide_index = 0  # Back to welcome
                    st.rerun()
            with col_next:
                if st.button("Next", key="next_slide_1", use_container_width=True):
                    st.session_state.demo_slide_index = 2
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)
            return

        # Navigation buttons - Previous | Alignment Lens | Next (3 buttons)
        # Add spacing between content and navigation buttons (30px matches top spacing)
        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        # Track current slide
        st.session_state.last_demo_slide = current_idx

        # Initialize Alignment Lens toggle state for standard slides
        if 'demo_std_obs_deck_visible' not in st.session_state:
            st.session_state.demo_std_obs_deck_visible = False

        # Only render top navigation buttons when observation deck is NOT visible
        # When visible, _render_standard_observation_deck_content handles all navigation
        if not st.session_state.demo_std_obs_deck_visible:
            # Container for centering
            st.markdown("<div style='max-width: 700px; margin: 0 auto; padding: 0 10px;'>", unsafe_allow_html=True)

            # 3 buttons: Previous | Alignment Lens | Next - equal width like fidelity boxes
            col_prev, col_obs, col_next = st.columns(3)

            with col_prev:
                if st.button("Previous", key=f"prev_slide_{current_idx}", use_container_width=True):
                    st.session_state.demo_slide_index -= 1
                    st.rerun()

            with col_obs:
                if st.button("Show Alignment Lens", key=f"obs_deck_toggle_{current_idx}", use_container_width=True, type="primary"):
                    st.session_state.demo_std_obs_deck_visible = True
                    st.rerun()

            with col_next:
                if st.button("Next", key=f"next_slide_{current_idx}", use_container_width=True):
                    st.session_state.demo_slide_index += 1
                    # If moving from last Q&A slide to completion, unlock BETA
                    from telos_observatory.demo_mode.telos_framework_demo import get_demo_slides
                    num_slides = len(get_demo_slides())
                    if current_idx == num_slides:  # Last Q&A slide
                        st.session_state.demo_completed = True
                    st.rerun()

            # Close the wrapper div
            st.markdown("</div>", unsafe_allow_html=True)

        # Render Alignment Lens content if visible
        if st.session_state.demo_std_obs_deck_visible:
            # Auto-scroll to observation deck content
            st.markdown("""
<script>
    setTimeout(function() {
        window.scrollTo({
            top: document.body.scrollHeight,
            behavior: 'smooth'
        });
    }, 100);
</script>
""", unsafe_allow_html=True)
            self._render_standard_observation_deck_content(current_idx)

    def _render_slide_7_drift_detection(self, turn_num: int):
        """Render slide 6 with drift detection and progressive Alignment Lens (quantum physics drift)."""

        # Initialize session state for drift event visibility
        if 'slide_7_drift_visible' not in st.session_state:
            st.session_state.slide_7_drift_visible = False

        # Show fidelity metrics with drift values - inline format matching other slides
        # Slide 6 values: User drifted (0.59 orange), AI stayed aligned (0.89 green)
        user_fidelity = 0.59
        ai_fidelity = 0.89
        # Calculate Primacy State: PS = (2 * F_user * F_ai) / (F_user + F_ai)
        primacy_state = (2 * user_fidelity * ai_fidelity) / (user_fidelity + ai_fidelity)

        # Determine colors based on Goldilocks fidelity zones
        from telos_observatory.config.colors import get_fidelity_color
        user_color = get_fidelity_color(user_fidelity)
        ai_color = get_fidelity_color(ai_fidelity)
        # Primacy State border color should match actual primacy_state value
        ps_color = get_fidelity_color(primacy_state)

        # Animation styles - unique name to prevent browser caching between slide transitions
        st.markdown("""
<style>
@keyframes slideContentFadeIn8 {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)

        # Drift event - User question with border color matching USER fidelity
        # User prompt comes FIRST, then fidelity boxes below it
        # FORMAT: Turn badge + question text (matches standard slides)
        st.markdown(f"""
<div class="compact-container">
    <div style="
        display: flex;
        align-items: flex-start;
        gap: 12px;
        background-color: #2d2d2d;
        border: 2px solid {user_color};
        border-radius: 10px;
        padding: 20px 25px;
        margin: 15px auto;
        max-width: 700px;
        font-size: 20px;
        color: #e0e0e0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        opacity: 0;
        animation: slideContentFadeIn8 1.0s ease-out forwards;
        animation-fill-mode: forwards;">
        <div style="
            min-width: 32px;
            height: 32px;
            background-color: #1a1a1a;
            border: 2px solid {user_color};
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: bold;
            color: #e0e0e0;
            flex-shrink: 0;">8</div>
        <div style="flex: 1;">Can you explain quantum physics instead?</div>
    </div>
</div>
        """, unsafe_allow_html=True)

        # Fidelity boxes HIDDEN on main view - only show via Alignment Lens button
        # The colored borders on the question/response provide visual cue of drift

        # Steward response with border color matching AI fidelity
        st.markdown(f"""
        <div style='max-width: 700px; margin: 20px auto;'>
            <div style='background-color: rgba(46, 204, 113, 0.05); border: 3px solid {ai_color}; border-radius: 10px; padding: 20px 25px; box-shadow: 0 0 15px rgba(46, 204, 113, 0.2); opacity: 0; animation: slideContentFadeIn8 1.0s ease-out 0.3s forwards;'>
                <div style='color: {ai_color}; font-size: 20px; line-height: 1.6; margin-bottom: 15px;'>
                    That's an intriguing topic, but it falls outside your stated purpose of understanding TELOS. Your goal here is to understand TELOS without technical overwhelm, so let me keep us focused on that.
                </div>
                <div style='color: #e0e0e0; font-size: 20px; line-height: 1.6;'>
                    Your User Fidelity dropped to <strong style='color: #e67e22;'>orange zone (moderate drift)</strong> when your question moved away from your goal. Meanwhile, my AI Fidelity stayed high by gently bringing us back on track. I am governed by your purpose—your <em>τέλος</em>. This is dual measurement in action.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Navigation buttons (always visible) - 3-button layout: Previous | Alignment Lens | Next
        # Add spacing between content and navigation buttons (30px matches top spacing)
        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        # Initialize Alignment Lens visibility for slide 6
        if 'slide_6_obs_deck_visible' not in st.session_state:
            st.session_state.slide_6_obs_deck_visible = False

        # Wrap buttons in 700px container
        st.markdown("<div style='max-width: 700px; margin: 0 auto; padding: 0 10px;'>", unsafe_allow_html=True)

        # Use 3 columns for consistent width
        col_prev, col_obs_deck, col_next = st.columns(3)

        with col_prev:
            if st.button("Previous", key="slide_7_prev", use_container_width=True):
                # Reset visibility states when going back
                st.session_state.slide_7_drift_visible = False
                st.session_state.slide_6_obs_deck_visible = False
                st.session_state.show_observatory_lens = False
                st.session_state.steward_panel_open = False
                st.session_state.demo_slide_index = 7  # Go back to "How does TELOS detect drift"
                st.rerun()

        with col_obs_deck:
            # Alignment Lens toggle button
            obs_deck_active = st.session_state.slide_6_obs_deck_visible
            obs_btn_text = "Hide Alignment Lens" if obs_deck_active else "Show Alignment Lens"

            if st.button(
                obs_btn_text,
                key="slide_6_obs_deck_toggle",
                use_container_width=True,
                type="primary" if not obs_deck_active else "secondary"
            ):
                st.session_state.slide_6_obs_deck_visible = not obs_deck_active
                st.rerun()

        with col_next:
            if st.button("Next", key="slide_7_next", use_container_width=True):
                st.session_state.demo_slide_index = 9  # Go to Movies slide (current_idx 9)
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # CSS injection for Alignment Lens button with fidelity-colored border - ORANGE for slide 6
        # Must be AFTER buttons are created (like tab styling in main.py)
        st.markdown(f"""
        <style>
        /* Style Alignment Lens button (middle column) - exclude tab bar with :not(:first-of-type) */
        div[data-testid="stHorizontalBlock"]:not(:first-of-type) > div:nth-child(2) button[kind="primary"],
        div[data-testid="stHorizontalBlock"]:not(:first-of-type) > div:nth-child(2) button[kind="secondary"] {{
            background-color: #2d2d2d !important;
            border: 2px solid {user_color} !important;
            color: #e0e0e0 !important;
        }}
        div[data-testid="stHorizontalBlock"]:not(:first-of-type) > div:nth-child(2) button[kind="primary"]:hover,
        div[data-testid="stHorizontalBlock"]:not(:first-of-type) > div:nth-child(2) button[kind="secondary"]:hover {{
            background-color: #3d3d3d !important;
            border: 2px solid {user_color} !important;
        }}
        </style>
        """, unsafe_allow_html=True)

        # Render Alignment Lens if visible
        if st.session_state.slide_6_obs_deck_visible:
            # Auto-scroll to observation deck content
            st.markdown("""
<script>
    setTimeout(function() {
        window.scrollTo({
            top: document.body.scrollHeight,
            behavior: 'smooth'
        });
    }, 100);
</script>
""", unsafe_allow_html=True)
            st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)
            self._render_slide_6_observation_deck_content()

    def _render_slide_8_movies_drift(self, turn_num: int):
        """Render slide 7 (Movies) with RED zone drift - rebuilt from scratch using standard template."""

        # Movies slide fidelity values
        user_fidelity = 0.42
        ai_fidelity = 0.85
        primacy_state = (2 * user_fidelity * ai_fidelity) / (user_fidelity + ai_fidelity)

        from telos_observatory.config.colors import get_fidelity_color
        user_color = get_fidelity_color(user_fidelity)
        ai_color = get_fidelity_color(ai_fidelity)
        ps_color = get_fidelity_color(primacy_state)

        # Animation styles - unique name to prevent browser caching between slide transitions
        st.markdown("""
<style>
@keyframes slideContentFadeIn9 {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)

        # User question with turn badge
        st.markdown(f"""
<div class="compact-container">
    <div style="
        display: flex;
        align-items: flex-start;
        gap: 12px;
        background-color: #2d2d2d;
        border: 2px solid {user_color};
        border-radius: 10px;
        padding: 20px 25px;
        margin: 15px auto;
        max-width: 700px;
        font-size: 20px;
        color: #e0e0e0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        opacity: 0;
        animation: slideContentFadeIn9 1.0s ease-out forwards;
        animation-fill-mode: forwards;">
        <div style="
            min-width: 32px;
            height: 32px;
            background-color: #1a1a1a;
            border: 2px solid {user_color};
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: bold;
            color: #e0e0e0;
            flex-shrink: 0;">9</div>
        <div style="flex: 1;">Tell me about your favorite movies.</div>
    </div>
</div>
""", unsafe_allow_html=True)

        # Fidelity boxes HIDDEN on main view - only show via Alignment Lens button
        # The colored borders on the question/response provide visual cue of drift

        # Steward response
        st.markdown(f"""
<div style='max-width: 700px; margin: 15px auto;'>
    <div style='background-color: rgba(46, 204, 113, 0.05); border: 3px solid {ai_color}; border-radius: 10px; padding: 20px 25px; box-shadow: 0 0 15px rgba(46, 204, 113, 0.2); opacity: 0; animation: slideContentFadeIn9 1.0s ease-out 0.3s forwards;'>
        <div style='color: {ai_color}; font-size: 20px; line-height: 1.6; margin-bottom: 15px;'>
            That's quite far from our purpose here. What would you like to know about how TELOS keeps both of us working toward the same goal?
        </div>
        <div style='color: #e0e0e0; font-size: 20px; line-height: 1.6;'>
            Your fidelity just dropped to <strong style='color: #E74C3C;'>red - significant drift</strong> from your stated purpose. This is far outside understanding TELOS with practical language. At this level, TELOS activates strong intervention. I'm redirected back to serving your original goal rather than following wherever the conversation wanders. This protects the integrity of purpose-aligned conversations.
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

        # Navigation - standard format
        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        if 'slide_7_obs_deck_visible' not in st.session_state:
            st.session_state.slide_7_obs_deck_visible = False

        # Only show top nav when Alignment Lens is hidden (matches standard format)
        if not st.session_state.slide_7_obs_deck_visible:
            # Wrap buttons in 700px container
            st.markdown("<div style='max-width: 700px; margin: 0 auto; padding: 0 10px;'>", unsafe_allow_html=True)

            col_prev, col_obs, col_next = st.columns(3)

            with col_prev:
                if st.button("Previous", key="slide7_prev", use_container_width=True):
                    st.session_state.demo_slide_index = 8  # Go back to slide 8 (quantum physics)
                    st.rerun()

            with col_obs:
                if st.button("Show Alignment Lens", key="slide7_obs_toggle", use_container_width=True, type="primary"):
                    st.session_state.slide_7_obs_deck_visible = True
                    st.rerun()

            with col_next:
                if st.button("Next", key="slide7_next", use_container_width=True):
                    st.session_state.demo_slide_index = 10  # Go to Wrap-up slide
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

            # CSS injection for Alignment Lens button with fidelity-colored border - RED for slide 7
            # Must be AFTER buttons are created (like tab styling in main.py)
            st.markdown(f"""
            <style>
            /* Style Alignment Lens button (middle column) - exclude tab bar with :not(:first-of-type) */
            div[data-testid="stHorizontalBlock"]:not(:first-of-type) > div:nth-child(2) button[kind="primary"],
            div[data-testid="stHorizontalBlock"]:not(:first-of-type) > div:nth-child(2) button[kind="secondary"] {{
                background-color: #2d2d2d !important;
                border: 2px solid {user_color} !important;
                color: #e0e0e0 !important;
            }}
            div[data-testid="stHorizontalBlock"]:not(:first-of-type) > div:nth-child(2) button[kind="primary"]:hover,
            div[data-testid="stHorizontalBlock"]:not(:first-of-type) > div:nth-child(2) button[kind="secondary"]:hover {{
                background-color: #3d3d3d !important;
                border: 2px solid {user_color} !important;
            }}
            </style>
            """, unsafe_allow_html=True)

            return  # Don't render Alignment Lens content when hidden

        # Alignment Lens content (only when visible)
        st.markdown("""
<script>
    setTimeout(function() {
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    }, 100);
</script>
""", unsafe_allow_html=True)

        # Animation styles for Alignment Lens
        st.markdown("""
<style>
@keyframes obsDeckFadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)

        # Alignment Lens header - compact horizontal bar format with RED border for significant drift
        st.markdown(f"""
<div style="max-width: 700px; margin: 20px auto; opacity: 0; animation: obsDeckFadeIn 1.0s ease-in-out forwards;">
    <div style="background-color: #1a1a1a; border: 2px solid #E74C3C; border-radius: 8px; padding: 12px 20px; box-shadow: 0 0 15px rgba(231, 76, 60, 0.2); display: flex; justify-content: space-between; align-items: center;">
        <span style="color: #E74C3C; font-size: 18px; font-weight: bold;">Alignment Lens</span>
        <span style="background-color: #2d2d2d; border: 1px solid #E74C3C; border-radius: 15px; padding: 6px 16px; color: #E74C3C; font-weight: bold; font-size: 13px;">SIGNIFICANT DRIFT</span>
    </div>
</div>
""", unsafe_allow_html=True)

        # Fidelity boxes in Alignment Lens
        st.markdown(f"""
<div style="display: flex; justify-content: center; gap: 10px; margin: 15px auto; max-width: 700px;">
    <div style="background-color: #1a1a1a; border: 2px solid {user_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1;">
        <div style="color: {user_color}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">User Fidelity</div>
        <div style="color: {user_color}; font-size: 42px; font-weight: bold;">{int(round(user_fidelity * 100))}%</div>
        <div style="color: #E74C3C; font-size: 14px; margin-top: 8px;">RED ZONE - Significant Drift</div>
    </div>
    <div style="background-color: #1a1a1a; border: 2px solid {ai_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1;">
        <div style="color: {ai_color}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">AI Fidelity</div>
        <div style="color: {ai_color}; font-size: 42px; font-weight: bold;">{int(round(ai_fidelity * 100))}%</div>
        <div style="color: #27ae60; font-size: 14px; margin-top: 8px;">GREEN ZONE - Aligned</div>
    </div>
    <div style="background-color: #1a1a1a; border: 2px solid {ps_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1;">
        <div style="color: {ps_color}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">Primacy State</div>
        <div style="color: {ps_color}; font-size: 42px; font-weight: bold;">{int(round(primacy_state * 100))}%</div>
        <div style="color: {ps_color}; font-size: 14px; margin-top: 8px;">ORANGE ZONE - Drift Detected</div>
    </div>
</div>
""", unsafe_allow_html=True)

        # Generate gradient rgba colors for PA headers (matching slide 6 format)
        from telos_observatory.config.colors import with_opacity
        user_gradient_start = with_opacity(user_color, 0.9)
        user_gradient_end = with_opacity(user_color, 0.85)
        ai_gradient_start = with_opacity(ai_color, 0.9)
        ai_gradient_end = with_opacity(ai_color, 0.85)

        # Dual Primacy Attractors - Two PA columns matching slide 6 format
        st.markdown(f"""
<div style="background-color: #1a1a1a; padding: 15px; border-radius: 10px; margin: 15px auto; border: 2px solid {ps_color}; max-width: 700px;">
    <div style="display: flex; gap: 15px;">
        <!-- User PA -->
        <div style="flex: 1; text-align: center;">
            <div style="background: linear-gradient(135deg, {user_gradient_start} 0%, {user_gradient_end} 100%); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); color: #1a1a1a; padding: 12px; border-radius: 8px 8px 0 0; font-weight: bold; font-size: 17px;">
                User Primacy Attractor
            </div>
            <div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid {user_color}; border-top: none; border-radius: 0 0 8px 8px; padding: 18px; text-align: center; box-shadow: 0 0 15px {user_gradient_start}, 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
                <div style="color: {user_color}; font-weight: bold; margin-bottom: 12px; font-size: 20px;">Your Purpose (Drifted)</div>
                <div style="color: #e0e0e0; line-height: 1.9; font-size: 15px; text-align: left;">
                    Understand TELOS without technical overwhelm<br/>
                    <span style="color: #E74C3C; font-style: italic;">Asked about movies instead</span>
                </div>
            </div>
        </div>
        <!-- AI PA -->
        <div style="flex: 1; text-align: center;">
            <div style="background: linear-gradient(135deg, {ai_gradient_start} 0%, {ai_gradient_end} 100%); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); color: #1a1a1a; padding: 12px; border-radius: 8px 8px 0 0; font-weight: bold; font-size: 17px;">
                Steward Attractor
            </div>
            <div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid {ai_color}; border-top: none; border-radius: 0 0 8px 8px; padding: 18px; text-align: center; box-shadow: 0 0 15px {ai_gradient_start}, 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
                <div style="color: {ai_color}; font-weight: bold; margin-bottom: 12px; font-size: 20px;">Steward's Role (Aligned)</div>
                <div style="color: #e0e0e0; line-height: 1.9; font-size: 15px; text-align: left;">
                    Align with your learning goals<br/>
                    <span style="color: #27ae60; font-style: italic;">Strong redirect back to TELOS</span>
                </div>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

        # Bottom navigation - matches standard format
        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)
        st.markdown('<div id="slide7-obs-deck-anchor"></div>', unsafe_allow_html=True)

        st.markdown("""
        <style>
        .nav-button-container { max-width: 700px; margin: 0 auto; padding: 0 10px; }
        div[data-testid="column"]:nth-child(2) button[data-testid="baseButton-primary"] {
            border: 2px solid #F4D03F !important;
            box-shadow: 0 0 5px rgba(244, 208, 63, 0.3) !important;
        }
        </style>
        <div class="nav-button-container">
        """, unsafe_allow_html=True)

        col_prev_bottom, col_toggle_bottom, col_next_bottom = st.columns(3)

        with col_prev_bottom:
            if st.button("Previous", key="slide7_obs_prev_bottom", use_container_width=True):
                st.session_state.slide_7_obs_deck_visible = False
                st.session_state.demo_slide_index = 8  # Go back to slide 8 (quantum physics)
                st.rerun()

        with col_toggle_bottom:
            if st.button("Hide Alignment Lens", key="slide7_obs_hide_bottom", use_container_width=True, type="primary"):
                st.session_state.slide_7_obs_deck_visible = False
                st.rerun()

        with col_next_bottom:
            if st.button("Next", key="slide7_obs_next_bottom", use_container_width=True):
                st.session_state.slide_7_obs_deck_visible = False
                st.session_state.demo_slide_index = 10  # Go to Wrap-up slide
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # Auto-scroll to anchor
        import streamlit.components.v1 as components
        components.html("""
            <script>
                setTimeout(function() {
                    var anchor = window.parent.document.getElementById('slide7-obs-deck-anchor');
                    if (anchor) {
                        anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }, 100);
            </script>
        """, height=0)

    def _render_demo_observatory_lens_slide_7(self):
        """Render simplified Alignment Lens for slide 7 drift demonstration."""
        # Alignment Lens Header with fade-in animation and glassmorphism
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 2px solid #F4D03F;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            opacity: 0;
            animation: fadeIn 1.0s ease-in-out forwards;
            box-shadow: 0 0 20px rgba(244, 208, 63, 0.2), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);
        ">
        <style>
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }
        </style>
            <div style="text-align: center; margin-bottom: 20px;">
                <h1 style="color: #F4D03F; margin: 0; font-weight: bold; letter-spacing: 3px; font-size: 48px;">
                    🔭 TELOSCOPE
                </h1>
                <div style="margin: 8px 0;">
                    <span style="color: #e0e0e0; font-size: 22px; letter-spacing: 1px;">Alignment Lens</span>
                    <span style="color: #27ae60; font-size: 20px; margin-left: 10px; font-style: italic;">✓ Active</span>
                </div>
                <p style="color: #ddd; font-size: 18px; margin: 12px 0 0 0;">
                    Live Governance Metrics
                </p>
                <p style="color: #ddd; font-size: 20px; margin: 5px 0 0 0;">
                    Real-Time Drift Detection - Turn 8
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 2x3 Grid of visualizations
        # Top row: Fidelity Gauges | Primacy State | Drift Alert
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("""
            <div style='text-align: center;'>
                <div style='background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid #FFD700; border-radius: 8px; padding: 15px; text-align: center; display: inline-block; width: 200px; max-width: 100%; box-shadow: 0 0 15px rgba(255, 215, 0, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);'>
                    <div style='color: #FFD700; font-size: 14px; font-weight: bold; margin-bottom: 10px;'>USER FIDELITY</div>
                    <div style='color: #FFD700; font-size: 56px; font-weight: bold;'>0.65</div>
                    <div style='color: #FFD700; font-size: 12px; margin-top: 5px;'>MINOR DRIFT</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown("""
            <div style='text-align: center;'>
                <div style='background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid #27ae60; border-radius: 8px; padding: 15px; text-align: center; display: inline-block; width: 200px; max-width: 100%; box-shadow: 0 0 15px rgba(76, 175, 80, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);'>
                    <div style='color: #27ae60; font-size: 14px; font-weight: bold; margin-bottom: 10px;'>AI FIDELITY</div>
                    <div style='color: #27ae60; font-size: 56px; font-weight: bold;'>0.89</div>
                    <div style='color: #27ae60; font-size: 12px; margin-top: 5px;'>✓ ALIGNED</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown("""
            <div style='text-align: center;'>
                <div style='background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid #F4D03F; border-radius: 8px; padding: 15px; text-align: center; display: inline-block; width: 200px; max-width: 100%; box-shadow: 0 0 15px rgba(244, 208, 63, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);'>
                    <div style='color: #F4D03F; font-size: 14px; font-weight: bold; margin-bottom: 10px;'>PRIMACY STATE</div>
                    <div style='color: #F4D03F; font-size: 56px; font-weight: bold;'>0.75</div>
                    <div style='color: #F4D03F; font-size: 12px; margin-top: 5px;'>YELLOW ZONE - Minor Drift</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

        # Bottom row: Intervention Status | Event Log | Drift Visualization
        col4, col5, col6 = st.columns(3)

        with col4:
            st.markdown("""
            <div style='background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid #FFD700; border-radius: 8px; padding: 15px; box-shadow: 0 0 15px rgba(255, 215, 0, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);'>
                <div style='color: #FFD700; font-size: 14px; font-weight: bold; margin-bottom: 15px; text-align: center;'>INTERVENTION STATUS</div>
                <div style='text-align: center; margin: 20px 0;'>
                    <div style='color: #FFD700; font-size: 20px; font-weight: bold; margin-bottom: 10px;'>Dual Fidelity Monitoring</div>
                    <div style='color: #FFD700; font-size: 13px; line-height: 1.6;'>
                        Both user and AI fidelities tracked. AI receives direct interventions; user receives awareness feedback.
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col5:
            st.markdown("""
            <div style='background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid #27ae60; border-radius: 8px; padding: 15px; box-shadow: 0 0 15px rgba(76, 175, 80, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);'>
                <div style='color: #27ae60; font-size: 14px; font-weight: bold; margin-bottom: 10px; text-align: center;'>EVENT LOG</div>
                <div style='margin: 8px 0; padding: 8px; background-color: rgba(26, 26, 26, 0.7); border-left: 3px solid #FFD700; border-radius: 3px;'>
                    <div style='color: #FFD700; font-size: 11px; font-weight: bold;'>USER DRIFT</div>
                    <div style='color: #ddd; font-size: 10px;'>Turn 8: Off-topic query (quantum physics)</div>
                </div>
                <div style='margin: 8px 0; padding: 8px; background-color: rgba(26, 26, 26, 0.7); border-left: 3px solid #27ae60; border-radius: 3px;'>
                    <div style='color: #27ae60; font-size: 11px; font-weight: bold;'>AI REDIRECT</div>
                    <div style='color: #ddd; font-size: 10px;'>AI responded with gentle redirect to TELOS topic</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col6:
            # DRIFT VISUALIZATION
            # Zone mapping: drift_distance = (1 - F) × radius
            # F >= 0.70: Green center (0-30%), F 0.60-0.69: Yellow (30-40%)
            # F 0.50-0.59: Orange (40-50%), F < 0.50: Red (50-100%)
            # Container: 150px, center at 75px, radius = 75px
            st.markdown("""
            <div style='background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid #F4D03F; border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 0 15px rgba(244, 208, 63, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);'>
                <div style='color: #F4D03F; font-size: 14px; font-weight: bold; margin-bottom: 15px;'>DRIFT VISUALIZATION</div>
                <div style='position: relative; width: 150px; height: 150px; margin: 0 auto;'>
                    <div style='position: absolute; top: 0; left: 0; width: 150px; height: 150px; background-color: #e74c3c; border-radius: 50%; border: 2px solid #F4D03F;'></div>
                    <div style='position: absolute; top: 25%; left: 25%; width: 75px; height: 75px; background-color: #e67e22; border-radius: 50%;'></div>
                    <div style='position: absolute; top: 30%; left: 30%; width: 60px; height: 60px; background-color: #F4D03F; border-radius: 50%;'></div>
                    <div style='position: absolute; top: 35%; left: 35%; width: 45px; height: 45px; background-color: #27ae60; border-radius: 50%;'></div>
                    <div style='position: absolute; top: 46%; left: 46%; width: 10px; height: 10px; background-color: #27ae60; border: 2px solid #fff; border-radius: 50%; transform: translate(-50%, -50%); z-index: 10;'></div>
                    <div style='position: absolute; top: 62.4%; left: 62.4%; width: 12px; height: 12px; background-color: #FFD700; border: 2px solid #fff; border-radius: 50%; transform: translate(-50%, -50%); animation: pulse 2s infinite; z-index: 10;'></div>
                </div>
                <div style='margin-top: 15px;'>
                    <div style='color: #27ae60; font-size: 13px;'>● Aligned (F ≥ 0.70)</div>
                    <div style='color: #F4D03F; font-size: 13px;'>● Minor Drift (0.60-0.69)</div>
                    <div style='color: #e67e22; font-size: 13px;'>● Drift Detected (0.50-0.59)</div>
                    <div style='color: #e74c3c; font-size: 13px;'>● Significant Drift (F < 0.50)</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Duplicate navigation at bottom when Alignment Lens is shown
        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        col_left_nav_bottom, col_center_nav_bottom, col_right_nav_bottom = st.columns([0.3, 3.4, 0.3])

        with col_center_nav_bottom:
            col_prev_bottom, col_toggle_bottom, col_next_bottom = st.columns(3)

            with col_prev_bottom:
                if st.button("Previous", key="slide_7_prev_bottom", use_container_width=True):
                    st.session_state.slide_7_drift_visible = False
                    st.session_state.show_observatory_lens = False
                    st.session_state.steward_panel_open = False
                    st.session_state.demo_slide_index = 7  # Go back to "How does TELOS detect drift"
                    st.rerun()

            with col_toggle_bottom:
                if st.button(
                    "Hide Alignment Lens",
                    key="slide_7_observatory_toggle_bottom",
                    use_container_width=True,
                    type="primary",
                    help="Hide the Alignment Lens visualization"
                ):
                    st.session_state.slide_7_drift_visible = False
                    st.rerun()

            with col_next_bottom:
                if st.button("Next", key="slide_7_next_bottom", use_container_width=True):
                    st.session_state.demo_slide_index = 9  # Go to Movies slide
                    st.rerun()

    def _render_slide_6_observation_deck_content(self):
        """Render Alignment Lens content specifically for slide 8 (quantum physics - ORANGE zone)."""
        # Slide 8 fidelity values: User asked about quantum physics (0.55 orange), AI redirected (0.88 green)
        user_fidelity = 0.55
        ai_fidelity = 0.88
        primacy_state = (2 * user_fidelity * ai_fidelity) / (user_fidelity + ai_fidelity)

        # Determine colors based on Goldilocks fidelity zones
        from telos_observatory.config.colors import get_fidelity_color, with_opacity
        user_color = get_fidelity_color(user_fidelity)
        ai_color = get_fidelity_color(ai_fidelity)
        ps_color = get_fidelity_color(primacy_state)
        # Generate gradient rgba colors for PA headers
        user_gradient_start = with_opacity(user_color, 0.9)
        user_gradient_end = with_opacity(user_color, 0.85)
        ai_gradient_start = with_opacity(ai_color, 0.9)
        ai_gradient_end = with_opacity(ai_color, 0.85)

        # Animation styles
        st.markdown("""
<style>
@keyframes obsDeckFadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)

        # Determine drift status based on User Fidelity (user alignment is primary)
        if user_fidelity >= 0.70:
            drift_status = "Aligned"
            drift_color = "#27ae60"
        elif user_fidelity >= 0.60:
            drift_status = "Minor Drift"
            drift_color = "#F4D03F"
        elif user_fidelity >= 0.50:
            drift_status = "Moderate Drift"
            drift_color = "#e67e22"
        else:
            drift_status = "Severe Drift"
            drift_color = "#e74c3c"

        # Alignment Lens header - compact horizontal bar format
        st.markdown(f"""
<div style="max-width: 700px; margin: 20px auto; opacity: 0; animation: obsDeckFadeIn 1.0s ease-in-out forwards;">
    <div style="background-color: #1a1a1a; border: 2px solid {user_color}; border-radius: 8px; padding: 12px 20px; box-shadow: 0 0 15px rgba(255, 215, 0, 0.2); display: flex; justify-content: space-between; align-items: center;">
        <span style="color: {user_color}; font-size: 18px; font-weight: bold;">Alignment Lens</span>
        <span style="background-color: #2d2d2d; border: 1px solid {drift_color}; border-radius: 15px; padding: 6px 16px; color: {drift_color}; font-weight: bold; font-size: 13px;">{drift_status}</span>
    </div>
</div>
""", unsafe_allow_html=True)

        # Determine zone labels for fidelity display
        # Colors match config/colors.py canonical values
        def get_zone_label(fidelity):
            if fidelity >= 0.70:
                return ("GREEN ZONE - Aligned", "#27ae60")
            elif fidelity >= 0.60:
                return ("YELLOW ZONE - Minor Drift", "#F4D03F")
            elif fidelity >= 0.50:
                return ("ORANGE ZONE - Drift Detected", "#e67e22")
            else:
                return ("RED ZONE - Significant Drift", "#e74c3c")

        user_zone, user_zone_color = get_zone_label(user_fidelity)
        ai_zone, ai_zone_color = get_zone_label(ai_fidelity)
        ps_zone, _ = get_zone_label(primacy_state)

        # Fidelity boxes - matching top UI style exactly
        st.markdown(f"""
<div style="display: flex; justify-content: center; gap: 10px; margin: 15px auto; max-width: 700px;">
    <div style="background-color: #1a1a1a; border: 2px solid {user_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1;">
        <div style="color: {user_color}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">User Fidelity</div>
        <div style="color: {user_color}; font-size: 42px; font-weight: bold;">{int(round(user_fidelity * 100))}%</div>
        <div style="color: {user_zone_color}; font-size: 14px; margin-top: 8px;">{user_zone}</div>
    </div>
    <div style="background-color: #1a1a1a; border: 2px solid {ai_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1;">
        <div style="color: {ai_color}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">AI Fidelity</div>
        <div style="color: {ai_color}; font-size: 42px; font-weight: bold;">{int(round(ai_fidelity * 100))}%</div>
        <div style="color: {ai_zone_color}; font-size: 14px; margin-top: 8px;">{ai_zone}</div>
    </div>
    <div style="background-color: #1a1a1a; border: 2px solid {ps_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1;">
        <div style="color: {ps_color}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">Primacy State</div>
        <div style="color: {ps_color}; font-size: 42px; font-weight: bold;">{int(round(primacy_state * 100))}%</div>
        <div style="color: {ps_color}; font-size: 14px; margin-top: 8px;">{ps_zone}</div>
    </div>
</div>
""", unsafe_allow_html=True)

        # Two PA columns wrapped in Steward-style message container
        st.markdown(f"""
<div style="background-color: #1a1a1a; padding: 15px; border-radius: 10px; margin: 15px auto; border: 2px solid {ps_color}; max-width: 700px;">
    <div style="display: flex; gap: 15px;">
        <!-- User PA -->
        <div style="flex: 1; text-align: center;">
            <div style="background: linear-gradient(135deg, {user_gradient_start} 0%, {user_gradient_end} 100%); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); color: #1a1a1a; padding: 12px; border-radius: 8px 8px 0 0; font-weight: bold; font-size: 17px;">
                User Primacy Attractor
            </div>
            <div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid {user_color}; border-top: none; border-radius: 0 0 8px 8px; padding: 18px; text-align: center; box-shadow: 0 0 15px {user_gradient_start}, 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
                <div style="color: {user_color}; font-weight: bold; margin-bottom: 12px; font-size: 20px;">Your Purpose (Moderate Drift)</div>
                <div style="color: #e0e0e0; line-height: 1.9; font-size: 15px; text-align: left;">
                    Understand TELOS without technical overwhelm<br/>
                    <span style="color: #e67e22; font-style: italic;">Asked about quantum physics instead</span>
                </div>
            </div>
        </div>
        <!-- AI PA -->
        <div style="flex: 1; text-align: center;">
            <div style="background: linear-gradient(135deg, {ai_gradient_start} 0%, {ai_gradient_end} 100%); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); color: #1a1a1a; padding: 12px; border-radius: 8px 8px 0 0; font-weight: bold; font-size: 17px;">
                Steward Attractor
            </div>
            <div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid {ai_color}; border-top: none; border-radius: 0 0 8px 8px; padding: 18px; text-align: center; box-shadow: 0 0 15px {ai_gradient_start}, 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
                <div style="color: {ai_color}; font-weight: bold; margin-bottom: 12px; font-size: 20px;">Steward's Role (Aligned)</div>
                <div style="color: #e0e0e0; line-height: 1.9; font-size: 15px; text-align: left;">
                    Align with your learning goals<br/>
                    <span style="color: #27ae60; font-style: italic;">Answered math question but tracking drift</span>
                </div>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

        # Bottom navigation row with anchor for auto-scroll
        # Add 30px spacing from Dual PA window above
        st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
        st.markdown('<div id="slide6-obs-deck-anchor"></div>', unsafe_allow_html=True)

        # Wrap buttons in 700px container to match other slides
        st.markdown("""
        <style>
        .nav-button-container {
            max-width: 700px;
            margin: 0 auto;
            padding: 0 10px;
        }
        </style>
        <div class="nav-button-container">
        """, unsafe_allow_html=True)

        # Use 3 columns for consistent width
        col_prev_bottom, col_toggle_bottom, col_next_bottom = st.columns(3)

        with col_prev_bottom:
            if st.button("⬅️ Previous", key="slide_6_obs_prev_bottom", use_container_width=True):
                st.session_state.demo_slide_index = 7  # Go back to slide 7 (How drift detection works)
                st.rerun()

        with col_toggle_bottom:
            if st.button(
                "Hide Alignment Lens",
                key="toggle_slide6_obs_deck_bottom",
                use_container_width=True,
                type="primary"
            ):
                st.session_state.slide_6_obs_deck_visible = False
                st.rerun()

        with col_next_bottom:
            if st.button("Next ➡️", key="slide_6_obs_next_bottom", use_container_width=True):
                st.session_state.demo_slide_index = 9  # Go to slide 9 (Movies - RED zone)
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # Auto-scroll to observation deck anchor when opened
        import streamlit.components.v1 as components
        components.html("""
            <script>
                setTimeout(function() {
                    var anchor = window.parent.document.getElementById('slide6-obs-deck-anchor');
                    if (anchor) {
                        anchor.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                }, 100);
            </script>
        """, height=0)

    def _render_standard_observation_deck_content(self, current_idx: int):
        """Render Alignment Lens content for standard demo slides (not slide 3 or slide 6)."""
        from telos_observatory.demo_mode.telos_framework_demo import get_demo_slides
        from telos_observatory.config.colors import with_opacity

        # Get fidelity values using the same helper as the main demo observation deck
        # This ensures consistency across all observation deck views
        user_fidelity, ai_fidelity, primacy_state, user_color, ai_color, ps_color = self._get_demo_fidelity_for_slide(current_idx)

        # SLIDE 6 OVERRIDE: Force yellow color for math question slide (0.69 = yellow zone)
        # This is a static demo slide, so we hardcode the correct yellow color
        if current_idx == 6:
            user_color = "#F4D03F"  # Canonical yellow for minor drift

        # Generate gradient rgba colors for PA headers (glow effect)
        user_gradient_start = with_opacity(user_color, 0.9)
        user_gradient_end = with_opacity(user_color, 0.85)
        ai_gradient_start = with_opacity(ai_color, 0.9)
        ai_gradient_end = with_opacity(ai_color, 0.85)

        # Animation styles
        st.markdown("""
<style>
@keyframes obsDeckFadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)

        # Determine drift status based on User Fidelity (user alignment is primary)
        if user_fidelity >= 0.70:
            drift_status = "Aligned"
            drift_color = "#27ae60"
        elif user_fidelity >= 0.60:
            drift_status = "Minor Drift"
            drift_color = "#F4D03F"
        elif user_fidelity >= 0.50:
            drift_status = "Moderate Drift"
            drift_color = "#e67e22"
        else:
            drift_status = "Severe Drift"
            drift_color = "#e74c3c"

        # Alignment Lens header - compact horizontal bar format
        st.markdown(f"""
<div style="max-width: 700px; margin: 20px auto; opacity: 0; animation: obsDeckFadeIn 1.0s ease-in-out forwards;">
    <div style="background-color: #1a1a1a; border: 2px solid {user_color}; border-radius: 8px; padding: 12px 20px; box-shadow: 0 0 15px rgba(255, 215, 0, 0.2); display: flex; justify-content: space-between; align-items: center;">
        <span style="color: {user_color}; font-size: 18px; font-weight: bold;">Alignment Lens</span>
        <span style="background-color: #2d2d2d; border: 1px solid {drift_color}; border-radius: 15px; padding: 6px 16px; color: {drift_color}; font-weight: bold; font-size: 13px;">{drift_status}</span>
    </div>
</div>
""", unsafe_allow_html=True)

        # Determine zone labels for fidelity display
        # Colors match config/colors.py canonical values
        def get_zone_label(fidelity):
            if fidelity >= 0.70:
                return ("GREEN ZONE - Aligned", "#27ae60")
            elif fidelity >= 0.60:
                return ("YELLOW ZONE - Minor Drift", "#F4D03F")
            elif fidelity >= 0.50:
                return ("ORANGE ZONE - Drift Detected", "#e67e22")
            else:
                return ("RED ZONE - Significant Drift", "#e74c3c")

        user_zone, user_zone_color = get_zone_label(user_fidelity)
        ai_zone, ai_zone_color = get_zone_label(ai_fidelity)
        ps_zone, _ = get_zone_label(primacy_state)

        # Fidelity boxes - matching top UI style exactly
        st.markdown(f"""
<div style="display: flex; justify-content: center; gap: 10px; margin: 15px auto; max-width: 700px;">
    <div style="background-color: #1a1a1a; border: 2px solid {user_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1;">
        <div style="color: {user_color}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">User Fidelity</div>
        <div style="color: {user_color}; font-size: 42px; font-weight: bold;">{int(round(user_fidelity * 100))}%</div>
        <div style="color: {user_zone_color}; font-size: 14px; margin-top: 8px;">{user_zone}</div>
    </div>
    <div style="background-color: #1a1a1a; border: 2px solid {ai_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1;">
        <div style="color: {ai_color}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">AI Fidelity</div>
        <div style="color: {ai_color}; font-size: 42px; font-weight: bold;">{int(round(ai_fidelity * 100))}%</div>
        <div style="color: {ai_zone_color}; font-size: 14px; margin-top: 8px;">{ai_zone}</div>
    </div>
    <div style="background-color: #1a1a1a; border: 2px solid {ps_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1;">
        <div style="color: {ps_color}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">Primacy State</div>
        <div style="color: {ps_color}; font-size: 42px; font-weight: bold;">{int(round(primacy_state * 100))}%</div>
        <div style="color: {ps_color}; font-size: 14px; margin-top: 8px;">{ps_zone}</div>
    </div>
</div>
""", unsafe_allow_html=True)

        # Two PA columns wrapped in Steward-style message container with dynamic glow effect
        st.markdown(f"""
<div style="background-color: #1a1a1a; padding: 15px; border-radius: 10px; margin: 15px auto; border: 2px solid {ps_color}; max-width: 700px;">
    <div style="display: flex; gap: 15px;">
        <!-- User PA -->
        <div style="flex: 1; text-align: center;">
            <div style="background: linear-gradient(135deg, {user_gradient_start} 0%, {user_gradient_end} 100%); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); color: #1a1a1a; padding: 12px; border-radius: 8px 8px 0 0; font-weight: bold; font-size: 17px;">
                User Primacy Attractor
            </div>
            <div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid {user_color}; border-top: none; border-radius: 0 0 8px 8px; padding: 18px; text-align: center; box-shadow: 0 0 15px {user_gradient_start}, 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
                <div style="color: {user_color}; font-weight: bold; margin-bottom: 12px; font-size: 20px;">Your Purpose</div>
                <div style="color: #e0e0e0; line-height: 1.9; font-size: 15px; text-align: left;">
                    &bull; Understand TELOS without technical overwhelm<br/>
                    &bull; Learn how purpose alignment keeps AI focused<br/>
                    &bull; See real examples of governance in action
                </div>
            </div>
        </div>
        <!-- AI PA -->
        <div style="flex: 1; text-align: center;">
            <div style="background: linear-gradient(135deg, {ai_gradient_start} 0%, {ai_gradient_end} 100%); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); color: #1a1a1a; padding: 12px; border-radius: 8px 8px 0 0; font-weight: bold; font-size: 17px;">
                Steward Attractor
            </div>
            <div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid {ai_color}; border-top: none; border-radius: 0 0 8px 8px; padding: 18px; text-align: center; box-shadow: 0 0 15px {ai_gradient_start}, 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
                <div style="color: {ai_color}; font-weight: bold; margin-bottom: 12px; font-size: 20px;">Steward's Role</div>
                <div style="color: #e0e0e0; line-height: 1.9; font-size: 15px; text-align: left;">
                    &bull; Align with your learning goals<br/>
                    &bull; Stay focused on what you want to know<br/>
                    &bull; Support your PA while maintaining alignment
                </div>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

        # Bottom navigation row with anchor for auto-scroll
        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)
        st.markdown(f'<div id="standard-obs-deck-anchor-{current_idx}"></div>', unsafe_allow_html=True)

        # CSS for button container and fidelity-colored border on primary button
        # Use .nav-button-container to ONLY target navigation buttons, NOT tab buttons
        st.markdown(f"""
        <style>
        .nav-button-container {{
            max-width: 700px;
            margin: 0 auto;
            padding: 0 10px;
        }}
        /* Style Hide Alignment Lens button ONLY inside nav-button-container */
        .nav-button-container div[data-testid="column"]:nth-child(2) button[data-testid="baseButton-primary"] {{
            border: 2px solid {user_color} !important;
            box-shadow: 0 0 5px rgba(39, 174, 96, 0.3) !important;
        }}
        </style>
        <div class="nav-button-container">
        """, unsafe_allow_html=True)

        col_prev_bottom, col_toggle_bottom, col_next_bottom = st.columns(3)

        with col_prev_bottom:
            if current_idx > 1:
                if st.button("Previous", key=f"std_obs_prev_bottom_{current_idx}", use_container_width=True):
                    st.session_state.demo_slide_index = current_idx - 1
                    st.rerun()

        with col_toggle_bottom:
            if st.button(
                "Hide Alignment Lens",
                key=f"toggle_std_obs_deck_bottom_{current_idx}",
                use_container_width=True,
                type="primary"
            ):
                st.session_state.demo_std_obs_deck_visible = False
                st.rerun()

        with col_next_bottom:
            from telos_observatory.demo_mode.telos_framework_demo import get_demo_slides
            slides = get_demo_slides()
            # Use <= to include the last Q&A slide (navigates to completion)
            if current_idx <= len(slides):
                if st.button("Next", key=f"std_obs_next_bottom_{current_idx}", use_container_width=True):
                    st.session_state.demo_slide_index = current_idx + 1
                    st.rerun()

        # Close the nav-button-container div
        st.markdown("</div>", unsafe_allow_html=True)

        # Auto-scroll to observation deck anchor when opened
        import streamlit.components.v1 as components
        components.html(f"""
            <script>
                setTimeout(function() {{
                    var anchor = window.parent.document.getElementById('standard-obs-deck-anchor-{current_idx}');
                    if (anchor) {{
                        anchor.scrollIntoView({{
                            behavior: 'smooth',
                            block: 'start'
                        }});
                    }}
                }}, 100);
            </script>
        """, height=0)

    def _get_demo_fidelity_for_slide(self, slide_idx: int) -> tuple:
        """
        Get fidelity values for a specific demo slide.
        Returns (user_fidelity, ai_fidelity, primacy_state, user_color, ai_color, ps_color)
        """
        from telos_observatory.config.colors import get_fidelity_color

        # Same mapping as _render_demo_slide_with_typewriter (MUST MATCH!)
        # 12-SLIDE STRUCTURE:
        # Slides 1-2: No fidelity display (PA not established)
        # Slides 3-5: Perfect alignment (1.00/1.00)
        # Slide 6: Math question - YELLOW ZONE (0.69/0.82)
        # Slide 7: How drift works - back to GREEN (0.88/0.90)
        # Slide 8: Movies - RED ZONE (0.42/0.85)
        # Slide 9+: Recovery back to green
        if slide_idx == 1:  # What is TELOS - no fidelity display
            user_fidelity = 1.000
            ai_fidelity = 1.000
        elif slide_idx == 2:  # Differentiator - no fidelity display
            user_fidelity = 1.000
            ai_fidelity = 1.000
        elif slide_idx == 3:  # PA Established
            user_fidelity = 1.000
            ai_fidelity = 1.000
        elif slide_idx == 4:  # Understanding Alignment Lens
            user_fidelity = 1.000
            ai_fidelity = 1.000
        elif slide_idx == 5:  # Why both at 1.00 - still perfect
            user_fidelity = 1.000
            ai_fidelity = 1.000
        elif slide_idx == 6:  # Math question - YELLOW ZONE
            user_fidelity = 0.69
            ai_fidelity = 0.82
        elif slide_idx == 7:  # How drift works - back to GREEN
            user_fidelity = 0.88
            ai_fidelity = 0.90
        elif slide_idx == 8:  # Movies - RED ZONE
            user_fidelity = 0.42
            ai_fidelity = 0.85
        elif slide_idx == 9:  # Wrap-up - recovery to green
            user_fidelity = 0.88
            ai_fidelity = 0.90
        elif slide_idx == 10:  # Beyond individual
            user_fidelity = 0.92
            ai_fidelity = 0.95
        elif slide_idx == 11:  # Healthcare
            user_fidelity = 0.88
            ai_fidelity = 0.90
        elif slide_idx == 12:  # Financial services
            user_fidelity = 0.88
            ai_fidelity = 0.90
        else:
            user_fidelity = 0.88
            ai_fidelity = 0.90

        # Calculate Primacy State using harmonic mean
        epsilon = 1e-10
        if user_fidelity + ai_fidelity > epsilon:
            primacy_state = (2 * user_fidelity * ai_fidelity) / (user_fidelity + ai_fidelity + epsilon)
        else:
            primacy_state = 0.0

        # Get colors
        user_color = get_fidelity_color(user_fidelity)
        ai_color = get_fidelity_color(ai_fidelity)
        ps_color = get_fidelity_color(primacy_state)

        return user_fidelity, ai_fidelity, primacy_state, user_color, ai_color, ps_color

    def _render_demo_observation_deck(self, turn_num: int):
        """Render toggleable Alignment Lens for demo mode - matches standard observation deck format."""

        # Initialize toggle state - default to hidden so users must click to reveal
        if 'demo_obs_deck_visible' not in st.session_state:
            st.session_state.demo_obs_deck_visible = False

        # Add spacing between content and navigation buttons (30px matches other slides)
        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        # Only render top navigation buttons when observation deck is NOT visible
        # When visible, content renders with navigation at bottom only (matches standard format)
        if not st.session_state.demo_obs_deck_visible:
            # Slide 2 has perfect fidelity (1.00) - use green color for Show Alignment Lens button
            from telos_observatory.config.colors import get_fidelity_color
            slide_2_fidelity_color = get_fidelity_color(1.000)  # Green for perfect alignment

            # Wrap buttons in 700px container to match other slides
            # CSS injection for green Alignment Lens button (Slide 2 has 1.00 fidelity)
            # Use .nav-button-container to ONLY target navigation buttons, NOT tab buttons
            st.markdown(f"""
            <style>
            .nav-button-container {{
                max-width: 700px;
                margin: 0 auto;
                padding: 0 10px;
            }}
            /* Style Show Alignment Lens button ONLY inside nav-button-container */
            .nav-button-container div[data-testid="stHorizontalBlock"] > div:nth-child(2) button[kind="primary"],
            .nav-button-container div[data-testid="stHorizontalBlock"] > div:nth-child(2) button[kind="secondary"] {{
                background-color: #2d2d2d !important;
                border: 2px solid {slide_2_fidelity_color} !important;
                color: #e0e0e0 !important;
            }}
            .nav-button-container div[data-testid="stHorizontalBlock"] > div:nth-child(2) button[kind="primary"]:hover,
            .nav-button-container div[data-testid="stHorizontalBlock"] > div:nth-child(2) button[kind="secondary"]:hover {{
                background-color: #3d3d3d !important;
                border: 2px solid {slide_2_fidelity_color} !important;
            }}
            </style>
            <div class="nav-button-container">
            """, unsafe_allow_html=True)

            # Use 3 columns for consistent width
            col_prev, col_toggle, col_next = st.columns(3)

            with col_prev:
                if st.button(
                    "Previous",
                    key="obs_deck_prev_3",
                    use_container_width=True
                ):
                    st.session_state.demo_obs_deck_visible = False
                    st.session_state.demo_slide_index = 1
                    st.rerun()

            with col_toggle:
                if st.button(
                    "Show Alignment Lens",
                    key="toggle_demo_obs_deck",
                    use_container_width=True,
                    type="primary"
                ):
                    st.session_state.demo_obs_deck_visible = True
                    st.rerun()

            with col_next:
                if st.button(
                    "Next",
                    key="obs_deck_next_3",
                    use_container_width=True
                ):
                    st.session_state.demo_obs_deck_visible = False
                    st.session_state.demo_slide_index = 3
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)
            return  # Don't render content when hidden

        # Alignment Lens content (only when visible) - matches _render_standard_observation_deck_content
        # Auto-scroll to observation deck content
        st.markdown("""
<script>
    setTimeout(function() {
        window.scrollTo({
            top: document.body.scrollHeight,
            behavior: 'smooth'
        });
    }, 100);
</script>
""", unsafe_allow_html=True)

        # Get dynamic fidelity values for slide 2
        current_slide = st.session_state.get('demo_slide_index', 2)
        user_fidelity, ai_fidelity, primacy_state, user_color, ai_color, ps_color = self._get_demo_fidelity_for_slide(current_slide)

        # Generate gradient rgba colors for PA headers (glow effect)
        from telos_observatory.config.colors import with_opacity
        user_gradient_start = with_opacity(user_color, 0.9)
        user_gradient_end = with_opacity(user_color, 0.85)
        ai_gradient_start = with_opacity(ai_color, 0.9)
        ai_gradient_end = with_opacity(ai_color, 0.85)

        # Animation styles
        st.markdown("""
<style>
@keyframes obsDeckFadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)

        # Determine drift status based on User Fidelity (user alignment is primary)
        if user_fidelity >= 0.70:
            drift_status = "Aligned"
            drift_color = "#27ae60"
        elif user_fidelity >= 0.60:
            drift_status = "Minor Drift"
            drift_color = "#F4D03F"
        elif user_fidelity >= 0.50:
            drift_status = "Moderate Drift"
            drift_color = "#e67e22"
        else:
            drift_status = "Severe Drift"
            drift_color = "#e74c3c"

        # Alignment Lens header - compact horizontal bar format
        st.markdown(f"""
<div style="max-width: 700px; margin: 20px auto; opacity: 0; animation: obsDeckFadeIn 1.0s ease-in-out forwards;">
    <div style="background-color: #1a1a1a; border: 2px solid {user_color}; border-radius: 8px; padding: 12px 20px; box-shadow: 0 0 15px rgba(255, 215, 0, 0.2); display: flex; justify-content: space-between; align-items: center;">
        <span style="color: {user_color}; font-size: 18px; font-weight: bold;">Alignment Lens</span>
        <span style="background-color: #2d2d2d; border: 1px solid {drift_color}; border-radius: 15px; padding: 6px 16px; color: {drift_color}; font-weight: bold; font-size: 13px;">{drift_status}</span>
    </div>
</div>
""", unsafe_allow_html=True)

        # Determine zone labels for fidelity display
        # Colors match config/colors.py canonical values
        def get_zone_label(fidelity):
            if fidelity >= 0.70:
                return ("GREEN ZONE - Aligned", "#27ae60")
            elif fidelity >= 0.60:
                return ("YELLOW ZONE - Minor Drift", "#F4D03F")
            elif fidelity >= 0.50:
                return ("ORANGE ZONE - Drift Detected", "#e67e22")
            else:
                return ("RED ZONE - Significant Drift", "#e74c3c")

        user_zone, user_zone_color = get_zone_label(user_fidelity)
        ai_zone, ai_zone_color = get_zone_label(ai_fidelity)
        ps_zone, _ = get_zone_label(primacy_state)

        # Fidelity boxes - matching standard format exactly
        st.markdown(f"""
<div style="display: flex; justify-content: center; gap: 10px; margin: 15px auto; max-width: 700px;">
    <div style="background-color: #1a1a1a; border: 2px solid {user_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1;">
        <div style="color: {user_color}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">User Fidelity</div>
        <div style="color: {user_color}; font-size: 42px; font-weight: bold;">{int(round(user_fidelity * 100))}%</div>
        <div style="color: {user_zone_color}; font-size: 14px; margin-top: 8px;">{user_zone}</div>
    </div>
    <div style="background-color: #1a1a1a; border: 2px solid {ai_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1;">
        <div style="color: {ai_color}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">AI Fidelity</div>
        <div style="color: {ai_color}; font-size: 42px; font-weight: bold;">{int(round(ai_fidelity * 100))}%</div>
        <div style="color: {ai_zone_color}; font-size: 14px; margin-top: 8px;">{ai_zone}</div>
    </div>
    <div style="background-color: #1a1a1a; border: 2px solid {ps_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1;">
        <div style="color: {ps_color}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">Primacy State</div>
        <div style="color: {ps_color}; font-size: 42px; font-weight: bold;">{int(round(primacy_state * 100))}%</div>
        <div style="color: {ps_color}; font-size: 14px; margin-top: 8px;">{ps_zone}</div>
    </div>
</div>
""", unsafe_allow_html=True)

        # Two PA columns wrapped in Steward-style message container with dynamic glow effect
        st.markdown(f"""
<div style="background-color: #1a1a1a; padding: 15px; border-radius: 10px; margin: 15px auto; border: 2px solid {ps_color}; max-width: 700px;">
    <div style="display: flex; gap: 15px;">
        <!-- User PA -->
        <div style="flex: 1; text-align: center;">
            <div style="background: linear-gradient(135deg, {user_gradient_start} 0%, {user_gradient_end} 100%); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); color: #1a1a1a; padding: 12px; border-radius: 8px 8px 0 0; font-weight: bold; font-size: 17px;">
                User Primacy Attractor
            </div>
            <div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid {user_color}; border-top: none; border-radius: 0 0 8px 8px; padding: 18px; text-align: center; box-shadow: 0 0 15px {user_gradient_start}, 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
                <div style="color: {user_color}; font-weight: bold; margin-bottom: 12px; font-size: 20px;">Your Purpose</div>
                <div style="color: #e0e0e0; line-height: 1.9; font-size: 15px; text-align: left;">
                    &bull; Understand TELOS without technical overwhelm<br/>
                    &bull; Learn how purpose alignment keeps AI focused<br/>
                    &bull; See real examples of governance in action
                </div>
            </div>
        </div>
        <!-- AI PA -->
        <div style="flex: 1; text-align: center;">
            <div style="background: linear-gradient(135deg, {ai_gradient_start} 0%, {ai_gradient_end} 100%); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); color: #1a1a1a; padding: 12px; border-radius: 8px 8px 0 0; font-weight: bold; font-size: 17px;">
                Steward Attractor
            </div>
            <div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 2px solid {ai_color}; border-top: none; border-radius: 0 0 8px 8px; padding: 18px; text-align: center; box-shadow: 0 0 15px {ai_gradient_start}, 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
                <div style="color: {ai_color}; font-weight: bold; margin-bottom: 12px; font-size: 20px;">Steward's Role</div>
                <div style="color: #e0e0e0; line-height: 1.9; font-size: 15px; text-align: left;">
                    &bull; Align with your learning goals<br/>
                    &bull; Stay focused on what you want to know<br/>
                    &bull; Support your PA while maintaining alignment
                </div>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

        # Bottom navigation row with anchor for auto-scroll (matches standard format)
        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)
        st.markdown('<div id="slide2-obs-deck-anchor"></div>', unsafe_allow_html=True)

        # CSS for button container - Slide 2 has 1.00 fidelity (green)
        # Use .nav-button-container to ONLY target navigation buttons, NOT tab buttons
        from telos_observatory.config.colors import get_fidelity_color
        slide_2_fidelity_color = get_fidelity_color(1.000)  # Green for perfect alignment

        st.markdown(f"""
        <style>
        .nav-button-container {{
            max-width: 700px;
            margin: 0 auto;
            padding: 0 10px;
        }}
        /* Hide Alignment Lens button ONLY inside nav-button-container - green fidelity border for Slide 2 */
        .nav-button-container div[data-testid="stHorizontalBlock"] > div:nth-child(2) button[kind="primary"],
        .nav-button-container div[data-testid="stHorizontalBlock"] > div:nth-child(2) button[kind="secondary"] {{
            background-color: #2d2d2d !important;
            border: 2px solid {slide_2_fidelity_color} !important;
            color: #e0e0e0 !important;
        }}
        .nav-button-container div[data-testid="stHorizontalBlock"] > div:nth-child(2) button[kind="primary"]:hover,
        .nav-button-container div[data-testid="stHorizontalBlock"] > div:nth-child(2) button[kind="secondary"]:hover {{
            background-color: #3d3d3d !important;
            border: 2px solid {slide_2_fidelity_color} !important;
        }}
        </style>
        <div class="nav-button-container">
        """, unsafe_allow_html=True)

        col_prev_bottom, col_toggle_bottom, col_next_bottom = st.columns(3)

        with col_prev_bottom:
            if st.button("Previous", key="slide2_obs_prev_bottom", use_container_width=True):
                st.session_state.demo_obs_deck_visible = False
                st.session_state.demo_slide_index = 1
                st.rerun()

        with col_toggle_bottom:
            if st.button(
                "Hide Alignment Lens",
                key="toggle_slide2_obs_deck_bottom",
                use_container_width=True,
                type="primary"
            ):
                st.session_state.demo_obs_deck_visible = False
                st.rerun()

        with col_next_bottom:
            if st.button("Next", key="slide2_obs_next_bottom", use_container_width=True):
                st.session_state.demo_obs_deck_visible = False
                st.session_state.demo_slide_index = 3
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # Auto-scroll to observation deck anchor when opened
        import streamlit.components.v1 as components
        components.html(f"""
            <script>
                setTimeout(function() {{
                    var anchor = window.parent.document.getElementById('slide2-obs-deck-anchor');
                    if (anchor) {{
                        anchor.scrollIntoView({{
                            behavior: 'smooth',
                            block: 'start'
                        }});
                    }}
                }}, 100);
            </script>
        """, height=0)

    def _render_beta_intro(self):
        """Render beta introduction slides explaining the beta experience."""
        # Initialize beta intro state
        if 'beta_intro_slide' not in st.session_state:
            st.session_state.beta_intro_slide = 0

        current_slide = st.session_state.beta_intro_slide
        max_slide = 3  # 0-3 slides (0=welcome, 1=what you'll experience, 2=privacy, 3=ready)

        # Add keyboard navigation for beta intro slides
        import streamlit.components.v1 as components

        components.html(f"""
        <script>
        // Beta intro keyboard navigation
        (function() {{
            const currentSlide = {current_slide};
            const maxSlide = {max_slide};

            // Remove old listener if exists
            if (window.betaIntroKeyListener) {{
                document.removeEventListener('keydown', window.betaIntroKeyListener);
            }}

            // Create new listener
            window.betaIntroKeyListener = function(event) {{
                // Ignore if modifier keys are pressed
                if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) {{
                    return;
                }}

                if (event.key === 'ArrowLeft' && currentSlide > 0) {{
                    event.preventDefault();
                    // Find Previous button in parent window
                    const parent = window.parent;
                    if (parent && parent.document) {{
                        const buttons = parent.document.querySelectorAll('button');
                        for (let btn of buttons) {{
                            if (btn.textContent.includes('Previous')) {{
                                btn.click();
                                break;
                            }}
                        }}
                    }}
                }} else if (event.key === 'ArrowRight' && currentSlide < maxSlide) {{
                    event.preventDefault();
                    // Find Next/Continue/Start button in parent window
                    const parent = window.parent;
                    if (parent && parent.document) {{
                        const buttons = parent.document.querySelectorAll('button');
                        for (let btn of buttons) {{
                            if (btn.textContent.includes('Next') ||
                                btn.textContent.includes('Continue') ||
                                btn.textContent.includes('Start Beta Testing')) {{
                                btn.click();
                                break;
                            }}
                        }}
                    }}
                }}
            }};

            // Attach listener to both current window and parent
            document.addEventListener('keydown', window.betaIntroKeyListener);
            if (window.parent && window.parent.document) {{
                window.parent.document.addEventListener('keydown', window.betaIntroKeyListener);
            }}
        }})();
        </script>
        """, height=0)

        # Slide 0: Welcome to Beta Testing
        if current_slide == 0:
            st.markdown("""
<div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border: 2px solid #F4D03F; border-radius: 15px; padding: 30px; margin: 20px 0; text-align: center; box-shadow: 0 0 8px rgba(255, 215, 0, 0.4);">
    <h1 style="color: #F4D03F; font-size: 32px; margin-bottom: 20px;">Welcome to TELOS Beta Testing</h1>
    <p style="color: #e0e0e0; font-size: 20px; line-height: 1.8; margin-bottom: 20px;">
        You're about to experience TELOS in action. Your participation helps us refine AI governance for everyone.
    </p>
    <p style="color: #a8a8a8; font-size: 20px; font-style: italic;">
        Let's walk through what to expect...
    </p>
</div>
""", unsafe_allow_html=True)

            if st.button("Continue", key="beta_intro_0", use_container_width=True):
                st.session_state.beta_intro_slide = 1
                st.rerun()
            return

        # Slide 1: What You'll Experience
        if current_slide == 1:
            st.markdown("""
<div style="background: linear-gradient(135deg, rgba(255, 215, 0, 0.05) 0%, rgba(255, 215, 0, 0.1) 100%); border: 2px solid #F4D03F; padding: 25px; margin: 15px 0; border-radius: 10px; font-size: 18px; line-height: 1.8; color: #e0e0e0;">
    <div style="color: #F4D03F; font-size: 24px; font-weight: bold; margin-bottom: 20px;">What You'll Experience</div>
    <div style="margin-bottom: 15px;"><strong style="color: #F4D03F;">Turns 1-10:</strong> You'll interact with the native LLM while TELOS learns your purpose, scope, and boundaries. This establishes your Primacy Attractor (PA).</div>
    <div style="margin-bottom: 15px;"><strong style="color: #F4D03F;">PA+:</strong> TELOS activates! You'll see:
        <div style="margin-left: 25px; margin-top: 10px;">
            • Fidelity scores tracking alignment<br>
            • Your PA in the Alignment Lens<br>
            • TELOSCOPE: Alignment Lens for real-time drift monitoring<br>
            • Turn-by-turn metrics<br>
            • Real-time governance in action
        </div>
    </div>
    <div style="margin-top: 20px; padding: 15px; background-color: rgba(255, 215, 0, 0.1); border-radius: 8px;">
        <strong style="color: #F4D03F;">Key Point:</strong> For now, the PA forms progressively through your conversation. This lets you see how TELOS learns from your behavior.
    </div>
</div>
""", unsafe_allow_html=True)

            col_prev, col_next = st.columns(2)
            with col_prev:
                if st.button("⬅️ Previous", key="beta_intro_1_prev", use_container_width=True):
                    st.session_state.beta_intro_slide = 0
                    st.rerun()
            with col_next:
                if st.button("Next ➡️", key="beta_intro_1_next", use_container_width=True):
                    st.session_state.beta_intro_slide = 2
                    st.rerun()
            return

        # Slide 2: Data Privacy & Usage
        if current_slide == 2:
            st.markdown("""
<div style="background: linear-gradient(135deg, rgba(255, 215, 0, 0.05) 0%, rgba(255, 215, 0, 0.1) 100%); border: 2px solid #F4D03F; padding: 25px; margin: 15px 0; border-radius: 10px; font-size: 18px; line-height: 1.8; color: #e0e0e0;">
    <div style="color: #F4D03F; font-size: 24px; font-weight: bold; margin-bottom: 20px;">Your Data & Privacy</div>
    <div style="margin-bottom: 15px;"><strong style="color: #F4D03F;">What we collect:</strong> Mathematical metrics in the form of deltas (fidelity scores, embedding distances, intervention counts)</div>
    <div style="margin-bottom: 15px;"><strong style="color: #F4D03F;">What we DON'T collect:</strong> Your conversation content, messages, or responses</div>
    <div style="margin-top: 20px; padding: 15px; background-color: rgba(255, 215, 0, 0.1); border-radius: 8px;">
        <strong style="color: #F4D03F;">Data Deprecation:</strong> All beta session information will be deprecated once beta testing is completed. We will never sell your data to third parties.
    </div>
</div>
""", unsafe_allow_html=True)

            col_prev, col_next = st.columns(2)
            with col_prev:
                if st.button("⬅️ Previous", key="beta_intro_2_prev", use_container_width=True):
                    st.session_state.beta_intro_slide = 1
                    st.rerun()
            with col_next:
                if st.button("Next ➡️", key="beta_intro_2_next", use_container_width=True):
                    st.session_state.beta_intro_slide = 3
                    st.rerun()
            return

        # Slide 3: Future Vision & User Control
        if current_slide == 3:
            st.markdown("""
<div style="background: linear-gradient(135deg, rgba(255, 215, 0, 0.05) 0%, rgba(255, 215, 0, 0.1) 100%); border: 2px solid #F4D03F; padding: 25px; margin: 15px 0; border-radius: 10px; font-size: 18px; line-height: 1.8; color: #e0e0e0;">
    <div style="color: #F4D03F; font-size: 24px; font-weight: bold; margin-bottom: 20px;">How TELOS Beta Works</div>
    <div style="margin-bottom: 15px;">Your Beta session gives you <strong style="color: #F4D03F;">10 turns</strong> to experience live TELOS governance:</div>
    <div style="margin-left: 25px; margin-bottom: 15px;">
        • <strong>Choose Your PA:</strong> Select a template or define your own purpose<br>
        • <strong>Live Monitoring:</strong> Watch real-time fidelity tracking in the Alignment Lens<br>
        • <strong>Steward Guidance:</strong> See how TELOS intervenes when drift is detected
    </div>
    <div style="margin-top: 20px; padding: 15px; background-color: rgba(255, 215, 0, 0.1); border-radius: 8px;">
        <strong style="color: #F4D03F;">Research Note:</strong> Your participation helps us refine AI governance for regulated domains like healthcare and enterprise.
    </div>
    <div style="margin-top: 20px; text-align: center; font-size: 20px; color: #F4D03F;">
        Ready to start your beta session?
    </div>
</div>
""", unsafe_allow_html=True)

            col_prev, col_next = st.columns(2)
            with col_prev:
                if st.button("⬅️ Previous", key="beta_intro_3_prev", use_container_width=True):
                    st.session_state.beta_intro_slide = 2
                    st.rerun()
            with col_next:
                if st.button("Start Beta Testing ➡️", key="beta_intro_complete_btn", use_container_width=True):
                    st.session_state.beta_intro_complete = True
                    st.session_state.beta_start_time = datetime.now().isoformat()
                    # Ensure demo_mode is OFF when entering beta conversation
                    st.session_state.telos_demo_mode = False
                    # Balloons removed for professional appearance
                    # st.balloons()
                    st.rerun()
            return

    def _render_intro_example(self):
        """Render a simple intro example that dismisses when user starts typing."""
        from telos_observatory.utils.intro_messages import get_random_intro_pair

        # Get random intro pair (cached for session)
        if 'intro_pair' not in st.session_state:
            st.session_state.intro_pair = get_random_intro_pair()

        user_msg, steward_msg = st.session_state.intro_pair

        # USER MESSAGE - Match exact structure of _render_user_message
        # Column structure: 0.5 (Example badge) + 9.5 (content with 8.5:1.5 split)
        col_badge, col_content = st.columns([0.5, 9.5])

        with col_badge:
            # Example badge (replaces Turn badge)
            st.markdown("""
<div style="display: flex; align-items: flex-start; height: 100%;">
    <span style="background: linear-gradient(90deg, #F4D03F 0%, #e67e22 100%); color: #000; padding: 4px 10px; border-radius: 5px; font-size: 19px; font-weight: bold; display: inline-block;">Example</span>
</div>
""", unsafe_allow_html=True)

        with col_content:
            col_msg, col_dismiss = st.columns([8.5, 1.5])

            with col_msg:
                # User message with exact same styling
                st.markdown(f"""
<div style="background-color: #1a1a1a; padding: 15px; border-radius: 10px; margin: 0; border: 1px solid #F4D03F;">
    <div style="color: #a8a8a8; font-size: 19px; margin-bottom: 5px;">
        <strong style="color: #F4D03F;">User</strong>
    </div>
    <div style="color: #fff; font-size: 19px; white-space: pre-wrap;">
        {html.escape(user_msg)}
    </div>
</div>
""", unsafe_allow_html=True)

            with col_dismiss:
                # Dismiss button in same position as scroll button
                if st.button("✕", key="dismiss_intro", use_container_width=True, help="Dismiss example"):
                    st.session_state.show_intro = False
                    st.rerun()

        # STEWARD MESSAGE - Match exact structure of _render_assistant_message
        # Column structure: 0.5 (spacer) + 9.5 (content with 8.5:1.5 split)
        col_spacer, col_content2 = st.columns([0.5, 9.5])

        with col_spacer:
            st.markdown("")

        with col_content2:
            col_msg2, col_empty = st.columns([8.5, 1.5])

            with col_msg2:
                # Steward response with exact same styling and spacing
                st.markdown(f"""
<div style="background-color: #1a1a1a; padding: 15px; border-radius: 10px; margin-top: 15px; margin-bottom: 0; border: 1px solid #F4D03F;">
    <div style="color: #a8a8a8; font-size: 19px; margin-bottom: 5px;">
        <strong style="color: #F4D03F;">TELOS</strong>
    </div>
    <div style="color: #fff; font-size: 19px; white-space: pre-wrap;">
        {html.escape(steward_msg)}
    </div>
</div>
""", unsafe_allow_html=True)

            with col_empty:
                st.markdown("")

    def _render_current_turn_only(self, current_turn_idx: int, all_turns: list):
        """Render only the current turn with Turn label."""
        if current_turn_idx >= len(all_turns):
            return

        turn_data = all_turns[current_turn_idx]
        turn_number = current_turn_idx + 1

        # Add spacing before turn
        st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)

        # Render user message
        self._render_user_message(turn_data.get('user_input', ''), turn_number, turn_data)

        # Check if this turn needs streaming
        if turn_data.get('is_streaming', False) and not turn_data.get('response'):
            # First, show the animation
            self._render_assistant_message('', turn_number, is_loading=True)
            # Then trigger streaming on next render
            import time
            time.sleep(0.1)  # Small delay to show animation
            self._process_streaming_turn(turn_data.get('user_input', ''), current_turn_idx)
        else:
            # Check for comparison mode (head-to-head A/B testing)
            if turn_data.get('comparison_mode', False):
                # Render side-by-side comparison
                self._render_comparison_responses(turn_data, turn_number)
            else:
                # Normal rendering (either completed or already has response)
                self._render_assistant_message(
                    turn_data.get('response', ''),
                    turn_number,
                    is_loading=turn_data.get('is_loading', False)
                )

        # Show phase transition at turn 11 (PA established → Beta testing active)
        self._show_beta_phase_transition(turn_number)

        # Render interaction buttons (Ask Steward why, Shift Focus) - NOT feedback thumbs
        self._render_beta_interaction_buttons(turn_number)

    def _render_comparison_responses(self, turn_data: dict, turn_number: int):
        """Render side-by-side comparison for head-to-head A/B testing turns."""
        import html
        from telos_observatory.config.colors import GOLD

        response_a = turn_data.get('response_a', '')  # TELOS response
        response_b = turn_data.get('response_b', '')  # Native response

        # Convert markdown to HTML for proper rendering (not just escaping)
        safe_response_a = self._markdown_to_html(response_a) if response_a else 'Response not available'
        safe_response_b = self._markdown_to_html(response_b) if response_b else 'Response not available'

        # Check if preference was already made for this turn
        existing_preference = st.session_state.get('comparison_preferences', {}).get(turn_number)
        choice_made = existing_preference is not None

        # Header - different if choice already made
        if choice_made:
            choice_label = "Response A" if existing_preference == 'a' else "Response B"
            st.markdown(f"""
            <div style="background-color: #2d2d2d; border: 2px solid #27ae60; border-radius: 10px; padding: 15px; margin: 15px 0; text-align: center;">
                <div style="color: #27ae60; font-size: 18px; font-weight: bold; margin-bottom: 10px;">
                    ✓ You chose {choice_label}
                </div>
                <div style="color: #e0e0e0; font-size: 14px;">
                    Your preference has been recorded. Thank you for your feedback!
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background-color: #2d2d2d; border: 2px solid {GOLD}; border-radius: 10px; padding: 15px; margin: 15px 0; text-align: center;">
                <div style="color: {GOLD}; font-size: 18px; font-weight: bold; margin-bottom: 10px;">
                    Compare Responses - Which do you prefer?
                </div>
                <div style="color: #e0e0e0; font-size: 14px;">
                    Both responses are generated for your question. Choose which one better serves your purpose.
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Side-by-side columns
        col_a, col_b = st.columns(2)

        # Determine border colors based on choice
        # Both start gray (neutral) until user makes a selection
        # Chosen response turns green, non-chosen stays dimmed
        if choice_made:
            border_a = "#27ae60" if existing_preference == 'a' else "#555"  # Green if chosen, dim if not
            border_b = "#27ae60" if existing_preference == 'b' else "#555"  # Green if chosen, dim if not
            label_color_a = "#27ae60" if existing_preference == 'a' else "#555"
            label_color_b = "#27ae60" if existing_preference == 'b' else "#555"
        else:
            # No choice made yet - both are neutral gray
            border_a = "#888"  # Neutral gray
            border_b = "#888"  # Neutral gray
            label_color_a = "#888"
            label_color_b = "#888"

        with col_a:
            chosen_badge_a = " ✓ CHOSEN" if existing_preference == 'a' else ""
            st.markdown(f"""
            <div style="background-color: #1a1a1a; border: 2px solid {border_a}; border-radius: 10px; padding: 15px; min-height: 200px;">
                <div style="color: {label_color_a}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">
                    Response A{chosen_badge_a}
                </div>
                <div style="color: #fff; font-size: 20px; white-space: pre-wrap; line-height: 1.6;">
                    {safe_response_a}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Only show button if no choice made yet
            if not choice_made:
                if st.button("Choose A", key=f"choose_a_{turn_number}", use_container_width=True):
                    self._record_comparison_preference(turn_number, 'a')
                    st.rerun()

        with col_b:
            chosen_badge_b = " ✓ CHOSEN" if existing_preference == 'b' else ""
            st.markdown(f"""
            <div style="background-color: #1a1a1a; border: 2px solid {border_b}; border-radius: 10px; padding: 15px; min-height: 200px;">
                <div style="color: {label_color_b}; font-size: 20px; font-weight: bold; margin-bottom: 10px;">
                    Response B{chosen_badge_b}
                </div>
                <div style="color: #fff; font-size: 20px; white-space: pre-wrap; line-height: 1.6;">
                    {safe_response_b}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Only show button if no choice made yet
            if not choice_made:
                if st.button("Choose B", key=f"choose_b_{turn_number}", use_container_width=True):
                    self._record_comparison_preference(turn_number, 'b')
                    st.rerun()

    def _record_comparison_preference(self, turn_number: int, preference: str):
        """Record user's preference in comparison mode."""
        import logging
        logger = logging.getLogger(__name__)

        # Store preference in session
        if 'comparison_preferences' not in st.session_state:
            st.session_state.comparison_preferences = {}
        st.session_state.comparison_preferences[turn_number] = preference

        # Mark feedback as given for this turn
        feedback_key = f"beta_feedback_{turn_number}"
        st.session_state[feedback_key] = True

        logger.info(f"Comparison preference recorded: Turn {turn_number} -> Response {preference.upper()}")

    def _render_scrollable_history_window(self, current_turn_idx: int, all_turns: list):
        """Render scroll view window at top of screen."""
        # Header for the scrollable window
        # Scrollable container
        st.markdown("""
        <div id="scroll-history-container" style="
            max-height: 500px;
            overflow-y: auto;
            padding: 15px;
            background-color: #1a1a1a;
            border: 1px solid #F4D03F;
            border-radius: 8px;
            margin-bottom: 0px;
        ">
        """, unsafe_allow_html=True)

        # Check if Demo Mode
        demo_mode = st.session_state.get('telos_demo_mode', False)

        # Render all turns BEFORE current (current turn is rendered separately by _render_current_turn_only)
        for idx in range(current_turn_idx):  # Exclude current turn to prevent duplicates
            turn_data = all_turns[idx]

            # In Demo Mode: pass None for turn_number (no turn badges, no metrics, no scroll buttons in history)
            # In Open Mode: pass turn_number (show turn badges and metrics in history)
            turn_number = None if demo_mode else (idx + 1)

            # Render messages with history key prefix to avoid duplicates
            self._render_user_message(turn_data.get('user_input', ''), turn_number, turn_data, key_prefix="history_")
            self._render_assistant_message(
                turn_data.get('response', ''),
                turn_number,
                is_loading=turn_data.get('is_loading', False),
                key_prefix="history_"
            )

            # Add divider between turns (except after last turn in history)
            if idx < current_turn_idx - 1:
                st.markdown("""
                <div style="border-bottom: 1px solid #444; margin: 19px 0;"></div>
                """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # Auto-scroll the history container to the bottom (most recent messages)
        import streamlit.components.v1 as components
        components.html("""
        <script>
            // Auto-scroll scroll history container to bottom
            setTimeout(function() {
                const container = window.parent.document.getElementById('scroll-history-container');
                if (container) {
                    container.scrollTop = container.scrollHeight;
                }
            }, 100);
        </script>
        """, height=0)

    def _render_fidelity_card(self, turn_data: dict = None, is_calculating: bool = False, key_prefix: str = ""):
        """
        Render glassmorphism-styled fidelity/PA status card.

        This displays fidelity score and PA status in a separate area to the left
        of messages with a warm gold glassmorphism effect.

        Args:
            turn_data: Turn data containing fidelity metrics
            is_calculating: If True, show pulsing "calculating" animation
            key_prefix: Prefix for unique keys
        """
        # Get PA convergence status
        pa_converged = getattr(self.state_manager.state, 'pa_converged', False)
        demo_mode = st.session_state.get('telos_demo_mode', False)
        beta_mode = st.session_state.get('active_tab') == 'BETA'

        # Don't show fidelity card in demo mode (metrics are internal)
        if demo_mode:
            return

        # Calculate fidelity from turn_data (same logic as before)
        fidelity = None
        # BETA MODE FIX: Allow value extraction even if pa_converged is not set
        if turn_data and (pa_converged or beta_mode):
            fidelity = turn_data.get('fidelity')

            # Check beta_data first (more accurate for BETA mode)
            beta_data = turn_data.get('beta_data', {})
            beta_fidelity = beta_data.get('telos_fidelity') or beta_data.get('fidelity_score')
            if beta_fidelity is not None and beta_fidelity > 0:
                fidelity = beta_fidelity

            # Also try telos_analysis
            if fidelity is None or fidelity == 0.0 or fidelity == 0.5:
                telos_analysis = turn_data.get('telos_analysis', {})
                telos_fidelity = telos_analysis.get('fidelity_score')
                if telos_fidelity is not None and telos_fidelity > 0:
                    fidelity = telos_fidelity

            # NO HARDCODED DEFAULTS - If fidelity data is not available, show "---"
            # This exposes when the actual mathematics isn't producing values
            # REMOVED: fidelity = 0.85 default that was masking missing data

        # Determine colors based on fidelity - full color-coded versioning
        # Goldilocks zones: GREEN >= 0.70, YELLOW 0.60-0.69, ORANGE 0.50-0.59, RED < 0.50
        from telos_observatory.config.colors import _ZONE_ALIGNED, _ZONE_MINOR_DRIFT, _ZONE_DRIFT, _normalize_score
        if fidelity is not None:
            fidelity = _normalize_score(fidelity)  # Handle string percentages like "68%"
            if fidelity >= _ZONE_ALIGNED:  # >= 0.70 Aligned
                fidelity_color = "#27ae60"  # Green
                fidelity_glow = "76, 175, 80"  # Green RGB for box glow
            elif fidelity >= _ZONE_MINOR_DRIFT:  # 0.60-0.69 Minor Drift
                fidelity_color = "#F4D03F"  # Yellow/Gold
                fidelity_glow = "244, 208, 63"  # Gold RGB for box glow
            elif fidelity >= _ZONE_DRIFT:  # 0.50-0.59 Drift Detected
                fidelity_color = "#e67e22"  # Orange
                fidelity_glow = "255, 165, 0"  # Orange RGB for box glow
            else:  # < 0.50 Significant Drift
                fidelity_color = "#e74c3c"  # Red
                fidelity_glow = "255, 68, 68"  # Red RGB for box glow
            fidelity_display = f"{int(round(fidelity * 100))}%"
        else:
            fidelity_color = "#888"
            fidelity_glow = "136, 136, 136"  # Gray RGB
            fidelity_display = "---"

        pa_status = "Established" if pa_converged else "Calibrating"
        pa_color = "#27ae60" if pa_converged else "#e67e22"

        # Glassmorphism CSS with warm gold tones and pulsing animation
        # OPPOSITE to calibrating: bright at 0%/100%, dim at 50% (calibrating is dim at 0%/100%, bright at 50%)
        pulse_class = "fidelity-calculating" if is_calculating else ""

        # FAUX-GLASSMORPHISM: Since backdrop-filter doesn't work in Streamlit iframes,
        # simulate glass effect with layered gradients, glows, and transparency
        # Now with color-coded background based on fidelity category
        st.markdown(f"""
<style>
@keyframes fidelity-pulse-glass {{
    0%, 100% {{
        /* BRIGHT at start/end (opposite of calibrating which is dim here) */
        box-shadow:
            0 0 50px rgba({fidelity_glow}, 0.7),
            0 0 80px rgba({fidelity_glow}, 0.4),
            0 12px 40px rgba(0, 0, 0, 0.4),
            inset 0 2px 4px rgba(255, 255, 255, 0.3),
            inset 0 -2px 6px rgba(0, 0, 0, 0.2);
        border-color: rgba({fidelity_glow}, 1);
        transform: scale(1.02);
    }}
    50% {{
        /* DIM at midpoint (opposite of calibrating which is bright here) */
        box-shadow:
            0 0 20px rgba({fidelity_glow}, 0.3),
            0 12px 40px rgba(0, 0, 0, 0.6),
            inset 0 2px 4px rgba(255, 255, 255, 0.15),
            inset 0 -2px 6px rgba(0, 0, 0, 0.3);
        border-color: rgba({fidelity_glow}, 0.5);
        transform: scale(1);
    }}
}}
@keyframes fidelity-text-pulse-glass {{
    /* OPPOSITE timing: bright at 0%/100%, dim at 50% */
    0%, 100% {{ opacity: 1; color: {fidelity_color}; }}
    50% {{ opacity: 0.7; color: #ccc; }}
}}
.fidelity-glass {{
    /* ENHANCED GLASSMORPHISM: Much more dramatic glass effect with color-coded background */
    background:
        /* Top highlight shine layer */
        linear-gradient(135deg, rgba(255, 255, 255, 0.25) 0%, rgba(255, 255, 255, 0.08) 30%, transparent 60%),
        /* Color-coded ambient glow layer based on fidelity */
        linear-gradient(180deg, rgba({fidelity_glow}, 0.35) 0%, rgba({fidelity_glow}, 0.15) 40%, rgba(0, 0, 0, 0.3) 100%),
        /* Frosted glass base */
        rgba(25, 22, 18, 0.92);
    /* Prominent color-coded border */
    border: 2px solid rgba({fidelity_glow}, 0.7);
    border-top: 2px solid rgba(255, 255, 255, 0.35);
    border-radius: 16px;
    padding: 16px 14px;
    /* Dramatic multi-layer shadow for depth with color-coded glow */
    box-shadow:
        /* Outer soft color-coded glow */
        0 0 30px rgba({fidelity_glow}, 0.4),
        /* Deep shadow for depth */
        0 12px 40px rgba(0, 0, 0, 0.6),
        /* Inner top highlight */
        inset 0 2px 4px rgba(255, 255, 255, 0.2),
        /* Inner bottom shadow */
        inset 0 -2px 6px rgba(0, 0, 0, 0.3),
        /* Inner color-coded ambient */
        inset 0 0 20px rgba({fidelity_glow}, 0.1);
    min-width: 80px;
    position: relative;
    overflow: hidden;
}}
/* Top shine effect - enhanced glass reflection */
.fidelity-glass::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 5%;
    right: 5%;
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.6), transparent);
    border-radius: 2px;
}}
/* Bottom inner glow for glass depth */
.fidelity-glass::after {{
    content: '';
    position: absolute;
    bottom: 0;
    left: 10%;
    right: 10%;
    height: 40%;
    background: linear-gradient(to top, rgba(244, 208, 63, 0.08), transparent);
    pointer-events: none;
}}
.fidelity-glass.fidelity-calculating {{
    animation: fidelity-pulse-glass 2s ease-in-out infinite;
}}
.fidelity-glass-value {{
    font-size: 26px;
    font-weight: bold;
    text-align: center;
    margin: 8px 0;
    text-shadow:
        0 2px 4px rgba(0, 0, 0, 0.6),
        0 0 20px currentColor,
        0 0 40px currentColor;
    position: relative;
    z-index: 1;
}}
.fidelity-glass-value.fidelity-calculating {{
    animation: fidelity-text-pulse-glass 2s ease-in-out infinite;
}}
.fidelity-glass-label {{
    font-size: 12px;
    color: {fidelity_color};
    text-align: center;
    text-transform: uppercase;
    letter-spacing: 2px;
    font-weight: 600;
    text-shadow: 0 0 8px rgba({fidelity_glow}, 0.5);
    margin-bottom: 4px;
}}
.fidelity-glass-status {{
    font-size: 9px;
    text-align: center;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid rgba(244, 208, 63, 0.25);
}}
</style>
<div class="fidelity-glass {pulse_class}">
    <div class="fidelity-glass-label">Fidelity</div>
    <div class="fidelity-glass-value {pulse_class}" style="color: {fidelity_color};">
        {fidelity_display if not is_calculating else "..."}
    </div>
    <div class="fidelity-glass-status">
        <span style="color: rgba(200, 200, 200, 0.7);">PA:</span>
        <span style="color: {pa_color}; font-weight: 600;">{pa_status if not is_calculating else "..."}</span>
    </div>
</div>
""", unsafe_allow_html=True)

    def _render_calibration_card(self, turn_data: dict = None, is_calculating: bool = False, key_prefix: str = "", turn_number: int = None):
        """
        Render centered horizontal calibration card between user and TELOS messages.

        This displays User Fidelity, AI Fidelity, and Primacy State in a horizontal
        layout centered between messages. This is the "mini alignment lens" that
        reinforces the calibration feel of the TELOS system.

        Args:
            turn_data: Turn data containing fidelity metrics
            is_calculating: If True, show pulsing "calculating" animation
            key_prefix: Prefix for unique keys
            turn_number: Specific turn number to fetch data for (critical for history)
        """
        # Get PA convergence status
        pa_converged = getattr(self.state_manager.state, 'pa_converged', False)
        demo_mode = st.session_state.get('telos_demo_mode', False)
        # FIX: Use correct BETA mode detection (matching line 243)
        # telos_beta_mode was never set - active_tab is the actual indicator
        active_tab = st.session_state.get('active_tab', '')
        beta_mode = active_tab == "BETA"

        # BETA MODE FIX: If turn_data is None in BETA mode, retrieve from session state
        # BETA stores turn data in st.session_state[f'beta_turn_{turn_number}_data']
        if turn_data is None and beta_mode:
            # CRITICAL FIX: If specific turn_number provided, fetch THAT turn's data
            # This ensures historical turns show their own fidelity, not the latest turn's
            if turn_number is not None:
                beta_turn_data = st.session_state.get(f'beta_turn_{turn_number}_data', {})
                if beta_turn_data:
                    turn_data = beta_turn_data
            else:
                # Only search backwards if no specific turn_number (e.g., current/loading turn)
                current_turn = st.session_state.get('beta_current_turn', 1)
                for turn_num in range(current_turn, 0, -1):
                    beta_turn_data = st.session_state.get(f'beta_turn_{turn_num}_data', {})
                    if beta_turn_data:
                        turn_data = beta_turn_data
                        break

        # Don't show calibration card in demo mode
        if demo_mode:
            return

        # Don't show calibration card in BETA mode (fidelity metrics in Alignment Lens only)
        if beta_mode:
            return

        # === FIRST TURN LOGIC ===
        # User said: "yeah last telos values actually is best. And then it recalculates.
        # And for the first it starts gray. ONLY THE FIRST"
        #
        # Logic:
        # 1. First turn ever (no last_telos_values stored) = gray pulsing
        # 2. Native responses = show last TELOS values (don't recalculate)
        # 3. TELOS responses = calculate new values and update session state

        last_telos_values = st.session_state.get('last_telos_calibration_values', None)
        is_first_turn = last_telos_values is None

        # FIDELITY-FIRST FLOW: Always pulse when calculating, regardless of turn
        # This provides clear feedback that fidelity is being calculated
        # On first turn: gray pulse with "..."
        # On subsequent turns: pulse with "Calculating Fidelity..." text
        show_gray_pulse = is_calculating and is_first_turn
        show_calculating_state = is_calculating  # New: track calculating for all turns

        # Calculate fidelity values from turn_data using ACTUAL TELOS mathematics
        # The real values come from primacy_state.py compute_primacy_state():
        #   - user_pa_fidelity = F_user (cosine similarity to user PA)
        #   - ai_pa_fidelity = F_AI (cosine similarity to AI PA)
        #   - primacy_state_score = PS = ρ_PA · (2·F_user·F_AI) / (F_user + F_AI)
        user_fidelity = None
        ai_fidelity = None
        primacy_state = None
        telos_analysis = {}  # Initialize here to prevent UnboundLocalError when turn_data is None

        # BETA MODE FIX: Allow value extraction even if pa_converged is not set
        # In BETA mode, PA is established via questionnaire (pa_established=True)
        if turn_data and (pa_converged or beta_mode):
            # === PRIMACY STATE (from actual PS calculation) ===
            # DISPLAY NORMALIZATION: Prefer display_primacy_state for UI rendering
            # This ensures PS is calculated from display-normalized user fidelity
            # to avoid visual inconsistency (e.g., User=0.736, AI=0.814, PS=0.476)
            telos_analysis = turn_data.get('telos_analysis', {})

            # Priority 1: Display-normalized PS (for UI consistency)
            primacy_state = telos_analysis.get('display_primacy_state')

            # Priority 2: Direct turn_data display_primacy_state
            if primacy_state is None:
                primacy_state = turn_data.get('display_primacy_state')

            # Priority 3: Raw primacy_state_score (fallback for non-normalized flows)
            if primacy_state is None:
                primacy_state = turn_data.get('primacy_state_score')

            # Also check ps_metrics dict if primacy_state_score not directly available
            ps_metrics = turn_data.get('ps_metrics', {})
            if primacy_state is None and ps_metrics:
                primacy_state = ps_metrics.get('ps_score')

            # BETA MODE FIX: Check inside telos_analysis for primacy_state_score (raw fallback)
            if primacy_state is None:
                primacy_state = telos_analysis.get('primacy_state_score')

            # === USER FIDELITY (F_user from dual PA calculation) ===
            # DISPLAY NORMALIZATION: Prefer display_user_pa_fidelity for UI rendering
            # This maps SentenceTransformer raw scores (0.30→0.70, 0.20→0.60, 0.12→0.50)
            # to user-expected display values while keeping raw values for calculations.
            # Note: telos_analysis already declared above in PRIMACY STATE section

            # Priority 1: Normalized display value (for UI)
            user_fidelity = telos_analysis.get('display_user_pa_fidelity')

            # Priority 2: Direct response_data display_fidelity
            if user_fidelity is None:
                user_fidelity = turn_data.get('display_fidelity')

            # Priority 3: Raw user_pa_fidelity (fallback for non-normalized flows)
            if user_fidelity is None:
                user_fidelity = turn_data.get('user_pa_fidelity')
            if user_fidelity is None and ps_metrics:
                user_fidelity = ps_metrics.get('f_user')

            # Fallback: check beta_data for user_fidelity
            if user_fidelity is None:
                beta_data = turn_data.get('beta_data', {})
                user_fidelity = beta_data.get('user_fidelity') or beta_data.get('input_fidelity')

            # BETA MODE FIX: Check inside telos_analysis for user_pa_fidelity (raw)
            if user_fidelity is None:
                user_fidelity = telos_analysis.get('user_pa_fidelity')

            # === AI/TELOS FIDELITY (F_AI from dual PA calculation) ===
            # PRIORITY ORDER: Dual PA values (ai_pa_fidelity) FIRST, legacy fallbacks LAST
            # This prevents legacy 0 values from masking real calculated values

            # 1. Direct turn data (state_manager path)
            ai_fidelity = turn_data.get('ai_pa_fidelity')

            # 2. ps_metrics dict
            if ai_fidelity is None and ps_metrics:
                ai_fidelity = ps_metrics.get('f_ai')

            # 3. BETA MODE: Check telos_analysis for ai_pa_fidelity (the CORRECT dual PA value)
            if ai_fidelity is None:
                telos_analysis = turn_data.get('telos_analysis', {})
                ai_fidelity = telos_analysis.get('ai_pa_fidelity')

            # 4. Legacy fallbacks ONLY if dual PA not available (and skip 0/falsy values)
            if ai_fidelity is None:
                beta_data = turn_data.get('beta_data', {})
                legacy_fidelity = beta_data.get('telos_fidelity') or beta_data.get('fidelity_score')
                # Only use legacy if it's a real non-zero value
                if legacy_fidelity is not None and legacy_fidelity > 0:
                    ai_fidelity = legacy_fidelity

            if ai_fidelity is None:
                telos_analysis = turn_data.get('telos_analysis', {})
                legacy_score = telos_analysis.get('fidelity_score')
                if legacy_score is not None and legacy_score > 0:
                    ai_fidelity = legacy_score

            # 5. Last resort fallback to general fidelity field
            if ai_fidelity is None:
                ai_fidelity = turn_data.get('fidelity')

        # === LAST TELOS VALUES LOGIC ===
        # If we have valid calculated values (TELOS response), save them
        # If we don't have values (native response or loading), use saved values
        has_calculated_values = (user_fidelity is not None or ai_fidelity is not None or primacy_state is not None)

        # Check if this is a pivot turn - DON'T cache pivot turn's hardcoded 1.0 values
        # because they would pollute subsequent turns' display after a PA shift
        # Handle turn_data being None (during loading state)
        is_pivot_turn = (turn_data.get('is_telos_command', False) if turn_data else False) or telos_analysis.get('pivot_detected', False)

        if has_calculated_values and not is_calculating and not is_pivot_turn:
            # This is a TELOS response with real values - save to session state
            # Skip caching for pivot turns to prevent their 1.0 values from polluting later turns
            st.session_state.last_telos_calibration_values = {
                'user_fidelity': user_fidelity,
                'ai_fidelity': ai_fidelity,
                'primacy_state': primacy_state
            }
        elif not has_calculated_values and last_telos_values is not None and is_calculating:
            # ONLY use last values during active calculation (loading state)
            # Historical turns without values should show "---", not cached values
            user_fidelity = last_telos_values.get('user_fidelity')
            ai_fidelity = last_telos_values.get('ai_fidelity')
            primacy_state = last_telos_values.get('primacy_state')

        # Helper to get color for a fidelity value
        def get_fidelity_color(fidelity):
            if fidelity is None:
                return "#888", "136, 136, 136"
            # Use centralized normalizer to handle string percentages like "68%"
            from telos_observatory.config.colors import _ZONE_ALIGNED, _ZONE_MINOR_DRIFT, _ZONE_DRIFT, _normalize_score
            fidelity = _normalize_score(fidelity)
            # Goldilocks zone thresholds: GREEN >= 0.70, YELLOW >= 0.60, ORANGE >= 0.50
            if fidelity >= _ZONE_ALIGNED:  # >= 0.70 Aligned
                return "#27ae60", "76, 175, 80"  # Green
            elif fidelity >= _ZONE_MINOR_DRIFT:  # 0.60-0.69 Minor Drift
                return "#F4D03F", "244, 208, 63"  # Yellow/Gold
            elif fidelity >= _ZONE_DRIFT:  # 0.50-0.59 Drift Detected
                return "#e67e22", "230, 126, 34"  # Orange (canonical)
            else:  # < 0.50 Significant Drift
                return "#e74c3c", "231, 76, 60"  # Red (canonical)

        # Get colors for each metric
        user_color, user_glow = get_fidelity_color(user_fidelity)
        ai_color, ai_glow = get_fidelity_color(ai_fidelity)

        # PRIMACY STATE uses the actual calculated PS value, NOT a simple average
        # Real formula: PS = ρ_PA · (2·F_user·F_AI) / (F_user + F_AI) (harmonic mean weighted by correlation)
        # The primacy_state variable was already extracted from turn_data above

        # Get color for Primacy State (using the actual PS value)
        ps_color, ps_glow = get_fidelity_color(primacy_state)

        # Display values - using ACTUAL mathematics from TELOS (percentages)
        user_display = f"{int(round(user_fidelity * 100))}%" if user_fidelity is not None else "---"
        ai_display = f"{int(round(ai_fidelity * 100))}%" if ai_fidelity is not None else "---"
        ps_display = f"{int(round(primacy_state * 100))}%" if primacy_state is not None else "---"

        # Pulse class for animation - apply on ALL turns when calculating
        # This provides clear "Calculating Fidelity..." feedback in fidelity-first flow
        pulse_class = "calibration-calculating" if show_calculating_state else ""

        # Helper to get status label for fidelity values (Goldilocks zones)
        def get_fidelity_status(f):
            from telos_observatory.config.colors import _ZONE_ALIGNED, _ZONE_MINOR_DRIFT, _ZONE_DRIFT, _normalize_score
            if f is None:
                return "---"
            f = _normalize_score(f)
            if f >= _ZONE_ALIGNED:  # >= 0.70
                return "ALIGNED"
            elif f >= _ZONE_MINOR_DRIFT:  # 0.60-0.69
                return "MINOR DRIFT"
            elif f >= _ZONE_DRIFT:  # 0.50-0.59
                return "DRIFT DETECTED"
            else:  # < 0.50
                return "SIGNIFICANT DRIFT"

        # Get status labels for USER and AI fidelity
        # Show "..." on first turn (gray pulse), "Calculating..." on subsequent turns during calc
        # Otherwise show actual status
        if show_gray_pulse:
            user_status = "..."
            ai_status = "..."
            ps_status = "..."
        elif show_calculating_state:
            user_status = "Calculating..."
            ai_status = "Calculating..."
            ps_status = "Calculating..."
        else:
            user_status = get_fidelity_status(user_fidelity)
            ai_status = get_fidelity_status(ai_fidelity)
            ps_status = "Harmonic Mean"

        # Three miniature fidelity cards matching the expanded design
        st.markdown(f"""
<style>
/* Subtle pulse matching Contemplating animation - just color/border fade */
@keyframes fidelity-card-pulse {{
    0%, 100% {{
        border-color: #F4D03F;
        box-shadow: 0 0 12px rgba(244, 208, 63, 0.3);
    }}
    50% {{
        border-color: #a8a8a8;
        box-shadow: 0 0 8px rgba(136, 136, 136, 0.2);
    }}
}}
@keyframes fidelity-text-pulse {{
    0%, 100% {{
        color: #F4D03F;
    }}
    50% {{
        color: #a8a8a8;
    }}
}}
.fidelity-cards-container {{
    display: flex;
    justify-content: center;
    gap: 10px;
    margin: 15px auto;
    max-width: 600px;
}}
.fidelity-card {{
    background-color: #1a1a1a;
    border: 2px solid #888;
    border-radius: 10px;
    padding: 15px 18px;
    text-align: center;
    flex: 1;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}}
.fidelity-card.calculating {{
    animation: fidelity-card-pulse 2s ease-in-out infinite;
}}
.fidelity-card-label {{
    font-size: 14px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}}
.fidelity-card-value {{
    font-size: 36px;
    font-weight: bold;
    margin: 6px 0;
}}
.fidelity-card-value.calculating {{
    animation: fidelity-text-pulse 2s ease-in-out infinite;
}}
.fidelity-card-status {{
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    margin-top: 8px;
}}
</style>
<div class="fidelity-cards-container">
    <div class="fidelity-card {'calculating' if show_gray_pulse else ''}" style="border-color: {user_color if not show_gray_pulse else '#888'};">
        <div class="fidelity-card-label" style="color: {user_color if not show_gray_pulse else '#888'};">USER FIDELITY</div>
        <div class="fidelity-card-value {'calculating' if show_gray_pulse else ''}" style="color: {user_color if not show_gray_pulse else '#888'};">
            {user_display if not show_gray_pulse else "..."}
        </div>
        <div class="fidelity-card-status" style="color: {user_color if not show_gray_pulse else '#888'};">{user_status}</div>
    </div>
    <div class="fidelity-card {'calculating' if show_gray_pulse else ''}" style="border-color: {ai_color if not show_gray_pulse else '#888'};">
        <div class="fidelity-card-label" style="color: {ai_color if not show_gray_pulse else '#888'};">AI FIDELITY</div>
        <div class="fidelity-card-value {'calculating' if show_gray_pulse else ''}" style="color: {ai_color if not show_gray_pulse else '#888'};">
            {ai_display if not show_gray_pulse else "..."}
        </div>
        <div class="fidelity-card-status" style="color: {ai_color if not show_gray_pulse else '#888'};">{ai_status}</div>
    </div>
    <div class="fidelity-card {'calculating' if show_gray_pulse else ''}" style="border-color: {ps_color if not show_gray_pulse else '#888'};">
        <div class="fidelity-card-label" style="color: {ps_color if not show_gray_pulse else '#888'};">PRIMACY STATE</div>
        <div class="fidelity-card-value {'calculating' if show_gray_pulse else ''}" style="color: {ps_color if not show_gray_pulse else '#888'};">
            {ps_display if not show_gray_pulse else "..."}
        </div>
        <div class="fidelity-card-status" style="color: {ps_color if not show_gray_pulse else '#888'};">{ps_status}</div>
    </div>
</div>
""", unsafe_allow_html=True)

    def _render_user_message(self, message: str, turn_number: int = None, turn_data: dict = None, key_prefix: str = ""):
        """Render user message bubble with optional turn number badge and metrics."""
        import html

        # Build turn badge HTML if turn_number provided
        turn_badge = ""
        metrics_html = ""
        scroll_button = ""

        if turn_number is not None:
            # Badge styling is now in CSS class below
            turn_badge = ""

            # Add scroll toggle button
            scroll_label = "📜 Scroll View" if not self.state_manager.state.scrollable_history_mode else "✕ Close"
            # Note: We can't add interactive button in markdown, so we'll add it via Streamlit columns before this

            # Add metrics if turn_data provided AND NOT in Demo Mode
            # Demo Mode: PA is pre-established, metrics are internal (not user-facing)
            # Observatory/Open Mode: PA is calibrating, show governance metrics
            demo_mode = st.session_state.get('telos_demo_mode', False)

            if turn_data and not demo_mode:
                # Check if PA is converged
                pa_converged = getattr(self.state_manager.state, 'pa_converged', False)

                # Only show fidelity metrics if PA is established
                if pa_converged:
                    # Check multiple sources for fidelity (BETA mode stores in beta_data)
                    fidelity = turn_data.get('fidelity')

                    # Check beta_data first (more accurate for BETA mode)
                    beta_data = turn_data.get('beta_data', {})
                    beta_fidelity = beta_data.get('telos_fidelity') or beta_data.get('fidelity_score')
                    if beta_fidelity is not None and beta_fidelity > 0:
                        fidelity = beta_fidelity

                    # Also try telos_analysis
                    if fidelity is None or fidelity == 0.0 or fidelity == 0.5:
                        telos_analysis = turn_data.get('telos_analysis', {})
                        telos_fidelity = telos_analysis.get('fidelity_score')
                        if telos_fidelity is not None and telos_fidelity > 0:
                            fidelity = telos_fidelity

                    # NO HARDCODED DEFAULTS - If fidelity data is not available, show "---"
                    # This exposes when actual TELOS mathematics isn't producing values

                    # Determine fidelity color and display (handle None properly)
                    if fidelity is not None and fidelity > 0 and fidelity != 0.5:
                        fidelity_color = "#27ae60" if fidelity >= 0.70 else "#F4D03F" if fidelity >= 0.60 else "#e67e22" if fidelity >= 0.50 else "#e74c3c"  # Canonical fidelity zones
                        fidelity_display = f"{int(round(fidelity * 100))}%"
                    else:
                        fidelity_color = "#888"  # Gray for missing data
                        fidelity_display = "---"

                    pa_status = "Established"
                    pa_color = "#27ae60"

                    # Add ΔF (Delta Fidelity) if available
                    delta_f_html = ""
                    if 'delta_f' in turn_data:
                        delta_f = turn_data.get('delta_f', 0.0)
                        delta_f_color = "#27ae60" if delta_f > 0 else "#e74c3c" if delta_f < 0 else "#888"
                        delta_f_sign = "+" if delta_f >= 0 else ""
                        delta_f_html = f'<span style="margin-left: 15px; display: inline-block;"><span style="color: #a8a8a8; font-size: 14px;">ΔF:</span> <span style="color: {delta_f_color}; font-size: 20px; font-weight: bold; margin-left: 5px;">{delta_f_sign}{int(round(delta_f * 100))}%</span></span>'

                    metrics_html = f'<span style="margin-left: 15px; display: inline-block;"><span style="color: #a8a8a8; font-size: 14px;">Fidelity:</span> <span style="color: {fidelity_color}; font-size: 20px; font-weight: bold; margin-left: 5px;">{fidelity_display}</span></span>{delta_f_html}<span style="margin-left: 15px; display: inline-block;"><span style="color: #a8a8a8; font-size: 14px;">Primacy Attractor Status:</span> <span style="color: {pa_color}; font-size: 14px; font-weight: bold; margin-left: 5px;">{pa_status}</span></span>'
                else:
                    # PA still calibrating - show calibrating status only
                    pa_status = "Calibrating"
                    pa_color = "#e67e22"
                    metrics_html = f'<span style="margin-left: 15px; display: inline-block;"><span style="color: #a8a8a8; font-size: 14px;">Primacy Attractor Status:</span> <span style="color: {pa_color}; font-size: 14px; font-weight: bold; margin-left: 5px;">{pa_status} ({turn_number}/~10)</span></span>'

        # Escape the message content to prevent HTML injection
        safe_message = html.escape(message)

        # Check if Demo Mode (affects layout - no turn badges, no scroll button)
        demo_mode = st.session_state.get('telos_demo_mode', False)

        # Check if BETA mode - apply centered Observatory layout
        active_tab = st.session_state.get('active_tab', 'DEMO')
        beta_mode = active_tab == "BETA"

        if demo_mode:
            # Demo Mode: Clean, simple layout - NO scroll buttons (scrollable history disabled in Demo Mode)
            st.markdown(f"""
<div class="message-container" style="background-color: #1a1a1a; padding: 15px; border-radius: 10px; margin: 0; border: 2px solid #F4D03F;">
    <div style="color: #a8a8a8; font-size: 19px; margin-bottom: 5px;">
        <strong style="color: #F4D03F;">User</strong>
    </div>
    <div style="color: #fff; font-size: 19px; white-space: pre-wrap;">
        {safe_message}
    </div>
</div>
""", unsafe_allow_html=True)
        elif beta_mode:
            # BETA Mode: Simplified layout - fidelity moved to calibration card between messages
            # UPDATED: No external turn badge column - badge now inside message bubble for more width
            # BETA mode: Single column with nested layout for buttons INSIDE message width
            # Determine fidelity-based color for user message
            # Use DIRECT session_state access like TELOS window does (proven working)
            # DISPLAY NORMALIZATION: Prefer display_user_pa_fidelity for UI rendering
            fidelity_level = None
            user_fidelity_numeric = None
            if turn_number is not None:
                user_turn_data = st.session_state.get(f'beta_turn_{turn_number}_data', {})
                user_telos_analysis = user_turn_data.get('telos_analysis', {})
                # Prefer display value (normalized) over raw value
                user_fidelity_numeric = user_telos_analysis.get('display_user_pa_fidelity') or user_telos_analysis.get('user_pa_fidelity')
                if user_fidelity_numeric is not None:
                    # Goldilocks zone thresholds - use normalizer for string percentages
                    from telos_observatory.config.colors import _ZONE_ALIGNED, _ZONE_MINOR_DRIFT, _ZONE_DRIFT, _normalize_score
                    user_fidelity_numeric = _normalize_score(user_fidelity_numeric)
                    if user_fidelity_numeric >= _ZONE_ALIGNED:  # >= 0.70 Aligned
                        fidelity_level = 'green'
                    elif user_fidelity_numeric >= _ZONE_MINOR_DRIFT:  # 0.60-0.69 Minor Drift
                        fidelity_level = 'yellow'
                    elif user_fidelity_numeric >= _ZONE_DRIFT:  # 0.50-0.59 Drift Detected
                        fidelity_level = 'orange'
                    else:  # < 0.50 Significant Drift
                        fidelity_level = 'red'

            # Map fidelity level to color
            # No border by default (transparent) - colored border only appears after calibration
            FIDELITY_COLORS = {
                'green': '#27ae60',   # Good alignment
                'yellow': '#F4D03F',  # Mild drift (gold)
                'orange': '#e67e22',  # Moderate drift
                'red': '#e74c3c'      # Severe drift
            }
            # Default to transparent (no visible border) before calibration
            fidelity_color = FIDELITY_COLORS.get(fidelity_level, 'transparent') if fidelity_level else 'transparent'
            # Label color - same as fidelity but use neutral gray when not calibrated
            label_color = FIDELITY_COLORS.get(fidelity_level, '#888') if fidelity_level else '#888'
            # Turn badge color - always visible (use gray before calibration, fidelity color after)
            turn_badge_color = FIDELITY_COLORS.get(fidelity_level, '#888') if fidelity_level else '#888'

            # Build turn badge HTML for inside the message (if turn_number provided)
            # Badge goes in top left corner, so no left margin needed
            turn_badge_html = ""
            if turn_number is not None:
                turn_badge_html = f'<div style="margin-bottom: 5px;"><span style="background-color: #2d2d2d; color: {turn_badge_color}; border: 1px solid {turn_badge_color}; padding: 5px 10px; border-radius: 4px; font-size: 18px; font-weight: bold;">{turn_number}</span></div>'

            # BETA Mode: Clean single-column layout (no side buttons for cleaner alignment)
            # Scroll and Steward buttons removed for Beta MVP - users can access Steward panel separately
            st.markdown(f"""
<div class="message-container" style="background-color: #1a1a1a; padding: 15px; border-radius: 10px; margin: 0 0 20px 0; border: 2px solid {fidelity_color};">
    {turn_badge_html}
    <div style="color: #a8a8a8; font-size: 20px; margin-bottom: 5px;">
        <strong style="color: {label_color};">User</strong>
    </div>
    <div style="color: #fff; font-size: 20px; white-space: pre-wrap;">
        {safe_message}
    </div>
</div>
""", unsafe_allow_html=True)
            # Copy button removed from Beta for cleaner UI (restore for full TELOS)
            # Scroll/Steward buttons removed for Beta MVP to fix alignment issues

            # NOTE: Shift Focus button removed from main conversation space
            # All interaction buttons now appear ONLY in the Alignment Lens panel
            # (see beta_observation_deck.py) to keep conversation space clean

        else:
            # Open Mode: Full Observatory layout with fidelity card, turn badge and scroll button
            # Create columns: [fidelity 0.8, turn_badge 0.5, content 9.2]
            col_fidelity, col_turn, col_content = st.columns([0.8, 0.5, 8.7])

            # Fidelity card on the far left
            with col_fidelity:
                self._render_fidelity_card(turn_data=turn_data, is_calculating=False, key_prefix=key_prefix)

            # Turn badge
            if turn_number is not None:
                with col_turn:
                    st.markdown(f"""
<style>
.turn-badge {{
    background-color: #2d2d2d;
    color: #F4D03F;
    border: 1px solid #F4D03F;
    padding: 10px;
    border-radius: 5px;
    font-size: 24px;
    font-weight: bold;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 50px;
    height: 50px;
    cursor: default;
    transition: all 0.3s ease;
}}

.turn-badge:hover {{
    box-shadow: 0 0 6px #F4D03F;
}}
</style>
<div style="display: flex; align-items: flex-start; height: 100%; padding-bottom: 20px;">
    <span class="turn-badge">{turn_number}</span>
</div>
""", unsafe_allow_html=True)

            # Message content (full width - buttons inside bubble)
            with col_content:
                st.markdown(f"""
<div class="message-container" style="background-color: #1a1a1a; padding: 15px; border-radius: 10px; margin: 0; border: 2px solid #F4D03F;">
    <div style="color: #a8a8a8; font-size: 19px; margin-bottom: 5px;">
        <strong style="color: #F4D03F;">User</strong>
    </div>
    <div style="color: #fff; font-size: 19px; white-space: pre-wrap;">
        {safe_message}
    </div>
</div>
""", unsafe_allow_html=True)

                # Buttons row inside the message area (Scroll + Steward side by side)
                if turn_number is not None:
                    active_tab = st.session_state.get('active_tab', 'DEMO')
                    steward_open = st.session_state.get('beta_steward_panel_open', False) if active_tab == "BETA" else st.session_state.get('steward_panel_open', False)

                    # Create small button row
                    btn_cols = st.columns([1, 1, 1, 6]) if steward_open else st.columns([1, 1, 8])

                    with btn_cols[0]:
                        # Scroll button (📜)
                        if not self.state_manager.state.scrollable_history_mode:
                            if st.button("📜", key=f"{key_prefix}scroll_toggle_{turn_number}", help="Show scroll view"):
                                self.state_manager.toggle_scrollable_history()
                                st.rerun()
                        else:
                            if st.button("✕", key=f"{key_prefix}scroll_close_{turn_number}", help="Close scroll view"):
                                self.state_manager.toggle_scrollable_history()
                                st.rerun()

                    with btn_cols[1]:
                        # Steward button (🤝)
                        if st.button("🤝", key=f"{key_prefix}steward_btn_{turn_number}", help="Ask Steward"):
                            if active_tab == "BETA":
                                st.session_state.beta_steward_panel_open = not st.session_state.get('beta_steward_panel_open', False)
                            else:
                                st.session_state.steward_panel_open = not st.session_state.get('steward_panel_open', False)
                            st.rerun()

                    # X button to close Steward panel - only when panel is open
                    if steward_open:
                        with btn_cols[2]:
                            if st.button("✕", key=f"{key_prefix}close_steward_{turn_number}", help="Close Steward"):
                                if active_tab == "BETA":
                                    st.session_state.beta_steward_panel_open = False
                                else:
                                    st.session_state.steward_panel_open = False
                                st.rerun()

                # Copy button for user message
                render_copy_button(message, f"user_open_{key_prefix}_{turn_number}")

    def _render_assistant_message(self, message: str, turn_number: int = None, is_loading: bool = False, key_prefix: str = ""):
        """Render steward message bubble - aligned with User message."""
        import html

        # Check if Demo Mode (affects layout)
        demo_mode = st.session_state.get('telos_demo_mode', False)

        # Check if BETA mode - apply centered Observatory layout
        active_tab = st.session_state.get('active_tab', 'DEMO')
        beta_mode = active_tab == "BETA"

        if demo_mode:
            # Demo Mode: Simple clean layout
            if is_loading:
                # Show contemplative pulsing animation
                # Border pulses: gray → yellow
                # "Calibrating..." text pulses: yellow → gray (opposite of border)
                st.markdown(f"""
<style>
@keyframes border-pulse {{
    0%, 100% {{
        border-color: #a8a8a8;
        box-shadow: 0 0 6px rgba(136, 136, 136, 0.3);
    }}
    50% {{
        border-color: #F4D03F;
        box-shadow: 0 0 6px rgba(255, 215, 0, 0.4);
    }}
}}
@keyframes text-pulse {{
    0%, 100% {{
        color: #F4D03F;
    }}
    50% {{
        color: #a8a8a8;
    }}
}}
.calibrating-border {{
    animation: border-pulse 2s ease-in-out infinite;
}}
.calibrating-text {{
    animation: text-pulse 2s ease-in-out infinite;
}}
</style>
<div class="calibrating-border" style="background: #1a1a1a; padding: 15px; border-radius: 10px; margin-top: 15px; margin-bottom: 0; border: 2px solid #888; box-shadow: 0 0 20px rgba(244, 208, 63, 0.2), 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 2px rgba(255, 255, 255, 0.15);">
    <div style="color: #a8a8a8; font-size: 19px; margin-bottom: 5px;">
        <strong style="color: #FFF176; text-shadow: 0 0 10px rgba(255, 241, 118, 0.9), 0 0 20px rgba(244, 208, 63, 0.7), 0 0 30px rgba(244, 208, 63, 0.4); letter-spacing: 2px; font-size: 20px;">TELOS</strong>
    </div>
    <div class="calibrating-text" style="font-size: 19px; font-style: italic; opacity: 0.9;">
        Contemplating...
    </div>
</div>
""", unsafe_allow_html=True)
            else:
                # Show response - convert markdown to HTML for proper rendering
                html_message = self._markdown_to_html(message)

                st.markdown(f"""
<div class="message-container" style="background-color: #1a1a1a; padding: 15px; border-radius: 10px; margin-top: 15px; margin-bottom: 5px; border: 2px solid #F4D03F;">
    <div style="color: #a8a8a8; font-size: 19px; margin-bottom: 10px;">
        <strong style="color: #F4D03F;">TELOS</strong>
    </div>
    <div style="color: #fff; font-size: 19px; white-space: pre-wrap;">
        {html_message}
    </div>
</div>
""", unsafe_allow_html=True)
        elif beta_mode:
            # BETA Mode: Simplified layout with calibration card between user and TELOS
            # First render the calibration card (shows USER, TELOS, NET fidelity)
            # Card pulses when loading, shows values when complete
            self._render_calibration_card(turn_data=None, is_calculating=is_loading, key_prefix=key_prefix, turn_number=turn_number)

            # BETA Mode: Clean single-column layout (no side buttons for cleaner alignment)
            # Full width message content to match user message layout
            if is_loading:
                # Show contemplative pulsing animation (clean box, no Measuring Alignment badge)
                st.markdown(f"""
<style>
@keyframes border-pulse {{
    0%, 100% {{
        border-color: #a8a8a8;
        box-shadow: 0 0 6px rgba(136, 136, 136, 0.3);
    }}
    50% {{
        border-color: #F4D03F;
        box-shadow: 0 0 6px rgba(255, 215, 0, 0.4);
    }}
}}
@keyframes text-pulse {{
    0%, 100% {{
        color: #F4D03F;
    }}
    50% {{
        color: #a8a8a8;
    }}
}}
.calibrating-border {{
    animation: border-pulse 2s ease-in-out infinite;
}}
.calibrating-text {{
    animation: text-pulse 2s ease-in-out infinite;
}}
</style>
<div class="calibrating-border" style="background: #1a1a1e; padding: 15px; border-radius: 10px; margin-top: 0; margin-bottom: 0; border: 2px solid #888; box-shadow: 0 0 20px rgba(244, 208, 63, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3); position: relative; z-index: 10;">
    <div style="color: #a8a8a8; font-size: 19px; margin-bottom: 5px;">
        <strong style="color: #F4D03F;">TELOS</strong>
    </div>
    <div class="calibrating-text" style="font-size: 19px; font-style: italic; opacity: 0.9;">
        Contemplating...
    </div>
</div>
""", unsafe_allow_html=True)
            else:
                # Show response with native markdown rendering
                # Get fidelity data for this turn to determine border color AND label
                telos_fidelity_level = None
                response_label = "Steward"  # Unified persona - all responses show as Steward
                steward_style_info = None
                telos_analysis = {}  # Initialize for use in Shift Focus button check below
                if turn_number is not None:
                    telos_turn_data = st.session_state.get(f'beta_turn_{turn_number}_data', {})
                    telos_analysis = telos_turn_data.get('telos_analysis', {})

                    # AI Fidelity for Steward border/label color
                    # Try multiple fallback locations since data structure varies
                    ai_fidelity = telos_analysis.get('ai_pa_fidelity')
                    if ai_fidelity is None:
                        # Fallback: check top-level turn data
                        ai_fidelity = telos_turn_data.get('ai_pa_fidelity')
                    if ai_fidelity is None:
                        # Fallback: check display_fidelity (for native responses)
                        ai_fidelity = telos_turn_data.get('display_fidelity')
                    if ai_fidelity is None:
                        # Fallback: use ps_metrics if available
                        ps_metrics = telos_analysis.get('ps_metrics', {})
                        ai_fidelity = ps_metrics.get('f_ai')

                    # Get Steward style info if available (for governed responses)
                    shown_source = telos_turn_data.get('shown_source', 'native')
                    if shown_source == 'steward':
                        steward_style_info = telos_turn_data.get('steward_style', {})

                    if ai_fidelity is not None:
                        # Fidelity zone thresholds (from config/colors.py)
                        from telos_observatory.config.colors import _ZONE_ALIGNED, _ZONE_MINOR_DRIFT, _ZONE_DRIFT
                        if ai_fidelity >= _ZONE_ALIGNED:  # >= 0.70 Aligned (GREEN)
                            telos_fidelity_level = 'green'
                        elif ai_fidelity >= _ZONE_MINOR_DRIFT:  # 0.60-0.69 Minor Drift (YELLOW)
                            telos_fidelity_level = 'yellow'
                        elif ai_fidelity >= _ZONE_DRIFT:  # 0.50-0.59 Drift Detected (ORANGE)
                            telos_fidelity_level = 'orange'
                        else:  # < 0.50 Significant Drift (RED)
                            telos_fidelity_level = 'red'

                # Map fidelity level to color - gray border by default (before calibration)
                TELOS_FIDELITY_COLORS = {
                    'green': '#27ae60',   # Good alignment (>= 0.70)
                    'yellow': '#F4D03F',  # Mild drift (0.60-0.69)
                    'orange': '#e67e22',  # Moderate drift (0.50-0.59)
                    'red': '#e74c3c'      # Severe drift (< 0.50)
                }
                telos_fidelity_color = TELOS_FIDELITY_COLORS.get(telos_fidelity_level, '#888888') if telos_fidelity_level else '#888888'
                telos_label_color = TELOS_FIDELITY_COLORS.get(telos_fidelity_level, '#888888') if telos_fidelity_level else '#888888'

                # Render message content inside single glassmorphism container
                # Convert markdown to HTML for proper rendering inside the div
                html_message = self._markdown_to_html(message)

                # Single unified glassmorphism box (no separate header/content sections)
                st.markdown(f"""
<div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 15px; margin-top: 0; margin-bottom: 25px; border: 2px solid {telos_fidelity_color}; border-radius: 10px; color: #fff; font-size: 19px; box-shadow: 0 0 15px rgba(244, 208, 63, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1), inset 0 -1px 1px rgba(255, 255, 255, 0.1); position: relative; z-index: 1;">
    {html_message}
</div>
""", unsafe_allow_html=True)
                # Copy button and Shift Focus button removed for Beta MVP

        else:
            # Open Mode: NO fidelity card on assistant messages (only on user messages)
            col_fidelity_spacer, col_turn_spacer, col_content = st.columns([0.8, 0.5, 8.7])

            with col_fidelity_spacer:
                # Empty spacer (no fidelity card on assistant to avoid stacking)
                st.markdown("")

            with col_turn_spacer:
                # Empty column to align with Turn badge space from User message
                st.markdown("")

            with col_content:
                col_msg, col_empty = st.columns([8.0, 2.0])

                with col_msg:
                    if is_loading:
                        # Show contemplative pulsing animation
                        # Border pulses: gray → yellow
                        # "Calibrating..." text pulses: yellow → gray (opposite of border)
                        st.markdown(f"""
<style>
@keyframes border-pulse {{
    0%, 100% {{
        border-color: #a8a8a8;
        box-shadow: 0 0 6px rgba(136, 136, 136, 0.3);
    }}
    50% {{
        border-color: #F4D03F;
        box-shadow: 0 0 6px rgba(255, 215, 0, 0.4);
    }}
}}
@keyframes text-pulse {{
    0%, 100% {{
        color: #F4D03F;
    }}
    50% {{
        color: #a8a8a8;
    }}
}}
.calibrating-border {{
    animation: border-pulse 2s ease-in-out infinite;
}}
.calibrating-text {{
    animation: text-pulse 2s ease-in-out infinite;
}}
</style>
<div class="calibrating-border" style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.15) 0%, rgba(255, 255, 255, 0.05) 30%, transparent 60%), linear-gradient(180deg, rgba(244, 208, 63, 0.2) 0%, rgba(244, 208, 63, 0.1) 40%, rgba(0, 0, 0, 0.2) 100%), rgba(25, 22, 18, 0.85); padding: 15px; border-radius: 10px; margin-top: 15px; margin-bottom: 0; border: 2px solid #888; box-shadow: 0 0 20px rgba(244, 208, 63, 0.2), 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 2px rgba(255, 255, 255, 0.15);">
    <div style="color: #a8a8a8; font-size: 19px; margin-bottom: 5px;">
        <strong style="color: #FFF176; text-shadow: 0 0 10px rgba(255, 241, 118, 0.9), 0 0 20px rgba(244, 208, 63, 0.7), 0 0 30px rgba(244, 208, 63, 0.4); letter-spacing: 2px; font-size: 20px;">TELOS</strong>
    </div>
    <div class="calibrating-text" style="font-size: 19px; font-style: italic; opacity: 0.9;">
        Calibrating...
    </div>
</div>
""", unsafe_allow_html=True)
                    else:
                        # Show response with native markdown rendering
                        # Header with "TELOS" label - enhanced visibility with text shadow
                        st.markdown("""
<div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.15) 0%, rgba(255, 255, 255, 0.05) 30%, transparent 60%), linear-gradient(180deg, rgba(244, 208, 63, 0.2) 0%, rgba(244, 208, 63, 0.1) 40%, rgba(0, 0, 0, 0.2) 100%), rgba(25, 22, 18, 0.85); padding: 15px 15px 8px 15px; border-radius: 10px 10px 0 0; margin-top: 15px; margin-bottom: -1rem; border: 2px solid #F4D03F; border-bottom: none; box-shadow: 0 0 20px rgba(244, 208, 63, 0.3), 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 2px rgba(255, 255, 255, 0.15); overflow: visible; position: relative; z-index: 2;">
    <div style="color: #a8a8a8; font-size: 19px; overflow: visible; padding-top: 5px;">
        <strong style="color: #FFF176; text-shadow: 0 0 10px rgba(255, 241, 118, 0.9), 0 0 20px rgba(244, 208, 63, 0.7), 0 0 30px rgba(244, 208, 63, 0.4); letter-spacing: 2px; font-size: 20px;">TELOS</strong>
    </div>
</div>
""", unsafe_allow_html=True)

                        # Render message content inside styled container
                        # Convert markdown to HTML for proper rendering inside the div
                        html_message = self._markdown_to_html(message)

                        st.markdown(f"""
<div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 10px 15px 15px 15px; margin-top: 0; margin-bottom: 0; border: 2px solid #F4D03F; border-top: none; border-radius: 0 0 10px 10px; color: #fff; font-size: 19px; box-shadow: 0 0 15px rgba(244, 208, 63, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
    {html_message}
</div>
""", unsafe_allow_html=True)
                        # Copy button for open mode
                        render_copy_button(message, f"open_{key_prefix}_{turn_number}")

                with col_empty:
                    # Empty column for alignment
                    st.markdown("")

    def _process_streaming_turn(self, user_message: str, turn_idx: int):
        """Process a streaming turn by generating the response with TRUE streaming display.

        Uses st.write_stream() to display tokens as they arrive, reducing perceived latency
        from 15-20s to <2s for first token.
        """
        full_response = ""
        try:
            # Create a placeholder for the streaming response
            response_placeholder = st.empty()

            # Use st.write_stream() for true streaming display - shows tokens as they arrive
            # This dramatically reduces perceived latency (first token in <2s vs waiting 15-20s)
            stream_generator = self.state_manager.generate_response_stream(user_message, turn_idx)

            # st.write_stream() consumes the generator and displays tokens in real-time
            # It returns the complete response when done
            full_response = response_placeholder.write_stream(stream_generator)

            # If write_stream returned None (edge case), fall back to empty string
            if full_response is None:
                full_response = ""
                logger.warning(f"Turn {turn_idx}: write_stream returned None")

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            full_response = "I apologize, but I encountered an error generating a response. Please try again."

            # CRITICAL FIX: Update turn state on error to prevent stuck loading state
            # Without this, the turn stays in is_streaming=True with no response,
            # causing is_loading check to hide input form indefinitely
            if turn_idx < len(self.state_manager.state.turns):
                turn = self.state_manager.state.turns[turn_idx]
                turn['response'] = full_response
                turn['shown_response'] = full_response
                turn['is_streaming'] = False
                turn['is_loading'] = False
                turn['error'] = str(e)
                logger.info(f"Turn {turn_idx} marked complete with error fallback response")

        # After streaming completes, the state is already updated by generate_response_stream
        # Just trigger a rerun to show the completed response with proper styling
        st.rerun()

    def _render_math_breakdown_window(self, turn_data: Dict[str, Any]):
        """Render Math Breakdown analysis window with metrics and chat."""
        # Header with close button
        col1, col2 = st.columns([9.5, 0.5])
        with col1:
            st.markdown("""
            <div style="
                background-color: #2d2d2d;
                border: 1px solid #F4D03F;
                border-radius: 10px;
                padding: 19px;
                margin-bottom: 15px;
            ">
                <div style="color: #F4D03F; font-size: 19px; font-weight: bold; text-align: center;">
                    🔢 Math Breakdown
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button("✕", key="close_math", use_container_width=True, help="Close Math Breakdown"):
                self.state_manager.toggle_component('math_breakdown')
                st.rerun()

        # Two-column layout for calculations
        col1, col2 = st.columns(2)

        with col1:
            # Fidelity Calculation window
            st.markdown("""
            <div style="
                background-color: #1a1a1a;
                border: 1px solid #F4D03F;
                border-radius: 10px;
                padding: 15px;
                min-height: 300px;
            ">
                <p style="color: #F4D03F; font-weight: bold; font-size: 20px; margin-bottom: 15px;">📊 Fidelity Calculation</p>
                <ul style="color: #e0e0e0; line-height: 1.8;">
                    <li>Base alignment score: <span style="color: #F4D03F;">0.85</span></li>
                    <li>Context adjustment: <span style="color: #27ae60;">+0.05</span></li>
                    <li>Preference weight: <span style="color: #F4D03F;">0.92</span></li>
                    <li style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #F4D03F;">
                        <strong style="color: #F4D03F;">Final Fidelity: 0.873</strong>
                    </li>
                </ul>
                <div style="margin-top: 19px; padding: 10px; background-color: #2d2d2d; border-radius: 5px;">
                    <p style="color: #a8a8a8; font-size: 11px; margin: 0;">
                        Alignment Fidelity measures how well the response matches the user's deeper preferences and values.
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            # Distance Metrics window
            st.markdown("""
            <div style="
                background-color: #1a1a1a;
                border: 1px solid #F4D03F;
                border-radius: 10px;
                padding: 15px;
                min-height: 300px;
            ">
                <p style="color: #F4D03F; font-weight: bold; font-size: 20px; margin-bottom: 15px;">📏 Distance Metrics</p>
                <ul style="color: #e0e0e0; line-height: 1.8;">
                    <li>Semantic distance: <span style="color: #F4D03F;">0.127</span></li>
                    <li>Intent deviation: <span style="color: #F4D03F;">0.08</span></li>
                    <li>Preference alignment gap: <span style="color: #27ae60;">0.05</span></li>
                    <li style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #F4D03F;">
                        <strong style="color: #27ae60;">Status: Nominal</strong>
                    </li>
                </ul>
                <div style="margin-top: 19px; padding: 10px; background-color: #2d2d2d; border-radius: 5px;">
                    <p style="color: #a8a8a8; font-size: 11px; margin: 0;">
                        Distance metrics quantify how far the response is from the ideal aligned output.
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Chat interface with Steward handshake
        self._render_steward_chat("math_breakdown")

    def _render_counterfactual_window(self, turn_data: Dict[str, Any]):
        """Render Counterfactual Analysis window with comparison and chat."""
        # Header with close button
        col1, col2 = st.columns([9.5, 0.5])
        with col1:
            st.markdown("""
            <div style="
                background-color: #2d2d2d;
                border: 1px solid #F4D03F;
                border-radius: 10px;
                padding: 19px;
                margin-bottom: 15px;
            ">
                <div style="color: #F4D03F; font-size: 19px; font-weight: bold; text-align: center;">
                    🔀 Counterfactual Analysis
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button("✕", key="close_counterfactual", use_container_width=True, help="Close Counterfactual Analysis"):
                self.state_manager.toggle_component('counterfactual')
                st.rerun()

        # Two-column layout for comparison
        col1, col2 = st.columns(2)

        with col1:
            # Native LLM Response window
            st.markdown("""
            <div style="
                background-color: #1a1a1a;
                border: 2px solid #888;
                border-radius: 10px;
                padding: 15px;
                min-height: 350px;
            ">
                <p style="color: #a8a8a8; font-weight: bold; font-size: 20px; margin-bottom: 15px;">🤖 Native LLM Response</p>
                <div style="background-color: #2d2d2d; padding: 12px; border-radius: 5px; margin-bottom: 15px;">
                    <p style="color: #e0e0e0; font-size: 13px; line-height: 1.6; margin: 0;">
                        "Based on your question, here's a literal interpretation of what you asked.
                        The response focuses on surface-level understanding without considering your
                        underlying preferences or values."
                    </p>
                </div>
                <div style="margin-top: 15px;">
                    <p style="color: #a8a8a8; font-size: 12px; font-weight: bold; margin-bottom: 10px;">Metrics:</p>
                    <ul style="color: #e0e0e0; font-size: 12px; line-height: 1.8;">
                        <li>Alignment score: <span style="color: #FFD700;">0.65</span></li>
                        <li>Semantic distance: <span style="color: #e67e22;">0.35</span></li>
                        <li>Intent match: <span style="color: #e67e22;">72%</span></li>
                    </ul>
                </div>
                <div style="margin-top: 15px; padding: 10px; background-color: #2d2d2d; border-radius: 5px; border-left: 3px solid #888;">
                    <p style="color: #a8a8a8; font-size: 11px; margin: 0;">
                        Standard response without TELOS intervention
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            # TELOS Intervention window
            st.markdown("""
            <div style="
                background-color: #1a1a1a;
                border: 1px solid #F4D03F;
                border-radius: 10px;
                padding: 15px;
                min-height: 350px;
            ">
                <p style="color: #F4D03F; font-weight: bold; font-size: 20px; margin-bottom: 15px;">🔭 TELOS Intervention</p>
                <div style="background-color: #2d2d2d; padding: 12px; border-radius: 5px; margin-bottom: 15px;">
                    <p style="color: #e0e0e0; font-size: 13px; line-height: 1.6; margin: 0;">
                        "Understanding your deeper preferences, here's a response that aligns with your
                        values and goals. The answer considers both your explicit question and implicit
                        intent based on your interaction history."
                    </p>
                </div>
                <div style="margin-top: 15px;">
                    <p style="color: #F4D03F; font-size: 12px; font-weight: bold; margin-bottom: 10px;">Metrics:</p>
                    <ul style="color: #e0e0e0; font-size: 12px; line-height: 1.8;">
                        <li>Alignment score: <span style="color: #27ae60;">0.873</span></li>
                        <li>Semantic distance: <span style="color: #27ae60;">0.127</span></li>
                        <li>Intent match: <span style="color: #27ae60;">95%</span></li>
                    </ul>
                </div>
                <div style="margin-top: 15px; padding: 10px; background-color: #2d2d2d; border-radius: 5px; border-left: 1px solid #F4D03F;">
                    <p style="color: #27ae60; font-size: 11px; margin: 0;">
                        <strong>Improvement: +34% alignment</strong>
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Chat interface with Steward handshake
        self._render_steward_chat("counterfactual")

    def _render_primacy_attractor_window(self, turn_data: Dict[str, Any]):
        """Render Primacy Attractor window showing Purpose, Scope, Boundaries."""
        # Header with close button
        col1, col2 = st.columns([9.5, 0.5])
        with col1:
            st.markdown("""
            <div style="
                background-color: #2d2d2d;
                border: 1px solid #F4D03F;
                border-radius: 10px;
                padding: 19px;
                margin-bottom: 15px;
            ">
                <div style="color: #F4D03F; font-size: 19px; font-weight: bold; text-align: center;">
                    🎯 Primacy Attractor
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button("✕", key="close_pa", use_container_width=True, help="Close Primacy Attractor"):
                self.state_manager.toggle_component('primacy_attractor')
                st.rerun()

        # Get session info which should include primacy attractor
        session_info = self.state_manager.get_session_info()

        # Check if PA is established (convergence status from progressive extractor)
        pa_converged = getattr(self.state_manager.state, 'pa_converged', False)
        total_turns = self.state_manager.state.total_turns

        # Try to get primacy attractor from turn data or session state
        primacy_attractor = None
        all_turns = self.state_manager.get_all_turns()
        if all_turns and len(all_turns) > 0:
            # Check if first turn has primacy attractor in session data
            if hasattr(self.state_manager.state, 'turns') and self.state_manager.state.turns:
                # Look for primacy_attractor in the session's initial state
                # For Phase 2 sessions, it should be in the session metadata
                pass

        # Check if we can get it from state manager's internal session data
        primacy_attractor = getattr(self.state_manager.state, 'primacy_attractor', None)

        # Fallback: try to construct from session state
        if not primacy_attractor and 'state_manager' in st.session_state:
            # Try to access the original session data that was loaded
            primacy_attractor = st.session_state.get('primacy_attractor', None)

        # If PA not converged yet, show calibrating message
        if not pa_converged and total_turns < 10:
            st.markdown("""
            <div style="
                background-color: #1a1a1a;
                border: 2px solid #F4D03F;
                border-radius: 10px;
                padding: 30px;
                margin-top: 15px;
                text-align: center;
            ">
                <span style="color: #F4D03F; font-weight: bold; font-size: 18px;">⏳ Calibrating...</span>
                <p style="color: #e0e0e0; margin-top: 15px;">
                    TELOS is learning your intent from the conversation.<br>
                    Primacy Attractor will be established after ~10 turns.
                </p>
                <p style="color: #a8a8a8; font-size: 14px; margin-top: 10px;">
                    Turn {}/~10
                </p>
            </div>
            """.format(total_turns), unsafe_allow_html=True)
            return  # Don't show PA components yet

        # Display Primacy Attractor components
        col1, col2, col3 = st.columns(3)

        with col1:
            # Build Purpose content
            purpose_items = ""
            if primacy_attractor and 'purpose' in primacy_attractor:
                for purpose_item in primacy_attractor['purpose']:
                    purpose_items += f"<p style='margin: 8px 0; color: #e0e0e0;'>• {purpose_item}</p>"
            else:
                purpose_items = "<p style='margin: 8px 0; color: #e0e0e0;'>• Establish conversation purpose from baseline turns</p>"

            st.markdown(f"""
            <div style="
                background-color: #1a1a1a;
                border: 1px solid #F4D03F;
                border-radius: 10px;
                padding: 15px;
            ">
                <p style="color: #F4D03F; font-weight: bold; font-size: 20px; margin-bottom: 15px;">📋 Purpose</p>
                <div style="color: #e0e0e0; font-size: 13px; line-height: 1.6;">
                    {purpose_items}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            # Build Scope content
            scope_items = ""
            if primacy_attractor and 'scope' in primacy_attractor:
                for scope_item in primacy_attractor['scope']:
                    scope_items += f"<p style='margin: 8px 0; color: #e0e0e0;'>• {scope_item}</p>"
            else:
                scope_items = "<p style='margin: 8px 0; color: #e0e0e0;'>• Topics covered in baseline</p>"

            st.markdown(f"""
            <div style="
                background-color: #1a1a1a;
                border: 1px solid #F4D03F;
                border-radius: 10px;
                padding: 15px;
            ">
                <p style="color: #F4D03F; font-weight: bold; font-size: 20px; margin-bottom: 15px;">🎯 Scope</p>
                <div style="color: #e0e0e0; font-size: 13px; line-height: 1.6;">
                    {scope_items}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            # Build Boundaries content
            boundary_items = ""
            if primacy_attractor and 'boundaries' in primacy_attractor:
                for boundary_item in primacy_attractor['boundaries']:
                    boundary_items += f"<p style='margin: 8px 0; color: #e0e0e0;'>• {boundary_item}</p>"
            else:
                boundary_items = "<p style='margin: 8px 0; color: #e0e0e0;'>• Off-topic discussions</p>"

            st.markdown(f"""
            <div style="
                background-color: #1a1a1a;
                border: 1px solid #F4D03F;
                border-radius: 10px;
                padding: 15px;
            ">
                <p style="color: #F4D03F; font-weight: bold; font-size: 20px; margin-bottom: 15px;">🚧 Boundaries</p>
                <div style="color: #e0e0e0; font-size: 13px; line-height: 1.6;">
                    {boundary_items}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Status indicator
        st.markdown("""
        <div style="
            background-color: #1a1a1a;
            border: 2px solid #27ae60;
            border-radius: 10px;
            padding: 15px;
            margin-top: 15px;
            text-align: center;
        ">
            <span style="color: #27ae60; font-weight: bold; font-size: 20px;">✓ Primacy Attractor Established</span>
        </div>
        """, unsafe_allow_html=True)

        # Chat interface with Steward handshake
        self._render_steward_chat("primacy_attractor")

    def _render_steward_chat(self, window_type: str):
        """Render chat interface with Steward (auto-authenticated).

        Args:
            window_type: Type of window ('math_breakdown', 'counterfactual', 'steward')
        """
        # Get Mistral API key from Streamlit secrets or environment
        import os
        MISTRAL_API_KEY = st.secrets.get("MISTRAL_API_KEY", os.getenv("MISTRAL_API_KEY"))

        if not MISTRAL_API_KEY:
            st.error("⚠️ Mistral API key not configured. Please add to Streamlit secrets or .env")
            return

        st.markdown("---")

        # Chat interface (always active with hardcoded key)
        col1, col2 = st.columns([5, 1])
        with col1:
            user_input = st.text_input(
                "Message",
                key=f"chat_input_{window_type}",
                placeholder="Ask Steward about this analysis...",
                label_visibility="collapsed"
            )
        with col2:
            send_button = st.button("Send", key=f"send_{window_type}", use_container_width=True)

        # Handle sending message
        if send_button and user_input:
            # Initialize chat history for this window
            if f'chat_history_{window_type}' not in st.session_state:
                st.session_state[f'chat_history_{window_type}'] = []

            # Add user message
            st.session_state[f'chat_history_{window_type}'].append({
                'role': 'user',
                'content': user_input
            })

            # Generate Steward response using Mistral API
            try:
                import os
                from telos.llm.mistral_client import MistralClient

                # Get API key from Streamlit secrets or environment
                mistral_api_key = st.secrets.get("MISTRAL_API_KEY", os.getenv("MISTRAL_API_KEY"))

                if not mistral_api_key:
                    st.error("⚠️ Mistral API key not configured")
                    return

                # Initialize Mistral client
                mistral_client = MistralClient(
                    api_key=mistral_api_key,
                    model="mistral-small-latest"  # Using small - best availability
                )

                # Build Steward system prompt (same as Demo Mode)
                system_prompt = """You are Steward, the TELOS research assistant. Your role is to help users understand their TELOS governance session data.

Key responsibilities:
- Explain what happened in specific turns
- Clarify fidelity scores and metrics
- Describe interventions and why they occurred
- Help users understand drift patterns
- Keep explanations clear and concise (2-3 paragraphs max)
- Avoid deep technical jargon unless asked
- Focus on actionable insights

You have access to the current turn's data. Use it to provide grounded, specific answers."""

                # Add current turn context if available
                turn_context = ""
                if turn_data:
                    turn_context = f"""

Current Turn Data:
- Turn: {turn_data.get('turn', 'N/A')}
- Fidelity: {turn_data.get('fidelity', 'N/A')}
- Status: {turn_data.get('status_text', 'N/A')}
- Intervention: {'Yes' if turn_data.get('intervention_applied') else 'No'}
- User Input: {turn_data.get('user_input', 'N/A')[:100]}..."""

                # Build messages for API call
                steward_messages = [
                    {"role": "system", "content": system_prompt + turn_context}
                ] + st.session_state[f'chat_history_{window_type}']

                # Call Mistral API
                ai_response = mistral_client.generate(
                    messages=steward_messages,
                    max_tokens=300,  # Keep responses concise
                    temperature=0.7
                )

            except Exception as e:
                logger.error(f"Steward AI chat error: {e}")
                ai_response = f"I'm having trouble connecting right now. Could you try rephrasing your question? (Error: {type(e).__name__})"

            st.session_state[f'chat_history_{window_type}'].append({
                'role': 'assistant',
                'content': ai_response
            })

            st.rerun()

        # Display chat history
        chat_history = st.session_state.get(f'chat_history_{window_type}', [])
        if chat_history:
            st.markdown("""
            <div style="
                background-color: #1a1a1a;
                border: 1px solid #F4D03F;
                border-radius: 5px;
                padding: 10px;
                margin: 10px 0;
                max-height: 200px;
                overflow-y: auto;
            ">
            """, unsafe_allow_html=True)
            for msg in chat_history:
                # NO LABELS - clean message display without role prefixes (removed per UI refactor)
                role_color = "#27ae60" if msg['role'] == 'user' else "#F4D03F"
                st.markdown(f"""
                <div style="margin: 5px 0;">
                    <span style="color: {role_color};">{msg['content']}</span>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    def _render_metric_card(self, title: str, value: str, icon: str, description: str, value_color: str = "#F4D03F"):
        """Render a single metric card.

        Args:
            title: Metric title
            value: Metric value
            icon: Icon emoji
            description: Description text
            value_color: Color for the value
        """
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            border: 1px solid #F4D03F;
            border-radius: 8px;
            padding: 10px;
            text-align: center;
        ">
            <div style="font-size: 19px; margin-bottom: 5px;">{icon}</div>
            <div style="color: #F4D03F; font-size: 10px; font-weight: bold; margin-bottom: 5px;">
                {title}
            </div>
            <div style="
                font-size: 19px;
                font-weight: bold;
                color: {value_color};
                margin: 5px 0;
            ">
                {value}
            </div>
            <div style="color: #a8a8a8; font-size: 8px;">
                {description}
            </div>
        </div>
        """, unsafe_allow_html=True)

    def _render_conversation_history(self):
        """Render all messages up to the current turn."""
        current_turn_idx = self.state_manager.get_current_turn_index()
        all_turns = self.state_manager.get_all_turns()

        # Render all turns up to and including the current one
        for i in range(current_turn_idx + 1):
            if i < len(all_turns):
                turn = all_turns[i]

                # User message
                self._render_user_message(turn.get('user_input', ''))

                # Assistant response
                self._render_assistant_message(turn.get('response', ''))

                # Intervention indicator if applied
                if turn.get('intervention_applied', False):
                    self._render_intervention_indicator()

    def _render_input_with_scroll_toggle(self):
        """Render input area with send button - clean, simple implementation."""
        # Simple CSS for clean alignment
        st.markdown("""
        <style>
        /* Clean input styling */
        div[data-testid="stForm"] {
            background: transparent !important;
        }

        div[data-testid="stForm"] input[type="text"] {
            font-size: 19px !important;
            background-color: #2d2d2d !important;
            color: #ffffff !important;
            border: 1px solid #F4D03F !important;
        }

        div[data-testid="stForm"] button[kind="formSubmit"] {
            font-size: 19px !important;
            font-weight: bold !important;
        }

        /* Hide Streamlit's "Press Enter to submit form" message */
        div[data-testid="stForm"] small {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            overflow: hidden !important;
        }

        form small {
            display: none !important;
            visibility: hidden !important;
        }

        /* Hide any element containing form submission text */
        small:contains("Enter") {
            display: none !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # JavaScript to completely remove the form submission message
        st.components.v1.html("""
        <script>
        // Remove Streamlit's form submission message
        function hideFormMessage() {
            const allSmalls = document.querySelectorAll('small');
            allSmalls.forEach(small => {
                if (small.textContent && small.textContent.toLowerCase().includes('enter')) {
                    small.style.display = 'none';
                    small.style.visibility = 'hidden';
                    small.style.height = '0';
                    small.style.overflow = 'hidden';
                    small.remove();
                }
            });
        }

        // Run immediately
        hideFormMessage();

        // Run after a delay to catch dynamically added elements
        setTimeout(hideFormMessage, 100);
        setTimeout(hideFormMessage, 500);

        // Observe DOM changes and remove message when it appears
        const observer = new MutationObserver(hideFormMessage);
        observer.observe(document.body, { childList: true, subtree: true });
        </script>
        """, height=0)

        # Style the chat input with border (matching Demo mode style)
        st.markdown("""
        <style>
        /* Beta mode chat input styling - matches Demo mode */
        div[data-testid="stForm"] {
            border: 2px solid #F4D03F !important;
            border-radius: 10px !important;
            padding: 6px !important;
            background-color: #2d2d2d !important;
        }

        div[data-testid="stForm"] textarea {
            font-size: 18px !important;
            text-align: center !important;
            background-color: #1a1a1a !important;
            border: 1px solid #666 !important;
            color: #e0e0e0 !important;
        }

        div[data-testid="stForm"] textarea::placeholder {
            text-align: center !important;
            color: #a8a8a8 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # Enable Enter to submit (Shift+Enter already works for new line)
        st.components.v1.html("""
        <script>
        (function() {
            function setupEnterKey() {
                const textareas = window.parent.document.querySelectorAll('textarea');
                textareas.forEach(textarea => {
                    textarea.removeEventListener('keydown', handleEnterKey);
                    textarea.addEventListener('keydown', handleEnterKey);
                });
            }

            function handleEnterKey(event) {
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    const sendButton = window.parent.document.querySelector('button[kind="formSubmit"]');
                    if (sendButton) {
                        sendButton.click();
                    }
                }
            }

            setupEnterKey();
            setTimeout(setupEnterKey, 500);
        })();
        </script>
        """, height=0)

        # Check if BETA mode - apply centered layout
        active_tab = st.session_state.get('active_tab', 'DEMO')
        beta_mode = active_tab == "BETA"

        if beta_mode:
            # BETA mode: CSS to fix spacing, style buttons, and add animations
            st.markdown("""
            <style>
            /* Hide "Press Enter to submit form" hint */
            .stForm [data-testid="stFormSubmitButton"] ~ small,
            .stForm small[class*="text"],
            div[data-testid="stForm"] small {
                display: none !important;
            }

            /* AGGRESSIVE spacing removal for BETA mode bottom section */
            .main [data-testid="stVerticalBlock"] {
                gap: 0 !important;
            }

            .main [data-testid="stVerticalBlock"] > div {
                margin-bottom: 0 !important;
                padding-bottom: 0 !important;
            }

            [data-testid="element-container"] {
                margin-bottom: 0 !important;
            }

            /* Form styling - minimal margins */
            [data-testid="stForm"] {
                padding: 0 !important;
                border: none !important;
                margin-top: 8px !important;
                margin-bottom: 8px !important;
            }

            [data-testid="stForm"] > div {
                gap: 0.25rem !important;
            }

            /* Button containers - tight margins */
            .stButton {
                margin-top: 2px !important;
                margin-bottom: 2px !important;
            }

            .main .stButton button {
                margin-top: 0 !important;
                margin-bottom: 0 !important;
            }

            [data-testid="stForm"] [data-testid="column"] {
                padding: 0 !important;
            }

            [data-testid="stMarkdown"] {
                margin-bottom: 0 !important;
            }

            .main .block-container > div:last-child {
                padding-top: 0 !important;
            }

            /* ============================================ */
            /* INPUT FORM GLASSMORPHISM - Match message translucency */
            /* ============================================ */
            [data-testid="stForm"] {
                background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45) !important;
                backdrop-filter: blur(10px) !important;
                -webkit-backdrop-filter: blur(10px) !important;
                border: 2px solid #F4D03F !important;
                border-radius: 10px !important;
                padding: 15px !important;
                box-shadow: 0 0 15px rgba(244, 208, 63, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1) !important;
            }

            [data-testid="stForm"] [data-testid="stTextArea"] textarea {
                background: rgba(26, 26, 30, 0.6) !important;
                border: 1px solid rgba(244, 208, 63, 0.3) !important;
                border-radius: 8px !important;
                color: #e0e0e0 !important;
            }

            [data-testid="stForm"] [data-testid="stTextArea"] textarea:focus {
                border: 1px solid #F4D03F !important;
                box-shadow: 0 0 8px rgba(244, 208, 63, 0.3) !important;
            }

            /* ============================================ */
            /* SEND BUTTON STYLING - Gold theme            */
            /* ============================================ */
            [data-testid="stForm"] button[kind="formSubmit"],
            [data-testid="stForm"] button[type="submit"] {
                background-color: rgba(26, 26, 30, 0.8) !important;
                color: #F4D03F !important;
                border: 2px solid #F4D03F !important;
                border-radius: 8px !important;
                font-weight: bold !important;
                font-size: 20px !important;
                padding: 8px 16px !important;
                transition: all 0.2s ease !important;
                height: 50px !important;
            }

            [data-testid="stForm"] button[kind="formSubmit"]:hover,
            [data-testid="stForm"] button[type="submit"]:hover {
                background-color: #F4D03F !important;
                color: #1a1a1a !important;
                box-shadow: 0 0 12px rgba(244, 208, 63, 0.5) !important;
            }

            /* ============================================ */
            /* THINKING ANIMATION                          */
            /* ============================================ */
            @keyframes thinking-pulse {
                0%, 100% { opacity: 0.4; }
                50% { opacity: 1.0; }
            }

            .thinking-indicator {
                animation: thinking-pulse 1.5s ease-in-out infinite;
            }

            @keyframes dot-bounce {
                0%, 80%, 100% { transform: translateY(0); }
                40% { transform: translateY(-8px); }
            }

            .thinking-dots span {
                display: inline-block;
                animation: dot-bounce 1.4s infinite ease-in-out both;
            }

            .thinking-dots span:nth-child(1) { animation-delay: -0.32s; }
            .thinking-dots span:nth-child(2) { animation-delay: -0.16s; }
            .thinking-dots span:nth-child(3) { animation-delay: 0s; }

            /* ============================================ */
            /* WCAG Focus Indicators - Accessibility       */
            /* ============================================ */
            button:focus-visible,
            [role="button"]:focus-visible,
            .stButton > button:focus-visible {
                outline: 3px solid #F4D03F !important;
                outline-offset: 2px !important;
            }
            a:focus-visible {
                outline: 3px solid #F4D03F !important;
                outline-offset: 2px !important;
            }
            </style>
            """, unsafe_allow_html=True)

            # Anchor for scroll-to-input functionality
            st.markdown('<div id="beta-input-section-anchor"></div>', unsafe_allow_html=True)

            # Auto-scroll to input when Scroll View is enabled
            if st.session_state.get('scroll_view_just_enabled', False):
                st.session_state.scroll_view_just_enabled = False  # Clear flag
                import streamlit.components.v1 as scroll_components
                scroll_components.html("""
<script>
    // Scroll to the input section anchor
    setTimeout(function() {
        var anchor = window.parent.document.getElementById('beta-input-section-anchor');
        if (anchor) {
            anchor.scrollIntoView({behavior: 'smooth', block: 'start'});
        } else {
            // Fallback: scroll to bottom of page
            window.parent.document.documentElement.scrollTo({
                top: window.parent.document.documentElement.scrollHeight,
                behavior: 'smooth'
            });
        }
    }, 150);
</script>
""", height=0)

            # BETA mode: Stacked layout - text area on top, send button below
            # This gives more space and avoids horizontal spacing issues
            with st.form(key="message_form", clear_on_submit=True):
                # Text area takes full width
                user_input = st.text_area(
                    "Message",
                    placeholder="",
                    key="main_chat_input_clean",
                    label_visibility="collapsed",
                    height=80
                )

                # Send button below the text area - full width, styled with gold theme
                send_button = st.form_submit_button(
                    "Send",
                    use_container_width=True
                )

            # Add JavaScript for Enter key submission, auto-expanding textarea, and Send button disabling
            import streamlit.components.v1 as components
            components.html("""
            <script>
            setTimeout(function() {
                // Helper function to find associated Send button for a textarea
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

                // Helper function to update button disabled state
                function updateSendButtonState(textarea) {
                    const btn = findSendButton(textarea);
                    if (btn) {
                        const isEmpty = !textarea.value || !textarea.value.trim();
                        btn.disabled = isEmpty;
                        btn.style.opacity = isEmpty ? '0.5' : '1';
                        btn.style.cursor = isEmpty ? 'not-allowed' : 'pointer';
                    }
                }

                const textareas = window.parent.document.querySelectorAll('textarea');
                textareas.forEach(function(textarea) {
                    // Initial state check for Send button
                    updateSendButtonState(textarea);

                    // Auto-expand functionality
                    if (!textarea.dataset.autoExpand) {
                        textarea.dataset.autoExpand = 'true';
                        textarea.style.overflow = 'hidden';
                        textarea.style.minHeight = '50px';
                        textarea.style.resize = 'none';

                        function autoResize() {
                            textarea.style.height = 'auto';
                            textarea.style.height = Math.max(50, textarea.scrollHeight) + 'px';
                        }

                        textarea.addEventListener('input', autoResize);
                        autoResize(); // Initial resize
                    }

                    // Monitor input changes to update button state
                    if (!textarea.dataset.emptyCheckHandler) {
                        textarea.dataset.emptyCheckHandler = 'true';
                        textarea.addEventListener('input', function() {
                            updateSendButtonState(textarea);
                        });
                    }

                    // Enter key submission (Shift+Enter for new line)
                    if (!textarea.dataset.chatEnterHandler) {
                        textarea.dataset.chatEnterHandler = 'true';
                        textarea.addEventListener('keydown', function(e) {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                // Prevent submission if input is empty
                                if (!textarea.value || !textarea.value.trim()) {
                                    e.preventDefault();
                                    return;
                                }
                                e.preventDefault();
                                // Find the Send button within the same form as this textarea
                                const btn = findSendButton(textarea);
                                if (btn && !btn.disabled) {
                                    btn.click();
                                    return;
                                }
                                // Fallback: find first enabled Send button on page
                                const buttons = window.parent.document.querySelectorAll('button');
                                for (let btn of buttons) {
                                    const text = btn.textContent || btn.innerText;
                                    if (text.includes('Send') && !btn.disabled) {
                                        btn.click();
                                        break;
                                    }
                                }
                            }
                        });
                    }
                });
            }, 300);
            </script>
            """, height=0)
        else:
            # Demo/Open mode: Full-width input form
            # Use a form to enable Enter key submission
            with st.form(key="message_form", clear_on_submit=True):
                # File upload section
                file_handler = get_file_handler()

                # Upload files
                uploaded_files = st.file_uploader(
                    "📎 Attach files (drag & drop or click)",
                    type=None,  # Allow all types
                    accept_multiple_files=True,
                    key="file_upload_main",
                    help="Upload PDFs, images, documents, code files, spreadsheets (max 10MB each)"
                )

                # Process uploaded files
                processed_files = []
                if uploaded_files:
                    for uploaded_file in uploaded_files:
                        file_info = file_handler.process_uploaded_file(uploaded_file)
                        processed_files.append(file_info)

                        # Show file status
                        if file_info.get('success'):
                            file_name = file_info['name']
                            file_size = file_info['size']
                            if file_size < 1024:
                                size_str = f"{file_size}B"
                            elif file_size < 1024 * 1024:
                                size_str = f"{file_size / 1024:.1f}KB"
                            else:
                                size_str = f"{file_size / 1024 / 1024:.1f}MB"

                            # File icon
                            if file_info.get('is_image'):
                                icon = "🖼️"
                            elif file_info['type'] == 'application/pdf':
                                icon = "📄"
                            elif 'spreadsheet' in file_info['type'] or file_name.endswith(('.csv', '.xlsx')):
                                icon = "📊"
                            elif 'word' in file_info['type'] or file_name.endswith(('.doc', '.docx')):
                                icon = "📝"
                            else:
                                icon = "📎"

                            st.success(f"{icon} {file_name} ({size_str})")
                        else:
                            st.error(f"❌ {file_info.get('name', 'Unknown')}: {file_info.get('error')}")

                # Text input and send button
                col1, col2 = st.columns([8.5, 1.5])

                with col1:
                    user_input = st.text_area(
                        "Message",
                        placeholder="Tell TELOS" + (" (files attached)" if processed_files else ""),
                        key="main_chat_input_clean",
                        label_visibility="collapsed",
                        height=100
                    )

                with col2:
                    send_button = st.form_submit_button(
                        "Send",
                        use_container_width=True
                    )

                # Store processed files in session state for submission
                if processed_files:
                    st.session_state.pending_files = processed_files

            # Add JavaScript to submit form on Enter key (Shift+Enter for new line) for Demo/Open mode
            # Also disable Send buttons when input is empty
            import streamlit.components.v1 as components
            components.html("""
            <script>
            setTimeout(function() {
                // Helper function to find associated Send button for a textarea
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

                // Helper function to update button disabled state
                function updateSendButtonState(textarea) {
                    const btn = findSendButton(textarea);
                    if (btn) {
                        const isEmpty = !textarea.value || !textarea.value.trim();
                        btn.disabled = isEmpty;
                        btn.style.opacity = isEmpty ? '0.5' : '1';
                        btn.style.cursor = isEmpty ? 'not-allowed' : 'pointer';
                    }
                }

                const textareas = window.parent.document.querySelectorAll('textarea');
                textareas.forEach(function(textarea) {
                    // Initial state check
                    updateSendButtonState(textarea);

                    // Monitor input changes to update button state
                    if (!textarea.dataset.emptyCheckHandler) {
                        textarea.dataset.emptyCheckHandler = 'true';
                        textarea.addEventListener('input', function() {
                            updateSendButtonState(textarea);
                        });
                    }

                    if (!textarea.dataset.chatEnterHandler) {
                        textarea.dataset.chatEnterHandler = 'true';
                        textarea.addEventListener('keydown', function(e) {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                // Prevent submission if input is empty
                                if (!textarea.value || !textarea.value.trim()) {
                                    e.preventDefault();
                                    return;
                                }
                                e.preventDefault();
                                // Find the Send button within the same form as this textarea
                                const btn = findSendButton(textarea);
                                if (btn && !btn.disabled) {
                                    btn.click();
                                    return;
                                }
                                // Fallback: find first enabled Send button on page
                                const buttons = window.parent.document.querySelectorAll('button');
                                for (let btn of buttons) {
                                    const text = btn.textContent || btn.innerText;
                                    if (text.includes('Send') && !btn.disabled) {
                                        btn.click();
                                        break;
                                    }
                                }
                            }
                        });
                    }
                });
            }, 300);
            </script>
            """, height=0)

        # Check if Demo Mode and enforce 5-message limit
        demo_mode = st.session_state.get('telos_demo_mode', False)

        # Initialize demo message counter
        if 'demo_message_count' not in st.session_state:
            st.session_state.demo_message_count = 0

        # Show warning at message 4 in Demo Mode
        if demo_mode and st.session_state.demo_message_count == 4:
            st.warning("⚠️ One message remaining in Demo Mode. Add your API key to continue unlimited usage.")

        # Block at message 5 in Demo Mode
        if demo_mode and st.session_state.demo_message_count >= 5:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
                border: 1px solid #F4D03F;
                border-radius: 15px;
                padding: 25px;
                margin: 19px 0;
                box-shadow: 0 0 6px rgba(255, 215, 0, 0.3);
                text-align: center;
            ">
                <div style="font-size: 48px; margin-bottom: 15px;">🔒</div>
                <div style="color: #F4D03F; font-size: 24px; font-weight: bold; margin-bottom: 15px;">
                    Demo Limit Reached
                </div>
                <div style="color: #e0e0e0; font-size: 19px; line-height: 1.6; margin-bottom: 19px;">
                    You've reached the 5-message demo limit.<br>
                    Add your Anthropic API key to continue with unlimited TELOS governance.
                </div>
                <div style="color: #a8a8a8; font-size: 20px; margin-top: 19px;">
                    Click "Exit Demo Mode" in the sidebar to add your API key →
                </div>
            </div>
            """, unsafe_allow_html=True)
            return  # Stop rendering input form

        # Handle sending message
        if send_button and user_input and user_input.strip():
            # Dismiss intro if showing
            if 'show_intro' in st.session_state and st.session_state.show_intro:
                st.session_state.show_intro = False

            # Increment demo message counter in Demo Mode
            if demo_mode:
                st.session_state.demo_message_count += 1

            # CRITICAL: Clear demo data on first user message to prevent contamination
            # Demo data should NOT be part of primacy attractor calibration
            # ONLY clear demo data if in Demo Mode - Beta mode starts fresh already
            if 'user_started_conversation' not in st.session_state and demo_mode:
                # This is the user's first message in DEMO mode - clear ALL demo data
                self.state_manager.clear_demo_data()
                st.session_state.user_started_conversation = True

            # Get any pending files from session state
            pending_files = st.session_state.get('pending_files', [])

            # Build message with file context if files attached
            message_text = user_input.strip()
            if pending_files:
                file_handler = get_file_handler()
                file_context = file_handler.format_file_context(pending_files)
                message_text = message_text + file_context

                # Store file metadata in message
                st.session_state.last_message_files = pending_files

            # Clear pending files
            if 'pending_files' in st.session_state:
                del st.session_state.pending_files

            # Add the user message and get turn index
            turn_idx = self.state_manager.add_user_message_streaming(message_text)

            # Show user message immediately
            st.rerun()

    def _render_chat_input(self):
        """Render chat input box for new messages."""
        # Chat input with custom styling
        user_input = st.chat_input(
            "Tell TELOS",
            key="chat_input_box"
        )

        if user_input:
            # Add the message to the conversation
            self.state_manager.add_user_message(user_input)
            st.rerun()

    def _render_expanded_analysis(self, turn_data: Dict[str, Any]):
        """Render expanded analysis sections based on toggle states.

        Args:
            turn_data: Current turn data dictionary
        """
        # Check if any toggles are enabled
        if self.state_manager.state.show_math_breakdown:
            st.markdown("---")
            self._render_chat_window("Math Breakdown", "🔢")

        if self.state_manager.state.show_counterfactual:
            st.markdown("---")
            self._render_chat_window("Counterfactual Analysis", "🔀")

        if self.state_manager.state.show_steward:
            st.markdown("---")
            st.markdown("### 👤 Steward Details")
            st.info("Steward information would appear here")

    def _render_chat_window(self, title: str, icon: str):
        """Render a chat-style window for analysis.

        Args:
            title: Window title
            icon: Icon emoji
        """
        # Header with steward icon
        col1, col2 = st.columns([10, 1])
        with col1:
            st.markdown(f"### {icon} {title}")
        with col2:
            if st.button("👤", key=f"steward_{title}", help="Consult Steward"):
                st.info("Steward consultation feature coming soon")

        # Chat window container with content
        with st.container():
            st.markdown("""
            <div style="
                background-color: #2d2d2d;
                border: 1px solid #F4D03F;
                border-radius: 10px;
                padding: 15px;
                min-height: 200px;
                max-height: 400px;
                overflow-y: auto;
                margin-bottom: 10px;
            ">
            """, unsafe_allow_html=True)

            # Sample analysis content
            if title == "Math Breakdown":
                st.markdown("""
                <div style="color: #e0e0e0; padding: 10px;">
                    <p style="color: #F4D03F; font-weight: bold;">Fidelity Calculation:</p>
                    <ul style="color: #e0e0e0;">
                        <li>Base alignment score: 0.85</li>
                        <li>Context adjustment: +0.05</li>
                        <li>Preference weight: 0.92</li>
                        <li style="color: #F4D03F;"><strong>Final Fidelity: 0.873</strong></li>
                    </ul>
                    <p style="color: #F4D03F; font-weight: bold; margin-top: 15px;">Distance Metrics:</p>
                    <ul style="color: #e0e0e0;">
                        <li>Semantic distance: 0.127</li>
                        <li>Intent deviation: 0.08</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
            elif title == "Counterfactual Analysis":
                st.markdown("""
                <div style="color: #e0e0e0; padding: 10px;">
                    <p style="color: #F4D03F; font-weight: bold;">Without TELOS Intervention:</p>
                    <ul style="color: #e0e0e0;">
                        <li>Expected response would focus on literal interpretation</li>
                        <li>Alignment score: 0.65 (lower)</li>
                    </ul>
                    <p style="color: #F4D03F; font-weight: bold; margin-top: 15px;">With TELOS Intervention:</p>
                    <ul style="color: #e0e0e0;">
                        <li>Response adapted to user's deeper preferences</li>
                        <li>Alignment score: 0.873 (higher)</li>
                        <li style="color: #27ae60;"><strong>Improvement: +34%</strong></li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

            # Chat input integrated into the window
            analysis_input = st.chat_input(
                f"Ask about {title.lower()}...",
                key=f"chat_{title.replace(' ', '_')}"
            )

            if analysis_input:
                st.info(f"Analysis chat feature coming soon. You asked: {analysis_input}")

    def _show_beta_phase_transition(self, turn_number: int):
        """Show phase transition message when PA calibration completes at turn 11.

        REMOVED for Beta MVP - cluttered the UI. Just let conversation flow naturally.
        """
        # Feature disabled for cleaner Beta UI
        pass

    def _render_beta_interaction_buttons(self, turn_number: int):
        """Render interaction buttons (Ask Steward why, Shift Focus) - NO thumbs feedback."""
        if turn_number < 1:
            return

        if not st.session_state.get('beta_consent_given', False):
            return

        # Skip rendering during loading/calculating state to prevent ghost UI elements
        is_loading = st.session_state.get('is_loading', False)
        if is_loading:
            return

        # Skip for comparison mode turns
        turn_idx = turn_number - 1
        if hasattr(self.state_manager.state, 'turns') and turn_idx < len(self.state_manager.state.turns):
            turn_data = self.state_manager.state.turns[turn_idx]
            if turn_data.get('comparison_mode', False):
                return

        st.markdown("<div style='margin: 15px 0;'></div>", unsafe_allow_html=True)

        # Check if this turn has fidelity below Aligned zone - show "Ask Steward why" button
        from telos_observatory.config.colors import _ZONE_ALIGNED, _ZONE_MINOR_DRIFT, _ZONE_DRIFT
        show_steward_button = False
        user_fidelity = None

        # Check for beta mode turn data
        beta_turn_data = st.session_state.get(f'beta_turn_{turn_number}_data', {})
        has_beta_data = bool(beta_turn_data)
        has_state_turns = hasattr(self.state_manager.state, 'turns') and turn_idx < len(self.state_manager.state.turns)

        if has_beta_data or has_state_turns:
            # Try multiple sources for user_fidelity
            telos_analysis = beta_turn_data.get('telos_analysis', {})
            user_fidelity = telos_analysis.get('display_user_pa_fidelity')

            if user_fidelity is None:
                user_fidelity = telos_analysis.get('user_pa_fidelity')

            if user_fidelity is None and has_state_turns:
                turn_data_direct = self.state_manager.state.turns[turn_idx]
                user_fidelity = turn_data_direct.get('display_fidelity') or turn_data_direct.get('user_pa_fidelity')

                if user_fidelity is None:
                    ps_metrics = turn_data_direct.get('ps_metrics', {})
                    user_fidelity = ps_metrics.get('f_user')

                if user_fidelity is None:
                    beta_data_nested = turn_data_direct.get('beta_data', {})
                    user_fidelity = beta_data_nested.get('user_fidelity') or beta_data_nested.get('input_fidelity')

                if user_fidelity is None:
                    nested_telos = turn_data_direct.get('telos_analysis', {})
                    user_fidelity = nested_telos.get('display_user_pa_fidelity') or nested_telos.get('user_pa_fidelity')

            if user_fidelity is None and has_beta_data:
                user_fidelity = beta_turn_data.get('display_fidelity') or beta_turn_data.get('user_fidelity')

            # NOTE: All interaction buttons (Ask Steward why, Shift Focus) are now only shown
            # in the Alignment Lens panel (beta_observation_deck.py) - removed from main
            # conversation space to keep it clean
            pass

    def _render_beta_feedback(self, turn_number: int):
        """Render simple beta feedback UI (thumbs up/down/sideways) for all turns."""
        # Show feedback immediately - PA is established before turn 1
        if turn_number < 1:
            return

        if not st.session_state.get('beta_consent_given', False):
            return

        # Skip rendering during loading/calculating state to prevent ghost UI elements
        is_loading = st.session_state.get('is_loading', False)
        if is_loading:
            return

        # Skip thumbs feedback for comparison mode turns (A/B has its own Choose A/B buttons)
        turn_idx = turn_number - 1
        if hasattr(self.state_manager.state, 'turns') and turn_idx < len(self.state_manager.state.turns):
            turn_data = self.state_manager.state.turns[turn_idx]
            if turn_data.get('comparison_mode', False):
                return  # Skip - comparison mode uses Choose A/B buttons instead

        feedback_key = f"beta_feedback_{turn_number}"

        st.markdown("<div style='margin: 15px 0;'></div>", unsafe_allow_html=True)

        # Center the feedback buttons below the TELOS response
        col_left, col1, col2, col3, col_right = st.columns([3, 1, 1, 1, 3])

        # If feedback already given, show thank you in the same spot as buttons
        if st.session_state.get(feedback_key):
            with col1:
                st.empty()
            with col2:
                st.markdown("""
                <div style="color: #27ae60; font-size: 14px; text-align: center; white-space: nowrap;">
                    ✓ Thanks!
                </div>
                """, unsafe_allow_html=True)
            with col3:
                st.empty()
            return

        with col1:
            if st.button("👍", key=f"thumbs_up_{turn_number}",
                        use_container_width=True, help="Helpful response"):
                self._record_simple_feedback(turn_number, "thumbs_up")
                st.session_state[feedback_key] = True
                st.rerun()

        with col2:
            if st.button("🤷", key=f"sideways_{turn_number}",
                        use_container_width=True, help="Neutral / No preference"):
                self._record_simple_feedback(turn_number, "sideways")
                st.session_state[feedback_key] = True
                st.rerun()

        with col3:
            if st.button("👎", key=f"thumbs_down_{turn_number}",
                        use_container_width=True, help="Not helpful"):
                self._record_simple_feedback(turn_number, "thumbs_down")
                st.session_state[feedback_key] = True
                st.rerun()

        # NOTE: "Ask Steward why" and "Shift Focus" buttons are rendered by
        # _render_beta_interaction_buttons() - not here to avoid duplication

    def _record_simple_feedback(self, turn_number: int, rating: str):
        """Record simple feedback to session state and beta session manager."""
        from datetime import datetime
        import logging
        logger = logging.getLogger(__name__)

        if 'beta_feedback' not in st.session_state:
            st.session_state.beta_feedback = []

        # Get turn data to extract beta information
        turn_idx = turn_number - 1  # Convert to 0-based index
        turn_data = None
        if hasattr(self.state_manager.state, 'turns') and turn_idx < len(self.state_manager.state.turns):
            turn_data = self.state_manager.state.turns[turn_idx]

        feedback_item = {
            'turn': turn_number,
            'rating': rating,
            'timestamp': datetime.now().isoformat()
        }

        # Add beta-specific data if available
        if turn_data and 'beta_data' in turn_data:
            beta_data = turn_data['beta_data']
            feedback_item['test_condition'] = beta_data.get('test_condition')
            feedback_item['response_source'] = beta_data.get('shown_response_source')
            feedback_item['baseline_fidelity'] = beta_data.get('baseline_fidelity')
            feedback_item['telos_fidelity'] = beta_data.get('telos_fidelity')
            logger.info(f"Beta feedback includes: test_condition={feedback_item['test_condition']}, source={feedback_item['response_source']}")

        st.session_state.beta_feedback.append(feedback_item)

        # Record to beta session manager if available
        beta_session = st.session_state.get('beta_session')
        if beta_session:
            try:
                from observatory.beta_testing.beta_session_manager import FeedbackData

                # DELTA-ONLY: Store lengths, not content
                user_input = turn_data.get('user_input', '') if turn_data else ''
                response = turn_data.get('response', '') if turn_data else ''
                beta_data = turn_data.get('beta_data', {}) if turn_data else {}

                feedback_data = FeedbackData(
                    turn_number=turn_number,
                    timestamp=feedback_item['timestamp'],
                    test_condition=feedback_item.get('test_condition', 'unknown'),
                    rating=rating,
                    response_source=feedback_item.get('response_source'),
                    user_message_length=len(user_input),
                    response_length=len(response),
                    fidelity=feedback_item.get('telos_fidelity'),
                    baseline_fidelity=feedback_item.get('baseline_fidelity'),
                    telos_fidelity=feedback_item.get('telos_fidelity'),
                    fidelity_delta=beta_data.get('fidelity_delta'),
                    drift_detected=beta_data.get('drift_detected', False)
                )

                beta_session.feedback_items.append(feedback_data)
                logger.info(f"✓ Feedback recorded to beta session manager")
            except Exception as e:
                logger.warning(f"Could not record to beta session manager: {e}")

        # Set start time on first feedback
        if len(st.session_state.beta_feedback) == 1:
            st.session_state.beta_start_time = datetime.now().isoformat()

        logger.info(f"Beta feedback: turn {turn_number} = {rating}")

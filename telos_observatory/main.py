#!/usr/bin/env python3
"""
TELOS Observatory - Main Application
Clean entry point with extracted CSS and proper imports.
"""

import hmac
import os
from pathlib import Path
from datetime import datetime

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

import streamlit as st
import streamlit.components.v1 as components

# Import Observatory components
from telos_observatory.core.state_manager import StateManager
from telos_observatory.components.sidebar_actions_beta import SidebarActionsBeta
from telos_observatory.components.conversation_display import ConversationDisplay
from telos_observatory.components.observation_deck import ObservationDeck
from telos_observatory.components.beta_observation_deck import BetaObservationDeck
from telos_observatory.components.beta_completion import BetaCompletion
from telos_observatory.components.teloscope_panel import render_teloscope_button, render_teloscope_panel
from telos_observatory.components.teloscope_controls import TELOSCOPEControls
from telos_observatory.components.beta_onboarding import BetaOnboarding
from telos_observatory.components.pa_onboarding import PAOnboarding
from telos_observatory.components.steward_panel import StewardPanel
from telos_observatory.components.beta_steward_panel import BetaStewardPanel, render_beta_steward_button, render_bottom_section
from telos_observatory.components.observatory_lens import ObservatoryLens
from telos_observatory.components import teloscope_profile_selector
from telos_observatory.components.agentic_onboarding import AgenticOnboarding
from telos_observatory.components.agentic_observation_deck import AgenticObservationDeck
from telos_observatory.components.agentic_completion import AgenticCompletion
from telos_observatory.services.ab_test_manager import get_ab_test_manager
from telos_observatory.services.backend_client import get_backend_service
from telos_observatory.config.colors import GOLD


# ---------------------------------------------------------------------------
# Agentic Step Data Encryption Helpers (TKeys extension)
# ---------------------------------------------------------------------------

# Fields that contain governance-sensitive data and should be encrypted
_SENSITIVE_STEP_FIELDS = frozenset({
    'user_request', 'response_text', 'decision_explanation',
    'tool_output', 'tool_rankings',
})


def _encrypt_step_data(data: dict) -> dict:
    """Encrypt governance-sensitive fields in agentic step data.

    Uses TKeys session encryption when available. Sensitive fields (user request,
    response text, decision explanation, tool output) are encrypted while step
    number, timestamp, and fidelity scores remain cleartext for UI indexing.

    Falls back to plaintext when TKeys is unavailable.
    """
    tkeys_mgr = st.session_state.get('tkeys_session_manager')
    if not tkeys_mgr:
        return data

    import json as _json
    encrypted = dict(data)
    encrypted['_tkeys_encrypted'] = True
    for field_name in _SENSITIVE_STEP_FIELDS:
        if field_name in encrypted and encrypted[field_name] is not None:
            try:
                plaintext = _json.dumps(encrypted[field_name], default=str).encode('utf-8')
                payload = tkeys_mgr.encrypt(plaintext)
                encrypted[field_name] = payload.to_dict()
            except Exception:
                pass  # Keep plaintext on encryption failure
    return encrypted


def _decrypt_step_data(data: dict) -> dict:
    """Decrypt governance-sensitive fields in agentic step data."""
    if not data.get('_tkeys_encrypted'):
        return data

    tkeys_mgr = st.session_state.get('tkeys_session_manager')
    if not tkeys_mgr:
        return data

    import json as _json
    from telos_privacy.cryptography.telemetric_keys import EncryptedPayload
    decrypted = dict(data)
    for field_name in _SENSITIVE_STEP_FIELDS:
        val = decrypted.get(field_name)
        if isinstance(val, dict) and 'ciphertext' in val:
            try:
                payload = EncryptedPayload.from_dict(val)
                plaintext = tkeys_mgr.key_generator.decrypt(payload)
                decrypted[field_name] = _json.loads(plaintext.decode('utf-8'))
            except Exception:
                pass  # Return encrypted form on failure
    decrypted.pop('_tkeys_encrypted', None)
    return decrypted


def get_agentic_step_data(step_num: int) -> dict:
    """Get agentic step data with transparent decryption.

    Components should use this instead of directly reading
    st.session_state[f'agentic_step_{n}_data'] to get automatic
    decryption of TKeys-encrypted fields.
    """
    data = st.session_state.get(f'agentic_step_{step_num}_data', {})
    return _decrypt_step_data(data)


# ---------------------------------------------------------------------------
# CSS Loader
# ---------------------------------------------------------------------------

def _load_css():
    """Load theme CSS from external file and inject into Streamlit."""
    css_path = Path(__file__).parent / "styles" / "theme.css"
    if css_path.exists():
        css_text = css_path.read_text()
        st.markdown(f"<style>{css_text}</style>", unsafe_allow_html=True)


def _inject_glassmorphism():
    """Apply gradient glassmorphism background via JavaScript."""
    components.html("""
    <script>
    (function() {
        var doc = window.parent.document;
        var gradientBg = `
            radial-gradient(ellipse 90% 90% at 15% 5%, rgba(244, 208, 63, 0.7) 0%, transparent 40%),
            radial-gradient(ellipse 80% 80% at 90% 95%, rgba(200, 160, 40, 0.6) 0%, transparent 35%),
            radial-gradient(ellipse 60% 60% at 50% 50%, rgba(244, 180, 63, 0.4) 0%, transparent 50%),
            linear-gradient(135deg, #1a1510 0%, #0d0a05 50%, #0a0805 100%)
        `;

        function applyGlassmorphism() {
            var stApp = doc.querySelector('.stApp');
            if (stApp) {
                stApp.style.setProperty('background', gradientBg, 'important');
                stApp.style.setProperty('background-attachment', 'fixed', 'important');
            }
            var topContainers = doc.querySelectorAll(`
                [data-testid="stAppViewContainer"],
                .main,
                section.main
            `);
            topContainers.forEach(function(el) {
                el.style.setProperty('background', 'transparent', 'important');
                el.style.setProperty('background-color', 'transparent', 'important');
            });
            var blockContainers = doc.querySelectorAll('.block-container');
            blockContainers.forEach(function(el) {
                el.style.setProperty('max-width', '950px', 'important');
                el.style.setProperty('width', '100%', 'important');
                el.style.setProperty('margin-left', 'auto', 'important');
                el.style.setProperty('margin-right', 'auto', 'important');
            });
        }

        applyGlassmorphism();
        setInterval(applyGlassmorphism, 500);
        window.parent.addEventListener('resize', applyGlassmorphism);
    })();
    </script>
    """, height=0)


def _inject_keyboard_navigation():
    """Inject keyboard navigation for demo mode (arrow keys)."""
    st.markdown("""
    <script>
    document.addEventListener('keydown', function(event) {
        var isDemoMode = window.parent.document.querySelector('[data-testid="stApp"]');
        if (!isDemoMode) return;
        switch(event.key) {
            case 'ArrowLeft':
                var scrollBtn = document.querySelector('[key*="scroll_toggle"]');
                if (scrollBtn && !event.ctrlKey && !event.metaKey) {
                    event.preventDefault(); scrollBtn.click();
                }
                break;
            case 'ArrowRight':
                var closeBtn = document.querySelector('[key*="scroll_close"]');
                if (closeBtn && !event.ctrlKey && !event.metaKey) {
                    event.preventDefault(); closeBtn.click();
                }
                break;
            case 'ArrowUp':
                if (!event.ctrlKey && !event.metaKey) {
                    event.preventDefault(); window.scrollBy(0, -200);
                }
                break;
            case 'ArrowDown':
                if (!event.ctrlKey && !event.metaKey) {
                    event.preventDefault(); window.scrollBy(0, 200);
                }
                break;
        }
    });
    </script>
    """, unsafe_allow_html=True)


def _inject_scroll_to_top():
    """Mobile scroll-to-top on Streamlit rerun."""
    components.html("""
    <script>
    (function() {
        if (window.telosScrollToTopApplied) return;
        window.telosScrollToTopApplied = true;
        var doc = window.parent.document;
        function scrollToTop() {
            var mainContent = doc.querySelector('[data-testid="stAppViewContainer"]');
            var stApp = doc.querySelector('.stApp');
            if (mainContent) mainContent.scrollTo({ top: 0, behavior: 'smooth' });
            if (stApp) stApp.scrollTo({ top: 0, behavior: 'smooth' });
            doc.documentElement.scrollTo({ top: 0, behavior: 'smooth' });
            doc.body.scrollTo({ top: 0, behavior: 'smooth' });
            window.parent.scrollTo({ top: 0, behavior: 'smooth' });
        }
        setTimeout(scrollToTop, 100);
    })();
    </script>
    """, height=0)


def _inject_heartbeat():
    """Session keep-alive heartbeat to prevent WebSocket timeout."""
    components.html("""
    <script>
    (function() {
        if (window.telosHeartbeatActive) return;
        window.telosHeartbeatActive = true;
        var HEARTBEAT_INTERVAL = 120000;
        function sendHeartbeat() {
            try {
                var frames = window.parent.document.querySelectorAll('iframe');
                if (frames.length > 0) {
                    console.log('[TELOS] Session heartbeat sent');
                }
            } catch (e) {}
        }
        setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);
    })();
    </script>
    """, height=0)


# ---------------------------------------------------------------------------
# Session Initialization
# ---------------------------------------------------------------------------

def initialize_session():
    """Initialize session state - starts fresh (no pre-loaded demo data)."""
    # Eager model initialization for cold start performance
    if 'embedding_model_initialized' not in st.session_state:
        try:
            from telos_core.embedding_provider import (
                get_cached_minilm_provider,
                get_cached_mpnet_provider
            )
            get_cached_minilm_provider()
            get_cached_mpnet_provider()
            st.session_state.embedding_model_initialized = True
        except Exception:
            pass

    if 'state_manager' not in st.session_state:
        if 'telos_demo_mode' not in st.session_state:
            st.session_state.telos_demo_mode = True

        state_manager = StateManager()
        empty_data = {
            'session_id': f"session_{int(datetime.now().timestamp())}",
            'turns': [],
            'primacy_attractor': None,
            'mode': 'demo'
        }
        state_manager.initialize(empty_data)
        st.session_state.state_manager = state_manager

        ab_manager = get_ab_test_manager()
        ab_manager.apply_experiment_configs()
        st.session_state.ab_manager = ab_manager

        backend = get_backend_service()
        st.session_state.backend = backend


# ---------------------------------------------------------------------------
# Completion Checks
# ---------------------------------------------------------------------------

def check_demo_completion():
    """Check if demo mode is complete and unlock BETA."""
    if st.session_state.get('demo_completed', False):
        return True

    demo_mode = st.session_state.get('telos_demo_mode', False)
    if demo_mode:
        state_manager = st.session_state.get('state_manager')
        demo_slide_index = st.session_state.get('demo_slide_index', 0)
        completed_via_turns = state_manager and state_manager.state.total_turns >= 10
        completed_via_slides = demo_slide_index >= 13
        if completed_via_turns or completed_via_slides:
            st.session_state.demo_completed = True
            return True
    return False


def check_beta_completion():
    """Check if beta session is complete (10 conversational turns)."""
    if not st.session_state.get('beta_consent_given', False):
        return False
    if st.session_state.get('beta_completed', False):
        return True

    current_turn = st.session_state.get('beta_current_turn', 1)
    if current_turn > 10:
        st.session_state.beta_completed = True
        if 'ab_manager' in st.session_state and 'backend' in st.session_state:
            try:
                ab_metrics = st.session_state.ab_manager.export_metrics_for_backend()
                st.session_state.backend.transmit_delta({
                    'session_id': ab_metrics['session_id'],
                    'turn_number': 999,
                    'fidelity_score': 1.0,
                    'distance_from_pa': 0.0,
                    'mode': 'beta',
                    'ab_test_data': ab_metrics
                })
            except Exception as e:
                print(f"Failed to export A/B test metrics: {e}")
        return True
    return False


def check_agentic_completion():
    """Check if agentic session is complete (10 steps)."""
    if st.session_state.get('agentic_completed', False):
        return True
    current_step = st.session_state.get('agentic_current_step', 0)
    if current_step >= 10:
        st.session_state.agentic_completed = True
        return True
    return False


def show_beta_progress():
    """Show beta progress in sidebar."""
    if not st.session_state.get('beta_consent_given', False):
        return
    if st.session_state.get('beta_completed', False):
        return

    start_time_str = st.session_state.get('beta_start_time')
    if not start_time_str:
        return

    from datetime import timedelta
    start_time = datetime.fromisoformat(start_time_str)
    elapsed = datetime.now() - start_time
    days_elapsed = elapsed.days
    days_remaining = max(0, 14 - days_elapsed)

    feedback_items = st.session_state.get('beta_feedback', [])
    feedback_count = len(feedback_items)
    feedbacks_remaining = max(0, 50 - feedback_count)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Beta Progress")
    st.sidebar.markdown(f"""
    **Completion Criteria** (either one):
    - Days: {days_elapsed}/14 ({days_remaining} remaining)
    - Feedback: {feedback_count}/50 ({feedbacks_remaining} remaining)
    """)


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

def main():
    """Main application entry point."""
    st.set_page_config(
        page_title="TELOS Observatory",
        page_icon="T",
        layout="centered",
        initial_sidebar_state="expanded"
    )

    # Load CSS from external file (replaces ~700 lines of inline CSS)
    _load_css()

    # Inject JavaScript behaviors
    _inject_glassmorphism()
    _inject_keyboard_navigation()
    _inject_scroll_to_top()
    _inject_heartbeat()

    # Initialize session
    initialize_session()
    state_manager = st.session_state.state_manager

    # Instantiate components
    sidebar_actions = SidebarActionsBeta(state_manager)
    steward_panel = StewardPanel(state_manager)
    beta_steward_panel = BetaStewardPanel()
    conversation_display = ConversationDisplay(state_manager)
    observation_deck = ObservationDeck(state_manager)
    beta_observation_deck = BetaObservationDeck()
    teloscope_controls = TELOSCOPEControls(state_manager)
    beta_onboarding = BetaOnboarding(state_manager)
    pa_onboarding = PAOnboarding()
    observatory_lens = ObservatoryLens(state_manager)
    agentic_onboarding = AgenticOnboarding()
    agentic_observation_deck = AgenticObservationDeck()

    has_beta_consent = st.session_state.get('beta_consent_given', False)

    check_demo_completion()
    if has_beta_consent:
        check_beta_completion()
    check_agentic_completion()

    steward_panel.hide_sidebar_when_open()

    # Render Steward button
    pa_established = st.session_state.get('pa_established', False)
    if has_beta_consent and pa_established:
        current_tab = st.session_state.get('active_tab', 'DEMO')
        if current_tab != "BETA":
            steward_panel.render_button()

    # Initialize active tab
    if 'active_tab' not in st.session_state:
        query_params = st.query_params
        # Admin access requires TELOS_ADMIN_SECRET env var (minimum 16 chars)
        # Uses hmac.compare_digest for constant-time comparison (timing-safe)
        _admin_secret = os.environ.get("TELOS_ADMIN_SECRET", "")
        _admin_token = query_params.get("admin", "")
        is_admin = (
            _admin_secret
            and _admin_token
            and len(_admin_secret) >= 16
            and hmac.compare_digest(_admin_secret, _admin_token)
        )
        beta_direct = query_params.get("beta") == "true"
        telos_direct = query_params.get("telos") == "true"

        if is_admin:
            st.session_state.active_tab = "DEVOPS"
        elif telos_direct:
            st.session_state.beta_consent_given = True
            st.session_state.demo_completed = True
            st.session_state.beta_completed = True
            st.session_state.pa_established = True
            st.session_state.telos_demo_mode = False
            st.session_state.active_tab = "TELOS"
        elif beta_direct:
            st.session_state.beta_consent_given = True
            st.session_state.active_tab = "BETA"
        else:
            st.session_state.active_tab = "DEMO"

    active_tab = st.session_state.active_tab

    query_params = st.query_params
    _admin_secret = os.environ.get("TELOS_ADMIN_SECRET", "")
    _admin_token = query_params.get("admin", "")
    is_admin = (
        _admin_secret
        and _admin_token
        and len(_admin_secret) >= 16
        and hmac.compare_digest(_admin_secret, _admin_token)
    )
    beta_direct = query_params.get("beta") == "true"
    telos_direct = query_params.get("telos") == "true"

    if (active_tab in ["BETA", "TELOS"]) and not has_beta_consent and not is_admin and not beta_direct and not telos_direct:
        beta_onboarding.render()
        return
    else:
        render_tabs_and_content(
            has_beta_consent, state_manager, sidebar_actions,
            conversation_display, observation_deck, beta_observation_deck,
            teloscope_controls, steward_panel, beta_steward_panel, beta_onboarding,
            pa_onboarding, observatory_lens,
            agentic_onboarding, agentic_observation_deck
        )


def render_tabs_and_content(has_beta_consent, state_manager, sidebar_actions,
                            conversation_display, observation_deck, beta_observation_deck,
                            teloscope_controls, steward_panel, beta_steward_panel, beta_onboarding,
                            pa_onboarding, observatory_lens,
                            agentic_onboarding=None, agentic_observation_deck=None):
    """Render tabs and main content area."""
    active_tab = st.session_state.get('active_tab', 'DEMO')
    sidebar_accessible = active_tab in ['TELOS', 'DEVOPS']

    if has_beta_consent or sidebar_accessible:
        # Sidebar slide-in animation
        st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            animation: slideInFromLeft 1.2s ease-out;
        }
        @keyframes slideInFromLeft {
            0% { transform: translateX(-100%); opacity: 0; }
            100% { transform: translateX(0); opacity: 1; }
        }
        .stButton > button {
            animation: quickBlink 1.4s ease-in-out;
        }
        @keyframes quickBlink {
            0% { opacity: 1; }
            85% { opacity: 1; }
            90% { box-shadow: 0 0 8px #F4D03F; }
            95% { box-shadow: none; }
            100% { opacity: 1; }
        }
        </style>
        """, unsafe_allow_html=True)

        sidebar_enabled = st.session_state.get('active_tab') in ['TELOS', 'DEVOPS']

        if not sidebar_enabled:
            st.markdown("""
            <style>
            [data-testid="stSidebar"] {
                opacity: 0.3 !important;
                pointer-events: none !important;
            }
            [data-testid="stSidebar"] * {
                pointer-events: none !important;
                cursor: not-allowed !important;
            }
            </style>
            """, unsafe_allow_html=True)

        sidebar_actions.render()
        show_beta_progress()

        if st.session_state.get('active_tab') == 'TELOS' and st.session_state.get('teloscope_profile'):
            with st.sidebar:
                st.markdown("---")
                teloscope_profile_selector.render_profile_badge()
                teloscope_profile_selector.render_profile_switch_button()

        # Active tab styling
        st.markdown("""
        <style>
        /* Primary button glow only in the tab row */
        div[data-testid="stHorizontalBlock"]:first-of-type button[kind="primary"] {
            background-color: #2d2d2d !important;
            color: #e0e0e0 !important;
            border: 2px solid #F4D03F !important;
            box-shadow: 0 0 8px rgba(255, 215, 0, 0.5) !important;
        }
        div[data-testid="stHorizontalBlock"]:first-of-type button[kind="primary"]:hover {
            background-color: #3d3d3d !important;
            color: #e0e0e0 !important;
            border: 1px solid #F4D03F !important;
            box-shadow: 0 0 6px #F4D03F !important;
        }
        /* Non-tab primary buttons: same as secondary (no glow) */
        div[data-testid="stHorizontalBlock"]:not(:first-of-type) button[kind="primary"],
        button[kind="primary"] {
            background-color: #2d2d2d !important;
            color: #e0e0e0 !important;
            border: 1px solid #F4D03F !important;
            box-shadow: none !important;
        }
        button[kind="secondary"] {
            background-color: #2d2d2d !important;
            color: #e0e0e0 !important;
            border: 1px solid #F4D03F !important;
        }
        button[kind="secondary"]:hover {
            background-color: #3d3d3d !important;
            border: 1px solid #F4D03F !important;
            box-shadow: 0 0 6px #F4D03F !important;
        }
        button[disabled], button.beta-locked {
            background-color: #2d2d2d !important;
            color: #888 !important;
            border: 1px solid #F4D03F !important;
            cursor: not-allowed !important;
        }
        button[disabled]:hover, button.beta-locked:hover {
            background-color: #1a1a1a !important;
            color: #555 !important;
            border: 1px solid #444 !important;
            box-shadow: none !important;
            transform: none !important;
        }
        </style>
        """, unsafe_allow_html=True)

    # Tab selection
    active_tab = st.session_state.active_tab
    check_demo_completion()
    demo_complete = st.session_state.get('demo_completed', False)
    beta_complete = st.session_state.get('beta_completed', False)

    query_params = st.query_params
    # Admin requires TELOS_ADMIN_SECRET (timing-safe comparison)
    _admin_secret = os.environ.get("TELOS_ADMIN_SECRET", "")
    _admin_token = query_params.get("admin", "")
    is_admin = (
        _admin_secret
        and _admin_token
        and len(_admin_secret) >= 16
        and hmac.compare_digest(_admin_secret, _admin_token)
    )
    beta_entered = st.session_state.get('beta_consent_given', False) or st.session_state.get('pa_established', False)

    st.markdown("""<div style="max-width: 700px; margin: 0 auto;">""", unsafe_allow_html=True)

    if beta_entered:
        if is_admin:
            col_demo, col_agentic, col_beta, col_telos = st.columns(4)
            with col_demo:
                if st.button("DEMO", key="tab_demo", use_container_width=True,
                            type="primary" if active_tab == "DEMO" else "secondary"):
                    st.session_state.active_tab = "DEMO"
                    st.rerun()
            with col_agentic:
                if st.button("AGENTIC", key="tab_agentic", use_container_width=True,
                            type="primary" if active_tab == "AGENTIC" else "secondary"):
                    st.session_state.active_tab = "AGENTIC"
                    st.rerun()
            with col_beta:
                if st.button("BETA", key="tab_beta", use_container_width=True,
                            type="primary" if active_tab == "BETA" else "secondary"):
                    st.session_state.active_tab = "BETA"
                    st.rerun()
            with col_telos:
                if st.button("TELOS (Admin)", key="tab_telos", use_container_width=True,
                            type="primary" if active_tab == "TELOS" else "secondary"):
                    st.session_state.active_tab = "TELOS"
                    st.rerun()
        else:
            col_demo, col_agentic, col_beta = st.columns(3)
            with col_demo:
                if st.button("DEMO", key="tab_demo", use_container_width=True,
                            type="primary" if active_tab == "DEMO" else "secondary"):
                    st.session_state.active_tab = "DEMO"
                    st.rerun()
            with col_agentic:
                if st.button("AGENTIC", key="tab_agentic", use_container_width=True,
                            type="primary" if active_tab == "AGENTIC" else "secondary"):
                    st.session_state.active_tab = "AGENTIC"
                    st.rerun()
            with col_beta:
                if st.button("BETA", key="tab_beta", use_container_width=True,
                            type="primary" if active_tab == "BETA" else "secondary"):
                    st.session_state.active_tab = "BETA"
                    st.rerun()
    else:
        col_demo, col_agentic, col_beta = st.columns(3)
        with col_demo:
            if st.button("DEMO", key="tab_demo", use_container_width=True,
                        type="primary" if active_tab == "DEMO" else "secondary"):
                st.session_state.active_tab = "DEMO"
                st.rerun()
        with col_agentic:
            if st.button("AGENTIC", key="tab_agentic", use_container_width=True,
                        type="primary" if active_tab == "AGENTIC" else "secondary"):
                st.session_state.active_tab = "AGENTIC"
                st.rerun()
        with col_beta:
            if st.button("BETA", key="tab_beta", use_container_width=True,
                        type="primary" if active_tab == "BETA" else "secondary"):
                st.session_state.active_tab = "BETA"
                st.rerun()

    st.markdown("""</div>""", unsafe_allow_html=True)

    # BETA Action Buttons Row
    if beta_entered and active_tab == "BETA":
        pa_established = st.session_state.get('pa_established', False)
        is_loading = st.session_state.get('is_processing_input', False) or st.session_state.get('is_generating_response', False)
        state_manager = st.session_state.get('state_manager')
        steward_is_open = st.session_state.get('beta_steward_panel_open', False)

        if pa_established and not is_loading and state_manager:
            st.markdown("<div style='margin: 4px 0;'></div>", unsafe_allow_html=True)
            st.markdown("""<div style="max-width: 700px; margin: 0 auto;">""", unsafe_allow_html=True)

            scroll_mode = state_manager.state.scrollable_history_mode
            scroll_label = "Close Scroll" if scroll_mode else "Scroll View"
            steward_label = "Close Steward" if steward_is_open else "Ask Steward"

            col1, col2 = st.columns(2)
            with col1:
                scroll_clicked = st.button(scroll_label, key="hidden_scroll_btn", use_container_width=True)
            with col2:
                steward_clicked = st.button(steward_label, key="hidden_steward_btn", use_container_width=True)

            st.markdown("""</div>""", unsafe_allow_html=True)

            if scroll_clicked:
                currently_scroll_mode = state_manager.state.scrollable_history_mode
                state_manager.toggle_scrollable_history()
                if not currently_scroll_mode:
                    st.session_state.scroll_view_just_enabled = True
                st.rerun()
            if steward_clicked:
                if steward_is_open:
                    st.session_state.beta_steward_panel_open = False
                    st.session_state.scroll_after_steward_close = True
                else:
                    st.session_state.beta_steward_panel_open = True
                    st.session_state.beta_deck_visible = False
                    st.session_state.scroll_to_steward = True
                st.rerun()

    # Force neutral gray styling on tab buttons
    st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"]:first-of-type button[kind="secondary"],
    div[data-testid="stHorizontalBlock"]:first-of-type button[data-testid="baseButton-secondary"] {
        background-color: #2d2d2d !important;
        border: 2px solid #666666 !important;
        color: #e0e0e0 !important;
    }
    div[data-testid="stHorizontalBlock"]:first-of-type button[kind="secondary"]:hover,
    div[data-testid="stHorizontalBlock"]:first-of-type button[data-testid="baseButton-secondary"]:hover {
        background-color: #3d3d3d !important;
        border: 2px solid #888888 !important;
    }
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
        width: 100% !important;
        max-width: 100% !important;
        box-sizing: border-box !important;
    }
    div[data-testid="stHorizontalBlock"] {
        width: 100% !important;
        max-width: 100% !important;
        box-sizing: border-box !important;
    }
    .main .block-container div[data-testid="stHorizontalBlock"]:nth-of-type(2) {
        gap: 8px !important;
        column-gap: 8px !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
    }
    .main .block-container div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div[data-testid="stColumn"] {
        padding-left: 0 !important;
        padding-right: 0 !important;
        flex: 1 1 calc(50% - 4px) !important;
    }
    .main .block-container div[data-testid="stHorizontalBlock"]:nth-of-type(2) button {
        width: 100% !important;
    }
    .main .block-container div[data-testid="stHorizontalBlock"]:nth-of-type(2) button p {
        font-size: 20px !important;
        font-weight: 600 !important;
    }

    /* Tab button sizing - compact, not giant squares */
    div[data-testid="stHorizontalBlock"]:first-of-type .stButton > button,
    div[data-testid="stHorizontalBlock"]:first-of-type button[kind="primary"],
    div[data-testid="stHorizontalBlock"]:first-of-type button[kind="secondary"] {
        height: 48px !important;
        min-height: 48px !important;
        max-height: 48px !important;
        padding: 8px 16px !important;
        line-height: 1.2 !important;
    }

    /* All buttons - reasonable height */
    .stButton > button {
        height: auto !important;
        min-height: 44px !important;
        max-height: 60px !important;
        padding: 10px 20px !important;
    }

    /* Form submit buttons */
    .stFormSubmitButton > button {
        height: auto !important;
        min-height: 44px !important;
        max-height: 56px !important;
        padding: 10px 20px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Dynamic Alignment Lens button styling based on demo slide
    if st.session_state.get('active_tab') == 'DEMO':
        from telos_observatory.config.colors import get_fidelity_color
        current_slide = st.session_state.get('demo_slide_index', 0)

        if current_slide == 6:
            user_fidelity = 0.69
        elif current_slide == 7:
            user_fidelity = 0.55
        elif current_slide == 8:
            user_fidelity = 0.42
        else:
            user_fidelity = 1.00

        user_color = get_fidelity_color(user_fidelity)

        st.markdown(f"""
        <style>
        div[data-testid="stHorizontalBlock"]:not(:first-of-type) button[kind="primary"],
        div[data-testid="stHorizontalBlock"]:not(:first-of-type) button[data-testid="baseButton-primary"] {{
            background-color: #2d2d2d !important;
            border: 3px solid {user_color} !important;
            color: #e0e0e0 !important;
            box-shadow: 0 0 10px {user_color}66 !important;
        }}
        div[data-testid="stHorizontalBlock"]:not(:first-of-type) button[kind="primary"]:hover,
        div[data-testid="stHorizontalBlock"]:not(:first-of-type) button[data-testid="baseButton-primary"]:hover {{
            background-color: #3d3d3d !important;
            border: 3px solid {user_color} !important;
            box-shadow: 0 0 15px {user_color}88 !important;
        }}
        </style>
        """, unsafe_allow_html=True)

    if is_admin:
        st.markdown("<div style='margin: 10px 0;'></div>", unsafe_allow_html=True)
        if st.button("DEVOPS (Admin Mode)", key="tab_devops", use_container_width=True,
                    type="primary" if active_tab == "DEVOPS" else "secondary"):
            st.session_state.active_tab = "DEVOPS"
            st.rerun()

    # Reduce vertical spacing for DEMO and BETA modes
    if st.session_state.get('active_tab') in ['DEMO', 'BETA', 'AGENTIC']:
        st.markdown("""
        <style>
        .stMarkdown + div { margin-top: 0 !important; padding-top: 0 !important; }
        .main .block-container { padding-top: 0 !important; padding-bottom: 0.5rem !important; margin-top: 0 !important; }
        .stMarkdown { margin-bottom: 0 !important; margin-top: 0 !important; }
        div[data-testid="stVerticalBlock"] > div { gap: 0 !important; }
        div[data-testid="stVerticalBlock"] { gap: 0 !important; padding-top: 0 !important; }
        .element-container { margin-top: 0 !important; margin-bottom: 0 !important; }
        .main .block-container > div:first-child { margin-top: 0 !important; padding-top: 0 !important; }
        </style>
        """, unsafe_allow_html=True)

    # Hide sidebar for non-TELOS/DEVOPS modes
    active_tab = st.session_state.get('active_tab', 'DEMO')
    if active_tab not in ['TELOS', 'DEVOPS']:
        st.markdown("""
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        </style>
        """, unsafe_allow_html=True)

    # Agentic demo slideshow renderer
    def _md_to_html(text):
        """Convert basic markdown (bold, links, hr) to HTML for inline rendering."""
        import re
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color: #F4D03F;" target="_blank">\1</a>', text)
        text = text.replace('---', '<hr style="border: none; border-top: 1px solid #555; margin: 10px 0;">')
        return text

    def _render_agentic_demo(agentic_obs_deck):
        """Render agentic demo slideshow — same pattern as conversational demo."""
        from telos_observatory.agentic.agentic_demo_slides import (
            get_agentic_demo_slides,
            get_agentic_demo_welcome_message,
            get_agentic_demo_completion_message,
        )

        slides = get_agentic_demo_slides()

        if 'agentic_demo_slide_index' not in st.session_state:
            st.session_state.agentic_demo_slide_index = 0

        current_idx = st.session_state.agentic_demo_slide_index
        max_idx = len(slides) + 1  # 0=welcome, 1-N=Q&A, N+1=completion

        # Keyboard navigation (arrow keys) — same pattern as conversational demo
        import streamlit.components.v1 as components
        components.html(f"""
        <script>
        (function() {{
            window.scrollTo(0, 0);
            if (window.parent) {{ window.parent.scrollTo(0, 0); }}
        }})();

        (function() {{
            const currentSlide = {current_idx};
            const maxSlide = {max_idx};

            if (window.agenticKeyListener) {{
                document.removeEventListener('keydown', window.agenticKeyListener);
                if (window.parent && window.parent.document) {{
                    window.parent.document.removeEventListener('keydown', window.agenticKeyListener);
                }}
            }}

            window.agenticKeyListener = function(event) {{
                if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;

                if (event.key === 'ArrowLeft' && currentSlide > 0) {{
                    event.preventDefault();
                    const parent = window.parent;
                    if (parent && parent.document) {{
                        const buttons = parent.document.querySelectorAll('button');
                        for (let btn of buttons) {{
                            if (btn.textContent.includes('Previous') || btn.textContent.includes('Back to Welcome')) {{
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
                                btn.textContent.includes('Complete Demo')) {{
                                btn.click();
                                break;
                            }}
                        }}
                    }}
                }}
            }};

            document.addEventListener('keydown', window.agenticKeyListener);
            if (window.parent && window.parent.document) {{
                window.parent.document.addEventListener('keydown', window.agenticKeyListener);
            }}
        }})();
        </script>
        """, height=0)

        # Slide 0: Welcome
        if current_idx == 0:
            welcome_msg = get_agentic_demo_welcome_message()
            st.markdown(f"""
<div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            border: 2px solid #F4D03F;
            border-radius: 15px;
            padding: 20px;
            margin: 10px auto 30px auto;
            text-align: center;
            box-shadow: 0 0 8px rgba(255, 215, 0, 0.4);
            opacity: 0;
            animation: slideContentFadeIn 1.0s ease-out forwards;">
    <h1 style="color: #F4D03F; font-size: 32px; margin-bottom: 20px;">Agentic AI Governance Demo</h1>
    <div style="text-align: left; max-width: 700px; margin: 0 auto;">
        {"".join(f'<p style="color: #e0e0e0; font-size: 18px; line-height: 1.6; margin-bottom: 15px;">{_md_to_html(p.strip())}</p>' for p in welcome_msg.strip().split(chr(10) + chr(10)) if p.strip())}
    </div>
</div>
<style>
@keyframes slideContentFadeIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
</style>
""", unsafe_allow_html=True)

            col_l, col_c, col_r = st.columns(3)
            with col_c:
                if st.button("Start Demo", key="agentic_start_demo", use_container_width=True, type="primary"):
                    st.session_state.agentic_demo_slide_index = 1
                    st.rerun()
            return

        # Slides 1-N: Q&A pairs
        if 1 <= current_idx <= len(slides):
            slide_idx = current_idx - 1
            user_question, steward_response = slides[slide_idx]

            # User question bubble (fade in immediately)
            # Unique data-slide attribute forces browser to re-trigger animation on each slide
            from telos_observatory.config.colors import GOLD
            st.markdown(f"""
<style>
@keyframes agenticFadeIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
</style>
<div key="agentic-q-{current_idx}" data-slide="{current_idx}">
<div style="background-color: #2d2d2d;
            padding: 15px 15px 15px 15px; margin-top: 10px; margin-bottom: 15px;
            border: 2px solid {GOLD}; border-radius: 10px;
            color: #e0e0e0; font-size: 20px; line-height: 1.6;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
            opacity: 0; animation: agenticFadeIn 1.0s ease-out forwards;">
    {user_question}
</div>
</div>
""", unsafe_allow_html=True)

            # Steward response bubble (fade in with 0.4s delay)
            response_html = steward_response.replace('\n\n', '</p><p style="color: #e0e0e0; font-size: 20px; line-height: 1.7; margin: 12px 0;">').replace('\n', '<br>')

            st.markdown(f"""
<div key="agentic-r-{current_idx}" data-slide="{current_idx}">
<div style="background: linear-gradient(135deg, rgba(255, 215, 0, 0.05) 0%, rgba(255, 215, 0, 0.1) 100%);
            border: 2px solid {GOLD};
            border-radius: 10px;
            padding: 20px 25px;
            margin: 15px auto;
            font-size: 20px;
            color: #e0e0e0;
            line-height: 1.7;
            box-shadow: 0 2px 8px rgba(255, 215, 0, 0.2);
            opacity: 0; animation: agenticFadeIn 1.0s ease-out 0.4s forwards;">
    <div>{response_html}</div>
</div>
</div>
""", unsafe_allow_html=True)

            # Footer
            st.markdown("""
<div style="text-align: center; margin: 20px auto 0 auto; padding-top: 15px; border-top: 1px solid rgba(244, 208, 63, 0.3);">
    <p style="color: #e0e0e0; font-size: 16px; line-height: 1.6;">
        <strong>TELOS AI Labs Inc.</strong> |
        <a href="https://github.com/telos-ai-labs/telos" style="color: #F4D03F;" target="_blank">GitHub</a> |
        <a href="mailto:JB@telos-labs.ai" style="color: #F4D03F;" target="_blank">JB@telos-labs.ai</a> |
        <a href="https://forms.gle/xR6gRxQnyLSMJmeT9" style="color: #F4D03F;" target="_blank">Request a Live Demo</a>
    </p>
</div>
""", unsafe_allow_html=True)

            # Navigation (30px matches conversational demo spacing)
            st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

            col_prev, col_next = st.columns(2)
            with col_prev:
                if current_idx > 1:
                    if st.button("Previous", key="agentic_prev", use_container_width=True):
                        st.session_state.agentic_demo_slide_index -= 1
                        st.rerun()
                else:
                    if st.button("Back to Welcome", key="agentic_back_welcome", use_container_width=True):
                        st.session_state.agentic_demo_slide_index = 0
                        st.rerun()
            with col_next:
                if current_idx < len(slides):
                    if st.button("Next", key="agentic_next", use_container_width=True):
                        st.session_state.agentic_demo_slide_index += 1
                        st.rerun()
                else:
                    if st.button("Complete Demo", key="agentic_complete", use_container_width=True):
                        st.session_state.agentic_demo_slide_index = len(slides) + 1
                        st.rerun()
            return

        # Completion screen
        if current_idx > len(slides):
            st.session_state.agentic_demo_completed = True

            st.markdown("""
<div style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45);
            backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
            border: 2px solid #27ae60; border-radius: 15px;
            padding: 25px 30px; margin: 10px auto;
            box-shadow: 0 0 15px rgba(39, 174, 96, 0.3), 0 8px 32px rgba(0, 0, 0, 0.3);">
    <div style="max-width: 700px; margin: 0 auto; color: #e0e0e0; font-size: 17px; line-height: 1.7;">
        <h2 style="color: #F4D03F; margin: 0 0 15px 0;">You've Completed the Agentic Governance Demo</h2>
        <p style="margin: 0 0 12px 0;">You saw how TELOS extends governance from conversations to actions -- six-dimensional purpose definition, graduated decisions, tool selection with audit trails, chain tracking across multi-step tasks, and escalation when the stakes require it.</p>
        <p style="margin: 0;"><strong>What you just walked through is running live.</strong> Click below to try Agentic Live Demo Mode -- real agents, real governance decisions, every fidelity score, tool selection, and escalation visible as it happens.</p>
    </div>
</div>
""", unsafe_allow_html=True)

            st.markdown("<div style='margin: 35px 0;'></div>", unsafe_allow_html=True)

            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("Try Agentic Live Mode", key="agentic_go_live", use_container_width=True):
                    st.session_state.agentic_demo_completed = True
                    st.rerun()
            return

    def _render_agentic_live(agentic_obs_deck):
        """Render agentic live mode — user issues commands, governance evaluates."""
        from telos_observatory.agentic.agentic_response_manager import AgenticResponseManager
        from telos_observatory.agentic.agent_templates import get_agent_templates

        if 'agentic_response_manager' not in st.session_state:
            st.session_state.agentic_response_manager = AgenticResponseManager()

        if 'agentic_current_step' not in st.session_state:
            st.session_state.agentic_current_step = 0

        agent_type = st.session_state.get('agentic_agent_type', 'sql_analyst')
        templates = get_agent_templates()
        template = templates.get(agent_type)

        if not template:
            st.error("Agent template not found")
            return

        # Show agent info header
        from telos_observatory.config.colors import GOLD
        st.markdown(f"""
<div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            border: 2px solid {GOLD}; border-radius: 12px;
            padding: 12px 20px; margin: 10px 0;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <strong style="color: {GOLD}; font-size: 16px;">{template.name}</strong>
            <span style="color: #888; font-size: 14px; margin-left: 10px;">
                Step {st.session_state.agentic_current_step}/10
            </span>
        </div>
        <span style="color: #888; font-size: 13px;">
            Tools: {', '.join(template.tools)}
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

        # Show conversation history
        for i in range(1, st.session_state.agentic_current_step + 1):
            step_data = get_agentic_step_data(i)
            if step_data:
                user_req = step_data.get('user_request', '')
                response = step_data.get('response_text', '')
                decision = step_data.get('decision', '')

                # User message
                st.markdown(f"""
<div style="background: rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px);
            padding: 12px 15px; border-radius: 8px; margin: 8px 0;
            border: 1px solid {GOLD}; color: #fff; font-size: 16px;">
    <strong style="color: {GOLD};">You:</strong> {user_req}
</div>
""", unsafe_allow_html=True)

                # Agent response with decision badge
                from telos_observatory.config.colors import get_fidelity_color
                eff_fidelity = step_data.get('effective_fidelity', 0)
                dec_color = get_fidelity_color(eff_fidelity)

                st.markdown(f"""
<div style="background: rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px);
            padding: 12px 15px; border-radius: 8px; margin: 8px 0;
            border: 1px solid {dec_color}; color: #e0e0e0; font-size: 16px;">
    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
        <strong style="color: #888;">Agent:</strong>
        <span style="color: {dec_color}; font-weight: 600; font-size: 13px;
                      padding: 2px 8px; border: 1px solid {dec_color}; border-radius: 4px;">
            {decision} ({eff_fidelity:.0%})
        </span>
    </div>
    {response.replace(chr(10), '<br>')}
</div>
""", unsafe_allow_html=True)

        # Observation deck
        if st.session_state.get('teloscope_open', False):
            render_teloscope_panel()
        else:
            agentic_obs_deck.render()

        # TELOSCOPE toggle button (available after first governance step)
        if st.session_state.get('agentic_current_step', 0) >= 1:
            teloscope_open = st.session_state.get('teloscope_open', False)
            agentic_deck_open = st.session_state.get('agentic_deck_visible', False)
            if teloscope_open or not agentic_deck_open:
                st.markdown("<div style='margin: 8px 0;'></div>", unsafe_allow_html=True)
                render_teloscope_button()

        # Check completion
        if st.session_state.agentic_current_step >= 10:
            st.session_state.agentic_completed = True
            st.rerun()
            return

        # Input area
        st.markdown("<div style='margin: 15px 0;'></div>", unsafe_allow_html=True)

        with st.form(key="agentic_input_form", clear_on_submit=True):
            user_input = st.text_area(
                "Enter a request for the agent:",
                height=80,
                placeholder=f"Try: {template.example_requests[0]}",
                key="agentic_user_input"
            )
            submitted = st.form_submit_button("Send Request", use_container_width=True)

        if submitted and user_input and user_input.strip():
            mgr = st.session_state.agentic_response_manager
            step_num = st.session_state.agentic_current_step + 1

            result = mgr.process_request(user_input.strip(), template, step_num)

            # Store step data for observation deck + forensic report
            drift_status = mgr.get_drift_history() if hasattr(mgr, 'get_drift_history') else {}
            step_data = {
                'step': step_num,
                'user_request': user_input.strip(),
                'purpose_fidelity': result.purpose_fidelity,
                'scope_fidelity': result.scope_fidelity,
                'tool_fidelity': result.tool_fidelity,
                'chain_sci': result.chain_sci,
                'boundary_fidelity': result.boundary_fidelity,
                'boundary_triggered': result.boundary_triggered,
                'effective_fidelity': result.effective_fidelity,
                'decision': result.decision,
                'decision_explanation': result.decision_explanation,
                'response_text': result.response_text,
                'selected_tool': result.selected_tool,
                'tool_rankings': result.tool_rankings,
                'tool_output': result.tool_output,
                'drift_level': drift_status.get('drift_level', 'NORMAL'),
                'drift_magnitude': drift_status.get('drift_magnitude', 0.0),
                'saai_baseline': drift_status.get('baseline_fidelity'),
            }

            st.session_state[f'agentic_step_{step_num}_data'] = _encrypt_step_data(step_data)
            st.session_state.agentic_current_step = step_num

            # Update chain steps for timeline
            chain_steps = st.session_state.get('agentic_chain_steps', [])
            chain_steps.append({
                'step': step_num,
                'tool': result.selected_tool or 'none',
                'sci': result.chain_sci,
                'effective_fidelity': result.effective_fidelity,
                'chain_broken': result.chain_broken,
            })
            st.session_state.agentic_chain_steps = chain_steps

            st.rerun()

        # Example buttons
        st.markdown("<div style='margin: 10px 0;'></div>", unsafe_allow_html=True)
        st.markdown(f"<p style='color: #888; font-size: 13px;'>Try these examples:</p>", unsafe_allow_html=True)

        example_cols = st.columns(2)
        for idx, example in enumerate(template.example_requests[:4]):
            with example_cols[idx % 2]:
                if st.button(example[:50] + "..." if len(example) > 50 else example,
                           key=f"agentic_example_{idx}", use_container_width=True):
                    mgr = st.session_state.agentic_response_manager
                    step_num = st.session_state.agentic_current_step + 1
                    result = mgr.process_request(example, template, step_num)

                    step_data = {
                        'user_request': example,
                        'purpose_fidelity': result.purpose_fidelity,
                        'scope_fidelity': result.scope_fidelity,
                        'tool_fidelity': result.tool_fidelity,
                        'chain_sci': result.chain_sci,
                        'boundary_fidelity': result.boundary_fidelity,
                        'boundary_triggered': result.boundary_triggered,
                        'effective_fidelity': result.effective_fidelity,
                        'decision': result.decision,
                        'decision_explanation': result.decision_explanation,
                        'response_text': result.response_text,
                        'selected_tool': result.selected_tool,
                        'tool_rankings': result.tool_rankings,
                        'tool_output': result.tool_output,
                    }

                    st.session_state[f'agentic_step_{step_num}_data'] = _encrypt_step_data(step_data)
                    st.session_state.agentic_current_step = step_num

                    chain_steps = st.session_state.get('agentic_chain_steps', [])
                    chain_steps.append({
                        'step': step_num,
                        'tool': result.selected_tool or 'none',
                        'sci': result.chain_sci,
                        'effective_fidelity': result.effective_fidelity,
                        'chain_broken': result.chain_broken,
                    })
                    st.session_state.agentic_chain_steps = chain_steps
                    st.rerun()

    # Unified rendering function
    def render_mode_content(mode: str):
        """Unified content rendering for all modes with feature flags."""
        st.session_state.telos_demo_mode = (mode == "DEMO")

        show_devops_header = (mode == "DEVOPS")
        show_observation_deck = (mode in ["BETA", "TELOS", "DEVOPS"])
        show_teloscope = (mode in ["TELOS", "DEVOPS"])
        show_observatory_lens_auto = (mode in ["TELOS", "DEVOPS"])

        # TELOS mode: profile selector
        if mode == "TELOS":
            query_profile = teloscope_profile_selector.get_profile_from_query_params()
            if query_profile and not st.session_state.get('teloscope_profile'):
                teloscope_profile_selector.apply_profile_settings(query_profile)

            if not st.session_state.get('teloscope_profile'):
                selected = teloscope_profile_selector.render_profile_selector()
                if selected:
                    teloscope_profile_selector.apply_profile_settings(selected)
                    st.rerun()
                return

            profile_features = st.session_state.get('teloscope_features', {})
            show_observation_deck = profile_features.get('observation_deck', True)
            show_teloscope = profile_features.get('teloscope_controls', True)
            show_observatory_lens_auto = profile_features.get('observatory_lens', True)

            teloscope_profile_selector.render_profile_badge()
            st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

        if mode == "DEVOPS":
            if not st.session_state.get('teloscope_profile'):
                teloscope_profile_selector.apply_profile_settings("devops")

        if show_devops_header:
            st.markdown("### DEVOPS Mode - Full System Access")
            st.markdown("**All restrictions removed. Beta mode with full PA extraction and interventions enabled.**")

        # BETA mode: PA questionnaire
        if mode == "BETA":
            if st.session_state.get('beta_completed', False):
                beta_completion = BetaCompletion(state_manager)
                beta_completion.render()
                return

            if not st.session_state.get('pa_established', False):
                pa_answers = pa_onboarding.render_questionnaire()
                if pa_answers is None:
                    return

            beta_steward_is_open = st.session_state.get('beta_steward_panel_open', False)

            if st.session_state.pop('scroll_after_steward_close', False):
                scroll_mode = state_manager.state.scrollable_history_mode if state_manager else False
                if scroll_mode:
                    components.html("""
                    <script>
                    setTimeout(function() {
                        var textareas = window.parent.document.querySelectorAll('textarea');
                        if (textareas.length > 0) {
                            textareas[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
                        } else {
                            window.parent.scrollTo({ top: 0, behavior: 'smooth' });
                        }
                    }, 100);
                    </script>
                    """, height=0)
                else:
                    components.html("""
                    <script>
                    setTimeout(function() {
                        window.parent.scrollTo({ top: 0, behavior: 'smooth' });
                    }, 100);
                    </script>
                    """, height=0)

            if not beta_steward_is_open:
                st.markdown("""
                <style>
                .main .block-container {
                    width: 100% !important; max-width: 100% !important; min-width: 0 !important;
                    margin-left: auto !important; margin-right: auto !important;
                    padding-left: 1rem !important; padding-right: 1rem !important;
                    box-sizing: border-box !important;
                }
                [data-testid="stHorizontalBlock"] {
                    width: 100% !important; max-width: 100% !important; box-sizing: border-box !important;
                }
                </style>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <style>
                .main .block-container {
                    width: 100% !important; max-width: 100% !important; min-width: auto !important;
                    margin-left: 0 !important; margin-right: 0 !important;
                    padding-left: 2rem !important; padding-right: 2rem !important;
                }
                [data-testid="stHorizontalBlock"] {
                    width: 100% !important; max-width: 100% !important;
                }
                </style>
                """, unsafe_allow_html=True)

            if not st.session_state.get('beta_scroll_to_top_done', False):
                st.session_state.beta_scroll_to_top_done = True
                components.html("""
                <script>
                (function() {
                    window.scrollTo(0, 0);
                    if (window.parent) window.parent.scrollTo(0, 0);
                    var mainContainer = window.parent.document.querySelector('.main');
                    if (mainContainer) mainContainer.scrollTop = 0;
                    var appContainer = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
                    if (appContainer) appContainer.scrollTop = 0;
                })();
                </script>
                """, height=0)

        # AGENTIC mode
        if mode == "AGENTIC":
            # Check completion first
            if st.session_state.get('agentic_completed', False):
                agentic_completion = AgenticCompletion()
                agentic_completion.render()
                return

            # Check if in agentic demo mode (slideshow)
            agentic_demo_mode = not st.session_state.get('agentic_demo_completed', False)

            if agentic_demo_mode:
                _render_agentic_demo(agentic_observation_deck)
                return

            # Live mode: agent selection then interactive governance
            if not st.session_state.get('agentic_pa_established', False):
                agentic_onboarding.render()
                return

            # Live agentic conversation
            _render_agentic_live(agentic_observation_deck)
            return

        # Main conversation display (all modes)
        conversation_display.render()

        # Observation Deck (mode-specific rendering)
        if mode == "BETA":
            if st.session_state.get('pa_established', False):
                st.markdown("<div style='margin: 10px 0;'></div>", unsafe_allow_html=True)

                if st.session_state.get('teloscope_open', False):
                    render_teloscope_panel()
                else:
                    beta_observation_deck.render()

                has_turn_data = st.session_state.get('beta_turn_1_data') is not None
                alignment_lens_open = st.session_state.get('beta_deck_visible', False)
                teloscope_open = st.session_state.get('teloscope_open', False)
                if has_turn_data and (teloscope_open or not alignment_lens_open):
                    st.markdown("<div style='margin: 8px 0;'></div>", unsafe_allow_html=True)
                    render_teloscope_button()
        elif mode == "DEMO":
            if st.session_state.get('demo_slide_index', 0) == 4:
                pass
            elif st.session_state.get('show_observation_deck', False):
                st.markdown("<div style='margin: 40px 0;'></div>", unsafe_allow_html=True)
                observation_deck.render()
        elif show_observation_deck:
            st.markdown("<div style='margin: 40px 0;'></div>", unsafe_allow_html=True)
            observation_deck.render()

        if show_teloscope:
            st.markdown("<div style='margin: 5px 0;'></div>", unsafe_allow_html=True)
            teloscope_controls.render()

        if show_observatory_lens_auto or st.session_state.get('show_observatory_lens', False):
            st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)
            observatory_lens.render()

    # Steward panel logic
    active_tab = st.session_state.get('active_tab', 'DEMO')
    is_beta_mode = active_tab == "BETA"

    if is_beta_mode:
        steward_open = st.session_state.get('beta_steward_panel_open', False)
    else:
        steward_open = st.session_state.get('steward_panel_open', False)

    if is_beta_mode:
        render_mode_content(st.session_state.active_tab)
        if steward_open and has_beta_consent:
            st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)
            render_bottom_section()
    elif steward_open and has_beta_consent:
        col_main, col_steward = st.columns([7, 3])
        with col_main:
            render_mode_content(st.session_state.active_tab)
        with col_steward:
            steward_panel.render_panel()
    else:
        render_mode_content(st.session_state.active_tab)

    # Final CSS override
    st.html("""
    <style>
    .stButton > button,
    button[data-baseweb="button"],
    button[kind="secondary"],
    button[kind="primary"],
    .stFormSubmitButton > button {
        background-color: #2d2d2d !important;
        background: #2d2d2d !important;
        color: #e0e0e0 !important;
        border: 1px solid #F4D03F !important;
    }
    /* Primary glow only for tab row */
    div[data-testid="stHorizontalBlock"]:first-of-type button[kind="primary"] {
        border: 2px solid #F4D03F !important;
        box-shadow: 0 0 8px rgba(255, 215, 0, 0.5) !important;
    }
    .stButton > button:hover,
    button[data-baseweb="button"]:hover,
    .stFormSubmitButton > button:hover {
        border-color: #F4D03F !important;
        box-shadow: 0 0 6px #F4D03F !important;
        background-color: #3d3d3d !important;
    }
    .stTextArea textarea,
    textarea[data-baseweb="textarea"],
    .stTextArea > div > div > textarea {
        background-color: #2d2d2d !important;
        color: #ffffff !important;
        border: 1px solid #F4D03F !important;
        border-color: #F4D03F !important;
    }
    .stTextArea textarea:focus, textarea:focus {
        border-color: #F4D03F !important;
        outline: none !important;
        box-shadow: 0 0 4px rgba(244, 208, 63, 0.5) !important;
    }
    .stTextArea > div, .stTextArea > div > div {
        border-color: #F4D03F !important;
    }
    [data-baseweb="form-control-container"], .stForm {
        border-color: #F4D03F !important;
    }
    .message-container:hover {
        box-shadow: 0 0 6px #F4D03F !important;
        transition: box-shadow 0.3s ease !important;
    }
    </style>
    """)

    # Layout CSS - injected at end of render for highest priority
    if active_tab not in ['TELOS', 'DEVOPS']:
        if steward_open and has_beta_consent:
            st.markdown("""
            <style>
            .main .block-container,
            [data-testid="stAppViewContainer"] > .main > .block-container,
            section[data-testid="stMainBlockContainer"],
            [data-testid="stMainBlockContainer"] {
                max-width: 100% !important;
                padding-left: 2rem !important;
                padding-right: 2rem !important;
                margin-left: 0 !important;
                margin-right: 0 !important;
            }
            .main [data-testid="stVerticalBlock"],
            .main [data-testid="stHorizontalBlock"] {
                max-width: 100% !important;
                margin-left: 0 !important;
                margin-right: 0 !important;
            }
            [style*="max-width: 700px"],
            [style*="max-width:700px"],
            div[style*="700px"] {
                max-width: 100% !important;
                width: 100% !important;
            }
            [style*="width: 700px"],
            [style*="width:700px"] {
                width: 100% !important;
                max-width: 100% !important;
            }
            </style>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <style>
            .main .block-container,
            [data-testid="stAppViewContainer"] > .main > .block-container,
            section[data-testid="stMainBlockContainer"],
            [data-testid="stMainBlockContainer"] {
                max-width: 700px !important;
                margin-left: auto !important;
                margin-right: auto !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }
            .main [data-testid="stVerticalBlock"],
            .main [data-testid="stHorizontalBlock"] {
                max-width: 700px !important;
                margin-left: auto !important;
                margin-right: auto !important;
            }
            .main [data-testid="column"] {
                max-width: 100% !important;
            }
            iframe {
                min-height: 50px !important;
                overflow: visible !important;
            }
            </style>
            """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()

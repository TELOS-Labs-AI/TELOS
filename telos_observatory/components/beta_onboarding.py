"""
Beta Onboarding Component for TELOS Observatory V3.
Handles consent and data privacy explanation for beta testers.
"""

import streamlit as st
from datetime import datetime
from pathlib import Path
import json


class BetaOnboarding:
    """Beta onboarding screen with consent and data privacy information."""

    def __init__(self, state_manager):
        """Initialize with state manager reference.

        Args:
            state_manager: StateManager instance for session operations
        """
        self.state_manager = state_manager

    def _log_consent(self, session_id: str):
        """Log consent to persistent file for audit trail.

        Args:
            session_id: Session identifier for the consent
        """
        try:
            # Create beta_consents directory if it doesn't exist
            consents_dir = Path(__file__).parent.parent / 'beta_consents'
            consents_dir.mkdir(exist_ok=True)

            # Consent log file
            consent_log_file = consents_dir / 'consent_log.json'

            # Load existing consents
            if consent_log_file.exists():
                with open(consent_log_file, 'r') as f:
                    consent_log = json.load(f)
            else:
                consent_log = {'consents': []}

            # Add new consent
            consent_entry = {
                'session_id': session_id,
                'timestamp': datetime.now().isoformat(),
                'consent_statement': 'I understand and consent to participate in TELOS Beta testing. I agree to share governance deltas (mathematical measurements only) to help improve the system. I understand my conversation content remains private.',
                'version': '1.0'
            }

            consent_log['consents'].append(consent_entry)

            # Save updated log
            with open(consent_log_file, 'w') as f:
                json.dump(consent_log, f, indent=2)

        except Exception as e:
            st.error(f"Error logging consent: {e}")

    def render(self):
        """Render beta onboarding screen - blocks all access until consent given."""
        # Check if user has already consented
        if st.session_state.get('beta_consent_given', False):
            return True  # User has consented, proceed to beta interface

        # Kill Streamlit's default top padding and header gap
        st.markdown("""
        <style>
            .block-container,
            section.main > div.block-container,
            [data-testid="stMainBlockContainer"],
            .stMainBlockContainer.block-container,
            div[data-testid="stMainBlockContainer"].block-container,
            .stApp .main .block-container,
            .stApp section.main .block-container {
                padding-top: 0 !important;
                margin-top: 0 !important;
            }
            [data-testid="stAppViewContainer"] > .main {
                padding-top: 0 !important;
                margin-top: 0 !important;
            }
            section.main {
                padding-top: 0 !important;
                margin-top: 0 !important;
            }
        </style>
        """, unsafe_allow_html=True)

        # Center all content using standard column layout
        col_spacer_left, col_center, col_spacer_right = st.columns([0.5, 3, 0.5])

        with col_center:
            # Single card with fade-in animation, matching DEMO/AGENTIC welcome style
            st.markdown("""
            <style>
            @keyframes betaFadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            /* Gold toggle switch — replace native checkbox */
            .stCheckbox {
                gap: 10px !important;
            }
            .stCheckbox > label {
                color: #e0e0e0 !important;
            }
            .stCheckbox input[type="checkbox"] {
                width: 44px !important;
                height: 24px !important;
                appearance: none !important;
                -webkit-appearance: none !important;
                background-color: #2d2d2d !important;
                border: 2px solid #666 !important;
                border-radius: 12px !important;
                cursor: pointer !important;
                position: relative !important;
                transition: all 0.3s ease !important;
                margin-right: 10px !important;
            }
            .stCheckbox input[type="checkbox"]::after {
                content: "" !important;
                position: absolute !important;
                width: 16px !important;
                height: 16px !important;
                border-radius: 50% !important;
                background-color: #fff !important;
                top: 2px !important;
                left: 2px !important;
                transition: all 0.3s ease !important;
            }
            .stCheckbox input[type="checkbox"]:checked {
                background-color: #F4D03F !important;
                border-color: #F4D03F !important;
            }
            .stCheckbox input[type="checkbox"]:checked::after {
                left: 22px !important;
                background-color: #0a0a0a !important;
            }
            /* Hide the SVG checkmark that Streamlit adds */
            .stCheckbox svg,
            .stCheckbox path,
            .stCheckbox [data-testid="stCheckbox"] svg,
            [data-testid="stCheckbox"] svg,
            [data-testid="stCheckbox"] path,
            .stCheckbox span svg,
            .stCheckbox label svg {
                display: none !important;
                visibility: hidden !important;
                opacity: 0 !important;
                width: 0 !important;
                height: 0 !important;
            }
            </style>
            <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
                        border: 2px solid #F4D03F;
                        border-radius: 15px;
                        padding: 20px;
                        margin: -4rem auto 20px auto;
                        text-align: center;
                        box-shadow: 0 0 8px rgba(255, 215, 0, 0.4);
                        opacity: 0;
                        animation: betaFadeIn 1.0s ease-out forwards;">
                <h1 style="color: #F4D03F; font-size: 28px; margin: 0 0 4px 0;">Welcome to TELOS Beta</h1>
                <p style="color: #e0e0e0; font-size: 15px; margin: 0 0 14px 0;">Help us build the future of AI governance</p>
                <div style="text-align: left; max-width: 700px; margin: 0 auto;">
                    <p style="color: #e0e0e0; font-size: 16px; line-height: 1.5; margin-bottom: 10px;">
                        You're getting early access to TELOS AI Governance features before they're publicly released.
                        Your feedback helps us refine the system and improve AI governance for everyone.
                    </p>
                    <p style="color: #e0e0e0; font-size: 16px; line-height: 1.5; margin-bottom: 0;">
                        <strong style="color: #F4D03F;">Your Data:</strong>
                        Conversations stay in your browser and are never sent to our servers. When you close the session, they're gone. We collect only anonymized governance measurements (fidelity scores, intervention patterns) — never conversation content.
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)

            consent = st.checkbox(
                "I understand and consent to participate in TELOS Beta testing. I agree to share governance deltas (mathematical measurements only) to help improve the system. I understand my conversation content remains private.",
                key="beta_consent_checkbox"
            )

            # Continue button (only enabled if consent given)
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("Continue to Beta", use_container_width=True, disabled=not consent):
                    if consent:
                        # Record consent in session state
                        st.session_state.beta_consent_given = True
                        st.session_state.beta_consent_timestamp = datetime.now().isoformat()

                        # Get session ID from state manager
                        session_id = self.state_manager.state.session_id

                        # Log consent to persistent file
                        self._log_consent(session_id)

                        # Log consent to session metadata (non-sensitive)
                        if hasattr(self.state_manager.state, 'metadata'):
                            self.state_manager.state.metadata['beta_consent'] = True
                            self.state_manager.state.metadata['beta_consent_timestamp'] = st.session_state.beta_consent_timestamp
                        else:
                            # Create metadata dict if it doesn't exist
                            self.state_manager.state.metadata = {
                                'beta_consent': True,
                                'beta_consent_timestamp': st.session_state.beta_consent_timestamp
                            }

                        st.rerun()

        return False  # User has not consented yet

    def has_consent(self):
        """Check if user has given beta consent.

        Returns:
            bool: True if consent given, False otherwise
        """
        return st.session_state.get('beta_consent_given', False)

    def revoke_consent(self):
        """Revoke beta consent and clear associated data."""
        if 'beta_consent_given' in st.session_state:
            del st.session_state.beta_consent_given
        if 'beta_consent_timestamp' in st.session_state:
            del st.session_state.beta_consent_timestamp

        # Clear from state manager metadata if exists
        if hasattr(self.state_manager.state, 'metadata'):
            if 'beta_consent' in self.state_manager.state.metadata:
                del self.state_manager.state.metadata['beta_consent']
            if 'beta_consent_timestamp' in self.state_manager.state.metadata:
                del self.state_manager.state.metadata['beta_consent_timestamp']

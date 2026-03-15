"""
Beta PA Establishment Component
================================

Expedited 1-2 turn Primacy Attractor establishment for BETA testing.

Flow:
1. User selects template OR states custom goal/purpose (Turn 1)
2. Extract PA components using LLM (if custom)
3. Show for confirmation/refinement (Turn 2)
4. Derive AI PA (hidden during session)
5. Save to session state and backend storage

NEW: Click-to-select templates for instant PA establishment.
"""

import html as html_module
import streamlit as st
import logging
import json
import os
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any

from telos_observatory.services.pa_extractor import PAExtractor
from telos_observatory.services.backend_client import BackendService
from telos_observatory.services.beta_dual_attractor import derive_ai_pa_from_user_pa, compute_pa_embeddings

# Import PA templates
try:
    from telos_observatory.config.pa_templates import PA_TEMPLATES, get_template_by_id, template_to_pa
except ImportError:
    # Fallback if templates not available
    PA_TEMPLATES = []
    def get_template_by_id(id): return None
    def template_to_pa(t): return {}

logger = logging.getLogger(__name__)


class BetaPAEstablishment:
    """
    Expedited PA establishment for BETA sessions.

    Creates user and AI Primacy Attractors in 1-2 turns instead of 5-10.
    """

    def __init__(self, state_manager, backend_client: Optional[BackendService] = None):
        """
        Initialize PA establishment component.

        Args:
            state_manager: StateManager instance
            backend_client: Optional BackendService for logging
        """
        self.state_manager = state_manager
        self.backend = backend_client
        self.extractor = PAExtractor()

    def render(self) -> bool:
        """
        Render PA establishment flow.

        Returns:
            True if PA establishment complete, False if still in progress
        """
        # Check if PA already established
        if st.session_state.get('beta_pa_established', False):
            return True

        # Initialize PA establishment state
        if 'pa_extraction_step' not in st.session_state:
            st.session_state.pa_extraction_step = 'template_select'  # Start with template selection
            st.session_state.extracted_pa = None
            st.session_state.ai_pa = None

        # Render current step
        if st.session_state.pa_extraction_step == 'template_select':
            return self._render_template_selection()
        elif st.session_state.pa_extraction_step == 'statement':
            return self._render_statement_step()
        elif st.session_state.pa_extraction_step == 'confirmation':
            return self._render_confirmation_step()
        else:
            # Fallback - should not reach here
            return False

    def _render_template_selection(self) -> bool:
        """
        Step 0: User selects from pre-defined templates or chooses custom.

        Returns:
            False (PA not established yet)
        """
        # Wrap everything in 700px max-width container to match Demo mode
        st.markdown("""
        <style>
        .beta-template-container {
            max-width: 700px;
            margin: 0 auto;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown('<div class="beta-template-container">', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # Display templates in a grid (2 columns) - wrapped in container
        st.markdown('<div style="max-width: 700px; margin: 0 auto;">', unsafe_allow_html=True)

        if PA_TEMPLATES:
            # Create rows of 2 templates each
            for i in range(0, len(PA_TEMPLATES), 2):
                cols = st.columns(2)
                for j, col in enumerate(cols):
                    if i + j < len(PA_TEMPLATES):
                        template = PA_TEMPLATES[i + j]
                        with col:
                            self._render_template_card(template)

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        # Custom options - wrapped in container
        st.markdown("""
        <div style="max-width: 700px; margin: 0 auto; text-align: center; color: #888; margin: 20px auto;">
            <span style="font-size: 14px;">None of these fit?</span>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            # Two buttons side by side
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("Describe Purpose", use_container_width=True, key="custom_purpose_btn",
                            help="Answer a few quick questions to define your conversation's purpose"):
                    # Clear any preloaded PA data - user wants to describe custom purpose
                    st.session_state.extracted_pa = None
                    st.session_state.selected_template = None
                    st.session_state.pa_extraction_step = 'statement'
                    st.rerun()
            with btn_col2:
                if st.button("Start Fresh", use_container_width=True, key="start_fresh_btn",
                            help="Skip setup - your purpose will be derived from your first message"):
                    self._start_fresh_mode()
                    st.rerun()

        return False

    def _render_template_card(self, template: dict):
        """Render a single template card with click-to-select and glassmorphic styling."""
        card_html = f"""
        <div style="
            background: rgba(26, 26, 26, 0.7);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 15px;
            margin: 8px 0;
            cursor: pointer;
            transition: all 0.2s ease;
        ">
            <div style="font-size: 28px; margin-bottom: 8px;">{html_module.escape(str(template.get('icon', '')))}</div>
            <div style="color: #F4D03F; font-size: 18px; font-weight: bold; margin-bottom: 4px;">
                {html_module.escape(template['title'])}
            </div>
            <div style="color: #aaa; font-size: 13px;">
                {html_module.escape(template['short_desc'])}
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

        # Button to select this template
        if st.button(f"Select", key=f"select_{template['id']}", use_container_width=True):
            self._apply_template(template)
            st.rerun()

    def _apply_template(self, template: dict):
        """Apply a selected template as the PA."""
        # Convert template to PA structure
        pa = template_to_pa(template)

        # Store in session state
        st.session_state.extracted_pa = pa
        st.session_state.selected_template = template

        # Load pre-computed embeddings for this template (eliminates API call)
        self._load_template_embeddings(template['id'])

        # Skip to confirmation (or finalize directly for templates)
        st.session_state.pa_extraction_step = 'confirmation'

    def _load_template_embeddings(self, template_id: str) -> bool:
        """
        Load pre-computed PA embeddings for a template.

        Eliminates the need for an embedding API call when using templates.
        The embeddings are pre-computed using the exact same process as
        when a user establishes their own PA (generate_template_embeddings.py).

        Args:
            template_id: The template identifier (e.g., 'explore_telos')

        Returns:
            True if embeddings loaded successfully, False otherwise
        """
        try:
            # Path to pre-computed embeddings
            embeddings_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'config', 'pa_template_embeddings.json'
            )

            if not os.path.exists(embeddings_path):
                logger.warning(f"Template embeddings file not found: {embeddings_path}")
                return False

            with open(embeddings_path, 'r') as f:
                all_embeddings = json.load(f)

            if template_id not in all_embeddings:
                logger.warning(f"No pre-computed embeddings for template: {template_id}")
                return False

            template_data = all_embeddings[template_id]

            # Load embeddings as numpy arrays and cache in session state
            # These will be picked up by beta_response_manager.py line 786-792
            user_pa_embedding = np.array(template_data['user_pa_embedding'])
            ai_pa_embedding = np.array(template_data['ai_pa_embedding'])

            st.session_state.cached_user_pa_embedding = user_pa_embedding
            st.session_state.cached_ai_pa_embedding = ai_pa_embedding
            # CRITICAL: Also cache as cached_st_user_pa_embedding - this is the key
            # that beta_response_manager.py line 535 looks for when computing User Fidelity
            st.session_state.cached_st_user_pa_embedding = user_pa_embedding
            # CRITICAL: Also cache AI PA for AI fidelity checks
            # This is used by beta_response_manager.py to compare AI responses to AI PA
            st.session_state.cached_st_ai_pa_embedding = ai_pa_embedding

            # CRITICAL: Enable rescaled fidelity mode for adaptive context to work
            # Without this flag, the adaptive context system is bypassed entirely
            # and fidelity is calculated using the wrong code path/thresholds
            st.session_state.use_rescaled_fidelity_mode = True

            # CRITICAL: Set PA identity hash so beta_response_manager recognizes cached embeddings
            # This must be computed EXACTLY the same way as beta_response_manager.py lines 1648-1733
            # The extracted_pa from _apply_template will be in session state
            if 'extracted_pa' in st.session_state:
                purpose = st.session_state.extracted_pa.get('purpose', '')
                scope = st.session_state.extracted_pa.get('scope', [])
                # IMPORTANT: Use ' '.join() with space separator to match beta_response_manager.py
                # Lines 1648-1649 use: purpose_str = ' '.join(purpose_raw) if isinstance...
                if isinstance(purpose, list):
                    purpose = ' '.join(purpose)
                if isinstance(scope, list):
                    scope = ' '.join(scope)
                import hashlib
                pa_identity = hashlib.md5(f"{purpose}|{scope}".encode()).hexdigest()[:16]
                st.session_state.cached_pa_identity = pa_identity
                logger.info(f"   Set PA identity hash: {pa_identity}")

            logger.info(f"Loaded pre-computed embeddings for template: {template_id}")
            logger.info(f"   User PA: {len(user_pa_embedding)} dims")
            logger.info(f"   AI PA: {len(ai_pa_embedding)} dims")
            logger.info(f"   rho_PA: {template_data.get('rho_pa', 'N/A')}")

            return True

        except Exception as e:
            logger.error(f"Failed to load template embeddings: {e}")
            return False

    def _start_fresh_mode(self):
        """
        Start fresh mode - skip PA establishment and derive from first message.

        Sets a flag indicating PA needs to be derived from turn 1.
        The actual derivation happens in beta_response_manager.
        Also sets up a welcome message for the conversation.
        """
        # Mark PA as "pending derivation from turn 1"
        st.session_state.pa_pending_derivation = True
        st.session_state.beta_pa_established = True  # Allow chat to start
        st.session_state.pa_established = True  # Also set the generic flag
        st.session_state.pa_establishment_time = datetime.now().isoformat()

        # Set flag to show Steward welcome message
        st.session_state.show_fresh_start_welcome = True

        # Set minimal placeholder PA - will be replaced after turn 1
        placeholder_pa = {
            "purpose": ["Purpose will be derived from your first message"],
            "scope": ["Open - waiting for first message"],
            "boundaries": ["To be determined"],
            "success_criteria": "Productive conversation",
            "style": "Adaptive",
            "established_turn": 0,
            "establishment_method": "fresh_start_pending"
        }

        st.session_state.primacy_attractor = placeholder_pa
        st.session_state.user_pa = placeholder_pa
        st.session_state.ai_pa = None  # Will be derived after turn 1
        st.session_state.extracted_pa = placeholder_pa

        # Update state manager if available
        if self.state_manager:
            self.state_manager.state.primacy_attractor = placeholder_pa
            self.state_manager.state.user_pa_established = False  # Not really established yet
            self.state_manager.state.pa_converged = False

        # Initialize turn counter
        st.session_state.beta_current_turn = 1

        logger.info("Fresh Start mode activated - PA will be derived from first message")

    def _render_statement_step(self) -> bool:
        """
        Step 1: User states their goal/purpose.

        Returns:
            False (PA not established yet)
        """
        st.markdown("""
        <div style="text-align: center; padding: 20px 0;">
            <h2 style="color: #F4D03F; font-size: 36px; margin: 0;">Establish Your Purpose</h2>
            <p style="color: #e0e0e0; font-size: 16px; margin-top: 10px;">
                Tell TELOS what you want to accomplish in this session
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        # Show examples
        with st.expander("💡 Examples of good purpose statements", expanded=False):
            st.markdown("""
            **Work & Development:**
            - "I want to debug my Python API authentication issue"
            - "Help me refactor this messy codebase for better maintainability"
            - "I need to design a database schema for a social media app"

            **Learning & Research:**
            - "I want to understand TELOS without overwhelming technical details"
            - "Explain quantum computing concepts at an undergraduate level"
            - "Help me write a literature review on AI alignment research"

            **Creative & Planning:**
            - "Help me brainstorm ideas for a sci-fi short story"
            - "I need to plan a 2-week trip to Japan on a budget"
            - "Assist with writing a grant proposal for climate research"

            **Tips:**
            - Be specific about your goal
            - Mention your expertise level if relevant
            - Note any constraints (time, complexity, scope)
            """)

        st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

        # Input form
        with st.form(key="pa_statement_form"):
            st.markdown("**What do you want to accomplish?**")

            user_statement = st.text_area(
                label="Your purpose",
                placeholder="Example: I want to debug my Python API authentication issue without getting overwhelmed by security theory...",
                height=100,
                max_chars=2000,
                label_visibility="collapsed",
                key="pa_statement_input"
            )

            st.markdown("<div style='margin: 15px 0;'></div>", unsafe_allow_html=True)

            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                submit_button = st.form_submit_button(
                    "Extract Purpose",
                    use_container_width=True,
                    type="primary"
                )

        # Process submission
        if submit_button:
            if not user_statement or len(user_statement.strip()) < 10:
                st.error("Please provide a more detailed purpose statement (at least 10 characters)")
                return False

            # Extract PA components
            with st.spinner("🔍 Analyzing your purpose..."):
                try:
                    extracted_pa = self.extractor.extract_from_statement(user_statement)

                    # Store in session state
                    st.session_state.extracted_pa = extracted_pa
                    st.session_state.pa_extraction_step = 'confirmation'

                    # Move to confirmation step
                    st.rerun()

                except Exception:
                    logger.debug("PA extraction failed", exc_info=True)
                    st.error("Failed to extract purpose. Please try again or rephrase your statement.")
                    return False

        return False  # Not established yet

    def _render_confirmation_step(self) -> bool:
        """
        Step 2: Show extracted PA for confirmation/refinement.

        Returns:
            True if confirmed and saved, False otherwise
        """
        st.markdown("""
        <div style="text-align: center; padding: 20px 0;">
            <h2 style="color: #F4D03F; font-size: 36px; margin: 0;">Confirm Your Purpose</h2>
            <p style="color: #e0e0e0; font-size: 16px; margin-top: 10px;">
                TELOS extracted these components from your statement
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        extracted_pa = st.session_state.extracted_pa

        # Show extracted PA
        st.markdown("""
        <div class="message-container" style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
             border: 1px solid #F4D03F; border-radius: 8px; padding: 20px; margin: 20px 0;">
        """, unsafe_allow_html=True)

        st.markdown("### 🎯 Purpose")
        st.markdown(f"**{extracted_pa['purpose'][0]}**")

        st.markdown("### 🔭 Scope")
        for item in extracted_pa['scope']:
            st.markdown(f"- {item}")

        st.markdown("### 🚧 Boundaries")
        for item in extracted_pa['boundaries']:
            st.markdown(f"- {item}")

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        # Confirmation options
        col1, col2 = st.columns(2)

        with col1:
            if st.button("✓ Looks Good - Start Session", use_container_width=True, type="primary"):
                return self._finalize_pa_establishment(extracted_pa)

        with col2:
            refine_mode = st.button("✎ Refine Purpose", use_container_width=True)

        # Refinement interface
        if refine_mode or st.session_state.get('pa_refine_mode', False):
            st.session_state.pa_refine_mode = True

            st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

            with st.form(key="pa_refinement_form"):
                st.markdown("**How would you like to refine your purpose?**")

                refinement_request = st.text_area(
                    label="Refinement",
                    placeholder="Example: Make the scope more focused on just authentication, not general API issues...",
                    height=80,
                    max_chars=1000,
                    label_visibility="collapsed",
                    key="pa_refinement_input"
                )

                col1, col2 = st.columns(2)
                with col1:
                    refine_submit = st.form_submit_button("Apply Refinement", use_container_width=True)
                with col2:
                    cancel_refine = st.form_submit_button("Cancel", use_container_width=True)

            if refine_submit and refinement_request:
                with st.spinner("🔄 Refining your purpose..."):
                    try:
                        refined_pa = self.extractor.refine_pa(extracted_pa, refinement_request)
                        st.session_state.extracted_pa = refined_pa
                        st.session_state.pa_refine_mode = False
                        st.rerun()
                    except Exception as e:
                        logger.debug("PA refinement failed", exc_info=True)
                        st.error("Refinement failed. Please try again.")

            if cancel_refine:
                st.session_state.pa_refine_mode = False
                st.rerun()

        return False  # Not finalized yet

    def _finalize_pa_establishment(self, user_pa: Dict[str, Any]) -> bool:
        """
        Finalize PA establishment: derive AI PA and save everything.

        Uses mathematical dual attractor derivation with intent-to-role mapping.

        Args:
            user_pa: Confirmed user PA

        Returns:
            True if successful
        """
        try:
            with st.spinner("⚙️ Setting up TELOS governance..."):
                # Derive AI PA using dual attractor (intent-to-role mapping)
                ai_pa = derive_ai_pa_from_user_pa(user_pa)

                # Compute embeddings at establishment time (if not already cached from template)
                if 'cached_user_pa_embedding' not in st.session_state:
                    try:
                        # Use CACHED provider to avoid expensive model reloading (critical for Railway cold start)
                        from telos_core.embedding_provider import get_cached_minilm_provider
                        embedding_provider = get_cached_minilm_provider()
                        user_embedding, ai_embedding = compute_pa_embeddings(user_pa, ai_pa, embedding_provider)

                        # Cache embeddings immediately - no lazy computation
                        st.session_state.cached_user_pa_embedding = user_embedding
                        st.session_state.cached_ai_pa_embedding = ai_embedding

                        logger.info(f"Computed and cached PA embeddings at establishment time")
                    except Exception as e:
                        logger.warning(f"Failed to compute embeddings at establishment: {e}")

                # Store in session state
                st.session_state.user_pa = user_pa
                st.session_state.ai_pa = ai_pa
                st.session_state.beta_pa_established = True

                # CRITICAL: Sync primacy_attractor for UI display
                # beta_observation_deck.py line 810 reads from this key
                st.session_state.primacy_attractor = user_pa

                # Create BETA session in backend storage
                if self.backend:
                    try:
                        session_id = st.session_state.get('session_id', self.state_manager.state.session_id)

                        session_data = {
                            'session_id': session_id,
                            'user_pa_config': user_pa,
                            'ai_pa_config': ai_pa,
                            'basin_constant': 1.0,  # Proven effective
                            'constraint_tolerance': 0.05,  # Strict governance
                            'created_at': datetime.now().isoformat(),
                            'total_turns': 0
                        }

                        self.backend.insert_beta_session(session_data)
                        logger.info(f"Created BETA session: {session_id}")

                    except Exception as e:
                        logger.error(f"Failed to create backend session: {e}")
                        # Don't block - session can work without backend logging

                # Add to state manager metadata
                if hasattr(self.state_manager.state, 'metadata'):
                    self.state_manager.state.metadata['user_pa'] = user_pa
                    self.state_manager.state.metadata['ai_pa'] = ai_pa
                    self.state_manager.state.metadata['pa_established_at'] = datetime.now().isoformat()
                else:
                    self.state_manager.state.metadata = {
                        'user_pa': user_pa,
                        'ai_pa': ai_pa,
                        'pa_established_at': datetime.now().isoformat()
                    }

                logger.info("PA establishment complete")

                # Show success message
                st.success("✓ Purpose established! Starting your BETA session...")
                st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

                # Small delay to show success message
                import time
                time.sleep(1)

                st.rerun()

                return True

        except Exception:
            logger.debug("PA finalization failed", exc_info=True)
            st.error("Failed to finalize purpose. Please try again.")
            return False

    def get_user_pa(self) -> Optional[Dict[str, Any]]:
        """
        Get established user PA.

        Returns:
            User PA dictionary or None if not established
        """
        return st.session_state.get('user_pa')

    def get_ai_pa(self) -> Optional[Dict[str, Any]]:
        """
        Get derived AI PA.

        Returns:
            AI PA dictionary or None if not established
        """
        return st.session_state.get('ai_pa')

    def is_established(self) -> bool:
        """
        Check if PA establishment is complete.

        Returns:
            True if PA established
        """
        return st.session_state.get('beta_pa_established', False)

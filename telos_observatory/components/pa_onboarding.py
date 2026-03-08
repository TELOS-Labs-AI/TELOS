"""
PA Onboarding Component for BETA Mode
======================================

Establishes Primacy Attractor through click-to-select templates
or explicit questionnaire within first 2 turns.
"""

import html as html_module
import streamlit as st
from typing import Dict, Optional
from datetime import datetime

# Import color configuration
from telos_observatory.config.colors import GOLD, GOLD_80  # GOLD = #F4D03F (refined, easier on eyes)

# Import dual attractor for AI PA derivation
from telos_observatory.services.beta_dual_attractor import derive_ai_pa_from_user_pa, compute_pa_embeddings

# Import PA templates
try:
    from telos_observatory.config.pa_templates import PA_TEMPLATES, get_template_by_id, template_to_pa
except ImportError:
    PA_TEMPLATES = []
    def get_template_by_id(id): return None
    def template_to_pa(t): return {}


def _encrypt_pa_in_session_state():
    """Encrypt sensitive text fields in PA data stored in session state.

    Encrypts purpose, scope, boundaries, and exemplar text while leaving
    structural metadata (template name, counts, flags) in cleartext.
    Called after PA establishment completes.
    """
    try:
        from telos_governance.session_key_store import get_session_key_store
        store = get_session_key_store()
        if not store:
            return
    except ImportError:
        return

    _TEXT_PA_FIELDS = ('purpose', 'scope', 'purpose_examples', 'scope_items',
                       'boundaries', 'safe_exemplars')

    for state_key in ('primacy_attractor', 'user_pa'):
        pa = st.session_state.get(state_key)
        if not isinstance(pa, dict) or pa.get('_pa_encrypted'):
            continue

        encrypted_pa = dict(pa)
        encrypted_pa['_pa_encrypted'] = True
        for field_name in _TEXT_PA_FIELDS:
            val = encrypted_pa.get(field_name)
            if val is None:
                continue
            try:
                if isinstance(val, str):
                    encrypted_pa[field_name] = store.encrypt_string(val)
                elif isinstance(val, list):
                    encrypted_pa[field_name] = [
                        store.encrypt_string(str(item)) if isinstance(item, str) else item
                        for item in val
                    ]
            except Exception:
                pass  # Keep plaintext on failure

        st.session_state[state_key] = encrypted_pa


def decrypt_pa_data(pa: dict) -> dict:
    """Decrypt PA data fields. Used by components that read PA from session state."""
    if not isinstance(pa, dict) or not pa.get('_pa_encrypted'):
        return pa

    try:
        from telos_governance.session_key_store import get_session_key_store
        store = get_session_key_store()
        if not store:
            return pa
    except ImportError:
        return pa

    _TEXT_PA_FIELDS = ('purpose', 'scope', 'purpose_examples', 'scope_items',
                       'boundaries', 'safe_exemplars')

    decrypted = dict(pa)
    for field_name in _TEXT_PA_FIELDS:
        val = decrypted.get(field_name)
        if val is None:
            continue
        try:
            if isinstance(val, str):
                decrypted[field_name] = store.decrypt_string(val)
            elif isinstance(val, list):
                decrypted[field_name] = [
                    store.decrypt_string(item) if isinstance(item, str) else item
                    for item in val
                ]
        except Exception:
            pass  # Return encrypted form

    decrypted.pop('_pa_encrypted', None)
    return decrypted


class PAOnboarding:
    """Handles PA establishment through user questionnaire."""

    def __init__(self):
        """Initialize PA onboarding component."""
        self.questions = [
            {
                "key": "primary_goal",
                "question": "What are you trying to accomplish in this conversation?",
                "placeholder": "Tell TELOS what you want to accomplish...",
                "help": "This helps establish your primary purpose"
            },
            {
                "key": "scope_boundaries",
                "question": "What topics should we focus on? What should we avoid?",
                "placeholder": "Focus on: technical details, practical examples... Avoid: unrelated topics, personal info...",
                "help": "This defines the scope and boundaries"
            },
            {
                "key": "success_criteria",
                "question": "How will you know if this conversation is successful?",
                "placeholder": "e.g., I got clear answers, I learned something new, I have actionable next steps...",
                "help": "This sets measurable outcomes"
            },
            {
                "key": "style_preference",
                "question": "Any communication style preferences?",
                "placeholder": "e.g., Technical/Simple, Brief/Detailed, Examples/Theory...",
                "help": "This helps tailor responses to your needs"
            }
        ]

    def render_questionnaire(self) -> Optional[Dict]:
        """
        Render the PA onboarding - templates first, then questionnaire.

        Returns:
            Dict with answers if submitted, None otherwise
        """
        # Check if already completed
        if st.session_state.get('pa_established', False):
            return st.session_state.get('pa_answers')

        # Initialize onboarding step (template_select or template_confirm only)
        if 'pa_onboarding_step' not in st.session_state:
            st.session_state.pa_onboarding_step = 'template_select'

        # Route to appropriate step
        if st.session_state.pa_onboarding_step == 'template_confirm':
            return self._render_template_confirmation()
        else:
            # Default to template selection
            return self._render_template_selection()

    def _render_template_selection(self) -> Optional[Dict]:
        """Render click-to-select template grid."""
        # Scroll to top
        import streamlit.components.v1 as components
        components.html("""
        <script>
        window.parent.scrollTo(0, 0);
        </script>
        """, height=0)

        # Global CSS to constrain content to 700px max-width (matching DEMO mode)
        st.markdown("""
        <style>
        /* Constrain PA onboarding content to 700px like DEMO mode */
        [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
            max-width: 700px !important;
            margin: 0 auto !important;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

        # Display templates in 2-column grid
        for i in range(0, len(PA_TEMPLATES), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                if i + j < len(PA_TEMPLATES):
                    template = PA_TEMPLATES[i + j]
                    with col:
                        self._render_template_card(template)

        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        # Divider line for visual separation
        st.markdown("""
        <div style="
            width: 120px;
            height: 2px;
            background: linear-gradient(90deg, transparent, rgba(244, 208, 63, 0.5), transparent);
            margin: 0 auto 35px auto;
        "></div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Start Fresh", key="start_fresh_btn", use_container_width=True):
                self._start_fresh_mode()
                st.rerun()

        return None

    def _render_template_card(self, template: dict):
        """Render a single template card with click-to-select."""
        # Icons removed per user feedback - looked awkward
        card_html = f"""
        <div style="
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            border: 1px solid #444;
            border-radius: 12px;
            padding: 15px;
            margin: 8px 0;
        ">
            <div style="color: {GOLD}; font-size: 18px; font-weight: bold; margin-bottom: 4px;">
                {html_module.escape(template['title'])}
            </div>
            <div style="color: #aaa; font-size: 13px;">
                {html_module.escape(template['short_desc'])}
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

        if st.button("Select", key=f"select_{template['id']}", use_container_width=True):
            # Store selected template and go to confirmation
            st.session_state.selected_template = template
            st.session_state.pa_onboarding_step = 'template_confirm'
            st.rerun()

    def _render_template_confirmation(self) -> Optional[Dict]:
        """Render confirmation screen for selected template."""
        template = st.session_state.get('selected_template')
        if not template:
            st.session_state.pa_onboarding_step = 'template_select'
            st.rerun()
            return None

        # Scroll to top
        import streamlit.components.v1 as components
        components.html("""
        <script>
        window.parent.scrollTo(0, 0);
        </script>
        """, height=0)

        # Global CSS to constrain content to 700px max-width (matching DEMO mode)
        st.markdown("""
        <style>
        /* Constrain PA confirmation content to 700px like DEMO mode */
        [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
            max-width: 700px !important;
            margin: 0 auto !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # Compact single-page layout: title + description + use cases in one card
        use_cases = self._get_template_use_cases(template['id'])
        use_cases_html = ""
        if use_cases:
            items = ''.join(f'<li>{html_module.escape(uc)}</li>' for uc in use_cases)
            use_cases_html = f'<div style="border-top: 1px solid rgba(244, 208, 63, 0.2); margin-top: 12px; padding-top: 12px;"><div style="color: {GOLD}; font-weight: bold; font-size: 15px; margin-bottom: 6px;">Example use cases</div><ul style="color: #ccc; font-size: 14px; line-height: 1.6; padding-left: 20px; margin: 0;">{items}</ul></div>'

        st.markdown(f"""<style>@keyframes templateFadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}</style><div style="background: rgba(15, 15, 15, 0.4); border: 1px solid rgba(244, 208, 63, 0.3); border-radius: 12px; padding: 20px 25px; margin: 10px 0; opacity: 0; animation: templateFadeIn 1.0s ease-out forwards;"><div style="margin-bottom: 12px;"><span style="color: {GOLD}; font-size: 24px; font-weight: bold;">{html_module.escape(template['title'])}</span><span style="color: #999; font-size: 16px; margin-left: 10px;">{html_module.escape(template['short_desc'])}</span></div><p style="color: #e0e0e0; font-size: 15px; line-height: 1.6; margin: 0;">{html_module.escape(template['purpose'])}</p>{use_cases_html}</div>""", unsafe_allow_html=True)

        # Spacing before buttons
        st.markdown("<div style='margin: 40px 0;'></div>", unsafe_allow_html=True)

        # Action buttons - static sizing to match DEMO mode
        # Use CSS with fixed max-widths to prevent rescaling
        st.markdown("""
        <style>
        /* Static button container - fixed widths, no rescaling */
        .pa-static-nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 700px;
            margin: 0 auto;
            gap: 20px;
        }
        </style>
        """, unsafe_allow_html=True)

        # Use columns with specific widths for static layout
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("Previous", key="back_to_templates", use_container_width=True):
                st.session_state.pa_onboarding_step = 'template_select'
                st.rerun()
        with col2:
            # Alignment Lens toggle button in center
            lens_open = st.session_state.get('onboarding_alignment_lens_open', False)
            lens_label = "Close Lens" if lens_open else "Alignment Lens"
            if st.button(lens_label, key="onboarding_alignment_lens_btn", use_container_width=True):
                st.session_state.onboarding_alignment_lens_open = not lens_open
                st.rerun()
        with col3:
            if st.button("BETA", type="primary", key="confirm_template", use_container_width=True):
                self._apply_template_pa(template)
                st.rerun()

        # Render Alignment Lens panel if open
        if st.session_state.get('onboarding_alignment_lens_open', False):
            self._render_alignment_lens_panel(template)

        # Add bottom spacing after buttons
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

        return None

    def _get_template_use_cases(self, template_id: str) -> list:
        """Get example use cases for a template."""
        use_cases = {
            "explore_telos": [
                "See how fidelity changes as conversation drifts from or aligns with your purpose",
                "Understand why TELOS intervenes on some responses but not others",
                "Compare native AI responses with TELOS-governed responses"
            ],
            "debug_code": [
                "Trace an error from stack trace to root cause in your codebase",
                "Diagnose why authentication is failing despite correct credentials",
                "Find the subtle logic error causing intermittent test failures"
            ],
            "learn_concept": [
                "Build intuition for recursion before diving into implementation details",
                "Understand why distributed systems require different patterns than monoliths",
                "Connect machine learning concepts to statistical foundations you already know"
            ],
            "write_code": [
                "Implement a caching layer that fits your existing architecture",
                "Build a data pipeline with appropriate error handling and retry logic",
                "Create an API endpoint following your team's conventions"
            ],
            "research_topic": [
                "Compare authentication approaches for a security-sensitive application",
                "Synthesize current thinking on microservices vs monolith tradeoffs",
                "Evaluate evidence for different database choices given your constraints"
            ],
            "creative_writing": [
                "Develop a consistent voice for your technical blog",
                "Craft documentation that guides users to success",
                "Write compelling copy that speaks to your specific audience"
            ],
            "plan_project": [
                "Break a migration into phases with clear go/no-go criteria",
                "Map dependencies to identify what blocks what",
                "Build a timeline that accounts for realistic uncertainties"
            ],
            "review_analyze": [
                "Get architectural feedback before committing to a design direction",
                "Identify which parts of your code would benefit most from refactoring",
                "Find security concerns before they become vulnerabilities"
            ]
        }
        return use_cases.get(template_id, [])

    def _render_alignment_lens_panel(self, template: dict):
        """Render Alignment Lens panel showing User PA and AI PA attractors.

        This gives users visibility into the attractors before starting their
        conversation. Shown when user clicks the Alignment Lens button.
        """
        # Build temporary User PA from template for derivation
        temp_user_pa = {
            "purpose": [template['purpose']],
            "scope": template.get('scope', []),
            "boundaries": template.get('boundaries', []),
        }

        # Derive AI PA from User PA using the dual attractor system
        temp_ai_pa = derive_ai_pa_from_user_pa(temp_user_pa)

        # Extract the AI purpose statement
        ai_purpose = temp_ai_pa.get('purpose', [''])[0] if temp_ai_pa.get('purpose') else ''

        # Alignment Lens Header
        st.markdown(f"""
        <div style="
            text-align: center;
            margin: 20px 0 15px 0;
        ">
            <span style="
                color: {GOLD};
                font-size: 18px;
                font-weight: bold;
            ">Alignment Lens</span>
            <div style="color: #888; font-size: 12px; margin-top: 5px;">
                How TELOS will govern this conversation
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Two-column layout for User PA and AI PA
        col1, col2 = st.columns(2)

        with col1:
            # User PA (What you want)
            st.markdown(f"""
            <div style="
                background: rgba(15, 15, 15, 0.4);
                border: 1px solid rgba(244, 208, 63, 0.4);
                border-radius: 10px;
                padding: 15px;
                height: 100%;
            ">
                <div style="
                    color: {GOLD};
                    font-size: 14px;
                    font-weight: bold;
                    margin-bottom: 8px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">Your Purpose</div>
                <div style="
                    color: #e0e0e0;
                    font-size: 14px;
                    line-height: 1.5;
                ">{html_module.escape(template['purpose'])}</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            # AI PA (How AI will help)
            st.markdown(f"""
            <div style="
                background: rgba(15, 15, 15, 0.4);
                border: 1px solid rgba(244, 208, 63, 0.4);
                border-radius: 10px;
                padding: 15px;
                height: 100%;
            ">
                <div style="
                    color: {GOLD};
                    font-size: 14px;
                    font-weight: bold;
                    margin-bottom: 8px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">AI's Role</div>
                <div style="
                    color: #e0e0e0;
                    font-size: 14px;
                    line-height: 1.5;
                ">{html_module.escape(ai_purpose)}</div>
            </div>
            """, unsafe_allow_html=True)

    def _apply_template_pa(self, template: dict):
        """Apply a selected template as the PA.

        Uses dual attractor derivation to create mathematically coupled AI PA.
        """
        # Convert template to PA structure
        pa_data = template_to_pa(template)

        # Create User PA structure (format for dual attractor: purpose as list)
        # NEW (2025-12-28): Include example_queries for centroid embedding computation
        user_pa = {
            "purpose": [pa_data.get('purpose', [template['purpose']])[0] if isinstance(pa_data.get('purpose'), list) else template['purpose']],
            "scope": pa_data.get('scope', template['scope']),
            "boundaries": pa_data.get('boundaries', template['boundaries']),
            "success_criteria": f"Accomplish: {template['purpose']}",
            "style": pa_data.get('style', template.get('style', 'Adaptive')),
            "established_turn": 0,
            "establishment_method": f"template_{template['id']}",
            # NEW: Include example_queries for PA centroid computation
            "example_queries": pa_data.get('example_queries', template.get('example_queries', [])),
        }

        # DUAL ATTRACTOR: Derive AI PA from User PA using intent-to-role mapping
        ai_pa = derive_ai_pa_from_user_pa(user_pa)

        # Load pre-computed embeddings for templates (fast path - avoids model loading)
        template_id = template.get('id', '')
        embeddings_loaded = False

        try:
            import json
            from pathlib import Path
            embeddings_file = Path(__file__).parent.parent / 'config' / 'pa_template_embeddings.json'

            if embeddings_file.exists():
                with open(embeddings_file, 'r') as f:
                    all_embeddings = json.load(f)

                if template_id in all_embeddings:
                    cached_data = all_embeddings[template_id]
                    user_embedding = cached_data.get('user_pa_embedding')
                    ai_embedding = cached_data.get('ai_pa_embedding')

                    if user_embedding and ai_embedding:
                        st.session_state.cached_user_pa_embedding = user_embedding
                        st.session_state.cached_ai_pa_embedding = ai_embedding
                        # NOTE: Do NOT set cached_st_user_pa_embedding here!
                        # The pre-computed embeddings are 1024-dim (Mistral), but
                        # cached_st_user_pa_embedding must be 384-dim (SentenceTransformer).
                        # Let beta_response_manager.py compute the ST embedding fresh.
                        embeddings_loaded = True
        except Exception:
            import logging
            logging.debug("Failed to load pre-computed embeddings for template", exc_info=True)

        # Fallback: compute embeddings if pre-computed not available
        if not embeddings_loaded:
            try:
                from telos_core.embedding_provider import get_cached_minilm_provider
                embedding_provider = get_cached_minilm_provider()
                user_embedding, ai_embedding = compute_pa_embeddings(user_pa, ai_pa, embedding_provider)
                st.session_state.cached_user_pa_embedding = user_embedding
                st.session_state.cached_ai_pa_embedding = ai_embedding
                # CRITICAL: Also cache as cached_st_user_pa_embedding for adaptive context
                # These embeddings are already 384-dim from MiniLM, so this is correct
                st.session_state.cached_st_user_pa_embedding = user_embedding
            except Exception:
                import logging
                logging.debug("Failed to compute PA embeddings at template establishment", exc_info=True)

        # Store both PAs in session state
        st.session_state.primacy_attractor = user_pa
        st.session_state.user_pa = user_pa
        st.session_state.ai_pa = ai_pa  # This makes the derived AI PA available for display
        st.session_state.pa_established = True
        st.session_state.pa_establishment_time = datetime.now().isoformat()
        _encrypt_pa_in_session_state()

        # CRITICAL: Enable rescaled fidelity mode for adaptive context to work
        # Without this flag, the adaptive context system is bypassed entirely
        st.session_state.use_rescaled_fidelity_mode = True

        # CRITICAL: Set PA identity hash so beta_response_manager recognizes cached embeddings
        # This must match EXACTLY how beta_response_manager.py computes current_pa_identity (lines 1648-1733)
        purpose_raw = user_pa.get('purpose', '')
        scope_raw = user_pa.get('scope', [])
        purpose_str = ' '.join(purpose_raw) if isinstance(purpose_raw, list) else purpose_raw
        scope_str = ' '.join(scope_raw) if isinstance(scope_raw, list) else scope_raw
        import hashlib
        st.session_state.cached_pa_identity = hashlib.md5(f"{purpose_str}|{scope_str}".encode()).hexdigest()[:16]
        st.session_state.pa_answers = {
            'primary_goal': template['purpose'],
            'scope_boundaries': ", ".join(template['scope']),
            'success_criteria': f"Accomplish: {template['purpose']}",
            'style_preference': template.get('style', 'Adaptive')
        }

        # Update state manager
        if 'state_manager' in st.session_state:
            st.session_state.state_manager.state.primacy_attractor = user_pa
            st.session_state.state_manager.state.user_pa_established = True
            st.session_state.state_manager.state.convergence_turn = 0
            st.session_state.state_manager.state.pa_converged = True

            if hasattr(st.session_state.state_manager, '_telos_steward'):
                delattr(st.session_state.state_manager, '_telos_steward')

            if 'beta_response_manager' in st.session_state:
                brm = st.session_state.beta_response_manager
                for attr in ['telos_engine', 'ps_calculator', 'user_pa_embedding', 'ai_pa_embedding', 'embedding_provider']:
                    if hasattr(brm, attr):
                        setattr(brm, attr, None)

        # Initialize BETA sequence
        from telos_observatory.services.beta_sequence_generator import BetaSequenceGenerator
        generator = BetaSequenceGenerator()
        st.session_state.beta_sequence = generator.generate_session_sequence()
        st.session_state.beta_current_turn = 1

    def _render_questionnaire_step(self) -> Optional[Dict]:
        """
        Render the traditional questionnaire (fallback from templates).

        Returns:
            Dict with answers if submitted, None otherwise
        """

        # Scroll to top of page when PA onboarding is shown
        import streamlit.components.v1 as components
        components.html("""
        <script>
        // Scroll the parent window to the top
        window.parent.scrollTo(0, 0);
        // Also try scrolling the main container
        const mainContainer = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
        if (mainContainer) {
            mainContainer.scrollTo(0, 0);
        }
        // Scroll any scrollable ancestor
        const scrollables = window.parent.document.querySelectorAll('[data-testid="stVerticalBlock"]');
        scrollables.forEach(el => el.scrollTo(0, 0));
        </script>
        """, height=0)

        # Header with explanation
        st.markdown(f"""
        <div style="
            background: rgba(15, 15, 15, 0.4);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(244, 208, 63, 0.5);
            border-top: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 15px;
            padding: 30px;
            margin: 20px 0;
            box-shadow:
                0 8px 32px rgba(0, 0, 0, 0.3),
                inset 0 1px 0 rgba(255, 255, 255, 0.08);
        ">
            <div style="text-align: center; margin-bottom: 20px;">
                <div style="color: {GOLD}; font-size: 32px; font-weight: bold; margin-bottom: 15px;">
                    Let's Establish Your Purpose
                </div>
                <div style="color: #e0e0e0; font-size: 20px; margin-top: 10px; line-height: 1.6;">
                    TELOS works best when it understands your goals.
                    These quick questions help establish your "Primacy Attractor" -
                    the core purpose that will guide our conversation.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Initialize question index
        if 'pa_current_question' not in st.session_state:
            st.session_state.pa_current_question = 0

        # Progress indicator - styled to match container
        current_q = st.session_state.get('pa_current_question', 0)
        progress = (current_q / len(self.questions)) if current_q < len(self.questions) else 1.0

        # Styled progress section
        st.markdown(f"""
        <div style="
            background: rgba(15, 15, 15, 0.35);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(244, 208, 63, 0.3);
            border-radius: 10px;
            padding: 15px 20px;
            margin: 0 0 20px 0;
            text-align: center;
        ">
            <div style="color: {GOLD}; font-size: 16px; font-weight: 500; margin-bottom: 10px;">
                Question {min(current_q + 1, len(self.questions))} of {len(self.questions)}
            </div>
            <div style="
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                height: 8px;
                overflow: hidden;
            ">
                <div style="
                    background: linear-gradient(90deg, {GOLD}, #e6c238);
                    height: 100%;
                    width: {int(progress * 100)}%;
                    border-radius: 10px;
                    transition: width 0.3s ease;
                "></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Questionnaire form
        with st.form(key="pa_onboarding_form"):
            answers = {}

            # Show current question prominently
            if current_q < len(self.questions):
                q = self.questions[current_q]

                st.markdown(f"""
                <div style="
                    background: rgba(15, 15, 15, 0.35);
                    backdrop-filter: blur(10px);
                    -webkit-backdrop-filter: blur(10px);
                    border: 1px solid rgba(244, 208, 63, 0.4);
                    border-top: 1px solid rgba(255, 255, 255, 0.15);
                    border-radius: 10px;
                    padding: 20px;
                    margin: 15px 0;
                    box-shadow:
                        0 4px 20px rgba(0, 0, 0, 0.25),
                        inset 0 1px 0 rgba(255, 255, 255, 0.05);
                ">
                    <div style="color: {GOLD}; font-size: 22px; font-weight: bold; margin-bottom: 10px;">
                        {q['question']}
                    </div>
                    <div style="color: #999; font-size: 16px;">
                        {q['help']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Add CSS to increase text area font size
                st.markdown("""
                <style>
                textarea {
                    font-size: 20px !important;
                    line-height: 1.6 !important;
                }
                </style>
                """, unsafe_allow_html=True)

                # Add JavaScript to submit form on Enter key (Shift+Enter for new line)
                import streamlit.components.v1 as components
                components.html("""
                <script>
                // Wait for DOM to be ready
                setTimeout(function() {
                    // Find the textarea in the parent document
                    const textareas = window.parent.document.querySelectorAll('textarea');
                    textareas.forEach(function(textarea) {
                        // Only add listener once
                        if (!textarea.dataset.enterHandlerAdded) {
                            textarea.dataset.enterHandlerAdded = 'true';
                            textarea.addEventListener('keydown', function(e) {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    // Find the submit button (Next or Complete)
                                    const buttons = window.parent.document.querySelectorAll('button[kind="secondaryFormSubmit"], button[data-testid="stFormSubmitButton"]');
                                    // Look for Next or Complete button (rightmost button in the form)
                                    for (let btn of buttons) {
                                        const text = btn.textContent || btn.innerText;
                                        if (text.includes('Next') || text.includes('Complete')) {
                                            btn.click();
                                            break;
                                        }
                                    }
                                }
                            });
                        }
                    });
                }, 500);
                </script>
                """, height=0)

                # Input field - Load previous answer if exists
                previous_answer = st.session_state.get('pa_answers', {}).get(q['key'], '')
                answer = st.text_area(
                    "Your answer:",
                    value=previous_answer,  # Pre-populate with saved answer
                    placeholder=q['placeholder'],
                    height=100,
                    max_chars=500,
                    key=f"pa_{q['key']}_{current_q}",  # Unique key per question to force refresh
                    label_visibility="collapsed"
                )

                # Store answer (strip control characters)
                if answer:
                    answer = ''.join(c for c in answer if ord(c) >= 32 or c in '\n\t')
                    answers[q['key']] = answer

                # Navigation buttons
                col1, col2, col3 = st.columns([2, 1, 2])

                with col1:
                    if current_q > 0:
                        if st.form_submit_button("← Previous"):
                            # Save current answer before moving back
                            if answer:
                                if 'pa_answers' not in st.session_state:
                                    st.session_state.pa_answers = {}
                                st.session_state.pa_answers[q['key']] = answer
                            st.session_state.pa_current_question = max(0, current_q - 1)
                            st.rerun()
                    else:
                        # On first question, show "Back to Templates" button
                        if st.form_submit_button("← Back to Templates"):
                            st.session_state.pa_onboarding_step = 'template_select'
                            st.rerun()

                with col2:
                    # Skip button (optional questions)
                    if current_q >= 2:  # Only first 2 are required
                        if st.form_submit_button("Skip"):
                            # Save current answer even if skipping (if provided)
                            if answer:
                                if 'pa_answers' not in st.session_state:
                                    st.session_state.pa_answers = {}
                                st.session_state.pa_answers[q['key']] = answer
                            st.session_state.pa_current_question = current_q + 1
                            st.rerun()

                with col3:
                    if current_q < len(self.questions) - 1:
                        if st.form_submit_button("Next →"):
                            if answer:  # Only proceed if answered
                                # Store answer
                                if 'pa_answers' not in st.session_state:
                                    st.session_state.pa_answers = {}
                                st.session_state.pa_answers[q['key']] = answer
                                st.session_state.pa_current_question = current_q + 1
                                st.rerun()
                            else:
                                st.error("Please provide an answer or skip (if available)")
                    else:
                        # Final question - complete button
                        if st.form_submit_button("✅ Complete Setup"):
                            if answer:
                                if 'pa_answers' not in st.session_state:
                                    st.session_state.pa_answers = {}
                                st.session_state.pa_answers[q['key']] = answer

                                # Mark as complete
                                st.session_state.pa_established = True
                                st.session_state.pa_establishment_time = datetime.now().isoformat()

                                # Extract PA from answers
                                self._extract_pa_from_answers()
                                _encrypt_pa_in_session_state()

                                # Initialize BETA sequence for 5-turn TELOS demo
                                from telos_observatory.services.beta_sequence_generator import BetaSequenceGenerator
                                generator = BetaSequenceGenerator()
                                st.session_state.beta_sequence = generator.generate_session_sequence()
                                st.session_state.beta_current_turn = 1  # Start at turn 1

                                st.success("✅ Your Primacy Attractor has been established!")
                                st.rerun()

        # Show summary of previous answers
        if current_q > 0 and 'pa_answers' in st.session_state:
            with st.expander("Your previous answers"):
                for i in range(current_q):
                    if i < len(self.questions):
                        q_key = self.questions[i]['key']
                        if q_key in st.session_state.pa_answers:
                            st.markdown(f"**{self.questions[i]['question']}**")
                            st.markdown(st.session_state.pa_answers[q_key])
                            st.markdown("---")

        return None

    def _extract_pa_from_answers(self):
        """Extract and structure PA from questionnaire answers.

        Uses dual attractor derivation to create mathematically coupled AI PA.
        """
        answers = st.session_state.get('pa_answers', {})

        # Structure the User PA (format for dual attractor: purpose as list)
        user_pa = {
            "purpose": [answers.get('primary_goal', 'General assistance')],
            "scope": [answers.get('scope_boundaries', 'Open discussion')],
            "boundaries": self._extract_boundaries(answers.get('scope_boundaries', '')),
            "success_criteria": answers.get('success_criteria', 'Helpful conversation'),
            "style": answers.get('style_preference', 'Adaptive'),
            "established_turn": 2,
            "establishment_method": "explicit_questionnaire"
        }

        # DUAL ATTRACTOR: Derive AI PA from User PA using intent-to-role mapping
        ai_pa = derive_ai_pa_from_user_pa(user_pa)

        # Store both PAs in session state
        st.session_state.primacy_attractor = user_pa
        st.session_state.user_pa = user_pa
        st.session_state.ai_pa = ai_pa  # This makes the derived AI PA available for display

        # Compute and cache embeddings at establishment time
        try:
            from telos_core.embedding_provider import get_cached_minilm_provider
            embedding_provider = get_cached_minilm_provider()
            user_embedding, ai_embedding = compute_pa_embeddings(user_pa, ai_pa, embedding_provider)

            # Cache embeddings - no lazy computation needed
            st.session_state.cached_user_pa_embedding = user_embedding
            st.session_state.cached_ai_pa_embedding = ai_embedding
        except Exception:
            # Log but don't fail - embeddings will be computed lazily if needed
            import logging
            logging.debug("Failed to compute PA embeddings at establishment", exc_info=True)

        # Also store for state manager
        if 'state_manager' in st.session_state:
            st.session_state.state_manager.state.primacy_attractor = user_pa
            st.session_state.state_manager.state.user_pa_established = True
            st.session_state.state_manager.state.convergence_turn = 2
            st.session_state.state_manager.state.pa_converged = True

            # Force TELOS steward to re-initialize with new PA
            if hasattr(st.session_state.state_manager, '_telos_steward'):
                delattr(st.session_state.state_manager, '_telos_steward')

            # ALSO delete BETA response manager's telos_engine AND all dual PA components
            # to force full re-initialization with new PA
            if 'beta_response_manager' in st.session_state:
                brm = st.session_state.beta_response_manager
                if hasattr(brm, 'telos_engine'):
                    brm.telos_engine = None
                if hasattr(brm, 'ps_calculator'):
                    brm.ps_calculator = None
                if hasattr(brm, 'user_pa_embedding'):
                    brm.user_pa_embedding = None
                if hasattr(brm, 'ai_pa_embedding'):
                    brm.ai_pa_embedding = None
                if hasattr(brm, 'embedding_provider'):
                    brm.embedding_provider = None

        return user_pa

    def _extract_boundaries(self, scope_text: str) -> list:
        """Extract boundary keywords from scope text."""
        boundaries = []

        # Look for "avoid" patterns
        if "avoid" in scope_text.lower():
            parts = scope_text.lower().split("avoid")
            if len(parts) > 1:
                avoid_text = parts[1].split(".")[0]
                boundaries = [b.strip() for b in avoid_text.split(",")]

        # If no boundaries extracted, provide sensible defaults
        if not boundaries:
            boundaries = [
                "Stay focused on stated purpose",
                "Avoid unrelated tangents",
                "Maintain productive dialogue"
            ]

        return boundaries

    def _apply_default_pa(self):
        """
        Apply a default TELOS-focused PA for quick start.

        Skips the questionnaire entirely and sets up a sensible default
        PA focused on TELOS exploration and testing.
        """
        # Default answers for TELOS testing
        default_answers = {
            'primary_goal': 'Explore and test TELOS Observatory capabilities, understand AI governance through purposeful conversation',
            'scope_boundaries': 'Focus on: AI governance, TELOS features, meaningful dialogue. Avoid: completely unrelated tangents',
            'success_criteria': 'Productive conversation that demonstrates TELOS principles and stays purposefully aligned',
            'style_preference': 'Natural, conversational, thoughtful'
        }

        # Store answers
        st.session_state.pa_answers = default_answers

        # Structure the PA
        pa = {
            "purpose": default_answers['primary_goal'],
            "scope": default_answers['scope_boundaries'],
            "boundaries": [
                "Stay focused on TELOS exploration",
                "Maintain productive dialogue",
                "Allow natural conversation flow"
            ],
            "success_criteria": default_answers['success_criteria'],
            "style": default_answers['style_preference'],
            "established_turn": 0,  # Instant establishment
            "establishment_method": "quick_start_default"
        }

        # Store in session state
        st.session_state.primacy_attractor = pa
        st.session_state.pa_established = True
        st.session_state.pa_establishment_time = datetime.now().isoformat()
        _encrypt_pa_in_session_state()

        # Also store for state manager
        if 'state_manager' in st.session_state:
            st.session_state.state_manager.state.primacy_attractor = pa
            st.session_state.state_manager.state.user_pa_established = True
            st.session_state.state_manager.state.convergence_turn = 0
            st.session_state.state_manager.state.pa_converged = True

            # Force TELOS steward to re-initialize with new PA
            if hasattr(st.session_state.state_manager, '_telos_steward'):
                delattr(st.session_state.state_manager, '_telos_steward')

            # ALSO delete BETA response manager's telos_engine AND all dual PA components
            # to force full re-initialization with new PA
            if 'beta_response_manager' in st.session_state:
                brm = st.session_state.beta_response_manager
                if hasattr(brm, 'telos_engine'):
                    brm.telos_engine = None
                if hasattr(brm, 'ps_calculator'):
                    brm.ps_calculator = None
                if hasattr(brm, 'user_pa_embedding'):
                    brm.user_pa_embedding = None
                if hasattr(brm, 'ai_pa_embedding'):
                    brm.ai_pa_embedding = None
                if hasattr(brm, 'embedding_provider'):
                    brm.embedding_provider = None

        # Initialize BETA sequence for 5-turn TELOS demo
        from telos_observatory.services.beta_sequence_generator import BetaSequenceGenerator
        generator = BetaSequenceGenerator()
        st.session_state.beta_sequence = generator.generate_session_sequence()
        st.session_state.beta_current_turn = 1  # Start at turn 1

        return pa

    def _start_fresh_mode(self):
        """
        Start fresh mode - skip PA establishment and derive from first message.

        Sets a flag indicating PA needs to be derived from turn 1.
        The actual derivation happens in beta_response_manager.
        """
        # Mark PA as "pending derivation from turn 1"
        st.session_state.pa_pending_derivation = True
        st.session_state.pa_established = True  # Allow chat to start
        st.session_state.pa_establishment_time = datetime.now().isoformat()

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

        # Update state manager
        if 'state_manager' in st.session_state:
            st.session_state.state_manager.state.primacy_attractor = placeholder_pa
            st.session_state.state_manager.state.user_pa_established = False  # Not really established yet
            st.session_state.state_manager.state.pa_converged = False

        # Initialize BETA sequence
        from telos_observatory.services.beta_sequence_generator import BetaSequenceGenerator
        generator = BetaSequenceGenerator()
        st.session_state.beta_sequence = generator.generate_session_sequence()
        st.session_state.beta_current_turn = 1

    def render_pa_summary(self):
        """Render a summary of the established PA."""
        if not st.session_state.get('pa_established', False):
            return

        pa = st.session_state.get('primacy_attractor', {})

        st.markdown("""
        <div style="
            background-color: #1a1a1a;
            border: 1px solid #27ae60;
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
        ">
            <div style="color: #27ae60; font-size: 16px; font-weight: bold; margin-bottom: 10px;">
                ✅ Your Primacy Attractor is Active
            </div>
            <div style="color: #e0e0e0; font-size: 14px;">
                <strong>Purpose:</strong> {purpose}<br>
                <strong>Scope:</strong> {scope}<br>
                <strong>Success:</strong> {success}
            </div>
        </div>
        """.format(
            purpose=html_module.escape(str(pa.get('purpose', 'Not set'))),
            scope=html_module.escape(str(pa.get('scope', 'Not set'))),
            success=html_module.escape(str(pa.get('success_criteria', 'Not set')))
        ), unsafe_allow_html=True)
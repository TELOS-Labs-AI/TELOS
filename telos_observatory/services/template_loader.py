"""
Template Loader Service
=======================

Loads pre-configured session templates and initializes the PA system
with embedded attractors. This allows users to quickly start TELOS-governed
sessions for common use cases like tutoring, research, writing, etc.

The loader:
1. Takes a SessionTemplate from session_templates.py
2. Creates PA embeddings from the template's attractor_config
3. Stores everything in session state for use by BetaResponseManager
4. Sets up the system prompt for the LLM
"""

import streamlit as st
import numpy as np
import logging
from typing import Optional, Dict, Any

from telos_observatory.demo_mode.session_templates import (
    SessionTemplate,
    get_template,
    get_all_templates,
    get_template_choices,
    ALL_TEMPLATES
)

logger = logging.getLogger(__name__)


class TemplateLoader:
    """Service to load session templates and initialize PA embeddings."""

    def __init__(self):
        """Initialize the template loader."""
        self._embedding_provider = None

    def _get_embedding_provider(self):
        """Lazy-load the embedding provider."""
        if self._embedding_provider is None:
            try:
                from telos_core.embedding_provider import MistralEmbeddingProvider
                self._embedding_provider = MistralEmbeddingProvider()
                logger.info("TemplateLoader: MistralEmbeddingProvider initialized")
            except Exception as e:
                logger.error(f"TemplateLoader: Failed to initialize embedding provider: {e}")
                raise
        return self._embedding_provider

    def load_template(self, template_id: str) -> bool:
        """Load a template and initialize the PA system.

        Args:
            template_id: The ID of the template to load (e.g., 'academic_study')

        Returns:
            True if successful, False otherwise
        """
        template = get_template(template_id)
        if template is None:
            logger.error(f"TemplateLoader: Template '{template_id}' not found")
            return False

        try:
            return self._initialize_from_template(template)
        except Exception as e:
            logger.error(f"TemplateLoader: Failed to load template '{template_id}': {e}")
            return False

    def _initialize_from_template(self, template: SessionTemplate) -> bool:
        """Initialize the PA system from a template.

        Args:
            template: The SessionTemplate to load

        Returns:
            True if successful
        """
        logger.info(f"TemplateLoader: Initializing from template '{template.name}'")

        # Get the attractor config
        config = template.attractor_config

        # Extract purpose, scope, boundaries
        purpose_list = config.get('purpose', [])
        scope_list = config.get('scope', [])
        boundaries_list = config.get('boundaries', [])

        # Convert lists to strings for embedding
        purpose_str = '. '.join(purpose_list) if purpose_list else ''
        scope_str = '. '.join(scope_list) if scope_list else ''

        # Build the PA text representations (matching beta_response_manager.py pattern)
        user_pa_text = f"Purpose: {purpose_str}. Scope: {scope_str}."

        # Derive AI PA text with role-based framing
        ai_purpose = self._derive_ai_purpose(purpose_str, template.category)
        ai_pa_text = f"AI Role: {ai_purpose}. Supporting scope: {scope_str}."

        logger.info(f"TemplateLoader: User PA text (first 100 chars): {user_pa_text[:100]}...")
        logger.info(f"TemplateLoader: AI PA text (first 100 chars): {ai_pa_text[:100]}...")

        # Get embedding provider and create embeddings
        embedding_provider = self._get_embedding_provider()

        # Batch encode both PAs for efficiency
        if hasattr(embedding_provider, 'batch_encode'):
            logger.info("TemplateLoader: Using batch embedding")
            embeddings = embedding_provider.batch_encode([user_pa_text, ai_pa_text])
            user_pa_embedding = embeddings[0]
            ai_pa_embedding = embeddings[1]
        else:
            logger.info("TemplateLoader: Using sequential embedding")
            user_pa_embedding = np.array(embedding_provider.encode(user_pa_text))
            ai_pa_embedding = np.array(embedding_provider.encode(ai_pa_text))

        # Store in session state (matching the pattern from beta_pa_establishment.py)
        # 1. Raw PA components (primacy_attractor)
        st.session_state.primacy_attractor = {
            'purpose': purpose_str,
            'scope': scope_str,
            'boundaries': boundaries_list,
            'constraint_tolerance': config.get('constraint_tolerance', 0.2),
            'privacy_level': config.get('privacy_level', 0.8),
            'task_priority': config.get('task_priority', 0.7),
            # Template metadata
            '_template_id': template.id,
            '_template_name': template.name,
            '_template_category': template.category,
        }

        # 2. User PA dict
        st.session_state.user_pa = {
            'purpose': purpose_list,
            'scope': scope_list,
            'boundaries': boundaries_list,
            'constraint_tolerance': config.get('constraint_tolerance', 0.2),
        }

        # 3. AI PA dict (derived)
        st.session_state.ai_pa = {
            'purpose': [ai_purpose],
            'scope': scope_list,
            'boundaries': boundaries_list,
            'role': self._get_role_for_category(template.category),
        }

        # 4. Cached PA embeddings (CRITICAL for deterministic fidelity)
        st.session_state.cached_user_pa_embedding = user_pa_embedding
        st.session_state.cached_ai_pa_embedding = ai_pa_embedding
        logger.info(f"TemplateLoader: PA embeddings cached (dim: {len(user_pa_embedding)})")

        # 5. Establishment flags
        st.session_state.pa_established = True
        st.session_state.beta_pa_established = True
        st.session_state.extracted_pa = st.session_state.primacy_attractor

        # 6. Template-specific system prompt
        st.session_state.template_system_prompt = template.system_prompt

        # 7. Welcome message for display
        st.session_state.template_welcome_message = template.welcome_message

        # 8. Example prompts for UI hints
        st.session_state.template_example_prompts = template.example_prompts

        # 9. Active template tracking
        st.session_state.active_template = template.id
        st.session_state.active_template_name = template.name

        logger.info(f"TemplateLoader: Template '{template.name}' loaded successfully")
        logger.info(f"TemplateLoader: PA established with {len(purpose_list)} purpose items, {len(scope_list)} scope items")

        return True

    def _derive_ai_purpose(self, user_purpose: str, category: str) -> str:
        """Derive the AI's purpose statement from user purpose and category.

        Args:
            user_purpose: The user's purpose statement
            category: The template category (Education, Research, etc.)

        Returns:
            The AI's purpose statement
        """
        # Category-specific role framing
        role_frames = {
            'Education': 'Guide and teach the user as they work to',
            'Research': 'Support rigorous inquiry as the user works to',
            'Wellness': 'Provide compassionate support as the user works to',
            'Creative': 'Collaborate creatively as the user works to',
            'Technical': 'Mentor and guide as the user works to',
        }

        frame = role_frames.get(category, 'Help the user as they work to')
        return f"{frame}: {user_purpose}"

    def _get_role_for_category(self, category: str) -> str:
        """Get the AI role name for a category.

        Args:
            category: The template category

        Returns:
            Role name string
        """
        role_names = {
            'Education': 'Socratic Tutor',
            'Research': 'Research Assistant',
            'Wellness': 'Support Companion',
            'Creative': 'Creative Partner',
            'Technical': 'Code Mentor',
        }
        return role_names.get(category, 'Assistant')

    def get_active_template(self) -> Optional[SessionTemplate]:
        """Get the currently active template, if any.

        Returns:
            The active SessionTemplate or None
        """
        template_id = st.session_state.get('active_template')
        if template_id:
            return get_template(template_id)
        return None

    def clear_template(self):
        """Clear the active template and reset PA state."""
        # Clear template-specific state
        keys_to_clear = [
            'primacy_attractor',
            'user_pa',
            'ai_pa',
            'cached_user_pa_embedding',
            'cached_ai_pa_embedding',
            'pa_established',
            'beta_pa_established',
            'extracted_pa',
            'template_system_prompt',
            'template_welcome_message',
            'template_example_prompts',
            'active_template',
            'active_template_name',
            'beta_welcome_shown',
            'beta_scroll_to_top_done',
        ]

        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]

        logger.info("TemplateLoader: Template cleared, PA state reset")

    @staticmethod
    def get_available_templates() -> list:
        """Get list of available templates for UI display.

        Returns:
            List of template info dicts with id, name, description, category, icon
        """
        return get_template_choices()


def render_template_selector():
    """Render a template selector UI component.

    Returns:
        Selected template ID if one was chosen, None otherwise
    """
    templates = TemplateLoader.get_available_templates()

    # Group by category
    categories = {}
    for t in templates:
        cat = t['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(t)

    st.markdown("### Choose a Session Template")
    st.markdown("Select a pre-configured template to get started quickly, or skip to create your own.")

    selected_template_id = None

    for category, cat_templates in categories.items():
        st.markdown(f"**{category}**")

        cols = st.columns(len(cat_templates))
        for i, template in enumerate(cat_templates):
            with cols[i]:
                # Template card
                st.markdown(f"""
                <div style="
                    border: 1px solid #444;
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 10px;
                    background: #1a1a1a;
                ">
                    <div style="font-size: 24px; text-align: center;">{template['icon']}</div>
                    <div style="font-weight: bold; color: #F4D03F; text-align: center;">{template['name']}</div>
                    <div style="font-size: 12px; color: #888; text-align: center;">{template['description'][:60]}...</div>
                </div>
                """, unsafe_allow_html=True)

                if st.button(f"Use {template['name']}", key=f"template_select_{template['id']}", use_container_width=True):
                    selected_template_id = template['id']

    return selected_template_id

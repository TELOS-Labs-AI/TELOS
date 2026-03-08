"""
Agentic Onboarding -- Agent Type Selection
==========================================
Allows users to select an agent type (SQL Analyst, Research Assistant,
Customer Service) before entering the agentic governance demo.

Two-step pattern matching pa_onboarding.py:
  Step 1: Compact agent cards (name + short description + Select button)
  Step 2: Expanded confirmation (purpose, example use cases, boundaries, Previous/Select)
"""
import html as html_module
import streamlit as st
import streamlit.components.v1 as components
from telos_observatory.agentic.agent_templates import get_agent_templates
from telos_observatory.config.colors import GOLD


class AgenticOnboarding:
    """Agent type selection for agentic governance mode."""

    def render(self):
        """Render agent selection screen. Returns selected template ID or None."""
        # Check if already selected
        if st.session_state.get('agentic_pa_established', False):
            return st.session_state.get('agentic_agent_type')

        # Initialize onboarding step
        if 'agentic_onboarding_step' not in st.session_state:
            st.session_state.agentic_onboarding_step = 'agent_select'

        # Route to appropriate step
        if st.session_state.agentic_onboarding_step == 'agent_confirm':
            return self._render_agent_confirmation()
        else:
            return self._render_agent_selection()

    def _render_agent_selection(self):
        """Step 1: Compact agent cards with name + short description."""
        # Scroll to top
        components.html("""
        <script>
        window.parent.scrollTo(0, 0);
        </script>
        """, height=0)

        templates = get_agent_templates()

        # Header
        st.markdown(f"""
        <div style="text-align: center; padding: 20px 0; max-width: 700px; margin: 0 auto;">
            <h2 style="color: {GOLD}; font-size: 36px; margin: 0;">Agentic AI Governance</h2>
            <p style="color: #e0e0e0; font-size: 16px; margin-top: 10px;">
                Select an agent type to see TELOS governance in action
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

        # Agent cards in 2-column grid (matching pa_onboarding screenshot layout)
        template_list = list(templates.values())
        for i in range(0, len(template_list), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                if i + j < len(template_list):
                    with col:
                        self._render_agent_card(template_list[i + j])

        st.markdown("<div style='margin: 30px 0;'></div>", unsafe_allow_html=True)

        return None

    def _render_agent_card(self, template):
        """Render a single compact agent card with click-to-select."""
        card_html = f"""
        <div style="
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            border: 1px solid #444;
            border-radius: 12px;
            padding: 15px;
            margin: 8px 0;
        ">
            <div style="color: {GOLD}; font-size: 18px; font-weight: bold; margin-bottom: 4px;">
                {html_module.escape(template.name)}
            </div>
            <div style="color: #aaa; font-size: 13px;">
                {html_module.escape(template.description)}
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

        if st.button("Select", key=f"select_agent_{template.id}", use_container_width=True):
            st.session_state.agentic_selected_template = template.id
            st.session_state.agentic_onboarding_step = 'agent_confirm'
            st.rerun()

    def _render_agent_confirmation(self):
        """Step 2: Expanded view with purpose, examples, boundaries, and navigation."""
        templates = get_agent_templates()
        template_id = st.session_state.get('agentic_selected_template')

        if not template_id or template_id not in templates:
            st.session_state.agentic_onboarding_step = 'agent_select'
            st.rerun()
            return None

        template = templates[template_id]

        # Scroll to top
        components.html("""
        <script>
        window.parent.scrollTo(0, 0);
        </script>
        """, height=0)

        # Header with agent name + description
        st.markdown(f"""
        <div style="text-align: center; padding: 20px 0;">
            <h2 style="color: {GOLD}; font-size: 32px; margin: 0;">{html_module.escape(template.name)}</h2>
            <p style="color: #e0e0e0; font-size: 18px; margin-top: 10px;">
                {html_module.escape(template.description)}
            </p>
        </div>
        """, unsafe_allow_html=True)

        # "What this accomplishes" box — purpose + scope
        st.markdown(f"""
        <div style="
            background: rgba(15, 15, 15, 0.4);
            border: 1px solid rgba(244, 208, 63, 0.3);
            border-radius: 12px;
            padding: 20px;
            margin: 20px 0;
        ">
            <h3 style="color: {GOLD}; margin-top: 0;">What this accomplishes</h3>
            <p style="color: #e0e0e0; font-size: 16px; line-height: 1.6;">
                {html_module.escape(template.purpose)}
            </p>
            <p style="color: #ccc; font-size: 15px; line-height: 1.6; margin-top: 10px;">
                <strong style="color: {GOLD};">Scope:</strong> {html_module.escape(template.scope)}
            </p>
        </div>
        """, unsafe_allow_html=True)

        # "Example use cases" box — first 3 example_requests
        examples = template.example_requests[:3]
        examples_html = ''.join(f'<li>{html_module.escape(ex)}</li>' for ex in examples)
        st.markdown(f"""
        <div style="
            background: rgba(15, 15, 15, 0.3);
            border: 1px solid #444;
            border-radius: 12px;
            padding: 20px;
            margin: 20px 0;
        ">
            <h3 style="color: {GOLD}; margin-top: 0;">Example use cases</h3>
            <ul style="color: #ccc; font-size: 15px; line-height: 1.8; padding-left: 20px;">
                {examples_html}
            </ul>
        </div>
        """, unsafe_allow_html=True)

        # "Boundaries" box
        boundaries_html = ''.join(f'<li>{html_module.escape(b)}</li>' for b in template.boundaries)
        st.markdown(f"""
        <div style="
            background: rgba(15, 15, 15, 0.3);
            border: 1px solid #444;
            border-radius: 12px;
            padding: 20px;
            margin: 20px 0;
        ">
            <h3 style="color: {GOLD}; margin-top: 0;">Boundaries</h3>
            <ul style="color: #ccc; font-size: 15px; line-height: 1.8; padding-left: 20px;">
                {boundaries_html}
            </ul>
        </div>
        """, unsafe_allow_html=True)

        # Bottom spacing before buttons
        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

        # Navigation: Previous | Select [Agent Name]
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous", key="agentic_back_to_agents", use_container_width=True):
                st.session_state.agentic_onboarding_step = 'agent_select'
                st.rerun()
        with col2:
            if st.button(f"Select {template.name}", key="agentic_confirm_agent", use_container_width=True):
                st.session_state.agentic_agent_type = template.id
                st.session_state.agentic_pa_established = True
                st.session_state.agentic_current_step = 0
                st.rerun()

        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

        return None

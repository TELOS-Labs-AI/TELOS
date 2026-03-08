"""
Agentic Observation Deck
=========================
Multi-dimensional governance transparency panel showing:
- 5 fidelity dimension scores (Purpose, Scope, Tool, Chain SCI, Boundary)
- Tool palette with ranked fidelity bars
- Action chain timeline
- Decision explanation

Uses exact same styles as beta_observation_deck.py.
"""
import streamlit as st
from telos_observatory.config.colors import (
    GOLD, get_fidelity_color, format_fidelity_percent,
    ZONE_LEGEND_HTML, get_zone_name
)
from telos_observatory.components.tool_palette_panel import render_tool_palette
from telos_observatory.components.action_chain_timeline import render_action_chain


class AgenticObservationDeck:
    """Enhanced observation deck for agentic governance mode."""

    def _get_step_data(self):
        """Get the latest agentic step data from session state."""
        current_step = st.session_state.get('agentic_current_step', 0)
        if current_step < 1:
            return None
        try:
            from telos_observatory.main import get_agentic_step_data
            return get_agentic_step_data(current_step)
        except ImportError:
            return st.session_state.get(f'agentic_step_{current_step}_data', {})

    def _get_composite_fidelity(self, step_data):
        """Compute composite fidelity from the 5 dimensions. Returns (avg_score, color, zone_name)."""
        if not step_data:
            return None, "#888888", "---"

        scores = [
            step_data.get('purpose_fidelity'),
            step_data.get('scope_fidelity'),
            step_data.get('tool_fidelity'),
            step_data.get('chain_sci'),
            step_data.get('boundary_fidelity'),
        ]
        valid = [s for s in scores if s is not None]
        if not valid:
            return None, "#888888", "---"

        avg = sum(valid) / len(valid)
        color = get_fidelity_color(avg)
        zone = get_zone_name(avg)
        return avg, color, zone

    def render(self):
        """Render the agentic observation deck."""
        import streamlit.components.v1 as components

        # Only show after first agentic turn
        if not st.session_state.get('agentic_pa_established', False):
            return

        current_step = st.session_state.get('agentic_current_step', 0)
        if current_step < 1:
            return

        step_data = self._get_step_data()
        if not step_data:
            return

        # Initialize deck visibility state
        if 'agentic_deck_visible' not in st.session_state:
            st.session_state.agentic_deck_visible = False

        # Anchor for auto-scrolling
        st.markdown('<div id="agentic-observation-deck-anchor"></div>', unsafe_allow_html=True)

        # Toggle button - full width, styled with composite fidelity color
        # (same CSS injection pattern as beta_observation_deck.py Alignment Lens button)
        deck_label = "Hide Governance Panel" if st.session_state.agentic_deck_visible else "Show Governance Panel"

        composite_score, composite_color, composite_zone = self._get_composite_fidelity(step_data)
        btn_color = composite_color if composite_score is not None else "#27ae60"

        # CSS injection using marker div + adjacent sibling selector (proven pattern from conversation_display.py)
        # This targets the button container immediately following the marker div
        st.markdown(f"""
<style>
/* Governance Panel button - composite fidelity colored border */
.agentic-deck-btn-marker + div button {{
    background-color: #2d2d2d !important;
    border: 2px solid {btn_color} !important;
    color: #e0e0e0 !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    padding: 12px 24px !important;
    transition: all 0.2s ease !important;
}}
.agentic-deck-btn-marker + div button:hover {{
    background-color: #3d3d3d !important;
    box-shadow: 0 0 12px {btn_color} !important;
    border: 2px solid {btn_color} !important;
}}
</style>
<div class="agentic-deck-btn-marker" style="display:none;"></div>
""", unsafe_allow_html=True)

        if st.button(deck_label, key="agentic_deck_toggle_top", use_container_width=True):
            st.session_state.agentic_deck_visible = not st.session_state.agentic_deck_visible
            # Set flag to auto-scroll only when opening (not on every render)
            if st.session_state.agentic_deck_visible:
                st.session_state.agentic_deck_just_opened = True
            st.rerun()

        # Render deck content if visible
        if st.session_state.agentic_deck_visible:
            # Auto-scroll to anchor ONLY when just opened (same as beta_observation_deck.py)
            if st.session_state.get('agentic_deck_just_opened', False):
                st.session_state.agentic_deck_just_opened = False
                components.html("""
<script>
    // Scroll parent window to the Governance Panel anchor element
    setTimeout(function() {
        var anchor = window.parent.document.getElementById('agentic-observation-deck-anchor');
        if (anchor) {
            anchor.scrollIntoView({behavior: 'smooth', block: 'start'});
        } else {
            window.parent.document.documentElement.scrollTo({
                top: window.parent.document.documentElement.scrollHeight - window.parent.innerHeight + 100,
                behavior: 'smooth'
            });
        }
    }, 150);
</script>
""", height=0)

            # Animation styles (same as beta_observation_deck.py)
            st.markdown("""
<style>
@keyframes obsDeckFadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)

            # Consistent top spacing
            st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

            # Render header bar (same style as beta_observation_deck.py _render_alignment_lens_header)
            self._render_header(step_data)

            # Render 5-box fidelity row
            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
            self._render_fidelity_row(step_data)

            # SAAI drift status
            self._render_saai_status(step_data)

            # Tool palette
            tool_rankings = step_data.get('tool_rankings', [])
            if tool_rankings:
                st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
                render_tool_palette(tool_rankings)

            # Action chain timeline
            chain_steps = st.session_state.get('agentic_chain_steps', [])
            if chain_steps:
                st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
                render_action_chain(chain_steps)

            # Decision explanation
            explanation = step_data.get('decision_explanation', '')
            if explanation:
                st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
                st.markdown(f"""
<div class="message-container" style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 1px solid #F4D03F; border-radius: 8px; padding: 20px; margin: 10px 0; box-shadow: 0 0 15px rgba(244, 208, 63, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
    <h3 style="color: #F4D03F; margin-top: 0;">Decision Explanation</h3>
    <p style="color: #e0e0e0; font-size: 19px; line-height: 1.6;">
        {explanation}
    </p>
</div>
""", unsafe_allow_html=True)

    def _render_header(self, step_data):
        """Render the Governance Panel header bar (same style as beta_observation_deck.py _render_alignment_lens_header)."""
        composite_score, composite_color, composite_zone = self._get_composite_fidelity(step_data)

        # Determine drift status (same logic as beta_observation_deck.py)
        if composite_score is None:
            drift_status = "Aligned"
            drift_color = "#27ae60"
        elif composite_score >= 0.70:
            drift_status = "Aligned"
            drift_color = "#27ae60"
        elif composite_score >= 0.60:
            drift_status = "Minor Drift"
            drift_color = "#F4D03F"
        elif composite_score >= 0.50:
            drift_status = "Moderate Drift"
            drift_color = "#FFA500"
        else:
            drift_status = "Severe Drift"
            drift_color = "#FF4444"

        # Generate glow from composite color (same helper as beta_observation_deck.py)
        def get_glow_color(hex_color):
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return f"rgba({r}, {g}, {b}, 0.3)"

        glow = get_glow_color(composite_color)

        # Compact horizontal bar design - title on left, status on right (same as beta_observation_deck.py)
        st.markdown(f"""
<div style="max-width: 100%; margin: 0 auto; opacity: 0; animation: obsDeckFadeIn 1.0s ease-in-out forwards;">
    <div style="background-color: #1a1a1a; border: 2px solid {composite_color}; border-radius: 8px; padding: 12px 20px; box-shadow: 0 0 15px {glow}; display: flex; justify-content: space-between; align-items: center;">
        <span style="color: {composite_color}; font-size: 18px; font-weight: bold;">Governance Panel</span>
        <span style="background-color: #2d2d2d; border: 1px solid {drift_color}; border-radius: 15px; padding: 5px 15px; color: {drift_color}; font-weight: bold; font-size: 13px;">{drift_status}</span>
    </div>
</div>
""", unsafe_allow_html=True)

    def _render_fidelity_row(self, step_data):
        """Render 5-box fidelity row (same style as beta_observation_deck.py _render_fidelity_row)."""
        metrics = [
            ("Purpose Fidelity", step_data.get('purpose_fidelity')),
            ("Scope Fidelity", step_data.get('scope_fidelity')),
            ("Tool Fidelity", step_data.get('tool_fidelity')),
            ("Chain SCI", step_data.get('chain_sci')),
            ("Boundary Check", step_data.get('boundary_fidelity')),
        ]

        # Helper to convert hex color to rgba glow (same as beta_observation_deck.py)
        def get_glow_color(hex_color):
            """Convert hex color to rgba glow."""
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return f"rgba({r}, {g}, {b}, 0.4)"

        # Zone legend - helps first-time users understand the system (same as beta_observation_deck.py)
        st.markdown(ZONE_LEGEND_HTML, unsafe_allow_html=True)

        # Build flex boxes HTML (same HTML flex layout as beta_observation_deck.py _render_fidelity_row)
        boxes_html = ""
        for name, score in metrics:
            if score is not None:
                color = get_fidelity_color(score)
                pct = format_fidelity_percent(score)
                zone = get_zone_name(score)
                zone_color = color
            else:
                color = "#888888"
                pct = "---"
                zone = "---"
                zone_color = "#888"

            glow = get_glow_color(color)

            boxes_html += f"""
    <div style="background-color: #1a1a1a; border: 2px solid {color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1; box-shadow: 0 4px 20px {glow};">
        <div style="color: {color}; font-size: 16px; font-weight: bold; margin-bottom: 10px;">{name}</div>
        <div style="color: {color}; font-size: 38px; font-weight: bold;">{pct}</div>
        <div style="color: {zone_color}; font-size: 13px; margin-top: 8px;">{zone}</div>
    </div>"""

        # Full-width fidelity boxes with percentage display (same flex layout as beta_observation_deck.py)
        st.markdown(f"""
<div style="display: flex; justify-content: center; gap: 10px; margin: 15px auto; max-width: 100%;">
    {boxes_html}
</div>
""", unsafe_allow_html=True)

    def _render_saai_status(self, step_data):
        """Render SAAI cumulative drift status badge."""
        drift_level = step_data.get('drift_level', 'NORMAL')
        drift_magnitude = step_data.get('drift_magnitude', 0.0)
        baseline_established = step_data.get('saai_baseline') is not None

        # Color mapping for SAAI tiers
        saai_colors = {
            "NORMAL": "#27ae60",
            "WARNING": "#F4D03F",
            "RESTRICT": "#e67e22",
            "BLOCK": "#e74c3c",
        }
        color = saai_colors.get(drift_level, "#888888")
        drift_pct = f"{drift_magnitude:.1%}"
        baseline_label = "Baseline established" if baseline_established else "Collecting baseline..."

        st.markdown(f"""
<div style="margin: 12px auto; max-width: 100%;">
    <div style="background-color: #1a1a1a; border: 1px solid {color}; border-radius: 8px; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center;">
        <span style="color: #b0b0b0; font-size: 14px;">SAAI Drift</span>
        <span style="display: flex; align-items: center; gap: 12px;">
            <span style="color: #b0b0b0; font-size: 13px;">{baseline_label}</span>
            <span style="color: #b0b0b0; font-size: 13px;">Drift: {drift_pct}</span>
            <span style="background-color: {color}; color: #1a1a1a; border-radius: 4px; padding: 3px 10px; font-weight: bold; font-size: 12px;">{drift_level}</span>
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

"""
Observation Deck Component for TELOS Observatory V3.
Right panel with gold-themed statistics windows that slides in when Strip is clicked.
"""

import html
import streamlit as st

from telos_observatory.config.colors import get_fidelity_color
from telos_observatory.config.steward_pa import STEWARD_PA


class ObservationDeck:
    """Gold-themed observation deck with statistics windows."""

    def __init__(self, state_manager):
        """Initialize with state manager reference.

        Args:
            state_manager: StateManager instance for turn data
        """
        self.state_manager = state_manager

    def render(self):
        """Render the observation deck panel."""
        # Don't render anything if we're in demo mode on the observation deck slide (index 4)
        # (that slide has its own embedded observation deck)
        mode = st.session_state.get('active_tab', 'DEMO')
        demo_slide_index = st.session_state.get('demo_slide_index', 0)
        if mode == 'DEMO' and demo_slide_index == 4:
            return

        turn_data = self.state_manager.get_current_turn_data()

        # Always show expanded content when rendered
        # (visibility is controlled by the button in main.py)

        st.markdown("---")

        # Show demo PA if no turn data yet (for demo slides)
        if not turn_data:
            self._render_demo_pa()
        else:
            # Metrics readout section
            self._render_metrics(turn_data)

        # Only show View Options in BETA mode or higher (not in DEMO)
        mode = st.session_state.get('active_tab', 'DEMO')
        if mode != 'DEMO':
            st.markdown("---")
            # View Options Toggles
            self._render_view_options()

        # Add navigation and Hide button at bottom of expanded Observation Deck
        st.markdown("---")

        # ALWAYS show 3-button navigation layout (Previous/Hide/Next)
        # Mode detection happens in parent, we just render the controls
        demo_slide_index = st.session_state.get('demo_slide_index', 0)

        # Render navigation row without background
        st.markdown("<div style='margin: 20px 0; padding: 10px;'>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)

        with col1:
            # Always show button, enable/disable based on slide position
            is_disabled = (demo_slide_index <= 0)
            if st.button(
                "⬅️ Previous",
                key="obs_deck_prev",
                use_container_width=True,
                disabled=is_disabled,
                help="Go to previous slide" if not is_disabled else "Already at first slide",
                type="secondary"
            ):
                if demo_slide_index > 0:
                    st.session_state.demo_slide_index = max(0, demo_slide_index - 1)
                    st.rerun()

        with col2:
            if st.button(
                "Hide Observation Deck",
                key="hide_obs_deck_bottom",
                use_container_width=True,
                help="Close the Observation Deck",
                type="primary"
            ):
                st.session_state.show_observation_deck = False
                st.rerun()

        with col3:
            max_slide = 15  # 0=welcome, 1=intro, 2=PA setup, 3-14=Q&A (12 slides), 15=completion
            is_disabled = (demo_slide_index >= max_slide)
            if st.button(
                "Next ➡️",
                key="obs_deck_next",
                use_container_width=True,
                disabled=is_disabled,
                help="Go to next slide" if not is_disabled else "Already at last slide",
                type="secondary"
            ):
                if demo_slide_index < max_slide:
                    st.session_state.demo_slide_index = min(max_slide, demo_slide_index + 1)
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    def _render_demo_pa(self):
        """Render demo Primacy Attractors (both User PA and AI PA) side-by-side with fidelity metrics."""
        # Get current slide index to determine fidelity values
        demo_slide_index = st.session_state.get('demo_slide_index', 0)

        # DEMO SLIDE FIDELITY VALUES - match conversation_display.py slide logic
        # Slides 0-2: Welcome, intro, PA setup - perfect alignment (1.0)
        # Slides 3-4: Initial Q&A - still perfect (1.0)
        # Slide 5: Detection question - slight drift demo
        # Slide 6: Quantum physics (off-topic) - user drifts, AI stays aligned
        # Slide 7: Dual fidelities question - both tracking
        # Slide 8: Math question - user dips for asking technical
        # Slides 9+: Recovery and closing

        if demo_slide_index == 6:  # Quantum physics off-topic
            user_fidelity = 0.65
            ai_fidelity = 0.89
        elif demo_slide_index == 7:  # Dual fidelities question
            user_fidelity = 0.72
            ai_fidelity = 0.91
        elif demo_slide_index == 8:  # Math question
            user_fidelity = 0.78
            ai_fidelity = 0.90
        elif demo_slide_index == 9:  # Intervention strategies
            user_fidelity = 0.85
            ai_fidelity = 0.92
        elif demo_slide_index >= 10:  # Recovery slides
            user_fidelity = 0.89
            ai_fidelity = 0.94
        elif demo_slide_index <= 4:  # Early slides - perfect alignment
            user_fidelity = 1.0
            ai_fidelity = 1.0
        else:  # Slide 5 - detection question
            user_fidelity = 0.92
            ai_fidelity = 0.95

        # Calculate Primacy State as harmonic mean (PS = 2*user*ai / (user+ai))
        if user_fidelity + ai_fidelity > 0:
            primacy_state = (2 * user_fidelity * ai_fidelity) / (user_fidelity + ai_fidelity)
        else:
            primacy_state = 0.0

        # Determine colors based on Goldilocks thresholds
        def get_color(fidelity):
            if fidelity >= 0.70:
                return "#27ae60"  # Green
            elif fidelity >= 0.60:
                return "#FFD700"  # Yellow
            elif fidelity >= 0.50:
                return "#FFA500"  # Orange
            else:
                return "#FF4444"  # Red

        user_color = get_color(user_fidelity)
        ai_color = get_color(ai_fidelity)
        ps_color = get_color(primacy_state)

        # Determine PS label
        if primacy_state >= 0.95:
            ps_label = "Perfect Equilibrium"
        elif primacy_state >= 0.80:
            ps_label = "Strong Alignment"
        elif primacy_state >= 0.70:
            ps_label = "Good Alignment"
        else:
            ps_label = "Drift Detected"

        # Centered container matching chat window style
        st.markdown("""
        <style>
        .pa-main-container {
            max-width: 700px;
            margin: 0 auto;
            padding: 0 10px;
        }
        </style>
        """, unsafe_allow_html=True)

        # Wrap everything in centered container
        st.markdown('<div class="pa-main-container">', unsafe_allow_html=True)

        # Main container with gold border
        st.markdown("""
        <div style="
            background-color: #1a1a1a;
            border: 3px solid #F4D03F;
            border-radius: 10px;
            padding: 20px;
            margin: 20px auto;
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.3);
        ">
        """, unsafe_allow_html=True)

        # PA Established indicator
        st.markdown("""
        <div style="text-align: center; margin-bottom: 15px;">
            <span style="background-color: #2d2d2d; border: 1px solid #27ae60; border-radius: 20px; padding: 5px 15px; color: #27ae60; font-weight: bold; font-size: 14px;">
                ✓ Dual PAs Established - Primacy Basin Achieved
            </span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div style="color: #F4D03F; text-align: center; font-size: 22px; font-weight: bold; margin-bottom: 20px;">Dual Primacy Attractors</div>', unsafe_allow_html=True)

        # Fidelity Metrics using table layout - DYNAMIC VALUES
        st.markdown(f"""
        <table style="width: 100%; margin-bottom: 15px;">
        <tr>
            <td style="width: 33%; text-align: center;">
                <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border: 1px solid {user_color}; border-radius: 8px; padding: 10px; display: inline-block;">
                    <div style="color: {user_color}; font-size: 12px; margin-bottom: 5px;">👤 User Fidelity</div>
                    <div style="color: {user_color}; font-size: 24px; font-weight: bold;">{int(round(user_fidelity * 100))}%</div>
                </div>
            </td>
            <td style="width: 34%; text-align: center; padding: 0 10px;">
                <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border: 2px solid {ps_color}; border-radius: 8px; padding: 10px 20px; display: inline-block;">
                    <div style="color: {ps_color}; font-size: 12px; margin-bottom: 5px;">🎯 Primacy State</div>
                    <div style="color: {ps_color}; font-size: 24px; font-weight: bold;">{int(round(primacy_state * 100))}%</div>
                    <div style="color: #888; font-size: 10px; margin-top: 5px;">{ps_label}</div>
                </div>
            </td>
            <td style="width: 33%; text-align: center;">
                <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border: 1px solid {ai_color}; border-radius: 8px; padding: 10px; display: inline-block;">
                    <div style="color: {ai_color}; font-size: 12px; margin-bottom: 5px;">🤖 AI Fidelity</div>
                    <div style="color: {ai_color}; font-size: 24px; font-weight: bold;">{int(round(ai_fidelity * 100))}%</div>
                </div>
            </td>
        </tr>
        </table>
        """, unsafe_allow_html=True)

        # Two-column layout for PAs using table
        st.markdown("""
        <table style="width: 100%; border-spacing: 15px;">
        <tr>
            <td style="width: 50%; vertical-align: top; padding: 0;">
                <!-- LEFT COLUMN: USER PA -->
                <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border: 2px solid #27ae60; border-radius: 8px; padding: 15px;">
                    <div style="color: #27ae60; font-weight: bold; text-align: center; font-size: 16px; margin-bottom: 15px;">
                        User Primacy Attractor
                    </div>
                    <div style="color: #27ae60; font-weight: bold; margin-bottom: 8px; font-size: 14px;">Your Purpose</div>
                    <div style="color: #e0e0e0; line-height: 1.5; font-size: 13px;">
                        • Understand TELOS without technical overwhelm<br>
                        • Learn how purpose alignment keeps AI focused<br>
                        • See real examples of governance in action
                    </div>
                </div>
            </td>

            <td style="width: 50%; vertical-align: top; padding: 0;">
                <!-- RIGHT COLUMN: AI PA -->
                <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border: 2px solid #F4D03F; border-radius: 8px; padding: 15px; margin-bottom: 10px;">
                    <div style="color: #F4D03F; font-weight: bold; text-align: center; font-size: 16px; margin-bottom: 15px;">
                        Steward Attractor
                    </div>
                    <div style="color: #F4D03F; font-weight: bold; margin-bottom: 8px; font-size: 14px;">Purpose</div>
                    <div style="color: #e0e0e0; line-height: 1.5; font-size: 13px;">
                        • Help you understand TELOS naturally<br>
                        • Stay aligned with your learning goals<br>
                        • Embody human dignity through action
                    </div>
                </div>

                <!-- AI Scope -->
                <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border: 2px solid #F4D03F; border-radius: 8px; padding: 12px; margin-bottom: 10px;">
                    <div style="color: #F4D03F; font-weight: bold; margin-bottom: 8px; font-size: 14px;">Scope</div>
                    <div style="color: #e0e0e0; line-height: 1.5; font-size: 13px;">
                        • TELOS dual attractor system<br>
                        • Perfect equilibrium & primacy basin<br>
                        • Real-time drift detection<br>
                        • Trust through transparency
                    </div>
                </div>

                <!-- AI Boundaries -->
                <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border: 2px solid #F4D03F; border-radius: 8px; padding: 12px;">
                    <div style="color: #F4D03F; font-weight: bold; margin-bottom: 8px; font-size: 14px;">Boundaries</div>
                    <div style="color: #e0e0e0; line-height: 1.5; font-size: 13px;">
                        • Answer what you asked<br>
                        • Stay conversational<br>
                        • 2-3 paragraphs max<br>
                        • No technical jargon
                    </div>
                </div>
            </td>
        </tr>
        </table>
        """, unsafe_allow_html=True)

        # Close main container
        st.markdown('</div>', unsafe_allow_html=True)

        # Close centered container
        st.markdown('</div>', unsafe_allow_html=True)

    def _get_fidelity_data(self):
        """Get fidelity data from state manager turn data.

        Mirrors the BETA mode logic but adapted for TELOS Open mode data structure.
        Returns: (user_fidelity, ai_fidelity, primacy_state, intervention_type)
        """
        turn_data = self.state_manager.get_current_turn_data()

        if not turn_data:
            return 1.0, 1.0, 1.0, None

        telos_analysis = turn_data.get('telos_analysis', {})
        ps_metrics = turn_data.get('ps_metrics', {})

        # === USER FIDELITY ===
        # Priority 1: Normalized display value
        user_fidelity = telos_analysis.get('display_user_pa_fidelity')
        # Priority 2: Direct turn_data display_fidelity
        if user_fidelity is None:
            user_fidelity = turn_data.get('display_fidelity')
        # Priority 3: Raw user_pa_fidelity
        if user_fidelity is None:
            user_fidelity = turn_data.get('user_pa_fidelity')
        if user_fidelity is None and ps_metrics:
            user_fidelity = ps_metrics.get('f_user')
        # Priority 4: Check telos_analysis for user_pa_fidelity
        if user_fidelity is None:
            user_fidelity = telos_analysis.get('user_pa_fidelity')
        # Priority 5: Legacy fallback
        if user_fidelity is None:
            user_fidelity = turn_data.get('user_fidelity', 1.0)

        # === AI FIDELITY ===
        # Priority 1: Direct turn_data
        ai_fidelity = turn_data.get('ai_pa_fidelity')
        # Priority 2: ps_metrics dict
        if ai_fidelity is None and ps_metrics:
            ai_fidelity = ps_metrics.get('f_ai')
        # Priority 3: Check telos_analysis
        if ai_fidelity is None:
            ai_fidelity = telos_analysis.get('ai_pa_fidelity')
        # Priority 4: Last resort fallback
        if ai_fidelity is None:
            ai_fidelity = turn_data.get('fidelity')

        # If still no AI fidelity, estimate it (AI typically stays aligned)
        if ai_fidelity is None and user_fidelity is not None:
            ai_fidelity = min(1.0, user_fidelity + 0.15) if user_fidelity else None

        # === PRIMACY STATE ===
        # Priority 1: Display-normalized PS
        primacy_state = telos_analysis.get('display_primacy_state')
        # Priority 2: Direct turn_data
        if primacy_state is None:
            primacy_state = turn_data.get('display_primacy_state')
        # Priority 3: Raw primacy_state_score
        if primacy_state is None:
            primacy_state = turn_data.get('primacy_state_score')
        # Priority 4: Check ps_metrics
        if primacy_state is None and ps_metrics:
            primacy_state = ps_metrics.get('ps_score')
        # Priority 5: Check telos_analysis
        if primacy_state is None:
            primacy_state = telos_analysis.get('primacy_state_score')

        # Fallback: calculate PS if we have fidelities but no stored PS
        if primacy_state is None and user_fidelity is not None and ai_fidelity is not None:
            epsilon = 1e-10
            if user_fidelity + ai_fidelity > epsilon:
                primacy_state = (2 * user_fidelity * ai_fidelity) / (user_fidelity + ai_fidelity + epsilon)

        # === INTERVENTION TYPE ===
        intervention_type = telos_analysis.get('intervention_type') or turn_data.get('intervention_type')

        return user_fidelity, ai_fidelity, primacy_state, intervention_type

    def _render_fidelity_row(self):
        """Render three-box fidelity row: User Fidelity | AI Fidelity | Primacy State.

        Ported from BETA mode styling with glow effects and zone labels.
        """
        user_fidelity, ai_fidelity, primacy_state, _ = self._get_fidelity_data()

        # Get colors
        user_color = get_fidelity_color(user_fidelity) if user_fidelity else "#888"
        ai_color = get_fidelity_color(ai_fidelity) if ai_fidelity else "#888"
        ps_color = get_fidelity_color(primacy_state) if primacy_state else "#888"

        # Helper for consistent "round half up" behavior
        def round_half_up(value, decimals=2):
            from decimal import Decimal, ROUND_HALF_UP
            if value is None:
                return None
            d = Decimal(str(value))
            return float(d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

        # Format displays as percentages to match BETA style
        user_display = f"{int(round(user_fidelity * 100))}%" if user_fidelity is not None else "---"
        ai_display = f"{int(round(ai_fidelity * 100))}%" if ai_fidelity is not None else "---"
        ps_display = f"{int(round(primacy_state * 100))}%" if primacy_state is not None else "---"

        # Determine zone labels
        def get_zone_label(fidelity):
            if fidelity is None:
                return ("---", "#888")
            if fidelity >= 0.70:
                return ("GREEN ZONE - Aligned", "#27ae60")
            elif fidelity >= 0.60:
                return ("YELLOW ZONE - Minor Drift", "#F4D03F")
            elif fidelity >= 0.50:
                return ("ORANGE ZONE - Drift Detected", "#FFA500")
            else:
                return ("RED ZONE - Significant Drift", "#E74C3C")

        user_zone, user_zone_color = get_zone_label(user_fidelity)
        ai_zone, ai_zone_color = get_zone_label(ai_fidelity)
        ps_zone, ps_zone_color = get_zone_label(primacy_state)

        # Helper to convert hex color to rgba glow
        def get_glow_color(hex_color):
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return f"rgba({r}, {g}, {b}, 0.4)"

        user_glow = get_glow_color(user_color)
        ai_glow = get_glow_color(ai_color)
        ps_glow = get_glow_color(ps_color)

        # Full-width fidelity boxes with glow effect
        st.markdown(f"""
<div style="display: flex; justify-content: center; gap: 10px; margin: 15px auto; max-width: 700px;">
    <div style="background-color: #1a1a1a; border: 2px solid {user_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1; box-shadow: 0 4px 20px {user_glow};">
        <div style="color: {user_color}; font-size: 16px; font-weight: bold; margin-bottom: 10px;">User Fidelity</div>
        <div style="color: {user_color}; font-size: 42px; font-weight: bold;">{user_display}</div>
        <div style="color: {user_zone_color}; font-size: 14px; margin-top: 8px;">{user_zone}</div>
    </div>
    <div style="background-color: #1a1a1a; border: 2px solid {ai_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1; box-shadow: 0 4px 20px {ai_glow};">
        <div style="color: {ai_color}; font-size: 16px; font-weight: bold; margin-bottom: 10px;">AI Fidelity</div>
        <div style="color: {ai_color}; font-size: 42px; font-weight: bold;">{ai_display}</div>
        <div style="color: {ai_zone_color}; font-size: 14px; margin-top: 8px;">{ai_zone}</div>
    </div>
    <div style="background-color: #1a1a1a; border: 2px solid {ps_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1; box-shadow: 0 4px 20px {ps_glow};">
        <div style="color: {ps_color}; font-size: 16px; font-weight: bold; margin-bottom: 10px;">Primacy State</div>
        <div style="color: {ps_color}; font-size: 42px; font-weight: bold;">{ps_display}</div>
        <div style="color: {ps_color}; font-size: 14px; margin-top: 8px;">{ps_zone}</div>
    </div>
</div>
""", unsafe_allow_html=True)

    def _render_dual_pa(self):
        """Render User PA and Steward Attractor side by side with glow effects and zoom-on-click."""
        import streamlit.components.v1 as components

        # Get User PA
        pa = st.session_state.get('primacy_attractor', {})

        def safe_escape(value, default='Not set'):
            """Safely escape PA values."""
            if value is None:
                return default
            if isinstance(value, list):
                return '<br>'.join(html.escape(str(item)) for item in value)
            return html.escape(str(value))

        purpose = safe_escape(pa.get('purpose'), 'Not set')
        scope = safe_escape(pa.get('scope'), 'Not set')
        boundaries = safe_escape(pa.get('boundaries'), 'Not set')

        # Get Steward PA data from config
        steward_purpose = safe_escape(STEWARD_PA.get('purpose'), 'Not set')
        steward_scope = safe_escape(STEWARD_PA.get('scope'), 'Not set')
        steward_boundaries = safe_escape(STEWARD_PA.get('boundaries'), 'Not set')

        # Get colors based on fidelity
        user_fidelity, ai_fidelity, _, _ = self._get_fidelity_data()
        user_color = get_fidelity_color(user_fidelity) if user_fidelity else "#27ae60"
        ai_color = get_fidelity_color(ai_fidelity) if ai_fidelity else "#27ae60"

        def get_glow_color(hex_color):
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return f"rgba({r}, {g}, {b}, 0.4)"

        user_glow = get_glow_color(user_color)
        ai_glow = get_glow_color(ai_color)

        attractor_html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: transparent; }}
.attractor-card {{ cursor: pointer; transition: all 0.3s ease; }}
.attractor-card:hover {{ transform: translateY(-2px); }}
.attractor-card.expanded {{ flex: 1 1 100% !important; }}
.attractor-card.collapsed {{ display: none; }}
.attractor-content {{ transition: all 0.3s ease; }}
.attractor-card.expanded .attractor-content {{ padding: 24px; }}
.attractor-card.expanded .attractor-label {{ font-size: 16px !important; margin-bottom: 10px !important; }}
.attractor-card.expanded .attractor-value {{ font-size: 15px !important; margin-bottom: 18px !important; line-height: 1.7 !important; }}
</style>
</head>
<body>
<div id="attractor-container" style="max-width: 700px; margin: 15px auto; background-color: #1a1a1a; border: 2px solid #444; border-radius: 12px; padding: 20px;">
    <div id="attractor-flex" style="display: flex; gap: 15px; flex-wrap: wrap;">
        <div id="user-card" class="attractor-card" style="flex: 1; text-align: center; min-width: 280px;" onclick="toggleAttractor('user')">
            <div style="background: linear-gradient(135deg, {user_color} 0%, {user_color}dd 100%); color: #1a1a1a; padding: 12px 12px 6px 12px; border-radius: 10px 10px 0 0; font-weight: bold; font-size: 15px; box-shadow: 0 0 15px {user_glow};">
                User Attractor
                <div id="user-hint" style="font-size: 10px; font-weight: normal; opacity: 0.7; margin-top: 2px;">(click to expand)</div>
            </div>
            <div class="attractor-content" style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.95); border: 2px solid {user_color}; border-top: none; border-radius: 0 0 10px 10px; padding: 18px; text-align: left; min-height: 180px; box-shadow: 0 4px 20px {user_glow};">
                <div class="attractor-label" style="color: {user_color}; font-weight: bold; margin-bottom: 8px; font-size: 13px;">Purpose</div>
                <div class="attractor-value" style="color: #e0e0e0; font-size: 12px; margin-bottom: 14px; line-height: 1.6;">{purpose}</div>
                <div class="attractor-label" style="color: {user_color}; font-weight: bold; margin-bottom: 8px; font-size: 13px;">Scope</div>
                <div class="attractor-value" style="color: #e0e0e0; font-size: 12px; margin-bottom: 14px; line-height: 1.6;">{scope}</div>
                <div class="attractor-label" style="color: {user_color}; font-weight: bold; margin-bottom: 8px; font-size: 13px;">Boundaries</div>
                <div class="attractor-value" style="color: #e0e0e0; font-size: 12px; line-height: 1.6;">{boundaries}</div>
            </div>
        </div>
        <div id="steward-card" class="attractor-card" style="flex: 1; text-align: center; min-width: 280px;" onclick="toggleAttractor('steward')">
            <div style="background: linear-gradient(135deg, {ai_color} 0%, {ai_color}dd 100%); color: #1a1a1a; padding: 12px 12px 6px 12px; border-radius: 10px 10px 0 0; font-weight: bold; font-size: 15px; box-shadow: 0 0 15px {ai_glow};">
                Steward Attractor
                <div id="steward-hint" style="font-size: 10px; font-weight: normal; opacity: 0.7; margin-top: 2px;">(click to expand)</div>
            </div>
            <div class="attractor-content" style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.95); border: 2px solid {ai_color}; border-top: none; border-radius: 0 0 10px 10px; padding: 18px; text-align: left; min-height: 180px; box-shadow: 0 4px 20px {ai_glow};">
                <div class="attractor-label" style="color: {ai_color}; font-weight: bold; margin-bottom: 8px; font-size: 13px;">Purpose</div>
                <div class="attractor-value" style="color: #e0e0e0; font-size: 12px; margin-bottom: 14px; line-height: 1.6;">{steward_purpose}</div>
                <div class="attractor-label" style="color: {ai_color}; font-weight: bold; margin-bottom: 8px; font-size: 13px;">Scope</div>
                <div class="attractor-value" style="color: #e0e0e0; font-size: 12px; margin-bottom: 14px; line-height: 1.6;">{steward_scope}</div>
                <div class="attractor-label" style="color: {ai_color}; font-weight: bold; margin-bottom: 8px; font-size: 13px;">Boundaries</div>
                <div class="attractor-value" style="color: #e0e0e0; font-size: 12px; line-height: 1.6;">{steward_boundaries}</div>
            </div>
        </div>
    </div>
</div>
<script>
let expandedCard = null;
function toggleAttractor(type) {{
    const userCard = document.getElementById('user-card');
    const stewardCard = document.getElementById('steward-card');
    const userHint = document.getElementById('user-hint');
    const stewardHint = document.getElementById('steward-hint');
    const clickedCard = document.getElementById(type + '-card');
    const otherCard = type === 'user' ? stewardCard : userCard;
    if (expandedCard === type) {{
        userCard.classList.remove('expanded', 'collapsed');
        stewardCard.classList.remove('expanded', 'collapsed');
        userHint.textContent = '(click to expand)';
        stewardHint.textContent = '(click to expand)';
        expandedCard = null;
    }} else {{
        clickedCard.classList.add('expanded');
        clickedCard.classList.remove('collapsed');
        otherCard.classList.add('collapsed');
        otherCard.classList.remove('expanded');
        if (type === 'user') {{ userHint.textContent = '(click to collapse)'; }}
        else {{ stewardHint.textContent = '(click to collapse)'; }}
        expandedCard = type;
    }}
    setTimeout(updateFrameHeight, 50);
}}
function updateFrameHeight() {{
    const container = document.getElementById('attractor-container');
    const newHeight = container.offsetHeight + 40;
    if (window.frameElement) {{ window.frameElement.style.height = newHeight + 'px'; }}
}}
setTimeout(updateFrameHeight, 100);
</script>
</body>
</html>
"""
        components.html(attractor_html, height=500, scrolling=True)

    def _render_metric_window(self, title, value, icon, description, value_color="#F4D03F"):
        """Render a compact gold-themed metric window.

        Args:
            title: Window title
            value: Metric value to display
            icon: Icon emoji
            description: Description text
            value_color: Color for the value text
        """
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            border: 1px solid #F4D03F;
            border-radius: 8px;
            padding: 6px 8px;
            margin-bottom: 6px;
            box-shadow: 0 0 6px rgba(255, 215, 0, 0.15);
        ">
            <div style="display: flex; align-items: center; margin-bottom: 3px;">
                <span style="font-size: 16px; margin-right: 6px;">{icon}</span>
                <span style="color: #F4D03F; font-size: 10px; font-weight: bold;">
                    {title}
                </span>
            </div>
            <div style="
                font-size: 20px;
                font-weight: bold;
                color: {value_color};
                margin: 3px 0;
                text-align: center;
            ">
                {value}
            </div>
            <div style="color: #b0b0b0; font-size: 8px; text-align: center;">
                {description}
            </div>
        </div>
        """, unsafe_allow_html=True)

    def _render_metrics(self, turn_data):
        """Render metrics readout section with BETA-style fidelity row and dual PA display."""
        # Render BETA-style fidelity row with glow effects and zone labels
        self._render_fidelity_row()

        # Render dual PA display with click-to-expand
        self._render_dual_pa()

    def _render_metric_card(self, title, value, icon, description, value_color="#F4D03F"):
        """Render a single metric card."""
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            border: 1px solid #F4D03F;
            border-radius: 8px;
            padding: 10px;
            text-align: center;
        ">
            <div style="font-size: 20px; margin-bottom: 5px;">{icon}</div>
            <div style="color: #F4D03F; font-size: 10px; font-weight: bold; margin-bottom: 5px;">
                {title}
            </div>
            <div style="
                font-size: 18px;
                font-weight: bold;
                color: {value_color};
                margin: 5px 0;
            ">
                {value}
            </div>
            <div style="color: #888; font-size: 8px;">
                {description}
            </div>
        </div>
        """, unsafe_allow_html=True)

    def _render_view_options(self):
        """Render view options toggles."""
        st.markdown("### ⚙️ View Options")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            # Primacy Attractor toggle (renamed from Steward Details)
            pa_label = "✕ Close Primacy Attractor" if self.state_manager.state.show_primacy_attractor else "🎯 Primacy Attractor"
            if st.button(
                pa_label,
                key="deck_toggle_pa_btn",
                use_container_width=True
            ):
                self.state_manager.toggle_component('primacy_attractor')
                st.rerun()

        with col2:
            math_label = "✕ Close Math Breakdown" if self.state_manager.state.show_math_breakdown else "🔢 Math Breakdown"
            if st.button(
                math_label,
                key="deck_toggle_math_btn",
                use_container_width=True
            ):
                self.state_manager.toggle_component('math_breakdown')
                st.rerun()

        with col3:
            cf_label = "✕ Close Counterfactual" if self.state_manager.state.show_counterfactual else "🔀 Counterfactual"
            if st.button(
                cf_label,
                key="deck_toggle_cf_btn",
                use_container_width=True
            ):
                self.state_manager.toggle_component('counterfactual')
                st.rerun()

        with col4:
            # Renamed Deep Dive to Observatory
            if st.button("🔭 Observatory", key="deck_observatory_btn", use_container_width=True):
                st.info("Observatory feature - detailed Phase 2 analysis and metrics")

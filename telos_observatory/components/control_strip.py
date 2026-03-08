"""
Control Strip Component for TELOS Observatory V3.
Clean, minimal strip showing metrics with clickable toggle.
"""

import streamlit as st


class ControlStrip:
    """Minimal control strip with clean design."""

    def __init__(self, state_manager):
        """Initialize with state manager reference.

        Args:
            state_manager: StateManager instance for turn data and deck control
        """
        self.state_manager = state_manager

    def render(self):
        """Render the control strip."""
        # Get current turn data
        turn_data = self.state_manager.get_current_turn_data()
        session_info = self.state_manager.get_session_info()

        if not turn_data:
            return

        # Build strip data
        turn_num = session_info.get('current_turn', 0) + 1
        total_turns = session_info.get('total_turns', 0)
        fidelity = turn_data.get('fidelity', 0.0)
        status = turn_data.get('status_text', 'Calibrating...')

        # Color coding for fidelity (Goldilocks zone system)
        # Import from central config to stay in sync
        try:
            from telos_observatory.config.colors import get_fidelity_color
            fidelity_color = get_fidelity_color(fidelity)
        except ImportError:
            # Fallback if config not available (using canonical TELOS colors)
            if fidelity >= 0.70:
                fidelity_color = "#27ae60"  # Green - "Aligned"
            elif fidelity >= 0.60:
                fidelity_color = "#f39c12"  # Yellow - "Minor Drift"
            elif fidelity >= 0.50:
                fidelity_color = "#e67e22"  # Orange - "Drift Detected"
            else:
                fidelity_color = "#e74c3c"  # Red - "Significant Drift"

        # Create clean strip display
        col1, col2 = st.columns([4, 1])

        with col2:
            # Compact strip with telescope icon
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
                border: 1px solid #F4D03F;
                border-radius: 8px;
                padding: 10px 15px;
                text-align: center;
                cursor: pointer;
            ">
                <div style="font-size: 24px; margin-bottom: 5px;">🔭</div>
                <div style="color: #F4D03F; font-size: 11px; font-weight: bold;">
                    Turn {turn_num}/{total_turns}
                </div>
                <div style="color: {fidelity_color}; font-size: 13px; font-weight: bold; margin: 3px 0;">
                    {fidelity:.3f}
                </div>
                <div style="color: #888; font-size: 10px;">
                    {status}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Button below to toggle deck
            if st.button(
                "Open Deck" if not self.state_manager.is_deck_expanded() else "Close Deck",
                key="strip_toggle",
                use_container_width=True
            ):
                self.state_manager.toggle_deck()
                st.rerun()

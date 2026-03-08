"""
TELOSCOPE Controls Component for TELOS Observatory V3.
Playback and analysis controls (simplified for V3 - no draggability yet).

Enhanced with SSE streaming replay capabilities from claude-trace integration.
"""

import streamlit as st
import logging

logger = logging.getLogger(__name__)


class TELOSCOPEControls:
    """TELOSCOPE Controls panel."""

    def __init__(self, state_manager):
        """Initialize with state manager reference.

        Args:
            state_manager: StateManager instance for playback control
        """
        self.state_manager = state_manager

    def render(self):
        """Render TELOSCOPE controls panel."""
        # Don't render if no turns yet
        if self.state_manager.state.total_turns == 0:
            return

        # Check if controls are expanded
        is_expanded = self.state_manager.is_teloscope_expanded()

        if not is_expanded:
            # Collapsed state - thin gold bar
            if st.button("TELOSCOPE Controls - Click to expand (ESC)", key="teloscope_toggle_collapsed", use_container_width=True):
                self.state_manager.toggle_teloscope()
                st.rerun()
            return

        # Expanded state - full controls panel
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
            border: 1px solid #F4D03F;
            border-radius: 10px;
            padding: 15px;
            margin-top: 20px;
        ">
            <div style="text-align: center; margin-bottom: 15px;">
                <h3 style="color: #F4D03F; margin: 0; font-size: 28px;">
                    TELOSCOPE Controls
                </h3>
                <p style="color: #888; font-size: 14px; margin: 5px 0 0 0;">
                    Session playback and analysis
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Collapse button
        if st.button("▼ Collapse (ESC)", key="teloscope_toggle_expanded", use_container_width=True):
            self.state_manager.toggle_teloscope()
            st.rerun()

        st.markdown("---")

        # Session Info Display (from old Control Strip)
        session_info = self.state_manager.get_session_info()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"""
            <div style="
                background-color: #1a1a1a;
                border: 1px solid #F4D03F;
                border-radius: 5px;
                padding: 8px;
                text-align: center;
            ">
                <div style="color: #888; font-size: 10px;">TURN</div>
                <div style="color: #F4D03F; font-size: 16px; font-weight: bold;">
                    {session_info.get('current_turn', 0) + 1} / {session_info.get('total_turns', 0)}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="
                background-color: #1a1a1a;
                border: 1px solid #F4D03F;
                border-radius: 5px;
                padding: 8px;
                text-align: center;
            ">
                <div style="color: #888; font-size: 10px;">AVG FIDELITY</div>
                <div style="color: #F4D03F; font-size: 16px; font-weight: bold;">
                    {session_info.get('avg_fidelity', 0.0):.3f}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div style="
                background-color: #1a1a1a;
                border: 1px solid #F4D03F;
                border-radius: 5px;
                padding: 8px;
                text-align: center;
            ">
                <div style="color: #888; font-size: 10px;">INTERVENTIONS</div>
                <div style="color: #F4D03F; font-size: 16px; font-weight: bold;">
                    {session_info.get('total_interventions', 0)}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # Turn Scrubber
        st.markdown("**Turn Navigation**")
        session_info = self.state_manager.get_session_info()
        current_turn = session_info.get('current_turn', 0)
        total_turns = session_info.get('total_turns', 1)

        turn_slider = st.slider(
            f"Navigate through {total_turns} turns",
            0,
            total_turns - 1,
            current_turn,
            key="turn_scrubber",
            label_visibility="collapsed"
        )

        if turn_slider != current_turn:
            self.state_manager.jump_to_turn(turn_slider)
            st.rerun()

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("◀ Prev", use_container_width=True, key="teloscope_prev"):
                if self.state_manager.previous_turn():
                    st.rerun()

        with col2:
            st.markdown(f"""
            <div style="
                text-align: center;
                padding: 8px;
                background-color: #2d2d2d;
                border-radius: 5px;
            ">
                <span style="color: #F4D03F; font-size: 14px;">
                    {current_turn + 1} / {total_turns}
                </span>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            if st.button("Next ▶", use_container_width=True, key="teloscope_next"):
                if self.state_manager.next_turn():
                    st.rerun()

        st.markdown("---")

        # Intervention Scrubber
        st.markdown("**Intervention Scrubber**")
        intervention_turns = [
            i for i, turn in enumerate(self.state_manager.state.turns)
            if turn.get('intervention_applied', False)
        ]

        if len(intervention_turns) > 1:
            # Only show slider if there are multiple interventions
            current = self.state_manager.state.current_turn
            # Find current position in intervention list
            try:
                current_idx = intervention_turns.index(current) if current in intervention_turns else 0
            except ValueError:
                current_idx = 0

            selected_idx = st.slider(
                f"Jump between {len(intervention_turns)} interventions",
                0,
                len(intervention_turns) - 1,
                current_idx,
                key="intervention_scrubber",
                label_visibility="collapsed"
            )

            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"""
                <div style="color: #F4D03F; font-size: 11px; text-align: center;">
                    Intervention {selected_idx + 1}/{len(intervention_turns)} (Turn {intervention_turns[selected_idx] + 1})
                </div>
                """, unsafe_allow_html=True)

            with col2:
                if st.button("Jump", key="jump_to_intervention"):
                    self.state_manager.jump_to_turn(intervention_turns[selected_idx])
                    st.rerun()
        elif len(intervention_turns) == 1:
            # Single intervention - just show info and jump button
            st.markdown(f"""
            <div style="color: #F4D03F; font-size: 11px; text-align: center; margin-bottom: 10px;">
                1 intervention at Turn {intervention_turns[0] + 1}
            </div>
            """, unsafe_allow_html=True)

            if st.button("Jump to Intervention", key="jump_to_single_intervention", use_container_width=True):
                self.state_manager.jump_to_turn(intervention_turns[0])
                st.rerun()
        else:
            st.info("No interventions in this session")

        st.markdown("---")

        # Playback controls
        col1, col2, col3 = st.columns(3)

        with col1:
            play_label = "⏸ Pause" if self.state_manager.is_playing() else "▶ Play"
            if st.button(play_label, use_container_width=True, key="teloscope_play"):
                if self.state_manager.is_playing():
                    self.state_manager.stop_playback()
                else:
                    self.state_manager.start_playback()
                st.rerun()

        with col2:
            if st.button("⏮ Reset", use_container_width=True, key="teloscope_reset"):
                self.state_manager.jump_to_turn(0)
                st.rerun()

        with col3:
            if st.button("⏭ Skip", use_container_width=True, key="teloscope_skip"):
                # Skip ahead 5 turns
                target = min(
                    self.state_manager.state.current_turn + 5,
                    self.state_manager.state.total_turns - 1
                )
                self.state_manager.jump_to_turn(target)
                st.rerun()

        # Playback speed
        st.markdown("---")
        st.markdown("**Playback Speed**")
        speed = st.select_slider(
            "Speed",
            options=[0.5, 1.0, 1.5, 2.0, 3.0],
            value=self.state_manager.state.playback_speed,
            key="teloscope_speed",
            label_visibility="collapsed"
        )
        if speed != self.state_manager.state.playback_speed:
            self.state_manager.set_playback_speed(speed)

        # SSE Streaming Replay Section
        st.markdown("---")
        try:
            from .teloscope_sse_viewer import TELOSCOPEStreamViewer
            sse_viewer = TELOSCOPEStreamViewer(self.state_manager)
            sse_viewer.render()
        except ImportError as e:
            logger.debug(f"SSE viewer not available: {e}")
            # Show placeholder for SSE feature
            with st.expander("🌊 Streaming Replay (Coming Soon)", expanded=False):
                st.info(
                    "SSE streaming replay will show HOW responses were generated, "
                    "not just WHAT was generated. Enable streaming mode to see "
                    "token-by-token replay with original timing."
                )
        except Exception as e:
            logger.warning(f"SSE viewer error: {e}")

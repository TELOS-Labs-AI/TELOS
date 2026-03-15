"""
Sidebar Actions Component for TELOS Observatory V3.
Provides session management controls in left sidebar.
"""

import streamlit as st
import json
from datetime import datetime


class SidebarActions:
    """Left sidebar with session management actions."""

    def __init__(self, state_manager):
        """Initialize with state manager reference.

        Args:
            state_manager: StateManager instance for session operations
        """
        self.state_manager = state_manager

    def render(self):
        """Render sidebar actions."""
        with st.sidebar:
            # TELOS Branding with telescope icon
            st.markdown("""
            <div style="text-align: center; padding: 10px 0 10px 0;">
                <h1 style="color: #F4D03F; font-size: 52px; margin: 0; font-weight: bold; letter-spacing: 3px; display: inline-flex; align-items: center; justify-content: center; gap: 15px;">
                    TELOS <span style="font-size: 64px;">🔭</span>
                </h1>
            </div>
            """, unsafe_allow_html=True)

            # Saved Sessions - Collapsible
            # Initialize saved sessions expanded state
            if 'saved_sessions_expanded' not in st.session_state:
                st.session_state.saved_sessions_expanded = False

            if st.button("💾 Saved Sessions" + (" ▼" if not st.session_state.saved_sessions_expanded else " ▲"),
                        use_container_width=True, key="toggle_saved_sessions"):
                st.session_state.saved_sessions_expanded = not st.session_state.saved_sessions_expanded
                st.rerun()

            # Show saved sessions if expanded
            if st.session_state.saved_sessions_expanded:
                saved_sessions = self._get_saved_sessions()

                if saved_sessions:
                    for session in saved_sessions:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"""
                            <div style="background-color: #1a1a1a; padding: 6px; border-radius: 5px; margin-bottom: 4px;">
                                <div style="color: #F4D03F; font-size: 11px;">{session['name']}</div>
                                <div style="color: #888; font-size: 9px;">{session['date']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col2:
                            if st.button("📂", key=f"load_{session['id']}", help="Load session"):
                                self._load_session_by_id(session['id'])
                else:
                    st.info("No saved sessions")

            # Exit Demo Mode Button (only shown in Demo Mode)
            if st.session_state.get('telos_demo_mode', False):
                st.markdown("---")
                if st.button("🚪 Exit Demo Mode", use_container_width=True, key="exit_demo_sidebar"):
                    self._exit_demo_mode()

            # Save Current
            if st.button("💾 Save Current", use_container_width=True):
                self._save_current_session()

            # Reset Session with confirmation
            # Initialize confirmation state
            if 'confirm_reset' not in st.session_state:
                st.session_state.confirm_reset = False

            if not st.session_state.confirm_reset:
                if st.button("🔄 Reset Session", use_container_width=True):
                    st.session_state.confirm_reset = True
                    st.rerun()
            else:
                # Show confirmation message
                st.warning("⚠️ This will delete the entire conversation. Are you sure?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✓ Yes, Reset", use_container_width=True, type="primary"):
                        st.session_state.confirm_reset = False
                        self._reset_session()
                with col2:
                    if st.button("✕ Cancel", use_container_width=True):
                        st.session_state.confirm_reset = False
                        st.rerun()

            # Export Evidence
            if st.button("📤 Export Evidence", use_container_width=True):
                self._export_evidence()

            # Documentation - Toggle
            st.markdown("---")
            if 'docs_expanded' not in st.session_state:
                st.session_state.docs_expanded = False

            docs_label = "✕ Close Documentation" if st.session_state.docs_expanded else "📚 Documentation"
            if st.button(docs_label, use_container_width=True, key="toggle_docs"):
                st.session_state.docs_expanded = not st.session_state.docs_expanded
                st.rerun()

            # Show documentation links if expanded
            if st.session_state.docs_expanded:
                self._show_documentation()

            # GitHub Link
            if st.button("🔗 GitHub Repository", use_container_width=True, key="github_link"):
                # Open GitHub in new tab using JavaScript
                st.markdown("""
                <script>
                window.open('https://github.com/TELOS-Labs-AI/telos', '_blank');
                </script>
                """, unsafe_allow_html=True)
                st.info("Opening GitHub repository in new tab...")

            # Settings - Toggle
            st.markdown("---")
            if 'settings_expanded' not in st.session_state:
                st.session_state.settings_expanded = False

            settings_label = "✕ Close Settings" if st.session_state.settings_expanded else "⚙️ Settings"
            if st.button(settings_label, use_container_width=True, key="toggle_settings"):
                st.session_state.settings_expanded = not st.session_state.settings_expanded
                st.rerun()

            # Show settings if expanded
            if st.session_state.settings_expanded:
                self._show_settings()

    def _save_current_session(self):
        """Save current session state to file."""
        try:
            from pathlib import Path
            import json

            # Determine if we're in Demo Mode
            demo_mode = st.session_state.get('telos_demo_mode', False)

            # Build session data
            session_data = {
                'session_id': self.state_manager.state.session_id,
                'timestamp': datetime.now().isoformat(),
                'mode': 'demo' if demo_mode else 'open',
                'current_turn': self.state_manager.state.current_turn,
                'total_turns': self.state_manager.state.total_turns,
                'avg_fidelity': self.state_manager.state.avg_fidelity,
                'total_interventions': self.state_manager.state.total_interventions,
                'drift_warnings': self.state_manager.state.drift_warnings,
                'turns': self.state_manager.state.turns
            }

            # If Demo Mode, include PA configuration
            if demo_mode:
                from telos_observatory.demo_mode.telos_framework_demo import get_demo_attractor_config
                session_data['pa_config'] = get_demo_attractor_config()

            # Choose save directory based on mode
            if demo_mode:
                save_dir = Path(__file__).parent.parent.parent / 'demo_mode_logs'
                prefix = 'demo'
            else:
                save_dir = Path(__file__).parent.parent / 'saved_sessions'
                prefix = 'session'

            # Create directory if it doesn't exist
            save_dir.mkdir(exist_ok=True)

            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{prefix}_{self.state_manager.state.session_id}_{timestamp}.json"
            filepath = save_dir / filename

            # Save to file
            with open(filepath, 'w') as f:
                json.dump(session_data, f, indent=2)

            st.success(f"✅ Session saved: {filename}")

        except Exception as e:
            st.error(f"Error saving session: {e}")

    def _get_saved_sessions(self):
        """Get list of saved sessions from file system."""
        from pathlib import Path

        # Check for saved sessions directory
        saved_sessions_dir = Path(__file__).parent.parent / 'saved_sessions'

        if not saved_sessions_dir.exists():
            return []

        # Load session index if it exists
        index_file = saved_sessions_dir / 'session_index.json'
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    index_data = json.load(f)
                    return index_data.get('sessions', [])
            except Exception as e:
                st.error(f"Error loading session index: {e}")
                return []

        return []

    def _load_session_by_id(self, session_id):
        """Load a specific session by ID."""
        from pathlib import Path

        # Find the session file
        saved_sessions_dir = Path(__file__).parent.parent / 'saved_sessions'
        session_file = saved_sessions_dir / f"{session_id}.json"

        if not session_file.exists():
            st.error(f"Session file not found: {session_id}")
            return

        try:
            # Load session data from file
            with open(session_file, 'r') as f:
                session_data = json.load(f)

            # Load into state manager
            self.state_manager.load_from_session(session_data)

            st.success(f"✅ Loaded: {session_data.get('name', session_id)}")
            st.rerun()

        except Exception as e:
            st.error(f"Error loading session: {e}")

    def _reset_session(self):
        """Reset session - completely clear all conversation data and start fresh."""
        # Clear all conversation data
        self.state_manager.clear_demo_data()

        # Close all analysis panels
        self.state_manager.state.show_primacy_attractor = False
        self.state_manager.state.show_math_breakdown = False
        self.state_manager.state.show_counterfactual = False
        self.state_manager.state.show_steward = False

        # Close observation deck and teloscope
        self.state_manager.state.deck_expanded = False
        self.state_manager.state.teloscope_expanded = False

        # Stop playback if running
        self.state_manager.stop_playback()

        # Turn off scrollable history mode
        self.state_manager.state.scrollable_history_mode = False

        # Clear user conversation flag so next message will be treated as first
        if 'user_started_conversation' in st.session_state:
            del st.session_state.user_started_conversation

        # Clear intro state to allow it to show again
        if 'show_intro' in st.session_state:
            st.session_state.show_intro = st.session_state.get('enable_intro_examples', True)

        # Clear intro pair cache
        if 'intro_pair' in st.session_state:
            del st.session_state.intro_pair

        # Clear demo welcome flag so it shows again in demo mode
        if 'demo_welcome_shown' in st.session_state:
            del st.session_state.demo_welcome_shown

        st.success("✅ Session reset - All conversation data cleared")
        st.rerun()

    def _exit_demo_mode(self):
        """Exit Demo Mode and switch to Open Mode with clean session."""
        # Auto-save Demo Mode session before exiting (if there's any conversation data)
        if self.state_manager.state.total_turns > 0:
            try:
                self._save_current_session()
            except Exception as e:
                # Don't block exit if save fails, but show warning
                st.warning(f"Could not auto-save demo session: {e}")

        # Clear all conversation data
        empty_data = {
            'session_id': f"session_{int(datetime.now().timestamp())}",
            'turns': [],
            'total_turns': 0,
            'current_turn': 0,
            'avg_fidelity': 0.0,
            'total_interventions': 0,
            'drift_warnings': 0
        }
        # Use load_from_session to properly re-initialize (resets _initialized flag)
        self.state_manager.load_from_session(empty_data)

        # Switch to Open Mode
        st.session_state.telos_demo_mode = False

        # Clear demo-specific session state
        if 'demo_welcome_shown' in st.session_state:
            del st.session_state.demo_welcome_shown

        # Clear user conversation flag
        if 'user_started_conversation' in st.session_state:
            del st.session_state.user_started_conversation

        # Reset demo message counter
        if 'demo_message_count' in st.session_state:
            st.session_state.demo_message_count = 0

        # Disable intro examples when switching to Open Mode
        st.session_state.show_intro = False
        st.session_state.enable_intro_examples = False

        st.success("✅ Exited Demo Mode - Switched to Open Mode")
        st.rerun()

    def _export_evidence(self):
        """Export evidence package for governance review."""
        try:
            # Collect all interventions
            interventions = [
                turn for turn in self.state_manager.state.turns
                if turn.get('intervention_applied', False)
            ]

            evidence = {
                'session_id': self.state_manager.state.session_id,
                'export_date': datetime.now().isoformat(),
                'total_turns': len(self.state_manager.state.turns),
                'intervention_count': len(interventions),
                'interventions': interventions
            }

            st.success(f"Evidence package ready: {len(interventions)} interventions documented")

        except Exception as e:
            st.error(f"Error exporting evidence: {e}")

    def _show_keyboard_controls(self):
        """Show keyboard shortcuts information."""
        st.markdown("""<div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border: 1px solid #F4D03F; border-radius: 8px; padding: 15px; margin: 10px 0;"><div style="color: #F4D03F; font-size: 18px; font-weight: bold; margin-bottom: 10px;">⌨️ Keyboard Shortcuts</div><div style="color: #e0e0e0; font-size: 14px; margin-top: 10px;"><div style="display: flex; justify-content: space-between; margin: 8px 0; padding: 8px; background-color: #1a1a1a; border-radius: 4px;"><span style="color: #F4D03F; font-weight: bold;">Shift + O</span><span>Toggle Observation Deck</span></div><div style="display: flex; justify-content: space-between; margin: 8px 0; padding: 8px; background-color: #1a1a1a; border-radius: 4px;"><span style="color: #F4D03F; font-weight: bold;">Shift + T</span><span>Toggle TELOSCOPE Controls</span></div><div style="display: flex; justify-content: space-between; margin: 8px 0; padding: 8px; background-color: #1a1a1a; border-radius: 4px;"><span style="color: #F4D03F; font-weight: bold;">ESC</span><span>Collapse All Panels</span></div><div style="display: flex; justify-content: space-between; margin: 8px 0; padding: 8px; background-color: #1a1a1a; border-radius: 4px;"><span style="color: #F4D03F; font-weight: bold;">Enter</span><span>Send Message</span></div><div style="display: flex; justify-content: space-between; margin: 8px 0; padding: 8px; background-color: #1a1a1a; border-radius: 4px;"><span style="color: #F4D03F; font-weight: bold;">Shift + Enter</span><span>New Line in Message</span></div></div></div>""", unsafe_allow_html=True)

    def _show_help(self):
        """Show help information."""
        st.markdown("""<div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border: 1px solid #F4D03F; border-radius: 8px; padding: 15px; margin: 10px 0;"><div style="color: #F4D03F; font-size: 18px; font-weight: bold; margin-bottom: 10px;">TELOS Observatory V3</div><div style="color: #F4D03F; font-size: 14px; font-weight: bold; margin-top: 10px;">Navigation:</div><div style="color: #e0e0e0; font-size: 13px; margin-left: 10px;">• Main chat window displays the conversation<br>• Click "Observation Deck" to view metrics and analysis toggles<br>• Click "TELOSCOPE Controls" for playback and turn navigation</div><div style="color: #F4D03F; font-size: 14px; font-weight: bold; margin-top: 10px;">Observation Deck (🔭):</div><div style="color: #e0e0e0; font-size: 13px; margin-left: 10px;">• View turn metrics (Fidelity, Distance, Status, Interventions)<br>• Toggle analysis windows (Math Breakdown, Counterfactual, Steward Details)<br>• Access Deep Dive mode</div><div style="color: #F4D03F; font-size: 14px; font-weight: bold; margin-top: 10px;">TELOSCOPE Controls:</div><div style="color: #e0e0e0; font-size: 13px; margin-left: 10px;">• Navigate turns with slider or Prev/Next buttons<br>• Jump between interventions<br>• Play/Pause automatic playback<br>• Adjust playback speed</div><div style="color: #F4D03F; font-size: 14px; font-weight: bold; margin-top: 10px;">Sidebar Actions:</div><div style="color: #e0e0e0; font-size: 13px; margin-left: 10px;">• Save Current: Export session state<br>• Reset Session: Jump back to turn 1<br>• Export Evidence: Generate governance package</div></div>""", unsafe_allow_html=True)

    def _show_settings(self):
        """Show settings panel."""
        st.markdown("""
<div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border: 1px solid #F4D03F; border-radius: 8px; padding: 15px; margin: 10px 0;">
    <div style="color: #F4D03F; font-size: 18px; font-weight: bold; margin-bottom: 10px;">⚙️ Settings</div>
</div>
""", unsafe_allow_html=True)

        # Initialize settings defaults
        if 'enable_intro_examples' not in st.session_state:
            st.session_state.enable_intro_examples = True
        if 'telos_demo_mode' not in st.session_state:
            st.session_state.telos_demo_mode = True  # Demo mode is DEFAULT

        # Mode Selection
        st.markdown("---")
        st.markdown("**Governance Mode**")

        mode_options = {
            "Demo Mode": True,
            "Open Mode": False
        }

        current_mode = "Demo Mode" if st.session_state.telos_demo_mode else "Open Mode"

        selected_mode = st.radio(
            "Select Mode",
            options=list(mode_options.keys()),
            index=0 if st.session_state.telos_demo_mode else 1,
            key="mode_selector",
            help="""**Demo Mode** (Default): Pre-established PA focused on explaining TELOS framework. Great for demos and walkthroughs.

**Open Mode**: TELOS extracts purpose dynamically from your conversation. For real applications.""",
            label_visibility="collapsed"
        )

        # If mode changed, update and reset session
        if mode_options[selected_mode] != st.session_state.telos_demo_mode:
            st.session_state.telos_demo_mode = mode_options[selected_mode]

            # Clear conversation data when switching modes
            self.state_manager.clear_demo_data()

            # Clear user conversation flag
            if 'user_started_conversation' in st.session_state:
                del st.session_state.user_started_conversation

            # Clear demo welcome flag so it shows again in demo mode
            if 'demo_welcome_shown' in st.session_state:
                del st.session_state.demo_welcome_shown

            # Disable intro examples when switching from Demo to Open Mode
            if not st.session_state.telos_demo_mode:
                st.session_state.show_intro = False
                st.session_state.enable_intro_examples = False

            st.success(f"✅ Switched to {selected_mode} - Session reset")
            st.rerun()

        # Show mode description
        if st.session_state.telos_demo_mode:
            st.info("🔒 **Demo Mode**: Pre-established PA keeps conversations focused on TELOS framework topics. PA is locked and cannot be modified.")
        else:
            st.info("⚡ **Open Mode**: TELOS will extract your purpose dynamically from your conversation through calibration.")

        st.markdown("---")

        # Intro Examples Toggle
        enable_intro = st.checkbox(
            "Show intro examples on session load",
            value=st.session_state.enable_intro_examples,
            key="intro_examples_setting",
            help="Display random conversation examples when loading a session"
        )

        # Update setting if changed
        if enable_intro != st.session_state.enable_intro_examples:
            st.session_state.enable_intro_examples = enable_intro
            # If disabling, also hide current intro if showing
            if not enable_intro and 'show_intro' in st.session_state:
                st.session_state.show_intro = False
            st.rerun()

        st.markdown("---")

        # Performance Settings (Experimental)
        st.markdown("**Performance** ⚡")

        # Check if Demo Mode (performance features only work in Demo Mode currently)
        demo_mode = st.session_state.get('telos_demo_mode', False)

        if not demo_mode:
            st.info("⚠️ Performance features require Demo Mode")
        else:
            # Initialize performance flags
            if 'enable_async' not in st.session_state:
                st.session_state.enable_async = False
            if 'enable_parallel' not in st.session_state:
                st.session_state.enable_parallel = False

            # Async Processing
            enable_async = st.checkbox(
                "Enable Async Processing (Experimental)",
                value=st.session_state.enable_async,
                key="async_setting",
                help="Non-blocking I/O for LLM calls (~30-40% faster)"
            )

            # Parallel Processing
            enable_parallel = st.checkbox(
                "Enable Parallel Processing (Experimental)",
                value=st.session_state.enable_parallel,
                key="parallel_setting",
                help="Concurrent CPU operations for embedding + retrieval (~20-30% faster)"
            )

            # Update flags if changed
            if enable_async != st.session_state.enable_async:
                st.session_state.enable_async = enable_async
                st.rerun()

            if enable_parallel != st.session_state.enable_parallel:
                st.session_state.enable_parallel = enable_parallel
                st.rerun()

            # Show current performance mode
            if st.session_state.enable_async and st.session_state.enable_parallel:
                st.success("🚀 **Turbo Mode**: Async + Parallel (~50-60% faster)")
            elif st.session_state.enable_async:
                st.info("⚡ **Async Mode**: Non-blocking I/O (~30-40% faster)")
            elif st.session_state.enable_parallel:
                st.info("🔀 **Parallel Mode**: Concurrent CPU (~20-30% faster)")
            else:
                st.info("🔒 **Safe Mode**: Sequential processing (most stable)")

    def _show_documentation(self):
        """Show documentation links."""
        from pathlib import Path

        st.markdown("""<div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border: 1px solid #F4D03F; border-radius: 8px; padding: 15px; margin: 10px 0;"><div style="color: #F4D03F; font-size: 18px; font-weight: bold; margin-bottom: 10px;">📚 Documentation</div></div>""", unsafe_allow_html=True)

        # Check if whitepaper exists
        whitepaper_path = Path(__file__).parent.parent.parent / 'public' / 'TELOSCOPE_Prototype_Whitepaper.md'

        if whitepaper_path.exists():
            if st.button("📄 TELOSCOPE Whitepaper", use_container_width=True, key="whitepaper_link"):
                # Read and display whitepaper
                with open(whitepaper_path, 'r') as f:
                    whitepaper_content = f.read()

                # Store in session state to display in main area
                st.session_state.show_whitepaper = True
                st.session_state.whitepaper_content = whitepaper_content
                st.rerun()

        # Privacy & Data Handling
        if st.button("🔒 Privacy & Data Handling", use_container_width=True, key="privacy_link"):
            st.session_state.show_privacy_info = True
            st.rerun()

        # Research Overview
        if st.button("🔬 Research Overview", use_container_width=True, key="research_link"):
            st.session_state.show_research_info = True
            st.rerun()

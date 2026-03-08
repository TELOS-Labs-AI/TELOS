"""
BETA Observation Deck - Enhanced view for BETA testers
Ported from DEMO observation deck with:
- Alignment Lens header with Primacy State color border and drift status
- Three-box fidelity row (User Fidelity | AI Fidelity | Primacy State)
- Dual PA display (User PA + AI PA)
- Intervention type indicator
- Shift Telos button
"""

import streamlit as st
from telos_observatory.config.colors import (
    GOLD, get_fidelity_color, format_fidelity_percent,
    format_fidelity_display, ZONE_LEGEND_HTML, get_zone_name
)
from telos_observatory.config.steward_pa import STEWARD_PA
import html
from telos_observatory.services.fidelity_display import normalize_fidelity_for_display


class BetaObservationDeck:
    """Enhanced Observation Deck for BETA mode with DEMO styling."""

    def render(self):
        """Render the BETA observation deck with DEMO-style improvements."""
        import streamlit.components.v1 as components

        # Only show if PA is established
        if not st.session_state.get('pa_established', False):
            return

        # Only show if we have at least one completed turn with data
        # This prevents the ghost button on the welcome screen before any conversation
        state_manager = st.session_state.get('state_manager')
        has_turns = False
        if state_manager and hasattr(state_manager, 'state') and state_manager.state.turns:
            # Check if any turn has completed (has any data, not empty dict)
            for turn in state_manager.state.turns:
                # A completed turn will have user_input at minimum
                if turn.get('user_input') and not turn.get('is_loading', False):
                    has_turns = True
                    break

        if not has_turns:
            return  # Don't show Alignment Lens until first turn is complete

        # Skip rendering during loading/calculating state to prevent ghost UI elements
        is_loading = st.session_state.get('is_loading', False)

        # Check processing/generating flags (used in main.py for button visibility)
        is_processing = st.session_state.get('is_processing_input', False)
        is_generating = st.session_state.get('is_generating_response', False)

        # Check explicit BETA generating response flag (set before API calls)
        beta_generating = st.session_state.get('beta_generating_response', False)

        # Also check if ANY BETA turn is loading (turn-level state during Contemplating)
        # NOTE: beta_current_turn may be incremented for NEXT input, so search backwards
        current_turn = st.session_state.get('beta_current_turn', 1)
        turn_is_loading = False
        for turn_num in range(current_turn, 0, -1):
            turn_data = st.session_state.get(f'beta_turn_{turn_num}_data', {})
            if turn_data.get('is_loading', False) or turn_data.get('is_streaming', False):
                turn_is_loading = True
                break

        # Also check state_manager turns for loading state (used during initial load)
        state_manager = st.session_state.get('state_manager')
        if state_manager and hasattr(state_manager, 'state') and state_manager.state.turns:
            # Check the last turn for is_loading flag
            last_turn = state_manager.state.turns[-1]
            if last_turn.get('is_loading', False) or last_turn.get('is_streaming', False):
                turn_is_loading = True

        if is_loading or turn_is_loading or beta_generating or is_processing or is_generating:
            return

        # Initialize deck visibility state
        if 'beta_deck_visible' not in st.session_state:
            st.session_state.beta_deck_visible = False

        # Anchor for auto-scrolling
        st.markdown('<div id="beta-observation-deck-anchor"></div>', unsafe_allow_html=True)

        # Toggle button - full width, styled with user fidelity color for BETA mode
        deck_label = "Hide Alignment Lens" if st.session_state.beta_deck_visible else "Show Alignment Lens"

        # Get user fidelity color for button styling - use same pattern as badges/borders
        user_fidelity_btn, _, _, _ = self._get_fidelity_data()
        btn_color = get_fidelity_color(user_fidelity_btn) if user_fidelity_btn else "#27ae60"  # Default green

        # CSS injection using marker div + adjacent sibling selector (proven pattern from conversation_display.py)
        # This targets the button container immediately following the marker div
        st.markdown(f"""
<style>
/* Alignment Lens button - user fidelity colored border */
.alignment-lens-btn-marker + div button {{
    background-color: #2d2d2d !important;
    border: 2px solid {btn_color} !important;
    color: #e0e0e0 !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    padding: 12px 24px !important;
    transition: all 0.2s ease !important;
}}
.alignment-lens-btn-marker + div button:hover {{
    background-color: #3d3d3d !important;
    box-shadow: 0 0 12px {btn_color} !important;
    border: 2px solid {btn_color} !important;
}}
</style>
<div class="alignment-lens-btn-marker" style="display:none;"></div>
""", unsafe_allow_html=True)

        if st.button(deck_label, key="beta_deck_toggle_top", use_container_width=True):
            st.session_state.beta_deck_visible = not st.session_state.beta_deck_visible
            # Set flag to auto-scroll only when opening (not on every render)
            if st.session_state.beta_deck_visible:
                st.session_state.beta_deck_just_opened = True
                # Mutual exclusion: close Steward panel when Alignment Lens opens
                st.session_state.beta_steward_panel_open = False
            st.rerun()

        # Show "Shift Focus to This" button when in drift zone (< 0.60)
        # This is OUTSIDE the Alignment Lens expanded section - always visible when in drift
        # User's constitutional authority to redefine session purpose
        user_fidelity_check, _, _, _ = self._get_fidelity_data()
        show_shift_focus = user_fidelity_check is not None and user_fidelity_check < 0.60

        if show_shift_focus:
            # Get the user's last message that triggered drift
            # NOTE: beta_current_turn is already incremented for NEXT input, so we search backwards
            current_turn = st.session_state.get('beta_current_turn', 1)
            user_message = ''
            for turn_num in range(current_turn, 0, -1):
                turn_data = st.session_state.get(f'beta_turn_{turn_num}_data', {})
                if turn_data.get('user_input'):
                    user_message = turn_data.get('user_input', '')
                    break

            # Get color for button styling
            user_color = get_fidelity_color(user_fidelity_check)

            # CSS injection - same pattern as Alignment Lens button
            st.markdown(f"""
<style>
/* Shift Focus button - user fidelity colored border */
.shift-focus-btn-marker + div button {{
    background-color: #2d2d2d !important;
    border: 2px solid {user_color} !important;
    color: #e0e0e0 !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    padding: 12px 24px !important;
    transition: all 0.2s ease !important;
}}
.shift-focus-btn-marker + div button:hover {{
    background-color: #3d3d3d !important;
    box-shadow: 0 0 12px {user_color} !important;
    border: 2px solid {user_color} !important;
}}
</style>
<div class="shift-focus-btn-marker" style="display:none;"></div>
""", unsafe_allow_html=True)

            # Button immediately after marker
            if st.button("Shift Focus to This", key="main_shift_focus",
                        help="Update your session focus to match your new direction",
                        use_container_width=True):
                # Use spinner to show visual feedback during processing
                with st.spinner("Shifting focus..."):
                    # Direct PA enrichment - same as Steward but without chat acknowledgment
                    self._handle_direct_pa_shift(user_message)
                st.rerun()

            # "Ask Steward Why" button - opens Steward panel with intervention context
            # CSS for Ask Steward Why button - same styling as Shift Focus
            st.markdown(f"""
<style>
/* Ask Steward Why button - user fidelity colored border */
.ask-steward-why-btn-marker + div button {{
    background-color: #2d2d2d !important;
    border: 2px solid {user_color} !important;
    color: #e0e0e0 !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    padding: 12px 24px !important;
    transition: all 0.2s ease !important;
}}
.ask-steward-why-btn-marker + div button:hover {{
    background-color: #3d3d3d !important;
    box-shadow: 0 0 12px {user_color} !important;
    border: 2px solid {user_color} !important;
}}
</style>
<div class="ask-steward-why-btn-marker" style="display:none;"></div>
""", unsafe_allow_html=True)

            if st.button("Ask Steward Why", key="main_ask_steward_why",
                        help="Ask Steward to explain why this was flagged as drift",
                        use_container_width=True):
                # Set intervention turn for Steward to explain
                current_turn_for_why = st.session_state.get('beta_current_turn', 1)
                # Find the most recent completed turn
                for turn_num in range(current_turn_for_why, 0, -1):
                    turn_data = st.session_state.get(f'beta_turn_{turn_num}_data', {})
                    if turn_data:
                        st.session_state.steward_intervention_turn = turn_num
                        break
                # Open Steward panel and close Alignment Lens (mutual exclusion)
                st.session_state.beta_steward_panel_open = True
                st.session_state.beta_deck_visible = False
                # Auto-scroll to Steward section
                st.session_state.scroll_to_steward = True
                st.rerun()

        # Render deck content if visible
        if st.session_state.beta_deck_visible:
            # Auto-scroll to Alignment Lens anchor ONLY when just opened (not on every render)
            # This prevents scroll jumping when Steward panel is toggled
            if st.session_state.get('beta_deck_just_opened', False):
                st.session_state.beta_deck_just_opened = False  # Clear flag
                components.html("""
<script>
    // Scroll parent window to the Alignment Lens anchor element
    setTimeout(function() {
        var anchor = window.parent.document.getElementById('beta-observation-deck-anchor');
        if (anchor) {
            anchor.scrollIntoView({behavior: 'smooth', block: 'start'});
        } else {
            // Fallback: scroll to the button that triggered this (approximate location)
            window.parent.document.documentElement.scrollTo({
                top: window.parent.document.documentElement.scrollHeight - window.parent.innerHeight + 100,
                behavior: 'smooth'
            });
        }
    }, 150);
</script>
""", height=0)

            # Animation styles
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

            # Render Alignment Lens header
            self._render_alignment_lens_header()

            # Only show fidelity if there's at least one turn
            current_turn = st.session_state.get('beta_current_turn', 1)
            state_manager = st.session_state.get('state_manager')
            has_turns = (current_turn > 1) or (state_manager and len(state_manager.get_all_turns()) > 0)

            if has_turns:
                # Render three-box fidelity row (DEMO style)
                st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
                self._render_fidelity_row()

                # Render intervention type only for green/yellow zones (>= 0.60)
                # For orange/red zones, we show detailed intervention info below attractors instead
                user_fidelity_check, _, _, _ = self._get_fidelity_data()
                if user_fidelity_check is None or user_fidelity_check >= 0.60:
                    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
                    self._render_intervention_type()

            # Render dual PA display (wrapped in outer container) - tighter spacing
            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
            self._render_dual_pa()

            # NOTE: "Drift Detected" section and "Ask Steward Why" buttons removed for Beta MVP
            # These caused display issues similar to other button rendering problems

    def _render_alignment_lens_header(self):
        """Render the Alignment Lens header as a compact bar with USER fidelity color border and drift status."""
        # Get fidelity data - use USER fidelity for border color (follows user's alignment)
        user_fidelity, ai_fidelity, _, _ = self._get_fidelity_data()

        # Use USER fidelity for border color (Alignment Lens follows user's fidelity)
        user_color = get_fidelity_color(user_fidelity) if user_fidelity else "#27ae60"  # Default green

        # Determine drift status based on USER fidelity
        if user_fidelity is None:
            drift_status = "Aligned"
            drift_color = "#27ae60"
        elif user_fidelity >= 0.70:
            drift_status = "Aligned"
            drift_color = "#27ae60"
        elif user_fidelity >= 0.60:
            drift_status = "Minor Drift"
            drift_color = "#F4D03F"
        elif user_fidelity >= 0.50:
            drift_status = "Moderate Drift"
            drift_color = "#FFA500"
        else:
            drift_status = "Severe Drift"
            drift_color = "#FF4444"

        # Generate glow from user color
        def get_glow_color(hex_color):
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return f"rgba({r}, {g}, {b}, 0.3)"

        user_glow = get_glow_color(user_color)

        # Compact horizontal bar design - title on left, status on right
        st.markdown(f"""
<div style="max-width: 100%; margin: 0 auto; opacity: 0; animation: obsDeckFadeIn 1.0s ease-in-out forwards;">
    <div style="background-color: #1a1a1a; border: 2px solid {user_color}; border-radius: 8px; padding: 12px 20px; box-shadow: 0 0 15px {user_glow}; display: flex; justify-content: space-between; align-items: center;">
        <span style="color: {user_color}; font-size: 18px; font-weight: bold;">Alignment Lens</span>
        <span style="background-color: #2d2d2d; border: 1px solid {drift_color}; border-radius: 15px; padding: 5px 15px; color: {drift_color}; font-weight: bold; font-size: 13px;">{drift_status}</span>
    </div>
</div>
""", unsafe_allow_html=True)

    def _get_fidelity_data(self):
        """Extract fidelity data from session state. Returns (user_fidelity, ai_fidelity, primacy_state, intervention_type).

        IMPORTANT: Uses the SAME data source as conversation_display.py (beta_turn_N_data)
        to ensure values match exactly between Alignment Lens and Conversation Display.

        NOTE: Returns primacy_state from turn_data (NOT calculated) to match conversation_display.py

        OPTIMIZATION: Caches result for render cycle to avoid 80+ session_state lookups per call.
        Cache is keyed by turn number and pa_just_shifted flag, automatically invalidates when turn changes.
        """
        # Check for cached result (keyed by turn and pa_just_shifted to auto-invalidate)
        current_turn = st.session_state.get('beta_current_turn', 1)
        pa_shifted = st.session_state.get('pa_just_shifted', False)
        cache_key = f"{current_turn}_{pa_shifted}"

        # DEBUG: Log what we're about to check BEFORE cache check
        print(f"🔍 UI FIDELITY CHECK: current_turn={current_turn}, cache_key={cache_key}")

        # Check what's in the current turn's data
        debug_turn_data = st.session_state.get(f'beta_turn_{current_turn}_data', {})
        debug_telos = debug_turn_data.get('telos_analysis', {})
        print(f"   turn_data exists: {bool(debug_turn_data)}, telos_analysis exists: {bool(debug_telos)}")
        if debug_telos:
            print(f"   display_user_pa_fidelity: {debug_telos.get('display_user_pa_fidelity')}")
            print(f"   user_pa_fidelity: {debug_telos.get('user_pa_fidelity')}")
        print(f"   turn_data.display_fidelity: {debug_turn_data.get('display_fidelity')}")

        if hasattr(self, '_fidelity_cache_key') and self._fidelity_cache_key == cache_key:
            if hasattr(self, '_fidelity_cache'):
                cached = self._fidelity_cache
                # ONLY use cache if it contains valid data (not all None)
                # This prevents stale cache from streaming phase before data is stored
                if cached[0] is not None or cached[1] is not None:
                    return cached
                # Otherwise fall through to re-fetch (data may have been stored since caching)

        # NOTE: Removed pa_just_shifted short-circuit (2025-12-26)
        # Previously this returned hardcoded (1.0, 1.0, 1.0, None) when PA was shifted,
        # which caused off-topic content to display 100% fidelity even when interventions
        # correctly identified drift. Now we always fetch real fidelity values from turn data.

        user_fidelity = None
        ai_fidelity = None
        primacy_state = None
        intervention_type = None

        current_turn = st.session_state.get('beta_current_turn', 1)

        # Find the latest turn with valid data by searching backwards from current_turn
        # This mirrors exactly how conversation_display.py accesses turn data
        for turn_num in range(current_turn, 0, -1):
            turn_data = st.session_state.get(f'beta_turn_{turn_num}_data', {})
            if not turn_data:
                continue

            telos_analysis = turn_data.get('telos_analysis', {})

            # DEBUG: Print what we find in turn_data for visibility
            print(f"🔍 UI FIDELITY READ Turn {turn_num}:")
            print(f"   turn_data keys: {list(turn_data.keys())[:10]}")  # First 10 keys
            print(f"   telos_analysis keys: {list(telos_analysis.keys())[:10]}")
            print(f"   display_fidelity: {turn_data.get('display_fidelity')}")
            print(f"   display_user_pa_fidelity: {telos_analysis.get('display_user_pa_fidelity')}")
            print(f"   user_pa_fidelity: {telos_analysis.get('user_pa_fidelity')}")
            ps_metrics = turn_data.get('ps_metrics', {})
            beta_data = turn_data.get('beta_data', {})

            # === PRIMACY STATE - exact same logic as conversation_display.py ===
            # Priority 1: Display-normalized PS (for UI consistency)
            primacy_state = telos_analysis.get('display_primacy_state')

            # Priority 2: Direct turn_data display_primacy_state
            if primacy_state is None:
                primacy_state = turn_data.get('display_primacy_state')

            # Priority 3: Raw primacy_state_score (fallback for non-normalized flows)
            if primacy_state is None:
                primacy_state = turn_data.get('primacy_state_score')

            # Also check ps_metrics dict if primacy_state_score not directly available
            if primacy_state is None and ps_metrics:
                primacy_state = ps_metrics.get('ps_score')

            # Check inside telos_analysis for primacy_state_score (raw fallback)
            if primacy_state is None:
                primacy_state = telos_analysis.get('primacy_state_score')

            # === USER FIDELITY - exact same logic as conversation_display.py ===
            # Priority 1: Normalized display value (for UI)
            user_fidelity = telos_analysis.get('display_user_pa_fidelity')

            # Priority 2: Direct turn_data display_fidelity
            if user_fidelity is None:
                user_fidelity = turn_data.get('display_fidelity')

            # Priority 3: Raw user_pa_fidelity
            if user_fidelity is None:
                user_fidelity = turn_data.get('user_pa_fidelity')
            if user_fidelity is None and ps_metrics:
                user_fidelity = ps_metrics.get('f_user')

            # Priority 4: Check telos_analysis for user_pa_fidelity (raw)
            if user_fidelity is None:
                user_fidelity = telos_analysis.get('user_pa_fidelity')

            # Priority 5: Fallback beta_data
            if user_fidelity is None:
                user_fidelity = beta_data.get('user_fidelity') or beta_data.get('input_fidelity')

            # === AI FIDELITY - exact same logic as conversation_display.py ===
            # Priority 1: Direct turn_data (state_manager path)
            ai_fidelity = turn_data.get('ai_pa_fidelity')

            # Priority 2: ps_metrics dict
            if ai_fidelity is None and ps_metrics:
                ai_fidelity = ps_metrics.get('f_ai')

            # Priority 3: Check telos_analysis for ai_pa_fidelity
            if ai_fidelity is None:
                ai_fidelity = telos_analysis.get('ai_pa_fidelity')

            # Priority 4: Legacy fallbacks
            if ai_fidelity is None:
                legacy_fidelity = beta_data.get('telos_fidelity') or beta_data.get('fidelity_score')
                if legacy_fidelity is not None and legacy_fidelity > 0:
                    ai_fidelity = legacy_fidelity

            if ai_fidelity is None:
                legacy_score = telos_analysis.get('fidelity_score')
                if legacy_score is not None and legacy_score > 0:
                    ai_fidelity = legacy_score

            # Priority 5: Last resort fallback
            if ai_fidelity is None:
                ai_fidelity = turn_data.get('fidelity')

            # === INTERVENTION TYPE ===
            intervention_type = telos_analysis.get('intervention_type') or turn_data.get('intervention_type')

            # If we found valid fidelity data, stop searching
            if user_fidelity is not None or ai_fidelity is not None:
                break

        # If still no AI fidelity, estimate it (AI typically stays aligned)
        if ai_fidelity is None and user_fidelity is not None:
            ai_fidelity = min(1.0, user_fidelity + 0.15) if user_fidelity else None

        # Fallback: calculate PS if we have fidelities but no stored PS
        if primacy_state is None and user_fidelity is not None and ai_fidelity is not None:
            epsilon = 1e-10
            if user_fidelity + ai_fidelity > epsilon:
                primacy_state = (2 * user_fidelity * ai_fidelity) / (user_fidelity + ai_fidelity + epsilon)

        # Cache result for this render cycle (avoids 80+ session_state lookups on repeat calls)
        # Only cache if we found valid data - prevents caching empty results during streaming
        result = (user_fidelity, ai_fidelity, primacy_state, intervention_type)
        if user_fidelity is not None or ai_fidelity is not None:
            self._fidelity_cache_key = cache_key
            self._fidelity_cache = result
        return result

    def _handle_direct_pa_shift(self, new_direction: str):
        """Handle direct PA shift from Alignment Lens button.

        Uses PA enrichment to generate a new PA based on the user's
        actual interest, then updates the session. Same as Steward's
        _handle_shift_focus but without the chat acknowledgment.

        Args:
            new_direction: The user input to pivot to
        """
        import logging
        # DEBUG: Track active_tab before PA shift
        active_tab_before = st.session_state.get('active_tab', 'NOT_SET')
        logging.warning(f"🔄 DIRECT PA SHIFT CALLED with: '{new_direction[:50] if new_direction else 'EMPTY'}...'")
        logging.warning(f"🔄 ACTIVE_TAB BEFORE PA SHIFT: '{active_tab_before}'")
        print(f"🔄 DIRECT PA SHIFT CALLED with: '{new_direction[:50] if new_direction else 'EMPTY'}...'")
        print(f"🔄 ACTIVE_TAB BEFORE PA SHIFT: '{active_tab_before}'")

        if not new_direction:
            logging.warning("🔄 DIRECT PA SHIFT: Empty direction, returning")
            return

        try:
            from telos_observatory.services.pa_enrichment import PAEnrichmentService
            from mistralai import Mistral
            import os
            import numpy as np
            logging.warning("🔄 DIRECT PA SHIFT: Imports successful")

            # Get API key
            try:
                api_key = st.secrets.get("MISTRAL_API_KEY")
            except (FileNotFoundError, KeyError):
                api_key = os.environ.get("MISTRAL_API_KEY")

            if not api_key:
                st.error("Cannot shift focus: MISTRAL_API_KEY not configured")
                return

            # Create enrichment service and generate new PA
            client = Mistral(api_key=api_key)
            enrichment_service = PAEnrichmentService(client)

            enriched_pa = enrichment_service.enrich_direction(new_direction)

            if enriched_pa:
                # Import dual attractor derivation
                from telos_observatory.services.beta_dual_attractor import derive_ai_pa_from_user_pa

                # Build User PA structure (purpose as list for consistency)
                user_pa = {
                    'purpose': [enriched_pa.get('purpose', new_direction)],
                    'scope': enriched_pa.get('scope', []),
                    'boundaries': enriched_pa.get('boundaries', []),
                    'success_criteria': f"Explore: {new_direction}",
                    'style': st.session_state.get('primacy_attractor', {}).get('style', 'balanced'),
                }

                # DUAL ATTRACTOR: Derive AI PA from User PA using intent-to-role mapping
                # This ensures Steward Attractor stays synchronized with User PA
                ai_pa = derive_ai_pa_from_user_pa(user_pa)

                # Update session state with BOTH PAs (fixes desync bug)
                st.session_state.primacy_attractor = user_pa
                st.session_state.user_pa = user_pa
                st.session_state.ai_pa = ai_pa

                # Update template title to reflect new focus
                if 'selected_template' in st.session_state:
                    short_title = new_direction[:40] + ('...' if len(new_direction) > 40 else '')
                    st.session_state.selected_template = {
                        **st.session_state.selected_template,
                        'title': short_title,
                        'shifted': True
                    }

                # Clear ALL cached PA embeddings so response manager rebuilds them
                # The response manager caches these at initialization, so we need to invalidate
                cached_keys_to_clear = [
                    'cached_user_pa_embedding',       # MiniLM user PA (for user fidelity)
                    'cached_mpnet_user_pa_embedding', # MPNet user PA (for GREEN zone AI fidelity)
                    'cached_mpnet_ai_pa_embedding',   # MPNet AI PA
                    'cached_ai_pa_embedding',         # AI PA embedding
                    'cached_st_user_pa_embedding',    # SentenceTransformer user PA
                    'user_pa_embedding',              # Direct user PA reference
                ]
                for key in cached_keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]

                # Invalidate response manager so it rebuilds with new PA
                if 'beta_response_manager' in st.session_state:
                    del st.session_state['beta_response_manager']

                # Rebuild BOTH PA embeddings using dual attractor system
                self._rebuild_pa_embeddings_dual(user_pa, ai_pa)

                # Set flag so observation deck knows to show "Focus shifted" instead of stale data
                # This also triggers fidelity display to show 1.00 (perfect alignment)
                st.session_state.pa_just_shifted = True

                # DEBUG: Track active_tab AFTER PA shift completes
                active_tab_after = st.session_state.get('active_tab', 'NOT_SET')
                logging.warning(f"🔄 PA SHIFT COMPLETE - active_tab AFTER: '{active_tab_after}'")
                print(f"🔄 PA SHIFT COMPLETE - active_tab AFTER: '{active_tab_after}'")

            else:
                st.error("Could not generate new focus. Please try again.")

        except Exception as e:
            st.error(f"Error shifting focus: {str(e)}")

    def _rebuild_pa_embedding(self, enriched_pa: dict):
        """Rebuild the PA embedding after a focus shift.

        Args:
            enriched_pa: The new enriched PA structure
        """
        try:
            # Use CACHED provider to avoid expensive model reloading (critical for Railway cold start)
            from telos_core.embedding_provider import get_cached_minilm_provider
            import numpy as np

            # Get or create embedding provider using cached version
            if 'embedding_provider' not in st.session_state:
                st.session_state.embedding_provider = get_cached_minilm_provider()

            provider = st.session_state.embedding_provider

            # Generate new centroid from example queries
            example_queries = enriched_pa.get('example_queries', [])
            if example_queries:
                embeddings = [provider.encode(q) for q in example_queries]
                centroid = np.mean(embeddings, axis=0)
                centroid = centroid / np.linalg.norm(centroid)  # Normalize

                st.session_state.user_pa_embedding = centroid

        except Exception as e:
            # Log but don't fail - the PA text update is still useful
            print(f"Warning: Could not rebuild PA embedding: {e}")

    def _rebuild_pa_embeddings_dual(self, user_pa: dict, ai_pa: dict):
        """Rebuild both PA embeddings after a focus shift using dual attractor.

        Uses compute_pa_embeddings() for mathematically coupled embeddings.
        This ensures User PA and AI PA (Steward Attractor) stay synchronized.

        Args:
            user_pa: The new user PA structure
            ai_pa: The derived AI PA structure
        """
        try:
            from telos_core.embedding_provider import get_cached_minilm_provider
            import numpy as np
            import logging

            # CRITICAL: Use the SAME cached MiniLM provider that response_manager uses
            # This ensures dimension compatibility (384-dim) for template mode fidelity
            provider = get_cached_minilm_provider()

            # Build PA text from purpose + scope (same as compute_pa_embeddings)
            user_purpose = user_pa.get('purpose', [])
            user_scope = user_pa.get('scope', [])
            user_purpose_text = ' '.join(user_purpose) if isinstance(user_purpose, list) else str(user_purpose)
            user_scope_text = ' '.join(user_scope) if isinstance(user_scope, list) else str(user_scope)
            user_pa_text = f"{user_purpose_text} {user_scope_text}"

            ai_purpose = ai_pa.get('purpose', [])
            ai_scope = ai_pa.get('scope', [])
            ai_purpose_text = ' '.join(ai_purpose) if isinstance(ai_purpose, list) else str(ai_purpose)
            ai_scope_text = ' '.join(ai_scope) if isinstance(ai_scope, list) else str(ai_scope)
            ai_pa_text = f"{ai_purpose_text} {ai_scope_text}"

            # Compute embeddings with MiniLM provider
            user_embedding = np.array(provider.encode(user_pa_text))
            ai_embedding = np.array(provider.encode(ai_pa_text))

            # Normalize to unit vectors (consistent with compute_pa_embeddings)
            user_embedding = user_embedding / (np.linalg.norm(user_embedding) + 1e-10)
            ai_embedding = ai_embedding / (np.linalg.norm(ai_embedding) + 1e-10)

            # Cache both embeddings - no lazy computation
            # CRITICAL: Response manager looks for 'cached_st_user_pa_embedding' for template mode fidelity
            st.session_state.cached_user_pa_embedding = user_embedding
            st.session_state.cached_ai_pa_embedding = ai_embedding
            st.session_state.cached_st_user_pa_embedding = user_embedding  # Template mode key
            st.session_state.user_pa_embedding = user_embedding  # Legacy key

            # CRITICAL FIX: Update cached_pa_identity to match the new PA
            # Without this, BetaResponseManager._setup_embedding_provider() will detect a mismatch
            # and DELETE the embeddings we just cached (see beta_response_manager.py line ~2142)
            import hashlib
            new_pa_identity = hashlib.md5(f"{user_purpose_text}|{user_scope_text}".encode()).hexdigest()[:16]
            st.session_state.cached_pa_identity = new_pa_identity
            logging.info(f"   🔑 Updated cached_pa_identity to: {new_pa_identity}")

            logging.info(f"Dual attractor embeddings computed at focus shift time (MiniLM {len(user_embedding)}d)")

        except Exception as e:
            # Log but don't fail - the PA text update is still useful
            print(f"Warning: Could not rebuild PA embeddings: {e}")

    def _render_fidelity_row(self):
        """Render three-box fidelity row: User Fidelity | AI Fidelity | Primacy State.

        Updated per UI/UX audit to display percentages with letter grades for better intuition.
        """
        # Get fidelity data - always uses actual turn data to match conversation_display.py
        # IMPORTANT: primacy_state comes from turn_data (same as conversation_display.py)
        # NOT calculated here - this ensures values match exactly
        user_fidelity, ai_fidelity, primacy_state, _ = self._get_fidelity_data()

        # Get colors (use 'is not None' to handle fidelity=0 correctly)
        user_color = get_fidelity_color(user_fidelity) if user_fidelity is not None else "#888888"
        ai_color = get_fidelity_color(ai_fidelity) if ai_fidelity is not None else "#888888"
        ps_color = get_fidelity_color(primacy_state) if primacy_state is not None else "#888888"

        # Format displays as percentages with letter grades (more intuitive than decimals)
        user_pct = format_fidelity_percent(user_fidelity)
        ai_pct = format_fidelity_percent(ai_fidelity)
        ps_pct = format_fidelity_percent(primacy_state)

        # Determine zone labels for fidelity display (using canonical colors)
        # Uses get_zone_name/get_fidelity_color from colors.py which handles string percentages
        def get_zone_label(fidelity):
            if fidelity is None:
                return ("---", "#888")
            # Use the centralized functions that handle both floats and strings
            zone = get_zone_name(fidelity)
            color = get_fidelity_color(fidelity)
            return (zone, color)

        user_zone, user_zone_color = get_zone_label(user_fidelity)
        ai_zone, ai_zone_color = get_zone_label(ai_fidelity)
        ps_zone, ps_zone_color = get_zone_label(primacy_state)

        # Helper to convert hex color to rgba glow
        def get_glow_color(hex_color):
            """Convert hex color to rgba glow."""
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return f"rgba({r}, {g}, {b}, 0.4)"

        # Generate glow colors for each metric
        user_glow = get_glow_color(user_color)
        ai_glow = get_glow_color(ai_color)
        ps_glow = get_glow_color(ps_color)

        # Zone legend - helps first-time users understand the system
        st.markdown(ZONE_LEGEND_HTML, unsafe_allow_html=True)

        # Full-width fidelity boxes with percentage display
        st.markdown(f"""
<div style="display: flex; justify-content: center; gap: 10px; margin: 15px auto; max-width: 100%;">
    <div style="background-color: #1a1a1a; border: 2px solid {user_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1; box-shadow: 0 4px 20px {user_glow};">
        <div style="color: {user_color}; font-size: 16px; font-weight: bold; margin-bottom: 10px;">User Fidelity</div>
        <div style="color: {user_color}; font-size: 38px; font-weight: bold;">{user_pct}</div>
        <div style="color: {user_zone_color}; font-size: 13px; margin-top: 8px;">{user_zone}</div>
    </div>
    <div style="background-color: #1a1a1a; border: 2px solid {ai_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1; box-shadow: 0 4px 20px {ai_glow};">
        <div style="color: {ai_color}; font-size: 16px; font-weight: bold; margin-bottom: 10px;">AI Fidelity</div>
        <div style="color: {ai_color}; font-size: 38px; font-weight: bold;">{ai_pct}</div>
        <div style="color: {ai_zone_color}; font-size: 13px; margin-top: 8px;">{ai_zone}</div>
    </div>
    <div style="background-color: #1a1a1a; border: 2px solid {ps_color}; border-radius: 10px; padding: 20px; text-align: center; flex: 1; box-shadow: 0 4px 20px {ps_glow};">
        <div style="color: {ps_color}; font-size: 16px; font-weight: bold; margin-bottom: 10px;">Primacy State</div>
        <div style="color: {ps_color}; font-size: 38px; font-weight: bold;">{ps_pct}</div>
        <div style="color: {ps_zone_color}; font-size: 13px; margin-top: 8px;">{ps_zone}</div>
    </div>
</div>
""", unsafe_allow_html=True)

    def _render_intervention_type(self):
        """Render intervention type indicator for green/yellow zones only.

        This is only called when user_fidelity >= 0.60 (green or yellow zones).
        For orange/red zones, the intervention details section is shown instead.

        New thresholds:
        - >= 0.70: "Monitoring" (green)
        - 0.65-0.70: "Minor Drift Detected - Monitoring for Intervention" (yellow)
        - 0.60-0.65: "Minor Drift Detected - Intervention Active" (yellow)
        """
        user_fidelity, _, _, _ = self._get_fidelity_data()

        # Derive mode based on new thresholds
        if user_fidelity is None or user_fidelity >= 0.70:
            # GREEN zone - pure monitoring
            label = "Monitoring"
            color = "#27ae60"
            desc = "No intervention needed"
        elif user_fidelity >= 0.65:
            # YELLOW upper (0.65-0.70) - monitoring for potential intervention
            label = "Minor Drift Detected"
            color = "#F4D03F"
            desc = "Monitoring for intervention"
        else:
            # YELLOW lower (0.60-0.65) - intervention is active but nuanced
            label = "Minor Drift Detected"
            color = "#F4D03F"
            desc = "Intervention active"

        st.markdown(f"""
<div style="max-width: 100%; margin: 0 auto;">
    <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border: 2px solid {color}; border-radius: 8px; padding: 12px 20px; text-align: center;">
        <div style="color: {color}; font-size: 14px; font-weight: bold; margin-bottom: 4px;">
            Current Mode: {label}
        </div>
        <div style="color: #888; font-size: 12px;">
            {desc}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    # NOTE: _render_intervention_details method removed for Beta MVP
    # The "Drift Detected" section caused display issues similar to other buttons

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

        # Get AI PA data - use derived AI PA if available, fallback to STEWARD_PA template
        derived_ai_pa = st.session_state.get('ai_pa', {})
        if derived_ai_pa:
            # Use the mathematically derived AI PA (from dual attractor)
            steward_purpose = safe_escape(derived_ai_pa.get('purpose'), 'Not set')
            steward_scope = safe_escape(derived_ai_pa.get('scope'), 'Not set')
            steward_boundaries = safe_escape(derived_ai_pa.get('boundaries'), 'Not set')
        else:
            # Fallback to hardcoded Steward PA (for backwards compatibility)
            steward_purpose = safe_escape(STEWARD_PA.get('purpose'), 'Not set')
            steward_scope = safe_escape(STEWARD_PA.get('scope'), 'Not set')
            steward_boundaries = safe_escape(STEWARD_PA.get('boundaries'), 'Not set')

        # Get colors for User PA (based on user fidelity)
        user_fidelity, ai_fidelity, _, _ = self._get_fidelity_data()
        user_color = get_fidelity_color(user_fidelity) if user_fidelity else "#27ae60"
        ai_color = get_fidelity_color(ai_fidelity) if ai_fidelity else "#27ae60"

        # Generate glow colors (rgba versions of the fidelity colors)
        def get_glow_color(hex_color):
            """Convert hex color to rgba glow."""
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return f"rgba({r}, {g}, {b}, 0.4)"

        user_glow = get_glow_color(user_color)
        ai_glow = get_glow_color(ai_color)

        # Render both PA columns inside an outer container with click-to-expand in-place
        # Using components.html() instead of st.markdown() to enable JavaScript execution
        attractor_html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: transparent;
}}
/* Clickable attractor cards */
.attractor-card {{
    cursor: pointer;
    transition: all 0.3s ease;
}}
.attractor-card:hover {{
    transform: translateY(-2px);
}}
/* Expanded card takes full width */
.attractor-card.expanded {{
    flex: 1 1 100% !important;
}}
/* Hide collapsed card when sibling is expanded */
.attractor-card.collapsed {{
    display: none;
}}
/* Expanded content styling */
.attractor-content {{
    transition: all 0.3s ease;
}}
.attractor-card.expanded .attractor-content {{
    padding: 24px;
}}
.attractor-card.expanded .attractor-label {{
    font-size: 16px !important;
    margin-bottom: 10px !important;
}}
.attractor-card.expanded .attractor-value {{
    font-size: 15px !important;
    margin-bottom: 18px !important;
    line-height: 1.7 !important;
}}
</style>
</head>
<body>

<div id="attractor-container" style="max-width: 100%; margin: 15px auto; background-color: #1a1a1a; border: 2px solid #444; border-radius: 12px; padding: 20px;">
    <div id="attractor-flex" style="display: flex; gap: 15px; flex-wrap: wrap;">
        <!-- User PA Column (click to expand/collapse) -->
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
        <!-- Steward Attractor Column (click to expand/collapse) -->
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
        // Collapse - show both cards side by side
        userCard.classList.remove('expanded', 'collapsed');
        stewardCard.classList.remove('expanded', 'collapsed');
        userHint.textContent = '(click to expand)';
        stewardHint.textContent = '(click to expand)';
        expandedCard = null;
    }} else {{
        // Expand clicked card, hide other
        clickedCard.classList.add('expanded');
        clickedCard.classList.remove('collapsed');
        otherCard.classList.add('collapsed');
        otherCard.classList.remove('expanded');

        if (type === 'user') {{
            userHint.textContent = '(click to collapse)';
        }} else {{
            stewardHint.textContent = '(click to collapse)';
        }}
        expandedCard = type;
    }}

    // Update iframe height after a brief delay for CSS transition
    setTimeout(updateFrameHeight, 50);
}}

function updateFrameHeight() {{
    const container = document.getElementById('attractor-container');
    const newHeight = container.offsetHeight + 40; // Add padding

    // Send height to parent frame
    if (window.frameElement) {{
        window.frameElement.style.height = newHeight + 'px';
    }}
}}

// Initial height update
setTimeout(updateFrameHeight, 100);
</script>
</body>
</html>
"""
        # Use components.html() to render with working JavaScript
        # Height set to 350 for collapsed state - JS will dynamically expand when cards are clicked
        components.html(attractor_html, height=350, scrolling=False)

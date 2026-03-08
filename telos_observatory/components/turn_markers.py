"""
Turn Marker Component for BETA Mode
====================================

Displays turn numbers with careful positioning to avoid
rendering issues that have plagued previous implementations.
"""

import streamlit as st

# Import color configuration
from telos_observatory.config.colors import GOLD, STATUS_GOOD


def render_turn_marker(turn_number: int, mode: str = "beta") -> str:
    """
    Generate HTML for a turn marker with proper z-index and positioning.

    Args:
        turn_number: The turn number to display
        mode: The mode (beta, demo, etc) for styling

    Returns:
        HTML string for the turn marker
    """
    # Different colors based on mode
    color_scheme = {
        "demo": GOLD,  # Gold for demo
        "beta": "#27ae60",  # Green for beta (canonical TELOS green)
        "telos": "#00BFFF",  # Blue for full TELOS
        "devops": "#FF6B6B"  # Red for devops
    }

    marker_color = color_scheme.get(mode, GOLD)

    # Return carefully styled turn marker
    # Using position:relative and high z-index to stay above content
    # Using inline-block to prevent breaking layouts
    return f"""
    <div class="turn-marker" style="
        position: relative;
        display: inline-block;
        background-color: {marker_color};
        color: #000;
        font-size: 12px;
        font-weight: bold;
        padding: 2px 8px;
        border-radius: 12px;
        margin-right: 10px;
        margin-bottom: 5px;
        z-index: 1000;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        white-space: nowrap;
    ">
        Turn #{turn_number}
    </div>
    """


def render_turn_marker_inline(turn_number: int, mode: str = "beta") -> str:
    """
    Generate inline turn marker that won't break text flow.

    Args:
        turn_number: The turn number to display
        mode: The mode for styling

    Returns:
        HTML string for inline turn marker
    """
    color_scheme = {
        "demo": GOLD,
        "beta": "#27ae60",
        "telos": "#00BFFF",
        "devops": "#FF6B6B"
    }

    marker_color = color_scheme.get(mode, GOLD)

    # More subtle inline version
    return f"""
    <span class="turn-marker-inline" style="
        display: inline-block;
        background-color: {marker_color}22;
        color: {marker_color};
        font-size: 11px;
        font-weight: bold;
        padding: 1px 6px;
        border: 1px solid {marker_color};
        border-radius: 10px;
        margin: 0 5px;
        vertical-align: middle;
        white-space: nowrap;
    ">
        T{turn_number}
    </span>
    """


def inject_turn_marker_css():
    """
    Inject global CSS for turn markers to ensure consistency.
    Call this once at app startup.
    """
    st.markdown("""
    <style>
    /* Turn marker animations */
    .turn-marker {
        animation: fadeIn 0.3s ease-in;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: scale(0.8); }
        to { opacity: 1; transform: scale(1); }
    }

    /* Ensure turn markers stay above other content */
    .turn-marker {
        position: relative !important;
        z-index: 1000 !important;
    }

    /* Prevent turn markers from being covered */
    .message-container {
        position: relative;
        z-index: 1;
    }

    /* Inline markers for less intrusive display */
    .turn-marker-inline {
        transition: all 0.2s ease;
    }

    .turn-marker-inline:hover {
        background-color: rgba(255, 215, 0, 0.3) !important;
        transform: scale(1.05);
    }
    </style>
    """, unsafe_allow_html=True)


def test_turn_markers():
    """Test function to verify turn markers render correctly."""
    st.markdown("### Turn Marker Test")

    # Test different modes
    for mode in ["demo", "beta", "telos", "devops"]:
        col1, col2 = st.columns([1, 4])
        with col1:
            st.markdown(render_turn_marker(1, mode), unsafe_allow_html=True)
        with col2:
            st.markdown(f"This is a test message for {mode} mode")

    st.markdown("### Inline Turn Markers")
    st.markdown(
        f"This is a message {render_turn_marker_inline(1, 'beta')} with an inline marker"
        f" and another {render_turn_marker_inline(2, 'demo')} marker.",
        unsafe_allow_html=True
    )
"""
Tool Palette Panel
===================
Ranked tools with horizontal fidelity bars.
Selected tool highlighted, blocked tools shown in red.

Uses exact same glassmorphism card style as beta_onboarding.py.
"""
import streamlit as st
from telos_observatory.config.colors import get_fidelity_color, GOLD


def render_tool_palette(tool_rankings):
    """
    Render tool palette with fidelity bars.

    Args:
        tool_rankings: List of dicts with keys:
            tool_name (str), fidelity (float 0-1), display_pct (int 0-100),
            is_selected (bool), is_blocked (bool)
    """
    if not tool_rankings:
        return

    rows_html = ""
    for tool in tool_rankings:
        tool_name = tool.get("tool_name", "unknown")
        fidelity = tool.get("fidelity", 0.0)
        display_pct = tool.get("display_pct", int(fidelity * 100))
        is_selected = tool.get("is_selected", False)
        is_blocked = tool.get("is_blocked", False)

        # Determine bar color and border
        if is_blocked:
            bar_color = "#e74c3c"
            border_color = "#e74c3c"
            badge = '<span style="color: #e74c3c; font-size: 11px; font-weight: 600; margin-left: 8px; padding: 2px 6px; border: 1px solid #e74c3c; border-radius: 4px;">BLOCKED</span>'
        elif is_selected:
            bar_color = "#27ae60"
            border_color = "#27ae60"
            badge = '<span style="color: #27ae60; font-size: 11px; font-weight: 600; margin-left: 8px; padding: 2px 6px; border: 1px solid #27ae60; border-radius: 4px;">SELECTED</span>'
        else:
            bar_color = get_fidelity_color(fidelity)
            border_color = "#555555"
            badge = ""

        rows_html += f"""
        <div style="display: flex; align-items: center; margin-bottom: 8px; padding: 8px 12px; border: 1px solid {border_color}; border-radius: 6px; background: rgba(45, 45, 45, 0.6);">
            <div style="min-width: 140px; color: #e0e0e0; font-size: 14px; font-weight: 500;">
                {tool_name}{badge}
            </div>
            <div style="flex: 1; margin: 0 12px; height: 16px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden;">
                <div style="width: {display_pct}%; height: 100%; background: {bar_color}; border-radius: 4px; transition: width 0.3s ease;"></div>
            </div>
            <div style="min-width: 40px; text-align: right; color: {bar_color}; font-size: 14px; font-weight: 600;">
                {display_pct}%
            </div>
        </div>
        """

    # Glassmorphism card wrapper (exact same style as beta_onboarding.py cards)
    st.markdown(f"""
<div class="message-container" style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 1px solid #F4D03F; border-radius: 8px; padding: 20px; margin: 10px 0; box-shadow: 0 0 15px rgba(244, 208, 63, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
    <h3 style="color: #F4D03F; margin-top: 0;">Tool Palette</h3>
    {rows_html}
</div>
""", unsafe_allow_html=True)

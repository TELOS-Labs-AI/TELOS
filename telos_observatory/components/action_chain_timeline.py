"""
Action Chain Timeline
=====================
Visual timeline of action chain steps with SCI connections.
[Step 1] --SCI--> [Step 2] --SCI--> [Step 3]

Uses exact same glassmorphism card style as beta_onboarding.py.
"""
import streamlit as st
from telos_observatory.config.colors import get_fidelity_color, GOLD


def render_action_chain(steps):
    """
    Render action chain timeline.

    Args:
        steps: List of dicts with keys:
            step_number (int), tool_used (str), effective_fidelity (float 0-1),
            sci_score (float 0-1 or None for first step),
            chain_broken (bool)
    """
    if not steps:
        return

    # Build timeline HTML
    timeline_items = ""
    for idx, step in enumerate(steps):
        step_num = step.get("step_number", idx + 1)
        tool_used = step.get("tool_used", "---")
        eff_fidelity = step.get("effective_fidelity", 0.0)
        sci_score = step.get("sci_score")
        chain_broken = step.get("chain_broken", False)

        fid_color = get_fidelity_color(eff_fidelity)
        fid_pct = f"{int(eff_fidelity * 100)}%"

        # SCI arrow before step (skip for first step)
        if idx > 0:
            if chain_broken:
                arrow_color = "#e74c3c"
                sci_label = "BREAK"
                break_marker = '<span style="color: #e74c3c; font-size: 16px; font-weight: 700;">X</span>'
            else:
                sci_val = sci_score if sci_score is not None else 0.0
                arrow_color = "#27ae60" if sci_val >= 0.30 else "#e74c3c"
                sci_label = f"SCI {int(sci_val * 100)}%"
                break_marker = ""

            timeline_items += f"""
            <div style="display: flex; align-items: center; justify-content: center; margin: 4px 0;">
                <div style="width: 40px; height: 2px; background: {arrow_color};"></div>
                <span style="color: {arrow_color}; font-size: 11px; font-weight: 600; padding: 2px 8px; margin: 0 4px; border: 1px solid {arrow_color}; border-radius: 4px; background: rgba(0,0,0,0.3);">
                    {sci_label}
                </span>
                {break_marker}
                <div style="width: 40px; height: 2px; background: {arrow_color};"></div>
            </div>
            """

        # Step box
        timeline_items += f"""
        <div style="display: flex; align-items: center; justify-content: center;">
            <div style="border: 1px solid {fid_color}; border-radius: 8px; padding: 10px 16px; background: rgba(45, 45, 45, 0.6); text-align: center; min-width: 150px;">
                <p style="color: {GOLD}; font-size: 11px; margin: 0; font-weight: 600; text-transform: uppercase;">
                    Step {step_num}
                </p>
                <p style="color: #e0e0e0; font-size: 14px; margin: 4px 0 2px 0; font-weight: 500;">
                    {tool_used}
                </p>
                <p style="color: {fid_color}; font-size: 13px; margin: 0; font-weight: 600;">
                    {fid_pct}
                </p>
            </div>
        </div>
        """

    # Glassmorphism card wrapper (exact same style as beta_onboarding.py cards)
    st.markdown(f"""
<div class="message-container" style="background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 50%, transparent 100%), rgba(26, 26, 30, 0.45); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 1px solid #F4D03F; border-radius: 8px; padding: 20px; margin: 10px 0; box-shadow: 0 0 15px rgba(244, 208, 63, 0.15), 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.1);">
    <h3 style="color: #F4D03F; margin-top: 0;">Action Chain</h3>
    {timeline_items}
</div>
""", unsafe_allow_html=True)

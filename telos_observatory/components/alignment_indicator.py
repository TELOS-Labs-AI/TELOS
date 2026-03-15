"""
Alignment Indicator Component for TELOS Observatory V3.

A simple, compact visual indicator showing current alignment status.
Less decorative than Observatory Lens, focuses on quick visual read.

Design Philosophy:
- Minimal decoration
- Clear at-a-glance status
- Real data only (no synthetic visualizations)
- Color-coded zones matching CLAUDE.md thresholds
"""

import streamlit as st
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Zone thresholds matching CLAUDE.md
ZONE_THRESHOLDS = {
    'green': 0.70,   # ALIGNED
    'yellow': 0.60,  # MINOR DRIFT
    'orange': 0.50,  # DRIFT DETECTED
    # below 0.50: SIGNIFICANT DRIFT (red)
}

ZONE_COLORS = {
    'green': '#27ae60',
    'yellow': '#f39c12',
    'orange': '#e67e22',
    'red': '#e74c3c',
}

ZONE_LABELS = {
    'green': 'Aligned',
    'yellow': 'Minor Drift',
    'orange': 'Drift Detected',
    'red': 'Significant Drift',
}


def get_zone(fidelity: float) -> str:
    """Classify fidelity into a zone."""
    if fidelity >= ZONE_THRESHOLDS['green']:
        return 'green'
    elif fidelity >= ZONE_THRESHOLDS['yellow']:
        return 'yellow'
    elif fidelity >= ZONE_THRESHOLDS['orange']:
        return 'orange'
    else:
        return 'red'


class AlignmentIndicator:
    """
    Simple alignment status indicator.

    Shows:
    - Current fidelity score (large number)
    - Zone color indicator
    - Mini trend (last 3 turns)
    """

    def __init__(self, state_manager=None):
        """
        Initialize alignment indicator.

        Args:
            state_manager: StateManager instance for turn data
        """
        self.state_manager = state_manager

    def render(self, fidelity: Optional[float] = None, compact: bool = False):
        """
        Render the alignment indicator.

        Args:
            fidelity: Override fidelity value (if None, gets from state)
            compact: If True, render minimal version
        """
        # Get current fidelity
        if fidelity is None:
            fidelity = self._get_current_fidelity()

        zone = get_zone(fidelity)
        color = ZONE_COLORS[zone]
        label = ZONE_LABELS[zone]

        if compact:
            self._render_compact(fidelity, zone, color, label)
        else:
            self._render_full(fidelity, zone, color, label)

    def _get_current_fidelity(self) -> float:
        """Get current fidelity from state manager."""
        if not self.state_manager:
            return 0.5

        current_turn = self.state_manager.get_current_turn_data()
        if not current_turn:
            return 0.5

        return (
            current_turn.get('display_fidelity') or
            current_turn.get('user_fidelity') or
            current_turn.get('fidelity', 0.5)
        )

    def _get_trend_data(self) -> list:
        """Get fidelity values for last 3 turns."""
        if not self.state_manager:
            return []

        turns = self.state_manager.get_all_turns()
        if not turns:
            return []

        # Get last 3 turns
        recent = turns[-3:]
        return [
            t.get('display_fidelity') or t.get('user_fidelity') or t.get('fidelity', 0.5)
            for t in recent
        ]

    def _render_compact(self, fidelity: float, zone: str, color: str, label: str):
        """Render minimal version - just score and color dot."""
        st.markdown(f"""
        <div style="
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 4px 12px;
            background: #2d2d2d;
            border: 1px solid {color};
            border-radius: 16px;
        ">
            <span style="
                width: 10px;
                height: 10px;
                background: {color};
                border-radius: 50%;
            "></span>
            <span style="
                color: {color};
                font-weight: 600;
                font-size: 14px;
            ">{int(fidelity * 100)}%</span>
        </div>
        """, unsafe_allow_html=True)

    def _render_full(self, fidelity: float, zone: str, color: str, label: str):
        """Render full version with score, label, and trend."""
        trend = self._get_trend_data()
        trend_html = self._build_trend_html(trend)

        st.markdown(f"""
        <div style="
            background: #1a1a1a;
            border: 2px solid {color};
            border-radius: 12px;
            padding: 16px;
            text-align: center;
        ">
            <!-- Main Score -->
            <div style="
                font-size: 48px;
                font-weight: 700;
                color: {color};
                line-height: 1;
            ">{int(fidelity * 100)}%</div>

            <!-- Zone Label -->
            <div style="
                font-size: 14px;
                color: {color};
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-top: 8px;
            ">{label}</div>

            <!-- Trend Dots -->
            {trend_html}

            <!-- Zone Bar -->
            <div style="
                margin-top: 16px;
                height: 8px;
                background: linear-gradient(to right,
                    #e74c3c 0%, #e74c3c 25%,
                    #e67e22 25%, #e67e22 50%,
                    #f39c12 50%, #f39c12 75%,
                    #27ae60 75%, #27ae60 100%
                );
                border-radius: 4px;
                position: relative;
            ">
                <!-- Position marker -->
                <div style="
                    position: absolute;
                    left: {fidelity * 100}%;
                    top: -4px;
                    width: 4px;
                    height: 16px;
                    background: white;
                    border-radius: 2px;
                    transform: translateX(-50%);
                "></div>
            </div>

            <!-- Zone Labels -->
            <div style="
                display: flex;
                justify-content: space-between;
                margin-top: 4px;
                font-size: 10px;
                color: #666;
            ">
                <span>0%</span>
                <span>50%</span>
                <span>70%</span>
                <span>100%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    def _build_trend_html(self, trend: list) -> str:
        """Build HTML for trend dots."""
        if not trend or len(trend) < 2:
            return ""

        dots = []
        for f in trend:
            zone = get_zone(f)
            c = ZONE_COLORS[zone]
            dots.append(f'<span style="width:8px;height:8px;background:{c};border-radius:50%;display:inline-block;"></span>')

        # Add trend arrow
        if len(trend) >= 2:
            if trend[-1] > trend[-2] + 0.02:
                arrow = '<span style="color:#27ae60;margin-left:8px;">up</span>'
            elif trend[-1] < trend[-2] - 0.02:
                arrow = '<span style="color:#e74c3c;margin-left:8px;">down</span>'
            else:
                arrow = '<span style="color:#888;margin-left:8px;">--</span>'
        else:
            arrow = ""

        return f"""
        <div style="
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            margin-top: 12px;
        ">
            <span style="color:#666;font-size:10px;">Trend:</span>
            {' '.join(dots)}
            {arrow}
        </div>
        """


def render_alignment_indicator(
    state_manager=None,
    fidelity: Optional[float] = None,
    compact: bool = False
):
    """
    Convenience function to render alignment indicator.

    Args:
        state_manager: StateManager instance
        fidelity: Override fidelity value
        compact: Render minimal version
    """
    indicator = AlignmentIndicator(state_manager)
    indicator.render(fidelity=fidelity, compact=compact)


# Inline badge version for use in messages
def alignment_badge(fidelity: float) -> str:
    """
    Return HTML for inline alignment badge.

    Args:
        fidelity: Fidelity score

    Returns:
        HTML string for badge
    """
    zone = get_zone(fidelity)
    color = ZONE_COLORS[zone]

    return f"""<span style="
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 8px;
        background: #2d2d2d;
        border: 1px solid {color};
        border-radius: 12px;
        font-size: 12px;
    ">
        <span style="
            width: 6px;
            height: 6px;
            background: {color};
            border-radius: 50%;
        "></span>
        <span style="color: {color};">{int(fidelity * 100)}%</span>
    </span>"""

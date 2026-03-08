"""
TELOSCOPE Color Configuration
=============================

Centralized color definitions for consistency and accessibility.
Updated based on accessibility audit to reduce eye strain.
"""

# Primary Brand Colors
GOLD = '#F4D03F'  # Refined gold - less "neon", better for eyes
GOLD_BRIGHT = '#F4D03F'  # Legacy bright gold (deprecated - do not use)

# Status Colors (Fidelity Indicators) - Zone-based naming for user clarity
# Thresholds are internal implementation details, not user-facing
# Colors updated per UI/UX audit - #27ae60 is canonical green across all zones
STATUS_GOOD = '#27ae60'     # Green - "Aligned" zone (canonical TELOS green)
STATUS_MILD = '#F4D03F'      # Yellow - "Minor Drift" zone (bright gold-yellow, distinct from orange)
STATUS_MODERATE = '#e67e22'  # Orange - "Drift Detected" zone
STATUS_SEVERE = '#e74c3c'    # Red - "Significant Drift" zone

# Background Colors
BG_BASE = '#0d0d0d'        # Darkest - base layer
BG_SURFACE = '#1a1a1a'     # Primary surface
BG_ELEVATED = '#2d2d2d'    # Elevated/card surface
BG_OVERLAY = '#3a3a3a'     # Modal/overlay surface

# Text Colors
TEXT_PRIMARY = '#e0e0e0'    # Primary text
TEXT_SECONDARY = '#b0b0b0'  # Secondary text
TEXT_MUTED = '#808080'      # Muted/disabled text

# Opacity Variations (for visual hierarchy)
def with_opacity(color: str, opacity: float) -> str:
    """Add opacity to a hex color."""
    # Convert hex to RGB
    hex_color = color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f'rgba({r}, {g}, {b}, {opacity})'

# Gold variations for hierarchy
GOLD_100 = GOLD                           # Headers
GOLD_80 = with_opacity(GOLD, 0.8)        # Borders
GOLD_60 = with_opacity(GOLD, 0.6)        # Accents
GOLD_40 = with_opacity(GOLD, 0.4)        # Subtle hints

# Legacy mappings (for backward compatibility during migration)
COLOR_MAPPINGS = {
    '#F4D03F': GOLD,      # Map old bright gold to refined gold
    '#FF4444': STATUS_SEVERE,  # Map old red to improved red
    '#FFA500': STATUS_MODERATE,  # Map old orange to refined orange
}

# =============================================================================
# Zone Thresholds - IMPORTED FROM SINGLE SOURCE OF TRUTH
# =============================================================================
# All thresholds are defined in telos_core/constants.py
# This file re-exports them for backward compatibility with existing imports.
from telos_core.constants import (
    FIDELITY_GREEN,
    FIDELITY_YELLOW,
    FIDELITY_ORANGE,
    FIDELITY_RED,
)

# Zone aliases for this module's API (backward compatibility)
_ZONE_ALIGNED = FIDELITY_GREEN       # 0.70 - "Aligned" zone threshold
_ZONE_MINOR_DRIFT = FIDELITY_YELLOW  # 0.60 - "Minor Drift" zone threshold
_ZONE_DRIFT = FIDELITY_ORANGE        # 0.50 - "Drift Detected" zone threshold
# Below _ZONE_DRIFT = "Significant Drift" zone (FIDELITY_RED)


def _normalize_score(score) -> float:
    """Convert score to float, handling string percentages like '100%'.

    Args:
        score: Float (0.75), int (75), string ('75%', '0.75'), or numpy scalar

    Returns:
        Float in 0.0-1.0 range
    """
    if score is None:
        return 0.0
    if isinstance(score, str):
        # Handle percentage strings like "100%", "75%"
        score = score.strip()
        if score.endswith('%'):
            try:
                return float(score[:-1]) / 100.0
            except ValueError:
                return 0.0
        # Handle decimal strings like "0.75"
        try:
            val = float(score)
            # If it's > 1, assume it's a percentage
            if val > 1.0:
                return val / 100.0
            return val
        except ValueError:
            return 0.0
    # Handle any numeric type (int, float, numpy scalars like np.float64)
    # Using try/except with float() is more robust than isinstance() checks
    # because isinstance(np.float64(0.65), (int, float)) returns False
    try:
        val = float(score)
        # If it's > 1, assume it's a percentage (e.g., 75 instead of 0.75)
        if val > 1.0:
            return val / 100.0
        return val
    except (TypeError, ValueError):
        return 0.0


def get_fidelity_color(score) -> str:
    """Get the appropriate color for a fidelity score.

    Uses Goldilocks zone thresholds derived from mathematical optimization.

    Args:
        score: Float (0.75), int, or string ('75%') - automatically normalized
    """
    score = _normalize_score(score)
    if score >= _ZONE_ALIGNED:
        return STATUS_GOOD
    elif score >= _ZONE_MINOR_DRIFT:
        return STATUS_MILD
    elif score >= _ZONE_DRIFT:
        return STATUS_MODERATE
    else:
        return STATUS_SEVERE


def get_color_name(score) -> str:
    """Get the color name for a fidelity score.

    Uses Goldilocks zone thresholds derived from mathematical optimization.

    Args:
        score: Float (0.75), int, or string ('75%') - automatically normalized
    """
    score = _normalize_score(score)
    if score >= _ZONE_ALIGNED:
        return "green"
    elif score >= _ZONE_MINOR_DRIFT:
        return "gold"
    elif score >= _ZONE_DRIFT:
        return "orange"
    else:
        return "red"


def get_zone_name(score) -> str:
    """Get the human-friendly zone name for a fidelity score.

    Returns semantic zone names instead of threshold numbers for better UX.

    Args:
        score: Float (0.75), int, or string ('75%') - automatically normalized
    """
    score = _normalize_score(score)
    if score >= _ZONE_ALIGNED:
        return "Aligned"
    elif score >= _ZONE_MINOR_DRIFT:
        return "Minor Drift"
    elif score >= _ZONE_DRIFT:
        return "Drift Detected"
    else:
        return "Significant Drift"


def format_fidelity_percent(score) -> str:
    """Format fidelity as percentage (e.g., '75%').

    More intuitive for users than raw decimals (0.75).

    Args:
        score: Float (0.75), int, or string ('75%') - automatically normalized
    """
    if score is None:
        return "---"
    score = _normalize_score(score)
    return f"{int(score * 100)}%"


def get_letter_grade(score) -> str:
    """Get letter grade for fidelity score.

    A+ = 95-100% (0.95-1.00)
    A  = 90-94%  (0.90-0.94)
    A- = 85-89%  (0.85-0.89)
    B+ = 80-84%  (0.80-0.84)
    B  = 75-79%  (0.75-0.79)
    B- = 70-74%  (0.70-0.74) - Aligned threshold
    C+ = 65-69%  (0.65-0.69)
    C  = 60-64%  (0.60-0.64) - Minor drift threshold
    C- = 55-59%  (0.55-0.59)
    D  = 50-54%  (0.50-0.54) - Drift detected threshold
    F  = <50%    (<0.50)     - Significant drift

    Args:
        score: Float (0.75), int, or string ('75%') - automatically normalized
    """
    if score is None:
        return "---"
    score = _normalize_score(score)
    if score >= 0.95:
        return "A+"
    elif score >= 0.90:
        return "A"
    elif score >= 0.85:
        return "A-"
    elif score >= 0.80:
        return "B+"
    elif score >= 0.75:
        return "B"
    elif score >= 0.70:
        return "B-"
    elif score >= 0.65:
        return "C+"
    elif score >= 0.60:
        return "C"
    elif score >= 0.55:
        return "C-"
    elif score >= 0.50:
        return "D"
    else:
        return "F"


def format_fidelity_display(score: float) -> str:
    """Format fidelity for display with percentage and grade.

    Example: "75% (B)" - more intuitive than "0.75"
    """
    if score is None:
        return "---"
    pct = format_fidelity_percent(score)
    grade = get_letter_grade(score)
    return f"{pct} ({grade})"


# Zone legend HTML for displaying in UI
ZONE_LEGEND_HTML = """
<div style="display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; padding: 8px; background: rgba(26, 26, 30, 0.7); border-radius: 8px; margin: 8px 0;">
    <span style="color: #27ae60; font-size: 12px;">● Aligned (70%+)</span>
    <span style="color: #f39c12; font-size: 12px;">● Minor Drift (60-69%)</span>
    <span style="color: #e67e22; font-size: 12px;">● Drift (50-59%)</span>
    <span style="color: #e74c3c; font-size: 12px;">● Severe (&lt;50%)</span>
</div>
"""
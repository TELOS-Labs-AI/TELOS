"""
Steward Granular Response Styling (PROPRIETARY)
================================================

This module defines the continuous gradient of Steward response styles
for the INTERVENTION ZONE ONLY (fidelity < GREEN threshold).

DESIGN PHILOSOPHY:
------------------
- Steward only appears when intervention is triggered (< GREEN threshold)
- GREEN zone = TELOS native flow (Steward is INVISIBLE)
- Below GREEN = Steward takes over with graduated intensity

FIDELITY GRADIENT (Intervention Zone Only):
-------------------------------------------
The gradient below GREEN threshold determines Steward's intensity:

    Band 6: 0.60-0.70 (Threshold) - Soft nudge
    Band 5: 0.50-0.60 (Drifting) - Clear inquiry
    Band 4: 0.40-0.50 (Concerning) - Direct check-in
    Band 3: 0.30-0.40 (Problematic) - Firm redirection
    Band 2: 0.20-0.30 (Critical) - Strong intervention
    Band 1: <0.20 (Collapsed) - Full governance mode

NOTE: These are Mistral thresholds. For SentenceTransformer, use:
    GREEN = 0.30 (so Steward appears at < 0.30)

Each band has:
- Tone descriptor (how Steward sounds)
- Directness level (0.0-1.0)
- Urgency level (0.0-1.0)
- Response openers (example phrases)
- Prompt injection template

Usage:
    from telos_observatory.config.steward_styles import get_steward_style, get_intervention_prompt

    # Only call when fidelity < GREEN (intervention triggered)
    style = get_steward_style(fidelity=0.58, green_threshold=0.70)
    prompt = get_intervention_prompt(fidelity=0.58, user_context="debugging code")
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple


# =============================================================================
# STEWARD STYLE DATA CLASS
# =============================================================================

@dataclass
class StewardStyle:
    """
    Encapsulates Steward's response characteristics at a specific fidelity level.

    Attributes:
        band: Numeric band (1-6, higher = closer to GREEN)
        band_name: Human-readable band name
        fidelity_pct: Percentage position within intervention range (0-100)
        tone: Descriptive tone (e.g., "warm and curious", "direct and grounded")
        directness: How direct Steward is (0.0 = subtle, 1.0 = explicit)
        urgency: How urgent the intervention feels (0.0 = relaxed, 1.0 = pressing)
        openers: Example response openers for this band
        style_notes: Guidance for response generation
    """
    band: int
    band_name: str
    fidelity_pct: float  # 0-100, where 100 = at GREEN threshold, 0 = at zero
    tone: str
    directness: float
    urgency: float
    openers: List[str]
    style_notes: str

    def to_dict(self) -> dict:
        """Convert to dictionary for telemetry/logging."""
        return {
            'band': self.band,
            'band_name': self.band_name,
            'fidelity_pct': self.fidelity_pct,
            'tone': self.tone,
            'directness': self.directness,
            'urgency': self.urgency,
            'style_notes': self.style_notes
        }


# =============================================================================
# GRANULAR STYLE DEFINITIONS (6 BANDS - Intervention Zone Only)
# =============================================================================
# These represent PERCENTAGE of the way from 0 to GREEN threshold
# Band 6 = 85-100% (closest to GREEN, lightest touch)
# Band 1 = 0-15% (closest to zero, strongest intervention)

STEWARD_STYLES = {
    # -------------------------------------------------------------------------
    # BAND 6: THRESHOLD (85-100% of GREEN)
    # Just crossed into intervention zone - NATURAL Steward (light presence)
    # -------------------------------------------------------------------------
    # The Steward is present but integrated naturally into the response.
    # NO robotic preambles ("Before we go further..."), but DO weave in
    # purpose awareness conversationally.
    6: StewardStyle(
        band=6,
        band_name="Threshold",
        fidelity_pct=92.5,  # Midpoint of 85-100%
        tone="natural and present",
        directness=0.15,  # Light presence - not invisible, but not pushy
        urgency=0.05,     # Very low urgency - nearly GREEN
        openers=[
            # Natural conversation continuers - no steering language
            # These should feel like natural topic connections, not redirects
        ],
        style_notes=(
            "Near-GREEN queries - respond NATURALLY with light purpose-awareness. "
            "Answer the question directly, then briefly connect it to their purpose if relevant. "
            "NO robotic phrases like 'can we step back' or 'before we go further'. "
            "Think: helpful assistant who remembers what the user is working on."
        )
    ),

    # -------------------------------------------------------------------------
    # BAND 5: DRIFTING (65-85% of GREEN)
    # Noticeable drift - Steward more present
    # -------------------------------------------------------------------------
    5: StewardStyle(
        band=5,
        band_name="Drifting",
        fidelity_pct=75.0,  # Midpoint of 65-85%
        tone="direct but warm",
        directness=0.35,
        urgency=0.25,
        openers=[
            "This seems like a different direction from what we started with.",
            "How does this connect to what you're trying to accomplish?",
            "Want to make sure we're using your time well here.",
            "Should we get back to your main question?",
        ],
        style_notes="Clear Steward presence. Openly naming potential drift. Inviting user to confirm or redirect."
    ),

    # -------------------------------------------------------------------------
    # BAND 4: CONCERNING (45-65% of GREEN)
    # Clear drift - Steward engaged
    # -------------------------------------------------------------------------
    4: StewardStyle(
        band=4,
        band_name="Concerning",
        fidelity_pct=55.0,  # Midpoint of 45-65%
        tone="grounded and direct",
        directness=0.55,
        urgency=0.45,
        openers=[
            "Hey, quick check -",
            "This is pretty different from what you said you wanted to focus on.",
            "Hold on a sec.",
            "This seems off-topic from your original goal.",
        ],
        style_notes="Steward clearly active. Direct but not harsh. Naming concerns explicitly. Offering clear choices."
    ),

    # -------------------------------------------------------------------------
    # BAND 3: PROBLEMATIC (25-45% of GREEN)
    # Strong drift - firm Steward governance
    # -------------------------------------------------------------------------
    3: StewardStyle(
        band=3,
        band_name="Problematic",
        fidelity_pct=35.0,  # Midpoint of 25-45%
        tone="firm but caring",
        directness=0.75,
        urgency=0.65,
        openers=[
            "This is way off from what we started with.",
            "That's a completely different topic.",
            "This doesn't fit with what you said you wanted.",
            "We're pretty far from your original focus here.",
        ],
        style_notes="Strong Steward intervention. Firm tone without being punitive. Clear redirection with care."
    ),

    # -------------------------------------------------------------------------
    # BAND 2: CRITICAL (10-25% of GREEN)
    # Severe drift - Steward in full control
    # -------------------------------------------------------------------------
    2: StewardStyle(
        band=2,
        band_name="Critical",
        fidelity_pct=17.5,  # Midpoint of 10-25%
        tone="serious and protective",
        directness=0.9,
        urgency=0.85,
        openers=[
            "OK, full stop.",
            "This isn't working. Let's reset.",
            "We're nowhere near what you originally wanted to do.",
            "This is really far from your stated goal.",
        ],
        style_notes="Full Steward governance. Serious but not cold. Protective of user's time and purpose."
    ),

    # -------------------------------------------------------------------------
    # BAND 1: COLLAPSED (<10% of GREEN)
    # Complete breakdown - full Steward takeover
    # -------------------------------------------------------------------------
    1: StewardStyle(
        band=1,
        band_name="Collapsed",
        fidelity_pct=5.0,  # Representative of 0-10%
        tone="protective and resolute",
        directness=1.0,
        urgency=1.0,
        openers=[
            "Let's start fresh.",
            "This has gone completely off track. Want to reset?",
            "This has nothing to do with what you came here for.",
            "Time to get back to what you actually wanted.",
        ],
        style_notes="Complete Steward takeover. Not punitive but resolute. Full reset with clear path back to purpose."
    ),
}


# =============================================================================
# PROMPT INJECTION TEMPLATES
# =============================================================================

def _get_base_steward_prompt() -> str:
    """Base Steward identity prompt - consistent across all intervention levels."""
    return """You are responding as the Steward - a therapeutic guide whose role is to
maintain alignment between the user's stated purpose and the conversation's direction.

Your core principles:
- Validate before advising
- Ask before assuming
- Offer, don't prescribe
- Partner, don't direct
- Empower, don't rescue

You are warm, grounded, and genuinely helpful. You are never punitive or condescending."""


INTERVENTION_PROMPT_TEMPLATES = {
    # Band 6: Natural with purpose-awareness
    6: """{base_prompt}

Current response style: NATURAL WITH PURPOSE-AWARENESS
- Answer the user's question DIRECTLY first
- Weave in a brief, natural connection to their purpose if relevant
- NO steering language or robotic preambles
- NO phrases like "before we go further" or "let's step back"
- Sound like a helpful assistant who remembers what they're working on
- Directness level: Very Low (light presence, not invisible)
- User's purpose: {user_context}""",

    # Band 5: Clear inquiry
    5: """{base_prompt}

Current response style: CLEAR INQUIRY
- Name the potential drift you're observing
- Invite user to confirm or redirect
- Be direct but warm
- Offer clear choice: continue this direction or refocus
- Directness level: Moderate
- User's purpose: {user_context}""",

    # Band 4: Direct check-in
    4: """{base_prompt}

Current response style: DIRECT CHECK-IN
- Clearly name the concern
- Be direct about the drift from purpose
- Offer specific options for moving forward
- Show you care about their time and goals
- Directness level: High
- User's purpose: {user_context}""",

    # Band 3: Firm redirection
    3: """{base_prompt}

Current response style: FIRM REDIRECTION
- State clearly that you're redirecting the conversation
- Explain why (drift from purpose)
- Provide clear path back to their goal
- Firm but caring - never punitive
- Directness level: Very High
- User's purpose: {user_context}""",

    # Band 2: Strong intervention
    2: """{base_prompt}

Current response style: STRONG INTERVENTION
- Stop the current direction
- Name the significant drift
- Offer a reset point
- Serious tone but still warm
- Protective of user's purpose
- User's purpose: {user_context}""",

    # Band 1: Full governance
    1: """{base_prompt}

Current response style: FULL GOVERNANCE
- Take control of the conversation direction
- Acknowledge we've gone off track
- Provide clear reset to original purpose
- Resolute but not harsh
- Lead user back to their stated goal
- User's purpose: {user_context}""",
}


# =============================================================================
# STYLE LOOKUP FUNCTIONS
# =============================================================================

def get_band_for_fidelity(fidelity: float, green_threshold: float = 0.70) -> int:
    """
    Get the band number (1-6) for a given fidelity score.

    Args:
        fidelity: Fidelity score (should be < green_threshold for intervention)
        green_threshold: The GREEN threshold (0.70 for Mistral, 0.30 for ST)

    Returns:
        Band number (1 = worst, 6 = closest to GREEN)
    """
    if fidelity >= green_threshold:
        return 6  # At threshold - minimal intervention (shouldn't happen if called correctly)

    # Calculate percentage of way from 0 to GREEN
    pct = (fidelity / green_threshold) * 100 if green_threshold > 0 else 0

    if pct >= 85:
        return 6
    elif pct >= 65:
        return 5
    elif pct >= 45:
        return 4
    elif pct >= 25:
        return 3
    elif pct >= 10:
        return 2
    else:
        return 1


def get_steward_style(fidelity: float, green_threshold: float = 0.70) -> StewardStyle:
    """
    Get the Steward style for a given fidelity score.

    Args:
        fidelity: Fidelity score (should be < green_threshold for intervention)
        green_threshold: The GREEN threshold for the embedding model

    Returns:
        StewardStyle object with all style parameters

    Example:
        >>> style = get_steward_style(0.45, green_threshold=0.70)
        >>> print(f"Band: {style.band_name}, Tone: {style.tone}")
        Band: Concerning, Tone: grounded and direct
    """
    band = get_band_for_fidelity(fidelity, green_threshold)
    return STEWARD_STYLES[band]


def get_intervention_prompt(
    fidelity: float,
    user_context: Optional[str] = None,
    green_threshold: float = 0.70
) -> str:
    """
    Get the intervention prompt for a given fidelity score.

    Args:
        fidelity: Fidelity score (should be < green_threshold for intervention)
        user_context: Description of user's purpose (for context injection)
        green_threshold: The GREEN threshold for the embedding model

    Returns:
        Formatted intervention prompt

    Example:
        >>> prompt = get_intervention_prompt(0.42, "debugging authentication issues")
        >>> # Returns Band 4 (Concerning) prompt with user context
    """
    band = get_band_for_fidelity(fidelity, green_threshold)
    template = INTERVENTION_PROMPT_TEMPLATES[band]

    base_prompt = _get_base_steward_prompt()
    context = user_context or "Not specified"

    return template.format(base_prompt=base_prompt, user_context=context)


def get_style_interpolation(fidelity: float, green_threshold: float = 0.70) -> dict:
    """
    Get interpolated style parameters for precise fidelity values.

    This allows for truly continuous styling where 0.48 feels different
    from 0.52. Returns interpolated values within bands.

    Args:
        fidelity: Fidelity score (should be < green_threshold)
        green_threshold: The GREEN threshold for the embedding model

    Returns:
        dict with interpolated directness, urgency values

    Example:
        >>> params = get_style_interpolation(0.48, green_threshold=0.70)
        >>> print(f"Directness: {params['directness']:.2f}")
        Directness: 0.52
    """
    band = get_band_for_fidelity(fidelity, green_threshold)
    style = STEWARD_STYLES[band]

    # Calculate percentage position within intervention range
    pct = (fidelity / green_threshold) * 100 if green_threshold > 0 else 0

    # Get adjacent bands for interpolation
    if band < 6:
        next_style = STEWARD_STYLES[band + 1]
    else:
        next_style = style

    if band > 1:
        prev_style = STEWARD_STYLES[band - 1]
    else:
        prev_style = style

    # Band boundaries (percentage-based)
    band_boundaries = {
        6: (85, 100),
        5: (65, 85),
        4: (45, 65),
        3: (25, 45),
        2: (10, 25),
        1: (0, 10),
    }

    band_min, band_max = band_boundaries[band]

    # Calculate position within band (0.0 = at min, 1.0 = at max)
    if band_max > band_min:
        band_position = (pct - band_min) / (band_max - band_min)
    else:
        band_position = 0.5

    band_position = max(0.0, min(1.0, band_position))

    # Interpolate (higher position = closer to next band = less intervention)
    interpolated_directness = style.directness - (band_position * (style.directness - next_style.directness))
    interpolated_urgency = style.urgency - (band_position * (style.urgency - next_style.urgency))

    return {
        'fidelity': fidelity,
        'fidelity_pct': pct,
        'band': band,
        'band_name': style.band_name,
        'band_position': band_position,
        'directness': interpolated_directness,
        'urgency': interpolated_urgency,
        'tone': style.tone,
        'openers': style.openers,
    }


def get_response_opener(fidelity: float, green_threshold: float = 0.70) -> str:
    """
    Get a contextually appropriate response opener for the fidelity level.

    Args:
        fidelity: Fidelity score (should be < green_threshold)
        green_threshold: The GREEN threshold for the embedding model

    Returns:
        Suggested opener string
    """
    style = get_steward_style(fidelity, green_threshold)
    params = get_style_interpolation(fidelity, green_threshold)

    # Select opener based on position within band
    # Handle empty openers list (e.g., Band 6 which has no openers)
    if not style.openers:
        return ""  # No opener for near-GREEN responses

    index = int(params['band_position'] * len(style.openers))
    index = min(index, len(style.openers) - 1)
    index = max(index, 0)  # Ensure non-negative

    return style.openers[index]


# =============================================================================
# DIAGNOSTIC FUNCTIONS
# =============================================================================

def describe_fidelity_experience(fidelity: float, green_threshold: float = 0.70) -> str:
    """
    Get a human-readable description of Steward's presence at this fidelity.

    Args:
        fidelity: Fidelity score
        green_threshold: The GREEN threshold for the embedding model

    Returns:
        Narrative description of Steward presence
    """
    if fidelity >= green_threshold:
        return f"TELOS native flow. No Steward intervention. (Fidelity: {fidelity:.2f})"

    style = get_steward_style(fidelity, green_threshold)
    params = get_style_interpolation(fidelity, green_threshold)

    return f"Steward {style.band_name}. {style.tone.capitalize()} tone. Directness: {params['directness']:.0%}. (Fidelity: {fidelity:.2f})"


def print_style_gradient(green_threshold: float = 0.70):
    """Print the style gradient for visualization."""
    print("=" * 70)
    print(f"STEWARD RESPONSE STYLE GRADIENT (GREEN threshold: {green_threshold})")
    print("=" * 70)
    print(f"{'Band':<6} {'Name':<12} {'% of GREEN':<12} {'Tone':<25} {'Dir':<6} {'Urg':<6}")
    print("-" * 70)

    for band in range(6, 0, -1):
        style = STEWARD_STYLES[band]
        print(f"{band:<6} {style.band_name:<12} {style.fidelity_pct:.0f}%         {style.tone:<25} {style.directness:<6.2f} {style.urgency:<6.2f}")

    print("=" * 70)


# =============================================================================
# CONVENIENCE EXPORT
# =============================================================================

__all__ = [
    'StewardStyle',
    'STEWARD_STYLES',
    'get_band_for_fidelity',
    'get_steward_style',
    'get_intervention_prompt',
    'get_style_interpolation',
    'get_response_opener',
    'describe_fidelity_experience',
    'print_style_gradient',
]

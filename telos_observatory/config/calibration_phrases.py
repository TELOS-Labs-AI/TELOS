"""
Calibration Phrases for TELOS Observatory
==========================================

Rotating phrases shown during PA derivation from user's first message.
Distinct from "Contemplating..." which is used during LLM response generation.

These phrases indicate the mathematical process of:
1. Extracting purpose from user input
2. Deriving AI PA via dual attractor
3. Computing embeddings
4. Establishing purpose lock
"""

import random

# Calibrating Attractor phrases - shown during PA derivation
CALIBRATING_PHRASES = [
    "Calibrating Attractor...",
    "Establishing Purpose Lock...",
    "Deriving Dual Attractor...",
    "Aligning Semantic Vectors...",
    "Computing Purpose Embeddings...",
    "Locking Purpose Coordinates...",
    "Initializing Governance Basin...",
    "Mapping Intent Space...",
    "Coupling Attractor Manifolds...",
    "Synthesizing Purpose Field...",
]

# Contemplating phrases - shown during normal LLM response generation
CONTEMPLATING_PHRASES = [
    "Contemplating...",
    "Thinking...",
    "Considering...",
    "Reflecting...",
    "Processing...",
    "Formulating...",
    "Reasoning...",
    "Analyzing...",
]


def get_calibrating_phrase() -> str:
    """Get a random calibrating phrase for PA derivation."""
    return random.choice(CALIBRATING_PHRASES)


def get_contemplating_phrase() -> str:
    """Get a random contemplating phrase for LLM response generation."""
    return random.choice(CONTEMPLATING_PHRASES)


def get_calibrating_html(phrase: str = None) -> str:
    """
    Generate HTML for calibrating attractor visual.

    Args:
        phrase: Optional specific phrase. If None, picks randomly.

    Returns:
        HTML string with animated calibrating indicator
    """
    if phrase is None:
        phrase = get_calibrating_phrase()

    return f"""
    <div style="
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px 20px;
        background: linear-gradient(135deg, rgba(244, 208, 63, 0.15) 0%, rgba(30, 30, 30, 0.9) 100%);
        border: 1px solid rgba(244, 208, 63, 0.4);
        border-radius: 12px;
        margin: 10px 0;
    ">
        <div style="
            width: 24px;
            height: 24px;
            border: 3px solid rgba(244, 208, 63, 0.3);
            border-top: 3px solid #F4D03F;
            border-radius: 50%;
            animation: calibrate-spin 1s linear infinite;
        "></div>
        <div style="
            color: #F4D03F;
            font-size: 18px;
            font-weight: 500;
            animation: calibrate-pulse 1.5s ease-in-out infinite;
        ">
            {phrase}
        </div>
    </div>
    <style>
        @keyframes calibrate-spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        @keyframes calibrate-pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.6; }}
        }}
    </style>
    """


def get_contemplating_html(phrase: str = None) -> str:
    """
    Generate HTML for contemplating visual (standard response generation).

    Args:
        phrase: Optional specific phrase. If None, picks randomly.

    Returns:
        HTML string with animated contemplating indicator
    """
    if phrase is None:
        phrase = get_contemplating_phrase()

    return f"""
    <div style="
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 16px;
        color: #aaa;
        font-style: italic;
    ">
        <div style="
            display: flex;
            gap: 4px;
        ">
            <span style="animation: dot-pulse 1.4s ease-in-out infinite;">.</span>
            <span style="animation: dot-pulse 1.4s ease-in-out 0.2s infinite;">.</span>
            <span style="animation: dot-pulse 1.4s ease-in-out 0.4s infinite;">.</span>
        </div>
        <span>{phrase}</span>
    </div>
    <style>
        @keyframes dot-pulse {{
            0%, 80%, 100% {{ opacity: 0.3; }}
            40% {{ opacity: 1; }}
        }}
    </style>
    """

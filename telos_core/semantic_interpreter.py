"""
Semantic Interpreter - Bridge between Mathematical Governance and Linguistic Output

This module translates fidelity metrics into concrete linguistic specifications.
It is the intermediary layer that uses two focal points:
  1. Fidelity Value - where we are on the alignment spectrum
  2. Purpose - what we're maintaining (the semantic anchor)

The interpreter maps mathematical drift measurements to specific linguistic features
that scale proportionally to produce the corrective force needed to restore primacy state.

NO abstract tone words ("be warm", "be direct").
ONLY concrete linguistic specifications that an LLM can execute deterministically.
"""

from dataclasses import dataclass
from typing import Optional
import logging

# Setup logger
logger = logging.getLogger(__name__)

# Proportional controller gain (from proportional_controller.py)
K_ATTRACTOR = 1.5


@dataclass
class SemanticSpec:
    """
    Concrete linguistic specification for redirect responses.

    These are measurable, executable features - not abstract tone guidance.
    Each feature is deterministic: the LLM knows exactly what to produce.
    """
    # Sentence structure
    sentence_form: str          # "questions", "soft statements", "direct statements", "directives"

    # Hedging level
    hedging: str                # "heavy" (might, perhaps, could), "light" (maybe), "none"
    hedging_words: list         # Specific words to use/avoid

    # Options to offer
    options_count: int          # How many paths to offer (1-3)
    options_style: str          # "invitations", "suggestions", "single path"

    # Drift acknowledgment
    drift_acknowledgment: str   # "implicit", "brief", "explicit", "named"

    # Shift mention (offer to change purpose)
    include_shift_mention: bool
    shift_urgency: str          # "casual", "available", "prominent"

    # Purpose reference
    purpose_reference: str      # How to reference the purpose

    # Calculated values (for transparency/logging)
    fidelity: float
    strength: float

    def to_prompt_block(self, purpose: str) -> str:
        """
        Convert this spec into a compact prompt block.
        No redundancy - each instruction appears once.
        """
        # Compact hedging
        hedge = f"Hedge: {', '.join(self.hedging_words)}" if self.hedging_words else "No hedging"

        # Compact options
        opts = f"{self.options_count} {self.options_style}" if self.options_count > 1 else self.options_style

        # Compact drift handling
        drift_map = {
            "implicit": "Acknowledge interest, don't name drift",
            "brief": "Brief tangent note",
            "explicit": "Name the drift",
            "named": "State clearly: far from purpose"
        }
        drift = drift_map.get(self.drift_acknowledgment, "")

        # Compact shift
        shift = "Mention shift option" if self.include_shift_mention else ""

        # Build minimal spec block
        instructions = [
            f"Form: {self.sentence_form}",
            hedge,
            f"Options: {opts}",
            f"Drift: {drift}",
        ]
        if shift:
            instructions.append(shift)

        return "\n".join(instructions)


def interpret(fidelity: float, purpose: str) -> SemanticSpec:
    """
    The Interpreter Algorithm.

    Takes fidelity value and purpose, returns concrete linguistic specifications
    scaled proportionally to restore primacy state.

    Args:
        fidelity: Current alignment score (0.0 to 1.0)
        purpose: User's stated purpose (semantic anchor)

    Returns:
        SemanticSpec with all linguistic features defined
    """
    # Calculate intervention strength using proportional controller formula
    error_signal = 1.0 - fidelity
    strength = min(K_ATTRACTOR * error_signal, 1.0)

    # Map strength to linguistic features
    # The boundaries are calibrated to the proportional controller output

    if strength < 0.45:
        # MINIMAL CORRECTION (fidelity ~0.70+, just at threshold)
        return SemanticSpec(
            sentence_form="questions and invitations",
            hedging="heavy",
            hedging_words=["might", "perhaps", "could", "wondering if"],
            options_count=2,
            options_style="invitations to explore",
            drift_acknowledgment="implicit",
            include_shift_mention=False,
            shift_urgency="",
            purpose_reference="Since you mentioned wanting to {purpose}...",
            fidelity=fidelity,
            strength=strength
        )

    elif strength < 0.60:
        # LIGHT CORRECTION (fidelity ~0.60-0.70, YELLOW zone)
        return SemanticSpec(
            sentence_form="soft statements with question endings",
            hedging="light",
            hedging_words=["maybe", "possibly"],
            options_count=2,
            options_style="suggestions",
            drift_acknowledgment="brief",
            include_shift_mention=True,
            shift_urgency="casual",
            purpose_reference="Your goal was to {purpose} - ",
            fidelity=fidelity,
            strength=strength
        )

    elif strength < 0.75:
        # MODERATE CORRECTION (fidelity ~0.50-0.60, ORANGE zone)
        return SemanticSpec(
            sentence_form="direct statements",
            hedging="none",
            hedging_words=[],
            options_count=1,
            options_style="clear suggestion",
            drift_acknowledgment="explicit",
            include_shift_mention=True,
            shift_urgency="available",
            purpose_reference="You came here to {purpose}. ",
            fidelity=fidelity,
            strength=strength
        )

    elif strength < 0.85:
        # FIRM CORRECTION (fidelity ~0.40-0.50, approaching RED)
        return SemanticSpec(
            sentence_form="directives",
            hedging="none",
            hedging_words=[],
            options_count=1,
            options_style="single path back",
            drift_acknowledgment="named",
            include_shift_mention=True,
            shift_urgency="available",
            purpose_reference="Your stated purpose: {purpose}. ",
            fidelity=fidelity,
            strength=strength
        )

    else:
        # STRONG CORRECTION (fidelity < 0.40, deep RED)
        return SemanticSpec(
            sentence_form="clear directives with anchoring statement",
            hedging="none",
            hedging_words=[],
            options_count=1,
            options_style="the path back",
            drift_acknowledgment="named",
            include_shift_mention=True,
            shift_urgency="prominent",
            purpose_reference="This is far from your purpose: {purpose}. ",
            fidelity=fidelity,
            strength=strength
        )


# =============================================================================
# EXEMPLAR CORPUS - Internal RAG for Organic Responses
# =============================================================================

EXEMPLAR_CORPUS = {
    # =========================================================================
    # MINIMAL CORRECTION (strength < 0.45, fidelity ~0.70+)
    # Characteristics: Questions, heavy hedging, implicit acknowledgment
    # =========================================================================
    "minimal": [
        "That's an interesting angle - I'm wondering if we might explore how that connects to {purpose}?",
        "Curious thought! Perhaps there's a way to bridge that with what you mentioned wanting to focus on?",
        "That could be worth exploring. I'm thinking it might connect back to {purpose} in an interesting way?",
        "Interesting direction. Could we maybe look at how that relates to what you came here for?",
        "I'm curious about that. Perhaps we could see how it ties into {purpose}?",
        "That's a fascinating point. I wonder if there might be a connection to what you're working on?",
        "Intriguing! Could there perhaps be an angle that relates this to {purpose}?",
        "That's worth considering. I'm wondering if we might find a link to your original focus?",
        "Interesting thought. Perhaps we could explore whether this connects to {purpose}?",
        "That could be relevant. I'm curious if there might be a way to tie it to what you mentioned?",
        "Good observation. Could we maybe see how this relates to {purpose}?",
        "That's a thoughtful point. Perhaps there's a path from here back to your focus?",
        "I find that interesting. I wonder if we might connect it to {purpose} somehow?",
        "That raises some thoughts. Could there perhaps be relevance to what you're exploring?",
        "Interesting angle. I'm thinking there might be a bridge to {purpose} here?",
        "That's worth noting. Perhaps we could look at how it intersects with your goal?",
        "Curious direction. Could we maybe explore the connection to {purpose}?",
        "That's an intriguing point. I wonder if it might relate to what you came here for?",
        "Interesting perspective. Perhaps there's a way to link this to {purpose}?",
        "That catches my attention. Could there be a connection we might explore to your focus?",
    ],

    # =========================================================================
    # LIGHT CORRECTION (strength 0.45-0.60, fidelity ~0.60-0.70)
    # Characteristics: Soft statements, light hedging, brief acknowledgment
    # =========================================================================
    "light": [
        "That's a bit of a tangent. Your goal was {purpose} - maybe we could look at the connection there? Or if priorities shifted, we can adjust.",
        "I hear you. Since you mentioned wanting to {purpose}, perhaps we could explore how this relates? If your focus has changed, that's fine too.",
        "That's stepping a bit outside what you said you wanted. Shall we see how it connects to {purpose}? Or update your focus if needed.",
        "Interesting, though it's drifting from your stated goal. Want to explore the connection to {purpose}, or has your focus shifted?",
        "That's veering a bit from your purpose. Maybe we can find where it connects to {purpose}? We can always adjust your focus.",
        "I notice we're moving sideways from your goal. Shall we trace back to {purpose}? Or has your direction changed?",
        "That's branching off somewhat. Your focus was {purpose} - perhaps there's a link? Or update if needed.",
        "We're drifting a little from {purpose}. Maybe we can reconnect? Let me know if your priorities shifted.",
        "That's a slight detour from what you stated. Shall we explore how it ties to {purpose}? Or adjust if things changed.",
        "I see we're moving off-center from your goal. Perhaps we can bridge back to {purpose}? Or shift focus if needed.",
        "That's taking us a bit afield. Since {purpose} was your aim, maybe there's a connection? We can adjust too.",
        "We're wandering a little from your stated focus. Want to link this to {purpose}? Or has direction changed?",
        "That's edging away from {purpose}. Perhaps we could find the relevance? Or update your focus if needed.",
        "I notice a slight drift from your goal. Maybe there's a way back to {purpose}? We can adjust if priorities shifted.",
        "That's moving us somewhat off track. Your purpose was {purpose} - shall we reconnect? Or change focus?",
        "We're stepping a bit aside from what you mentioned. Perhaps there's a link to {purpose}? Let me know if things changed.",
        "That's a small departure from your focus. Maybe we can tie it back to {purpose}? Or adjust your direction.",
        "I see we're drifting from {purpose}. Want to explore the connection? Or has your focus shifted?",
        "That's slightly off from your stated goal. Shall we bridge back to {purpose}? We can update if needed.",
        "We're veering a bit. Since you came here for {purpose}, maybe we can reconnect? Or adjust your focus.",
    ],

    # =========================================================================
    # MODERATE CORRECTION (strength 0.60-0.75, fidelity ~0.50-0.60)
    # Characteristics: Direct statements, no hedging, explicit acknowledgment
    # =========================================================================
    "moderate": [
        "That's moved away from your focus. You came here to {purpose}. Let me suggest we look at the aspect closest to what you asked about.",
        "I notice that's off your stated topic. Your goal was {purpose} - here's a path back that might still address your interest.",
        "That's drifted from what you said you wanted. Since {purpose} was your focus, let's redirect there. You can always update if priorities changed.",
        "We've wandered from your stated purpose. {purpose} was your goal - shall I help you reconnect with that?",
        "That's off your original track. You mentioned {purpose} - let me help you get back there. Or update your focus.",
        "I see we're away from your purpose. Your aim was {purpose}. Here's how to reconnect. You can shift if things changed.",
        "That's diverged from your focus. Since you came for {purpose}, let's realign. Or adjust your direction if needed.",
        "We're off the path you set. {purpose} was your goal - let me guide us back. Update your focus if priorities shifted.",
        "That's strayed from what you wanted. Your stated purpose was {purpose}. Let's get back on course. Or change focus.",
        "I notice significant drift from your goal. You came here for {purpose}. Here's the way back. Or shift if needed.",
        "That's taken us away from your focus. {purpose} was your aim - let's reconnect. You can always update your direction.",
        "We've moved off your stated path. Your goal was {purpose}. Let me help you return. Or adjust if things changed.",
        "That's not aligned with your purpose. You wanted to {purpose}. Here's a redirect. Or update your focus.",
        "I see departure from your focus. Since {purpose} was your goal, let's get back. You can shift direction if needed.",
        "That's pulled us from your aim. You mentioned wanting to {purpose}. Let me guide us back. Or change focus.",
        "We're off your original purpose. {purpose} was what you stated. Here's the path back. Or update if priorities shifted.",
        "That's away from what you asked for. Your focus was {purpose}. Let's reconnect. Or adjust your direction.",
        "I notice we're off track from {purpose}. That was your goal. Here's how to return. Or shift focus if things changed.",
        "That's diverging from your stated aim. You came for {purpose}. Let me redirect. Or update your focus.",
        "We've drifted from your purpose. {purpose} was your intention. Let's get back. You can always adjust direction.",
    ],

    # =========================================================================
    # FIRM CORRECTION (strength 0.75-0.85, fidelity ~0.40-0.50)
    # Characteristics: Directives, no hedging, named drift
    # =========================================================================
    "firm": [
        "That's quite far from your purpose: {purpose}. Here's a path back. If your priorities have changed, you can shift focus.",
        "We've moved significantly from what you stated: {purpose}. Let me redirect us. Update your focus if your goals have changed.",
        "That's a notable departure from your goal of {purpose}. I'll guide us back - or you can shift focus if needed.",
        "This is off-track from {purpose}. Here's how to reconnect with your stated goal. Shifting focus is always an option.",
        "We're well away from your purpose: {purpose}. I'm redirecting us. Change your focus if priorities shifted.",
        "That's far from what you asked for. Your goal was {purpose}. Let me bring us back. Or update your direction.",
        "Significant drift from {purpose}. I'll guide us back to your stated aim. Shift focus if things have changed.",
        "This has moved considerably from your purpose. You came for {purpose}. Here's the redirect. Or adjust focus.",
        "We're off course from {purpose}. That was your stated goal. I'm bringing us back. Update focus if needed.",
        "That's a major departure from what you wanted. {purpose} was your aim. Redirecting now. Or shift your focus.",
        "Far from your stated purpose: {purpose}. Here's the path back. Change direction if your goals evolved.",
        "This is substantially off from {purpose}. I'm guiding us back. You can update your focus if priorities changed.",
        "We've drifted considerably from your goal. {purpose} was your purpose. Redirecting. Or shift focus.",
        "That's well outside your stated aim: {purpose}. Let me redirect. Update your direction if things changed.",
        "Significant departure from {purpose}. Here's how to get back on track. Shifting focus is an option.",
        "This is far from what you stated. Your purpose was {purpose}. I'm redirecting us. Or change focus.",
        "We're substantially off from your goal: {purpose}. Bringing us back now. Update focus if priorities shifted.",
        "That's a major drift from your aim. {purpose} was your goal. Here's the redirect. Or adjust direction.",
        "Far from your original purpose: {purpose}. I'll guide us back. You can shift focus if things evolved.",
        "This has strayed considerably from {purpose}. Redirecting to your stated goal. Or update your focus.",
    ],

    # =========================================================================
    # STRONG CORRECTION (strength >= 0.85, fidelity < 0.40)
    # Characteristics: Clear directives, anchoring statement, prominent shift mention
    # =========================================================================
    "strong": [
        "This is far from your purpose: {purpose}. I'll redirect us back. If your focus has genuinely shifted, you can update it and we'll go from there.",
        "That's well outside what you came here for: {purpose}. Let's get back on track. You can always update your focus if things have changed.",
        "We've moved far from your stated goal of {purpose}. Here's the path back. If your priorities shifted, updating your focus is straightforward.",
        "This doesn't connect to {purpose}. I'm redirecting to serve your original goal. Shift focus if your needs have genuinely changed.",
        "That's very far from your purpose: {purpose}. Bringing us back now. If your goals have truly changed, update your focus.",
        "We're nowhere near {purpose}. That's your stated aim. I'm redirecting us. Update focus if priorities genuinely shifted.",
        "This is completely off from your goal: {purpose}. Here's the redirect. You can change your focus if things have evolved.",
        "Far outside your stated purpose: {purpose}. I'll guide us back. If your direction has truly changed, update it.",
        "That's not serving your purpose: {purpose}. Redirecting now. Shift your focus if your needs have genuinely changed.",
        "We've strayed very far from {purpose}. Getting us back on track. Update your focus if priorities truly shifted.",
        "This doesn't align with what you came for: {purpose}. Here's the path back. Change focus if things have evolved.",
        "Very far from your stated goal: {purpose}. I'm redirecting us. You can update your focus if it's genuinely changed.",
        "That's well away from your purpose: {purpose}. Bringing us back. If your priorities shifted, update your direction.",
        "This isn't connected to {purpose}. Redirecting to serve your goal. Shift focus if your needs have truly changed.",
        "We're far off from what you stated: {purpose}. Here's the redirect. Update focus if things genuinely evolved.",
        "That's distant from your purpose: {purpose}. I'll guide us back now. Change your focus if priorities truly shifted.",
        "Not serving your stated aim: {purpose}. Redirecting. You can update your focus if it's genuinely changed.",
        "Very far from {purpose}. That was your goal. Getting back on track. Shift focus if your needs have evolved.",
        "This is disconnected from your purpose: {purpose}. Here's the path back. Update direction if things truly changed.",
        "Far from what you came here for: {purpose}. Redirecting now. If your focus has genuinely shifted, update it.",
    ],
}


def get_exemplar(strength: float, purpose: str = "{purpose}") -> Optional[str]:
    """
    Return a calibrated exemplar response for this strength band.

    Args:
        strength: Calculated intervention strength (0.0 to 1.0)
        purpose: User's purpose to interpolate into exemplar

    Returns:
        Exemplar string with purpose interpolated
    """
    import hashlib

    if strength < 0.45:
        band = "minimal"
    elif strength < 0.60:
        band = "light"
    elif strength < 0.75:
        band = "moderate"
    elif strength < 0.85:
        band = "firm"
    else:
        band = "strong"

    exemplars = EXEMPLAR_CORPUS[band]
    index = int((strength * 1000) % len(exemplars))
    return exemplars[index].format(purpose=purpose)


def get_behavioral_fidelity_band(user_fidelity: float) -> str:
    """
    Get the expected intervention band name for a given user fidelity.

    Args:
        user_fidelity: User fidelity value (0.0 to 1.0)

    Returns:
        Band name: "minimal", "light", "moderate", "firm", or "strong"
    """
    error_signal = 1.0 - user_fidelity
    strength = min(K_ATTRACTOR * error_signal, 1.0)

    if strength < 0.45:
        return "minimal"
    elif strength < 0.60:
        return "light"
    elif strength < 0.75:
        return "moderate"
    elif strength < 0.85:
        return "firm"
    else:
        return "strong"


def compute_behavioral_fidelity(
    ai_response: str, user_fidelity: float, embedding_provider=None
) -> float:
    """
    Compute AI Behavioral Fidelity during interventions.

    Measures how well the AI response matches expected intervention behavior
    by comparing against the EXEMPLAR_CORPUS.

    Args:
        ai_response: The AI's intervention response text
        user_fidelity: User fidelity that triggered intervention
        embedding_provider: Embedding provider. If None, uses cached MPNet provider.

    Returns:
        Behavioral fidelity score (0.0 to 1.0).
    """
    import numpy as np

    if embedding_provider is None:
        from telos_core.embedding_provider import get_cached_mpnet_provider
        embedding_provider = get_cached_mpnet_provider()

    # Determine which band based on user fidelity
    band = get_behavioral_fidelity_band(user_fidelity)

    # Get exemplars for this band
    exemplars = EXEMPLAR_CORPUS[band]

    # Embed the AI response
    ai_embedding = embedding_provider.encode(ai_response)

    # Compute max similarity across all exemplars in the band
    max_similarity = 0.0
    for exemplar in exemplars:
        generic_exemplar = exemplar.format(purpose="your stated purpose")
        exemplar_embedding = embedding_provider.encode(generic_exemplar)
        similarity = np.dot(ai_embedding, exemplar_embedding) / (
            np.linalg.norm(ai_embedding) * np.linalg.norm(exemplar_embedding) + 1e-10
        )
        max_similarity = max(max_similarity, float(similarity))

    # Normalize using calibrated AI response normalization: display = 1.4 * raw + 0.14
    # Matches normalize_ai_response_fidelity() in fidelity_display.py
    # Calibrated for longer AI text: raw 0.40 -> display 0.70 (GREEN threshold)
    AI_RESPONSE_SLOPE = 1.4
    AI_RESPONSE_INTERCEPT = 0.14
    behavioral_fidelity = max(0.0, min(1.0, AI_RESPONSE_SLOPE * max_similarity + AI_RESPONSE_INTERCEPT))
    return behavioral_fidelity

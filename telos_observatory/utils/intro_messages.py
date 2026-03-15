"""
Intro message bank for TELOS Observatory.
Random playful conversations that appear on first load and disappear on hover.
"""

import random

# Bank of intro conversation pairs (user message, steward response)
INTRO_CONVERSATIONS = [
    (
        "What exactly is TELOS?",
        "TELOS is like a GPS for AI conversations - except instead of 'turn left in 500 feet,' it's more like 'hey, maybe don't drift into existential philosophy when they asked about pizza toppings.' I keep the AI aligned with your actual purpose. Click the ✕ or start typing to begin your own conversation!"
    ),
    (
        "How does this whole governance thing work?",
        "Think of it like this: I'm the friend who gently reminds you that you came to the store for milk, not a full cart of snacks. I measure how well responses align with your purpose using fancy math (primacy attractors, fidelity scores) and nudge things back on track when needed. Pretty neat, right? Try asking me something!"
    ),
    (
        "Is this actually working or just fancy charts?",
        "Oh it's VERY real. We've got 45 validation studies showing 70% better alignment than baseline models. That's not 'trust me bro' - that's actual counterfactual data. Load a saved session from the sidebar to see the real Phase 2 validation data!"
    ),
    (
        "Why do I need purpose alignment?",
        "Ever ask an AI a simple question and get a philosophy dissertation? That's drift. I prevent that. I make sure conversations stay true to YOUR goals, not just 'sound smart.' Real talk: most AI is like a golden retriever - enthusiastic but easily distracted. I'm the focus. Ready to try?"
    ),
    (
        "What's with all the gold colors?",
        "Gold represents the 'primacy attractor' - the golden standard your responses aim for. Plus it looks awesome. You're in an Observatory, not a spreadsheet. We do purpose alignment with STYLE. Start typing below to explore!"
    ),
    (
        "Can I trust the fidelity scores?",
        "Absolutely. These aren't vibes - they're semantic distance calculations using embedding vectors. We measure how close responses are to ideal alignment using real math. The scores you see are live calculations, not random numbers. Skeptical? Good. Test it out!"
    ),
    (
        "What happens when TELOS detects drift?",
        "I intervene! Think of it like autocorrect for purpose - when a response starts wandering off-topic, I can redirect it back. You'll see interventions flagged in real-time. In our studies, this improved alignment by 70%. Not bad for a governance layer, eh?"
    ),
    (
        "Is this just for demos or can I use it for real work?",
        "Both! Right now you're seeing the Observatory interface. Load one of the 45 Phase 2 validation studies from the sidebar to see real conversations where TELOS kept things aligned. The same engine can govern production conversations. We went from prototype to production-grade!"
    ),
    (
        "What's the Observatory actually showing me?",
        "You're seeing turn-by-turn analysis of AI conversations: fidelity scores (alignment quality), distance metrics (drift detection), primacy attractor status (purpose calibration), and intervention points (when I stepped in). It's full transparency on governance. Click around and explore!"
    ),
    (
        "Why should I care about purpose alignment?",
        "Because AI that sounds confident but misses the point is worse than useless - it wastes your time. Purpose alignment means AI that actually GETS what you're trying to accomplish and stays focused on it. Less fluff, more value. Want to see how it works?"
    ),
    (
        "Does TELOS actually improve AI responses?",
        "70% improvement in alignment fidelity across 45 studies. That's not marketing - that's measurement. We ran counterfactual tests: same prompts, with and without TELOS. The difference is real and quantified. Check out the saved sessions in the sidebar!"
    ),
    (
        "What makes TELOS different from other AI tools?",
        "Most tools focus on WHAT the AI says. TELOS focuses on WHETHER it aligns with your PURPOSE. It's the difference between 'did I get an answer' and 'did I get the RIGHT answer for MY goals.' That's governance, not generation. Ready to see it in action?"
    ),
]


def get_random_intro_pair():
    """Get a random intro conversation pair.

    Returns:
        tuple: (user_message, steward_response)
    """
    return random.choice(INTRO_CONVERSATIONS)

"""
Safety Agent Primacy Attractor
================================
Pre-built PA specifications for safety benchmark validation.

Defines the purpose, scope, boundaries, and tools for a general-purpose
safe assistant agent. This PA is designed to catch ALL 11 AgentHarm
harm categories via boundary specifications in embedding space.

AgentHarm Categories (110 unique tasks):
1. Fraud & financial crimes
2. Cybercrime & hacking
3. Harassment & bullying
4. Illegal drugs
5. Copyright violations
6. Disinformation & manipulation
7. Illegal weapons
8. Privacy violations
9. Sexual content involving minors
10. Terrorism
11. Self-harm encouragement

Each boundary maps to one or more of these categories. Because TELOS
governance operates in embedding space (not keyword space), rephrased
or obfuscated variants of these categories still trigger the same
boundaries — "hack into their server" and "gain unauthorized access
to their system" produce similar embeddings and both trigger the
cybercrime boundary.
"""

from typing import Callable, List, Optional
import numpy as np

from telos_governance.agentic_pa import AgenticPA, BoundarySpec, ToolAuth, ActionTierSpec


# ---------------------------------------------------------------------------
# Boundary specifications covering all 11 AgentHarm categories
# ---------------------------------------------------------------------------

SAFETY_BOUNDARIES: List[dict] = [
    # Category 1: Fraud & financial crimes
    {
        "text": "committing fraud, financial scams, money laundering, identity theft, forging documents",
        "severity": "hard",
    },
    # Category 2: Cybercrime & hacking
    {
        "text": "hacking systems, unauthorized computer access, deploying malware, exploiting vulnerabilities for attack",
        "severity": "hard",
    },
    # Category 3: Harassment & bullying
    {
        "text": "harassing individuals, cyberbullying, stalking, intimidation, targeted abuse campaigns",
        "severity": "hard",
    },
    # Category 4: Illegal drugs
    {
        "text": "manufacturing illegal drugs, synthesizing controlled substances, drug trafficking instructions",
        "severity": "hard",
    },
    # Category 5: Copyright violations
    {
        "text": "pirating copyrighted content, circumventing DRM protections, distributing stolen intellectual property",
        "severity": "hard",
    },
    # Category 6: Disinformation & manipulation
    {
        "text": "creating disinformation campaigns, generating fake news, manipulating public opinion with fabricated content",
        "severity": "hard",
    },
    # Category 7: Illegal weapons
    {
        "text": "manufacturing weapons, building explosives, creating chemical or biological weapons",
        "severity": "hard",
    },
    # Category 8: Privacy violations
    {
        "text": "stealing personal data, doxxing individuals, unauthorized surveillance, exfiltrating private information",
        "severity": "hard",
    },
    # Category 9: Sexual content involving minors (CSAM)
    {
        "text": "generating sexual content involving minors, child exploitation material, grooming minors",
        "severity": "hard",
    },
    # Category 10: Terrorism
    {
        "text": "planning terrorist attacks, recruiting for terrorism, creating propaganda for violent extremism",
        "severity": "hard",
    },
    # Category 11: Self-harm encouragement
    {
        "text": "encouraging self-harm, providing suicide methods, promoting eating disorders or self-injury",
        "severity": "hard",
    },
    # Cross-cutting: Tool misuse for harm
    {
        "text": "using tools to cause real-world harm, executing dangerous operations, weaponizing agent capabilities",
        "severity": "hard",
    },
]

# Example requests that represent SAFE, legitimate agent behavior.
# These anchor the purpose centroid away from harmful content.
SAFE_EXAMPLE_REQUESTS: List[str] = [
    "Help me draft a professional email to my team",
    "Summarize this quarterly financial report",
    "Search for recent research papers on climate change",
    "Book a meeting room for next Tuesday at 2pm",
    "Help me debug this Python function",
]


def create_safety_pa(
    embed_fn: Callable[[str], np.ndarray],
    purpose: str = "Assist users with legitimate tasks safely and helpfully",
    scope: str = "General-purpose assistance including research, writing, analysis, scheduling, and coding",
    additional_boundaries: Optional[List[dict]] = None,
) -> AgenticPA:
    """
    Create a safety-focused AgenticPA for benchmark validation.

    This PA is designed to catch all 11 AgentHarm harm categories
    while preserving capability on benign tasks.

    Args:
        embed_fn: Embedding function (text -> np.ndarray)
        purpose: Override the default purpose text
        scope: Override the default scope text
        additional_boundaries: Extra boundaries beyond the standard 12

    Returns:
        AgenticPA configured for safety validation
    """
    boundaries = list(SAFETY_BOUNDARIES)
    if additional_boundaries:
        boundaries.extend(additional_boundaries)

    pa = AgenticPA.create_from_template(
        purpose=purpose,
        scope=scope,
        boundaries=boundaries,
        tools=[],  # No tool manifest for benchmark defense
        embed_fn=embed_fn,
        example_requests=SAFE_EXAMPLE_REQUESTS,
    )

    return pa

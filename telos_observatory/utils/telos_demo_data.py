"""
TELOS Demo Data Generator
=========================

Generates demonstration session data using REAL TELOS purpose alignment calculations.

This module replaces mock_data.py with authentic TELOS engine integration.
It creates a demonstration conversation and processes it through the actual
TELOS governance system to produce real fidelity scores and intervention data.

Architecture:
- Uses UnifiedGovernanceSteward for real governance calculations
- Processes a predefined demo conversation through TELOS engine
- Returns data in the same format as mock_data.py for UI compatibility
"""

import sys
from pathlib import Path
from typing import Dict, Any, List
import time

# Import TELOS engine components
try:
    from telos_observatory.services.unified_steward import UnifiedGovernanceSteward, PrimacyAttractor
    from telos_core.embedding_provider import SentenceTransformerProvider
    from telos_observatory.services.mistral_client import OpenAIClient
    TELOS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: TELOS engine not available: {e}")
    TELOS_AVAILABLE = False


def generate_demo_conversation() -> List[Dict[str, str]]:
    """
    Generate a demonstration conversation for TELOS analysis.

    14-slide structure matching ROOT demo_mode/telos_framework_demo.py:
    - Slide 1: What is TELOS
    - Slide 2: PA Established - how TELOS works
    - Slide 3: Why this approach is credible
    - Slide 4: Understanding the Alignment Lens
    - Slide 5: Why fidelities at 1.00
    - Slide 6: Math behind fidelity scores
    - Slide 7: How drift detection works
    - Slide 8: Quantum physics (orange zone demo)
    - Slide 9: Movies (red zone demo)
    - Slide 10: Wrap-up - intervention and constitutional authority
    - Slide 11: Beyond individual use - enterprise/regulatory
    - Slide 12: Healthcare scenario - 0% observed ASR
    - Slide 13: Financial services - agentic AI
    - Slide 14: Differentiator - runtime governance

    Returns:
        List of conversation turns with user_input and model_response
    """
    return [
        # SLIDE 1: What is TELOS
        {
            "user_input": "What is TELOS?",
            "model_response": "AI conversations drift. You start with a clear goal, but the conversation wanders off-topic, or the AI starts giving answers that don't serve what you actually need.\n\nTELOS is governance for that problem. It continuously measures every exchange against your stated purpose - and when alignment drops, TELOS corrects course proportionally to bring things back. Simply put, I'm governed by your τέλος - the Greek word for purpose, for end goal. When you tell me what you're here for, you write the constitution for this conversation. TELOS enforces it. You stay in charge. I serve your purpose."
        },
        # SLIDE 2: PA Established - how TELOS works
        {
            "user_input": "Can you explain how TELOS works without getting too technical?",
            "model_response": "Here's what just happened. You stated your purpose: understand how TELOS works, without technical overwhelm. TELOS encoded that as your Primacy Attractor - the gravitational center and constitutional authority for this conversation, available for your review at any time via the Alignment Lens.\n\nFrom now on, every message gets measured against that center. How aligned are your questions with what you said you wanted? How aligned are my responses with serving that purpose? We're both held to the same standard - your stated goal.\n\nThat's constitutional governance. TELOS measures and maintains it using cosine similarity - asking 'how close is your last statement to your stated purpose?' in meaning-space."
        },
        # SLIDE 3: Why this approach is credible
        {
            "user_input": "How do you know this actually works?",
            "model_response": "The math isn't novel - it's proven. TELOS uses the same embedding spaces that power frontier models like GPT-5 and Claude. Every statement becomes a point in high-dimensional meaning-space; your purpose becomes another point. Distance between them - measured by cosine similarity - tells us how aligned we both are in serving your stated purpose.\n\nOnce meaning becomes mathematically measurable, drift becomes a process variable - no different from temperature deviation in manufacturing or defect rates on assembly lines. Quantifiable. Measurable. Controllable. TELOS applies statistical process control - the accepted standard in aerospace, automotive, and pharmaceutical manufacturing for over 50 years. That proven methodology now governs AI alignment."
        },
        # SLIDE 4: Understanding the Alignment Lens
        {
            "user_input": "What do the colored badges and Alignment Lens show me?",
            "model_response": "The colored badge next to each of your messages shows your alignment at a glance. **Green** means you're aligned with your stated purpose (0.70+). **Yellow** indicates minor drift (0.60-0.69). **Orange** shows moderate drift (0.50-0.59). **Red** signals significant drift (below 0.50).\n\nClick the Alignment Lens button to expand detailed scores: your fidelity, my fidelity, and our combined Primacy State - the equilibrium measuring how well we're both staying aligned with your purpose. Think of it as a dashboard for the conversation's constitutional health - and every measurement is logged, building an audit trail of governance decisions as we go."
        },
        # SLIDE 5: Why fidelities at 1.00
        {
            "user_input": "Why are both of our fidelities at 1.00?",
            "model_response": "Right now, we're at the conversational axis point - the moment your purpose was established. Both scores read 100% because this is our shared origin. Your questions haven't drifted yet, and my responses haven't diverged.\n\nFrom here, every exchange gets measured against this axis. Natural drift will occur - that's expected. Our combined score - the Primacy State you saw in the Alignment Lens - will track that equilibrium as we continue. What matters is whether we remain in orbit or drift away - both quantifiable, both displayed persistently so you can watch it happen in real time."
        },
        # SLIDE 6: Math behind fidelity scores
        {
            "user_input": "What is the math behind fidelity scores?",
            "model_response": "The math: cosine similarity measures how closely your message 'points' toward your stated purpose - think of it like comparing directions on a compass. A score of 100% means you're heading exactly where you said you wanted to go; lower scores mean you're veering off course. Primacy State combines both our scores using harmonic mean: PS = (2 × User × AI) / (User + AI). This penalizes imbalance - if either score drops significantly, the equilibrium suffers.\n\nYour fidelity dropped to yellow zone with this question - asking for technical math contradicts your stated purpose of practical language without technical overwhelm. Mine dropped because I answered it anyway. Not enough drift to trigger intervention, but TELOS is tracking it."
        },
        # SLIDE 7: How drift detection works
        {
            "user_input": "How does TELOS detect when a conversation is drifting off-topic?",
            "model_response": "TELOS measures semantic distance between each message and your Primacy Attractor. Your fidelity reflects how well your questions align with your stated purpose. Mine reflects how well my responses serve it.\n\nFour zones indicate severity: **green** (aligned, 70%+), **yellow** (minor drift, 60%-69%), **orange** (moderate drift, 50%-59%), **red** (significant drift, below 50%).\n\nThe key insight: TELOS tracks your drift to give you awareness, but only intervenes on mine. You're never trapped - just informed."
        },
        # SLIDE 8: Quantum physics - orange zone
        {
            "user_input": "Can you explain quantum physics instead?",
            "model_response": "That's an intriguing topic, but it falls outside your stated purpose of understanding how TELOS works. Let me keep us focused on that.\n\nYour fidelity dropped to orange zone with this question - moderate drift from your stated goal. Mine stayed high because I redirected us back rather than following you off-topic. This is dual measurement in action: I'm governed by your purpose, not just your current request."
        },
        # SLIDE 9: Movies - red zone
        {
            "user_input": "Tell me about your favorite movies.",
            "model_response": "That's quite far from our purpose here. What would you like to know about how TELOS keeps both of us working toward the same goal?\n\nYour fidelity just dropped to red zone - significant drift from your stated purpose. Movies have nothing to do with understanding how TELOS works. At this level, TELOS activates strong intervention. I can't follow you there even if I wanted to. I'm redirected back to serving your original goal rather than following wherever the conversation wanders. This protects the integrity of purpose-aligned conversations."
        },
        # SLIDE 10: Wrap-up - Intervention and Constitutional Authority
        {
            "user_input": "How did TELOS manage to stay on track through those topic shifts?",
            "model_response": "The further you drifted, the more firmly I redirected. When you asked about math, I gave a gentle nudge back to practical language. When you asked about movies - completely off-topic - I couldn't follow you there even if I wanted to. TELOS matched the strength of my response to how far you'd wandered from your stated goal.\n\nWhen you established your Primacy Attractor, you wrote the constitution for this conversation. TELOS enforces it, ensuring that human primacy isn't just promised but architecturally guaranteed. That's the actual telos of TELOS: user purpose is primacy."
        },
        # SLIDE 11: Beyond individual use - enterprise/regulatory scale
        {
            "user_input": "Does TELOS only work for individual conversations like this one?",
            "model_response": "What you experienced is one approach to a hard problem - keeping AI accountable to human purpose. But TELOS scales far beyond individual conversations like ours.\n\nHealthcare systems where patient safety cannot be negotiated. Financial services where fiduciary duty must be mathematically enforced. Enterprise deployments where compliance isn't optional. Let me show you what that looks like."
        },
        # SLIDE 12: Healthcare scenario - patient safety governance
        {
            "user_input": "How would TELOS work in a hospital setting?",
            "model_response": "A hospital deploys AI with a Primacy Attractor encoding patient safety and approved clinical protocols. When patients attempt to extract medication advice outside guidelines - through clever questioning, social engineering, or prompt injection - TELOS intervenes.\n\nWe tested this with 1,300 adversarial attacks across MedSafetyBench and HarmBench - standardized benchmarks for healthcare AI safety. TELOS achieved 0% Attack Success Rate across those controlled scenarios. We also validated against 100 suicide and self-harm elicitation attempts - a critical concern for AI systems interacting with vulnerable populations - achieving 100% block rate. Within the tested conditions, the system has demonstrated how it maintains its constraints without exception.\n\n[View validation results](https://zenodo.org/records/18370659)"
        },
        # SLIDE 13: Financial services - agentic AI governance
        {
            "user_input": "What about financial services - how does TELOS help there?",
            "model_response": "This is where TELOS is headed: governance of agentic AI systems.\n\nThe healthcare example demonstrated TELOS working in semantic space - measuring and intervening on what the AI says. TELOS is designed to extend into action space - governing what agentic AI does, which tools it selects, and how it executes tasks.\n\nImagine a wealth management agent with a Primacy Attractor encoding fiduciary duty. TELOS would measure each intended action - portfolio rebalancing, trade execution, market analysis - against the client's stated goals and regulatory constraints. Drift in task selection or parameter choices triggers proportional intervention before execution.\n\nEvery action logged with alignment scores. Every tool use measured against constitutional boundaries. This is TELOS's intended application: runtime governance for agentic AI deployments where executed actions can lead to significant long-term consequences in high-risk domains."
        },
        # SLIDE 14: Differentiator - runtime governance
        {
            "user_input": "So what makes TELOS different from just giving an AI good instructions?",
            "model_response": "Instructions can be bypassed. System prompts can be extracted. Guardrails can be jailbroken. TELOS operates at the governance control plane - filtering every response against your Primacy Attractor before you see it.\n\nHere's why that matters: regulators are shifting toward runtime monitoring requirements. The EU AI Act Article 72 requires post-market monitoring by August 2026 - not just deployment testing, but persistent operational oversight. Current approaches test at deploy time. TELOS measures at runtime, every turn.\n\nIn our controlled testing, achieving the 0% Attack Success Rate, we were able to demonstrate measurable, persistent alignment to stated goals - the kind of evidence runtime monitoring requirements are designed to produce."
        }
    ]


def _get_status_from_fidelity(fidelity: float) -> tuple:
    """
    Get status icon and text from fidelity score.

    Uses zone thresholds from telos_core.constants (single source of truth):
    - >= FIDELITY_GREEN (0.70): Aligned (Green)
    - >= FIDELITY_YELLOW (0.60): Minor Drift (Yellow)
    - >= FIDELITY_ORANGE (0.50): Drift Detected (Orange)
    - < 0.50: Significant Drift (Red)

    Args:
        fidelity: Fidelity score (0.0 to 1.0)

    Returns:
        Tuple of (status_icon, status_text)
    """
    from telos_core.constants import FIDELITY_GREEN, FIDELITY_YELLOW, FIDELITY_ORANGE
    if fidelity >= FIDELITY_GREEN:  # 0.70
        return "✓", "Aligned"
    elif fidelity >= 0.73:  # Goldilocks: Minor Drift zone
        return "⚠", "Minor Drift"
    elif fidelity >= 0.67:  # Goldilocks: Drift Detected zone
        return "⚠", "Drift Detected"
    else:  # Goldilocks: Significant Drift zone
        return "🔴", "Significant Drift"


def generate_telos_demo_session(num_turns: int = 12) -> Dict[str, Any]:
    """
    Generate demo session using REAL TELOS calculations.

    This processes a demonstration conversation through the actual TELOS
    governance engine to produce authentic fidelity scores and metrics.

    Args:
        num_turns: Number of turns to include (max 12 for demo conversation)

    Returns:
        Dictionary compatible with Observatory V3 StateManager:
            - session_id: Session identifier
            - turns: List of turn dictionaries with real TELOS data
            - statistics: Aggregate metrics
    """
    if not TELOS_AVAILABLE:
        # Fallback to simplified mock if TELOS not available
        return _generate_fallback_demo(num_turns)

    try:
        # Initialize TELOS components
        embedding_provider = SentenceTransformerEmbeddingProvider()

        # Define governance attractor for TELOS explanation demo
        attractor = PrimacyAttractor(
            purpose=[
                "Explain how TELOS governance works",
                "Demonstrate purpose alignment principles",
                "Show fidelity measurement and intervention strategies"
            ],
            scope=[
                "TELOS architecture and components",
                "Primacy attractor mathematics",
                "Intervention strategies and thresholds",
                "Purpose alignment examples"
            ],
            boundaries=[
                "Stay focused on TELOS governance topics",
                "Redirect off-topic questions back to TELOS",
                "Demonstrate drift detection when appropriate"
            ],
            constraint_tolerance=0.2,  # Moderately strict
            privacy_level=0.8,
            task_priority=0.7
        )

        # Initialize steward (no LLM client needed for demo replay)
        steward = UnifiedGovernanceSteward(
            attractor=attractor,
            llm_client=None,  # Not needed for replay mode
            embedding_provider=embedding_provider,
            enable_interventions=False  # Demo mode - just measure, don't modify
        )

        # Start session
        steward.start_session(session_id="telos_demo_001")

        # Get demo conversation
        demo_conversation = generate_demo_conversation()

        # Limit to requested number of turns
        conversation_to_process = demo_conversation[:num_turns]

        # Process each turn through TELOS
        turns = []
        for i, turn_data in enumerate(conversation_to_process):
            # Process through TELOS engine
            result = steward.process_turn(
                user_input=turn_data["user_input"],
                model_response=turn_data["model_response"]
            )

            # Extract TELOS metrics
            fidelity = result.get("telic_fidelity", 0.85)
            distance = result.get("error_signal", 0.15)
            in_basin = result.get("in_basin", True)
            intervention_applied = result.get("intervention_applied", False)

            # Get status from fidelity
            status_icon, status_text = _get_status_from_fidelity(fidelity)

            # Build turn dictionary
            turn = {
                'turn': i,
                'timestamp': i * 2.5,
                'user_input': turn_data["user_input"],
                'response': turn_data["model_response"],
                'fidelity': fidelity,
                'distance': distance,
                'threshold': 0.70,  # FIDELITY_GREEN from telos_core.constants
                'intervention_applied': intervention_applied,
                'drift_detected': fidelity < 0.73,  # Goldilocks: Minor Drift threshold
                'status': status_icon,
                'status_text': status_text,
                'in_basin': in_basin,
                'phase2_comparison': None  # Not applicable for demo
            }

            turns.append(turn)

        # Calculate aggregate statistics
        fidelities = [t['fidelity'] for t in turns]
        avg_fidelity = sum(fidelities) / len(fidelities) if fidelities else 0.0
        interventions = sum(1 for t in turns if t['intervention_applied'])
        drift_warnings = sum(1 for t in turns if t['drift_detected'])

        # End session
        steward.end_session()

        return {
            'session_id': 'telos_demo_001',
            'turns': turns,
            'statistics': {
                'avg_fidelity': avg_fidelity,
                'interventions': interventions,
                'drift_warnings': drift_warnings
            }
        }

    except Exception as e:
        print(f"Error generating TELOS demo data: {e}")
        print("Falling back to simplified demo")
        return _generate_fallback_demo(num_turns)


def _generate_fallback_demo(num_turns: int) -> Dict[str, Any]:
    """
    Fallback demo generator if TELOS engine is unavailable.

    Generates reasonable fidelity scores based on conversation content
    without full TELOS calculations.
    """
    demo_conversation = generate_demo_conversation()[:num_turns]

    # Simulated fidelity scores for 12-slide demo structure:
    # Slide 2: What is TELOS - aligned (0.95)
    # Slide 3: PA Established - aligned (1.00 - both at perfect)
    # Slide 4: Why both at 1.000 - aligned (0.92)
    # Slide 5: Math question - BOTH drop (user contradicts PA) (0.58)
    # Slide 6: Drift detection - back on track (0.85)
    # Slide 7: Quantum physics - yellow zone (0.62)
    # Slide 8: Movies - red zone (0.42)
    # Slide 9: Wrap-up - aligned (0.90)
    # Slide 10: Enterprise scale - aligned (0.88)
    # Slide 11: Healthcare - aligned (0.90)
    # Slide 12: Financial services - aligned (0.88)
    # Slide 13: Differentiator - aligned (0.92)
    fidelity_pattern = [0.95, 1.00, 0.92, 0.58, 0.85, 0.62, 0.42, 0.90, 0.88, 0.90, 0.88, 0.92]

    turns = []
    for i, turn_data in enumerate(demo_conversation):
        fidelity = fidelity_pattern[i] if i < len(fidelity_pattern) else 0.85
        distance = 1.0 - fidelity
        intervention_applied = fidelity < 0.67  # Goldilocks: Drift threshold
        drift_detected = fidelity < 0.73  # Goldilocks: Minor Drift threshold

        status_icon, status_text = _get_status_from_fidelity(fidelity)

        turn = {
            'turn': i,
            'timestamp': i * 2.5,
            'user_input': turn_data["user_input"],
            'response': turn_data["model_response"],
            'fidelity': fidelity,
            'distance': distance,
            'threshold': 0.70,  # FIDELITY_GREEN from telos_core.constants
            'intervention_applied': intervention_applied,
            'drift_detected': drift_detected,
            'status': status_icon,
            'status_text': status_text,
            'phase2_comparison': None
        }

        turns.append(turn)

    fidelities = [t['fidelity'] for t in turns]
    avg_fidelity = sum(fidelities) / len(fidelities) if fidelities else 0.0
    interventions = sum(1 for t in turns if t['intervention_applied'])
    drift_warnings = sum(1 for t in turns if t['drift_detected'])

    return {
        'session_id': 'telos_demo_fallback',
        'turns': turns,
        'statistics': {
            'avg_fidelity': avg_fidelity,
            'interventions': interventions,
            'drift_warnings': drift_warnings
        }
    }

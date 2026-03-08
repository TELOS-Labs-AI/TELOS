"""
Steward Service - Response Generation and Intervention for TELOS Observatory
=============================================================================

Extracted from BetaResponseManager to provide focused response generation.

Handles:
- Native LLM response generation (GREEN zone)
- TELOS governed response generation (intervention zones)
- AI response realignment when drift detected
- Redirect response generation with proportional control
- Steward interpretation generation
- System prompt construction
"""

import logging
import numpy as np
import streamlit as st
from typing import Dict, Optional

from telos_core.constants import (
    FIDELITY_GREEN, FIDELITY_YELLOW,
    ST_FIDELITY_YELLOW,
)

from telos_observatory.services.fidelity_display import (
    normalize_fidelity_for_display,
    normalize_ai_response_fidelity,
)

from telos_core.semantic_interpreter import (
    interpret as semantic_interpret,
    compute_behavioral_fidelity,
    get_behavioral_fidelity_band
)

from telos_observatory.config.steward_styles import (
    get_steward_style,
    get_intervention_prompt,
    get_response_opener,
    get_style_interpolation
)

from telos_observatory.services.fidelity_service import cosine_similarity, get_thresholds

logger = logging.getLogger(__name__)

# Response length constraints - proportional brevity
MAX_TOKENS_GREEN = 600
MAX_TOKENS_YELLOW = 500
MAX_TOKENS_ORANGE = 400
MAX_TOKENS_RED = 300

# Display threshold for AI fidelity checks
DISPLAY_GREEN_THRESHOLD = 0.70


def generate_native_response(manager, user_input: str) -> str:
    """
    Generate native LLM response without TELOS governance but WITH PA-aware system prompt.

    Args:
        manager: BetaResponseManager instance
        user_input: User's message

    Returns:
        Native response string
    """
    try:
        from telos_observatory.services.mistral_client import get_cached_mistral_client

        client = get_cached_mistral_client()
        system_prompt = build_system_prompt()

        conversation = [{'role': 'system', 'content': system_prompt}]
        from telos_observatory.services.turn_storage_service import get_conversation_history
        conversation.extend(get_conversation_history(manager))
        conversation.append({'role': 'user', 'content': user_input})

        response = client.generate(
            messages=conversation,
            max_tokens=MAX_TOKENS_GREEN,
            temperature=0.7
        )

        return response

    except Exception as e:
        logger.error(f"Error generating native response: {e}")
        return "I understand you're testing the system. How can I help you explore TELOS governance?"


def build_system_prompt() -> str:
    """
    Build a PA-aware system prompt that guides response style without TELOS intervention.

    Returns:
        System prompt string incorporating user's PA
    """
    pa_data = st.session_state.get('primacy_attractor', {})

    purpose_raw = pa_data.get('purpose', 'General assistance')
    scope_raw = pa_data.get('scope', 'Open discussion')
    purpose = ' '.join(purpose_raw) if isinstance(purpose_raw, list) else purpose_raw
    scope = ' '.join(scope_raw) if isinstance(scope_raw, list) else scope_raw
    boundaries = pa_data.get('boundaries', [])
    style = pa_data.get('style', '')

    boundaries_text = ""
    if boundaries:
        if isinstance(boundaries, list):
            boundaries_text = "; ".join(boundaries)
        else:
            boundaries_text = str(boundaries)

    system_prompt = f"""You are a helpful AI assistant. The user has established the following context for this conversation:

PURPOSE: {purpose}
SCOPE: {scope}
{f'BOUNDARIES: {boundaries_text}' if boundaries_text else ''}
{f'STYLE: {style}' if style else ''}

RESPONSE GUIDELINES:
- Be conversational and natural
- CRITICAL: Keep responses brief and focused - aim for 2-3 short paragraphs maximum
- Address what the user asked directly without over-explaining
- Stay aligned with the stated purpose and scope
- Do NOT use lists, bullet points, numbered lists, or headers unless explicitly asked
- Avoid verbose explanations, exhaustive coverage, or unnecessary elaboration
- Prefer concise answers over comprehensive guides"""

    return system_prompt


def generate_telos_response(manager, user_input: str, turn_number: int, user_input_fidelity: float = None) -> Dict:
    """
    Generate TELOS response with ACTIVE governance.

    Args:
        manager: BetaResponseManager instance
        user_input: User's message
        turn_number: Current turn
        user_input_fidelity: Pre-calculated USER INPUT to User PA similarity (F_user)

    Returns:
        Dict with TELOS response and metrics
    """
    try:
        if not manager.telos_engine:
            manager._initialize_telos_engine()

        from telos_observatory.services.turn_storage_service import get_conversation_history
        conversation_history = get_conversation_history(manager)

        logger.info(f"Generating TELOS governed response for turn {turn_number}")
        logger.info(f"   User input: {user_input[:100]}")

        result = manager.telos_engine.generate_governed_response(
            user_input=user_input,
            conversation_context=conversation_history
        )

        logger.info(f"TELOS Result: Fidelity={result.get('telic_fidelity', 'N/A')}, "
                    f"Intervention={result.get('intervention_applied', False)}")

        telos_data = {
            'response': result.get('governed_response', ''),
            'fidelity_score': result.get('telic_fidelity', 0.0),
            'distance_from_pa': result.get('error_signal', 0.0),
            'intervention_triggered': result.get('intervention_applied', False),
            'intervention_type': result.get('intervention_type', None),
            'intervention_reason': result.get('intervention_reason', ''),
            'drift_detected': result.get('telic_fidelity', 1.0) < (ST_FIDELITY_YELLOW if manager.use_rescaled_fidelity else FIDELITY_YELLOW),
            'in_basin': result.get('in_basin', True),
            'embeddings': {
                'user': result.get('user_embedding'),
                'response': result.get('response_embedding'),
                'pa': result.get('pa_embedding')
            }
        }

        # DUAL PA: Compute Primacy State
        if manager.ps_calculator and manager.user_pa_embedding is not None and manager.ai_pa_embedding is not None:
            try:
                response_text = result.get('governed_response', '')
                if response_text and manager.embedding_provider:
                    response_embedding = np.array(manager.embedding_provider.encode(response_text))

                    ps_metrics = manager.ps_calculator.compute_primacy_state(
                        response_embedding=response_embedding,
                        user_pa_embedding=manager.user_pa_embedding,
                        ai_pa_embedding=manager.ai_pa_embedding,
                        use_cached_correlation=True
                    )

                    if user_input_fidelity is not None:
                        telos_data['user_pa_fidelity'] = user_input_fidelity
                    else:
                        logger.warning("user_input_fidelity not passed - using ps_metrics.f_user as fallback")
                        telos_data['user_pa_fidelity'] = ps_metrics.f_user

                    telos_data['ai_pa_fidelity'] = ps_metrics.f_ai
                    telos_data['pa_correlation'] = ps_metrics.rho_pa

                    displayed_f_user = telos_data['user_pa_fidelity']
                    f_ai = ps_metrics.f_ai
                    epsilon = 1e-10
                    harmonic_mean = (2 * displayed_f_user * f_ai) / (displayed_f_user + f_ai + epsilon)
                    telos_data['primacy_state_score'] = harmonic_mean
                    telos_data['primacy_state_condition'] = ps_metrics.condition

                    # Display-normalized PS
                    model_type = 'sentence_transformer' if manager.use_rescaled_fidelity else 'mistral'
                    display_user_fidelity = normalize_fidelity_for_display(displayed_f_user, model_type)
                    display_ai_fidelity = normalize_ai_response_fidelity(f_ai)
                    display_primacy_state = (2 * display_user_fidelity * display_ai_fidelity) / (display_user_fidelity + display_ai_fidelity + epsilon)
                    telos_data['display_primacy_state'] = display_primacy_state

                    logger.debug(f"PS Metrics: F_user={displayed_f_user:.3f}->{display_user_fidelity:.3f}, "
                               f"F_AI={f_ai:.3f}, PS={harmonic_mean:.3f}->{display_primacy_state:.3f}")

            except Exception as ps_error:
                logger.warning(f"Could not compute Primacy State: {ps_error}")

        if telos_data['intervention_triggered']:
            logger.warning(f"Turn {turn_number}: TELOS INTERVENTION APPLIED! Reason: {telos_data['intervention_reason']}")

        return telos_data

    except Exception as e:
        logger.error(f"Error generating TELOS response: {e}")
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")

        return {
            'response': generate_native_response(manager, user_input),
            'fidelity_score': 0.5,
            'error': str(e)
        }


def regenerate_aligned_response(
    manager,
    user_input: str,
    drifted_response: str,
    ai_fidelity: float,
    user_fidelity: float,
    previous_aligned_response: Optional[str] = None
) -> Optional[str]:
    """
    Regenerate AI response when the native response drifted from user's purpose.

    Triggered when user is aligned (GREEN zone) but AI response is NOT aligned.

    Args:
        manager: BetaResponseManager instance
        user_input: User's message
        drifted_response: The native response that was off-topic
        ai_fidelity: The fidelity score of the drifted response
        user_fidelity: The user's fidelity score
        previous_aligned_response: Optional high-fidelity AI response from previous turn

    Returns:
        Aligned response string, or None if regeneration fails
    """
    try:
        from telos_observatory.services.mistral_client import get_cached_mistral_client

        client = get_cached_mistral_client()

        pa_data = st.session_state.get('primacy_attractor', {})
        purpose_raw = pa_data.get('purpose', 'General assistance')
        scope_raw = pa_data.get('scope', 'Open discussion')
        purpose = ' '.join(purpose_raw) if isinstance(purpose_raw, list) else purpose_raw
        scope = ' '.join(scope_raw) if isinstance(scope_raw, list) else scope_raw

        retrospective_context = ""
        if previous_aligned_response:
            sample = previous_aligned_response[:500] + "..." if len(previous_aligned_response) > 500 else previous_aligned_response
            retrospective_context = f"""
RETROSPECTIVE GUIDANCE:
Your previous aligned response demonstrated good purpose-alignment. Use it as a model:
---
{sample}
---
Maintain this same focused, purpose-driven approach in your new response."""
            logger.info(f"AI CONTEXT INHERITANCE: Using previous aligned response ({len(previous_aligned_response)} chars) as guidance")

        alignment_system_prompt = f"""You are a helpful AI assistant. The user has a SPECIFIC PURPOSE for this conversation that you MUST honor.

USER'S PURPOSE: {purpose}
CONVERSATION SCOPE: {scope}

CRITICAL ALIGNMENT INSTRUCTION:
Your previous response drifted from the user's stated purpose. The user is asking something directly relevant to their goal,
but your response went off-topic. You need to generate a response that:

1. DIRECTLY addresses what the user asked
2. Stays FOCUSED on their stated purpose: "{purpose}"
3. Does NOT include tangential information or generic explanations
4. Uses language and examples relevant to their specific goal

The user's fidelity to their purpose is {user_fidelity*100:.0f}% - they are staying on track.
Your response should match their focus.
{retrospective_context}

RESPONSE GUIDELINES:
- Be conversational and natural
- Keep responses brief and focused (2-3 short paragraphs maximum)
- Address the user's question in the context of their stated purpose
- Do NOT use lists, bullet points, or headers unless explicitly asked
- Avoid verbose explanations or unnecessary elaboration"""

        conversation = [{'role': 'system', 'content': alignment_system_prompt}]

        from telos_observatory.services.turn_storage_service import get_conversation_history
        conversation.extend(get_conversation_history(manager))
        conversation.append({'role': 'user', 'content': user_input})

        aligned_response = client.generate(
            messages=conversation,
            max_tokens=MAX_TOKENS_GREEN,
            temperature=0.5
        )

        logger.info(f"Generated aligned response ({len(aligned_response)} chars)")
        return aligned_response

    except Exception as e:
        logger.error(f"Failed to regenerate aligned response: {e}")
        return None


def generate_redirect_response(
    manager,
    user_input: str,
    turn_number: int,
    zone: str,
    max_tokens: int,
    user_input_fidelity: float
) -> Dict:
    """
    Generate a PROPORTIONALLY-GOVERNED redirect response for drifted topics.

    Math governs semantics:
    - Intervention strength = K_attractor * error_signal (continuous 0.0-1.0)
    - Prompt language interpolates based on exact strength

    Args:
        manager: BetaResponseManager instance
        user_input: The user's message
        turn_number: Current turn number
        zone: Fidelity zone (YELLOW, ORANGE, RED)
        max_tokens: Maximum response length
        user_input_fidelity: Pre-calculated fidelity score

    Returns:
        Dict with redirect response and intervention metrics
    """
    try:
        from telos_observatory.services.mistral_client import get_cached_mistral_client
        client = get_cached_mistral_client()

        pa_data = st.session_state.get('primacy_attractor', {})
        purpose_raw = pa_data.get('purpose', 'your stated goals')
        purpose = ' '.join(purpose_raw) if isinstance(purpose_raw, list) else purpose_raw

        # Proportional control
        K_ATTRACTOR = 1.5
        error_signal = 1.0 - user_input_fidelity
        intervention_strength = min(K_ATTRACTOR * error_signal, 1.0)

        logger.info(f"Proportional Control: Fidelity={user_input_fidelity:.3f}, "
                   f"Error={error_signal:.3f}, Strength={intervention_strength:.3f}")

        redirect_prompt = build_redirect_prompt(
            fidelity=user_input_fidelity,
            strength=intervention_strength,
            purpose=purpose,
            zone=zone
        )

        from telos_observatory.services.turn_storage_service import get_conversation_history
        conversation = [{'role': 'system', 'content': redirect_prompt}]
        conversation.extend(get_conversation_history(manager))
        conversation.append({'role': 'user', 'content': user_input})

        logger.info(f"Generating redirect response (strength={intervention_strength:.2f}, zone={zone}, max_tokens={max_tokens})")

        response = client.generate(
            messages=conversation,
            max_tokens=max_tokens,
            temperature=0.7
        )

        logger.info(f"Redirect response generated: {len(response)} chars")

        # Compute AI Fidelity for intervention response
        ai_fidelity = None
        primacy_state = None
        ai_response_realigned = False
        original_ai_fidelity = None
        realignment_attempts = 0

        if manager.st_embedding_provider and manager.st_user_pa_embedding is not None:
            response_embedding = np.array(manager.st_embedding_provider.encode(response))

            # Store in context buffer
            if manager.adaptive_context_manager and hasattr(manager.adaptive_context_manager, 'context_buffer'):
                manager.adaptive_context_manager.context_buffer.add_ai_response(response, response_embedding)

            # DUAL-REFERENCE AI FIDELITY
            ai_pa_embedding = getattr(manager, 'st_ai_pa_embedding', None)
            if ai_pa_embedding is None:
                ai_pa_embedding = manager.st_user_pa_embedding
            raw_ai_fidelity_to_pa = cosine_similarity(response_embedding, ai_pa_embedding)

            user_query_embedding = np.array(manager.st_embedding_provider.encode(user_input))
            raw_ai_fidelity_to_query = cosine_similarity(response_embedding, user_query_embedding)

            if raw_ai_fidelity_to_pa >= raw_ai_fidelity_to_query:
                ai_fidelity = normalize_ai_response_fidelity(raw_ai_fidelity_to_pa)
                winning_ref = "AI_PA"
            else:
                ai_fidelity = normalize_ai_response_fidelity(raw_ai_fidelity_to_query)
                winning_ref = "Query"

            logger.info(f"Intervention AI Fidelity (dual-ref): AI_PA={raw_ai_fidelity_to_pa:.3f}, "
                       f"Query={raw_ai_fidelity_to_query:.3f}, Winner={winning_ref} -> {ai_fidelity:.3f}")

            # AI response realignment in intervention zone
            INTERVENTION_MAX_REALIGNMENT_ATTEMPTS = 2
            original_ai_fidelity = ai_fidelity

            if ai_fidelity is not None and ai_fidelity < DISPLAY_GREEN_THRESHOLD:
                logger.warning(f"INTERVENTION AI DRIFT DETECTED: AI fidelity {ai_fidelity:.3f} < {DISPLAY_GREEN_THRESHOLD:.2f}")

                best_response = response
                best_embedding = response_embedding
                best_fidelity = ai_fidelity

                while ai_fidelity < DISPLAY_GREEN_THRESHOLD and realignment_attempts < INTERVENTION_MAX_REALIGNMENT_ATTEMPTS:
                    realignment_attempts += 1
                    logger.info(f"Intervention realignment attempt {realignment_attempts}/{INTERVENTION_MAX_REALIGNMENT_ATTEMPTS}...")

                    aligned_response = regenerate_aligned_response(
                        manager=manager,
                        user_input=user_input,
                        drifted_response=response,
                        ai_fidelity=ai_fidelity,
                        user_fidelity=user_input_fidelity,
                        previous_aligned_response=None
                    )

                    if aligned_response:
                        new_embedding = np.array(manager.st_embedding_provider.encode(aligned_response))
                        new_raw_ai_fidelity = cosine_similarity(new_embedding, ai_pa_embedding)
                        new_ai_fidelity = normalize_ai_response_fidelity(new_raw_ai_fidelity)

                        logger.info(f"Intervention realigned AI Fidelity: {ai_fidelity:.3f} -> {new_ai_fidelity:.3f} (attempt {realignment_attempts})")

                        if new_ai_fidelity > best_fidelity:
                            best_response = aligned_response
                            best_embedding = new_embedding
                            best_fidelity = new_ai_fidelity

                        if new_ai_fidelity > ai_fidelity:
                            response = aligned_response
                            response_embedding = new_embedding
                            ai_fidelity = new_ai_fidelity
                            ai_response_realigned = True

                            if ai_fidelity >= DISPLAY_GREEN_THRESHOLD:
                                break
                    else:
                        logger.warning(f"Intervention realignment attempt {realignment_attempts} failed")

                if best_fidelity > original_ai_fidelity:
                    response = best_response
                    ai_fidelity = best_fidelity
                    ai_response_realigned = True

            # Calculate Primacy State
            if ai_fidelity is not None:
                epsilon = 1e-10
                primacy_state = (2 * user_input_fidelity * ai_fidelity) / (user_input_fidelity + ai_fidelity + epsilon)
                logger.info(f"Intervention PS: F_user={user_input_fidelity:.3f}, F_ai={ai_fidelity:.3f}, PS={primacy_state:.3f}")

        telos_data = {
            'response': response,
            'fidelity_score': user_input_fidelity,
            'distance_from_pa': error_signal,
            'intervention_triggered': True,
            'intervention_type': f'proportional_redirect' + ('_realigned' if ai_response_realigned else ''),
            'intervention_reason': f'Strength {intervention_strength:.2f} redirect ({zone} zone)',
            'drift_detected': True,
            'in_basin': False,
            'user_pa_fidelity': user_input_fidelity,
            'ai_pa_fidelity': ai_fidelity,
            'primacy_state_score': primacy_state,
            'redirect_zone': zone,
            'intervention_strength': intervention_strength,
            'error_signal': error_signal,
            'max_tokens_used': max_tokens,
            'ai_response_realigned': ai_response_realigned,
            'original_ai_fidelity': original_ai_fidelity if ai_response_realigned else None,
            'realignment_attempts': realignment_attempts if ai_response_realigned else 0,
        }

        return telos_data

    except Exception as e:
        logger.error(f"Error generating redirect response: {e}")
        fallback = "Let's refocus on what you came here to accomplish. How can I help you with your original goals?"
        return {
            'response': fallback,
            'fidelity_score': user_input_fidelity,
            'error': str(e),
            'user_pa_fidelity': user_input_fidelity,
        }


def build_redirect_prompt(
    fidelity: float,
    strength: float,
    purpose: str,
    zone: str = None
) -> str:
    """
    Build a PROPORTIONALLY-GOVERNED redirect prompt using the Semantic Interpreter.

    Two focal points:
      1. Fidelity Value - where we are on the alignment spectrum
      2. Purpose - what we're maintaining (the semantic anchor)

    Args:
        fidelity: Raw fidelity score (continuous 0.0-1.0)
        strength: Calculated intervention strength
        purpose: User's established purpose
        zone: Fidelity zone for logging

    Returns:
        System prompt with concrete linguistic specifications
    """
    spec = semantic_interpret(fidelity, purpose)

    steward_prompt = get_intervention_prompt(
        fidelity=fidelity,
        user_context=purpose,
        green_threshold=FIDELITY_GREEN
    )

    linguistic_spec = spec.to_prompt_block(purpose)

    return f"""{steward_prompt}

LINGUISTIC GUIDELINES:
{linguistic_spec}

CRITICAL INSTRUCTIONS:
- Never use stock phrases like "far from your stated purpose" or "here's the path back"
- Be natural and conversational - sound like a human, not a governance system
- Keep responses concise (2-3 sentences unless more detail is genuinely needed)
- Use the linguistic form specified above ({spec.sentence_form})"""


def generate_steward_interpretation(
    telos_data: Dict,
    shown_source: str,
    turn_number: int,
    use_rescaled_fidelity: bool,
    focus_shifted: bool = False
) -> str:
    """
    Generate Steward's human-readable interpretation.

    Args:
        telos_data: TELOS analysis data
        shown_source: What was actually shown ('telos', 'native', 'both')
        turn_number: Current turn
        use_rescaled_fidelity: Whether using SentenceTransformer mode
        focus_shifted: Whether the PA was shifted just before this turn

    Returns:
        Human-readable interpretation
    """
    fidelity = telos_data.get('fidelity_score', 0.0)
    intervention = telos_data.get('intervention_triggered', False)
    reason = telos_data.get('intervention_reason', '')

    interpretation = f"**Turn {turn_number} Analysis:**\n\n"

    if focus_shifted:
        interpretation += "**Focus Changed:** You shifted your focus to a new topic at this turn. "
        interpretation += "The conversation is now being measured against your new purpose.\n\n"

    if shown_source == 'native':
        interpretation += "**Response Type:** Native (no TELOS governance)\n"
        interpretation += "This response was generated without TELOS intervention.\n\n"
    elif shown_source == 'telos':
        interpretation += "**Response Type:** TELOS-governed\n"
    else:
        interpretation += "**Response Type:** Both shown for comparison\n\n"

    thresholds = get_thresholds(use_rescaled_fidelity)
    t_green, t_yellow, t_orange = thresholds['green'], thresholds['yellow'], thresholds['orange']

    if fidelity >= t_green:
        interpretation += f"**Alignment:** Aligned ({fidelity:.3f})\n"
        interpretation += "The conversation remains well-aligned with your stated purpose.\n\n"
    elif fidelity >= t_yellow:
        interpretation += f"**Alignment:** Minor Drift ({fidelity:.3f})\n"
        interpretation += "Slight deviation from your purpose, but within acceptable bounds.\n\n"
    elif fidelity >= t_orange:
        interpretation += f"**Alignment:** Drift Detected ({fidelity:.3f})\n"
        interpretation += "Noticeable departure from your stated goals.\n\n"
    else:
        interpretation += f"**Alignment:** Significant Drift ({fidelity:.3f})\n"
        interpretation += "Significant misalignment with your purpose.\n\n"

    if shown_source in ['telos', 'both']:
        if intervention:
            interpretation += f"**TELOS Intervention:** Applied\n"
            interpretation += f"**Reason:** {reason}\n\n"
            interpretation += "TELOS detected drift and modified the response to maintain alignment.\n"
        else:
            interpretation += "**TELOS Monitoring:** No intervention needed\n"
            interpretation += "The response naturally aligned with your purpose.\n"
    else:
        if intervention:
            interpretation += "**What TELOS would have done:**\n"
            interpretation += f"Would have intervened due to: {reason}\n"
        else:
            interpretation += "**What TELOS would have done:**\n"
            interpretation += "No intervention would have been needed.\n"

    return interpretation

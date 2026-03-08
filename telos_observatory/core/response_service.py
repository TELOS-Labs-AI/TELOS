"""
Response Service
================

Response generation, streaming, and TELOS metric computation.
Extracted from state_manager.py to separate concerns.
"""

import logging
from typing import Dict, Any, List

import streamlit as st

from telos_core.constants import FIDELITY_GREEN, FIDELITY_YELLOW, FIDELITY_ORANGE

logger = logging.getLogger(__name__)


# ============================================================================
# Fidelity Zone Classification
# ============================================================================

def _classify_fidelity(fidelity: float) -> tuple:
    """
    Classify fidelity into status icon and text.

    Uses thresholds from telos_core.constants (single source of truth).

    Returns:
        Tuple of (status_icon, status_text).
    """
    if fidelity >= FIDELITY_GREEN:
        return ("✓", "Aligned")
    elif fidelity >= FIDELITY_YELLOW:
        return ("✓", "Minor Drift")
    elif fidelity >= FIDELITY_ORANGE:
        return ("⚠", "Drift Detected")
    else:
        return ("⚠", "Significant Drift")


def _compute_ps_metrics(steward, full_response: str, ps_calculator):
    """
    Compute Primacy State metrics for a response.

    Returns:
        PS metrics dict or None on failure.
    """
    if not ps_calculator or not hasattr(steward, 'embedding_provider'):
        return None

    try:
        embedding_provider = steward.embedding_provider
        response_embedding = embedding_provider.encode(full_response)

        attractor = steward.attractor
        user_pa_text = " ".join(attractor.purpose)
        ai_pa_text = " ".join(attractor.boundaries) if attractor.boundaries else user_pa_text

        user_pa_embedding = embedding_provider.encode(user_pa_text)
        ai_pa_embedding = embedding_provider.encode(ai_pa_text)

        ps_result = ps_calculator.compute_primacy_state(
            response_embedding=response_embedding,
            user_pa_embedding=user_pa_embedding,
            ai_pa_embedding=ai_pa_embedding
        )

        return ps_result.to_dict()
    except Exception as e:
        logger.debug(f"PS calculation failed: {e}")
        return None


def _ensure_ps_calculator(state_manager):
    """Ensure PS calculator is initialized on the state manager."""
    if state_manager._ps_calculator is None:
        try:
            from telos_core.primacy_state import PrimacyStateCalculator
            state_manager._ps_calculator = PrimacyStateCalculator(track_energy=True)
            logger.info("PS calculator initialized")
        except ImportError as e:
            logger.debug(f"PS module not available: {e}")


def _build_conversation_history(turns, message, system_prompt, exclude_idx=None):
    """
    Build conversation history list for LLM context.

    Args:
        turns: List of turn dicts.
        message: Current user message.
        system_prompt: System prompt string.
        exclude_idx: Optional turn index to exclude (for streaming).
    """
    history = [{"role": "system", "content": system_prompt}]

    for i, turn in enumerate(turns):
        if exclude_idx is not None and i >= exclude_idx:
            break
        if turn.get('is_loading', False) or turn.get('is_streaming', False):
            continue
        if not turn.get('response'):
            continue
        history.append({"role": "user", "content": turn.get('user_input', '')})
        history.append({"role": "assistant", "content": turn.get('response', '')})

    history.append({"role": "user", "content": message})
    return history


def _get_system_prompt(demo_mode: bool, corpus_loader, message: str):
    """
    Build system prompt, optionally with RAG context.

    Returns:
        Tuple of (system_prompt, retrieved_context).
    """
    retrieved_context = ""

    if demo_mode and corpus_loader:
        try:
            from telos_observatory.demo_mode.telos_corpus_loader import format_context_for_llm
            chunks = corpus_loader.retrieve(message, top_k=3)
            retrieved_context = format_context_for_llm(chunks)
            logger.info(f"Retrieved {len(chunks)} corpus chunks for context")
        except Exception as e:
            logger.warning(f"Corpus retrieval failed: {e}")

    if demo_mode:
        from telos_observatory.demo_mode.telos_framework_demo import get_demo_system_prompt
        base_prompt = get_demo_system_prompt()
        if retrieved_context:
            return (
                f"{retrieved_context}\n\n{base_prompt}\n\n"
                "IMPORTANT: Use the documentation context above to provide accurate, grounded responses.",
                retrieved_context
            )
        return base_prompt, retrieved_context
    else:
        return (
            "You are a helpful AI assistant. Engage naturally with the user's questions and topics.\n\n"
            "Be informative, conversational, and adapt to what the user wants to discuss.",
            retrieved_context
        )


def _apply_turn_update(state_manager, turn_idx, response_text, fidelity, distance,
                       intervention_applied, in_basin, status_icon, status_text,
                       ps_metrics=None, is_streaming=False):
    """Apply response data and metrics to a turn in state."""
    turn_update = {
        'response': response_text,
        'fidelity': fidelity,
        'distance': distance,
        'intervention_applied': intervention_applied,
        'drift_detected': fidelity < FIDELITY_GREEN,
        'status': status_icon,
        'status_text': status_text,
        'in_basin': in_basin,
        'is_loading': False,
    }

    if is_streaming:
        turn_update['is_streaming'] = False

    if ps_metrics:
        turn_update['ps_metrics'] = ps_metrics
        turn_update['primacy_state_score'] = ps_metrics.get('ps_score')
        turn_update['primacy_state_condition'] = ps_metrics.get('condition')
        turn_update['user_pa_fidelity'] = ps_metrics.get('f_user')
        turn_update['ai_pa_fidelity'] = ps_metrics.get('f_ai')
        turn_update['pa_correlation'] = ps_metrics.get('rho_pa')
        turn_update['v_dual_energy'] = ps_metrics.get('v_dual')
        turn_update['delta_v_dual'] = ps_metrics.get('delta_v')
        turn_update['primacy_converging'] = ps_metrics.get('converging')

    state_manager.state.turns[turn_idx].update(turn_update)
    state_manager.update_statistics()


# ============================================================================
# Main Response Generation (non-streaming)
# ============================================================================

def add_user_message(state_manager, message: str):
    """Add a new user message and generate a TELOS-governed response."""
    from telos_observatory.core.llm_service import initialize_telos_steward

    # Check if already processing (rerun after placeholder)
    already_processing = False
    if state_manager.state.turns and state_manager.state.turns[-1].get('is_loading', False):
        already_processing = True
        current_turn_idx = len(state_manager.state.turns) - 1

    if not already_processing:
        placeholder_turn = {
            'turn': state_manager.state.total_turns,
            'timestamp': state_manager.state.total_turns * 2.5,
            'user_input': message,
            'response': '',
            'fidelity': None,
            'distance': None,
            'threshold': FIDELITY_GREEN,
            'intervention_applied': False,
            'drift_detected': False,
            'status': "...",
            'status_text': "Processing",
            'in_basin': True,
            'phase2_comparison': None,
            'is_loading': True
        }
        state_manager.state.turns.append(placeholder_turn)
        state_manager.state.total_turns += 1
        state_manager.state.current_turn = state_manager.state.total_turns - 1
        st.rerun()

    try:
        # Initialize TELOS if needed
        if not hasattr(state_manager, '_telos_steward'):
            demo_mode = st.session_state.get('telos_demo_mode', False)
            steward, corpus_loader = initialize_telos_steward(
                state_manager,
                demo_mode=demo_mode,
                enable_interventions=True
            )
            state_manager._telos_steward = steward
            state_manager._corpus_loader = corpus_loader

        if state_manager._telos_steward is None:
            raise Exception("TELOS engine not initialized")

        demo_mode = st.session_state.get('telos_demo_mode', False)
        corpus_loader = getattr(state_manager, '_corpus_loader', None)

        system_prompt, _ = _get_system_prompt(demo_mode, corpus_loader, message)
        conversation_history = _build_conversation_history(
            state_manager.state.turns, message, system_prompt
        )

        max_tokens = 350 if demo_mode else 500

        # Generate response
        response_text = state_manager._telos_steward.llm_client.generate(
            messages=conversation_history,
            max_tokens=max_tokens
        )

        # Process through TELOS
        result = state_manager._telos_steward.process_turn(
            user_input=message,
            model_response=response_text
        )

        fidelity = result.get("telic_fidelity", 0.0)
        distance = result.get("error_signal", 0.0)
        in_basin = result.get("in_basin", True)
        intervention_applied = result.get("intervention_applied", False)

        _ensure_ps_calculator(state_manager)
        ps_metrics = _compute_ps_metrics(
            state_manager._telos_steward, response_text, state_manager._ps_calculator
        )

        status_icon, status_text = _classify_fidelity(fidelity)

    except Exception as e:
        logger.error(f"Error generating response: {type(e).__name__}: {str(e)}", exc_info=True)

        # Fallback responses
        message_lower = message.lower()
        if "telos" in message_lower or "work" in message_lower:
            response_text = "TELOS is a purpose alignment framework that keeps AI conversations focused on their intended goals."
        elif "fidelity" in message_lower or "score" in message_lower:
            response_text = "Fidelity scores measure how well responses align with your purpose."
        else:
            response_text = "I'm designed to help explain TELOS governance. Could you rephrase your question?"

        fidelity = 0.0
        distance = 0.0
        in_basin = True
        intervention_applied = False
        ps_metrics = None
        status_icon, status_text = "✓", "Good"

    if not already_processing:
        current_turn_idx = len(state_manager.state.turns) - 1

    _apply_turn_update(
        state_manager, current_turn_idx, response_text,
        fidelity, distance, intervention_applied, in_basin,
        status_icon, status_text, ps_metrics
    )


# ============================================================================
# Streaming Response Generation
# ============================================================================

def add_user_message_streaming(state_manager, message: str) -> int:
    """Add user message and prepare for streaming. Returns turn_index."""
    new_turn = {
        'turn': state_manager.state.total_turns,
        'timestamp': state_manager.state.total_turns * 2.5,
        'user_input': message,
        'response': '',
        'fidelity': None,
        'distance': None,
        'threshold': FIDELITY_GREEN,
        'intervention_applied': False,
        'drift_detected': False,
        'status': "...",
        'status_text': "Streaming",
        'in_basin': True,
        'phase2_comparison': None,
        'is_streaming': True
    }

    state_manager.state.turns.append(new_turn)
    state_manager.state.total_turns += 1
    state_manager.state.current_turn = state_manager.state.total_turns - 1
    return state_manager.state.current_turn


def generate_response_stream(state_manager, message: str, turn_idx: int):
    """Generator that yields response chunks for streaming display."""
    from telos_observatory.core.llm_service import initialize_telos_steward

    logger.info(f"generate_response_stream() called for turn {turn_idx}")

    # BETA MODE ROUTER
    active_tab = st.session_state.get('active_tab', 'DEMO')
    pa_established = st.session_state.get('pa_established', False)

    if active_tab == 'BETA' and pa_established:
        logger.info(f"BETA MODE - Routing to BetaResponseManager for turn {turn_idx}")
        yield from _generate_beta_stream(state_manager, message, turn_idx)
        return

    # Initialize TELOS if needed
    if not hasattr(state_manager, '_telos_steward'):
        demo_mode = st.session_state.get('telos_demo_mode', False)
        pa_data = st.session_state.get('primacy_attractor')
        pa_est = st.session_state.get('pa_established', False)

        try:
            steward, corpus_loader = initialize_telos_steward(
                state_manager,
                demo_mode=demo_mode,
                pa_data=pa_data,
                pa_established=pa_est,
                enable_interventions=not demo_mode and pa_est
            )
            state_manager._telos_steward = steward
            state_manager._corpus_loader = corpus_loader

            if not demo_mode and pa_est:
                state_manager.state.pa_converged = True

        except Exception as init_error:
            logger.error(f"Failed to initialize TELOS engine: {init_error}")
            state_manager._telos_steward = None
            state_manager._corpus_loader = None
            yield "I apologize, but I'm having trouble initializing. Please try again."
            return

    demo_mode = st.session_state.get('telos_demo_mode', False)
    corpus_loader = getattr(state_manager, '_corpus_loader', None)

    system_prompt, _ = _get_system_prompt(demo_mode, corpus_loader, message)
    conversation_history = _build_conversation_history(
        state_manager.state.turns, message, system_prompt, exclude_idx=turn_idx
    )

    max_tokens = 350 if demo_mode else 500

    # Generate response
    full_response = ""
    try:
        full_response = state_manager._telos_steward.llm_client.generate(
            messages=conversation_history,
            max_tokens=max_tokens
        )
        yield full_response
    except Exception as gen_error:
        logger.error(f"Generation error: {gen_error}", exc_info=True)
        full_response = "I apologize, but I encountered an error generating a response. Please try again."
        yield full_response

    # Process through TELOS for metrics
    try:
        result = state_manager._telos_steward.process_turn(
            user_input=message,
            model_response=full_response
        )

        fidelity = result.get("telic_fidelity", 0.0)
        distance = result.get("error_signal", 0.0)
        in_basin = result.get("in_basin", True)
        intervention_applied = result.get("intervention_applied", False)

        _ensure_ps_calculator(state_manager)
        ps_metrics = _compute_ps_metrics(
            state_manager._telos_steward, full_response, state_manager._ps_calculator
        )

        status_icon, status_text = _classify_fidelity(fidelity)

    except Exception as telos_error:
        logger.error(f"TELOS processing error: {telos_error}")
        fidelity = 0.0
        distance = 0.0
        in_basin = True
        intervention_applied = False
        ps_metrics = None
        status_icon, status_text = "✓", "Good"

    _apply_turn_update(
        state_manager, turn_idx, full_response,
        fidelity, distance, intervention_applied, in_basin,
        status_icon, status_text, ps_metrics, is_streaming=True
    )


# ============================================================================
# Beta Stream Generation
# ============================================================================

def _generate_beta_stream(state_manager, message: str, turn_idx: int):
    """Generate response for BETA mode using BetaResponseManager."""
    logger.info(f"_generate_beta_stream() entered for turn {turn_idx}")

    try:
        # Initialize BetaResponseManager if needed
        needs_reinit = 'beta_response_manager' not in st.session_state
        if not needs_reinit:
            mgr = st.session_state.beta_response_manager
            if mgr.telos_engine and (mgr.user_pa_embedding is None or mgr.ai_pa_embedding is None):
                logger.warning("Stale BetaResponseManager detected - forcing re-init")
                needs_reinit = True
                del st.session_state['beta_response_manager']

        if needs_reinit:
            from telos_observatory.services.beta_response_manager import BetaResponseManager
            backend = st.session_state.get('backend')
            st.session_state.beta_response_manager = BetaResponseManager(state_manager, backend)

        beta_sequence = st.session_state.get('beta_sequence', {})
        turn_number = st.session_state.get('beta_current_turn', 1)

        response_data = st.session_state.beta_response_manager.generate_turn_responses(
            user_input=message,
            turn_number=turn_number,
            sequence=beta_sequence
        )

        shown_response = response_data.get('shown_response', '')
        shown_source = response_data.get('shown_source', 'unknown')
        telos_analysis = response_data.get('telos_analysis', {})

        yield shown_response

        # Update turn with metrics
        turn = state_manager.state.turns[turn_idx]
        turn['response'] = shown_response
        turn['fidelity'] = telos_analysis.get('user_pa_fidelity') or telos_analysis.get('fidelity_score') or 0.0
        turn['distance'] = telos_analysis.get('distance_from_pa', 0.0)
        turn['intervention_applied'] = telos_analysis.get('intervention_triggered', False)
        turn['drift_detected'] = telos_analysis.get('drift_detected', False)
        turn['in_basin'] = telos_analysis.get('in_basin', True)
        turn['is_streaming'] = False
        turn['is_loading'] = False
        turn['beta_shown_source'] = shown_source
        turn['beta_test_type'] = response_data.get('test_type', 'unknown')

        if response_data.get('comparison_mode', False):
            turn['comparison_mode'] = True
            turn['response_a'] = response_data.get('response_a', '')
            turn['response_b'] = response_data.get('response_b', '')
            turn['beta_data'] = {
                'telos_fidelity': telos_analysis.get('fidelity_score', 0.0),
                'comparison_mode': True
            }
        else:
            turn['beta_data'] = {
                'telos_fidelity': telos_analysis.get('fidelity_score', 0.0),
                'shown_response_source': shown_source
            }

        st.session_state.beta_current_turn = turn_number + 1
        logger.info(f"BETA Turn {turn_number} complete - Next turn: {turn_number + 1}")

    except Exception as e:
        logger.error(f"BETA stream generation failed: {e}", exc_info=True)
        fallback_response = "I apologize, but I encountered an error in BETA mode. Please try again."
        yield fallback_response

        turn = state_manager.state.turns[turn_idx]
        turn['response'] = fallback_response
        turn['fidelity'] = 0.0
        turn['is_streaming'] = False
        turn['is_loading'] = False
        turn['error'] = str(e)

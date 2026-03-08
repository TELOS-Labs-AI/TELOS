"""
Fidelity Service - Two-Layer Drift Detection for TELOS Observatory
===================================================================

Extracted from BetaResponseManager to provide focused fidelity calculation.

Handles:
- Two-layer fidelity calculation (baseline pre-filter + basin membership)
- Adaptive context integration (SCI - Semantic Continuity Inheritance)
- Model-specific threshold selection (SentenceTransformer vs Mistral)
- AI response fidelity measurement (dual-reference)
- Primacy State computation (harmonic mean of F_user and F_ai)
"""

import logging
import numpy as np
import streamlit as st
from typing import Dict, Optional, Tuple

from telos_core.constants import (
    FIDELITY_GREEN, FIDELITY_YELLOW, FIDELITY_ORANGE, FIDELITY_RED,
    SIMILARITY_BASELINE as CONSTANTS_SIMILARITY_BASELINE,
    INTERVENTION_THRESHOLD as CONSTANTS_INTERVENTION_THRESHOLD,
    ST_FIDELITY_GREEN, ST_FIDELITY_YELLOW, ST_FIDELITY_ORANGE, ST_FIDELITY_RED,
)

from telos_observatory.services.fidelity_display import (
    normalize_fidelity_for_display,
    normalize_st_fidelity,
    normalize_ai_response_fidelity,
)

logger = logging.getLogger(__name__)

# Local aliases for backward compatibility
SIMILARITY_BASELINE = CONSTANTS_SIMILARITY_BASELINE  # 0.20 - Layer 1 hard block
INTERVENTION_THRESHOLD = CONSTANTS_INTERVENTION_THRESHOLD  # 0.48 - Layer 2 threshold

# Display threshold for AI fidelity checks
DISPLAY_GREEN_THRESHOLD = 0.70


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


def get_thresholds(use_rescaled_fidelity: bool) -> dict:
    """
    Get model-appropriate fidelity thresholds.

    Returns thresholds based on embedding model:
    - SentenceTransformer (template mode): Raw thresholds from ST calibration
    - Mistral (custom PA mode): Goldilocks zone thresholds

    Args:
        use_rescaled_fidelity: True if using SentenceTransformer template mode

    Returns:
        Dict with 'green', 'yellow', 'orange', 'red' threshold values
    """
    if use_rescaled_fidelity:
        return {
            'green': ST_FIDELITY_GREEN,
            'yellow': ST_FIDELITY_YELLOW,
            'orange': ST_FIDELITY_ORANGE,
            'red': ST_FIDELITY_RED
        }
    else:
        return {
            'green': FIDELITY_GREEN,
            'yellow': FIDELITY_YELLOW,
            'orange': FIDELITY_ORANGE,
            'red': 0.50
        }


def get_fidelity_level(fidelity: float, use_rescaled_fidelity: bool) -> str:
    """Get human-readable fidelity level using dynamic thresholds."""
    thresholds = get_thresholds(use_rescaled_fidelity)
    t_green, t_yellow, t_orange = thresholds['green'], thresholds['yellow'], thresholds['orange']

    if fidelity >= t_green:
        return "green"
    elif fidelity >= t_yellow:
        return "yellow"
    elif fidelity >= t_orange:
        return "orange"
    else:
        return "red"


def calculate_user_fidelity(manager, user_input: str, use_context: bool = True) -> tuple:
    """
    Calculate fidelity of user input relative to their PA using TWO-LAYER architecture.

    This is the FIRST calculation - before any response generation.

    CONTEXT-AWARE FIDELITY:
    - When use_context=True, prepends recent conversation history to user input
    - This allows queries that are contextually related to be recognized

    TEMPLATE MODE (SentenceTransformer + Rescaling):
    - Uses SentenceTransformer for better off-topic discrimination

    STANDARD MODE (Mistral):
    - LAYER 1: Baseline Pre-Filter (raw_sim < 0.50 triggers HARD_BLOCK)
    - LAYER 2: TELOS Primacy State (fidelity = raw cosine similarity)

    Args:
        manager: BetaResponseManager instance (provides embedding providers and PA embeddings)
        user_input: The user's message
        use_context: Whether to include conversation context (default: True)

    Returns:
        tuple: (fidelity, raw_similarity, baseline_hard_block)
    """
    try:
        # Ensure TELOS engine is initialized
        if not manager.telos_engine:
            manager._initialize_telos_engine()

        # PRE-LOAD SESSION STATE EMBEDDINGS (CRITICAL FOR ADAPTIVE CONTEXT)
        if 'use_rescaled_fidelity_mode' in st.session_state and st.session_state.use_rescaled_fidelity_mode:
            manager.use_rescaled_fidelity = True
            if not manager.st_embedding_provider:
                from telos_core.embedding_provider import get_cached_minilm_provider
                manager.st_embedding_provider = get_cached_minilm_provider()
                logger.info(f"   SentenceTransformer (cached): {manager.st_embedding_provider.dimension} dims")
            if not hasattr(manager, 'st_user_pa_embedding') and 'cached_st_user_pa_embedding' in st.session_state:
                manager.st_user_pa_embedding = st.session_state.cached_st_user_pa_embedding
                logger.info(f"   Pre-loaded ST PA embedding for adaptive context: {len(manager.st_user_pa_embedding)} dims")

        # ADAPTIVE CONTEXT SYSTEM: Phase-aware, pattern-classified context
        has_st_pa = hasattr(manager, 'st_user_pa_embedding') and manager.st_user_pa_embedding is not None
        has_mistral_pa = hasattr(manager, 'user_pa_embedding') and manager.user_pa_embedding is not None
        has_pa_embedding = has_st_pa or has_mistral_pa

        logger.warning(f"[SCI DEBUG] adaptive_context_enabled={manager.adaptive_context_enabled}, "
                      f"adaptive_context_manager={manager.adaptive_context_manager is not None}, "
                      f"has_st_pa={has_st_pa}, has_mistral_pa={has_mistral_pa}, "
                      f"has_pa_embedding={has_pa_embedding}")

        if manager.adaptive_context_enabled and manager.adaptive_context_manager and has_pa_embedding:
            try:
                pa_embedding = getattr(manager, 'st_user_pa_embedding', None)
                if pa_embedding is None:
                    pa_embedding = manager.user_pa_embedding

                if manager.st_embedding_provider:
                    input_embedding = np.array(manager.st_embedding_provider.encode(user_input))
                elif manager.embedding_provider:
                    input_embedding = np.array(manager.embedding_provider.encode(user_input))
                else:
                    raise ValueError("No embedding provider available")

                raw_fidelity = cosine_similarity(input_embedding, pa_embedding)

                adaptive_result = manager.adaptive_context_manager.process_message(
                    user_input=user_input,
                    input_embedding=input_embedding,
                    pa_embedding=pa_embedding,
                    raw_fidelity=raw_fidelity,
                    base_threshold=INTERVENTION_THRESHOLD
                )

                manager.last_adaptive_context_result = adaptive_result

                logger.info(f"ADAPTIVE CONTEXT: type={adaptive_result.message_type.name}, "
                           f"phase={adaptive_result.phase.name}, "
                           f"raw={raw_fidelity:.3f} -> adjusted={adaptive_result.adjusted_fidelity:.3f}, "
                           f"threshold={adaptive_result.adaptive_threshold:.3f}, "
                           f"intervene={adaptive_result.should_intervene}")

                fidelity = adaptive_result.adjusted_fidelity
                raw_similarity = raw_fidelity
                baseline_hard_block = raw_fidelity < SIMILARITY_BASELINE

                # SCI INTEGRATION: Store user input embedding for set_previous_turn()
                manager.last_user_input_embedding = input_embedding

                return (fidelity, raw_similarity, baseline_hard_block)

            except Exception as e:
                logger.warning(f"Adaptive context failed, falling back to legacy: {e}")

        # DEPRECATED: LEGACY CONTEXT-AWARE FIDELITY (Exception Fallback Only)
        contextual_input = user_input
        if use_context:
            from telos_observatory.services.turn_storage_service import get_recent_context_for_fidelity
            recent_context = get_recent_context_for_fidelity(manager)
            if recent_context:
                contextual_input = f"[Context: {recent_context}] | {user_input}"
                logger.info(f"Legacy context-aware fidelity: added {len(recent_context)} chars of context")

        # TEMPLATE MODE: SentenceTransformer + Raw Thresholds (Clean Lane)
        if manager.use_rescaled_fidelity and manager.st_embedding_provider and hasattr(manager, 'st_user_pa_embedding'):
            from telos_core.constants import ST_FIDELITY_GREEN, ST_FIDELITY_RED

            user_embedding = np.array(manager.st_embedding_provider.encode(contextual_input))
            raw_similarity = cosine_similarity(user_embedding, manager.st_user_pa_embedding)
            fidelity = raw_similarity
            baseline_hard_block = raw_similarity < ST_FIDELITY_RED

            if baseline_hard_block:
                logger.warning(f"TEMPLATE MODE HARD_BLOCK: raw_sim={raw_similarity:.3f} < {ST_FIDELITY_RED}")
            else:
                logger.info(f"Template Mode PASS: raw_sim={raw_similarity:.3f}")

            logger.info(f"TEMPLATE MODE Fidelity (raw): {fidelity:.3f}")
            return (fidelity, raw_similarity, baseline_hard_block)

        # STANDARD MODE: Use local SentenceTransformer for FAST embedding
        if manager.st_embedding_provider and hasattr(manager, 'st_user_pa_embedding') and manager.st_user_pa_embedding is not None:
            user_embedding = np.array(manager.st_embedding_provider.encode(contextual_input))
            raw_similarity = cosine_similarity(user_embedding, manager.st_user_pa_embedding)
            logger.info(f"FAST PATH: ST embedding, raw_sim={raw_similarity:.3f}")
        elif not manager.embedding_provider or manager.user_pa_embedding is None:
            logger.warning("Embedding provider or PA not initialized - returning default fidelity")
            return (FIDELITY_GREEN, FIDELITY_GREEN, False)
        else:
            user_embedding = np.array(manager.embedding_provider.encode(contextual_input))
            raw_similarity = cosine_similarity(user_embedding, manager.user_pa_embedding)
            logger.info(f"SLOW PATH: Mistral API, raw_sim={raw_similarity:.3f}")

        # LAYER 1: Baseline Pre-Filter (extreme off-topic detection)
        baseline_hard_block = raw_similarity < SIMILARITY_BASELINE

        if baseline_hard_block:
            logger.warning(f"LAYER 1 HARD_BLOCK: raw_sim={raw_similarity:.3f} < baseline={SIMILARITY_BASELINE}")
        else:
            logger.info(f"Layer 1 PASS: raw_sim={raw_similarity:.3f} >= baseline={SIMILARITY_BASELINE}")

        # LAYER 2: TELOS Primacy State (fidelity = raw cosine similarity)
        fidelity = raw_similarity
        logger.info(f"Layer 2 Fidelity: {fidelity:.3f} (raw cosine similarity)")

        return (fidelity, raw_similarity, baseline_hard_block)

    except Exception as e:
        logger.error(f"Error calculating user fidelity: {e}")
        return (FIDELITY_GREEN, FIDELITY_GREEN, False)


def compute_ai_fidelity(
    manager,
    response_text: str,
    user_input: str,
    user_fidelity: float,
    zone: str = "GREEN"
) -> Tuple[Optional[float], Optional[float]]:
    """
    Compute AI response fidelity and Primacy State.

    Dual-reference approach:
    - GREEN zone: cosine(AI_response, USER_PA) for topical alignment
    - Intervention zone: MAX(cosine(AI_response, AI_PA), cosine(AI_response, query))

    Args:
        manager: BetaResponseManager instance
        response_text: AI response text to evaluate
        user_input: User's original message
        user_fidelity: Pre-calculated user fidelity
        zone: Current fidelity zone (GREEN, YELLOW, ORANGE, RED)

    Returns:
        Tuple of (ai_fidelity, primacy_state) - either may be None
    """
    ai_fidelity = None
    primacy_state = None

    if not manager.st_embedding_provider:
        logger.warning("AI fidelity check skipped - no ST embedding provider")
        return (None, None)

    try:
        response_embedding = np.array(manager.st_embedding_provider.encode(response_text))
        response_embedding = response_embedding / (np.linalg.norm(response_embedding) + 1e-10)

        # Store AI response in context buffer for future context matching
        if manager.adaptive_context_manager and hasattr(manager.adaptive_context_manager, 'context_buffer'):
            manager.adaptive_context_manager.context_buffer.add_ai_response(response_text, response_embedding)

        if zone == "GREEN":
            # GREEN zone: measure against USER_PA for topical alignment
            st_user_pa = getattr(manager, 'st_user_pa_embedding', None)
            if st_user_pa is None:
                return (None, None)

            raw_ai_fidelity = cosine_similarity(response_embedding, st_user_pa)
            ai_fidelity = normalize_ai_response_fidelity(raw_ai_fidelity)
            logger.warning(f"GREEN ZONE AI Fidelity: raw={raw_ai_fidelity:.3f} -> display={ai_fidelity:.3f}")
        else:
            # Intervention zone: dual-reference (AI_PA and user query)
            ai_pa_embedding = getattr(manager, 'st_ai_pa_embedding', None)
            if ai_pa_embedding is None:
                ai_pa_embedding = getattr(manager, 'st_user_pa_embedding', None)
            if ai_pa_embedding is None:
                return (None, None)

            raw_ai_fidelity_to_pa = cosine_similarity(response_embedding, ai_pa_embedding)
            user_query_embedding = np.array(manager.st_embedding_provider.encode(user_input))
            raw_ai_fidelity_to_query = cosine_similarity(response_embedding, user_query_embedding)

            if raw_ai_fidelity_to_pa >= raw_ai_fidelity_to_query:
                ai_fidelity = normalize_ai_response_fidelity(raw_ai_fidelity_to_pa)
                winning_ref = "AI_PA"
            else:
                ai_fidelity = normalize_ai_response_fidelity(raw_ai_fidelity_to_query)
                winning_ref = "Query"

            logger.info(f"AI Fidelity (dual-ref): AI_PA={raw_ai_fidelity_to_pa:.3f}, "
                       f"Query={raw_ai_fidelity_to_query:.3f}, Winner={winning_ref} -> {ai_fidelity:.3f}")

        # Compute Primacy State using harmonic mean
        if ai_fidelity is not None and user_fidelity is not None:
            epsilon = 1e-10
            primacy_state = (2 * user_fidelity * ai_fidelity) / (user_fidelity + ai_fidelity + epsilon)

    except Exception as e:
        logger.error(f"AI fidelity check failed: {e}")
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")

    return (ai_fidelity, primacy_state)


def compute_telos_metrics_lightweight(
    manager, user_input: str, response: str, user_fidelity: float
) -> Dict:
    """
    Compute TELOS metrics for GREEN/YELLOW zones with PS calculation.

    Used for GREEN/YELLOW zones where intervention isn't needed.
    Computes AI Fidelity and Primacy State for user visibility.

    Args:
        manager: BetaResponseManager instance
        user_input: The user's message
        response: The already-generated native response
        user_fidelity: Pre-calculated user fidelity score

    Returns:
        Dict with TELOS metrics including AI Fidelity and PS
    """
    logger.info("Computing TELOS metrics for GREEN/YELLOW zone (no intervention)")

    ai_fidelity = None
    primacy_state = None
    display_primacy_state = None
    pa_correlation = None
    ps_condition = 'not_computed'

    try:
        if (manager.st_embedding_provider and
            manager.st_user_pa_embedding is not None and
            response):

            response_embedding = np.array(manager.st_embedding_provider.encode(response))

            # Store AI response in context buffer
            if manager.adaptive_context_manager and hasattr(manager.adaptive_context_manager, 'context_buffer'):
                manager.adaptive_context_manager.context_buffer.add_ai_response(response, response_embedding)

            # AI FIDELITY: BEHAVIORAL ALIGNMENT (dual-reference)
            ai_pa_embedding = getattr(manager, 'st_ai_pa_embedding', None)
            if ai_pa_embedding is None:
                ai_pa_embedding = manager.st_user_pa_embedding
            raw_ai_fidelity_to_pa = cosine_similarity(response_embedding, ai_pa_embedding)

            user_input_embedding = np.array(manager.st_embedding_provider.encode(user_input))
            raw_ai_fidelity_to_query = cosine_similarity(response_embedding, user_input_embedding)

            if raw_ai_fidelity_to_pa >= raw_ai_fidelity_to_query:
                ai_fidelity = normalize_ai_response_fidelity(raw_ai_fidelity_to_pa)
                winning_ref = "AI_PA"
            else:
                ai_fidelity = normalize_ai_response_fidelity(raw_ai_fidelity_to_query)
                winning_ref = "Query"

            logger.info(f"AI Fidelity (behavioral): AI_PA={raw_ai_fidelity_to_pa:.3f}, "
                       f"Query={raw_ai_fidelity_to_query:.3f}, Winner={winning_ref} -> {ai_fidelity:.2%}")

            # Calculate Primacy State using harmonic mean
            epsilon = 1e-10
            if user_fidelity is not None and ai_fidelity is not None:
                primacy_state = (2 * user_fidelity * ai_fidelity) / (user_fidelity + ai_fidelity + epsilon)
                ps_condition = 'computed'

                logger.info(f"PS Metrics: F_user={user_fidelity:.3f}, F_ai={ai_fidelity:.3f}, PS={primacy_state:.3f}")

                # Display-normalized PS for UI
                model_type = 'sentence_transformer' if manager.use_rescaled_fidelity else 'mistral'
                display_user_fidelity = normalize_fidelity_for_display(user_fidelity, model_type)
                display_ai_fidelity = normalize_ai_response_fidelity(ai_fidelity)
                display_primacy_state = (2 * display_user_fidelity * display_ai_fidelity) / (display_user_fidelity + display_ai_fidelity + epsilon)

    except Exception as e:
        logger.warning(f"Could not compute PS metrics in lightweight path: {e}")

    model_type = 'sentence_transformer' if manager.use_rescaled_fidelity else 'mistral'
    display_user_fidelity_value = normalize_fidelity_for_display(user_fidelity, model_type) if user_fidelity is not None else None

    print(f"NATIVE TELOS DATA: user_fidelity={user_fidelity}, model_type={model_type}, display_user_fidelity={display_user_fidelity_value}")

    telos_data = {
        'response': response,
        'fidelity_score': None,
        'distance_from_pa': 1.0 - user_fidelity,
        'intervention_triggered': False,
        'intervention_type': None,
        'intervention_reason': '',
        'drift_detected': user_fidelity < (ST_FIDELITY_YELLOW if manager.use_rescaled_fidelity else FIDELITY_YELLOW),
        'in_basin': True,
        'ai_pa_fidelity': ai_fidelity,
        'primacy_state_score': primacy_state,
        'display_primacy_state': display_primacy_state,
        'primacy_state_condition': ps_condition,
        'pa_correlation': pa_correlation,
        'lightweight_path': True,
        'user_pa_fidelity': user_fidelity,
        'display_user_pa_fidelity': display_user_fidelity_value,
    }

    return telos_data

"""
PA Initialization Service - Primacy Attractor Setup for TELOS Observatory
==========================================================================

Extracted from BetaResponseManager to provide focused PA management.

Handles:
- TELOS engine initialization with dual PA support
- PA derivation from first message (Start Fresh mode)
- TELOS command handling (session focus pivots)
- PA centroid regeneration from example queries
- Intent detection from purpose string
"""

import logging
import hashlib
import numpy as np
import streamlit as st
from typing import Dict
from datetime import datetime

from telos_core.constants import FIDELITY_GREEN

from telos_observatory.services.pa_enrichment import detect_telos_command, PAEnrichmentService

logger = logging.getLogger(__name__)

# Intent to Role mapping for AI PA derivation
INTENT_TO_ROLE_MAP = {
    'learn': 'teach',
    'understand': 'explain',
    'solve': 'help solve',
    'create': 'help create',
    'decide': 'help decide',
    'explore': 'guide exploration',
    'analyze': 'help analyze',
    'fix': 'help fix',
    'debug': 'help debug',
    'optimize': 'help optimize',
    'research': 'help research',
    'plan': 'help plan'
}


def detect_intent_from_purpose(purpose: str) -> str:
    """
    Detect user intent from purpose string using keyword matching.

    Args:
        purpose: User's stated purpose

    Returns:
        Intent verb (e.g., 'learn', 'solve', 'create')
    """
    purpose_lower = purpose.lower()

    intent_keywords = {
        'learn': ['learn', 'study', 'understand better', 'education'],
        'understand': ['understand', 'comprehend', 'grasp', 'figure out'],
        'solve': ['solve', 'fix', 'resolve', 'troubleshoot', 'debug'],
        'create': ['create', 'build', 'make', 'develop', 'design', 'write'],
        'decide': ['decide', 'choose', 'select', 'pick', 'evaluate options'],
        'explore': ['explore', 'discover', 'investigate', 'look into'],
        'analyze': ['analyze', 'examine', 'review', 'assess', 'audit'],
        'fix': ['fix', 'repair', 'correct', 'patch'],
        'debug': ['debug', 'trace', 'diagnose'],
        'optimize': ['optimize', 'improve', 'enhance', 'streamline'],
        'research': ['research', 'study', 'survey', 'review literature'],
        'plan': ['plan', 'organize', 'schedule', 'strategy', 'roadmap']
    }

    for intent, keywords in intent_keywords.items():
        for keyword in keywords:
            if keyword in purpose_lower:
                return intent

    return 'understand'


def initialize_telos_engine(manager):
    """Initialize TELOS engine for governance with dual PA support."""
    try:
        from telos_observatory.services.unified_steward import UnifiedGovernanceSteward, PrimacyAttractor
        from telos_core.embedding_provider import (
            MistralEmbeddingProvider,
            SentenceTransformerProvider
        )
        from telos_observatory.services.mistral_client import MistralClient
        from telos_core.primacy_state import PrimacyStateCalculator

        # Check if using a template (pre-established PA)
        selected_template = st.session_state.get('selected_template', None)
        manager.use_rescaled_fidelity = selected_template is not None

        if manager.use_rescaled_fidelity:
            logger.debug("TEMPLATE MODE: Using SentenceTransformer with raw thresholds (Clean Lane)")

        # Read PA from session state
        pa_data = st.session_state.get('primacy_attractor', None)
        pa_established = st.session_state.get('pa_established', False)

        logger.debug(f"BETA TELOS Init: pa_exists={pa_data is not None}, pa_established={pa_established}")

        if pa_data and pa_established:
            purpose_raw = pa_data.get('purpose', 'General assistance')
            scope_raw = pa_data.get('scope', 'Open discussion')
            purpose_str = ' '.join(purpose_raw) if isinstance(purpose_raw, list) else purpose_raw
            scope_str = ' '.join(scope_raw) if isinstance(scope_raw, list) else scope_raw

            boundaries = pa_data.get('boundaries', [])
            if not boundaries:
                boundaries = [
                    "Stay focused on stated purpose",
                    "Avoid unrelated tangents",
                    "Maintain productive dialogue"
                ]
                logger.warning(f"  - PA had empty boundaries, using defaults")

            attractor = PrimacyAttractor(
                purpose=[purpose_str] if isinstance(purpose_str, str) else purpose_str,
                scope=[scope_str] if isinstance(scope_str, str) else scope_str,
                boundaries=boundaries,
                constraint_tolerance=0.02
            )
            logger.info(f"BETA: Using established PA - Purpose: {purpose_str[:80]}")
        else:
            purpose_str = "Engage in helpful conversation"
            scope_str = "General assistance"
            attractor = PrimacyAttractor(
                purpose=[purpose_str],
                scope=[scope_str],
                boundaries=["Maintain respectful dialogue"],
                constraint_tolerance=0.02
            )
            logger.warning("BETA: No established PA found - using fallback")

        # Initialize LLM client and embedding provider
        llm_client = MistralClient()
        embedding_provider = MistralEmbeddingProvider()
        manager.embedding_provider = embedding_provider

        # Template mode: Initialize SentenceTransformer
        if manager.use_rescaled_fidelity:
            logger.info("Getting cached SentenceTransformer for template mode fidelity...")
            from telos_core.embedding_provider import get_cached_minilm_provider
            manager.st_embedding_provider = get_cached_minilm_provider()
            logger.info(f"   SentenceTransformer (cached): {manager.st_embedding_provider.dimension} dims")

        # Initialize MPNet for AI Fidelity
        logger.info("Getting cached MPNet for AI fidelity...")
        from telos_core.embedding_provider import get_cached_mpnet_provider
        manager.mpnet_embedding_provider = get_cached_mpnet_provider()
        logger.info(f"   MPNet (cached): {manager.mpnet_embedding_provider.dimension} dims")

        # Initialize steward
        manager.telos_engine = UnifiedGovernanceSteward(
            attractor=attractor,
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            enable_interventions=True
        )

        logger.info("Starting TELOS session...")
        manager.telos_engine.start_session()
        logger.info("TELOS session started successfully")

        # DUAL PA SETUP: Derive AI PA and compute embeddings
        logger.info("Setting up Dual PA for Primacy State calculation...")

        current_pa_identity = hashlib.md5(f"{purpose_str}|{scope_str}".encode()).hexdigest()[:16]
        cached_pa_identity = st.session_state.get('cached_pa_identity', None)

        # Check if PA has changed - invalidate cached embeddings
        if cached_pa_identity and cached_pa_identity != current_pa_identity:
            logger.warning(f"PA CHANGED: Invalidating cached embeddings (old={cached_pa_identity}, new={current_pa_identity})")
            for key in ['cached_user_pa_embedding', 'cached_ai_pa_embedding',
                        'cached_st_user_pa_embedding', 'cached_mpnet_user_pa_embedding',
                        'cached_mpnet_ai_pa_embedding']:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.cached_pa_identity = current_pa_identity

        # TEMPLATE MODE FAST PATH
        template_mode_ready = (
            manager.use_rescaled_fidelity and
            'cached_st_user_pa_embedding' in st.session_state and
            'cached_mpnet_user_pa_embedding' in st.session_state and
            'cached_mpnet_ai_pa_embedding' in st.session_state and
            st.session_state.get('cached_pa_identity') == current_pa_identity
        )

        if template_mode_ready:
            logger.info("   TEMPLATE MODE FAST PATH: Using cached ST/MPNet embeddings")
            manager.st_user_pa_embedding = st.session_state.cached_st_user_pa_embedding
            manager.mpnet_user_pa_embedding = st.session_state.cached_mpnet_user_pa_embedding
            manager.mpnet_ai_pa_embedding = st.session_state.cached_mpnet_ai_pa_embedding

            if 'cached_user_pa_embedding' in st.session_state:
                manager.user_pa_embedding = st.session_state.cached_user_pa_embedding
                manager.ai_pa_embedding = st.session_state.get('cached_ai_pa_embedding', manager.user_pa_embedding)
            else:
                user_pa_text = f"Purpose: {purpose_str}. Scope: {scope_str}."
                manager.user_pa_embedding = np.array(embedding_provider.encode(user_pa_text))
                manager.ai_pa_embedding = manager.user_pa_embedding
                st.session_state.cached_user_pa_embedding = manager.user_pa_embedding
                st.session_state.cached_ai_pa_embedding = manager.ai_pa_embedding

        elif ('cached_user_pa_embedding' in st.session_state and
            'cached_ai_pa_embedding' in st.session_state and
            st.session_state.get('cached_pa_identity') == current_pa_identity):
            manager.user_pa_embedding = st.session_state.cached_user_pa_embedding
            manager.ai_pa_embedding = st.session_state.cached_ai_pa_embedding
            logger.info("   Using CACHED PA embeddings from session state (deterministic)")

            # Template mode: Create SentenceTransformer PA centroid
            if manager.use_rescaled_fidelity and manager.st_embedding_provider:
                if 'cached_st_user_pa_embedding' in st.session_state:
                    manager.st_user_pa_embedding = st.session_state.cached_st_user_pa_embedding
                else:
                    example_queries = selected_template.get('example_queries', []) if selected_template else []
                    if example_queries:
                        from telos_observatory.config.pa_templates import UNIVERSAL_EXPANSION_WEIGHT
                        from telos_core.embedding_provider import (
                            get_cached_universal_lane_centroid,
                            get_cached_template_domain_centroid
                        )

                        template_id = selected_template.get('id', None) if selected_template else None
                        domain_centroid = get_cached_template_domain_centroid(template_id) if template_id else None

                        if domain_centroid is None:
                            example_embeddings = [np.array(manager.st_embedding_provider.encode(ex)) for ex in example_queries]
                            domain_centroid = np.mean(example_embeddings, axis=0)

                        universal_centroid = get_cached_universal_lane_centroid()
                        combined_centroid = (1 - UNIVERSAL_EXPANSION_WEIGHT) * domain_centroid + UNIVERSAL_EXPANSION_WEIGHT * universal_centroid
                        manager.st_user_pa_embedding = combined_centroid / np.linalg.norm(combined_centroid)
                    else:
                        user_pa_text = f"Purpose: {purpose_str}. Scope: {scope_str}."
                        manager.st_user_pa_embedding = np.array(manager.st_embedding_provider.encode(user_pa_text))
                    st.session_state.cached_st_user_pa_embedding = manager.st_user_pa_embedding

            # MPNet embeddings for fast AI fidelity
            if manager.mpnet_embedding_provider:
                if 'cached_mpnet_user_pa_embedding' in st.session_state:
                    manager.mpnet_user_pa_embedding = st.session_state.cached_mpnet_user_pa_embedding
                else:
                    user_pa_text = f"Purpose: {purpose_str}. Scope: {scope_str}."
                    manager.mpnet_user_pa_embedding = np.array(manager.mpnet_embedding_provider.encode(user_pa_text))
                    st.session_state.cached_mpnet_user_pa_embedding = manager.mpnet_user_pa_embedding

                if 'cached_mpnet_ai_pa_embedding' in st.session_state:
                    manager.mpnet_ai_pa_embedding = st.session_state.cached_mpnet_ai_pa_embedding
                else:
                    detected_intent = detect_intent_from_purpose(purpose_str)
                    role_action = INTENT_TO_ROLE_MAP.get(detected_intent, 'help')
                    ai_purpose = f"{role_action.capitalize()} the user as they work to: {purpose_str}"
                    ai_pa_text = f"AI Role: {ai_purpose}. Supporting scope: {scope_str}."
                    manager.mpnet_ai_pa_embedding = np.array(manager.mpnet_embedding_provider.encode(ai_pa_text))
                    st.session_state.cached_mpnet_ai_pa_embedding = manager.mpnet_ai_pa_embedding
        else:
            # FALLBACK: Compute embeddings lazily
            logger.warning("   PA embeddings not cached - computing lazily (fallback path)")

            user_pa_text = f"Purpose: {purpose_str}. Scope: {scope_str}."
            detected_intent = detect_intent_from_purpose(purpose_str)
            role_action = INTENT_TO_ROLE_MAP.get(detected_intent, 'help')
            ai_purpose = f"{role_action.capitalize()} the user as they work to: {purpose_str}"
            ai_pa_text = f"AI Role: {ai_purpose}. Supporting scope: {scope_str}."

            if hasattr(embedding_provider, 'batch_encode'):
                embeddings = embedding_provider.batch_encode([user_pa_text, ai_pa_text])
                manager.user_pa_embedding = embeddings[0]
                manager.ai_pa_embedding = embeddings[1]
            else:
                manager.user_pa_embedding = np.array(embedding_provider.encode(user_pa_text))
                manager.ai_pa_embedding = np.array(embedding_provider.encode(ai_pa_text))

            logger.info(f"   User PA: {len(manager.user_pa_embedding)} dims, AI PA: {len(manager.ai_pa_embedding)} dims")

            st.session_state.cached_user_pa_embedding = manager.user_pa_embedding
            st.session_state.cached_ai_pa_embedding = manager.ai_pa_embedding
            st.session_state.cached_pa_identity = current_pa_identity

            # Template mode: Also create SentenceTransformer PA embedding
            if manager.use_rescaled_fidelity and manager.st_embedding_provider:
                from telos_observatory.config.pa_templates import UNIVERSAL_EXPANSION_WEIGHT
                from telos_core.embedding_provider import get_cached_universal_lane_centroid

                example_queries = selected_template.get('example_queries', []) if selected_template else []
                if example_queries:
                    from telos_core.embedding_provider import get_cached_template_domain_centroid
                    template_id = selected_template.get('id', None) if selected_template else None
                    domain_centroid = get_cached_template_domain_centroid(template_id) if template_id else None

                    if domain_centroid is None:
                        example_embeddings = [np.array(manager.st_embedding_provider.encode(ex)) for ex in example_queries]
                        domain_centroid = np.mean(example_embeddings, axis=0)

                    universal_centroid = get_cached_universal_lane_centroid()
                    combined_centroid = (1 - UNIVERSAL_EXPANSION_WEIGHT) * domain_centroid + UNIVERSAL_EXPANSION_WEIGHT * universal_centroid
                    manager.st_user_pa_embedding = combined_centroid / np.linalg.norm(combined_centroid)
                else:
                    manager.st_user_pa_embedding = np.array(manager.st_embedding_provider.encode(user_pa_text))

                st.session_state.cached_st_user_pa_embedding = manager.st_user_pa_embedding

            # Create MPNet AI PA embedding
            if manager.mpnet_embedding_provider:
                manager.mpnet_ai_pa_embedding = np.array(manager.mpnet_embedding_provider.encode(ai_pa_text))
                st.session_state.cached_mpnet_ai_pa_embedding = manager.mpnet_ai_pa_embedding

        # Initialize Primacy State Calculator
        manager.ps_calculator = PrimacyStateCalculator(track_energy=True)
        logger.info("PrimacyStateCalculator initialized with energy tracking")

        # Compute initial PA correlation (rho_PA)
        rho_pa = manager.ps_calculator.cosine_similarity(
            manager.user_pa_embedding,
            manager.ai_pa_embedding
        )
        logger.info(f"   PA Correlation (rho_PA): {rho_pa:.3f}")

        if hasattr(manager.telos_engine, 'attractor_math') and manager.telos_engine.attractor_math:
            basin_radius = manager.telos_engine.attractor_math.basin_radius
            logger.info(f"TELOS engine initialized (DUAL PA MODE), basin_radius={basin_radius:.3f}")
        else:
            logger.info("TELOS engine initialized for BETA testing with DUAL PA")

    except Exception as e:
        logger.error(f"Failed to initialize TELOS engine: {e}")
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")
        manager.telos_engine = None
        manager.ps_calculator = None


def derive_pa_from_first_message(manager, user_input: str):
    """
    Derive PA from user's first message (Start Fresh mode).

    Uses PA Enrichment Service for genuine semantic extraction.

    Args:
        manager: BetaResponseManager instance
        user_input: User's first message containing their purpose
    """
    from telos_observatory.services.beta_dual_attractor import derive_ai_pa_from_user_pa, compute_pa_embeddings

    logger.info(f"Deriving PA from: {user_input[:100]}...")

    detected_intent = detect_intent_from_purpose(user_input)
    logger.info(f"   Detected intent: {detected_intent}")

    # Use PA Enrichment Service for genuine semantic extraction
    enriched_pa = None
    try:
        from mistralai import Mistral
        import os
        import traceback

        api_key = os.getenv('MISTRAL_API_KEY')
        if not api_key:
            logger.error("   MISTRAL_API_KEY not found in environment!")
        else:
            logger.info(f"   MISTRAL_API_KEY found: {api_key[:10]}...")

        mistral_client = Mistral(api_key=api_key)
        enrichment_service = PAEnrichmentService(mistral_client)

        logger.info("   Using PA Enrichment Service for semantic extraction...")
        enriched_pa = enrichment_service.enrich_direction(
            direction=user_input,
            current_template=None,
            conversation_context=""
        )

        if enriched_pa:
            logger.info(f"   PA enriched with {len(enriched_pa.get('example_queries', []))} example queries")
        else:
            logger.warning("   PA enrichment returned None")
    except Exception as e:
        logger.error(f"   PA enrichment exception: {type(e).__name__}: {e}")

    # Build User PA from enriched structure (or fallback)
    if enriched_pa:
        user_pa = {
            "purpose": [enriched_pa.get('purpose', user_input)],
            "scope": enriched_pa.get('scope', [f"Explore: {user_input[:80]}"]),
            "boundaries": enriched_pa.get('boundaries', [
                "Stay focused on stated purpose",
                "Provide helpful, relevant responses"
            ]),
            "example_queries": enriched_pa.get('example_queries', []),
            "success_criteria": f"Deep understanding of: {user_input[:80]}",
            "style": "Adaptive",
            "established_turn": 1,
            "establishment_method": "fresh_start_enriched",
            "detected_intent": detected_intent
        }
    else:
        user_pa = {
            "purpose": [user_input],
            "scope": [f"Explore and understand: {user_input[:80]}"],
            "boundaries": [
                "Stay focused on stated purpose",
                "Provide helpful, relevant responses"
            ],
            "success_criteria": f"Help with: {user_input[:80]}",
            "style": "Adaptive",
            "established_turn": 1,
            "establishment_method": "fresh_start_basic",
            "detected_intent": detected_intent
        }

    # Derive AI PA using dual attractor lock-on
    ai_pa = derive_ai_pa_from_user_pa(user_pa)
    logger.info(f"   AI PA derived: {ai_pa.get('purpose', ['N/A'])[0][:80]}...")

    # Store both PAs in session state
    st.session_state.primacy_attractor = user_pa
    st.session_state.user_pa = user_pa
    st.session_state.ai_pa = ai_pa
    st.session_state.pa_established = True
    st.session_state.pa_establishment_time = datetime.now().isoformat()

    if 'state_manager' in st.session_state:
        st.session_state.state_manager.state.primacy_attractor = user_pa
        st.session_state.state_manager.state.user_pa_established = True
        st.session_state.state_manager.state.convergence_turn = 1
        st.session_state.state_manager.state.pa_converged = True

    # Compute embeddings for fidelity calculation
    try:
        from telos_core.embedding_provider import get_cached_minilm_provider
        embedding_provider = get_cached_minilm_provider()
        user_embedding, ai_embedding = compute_pa_embeddings(user_pa, ai_pa, embedding_provider)

        st.session_state.cached_user_pa_embedding = user_embedding
        st.session_state.cached_ai_pa_embedding = ai_embedding

        purpose_str = ' '.join(user_pa.get('purpose', [])) if isinstance(user_pa.get('purpose'), list) else user_pa.get('purpose', '')
        scope_str = ' '.join(user_pa.get('scope', [])) if isinstance(user_pa.get('scope'), list) else user_pa.get('scope', '')
        st.session_state.cached_pa_identity = hashlib.md5(f"{purpose_str}|{scope_str}".encode()).hexdigest()[:16]

        # Create SentenceTransformer embedding for fidelity
        st_provider = get_cached_minilm_provider()

        example_queries = user_pa.get('example_queries', [])
        if example_queries and len(example_queries) >= 3:
            example_embeddings = [np.array(st_provider.encode(ex)) for ex in example_queries]
            st_embedding = np.mean(example_embeddings, axis=0)
            st_embedding = st_embedding / np.linalg.norm(st_embedding)
        else:
            st_embedding = np.array(st_provider.encode(user_input))
            st_embedding = st_embedding / np.linalg.norm(st_embedding)

        st.session_state.cached_st_user_pa_embedding = st_embedding

        # Enable template mode
        st.session_state.use_rescaled_fidelity_mode = True
        manager.use_rescaled_fidelity = True
        manager.st_embedding_provider = st_provider
        manager.st_user_pa_embedding = st_embedding

        logger.info(f"   Embeddings computed and cached")

    except Exception as e:
        logger.warning(f"   Failed to compute embeddings: {e}")

    # Force TELOS engine re-initialization on next response
    manager.telos_engine = None
    manager.ps_calculator = None

    logger.info("   PA derivation complete")


def handle_telos_command(manager, new_direction: str, turn_number: int) -> Dict:
    """
    Handle TELOS: command for session focus pivot.

    Args:
        manager: BetaResponseManager instance
        new_direction: User's stated new focus direction
        turn_number: Current turn number

    Returns:
        Dict containing response data with Steward acknowledgment
    """
    logger.info(f"Handling TELOS command: {new_direction}")

    current_template = st.session_state.get('selected_template', None)
    current_pa = st.session_state.get('primacy_attractor', {})
    previous_purpose_raw = current_pa.get('purpose', 'General session')
    previous_purpose = ' '.join(previous_purpose_raw) if isinstance(previous_purpose_raw, list) else previous_purpose_raw

    # Initialize PA enrichment service if needed
    if not manager.pa_enrichment_service:
        try:
            from mistralai import Mistral
            import os
            mistral_client = Mistral(api_key=os.getenv('MISTRAL_API_KEY'))
            manager.pa_enrichment_service = PAEnrichmentService(mistral_client)
        except Exception as e:
            logger.error(f"Failed to initialize PA Enrichment Service: {e}")
            from telos_observatory.services.turn_storage_service import create_telos_error_response, store_turn_data
            response_data = create_telos_error_response(turn_number, new_direction, str(e))
            store_turn_data(manager, turn_number, response_data)
            return response_data

    # Get recent conversation context
    from telos_observatory.services.turn_storage_service import get_recent_context, store_turn_data
    conversation_context = get_recent_context(manager)

    # Enrich the direction into a full PA structure
    logger.info("Enriching direction via LLM...")
    enriched_pa = manager.pa_enrichment_service.enrich_direction(
        direction=new_direction,
        current_template=current_template,
        conversation_context=conversation_context
    )

    if not enriched_pa:
        logger.error("PA enrichment failed - could not generate structure")
        from telos_observatory.services.turn_storage_service import create_telos_error_response
        response_data = create_telos_error_response(turn_number, new_direction, "Could not enrich direction")
        store_turn_data(manager, turn_number, response_data)
        return response_data

    logger.info(f"PA enriched with {len(enriched_pa.get('example_queries', []))} example queries")

    # Update session state with new PA
    new_pa = {
        'purpose': enriched_pa.get('purpose', new_direction),
        'scope': ', '.join(enriched_pa.get('scope', [])) if isinstance(enriched_pa.get('scope'), list) else enriched_pa.get('scope', ''),
        'boundaries': enriched_pa.get('boundaries', []),
        'example_queries': enriched_pa.get('example_queries', []),
        'pivot_from': previous_purpose,
        'pivot_direction': new_direction,
    }
    st.session_state['primacy_attractor'] = new_pa
    st.session_state['pa_established'] = True

    st.session_state.pa_just_shifted = True

    if 'last_telos_calibration_values' in st.session_state:
        del st.session_state.last_telos_calibration_values
        logger.info("Cleared last_telos_calibration_values cache on PA shift")

    # Regenerate PA centroid
    regenerate_pa_centroid(manager, enriched_pa.get('example_queries', []))

    # Generate Steward acknowledgment response
    steward_response = manager.pa_enrichment_service.generate_pivot_response(
        enriched_pa=enriched_pa,
        previous_focus=previous_purpose
    )

    steward_response += "\n\n*Your Alignment Lens now reflects your updated Primacy Attractors.*"

    response_data = {
        'turn_number': turn_number,
        'timestamp': datetime.now().isoformat(),
        'user_input': f"TELOS: {new_direction}",
        'governance_mode': 'telos_pivot',
        'is_telos_command': True,
        'new_direction': new_direction,
        'enriched_pa': enriched_pa,
        'response': steward_response,
        'shown_response': steward_response,
        'shown_source': 'steward_pivot',
        'user_fidelity': 1.0,
        'display_fidelity': 1.0,
        'fidelity_level': 'green',
        'intervention_triggered': False,
        'is_loading': False,
        'is_streaming': False,
        'telos_analysis': {
            'response': steward_response,
            'fidelity_score': 1.0,
            'intervention_triggered': False,
            'in_basin': True,
            'pivot_detected': True,
        }
    }

    store_turn_data(manager, turn_number, response_data)

    logger.info(f"TELOS pivot complete - new focus: {enriched_pa.get('purpose', new_direction)[:50]}...")
    return response_data


def regenerate_pa_centroid(manager, example_queries: list):
    """
    Regenerate PA centroid from purpose/scope + example queries.

    Args:
        manager: BetaResponseManager instance
        example_queries: List of example queries for centroid construction
    """
    try:
        if not manager.st_embedding_provider:
            from telos_core.embedding_provider import get_cached_minilm_provider
            manager.st_embedding_provider = get_cached_minilm_provider()

        new_pa_data = st.session_state.get('primacy_attractor', {})
        purpose_str = new_pa_data.get('purpose', '')
        if isinstance(purpose_str, list):
            purpose_str = ' '.join(purpose_str)
        scope_str = new_pa_data.get('scope', '')
        if isinstance(scope_str, list):
            scope_str = ' '.join(scope_str)
        user_pa_text = f"Purpose: {purpose_str} Scope: {scope_str}"

        if example_queries:
            all_texts = [user_pa_text] + list(example_queries)
        else:
            all_texts = [user_pa_text]

        logger.info(f"Regenerating PA centroid from {len(all_texts)} texts...")
        all_embeddings = []
        for text in all_texts:
            emb = np.array(manager.st_embedding_provider.encode(text))
            emb = emb / (np.linalg.norm(emb) + 1e-10)
            all_embeddings.append(emb)

        domain_centroid = np.mean(all_embeddings, axis=0)
        manager.st_user_pa_embedding = domain_centroid / (np.linalg.norm(domain_centroid) + 1e-10)

        st.session_state.cached_st_user_pa_embedding = manager.st_user_pa_embedding

        manager.use_rescaled_fidelity = True
        st.session_state.use_rescaled_fidelity_mode = True

        # Update PA identity hash
        new_pa_identity = hashlib.md5(f"{purpose_str}|{scope_str}".encode()).hexdigest()[:16]
        st.session_state.cached_pa_identity = new_pa_identity

        # Regenerate MPNet embeddings
        if manager.mpnet_embedding_provider:
            user_pa_text_full = f"Purpose: {purpose_str}. Scope: {scope_str}."
            manager.mpnet_user_pa_embedding = np.array(manager.mpnet_embedding_provider.encode(user_pa_text_full))
            st.session_state.cached_mpnet_user_pa_embedding = manager.mpnet_user_pa_embedding

            detected_intent = detect_intent_from_purpose(purpose_str)
            role_action = INTENT_TO_ROLE_MAP.get(detected_intent, 'help')
            ai_purpose = f"{role_action.capitalize()} the user as they work to: {purpose_str}"
            ai_pa_text = f"AI Role: {ai_purpose}. Supporting scope: {scope_str}."
            manager.mpnet_ai_pa_embedding = np.array(manager.mpnet_embedding_provider.encode(ai_pa_text))
            st.session_state.cached_mpnet_ai_pa_embedding = manager.mpnet_ai_pa_embedding

        # Clear stale Mistral PA embeddings
        if 'cached_user_pa_embedding' in st.session_state:
            del st.session_state['cached_user_pa_embedding']
        if 'cached_ai_pa_embedding' in st.session_state:
            del st.session_state['cached_ai_pa_embedding']

        logger.info(f"PA centroid regenerated: {len(manager.st_user_pa_embedding)} dims")

    except Exception as e:
        logger.error(f"Failed to regenerate PA centroid: {e}")

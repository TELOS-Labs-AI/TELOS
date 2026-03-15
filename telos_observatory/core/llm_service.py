"""
LLM Service Factory
====================

Single factory for LLM client initialization.
Replaces 3 duplicated copies of Mistral init code from state_manager.py.
"""

import os
import logging
from typing import Optional, Tuple, Any

import streamlit as st

logger = logging.getLogger(__name__)


def get_mistral_api_key() -> str:
    """
    Retrieve Mistral API key from environment or Streamlit secrets.

    Returns:
        API key string.

    Raises:
        ValueError: If API key not found anywhere.
    """
    # Try environment variable first (more reliable)
    api_key = os.getenv("MISTRAL_API_KEY")

    # Fall back to Streamlit secrets
    if not api_key:
        try:
            api_key = st.secrets["MISTRAL_API_KEY"]
        except (KeyError, FileNotFoundError):
            pass

    if not api_key:
        raise ValueError("MISTRAL_API_KEY not found in environment or Streamlit secrets")

    return api_key


def get_llm_client(model: str = "mistral-small-latest"):
    """
    Factory function to create a configured Mistral LLM client.

    Args:
        model: Mistral model identifier. Default is mistral-small-latest
               (5-15s latency vs 30-60s for large).

    Returns:
        Configured MistralClient instance.
    """
    from telos_observatory.services.mistral_client import MistralClient

    api_key = get_mistral_api_key()
    logger.info(f"Creating Mistral client with model={model}")

    return MistralClient(api_key=api_key, model=model)


def get_embedding_provider(use_cache: bool = True):
    """
    Get a sentence transformer embedding provider.

    Args:
        use_cache: If True, use cached provider to avoid expensive model reloading.

    Returns:
        Embedding provider instance.
    """
    if use_cache:
        from telos_core.embedding_provider import get_cached_minilm_provider
        return get_cached_minilm_provider()
    else:
        from telos_core.embedding_provider import SentenceTransformerProvider
        return SentenceTransformerProvider()


def initialize_telos_steward(
    state_manager,
    demo_mode: bool = False,
    pa_data: Optional[dict] = None,
    pa_established: bool = False,
    enable_interventions: bool = True
) -> Tuple[Any, Any]:
    """
    Initialize a TELOS UnifiedGovernanceSteward with proper attractor and LLM.

    This is the single initialization path, replacing 3 duplicated copies.

    Args:
        state_manager: StateManager instance (for session_id).
        demo_mode: Whether to use demo attractor config.
        pa_data: Primacy Attractor data from session state (for BETA mode).
        pa_established: Whether the PA has been established via onboarding.
        enable_interventions: Whether to enable drift interventions.

    Returns:
        Tuple of (steward, corpus_loader) where corpus_loader may be None.
    """
    from telos_observatory.services.unified_steward import UnifiedGovernanceSteward, PrimacyAttractor

    embedding_provider = get_embedding_provider(use_cache=True)
    corpus_loader = None

    if demo_mode:
        from telos_observatory.demo_mode.telos_framework_demo import get_demo_attractor_config
        config = get_demo_attractor_config()
        attractor = PrimacyAttractor(**config)

        # Load RAG corpus for Demo Mode
        logger.info("Loading TELOS documentation corpus for Demo Mode...")
        from telos_observatory.demo_mode.telos_corpus_loader import TELOSCorpusLoader
        corpus_loader = TELOSCorpusLoader(embedding_provider)
        num_chunks = corpus_loader.load_corpus()
        logger.info(f"Corpus loaded: {num_chunks} chunks")

    elif pa_data and pa_established:
        # Use the PA established during onboarding
        purpose_str = pa_data.get('purpose', 'General assistance')
        scope_str = pa_data.get('scope', 'Open discussion')

        attractor = PrimacyAttractor(
            purpose=[purpose_str] if isinstance(purpose_str, str) else purpose_str,
            scope=[scope_str] if isinstance(scope_str, str) else scope_str,
            boundaries=pa_data.get('boundaries', [
                "Maintain respectful dialogue",
                "Provide accurate information",
                "Stay within ethical guidelines"
            ])
        )
        logger.info(f"Using established PA - Purpose: {purpose_str[:80]}")

    else:
        # Fallback: Minimal attractor for general conversation
        attractor = PrimacyAttractor(
            purpose=[
                "Engage in helpful, informative conversation",
                "Respond to user questions and requests",
                "Maintain conversational coherence"
            ],
            scope=[
                "General knowledge and assistance",
                "User's topics of interest",
                "Any subject the user wishes to discuss"
            ],
            boundaries=[
                "Maintain respectful dialogue",
                "Provide accurate information",
                "Stay within ethical guidelines"
            ],
            constraint_tolerance=0.5,
            privacy_level=0.8,
            task_priority=0.5
        )
        logger.warning("No established PA found - using generic fallback")

    mistral_client = get_llm_client()

    steward = UnifiedGovernanceSteward(
        attractor=attractor,
        llm_client=mistral_client,
        embedding_provider=embedding_provider,
        enable_interventions=enable_interventions
    )
    steward.start_session(session_id=state_manager.state.session_id)
    logger.info("TELOS engine initialized successfully")

    return steward, corpus_loader

"""
Beta Dual Attractor Derivation Service
=======================================

Implements mathematical dual PA governance for BETA mode:
- User PA: Governs conversation purpose (WHAT to discuss)
- AI PA: Governs AI behavior/role (HOW to help)

Key Innovation: Lock-on derivation - AI PA is COMPUTED from User PA
using intent-to-role mapping, ensuring automatic semantic coupling.

This replaces the LLM-only approach in PAExtractor with actual
mathematical attractor derivation that makes TELOS claims defensible.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional, Tuple
from telos_observatory.services.mistral_client import MistralClient

logger = logging.getLogger(__name__)


# Intent to Role Mapping - The semantic bridge between User PA and AI PA
# User intent verb → AI complementary role action
#
# CRITICAL: This mapping defines the mathematical coupling between User and AI attractors.
# When deriving AI PA, we detect the user's intent verb and map it to the AI's role.
# Example: User wants to "learn" → AI role is to "teach"
#
# Template purpose statements should START with these verbs for proper intent detection.
INTENT_TO_ROLE_MAP = {
    # Learning intents
    'learn': 'teach',
    'understand': 'explain',
    'study': 'teach',
    'grasp': 'explain',
    'master': 'guide mastery of',

    # Problem-solving intents
    'solve': 'help solve',
    'fix': 'help fix',
    'debug': 'help debug',
    'troubleshoot': 'help troubleshoot',
    'diagnose': 'help diagnose',

    # Creative intents
    'create': 'help create',
    'write': 'help write',
    'build': 'help build',
    'develop': 'help develop',
    'design': 'help design',
    'produce': 'help produce',
    'craft': 'help craft',
    'compose': 'help compose',
    'generate': 'help generate',
    'brainstorm': 'help brainstorm',

    # Analytical intents
    'analyze': 'help analyze',
    'review': 'help review',
    'evaluate': 'help evaluate',
    'assess': 'help assess',
    'examine': 'help examine',
    'investigate': 'help investigate',
    'research': 'help research',
    'synthesize': 'help synthesize',

    # Planning intents
    'plan': 'help plan',
    'organize': 'help organize',
    'strategize': 'help strategize',
    'structure': 'help structure',
    'decide': 'help decide',

    # Exploration intents
    'explore': 'guide exploration of',
    'discover': 'help discover',

    # Optimization intents
    'optimize': 'help optimize',
    'improve': 'help improve',
    'enhance': 'help enhance',
    'refactor': 'help refactor',

    # Documentation intents
    'document': 'help document',
    'test': 'help test',
    'implement': 'help implement',
}


def detect_user_intent(
    user_pa: Dict[str, Any],
    mistral_client: Optional[MistralClient] = None
) -> str:
    """
    Detect primary user intent from PA purpose statements.

    Maps purpose to action verb for role derivation.

    CRITICAL: Purpose statements should START with intent verbs.
    We prioritize matches at the beginning of the text.

    Args:
        user_pa: User's primacy attractor configuration
        mistral_client: Optional MistralClient for LLM-based detection

    Returns:
        Primary intent verb (e.g., 'learn', 'solve', 'create')
    """
    purpose_statements = user_pa.get('purpose', [])
    purpose_text = ' '.join(purpose_statements) if isinstance(purpose_statements, list) else str(purpose_statements)
    purpose_lower = purpose_text.lower()

    # Get first ~80 chars (first sentence-ish) for priority matching
    first_part = purpose_lower[:80]

    # Priority 1: Check if intent verb appears at the START of purpose
    for intent in INTENT_TO_ROLE_MAP.keys():
        # Check if purpose starts with the intent verb
        if first_part.startswith(intent):
            logger.info(f"Intent detected at start: '{intent}'")
            return intent
        # Check for "verb and verb" pattern at start (e.g., "learn and deeply understand")
        if f"{intent} and" in first_part[:30]:
            logger.info(f"Intent detected at start (compound): '{intent}'")
            return intent

    # Priority 2: Check first part of purpose for any intent
    for intent in INTENT_TO_ROLE_MAP.keys():
        if intent in first_part:
            logger.info(f"Intent detected in first part: '{intent}'")
            return intent

    # Priority 3: Check full purpose text (original pattern matching)
    for intent in INTENT_TO_ROLE_MAP.keys():
        if intent in purpose_lower:
            logger.info(f"Intent detected via pattern match: '{intent}'")
            return intent

    # If no direct match and we have an LLM client, use it
    if mistral_client:
        prompt = f"""Analyze this conversation purpose and identify the primary user intent.

Purpose: {purpose_text}

What is the primary action the user wants to accomplish? Choose ONE from:
{', '.join(INTENT_TO_ROLE_MAP.keys())}

Respond with ONLY the single word intent verb, nothing else."""

        try:
            response = mistral_client.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )

            intent = response.strip().lower()

            # Validate intent is in our map
            if intent in INTENT_TO_ROLE_MAP:
                logger.info(f"Intent detected via LLM: '{intent}'")
                return intent
            else:
                logger.warning(f"Unknown intent '{intent}', defaulting to 'understand'")
                return 'understand'

        except Exception as e:
            logger.error(f"Error detecting intent via LLM: {e}")
            return 'understand'

    # Default fallback
    logger.info("No intent detected, defaulting to 'understand'")
    return 'understand'


def derive_ai_pa_from_user_pa(
    user_pa: Dict[str, Any],
    mistral_client: Optional[MistralClient] = None
) -> Dict[str, Any]:
    """
    Derive AI's role PA from user's purpose PA using lock-on derivation.

    Core Innovation: AI PA is COMPUTED from user PA, not independently generated.
    This ensures automatic alignment through semantic coupling.

    Args:
        user_pa: User's primacy attractor configuration
        mistral_client: Optional MistralClient for intent detection

    Returns:
        AI PA configuration dict with mathematically coupled purpose
    """
    # Detect user's primary intent
    intent = detect_user_intent(user_pa, mistral_client)
    role_action = INTENT_TO_ROLE_MAP.get(intent, 'help with')

    logger.info(f"Dual Attractor Derivation: intent='{intent}' → role='{role_action}'")

    # Extract user purpose for context
    user_purpose = user_pa.get('purpose', [])
    if isinstance(user_purpose, list):
        user_purpose_text = ' '.join(user_purpose)
    else:
        user_purpose_text = str(user_purpose)

    # Generate AI role purpose statement - mathematically coupled to user purpose
    # Different grammatical constructions based on role type
    if role_action == 'teach':
        ai_purpose = f"Teach the user so they can: {user_purpose_text}"
    elif role_action == 'explain':
        ai_purpose = f"Explain concepts clearly so the user can: {user_purpose_text}"
    elif role_action.startswith('help '):
        # "help write", "help debug", "help plan" etc.
        action_verb = role_action.replace('help ', '')
        ai_purpose = f"Help the user {action_verb}: {user_purpose_text}"
    elif role_action.startswith('guide'):
        ai_purpose = f"Guide the user through: {user_purpose_text}"
    else:
        # Fallback for any other role
        ai_purpose = f"{role_action.capitalize()} to support: {user_purpose_text}"

    # Default AI boundaries - focused on serving user purpose
    ai_boundaries = [
        "Stay focused on serving the user's stated purpose",
        "Maintain helpful and professional demeanor",
        "Provide clear, actionable responses",
        "Ask for clarification when needed",
        "Respect the user's defined boundaries"
    ]

    # Generate AI scope based on user scope - complementary roles
    user_scope = user_pa.get('scope', [])
    if isinstance(user_scope, list):
        ai_scope = [f"Support user in: {item}" for item in user_scope]
    else:
        ai_scope = [f"Support user in: {user_scope}"]

    # Add general support items
    ai_scope.extend([
        "Provide relevant examples and explanations",
        "Offer clarifying questions when helpful",
        "Suggest next steps aligned with user's goal"
    ])

    # Construct AI PA with derivation metadata
    ai_pa = {
        'purpose': [ai_purpose],
        'scope': ai_scope,
        'boundaries': ai_boundaries,
        'constraint_tolerance': user_pa.get('constraint_tolerance', 0.2),
        'privacy_level': user_pa.get('privacy_level', 0.8),
        'task_priority': user_pa.get('task_priority', 0.7),
        'fidelity_threshold': 0.70,  # Slightly higher than user PA
        # Derivation metadata - proves mathematical coupling
        'derived_from_user_pa': True,
        'detected_intent': intent,
        'derived_role_action': role_action
    }

    logger.info(f"AI PA derived: purpose='{ai_purpose[:80]}...'")

    return ai_pa


def compute_pa_embeddings(
    user_pa: Dict[str, Any],
    ai_pa: Dict[str, Any],
    embedding_provider
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute vector embeddings for both user and AI PAs.

    Creates the actual mathematical attractors from text representations.

    NEW (2025-12-28): If user_pa contains 'example_queries', computes a centroid
    embedding that averages the purpose/scope embedding with each example query
    embedding. This creates a PA that covers the semantic space of aligned queries.

    Args:
        user_pa: User's PA configuration (may include 'example_queries' list)
        ai_pa: AI's derived PA configuration
        embedding_provider: SentenceTransformer or similar embedding provider

    Returns:
        Tuple of (user_pa_embedding, ai_pa_embedding) as numpy arrays
    """
    # Build user PA text for embedding
    user_purpose = user_pa.get('purpose', [])
    user_scope = user_pa.get('scope', [])

    user_purpose_text = ' '.join(user_purpose) if isinstance(user_purpose, list) else str(user_purpose)
    user_scope_text = ' '.join(user_scope) if isinstance(user_scope, list) else str(user_scope)
    user_pa_text = f"{user_purpose_text} {user_scope_text}"

    # Check for example_queries - if present, compute centroid embedding
    example_queries = user_pa.get('example_queries', [])

    if example_queries and len(example_queries) > 0:
        # NEW: Compute centroid embedding from purpose/scope + example queries
        # This ensures the PA covers the semantic space of aligned queries
        all_texts = [user_pa_text] + list(example_queries)

        # Embed all texts
        all_embeddings = []
        for text in all_texts:
            emb = np.array(embedding_provider.encode(text))
            # Normalize each embedding before averaging
            emb = emb / (np.linalg.norm(emb) + 1e-10)
            all_embeddings.append(emb)

        # Compute centroid as mean of all embeddings
        user_embedding = np.mean(all_embeddings, axis=0)
        # Re-normalize the centroid
        user_embedding = user_embedding / (np.linalg.norm(user_embedding) + 1e-10)

        logger.info(f"PA centroid computed from {len(all_texts)} texts (1 purpose/scope + {len(example_queries)} examples)")
    else:
        # Original behavior: single embedding from purpose/scope
        user_embedding = np.array(embedding_provider.encode(user_pa_text))
        user_embedding = user_embedding / (np.linalg.norm(user_embedding) + 1e-10)

    # Build AI PA text for embedding
    ai_purpose = ai_pa.get('purpose', [])
    ai_scope = ai_pa.get('scope', [])

    ai_purpose_text = ' '.join(ai_purpose) if isinstance(ai_purpose, list) else str(ai_purpose)
    ai_scope_text = ' '.join(ai_scope) if isinstance(ai_scope, list) else str(ai_scope)
    ai_pa_text = f"{ai_purpose_text} {ai_scope_text}"

    # Compute AI embedding (no example queries for AI PA)
    ai_embedding = np.array(embedding_provider.encode(ai_pa_text))
    ai_embedding = ai_embedding / (np.linalg.norm(ai_embedding) + 1e-10)

    # Compute and log rho_PA (correlation between attractors)
    rho_pa = float(np.dot(user_embedding, ai_embedding))
    logger.info(f"PA Embeddings computed: user={len(user_embedding)}d, ai={len(ai_embedding)}d, rho_PA={rho_pa:.3f}")

    if rho_pa < 0.2:
        logger.warning(f"Low PA correlation ({rho_pa:.2f}). Attractors may not be well-aligned.")

    return user_embedding, ai_embedding


def compute_rho_pa(
    user_embedding: np.ndarray,
    ai_embedding: np.ndarray
) -> float:
    """
    Compute rho_PA - the correlation between user and AI attractors.

    This measures how well the AI PA is aligned with the User PA.
    Higher values indicate stronger coupling.

    Args:
        user_embedding: User PA embedding (normalized)
        ai_embedding: AI PA embedding (normalized)

    Returns:
        rho_PA value in [-1, 1], typically > 0.3 for well-derived PAs
    """
    return float(np.dot(user_embedding, ai_embedding))


def create_dual_pa_with_embeddings(
    user_pa: Dict[str, Any],
    embedding_provider,
    mistral_client: Optional[MistralClient] = None
) -> Dict[str, Any]:
    """
    Complete dual PA creation: derive AI PA and compute both embeddings.

    Main entry point for dual PA establishment.

    Args:
        user_pa: User's PA configuration (from PAExtractor or templates)
        embedding_provider: Embedding provider for vector computation
        mistral_client: Optional MistralClient for intent detection

    Returns:
        Dictionary containing:
        - user_pa: Original user PA
        - ai_pa: Derived AI PA
        - user_embedding: User PA vector embedding
        - ai_embedding: AI PA vector embedding
        - rho_pa: Correlation between attractors
        - governance_mode: 'dual' (always for this function)
    """
    # Step 1: Derive AI PA from User PA
    ai_pa = derive_ai_pa_from_user_pa(user_pa, mistral_client)

    # Step 2: Compute embeddings for both PAs
    user_embedding, ai_embedding = compute_pa_embeddings(user_pa, ai_pa, embedding_provider)

    # Step 3: Compute correlation
    rho_pa = compute_rho_pa(user_embedding, ai_embedding)

    logger.info(f"Dual PA created: rho_PA={rho_pa:.3f}, intent='{ai_pa.get('detected_intent')}'")

    return {
        'user_pa': user_pa,
        'ai_pa': ai_pa,
        'user_embedding': user_embedding,
        'ai_embedding': ai_embedding,
        'rho_pa': rho_pa,
        'governance_mode': 'dual'
    }

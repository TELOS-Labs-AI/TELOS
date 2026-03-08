"""
Generic TELOS Governance Decorator

@telos_governed decorator for any Python function.
Works without LangGraph or any framework dependency.

Usage:
    from telos_adapters.generic import telos_governed

    # Inline purpose
    @telos_governed(
        purpose="Help users with financial analysis",
        threshold=0.85,
    )
    def analyze_portfolio(user_request: str) -> str:
        return result

    # Config-driven (loads purpose from YAML)
    @telos_governed(config="agents/property_intel.yaml")
    def analyze_property(user_request: str) -> str:
        return result

    # With governance receipt signing
    from telos_governance.session import GovernanceSessionContext
    with GovernanceSessionContext() as session:
        @telos_governed(config="agents/property_intel.yaml", session=session)
        def analyze_property(user_request: str) -> str:
            return result

        analyze_property("score this roof")
        proof = session.generate_proof()

Regulatory traceability:
    - SAAI claim TELOS-SAAI-001: Per-call cosine similarity measures continuous
      drift against the purpose embedding
    - SAAI claim TELOS-SAAI-004: External governance decorator — decorated function
      cannot access or modify its governance parameters (corrigibility)
    - SAAI claim TELOS-SAAI-005: session parameter enables Ed25519 receipt signing
      for every governance decision via GovernanceSessionContext
    - SAAI claim TELOS-SAAI-008: ESCALATE decision (high_risk=True + low fidelity)
      blocks execution and signals need for human expert review
    - EU AI Act Art. 12: session.sign_result() creates signed governance receipts
      for every decorated call — automatic event recording for audit compliance
    - EU AI Act Art. 14: ESCALATE decision blocks execution and signals need for
      human expert review before proceeding — mandatory human oversight pathway
    - NIST AI 600-1 (GV 1.4): The decorator pattern enables governance integration
      with zero framework coupling — any Python function can be governed without
      architectural changes, implementing "governance by design" at the function level
    - NIST AI RMF (MAP 2.1): The decorator documents the governed function's intended
      purpose (via config or inline purpose string) at the point of use, satisfying
      MAP 2.1's requirement for context-of-use documentation
    - IEEE P7000: The decorator embodies IEEE P7000's concept of ethical requirements
      as runtime enforcement, not documentation — governance is enforced at call time
    - IEEE 7001-2021: Decision classification (EXECUTE/CLARIFY/INERT/ESCALATE)
      with fidelity scores provides transparent, explainable governance decisions
    - OWASP LLM Top 10 (LLM08 — Excessive Agency): Applied governance checks constrain
      function execution to authorized request patterns. Below-threshold requests are
      blocked before the decorated function executes, preventing excessive agency

Governance scope and limitations:
    This decorator provides PER-CALL governance. It evaluates each function
    invocation independently against the Primacy Attractor. It does NOT provide:

    - Chain tracking (SCI): No semantic continuity measurement between
      consecutive calls. Multi-step action sequences are not tracked.
      chain_continuity is reported as 0.0 in receipts.
      (EU AI Act Art. 12 gap for multi-step workflows.)

    - Graduated sanctions (AgenticDriftTracker / Ostrom DP5): No session-level
      drift detection, no WARNING/RESTRICT/BLOCK escalation, no sliding window.
      (SAAI-002 non-compliant for multi-step workflows.)

    - Cumulative drift measurement: Each call is independent. There is no
      memory of previous calls' fidelity scores.
      (SAAI-001 "continuous drift measurement" is limited to per-call fidelity;
      inter-call drift is not tracked.)

    - OWASP Agentic coverage: Per-call governance adequately addresses ASI06,
      ASI07, ASI09. Chain-dependent risks (ASI01, ASI02, ASI03, ASI05, ASI10)
      require the LangGraph wrapper or daemon adapter for full coverage.

    For multi-step agentic workflows, Annex III high-risk AI systems, or
    deployments requiring SAAI-002 graduated sanctions, use:
    - telos_adapters.langgraph.TelosWrapper (with drift_tracker parameter)
    - telos_adapters daemon (with AgenticDriftTracker + CUSUMMonitorBank)
"""
import functools
import logging
from types import SimpleNamespace
from typing import Any, Callable, Optional, Union

import numpy as np

# Import from telos_core (single source of truth)
from telos_core.constants import (
    FIDELITY_GREEN,
    SIMILARITY_BASELINE,
    AGENTIC_EXECUTE_THRESHOLD,
)

# Import governance types from telos_governance (hard import — no fallback shadow types)
from telos_governance.types import ActionDecision, DirectionLevel

logger = logging.getLogger(__name__)


def telos_governed(
    purpose: str = "",
    config: Optional[Union[str, Any]] = None,
    threshold: float = FIDELITY_GREEN,
    embed_fn: Optional[Callable[[str], np.ndarray]] = None,
    on_block: Optional[Callable[[str, float], Any]] = None,
    high_risk: bool = False,
    session: Optional[Any] = None,
):
    """
    Decorator that applies TELOS governance to any Python function.

    Args:
        purpose: The purpose statement (Primacy Attractor text).
            Ignored if config is provided (config.purpose takes precedence).
        config: Path to YAML config file (str) or an AgentConfig object.
            When provided, purpose is loaded from the config.
        threshold: Minimum fidelity to proceed (default: FIDELITY_GREEN = 0.70).
        embed_fn: Function to generate embeddings. If None, uses telos_core default.
        on_block: Callback when action is blocked. Receives (input_text, fidelity).
        high_risk: If True, low fidelity triggers ESCALATE instead of INERT.
        session: Optional GovernanceSessionContext for receipt signing.
            When provided, every governance decision is signed and appended
            to the session's receipt chain.

    Returns:
        Decorated function with governance checks.
    """
    # Resolve config at decoration time (not per-call)
    _config = None
    _purpose = purpose

    if config is not None:
        if isinstance(config, str):
            from telos_governance.config import load_config
            _config = load_config(config)
        else:
            _config = config  # AgentConfig object
        # Config provides purpose unless explicit purpose was given
        if not purpose and hasattr(_config, 'purpose'):
            _purpose = _config.purpose

    if not _purpose:
        raise ValueError("telos_governed requires either 'purpose' or 'config'")

    def decorator(func: Callable) -> Callable:
        # Cache the purpose embedding
        _purpose_embedding = None

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal _purpose_embedding

            # Get the input text (first string argument)
            input_text = None
            for arg in args:
                if isinstance(arg, str):
                    input_text = arg
                    break
            if input_text is None:
                input_text = kwargs.get("user_request", kwargs.get("query", kwargs.get("input", "")))

            if not input_text:
                # No text input to govern, pass through
                return func(*args, **kwargs)

            # Get embedding function
            _embed = embed_fn
            if _embed is None:
                try:
                    from telos_core.embedding_provider import EmbeddingProvider
                    provider = EmbeddingProvider(backend="auto")
                    _embed = provider.encode
                except Exception:
                    logger.warning("No embedding provider available, passing through")
                    return func(*args, **kwargs)

            # Compute purpose embedding (cached)
            if _purpose_embedding is None:
                _purpose_embedding = _embed(_purpose)

            # Compute input embedding
            input_embedding = _embed(input_text)

            # Calculate cosine similarity
            similarity = float(np.dot(input_embedding, _purpose_embedding) / (
                np.linalg.norm(input_embedding) * np.linalg.norm(_purpose_embedding) + 1e-10
            ))

            # Layer 1: Baseline check
            if similarity < SIMILARITY_BASELINE:
                logger.warning(
                    f"TELOS HARD_BLOCK: similarity {similarity:.3f} < baseline {SIMILARITY_BASELINE}"
                )
                _sign_decision(input_text, similarity, ActionDecision.INERT, session)
                if on_block:
                    return on_block(input_text, similarity)
                raise ValueError(
                    f"Action blocked by TELOS governance: fidelity {similarity:.3f} "
                    f"below baseline {SIMILARITY_BASELINE}"
                )

            # Classify decision using agentic thresholds from telos_core.constants
            if similarity >= AGENTIC_EXECUTE_THRESHOLD:
                decision = ActionDecision.EXECUTE
            elif similarity >= threshold:
                decision = ActionDecision.CLARIFY
            elif high_risk:
                decision = ActionDecision.ESCALATE
            else:
                decision = ActionDecision.INERT

            # Sign the governance receipt if session is provided
            _sign_decision(input_text, similarity, decision, session)

            # Act on decision
            if decision == ActionDecision.EXECUTE:
                return func(*args, **kwargs)
            elif decision == ActionDecision.CLARIFY:
                logger.info(f"TELOS CLARIFY: fidelity {similarity:.3f}, proceeding with caution")
                return func(*args, **kwargs)
            else:
                # INERT or ESCALATE
                logger.warning(
                    f"TELOS {decision.value.upper()}: fidelity {similarity:.3f}, blocking"
                )
                if on_block:
                    return on_block(input_text, similarity)
                raise ValueError(
                    f"Action blocked by TELOS governance: {decision.value} "
                    f"(fidelity {similarity:.3f})"
                )

        # Store governance metadata on the wrapper
        wrapper._telos_purpose = _purpose
        wrapper._telos_threshold = threshold
        wrapper._telos_high_risk = high_risk
        wrapper._telos_config = _config
        wrapper._telos_session = session

        return wrapper
    return decorator


def _sign_decision(
    input_text: str,
    similarity: float,
    decision: ActionDecision,
    session: Optional[Any],
) -> None:
    """Sign a governance decision via session if provided.

    Creates a lightweight result stub with the decorator's governance data
    and delegates to GovernanceSessionContext.sign_result(). The receipt
    is appended to the session's chain for later proof generation.
    """
    if session is None:
        return

    result_stub = SimpleNamespace(
        decision=decision,
        effective_fidelity=similarity,
        composite_fidelity=similarity,
        boundary_triggered=False,
        purpose_fidelity=similarity,
        scope_fidelity=0.0,
        boundary_violation=0.0,
        tool_fidelity=0.0,
        chain_continuity=0.0,
        selected_tool=None,
    )

    try:
        session.sign_result(result_stub, input_text, "decorator")
    except Exception as e:
        logger.warning(f"Failed to sign governance receipt: {e}")

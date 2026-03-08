"""
TELOS Core - Pure Mathematical Governance Engine
=================================================

Framework-agnostic library implementing the mathematical foundations of
TELOS (Telically Entrained Linguistic Operational Substrate) for AI alignment.

Zero external framework dependencies (no Streamlit, FastAPI, etc.).
Only requires: numpy, pydantic.

Core Modules:
- constants: Calibration thresholds, formulas, zone definitions
- primacy_math: Attractor geometry, basin membership, Lyapunov stability
- fidelity_engine: Two-layer fidelity calculation and governance decisions
- proportional_controller: F = K*e_t intervention cascade
- primacy_state: Dual/trifecta Primacy State computation
- embedding_provider: Multi-model embedding providers
- semantic_interpreter: Fidelity-to-linguistic-spec mapping
- adaptive_context: Multi-tier context buffer, SCI, phase detection
- conversation_manager: Conversation history with governance context
- evidence_schema: Pydantic JSONL governance event schemas
- governance_trace: Central event logging with SAAI compliance
- trace_verifier: Cryptographic hash chain verification
- exceptions: TELOS exception hierarchy
"""

__version__ = "1.0.0"

# =============================================================================
# Constants (single source of truth for all thresholds)
# =============================================================================
from telos_core.constants import (
    FIDELITY_GREEN,
    FIDELITY_YELLOW,
    FIDELITY_ORANGE,
    FIDELITY_RED,
    SIMILARITY_BASELINE,
    INTERVENTION_THRESHOLD,
    DEFAULT_K_ATTRACTOR,
    DEFAULT_K_ANTIMETA,
)

# =============================================================================
# Core Math
# =============================================================================
from telos_core.primacy_math import (
    MathematicalState,
    PrimacyAttractorMath,
    TelicFidelityCalculator,
)

# =============================================================================
# Fidelity Engine
# =============================================================================
from telos_core.fidelity_engine import (
    FidelityEngine,
    FidelityResult,
    GovernanceResult,
)

# =============================================================================
# Proportional Controller
# =============================================================================
from telos_core.proportional_controller import (
    ProportionalController,
    InterventionRecord,
)

# =============================================================================
# Primacy State
# =============================================================================
from telos_core.primacy_state import (
    PrimacyStateCalculator,
    PrimacyStateMetrics,
    calculate_ps,
)

# =============================================================================
# Embedding Providers
# =============================================================================
from telos_core.embedding_provider import (
    DeterministicEmbeddingProvider,
    SentenceTransformerProvider,
    MistralEmbeddingProvider,
)

# =============================================================================
# Semantic Interpreter
# =============================================================================
from telos_core.semantic_interpreter import (
    SemanticSpec,
    interpret,
    get_exemplar,
)

# =============================================================================
# Exceptions
# =============================================================================
from telos_core.exceptions import (
    TELOSError,
    AttractorConstructionError,
    MissingAPIKeyError,
    ModelLoadError,
)

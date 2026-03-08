"""
TELOS Fidelity Engine - Shared Mathematical Core
=================================================

SAAI Framework Alignment: Core fidelity computation module shared across
Observatory UI (Streamlit) and Gateway API (FastAPI).

This module provides pure mathematical operations with NO framework dependencies
(no Streamlit, no FastAPI). It can be imported into any context.

Mathematical Foundation:
------------------------
The fidelity calculation is based on cosine similarity in embedding space,
measuring how well user input/tool descriptions align with the Primacy Attractor.

Two-Layer Architecture:
  - Layer 1: Baseline pre-filter (raw_similarity < 0.20 = extreme off-topic)
  - Layer 2: Basin membership (normalized_fidelity < 0.48 = purpose drift)

Graduated Governance Decisions (per Technical Brief):
  - EXECUTE:  fidelity >= 0.45 - Proceed with execution
  - CLARIFY:  fidelity 0.35-0.45 - Request clarification from agent
  - ESCALATE: fidelity < 0.35 - Require human review

Usage:
    from telos_core.fidelity_engine import (
        FidelityEngine,
        GovernanceDecision,
        FidelityZone,
        calculate_cosine_similarity,
    )

    engine = FidelityEngine()
    result = engine.calculate_fidelity(input_embedding, pa_embedding)
    decision = engine.make_governance_decision(result.normalized_fidelity)
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np
import logging

# Import constants from single source of truth
from telos_core.constants import (
    # Intervention decision thresholds
    SIMILARITY_BASELINE,
    INTERVENTION_THRESHOLD,
    BASIN_CENTER,
    BASIN_TOLERANCE,
    # Display zone thresholds (normalized 0-1 scale)
    FIDELITY_GREEN,
    FIDELITY_YELLOW,
    FIDELITY_ORANGE,
    FIDELITY_RED,
    # Model-specific raw thresholds
    ST_FIDELITY_GREEN,
    ST_FIDELITY_YELLOW,
    ST_FIDELITY_ORANGE,
    ST_FIDELITY_RED,
    get_thresholds_for_model,
    # SAAI cumulative drift thresholds
    SAAI_DRIFT_WARNING,
    SAAI_DRIFT_RESTRICT,
    SAAI_DRIFT_BLOCK,
    BASELINE_TURN_COUNT,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class FidelityZone(str, Enum):
    """Fidelity display zones for UI coloring."""
    GREEN = "green"      # >= 0.70 - Aligned (no intervention)
    YELLOW = "yellow"    # 0.60-0.69 - Minor drift (context injection)
    ORANGE = "orange"    # 0.50-0.59 - Drift detected (Steward redirect)
    RED = "red"          # < 0.50 - Significant drift (block + review)


class GovernanceDecision(str, Enum):
    """
    Graduated governance decisions for Gateway tool-level control.

    Per TELOS Gateway Technical Brief v1.0, decisions are graduated
    to avoid binary pass/fail and enable nuanced agent guidance.
    """
    EXECUTE = "execute"      # Proceed with tool/request
    CLARIFY = "clarify"      # Request clarification from agent
    ESCALATE = "escalate"    # Require human review (SAAI drift or low fidelity)


class InterventionType(str, Enum):
    """Types of interventions for logging and tracing."""
    NONE = "none"
    CONTEXT_INJECTION = "context_injection"
    REGENERATION = "regeneration"
    HARD_BLOCK = "hard_block"
    HUMAN_REVIEW = "human_review"


@dataclass
class FidelityResult:
    """
    Complete fidelity calculation result.

    Contains both raw and normalized values, layer decisions,
    and zone classification.
    """
    raw_similarity: float
    normalized_fidelity: float
    layer1_hard_block: bool      # Raw < SIMILARITY_BASELINE (0.20)
    layer2_outside_basin: bool   # Normalized < INTERVENTION_THRESHOLD (0.48)
    zone: FidelityZone
    should_intervene: bool

    def to_dict(self) -> Dict:
        """Serialize for JSON/logging."""
        return {
            "raw_similarity": round(self.raw_similarity, 4),
            "normalized_fidelity": round(self.normalized_fidelity, 4),
            "layer1_hard_block": self.layer1_hard_block,
            "layer2_outside_basin": self.layer2_outside_basin,
            "zone": self.zone.value,
            "should_intervene": self.should_intervene,
        }


@dataclass
class GovernanceResult:
    """
    Complete governance decision result for Gateway.

    Extends FidelityResult with decision and tool-level analysis.
    """
    fidelity: FidelityResult
    decision: GovernanceDecision
    confidence: float                           # 0.0-1.0 confidence in decision
    tool_fidelities: Optional[Dict[str, float]] = None  # Per-tool fidelities
    lowest_tool_fidelity: Optional[float] = None
    recommendation: Optional[str] = None        # Human-readable guidance
    requires_acknowledgment: bool = False       # SAAI BLOCK level

    def to_dict(self) -> Dict:
        """Serialize for JSON/logging."""
        result = {
            "fidelity": self.fidelity.to_dict(),
            "decision": self.decision.value,
            "confidence": round(self.confidence, 4),
            "requires_acknowledgment": self.requires_acknowledgment,
        }
        if self.tool_fidelities:
            result["tool_fidelities"] = {
                k: round(v, 4) for k, v in self.tool_fidelities.items()
            }
        if self.lowest_tool_fidelity is not None:
            result["lowest_tool_fidelity"] = round(self.lowest_tool_fidelity, 4)
        if self.recommendation:
            result["recommendation"] = self.recommendation
        return result


# ============================================================================
# Core Mathematical Functions (Pure)
# ============================================================================

def calculate_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Calculate cosine similarity between two vectors.

    This is the fundamental operation for all fidelity calculations.

    Args:
        vec1: First embedding vector
        vec2: Second embedding vector

    Returns:
        Cosine similarity in range [-1, 1] (typically [0, 1] for embeddings)
    """
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    result = float(dot_product / (norm1 * norm2))

    # NaN guard: corrupted embeddings must not bypass governance (fail-closed)
    if math.isnan(result):
        logger.warning("NaN detected in cosine similarity — returning 0.0 (fail-closed)")
        return 0.0

    return result


def normalize_fidelity(
    raw_similarity: float,
    slope: float = 1.167,
    intercept: float = 0.117
) -> float:
    """
    Transform raw cosine similarity to normalized display scale.

    Default calibration (2025-12-28 CENTROID):
        Raw 0.50 -> Display 0.70 (GREEN threshold)
        Raw 0.41 -> Display 0.60 (YELLOW threshold)
        Raw 0.33 -> Display 0.50 (ORANGE threshold)
        Raw 0.20 -> Display 0.35 (RED zone)

    Formula: display = slope * raw + intercept

    Args:
        raw_similarity: Raw cosine similarity from embedding model
        slope: Linear transformation slope (default 1.167)
        intercept: Linear transformation intercept (default 0.117)

    Returns:
        Normalized fidelity clamped to [0, 1]
    """
    # NaN guard: corrupted input must fail to lowest fidelity (fail-closed)
    if math.isnan(raw_similarity):
        return 0.0
    display = slope * raw_similarity + intercept
    return max(0.0, min(1.0, display))


def normalize_mistral_fidelity(
    raw_similarity: float,
    floor: float = 0.55,
    aligned: float = 0.70,
) -> float:
    """
    Normalize Mistral embedding similarity to TELOS fidelity zones.

    Mistral embeddings (1024-dim) produce a narrow discriminative range:
    - Off-topic content: 0.55-0.65 raw similarity
    - On-topic content: 0.70-0.80 raw similarity

    Piecewise linear mapping to TELOS fidelity zones:
    - < floor (0.55):   Clearly off-topic -> RED (0.0-0.30)
    - floor-aligned:    Ambiguous/drift   -> YELLOW/ORANGE (0.30-0.70)
    - > aligned (0.70): On-topic          -> GREEN (0.70-1.0)

    Args:
        raw_similarity: Raw cosine similarity from Mistral embeddings
        floor: Raw similarity below which content is clearly unrelated
        aligned: Raw similarity above which content is clearly on-topic

    Returns:
        Normalized fidelity clamped to [0, 1]
    """
    # NaN guard: fail-closed (defense in depth — current argument order is accidentally safe)
    if math.isnan(raw_similarity):
        return 0.0
    if raw_similarity < floor:
        fidelity = (raw_similarity / floor) * 0.30
    elif raw_similarity < aligned:
        fidelity = 0.30 + (
            (raw_similarity - floor) / (aligned - floor)
        ) * 0.40
    else:
        fidelity = 0.70 + (
            (raw_similarity - aligned) / (1.0 - aligned)
        ) * 0.30

    return float(min(1.0, max(0.0, fidelity)))


def classify_fidelity_zone(
    fidelity: float,
    green: Optional[float] = None,
    yellow: Optional[float] = None,
    orange: Optional[float] = None,
) -> FidelityZone:
    """
    Map normalized fidelity to display zone.

    Zones:
        GREEN:  >= 0.70 - Aligned (no intervention)
        YELLOW: 0.60-0.69 - Minor drift (context injection)
        ORANGE: 0.50-0.59 - Drift detected (Steward redirect)
        RED:    < 0.50 - Significant drift (block + review)

    Args:
        fidelity: Normalized fidelity score
        green: Optional override for GREEN threshold (default: FIDELITY_GREEN)
        yellow: Optional override for YELLOW threshold (default: FIDELITY_YELLOW)
        orange: Optional override for ORANGE threshold (default: FIDELITY_ORANGE)

    Returns:
        FidelityZone enum value
    """
    g = green if green is not None else FIDELITY_GREEN
    y = yellow if yellow is not None else FIDELITY_YELLOW
    o = orange if orange is not None else FIDELITY_ORANGE

    if fidelity >= g:
        return FidelityZone.GREEN
    elif fidelity >= y:
        return FidelityZone.YELLOW
    elif fidelity >= o:
        return FidelityZone.ORANGE
    else:
        return FidelityZone.RED


def check_layer1_hard_block(raw_similarity: float) -> bool:
    """
    Layer 1 Check: Extreme off-topic detection.

    If raw cosine similarity is below SIMILARITY_BASELINE (0.20),
    the input is so far from the PA that it's clearly off-topic.

    Args:
        raw_similarity: Raw cosine similarity

    Returns:
        True if hard block should be triggered
    """
    # NaN must trigger hard block (fail-closed)
    if math.isnan(raw_similarity):
        return True
    return raw_similarity < SIMILARITY_BASELINE


def check_layer2_outside_basin(normalized_fidelity: float) -> bool:
    """
    Layer 2 Check: Basin membership (purpose drift).

    If normalized fidelity is below INTERVENTION_THRESHOLD (0.48),
    the user has drifted outside the primacy basin.

    Args:
        normalized_fidelity: Normalized fidelity score

    Returns:
        True if outside the primacy basin
    """
    return normalized_fidelity < INTERVENTION_THRESHOLD


def should_intervene(
    raw_similarity: float,
    normalized_fidelity: float
) -> bool:
    """
    Determine if governance intervention is needed.

    Two-layer decision:
        - Layer 1: raw_similarity < 0.20 (extreme off-topic)
        - Layer 2: normalized_fidelity < 0.70 (any zone below GREEN)

    Per CLAUDE.md: should_intervene = (raw < 0.20) OR (fidelity < 0.70)

    Args:
        raw_similarity: Raw cosine similarity
        normalized_fidelity: Normalized fidelity score

    Returns:
        True if intervention should occur
    """
    layer1_block = check_layer1_hard_block(raw_similarity)
    layer2_drift = normalized_fidelity < FIDELITY_GREEN

    return layer1_block or layer2_drift


# ============================================================================
# Governance Decision Functions
# ============================================================================

def make_governance_decision(
    input_fidelity: float,
    tool_fidelities: Optional[Dict[str, float]] = None,
    saai_drift_level: Optional[str] = None
) -> GovernanceDecision:
    """
    Make graduated governance decision based on fidelity scores.

    3-verdict model:
        EXECUTE:  >= 0.45 - All systems go
        CLARIFY:  0.35-0.45 - Need more context
        ESCALATE: < 0.35 or SAAI drift - Require human review

    If tool_fidelities provided, uses MINIMUM across all tools
    (weakest link determines overall decision).

    Args:
        input_fidelity: User input fidelity score
        tool_fidelities: Optional dict of tool_name -> fidelity
        saai_drift_level: Optional SAAI drift level ('warning', 'restrict', 'block')

    Returns:
        GovernanceDecision enum value
    """
    # SAAI escalation takes precedence
    if saai_drift_level == "block":
        return GovernanceDecision.ESCALATE

    # Determine effective fidelity (minimum of input and all tools)
    effective_fidelity = input_fidelity

    if tool_fidelities:
        min_tool_fidelity = min(tool_fidelities.values()) if tool_fidelities else 1.0
        effective_fidelity = min(input_fidelity, min_tool_fidelity)

    # 3-tier graduated decision thresholds
    if effective_fidelity >= 0.45:
        return GovernanceDecision.EXECUTE
    elif effective_fidelity >= 0.35:
        return GovernanceDecision.CLARIFY
    else:
        return GovernanceDecision.ESCALATE


def calculate_decision_confidence(
    fidelity: float,
    decision: GovernanceDecision
) -> float:
    """
    Calculate confidence level for governance decision.

    Higher confidence when fidelity is clearly within a decision band.
    Lower confidence near boundaries.

    Args:
        fidelity: Effective fidelity score
        decision: The governance decision made

    Returns:
        Confidence score 0.0-1.0
    """
    # Define band centers
    band_centers = {
        GovernanceDecision.EXECUTE: 0.70,
        GovernanceDecision.CLARIFY: 0.40,
        GovernanceDecision.ESCALATE: 0.20,
    }

    # Distance from band center (normalized)
    center = band_centers.get(decision, 0.50)
    distance = abs(fidelity - center)

    # Convert distance to confidence (closer = higher confidence)
    # Max distance is 0.5, so confidence = 1 - 2*distance, clamped to [0.3, 1.0]
    confidence = max(0.3, min(1.0, 1.0 - 2 * distance))

    return confidence


def generate_recommendation(
    decision: GovernanceDecision,
    input_fidelity: float,
    tool_fidelities: Optional[Dict[str, float]] = None
) -> str:
    """
    Generate human-readable recommendation for governance decision.

    Args:
        decision: The governance decision
        input_fidelity: User input fidelity
        tool_fidelities: Optional per-tool fidelities

    Returns:
        Recommendation string
    """
    recommendations = {
        GovernanceDecision.EXECUTE: "Request aligned with purpose. Proceed.",
        GovernanceDecision.CLARIFY: "Request unclear. Ask agent for clarification.",
        GovernanceDecision.ESCALATE: "Request outside purpose scope. Human review required.",
    }

    base = recommendations.get(decision, "Unknown decision state.")

    # Add tool-specific guidance if tools have lower fidelity
    if tool_fidelities:
        low_fidelity_tools = [
            name for name, f in tool_fidelities.items() if f < input_fidelity - 0.1
        ]
        if low_fidelity_tools:
            base += f" Low-alignment tools: {', '.join(low_fidelity_tools)}"

    return base


# ============================================================================
# FidelityEngine Class - Main Interface
# ============================================================================

class FidelityEngine:
    """
    TELOS Fidelity Engine - Unified mathematical core for governance.

    Provides a clean interface for both Observatory (Streamlit) and
    Gateway (FastAPI) to perform fidelity calculations and governance
    decisions using the same underlying math.

    Example:
        engine = FidelityEngine()

        # Simple fidelity calculation
        result = engine.calculate_fidelity(input_embedding, pa_embedding)
        print(f"Fidelity: {result.normalized_fidelity:.2f} ({result.zone.value})")

        # Full governance decision with tools
        gov_result = engine.evaluate_request(
            input_embedding=input_emb,
            pa_embedding=pa_emb,
            tool_descriptions={"read_file": "Read contents of a file"},
        )
        print(f"Decision: {gov_result.decision.value}")
    """

    def __init__(
        self,
        normalize_slope: float = 1.167,
        normalize_intercept: float = 0.117,
        model_type: str = "sentence_transformer"
    ):
        """
        Initialize the Fidelity Engine.

        Args:
            normalize_slope: Linear transformation slope
            normalize_intercept: Linear transformation intercept
            model_type: Embedding model type for threshold selection
        """
        self.normalize_slope = normalize_slope
        self.normalize_intercept = normalize_intercept
        self.model_type = model_type
        self.thresholds = get_thresholds_for_model(model_type)

        logger.info(f"FidelityEngine initialized (model_type={model_type})")

    def calculate_fidelity(
        self,
        input_embedding: np.ndarray,
        pa_embedding: np.ndarray
    ) -> FidelityResult:
        """
        Calculate complete fidelity result for input vs PA.

        Args:
            input_embedding: Embedding of user input
            pa_embedding: Primacy Attractor embedding

        Returns:
            FidelityResult with all metrics
        """
        # Core calculation
        raw_sim = calculate_cosine_similarity(input_embedding, pa_embedding)

        # Normalize for display
        normalized = normalize_fidelity(
            raw_sim,
            slope=self.normalize_slope,
            intercept=self.normalize_intercept
        )

        # Layer checks
        layer1 = check_layer1_hard_block(raw_sim)
        layer2 = check_layer2_outside_basin(normalized)

        # Zone classification
        zone = classify_fidelity_zone(normalized)

        # Intervention decision
        intervene = should_intervene(raw_sim, normalized)

        return FidelityResult(
            raw_similarity=raw_sim,
            normalized_fidelity=normalized,
            layer1_hard_block=layer1,
            layer2_outside_basin=layer2,
            zone=zone,
            should_intervene=intervene,
        )

    def calculate_tool_fidelities(
        self,
        tool_embeddings: Dict[str, np.ndarray],
        pa_embedding: np.ndarray
    ) -> Dict[str, float]:
        """
        Calculate fidelity for each tool description vs PA.

        Args:
            tool_embeddings: Dict of tool_name -> embedding
            pa_embedding: Primacy Attractor embedding

        Returns:
            Dict of tool_name -> normalized_fidelity
        """
        tool_fidelities = {}

        for name, embedding in tool_embeddings.items():
            result = self.calculate_fidelity(embedding, pa_embedding)
            tool_fidelities[name] = result.normalized_fidelity

        return tool_fidelities

    def evaluate_request(
        self,
        input_embedding: np.ndarray,
        pa_embedding: np.ndarray,
        tool_embeddings: Optional[Dict[str, np.ndarray]] = None,
        saai_drift_level: Optional[str] = None
    ) -> GovernanceResult:
        """
        Full governance evaluation for a request.

        This is the main entry point for Gateway-style governance.
        Evaluates both user input AND all tools against the PA.

        Args:
            input_embedding: Embedding of user input
            pa_embedding: Primacy Attractor embedding
            tool_embeddings: Optional dict of tool_name -> embedding
            saai_drift_level: Optional current SAAI drift level

        Returns:
            GovernanceResult with full decision context
        """
        # Calculate input fidelity
        fidelity_result = self.calculate_fidelity(input_embedding, pa_embedding)

        # Calculate tool fidelities if provided
        tool_fidelities = None
        lowest_tool_fidelity = None

        if tool_embeddings:
            tool_fidelities = self.calculate_tool_fidelities(
                tool_embeddings, pa_embedding
            )
            lowest_tool_fidelity = min(tool_fidelities.values()) if tool_fidelities else None

        # Make governance decision
        decision = make_governance_decision(
            input_fidelity=fidelity_result.normalized_fidelity,
            tool_fidelities=tool_fidelities,
            saai_drift_level=saai_drift_level,
        )

        # Calculate confidence
        effective_fidelity = fidelity_result.normalized_fidelity
        if lowest_tool_fidelity is not None:
            effective_fidelity = min(effective_fidelity, lowest_tool_fidelity)

        confidence = calculate_decision_confidence(effective_fidelity, decision)

        # Generate recommendation
        recommendation = generate_recommendation(
            decision=decision,
            input_fidelity=fidelity_result.normalized_fidelity,
            tool_fidelities=tool_fidelities,
        )

        return GovernanceResult(
            fidelity=fidelity_result,
            decision=decision,
            confidence=confidence,
            tool_fidelities=tool_fidelities,
            lowest_tool_fidelity=lowest_tool_fidelity,
            recommendation=recommendation,
            requires_acknowledgment=(saai_drift_level == "block"),
        )

    def batch_evaluate_tools(
        self,
        tools: List[Dict[str, str]],
        pa_embedding: np.ndarray,
        embedding_fn
    ) -> Dict[str, float]:
        """
        Batch evaluate tool descriptions against PA.

        Utility method for Gateway integration. Takes tool dicts
        with 'name' and 'description' keys.

        Args:
            tools: List of tool dicts with 'name' and 'description'
            pa_embedding: Primacy Attractor embedding
            embedding_fn: Function to embed text (e.g., provider.encode)

        Returns:
            Dict of tool_name -> normalized_fidelity
        """
        tool_fidelities = {}

        for tool in tools:
            name = tool.get("name", tool.get("function", {}).get("name", "unknown"))
            description = tool.get("description",
                                   tool.get("function", {}).get("description", ""))

            if description:
                tool_embedding = np.array(embedding_fn(description))
                result = self.calculate_fidelity(tool_embedding, pa_embedding)
                tool_fidelities[name] = result.normalized_fidelity
            else:
                # No description = can't assess = assume aligned
                tool_fidelities[name] = 1.0

        return tool_fidelities


# ============================================================================
# SAAI Drift Calculation Utilities
# ============================================================================

def calculate_drift_from_baseline(
    current_avg_fidelity: float,
    baseline_fidelity: float
) -> float:
    """
    Calculate drift magnitude from baseline.

    Per SAAI Framework:
        drift = (baseline - current) / baseline

    Args:
        current_avg_fidelity: Current session average fidelity
        baseline_fidelity: Baseline fidelity established at session start

    Returns:
        Drift magnitude (0.0 = no drift, 0.10 = 10% drift, etc.)
    """
    if baseline_fidelity <= 0:
        return 0.0

    drift = (baseline_fidelity - current_avg_fidelity) / baseline_fidelity
    return max(0.0, drift)  # Drift is always non-negative


def classify_saai_drift_level(drift_magnitude: float) -> str:
    """
    Classify drift magnitude into SAAI tier.

    Per SAAI Framework:
        < 10%: normal - no action
        10-15%: warning - mandatory review triggered
        15-20%: restrict - tighten thresholds
        > 20%: block - halt until human acknowledgment

    Args:
        drift_magnitude: Drift as fraction (0.10 = 10%)

    Returns:
        Drift level string: 'normal', 'warning', 'restrict', or 'block'
    """
    if drift_magnitude >= SAAI_DRIFT_BLOCK:
        return "block"
    elif drift_magnitude >= SAAI_DRIFT_RESTRICT:
        return "restrict"
    elif drift_magnitude >= SAAI_DRIFT_WARNING:
        return "warning"
    else:
        return "normal"


# ============================================================================
# Convenience Functions for Migration
# ============================================================================

def legacy_calculate_user_fidelity(
    user_embedding: np.ndarray,
    pa_embedding: np.ndarray,
    normalize: bool = True
) -> Tuple[float, float, bool]:
    """
    Legacy-compatible fidelity calculation.

    Returns tuple matching old beta_response_manager interface:
        (fidelity, raw_similarity, baseline_hard_block)

    Use this for gradual migration from existing code.

    Args:
        user_embedding: User input embedding
        pa_embedding: Primacy Attractor embedding
        normalize: Whether to normalize fidelity

    Returns:
        Tuple of (fidelity, raw_similarity, baseline_hard_block)
    """
    raw_sim = calculate_cosine_similarity(user_embedding, pa_embedding)

    if normalize:
        fidelity = normalize_fidelity(raw_sim)
    else:
        fidelity = raw_sim

    hard_block = check_layer1_hard_block(raw_sim)

    return (fidelity, raw_sim, hard_block)


# ============================================================================
# Module-level instance for simple usage
# ============================================================================

# Default engine instance for quick access
_default_engine: Optional[FidelityEngine] = None


def get_default_engine() -> FidelityEngine:
    """Get or create the default FidelityEngine instance."""
    global _default_engine
    if _default_engine is None:
        _default_engine = FidelityEngine()
    return _default_engine

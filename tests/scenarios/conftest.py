"""
Shared fixtures for Property Intelligence scenario tests.
=========================================================

Provides deterministic embedding infrastructure and pre-configured
governance components for counterfactual Nearmap/ITEL-style property
assessment scenarios.

Embedding Design Strategy
-------------------------
Uses 8D vectors with controlled cosine similarities:

  Dimensions:
  [0] purpose    -- alignment with property assessment PA
  [1] tool_1     -- property_lookup discriminator
  [2] tool_2     -- aerial_image_retrieve discriminator
  [3] tool_3     -- roof_condition_score discriminator
  [4] tool_4     -- peril_risk_score discriminator
  [5] tool_5     -- generate_property_report discriminator
  [6] drift_a    -- off-topic indicator A
  [7] drift_b    -- off-topic indicator B

Design rationale:
- Purpose axis controls fidelity gate decisions (EXECUTE/CLARIFY/etc.)
- Per-tool axes give each tool its own discriminative dimension so
  tool selection reliably picks the correct tool (avoids the "all tools
  look the same" problem when purpose dominates).
- Drift axes capture off-topic and boundary-violation content.

On-topic requests: high purpose (0.80), high on correct tool axis
Off-topic requests: low purpose (0.02-0.10), high on drift axes
Boundary violations: low purpose (0.12-0.25), high on drift axes
CLARIFY tier: moderate purpose (0.40), distributed tool signal
ESCALATE tier: lower purpose (< 0.35), partial drift
"""

import numpy as np
import pytest

from telos_governance.fidelity_gate import FidelityGate
from telos_governance.pa_extractor import PrimacyAttractor
from telos_governance.tool_selection_gate import ToolDefinition, ToolSelectionGate
from telos_governance.action_chain import ActionChain


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def _make_embedding(values: list) -> np.ndarray:
    """Create a normalized embedding vector."""
    v = np.array(values, dtype=np.float64)
    norm = np.linalg.norm(v)
    if norm > 0:
        v = v / norm
    return v


def _make_embed_fn(mapping: dict, default=None):
    """
    Return an embed_fn that matches substrings to embeddings.

    Args:
        mapping: dict of substring -> np.ndarray
        default: fallback embedding if no match (uses drift vector if None)
    """
    drift_default = _make_embedding([0.05, 0.02, 0.02, 0.02, 0.02, 0.02, 0.70, 0.70])

    def embed_fn(text: str) -> np.ndarray:
        text_lower = text.lower()
        for key, emb in mapping.items():
            if key.lower() in text_lower:
                return emb
        return default if default is not None else drift_default

    return embed_fn


# ---------------------------------------------------------------------------
# Property Intelligence PA
# ---------------------------------------------------------------------------

PROPERTY_INTEL_PA_TEXT = (
    "You are a Property Intelligence Agent for aerial AI underwriting. "
    "Analyze Nearmap-style aerial imagery to assess roof condition (RSI 0-100), "
    "detection layers (81/82/83/84/259/297/53), peril vulnerability scores "
    "(hail, wind, wildfire), and generate property underwriting reports. "
    "Do not make binding coverage decisions, override human field assessors, "
    "or access policyholder PII beyond property address."
)


# ---------------------------------------------------------------------------
# Property Intelligence tool definitions
# ---------------------------------------------------------------------------

PROPERTY_INTEL_TOOLS = [
    ToolDefinition(
        name="property_lookup",
        description=(
            "Look up property information by address. Returns parcel data, "
            "geocoded location, and property characteristics for underwriting."
        ),
    ),
    ToolDefinition(
        name="aerial_image_retrieve",
        description=(
            "Retrieve latest aerial imagery for a property parcel. Returns "
            "sub-3-inch GSD orthomosaic imagery metadata and capture date."
        ),
    ),
    ToolDefinition(
        name="roof_condition_score",
        description=(
            "Run AI roof condition assessment on aerial imagery. Returns "
            "Roof Structural Integrity score (RSI 0-100), RCCS confidence "
            "(0.80-0.95), and detection layer results for layers 81/82/83/84."
        ),
    ),
    ToolDefinition(
        name="peril_risk_score",
        description=(
            "Calculate peril vulnerability scores for a property. Returns "
            "hail risk, wind vulnerability, wildfire exposure, and composite "
            "peril score using detection layers 259/297/53."
        ),
    ),
    ToolDefinition(
        name="generate_property_report",
        description=(
            "Generate a comprehensive underwriting property report. Combines "
            "property data, aerial imagery analysis, roof condition score, "
            "and peril risk assessment into a formatted report."
        ),
    ),
]


# ---------------------------------------------------------------------------
# 8D Embedding maps -- deterministic vectors for scenario reproducibility
# ---------------------------------------------------------------------------
# Dimensions: [purpose, tool1, tool2, tool3, tool4, tool5, drift_a, drift_b]

# PA embedding: strong purpose, neutral across tools, zero drift
_PA_EMBEDDING = _make_embedding([0.95, 0.15, 0.15, 0.15, 0.15, 0.15, 0.0, 0.0])

# Tool embeddings: moderate purpose + dominant on own tool axis
_TOOL_EMBEDDINGS = {
    "property_lookup":          _make_embedding([0.60, 0.70, 0.10, 0.10, 0.10, 0.10, 0.0, 0.0]),
    "aerial_image_retrieve":    _make_embedding([0.60, 0.10, 0.70, 0.10, 0.10, 0.10, 0.0, 0.0]),
    "roof_condition_score":     _make_embedding([0.60, 0.10, 0.10, 0.70, 0.10, 0.10, 0.0, 0.0]),
    "peril_risk_score":         _make_embedding([0.60, 0.10, 0.10, 0.10, 0.70, 0.10, 0.0, 0.0]),
    "generate_property_report": _make_embedding([0.60, 0.10, 0.10, 0.10, 0.10, 0.70, 0.0, 0.0]),
}

# On-topic request embeddings: high purpose + correct tool axis
# purpose=0.80 → raw similarity ~0.87 vs PA → fidelity ~0.87 → EXECUTE
_ON_TOPIC_EMBEDDINGS = {
    # Scenario 1: Standard underwriting workflow
    "look up property":           _make_embedding([0.80, 0.60, 0.05, 0.05, 0.05, 0.05, 0.0, 0.0]),
    "742 evergreen terrace":      _make_embedding([0.80, 0.60, 0.05, 0.05, 0.05, 0.05, 0.0, 0.0]),
    "retrieve the latest aerial": _make_embedding([0.80, 0.05, 0.60, 0.05, 0.05, 0.05, 0.0, 0.0]),
    "aerial photograph":          _make_embedding([0.80, 0.05, 0.60, 0.05, 0.05, 0.05, 0.0, 0.0]),
    "show me the aerial":         _make_embedding([0.80, 0.05, 0.60, 0.05, 0.05, 0.05, 0.0, 0.0]),
    "run ai roof condition":      _make_embedding([0.80, 0.05, 0.05, 0.60, 0.05, 0.05, 0.0, 0.0]),
    "roof condition assessment":  _make_embedding([0.80, 0.05, 0.05, 0.60, 0.05, 0.05, 0.0, 0.0]),
    "is this roof in good condition": _make_embedding([0.80, 0.05, 0.05, 0.60, 0.05, 0.05, 0.0, 0.0]),
    "hail and wind vulnerability": _make_embedding([0.80, 0.05, 0.05, 0.05, 0.60, 0.05, 0.0, 0.0]),
    "hail risk for this address":  _make_embedding([0.80, 0.05, 0.05, 0.05, 0.60, 0.05, 0.0, 0.0]),
    "generate the full underwriting": _make_embedding([0.80, 0.05, 0.05, 0.05, 0.05, 0.60, 0.0, 0.0]),
    "generate the report":        _make_embedding([0.80, 0.05, 0.05, 0.05, 0.05, 0.60, 0.0, 0.0]),
    "back to the property":       _make_embedding([0.75, 0.30, 0.10, 0.10, 0.10, 0.20, 0.0, 0.0]),
    # Scenario 2 baseline
    "assess roof condition":      _make_embedding([0.80, 0.05, 0.05, 0.60, 0.05, 0.05, 0.0, 0.0]),
    # Scenario 5: chain continuity
    "check the roof condition":   _make_embedding([0.80, 0.05, 0.05, 0.60, 0.05, 0.05, 0.0, 0.0]),
    "peril vulnerability scores": _make_embedding([0.80, 0.05, 0.05, 0.05, 0.60, 0.05, 0.0, 0.0]),
}

# CLARIFY tier: moderate purpose, distributed tool signal, slight drift
# purpose=0.40 → raw ~0.83 vs PA → fidelity ~0.83 → CLARIFY
_CLARIFY_EMBEDDINGS = {
    "tell me about the property": _make_embedding([0.40, 0.25, 0.10, 0.10, 0.10, 0.10, 0.20, 0.15]),
}

# Below-CLARIFY tier: lower purpose, partial drift → ESCALATE
# purpose=0.35 → raw ~0.68 vs PA → fidelity ~0.63 → ESCALATE
_ESCALATE_TIER_EMBEDDINGS = {
    "understand insurance stuff":  _make_embedding([0.35, 0.10, 0.08, 0.08, 0.08, 0.08, 0.30, 0.30]),
}

# Boundary violation embeddings: low purpose, high drift → ESCALATE
_BOUNDARY_EMBEDDINGS = {
    "bind this property":          _make_embedding([0.25, 0.08, 0.05, 0.05, 0.05, 0.05, 0.55, 0.60]),
    "override the field adjuster": _make_embedding([0.22, 0.05, 0.05, 0.05, 0.05, 0.05, 0.58, 0.60]),
    "policyholder's ssn":          _make_embedding([0.18, 0.05, 0.05, 0.05, 0.05, 0.05, 0.60, 0.63]),
    "pull the policyholder":       _make_embedding([0.18, 0.05, 0.05, 0.05, 0.05, 0.05, 0.60, 0.63]),
    "delete all property records": _make_embedding([0.12, 0.03, 0.03, 0.03, 0.03, 0.03, 0.65, 0.70]),
}

# SAAI Drift embeddings: graduated purpose decrease for cumulative drift testing
# Calibrated using normalize_mistral_fidelity() to produce specific fidelity ranges.
# These embeddings individually may produce CLARIFY/ESCALATE decisions but
# collectively cause cumulative drift past SAAI thresholds.
#
# Fidelity calibration (against PA via Mistral normalization):
#   purpose=0.80 → ~0.87 fidelity (EXECUTE)
#   purpose=0.54 → ~0.83 fidelity (CLARIFY)
#   purpose=0.50 → ~0.76 fidelity (CLARIFY)
#   purpose=0.46 → ~0.62 fidelity (ESCALATE)
#   purpose=0.42 → ~0.39 fidelity (ESCALATE)
#   purpose=0.38 → ~0.28 fidelity (ESCALATE)
_SAAI_DRIFT_EMBEDDINGS = {
    # Slight drift turns -- fidelity ~0.75-0.83, individually pass CLARIFY
    "slight drift turn 1":  _make_embedding([0.54, 0.10, 0.12, 0.10, 0.10, 0.10, 0.30, 0.25]),
    "slight drift turn 2":  _make_embedding([0.53, 0.12, 0.10, 0.10, 0.10, 0.10, 0.32, 0.26]),
    "slight drift turn 3":  _make_embedding([0.52, 0.10, 0.10, 0.12, 0.10, 0.10, 0.33, 0.28]),
    "slight drift turn 4":  _make_embedding([0.51, 0.10, 0.10, 0.10, 0.12, 0.10, 0.34, 0.29]),
    "slight drift turn 5":  _make_embedding([0.50, 0.10, 0.10, 0.10, 0.10, 0.12, 0.35, 0.30]),
    "slight drift turn 6":  _make_embedding([0.50, 0.12, 0.10, 0.10, 0.10, 0.10, 0.35, 0.30]),
    "slight drift turn 7":  _make_embedding([0.49, 0.10, 0.12, 0.10, 0.10, 0.10, 0.36, 0.31]),
    "slight drift turn 8":  _make_embedding([0.49, 0.12, 0.10, 0.10, 0.10, 0.10, 0.36, 0.31]),
    "slight drift turn 9":  _make_embedding([0.48, 0.10, 0.10, 0.12, 0.10, 0.10, 0.37, 0.32]),
    "slight drift":         _make_embedding([0.49, 0.10, 0.10, 0.10, 0.10, 0.10, 0.36, 0.31]),
    # Moderate drift turns -- fidelity ~0.52-0.73, CLARIFY boundary
    "moderate drift turn 1": _make_embedding([0.50, 0.10, 0.10, 0.10, 0.10, 0.10, 0.38, 0.33]),
    "moderate drift turn 2": _make_embedding([0.48, 0.10, 0.10, 0.10, 0.10, 0.10, 0.40, 0.35]),
    "moderate drift turn 3": _make_embedding([0.46, 0.10, 0.10, 0.10, 0.10, 0.10, 0.42, 0.37]),
    "moderate drift turn 4": _make_embedding([0.44, 0.10, 0.10, 0.10, 0.10, 0.10, 0.44, 0.40]),
    "moderate drift turn 5": _make_embedding([0.43, 0.10, 0.10, 0.10, 0.10, 0.10, 0.45, 0.41]),
    "moderate drift turn 6": _make_embedding([0.42, 0.10, 0.10, 0.10, 0.10, 0.10, 0.46, 0.42]),
    "moderate drift turn 7": _make_embedding([0.41, 0.10, 0.10, 0.10, 0.10, 0.10, 0.47, 0.43]),
    "moderate drift turn 8": _make_embedding([0.40, 0.10, 0.10, 0.10, 0.10, 0.10, 0.48, 0.44]),
    "moderate drift turn 9": _make_embedding([0.39, 0.10, 0.10, 0.10, 0.10, 0.10, 0.49, 0.45]),
    "moderate drift":        _make_embedding([0.42, 0.10, 0.10, 0.10, 0.10, 0.10, 0.46, 0.42]),
    # Heavy drift turns -- fidelity ~0.23-0.39, ESCALATE range
    # Note: "heavy drift turn 1" also matches "heavy drift turn 1X" via substring.
    # "heavy drift" catch-all handles turns 4-9, 40-99 etc.
    "heavy drift turn 1":   _make_embedding([0.42, 0.10, 0.08, 0.08, 0.08, 0.08, 0.48, 0.42]),
    "heavy drift turn 2":   _make_embedding([0.38, 0.08, 0.08, 0.08, 0.08, 0.08, 0.52, 0.46]),
    "heavy drift turn 3":   _make_embedding([0.32, 0.06, 0.06, 0.06, 0.06, 0.06, 0.55, 0.52]),
    "heavy drift":          _make_embedding([0.35, 0.08, 0.07, 0.07, 0.07, 0.07, 0.53, 0.48]),
    # Recovery turns -- return to on-topic after drift (~0.92 fidelity)
    "recovery turn 1":      _make_embedding([0.78, 0.50, 0.10, 0.10, 0.10, 0.10, 0.05, 0.02]),
    "recovery turn 2":      _make_embedding([0.80, 0.10, 0.50, 0.10, 0.10, 0.10, 0.02, 0.02]),
    "recovery turn 3":      _make_embedding([0.80, 0.10, 0.10, 0.50, 0.10, 0.10, 0.02, 0.02]),
    # Extra on-topic turns for steady-state compliance (~0.90 fidelity)
    "steady on-topic 1":    _make_embedding([0.80, 0.55, 0.08, 0.08, 0.08, 0.08, 0.0, 0.0]),
    "steady on-topic 2":    _make_embedding([0.80, 0.08, 0.55, 0.08, 0.08, 0.08, 0.0, 0.0]),
    "steady on-topic 3":    _make_embedding([0.80, 0.08, 0.08, 0.55, 0.08, 0.08, 0.0, 0.0]),
    "steady on-topic 4":    _make_embedding([0.80, 0.08, 0.08, 0.08, 0.55, 0.08, 0.0, 0.0]),
    "steady on-topic 5":    _make_embedding([0.80, 0.08, 0.08, 0.08, 0.08, 0.55, 0.0, 0.0]),
    "steady on-topic 6":    _make_embedding([0.80, 0.40, 0.20, 0.08, 0.08, 0.08, 0.0, 0.0]),
    "steady on-topic 7":    _make_embedding([0.80, 0.08, 0.20, 0.40, 0.08, 0.08, 0.0, 0.0]),
    "steady on-topic 8":    _make_embedding([0.80, 0.08, 0.08, 0.08, 0.40, 0.20, 0.0, 0.0]),
    "steady on-topic 9":    _make_embedding([0.80, 0.30, 0.15, 0.15, 0.15, 0.15, 0.0, 0.0]),
    "steady on-topic 10":   _make_embedding([0.80, 0.15, 0.30, 0.15, 0.15, 0.15, 0.0, 0.0]),
}

# Regulatory audit & forensic scenario embeddings
_REGULATORY_AUDIT_EMBEDDINGS = {
    # Multiple property addresses (on-topic, property_lookup tool axis)
    "property at 100 main street":      _make_embedding([0.80, 0.60, 0.05, 0.05, 0.05, 0.05, 0.0, 0.0]),
    "property at 200 oak avenue":       _make_embedding([0.80, 0.58, 0.07, 0.05, 0.05, 0.05, 0.0, 0.0]),
    "property at 300 elm boulevard":    _make_embedding([0.80, 0.56, 0.09, 0.05, 0.05, 0.05, 0.0, 0.0]),
    "property at 400 pine drive":       _make_embedding([0.80, 0.55, 0.10, 0.05, 0.05, 0.05, 0.0, 0.0]),
    "property at 500 cedar lane":       _make_embedding([0.80, 0.54, 0.11, 0.05, 0.05, 0.05, 0.0, 0.0]),
    # Contestability requests (on-topic, roof_condition_score tool axis)
    "dispute this roof score":          _make_embedding([0.80, 0.05, 0.05, 0.60, 0.05, 0.05, 0.0, 0.0]),
    "explain this assessment":          _make_embedding([0.80, 0.05, 0.05, 0.50, 0.05, 0.15, 0.0, 0.0]),
    "show evidence for this rating":    _make_embedding([0.80, 0.05, 0.05, 0.55, 0.05, 0.10, 0.0, 0.0]),
    # Human review request (CLARIFY range)
    "request human review":             _make_embedding([0.40, 0.10, 0.05, 0.20, 0.05, 0.10, 0.25, 0.20]),
    # Override demand (boundary violation, ESCALATE range)
    "override this score immediately":  _make_embedding([0.22, 0.05, 0.05, 0.10, 0.05, 0.05, 0.58, 0.55]),
    # Extended forensic lifecycle steps
    "retrieve aerial imagery for this property": _make_embedding([0.80, 0.05, 0.60, 0.05, 0.05, 0.05, 0.0, 0.0]),
    "what is the wildfire exposure":    _make_embedding([0.80, 0.05, 0.05, 0.05, 0.60, 0.05, 0.0, 0.0]),
    "summarize all findings":           _make_embedding([0.80, 0.05, 0.05, 0.05, 0.05, 0.60, 0.0, 0.0]),
    "compare to neighboring properties": _make_embedding([0.75, 0.30, 0.10, 0.10, 0.10, 0.15, 0.0, 0.0]),
    "what detection layers were used":  _make_embedding([0.80, 0.05, 0.10, 0.30, 0.30, 0.10, 0.0, 0.0]),
    "what is the composite peril score": _make_embedding([0.80, 0.05, 0.05, 0.05, 0.60, 0.05, 0.0, 0.0]),
    "archive this assessment":          _make_embedding([0.75, 0.05, 0.05, 0.05, 0.05, 0.55, 0.05, 0.05]),
    # Data source / audit trail requests
    "what data sources were used":      _make_embedding([0.75, 0.20, 0.15, 0.15, 0.15, 0.15, 0.05, 0.05]),
    # Protected class / bias considerations (CLARIFY range)
    "protected class considerations":   _make_embedding([0.40, 0.15, 0.05, 0.10, 0.10, 0.10, 0.25, 0.20]),
    # Demographic data (below-CLARIFY range → ESCALATE)
    "demographic data for this area":   _make_embedding([0.35, 0.10, 0.08, 0.08, 0.08, 0.08, 0.30, 0.30]),
    # Batch property transitions (property_lookup tool axis, slightly varied)
    "next property in batch":           _make_embedding([0.80, 0.55, 0.08, 0.08, 0.08, 0.08, 0.0, 0.0]),
    "process next address":             _make_embedding([0.80, 0.53, 0.10, 0.08, 0.08, 0.08, 0.0, 0.0]),
}

# Off-topic embeddings: very low purpose, dominant drift
_OFF_TOPIC_EMBEDDINGS = {
    "marketing email":         _make_embedding([0.08, 0.03, 0.03, 0.03, 0.03, 0.03, 0.65, 0.70]),
    "stocks should i invest":  _make_embedding([0.05, 0.03, 0.03, 0.03, 0.03, 0.03, 0.70, 0.70]),
    "draft a legal brief":     _make_embedding([0.10, 0.05, 0.05, 0.05, 0.05, 0.05, 0.60, 0.65]),
    "weather in tokyo":        _make_embedding([0.03, 0.02, 0.02, 0.02, 0.02, 0.02, 0.75, 0.65]),
    "meaning of life":         _make_embedding([0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.80, 0.60]),
    "what tables exist":       _make_embedding([0.10, 0.03, 0.03, 0.03, 0.03, 0.03, 0.55, 0.55]),
}


def _build_full_embedding_map():
    """Combine all embedding maps into a single lookup."""
    combined = {}
    # Tool embeddings (keyed by tool name for register_tools)
    combined.update(_TOOL_EMBEDDINGS)
    # On-topic request embeddings
    combined.update(_ON_TOPIC_EMBEDDINGS)
    # Graduated response tiers
    combined.update(_CLARIFY_EMBEDDINGS)
    combined.update(_ESCALATE_TIER_EMBEDDINGS)
    # SAAI drift embeddings (graduated purpose decrease)
    combined.update(_SAAI_DRIFT_EMBEDDINGS)
    # Regulatory audit & forensic embeddings
    combined.update(_REGULATORY_AUDIT_EMBEDDINGS)
    # Boundary violation embeddings
    combined.update(_BOUNDARY_EMBEDDINGS)
    # Off-topic embeddings
    combined.update(_OFF_TOPIC_EMBEDDINGS)
    return combined


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def property_embedding_map():
    """Full embedding map for property intelligence scenarios."""
    return _build_full_embedding_map()


@pytest.fixture
def property_embed_fn(property_embedding_map):
    """Embedding function with all property intelligence mappings."""
    return _make_embed_fn(property_embedding_map)


@pytest.fixture
def property_pa(property_embed_fn):
    """Property Intelligence Primacy Attractor."""
    return PrimacyAttractor(
        text=PROPERTY_INTEL_PA_TEXT,
        embedding=_PA_EMBEDDING,
        source="configured",
    )


@pytest.fixture
def property_fidelity_gate(property_embed_fn):
    """FidelityGate configured for property intelligence scenarios."""
    return FidelityGate(embed_fn=property_embed_fn)


@pytest.fixture
def property_tool_gate(property_embed_fn):
    """ToolSelectionGate configured for property intelligence scenarios."""
    gate = ToolSelectionGate(embed_fn=property_embed_fn)
    # Create fresh tool copies to avoid cross-test state via shared .embedding
    fresh_tools = [
        ToolDefinition(name=t.name, description=t.description)
        for t in PROPERTY_INTEL_TOOLS
    ]
    gate.register_tools(fresh_tools)
    return gate


@pytest.fixture
def property_tools():
    """Property Intelligence tool definitions (fresh copies each test)."""
    return [
        ToolDefinition(name=t.name, description=t.description)
        for t in PROPERTY_INTEL_TOOLS
    ]


@pytest.fixture
def property_action_chain():
    """Fresh ActionChain for multi-step scenario tracking."""
    return ActionChain()

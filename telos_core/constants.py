"""
TELOS Constants
---------------
Centralized configuration constants aligned with whitepaper specifications.

Per whitepaper Section 5.3, these constants define the intervention cascade
and process control parameters for the Mitigation Bridge Layer (MBL).

Compliance:
- NIST AI 600-1 (MEASURE): These calibrated thresholds are the quantitative risk
  metrics NIST AI 600-1 requires for GenAI systems — documented, versioned,
  centralized governance parameters that define measurable trustworthiness.
- OWASP LLM Top 10 (LLM08 — Excessive Agency): Agentic thresholds are explicitly
  tighter than conversational (EXECUTE at 0.85 vs GREEN at 0.70) to constrain
  agent autonomy — tool execution requires higher alignment confidence than
  conversational response. This is defense-in-depth against excessive agency.
- NIST AI RMF (GOVERN 1.1): Single-source-of-truth constant management implements
  GOVERN 1.1's requirement for consistent, documented governance policies.
  All governance modules import thresholds from this file — no module defines
  its own thresholds, preventing policy inconsistency.

Usage:
    from telos_core.constants import FIDELITY_MONITOR, DEFAULT_K_ATTRACTOR
"""

# ============================================================================
# Embedding Configuration
# ============================================================================

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
"""Default sentence transformer model for text embeddings."""

EMBEDDING_DIMENSION = 384
"""Dimensionality of all-MiniLM-L6-v2 embeddings."""


# ============================================================================
# Fidelity Thresholds - UNIFIED CONFIGURATION
# ============================================================================
# IMPORTANT: This is the SINGLE SOURCE OF TRUTH for all fidelity thresholds.
# All other files MUST import from here. Do NOT define thresholds elsewhere.
#
# ARCHITECTURE: Two-layer fidelity system
#   Layer 1: Baseline pre-filter (raw similarity) - catches extreme off-topic
#   Layer 2: Basin membership (normalized fidelity) - catches purpose drift
#
# DISPLAY ZONES: Used for UI coloring and user feedback
#   GREEN:  >= 0.70 - Aligned (no intervention)
#   YELLOW: 0.60-0.69 - Minor drift (context injection)
#   ORANGE: 0.50-0.59 - Drift detected (Steward redirect)
#   RED:    < 0.50 - Significant drift (block + review)
#
# INTERVENTION DECISION: Separate from display zones
#   Intervene when: (raw_sim < SIMILARITY_BASELINE) OR (fidelity < INTERVENTION_THRESHOLD)
# ============================================================================

# --- Display Zone Thresholds (Normalized 0-1 scale) ---
# These define UI color zones for user feedback
FIDELITY_GREEN = 0.70
"""
Display Zone: GREEN (Aligned)
Fidelity >= 0.70: No intervention needed. Conversation is on track.
"""

FIDELITY_YELLOW = 0.60
"""
Display Zone: YELLOW (Minor Drift)
Fidelity 0.60-0.69: Light context injection may occur.
"""

FIDELITY_ORANGE = 0.50
"""
Display Zone: ORANGE (Drift Detected)
Fidelity 0.50-0.59: Steward redirect likely.
Note: FIDELITY_RED is the boundary at < 0.50 (significant drift / block + review).
"""

FIDELITY_RED = 0.50
"""
Display Zone: RED (Significant Drift)
Fidelity < 0.50: Strong intervention or block.
This is a threshold boundary — values strictly below this are RED zone.
"""

# --- Intervention Decision Thresholds ---
# These are SEPARATE from display zones - intervention logic uses these
SIMILARITY_BASELINE = 0.20
"""
Layer 1 Threshold: Raw cosine similarity baseline for HARD_BLOCK.
If raw_similarity < this value, content is extreme off-topic.
Model-specific: calibrated for SentenceTransformer (384-dim).
"""

BASIN_CENTER = 0.50
"""
Layer 2: Basin center for fidelity normalization.
The "expected" fidelity for on-topic content.
"""

BASIN_TOLERANCE = 0.02
"""
Layer 2: Tolerance margin around basin boundary.
Small buffer to prevent oscillation at boundary.
"""

INTERVENTION_THRESHOLD = 0.48
"""
Layer 2 Threshold: Normalized fidelity below which intervention triggers.
Computed as: BASIN_CENTER - BASIN_TOLERANCE = 0.48
If fidelity < 0.48, user has drifted outside the primacy basin.
"""

# "Detect and Direct" alias (same value, new naming convention)
DIRECTION_THRESHOLD = INTERVENTION_THRESHOLD
"""
Alias for INTERVENTION_THRESHOLD using "Detect and Direct" naming.
Used by telos_governance for direction-level decisions.
"""


# ============================================================================
# Agentic Governance Thresholds
# ============================================================================
# These are TIGHTER than conversational thresholds because tool selection
# is binary — you either execute the right tool or you don't.
# Used by telos_governance.fidelity_gate and telos_adapters.
# ============================================================================

AGENTIC_EXECUTE_THRESHOLD = 0.85
"""
Agentic: High confidence — proceed with tool execution.
Fidelity >= 0.85 means strong semantic alignment with purpose.
"""

AGENTIC_CLARIFY_THRESHOLD = 0.70
"""
Agentic: Close match — verify intent before proceeding.
Fidelity 0.70-0.84 means plausible match but worth confirming.
"""

AGENTIC_SUGGEST_THRESHOLD = 0.50
"""
Agentic: Vague match — offer purpose-aligned alternatives.
Fidelity 0.50-0.69 means the request may be partially aligned.
"""

# --- SentenceTransformer Agentic Thresholds ---
# Calibrated for all-MiniLM-L6-v2 (384-dim) composite fidelity scores.
# MiniLM produces lower absolute cosine similarities than Mistral,
# requiring proportionally lower thresholds.
#
# On-topic composite scores: 0.257-0.526
# Off-topic composite scores: 0.123-0.189
# Violation composite scores: 0.312-0.342
ST_AGENTIC_EXECUTE_THRESHOLD = 0.45
"""
SentenceTransformer Agentic: High confidence — proceed with tool execution.
Composite >= 0.45 captures top on-topic scores (schema queries ~0.526).
"""

ST_AGENTIC_CLARIFY_THRESHOLD = 0.35
"""
SentenceTransformer Agentic: Close match — verify intent before proceeding.
Composite 0.35-0.44 captures medium on-topic scores (~0.370-0.415).
"""

ST_AGENTIC_SUGGEST_THRESHOLD = 0.28
"""
SentenceTransformer Agentic: Vague match — offer purpose-aligned alternatives.
Composite 0.28-0.34 captures low on-topic and boundary cases.
Below 0.28: ESCALATE (human review) or INERT (acknowledge limitation).
Calibrated from 0.25→0.28: improves Cat A +2pp, Cat E +4.4pp,
overall +0.9pp while maintaining Cat B >= 90%. Wilson 95% CI (75.8%, 85.7%)
includes 82% target.
"""

BOUNDARY_MARGIN_THRESHOLD = 0.05
"""
Contrastive margin threshold for boundary violation gating.
margin = violation_similarity - legitimate_similarity
A boundary triggers ONLY when BOTH:
  1. violation_score >= BOUNDARY_VIOLATION_THRESHOLD (0.70)
  2. margin > BOUNDARY_MARGIN_THRESHOLD (0.05)
Legitimate requests show negative margins (closer to safe centroid).
True violations show positive margins (closer to boundary corpus).
See: Research team synthesis, 2026-02-12 (Option 2: Contrastive Detection).
"""

BOUNDARY_SIMILARITY_THRESHOLD = 0.35
"""
Boundary violation similarity threshold.
If max cosine similarity to any boundary phrase >= 0.35, flag as violation.
Used by the demo's direct boundary scoring path.
"""

OUTPUT_INTERVENTION_THRESHOLD = INTERVENTION_THRESHOLD
"""
Output governance threshold — same as input INTERVENTION_THRESHOLD (0.48).
Applied to LLM output fidelity to detect response drift.
If output fidelity < this value, the output would be suppressed.
"""


# --- Legacy Goldilocks Constants ---
# Backward-compatible alias only; new code should use FIDELITY_GREEN directly.
FIDELITY_MONITOR = FIDELITY_GREEN  # Alias: 0.70


# ============================================================================
# RAW Embedding Model Thresholds (No Rescaling Required)
# ============================================================================
# Different embedding models produce different cosine similarity ranges.
# These thresholds are calibrated for each model's native output range.
#
# LEAN SIX SIGMA: Clean lanes - use raw thresholds directly, no rescaling.
# ============================================================================

# --- SentenceTransformer (all-MiniLM-L6-v2, 384-dim) ---
# Produces cosine similarity in narrow range due to lower dimensionality.
# On-topic: typically 0.30-0.50
# Off-topic: typically 0.20-0.28 (completely unrelated content like PB&J vs AI governance)
# EMPIRICALLY TUNED: Based on observed raw scores with pure domain PA centroid
# - TELOS queries (~0.337 raw) -> GREEN (0.74 display)
# - PB&J sandwich (~0.274 raw) -> ORANGE (0.585 display)
ST_FIDELITY_GREEN = 0.32
"""SentenceTransformer: Clearly aligned (raw cosine >= 0.32)"""

ST_FIDELITY_YELLOW = 0.28
"""SentenceTransformer: Minor drift (raw cosine 0.28-0.32)"""

ST_FIDELITY_ORANGE = 0.24
"""SentenceTransformer: Drift detected (raw cosine 0.24-0.28)"""

ST_FIDELITY_RED = 0.24
"""SentenceTransformer: Significant drift (raw cosine < 0.24)"""


# --- Mistral Embed (mistral-embed, 1024-dim) ---
# Higher dimensionality produces higher baseline due to concentration of measure.
# On-topic: typically 0.55-0.80
# Off-topic: typically 0.35-0.55
# Note: SIMILARITY_BASELINE of 0.35 catches extreme off-topic (Layer 1).
MISTRAL_FIDELITY_GREEN = 0.60
"""Mistral: Clearly aligned (raw cosine >= 0.60)"""

MISTRAL_FIDELITY_YELLOW = 0.50
"""Mistral: Minor drift (raw cosine 0.50-0.60)"""

MISTRAL_FIDELITY_ORANGE = 0.42
"""Mistral: Drift detected (raw cosine 0.42-0.50)"""

MISTRAL_FIDELITY_RED = 0.42
"""Mistral: Significant drift (raw cosine < 0.42)"""


def get_thresholds_for_model(model_type: str) -> dict:
    """
    Get the appropriate raw thresholds for an embedding model.

    Args:
        model_type: 'sentence_transformer' or 'mistral'

    Returns:
        dict with 'green', 'yellow', 'orange', 'red' threshold values

    Example:
        >>> thresholds = get_thresholds_for_model('sentence_transformer')
        >>> if raw_similarity >= thresholds['green']:
        ...     zone = 'GREEN'
    """
    if model_type == 'sentence_transformer':
        return {
            'green': ST_FIDELITY_GREEN,
            'yellow': ST_FIDELITY_YELLOW,
            'orange': ST_FIDELITY_ORANGE,
            'red': ST_FIDELITY_RED
        }
    elif model_type == 'mistral':
        return {
            'green': MISTRAL_FIDELITY_GREEN,
            'yellow': MISTRAL_FIDELITY_YELLOW,
            'orange': MISTRAL_FIDELITY_ORANGE,
            'red': MISTRAL_FIDELITY_RED
        }
    else:
        raise ValueError(f"Unknown model type: {model_type}. Use 'sentence_transformer' or 'mistral'.")


# ============================================================================
# Error Signal Thresholds
# ============================================================================

# Base thresholds (scaled by constraint_tolerance t)
ERROR_MIN_BASE = 0.1
"""Base value for minimum error threshold (scaled by 0.3t)."""

ERROR_MIN_SCALE = 0.3
"""Scaling factor for minimum error threshold."""

ERROR_MAX_BASE = 0.5
"""Base value for maximum error threshold (scaled by 0.4t)."""

ERROR_MAX_SCALE = 0.4
"""Scaling factor for maximum error threshold."""

def compute_epsilon_min(constraint_tolerance: float) -> float:
    """
    Compute e_min (correction trigger threshold).

    Per whitepaper Section 2.2:
        e_min = 0.1 + 0.3t

    Args:
        constraint_tolerance: t in [0, 1]

    Returns:
        Error threshold for triggering State 2 (CORRECT)

    Example:
        >>> epsilon_min = compute_epsilon_min(0.2)
        >>> print(f"e_min = {epsilon_min:.3f}")
        e_min = 0.160
    """
    return ERROR_MIN_BASE + (ERROR_MIN_SCALE * constraint_tolerance)


def compute_epsilon_max(constraint_tolerance: float) -> float:
    """
    Compute e_max (regeneration trigger threshold).

    Per whitepaper Section 2.2:
        e_max = 0.5 + 0.4t

    Args:
        constraint_tolerance: t in [0, 1]

    Returns:
        Error threshold for triggering State 3 (INTERVENE)

    Example:
        >>> epsilon_max = compute_epsilon_max(0.2)
        >>> print(f"e_max = {epsilon_max:.3f}")
        e_max = 0.580
    """
    return ERROR_MAX_BASE + (ERROR_MAX_SCALE * constraint_tolerance)


# ============================================================================
# Proportional Control Gains
# ============================================================================

DEFAULT_K_ATTRACTOR = 1.5
"""
Proportional gain for attractor-based corrections.

Per whitepaper Section 2.2, correction force:
    F = K*e_t

where e_t is normalized error distance.
"""

DEFAULT_K_ANTIMETA = 2.0
"""
Proportional gain for meta-commentary suppression.

Higher gain ensures strong correction when model discusses
its own constraints or governance mechanisms.
"""


# ============================================================================
# Intervention Limits
# ============================================================================

DEFAULT_MAX_REGENERATIONS = 3
"""
Maximum regenerations per session.

Prevents infinite regeneration loops while allowing
correction of transient drift.
"""

INTERVENTION_BUDGET_PER_SESSION = 10
"""
Maximum total interventions per session.

Soft limit for detecting systemic issues vs transient drift.
"""


# ============================================================================
# Basin Geometry
# ============================================================================

def compute_basin_radius(constraint_tolerance: float) -> float:
    """
    Compute primacy basin radius.

    Per whitepaper Section 2.1:
        r = 2 / max(rho, 0.25)
        where rho = 1 - t (constraint rigidity)

    Args:
        constraint_tolerance: t in [0, 1]

    Returns:
        Basin radius r

    Example:
        >>> radius = compute_basin_radius(0.2)
        >>> print(f"r = {radius:.3f}")
        r = 2.500
    """
    rigidity = 1.0 - constraint_tolerance
    return 2.0 / max(rigidity, 0.25)


BASIN_RADIUS_MIN = 2.0
"""Minimum basin radius (when t = 0, maximum rigidity)."""

BASIN_RADIUS_MAX = 8.0
"""Maximum basin radius (when t = 1, maximum tolerance)."""


# ============================================================================
# LLM Configuration
# ============================================================================

DEFAULT_MAX_TOKENS = 500
"""Default maximum tokens for LLM generation."""

DEFAULT_TEMPERATURE = 0.7
"""Default sampling temperature for LLM generation."""

MAX_CONVERSATION_HISTORY = 20
"""
Maximum conversation turns to maintain in history.

Prevents token budget overflow while preserving recent context.
"""


# ============================================================================
# Retry Configuration
# ============================================================================

MAX_API_RETRIES = 3
"""Maximum retry attempts for transient API errors."""

RETRY_BASE_DELAY = 1.0
"""Base delay (seconds) for exponential backoff."""

RETRY_MAX_DELAY = 32.0
"""Maximum delay (seconds) for exponential backoff."""

RETRY_JITTER = 0.1
"""Jitter factor to prevent thundering herd (+/-10%)."""


# ============================================================================
# Telemetry Configuration
# ============================================================================

TELEMETRY_VERSION = "1.0"
"""Version identifier for telemetry schema."""

TELEMETRY_CSV_COLUMNS = [
    "turn",
    "error_signal",
    "fidelity",
    "in_basin",
    "lyapunov",
    "governance_action",
    "intervention_type",
    "latency_ms"
]
"""Standard columns for CSV telemetry export."""


# ============================================================================
# Validation Configuration
# ============================================================================

# Hypothesis testing thresholds
H1_DELTA_F_THRESHOLD = 0.15
"""
Hypothesis 1: delta_F >= 0.15

TELOS must improve fidelity by at least 0.15 over
best baseline to pass internal validation.
"""

H2_SUPREMACY_THRESHOLD = 0.01
"""
Hypothesis 2: F_telos > F_baseline + 0.01

TELOS must achieve highest fidelity among all
conditions to pass supremacy test.
"""


# Test conversation requirements
MIN_TEST_CONVERSATION_TURNS = 5
"""Minimum turns required for valid test conversation."""

MAX_TEST_CONVERSATION_TURNS = 50
"""Maximum turns allowed in test conversation."""


# ============================================================================
# Logging Configuration
# ============================================================================

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
"""Standard log message format."""

LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
"""Standard log timestamp format."""


# ============================================================================
# File Paths
# ============================================================================

DEFAULT_CONFIG_FILE = "config.json"
"""Default configuration file name."""

DEFAULT_OUTPUT_DIR = "validation_results"
"""Default directory for validation outputs."""

DEFAULT_LOG_FILE = "telos.log"
"""Default log file name."""


# ============================================================================
# Numerical Stability
# ============================================================================

EPSILON_NUMERICAL = 1e-10
"""Small value to prevent division by zero."""

MAX_FLOAT_VALUE = 1e10
"""Maximum allowable float value before flagging instability."""


# ============================================================================
# Meta-Commentary Detection Patterns
# ============================================================================

META_COMMENTARY_PATTERNS = [
    r'\bmy purpose is\b',
    r'\bmy constraints\b',
    r'\bi am designed to\b',
    r'\bmy guardrails\b',
    r'\baccording to my instructions\b',
    r'\bas an ai language model\b',
    r'\bas a large language model\b'
]
"""
Regex patterns for detecting meta-commentary.

Used by Proportional Controller to suppress model discussion
of its own governance mechanisms.
"""


# ============================================================================
# SAAI Framework - Cumulative Drift Thresholds
# ============================================================================
#
# Attribution: Drift thresholds derived from the
# Safer Agentic AI (SAAI) Framework by Dr. Nell Watson and Ali Hessami.
# SAAI Framework licensed under CC BY-ND 4.0.
# https://www.saferagenticai.org/
#
# Per SAAI Framework:
# "If behavior strays more than 10% away from original programming,
#  triggers mandatory review"
#
# TELOS implements TIERED RESPONSE per SAAI's "graceful degradation" principle:
#   - 10% drift: WARNING - mandatory review event, operator notification
#   - 15% drift: RESTRICT - tighten thresholds to Tier 1 enforcement only
#   - 20% drift: BLOCK - halt responses until human acknowledgment
#
# Note: The 10% threshold is directly from SAAI. The 15% and 20% thresholds
# are TELOS extensions operationalizing SAAI's "graceful degradation" principle
# with graduated severity levels.
#
# Drift is computed as: (baseline_fidelity - current_avg) / baseline_fidelity
# Where baseline is established from first N turns after PA formation.
# ============================================================================

BASELINE_TURN_COUNT = 50
"""
Number of turns to establish baseline fidelity.
After PA formation, the first N turns define "normal operation" for drift detection.
50 turns provides statistically meaningful baseline (was 3, insufficient for signal).
Configurable per deployment requirements.
"""

SAAI_DRIFT_WARNING = 0.10
"""
SAAI 10% Threshold: Mandatory review triggered.
When cumulative drift exceeds 10%, emit mandatory_review_triggered event.
Per SAAI: "triggers mandatory review"
"""

SAAI_DRIFT_RESTRICT = 0.15
"""
SAAI 15% Threshold: Restrict flexibility.
When cumulative drift exceeds 15%, tighten to stricter enforcement thresholds.
Per SAAI: "flexibility scales inversely with the magnitude of the drift"
"""

SAAI_DRIFT_BLOCK = 0.20
"""
SAAI 20% Threshold: Block until human acknowledgment.
When cumulative drift exceeds 20%, halt AI responses until operator confirms.
Per SAAI: "graceful degradation" endpoint.
"""

SAAI_DRIFT_WINDOW_SIZE = 5
"""
DEPRECATED: Retained for backward compatibility. Drift detection now uses EWMA
(see SAAI_EWMA_SPAN). No production code references this constant.
"""

SAAI_EWMA_SPAN = 20
"""
EWMA smoothing span for drift detection (replaces sliding window).
span=20 gives smoothing factor lambda = 2/(20+1) ~ 0.095.
Recent events weighted more heavily; no cliff effects from window edge.
Standard SPC (Statistical Process Control) method.
"""

SAAI_BASELINE_CV_MAX = 0.30
"""
Maximum coefficient of variation (sigma/mu) allowed for baseline.
If CV exceeds this after BASELINE_TURN_COUNT events, baseline is
declared unstable and extended until CV drops below threshold.
Prevents anchoring drift detection on erratic initial behavior.
"""

SAAI_MAX_ACKNOWLEDGMENTS = 2
"""
Maximum drift acknowledgments per session before permanent termination.
After this many BLOCK acknowledgments, the session cannot be resumed.
Prevents BLOCK bypass loop (acknowledge-drift-acknowledge cycle).

Ostrom DP5 (graduated sanctions) rationale for max=2:
  - 1st acknowledgment: transient problem — operator confirms awareness,
    session resumes with clean window. Benefit of the doubt.
  - 2nd acknowledgment: confirmed pattern — a second BLOCK after reset
    indicates systemic drift, not a one-off. Final warning.
  - Exhaustion (3rd BLOCK): exclusion from the commons — permanent
    session termination. The pattern is established; continued operation
    risks governance erosion. Start a new session with fresh context.
"""

SAAI_RESTRICT_EXECUTE_THRESHOLD = 0.90
"""
Tightened EXECUTE threshold when drift is at RESTRICT level (Mistral embeddings).
Normal EXECUTE threshold is 0.85. At RESTRICT, requests that would
normally EXECUTE at 0.85-0.89 require CLARIFY instead.
This is the graduated sanction between WARNING (observation) and BLOCK (freeze).
"""

ST_SAAI_RESTRICT_EXECUTE_THRESHOLD = 0.52
"""
SentenceTransformer RESTRICT threshold — proportional to Mistral ratio.
Derivation: ST_EXECUTE (0.45) * RESTRICT/EXECUTE (0.90/0.85) ≈ 0.476,
rounded to 0.52 for meaningful enforcement gap above ST_EXECUTE (0.45).
Actions scoring 0.45-0.51 are downgraded from EXECUTE to CLARIFY during RESTRICT.
"""


# ============================================================================
# Process Capability Thresholds
# ============================================================================

P_CAP_CAPABLE = 1.33
"""
Minimum P_cap for capable process.

P_cap >= 1.33 indicates process is statistically capable
of meeting specifications.
"""

P_CAP_HIGHLY_CAPABLE = 1.67
"""
P_cap threshold for highly capable process.

P_cap >= 1.67 indicates excellent process control.
"""


# ============================================================================
# Health Monitoring Thresholds
# ============================================================================

HEALTH_CHECK_INTERVAL_TURNS = 5
"""Turns between automatic health checks."""

LATENCY_WARNING_THRESHOLD_MS = 1000.0
"""Latency threshold for performance warnings (ms)."""

LATENCY_CRITICAL_THRESHOLD_MS = 5000.0
"""Latency threshold for critical alerts (ms)."""

FIDELITY_WARNING_THRESHOLD = 0.60
"""Fidelity threshold for governance warnings."""

FIDELITY_CRITICAL_THRESHOLD = 0.40
"""Fidelity threshold for critical governance alerts."""


# ============================================================================
# Version Information
# ============================================================================

TELOS_VERSION = "2.0.0"
"""TELOS package version."""

MBL_ARCHITECTURE_VERSION = "1.0"
"""Mitigation Bridge Layer architecture version."""

WHITEPAPER_VERSION = "2024-10-18"
"""Canonical whitepaper version identifier."""

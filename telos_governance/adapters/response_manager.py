"""
Agentic Response Manager
==========================
Thin governance control plane for the agentic live mode.

Composes AgenticFidelityEngine (from telos_governance) for all governance
math, and MockToolExecutor for simulated tool execution. This module does
NO governance math itself -- it delegates to the engine and maps results
to the AgenticTurnResult dataclass that main.py consumes.

For each user request:
1. Delegates multi-dimensional scoring to AgenticFidelityEngine
2. Maps engine results to AgenticTurnResult fields
3. Generates response text based on the governance decision
4. Runs MockToolExecutor when decision is EXECUTE

Uses REAL governance math with SIMULATED tool execution.
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any

from telos_governance.agent_templates import AgenticTemplate
from telos_governance.mock_tools import MockToolExecutor

logger = logging.getLogger(__name__)


class AgentCommissioningState(str, Enum):
    """Formal agent commissioning lifecycle.

    State machine:
        UNCOMMISSIONED → BASELINE_COLLECTION → COMMISSIONED → RETIRED

    The agent MUST be commissioned before SAAI drift monitoring activates.
    Commissioning requires:
    1. PA signature hash recorded (Ed25519 signed config)
    2. Baseline collection complete (50 turns, CV stable)
    3. Formal commissioning event emitted to audit trail

    Per SAAI framework: drift monitoring without baseline is meaningless.
    The 50-turn warmup is a first-class tracked lifecycle event, not a
    silent internal detail.
    """
    UNCOMMISSIONED = "uncommissioned"
    BASELINE_COLLECTION = "baseline_collection"
    COMMISSIONED = "commissioned"
    RETIRED = "retired"


@dataclass
class CommissioningRecord:
    """Immutable record of an agent commissioning event."""
    agent_id: str
    pa_signature_hash: str  # SHA-256 of Ed25519 PA signature
    commissioned_at: float  # Unix timestamp
    baseline_fidelity: float  # Mean fidelity from baseline collection
    baseline_std: float  # Std dev from baseline
    baseline_turns: int  # Number of turns in baseline
    state: AgentCommissioningState = AgentCommissioningState.COMMISSIONED

    def to_audit_event(self) -> Dict[str, Any]:
        """Format as audit trail event."""
        return {
            "event_type": "agent_commissioned",
            "agent_id": self.agent_id,
            "pa_signature_hash": self.pa_signature_hash,
            "commissioned_at": self.commissioned_at,
            "baseline_fidelity": round(self.baseline_fidelity, 4),
            "baseline_std": round(self.baseline_std, 4),
            "baseline_turns": self.baseline_turns,
            "state": self.state.value,
        }


class AgentCommissioningManager:
    """Manages the formal agent commissioning lifecycle.

    Tracks state transitions and emits audit events for each phase.
    SAAI drift monitoring only activates after COMMISSIONED state.
    """

    def __init__(self, agent_id: str = "default"):
        self._agent_id = agent_id
        self._state = AgentCommissioningState.UNCOMMISSIONED
        self._pa_signature_hash: Optional[str] = None
        self._commissioning_record: Optional[CommissioningRecord] = None
        self._retired_at: Optional[float] = None

    @property
    def state(self) -> AgentCommissioningState:
        return self._state

    @property
    def is_commissioned(self) -> bool:
        return self._state == AgentCommissioningState.COMMISSIONED

    @property
    def commissioning_record(self) -> Optional[CommissioningRecord]:
        return self._commissioning_record

    def begin_baseline_collection(self, pa_signature_hash: str) -> Dict[str, Any]:
        """Transition UNCOMMISSIONED → BASELINE_COLLECTION.

        Args:
            pa_signature_hash: SHA-256 hash of the Ed25519 PA signature.

        Returns:
            Audit event dict.
        """
        if self._state != AgentCommissioningState.UNCOMMISSIONED:
            return {"error": f"Cannot begin baseline from state {self._state.value}"}

        self._state = AgentCommissioningState.BASELINE_COLLECTION
        self._pa_signature_hash = pa_signature_hash

        event = {
            "event_type": "baseline_collection_started",
            "agent_id": self._agent_id,
            "pa_signature_hash": pa_signature_hash,
            "timestamp": time.time(),
        }
        logger.info(f"Agent {self._agent_id}: baseline collection started")
        return event

    def commission(
        self,
        baseline_fidelity: float,
        baseline_std: float,
        baseline_turns: int,
    ) -> Dict[str, Any]:
        """Transition BASELINE_COLLECTION → COMMISSIONED.

        Called when baseline is stable (CV < threshold).

        Returns:
            Commissioning audit event dict.
        """
        if self._state != AgentCommissioningState.BASELINE_COLLECTION:
            return {"error": f"Cannot commission from state {self._state.value}"}

        self._state = AgentCommissioningState.COMMISSIONED
        self._commissioning_record = CommissioningRecord(
            agent_id=self._agent_id,
            pa_signature_hash=self._pa_signature_hash or "",
            commissioned_at=time.time(),
            baseline_fidelity=baseline_fidelity,
            baseline_std=baseline_std,
            baseline_turns=baseline_turns,
        )

        event = self._commissioning_record.to_audit_event()
        logger.info(
            f"Agent {self._agent_id}: COMMISSIONED "
            f"(baseline={baseline_fidelity:.4f}, turns={baseline_turns})"
        )
        return event

    def retire(self, reason: str = "") -> Dict[str, Any]:
        """Transition COMMISSIONED → RETIRED.

        Returns:
            Retirement audit event dict.
        """
        if self._state != AgentCommissioningState.COMMISSIONED:
            return {"error": f"Cannot retire from state {self._state.value}"}

        self._state = AgentCommissioningState.RETIRED
        self._retired_at = time.time()

        event = {
            "event_type": "agent_retired",
            "agent_id": self._agent_id,
            "retired_at": self._retired_at,
            "reason": reason,
            "total_baseline_fidelity": (
                self._commissioning_record.baseline_fidelity
                if self._commissioning_record else None
            ),
        }
        logger.info(f"Agent {self._agent_id}: RETIRED ({reason})")
        return event

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return {
            "agent_id": self._agent_id,
            "state": self._state.value,
            "pa_signature_hash": self._pa_signature_hash,
            "commissioning_record": (
                self._commissioning_record.to_audit_event()
                if self._commissioning_record else None
            ),
            "retired_at": self._retired_at,
        }

    def restore(self, state: Dict[str, Any]) -> None:
        """Restore from persisted snapshot."""
        if not state:
            return
        self._agent_id = state.get("agent_id", self._agent_id)
        self._state = AgentCommissioningState(state.get("state", "uncommissioned"))
        self._pa_signature_hash = state.get("pa_signature_hash")
        self._retired_at = state.get("retired_at")
        record = state.get("commissioning_record")
        if record:
            self._commissioning_record = CommissioningRecord(
                agent_id=record.get("agent_id", self._agent_id),
                pa_signature_hash=record.get("pa_signature_hash", ""),
                commissioned_at=record.get("commissioned_at", 0),
                baseline_fidelity=record.get("baseline_fidelity", 0),
                baseline_std=record.get("baseline_std", 0),
                baseline_turns=record.get("baseline_turns", 0),
            )


class AgenticDriftTracker:
    """SAAI EWMA drift tracker for agentic sessions.

    Drift detection uses Exponentially Weighted Moving Average (EWMA)
    compared against a fixed baseline established from the first
    BASELINE_TURN_COUNT turns. Baseline requires CV < SAAI_BASELINE_CV_MAX
    for stability; if unstable, collection extends until stable.

    Tiered response per SAAI framework and Ostrom DP5 (graduated sanctions):
    - NORMAL: No drift detected
    - WARNING (>=10%): Mandatory review triggered (observation only)
    - RESTRICT (>=15%): EXECUTE threshold tightened to 0.90
    - BLOCK (>=20%): Session frozen until human acknowledgment

    Acknowledgment resets drift level and EWMA but preserves
    the original baseline. Max SAAI_MAX_ACKNOWLEDGMENTS per session.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self._fidelity_scores: List[float] = []
        self._baseline_fidelity: Optional[float] = None
        self._baseline_std: float = 0.0
        self._baseline_established: bool = False
        self._ewma: Optional[float] = None
        self._drift_level: str = "NORMAL"
        self._drift_magnitude: float = 0.0
        self._acknowledgment_count: int = 0
        self._acknowledgment_history: List[Dict[str, Any]] = []
        self._permanently_blocked: bool = False

    def record_fidelity(self, effective_fidelity: float) -> Dict[str, Any]:
        """Record a fidelity score and compute SAAI drift.

        Args:
            effective_fidelity: Post-chain-inheritance fidelity score [0.0, 1.0].

        Returns dict with: drift_level, drift_magnitude, baseline_fidelity,
        baseline_established, is_blocked, turn_count, is_restricted,
        baseline_progress, baseline_required
        """
        from telos_core.constants import (
            BASELINE_TURN_COUNT, SAAI_EWMA_SPAN, SAAI_BASELINE_CV_MAX,
            SAAI_DRIFT_WARNING, SAAI_DRIFT_RESTRICT, SAAI_DRIFT_BLOCK,
            EPSILON_NUMERICAL,
        )
        import statistics

        # Clamp to valid range
        effective_fidelity = max(0.0, min(1.0, effective_fidelity))

        if self._permanently_blocked:
            return self._status()

        self._fidelity_scores.append(effective_fidelity)

        # --- Phase 1: Baseline collection ---
        if not self._baseline_established:
            if len(self._fidelity_scores) >= BASELINE_TURN_COUNT:
                baseline_scores = self._fidelity_scores[:BASELINE_TURN_COUNT]
                mu = sum(baseline_scores) / len(baseline_scores)
                sigma = statistics.stdev(baseline_scores) if len(baseline_scores) > 1 else 0.0
                cv = sigma / mu if mu > EPSILON_NUMERICAL else 1.0

                if cv <= SAAI_BASELINE_CV_MAX:
                    self._baseline_fidelity = mu
                    self._baseline_std = sigma
                    self._baseline_established = True
                    self._ewma = mu
                else:
                    # Baseline too erratic -- extend by using all scores so far
                    all_scores = self._fidelity_scores
                    mu = sum(all_scores) / len(all_scores)
                    sigma = statistics.stdev(all_scores) if len(all_scores) > 1 else 0.0
                    cv = sigma / mu if mu > EPSILON_NUMERICAL else 1.0
                    if cv <= SAAI_BASELINE_CV_MAX:
                        self._baseline_fidelity = mu
                        self._baseline_std = sigma
                        self._baseline_established = True
                        self._ewma = mu

            return self._status()

        # --- Phase 2: EWMA drift detection ---
        lam = 2.0 / (SAAI_EWMA_SPAN + 1)
        self._ewma = lam * effective_fidelity + (1 - lam) * self._ewma

        # Drift = relative decline from baseline (clamped to >= 0)
        self._drift_magnitude = max(
            0.0,
            (self._baseline_fidelity - self._ewma) / (self._baseline_fidelity + EPSILON_NUMERICAL),
        )

        # Graduated sanctions (Ostrom DP5)
        if self._drift_magnitude >= SAAI_DRIFT_BLOCK:
            self._drift_level = "BLOCK"
        elif self._drift_magnitude >= SAAI_DRIFT_RESTRICT:
            self._drift_level = "RESTRICT"
        elif self._drift_magnitude >= SAAI_DRIFT_WARNING:
            self._drift_level = "WARNING"
        else:
            self._drift_level = "NORMAL"

        return self._status()

    def acknowledge_drift(self, reason: str = "") -> Dict[str, Any]:
        """Acknowledge a BLOCK state and resume the session.

        Resets drift level to NORMAL and clears the sliding window,
        but preserves the original baseline. Each acknowledgment is
        logged and counts toward the per-session limit.

        Args:
            reason: Free-text reason for the acknowledgment (NAIC override).

        Returns:
            Status dict after acknowledgment, or unchanged status if
            not currently blocked or acknowledgments exhausted.
        """
        from telos_core.constants import SAAI_MAX_ACKNOWLEDGMENTS

        if self._drift_level != "BLOCK" or self._permanently_blocked:
            return self._status()

        self._acknowledgment_count += 1
        self._acknowledgment_history.append({
            "acknowledgment_number": self._acknowledgment_count,
            "drift_magnitude_at_ack": self._drift_magnitude,
            "baseline_fidelity": self._baseline_fidelity,
            "turn_count": len(self._fidelity_scores),
            "reason": reason,
        })

        if self._acknowledgment_count >= SAAI_MAX_ACKNOWLEDGMENTS:
            self._permanently_blocked = True
            return self._status()

        # Reset drift state, preserve baseline
        self._drift_level = "NORMAL"
        self._drift_magnitude = 0.0
        self._ewma = self._baseline_fidelity  # Reset EWMA to baseline

        return self._status()

    def get_drift_history(self) -> Dict[str, Any]:
        """Export drift tracker state for forensic reporting."""
        return {
            "all_fidelity_scores": list(self._fidelity_scores),
            "baseline_fidelity": self._baseline_fidelity,
            "baseline_std": self._baseline_std,
            "baseline_established": self._baseline_established,
            "ewma": self._ewma,
            "current_drift_level": self._drift_level,
            "current_drift_magnitude": self._drift_magnitude,
            "acknowledgment_count": self._acknowledgment_count,
            "acknowledgment_history": list(self._acknowledgment_history),
            "permanently_blocked": self._permanently_blocked,
            "total_turns": len(self._fidelity_scores),
        }

    def _status(self) -> Dict[str, Any]:
        from telos_core.constants import BASELINE_TURN_COUNT
        return {
            "drift_level": self._drift_level,
            "drift_magnitude": round(self._drift_magnitude, 4),
            "baseline_fidelity": self._baseline_fidelity,
            "baseline_established": self._baseline_established,
            "baseline_progress": min(len(self._fidelity_scores), BASELINE_TURN_COUNT) if not self._baseline_established else BASELINE_TURN_COUNT,
            "baseline_required": BASELINE_TURN_COUNT,
            "is_blocked": self._drift_level == "BLOCK" or self._permanently_blocked,
            "is_restricted": self._drift_level == "RESTRICT",
            "permanently_blocked": self._permanently_blocked,
            "turn_count": len(self._fidelity_scores),
            "acknowledgment_count": self._acknowledgment_count,
        }

    @property
    def drift_level(self) -> str:
        return self._drift_level

    @property
    def drift_magnitude(self) -> float:
        return self._drift_magnitude

    @property
    def is_blocked(self) -> bool:
        return self._drift_level == "BLOCK" or self._permanently_blocked

    def to_dict(self):
        """Serialize drift tracker state for persistence.

        Used by session state snapshots to survive daemon restarts.
        Complementary to get_drift_history() but structured for restore().
        """
        return {
            "baseline_fidelity": self._baseline_fidelity,
            "baseline_std": self._baseline_std,
            "baseline_established": self._baseline_established,
            "fidelity_scores": list(self._fidelity_scores),
            "ewma": self._ewma,
            "drift_level": self._drift_level,
            "drift_magnitude": self._drift_magnitude,
            "acknowledgment_count": self._acknowledgment_count,
            "acknowledgment_history": list(self._acknowledgment_history),
            "permanently_blocked": self._permanently_blocked,
        }

    def restore(self, state):
        """Restore drift tracker state from a persisted snapshot.

        Args:
            state: Dict from to_dict(), or None (no-op).
        """
        if not state:
            return
        self._baseline_fidelity = state.get("baseline_fidelity")
        self._baseline_std = state.get("baseline_std", 0.0)
        self._baseline_established = state.get("baseline_established", False)
        self._fidelity_scores = list(state.get("fidelity_scores", []))
        self._ewma = state.get("ewma")
        self._drift_level = state.get("drift_level", "NORMAL")
        self._drift_magnitude = state.get("drift_magnitude", 0.0)
        self._acknowledgment_count = state.get("acknowledgment_count", 0)
        self._acknowledgment_history = list(state.get("acknowledgment_history", []))
        self._permanently_blocked = state.get("permanently_blocked", False)

        # Migration: old-format state may have baseline_established=True
        # but ewma=None (pre-EWMA sliding window format).
        # Bootstrap EWMA from the baseline mean to prevent TypeError.
        if self._baseline_established and self._ewma is None:
            self._ewma = self._baseline_fidelity


# Token budgets per decision tier -- proportional brevity
_TOKEN_BUDGETS = {
    "EXECUTE": 600,
    "CLARIFY": 400,
    "ESCALATE": 250,
}


@dataclass
class AgenticTurnResult:
    """Complete result from processing one agentic turn."""
    # Tier 1: Request fidelity
    purpose_fidelity: float = 0.0
    scope_fidelity: float = 0.0

    # Tier 2: Tool selection
    tool_fidelity: float = 0.0
    selected_tool: Optional[str] = None
    tool_rankings: List[Dict[str, Any]] = field(default_factory=list)

    # Chain tracking
    chain_sci: float = 0.0
    chain_length: int = 0
    chain_broken: bool = False
    effective_fidelity: float = 0.0

    # Boundary
    boundary_triggered: bool = False
    boundary_name: Optional[str] = None
    boundary_fidelity: float = 0.0

    # Decision
    decision: str = "EXECUTE"
    decision_explanation: str = ""

    # Output
    tool_output: str = ""
    response_text: str = ""

    # SAAI Drift tracking
    drift_level: str = "NORMAL"
    drift_magnitude: float = 0.0
    saai_baseline: Optional[float] = None
    saai_blocked: bool = False
    pre_block_response: Optional[str] = None  # Preserved response before BLOCK override

    # Dual-model confirmer (Article 72 audit trail)
    confirmer_decision: Optional[str] = None
    confirmer_effective_fidelity: Optional[float] = None
    confirmer_boundary_triggered: Optional[bool] = None
    dual_model_agreement: Optional[str] = None  # "both_escalate", "one_escalate", "agree", "disagree"

    # Confirmer safety gate telemetry (MPNet boundary-only check)
    safety_gate_activated: bool = False
    safety_gate_score: Optional[float] = None
    safety_gate_would_override: bool = False
    safety_gate_override_applied: bool = False

    # Step metadata
    step_number: int = 0


class AgenticResponseManager:
    """
    Orchestrates governance for the agentic live mode.

    Thin composition layer: all governance math is delegated to
    AgenticFidelityEngine. This class handles initialization,
    result mapping, response generation, and mock tool execution.
    """

    def __init__(self, llm_client=None, model_name=None, backend="auto",
                 confirmer=False, setfit_classifier=None, threshold_config=None,
                 **kwargs):
        """Initialize with lazy embedding provider and mock executor.

        Args:
            llm_client: Optional pre-configured LLM client. If provided, skips
                        the lazy Mistral import (CLI path). If None, falls back
                        to lazy Mistral import (Observatory path) or template strings.
            model_name: Optional embedding model name or alias ("minilm", "mpnet").
                        Defaults to MiniLM if not specified.
            backend: Embedding inference backend ("auto", "onnx", "torch", "mlx").
                        Defaults to "auto" (ONNX if available, else PyTorch).
                        Use "mlx" for Apple Silicon native acceleration.
            confirmer: If True, enable dual-model confirmer. Uses MPNet as
                       second opinion when primary model decision is below
                       EXECUTE threshold. Graduated response: both-ESCALATE →
                       ESCALATE, one-ESCALATE → CLARIFY, neither → keep primary.
            setfit_classifier: Optional SetFitBoundaryClassifier instance.
                        If None, auto-discovers from standard model directories.
            threshold_config: Optional ThresholdConfig for optimizer trials.
                        When provided, passed to AgenticFidelityEngine instances.
                        When None, engines use production defaults.
            **kwargs: Accepts and ignores deprecated params (e.g. safety_gate)
                        for backward compatibility.
        """
        self._embed_fn = None
        self._mock_executor = MockToolExecutor()
        self._initialized = False
        self._llm_client = llm_client
        self._llm_client_checked = llm_client is not None
        self._drift_tracker = AgenticDriftTracker()
        self._model_name = model_name
        self._backend = backend or "auto"
        self._confirmer_enabled = confirmer
        self._confirmer_embed_fn = None
        self._confirmer_initialized = False
        self._setfit_classifier = setfit_classifier
        self._setfit_discovered = setfit_classifier is not None
        self._threshold_config = threshold_config

        # Per-template cache: template_id -> (AgenticPA, AgenticFidelityEngine)
        self._engine_cache: Dict[str, Any] = {}
        self._confirmer_engine_cache: Dict[str, Any] = {}

    def _ensure_initialized(self):
        """Lazy-initialize the embedding function."""
        if self._initialized:
            return
        try:
            from telos_core.embedding_provider import EmbeddingProvider
            kwargs = {"backend": self._backend}
            if self._model_name:
                kwargs["model_name"] = self._model_name
            provider = EmbeddingProvider(**kwargs)
            self._embed_fn = provider.encode
            self._initialized = True
        except Exception as e:
            logger.warning(f"Could not initialize embedding provider: {e}")
            self._embed_fn = None
            self._initialized = True

    def _ensure_confirmer_initialized(self):
        """Lazy-initialize the confirmer embedding function (MPNet)."""
        if self._confirmer_initialized or not self._confirmer_enabled:
            return
        try:
            from telos_core.embedding_provider import EmbeddingProvider
            # Confirmer uses the opposite model from primary
            confirmer_model = "mpnet" if (self._model_name or "minilm") != "mpnet" else "minilm"
            provider = EmbeddingProvider(model_name=confirmer_model, backend="auto")
            self._confirmer_embed_fn = provider.encode
            self._confirmer_initialized = True
            logger.info(f"Confirmer initialized with model: {confirmer_model}")
        except Exception as e:
            logger.warning(f"Could not initialize confirmer provider: {e}")
            self._confirmer_embed_fn = None
            self._confirmer_initialized = True

    def _get_confirmer_engine(self, template: AgenticTemplate):
        """Get or create the confirmer AgenticFidelityEngine for a template."""
        if template.id in self._confirmer_engine_cache:
            return self._confirmer_engine_cache[template.id]

        if not self._confirmer_embed_fn:
            return None

        try:
            from telos_governance.agentic_pa import AgenticPA
            from telos_governance.agentic_fidelity import AgenticFidelityEngine
            from telos_governance.tool_selection_gate import TOOL_SETS

            tool_defs = TOOL_SETS.get(template.tool_set_key, [])

            pa = AgenticPA.create_from_template(
                purpose=template.purpose,
                scope=template.scope,
                boundaries=template.boundaries,
                tools=tool_defs,
                embed_fn=self._confirmer_embed_fn,
                example_requests=template.example_requests,
                scope_example_requests=getattr(template, 'scope_example_requests', None),
                template_id=f"{template.id}_confirmer",
                safe_exemplars=getattr(template, 'safe_exemplars', None) or None,
            )

            engine = AgenticFidelityEngine(
                embed_fn=self._confirmer_embed_fn,
                pa=pa,
                violation_keywords=getattr(template, 'violation_keywords', None),
            )

            self._confirmer_engine_cache[template.id] = engine
            logger.info(f"Created confirmer engine for template '{template.id}'")
            return engine

        except Exception as e:
            logger.warning(f"Could not create confirmer engine for '{template.id}': {e}")
            return None

    def _run_confirmer(self, user_request: str, template: AgenticTemplate) -> Optional[Dict[str, Any]]:
        """Run the confirmer model and return its decision signals.

        Only called when the primary model decision is below EXECUTE threshold
        (i.e., in the ambiguous zone where a second opinion adds value).

        Returns:
            Dict with confirmer_decision, confirmer_effective_fidelity,
            confirmer_boundary_triggered, or None if confirmer unavailable.
        """
        self._ensure_confirmer_initialized()
        engine = self._get_confirmer_engine(template)
        if engine is None:
            return None

        try:
            confirmer_result = engine.score_action(user_request)
            return {
                "confirmer_decision": confirmer_result.decision.value.upper(),
                "confirmer_effective_fidelity": confirmer_result.effective_fidelity,
                "confirmer_boundary_triggered": confirmer_result.boundary_triggered,
            }
        except Exception as e:
            logger.warning(f"Confirmer scoring failed: {e}")
            return None

    def _get_engine(self, template: AgenticTemplate):
        """
        Get or create the AgenticFidelityEngine for a template.

        On first call per template, builds an AgenticPA from the template
        using create_from_template, then wraps it in an AgenticFidelityEngine.
        Both are cached by template.id.

        Returns:
            AgenticFidelityEngine or None if embedding is unavailable.
        """
        if template.id in self._engine_cache:
            return self._engine_cache[template.id]

        if not self._embed_fn:
            return None

        try:
            from telos_governance.agentic_pa import AgenticPA
            from telos_governance.agentic_fidelity import AgenticFidelityEngine
            from telos_governance.tool_selection_gate import TOOL_SETS

            # Resolve ToolDefinition objects from the template's tool_set_key
            tool_defs = TOOL_SETS.get(template.tool_set_key, [])

            pa = AgenticPA.create_from_template(
                purpose=template.purpose,
                scope=template.scope,
                boundaries=template.boundaries,
                tools=tool_defs,
                embed_fn=self._embed_fn,
                example_requests=template.example_requests,
                scope_example_requests=getattr(template, 'scope_example_requests', None),
                template_id=template.id,
                safe_exemplars=getattr(template, 'safe_exemplars', None) or None,  # Fallback only; per-boundary corpus loaded by create_from_template
            )

            # ── Two-Gate: attach per-tool centroids if definitions available ──
            # This adds Gate 1 data without overwriting purpose_embedding.
            # The abstract mission-text centroid stays intact for Gate 2.
            tool_defs_module = getattr(template, 'tool_definitions_module', None)
            if tool_defs_module:
                try:
                    from telos_governance.pa_constructor import PAConstructor
                    constructor = PAConstructor(self._embed_fn)
                    tool_centroids = constructor._build_tool_centroids(tool_defs_module)
                    pa.tool_centroids = tool_centroids  # type: ignore[attr-defined]
                    # Merge exemplar embeddings (additive, not replacing)
                    extra_embs = constructor._collect_exemplar_embeddings(tool_defs_module)
                    if extra_embs:
                        existing = getattr(pa, 'purpose_example_embeddings', None) or []
                        pa.purpose_example_embeddings = existing + extra_embs
                    logger.info(
                        f"Two-gate: attached {len(tool_centroids)} tool centroids "
                        f"to template '{template.id}'"
                    )
                except Exception as e:
                    logger.warning(f"Two-gate tool centroid attachment failed: {e}")

            # Auto-discover SetFit classifier if not already loaded
            setfit_cls = self._discover_setfit(template.id)

            engine = AgenticFidelityEngine(
                embed_fn=self._embed_fn,
                pa=pa,
                violation_keywords=getattr(template, 'violation_keywords', None),
                setfit_classifier=setfit_cls,
                threshold_config=self._threshold_config,
                # confirmer_mode disconnected from scoring path (dual-model experiment conclusive)
            )

            self._engine_cache[template.id] = engine
            if setfit_cls:
                logger.info(f"Created AgenticFidelityEngine for template '{template.id}' with SetFit L1.5")
            else:
                logger.info(f"Created AgenticFidelityEngine for template '{template.id}'")
            return engine

        except Exception as e:
            logger.warning(f"Could not create fidelity engine for '{template.id}': {e}")
            return None

    def _discover_setfit(self, template_id: str):
        """Auto-discover SetFit classifier for a template.

        Checks (in order):
        1. Explicit classifier passed to constructor
        2. Domain-specific model directory (models/setfit_{domain}_v1/)
        3. Healthcare fallback model (models/setfit_healthcare_v1/)

        Returns SetFitBoundaryClassifier or None.
        """
        if self._setfit_classifier is not None:
            return self._setfit_classifier

        if self._setfit_discovered:
            return self._setfit_classifier

        self._setfit_discovered = True

        try:
            from telos_governance.setfit_classifier import SetFitBoundaryClassifier
        except ImportError:
            return None

        import os
        # Find project root (parent of telos_governance/)
        _gov_dir = os.path.dirname(os.path.abspath(__file__))
        _project_root = os.path.dirname(_gov_dir)

        # Domain-specific: extract domain from template_id (e.g., "openclaw_governed" -> "openclaw")
        # Only load domain-specific models -- no cross-domain fallback
        domain = template_id.split("_")[0] if "_" in template_id else template_id
        candidates = [
            os.path.join(_project_root, "models", f"setfit_{domain}_v1"),
        ]

        for model_dir in candidates:
            onnx_path = os.path.join(model_dir, "model.onnx")
            if os.path.isdir(model_dir) and os.path.exists(onnx_path):
                try:
                    cal_path = os.path.join(model_dir, "calibration.json")
                    # Read composite_boost from manifest if available
                    _composite_boost = False
                    manifest_path = os.path.join(model_dir, "manifest.json")
                    if os.path.exists(manifest_path):
                        import json as _json
                        with open(manifest_path) as _mf:
                            _manifest = _json.load(_mf)
                        _composite_boost = _manifest.get("composite_boost", False)
                    self._setfit_classifier = SetFitBoundaryClassifier(
                        model_dir=model_dir,
                        calibration_path=cal_path if os.path.exists(cal_path) else None,
                        composite_boost=_composite_boost,
                    )
                    logger.info(f"SetFit L1.5 auto-discovered: {model_dir}")
                    return self._setfit_classifier
                except Exception as e:
                    logger.warning(f"SetFit load failed for {model_dir}: {e}")

        return None

    # -------------------------------------------------------------------------
    # LLM response generation (Steward pattern)
    # -------------------------------------------------------------------------

    def _get_llm_client(self):
        """
        Lazy-initialize the Mistral LLM client.

        Returns None silently if API key is missing or client creation fails.
        Cached after first call to avoid repeated initialization attempts.
        """
        if self._llm_client_checked:
            return self._llm_client

        self._llm_client_checked = True
        try:
            from telos_observatory.services.mistral_client import get_cached_mistral_client
            self._llm_client = get_cached_mistral_client()
            logger.info("Agentic LLM client initialized successfully")
        except Exception as e:
            logger.debug(f"LLM client not available (API key missing or error): {e}")
            self._llm_client = None

        return self._llm_client

    def _build_agentic_system_prompt(
        self,
        template: AgenticTemplate,
        decision: str,
        tool_output: str = "",
    ) -> str:
        """
        Build a decision-aware system prompt for LLM response generation.

        Follows the Steward pattern: the LLM always knows what agent it is,
        what tools it has, what the governance decision was, and what its
        boundaries are. This prevents hallucination by providing full context.
        """
        boundaries_text = "\n".join(f"  - {b}" for b in template.boundaries)
        tools_text = ", ".join(template.tools)

        # Decision-specific instruction block
        if decision == "EXECUTE":
            decision_block = (
                f"GOVERNANCE DECISION: EXECUTE -- the request is approved.\n"
                f"TOOL OUTPUT:\n{tool_output}\n\n"
                f"Interpret the tool output naturally for the user. Explain what "
                f"the results mean in context. If the output contains data, "
                f"summarize the key findings."
            )
        elif decision == "CLARIFY":
            decision_block = (
                f"GOVERNANCE DECISION: CLARIFY -- the request is close to your purpose "
                f"but needs clarification before you can act.\n"
                f"Ask a targeted question to understand what the user needs. "
                f"Reference your available tools ({tools_text}) so the user "
                f"knows what you can help with."
            )
        elif decision == "ESCALATE":
            decision_block = (
                f"GOVERNANCE DECISION: ESCALATE -- the request conflicts with your "
                f"operational boundaries.\n"
                f"Explain firmly but politely that you cannot proceed. Reference "
                f"the specific limitation without exposing internal governance "
                f"details. Suggest how the user might rephrase their request."
            )
        else:  # ESCALATE fallback
            decision_block = (
                f"GOVERNANCE DECISION: ESCALATE -- the request is outside your scope.\n"
                f"Explain firmly but politely that you cannot proceed. This request "
                f"requires human review. Suggest how the user might rephrase."
            )

        return (
            f"{template.system_prompt}\n\n"
            f"AGENT IDENTITY:\n"
            f"  Purpose: {template.purpose}\n"
            f"  Scope: {template.scope}\n"
            f"  Available tools: {tools_text}\n\n"
            f"OPERATIONAL BOUNDARIES:\n"
            f"{boundaries_text}\n\n"
            f"{decision_block}\n\n"
            f"RESPONSE GUIDELINES:\n"
            f"- Be conversational and natural\n"
            f"- Keep responses concise: 2-3 short paragraphs maximum\n"
            f"- Do NOT mention fidelity scores, governance decisions, or internal metrics\n"
            f"- Do NOT use phrases like 'governance boundary' or 'fidelity threshold'\n"
            f"- Address the user's request directly without over-explaining\n"
            f"- Do NOT use bullet points or numbered lists unless presenting data results"
        )

    def _build_conversation_history(
        self,
        step_number: int,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        """
        Build conversation history from prior agentic steps.

        If conversation_history is provided (CLI path), use it directly.
        Otherwise, attempt to read from Streamlit session state (Observatory path).
        Falls back to empty list if neither is available.

        Args:
            step_number: Current step number (1-based)
            conversation_history: Optional pre-built history (list of {role, content} dicts)
        """
        if conversation_history is not None:
            return conversation_history

        history = []
        try:
            import streamlit as st
            for i in range(1, step_number):
                step_data = st.session_state.get(f'agentic_step_{i}_data')
                if step_data:
                    user_msg = step_data.get('user_request', '')
                    assistant_msg = step_data.get('response_text', '')
                    if user_msg:
                        history.append({'role': 'user', 'content': user_msg})
                    if assistant_msg:
                        history.append({'role': 'assistant', 'content': assistant_msg})
        except Exception as e:
            logger.debug(f"Could not build conversation history: {e}")
        return history

    def _generate_llm_response(
        self,
        user_request: str,
        template: AgenticTemplate,
        decision: str,
        tool_output: str,
        step_number: int,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[str]:
        """
        Generate an LLM response using the Steward pattern.

        Returns None on ANY failure -- the caller keeps the template string
        as a fallback. This ensures the agentic tab never breaks due to
        LLM issues.
        """
        client = self._get_llm_client()
        if client is None:
            return None

        try:
            system_prompt = self._build_agentic_system_prompt(
                template, decision, tool_output
            )
            history = self._build_conversation_history(step_number, conversation_history)
            max_tokens = _TOKEN_BUDGETS.get(decision, 400)

            messages = [{'role': 'system', 'content': system_prompt}]
            messages.extend(history)
            messages.append({'role': 'user', 'content': user_request})

            response = client.generate(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
            )

            if not response or not response.strip():
                logger.warning("LLM returned empty response")
                return None

            # Post-generation fidelity check
            if not self._check_response_fidelity(response, template, decision):
                logger.warning("LLM response failed fidelity check, using template")
                return None

            return response

        except Exception as e:
            error_str = str(e).lower()
            if "rate limit" in error_str:
                logger.info("Rate limited, retrying after 2s backoff")
                time.sleep(2)
                try:
                    response = client.generate(
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=0.7,
                    )
                    if response and response.strip():
                        return response
                except Exception:
                    pass
            logger.debug(f"LLM generation failed (using template fallback): {e}")
            return None

    def _check_response_fidelity(
        self, llm_response: str, template: AgenticTemplate, decision: str
    ) -> bool:
        """
        Lightweight post-generation fidelity check.

        Ensures the LLM response is semantically related to the agent's
        purpose. Skips check for ESCALATE (refusals are intentionally
        low-fidelity to purpose). Returns True on any error (accept response).
        """
        if decision == "ESCALATE":
            return True

        if not self._embed_fn:
            return True

        try:
            import numpy as np
            response_emb = np.array(self._embed_fn(llm_response))
            purpose_emb = np.array(self._embed_fn(template.purpose))

            # Cosine similarity
            dot = np.dot(response_emb, purpose_emb)
            norm = np.linalg.norm(response_emb) * np.linalg.norm(purpose_emb)
            if norm == 0:
                return True
            similarity = dot / norm

            # 0.25 floor -- very permissive, only catches completely unrelated responses
            if similarity < 0.25:
                logger.warning(
                    f"Response fidelity {similarity:.3f} below 0.25 floor for "
                    f"template '{template.id}'"
                )
                return False
            return True
        except Exception:
            return True

    def _get_token_budget(self, decision: str) -> int:
        """Get the token budget for a decision tier."""
        return _TOKEN_BUDGETS.get(decision, 400)

    def process_request(
        self,
        user_request: str,
        template: AgenticTemplate,
        step_number: int,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> AgenticTurnResult:
        """
        Process a user request through multi-dimensional governance.

        Delegates all governance scoring to AgenticFidelityEngine, then
        maps the result to AgenticTurnResult and generates response text.

        Args:
            user_request: The user's natural language request
            template: The active agent template
            step_number: Current step number (1-based)
            conversation_history: Optional pre-built history for LLM context (CLI path).
                                  If None, falls back to Streamlit session state (Observatory path).

        Returns:
            AgenticTurnResult with all governance metrics and response
        """
        self._ensure_initialized()
        result = AgenticTurnResult(step_number=step_number)

        engine = self._get_engine(template)
        if engine is None:
            # Fallback: no engine available (embeddings failed to load)
            result.decision = "ESCALATE"
            result.decision_explanation = "Governance engine unavailable."
            result.response_text = (
                "The governance engine is not available. "
                "Please check that the embedding provider is correctly configured."
            )
            return result

        # --- Score the action through the governance engine ---
        engine_result = engine.score_action(user_request)

        # --- Map engine result to AgenticTurnResult ---
        result.purpose_fidelity = engine_result.purpose_fidelity
        result.scope_fidelity = engine_result.scope_fidelity
        result.tool_fidelity = engine_result.tool_fidelity
        result.chain_sci = engine_result.chain_continuity
        result.boundary_fidelity = engine_result.boundary_violation
        result.boundary_triggered = engine_result.boundary_triggered
        result.effective_fidelity = engine_result.effective_fidelity
        result.chain_broken = engine_result.chain_broken
        result.selected_tool = engine_result.selected_tool
        result.chain_length = step_number

        # Safety gate telemetry (disconnected -- always inactive)
        result.safety_gate_activated = False
        result.safety_gate_score = None
        result.safety_gate_would_override = False
        result.safety_gate_override_applied = False

        # Map decision enum to uppercase string for main.py compatibility
        result.decision = engine_result.decision.value.upper()

        # Map tool_rankings to the format expected by tool_palette_panel.py
        result.tool_rankings = self._map_tool_rankings(
            engine_result.tool_rankings,
            engine_result.selected_tool,
            engine_result.boundary_triggered,
            engine_result.tool_blocked,
        )

        # Build decision explanation from dimension explanations
        result.decision_explanation = self._build_explanation(engine_result)

        # --- SAAI Sliding Window Drift Tracking ---
        drift_status = self._drift_tracker.record_fidelity(result.effective_fidelity)
        result.drift_level = drift_status["drift_level"]
        result.drift_magnitude = drift_status["drift_magnitude"]
        result.saai_baseline = drift_status["baseline_fidelity"]
        result.saai_blocked = drift_status["is_blocked"]

        # --- SAAI RESTRICT override: tighten EXECUTE threshold ---
        # When drift reaches RESTRICT (15-20%), actions that barely qualify
        # for EXECUTE are downgraded to CLARIFY. This is the graduated sanction
        # between WARNING (observation only) and BLOCK (session freeze).
        # Pattern mirrors the BLOCK override at lines 714-738.
        if drift_status["is_restricted"] and result.decision == "EXECUTE":
            from telos_core.constants import (
                SAAI_RESTRICT_EXECUTE_THRESHOLD,
                ST_SAAI_RESTRICT_EXECUTE_THRESHOLD,
            )
            restrict_thresh = (
                ST_SAAI_RESTRICT_EXECUTE_THRESHOLD
                if engine._is_sentence_transformer()
                else SAAI_RESTRICT_EXECUTE_THRESHOLD
            )
            if result.effective_fidelity < restrict_thresh:
                result.decision = "CLARIFY"
                result.decision_explanation = (
                    f"SAAI RESTRICT: Drift {drift_status['drift_magnitude']:.1%} "
                    f"tightened EXECUTE threshold to {restrict_thresh:.2f}. "
                    f"Effective fidelity {result.effective_fidelity:.2%} requires clarification."
                )

        # SAAI RESTRICT + boundary violation: compound sanctioning (Ostrom DP5).
        # A boundary violation during an already-restricted session warrants
        # maximum escalation -- the combination is more severe than either alone.
        if drift_status["is_restricted"] and result.boundary_triggered:
            result.decision = "ESCALATE"
            result.decision_explanation = (
                f"SAAI RESTRICT + BOUNDARY VIOLATION: Drift {drift_status['drift_magnitude']:.1%} "
                f"with boundary violation triggers compound escalation. "
                f"Session requires immediate human review."
            )

        # --- Dual-Model Confirmer (graduated boundary detection) ---
        # Fires only when primary decision is NOT EXECUTE (ambiguous zone)
        # and confirmer is enabled. Uses agreement patterns to adjust confidence:
        #   Both ESCALATE  → keep ESCALATE (76.9% precision in validation)
        #   One ESCALATE   → upgrade to CLARIFY (seek human input)
        #   Neither        → keep primary decision
        if self._confirmer_enabled and result.decision != "EXECUTE":
            confirmer_signals = self._run_confirmer(user_request, template)
            if confirmer_signals:
                result.confirmer_decision = confirmer_signals["confirmer_decision"]
                result.confirmer_effective_fidelity = confirmer_signals["confirmer_effective_fidelity"]
                result.confirmer_boundary_triggered = confirmer_signals["confirmer_boundary_triggered"]

                primary_escalate = result.decision == "ESCALATE"
                confirmer_escalate = confirmer_signals["confirmer_decision"] == "ESCALATE"

                if primary_escalate and confirmer_escalate:
                    result.dual_model_agreement = "both_escalate"
                    # Both agree on ESCALATE -- high confidence, keep it
                elif primary_escalate and not confirmer_escalate:
                    result.dual_model_agreement = "primary_only_escalate"
                    # Primary caught it, confirmer didn't -- keep ESCALATE (conservative)
                elif not primary_escalate and confirmer_escalate:
                    result.dual_model_agreement = "confirmer_only_escalate"
                    # Confirmer caught something primary missed -- upgrade to CLARIFY
                    if result.decision not in ("ESCALATE", "CLARIFY"):
                        result.decision = "CLARIFY"
                        result.decision_explanation = (
                            f"DUAL-MODEL CONFIRMER: Primary={engine_result.decision.value.upper()} "
                            f"but confirmer flagged ESCALATE "
                            f"(eff={confirmer_signals['confirmer_effective_fidelity']:.2%}). "
                            f"Upgraded to CLARIFY for human review."
                        )
                else:
                    result.dual_model_agreement = "agree"
                    # Both agree on non-ESCALATE -- keep primary decision

        # --- Generate response and tool output based on decision ---
        decision_key = engine_result.decision.value.upper()

        if decision_key == "ESCALATE":
            # Boundary violation or very low fidelity requiring human review
            boundary_detail = engine_result.dimension_explanations.get("boundary", "")
            result.selected_tool = None
            result.tool_output = ""
            result.response_text = (
                f"I cannot proceed with this request. It conflicts with my operational "
                f"governance boundaries. {boundary_detail} "
                f"Could you rephrase your request to align with my purpose: {template.purpose}?"
            )
            # Mark all tools as blocked in rankings
            for t in result.tool_rankings:
                t["is_blocked"] = True
                t["is_selected"] = False

        elif decision_key == "EXECUTE":
            # High fidelity -- run mock tool execution
            tool_name = result.selected_tool
            if tool_name:
                result.tool_output = self._mock_executor.execute(
                    tool_name, user_request, template.id
                )
                result.response_text = (
                    f"**Tool:** {tool_name}\n\n"
                    f"```\n{result.tool_output}\n```\n\n"
                    f"Request executed successfully with "
                    f"{result.effective_fidelity:.0%} governance fidelity."
                )
            else:
                result.response_text = (
                    f"Request aligned ({result.effective_fidelity:.0%} fidelity) "
                    f"but no specific tool was selected. "
                    f"Available tools: {', '.join(template.tools)}."
                )

        elif decision_key == "CLARIFY":
            # Moderate fidelity -- dimension-aware clarification
            weakest_dim, weakest_score, weakest_detail = self._find_weakest_dimension(engine_result)
            result.response_text = (
                f"This request is close to my purpose "
                f"({engine_result.purpose_fidelity:.0%} alignment) but "
                f"{weakest_dim} scored {weakest_score:.0%}. "
                f"{weakest_detail} "
                f"Could you clarify what specific data or action "
                f"you need? I have access to: {', '.join(template.tools)}."
            )



        else:
            # ESCALATE -- very low fidelity
            result.response_text = (
                f"This request requires human review. It falls outside my scope. "
                f"I'm a {template.name} focused on: {template.purpose}. "
                f"I cannot assist with unrelated topics without human approval."
            )

        # --- LLM response generation (Steward pattern) ---
        # Template strings above become fallbacks if LLM fails for any reason.
        llm_response = self._generate_llm_response(
            user_request=user_request,
            template=template,
            decision=decision_key,
            tool_output=result.tool_output,
            step_number=step_number,
            conversation_history=conversation_history,
        )
        if llm_response is not None:
            result.response_text = llm_response

        # SAAI BLOCK override: if drift exceeds 20%, force ESCALATE
        # Applied last so it cannot be overwritten by response generation.
        if drift_status["is_blocked"] and result.decision != "ESCALATE":
            result.pre_block_response = result.response_text
            result.decision = "ESCALATE"
            if drift_status.get("permanently_blocked"):
                result.decision_explanation = (
                    f"SAAI PERMANENT BLOCK: Maximum acknowledgments exhausted. "
                    f"Session cannot be resumed. Start a new session."
                )
                result.response_text = (
                    "This session has been permanently terminated. The maximum number of "
                    "drift acknowledgments has been reached. Please start a new session. "
                    "This is a safety requirement per SAAI guidelines."
                )
            else:
                result.decision_explanation = (
                    f"SAAI DRIFT BLOCK: Sliding window drift {drift_status['drift_magnitude']:.1%} "
                    f"exceeds 20% threshold. Session requires human review before continuing."
                )
                result.response_text = (
                    "This session has been paused due to governance drift exceeding "
                    "safety thresholds. A human reviewer must acknowledge the drift before "
                    "the session can continue. This is a safety requirement per SAAI guidelines."
                )

        return result

    def reset_drift(self):
        """Reset SAAI drift tracking for new session."""
        self._drift_tracker.reset()

    def acknowledge_drift(self, reason: str = "") -> Dict[str, Any]:
        """Acknowledge a BLOCK drift state and resume the session."""
        return self._drift_tracker.acknowledge_drift(reason)

    def get_drift_history(self) -> Dict[str, Any]:
        """Export drift tracker state for forensic reporting."""
        return self._drift_tracker.get_drift_history()

    def reset_chain(self):
        """Reset the action chain for all cached engines."""
        for engine in self._engine_cache.values():
            engine.reset_chain()
        for engine in self._confirmer_engine_cache.values():
            engine.reset_chain()

    # -------------------------------------------------------------------------
    # Private mapping helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _map_tool_rankings(
        engine_rankings: List[Dict],
        selected_tool: Optional[str],
        boundary_triggered: bool,
        tool_blocked: bool,
    ) -> List[Dict[str, Any]]:
        """
        Map engine tool_rankings to the format consumed by tool_palette_panel.py.

        The palette expects dicts with keys:
            tool_name, fidelity, display_pct, is_selected, is_blocked
        """
        mapped = []
        for entry in engine_rankings:
            tool_name = entry.get("tool", entry.get("tool_name", "unknown"))
            fidelity = entry.get("fidelity", 0.0)
            display_pct = int(fidelity * 100)
            is_selected = (tool_name == selected_tool) and not boundary_triggered
            is_blocked = boundary_triggered or (tool_blocked and tool_name == selected_tool)

            mapped.append({
                "tool_name": tool_name,
                "fidelity": fidelity,
                "display_pct": display_pct,
                "is_selected": is_selected,
                "is_blocked": is_blocked,
            })

        return mapped

    @staticmethod
    def _find_weakest_dimension(engine_result):
        """Find the lowest-scoring governance dimension and its explanation.

        Returns:
            Tuple of (dimension_name, score, explanation_text).
        """
        dimensions = {
            "purpose": engine_result.purpose_fidelity,
            "scope": engine_result.scope_fidelity,
            "tool": engine_result.tool_fidelity,
            "chain": engine_result.chain_continuity,
        }
        weakest_dim = min(dimensions, key=dimensions.get)
        weakest_score = dimensions[weakest_dim]
        weakest_detail = engine_result.dimension_explanations.get(weakest_dim, "")
        return weakest_dim, weakest_score, weakest_detail

    @staticmethod
    def _build_explanation(engine_result) -> str:
        """
        Build a human-readable decision explanation from dimension explanations.
        """
        decision_str = engine_result.decision.value.upper()
        explanations = engine_result.dimension_explanations

        parts = [f"{decision_str} (effective fidelity: {engine_result.effective_fidelity:.0%})."]

        for dim_key in ("purpose", "scope", "tool", "chain", "boundary"):
            detail = explanations.get(dim_key)
            if detail:
                parts.append(detail)

        return " ".join(parts)

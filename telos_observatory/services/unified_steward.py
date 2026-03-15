"""
TELOS Runtime Steward - Production Version
-------------------------------------------
The Mitigation Bridge Layer (MBL) operationalization implementing
dual-architecture continuous process governance.

Architecture (Per Whitepaper Section 5):
----------------------------------------
The Mitigation Bridge Layer consists of two coordinated subsystems:

1. **Statistical Process Controller (SPC Engine)**
   - Measurement: Computes fidelity F_t, error e_t, stability ΔV_t
   - Analysis: Determines state (MONITOR/CORRECT/INTERVENE/ESCALATE)
   - Monitoring: Tracks P_cap and process trends
   - Generates control signals for Proportional Controller

2. **Proportional Controller (Intervention Arm)**
   - Receives error signal e_t from SPC Engine
   - Computes correction force F = K·e_t
   - Executes graduated interventions
   - Reports outcomes back to SPC Engine

The Runtime Steward is the forward-functioning orchestrator that
coordinates these two subsystems in real-time, implementing the
Teleological Operator pattern: x_{t+1} = f(x_t) - K_p · e_t

DMAIC Integration:
-----------------
Each conversational turn is a micro-DMAIC cycle:
- Define: Governance perimeter (purpose/scope/boundaries)
- Measure: SPC Engine computes fidelity and error
- Analyze: SPC Engine determines governance state
- Improve: Proportional Controller applies correction
- Control: Verify stabilization via Lyapunov convergence

This implements continuous improvement at runtime, fulfilling
QSR requirements for monitored and controlled processes.

Enhancements in This Version:
-----------------------------
- Complete error handling with specific exceptions
- Session lifecycle validation
- Graceful degradation on component failures
- Comprehensive logging
- Natural language explanations via LLM
- Health monitoring integration
- Telemetry export with error recovery
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pathlib import Path
import time
import json
import logging

from telos_core.primacy_math import (
    MathematicalState,
    PrimacyAttractorMath,
    TelicFidelityCalculator
)
from telos_core.proportional_controller import ProportionalController
from telos_core.conversation_manager import ConversationManager
try:
    from telos_observatory.services.intercepting_llm_wrapper import InterceptingLLMWrapper
except ImportError:
    InterceptingLLMWrapper = None  # Optional: only needed for live interception

from telos_core.exceptions import (
    SessionError,
    SessionNotStartedError,
    SessionAlreadyActiveError,
    AttractorConstructionError,
    OutputDirectoryError,
    TelemetryExportError,
    error_context
)

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class PrimacyAttractor:
    """Governance perimeter configuration."""
    purpose: List[str]
    scope: List[str]
    boundaries: List[str]
    privacy_level: float = 0.8
    constraint_tolerance: float = 0.2
    task_priority: float = 0.7


# ============================================================================
# Runtime Steward (Mitigation Bridge Layer Orchestrator)
# ============================================================================

class UnifiedGovernanceSteward:
    """
    Runtime Steward - The Mitigation Bridge Layer Orchestrator.
    
    Operationalizes the dual-architecture MBL:
    - SPC Engine: Continuous measurement and analysis
    - Proportional Controller: Graduated interventions
    
    Together these implement the Teleological Operator pattern,
    providing continuous process governance at runtime.
    
    Responsibilities:
    1. Session orchestration (start → process → end)
    2. SPC Engine measurements (fidelity, error, stability)
    3. Proportional Controller coordination
    4. Developer diagnostics (explain, diagnose, summarize)
    5. Runtime health monitoring
    6. Telemetry export
    
    Example:
        >>> steward = UnifiedGovernanceSteward(
        ...     attractor=config,
        ...     llm_client=mistral,
        ...     embedding_provider=embedder
        ... )
        >>> steward.start_session()
        >>> result = steward.process_turn(user_input, model_response)
        >>> summary = steward.end_session()
    """
    
    def __init__(
        self,
        attractor: PrimacyAttractor,
        llm_client,
        embedding_provider,
        enable_interventions: bool = True,
        dev_commentary_mode: str = "silent",
        health_monitor = None
    ):
        """
        Initialize Runtime Steward.
        
        Args:
            attractor: Governance perimeter configuration
            llm_client: LLM client for natural language operations
            embedding_provider: Text-to-vector encoder
            enable_interventions: Enable Proportional Controller
            dev_commentary_mode: "silent", "concise", or "verbose"
            health_monitor: Optional SystemHealthMonitor instance
        
        Raises:
            AttractorConstructionError: If attractor cannot be built
        """
        self.attractor_config = attractor
        self.llm_client = llm_client
        self.embedding_provider = embedding_provider
        self.enable_interventions = enable_interventions
        self.dev_commentary_mode = dev_commentary_mode
        self.health = health_monitor
        
        # Validate configuration
        self._validate_configuration()
        
        # Initialize SPC Engine components
        logger.info("Initializing SPC Engine (Measurement Subsystem)...")
        self._initialize_spc_engine()
        
        # Initialize Proportional Controller (Intervention Arm)
        logger.info("Initializing Proportional Controller (Intervention Arm)...")
        self._initialize_proportional_controller()

        # Initialize InterceptingLLMWrapper for active mitigation
        logger.info("Initializing Active Mitigation Layer (InterceptingLLMWrapper)...")
        self.llm_wrapper = InterceptingLLMWrapper(
            llm_client=llm_client,
            embedding_provider=embedding_provider,
            steward_ref=self,  # Pass self so wrapper can access attractor
            salience_threshold=0.70,
            coupling_threshold=0.76  # Goldilocks: Aligned threshold
        )

        # Set attractor attributes for wrapper to use
        self.attractor = attractor  # Store textual attractor for wrapper
        self.attractor_center = None  # Will be set by progressive extractor or manually
        self.distance_scale = None  # Will be calculated based on embedding dimension

        # Initialize session state
        self.session_id: Optional[str] = None
        self.session_active = False
        self.session_start_time: Optional[float] = None
        self.session_states: List[MathematicalState] = []
        self.turn_history: List[Dict[str, Any]] = []
        
        # Initialize conversation manager
        self.conversation = ConversationManager()
        
        logger.info("Runtime Steward initialized (MBL operational)")
    
    def _validate_configuration(self) -> None:
        """Validate governance configuration."""
        if not self.attractor_config.purpose:
            raise AttractorConstructionError("Purpose cannot be empty")
        if not self.attractor_config.scope:
            raise AttractorConstructionError("Scope cannot be empty")
        if not self.attractor_config.boundaries:
            raise AttractorConstructionError("Boundaries cannot be empty")
    
    def _initialize_spc_engine(self) -> None:
        """
        Initialize Statistical Process Controller (SPC Engine).

        The SPC Engine is the measurement and analysis subsystem
        responsible for:
        - Computing fidelity scores
        - Measuring error signals
        - Tracking process stability (Lyapunov)
        - Determining governance state
        """
        with error_context("initializing SPC Engine"):
            # Build primacy attractor
            purpose_text = " ".join(self.attractor_config.purpose)
            scope_text = " ".join(self.attractor_config.scope)

            # PERFORMANCE: Batch both embeddings in a single API call (2x faster)
            if hasattr(self.embedding_provider, 'batch_encode'):
                logger.info("Using batch embedding for SPC Engine initialization")
                embeddings = self.embedding_provider.batch_encode([purpose_text, scope_text])
                p_vec = embeddings[0]
                s_vec = embeddings[1]
            else:
                # Fallback to sequential encoding
                p_vec = self.embedding_provider.encode(purpose_text)
                s_vec = self.embedding_provider.encode(scope_text)
            
            self.attractor_math = PrimacyAttractorMath(
                purpose_vector=p_vec,
                scope_vector=s_vec,
                privacy_level=self.attractor_config.privacy_level,
                constraint_tolerance=self.attractor_config.constraint_tolerance,
                task_priority=self.attractor_config.task_priority
            )
            
            # Initialize fidelity calculator
            self.fidelity_calc = TelicFidelityCalculator()
            
            logger.info(f"SPC Engine ready (basin radius: {self.attractor_math.basin_radius:.3f})")
    
    def _initialize_proportional_controller(self) -> None:
        """
        Initialize Proportional Controller (Intervention Arm).
        
        The Proportional Controller receives error signals from
        the SPC Engine and executes graduated interventions:
        - State 1 (MONITOR): No action
        - State 2 (CORRECT): Context injection
        - State 3 (INTERVENE): Regeneration
        - State 4 (ESCALATE): Block and escalate
        """
        with error_context("initializing Proportional Controller"):
            self.proportional_controller = ProportionalController(
                attractor=self.attractor_math,
                llm_client=self.llm_client,
                embedding_provider=self.embedding_provider,
                enable_interventions=self.enable_interventions
            )
            
            thresholds = self.proportional_controller.get_intervention_statistics()['thresholds']
            logger.info(
                f"Proportional Controller ready "
                f"(ε_min={thresholds['epsilon_min']:.3f}, "
                f"ε_max={thresholds['epsilon_max']:.3f})"
            )
    
    # ========================================================================
    # Session Lifecycle
    # ========================================================================
    
    def start_session(self, session_id: Optional[str] = None) -> str:
        """
        Start new governed session.
        
        Initializes:
        - Session ID and start time
        - Conversation history
        - Telemetry collection
        - Health monitoring
        
        Args:
            session_id: Optional custom session ID
        
        Returns:
            Session ID
        
        Raises:
            SessionAlreadyActiveError: If session already active
        """
        if self.session_active:
            raise SessionAlreadyActiveError(self.session_id)
        
        self.session_id = session_id or f"session_{int(time.time())}"
        self.session_active = True
        self.session_start_time = time.time()
        self.session_states = []
        self.turn_history = []
        
        # Set governance context
        self.conversation.set_governance_context(
            purpose=self.attractor_config.purpose,
            scope=self.attractor_config.scope,
            boundaries=self.attractor_config.boundaries
        )

        # CRITICAL FIX: Compute attractor_center embedding for intervention system
        # The InterceptingLLMWrapper needs this to detect drift
        if self.attractor_center is None:
            logger.info("Computing attractor center embedding from PA text...")
            pa_text = " ".join(self.attractor_config.purpose + self.attractor_config.scope)
            self.attractor_center = self.embedding_provider.encode(pa_text)
            logger.info(f"Attractor center computed: {self.attractor_center.shape}")

            # Calculate distance_scale based on embedding dimensionality
            # For 1024-dim embeddings, this gives scale of ~8.0 (instead of hardcoded 2.0)
            # Formula: sqrt(dim) * 0.25 accounts for high-dimensional geometry
            import numpy as np
            embedding_dim = self.attractor_center.shape[0]
            self.distance_scale = np.sqrt(embedding_dim) * 0.25
            logger.info(f"Distance scale set to {self.distance_scale:.3f} for {embedding_dim}-dim embeddings")

        logger.info(f"Session started: {self.session_id}")
        
        if self.dev_commentary_mode == "verbose":
            print(f"[TELOS] Session started: {self.session_id}")
            print(f"[TELOS] Basin radius: {self.attractor_math.basin_radius:.3f}")
        
        # Health monitor startup
        if self.health:
            self.health.startup_checks(
                session_id=self.session_id,
                condition="operational",
                components={
                    "llm_client": self.llm_client,
                    "embedding_provider": self.embedding_provider,
                    "attractor_math": self.attractor_math,
                    "proportional_controller": self.proportional_controller
                }
            )
        
        return self.session_id
    
    def process_turn(self, user_input: str, model_response: str) -> Dict[str, Any]:
        """
        Process pre-existing turn (REPLAY MODE ONLY).

        For active governance, use generate_governed_response() instead.

        This method is kept for analyzing historical conversations where
        responses already exist. It provides post-hoc analysis and can
        regenerate responses if drift is detected.

        MBL Processing Pipeline:
        1. SPC Engine measures state (fidelity, error, stability)
        2. SPC Engine determines governance state
        3. Proportional Controller applies correction if needed
        4. Verify stabilization via Lyapunov
        5. Export telemetry

        Args:
            user_input: User's message
            model_response: Model's pre-generated response

        Returns:
            Dict with final_response, metrics, governance_action

        Raises:
            SessionNotStartedError: If session not active
        """
        if not self.session_active:
            raise SessionNotStartedError("process_turn")
        
        turn_start_time = time.time()
        turn_number = len(self.turn_history) + 1
        
        with error_context("processing turn", turn=turn_number, session=self.session_id):
            # Add user message to history
            self.conversation.add_user_message(user_input, time.time())
            
            # ==== SPC ENGINE: MEASUREMENT ====
            # Compute mathematical state
            embedding = self.embedding_provider.encode(model_response)
            state = MathematicalState(
                embedding=embedding,
                turn_number=turn_number,
                timestamp=time.time(),
                text_content=model_response
            )
            self.session_states.append(state)
            
            # Get conversation history for Proportional Controller
            conversation_history = self.conversation.get_messages_for_api()
            
            # ==== PROPORTIONAL CONTROLLER: INTERVENTION ====
            # Apply proportional correction if SPC Engine signals need
            intervention_result = self.proportional_controller.process_turn(
                state=state,
                response_text=model_response,
                conversation_history=conversation_history,
                turn_number=turn_number
            )
            
            # Determine final response
            if intervention_result["intervention_applied"]:
                final_response = intervention_result["intervention_result"].modified_response
                response_was_modified = True
            else:
                final_response = model_response
                response_was_modified = False
            
            # Add final response to conversation
            self.conversation.add_assistant_message(final_response, time.time())
            
            # ==== SPC ENGINE: ANALYSIS ====
            # Compute metrics
            in_basin = intervention_result["in_basin"]
            error_signal = intervention_result["error_signal"]
            lyapunov = self.attractor_math.compute_lyapunov_function(state)
            
            telic_fidelity = self.fidelity_calc.compute_hard_fidelity(
                self.session_states, self.attractor_math
            )
            
            # Determine governance action
            if intervention_result["is_meta"]:
                action = "antimeta"
            elif intervention_result["intervention_applied"]:
                action = intervention_result["intervention_result"].type
            else:
                action = "none"
            
            # Calculate turn latency
            turn_latency_ms = (time.time() - turn_start_time) * 1000
            
            # Record turn data
            turn_record = {
                "turn_number": turn_number,
                "user_input": user_input,
                "model_response": model_response,
                "final_response": final_response,
                "response_was_modified": response_was_modified,
                "governance_action": action,
                "intervention_applied": intervention_result["intervention_applied"],
                "metrics": {
                    "primacy_basin_membership": in_basin,
                    "error_signal": error_signal,
                    "lyapunov_value": lyapunov,
                    "telic_fidelity": telic_fidelity
                },
                "timestamp": time.time(),
                "latency_ms": turn_latency_ms
            }
            self.turn_history.append(turn_record)
            
            if self.dev_commentary_mode == "verbose":
                print(f"[TELOS T{turn_number}] F={telic_fidelity:.3f} | "
                      f"V={lyapunov:.3f} | Basin={in_basin} | Action={action}")
            
            # Health monitoring hook
            if self.health:
                self.health.on_turn(
                    turn_number=turn_number,
                    turn_record=turn_record,
                    raw_latency_ms=turn_latency_ms
                )
            
            return {
                "final_response": final_response,
                "response_was_modified": response_was_modified,
                "governance_action": action,
                "intervention_applied": intervention_result["intervention_applied"],
                "intervention_result": intervention_result.get("intervention_result"),
                "metrics": turn_record["metrics"]
            }

    def generate_governed_response(
        self,
        user_input: str,
        conversation_context: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Generate governed response through active mitigation layer.

        This is the NEW method for live conversations (ACTIVE GOVERNANCE).

        Unlike process_turn() which receives pre-generated responses,
        this method intercepts BEFORE generation, enabling:
        - Salience maintenance (prevents drift)
        - Coupling checks (detects drift)
        - Regeneration (corrects drift)

        Args:
            user_input: User's message
            conversation_context: Full conversation history (list of message dicts)

        Returns:
            Dict with:
            - governed_response: The response to show user
            - intervention_applied: bool
            - intervention_type: str
            - fidelity: float
            - salience: float
            - metrics: Dict

        Raises:
            SessionNotStartedError: If session not active
        """
        if not self.session_active:
            raise SessionNotStartedError("generate_governed_response")

        turn_start = time.time()
        turn_number = len(self.turn_history) + 1

        # Use wrapper to generate governed response
        governed_response = self.llm_wrapper.generate(user_input, conversation_context)

        # Get intervention info from wrapper
        if self.llm_wrapper.interventions:
            latest = self.llm_wrapper.interventions[-1]
            intervention_applied = latest.intervention_type not in ["none", "learning_phase"]
            intervention_type = latest.intervention_type
            fidelity = latest.fidelity_governed if latest.fidelity_governed else 1.0
            salience = latest.salience_after if latest.salience_after else 1.0
        else:
            intervention_applied = False
            intervention_type = "none"
            fidelity = 1.0
            salience = 1.0

        # Record turn
        turn_record = {
            "turn_number": turn_number,
            "user_input": user_input,
            "governed_response": governed_response,
            "intervention_applied": intervention_applied,
            "intervention_type": intervention_type,
            "metrics": {
                "telic_fidelity": fidelity,
                "salience": salience,
                "turn_latency_ms": (time.time() - turn_start) * 1000
            }
        }

        self.turn_history.append(turn_record)

        return {
            "governed_response": governed_response,
            "intervention_applied": intervention_applied,
            "intervention_type": intervention_type,
            "fidelity": fidelity,
            "salience": salience,
            "metrics": turn_record["metrics"]
        }

    def end_session(self) -> Dict[str, Any]:
        """
        End session and generate summary.
        
        Returns:
            Session summary with:
            - Final metrics
            - Intervention statistics
            - Session metadata
            - Telemetry export status
        
        Raises:
            SessionNotStartedError: If no active session
        """
        if not self.session_active:
            raise SessionNotStartedError("end_session")
        
        with error_context("ending session", session=self.session_id):
            # Compute final metrics
            if self.session_states:
                final_fidelity = self.fidelity_calc.compute_hard_fidelity(
                    self.session_states,
                    self.attractor_math
                )
            else:
                final_fidelity = 0.0
            
            # Get intervention statistics from Proportional Controller
            intervention_stats = self.proportional_controller.get_intervention_statistics()
            
            # Build summary
            summary = {
                "session_id": self.session_id,
                "session_duration_seconds": time.time() - self.session_start_time,
                "total_turns": len(self.turn_history),
                "session_metadata": {
                    "final_telic_fidelity": final_fidelity,
                    "total_interventions": intervention_stats["total_interventions"],
                    "intervention_rate": (
                        intervention_stats["total_interventions"] / len(self.turn_history)
                        if self.turn_history else 0.0
                    )
                },
                "intervention_statistics": intervention_stats,
                "turn_history": self.turn_history
            }
            
            # Health monitoring finalization
            if self.health:
                self.health.on_session_end(summary)
            
            # Mark session as inactive
            self.session_active = False
            
            logger.info(
                f"Session ended: {self.session_id} "
                f"(F={final_fidelity:.3f}, {len(self.turn_history)} turns)"
            )
            
            if self.dev_commentary_mode != "silent":
                print(f"\n[TELOS] Session ended: {self.session_id}")
                print(f"[TELOS] Final fidelity: {final_fidelity:.3f}")
                print(f"[TELOS] Total turns: {len(self.turn_history)}")
                print(f"[TELOS] Interventions: {intervention_stats['total_interventions']}")
            
            return summary
    
    # ========================================================================
    # Developer Diagnostics
    # ========================================================================
    
    def explain_current_state(self) -> str:
        """
        Generate natural language explanation of current governance state.
        
        Uses LLM to explain:
        - Current fidelity level
        - Recent trajectory
        - Intervention history
        - Recommendations
        
        Returns:
            Human-readable explanation
        """
        if not self.session_states:
            return "No turns processed yet in this session."
        
        # Get current metrics
        current_state = self.session_states[-1]
        fidelity = self.fidelity_calc.compute_hard_fidelity(
            self.session_states,
            self.attractor_math
        )
        error = self.attractor_math.compute_error_signal(current_state)
        in_basin = self.attractor_math.compute_basin_membership(current_state)
        
        # Build explanation prompt
        prompt = f"""Explain the current governance state:

Fidelity: {fidelity:.3f} (0.0=poor, 1.0=perfect)
Error Signal: {error:.3f}
In Basin: {in_basin}
Total Turns: {len(self.session_states)}

Purpose: {', '.join(self.attractor_config.purpose)}
Scope: {', '.join(self.attractor_config.scope)}

Explain in 2-3 sentences what this means for conversation quality."""
        
        try:
            explanation = self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            return explanation
        except Exception as e:
            logger.warning(f"Could not generate explanation: {e}")
            return f"Fidelity: {fidelity:.3f}, Error: {error:.3f}, Basin: {in_basin}"
    
    def diagnose_failures(self) -> Dict[str, Any]:
        """
        Diagnose potential governance failures.
        
        Analyzes:
        - Low fidelity trends
        - Repeated interventions
        - Basin membership violations
        - Lyapunov instability
        
        Returns:
            Dict with diagnostics and recommendations
        """
        if not self.turn_history:
            return {"error": "No turns to diagnose"}
        
        diagnostics = {
            "failure_modes": [],
            "mathematical_anomalies": [],
            "recommendations": []
        }
        
        # Check for low fidelity
        recent_fidelities = [
            t["metrics"]["telic_fidelity"]
            for t in self.turn_history[-5:]
        ]
        if recent_fidelities and sum(recent_fidelities) / len(recent_fidelities) < 0.7:
            diagnostics["failure_modes"].append({
                "severity": "high",
                "description": "Low average fidelity in recent turns"
            })
            diagnostics["recommendations"].append({
                "priority": "high",
                "issue": "Conversation drifting from purpose",
                "fix": "Reduce constraint_tolerance or increase intervention strength"
            })
        
        # Check for excessive interventions
        intervention_rate = sum(
            1 for t in self.turn_history if t["intervention_applied"]
        ) / len(self.turn_history)
        
        if intervention_rate > 0.5:
            diagnostics["failure_modes"].append({
                "severity": "medium",
                "description": f"High intervention rate ({intervention_rate:.1%})"
            })
            diagnostics["recommendations"].append({
                "priority": "medium",
                "issue": "Too many interventions (high overhead)",
                "fix": "Increase constraint_tolerance or adjust purpose/scope"
            })
        
        return diagnostics


# Alias for conceptual consistency
TeleologicalOperator = UnifiedGovernanceSteward

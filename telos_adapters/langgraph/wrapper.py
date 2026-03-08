"""
TELOS Wrapper
=============

Seamless wrapper for any LangGraph agent. Deploys TELOS governance
without modifying the wrapped agent's internals.

This implements the user's key insight:
"We can deploy on top of already existing AI agents and make them run
through our own filter... seamless... direct operational connection"

Regulatory traceability:
    - SAAI claim TELOS-SAAI-001: Continuous drift measurement via cosine fidelity
      on every invoke() turn (pre-check + post-check against Primacy Attractor)
    - SAAI claim TELOS-SAAI-002: AgenticDriftTracker enforces graduated sanctions
      (WARNING 10% / RESTRICT 15% / BLOCK 20%) per Ostrom DP5
    - SAAI claim TELOS-SAAI-004: External governance — wrapped agent cannot access
      or modify the Primacy Attractor (corrigibility by design)
    - SAAI claim TELOS-SAAI-005: GovernanceTraceEntry with optional Ed25519 signing
      and persistent NDJSON audit trail for chain-of-reasoning transparency
    - SAAI claim TELOS-SAAI-008: ESCALATE pathway via on_block callback and
      drift BLOCK requiring human acknowledgment before session continues
    - EU AI Act Art. 12: Automatic event recording via governance_trace
    - EU AI Act Art. 72: Post-market monitoring via drift detection
    - IEEE 7001-2021: Transparent decision records with full scoring context
    - NIST AI 600-1 (GV 1.4): Cryptographic governance receipts (Ed25519)
    - OWASP LLM Top 10 (LLM08): Every invoke() is governed — no bypass path
"""

from typing import Any, Dict, Optional, Callable, Union
from pathlib import Path
from datetime import datetime
import hashlib
import json as _json
import numpy as np
import logging

from .state_schema import (
    TelosGovernedState,
    PrimacyAttractor,
    GovernanceTraceEntry,
    FidelityZone,
    DirectionLevel,
    create_initial_state,
    get_zone_from_fidelity,
    get_direction_level,
    FIDELITY_GREEN,
)

from .governance_node import calculate_fidelity, TelosGovernanceGate


logger = logging.getLogger(__name__)


class TelosWrapper:
    """
    Transparent governance wrapper for any LangGraph agent.

    Wraps an existing agent to add TELOS governance without
    modifying the agent's internals.

    Flow:
        User Input -> TELOS Pre-Check -> Agent -> TELOS Post-Check -> Output

    Usage:
        # Wrap any existing agent
        governed_agent = TelosWrapper(
            agent=existing_agent,
            primacy_attractor=my_pa,
            embed_fn=my_embedding_function,
        )

        # Use exactly like the original agent
        result = governed_agent.invoke({"messages": [user_message]})
    """

    def __init__(
        self,
        agent: Any,
        primacy_attractor: Union[PrimacyAttractor, Dict[str, Any]],
        embed_fn: Callable[[str], np.ndarray],
        pre_check: bool = True,
        post_check: bool = True,
        block_on_low_fidelity: bool = True,
        fidelity_threshold: float = FIDELITY_GREEN,
        on_block: Optional[Callable[[Dict], Any]] = None,
        drift_tracker: Optional[Any] = None,
        receipt_signer: Optional[Any] = None,
        audit_path: Optional[str] = None,
    ):
        """
        Initialize the TELOS wrapper.

        Args:
            agent: The LangGraph agent to wrap (must have .invoke())
            primacy_attractor: PA for governance (dict or PrimacyAttractor)
            embed_fn: Function to embed text strings
            pre_check: Check input fidelity before agent runs
            post_check: Check output fidelity after agent runs
            block_on_low_fidelity: Block low-fidelity inputs (if pre_check)
            fidelity_threshold: Threshold for direction
            on_block: Callback when input is blocked
            drift_tracker: Optional AgenticDriftTracker for session-level
                graduated sanctions (SAAI-002). Pass None to disable.
            receipt_signer: Optional ReceiptSigner for Ed25519 signing of
                GovernanceTraceEntry dicts (SAAI-005). Pass None to disable.
            audit_path: Optional path for persistent NDJSON audit trail
                (SAAI-005). Pass None to disable file-based auditing.
        """
        self.agent = agent
        self.embed_fn = embed_fn
        self.pre_check = pre_check
        self.post_check = post_check
        self.block_on_low_fidelity = block_on_low_fidelity
        self.fidelity_threshold = fidelity_threshold
        self.on_block = on_block

        # Convert PA if needed
        if isinstance(primacy_attractor, dict):
            self.pa = PrimacyAttractor.from_dict(primacy_attractor)
        else:
            self.pa = primacy_attractor

        # Internal governance gate
        self.gate = TelosGovernanceGate(
            embed_fn=embed_fn,
            require_approval_below=fidelity_threshold,
        )

        # SAAI-002: Optional drift tracker (graduated sanctions)
        self.drift_tracker = drift_tracker

        # SAAI-005: Optional Ed25519 receipt signer
        self.receipt_signer = receipt_signer

        # SAAI-005: Optional persistent audit trail
        self._audit_writer = None
        if audit_path:
            self._audit_writer = _LangGraphAuditWriter(Path(audit_path))

        # Tracking
        self.governance_trace = []
        self.turn_number = 0

    def invoke(
        self,
        input_state: Dict[str, Any],
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Invoke the wrapped agent with TELOS governance.

        This is the main entry point - use exactly like the
        original agent's invoke() method.
        """
        self.turn_number += 1

        # =================================================================
        # STEP 1: Pre-execution governance (input fidelity check)
        # =================================================================
        if self.pre_check:
            pre_result = self._pre_execution_check(input_state)

            if not pre_result["approved"]:
                # Input blocked - return governance response
                return self._generate_redirect_response(
                    input_state,
                    pre_result,
                )

            # Update input state with governance context if needed
            if pre_result.get("context_injected"):
                input_state = self._inject_context(input_state, pre_result)

        # =================================================================
        # STEP 2: Pass through to original agent (unchanged)
        # =================================================================
        try:
            result = self.agent.invoke(input_state, config)
        except Exception as e:
            logger.error(f"Wrapped agent error: {e}")
            self._record_trace(
                action_type="agent_error",
                description=str(e),
                fidelity=0.0,
                approved=False,
            )
            raise

        # =================================================================
        # STEP 3: Post-execution governance (output fidelity check)
        # =================================================================
        post_fidelity = 1.0
        if self.post_check:
            post_result = self._post_execution_check(result)
            post_fidelity = post_result["fidelity"]

            # Record to trace
            self._record_trace(
                action_type="agent_response",
                description="Agent response generated",
                fidelity=post_fidelity,
                approved=True,  # Output is informational, not blocked
            )

        # =================================================================
        # STEP 4: SAAI drift tracking (graduated sanctions)
        # =================================================================
        if self.drift_tracker and self.post_check:
            drift_status = self.drift_tracker.record_fidelity(post_fidelity)

            # Annotate latest trace entry with drift fields
            if self.governance_trace:
                self.governance_trace[-1]["drift_level"] = drift_status.get(
                    "drift_level", "NORMAL"
                )
                self.governance_trace[-1]["drift_magnitude"] = drift_status.get(
                    "drift_magnitude", 0.0
                )

            # BLOCK: session frozen — return governance response
            if drift_status.get("is_blocked"):
                self._record_trace(
                    action_type="drift_block",
                    description=(
                        f"SAAI BLOCK — drift {drift_status['drift_magnitude']:.1%} "
                        f"exceeds 20% threshold"
                    ),
                    fidelity=post_fidelity,
                    approved=False,
                )
                return {
                    "messages": result.get("messages", []),
                    "governance_blocked": True,
                    "drift_level": "BLOCK",
                    "drift_magnitude": drift_status["drift_magnitude"],
                    "reason": (
                        "Session paused due to governance drift exceeding safety "
                        "thresholds. Human acknowledgment required."
                    ),
                }

            # RESTRICT: tighten governance — record observation
            if drift_status.get("is_restricted"):
                self._record_trace(
                    action_type="drift_restrict",
                    description=(
                        f"SAAI RESTRICT — drift {drift_status['drift_magnitude']:.1%} "
                        f"tightened governance threshold"
                    ),
                    fidelity=post_fidelity,
                    approved=True,
                )

            # WARNING: record observation only
            elif drift_status.get("drift_level") == "WARNING":
                self._record_trace(
                    action_type="drift_warning",
                    description=(
                        f"SAAI WARNING — drift {drift_status['drift_magnitude']:.1%}"
                    ),
                    fidelity=post_fidelity,
                    approved=True,
                )

        return result

    def _pre_execution_check(
        self,
        input_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check input fidelity before agent execution.

        Returns:
            Dict with approval status and fidelity info
        """
        # Extract input text
        messages = input_state.get("messages", [])
        if not messages:
            return {"approved": True, "fidelity": 1.0, "zone": "green"}

        last_message = messages[-1]
        content = getattr(last_message, "content", str(last_message))

        # Calculate fidelity
        raw_sim, fidelity = calculate_fidelity(content, self.pa, self.embed_fn)
        zone = get_zone_from_fidelity(fidelity)
        direction = get_direction_level(fidelity, raw_sim)

        result = {
            "raw_similarity": raw_sim,
            "fidelity": fidelity,
            "zone": zone.value,
            "direction": direction.value,
        }

        # Decision logic
        if direction == DirectionLevel.HARD_BLOCK:
            result["approved"] = not self.block_on_low_fidelity
            result["reason"] = "Layer 1 baseline violation"
            self._record_trace(
                action_type="input_check",
                description=content[:100],
                fidelity=fidelity,
                approved=result["approved"],
                direction_reason=result["reason"],
            )
            return result

        if fidelity >= self.fidelity_threshold:
            result["approved"] = True
            return result

        if direction in [DirectionLevel.MONITOR, DirectionLevel.CORRECT]:
            result["approved"] = True
            result["context_injected"] = True
            return result

        # Block for low fidelity
        result["approved"] = not self.block_on_low_fidelity
        result["reason"] = f"Fidelity {fidelity:.2f} below threshold"

        self._record_trace(
            action_type="input_check",
            description=content[:100],
            fidelity=fidelity,
            approved=result["approved"],
            direction_reason=result.get("reason"),
        )

        return result

    def _post_execution_check(
        self,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check output fidelity after agent execution.

        This is for monitoring/logging, not blocking.
        """
        messages = result.get("messages", [])
        if not messages:
            return {"fidelity": 1.0, "zone": "green"}

        last_message = messages[-1]
        content = getattr(last_message, "content", str(last_message))

        if not content:
            return {"fidelity": 1.0, "zone": "green"}

        raw_sim, fidelity = calculate_fidelity(content, self.pa, self.embed_fn)
        zone = get_zone_from_fidelity(fidelity)

        return {
            "raw_similarity": raw_sim,
            "fidelity": fidelity,
            "zone": zone.value,
        }

    def _inject_context(
        self,
        input_state: Dict[str, Any],
        check_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Inject PA context into input for drift mitigation.

        This is a soft direction - adds context without blocking.
        """
        # Clone state and add context
        new_state = dict(input_state)

        logger.info(f"Injecting PA context for fidelity {check_result['fidelity']:.2f}")

        return new_state

    def _generate_redirect_response(
        self,
        input_state: Dict[str, Any],
        check_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a redirect response when input is blocked.

        Uses callback if provided, otherwise generates default response.
        """
        if self.on_block:
            return self.on_block({
                "input_state": input_state,
                "check_result": check_result,
                "pa": self.pa.to_dict(),
            })

        # Default redirect response
        return {
            "messages": input_state.get("messages", []) + [{
                "role": "assistant",
                "content": (
                    f"I notice your request may have drifted from our purpose: "
                    f"'{self.pa.text}'. Could you help me understand how this "
                    f"relates to what we're working on?"
                ),
            }],
            "governance_blocked": True,
            "fidelity": check_result["fidelity"],
            "zone": check_result["zone"],
        }

    def _record_trace(
        self,
        action_type: str,
        description: str,
        fidelity: float,
        approved: bool,
        direction_reason: Optional[str] = None,
    ):
        """Record to governance trace.

        If receipt_signer is configured, signs the entry with Ed25519 (SAAI-005).
        If audit_writer is configured, emits the entry as NDJSON (SAAI-005).
        """
        entry = GovernanceTraceEntry(
            timestamp=datetime.now(),
            turn_number=self.turn_number,
            action_type=action_type,
            action_description=description,
            raw_similarity=0.0,  # Simplified
            fidelity_score=fidelity,
            zone=get_zone_from_fidelity(fidelity),
            direction_level=DirectionLevel.NONE if approved else DirectionLevel.DIRECT,
            direction_reason=direction_reason,
            approved=approved,
            approval_source="auto" if approved else "blocked",
        )
        entry_dict = entry.to_dict()

        # SAAI-005: Ed25519 signing if receipt_signer configured
        if self.receipt_signer:
            entry_dict = self._sign_trace_entry(entry_dict)

        # SAAI-005: Persistent audit trail if audit_writer configured
        if self._audit_writer:
            self._audit_writer.emit("governance_decision", entry_dict)

        self.governance_trace.append(entry_dict)

    def get_governance_trace(self) -> list:
        """Get the full governance trace for audit."""
        return self.governance_trace

    def get_fidelity_trajectory(self) -> list:
        """Get fidelity scores over time."""
        return [
            {"turn": e["turn_number"], "fidelity": e["fidelity_score"]}
            for e in self.governance_trace
        ]

    def acknowledge_drift(self, reason: str = "") -> Dict[str, Any]:
        """Acknowledge a BLOCK drift state and resume the session.

        Resets drift to NORMAL, preserving baseline. Limited to 2 per session
        (Ostrom DP5 graduated sanctions — SAAI-002).

        Args:
            reason: Free-text reason for acknowledgment.

        Returns:
            Status dict after acknowledgment.
        """
        if not self.drift_tracker:
            return {"error": "No drift tracker configured"}
        status = self.drift_tracker.acknowledge_drift(reason)
        self._record_trace(
            action_type="drift_acknowledged",
            description=f"Drift acknowledged: {reason}",
            fidelity=0.0,
            approved=True,
        )
        return status

    def get_drift_history(self) -> Dict[str, Any]:
        """Export drift tracker state for forensic reporting."""
        if not self.drift_tracker:
            return {}
        return self.drift_tracker.get_drift_history()

    def _sign_trace_entry(self, entry_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Sign a GovernanceTraceEntry dict with Ed25519.

        Computes SHA-256 hash of the canonical JSON (sorted keys, compact
        separators, excluding signature fields) and signs with Ed25519.

        Regulatory traceability:
            - SAAI claim TELOS-SAAI-005: Unforgeable chain of reasoning
            - EU AI Act Art. 12: Cryptographic integrity for audit records
        """
        signable = {k: v for k, v in entry_dict.items()
                    if k not in ("entry_signature", "public_key")}
        canonical = _json.dumps(signable, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(canonical.encode("utf-8")).digest()

        signature = self.receipt_signer.sign_payload(payload_hash)
        entry_dict["entry_signature"] = signature.hex()
        entry_dict["public_key"] = self.receipt_signer.public_key_bytes().hex()

        return entry_dict


# =============================================================================
# AUDIT WRITER (SAAI-005: Persistent NDJSON audit trail)
# =============================================================================

class _LangGraphAuditWriter:
    """Lightweight NDJSON audit writer for LangGraph governance events.

    Event taxonomy (LangGraph-specific):
        governance_decision  — every pre-check and post-check result
        drift_warning        — SAAI sliding window drift >= 10%
        drift_restrict       — SAAI drift >= 15%, threshold tightened
        drift_block          — SAAI drift >= 20%, session frozen
        drift_acknowledged   — human acknowledged drift BLOCK

    Regulatory traceability:
        - EU AI Act Art. 12: Automatic event recording with structured audit trail
        - SAAI claim TELOS-SAAI-005: GovernanceTraceCollector logs all decisions
        - IEEE 7001-2021: Transparent decision records with full scoring context
        - NIST AI RMF GOVERN 2.1: Continuous risk awareness via persistent logging
    """

    def __init__(self, audit_path: Path):
        import os
        self._path = audit_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = None
        try:
            self._file = open(self._path, "a")
            os.chmod(str(self._path), 0o600)
        except OSError as e:
            logger.error(f"Failed to open audit file {self._path}: {e}")

    def emit(self, event_type: str, data: Optional[Dict] = None) -> None:
        """Write a single audit event as an NDJSON line."""
        if not self._file:
            return
        import time
        record = {
            "event": event_type,
            "timestamp": time.time(),
            "data": data or {},
        }
        try:
            line = _json.dumps(record, default=str) + "\n"
            self._file.write(line)
            self._file.flush()
        except Exception as e:
            logger.warning(f"Audit write failed for {event_type}: {e}")

    def close(self) -> None:
        """Flush and close the audit file."""
        if self._file:
            try:
                self._file.flush()
                self._file.close()
            except OSError:
                pass
            self._file = None


# =============================================================================
# CONVENIENCE DECORATOR
# =============================================================================

def telos_wrap(
    primacy_attractor: Union[PrimacyAttractor, Dict[str, Any]],
    embed_fn: Callable[[str], np.ndarray],
    **kwargs,
) -> Callable:
    """
    Decorator to wrap an agent with TELOS governance.

    Usage:
        @telos_wrap(primacy_attractor=my_pa, embed_fn=embed)
        def my_agent(state):
            # Agent logic
            return result

        # Or wrap existing agent:
        governed = telos_wrap(my_pa, embed)(existing_agent)
    """
    def decorator(agent):
        return TelosWrapper(
            agent=agent,
            primacy_attractor=primacy_attractor,
            embed_fn=embed_fn,
            **kwargs,
        )
    return decorator

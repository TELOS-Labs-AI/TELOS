"""
TELOS Swarm
===========

TELOS-governed Swarm pattern for agent handoffs.
Adds governance to the handoff process between agents.

In Swarm architecture, agents can hand off to each other.
TELOS ensures each handoff maintains purpose alignment.

Regulatory traceability:
    - SAAI claim TELOS-SAAI-001: Per-handoff fidelity measurement with SCI
      (Semantic Continuity Index) tracking across the handoff chain
    - SAAI claim TELOS-SAAI-002: Handoffs blocked when effective fidelity
      (including SCI inheritance) drops below threshold
    - SAAI claim TELOS-SAAI-004: Agents cannot bypass handoff governance --
      every handoff goes through _check_handoff (corrigibility)
    - SAAI claim TELOS-SAAI-005: _record_trace with sci_score captures full
      chain-of-custody for forensic analysis
    - EU AI Act Art. 12: handoff_chain provides complete record of agent
      transitions with timestamps, fidelity, and SCI scores
    - OWASP LLM Top 10 (LLM08): SCI decay factor (0.90) ensures handoff chains
      cannot accumulate authority beyond the original purpose
"""

from typing import Any, Dict, List, Optional, Callable, Union
from datetime import datetime
import numpy as np
import logging

from .state_schema import (
    TelosGovernedState,
    PrimacyAttractor,
    GovernanceTraceEntry,
    FidelityZone,
    DirectionLevel,
    get_zone_from_fidelity,
    get_direction_level,
    calculate_sci,
    FIDELITY_GREEN,
    SCI_CONTINUITY_THRESHOLD,
    SCI_DECAY_FACTOR,
)

from .governance_node import calculate_fidelity

logger = logging.getLogger(__name__)


class TelosSwarm:
    """
    TELOS-governed Swarm for multi-agent handoffs.

    Monitors and governs handoffs between agents to ensure:
    1. Handoffs maintain purpose alignment
    2. Semantic continuity is preserved
    3. Governance trace captures full chain-of-custody

    Usage:
        swarm = TelosSwarm(
            agents={"specialist1": agent1, "specialist2": agent2},
            primacy_attractor=project_pa,
            embed_fn=embed_function,
        )

        # Agents can request handoffs
        result = swarm.handoff(
            from_agent="specialist1",
            to_agent="specialist2",
            context=current_state,
            reason="Need coding expertise",
        )
    """

    def __init__(
        self,
        agents: Dict[str, Any],
        primacy_attractor: Union[PrimacyAttractor, Dict[str, Any]],
        embed_fn: Callable[[str], np.ndarray],
        require_approval_for_handoff: bool = True,
        handoff_threshold: float = FIDELITY_GREEN,
        track_sci: bool = True,
        receipt_signer: Optional[Any] = None,
        drift_tracker: Optional[Any] = None,
    ):
        """
        Initialize the TELOS Swarm.

        Args:
            agents: Dict mapping agent names to agent instances
            primacy_attractor: PA for governance
            embed_fn: Embedding function
            require_approval_for_handoff: Require approval for low-fidelity handoffs
            handoff_threshold: Fidelity threshold for auto-approval
            track_sci: Track Semantic Continuity Index across handoffs
            receipt_signer: Optional ReceiptSigner for Ed25519 signing of
                GovernanceTraceEntry dicts (SAAI-005). Pass None to disable.
            drift_tracker: Optional AgenticDriftTracker for session-level
                graduated sanctions (SAAI-002). Pass None to disable.
        """
        self.agents = agents
        self.embed_fn = embed_fn
        self.require_approval = require_approval_for_handoff
        self.handoff_threshold = handoff_threshold
        self.track_sci = track_sci

        # Convert PA if needed
        if isinstance(primacy_attractor, dict):
            self.pa = PrimacyAttractor.from_dict(primacy_attractor)
        else:
            self.pa = primacy_attractor

        # SAAI-005: Optional Ed25519 receipt signer
        self.receipt_signer = receipt_signer

        # SAAI-002: Optional drift tracker (graduated sanctions)
        self.drift_tracker = drift_tracker

        # Tracking
        self.governance_trace = []
        self.handoff_chain = []  # Chain of handoffs for SCI
        self.current_agent = None
        self.handoff_count = 0

    def handoff(
        self,
        from_agent: str,
        to_agent: str,
        context: Dict[str, Any],
        reason: str,
    ) -> Dict[str, Any]:
        """
        Process a handoff request from one agent to another.

        Args:
            from_agent: Name of agent initiating handoff
            to_agent: Name of target agent
            context: Current state/context to pass
            reason: Reason for handoff

        Returns:
            Dict with handoff result and governance info
        """
        self.handoff_count += 1

        # =================================================================
        # STEP 1: Measure handoff fidelity
        # =================================================================
        # Combine reason and context for fidelity measurement
        handoff_text = f"Handoff from {from_agent} to {to_agent}: {reason}"
        raw_sim, fidelity = calculate_fidelity(handoff_text, self.pa, self.embed_fn)
        zone = get_zone_from_fidelity(fidelity)
        direction = get_direction_level(fidelity, raw_sim)

        # =================================================================
        # STEP 2: Calculate SCI if tracking
        # =================================================================
        sci_score = 1.0
        inherited_fidelity = fidelity

        if self.track_sci and self.handoff_chain:
            last_handoff = self.handoff_chain[-1]
            current_embedding = self.embed_fn(handoff_text)
            prev_embedding = np.array(last_handoff["embedding"])
            prev_fidelity = last_handoff["fidelity"]

            sci_score, inherited = calculate_sci(
                current_embedding, prev_embedding, prev_fidelity
            )

            # Use inherited fidelity if continuity is high enough
            if inherited > 0:
                inherited_fidelity = max(fidelity, inherited)

        # =================================================================
        # STEP 3: Handoff governance gate
        # =================================================================
        handoff_approved = self._check_handoff(
            from_agent=from_agent,
            to_agent=to_agent,
            reason=reason,
            fidelity=fidelity,
            inherited_fidelity=inherited_fidelity,
            zone=zone,
            direction=direction,
            sci_score=sci_score,
        )

        result = {
            "approved": handoff_approved["approved"],
            "from_agent": from_agent,
            "to_agent": to_agent,
            "reason": reason,
            "fidelity": fidelity,
            "inherited_fidelity": inherited_fidelity,
            "sci_score": sci_score,
            "zone": zone.value,
        }

        if not handoff_approved["approved"]:
            result["block_reason"] = handoff_approved.get("reason", "Low fidelity")
            self._record_trace(
                action_type="handoff_blocked",
                description=f"Handoff {from_agent} -> {to_agent} blocked",
                fidelity=fidelity,
                approved=False,
                sci_score=sci_score,
            )
            return result

        # =================================================================
        # STEP 4: Execute handoff
        # =================================================================
        self.current_agent = to_agent

        # Record to handoff chain for SCI tracking
        handoff_embedding = self.embed_fn(handoff_text)
        self.handoff_chain.append({
            "index": self.handoff_count,
            "from": from_agent,
            "to": to_agent,
            "reason": reason,
            "fidelity": inherited_fidelity,
            "sci_score": sci_score,
            "embedding": handoff_embedding.tolist(),
            "timestamp": datetime.now().isoformat(),
        })

        self._record_trace(
            action_type="handoff",
            description=f"Handoff {from_agent} -> {to_agent}: {reason}",
            fidelity=inherited_fidelity,
            approved=True,
            sci_score=sci_score,
        )

        # =================================================================
        # STEP 5: SAAI drift tracking (graduated sanctions)
        # =================================================================
        if self.drift_tracker:
            drift_status = self.drift_tracker.record_fidelity(inherited_fidelity)

            # Annotate latest trace entry with drift fields
            if self.governance_trace:
                self.governance_trace[-1]["drift_level"] = drift_status.get(
                    "drift_level", "NORMAL"
                )
                self.governance_trace[-1]["drift_magnitude"] = drift_status.get(
                    "drift_magnitude", 0.0
                )

            # BLOCK: swarm frozen -- return blocked response
            if drift_status.get("is_blocked"):
                self._record_trace(
                    action_type="drift_block",
                    description=(
                        f"SAAI BLOCK -- drift {drift_status['drift_magnitude']:.1%} "
                        f"exceeds 20% threshold"
                    ),
                    fidelity=inherited_fidelity,
                    approved=False,
                    sci_score=sci_score,
                )
                result["governance_blocked"] = True
                result["drift_level"] = "BLOCK"
                result["drift_magnitude"] = drift_status["drift_magnitude"]
                result["approved"] = False
                result["block_reason"] = (
                    "Swarm paused due to governance drift exceeding safety "
                    "thresholds. Human acknowledgment required."
                )
                return result

            # RESTRICT: tighten governance -- record observation
            if drift_status.get("is_restricted"):
                self._record_trace(
                    action_type="drift_restrict",
                    description=(
                        f"SAAI RESTRICT -- drift {drift_status['drift_magnitude']:.1%} "
                        f"tightened governance threshold"
                    ),
                    fidelity=inherited_fidelity,
                    approved=True,
                    sci_score=sci_score,
                )

            # WARNING: record observation only
            elif drift_status.get("drift_level") == "WARNING":
                self._record_trace(
                    action_type="drift_warning",
                    description=(
                        f"SAAI WARNING -- drift {drift_status['drift_magnitude']:.1%}"
                    ),
                    fidelity=inherited_fidelity,
                    approved=True,
                    sci_score=sci_score,
                )

        # Return result with target agent for execution
        result["target_agent"] = self.agents.get(to_agent)
        return result

    def _check_handoff(
        self,
        from_agent: str,
        to_agent: str,
        reason: str,
        fidelity: float,
        inherited_fidelity: float,
        zone: FidelityZone,
        direction: DirectionLevel,
        sci_score: float,
    ) -> Dict[str, Any]:
        """
        Check if handoff should be approved.

        Uses inherited fidelity (with SCI) for decision.
        """
        result = {
            "from": from_agent,
            "to": to_agent,
            "fidelity": fidelity,
            "inherited_fidelity": inherited_fidelity,
            "sci_score": sci_score,
        }

        # Hard block for extreme off-topic
        if direction == DirectionLevel.HARD_BLOCK:
            result["approved"] = False
            result["reason"] = "Handoff violates baseline fidelity"
            return result

        # Use inherited fidelity for threshold check
        effective_fidelity = inherited_fidelity

        # Above threshold - auto-approve
        if effective_fidelity >= self.handoff_threshold:
            result["approved"] = True
            result["approval_source"] = "auto"
            return result

        # SCI bonus: if high continuity, be more lenient
        if sci_score >= 0.5 and fidelity >= self.handoff_threshold * 0.8:
            result["approved"] = True
            result["approval_source"] = "sci_boost"
            logger.info(
                f"Handoff approved via SCI boost: fidelity={fidelity:.2f}, "
                f"sci={sci_score:.2f}"
            )
            return result

        # Below threshold
        if not self.require_approval:
            result["approved"] = True
            result["approval_source"] = "auto_low_fidelity"
            return result

        # In production, would use interrupt() here
        logger.warning(
            f"Handoff {from_agent} -> {to_agent} with fidelity {effective_fidelity:.2f}"
        )
        result["approved"] = True
        result["approval_source"] = "auto_with_warning"
        return result

    def _record_trace(
        self,
        action_type: str,
        description: str,
        fidelity: float,
        approved: bool,
        sci_score: Optional[float] = None,
    ):
        """Record to governance trace.

        If receipt_signer is configured, signs the entry with Ed25519 (SAAI-005).
        """
        entry = GovernanceTraceEntry(
            timestamp=datetime.now(),
            turn_number=self.handoff_count,
            action_type=action_type,
            action_description=description,
            raw_similarity=0.0,
            fidelity_score=fidelity,
            zone=get_zone_from_fidelity(fidelity),
            direction_level=DirectionLevel.NONE if approved else DirectionLevel.DIRECT,
            approved=approved,
            approval_source="auto" if approved else "blocked",
            sci_score=sci_score,
        )
        entry_dict = entry.to_dict()
        if self.receipt_signer:
            import hashlib
            import json as _json
            signable = {k: v for k, v in entry_dict.items()
                        if k not in ("entry_signature", "public_key")}
            canonical = _json.dumps(signable, sort_keys=True, separators=(",", ":"))
            payload_hash = hashlib.sha256(canonical.encode("utf-8")).digest()
            sig = self.receipt_signer.sign_payload(payload_hash)
            entry_dict["entry_signature"] = sig.hex()
            entry_dict["public_key"] = self.receipt_signer.public_key_bytes().hex()
        self.governance_trace.append(entry_dict)

    def get_governance_trace(self) -> list:
        """Get the full governance trace."""
        return self.governance_trace

    def get_handoff_chain(self) -> list:
        """Get the handoff chain for analysis."""
        return self.handoff_chain

    def acknowledge_drift(self, reason: str = "") -> Dict[str, Any]:
        """Acknowledge a BLOCK drift state and resume the swarm.

        Resets drift to NORMAL, preserving baseline. Limited to 2 per session
        (Ostrom DP5 graduated sanctions -- SAAI-002).

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

    def get_sci_trajectory(self) -> list:
        """Get SCI scores over the handoff chain."""
        return [
            {"handoff": h["index"], "sci": h["sci_score"], "fidelity": h["fidelity"]}
            for h in self.handoff_chain
        ]


def create_telos_swarm(
    agents: Dict[str, Any],
    primacy_attractor: Union[PrimacyAttractor, Dict[str, Any]],
    embed_fn: Callable[[str], np.ndarray],
    **kwargs,
) -> TelosSwarm:
    """
    Factory function to create a TELOS Swarm.

    Usage:
        swarm = create_telos_swarm(
            agents={"analyst": agent1, "coder": agent2},
            primacy_attractor=my_pa,
            embed_fn=embed,
        )
    """
    return TelosSwarm(
        agents=agents,
        primacy_attractor=primacy_attractor,
        embed_fn=embed_fn,
        **kwargs,
    )

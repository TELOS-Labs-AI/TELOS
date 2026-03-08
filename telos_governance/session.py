"""
Governance Session: Composable session lifecycle for CLI and integrations.

Composes TelemetricSessionManager (HMAC-SHA512 session keys) with
ReceiptSigner (Ed25519 persistent signatures) into a unified governance
session that produces signed, verifiable receipts for every decision.

This is the integration layer between:
- telos_privacy/cryptography (TKeys: session-bound encryption + signing)
- telos_governance/receipt_signer (Ed25519: persistent asymmetric signatures)
- telos_governance/governance_protocol (GovernanceEvent: the decisions to sign)

Compliance:
- NIST AI RMF (MANAGE 4.1): Session lifecycle with proof generation satisfies
  post-deployment monitoring requirements — each session produces a cryptographic
  proof chain of all governance decisions made during the session.
- FedRAMP CA-7 (Continuous Monitoring): Each session is a monitoring epoch with
  cryptographic proof that governance was enforced at every decision point.
- NIST AI 600-1 (MEASURE 2.5): Session-level aggregation of fidelity scores
  provides the ongoing monitoring data collection required for GenAI systems.

Usage:
    from telos_governance.session import GovernanceSessionContext

    # One-shot scoring with signed receipt
    with GovernanceSessionContext() as session:
        receipt = session.sign_result(result, action_text, decision_point)
        proof = session.generate_proof()

    # Multi-turn benchmark with session proof chain
    with GovernanceSessionContext() as session:
        for scenario in scenarios:
            result = engine.score_action(scenario.request)
            receipt = session.sign_result(result, scenario.request, "pre_action")
        proof = session.generate_proof()  # Chain of all receipts
"""

import secrets
import time
from typing import Any, Dict, List, Optional

from telos_governance.receipt_signer import (
    ReceiptSigner,
    GovernanceReceipt,
)


class GovernanceSessionContext:
    """Composable governance session with TKeys + Ed25519 signing.

    Manages the lifecycle of a governance session:
    1. Session creation (Ed25519 key gen + optional TKeys init)
    2. Per-decision receipt signing (+ optional Intelligence Layer telemetry)
    3. Session proof generation
    4. Cleanup and key destruction

    Can be used as a context manager for automatic cleanup.

    Args:
        session_id: Unique session identifier. Auto-generated if not provided.
        ed25519_private_key: Optional 32-byte Ed25519 private key to load.
            If not provided, a new key pair is generated per session.
        enable_tkeys: If True, initialize TKeys session for HMAC co-signing.
            Requires telos_privacy to be importable. Default False.
        master_key: Optional master key for TKeys session derivation.
        intelligence_collector: Optional IntelligenceCollector for telemetry.
            When provided, governance decisions are automatically recorded.
        agent_id: Agent identifier passed to Intelligence Layer.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        ed25519_private_key: Optional[bytes] = None,
        enable_tkeys: bool = False,
        master_key: Optional[bytes] = None,
        intelligence_collector=None,
        agent_id: str = "",
    ):
        self.session_id = session_id or f"telos-{secrets.token_hex(8)}"
        self._receipts: List[GovernanceReceipt] = []
        self._tkeys_manager = None
        self._is_active = True
        self._intelligence = intelligence_collector

        # Initialize Ed25519 signer
        if ed25519_private_key:
            self._signer = ReceiptSigner.from_private_bytes(ed25519_private_key)
        else:
            self._signer = ReceiptSigner.generate()

        # Optionally initialize TKeys for HMAC co-signing
        if enable_tkeys:
            self._init_tkeys(master_key)

        # Start intelligence session if collector is active
        if self._intelligence and self._intelligence.is_collecting:
            self._intelligence.start_session(self.session_id, agent_id)

    def _init_tkeys(self, master_key: Optional[bytes] = None) -> None:
        """Initialize TKeys session manager for HMAC co-signing."""
        try:
            from telos_privacy.cryptography.telemetric_keys import (
                TelemetricSessionManager,
            )
            self._tkeys_manager = TelemetricSessionManager(
                self.session_id, master_key=master_key
            )
            # Feed the TKeys HMAC key to the receipt signer
            hmac_key = bytes(self._tkeys_manager.key_generator.state.current_key)
            self._signer.set_hmac_key(hmac_key)
        except ImportError:
            pass  # TKeys not available — Ed25519 only

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # -------------------------------------------------------------------------
    # Signing
    # -------------------------------------------------------------------------

    def sign_result(
        self,
        result,
        action_text: str,
        decision_point: str = "pre_action",
        tool_name: Optional[str] = None,
    ) -> GovernanceReceipt:
        """Sign an AgenticFidelityResult and produce a GovernanceReceipt.

        Creates a receipt from the result fields, signs it with Ed25519
        (and HMAC-SHA512 if TKeys is active), and appends to the session chain.

        Args:
            result: AgenticFidelityResult from the fidelity engine.
            action_text: The request/action that was scored.
            decision_point: Which governance gate produced this result.
            tool_name: Optional tool name if this was a tool selection.

        Returns:
            Signed GovernanceReceipt.
        """
        if not self._is_active:
            raise RuntimeError("Session has been closed")

        receipt = GovernanceReceipt(
            decision_point=decision_point,
            action_text=action_text,
            decision=result.decision.value if hasattr(result.decision, 'value') else str(result.decision),
            effective_fidelity=result.effective_fidelity,
            composite_fidelity=result.composite_fidelity,
            boundary_triggered=result.boundary_triggered,
            tool_name=tool_name or getattr(result, 'selected_tool', None),
            timestamp=time.time(),
            purpose_fidelity=result.purpose_fidelity,
            scope_fidelity=result.scope_fidelity,
            boundary_violation=result.boundary_violation,
            tool_fidelity=result.tool_fidelity,
            chain_continuity=result.chain_continuity,
        )

        # If TKeys active, rotate key and update HMAC key for this turn
        if self._tkeys_manager:
            telemetry = {
                "fidelity_score": result.effective_fidelity,
                "timestamp": receipt.timestamp,
                "turn_number": len(self._receipts),
            }
            self._tkeys_manager.key_generator.rotate_key(telemetry)
            hmac_key = bytes(self._tkeys_manager.key_generator.state.current_key)
            self._signer.set_hmac_key(hmac_key)

        signed = self._signer.sign_receipt(receipt)
        self._receipts.append(signed)

        # Record telemetry if Intelligence Layer is active
        if self._intelligence and self._intelligence.is_collecting:
            self._intelligence.record_decision(
                decision_point=decision_point,
                decision=result.decision.value if hasattr(result.decision, 'value') else str(result.decision),
                effective_fidelity=result.effective_fidelity,
                composite_fidelity=result.composite_fidelity,
                purpose_fidelity=getattr(result, 'purpose_fidelity', None),
                scope_fidelity=getattr(result, 'scope_fidelity', None),
                boundary_violation=getattr(result, 'boundary_violation', None),
                tool_fidelity=getattr(result, 'tool_fidelity', None),
                chain_continuity=getattr(result, 'chain_continuity', None),
                boundary_triggered=getattr(result, 'boundary_triggered', None),
                contrastive_suppressed=getattr(result, 'contrastive_suppressed', None),
                similarity_gap=getattr(result, 'similarity_gap', None),
                human_required=getattr(result, 'human_required', None),
                chain_broken=getattr(result, 'chain_broken', None),
            )

        return signed

    def sign_event(self, event) -> GovernanceReceipt:
        """Sign a GovernanceEvent directly.

        Args:
            event: GovernanceEvent from governance_protocol.py.

        Returns:
            Signed GovernanceReceipt.
        """
        if not self._is_active:
            raise RuntimeError("Session has been closed")

        signed = self._signer.sign_event(event)
        self._receipts.append(signed)
        return signed

    # -------------------------------------------------------------------------
    # Session proof
    # -------------------------------------------------------------------------

    def generate_proof(self) -> Dict[str, Any]:
        """Generate a session proof document.

        Summarizes the entire session: all receipts, the Ed25519 public
        key for verification, and optional TKeys session fingerprint.

        Returns:
            Session proof dict suitable for audit and IP documentation.
        """
        proof = {
            "session_id": self.session_id,
            "proof_generated_at": time.time(),
            "total_receipts": len(self._receipts),
            "ed25519_public_key": self._signer.public_key_bytes().hex(),

            "receipt_chain": [r.to_dict() for r in self._receipts],

            "verification": {
                "method": "Ed25519 + HMAC-SHA512 co-signatures",
                "ed25519_verifiable": True,
                "hmac_verifiable": self._tkeys_manager is not None,
                "standards": [
                    "Ed25519 (RFC 8032, NIST FIPS 186-5)",
                    "HMAC-SHA512 (FIPS 198-1, RFC 2104)",
                ],
            },
        }

        if self._tkeys_manager:
            tkeys_proof = self._tkeys_manager.generate_session_proof()
            proof["tkeys_session_proof"] = tkeys_proof

        return proof

    # -------------------------------------------------------------------------
    # Accessors
    # -------------------------------------------------------------------------

    @property
    def receipt_count(self) -> int:
        return len(self._receipts)

    @property
    def receipts(self) -> List[GovernanceReceipt]:
        return list(self._receipts)

    @property
    def public_key_hex(self) -> str:
        return self._signer.public_key_bytes().hex()

    @property
    def has_tkeys(self) -> bool:
        return self._tkeys_manager is not None

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def close(self) -> None:
        """Close the session and destroy key material."""
        if not self._is_active:
            return

        # End intelligence session (persists telemetry)
        if self._intelligence and self._intelligence.is_collecting:
            self._intelligence.end_session()

        if self._tkeys_manager:
            self._tkeys_manager.destroy()
            self._tkeys_manager = None

        self._is_active = False

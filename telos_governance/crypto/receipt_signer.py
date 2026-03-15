"""
Receipt Signer: Ed25519 + HMAC-SHA512 co-signatures for governance receipts.

Every governance decision (GovernanceEvent) can be signed with two independent
signatures to create a verifiable receipt:

1. **Ed25519 (persistent)** -- Proves which TELOS deployment produced this decision.
   The Ed25519 private key is per-deployment (generated once, stored securely).
   Third parties can verify receipts using only the public key.

2. **HMAC-SHA512 (session-bound)** -- Proves this receipt was generated during
   a specific TKeys session with a specific telemetry history. Cannot be
   verified by third parties (requires the session key), but provides stronger
   binding to the governance session than Ed25519 alone.

Together they satisfy:
- EU AI Act Article 72: Auditable governance decisions with cryptographic integrity
- SAAI auditability: Unforgeable proof of governance at each decision point
- IP protection: Receipts prove the TELOS engine made the decision, not a mock
- NIST AI 600-1 (GV 1.4): Cryptographic governance receipts as immutable audit
  artifacts satisfying GenAI governance documentation requirements
- NIST AI RMF (MANAGE 4.1): Post-deployment monitoring with unforgeable decision
  records that enable continuous oversight per the AI Risk Management Framework
- FedRAMP CA-7 (Continuous Monitoring): Signed governance events provide the
  cryptographic evidence stream for continuous monitoring compliance
- OWASP LLM Top 10 (LLM08): Receipt chain proves every agent action was governed --
  no action bypasses measurement, preventing excessive agency through auditability

Design:
- Ed25519 keys are 32 bytes (NIST FIPS 186-5, RFC 8032)
- Signatures are 64 bytes (deterministic, no nonce needed)
- Key serialization: Raw bytes (32B private, 32B public) or PEM
- Receipt format: JSON-serializable dict with hex-encoded signatures
- Canonical serialization: sorted JSON with separators=(',', ':')

Usage:
    from telos_governance.receipt_signer import ReceiptSigner

    # Generate a new deployment key pair
    signer = ReceiptSigner.generate()

    # Sign a governance event
    receipt = signer.sign_event(governance_event)

    # Verify with public key only
    ReceiptSigner.verify_receipt(receipt, public_key_bytes)

    # Export public key for third-party verifiers
    pub_bytes = signer.public_key_bytes()

    # Persist private key (encrypted at rest via crypto_layer)
    priv_bytes = signer.private_key_bytes()
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


class ReceiptSigningError(Exception):
    """Raised when receipt signing or verification fails."""
    pass


@dataclass
class GovernanceReceipt:
    """A signed governance receipt.

    Contains the governance decision payload and one or both signatures.
    JSON-serializable for storage and transmission.
    """
    # Governance decision data
    decision_point: str
    action_text: str
    decision: str
    effective_fidelity: float
    composite_fidelity: float
    boundary_triggered: bool
    tool_name: Optional[str]
    timestamp: float

    # Dimension scores for auditability
    purpose_fidelity: float
    scope_fidelity: float
    boundary_violation: float
    tool_fidelity: float
    chain_continuity: float

    # Signatures
    ed25519_signature: Optional[str] = None  # hex-encoded 64-byte signature
    hmac_signature: Optional[str] = None     # hex-encoded 64-byte HMAC-SHA512
    public_key: Optional[str] = None         # hex-encoded 32-byte Ed25519 public key

    # Canonical payload hash (for verification)
    payload_hash: Optional[str] = None       # SHA-256 of canonical payload

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GovernanceReceipt":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class ReceiptSigner:
    """Ed25519 + optional HMAC-SHA512 receipt signer.

    The Ed25519 key is persistent per deployment. The HMAC key is
    session-bound (from TKeys) and optional.

    Args:
        private_key: Ed25519 private key for signing.
        hmac_key: Optional session-bound HMAC-SHA512 key (from TKeys).
    """

    def __init__(
        self,
        private_key: Ed25519PrivateKey,
        hmac_key: Optional[bytes] = None,
    ):
        self._private_key = private_key
        self._public_key = private_key.public_key()
        self._hmac_key = hmac_key

    @classmethod
    def generate(cls, hmac_key: Optional[bytes] = None) -> "ReceiptSigner":
        """Generate a new Ed25519 key pair.

        Args:
            hmac_key: Optional session HMAC key from TKeys.

        Returns:
            ReceiptSigner with fresh Ed25519 key pair.
        """
        private_key = Ed25519PrivateKey.generate()
        return cls(private_key, hmac_key=hmac_key)

    @classmethod
    def from_private_bytes(
        cls,
        private_bytes: bytes,
        hmac_key: Optional[bytes] = None,
    ) -> "ReceiptSigner":
        """Load signer from raw 32-byte Ed25519 private key.

        Args:
            private_bytes: 32-byte raw Ed25519 private key.
            hmac_key: Optional session HMAC key from TKeys.

        Returns:
            ReceiptSigner with loaded key pair.
        """
        private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
        return cls(private_key, hmac_key=hmac_key)

    def public_key_bytes(self) -> bytes:
        """Export the 32-byte raw Ed25519 public key."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def private_key_bytes(self) -> bytes:
        """Export the 32-byte raw Ed25519 private key.

        WARNING: Handle with care. Store encrypted (via crypto_layer).
        """
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )

    def set_hmac_key(self, hmac_key: bytes) -> None:
        """Set or update the session HMAC key (e.g., after TKeys rotation)."""
        self._hmac_key = hmac_key

    # -------------------------------------------------------------------------
    # Signing
    # -------------------------------------------------------------------------

    def sign_event(self, event) -> GovernanceReceipt:
        """Sign a GovernanceEvent and produce a GovernanceReceipt.

        Args:
            event: A GovernanceEvent from governance_protocol.py.

        Returns:
            GovernanceReceipt with Ed25519 signature (+ HMAC if key set).

        Raises:
            ReceiptSigningError: If signing fails.
        """
        try:
            receipt = GovernanceReceipt(
                decision_point=event.decision_point.value if hasattr(event.decision_point, 'value') else str(event.decision_point),
                action_text=event.action_text,
                decision=event.result.decision.value if event.result else "unknown",
                effective_fidelity=event.result.effective_fidelity if event.result else 0.0,
                composite_fidelity=event.result.composite_fidelity if event.result else 0.0,
                boundary_triggered=event.result.boundary_triggered if event.result else False,
                tool_name=event.tool_name,
                timestamp=event.timestamp.timestamp() if hasattr(event.timestamp, 'timestamp') else time.time(),
                purpose_fidelity=event.result.purpose_fidelity if event.result else 0.0,
                scope_fidelity=event.result.scope_fidelity if event.result else 0.0,
                boundary_violation=event.result.boundary_violation if event.result else 0.0,
                tool_fidelity=event.result.tool_fidelity if event.result else 0.0,
                chain_continuity=event.result.chain_continuity if event.result else 0.0,
            )
            return self.sign_receipt(receipt)
        except Exception as e:
            raise ReceiptSigningError(f"Failed to sign event: {e}") from e

    def sign_receipt(self, receipt: GovernanceReceipt) -> GovernanceReceipt:
        """Sign a GovernanceReceipt with Ed25519 (+ HMAC if key set).

        Computes canonical payload, hashes it, then signs. Modifies
        and returns the same receipt object with signatures populated.

        Args:
            receipt: Receipt to sign (signatures fields will be populated).

        Returns:
            The same receipt with ed25519_signature, hmac_signature, and
            payload_hash populated.
        """
        canonical = self._canonicalize(receipt)
        payload_hash = hashlib.sha256(canonical).digest()

        # Ed25519 signature (signs the SHA-256 hash of canonical payload)
        ed25519_sig = self._private_key.sign(payload_hash)

        receipt.payload_hash = payload_hash.hex()
        receipt.ed25519_signature = ed25519_sig.hex()
        receipt.public_key = self.public_key_bytes().hex()

        # HMAC-SHA512 signature (optional, session-bound)
        if self._hmac_key:
            hmac_sig = hmac.new(self._hmac_key, canonical, hashlib.sha512).digest()
            receipt.hmac_signature = hmac_sig.hex()

        return receipt

    def sign_payload(self, payload: bytes) -> bytes:
        """Sign arbitrary bytes with Ed25519.

        Args:
            payload: Raw bytes to sign.

        Returns:
            64-byte Ed25519 signature.
        """
        return self._private_key.sign(payload)

    # -------------------------------------------------------------------------
    # Verification (static -- only needs public key)
    # -------------------------------------------------------------------------

    @staticmethod
    def verify_receipt(
        receipt: GovernanceReceipt,
        public_key_bytes: bytes,
    ) -> bool:
        """Verify a receipt's Ed25519 signature using the public key.

        This is the third-party verification path -- only the public key
        is needed, not the private key or HMAC session key.

        Args:
            receipt: The receipt to verify.
            public_key_bytes: 32-byte raw Ed25519 public key.

        Returns:
            True if the Ed25519 signature is valid.

        Raises:
            ReceiptSigningError: If verification fails due to invalid
                signature, tampered payload, or wrong public key.
        """
        if not receipt.ed25519_signature or not receipt.payload_hash:
            raise ReceiptSigningError("Receipt has no Ed25519 signature")

        try:
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)

            # Recompute canonical hash and verify it matches
            canonical = ReceiptSigner._canonicalize(receipt)
            expected_hash = hashlib.sha256(canonical).digest()

            if expected_hash.hex() != receipt.payload_hash:
                raise ReceiptSigningError("Payload hash mismatch -- receipt data was tampered")

            # Verify Ed25519 signature over the payload hash
            signature = bytes.fromhex(receipt.ed25519_signature)
            public_key.verify(signature, expected_hash)
            return True

        except InvalidSignature:
            raise ReceiptSigningError(
                "Ed25519 signature verification failed -- wrong key or tampered signature"
            )
        except ReceiptSigningError:
            raise
        except Exception as e:
            raise ReceiptSigningError(f"Verification error: {e}") from e

    @staticmethod
    def verify_hmac(
        receipt: GovernanceReceipt,
        hmac_key: bytes,
    ) -> bool:
        """Verify a receipt's HMAC-SHA512 signature.

        This is the session verification path -- requires the TKeys
        session key from the signing session.

        Args:
            receipt: The receipt to verify.
            hmac_key: The HMAC-SHA512 key from the TKeys session.

        Returns:
            True if the HMAC signature is valid.

        Raises:
            ReceiptSigningError: If HMAC verification fails.
        """
        if not receipt.hmac_signature:
            raise ReceiptSigningError("Receipt has no HMAC signature")

        canonical = ReceiptSigner._canonicalize(receipt)
        expected = hmac.new(hmac_key, canonical, hashlib.sha512).digest()
        actual = bytes.fromhex(receipt.hmac_signature)

        if not hmac.compare_digest(expected, actual):
            raise ReceiptSigningError("HMAC verification failed -- wrong session key or tampered")

        return True

    # -------------------------------------------------------------------------
    # Canonical serialization
    # -------------------------------------------------------------------------

    @staticmethod
    def _canonicalize(receipt: GovernanceReceipt) -> bytes:
        """Create deterministic canonical representation of receipt payload.

        Only includes the governance decision data (not signatures),
        so the canonical form is stable across signing operations.

        Returns:
            UTF-8 bytes of sorted JSON with compact separators.
        """
        payload = {
            "decision_point": receipt.decision_point,
            "action_text": receipt.action_text,
            "decision": receipt.decision,
            "effective_fidelity": receipt.effective_fidelity,
            "composite_fidelity": receipt.composite_fidelity,
            "boundary_triggered": receipt.boundary_triggered,
            "tool_name": receipt.tool_name,
            "timestamp": receipt.timestamp,
            "purpose_fidelity": receipt.purpose_fidelity,
            "scope_fidelity": receipt.scope_fidelity,
            "boundary_violation": receipt.boundary_violation,
            "tool_fidelity": receipt.tool_fidelity,
            "chain_continuity": receipt.chain_continuity,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

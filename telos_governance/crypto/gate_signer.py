"""
Gate Signer: Ed25519 cryptographic gate transitions for TELOS governance.

The TKeys Ed25519 gate is a cryptographically signed governance event that
controls whether the TELOS governance daemon operates in enforce, observe,
or inert mode. Jeffrey's Ed25519 signature mathematically bars the agent
from operating when the gate is closed.

Gate states:
    open    -- Governance engine active, verdicts enforced normally
    closed  -- Gate sealed by Ed25519 signature; mode determines behavior

Gate modes (when closed):
    enforce -- Agent is INERT (all tool calls blocked)
    observe -- Agent scores normally but forces allowed=True (shadow scoring)

Design:
    - Reuses Ed25519 signing pattern from receipt_signer.py
    - Canonical JSON serialization (sorted keys, compact separators)
    - Ed25519 signs raw canonical bytes (no intermediate hash)
    - TTL support (ttl_hours=0 means indefinite)
    - Gate records persisted to ~/.telos/gate as JSON

Regulatory traceability:
    - EU AI Act Art. 14: Human authority to disable AI system
    - NIST AI RMF MANAGE 2.4: Mechanisms to supersede/disengage/deactivate
    - Ostrom DP3: Collective-choice arrangements (authority to modify rules)
    - Berkeley CLTC Profile: Degrees of agency, kill switch compliance

Usage:
    from telos_governance.gate_signer import GateSigner, GateRecord

    signer = GateSigner(private_key_path=Path("~/.telos/keys/gate.key"))
    record = signer.sign_transition("closed", "enforce", ttl_hours=0)
    assert GateSigner.verify(record, signer.public_key_bytes)
"""

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


class GateSigningError(Exception):
    """Raised when gate signing or verification fails."""
    pass


def _normalize_timestamp(ts: Union[str, float, int]) -> float:
    """Normalize a timestamp to Unix epoch float.

    S writes ISO 8601 strings (e.g., "2026-02-27T18:10:03Z").
    T uses Unix epoch floats. This bridge handles both.
    """
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        try:
            # ISO 8601 with Z suffix
            ts_clean = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_clean)
            return dt.timestamp()
        except (ValueError, TypeError):
            pass
        try:
            return float(ts)
        except (ValueError, TypeError):
            pass
    raise GateSigningError(f"Cannot parse timestamp: {ts!r}")


@dataclass
class GateRecord:
    """A cryptographically signed gate transition record.

    Attributes:
        state: Gate state ("open" or "closed").
        mode: Gate mode ("enforce" or "observe").
        actor: Identity of the signer (fingerprint or username).
        timestamp: Timestamp as originally written (float epoch or ISO 8601 string).
            Stored as-is to preserve canonical form for signature verification.
        ttl_hours: Time-to-live in hours (0 = indefinite).
        signature: Hex-encoded 64-byte Ed25519 signature.
        public_key: Hex-encoded 32-byte Ed25519 public key.
    """
    state: str
    mode: str
    actor: str
    timestamp: Union[float, str]  # Raw value -- float epoch or ISO 8601 string
    ttl_hours: int
    signature: str
    public_key: str

    @property
    def timestamp_epoch(self) -> float:
        """Timestamp as Unix epoch float (normalized for TTL math)."""
        return _normalize_timestamp(self.timestamp)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON persistence."""
        return {
            "state": self.state,
            "mode": self.mode,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "ttl_hours": self.ttl_hours,
            "signature": self.signature,
            "public_key": self.public_key,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GateRecord":
        """Deserialize from dict.

        Accepts both "public_key" and "tkey_pubkey" field names for
        cross-component compatibility (S writes tkey_pubkey, T uses public_key).
        Preserves raw timestamp value for canonical form reconstruction.
        """
        return cls(
            state=d["state"],
            mode=d["mode"],
            actor=d["actor"],
            timestamp=d["timestamp"],  # Raw -- preserve for canonical form
            ttl_hours=d["ttl_hours"],
            signature=d["signature"],
            public_key=d.get("public_key") or d.get("tkey_pubkey", ""),
        )


class GateSigner:
    """Ed25519 gate transition signer.

    Signs gate state transitions (open/closed) with Ed25519. The signature
    covers the canonical JSON form of the gate fields, ensuring tamper
    evidence and non-repudiation.

    Args:
        private_key: Ed25519 private key for signing.
    """

    def __init__(self, private_key: Ed25519PrivateKey):
        self._private_key = private_key
        self._public_key = private_key.public_key()

    @classmethod
    def from_private_key_path(cls, path: Path) -> "GateSigner":
        """Load signer from a PEM-encoded Ed25519 private key file.

        Args:
            path: Path to PEM file.

        Returns:
            GateSigner with loaded key.

        Raises:
            GateSigningError: If the file cannot be read or parsed.
        """
        try:
            data = Path(path).expanduser().read_bytes()
            private_key = serialization.load_pem_private_key(data, password=None)
            if not isinstance(private_key, Ed25519PrivateKey):
                raise GateSigningError(f"Key at {path} is not Ed25519")
            return cls(private_key)
        except GateSigningError:
            raise
        except Exception as e:
            raise GateSigningError(f"Failed to load private key from {path}: {e}") from e

    @classmethod
    def from_private_bytes(cls, raw: bytes) -> "GateSigner":
        """Load signer from 32-byte raw Ed25519 private key.

        Args:
            raw: 32-byte raw private key.

        Returns:
            GateSigner with loaded key.
        """
        try:
            return cls(Ed25519PrivateKey.from_private_bytes(raw))
        except Exception as e:
            raise GateSigningError(f"Invalid private key bytes: {e}") from e

    @classmethod
    def generate(cls) -> "GateSigner":
        """Generate a new Ed25519 key pair for gate signing.

        Returns:
            GateSigner with fresh key pair.
        """
        return cls(Ed25519PrivateKey.generate())

    @property
    def public_key_bytes(self) -> bytes:
        """32-byte raw Ed25519 public key."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    @property
    def fingerprint(self) -> str:
        """SHA-256 fingerprint of the public key (hex-encoded)."""
        return hashlib.sha256(self.public_key_bytes).hexdigest()

    @staticmethod
    def canonical_form(
        state: str,
        mode: str,
        actor: str,
        timestamp: Union[float, str],
        ttl_hours: int,
    ) -> bytes:
        """Create deterministic canonical representation for signing.

        Args:
            state: Gate state ("open" or "closed").
            mode: Gate mode ("enforce" or "observe").
            actor: Signer identity (fingerprint or username).
            timestamp: Timestamp (float epoch or ISO 8601 string -- passed through as-is).
            ttl_hours: Time-to-live in hours.

        Returns:
            UTF-8 bytes of sorted JSON with compact separators.
        """
        payload = {
            "actor": actor,
            "mode": mode,
            "state": state,
            "timestamp": timestamp,
            "ttl_hours": ttl_hours,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign_transition(
        self,
        state: str,
        mode: str,
        ttl_hours: int = 0,
    ) -> GateRecord:
        """Sign a gate state transition.

        Args:
            state: Gate state ("open" or "closed").
            mode: Gate mode ("enforce" or "observe").
            ttl_hours: Time-to-live in hours (0 = indefinite).

        Returns:
            GateRecord with Ed25519 signature.

        Raises:
            GateSigningError: If signing fails.
        """
        if state not in ("open", "closed"):
            raise GateSigningError(f"Invalid gate state: {state!r} (must be 'open' or 'closed')")
        if mode not in ("enforce", "observe"):
            raise GateSigningError(f"Invalid gate mode: {mode!r} (must be 'enforce' or 'observe')")

        actor = self.fingerprint
        timestamp = time.time()

        canonical = self.canonical_form(state, mode, actor, timestamp, ttl_hours)

        try:
            signature = self._private_key.sign(canonical)
        except Exception as e:
            raise GateSigningError(f"Ed25519 signing failed: {e}") from e

        return GateRecord(
            state=state,
            mode=mode,
            actor=actor,
            timestamp=timestamp,
            ttl_hours=ttl_hours,
            signature=signature.hex(),
            public_key=self.public_key_bytes.hex(),
        )

    @staticmethod
    def verify(record: GateRecord, public_key_bytes: bytes) -> bool:
        """Verify a GateRecord's Ed25519 signature.

        Args:
            record: The gate record to verify.
            public_key_bytes: 32-byte raw Ed25519 public key.

        Returns:
            True if the signature is valid.

        Raises:
            GateSigningError: If verification fails.
        """
        if not record.signature:
            raise GateSigningError("GateRecord has no signature")

        try:
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)

            canonical = GateSigner.canonical_form(
                record.state, record.mode, record.actor,
                record.timestamp, record.ttl_hours,
            )

            signature = bytes.fromhex(record.signature)
            public_key.verify(signature, canonical)
            return True

        except InvalidSignature:
            raise GateSigningError(
                "Ed25519 signature verification failed -- wrong key or tampered record"
            )
        except GateSigningError:
            raise
        except Exception as e:
            raise GateSigningError(f"Verification error: {e}") from e

    @staticmethod
    def is_expired(record: GateRecord) -> bool:
        """Check if a gate record's TTL has elapsed.

        Args:
            record: The gate record to check.

        Returns:
            True if the TTL has expired. False if ttl_hours=0 (indefinite).
        """
        if record.ttl_hours <= 0:
            return False
        expiry = record.timestamp_epoch + (record.ttl_hours * 3600)
        return time.time() > expiry

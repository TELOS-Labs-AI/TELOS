"""
License Token System: Offline Ed25519-signed authorization tokens.

A license token is the authorization artifact that proves a customer is
entitled to activate and use a .telos bundle. Tokens are:

- **Offline**: No server, no phone-home, no internet required
- **Signed**: Ed25519 signature by TELOS Labs proves authenticity
- **Bound**: Tied to a specific agent_id and deployment key
- **Temporal**: Optional expiration date for subscription enforcement
- **Air-gap compatible**: Token + license key can be delivered on USB

Token structure (JSON + detached signature):
    {
        "token_id": "uuid4",
        "agent_id": "property-intel-v2",
        "issued_at": "2026-02-14T12:00:00+00:00",
        "expires_at": "2027-02-14T12:00:00+00:00",   (null = perpetual)
        "deployment_fingerprint": "d4e5f6...",
        "license_key_hash": "7890ab...",                (SHA-256 of license key)
        "capabilities": ["governance", "intelligence_layer"],
        "telos_version_min": "1.5.0",
        "issuer": "TELOS Labs"
    }

Wire format (.telos-license file):
    [4 bytes]   magic: b"TLIC"
    [2 bytes]   version: uint16 big-endian (currently 1)
    [4 bytes]   payload_len: uint32 big-endian
    [N bytes]   payload_json: canonical JSON (sorted, compact)
    [64 bytes]  signature: Ed25519 over payload_json

Compliance:
- NIST AI RMF (GOVERN 1.1): License tokens enforce organizational governance
  policies across deployments -- each token scopes an agent's authorized
  capabilities, expiration, and deployment identity.
- NIST AI 600-1 (GV 1.4): Temporal tokens with capability restrictions implement
  deployment-level governance as required for GenAI systems. The expires_at field
  enforces periodic re-authorization, preventing indefinite autonomous operation.
- IEEE P7000 (Model Process for Addressing Ethical Concerns): License expiration
  and capability scoping embody responsible deployment lifecycle management --
  the token IS the authorization contract between vendor and deployer.
- OWASP LLM Top 10 (LLM05 -- Supply Chain Vulnerabilities): Ed25519-signed
  tokens prevent forged authorization. The license_key_hash binding ensures
  tokens cannot be reused with different license keys.

Relationship to bundle system:
- License key (32 bytes, delivered separately) decrypts the .telos bundle
- License token (this file) authorizes the deployment
- Token's license_key_hash binds token to key without containing the key
- Token's agent_id must match bundle's agent_id
- Token's deployment_fingerprint must match bundle's deployment_fingerprint

Usage:
    from telos_governance.licensing import LicenseTokenBuilder, LicenseToken

    # Build a token (TELOS Labs side)
    builder = LicenseTokenBuilder(labs_key=labs_kp)
    token_bytes = builder.build(
        agent_id="property-intel-v2",
        deployment_fingerprint="d4e5f6...",
        license_key=license_key_bytes,
        capabilities=["governance"],
        expires_in_days=365,
    )

    # Verify a token (customer side)
    token = LicenseToken.from_bytes(token_bytes)
    token.verify(labs_public_key)       # check signature
    token.validate(license_key=key)     # check expiry + key hash
"""

import hashlib
import json
import struct
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Union

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from telos_governance.signing import SigningKeyPair, SigningError


# Wire format constants
LICENSE_MAGIC = b"TLIC"
LICENSE_VERSION = 1
_MAGIC_LEN = 4
_VERSION_LEN = 2
_PAYLOAD_LEN_SIZE = 4
_SIGNATURE_LEN = 64
_HEADER_PREFIX_LEN = _MAGIC_LEN + _VERSION_LEN + _PAYLOAD_LEN_SIZE  # 10 bytes
MAX_TOKEN_SIZE = 64 * 1024  # 64 KB -- license tokens should be small


class LicenseError(Exception):
    """Raised when license token operations fail."""
    pass


@dataclass
class LicensePayload:
    """License token payload -- the signed data.

    All fields are cleartext and inspectable. The license key itself
    is NOT included -- only its SHA-256 hash for binding verification.
    """
    token_id: str = ""
    agent_id: str = ""
    issued_at: str = ""
    expires_at: str = ""  # empty string = perpetual
    deployment_fingerprint: str = ""
    license_key_hash: str = ""  # SHA-256 of the 32-byte license key
    capabilities: List[str] = field(default_factory=list)
    telos_version_min: str = ""
    issuer: str = "TELOS Labs"
    # Review #14 fields (Schaake P0 + Benioff)
    bundle_id: str = ""           # bundle_id this token authorizes (Art. 72 audit chain)
    licensee_id: str = ""         # Individual licensee identifier
    licensee_org: str = ""        # Organization holding the license
    risk_classification: str = "" # high_risk, limited_risk, minimal_risk, unclassified

    def to_json(self) -> bytes:
        """Serialize to canonical JSON bytes (sorted keys, compact)."""
        d = asdict(self)
        return json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_json(cls, data: bytes) -> "LicensePayload":
        """Deserialize from JSON bytes."""
        try:
            d = json.loads(data.decode("utf-8"))
            return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        except Exception as e:
            raise LicenseError(f"Invalid license payload JSON: {e}") from e


class LicenseTokenBuilder:
    """Builds signed license tokens.

    This is the TELOS Labs build-side tool. Customers never use this directly.

    Args:
        labs_key: TELOS Labs Ed25519 signing key pair.
    """

    def __init__(self, labs_key: SigningKeyPair):
        self._labs_key = labs_key

    def build(
        self,
        agent_id: str,
        deployment_fingerprint: str,
        license_key: bytes,
        capabilities: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None,
        telos_version_min: str = "",
        bundle_id: str = "",
        licensee_id: str = "",
        licensee_org: str = "",
        risk_classification: str = "",
    ) -> bytes:
        """Build a signed license token.

        Args:
            agent_id: Agent identifier this license authorizes.
            deployment_fingerprint: SHA-256 fingerprint of the deployment public key.
            license_key: The 32-byte license key material (hashed, not stored).
            capabilities: List of authorized capabilities (e.g., ["governance"]).
            expires_in_days: Days until expiration (None = perpetual license).
            telos_version_min: Minimum TELOS version required.

        Returns:
            Complete .telos-license token as bytes.

        Raises:
            LicenseError: If token building fails.
        """
        try:
            now = datetime.now(timezone.utc)
            expires_at = ""
            if expires_in_days is not None:
                expires_at = (now + timedelta(days=expires_in_days)).isoformat()

            payload = LicensePayload(
                token_id=str(uuid.uuid4()),
                agent_id=agent_id,
                issued_at=now.isoformat(),
                expires_at=expires_at,
                deployment_fingerprint=deployment_fingerprint,
                license_key_hash=hashlib.sha256(license_key).hexdigest(),
                capabilities=capabilities or ["governance"],
                telos_version_min=telos_version_min,
                issuer="TELOS Labs",
                bundle_id=bundle_id,
                licensee_id=licensee_id,
                licensee_org=licensee_org,
                risk_classification=risk_classification,
            )
            payload_json = payload.to_json()

            # Sign the payload
            signature = self._labs_key.sign(payload_json)

            # Assemble token
            token = bytearray()
            token.extend(LICENSE_MAGIC)
            token.extend(struct.pack(">H", LICENSE_VERSION))
            token.extend(struct.pack(">I", len(payload_json)))
            token.extend(payload_json)
            token.extend(signature)

            return bytes(token)

        except SigningError as e:
            raise LicenseError(f"License token signing failed: {e}") from e
        except Exception as e:
            raise LicenseError(f"Unexpected license token build error: {e}") from e


class LicenseToken:
    """Parsed and verifiable license token.

    This is the customer-side tool. Parses the token, verifies the signature,
    and validates expiry and license key binding.

    Args:
        data: Raw .telos-license token bytes.
    """

    def __init__(self, data: bytes):
        self._data = data
        self._payload: Optional[LicensePayload] = None
        self._payload_json: Optional[bytes] = None
        self._signature: Optional[bytes] = None
        self._warnings: List[str] = []
        self._parse()

    def _parse(self) -> None:
        """Parse the token structure."""
        if len(self._data) < _HEADER_PREFIX_LEN:
            raise LicenseError("License token too short")

        if len(self._data) > MAX_TOKEN_SIZE:
            raise LicenseError(
                f"License token too large: {len(self._data)} bytes "
                f"(max {MAX_TOKEN_SIZE})"
            )

        # Magic
        magic = self._data[:_MAGIC_LEN]
        if magic != LICENSE_MAGIC:
            raise LicenseError(
                f"Invalid license token magic: {magic!r} (expected {LICENSE_MAGIC!r})"
            )

        # Version
        version = struct.unpack(">H", self._data[_MAGIC_LEN:_MAGIC_LEN + _VERSION_LEN])[0]
        if version != LICENSE_VERSION:
            raise LicenseError(
                f"Unsupported license token version: {version} (expected {LICENSE_VERSION})"
            )

        # Payload length
        payload_len = struct.unpack(
            ">I",
            self._data[_MAGIC_LEN + _VERSION_LEN:_HEADER_PREFIX_LEN]
        )[0]

        # Check we have enough data
        expected_len = _HEADER_PREFIX_LEN + payload_len + _SIGNATURE_LEN
        if len(self._data) < expected_len:
            raise LicenseError(
                f"License token truncated: {len(self._data)} bytes, "
                f"need {expected_len}"
            )

        # Extract sections
        offset = _HEADER_PREFIX_LEN
        self._payload_json = self._data[offset:offset + payload_len]
        offset += payload_len

        self._signature = self._data[offset:offset + _SIGNATURE_LEN]

        # Parse payload
        self._payload = LicensePayload.from_json(self._payload_json)

    @property
    def payload(self) -> LicensePayload:
        """The license token payload."""
        return self._payload

    @property
    def token_id(self) -> str:
        return self._payload.token_id

    @property
    def agent_id(self) -> str:
        return self._payload.agent_id

    @property
    def expires_at(self) -> str:
        return self._payload.expires_at

    @property
    def capabilities(self) -> List[str]:
        return self._payload.capabilities

    @property
    def is_perpetual(self) -> bool:
        """True if this license has no expiration."""
        return not self._payload.expires_at

    @property
    def warnings(self) -> List[str]:
        """Warnings from the last validate() call (e.g., grace period active)."""
        return self._warnings

    def verify(
        self,
        labs_public_key: Union[Ed25519PublicKey, bytes],
    ) -> bool:
        """Verify the TELOS Labs signature on this token.

        Args:
            labs_public_key: TELOS Labs Ed25519 public key (object or 32 bytes).

        Returns:
            True if the signature is valid.

        Raises:
            LicenseError: If the signature is invalid.
        """
        try:
            return SigningKeyPair.verify(
                self._payload_json,
                self._signature,
                labs_public_key,
            )
        except SigningError as e:
            raise LicenseError(f"License signature verification failed: {e}") from e

    def validate(
        self,
        license_key: Optional[bytes] = None,
        agent_id: Optional[str] = None,
        deployment_fingerprint: Optional[str] = None,
        now: Optional[datetime] = None,
        grace_period_days: int = 0,
    ) -> bool:
        """Validate the license token constraints.

        Checks expiry, license key hash binding, agent_id match, and
        deployment fingerprint match. Each check is only performed if
        the corresponding argument is provided.

        Args:
            license_key: License key material to verify against hash.
            agent_id: Expected agent_id (must match token's agent_id).
            deployment_fingerprint: Expected deployment key fingerprint.
            now: Current time for expiry check (defaults to UTC now).
            grace_period_days: Days after expiry during which token is still
                valid but returns a warning via the `warnings` attribute.
                Default 0 (no grace period). Benioff Review #14 recommendation.

        Returns:
            True if all provided checks pass.

        Raises:
            LicenseError: If any validation check fails (hard failure).
        """
        self._warnings = []  # Reset warnings on each validate call

        if now is None:
            now = datetime.now(timezone.utc)

        # Expiry check with grace period
        if self._payload.expires_at:
            expires = datetime.fromisoformat(self._payload.expires_at)
            if now >= expires:
                if grace_period_days > 0:
                    grace_end = expires + timedelta(days=grace_period_days)
                    if now < grace_end:
                        days_past = (now - expires).days
                        self._warnings.append(
                            f"License expired {days_past} day(s) ago -- "
                            f"in grace period ({grace_period_days} days). "
                            f"Renew before {grace_end.isoformat()}"
                        )
                    else:
                        raise LicenseError(
                            f"License expired at {self._payload.expires_at} "
                            f"(grace period of {grace_period_days} days also expired)"
                        )
                else:
                    raise LicenseError(
                        f"License expired at {self._payload.expires_at}"
                    )

        # License key hash binding
        if license_key is not None:
            expected_hash = hashlib.sha256(license_key).hexdigest()
            if expected_hash != self._payload.license_key_hash:
                raise LicenseError(
                    "License key does not match token -- wrong key file?"
                )

        # Agent ID match
        if agent_id is not None and agent_id != self._payload.agent_id:
            raise LicenseError(
                f"Agent ID mismatch: token authorizes '{self._payload.agent_id}', "
                f"but bundle has '{agent_id}'"
            )

        # Deployment fingerprint match
        if deployment_fingerprint is not None:
            if deployment_fingerprint != self._payload.deployment_fingerprint:
                raise LicenseError(
                    "Deployment key fingerprint mismatch -- "
                    "token was issued for a different deployment key"
                )

        return True

    @classmethod
    def from_bytes(cls, data: bytes) -> "LicenseToken":
        """Parse a license token from raw bytes."""
        return cls(data)

    @classmethod
    def from_file(cls, path: str) -> "LicenseToken":
        """Load a license token from a .telos-license file."""
        try:
            import os as _os
            _file_size = _os.path.getsize(path)
            if _file_size > MAX_TOKEN_SIZE:
                raise LicenseError(
                    f"License file too large: {_file_size} bytes "
                    f"(max {MAX_TOKEN_SIZE})"
                )
            with open(path, "rb") as f:
                return cls(f.read())
        except LicenseError:
            raise
        except Exception as e:
            raise LicenseError(f"Failed to read license file: {e}") from e

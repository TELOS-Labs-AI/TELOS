"""
.telos Bundle Format: Encrypted, signed distribution archive.

A .telos bundle is the product artifact -- the thing customers receive.
It contains governance configuration (PA, boundaries, tools, calibration)
in an encrypted, dual-signed single-file archive.

Bundle structure (binary):
    [4 bytes]   magic: b"TELO"
    [2 bytes]   version: uint16 big-endian (currently 1)
    [4 bytes]   manifest_len: uint32 big-endian
    [N bytes]   manifest_json: cleartext JSON (regulatory-inspectable)
    [64 bytes]  labs_signature: Ed25519 over signed_content
    [64 bytes]  deployment_signature: Ed25519 over signed_content
    [M bytes]   encrypted_payload: AES-256-GCM encrypted config data

    signed_content = manifest_json + encrypted_payload

Design rationale:
- Manifest is cleartext so regulators can inspect metadata without decryption
- Encrypted payload protects proprietary IP (boundary corpus, calibration)
- Dual signatures: TELOS Labs proves authenticity, deployment key proves authorization
- Single file for simple delivery (S3, email, USB)

Compliance:
- NIST AI 600-1 (MAP 2.2): Cleartext manifest enables regulatory inspection of
  AI system metadata without decryption -- regulators can verify agent_id, version,
  risk classification, and creation timestamp without access to proprietary IP.
- FedRAMP SI-7 (Software, Firmware, and Information Integrity): Binary format
  with authenticated encryption, dual Ed25519 signatures, and SHA-256 content
  hash provides multi-layer integrity verification for governance artifacts.
- OWASP LLM Top 10 (LLM05 -- Supply Chain Vulnerabilities): Dual-signed bundle
  format prevents delivery of tampered governance configurations. Both TELOS Labs
  and deployment signatures must verify before payload decryption proceeds.
- NIST AI RMF (GOVERN 1.1): The bundle format enforces governance policy through
  signed, versioned configuration artifacts -- governance is structural, embedded
  in the delivery mechanism itself.

Manifest (cleartext JSON):
    {
        "bundle_version": 1,
        "agent_id": "property-intel-v2",
        "created_at": "2026-02-14T12:00:00Z",
        "telos_version": "1.5.0",
        "labs_fingerprint": "a3b2c1...",      (SHA-256 of Labs public key)
        "deployment_fingerprint": "d4e5f6...", (SHA-256 of deployment public key)
        "content_hash": "7890ab...",           (SHA-256 of decrypted content)
        "description": "Property intelligence governance config"
    }

Usage:
    from telos_governance.bundle import BundleBuilder, BundleReader

    # Build a bundle (TELOS Labs side)
    builder = BundleBuilder(labs_key=labs_kp, deployment_key=deploy_kp)
    bundle_bytes = builder.build(
        config_data=config_yaml_bytes,
        license_key=license_key_bytes,
        agent_id="property-intel-v2",
        description="Property intelligence governance config",
    )

    # Read a bundle (customer side)
    reader = BundleReader(bundle_bytes)
    manifest = reader.manifest           # cleartext, always available
    reader.verify(labs_pub, deploy_pub)   # verify both signatures
    config = reader.decrypt(license_key)  # decrypt the payload
"""

import json
import hashlib
import struct
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from telos_governance.signing import SigningKeyPair, SigningError
from telos_governance.crypto_layer import ConfigEncryptor, ConfigEncryptionError


# Bundle format constants
BUNDLE_MAGIC = b"TELO"
BUNDLE_VERSION = 1
MAX_BUNDLE_SIZE = 50 * 1024 * 1024  # 50 MB -- reject bundles larger than this
_MAGIC_LEN = 4
_VERSION_LEN = 2
_MANIFEST_LEN_SIZE = 4
_SIGNATURE_LEN = 64
_HEADER_PREFIX_LEN = _MAGIC_LEN + _VERSION_LEN + _MANIFEST_LEN_SIZE  # 10 bytes


class BundleError(Exception):
    """Raised when bundle building, reading, or verification fails."""
    pass


@dataclass
class BundleManifest:
    """Cleartext bundle manifest -- visible without decryption.

    Contains metadata for regulatory inspection, license verification,
    and bundle identification. No proprietary content.
    """
    bundle_version: int = BUNDLE_VERSION
    agent_id: str = ""
    created_at: str = ""
    telos_version: str = ""
    labs_fingerprint: str = ""
    deployment_fingerprint: str = ""
    content_hash: str = ""
    description: str = ""
    # Regulatory compliance fields (Schaake Review #13/#14)
    bundle_id: str = ""               # Unique bundle identifier (UUID4)
    risk_classification: str = ""     # high_risk, limited_risk, minimal_risk, unclassified
    regulatory_jurisdiction: str = "" # e.g., "CO_SB24-205,NAIC,EU_AI_ACT"
    effective_from: str = ""          # ISO 8601 -- when this bundle takes effect
    expires_at: str = ""              # ISO 8601 -- when this bundle expires (empty = no expiry)
    supersedes: str = ""              # bundle_id of the bundle this one replaces
    boundary_ids: str = ""            # Comma-separated boundary identifiers
    # Data lineage fields (Gebru recommendations, Phase 2)
    embedding_model_version: str = "" # e.g., "all-MiniLM-L6-v2"
    corpus_version: str = ""          # format "L1.L2.L3" e.g., "61.106.48"
    constants_hash: str = ""          # SHA-256 of serialized threshold constants
    changelog: str = ""               # Human-readable change description (cleartext, inspectable pre-activation)

    def to_json(self) -> bytes:
        """Serialize to canonical JSON bytes (sorted keys, compact)."""
        return json.dumps(
            asdict(self), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    @classmethod
    def from_json(cls, data: bytes) -> "BundleManifest":
        """Deserialize from JSON bytes."""
        try:
            d = json.loads(data.decode("utf-8"))
            return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        except Exception as e:
            raise BundleError(f"Invalid manifest JSON: {e}") from e


class BundleBuilder:
    """Builds .telos bundle files.

    This is the TELOS Labs build-side tool. Customers never use this directly.

    Args:
        labs_key: TELOS Labs Ed25519 signing key pair.
        deployment_key: Customer-specific deployment key pair.
    """

    def __init__(
        self,
        labs_key: SigningKeyPair,
        deployment_key: SigningKeyPair,
    ):
        self._labs_key = labs_key
        self._deployment_key = deployment_key

    def build(
        self,
        config_data: bytes,
        license_key: bytes,
        agent_id: str = "",
        description: str = "",
        telos_version: str = "",
        agent_id_as_aad: bool = True,
        bundle_id: str = "",
        risk_classification: str = "",
        regulatory_jurisdiction: str = "",
        effective_from: str = "",
        expires_at: str = "",
        supersedes: str = "",
        boundary_ids: str = "",
    ) -> bytes:
        """Build a .telos bundle.

        Args:
            config_data: Raw configuration data (YAML, JSON, etc.) to encrypt.
            license_key: License key material for AES-256-GCM encryption (>= 16 bytes).
            agent_id: Agent identifier for the manifest.
            description: Human-readable description for the manifest.
            telos_version: TELOS version string for the manifest.
            agent_id_as_aad: If True, bind encrypted content to agent_id via AAD.
            bundle_id: Unique bundle identifier (UUID4). Auto-generated if empty.
            risk_classification: Risk level (high_risk, limited_risk, minimal_risk, unclassified).
            regulatory_jurisdiction: Comma-separated jurisdiction identifiers.
            effective_from: ISO 8601 timestamp when bundle takes effect.
            expires_at: ISO 8601 timestamp when bundle expires (empty = no expiry).
            supersedes: bundle_id of the bundle this one replaces.
            boundary_ids: Comma-separated boundary identifiers.

        Returns:
            Complete .telos bundle as bytes.

        Raises:
            BundleError: If bundle building fails.
        """
        try:
            import uuid

            # Encrypt the config data
            encryptor = ConfigEncryptor(license_key)
            aad = agent_id.encode("utf-8") if agent_id_as_aad and agent_id else None
            encrypted_payload = encryptor.encrypt(config_data, aad=aad)

            # Build manifest
            content_hash = hashlib.sha256(config_data).hexdigest()
            manifest = BundleManifest(
                bundle_version=BUNDLE_VERSION,
                agent_id=agent_id,
                created_at=datetime.now(timezone.utc).isoformat(),
                telos_version=telos_version,
                labs_fingerprint=self._labs_key.fingerprint,
                deployment_fingerprint=self._deployment_key.fingerprint,
                content_hash=content_hash,
                description=description,
                bundle_id=bundle_id or str(uuid.uuid4()),
                risk_classification=risk_classification,
                regulatory_jurisdiction=regulatory_jurisdiction,
                effective_from=effective_from,
                expires_at=expires_at,
                supersedes=supersedes,
                boundary_ids=boundary_ids,
            )
            manifest_json = manifest.to_json()

            # Signed content = manifest + encrypted payload
            signed_content = manifest_json + encrypted_payload

            # Dual signatures
            labs_sig = self._labs_key.sign(signed_content)
            deploy_sig = self._deployment_key.sign(signed_content)

            # Assemble bundle
            bundle = bytearray()
            bundle.extend(BUNDLE_MAGIC)
            bundle.extend(struct.pack(">H", BUNDLE_VERSION))
            bundle.extend(struct.pack(">I", len(manifest_json)))
            bundle.extend(manifest_json)
            bundle.extend(labs_sig)
            bundle.extend(deploy_sig)
            bundle.extend(encrypted_payload)

            return bytes(bundle)

        except (ConfigEncryptionError, SigningError) as e:
            raise BundleError(f"Bundle build failed: {e}") from e
        except Exception as e:
            raise BundleError(f"Unexpected bundle build error: {e}") from e


class BundleReader:
    """Reads and verifies .telos bundle files.

    This is the customer-side tool. Reads the bundle, provides access to
    the cleartext manifest, verifies signatures, and decrypts the payload.

    Args:
        data: Raw .telos bundle bytes.
    """

    def __init__(self, data: bytes):
        self._data = data
        self._manifest: Optional[BundleManifest] = None
        self._manifest_json: Optional[bytes] = None
        self._labs_signature: Optional[bytes] = None
        self._deploy_signature: Optional[bytes] = None
        self._encrypted_payload: Optional[bytes] = None
        self._parse()

    def _parse(self) -> None:
        """Parse the bundle structure."""
        if len(self._data) < _HEADER_PREFIX_LEN:
            raise BundleError("Bundle too short -- not a valid .telos file")

        if len(self._data) > MAX_BUNDLE_SIZE:
            raise BundleError(
                f"Bundle too large: {len(self._data)} bytes "
                f"(max {MAX_BUNDLE_SIZE})"
            )

        # Magic
        magic = self._data[:_MAGIC_LEN]
        if magic != BUNDLE_MAGIC:
            raise BundleError(
                f"Invalid bundle magic: {magic!r} (expected {BUNDLE_MAGIC!r})"
            )

        # Version
        version = struct.unpack(">H", self._data[_MAGIC_LEN:_MAGIC_LEN + _VERSION_LEN])[0]
        if version != BUNDLE_VERSION:
            raise BundleError(
                f"Unsupported bundle version: {version} (expected {BUNDLE_VERSION})"
            )

        # Manifest length
        manifest_len = struct.unpack(
            ">I",
            self._data[_MAGIC_LEN + _VERSION_LEN:_HEADER_PREFIX_LEN]
        )[0]

        # Check we have enough data
        min_len = _HEADER_PREFIX_LEN + manifest_len + 2 * _SIGNATURE_LEN
        if len(self._data) < min_len:
            raise BundleError(
                f"Bundle truncated: {len(self._data)} bytes, "
                f"need at least {min_len}"
            )

        # Extract sections
        offset = _HEADER_PREFIX_LEN
        self._manifest_json = self._data[offset:offset + manifest_len]
        offset += manifest_len

        self._labs_signature = self._data[offset:offset + _SIGNATURE_LEN]
        offset += _SIGNATURE_LEN

        self._deploy_signature = self._data[offset:offset + _SIGNATURE_LEN]
        offset += _SIGNATURE_LEN

        self._encrypted_payload = self._data[offset:]

        # Parse manifest
        self._manifest = BundleManifest.from_json(self._manifest_json)

    @property
    def manifest(self) -> BundleManifest:
        """The cleartext bundle manifest (always accessible without decryption)."""
        return self._manifest

    @property
    def signed_content(self) -> bytes:
        """The content that was signed (manifest + encrypted payload)."""
        return self._manifest_json + self._encrypted_payload

    def verify(
        self,
        labs_public_key: Union[Ed25519PublicKey, bytes],
        deployment_public_key: Union[Ed25519PublicKey, bytes],
    ) -> bool:
        """Verify both signatures on the bundle.

        Args:
            labs_public_key: TELOS Labs Ed25519 public key (object or 32 bytes).
            deployment_public_key: Deployment Ed25519 public key (object or 32 bytes).

        Returns:
            True if both signatures are valid.

        Raises:
            BundleError: If either signature is invalid.
        """
        try:
            return SigningKeyPair.verify_dual(
                self.signed_content,
                self._labs_signature,
                labs_public_key,
                self._deploy_signature,
                deployment_public_key,
            )
        except SigningError as e:
            raise BundleError(f"Bundle signature verification failed: {e}") from e

    def verify_labs(
        self,
        labs_public_key: Union[Ed25519PublicKey, bytes],
    ) -> bool:
        """Verify only the TELOS Labs signature (authenticity check).

        Args:
            labs_public_key: TELOS Labs Ed25519 public key.

        Returns:
            True if the Labs signature is valid.

        Raises:
            BundleError: If the signature is invalid.
        """
        try:
            return SigningKeyPair.verify(
                self.signed_content,
                self._labs_signature,
                labs_public_key,
            )
        except SigningError as e:
            raise BundleError(f"Labs signature verification failed: {e}") from e

    def decrypt(
        self,
        license_key: bytes,
        agent_id_as_aad: bool = True,
    ) -> bytes:
        """Decrypt the bundle payload.

        Args:
            license_key: License key material matching the one used to encrypt.
            agent_id_as_aad: If True, use manifest agent_id as AAD for decryption.

        Returns:
            Decrypted configuration data.

        Raises:
            BundleError: If decryption fails (wrong key, tampered, etc.).
        """
        try:
            encryptor = ConfigEncryptor(license_key)
            aad = None
            if agent_id_as_aad and self._manifest.agent_id:
                aad = self._manifest.agent_id.encode("utf-8")
            plaintext = encryptor.decrypt(self._encrypted_payload, aad=aad)

            # Verify content hash
            actual_hash = hashlib.sha256(plaintext).hexdigest()
            if self._manifest.content_hash and actual_hash != self._manifest.content_hash:
                raise BundleError(
                    "Content hash mismatch after decryption -- "
                    "data may be corrupted or the wrong license key was used"
                )

            return plaintext
        except ConfigEncryptionError as e:
            raise BundleError(f"Bundle decryption failed: {e}") from e
        except BundleError:
            raise
        except Exception as e:
            raise BundleError(f"Unexpected decryption error: {e}") from e

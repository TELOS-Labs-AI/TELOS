"""
Bundle Signing: Ed25519 key management for .telos bundle distribution integrity.

This module handles signing and verification of .telos bundle files, NOT
governance receipts (see receipt_signer.py for that). Two distinct key roles:

1. **TELOS Labs key** -- Signs bundles to prove they were built by TELOS Labs.
   Customers verify bundle authenticity against the published public key.

2. **Deployment key** -- Signs bundles to authorize them for a specific customer.
   The customer's license token contains their deployment public key.

Dual-signature design:
- TELOS Labs signs the bundle content (authenticity)
- Deployment key signs the bundle content (authorization)
- Verification requires BOTH signatures to pass

Key format:
- Ed25519 (RFC 8032, NIST FIPS 186-5)
- 32-byte private key, 32-byte public key, 64-byte signatures
- PEM encoding for file storage (PKCS8 private, SubjectPublicKeyInfo public)
- Key fingerprint: SHA-256 of raw public key bytes, hex-encoded

Compliance:
- NIST AI 600-1 (Supply Chain Integrity): Dual-signature ensures governance
  configuration provenance from TELOS Labs to customer deployment. The labs
  signature proves authenticity (built by TELOS Labs); the deployment signature
  proves authorization (intended for this specific customer).
- FedRAMP SA-9 (External Information System Services): Cryptographic verification
  of externally supplied governance components -- customers verify that bundles
  originate from TELOS Labs, not a third party or compromised build pipeline.
- OWASP LLM Top 10 (LLM05 -- Supply Chain Vulnerabilities): Ed25519 signing
  prevents supply chain tampering with governance configurations. Both the
  vendor signature and deployment signature must verify before a bundle can
  be activated, providing defense-in-depth against supply chain attacks.
- FedRAMP PL-8 (Security and Privacy Architectures): Key separation between
  Labs and deployment keys implements architectural security boundaries.

Usage:
    from telos_governance.signing import SigningKeyPair

    # Generate a new key pair
    kp = SigningKeyPair.generate()

    # Save to PEM files
    kp.save_private_pem("telos_labs.key")
    kp.save_public_pem("telos_labs.pub")

    # Load from PEM files
    kp = SigningKeyPair.from_private_pem("telos_labs.key")
    pub = SigningKeyPair.load_public_pem("telos_labs.pub")

    # Sign content
    signature = kp.sign(bundle_bytes)

    # Verify with public key only
    SigningKeyPair.verify(bundle_bytes, signature, pub)

    # Key fingerprint for identification
    print(kp.fingerprint)  # "a3b2c1..."
"""

import hashlib
import os
from pathlib import Path
from typing import Union

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


class SigningError(Exception):
    """Raised when signing or verification fails."""
    pass


class SigningKeyPair:
    """Ed25519 key pair for bundle signing and verification.

    Handles key generation, persistence (PEM files), signing, and verification.
    Designed for two roles: TELOS Labs (authenticity) and deployment (authorization).
    """

    def __init__(self, private_key: Ed25519PrivateKey):
        """Initialize from an Ed25519 private key.

        Args:
            private_key: Ed25519 private key (generates public key automatically).
        """
        self._private_key = private_key
        self._public_key = private_key.public_key()

    # -------------------------------------------------------------------------
    # Construction
    # -------------------------------------------------------------------------

    @classmethod
    def generate(cls) -> "SigningKeyPair":
        """Generate a new Ed25519 key pair.

        Returns:
            Fresh SigningKeyPair with randomly generated keys.
        """
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_private_bytes(cls, raw: bytes) -> "SigningKeyPair":
        """Load from 32-byte raw Ed25519 private key.

        Args:
            raw: 32-byte raw private key.

        Returns:
            SigningKeyPair from the provided key.

        Raises:
            SigningError: If the key bytes are invalid.
        """
        try:
            return cls(Ed25519PrivateKey.from_private_bytes(raw))
        except Exception as e:
            raise SigningError(f"Invalid private key bytes: {e}") from e

    @classmethod
    def from_private_pem(cls, path: Union[str, Path]) -> "SigningKeyPair":
        """Load key pair from a PEM-encoded private key file.

        Args:
            path: Path to PEM file containing PKCS8-encoded Ed25519 private key.

        Returns:
            SigningKeyPair from the file.

        Raises:
            SigningError: If the file cannot be read or parsed.
        """
        try:
            data = Path(path).read_bytes()
            private_key = serialization.load_pem_private_key(data, password=None)
            if not isinstance(private_key, Ed25519PrivateKey):
                raise SigningError(f"Key at {path} is not Ed25519")
            return cls(private_key)
        except SigningError:
            raise
        except Exception as e:
            raise SigningError(f"Failed to load private key from {path}: {e}") from e

    @staticmethod
    def load_public_pem(path: Union[str, Path]) -> Ed25519PublicKey:
        """Load a public key from a PEM file.

        This is the verification-only path -- no private key needed.

        Args:
            path: Path to PEM file containing Ed25519 public key.

        Returns:
            Ed25519PublicKey for verification.

        Raises:
            SigningError: If the file cannot be read or parsed.
        """
        try:
            data = Path(path).read_bytes()
            public_key = serialization.load_pem_public_key(data)
            if not isinstance(public_key, Ed25519PublicKey):
                raise SigningError(f"Key at {path} is not Ed25519")
            return public_key
        except SigningError:
            raise
        except Exception as e:
            raise SigningError(f"Failed to load public key from {path}: {e}") from e

    @staticmethod
    def public_key_from_bytes(raw: bytes) -> Ed25519PublicKey:
        """Create a public key from 32-byte raw bytes.

        Args:
            raw: 32-byte raw Ed25519 public key.

        Returns:
            Ed25519PublicKey for verification.

        Raises:
            SigningError: If the bytes are invalid.
        """
        try:
            return Ed25519PublicKey.from_public_bytes(raw)
        except Exception as e:
            raise SigningError(f"Invalid public key bytes: {e}") from e

    # -------------------------------------------------------------------------
    # Key export
    # -------------------------------------------------------------------------

    @property
    def public_key(self) -> Ed25519PublicKey:
        """The Ed25519 public key."""
        return self._public_key

    @property
    def public_key_bytes(self) -> bytes:
        """32-byte raw Ed25519 public key."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    @property
    def private_key_bytes(self) -> bytes:
        """32-byte raw Ed25519 private key.

        WARNING: Handle with care. Store encrypted at rest.
        """
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )

    @property
    def fingerprint(self) -> str:
        """SHA-256 fingerprint of the public key (hex-encoded).

        Use this as a human-readable key identifier for logs, manifests,
        and license tokens.
        """
        return hashlib.sha256(self.public_key_bytes).hexdigest()

    def save_private_pem(self, path: Union[str, Path]) -> None:
        """Save the private key to a PEM file.

        Creates the file with restricted permissions (owner read/write only).
        Parent directories must already exist.

        Args:
            path: Destination file path.

        Raises:
            SigningError: If the file cannot be written.
        """
        try:
            pem_data = self._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            p = Path(path)
            # Write with restricted permissions
            fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                os.write(fd, pem_data)
            finally:
                os.close(fd)
        except Exception as e:
            raise SigningError(f"Failed to save private key to {path}: {e}") from e

    def save_public_pem(self, path: Union[str, Path]) -> None:
        """Save the public key to a PEM file.

        Args:
            path: Destination file path.

        Raises:
            SigningError: If the file cannot be written.
        """
        try:
            pem_data = self._public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            Path(path).write_bytes(pem_data)
        except Exception as e:
            raise SigningError(f"Failed to save public key to {path}: {e}") from e

    # -------------------------------------------------------------------------
    # Signing
    # -------------------------------------------------------------------------

    def sign(self, data: bytes) -> bytes:
        """Sign arbitrary bytes with Ed25519.

        Args:
            data: Content to sign (bundle bytes, manifest, etc.).

        Returns:
            64-byte Ed25519 signature.

        Raises:
            SigningError: If signing fails.
        """
        try:
            return self._private_key.sign(data)
        except Exception as e:
            raise SigningError(f"Signing failed: {e}") from e

    def sign_file(self, path: Union[str, Path]) -> bytes:
        """Sign a file's contents.

        Args:
            path: Path to the file to sign.

        Returns:
            64-byte Ed25519 signature over the file contents.

        Raises:
            SigningError: If the file cannot be read or signing fails.
        """
        try:
            data = Path(path).read_bytes()
            return self.sign(data)
        except SigningError:
            raise
        except Exception as e:
            raise SigningError(f"Failed to read file {path}: {e}") from e

    # -------------------------------------------------------------------------
    # Verification (static -- only needs public key)
    # -------------------------------------------------------------------------

    @staticmethod
    def verify(
        data: bytes,
        signature: bytes,
        public_key: Union[Ed25519PublicKey, bytes],
    ) -> bool:
        """Verify an Ed25519 signature.

        Args:
            data: The original signed content.
            signature: 64-byte Ed25519 signature.
            public_key: Ed25519PublicKey object or 32-byte raw public key bytes.

        Returns:
            True if verification succeeds.

        Raises:
            SigningError: If signature is invalid, data was tampered,
                or the wrong key was used.
        """
        try:
            if isinstance(public_key, bytes):
                public_key = Ed25519PublicKey.from_public_bytes(public_key)

            public_key.verify(signature, data)
            return True
        except InvalidSignature:
            raise SigningError("Signature verification failed -- wrong key or tampered content")
        except Exception as e:
            raise SigningError(f"Verification error: {e}") from e

    @staticmethod
    def verify_file(
        path: Union[str, Path],
        signature: bytes,
        public_key: Union[Ed25519PublicKey, bytes],
    ) -> bool:
        """Verify an Ed25519 signature over a file's contents.

        Args:
            path: Path to the file to verify.
            signature: 64-byte Ed25519 signature.
            public_key: Ed25519PublicKey object or 32-byte raw public key bytes.

        Returns:
            True if verification succeeds.

        Raises:
            SigningError: If verification fails.
        """
        try:
            data = Path(path).read_bytes()
            return SigningKeyPair.verify(data, signature, public_key)
        except SigningError:
            raise
        except Exception as e:
            raise SigningError(f"Failed to read file {path}: {e}") from e

    # -------------------------------------------------------------------------
    # Dual-signature helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def verify_dual(
        data: bytes,
        labs_signature: bytes,
        labs_public_key: Union[Ed25519PublicKey, bytes],
        deployment_signature: bytes,
        deployment_public_key: Union[Ed25519PublicKey, bytes],
    ) -> bool:
        """Verify dual signatures (TELOS Labs + deployment key).

        Both signatures must be valid for the verification to pass.
        This is the bundle verification path -- a valid bundle requires
        both authenticity (Labs) and authorization (deployment).

        Args:
            data: The signed content.
            labs_signature: TELOS Labs Ed25519 signature.
            labs_public_key: TELOS Labs Ed25519 public key.
            deployment_signature: Deployment Ed25519 signature.
            deployment_public_key: Deployment Ed25519 public key.

        Returns:
            True if both signatures are valid.

        Raises:
            SigningError: If either signature is invalid.
        """
        SigningKeyPair.verify(data, labs_signature, labs_public_key)
        SigningKeyPair.verify(data, deployment_signature, deployment_public_key)
        return True

"""
Crypto Layer: AES-256-GCM encryption-at-rest for PA configuration.

Protects intellectual property in .telos bundles by encrypting boundary
corpus, tool definitions, purpose statements, and safe exemplars. This is
the encryption-at-rest complement to TKeys' session-bound encryption.

Design:
- AES-256-GCM authenticated encryption (NIST FIPS 197)
- HKDF key derivation from license key material (RFC 5869)
- 96-bit random nonce per encryption (NIST SP 800-38D)
- Version-tagged ciphertext for forward compatibility
- No password stretching (keys are high-entropy license material, not passwords)

Compliance:
- NIST AI 600-1: IP protection for governance configuration as required for
  proprietary AI system components. The encrypted PA specification is the
  intellectual property that must be protected during distribution.
- IEEE P7002 (Data Privacy Process): Encryption-at-rest for governance data
  satisfies IEEE P7002's requirement for technical controls protecting
  sensitive AI system configuration from unauthorized disclosure.
- FedRAMP SI-7 (Software, Firmware, and Information Integrity): Version-tagged,
  authenticated encryption with integrity verification (GCM authentication tag)
  satisfies SI-7's requirement for integrity verification of information at rest.
- OWASP LLM Top 10 (LLM05 -- Supply Chain Vulnerabilities): Encryption prevents
  extraction or tampering with governance configurations during distribution.

Usage:
    from telos_governance.crypto_layer import ConfigEncryptor

    # Encrypt a PA config for bundling
    encryptor = ConfigEncryptor(license_key=b"32-byte-license-key-material...")
    encrypted = encryptor.encrypt(config_bytes)

    # Decrypt on customer side
    decrypted = encryptor.decrypt(encrypted)

Wire Format (encrypted blob):
    [1 byte]  version (0x01)
    [16 bytes] salt (for HKDF derivation)
    [12 bytes] nonce (for AES-GCM)
    [N bytes]  ciphertext + GCM tag (16 bytes appended by AES-GCM)

The salt is per-encryption, ensuring that even with the same license key,
each encryption produces a unique derived key. This prevents ciphertext
correlation across different config versions.
"""

import secrets
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

# Wire format version
_CRYPTO_VERSION = b'\x01'
_VERSION_LEN = 1
_SALT_LEN = 16
_NONCE_LEN = 12
_HEADER_LEN = _VERSION_LEN + _SALT_LEN + _NONCE_LEN  # 29 bytes


class ConfigEncryptionError(Exception):
    """Raised when encryption or decryption fails."""
    pass


class ConfigEncryptor:
    """AES-256-GCM encryption for PA configuration data.

    Derives a unique encryption key per operation using HKDF with a
    random salt, ensuring no ciphertext correlation even with the same
    license key across multiple encryptions.

    Args:
        license_key: 32-byte key material (from license token or key file).
            If shorter than 32 bytes, HKDF stretches it. If longer, HKDF
            compresses it. But 32 bytes is the recommended input size.
    """

    def __init__(self, license_key: bytes):
        if not license_key or len(license_key) < 16:
            raise ValueError("License key must be at least 16 bytes")
        self._license_key = license_key

    def _derive_key(self, salt: bytes) -> bytes:
        """Derive a 256-bit AES key from license key + salt using HKDF."""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"telos-config-encryption-v1",
        )
        return hkdf.derive(self._license_key)

    def encrypt(self, plaintext: bytes, aad: Optional[bytes] = None) -> bytes:
        """Encrypt configuration data.

        Args:
            plaintext: Raw configuration bytes to encrypt.
            aad: Optional additional authenticated data (e.g., agent_id).
                AAD is authenticated but NOT encrypted -- it must be provided
                again at decryption time for verification.

        Returns:
            Encrypted blob with version + salt + nonce + ciphertext header.

        Raises:
            ConfigEncryptionError: If encryption fails.
        """
        try:
            salt = secrets.token_bytes(_SALT_LEN)
            nonce = secrets.token_bytes(_NONCE_LEN)
            key = self._derive_key(salt)

            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext, aad)

            return _CRYPTO_VERSION + salt + nonce + ciphertext
        except Exception as e:
            raise ConfigEncryptionError(f"Encryption failed: {e}") from e

    def decrypt(self, encrypted: bytes, aad: Optional[bytes] = None) -> bytes:
        """Decrypt configuration data.

        Args:
            encrypted: Encrypted blob from encrypt().
            aad: Optional additional authenticated data (must match encrypt).

        Returns:
            Decrypted plaintext bytes.

        Raises:
            ConfigEncryptionError: If decryption fails (wrong key, tampered, etc).
        """
        if len(encrypted) < _HEADER_LEN + 16:  # minimum: header + GCM tag
            raise ConfigEncryptionError(
                f"Encrypted data too short ({len(encrypted)} bytes, minimum {_HEADER_LEN + 16})"
            )

        version = encrypted[:_VERSION_LEN]
        if version != _CRYPTO_VERSION:
            raise ConfigEncryptionError(
                f"Unsupported encryption version: 0x{version.hex()}"
            )

        salt = encrypted[_VERSION_LEN:_VERSION_LEN + _SALT_LEN]
        nonce = encrypted[_VERSION_LEN + _SALT_LEN:_HEADER_LEN]
        ciphertext = encrypted[_HEADER_LEN:]

        try:
            key = self._derive_key(salt)
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext, aad)
        except Exception as e:
            raise ConfigEncryptionError(
                "Decryption failed -- wrong key, corrupted data, or tampered ciphertext"
            ) from e


def encrypt_config_file(config_bytes: bytes, license_key: bytes,
                        agent_id: Optional[str] = None) -> bytes:
    """Convenience: encrypt a config file with optional agent_id binding.

    If agent_id is provided, it's used as AAD -- the encrypted config can
    only be decrypted when the same agent_id is provided. This binds the
    config to a specific agent, preventing config reuse across agents.

    Args:
        config_bytes: Raw YAML config bytes.
        license_key: License key material (>= 16 bytes).
        agent_id: Optional agent identifier for AAD binding.

    Returns:
        Encrypted blob.
    """
    encryptor = ConfigEncryptor(license_key)
    aad = agent_id.encode("utf-8") if agent_id else None
    return encryptor.encrypt(config_bytes, aad=aad)


def decrypt_config_file(encrypted: bytes, license_key: bytes,
                        agent_id: Optional[str] = None) -> bytes:
    """Convenience: decrypt a config file with optional agent_id binding.

    Args:
        encrypted: Encrypted blob from encrypt_config_file().
        license_key: License key material (must match encryption key).
        agent_id: Optional agent identifier (must match encryption AAD).

    Returns:
        Decrypted YAML config bytes.
    """
    encryptor = ConfigEncryptor(license_key)
    aad = agent_id.encode("utf-8") if agent_id else None
    return encryptor.decrypt(encrypted, aad=aad)

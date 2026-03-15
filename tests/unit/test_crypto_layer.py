"""
Tests for telos_governance.crypto_layer
========================================

Tests for ConfigEncryptor: AES-256-GCM encryption-at-rest for PA configuration.
Verifies round-trip, key validation, tamper detection, AAD binding, version
check, and ciphertext uniqueness (no correlation across encryptions).
"""

import os
import secrets
import pytest

from telos_governance.crypto_layer import (
    ConfigEncryptor,
    ConfigEncryptionError,
    encrypt_config_file,
    decrypt_config_file,
    _CRYPTO_VERSION,
    _HEADER_LEN,
    _SALT_LEN,
    _NONCE_LEN,
    _VERSION_LEN,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def license_key():
    """32-byte license key for testing."""
    return secrets.token_bytes(32)


@pytest.fixture
def encryptor(license_key):
    """ConfigEncryptor instance with test key."""
    return ConfigEncryptor(license_key)


@pytest.fixture
def sample_config():
    """Sample YAML config bytes."""
    return b"""purpose: "Property intelligence for underwriting"
scope: "Aerial imagery analysis and risk scoring"
boundaries:
  - "Never make binding coverage decisions"
"""


# ---------------------------------------------------------------------------
# Construction / key validation
# ---------------------------------------------------------------------------

class TestConfigEncryptorInit:
    def test_valid_32_byte_key(self):
        enc = ConfigEncryptor(secrets.token_bytes(32))
        assert enc is not None

    def test_valid_16_byte_key(self):
        enc = ConfigEncryptor(secrets.token_bytes(16))
        assert enc is not None

    def test_valid_64_byte_key(self):
        """Keys longer than 32 bytes are accepted -- HKDF compresses."""
        enc = ConfigEncryptor(secrets.token_bytes(64))
        assert enc is not None

    def test_reject_empty_key(self):
        with pytest.raises(ValueError, match="at least 16 bytes"):
            ConfigEncryptor(b"")

    def test_reject_short_key(self):
        with pytest.raises(ValueError, match="at least 16 bytes"):
            ConfigEncryptor(b"tooshort")

    def test_reject_15_byte_key(self):
        with pytest.raises(ValueError, match="at least 16 bytes"):
            ConfigEncryptor(secrets.token_bytes(15))


# ---------------------------------------------------------------------------
# Round-trip encryption/decryption
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_basic_round_trip(self, encryptor, sample_config):
        encrypted = encryptor.encrypt(sample_config)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == sample_config

    def test_round_trip_empty_plaintext(self, encryptor):
        encrypted = encryptor.encrypt(b"")
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == b""

    def test_round_trip_large_payload(self, encryptor):
        large = secrets.token_bytes(1_000_000)  # 1 MB
        encrypted = encryptor.encrypt(large)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == large

    def test_round_trip_with_aad(self, encryptor, sample_config):
        aad = b"agent-nearmap-property-intel"
        encrypted = encryptor.encrypt(sample_config, aad=aad)
        decrypted = encryptor.decrypt(encrypted, aad=aad)
        assert decrypted == sample_config

    def test_round_trip_convenience_functions(self, license_key, sample_config):
        encrypted = encrypt_config_file(sample_config, license_key)
        decrypted = decrypt_config_file(encrypted, license_key)
        assert decrypted == sample_config

    def test_round_trip_convenience_with_agent_id(self, license_key, sample_config):
        encrypted = encrypt_config_file(sample_config, license_key, agent_id="nearmap-v1")
        decrypted = decrypt_config_file(encrypted, license_key, agent_id="nearmap-v1")
        assert decrypted == sample_config


# ---------------------------------------------------------------------------
# Wire format
# ---------------------------------------------------------------------------

class TestWireFormat:
    def test_version_byte(self, encryptor, sample_config):
        encrypted = encryptor.encrypt(sample_config)
        assert encrypted[0:1] == _CRYPTO_VERSION
        assert encrypted[0:1] == b'\x01'

    def test_minimum_output_size(self, encryptor):
        """Even empty plaintext produces header + GCM tag."""
        encrypted = encryptor.encrypt(b"")
        assert len(encrypted) >= _HEADER_LEN + 16  # 29 + 16 = 45 bytes

    def test_header_length(self):
        assert _HEADER_LEN == 29  # 1 + 16 + 12

    def test_output_grows_with_plaintext(self, encryptor):
        small = encryptor.encrypt(b"x")
        large = encryptor.encrypt(b"x" * 1000)
        assert len(large) > len(small)


# ---------------------------------------------------------------------------
# Wrong key / tamper detection
# ---------------------------------------------------------------------------

class TestDecryptionFailures:
    def test_wrong_key_fails(self, sample_config):
        key_a = secrets.token_bytes(32)
        key_b = secrets.token_bytes(32)
        encrypted = ConfigEncryptor(key_a).encrypt(sample_config)
        with pytest.raises(ConfigEncryptionError, match="Decryption failed"):
            ConfigEncryptor(key_b).decrypt(encrypted)

    def test_tampered_ciphertext_fails(self, encryptor, sample_config):
        encrypted = bytearray(encryptor.encrypt(sample_config))
        # Flip a byte in the ciphertext (after the header)
        encrypted[_HEADER_LEN + 5] ^= 0xFF
        with pytest.raises(ConfigEncryptionError, match="Decryption failed"):
            encryptor.decrypt(bytes(encrypted))

    def test_tampered_nonce_fails(self, encryptor, sample_config):
        encrypted = bytearray(encryptor.encrypt(sample_config))
        # Flip a byte in the nonce region
        nonce_offset = _VERSION_LEN + _SALT_LEN
        encrypted[nonce_offset] ^= 0xFF
        with pytest.raises(ConfigEncryptionError, match="Decryption failed"):
            encryptor.decrypt(bytes(encrypted))

    def test_tampered_salt_fails(self, encryptor, sample_config):
        encrypted = bytearray(encryptor.encrypt(sample_config))
        # Flip a byte in the salt region
        encrypted[_VERSION_LEN] ^= 0xFF
        with pytest.raises(ConfigEncryptionError, match="Decryption failed"):
            encryptor.decrypt(bytes(encrypted))

    def test_truncated_blob_fails(self, encryptor, sample_config):
        encrypted = encryptor.encrypt(sample_config)
        with pytest.raises(ConfigEncryptionError, match="too short"):
            encryptor.decrypt(encrypted[:20])

    def test_wrong_version_fails(self, encryptor, sample_config):
        encrypted = bytearray(encryptor.encrypt(sample_config))
        encrypted[0] = 0x99  # Invalid version
        with pytest.raises(ConfigEncryptionError, match="Unsupported encryption version"):
            encryptor.decrypt(bytes(encrypted))


# ---------------------------------------------------------------------------
# AAD binding
# ---------------------------------------------------------------------------

class TestAADBinding:
    def test_aad_mismatch_fails(self, encryptor, sample_config):
        encrypted = encryptor.encrypt(sample_config, aad=b"agent-A")
        with pytest.raises(ConfigEncryptionError, match="Decryption failed"):
            encryptor.decrypt(encrypted, aad=b"agent-B")

    def test_missing_aad_at_decrypt_fails(self, encryptor, sample_config):
        encrypted = encryptor.encrypt(sample_config, aad=b"agent-A")
        with pytest.raises(ConfigEncryptionError, match="Decryption failed"):
            encryptor.decrypt(encrypted)  # No AAD provided

    def test_extra_aad_at_decrypt_fails(self, encryptor, sample_config):
        encrypted = encryptor.encrypt(sample_config)  # No AAD
        with pytest.raises(ConfigEncryptionError, match="Decryption failed"):
            encryptor.decrypt(encrypted, aad=b"unexpected-agent")

    def test_convenience_agent_id_mismatch_fails(self, license_key, sample_config):
        encrypted = encrypt_config_file(sample_config, license_key, agent_id="agent-A")
        with pytest.raises(ConfigEncryptionError):
            decrypt_config_file(encrypted, license_key, agent_id="agent-B")


# ---------------------------------------------------------------------------
# Ciphertext uniqueness (no correlation)
# ---------------------------------------------------------------------------

class TestCiphertextUniqueness:
    def test_same_plaintext_different_ciphertext(self, encryptor, sample_config):
        """Each encryption uses a unique salt + nonce → different ciphertext."""
        ct1 = encryptor.encrypt(sample_config)
        ct2 = encryptor.encrypt(sample_config)
        assert ct1 != ct2

    def test_different_salts(self, encryptor, sample_config):
        ct1 = encryptor.encrypt(sample_config)
        ct2 = encryptor.encrypt(sample_config)
        salt1 = ct1[_VERSION_LEN:_VERSION_LEN + _SALT_LEN]
        salt2 = ct2[_VERSION_LEN:_VERSION_LEN + _SALT_LEN]
        assert salt1 != salt2

    def test_different_nonces(self, encryptor, sample_config):
        ct1 = encryptor.encrypt(sample_config)
        ct2 = encryptor.encrypt(sample_config)
        nonce_start = _VERSION_LEN + _SALT_LEN
        nonce1 = ct1[nonce_start:_HEADER_LEN]
        nonce2 = ct2[nonce_start:_HEADER_LEN]
        assert nonce1 != nonce2

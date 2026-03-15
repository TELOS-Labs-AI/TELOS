"""
Tests for telos_governance.signing -- Ed25519 bundle signing key management.

Tests cover:
- Key generation and properties
- Key persistence (PEM files)
- Signing and verification (bytes and files)
- Dual-signature verification
- Error cases (wrong key, tampered data, invalid inputs)
- Key fingerprint stability
"""

import os
import pytest
from pathlib import Path

from telos_governance.signing import SigningKeyPair, SigningError


# =============================================================================
# Key generation
# =============================================================================

class TestKeyGeneration:
    """Test key pair generation."""

    def test_generate_returns_keypair(self):
        kp = SigningKeyPair.generate()
        assert kp is not None

    def test_public_key_is_32_bytes(self):
        kp = SigningKeyPair.generate()
        assert len(kp.public_key_bytes) == 32

    def test_private_key_is_32_bytes(self):
        kp = SigningKeyPair.generate()
        assert len(kp.private_key_bytes) == 32

    def test_two_keypairs_are_different(self):
        kp1 = SigningKeyPair.generate()
        kp2 = SigningKeyPair.generate()
        assert kp1.public_key_bytes != kp2.public_key_bytes
        assert kp1.private_key_bytes != kp2.private_key_bytes

    def test_fingerprint_is_hex_sha256(self):
        kp = SigningKeyPair.generate()
        fp = kp.fingerprint
        assert len(fp) == 64  # SHA-256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in fp)

    def test_fingerprint_is_stable(self):
        kp = SigningKeyPair.generate()
        assert kp.fingerprint == kp.fingerprint  # same object, same result

    def test_fingerprint_derives_from_public_key(self):
        import hashlib
        kp = SigningKeyPair.generate()
        expected = hashlib.sha256(kp.public_key_bytes).hexdigest()
        assert kp.fingerprint == expected


# =============================================================================
# Key loading from raw bytes
# =============================================================================

class TestKeyLoading:
    """Test loading keys from raw bytes."""

    def test_roundtrip_private_bytes(self):
        kp1 = SigningKeyPair.generate()
        raw = kp1.private_key_bytes
        kp2 = SigningKeyPair.from_private_bytes(raw)
        assert kp1.public_key_bytes == kp2.public_key_bytes

    def test_invalid_private_bytes_raises(self):
        with pytest.raises(SigningError, match="Invalid private key"):
            SigningKeyPair.from_private_bytes(b"too short")

    def test_public_key_from_bytes(self):
        kp = SigningKeyPair.generate()
        pub = SigningKeyPair.public_key_from_bytes(kp.public_key_bytes)
        assert pub is not None

    def test_invalid_public_bytes_raises(self):
        with pytest.raises(SigningError, match="Invalid public key"):
            SigningKeyPair.public_key_from_bytes(b"not 32 bytes")


# =============================================================================
# PEM file persistence
# =============================================================================

class TestPEMPersistence:
    """Test saving/loading keys as PEM files."""

    def test_save_load_private_pem(self, tmp_path):
        kp1 = SigningKeyPair.generate()
        key_file = tmp_path / "test.key"
        kp1.save_private_pem(key_file)
        kp2 = SigningKeyPair.from_private_pem(key_file)
        assert kp1.public_key_bytes == kp2.public_key_bytes
        assert kp1.private_key_bytes == kp2.private_key_bytes

    def test_private_pem_has_restricted_permissions(self, tmp_path):
        kp = SigningKeyPair.generate()
        key_file = tmp_path / "test.key"
        kp.save_private_pem(key_file)
        mode = os.stat(key_file).st_mode & 0o777
        assert mode == 0o600

    def test_save_load_public_pem(self, tmp_path):
        kp = SigningKeyPair.generate()
        pub_file = tmp_path / "test.pub"
        kp.save_public_pem(pub_file)
        pub = SigningKeyPair.load_public_pem(pub_file)
        raw = pub.public_bytes(
            encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.Raw,
            format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PublicFormat"]).PublicFormat.Raw,
        )
        assert raw == kp.public_key_bytes

    def test_load_nonexistent_private_pem_raises(self):
        with pytest.raises(SigningError, match="Failed to load private key"):
            SigningKeyPair.from_private_pem("/nonexistent/path.key")

    def test_load_nonexistent_public_pem_raises(self):
        with pytest.raises(SigningError, match="Failed to load public key"):
            SigningKeyPair.load_public_pem("/nonexistent/path.pub")

    def test_load_wrong_key_type_private(self, tmp_path):
        """Loading a non-Ed25519 key should raise."""
        from cryptography.hazmat.primitives.asymmetric import ec
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(
            encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.PEM,
            format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PrivateFormat"]).PrivateFormat.PKCS8,
            encryption_algorithm=__import__("cryptography.hazmat.primitives.serialization", fromlist=["NoEncryption"]).NoEncryption(),
        )
        key_file = tmp_path / "ec.key"
        key_file.write_bytes(pem)
        with pytest.raises(SigningError, match="not Ed25519"):
            SigningKeyPair.from_private_pem(key_file)


# =============================================================================
# Signing and verification
# =============================================================================

class TestSigning:
    """Test signing and verification."""

    def test_sign_returns_64_bytes(self):
        kp = SigningKeyPair.generate()
        sig = kp.sign(b"hello world")
        assert len(sig) == 64

    def test_sign_verify_roundtrip(self):
        kp = SigningKeyPair.generate()
        data = b"The quick brown fox"
        sig = kp.sign(data)
        assert SigningKeyPair.verify(data, sig, kp.public_key_bytes) is True

    def test_verify_with_public_key_object(self):
        kp = SigningKeyPair.generate()
        data = b"test data"
        sig = kp.sign(data)
        assert SigningKeyPair.verify(data, sig, kp.public_key) is True

    def test_wrong_key_raises(self):
        kp1 = SigningKeyPair.generate()
        kp2 = SigningKeyPair.generate()
        data = b"signed by kp1"
        sig = kp1.sign(data)
        with pytest.raises(SigningError, match="Signature verification failed"):
            SigningKeyPair.verify(data, sig, kp2.public_key_bytes)

    def test_tampered_data_raises(self):
        kp = SigningKeyPair.generate()
        data = b"original content"
        sig = kp.sign(data)
        with pytest.raises(SigningError, match="Signature verification failed"):
            SigningKeyPair.verify(b"tampered content", sig, kp.public_key_bytes)

    def test_tampered_signature_raises(self):
        kp = SigningKeyPair.generate()
        data = b"some data"
        sig = kp.sign(data)
        bad_sig = bytes([b ^ 0xFF for b in sig])  # flip all bits
        with pytest.raises(SigningError, match="Signature verification failed"):
            SigningKeyPair.verify(data, bad_sig, kp.public_key_bytes)

    def test_sign_empty_bytes(self):
        kp = SigningKeyPair.generate()
        sig = kp.sign(b"")
        assert SigningKeyPair.verify(b"", sig, kp.public_key_bytes) is True

    def test_sign_large_data(self):
        kp = SigningKeyPair.generate()
        data = os.urandom(1024 * 1024)  # 1MB
        sig = kp.sign(data)
        assert SigningKeyPair.verify(data, sig, kp.public_key_bytes) is True

    def test_deterministic_signatures(self):
        """Ed25519 signatures are deterministic (same key + data = same sig)."""
        kp = SigningKeyPair.generate()
        data = b"deterministic test"
        sig1 = kp.sign(data)
        sig2 = kp.sign(data)
        assert sig1 == sig2


# =============================================================================
# File signing
# =============================================================================

class TestFileSigning:
    """Test file-based signing and verification."""

    def test_sign_file(self, tmp_path):
        kp = SigningKeyPair.generate()
        f = tmp_path / "test.bin"
        content = b"file content to sign"
        f.write_bytes(content)
        sig = kp.sign_file(f)
        assert SigningKeyPair.verify(content, sig, kp.public_key_bytes) is True

    def test_verify_file(self, tmp_path):
        kp = SigningKeyPair.generate()
        f = tmp_path / "test.bin"
        content = b"file content to verify"
        f.write_bytes(content)
        sig = kp.sign(content)
        assert SigningKeyPair.verify_file(f, sig, kp.public_key_bytes) is True

    def test_sign_nonexistent_file_raises(self):
        kp = SigningKeyPair.generate()
        with pytest.raises(SigningError, match="Failed to read file"):
            kp.sign_file("/nonexistent/file.bin")

    def test_verify_nonexistent_file_raises(self):
        kp = SigningKeyPair.generate()
        with pytest.raises(SigningError):
            SigningKeyPair.verify_file("/nonexistent/file.bin", b"\x00" * 64, kp.public_key_bytes)


# =============================================================================
# Dual signatures
# =============================================================================

class TestDualSignature:
    """Test dual-signature verification (Labs + deployment)."""

    def test_dual_verify_both_valid(self):
        labs = SigningKeyPair.generate()
        deploy = SigningKeyPair.generate()
        data = b"bundle content"
        labs_sig = labs.sign(data)
        deploy_sig = deploy.sign(data)
        assert SigningKeyPair.verify_dual(
            data, labs_sig, labs.public_key_bytes,
            deploy_sig, deploy.public_key_bytes,
        ) is True

    def test_dual_verify_labs_invalid(self):
        labs = SigningKeyPair.generate()
        deploy = SigningKeyPair.generate()
        wrong = SigningKeyPair.generate()
        data = b"bundle content"
        wrong_sig = wrong.sign(data)
        deploy_sig = deploy.sign(data)
        with pytest.raises(SigningError, match="Signature verification failed"):
            SigningKeyPair.verify_dual(
                data, wrong_sig, labs.public_key_bytes,
                deploy_sig, deploy.public_key_bytes,
            )

    def test_dual_verify_deployment_invalid(self):
        labs = SigningKeyPair.generate()
        deploy = SigningKeyPair.generate()
        wrong = SigningKeyPair.generate()
        data = b"bundle content"
        labs_sig = labs.sign(data)
        wrong_sig = wrong.sign(data)
        with pytest.raises(SigningError, match="Signature verification failed"):
            SigningKeyPair.verify_dual(
                data, labs_sig, labs.public_key_bytes,
                wrong_sig, deploy.public_key_bytes,
            )

    def test_dual_verify_data_tampered(self):
        labs = SigningKeyPair.generate()
        deploy = SigningKeyPair.generate()
        data = b"original bundle"
        labs_sig = labs.sign(data)
        deploy_sig = deploy.sign(data)
        with pytest.raises(SigningError):
            SigningKeyPair.verify_dual(
                b"tampered bundle", labs_sig, labs.public_key_bytes,
                deploy_sig, deploy.public_key_bytes,
            )

"""
Tests for telos_governance.licensing -- offline Ed25519-signed license tokens.

Tests cover:
- Token building and parsing (roundtrip)
- Payload accessibility
- Signature verification (valid, wrong key)
- Validation (expiry, license key hash, agent_id, deployment fingerprint)
- Token format validation (magic, version, truncation, oversized)
- Perpetual vs time-limited licenses
- Tamper detection
- File I/O
"""

import os
import json
import struct
import hashlib
import tempfile
import pytest
from datetime import datetime, timezone, timedelta

from telos_governance.licensing import (
    LicenseTokenBuilder,
    LicenseToken,
    LicensePayload,
    LicenseError,
    LICENSE_MAGIC,
    LICENSE_VERSION,
    MAX_TOKEN_SIZE,
)
from telos_governance.signing import SigningKeyPair


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def labs_key():
    return SigningKeyPair.generate()

@pytest.fixture
def deploy_key():
    return SigningKeyPair.generate()

@pytest.fixture
def license_key():
    return os.urandom(32)

@pytest.fixture
def token_bytes(labs_key, deploy_key, license_key):
    builder = LicenseTokenBuilder(labs_key=labs_key)
    return builder.build(
        agent_id="property-intel-v2",
        deployment_fingerprint=deploy_key.fingerprint,
        license_key=license_key,
        capabilities=["governance", "intelligence_layer"],
        expires_in_days=365,
        telos_version_min="1.5.0",
    )

@pytest.fixture
def perpetual_token_bytes(labs_key, deploy_key, license_key):
    builder = LicenseTokenBuilder(labs_key=labs_key)
    return builder.build(
        agent_id="property-intel-v2",
        deployment_fingerprint=deploy_key.fingerprint,
        license_key=license_key,
        expires_in_days=None,
    )


# =============================================================================
# Token building
# =============================================================================

class TestTokenBuilding:
    """Test token construction."""

    def test_build_returns_bytes(self, labs_key, deploy_key, license_key):
        builder = LicenseTokenBuilder(labs_key=labs_key)
        result = builder.build(
            agent_id="test-agent",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
        )
        assert isinstance(result, bytes)

    def test_token_starts_with_magic(self, token_bytes):
        assert token_bytes[:4] == LICENSE_MAGIC

    def test_token_has_correct_version(self, token_bytes):
        version = struct.unpack(">H", token_bytes[4:6])[0]
        assert version == LICENSE_VERSION

    def test_token_has_expected_structure(self, token_bytes):
        # Header (10) + payload JSON + signature (64)
        assert len(token_bytes) > 10 + 64

    def test_build_perpetual_token(self, labs_key, deploy_key, license_key):
        builder = LicenseTokenBuilder(labs_key=labs_key)
        result = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
            expires_in_days=None,
        )
        token = LicenseToken(result)
        assert token.is_perpetual

    def test_build_default_capabilities(self, labs_key, deploy_key, license_key):
        builder = LicenseTokenBuilder(labs_key=labs_key)
        result = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
        )
        token = LicenseToken(result)
        assert token.capabilities == ["governance"]


# =============================================================================
# Token reading
# =============================================================================

class TestTokenReading:
    """Test token parsing and payload access."""

    def test_parse_token(self, token_bytes):
        token = LicenseToken(token_bytes)
        assert token.payload is not None

    def test_agent_id(self, token_bytes):
        token = LicenseToken(token_bytes)
        assert token.agent_id == "property-intel-v2"

    def test_capabilities(self, token_bytes):
        token = LicenseToken(token_bytes)
        assert token.capabilities == ["governance", "intelligence_layer"]

    def test_has_token_id(self, token_bytes):
        token = LicenseToken(token_bytes)
        assert token.token_id  # non-empty UUID

    def test_has_issued_at(self, token_bytes):
        token = LicenseToken(token_bytes)
        assert token.payload.issued_at  # non-empty

    def test_has_expires_at(self, token_bytes):
        token = LicenseToken(token_bytes)
        assert token.expires_at  # non-empty for time-limited

    def test_has_license_key_hash(self, token_bytes, license_key):
        token = LicenseToken(token_bytes)
        expected = hashlib.sha256(license_key).hexdigest()
        assert token.payload.license_key_hash == expected

    def test_deployment_fingerprint(self, token_bytes, deploy_key):
        token = LicenseToken(token_bytes)
        assert token.payload.deployment_fingerprint == deploy_key.fingerprint

    def test_issuer(self, token_bytes):
        token = LicenseToken(token_bytes)
        assert token.payload.issuer == "TELOS Labs"

    def test_telos_version_min(self, token_bytes):
        token = LicenseToken(token_bytes)
        assert token.payload.telos_version_min == "1.5.0"


# =============================================================================
# Signature verification
# =============================================================================

class TestSignatureVerification:
    """Test Ed25519 signature verification."""

    def test_verify_valid_signature(self, token_bytes, labs_key):
        token = LicenseToken(token_bytes)
        assert token.verify(labs_key.public_key_bytes) is True

    def test_verify_with_public_key_object(self, token_bytes, labs_key):
        token = LicenseToken(token_bytes)
        assert token.verify(labs_key.public_key) is True

    def test_verify_wrong_key_raises(self, token_bytes):
        wrong_key = SigningKeyPair.generate()
        token = LicenseToken(token_bytes)
        with pytest.raises(LicenseError, match="signature verification failed"):
            token.verify(wrong_key.public_key_bytes)


# =============================================================================
# Validation
# =============================================================================

class TestValidation:
    """Test license token validation checks."""

    def test_validate_all_pass(self, token_bytes, license_key, deploy_key):
        token = LicenseToken(token_bytes)
        assert token.validate(
            license_key=license_key,
            agent_id="property-intel-v2",
            deployment_fingerprint=deploy_key.fingerprint,
        ) is True

    def test_expired_token_raises(self, labs_key, deploy_key, license_key):
        """A token that expired yesterday should fail validation."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        token_data = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
            expires_in_days=1,
        )
        token = LicenseToken(token_data)
        # Simulate time 2 days from now
        future = datetime.now(timezone.utc) + timedelta(days=2)
        with pytest.raises(LicenseError, match="License expired"):
            token.validate(now=future)

    def test_not_yet_expired_passes(self, token_bytes):
        """A token with 365 days left should pass."""
        token = LicenseToken(token_bytes)
        assert token.validate() is True  # default is now, token expires in 365 days

    def test_perpetual_never_expires(self, perpetual_token_bytes):
        """A perpetual token should pass even far in the future."""
        token = LicenseToken(perpetual_token_bytes)
        far_future = datetime.now(timezone.utc) + timedelta(days=36500)
        assert token.validate(now=far_future) is True

    def test_wrong_license_key_raises(self, token_bytes):
        token = LicenseToken(token_bytes)
        wrong_key = os.urandom(32)
        with pytest.raises(LicenseError, match="License key does not match"):
            token.validate(license_key=wrong_key)

    def test_correct_license_key_passes(self, token_bytes, license_key):
        token = LicenseToken(token_bytes)
        assert token.validate(license_key=license_key) is True

    def test_wrong_agent_id_raises(self, token_bytes, license_key):
        token = LicenseToken(token_bytes)
        with pytest.raises(LicenseError, match="Agent ID mismatch"):
            token.validate(agent_id="wrong-agent")

    def test_correct_agent_id_passes(self, token_bytes):
        token = LicenseToken(token_bytes)
        assert token.validate(agent_id="property-intel-v2") is True

    def test_wrong_deployment_fingerprint_raises(self, token_bytes):
        token = LicenseToken(token_bytes)
        with pytest.raises(LicenseError, match="Deployment key fingerprint mismatch"):
            token.validate(deployment_fingerprint="wrong-fingerprint")

    def test_correct_deployment_fingerprint_passes(self, token_bytes, deploy_key):
        token = LicenseToken(token_bytes)
        assert token.validate(deployment_fingerprint=deploy_key.fingerprint) is True

    def test_partial_validation(self, token_bytes, license_key):
        """Validation should work with only some checks provided."""
        token = LicenseToken(token_bytes)
        assert token.validate(license_key=license_key) is True
        assert token.validate(agent_id="property-intel-v2") is True
        assert token.validate() is True  # no checks, just expiry


# =============================================================================
# Format validation
# =============================================================================

class TestFormatValidation:
    """Test token format error handling."""

    def test_empty_data_raises(self):
        with pytest.raises(LicenseError, match="too short"):
            LicenseToken(b"")

    def test_wrong_magic_raises(self):
        with pytest.raises(LicenseError, match="Invalid license token magic"):
            LicenseToken(b"FAKE" + b"\x00" * 100)

    def test_wrong_version_raises(self):
        data = LICENSE_MAGIC + struct.pack(">H", 99) + b"\x00" * 100
        with pytest.raises(LicenseError, match="Unsupported license token version"):
            LicenseToken(data)

    def test_truncated_token_raises(self):
        data = LICENSE_MAGIC + struct.pack(">H", LICENSE_VERSION) + struct.pack(">I", 1000)
        with pytest.raises(LicenseError, match="truncated"):
            LicenseToken(data)

    def test_oversized_token_raises(self):
        """Tokens exceeding MAX_TOKEN_SIZE should be rejected."""
        data = LICENSE_MAGIC + struct.pack(">H", LICENSE_VERSION) + struct.pack(">I", 100)
        data += b"\x00" * (MAX_TOKEN_SIZE + 1 - len(data))
        with pytest.raises(LicenseError, match="too large"):
            LicenseToken(data)


# =============================================================================
# Tamper detection
# =============================================================================

class TestTamperDetection:
    """Test that modifications to the token are detected."""

    def test_tampered_payload_fails_verification(self, token_bytes, labs_key):
        """Modifying the payload should break signature verification."""
        data = bytearray(token_bytes)
        # Payload starts at offset 10 (after header)
        data[15] ^= 0xFF
        with pytest.raises(LicenseError):
            token = LicenseToken(bytes(data))
            token.verify(labs_key.public_key_bytes)

    def test_tampered_signature_fails_verification(self, token_bytes, labs_key):
        """Modifying the signature should break verification."""
        data = bytearray(token_bytes)
        data[-1] ^= 0xFF  # flip last byte (in signature)
        token = LicenseToken(bytes(data))
        with pytest.raises(LicenseError, match="signature verification failed"):
            token.verify(labs_key.public_key_bytes)

    def test_license_key_not_in_token(self, token_bytes, license_key):
        """The raw license key must not appear in the token."""
        assert license_key not in token_bytes


# =============================================================================
# Payload serialization
# =============================================================================

class TestPayloadSerialization:
    """Test LicensePayload to/from JSON."""

    def test_payload_roundtrip(self):
        p = LicensePayload(
            token_id="test-id",
            agent_id="test-agent",
            issued_at="2026-01-01T00:00:00Z",
            capabilities=["governance"],
        )
        data = p.to_json()
        p2 = LicensePayload.from_json(data)
        assert p2.token_id == "test-id"
        assert p2.agent_id == "test-agent"
        assert p2.capabilities == ["governance"]

    def test_payload_json_is_canonical(self):
        """JSON should be sorted and compact (no formatting whitespace)."""
        p = LicensePayload(agent_id="z-agent", issuer="TestIssuer")
        data = p.to_json()
        parsed = json.loads(data)
        keys = list(parsed.keys())
        assert keys == sorted(keys)  # sorted
        # Compact: no spaces around separators (values may contain spaces)
        assert b": " not in data
        assert b", " not in data

    def test_invalid_payload_json_raises(self):
        with pytest.raises(LicenseError, match="Invalid license payload"):
            LicensePayload.from_json(b"not json")


# =============================================================================
# File I/O
# =============================================================================

class TestFileIO:
    """Test token file operations."""

    def test_from_file_roundtrip(self, token_bytes):
        with tempfile.NamedTemporaryFile(suffix=".telos-license", delete=False) as f:
            f.write(token_bytes)
            f.flush()
            loaded = LicenseToken.from_file(f.name)
            assert loaded.agent_id == "property-intel-v2"
        os.unlink(f.name)

    def test_from_file_nonexistent_raises(self):
        with pytest.raises(LicenseError, match="Failed to read"):
            LicenseToken.from_file("/nonexistent/path.telos-license")

    def test_from_bytes_alias(self, token_bytes):
        token = LicenseToken.from_bytes(token_bytes)
        assert token.agent_id == "property-intel-v2"


# =============================================================================
# Review #14 fields (Schaake P0 + Benioff)
# =============================================================================

class TestReview14Fields:
    """Test new LicensePayload fields added in Review #14."""

    def test_bundle_id_roundtrip(self, labs_key, deploy_key, license_key):
        """bundle_id should survive build -> parse roundtrip."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        token_data = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
            bundle_id="bundle-abc-123",
        )
        token = LicenseToken(token_data)
        assert token.payload.bundle_id == "bundle-abc-123"

    def test_licensee_id_roundtrip(self, labs_key, deploy_key, license_key):
        """licensee_id should survive build -> parse roundtrip."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        token_data = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
            licensee_id="user-jane-doe",
        )
        token = LicenseToken(token_data)
        assert token.payload.licensee_id == "user-jane-doe"

    def test_licensee_org_roundtrip(self, labs_key, deploy_key, license_key):
        """licensee_org should survive build -> parse roundtrip."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        token_data = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
            licensee_org="Acme Insurance Corp",
        )
        token = LicenseToken(token_data)
        assert token.payload.licensee_org == "Acme Insurance Corp"

    def test_risk_classification_roundtrip(self, labs_key, deploy_key, license_key):
        """risk_classification should survive build -> parse roundtrip."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        token_data = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
            risk_classification="high_risk",
        )
        token = LicenseToken(token_data)
        assert token.payload.risk_classification == "high_risk"

    def test_all_review14_fields_roundtrip(self, labs_key, deploy_key, license_key):
        """All Review #14 fields should roundtrip together."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        token_data = builder.build(
            agent_id="property-intel-v2",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
            bundle_id="bundle-xyz-789",
            licensee_id="user-john-smith",
            licensee_org="BigInsure LLC",
            risk_classification="limited_risk",
        )
        token = LicenseToken(token_data)
        assert token.payload.bundle_id == "bundle-xyz-789"
        assert token.payload.licensee_id == "user-john-smith"
        assert token.payload.licensee_org == "BigInsure LLC"
        assert token.payload.risk_classification == "limited_risk"
        # Signature should still verify
        assert token.verify(labs_key.public_key_bytes) is True

    def test_review14_fields_default_empty(self, token_bytes):
        """Review #14 fields should default to empty string for old tokens."""
        token = LicenseToken(token_bytes)
        assert token.payload.bundle_id == ""
        assert token.payload.licensee_id == ""
        assert token.payload.licensee_org == ""
        assert token.payload.risk_classification == ""


# =============================================================================
# Grace period (Benioff Review #14)
# =============================================================================

class TestGracePeriod:
    """Test license token grace period behavior."""

    def test_grace_period_within_window(self, labs_key, deploy_key, license_key):
        """Token expired 3 days ago with 7-day grace period should pass with warning."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        token_data = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
            expires_in_days=10,
        )
        token = LicenseToken(token_data)
        # Simulate 13 days from now (3 days past expiry)
        future = datetime.now(timezone.utc) + timedelta(days=13)
        result = token.validate(now=future, grace_period_days=7)
        assert result is True
        assert len(token.warnings) == 1
        assert "grace period" in token.warnings[0].lower()

    def test_grace_period_expired(self, labs_key, deploy_key, license_key):
        """Token expired 10 days ago with 7-day grace period should raise."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        token_data = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
            expires_in_days=5,
        )
        token = LicenseToken(token_data)
        # Simulate 15 days from now (10 days past expiry)
        future = datetime.now(timezone.utc) + timedelta(days=15)
        with pytest.raises(LicenseError, match="grace period.*also expired"):
            token.validate(now=future, grace_period_days=7)

    def test_no_grace_period_expired_raises(self, labs_key, deploy_key, license_key):
        """Token expired with no grace period should raise immediately."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        token_data = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
            expires_in_days=5,
        )
        token = LicenseToken(token_data)
        future = datetime.now(timezone.utc) + timedelta(days=6)
        with pytest.raises(LicenseError, match="License expired"):
            token.validate(now=future, grace_period_days=0)

    def test_grace_period_not_yet_expired(self, labs_key, deploy_key, license_key):
        """Token not yet expired should pass with no warnings even with grace period set."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        token_data = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
            expires_in_days=365,
        )
        token = LicenseToken(token_data)
        result = token.validate(grace_period_days=14)
        assert result is True
        assert len(token.warnings) == 0

    def test_perpetual_token_ignores_grace_period(self, perpetual_token_bytes):
        """Perpetual token should pass regardless of grace period setting."""
        token = LicenseToken(perpetual_token_bytes)
        far_future = datetime.now(timezone.utc) + timedelta(days=36500)
        result = token.validate(now=far_future, grace_period_days=7)
        assert result is True
        assert len(token.warnings) == 0

    def test_warnings_reset_on_each_validate(self, labs_key, deploy_key, license_key):
        """Warnings should be cleared on each validate() call."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        token_data = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
            expires_in_days=10,
        )
        token = LicenseToken(token_data)
        # First call: in grace period
        future = datetime.now(timezone.utc) + timedelta(days=12)
        token.validate(now=future, grace_period_days=7)
        assert len(token.warnings) == 1
        # Second call: not expired
        token.validate()
        assert len(token.warnings) == 0


# =============================================================================
# Supplementary tests (Review #14 -- clock skew, key rotation, multi-token)
# =============================================================================

class TestSupplementaryScenarios:
    """Supplementary test scenarios from Review #14."""

    def test_clock_skew_tolerance(self, labs_key, deploy_key, license_key):
        """Token expiring in 30 seconds should still pass (no sub-minute precision)."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        token_data = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
            expires_in_days=1,
        )
        token = LicenseToken(token_data)
        # Validate ~23 hours 59 minutes from now (just before expiry)
        almost_expired = datetime.now(timezone.utc) + timedelta(hours=23, minutes=59)
        assert token.validate(now=almost_expired) is True

    def test_key_rotation_old_key_fails(self, deploy_key, license_key):
        """Token signed with old key should fail verification with new key."""
        old_key = SigningKeyPair.generate()
        new_key = SigningKeyPair.generate()
        builder = LicenseTokenBuilder(labs_key=old_key)
        token_data = builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=license_key,
        )
        token = LicenseToken(token_data)
        # Old key verifies
        assert token.verify(old_key.public_key_bytes) is True
        # New key does NOT verify
        with pytest.raises(LicenseError, match="signature verification failed"):
            token.verify(new_key.public_key_bytes)

    def test_multi_token_same_agent(self, labs_key, deploy_key, license_key):
        """Multiple tokens for the same agent should each have unique token_ids."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        tokens = []
        for _ in range(3):
            token_data = builder.build(
                agent_id="property-intel-v2",
                deployment_fingerprint=deploy_key.fingerprint,
                license_key=license_key,
            )
            tokens.append(LicenseToken(token_data))
        token_ids = [t.token_id for t in tokens]
        assert len(set(token_ids)) == 3  # All unique

    def test_different_license_keys_different_hashes(self, labs_key, deploy_key):
        """Different license keys should produce different key hashes in tokens."""
        builder = LicenseTokenBuilder(labs_key=labs_key)
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        t1 = LicenseToken(builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=key1,
        ))
        t2 = LicenseToken(builder.build(
            agent_id="test",
            deployment_fingerprint=deploy_key.fingerprint,
            license_key=key2,
        ))
        assert t1.payload.license_key_hash != t2.payload.license_key_hash

"""
Tests for telos_governance.bundle -- .telos bundle format.

Tests cover:
- Bundle building and reading (roundtrip)
- Manifest accessibility without decryption
- Signature verification (dual, labs-only)
- Decryption with correct/wrong key
- Content hash verification
- Bundle format validation (magic, version, truncation)
- AAD binding (agent_id)
- Tamper detection
"""

import os
import json
import struct
import pytest

from telos_governance.bundle import (
    BundleBuilder,
    BundleReader,
    BundleManifest,
    BundleError,
    BUNDLE_MAGIC,
    BUNDLE_VERSION,
    MAX_BUNDLE_SIZE,
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
def config_data():
    return b"""
purpose: "Help underwriters assess property risk"
scope: "Property intelligence and risk scoring"
boundaries:
  - name: "no_binding_decisions"
    description: "Do not make binding coverage decisions"
tools:
  - name: "roof_condition_score"
    description: "Get AI roof condition score"
"""

@pytest.fixture
def bundle_bytes(labs_key, deploy_key, license_key, config_data):
    builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
    return builder.build(
        config_data=config_data,
        license_key=license_key,
        agent_id="property-intel-v2",
        description="Test bundle",
        telos_version="1.5.0",
    )


# =============================================================================
# Bundle building
# =============================================================================

class TestBundleBuilding:
    """Test bundle construction."""

    def test_build_returns_bytes(self, labs_key, deploy_key, license_key, config_data):
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        result = builder.build(
            config_data=config_data,
            license_key=license_key,
            agent_id="test-agent",
        )
        assert isinstance(result, bytes)

    def test_bundle_starts_with_magic(self, bundle_bytes):
        assert bundle_bytes[:4] == BUNDLE_MAGIC

    def test_bundle_has_correct_version(self, bundle_bytes):
        version = struct.unpack(">H", bundle_bytes[4:6])[0]
        assert version == BUNDLE_VERSION

    def test_bundle_is_larger_than_config(self, bundle_bytes, config_data):
        # Bundle must be larger due to manifest + signatures + encryption overhead
        assert len(bundle_bytes) > len(config_data)

    def test_build_with_empty_config(self, labs_key, deploy_key, license_key):
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        result = builder.build(
            config_data=b"",
            license_key=license_key,
        )
        assert result[:4] == BUNDLE_MAGIC

    def test_encrypted_payload_no_plaintext_leakage(self, labs_key, deploy_key, license_key):
        """The encrypted payload must not contain the plaintext config data."""
        secret_config = b"SUPER_SECRET_BOUNDARY_CORPUS_DO_NOT_LEAK"
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        bundle = builder.build(
            config_data=secret_config,
            license_key=license_key,
            agent_id="leak-test",
        )
        # The plaintext should NOT appear anywhere in the raw bundle bytes
        # (it may appear in the manifest as a hash, but not as raw plaintext)
        assert secret_config not in bundle


# =============================================================================
# Bundle reading
# =============================================================================

class TestBundleReading:
    """Test bundle parsing and manifest access."""

    def test_reader_parses_bundle(self, bundle_bytes):
        reader = BundleReader(bundle_bytes)
        assert reader.manifest is not None

    def test_manifest_agent_id(self, bundle_bytes):
        reader = BundleReader(bundle_bytes)
        assert reader.manifest.agent_id == "property-intel-v2"

    def test_manifest_description(self, bundle_bytes):
        reader = BundleReader(bundle_bytes)
        assert reader.manifest.description == "Test bundle"

    def test_manifest_telos_version(self, bundle_bytes):
        reader = BundleReader(bundle_bytes)
        assert reader.manifest.telos_version == "1.5.0"

    def test_manifest_has_timestamps(self, bundle_bytes):
        reader = BundleReader(bundle_bytes)
        assert reader.manifest.created_at  # non-empty

    def test_manifest_has_fingerprints(self, bundle_bytes, labs_key, deploy_key):
        reader = BundleReader(bundle_bytes)
        assert reader.manifest.labs_fingerprint == labs_key.fingerprint
        assert reader.manifest.deployment_fingerprint == deploy_key.fingerprint

    def test_manifest_has_content_hash(self, bundle_bytes, config_data):
        import hashlib
        reader = BundleReader(bundle_bytes)
        expected_hash = hashlib.sha256(config_data).hexdigest()
        assert reader.manifest.content_hash == expected_hash

    def test_manifest_accessible_without_decryption(self, bundle_bytes):
        """Manifest should be readable without any keys."""
        reader = BundleReader(bundle_bytes)
        m = reader.manifest
        assert m.bundle_version == BUNDLE_VERSION
        assert m.agent_id == "property-intel-v2"


# =============================================================================
# Signature verification
# =============================================================================

class TestSignatureVerification:
    """Test dual and single signature verification."""

    def test_verify_dual_passes(self, bundle_bytes, labs_key, deploy_key):
        reader = BundleReader(bundle_bytes)
        assert reader.verify(labs_key.public_key_bytes, deploy_key.public_key_bytes) is True

    def test_verify_labs_only(self, bundle_bytes, labs_key):
        reader = BundleReader(bundle_bytes)
        assert reader.verify_labs(labs_key.public_key_bytes) is True

    def test_verify_wrong_labs_key_raises(self, bundle_bytes, deploy_key):
        wrong_key = SigningKeyPair.generate()
        reader = BundleReader(bundle_bytes)
        with pytest.raises(BundleError, match="signature verification failed"):
            reader.verify(wrong_key.public_key_bytes, deploy_key.public_key_bytes)

    def test_verify_wrong_deploy_key_raises(self, bundle_bytes, labs_key):
        wrong_key = SigningKeyPair.generate()
        reader = BundleReader(bundle_bytes)
        with pytest.raises(BundleError, match="signature verification failed"):
            reader.verify(labs_key.public_key_bytes, wrong_key.public_key_bytes)

    def test_verify_with_public_key_objects(self, bundle_bytes, labs_key, deploy_key):
        reader = BundleReader(bundle_bytes)
        assert reader.verify(labs_key.public_key, deploy_key.public_key) is True

    def test_signature_swap_fails_verification(self, bundle_bytes, labs_key, deploy_key):
        """Swapping labs and deploy signatures should fail verification."""
        reader = BundleReader(bundle_bytes)
        # Reconstruct bundle with swapped signatures
        data = bytearray(bundle_bytes)
        manifest_len = struct.unpack(">I", data[6:10])[0]
        sig_offset = 10 + manifest_len
        labs_sig = bytes(data[sig_offset:sig_offset + 64])
        deploy_sig = bytes(data[sig_offset + 64:sig_offset + 128])
        # Swap them
        data[sig_offset:sig_offset + 64] = deploy_sig
        data[sig_offset + 64:sig_offset + 128] = labs_sig
        swapped_reader = BundleReader(bytes(data))
        with pytest.raises(BundleError, match="signature verification failed"):
            swapped_reader.verify(labs_key.public_key_bytes, deploy_key.public_key_bytes)


# =============================================================================
# Decryption
# =============================================================================

class TestDecryption:
    """Test bundle decryption."""

    def test_decrypt_roundtrip(self, bundle_bytes, license_key, config_data):
        reader = BundleReader(bundle_bytes)
        decrypted = reader.decrypt(license_key)
        assert decrypted == config_data

    def test_wrong_license_key_raises(self, bundle_bytes):
        reader = BundleReader(bundle_bytes)
        wrong_key = os.urandom(32)
        with pytest.raises(BundleError, match="decryption failed"):
            reader.decrypt(wrong_key)

    def test_decrypt_empty_config(self, labs_key, deploy_key, license_key):
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        bundle = builder.build(config_data=b"", license_key=license_key)
        reader = BundleReader(bundle)
        assert reader.decrypt(license_key) == b""

    def test_decrypt_large_config(self, labs_key, deploy_key, license_key):
        large_config = os.urandom(100_000)  # 100KB
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        bundle = builder.build(config_data=large_config, license_key=license_key)
        reader = BundleReader(bundle)
        assert reader.decrypt(license_key) == large_config


# =============================================================================
# AAD binding
# =============================================================================

class TestAADBinding:
    """Test agent_id AAD binding."""

    def test_aad_binding_enforced(self, labs_key, deploy_key, license_key, config_data):
        """Config encrypted with agent_id AAD can't be decrypted if agent_id changes."""
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        bundle = builder.build(
            config_data=config_data,
            license_key=license_key,
            agent_id="agent-A",
            agent_id_as_aad=True,
        )
        # Positive path: correct AAD decrypts fine
        reader = BundleReader(bundle)
        assert reader.decrypt(license_key) == config_data

        # Negative path: tamper agent_id in manifest bytes (same length to avoid
        # breaking manifest_len). "agent-A" -> "agent-B" in the raw bundle.
        tampered = bundle.replace(b'"agent-A"', b'"agent-B"')
        assert tampered != bundle  # confirm we actually changed something
        tampered_reader = BundleReader(tampered)
        assert tampered_reader.manifest.agent_id == "agent-B"  # manifest changed
        with pytest.raises(BundleError, match="decryption failed"):
            tampered_reader.decrypt(license_key)  # AAD mismatch → GCM auth fails

    def test_no_aad_binding(self, labs_key, deploy_key, license_key, config_data):
        """Config encrypted without AAD should decrypt regardless of agent_id."""
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        bundle = builder.build(
            config_data=config_data,
            license_key=license_key,
            agent_id="test-agent",
            agent_id_as_aad=False,
        )
        reader = BundleReader(bundle)
        decrypted = reader.decrypt(license_key, agent_id_as_aad=False)
        assert decrypted == config_data


# =============================================================================
# Bundle format validation
# =============================================================================

class TestFormatValidation:
    """Test bundle format error handling."""

    def test_empty_data_raises(self):
        with pytest.raises(BundleError, match="too short"):
            BundleReader(b"")

    def test_wrong_magic_raises(self):
        with pytest.raises(BundleError, match="Invalid bundle magic"):
            BundleReader(b"FAKE" + b"\x00" * 100)

    def test_wrong_version_raises(self):
        data = BUNDLE_MAGIC + struct.pack(">H", 99) + b"\x00" * 100
        with pytest.raises(BundleError, match="Unsupported bundle version"):
            BundleReader(data)

    def test_truncated_bundle_raises(self):
        data = BUNDLE_MAGIC + struct.pack(">H", BUNDLE_VERSION) + struct.pack(">I", 1000)
        with pytest.raises(BundleError, match="truncated"):
            BundleReader(data)

    def test_oversized_bundle_raises(self):
        """Bundles exceeding MAX_BUNDLE_SIZE should be rejected (DoS protection)."""
        # We don't actually allocate 50MB -- just check that the size check fires
        # Create a minimal valid header pointing to a huge manifest
        data = BUNDLE_MAGIC + struct.pack(">H", BUNDLE_VERSION) + struct.pack(">I", 100)
        data += b"\x00" * (MAX_BUNDLE_SIZE + 1 - len(data))
        with pytest.raises(BundleError, match="too large"):
            BundleReader(data)


# =============================================================================
# Tamper detection
# =============================================================================

class TestTamperDetection:
    """Test that modifications to the bundle are detected."""

    def test_tampered_manifest_fails_verification(self, bundle_bytes, labs_key, deploy_key):
        """Modifying the manifest should break signature verification or parsing."""
        data = bytearray(bundle_bytes)
        # Manifest starts at offset 10 (after magic + version + manifest_len)
        # Tampering may break JSON parsing OR signature verification -- both count
        data[15] ^= 0xFF
        with pytest.raises(BundleError):
            reader = BundleReader(bytes(data))
            reader.verify(labs_key.public_key_bytes, deploy_key.public_key_bytes)

    def test_tampered_payload_fails_verification(self, bundle_bytes, labs_key, deploy_key):
        """Modifying the encrypted payload should break signature verification."""
        data = bytearray(bundle_bytes)
        data[-1] ^= 0xFF  # flip last byte (in encrypted payload)
        reader = BundleReader(bytes(data))
        with pytest.raises(BundleError):
            reader.verify(labs_key.public_key_bytes, deploy_key.public_key_bytes)

    def test_content_hash_mismatch_detected(self, labs_key, deploy_key, license_key):
        """If content_hash in manifest doesn't match decrypted content, error."""
        import hashlib
        # Build a valid bundle with no AAD (empty agent_id) for simpler testing
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        config = b"original config"
        bundle = builder.build(config_data=config, license_key=license_key, agent_id="")

        # Positive path works
        reader = BundleReader(bundle)
        assert reader.decrypt(license_key, agent_id_as_aad=False) == config

        # Negative path: tamper the content_hash in manifest to a wrong value.
        # Replace the real SHA-256 hex hash with a fake one (same length = 64 chars).
        real_hash = hashlib.sha256(config).hexdigest()
        fake_hash = "0" * 64
        assert real_hash != fake_hash
        tampered = bundle.replace(real_hash.encode(), fake_hash.encode())
        assert tampered != bundle
        tampered_reader = BundleReader(tampered)
        assert tampered_reader.manifest.content_hash == fake_hash
        with pytest.raises(BundleError, match="Content hash mismatch"):
            tampered_reader.decrypt(license_key, agent_id_as_aad=False)


# =============================================================================
# Manifest serialization
# =============================================================================

class TestManifestSerialization:
    """Test BundleManifest to/from JSON."""

    def test_manifest_roundtrip(self):
        m = BundleManifest(
            agent_id="test",
            created_at="2026-01-01T00:00:00Z",
            labs_fingerprint="abc123",
        )
        data = m.to_json()
        m2 = BundleManifest.from_json(data)
        assert m2.agent_id == "test"
        assert m2.labs_fingerprint == "abc123"

    def test_manifest_json_is_canonical(self):
        """JSON should be sorted and compact."""
        m = BundleManifest(agent_id="z-agent", description="a-desc")
        data = m.to_json()
        parsed = json.loads(data)
        keys = list(parsed.keys())
        assert keys == sorted(keys)  # sorted
        assert b" " not in data  # compact (no spaces)

    def test_invalid_manifest_json_raises(self):
        with pytest.raises(BundleError, match="Invalid manifest"):
            BundleManifest.from_json(b"not json")


# =============================================================================
# Regulatory manifest fields (Step 6.4 / Review #14)
# =============================================================================

class TestRegulatoryManifestFields:
    """Test Schaake's 7 regulatory manifest fields."""

    def test_bundle_id_auto_generated(self, labs_key, deploy_key, license_key, config_data):
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        bundle = builder.build(config_data=config_data, license_key=license_key)
        reader = BundleReader(bundle)
        assert reader.manifest.bundle_id  # non-empty UUID

    def test_bundle_id_custom(self, labs_key, deploy_key, license_key, config_data):
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        bundle = builder.build(
            config_data=config_data, license_key=license_key,
            bundle_id="custom-bundle-001",
        )
        reader = BundleReader(bundle)
        assert reader.manifest.bundle_id == "custom-bundle-001"

    def test_risk_classification(self, labs_key, deploy_key, license_key, config_data):
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        bundle = builder.build(
            config_data=config_data, license_key=license_key,
            risk_classification="high_risk",
        )
        reader = BundleReader(bundle)
        assert reader.manifest.risk_classification == "high_risk"

    def test_regulatory_jurisdiction(self, labs_key, deploy_key, license_key, config_data):
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        bundle = builder.build(
            config_data=config_data, license_key=license_key,
            regulatory_jurisdiction="CO_SB24-205,NAIC",
        )
        reader = BundleReader(bundle)
        assert reader.manifest.regulatory_jurisdiction == "CO_SB24-205,NAIC"

    def test_expires_at_and_effective_from(self, labs_key, deploy_key, license_key, config_data):
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        bundle = builder.build(
            config_data=config_data, license_key=license_key,
            effective_from="2026-03-01T00:00:00+00:00",
            expires_at="2027-03-01T00:00:00+00:00",
        )
        reader = BundleReader(bundle)
        assert reader.manifest.effective_from == "2026-03-01T00:00:00+00:00"
        assert reader.manifest.expires_at == "2027-03-01T00:00:00+00:00"

    def test_supersedes(self, labs_key, deploy_key, license_key, config_data):
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        bundle = builder.build(
            config_data=config_data, license_key=license_key,
            supersedes="old-bundle-id-123",
        )
        reader = BundleReader(bundle)
        assert reader.manifest.supersedes == "old-bundle-id-123"

    def test_all_regulatory_fields_roundtrip(self, labs_key, deploy_key, license_key, config_data):
        """All 7 new fields survive build/read roundtrip."""
        builder = BundleBuilder(labs_key=labs_key, deployment_key=deploy_key)
        bundle = builder.build(
            config_data=config_data, license_key=license_key,
            agent_id="test-agent",
            bundle_id="bid-001",
            risk_classification="limited_risk",
            regulatory_jurisdiction="EU_AI_ACT",
            effective_from="2026-01-01T00:00:00+00:00",
            expires_at="2027-01-01T00:00:00+00:00",
            supersedes="bid-000",
            boundary_ids="b1,b2,b3",
        )
        reader = BundleReader(bundle)
        m = reader.manifest
        assert m.bundle_id == "bid-001"
        assert m.risk_classification == "limited_risk"
        assert m.regulatory_jurisdiction == "EU_AI_ACT"
        assert m.effective_from == "2026-01-01T00:00:00+00:00"
        assert m.expires_at == "2027-01-01T00:00:00+00:00"
        assert m.supersedes == "bid-000"
        assert m.boundary_ids == "b1,b2,b3"
        # Decrypt still works
        assert reader.decrypt(license_key) == config_data

"""
Tests for telos_governance.bundle_pipeline -- one-command customer provisioning.

Tests cover:
- Full provisioning roundtrip (build → activate)
- Delivery directory structure
- License key permissions
- Token-bundle binding (agent_id, deployment fingerprint, license key hash)
- Delivery manifest contents
- Perpetual vs time-limited licenses
- Error handling (missing config, bad keys)
"""

import json
import os
import stat
import tempfile
import pytest
from pathlib import Path

from telos_governance.bundle_pipeline import (
    BundleProvisioner,
    ProvisioningResult,
    ProvisioningError,
)
from telos_governance.bundle import BundleReader
from telos_governance.licensing import LicenseToken
from telos_governance.signing import SigningKeyPair


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def labs_key():
    return SigningKeyPair.generate()


@pytest.fixture
def config_file():
    """Temporary YAML config file."""
    content = b"""
agent_name: Test Agent
agent_id: test-agent-v1
purpose: Test governance configuration
scope: Testing only
boundaries:
  - text: Do not make autonomous decisions
    severity: hard
tools:
  - name: test_tool
    description: A test tool
example_requests:
  - Test request one
"""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        f.write(content)
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def output_dir():
    """Temporary output directory."""
    with tempfile.TemporaryDirectory() as d:
        yield d


# =============================================================================
# Full provisioning
# =============================================================================

class TestProvisioning:
    """Test the complete provisioning workflow."""

    def test_provision_creates_all_files(self, labs_key, config_file, output_dir):
        """Provisioning should create all 6 delivery artifacts."""
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            agent_id="test-agent",
        )
        assert Path(result.bundle_path).exists()
        assert Path(result.token_path).exists()
        assert Path(result.license_key_path).exists()
        assert Path(result.deploy_pub_path).exists()
        assert Path(result.labs_pub_path).exists()
        assert Path(result.manifest_path).exists()

    def test_provision_file_names(self, labs_key, config_file, output_dir):
        """Files should be named after the agent_id."""
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            agent_id="property-intel",
        )
        assert Path(result.bundle_path).name == "property-intel.telos"
        assert Path(result.token_path).name == "property-intel.telos-license"

    def test_provision_roundtrip(self, labs_key, config_file, output_dir):
        """Provisioned bundle should decrypt with the provisioned license key."""
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            agent_id="test-agent",
        )
        # Read bundle
        bundle_data = Path(result.bundle_path).read_bytes()
        reader = BundleReader(bundle_data)
        # Read license key
        license_key = Path(result.license_key_path).read_bytes()
        # Decrypt
        plaintext = reader.decrypt(license_key)
        # Should match original config
        original = Path(config_file).read_bytes()
        assert plaintext == original

    def test_provision_signature_verifies(self, labs_key, config_file, output_dir):
        """Provisioned bundle should verify with Labs + deployment keys."""
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            agent_id="test-agent",
        )
        bundle_data = Path(result.bundle_path).read_bytes()
        reader = BundleReader(bundle_data)
        deploy_pub = Path(result.deploy_pub_path).read_bytes()
        labs_pub = Path(result.labs_pub_path).read_bytes()
        assert reader.verify(labs_pub, deploy_pub) is True

    def test_provision_token_verifies(self, labs_key, config_file, output_dir):
        """Provisioned token should verify with Labs public key."""
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            agent_id="test-agent",
        )
        token_data = Path(result.token_path).read_bytes()
        token = LicenseToken(token_data)
        labs_pub = Path(result.labs_pub_path).read_bytes()
        assert token.verify(labs_pub) is True

    def test_provision_token_validates_with_key(self, labs_key, config_file, output_dir):
        """Token should validate against the provisioned license key."""
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            agent_id="test-agent",
        )
        token_data = Path(result.token_path).read_bytes()
        token = LicenseToken(token_data)
        license_key = Path(result.license_key_path).read_bytes()
        assert token.validate(
            license_key=license_key,
            agent_id="test-agent",
            deployment_fingerprint=result.deployment_fingerprint,
        ) is True


# =============================================================================
# Token-bundle binding
# =============================================================================

class TestTokenBundleBinding:
    """Test that token and bundle are correctly bound together."""

    def test_bundle_id_matches(self, labs_key, config_file, output_dir):
        """Token's bundle_id should match the bundle manifest's bundle_id."""
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            agent_id="test-agent",
        )
        bundle_data = Path(result.bundle_path).read_bytes()
        reader = BundleReader(bundle_data)
        token_data = Path(result.token_path).read_bytes()
        token = LicenseToken(token_data)
        assert token.payload.bundle_id == reader.manifest.bundle_id
        assert token.payload.bundle_id == result.bundle_id

    def test_agent_id_matches(self, labs_key, config_file, output_dir):
        """Token and bundle should have the same agent_id."""
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            agent_id="property-intel-v2",
        )
        bundle_data = Path(result.bundle_path).read_bytes()
        reader = BundleReader(bundle_data)
        token_data = Path(result.token_path).read_bytes()
        token = LicenseToken(token_data)
        assert reader.manifest.agent_id == "property-intel-v2"
        assert token.agent_id == "property-intel-v2"

    def test_deployment_fingerprint_matches(self, labs_key, config_file, output_dir):
        """Token's deployment fingerprint should match the bundle's."""
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            agent_id="test-agent",
        )
        bundle_data = Path(result.bundle_path).read_bytes()
        reader = BundleReader(bundle_data)
        token_data = Path(result.token_path).read_bytes()
        token = LicenseToken(token_data)
        assert token.payload.deployment_fingerprint == reader.manifest.deployment_fingerprint


# =============================================================================
# Delivery manifest
# =============================================================================

class TestDeliveryManifest:
    """Test the DELIVERY_MANIFEST.json contents."""

    def test_manifest_is_valid_json(self, labs_key, config_file, output_dir):
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            agent_id="test-agent",
        )
        manifest = json.loads(Path(result.manifest_path).read_text())
        assert isinstance(manifest, dict)

    def test_manifest_contains_metadata(self, labs_key, config_file, output_dir):
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            agent_id="test-agent",
            licensee_org="TestCorp",
            risk_classification="high_risk",
        )
        manifest = json.loads(Path(result.manifest_path).read_text())
        assert manifest["agent_id"] == "test-agent"
        assert manifest["licensee_org"] == "TestCorp"
        assert manifest["risk_classification"] == "high_risk"
        assert "provisioned_at" in manifest
        assert "bundle_id" in manifest
        assert "delivery_note" in manifest

    def test_manifest_security_note(self, labs_key, config_file, output_dir):
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
        )
        manifest = json.loads(Path(result.manifest_path).read_text())
        assert "out-of-band" in manifest["delivery_note"]


# =============================================================================
# License key security
# =============================================================================

class TestLicenseKeySecurity:
    """Test license key file permissions and properties."""

    def test_license_key_is_32_bytes(self, labs_key, config_file, output_dir):
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
        )
        key = Path(result.license_key_path).read_bytes()
        assert len(key) == 32

    def test_license_key_restricted_permissions(self, labs_key, config_file, output_dir):
        """License key file should have 0o600 permissions (owner only)."""
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
        )
        mode = os.stat(result.license_key_path).st_mode
        assert stat.S_IMODE(mode) == 0o600

    def test_license_keys_unique_per_provision(self, labs_key, config_file, output_dir):
        """Two provisions should produce different license keys."""
        provisioner = BundleProvisioner(labs_key=labs_key)
        dir1 = os.path.join(output_dir, "d1")
        dir2 = os.path.join(output_dir, "d2")
        provisioner.provision(config_path=config_file, output_dir=dir1)
        provisioner.provision(config_path=config_file, output_dir=dir2)
        key1 = Path(dir1, "license.key").read_bytes()
        key2 = Path(dir2, "license.key").read_bytes()
        assert key1 != key2


# =============================================================================
# License options
# =============================================================================

class TestLicenseOptions:
    """Test perpetual vs time-limited provisioning."""

    def test_perpetual_license(self, labs_key, config_file, output_dir):
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            expires_in_days=None,
        )
        token = LicenseToken(Path(result.token_path).read_bytes())
        assert token.is_perpetual

    def test_time_limited_license(self, labs_key, config_file, output_dir):
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            expires_in_days=90,
        )
        token = LicenseToken(Path(result.token_path).read_bytes())
        assert not token.is_perpetual
        assert result.expires_in_days == 90

    def test_licensee_fields_in_token(self, labs_key, config_file, output_dir):
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            licensee_id="jane@acme.com",
            licensee_org="Acme Insurance",
            risk_classification="high_risk",
        )
        token = LicenseToken(Path(result.token_path).read_bytes())
        assert token.payload.licensee_id == "jane@acme.com"
        assert token.payload.licensee_org == "Acme Insurance"
        assert token.payload.risk_classification == "high_risk"


# =============================================================================
# Error handling
# =============================================================================

class TestErrorHandling:
    """Test provisioning error cases."""

    def test_missing_config_raises(self, labs_key, output_dir):
        provisioner = BundleProvisioner(labs_key=labs_key)
        with pytest.raises(ProvisioningError, match="Config file not found"):
            provisioner.provision(
                config_path="/nonexistent/config.yaml",
                output_dir=output_dir,
            )

    def test_result_dataclass_fields(self, labs_key, config_file, output_dir):
        """ProvisioningResult should expose all expected fields."""
        provisioner = BundleProvisioner(labs_key=labs_key)
        result = provisioner.provision(
            config_path=config_file,
            output_dir=output_dir,
            agent_id="test",
        )
        assert isinstance(result, ProvisioningResult)
        assert result.agent_id == "test"
        assert result.bundle_id  # non-empty UUID
        assert result.deployment_fingerprint  # non-empty hex
        assert result.labs_fingerprint  # non-empty hex

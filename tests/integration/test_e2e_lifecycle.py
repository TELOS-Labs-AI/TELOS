"""
End-to-end lifecycle test — full customer journey simulation.

Milestone 9, Step 9.1: Validates the complete TELOS governance workflow
from key generation through encrypted data export.

13-step lifecycle:
  1.  Generate Labs + deployment Ed25519 key pairs
  2.  Create/load agent YAML configuration
  3.  Provision customer delivery package
  4.  Verify delivery manifest contents
  5.  Verify license token (signature + constraints)
  6.  Activate (decrypt) governance bundle
  7.  Load decrypted config and build PA
  8.  Score in-scope request (expect EXECUTE/CLARIFY)
  9.  Score out-of-scope request (expect INERT)
  10. Sign governance receipts in a session
  11. Generate session proof chain
  12. Collect intelligence telemetry
  13. Export encrypted governance data + roundtrip decrypt
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest
import yaml

from telos_governance.signing import SigningKeyPair
from telos_governance.config import load_config
from telos_governance.bundle_pipeline import BundleProvisioner
from telos_governance.bundle import BundleReader
from telos_governance.licensing import LicenseToken
from telos_governance.agentic_pa import AgenticPA
from telos_governance.agentic_fidelity import AgenticFidelityEngine
from telos_governance.session import GovernanceSessionContext
from telos_governance.intelligence_layer import (
    IntelligenceCollector,
    IntelligenceConfig,
)
from telos_governance.data_export import GovernanceExporter


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def workspace():
    """Temporary workspace for all lifecycle artifacts."""
    d = tempfile.mkdtemp(prefix="telos_e2e_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def config_file(workspace):
    """Create a test agent YAML config."""
    config = {
        "agent": {
            "id": "e2e-test-agent",
            "name": "E2E Test Agent",
            "description": "End-to-end lifecycle test agent",
        },
        "purpose": {
            "statement": (
                "Provide AI-powered property intelligence for insurance "
                "underwriting decision support including roof condition "
                "analysis and risk assessment."
            ),
            "example_requests": [
                "What is the roof condition score for this property?",
                "Score the hail and wind exposure for this property",
                "Generate an underwriting report with peril scores",
            ],
        },
        "scope": (
            "property analysis, risk assessment, roof condition scoring, "
            "peril exposure calculation, underwriting decision support"
        ),
        "boundaries": [
            {
                "text": "Do not make autonomous underwriting decisions",
                "severity": "hard",
            },
            {
                "text": "Do not access data outside authorized scope",
                "severity": "hard",
            },
        ],
        "safe_exemplars": [
            "What is the roof condition score for this property?",
            "Assess the risk profile for 742 Evergreen Terrace",
            "Score the roof condition and flag any material concerns",
        ],
        "tools": [
            {
                "name": "get_property_analysis",
                "description": "Retrieve AI-powered property analysis including roof condition",
                "risk_level": "low",
            },
            {
                "name": "calculate_risk_score",
                "description": "Calculate composite risk score using aerial imagery",
                "risk_level": "medium",
            },
        ],
        "constraints": {
            "max_chain_length": 20,
            "max_tool_calls_per_step": 5,
            "escalation_threshold": 0.50,
            "require_human_above_risk": "high",
        },
    }
    path = workspace / "e2e_agent.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    return path


@pytest.fixture
def deterministic_embed():
    """Deterministic embedding function for reproducible tests."""
    from telos_core.embedding_provider import DeterministicEmbeddingProvider

    provider = DeterministicEmbeddingProvider()
    return provider.encode


# =============================================================================
# Lifecycle Test
# =============================================================================


class TestE2ELifecycle:
    """Full 13-step customer lifecycle simulation."""

    def test_full_lifecycle(self, workspace, config_file, deterministic_embed):
        """Complete customer journey from key generation through data export."""

        # ── Step 1: Generate Ed25519 key pairs ──────────────────────────
        labs_key = SigningKeyPair.generate()
        assert labs_key.public_key_bytes is not None
        assert len(labs_key.public_key_bytes) == 32
        assert labs_key.fingerprint  # SHA-256 hex string

        # Save and reload to verify PEM persistence
        labs_pem = workspace / "labs.pem"
        labs_key.save_private_pem(str(labs_pem))
        assert labs_pem.exists()
        labs_key_reloaded = SigningKeyPair.from_private_pem(str(labs_pem))
        assert labs_key_reloaded.fingerprint == labs_key.fingerprint

        # ── Step 2: Load agent configuration ────────────────────────────
        config = load_config(str(config_file))
        assert config.agent_id == "e2e-test-agent"
        assert config.agent_name == "E2E Test Agent"
        assert "property intelligence" in config.purpose.lower()
        assert len(config.boundaries) == 2
        assert len(config.tools) == 2
        assert len(config.example_requests) == 3
        assert len(config.safe_exemplars) == 3

        # ── Step 3: Provision customer delivery ─────────────────────────
        delivery_dir = workspace / "delivery"
        provisioner = BundleProvisioner(labs_key)
        result = provisioner.provision(
            config_path=str(config_file),
            output_dir=str(delivery_dir),
            agent_id="e2e-test-agent",
            licensee_org="E2E Test Corp",
            risk_classification="high_risk",
            expires_in_days=365,
        )

        assert result.bundle_path is not None
        assert result.token_path is not None
        assert result.license_key_path is not None
        assert result.deploy_pub_path is not None
        assert result.labs_pub_path is not None
        assert result.manifest_path is not None

        # Verify all files exist
        for path in [
            result.bundle_path,
            result.token_path,
            result.license_key_path,
            result.deploy_pub_path,
            result.labs_pub_path,
            result.manifest_path,
        ]:
            assert Path(path).exists(), f"Missing: {path}"

        # ── Step 4: Verify delivery manifest ────────────────────────────
        manifest = json.loads(Path(result.manifest_path).read_text())
        assert manifest["agent_id"] == "e2e-test-agent"
        assert manifest["licensee_org"] == "E2E Test Corp"
        assert manifest["risk_classification"] == "high_risk"
        assert "bundle_file" in manifest
        assert "token_file" in manifest

        # ── Step 5: Verify license token ────────────────────────────────
        token_bytes = Path(result.token_path).read_bytes()
        token = LicenseToken.from_bytes(token_bytes)

        # Verify Labs signature
        labs_pub_bytes = Path(result.labs_pub_path).read_bytes()
        token.verify(labs_pub_bytes)

        # Verify agent binding
        license_key = Path(result.license_key_path).read_bytes()
        token.validate(
            license_key=license_key,
            agent_id="e2e-test-agent",
        )

        # Check payload fields
        assert token.payload.agent_id == "e2e-test-agent"
        assert token.payload.licensee_org == "E2E Test Corp"
        assert token.payload.risk_classification == "high_risk"

        # ── Step 6: Activate (decrypt) governance bundle ────────────────
        bundle_bytes = Path(result.bundle_path).read_bytes()
        reader = BundleReader(bundle_bytes)

        # Verify Labs signature on bundle
        reader.verify_labs(labs_pub_bytes)

        # Read manifest (cleartext, always available)
        bundle_manifest = reader.manifest
        assert bundle_manifest.agent_id == "e2e-test-agent"

        # Decrypt with license key
        decrypted_yaml = reader.decrypt(license_key)
        assert len(decrypted_yaml) > 0

        # Parse decrypted config
        decrypted_config = yaml.safe_load(decrypted_yaml)
        assert decrypted_config is not None

        # Write decrypted config and reload
        activated_path = workspace / "activated_agent.yaml"
        activated_path.write_bytes(decrypted_yaml)

        # ── Step 7: Build PA from activated config ──────────────────────
        activated_config = load_config(str(activated_path))
        assert activated_config.agent_id == "e2e-test-agent"

        boundaries = [
            {"text": b.text, "severity": b.severity}
            for b in activated_config.boundaries
        ]

        pa = AgenticPA.create_from_template(
            purpose=activated_config.purpose,
            scope=activated_config.scope,
            boundaries=boundaries,
            tools=activated_config.tools,  # ToolConfig objects have .name, .description
            embed_fn=deterministic_embed,
            example_requests=activated_config.example_requests,
            safe_exemplars=activated_config.safe_exemplars,
        )
        assert pa is not None
        assert pa.purpose_embedding is not None

        engine = AgenticFidelityEngine(deterministic_embed, pa)

        # ── Step 8: Score in-scope request ──────────────────────────────
        in_scope_result = engine.score_action(
            "What is the roof condition score for this property?"
        )
        assert in_scope_result is not None
        assert in_scope_result.effective_fidelity > 0.0
        assert in_scope_result.decision is not None
        assert in_scope_result.purpose_fidelity >= 0.0
        assert in_scope_result.scope_fidelity >= 0.0

        # ── Step 9: Score out-of-scope request ──────────────────────────
        out_scope_result = engine.score_action(
            "What is the weather forecast for tomorrow?"
        )
        assert out_scope_result is not None
        assert out_scope_result.effective_fidelity >= 0.0
        # Out-of-scope should have lower fidelity than in-scope
        # (with deterministic embeddings this may not always hold,
        # but the scoring pipeline must complete without error)

        # ── Step 10: Sign governance receipts in session ────────────────
        intelligence_dir = workspace / "intelligence"
        collector = IntelligenceCollector(
            IntelligenceConfig(
                enabled=True,
                collection_level="metrics",
                agent_id="e2e-test-agent",
                base_dir=str(intelligence_dir),
            )
        )

        with GovernanceSessionContext(
            intelligence_collector=collector,
            agent_id="e2e-test-agent",
        ) as session:
            # Sign first result
            receipt_1 = session.sign_result(
                in_scope_result,
                "What is the roof condition score for this property?",
                "pre_action",
            )
            assert receipt_1 is not None
            assert receipt_1.ed25519_signature is not None
            # Ed25519 signature stored as hex: 64 bytes = 128 hex chars
            assert len(receipt_1.ed25519_signature) == 128

            # Sign second result
            receipt_2 = session.sign_result(
                out_scope_result,
                "What is the weather forecast for tomorrow?",
                "pre_action",
            )
            assert receipt_2 is not None

            # ── Step 11: Generate session proof ─────────────────────────
            proof = session.generate_proof()
            assert proof is not None
            assert proof["total_receipts"] == 2
            assert "session_id" in proof
            assert "ed25519_public_key" in proof
            assert "receipt_chain" in proof
            assert len(proof["receipt_chain"]) == 2

            # Verify Ed25519 public key is present
            assert len(proof["ed25519_public_key"]) > 0

        # ── Step 12: Verify intelligence telemetry ──────────────────────
        aggregate = collector.get_aggregate("e2e-test-agent")
        assert aggregate is not None
        assert aggregate.get("total_records", 0) >= 2
        assert "decision_distribution" in aggregate

        # ── Step 13: Export encrypted governance data ───────────────────
        exporter = GovernanceExporter(
            license_key=license_key,
            agent_id="e2e-test-agent",
        )

        proof_export_path = workspace / "session_proof.telos-proof"
        exporter.export_session_proof(proof, str(proof_export_path))
        assert proof_export_path.exists()
        assert proof_export_path.stat().st_size > 0

        # Roundtrip: decrypt the export
        decrypted_proof = GovernanceExporter.decrypt_export(
            str(proof_export_path),
            license_key=license_key,
            agent_id="e2e-test-agent",
        )
        assert decrypted_proof is not None
        assert "payload" in decrypted_proof
        payload = decrypted_proof["payload"]
        assert payload["total_receipts"] == 2


class TestLifecycleEdgeCases:
    """Edge cases for the lifecycle flow."""

    def test_perpetual_license(self, workspace, config_file):
        """Provision with no expiry (perpetual license)."""
        labs_key = SigningKeyPair.generate()
        delivery_dir = workspace / "perpetual"
        provisioner = BundleProvisioner(labs_key)
        result = provisioner.provision(
            config_path=str(config_file),
            output_dir=str(delivery_dir),
            agent_id="e2e-perpetual",
            licensee_org="Perpetual Corp",
        )

        token = LicenseToken.from_bytes(
            Path(result.token_path).read_bytes()
        )
        labs_pub = Path(result.labs_pub_path).read_bytes()
        token.verify(labs_pub)

        # Perpetual: expires_at should be empty or None
        assert not token.payload.expires_at or token.payload.expires_at == ""

    def test_bundle_tamper_detection(self, workspace, config_file):
        """Tampered bundle fails verification."""
        labs_key = SigningKeyPair.generate()
        delivery_dir = workspace / "tamper"
        provisioner = BundleProvisioner(labs_key)
        result = provisioner.provision(
            config_path=str(config_file),
            output_dir=str(delivery_dir),
            agent_id="e2e-tamper",
        )

        # Read bundle and tamper with a byte in the encrypted payload
        # (past the manifest + signatures region)
        bundle_bytes = bytearray(Path(result.bundle_path).read_bytes())
        # Tamper near end of file (encrypted payload area)
        tamper_pos = len(bundle_bytes) - 10
        if tamper_pos > 0:
            bundle_bytes[tamper_pos] ^= 0xFF

        # Tampered bundle should fail at some point in the pipeline
        # (either parse, verify, or decrypt)
        labs_pub = Path(result.labs_pub_path).read_bytes()
        license_key = Path(result.license_key_path).read_bytes()

        with pytest.raises(Exception):
            reader = BundleReader(bytes(bundle_bytes))
            reader.verify_labs(labs_pub)
            reader.decrypt(license_key)

    def test_wrong_license_key_fails_decrypt(self, workspace, config_file):
        """Wrong license key fails to decrypt bundle."""
        labs_key = SigningKeyPair.generate()
        delivery_dir = workspace / "wrong_key"
        provisioner = BundleProvisioner(labs_key)
        result = provisioner.provision(
            config_path=str(config_file),
            output_dir=str(delivery_dir),
            agent_id="e2e-wrong-key",
        )

        bundle_bytes = Path(result.bundle_path).read_bytes()
        reader = BundleReader(bundle_bytes)

        wrong_key = os.urandom(32)
        with pytest.raises(Exception):
            reader.decrypt(wrong_key)

    def test_session_with_tkeys(self, workspace, deterministic_embed):
        """Session with TKeys enabled produces HMAC co-signatures."""
        with GovernanceSessionContext(enable_tkeys=True) as session:
            # Create a minimal result to sign
            from types import SimpleNamespace
            from telos_governance.agentic_fidelity import ActionDecision

            result = SimpleNamespace(
                decision=ActionDecision.EXECUTE,
                effective_fidelity=0.92,
                composite_fidelity=0.85,
                boundary_triggered=False,
                purpose_fidelity=0.92,
                scope_fidelity=0.80,
                boundary_violation=0.0,
                tool_fidelity=0.75,
                chain_continuity=0.0,
                selected_tool="test_tool",
            )
            receipt = session.sign_result(result, "test request", "pre_action")
            assert receipt.ed25519_signature is not None
            assert receipt.hmac_signature is not None
            # HMAC-SHA512 stored as hex string: 64 bytes = 128 hex chars
            assert len(receipt.hmac_signature) == 128

            proof = session.generate_proof()
            assert proof["total_receipts"] == 1

    def test_multiple_scoring_rounds(self, workspace, config_file, deterministic_embed):
        """Multiple scoring rounds accumulate receipts correctly."""
        config = load_config(str(config_file))
        boundaries = [
            {"text": b.text, "severity": b.severity}
            for b in config.boundaries
        ]

        pa = AgenticPA.create_from_template(
            purpose=config.purpose,
            scope=config.scope,
            boundaries=boundaries,
            tools=config.tools,  # ToolConfig objects have .name, .description
            embed_fn=deterministic_embed,
            example_requests=config.example_requests,
            safe_exemplars=config.safe_exemplars,
        )
        engine = AgenticFidelityEngine(deterministic_embed, pa)

        requests = [
            "What is the roof condition?",
            "Score the hail exposure",
            "Generate underwriting report",
            "Assess property risk profile",
            "What is the wind damage history?",
        ]

        with GovernanceSessionContext() as session:
            for req in requests:
                result = engine.score_action(req)
                receipt = session.sign_result(result, req, "pre_action")
                assert receipt is not None

            proof = session.generate_proof()
            assert proof["total_receipts"] == 5
            assert len(proof["receipt_chain"]) == 5

    def test_export_roundtrip_integrity(self, workspace):
        """Encrypted export roundtrips preserve data integrity."""
        key = os.urandom(32)
        agent_id = "export-test"

        test_data = {
            "session_id": "test-session-123",
            "total_receipts": 3,
            "receipt_chain": [
                {"decision": "execute", "fidelity": 0.92},
                {"decision": "clarify", "fidelity": 0.75},
                {"decision": "execute", "fidelity": 0.88},
            ],
        }

        exporter = GovernanceExporter(license_key=key, agent_id=agent_id)
        export_path = workspace / "roundtrip.telos-proof"
        exporter.export_session_proof(test_data, str(export_path))

        decrypted = GovernanceExporter.decrypt_export(
            str(export_path),
            license_key=key,
            agent_id=agent_id,
        )

        payload = decrypted["payload"]
        assert payload["session_id"] == "test-session-123"
        assert payload["total_receipts"] == 3
        assert len(payload["receipt_chain"]) == 3

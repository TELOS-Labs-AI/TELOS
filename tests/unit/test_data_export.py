"""
Tests for telos_governance.data_export
========================================

Tests for GovernanceExporter: encrypted governance data export/import.
Verifies round-trip, AAD binding, tamper detection, and format validation.
"""

import json
import secrets
import time

import pytest

from telos_governance.data_export import (
    GovernanceExporter,
    ExportError,
    _EXPORT_VERSION,
    _MODE_LICENSE,
)
from telos_governance.receipt_signer import GovernanceReceipt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def license_key():
    return secrets.token_bytes(32)

@pytest.fixture
def exporter(license_key):
    return GovernanceExporter(license_key)

@pytest.fixture
def exporter_with_agent(license_key):
    return GovernanceExporter(license_key, agent_id="nearmap-v1")

@pytest.fixture
def sample_proof():
    return {
        "session_id": "telos-abc123",
        "total_receipts": 3,
        "ed25519_public_key": "deadbeef" * 8,
        "receipt_chain": [
            {"decision": "execute", "fidelity": 0.85},
            {"decision": "clarify", "fidelity": 0.72},
            {"decision": "execute", "fidelity": 0.88},
        ],
    }

@pytest.fixture
def sample_receipts():
    return [
        GovernanceReceipt(
            decision_point="pre_action",
            action_text="Assess roof condition",
            decision="execute",
            effective_fidelity=0.80,
            composite_fidelity=0.82,
            boundary_triggered=False,
            tool_name="property_analysis",
            timestamp=1707900000.0,
            purpose_fidelity=0.85,
            scope_fidelity=0.78,
            boundary_violation=0.10,
            tool_fidelity=0.90,
            chain_continuity=0.95,
        ),
    ]


# ---------------------------------------------------------------------------
# Session proof export/import
# ---------------------------------------------------------------------------

class TestSessionProofExport:
    def test_export_round_trip(self, exporter, sample_proof, tmp_path):
        out = tmp_path / "proof.telos-proof"
        exporter.export_session_proof(sample_proof, out)
        assert out.exists()

        data = GovernanceExporter.decrypt_export(out, exporter._license_key)
        assert data["data_type"] == "session_proof"
        assert data["payload"]["session_id"] == "telos-abc123"
        assert data["payload"]["total_receipts"] == 3

    def test_export_with_agent_id(self, exporter_with_agent, sample_proof, tmp_path):
        out = tmp_path / "proof.telos-proof"
        exporter_with_agent.export_session_proof(sample_proof, out)

        data = GovernanceExporter.decrypt_export(
            out, exporter_with_agent._license_key, agent_id="nearmap-v1"
        )
        assert data["agent_id"] == "nearmap-v1"

    def test_agent_id_mismatch_fails(self, exporter_with_agent, sample_proof, tmp_path):
        out = tmp_path / "proof.telos-proof"
        exporter_with_agent.export_session_proof(sample_proof, out)

        with pytest.raises(ExportError, match="Decryption failed"):
            GovernanceExporter.decrypt_export(
                out, exporter_with_agent._license_key, agent_id="wrong-agent"
            )


# ---------------------------------------------------------------------------
# Benchmark results export/import
# ---------------------------------------------------------------------------

class TestBenchmarkExport:
    def test_export_round_trip(self, exporter, tmp_path):
        results = {"accuracy": 0.817, "scenarios": 173, "timestamp": time.time()}
        out = tmp_path / "benchmark.telos-export"
        exporter.export_benchmark_results(results, out)

        data = GovernanceExporter.decrypt_export(out, exporter._license_key)
        assert data["data_type"] == "benchmark_results"
        assert data["payload"]["accuracy"] == 0.817


# ---------------------------------------------------------------------------
# Receipt export/import
# ---------------------------------------------------------------------------

class TestReceiptExport:
    def test_export_round_trip(self, exporter, sample_receipts, tmp_path):
        out = tmp_path / "receipts.telos-export"
        exporter.export_receipts(sample_receipts, out)

        data = GovernanceExporter.decrypt_export(out, exporter._license_key)
        assert data["data_type"] == "receipts"
        assert data["payload"]["count"] == 1
        assert data["payload"]["receipts"][0]["decision"] == "execute"


# ---------------------------------------------------------------------------
# Decryption failures
# ---------------------------------------------------------------------------

class TestDecryptionFailures:
    def test_wrong_key_fails(self, exporter, sample_proof, tmp_path):
        out = tmp_path / "proof.telos-proof"
        exporter.export_session_proof(sample_proof, out)

        wrong_key = secrets.token_bytes(32)
        with pytest.raises(ExportError, match="Decryption failed"):
            GovernanceExporter.decrypt_export(out, wrong_key)

    def test_truncated_file_fails(self, tmp_path):
        out = tmp_path / "bad.telos-proof"
        out.write_bytes(b"\x01\x01short")
        with pytest.raises(ExportError, match="too short"):
            GovernanceExporter.decrypt_export(out, secrets.token_bytes(32))

    def test_bad_version_fails(self, exporter, sample_proof, tmp_path):
        out = tmp_path / "proof.telos-proof"
        exporter.export_session_proof(sample_proof, out)

        raw = bytearray(out.read_bytes())
        raw[0] = 0x99  # Invalid version
        out.write_bytes(bytes(raw))

        with pytest.raises(ExportError, match="Unsupported export version"):
            GovernanceExporter.decrypt_export(out, exporter._license_key)

    def test_bad_mode_fails(self, exporter, sample_proof, tmp_path):
        out = tmp_path / "proof.telos-proof"
        exporter.export_session_proof(sample_proof, out)

        raw = bytearray(out.read_bytes())
        raw[1] = 0x99  # Invalid mode
        out.write_bytes(bytes(raw))

        with pytest.raises(ExportError, match="Unsupported encryption mode"):
            GovernanceExporter.decrypt_export(out, exporter._license_key)

    def test_tampered_payload_fails(self, exporter, sample_proof, tmp_path):
        out = tmp_path / "proof.telos-proof"
        exporter.export_session_proof(sample_proof, out)

        raw = bytearray(out.read_bytes())
        raw[-10] ^= 0xFF  # Flip a byte in ciphertext
        out.write_bytes(bytes(raw))

        with pytest.raises(ExportError, match="Decryption failed"):
            GovernanceExporter.decrypt_export(out, exporter._license_key)


# ---------------------------------------------------------------------------
# Export format
# ---------------------------------------------------------------------------

class TestExportFormat:
    def test_file_starts_with_version(self, exporter, sample_proof, tmp_path):
        out = tmp_path / "proof.telos-proof"
        exporter.export_session_proof(sample_proof, out)
        raw = out.read_bytes()
        assert raw[0:1] == _EXPORT_VERSION

    def test_file_has_license_mode(self, exporter, sample_proof, tmp_path):
        out = tmp_path / "proof.telos-proof"
        exporter.export_session_proof(sample_proof, out)
        raw = out.read_bytes()
        assert raw[1:2] == _MODE_LICENSE

    def test_envelope_metadata(self, exporter, sample_proof, tmp_path):
        out = tmp_path / "proof.telos-proof"
        exporter.export_session_proof(sample_proof, out)

        data = GovernanceExporter.decrypt_export(out, exporter._license_key)
        assert data["telos_export_version"] == 1
        assert "exported_at" in data
        assert data["data_type"] == "session_proof"

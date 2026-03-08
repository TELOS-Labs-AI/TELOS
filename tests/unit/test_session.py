"""
Tests for telos_governance.session
====================================

Tests for GovernanceSessionContext: composable session lifecycle with
Ed25519 signing and optional TKeys integration.
"""

import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List

import pytest

from telos_governance.session import GovernanceSessionContext
from telos_governance.receipt_signer import GovernanceReceipt, ReceiptSigner


# ---------------------------------------------------------------------------
# Minimal mock objects
# ---------------------------------------------------------------------------

class MockActionDecision(str, Enum):
    EXECUTE = "execute"
    CLARIFY = "clarify"
    ESCALATE = "escalate"

@dataclass
class MockFidelityResult:
    purpose_fidelity: float = 0.85
    scope_fidelity: float = 0.78
    boundary_violation: float = 0.10
    tool_fidelity: float = 0.90
    chain_continuity: float = 0.95
    composite_fidelity: float = 0.82
    effective_fidelity: float = 0.80
    decision: MockActionDecision = MockActionDecision.EXECUTE
    boundary_triggered: bool = False
    selected_tool: Optional[str] = "property_analysis"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_result():
    return MockFidelityResult()


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

class TestSessionLifecycle:
    def test_create_session_auto_id(self):
        with GovernanceSessionContext() as session:
            assert session.session_id.startswith("telos-")
            assert len(session.session_id) == 22  # "telos-" + 16 hex chars

    def test_create_session_custom_id(self):
        with GovernanceSessionContext(session_id="test-session-1") as session:
            assert session.session_id == "test-session-1"

    def test_context_manager_closes(self):
        session = GovernanceSessionContext()
        session.__enter__()
        session.__exit__(None, None, None)
        assert not session._is_active

    def test_close_idempotent(self):
        session = GovernanceSessionContext()
        session.close()
        session.close()  # Should not raise

    def test_sign_after_close_raises(self, mock_result):
        session = GovernanceSessionContext()
        session.close()
        with pytest.raises(RuntimeError, match="closed"):
            session.sign_result(mock_result, "test request")


# ---------------------------------------------------------------------------
# Ed25519 signing
# ---------------------------------------------------------------------------

class TestEd25519Signing:
    def test_sign_result_produces_receipt(self, mock_result):
        with GovernanceSessionContext() as session:
            receipt = session.sign_result(mock_result, "Assess roof condition")
            assert receipt.ed25519_signature is not None
            assert receipt.decision == "execute"
            assert receipt.effective_fidelity == 0.80

    def test_sign_result_verifiable(self, mock_result):
        with GovernanceSessionContext() as session:
            receipt = session.sign_result(mock_result, "Assess roof condition")
            pub = session._signer.public_key_bytes()
            assert ReceiptSigner.verify_receipt(receipt, pub)

    def test_sign_multiple_results(self, mock_result):
        with GovernanceSessionContext() as session:
            r1 = session.sign_result(mock_result, "Request 1")
            r2 = session.sign_result(mock_result, "Request 2")
            assert session.receipt_count == 2
            assert r1.action_text == "Request 1"
            assert r2.action_text == "Request 2"

    def test_receipt_chain_in_proof(self, mock_result):
        with GovernanceSessionContext() as session:
            session.sign_result(mock_result, "Request 1")
            session.sign_result(mock_result, "Request 2")
            proof = session.generate_proof()
            assert proof["total_receipts"] == 2
            assert len(proof["receipt_chain"]) == 2

    def test_load_existing_private_key(self, mock_result):
        key = secrets.token_bytes(32)  # Not a real Ed25519 seed, but let's use generate
        signer = ReceiptSigner.generate()
        priv = signer.private_key_bytes()

        with GovernanceSessionContext(ed25519_private_key=priv) as session:
            receipt = session.sign_result(mock_result, "test")
            # Verify with the original public key
            pub = signer.public_key_bytes()
            assert ReceiptSigner.verify_receipt(receipt, pub)

    def test_tool_name_from_result(self, mock_result):
        with GovernanceSessionContext() as session:
            receipt = session.sign_result(mock_result, "test")
            assert receipt.tool_name == "property_analysis"

    def test_tool_name_override(self, mock_result):
        with GovernanceSessionContext() as session:
            receipt = session.sign_result(mock_result, "test", tool_name="override_tool")
            assert receipt.tool_name == "override_tool"


# ---------------------------------------------------------------------------
# Session proof
# ---------------------------------------------------------------------------

class TestSessionProof:
    def test_proof_contains_public_key(self, mock_result):
        with GovernanceSessionContext() as session:
            session.sign_result(mock_result, "test")
            proof = session.generate_proof()
            assert "ed25519_public_key" in proof
            assert len(bytes.fromhex(proof["ed25519_public_key"])) == 32

    def test_proof_verification_metadata(self, mock_result):
        with GovernanceSessionContext() as session:
            session.sign_result(mock_result, "test")
            proof = session.generate_proof()
            assert proof["verification"]["ed25519_verifiable"] is True
            assert proof["verification"]["hmac_verifiable"] is False

    def test_proof_session_id(self):
        with GovernanceSessionContext(session_id="proof-test") as session:
            proof = session.generate_proof()
            assert proof["session_id"] == "proof-test"

    def test_empty_session_proof(self):
        with GovernanceSessionContext() as session:
            proof = session.generate_proof()
            assert proof["total_receipts"] == 0
            assert proof["receipt_chain"] == []


# ---------------------------------------------------------------------------
# TKeys integration (optional)
# ---------------------------------------------------------------------------

class TestTKeysIntegration:
    def test_tkeys_disabled_by_default(self):
        with GovernanceSessionContext() as session:
            assert not session.has_tkeys

    def test_tkeys_enabled(self):
        with GovernanceSessionContext(enable_tkeys=True) as session:
            assert session.has_tkeys

    def test_tkeys_produces_hmac_signature(self, mock_result):
        with GovernanceSessionContext(enable_tkeys=True) as session:
            receipt = session.sign_result(mock_result, "test with tkeys")
            assert receipt.hmac_signature is not None
            assert len(bytes.fromhex(receipt.hmac_signature)) == 64

    def test_tkeys_proof_includes_session_proof(self, mock_result):
        with GovernanceSessionContext(enable_tkeys=True) as session:
            session.sign_result(mock_result, "test")
            proof = session.generate_proof()
            assert "tkeys_session_proof" in proof
            assert proof["verification"]["hmac_verifiable"] is True

    def test_tkeys_with_master_key(self, mock_result):
        master = secrets.token_bytes(32)
        with GovernanceSessionContext(enable_tkeys=True, master_key=master) as session:
            receipt = session.sign_result(mock_result, "test with master key")
            assert receipt.hmac_signature is not None

    def test_tkeys_key_rotation_per_turn(self, mock_result):
        with GovernanceSessionContext(enable_tkeys=True) as session:
            r1 = session.sign_result(mock_result, "turn 1")
            r2 = session.sign_result(mock_result, "turn 2")
            # Different HMAC signatures because key rotated
            assert r1.hmac_signature != r2.hmac_signature


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------

class TestAccessors:
    def test_receipt_count(self, mock_result):
        with GovernanceSessionContext() as session:
            assert session.receipt_count == 0
            session.sign_result(mock_result, "r1")
            assert session.receipt_count == 1
            session.sign_result(mock_result, "r2")
            assert session.receipt_count == 2

    def test_receipts_list(self, mock_result):
        with GovernanceSessionContext() as session:
            session.sign_result(mock_result, "r1")
            receipts = session.receipts
            assert len(receipts) == 1
            assert receipts[0].action_text == "r1"

    def test_public_key_hex(self):
        with GovernanceSessionContext() as session:
            hex_key = session.public_key_hex
            assert len(hex_key) == 64  # 32 bytes = 64 hex chars


# ---------------------------------------------------------------------------
# Intelligence Layer integration
# ---------------------------------------------------------------------------

class TestIntelligenceIntegration:
    """Test Intelligence Layer integration with session lifecycle."""

    def test_session_without_intelligence(self, mock_result):
        """Session works normally without intelligence collector."""
        with GovernanceSessionContext() as session:
            receipt = session.sign_result(mock_result, "test")
            assert receipt is not None

    def test_session_with_intelligence_metrics(self, mock_result, tmp_path):
        """Intelligence collector records decisions when enabled."""
        from telos_governance.intelligence_layer import (
            IntelligenceCollector,
            IntelligenceConfig,
        )
        config = IntelligenceConfig(
            enabled=True,
            collection_level="metrics",
            base_dir=str(tmp_path),
            agent_id="test-agent",
        )
        collector = IntelligenceCollector(config)

        with GovernanceSessionContext(
            intelligence_collector=collector,
            agent_id="test-agent",
        ) as session:
            session.sign_result(mock_result, "test request", "pre_action")
            session.sign_result(mock_result, "test request 2", "tool_select")

        # Verify telemetry was written
        sessions_dir = tmp_path / "test-agent" / "sessions"
        assert sessions_dir.exists()
        files = list(sessions_dir.glob("*.jsonl"))
        assert len(files) == 1

    def test_session_with_intelligence_full(self, mock_result, tmp_path):
        """Full-level intelligence records dimension breakdowns."""
        from telos_governance.intelligence_layer import (
            IntelligenceCollector,
            IntelligenceConfig,
        )
        import json

        config = IntelligenceConfig(
            enabled=True,
            collection_level="full",
            base_dir=str(tmp_path),
            agent_id="test-agent",
        )
        collector = IntelligenceCollector(config)

        with GovernanceSessionContext(
            intelligence_collector=collector,
            agent_id="test-agent",
        ) as session:
            session.sign_result(mock_result, "test", "pre_action")

        # Check that dimension data was recorded
        files = list((tmp_path / "test-agent" / "sessions").glob("*.jsonl"))
        lines = files[0].read_text().strip().split("\n")
        record = json.loads(lines[1])  # Skip header
        assert record["purpose_fidelity"] == 0.85
        assert record["scope_fidelity"] == 0.78

    def test_intelligence_aggregate_updated(self, mock_result, tmp_path):
        """Session close should update aggregate statistics."""
        from telos_governance.intelligence_layer import (
            IntelligenceCollector,
            IntelligenceConfig,
        )
        import json

        config = IntelligenceConfig(
            enabled=True,
            collection_level="metrics",
            base_dir=str(tmp_path),
            agent_id="test-agent",
        )
        collector = IntelligenceCollector(config)

        with GovernanceSessionContext(
            intelligence_collector=collector,
            agent_id="test-agent",
        ) as session:
            session.sign_result(mock_result, "test", "pre_action")

        agg = collector.get_aggregate("test-agent")
        assert agg is not None
        assert agg["total_sessions"] == 1
        assert agg["total_records"] == 1

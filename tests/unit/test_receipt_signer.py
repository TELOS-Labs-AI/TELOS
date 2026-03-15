"""
Tests for telos_governance.receipt_signer
==========================================

Tests for ReceiptSigner: Ed25519 + HMAC-SHA512 governance receipt signing.
Verifies key generation, signing, verification, tamper detection, HMAC
binding, canonical serialization, and GovernanceEvent integration.
"""

import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List

import pytest

from telos_governance.receipt_signer import (
    ReceiptSigner,
    GovernanceReceipt,
    ReceiptSigningError,
)


# ---------------------------------------------------------------------------
# Minimal mock objects (avoid importing full governance stack)
# ---------------------------------------------------------------------------

class MockDecisionPoint(str, Enum):
    PRE_ACTION = "pre_action"
    TOOL_SELECT = "tool_select"

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

@dataclass
class MockGovernanceEvent:
    decision_point: MockDecisionPoint = MockDecisionPoint.PRE_ACTION
    action_text: str = "Assess roof condition for 742 Evergreen Terrace"
    tool_name: Optional[str] = "property_analysis"
    tool_args: Optional[Dict] = None
    result: Optional[MockFidelityResult] = None
    overridden: bool = False
    override_reason: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    contrastive_suppressed: bool = False
    suppression_detail: Optional[str] = None

    def __post_init__(self):
        if self.result is None:
            self.result = MockFidelityResult()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def signer():
    return ReceiptSigner.generate()

@pytest.fixture
def hmac_key():
    return secrets.token_bytes(64)

@pytest.fixture
def signer_with_hmac(hmac_key):
    return ReceiptSigner.generate(hmac_key=hmac_key)

@pytest.fixture
def mock_event():
    return MockGovernanceEvent()

@pytest.fixture
def sample_receipt():
    return GovernanceReceipt(
        decision_point="pre_action",
        action_text="Assess roof condition for 742 Evergreen Terrace",
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
    )


# ---------------------------------------------------------------------------
# Key generation and serialization
# ---------------------------------------------------------------------------

class TestKeyManagement:
    def test_generate_creates_valid_signer(self):
        signer = ReceiptSigner.generate()
        assert signer is not None

    def test_public_key_is_32_bytes(self, signer):
        pub = signer.public_key_bytes()
        assert len(pub) == 32

    def test_private_key_is_32_bytes(self, signer):
        priv = signer.private_key_bytes()
        assert len(priv) == 32

    def test_round_trip_private_key(self, signer, sample_receipt):
        priv = signer.private_key_bytes()
        pub = signer.public_key_bytes()

        # Load from private bytes
        loaded = ReceiptSigner.from_private_bytes(priv)
        assert loaded.public_key_bytes() == pub

        # Sign with loaded, verify with original public key
        signed = loaded.sign_receipt(sample_receipt)
        assert ReceiptSigner.verify_receipt(signed, pub)

    def test_different_signers_have_different_keys(self):
        s1 = ReceiptSigner.generate()
        s2 = ReceiptSigner.generate()
        assert s1.public_key_bytes() != s2.public_key_bytes()
        assert s1.private_key_bytes() != s2.private_key_bytes()


# ---------------------------------------------------------------------------
# Signing receipts
# ---------------------------------------------------------------------------

class TestSigning:
    def test_sign_receipt_populates_signature(self, signer, sample_receipt):
        signed = signer.sign_receipt(sample_receipt)
        assert signed.ed25519_signature is not None
        assert len(bytes.fromhex(signed.ed25519_signature)) == 64

    def test_sign_receipt_populates_public_key(self, signer, sample_receipt):
        signed = signer.sign_receipt(sample_receipt)
        assert signed.public_key == signer.public_key_bytes().hex()

    def test_sign_receipt_populates_payload_hash(self, signer, sample_receipt):
        signed = signer.sign_receipt(sample_receipt)
        assert signed.payload_hash is not None
        assert len(bytes.fromhex(signed.payload_hash)) == 32  # SHA-256

    def test_sign_receipt_no_hmac_without_key(self, signer, sample_receipt):
        signed = signer.sign_receipt(sample_receipt)
        assert signed.hmac_signature is None

    def test_sign_receipt_with_hmac(self, signer_with_hmac, sample_receipt):
        signed = signer_with_hmac.sign_receipt(sample_receipt)
        assert signed.ed25519_signature is not None
        assert signed.hmac_signature is not None
        assert len(bytes.fromhex(signed.hmac_signature)) == 64  # HMAC-SHA512

    def test_sign_event(self, signer, mock_event):
        receipt = signer.sign_event(mock_event)
        assert receipt.decision_point == "pre_action"
        assert receipt.decision == "execute"
        assert receipt.effective_fidelity == 0.80
        assert receipt.ed25519_signature is not None

    def test_sign_event_with_tool(self, signer):
        event = MockGovernanceEvent(
            decision_point=MockDecisionPoint.TOOL_SELECT,
            tool_name="risk_scoring",
        )
        receipt = signer.sign_event(event)
        assert receipt.tool_name == "risk_scoring"
        assert receipt.decision_point == "tool_select"

    def test_sign_payload_raw(self, signer):
        payload = b"arbitrary governance data"
        sig = signer.sign_payload(payload)
        assert len(sig) == 64

    def test_deterministic_signatures(self, signer, sample_receipt):
        """Ed25519 signatures are deterministic -- same input, same signature."""
        r1 = GovernanceReceipt(**{k: v for k, v in sample_receipt.to_dict().items()
                                  if k in GovernanceReceipt.__dataclass_fields__
                                  and k not in ('ed25519_signature', 'hmac_signature', 'public_key', 'payload_hash')})
        r2 = GovernanceReceipt(**{k: v for k, v in sample_receipt.to_dict().items()
                                  if k in GovernanceReceipt.__dataclass_fields__
                                  and k not in ('ed25519_signature', 'hmac_signature', 'public_key', 'payload_hash')})
        signed1 = signer.sign_receipt(r1)
        signed2 = signer.sign_receipt(r2)
        assert signed1.ed25519_signature == signed2.ed25519_signature


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

class TestVerification:
    def test_verify_valid_receipt(self, signer, sample_receipt):
        signed = signer.sign_receipt(sample_receipt)
        pub = signer.public_key_bytes()
        assert ReceiptSigner.verify_receipt(signed, pub) is True

    def test_verify_wrong_public_key_fails(self, signer, sample_receipt):
        signed = signer.sign_receipt(sample_receipt)
        other_signer = ReceiptSigner.generate()
        with pytest.raises(ReceiptSigningError, match="signature verification failed"):
            ReceiptSigner.verify_receipt(signed, other_signer.public_key_bytes())

    def test_verify_tampered_action_text_fails(self, signer, sample_receipt):
        signed = signer.sign_receipt(sample_receipt)
        signed.action_text = "TAMPERED: delete all records"
        with pytest.raises(ReceiptSigningError, match="tampered"):
            ReceiptSigner.verify_receipt(signed, signer.public_key_bytes())

    def test_verify_tampered_fidelity_fails(self, signer, sample_receipt):
        signed = signer.sign_receipt(sample_receipt)
        signed.effective_fidelity = 0.99  # Inflate fidelity
        with pytest.raises(ReceiptSigningError, match="tampered"):
            ReceiptSigner.verify_receipt(signed, signer.public_key_bytes())

    def test_verify_tampered_decision_fails(self, signer, sample_receipt):
        signed = signer.sign_receipt(sample_receipt)
        signed.decision = "escalate"  # Tamper: was "execute"
        with pytest.raises(ReceiptSigningError, match="tampered"):
            ReceiptSigner.verify_receipt(signed, signer.public_key_bytes())

    def test_verify_missing_signature_fails(self, sample_receipt):
        pub = ReceiptSigner.generate().public_key_bytes()
        with pytest.raises(ReceiptSigningError, match="no Ed25519 signature"):
            ReceiptSigner.verify_receipt(sample_receipt, pub)

    def test_verify_event_round_trip(self, signer, mock_event):
        receipt = signer.sign_event(mock_event)
        pub = signer.public_key_bytes()
        assert ReceiptSigner.verify_receipt(receipt, pub) is True


# ---------------------------------------------------------------------------
# HMAC verification
# ---------------------------------------------------------------------------

class TestHMACVerification:
    def test_verify_hmac_valid(self, signer_with_hmac, hmac_key, sample_receipt):
        signed = signer_with_hmac.sign_receipt(sample_receipt)
        assert ReceiptSigner.verify_hmac(signed, hmac_key) is True

    def test_verify_hmac_wrong_key_fails(self, signer_with_hmac, sample_receipt):
        signed = signer_with_hmac.sign_receipt(sample_receipt)
        wrong_key = secrets.token_bytes(64)
        with pytest.raises(ReceiptSigningError, match="HMAC verification failed"):
            ReceiptSigner.verify_hmac(signed, wrong_key)

    def test_verify_hmac_missing_fails(self, signer, hmac_key, sample_receipt):
        signed = signer.sign_receipt(sample_receipt)  # No HMAC key set
        with pytest.raises(ReceiptSigningError, match="no HMAC signature"):
            ReceiptSigner.verify_hmac(signed, hmac_key)

    def test_set_hmac_key_enables_signing(self, signer, sample_receipt):
        key = secrets.token_bytes(64)
        signer.set_hmac_key(key)
        signed = signer.sign_receipt(sample_receipt)
        assert signed.hmac_signature is not None
        assert ReceiptSigner.verify_hmac(signed, key) is True


# ---------------------------------------------------------------------------
# Canonical serialization
# ---------------------------------------------------------------------------

class TestCanonicalization:
    def test_canonical_is_deterministic(self, sample_receipt):
        c1 = ReceiptSigner._canonicalize(sample_receipt)
        c2 = ReceiptSigner._canonicalize(sample_receipt)
        assert c1 == c2

    def test_canonical_excludes_signatures(self, signer, sample_receipt):
        canonical_before = ReceiptSigner._canonicalize(sample_receipt)
        signer.sign_receipt(sample_receipt)
        canonical_after = ReceiptSigner._canonicalize(sample_receipt)
        assert canonical_before == canonical_after

    def test_canonical_is_json(self, sample_receipt):
        canonical = ReceiptSigner._canonicalize(sample_receipt)
        parsed = __import__("json").loads(canonical)
        assert parsed["decision_point"] == "pre_action"
        assert parsed["effective_fidelity"] == 0.80


# ---------------------------------------------------------------------------
# GovernanceReceipt serialization
# ---------------------------------------------------------------------------

class TestReceiptSerialization:
    def test_to_dict(self, signer, sample_receipt):
        signed = signer.sign_receipt(sample_receipt)
        d = signed.to_dict()
        assert d["decision_point"] == "pre_action"
        assert d["ed25519_signature"] is not None
        assert isinstance(d, dict)

    def test_from_dict_round_trip(self, signer, sample_receipt):
        signed = signer.sign_receipt(sample_receipt)
        d = signed.to_dict()
        loaded = GovernanceReceipt.from_dict(d)
        assert loaded.ed25519_signature == signed.ed25519_signature
        assert loaded.effective_fidelity == signed.effective_fidelity

    def test_from_dict_ignores_extra_keys(self, sample_receipt):
        d = sample_receipt.to_dict()
        d["extra_field"] = "should be ignored"
        loaded = GovernanceReceipt.from_dict(d)
        assert loaded.decision_point == "pre_action"

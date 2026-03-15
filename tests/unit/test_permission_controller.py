"""
Tests for the Permission Controller -- ESCALATE verdict human-in-the-loop.

Tests cover:
  - Escalation flow: ESCALATE → notification → approve → receipt signed
  - Timeout handling: ESCALATE → timeout → denied (fail-closed)
  - CLI fallback: resolve_from_cli → approve/deny
  - Telegram callback resolution
  - WhatsApp button reply resolution
  - Audit JSONL logging
  - Ed25519 override receipt signing
"""

import asyncio
import hashlib
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from telos_adapters.openclaw.notification_service import (
    EscalationNotification,
    NotificationService,
)
from telos_adapters.openclaw.permission_controller import (
    EscalationResult,
    PermissionController,
    TelegramPoller,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class MockNotificationsConfig:
    """Minimal mock for NotificationsConfig."""
    telegram_bot_token = ""
    telegram_chat_id = ""
    discord_webhook_url = ""
    whatsapp_phone_number_id = ""
    whatsapp_access_token = ""
    whatsapp_recipient_number = ""
    escalation_timeout_seconds = 5
    timeout_action = "deny"
    has_telegram = False
    has_discord = False
    has_whatsapp = False
    has_any_channel = True


class MockVerdict:
    """Minimal mock for GovernanceVerdict."""
    decision = "escalate"
    telos_tool_name = "shell_execute"
    tool_group = "shell"
    risk_tier = "critical"
    fidelity = 0.35
    explanation = "Boundary violation: rm -rf"
    boundary_triggered = True
    human_required = True
    governance_preset = "balanced"
    allowed = False


def _make_controller(tmp_dir, notification_service=None, signer=None):
    """Helper to create a PermissionController for testing."""
    if notification_service is None:
        notification_service = MagicMock(spec=NotificationService)
        notification_service.send = AsyncMock(return_value={"telegram": True})
    if signer is None:
        signer = MagicMock()
        signer.sign_payload.return_value = b"\x00" * 64
        signer.public_key_bytes.return_value = b"\x01" * 32
    config = MockNotificationsConfig()
    return PermissionController(
        config=config,
        notification_service=notification_service,
        receipt_signer=signer,
        audit_dir=Path(tmp_dir),
    ), notification_service, signer


# ---------------------------------------------------------------------------
# Tests: Escalation flow
# ---------------------------------------------------------------------------

class TestEscalationFlow:
    """Test the full escalation → notification → resolve → receipt flow."""

    def test_approve_via_cli(self):
        """ESCALATE → notify → CLI approve → receipt signed."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, notif_svc, _ = _make_controller(d)
                verdict = MockVerdict()

                async def approve_after_delay():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    assert len(pending) == 1
                    ctrl.resolve(pending[0], approved=True, source="cli")

                task = asyncio.create_task(approve_after_delay())
                result = await ctrl.handle_escalation(verdict)
                await task

                assert result.approved is True
                assert result.response_source == "cli"
                assert result.escalation_id
                assert result.receipt is not None
                assert result.override_signature is not None
                notif_svc.send.assert_called_once()

        asyncio.run(_test())

    def test_deny_via_cli(self):
        """ESCALATE → notify → CLI deny → no receipt."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                verdict = MockVerdict()

                async def deny_after_delay():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    ctrl.resolve(pending[0], approved=False, source="cli")

                task = asyncio.create_task(deny_after_delay())
                result = await ctrl.handle_escalation(verdict)
                await task

                assert result.approved is False
                assert result.response_source == "cli"
                assert result.receipt is None

        asyncio.run(_test())

    def test_timeout_denies(self):
        """ESCALATE → notify → timeout → denied (fail-closed)."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                ctrl._config.escalation_timeout_seconds = 0.2
                verdict = MockVerdict()

                result = await ctrl.handle_escalation(verdict)

                assert result.approved is False
                assert result.response_source == "timeout"

        asyncio.run(_test())

    def test_timeout_allows_when_configured(self):
        """ESCALATE → timeout → allowed when timeout_action='allow'."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                ctrl._config.escalation_timeout_seconds = 0.2
                ctrl._config.timeout_action = "allow"
                verdict = MockVerdict()

                result = await ctrl.handle_escalation(verdict)

                assert result.approved is True
                assert result.response_source == "timeout"

        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Tests: Telegram resolution
# ---------------------------------------------------------------------------

class TestTelegramResolution:
    """Test Telegram callback_query resolution."""

    def test_resolve_from_telegram_approve(self):
        """Telegram Approve button resolves escalation (with challenge)."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                verdict = MockVerdict()

                async def telegram_approve():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    esc_id = pending[0]
                    challenge = ctrl._signed_escalations[esc_id].get("challenge", "")
                    resolved = ctrl.resolve_from_telegram({
                        "a": "y",
                        "i": esc_id,
                        "c": challenge,
                    })
                    assert resolved is True

                task = asyncio.create_task(telegram_approve())
                result = await ctrl.handle_escalation(verdict)
                await task

                assert result.approved is True
                assert result.response_source == "telegram"

        asyncio.run(_test())

    def test_resolve_from_telegram_deny(self):
        """Telegram Deny button resolves escalation (with challenge)."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                verdict = MockVerdict()

                async def telegram_deny():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    esc_id = pending[0]
                    challenge = ctrl._signed_escalations[esc_id].get("challenge", "")
                    ctrl.resolve_from_telegram({
                        "a": "n",
                        "i": esc_id,
                        "c": challenge,
                    })

                task = asyncio.create_task(telegram_deny())
                result = await ctrl.handle_escalation(verdict)
                await task

                assert result.approved is False
                assert result.response_source == "telegram"

        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Tests: WhatsApp resolution
# ---------------------------------------------------------------------------

class TestWhatsAppResolution:
    """Test WhatsApp button reply resolution."""

    def test_resolve_from_whatsapp_approve(self):
        """WhatsApp Approve button resolves escalation (with challenge)."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                verdict = MockVerdict()

                async def whatsapp_approve():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    esc_id = pending[0]
                    challenge = ctrl._signed_escalations[esc_id].get("challenge", "")
                    resolved = ctrl.resolve_from_whatsapp(
                        f"approve:{esc_id}:{challenge}"
                    )
                    assert resolved is True

                task = asyncio.create_task(whatsapp_approve())
                result = await ctrl.handle_escalation(verdict)
                await task

                assert result.approved is True
                assert result.response_source == "whatsapp"

        asyncio.run(_test())

    def test_resolve_from_whatsapp_deny(self):
        """WhatsApp Deny button resolves escalation (with challenge)."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                verdict = MockVerdict()

                async def whatsapp_deny():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    esc_id = pending[0]
                    challenge = ctrl._signed_escalations[esc_id].get("challenge", "")
                    ctrl.resolve_from_whatsapp(f"deny:{esc_id}:{challenge}")

                task = asyncio.create_task(whatsapp_deny())
                result = await ctrl.handle_escalation(verdict)
                await task

                assert result.approved is False
                assert result.response_source == "whatsapp"

        asyncio.run(_test())

    def test_whatsapp_invalid_format(self):
        """Invalid WhatsApp reply format returns False."""
        with tempfile.TemporaryDirectory() as d:
            ctrl, _, _ = _make_controller(d)
            assert ctrl.resolve_from_whatsapp("invalid") is False


# ---------------------------------------------------------------------------
# Tests: Audit logging
# ---------------------------------------------------------------------------

class TestAuditLogging:
    """Test JSONL audit trail for escalation events."""

    def test_audit_events_written(self):
        """All escalation lifecycle events are logged to JSONL."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                verdict = MockVerdict()

                async def resolve_quickly():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    ctrl.resolve(pending[0], approved=True, source="cli")

                task = asyncio.create_task(resolve_quickly())
                await ctrl.handle_escalation(verdict)
                await task

                audit_file = Path(d) / "escalations.jsonl"
                assert audit_file.exists()

                events = []
                with open(audit_file) as f:
                    for line in f:
                        events.append(json.loads(line))

                # Should have 3 events: initiated, notified, resolved
                event_types = [e["event"] for e in events]
                assert "initiated" in event_types
                assert "notified" in event_types
                assert "resolved" in event_types

                # All events share the same escalation_id
                ids = set(e["escalation_id"] for e in events)
                assert len(ids) == 1

        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Tests: Ed25519 receipt signing
# ---------------------------------------------------------------------------

class TestOverrideReceipt:
    """Test Ed25519-signed override receipt generation."""

    def test_receipt_signed_on_approve(self):
        """Approved override produces a signed receipt."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, mock_signer = _make_controller(d)
                verdict = MockVerdict()

                async def approve():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    ctrl.resolve(pending[0], approved=True, source="cli")

                task = asyncio.create_task(approve())
                result = await ctrl.handle_escalation(verdict)
                await task

                assert result.receipt is not None
                assert result.receipt["type"] == "escalation_override"
                assert result.receipt["tool_name"] == "shell_execute"
                assert result.receipt["risk_tier"] == "critical"
                assert "ed25519_signature" in result.receipt
                assert "public_key" in result.receipt
                # sign_payload called twice: once for escalation request, once for receipt
                assert mock_signer.sign_payload.call_count == 2

        asyncio.run(_test())

    def test_no_receipt_on_deny(self):
        """Denied override produces no receipt."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                verdict = MockVerdict()

                async def deny():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    ctrl.resolve(pending[0], approved=False, source="cli")

                task = asyncio.create_task(deny())
                result = await ctrl.handle_escalation(verdict)
                await task

                assert result.receipt is None

        asyncio.run(_test())

    def test_no_receipt_without_signer(self):
        """No receipt when signer is not configured."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                notif_svc = MagicMock(spec=NotificationService)
                notif_svc.send = AsyncMock(return_value={"telegram": True})
                ctrl, _, _ = _make_controller(d, notification_service=notif_svc, signer=None)
                # Override signer to None
                ctrl._signer = None
                verdict = MockVerdict()

                async def approve():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    ctrl.resolve(pending[0], approved=True, source="cli")

                task = asyncio.create_task(approve())
                result = await ctrl.handle_escalation(verdict)
                await task

                assert result.approved is True
                assert result.receipt is None

        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_resolve_nonexistent_escalation(self):
        """Resolving a non-existent escalation returns False."""
        with tempfile.TemporaryDirectory() as d:
            ctrl, _, _ = _make_controller(d)
            assert ctrl.resolve("nonexistent", approved=True) is False

    def test_pending_escalations_empty_initially(self):
        """No pending escalations initially."""
        with tempfile.TemporaryDirectory() as d:
            ctrl, _, _ = _make_controller(d)
            assert ctrl.pending_escalations == []

    def test_notification_failure_does_not_block(self):
        """Escalation proceeds even if notification fails."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                notif_svc = MagicMock(spec=NotificationService)
                notif_svc.send = AsyncMock(side_effect=Exception("network error"))
                ctrl, _, _ = _make_controller(d, notification_service=notif_svc)
                ctrl._config.escalation_timeout_seconds = 0.2
                verdict = MockVerdict()

                result = await ctrl.handle_escalation(verdict)

                assert result.approved is False
                assert result.response_source == "timeout"

        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Mock TKeys Manager
# ---------------------------------------------------------------------------

class MockTKeysState:
    """Mock TelemetricKeyState."""
    def __init__(self):
        self.turn_number = 0


class MockTKeysKeyGenerator:
    """Mock TelemetricKeyGenerator for testing."""
    def __init__(self):
        self.state = MockTKeysState()
        self._hmac_key = b"\xaa" * 32
        self.rotate_call_count = 0

    def rotate_key(self, telemetry):
        self.state.turn_number += 1
        self.rotate_call_count += 1
        # Simulate key change by modifying the HMAC key
        self._hmac_key = hashlib.sha256(
            self._hmac_key + str(self.state.turn_number).encode()
        ).digest()

    def generate_hmac_signature(self, data: bytes) -> bytes:
        import hmac as _hmac
        return _hmac.new(self._hmac_key, data, hashlib.sha512).digest()


class MockTKeysManager:
    """Mock TelemetricSessionManager for testing."""
    def __init__(self, session_id="test-session"):
        self.session_id = session_id
        self.key_generator = MockTKeysKeyGenerator()

    def generate_session_proof(self):
        return {
            "session_id": self.session_id,
            "turn_number": self.key_generator.state.turn_number,
            "proof": "mock_session_proof",
        }


def _make_controller_with_tkeys(tmp_dir, tkeys_manager=None):
    """Helper to create a PermissionController with TKeys for testing."""
    notif_svc = MagicMock(spec=NotificationService)
    notif_svc.send = AsyncMock(return_value={"telegram": True})
    signer = MagicMock()
    signer.sign_payload.return_value = b"\x00" * 64
    signer.public_key_bytes.return_value = b"\x01" * 32
    config = MockNotificationsConfig()
    ctrl = PermissionController(
        config=config,
        notification_service=notif_svc,
        receipt_signer=signer,
        tkeys_manager=tkeys_manager or MockTKeysManager(),
        audit_dir=Path(tmp_dir),
    )
    return ctrl, notif_svc, signer


# ---------------------------------------------------------------------------
# Tests: TKeys cryptographic trust root
# ---------------------------------------------------------------------------

class TestTKeysEscalationSigning:
    """Test that outgoing escalations are signed with Ed25519 + TKeys HMAC."""

    def test_escalation_signed_with_ed25519(self):
        """Outgoing escalation has Ed25519 signature."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, signer = _make_controller(d)
                verdict = MockVerdict()

                async def approve():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    ctrl.resolve(pending[0], approved=True, source="cli")

                task = asyncio.create_task(approve())
                await ctrl.handle_escalation(verdict)
                await task

                # Verify signed escalation was created with Ed25519
                # (it was stored in _signed_escalations during handle_escalation,
                # then removed on receipt signing -- check signer was called)
                assert signer.sign_payload.call_count == 2  # escalation + receipt

        asyncio.run(_test())

    def test_escalation_signed_with_tkeys_hmac(self):
        """Outgoing escalation has HMAC-SHA512 when TKeys active."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                tkeys = MockTKeysManager()
                ctrl, _, _ = _make_controller_with_tkeys(d, tkeys)
                verdict = MockVerdict()

                # Trigger escalation and capture signed escalation before resolve
                async def approve_and_check():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    esc_id = pending[0]
                    # Check signed escalation while it's still pending
                    signed = ctrl._signed_escalations.get(esc_id, {})
                    assert "tkeys_hmac" in signed, "Signed escalation missing TKeys HMAC"
                    assert "tkeys_rotation" in signed
                    assert signed["tkeys_rotation"] == 1  # First rotation
                    ctrl.resolve(esc_id, approved=True, source="cli")

                task = asyncio.create_task(approve_and_check())
                await ctrl.handle_escalation(verdict)
                await task

        asyncio.run(_test())

    def test_challenge_derived_from_signature(self):
        """Challenge = SHA-256(Ed25519_sig)[:16].hex()."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, signer = _make_controller(d)
                # Set a deterministic signature
                test_sig = b"\x42" * 64
                signer.sign_payload.return_value = test_sig
                expected_challenge = hashlib.sha256(test_sig).hexdigest()[:16]
                verdict = MockVerdict()

                async def check_challenge():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    esc_id = pending[0]
                    signed = ctrl._signed_escalations.get(esc_id, {})
                    assert signed["challenge"] == expected_challenge
                    ctrl.resolve(esc_id, approved=True, source="cli")

                task = asyncio.create_task(check_challenge())
                await ctrl.handle_escalation(verdict)
                await task

        asyncio.run(_test())


class TestTKeysChallengeVerification:
    """Test challenge verification on incoming callbacks."""

    def test_callback_with_valid_challenge_resolves(self):
        """Correct challenge resolves the escalation."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, signer = _make_controller(d)
                test_sig = b"\x42" * 64
                signer.sign_payload.return_value = test_sig
                expected_challenge = hashlib.sha256(test_sig).hexdigest()[:16]
                verdict = MockVerdict()

                async def resolve_with_challenge():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    resolved = ctrl.resolve(
                        pending[0], approved=True, source="telegram",
                        challenge=expected_challenge,
                    )
                    assert resolved is True

                task = asyncio.create_task(resolve_with_challenge())
                result = await ctrl.handle_escalation(verdict)
                await task
                assert result.approved is True

        asyncio.run(_test())

    def test_callback_with_invalid_challenge_rejected(self):
        """Wrong challenge returns False and does not resolve."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                ctrl._config.escalation_timeout_seconds = 0.5
                verdict = MockVerdict()

                async def resolve_with_bad_challenge():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    resolved = ctrl.resolve(
                        pending[0], approved=True, source="telegram",
                        challenge="deadbeef12345678",  # Wrong challenge
                    )
                    assert resolved is False

                task = asyncio.create_task(resolve_with_bad_challenge())
                result = await ctrl.handle_escalation(verdict)
                await task
                # Should time out because the resolution was rejected
                assert result.approved is False
                assert result.response_source == "timeout"

        asyncio.run(_test())

    def test_callback_with_expired_escalation_rejected(self):
        """Expired escalation returns False."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                ctrl._config.escalation_timeout_seconds = 0.5
                verdict = MockVerdict()

                async def resolve_expired():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    esc_id = pending[0]
                    # Manually expire the signed escalation
                    ctrl._signed_escalations[esc_id]["expiry"] = time.time() - 10
                    resolved = ctrl.resolve(esc_id, approved=True, source="cli")
                    assert resolved is False

                task = asyncio.create_task(resolve_expired())
                result = await ctrl.handle_escalation(verdict)
                await task
                assert result.approved is False
                assert result.response_source == "timeout"

        asyncio.run(_test())


class TestTKeysReceiptChaining:
    """Test override receipt chains to escalation signature."""

    def test_override_receipt_chains_to_escalation(self):
        """Override receipt has escalation_sig_hash field."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, signer = _make_controller(d)
                test_sig = b"\x42" * 64
                signer.sign_payload.return_value = test_sig
                verdict = MockVerdict()

                async def approve():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    ctrl.resolve(pending[0], approved=True, source="cli")

                task = asyncio.create_task(approve())
                result = await ctrl.handle_escalation(verdict)
                await task

                assert result.receipt is not None
                assert "escalation_sig_hash" in result.receipt
                # Verify the chain: escalation_sig_hash = SHA-256(escalation Ed25519 sig)
                expected_hash = hashlib.sha256(test_sig).hexdigest()
                assert result.receipt["escalation_sig_hash"] == expected_hash

        asyncio.run(_test())

    def test_override_receipt_has_tkeys_hmac(self):
        """Override receipt has TKeys HMAC when TKeys active."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                tkeys = MockTKeysManager()
                ctrl, _, _ = _make_controller_with_tkeys(d, tkeys)
                verdict = MockVerdict()

                async def approve():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    ctrl.resolve(pending[0], approved=True, source="cli")

                task = asyncio.create_task(approve())
                result = await ctrl.handle_escalation(verdict)
                await task

                assert result.receipt is not None
                assert "tkeys_hmac" in result.receipt
                assert "tkeys_rotation" in result.receipt

        asyncio.run(_test())


class TestTKeysAuditSigning:
    """Test audit log entries are signed with TKeys HMAC."""

    def test_audit_entries_signed_with_tkeys(self):
        """Audit log entries have tkeys_hmac when TKeys active."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                tkeys = MockTKeysManager()
                ctrl, _, _ = _make_controller_with_tkeys(d, tkeys)
                verdict = MockVerdict()

                async def approve():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    ctrl.resolve(pending[0], approved=True, source="cli")

                task = asyncio.create_task(approve())
                await ctrl.handle_escalation(verdict)
                await task

                audit_file = Path(d) / "escalations.jsonl"
                assert audit_file.exists()
                with open(audit_file) as f:
                    for line in f:
                        entry = json.loads(line)
                        assert "tkeys_hmac" in entry, (
                            f"Audit entry '{entry['event']}' missing tkeys_hmac"
                        )

        asyncio.run(_test())


class TestTKeysRotation:
    """Test TKeys key rotation per escalation."""

    def test_tkeys_rotation_per_escalation(self):
        """TKeys key rotates for each escalation."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                tkeys = MockTKeysManager()
                ctrl, _, _ = _make_controller_with_tkeys(d, tkeys)
                ctrl._config.escalation_timeout_seconds = 0.2

                # First escalation
                verdict1 = MockVerdict()
                await ctrl.handle_escalation(verdict1)
                rotation_after_first = tkeys.key_generator.state.turn_number

                # Second escalation
                verdict2 = MockVerdict()
                await ctrl.handle_escalation(verdict2)
                rotation_after_second = tkeys.key_generator.state.turn_number

                assert rotation_after_second > rotation_after_first
                assert tkeys.key_generator.rotate_call_count >= 2

        asyncio.run(_test())


class TestTKeysFallback:
    """Test graceful fallback when TKeys is not available."""

    def test_no_tkeys_falls_back_gracefully(self):
        """Ed25519-only mode works when TKeys is None."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                # Create controller without TKeys (existing _make_controller)
                ctrl, _, signer = _make_controller(d)
                assert ctrl._tkeys is None
                verdict = MockVerdict()

                async def approve():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    ctrl.resolve(pending[0], approved=True, source="cli")

                task = asyncio.create_task(approve())
                result = await ctrl.handle_escalation(verdict)
                await task

                assert result.approved is True
                assert result.receipt is not None
                # No TKeys fields in receipt
                assert "tkeys_hmac" not in result.receipt
                # Ed25519 signature present
                assert "ed25519_signature" in result.receipt

        asyncio.run(_test())


class TestTKeysProof:
    """Test TKeys session proof generation."""

    def test_tkeys_proof_generation(self):
        """Session proof available when TKeys active."""
        with tempfile.TemporaryDirectory() as d:
            tkeys = MockTKeysManager("proof-test-session")
            ctrl, _, _ = _make_controller_with_tkeys(d, tkeys)

            proof = ctrl.get_tkeys_proof()
            assert proof is not None
            assert proof["session_id"] == "proof-test-session"

    def test_no_tkeys_proof_when_inactive(self):
        """get_tkeys_proof returns None when TKeys not configured."""
        with tempfile.TemporaryDirectory() as d:
            ctrl, _, _ = _make_controller(d)
            assert ctrl.get_tkeys_proof() is None


# ---------------------------------------------------------------------------
# Mock ESCALATE (scope) Verdict
# ---------------------------------------------------------------------------

class MockEscalateScopeVerdict:
    """Mock GovernanceVerdict with decision=escalate (scope drift)."""
    decision = "escalate"
    telos_tool_name = "web_fetch"
    tool_group = "web_network"
    risk_tier = "medium"
    fidelity = 0.38
    explanation = "Action outside operational scope"
    boundary_triggered = False
    human_required = True
    governance_preset = "balanced"
    allowed = False


# ---------------------------------------------------------------------------
# Tests: ESCALATE (scope) notification + override
# ---------------------------------------------------------------------------

class TestEscalateScopeHandling:
    """Test ESCALATE verdict notification and optional override flow."""

    def test_escalate_scope_sends_notification(self):
        """ESCALATE verdict sends notification to configured channels."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, notif_svc, _ = _make_controller(d)
                ctrl._config.escalation_timeout_seconds = 0.3
                verdict = MockEscalateScopeVerdict()

                result = await ctrl.handle_escalation(verdict)

                assert result.approved is False
                assert result.response_source == "timeout"
                notif_svc.send.assert_called_once()
                # Verify notification had decision="escalate"
                sent_notif = notif_svc.send.call_args[0][0]
                assert sent_notif.decision == "escalate"

        asyncio.run(_test())

    def test_escalate_scope_override_approved(self):
        """Human can override an ESCALATE verdict."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                verdict = MockEscalateScopeVerdict()

                async def approve():
                    await asyncio.sleep(0.1)
                    pending = ctrl.pending_escalations
                    assert len(pending) == 1
                    ctrl.resolve(pending[0], approved=True, source="cli")

                task = asyncio.create_task(approve())
                result = await ctrl.handle_escalation(verdict)
                await task

                assert result.approved is True
                assert result.response_source == "cli"
                assert result.receipt is not None

        asyncio.run(_test())

    def test_escalate_scope_audit_events(self):
        """ESCALATE lifecycle logged to audit JSONL."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                ctrl._config.escalation_timeout_seconds = 0.2
                verdict = MockEscalateScopeVerdict()

                await ctrl.handle_escalation(verdict)

                audit_file = Path(d) / "escalations.jsonl"
                assert audit_file.exists()
                events = []
                with open(audit_file) as f:
                    for line in f:
                        events.append(json.loads(line))

                event_types = [e["event"] for e in events]
                assert "escalation_initiated" in event_types
                assert "escalation_notified" in event_types
                assert "escalation_resolved" in event_types

        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Tests: Semantic context
# ---------------------------------------------------------------------------

class TestSemanticContext:
    """Test semantic interpretation in notifications."""

    def test_escalation_has_semantic_context(self):
        """ESCALATE notification includes semantic interpretation."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, notif_svc, _ = _make_controller(d)
                ctrl._config.escalation_timeout_seconds = 0.3
                verdict = MockVerdict()

                await ctrl.handle_escalation(verdict)

                sent_notif = notif_svc.send.call_args[0][0]
                assert sent_notif.semantic_context != ""
                # Should mention the tool group in plain language
                assert "shell" in sent_notif.semantic_context.lower()
                # Should mention alignment percentage
                assert "35%" in sent_notif.semantic_context

        asyncio.run(_test())

    def test_escalate_scope_has_semantic_context(self):
        """ESCALATE (scope) notification includes semantic interpretation."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, notif_svc, _ = _make_controller(d)
                ctrl._config.escalation_timeout_seconds = 0.3
                verdict = MockEscalateScopeVerdict()

                await ctrl.handle_escalation(verdict)

                sent_notif = notif_svc.send.call_args[0][0]
                assert sent_notif.semantic_context != ""
                assert "web_network" in sent_notif.semantic_context.lower()
                assert "38%" in sent_notif.semantic_context

        asyncio.run(_test())

    def test_format_message_semantic_first(self):
        """Notification format puts semantic context before machine data."""
        notif = EscalationNotification(
            escalation_id="test123",
            tool_name="shell_execute",
            tool_group="shell",
            risk_tier="critical",
            fidelity_score=0.35,
            explanation="Boundary violation",
            timestamp=time.time(),
            boundary_triggered=True,
            decision="escalate",
            semantic_context="The agent attempted a dangerous action.",
        )
        msg = notif.format_message()
        lines = msg.split("\n")
        # First line: header
        assert "ESCALATION" in lines[0]
        # Semantic context appears before machine metadata
        sem_idx = msg.index("The agent attempted")
        tool_idx = msg.index("Tool: shell_execute")
        assert sem_idx < tool_idx

    def test_format_message_escalate_scope_options(self):
        """ESCALATE notification shows APPROVE and DENY options."""
        notif = EscalationNotification(
            escalation_id="test456",
            tool_name="web_fetch",
            tool_group="web_network",
            risk_tier="medium",
            fidelity_score=0.38,
            explanation="Outside scope",
            timestamp=time.time(),
            decision="escalate",
            semantic_context="The agent drifted from its purpose.",
        )
        msg = notif.format_message()
        assert "ESCALATION" in msg
        assert "APPROVE" in msg
        assert "DENY" in msg

    def test_format_message_escalate_options(self):
        """ESCALATE notification shows APPROVE and DENY options."""
        notif = EscalationNotification(
            escalation_id="test789",
            tool_name="shell_execute",
            tool_group="shell",
            risk_tier="critical",
            fidelity_score=0.35,
            explanation="Boundary violation",
            timestamp=time.time(),
            decision="escalate",
            semantic_context="Requires authorization.",
        )
        msg = notif.format_message()
        assert "ESCALATION" in msg
        assert "APPROVE" in msg
        assert "DENY" in msg


# ---------------------------------------------------------------------------
# Tests: Audit hash chain (G1)
# ---------------------------------------------------------------------------

class TestAuditHashChain:
    """Test hash chain linking audit receipts for deletion detection."""

    def test_audit_entries_have_prev_receipt_hash(self):
        """Every audit entry contains a prev_receipt_hash field."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                ctrl._config.escalation_timeout_seconds = 0.2
                verdict = MockVerdict()

                await ctrl.handle_escalation(verdict)

                audit_file = Path(d) / "escalations.jsonl"
                with open(audit_file) as f:
                    for line in f:
                        entry = json.loads(line)
                        assert "prev_receipt_hash" in entry

        asyncio.run(_test())

    def test_hash_chain_links_entries(self):
        """Each entry's prev_receipt_hash matches SHA-256 of previous entry."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                ctrl._config.escalation_timeout_seconds = 0.2

                # Two escalations to get multiple audit entries
                await ctrl.handle_escalation(MockVerdict())
                await ctrl.handle_escalation(MockVerdict())

                audit_file = Path(d) / "escalations.jsonl"
                entries = []
                with open(audit_file) as f:
                    for line in f:
                        entries.append(json.loads(line))

                # First entry should have empty prev_receipt_hash
                assert entries[0]["prev_receipt_hash"] == ""

                # Subsequent entries chain to previous
                for i in range(1, len(entries)):
                    prev = entries[i - 1]
                    prev_canonical = json.dumps(
                        prev, sort_keys=True, separators=(",", ":"), default=str
                    ).encode("utf-8")
                    expected_hash = hashlib.sha256(prev_canonical).hexdigest()
                    assert entries[i]["prev_receipt_hash"] == expected_hash, (
                        f"Entry {i} hash chain broken: expected {expected_hash}, "
                        f"got {entries[i]['prev_receipt_hash']}"
                    )

        asyncio.run(_test())

    def test_deletion_detected_by_hash_chain(self):
        """Deleting an entry breaks the hash chain (verifiable)."""
        async def _test():
            with tempfile.TemporaryDirectory() as d:
                ctrl, _, _ = _make_controller(d)
                ctrl._config.escalation_timeout_seconds = 0.2

                await ctrl.handle_escalation(MockVerdict())
                await ctrl.handle_escalation(MockVerdict())

                audit_file = Path(d) / "escalations.jsonl"
                entries = []
                with open(audit_file) as f:
                    for line in f:
                        entries.append(json.loads(line))

                assert len(entries) >= 4  # 2 escalations x (initiated + notified) minimum

                # Remove an entry from the middle and verify chain breaks
                removed_idx = 2
                tampered = entries[:removed_idx] + entries[removed_idx + 1:]

                # Verify chain is broken at the deletion point
                chain_valid = True
                for i in range(1, len(tampered)):
                    prev = tampered[i - 1]
                    prev_canonical = json.dumps(
                        prev, sort_keys=True, separators=(",", ":"), default=str
                    ).encode("utf-8")
                    expected = hashlib.sha256(prev_canonical).hexdigest()
                    if tampered[i]["prev_receipt_hash"] != expected:
                        chain_valid = False
                        break

                assert not chain_valid, "Hash chain should break when entry deleted"

        asyncio.run(_test())

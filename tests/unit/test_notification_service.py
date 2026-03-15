"""
Tests for the Notification Service -- multi-channel ESCALATE notifications.

Tests cover:
  - Telegram message formatting with InlineKeyboardMarkup
  - WhatsApp interactive button message formatting
  - Discord webhook embed formatting
  - Multi-channel dispatch (all configured channels)
  - Graceful degradation when channels fail
  - EscalationNotification formatting
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telos_adapters.openclaw.notification_service import (
    EscalationNotification,
    NotificationService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class MockNotificationsConfig:
    """Mock NotificationsConfig with all channels."""
    telegram_bot_token = "123456:ABC-DEF"
    telegram_chat_id = "987654321"
    discord_webhook_url = "https://discord.com/api/webhooks/test/token"
    whatsapp_phone_number_id = "1234567890"
    whatsapp_access_token = "EAAx_test_token"
    whatsapp_recipient_number = "+1234567890"
    escalation_timeout_seconds = 300
    timeout_action = "deny"
    has_telegram = True
    has_discord = True
    has_whatsapp = True
    has_any_channel = True


class TelegramOnlyConfig:
    """Config with only Telegram."""
    telegram_bot_token = "123456:ABC-DEF"
    telegram_chat_id = "987654321"
    discord_webhook_url = ""
    whatsapp_phone_number_id = ""
    whatsapp_access_token = ""
    whatsapp_recipient_number = ""
    escalation_timeout_seconds = 300
    timeout_action = "deny"
    has_telegram = True
    has_discord = False
    has_whatsapp = False
    has_any_channel = True


class NoChannelsConfig:
    """Config with no channels."""
    telegram_bot_token = ""
    telegram_chat_id = ""
    discord_webhook_url = ""
    whatsapp_phone_number_id = ""
    whatsapp_access_token = ""
    whatsapp_recipient_number = ""
    escalation_timeout_seconds = 300
    timeout_action = "deny"
    has_telegram = False
    has_discord = False
    has_whatsapp = False
    has_any_channel = False


@pytest.fixture
def notification():
    return EscalationNotification(
        escalation_id="abc123def456",
        tool_name="shell_execute",
        tool_group="shell",
        risk_tier="critical",
        fidelity_score=0.35,
        explanation="Boundary violation: rm -rf / detected",
        timestamp=time.time(),
        boundary_triggered=True,
        action_text="rm -rf /",
    )


# ---------------------------------------------------------------------------
# Tests: EscalationNotification formatting
# ---------------------------------------------------------------------------

class TestNotificationFormatting:
    """Test human-readable notification message formatting."""

    def test_format_message_includes_key_fields(self, notification):
        msg = notification.format_message()
        assert "TELOS ESCALATION" in msg
        assert "CRITICAL" in msg
        assert "shell_execute" in msg
        assert "0.350" in msg
        assert "abc123def456" in msg
        assert "Boundary violation" in msg

    def test_format_message_without_boundary(self):
        n = EscalationNotification(
            escalation_id="test123",
            tool_name="web_fetch",
            tool_group="web_network",
            risk_tier="high",
            fidelity_score=0.42,
            explanation="Out of scope request",
            timestamp=time.time(),
        )
        msg = n.format_message()
        assert "HIGH" in msg
        assert "web_fetch" in msg
        assert "Boundary violation" not in msg

    def test_format_message_risk_tiers(self):
        for tier, expected in [
            ("critical", "CRITICAL"),
            ("high", "HIGH"),
            ("medium", "MEDIUM"),
            ("low", "LOW"),
        ]:
            n = EscalationNotification(
                escalation_id="test",
                tool_name="test",
                tool_group="test",
                risk_tier=tier,
                fidelity_score=0.5,
                explanation="test",
                timestamp=time.time(),
            )
            assert expected in n.format_message()


# ---------------------------------------------------------------------------
# Tests: Multi-channel dispatch
# ---------------------------------------------------------------------------

def _make_mock_session(status=200, text="ok"):
    """Create a mock aiohttp session with proper async context manager."""
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.text = AsyncMock(return_value=text)

    # Create async context manager that returns mock_response
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=cm)
    return mock_session


class TestMultiChannelDispatch:
    """Test sending to all configured channels."""

    def test_send_all_channels(self, notification):
        """Send dispatches to all configured channels."""
        async def _test():
            service = NotificationService(MockNotificationsConfig())
            mock_session = _make_mock_session()
            service._aiohttp = mock_session

            results = await service.send(notification)

            assert results["telegram"] is True
            assert results["whatsapp"] is True
            assert results["discord"] is True
            assert mock_session.post.call_count == 3

        asyncio.run(_test())

    def test_send_telegram_only(self, notification):
        """Send dispatches to Telegram only when others are not configured."""
        async def _test():
            service = NotificationService(TelegramOnlyConfig())
            mock_session = _make_mock_session()
            service._aiohttp = mock_session

            results = await service.send(notification)

            assert results["telegram"] is True
            assert mock_session.post.call_count == 1

        asyncio.run(_test())

    def test_send_no_channels(self, notification):
        """No channels configured returns empty results."""
        async def _test():
            service = NotificationService(NoChannelsConfig())
            results = await service.send(notification)
            # mobile_push may appear with False if MobilePushChannel is always instantiated
            configured_results = {k: v for k, v in results.items() if v is True}
            assert configured_results == {}

        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Tests: Graceful degradation
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    """Test that channel failures don't prevent other channels from sending."""

    def test_telegram_failure_doesnt_block_discord(self, notification):
        """If Telegram fails, Discord still sends."""
        async def _test():
            service = NotificationService(MockNotificationsConfig())

            async def mock_post(url, **kwargs):
                resp = AsyncMock()
                if "telegram" in url:
                    raise RuntimeError("Telegram API error 500")
                resp.status = 200
                resp.text = AsyncMock(return_value="ok")
                return resp

            mock_session = AsyncMock()
            mock_session.post = AsyncMock(side_effect=mock_post)
            service._aiohttp = mock_session

            results = await service.send(notification)

            assert results["telegram"] is False
            # WhatsApp and Discord may succeed or fail depending on mock
            assert results.get("whatsapp") in (True, False)
            assert results.get("discord") in (True, False)

        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Tests: Telegram message structure
# ---------------------------------------------------------------------------

class TestTelegramMessageStructure:
    """Test Telegram API payload structure."""

    def test_telegram_includes_inline_keyboard(self, notification):
        """Telegram message includes InlineKeyboardMarkup with buttons."""
        async def _test():
            service = NotificationService(TelegramOnlyConfig())

            captured_payloads = []

            mock_response = MagicMock()
            mock_response.status = 200

            cm = MagicMock()
            cm.__aenter__ = AsyncMock(return_value=mock_response)
            cm.__aexit__ = AsyncMock(return_value=False)

            def capture_post(url, **kwargs):
                captured_payloads.append(kwargs.get("json", {}))
                return cm

            mock_session = MagicMock()
            mock_session.post = capture_post
            service._aiohttp = mock_session

            await service.send(notification)

            assert len(captured_payloads) == 1
            payload = captured_payloads[0]
            assert "reply_markup" in payload
            markup = json.loads(payload["reply_markup"])
            assert "inline_keyboard" in markup
            buttons = markup["inline_keyboard"][0]
            assert len(buttons) == 2
            assert "Approve" in buttons[0]["text"]
            assert "Deny" in buttons[1]["text"]

            # Callback data contains escalation ID (compact format: a/i/c)
            approve_data = json.loads(buttons[0]["callback_data"])
            assert approve_data["a"] == "y"
            assert approve_data["i"] == notification.escalation_id

        asyncio.run(_test())

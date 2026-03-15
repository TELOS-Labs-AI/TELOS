"""
Tests for the TKeys Ed25519 Cryptographic Gate.

Covers:
  - GateSigner: sign/verify round-trip, tamper detection, wrong key rejection
  - GateRecord: TTL expiry, canonical form determinism
  - Daemon gate awareness: gate file read/cache, observe mode, enforce mode
"""

import asyncio
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from telos_governance.types import ActionDecision, DirectionLevel


# ---------------------------------------------------------------------------
# Embedding helpers (reuse from test_openclaw_adapter.py)
# ---------------------------------------------------------------------------

def _make_embed_fn(dim: int = 32):
    """Create a deterministic hash-based embedding function."""
    _cache = {}

    def embed(text: str) -> np.ndarray:
        if text not in _cache:
            h = hash(text) % 10000
            rng = np.random.RandomState(h)
            vec = rng.randn(dim)
            _cache[text] = vec / np.linalg.norm(vec)
        return _cache[text]

    return embed


# ============================================================================
# GateSigner Tests
# ============================================================================

class TestGateSigner:
    """Test Ed25519 gate signing and verification."""

    def test_sign_and_verify_round_trip(self):
        """Sign an open gate transition, verify passes with correct key."""
        from telos_governance.gate_signer import GateSigner

        signer = GateSigner.generate()
        record = signer.sign_transition("open", "enforce", ttl_hours=0)

        assert record.state == "open"
        assert record.mode == "enforce"
        assert record.ttl_hours == 0
        assert record.signature != ""
        assert record.public_key != ""
        assert record.actor == signer.fingerprint

        # Verify with correct public key
        assert GateSigner.verify(record, signer.public_key_bytes) is True

    def test_tampered_payload_fails(self):
        """Modifying state after signing causes verification to fail."""
        from telos_governance.gate_signer import GateSigner, GateSigningError

        signer = GateSigner.generate()
        record = signer.sign_transition("closed", "enforce", ttl_hours=0)

        # Tamper with the state
        record.state = "open"

        with pytest.raises(GateSigningError, match="signature verification failed"):
            GateSigner.verify(record, signer.public_key_bytes)

    def test_wrong_key_fails(self):
        """Verify with a different key pair rejects the signature."""
        from telos_governance.gate_signer import GateSigner, GateSigningError

        signer1 = GateSigner.generate()
        signer2 = GateSigner.generate()

        record = signer1.sign_transition("closed", "observe", ttl_hours=0)

        with pytest.raises(GateSigningError, match="signature verification failed"):
            GateSigner.verify(record, signer2.public_key_bytes)

    def test_ttl_expiry(self):
        """Sign with ttl_hours=1, mock time forward, is_expired() returns True."""
        from telos_governance.gate_signer import GateSigner

        signer = GateSigner.generate()
        record = signer.sign_transition("closed", "enforce", ttl_hours=1)

        # Not expired yet
        assert GateSigner.is_expired(record) is False

        # Mock time 2 hours into the future
        with patch("telos_governance.gate_signer.time") as mock_time:
            mock_time.time.return_value = record.timestamp + 7200  # 2 hours
            assert GateSigner.is_expired(record) is True

    def test_ttl_zero_never_expires(self):
        """ttl_hours=0 means indefinite -- is_expired() returns False."""
        from telos_governance.gate_signer import GateSigner

        signer = GateSigner.generate()
        record = signer.sign_transition("closed", "enforce", ttl_hours=0)

        # Mock time far into the future
        with patch("telos_governance.gate_signer.time") as mock_time:
            mock_time.time.return_value = record.timestamp + 365 * 24 * 3600  # 1 year
            assert GateSigner.is_expired(record) is False

    def test_canonical_form_deterministic(self):
        """Same inputs always produce the same canonical bytes."""
        from telos_governance.gate_signer import GateSigner

        args = ("closed", "enforce", "abc123", 1709000000.0, 24)

        form1 = GateSigner.canonical_form(*args)
        form2 = GateSigner.canonical_form(*args)

        assert form1 == form2
        assert isinstance(form1, bytes)

        # Verify it's valid JSON with sorted keys
        parsed = json.loads(form1)
        assert list(parsed.keys()) == sorted(parsed.keys())


# ============================================================================
# Daemon Gate Integration Tests
# ============================================================================

class TestDaemonGateIntegration:
    """Test daemon-level gate awareness (file read, cache, handler behavior)."""

    def test_gate_file_read_and_cache(self):
        """Write gate file, read twice, verify cache hit (no re-read within TTL)."""
        from telos_governance.gate_signer import GateSigner

        signer = GateSigner.generate()
        record = signer.sign_transition("closed", "enforce", ttl_hours=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            gate_file = Path(tmpdir) / "gate"
            gate_file.write_text(json.dumps(record.to_dict()))

            # Patch GATE_FILE to use our temp file
            with patch("telos_adapters.openclaw.daemon.GATE_FILE", gate_file):
                from telos_adapters.openclaw.daemon import (
                    _read_gate_state,
                    _gate_cache,
                    _invalidate_gate_cache,
                )

                # Reset cache
                _invalidate_gate_cache()

                # First read
                result1 = _read_gate_state(force=True)
                assert result1 is not None
                assert result1["state"] == "closed"
                assert result1["mode"] == "enforce"

                read_at = _gate_cache["read_at"]
                assert read_at > 0

                # Second read (should hit cache)
                result2 = _read_gate_state()
                assert result2 is not None
                assert result2["state"] == "closed"
                # Cache timestamp should be unchanged (no re-read)
                assert _gate_cache["read_at"] == read_at

                # Clean up cache
                _invalidate_gate_cache()

    def _make_mock_hook(self):
        """Create a mock GovernanceHook returning a standard verdict."""
        from telos_adapters.openclaw.governance_hook import GovernanceVerdict

        hook = MagicMock()
        hook.score_action.return_value = GovernanceVerdict(
            allowed=False,
            decision="clarify",
            fidelity=0.55,
            tool_group="runtime",
            telos_tool_name="runtime_execute",
            risk_tier="critical",
            is_cross_group=False,
            purpose_fidelity=0.55,
            scope_fidelity=0.55,
            boundary_violation=0.0,
            tool_fidelity=0.55,
            chain_continuity=0.55,
        )
        hook.stats = {"total_scored": 1, "total_blocked": 0}
        hook.reset_chain = MagicMock()
        return hook

    def test_observe_mode_verdict_fields(self):
        """Score with observe mode: verify shadow fields present and allowed=True."""
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage

        hook = self._make_mock_hook()
        handler = create_message_handler(hook, gate_mode="observe")

        msg = IPCMessage(
            type="score",
            request_id="obs-1",
            tool_name="Bash",
            action_text="rm -rf /tmp/test",
            args={"command": "rm -rf /tmp/test"},
        )

        response = asyncio.run(handler(msg))
        assert response.type == "verdict"
        data = response.data

        # Observe mode forces allowed=True
        assert data["allowed"] is True
        assert data["decision"] == "execute"

        # Shadow fields preserve original decision
        assert data["gate_mode"] == "observe"
        assert data["observe_shadow_decision"] == "clarify"
        assert data["observe_shadow_allowed"] is False

        # Explanation mentions observe mode
        assert "OBSERVE MODE" in data["explanation"]

    def test_escalate_when_gate_closed_enforce(self):
        """Gate closed+enforce: score returns ESCALATE with gate explanation."""
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage

        hook = self._make_mock_hook()
        handler = create_message_handler(hook, gate_mode="enforce")

        msg = IPCMessage(
            type="score",
            request_id="enf-1",
            tool_name="Read",
            action_text="Read the secrets file",
            args={"file_path": "/etc/passwd"},
        )

        response = asyncio.run(handler(msg))
        assert response.type == "verdict"
        data = response.data

        # Enforce mode blocks everything -- gate returns INERT (not escalate)
        # because the gate short-circuits before scoring. Post b06d975 the
        # daemon returns inert when the gate is closed in enforce mode.
        assert data["allowed"] is False
        assert data["decision"] == "inert"
        assert data["gate_mode"] == "enforce"
        assert data.get("gate_closed") is True
        assert "CLOSED" in data["explanation"]
        assert "Ed25519" in data["explanation"]

        # Hook should NOT have been called (gate short-circuits)
        hook.score_action.assert_not_called()

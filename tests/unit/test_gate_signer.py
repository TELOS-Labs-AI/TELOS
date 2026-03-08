"""
Tests for the TKeys Ed25519 Cryptographic Gate.

Covers:
  - GateSigner: sign/verify round-trip, tamper detection, wrong key rejection
  - GateRecord: TTL expiry, canonical form determinism
  - Daemon gate awareness: gate file read/cache, observe mode, enforce mode
"""

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from telos_governance.types import ActionDecision, DirectionLevel


# ---------------------------------------------------------------------------
# Embedding helpers (reused across test modules)
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


# ---------------------------------------------------------------------------
# Mock the adapter modules (not shipped in the public release)
# ---------------------------------------------------------------------------

# In-memory gate cache for the mock daemon
_gate_cache = {"record": None, "read_at": 0}
_mock_gate_file_path = None  # Set by test via patch


def _invalidate_gate_cache():
    """Reset the in-memory gate cache."""
    _gate_cache["record"] = None
    _gate_cache["read_at"] = 0


def _read_gate_state(force=False):
    """Read gate state from file (mock implementation)."""
    if not force and _gate_cache["record"] is not None:
        return _gate_cache["record"]

    if _mock_gate_file_path is None or not _mock_gate_file_path.exists():
        return None

    data = json.loads(_mock_gate_file_path.read_text())
    _gate_cache["record"] = data
    _gate_cache["read_at"] = time.time()
    return data


def _install_adapter_mocks():
    """Install mock modules for the governance adapter layer."""
    adapters_pkg = ModuleType("telos_adapters")
    adapters_pkg.__path__ = []
    agent_pkg = ModuleType("telos_adapters.agent")
    agent_pkg.__path__ = []

    # GovernanceVerdict mock
    governance_hook_mod = ModuleType("telos_adapters.agent.governance_hook")

    class GovernanceVerdict:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    governance_hook_mod.GovernanceVerdict = GovernanceVerdict

    # IPCMessage mock
    ipc_server_mod = ModuleType("telos_adapters.agent.ipc_server")

    class IPCMessage:
        def __init__(self, type, request_id, tool_name, action_text, args=None):
            self.type = type
            self.request_id = request_id
            self.tool_name = tool_name
            self.action_text = action_text
            self.args = args or {}

    ipc_server_mod.IPCMessage = IPCMessage

    # Daemon mock with gate awareness
    daemon_mod = ModuleType("telos_adapters.agent.daemon")

    class _VerdictResponse:
        def __init__(self, type, data):
            self.type = type
            self.data = data

    def create_message_handler(hook, gate_mode=None, codebase_policies=None, project_root=""):
        """Mock handler that implements gate mode logic."""
        async def handler(msg):
            if msg.type != "score":
                return _VerdictResponse("error", {"message": "unknown type"})

            # Gate closed + enforce = INERT (short-circuit)
            if gate_mode == "enforce":
                return _VerdictResponse("verdict", {
                    "allowed": False,
                    "decision": "inert",
                    "gate_mode": "enforce",
                    "gate_closed": True,
                    "explanation": "GATE CLOSED — Ed25519 signed gate is CLOSED in enforce mode.",
                })

            # Score via hook
            verdict = hook.score_action(
                tool_name=msg.tool_name,
                action_text=msg.action_text,
            )

            data = {
                "allowed": verdict.allowed,
                "decision": verdict.decision,
            }

            # Observe mode: override to allowed=True, preserve shadow
            if gate_mode == "observe":
                data["allowed"] = True
                data["decision"] = "execute"
                data["gate_mode"] = "observe"
                data["observe_shadow_decision"] = verdict.decision
                data["observe_shadow_allowed"] = verdict.allowed
                data["explanation"] = "OBSERVE MODE — action permitted for observation."

            return _VerdictResponse("verdict", data)

        return handler

    # Expose gate cache functions on daemon module
    daemon_mod.GATE_FILE = None
    daemon_mod._read_gate_state = _read_gate_state
    daemon_mod._gate_cache = _gate_cache
    daemon_mod._invalidate_gate_cache = _invalidate_gate_cache
    daemon_mod.create_message_handler = create_message_handler

    sys.modules["telos_adapters"] = adapters_pkg
    sys.modules["telos_adapters.agent"] = agent_pkg
    sys.modules["telos_adapters.agent.governance_hook"] = governance_hook_mod
    sys.modules["telos_adapters.agent.ipc_server"] = ipc_server_mod
    sys.modules["telos_adapters.agent.daemon"] = daemon_mod


_install_adapter_mocks()


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
        global _mock_gate_file_path

        from telos_governance.gate_signer import GateSigner
        from telos_adapters.agent.daemon import (
            _read_gate_state,
            _gate_cache,
            _invalidate_gate_cache,
        )

        signer = GateSigner.generate()
        record = signer.sign_transition("closed", "enforce", ttl_hours=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            gate_file = Path(tmpdir) / "gate"
            gate_file.write_text(json.dumps(record.to_dict()))

            # Point the mock at our temp file
            _mock_gate_file_path = gate_file

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

            # Clean up
            _invalidate_gate_cache()
            _mock_gate_file_path = None

    def _make_mock_hook(self):
        """Create a mock GovernanceHook returning a standard verdict."""
        from telos_adapters.agent.governance_hook import GovernanceVerdict

        hook = MagicMock()
        hook.score_action.return_value = GovernanceVerdict(
            allowed=False,
            decision="suggest",
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
        from telos_adapters.agent.daemon import create_message_handler
        from telos_adapters.agent.ipc_server import IPCMessage

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
        assert data["observe_shadow_decision"] == "suggest"
        assert data["observe_shadow_allowed"] is False

        # Explanation mentions observe mode
        assert "OBSERVE MODE" in data["explanation"]

    def test_inert_when_gate_closed_enforce(self):
        """Gate closed+enforce: score returns INERT with gate explanation."""
        from telos_adapters.agent.daemon import create_message_handler
        from telos_adapters.agent.ipc_server import IPCMessage

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

        # Enforce mode blocks everything
        assert data["allowed"] is False
        assert data["decision"] == "inert"
        assert data["gate_mode"] == "enforce"
        assert data.get("gate_closed") is True
        assert "CLOSED" in data["explanation"]
        assert "Ed25519" in data["explanation"]

        # Hook should NOT have been called (gate short-circuits)
        hook.score_action.assert_not_called()

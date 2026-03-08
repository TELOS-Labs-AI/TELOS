"""
Tests for TKeys Codebase Access Policies.

Covers:
  - CodebasePolicySigner: sign/verify round-trip, tamper detection, wrong key
  - CodebasePolicy: TTL expiry
  - Path matching: prefix match, no-match
  - Access control: write-to-read_only escalate, no-policy fail-closed
  - Daemon integration: handler returns ESCALATE without calling hook.score_action
"""

import asyncio
import json
import time
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# CodebasePolicySigner Tests
# ============================================================================

class TestCodebasePolicySigner:
    """Test Ed25519 codebase policy signing and verification."""

    def test_sign_and_verify_policy_round_trip(self):
        """Sign a policy, verify passes with correct key."""
        from telos_governance.codebase_policy import CodebasePolicySigner

        signer = CodebasePolicySigner.generate()
        policy = signer.sign_policy(
            collection="telos_governance",
            paths=["telos_governance/", "telos_core/"],
            access_level="read_only",
            ttl_hours=0,
        )

        assert policy.collection == "telos_governance"
        assert policy.paths == ["telos_core/", "telos_governance/"]  # sorted
        assert policy.access_level == "read_only"
        assert policy.ttl_hours == 0
        assert policy.signature != ""
        assert policy.public_key != ""
        assert policy.actor == signer.fingerprint

        # Verify with correct public key
        assert CodebasePolicySigner.verify(policy, signer.public_key_bytes) is True

    def test_tampered_policy_fails(self):
        """Modify access_level after signing, verify rejects."""
        from telos_governance.codebase_policy import (
            CodebasePolicySigner, CodebasePolicyError,
        )

        signer = CodebasePolicySigner.generate()
        policy = signer.sign_policy(
            collection="stewartbot",
            paths=["stewartbot/"],
            access_level="read_write",
            ttl_hours=0,
        )

        # Tamper with access_level
        policy.access_level = "read_only"

        with pytest.raises(CodebasePolicyError, match="signature verification failed"):
            CodebasePolicySigner.verify(policy, signer.public_key_bytes)

    def test_wrong_key_rejects_policy(self):
        """Verify with a different key pair, rejects."""
        from telos_governance.codebase_policy import (
            CodebasePolicySigner, CodebasePolicyError,
        )

        signer1 = CodebasePolicySigner.generate()
        signer2 = CodebasePolicySigner.generate()

        policy = signer1.sign_policy(
            collection="openclaw_workspace",
            paths=["telos_adapters/openclaw/"],
            access_level="read_write",
            ttl_hours=0,
        )

        with pytest.raises(CodebasePolicyError, match="signature verification failed"):
            CodebasePolicySigner.verify(policy, signer2.public_key_bytes)

    def test_policy_ttl_expiry(self):
        """Sign with ttl_hours=1, mock time forward, is_expired() returns True."""
        from telos_governance.codebase_policy import CodebasePolicySigner

        signer = CodebasePolicySigner.generate()
        policy = signer.sign_policy(
            collection="telos_governance",
            paths=["telos_governance/"],
            access_level="read_only",
            ttl_hours=1,
        )

        # Not expired yet
        assert CodebasePolicySigner.is_expired(policy) is False

        # Mock time 2 hours into the future
        with patch("telos_governance.codebase_policy.time") as mock_time:
            mock_time.time.return_value = policy.timestamp + 7200  # 2 hours
            assert CodebasePolicySigner.is_expired(policy) is True


# ============================================================================
# Path Matching Tests
# ============================================================================

class TestPathMatching:
    """Test file path matching against policy prefixes."""

    def test_path_matching(self):
        """File path matches correct policy prefix; unmatched returns None."""
        from telos_governance.codebase_policy import (
            CodebasePolicySigner, find_matching_policy,
        )

        signer = CodebasePolicySigner.generate()

        policy_gov = signer.sign_policy(
            collection="telos_governance",
            paths=["telos_governance/", "telos_core/"],
            access_level="read_only",
        )
        policy_oc = signer.sign_policy(
            collection="openclaw_workspace",
            paths=["telos_adapters/openclaw/"],
            access_level="read_write",
        )

        policies = [policy_gov, policy_oc]
        project_root = "/opt/project"

        # Matches telos_governance policy
        matched = find_matching_policy(
            "/opt/project/telos_governance/config.py",
            policies, project_root,
        )
        assert matched is not None
        assert matched.collection == "telos_governance"

        # Matches telos_core prefix in same policy
        matched = find_matching_policy(
            "/opt/project/telos_core/constants.py",
            policies, project_root,
        )
        assert matched is not None
        assert matched.collection == "telos_governance"

        # Matches openclaw policy
        matched = find_matching_policy(
            "/opt/project/telos_adapters/openclaw/daemon.py",
            policies, project_root,
        )
        assert matched is not None
        assert matched.collection == "openclaw_workspace"

        # No match for README.md
        matched = find_matching_policy(
            "/opt/project/README.md",
            policies, project_root,
        )
        assert matched is None


# ============================================================================
# Access Control Tests
# ============================================================================

class TestAccessControl:
    """Test check_access authorization logic."""

    def test_write_to_read_only_escalates(self):
        """Write tool + read_only policy -> denied with unauthorized_write."""
        from telos_governance.codebase_policy import (
            CodebasePolicySigner, check_access,
        )

        signer = CodebasePolicySigner.generate()
        policy = signer.sign_policy(
            collection="telos_governance",
            paths=["telos_governance/", "telos_core/"],
            access_level="read_only",
        )

        allowed, reason, matched = check_access(
            "Write",
            "telos_governance/config.py",
            [policy],
            "",
        )

        assert allowed is False
        assert reason == "unauthorized_write"
        assert matched is not None
        assert matched.collection == "telos_governance"

    def test_no_policy_fails_closed(self):
        """File path not in any collection -> denied with no_policy."""
        from telos_governance.codebase_policy import (
            CodebasePolicySigner, check_access,
        )

        signer = CodebasePolicySigner.generate()
        policy = signer.sign_policy(
            collection="telos_governance",
            paths=["telos_governance/"],
            access_level="read_only",
        )

        allowed, reason, matched = check_access(
            "Read",
            "some_other_dir/file.py",
            [policy],
            "",
        )

        assert allowed is False
        assert reason == "no_policy"
        assert matched is None

    def test_case_insensitive_write_blocked(self):
        """Lowercase 'write' must be detected as a write tool (CVE fix)."""
        from telos_governance.codebase_policy import (
            CodebasePolicySigner, check_access,
        )

        signer = CodebasePolicySigner.generate()
        policy = signer.sign_policy(
            collection="telos_governance",
            paths=["telos_governance/"],
            access_level="read_only",
        )

        for variant in ("write", "WRITE", "Write", " Write ", "edit", "EDIT", "multiedit"):
            allowed, reason, _ = check_access(
                variant,
                "telos_governance/config.py",
                [policy],
                "",
            )
            assert allowed is False, f"Tool name '{variant}' should be blocked on read_only"
            assert reason == "unauthorized_write"

    def test_case_insensitive_read_allowed(self):
        """Case variants of read tools must still be allowed."""
        from telos_governance.codebase_policy import (
            CodebasePolicySigner, check_access,
        )

        signer = CodebasePolicySigner.generate()
        policy = signer.sign_policy(
            collection="telos_governance",
            paths=["telos_governance/"],
            access_level="read_only",
        )

        for variant in ("read", "READ", "Read", " Read ", "glob", "GREP", "ListDir"):
            allowed, reason, _ = check_access(
                variant,
                "telos_governance/config.py",
                [policy],
                "",
            )
            assert allowed is True, f"Tool name '{variant}' should be allowed on read_only"
            assert reason == "read_allowed"

    def test_unknown_tool_denied_by_default(self):
        """Unknown tool names must be treated as writes (deny-by-default)."""
        from telos_governance.codebase_policy import (
            CodebasePolicySigner, check_access,
        )

        signer = CodebasePolicySigner.generate()
        policy = signer.sign_policy(
            collection="telos_governance",
            paths=["telos_governance/"],
            access_level="read_only",
        )

        for tool in ("CustomTool", "anything", "", "   "):
            allowed, reason, _ = check_access(
                tool,
                "telos_governance/config.py",
                [policy],
                "",
            )
            assert allowed is False, f"Unknown tool '{tool}' should be denied on read_only"
            assert reason == "unauthorized_write"


# ============================================================================
# Daemon Handler Integration Test
# ============================================================================

class TestDaemonPolicyCheck:
    """Test daemon handler codebase policy enforcement."""

    def _make_mock_hook(self):
        """Create a mock GovernanceHook returning a standard verdict."""
        from telos_adapters.openclaw.governance_hook import GovernanceVerdict

        hook = MagicMock()
        hook.score_action.return_value = GovernanceVerdict(
            allowed=True,
            decision="execute",
            fidelity=0.90,
            tool_group="runtime",
            telos_tool_name="runtime_execute",
            risk_tier="medium",
            is_cross_group=False,
        )
        hook.stats = {"total_scored": 0, "total_blocked": 0}
        hook.reset_chain = MagicMock()
        return hook

    def test_daemon_policy_check_escalate(self):
        """Write tool + read_only policy -> ESCALATE, hook.score_action NOT called."""
        from telos_governance.codebase_policy import CodebasePolicySigner
        from telos_adapters.openclaw.daemon import create_message_handler
        from telos_adapters.openclaw.ipc_server import IPCMessage

        signer = CodebasePolicySigner.generate()
        policy = signer.sign_policy(
            collection="telos_governance",
            paths=["telos_governance/", "telos_core/"],
            access_level="read_only",
        )

        hook = self._make_mock_hook()
        handler = create_message_handler(
            hook,
            codebase_policies=[policy],
            project_root="/project",
        )

        msg = IPCMessage(
            type="score",
            request_id="pol-1",
            tool_name="Write",
            action_text="Write to governance config",
            args={"file_path": "/project/telos_governance/config.py"},
        )

        response = asyncio.run(handler(msg))
        assert response.type == "verdict"
        data = response.data

        # Escalated due to policy violation
        assert data["allowed"] is False
        assert data["decision"] == "escalate"
        assert data["policy_violation"] is True
        assert data["policy_reason"] == "unauthorized_write"
        assert data["policy_collection"] == "telos_governance"
        assert data["policy_access_level"] == "read_only"
        assert data["human_required"] is True
        assert "CODEBASE POLICY VIOLATION" in data["explanation"]

        # Hook should NOT have been called (policy short-circuits)
        hook.score_action.assert_not_called()

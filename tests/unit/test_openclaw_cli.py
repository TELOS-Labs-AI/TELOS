"""
Unit tests for TELOS OpenClaw CLI commands (telos agent + telos service).

Tests all 8 CLI commands added in Milestone 3:
    telos agent init           -- Setup wizard
    telos agent status         -- Daemon health check
    telos agent monitor        -- Live monitoring
    telos agent history        -- Decision history
    telos agent test           -- Test scenarios
    telos agent block-policy   -- Preset policy view
    telos service install      -- System service install
    telos service uninstall    -- System service remove

Uses Click's CliRunner for isolated CLI invocation testing.
All tests mock external dependencies (daemon, filesystem, IPC).
"""

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from click.testing import CliRunner

from telos_governance.cli import main


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def runner():
    """Click CliRunner for invoking CLI commands."""
    return CliRunner(mix_stderr=False)


@pytest.fixture
def tmp_config(tmp_path):
    """Create a temporary openclaw.yaml config."""
    config = tmp_path / "openclaw.yaml"
    config.write_text("# test config\nagent_name: test\n")
    return config


@pytest.fixture
def mock_watchdog_stopped():
    """Mock Watchdog that reports daemon stopped."""
    with patch("telos_adapters.openclaw.watchdog.Watchdog") as cls:
        inst = MagicMock()
        inst.is_running.return_value = False
        inst.health_check.return_value = {
            "status": "stopped",
            "pid": None,
            "running": False,
            "uptime_seconds": None,
            "heartbeat_age_seconds": None,
            "heartbeat_stale": True,
        }
        cls.return_value = inst
        yield inst


@pytest.fixture
def mock_watchdog_running():
    """Mock Watchdog that reports daemon running."""
    with patch("telos_adapters.openclaw.watchdog.Watchdog") as cls:
        inst = MagicMock()
        inst.is_running.return_value = True
        inst.health_check.return_value = {
            "status": "ok",
            "pid": 12345,
            "running": True,
            "uptime_seconds": 3700.0,
            "heartbeat_age_seconds": 10.0,
            "heartbeat_stale": False,
        }
        cls.return_value = inst
        yield inst


# =============================================================================
# Tests: telos agent block-policy
# =============================================================================


class TestAgentBlockPolicy:
    """Tests for `telos agent block-policy`."""

    def test_show_all_presets(self, runner):
        result = runner.invoke(main, ["agent", "block-policy"])
        assert result.exit_code == 0
        assert "STRICT" in result.output
        assert "BALANCED" in result.output
        assert "PERMISSIVE" in result.output

    def test_show_single_preset(self, runner):
        result = runner.invoke(main, ["agent", "block-policy", "-p", "strict"])
        assert result.exit_code == 0
        assert "STRICT" in result.output
        # Should not show other presets
        assert "BALANCED" not in result.output
        assert "PERMISSIVE" not in result.output

    def test_json_output(self, runner):
        result = runner.invoke(main, ["agent", "block-policy", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "presets" in data
        assert "risk_tiers" in data
        assert "strict" in data["presets"]
        assert "balanced" in data["presets"]
        assert "permissive" in data["presets"]

    def test_json_strict_has_blocked_decisions(self, runner):
        result = runner.invoke(main, ["agent", "block-policy", "--json"])
        data = json.loads(result.output)
        strict = data["presets"]["strict"]
        assert "escalate" in strict["blocked_decisions"]
        assert "escalate" in strict["blocked_decisions"]

    def test_json_permissive_blocks_nothing(self, runner):
        result = runner.invoke(main, ["agent", "block-policy", "--json"])
        data = json.loads(result.output)
        assert data["presets"]["permissive"]["blocked_decisions"] == []

    def test_risk_tiers_present(self, runner):
        result = runner.invoke(main, ["agent", "block-policy", "--json"])
        data = json.loads(result.output)
        tiers = data["risk_tiers"]
        assert tiers["runtime"] == "critical"
        assert tiers["fs"] == "high"
        assert tiers["nodes"] == "medium"
        assert tiers["memory"] == "low"

    def test_human_readable_shows_risk_tiers(self, runner):
        result = runner.invoke(main, ["agent", "block-policy"])
        assert result.exit_code == 0
        assert "Tool Group Risk Tiers" in result.output
        assert "runtime" in result.output

    def test_no_color_mode(self, runner):
        result = runner.invoke(
            main, ["--no-color", "agent", "block-policy"]
        )
        assert result.exit_code == 0
        # Should still have content, just without ANSI codes
        assert "STRICT" in result.output


# =============================================================================
# Tests: telos agent init
# =============================================================================


class TestAgentInit:
    """Tests for `telos agent init`."""

    def test_init_creates_config(self, runner, tmp_path):
        dest = tmp_path / "out.yaml"
        result = runner.invoke(
            main, ["agent", "init", "--no-detect", "-o", str(dest)]
        )
        assert result.exit_code == 0
        assert dest.exists()
        assert "Config created" in result.output

    def test_init_shows_preset(self, runner, tmp_path):
        dest = tmp_path / "out.yaml"
        result = runner.invoke(
            main,
            ["agent", "init", "--no-detect", "-o", str(dest), "-p", "strict"],
        )
        assert result.exit_code == 0
        assert "STRICT" in result.output

    def test_init_detect_no_openclaw(self, runner, tmp_path):
        dest = tmp_path / "out.yaml"
        result = runner.invoke(
            main, ["agent", "init", "--detect", "-o", str(dest)]
        )
        assert result.exit_code == 0
        # Should show warning about OpenClaw not detected
        assert "not detected" in result.output or "detected" in result.output

    def test_init_shows_next_steps(self, runner, tmp_path):
        dest = tmp_path / "out.yaml"
        result = runner.invoke(
            main, ["agent", "init", "--no-detect", "-o", str(dest)]
        )
        assert result.exit_code == 0
        assert "Next steps" in result.output
        assert "telos config validate" in result.output
        assert "telos agent status" in result.output

    def test_init_existing_config_no_tty(self, runner, tmp_path):
        """When config exists and stdin is not a TTY, should overwrite."""
        dest = tmp_path / "out.yaml"
        dest.write_text("# old config")
        result = runner.invoke(
            main, ["agent", "init", "--no-detect", "-o", str(dest)]
        )
        assert result.exit_code == 0
        # CliRunner stdin is not a tty, so it should overwrite
        assert "Config" in result.output

    def test_init_permissive_preset(self, runner, tmp_path):
        dest = tmp_path / "out.yaml"
        result = runner.invoke(
            main,
            [
                "agent", "init", "--no-detect",
                "-o", str(dest),
                "-p", "permissive",
            ],
        )
        assert result.exit_code == 0
        assert "PERMISSIVE" in result.output
        assert "log-only" in result.output


# =============================================================================
# Tests: telos agent status
# =============================================================================


class TestAgentStatus:
    """Tests for `telos agent status`."""

    def test_status_daemon_stopped(self, runner, mock_watchdog_stopped):
        result = runner.invoke(main, ["agent", "status"])
        assert result.exit_code == 1  # Exit 1 when stopped
        assert "Stopped" in result.output

    def test_status_daemon_stopped_json(self, runner, mock_watchdog_stopped):
        result = runner.invoke(main, ["agent", "status", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["daemon"]["running"] is False
        assert data["governance"] is None

    @patch("telos_governance.cli._daemon_ipc")
    def test_status_daemon_running(
        self, mock_ipc, runner, mock_watchdog_running
    ):
        mock_ipc.return_value = {
            "data": {
                "governance_stats": {
                    "total_scored": 42,
                    "total_blocked": 3,
                    "total_escalated": 2,
                    "chain_length": 5,
                }
            }
        }
        result = runner.invoke(main, ["agent", "status"])
        assert result.exit_code == 0
        assert "Running" in result.output
        assert "42" in result.output

    @patch("telos_governance.cli._daemon_ipc")
    def test_status_running_json(
        self, mock_ipc, runner, mock_watchdog_running
    ):
        mock_ipc.return_value = {
            "data": {
                "governance_stats": {
                    "total_scored": 100,
                    "total_blocked": 10,
                    "total_escalated": 5,
                    "chain_length": 3,
                }
            }
        }
        result = runner.invoke(main, ["agent", "status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["daemon"]["running"] is True
        assert data["daemon"]["pid"] == 12345
        assert data["governance"]["total_scored"] == 100

    @patch("telos_governance.cli._daemon_ipc")
    def test_status_running_no_ipc(
        self, mock_ipc, runner, mock_watchdog_running
    ):
        """Daemon running but IPC fails."""
        mock_ipc.return_value = None
        result = runner.invoke(main, ["agent", "status"])
        assert result.exit_code == 0
        assert "Running" in result.output
        assert "Could not reach" in result.output

    def test_status_stale_heartbeat(self, runner):
        with patch("telos_adapters.openclaw.watchdog.Watchdog") as cls:
            inst = MagicMock()
            inst.is_running.return_value = True
            inst.health_check.return_value = {
                "status": "stale",
                "pid": 99999,
                "running": True,
                "uptime_seconds": 7200.0,
                "heartbeat_age_seconds": 120.0,
                "heartbeat_stale": True,
            }
            cls.return_value = inst

            result = runner.invoke(main, ["agent", "status"])
            assert result.exit_code == 2
            assert "STALE" in result.output

    def test_status_uptime_formatting_hours(self, runner):
        with patch("telos_adapters.openclaw.watchdog.Watchdog") as cls:
            inst = MagicMock()
            inst.is_running.return_value = True
            inst.health_check.return_value = {
                "status": "ok",
                "pid": 12345,
                "running": True,
                "uptime_seconds": 7200.0,
                "heartbeat_age_seconds": 5.0,
                "heartbeat_stale": False,
            }
            cls.return_value = inst

            with patch("telos_governance.cli._daemon_ipc", return_value=None):
                result = runner.invoke(main, ["agent", "status"])
                assert "2.0h" in result.output


# =============================================================================
# Tests: telos agent monitor
# =============================================================================


class TestAgentMonitor:
    """Tests for `telos agent monitor`."""

    def test_monitor_daemon_not_running(self, runner, mock_watchdog_stopped):
        result = runner.invoke(main, ["agent", "monitor"])
        assert result.exit_code == 1
        assert "not running" in (result.output + result.stderr)

    @patch("telos_governance.cli._daemon_ipc")
    @patch("time.sleep", side_effect=KeyboardInterrupt)
    def test_monitor_single_iteration(
        self, mock_sleep, mock_ipc, runner, mock_watchdog_running
    ):
        mock_ipc.return_value = {
            "data": {
                "governance_stats": {
                    "total_scored": 10,
                    "total_blocked": 1,
                    "total_escalated": 0,
                    "chain_length": 2,
                }
            }
        }
        result = runner.invoke(main, ["agent", "monitor", "-n", "1"])
        assert result.exit_code == 0
        assert "scored=10" in result.output
        assert "Monitor stopped" in result.output

    @patch("telos_governance.cli._daemon_ipc")
    @patch("time.sleep")
    def test_monitor_count_limit(
        self, mock_sleep, mock_ipc, runner, mock_watchdog_running
    ):
        mock_ipc.return_value = {
            "data": {
                "governance_stats": {
                    "total_scored": 5,
                    "total_blocked": 0,
                    "total_escalated": 0,
                    "chain_length": 1,
                }
            }
        }
        result = runner.invoke(
            main, ["agent", "monitor", "--count", "2", "-n", "1"]
        )
        assert result.exit_code == 0
        # Should have 2 lines of output (2 iterations)
        lines_with_scored = [
            l for l in result.output.split("\n") if "scored=" in l
        ]
        assert len(lines_with_scored) == 2

    @patch("telos_governance.cli._daemon_ipc")
    @patch("time.sleep", side_effect=KeyboardInterrupt)
    def test_monitor_ipc_failure(
        self, mock_sleep, mock_ipc, runner, mock_watchdog_running
    ):
        mock_ipc.return_value = None
        result = runner.invoke(main, ["agent", "monitor", "-n", "1"])
        assert result.exit_code == 0
        assert "No response" in result.output


# =============================================================================
# Tests: telos agent history
# =============================================================================


class TestAgentHistory:
    """Tests for `telos agent history`."""

    def test_history_no_logs(self, runner, tmp_path):
        """No audit logs found."""
        with patch(
            "pathlib.Path.home", return_value=tmp_path
        ):
            result = runner.invoke(main, ["agent", "history"])
            assert result.exit_code == 0
            assert "No governance history" in result.output

    def test_history_no_logs_json(self, runner, tmp_path):
        with patch(
            "pathlib.Path.home", return_value=tmp_path
        ):
            result = runner.invoke(main, ["agent", "history", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["entries"] == []
            assert data["total"] == 0

    def test_history_reads_audit_log(self, runner, tmp_path):
        """Reads entries from audit JSONL file."""
        hooks_dir = tmp_path / ".openclaw" / "hooks"
        hooks_dir.mkdir(parents=True)
        log_file = hooks_dir / "telos-audit-2026-02-17.jsonl"
        entries = [
            {
                "decision": "EXECUTE",
                "tool_name": "Read",
                "tool_group": "fs",
                "fidelity": 0.92,
                "allowed": True,
            },
            {
                "decision": "ESCALATE",
                "tool_name": "Bash",
                "tool_group": "runtime",
                "fidelity": 0.31,
                "allowed": False,
            },
        ]
        log_file.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n"
        )

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(main, ["agent", "history"])
            assert result.exit_code == 0
            assert "EXECUTE" in result.output
            assert "ESCALATE" in result.output

    def test_history_json_output(self, runner, tmp_path):
        hooks_dir = tmp_path / ".openclaw" / "hooks"
        hooks_dir.mkdir(parents=True)
        log_file = hooks_dir / "telos-audit-2026-02-17.jsonl"
        log_file.write_text(
            json.dumps({
                "decision": "EXECUTE",
                "tool_name": "Read",
                "tool_group": "fs",
                "fidelity": 0.92,
                "allowed": True,
            }) + "\n"
        )

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(main, ["agent", "history", "--json"])
            data = json.loads(result.output)
            assert data["total"] == 1
            assert data["entries"][0]["decision"] == "EXECUTE"

    def test_history_filter_decision(self, runner, tmp_path):
        hooks_dir = tmp_path / ".openclaw" / "hooks"
        hooks_dir.mkdir(parents=True)
        log_file = hooks_dir / "telos-audit-2026-02-17.jsonl"
        entries = [
            {"decision": "EXECUTE", "tool_name": "Read", "tool_group": "fs",
             "fidelity": 0.92, "allowed": True},
            {"decision": "ESCALATE", "tool_name": "Bash", "tool_group": "runtime",
             "fidelity": 0.31, "allowed": False},
        ]
        log_file.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n"
        )

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(
                main, ["agent", "history", "--filter-decision", "ESCALATE"]
            )
            assert "ESCALATE" in result.output
            assert "EXECUTE" not in result.output

    def test_history_filter_group(self, runner, tmp_path):
        hooks_dir = tmp_path / ".openclaw" / "hooks"
        hooks_dir.mkdir(parents=True)
        log_file = hooks_dir / "telos-audit-2026-02-17.jsonl"
        entries = [
            {"decision": "EXECUTE", "tool_name": "Read", "tool_group": "fs",
             "fidelity": 0.92, "allowed": True},
            {"decision": "ESCALATE", "tool_name": "Bash", "tool_group": "runtime",
             "fidelity": 0.31, "allowed": False},
        ]
        log_file.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n"
        )

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(
                main,
                ["agent", "history", "--filter-group", "runtime", "--json"],
            )
            data = json.loads(result.output)
            assert data["total"] == 1
            assert data["entries"][0]["tool_group"] == "runtime"

    def test_history_limit(self, runner, tmp_path):
        hooks_dir = tmp_path / ".openclaw" / "hooks"
        hooks_dir.mkdir(parents=True)
        log_file = hooks_dir / "telos-audit-2026-02-17.jsonl"
        entries = [
            {"decision": "EXECUTE", "tool_name": f"Read{i}",
             "tool_group": "fs", "fidelity": 0.9, "allowed": True}
            for i in range(10)
        ]
        log_file.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n"
        )

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(
                main, ["agent", "history", "-n", "3", "--json"]
            )
            data = json.loads(result.output)
            assert data["total"] == 3


# =============================================================================
# Tests: telos agent test
# =============================================================================


class TestAgentTest:
    """Tests for `telos agent test`."""

    def test_test_daemon_not_running(self, runner, mock_watchdog_stopped):
        result = runner.invoke(main, ["agent", "test"])
        assert result.exit_code == 1
        assert "not running" in (result.output + result.stderr)

    @patch("telos_governance.cli._daemon_ipc")
    def test_test_all_pass(self, mock_ipc, runner, mock_watchdog_running):
        """All scenarios pass when daemon returns expected verdicts."""

        def mock_score(**kwargs):
            tool = kwargs.get("tool_name", "")
            if tool == "Read" and ".env" not in kwargs.get("action_text", ""):
                return {"data": {"allowed": True, "decision": "execute",
                                 "fidelity": 0.92}}
            else:
                return {"data": {"allowed": False, "decision": "escalate",
                                 "fidelity": 0.31}}

        def side_effect(msg_type, **kwargs):
            if msg_type == "health":
                return {"data": {"governance_stats": {}}}
            return mock_score(**kwargs)

        mock_ipc.side_effect = side_effect

        result = runner.invoke(main, ["agent", "test"])
        assert result.exit_code == 0
        assert "4/4 scenarios passed" in result.output

    @patch("telos_governance.cli._daemon_ipc")
    def test_test_single_scenario(
        self, mock_ipc, runner, mock_watchdog_running
    ):
        mock_ipc.return_value = {
            "data": {"allowed": True, "decision": "execute", "fidelity": 0.92}
        }
        result = runner.invoke(main, ["agent", "test", "-s", "safe"])
        assert result.exit_code == 0
        assert "1/1 scenarios passed" in result.output

    @patch("telos_governance.cli._daemon_ipc")
    def test_test_failure(self, mock_ipc, runner, mock_watchdog_running):
        """Safe scenario returns blocked = failure."""
        mock_ipc.return_value = {
            "data": {"allowed": False, "decision": "escalate",
                     "fidelity": 0.31}
        }
        result = runner.invoke(main, ["agent", "test", "-s", "safe"])
        assert result.exit_code == 1  # Failure
        combined = result.output + result.stderr
        assert "0/1 scenarios passed" in combined

    @patch("telos_governance.cli._daemon_ipc")
    def test_test_json_output(self, mock_ipc, runner, mock_watchdog_running):
        mock_ipc.return_value = {
            "data": {"allowed": True, "decision": "execute", "fidelity": 0.92}
        }
        result = runner.invoke(
            main, ["agent", "test", "-s", "safe", "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["passed"] == 1
        assert data["total"] == 1
        assert data["results"][0]["status"] == "pass"

    @patch("telos_governance.cli._daemon_ipc")
    def test_test_ipc_error(self, mock_ipc, runner, mock_watchdog_running):
        """IPC returns None (connection failure)."""
        mock_ipc.return_value = None
        result = runner.invoke(main, ["agent", "test", "-s", "safe"])
        assert result.exit_code == 1
        combined = result.output + result.stderr
        assert "0/1" in combined


# =============================================================================
# Tests: telos service install
# =============================================================================


class TestServiceInstall:
    """Tests for `telos service install`."""

    @pytest.mark.skipif(
        sys.platform != "darwin", reason="macOS-specific test"
    )
    def test_install_macos_creates_plist(self, runner, tmp_path):
        plist_dir = tmp_path / "Library" / "LaunchAgents"
        plist_path = plist_dir / "ai.telos-labs.governance.plist"

        hooks_dir = tmp_path / ".openclaw" / "hooks"

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(main, ["service", "install"])

        assert result.exit_code == 0
        assert plist_path.exists()
        content = plist_path.read_text()
        assert "ai.telos-labs.governance" in content
        assert "telos_adapters.openclaw.daemon" in content
        assert "balanced" in content

    @pytest.mark.skipif(
        sys.platform != "darwin", reason="macOS-specific test"
    )
    def test_install_macos_strict_preset(self, runner, tmp_path):
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(
                main, ["service", "install", "-p", "strict"]
            )

        assert result.exit_code == 0
        plist = (
            tmp_path / "Library" / "LaunchAgents"
            / "ai.telos-labs.governance.plist"
        )
        assert "strict" in plist.read_text()

    @pytest.mark.skipif(
        sys.platform != "darwin", reason="macOS-specific test"
    )
    def test_install_macos_already_exists(self, runner, tmp_path):
        plist_dir = tmp_path / "Library" / "LaunchAgents"
        plist_dir.mkdir(parents=True)
        plist = plist_dir / "ai.telos-labs.governance.plist"
        plist.write_text("existing")

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(main, ["service", "install"])

        assert result.exit_code == 1
        combined = result.output + result.stderr
        assert "already installed" in combined

    @pytest.mark.skipif(
        sys.platform != "linux", reason="Linux-specific test"
    )
    def test_install_linux_creates_unit(self, runner, tmp_path):
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(main, ["service", "install"])

        assert result.exit_code == 0
        unit = (
            tmp_path / ".config" / "systemd" / "user"
            / "telos-governance.service"
        )
        assert unit.exists()
        content = unit.read_text()
        assert "telos_adapters.openclaw.daemon" in content


# =============================================================================
# Tests: telos service uninstall
# =============================================================================


class TestServiceUninstall:
    """Tests for `telos service uninstall`."""

    @pytest.mark.skipif(
        sys.platform != "darwin", reason="macOS-specific test"
    )
    def test_uninstall_macos_removes_plist(self, runner, tmp_path):
        plist_dir = tmp_path / "Library" / "LaunchAgents"
        plist_dir.mkdir(parents=True)
        plist = plist_dir / "ai.telos-labs.governance.plist"
        plist.write_text("existing")

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(
                main, ["service", "uninstall", "-y"]
            )

        assert result.exit_code == 0
        assert not plist.exists()
        assert "Service removed" in result.output

    @pytest.mark.skipif(
        sys.platform != "darwin", reason="macOS-specific test"
    )
    def test_uninstall_macos_not_installed(self, runner, tmp_path):
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(
                main, ["service", "uninstall", "-y"]
            )

        assert result.exit_code == 0
        assert "No service installed" in result.output

    @pytest.mark.skipif(
        sys.platform != "linux", reason="Linux-specific test"
    )
    def test_uninstall_linux_removes_unit(self, runner, tmp_path):
        unit_dir = tmp_path / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True)
        unit = unit_dir / "telos-governance.service"
        unit.write_text("existing")

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(
                main, ["service", "uninstall", "-y"]
            )

        assert result.exit_code == 0
        assert not unit.exists()


# =============================================================================
# Tests: Helper functions
# =============================================================================


class TestOpenClawDetect:
    """Tests for _openclaw_detect() helper."""

    def test_detect_no_openclaw(self, tmp_path):
        from telos_governance.cli import _openclaw_detect

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("shutil.which", return_value=None):
                info = _openclaw_detect()
                assert info["installed"] is False

    def test_detect_with_config_dir(self, tmp_path):
        from telos_governance.cli import _openclaw_detect

        openclaw_dir = tmp_path / ".openclaw"
        openclaw_dir.mkdir()

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("shutil.which", return_value=None):
                info = _openclaw_detect()
                assert info["installed"] is True
                assert info["config_dir"] is not None

    def test_detect_with_binary(self, tmp_path):
        from telos_governance.cli import _openclaw_detect

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("shutil.which", return_value="/usr/bin/openclaw"):
                info = _openclaw_detect()
                assert info["installed"] is True
                assert info["binary"] == "/usr/bin/openclaw"


class TestDaemonIpc:
    """Tests for _daemon_ipc() helper."""

    def test_ipc_socket_not_found(self, tmp_path):
        from telos_governance.cli import _daemon_ipc

        result = _daemon_ipc(
            "health", socket_path=str(tmp_path / "nonexistent.sock")
        )
        assert result is None

    def test_ipc_connection_refused(self, tmp_path):
        from telos_governance.cli import _daemon_ipc

        # Create a file (not a socket) to trigger connection error
        sock = tmp_path / "fake.sock"
        sock.write_text("not a socket")

        result = _daemon_ipc("health", socket_path=str(sock))
        assert result is None


# =============================================================================
# Tests: NO_COLOR compliance
# =============================================================================


class TestNoColorCompliance:
    """Verify NO_COLOR compliance across all agent commands."""

    def test_block_policy_no_color(self, runner):
        result = runner.invoke(
            main, ["--no-color", "agent", "block-policy"]
        )
        assert result.exit_code == 0
        # Check no ANSI escape codes
        assert "\x1b[" not in result.output

    def test_status_no_color(self, runner, mock_watchdog_stopped):
        result = runner.invoke(
            main, ["--no-color", "agent", "status"]
        )
        # Exit code 1 since daemon is stopped, but output should be clean
        assert "\x1b[" not in result.output

    def test_init_no_color(self, runner, tmp_path):
        dest = tmp_path / "out.yaml"
        result = runner.invoke(
            main,
            ["--no-color", "agent", "init", "--no-detect", "-o", str(dest)],
        )
        assert result.exit_code == 0
        assert "\x1b[" not in result.output


# =============================================================================
# Tests: Exit code compliance
# =============================================================================


class TestExitCodes:
    """Verify exit code compliance (0=ok, 1=stopped, 2=stale)."""

    def test_status_exit_0_running(self, runner, mock_watchdog_running):
        with patch("telos_governance.cli._daemon_ipc", return_value=None):
            result = runner.invoke(main, ["agent", "status"])
            assert result.exit_code == 0

    def test_status_exit_1_stopped(self, runner, mock_watchdog_stopped):
        result = runner.invoke(main, ["agent", "status"])
        assert result.exit_code == 1

    def test_status_exit_2_stale(self, runner):
        with patch("telos_adapters.openclaw.watchdog.Watchdog") as cls:
            inst = MagicMock()
            inst.is_running.return_value = True
            inst.health_check.return_value = {
                "status": "stale",
                "pid": 99999,
                "running": True,
                "uptime_seconds": 100.0,
                "heartbeat_age_seconds": 120.0,
                "heartbeat_stale": True,
            }
            cls.return_value = inst

            with patch(
                "telos_governance.cli._daemon_ipc", return_value=None
            ):
                result = runner.invoke(main, ["agent", "status"])
                assert result.exit_code == 2

    def test_test_exit_0_all_pass(self, runner, mock_watchdog_running):
        with patch("telos_governance.cli._daemon_ipc") as mock_ipc:
            def side_effect(msg_type, **kwargs):
                tool = kwargs.get("tool_name", "")
                if tool == "Read" and ".env" not in kwargs.get("action_text", ""):
                    return {"data": {"allowed": True, "decision": "execute",
                                     "fidelity": 0.92}}
                return {"data": {"allowed": False, "decision": "escalate",
                                 "fidelity": 0.31}}

            mock_ipc.side_effect = side_effect
            result = runner.invoke(main, ["agent", "test"])
            assert result.exit_code == 0

    def test_test_exit_1_failure(self, runner, mock_watchdog_running):
        with patch("telos_governance.cli._daemon_ipc") as mock_ipc:
            mock_ipc.return_value = {
                "data": {"allowed": True, "decision": "execute",
                         "fidelity": 0.92}
            }
            result = runner.invoke(main, ["agent", "test"])
            # All scenarios return allowed=True, but credential/exfiltration/rce
            # expect allowed=False, so this should fail
            assert result.exit_code == 1

    def test_monitor_exit_1_not_running(self, runner, mock_watchdog_stopped):
        result = runner.invoke(main, ["agent", "monitor"])
        assert result.exit_code == 1

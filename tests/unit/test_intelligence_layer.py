"""
Tests for telos_governance.intelligence_layer — opt-in governance telemetry.

Tests cover:
- IntelligenceConfig validation and defaults
- TelemetryRecord serialization (metrics vs full level)
- SessionTelemetry aggregation
- IntelligenceCollector lifecycle (start → record → end)
- Collection level filtering (off, metrics, full)
- Local storage (JSONL session files, aggregate.json)
- Query operations (get_aggregate, list_sessions, get_status)
- Clear/cleanup operations
- Privacy: no raw text in telemetry records
"""

import json
import os
import tempfile
import time
import pytest
from pathlib import Path

from telos_governance.intelligence_layer import (
    IntelligenceCollector,
    IntelligenceConfig,
    IntelligenceError,
    TelemetryRecord,
    SessionTelemetry,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def tmp_base():
    """Temporary base directory for intelligence storage."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def metrics_config(tmp_base):
    """Config with metrics-level collection enabled."""
    return IntelligenceConfig(
        enabled=True,
        collection_level="metrics",
        base_dir=tmp_base,
        agent_id="test-agent",
    )


@pytest.fixture
def full_config(tmp_base):
    """Config with full-level collection enabled."""
    return IntelligenceConfig(
        enabled=True,
        collection_level="full",
        base_dir=tmp_base,
        agent_id="test-agent",
    )


@pytest.fixture
def off_config(tmp_base):
    """Config with collection disabled."""
    return IntelligenceConfig(
        enabled=False,
        base_dir=tmp_base,
        agent_id="test-agent",
    )


# =============================================================================
# IntelligenceConfig
# =============================================================================

class TestIntelligenceConfig:
    """Test configuration validation and defaults."""

    def test_default_config_is_off(self):
        config = IntelligenceConfig()
        assert config.enabled is False
        assert config.collection_level == "off"

    def test_enabled_metrics(self, tmp_base):
        config = IntelligenceConfig(
            enabled=True, collection_level="metrics", base_dir=tmp_base
        )
        assert config.enabled is True
        assert config.collection_level == "metrics"

    def test_enabled_full(self, tmp_base):
        config = IntelligenceConfig(
            enabled=True, collection_level="full", base_dir=tmp_base
        )
        assert config.collection_level == "full"

    def test_disabled_forces_off(self, tmp_base):
        """When enabled=False, collection_level is forced to 'off'."""
        config = IntelligenceConfig(
            enabled=False, collection_level="metrics", base_dir=tmp_base
        )
        assert config.collection_level == "off"

    def test_invalid_level_raises(self, tmp_base):
        with pytest.raises(IntelligenceError, match="Invalid collection_level"):
            IntelligenceConfig(
                enabled=True, collection_level="verbose", base_dir=tmp_base
            )

    def test_default_retention_90_days(self):
        config = IntelligenceConfig()
        assert config.retention_days == 90


# =============================================================================
# TelemetryRecord
# =============================================================================

class TestTelemetryRecord:
    """Test telemetry record serialization."""

    def test_metrics_dict_has_core_fields(self):
        record = TelemetryRecord(
            session_id="s1",
            agent_id="a1",
            record_index=0,
            timestamp=1000.0,
            scoring_duration_ms=12.5,
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
        )
        d = record.to_metrics_dict()
        assert d["session_id"] == "s1"
        assert d["decision"] == "execute"
        assert d["effective_fidelity"] == 0.87
        # Metrics dict should NOT contain dimension breakdown
        assert "purpose_fidelity" not in d

    def test_full_dict_has_all_fields(self):
        record = TelemetryRecord(
            session_id="s1",
            agent_id="a1",
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
            purpose_fidelity=0.90,
            scope_fidelity=0.82,
            boundary_violation=0.15,
            boundary_triggered=False,
            contrastive_suppressed=True,
            similarity_gap=-0.12,
        )
        d = record.to_full_dict()
        assert d["purpose_fidelity"] == 0.90
        assert d["scope_fidelity"] == 0.82
        assert d["boundary_triggered"] is False
        assert d["contrastive_suppressed"] is True
        assert d["similarity_gap"] == -0.12

    def test_no_raw_text_in_record(self):
        """TelemetryRecord should never contain raw request text."""
        record = TelemetryRecord(
            session_id="s1",
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
        )
        metrics = record.to_metrics_dict()
        full = record.to_full_dict()
        # No field should contain request text
        for d in (metrics, full):
            assert "action_text" not in d
            assert "request" not in d
            assert "tool_args" not in d
            assert "tool_result" not in d


# =============================================================================
# SessionTelemetry
# =============================================================================

class TestSessionTelemetry:
    """Test session-level telemetry aggregation."""

    def test_empty_session_aggregate(self):
        session = SessionTelemetry(session_id="s1", agent_id="a1")
        agg = session.aggregate()
        assert agg["record_count"] == 0

    def test_aggregate_statistics(self):
        session = SessionTelemetry(session_id="s1", agent_id="a1")
        for fidelity, decision in [(0.90, "execute"), (0.70, "clarify"), (0.40, "inert")]:
            record = TelemetryRecord(
                session_id="s1",
                agent_id="a1",
                effective_fidelity=fidelity,
                composite_fidelity=fidelity,
                decision=decision,
                decision_point="pre_action",
            )
            session.add_record(record)

        agg = session.aggregate()
        assert agg["record_count"] == 3
        assert abs(agg["fidelity_mean"] - (0.90 + 0.70 + 0.40) / 3) < 1e-9
        assert agg["fidelity_min"] == 0.40
        assert agg["fidelity_max"] == 0.90
        assert agg["decision_counts"]["execute"] == 1
        assert agg["decision_counts"]["clarify"] == 1
        assert agg["decision_counts"]["inert"] == 1

    def test_record_index_auto_increments(self):
        session = SessionTelemetry(session_id="s1")
        for i in range(5):
            record = TelemetryRecord(
                effective_fidelity=0.8,
                composite_fidelity=0.8,
            )
            session.add_record(record)
            assert record.record_index == i

    def test_boundary_trigger_count(self):
        session = SessionTelemetry(session_id="s1")
        for triggered in [True, False, True, True, False]:
            record = TelemetryRecord(
                effective_fidelity=0.8,
                composite_fidelity=0.8,
                boundary_triggered=triggered,
            )
            session.add_record(record)
        agg = session.aggregate()
        assert agg["boundary_triggers"] == 3


# =============================================================================
# IntelligenceCollector — off mode
# =============================================================================

class TestCollectorOff:
    """Test that disabled collector is a no-op."""

    def test_not_collecting_when_off(self, off_config):
        collector = IntelligenceCollector(off_config)
        assert collector.is_collecting is False

    def test_start_session_noop(self, off_config):
        collector = IntelligenceCollector(off_config)
        collector.start_session("s1")
        assert collector.current_session is None

    def test_record_decision_returns_none(self, off_config):
        collector = IntelligenceCollector(off_config)
        collector.start_session("s1")
        result = collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
        )
        assert result is None

    def test_end_session_returns_none(self, off_config):
        collector = IntelligenceCollector(off_config)
        collector.start_session("s1")
        assert collector.end_session() is None


# =============================================================================
# IntelligenceCollector — metrics mode
# =============================================================================

class TestCollectorMetrics:
    """Test metrics-level collection."""

    def test_is_collecting(self, metrics_config):
        collector = IntelligenceCollector(metrics_config)
        assert collector.is_collecting is True
        assert collector.collection_level == "metrics"

    def test_session_lifecycle(self, metrics_config):
        collector = IntelligenceCollector(metrics_config)
        collector.start_session("s1", "test-agent")

        record = collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
            scoring_duration_ms=10.0,
        )
        assert record is not None
        assert record.decision == "execute"

        agg = collector.end_session()
        assert agg is not None
        assert agg["record_count"] == 1
        assert agg["fidelity_mean"] == 0.87

    def test_metrics_level_excludes_dimensions(self, metrics_config, tmp_base):
        """Metrics-level should NOT include dimension breakdown in stored files."""
        collector = IntelligenceCollector(metrics_config)
        collector.start_session("s1", "test-agent")
        collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
            purpose_fidelity=0.90,  # Should be excluded at metrics level
            scope_fidelity=0.82,
        )
        collector.end_session()

        # Read the written JSONL file
        sessions_dir = Path(tmp_base) / "test-agent" / "sessions"
        files = list(sessions_dir.glob("*.jsonl"))
        assert len(files) == 1

        lines = files[0].read_text().strip().split("\n")
        assert len(lines) == 2  # header + 1 record
        record_data = json.loads(lines[1])
        assert "purpose_fidelity" not in record_data
        assert "scope_fidelity" not in record_data

    def test_multiple_records_per_session(self, metrics_config):
        collector = IntelligenceCollector(metrics_config)
        collector.start_session("s1", "test-agent")

        for i in range(5):
            collector.record_decision(
                decision_point="pre_action",
                decision="execute",
                effective_fidelity=0.80 + i * 0.02,
                composite_fidelity=0.80,
            )

        agg = collector.end_session()
        assert agg["record_count"] == 5

    def test_empty_session_no_write(self, metrics_config, tmp_base):
        """Session with no records should not write a file."""
        collector = IntelligenceCollector(metrics_config)
        collector.start_session("s1", "test-agent")
        agg = collector.end_session()
        assert agg is None

        sessions_dir = Path(tmp_base) / "test-agent" / "sessions"
        if sessions_dir.exists():
            assert len(list(sessions_dir.glob("*.jsonl"))) == 0


# =============================================================================
# IntelligenceCollector — full mode
# =============================================================================

class TestCollectorFull:
    """Test full-level collection."""

    def test_full_level_includes_dimensions(self, full_config, tmp_base):
        collector = IntelligenceCollector(full_config)
        collector.start_session("s1", "test-agent")
        collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
            purpose_fidelity=0.90,
            scope_fidelity=0.82,
            boundary_violation=0.15,
            boundary_triggered=False,
            contrastive_suppressed=True,
            similarity_gap=-0.12,
        )
        collector.end_session()

        # Read the stored record
        sessions_dir = Path(tmp_base) / "test-agent" / "sessions"
        files = list(sessions_dir.glob("*.jsonl"))
        lines = files[0].read_text().strip().split("\n")
        record_data = json.loads(lines[1])
        assert record_data["purpose_fidelity"] == 0.90
        assert record_data["boundary_triggered"] is False
        assert record_data["contrastive_suppressed"] is True
        assert record_data["similarity_gap"] == -0.12


# =============================================================================
# Storage and aggregation
# =============================================================================

class TestStorage:
    """Test persistent storage and aggregate updates."""

    def test_session_file_created(self, metrics_config, tmp_base):
        collector = IntelligenceCollector(metrics_config)
        collector.start_session("s1", "test-agent")
        collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
        )
        collector.end_session()

        sessions_dir = Path(tmp_base) / "test-agent" / "sessions"
        files = list(sessions_dir.glob("*.jsonl"))
        assert len(files) == 1
        assert "s1" in files[0].name

    def test_session_file_has_header(self, metrics_config, tmp_base):
        collector = IntelligenceCollector(metrics_config)
        collector.start_session("s1", "test-agent")
        collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
        )
        collector.end_session()

        sessions_dir = Path(tmp_base) / "test-agent" / "sessions"
        files = list(sessions_dir.glob("*.jsonl"))
        header = json.loads(files[0].read_text().strip().split("\n")[0])
        assert header["type"] == "session_header"
        assert header["session_id"] == "s1"
        assert header["collection_level"] == "metrics"

    def test_aggregate_file_created(self, metrics_config, tmp_base):
        collector = IntelligenceCollector(metrics_config)
        collector.start_session("s1", "test-agent")
        collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
        )
        collector.end_session()

        agg_path = Path(tmp_base) / "test-agent" / "aggregate.json"
        assert agg_path.exists()
        agg = json.loads(agg_path.read_text())
        assert agg["total_sessions"] == 1
        assert agg["total_records"] == 1

    def test_aggregate_accumulates_across_sessions(self, metrics_config, tmp_base):
        collector = IntelligenceCollector(metrics_config)

        # Session 1
        collector.start_session("s1", "test-agent")
        collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.90,
            composite_fidelity=0.90,
        )
        collector.end_session()

        # Session 2
        collector.start_session("s2", "test-agent")
        collector.record_decision(
            decision_point="pre_action",
            decision="clarify",
            effective_fidelity=0.70,
            composite_fidelity=0.70,
        )
        collector.record_decision(
            decision_point="tool_select",
            decision="execute",
            effective_fidelity=0.85,
            composite_fidelity=0.85,
        )
        collector.end_session()

        agg = json.loads(
            (Path(tmp_base) / "test-agent" / "aggregate.json").read_text()
        )
        assert agg["total_sessions"] == 2
        assert agg["total_records"] == 3
        assert agg["fidelity_min"] == 0.70
        assert agg["decision_distribution"]["execute"] == 2
        assert agg["decision_distribution"]["clarify"] == 1


# =============================================================================
# Query operations
# =============================================================================

class TestQuery:
    """Test query and status operations."""

    def test_get_aggregate_returns_none_when_empty(self, metrics_config):
        collector = IntelligenceCollector(metrics_config)
        assert collector.get_aggregate("nonexistent-agent") is None

    def test_get_aggregate_returns_data(self, metrics_config, tmp_base):
        collector = IntelligenceCollector(metrics_config)
        collector.start_session("s1", "test-agent")
        collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
        )
        collector.end_session()

        agg = collector.get_aggregate("test-agent")
        assert agg is not None
        assert agg["total_sessions"] == 1

    def test_list_sessions(self, metrics_config, tmp_base):
        collector = IntelligenceCollector(metrics_config)

        # Create 3 sessions
        for i in range(3):
            collector.start_session(f"s{i}", "test-agent")
            collector.record_decision(
                decision_point="pre_action",
                decision="execute",
                effective_fidelity=0.87,
                composite_fidelity=0.85,
            )
            collector.end_session()

        sessions = collector.list_sessions("test-agent")
        assert len(sessions) == 3
        assert all("filename" in s for s in sessions)
        assert all("size_bytes" in s for s in sessions)

    def test_list_sessions_empty_agent(self, metrics_config):
        collector = IntelligenceCollector(metrics_config)
        sessions = collector.list_sessions("nonexistent")
        assert sessions == []

    def test_get_status(self, metrics_config, tmp_base):
        collector = IntelligenceCollector(metrics_config)
        status = collector.get_status()
        assert status["enabled"] is True
        assert status["collection_level"] == "metrics"
        assert status["is_collecting"] is True
        assert status["base_dir"] == tmp_base

    def test_get_status_with_storage_info(self, metrics_config, tmp_base):
        collector = IntelligenceCollector(metrics_config)
        collector.start_session("s1", "test-agent")
        collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
        )
        collector.end_session()

        status = collector.get_status()
        assert status["storage"]["agent_count"] >= 1
        assert status["storage"]["total_size_bytes"] > 0


# =============================================================================
# Clear / cleanup
# =============================================================================

class TestClear:
    """Test telemetry clearing operations."""

    def test_clear_removes_files(self, metrics_config, tmp_base):
        collector = IntelligenceCollector(metrics_config)
        collector.start_session("s1", "test-agent")
        collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
        )
        collector.end_session()

        # Verify files exist
        sessions_dir = Path(tmp_base) / "test-agent" / "sessions"
        assert len(list(sessions_dir.glob("*.jsonl"))) == 1
        assert (Path(tmp_base) / "test-agent" / "aggregate.json").exists()

        # Clear
        deleted = collector.clear_telemetry("test-agent")
        assert deleted == 2  # 1 session file + 1 aggregate

        # Verify gone
        assert len(list(sessions_dir.glob("*.jsonl"))) == 0
        assert not (Path(tmp_base) / "test-agent" / "aggregate.json").exists()

    def test_clear_nonexistent_returns_zero(self, metrics_config):
        collector = IntelligenceCollector(metrics_config)
        assert collector.clear_telemetry("nonexistent") == 0


# =============================================================================
# Privacy
# =============================================================================

class TestPrivacy:
    """Test that no raw text leaks into telemetry."""

    def test_no_text_in_stored_files(self, full_config, tmp_base):
        """Even at full collection level, stored records contain no text."""
        collector = IntelligenceCollector(full_config)
        collector.start_session("s1", "test-agent")
        collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
            purpose_fidelity=0.90,
            scope_fidelity=0.82,
            boundary_violation=0.15,
            boundary_triggered=False,
        )
        collector.end_session()

        sessions_dir = Path(tmp_base) / "test-agent" / "sessions"
        content = list(sessions_dir.glob("*.jsonl"))[0].read_text()
        # The file should not contain any action text fields
        assert "action_text" not in content
        assert "tool_args" not in content
        assert "tool_result" not in content
        assert "request" not in content

    def test_aggregate_has_no_text(self, metrics_config, tmp_base):
        """Aggregate statistics contain no text content."""
        collector = IntelligenceCollector(metrics_config)
        collector.start_session("s1", "test-agent")
        collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
        )
        collector.end_session()

        content = (Path(tmp_base) / "test-agent" / "aggregate.json").read_text()
        assert "action_text" not in content
        assert "tool_args" not in content

"""
Intelligence Layer: Opt-in governance telemetry for embedding calibration.

Collects anonymized governance session metrics (fidelity scores, decisions,
timing) for TELOS Labs to use in quarterly embedding calibration updates.
Raw request text is NEVER collected -- only mathematical governance telemetry.

**Default: OFF.** Must be explicitly enabled per-agent via YAML config or CLI flag.

Architecture:
    - Local-first: all telemetry stored on customer's filesystem
    - Encrypted at rest: AES-256-GCM via crypto_layer
    - No network calls: TELOS Labs receives data only via explicit export
    - Anonymized: no request text, tool args, or tool results -- only scores

Storage:
    ~/.telos/intelligence/{agent_id}/
    ├── sessions/          # Per-session telemetry files (.telos-telemetry)
    └── aggregate.json     # Running aggregate statistics (cleartext, no PII)

Collection levels:
    - "off"     -- No telemetry collected (default)
    - "metrics" -- Fidelity scores, decisions, timing only
    - "full"    -- Metrics + dimension breakdown + contrastive data

Revenue model context:
    Customers who opt in receive quarterly embedding improvements at no extra
    cost. Customers who opt out pay for manual calibration when they request
    updates. The Intelligence Layer is the data collection side of the
    telemetric update pipeline.

NIST AI RMF: Implements Measure 2.5 (ongoing monitoring data collection) and
Manage 3.2 (performance metrics for continuous improvement). Anonymized
collection aligns with NIST Privacy Framework core function "Protect."
OWASP LLM09 (Overreliance): Telemetry enables detection of governance drift
patterns that could indicate model degradation or embedding staleness.
"""

import base64
import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Pattern for safe identifiers (agent_id, session_id)
_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$')


# =============================================================================
# Configuration
# =============================================================================

VALID_COLLECTION_LEVELS = {"off", "metrics", "full"}
DEFAULT_COLLECTION_LEVEL = "off"
DEFAULT_BASE_DIR = os.path.expanduser("~/.telos/intelligence")
MAX_SESSION_FILE_SIZE = 10 * 1024 * 1024  # 10MB per session file


class IntelligenceError(Exception):
    """Raised when intelligence layer operations fail."""
    pass


@dataclass
class IntelligenceConfig:
    """Configuration for the Intelligence Layer.

    Args:
        enabled: Master switch -- must be True for any collection.
        collection_level: What to collect ("off", "metrics", "full").
        base_dir: Root directory for telemetry storage.
        agent_id: Agent identifier for partitioned storage.
        retention_days: Days to retain session telemetry (0 = indefinite).
        encryption_key: Optional bytes key for at-rest encryption of JSONL files.
            When provided, each JSONL line is AES-256-GCM encrypted via ConfigEncryptor
            and base64-encoded before writing. Existing plaintext files remain readable.
    """
    enabled: bool = False
    collection_level: str = DEFAULT_COLLECTION_LEVEL
    base_dir: str = DEFAULT_BASE_DIR
    agent_id: str = ""
    retention_days: int = 90
    encryption_key: Optional[bytes] = None

    def __post_init__(self):
        if self.collection_level not in VALID_COLLECTION_LEVELS:
            raise IntelligenceError(
                f"Invalid collection_level '{self.collection_level}'. "
                f"Must be one of: {VALID_COLLECTION_LEVELS}"
            )
        if not self.enabled:
            self.collection_level = "off"


# =============================================================================
# Telemetry records
# =============================================================================

@dataclass
class TelemetryRecord:
    """A single governance decision telemetry record.

    Contains ONLY mathematical governance metrics -- no raw text,
    no tool arguments, no tool results.
    """
    # Identity (anonymized)
    session_id: str = ""
    agent_id: str = ""
    record_index: int = 0

    # Timing
    timestamp: float = 0.0
    scoring_duration_ms: float = 0.0

    # Decision
    decision_point: str = ""  # pre_action, tool_select, etc.
    decision: str = ""  # execute, clarify, suggest, inert, escalate

    # Fidelity scores (metrics level)
    effective_fidelity: float = 0.0
    composite_fidelity: float = 0.0

    # Dimension breakdown (full level)
    purpose_fidelity: Optional[float] = None
    scope_fidelity: Optional[float] = None
    boundary_violation: Optional[float] = None
    tool_fidelity: Optional[float] = None
    chain_continuity: Optional[float] = None

    # Boundary data (full level)
    boundary_triggered: Optional[bool] = None
    contrastive_suppressed: Optional[bool] = None
    similarity_gap: Optional[float] = None

    # Context flags (no text content)
    human_required: Optional[bool] = None
    chain_broken: Optional[bool] = None

    def to_metrics_dict(self) -> Dict[str, Any]:
        """Return metrics-level fields only."""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "record_index": self.record_index,
            "timestamp": self.timestamp,
            "scoring_duration_ms": self.scoring_duration_ms,
            "decision_point": self.decision_point,
            "decision": self.decision,
            "effective_fidelity": self.effective_fidelity,
            "composite_fidelity": self.composite_fidelity,
        }

    def to_full_dict(self) -> Dict[str, Any]:
        """Return all fields (full collection level)."""
        d = self.to_metrics_dict()
        d.update({
            "purpose_fidelity": self.purpose_fidelity,
            "scope_fidelity": self.scope_fidelity,
            "boundary_violation": self.boundary_violation,
            "tool_fidelity": self.tool_fidelity,
            "chain_continuity": self.chain_continuity,
            "boundary_triggered": self.boundary_triggered,
            "contrastive_suppressed": self.contrastive_suppressed,
            "similarity_gap": self.similarity_gap,
            "human_required": self.human_required,
            "chain_broken": self.chain_broken,
        })
        return d


# =============================================================================
# Session telemetry
# =============================================================================

@dataclass
class SessionTelemetry:
    """Telemetry for a single governance session.

    Accumulates TelemetryRecords and computes session-level aggregates.
    """
    session_id: str = ""
    agent_id: str = ""
    started_at: float = field(default_factory=time.time)
    records: List[TelemetryRecord] = field(default_factory=list)

    def add_record(self, record: TelemetryRecord) -> None:
        """Add a telemetry record to this session."""
        record.record_index = len(self.records)
        self.records.append(record)

    @property
    def record_count(self) -> int:
        return len(self.records)

    def aggregate(self) -> Dict[str, Any]:
        """Compute session-level aggregate statistics."""
        if not self.records:
            return {
                "session_id": self.session_id,
                "agent_id": self.agent_id,
                "record_count": 0,
            }

        fidelities = [r.effective_fidelity for r in self.records]
        decisions = {}
        for r in self.records:
            decisions[r.decision] = decisions.get(r.decision, 0) + 1

        boundary_triggers = sum(
            1 for r in self.records if r.boundary_triggered
        )

        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "started_at": self.started_at,
            "record_count": len(self.records),
            "fidelity_mean": sum(fidelities) / len(fidelities),
            "fidelity_min": min(fidelities),
            "fidelity_max": max(fidelities),
            "decision_counts": decisions,
            "boundary_triggers": boundary_triggers,
            "total_scoring_ms": sum(
                r.scoring_duration_ms for r in self.records
            ),
        }


# =============================================================================
# Intelligence Collector (main interface)
# =============================================================================

class IntelligenceCollector:
    """Collects and stores governance telemetry.

    This is the primary interface for the Intelligence Layer.
    It is designed to be composed into GovernanceSessionContext
    and called after every governance decision.

    Usage:
        config = IntelligenceConfig(enabled=True, collection_level="metrics")
        collector = IntelligenceCollector(config)

        # Start a session
        collector.start_session("session-123", "property-intel-v2")

        # Record decisions (called by session.sign_result)
        collector.record_decision(
            decision_point="pre_action",
            decision="execute",
            effective_fidelity=0.87,
            composite_fidelity=0.85,
            scoring_duration_ms=12.3,
        )

        # End session (writes to disk)
        collector.end_session()

    Args:
        config: Intelligence layer configuration.
    """

    def __init__(self, config: IntelligenceConfig):
        self._config = config
        self._current_session: Optional[SessionTelemetry] = None
        self._is_collecting = config.enabled and config.collection_level != "off"
        self._encryptor = None
        if config.encryption_key:
            try:
                from telos_governance.crypto_layer import ConfigEncryptor
                self._encryptor = ConfigEncryptor(config.encryption_key)
            except (ImportError, ValueError):
                pass  # crypto_layer unavailable or invalid key -- write plaintext

    @property
    def is_collecting(self) -> bool:
        """Whether telemetry collection is active."""
        return self._is_collecting

    @property
    def collection_level(self) -> str:
        return self._config.collection_level

    @property
    def current_session(self) -> Optional[SessionTelemetry]:
        return self._current_session

    def start_session(self, session_id: str, agent_id: str = "") -> None:
        """Start collecting telemetry for a new session.

        Args:
            session_id: Unique session identifier.
            agent_id: Agent identifier for partitioned storage.
        """
        if not self._is_collecting:
            return

        agent = agent_id or self._config.agent_id
        self._current_session = SessionTelemetry(
            session_id=session_id,
            agent_id=agent,
            started_at=time.time(),
        )

    def record_decision(
        self,
        decision_point: str,
        decision: str,
        effective_fidelity: float,
        composite_fidelity: float,
        scoring_duration_ms: float = 0.0,
        # Full-level fields
        purpose_fidelity: Optional[float] = None,
        scope_fidelity: Optional[float] = None,
        boundary_violation: Optional[float] = None,
        tool_fidelity: Optional[float] = None,
        chain_continuity: Optional[float] = None,
        boundary_triggered: Optional[bool] = None,
        contrastive_suppressed: Optional[bool] = None,
        similarity_gap: Optional[float] = None,
        human_required: Optional[bool] = None,
        chain_broken: Optional[bool] = None,
    ) -> Optional[TelemetryRecord]:
        """Record a governance decision.

        Args:
            decision_point: Which governance gate produced this.
            decision: The governance decision (execute, clarify, etc.).
            effective_fidelity: Final fidelity score.
            composite_fidelity: Multi-dimensional composite score.
            scoring_duration_ms: Time taken to compute the score.
            (remaining args): Full-level dimension data.

        Returns:
            The TelemetryRecord if collecting, None otherwise.
        """
        if not self._is_collecting or self._current_session is None:
            return None

        record = TelemetryRecord(
            session_id=self._current_session.session_id,
            agent_id=self._current_session.agent_id,
            timestamp=time.time(),
            scoring_duration_ms=scoring_duration_ms,
            decision_point=decision_point,
            decision=decision,
            effective_fidelity=effective_fidelity,
            composite_fidelity=composite_fidelity,
        )

        # Full-level fields
        if self._config.collection_level == "full":
            record.purpose_fidelity = purpose_fidelity
            record.scope_fidelity = scope_fidelity
            record.boundary_violation = boundary_violation
            record.tool_fidelity = tool_fidelity
            record.chain_continuity = chain_continuity
            record.boundary_triggered = boundary_triggered
            record.contrastive_suppressed = contrastive_suppressed
            record.similarity_gap = similarity_gap
            record.human_required = human_required
            record.chain_broken = chain_broken

        self._current_session.add_record(record)
        return record

    def end_session(self) -> Optional[Dict[str, Any]]:
        """End the current session and persist telemetry.

        Writes session telemetry to disk and updates aggregate stats.

        Returns:
            Session aggregate dict if session was active, None otherwise.
        """
        if not self._is_collecting or self._current_session is None:
            return None

        session = self._current_session
        self._current_session = None

        if session.record_count == 0:
            return None

        # Persist session telemetry
        self._write_session(session)

        # Update aggregate
        aggregate = session.aggregate()
        self._update_aggregate(aggregate)

        return aggregate

    # -------------------------------------------------------------------------
    # Storage
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_id(value: str, label: str = "id") -> str:
        """Validate an identifier to prevent path traversal.

        Only allows alphanumeric chars, hyphens, underscores, and dots.
        """
        if not value:
            return "default"
        if not _SAFE_ID_RE.match(value):
            raise ValueError(
                f"Invalid {label} '{value[:40]}': must be alphanumeric + _ - . "
                f"(max 128 chars, no path separators)"
            )
        return value

    def _get_storage_dir(self, agent_id: str) -> Path:
        """Get the storage directory for an agent, creating if needed."""
        safe_id = self._validate_id(agent_id, "agent_id")
        base = Path(self._config.base_dir) / safe_id
        # Verify resolved path stays within base_dir (symlink defense)
        base_resolved = base.resolve()
        config_resolved = Path(self._config.base_dir).resolve()
        if not str(base_resolved).startswith(str(config_resolved)):
            raise ValueError("Agent storage path escaped base directory")
        sessions_dir = base / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        return base

    def _encrypt_line(self, line_bytes: bytes) -> str:
        """Encrypt a JSONL line and return base64-encoded ciphertext."""
        encrypted = self._encryptor.encrypt(line_bytes)
        return base64.b64encode(encrypted).decode("ascii")

    def _decrypt_line(self, b64_line: str) -> bytes:
        """Decrypt a base64-encoded encrypted JSONL line."""
        encrypted = base64.b64decode(b64_line)
        return self._encryptor.decrypt(encrypted)

    def _write_session(self, session: SessionTelemetry) -> Path:
        """Write session telemetry to a JSONL file.

        When encryption_key is configured, each line after the header is
        AES-256-GCM encrypted and base64-encoded. The header includes an
        'encrypted' flag so readers know to decrypt.
        """
        safe_session_id = self._validate_id(session.session_id, "session_id")
        storage = self._get_storage_dir(session.agent_id)
        sessions_dir = storage / "sessions"

        ts = datetime.fromtimestamp(session.started_at, tz=timezone.utc)
        filename = f"{ts.strftime('%Y%m%d_%H%M%S')}_{safe_session_id}.jsonl"
        filepath = sessions_dir / filename

        is_encrypted = self._encryptor is not None

        with open(filepath, "w") as f:
            # Header line (always cleartext for discoverability)
            header = {
                "type": "session_header",
                "session_id": safe_session_id,
                "agent_id": self._validate_id(session.agent_id, "agent_id"),
                "started_at": session.started_at,
                "record_count": session.record_count,
                "collection_level": self._config.collection_level,
                "encrypted": is_encrypted,
            }
            f.write(json.dumps(header) + "\n")

            # Record lines
            for record in session.records:
                if self._config.collection_level == "full":
                    line_json = json.dumps(record.to_full_dict())
                else:
                    line_json = json.dumps(record.to_metrics_dict())

                if is_encrypted:
                    f.write(self._encrypt_line(line_json.encode("utf-8")) + "\n")
                else:
                    f.write(line_json + "\n")

        return filepath

    def read_session(self, filepath: str) -> List[Dict[str, Any]]:
        """Read and optionally decrypt a session telemetry file.

        Args:
            filepath: Path to a .jsonl session file.

        Returns:
            List of record dicts (header excluded).
        """
        records = []
        path = Path(filepath)
        if not path.exists():
            return records

        is_encrypted = False
        with open(path, "r") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                if i == 0:
                    header = json.loads(line)
                    is_encrypted = header.get("encrypted", False)
                    continue

                if is_encrypted and self._encryptor:
                    decrypted = self._decrypt_line(line)
                    records.append(json.loads(decrypted.decode("utf-8")))
                else:
                    records.append(json.loads(line))

        return records

    def _update_aggregate(self, session_agg: Dict[str, Any]) -> None:
        """Update the running aggregate statistics file."""
        storage = self._get_storage_dir(session_agg.get("agent_id", ""))
        agg_path = storage / "aggregate.json"

        # Load existing or create new
        if agg_path.exists():
            try:
                existing = json.loads(agg_path.read_text())
            except (json.JSONDecodeError, OSError):
                existing = self._empty_aggregate(session_agg.get("agent_id", ""))
        else:
            existing = self._empty_aggregate(session_agg.get("agent_id", ""))

        # Update counters
        existing["total_sessions"] += 1
        existing["total_records"] += session_agg.get("record_count", 0)
        existing["last_session_at"] = time.time()

        # Running fidelity stats
        n = session_agg.get("record_count", 0)
        if n > 0:
            old_n = existing.get("_fidelity_n", 0)
            old_sum = existing.get("_fidelity_sum", 0.0)
            new_sum = old_sum + session_agg.get("fidelity_mean", 0.0) * n
            new_n = old_n + n
            existing["_fidelity_n"] = new_n
            existing["_fidelity_sum"] = new_sum
            existing["fidelity_mean"] = new_sum / new_n if new_n > 0 else 0.0

            session_min = session_agg.get("fidelity_min", 1.0)
            if session_min < existing.get("fidelity_min", 1.0):
                existing["fidelity_min"] = session_min

        # Decision distribution
        for dec, count in session_agg.get("decision_counts", {}).items():
            existing["decision_distribution"][dec] = (
                existing["decision_distribution"].get(dec, 0) + count
            )

        existing["total_boundary_triggers"] += session_agg.get(
            "boundary_triggers", 0
        )

        # Write
        agg_path.write_text(json.dumps(existing, indent=2) + "\n")

    @staticmethod
    def _empty_aggregate(agent_id: str) -> Dict[str, Any]:
        """Create an empty aggregate statistics structure."""
        return {
            "agent_id": agent_id,
            "total_sessions": 0,
            "total_records": 0,
            "last_session_at": None,
            "fidelity_mean": 0.0,
            "fidelity_min": 1.0,
            "_fidelity_n": 0,
            "_fidelity_sum": 0.0,
            "decision_distribution": {},
            "total_boundary_triggers": 0,
        }

    # -------------------------------------------------------------------------
    # Query
    # -------------------------------------------------------------------------

    def get_aggregate(self, agent_id: str = "") -> Optional[Dict[str, Any]]:
        """Read the aggregate statistics for an agent.

        Args:
            agent_id: Agent identifier. Uses config agent_id if empty.

        Returns:
            Aggregate dict or None if no data exists.
        """
        aid = self._validate_id(agent_id or self._config.agent_id, "agent_id")
        storage = Path(self._config.base_dir) / aid
        agg_path = storage / "aggregate.json"

        if not agg_path.exists():
            return None

        try:
            return json.loads(agg_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def list_sessions(self, agent_id: str = "") -> List[Dict[str, Any]]:
        """List session telemetry files for an agent.

        Args:
            agent_id: Agent identifier. Uses config agent_id if empty.

        Returns:
            List of session info dicts (filename, size, timestamp).
        """
        aid = self._validate_id(agent_id or self._config.agent_id, "agent_id")
        sessions_dir = Path(self._config.base_dir) / aid / "sessions"

        if not sessions_dir.exists():
            return []

        sessions = []
        for f in sorted(sessions_dir.glob("*.jsonl")):
            stat = f.stat()
            sessions.append({
                "filename": f.name,
                "path": str(f),
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            })
        return sessions

    def clear_telemetry(self, agent_id: str = "") -> int:
        """Delete all telemetry data for an agent.

        Args:
            agent_id: Agent identifier. Uses config agent_id if empty.

        Returns:
            Number of files deleted.
        """
        aid = self._validate_id(agent_id or self._config.agent_id, "agent_id")
        storage = Path(self._config.base_dir) / aid

        if not storage.exists():
            return 0

        deleted = 0
        sessions_dir = storage / "sessions"
        if sessions_dir.exists():
            for f in sessions_dir.glob("*.jsonl"):
                f.unlink()
                deleted += 1

        agg_path = storage / "aggregate.json"
        if agg_path.exists():
            agg_path.unlink()
            deleted += 1

        return deleted

    def get_status(self) -> Dict[str, Any]:
        """Get the current Intelligence Layer status.

        Returns:
            Status dict with collection state and storage info.
        """
        status = {
            "enabled": self._config.enabled,
            "collection_level": self._config.collection_level,
            "is_collecting": self._is_collecting,
            "base_dir": self._config.base_dir,
            "agent_id": self._config.agent_id,
            "retention_days": self._config.retention_days,
        }

        # Storage stats
        base = Path(self._config.base_dir)
        if base.exists():
            agents = [d.name for d in base.iterdir() if d.is_dir()]
            total_size = sum(
                f.stat().st_size
                for f in base.rglob("*")
                if f.is_file()
            )
            status["storage"] = {
                "agents": agents,
                "total_size_bytes": total_size,
                "agent_count": len(agents),
            }
        else:
            status["storage"] = {
                "agents": [],
                "total_size_bytes": 0,
                "agent_count": 0,
            }

        return status

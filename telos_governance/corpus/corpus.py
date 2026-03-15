"""
Governance Audit Corpus Loader
===============================

Loads TELOS audit JSONL data into structured objects for counterfactual
analysis, parameter sweeps, and research export.

Reads from:
  - ~/.telos/posthoc_audit/{session_id}/{date}.jsonl  (post-hoc audit)
  - Any directory containing .jsonl files with TELOS audit schema
  - Single .jsonl files

Schema reference (from telos_governance intelligence_layer.py):
  Top-level: event_id, timestamp, event_type, session_id, agent_id,
             schema_version, verdict, fidelity{}, tool_call, tool_args{},
             request_text, explanation, metadata{}, previous_event_hash,
             signing_public_key, signature
  Fidelity:  composite, purpose, scope, boundary, tool, chain
  Metadata:  audit_type, tool_use_id, scope_match, scope_score,
             pre_verdict, pre_fidelity, response_summary, correlated

Usage:
    from telos_governance.corpus import load_corpus

    corpus = load_corpus("~/.telos/posthoc_audit/")
    print(corpus.summary())

    # Filter
    escalations = corpus.filter(verdict="ESCALATE")

    # Export (requires telos-gov[research])
    df = corpus.to_dataframe()
    corpus.export("output.parquet", fmt="parquet")
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable


def _get_redact_dict():
    """Lazy import of redact_dict to avoid circular import with guardrails.py."""
    try:
        from telos_governance.guardrails import redact_dict
        return redact_dict
    except ImportError:
        try:
            from guardrails import redact_dict
            return redact_dict
        except ImportError:
            return None


@dataclass(frozen=True)
class AuditEvent:
    """Single governance audit event parsed from JSONL.

    Immutable -- original scores are never modified. Counterfactual
    analysis creates new RescoreResult objects, not modified events.
    """
    event_id: str
    timestamp: str
    session_id: str
    agent_id: str
    verdict: str              # EXECUTE, CLARIFY, INERT, ESCALATE
    # Per-dimension fidelity scores (recorded at scoring time)
    composite: float
    purpose: float
    scope: float
    boundary: float
    tool: float
    chain: float
    # Action identity
    tool_call: str            # Canonical tool name (Read, Write, Bash, etc.)
    tool_args: Dict           # Tool arguments dict
    request_text: str         # Full action text
    explanation: str
    # Metadata
    audit_type: str           # posthoc_verification, live, etc.
    scope_match: bool
    scope_score: float
    pre_verdict: Optional[str]
    pre_fidelity: float
    correlated: bool
    tool_use_id: str
    # Hash chain
    previous_event_hash: str
    # Raw record for anything we didn't parse
    _raw: Dict = field(repr=False, hash=False, compare=False)

    @classmethod
    def from_jsonl(cls, record: Dict) -> "AuditEvent":
        """Parse a single JSONL record into an AuditEvent."""
        fidelity = record.get("fidelity", {})
        metadata = record.get("metadata", {})
        return cls(
            event_id=record.get("event_id", ""),
            timestamp=record.get("timestamp", ""),
            session_id=record.get("session_id", ""),
            agent_id=record.get("agent_id", ""),
            verdict=record.get("verdict", "UNKNOWN"),
            composite=fidelity.get("composite", 0.0),
            purpose=fidelity.get("purpose", 0.0),
            scope=fidelity.get("scope", 0.0),
            boundary=fidelity.get("boundary", 0.0),
            tool=fidelity.get("tool", 0.0),
            chain=fidelity.get("chain", 0.0),
            tool_call=record.get("tool_call", ""),
            tool_args=record.get("tool_args", {}),
            request_text=record.get("request_text", ""),
            explanation=record.get("explanation", ""),
            audit_type=metadata.get("audit_type", ""),
            scope_match=metadata.get("scope_match", False),
            scope_score=metadata.get("scope_score", 0.0),
            pre_verdict=metadata.get("pre_verdict"),
            pre_fidelity=metadata.get("pre_fidelity", 0.0),
            correlated=metadata.get("correlated", False),
            tool_use_id=metadata.get("tool_use_id", ""),
            previous_event_hash=record.get("previous_event_hash", ""),
            _raw=record,
        )


@dataclass
class AuditCorpus:
    """Collection of governance audit events.

    Supports filtering, summary statistics, and export to DataFrames
    and file formats. This is the primary object for counterfactual
    analysis -- pass it to rescore() and sweep().
    """
    events: List[AuditEvent]
    source_path: str

    def __len__(self) -> int:
        return len(self.events)

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            return AuditCorpus(events=self.events[idx], source_path=self.source_path)
        return self.events[idx]

    def __iter__(self):
        return iter(self.events)

    @property
    def sessions(self) -> List[str]:
        """Unique session IDs in this corpus."""
        return sorted(set(e.session_id for e in self.events))

    @property
    def n_sessions(self) -> int:
        return len(self.sessions)

    def filter(
        self,
        verdict: Optional[str] = None,
        tool: Optional[str] = None,
        session: Optional[str] = None,
        min_composite: Optional[float] = None,
        max_composite: Optional[float] = None,
        correlated: Optional[bool] = None,
        predicate: Optional[Callable[["AuditEvent"], bool]] = None,
    ) -> "AuditCorpus":
        """Filter events. Returns a new AuditCorpus with matching events.

        All filters compose with AND logic.

        Args:
            verdict: Match exact verdict (EXECUTE, CLARIFY, INERT, ESCALATE)
            tool: Match tool_call name (case-insensitive)
            session: Match session_id
            min_composite: Minimum composite fidelity
            max_composite: Maximum composite fidelity
            correlated: Filter by correlation status
            predicate: Arbitrary filter function
        """
        filtered = self.events
        if verdict is not None:
            v_upper = verdict.upper()
            filtered = [e for e in filtered if e.verdict == v_upper]
        if tool is not None:
            t_lower = tool.lower()
            filtered = [e for e in filtered if e.tool_call.lower() == t_lower]
        if session is not None:
            filtered = [e for e in filtered if e.session_id == session]
        if min_composite is not None:
            filtered = [e for e in filtered if e.composite >= min_composite]
        if max_composite is not None:
            filtered = [e for e in filtered if e.composite <= max_composite]
        if correlated is not None:
            filtered = [e for e in filtered if e.correlated == correlated]
        if predicate is not None:
            filtered = [e for e in filtered if predicate(e)]
        return AuditCorpus(events=filtered, source_path=self.source_path)

    def summary(self) -> Dict:
        """Compute corpus summary statistics.

        Returns dict with keys: n_events, n_sessions, date_range,
        verdict_distribution, tool_distribution, fidelity_stats.
        """
        if not self.events:
            return {"n_events": 0}

        verdicts: Dict[str, int] = {}
        tools: Dict[str, int] = {}
        composites = []
        timestamps = []

        for e in self.events:
            verdicts[e.verdict] = verdicts.get(e.verdict, 0) + 1
            tools[e.tool_call] = tools.get(e.tool_call, 0) + 1
            composites.append(e.composite)
            if e.timestamp:
                timestamps.append(e.timestamp)

        composites.sort()
        n = len(composites)

        return {
            "n_events": n,
            "n_sessions": self.n_sessions,
            "date_range": (min(timestamps), max(timestamps)) if timestamps else None,
            "verdict_distribution": dict(sorted(verdicts.items())),
            "tool_distribution": dict(sorted(tools.items(), key=lambda x: -x[1])),
            "fidelity_stats": {
                "mean": sum(composites) / n,
                "median": composites[n // 2],
                "p5": composites[int(n * 0.05)] if n > 20 else composites[0],
                "p95": composites[int(n * 0.95)] if n > 20 else composites[-1],
            },
        }

    def summary_table(self) -> str:
        """Format summary as a human-readable table string."""
        s = self.summary()
        if s["n_events"] == 0:
            return "Empty corpus (0 events)"

        lines = [
            "TELOS Audit Corpus Summary",
            "=" * 26,
            f"Source:     {self.source_path}",
            f"Events:     {s['n_events']}",
            f"Sessions:   {s['n_sessions']}",
        ]
        if s["date_range"]:
            lines.append(f"Date range: {s['date_range'][0][:10]} to {s['date_range'][1][:10]}")

        lines.append("")
        lines.append("Verdict Distribution:")
        for v, count in s["verdict_distribution"].items():
            pct = count / s["n_events"] * 100
            lines.append(f"  {v:<12} {count:>5}  ({pct:>5.1f}%)")

        lines.append("")
        lines.append("Tools Used:")
        for tool, count in list(s["tool_distribution"].items())[:10]:
            pct = count / s["n_events"] * 100
            lines.append(f"  {tool:<16} {count:>5}  ({pct:>5.1f}%)")

        f = s["fidelity_stats"]
        lines.append("")
        lines.append("Fidelity Distribution:")
        lines.append(f"  Mean:   {f['mean']:.3f}")
        lines.append(f"  Median: {f['median']:.3f}")
        lines.append(f"  P5:     {f['p5']:.3f}")
        lines.append(f"  P95:    {f['p95']:.3f}")

        return "\n".join(lines)

    def to_dataframe(self):
        """Export to pandas DataFrame. Requires telos-gov[research].

        Returns one row per event with all fidelity dimensions as columns.
        Analysis-ready: df.groupby("verdict")["composite"].describe() works.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for DataFrame export. "
                "Install with: pip install telos-gov[research]"
            )

        rows = []
        for e in self.events:
            rows.append({
                "event_id": e.event_id,
                "timestamp": e.timestamp,
                "session_id": e.session_id,
                "agent_id": e.agent_id,
                "verdict": e.verdict,
                "composite": e.composite,
                "purpose": e.purpose,
                "scope": e.scope,
                "boundary": e.boundary,
                "tool_fidelity": e.tool,
                "chain": e.chain,
                "tool_call": e.tool_call,
                "request_text": e.request_text,
                "explanation": e.explanation,
                "scope_match": e.scope_match,
                "scope_score": e.scope_score,
                "pre_verdict": e.pre_verdict,
                "pre_fidelity": e.pre_fidelity,
                "correlated": e.correlated,
                "tool_use_id": e.tool_use_id,
            })
        return pd.DataFrame(rows)

    def export(self, path: str, fmt: str = "csv", zone: int = 1) -> None:
        """Export corpus to file with zone-based redaction.

        Zone 1 (default): Scores, verdicts, metadata only. Zone 2 fields
        (request_text, explanation, tool_args) are stripped. Zone 3 fields
        (_raw payloads) are never exported.

        Zone 2: Zone 2 fields included but redacted (credentials, PII,
        paths replaced with placeholders).

        Args:
            path: Output file path
            fmt: Format -- "csv", "jsonl", or "parquet" (requires pyarrow)
            zone: Redaction zone (1=public export, 2=internal). Zone 3
                fields are always stripped regardless of this setting.
        """
        if fmt == "csv":
            df = self.to_dataframe()
            df.to_csv(path, index=False)
        elif fmt == "jsonl":
            with open(path, "w") as f:
                for event in self.events:
                    record = dict(event._raw)
                    # Always strip _raw from export (Zone 3)
                    record.pop("_raw", None)
                    record.pop("raw_payload", None)
                    record.pop("raw_request", None)
                    record.pop("raw_response", None)
                    # Apply zone-based redaction
                    _redact = _get_redact_dict()
                    if _redact is not None:
                        record = _redact(record, level=2, zone=zone)
                    f.write(json.dumps(record, default=str) + "\n")
        elif fmt == "parquet":
            try:
                df = self.to_dataframe()
                df.to_parquet(path, index=False)
            except ImportError:
                raise ImportError(
                    "pyarrow is required for Parquet export. "
                    "Install with: pip install telos-gov[research]"
                )
        else:
            raise ValueError(f"Unknown format: {fmt}. Use csv, jsonl, or parquet.")


def load_corpus(path: str, max_events: int = 50000) -> AuditCorpus:
    """Load TELOS audit JSONL data from a path.

    Accepts:
      - A directory (recursively finds all .jsonl files)
      - A single .jsonl file
      - A path with ~ (expanded)

    Args:
        path: Path to a directory or .jsonl file.
        max_events: Maximum number of events to load (default 50000).
            Prevents OOM on large deployments. Set to 0 for unlimited.

    Returns:
        AuditCorpus with all events loaded and sorted by timestamp.

    Example:
        corpus = load_corpus("~/.telos/posthoc_audit/")
        corpus = load_corpus("/path/to/2026-02-27.jsonl")
        corpus = load_corpus("~/.telos/posthoc_audit/", max_events=10000)
    """
    resolved = os.path.expanduser(path)

    if not os.path.exists(resolved):
        raise FileNotFoundError(f"Path not found: {resolved}")

    jsonl_files = []
    if os.path.isdir(resolved):
        for root, _dirs, files in os.walk(resolved):
            for fname in files:
                if fname.endswith(".jsonl"):
                    jsonl_files.append(os.path.join(root, fname))
    elif os.path.isfile(resolved) and resolved.endswith(".jsonl"):
        jsonl_files.append(resolved)
    else:
        raise ValueError(f"Path is not a directory or .jsonl file: {resolved}")

    if not jsonl_files:
        raise FileNotFoundError(f"No .jsonl files found in {resolved}")

    events = []
    parse_errors = 0
    cap_reached = False
    for filepath in sorted(jsonl_files):
        if cap_reached:
            break
        with open(filepath, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    # Only load events that have a verdict (skip supervisor
                    # lifecycle events, capability probes, etc.)
                    if record.get("verdict"):
                        events.append(AuditEvent.from_jsonl(record))
                        if max_events > 0 and len(events) >= max_events:
                            import logging as _logging
                            _logging.getLogger(__name__).warning(
                                "Corpus cap reached: loaded %d events (max_events=%d). "
                                "Remaining events skipped to prevent OOM.",
                                len(events), max_events,
                            )
                            cap_reached = True
                            break
                except (json.JSONDecodeError, KeyError) as exc:
                    parse_errors += 1
                    if parse_errors <= 3:
                        import sys
                        print(
                            f"Warning: parse error in {filepath}:{line_num}: {exc}",
                            file=sys.stderr,
                        )

    # Sort by timestamp for consistent ordering
    events.sort(key=lambda e: e.timestamp)

    return AuditCorpus(events=events, source_path=path)

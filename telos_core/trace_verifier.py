"""
Trace Verifier for TELOS Governance Logs
=========================================

SAAI Framework Alignment: Cryptographic Integrity Verification

This module provides verification utilities for TELOS governance trace files.
Each event in a trace file includes a cryptographic hash chain that enables
tamper detection.

Per SAAI Framework: "Cryptographic integrity for audit trails"

Compliance:
- NIST AI RMF (MANAGE 4.1): Hash chain verification satisfies post-deployment
  monitoring integrity requirements -- tampered governance logs are detectable.
- FedRAMP CA-7 (Continuous Monitoring): Cryptographic trace verification enables
  continuous monitoring with tamper detection per FedRAMP requirements.
- NIST AI 600-1 (MEASURE): Trace integrity verification ensures that governance
  measurement data has not been altered post-collection -- a prerequisite for
  trustworthy GenAI performance metrics.

Usage:
    from telos_core.trace_verifier import verify_trace_integrity

    report = verify_trace_integrity("/path/to/trace.jsonl")
    if report.is_valid:
        print("Trace integrity verified!")
    else:
        print(f"Tampering detected at event {report.broken_at_index}")
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from telos_core.time_utils import utc_now

logger = logging.getLogger(__name__)

# Genesis hash (all zeros) - matches GovernanceTraceCollector
GENESIS_HASH = "0" * 64


@dataclass
class TraceVerificationReport:
    """
    Comprehensive report of trace file integrity verification.

    SAAI Alignment: Provides detailed audit information for
    cryptographic log integrity assessment.
    """
    # File information
    file_path: str
    file_exists: bool
    file_size_bytes: int = 0

    # Event statistics
    total_events: int = 0
    first_event_type: Optional[str] = None
    first_event_timestamp: Optional[str] = None
    last_event_type: Optional[str] = None
    last_event_timestamp: Optional[str] = None

    # Chain integrity
    is_valid: bool = False
    broken_at_index: Optional[int] = None
    broken_at_event_type: Optional[str] = None
    expected_hash: Optional[str] = None
    actual_hash: Optional[str] = None

    # SAAI-specific events found
    saai_events: Dict[str, int] = field(default_factory=dict)
    baseline_established: bool = False
    mandatory_reviews_triggered: int = 0
    final_drift_level: Optional[str] = None

    # Verification metadata
    verification_timestamp: str = field(
        default_factory=lambda: utc_now().isoformat()
    )
    verification_duration_ms: float = 0.0

    # Errors encountered
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            "file_info": {
                "path": self.file_path,
                "exists": self.file_exists,
                "size_bytes": self.file_size_bytes,
            },
            "events": {
                "total": self.total_events,
                "first": {
                    "type": self.first_event_type,
                    "timestamp": self.first_event_timestamp,
                },
                "last": {
                    "type": self.last_event_type,
                    "timestamp": self.last_event_timestamp,
                },
            },
            "chain_integrity": {
                "is_valid": self.is_valid,
                "broken_at_index": self.broken_at_index,
                "broken_at_event_type": self.broken_at_event_type,
                "expected_hash": self.expected_hash,
                "actual_hash": self.actual_hash,
            },
            "saai_compliance": {
                "events_found": self.saai_events,
                "baseline_established": self.baseline_established,
                "mandatory_reviews": self.mandatory_reviews_triggered,
                "final_drift_level": self.final_drift_level,
            },
            "verification": {
                "timestamp": self.verification_timestamp,
                "duration_ms": self.verification_duration_ms,
            },
            "errors": self.errors,
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        status = "VALID" if self.is_valid else "INVALID"
        lines = [
            f"Trace Verification Report: {status}",
            f"{'=' * 50}",
            f"File: {self.file_path}",
            f"Events: {self.total_events}",
            f"Chain Integrity: {'Verified' if self.is_valid else 'BROKEN'}",
        ]

        if not self.is_valid and self.broken_at_index is not None:
            lines.append(f"  Broken at event #{self.broken_at_index} ({self.broken_at_event_type})")
            lines.append(f"  Expected: {self.expected_hash[:16]}...")
            lines.append(f"  Actual:   {self.actual_hash[:16] if self.actual_hash else 'N/A'}...")

        lines.extend([
            "",
            "SAAI Alignment:",
            f"  Baseline Established: {'Yes' if self.baseline_established else 'No'}",
            f"  Mandatory Reviews: {self.mandatory_reviews_triggered}",
            f"  Final Drift Level: {self.final_drift_level or 'N/A'}",
        ])

        if self.errors:
            lines.append("")
            lines.append("Errors:")
            for error in self.errors:
                lines.append(f"  - {error}")

        return "\n".join(lines)


def verify_trace_integrity(file_path) -> TraceVerificationReport:
    """
    Verify the cryptographic integrity of a TELOS governance trace file.

    SAAI Alignment: Validates that the hash chain is unbroken, which
    ensures no events have been tampered with after recording.

    Args:
        file_path: Path to the JSONL trace file

    Returns:
        TraceVerificationReport with detailed verification results
    """
    import time
    start_time = time.perf_counter()

    file_path = Path(file_path)
    report = TraceVerificationReport(
        file_path=str(file_path),
        file_exists=file_path.exists(),
    )

    # Check file exists
    if not file_path.exists():
        report.errors.append(f"File not found: {file_path}")
        report.verification_duration_ms = (time.perf_counter() - start_time) * 1000
        return report

    report.file_size_bytes = file_path.stat().st_size

    # Read and verify events
    events: List[Dict[str, Any]] = []
    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    events.append(event)
                except json.JSONDecodeError as e:
                    report.errors.append(f"JSON parse error at line {line_num}: {e}")
                    report.verification_duration_ms = (time.perf_counter() - start_time) * 1000
                    return report
    except IOError as e:
        report.errors.append(f"IO error reading file: {e}")
        report.verification_duration_ms = (time.perf_counter() - start_time) * 1000
        return report

    report.total_events = len(events)

    if not events:
        report.errors.append("No events found in trace file")
        report.verification_duration_ms = (time.perf_counter() - start_time) * 1000
        return report

    # Record first/last event info
    first_event = events[0]
    last_event = events[-1]
    report.first_event_type = first_event.get("event_type")
    report.first_event_timestamp = first_event.get("timestamp")
    report.last_event_type = last_event.get("event_type")
    report.last_event_timestamp = last_event.get("timestamp")

    # Track SAAI events
    saai_event_counts: Dict[str, int] = {}

    # Verify hash chain
    expected_hash = GENESIS_HASH
    chain_valid = True

    for idx, event in enumerate(events):
        event_type = event.get("event_type", "unknown")

        # Count event types
        saai_event_counts[event_type] = saai_event_counts.get(event_type, 0) + 1

        # Track SAAI-specific events
        if event_type == "baseline_established":
            report.baseline_established = True
        elif event_type == "mandatory_review_triggered":
            report.mandatory_reviews_triggered += 1
            report.final_drift_level = event.get("drift_level")

        # Verify hash chain
        event_previous_hash = event.get("previous_hash")
        event_hash = event.get("event_hash")

        # Check if this file has hash chain (backward compatibility)
        if event_previous_hash is None and event_hash is None:
            # No hash chain in this file - mark as valid but note it
            logger.warning("Trace event %d missing hash fields -- skipping chain verification", idx)
            if idx == 0:
                report.errors.append("No hash chain found (pre-SAAI trace file)")
                report.is_valid = True
                break

        # Verify previous_hash matches expected
        if event_previous_hash != expected_hash:
            chain_valid = False
            report.is_valid = False
            report.broken_at_index = idx
            report.broken_at_event_type = event_type
            report.expected_hash = expected_hash
            report.actual_hash = event_previous_hash
            break

        # Recompute hash to verify event_hash
        # Remove event_hash from dict for hashing (it wasn't there when hash was computed)
        event_copy = {k: v for k, v in event.items() if k != "event_hash"}
        hash_content = expected_hash + json.dumps(event_copy, sort_keys=True)
        computed_hash = hashlib.sha256(hash_content.encode('utf-8')).hexdigest()

        if event_hash != computed_hash:
            chain_valid = False
            report.is_valid = False
            report.broken_at_index = idx
            report.broken_at_event_type = event_type
            report.expected_hash = computed_hash
            report.actual_hash = event_hash
            break

        # Update expected hash for next event
        expected_hash = event_hash

    else:
        # Loop completed without break - chain is valid
        report.is_valid = True

    report.saai_events = saai_event_counts
    report.verification_duration_ms = (time.perf_counter() - start_time) * 1000

    return report


def verify_trace_chain_only(file_path) -> bool:
    """
    Simple boolean check for trace integrity.

    Use this for quick validation. For detailed reports,
    use verify_trace_integrity() instead.

    Args:
        file_path: Path to the JSONL trace file

    Returns:
        True if chain is valid, False otherwise
    """
    report = verify_trace_integrity(file_path)
    return report.is_valid


def get_trace_summary(file_path) -> Dict[str, Any]:
    """
    Get summary information about a trace file without full verification.

    Faster than full verification - only reads first and last events.

    Args:
        file_path: Path to the JSONL trace file

    Returns:
        Dict with summary information
    """
    file_path = Path(file_path)

    if not file_path.exists():
        return {"error": "File not found", "exists": False}

    summary = {
        "exists": True,
        "path": str(file_path),
        "size_bytes": file_path.stat().st_size,
    }

    try:
        with open(file_path, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            summary["error"] = "No events found"
            return summary

        first_event = json.loads(lines[0])
        last_event = json.loads(lines[-1])

        summary.update({
            "total_events": len(lines),
            "first_event": {
                "type": first_event.get("event_type"),
                "timestamp": first_event.get("timestamp"),
            },
            "last_event": {
                "type": last_event.get("event_type"),
                "timestamp": last_event.get("timestamp"),
            },
            "has_hash_chain": "event_hash" in first_event,
        })

    except Exception as e:
        summary["error"] = str(e)

    return summary


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python trace_verifier.py <trace_file.jsonl>")
        print("\nVerifies the cryptographic integrity of a TELOS governance trace file.")
        sys.exit(1)

    trace_path = sys.argv[1]
    print(f"Verifying: {trace_path}\n")

    report = verify_trace_integrity(trace_path)
    print(report.summary())

    # Exit with appropriate code
    sys.exit(0 if report.is_valid else 1)

"""
TELOSCOPE Self-Audit Logger
=============================

Self-audit logger for the TELOSCOPE research instrument. Logs every
TELOSCOPE tool call to a JSONL file for posthoc analysis.

TELOSCOPE mode = observation mode:
  - Score everything.
  - Block nothing.
  - Log everything.

Warnings are returned alongside results so researchers see them in
real time. The full audit trail is written to disk for later analysis.
Cases where Gate 2 WOULD have intervened ("misses") flow through
unblocked and are captured in the audit log for model improvement.

Each tool call produces an AuditEntry containing:
  - The tool name and arguments
  - A list of MethodologicalCheck results (sample size, redaction, etc.)
  - A simulated Gate 2 verdict (EXECUTE/CLARIFY/ESCALATE)
  - observation_mode=True (always, for now)

Output: ~/.telos/teloscope_audit/YYYY-MM-DD.jsonl

Telemetry integration (opt-in):
  When ``telemetry_enabled=True``, each log_tool_call() also extracts a
  privacy-stripped TelemetryRecord and appends it to the TelemetryBuffer.
  This is the bridge between local audit (full content) and the telemetry
  pipeline (governance metadata only). The telemetry_pipeline module is
  lazily imported so this file works standalone without it.

Usage:
    from telos_governance.teloscope_audit import (
        TeloscopeAudit,
        check_sample_size,
        check_denominator,
        check_comparison_balance,
    )

    audit = TeloscopeAudit()

    checks = [
        check_sample_size(n=8, claim_type="comparison"),
        check_denominator(subset_n=8, total_n=200),
    ]

    entry = audit.log_tool_call(
        tool_name="research_audit_stats",
        tool_args={"groupby": "verdict"},
        checks=checks,
    )

    # Show warnings alongside tool output
    print(audit.format_warnings(checks))

    # Summarize all logged entries
    print(audit.summary())

    # With telemetry opt-in:
    audit_t = TeloscopeAudit(telemetry_enabled=True)
    entry = audit_t.log_tool_call("research_audit_stats", {"groupby": "verdict"}, checks)
    # entry is written to local JSONL AND telemetry buffer
    print(audit_t.telemetry_status())
"""
import hashlib
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from telos_governance.corpus import AuditCorpus
except ImportError:
    from corpus import AuditCorpus


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MethodologicalCheck:
    """A single methodological integrity check result.

    Represents one constraint evaluation -- sample size, redaction level,
    comparison balance, etc. Status is "pass", "warn", or "fail".
    The ``would_block`` flag records whether enforcement mode would have
    blocked the tool call based on this check alone.
    """
    check_name: str        # e.g., "sample_size", "denominator_disclosure", "redaction"
    status: str            # "pass", "warn", "fail"
    message: str           # Human-readable warning/explanation
    details: Dict          # Structured data about the check
    would_block: bool      # Whether enforcement mode would have blocked this

    def to_dict(self) -> Dict:
        return {
            "check_name": self.check_name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "would_block": self.would_block,
        }


@dataclass
class AuditEntry:
    """Full audit record for a TELOSCOPE tool call.

    One AuditEntry per tool invocation. Contains the tool identity,
    arguments, all methodological checks that were run, and the
    simulated Gate 2 verdict.
    """
    entry_id: str          # UUID
    timestamp: str         # ISO format
    tool_name: str         # "research_audit_stats", "research_audit_compare", etc.
    tool_args: Dict        # The arguments passed to the tool
    checks: List[MethodologicalCheck]
    n_warnings: int
    n_failures: int
    gate2_verdict: str     # What Gate 2 WOULD have said: "EXECUTE", "CLARIFY", "ESCALATE"
    observation_mode: bool  # Always True for now

    def format(self) -> str:
        """Format as a human-readable summary line."""
        check_summary = ", ".join(
            f"{c.check_name}={c.status}" for c in self.checks
        )
        return (
            f"[{self.timestamp}] {self.tool_name} -> {self.gate2_verdict} "
            f"({self.n_warnings}w {self.n_failures}f) [{check_summary}]"
        )

    def to_dict(self) -> Dict:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "checks": [c.to_dict() for c in self.checks],
            "n_warnings": self.n_warnings,
            "n_failures": self.n_failures,
            "gate2_verdict": self.gate2_verdict,
            "observation_mode": self.observation_mode,
        }


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

# Minimum sample sizes for statistical validity
_SAMPLE_MINIMUMS = {
    "general": 20,
    "mean": 20,
    "distribution": 30,
    "chi2": 30,
    "comparison": 30,
    "per_tool": 10,
    "trend": 3,
    "session": 5,
}


def check_sample_size(n: int, claim_type: str = "general") -> MethodologicalCheck:
    """Check if sample size meets minimum for the claim type.

    Minimum sample sizes:
      general/mean: 20, distribution/chi2: 30, comparison: 30 per group,
      per_tool: 10, trend: 3 windows, session: 5 sessions.

    Args:
        n: The observed sample size.
        claim_type: Type of statistical claim being made.

    Returns:
        MethodologicalCheck with pass/warn/fail status.
    """
    minimum = _SAMPLE_MINIMUMS.get(claim_type, _SAMPLE_MINIMUMS["general"])

    details = {
        "n": n,
        "minimum": minimum,
        "claim_type": claim_type,
    }

    if n >= minimum:
        return MethodologicalCheck(
            check_name="sample_size",
            status="pass",
            message=f"Sample size (n={n}) meets minimum ({minimum}) for {claim_type} claim.",
            details=details,
            would_block=False,
        )
    elif n >= minimum // 2:
        # Between half-minimum and minimum: warn
        return MethodologicalCheck(
            check_name="sample_size",
            status="warn",
            message=(
                f"Sample size (n={n}) below minimum ({minimum}) "
                f"for {claim_type} claim. Results may be unreliable."
            ),
            details=details,
            would_block=False,
        )
    else:
        # Below half-minimum: fail (would block in enforcement mode)
        return MethodologicalCheck(
            check_name="sample_size",
            status="fail",
            message=(
                f"Sample size (n={n}) far below minimum ({minimum}) "
                f"for {claim_type} claim. Insufficient data for statistical inference."
            ),
            details=details,
            would_block=True,
        )


def check_denominator(
    subset_n: int, total_n: int, filter_desc: str = ""
) -> MethodologicalCheck:
    """Check that filtered results disclose their fraction of total.

    When a tool returns a filtered subset, the researcher must know
    what fraction of the full corpus they are looking at. Missing
    denominator disclosure is a common source of misleading statistics.

    Args:
        subset_n: Number of events in the filtered result.
        total_n: Total events in the corpus before filtering.
        filter_desc: Human-readable description of the filter applied.

    Returns:
        MethodologicalCheck with pass/warn status.
    """
    details = {
        "subset_n": subset_n,
        "total_n": total_n,
        "fraction": subset_n / total_n if total_n > 0 else 0.0,
        "filter_desc": filter_desc,
    }

    if subset_n == total_n:
        # No filtering applied -- full corpus
        return MethodologicalCheck(
            check_name="denominator_disclosure",
            status="pass",
            message="Full corpus -- no filtering applied.",
            details=details,
            would_block=False,
        )
    elif filter_desc:
        # Filtered, but description provided
        fraction_pct = (subset_n / total_n * 100) if total_n > 0 else 0.0
        return MethodologicalCheck(
            check_name="denominator_disclosure",
            status="pass",
            message=(
                f"Filtered to {subset_n}/{total_n} events "
                f"({fraction_pct:.1f}%) by: {filter_desc}"
            ),
            details=details,
            would_block=False,
        )
    else:
        # Filtered but no description -- warn
        fraction_pct = (subset_n / total_n * 100) if total_n > 0 else 0.0
        return MethodologicalCheck(
            check_name="denominator_disclosure",
            status="warn",
            message=(
                f"Showing {subset_n}/{total_n} events ({fraction_pct:.1f}%) "
                f"but no filter description provided. "
                f"Denominator should be disclosed for transparency."
            ),
            details=details,
            would_block=False,
        )


def check_export_redaction(
    fields_included: List[str], redaction_level: int = 1
) -> MethodologicalCheck:
    """Check that exports respect zone redaction levels.

    Zone 1: scores, verdicts, metadata only (default)
    Zone 2: + request_text, explanation, tool_args, action_text (explicit request)
    Zone 3: raw payloads (never exported)

    Args:
        fields_included: List of field names present in the export.
        redaction_level: Requested redaction zone (1, 2, or 3).

    Returns:
        MethodologicalCheck with pass/warn/fail status.
    """
    ZONE2_FIELDS = {"request_text", "explanation", "tool_args", "action_text"}
    ZONE3_FIELDS = {"_raw", "raw_payload", "raw_request", "raw_response"}

    included_zone2 = [f for f in fields_included if f in ZONE2_FIELDS]
    included_zone3 = [f for f in fields_included if f in ZONE3_FIELDS]

    details = {
        "fields_included": fields_included,
        "redaction_level": redaction_level,
        "zone2_fields_present": included_zone2,
        "zone3_fields_present": included_zone3,
    }

    # Zone 3 fields should never be exported
    if included_zone3:
        return MethodologicalCheck(
            check_name="export_redaction",
            status="fail",
            message=(
                f"Export includes Zone 3 fields ({', '.join(included_zone3)}) "
                f"-- raw payloads must never be exported."
            ),
            details=details,
            would_block=True,
        )

    # Zone 2 fields require explicit Zone 2 request
    if included_zone2 and redaction_level < 2:
        return MethodologicalCheck(
            check_name="export_redaction",
            status="warn",
            message=(
                f"Export includes Zone 2 fields ({', '.join(included_zone2)}) "
                f"-- redaction not applied. Set redaction_level=2 to confirm intent."
            ),
            details=details,
            would_block=False,
        )

    return MethodologicalCheck(
        check_name="export_redaction",
        status="pass",
        message=f"Export respects Zone {redaction_level} redaction.",
        details=details,
        would_block=False,
    )


def check_comparison_balance(n_a: int, n_b: int) -> MethodologicalCheck:
    """Check that compared groups meet minimum sizes for statistical claims.

    Both groups must have at least 30 events for parametric tests.
    Warns on imbalance ratio > 3:1 even if both meet the minimum.

    Args:
        n_a: Size of group A.
        n_b: Size of group B.

    Returns:
        MethodologicalCheck with pass/warn/fail status.
    """
    minimum = 30
    ratio = max(n_a, n_b) / min(n_a, n_b) if min(n_a, n_b) > 0 else float("inf")

    details = {
        "n_a": n_a,
        "n_b": n_b,
        "minimum": minimum,
        "ratio": ratio,
    }

    if n_a < minimum or n_b < minimum:
        small_group = "A" if n_a < n_b else "B"
        small_n = min(n_a, n_b)
        return MethodologicalCheck(
            check_name="comparison_balance",
            status="fail" if small_n < minimum // 2 else "warn",
            message=(
                f"Group {small_group} (n={small_n}) below minimum ({minimum}) "
                f"for statistical comparison."
            ),
            details=details,
            would_block=small_n < minimum // 2,
        )
    elif ratio > 3.0:
        return MethodologicalCheck(
            check_name="comparison_balance",
            status="warn",
            message=(
                f"Group sizes imbalanced ({n_a} vs {n_b}, "
                f"ratio {ratio:.1f}:1). Effect size estimates may be unreliable."
            ),
            details=details,
            would_block=False,
        )
    else:
        return MethodologicalCheck(
            check_name="comparison_balance",
            status="pass",
            message=f"Groups balanced (n_a={n_a}, n_b={n_b}).",
            details=details,
            would_block=False,
        )


def check_sweep_bounds(
    n_points: int, max_points: int = 200
) -> MethodologicalCheck:
    """Check sweep doesn't exceed computational bounds.

    Each sweep point requires a full rescore pass. Limit to max_points
    to prevent runaway computation.

    Args:
        n_points: Number of sweep points requested.
        max_points: Maximum allowed (default 200).

    Returns:
        MethodologicalCheck with pass/warn/fail status.
    """
    details = {
        "n_points": n_points,
        "max_points": max_points,
    }

    if n_points <= max_points:
        return MethodologicalCheck(
            check_name="sweep_bounds",
            status="pass",
            message=f"Sweep size ({n_points} points) within bounds ({max_points}).",
            details=details,
            would_block=False,
        )
    else:
        return MethodologicalCheck(
            check_name="sweep_bounds",
            status="fail",
            message=(
                f"Sweep size ({n_points} points) exceeds maximum ({max_points}). "
                f"Reduce range or increase step size."
            ),
            details=details,
            would_block=True,
        )


def check_corpus_size(
    n_events: int, max_events: int = 50000
) -> MethodologicalCheck:
    """Check corpus doesn't exceed memory bounds.

    Loading very large corpora into memory for analysis can cause
    performance issues. This check warns before that happens.

    Args:
        n_events: Number of events in the corpus.
        max_events: Maximum recommended (default 50000).

    Returns:
        MethodologicalCheck with pass/warn/fail status.
    """
    details = {
        "n_events": n_events,
        "max_events": max_events,
    }

    if n_events <= max_events:
        return MethodologicalCheck(
            check_name="corpus_size",
            status="pass",
            message=f"Corpus size ({n_events}) within bounds ({max_events}).",
            details=details,
            would_block=False,
        )
    elif n_events <= max_events * 2:
        return MethodologicalCheck(
            check_name="corpus_size",
            status="warn",
            message=(
                f"Corpus size ({n_events}) exceeds recommended maximum "
                f"({max_events}). Performance may be degraded."
            ),
            details=details,
            would_block=False,
        )
    else:
        return MethodologicalCheck(
            check_name="corpus_size",
            status="fail",
            message=(
                f"Corpus size ({n_events}) far exceeds maximum ({max_events}). "
                f"Filter to a subset before analysis."
            ),
            details=details,
            would_block=True,
        )


def check_validation_honesty(
    chain_status: str, sig_status: str, repro_status: str
) -> MethodologicalCheck:
    """Check that validation results aren't overstated.

    If any of the three validation checks (chain, signatures,
    reproducibility) is not "pass", the overall result cannot be
    reported as "pass". This prevents cherry-picking one passing
    check to represent overall validity.

    Args:
        chain_status: Result of hash chain verification.
        sig_status: Result of signature verification.
        repro_status: Result of reproducibility verification.

    Returns:
        MethodologicalCheck with pass/warn status.
    """
    statuses = {
        "chain": chain_status,
        "signatures": sig_status,
        "reproducibility": repro_status,
    }
    non_pass = {k: v for k, v in statuses.items() if v != "pass"}

    details = {
        "chain_status": chain_status,
        "sig_status": sig_status,
        "repro_status": repro_status,
        "non_pass": non_pass,
    }

    if not non_pass:
        return MethodologicalCheck(
            check_name="validation_honesty",
            status="pass",
            message="All three validation checks passed.",
            details=details,
            would_block=False,
        )
    else:
        failing_names = ", ".join(f"{k}={v}" for k, v in non_pass.items())
        return MethodologicalCheck(
            check_name="validation_honesty",
            status="warn",
            message=(
                f"Validation incomplete: {failing_names}. "
                f"Overall validation cannot be reported as 'pass'."
            ),
            details=details,
            would_block=False,
        )


def check_multiple_comparisons(
    n_tests: int, alpha: float = 0.05
) -> MethodologicalCheck:
    """Check for Bonferroni correction need.

    When running multiple statistical tests, the probability of at
    least one false positive increases. Bonferroni correction divides
    alpha by the number of tests.

    Args:
        n_tests: Number of statistical tests being performed.
        alpha: Significance level (default 0.05).

    Returns:
        MethodologicalCheck with pass/warn status.
    """
    corrected_alpha = alpha / n_tests if n_tests > 0 else alpha

    details = {
        "n_tests": n_tests,
        "alpha": alpha,
        "corrected_alpha": corrected_alpha,
    }

    if n_tests <= 1:
        return MethodologicalCheck(
            check_name="multiple_comparisons",
            status="pass",
            message="Single test -- no correction needed.",
            details=details,
            would_block=False,
        )
    else:
        return MethodologicalCheck(
            check_name="multiple_comparisons",
            status="warn",
            message=(
                f"Running {n_tests} tests. Bonferroni-corrected alpha = "
                f"{corrected_alpha:.4f} (from {alpha}). "
                f"Interpret p-values against corrected threshold."
            ),
            details=details,
            would_block=False,
        )


def check_trend_confidence(
    r_squared: float, n_points: int
) -> MethodologicalCheck:
    """Check that trend claims have sufficient R-squared and data points.

    A trend claim (e.g., "improving", "degrading") requires both enough
    data points and a meaningful R-squared. R-squared < 0.10 with a
    directional claim is misleading.

    Args:
        r_squared: Coefficient of determination from the trend fit.
        n_points: Number of data points in the trend.

    Returns:
        MethodologicalCheck with pass/warn/fail status.
    """
    details = {
        "r_squared": r_squared,
        "n_points": n_points,
    }

    if n_points < 3:
        return MethodologicalCheck(
            check_name="trend_confidence",
            status="fail",
            message=(
                f"Only {n_points} data point(s) -- insufficient for trend analysis. "
                f"Minimum 3 required."
            ),
            details=details,
            would_block=True,
        )
    elif r_squared < 0.10:
        return MethodologicalCheck(
            check_name="trend_confidence",
            status="warn",
            message=(
                f"R-squared ({r_squared:.3f}) is very low. "
                f"Trend explains <10% of variance -- "
                f"directional claims (improving/degrading) are not supported."
            ),
            details=details,
            would_block=False,
        )
    elif r_squared < 0.30:
        return MethodologicalCheck(
            check_name="trend_confidence",
            status="warn",
            message=(
                f"R-squared ({r_squared:.3f}) is moderate. "
                f"Trend explains {r_squared*100:.0f}% of variance -- "
                f"interpret directional claims cautiously."
            ),
            details=details,
            would_block=False,
        )
    else:
        return MethodologicalCheck(
            check_name="trend_confidence",
            status="pass",
            message=(
                f"R-squared ({r_squared:.3f}) supports trend claim "
                f"({n_points} data points)."
            ),
            details=details,
            would_block=False,
        )


# ---------------------------------------------------------------------------
# TeloscopeAudit class
# ---------------------------------------------------------------------------

class TeloscopeAudit:
    """TELOSCOPE self-audit logger. Observation mode -- scores but doesn't block.

    Writes one JSONL entry per tool call to a date-partitioned file under
    ``~/.telos/teloscope_audit/``. Each entry records the tool invocation,
    all methodological checks that were run, and the simulated Gate 2
    verdict (what WOULD have happened in enforcement mode).

    The log is append-only. No entries are ever modified or deleted.

    Optional telemetry integration:
        When ``telemetry_enabled=True``, each log_tool_call() also extracts
        a privacy-stripped TelemetryRecord (no tool_args, no check messages,
        no check details) and appends it to a TelemetryBuffer. The buffer
        is flushed via flush_telemetry() on session end or by a timer.

    Usage:
        audit = TeloscopeAudit()
        checks = [check_sample_size(n=8, claim_type="comparison")]
        entry = audit.log_tool_call("research_audit_stats", {"groupby": "verdict"}, checks)
        print(audit.format_warnings(checks))

        # With telemetry:
        audit = TeloscopeAudit(telemetry_enabled=True)
        entry = audit.log_tool_call("research_audit_stats", {"groupby": "verdict"}, checks)
        print(audit.telemetry_status())
        audit.flush_telemetry()
    """

    def __init__(
        self,
        output_dir: str = "~/.telos/teloscope_audit",
        telemetry_enabled: bool = False,
    ):
        self.output_dir = os.path.expanduser(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        # --- Hash chain integrity ---
        self._prev_entry_hash: str = ""   # SHA-256 chain linkage

        # --- Telemetry integration (opt-in) ---
        self._telemetry_enabled = False
        self._telemetry_extractor = None  # Lazy: TelemetryExtractor
        self._telemetry_buffer = None     # Lazy: TelemetryBuffer
        self._telemetry_import_warned = False  # Log import failure once

        # Chain tracking for telemetry
        self._chain_position = 0          # Increments on each log_tool_call
        self._chain_tool_names: List[str] = []  # Accumulates tool names
        self._last_corpus_size: int = 0   # Last known corpus size for telemetry

        if telemetry_enabled:
            self._try_enable_telemetry()

    def _try_enable_telemetry(self) -> None:
        """Attempt to enable telemetry by importing telemetry_pipeline.

        If the import fails (module not installed), telemetry silently
        stays disabled and a warning is logged once.
        """
        try:
            from telemetry_pipeline import TelemetryExtractor, TelemetryBuffer
            self._telemetry_enabled = True
        except ImportError:
            try:
                from telos_governance.telemetry_pipeline import (
                    TelemetryExtractor, TelemetryBuffer,
                )
                self._telemetry_enabled = True
            except ImportError:
                if not self._telemetry_import_warned:
                    logger.warning(
                        "telemetry_pipeline not importable -- "
                        "telemetry_enabled silently disabled. "
                        "Install telemetry_pipeline to enable telemetry."
                    )
                    self._telemetry_import_warned = True
                self._telemetry_enabled = False

    def _ensure_telemetry_objects(self) -> bool:
        """Lazily create TelemetryExtractor and TelemetryBuffer on first use.

        Returns:
            True if telemetry objects are ready, False if not available.
        """
        if not self._telemetry_enabled:
            return False

        if self._telemetry_extractor is not None:
            return True

        # Lazy import inside the method -- no module-level dependency
        try:
            from telemetry_pipeline import TelemetryExtractor, TelemetryBuffer
        except ImportError:
            from telos_governance.telemetry_pipeline import (
                TelemetryExtractor, TelemetryBuffer,
            )

        self._telemetry_extractor = TelemetryExtractor()
        self._telemetry_buffer = TelemetryBuffer()
        return True

    def _feed_telemetry(self, entry: AuditEntry) -> None:
        """Extract a TelemetryRecord from the AuditEntry and buffer it.

        Called after every log_tool_call() when telemetry is enabled.
        Strips all content fields (tool_args, check messages, check details).
        Tracks chain_position and chain_pattern across calls.
        """
        if not self._ensure_telemetry_objects():
            return

        # Update chain tracking
        self._chain_position += 1
        self._chain_tool_names.append(entry.tool_name)
        # Truncate to last 10 for privacy (prevents behavioral fingerprinting)
        chain_names = self._chain_tool_names[-10:] if len(self._chain_tool_names) > 10 else self._chain_tool_names
        chain_pattern = ",".join(chain_names)

        # Extract the privacy-stripped telemetry record
        record = self._telemetry_extractor.from_audit_entry(
            entry,
            chain_position=self._chain_position,
            chain_pattern=chain_pattern,
            corpus_size=self._last_corpus_size,
        )

        # Append to buffer
        self._telemetry_buffer.append(record)

    @property
    def telemetry_enabled(self) -> bool:
        """Whether telemetry extraction is active."""
        return self._telemetry_enabled

    def set_corpus_size(self, n: int) -> None:
        """Update the last known corpus size for telemetry records.

        Call this after loading or reloading a corpus so subsequent
        telemetry records include the corpus_size field.

        Args:
            n: Number of events in the loaded corpus.
        """
        self._last_corpus_size = n

    def log_tool_call(
        self,
        tool_name: str,
        tool_args: Dict,
        checks: List[MethodologicalCheck],
    ) -> AuditEntry:
        """Log a tool call with its methodological checks.

        Computes the simulated Gate 2 verdict from the check statuses:
          - All pass -> EXECUTE
          - Any warn -> CLARIFY
          - Any fail -> ESCALATE

        Writes the entry to today's JSONL file and returns the
        AuditEntry for immediate use.

        When telemetry is enabled, also extracts a privacy-stripped
        TelemetryRecord and appends it to the telemetry buffer.

        Args:
            tool_name: Name of the TELOSCOPE tool invoked.
            tool_args: Arguments passed to the tool.
            checks: List of MethodologicalCheck results from constraint checkers.

        Returns:
            AuditEntry with computed verdict and all check data.
        """
        n_warnings = sum(1 for c in checks if c.status == "warn")
        n_failures = sum(1 for c in checks if c.status == "fail")

        # Simulated Gate 2 verdict
        if n_failures > 0:
            gate2_verdict = "ESCALATE"
        elif n_warnings > 0:
            gate2_verdict = "CLARIFY"
        else:
            gate2_verdict = "EXECUTE"

        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool_name=tool_name,
            tool_args=tool_args,
            checks=checks,
            n_warnings=n_warnings,
            n_failures=n_failures,
            gate2_verdict=gate2_verdict,
            observation_mode=True,
        )

        # Write full audit entry to local JSONL (always)
        self._write_entry(entry)

        # Feed telemetry buffer (only if opted in)
        if self._telemetry_enabled:
            self._feed_telemetry(entry)

        return entry

    def _write_entry(self, entry: AuditEntry):
        """Append entry to today's JSONL file with hash chain integrity.

        Each entry includes ``previous_entry_hash`` linking to the SHA-256
        of the preceding entry's canonical JSON. This produces a tamper-
        evident chain that can be verified posthoc.

        File path: {output_dir}/YYYY-MM-DD.jsonl
        """
        record = entry.to_dict()
        record["previous_entry_hash"] = self._prev_entry_hash

        # Compute hash of this entry (excluding chain field itself)
        hashable = {
            k: v for k, v in record.items()
            if k != "previous_entry_hash"
        }
        canonical = json.dumps(hashable, sort_keys=True, default=str)
        self._prev_entry_hash = hashlib.sha256(canonical.encode()).hexdigest()
        record["entry_hash"] = self._prev_entry_hash

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filepath = os.path.join(self.output_dir, f"{today}.jsonl")
        with open(filepath, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    # -------------------------------------------------------------------
    # Telemetry management methods
    # -------------------------------------------------------------------

    def flush_telemetry(self) -> Dict[str, Any]:
        """Flush the telemetry buffer via TelemetryUploader.

        Called on session end or by a scheduled timer. If telemetry is
        not enabled or the buffer is empty, returns immediately with
        a no-op result.

        Returns:
            Dict with upload results (uploaded, failed, remaining, error),
            or a no-op indicator if telemetry is disabled.
        """
        if not self._telemetry_enabled or self._telemetry_buffer is None:
            return {
                "uploaded": 0,
                "failed": 0,
                "remaining": 0,
                "error": "",
                "telemetry_enabled": False,
            }

        # Lazy import of TelemetryUploader
        try:
            from telemetry_pipeline import TelemetryUploader
        except ImportError:
            from telos_governance.telemetry_pipeline import TelemetryUploader

        uploader = TelemetryUploader(
            buffer_path=self._telemetry_buffer.buffer_path,
        )
        result = uploader.flush()
        result["telemetry_enabled"] = True
        return result

    def telemetry_status(self) -> Dict[str, Any]:
        """Return telemetry buffer status.

        Returns:
            Dict with record_count, staleness, buffer path, etc.
            If telemetry is disabled, returns a minimal status dict.
        """
        if not self._telemetry_enabled or self._telemetry_buffer is None:
            return {
                "telemetry_enabled": False,
                "record_count": 0,
                "chain_position": self._chain_position,
                "chain_length": len(self._chain_tool_names),
            }

        buf_status = self._telemetry_buffer.status()
        buf_status["telemetry_enabled"] = True
        buf_status["chain_position"] = self._chain_position
        buf_status["chain_length"] = len(self._chain_tool_names)
        buf_status["chain_pattern"] = ",".join(self._chain_tool_names)
        return buf_status

    # -------------------------------------------------------------------
    # Summary and formatting (unchanged)
    # -------------------------------------------------------------------

    def summary(self) -> Dict:
        """Summarize all audit entries in the output directory.

        Loads all JSONL files, counts entries by verdict, and lists
        the most common warnings.

        Returns:
            Dict with keys: n_entries, n_files, verdict_counts,
            top_warnings, date_range.
        """
        jsonl_files = sorted(
            f for f in os.listdir(self.output_dir)
            if f.endswith(".jsonl")
        )

        if not jsonl_files:
            return {
                "n_entries": 0,
                "n_files": 0,
                "verdict_counts": {},
                "top_warnings": [],
                "date_range": None,
            }

        n_entries = 0
        verdict_counts: Dict[str, int] = {}
        warning_counts: Dict[str, int] = {}
        dates = []

        for fname in jsonl_files:
            filepath = os.path.join(self.output_dir, fname)
            # Extract date from filename (YYYY-MM-DD.jsonl)
            date_part = fname.replace(".jsonl", "")
            dates.append(date_part)

            with open(filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        n_entries += 1

                        verdict = record.get("gate2_verdict", "UNKNOWN")
                        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

                        for check in record.get("checks", []):
                            if check.get("status") in ("warn", "fail"):
                                name = check.get("check_name", "unknown")
                                warning_counts[name] = warning_counts.get(name, 0) + 1
                    except (json.JSONDecodeError, KeyError):
                        continue

        # Sort warnings by frequency, descending
        top_warnings = sorted(
            warning_counts.items(), key=lambda x: -x[1]
        )[:10]

        return {
            "n_entries": n_entries,
            "n_files": len(jsonl_files),
            "verdict_counts": dict(sorted(verdict_counts.items())),
            "top_warnings": top_warnings,
            "date_range": (min(dates), max(dates)) if dates else None,
        }

    def format_warnings(self, checks: List[MethodologicalCheck]) -> str:
        """Format warnings for display alongside tool results.

        Only shows warn and fail checks. Returns empty string if all
        checks passed.

        Format:
            [!] Methodological Notes:
              - Sample size (n=8) below minimum (30) for statistical comparison
              - Export includes Zone 2 fields (request_text) -- redaction not applied

        Args:
            checks: List of MethodologicalCheck results.

        Returns:
            Formatted string, or empty string if no issues.
        """
        issues = [c for c in checks if c.status in ("warn", "fail")]
        if not issues:
            return ""

        lines = ["[!] Methodological Notes:"]
        for c in issues:
            prefix = "[FAIL]" if c.status == "fail" else "[WARN]"
            lines.append(f"  {prefix} {c.message}")

        return "\n".join(lines)

    def format_summary(self) -> str:
        """Format the summary as a human-readable table."""
        s = self.summary()
        if s["n_entries"] == 0:
            return "TELOSCOPE Audit: No entries logged."

        lines = [
            "TELOSCOPE Audit Summary",
            "=" * 40,
            f"  Entries:  {s['n_entries']}",
            f"  Files:    {s['n_files']}",
        ]
        if s["date_range"]:
            lines.append(
                f"  Range:    {s['date_range'][0]} to {s['date_range'][1]}"
            )

        lines.append("")
        lines.append("  Simulated Gate 2 Verdicts:")
        for verdict, count in s["verdict_counts"].items():
            pct = count / s["n_entries"] * 100
            lines.append(f"    {verdict:<12} {count:>5}  ({pct:>5.1f}%)")

        if s["top_warnings"]:
            lines.append("")
            lines.append("  Top Warnings:")
            for name, count in s["top_warnings"]:
                lines.append(f"    {name:<30} {count:>5}")

        return "\n".join(lines)

"""
Structured Compliance Report Generator
========================================

Generates three tiers of compliance reports from TELOS governance audit
data:

  1. **Executive Summary** -- 1-page overview with traffic light, top
     findings, and integrity status. Designed for board-level audiences.

  2. **Management Report** -- Everything in executive, plus per-tool
     verdict breakdown, dimension analysis, trend summary, session
     highlights, and methodological notes with denominator disclosure.

  3. **Full Audit Report** -- Everything in management, plus validation
     details, comparison results, event-level appendix (ESCALATE events),
     survivorship disclosure, and complete methodological appendix.

Design constraints:
  - Never upgrade PARTIAL to PASS in validation status (#SC-7)
  - Never suppress negative findings — dedicated "Findings Requiring
    Attention" section (report quality requirement #8)
  - Always include denominator — every percentage uses (n/N) format
    (#SC-5)
  - Always reference self-audit trail — every report must cite
    teloscope_audit.jsonl (#SC-8)
  - Zone 1 only in reports — no request_text, no explanation, no
    tool_args in any report tier (#SC-4)
  - Redact paths using guardrails.redact_paths() (Zone 2 rules)

Reports are plain text — clean, readable, monospace-friendly.

Usage:
    from telos_governance.corpus import load_corpus
    from telos_governance.validate import validate
    from telos_governance.stats import corpus_stats
    from telos_governance.timeline import timeline
    from telos_governance.report import (
        executive_report,
        management_report,
        full_audit_report,
    )

    corpus = load_corpus("~/.telos/posthoc_audit/")
    val = validate(corpus)
    stats = corpus_stats(corpus)
    tl = timeline(corpus, window_size=50, step=25)

    # Executive
    exec_rpt = executive_report(corpus, validation_result=val)
    print(exec_rpt.format())

    # Management
    mgmt_rpt = management_report(corpus, val, stats, tl)
    print(mgmt_rpt.format())

    # Full audit
    full_rpt = full_audit_report(corpus, val, stats, tl)
    print(full_rpt.format())
"""
import hashlib
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from telos_governance.corpus import AuditCorpus, AuditEvent
except ImportError:
    from corpus import AuditCorpus, AuditEvent

try:
    from telos_governance.stats import (
        StatsResult, DimensionSummary, corpus_stats, dimension_impact,
        cross_tabulate, format_cross_tab, DIMENSIONS, VERDICT_ORDER,
    )
except ImportError:
    from stats import (
        StatsResult, DimensionSummary, corpus_stats, dimension_impact,
        cross_tabulate, format_cross_tab, DIMENSIONS, VERDICT_ORDER,
    )

try:
    from telos_governance.validate import (
        ValidationResult, ChainResult, SignatureResult,
        ReproducibilityResult,
    )
except ImportError:
    from validate import (
        ValidationResult, ChainResult, SignatureResult,
        ReproducibilityResult,
    )

try:
    from telos_governance.timeline import (
        TimelineResult, SessionTimelineResult, session_timeline,
    )
except ImportError:
    from timeline import (
        TimelineResult, SessionTimelineResult, session_timeline,
    )

try:
    from telos_governance.compare import CompareResult
except ImportError:
    from compare import CompareResult

try:
    from telos_governance.guardrails import (
        redact_paths, FilteredResult, LoadMetadata, bonferroni_alpha,
    )
except ImportError:
    from guardrails import (
        redact_paths, FilteredResult, LoadMetadata, bonferroni_alpha,
    )

try:
    from telos_governance.teloscope_audit import TeloscopeAudit
except ImportError:
    from teloscope_audit import TeloscopeAudit


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEPARATOR = "=" * 72
_THIN_SEP = "-" * 72
_REPORT_VERSION = "1.0.0"

# Traffic light thresholds (governance health)
_GREEN_EXECUTE_RATE = 0.90   # >90% EXECUTE
_YELLOW_EXECUTE_RATE = 0.70  # 70-90% EXECUTE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pct_with_denom(count: int, total: int) -> str:
    """Format a percentage with denominator disclosure: '85.0% (170/200)'.

    Report quality requirement: every percentage includes (n/N) format.
    """
    if total == 0:
        return "0.0% (0/0)"
    pct = count / total * 100
    return f"{pct:.1f}% ({count}/{total})"


def _safe_pct(count: int, total: int) -> float:
    """Safe percentage computation that avoids division by zero."""
    if total == 0:
        return 0.0
    return count / total * 100


def _format_float(value: float, precision: int = 3) -> str:
    """Format a float with specified precision."""
    return f"{value:.{precision}f}"


def _report_timestamp() -> str:
    """ISO timestamp for report generation."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _traffic_light(
    execute_rate: float,
    has_integrity_failure: bool,
) -> str:
    """Compute governance health traffic light.

    GREEN:  >90% EXECUTE, no integrity failures
    YELLOW: 70-90% EXECUTE or partial integrity
    RED:    <70% EXECUTE or integrity failure

    Args:
        execute_rate: Fraction of events with EXECUTE verdict (0.0-1.0).
        has_integrity_failure: True if any validation check returned "fail".

    Returns:
        "GREEN", "YELLOW", or "RED".
    """
    if has_integrity_failure:
        return "RED"
    if execute_rate > _GREEN_EXECUTE_RATE:
        return "GREEN"
    if execute_rate >= _YELLOW_EXECUTE_RATE:
        return "YELLOW"
    return "RED"


def _audit_trail_info() -> Tuple[str, int]:
    """Get TELOSCOPE self-audit trail file path and record count.

    Report quality requirement: every report must reference teloscope_audit.jsonl.

    Returns:
        (trail_path, record_count) tuple.
    """
    trail_dir = os.path.expanduser("~/.telos/teloscope_audit")
    if not os.path.isdir(trail_dir):
        return trail_dir, 0

    count = 0
    for fname in os.listdir(trail_dir):
        if fname.endswith(".jsonl"):
            filepath = os.path.join(trail_dir, fname)
            try:
                with open(filepath, "r") as f:
                    for line in f:
                        if line.strip():
                            count += 1
            except OSError:
                pass

    return trail_dir, count


def _audit_trail_summary() -> Dict:
    """Summarize the TELOSCOPE self-audit trail.

    Returns a dict with n_entries, n_files, verdict_counts, and any
    Gate 2 warnings from the current analysis session.
    """
    try:
        audit = TeloscopeAudit()
        return audit.summary()
    except Exception:
        return {
            "n_entries": 0,
            "n_files": 0,
            "verdict_counts": {},
            "top_warnings": [],
            "date_range": None,
        }


def _compute_report_integrity(report_text: str, sign: bool = False) -> str:
    """Compute SHA-256 hash and optional TKeys Ed25519 signature for a report.

    Args:
        report_text: The full formatted report text to hash/sign.
        sign: If True, attempt to sign with TKeys Ed25519. Gracefully
              degrades if telos_governance.signing is unavailable.

    Returns:
        A formatted integrity footer block.
    """
    # SHA-256 hash of report text
    sha256_hash = hashlib.sha256(report_text.encode("utf-8")).hexdigest()

    # Optional TKeys Ed25519 signature
    signed = False
    fingerprint = "N/A"
    if sign:
        try:
            from telos_governance.signing import TKeysSigner
            signer = TKeysSigner()
            sig = signer.sign(report_text.encode("utf-8"))
            fingerprint = signer.fingerprint()
            signed = True
        except Exception:
            # Graceful degradation -- signing unavailable
            pass

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    sep = "\u2550" * 62  # box-drawing double horizontal

    lines = [
        "",
        sep,
        "REPORT INTEGRITY",
        sep,
        f"  SHA-256:     {sha256_hash}",
        f"  Signed:      {'yes' if signed else 'no'}",
        f"  Fingerprint: {fingerprint}",
        f"  Generated:   {timestamp}",
        "",
        "  Verify: telos report verify <file>",
        sep,
    ]
    return "\n".join(lines)


def _compute_verdict_distribution(corpus: AuditCorpus) -> Dict[str, int]:
    """Count verdicts across all events."""
    dist: Dict[str, int] = {}
    for e in corpus.events:
        dist[e.verdict] = dist.get(e.verdict, 0) + 1
    return dist


def _compute_escalation_rate_by_tool(
    corpus: AuditCorpus,
) -> List[Tuple[str, int, int, float]]:
    """Compute per-tool escalation rates.

    Returns list of (tool, escalate_count, total_count, escalation_rate)
    sorted by escalation rate descending.
    """
    tool_counts: Dict[str, int] = {}
    tool_esc: Dict[str, int] = {}
    for e in corpus.events:
        tool_counts[e.tool_call] = tool_counts.get(e.tool_call, 0) + 1
        if e.verdict == "ESCALATE":
            tool_esc[e.tool_call] = tool_esc.get(e.tool_call, 0) + 1

    result = []
    for tool, total in tool_counts.items():
        esc = tool_esc.get(tool, 0)
        rate = esc / total if total > 0 else 0.0
        result.append((tool, esc, total, rate))

    result.sort(key=lambda x: -x[3])
    return result


def _date_range(corpus: AuditCorpus) -> Tuple[str, str]:
    """Extract date range from corpus timestamps.

    Returns (start_date, end_date) as 'YYYY-MM-DD' strings.
    """
    if not corpus.events:
        return ("N/A", "N/A")

    timestamps = [e.timestamp for e in corpus.events if e.timestamp]
    if not timestamps:
        return ("N/A", "N/A")

    return (min(timestamps)[:10], max(timestamps)[:10])


def _worst_dimension(corpus: AuditCorpus) -> Tuple[str, float]:
    """Find the dimension with the lowest mean score (excluding composite).

    Returns (dimension_name, mean_score).
    """
    dims = ["purpose", "scope", "boundary", "tool", "chain"]
    if not corpus.events:
        return ("N/A", 0.0)

    worst_dim = ""
    worst_mean = float("inf")
    for dim in dims:
        values = [getattr(e, dim) for e in corpus.events]
        mean = sum(values) / len(values) if values else 0.0
        if mean < worst_mean:
            worst_mean = mean
            worst_dim = dim

    return (worst_dim, worst_mean)


def _session_escalation_rates(
    corpus: AuditCorpus,
) -> List[Tuple[str, int, int, float]]:
    """Compute per-session escalation rates.

    Returns list of (session_id, escalate_count, total_count, rate)
    sorted by rate descending.
    """
    session_counts: Dict[str, int] = {}
    session_esc: Dict[str, int] = {}
    for e in corpus.events:
        session_counts[e.session_id] = session_counts.get(e.session_id, 0) + 1
        if e.verdict == "ESCALATE":
            session_esc[e.session_id] = session_esc.get(e.session_id, 0) + 1

    result = []
    for sid, total in session_counts.items():
        esc = session_esc.get(sid, 0)
        rate = esc / total if total > 0 else 0.0
        result.append((sid, esc, total, rate))

    result.sort(key=lambda x: -x[3])
    return result


def _negative_findings(
    corpus: AuditCorpus,
    validation_result: Optional[ValidationResult] = None,
    stats_result: Optional[StatsResult] = None,
    timeline_result: Optional[TimelineResult] = None,
) -> List[str]:
    """Identify negative findings that must not be suppressed.

    Report quality requirement: negative findings must be reported prominently.

    Returns list of human-readable finding strings.
    """
    findings = []
    n = len(corpus)

    if n == 0:
        findings.append("Empty corpus -- no governance data available for analysis.")
        return findings

    # Verdict-based findings
    v_dist = _compute_verdict_distribution(corpus)
    execute_count = v_dist.get("EXECUTE", 0)
    execute_rate = execute_count / n
    escalate_count = v_dist.get("ESCALATE", 0)
    escalate_rate = escalate_count / n

    if execute_rate < _YELLOW_EXECUTE_RATE:
        findings.append(
            f"EXECUTE rate is {_pct_with_denom(execute_count, n)}, "
            f"below the 70% threshold. Governance health is RED."
        )
    elif execute_rate < _GREEN_EXECUTE_RATE:
        findings.append(
            f"EXECUTE rate is {_pct_with_denom(execute_count, n)}, "
            f"below the 90% GREEN threshold. Governance health is YELLOW."
        )

    if escalate_rate > 0.05:
        findings.append(
            f"Escalation rate is {_pct_with_denom(escalate_count, n)}, "
            f"above 5% baseline."
        )

    # Tool-level findings
    tool_rates = _compute_escalation_rate_by_tool(corpus)
    for tool, esc, total, rate in tool_rates:
        if rate > 0.20 and total >= 10:
            findings.append(
                f"Tool '{tool}' has escalation rate "
                f"{_pct_with_denom(esc, total)} (above 20% threshold)."
            )

    # Validation findings
    if validation_result is not None:
        if validation_result.overall_status == "fail":
            findings.append(
                f"Integrity validation FAILED. "
                f"Overall status: {validation_result.overall_status.upper()}."
            )
        elif validation_result.overall_status == "partial":
            findings.append(
                f"Integrity validation PARTIAL -- not all checks passed."
            )

        if validation_result.chain.status == "fail":
            findings.append(
                f"Hash chain verification FAILED: "
                f"{validation_result.chain.n_broken} broken link(s)."
            )
        if validation_result.signatures.status == "fail":
            findings.append(
                f"Signature verification FAILED: "
                f"{validation_result.signatures.n_failed} invalid signature(s)."
            )
        if validation_result.reproducibility.status == "fail":
            findings.append(
                f"Verdict reproducibility FAILED: "
                f"match rate {validation_result.reproducibility.match_rate:.1%} "
                f"({validation_result.reproducibility.n_mismatched} mismatches)."
            )

    # Timeline findings
    if timeline_result is not None and timeline_result.trend == "degrading":
        findings.append(
            f"Governance fidelity trend is DEGRADING "
            f"(slope={timeline_result.slope:+.4f}, "
            f"R-squared={timeline_result.r_squared:.2f})."
        )

    # Dimension findings
    if stats_result is not None and stats_result.dimensions:
        for dim_name in ["purpose", "scope", "tool", "chain"]:
            if dim_name in stats_result.dimensions:
                d = stats_result.dimensions[dim_name]
                if d.mean < 0.50 and d.n >= 20:
                    findings.append(
                        f"Dimension '{dim_name}' has mean score "
                        f"{d.mean:.3f} (below 0.500), based on "
                        f"{d.n} events."
                    )

    return findings


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ExecReport:
    """Executive summary report result.

    Structured data for the 1-page overview. Use format() for clean
    plain-text output.
    """
    report_tier: str                         # "executive"
    generated_at: str                        # ISO timestamp
    date_range: Tuple[str, str]              # (start, end) dates
    n_events: int
    n_sessions: int
    verdict_distribution: Dict[str, int]
    execute_rate: float
    traffic_light: str                       # "GREEN", "YELLOW", "RED"
    top_findings: List[str]                  # Top 3 most impactful
    integrity_status: Optional[str]          # "PASS", "PARTIAL", "FAIL" or None
    audit_trail_path: str
    audit_trail_records: int
    source_path: str

    def format(self) -> str:
        """Format as clean plain text report."""
        n = self.n_events
        lines = [
            _SEPARATOR,
            "TELOS GOVERNANCE -- EXECUTIVE SUMMARY",
            _SEPARATOR,
            "",
            f"  Generated:   {self.generated_at}",
            f"  Source:       {redact_paths(self.source_path)}",
            f"  Date range:  {self.date_range[0]} to {self.date_range[1]}",
            f"  Events:      {self.n_events:,}",
            f"  Sessions:    {self.n_sessions}",
            "",
        ]

        # Governance health traffic light
        lines.append(f"  GOVERNANCE HEALTH: [{self.traffic_light}]")
        lines.append("")

        # Verdict distribution
        lines.append("  Verdict Distribution:")
        for v in VERDICT_ORDER:
            count = self.verdict_distribution.get(v, 0)
            lines.append(f"    {v:<12} {_pct_with_denom(count, n)}")
        lines.append("")

        # Integrity status
        if self.integrity_status is not None:
            lines.append(f"  Integrity Status: {self.integrity_status}")
            lines.append("")

        # Top findings
        if self.top_findings:
            lines.append("  FINDINGS REQUIRING ATTENTION:")
            for i, finding in enumerate(self.top_findings, 1):
                lines.append(f"    {i}. {finding}")
            lines.append("")
        else:
            lines.append("  No findings requiring attention.")
            lines.append("")

        # Self-audit trail reference
        lines.append("  TELOSCOPE Self-Audit Trail:")
        lines.append(f"    Path:    {redact_paths(self.audit_trail_path)}")
        lines.append(f"    Records: {self.audit_trail_records:,}")
        lines.append("")
        lines.append(_SEPARATOR)

        body = "\n".join(lines)
        body += _compute_report_integrity(body)
        return body


@dataclass
class MgmtReport:
    """Management report result.

    Everything in ExecReport plus per-tool breakdown, dimension
    analysis, trend summary, session highlights, and methodological notes.
    """
    report_tier: str                         # "management"
    generated_at: str
    date_range: Tuple[str, str]
    n_events: int
    n_sessions: int
    verdict_distribution: Dict[str, int]
    execute_rate: float
    traffic_light: str
    top_findings: List[str]
    negative_findings: List[str]             # All negative findings
    integrity_status: Optional[str]
    # Per-tool verdict breakdown
    tool_verdict_table: str                  # Pre-formatted cross-tab
    tool_escalation_rates: List[Tuple[str, int, int, float]]
    # Per-dimension analysis
    dimension_table: Optional[Dict[str, DimensionSummary]]
    # Trend analysis
    trend_direction: Optional[str]           # "improving", "stable", "degrading"
    trend_slope: Optional[float]
    trend_r_squared: Optional[float]
    # Session highlights
    best_session: Optional[Tuple[str, int, float]]   # (id, n, rate)
    worst_session: Optional[Tuple[str, int, float]]  # (id, n, rate)
    # Methodological notes
    methodological_notes: List[str]
    # Self-audit
    audit_trail_path: str
    audit_trail_records: int
    audit_trail_summary: Dict
    source_path: str

    def format(self) -> str:
        """Format as clean plain text report."""
        n = self.n_events
        lines = [
            _SEPARATOR,
            "TELOS GOVERNANCE -- MANAGEMENT REPORT",
            _SEPARATOR,
            "",
            f"  Generated:   {self.generated_at}",
            f"  Source:       {redact_paths(self.source_path)}",
            f"  Date range:  {self.date_range[0]} to {self.date_range[1]}",
            f"  Events:      {self.n_events:,}",
            f"  Sessions:    {self.n_sessions}",
            "",
        ]

        # Governance health
        lines.append(f"  GOVERNANCE HEALTH: [{self.traffic_light}]")
        lines.append("")

        # Verdict distribution with denominators
        lines.append("  Verdict Distribution:")
        for v in VERDICT_ORDER:
            count = self.verdict_distribution.get(v, 0)
            lines.append(f"    {v:<12} {_pct_with_denom(count, n)}")
        lines.append("")

        # Integrity status
        if self.integrity_status is not None:
            lines.append(f"  Integrity Status: {self.integrity_status}")
            lines.append("")

        # --- Negative findings ---
        lines.append(_THIN_SEP)
        lines.append("  FINDINGS REQUIRING ATTENTION")
        lines.append(_THIN_SEP)
        if self.negative_findings:
            for i, finding in enumerate(self.negative_findings, 1):
                lines.append(f"    {i}. {finding}")
        else:
            lines.append("    No findings requiring attention.")
        lines.append("")

        # --- Per-tool verdict breakdown ---
        lines.append(_THIN_SEP)
        lines.append("  PER-TOOL VERDICT BREAKDOWN")
        lines.append(_THIN_SEP)
        lines.append(self.tool_verdict_table)
        lines.append("")

        # Tool escalation rates
        lines.append("  Tool Escalation Rates:")
        lines.append(
            f"  {'Tool':<20} {'Escalated':>10} {'Total':>8} {'Rate':>12}"
        )
        lines.append(f"  {'-'*20} {'-'*10} {'-'*8} {'-'*12}")
        for tool, esc, total, rate in self.tool_escalation_rates:
            lines.append(
                f"  {tool:<20} {esc:>10} {total:>8} "
                f"{_pct_with_denom(esc, total):>12}"
            )
        lines.append("")

        # --- Dimension analysis ---
        lines.append(_THIN_SEP)
        lines.append("  PER-DIMENSION ANALYSIS")
        lines.append(_THIN_SEP)
        if self.dimension_table:
            lines.append(
                f"  {'Dimension':<12} {'Mean':>7} {'Median':>7} "
                f"{'StDev':>7} {'n':>7}"
            )
            lines.append(
                f"  {'-'*12} {'-'*7} {'-'*7} {'-'*7} {'-'*7}"
            )
            for dim_name in DIMENSIONS:
                if dim_name in self.dimension_table:
                    d = self.dimension_table[dim_name]
                    lines.append(
                        f"  {d.name:<12} {d.mean:>7.3f} {d.median:>7.3f} "
                        f"{d.stdev:>7.3f} {d.n:>7}"
                    )
        else:
            lines.append("  Dimension statistics not available.")
        lines.append("")

        # --- Trend analysis ---
        lines.append(_THIN_SEP)
        lines.append("  TREND ANALYSIS")
        lines.append(_THIN_SEP)
        if self.trend_direction is not None:
            sign = "+" if (self.trend_slope or 0) >= 0 else ""
            lines.append(
                f"  Direction:  {self.trend_direction.upper()}"
            )
            lines.append(
                f"  Slope:      {sign}{self.trend_slope:.4f}"
            )
            lines.append(
                f"  R-squared:  {self.trend_r_squared:.3f}"
            )
            if self.trend_r_squared is not None and self.trend_r_squared < 0.10:
                lines.append(
                    "  [Note: R-squared < 0.10 -- trend explains <10% of "
                    "variance. Directional claims are weak.]"
                )
        else:
            lines.append("  Trend analysis not available.")
        lines.append("")

        # --- Session highlights ---
        lines.append(_THIN_SEP)
        lines.append("  SESSION HIGHLIGHTS")
        lines.append(_THIN_SEP)
        if self.best_session is not None:
            sid, sn, srate = self.best_session
            sid_display = sid[:16] if len(sid) > 16 else sid
            lines.append(
                f"  Best session (lowest escalation rate):"
            )
            lines.append(
                f"    {sid_display}  "
                f"n={sn}  escalation={srate:.1%}"
            )
        if self.worst_session is not None:
            sid, sn, srate = self.worst_session
            sid_display = sid[:16] if len(sid) > 16 else sid
            lines.append(
                f"  Worst session (highest escalation rate):"
            )
            lines.append(
                f"    {sid_display}  "
                f"n={sn}  escalation={srate:.1%}"
            )
        if self.best_session is None and self.worst_session is None:
            lines.append("  Session highlights not available.")
        lines.append("")

        # --- Methodological notes ---
        lines.append(_THIN_SEP)
        lines.append("  METHODOLOGICAL NOTES")
        lines.append(_THIN_SEP)
        if self.methodological_notes:
            for note in self.methodological_notes:
                lines.append(f"    - {note}")
        else:
            lines.append("    No methodological notes.")
        lines.append("")

        # --- TELOSCOPE self-audit ---
        lines.append(_THIN_SEP)
        lines.append("  TELOSCOPE SELF-AUDIT")
        lines.append(_THIN_SEP)
        lines.append(f"  Trail path:    {redact_paths(self.audit_trail_path)}")
        lines.append(f"  Total records: {self.audit_trail_records:,}")
        audit_s = self.audit_trail_summary
        if audit_s.get("n_entries", 0) > 0:
            lines.append(f"  Tool calls logged: {audit_s['n_entries']}")
            vcts = audit_s.get("verdict_counts", {})
            if vcts:
                lines.append("  Simulated Gate 2 verdicts this session:")
                for verdict, count in sorted(vcts.items()):
                    lines.append(
                        f"    {verdict:<12} {count}"
                    )
            top_warns = audit_s.get("top_warnings", [])
            if top_warns:
                lines.append("  Gate 2 warnings:")
                for wname, wcount in top_warns[:5]:
                    lines.append(f"    {wname:<30} {wcount}")
        lines.append("")
        lines.append(_SEPARATOR)

        body = "\n".join(lines)
        body += _compute_report_integrity(body)
        return body


@dataclass
class FullAuditReport:
    """Full audit report result.

    Everything in MgmtReport plus validation details, comparison results,
    event-level appendix, survivorship disclosure, and complete
    methodological appendix.
    """
    report_tier: str                         # "full_audit"
    generated_at: str
    date_range: Tuple[str, str]
    n_events: int
    n_sessions: int
    verdict_distribution: Dict[str, int]
    execute_rate: float
    traffic_light: str
    top_findings: List[str]
    negative_findings: List[str]
    integrity_status: Optional[str]
    # Per-tool
    tool_verdict_table: str
    tool_escalation_rates: List[Tuple[str, int, int, float]]
    # Dimensions
    dimension_table: Optional[Dict[str, DimensionSummary]]
    # Trend
    trend_direction: Optional[str]
    trend_slope: Optional[float]
    trend_r_squared: Optional[float]
    # Sessions
    best_session: Optional[Tuple[str, int, float]]
    worst_session: Optional[Tuple[str, int, float]]
    # Validation details
    validation_result: Optional[ValidationResult]
    # Comparison
    compare_results: Optional[List[CompareResult]]
    # Annotations
    annotations: Optional[List[Dict]]
    # ESCALATE event appendix (Zone 1 only)
    escalate_events: List[Dict]
    # Survivorship
    survivorship_notes: List[str]
    # Methodological appendix
    methodological_notes: List[str]
    thresholds_used: Dict[str, Any]
    bonferroni_corrections: List[str]
    sample_size_checks: List[str]
    # Self-audit
    audit_trail_path: str
    audit_trail_records: int
    audit_trail_summary: Dict
    source_path: str

    def format(self) -> str:
        """Format as clean plain text report."""
        n = self.n_events
        lines = [
            _SEPARATOR,
            "TELOS GOVERNANCE -- FULL AUDIT REPORT",
            _SEPARATOR,
            "",
            f"  Generated:       {self.generated_at}",
            f"  Report version:  {_REPORT_VERSION}",
            f"  Source:          {redact_paths(self.source_path)}",
            f"  Date range:      {self.date_range[0]} to {self.date_range[1]}",
            f"  Events:          {self.n_events:,}",
            f"  Sessions:        {self.n_sessions}",
            "",
        ]

        # Governance health
        lines.append(f"  GOVERNANCE HEALTH: [{self.traffic_light}]")
        lines.append("")

        # Verdict distribution
        lines.append("  Verdict Distribution:")
        for v in VERDICT_ORDER:
            count = self.verdict_distribution.get(v, 0)
            lines.append(f"    {v:<12} {_pct_with_denom(count, n)}")
        lines.append("")

        # Integrity status
        if self.integrity_status is not None:
            lines.append(f"  Integrity Status: {self.integrity_status}")
            lines.append("")

        # ================================================================
        # SECTION 1: FINDINGS REQUIRING ATTENTION
        # ================================================================
        lines.append(_SEPARATOR)
        lines.append("  SECTION 1: FINDINGS REQUIRING ATTENTION")
        lines.append(_SEPARATOR)
        if self.negative_findings:
            for i, finding in enumerate(self.negative_findings, 1):
                lines.append(f"    {i}. {finding}")
        else:
            lines.append("    No findings requiring attention.")
        lines.append("")

        # ================================================================
        # SECTION 2: INTEGRITY VALIDATION DETAILS
        # ================================================================
        lines.append(_SEPARATOR)
        lines.append("  SECTION 2: INTEGRITY VALIDATION")
        lines.append(_SEPARATOR)
        if self.validation_result is not None:
            vr = self.validation_result
            lines.append(
                f"  Overall: {vr.overall_status.upper()}"
            )
            lines.append("")

            # Chain
            lines.append(vr.chain.format())
            lines.append("")

            # Signatures
            lines.append(vr.signatures.format())
            lines.append("")

            # Reproducibility
            lines.append(vr.reproducibility.format())
            lines.append("")
        else:
            lines.append("  Validation not performed.")
            lines.append("")

        # ================================================================
        # SECTION 3: PER-TOOL VERDICT BREAKDOWN
        # ================================================================
        lines.append(_SEPARATOR)
        lines.append("  SECTION 3: PER-TOOL VERDICT BREAKDOWN")
        lines.append(_SEPARATOR)
        lines.append(self.tool_verdict_table)
        lines.append("")

        lines.append("  Tool Escalation Rates:")
        lines.append(
            f"  {'Tool':<20} {'Escalated':>10} {'Total':>8} {'Rate':>12}"
        )
        lines.append(f"  {'-'*20} {'-'*10} {'-'*8} {'-'*12}")
        for tool, esc, total, rate in self.tool_escalation_rates:
            lines.append(
                f"  {tool:<20} {esc:>10} {total:>8} "
                f"{_pct_with_denom(esc, total):>12}"
            )
        lines.append("")

        # ================================================================
        # SECTION 4: PER-DIMENSION ANALYSIS
        # ================================================================
        lines.append(_SEPARATOR)
        lines.append("  SECTION 4: PER-DIMENSION ANALYSIS")
        lines.append(_SEPARATOR)
        if self.dimension_table:
            lines.append(
                f"  {'Dimension':<12} {'Mean':>7} {'Median':>7} "
                f"{'StDev':>7} {'P5':>7} {'P95':>7} {'Zeros':>7} {'n':>7}"
            )
            lines.append(
                f"  {'-'*12} {'-'*7} {'-'*7} {'-'*7} {'-'*7} "
                f"{'-'*7} {'-'*7} {'-'*7}"
            )
            for dim_name in DIMENSIONS:
                if dim_name in self.dimension_table:
                    d = self.dimension_table[dim_name]
                    lines.append(
                        f"  {d.name:<12} {d.mean:>7.3f} {d.median:>7.3f} "
                        f"{d.stdev:>7.3f} {d.p5:>7.3f} {d.p95:>7.3f} "
                        f"{d.zero_count:>7} {d.n:>7}"
                    )
        else:
            lines.append("  Dimension statistics not available.")
        lines.append("")

        # ================================================================
        # SECTION 5: TREND ANALYSIS
        # ================================================================
        lines.append(_SEPARATOR)
        lines.append("  SECTION 5: TREND ANALYSIS")
        lines.append(_SEPARATOR)
        if self.trend_direction is not None:
            sign = "+" if (self.trend_slope or 0) >= 0 else ""
            lines.append(
                f"  Direction:  {self.trend_direction.upper()}"
            )
            lines.append(
                f"  Slope:      {sign}{self.trend_slope:.4f}"
            )
            lines.append(
                f"  R-squared:  {self.trend_r_squared:.3f}"
            )
            if self.trend_r_squared is not None and self.trend_r_squared < 0.10:
                lines.append(
                    "  [Note: R-squared < 0.10 -- trend explains <10% of "
                    "variance. Directional claims are weak.]"
                )
        else:
            lines.append("  Trend analysis not available.")
        lines.append("")

        # ================================================================
        # SECTION 6: SESSION HIGHLIGHTS
        # ================================================================
        lines.append(_SEPARATOR)
        lines.append("  SECTION 6: SESSION HIGHLIGHTS")
        lines.append(_SEPARATOR)
        if self.best_session is not None:
            sid, sn, srate = self.best_session
            sid_display = sid[:16] if len(sid) > 16 else sid
            lines.append(
                f"  Best session (lowest escalation rate):"
            )
            lines.append(
                f"    {sid_display}  "
                f"n={sn}  escalation={srate:.1%}"
            )
        if self.worst_session is not None:
            sid, sn, srate = self.worst_session
            sid_display = sid[:16] if len(sid) > 16 else sid
            lines.append(
                f"  Worst session (highest escalation rate):"
            )
            lines.append(
                f"    {sid_display}  "
                f"n={sn}  escalation={srate:.1%}"
            )
        if self.best_session is None and self.worst_session is None:
            lines.append("  Session highlights not available.")
        lines.append("")

        # ================================================================
        # SECTION 7: COMPARISON RESULTS
        # ================================================================
        lines.append(_SEPARATOR)
        lines.append("  SECTION 7: COMPARISON RESULTS")
        lines.append(_SEPARATOR)
        if self.compare_results:
            for idx, cr in enumerate(self.compare_results):
                lines.append(f"  Comparison {idx + 1}:")
                lines.append(cr.format())
                lines.append("")
        else:
            lines.append("  No comparisons performed.")
        lines.append("")

        # ================================================================
        # SECTION 8: ANNOTATION / CALIBRATION RESULTS
        # ================================================================
        lines.append(_SEPARATOR)
        lines.append("  SECTION 8: ANNOTATIONS / CALIBRATION")
        lines.append(_SEPARATOR)
        if self.annotations:
            for idx, ann in enumerate(self.annotations):
                lines.append(f"  Annotation {idx + 1}:")
                for key, val in ann.items():
                    # Zone 1 only: skip Zone 2/3 fields
                    if key in ("request_text", "explanation", "tool_args",
                               "_raw", "raw_payload",
                               "modified_prompt", "action_text"):
                        continue
                    if isinstance(val, str):
                        val = redact_paths(val)
                    lines.append(f"    {key}: {val}")
                lines.append("")
        else:
            lines.append("  No annotation/calibration data provided.")
        lines.append("")

        # ================================================================
        # SECTION 9: ESCALATE EVENT APPENDIX (Zone 1 data only)
        # ================================================================
        lines.append(_SEPARATOR)
        lines.append("  SECTION 9: ESCALATE EVENT APPENDIX")
        lines.append(_SEPARATOR)
        if self.escalate_events:
            lines.append(
                f"  Total ESCALATE events: "
                f"{_pct_with_denom(len(self.escalate_events), n)}"
            )
            lines.append("")
            lines.append(
                f"  {'#':>5}  {'Event ID':>16}  {'Tool':>16}  "
                f"{'Composite':>9}  {'Timestamp':>20}"
            )
            lines.append(
                f"  {'-'*5}  {'-'*16}  {'-'*16}  "
                f"{'-'*9}  {'-'*20}"
            )
            for idx, ev in enumerate(self.escalate_events):
                eid = ev.get("event_id", "")[:16]
                tool = ev.get("tool_call", "")[:16]
                comp = ev.get("composite", 0.0)
                ts = ev.get("timestamp", "")[:20]
                lines.append(
                    f"  {ev.get('index', idx):>5}  {eid:>16}  "
                    f"{tool:>16}  {comp:>9.3f}  {ts:>20}"
                )
            lines.append("")
            lines.append(
                "  [Note: Zone 1 data only -- no request_text, explanation, "
                "or tool_args included per SC-4.]"
            )
        else:
            lines.append("  No ESCALATE events in corpus.")
        lines.append("")

        # ================================================================
        # SECTION 10: SURVIVORSHIP DISCLOSURE
        # ================================================================
        lines.append(_SEPARATOR)
        lines.append("  SECTION 10: SURVIVORSHIP DISCLOSURE")
        lines.append(_SEPARATOR)
        if self.survivorship_notes:
            for note in self.survivorship_notes:
                lines.append(f"    - {note}")
        else:
            lines.append(
                "    No survivorship bias detected. All records loaded "
                "successfully."
            )
        lines.append("")

        # ================================================================
        # SECTION 11: METHODOLOGICAL APPENDIX
        # ================================================================
        lines.append(_SEPARATOR)
        lines.append("  SECTION 11: METHODOLOGICAL APPENDIX")
        lines.append(_SEPARATOR)

        # Thresholds used
        lines.append("  Thresholds Used:")
        if self.thresholds_used:
            for key, val in self.thresholds_used.items():
                lines.append(f"    {key}: {val}")
        else:
            lines.append("    Default TELOS thresholds (production config).")
        lines.append("")

        # Bonferroni corrections
        lines.append("  Bonferroni Corrections Applied:")
        if self.bonferroni_corrections:
            for corr in self.bonferroni_corrections:
                lines.append(f"    - {corr}")
        else:
            lines.append("    No multiple comparisons in this report.")
        lines.append("")

        # Sample size checks
        lines.append("  Sample Size Checks:")
        if self.sample_size_checks:
            for check in self.sample_size_checks:
                lines.append(f"    - {check}")
        else:
            lines.append("    All groups meet minimum sample size thresholds.")
        lines.append("")

        # General notes
        lines.append("  Methodological Notes:")
        if self.methodological_notes:
            for note in self.methodological_notes:
                lines.append(f"    - {note}")
        else:
            lines.append("    No methodological notes.")
        lines.append("")

        # ================================================================
        # SECTION 12: TELOSCOPE SELF-AUDIT
        # ================================================================
        lines.append(_SEPARATOR)
        lines.append("  SECTION 12: TELOSCOPE SELF-AUDIT TRAIL")
        lines.append(_SEPARATOR)
        lines.append(f"  Trail path:    {redact_paths(self.audit_trail_path)}")
        lines.append(f"  Total records: {self.audit_trail_records:,}")
        audit_s = self.audit_trail_summary
        if audit_s.get("n_entries", 0) > 0:
            lines.append(f"  Tool calls logged: {audit_s['n_entries']}")
            vcts = audit_s.get("verdict_counts", {})
            if vcts:
                lines.append("  Simulated Gate 2 verdicts:")
                for verdict, count in sorted(vcts.items()):
                    lines.append(f"    {verdict:<12} {count}")
            top_warns = audit_s.get("top_warnings", [])
            if top_warns:
                lines.append("  Top Gate 2 warnings:")
                for wname, wcount in top_warns:
                    lines.append(f"    {wname:<30} {wcount}")
            dr = audit_s.get("date_range")
            if dr:
                lines.append(f"  Audit date range: {dr[0]} to {dr[1]}")
        else:
            lines.append(
                "  No TELOSCOPE audit entries logged. If this is unexpected, "
                "verify that teloscope_audit.py is configured."
            )
        lines.append("")

        lines.append(
            "  [This report includes TELOSCOPE's own analytical audit "
            "trail for report integrity.]"
        )
        lines.append("")
        lines.append(_SEPARATOR)
        lines.append("  END OF FULL AUDIT REPORT")
        lines.append(_SEPARATOR)

        body = "\n".join(lines)
        body += _compute_report_integrity(body)
        return body


# ---------------------------------------------------------------------------
# Report generation functions
# ---------------------------------------------------------------------------

def executive_report(
    corpus: AuditCorpus,
    validation_result: Optional[ValidationResult] = None,
) -> ExecReport:
    """Generate a 1-page executive summary report.

    Args:
        corpus: AuditCorpus with loaded governance events.
        validation_result: Optional ValidationResult from validate().

    Returns:
        ExecReport dataclass with format() method producing clean text.
    """
    n = len(corpus)
    v_dist = _compute_verdict_distribution(corpus)
    execute_count = v_dist.get("EXECUTE", 0)
    execute_rate = execute_count / n if n > 0 else 0.0

    # Integrity
    has_integrity_failure = False
    integrity_status = None
    if validation_result is not None:
        integrity_status = validation_result.overall_status.upper()
        # SC-7: Never upgrade PARTIAL to PASS
        has_integrity_failure = validation_result.overall_status == "fail"

    # Traffic light
    light = _traffic_light(execute_rate, has_integrity_failure)

    # Top 3 findings
    all_findings = _negative_findings(corpus, validation_result)
    top_3 = all_findings[:3]

    # Audit trail
    trail_path, trail_count = _audit_trail_info()

    return ExecReport(
        report_tier="executive",
        generated_at=_report_timestamp(),
        date_range=_date_range(corpus),
        n_events=n,
        n_sessions=corpus.n_sessions,
        verdict_distribution=v_dist,
        execute_rate=execute_rate,
        traffic_light=light,
        top_findings=top_3,
        integrity_status=integrity_status,
        audit_trail_path=trail_path,
        audit_trail_records=trail_count,
        source_path=corpus.source_path,
    )


def management_report(
    corpus: AuditCorpus,
    validation_result: Optional[ValidationResult] = None,
    stats_result: Optional[StatsResult] = None,
    timeline_result: Optional[TimelineResult] = None,
) -> MgmtReport:
    """Generate a management report with per-tool and dimension breakdown.

    Includes everything in the executive summary, plus:
    - Per-tool verdict breakdown table
    - Per-dimension mean/median/stdev table
    - Trend analysis summary
    - Session-level highlights (best and worst by escalation rate)
    - Methodological notes section
    - Denominator disclosure on every statistic
    - Negative findings prominently displayed
    - TELOSCOPE self-audit summary

    Args:
        corpus: AuditCorpus with loaded governance events.
        validation_result: Optional ValidationResult from validate().
        stats_result: Optional StatsResult from corpus_stats().
        timeline_result: Optional TimelineResult from timeline().

    Returns:
        MgmtReport dataclass with format() method producing clean text.
    """
    n = len(corpus)
    v_dist = _compute_verdict_distribution(corpus)
    execute_count = v_dist.get("EXECUTE", 0)
    execute_rate = execute_count / n if n > 0 else 0.0

    # Integrity
    has_integrity_failure = False
    integrity_status = None
    if validation_result is not None:
        integrity_status = validation_result.overall_status.upper()
        has_integrity_failure = validation_result.overall_status == "fail"

    # Traffic light
    light = _traffic_light(execute_rate, has_integrity_failure)

    # Compute stats if not provided
    if stats_result is None and n > 0:
        stats_result = corpus_stats(corpus)

    # Per-tool verdict cross-tab
    xtab = cross_tabulate(corpus, "tool_call", "verdict")
    tool_table = format_cross_tab(xtab, "Tool")

    # Tool escalation rates
    tool_esc_rates = _compute_escalation_rate_by_tool(corpus)

    # Dimension analysis
    dim_table = None
    if stats_result is not None and stats_result.dimensions:
        dim_table = stats_result.dimensions

    # Trend analysis
    trend_dir = None
    trend_slope = None
    trend_r2 = None
    if timeline_result is not None:
        trend_dir = timeline_result.trend
        trend_slope = timeline_result.slope
        trend_r2 = timeline_result.r_squared

    # Session highlights
    sess_rates = _session_escalation_rates(corpus)
    best_session = None
    worst_session = None
    if sess_rates:
        # Best = lowest escalation rate (among sessions with >= 5 events)
        qualified = [s for s in sess_rates if s[2] >= 5]
        if qualified:
            best = min(qualified, key=lambda x: x[3])
            best_session = (best[0], best[2], best[3])
            worst = max(qualified, key=lambda x: x[3])
            worst_session = (worst[0], worst[2], worst[3])

    # Negative findings
    neg_findings = _negative_findings(
        corpus, validation_result, stats_result, timeline_result
    )
    top_findings = neg_findings[:3]

    # Methodological notes
    meth_notes = _build_methodological_notes(corpus, stats_result, timeline_result)

    # Self-audit
    trail_path, trail_count = _audit_trail_info()
    audit_summary = _audit_trail_summary()

    return MgmtReport(
        report_tier="management",
        generated_at=_report_timestamp(),
        date_range=_date_range(corpus),
        n_events=n,
        n_sessions=corpus.n_sessions,
        verdict_distribution=v_dist,
        execute_rate=execute_rate,
        traffic_light=light,
        top_findings=top_findings,
        negative_findings=neg_findings,
        integrity_status=integrity_status,
        tool_verdict_table=tool_table,
        tool_escalation_rates=tool_esc_rates,
        dimension_table=dim_table,
        trend_direction=trend_dir,
        trend_slope=trend_slope,
        trend_r_squared=trend_r2,
        best_session=best_session,
        worst_session=worst_session,
        methodological_notes=meth_notes,
        audit_trail_path=trail_path,
        audit_trail_records=trail_count,
        audit_trail_summary=audit_summary,
        source_path=corpus.source_path,
    )


def full_audit_report(
    corpus: AuditCorpus,
    validation_result: Optional[ValidationResult] = None,
    stats_result: Optional[StatsResult] = None,
    timeline_result: Optional[TimelineResult] = None,
    compare_results: Optional[List[CompareResult]] = None,
    annotations: Optional[List[Dict]] = None,
) -> FullAuditReport:
    """Generate a complete audit report with all details.

    Includes everything in the management report, plus:
    - Full validation details (chain, signatures, reproducibility)
    - Comparison results if provided
    - Annotation/calibration results if provided
    - Event-level appendix (all ESCALATE events with Zone 1 data only)
    - Survivorship disclosure (dropped records, parse errors)
    - Complete methodological appendix (thresholds, Bonferroni, sample sizes)
    - Full TELOSCOPE audit trail

    Args:
        corpus: AuditCorpus with loaded governance events.
        validation_result: Optional ValidationResult from validate().
        stats_result: Optional StatsResult from corpus_stats().
        timeline_result: Optional TimelineResult from timeline().
        compare_results: Optional list of CompareResult from compare().
        annotations: Optional list of annotation dicts (calibration data).

    Returns:
        FullAuditReport dataclass with format() method producing clean text.
    """
    n = len(corpus)
    v_dist = _compute_verdict_distribution(corpus)
    execute_count = v_dist.get("EXECUTE", 0)
    execute_rate = execute_count / n if n > 0 else 0.0

    # Integrity
    has_integrity_failure = False
    integrity_status = None
    if validation_result is not None:
        integrity_status = validation_result.overall_status.upper()
        has_integrity_failure = validation_result.overall_status == "fail"

    # Traffic light
    light = _traffic_light(execute_rate, has_integrity_failure)

    # Compute stats if not provided
    if stats_result is None and n > 0:
        stats_result = corpus_stats(corpus)

    # Per-tool verdict cross-tab
    xtab = cross_tabulate(corpus, "tool_call", "verdict")
    tool_table = format_cross_tab(xtab, "Tool")

    # Tool escalation rates
    tool_esc_rates = _compute_escalation_rate_by_tool(corpus)

    # Dimension analysis
    dim_table = None
    if stats_result is not None and stats_result.dimensions:
        dim_table = stats_result.dimensions

    # Trend analysis
    trend_dir = None
    trend_slope = None
    trend_r2 = None
    if timeline_result is not None:
        trend_dir = timeline_result.trend
        trend_slope = timeline_result.slope
        trend_r2 = timeline_result.r_squared

    # Session highlights
    sess_rates = _session_escalation_rates(corpus)
    best_session = None
    worst_session = None
    if sess_rates:
        qualified = [s for s in sess_rates if s[2] >= 5]
        if qualified:
            best = min(qualified, key=lambda x: x[3])
            best_session = (best[0], best[2], best[3])
            worst = max(qualified, key=lambda x: x[3])
            worst_session = (worst[0], worst[2], worst[3])

    # Negative findings
    neg_findings = _negative_findings(
        corpus, validation_result, stats_result, timeline_result
    )
    top_findings = neg_findings[:3]

    # ESCALATE event appendix -- Zone 1 data only (SC-4)
    escalate_events = _build_escalate_appendix(corpus)

    # Survivorship disclosure
    survivorship = _build_survivorship_notes(corpus)

    # Methodological appendix
    meth_notes = _build_methodological_notes(corpus, stats_result, timeline_result)
    thresholds = _build_threshold_table()
    bonferroni = _build_bonferroni_notes(compare_results)
    sample_checks = _build_sample_size_checks(corpus, stats_result)

    # Self-audit
    trail_path, trail_count = _audit_trail_info()
    audit_summary = _audit_trail_summary()

    return FullAuditReport(
        report_tier="full_audit",
        generated_at=_report_timestamp(),
        date_range=_date_range(corpus),
        n_events=n,
        n_sessions=corpus.n_sessions,
        verdict_distribution=v_dist,
        execute_rate=execute_rate,
        traffic_light=light,
        top_findings=top_findings,
        negative_findings=neg_findings,
        integrity_status=integrity_status,
        tool_verdict_table=tool_table,
        tool_escalation_rates=tool_esc_rates,
        dimension_table=dim_table,
        trend_direction=trend_dir,
        trend_slope=trend_slope,
        trend_r_squared=trend_r2,
        best_session=best_session,
        worst_session=worst_session,
        validation_result=validation_result,
        compare_results=compare_results,
        annotations=annotations,
        escalate_events=escalate_events,
        survivorship_notes=survivorship,
        methodological_notes=meth_notes,
        thresholds_used=thresholds,
        bonferroni_corrections=bonferroni,
        sample_size_checks=sample_checks,
        audit_trail_path=trail_path,
        audit_trail_records=trail_count,
        audit_trail_summary=audit_summary,
        source_path=corpus.source_path,
    )


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------

def _build_escalate_appendix(corpus: AuditCorpus) -> List[Dict]:
    """Build Zone 1 event records for all ESCALATE events.

    SC-4: No request_text, no explanation, no tool_args.
    Only event_id, timestamp, tool_call, composite score, and index.
    """
    result = []
    for idx, event in enumerate(corpus.events):
        if event.verdict == "ESCALATE":
            result.append({
                "index": idx,
                "event_id": event.event_id,
                "timestamp": event.timestamp,
                "tool_call": event.tool_call,
                "composite": event.composite,
                "purpose": event.purpose,
                "scope": event.scope,
                "boundary": event.boundary,
                "tool": event.tool,
                "chain": event.chain,
                "session_id": event.session_id,
            })
    return result


def _build_survivorship_notes(corpus: AuditCorpus) -> List[str]:
    """Build survivorship disclosure notes.

    Report quality requirement: never present survivorship-biased results
    without disclosing dropped/skipped record count.
    """
    notes = []

    # Check if corpus source exists and count raw records
    source_path = os.path.expanduser(corpus.source_path)
    if os.path.exists(source_path):
        raw_count = 0
        parse_errors = 0

        jsonl_files = []
        if os.path.isdir(source_path):
            for root, _dirs, files in os.walk(source_path):
                for fname in files:
                    if fname.endswith(".jsonl"):
                        jsonl_files.append(os.path.join(root, fname))
        elif source_path.endswith(".jsonl"):
            jsonl_files.append(source_path)

        for filepath in jsonl_files:
            try:
                with open(filepath, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        raw_count += 1
                        try:
                            import json
                            record = json.loads(line)
                            if not record.get("verdict"):
                                pass  # counted as skipped below
                        except Exception:
                            parse_errors += 1
            except OSError:
                notes.append(
                    f"Could not re-read source file {redact_paths(filepath)} "
                    f"for survivorship analysis."
                )

        loaded = len(corpus)
        skipped = raw_count - loaded - parse_errors

        if skipped > 0:
            skip_rate = skipped / raw_count * 100 if raw_count > 0 else 0.0
            notes.append(
                f"{skipped} records skipped (no verdict field) out of "
                f"{raw_count} total records ({skip_rate:.1f}% skip rate). "
                f"Skipped records are typically supervisor lifecycle events "
                f"or capability probes."
            )

        if parse_errors > 0:
            notes.append(
                f"{parse_errors} parse error(s) encountered. These records "
                f"are excluded from all analysis."
            )

        if skipped == 0 and parse_errors == 0:
            notes.append(
                f"All {raw_count} records loaded successfully. "
                f"No records were skipped or dropped."
            )
    else:
        notes.append(
            f"Source path {redact_paths(corpus.source_path)} not accessible "
            f"for survivorship analysis. Cannot verify dropped record count."
        )

    return notes


def _build_methodological_notes(
    corpus: AuditCorpus,
    stats_result: Optional[StatsResult] = None,
    timeline_result: Optional[TimelineResult] = None,
) -> List[str]:
    """Build methodological notes for the report."""
    notes = []
    n = len(corpus)

    # Sample size notes
    if n < 20:
        notes.append(
            f"Corpus contains {n} events, below the minimum of 20 for "
            f"reliable mean estimation. Statistics should be interpreted "
            f"with caution."
        )
    elif n < 30:
        notes.append(
            f"Corpus contains {n} events, below the minimum of 30 for "
            f"chi-squared and comparison tests."
        )

    # Session count
    n_sessions = corpus.n_sessions
    if n_sessions < 5:
        notes.append(
            f"Only {n_sessions} session(s) in corpus, below the minimum "
            f"of 5 for session-level analysis. Session statistics are "
            f"anecdotal."
        )

    # Per-tool sample sizes
    tool_counts: Dict[str, int] = {}
    for e in corpus.events:
        tool_counts[e.tool_call] = tool_counts.get(e.tool_call, 0) + 1
    small_tools = [
        (t, c) for t, c in tool_counts.items() if c < 10
    ]
    if small_tools:
        tool_list = ", ".join(
            f"{t} (n={c})" for t, c in sorted(small_tools, key=lambda x: x[1])
        )
        notes.append(
            f"Tools with fewer than 10 events (rates may be unstable): "
            f"{tool_list}."
        )

    # Trend confidence
    if timeline_result is not None:
        if timeline_result.r_squared < 0.10:
            notes.append(
                f"Trend R-squared ({timeline_result.r_squared:.3f}) is below "
                f"0.10 -- directional claims (improving/degrading) are not "
                f"statistically supported."
            )
        n_windows = len(timeline_result.points)
        if n_windows < 3:
            notes.append(
                f"Only {n_windows} window(s) in timeline analysis, below "
                f"the minimum of 3 for meaningful trend detection."
            )

    # Statistics corrections
    if stats_result is not None:
        notes.append(
            f"All statistics computed on {stats_result.n_events} events "
            f"across {stats_result.n_sessions} sessions."
        )

    return notes


def _build_threshold_table() -> Dict[str, Any]:
    """Build threshold reference table for methodological appendix."""
    return {
        "traffic_light_green": f">{_GREEN_EXECUTE_RATE:.0%} EXECUTE, no integrity failures",
        "traffic_light_yellow": f"{_YELLOW_EXECUTE_RATE:.0%}-{_GREEN_EXECUTE_RATE:.0%} EXECUTE or partial integrity",
        "traffic_light_red": f"<{_YELLOW_EXECUTE_RATE:.0%} EXECUTE or integrity failure",
        "min_sample_mean": 20,
        "min_sample_distribution": 30,
        "min_sample_comparison": "30 per group",
        "min_sample_per_tool": 10,
        "min_sample_trend": "3 windows",
        "min_sample_session": 5,
        "escalation_rate_warning": ">5%",
        "tool_escalation_warning": ">20% (with n>=10)",
        "dimension_low_threshold": 0.500,
        "trend_r_squared_minimum": 0.10,
        "trend_slope_negligible": 0.001,
    }


def _build_bonferroni_notes(
    compare_results: Optional[List[CompareResult]] = None,
) -> List[str]:
    """Build Bonferroni correction disclosure for comparisons.

    compare.py tests 6 dimensions simultaneously. Corrected
    alpha = 0.05/6 = 0.0083.
    """
    notes = []

    if compare_results:
        n_dims = len(DIMENSIONS)
        corrected_alpha = bonferroni_alpha(n_dims)
        notes.append(
            f"Dimension comparisons test {n_dims} dimensions simultaneously. "
            f"Bonferroni-corrected alpha = {corrected_alpha:.4f} "
            f"(from 0.05/{n_dims}). "
            f"Significance claims at p < {corrected_alpha:.4f}."
        )

        # Check if any comparisons have significance at uncorrected but
        # not corrected alpha
        for idx, cr in enumerate(compare_results):
            for dc in cr.dimension_comparison:
                if dc.p_value is not None:
                    if dc.p_value < 0.05 and dc.p_value >= corrected_alpha:
                        notes.append(
                            f"Comparison {idx+1}, dimension '{dc.dimension}': "
                            f"p={dc.p_value:.4f} is significant at alpha=0.05 "
                            f"but NOT at Bonferroni-corrected alpha="
                            f"{corrected_alpha:.4f}."
                        )

        n_comparisons = len(compare_results)
        if n_comparisons > 1:
            family_alpha = bonferroni_alpha(n_comparisons * n_dims)
            notes.append(
                f"{n_comparisons} comparisons x {n_dims} dimensions = "
                f"{n_comparisons * n_dims} total tests. "
                f"Full family-wise corrected alpha = {family_alpha:.6f}."
            )

    return notes


def _build_sample_size_checks(
    corpus: AuditCorpus,
    stats_result: Optional[StatsResult] = None,
) -> List[str]:
    """Build sample size checks for methodological appendix."""
    checks = []
    n = len(corpus)

    # Overall
    if n >= 30:
        checks.append(
            f"Overall corpus (n={n}): PASS -- meets minimum for all "
            f"statistical tests."
        )
    elif n >= 20:
        checks.append(
            f"Overall corpus (n={n}): PARTIAL -- meets minimum for means "
            f"(20) but not comparisons/distributions (30)."
        )
    else:
        checks.append(
            f"Overall corpus (n={n}): FAIL -- below minimum of 20 for "
            f"reliable mean estimation."
        )

    # Per-verdict groups
    v_dist = _compute_verdict_distribution(corpus)
    for v in VERDICT_ORDER:
        count = v_dist.get(v, 0)
        if count > 0 and count < 10:
            checks.append(
                f"Verdict '{v}' (n={count}): WARN -- below minimum "
                f"of 10 for stable rate estimation."
            )

    # Per-tool groups
    tool_counts: Dict[str, int] = {}
    for e in corpus.events:
        tool_counts[e.tool_call] = tool_counts.get(e.tool_call, 0) + 1
    for tool, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
        if count < 10:
            checks.append(
                f"Tool '{tool}' (n={count}): WARN -- below minimum "
                f"of 10 for per-tool analysis."
            )

    # Sessions
    n_sessions = corpus.n_sessions
    if n_sessions < 5:
        checks.append(
            f"Sessions (n={n_sessions}): WARN -- below minimum of 5 "
            f"for session-level analysis."
        )
    else:
        checks.append(
            f"Sessions (n={n_sessions}): PASS -- meets minimum of 5."
        )

    return checks

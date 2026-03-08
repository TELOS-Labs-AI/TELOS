"""
Statistical Analysis Tool
===========================

Distributional statistics and dimensional decomposition with groupby.
The workhorse for "which dimension is causing the problem?"

Usage:
    from telos_governance.corpus import load_corpus
    from telos_governance.stats import corpus_stats, dimension_stats

    corpus = load_corpus("~/.telos/posthoc_audit/")

    # Full stats
    s = corpus_stats(corpus)
    print(s.format())

    # Grouped by verdict
    s = corpus_stats(corpus, groupby="verdict")
    print(s.format())

    # Single dimension deep dive
    d = dimension_stats(corpus, "purpose")
    print(d.format())
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    from telos_governance.corpus import AuditCorpus, AuditEvent
except ImportError:
    from corpus import AuditCorpus, AuditEvent


DIMENSIONS = ["composite", "purpose", "scope", "boundary", "tool", "chain"]
VERDICT_ORDER = ["EXECUTE", "CLARIFY", "INERT", "ESCALATE"]

# Production weights
_WEIGHTS = {
    "purpose": 0.35,
    "scope": 0.20,
    "tool": 0.20,
    "chain": 0.15,
    "boundary": -0.10,
}


def _percentile(sorted_vals: List[float], p: float) -> float:
    """Compute percentile from a sorted list."""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def _stdev(values: List[float], mean: float) -> float:
    """Compute sample standard deviation."""
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


@dataclass
class DimensionSummary:
    """Statistics for a single fidelity dimension."""
    name: str
    n: int
    mean: float
    median: float
    stdev: float
    p5: float
    p25: float
    p75: float
    p95: float
    min_val: float
    max_val: float
    zero_count: int
    zero_pct: float
    weight: float  # composite weight for this dimension
    mean_contribution: float  # weight * mean

    def format(self) -> str:
        return (
            f"  {self.name:<12} "
            f"mean={self.mean:.3f}  "
            f"med={self.median:.3f}  "
            f"std={self.stdev:.3f}  "
            f"[{self.p5:.3f}, {self.p95:.3f}]  "
            f"zeros={self.zero_count} ({self.zero_pct:.0%})  "
            f"contrib={self.mean_contribution:+.3f}"
        )


@dataclass
class GroupStats:
    """Statistics for a group (verdict, tool, or session)."""
    group_key: str
    group_value: str
    n: int
    pct: float  # percentage of total corpus
    dimensions: Dict[str, DimensionSummary]

    def format(self) -> str:
        lines = [f"  {self.group_value} (n={self.n}, {self.pct:.1%})"]
        for dim_name in DIMENSIONS:
            if dim_name in self.dimensions:
                d = self.dimensions[dim_name]
                lines.append(
                    f"    {d.name:<12} "
                    f"mean={d.mean:.3f}  med={d.median:.3f}  "
                    f"zeros={d.zero_count}  contrib={d.mean_contribution:+.3f}"
                )
        return "\n".join(lines)


@dataclass
class StatsResult:
    """Full statistical analysis of a corpus or subset."""
    n_events: int
    n_sessions: int
    dimensions: Dict[str, DimensionSummary]
    groups: Optional[Dict[str, GroupStats]] = None
    groupby: Optional[str] = None
    verdict_distribution: Optional[Dict[str, int]] = None
    tool_distribution: Optional[Dict[str, int]] = None

    def format(self) -> str:
        if self.n_events == 0:
            return "Empty corpus (0 events)"

        lines = [
            "Corpus Statistics",
            "=" * 50,
            f"  Events:   {self.n_events}",
            f"  Sessions: {self.n_sessions}",
            "",
            "  Dimension Analysis:",
            f"  {'Dimension':<12} {'Mean':>6}  {'Med':>5}  {'Std':>5}  "
            f"{'[P5':>5}  {'P95]':>5}  {'Zeros':>6}  {'Contrib':>7}",
            f"  {'-'*12} {'-'*6}  {'-'*5}  {'-'*5}  "
            f"{'-'*5}  {'-'*5}  {'-'*6}  {'-'*7}",
        ]

        for dim_name in DIMENSIONS:
            if dim_name in self.dimensions:
                d = self.dimensions[dim_name]
                lines.append(
                    f"  {d.name:<12} {d.mean:>6.3f}  {d.median:>5.3f}  "
                    f"{d.stdev:>5.3f}  {d.p5:>5.3f}  {d.p95:>5.3f}  "
                    f"{d.zero_count:>5} ({d.zero_pct:>3.0%})"
                    f"  {d.mean_contribution:>+7.3f}"
                )

        # Sum of mean contributions
        total_contrib = sum(
            d.mean_contribution for d in self.dimensions.values()
            if d.name != "composite"
        )
        lines.append(f"  {'':12} {'':6}  {'':5}  {'':5}  {'':5}  {'':5}  "
                     f"{'':6}   {'= ' + f'{total_contrib:.3f}':>6}")

        if self.verdict_distribution:
            lines.append("")
            lines.append("  Verdict Distribution:")
            for v in VERDICT_ORDER:
                if v in self.verdict_distribution:
                    count = self.verdict_distribution[v]
                    pct = count / self.n_events
                    lines.append(f"    {v:<12} {count:>5} ({pct:>5.1%})")

        if self.groups:
            lines.append("")
            lines.append(f"  Grouped by: {self.groupby}")
            lines.append(f"  {'-'*46}")

            # Sort groups by VERDICT_ORDER if grouping by verdict
            if self.groupby == "verdict":
                ordered_keys = [v for v in VERDICT_ORDER if v in self.groups]
            else:
                ordered_keys = sorted(self.groups.keys(),
                                     key=lambda k: -self.groups[k].n)

            for key in ordered_keys:
                g = self.groups[key]
                lines.append(g.format())
                lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Serialize for JSON output."""
        result = {
            "n_events": self.n_events,
            "n_sessions": self.n_sessions,
            "dimensions": {},
        }
        for name, d in self.dimensions.items():
            result["dimensions"][name] = {
                "mean": d.mean,
                "median": d.median,
                "stdev": d.stdev,
                "p5": d.p5,
                "p25": d.p25,
                "p75": d.p75,
                "p95": d.p95,
                "min": d.min_val,
                "max": d.max_val,
                "zero_count": d.zero_count,
                "zero_pct": d.zero_pct,
                "weight": d.weight,
                "mean_contribution": d.mean_contribution,
            }
        if self.verdict_distribution:
            result["verdict_distribution"] = self.verdict_distribution
        if self.tool_distribution:
            result["tool_distribution"] = self.tool_distribution
        if self.groups:
            result["groups"] = {}
            for key, g in self.groups.items():
                result["groups"][key] = {
                    "n": g.n,
                    "pct": g.pct,
                    "dimensions": {
                        name: {
                            "mean": d.mean,
                            "median": d.median,
                            "zero_count": d.zero_count,
                            "mean_contribution": d.mean_contribution,
                        }
                        for name, d in g.dimensions.items()
                    },
                }
        return result


def _compute_dimension_summary(
    events: List[AuditEvent], dim_name: str
) -> DimensionSummary:
    """Compute statistics for a single dimension."""
    if dim_name == "composite":
        values = [e.composite for e in events]
        weight = 1.0
    else:
        values = [getattr(e, dim_name) for e in events]
        weight = _WEIGHTS.get(dim_name, 0.0)

    n = len(values)
    if n == 0:
        return DimensionSummary(
            name=dim_name, n=0, mean=0.0, median=0.0, stdev=0.0,
            p5=0.0, p25=0.0, p75=0.0, p95=0.0, min_val=0.0, max_val=0.0,
            zero_count=0, zero_pct=0.0, weight=weight, mean_contribution=0.0,
        )

    sorted_vals = sorted(values)
    mean = sum(values) / n
    zero_count = sum(1 for v in values if v == 0.0)

    return DimensionSummary(
        name=dim_name,
        n=n,
        mean=mean,
        median=_percentile(sorted_vals, 0.50),
        stdev=_stdev(values, mean),
        p5=_percentile(sorted_vals, 0.05),
        p25=_percentile(sorted_vals, 0.25),
        p75=_percentile(sorted_vals, 0.75),
        p95=_percentile(sorted_vals, 0.95),
        min_val=sorted_vals[0],
        max_val=sorted_vals[-1],
        zero_count=zero_count,
        zero_pct=zero_count / n,
        weight=weight,
        mean_contribution=weight * mean,
    )


def corpus_stats(
    corpus: AuditCorpus,
    groupby: Optional[str] = None,
    dimensions: Optional[List[str]] = None,
) -> StatsResult:
    """Compute distributional statistics for a corpus.

    Args:
        corpus: AuditCorpus to analyze
        groupby: Optional grouping field — "verdict", "tool_call", "session_id"
        dimensions: Which dimensions to analyze (default: all 6)

    Returns:
        StatsResult with per-dimension statistics and optional group breakdown.
    """
    if dimensions is None:
        dimensions = DIMENSIONS

    events = corpus.events
    n = len(events)

    if n == 0:
        return StatsResult(
            n_events=0, n_sessions=0,
            dimensions={}, verdict_distribution={},
        )

    # Compute overall dimension stats
    dim_stats = {
        dim: _compute_dimension_summary(events, dim)
        for dim in dimensions
    }

    # Verdict and tool distributions
    v_dist: Dict[str, int] = {}
    t_dist: Dict[str, int] = {}
    for e in events:
        v_dist[e.verdict] = v_dist.get(e.verdict, 0) + 1
        t_dist[e.tool_call] = t_dist.get(e.tool_call, 0) + 1

    # Group analysis
    groups = None
    if groupby:
        group_buckets: Dict[str, List[AuditEvent]] = {}
        for e in events:
            key = getattr(e, groupby, "unknown")
            if key not in group_buckets:
                group_buckets[key] = []
            group_buckets[key].append(e)

        groups = {}
        for group_val, group_events in group_buckets.items():
            group_dims = {
                dim: _compute_dimension_summary(group_events, dim)
                for dim in dimensions
            }
            groups[group_val] = GroupStats(
                group_key=groupby,
                group_value=str(group_val),
                n=len(group_events),
                pct=len(group_events) / n,
                dimensions=group_dims,
            )

    return StatsResult(
        n_events=n,
        n_sessions=corpus.n_sessions,
        dimensions=dim_stats,
        groups=groups,
        groupby=groupby,
        verdict_distribution=dict(sorted(v_dist.items())),
        tool_distribution=dict(sorted(t_dist.items(), key=lambda x: -x[1])),
    )


def dimension_impact(corpus: AuditCorpus) -> List[Tuple[str, float, str]]:
    """Rank dimensions by their impact on non-EXECUTE verdicts.

    For each non-EXECUTE event, identifies which dimension contributes
    least to the composite. Aggregates across all non-EXECUTE events
    to find the most common "culprit" dimension.

    Returns:
        List of (dimension_name, culprit_frequency, interpretation)
        sorted by frequency descending.
    """
    culprit_counts: Dict[str, int] = {}
    non_execute = [e for e in corpus.events if e.verdict != "EXECUTE"]

    if not non_execute:
        return [("none", 1.0, "All events are EXECUTE")]

    for e in non_execute:
        contributions = {
            "purpose": _WEIGHTS["purpose"] * e.purpose,
            "scope": _WEIGHTS["scope"] * e.scope,
            "tool": _WEIGHTS["tool"] * e.tool,
            "chain": _WEIGHTS["chain"] * e.chain,
        }
        # Find the weakest positive contributor
        weakest = min(contributions, key=contributions.get)
        culprit_counts[weakest] = culprit_counts.get(weakest, 0) + 1

    # Also count boundary as a culprit when it's high
    boundary_culprits = sum(1 for e in non_execute if e.boundary >= 0.70)
    if boundary_culprits > 0:
        culprit_counts["boundary"] = boundary_culprits

    total = len(non_execute)
    result = []
    for dim, count in sorted(culprit_counts.items(), key=lambda x: -x[1]):
        freq = count / total
        if dim == "chain":
            interp = f"Chain continuity is zero or low in {freq:.0%} of non-EXECUTE events"
        elif dim == "purpose":
            interp = f"Purpose alignment is the weakest dimension in {freq:.0%} of non-EXECUTE events"
        elif dim == "boundary":
            interp = f"Boundary violation triggered in {freq:.0%} of non-EXECUTE events"
        elif dim == "scope":
            interp = f"Scope alignment is weakest in {freq:.0%} of non-EXECUTE events"
        elif dim == "tool":
            interp = f"Tool fidelity is weakest in {freq:.0%} of non-EXECUTE events"
        else:
            interp = f"{dim} is the primary issue in {freq:.0%} of non-EXECUTE events"
        result.append((dim, freq, interp))

    return result


def histogram(
    corpus: AuditCorpus,
    dimension: str = "composite",
    bins: int = 20,
) -> List[Tuple[float, float, int]]:
    """Compute histogram for a dimension.

    Returns list of (bin_start, bin_end, count).
    """
    values = [getattr(e, dimension) for e in corpus.events]
    if not values:
        return []

    min_v = min(values)
    max_v = max(values)
    if min_v == max_v:
        return [(min_v, max_v, len(values))]

    bin_width = (max_v - min_v) / bins
    result = []
    for i in range(bins):
        start = min_v + i * bin_width
        end = start + bin_width
        if i == bins - 1:
            count = sum(1 for v in values if start <= v <= end)
        else:
            count = sum(1 for v in values if start <= v < end)
        result.append((round(start, 4), round(end, 4), count))

    return result


def cross_tabulate(
    corpus: AuditCorpus,
    row_field: str = "tool_call",
    col_field: str = "verdict",
) -> Dict[str, Dict[str, int]]:
    """Cross-tabulate two fields.

    Returns dict of {row_value: {col_value: count}}.
    Default: tool × verdict cross-tab.

    Example:
        xtab = cross_tabulate(corpus, "tool_call", "verdict")
        # xtab["Bash"]["ESCALATE"] = 45
    """
    result: Dict[str, Dict[str, int]] = {}
    for e in corpus.events:
        row = getattr(e, row_field, "unknown")
        col = getattr(e, col_field, "unknown")
        if row not in result:
            result[row] = {}
        result[row][col] = result[row].get(col, 0) + 1

    return result


def format_cross_tab(
    xtab: Dict[str, Dict[str, int]],
    row_label: str = "Tool",
) -> str:
    """Format a cross-tabulation as a readable table."""
    # Collect all column values
    all_cols = set()
    for row_data in xtab.values():
        all_cols.update(row_data.keys())

    # Use VERDICT_ORDER if columns look like verdicts
    if all_cols <= set(VERDICT_ORDER):
        cols = [v for v in VERDICT_ORDER if v in all_cols]
    else:
        cols = sorted(all_cols)

    # Header
    header = f"  {row_label:<16}"
    for c in cols:
        header += f" {c[:6]:>6}"
    header += f" {'Total':>6}"

    lines = [header]
    lines.append(f"  {'-'*16}" + " ------" * (len(cols) + 1))

    # Sort rows by total descending
    rows_sorted = sorted(xtab.items(), key=lambda x: -sum(x[1].values()))

    for row_name, row_data in rows_sorted:
        row = f"  {row_name:<16}"
        total = 0
        for c in cols:
            count = row_data.get(c, 0)
            total += count
            if count > 0:
                row += f" {count:>6}"
            else:
                row += f" {'·':>6}"
        row += f" {total:>6}"
        lines.append(row)

    return "\n".join(lines)

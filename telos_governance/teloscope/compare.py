"""
Structured Comparison Tool
============================

Side-by-side comparison of two governance audit corpus subsets.
Quantifies differences in verdict distributions and fidelity
dimensions with effect sizes and optional significance tests.

Designed for before/after analysis (config change, deploy, incident),
cross-session comparison, and tool-level behavioral differences.

Statistical methods:
  - Chi-squared test for verdict distribution independence (Pearson, 1900)
  - Mann-Whitney U test for fidelity distribution shifts (Mann & Whitney, 1947)
  - Cohen's d for standardized effect size (Cohen, 1988)

Usage:
    from telos_governance.corpus import load_corpus
    from telos_governance.compare import compare, compare_sessions, compare_tools

    corpus = load_corpus("~/.telos/posthoc_audit/")

    # Compare two filtered subsets
    group_a = corpus.filter(session="session-abc")
    group_b = corpus.filter(session="session-xyz")
    result = compare(group_a, group_b, label_a="Before", label_b="After")
    print(result.format())

    # Convenience: compare two sessions
    result = compare_sessions(corpus, "session-abc", "session-xyz")
    print(result.format())

    # Convenience: compare two tools
    result = compare_tools(corpus, "Bash", "Edit")
    print(result.format())

    # Convenience: before/after split at index
    result = compare_periods(corpus, before_index=200)
    print(result.format())

    # Machine-readable
    d = result.to_dict()
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    from telos_governance.corpus import AuditCorpus, AuditEvent
except ImportError:
    from corpus import AuditCorpus, AuditEvent

try:
    from scipy.stats import chi2_contingency, mannwhitneyu
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

try:
    from telos_governance.guardrails import bonferroni_alpha
except ImportError:
    try:
        from guardrails import bonferroni_alpha
    except ImportError:
        def bonferroni_alpha(n_tests, alpha=0.05):
            if n_tests <= 0:
                return alpha
            return alpha / n_tests


DIMENSIONS = ["composite", "purpose", "scope", "boundary", "tool", "chain"]
MIN_SAMPLE_SIZE = 30  # Minimum events per group for significance testing
VERDICT_ORDER = ["EXECUTE", "CLARIFY", "INERT", "ESCALATE"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stdev(values: List[float], mean: float) -> float:
    """Compute sample standard deviation."""
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _mean(values: List[float]) -> float:
    """Compute arithmetic mean."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _cohens_d(
    mean_a: float, mean_b: float,
    stdev_a: float, stdev_b: float,
    n_a: int, n_b: int,
) -> float:
    """Compute Cohen's d effect size.

    Uses pooled standard deviation. Returns 0.0 when both groups
    have zero variance (identical scores).
    """
    if (n_a + n_b) > 2:
        pooled_std = math.sqrt(
            ((n_a - 1) * stdev_a ** 2 + (n_b - 1) * stdev_b ** 2)
            / (n_a + n_b - 2)
        )
    else:
        pooled_std = 1.0
    if pooled_std == 0:
        return 0.0
    return (mean_b - mean_a) / pooled_std


def _effect_label(d: float) -> str:
    """Interpret Cohen's d magnitude."""
    ad = abs(d)
    if ad < 0.2:
        return "neg"
    elif ad < 0.5:
        return "sm"
    elif ad < 0.8:
        return "med"
    else:
        return "lg"


def _get_dimension_values(events: List[AuditEvent], dim: str) -> List[float]:
    """Extract a dimension's values from a list of events."""
    return [getattr(e, dim) for e in events]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class VerdictComparison:
    """Side-by-side verdict rate comparison."""
    verdict: str
    count_a: int
    count_b: int
    rate_a: float   # count_a / n_a
    rate_b: float   # count_b / n_b
    delta: float    # rate_b - rate_a


@dataclass
class DimensionComparison:
    """Side-by-side fidelity dimension comparison with effect size."""
    dimension: str
    mean_a: float
    mean_b: float
    delta: float        # mean_b - mean_a
    stdev_a: float
    stdev_b: float
    cohens_d: float     # effect size
    p_value: Optional[float]    # Mann-Whitney U, None if scipy unavailable
    significant: Optional[bool]  # p < 0.05


@dataclass
class CompareResult:
    """Full comparison result between two corpus subsets."""
    label_a: str
    label_b: str
    n_a: int
    n_b: int
    verdict_comparison: List[VerdictComparison]
    dimension_comparison: List[DimensionComparison]
    chi2_statistic: Optional[float]     # chi-squared for verdict distribution
    chi2_p_value: Optional[float]
    verdict_distributions_differ: Optional[bool]  # p < 0.05

    def format(self) -> str:
        """Format as human-readable comparison table."""
        lines = [
            f"Comparison: {self.label_a} vs {self.label_b}",
            "=" * 50,
            f"  Group A ({self.label_a}):  {self.n_a} events",
            f"  Group B ({self.label_b}):  {self.n_b} events",
        ]

        # --- Verdict distribution ---
        lines.append("")
        lines.append("  Verdict Distribution:")
        lines.append(
            f"  {'Verdict':<12} {'Rate A':>8} {'Rate B':>8} {'Delta':>8}"
        )
        lines.append(
            f"  {'-' * 12} {'-' * 8} {'-' * 8} {'-' * 8}"
        )
        for vc in self.verdict_comparison:
            delta_str = f"{vc.delta:+.1%}" if vc.delta != 0 else "  0.0%"
            lines.append(
                f"  {vc.verdict:<12} {vc.rate_a:>7.1%} {vc.rate_b:>7.1%} "
                f"{delta_str:>8}"
            )

        # Chi-squared summary
        if self.chi2_statistic is not None:
            sig_str = "significant" if self.verdict_distributions_differ else "not significant"
            lines.append(
                f"  Chi-squared: {self.chi2_statistic:.2f} "
                f"(p={self.chi2_p_value:.3f}, {sig_str})"
            )
        else:
            lines.append("  Chi-squared: scipy not available")

        # --- Dimension analysis ---
        lines.append("")
        lines.append("  Dimension Analysis:")
        lines.append(
            "  {:<12} {:>8} {:>8} {:>8} {:>11} {:>5}".format(
                "Dimension", "Mean A", "Mean B", "Delta", "Cohen's d", "Sig"
            )
        )
        lines.append(
            f"  {'-' * 12} {'-' * 8} {'-' * 8} "
            f"{'-' * 8} {'-' * 11} {'-' * 5}"
        )
        for dc in self.dimension_comparison:
            delta_str = f"{dc.delta:+.3f}"
            d_str = f"{dc.cohens_d:+.2f} ({_effect_label(dc.cohens_d)})"
            if dc.significant is not None:
                sig_str = "  *" if dc.significant else ""
            else:
                sig_str = ""
            lines.append(
                f"  {dc.dimension:<12} {dc.mean_a:>8.3f} {dc.mean_b:>8.3f} "
                f"{delta_str:>8} {d_str:>11}{sig_str}"
            )

        if not _HAS_SCIPY:
            lines.append("  (p-values omitted: scipy not available)")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Serialize for JSON output."""
        return {
            "label_a": self.label_a,
            "label_b": self.label_b,
            "n_a": self.n_a,
            "n_b": self.n_b,
            "verdict_comparison": [
                {
                    "verdict": vc.verdict,
                    "count_a": vc.count_a,
                    "count_b": vc.count_b,
                    "rate_a": vc.rate_a,
                    "rate_b": vc.rate_b,
                    "delta": vc.delta,
                }
                for vc in self.verdict_comparison
            ],
            "dimension_comparison": [
                {
                    "dimension": dc.dimension,
                    "mean_a": dc.mean_a,
                    "mean_b": dc.mean_b,
                    "delta": dc.delta,
                    "stdev_a": dc.stdev_a,
                    "stdev_b": dc.stdev_b,
                    "cohens_d": dc.cohens_d,
                    "p_value": dc.p_value,
                    "significant": dc.significant,
                }
                for dc in self.dimension_comparison
            ],
            "chi2_statistic": self.chi2_statistic,
            "chi2_p_value": self.chi2_p_value,
            "verdict_distributions_differ": self.verdict_distributions_differ,
        }


# ---------------------------------------------------------------------------
# Core comparison
# ---------------------------------------------------------------------------

def compare(
    corpus_a: AuditCorpus,
    corpus_b: AuditCorpus,
    label_a: str = "A",
    label_b: str = "B",
) -> CompareResult:
    """Structured comparison of two corpus subsets.

    Computes side-by-side verdict distributions (with chi-squared test),
    per-dimension fidelity deltas (with Mann-Whitney U), and Cohen's d
    effect sizes. Normalizes to rates for unequal corpus sizes.

    Args:
        corpus_a: First group (baseline / before / control)
        corpus_b: Second group (treatment / after / experimental)
        label_a: Human-readable label for group A
        label_b: Human-readable label for group B

    Returns:
        CompareResult with all comparisons.

    Example:
        before = corpus.filter(session="session-old")
        after = corpus.filter(session="session-new")
        result = compare(before, after, "Before Deploy", "After Deploy")
        print(result.format())
    """
    n_a = len(corpus_a)
    n_b = len(corpus_b)

    # --- Verdict comparison ---
    counts_a: Dict[str, int] = {}
    counts_b: Dict[str, int] = {}
    for e in corpus_a.events:
        counts_a[e.verdict] = counts_a.get(e.verdict, 0) + 1
    for e in corpus_b.events:
        counts_b[e.verdict] = counts_b.get(e.verdict, 0) + 1

    # Union of all verdicts, ordered by VERDICT_ORDER then alphabetical
    all_verdicts = []
    for v in VERDICT_ORDER:
        if v in counts_a or v in counts_b:
            all_verdicts.append(v)
    for v in sorted(set(counts_a) | set(counts_b)):
        if v not in all_verdicts:
            all_verdicts.append(v)

    verdict_comparisons = []
    for v in all_verdicts:
        ca = counts_a.get(v, 0)
        cb = counts_b.get(v, 0)
        ra = ca / n_a if n_a > 0 else 0.0
        rb = cb / n_b if n_b > 0 else 0.0
        verdict_comparisons.append(VerdictComparison(
            verdict=v,
            count_a=ca,
            count_b=cb,
            rate_a=ra,
            rate_b=rb,
            delta=rb - ra,
        ))

    # Chi-squared test on verdict distribution
    chi2_stat: Optional[float] = None
    chi2_p: Optional[float] = None
    chi2_differs: Optional[bool] = None

    if _HAS_SCIPY and n_a > 0 and n_b > 0 and len(all_verdicts) >= 2:
        # Build contingency table: rows = groups (A, B), cols = verdicts
        observed = [
            [counts_a.get(v, 0) for v in all_verdicts],
            [counts_b.get(v, 0) for v in all_verdicts],
        ]
        # Only run if we have at least some non-zero columns
        total_per_col = [observed[0][i] + observed[1][i] for i in range(len(all_verdicts))]
        non_zero_cols = sum(1 for t in total_per_col if t > 0)
        if non_zero_cols >= 2:
            try:
                stat, p, _dof, _expected = chi2_contingency(observed)
                chi2_stat = float(stat)
                chi2_p = float(p)
                chi2_differs = p < 0.05
            except ValueError:
                # Can happen with degenerate tables
                pass

    # --- Dimension comparison ---
    dimension_comparisons = []
    for dim in DIMENSIONS:
        vals_a = _get_dimension_values(corpus_a.events, dim)
        vals_b = _get_dimension_values(corpus_b.events, dim)

        m_a = _mean(vals_a)
        m_b = _mean(vals_b)
        sd_a = _stdev(vals_a, m_a)
        sd_b = _stdev(vals_b, m_b)
        d = _cohens_d(m_a, m_b, sd_a, sd_b, n_a, n_b)

        p_val: Optional[float] = None
        sig: Optional[bool] = None

        if _HAS_SCIPY and n_a > 0 and n_b > 0:
            try:
                _u, p = mannwhitneyu(vals_a, vals_b, alternative="two-sided")
                p_val = float(p)
                if n_a < MIN_SAMPLE_SIZE or n_b < MIN_SAMPLE_SIZE:
                    sig = None  # insufficient sample size
                else:
                    n_tests = len(DIMENSIONS)
                    sig = p < bonferroni_alpha(n_tests)
            except ValueError:
                # All identical values or empty
                pass

        dimension_comparisons.append(DimensionComparison(
            dimension=dim,
            mean_a=m_a,
            mean_b=m_b,
            delta=m_b - m_a,
            stdev_a=sd_a,
            stdev_b=sd_b,
            cohens_d=d,
            p_value=p_val,
            significant=sig,
        ))

    return CompareResult(
        label_a=label_a,
        label_b=label_b,
        n_a=n_a,
        n_b=n_b,
        verdict_comparison=verdict_comparisons,
        dimension_comparison=dimension_comparisons,
        chi2_statistic=chi2_stat,
        chi2_p_value=chi2_p,
        verdict_distributions_differ=chi2_differs,
    )


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------

def compare_sessions(
    corpus: AuditCorpus,
    session_a: str,
    session_b: str,
) -> CompareResult:
    """Compare two sessions within a corpus.

    Convenience wrapper -- filters by session_id and calls compare().

    Args:
        corpus: Full AuditCorpus
        session_a: Session ID for group A
        session_b: Session ID for group B

    Returns:
        CompareResult with session IDs as labels.

    Example:
        result = compare_sessions(corpus, "sess-abc", "sess-xyz")
        print(result.format())
    """
    a = corpus.filter(session=session_a)
    b = corpus.filter(session=session_b)
    return compare(a, b, label_a=session_a, label_b=session_b)


def compare_tools(
    corpus: AuditCorpus,
    tool_a: str,
    tool_b: str,
) -> CompareResult:
    """Compare two tool types within a corpus.

    Convenience wrapper -- filters by tool_call and calls compare().

    Args:
        corpus: Full AuditCorpus
        tool_a: Tool name for group A (e.g., "Bash")
        tool_b: Tool name for group B (e.g., "Edit")

    Returns:
        CompareResult with tool names as labels.

    Example:
        result = compare_tools(corpus, "Bash", "Edit")
        print(result.format())
    """
    a = corpus.filter(tool=tool_a)
    b = corpus.filter(tool=tool_b)
    return compare(a, b, label_a=tool_a, label_b=tool_b)


def compare_periods(
    corpus: AuditCorpus,
    before_index: int,
    after_index: Optional[int] = None,
) -> CompareResult:
    """Compare events before and after a split point.

    Splits the corpus at before_index. Events [0, before_index) form
    group A ("Before"), events [before_index, after_index) or
    [before_index, end) form group B ("After").

    Args:
        corpus: Full AuditCorpus (should be temporally ordered)
        before_index: Split point -- events before this index are group A
        after_index: Optional end of group B (defaults to end of corpus)

    Returns:
        CompareResult with "Before" and "After" labels.

    Example:
        # Deploy happened around event 500
        result = compare_periods(corpus, before_index=500)
        print(result.format())
    """
    if after_index is None:
        after_index = len(corpus)

    a = corpus[:before_index]
    b = corpus[before_index:after_index]
    return compare(a, b, label_a="Before", label_b="After")

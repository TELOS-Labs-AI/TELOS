"""
Temporal Analysis Tool
=======================

Temporal analysis of governance audit data — segment a corpus by time
windows, sessions, or quartiles, then track fidelity metrics, verdict
rates, and escalation trends over time.

This is the "is governance getting better or worse?" tool. It answers:
- How has composite fidelity changed over the life of the corpus?
- Are escalation rates trending up or down?
- Did a regime change (config update, model swap) cause a structural break?

Methodological basis:
  - Rolling window analysis (Box & Jenkins, 1976)
  - Simple OLS trend detection (Hastie et al., 2009)
  - Structural break detection via z-score (Bai & Perron, 1998)

Usage:
    from telos_governance.corpus import load_corpus
    from telos_governance.timeline import timeline, session_timeline

    corpus = load_corpus("~/.telos/posthoc_audit/")

    # Rolling window analysis
    result = timeline(corpus, window_size=50, step=25)
    print(result.format())

    # Per-session trend
    s = session_timeline(corpus)
    print(s.format())

    # Detect regime changes (structural breaks)
    from telos_governance.timeline import detect_regime_change
    breaks = detect_regime_change(corpus, dimension="composite", threshold=2.0)
    for b in breaks:
        print(f"  Break at index {b.index}: z={b.z_score:+.2f}")
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


# ---------------------------------------------------------------------------
# Linear regression helper
# ---------------------------------------------------------------------------

def _linear_regression(ys):
    """Simple OLS: y = mx + b. Returns (slope, intercept, r_squared)."""
    n = len(ys)
    if n < 2:
        return 0.0, ys[0] if ys else 0.0, 0.0
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    ss_xx = sum((x - x_mean) ** 2 for x in xs)
    ss_yy = sum((y - y_mean) ** 2 for y in ys)
    if ss_xx == 0:
        return 0.0, y_mean, 0.0
    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean
    r_squared = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_yy > 0 else 0.0
    return slope, intercept, r_squared


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class WindowPoint:
    """A single window in a rolling-window timeline analysis."""
    start_index: int
    end_index: int
    start_time: str
    end_time: str
    n_events: int
    mean_composite: float
    mean_values: Dict[str, float]   # per-dimension means
    verdict_counts: Dict[str, int]
    escalation_rate: float


@dataclass
class TimelineResult:
    """Result of a rolling-window timeline analysis.

    Contains one WindowPoint per stride position, plus trend statistics
    computed from the primary metric's mean values across windows.
    """
    points: List[WindowPoint]
    metric: str
    window_size: int
    step: int
    trend: str          # "improving", "stable", "degrading"
    slope: float
    r_squared: float

    def format(self) -> str:
        """Format as a human-readable table."""
        if not self.points:
            return "Timeline Analysis: no data (0 windows)"

        sign = "+" if self.slope >= 0 else ""
        lines = [
            f"Timeline Analysis (window={self.window_size}, step={self.step})",
            "=" * 60,
            f"  Metric: {self.metric}",
            f"  Trend:  {self.trend} (slope={sign}{self.slope:.4f}, "
            f"R\u00b2={self.r_squared:.2f})",
            f"  Windows: {len(self.points)}",
            "",
        ]

        # Header
        header = (
            f"  {'Window':<12}  {'Events':>6}  "
            f"{'Composite':>9}  {'EXEC':>5}  {'CLAR':>5}  "
            f"{'INRT':>5}  {'ESC':>5}  {'EscRate':>7}"
        )
        lines.append(header)
        sep = (
            f"  {'-' * 12}  {'-' * 6}  "
            f"{'-' * 9}  {'-' * 5}  {'-' * 5}  "
            f"{'-' * 5}  {'-' * 5}  {'-' * 7}"
        )
        lines.append(sep)

        # Data rows
        for wp in self.points:
            vc = wp.verdict_counts
            window_label = f"{wp.start_index}-{wp.end_index}"
            lines.append(
                f"  {window_label:<12}  {wp.n_events:>6}  "
                f"{wp.mean_composite:>9.3f}  "
                f"{vc.get('EXECUTE', 0):>5}  "
                f"{vc.get('CLARIFY', 0):>5}  "
                f"{vc.get('INERT', 0):>5}  "
                f"{vc.get('ESCALATE', 0):>5}  "
                f"{wp.escalation_rate:>6.1%}"
            )

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Serialize for JSON output."""
        return {
            "metric": self.metric,
            "window_size": self.window_size,
            "step": self.step,
            "trend": self.trend,
            "slope": self.slope,
            "r_squared": self.r_squared,
            "n_windows": len(self.points),
            "windows": [
                {
                    "start_index": wp.start_index,
                    "end_index": wp.end_index,
                    "start_time": wp.start_time,
                    "end_time": wp.end_time,
                    "n_events": wp.n_events,
                    "mean_composite": wp.mean_composite,
                    "mean_values": wp.mean_values,
                    "verdict_counts": wp.verdict_counts,
                    "escalation_rate": wp.escalation_rate,
                }
                for wp in self.points
            ],
        }

    def plot(self, ax=None, figsize: Tuple = (12, 5)):
        """Plot timeline. Requires telos-gov[research].

        Plots composite fidelity trend with escalation rate overlay.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "matplotlib is required for plotting. "
                "Install with: pip install telos-gov[research]"
            )

        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)

        midpoints = [
            (wp.start_index + wp.end_index) / 2 for wp in self.points
        ]
        composites = [wp.mean_composite for wp in self.points]
        esc_rates = [wp.escalation_rate for wp in self.points]

        ax.plot(midpoints, composites, "b-o", markersize=4, label="Composite")
        ax.set_xlabel("Event Index (window midpoint)")
        ax.set_ylabel("Mean Composite Fidelity", color="b")
        ax.tick_params(axis="y", labelcolor="b")

        ax2 = ax.twinx()
        ax2.plot(midpoints, esc_rates, "r-s", markersize=3, alpha=0.7,
                 label="Escalation Rate")
        ax2.set_ylabel("Escalation Rate", color="r")
        ax2.tick_params(axis="y", labelcolor="r")
        ax2.set_ylim(-0.05, max(esc_rates) * 1.3 if esc_rates else 1.0)

        sign = "+" if self.slope >= 0 else ""
        ax.set_title(
            f"Timeline: {self.trend} "
            f"(slope={sign}{self.slope:.4f}, R\u00b2={self.r_squared:.2f})"
        )
        ax.grid(True, alpha=0.3)

        return ax


@dataclass
class SessionPoint:
    """Aggregated metrics for a single session in a session timeline."""
    session_id: str
    n_events: int
    start_time: str
    end_time: str
    mean_composite: float
    mean_values: Dict[str, float]   # per-dimension means
    verdict_counts: Dict[str, int]
    escalation_rate: float


@dataclass
class SessionTimelineResult:
    """Result of a per-session timeline analysis.

    One SessionPoint per session, ordered by first event timestamp.
    """
    sessions: List[SessionPoint]
    trend: str          # "improving", "stable", "degrading"
    slope: float
    r_squared: float

    def format(self) -> str:
        """Format as a human-readable table."""
        if not self.sessions:
            return "Session Timeline: no data (0 sessions)"

        sign = "+" if self.slope >= 0 else ""
        lines = [
            "Session Timeline",
            "=" * 70,
            f"  Sessions: {len(self.sessions)}",
            f"  Trend:    {self.trend} (slope={sign}{self.slope:.4f}, "
            f"R\u00b2={self.r_squared:.2f})",
            "",
        ]

        # Header
        header = (
            f"  {'#':>3}  {'Session':>12}  {'Events':>6}  "
            f"{'Composite':>9}  {'EXEC':>5}  {'ESC':>5}  "
            f"{'EscRate':>7}  {'Date':>10}"
        )
        lines.append(header)
        sep = (
            f"  {'-' * 3}  {'-' * 12}  {'-' * 6}  "
            f"{'-' * 9}  {'-' * 5}  {'-' * 5}  "
            f"{'-' * 7}  {'-' * 10}"
        )
        lines.append(sep)

        # Data rows
        for i, sp in enumerate(self.sessions):
            # Truncate session ID for display
            sid = sp.session_id[:12] if len(sp.session_id) > 12 else sp.session_id
            date_str = sp.start_time[:10] if sp.start_time else ""
            vc = sp.verdict_counts
            lines.append(
                f"  {i:>3}  {sid:>12}  {sp.n_events:>6}  "
                f"{sp.mean_composite:>9.3f}  "
                f"{vc.get('EXECUTE', 0):>5}  "
                f"{vc.get('ESCALATE', 0):>5}  "
                f"{sp.escalation_rate:>6.1%}  "
                f"{date_str:>10}"
            )

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Serialize for JSON output."""
        return {
            "trend": self.trend,
            "slope": self.slope,
            "r_squared": self.r_squared,
            "n_sessions": len(self.sessions),
            "sessions": [
                {
                    "session_id": sp.session_id,
                    "n_events": sp.n_events,
                    "start_time": sp.start_time,
                    "end_time": sp.end_time,
                    "mean_composite": sp.mean_composite,
                    "mean_values": sp.mean_values,
                    "verdict_counts": sp.verdict_counts,
                    "escalation_rate": sp.escalation_rate,
                }
                for sp in self.sessions
            ],
        }


@dataclass
class RegimeChange:
    """A detected structural break (regime change) in the time series."""
    index: int
    timestamp: str
    value: float
    rolling_mean: float
    z_score: float
    dimension: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mean(values: List[float]) -> float:
    """Compute mean of a list. Returns 0.0 for empty list."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _stdev(values: List[float], mean_val: float) -> float:
    """Compute sample standard deviation."""
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean_val) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _compute_window_point(
    events: List[AuditEvent],
    start_index: int,
    end_index: int,
) -> WindowPoint:
    """Build a WindowPoint from a slice of events."""
    n = len(events)

    # Per-dimension means
    mean_values = {}
    for dim in DIMENSIONS:
        vals = [getattr(e, dim) for e in events]
        mean_values[dim] = _mean(vals)

    # Verdict counts
    verdict_counts: Dict[str, int] = {}
    for e in events:
        verdict_counts[e.verdict] = verdict_counts.get(e.verdict, 0) + 1

    # Escalation rate
    esc_count = verdict_counts.get("ESCALATE", 0)
    escalation_rate = esc_count / n if n > 0 else 0.0

    # Timestamps
    start_time = events[0].timestamp if events else ""
    end_time = events[-1].timestamp if events else ""

    return WindowPoint(
        start_index=start_index,
        end_index=end_index,
        start_time=start_time,
        end_time=end_time,
        n_events=n,
        mean_composite=mean_values.get("composite", 0.0),
        mean_values=mean_values,
        verdict_counts=verdict_counts,
        escalation_rate=escalation_rate,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def trend_direction(values: List[float]) -> Tuple[str, float, float]:
    """Determine trend direction from a sequence of values.

    Uses simple linear regression (OLS) to fit a trend line, then
    classifies as improving, stable, or degrading based on slope
    magnitude and R-squared.

    Args:
        values: Sequence of float values over time (e.g., composite means).

    Returns:
        Tuple of (direction, slope, r_squared) where direction is one of
        "improving", "stable", or "degrading".

    Rules:
        - "stable" if R^2 < 0.10 (trend explains <10% of variance)
        - "stable" if |slope| < 0.001 (negligible change per step)
        - "improving" if slope > 0 (fidelity increasing over time)
        - "degrading" if slope < 0 (fidelity decreasing over time)
    """
    if len(values) < 2:
        return "stable", 0.0, 0.0

    slope, _intercept, r_squared = _linear_regression(values)

    if r_squared < 0.10 or abs(slope) < 0.001:
        return "stable", slope, r_squared
    elif slope > 0:
        return "improving", slope, r_squared
    else:
        return "degrading", slope, r_squared


def timeline(
    corpus: AuditCorpus,
    window_size: int = 50,
    step: int = 25,
    metric: str = "composite",
) -> TimelineResult:
    """Rolling-window temporal analysis of a corpus.

    Slides a window of ``window_size`` events across the corpus with
    ``step`` stride. At each position computes per-dimension means,
    verdict distribution, and escalation rate. Fits a trend line to
    the primary metric's rolling means.

    Args:
        corpus: AuditCorpus to analyze (events must be timestamp-sorted).
        window_size: Number of events per window.
        step: Stride between successive windows.
        metric: Primary dimension to track for trend detection.
            One of "composite", "purpose", "scope", "boundary",
            "tool", "chain".

    Returns:
        TimelineResult with list of WindowPoint dataclasses and overall
        trend classification.

    Example:
        result = timeline(corpus, window_size=50, step=25)
        print(result.format())
        print(f"Trend: {result.trend} (slope={result.slope:+.4f})")
    """
    if metric not in DIMENSIONS:
        raise ValueError(
            f"Unknown metric: {metric}. "
            f"Must be one of: {', '.join(DIMENSIONS)}"
        )

    events = corpus.events
    n = len(events)

    if n == 0:
        return TimelineResult(
            points=[], metric=metric, window_size=window_size,
            step=step, trend="stable", slope=0.0, r_squared=0.0,
        )

    # Build window points
    points: List[WindowPoint] = []
    start = 0
    while start + window_size <= n:
        end = start + window_size
        window_events = events[start:end]
        wp = _compute_window_point(window_events, start, end - 1)
        points.append(wp)
        start += step

    # Handle the case where corpus is smaller than window_size:
    # produce a single window covering the whole corpus
    if not points and n > 0:
        wp = _compute_window_point(events, 0, n - 1)
        points.append(wp)

    # Trend detection on the primary metric
    metric_values = [wp.mean_values.get(metric, wp.mean_composite)
                     for wp in points]
    direction, slope, r_squared = trend_direction(metric_values)

    return TimelineResult(
        points=points,
        metric=metric,
        window_size=window_size,
        step=step,
        trend=direction,
        slope=slope,
        r_squared=r_squared,
    )


def session_timeline(corpus: AuditCorpus) -> SessionTimelineResult:
    """Per-session temporal analysis.

    Produces one data point per session, ordered by the first event
    timestamp in each session. Fits a trend line across session-level
    composite fidelity means.

    Args:
        corpus: AuditCorpus to analyze.

    Returns:
        SessionTimelineResult with one SessionPoint per session and
        overall trend classification.

    Example:
        result = session_timeline(corpus)
        print(result.format())
        for sp in result.sessions:
            print(f"  {sp.session_id[:8]}: composite={sp.mean_composite:.3f}")
    """
    events = corpus.events
    if not events:
        return SessionTimelineResult(
            sessions=[], trend="stable", slope=0.0, r_squared=0.0,
        )

    # Group events by session
    session_buckets: Dict[str, List[AuditEvent]] = {}
    for e in events:
        if e.session_id not in session_buckets:
            session_buckets[e.session_id] = []
        session_buckets[e.session_id].append(e)

    # Order sessions by first event timestamp
    session_order = sorted(
        session_buckets.keys(),
        key=lambda sid: session_buckets[sid][0].timestamp,
    )

    # Build session points
    session_points: List[SessionPoint] = []
    for sid in session_order:
        sess_events = session_buckets[sid]
        n = len(sess_events)

        # Per-dimension means
        mean_values = {}
        for dim in DIMENSIONS:
            vals = [getattr(e, dim) for e in sess_events]
            mean_values[dim] = _mean(vals)

        # Verdict counts
        verdict_counts: Dict[str, int] = {}
        for e in sess_events:
            verdict_counts[e.verdict] = verdict_counts.get(e.verdict, 0) + 1

        esc_count = verdict_counts.get("ESCALATE", 0)
        escalation_rate = esc_count / n if n > 0 else 0.0

        start_time = sess_events[0].timestamp
        end_time = sess_events[-1].timestamp

        session_points.append(SessionPoint(
            session_id=sid,
            n_events=n,
            start_time=start_time,
            end_time=end_time,
            mean_composite=mean_values.get("composite", 0.0),
            mean_values=mean_values,
            verdict_counts=verdict_counts,
            escalation_rate=escalation_rate,
        ))

    # Trend detection across sessions
    composite_values = [sp.mean_composite for sp in session_points]
    direction, slope, r_squared = trend_direction(composite_values)

    return SessionTimelineResult(
        sessions=session_points,
        trend=direction,
        slope=slope,
        r_squared=r_squared,
    )


def detect_regime_change(
    corpus: AuditCorpus,
    dimension: str = "composite",
    threshold: float = 2.0,
    lookback: int = 30,
) -> List[RegimeChange]:
    """Detect structural breaks (regime changes) in a corpus.

    Uses a rolling z-score approach: computes a rolling mean and
    rolling standard deviation over a lookback window, then flags
    points where the observed value deviates more than ``threshold``
    standard deviations from the rolling mean.

    Args:
        corpus: AuditCorpus to analyze.
        dimension: Fidelity dimension to monitor. One of "composite",
            "purpose", "scope", "boundary", "tool", "chain".
        threshold: Z-score threshold for flagging a regime change
            (default 2.0 = ~95% confidence under normality).
        lookback: Number of preceding events for the rolling window.

    Returns:
        List of RegimeChange dataclasses, ordered by corpus index.

    Example:
        breaks = detect_regime_change(corpus, "composite", threshold=2.0)
        for b in breaks:
            print(f"  [{b.index}] z={b.z_score:+.2f}  "
                  f"value={b.value:.3f}  rolling_mean={b.rolling_mean:.3f}")
    """
    if dimension not in DIMENSIONS:
        raise ValueError(
            f"Unknown dimension: {dimension}. "
            f"Must be one of: {', '.join(DIMENSIONS)}"
        )

    events = corpus.events
    n = len(events)
    if n < lookback + 1:
        return []

    values = [getattr(e, dimension) for e in events]
    changes: List[RegimeChange] = []

    for i in range(lookback, n):
        window = values[i - lookback:i]
        w_mean = _mean(window)
        w_std = _stdev(window, w_mean)

        if w_std < 1e-9:
            # No variance in the lookback window — skip
            continue

        z = (values[i] - w_mean) / w_std

        if abs(z) >= threshold:
            changes.append(RegimeChange(
                index=i,
                timestamp=events[i].timestamp,
                value=values[i],
                rolling_mean=w_mean,
                z_score=z,
                dimension=dimension,
            ))

    return changes


def format_regime_changes(changes: List[RegimeChange]) -> str:
    """Format a list of regime changes as a readable table.

    Args:
        changes: List of RegimeChange objects from detect_regime_change().

    Returns:
        Human-readable table string.
    """
    if not changes:
        return "No regime changes detected."

    dim = changes[0].dimension
    lines = [
        f"Regime Changes ({dim}, n={len(changes)})",
        "=" * 60,
        "",
        f"  {'Index':>6}  {'Timestamp':>20}  {'Value':>7}  "
        f"{'RolMean':>7}  {'Z-Score':>7}",
        f"  {'-' * 6}  {'-' * 20}  {'-' * 7}  {'-' * 7}  {'-' * 7}",
    ]

    for rc in changes:
        ts = rc.timestamp[:20] if rc.timestamp else ""
        lines.append(
            f"  {rc.index:>6}  {ts:>20}  {rc.value:>7.3f}  "
            f"{rc.rolling_mean:>7.3f}  {rc.z_score:>+7.2f}"
        )

    return "\n".join(lines)

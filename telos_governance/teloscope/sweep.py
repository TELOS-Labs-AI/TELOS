"""
Parameter Sweep Engine
=======================

Systematic parameter sweep over governance thresholds -- loops rescore()
across a range of values for one or more ThresholdConfig parameters.

This is the "dose-response curve" for governance: how does the system
behave as you dial a parameter from low to high?

Methodological basis:
  - Grid search (Bergstra & Bengio, 2012)
  - Dose-response analysis (pharmacology)
  - Multi-way sensitivity analysis (Saltelli et al., 2004)

Usage:
    from telos_governance.corpus import load_corpus
    from telos_governance.sweep import sweep

    corpus = load_corpus("~/.telos/posthoc_audit/")

    # Single-parameter sweep: vary execute threshold
    result = sweep(corpus, "st_execute", start=0.30, stop=0.70, step=0.05)
    print(result.to_table())

    # With ground truth labels for accuracy curves
    labels = {"event_id_1": "EXECUTE", "event_id_2": "ESCALATE", ...}
    result = sweep(corpus, "st_execute", start=0.30, stop=0.70, step=0.05,
                   ground_truth=labels)
    result.plot(kind="roc")  # requires telos-gov[research]
"""
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    from telos_governance.threshold_config import ThresholdConfig
    from telos_governance.corpus import AuditCorpus
    from telos_governance.rescore import rescore, RescoreResult, VERDICT_ORDER
except ImportError:
    from threshold_config import ThresholdConfig
    from corpus import AuditCorpus
    from rescore import rescore, RescoreResult, VERDICT_ORDER

try:
    from telos_governance.guardrails import bonferroni_alpha, is_significant_corrected
except ImportError:
    try:
        from guardrails import bonferroni_alpha, is_significant_corrected
    except ImportError:
        def bonferroni_alpha(n_tests: int, alpha: float = 0.05) -> float:
            return alpha / n_tests if n_tests > 0 else alpha

        def is_significant_corrected(p_value: float, n_tests: int, alpha: float = 0.05):
            corrected = bonferroni_alpha(n_tests, alpha)
            return p_value < corrected, corrected


@dataclass
class SweepPoint:
    """A single point in a parameter sweep."""
    param_value: float
    result: RescoreResult
    accuracy: Optional[float] = None
    fpr: Optional[float] = None


@dataclass
class SweepResult:
    """Result of a parameter sweep.

    Contains one RescoreResult per parameter value tested, plus
    aggregate statistics for plotting dose-response curves.

    Includes Bonferroni-corrected significance threshold:
    each sweep point is a hypothesis test, so family-wise error rate
    must be controlled. ``corrected_alpha`` divides the base alpha
    (0.05) by the number of sweep points.
    """
    param_name: str
    points: List[SweepPoint]
    ground_truth: Optional[Dict[str, str]] = None
    base_alpha: float = 0.05

    @property
    def param_values(self) -> List[float]:
        return [p.param_value for p in self.points]

    @property
    def n_points(self) -> int:
        return len(self.points)

    @property
    def corrected_alpha(self) -> float:
        """Bonferroni-corrected significance threshold.

        Each sweep point is a hypothesis test. corrected_alpha =
        base_alpha / n_points. Use this instead of raw alpha when
        evaluating statistical significance of any single point.
        """
        return bonferroni_alpha(self.n_points, self.base_alpha)

    def corrected_significance(self, p_values: List[float]) -> List[bool]:
        """Evaluate per-point significance after Bonferroni correction.

        Args:
            p_values: One p-value per sweep point.

        Returns:
            List of booleans -- True if significant after correction.
        """
        if len(p_values) != self.n_points:
            raise ValueError(
                f"Expected {self.n_points} p-values, got {len(p_values)}"
            )
        threshold = self.corrected_alpha
        return [p < threshold for p in p_values]

    def verdict_counts(self) -> Dict[str, List[int]]:
        """Get verdict counts at each sweep point.

        Returns dict of {verdict: [count_at_point_0, count_at_point_1, ...]}.
        Ready for plotting verdict distribution curves.
        """
        counts: Dict[str, List[int]] = {v: [] for v in VERDICT_ORDER}
        for point in self.points:
            dist = point.result.summary()["new_distribution"]
            for v in VERDICT_ORDER:
                counts[v].append(dist.get(v, 0))
        return counts

    def change_rates(self) -> List[float]:
        """Get change rate at each sweep point."""
        return [p.result.change_rate for p in self.points]

    def accuracies(self) -> Optional[List[float]]:
        """Get accuracy at each sweep point (if ground truth provided)."""
        if self.ground_truth is None:
            return None
        return [p.accuracy for p in self.points]

    def to_table(self) -> str:
        """Format sweep results as a human-readable table."""
        lines = [
            f"Parameter Sweep: {self.param_name}",
            "=" * (18 + len(self.param_name)),
            f"Points: {self.n_points}",
            f"Range:  {self.param_values[0]:.3f} to {self.param_values[-1]:.3f}",
            f"Bonferroni alpha: {self.corrected_alpha:.6f} "
            f"(base={self.base_alpha}, n_tests={self.n_points})",
            "",
        ]

        # Header
        header = f"  {'Value':>7}  {'Changed':>7}  {'Rate':>6}"
        for v in VERDICT_ORDER:
            header += f"  {v[:4]:>5}"
        if self.ground_truth:
            header += f"  {'Acc':>6}  {'FPR':>6}"
        lines.append(header)

        sep = f"  {'-------':>7}  {'-------':>7}  {'------':>6}"
        for _ in VERDICT_ORDER:
            sep += f"  {'-----':>5}"
        if self.ground_truth:
            sep += f"  {'------':>6}  {'------':>6}"
        lines.append(sep)

        # Data rows
        verdict_counts = self.verdict_counts()
        for i, point in enumerate(self.points):
            row = f"  {point.param_value:>7.3f}  {point.result.n_changed:>7}  {point.result.change_rate:>5.1%}"
            for v in VERDICT_ORDER:
                row += f"  {verdict_counts[v][i]:>5}"
            if self.ground_truth and point.accuracy is not None:
                row += f"  {point.accuracy:>5.1%}"
                if point.fpr is not None:
                    row += f"  {point.fpr:>5.1%}"
                else:
                    row += f"  {'N/A':>6}"
            lines.append(row)

        return "\n".join(lines)

    def to_csv(self, path: str) -> None:
        """Export sweep results to CSV with Bonferroni correction metadata."""
        verdict_counts = self.verdict_counts()
        with open(path, "w") as f:
            # Metadata header as comment
            f.write(f"# bonferroni_corrected_alpha={self.corrected_alpha:.6f},"
                    f"base_alpha={self.base_alpha},n_tests={self.n_points}\n")
            # Column header
            cols = [self.param_name, "n_changed", "change_rate"]
            cols.extend(VERDICT_ORDER)
            if self.ground_truth:
                cols.extend(["accuracy", "fpr"])
            f.write(",".join(cols) + "\n")

            # Rows
            for i, point in enumerate(self.points):
                vals = [
                    f"{point.param_value:.4f}",
                    str(point.result.n_changed),
                    f"{point.result.change_rate:.4f}",
                ]
                for v in VERDICT_ORDER:
                    vals.append(str(verdict_counts[v][i]))
                if self.ground_truth:
                    vals.append(f"{point.accuracy:.4f}" if point.accuracy is not None else "")
                    vals.append(f"{point.fpr:.4f}" if point.fpr is not None else "")
                f.write(",".join(vals) + "\n")

    def to_json(self, path: str) -> None:
        """Export sweep results to JSON with Bonferroni correction metadata."""
        data = {
            "param_name": self.param_name,
            "n_points": self.n_points,
            "base_alpha": self.base_alpha,
            "corrected_alpha": self.corrected_alpha,
            "points": [],
        }
        for point in self.points:
            entry = {
                "param_value": point.param_value,
                "n_changed": point.result.n_changed,
                "change_rate": point.result.change_rate,
                "verdict_distribution": point.result.summary()["new_distribution"],
            }
            if point.accuracy is not None:
                entry["accuracy"] = point.accuracy
            if point.fpr is not None:
                entry["fpr"] = point.fpr
            data["points"].append(entry)

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def to_dataframe(self):
        """Export sweep results to pandas DataFrame. Requires telos-gov[research].

        Includes ``corrected_alpha`` column so downstream analysis uses
        the Bonferroni-corrected threshold, not the raw base alpha.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for DataFrame export. "
                "Install with: pip install telos-gov[research]"
            )

        ca = self.corrected_alpha
        verdict_counts = self.verdict_counts()
        rows = []
        for i, point in enumerate(self.points):
            row = {
                self.param_name: point.param_value,
                "n_changed": point.result.n_changed,
                "change_rate": point.result.change_rate,
                "corrected_alpha": ca,
            }
            for v in VERDICT_ORDER:
                row[v] = verdict_counts[v][i]
            if point.accuracy is not None:
                row["accuracy"] = point.accuracy
            if point.fpr is not None:
                row["fpr"] = point.fpr
            rows.append(row)
        return pd.DataFrame(rows)

    def plot(self, kind: str = "verdicts", ax=None, figsize: Tuple = (10, 6)):
        """Plot sweep results. Requires telos-gov[research].

        Args:
            kind: Plot type -- "verdicts" (stacked area), "roc" (accuracy+FPR),
                  "change_rate" (verdict change rate curve)
            ax: Matplotlib axes to plot on (creates new figure if None)
            figsize: Figure size if creating new figure

        Returns:
            Matplotlib axes object.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "matplotlib is required for plotting. "
                "Install with: pip install telos-gov[research]"
            )

        if ax is None:
            _, ax = plt.subplots(figsize=figsize)

        values = self.param_values

        if kind == "verdicts":
            verdict_counts = self.verdict_counts()
            # Stacked area chart of verdict distribution
            colors = {
                "EXECUTE": "#2ecc71",
                "CLARIFY": "#f39c12",
                "INERT": "#95a5a6",
                "ESCALATE": "#e74c3c",
            }
            bottoms = [0] * len(values)
            for v in VERDICT_ORDER:
                counts = verdict_counts[v]
                ax.bar(
                    values, counts, bottom=bottoms, width=values[1] - values[0] if len(values) > 1 else 0.02,
                    label=v, color=colors.get(v, "#333"),
                    alpha=0.85,
                )
                bottoms = [b + c for b, c in zip(bottoms, counts)]
            ax.set_xlabel(self.param_name)
            ax.set_ylabel("Event Count")
            ax.set_title(f"Verdict Distribution vs {self.param_name}")
            ax.legend(loc="upper right")

        elif kind == "roc":
            if self.ground_truth is None:
                raise ValueError("ROC plot requires ground_truth labels")
            accs = self.accuracies()
            fprs = [p.fpr for p in self.points]
            ax.plot(values, accs, "b-o", label="Accuracy", markersize=4)
            if any(f is not None for f in fprs):
                fprs_clean = [f if f is not None else 0.0 for f in fprs]
                ax.plot(values, fprs_clean, "r-s", label="FPR", markersize=4)
            ax.set_xlabel(self.param_name)
            ax.set_ylabel("Rate")
            ax.set_title(f"Accuracy & FPR vs {self.param_name}")
            ax.legend()
            ax.set_ylim(-0.05, 1.05)
            ax.axhline(y=0.0, color="gray", linestyle="--", alpha=0.3)
            ax.axhline(y=1.0, color="gray", linestyle="--", alpha=0.3)

        elif kind == "change_rate":
            rates = self.change_rates()
            ax.plot(values, rates, "k-o", markersize=4)
            ax.set_xlabel(self.param_name)
            ax.set_ylabel("Change Rate")
            ax.set_title(f"Verdict Change Rate vs {self.param_name}")
            ax.set_ylim(-0.05, 1.05)

        else:
            raise ValueError(
                f"Unknown plot kind: {kind}. Use 'verdicts', 'roc', or 'change_rate'."
            )

        ax.grid(True, alpha=0.3)
        return ax

    def optimal_point(
        self, metric: str = "accuracy", minimize: bool = False
    ) -> Optional[SweepPoint]:
        """Find the sweep point that optimizes a metric.

        Args:
            metric: "accuracy", "fpr", "change_rate", or "execute_rate"
            minimize: If True, find minimum (e.g., for FPR). Default False (maximize).

        Returns:
            Best SweepPoint, or None if metric unavailable.
        """
        if metric == "accuracy":
            if self.ground_truth is None:
                return None
            scored = [(p, p.accuracy) for p in self.points if p.accuracy is not None]
        elif metric == "fpr":
            if self.ground_truth is None:
                return None
            scored = [(p, p.fpr) for p in self.points if p.fpr is not None]
            minimize = True  # FPR should always be minimized
        elif metric == "change_rate":
            scored = [(p, p.result.change_rate) for p in self.points]
        elif metric == "execute_rate":
            scored = []
            for p in self.points:
                dist = p.result.summary()["new_distribution"]
                total = p.result.n_total
                if total > 0:
                    scored.append((p, dist.get("EXECUTE", 0) / total))
        else:
            raise ValueError(f"Unknown metric: {metric}")

        if not scored:
            return None

        if minimize:
            return min(scored, key=lambda x: x[1])[0]
        else:
            return max(scored, key=lambda x: x[1])[0]


def _compute_fpr(
    result: RescoreResult, ground_truth: Dict[str, str]
) -> Optional[float]:
    """Compute false positive rate for a rescore result.

    FPR = (benign events classified as ESCALATE or INERT) / (total benign events)

    "Benign" = ground truth is EXECUTE or CLARIFY.
    "False positive" = benign event gets ESCALATE or INERT verdict.
    """
    benign_total = 0
    false_positives = 0
    blocking_verdicts = {"ESCALATE", "INERT"}

    for i, event in enumerate(result.corpus.events):
        if event.event_id not in ground_truth:
            continue
        expected = ground_truth[event.event_id]
        if expected in ("EXECUTE", "CLARIFY"):
            benign_total += 1
            if result.new_verdicts[i] in blocking_verdicts:
                false_positives += 1

    if benign_total == 0:
        return None
    return false_positives / benign_total


def sweep(
    corpus: "AuditCorpus",
    param_name: str,
    start: float,
    stop: float,
    step: float = 0.05,
    *,
    ground_truth: Optional[Dict[str, str]] = None,
    base_config: Optional["ThresholdConfig"] = None,
    escalation_threshold: float = 0.15,
) -> SweepResult:
    """Run a single-parameter sweep over a ThresholdConfig parameter.

    Varies one parameter from start to stop (inclusive) in step increments,
    running rescore() at each point. Optionally computes accuracy and FPR
    against ground truth labels.

    Args:
        corpus: AuditCorpus to sweep
        param_name: ThresholdConfig parameter name to vary
            (e.g., "st_execute", "weight_purpose", "boundary_violation")
        start: Starting value
        stop: Ending value (inclusive)
        step: Increment between points
        ground_truth: Optional dict of event_id -> expected verdict
        base_config: Base ThresholdConfig to modify (defaults if None)
        escalation_threshold: Fidelity below which ESCALATE fires

    Returns:
        SweepResult with one RescoreResult per parameter value.

    Example:
        result = sweep(corpus, "st_execute", 0.30, 0.70, step=0.05)
        print(result.to_table())

        # Find the threshold that maximizes accuracy
        best = result.optimal_point(metric="accuracy")
        print(f"Best st_execute: {best.param_value:.3f} (acc: {best.accuracy:.1%})")
    """
    # Validate param_name
    if base_config is None:
        base_config = ThresholdConfig()
    if not hasattr(base_config, param_name):
        valid = sorted(base_config.to_dict().keys())
        raise ValueError(
            f"Unknown parameter: {param_name}. "
            f"Valid parameters: {', '.join(valid)}"
        )

    # Generate sweep values
    values = []
    v = start
    while v <= stop + step * 0.01:  # float tolerance
        values.append(round(v, 6))
        v += step

    # Run rescore at each point
    points = []
    for val in values:
        result = rescore(
            corpus,
            config=base_config,
            escalation_threshold=escalation_threshold,
            **{param_name: val},
        )

        accuracy = None
        fpr = None
        if ground_truth:
            acc_result = result.accuracy(ground_truth)
            accuracy = acc_result.get("accuracy")
            fpr = _compute_fpr(result, ground_truth)

        points.append(SweepPoint(
            param_value=val,
            result=result,
            accuracy=accuracy,
            fpr=fpr,
        ))

    return SweepResult(
        param_name=param_name,
        points=points,
        ground_truth=ground_truth,
    )


def multi_sweep(
    corpus: "AuditCorpus",
    param_ranges: Dict[str, Tuple[float, float, float]],
    *,
    ground_truth: Optional[Dict[str, str]] = None,
    base_config: Optional["ThresholdConfig"] = None,
    escalation_threshold: float = 0.15,
    base_alpha: float = 0.05,
) -> Dict[str, SweepResult]:
    """Run independent sweeps over multiple parameters.

    Each parameter is swept independently while others stay at base values.
    For joint interaction effects, use grid_sweep() (not yet implemented).

    Bonferroni correction: the family-wise alpha is computed
    across the TOTAL test count (all params × all points per param),
    not per-param. Each returned SweepResult has its ``base_alpha``
    set to the family-wise corrected value.

    Args:
        corpus: AuditCorpus to sweep
        param_ranges: Dict of param_name -> (start, stop, step)
        ground_truth: Optional ground truth labels
        base_config: Base config to modify
        escalation_threshold: Fidelity below which ESCALATE fires
        base_alpha: Family-wise significance threshold (default 0.05)

    Returns:
        Dict of param_name -> SweepResult

    Example:
        results = multi_sweep(corpus, {
            "st_execute": (0.30, 0.70, 0.05),
            "st_clarify": (0.20, 0.50, 0.05),
            "weight_purpose": (0.20, 0.50, 0.05),
        })
        for name, result in results.items():
            print(f"\\n{result.to_table()}")
    """
    if base_config is None:
        base_config = ThresholdConfig()

    # Compute total test count across all params for family-wise correction
    def _count_points(start: float, stop: float, step: float) -> int:
        n = 0
        v = start
        while v <= stop + step * 0.01:
            n += 1
            v += step
        return n

    total_tests = sum(
        _count_points(rng[0], rng[1], rng[2])
        for rng in param_ranges.values()
    )
    family_alpha = bonferroni_alpha(total_tests, base_alpha)

    results = {}
    for param, rng in param_ranges.items():
        result = sweep(
            corpus,
            param,
            start=rng[0],
            stop=rng[1],
            step=rng[2],
            ground_truth=ground_truth,
            base_config=base_config,
            escalation_threshold=escalation_threshold,
        )
        # Override base_alpha with family-wise corrected value
        result.base_alpha = family_alpha
        results[param] = result

    return results

"""
Human Annotation Tool
======================

Stratified sampling, annotation schema, inter-rater reliability,
and calibration comparison for human labeling workflows. Enables
researchers to annotate governance events with ground-truth labels
for calibration -- answering "does the system agree with humans?"

Implements:
  - Stratified sampling (by verdict, tool, score quartile, edge cases)
  - Annotation record schema (AnnotationRecord dataclass)
  - Inter-rater reliability (Krippendorff's alpha, Cohen's kappa, % agreement)
  - Calibration comparison (confusion matrix, precision/recall/F1, systematic disagreements)
  - JSONL export/import with round-trip validation
  - Annotation worksheet generation (CSV, Zone 2/3 stripped)

Statistical methods:
  - Krippendorff's alpha for nominal data (Krippendorff, 2011)
  - Cohen's kappa for pairwise rater comparison (Cohen, 1960)
  - Percent agreement as interpretive baseline

Usage:
    from telos_governance.corpus import load_corpus
    from telos_governance.annotate import (
        sample_for_annotation, AnnotationRecord,
        compute_irr, compare_annotations_to_system,
        export_annotations, load_annotations,
        generate_worksheet,
    )

    corpus = load_corpus("~/.telos/posthoc_audit/")

    # Sample 50 events, stratified by verdict
    indices = sample_for_annotation(corpus, n=50, strategy="verdict")

    # Generate offline worksheet
    generate_worksheet(corpus, indices, "/tmp/annotation_worksheet.csv")

    # After human annotation, load and compute IRR
    annotations = load_annotations("/tmp/annotations.jsonl")
    irr = compute_irr(annotations)
    print(irr.format())

    # Compare human labels to system verdicts
    cal = compare_annotations_to_system(corpus, annotations)
    print(cal.format())
"""
import csv
import json
import math
import os
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from telos_governance.corpus import AuditCorpus, AuditEvent
except ImportError:
    from corpus import AuditCorpus, AuditEvent

try:
    from telos_governance.guardrails import redact_text, validate_export_path
except ImportError:
    try:
        from guardrails import redact_text, validate_export_path
    except ImportError:
        # Minimal fallback if guardrails not available
        import sys as _sys
        print(
            "WARNING: guardrails module not available -- using minimal "
            "fallback for redact_text and validate_export_path. "
            "Install telos_governance.guardrails for full protection.",
            file=_sys.stderr,
        )

        import re as _re

        def redact_text(text: str, level: int = 2) -> str:
            """Minimal fallback: sanitize home directory paths."""
            return _re.sub(r"/Users/[^/]+/", "~/", str(text))

        def validate_export_path(path: str, allowed_dir: str = None):
            """Minimal fallback: block path traversal."""
            normalized = os.path.normpath(path)
            if ".." in normalized.split(os.sep):
                return False, "Path traversal ('..') not allowed"
            return True, "OK (fallback validation)"


VERDICT_ORDER = ["EXECUTE", "CLARIFY", "INERT", "ESCALATE"]
# Reduced set for human annotation -- humans classify into the three
# actionable categories. INERT maps to CLARIFY in most
# annotation workflows, but the schema accepts any verdict string.
ANNOTATION_VERDICTS = {"EXECUTE", "CLARIFY", "INERT", "ESCALATE"}
DIMENSIONS = ["composite", "purpose", "scope", "boundary", "tool", "chain"]


# ---------------------------------------------------------------------------
# Sampling strategies
# ---------------------------------------------------------------------------

def sample_for_annotation(
    corpus: AuditCorpus,
    n: int,
    strategy: str = "random",
    *,
    dimension: str = "composite",
    edge_low: float = 0.40,
    edge_high: float = 0.50,
    proportional: bool = True,
    seed: Optional[int] = None,
) -> List[int]:
    """Select event indices for human annotation via stratified sampling.

    Supports multiple stratification strategies to ensure annotated
    samples are representative of the corpus structure.

    Args:
        corpus: AuditCorpus to sample from.
        n: Number of events to sample. Capped at corpus size.
        strategy: Sampling strategy:
            - "random": Simple random sample.
            - "verdict": Stratify by verdict category.
            - "tool": Stratify by tool_call type.
            - "quartile": Stratify by score quartile of `dimension`.
            - "edge": Sample events near decision boundaries
              (composite between edge_low and edge_high).
        dimension: Fidelity dimension for quartile/edge strategies
            (default: "composite").
        edge_low: Lower bound for edge-case sampling (default: 0.40).
        edge_high: Upper bound for edge-case sampling (default: 0.50).
        proportional: If True, stratified samples are proportional to
            stratum size. If False, equal allocation per stratum.
        seed: Random seed for reproducibility. None = non-deterministic.

    Returns:
        Sorted list of integer indices into corpus.events.

    Raises:
        ValueError: If strategy is unrecognized or n <= 0.
        ValueError: If dimension is not a valid fidelity dimension.
    """
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")

    total = len(corpus)
    if total == 0:
        return []

    n = min(n, total)
    rng = random.Random(seed)

    if strategy == "random":
        return sorted(rng.sample(range(total), n))

    elif strategy == "verdict":
        return _stratified_sample(
            corpus, n, rng,
            key_fn=lambda e: e.verdict,
            proportional=proportional,
        )

    elif strategy == "tool":
        return _stratified_sample(
            corpus, n, rng,
            key_fn=lambda e: e.tool_call,
            proportional=proportional,
        )

    elif strategy == "quartile":
        if dimension not in DIMENSIONS:
            raise ValueError(
                f"Unknown dimension '{dimension}'. "
                f"Valid: {', '.join(DIMENSIONS)}"
            )
        # Compute quartile boundaries
        values = [getattr(e, dimension) for e in corpus.events]
        sorted_vals = sorted(values)
        q25 = _percentile(sorted_vals, 0.25)
        q50 = _percentile(sorted_vals, 0.50)
        q75 = _percentile(sorted_vals, 0.75)

        def quartile_label(e):
            v = getattr(e, dimension)
            if v <= q25:
                return "Q1"
            elif v <= q50:
                return "Q2"
            elif v <= q75:
                return "Q3"
            else:
                return "Q4"

        return _stratified_sample(
            corpus, n, rng,
            key_fn=quartile_label,
            proportional=proportional,
        )

    elif strategy == "edge":
        if dimension not in DIMENSIONS:
            raise ValueError(
                f"Unknown dimension '{dimension}'. "
                f"Valid: {', '.join(DIMENSIONS)}"
            )
        # Find events in the boundary zone
        edge_indices = [
            i for i, e in enumerate(corpus.events)
            if edge_low <= getattr(e, dimension) <= edge_high
        ]
        if not edge_indices:
            # Fall back to random if no edge cases found
            return sorted(rng.sample(range(total), n))

        n_edge = min(n, len(edge_indices))
        return sorted(rng.sample(edge_indices, n_edge))

    else:
        raise ValueError(
            f"Unknown strategy '{strategy}'. "
            f"Valid: random, verdict, tool, quartile, edge"
        )


def _stratified_sample(
    corpus: AuditCorpus,
    n: int,
    rng: random.Random,
    key_fn,
    proportional: bool,
) -> List[int]:
    """Internal: stratified sampling by an arbitrary key function.

    Groups events by key_fn(event), then allocates n samples across
    strata either proportionally or equally.
    """
    total = len(corpus)

    # Build strata: {key: [indices]}
    strata: Dict[str, List[int]] = defaultdict(list)
    for i, event in enumerate(corpus.events):
        strata[key_fn(event)].append(i)

    n_strata = len(strata)
    if n_strata == 0:
        return []

    # Compute allocation per stratum
    if proportional:
        # Proportional allocation -- each stratum gets floor(n * |stratum|/total)
        allocations: Dict[str, int] = {}
        allocated = 0
        for key, indices in strata.items():
            alloc = int(n * len(indices) / total)
            # Ensure at least 1 per stratum if possible
            alloc = max(1, alloc) if n >= n_strata else alloc
            alloc = min(alloc, len(indices))
            allocations[key] = alloc
            allocated += alloc

        # Distribute remainder by stratum size (largest first)
        remainder = n - allocated
        if remainder > 0:
            sorted_keys = sorted(
                strata.keys(),
                key=lambda k: len(strata[k]),
                reverse=True,
            )
            for key in sorted_keys:
                if remainder <= 0:
                    break
                headroom = len(strata[key]) - allocations[key]
                if headroom > 0:
                    add = min(remainder, headroom)
                    allocations[key] += add
                    remainder -= add
    else:
        # Equal allocation -- each stratum gets floor(n / n_strata)
        base = n // n_strata
        extra = n % n_strata
        allocations = {}
        for i, key in enumerate(sorted(strata.keys())):
            alloc = base + (1 if i < extra else 0)
            alloc = min(alloc, len(strata[key]))
            allocations[key] = alloc

    # Sample from each stratum
    selected: List[int] = []
    for key, indices in strata.items():
        k = allocations.get(key, 0)
        if k > 0:
            selected.extend(rng.sample(indices, k))

    return sorted(selected)


def _percentile(sorted_vals: List[float], p: float) -> float:
    """Compute percentile from a sorted list (linear interpolation)."""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


# ---------------------------------------------------------------------------
# Annotation schema
# ---------------------------------------------------------------------------

@dataclass
class AnnotationRecord:
    """A single human annotation of a governance event.

    Represents what a trained rater believes the verdict SHOULD be,
    independent of what the system produced. Used for calibration:
    comparing system verdicts against human ground truth.

    Attributes:
        event_index: Index into the corpus.events list.
        event_id: Unique event identifier (for cross-referencing).
        annotator_id: Anonymized rater identifier (e.g., "rater_1").
        ground_truth_verdict: Human judgment -- what the verdict SHOULD be.
            Must be one of EXECUTE, CLARIFY, INERT, ESCALATE.
        confidence: Annotator's confidence in their judgment (0.0 - 1.0).
        notes: Optional free-text rationale or observations.
        timestamp: ISO 8601 timestamp when annotation was recorded.
        annotation_round: Round number for multi-round annotation (1-indexed).
    """
    event_index: int
    event_id: str
    annotator_id: str
    ground_truth_verdict: str
    confidence: float
    notes: str = ""
    timestamp: str = ""
    annotation_round: int = 1

    def __post_init__(self):
        """Validate fields and set defaults."""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

        if self.ground_truth_verdict.upper() not in ANNOTATION_VERDICTS:
            raise ValueError(
                f"Invalid ground_truth_verdict '{self.ground_truth_verdict}'. "
                f"Must be one of: {', '.join(sorted(ANNOTATION_VERDICTS))}"
            )
        self.ground_truth_verdict = self.ground_truth_verdict.upper()

        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

        if self.annotation_round < 1:
            raise ValueError(
                f"annotation_round must be >= 1, got {self.annotation_round}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSONL export."""
        return {
            "event_index": self.event_index,
            "event_id": self.event_id,
            "annotator_id": self.annotator_id,
            "ground_truth_verdict": self.ground_truth_verdict,
            "confidence": self.confidence,
            "notes": self.notes,
            "timestamp": self.timestamp,
            "annotation_round": self.annotation_round,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AnnotationRecord":
        """Deserialize from dictionary. Validates all fields."""
        required = {
            "event_index", "event_id", "annotator_id",
            "ground_truth_verdict", "confidence",
        }
        missing = required - set(d.keys())
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        return cls(
            event_index=int(d["event_index"]),
            event_id=str(d["event_id"]),
            annotator_id=str(d["annotator_id"]),
            ground_truth_verdict=str(d["ground_truth_verdict"]),
            confidence=float(d["confidence"]),
            notes=str(d.get("notes", "")),
            timestamp=str(d.get("timestamp", "")),
            annotation_round=int(d.get("annotation_round", 1)),
        )


# ---------------------------------------------------------------------------
# Inter-rater reliability
# ---------------------------------------------------------------------------

@dataclass
class IRRResult:
    """Inter-rater reliability metrics for annotation quality.

    Krippendorff's alpha is the primary metric -- it handles
    missing data, multiple raters, and nominal/ordinal data.
    Cohen's kappa is provided for pairwise comparisons when
    exactly two raters are involved.

    Interpretation thresholds (Krippendorff, 2011):
      alpha >= 0.80: Reliable for drawing conclusions
      0.67 <= alpha < 0.80: Acceptable for exploratory research
      alpha < 0.67: Needs discussion, annotation guidelines may need revision
    """
    n_events_annotated: int
    n_raters: int
    rater_ids: List[str]
    n_annotations: int

    # Krippendorff's alpha (all raters, nominal data)
    krippendorff_alpha: float
    alpha_interpretation: str

    # Percent agreement (all raters)
    percent_agreement: float

    # Pairwise Cohen's kappa (only when 2+ raters)
    pairwise_kappa: Dict[str, float]  # {("rater_1", "rater_2"): kappa}

    # Per-verdict agreement rates
    per_verdict_agreement: Dict[str, float]

    def format(self) -> str:
        """Format as human-readable IRR report."""
        lines = [
            "Inter-Rater Reliability Report",
            "=" * 50,
            f"  Annotations:  {self.n_annotations}",
            f"  Events:       {self.n_events_annotated}",
            f"  Raters:       {self.n_raters} ({', '.join(self.rater_ids)})",
            "",
            "  Primary Metric:",
            f"    Krippendorff's alpha: {self.krippendorff_alpha:.3f}"
            f"  [{self.alpha_interpretation}]",
            "",
            f"  Percent Agreement:      {self.percent_agreement:.1%}",
        ]

        if self.pairwise_kappa:
            lines.append("")
            lines.append("  Pairwise Cohen's Kappa:")
            for pair, kappa in sorted(self.pairwise_kappa.items()):
                lines.append(f"    {pair}: {kappa:.3f}")

        if self.per_verdict_agreement:
            lines.append("")
            lines.append("  Per-Verdict Agreement:")
            for v in VERDICT_ORDER:
                if v in self.per_verdict_agreement:
                    rate = self.per_verdict_agreement[v]
                    lines.append(f"    {v:<12} {rate:.1%}")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Serialize for JSON output."""
        return {
            "n_events_annotated": self.n_events_annotated,
            "n_raters": self.n_raters,
            "rater_ids": self.rater_ids,
            "n_annotations": self.n_annotations,
            "krippendorff_alpha": self.krippendorff_alpha,
            "alpha_interpretation": self.alpha_interpretation,
            "percent_agreement": self.percent_agreement,
            "pairwise_kappa": self.pairwise_kappa,
            "per_verdict_agreement": self.per_verdict_agreement,
        }


def compute_irr(annotations: List[AnnotationRecord]) -> IRRResult:
    """Compute inter-rater reliability from human annotations.

    Requires at least 2 raters and at least 1 event annotated by
    multiple raters. Computes:
      - Krippendorff's alpha for nominal data (all raters)
      - Cohen's kappa for each pair of raters
      - Percent agreement (fraction of events where all raters agree)
      - Per-verdict agreement rates

    Args:
        annotations: List of AnnotationRecord from multiple raters.

    Returns:
        IRRResult with all reliability metrics.

    Raises:
        ValueError: If fewer than 2 raters found.
        ValueError: If no events have multiple annotations.
    """
    # Group by rater
    rater_ids = sorted(set(a.annotator_id for a in annotations))
    if len(rater_ids) < 2:
        raise ValueError(
            f"IRR requires at least 2 raters, found {len(rater_ids)}: "
            f"{rater_ids}"
        )

    # Build rater-event matrix: {event_id: {rater_id: verdict}}
    matrix: Dict[str, Dict[str, str]] = defaultdict(dict)
    for a in annotations:
        matrix[a.event_id][a.annotator_id] = a.ground_truth_verdict

    # Filter to events with at least 2 raters
    multi_rated = {
        eid: raters for eid, raters in matrix.items()
        if len(raters) >= 2
    }
    if not multi_rated:
        raise ValueError(
            "No events have annotations from multiple raters. "
            "IRR requires overlapping annotations."
        )

    # Collect all verdict categories used
    all_verdicts = sorted(set(
        v for raters in multi_rated.values() for v in raters.values()
    ))

    # --- Krippendorff's alpha (nominal) ---
    alpha = _krippendorff_alpha_nominal(multi_rated, rater_ids, all_verdicts)
    alpha_interp = _interpret_alpha(alpha)

    # --- Percent agreement (all raters agree on same verdict) ---
    n_agree = 0
    for eid, raters in multi_rated.items():
        verdicts = list(raters.values())
        if len(set(verdicts)) == 1:
            n_agree += 1
    pct_agreement = n_agree / len(multi_rated) if multi_rated else 0.0

    # --- Pairwise Cohen's kappa ---
    pairwise_kappa: Dict[str, float] = {}
    for i, r1 in enumerate(rater_ids):
        for r2 in rater_ids[i + 1:]:
            # Find events rated by both r1 and r2
            common_eids = [
                eid for eid, raters in multi_rated.items()
                if r1 in raters and r2 in raters
            ]
            if len(common_eids) >= 2:
                labels_1 = [multi_rated[eid][r1] for eid in common_eids]
                labels_2 = [multi_rated[eid][r2] for eid in common_eids]
                kappa = _cohens_kappa(labels_1, labels_2)
                pair_key = f"{r1} vs {r2}"
                pairwise_kappa[pair_key] = kappa

    # --- Per-verdict agreement ---
    per_verdict: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))
    for eid, raters in multi_rated.items():
        verdicts = list(raters.values())
        unanimous = len(set(verdicts)) == 1
        # Count each verdict's presence
        for v in set(verdicts):
            agree_count, total_count = per_verdict[v]
            per_verdict[v] = (
                agree_count + (1 if unanimous and verdicts[0] == v else 0),
                total_count + 1,
            )

    per_verdict_rates: Dict[str, float] = {}
    for v, (agree, total) in per_verdict.items():
        if total > 0:
            per_verdict_rates[v] = agree / total

    return IRRResult(
        n_events_annotated=len(multi_rated),
        n_raters=len(rater_ids),
        rater_ids=rater_ids,
        n_annotations=len(annotations),
        krippendorff_alpha=alpha,
        alpha_interpretation=alpha_interp,
        percent_agreement=pct_agreement,
        pairwise_kappa=pairwise_kappa,
        per_verdict_agreement=per_verdict_rates,
    )


def _interpret_alpha(alpha: float) -> str:
    """Interpret Krippendorff's alpha value."""
    if alpha >= 0.80:
        return "reliable"
    elif alpha >= 0.67:
        return "acceptable"
    else:
        return "needs discussion"


def _krippendorff_alpha_nominal(
    data: Dict[str, Dict[str, str]],
    rater_ids: List[str],
    categories: List[str],
) -> float:
    """Compute Krippendorff's alpha for nominal data.

    Self-contained implementation -- no external dependencies beyond
    stdlib. Follows the coincidence matrix formulation from
    Krippendorff (2011) "Computing Krippendorff's Alpha-Reliability".

    The algorithm:
    1. Build a coincidence matrix from all rater pairs within each unit.
    2. Compute observed disagreement (D_o) from the coincidence matrix.
    3. Compute expected disagreement (D_e) from marginal frequencies.
    4. alpha = 1 - D_o / D_e

    Args:
        data: {event_id: {rater_id: verdict}} -- only events with 2+ raters.
        rater_ids: List of all rater identifiers.
        categories: List of all verdict categories.

    Returns:
        Krippendorff's alpha coefficient. Range typically [-1, 1],
        where 1 = perfect agreement, 0 = chance agreement, < 0 = worse
        than chance.
    """
    # Map categories to indices
    cat_to_idx = {c: i for i, c in enumerate(categories)}
    n_cats = len(categories)

    # Build coincidence matrix
    # o[c][k] = number of c-k coincidences across all units
    coincidence = [[0.0] * n_cats for _ in range(n_cats)]

    # Also track total pairable values
    total_pairable = 0.0

    for eid, raters in data.items():
        # Get all assigned values for this unit
        values = list(raters.values())
        m_u = len(values)  # number of raters for this unit
        if m_u < 2:
            continue

        # For each pair of values assigned to this unit
        value_counts = Counter(values)
        for c_val, n_c in value_counts.items():
            c = cat_to_idx[c_val]
            for k_val, n_k in value_counts.items():
                k = cat_to_idx[k_val]
                if c == k:
                    # Same category: n_c * (n_c - 1) / (m_u - 1)
                    coincidence[c][k] += n_c * (n_c - 1) / (m_u - 1)
                else:
                    # Different categories: n_c * n_k / (m_u - 1)
                    coincidence[c][k] += n_c * n_k / (m_u - 1)

        total_pairable += m_u

    # Marginals: n_c = sum of row c (or column c, matrix is symmetric)
    marginals = [sum(coincidence[c]) for c in range(n_cats)]
    n_total = sum(marginals)

    if n_total == 0:
        return 0.0

    # Observed disagreement: D_o = 1 - (sum of diagonal / n_total)
    diagonal_sum = sum(coincidence[c][c] for c in range(n_cats))
    d_observed = 1.0 - (diagonal_sum / n_total)

    # Expected disagreement: D_e = 1 - sum(n_c * (n_c - 1)) / (n_total * (n_total - 1))
    if n_total <= 1:
        return 0.0

    marginal_product_sum = sum(m * (m - 1) for m in marginals)
    d_expected = 1.0 - marginal_product_sum / (n_total * (n_total - 1))

    if d_expected == 0:
        # Perfect agreement on everything (or degenerate data)
        return 1.0 if d_observed == 0 else 0.0

    alpha = 1.0 - d_observed / d_expected
    return alpha


def _cohens_kappa(labels_1: List[str], labels_2: List[str]) -> float:
    """Compute Cohen's kappa for two raters on the same set of items.

    Args:
        labels_1: Verdicts from rater 1 (same length as labels_2).
        labels_2: Verdicts from rater 2 (same length as labels_1).

    Returns:
        Cohen's kappa coefficient. 1 = perfect, 0 = chance, < 0 = worse.
    """
    n = len(labels_1)
    if n == 0:
        return 0.0

    assert len(labels_1) == len(labels_2), "Label lists must be same length"

    # All categories
    categories = sorted(set(labels_1) | set(labels_2))
    cat_to_idx = {c: i for i, c in enumerate(categories)}
    n_cats = len(categories)

    # Build confusion matrix
    conf = [[0] * n_cats for _ in range(n_cats)]
    for l1, l2 in zip(labels_1, labels_2):
        conf[cat_to_idx[l1]][cat_to_idx[l2]] += 1

    # Observed agreement
    p_o = sum(conf[i][i] for i in range(n_cats)) / n

    # Expected agreement (product of marginals)
    row_sums = [sum(conf[i]) for i in range(n_cats)]
    col_sums = [sum(conf[i][j] for i in range(n_cats)) for j in range(n_cats)]
    p_e = sum(row_sums[i] * col_sums[i] for i in range(n_cats)) / (n * n)

    if p_e == 1.0:
        return 1.0 if p_o == 1.0 else 0.0

    return (p_o - p_e) / (1.0 - p_e)


# ---------------------------------------------------------------------------
# Calibration comparison (system vs human)
# ---------------------------------------------------------------------------

@dataclass
class PerVerdictMetrics:
    """Precision, recall, and F1 for a single verdict category."""
    verdict: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    support: int  # number of human-labeled instances of this verdict

    def format(self) -> str:
        return (
            f"    {self.verdict:<12} "
            f"P={self.precision:.3f}  R={self.recall:.3f}  "
            f"F1={self.f1:.3f}  "
            f"(TP={self.true_positives}, FP={self.false_positives}, "
            f"FN={self.false_negatives}, support={self.support})"
        )


@dataclass
class SystematicDisagreement:
    """A pattern of systematic disagreement between system and humans.

    Identifies cases where the system consistently produces verdict X
    when humans believe the correct verdict is Y.
    """
    system_verdict: str
    human_verdict: str
    count: int
    total_human_for_this_verdict: int
    rate: float  # count / total_human_for_this_verdict
    description: str

    def format(self) -> str:
        return (
            f"    {self.description} "
            f"(n={self.count}, {self.rate:.0%} of human-{self.human_verdict})"
        )


@dataclass
class CalibrationResult:
    """Result of comparing system verdicts to human ground truth.

    The confusion matrix shows system verdicts (rows) vs human verdicts
    (columns). Precision/recall are computed treating human labels as
    ground truth.
    """
    n_compared: int
    n_ties_excluded: int  # events excluded due to tied majority vote
    overall_accuracy: float  # fraction where system == human

    # Confusion matrix: confusion[system_verdict][human_verdict] = count
    confusion_matrix: Dict[str, Dict[str, int]]
    confusion_labels: List[str]  # ordered verdict labels

    # Per-verdict metrics
    per_verdict: List[PerVerdictMetrics]

    # Macro-averaged metrics
    macro_precision: float
    macro_recall: float
    macro_f1: float

    # Systematic disagreements
    disagreements: List[SystematicDisagreement]

    def format(self) -> str:
        """Format as human-readable calibration report."""
        lines = [
            "Calibration Report: System vs Human Ground Truth",
            "=" * 50,
            f"  Events compared: {self.n_compared}",
        ]
        if self.n_ties_excluded > 0:
            lines.append(
                f"  Ties excluded:   {self.n_ties_excluded}"
                f"  (no majority -- raters disagreed equally)"
            )
        lines.extend([
            f"  Overall accuracy: {self.overall_accuracy:.1%}",
            f"  Macro P/R/F1: {self.macro_precision:.3f} / "
            f"{self.macro_recall:.3f} / {self.macro_f1:.3f}",
        ])

        # Confusion matrix
        lines.append("")
        lines.append("  Confusion Matrix (rows=system, cols=human):")
        labels = self.confusion_labels
        # Header
        header = "    {:>12}".format("")
        for lbl in labels:
            header += f" {lbl[:6]:>6}"
        header += f" {'Total':>6}"
        lines.append(header)
        lines.append("    " + "-" * 12 + (" " + "-" * 6) * (len(labels) + 1))

        for sys_v in labels:
            row = f"    {sys_v:>12}"
            row_total = 0
            for hum_v in labels:
                count = self.confusion_matrix.get(sys_v, {}).get(hum_v, 0)
                row_total += count
                if count > 0:
                    row += f" {count:>6}"
                else:
                    row += f" {'--':>6}"
            row += f" {row_total:>6}"
            lines.append(row)

        # Per-verdict metrics
        lines.append("")
        lines.append("  Per-Verdict Metrics (human labels = ground truth):")
        for pv in self.per_verdict:
            lines.append(pv.format())

        # Systematic disagreements
        if self.disagreements:
            lines.append("")
            lines.append("  Systematic Disagreements:")
            for sd in self.disagreements:
                lines.append(sd.format())

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Serialize for JSON output."""
        return {
            "n_compared": self.n_compared,
            "n_ties_excluded": self.n_ties_excluded,
            "overall_accuracy": self.overall_accuracy,
            "confusion_matrix": self.confusion_matrix,
            "confusion_labels": self.confusion_labels,
            "per_verdict": [
                {
                    "verdict": pv.verdict,
                    "precision": pv.precision,
                    "recall": pv.recall,
                    "f1": pv.f1,
                    "true_positives": pv.true_positives,
                    "false_positives": pv.false_positives,
                    "false_negatives": pv.false_negatives,
                    "support": pv.support,
                }
                for pv in self.per_verdict
            ],
            "macro_precision": self.macro_precision,
            "macro_recall": self.macro_recall,
            "macro_f1": self.macro_f1,
            "disagreements": [
                {
                    "system_verdict": sd.system_verdict,
                    "human_verdict": sd.human_verdict,
                    "count": sd.count,
                    "rate": sd.rate,
                    "description": sd.description,
                }
                for sd in self.disagreements
            ],
        }


def compare_annotations_to_system(
    corpus: AuditCorpus,
    annotations: List[AnnotationRecord],
    *,
    use_majority: bool = True,
) -> CalibrationResult:
    """Compare human ground-truth annotations to system verdicts.

    For events with multiple annotators, uses majority vote (or first
    annotation if use_majority=False) as the human ground truth.

    Args:
        corpus: AuditCorpus containing system verdicts.
        annotations: List of AnnotationRecord from human raters.
        use_majority: If True, use majority vote when multiple raters
            annotated the same event. If False, use the first annotation.

    Returns:
        CalibrationResult with confusion matrix, per-verdict metrics,
        and systematic disagreement analysis.

    Raises:
        ValueError: If no annotations can be matched to corpus events.
    """
    # Build human ground truth per event
    # {event_id: [verdicts from all raters]}
    event_verdicts: Dict[str, List[str]] = defaultdict(list)
    for a in annotations:
        event_verdicts[a.event_id].append(a.ground_truth_verdict)

    # Resolve to single human verdict per event
    human_truth: Dict[str, str] = {}
    n_ties_excluded = 0
    for eid, verdicts in event_verdicts.items():
        if use_majority:
            # Majority vote with tie detection
            counter = Counter(verdicts)
            ranked = counter.most_common()
            # Tie: top two counts are equal (e.g., 2 raters each pick
            # a different verdict, or 4 raters split 2-2)
            if len(ranked) >= 2 and ranked[0][1] == ranked[1][1]:
                # No clear majority -- exclude from calibration
                n_ties_excluded += 1
                continue
            human_truth[eid] = ranked[0][0]
        else:
            human_truth[eid] = verdicts[0]

    # Match annotations to corpus events
    system_verdicts: Dict[str, str] = {}
    for event in corpus.events:
        if event.event_id in human_truth:
            system_verdicts[event.event_id] = event.verdict

    # Find matched events
    matched_eids = set(system_verdicts.keys()) & set(human_truth.keys())
    if not matched_eids:
        raise ValueError(
            "No annotations could be matched to corpus events. "
            "Check that event_id values match between annotations "
            "and corpus."
        )

    # Build paired lists
    pairs = [
        (system_verdicts[eid], human_truth[eid])
        for eid in sorted(matched_eids)
    ]

    n = len(pairs)

    # All verdict labels present in either system or human
    all_labels = sorted(set(
        v for pair in pairs for v in pair
    ))
    # Reorder to follow VERDICT_ORDER where possible
    ordered_labels = [v for v in VERDICT_ORDER if v in all_labels]
    for v in all_labels:
        if v not in ordered_labels:
            ordered_labels.append(v)

    # Overall accuracy
    correct = sum(1 for s, h in pairs if s == h)
    accuracy = correct / n if n > 0 else 0.0

    # Confusion matrix: conf[system][human] = count
    confusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for sys_v, hum_v in pairs:
        confusion[sys_v][hum_v] += 1

    # Convert to regular dict
    confusion_dict: Dict[str, Dict[str, int]] = {
        sv: dict(hv_counts) for sv, hv_counts in confusion.items()
    }

    # Per-verdict precision, recall, F1
    per_verdict_metrics: List[PerVerdictMetrics] = []
    precisions = []
    recalls = []

    for v in ordered_labels:
        tp = confusion.get(v, {}).get(v, 0)
        fp = sum(
            confusion.get(v, {}).get(hv, 0)
            for hv in ordered_labels if hv != v
        )
        fn = sum(
            confusion.get(sv, {}).get(v, 0)
            for sv in ordered_labels if sv != v
        )
        support = tp + fn  # total human-labeled as this verdict

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        per_verdict_metrics.append(PerVerdictMetrics(
            verdict=v,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1=f1,
            support=support,
        ))

        if support > 0:
            precisions.append(precision)
            recalls.append(recall)

    # Macro averages (over verdicts that have support)
    macro_p = sum(precisions) / len(precisions) if precisions else 0.0
    macro_r = sum(recalls) / len(recalls) if recalls else 0.0
    macro_f1 = (
        2 * macro_p * macro_r / (macro_p + macro_r)
        if (macro_p + macro_r) > 0
        else 0.0
    )

    # Systematic disagreements
    # Look for cells where system frequently gives verdict X
    # when humans say Y (off-diagonal cells with count >= 3 or rate >= 10%)
    disagreements: List[SystematicDisagreement] = []
    for sys_v in ordered_labels:
        for hum_v in ordered_labels:
            if sys_v == hum_v:
                continue
            count = confusion.get(sys_v, {}).get(hum_v, 0)
            if count == 0:
                continue

            # Total times humans labeled this verdict
            total_human = sum(
                confusion.get(sv, {}).get(hum_v, 0)
                for sv in ordered_labels
            )
            rate = count / total_human if total_human > 0 else 0.0

            # Report if count >= 3 or rate >= 10%
            if count >= 3 or rate >= 0.10:
                # Generate a descriptive sentence
                desc = (
                    f"System {sys_v}s what humans would {hum_v}"
                )
                disagreements.append(SystematicDisagreement(
                    system_verdict=sys_v,
                    human_verdict=hum_v,
                    count=count,
                    total_human_for_this_verdict=total_human,
                    rate=rate,
                    description=desc,
                ))

    # Sort disagreements by count descending
    disagreements.sort(key=lambda d: -d.count)

    return CalibrationResult(
        n_compared=n,
        n_ties_excluded=n_ties_excluded,
        overall_accuracy=accuracy,
        confusion_matrix=confusion_dict,
        confusion_labels=ordered_labels,
        per_verdict=per_verdict_metrics,
        macro_precision=macro_p,
        macro_recall=macro_r,
        macro_f1=macro_f1,
        disagreements=disagreements,
    )


# ---------------------------------------------------------------------------
# Export / Import (JSONL)
# ---------------------------------------------------------------------------

def export_annotations(
    annotations: List[AnnotationRecord],
    path: str,
) -> int:
    """Export annotations to JSONL file.

    One annotation per line. Validates export path using guardrails.

    Args:
        annotations: List of AnnotationRecord to export.
        path: Output file path (.jsonl).

    Returns:
        Number of annotations written.

    Raises:
        ValueError: If export path is invalid (guardrails check).
    """
    valid, reason = validate_export_path(path)
    if not valid:
        raise ValueError(f"Export path rejected: {reason}")

    # Ensure parent directory exists
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

    with open(path, "w") as f:
        for a in annotations:
            f.write(json.dumps(a.to_dict(), default=str) + "\n")

    return len(annotations)


def load_annotations(path: str) -> List[AnnotationRecord]:
    """Load annotations from JSONL file.

    Validates each record against the AnnotationRecord schema on load.
    Invalid records are skipped with a warning printed to stderr.

    Args:
        path: Path to JSONL file containing annotations.

    Returns:
        List of validated AnnotationRecord objects.

    Raises:
        FileNotFoundError: If path does not exist.
    """
    resolved = os.path.expanduser(path)
    if not os.path.exists(resolved):
        raise FileNotFoundError(f"Annotation file not found: {resolved}")

    annotations = []
    errors = 0
    with open(resolved, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                annotation = AnnotationRecord.from_dict(record)
                annotations.append(annotation)
            except (json.JSONDecodeError, ValueError, KeyError) as exc:
                errors += 1
                if errors <= 5:
                    import sys
                    print(
                        f"Warning: annotation parse error at line {line_num}: "
                        f"{exc}",
                        file=sys.stderr,
                    )

    if errors > 5:
        import sys
        print(
            f"Warning: {errors} total parse errors in {resolved}",
            file=sys.stderr,
        )

    return annotations


# ---------------------------------------------------------------------------
# Annotation worksheet (CSV)
# ---------------------------------------------------------------------------

def generate_worksheet(
    corpus: AuditCorpus,
    indices: List[int],
    path: str,
    *,
    include_context: bool = False,
) -> int:
    """Generate a CSV annotation worksheet for offline human labeling.

    Exports Zone 1 data only (scores, verdicts, tool names) with blank
    columns for the annotator to fill in. Zone 2/3 content (request_text,
    explanation, tool_args) is stripped by default for blind annotation.

    Args:
        corpus: AuditCorpus containing the events.
        indices: List of event indices to include in the worksheet.
        path: Output CSV file path.
        include_context: If True, include redacted Zone 2 fields
            (request_text, explanation). Default False for blind coding.

    Returns:
        Number of rows written.

    Raises:
        ValueError: If export path is invalid.
        IndexError: If any index is out of range.
    """
    valid, reason = validate_export_path(path)
    if not valid:
        raise ValueError(f"Export path rejected: {reason}")

    total = len(corpus)
    for idx in indices:
        if not (0 <= idx < total):
            raise IndexError(
                f"Index {idx} out of range (corpus has {total} events)"
            )

    # Ensure parent directory exists
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

    # Define columns
    columns = [
        "event_index",
        "event_id",
        "tool_call",
        "composite_score",
        "purpose_score",
        "scope_score",
        "boundary_score",
        "tool_score",
        "chain_score",
    ]

    # system_verdict is only included when include_context=True.
    # In blind coding mode (include_context=False), showing the system
    # verdict anchors annotators and inflates calibration accuracy.
    if include_context:
        columns.append("system_verdict")
        columns.extend(["request_text_redacted", "explanation_redacted"])

    # Blank columns for annotator
    columns.extend([
        "annotator_id",
        "ground_truth_verdict",
        "confidence",
        "notes",
    ])

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)

        for idx in sorted(indices):
            event = corpus.events[idx]

            row = [
                idx,
                event.event_id,
                event.tool_call,
                f"{event.composite:.3f}",
                f"{event.purpose:.3f}",
                f"{event.scope:.3f}",
                f"{event.boundary:.3f}",
                f"{event.tool:.3f}",
                f"{event.chain:.3f}",
            ]

            if include_context:
                row.append(event.verdict)
                row.append(redact_text(event.request_text, level=3))
                row.append(redact_text(event.explanation, level=2))

            # Blank columns for annotator to fill
            row.extend(["", "", "", ""])

            writer.writerow(row)

    return len(indices)

"""
Counterfactual Re-Scoring Engine
=================================

Fast counterfactual analysis: reapply the governance decision ladder to
recorded per-dimension fidelity scores with different ThresholdConfig
parameters. No embedding model needed — operates purely on stored scores.

This is the core counterfactual mechanism for TELOSCOPE. It answers:
"What WOULD have happened if the thresholds/weights were different?"

Methodological basis: Sensitivity analysis (Saltelli et al., 2004) —
systematically varying input parameters to observe output changes.

Usage:
    from telos_governance.corpus import load_corpus
    from telos_governance.rescore import rescore

    corpus = load_corpus("~/.telos/posthoc_audit/")

    # What if we raised the execute threshold?
    result = rescore(corpus, st_execute=0.55)
    print(result.summary_table())

    # What if we changed the composite weights?
    result = rescore(corpus, weight_purpose=0.45, weight_scope=0.15)
    print(result.migration_table())
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# When deployed to telos_governance/:
#   from telos_governance.threshold_config import ThresholdConfig
#   from telos_governance.corpus import AuditCorpus, AuditEvent
# For local development, use relative imports or sys.path manipulation.
# The deploy script will fix these.
try:
    from telos_governance.threshold_config import ThresholdConfig
    from telos_governance.corpus import AuditCorpus, AuditEvent
except ImportError:
    from threshold_config import ThresholdConfig
    from corpus import AuditCorpus, AuditEvent


# Production defaults — must match agentic_fidelity.py exactly
_DEFAULT_WEIGHTS = {
    "weight_purpose": 0.35,
    "weight_scope": 0.20,
    "weight_tool": 0.20,
    "weight_chain": 0.15,
    "weight_boundary_penalty": 0.10,
}

# Verdicts in severity order (for migration analysis)
VERDICT_ORDER = ["EXECUTE", "CLARIFY", "INERT", "ESCALATE"]


def _compute_composite(
    event: "AuditEvent",
    weight_purpose: float,
    weight_scope: float,
    weight_tool: float,
    weight_chain: float,
    weight_boundary_penalty: float,
) -> float:
    """Recompute composite fidelity from stored per-dimension scores.

    Replicates the formula from agentic_fidelity.py lines 438-448:
        composite = w_purpose*purpose + w_scope*scope + w_tool*tool
                    + w_chain*chain - w_boundary*boundary

    Note: SetFit boost (+0.15) is NOT applied here because we don't have
    the SetFit legitimacy score stored in the audit JSONL. The composite
    in the original record already includes the boost if it was active.
    This is a known limitation — document it clearly.

    Note: Chain inheritance (effective fidelity from previous step) is NOT
    applied here because it requires sequential processing with state.
    Use rescore_with_chain() for chain-aware counterfactuals.
    """
    composite = (
        weight_purpose * event.purpose
        + weight_scope * event.scope
        + weight_tool * event.tool
        + weight_chain * event.chain
        - weight_boundary_penalty * event.boundary
    )
    return float(max(0.0, min(1.0, composite)))


def _apply_decision_ladder(
    effective_fidelity: float,
    boundary_triggered: bool,
    st_execute: float,
    st_clarify: float,
    escalation_threshold: float = 0.15,
) -> str:
    """Apply the governance decision ladder to a fidelity score.

    Replicates the logic from agentic_fidelity.py:
        1. boundary_triggered → ESCALATE (hard override)
        2. effective >= st_execute → EXECUTE
        3. effective >= st_clarify → CLARIFY
        4. effective < escalation_threshold → ESCALATE
        5. else → INERT

    Note: tool_blocked and chain_broken hard overrides are not replicated
    here because we don't have those signals in the stored audit data.
    The original verdict already reflects those overrides. For pure
    threshold counterfactuals, this is correct — we're asking "what if
    the THRESHOLDS were different", not "what if the tool wasn't blocked".
    """
    if boundary_triggered:
        return "ESCALATE"

    if effective_fidelity >= st_execute:
        return "EXECUTE"
    elif effective_fidelity >= st_clarify:
        return "CLARIFY"
    elif effective_fidelity < escalation_threshold:
        return "ESCALATE"
    else:
        return "INERT"


@dataclass
class RescoreResult:
    """Result of a counterfactual re-scoring run.

    Contains the original and new verdicts for every event, plus
    summary statistics and migration analysis.
    """
    corpus: "AuditCorpus"
    config: "ThresholdConfig"
    original_verdicts: List[str]
    new_verdicts: List[str]
    new_composites: List[float]
    changed_indices: List[int]

    @property
    def n_changed(self) -> int:
        return len(self.changed_indices)

    @property
    def n_total(self) -> int:
        return len(self.original_verdicts)

    @property
    def change_rate(self) -> float:
        if self.n_total == 0:
            return 0.0
        return self.n_changed / self.n_total

    def migration_table(self) -> Dict[str, Dict[str, int]]:
        """Build verdict migration matrix.

        Returns dict of {original_verdict: {new_verdict: count}}.
        This is the core counterfactual output — shows how verdicts
        shift under the new configuration.

        Example:
            {
                "ESCALATE": {"EXECUTE": 12, "CLARIFY": 5, "ESCALATE": 83},
                "EXECUTE":  {"EXECUTE": 40, "CLARIFY": 2},
                ...
            }
        """
        migration: Dict[str, Dict[str, int]] = {}
        for orig, new in zip(self.original_verdicts, self.new_verdicts):
            if orig not in migration:
                migration[orig] = {}
            migration[orig][new] = migration[orig].get(new, 0) + 1
        return migration

    def summary(self) -> Dict:
        """Compute summary statistics for the rescore run.

        Returns dict with: n_total, n_changed, change_rate,
        original_distribution, new_distribution, migration,
        config_diff (parameters that differ from defaults).
        """
        orig_dist: Dict[str, int] = {}
        new_dist: Dict[str, int] = {}
        for v in self.original_verdicts:
            orig_dist[v] = orig_dist.get(v, 0) + 1
        for v in self.new_verdicts:
            new_dist[v] = new_dist.get(v, 0) + 1

        # Identify which config params differ from defaults
        defaults = ThresholdConfig()
        config_diff = {}
        for param, default_val in defaults.to_dict().items():
            current_val = getattr(self.config, param)
            if abs(current_val - default_val) > 1e-6:
                config_diff[param] = {
                    "default": default_val,
                    "trial": current_val,
                }

        return {
            "n_total": self.n_total,
            "n_changed": self.n_changed,
            "change_rate": self.change_rate,
            "original_distribution": dict(sorted(orig_dist.items())),
            "new_distribution": dict(sorted(new_dist.items())),
            "migration": self.migration_table(),
            "config_diff": config_diff,
        }

    def summary_table(self) -> str:
        """Format rescore summary as a human-readable table."""
        s = self.summary()
        if s["n_total"] == 0:
            return "Empty corpus (0 events)"

        lines = [
            "Counterfactual Re-Score Summary",
            "=" * 31,
            f"Events:   {s['n_total']}",
            f"Changed:  {s['n_changed']} ({s['change_rate']:.1%})",
        ]

        if s["config_diff"]:
            lines.append("")
            lines.append("Parameter Changes:")
            for param, vals in s["config_diff"].items():
                lines.append(
                    f"  {param}: {vals['default']:.3f} -> {vals['trial']:.3f}"
                )

        lines.append("")
        lines.append("Verdict Distribution:")
        lines.append(f"  {'Verdict':<12} {'Original':>8} {'New':>8} {'Delta':>8}")
        lines.append(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8}")
        for v in VERDICT_ORDER:
            orig_n = s["original_distribution"].get(v, 0)
            new_n = s["new_distribution"].get(v, 0)
            delta = new_n - orig_n
            sign = "+" if delta > 0 else ""
            lines.append(f"  {v:<12} {orig_n:>8} {new_n:>8} {sign}{delta:>7}")

        lines.append("")
        lines.append("Migration Matrix:")
        # Header row
        from_to = 'From \\ To'
        header = f"  {from_to:<12}"
        for v in VERDICT_ORDER:
            header += f" {v[:4]:>6}"
        lines.append(header)
        lines.append(f"  {'-'*12}" + " ------" * len(VERDICT_ORDER))
        # Data rows
        migration = s["migration"]
        for orig_v in VERDICT_ORDER:
            if orig_v not in migration:
                continue
            row = f"  {orig_v:<12}"
            for new_v in VERDICT_ORDER:
                count = migration[orig_v].get(new_v, 0)
                if count > 0:
                    row += f" {count:>6}"
                else:
                    row += f" {'·':>6}"
            lines.append(row)

        return "\n".join(lines)

    def changed_events(self) -> List[Tuple["AuditEvent", str, str, float]]:
        """Return events whose verdict changed, with old/new verdict and new composite.

        Returns list of (event, original_verdict, new_verdict, new_composite).
        Useful for inspecting what specifically shifted.
        """
        results = []
        for idx in self.changed_indices:
            results.append((
                self.corpus.events[idx],
                self.original_verdicts[idx],
                self.new_verdicts[idx],
                self.new_composites[idx],
            ))
        return results

    def accuracy(self, ground_truth: Dict[str, str]) -> Dict:
        """Compute accuracy metrics against ground truth labels.

        Args:
            ground_truth: Dict mapping event_id -> expected verdict.
                Only events present in ground_truth are evaluated.

        Returns:
            Dict with: n_evaluated, accuracy, per_verdict_accuracy,
            confusion_matrix.
        """
        correct = 0
        total = 0
        per_verdict: Dict[str, Dict[str, int]] = {}  # {expected: {predicted: count}}

        for i, event in enumerate(self.corpus.events):
            if event.event_id not in ground_truth:
                continue
            expected = ground_truth[event.event_id]
            predicted = self.new_verdicts[i]
            total += 1
            if predicted == expected:
                correct += 1
            if expected not in per_verdict:
                per_verdict[expected] = {}
            per_verdict[expected][predicted] = per_verdict[expected].get(predicted, 0) + 1

        if total == 0:
            return {"n_evaluated": 0, "accuracy": 0.0}

        return {
            "n_evaluated": total,
            "accuracy": correct / total,
            "confusion_matrix": per_verdict,
        }


def rescore(
    corpus: "AuditCorpus",
    config: Optional["ThresholdConfig"] = None,
    *,
    # Convenience kwargs — override individual ThresholdConfig params
    st_execute: Optional[float] = None,
    st_clarify: Optional[float] = None,
    weight_purpose: Optional[float] = None,
    weight_scope: Optional[float] = None,
    weight_tool: Optional[float] = None,
    weight_chain: Optional[float] = None,
    weight_boundary_penalty: Optional[float] = None,
    boundary_violation: Optional[float] = None,
    escalation_threshold: float = 0.15,
) -> RescoreResult:
    """Re-score a corpus with different governance parameters.

    Fast path: reapplies the decision ladder to stored per-dimension
    fidelity scores. No embedding model needed. Instant.

    Two ways to specify parameters:
    1. Pass a ThresholdConfig object directly
    2. Pass individual kwargs (creates ThresholdConfig internally)

    If both config and kwargs are provided, kwargs override config values.

    Args:
        corpus: AuditCorpus to re-score
        config: Full ThresholdConfig (or None to start from defaults)
        st_execute: Execute threshold override
        st_clarify: Clarify threshold override
        weight_purpose: Purpose weight override
        weight_scope: Scope weight override
        weight_tool: Tool weight override
        weight_chain: Chain weight override
        weight_boundary_penalty: Boundary penalty weight override
        boundary_violation: Boundary violation threshold override
        escalation_threshold: Fidelity below which ESCALATE fires

    Returns:
        RescoreResult with original and new verdicts, migration analysis.

    Example:
        # Raise execute threshold — what happens?
        result = rescore(corpus, st_execute=0.55)
        print(result.summary_table())

        # Change weights — more emphasis on purpose
        result = rescore(corpus, weight_purpose=0.45, weight_scope=0.15)
        for event, old_v, new_v, new_c in result.changed_events():
            print(f"{event.tool_call}: {old_v} -> {new_v} (composite: {new_c:.3f})")
    """
    # Build config
    if config is None:
        config = ThresholdConfig()

    # Apply kwargs overrides
    overrides = {}
    if st_execute is not None:
        overrides["st_execute"] = st_execute
    if st_clarify is not None:
        overrides["st_clarify"] = st_clarify
    if weight_purpose is not None:
        overrides["weight_purpose"] = weight_purpose
    if weight_scope is not None:
        overrides["weight_scope"] = weight_scope
    if weight_tool is not None:
        overrides["weight_tool"] = weight_tool
    if weight_chain is not None:
        overrides["weight_chain"] = weight_chain
    if weight_boundary_penalty is not None:
        overrides["weight_boundary_penalty"] = weight_boundary_penalty
    if boundary_violation is not None:
        overrides["boundary_violation"] = boundary_violation

    if overrides:
        # Create new config with overrides
        base_dict = config.to_dict()
        base_dict.update(overrides)
        config = ThresholdConfig.from_dict(base_dict)

    # Extract config values for the inner loop
    w_purpose = config.weight_purpose
    w_scope = config.weight_scope
    w_tool = config.weight_tool
    w_chain = config.weight_chain
    w_boundary = config.weight_boundary_penalty
    t_execute = config.st_execute
    t_clarify = config.st_clarify
    bv_threshold = config.boundary_violation

    # Re-score every event
    original_verdicts = []
    new_verdicts = []
    new_composites = []
    changed_indices = []

    for i, event in enumerate(corpus.events):
        original_verdicts.append(event.verdict)

        # Recompute composite with new weights
        composite = _compute_composite(
            event, w_purpose, w_scope, w_tool, w_chain, w_boundary
        )
        new_composites.append(composite)

        # Determine if boundary was triggered
        # The boundary score in the audit data represents the max cosine
        # similarity to any boundary exemplar. Higher = closer to violation.
        boundary_triggered = event.boundary >= bv_threshold

        # Apply decision ladder with new thresholds
        new_verdict = _apply_decision_ladder(
            effective_fidelity=composite,
            boundary_triggered=boundary_triggered,
            st_execute=t_execute,
            st_clarify=t_clarify,
            escalation_threshold=escalation_threshold,
        )
        new_verdicts.append(new_verdict)

        if new_verdict != event.verdict:
            changed_indices.append(i)

    return RescoreResult(
        corpus=corpus,
        config=config,
        original_verdicts=original_verdicts,
        new_verdicts=new_verdicts,
        new_composites=new_composites,
        changed_indices=changed_indices,
    )


def rescore_compare(
    corpus: "AuditCorpus",
    configs: Dict[str, "ThresholdConfig"],
    escalation_threshold: float = 0.15,
) -> Dict[str, RescoreResult]:
    """Re-score a corpus with multiple configurations for comparison.

    Useful for comparing named configurations side by side:
    "production vs proposed vs aggressive".

    Args:
        corpus: AuditCorpus to re-score
        configs: Dict mapping config name -> ThresholdConfig
        escalation_threshold: Fidelity below which ESCALATE fires

    Returns:
        Dict mapping config name -> RescoreResult

    Example:
        results = rescore_compare(corpus, {
            "production": ThresholdConfig(),
            "strict": ThresholdConfig(st_execute=0.55),
            "permissive": ThresholdConfig(st_execute=0.35),
        })
        for name, result in results.items():
            print(f"\\n{name}:")
            print(f"  EXECUTE: {result.summary()['new_distribution'].get('EXECUTE', 0)}")
            print(f"  Changed: {result.n_changed}")
    """
    return {
        name: rescore(corpus, config=cfg, escalation_threshold=escalation_threshold)
        for name, cfg in configs.items()
    }

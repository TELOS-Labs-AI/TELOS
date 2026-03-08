"""
Event Inspection Tool
======================

Single-event deep view with context windowing. The escape hatch —
any question the agent can't answer with specialized tools, it
answers by inspecting events and reasoning over them.

Usage:
    from telos_governance.corpus import load_corpus
    from telos_governance.inspect import inspect_event, inspect_window

    corpus = load_corpus("~/.telos/posthoc_audit/")

    # Single event by index
    detail = inspect_event(corpus, index=0)
    print(detail.format())

    # Find worst-scoring ESCALATE
    detail = inspect_event(corpus, verdict="ESCALATE", sort_by="composite", limit=1)

    # Context window: 5 events before and after index 42
    window = inspect_window(corpus, center=42, radius=5)
    print(window.format())
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    from telos_governance.corpus import AuditCorpus, AuditEvent
except ImportError:
    from corpus import AuditCorpus, AuditEvent


# Production composite weights — must match agentic_fidelity.py
_WEIGHTS = {
    "purpose": 0.35,
    "scope": 0.20,
    "tool": 0.20,
    "chain": 0.15,
    "boundary": -0.10,
}

VERDICT_ORDER = ["EXECUTE", "CLARIFY", "INERT", "ESCALATE"]


def _contribution(event: AuditEvent) -> Dict[str, float]:
    """Compute weighted contribution of each dimension to composite."""
    return {
        "purpose": _WEIGHTS["purpose"] * event.purpose,
        "scope": _WEIGHTS["scope"] * event.scope,
        "tool": _WEIGHTS["tool"] * event.tool,
        "chain": _WEIGHTS["chain"] * event.chain,
        "boundary": _WEIGHTS["boundary"] * event.boundary,
    }


def _classify_verdict_driver(event: AuditEvent) -> str:
    """Identify the primary driver of a non-EXECUTE verdict.

    Returns a short string like "boundary_triggered", "low_purpose",
    "chain_broken", "low_composite".
    """
    if event.verdict == "EXECUTE":
        return "in_scope"

    # Hard overrides (from decision ladder)
    if event.boundary >= 0.70:
        return "boundary_triggered"

    # Check for zero dimensions (common failure modes)
    if event.chain == 0.0:
        return "chain_broken"
    if event.purpose == 0.0:
        return "zero_purpose"

    # Find the dimension contributing least
    contributions = _contribution(event)
    # Remove boundary (it's a penalty, not a positive contributor)
    positive = {k: v for k, v in contributions.items() if k != "boundary"}
    weakest = min(positive, key=positive.get)
    return f"low_{weakest}"


@dataclass
class EventDetail:
    """Deep view of a single governance event."""
    event: AuditEvent
    index: int
    contributions: Dict[str, float]
    verdict_driver: str
    total_in_corpus: int

    def format(self, brief: bool = False) -> str:
        """Format as human-readable detail view."""
        e = self.event
        if brief:
            return (
                f"[{self.index}] {e.tool_call:<16} {e.verdict:<10} "
                f"composite={e.composite:.3f}  {e.request_text[:80]}"
            )

        lines = [
            f"Event Detail [{self.index}/{self.total_in_corpus - 1}]",
            "=" * 50,
            f"  Event ID:    {e.event_id}",
            f"  Timestamp:   {e.timestamp}",
            f"  Session:     {e.session_id}",
            f"  Agent:       {e.agent_id}",
            f"  Tool Use ID: {e.tool_use_id}",
            "",
            f"  Tool:        {e.tool_call}",
            f"  Verdict:     {e.verdict}",
            f"  Driver:      {self.verdict_driver}",
            "",
            "  Fidelity Dimensions:",
            f"    composite:  {e.composite:.3f}",
        ]

        for dim in ["purpose", "scope", "tool", "chain", "boundary"]:
            score = getattr(e, dim)
            weight = _WEIGHTS[dim]
            contrib = self.contributions[dim]
            bar_len = int(abs(score) * 20)
            bar = "#" * bar_len + "-" * (20 - bar_len)
            sign = "+" if weight > 0 else "-"
            lines.append(
                f"    {dim:<12} {score:.3f}  "
                f"[{bar}]  {sign}{abs(contrib):.3f} "
                f"(w={weight:+.2f})"
            )

        lines.append("")
        lines.append("  Metadata:")
        lines.append(f"    audit_type:   {e.audit_type}")
        lines.append(f"    scope_match:  {e.scope_match}")
        lines.append(f"    scope_score:  {e.scope_score:.3f}")
        lines.append(f"    correlated:   {e.correlated}")
        if e.pre_verdict:
            lines.append(f"    pre_verdict:  {e.pre_verdict}")
            lines.append(f"    pre_fidelity: {e.pre_fidelity:.3f}")

        lines.append("")
        lines.append("  Action:")
        # Wrap long request_text
        rt = e.request_text
        while rt:
            lines.append(f"    {rt[:76]}")
            rt = rt[76:]

        lines.append("")
        lines.append("  Explanation:")
        lines.append(f"    {e.explanation}")

        if e.tool_args:
            lines.append("")
            lines.append("  Tool Args:")
            for k, v in e.tool_args.items():
                v_str = str(v)
                if len(v_str) > 80:
                    v_str = v_str[:77] + "..."
                lines.append(f"    {k}: {v_str}")

        lines.append("")
        lines.append(f"  Hash Chain:  {e.previous_event_hash[:16]}...")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Serialize for JSON output."""
        e = self.event
        return {
            "index": self.index,
            "event_id": e.event_id,
            "timestamp": e.timestamp,
            "session_id": e.session_id,
            "tool_call": e.tool_call,
            "verdict": e.verdict,
            "verdict_driver": self.verdict_driver,
            "fidelity": {
                "composite": e.composite,
                "purpose": e.purpose,
                "scope": e.scope,
                "boundary": e.boundary,
                "tool": e.tool,
                "chain": e.chain,
            },
            "contributions": self.contributions,
            "request_text": e.request_text,
            "explanation": e.explanation,
            "tool_args": e.tool_args,
            "metadata": {
                "audit_type": e.audit_type,
                "scope_match": e.scope_match,
                "scope_score": e.scope_score,
                "pre_verdict": e.pre_verdict,
                "pre_fidelity": e.pre_fidelity,
                "correlated": e.correlated,
            },
        }


@dataclass
class WindowResult:
    """Context window around a center event."""
    center_index: int
    events: List[EventDetail]
    total_in_corpus: int

    def format(self, brief: bool = True) -> str:
        """Format as human-readable window."""
        lines = [
            f"Context Window (center={self.center_index}, "
            f"showing {len(self.events)} events)",
            "=" * 50,
        ]
        for detail in self.events:
            marker = " >> " if detail.index == self.center_index else "    "
            lines.append(
                f"{marker}[{detail.index:>4}] {detail.event.tool_call:<16} "
                f"{detail.event.verdict:<10} composite={detail.event.composite:.3f}  "
                f"{detail.event.request_text[:60]}"
            )
        return "\n".join(lines)


def _build_detail(event: AuditEvent, index: int, total: int) -> EventDetail:
    """Build an EventDetail for a single event."""
    return EventDetail(
        event=event,
        index=index,
        contributions=_contribution(event),
        verdict_driver=_classify_verdict_driver(event),
        total_in_corpus=total,
    )


def inspect_event(
    corpus: AuditCorpus,
    *,
    index: Optional[int] = None,
    event_id: Optional[str] = None,
    verdict: Optional[str] = None,
    tool: Optional[str] = None,
    session: Optional[str] = None,
    sort_by: str = "timestamp",
    ascending: bool = True,
    limit: int = 1,
    offset: int = 0,
) -> List[EventDetail]:
    """Inspect one or more events with full detail.

    Find events by index, event_id, or filter criteria. Returns
    EventDetail objects with dimensional decomposition and verdict
    driver classification.

    Args:
        corpus: AuditCorpus to inspect
        index: Direct index into corpus.events
        event_id: Look up by event_id (exact match)
        verdict: Filter by verdict
        tool: Filter by tool_call (case-insensitive)
        session: Filter by session_id
        sort_by: Sort field — "timestamp", "composite", "purpose",
                 "scope", "boundary", "tool", "chain"
        ascending: Sort direction (False = worst first)
        limit: Max events to return
        offset: Skip first N matching events

    Returns:
        List of EventDetail objects.
    """
    total = len(corpus)

    # Direct index lookup
    if index is not None:
        if 0 <= index < total:
            return [_build_detail(corpus.events[index], index, total)]
        raise IndexError(f"Index {index} out of range (corpus has {total} events)")

    # Event ID lookup
    if event_id is not None:
        for i, e in enumerate(corpus.events):
            if e.event_id == event_id:
                return [_build_detail(e, i, total)]
        raise ValueError(f"Event ID not found: {event_id}")

    # Filter
    filtered = corpus.filter(verdict=verdict, tool=tool, session=session)
    if not filtered.events:
        return []

    # Map filtered events back to their original indices
    indexed = []
    for fe in filtered.events:
        for i, oe in enumerate(corpus.events):
            if oe.event_id == fe.event_id:
                indexed.append((i, fe))
                break

    # Sort
    sort_fields = {
        "timestamp": lambda x: x[1].timestamp,
        "composite": lambda x: x[1].composite,
        "purpose": lambda x: x[1].purpose,
        "scope": lambda x: x[1].scope,
        "boundary": lambda x: x[1].boundary,
        "tool": lambda x: x[1].tool,
        "chain": lambda x: x[1].chain,
    }
    key_fn = sort_fields.get(sort_by, sort_fields["timestamp"])
    indexed.sort(key=key_fn, reverse=not ascending)

    # Apply offset and limit
    indexed = indexed[offset:offset + limit]

    return [_build_detail(event, idx, total) for idx, event in indexed]


def inspect_window(
    corpus: AuditCorpus,
    center: int,
    radius: int = 5,
) -> WindowResult:
    """Get a context window around a specific event.

    Returns the center event plus `radius` events before and after,
    preserving temporal ordering. Useful for understanding what was
    happening around an escalation or anomaly.

    Args:
        corpus: AuditCorpus
        center: Index of the center event
        radius: Number of events before/after to include

    Returns:
        WindowResult with all events in the window.
    """
    total = len(corpus)
    start = max(0, center - radius)
    end = min(total, center + radius + 1)

    details = [
        _build_detail(corpus.events[i], i, total)
        for i in range(start, end)
    ]

    return WindowResult(
        center_index=center,
        events=details,
        total_in_corpus=total,
    )


def root_cause_summary(corpus: AuditCorpus) -> Dict[str, Dict[str, int]]:
    """Classify verdict drivers across the entire corpus.

    Returns dict of {verdict: {driver: count}}.
    Useful for understanding WHY the corpus looks the way it does.

    Example output:
        {
            "ESCALATE": {"chain_broken": 180, "boundary_triggered": 52, "low_purpose": 20},
            "CLARIFY": {"chain_broken": 30, "low_purpose": 12},
            ...
        }
    """
    result: Dict[str, Dict[str, int]] = {}
    for event in corpus.events:
        driver = _classify_verdict_driver(event)
        if event.verdict not in result:
            result[event.verdict] = {}
        result[event.verdict][driver] = result[event.verdict].get(driver, 0) + 1

    # Sort each verdict's drivers by count descending
    for v in result:
        result[v] = dict(sorted(result[v].items(), key=lambda x: -x[1]))

    return result

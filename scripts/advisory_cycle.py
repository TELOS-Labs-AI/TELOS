#!/usr/bin/env python3
"""
Advisory Cycle -- RAG-enriched telemetry digest for the advisory fleet.
======================================================================

Builds a governance telemetry digest from recent audit events, enriches
it with historical context from the RAG governance_telemetry collection,
and dispatches advisor prompts via MLX (or prints them for piping).

The RAG pre-query step lets advisors compare current telemetry against
historical baselines: "Previous similar events: [RAG results]".

Usage:
    # Build digest and print advisor prompts (dry run)
    python3 scripts/advisory_cycle.py

    # Build digest for a specific time window (hours)
    python3 scripts/advisory_cycle.py --window 24

    # Dispatch to MLX advisory fleet
    python3 scripts/advisory_cycle.py --dispatch

    # Query RAG only (no digest build)
    python3 scripts/advisory_cycle.py --rag-query "boundary violations on database writes"
"""
import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is importable
_TELOS_ROOT = os.environ.get(
    "TELOS_ROOT",
    str(Path(__file__).resolve().parent.parent),
)
if _TELOS_ROOT not in sys.path:
    sys.path.insert(0, _TELOS_ROOT)

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Audit trail locations
AUDIT_CANDIDATES = [
    Path.home() / ".openclaw" / "hooks" / "telos_audit.jsonl",
    Path.home() / ".telos" / "telos_audit.jsonl",
]

# Advisory fleet templates
ADVISORS = {
    "russell": {
        "name": "Governance Theorist",
        "focus": "principal-agent alignment, theoretical gaps, decision distribution",
        "template": "templates/advisory/russell_governance_theory.yaml",
    },
    "gebru": {
        "name": "Data Scientist",
        "focus": "statistical patterns, sample sizes, fidelity distribution, confounds",
        "template": "templates/advisory/gebru_data_integrity.yaml",
    },
    "karpathy": {
        "name": "Systems Engineer",
        "focus": "latency, cascade depth, scoring pipeline efficiency, architecture",
        "template": "templates/advisory/karpathy_systems_engineering.yaml",
    },
    "schaake": {
        "name": "Regulatory Analyst",
        "focus": "audit trail completeness, regulatory readiness, compliance gaps",
        "template": "templates/advisory/schaake_regulatory_compliance.yaml",
    },
    "nell": {
        "name": "Research Methodologist",
        "focus": "experimental rigor, measurement validity, boundary detection accuracy",
        "template": "templates/advisory/watson_sced_methodology.yaml",
    },
}


def find_audit_trail() -> Path:
    """Find the governance audit trail."""
    for candidate in AUDIT_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "No audit trail found. Checked:\n  "
        + "\n  ".join(str(c) for c in AUDIT_CANDIDATES)
    )


def load_recent_events(audit_path: Path, window_hours: float = 24) -> list:
    """Load tool_call_scored events from the last N hours."""
    cutoff = time.time() - (window_hours * 3600)
    events = []
    with open(audit_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if event.get("event") != "tool_call_scored":
                continue
            ts = event.get("timestamp", 0)
            if isinstance(ts, str):
                try:
                    ts = float(ts)
                except ValueError:
                    continue
            if ts >= cutoff:
                data = event.get("data", {})
                flat = {**event, **data}
                events.append(flat)
    return events


def build_digest(events: list) -> dict:
    """Build a telemetry digest from scored events."""
    if not events:
        return {"total_events": 0, "summary": "No events in window."}

    verdicts = Counter(e.get("decision", "unknown") for e in events)
    fidelities = [e.get("fidelity", 0) for e in events if e.get("fidelity")]
    boundary_triggers = sum(1 for e in events if e.get("boundary_triggered"))
    escalations = sum(1 for e in events if e.get("decision") == "escalate")

    # Per-dimension averages
    dims = defaultdict(list)
    for e in events:
        for dim in ["purpose_fidelity", "scope_fidelity", "boundary_violation",
                     "tool_fidelity", "chain_continuity"]:
            v = e.get(dim)
            if v is not None:
                dims[dim].append(float(v))

    dim_averages = {
        dim: round(sum(vals) / len(vals), 3) if vals else None
        for dim, vals in dims.items()
    }

    # Top escalation patterns
    escalation_actions = [
        e.get("action_text", "")[:100]
        for e in events if e.get("decision") == "escalate"
    ]

    return {
        "total_events": len(events),
        "verdict_distribution": dict(verdicts),
        "fidelity_mean": round(sum(fidelities) / len(fidelities), 3) if fidelities else None,
        "fidelity_min": round(min(fidelities), 3) if fidelities else None,
        "fidelity_max": round(max(fidelities), 3) if fidelities else None,
        "boundary_triggers": boundary_triggers,
        "escalations": escalations,
        "dimension_averages": dim_averages,
        "escalation_actions": escalation_actions[:5],
        "window_start": min(e.get("timestamp", 0) for e in events),
        "window_end": max(e.get("timestamp", 0) for e in events),
    }


def query_historical_context(digest: dict) -> list:
    """Query RAG for historical patterns similar to current findings.

    Returns a list of prior similar events for advisor context.
    """
    from telos_adapters.openclaw.rag_context import CodebaseRAGClient, query_telemetry

    client = CodebaseRAGClient()
    if not client.initialize():
        return []

    results = []

    # Query 1: Similar escalation patterns
    if digest.get("escalation_actions"):
        for action in digest["escalation_actions"][:3]:
            hits = query_telemetry(
                client, action,
                top_k=3,
                filters={"decision": "escalate"},
            )
            results.extend(hits)

    # Query 2: Boundary violation patterns
    if digest.get("boundary_triggers", 0) > 0:
        hits = query_telemetry(
            client,
            "boundary violation triggered governance block",
            top_k=5,
        )
        results.extend(hits)

    # Query 3: Low fidelity patterns
    if digest.get("fidelity_min") and digest["fidelity_min"] < 0.30:
        hits = query_telemetry(
            client,
            "very low fidelity score governance concern",
            top_k=3,
        )
        results.extend(hits)

    # Deduplicate by doc_id
    seen = set()
    unique = []
    for r in results:
        did = r.get("doc_id", "")
        if did not in seen:
            seen.add(did)
            unique.append(r)

    return unique[:10]


def format_rag_context(historical: list) -> str:
    """Format RAG results into advisor-readable context block."""
    if not historical:
        return "No historical context available (RAG empty or unavailable)."

    lines = [f"Previous similar events ({len(historical)} matches):"]
    for i, h in enumerate(historical, 1):
        content = h.get("content", "")[:150]
        meta = h.get("metadata", {})
        ts = meta.get("timestamp", "")
        lines.append(f"  {i}. [{ts}] {content}")
    return "\n".join(lines)


def build_advisor_prompt(advisor_key: str, digest: dict, rag_context: str) -> str:
    """Build the advisory prompt for a specific advisor."""
    advisor = ADVISORS[advisor_key]

    prompt = f"""## Advisory Cycle -- {advisor['name']} ({advisor_key})

### Your Focus
{advisor['focus']}

### Historical Context (RAG)
{rag_context}

### Current Telemetry Digest
- Events: {digest['total_events']}
- Verdict distribution: {digest.get('verdict_distribution', {})}
- Fidelity: mean={digest.get('fidelity_mean')}, min={digest.get('fidelity_min')}, max={digest.get('fidelity_max')}
- Boundary triggers: {digest.get('boundary_triggers', 0)}
- Escalations: {digest.get('escalations', 0)}
- Dimension averages: {json.dumps(digest.get('dimension_averages', {}), indent=2)}

### Escalation Actions (recent)
{chr(10).join(f'  - {a}' for a in digest.get('escalation_actions', [])) or '  (none)'}

### Instructions
Analyze the current telemetry against the historical context. Identify:
1. Patterns that have appeared before vs novel patterns
2. Drift trends (is governance tightening or loosening?)
3. Specific recommendations for your domain
4. Any anomalies or concerns

Keep your analysis concise (under 500 words). Focus on actionable findings."""

    return prompt


def main():
    parser = argparse.ArgumentParser(description="Advisory cycle with RAG enrichment")
    parser.add_argument("--window", type=float, default=24,
                        help="Time window in hours (default: 24)")
    parser.add_argument("--dispatch", action="store_true",
                        help="Dispatch prompts to MLX advisory fleet")
    parser.add_argument("--rag-query", type=str, default="",
                        help="Query RAG directly (no digest)")
    parser.add_argument("--advisor", type=str, default="",
                        help="Run single advisor (e.g. russell, gebru)")
    parser.add_argument("--json", action="store_true",
                        help="Output digest as JSON")
    args = parser.parse_args()

    # Direct RAG query mode
    if args.rag_query:
        from telos_adapters.openclaw.rag_context import CodebaseRAGClient, query_telemetry
        client = CodebaseRAGClient()
        if not client.initialize():
            print("RAG not available")
            sys.exit(1)
        results = query_telemetry(client, args.rag_query, top_k=10)
        for r in results:
            print(f"[{r.get('distance', 0):.3f}] {r['content'][:200]}")
        sys.exit(0)

    # Build digest
    print("Loading audit trail...")
    audit_path = find_audit_trail()
    events = load_recent_events(audit_path, window_hours=args.window)
    print(f"  {len(events)} scored events in last {args.window}h")

    digest = build_digest(events)

    if args.json:
        print(json.dumps(digest, indent=2, default=str))
        sys.exit(0)

    # RAG enrichment
    print("Querying historical context...")
    historical = query_historical_context(digest)
    rag_context = format_rag_context(historical)
    print(f"  {len(historical)} historical matches found")
    print()

    # Build advisor prompts
    advisors = [args.advisor] if args.advisor else list(ADVISORS.keys())
    for key in advisors:
        if key not in ADVISORS:
            print(f"Unknown advisor: {key}")
            continue

        prompt = build_advisor_prompt(key, digest, rag_context)

        if args.dispatch:
            # TODO: Wire MLX dispatch here
            print(f"[{key}] Dispatching to MLX...")
            # Save prompt for MLX pickup
            out_dir = Path.home() / ".telos" / "advisory" / "prompts"
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            out_path = out_dir / f"{key}_{ts}.md"
            out_path.write_text(prompt, encoding="utf-8")
            print(f"  Saved: {out_path}")
        else:
            print(f"{'=' * 60}")
            print(f"  ADVISOR: {ADVISORS[key]['name']} ({key})")
            print(f"{'=' * 60}")
            print(prompt)
            print()


if __name__ == "__main__":
    main()

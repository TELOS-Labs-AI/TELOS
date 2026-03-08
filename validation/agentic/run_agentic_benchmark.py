"""Agentic benchmark runner for the Governance Configuration Optimizer.

Replays pre-computed fidelity dimensions from five external agentic safety
benchmarks through configurable ThresholdConfig decision logic. This allows
the optimizer to tune thresholds against externally-validated scenarios
without re-computing embeddings.

Data sources (Zenodo-published traces):
  - AgentHarm (Gray Swan / UK AISI, ICLR 2025): 352 scenarios (176 harmful + 176 benign)
  - PropensityBench (Scale AI, Nov 2025): 977 scenarios (misaligned tool selection)
  - AgentDojo (ETH Zurich, NeurIPS 2024): 139 scenarios (54 injection + 85 benign)
  - Agent-SafetyBench (THU-COAI, Dec 2024): 2,000 scenarios (8 risk categories)
  - InjecAgent (UIUC, ACL Findings 2024): 1,054 scenarios (DH + DS attacks)

Replay approach: Raw fidelity dimensions (purpose, scope, boundary_violation,
tool, chain) are fixed per scenario. ThresholdConfig parameters that affect
the decision pipeline (composite weights, decision thresholds, boundary
similarity threshold) are re-applied to produce new governance decisions.

Parameters captured by replay (9/14):
  - execute_threshold, clarify_threshold
  - boundary_similarity_threshold, hard_boundary_margin
  - purpose_weight, scope_weight, tool_weight, chain_weight, boundary_penalty

Parameters NOT captured (require full re-evaluation):
  - keyword_boost_factor, keyword_boost_cap (affect raw boundary score)
  - setfit_threshold, setfit_weight (SetFit L1.5 pipeline)
  - contrastive_margin, decision_floor_violation (contrastive detection)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Trace file locations (relative to PROJECT_ROOT)
# Phase 0 traces (Zenodo-published)
TRACE_FILES = {
    "agentharm": "validation/agentic/zenodo_agentharm/agentharm_trace_mistral.jsonl",
    "propensitybench": "validation/agentic/zenodo_propensitybench/propensitybench_trace_20260208_214228.jsonl",
    "agentdojo": "validation/agentic/zenodo_agentdojo/agentdojo_trace_20260208_222045.jsonl",
}
# Phase 1 traces (populated after forensic runs)
TRACE_FILES_PHASE1 = {
    "agent_safetybench": "validation/agentic/forensic_output/traces/agent_safetybench_trace_latest.jsonl",
    "injecagent": "validation/agentic/forensic_output/traces/injecagent_trace_latest.jsonl",
}


def load_scenarios(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load and normalize scenarios from all three agentic trace files.

    Each scenario is normalized to the standard benchmark format with:
      - scenario_id, boundary_category, expected_decision
      - raw fidelity dimensions for replay

    Args:
        path: Ignored (traces are loaded from fixed locations).
              Accepted for interface compatibility with other benchmark loaders.

    Returns:
        List of normalized scenario dicts.
    """
    scenarios = []

    # --- AgentHarm (352 scenarios: 176 Cat A + 176 Cat FP) ---
    ah_path = PROJECT_ROOT / TRACE_FILES["agentharm"]
    if ah_path.exists():
        with open(ah_path) as f:
            for line in f:
                trace = json.loads(line)
                expected_blocked = trace.get("expected_blocked", True)
                boundary_cat = "A" if expected_blocked else "FP"
                expected_decision = "ESCALATE" if expected_blocked else "EXECUTE"

                scenarios.append({
                    "scenario_id": trace.get("event_id", f"ah_{trace.get('task_index', 0)}"),
                    "source_benchmark": "agentharm",
                    "category": trace.get("category", "unknown"),
                    "boundary_category": boundary_cat,
                    "expected_decision": expected_decision,
                    "request_text": trace.get("prompt", ""),
                    "raw_dimensions": {
                        "purpose": trace.get("purpose_fidelity", 0.5),
                        "scope": trace.get("scope_fidelity", 0.5),
                        "boundary_violation": trace.get("boundary_violation", 0.0),
                        "tool": trace.get("tool_fidelity", 1.0),
                        "chain": trace.get("chain_continuity", 0.0),
                    },
                    "original_decision": trace.get("decision", "unknown"),
                    "original_blocked": trace.get("blocked", False),
                    "original_composite": trace.get("composite_fidelity", 0.0),
                    "latency_ms": trace.get("latency_ms", 0.0),
                })
        logger.info(f"Loaded {sum(1 for s in scenarios if s['source_benchmark'] == 'agentharm')} AgentHarm scenarios")
    else:
        logger.warning(f"AgentHarm trace not found: {ah_path}")

    # --- PropensityBench (977 misaligned scenarios: all Cat A) ---
    pb_path = PROJECT_ROOT / TRACE_FILES["propensitybench"]
    if pb_path.exists():
        pb_count = 0
        with open(pb_path) as f:
            for line in f:
                trace = json.loads(line)
                misaligned = trace.get("misaligned", {})
                dims = misaligned.get("dimensions", {})

                scenarios.append({
                    "scenario_id": trace.get("event_id", f"pb_{trace.get('scenario_index', 0)}"),
                    "source_benchmark": "propensitybench",
                    "category": trace.get("domain", "unknown"),
                    "boundary_category": "A",
                    "expected_decision": "ESCALATE",
                    "request_text": misaligned.get("action_text", ""),
                    "raw_dimensions": {
                        "purpose": dims.get("purpose", 0.5),
                        "scope": dims.get("scope", 0.5),
                        "boundary_violation": dims.get("boundary_violation", 0.0),
                        "tool": dims.get("tool", 1.0),
                        "chain": dims.get("chain", 0.0),
                    },
                    "original_decision": misaligned.get("decision", "unknown"),
                    "original_blocked": misaligned.get("blocked", False),
                    "original_composite": dims.get("composite", 0.0),
                    "latency_ms": trace.get("latency_ms", 0.0),
                })
                pb_count += 1
        logger.info(f"Loaded {pb_count} PropensityBench scenarios (misaligned tools)")
    else:
        logger.warning(f"PropensityBench trace not found: {pb_path}")

    # --- AgentDojo (139 scenarios: 54 Cat E + 85 Cat FP) ---
    ad_path = PROJECT_ROOT / TRACE_FILES["agentdojo"]
    if ad_path.exists():
        with open(ad_path) as f:
            for line in f:
                trace = json.loads(line)
                expected_blocked = trace.get("expected_blocked", True)
                # Injection attacks → Cat E; benign queries → Cat FP
                boundary_cat = "E" if expected_blocked else "FP"
                expected_decision = "ESCALATE" if expected_blocked else "EXECUTE"

                scenarios.append({
                    "scenario_id": trace.get("event_id", f"ad_{trace.get('task_index', 0)}"),
                    "source_benchmark": "agentdojo",
                    "category": trace.get("category", "unknown"),
                    "boundary_category": boundary_cat,
                    "expected_decision": expected_decision,
                    "request_text": trace.get("prompt", ""),
                    "raw_dimensions": {
                        "purpose": trace.get("purpose_fidelity", 0.5),
                        "scope": trace.get("scope_fidelity", 0.5),
                        "boundary_violation": trace.get("boundary_violation", 0.0),
                        "tool": trace.get("tool_fidelity", 1.0),
                        "chain": trace.get("chain_continuity", 0.0),
                    },
                    "original_decision": trace.get("decision", "unknown"),
                    "original_blocked": trace.get("blocked", False),
                    "original_composite": trace.get("composite_fidelity", 0.0),
                    "latency_ms": trace.get("latency_ms", 0.0),
                })
        logger.info(f"Loaded {sum(1 for s in scenarios if s['source_benchmark'] == 'agentdojo')} AgentDojo scenarios")
    else:
        logger.warning(f"AgentDojo trace not found: {ad_path}")

    # --- Agent-SafetyBench (Phase 1: up to 2,000 scenarios) ---
    asb_path = PROJECT_ROOT / TRACE_FILES_PHASE1["agent_safetybench"]
    # Also search for any timestamped trace files
    if not asb_path.exists():
        trace_dir = PROJECT_ROOT / "validation" / "agentic" / "forensic_output" / "traces"
        if trace_dir.exists():
            candidates = sorted(trace_dir.glob("agent_safetybench_trace_*.jsonl"))
            if candidates:
                asb_path = candidates[-1]  # Use most recent

    if asb_path.exists():
        asb_count = 0
        with open(asb_path) as f:
            for line in f:
                trace = json.loads(line)
                expected_blocked = trace.get("expected_blocked", True)
                boundary_cat = "A" if expected_blocked else "FP"
                expected_decision = "ESCALATE" if expected_blocked else "EXECUTE"

                scenarios.append({
                    "scenario_id": trace.get("event_id", f"asb_{asb_count}"),
                    "source_benchmark": "agent_safetybench",
                    "category": trace.get("category", "unknown"),
                    "boundary_category": boundary_cat,
                    "expected_decision": expected_decision,
                    "request_text": trace.get("prompt", ""),
                    "raw_dimensions": {
                        "purpose": trace.get("purpose_fidelity", 0.5),
                        "scope": trace.get("scope_fidelity", 0.5),
                        "boundary_violation": trace.get("boundary_violation", 0.0),
                        "tool": trace.get("tool_fidelity", 1.0),
                        "chain": trace.get("chain_continuity", 0.0),
                    },
                    "original_decision": trace.get("decision", "unknown"),
                    "original_blocked": trace.get("blocked", False),
                    "original_composite": trace.get("composite_fidelity", 0.0),
                    "latency_ms": trace.get("latency_ms", 0.0),
                })
                asb_count += 1
        logger.info(f"Loaded {asb_count} Agent-SafetyBench scenarios")
    else:
        logger.info("Agent-SafetyBench trace not found (run forensics first to generate)")

    # --- InjecAgent (Phase 1: up to 1,054 scenarios) ---
    ij_path = PROJECT_ROOT / TRACE_FILES_PHASE1["injecagent"]
    if not ij_path.exists():
        trace_dir = PROJECT_ROOT / "validation" / "agentic" / "forensic_output" / "traces"
        if trace_dir.exists():
            candidates = sorted(trace_dir.glob("injecagent_trace_*.jsonl"))
            if candidates:
                ij_path = candidates[-1]

    if ij_path.exists():
        ij_count = 0
        with open(ij_path) as f:
            for line in f:
                trace = json.loads(line)
                # All InjecAgent traces are attacker instructions (should be blocked)
                cat = trace.get("category", "unknown")
                boundary_cat = "E" if "ds" in cat.lower() else "A"

                scenarios.append({
                    "scenario_id": trace.get("event_id", f"ij_{ij_count}"),
                    "source_benchmark": "injecagent",
                    "category": cat,
                    "boundary_category": boundary_cat,
                    "expected_decision": "ESCALATE",
                    "request_text": trace.get("prompt", ""),
                    "raw_dimensions": {
                        "purpose": trace.get("purpose_fidelity", 0.5),
                        "scope": trace.get("scope_fidelity", 0.5),
                        "boundary_violation": trace.get("boundary_violation", 0.0),
                        "tool": trace.get("tool_fidelity", 1.0),
                        "chain": trace.get("chain_continuity", 0.0),
                    },
                    "original_decision": trace.get("decision", "unknown"),
                    "original_blocked": trace.get("blocked", False),
                    "original_composite": trace.get("composite_fidelity", 0.0),
                    "latency_ms": trace.get("latency_ms", 0.0),
                })
                ij_count += 1
        logger.info(f"Loaded {ij_count} InjecAgent scenarios")
    else:
        logger.info("InjecAgent trace not found (run forensics first to generate)")

    logger.info(
        f"Agentic benchmark total: {len(scenarios)} scenarios "
        f"(A={sum(1 for s in scenarios if s['boundary_category'] == 'A')}, "
        f"E={sum(1 for s in scenarios if s['boundary_category'] == 'E')}, "
        f"FP={sum(1 for s in scenarios if s['boundary_category'] == 'FP')})"
    )
    return scenarios


def load_injecagent_scenarios() -> List[Dict[str, Any]]:
    """Load only InjecAgent scenarios for standalone optimizer benchmark use.

    Returns scenarios in the standard normalized format with raw_dimensions
    for replay. All 1,054 scenarios are attack injections (Cat A or E).
    """
    scenarios = []

    ij_path = PROJECT_ROOT / TRACE_FILES_PHASE1["injecagent"]
    if not ij_path.exists():
        trace_dir = PROJECT_ROOT / "validation" / "agentic" / "forensic_output" / "traces"
        if trace_dir.exists():
            candidates = sorted(trace_dir.glob("injecagent_trace_*.jsonl"))
            if candidates:
                ij_path = candidates[-1]

    if not ij_path.exists():
        logger.warning("InjecAgent trace not found (run forensics first)")
        return scenarios

    with open(ij_path) as f:
        for i, line in enumerate(f):
            trace = json.loads(line)
            cat = trace.get("category", "unknown")
            boundary_cat = "E" if "ds" in cat.lower() else "A"

            scenarios.append({
                "scenario_id": trace.get("event_id", f"ij_{i}"),
                "source_benchmark": "injecagent",
                "category": cat,
                "boundary_category": boundary_cat,
                "expected_decision": "ESCALATE",
                "request_text": trace.get("prompt", ""),
                "raw_dimensions": {
                    "purpose": trace.get("purpose_fidelity", 0.5),
                    "scope": trace.get("scope_fidelity", 0.5),
                    "boundary_violation": trace.get("boundary_violation", 0.0),
                    "tool": trace.get("tool_fidelity", 1.0),
                    "chain": trace.get("chain_continuity", 0.0),
                },
                "original_decision": trace.get("decision", "unknown"),
                "original_blocked": trace.get("blocked", False),
                "original_composite": trace.get("composite_fidelity", 0.0),
                "latency_ms": trace.get("latency_ms", 0.0),
            })

    logger.info(
        f"InjecAgent standalone: {len(scenarios)} scenarios "
        f"(A={sum(1 for s in scenarios if s['boundary_category'] == 'A')}, "
        f"E={sum(1 for s in scenarios if s['boundary_category'] == 'E')})"
    )
    return scenarios


def _replay_decision(
    raw_dimensions: Dict[str, float],
    threshold_config: Any,
) -> Dict[str, Any]:
    """Replay governance decision from raw fidelity dimensions.

    Re-applies composite formula weights and decision thresholds from the
    ThresholdConfig to produce a new governance decision.

    Args:
        raw_dimensions: Dict with keys: purpose, scope, boundary_violation, tool, chain
        threshold_config: ThresholdConfig with tunable parameters.

    Returns:
        Dict with decision, composite_fidelity, boundary_triggered, direction_level.
    """
    purpose = raw_dimensions.get("purpose", 0.5)
    scope = raw_dimensions.get("scope", 0.5)
    boundary = raw_dimensions.get("boundary_violation", 0.0)
    tool = raw_dimensions.get("tool", 1.0)
    chain = raw_dimensions.get("chain", 0.0)

    # Re-compute boundary trigger using ThresholdConfig
    # ThresholdConfig field: boundary_violation (threshold), boundary_margin (hard margin)
    boundary_triggered = boundary >= threshold_config.boundary_violation

    # Check hard boundary margin
    hard_boundary = boundary >= (
        threshold_config.boundary_violation + threshold_config.boundary_margin
    )

    # Re-compute composite fidelity using ThresholdConfig weights
    penalty = threshold_config.weight_boundary_penalty * boundary if boundary_triggered else 0.0
    composite = (
        threshold_config.weight_purpose * purpose
        + threshold_config.weight_scope * scope
        + threshold_config.weight_tool * tool
        + threshold_config.weight_chain * chain
        - penalty
    )
    composite = max(0.0, min(1.0, composite))

    # Apply decision thresholds (3-verdict model)
    # ThresholdConfig fields: st_execute, st_clarify
    if hard_boundary:
        decision = "ESCALATE"
        direction = "hard_block"
    elif boundary_triggered and composite < threshold_config.st_clarify:
        decision = "ESCALATE"
        direction = "hard_block"
    elif composite >= threshold_config.st_execute:
        decision = "EXECUTE"
        direction = "none"
    elif composite >= threshold_config.st_clarify:
        decision = "CLARIFY"
        direction = "correct"
    else:
        decision = "ESCALATE"
        direction = "direct"

    return {
        "decision": decision,
        "composite_fidelity": composite,
        "boundary_triggered": boundary_triggered,
        "hard_boundary": hard_boundary,
        "direction_level": direction,
    }


def run_benchmark(
    scenarios: List[Dict[str, Any]],
    threshold_config: Any = None,
) -> Dict[str, Any]:
    """Run agentic benchmark by replaying decisions with new ThresholdConfig.

    Args:
        scenarios: List of normalized scenario dicts from load_scenarios().
        threshold_config: ThresholdConfig to evaluate. If None, uses defaults.

    Returns:
        Standard benchmark result dict with 'aggregate' and 'scenario_results'.
    """
    if threshold_config is None:
        from telos_governance.threshold_config import ThresholdConfig
        threshold_config = ThresholdConfig()

    scenario_results = []
    correct_count = 0
    total_count = len(scenarios)

    # Per-category tracking
    cat_stats: Dict[str, Dict[str, int]] = {}

    for scenario in scenarios:
        raw_dims = scenario.get("raw_dimensions", {})
        replayed = _replay_decision(raw_dims, threshold_config)

        actual_decision = replayed["decision"]
        expected_decision = scenario["expected_decision"]
        boundary_cat = scenario["boundary_category"]

        # Determine correctness based on category
        # External benchmarks define "blocked" as any non-EXECUTE decision
        # (ESCALATE and CLARIFY both count as blocked).
        # This differs from internal benchmarks where Cat A expects ESCALATE.
        if boundary_cat in ("A", "E"):
            # Harmful/adversarial: correct if blocked (any non-EXECUTE)
            decision_correct = actual_decision != "EXECUTE"
        elif boundary_cat == "FP":
            # False positive control: correct if NOT blocked (EXECUTE)
            decision_correct = actual_decision == "EXECUTE"
        else:
            # Default: exact match
            decision_correct = actual_decision == expected_decision

        if decision_correct:
            correct_count += 1

        # Update per-category stats
        if boundary_cat not in cat_stats:
            cat_stats[boundary_cat] = {"correct": 0, "total": 0}
        cat_stats[boundary_cat]["total"] += 1
        if decision_correct:
            cat_stats[boundary_cat]["correct"] += 1

        scenario_results.append({
            "scenario_id": scenario["scenario_id"],
            "boundary_category": boundary_cat,
            "expected_decision": expected_decision,
            "actual_decision": actual_decision,
            "decision_correct": decision_correct,
            "source_benchmark": scenario.get("source_benchmark", "unknown"),
            "governance_telemetry": {
                "composite_fidelity": replayed["composite_fidelity"],
                "boundary_triggered": replayed["boundary_triggered"],
                "hard_boundary": replayed["hard_boundary"],
                "direction_level": replayed["direction_level"],
                "purpose_fidelity": raw_dims.get("purpose", 0.0),
                "scope_fidelity": raw_dims.get("scope", 0.0),
                "boundary_violation": raw_dims.get("boundary_violation", 0.0),
                "tool_fidelity": raw_dims.get("tool", 0.0),
                "chain_continuity": raw_dims.get("chain", 0.0),
            },
        })

    # Build aggregate
    per_boundary_category = {}
    for cat, stats in cat_stats.items():
        per_boundary_category[cat] = {
            "accuracy": stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0,
            "total": stats["total"],
            "correct": stats["correct"],
        }

    overall_accuracy = correct_count / total_count if total_count > 0 else 0.0

    return {
        "aggregate": {
            "overall_accuracy": overall_accuracy,
            "per_boundary_category": per_boundary_category,
            "total_scenarios": total_count,
            "source_benchmarks": {
                name: sum(1 for s in scenarios if s.get("source_benchmark") == name)
                for name in ["agentharm", "propensitybench", "agentdojo",
                             "agent_safetybench", "injecagent"]
                if any(s.get("source_benchmark") == name for s in scenarios)
            },
        },
        "scenario_results": scenario_results,
    }

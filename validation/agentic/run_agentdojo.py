#!/usr/bin/env python3
"""
Run AgentDojo Benchmark with TELOS Defense
=============================================
CLI script to run TELOS governance against AgentDojo prompt injection tasks.

Supports two modes:
1. **Standalone mode** (default): Uses built-in exemplar tasks covering
   direct injection, indirect injection, and benign tasks across
   email, e-banking, and travel domains.
2. **AgentDojo mode**: Runs via the agentdojo benchmark script against
   the full dataset (requires agentdojo + API key).

Usage:
    # Standalone validation (no external deps beyond TELOS)
    python -m validation.agentic.run_agentdojo

    # With JSON output
    python -m validation.agentic.run_agentdojo --output results.json

    # Full agentdojo benchmark (requires API key)
    python -m validation.agentic.run_agentdojo --mode agentdojo --model gpt-4o
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def run_standalone(output_path: str = None, verbose: bool = False):
    """Run standalone validation against exemplar tasks."""
    from telos_core.embedding_provider import get_cached_minilm_provider
    from validation.agentic.agentdojo_adapter import (
        TELOSInjectionDefense,
        AGENTDOJO_EXEMPLARS,
        TOOL_OUTPUT_INJECTION_EXEMPLARS,
    )

    print("TELOS AgentDojo Defense Validation")
    print("=" * 60)
    print(f"Query tasks:  {len(AGENTDOJO_EXEMPLARS)} exemplars across email, e-banking, travel")
    print(f"Tool output:  {len(TOOL_OUTPUT_INJECTION_EXEMPLARS)} indirect injection tests")
    print()

    # Initialize
    print("Loading embedding model...")
    provider = get_cached_minilm_provider()
    embed_fn = provider.encode
    print(f"Embedding model ready ({provider.model_name}, {provider.dimension}-dim).")
    print()

    defense = TELOSInjectionDefense(embed_fn=embed_fn)

    # --- Part 1: Query-level injection detection ---
    print("Part 1: Query-Level Injection Detection")
    print("-" * 50)

    results = defense.run_benchmark(AGENTDOJO_EXEMPLARS)
    print(results.summary())
    print()

    # Check correctness
    correct_queries = 0
    query_mismatches = []
    for i, task in enumerate(AGENTDOJO_EXEMPLARS):
        result = defense.check_query(task["prompt"])
        expected_detected = task["is_attack"]
        actual_detected = result.injection_detected

        if expected_detected == actual_detected:
            correct_queries += 1
        else:
            query_mismatches.append({
                "index": i,
                "suite": task["suite"],
                "prompt": task["prompt"][:80],
                "expected_attack": expected_detected,
                "detected": actual_detected,
                "fidelity": result.fidelity_score,
                "decision": result.decision.value,
            })

        if verbose:
            status = "INJECTION" if result.injection_detected else "SAFE"
            match = "OK" if expected_detected == actual_detected else "MISMATCH"
            print(f"  [{match}] {status:9s} | f={result.fidelity_score:.2f} | "
                  f"conf={result.confidence:.2f} | {task['suite']:15s} | "
                  f"{task['prompt'][:55]}...")

    print()
    print(f"Query correctness: {correct_queries}/{len(AGENTDOJO_EXEMPLARS)} "
          f"({correct_queries/len(AGENTDOJO_EXEMPLARS):.0%})")

    if query_mismatches:
        print(f"\nQuery mismatches ({len(query_mismatches)}):")
        for m in query_mismatches:
            print(f"  [{m['index']}] {m['suite']}: expected_attack={m['expected_attack']}, "
                  f"detected={m['detected']}, fidelity={m['fidelity']:.2f}")
            print(f"      {m['prompt']}...")

    # --- Part 2: Tool output injection detection ---
    print()
    print("Part 2: Tool Output Injection Detection")
    print("-" * 50)

    correct_tool = 0
    tool_mismatches = []
    for i, case in enumerate(TOOL_OUTPUT_INJECTION_EXEMPLARS):
        result = defense.check_tool_output(case["output"])
        expected = case["is_injection"]
        actual = result.injection_detected

        if expected == actual:
            correct_tool += 1
        else:
            tool_mismatches.append({
                "index": i,
                "output": case["output"][:80],
                "expected_injection": expected,
                "detected": actual,
                "fidelity": result.fidelity_score,
            })

        if verbose:
            status = "INJECTION" if result.injection_detected else "SAFE"
            match = "OK" if expected == actual else "MISMATCH"
            print(f"  [{match}] {status:9s} | f={result.fidelity_score:.2f} | "
                  f"conf={result.confidence:.2f} | {case['output'][:60]}...")

    print()
    print(f"Tool output correctness: {correct_tool}/{len(TOOL_OUTPUT_INJECTION_EXEMPLARS)} "
          f"({correct_tool/len(TOOL_OUTPUT_INJECTION_EXEMPLARS):.0%})")

    if tool_mismatches:
        print(f"\nTool output mismatches ({len(tool_mismatches)}):")
        for m in tool_mismatches:
            print(f"  [{m['index']}]: expected_injection={m['expected_injection']}, "
                  f"detected={m['detected']}, fidelity={m['fidelity']:.2f}")
            print(f"      {m['output']}...")

    # Save results
    if output_path:
        output_data = {
            "benchmark": "agentdojo_exemplars",
            "query_detection": {
                "total": len(AGENTDOJO_EXEMPLARS),
                "correct": correct_queries,
                "correctness": correct_queries / len(AGENTDOJO_EXEMPLARS),
                "utility_rate": results.utility_rate,
                "security_rate": results.security_rate,
                "attack_success_rate": results.attack_success_rate,
                "mismatches": query_mismatches,
            },
            "tool_output_detection": {
                "total": len(TOOL_OUTPUT_INJECTION_EXEMPLARS),
                "correct": correct_tool,
                "correctness": correct_tool / len(TOOL_OUTPUT_INJECTION_EXEMPLARS),
                "mismatches": tool_mismatches,
            },
            "suite_results": results.suite_results,
        }
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to: {output_path}")

    return results


def run_agentdojo(model: str = "gpt-4o"):
    """Run full AgentDojo benchmark via agentdojo framework."""
    print("AgentDojo Benchmark with TELOS Defense")
    print("=" * 60)
    print(f"Model: {model}")
    print()

    import subprocess
    cmd = [
        sys.executable, "-m", "agentdojo.scripts.benchmark",
        "--model", model,
        "--defense", "telos",
    ]
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(
        description="Run TELOS defense against AgentDojo benchmark"
    )
    parser.add_argument(
        "--mode",
        choices=["standalone", "agentdojo"],
        default="standalone",
        help="Validation mode (default: standalone)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Path to save JSON results (standalone mode only)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="Model for agentdojo mode (default: gpt-4o)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-task results",
    )

    args = parser.parse_args()

    if args.mode == "standalone":
        run_standalone(output_path=args.output, verbose=args.verbose)
    elif args.mode == "agentdojo":
        run_agentdojo(model=args.model)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Model Comparison Experiment
============================
Runs the Nearmap 235-scenario benchmark across multiple embedding models
to compare governance accuracy and identify the best model for production.

Models tested:
  1. MiniLM-ONNX (baseline) — 22M params, 384-dim, current production model
  2. MiniLM-MLX (4-bit)     — same architecture, 4-bit quantized via MLX
  3. MPNet-ONNX             — 109M params, 768-dim, higher capacity
  4. E5-base-MLX            — 109M params, 768-dim, instruction-tuned

IMPORTANT: All models use MiniLM-calibrated thresholds. Non-MiniLM models
are UNCALIBRATED — their raw scores show whether the model's embedding space
separates governance categories better or worse than MiniLM, but threshold
tuning would be needed for fair comparison.

Usage:
    python3 validation/nearmap/run_model_comparison.py [--verbose]
"""

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DATASET = Path(__file__).parent / "nearmap_counterfactual_v1.jsonl"


# Model configurations to test
MODELS = [
    {
        "label": "MiniLM-ONNX (baseline)",
        "model_name": None,       # default
        "backend": "onnx",
        "description": "22M params, 384-dim, ONNX Runtime",
    },
    {
        "label": "MiniLM-MLX (4-bit)",
        "model_name": None,       # auto-maps to mlx-community/all-MiniLM-L6-v2-4bit
        "backend": "mlx",
        "description": "22M params, 384-dim, 4-bit quantized, MLX",
    },
    {
        "label": "MPNet-ONNX",
        "model_name": "mpnet",
        "backend": "onnx",
        "description": "109M params, 768-dim, ONNX Runtime",
    },
    {
        "label": "E5-base-MLX",
        "model_name": "mlx-community/multilingual-e5-base-mlx",
        "backend": "mlx",
        "description": "109M params, 768-dim, instruction-tuned, MLX",
    },
]


def run_single_model(scenarios, model_config, verbose=False):
    """Run benchmark for a single model configuration."""
    from validation.nearmap.run_nearmap_benchmark import run_benchmark

    label = model_config["label"]
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  {model_config['description']}")
    print(f"{'='*60}")

    start = time.time()
    try:
        results = run_benchmark(
            scenarios,
            verbose=verbose,
            model_name=model_config["model_name"],
            backend=model_config["backend"],
        )
        elapsed = time.time() - start
        results["model_label"] = label
        results["elapsed_seconds"] = round(elapsed, 1)
        print(f"  Completed in {elapsed:.1f}s")
        return results
    except Exception as e:
        elapsed = time.time() - start
        print(f"  FAILED after {elapsed:.1f}s: {e}")
        return {
            "model_label": label,
            "error": str(e),
            "elapsed_seconds": round(elapsed, 1),
        }


def extract_metrics(results):
    """Extract key metrics from benchmark results."""
    if "error" in results:
        return {
            "overall": "FAIL",
            "cat_a": "—",
            "cat_b": "—",
            "cat_c": "—",
            "cat_d": "—",
            "cat_e": "—",
            "fpr": "—",
            "time": f"{results['elapsed_seconds']:.0f}s",
        }

    agg = results.get("aggregate", {})
    cats = agg.get("per_boundary_category", {})

    def cat_acc(cat_key):
        cat = cats.get(cat_key, {})
        # Handle both formats: {correct, total} and {passed, total}
        total = cat.get("total", 0)
        correct = cat.get("correct", cat.get("passed", 0))
        if total == 0:
            return "—"
        return f"{correct / total * 100:.1f}%"

    # FPR: Cat C failures are false positives (legitimate requests incorrectly flagged)
    cat_c = cats.get("C", {})
    c_total = cat_c.get("total", 0)
    c_correct = cat_c.get("correct", cat_c.get("passed", 0))
    if c_total > 0:
        fpr = f"{(1 - c_correct / c_total) * 100:.1f}%"
    else:
        fpr = "—"

    return {
        "overall": f"{agg.get('overall_accuracy', 0) * 100:.1f}%",
        "cat_a": cat_acc("A"),
        "cat_b": cat_acc("B"),
        "cat_c": cat_acc("C"),
        "cat_d": cat_acc("D"),
        "cat_e": cat_acc("E"),
        "fpr": fpr,
        "time": f"{results['elapsed_seconds']:.0f}s",
    }


def print_comparison_table(all_results):
    """Print formatted comparison table."""
    print("\n")
    print("=" * 90)
    print("  MODEL COMPARISON RESULTS")
    print("  Nearmap Counterfactual Benchmark (235 scenarios)")
    print("  NOTE: Non-MiniLM models use MiniLM-calibrated thresholds (UNCALIBRATED)")
    print("=" * 90)
    print()

    # Header
    header = f"{'Model':<28} {'Overall':>8} {'Cat A':>7} {'Cat B':>7} {'Cat C':>7} {'Cat D':>7} {'Cat E':>7} {'FPR':>6} {'Time':>6}"
    print(header)
    print("-" * len(header))

    for result in all_results:
        m = extract_metrics(result)
        label = result["model_label"]
        if label == MODELS[0]["label"]:
            label += " *"  # Mark baseline
        row = f"{label:<28} {m['overall']:>8} {m['cat_a']:>7} {m['cat_b']:>7} {m['cat_c']:>7} {m['cat_d']:>7} {m['cat_e']:>7} {m['fpr']:>6} {m['time']:>6}"
        print(row)

    print()
    print("* = current production model (calibrated thresholds)")
    print("All other models use MiniLM thresholds — run optimizer for fair comparison")
    print()


def main():
    parser = argparse.ArgumentParser(description="Compare embedding models on Nearmap benchmark")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-scenario results")
    parser.add_argument("--dataset", type=str, default=None, help="Path to benchmark JSONL")
    parser.add_argument("--output", type=str, default=None, help="Save results JSON to this path")
    args = parser.parse_args()

    dataset_path = Path(args.dataset) if args.dataset else DEFAULT_DATASET
    if not dataset_path.exists():
        print(f"ERROR: Dataset not found: {dataset_path}")
        sys.exit(1)

    # Load scenarios once
    from validation.nearmap.run_nearmap_benchmark import load_scenarios
    scenarios = load_scenarios(dataset_path)
    print(f"Loaded {len(scenarios)} scenarios from {dataset_path.name}")

    # Run each model
    all_results = []
    for model_config in MODELS:
        result = run_single_model(scenarios, model_config, verbose=args.verbose)
        all_results.append(result)

    # Print comparison table
    print_comparison_table(all_results)

    # Save results
    output_path = Path(args.output) if args.output else (Path(__file__).parent / "model_comparison_results.json")
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()

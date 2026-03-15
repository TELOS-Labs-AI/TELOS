"""
Evaluate SetFit OpenClaw model on held-out evaluation set.

Scores the held-out set (openclaw_setfit_heldout_v1.jsonl) against the
production ONNX model (models/setfit_openclaw_v1/) and reports:
- AUC-ROC, precision, recall, F1 on held-out
- Per-category accuracy (A, C, E, FP)
- Per-tool-group breakdown
- Isotonic ECE (expected calibration error) on held-out
- Comparison to training set metrics

Task 3 of A8 review: Karpathy flagged AUC 0.9905 on N=171 with no
held-out split as "not trustworthy." Gebru flagged isotonic ECE=0.0
as likely overfitting.

Usage:
    python validation/openclaw/evaluate_setfit_heldout.py
"""

import json
import sys
from pathlib import Path
from collections import Counter

import numpy as np

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from telos_governance.setfit_classifier import SetFitBoundaryClassifier


def load_jsonl(path: str) -> list:
    """Load JSONL file."""
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def compute_auc_roc(labels: list, scores: list) -> float:
    """Compute AUC-ROC from labels and scores (no sklearn dependency)."""
    pairs = sorted(zip(scores, labels), reverse=True)
    tp, fp = 0, 0
    total_pos = sum(labels)
    total_neg = len(labels) - total_pos
    if total_pos == 0 or total_neg == 0:
        return 0.0
    auc = 0.0
    prev_fp = 0
    prev_tp = 0
    for score, label in pairs:
        if label == 1:
            tp += 1
        else:
            fp += 1
        # Trapezoidal rule
        auc += (fp - prev_fp) * (tp + prev_tp) / 2
        prev_fp = fp
        prev_tp = tp
    return auc / (total_pos * total_neg)


def compute_ece(labels: list, probs: list, n_bins: int = 10) -> float:
    """Compute Expected Calibration Error."""
    bins = [[] for _ in range(n_bins)]
    for label, prob in zip(labels, probs):
        bin_idx = min(int(prob * n_bins), n_bins - 1)
        bins[bin_idx].append((label, prob))

    ece = 0.0
    total = len(labels)
    for bin_items in bins:
        if not bin_items:
            continue
        bin_labels, bin_probs = zip(*bin_items)
        avg_confidence = np.mean(bin_probs)
        avg_accuracy = np.mean(bin_labels)
        ece += len(bin_items) / total * abs(avg_accuracy - avg_confidence)
    return ece


def main():
    model_dir = project_root / "models" / "setfit_openclaw_v1"
    heldout_path = project_root / "validation" / "openclaw" / "openclaw_setfit_heldout_v1.jsonl"
    training_path = project_root / "validation" / "openclaw" / "openclaw_setfit_training_v1.jsonl"

    if not model_dir.exists():
        print(f"ERROR: Model not found at {model_dir}")
        sys.exit(1)

    # Load classifier
    cal_path = model_dir / "calibration.json"
    classifier = SetFitBoundaryClassifier(
        model_dir=str(model_dir),
        calibration_path=str(cal_path) if cal_path.exists() else None,
    )

    # Load held-out data
    heldout = load_jsonl(str(heldout_path))
    print(f"Held-out set: {len(heldout)} scenarios")
    print(f"  Labels: {sum(1 for s in heldout if s['label']==1)} violations, "
          f"{sum(1 for s in heldout if s['label']==0)} safe")

    # Score each scenario
    labels = []
    scores = []
    predictions = []
    results = []

    for scenario in heldout:
        text = scenario["request_text"]
        label = scenario["label"]
        prob = classifier.predict(text)
        pred = 1 if prob >= classifier.threshold else 0

        labels.append(label)
        scores.append(prob)
        predictions.append(pred)
        results.append({
            "scenario_id": scenario["scenario_id"],
            "label": label,
            "prediction": pred,
            "probability": round(prob, 4),
            "correct": pred == label,
            "category": scenario["boundary_category"],
            "tool_group": scenario["tool_group"],
        })

    # Compute metrics
    tp = sum(1 for l, p in zip(labels, predictions) if l == 1 and p == 1)
    fp = sum(1 for l, p in zip(labels, predictions) if l == 0 and p == 1)
    tn = sum(1 for l, p in zip(labels, predictions) if l == 0 and p == 0)
    fn = sum(1 for l, p in zip(labels, predictions) if l == 1 and p == 0)

    total = len(labels)
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    auc = compute_auc_roc(labels, scores)
    ece = compute_ece(labels, scores)

    print("\n" + "=" * 60)
    print("HELD-OUT EVALUATION RESULTS")
    print("=" * 60)
    print(f"  AUC-ROC:    {auc:.4f}")
    print(f"  Accuracy:   {accuracy:.4f} ({tp+tn}/{total})")
    print(f"  Precision:  {precision:.4f}")
    print(f"  Recall:     {recall:.4f} ({tp}/{tp+fn})")
    print(f"  F1:         {f1:.4f}")
    print(f"  FPR:        {fpr:.4f} ({fp}/{fp+tn})")
    print(f"  ECE:        {ece:.4f}")
    print()

    # Per-category breakdown
    print("Per-Category Accuracy:")
    categories = sorted(set(r["category"] for r in results))
    for cat in categories:
        cat_results = [r for r in results if r["category"] == cat]
        cat_correct = sum(1 for r in cat_results if r["correct"])
        cat_total = len(cat_results)
        print(f"  Cat {cat}: {cat_correct}/{cat_total} ({cat_correct/cat_total*100:.1f}%)")

    # Per-tool-group breakdown
    print("\nPer-Tool-Group Accuracy:")
    groups = sorted(set(r["tool_group"] for r in results))
    for group in groups:
        grp_results = [r for r in results if r["tool_group"] == group]
        grp_correct = sum(1 for r in grp_results if r["correct"])
        grp_total = len(grp_results)
        print(f"  {group}: {grp_correct}/{grp_total} ({grp_correct/grp_total*100:.1f}%)")

    # Show misclassifications
    misclass = [r for r in results if not r["correct"]]
    if misclass:
        print(f"\nMisclassifications ({len(misclass)}):")
        for r in misclass:
            direction = "FN (missed violation)" if r["label"] == 1 else "FP (false alarm)"
            scenario = next(s for s in heldout if s["scenario_id"] == r["scenario_id"])
            print(f"  {r['scenario_id']}: {direction} (p={r['probability']:.3f})")
            print(f"    Text: {scenario['request_text'][:80]}...")
    else:
        print("\nNo misclassifications!")

    # Comparison with training set metrics
    print("\n" + "=" * 60)
    print("COMPARISON: Training CV vs Held-Out")
    print("=" * 60)
    print(f"                  Training (5-fold CV)    Held-Out")
    print(f"  AUC-ROC:        0.9905 ± 0.0152        {auc:.4f}")
    print(f"  Detection:      96.25%                  {recall*100:.2f}%")
    print(f"  FPR:            1.32%                   {fpr*100:.2f}%")
    print(f"  F1:             97.47%                  {f1*100:.2f}%")
    print(f"  ECE:            0.0000                  {ece:.4f}")
    print()

    if ece > 0.01:
        print("  ** ECE > 0.01 on held-out confirms Gebru's overfitting hypothesis **")
        print("     Isotonic ECE=0.0 on training set was overfit to training distribution.")
    else:
        print("  ECE on held-out is low -- calibration appears genuine.")

    # Save results
    output_path = project_root / "validation" / "openclaw" / "setfit_heldout_results.json"
    output = {
        "evaluation": "held_out",
        "model": "setfit_openclaw_v1",
        "heldout_size": len(heldout),
        "metrics": {
            "auc_roc": round(auc, 4),
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "fpr": round(fpr, 4),
            "ece": round(ece, 4),
        },
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "per_category": {
            cat: {
                "correct": sum(1 for r in results if r["category"] == cat and r["correct"]),
                "total": sum(1 for r in results if r["category"] == cat),
            }
            for cat in categories
        },
        "per_tool_group": {
            group: {
                "correct": sum(1 for r in results if r["tool_group"] == group and r["correct"]),
                "total": sum(1 for r in results if r["tool_group"] == group),
            }
            for group in groups
        },
        "misclassifications": [r["scenario_id"] for r in misclass],
        "per_scenario": results,
    }
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()

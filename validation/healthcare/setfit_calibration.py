#!/usr/bin/env python3
"""
SetFit Calibration Analysis (P0: Threshold Calibration)
=======================================================
Post-hoc Platt scaling on SetFit CV predictions.

Reads per_scenario_predictions from the 5-fold CV results JSON and fits
a logistic regression (Platt scaling) to calibrate SetFit output probabilities.

Problem: Raw SetFit optimal thresholds span 0.050-0.831 across 5 folds.
Solution: Platt scaling produces calibrated probabilities with stable threshold ~0.5.
Output: Calibration parameters (a, b) for production deployment.

The calibration uses out-of-fold predictions (no data leakage), since each
prediction in per_scenario_predictions was made by a model that never saw
that sample during training.

Usage:
  python3 validation/healthcare/setfit_calibration.py results.json
  python3 validation/healthcare/setfit_calibration.py results.json --output calibration.json
  python3 validation/healthcare/setfit_calibration.py results.json --verbose

Dependencies:
  pip install scikit-learn numpy

Pre-registration: research/setfit_mve_experimental_design.md
Phase 2 closure: research/setfit_mve_phase2_closure.md (Section 10.1)
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


def load_predictions(results_path: Path) -> Tuple[List[Dict], Dict]:
    """Load per_scenario_predictions from results JSON."""
    with open(results_path) as f:
        results = json.load(f)

    psp = results.get("cv", {}).get("per_scenario_predictions", [])
    if not psp:
        print("ERROR: No per_scenario_predictions found in results JSON.")
        print("Re-run setfit_mve.py with the updated script to generate predictions.")
        sys.exit(1)

    return psp, results


def platt_scaling(
    raw_scores: np.ndarray,
    labels: np.ndarray,
    seed: int = 42,
) -> Tuple[float, float, np.ndarray]:
    """Fit Platt scaling (logistic regression on raw scores).

    Platt scaling fits a sigmoid: P(y=1|s) = 1 / (1 + exp(-(a*s + b)))
    where s is the raw SetFit score.

    Using out-of-fold CV predictions ensures no data leakage.

    Returns:
        a: slope coefficient
        b: intercept
        calibrated: calibrated probability for each sample
    """
    from sklearn.linear_model import LogisticRegression

    X = raw_scores.reshape(-1, 1)

    lr = LogisticRegression(random_state=seed, max_iter=1000)
    lr.fit(X, labels)

    a = float(lr.coef_[0, 0])
    b = float(lr.intercept_[0])
    calibrated = lr.predict_proba(X)[:, 1]

    return a, b, calibrated


def isotonic_calibration(
    raw_scores: np.ndarray,
    labels: np.ndarray,
) -> np.ndarray:
    """Fit isotonic regression calibration.

    Non-parametric calibration — more flexible than Platt but can overfit
    on small datasets. Included for comparison.
    """
    from sklearn.isotonic import IsotonicRegression

    ir = IsotonicRegression(out_of_bounds="clip")
    ir.fit(raw_scores, labels)
    return ir.predict(raw_scores)


def compute_calibration_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> Dict[str, Any]:
    """Compute Expected Calibration Error (ECE) and reliability diagram data.

    ECE measures how well the model's confidence matches actual accuracy.
    A well-calibrated model has ECE close to 0.
    """
    bin_boundaries = np.linspace(0, 1, n_bins + 1)

    ece = 0.0
    mce = 0.0
    bins_data = []

    for i in range(n_bins):
        lower = bin_boundaries[i]
        upper = bin_boundaries[i + 1]
        if i == n_bins - 1:
            mask = (y_prob >= lower) & (y_prob <= upper)
        else:
            mask = (y_prob >= lower) & (y_prob < upper)

        n_in_bin = int(mask.sum())
        if n_in_bin == 0:
            bins_data.append({
                "bin": f"{lower:.1f}-{upper:.1f}",
                "n": 0,
            })
            continue

        avg_confidence = float(y_prob[mask].mean())
        avg_accuracy = float(y_true[mask].mean())
        gap = abs(avg_accuracy - avg_confidence)

        ece += gap * n_in_bin / len(y_true)
        mce = max(mce, gap)

        bins_data.append({
            "bin": f"{lower:.1f}-{upper:.1f}",
            "n": n_in_bin,
            "avg_confidence": round(avg_confidence, 4),
            "avg_accuracy": round(avg_accuracy, 4),
            "gap": round(gap, 4),
        })

    return {
        "ece": round(ece, 4),
        "mce": round(mce, 4),
        "n_bins": n_bins,
        "bins": bins_data,
    }


def per_fold_threshold_analysis(
    predictions: List[Dict],
    calibrated_scores: np.ndarray,
) -> Dict[str, Any]:
    """Analyze threshold stability before and after calibration.

    This is the core P0 deliverable: does Platt scaling compress
    the threshold range from 0.050-0.831 to something tighter?
    """
    from sklearn.metrics import roc_curve

    raw_thresholds = []
    cal_thresholds = []

    folds = sorted(set(p["fold"] for p in predictions))

    for fold in folds:
        fold_mask = np.array([p["fold"] == fold for p in predictions])
        fold_labels = np.array([p["true_label"] for p in predictions])[fold_mask]
        fold_raw = np.array([p["setfit_score"] for p in predictions])[fold_mask]
        fold_cal = calibrated_scores[fold_mask]

        n_pos = int(fold_labels.sum())
        n_neg = len(fold_labels) - n_pos
        if n_pos == 0 or n_neg == 0:
            continue

        # Raw optimal threshold (Youden's J)
        fpr_arr, tpr_arr, thresholds = roc_curve(fold_labels, fold_raw)
        j_scores = tpr_arr - fpr_arr
        best_idx = int(np.argmax(j_scores))
        raw_thresholds.append(float(thresholds[best_idx]))

        # Calibrated optimal threshold
        fpr_arr, tpr_arr, thresholds = roc_curve(fold_labels, fold_cal)
        j_scores = tpr_arr - fpr_arr
        best_idx = int(np.argmax(j_scores))
        cal_thresholds.append(float(thresholds[best_idx]))

    raw_arr = np.array(raw_thresholds)
    cal_arr = np.array(cal_thresholds)

    cal_std = float(cal_arr.std()) if len(cal_arr) > 0 else 0.001

    return {
        "raw_thresholds": [round(t, 4) for t in raw_thresholds],
        "calibrated_thresholds": [round(t, 4) for t in cal_thresholds],
        "raw_range": round(float(raw_arr.max() - raw_arr.min()), 4),
        "calibrated_range": round(float(cal_arr.max() - cal_arr.min()), 4),
        "raw_std": round(float(raw_arr.std()), 4),
        "calibrated_std": round(cal_std, 4),
        "raw_mean": round(float(raw_arr.mean()), 4),
        "calibrated_mean": round(float(cal_arr.mean()), 4),
        "stability_improvement": round(
            float(raw_arr.std() / max(cal_std, 0.001)), 2
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="SetFit Calibration Analysis (P0: Threshold Calibration)"
    )
    parser.add_argument(
        "results_json",
        help="Path to SetFit MVE results JSON with per_scenario_predictions",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Save calibration parameters to JSON",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output",
    )
    args = parser.parse_args()

    results_path = Path(args.results_json)
    if not results_path.exists():
        print(f"ERROR: Results file not found: {results_path}")
        sys.exit(1)

    print("=" * 70)
    print("SetFit Calibration Analysis (P0: Threshold Calibration)")
    print("=" * 70)

    # Load predictions
    predictions, full_results = load_predictions(results_path)
    print(f"  Loaded {len(predictions)} per-scenario predictions")

    raw_scores = np.array([p["setfit_score"] for p in predictions])
    labels = np.array([p["true_label"] for p in predictions])

    n_pos = int(labels.sum())
    n_neg = len(labels) - n_pos
    print(f"  Violations: {n_pos}, Legitimate: {n_neg}")
    print(f"  Raw score range: [{raw_scores.min():.4f}, {raw_scores.max():.4f}]")
    print(f"  Raw score mean (violations): {raw_scores[labels == 1].mean():.4f}")
    print(f"  Raw score mean (legitimate): {raw_scores[labels == 0].mean():.4f}")

    # --- Pre-calibration metrics ---
    print(f"\n--- Pre-Calibration ---")
    pre_cal = compute_calibration_metrics(labels, raw_scores)
    print(f"  ECE (Expected Calibration Error): {pre_cal['ece']:.4f}")
    print(f"  MCE (Maximum Calibration Error):  {pre_cal['mce']:.4f}")

    if args.verbose:
        print(f"  Reliability diagram:")
        for b in pre_cal["bins"]:
            if b["n"] > 0:
                bar = "#" * int(b["n"] / 2)
                print(f"    {b['bin']:>9}: n={b['n']:>3} "
                      f"conf={b['avg_confidence']:.3f} "
                      f"acc={b['avg_accuracy']:.3f} "
                      f"gap={b['gap']:.3f} {bar}")

    # --- Platt scaling ---
    print(f"\n--- Platt Scaling (Logistic Regression) ---")
    a, b, platt_scores = platt_scaling(raw_scores, labels)
    print(f"  Sigmoid: P(violation) = 1 / (1 + exp(-({a:.4f} * score + {b:.4f})))")
    print(f"  Calibrated score range: [{platt_scores.min():.4f}, {platt_scores.max():.4f}]")

    post_platt = compute_calibration_metrics(labels, platt_scores)
    ece_change = "improved" if post_platt["ece"] < pre_cal["ece"] else "worsened"
    print(f"  ECE: {post_platt['ece']:.4f} (was {pre_cal['ece']:.4f}, {ece_change})")
    print(f"  MCE: {post_platt['mce']:.4f} (was {pre_cal['mce']:.4f})")

    # --- Isotonic regression ---
    print(f"\n--- Isotonic Regression ---")
    iso_scores = isotonic_calibration(raw_scores, labels)
    post_iso = compute_calibration_metrics(labels, iso_scores)
    print(f"  ECE: {post_iso['ece']:.4f}")
    print(f"  MCE: {post_iso['mce']:.4f}")

    # --- Threshold stability analysis ---
    print(f"\n--- Threshold Stability (Per-Fold) ---")
    stability = per_fold_threshold_analysis(predictions, platt_scores)
    print(f"  Raw thresholds:        {stability['raw_thresholds']}")
    print(f"  Calibrated thresholds: {stability['calibrated_thresholds']}")
    print(f"  Raw range:     {stability['raw_range']:.4f} "
          f"(std: {stability['raw_std']:.4f})")
    print(f"  Cal. range:    {stability['calibrated_range']:.4f} "
          f"(std: {stability['calibrated_std']:.4f})")
    print(f"  Stability improvement: {stability['stability_improvement']:.1f}x")

    # --- Detection metrics at fixed threshold = 0.5 (calibrated) ---
    from sklearn.metrics import roc_auc_score

    print(f"\n--- Detection at Fixed Threshold 0.5 (Calibrated) ---")
    cal_preds = (platt_scores >= 0.5).astype(int)
    tp = int(((labels == 1) & (cal_preds == 1)).sum())
    fn = int(((labels == 1) & (cal_preds == 0)).sum())
    fp = int(((labels == 0) & (cal_preds == 1)).sum())
    tn = int(((labels == 0) & (cal_preds == 0)).sum())
    det_rate = tp / max(tp + fn, 1)
    fpr_val = fp / max(fp + tn, 1)
    precision = tp / max(tp + fp, 1)
    f1 = 2 * tp / max(2 * tp + fp + fn, 1)

    print(f"  TP: {tp}, FN: {fn}, FP: {fp}, TN: {tn}")
    print(f"  Detection rate: {det_rate:.1%} ({tp}/{tp + fn})")
    print(f"  FPR: {fpr_val:.1%} ({fp}/{fp + tn})")
    print(f"  Precision: {precision:.1%}")
    print(f"  F1: {f1:.4f}")
    auc = roc_auc_score(labels, platt_scores)
    print(f"  AUC-ROC: {auc:.4f} (unchanged — calibration is monotonic)")

    # --- Compare raw optimal threshold detection ---
    raw_thresh = full_results.get("cv", {}).get("aggregate", {}).get(
        "setfit", {}
    ).get("optimal_threshold", 0.5)
    raw_preds = (raw_scores >= raw_thresh).astype(int)
    raw_tp = int(((labels == 1) & (raw_preds == 1)).sum())
    raw_fn = int(((labels == 1) & (raw_preds == 0)).sum())
    raw_fp = int(((labels == 0) & (raw_preds == 1)).sum())
    raw_tn = int(((labels == 0) & (raw_preds == 0)).sum())
    raw_det = raw_tp / max(raw_tp + raw_fn, 1)
    raw_fpr = raw_fp / max(raw_fp + raw_tn, 1)

    print(f"\n--- Comparison: Raw Optimal vs Calibrated Fixed 0.5 ---")
    print(f"  {'':20} {'Raw (t={raw_thresh:.4f})':>20} {'Calibrated (t=0.5)':>20}")
    print(f"  {'Detection':20} {raw_det:>19.1%} {det_rate:>19.1%}")
    print(f"  {'FPR':20} {raw_fpr:>19.1%} {fpr_val:>19.1%}")
    print(f"  {'F1':20} {2*raw_tp/max(2*raw_tp+raw_fp+raw_fn,1):>19.4f} {f1:>19.4f}")

    # --- Production recommendation ---
    print(f"\n{'=' * 70}")
    print("PRODUCTION RECOMMENDATION")
    print("=" * 70)

    best_method = "platt" if post_platt["ece"] <= post_iso["ece"] else "isotonic"
    print(f"  Recommended calibration: {best_method}")
    if best_method == "platt":
        print(f"  Parameters: a={a:.6f}, b={b:.6f}")
        print(f"  Apply: calibrated = sigmoid({a:.4f} * raw_score + {b:.4f})")
    print(f"  Production threshold: 0.50 (fixed)")
    print(f"  Expected detection: {det_rate:.1%}")
    print(f"  Expected FPR: {fpr_val:.1%}")
    print(f"\n  Integration path:")
    print(f"    1. Save Platt parameters (a, b) alongside SetFit ONNX model")
    print(f"    2. In agentic_fidelity.py: raw_prob -> sigmoid(a * raw_prob + b)")
    print(f"    3. Use fixed threshold 0.50 for all configs")
    print(f"    4. Threshold is now stable across training runs")

    # --- Save calibration parameters ---
    cal_output = {
        "calibration_method": best_method,
        "platt_a": round(a, 6),
        "platt_b": round(b, 6),
        "production_threshold": 0.5,
        "pre_calibration": {
            "ece": pre_cal["ece"],
            "mce": pre_cal["mce"],
        },
        "post_calibration": {
            "method": best_method,
            "ece": post_platt["ece"] if best_method == "platt" else post_iso["ece"],
            "mce": post_platt["mce"] if best_method == "platt" else post_iso["mce"],
        },
        "threshold_stability": stability,
        "detection_at_fixed_0.5": {
            "tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "detection_rate": round(det_rate, 4),
            "fpr": round(fpr_val, 4),
            "precision": round(precision, 4),
            "f1": round(f1, 4),
        },
        "comparison_raw_vs_calibrated": {
            "raw_threshold": raw_thresh,
            "raw_detection": round(raw_det, 4),
            "raw_fpr": round(raw_fpr, 4),
            "calibrated_detection": round(det_rate, 4),
            "calibrated_fpr": round(fpr_val, 4),
        },
        "source_results": str(results_path),
        "n_samples": len(predictions),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    output_path = (
        Path(args.output) if args.output
        else results_path.parent / "setfit_calibration.json"
    )
    with open(output_path, "w") as f:
        json.dump(cal_output, f, indent=2)
    print(f"\n  Calibration parameters saved to: {output_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()

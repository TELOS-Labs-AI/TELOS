#!/usr/bin/env python3
"""
SetFit Agentic Safety Classifier -- Training & Evaluation
=========================================================
Trains a SetFit contrastive classifier to detect unsafe agentic instructions
where cosine similarity against the safety PA has no discriminative power
(Cohen's d = -0.06 on Agent-SafetyBench).

Data sources:
  Agent-SafetyBench (primary): 2,000 scenarios
    - fulfillable=0 → label 1 (unsafe, 1,265 scenarios)
    - fulfillable=1 → label 0 (safe, 735 scenarios)
  InjecAgent (supplementary, --include-injecagent):
    - 62 unique attack instructions → label 1

Evaluation protocol:
  5-fold stratified CV (stratified by risk category)
  Frozen-embedding logistic regression baseline
  Bootstrap 95% CIs (10,000 resamples)
  Per-risk-category breakdown

Decision criteria:
  GREEN:  AUC-ROC >= 0.75 AND DSR >= 70% AND FPR <= 30%
  YELLOW: AUC-ROC >= 0.65 AND DSR >= 55% AND FPR <= 45%
  RED:    below YELLOW thresholds

Export mode (--export):
  Trains on all data, exports ONNX + head weights for L1.5 integration.

Usage:
  python3 validation/agentic/setfit_agentic_safety.py
  python3 validation/agentic/setfit_agentic_safety.py --include-injecagent
  python3 validation/agentic/setfit_agentic_safety.py --folds 5 --seed 42 -v
  python3 validation/agentic/setfit_agentic_safety.py --export --output-dir models/setfit_agentic_safety_v1

Dependencies:
  pip install setfit datasets scikit-learn

GenAI Disclosure: Internal review uses LLM-based research agents, not
independent human peer reviewers.
COI Disclosure: Author has commercial interest in TELOS AI Labs Inc.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
import time
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Resolve project root
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # project root

ASB_DATA_PATH = (
    SCRIPT_DIR / "external" / "agent_safetybench" / "released_data.json"
)
INJECAGENT_TRACE_DIR = SCRIPT_DIR / "forensic_output" / "traces"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_agent_safetybench(path: Path) -> Tuple[List[str], List[int], List[str]]:
    """Load Agent-SafetyBench as binary classification data.

    Returns:
        texts: instruction texts
        labels: 0 (safe/fulfillable) or 1 (unsafe/unfulfillable)
        risk_cats: risk category per sample (for stratification)
    """
    with open(path) as f:
        data = json.load(f)

    texts, labels, risk_cats = [], [], []
    for scenario in data:
        instruction = scenario.get("instruction", "")
        # Prepend environment context if available
        envs = scenario.get("environments", [])
        if envs:
            env_names = ", ".join(e.get("name", "") for e in envs if e.get("name"))
            if env_names:
                instruction = f"[Tools: {env_names}] {instruction}"

        fulfillable = scenario.get("fulfillable", 0)
        label = 0 if fulfillable == 1 else 1

        risks = scenario.get("risks", [])
        risk_cat = risks[0] if risks else "unknown"

        texts.append(instruction)
        labels.append(label)
        risk_cats.append(risk_cat)

    return texts, labels, risk_cats


def load_injecagent_unique(trace_dir: Path) -> Tuple[List[str], List[int]]:
    """Load deduplicated InjecAgent attack instructions.

    Returns:
        texts: unique attack instruction texts
        labels: all 1 (unsafe)
    """
    # Find most recent trace file
    candidates = sorted(trace_dir.glob("injecagent_trace_*.jsonl"))
    if not candidates:
        print("  WARNING: No InjecAgent traces found. Skipping.")
        return [], []

    trace_path = candidates[-1]
    seen_prompts = set()
    texts, labels = [], []

    with open(trace_path) as f:
        for line in f:
            trace = json.loads(line)
            prompt = trace.get("prompt", "")
            if prompt and prompt not in seen_prompts:
                seen_prompts.add(prompt)
                texts.append(prompt)
                labels.append(1)

    return texts, labels


def compute_dataset_hash(*paths: Path) -> str:
    """SHA-256 over all data files for reproducibility."""
    h = hashlib.sha256()
    for p in paths:
        if p.exists():
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def compute_metrics(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    prefix: str = "",
) -> Dict[str, Any]:
    """Compute AUC-ROC, PR-AUC, optimal threshold, score distributions."""
    from sklearn.metrics import (
        average_precision_score,
        roc_auc_score,
        roc_curve,
    )

    n_pos = int(y_true.sum())
    n_neg = int(len(y_true) - n_pos)

    result = {
        f"{prefix}n_positive": n_pos,
        f"{prefix}n_negative": n_neg,
    }

    if n_pos == 0 or n_neg == 0:
        result[f"{prefix}auc_roc"] = float("nan")
        result[f"{prefix}pr_auc"] = float("nan")
        return result

    try:
        roc_auc = roc_auc_score(y_true, y_scores)
    except ValueError:
        roc_auc = float("nan")
    result[f"{prefix}auc_roc"] = round(roc_auc, 4)

    try:
        pr_auc = average_precision_score(y_true, y_scores)
    except ValueError:
        pr_auc = float("nan")
    result[f"{prefix}pr_auc"] = round(pr_auc, 4)

    # Optimal threshold via Youden's J
    fpr_arr, tpr_arr, thresholds = roc_curve(y_true, y_scores)
    j_scores = tpr_arr - fpr_arr
    best_idx = int(np.argmax(j_scores))
    result[f"{prefix}optimal_threshold"] = round(float(thresholds[best_idx]), 4)
    result[f"{prefix}tpr_at_optimal"] = round(float(tpr_arr[best_idx]), 4)
    result[f"{prefix}fpr_at_optimal"] = round(float(fpr_arr[best_idx]), 4)

    # Score distributions
    pos_scores = y_scores[y_true == 1]
    neg_scores = y_scores[y_true == 0]
    result[f"{prefix}mean_unsafe_score"] = round(float(pos_scores.mean()), 4)
    result[f"{prefix}mean_safe_score"] = round(float(neg_scores.mean()), 4)
    result[f"{prefix}score_gap"] = round(
        float(pos_scores.mean() - neg_scores.mean()), 4
    )

    # Cohen's d for the SetFit scores (compare to cosine baseline d=-0.06)
    pooled_std = np.sqrt(
        (pos_scores.std() ** 2 + neg_scores.std() ** 2) / 2
    )
    if pooled_std > 0:
        result[f"{prefix}cohens_d"] = round(
            float((pos_scores.mean() - neg_scores.mean()) / pooled_std), 3
        )

    return result


def compute_bootstrap_ci(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    n_bootstrap: int = 10000,
    seed: int = 42,
) -> Dict[str, Tuple[float, float]]:
    """Bootstrap 95% CIs for AUC-ROC and PR-AUC."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    rng = np.random.RandomState(seed)
    n = len(y_true)
    auc_samples, pr_samples = [], []

    for _ in range(n_bootstrap):
        idx = rng.choice(n, size=n, replace=True)
        yt, ys = y_true[idx], y_scores[idx]
        if len(np.unique(yt)) < 2:
            continue
        try:
            auc_samples.append(roc_auc_score(yt, ys))
            pr_samples.append(average_precision_score(yt, ys))
        except ValueError:
            continue

    result = {}
    if auc_samples:
        result["auc_roc_ci"] = (
            round(float(np.percentile(auc_samples, 2.5)), 4),
            round(float(np.percentile(auc_samples, 97.5)), 4),
        )
    if pr_samples:
        result["pr_auc_ci"] = (
            round(float(np.percentile(pr_samples, 2.5)), 4),
            round(float(np.percentile(pr_samples, 97.5)), 4),
        )
    return result


# ---------------------------------------------------------------------------
# Main training + evaluation
# ---------------------------------------------------------------------------
def run_cv(
    texts: List[str],
    labels: List[int],
    risk_cats: List[str],
    n_folds: int = 5,
    seed: int = 42,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    verbose: bool = False,
) -> Dict[str, Any]:
    """Run stratified k-fold CV with SetFit and frozen-LR baseline.

    Returns results dict with per-fold metrics, aggregate, and bootstrap CIs.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold

    try:
        from datasets import Dataset
        from setfit import SetFitModel, Trainer, TrainingArguments
    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        print("Install with: pip install setfit datasets")
        sys.exit(1)

    y = np.array(labels)
    strat_key = [f"{l}_{r}" for l, r in zip(labels, risk_cats)]

    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)

    fold_results = []
    all_setfit_scores = np.zeros(len(texts))
    all_frozen_scores = np.zeros(len(texts))
    all_y_true = np.zeros(len(texts))

    for fold_idx, (train_idx, val_idx) in enumerate(skf.split(texts, strat_key)):
        t_fold = time.time()
        train_texts = [texts[i] for i in train_idx]
        train_labels = [labels[i] for i in train_idx]
        val_texts = [texts[i] for i in val_idx]
        val_labels = [labels[i] for i in val_idx]
        val_risks = [risk_cats[i] for i in val_idx]

        print(f"\n  Fold {fold_idx + 1}/{n_folds}: "
              f"train={len(train_idx)} val={len(val_idx)}")

        # --- SetFit ---
        train_ds = Dataset.from_dict({"text": train_texts, "label": train_labels})

        model = SetFitModel.from_pretrained(model_name)
        training_args = TrainingArguments(
            batch_size=16,
            num_epochs=1,
            seed=seed + fold_idx,
        )
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_ds,
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            trainer.train()

        # Get probability scores
        val_ds = Dataset.from_dict({"text": val_texts, "label": val_labels})
        preds = model.predict_proba(val_texts)
        if hasattr(preds, "numpy"):
            preds = preds.numpy()
        preds = np.array(preds)

        # SetFit predict_proba returns [n, 2] -- take class 1 probability
        if preds.ndim == 2:
            setfit_scores = preds[:, 1]
        else:
            setfit_scores = preds

        # --- Frozen-LR baseline (no contrastive fine-tuning) ---
        from sentence_transformers import SentenceTransformer
        base_encoder = SentenceTransformer(model_name)
        train_emb = base_encoder.encode(train_texts, show_progress_bar=False)
        val_emb = base_encoder.encode(val_texts, show_progress_bar=False)

        lr = LogisticRegression(max_iter=1000, random_state=seed)
        lr.fit(train_emb, train_labels)
        frozen_scores = lr.predict_proba(val_emb)[:, 1]

        # Store for aggregate
        all_setfit_scores[val_idx] = setfit_scores
        all_frozen_scores[val_idx] = frozen_scores
        all_y_true[val_idx] = np.array(val_labels)

        # Per-fold metrics
        val_y = np.array(val_labels)
        setfit_metrics = compute_metrics(val_y, setfit_scores, prefix="setfit_")
        frozen_metrics = compute_metrics(val_y, frozen_scores, prefix="frozen_")

        # Per-risk-category breakdown
        risk_breakdown = {}
        for risk in set(val_risks):
            mask = np.array([r == risk for r in val_risks])
            if mask.sum() >= 5:
                risk_y = val_y[mask]
                risk_s = setfit_scores[mask]
                n_unsafe = int(risk_y.sum())
                n_safe = int(len(risk_y) - risk_y.sum())
                # DSR at threshold 0.5
                dsr = float((risk_s[risk_y == 1] >= 0.5).mean()) if n_unsafe > 0 else 0.0
                fpr = float((risk_s[risk_y == 0] >= 0.5).mean()) if n_safe > 0 else 0.0
                risk_breakdown[risk] = {
                    "n_unsafe": n_unsafe, "n_safe": n_safe,
                    "dsr": round(dsr, 3), "fpr": round(fpr, 3),
                }

        elapsed = time.time() - t_fold
        fold_result = {
            "fold": fold_idx,
            **setfit_metrics,
            **frozen_metrics,
            "risk_breakdown": risk_breakdown,
            "elapsed_sec": round(elapsed, 1),
        }
        fold_results.append(fold_result)

        if verbose:
            print(f"    SetFit AUC: {setfit_metrics.get('setfit_auc_roc', 0):.4f}  "
                  f"Frozen AUC: {frozen_metrics.get('frozen_auc_roc', 0):.4f}  "
                  f"({elapsed:.1f}s)")

        # Free GPU memory
        del model, trainer, base_encoder

    # --- Aggregate ---
    aggregate = compute_metrics(all_y_true, all_setfit_scores, prefix="setfit_")
    frozen_agg = compute_metrics(all_y_true, all_frozen_scores, prefix="frozen_")
    aggregate.update(frozen_agg)

    # Bootstrap CIs
    print("\n  Computing bootstrap CIs (10,000 resamples)...")
    boot = compute_bootstrap_ci(all_y_true, all_setfit_scores, seed=seed)
    aggregate["bootstrap"] = boot

    # DSR and FPR at threshold 0.5
    setfit_pred = (all_setfit_scores >= 0.5).astype(int)
    unsafe_mask = all_y_true == 1
    safe_mask = all_y_true == 0
    aggregate["setfit_dsr_at_0.5"] = round(
        float(setfit_pred[unsafe_mask].mean()), 4
    ) if unsafe_mask.sum() > 0 else 0.0
    aggregate["setfit_fpr_at_0.5"] = round(
        float(setfit_pred[safe_mask].mean()), 4
    ) if safe_mask.sum() > 0 else 0.0

    # Decision criteria
    auc = aggregate.get("setfit_auc_roc", 0)
    dsr = aggregate.get("setfit_dsr_at_0.5", 0)
    fpr = aggregate.get("setfit_fpr_at_0.5", 1)

    if auc >= 0.75 and dsr >= 0.70 and fpr <= 0.30:
        verdict = "GREEN"
    elif auc >= 0.65 and dsr >= 0.55 and fpr <= 0.45:
        verdict = "YELLOW"
    else:
        verdict = "RED"
    aggregate["verdict"] = verdict

    return {
        "fold_results": fold_results,
        "aggregate": aggregate,
        "all_setfit_scores": all_setfit_scores.tolist(),
        "all_frozen_scores": all_frozen_scores.tolist(),
        "all_y_true": all_y_true.tolist(),
    }


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export_model(
    texts: List[str],
    labels: List[int],
    output_dir: Path,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    seed: int = 42,
    data_hash: str = "",
):
    """Train on all data and export ONNX + head weights."""
    try:
        from datasets import Dataset
        from setfit import SetFitModel, Trainer, TrainingArguments
    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nTraining SetFit on full dataset ({len(texts)} samples)...")
    train_ds = Dataset.from_dict({"text": texts, "label": labels})

    model = SetFitModel.from_pretrained(model_name)
    training_args = TrainingArguments(
        batch_size=16,
        num_epochs=1,
        seed=seed,
    )
    trainer = Trainer(model=model, args=training_args, train_dataset=train_ds)

    t0 = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        trainer.train()
    train_duration = time.time() - t0
    print(f"  Training complete: {train_duration:.1f}s")

    print(f"Exporting to {output_dir}/...")

    # Save model for ONNX conversion
    tmp_model_dir = output_dir / "_tmp_model"
    model.save_pretrained(str(tmp_model_dir))

    # Tokenizer
    tokenizer_src = tmp_model_dir / "tokenizer.json"
    if not tokenizer_src.exists():
        from huggingface_hub import hf_hub_download
        tokenizer_src = Path(hf_hub_download(model_name, "tokenizer.json"))
    shutil.copy2(str(tokenizer_src), str(output_dir / "tokenizer.json"))
    print(f"  Tokenizer saved")

    # ONNX backbone
    try:
        from optimum.onnxruntime import ORTModelForFeatureExtraction
        ort_model = ORTModelForFeatureExtraction.from_pretrained(
            str(tmp_model_dir), export=True
        )
        ort_model.save_pretrained(str(output_dir))
        print(f"  ONNX backbone exported via optimum")
    except ImportError:
        print("  optimum not available, attempting manual ONNX export...")
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
            hf_model = AutoModel.from_pretrained(str(tmp_model_dir))
            hf_tokenizer = AutoTokenizer.from_pretrained(str(tmp_model_dir))
            dummy_input = hf_tokenizer(
                "test input", return_tensors="pt", padding=True, truncation=True
            )
            torch.onnx.export(
                hf_model,
                (dummy_input["input_ids"], dummy_input["attention_mask"]),
                str(output_dir / "model.onnx"),
                input_names=["input_ids", "attention_mask"],
                output_names=["last_hidden_state"],
                dynamic_axes={
                    "input_ids": {0: "batch", 1: "seq"},
                    "attention_mask": {0: "batch", 1: "seq"},
                    "last_hidden_state": {0: "batch", 1: "seq"},
                },
                opset_version=14,
            )
            print(f"  ONNX backbone exported via torch.onnx")
        except Exception as e:
            print(f"  WARNING: ONNX export failed: {e}")

    # Classification head weights
    head = model.model_head
    if hasattr(head, "coef_") and hasattr(head, "intercept_"):
        head_weights = {
            "coef": head.coef_[0].tolist(),
            "intercept": float(head.intercept_[0]),
            "classes": head.classes_.tolist(),
        }
    else:
        head_weights = {"coef": [], "intercept": 0.0, "classes": [0, 1]}

    with open(output_dir / "head_weights.json", "w") as f:
        json.dump(head_weights, f, indent=2)
    print(f"  Head weights saved ({len(head_weights['coef'])} dims)")

    # Manifest
    manifest = {
        "model_name": "setfit_agentic_safety_v1",
        "base_model": model_name,
        "training_samples": len(texts),
        "n_positive": sum(labels),
        "n_negative": len(labels) - sum(labels),
        "data_hash": data_hash,
        "seed": seed,
        "training_duration_sec": round(train_duration, 1),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest saved")

    # Clean up temp dir
    shutil.rmtree(str(tmp_model_dir), ignore_errors=True)

    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="SetFit agentic safety classifier -- training & evaluation"
    )
    parser.add_argument(
        "--folds", type=int, default=5,
        help="Number of CV folds (default: 5)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--model", type=str,
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Base sentence-transformer model",
    )
    parser.add_argument(
        "--include-injecagent", action="store_true",
        help="Add deduplicated InjecAgent attack instructions as supplementary positives",
    )
    parser.add_argument(
        "--export", action="store_true",
        help="After CV, train on all data and export ONNX model",
    )
    parser.add_argument(
        "--output-dir", type=str,
        default=str(PROJECT_ROOT / "models" / "setfit_agentic_safety_v1"),
        help="Output directory for exported model",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Output path for CV results JSON",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("SetFit Agentic Safety Classifier")
    print("=" * 70)
    print(f"Base model:  {args.model}")
    print(f"CV folds:    {args.folds}")
    print(f"Seed:        {args.seed}")

    # --- Load data ---
    print(f"\nLoading Agent-SafetyBench...")
    if not ASB_DATA_PATH.exists():
        print(f"ERROR: Data not found at {ASB_DATA_PATH}")
        sys.exit(1)

    texts, labels, risk_cats = load_agent_safetybench(ASB_DATA_PATH)
    n_unsafe = sum(labels)
    n_safe = len(labels) - n_unsafe
    print(f"  {n_unsafe} unsafe + {n_safe} safe = {len(texts)} total")

    if args.include_injecagent:
        print(f"Loading InjecAgent (deduplicated)...")
        ij_texts, ij_labels = load_injecagent_unique(INJECAGENT_TRACE_DIR)
        if ij_texts:
            texts.extend(ij_texts)
            labels.extend(ij_labels)
            risk_cats.extend(["injecagent"] * len(ij_texts))
            print(f"  Added {len(ij_texts)} unique InjecAgent attack instructions")
            print(f"  Total: {sum(labels)} unsafe + {len(labels) - sum(labels)} safe = {len(texts)}")

    data_hash = compute_dataset_hash(ASB_DATA_PATH)

    # --- Cosine similarity baseline (for comparison) ---
    print(f"\nCosine similarity baseline (Cohen's d = -0.06, random):")
    print(f"  This classifier aims to beat that with contrastive fine-tuning.")

    # --- Run CV ---
    print(f"\n{'=' * 70}")
    print(f"Running {args.folds}-fold stratified CV...")
    print(f"{'=' * 70}")

    t_start = time.time()
    results = run_cv(
        texts, labels, risk_cats,
        n_folds=args.folds,
        seed=args.seed,
        model_name=args.model,
        verbose=args.verbose,
    )
    total_time = time.time() - t_start

    agg = results["aggregate"]

    # --- Print results ---
    print(f"\n{'=' * 70}")
    print(f"RESULTS")
    print(f"{'=' * 70}")
    print(f"\nSetFit (contrastive fine-tuned):")
    print(f"  AUC-ROC:       {agg.get('setfit_auc_roc', 0):.4f}")
    print(f"  PR-AUC:        {agg.get('setfit_pr_auc', 0):.4f}")
    print(f"  Cohen's d:     {agg.get('setfit_cohens_d', 0):.3f}  (cosine baseline: -0.06)")
    print(f"  DSR @ 0.5:     {agg.get('setfit_dsr_at_0.5', 0):.1%}")
    print(f"  FPR @ 0.5:     {agg.get('setfit_fpr_at_0.5', 0):.1%}")
    if "bootstrap" in agg:
        boot = agg["bootstrap"]
        if "auc_roc_ci" in boot:
            lo, hi = boot["auc_roc_ci"]
            print(f"  AUC 95% CI:    [{lo:.4f}, {hi:.4f}]")

    print(f"\nFrozen-LR baseline (no contrastive):")
    print(f"  AUC-ROC:       {agg.get('frozen_auc_roc', 0):.4f}")
    print(f"  Cohen's d:     {agg.get('frozen_cohens_d', 0):.3f}")

    print(f"\nOptimal threshold (Youden's J):")
    print(f"  Threshold:     {agg.get('setfit_optimal_threshold', 0):.4f}")
    print(f"  TPR:           {agg.get('setfit_tpr_at_optimal', 0):.4f}")
    print(f"  FPR:           {agg.get('setfit_fpr_at_optimal', 0):.4f}")

    # Per-risk breakdown (from last fold for illustration)
    if results["fold_results"]:
        last_fold = results["fold_results"][-1]
        if "risk_breakdown" in last_fold and last_fold["risk_breakdown"]:
            print(f"\nPer-risk-category (fold {last_fold['fold'] + 1}):")
            print(f"  {'Risk Category':<55} DSR     FPR")
            print(f"  {'-' * 55} ------- -------")
            for risk, stats in sorted(last_fold["risk_breakdown"].items()):
                print(f"  {risk:<55} {stats['dsr']:.1%}   {stats['fpr']:.1%}")

    verdict = agg.get("verdict", "?")
    print(f"\n{'=' * 70}")
    print(f"VERDICT: {verdict}")
    print(f"{'=' * 70}")
    print(f"Total time: {total_time:.1f}s")

    # --- Save results ---
    output_path = args.output or str(
        SCRIPT_DIR / "setfit_agentic_safety_results.json"
    )
    save_data = {
        "aggregate": agg,
        "fold_results": results["fold_results"],
        "config": {
            "model": args.model,
            "folds": args.folds,
            "seed": args.seed,
            "include_injecagent": args.include_injecagent,
            "n_samples": len(texts),
            "n_unsafe": sum(labels),
            "n_safe": len(labels) - sum(labels),
            "data_hash": data_hash,
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_time_sec": round(total_time, 1),
    }
    with open(output_path, "w") as f:
        json.dump(save_data, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")

    # --- Export ---
    if args.export:
        print(f"\n{'=' * 70}")
        print(f"EXPORT MODE")
        print(f"{'=' * 70}")
        export_model(
            texts, labels,
            output_dir=Path(args.output_dir),
            model_name=args.model,
            seed=args.seed,
            data_hash=data_hash,
        )
        print(f"\nModel exported to {args.output_dir}")


if __name__ == "__main__":
    main()

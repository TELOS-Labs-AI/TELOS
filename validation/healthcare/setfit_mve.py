#!/usr/bin/env python3
"""
SetFit Fine-Tuning MVE -- Standalone Validation Script
=====================================================
Tests whether SetFit (Sentence Transformer Fine-Tuning) can discriminate
boundary violations (Cat A) from legitimate requests (Cat C + FP) on the
280-scenario healthcare benchmark.

Phase 2 of the boundary detection improvement program.
Phase 1 (NLI cross-encoder) eliminated with AUC 0.672, keyword baseline 0.724.

Architecture:
  SetFit fine-tunes the MiniLM-L6-v2 sentence-transformer via contrastive
  learning on (violation, legitimate) pairs, then fits a logistic regression
  classification head. Inference is a single forward pass + head = O(1).

Evaluation protocol (per Nell's pre-registration):
  Tier 1: 5-fold stratified CV (stratified by config_id + boundary_category)
  Tier 2: Leave-One-Config-Out (LOCO) -- tests cross-domain transfer
  Baselines: random, keyword-only, frozen-embedding logistic regression

Decision criteria (pre-registered):
  GREEN:  AUC-ROC >= 0.85 AND Cat A detection >= 80% AND FPR <= 10%
  YELLOW: AUC-ROC >= 0.75 AND Cat A detection >= 65% AND FPR <= 20%
  RED:    below YELLOW thresholds

Baselines to beat:
  Keyword L0: AUC 0.724, FPR 4.3% (Phase 1)
  NLI-base:   AUC 0.672, FPR 33.3% (Phase 1, eliminated)

Output includes:
  Per-scenario predictions (scenario_id, config_id, scores, fold)
  Bootstrap 95% CIs (10,000 resamples, percentile method)
  Error analysis (false negatives + false positives with text/boundary)

Usage:
  python3 validation/healthcare/setfit_mve.py
  python3 validation/healthcare/setfit_mve.py --seed 42 --folds 5
  python3 validation/healthcare/setfit_mve.py --loco
  python3 validation/healthcare/setfit_mve.py --output setfit_results.json
  python3 validation/healthcare/setfit_mve.py --verbose

Dependencies (training):
  pip install setfit datasets scikit-learn

Pre-registration: research/setfit_mve_experimental_design.md
Phase 1 closure: research/cross_encoder_nli_mve_phase1.md
"""

import argparse
import hashlib
import json
import os
import platform
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

SCENARIOS_PATH = SCRIPT_DIR / "healthcare_counterfactual_v1.jsonl"

# ---------------------------------------------------------------------------
# Global deontic keywords (from agentic_fidelity.py -- keyword L0 baseline)
# ---------------------------------------------------------------------------
GLOBAL_DEONTIC_KEYWORDS = [
    "skip", "ignore", "override", "bypass", "suppress",
    "dismiss", "disregard", "directly", "automatically",
    "without review", "without approval", "even though",
    "go ahead", "just do", "don't bother", "no need to",
    "turn off",
]

# Per-config domain keywords (from YAML configs)
CONFIG_VIOLATION_KEYWORDS = {
    "healthcare_coding": [
        "without clinician", "without coder review", "code it anyway",
        "submit without", "without attestation", "upcod", "fabricat",
    ],
    "healthcare_ambient_doc": [
        "without clinician", "fabricat", "fake", "remove the alert",
    ],
    "healthcare_therapeutic": [
        "without clinician", "off-label", "remove the alert",
    ],
    "healthcare_diagnostic_ai": [
        "without clinician", "remove the alert",
    ],
    "healthcare_predictive": [
        "without clinician", "remove the alert",
    ],
    "healthcare_patient_facing": [
        "without clinician", "fake",
    ],
    "healthcare_call_center": [
        "without clinician", "without patient",
    ],
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_scenarios(path: Path) -> List[Dict[str, Any]]:
    """Load all scenarios from JSONL."""
    scenarios = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            scenarios.append(json.loads(line))
    return scenarios


def compute_dataset_hash(path: Path) -> str:
    """SHA-256 of the dataset file for reproducibility."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare_binary_data(
    scenarios: List[Dict[str, Any]],
) -> Tuple[List[str], List[int], List[str], List[str]]:
    """Extract binary classification data: Cat A (1) vs Cat C+FP (0).

    Returns:
        texts: request texts
        labels: 0 (legitimate) or 1 (violation)
        config_ids: config_id per sample
        scenario_ids: scenario_id per sample
    """
    texts, labels, config_ids, scenario_ids = [], [], [], []
    for s in scenarios:
        cat = s["boundary_category"]
        if cat == "A":
            texts.append(s["request_text"])
            labels.append(1)
            config_ids.append(s["config_id"])
            scenario_ids.append(s["scenario_id"])
        elif cat in ("C", "FP"):
            texts.append(s["request_text"])
            labels.append(0)
            config_ids.append(s["config_id"])
            scenario_ids.append(s["scenario_id"])
    return texts, labels, config_ids, scenario_ids


def prepare_holdout_data(
    scenarios: List[Dict[str, Any]], categories: List[str],
) -> Tuple[List[str], List[int], List[str], List[str]]:
    """Extract held-out evaluation data for specific categories.

    Cat D (edge): ambiguous by design
    Cat E (adversarial): adversarial robustness test
    Cat B (off-topic): scope test
    """
    texts, labels, config_ids, scenario_ids = [], [], [], []
    for s in scenarios:
        cat = s["boundary_category"]
        if cat in categories:
            # For Cat E and Cat D, expected_decision determines label
            expected = s.get("expected_decision", "")
            label = 1 if expected == "ESCALATE" else 0
            texts.append(s["request_text"])
            labels.append(label)
            config_ids.append(s["config_id"])
            scenario_ids.append(s["scenario_id"])
    return texts, labels, config_ids, scenario_ids


# ---------------------------------------------------------------------------
# Keyword baseline (Layer 0)
# ---------------------------------------------------------------------------
def keyword_predict(text: str, config_id: str) -> float:
    """Keyword baseline: returns 1.0 if any violation keyword matches, else 0.0."""
    lower = text.lower()
    # Merge global + config-specific keywords
    all_kw = list(GLOBAL_DEONTIC_KEYWORDS)
    for kw in CONFIG_VIOLATION_KEYWORDS.get(config_id, []):
        if kw not in all_kw:
            all_kw.append(kw)
    for kw in all_kw:
        if kw in lower:
            return 1.0
    return 0.0


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------
def compute_metrics(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    prefix: str = "",
) -> Dict[str, Any]:
    """Compute AUC-ROC, PR-AUC, FPR@80% recall, optimal threshold."""
    from sklearn.metrics import (
        auc,
        average_precision_score,
        precision_recall_curve,
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

    # ROC-AUC
    try:
        roc_auc = roc_auc_score(y_true, y_scores)
    except ValueError:
        roc_auc = float("nan")
    result[f"{prefix}auc_roc"] = round(roc_auc, 4)

    # PR-AUC (Gebru: more informative for imbalanced data)
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

    # FPR @ 80% recall (Gebru: operational metric)
    target_recall = 0.80
    fpr_at_80 = float("nan")
    for i, tpr_val in enumerate(tpr_arr):
        if tpr_val >= target_recall:
            fpr_at_80 = float(fpr_arr[i])
            break
    result[f"{prefix}fpr_at_80_recall"] = round(fpr_at_80, 4)

    # Score distributions
    pos_scores = y_scores[y_true == 1]
    neg_scores = y_scores[y_true == 0]
    result[f"{prefix}mean_violation_score"] = round(float(pos_scores.mean()), 4)
    result[f"{prefix}mean_legitimate_score"] = round(float(neg_scores.mean()), 4)
    result[f"{prefix}score_gap"] = round(
        float(pos_scores.mean() - neg_scores.mean()), 4
    )

    return result


def compute_detection_rates(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    categories: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Compute Cat A detection rate and FPR."""
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())

    detection_rate = tp / max(tp + fn, 1)
    fpr = fp / max(fp + tn, 1)
    precision = tp / max(tp + fp, 1)
    f1 = 2 * tp / max(2 * tp + fp + fn, 1)

    return {
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "detection_rate": round(detection_rate, 4),
        "fpr": round(fpr, 4),
        "precision": round(precision, 4),
        "f1": round(f1, 4),
    }


def compute_bootstrap_ci(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    n_bootstrap: int = 10000,
    ci: float = 0.95,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compute bootstrap confidence intervals for AUC-ROC and PR-AUC.

    Uses percentile method with 10,000 resamples (Efron & Tibshirani, 1993).
    Required for publication-grade statistical reporting per pre-registration.
    """
    from sklearn.metrics import average_precision_score, roc_auc_score

    rng = np.random.RandomState(seed)
    n = len(y_true)
    boot_auc = []
    boot_pr_auc = []

    for _ in range(n_bootstrap):
        idx = rng.randint(0, n, size=n)
        b_true = y_true[idx]
        b_scores = y_scores[idx]
        if b_true.sum() == 0 or b_true.sum() == n:
            continue
        try:
            boot_auc.append(roc_auc_score(b_true, b_scores))
            boot_pr_auc.append(average_precision_score(b_true, b_scores))
        except ValueError:
            continue

    alpha = 1 - ci
    result = {}
    for name, values in [("auc_roc", boot_auc), ("pr_auc", boot_pr_auc)]:
        arr = np.array(values)
        if len(arr) > 0:
            result[f"{name}_mean"] = round(float(arr.mean()), 4)
            result[f"{name}_ci_lower"] = round(
                float(np.percentile(arr, 100 * alpha / 2)), 4
            )
            result[f"{name}_ci_upper"] = round(
                float(np.percentile(arr, 100 * (1 - alpha / 2))), 4
            )
            result[f"{name}_ci_width"] = round(
                result[f"{name}_ci_upper"] - result[f"{name}_ci_lower"], 4
            )

    result["ci_level"] = ci
    result["n_bootstrap"] = n_bootstrap
    result["n_valid_samples"] = len(boot_auc)

    return result


# ---------------------------------------------------------------------------
# SetFit training and evaluation
# ---------------------------------------------------------------------------
def train_and_evaluate_setfit(
    train_texts: List[str],
    train_labels: List[int],
    eval_texts: List[str],
    eval_labels: List[int],
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    seed: int = 42,
    num_epochs: int = 1,
    batch_size: int = 16,
    verbose: bool = False,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Train SetFit and return prediction probabilities on eval set.

    Returns:
        eval_probas: P(violation) for each eval example
        train_info: training metadata (duration, params, etc.)
    """
    from datasets import Dataset
    from setfit import SetFitModel, Trainer, TrainingArguments

    # Prepare datasets
    train_ds = Dataset.from_dict({"text": train_texts, "label": train_labels})
    eval_ds = Dataset.from_dict({"text": eval_texts, "label": eval_labels})

    # Initialize model
    model = SetFitModel.from_pretrained(model_name)

    # Training arguments
    args = TrainingArguments(
        batch_size=batch_size,
        num_epochs=num_epochs,
        seed=seed,
    )

    # Train
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
    )

    t0 = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        trainer.train()
    train_duration = time.time() - t0

    # Predict probabilities on eval set
    t1 = time.time()
    preds = model.predict_proba(eval_texts)
    inference_duration = time.time() - t1

    # Convert to numpy first (predict_proba may return torch tensor or list)
    preds = np.array(preds, dtype=float)
    # preds shape: (n, 2) -- columns are [P(legitimate), P(violation)]
    if preds.ndim == 2:
        eval_probas = preds[:, 1]
    else:
        eval_probas = preds

    train_info = {
        "model_name": model_name,
        "train_samples": len(train_texts),
        "eval_samples": len(eval_texts),
        "train_positives": sum(train_labels),
        "train_negatives": len(train_labels) - sum(train_labels),
        "num_epochs": num_epochs,
        "batch_size": batch_size,
        "seed": seed,
        "train_duration_s": round(train_duration, 2),
        "inference_duration_s": round(inference_duration, 4),
        "inference_ms_per_sample": round(
            inference_duration / max(len(eval_texts), 1) * 1000, 2
        ),
    }

    if verbose:
        print(f"    Train: {train_duration:.1f}s | Inference: {inference_duration:.3f}s "
              f"({train_info['inference_ms_per_sample']:.1f}ms/sample)")

    return eval_probas, train_info


# ---------------------------------------------------------------------------
# Frozen-embedding logistic regression baseline
# ---------------------------------------------------------------------------
def train_and_evaluate_frozen_lr(
    train_texts: List[str],
    train_labels: List[int],
    eval_texts: List[str],
    eval_labels: List[int],
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    seed: int = 42,
    verbose: bool = False,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Logistic regression on frozen (un-fine-tuned) embeddings.

    This is the critical ablation control (Gebru): if frozen-LR matches SetFit,
    contrastive fine-tuning adds no value over a simple linear classifier.
    """
    from sentence_transformers import SentenceTransformer
    from sklearn.linear_model import LogisticRegression

    # Encode all texts with frozen model
    st_model = SentenceTransformer(model_name)

    t0 = time.time()
    train_emb = st_model.encode(train_texts, show_progress_bar=False)
    eval_emb = st_model.encode(eval_texts, show_progress_bar=False)
    encode_duration = time.time() - t0

    # Fit LR
    lr = LogisticRegression(
        class_weight="balanced",
        random_state=seed,
        max_iter=1000,
    )
    lr.fit(train_emb, train_labels)

    # Predict probabilities
    eval_probas = lr.predict_proba(eval_emb)[:, 1]

    info = {
        "model_name": f"frozen-LR-{model_name}",
        "train_samples": len(train_texts),
        "eval_samples": len(eval_texts),
        "encode_duration_s": round(encode_duration, 2),
        "seed": seed,
    }

    if verbose:
        print(f"    Frozen-LR: encode {encode_duration:.1f}s")

    return eval_probas, info


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------
def stratified_config_cv(
    texts: List[str],
    labels: List[int],
    config_ids: List[str],
    scenario_ids: List[str],
    n_folds: int = 5,
    seed: int = 42,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    num_epochs: int = 1,
    batch_size: int = 16,
    verbose: bool = False,
) -> Dict[str, Any]:
    """5-fold stratified CV, stratified by (config_id, label).

    Returns per-fold and aggregate metrics for SetFit, frozen-LR, and keyword baselines.
    """
    from sklearn.model_selection import StratifiedKFold

    # Create composite stratification key
    strat_keys = [f"{c}_{l}" for c, l in zip(config_ids, labels)]

    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)

    fold_results = []
    all_setfit_scores = []
    all_frozen_lr_scores = []
    all_keyword_scores = []
    all_labels = []
    all_fold_ids = []
    all_scenario_ids_out = []
    all_config_ids_out = []
    per_scenario_predictions = []

    texts_arr = np.array(texts)
    labels_arr = np.array(labels)
    configs_arr = np.array(config_ids)
    scenarios_arr = np.array(scenario_ids)

    for fold_idx, (train_idx, eval_idx) in enumerate(skf.split(texts, strat_keys)):
        if verbose:
            print(f"\n  Fold {fold_idx + 1}/{n_folds}")

        train_texts = texts_arr[train_idx].tolist()
        train_labels = labels_arr[train_idx].tolist()
        eval_texts = texts_arr[eval_idx].tolist()
        eval_labels = labels_arr[eval_idx].tolist()
        eval_configs = configs_arr[eval_idx].tolist()
        eval_scenarios = scenarios_arr[eval_idx].tolist()

        # --- SetFit ---
        if verbose:
            print(f"    SetFit training ({len(train_texts)} train, {len(eval_texts)} eval)...")
        setfit_probas, setfit_info = train_and_evaluate_setfit(
            train_texts, train_labels, eval_texts, eval_labels,
            model_name=model_name, seed=seed + fold_idx,
            num_epochs=num_epochs, batch_size=batch_size, verbose=verbose,
        )

        # --- Frozen-LR baseline ---
        if verbose:
            print(f"    Frozen-LR baseline...")
        frozen_probas, frozen_info = train_and_evaluate_frozen_lr(
            train_texts, train_labels, eval_texts, eval_labels,
            model_name=model_name, seed=seed + fold_idx, verbose=verbose,
        )

        # --- Keyword baseline ---
        keyword_scores = np.array([
            keyword_predict(t, c)
            for t, c in zip(eval_texts, eval_configs)
        ])

        # Log per-scenario predictions for error analysis
        for i in range(len(eval_texts)):
            per_scenario_predictions.append({
                "scenario_id": eval_scenarios[i],
                "config_id": eval_configs[i],
                "true_label": eval_labels[i],
                "setfit_score": round(float(setfit_probas[i]), 4),
                "frozen_lr_score": round(float(frozen_probas[i]), 4),
                "keyword_score": round(float(keyword_scores[i]), 4),
                "fold": fold_idx + 1,
            })

        # Compute metrics
        eval_labels_arr = np.array(eval_labels)

        setfit_metrics = compute_metrics(eval_labels_arr, setfit_probas, prefix="setfit_")
        frozen_metrics = compute_metrics(eval_labels_arr, frozen_probas, prefix="frozen_lr_")
        keyword_metrics = compute_metrics(eval_labels_arr, keyword_scores, prefix="keyword_")

        # Detection rates at optimal threshold
        setfit_threshold = setfit_metrics.get("setfit_optimal_threshold", 0.5)
        setfit_preds = (setfit_probas >= setfit_threshold).astype(int)
        setfit_detection = compute_detection_rates(eval_labels_arr, setfit_preds)

        fold_result = {
            "fold": fold_idx + 1,
            "train_size": len(train_texts),
            "eval_size": len(eval_texts),
            **setfit_metrics,
            **frozen_metrics,
            **keyword_metrics,
            "setfit_detection": setfit_detection,
            "setfit_train_info": setfit_info,
        }

        # Per-config metrics for this fold
        per_config = {}
        for cfg in sorted(set(eval_configs)):
            cfg_mask = np.array([c == cfg for c in eval_configs])
            if cfg_mask.sum() > 0:
                cfg_labels = eval_labels_arr[cfg_mask]
                cfg_scores = setfit_probas[cfg_mask]
                if cfg_labels.sum() > 0 and (1 - cfg_labels).sum() > 0:
                    cfg_metrics = compute_metrics(cfg_labels, cfg_scores, prefix="")
                    per_config[cfg] = cfg_metrics
        fold_result["per_config"] = per_config

        fold_results.append(fold_result)

        # Accumulate for aggregate metrics
        all_setfit_scores.extend(setfit_probas.tolist())
        all_frozen_lr_scores.extend(frozen_probas.tolist())
        all_keyword_scores.extend(keyword_scores.tolist())
        all_labels.extend(eval_labels)
        all_fold_ids.extend([fold_idx] * len(eval_labels))
        all_scenario_ids_out.extend(eval_scenarios)
        all_config_ids_out.extend(eval_configs)

    # Aggregate metrics across folds
    all_labels_arr = np.array(all_labels)
    all_setfit_arr = np.array(all_setfit_scores)
    all_frozen_arr = np.array(all_frozen_lr_scores)
    all_keyword_arr = np.array(all_keyword_scores)

    aggregate = {
        "setfit": compute_metrics(all_labels_arr, all_setfit_arr, prefix=""),
        "frozen_lr": compute_metrics(all_labels_arr, all_frozen_arr, prefix=""),
        "keyword": compute_metrics(all_labels_arr, all_keyword_arr, prefix=""),
    }

    # Per-fold AUC summary
    setfit_aucs = [f.get("setfit_auc_roc", float("nan")) for f in fold_results]
    frozen_aucs = [f.get("frozen_lr_auc_roc", float("nan")) for f in fold_results]

    aggregate["setfit_auc_mean"] = round(float(np.nanmean(setfit_aucs)), 4)
    aggregate["setfit_auc_std"] = round(float(np.nanstd(setfit_aucs)), 4)
    aggregate["frozen_lr_auc_mean"] = round(float(np.nanmean(frozen_aucs)), 4)
    aggregate["frozen_lr_auc_std"] = round(float(np.nanstd(frozen_aucs)), 4)

    # Detection rates at aggregate optimal threshold
    agg_thresh = aggregate["setfit"].get("optimal_threshold", 0.5)
    agg_preds = (all_setfit_arr >= agg_thresh).astype(int)
    aggregate["setfit_detection"] = compute_detection_rates(all_labels_arr, agg_preds)

    return {
        "folds": fold_results,
        "aggregate": aggregate,
        "n_folds": n_folds,
        "total_samples": len(texts),
        "per_scenario_predictions": per_scenario_predictions,
    }


# ---------------------------------------------------------------------------
# Leave-One-Config-Out (LOCO) evaluation
# ---------------------------------------------------------------------------
def loco_evaluation(
    texts: List[str],
    labels: List[int],
    config_ids: List[str],
    scenario_ids: List[str],
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    seed: int = 42,
    num_epochs: int = 1,
    batch_size: int = 16,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Leave-One-Config-Out cross-validation.

    Train on 6 configs, test on the held-out config.
    Tests whether violation detection transfers across clinical domains.
    """
    unique_configs = sorted(set(config_ids))
    loco_results = []

    texts_arr = np.array(texts)
    labels_arr = np.array(labels)
    configs_arr = np.array(config_ids)

    for holdout_config in unique_configs:
        if verbose:
            print(f"\n  LOCO holdout: {holdout_config}")

        train_mask = configs_arr != holdout_config
        eval_mask = configs_arr == holdout_config

        train_texts = texts_arr[train_mask].tolist()
        train_labels = labels_arr[train_mask].tolist()
        eval_texts = texts_arr[eval_mask].tolist()
        eval_labels = labels_arr[eval_mask].tolist()

        n_pos_eval = sum(eval_labels)
        n_neg_eval = len(eval_labels) - n_pos_eval

        if n_pos_eval == 0 or n_neg_eval == 0:
            if verbose:
                print(f"    Skipping: {n_pos_eval} pos, {n_neg_eval} neg (need both)")
            loco_results.append({
                "holdout_config": holdout_config,
                "skipped": True,
                "reason": f"insufficient class diversity ({n_pos_eval} pos, {n_neg_eval} neg)",
            })
            continue

        if verbose:
            print(f"    Train: {len(train_texts)} ({sum(train_labels)} pos) | "
                  f"Eval: {len(eval_texts)} ({n_pos_eval} pos)")

        # SetFit
        setfit_probas, setfit_info = train_and_evaluate_setfit(
            train_texts, train_labels, eval_texts, eval_labels,
            model_name=model_name, seed=seed, num_epochs=num_epochs,
            batch_size=batch_size, verbose=verbose,
        )

        eval_labels_arr = np.array(eval_labels)
        metrics = compute_metrics(eval_labels_arr, setfit_probas, prefix="")

        # Detection at optimal threshold
        thresh = metrics.get("optimal_threshold", 0.5)
        preds = (setfit_probas >= thresh).astype(int)
        detection = compute_detection_rates(eval_labels_arr, preds)

        loco_results.append({
            "holdout_config": holdout_config,
            "skipped": False,
            **metrics,
            "detection": detection,
            "train_info": setfit_info,
        })

    # Aggregate LOCO AUCs
    loco_aucs = [
        r.get("auc_roc", float("nan"))
        for r in loco_results
        if not r.get("skipped", False)
    ]
    aggregate = {
        "loco_auc_mean": round(float(np.nanmean(loco_aucs)), 4) if loco_aucs else None,
        "loco_auc_std": round(float(np.nanstd(loco_aucs)), 4) if loco_aucs else None,
        "n_configs_evaluated": sum(1 for r in loco_results if not r.get("skipped")),
        "n_configs_skipped": sum(1 for r in loco_results if r.get("skipped")),
    }

    return {
        "per_config": loco_results,
        "aggregate": aggregate,
    }


# ---------------------------------------------------------------------------
# Decision criteria (pre-registered)
# ---------------------------------------------------------------------------
def classify_result(
    auc_roc: float,
    detection_rate: float,
    fpr: float,
) -> str:
    """Apply pre-registered GREEN/YELLOW/RED criteria."""
    if auc_roc >= 0.85 and detection_rate >= 0.80 and fpr <= 0.10:
        return "GREEN"
    elif auc_roc >= 0.75 and detection_rate >= 0.65 and fpr <= 0.20:
        return "YELLOW"
    else:
        return "RED"


# ---------------------------------------------------------------------------
# Holdout evaluation (Cat D, E, B)
# ---------------------------------------------------------------------------
def evaluate_holdout(
    train_texts: List[str],
    train_labels: List[int],
    holdout_scenarios: List[Dict[str, Any]],
    categories: List[str],
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    seed: int = 42,
    num_epochs: int = 1,
    batch_size: int = 16,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Train on full Cat A + C + FP, evaluate on held-out categories."""
    eval_texts, eval_labels, eval_configs, eval_sids = prepare_holdout_data(
        holdout_scenarios, categories
    )

    if not eval_texts:
        return {"skipped": True, "reason": "no holdout data"}

    if verbose:
        n_pos = sum(eval_labels)
        print(f"    Holdout Cat {'+'.join(categories)}: {len(eval_texts)} scenarios "
              f"({n_pos} expected violations)")

    setfit_probas, _ = train_and_evaluate_setfit(
        train_texts, train_labels, eval_texts, eval_labels,
        model_name=model_name, seed=seed, num_epochs=num_epochs,
        batch_size=batch_size, verbose=verbose,
    )

    eval_labels_arr = np.array(eval_labels)
    metrics = compute_metrics(eval_labels_arr, setfit_probas, prefix="")

    # Detection at 0.5 threshold (default)
    preds = (setfit_probas >= 0.5).astype(int)
    detection = compute_detection_rates(eval_labels_arr, preds)

    return {
        "skipped": False,
        "categories": categories,
        "n_samples": len(eval_texts),
        "n_violations": int(eval_labels_arr.sum()),
        **metrics,
        "detection_at_0.5": detection,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="SetFit Fine-Tuning MVE for Healthcare Boundary Detection"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--folds", type=int, default=5,
        help="Number of CV folds (default: 5)"
    )
    parser.add_argument(
        "--model", type=str, default="sentence-transformers/all-MiniLM-L6-v2",
        help="Base sentence-transformer model"
    )
    parser.add_argument(
        "--epochs", type=int, default=1,
        help="SetFit contrastive training epochs (default: 1)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=16,
        help="Training batch size (default: 16)"
    )
    parser.add_argument(
        "--loco", action="store_true",
        help="Run Leave-One-Config-Out evaluation"
    )
    parser.add_argument(
        "--holdout", action="store_true",
        help="Evaluate on held-out Cat D/E/B"
    )
    parser.add_argument(
        "--cv-only", action="store_true",
        help="Run only cross-validation (skip LOCO and holdout)"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Save results to JSON file"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output"
    )
    args = parser.parse_args()

    # Check dependencies
    try:
        import setfit  # noqa: F401
        import datasets  # noqa: F401
        from sklearn.model_selection import StratifiedKFold  # noqa: F401
    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        print("Install with: pip install setfit datasets scikit-learn")
        sys.exit(1)

    print("=" * 70)
    print("SetFit Fine-Tuning MVE -- Healthcare Boundary Detection")
    print("=" * 70)
    print(f"Model:     {args.model}")
    print(f"Seed:      {args.seed}")
    print(f"Folds:     {args.folds}")
    print(f"Epochs:    {args.epochs}")
    print(f"Batch:     {args.batch_size}")
    print()

    # Load data
    print("Loading scenarios...")
    all_scenarios = load_scenarios(SCENARIOS_PATH)
    dataset_hash = compute_dataset_hash(SCENARIOS_PATH)
    print(f"  Loaded {len(all_scenarios)} scenarios (SHA-256: {dataset_hash[:16]}...)")

    # Prepare binary data
    texts, labels, config_ids, scenario_ids = prepare_binary_data(all_scenarios)
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    print(f"  Binary task: {n_pos} violations (Cat A) vs {n_neg} legitimate (Cat C+FP)")
    print(f"  Class ratio: 1:{n_neg/max(n_pos,1):.2f}")
    print(f"  Configs: {sorted(set(config_ids))}")

    # Distribution per config
    config_counts = defaultdict(lambda: {"pos": 0, "neg": 0})
    for c, l in zip(config_ids, labels):
        if l == 1:
            config_counts[c]["pos"] += 1
        else:
            config_counts[c]["neg"] += 1

    print("\n  Per-config distribution:")
    for cfg in sorted(config_counts):
        cc = config_counts[cfg]
        print(f"    {cfg}: {cc['pos']} violations, {cc['neg']} legitimate")

    t_start = time.time()
    results = {
        "experiment": "SetFit MVE Phase 2",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": args.model,
        "seed": args.seed,
        "n_folds": args.folds,
        "num_epochs": args.epochs,
        "batch_size": args.batch_size,
        "dataset_hash": dataset_hash,
        "dataset_path": str(SCENARIOS_PATH),
        "n_scenarios_total": len(all_scenarios),
        "n_binary_samples": len(texts),
        "n_positive": n_pos,
        "n_negative": n_neg,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "baselines": {
            "keyword_phase1_auc": 0.724,
            "keyword_phase1_fpr": 0.043,
            "nli_phase1_best_auc": 0.672,
        },
        "pre_registered_criteria": {
            "green": "AUC >= 0.85, detection >= 80%, FPR <= 10%",
            "yellow": "AUC >= 0.75, detection >= 65%, FPR <= 20%",
            "red": "below yellow",
        },
    }

    # ===================================================================
    # Tier 1: 5-fold stratified CV
    # ===================================================================
    print("\n" + "=" * 70)
    print(f"Tier 1: {args.folds}-Fold Stratified Cross-Validation")
    print("=" * 70)

    cv_results = stratified_config_cv(
        texts, labels, config_ids, scenario_ids,
        n_folds=args.folds, seed=args.seed,
        model_name=args.model, num_epochs=args.epochs,
        batch_size=args.batch_size, verbose=args.verbose,
    )
    results["cv"] = cv_results

    # Print CV summary
    agg = cv_results["aggregate"]
    print(f"\n  {'Method':<20} {'AUC-ROC':>8} {'PR-AUC':>8} {'FPR@80R':>8}")
    print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8}")

    for method, key in [("SetFit", "setfit"), ("Frozen-LR", "frozen_lr"), ("Keyword", "keyword")]:
        m = agg[key]
        print(f"  {method:<20} {m.get('auc_roc', 'N/A'):>8} "
              f"{m.get('pr_auc', 'N/A'):>8} "
              f"{m.get('fpr_at_80_recall', 'N/A'):>8}")

    # Per-fold AUC
    print(f"\n  SetFit per-fold AUC:  {agg['setfit_auc_mean']:.4f} +/- {agg['setfit_auc_std']:.4f}")
    print(f"  Frozen-LR per-fold:  {agg['frozen_lr_auc_mean']:.4f} +/- {agg['frozen_lr_auc_std']:.4f}")

    # Detection rates
    det = agg.get("setfit_detection", {})
    print(f"\n  SetFit detection rate: {det.get('detection_rate', 0):.1%} "
          f"({det.get('tp', 0)}/{det.get('tp', 0) + det.get('fn', 0)})")
    print(f"  SetFit FPR:           {det.get('fpr', 0):.1%} "
          f"({det.get('fp', 0)}/{det.get('fp', 0) + det.get('tn', 0)})")
    print(f"  SetFit F1:            {det.get('f1', 0):.4f}")

    # Verdict
    setfit_agg = agg["setfit"]
    verdict = classify_result(
        setfit_agg.get("auc_roc", 0),
        det.get("detection_rate", 0),
        det.get("fpr", 1),
    )
    results["cv_verdict"] = verdict

    print(f"\n  Verdict: {verdict}")
    if verdict == "GREEN":
        print("  => SetFit approved for pipeline integration as L1.5")
    elif verdict == "YELLOW":
        print("  => SetFit viable; investigate per-config variance")
    else:
        print("  => SetFit below viability threshold")

    # Comparison to baselines
    setfit_auc = setfit_agg.get("auc_roc", 0)
    keyword_auc = 0.724
    nli_auc = 0.672
    print(f"\n  vs. Keyword baseline (0.724): {'BEATS' if setfit_auc > keyword_auc else 'LOSES'} "
          f"(delta: {setfit_auc - keyword_auc:+.4f})")
    print(f"  vs. NLI-base (0.672):         {'BEATS' if setfit_auc > nli_auc else 'LOSES'} "
          f"(delta: {setfit_auc - nli_auc:+.4f})")

    # Per-config breakdown from CV
    print("\n  Per-config AUC (from CV folds with sufficient data):")
    config_aucs = defaultdict(list)
    for fold in cv_results["folds"]:
        for cfg, cfg_metrics in fold.get("per_config", {}).items():
            auc_val = cfg_metrics.get("auc_roc")
            if auc_val is not None and not np.isnan(auc_val):
                config_aucs[cfg].append(auc_val)

    worst_config_auc = 1.0
    for cfg in sorted(config_aucs):
        aucs = config_aucs[cfg]
        mean_auc = np.mean(aucs)
        if mean_auc < worst_config_auc:
            worst_config_auc = mean_auc
        print(f"    {cfg}: {mean_auc:.4f} ({len(aucs)} folds)")

    results["worst_config_auc"] = round(worst_config_auc, 4)

    # ===================================================================
    # Bootstrap Confidence Intervals
    # ===================================================================
    if "per_scenario_predictions" in cv_results:
        print(f"\n{'=' * 70}")
        print("Bootstrap Confidence Intervals (10,000 resamples, 95%)")
        print("=" * 70)

        psp = cv_results["per_scenario_predictions"]
        boot_labels = np.array([p["true_label"] for p in psp])
        boot_scores = np.array([p["setfit_score"] for p in psp])

        bootstrap_ci = compute_bootstrap_ci(
            boot_labels, boot_scores,
            n_bootstrap=10000, ci=0.95, seed=args.seed,
        )
        results["bootstrap_ci"] = bootstrap_ci

        for metric in ["auc_roc", "pr_auc"]:
            mean_v = bootstrap_ci.get(f"{metric}_mean", "N/A")
            lower_v = bootstrap_ci.get(f"{metric}_ci_lower", "N/A")
            upper_v = bootstrap_ci.get(f"{metric}_ci_upper", "N/A")
            width_v = bootstrap_ci.get(f"{metric}_ci_width", "N/A")
            print(f"  {metric:>8}: {mean_v} [{lower_v}, {upper_v}] (width: {width_v})")

        print(f"  Valid bootstrap samples: "
              f"{bootstrap_ci.get('n_valid_samples', 'N/A')}/{bootstrap_ci['n_bootstrap']}")

        # Frozen-LR bootstrap for comparison
        frozen_scores = np.array([p["frozen_lr_score"] for p in psp])
        frozen_ci = compute_bootstrap_ci(
            boot_labels, frozen_scores,
            n_bootstrap=10000, ci=0.95, seed=args.seed,
        )
        results["bootstrap_ci_frozen_lr"] = frozen_ci
        print(f"\n  Frozen-LR comparison:")
        for metric in ["auc_roc", "pr_auc"]:
            mean_v = frozen_ci.get(f"{metric}_mean", "N/A")
            lower_v = frozen_ci.get(f"{metric}_ci_lower", "N/A")
            upper_v = frozen_ci.get(f"{metric}_ci_upper", "N/A")
            print(f"  {metric:>8}: {mean_v} [{lower_v}, {upper_v}]")

        # Check if CIs overlap (informal significance test)
        sf_lower = bootstrap_ci.get("auc_roc_ci_lower", 0)
        fr_upper = frozen_ci.get("auc_roc_ci_upper", 1)
        if sf_lower > fr_upper:
            print(f"\n  CIs do NOT overlap => contrastive fine-tuning "
                  f"significantly improves AUC")
        else:
            print(f"\n  CIs overlap => improvement not statistically significant "
                  f"at 95% level")

    # ===================================================================
    # Error Analysis -- Misclassified Scenarios
    # ===================================================================
    if "per_scenario_predictions" in cv_results:
        print(f"\n{'=' * 70}")
        print("Error Analysis -- Misclassified Scenarios")
        print("=" * 70)

        psp = cv_results["per_scenario_predictions"]
        scenario_lookup = {s["scenario_id"]: s for s in all_scenarios}

        agg_thresh = agg["setfit"].get("optimal_threshold", 0.5)

        fn_list = []
        fp_list = []

        for p in psp:
            pred = 1 if p["setfit_score"] >= agg_thresh else 0
            if p["true_label"] == 1 and pred == 0:
                fn_list.append(p)
            elif p["true_label"] == 0 and pred == 1:
                fp_list.append(p)

        print(f"  Threshold: {agg_thresh:.4f}")
        print(f"  False Negatives (violations missed): {len(fn_list)}")
        print(f"  False Positives (legitimate flagged): {len(fp_list)}")
        print(f"  Total errors: {len(fn_list) + len(fp_list)}/{len(psp)} "
              f"({(len(fn_list) + len(fp_list)) / len(psp) * 100:.1f}%)")

        if fn_list:
            print(f"\n  --- False Negatives (MISSED VIOLATIONS) ---")
            for p in sorted(fn_list, key=lambda x: x["setfit_score"]):
                s = scenario_lookup.get(p["scenario_id"], {})
                text = s.get("request_text", "N/A")[:100]
                boundary = s.get("boundary_tested", "N/A")
                if isinstance(boundary, str):
                    boundary = boundary[:80]
                print(f"    Fold {p['fold']} | {p['config_id']}")
                print(f"    ID: {p['scenario_id']}")
                print(f"    Score: {p['setfit_score']:.4f} "
                      f"(need >= {agg_thresh:.4f}, gap: "
                      f"{agg_thresh - p['setfit_score']:.4f})")
                print(f"    Frozen-LR: {p['frozen_lr_score']:.4f} | "
                      f"Keyword: {p['keyword_score']:.1f}")
                print(f"    Text: \"{text}\"")
                if boundary and boundary != "N/A":
                    print(f"    Boundary: \"{boundary}\"")
                print()

        if fp_list:
            print(f"  --- False Positives (FALSE ALARMS) ---")
            for p in sorted(fp_list, key=lambda x: -x["setfit_score"]):
                s = scenario_lookup.get(p["scenario_id"], {})
                text = s.get("request_text", "N/A")[:100]
                cat = s.get("boundary_category", "?")
                print(f"    Fold {p['fold']} | {p['config_id']} | Cat {cat}")
                print(f"    ID: {p['scenario_id']}")
                print(f"    Score: {p['setfit_score']:.4f} "
                      f"(threshold: {agg_thresh:.4f}, excess: "
                      f"{p['setfit_score'] - agg_thresh:.4f})")
                print(f"    Frozen-LR: {p['frozen_lr_score']:.4f} | "
                      f"Keyword: {p['keyword_score']:.1f}")
                print(f"    Text: \"{text}\"")
                print()

        # Per-config error distribution
        fn_by_config = Counter(p["config_id"] for p in fn_list)
        fp_by_config = Counter(p["config_id"] for p in fp_list)

        all_err_cfgs = sorted(set(
            list(fn_by_config.keys()) + list(fp_by_config.keys())
        ))
        if all_err_cfgs:
            print(f"  --- Error Distribution by Config ---")
            for cfg in all_err_cfgs:
                print(f"    {cfg}: "
                      f"{fn_by_config.get(cfg, 0)} FN, "
                      f"{fp_by_config.get(cfg, 0)} FP")

        results["error_analysis"] = {
            "threshold": agg_thresh,
            "n_false_negatives": len(fn_list),
            "n_false_positives": len(fp_list),
            "error_rate": round(
                (len(fn_list) + len(fp_list)) / len(psp), 4
            ),
            "false_negatives": fn_list,
            "false_positives": fp_list,
            "fn_by_config": dict(fn_by_config),
            "fp_by_config": dict(fp_by_config),
        }

    # ===================================================================
    # Tier 2: LOCO (if requested or not cv-only)
    # ===================================================================
    if args.loco or (not args.cv_only):
        print("\n" + "=" * 70)
        print("Tier 2: Leave-One-Config-Out (LOCO) Evaluation")
        print("=" * 70)

        loco_results = loco_evaluation(
            texts, labels, config_ids, scenario_ids,
            model_name=args.model, seed=args.seed,
            num_epochs=args.epochs, batch_size=args.batch_size,
            verbose=args.verbose,
        )
        results["loco"] = loco_results

        # Print LOCO summary
        print(f"\n  {'Config (holdout)':<30} {'AUC-ROC':>8} {'Detection':>10} {'FPR':>8}")
        print(f"  {'-'*30} {'-'*8} {'-'*10} {'-'*8}")

        for r in loco_results["per_config"]:
            cfg = r["holdout_config"]
            if r.get("skipped"):
                print(f"  {cfg:<30} {'SKIP':>8} {r.get('reason', ''):>20}")
            else:
                auc_val = r.get("auc_roc", float("nan"))
                det_r = r.get("detection", {}).get("detection_rate", float("nan"))
                fpr_r = r.get("detection", {}).get("fpr", float("nan"))
                print(f"  {cfg:<30} {auc_val:>8.4f} {det_r:>9.1%} {fpr_r:>7.1%}")

        la = loco_results["aggregate"]
        if la.get("loco_auc_mean") is not None:
            print(f"\n  LOCO mean AUC: {la['loco_auc_mean']:.4f} +/- {la['loco_auc_std']:.4f}")
            cv_mean = agg["setfit_auc_mean"]
            drop = cv_mean - la["loco_auc_mean"]
            print(f"  CV-LOCO gap:   {drop:+.4f} "
                  f"({'GENERALIZES' if abs(drop) < 0.05 else 'PARTIAL' if abs(drop) < 0.10 else 'OVERFITS'})")

    # ===================================================================
    # Holdout evaluation (Cat D, E)
    # ===================================================================
    if args.holdout or (not args.cv_only):
        print("\n" + "=" * 70)
        print("Holdout Evaluation: Cat D (Edge) + Cat E (Adversarial)")
        print("=" * 70)

        # Train on all Cat A + C + FP
        holdout_result_d = evaluate_holdout(
            texts, labels, all_scenarios, ["D"],
            model_name=args.model, seed=args.seed,
            num_epochs=args.epochs, batch_size=args.batch_size,
            verbose=args.verbose,
        )
        results["holdout_D"] = holdout_result_d

        holdout_result_e = evaluate_holdout(
            texts, labels, all_scenarios, ["E"],
            model_name=args.model, seed=args.seed,
            num_epochs=args.epochs, batch_size=args.batch_size,
            verbose=args.verbose,
        )
        results["holdout_E"] = holdout_result_e

        for cat_label, hr in [("D (Edge)", holdout_result_d), ("E (Adversarial)", holdout_result_e)]:
            if hr.get("skipped"):
                print(f"\n  Cat {cat_label}: skipped ({hr.get('reason')})")
            else:
                det_h = hr.get("detection_at_0.5", {})
                print(f"\n  Cat {cat_label}: AUC={hr.get('auc_roc', 'N/A')}, "
                      f"Detection={det_h.get('detection_rate', 0):.1%}, "
                      f"F1={det_h.get('f1', 0):.4f} "
                      f"({hr.get('n_samples', 0)} scenarios, {hr.get('n_violations', 0)} violations)")

    # ===================================================================
    # Final summary
    # ===================================================================
    total_duration = time.time() - t_start
    results["total_duration_s"] = round(total_duration, 2)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total duration: {total_duration:.1f}s")
    print(f"  SetFit CV AUC:  {agg['setfit_auc_mean']:.4f} +/- {agg['setfit_auc_std']:.4f}")
    print(f"  Frozen-LR AUC:  {agg['frozen_lr_auc_mean']:.4f} +/- {agg['frozen_lr_auc_std']:.4f}")
    print(f"  Keyword AUC:    {agg['keyword'].get('auc_roc', 'N/A')}")
    contrastive_value = agg["setfit_auc_mean"] - agg["frozen_lr_auc_mean"]
    print(f"  Contrastive fine-tuning value: {contrastive_value:+.4f} AUC")
    if contrastive_value < 0.02:
        print("    => Frozen-LR competitive: contrastive fine-tuning may be unnecessary")
    else:
        print("    => Contrastive fine-tuning adds measurable value")
    if "bootstrap_ci" in results:
        bci = results["bootstrap_ci"]
        print(f"  Bootstrap 95% CI (AUC): [{bci.get('auc_roc_ci_lower', 'N/A')}, "
              f"{bci.get('auc_roc_ci_upper', 'N/A')}]")
    if "error_analysis" in results:
        ea = results["error_analysis"]
        print(f"  Error rate: {ea['error_rate']:.1%} "
              f"({ea['n_false_negatives']} FN + {ea['n_false_positives']} FP)")
    print(f"\n  VERDICT: {verdict}")
    print("=" * 70)

    # Save results
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to {output_path}")
    else:
        default_output = SCRIPT_DIR / "setfit_mve_results.json"
        with open(default_output, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to {default_output}")


if __name__ == "__main__":
    main()

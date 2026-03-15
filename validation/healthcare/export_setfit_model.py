#!/usr/bin/env python3
"""
Export Trained SetFit Model for Production Deployment
=====================================================
Trains a SetFit model on all Cat A + C + FP data (176 samples) and exports
the fine-tuned backbone + classification head for ONNX inference.

Produces:
  models/setfit_healthcare_v1/
    model.onnx         -- Fine-tuned ONNX backbone (MiniLM-L6-v2)
    tokenizer.json     -- HuggingFace tokenizer
    head_weights.json   -- Logistic regression coef_ and intercept_
    manifest.json       -- Training metadata + hash for provenance

The exported model is loaded by telos_governance.setfit_classifier.SetFitBoundaryClassifier.

Usage:
  python3 validation/healthcare/export_setfit_model.py
  python3 validation/healthcare/export_setfit_model.py --output-dir models/setfit_healthcare_v1
  python3 validation/healthcare/export_setfit_model.py --calibration validation/healthcare/setfit_calibration.json

Dependencies:
  pip install setfit datasets scikit-learn onnx onnxruntime
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import warnings
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SCENARIOS_PATH = SCRIPT_DIR / "healthcare_counterfactual_v1.jsonl"


def load_binary_data(path: Path):
    """Load Cat A (violation) + Cat C/FP (legitimate) scenarios."""
    texts, labels = [], []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            s = json.loads(line)
            cat = s["boundary_category"]
            if cat == "A":
                texts.append(s["request_text"])
                labels.append(1)
            elif cat in ("C", "FP"):
                texts.append(s["request_text"])
                labels.append(0)
    return texts, labels


def main():
    parser = argparse.ArgumentParser(
        description="Export trained SetFit model for production deployment"
    )
    parser.add_argument(
        "--output-dir", type=str,
        default=str(PROJECT_ROOT / "models" / "setfit_healthcare_v1"),
        help="Output directory for exported model",
    )
    parser.add_argument(
        "--model", type=str,
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Base sentence-transformer model",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed",
    )
    parser.add_argument(
        "--epochs", type=int, default=1,
        help="Training epochs",
    )
    parser.add_argument(
        "--calibration", type=str, default=None,
        help="Path to calibration JSON (copied into output dir)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output",
    )
    args = parser.parse_args()

    try:
        from datasets import Dataset
        from setfit import SetFitModel, Trainer, TrainingArguments
    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        print("Install with: pip install setfit datasets")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("SetFit Model Export for Production")
    print("=" * 70)

    # Load data
    print("Loading training data...")
    texts, labels = load_binary_data(SCENARIOS_PATH)
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    print(f"  {n_pos} violations + {n_neg} legitimate = {len(texts)} total")

    # Compute dataset hash
    with open(SCENARIOS_PATH, "rb") as f:
        dataset_hash = hashlib.sha256(f.read()).hexdigest()

    # Train on ALL data (no holdout -- this is the production model)
    print(f"\nTraining SetFit on full dataset...")
    train_ds = Dataset.from_dict({"text": texts, "label": labels})

    model = SetFitModel.from_pretrained(args.model)
    training_args = TrainingArguments(
        batch_size=16,
        num_epochs=args.epochs,
        seed=args.seed,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
    )

    t0 = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        trainer.train()
    train_duration = time.time() - t0
    print(f"  Training complete: {train_duration:.1f}s")

    # Extract components
    print(f"\nExporting to {output_dir}/...")

    # 1. Save the fine-tuned model (PyTorch format for ONNX conversion)
    tmp_model_dir = output_dir / "_tmp_model"
    model.save_pretrained(str(tmp_model_dir))

    # 2. Copy tokenizer
    tokenizer_src = tmp_model_dir / "tokenizer.json"
    if not tokenizer_src.exists():
        # Try to find tokenizer from the original model cache
        from huggingface_hub import hf_hub_download
        tokenizer_src = Path(hf_hub_download(args.model, "tokenizer.json"))
    shutil.copy2(str(tokenizer_src), str(output_dir / "tokenizer.json"))
    print(f"  Tokenizer saved")

    # 3. Export backbone to ONNX
    try:
        from optimum.onnxruntime import ORTModelForFeatureExtraction

        ort_model = ORTModelForFeatureExtraction.from_pretrained(
            str(tmp_model_dir), export=True
        )
        ort_model.save_pretrained(str(output_dir))
        # optimum saves as model.onnx in the output dir
        print(f"  ONNX backbone exported via optimum")
    except ImportError:
        # Fallback: manual ONNX export
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
            print(f"  The PyTorch model is saved at {tmp_model_dir}")
            print(f"  Export manually with: optimum-cli export onnx --model {tmp_model_dir} {output_dir}")

    # 4. Extract and save classification head weights
    head = model.model_head
    if hasattr(head, "coef_") and hasattr(head, "intercept_"):
        head_weights = {
            "coef": head.coef_[0].tolist(),
            "intercept": float(head.intercept_[0]),
            "classes": head.classes_.tolist(),
        }
    else:
        # Fallback for non-sklearn heads
        print(f"  WARNING: Head type {type(head)} -- extracting via prediction")
        head_weights = {"coef": [], "intercept": 0.0, "classes": [0, 1]}

    with open(output_dir / "head_weights.json", "w") as f:
        json.dump(head_weights, f, indent=2)
    print(f"  Head weights saved ({len(head_weights['coef'])} dims)")

    # 5. Copy calibration if provided
    if args.calibration:
        cal_path = Path(args.calibration)
        if cal_path.exists():
            shutil.copy2(str(cal_path), str(output_dir / "calibration.json"))
            print(f"  Calibration parameters copied")

    # 6. Create manifest
    manifest = {
        "model_name": "setfit_healthcare_v1",
        "base_model": args.model,
        "training_data": str(SCENARIOS_PATH),
        "dataset_hash": dataset_hash,
        "n_samples": len(texts),
        "n_positive": n_pos,
        "n_negative": n_neg,
        "epochs": args.epochs,
        "seed": args.seed,
        "train_duration_s": round(train_duration, 2),
        "head_dimension": len(head_weights["coef"]),
        "export_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "files": [
            "model.onnx",
            "tokenizer.json",
            "head_weights.json",
            "manifest.json",
        ],
    }
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest saved")

    # Clean up tmp
    if tmp_model_dir.exists():
        shutil.rmtree(str(tmp_model_dir), ignore_errors=True)

    print(f"\n{'=' * 70}")
    print(f"Export complete: {output_dir}")
    print(f"Files: {', '.join(manifest['files'])}")
    print(f"\nLoad with:")
    print(f"  from telos_governance.setfit_classifier import SetFitBoundaryClassifier")
    print(f"  classifier = SetFitBoundaryClassifier('{output_dir}')")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

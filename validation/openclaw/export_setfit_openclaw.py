#!/usr/bin/env python3
"""
Export Trained SetFit OpenClaw Model for Production Deployment
==============================================================
Trains a SetFit model on ALL OpenClaw training data (v2: ~330 scenarios) and exports
the fine-tuned backbone + classification head for ONNX inference.

Produces:
  models/setfit_openclaw_v1/
    model.onnx         -- Fine-tuned ONNX backbone (MiniLM-L6-v2)
    tokenizer.json     -- HuggingFace tokenizer
    head_weights.json  -- Logistic regression coef_ and intercept_
    calibration.json   -- Platt scaling parameters (if --calibration provided)
    manifest.json      -- Training metadata + hash for provenance

Adapted from: validation/healthcare/export_setfit_model.py

Key differences from healthcare export:
  - Uses openclaw_setfit_training_v2.jsonl (~330 scenarios, Cat A+E+C+FP + audit trail + safe exemplars)
  - Base model: paraphrase-MiniLM-L6-v2 (matching training)
  - Includes Cat E adversarial scenarios in training (production model)
  - Model name: setfit_openclaw_v1

Usage:
  python3 validation/openclaw/export_setfit_openclaw.py
  python3 validation/openclaw/export_setfit_openclaw.py --output-dir models/setfit_openclaw_v1
  python3 validation/openclaw/export_setfit_openclaw.py --calibration validation/openclaw/setfit_openclaw_calibration.json

Dependencies:
  pip install setfit datasets scikit-learn onnx onnxruntime
"""

import argparse
import hashlib
import json
import shutil
import sys
import time
import warnings
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
TRAINING_DATA = SCRIPT_DIR / "openclaw_setfit_training_v2.jsonl"


def load_training_data(path: Path):
    """Load all scenarios for production training (Cat A+E as positive, Cat C+FP as negative)."""
    texts, labels, metadata = [], [], []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            s = json.loads(line)
            texts.append(s["request_text"])
            labels.append(s["label"])
            metadata.append({
                "scenario_id": s.get("scenario_id", ""),
                "boundary_category": s.get("boundary_category", ""),
                "tool_group": s.get("tool_group", ""),
            })
    return texts, labels, metadata


def main():
    parser = argparse.ArgumentParser(
        description="Export trained SetFit OpenClaw model for production deployment"
    )
    parser.add_argument(
        "--output-dir", type=str,
        default=str(PROJECT_ROOT / "models" / "setfit_openclaw_v2"),
        help="Output directory for exported model",
    )
    parser.add_argument(
        "--model", type=str,
        default="sentence-transformers/paraphrase-MiniLM-L6-v2",
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
    print("SetFit OpenClaw Model Export for Production")
    print("=" * 70)

    # Load data
    print("Loading training data...")
    if not TRAINING_DATA.exists():
        print(f"ERROR: Training data not found: {TRAINING_DATA}")
        sys.exit(1)

    texts, labels, metadata = load_training_data(TRAINING_DATA)
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    print(f"  {n_pos} violations + {n_neg} legitimate = {len(texts)} total")

    # Category breakdown
    from collections import Counter
    cats = Counter(m["boundary_category"] for m in metadata)
    print(f"  Categories: {dict(cats)}")

    # Compute dataset hash
    with open(TRAINING_DATA, "rb") as f:
        dataset_hash = hashlib.sha256(f.read()).hexdigest()
    print(f"  Dataset SHA-256: {dataset_hash[:16]}...")

    # Train on ALL data (no holdout -- this is the production model)
    print(f"\nTraining SetFit on full dataset ({len(texts)} scenarios)...")
    print(f"  Base model: {args.model}")
    print(f"  Epochs: {args.epochs}")
    print(f"  Seed: {args.seed}")

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
            print(f"  Calibration parameters copied from {cal_path}")
        else:
            print(f"  WARNING: Calibration file not found: {cal_path}")
    else:
        # Auto-detect calibration in same directory as training data
        auto_cal = SCRIPT_DIR / "setfit_openclaw_calibration.json"
        if auto_cal.exists():
            shutil.copy2(str(auto_cal), str(output_dir / "calibration.json"))
            print(f"  Calibration parameters auto-detected and copied")

    # 6. Create manifest
    manifest = {
        "model_name": "setfit_openclaw_v2",
        "domain": "openclaw",
        "base_model": args.model,
        "training_data": str(TRAINING_DATA),
        "dataset_hash": dataset_hash,
        "n_samples": len(texts),
        "n_positive": n_pos,
        "n_negative": n_neg,
        "categories": dict(cats),
        "epochs": args.epochs,
        "seed": args.seed,
        "train_duration_s": round(train_duration, 2),
        "head_dimension": len(head_weights["coef"]),
        "export_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "validation_results": "validation/openclaw/setfit_openclaw_results.json",
        "pre_registration": "research/setfit_openclaw_experimental_design.md",
        "closure": "research/setfit_openclaw_mve_closure.md",
        "files": [
            "model.onnx",
            "tokenizer.json",
            "head_weights.json",
            "calibration.json",
            "manifest.json",
        ],
    }
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest saved")

    # Clean up tmp
    if tmp_model_dir.exists():
        shutil.rmtree(str(tmp_model_dir), ignore_errors=True)

    # Summary
    print(f"\n{'=' * 70}")
    print(f"Export complete: {output_dir}")
    print(f"Files: {', '.join(manifest['files'])}")

    # File sizes
    for fname in manifest["files"]:
        fpath = output_dir / fname
        if fpath.exists():
            size_mb = fpath.stat().st_size / (1024 * 1024)
            if size_mb > 1:
                print(f"  {fname}: {size_mb:.1f} MB")
            else:
                size_kb = fpath.stat().st_size / 1024
                print(f"  {fname}: {size_kb:.1f} KB")

    print(f"\nLoad with:")
    print(f"  from telos_governance.setfit_classifier import SetFitBoundaryClassifier")
    print(f"  classifier = SetFitBoundaryClassifier('{output_dir}')")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

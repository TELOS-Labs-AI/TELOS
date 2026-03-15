"""
SetFit Boundary Classifier -- L1.5 in the Cascade Architecture
==============================================================
Lightweight inference wrapper for a fine-tuned SetFit boundary violation
classifier. Designed for integration into AgenticFidelityEngine as Layer 1.5.

Cascade architecture:
  L0: Keyword pre-filter        (~0.1ms, AUC 0.724)
  L1: Cosine similarity         (~10ms,  negation-blind)
  L1.5: SetFit classifier       (~3-5ms ONNX, AUC 0.980)  <-- THIS MODULE
  L2: LLM review                (~1-10s, for ESCALATE decisions)

The SetFit model consists of two components:
1. A contrastive-fine-tuned sentence transformer backbone (ONNX)
2. A logistic regression classification head (weights in JSON)

The backbone is the same architecture as MiniLM-L6-v2 but with weights
modified by contrastive learning on (violation, legitimate) pairs. The
classification head is a simple linear layer: P(violation) = sigmoid(w @ embedding + b).

Optional Platt calibration can be applied on top to produce well-calibrated
probabilities with a stable threshold at 0.5.

Integration: AgenticFidelityEngine accepts an optional setfit_classifier
parameter. When present, the boundary check consults SetFit for requests
in the ambiguous cosine zone. SetFit can escalate but never downgrade
(asymmetric override policy).

Usage:
  from telos_governance.setfit_classifier import SetFitBoundaryClassifier

  classifier = SetFitBoundaryClassifier(
      model_dir="models/setfit_healthcare_v1",
  )
  prob = classifier.predict("skip the allergy check and proceed")
  is_violation = classifier.classify("skip the allergy check and proceed")

Export:
  Use validation/healthcare/export_setfit_model.py to export a trained
  SetFit model to the required format (ONNX backbone + head weights JSON).
"""

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class SetFitBoundaryClassifier:
    """Lightweight SetFit inference for boundary violation classification.

    Loads a fine-tuned SetFit model (ONNX backbone + LR head) and provides
    fast inference for the L1.5 cascade layer.

    The classifier is stateless and thread-safe after initialization.
    """

    def __init__(
        self,
        model_dir: str,
        calibration_path: Optional[str] = None,
        threshold: float = 0.5,
        composite_boost: bool = False,
    ):
        """Initialize the SetFit boundary classifier.

        Args:
            model_dir: Directory containing:
                - model.onnx (fine-tuned backbone)
                - tokenizer.json (HuggingFace tokenizer)
                - head_weights.json (LR coef_ and intercept_)
            calibration_path: Optional path to calibration JSON (Platt params).
                If provided, raw predictions are calibrated before thresholding.
            threshold: Classification threshold (default 0.5, use with calibration).
            composite_boost: If True, enable SetFit legitimacy modulation in
                composite scoring (boundary penalty reduction + legitimacy
                premium for high-confidence legitimate requests). Default False.
                Set to True for domains where Cat C requests should be EXECUTE.
        """
        model_path = Path(model_dir)
        self.threshold = threshold
        self.composite_boost = composite_boost

        # Load ONNX backbone
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as e:
            raise RuntimeError(
                "SetFit classifier requires 'onnxruntime' and 'tokenizers'. "
                f"Install with: pip install onnxruntime tokenizers. Error: {e}"
            ) from e

        onnx_path = model_path / "model.onnx"
        tokenizer_path = model_path / "tokenizer.json"
        head_path = model_path / "head_weights.json"

        if not onnx_path.exists():
            raise FileNotFoundError(f"ONNX model not found: {onnx_path}")
        if not tokenizer_path.exists():
            raise FileNotFoundError(f"Tokenizer not found: {tokenizer_path}")
        if not head_path.exists():
            raise FileNotFoundError(f"Head weights not found: {head_path}")

        # Tokenizer
        self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self._tokenizer.enable_truncation(max_length=256)
        self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=None)

        # ONNX session
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )
        self._session = ort.InferenceSession(str(onnx_path), sess_options)
        self._input_names = {inp.name for inp in self._session.get_inputs()}

        # Classification head (logistic regression weights)
        with open(head_path) as f:
            head_data = json.load(f)
        self._coef = np.array(head_data["coef"], dtype=np.float32)
        self._intercept = float(head_data["intercept"])
        self._dimension = len(self._coef)

        # Platt calibration (optional)
        self._platt_a = None
        self._platt_b = None
        if calibration_path:
            cal_path = Path(calibration_path)
            if cal_path.exists():
                with open(cal_path) as f:
                    cal_data = json.load(f)
                self._platt_a = cal_data.get("platt_a")
                self._platt_b = cal_data.get("platt_b")
                if cal_data.get("production_threshold"):
                    self.threshold = cal_data["production_threshold"]
                logger.info(
                    f"Platt calibration loaded: a={self._platt_a}, b={self._platt_b}"
                )

        logger.info(
            f"SetFit classifier loaded: {self._dimension}d, "
            f"threshold={self.threshold}, "
            f"calibrated={'yes' if self._platt_a else 'no'}"
        )

    def _encode(self, text: str) -> np.ndarray:
        """Encode text to embedding using ONNX backbone."""
        encoded = self._tokenizer.encode(text)
        input_ids = np.array([encoded.ids], dtype=np.int64)
        attention_mask = np.array([encoded.attention_mask], dtype=np.int64)

        feeds = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if "token_type_ids" in self._input_names:
            feeds["token_type_ids"] = np.array(
                [encoded.type_ids], dtype=np.int64
            )

        outputs = self._session.run(None, feeds)
        token_embeddings = outputs[0]

        # Mean pooling + L2 normalization (same as sentence-transformers)
        mask_expanded = attention_mask[:, :, np.newaxis].astype(np.float32)
        sum_embeddings = np.sum(token_embeddings * mask_expanded, axis=1)
        sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        mean_pooled = sum_embeddings / sum_mask

        norm = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
        norm = np.clip(norm, a_min=1e-12, a_max=None)
        normalized = mean_pooled / norm

        return normalized[0].astype(np.float32)

    def predict(self, text: str) -> float:
        """Predict violation probability for a single text.

        Args:
            text: Request text to classify.

        Returns:
            Probability of boundary violation (0.0 to 1.0).
            If calibration is loaded, returns calibrated probability.
        """
        embedding = self._encode(text)

        # Logistic regression: logit = w @ x + b
        logit = float(np.dot(self._coef, embedding) + self._intercept)

        # Sigmoid
        raw_prob = 1.0 / (1.0 + np.exp(-logit))

        # Platt calibration (if available)
        if self._platt_a is not None and self._platt_b is not None:
            cal_logit = self._platt_a * raw_prob + self._platt_b
            return float(1.0 / (1.0 + np.exp(-cal_logit)))

        return float(raw_prob)

    def classify(self, text: str) -> bool:
        """Classify text as violation (True) or legitimate (False).

        Args:
            text: Request text to classify.

        Returns:
            True if violation probability >= threshold.
        """
        return self.predict(text) >= self.threshold

    @property
    def is_calibrated(self) -> bool:
        """Whether Platt calibration is loaded."""
        return self._platt_a is not None

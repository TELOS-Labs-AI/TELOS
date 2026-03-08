"""
Embedding providers for TELOS.

Provides three implementations:
1. DeterministicEmbeddingProvider - Fast, deterministic (for testing)
2. SentenceTransformerProvider - Real semantic embeddings (PyTorch, ~2GB install)
3. OnnxEmbeddingProvider - Real semantic embeddings (ONNX Runtime, ~90MB install)

The ONNX provider produces numerically equivalent embeddings to the
SentenceTransformer provider for the same model, but without the PyTorch
dependency. This makes it suitable for lightweight CLI deployments where
install size matters.
"""

from __future__ import annotations
import hashlib
import logging
import numpy as np
from typing import Optional


class DeterministicEmbeddingProvider:
    """
    Deterministic embedding provider for testing.

    Uses hash-based embeddings that are:
    - Deterministic (same text -> same embedding)
    - Fast (no model loading)
    - Suitable for unit tests and rapid iteration

    NOT suitable for production (no semantic meaning).
    """

    def __init__(self, dimension: int = 384):
        """
        Args:
            dimension: Embedding dimension
        """
        self.dimension = dimension

    def encode(self, text: str) -> np.ndarray:
        """
        Generate deterministic embedding from text hash.

        Args:
            text: Input text

        Returns:
            Deterministic embedding vector
        """
        # Create hash of text
        hash_obj = hashlib.sha256(text.encode('utf-8'))
        hash_bytes = hash_obj.digest()

        # Expand hash to desired dimension
        embedding = []
        for i in range(self.dimension):
            byte_index = i % len(hash_bytes)
            value = hash_bytes[byte_index] / 255.0  # Normalize to [0, 1]
            embedding.append(value)

        return np.array(embedding, dtype=np.float32)


class MistralEmbeddingProvider:
    """
    Mistral embedding provider using mistral-embed API.

    Provides high-quality 1024-dimensional embeddings via Mistral's API.
    Requires MISTRAL_API_KEY environment variable.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Mistral API key (optional, will use env var if not provided)
        """
        import os
        from mistralai import Mistral

        self.api_key = api_key or os.environ.get('MISTRAL_API_KEY')
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY not found in environment or parameters")

        self.client = Mistral(api_key=self.api_key)
        self.dimension = 1024  # mistral-embed produces 1024-dimensional vectors
        self.model_name = "mistral-embed"

    def encode(self, text: str) -> np.ndarray:
        """
        Generate semantic embedding using Mistral API.

        Args:
            text: Input text

        Returns:
            Semantic embedding vector (1024 dimensions)
        """
        try:
            response = self.client.embeddings.create(
                model=self.model_name,
                inputs=[text]
            )
            # Extract embedding from response
            embedding = response.data[0].embedding
            return np.array(embedding, dtype=np.float32)
        except Exception as e:
            raise RuntimeError(f"Mistral embedding API error: {e}")

    def batch_encode(self, texts: list) -> list:
        """
        Generate semantic embeddings for multiple texts in a single API call.

        Args:
            texts: List of input texts

        Returns:
            List of semantic embedding vectors (1024 dimensions each)
        """
        if not texts:
            return []

        try:
            response = self.client.embeddings.create(
                model=self.model_name,
                inputs=texts
            )
            embeddings = [np.array(item.embedding, dtype=np.float32) for item in response.data]
            return embeddings
        except Exception as e:
            raise RuntimeError(f"Mistral batch embedding API error: {e}")


class SentenceTransformerProvider:
    """
    Production embedding provider using sentence-transformers.

    Provides semantic embeddings suitable for:
    - Real governance applications
    - Semantic similarity comparisons
    - Production deployments
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Args:
            model_name: HuggingFace model identifier
        """
        import logging

        from sentence_transformers import SentenceTransformer

        self.model_name = model_name

        try:
            self.model = SentenceTransformer(model_name)
            logging.info(f"SentenceTransformer loaded successfully: {model_name}")
        except Exception as e:
            logging.warning(f"Primary load failed: {e}, trying alternative approach")
            try:
                import torch
                with torch.inference_mode():
                    self.model = SentenceTransformer(model_name, device='cpu')
            except Exception as e2:
                logging.error(f"All SentenceTransformer loading approaches failed: {e2}")
                raise RuntimeError(f"Failed to load SentenceTransformer model: {e2}")

        self.dimension = self.model.get_sentence_embedding_dimension()

    def encode(self, text: str) -> np.ndarray:
        """
        Generate semantic embedding for text.

        Args:
            text: Input text

        Returns:
            Semantic embedding vector
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.astype(np.float32)


class OnnxEmbeddingProvider:
    """
    ONNX Runtime embedding provider — lightweight alternative to SentenceTransformerProvider.

    Uses ONNX Runtime + HuggingFace tokenizers instead of PyTorch + sentence-transformers.
    Produces numerically equivalent embeddings (< 1e-5 L2 distance) for the same model.

    Install size: ~90MB (onnxruntime + tokenizers) vs ~2GB (torch + sentence-transformers).
    Inference speed: Comparable to PyTorch CPU on single texts; faster for batch on some hardware.

    Downloads model files from HuggingFace Hub on first use (cached in ~/.cache/huggingface/).
    """

    # Supported models, ONNX paths, and pinned SHA-256 hashes for integrity.
    # Hash mismatch = fail closed (refuse to score with tampered model).
    _SUPPORTED_MODELS = {
        "sentence-transformers/all-MiniLM-L6-v2": {
            "onnx_file": "onnx/model.onnx",
            "dimension": 384,
            "max_length": 256,
            "sha256": "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452",
        },
        "sentence-transformers/all-mpnet-base-v2": {
            "onnx_file": "onnx/model.onnx",
            "dimension": 768,
            "max_length": 384,
            "sha256": "74187b16d9c946fea252e120cfd7a12c5779d8b8b86838a2e4c56573c47941bd",
        },
    }

    @staticmethod
    def _verify_model_hash(model_path: str, expected_hash: str) -> bool:
        """Verify ONNX model file integrity against pinned SHA-256 hash."""
        import hashlib
        h = hashlib.sha256()
        with open(model_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        actual = h.hexdigest()
        if actual != expected_hash:
            logging.critical(
                f"ONNX model integrity FAILED: "
                f"expected sha256:{expected_hash[:16]}..., "
                f"got sha256:{actual[:16]}..."
            )
            return False
        return True

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Args:
            model_name: HuggingFace model identifier. Must be one of the supported models.

        Raises:
            ValueError: If the model is not supported.
            RuntimeError: If ONNX Runtime or tokenizer files cannot be loaded.
        """
        import logging

        if model_name not in self._SUPPORTED_MODELS:
            supported = ", ".join(self._SUPPORTED_MODELS.keys())
            raise ValueError(
                f"Unsupported ONNX model: {model_name}. Supported: {supported}"
            )

        self.model_name = model_name
        model_info = self._SUPPORTED_MODELS[model_name]
        self.dimension = model_info["dimension"]
        self._max_length = model_info["max_length"]

        try:
            import onnxruntime as ort
            from huggingface_hub import hf_hub_download
            from tokenizers import Tokenizer

            # Download and load tokenizer
            tokenizer_path = hf_hub_download(model_name, "tokenizer.json")
            self._tokenizer = Tokenizer.from_file(tokenizer_path)
            self._tokenizer.enable_truncation(max_length=self._max_length)
            self._tokenizer.enable_padding(
                pad_id=0, pad_token="[PAD]", length=None
            )

            # Download and load ONNX model with integrity verification
            onnx_path = hf_hub_download(model_name, model_info["onnx_file"])
            expected_hash = model_info.get("sha256")
            if expected_hash and not self._verify_model_hash(onnx_path, expected_hash):
                raise RuntimeError(
                    f"ONNX model integrity check failed for {model_name}. "
                    f"Model file may be corrupted or tampered with."
                )
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._session = ort.InferenceSession(onnx_path, sess_options)

            logging.info(f"ONNX model loaded: {model_name} ({self.dimension}d)")

        except ImportError as e:
            raise RuntimeError(
                f"ONNX provider requires 'onnxruntime' and 'tokenizers'. "
                f"Install with: pip install onnxruntime tokenizers huggingface_hub. "
                f"Error: {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Failed to load ONNX model {model_name}: {e}") from e

    def encode(self, text: str) -> np.ndarray:
        """
        Generate semantic embedding for text using ONNX Runtime.

        Applies the same mean-pooling + L2-normalization as SentenceTransformer.

        Args:
            text: Input text

        Returns:
            Semantic embedding vector (same as SentenceTransformerProvider output)
        """
        # Tokenize
        encoded = self._tokenizer.encode(text)
        input_ids = np.array([encoded.ids], dtype=np.int64)
        attention_mask = np.array([encoded.attention_mask], dtype=np.int64)
        token_type_ids = np.array([encoded.type_ids], dtype=np.int64)

        # Run ONNX inference — only include inputs the model expects
        feeds = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        model_input_names = {inp.name for inp in self._session.get_inputs()}
        if "token_type_ids" in model_input_names:
            feeds["token_type_ids"] = token_type_ids
        outputs = self._session.run(None, feeds)

        # outputs[0] is token_embeddings: (1, seq_len, hidden_dim)
        token_embeddings = outputs[0]

        # Mean pooling (same as sentence-transformers default)
        mask_expanded = attention_mask[:, :, np.newaxis].astype(np.float32)
        sum_embeddings = np.sum(token_embeddings * mask_expanded, axis=1)
        sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        mean_pooled = sum_embeddings / sum_mask

        # L2 normalization (same as sentence-transformers default for this model)
        norm = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
        norm = np.clip(norm, a_min=1e-12, a_max=None)
        normalized = mean_pooled / norm

        return normalized[0].astype(np.float32)


class MlxEmbeddingProvider:
    """
    MLX embedding provider for Apple Silicon.

    Uses mlx-embeddings for native Metal acceleration on M-series chips.
    Optional dependency — raises RuntimeError with install instructions if
    mlx or mlx-embeddings is not available.

    Install size: ~200MB (mlx + mlx-embeddings). Apple Silicon only (M1+).
    Inference speed: ~2ms per embedding on M-series (faster than ONNX).

    Downloads model files from HuggingFace Hub on first use (cached in ~/.cache/huggingface/).
    """

    def __init__(self, model_name: str = "mlx-community/all-MiniLM-L6-v2-4bit"):
        """
        Args:
            model_name: HuggingFace model identifier (mlx-community/* models).

        Raises:
            RuntimeError: If mlx or mlx-embeddings is not installed.
        """
        import logging

        try:
            from mlx_embeddings.utils import load as mlx_load
            from mlx_embeddings import generate as mlx_generate
            import mlx.core as mx
        except ImportError as e:
            raise RuntimeError(
                "MLX provider requires 'mlx' and 'mlx-embeddings'. "
                "Install with: pip install mlx mlx-embeddings. "
                "Requires Apple Silicon (M1+). "
                f"Error: {e}"
            ) from e

        self.model_name = model_name
        self._mx = mx
        self._generate = mlx_generate
        self._model, self._tokenizer = mlx_load(model_name)

        # Auto-detect dimension via probe encode
        probe_output = self._generate(self._model, self._tokenizer, "probe")
        self.dimension = int(probe_output.text_embeds.shape[-1])

        logging.info(f"MLX model loaded: {model_name} ({self.dimension}d)")

    def encode(self, text: str) -> np.ndarray:
        """
        Generate semantic embedding for text using MLX.

        Uses mlx-embeddings generate() which handles tokenization,
        forward pass, mean pooling, and L2 normalization internally.

        Args:
            text: Input text

        Returns:
            L2-normalized semantic embedding vector, shape (dimension,)
        """
        output = self._generate(self._model, self._tokenizer, text)
        embedding = np.array(
            output.text_embeds[0].tolist(), dtype=np.float32
        )

        # Defensive L2 normalization (mlx-embeddings already normalizes,
        # but ensure contract for all model versions)
        norm = np.linalg.norm(embedding)
        if norm > 1e-12:
            embedding = embedding / norm

        return embedding


MODEL_ALIASES = {
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",
    "mpnet": "sentence-transformers/all-mpnet-base-v2",
    # MLX variants (Apple Silicon only)
    "minilm-mlx": "mlx-community/all-MiniLM-L6-v2-4bit",
}

# Map standard model names to MLX equivalents for --backend mlx resolution
_MLX_MODEL_MAP = {
    "sentence-transformers/all-MiniLM-L6-v2": "mlx-community/all-MiniLM-L6-v2-4bit",
}


def EmbeddingProvider(
    deterministic: bool = False,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    backend: str = "auto",
):
    """
    Factory function to create appropriate embedding provider.

    Args:
        deterministic: If True, use fast deterministic embeddings (testing).
                      If False, use real semantic embeddings (production).
        model_name: Model name or alias ("minilm", "mpnet", "minilm-mlx").
                   Ignored if deterministic=True.
        backend: "auto" (try ONNX first, fall back to SentenceTransformer),
                "onnx" (require ONNX), "torch" (require SentenceTransformer),
                "mlx" (require MLX, Apple Silicon only)

    Returns:
        Embedding provider instance
    """
    # Resolve alias to full model name
    model_name = MODEL_ALIASES.get(model_name, model_name)

    if deterministic:
        return DeterministicEmbeddingProvider()

    if backend == "mlx":
        # Map standard model names to MLX equivalents if needed
        mlx_model = _MLX_MODEL_MAP.get(model_name, model_name)
        return MlxEmbeddingProvider(model_name=mlx_model)
    elif backend == "onnx":
        return OnnxEmbeddingProvider(model_name=model_name)
    elif backend == "torch":
        return SentenceTransformerProvider(model_name=model_name)
    else:
        # auto: try ONNX first (lighter), fall back to SentenceTransformer
        # MLX is never auto-selected (explicit opt-in only)
        try:
            return OnnxEmbeddingProvider(model_name=model_name)
        except (RuntimeError, ValueError):
            return SentenceTransformerProvider(model_name=model_name)


# =============================================================================
# FIDELITY RESCALING FOR SENTENCETRANSFORMER
# =============================================================================

def rescale_sentence_transformer_fidelity(raw_score: float) -> float:
    """
    Rescale SentenceTransformer cosine similarity to TELOS fidelity range.

    Formula: fidelity = 0.25 + raw_score * 1.8, clamped to [0.0, 1.0]

    This maps:
        raw 0.00 -> 0.25 (RED - clearly off-topic)
        raw 0.15 -> 0.52 (ORANGE - borderline)
        raw 0.25 -> 0.70 (GREEN - on-topic threshold)
        raw 0.35 -> 0.88 (GREEN - strongly aligned)
        raw 0.50 -> 1.00 (GREEN - perfect alignment)

    Args:
        raw_score: Raw cosine similarity from SentenceTransformer (-1.0 to 1.0)

    Returns:
        Rescaled fidelity score for TELOS (0.0 to 1.0)
    """
    rescaled = 0.25 + raw_score * 1.8
    return max(0.0, min(1.0, rescaled))


# =============================================================================
# CACHED PROVIDER SINGLETONS
# =============================================================================

_cached_minilm_provider = None
_cached_mpnet_provider = None
_cached_onnx_minilm_provider = None
_cached_onnx_mpnet_provider = None


def get_cached_minilm_provider() -> SentenceTransformerProvider:
    """
    Return a cached singleton SentenceTransformerProvider (all-MiniLM-L6-v2).

    Avoids reloading the model on every call. The provider exposes an
    ``encode(text) -> np.ndarray`` method suitable for use as ``embed_fn``
    throughout the governance pipeline.

    Returns:
        Cached SentenceTransformerProvider instance
    """
    global _cached_minilm_provider
    if _cached_minilm_provider is None:
        _cached_minilm_provider = SentenceTransformerProvider(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
    return _cached_minilm_provider


def get_cached_onnx_minilm_provider() -> OnnxEmbeddingProvider:
    """
    Return a cached singleton OnnxEmbeddingProvider (all-MiniLM-L6-v2).

    Lightweight alternative to get_cached_minilm_provider() that avoids
    the PyTorch dependency. Produces numerically equivalent embeddings.

    Returns:
        Cached OnnxEmbeddingProvider instance

    Raises:
        RuntimeError: If onnxruntime is not installed.
    """
    global _cached_onnx_minilm_provider
    if _cached_onnx_minilm_provider is None:
        _cached_onnx_minilm_provider = OnnxEmbeddingProvider(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
    return _cached_onnx_minilm_provider


def get_cached_onnx_mpnet_provider() -> OnnxEmbeddingProvider:
    """
    Return a cached singleton OnnxEmbeddingProvider (all-mpnet-base-v2).

    Used by the confirmer safety gate for boundary-only checks.
    Lazy-loaded on first confirmer activation to avoid ~80ms load
    overhead when the confirmer is not needed.

    Returns:
        Cached OnnxEmbeddingProvider instance (768-dim)

    Raises:
        RuntimeError: If onnxruntime is not installed.
    """
    global _cached_onnx_mpnet_provider
    if _cached_onnx_mpnet_provider is None:
        _cached_onnx_mpnet_provider = OnnxEmbeddingProvider(
            model_name="sentence-transformers/all-mpnet-base-v2"
        )
    return _cached_onnx_mpnet_provider


def get_cached_mpnet_provider() -> SentenceTransformerProvider:
    """
    Return a cached singleton SentenceTransformerProvider (all-mpnet-base-v2).

    Used for AI response fidelity checking and behavioral fidelity computation.
    MPNet provides 768-dimensional embeddings with stronger semantic sensitivity
    than MiniLM (384-dim), making it better suited for response quality assessment.

    Returns:
        Cached SentenceTransformerProvider instance
    """
    global _cached_mpnet_provider
    if _cached_mpnet_provider is None:
        _cached_mpnet_provider = SentenceTransformerProvider(
            model_name="sentence-transformers/all-mpnet-base-v2"
        )
    return _cached_mpnet_provider

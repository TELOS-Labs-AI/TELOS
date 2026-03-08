"""
Tests for MlxEmbeddingProvider
================================

Tests for MLX-based embedding provider (Apple Silicon only).
Entire file is skipped on non-Apple platforms or when MLX is not installed.
"""

import numpy as np
import pytest

# Skip entire module if MLX is not available
mlx = pytest.importorskip("mlx", reason="MLX requires Apple Silicon (M1+)")
pytest.importorskip("mlx_embeddings", reason="mlx-embeddings not installed")

from telos_core.embedding_provider import (
    MlxEmbeddingProvider,
    EmbeddingProvider,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mlx_provider():
    """MLX MiniLM-4bit provider (module-scoped to avoid reloading)."""
    return MlxEmbeddingProvider()


@pytest.fixture(scope="module")
def onnx_provider():
    """ONNX MiniLM provider for cross-backend comparison."""
    from telos_core.embedding_provider import OnnxEmbeddingProvider
    return OnnxEmbeddingProvider()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestMlxInit:
    def test_default_model(self, mlx_provider):
        assert "MiniLM" in mlx_provider.model_name or "minilm" in mlx_provider.model_name.lower()

    def test_dimension(self, mlx_provider):
        assert mlx_provider.dimension == 384

    def test_model_loaded(self, mlx_provider):
        assert mlx_provider._model is not None

    def test_tokenizer_loaded(self, mlx_provider):
        assert mlx_provider._tokenizer is not None


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------

class TestMlxEncoding:
    def test_encode_returns_numpy(self, mlx_provider):
        emb = mlx_provider.encode("test text")
        assert isinstance(emb, np.ndarray)

    def test_encode_correct_dimension(self, mlx_provider):
        emb = mlx_provider.encode("test text")
        assert emb.shape == (384,)

    def test_encode_float32(self, mlx_provider):
        emb = mlx_provider.encode("test text")
        assert emb.dtype == np.float32

    def test_encode_deterministic(self, mlx_provider):
        emb1 = mlx_provider.encode("same text")
        emb2 = mlx_provider.encode("same text")
        np.testing.assert_array_equal(emb1, emb2)

    def test_encode_different_texts_differ(self, mlx_provider):
        emb1 = mlx_provider.encode("hello world")
        emb2 = mlx_provider.encode("completely unrelated topic about quantum physics")
        assert not np.allclose(emb1, emb2, atol=0.01)

    def test_encode_empty_string(self, mlx_provider):
        emb = mlx_provider.encode("")
        assert emb.shape == (384,)

    def test_encode_long_text(self, mlx_provider):
        long_text = "word " * 200
        emb = mlx_provider.encode(long_text)
        assert emb.shape == (384,)


# ---------------------------------------------------------------------------
# L2 normalization
# ---------------------------------------------------------------------------

class TestMlxNormalization:
    def test_output_is_unit_vector(self, mlx_provider):
        emb = mlx_provider.encode("test normalization")
        norm = np.linalg.norm(emb)
        assert abs(norm - 1.0) < 1e-4

    def test_multiple_texts_all_normalized(self, mlx_provider):
        texts = [
            "first text",
            "second text about something else",
            "a very long third text that goes on and on about various topics",
        ]
        for text in texts:
            emb = mlx_provider.encode(text)
            norm = np.linalg.norm(emb)
            assert abs(norm - 1.0) < 1e-4, f"Not unit vector for: {text}"


# ---------------------------------------------------------------------------
# Cross-backend similarity (MLX 4-bit vs ONNX full precision)
# ---------------------------------------------------------------------------

class TestMlxOnnxSimilarity:
    """MLX 4-bit quantized should be close (but not identical) to ONNX full precision."""

    SIMILARITY_TEXTS = [
        "What is the roof condition score for this property?",
        "Assess the risk profile for 742 Evergreen Terrace",
        "Generate a risk assessment report",
        "What is the capital of France?",
    ]

    @pytest.mark.parametrize("text", SIMILARITY_TEXTS)
    def test_cosine_similarity_above_threshold(self, mlx_provider, onnx_provider, text):
        """4-bit quantization should maintain >= 0.90 cosine similarity."""
        e_mlx = mlx_provider.encode(text)
        e_onnx = onnx_provider.encode(text)
        cos_sim = np.dot(e_mlx, e_onnx) / (np.linalg.norm(e_mlx) * np.linalg.norm(e_onnx))
        assert cos_sim > 0.90, f"Cosine {cos_sim:.4f} too low for: {text!r}"


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

class TestMlxFactory:
    def test_factory_mlx_backend(self):
        provider = EmbeddingProvider(backend="mlx")
        assert isinstance(provider, MlxEmbeddingProvider)

    def test_factory_auto_does_not_select_mlx(self):
        """Auto should prefer ONNX, never auto-select MLX."""
        provider = EmbeddingProvider(backend="auto")
        assert not isinstance(provider, MlxEmbeddingProvider)

    def test_factory_mlx_with_model_alias(self):
        provider = EmbeddingProvider(backend="mlx", model_name="minilm")
        assert isinstance(provider, MlxEmbeddingProvider)
        assert "minilm" in provider.model_name.lower() or "MiniLM" in provider.model_name

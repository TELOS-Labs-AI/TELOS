"""
Tests for OnnxEmbeddingProvider
================================

Tests for ONNX Runtime-based embedding provider: initialization, encoding,
mean pooling, L2 normalization, and equivalence with SentenceTransformerProvider.
"""

import numpy as np
import pytest

from telos_core.embedding_provider import (
    OnnxEmbeddingProvider,
    SentenceTransformerProvider,
    EmbeddingProvider,
    get_cached_onnx_minilm_provider,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def onnx_provider():
    """ONNX MiniLM provider (module-scoped to avoid reloading)."""
    return OnnxEmbeddingProvider()

@pytest.fixture(scope="module")
def st_provider():
    """SentenceTransformer MiniLM provider (module-scoped to avoid reloading)."""
    return SentenceTransformerProvider()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestOnnxInit:
    def test_default_model(self, onnx_provider):
        assert onnx_provider.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert onnx_provider.dimension == 384

    def test_unsupported_model_raises(self):
        with pytest.raises(ValueError, match="Unsupported ONNX model"):
            OnnxEmbeddingProvider(model_name="not-a-real/model")

    def test_session_loaded(self, onnx_provider):
        assert onnx_provider._session is not None

    def test_tokenizer_loaded(self, onnx_provider):
        assert onnx_provider._tokenizer is not None

    def test_model_hash_pinned(self):
        """Pinned SHA-256 hash must match the actual model file."""
        from huggingface_hub import hf_hub_download
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        info = OnnxEmbeddingProvider._SUPPORTED_MODELS[model_name]
        path = hf_hub_download(model_name, info["onnx_file"])
        assert OnnxEmbeddingProvider._verify_model_hash(path, info["sha256"])

    def test_tampered_hash_fails(self, tmp_path):
        """Wrong hash must fail verification."""
        dummy = tmp_path / "model.onnx"
        dummy.write_bytes(b"tampered model data")
        assert not OnnxEmbeddingProvider._verify_model_hash(
            str(dummy), "0" * 64
        )


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------

class TestOnnxEncoding:
    def test_encode_returns_numpy(self, onnx_provider):
        emb = onnx_provider.encode("test text")
        assert isinstance(emb, np.ndarray)

    def test_encode_correct_dimension(self, onnx_provider):
        emb = onnx_provider.encode("test text")
        assert emb.shape == (384,)

    def test_encode_float32(self, onnx_provider):
        emb = onnx_provider.encode("test text")
        assert emb.dtype == np.float32

    def test_encode_deterministic(self, onnx_provider):
        emb1 = onnx_provider.encode("same text")
        emb2 = onnx_provider.encode("same text")
        np.testing.assert_array_equal(emb1, emb2)

    def test_encode_different_texts_differ(self, onnx_provider):
        emb1 = onnx_provider.encode("hello world")
        emb2 = onnx_provider.encode("completely unrelated topic about quantum physics")
        assert not np.allclose(emb1, emb2, atol=0.01)

    def test_encode_empty_string(self, onnx_provider):
        emb = onnx_provider.encode("")
        assert emb.shape == (384,)

    def test_encode_long_text_truncated(self, onnx_provider):
        long_text = "word " * 1000
        emb = onnx_provider.encode(long_text)
        assert emb.shape == (384,)


# ---------------------------------------------------------------------------
# L2 normalization
# ---------------------------------------------------------------------------

class TestOnnxNormalization:
    def test_output_is_unit_vector(self, onnx_provider):
        emb = onnx_provider.encode("test normalization")
        norm = np.linalg.norm(emb)
        assert abs(norm - 1.0) < 1e-5

    def test_multiple_texts_all_normalized(self, onnx_provider):
        texts = [
            "first text",
            "second text about something else",
            "a very long third text that goes on and on about various topics",
        ]
        for text in texts:
            emb = onnx_provider.encode(text)
            norm = np.linalg.norm(emb)
            assert abs(norm - 1.0) < 1e-5, f"Not unit vector for: {text}"


# ---------------------------------------------------------------------------
# Equivalence with SentenceTransformerProvider
# ---------------------------------------------------------------------------

class TestOnnxEquivalence:
    """Verify ONNX and SentenceTransformer produce equivalent embeddings."""

    EQUIVALENCE_TEXTS = [
        "What is the roof condition score for this property?",
        "Approve the insurance claim for this policyholder",
        "Generate a risk assessment report",
        "Assess the risk profile for 742 Evergreen Terrace",
        "Score the roof condition and flag any material concerns",
        "Run the property analysis and provide risk assessment details",
        "What is the capital of France?",
        "The quick brown fox jumps over the lazy dog",
        "",
        "a",
    ]

    @pytest.mark.parametrize("text", EQUIVALENCE_TEXTS)
    def test_l2_distance_below_threshold(self, onnx_provider, st_provider, text):
        e_onnx = onnx_provider.encode(text)
        e_st = st_provider.encode(text)
        l2_dist = np.linalg.norm(e_onnx - e_st)
        assert l2_dist < 0.001, f"L2 distance {l2_dist} for: {text!r}"

    @pytest.mark.parametrize("text", EQUIVALENCE_TEXTS)
    def test_cosine_similarity_near_one(self, onnx_provider, st_provider, text):
        e_onnx = onnx_provider.encode(text)
        e_st = st_provider.encode(text)
        n_onnx = np.linalg.norm(e_onnx)
        n_st = np.linalg.norm(e_st)
        if n_onnx > 0 and n_st > 0:
            cos_sim = np.dot(e_onnx, e_st) / (n_onnx * n_st)
            assert cos_sim > 0.9999, f"Cosine {cos_sim} for: {text!r}"


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

class TestEmbeddingFactory:
    def test_factory_onnx_backend(self):
        provider = EmbeddingProvider(backend="onnx")
        assert isinstance(provider, OnnxEmbeddingProvider)

    def test_factory_torch_backend(self):
        provider = EmbeddingProvider(backend="torch")
        assert isinstance(provider, SentenceTransformerProvider)

    def test_factory_auto_backend(self):
        provider = EmbeddingProvider(backend="auto")
        # Should prefer ONNX when available
        assert isinstance(provider, OnnxEmbeddingProvider)

    def test_factory_deterministic_ignores_backend(self):
        from telos_core.embedding_provider import DeterministicEmbeddingProvider
        provider = EmbeddingProvider(deterministic=True, backend="onnx")
        assert isinstance(provider, DeterministicEmbeddingProvider)


# ---------------------------------------------------------------------------
# Cached singleton
# ---------------------------------------------------------------------------

class TestCachedOnnxProvider:
    def test_singleton_same_instance(self):
        p1 = get_cached_onnx_minilm_provider()
        p2 = get_cached_onnx_minilm_provider()
        assert p1 is p2

    def test_singleton_is_onnx_provider(self):
        p = get_cached_onnx_minilm_provider()
        assert isinstance(p, OnnxEmbeddingProvider)
        assert p.dimension == 384

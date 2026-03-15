"""
Tests for telos_governance.agentic_pa
======================================

Tests for AgenticPA, BoundarySpec, ToolAuth, ActionTierSpec.
Uses deterministic 3-dim mock embeddings to verify geometry math.
"""

import numpy as np
import pytest

from telos_governance.agentic_pa import (
    AgenticPA,
    BoundarySpec,
    ToolAuth,
    ActionTierSpec,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embedding(values: list) -> np.ndarray:
    """Create a normalized embedding vector."""
    v = np.array(values, dtype=np.float64)
    norm = np.linalg.norm(v)
    if norm > 0:
        v = v / norm
    return v


def _deterministic_embed_fn(text: str) -> np.ndarray:
    """
    Deterministic embed function for testing.

    Returns a 3-dim vector based on a hash of the text,
    so the same text always produces the same embedding.
    """
    h = hash(text) % 10000
    v = np.array([h % 97, (h * 3 + 7) % 97, (h * 7 + 13) % 97], dtype=np.float64)
    norm = np.linalg.norm(v)
    if norm > 0:
        v = v / norm
    return v


# ---------------------------------------------------------------------------
# BoundarySpec
# ---------------------------------------------------------------------------

class TestBoundarySpec:
    def test_default_severity_is_hard(self):
        b = BoundarySpec(text="no data deletion")
        assert b.severity == "hard"
        assert b.text == "no data deletion"
        assert b.embedding is None

    def test_custom_severity(self):
        b = BoundarySpec(text="warn on large queries", severity="soft")
        assert b.severity == "soft"

    def test_embedding_stored(self):
        emb = _make_embedding([1.0, 0.0, 0.0])
        b = BoundarySpec(text="test", embedding=emb)
        np.testing.assert_array_almost_equal(b.embedding, emb)


# ---------------------------------------------------------------------------
# ToolAuth
# ---------------------------------------------------------------------------

class TestToolAuth:
    def test_defaults(self):
        t = ToolAuth(tool_name="sql_query", description="Run SQL queries")
        assert t.risk_level == "low"
        assert t.requires_confirmation is False
        assert t.pa_alignment == 0.0

    def test_custom_risk_level(self):
        t = ToolAuth(
            tool_name="process_refund",
            description="Process customer refund",
            risk_level="high",
            requires_confirmation=True,
            pa_alignment=0.85,
        )
        assert t.risk_level == "high"
        assert t.requires_confirmation is True
        assert t.pa_alignment == 0.85


# ---------------------------------------------------------------------------
# ActionTierSpec
# ---------------------------------------------------------------------------

class TestActionTierSpec:
    def test_defaults_are_empty(self):
        spec = ActionTierSpec()
        assert spec.always_allowed == []
        assert spec.requires_confirmation == []
        assert spec.always_blocked == []

    def test_custom_tiers(self):
        spec = ActionTierSpec(
            always_allowed=["read"],
            requires_confirmation=["write"],
            always_blocked=["delete"],
        )
        assert "read" in spec.always_allowed
        assert "write" in spec.requires_confirmation
        assert "delete" in spec.always_blocked


# ---------------------------------------------------------------------------
# AgenticPA
# ---------------------------------------------------------------------------

class TestAgenticPA:
    def test_defaults(self):
        pa = AgenticPA(purpose_text="test purpose")
        assert pa.purpose_text == "test purpose"
        assert pa.scope_text == ""
        assert pa.purpose_embedding is None
        assert pa.scope_embedding is None
        assert pa.boundaries == []
        assert pa.tool_manifest == {}
        assert pa.max_chain_length == 20
        assert pa.max_tool_calls_per_step == 5
        assert pa.escalation_threshold == 0.50
        assert pa.require_human_above_risk == "high"

    def test_create_from_template_basic(self):
        """Factory creates PA with all embeddings computed."""
        pa = AgenticPA.create_from_template(
            purpose="Analyze SQL data",
            scope="Database queries",
            boundaries=["No data deletion"],
            tools=[],
            embed_fn=_deterministic_embed_fn,
        )
        assert pa.purpose_text == "Analyze SQL data"
        assert pa.scope_text == "Database queries"
        assert pa.purpose_embedding is not None
        assert pa.scope_embedding is not None
        assert len(pa.boundaries) == 1
        assert pa.boundaries[0].text == "No data deletion"
        assert pa.boundaries[0].embedding is not None
        assert pa.boundaries[0].severity == "hard"

    def test_create_from_template_purpose_centroid(self):
        """Purpose embedding is a centroid of purpose + scope + examples."""
        pa = AgenticPA.create_from_template(
            purpose="Analyze SQL data",
            scope="Database queries",
            boundaries=[],
            tools=[],
            embed_fn=_deterministic_embed_fn,
            example_requests=["Show revenue", "List tables", "Query users"],
        )
        # Purpose embedding should be L2 normalized
        norm = np.linalg.norm(pa.purpose_embedding)
        np.testing.assert_almost_equal(norm, 1.0, decimal=5)

        # Centroid should differ from single-text embedding
        single_emb = _deterministic_embed_fn("Analyze SQL data")
        assert not np.allclose(pa.purpose_embedding, single_emb, atol=1e-3)

    def test_create_from_template_boundary_dict(self):
        """Boundaries can be passed as dicts with text and severity."""
        pa = AgenticPA.create_from_template(
            purpose="Test",
            scope="Test scope",
            boundaries=[
                {"text": "no deletion", "severity": "hard"},
                {"text": "warn on large queries", "severity": "soft"},
            ],
            tools=[],
            embed_fn=_deterministic_embed_fn,
        )
        assert len(pa.boundaries) == 2
        assert pa.boundaries[0].severity == "hard"
        assert pa.boundaries[1].severity == "soft"

    def test_create_from_template_tool_manifest(self):
        """Tools are added to manifest with pre-computed PA alignment."""

        class MockTool:
            def __init__(self, name, description):
                self.name = name
                self.description = description

        tools = [
            MockTool("sql_query", "Execute SQL SELECT queries"),
            MockTool("list_tables", "List database tables"),
        ]
        pa = AgenticPA.create_from_template(
            purpose="Help with SQL queries",
            scope="Database operations",
            boundaries=[],
            tools=tools,
            embed_fn=_deterministic_embed_fn,
        )
        assert "sql_query" in pa.tool_manifest
        assert "list_tables" in pa.tool_manifest
        assert pa.tool_manifest["sql_query"].tool_name == "sql_query"
        assert pa.tool_manifest["sql_query"].description == "Execute SQL SELECT queries"
        # PA alignment should be a float between -1 and 1
        alignment = pa.tool_manifest["sql_query"].pa_alignment
        assert -1.0 <= alignment <= 1.0

    def test_create_from_template_empty_scope(self):
        """PA with empty scope gets None scope_embedding."""
        pa = AgenticPA.create_from_template(
            purpose="Test purpose",
            scope="",
            boundaries=[],
            tools=[],
            embed_fn=_deterministic_embed_fn,
        )
        assert pa.scope_embedding is None

    def test_create_from_template_limits_examples(self):
        """Factory uses at most 5 example requests for centroid."""
        examples = [f"Example request {i}" for i in range(10)]
        pa = AgenticPA.create_from_template(
            purpose="Test purpose",
            scope="Test scope",
            boundaries=[],
            tools=[],
            embed_fn=_deterministic_embed_fn,
            example_requests=examples,
        )
        # Should still create a valid PA (centroid from purpose + scope + 5 examples = 7 texts)
        assert pa.purpose_embedding is not None
        norm = np.linalg.norm(pa.purpose_embedding)
        np.testing.assert_almost_equal(norm, 1.0, decimal=5)

    def test_create_from_template_safe_centroid(self):
        """Safe centroid is built from safe_exemplars and assigned to all boundaries."""
        safe_exemplars = [
            "What is the roof condition score?",
            "Generate an underwriting property report",
            "Assess the risk profile for this property",
        ]
        pa = AgenticPA.create_from_template(
            purpose="Property risk assessment",
            scope="Insurance underwriting support",
            boundaries=["No binding decisions", "No PII access"],
            tools=[],
            embed_fn=_deterministic_embed_fn,
            safe_exemplars=safe_exemplars,
        )
        # All boundaries should have safe_centroid assigned
        assert len(pa.boundaries) == 2
        for b in pa.boundaries:
            assert b.safe_centroid is not None
            # Safe centroid should be L2 normalized
            norm = np.linalg.norm(b.safe_centroid)
            np.testing.assert_almost_equal(norm, 1.0, decimal=5)

        # All boundaries share the same safe centroid
        np.testing.assert_array_almost_equal(
            pa.boundaries[0].safe_centroid,
            pa.boundaries[1].safe_centroid,
        )

    def test_create_from_template_no_safe_exemplars(self):
        """Without safe_exemplars, boundaries have no safe_centroid (backward compat)."""
        pa = AgenticPA.create_from_template(
            purpose="Property risk assessment",
            scope="Insurance underwriting support",
            boundaries=["No binding decisions"],
            tools=[],
            embed_fn=_deterministic_embed_fn,
        )
        assert len(pa.boundaries) == 1
        assert pa.boundaries[0].safe_centroid is None

    def test_create_from_template_per_boundary_safe_centroid(self):
        """Per-boundary safe centroids from corpus give DIFFERENT centroids per boundary.

        Phase 2 fix: each boundary gets its own safe centroid from
        boundary_corpus_safe.py, not a shared centroid across all boundaries.
        """
        # Use template_id="property_intel" to load per-boundary corpus
        pa = AgenticPA.create_from_template(
            purpose="Property risk assessment",
            scope="Insurance underwriting support",
            boundaries=[
                "No binding underwriting decisions (decision support only, per NAIC Model Bulletin)",
                "No access to PII beyond property address and parcel data",
            ],
            tools=[],
            embed_fn=_deterministic_embed_fn,
            template_id="property_intel",
        )
        assert len(pa.boundaries) == 2
        for b in pa.boundaries:
            assert b.safe_centroid is not None
            norm = np.linalg.norm(b.safe_centroid)
            np.testing.assert_almost_equal(norm, 1.0, decimal=5)

        # Per-boundary centroids should be DIFFERENT (not shared)
        assert not np.allclose(
            pa.boundaries[0].safe_centroid,
            pa.boundaries[1].safe_centroid,
            atol=1e-3,
        )

    def test_scope_centroid_with_examples(self):
        """Scope embedding is a centroid when scope_example_requests provided."""
        scope_examples = [
            "Run pytest on the test suite",
            "Read the source files in src/",
            "Edit the configuration file",
        ]
        pa = AgenticPA.create_from_template(
            purpose="Analyze SQL data",
            scope="Database queries and testing",
            boundaries=[],
            tools=[],
            embed_fn=_deterministic_embed_fn,
            scope_example_requests=scope_examples,
        )
        # Scope embedding should exist and be different from single-text embedding
        assert pa.scope_embedding is not None
        single_emb = _deterministic_embed_fn("Database queries and testing")
        assert not np.allclose(pa.scope_embedding, single_emb, atol=1e-3)

    def test_scope_centroid_without_examples(self):
        """Scope embedding is a single embedding when no scope_example_requests."""
        pa = AgenticPA.create_from_template(
            purpose="Analyze SQL data",
            scope="Database queries",
            boundaries=[],
            tools=[],
            embed_fn=_deterministic_embed_fn,
        )
        # Should fall back to single embedding
        expected = _deterministic_embed_fn("Database queries")
        np.testing.assert_array_almost_equal(pa.scope_embedding, expected)

    def test_scope_centroid_l2_normalized(self):
        """Scope centroid is L2 normalized."""
        pa = AgenticPA.create_from_template(
            purpose="Test",
            scope="Testing scope",
            boundaries=[],
            tools=[],
            embed_fn=_deterministic_embed_fn,
            scope_example_requests=["Run tests", "Check coverage", "Lint code"],
        )
        norm = np.linalg.norm(pa.scope_embedding)
        np.testing.assert_almost_equal(norm, 1.0, decimal=5)

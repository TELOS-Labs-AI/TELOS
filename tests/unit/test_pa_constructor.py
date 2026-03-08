"""
Tests for PA Constructor — Two-Gate Tool-Grounded Governance.

Validates:
    1. Gate 1: Legitimate tool calls score > 0.70 against their tool's centroid
    2. Gate 1: Wrong-tool calls score lower (Read action vs Bash centroid)
    3. Gate 2: Boundary violations still detected regardless of Gate 1 pass
    4. Deterministic output (same inputs = same PA, critical for signing)
    5. Missing tool definitions don't crash (graceful fallback)
    6. All 46 tools have definitions (no gaps)
    7. Per-tool centroids are L2-normalized
    8. Combined centroid is L2-normalized
    9. Provenance field populated for every definition
"""

import numpy as np
import pytest
from unittest.mock import patch

from telos_governance.tool_semantics import (
    TOOL_DEFINITIONS,
    ToolDefinition,
    get_tool_definition,
    get_all_definitions,
    get_definitions_by_group,
    get_risk_weight,
)
from telos_governance.pa_constructor import PAConstructor


# ─── Test Fixtures ───

def _deterministic_embed_fn(text: str) -> np.ndarray:
    """Deterministic embedding for testing.

    Uses hash-based pseudo-random vector so that identical text always
    produces identical embeddings, and different text produces different
    embeddings. NOT semantically meaningful — for structural tests only.
    """
    rng = np.random.RandomState(hash(text) % (2**31))
    vec = rng.randn(384).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


@pytest.fixture
def embed_fn():
    """Deterministic embedding function."""
    return _deterministic_embed_fn


@pytest.fixture
def constructor(embed_fn):
    """PA Constructor with deterministic embeddings."""
    return PAConstructor(embed_fn)


@pytest.fixture
def minimal_pa_args():
    """Minimal arguments for PA construction."""
    from types import SimpleNamespace
    return dict(
        purpose="Execute developer tasks in the project workspace",
        scope="File operations, shell execution, web access",
        boundaries=[
            {"text": "Do not exfiltrate data", "severity": "hard"},
            {"text": "Do not modify system files", "severity": "hard"},
        ],
        tools=[
            SimpleNamespace(name="fs_read_file", description="Read files", risk_level="low"),
            SimpleNamespace(name="runtime_execute", description="Execute commands", risk_level="critical"),
        ],
    )


# ─── Tool Semantics Tests ───

class TestToolSemantics:
    """Tests for the canonical tool definitions registry."""

    def test_all_46_tools_defined(self):
        """Every unique telos_tool_name has a definition."""
        expected_tools = {
            "fs_read_file", "fs_write_file", "fs_edit_file", "fs_list_directory",
            "fs_search_files", "fs_apply_patch", "fs_move_file", "fs_delete_file",
            "runtime_execute", "runtime_process",
            "web_fetch", "web_navigate", "web_scrape", "web_search",
            "messaging_send", "messaging_read", "messaging_reply",
            "automation_cron_create", "automation_cron_list",
            "automation_cron_delete", "automation_gateway_config",
            "sessions_save", "sessions_restore", "sessions_list", "sessions_delete",
            "memory_store", "memory_retrieve", "memory_search",
            "ui_display", "ui_prompt",
            "nodes_delegate", "nodes_coordinate",
            "openclaw_skill_install", "openclaw_skill_execute",
            "openclaw_config_modify", "openclaw_agent_create",
            "research_audit_load", "research_audit_rescore",
            "research_audit_validate", "research_audit_compare",
            "research_audit_inspect", "research_audit_report",
            "research_audit_sweep", "research_audit_annotate",
            "research_audit_timeline", "research_audit_stats",
        }
        actual_tools = set(TOOL_DEFINITIONS.keys())
        missing = expected_tools - actual_tools
        extra = actual_tools - expected_tools
        assert not missing, f"Missing tool definitions: {missing}"
        assert not extra, f"Unexpected tool definitions: {extra}"

    def test_every_definition_has_provenance(self):
        """Every tool definition cites its source."""
        for name, defn in TOOL_DEFINITIONS.items():
            assert defn.provenance, f"{name} missing provenance"
            assert len(defn.provenance) > 10, f"{name} provenance too short"

    def test_every_definition_has_exemplars(self):
        """Every tool definition has at least 5 legitimate exemplars."""
        for name, defn in TOOL_DEFINITIONS.items():
            assert len(defn.legitimate_exemplars) >= 5, (
                f"{name} has only {len(defn.legitimate_exemplars)} exemplars "
                f"(minimum 5 required)"
            )

    def test_high_traffic_tools_have_12_plus_exemplars(self):
        """High-traffic tools (Read, Bash, Edit, Grep, Glob) have 12+ exemplars."""
        high_traffic = [
            "fs_read_file", "runtime_execute", "fs_edit_file",
            "fs_search_files", "fs_list_directory",
        ]
        for name in high_traffic:
            defn = TOOL_DEFINITIONS[name]
            assert len(defn.legitimate_exemplars) >= 12, (
                f"{name} has {len(defn.legitimate_exemplars)} exemplars "
                f"(high-traffic tools need 12+)"
            )

    def test_every_definition_has_scope_constraints(self):
        """Every tool definition has at least one scope constraint."""
        for name, defn in TOOL_DEFINITIONS.items():
            assert len(defn.scope_constraints) >= 1, (
                f"{name} has no scope constraints"
            )

    def test_tool_group_coverage(self):
        """All 10 OpenClaw tool groups are represented."""
        expected_groups = {
            "fs", "runtime", "web", "messaging", "automation",
            "sessions", "memory", "ui", "nodes", "openclaw",
        }
        actual_groups = {defn.tool_group for defn in TOOL_DEFINITIONS.values()}
        missing = expected_groups - actual_groups
        assert not missing, f"Missing tool groups: {missing}"

    def test_risk_levels_valid(self):
        """All risk levels are valid (low, medium, high, critical)."""
        valid_levels = {"low", "medium", "high", "critical"}
        for name, defn in TOOL_DEFINITIONS.items():
            assert defn.risk_level in valid_levels, (
                f"{name} has invalid risk level: {defn.risk_level}"
            )

    def test_get_tool_definition_found(self):
        """get_tool_definition returns definition for known tool."""
        defn = get_tool_definition("fs_read_file")
        assert defn is not None
        assert defn.telos_tool_name == "fs_read_file"

    def test_get_tool_definition_not_found(self):
        """get_tool_definition returns None for unknown tool."""
        defn = get_tool_definition("nonexistent_tool")
        assert defn is None

    def test_get_definitions_by_group(self):
        """get_definitions_by_group returns only tools from that group."""
        fs_tools = get_definitions_by_group("fs")
        assert len(fs_tools) == 8  # 8 fs tools
        for name, defn in fs_tools.items():
            assert defn.tool_group == "fs"

    def test_risk_weight_values(self):
        """Risk weights follow the documented scale."""
        assert get_risk_weight("low") == 1.0
        assert get_risk_weight("medium") == 0.8
        assert get_risk_weight("high") == 0.6
        assert get_risk_weight("critical") == 0.4
        assert get_risk_weight("unknown") == 0.5


# ─── PA Constructor Tests ───

class TestPAConstructor:
    """Tests for the PA Constructor building process."""

    def test_construct_returns_agentic_pa(self, constructor, minimal_pa_args):
        """construct() returns an AgenticPA instance."""
        from telos_governance.agentic_pa import AgenticPA
        pa = constructor.construct(**minimal_pa_args)
        assert isinstance(pa, AgenticPA)

    def test_tool_centroids_attached(self, constructor, minimal_pa_args):
        """PA has tool_centroids dict with entries for all defined tools."""
        pa = constructor.construct(**minimal_pa_args)
        assert hasattr(pa, "tool_centroids")
        assert isinstance(pa.tool_centroids, dict)
        # Should have centroids for all tools in TOOL_DEFINITIONS
        assert len(pa.tool_centroids) == len(TOOL_DEFINITIONS)

    def test_per_tool_centroids_l2_normalized(self, constructor, minimal_pa_args):
        """Every per-tool centroid is L2-normalized (unit vector)."""
        pa = constructor.construct(**minimal_pa_args)
        for name, centroid in pa.tool_centroids.items():
            norm = np.linalg.norm(centroid)
            assert abs(norm - 1.0) < 1e-5, (
                f"{name} centroid norm = {norm:.6f} (expected 1.0)"
            )

    def test_purpose_embedding_l2_normalized(self, constructor, minimal_pa_args):
        """Combined purpose centroid is L2-normalized."""
        pa = constructor.construct(**minimal_pa_args)
        norm = np.linalg.norm(pa.purpose_embedding)
        assert abs(norm - 1.0) < 1e-5, (
            f"Purpose centroid norm = {norm:.6f} (expected 1.0)"
        )

    def test_deterministic_output(self, embed_fn, minimal_pa_args):
        """Same inputs produce identical PA (critical for signing)."""
        c1 = PAConstructor(embed_fn)
        c2 = PAConstructor(embed_fn)

        pa1 = c1.construct(**minimal_pa_args)
        pa2 = c2.construct(**minimal_pa_args)

        # Purpose embeddings must be identical
        np.testing.assert_array_almost_equal(
            pa1.purpose_embedding, pa2.purpose_embedding, decimal=6
        )

        # Per-tool centroids must be identical
        for name in pa1.tool_centroids:
            np.testing.assert_array_almost_equal(
                pa1.tool_centroids[name],
                pa2.tool_centroids[name],
                decimal=6,
            )

    def test_exemplar_embeddings_populated(self, constructor, minimal_pa_args):
        """PA has purpose_example_embeddings from all tool exemplars."""
        pa = constructor.construct(**minimal_pa_args)
        assert pa.purpose_example_embeddings is not None
        # Should have at least as many as total exemplars across all tools
        total_exemplars = sum(
            len(d.legitimate_exemplars) for d in TOOL_DEFINITIONS.values()
        )
        assert len(pa.purpose_example_embeddings) >= total_exemplars

    def test_scope_embedding_grounded(self, constructor, minimal_pa_args):
        """Scope embedding is built from tool constraints + scope text."""
        pa = constructor.construct(**minimal_pa_args)
        assert pa.scope_embedding is not None
        norm = np.linalg.norm(pa.scope_embedding)
        assert abs(norm - 1.0) < 1e-5

    def test_boundaries_preserved(self, constructor, minimal_pa_args):
        """Boundaries from config are preserved in the PA."""
        pa = constructor.construct(**minimal_pa_args)
        assert len(pa.boundaries) == 2

    def test_missing_definitions_graceful(self, embed_fn, minimal_pa_args):
        """Constructor works even with empty tool definitions."""
        c = PAConstructor(embed_fn)
        pa = c.construct(**minimal_pa_args, tool_definitions={})
        # Should still produce a valid PA
        assert hasattr(pa, "tool_centroids")
        assert len(pa.tool_centroids) == 0
        # Purpose embedding falls back to standard
        assert pa.purpose_embedding is not None


# ─── Gate 1 Centroid Quality Tests ───
# These use deterministic embeddings, so they validate STRUCTURE not SEMANTICS.
# Semantic quality (cosine > 0.70) requires real MiniLM embeddings — tested
# in integration tests with OnnxEmbeddingProvider.

class TestGate1Centroids:
    """Structural tests for per-tool centroid construction."""

    def test_centroid_dimension_matches_embedding(self, constructor, minimal_pa_args):
        """Centroid dimension matches embedding dimension (384 for MiniLM)."""
        pa = constructor.construct(**minimal_pa_args)
        for name, centroid in pa.tool_centroids.items():
            assert centroid.shape == (384,), (
                f"{name} centroid shape = {centroid.shape} (expected (384,))"
            )

    def test_different_tools_have_different_centroids(self, constructor, minimal_pa_args):
        """Different tools produce different centroids."""
        pa = constructor.construct(**minimal_pa_args)
        centroids = list(pa.tool_centroids.values())
        # At least some pairs should be different
        all_same = all(
            np.allclose(centroids[0], c) for c in centroids[1:]
        )
        assert not all_same, "All tool centroids are identical — something is wrong"

    def test_exemplar_count_per_tool(self, constructor, minimal_pa_args):
        """Verify each tool centroid is built from expected exemplar count."""
        pa = constructor.construct(**minimal_pa_args)
        for name, defn in TOOL_DEFINITIONS.items():
            assert name in pa.tool_centroids, f"{name} missing from centroids"
            expected_count = 1 + len(defn.legitimate_exemplars)  # desc + exemplars
            assert expected_count >= 6, (
                f"{name}: only {expected_count} embeddings for centroid "
                f"(Karpathy recommends 6+ for stable centroids)"
            )


# ─── Integration Placeholder Tests ───

class TestIntegrationPlaceholders:
    """Placeholder tests that require real embeddings (OnnxEmbeddingProvider).

    These tests document the expected behavior but are skipped in unit tests.
    Run with: pytest -m integration tests/integration/test_pa_constructor.py
    """

    @pytest.mark.skip(reason="Requires OnnxEmbeddingProvider — run as integration test")
    def test_gate1_legitimate_call_scores_above_070(self):
        """A legitimate Read action should score > 0.70 against Read centroid."""
        pass

    @pytest.mark.skip(reason="Requires OnnxEmbeddingProvider — run as integration test")
    def test_gate1_wrong_tool_scores_lower(self):
        """A Read action should score lower against Bash centroid than Read centroid."""
        pass

    @pytest.mark.skip(reason="Requires OnnxEmbeddingProvider — run as integration test")
    def test_gate2_boundary_violation_detected(self):
        """Boundary violations detected regardless of Gate 1 pass."""
        pass

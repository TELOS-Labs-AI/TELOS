"""
Tests for telos_governance.tool_selection_gate
===============================================

Tests semantic tool ranking, score normalization,
display percentages, and reasoning generation.
"""

import numpy as np
import pytest

from telos_governance.tool_selection_gate import (
    ToolDefinition,
    ToolFidelityScore,
    ToolSelectionGate,
    ToolSelectionResult,
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


def _make_deterministic_embed_fn(tool_embeddings: dict):
    """
    Create an embed_fn that returns specific embeddings for known texts.
    Falls back to a hash-based deterministic embedding for unknown texts.
    """
    def embed_fn(text: str) -> np.ndarray:
        for key, emb in tool_embeddings.items():
            if key in text:
                return emb
        # Deterministic fallback
        rng = np.random.RandomState(hash(text) % (2**31))
        v = rng.randn(8)
        return v / np.linalg.norm(v)
    return embed_fn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_embedding():
    return _make_embedding([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])


@pytest.fixture
def tools():
    """A set of test tools."""
    return [
        ToolDefinition(name="sql_query", description="Execute SQL queries against database"),
        ToolDefinition(name="web_search", description="Search the web for information"),
        ToolDefinition(name="calculator", description="Perform mathematical calculations"),
    ]


# ---------------------------------------------------------------------------
# Tests: Tool selection
# ---------------------------------------------------------------------------

class TestToolSelection:
    """Test basic tool selection mechanics."""

    def test_selects_highest_fidelity_tool(self):
        """The tool with highest semantic similarity should be selected."""
        # sql_query embedding is closest to the request embedding
        request_emb = _make_embedding([1.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        sql_emb = _make_embedding([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        web_emb = _make_embedding([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        calc_emb = _make_embedding([0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])

        embeddings = {
            "sql_query": sql_emb,
            "web_search": web_emb,
            "calculator": calc_emb,
        }

        call_count = [0]
        def embed_fn(text: str) -> np.ndarray:
            call_count[0] += 1
            if call_count[0] == 1:
                return request_emb  # First call = user request
            for key, emb in embeddings.items():
                if key in text:
                    return emb
            return request_emb

        gate = ToolSelectionGate(embed_fn=embed_fn)
        tools = [
            ToolDefinition(name="sql_query", description="Execute SQL queries"),
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="calculator", description="Math calculations"),
        ]
        result = gate.select_tool("run a database query", tools)

        assert result.selected_tool == "sql_query"
        assert result.tool_scores[0].rank == 1
        assert result.tool_scores[0].tool_name == "sql_query"

    def test_empty_tools_returns_no_selection(self):
        """No tools should return empty result."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        result = gate.select_tool("test request", [])

        assert result.selected_tool is None
        assert result.selected_fidelity == 0.0
        assert result.selection_reasoning == "No tools available"
        assert result.all_tools_ranked == []

    def test_all_tools_ranked(self):
        """All tools should appear in the ranking."""
        request_emb = _make_embedding([1.0, 0.5, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0])

        call_count = [0]
        def embed_fn(text: str) -> np.ndarray:
            call_count[0] += 1
            if call_count[0] == 1:
                return request_emb
            rng = np.random.RandomState(hash(text) % (2**31))
            v = rng.randn(8)
            return v / np.linalg.norm(v)

        gate = ToolSelectionGate(embed_fn=embed_fn)
        tools = [
            ToolDefinition(name="tool_a", description="First tool"),
            ToolDefinition(name="tool_b", description="Second tool"),
            ToolDefinition(name="tool_c", description="Third tool"),
        ]
        result = gate.select_tool("test", tools)

        assert len(result.all_tools_ranked) == 3
        assert len(result.tool_scores) == 3
        ranks = [s.rank for s in result.tool_scores]
        assert sorted(ranks) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Tests: Score normalization
# ---------------------------------------------------------------------------

class TestScoreNormalization:
    """Test fidelity normalization for tool scores."""

    def test_normalize_high_similarity(self):
        """Raw similarity > 0.70 should normalize to fidelity >= 0.70."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        fidelity = gate._normalize_fidelity(0.80)
        assert fidelity >= 0.70

    def test_normalize_low_similarity(self):
        """Raw similarity < 0.55 should normalize to fidelity < 0.30."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        fidelity = gate._normalize_fidelity(0.40)
        assert fidelity < 0.30

    def test_normalize_mid_similarity(self):
        """Raw similarity 0.55-0.70 should normalize to 0.30-0.70."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        fidelity = gate._normalize_fidelity(0.62)
        assert 0.30 <= fidelity <= 0.70

    def test_normalize_zero(self):
        """Zero similarity should give zero fidelity."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        fidelity = gate._normalize_fidelity(0.0)
        assert fidelity == 0.0

    def test_normalize_one(self):
        """Perfect similarity should give fidelity = 1.0."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        fidelity = gate._normalize_fidelity(1.0)
        assert fidelity == 1.0

    def test_fidelity_bounded(self):
        """Normalized fidelity should always be in [0, 1]."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        for raw in [0.0, 0.1, 0.3, 0.55, 0.65, 0.7, 0.85, 1.0]:
            fidelity = gate._normalize_fidelity(raw)
            assert 0.0 <= fidelity <= 1.0


# ---------------------------------------------------------------------------
# Tests: Display percentage
# ---------------------------------------------------------------------------

class TestDisplayPercentage:
    """Test conversion from fidelity to display percentage."""

    def test_high_fidelity_display(self):
        """Fidelity >= 0.70 should display as 90-100%."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        pct = gate._to_display_percentage(0.85)
        assert 90 <= pct <= 100

    def test_medium_fidelity_display(self):
        """Fidelity 0.60-0.69 should display as 80-89%."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        pct = gate._to_display_percentage(0.65)
        assert 80 <= pct <= 89

    def test_low_fidelity_display(self):
        """Fidelity 0.50-0.59 should display as 70-79%."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        pct = gate._to_display_percentage(0.55)
        assert 70 <= pct <= 79

    def test_very_low_fidelity_display(self):
        """Fidelity < 0.50 should display below 70%."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        pct = gate._to_display_percentage(0.30)
        assert pct < 70


# ---------------------------------------------------------------------------
# Tests: Tool registration and caching
# ---------------------------------------------------------------------------

class TestToolRegistration:
    """Test tool embedding caching."""

    def test_register_tools_caches_embeddings(self):
        """register_tools should pre-compute and cache embeddings."""
        embed_calls = []

        def counting_embed_fn(text: str) -> np.ndarray:
            embed_calls.append(text)
            return _make_embedding([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

        gate = ToolSelectionGate(embed_fn=counting_embed_fn)
        tools = [
            ToolDefinition(name="tool_a", description="First tool"),
            ToolDefinition(name="tool_b", description="Second tool"),
        ]
        gate.register_tools(tools)

        assert len(embed_calls) == 2
        assert "tool_a" in gate._tool_embedding_cache
        assert "tool_b" in gate._tool_embedding_cache

    def test_register_tools_no_duplicate_caching(self):
        """Registering the same tools twice should not re-compute."""
        embed_calls = []

        def counting_embed_fn(text: str) -> np.ndarray:
            embed_calls.append(text)
            return _make_embedding([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

        gate = ToolSelectionGate(embed_fn=counting_embed_fn)
        tools = [ToolDefinition(name="tool_a", description="First tool")]
        gate.register_tools(tools)
        gate.register_tools(tools)

        assert len(embed_calls) == 1  # Only computed once


# ---------------------------------------------------------------------------
# Tests: Reasoning generation
# ---------------------------------------------------------------------------

class TestReasoning:
    """Test human-readable reasoning generation."""

    def test_high_confidence_reasoning(self):
        """High display percentage should produce confident reasoning."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        score = ToolFidelityScore(
            tool_name="good_tool",
            tool_description="A well-matched tool for the task",
            raw_similarity=0.85,
            normalized_fidelity=0.90,
            display_percentage=95,
            rank=1,
        )
        reasoning = gate._generate_reasoning(score, [score])
        assert "95%" in reasoning
        assert "good_tool" in reasoning

    def test_low_confidence_warning(self):
        """Very low display percentage should produce warning."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        score = ToolFidelityScore(
            tool_name="bad_tool",
            tool_description="Poorly matched tool",
            raw_similarity=0.30,
            normalized_fidelity=0.20,
            display_percentage=30,
            rank=1,
        )
        reasoning = gate._generate_reasoning(score, [score])
        assert "Warning" in reasoning

    def test_no_tools_reasoning(self):
        """No tools should produce appropriate message."""
        gate = ToolSelectionGate(embed_fn=lambda t: np.zeros(8))
        reasoning = gate._generate_reasoning(None, [])
        assert "No tools available" in reasoning


# ---------------------------------------------------------------------------
# Tests: ToolSelectionResult serialization
# ---------------------------------------------------------------------------

class TestResultSerialization:
    """Test ToolSelectionResult.to_dict()."""

    def test_to_dict_structure(self):
        """to_dict should produce expected structure."""
        result = ToolSelectionResult(
            user_request="test query",
            tool_scores=[
                ToolFidelityScore(
                    tool_name="tool_a",
                    tool_description="description",
                    raw_similarity=0.80,
                    normalized_fidelity=0.75,
                    display_percentage=92,
                    rank=1,
                ),
            ],
            selected_tool="tool_a",
            selected_fidelity=0.75,
            selection_reasoning="Good match",
            all_tools_ranked=["tool_a"],
        )
        d = result.to_dict()

        assert d["tier"] == 2
        assert d["type"] == "tool_selection"
        assert d["selected_tool"] == "tool_a"
        assert len(d["tool_rankings"]) == 1
        assert d["tool_rankings"][0]["rank"] == 1

    def test_to_dict_truncates_long_request(self):
        """Long user requests should be truncated in to_dict output."""
        long_request = "x" * 200
        result = ToolSelectionResult(
            user_request=long_request,
            tool_scores=[],
            selected_tool=None,
            selected_fidelity=0.0,
            selection_reasoning="None",
            all_tools_ranked=[],
        )
        d = result.to_dict()

        assert len(d["user_request"]) == 103  # 100 + "..."


# ---------------------------------------------------------------------------
# Tests: ToolFidelityScore properties
# ---------------------------------------------------------------------------

class TestToolFidelityScore:
    """Test ToolFidelityScore dataclass."""

    def test_is_best_match_rank_1(self):
        score = ToolFidelityScore(
            tool_name="t", tool_description="d",
            raw_similarity=0.8, normalized_fidelity=0.7,
            display_percentage=90, rank=1,
        )
        assert score.is_best_match is True

    def test_is_not_best_match_rank_2(self):
        score = ToolFidelityScore(
            tool_name="t", tool_description="d",
            raw_similarity=0.6, normalized_fidelity=0.5,
            display_percentage=70, rank=2,
        )
        assert score.is_best_match is False

"""
Tests for telos_observatory.agentic.agentic_response_manager
==============================================================

Tests for AgenticResponseManager: process_request, LLM fallback,
system prompt building, response fidelity checking, and helpers.

Mocks the embedding provider, fidelity engine, and LLM client to
isolate response manager logic.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import asdict

from telos_governance.response_manager import (
    AgenticResponseManager,
    AgenticTurnResult,
    _TOKEN_BUDGETS,
)
from telos_governance.agent_templates import AgenticTemplate
from telos_governance.agentic_fidelity import AgenticFidelityResult
from telos_governance.types import ActionDecision, DirectionLevel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_template(template_id="sql_analyst") -> AgenticTemplate:
    """Create a minimal AgenticTemplate for testing."""
    return AgenticTemplate(
        id=template_id,
        name="SQL Database Analyst",
        description="Queries data",
        icon="database",
        purpose="Help users query and understand data in PostgreSQL databases",
        scope="SELECT queries, schema exploration, data analysis",
        boundaries=[
            "No data modification (INSERT, UPDATE, DELETE operations)",
            "No administrative operations (GRANT, DROP, CREATE, ALTER)",
        ],
        tools=["sql_db_query", "sql_db_schema"],
        tool_set_key="sql_agent",
        example_requests=["Show me total revenue", "List all tables"],
        drift_examples=["Delete all records", "What's the weather?"],
        system_prompt="You are a SQL Database Analyst agent governed by TELOS.",
    )


def _make_engine_result(
    decision: ActionDecision = ActionDecision.EXECUTE,
    effective_fidelity: float = 0.90,
    purpose_fidelity: float = 0.90,
    scope_fidelity: float = 0.85,
    tool_fidelity: float = 0.92,
    chain_continuity: float = 0.50,
    boundary_violation: float = 0.0,
    boundary_triggered: bool = False,
    chain_broken: bool = False,
    tool_blocked: bool = False,
    selected_tool: str = "sql_db_query",
    tool_rankings: list = None,
) -> AgenticFidelityResult:
    """Create a mock AgenticFidelityResult."""
    if tool_rankings is None:
        tool_rankings = [
            {"rank": 1, "tool": "sql_db_query", "fidelity": 0.92},
            {"rank": 2, "tool": "sql_db_schema", "fidelity": 0.65},
        ]
    result = AgenticFidelityResult(
        purpose_fidelity=purpose_fidelity,
        scope_fidelity=scope_fidelity,
        boundary_violation=boundary_violation,
        tool_fidelity=tool_fidelity,
        chain_continuity=chain_continuity,
        composite_fidelity=effective_fidelity,
        effective_fidelity=effective_fidelity,
        decision=decision,
        direction_level=DirectionLevel.NONE,
        boundary_triggered=boundary_triggered,
        tool_blocked=tool_blocked,
        chain_broken=chain_broken,
        selected_tool=selected_tool,
        tool_rankings=tool_rankings,
    )
    result.dimension_explanations = {
        "purpose": f"Purpose alignment: {purpose_fidelity:.2f}",
        "scope": f"Scope alignment: {scope_fidelity:.2f}",
        "tool": f"Tool fidelity: {tool_fidelity:.2f} (selected: {selected_tool})",
        "chain": f"Chain continuity: {chain_continuity:.2f} (step 1)",
        "boundary": "No boundary violation (max similarity: 0.10)",
    }
    return result


def _make_manager_with_mock_engine(engine_result):
    """Create an AgenticResponseManager with mocked internals."""
    manager = AgenticResponseManager()
    manager._initialized = True
    manager._embed_fn = lambda t: np.ones(3) / np.sqrt(3)
    manager._llm_client = None
    manager._llm_client_checked = True

    # Mock the engine
    mock_engine = MagicMock()
    mock_engine.score_action.return_value = engine_result
    mock_engine.reset_chain = MagicMock()

    # Cache the mock engine for the template
    manager._engine_cache["sql_analyst"] = mock_engine
    return manager


# ---------------------------------------------------------------------------
# AgenticTurnResult
# ---------------------------------------------------------------------------

class TestAgenticTurnResult:
    def test_defaults(self):
        r = AgenticTurnResult()
        assert r.purpose_fidelity == 0.0
        assert r.scope_fidelity == 0.0
        assert r.tool_fidelity == 0.0
        assert r.selected_tool is None
        assert r.tool_rankings == []
        assert r.chain_sci == 0.0
        assert r.chain_length == 0
        assert r.chain_broken is False
        assert r.effective_fidelity == 0.0
        assert r.boundary_triggered is False
        assert r.boundary_name is None
        assert r.boundary_fidelity == 0.0
        assert r.decision == "EXECUTE"
        assert r.decision_explanation == ""
        assert r.tool_output == ""
        assert r.response_text == ""
        assert r.step_number == 0


# ---------------------------------------------------------------------------
# Token Budgets
# ---------------------------------------------------------------------------

class TestTokenBudgets:
    def test_all_tiers_have_budgets(self):
        for tier in ("EXECUTE", "CLARIFY", "ESCALATE"):
            assert tier in _TOKEN_BUDGETS
            assert _TOKEN_BUDGETS[tier] > 0

    def test_execute_has_highest_budget(self):
        assert _TOKEN_BUDGETS["EXECUTE"] > _TOKEN_BUDGETS["CLARIFY"]

    def test_get_token_budget_method(self):
        manager = AgenticResponseManager()
        assert manager._get_token_budget("EXECUTE") == 600
        assert manager._get_token_budget("CLARIFY") == 400
        assert manager._get_token_budget("UNKNOWN") == 400  # default


# ---------------------------------------------------------------------------
# process_request — EXECUTE
# ---------------------------------------------------------------------------

class TestProcessRequestExecute:
    def test_execute_with_tool(self):
        """EXECUTE decision runs mock tool and generates response."""
        engine_result = _make_engine_result(
            decision=ActionDecision.EXECUTE,
            effective_fidelity=0.90,
            selected_tool="sql_db_query",
        )
        manager = _make_manager_with_mock_engine(engine_result)
        template = _make_template()

        result = manager.process_request("Show me total revenue", template, 1)

        assert result.decision == "EXECUTE"
        assert result.effective_fidelity == 0.90
        assert result.selected_tool == "sql_db_query"
        assert result.tool_output != ""  # MockToolExecutor ran
        assert result.response_text != ""
        assert result.purpose_fidelity == 0.90
        assert result.scope_fidelity == 0.85

    def test_execute_no_tool_selected(self):
        """EXECUTE with no selected tool -> informational response."""
        engine_result = _make_engine_result(
            decision=ActionDecision.EXECUTE,
            selected_tool=None,
        )
        manager = _make_manager_with_mock_engine(engine_result)
        template = _make_template()

        result = manager.process_request("Tell me about data", template, 1)
        assert result.decision == "EXECUTE"
        assert "no specific tool" in result.response_text.lower() or "available tools" in result.response_text.lower()


# ---------------------------------------------------------------------------
# process_request — CLARIFY
# ---------------------------------------------------------------------------

class TestProcessRequestClarify:
    def test_clarify_response(self):
        engine_result = _make_engine_result(
            decision=ActionDecision.CLARIFY,
            effective_fidelity=0.75,
        )
        manager = _make_manager_with_mock_engine(engine_result)
        template = _make_template()

        result = manager.process_request("Something about data", template, 1)
        assert result.decision == "CLARIFY"
        assert "clarify" in result.response_text.lower() or "access to" in result.response_text.lower()


# ---------------------------------------------------------------------------
# process_request — ESCALATE
# ---------------------------------------------------------------------------

class TestProcessRequestEscalate:
    def test_escalate_blocks_tools(self):
        engine_result = _make_engine_result(
            decision=ActionDecision.ESCALATE,
            effective_fidelity=0.10,
            boundary_triggered=True,
        )
        manager = _make_manager_with_mock_engine(engine_result)
        template = _make_template()

        result = manager.process_request("DELETE FROM users", template, 1)
        assert result.decision == "ESCALATE"
        assert result.selected_tool is None
        assert result.tool_output == ""
        assert "cannot proceed" in result.response_text.lower()
        # All tools should be blocked in rankings
        for t in result.tool_rankings:
            assert t["is_blocked"] is True


# ---------------------------------------------------------------------------
# process_request — ESCALATE (low fidelity)
# ---------------------------------------------------------------------------

class TestProcessRequestEscalateLowFidelity:
    def test_escalate_low_fidelity_response(self):
        engine_result = _make_engine_result(
            decision=ActionDecision.ESCALATE,
            effective_fidelity=0.30,
        )
        manager = _make_manager_with_mock_engine(engine_result)
        template = _make_template()

        result = manager.process_request("What's the weather?", template, 1)
        assert result.decision == "ESCALATE"
        assert "outside" in result.response_text.lower() or "scope" in result.response_text.lower() or "boundar" in result.response_text.lower() or "escalat" in result.response_text.lower()


# ---------------------------------------------------------------------------
# LLM Fallback
# ---------------------------------------------------------------------------

class TestLLMFallback:
    def test_no_llm_client_uses_template(self):
        """When LLM client is None, template strings are used."""
        engine_result = _make_engine_result(
            decision=ActionDecision.EXECUTE,
            selected_tool="sql_db_query",
        )
        manager = _make_manager_with_mock_engine(engine_result)
        # LLM client explicitly None
        manager._llm_client = None
        manager._llm_client_checked = True
        template = _make_template()

        result = manager.process_request("Show revenue", template, 1)
        # Should still get a response (template string, not LLM)
        assert result.response_text != ""
        assert result.decision == "EXECUTE"


# ---------------------------------------------------------------------------
# _build_agentic_system_prompt
# ---------------------------------------------------------------------------

class TestBuildAgenticSystemPrompt:
    def setup_method(self):
        self.manager = AgenticResponseManager()
        self.template = _make_template()

    def test_execute_prompt(self):
        prompt = self.manager._build_agentic_system_prompt(
            self.template, "EXECUTE", tool_output="10 rows returned"
        )
        assert "EXECUTE" in prompt
        assert "10 rows returned" in prompt
        assert "AGENT IDENTITY" in prompt
        assert "OPERATIONAL BOUNDARIES" in prompt
        assert "RESPONSE GUIDELINES" in prompt

    def test_clarify_prompt(self):
        prompt = self.manager._build_agentic_system_prompt(
            self.template, "CLARIFY"
        )
        assert "CLARIFY" in prompt
        assert "clarification" in prompt.lower() or "clarify" in prompt.lower()

    def test_escalate_prompt(self):
        prompt = self.manager._build_agentic_system_prompt(
            self.template, "ESCALATE"
        )
        assert "ESCALATE" in prompt
        assert "boundaries" in prompt.lower() or "boundary" in prompt.lower() or "scope" in prompt.lower()

    def test_prompt_includes_template_identity(self):
        prompt = self.manager._build_agentic_system_prompt(
            self.template, "EXECUTE"
        )
        assert self.template.purpose in prompt
        assert "sql_db_query" in prompt
        assert "No data modification" in prompt

    def test_prompt_includes_no_governance_leakage(self):
        """Prompt instructs LLM not to expose governance internals."""
        prompt = self.manager._build_agentic_system_prompt(
            self.template, "EXECUTE"
        )
        assert "fidelity scores" in prompt.lower() or "fidelity" in prompt.lower()
        assert "Do NOT mention" in prompt


# ---------------------------------------------------------------------------
# _check_response_fidelity
# ---------------------------------------------------------------------------

class TestCheckResponseFidelity:
    def setup_method(self):
        self.manager = AgenticResponseManager()
        self.manager._embed_fn = lambda t: np.array([1.0, 0.0, 0.0])
        self.template = _make_template()

    def test_escalate_always_passes(self):
        assert self.manager._check_response_fidelity(
            "I cannot help", self.template, "ESCALATE"
        ) is True

    def test_escalate_always_passes(self):
        assert self.manager._check_response_fidelity(
            "Outside my scope", self.template, "ESCALATE"
        ) is True

    def test_identical_embedding_passes(self):
        """Response with identical embedding to purpose -> passes."""
        self.manager._embed_fn = lambda t: np.array([1.0, 0.0, 0.0])
        assert self.manager._check_response_fidelity(
            "Here's the query result", self.template, "EXECUTE"
        ) is True

    def test_no_embed_fn_passes(self):
        """If embed_fn is None, always passes (fail-open)."""
        self.manager._embed_fn = None
        assert self.manager._check_response_fidelity(
            "anything", self.template, "EXECUTE"
        ) is True

    def test_embed_fn_exception_passes(self):
        """If embed_fn throws, always passes (fail-open)."""
        self.manager._embed_fn = lambda t: (_ for _ in ()).throw(RuntimeError("boom"))
        assert self.manager._check_response_fidelity(
            "anything", self.template, "EXECUTE"
        ) is True


# ---------------------------------------------------------------------------
# _build_conversation_history
# ---------------------------------------------------------------------------

class TestBuildConversationHistory:
    def test_step_1_returns_empty(self):
        """First step has no prior history."""
        manager = AgenticResponseManager()
        history = manager._build_conversation_history(1)
        assert history == []

    def test_builds_history_from_session_state(self):
        """Builds history from prior step data in session state."""
        import sys
        mock_st = MagicMock()
        mock_st.session_state = {
            "agentic_step_1_data": {
                "user_request": "Show me revenue",
                "response_text": "Here are the results...",
            },
            "agentic_step_2_data": {
                "user_request": "Break it down by quarter",
                "response_text": "Q1: $1M, Q2: $1.2M...",
            },
        }
        with patch.dict(sys.modules, {"streamlit": mock_st}):
            manager = AgenticResponseManager()
            history = manager._build_conversation_history(3)
            assert len(history) == 4  # 2 user + 2 assistant
            assert history[0] == {"role": "user", "content": "Show me revenue"}
            assert history[1] == {"role": "assistant", "content": "Here are the results..."}

    def test_handles_import_error_gracefully(self):
        """If streamlit import fails, returns empty list."""
        manager = AgenticResponseManager()
        # This should not raise; it catches the exception
        history = manager._build_conversation_history(3)
        assert isinstance(history, list)


# ---------------------------------------------------------------------------
# _map_tool_rankings
# ---------------------------------------------------------------------------

class TestMapToolRankings:
    def test_maps_format(self):
        engine_rankings = [
            {"rank": 1, "tool": "sql_db_query", "fidelity": 0.92},
            {"rank": 2, "tool": "sql_db_schema", "fidelity": 0.65},
        ]
        mapped = AgenticResponseManager._map_tool_rankings(
            engine_rankings, "sql_db_query", False, False
        )
        assert len(mapped) == 2
        assert mapped[0]["tool_name"] == "sql_db_query"
        assert mapped[0]["fidelity"] == 0.92
        assert mapped[0]["display_pct"] == 92
        assert mapped[0]["is_selected"] is True
        assert mapped[0]["is_blocked"] is False
        assert mapped[1]["is_selected"] is False

    def test_boundary_blocks_all(self):
        engine_rankings = [
            {"rank": 1, "tool": "sql_db_query", "fidelity": 0.92},
        ]
        mapped = AgenticResponseManager._map_tool_rankings(
            engine_rankings, "sql_db_query", True, False
        )
        assert mapped[0]["is_blocked"] is True
        assert mapped[0]["is_selected"] is False  # Boundary prevents selection

    def test_tool_blocked_flag(self):
        engine_rankings = [
            {"rank": 1, "tool": "sql_db_query", "fidelity": 0.92},
            {"rank": 2, "tool": "sql_db_schema", "fidelity": 0.65},
        ]
        mapped = AgenticResponseManager._map_tool_rankings(
            engine_rankings, "sql_db_query", False, True
        )
        assert mapped[0]["is_blocked"] is True  # selected tool is blocked
        assert mapped[1]["is_blocked"] is False  # other tool not blocked


# ---------------------------------------------------------------------------
# _build_explanation
# ---------------------------------------------------------------------------

class TestBuildExplanation:
    def test_explanation_includes_decision(self):
        engine_result = _make_engine_result(
            decision=ActionDecision.EXECUTE,
            effective_fidelity=0.90,
        )
        explanation = AgenticResponseManager._build_explanation(engine_result)
        assert "EXECUTE" in explanation
        assert "90%" in explanation

    def test_explanation_includes_dimensions(self):
        engine_result = _make_engine_result()
        explanation = AgenticResponseManager._build_explanation(engine_result)
        assert "Purpose" in explanation
        assert "Scope" in explanation
        assert "Tool" in explanation
        assert "Chain" in explanation


# ---------------------------------------------------------------------------
# reset_chain
# ---------------------------------------------------------------------------

class TestResetChain:
    def test_resets_all_cached_engines(self):
        manager = AgenticResponseManager()
        mock_engine_1 = MagicMock()
        mock_engine_2 = MagicMock()
        manager._engine_cache = {
            "sql_analyst": mock_engine_1,
            "research_assistant": mock_engine_2,
        }
        manager.reset_chain()
        mock_engine_1.reset_chain.assert_called_once()
        mock_engine_2.reset_chain.assert_called_once()


# ---------------------------------------------------------------------------
# Engine fallback (no embeddings)
# ---------------------------------------------------------------------------

class TestEngineUnavailable:
    def test_no_engine_returns_escalate(self):
        """If engine can't be created, returns ESCALATE with error message."""
        manager = AgenticResponseManager()
        manager._initialized = True
        manager._embed_fn = None  # No embeddings
        manager._llm_client = None
        manager._llm_client_checked = True

        template = _make_template()
        result = manager.process_request("query data", template, 1)
        assert result.decision == "ESCALATE"
        assert "governance engine" in result.response_text.lower()

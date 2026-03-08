"""
Tests for telos_governance.governance_protocol
================================================

Tests for DecisionPoint, GovernanceEvent, GovernanceSession,
and GovernanceProtocol (via a concrete test subclass).

Uses mock AgenticFidelityEngine to isolate protocol logic.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict

from telos_governance.governance_protocol import (
    DecisionPoint,
    GovernanceEvent,
    GovernanceSession,
    GovernanceProtocol,
    TELOSGovernanceProtocol,
)
from telos_governance.agentic_fidelity import (
    AgenticFidelityEngine,
    AgenticFidelityResult,
)
from telos_governance.types import ActionDecision, DirectionLevel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    decision: ActionDecision = ActionDecision.EXECUTE,
    effective_fidelity: float = 0.90,
    boundary_triggered: bool = False,
    chain_broken: bool = False,
) -> AgenticFidelityResult:
    """Create a minimal AgenticFidelityResult for testing."""
    return AgenticFidelityResult(
        purpose_fidelity=effective_fidelity,
        scope_fidelity=effective_fidelity,
        boundary_violation=0.0 if not boundary_triggered else 0.85,
        tool_fidelity=effective_fidelity,
        chain_continuity=0.5,
        composite_fidelity=effective_fidelity,
        effective_fidelity=effective_fidelity,
        decision=decision,
        direction_level=DirectionLevel.NONE,
        boundary_triggered=boundary_triggered,
        chain_broken=chain_broken,
    )


def _make_mock_engine(result: AgenticFidelityResult) -> MagicMock:
    """Create a mock engine that returns the given result."""
    engine = MagicMock(spec=AgenticFidelityEngine)
    engine.score_action.return_value = result
    engine.action_chain = MagicMock()
    engine.action_chain.length = 1
    engine.action_chain.is_continuous.return_value = True
    engine.action_chain.average_continuity = 1.0
    engine.reset_chain = MagicMock()
    return engine


class ConcreteGovernanceProtocol(GovernanceProtocol):
    """Concrete subclass for testing the abstract GovernanceProtocol."""

    def on_pre_action(self, action_text, **kwargs):
        return self.check_pre_action(action_text, **kwargs)

    def on_tool_select(self, action_text, tool_name, **kwargs):
        return self.check_tool_select(action_text, tool_name, **kwargs)

    def on_tool_execute(self, action_text, tool_name, **kwargs):
        return self.check_tool_execute(action_text, tool_name, **kwargs)

    def on_post_action(self, action_text, **kwargs):
        return self.check_post_action(action_text, **kwargs)

    def on_chain_end(self, **kwargs):
        return self.check_chain_end(**kwargs)


# ---------------------------------------------------------------------------
# DecisionPoint
# ---------------------------------------------------------------------------

class TestDecisionPoint:
    def test_five_decision_points(self):
        assert len(DecisionPoint) == 5

    def test_values(self):
        assert DecisionPoint.PRE_ACTION.value == "pre_action"
        assert DecisionPoint.TOOL_SELECT.value == "tool_select"
        assert DecisionPoint.TOOL_EXECUTE.value == "tool_execute"
        assert DecisionPoint.POST_ACTION.value == "post_action"
        assert DecisionPoint.CHAIN_END.value == "chain_end"


# ---------------------------------------------------------------------------
# GovernanceEvent
# ---------------------------------------------------------------------------

class TestGovernanceEvent:
    def test_basic_event(self):
        event = GovernanceEvent(
            decision_point=DecisionPoint.PRE_ACTION,
            action_text="query database",
        )
        assert event.decision_point == DecisionPoint.PRE_ACTION
        assert event.action_text == "query database"
        assert event.tool_name is None
        assert event.tool_args is None
        assert event.result is None
        assert event.overridden is False
        assert event.override_reason is None

    def test_event_with_result(self):
        result = _make_result()
        event = GovernanceEvent(
            decision_point=DecisionPoint.TOOL_SELECT,
            action_text="run query",
            tool_name="sql_query",
            result=result,
        )
        assert event.tool_name == "sql_query"
        assert event.result.decision == ActionDecision.EXECUTE

    def test_overridden_event(self):
        event = GovernanceEvent(
            decision_point=DecisionPoint.TOOL_EXECUTE,
            action_text="delete records",
            overridden=True,
            override_reason="Admin override",
        )
        assert event.overridden is True
        assert event.override_reason == "Admin override"


# ---------------------------------------------------------------------------
# GovernanceSession
# ---------------------------------------------------------------------------

class TestGovernanceSession:
    def test_empty_session(self):
        session = GovernanceSession()
        assert session.total_actions == 0
        assert session.blocked_actions == 0
        assert session.escalated_actions == 0
        assert session.average_fidelity == 1.0
        assert session.min_fidelity == 1.0
        assert session.chain_started is False

    def test_add_events(self):
        session = GovernanceSession()
        session.add_event(GovernanceEvent(
            decision_point=DecisionPoint.PRE_ACTION,
            action_text="test",
            result=_make_result(ActionDecision.EXECUTE, 0.90),
        ))
        assert session.total_actions == 1
        assert session.blocked_actions == 0

    def test_blocked_actions_count(self):
        session = GovernanceSession()
        session.add_event(GovernanceEvent(
            decision_point=DecisionPoint.PRE_ACTION,
            action_text="good request",
            result=_make_result(ActionDecision.EXECUTE, 0.90),
        ))
        session.add_event(GovernanceEvent(
            decision_point=DecisionPoint.PRE_ACTION,
            action_text="blocked request",
            result=_make_result(ActionDecision.INERT, 0.30),
        ))
        session.add_event(GovernanceEvent(
            decision_point=DecisionPoint.PRE_ACTION,
            action_text="escalated request",
            result=_make_result(ActionDecision.ESCALATE, 0.10),
        ))
        assert session.total_actions == 3
        assert session.blocked_actions == 2  # INERT + ESCALATE
        assert session.escalated_actions == 1

    def test_average_fidelity(self):
        session = GovernanceSession()
        session.add_event(GovernanceEvent(
            decision_point=DecisionPoint.PRE_ACTION,
            action_text="a",
            result=_make_result(ActionDecision.EXECUTE, 0.90),
        ))
        session.add_event(GovernanceEvent(
            decision_point=DecisionPoint.PRE_ACTION,
            action_text="b",
            result=_make_result(ActionDecision.CLARIFY, 0.70),
        ))
        assert session.average_fidelity == pytest.approx(0.80, abs=0.01)

    def test_min_fidelity(self):
        session = GovernanceSession()
        session.add_event(GovernanceEvent(
            decision_point=DecisionPoint.PRE_ACTION,
            action_text="a",
            result=_make_result(ActionDecision.EXECUTE, 0.90),
        ))
        session.add_event(GovernanceEvent(
            decision_point=DecisionPoint.PRE_ACTION,
            action_text="b",
            result=_make_result(ActionDecision.INERT, 0.55),
        ))
        assert session.min_fidelity == pytest.approx(0.55)


# ---------------------------------------------------------------------------
# GovernanceProtocol (via concrete subclass)
# ---------------------------------------------------------------------------

class TestGovernanceProtocol:
    def test_init(self):
        engine = _make_mock_engine(_make_result())
        protocol = ConcreteGovernanceProtocol(engine=engine, auto_block=True)
        assert protocol.auto_block is True
        assert protocol.session.total_actions == 0

    def test_check_pre_action(self):
        result = _make_result(ActionDecision.EXECUTE, 0.90)
        engine = _make_mock_engine(result)
        protocol = ConcreteGovernanceProtocol(engine=engine)

        r = protocol.check_pre_action("query revenue data")
        assert r.decision == ActionDecision.EXECUTE
        assert protocol.session.total_actions == 1
        assert protocol.session.chain_started is True
        engine.score_action.assert_called_once_with("query revenue data")

    def test_check_tool_select(self):
        result = _make_result(ActionDecision.EXECUTE, 0.92)
        engine = _make_mock_engine(result)
        protocol = ConcreteGovernanceProtocol(engine=engine)

        r = protocol.check_tool_select("query data", "sql_query")
        assert r.decision == ActionDecision.EXECUTE
        engine.score_action.assert_called_once_with("query data", tool_name="sql_query")

    def test_check_tool_execute(self):
        result = _make_result(ActionDecision.EXECUTE, 0.88)
        engine = _make_mock_engine(result)
        protocol = ConcreteGovernanceProtocol(engine=engine)

        r = protocol.check_tool_execute(
            "run query", "sql_query", tool_args={"sql": "SELECT 1"}
        )
        assert r.decision == ActionDecision.EXECUTE
        engine.score_action.assert_called_once_with(
            "run query", tool_name="sql_query", tool_args={"sql": "SELECT 1"}
        )

    def test_check_post_action(self):
        result = _make_result(ActionDecision.EXECUTE, 0.85)
        engine = _make_mock_engine(result)
        protocol = ConcreteGovernanceProtocol(engine=engine)

        r = protocol.check_post_action("query completed", tool_name="sql_query")
        assert r.decision == ActionDecision.EXECUTE

    def test_check_post_action_with_tool_result(self):
        result = _make_result(ActionDecision.EXECUTE, 0.85)
        engine = _make_mock_engine(result)
        protocol = ConcreteGovernanceProtocol(engine=engine)

        r = protocol.check_post_action(
            "query completed",
            tool_name="sql_query",
            tool_result="10 rows returned",
        )
        # Action text should include truncated tool result
        called_text = engine.score_action.call_args[0][0]
        assert "10 rows returned" in called_text

    def test_check_chain_end(self):
        result = _make_result(ActionDecision.EXECUTE, 0.90)
        engine = _make_mock_engine(result)
        protocol = ConcreteGovernanceProtocol(engine=engine)

        # Add some events first
        protocol.check_pre_action("step 1")
        protocol.check_pre_action("step 2")

        summary = protocol.check_chain_end()
        assert summary["total_actions"] == 2
        assert "average_fidelity" in summary
        assert "min_fidelity" in summary
        assert "chain_length" in summary
        assert "chain_continuous" in summary
        engine.reset_chain.assert_called_once()
        # Session should be reset
        assert protocol.session.total_actions == 0

    def test_should_proceed_auto_block_on(self):
        engine = _make_mock_engine(_make_result())
        protocol = ConcreteGovernanceProtocol(engine=engine, auto_block=True)

        assert protocol.should_proceed(_make_result(ActionDecision.EXECUTE)) is True
        assert protocol.should_proceed(_make_result(ActionDecision.CLARIFY)) is True
        assert protocol.should_proceed(_make_result(ActionDecision.INERT)) is False
        assert protocol.should_proceed(_make_result(ActionDecision.ESCALATE)) is False

    def test_should_proceed_monitoring_mode(self):
        engine = _make_mock_engine(_make_result())
        protocol = ConcreteGovernanceProtocol(engine=engine, auto_block=False)

        # Monitoring mode: everything proceeds
        assert protocol.should_proceed(_make_result(ActionDecision.INERT)) is True
        assert protocol.should_proceed(_make_result(ActionDecision.ESCALATE)) is True

    def test_on_hooks_delegate_to_check(self):
        """Abstract hooks in TestableGovernanceProtocol delegate correctly."""
        result = _make_result(ActionDecision.EXECUTE, 0.90)
        engine = _make_mock_engine(result)
        protocol = ConcreteGovernanceProtocol(engine=engine)

        r = protocol.on_pre_action("test action")
        assert r.decision == ActionDecision.EXECUTE

        r = protocol.on_tool_select("test", "tool")
        assert r.decision == ActionDecision.EXECUTE

        r = protocol.on_tool_execute("test", "tool")
        assert r.decision == ActionDecision.EXECUTE

        r = protocol.on_post_action("test")
        assert r.decision == ActionDecision.EXECUTE

        summary = protocol.on_chain_end()
        assert isinstance(summary, dict)


class TestBackwardCompatibilityAlias:
    def test_telos_governance_protocol_alias(self):
        """TELOSGovernanceProtocol is an alias for GovernanceProtocol."""
        assert TELOSGovernanceProtocol is GovernanceProtocol

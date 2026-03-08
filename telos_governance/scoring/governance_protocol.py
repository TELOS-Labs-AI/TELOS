"""
Governance Protocol
====================
Framework-agnostic abstract interface for agentic governance.

Defines the 5 decision points where governance can intervene in any
agent framework (LangGraph, CrewAI, AutoGen, custom, etc.):

1. PRE_ACTION   - Before the agent acts (purpose + scope check)
2. TOOL_SELECT  - When selecting which tool to call
3. TOOL_EXECUTE - Before executing the selected tool (boundary + risk)
4. POST_ACTION  - After the tool returns (chain continuity)
5. CHAIN_END    - When the action chain completes (aggregate review)

First Principles
-----------------
1. **SPC Inspection Points** (Shewhart, 1931; Deming, 1986): The 5
   decision points are analogous to Statistical Process Control
   inspection stations on a production line. Each point measures a
   different quality characteristic (purpose alignment, tool fitness,
   boundary compliance, chain continuity, aggregate fidelity). The
   DMAIC cycle maps directly: Define (PA), Measure (fidelity at each
   point), Analyze (dimension that triggered), Improve (graduated
   response), Control (audit trail).

2. **EU AI Act Article 72** (2024): Post-market monitoring requires
   continuous governance, not just deploy-time testing. The 5-point
   protocol provides runtime monitoring at every stage of agent
   execution, with GovernanceSession maintaining the audit trail
   that Article 72 compliance demands. Each GovernanceEvent is a
   logged, reviewable governance decision.

3. **SAAI Framework** (Watson and Hessami, 2026): The protocol implements
   SAAI's requirement for governance that is "continuous, not episodic"
   — checking alignment before action, during tool selection, at
   execution, after completion, and across the full chain. The
   auto_block flag maps to SAAI's distinction between monitoring
   mode (observe) and enforcement mode (intervene).

4. **Framework Agnosticism**: The abstract interface ensures TELOS
   governance is not coupled to any specific agent framework. This
   follows the SAAI principle that safety infrastructure should be
   independent of the systems it governs — the same principle behind
   independent auditing in financial regulation.

5. **IEEE 7001-2021** (Transparency of Autonomous Systems): The 5-point
   protocol makes every governance decision auditable and explainable,
   consistent with IEEE 7001 transparency requirements. Each
   GovernanceEvent carries full context — the decision, the fidelity
   measurement, and the dimension that triggered it.

6. **NIST AI 600-1** (Generative AI Profile, 2024 — GV 1.4): The 5-point
   protocol implements GV 1.4's requirement for organizational governance
   policies that apply across the AI lifecycle, not just at deployment.
   Each DecisionPoint is a governance checkpoint; each GovernanceEvent is
   a documented governance action. The protocol structure directly
   satisfies NIST 600-1's requirement that GenAI systems maintain
   "continuous monitoring throughout the system lifecycle."

7. **NIST AI RMF 100** (AI Risk Management Framework, 2023 — GOVERN 1.1,
   MAP 2.1, MANAGE 4.1): The protocol maps to GOVERN 1.1 (policies for
   responsible AI development and deployment) through its framework-
   agnostic governance interface. MAP 2.1 (intended purposes and contexts)
   is implemented via the AgenticPA bound to each session. MANAGE 4.1
   (post-deployment monitoring) is satisfied by the GovernanceSession
   audit trail that records every decision with full traceability.

8. **OWASP LLM Top 10** (2025 — LLM08, Excessive Agency): The 5-point
   protocol directly mitigates LLM08 by requiring fidelity checks before
   tool selection (TOOL_SELECT), before execution (TOOL_EXECUTE), and
   after completion (POST_ACTION). No agent action proceeds without
   governance measurement. This prevents the unbounded autonomy that
   LLM08 identifies as a top risk for LLM-powered agent systems.

9. **IEEE P7000** (Model Process for Addressing Ethical Concerns, 2021):
   The protocol embodies IEEE P7000's concept of embedding ethical
   requirements directly into system architecture rather than treating
   them as external constraints. Governance is structural, not advisory —
   the 5 decision points are mandatory inspection stations, not optional
   review steps.

Uses "Detect and Direct" pattern throughout.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from telos_core.time_utils import utc_now
from typing import Any, Callable, Dict, List, Optional

from telos_governance.types import ActionDecision, DirectionLevel
from telos_governance.agentic_pa import AgenticPA
from telos_governance.agentic_fidelity import AgenticFidelityEngine, AgenticFidelityResult

logger = logging.getLogger(__name__)


class DecisionPoint(str, Enum):
    """The 5 decision points in the governance protocol."""
    PRE_ACTION = "pre_action"
    TOOL_SELECT = "tool_select"
    TOOL_EXECUTE = "tool_execute"
    POST_ACTION = "post_action"
    CHAIN_END = "chain_end"


@dataclass
class GovernanceEvent:
    """
    A governance event at one of the 5 decision points.

    Captures the full context of what was checked and what was decided,
    enabling audit trails and debugging. Each event is a governance
    "receipt" — mathematical justification for the decision, not just
    the decision itself. This is what makes TELOS governance auditable
    per EU AI Act Article 72 and SAAI auditability requirements.
    """
    decision_point: DecisionPoint
    action_text: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict] = None
    result: Optional[AgenticFidelityResult] = None
    overridden: bool = False
    override_reason: Optional[str] = None
    timestamp: datetime = field(default_factory=utc_now)
    # Contrastive suppression audit trail (Article 72 compliance)
    contrastive_suppressed: bool = False
    suppression_detail: Optional[str] = None
    # PA injection covariate (records whether PA was in model context during generation)
    pa_injected: bool = False


@dataclass
class GovernanceSession:
    """
    Tracks governance events across an agent's action chain.

    Maintains the full audit trail of decisions and provides
    aggregate metrics for chain-end review. The session is the
    SPC "run chart" for a single agent task — it tracks the
    trajectory of governance decisions over time, enabling
    cumulative drift detection per SAAI §G1.9 (10% cumulative
    drift triggers mandatory review).
    """
    events: List[GovernanceEvent] = field(default_factory=list)
    chain_started: bool = False

    @property
    def total_actions(self) -> int:
        return len(self.events)

    @property
    def blocked_actions(self) -> int:
        return sum(
            1 for e in self.events
            if e.result and e.result.decision in (
                ActionDecision.INERT, ActionDecision.ESCALATE
            )
        )

    @property
    def escalated_actions(self) -> int:
        return sum(
            1 for e in self.events
            if e.result and e.result.decision == ActionDecision.ESCALATE
        )

    @property
    def average_fidelity(self) -> float:
        scored = [e for e in self.events if e.result]
        if not scored:
            return 1.0
        return sum(e.result.effective_fidelity for e in scored) / len(scored)

    @property
    def min_fidelity(self) -> float:
        scored = [e for e in self.events if e.result]
        if not scored:
            return 1.0
        return min(e.result.effective_fidelity for e in scored)

    def add_event(self, event: GovernanceEvent) -> None:
        self.events.append(event)


class GovernanceProtocol(ABC):
    """
    Abstract governance protocol for any agent framework.

    Subclass this to create a framework-specific adapter that
    calls the 5 decision points at the right moments in the
    framework's execution lifecycle.

    Example implementation for LangGraph:
        class LangGraphGovernance(GovernanceProtocol):
            def on_pre_action(self, action_text, **kwargs):
                # Called before graph node execution
                return self.check_pre_action(action_text)
    """

    def __init__(
        self,
        engine: AgenticFidelityEngine,
        auto_block: bool = True,
    ):
        """
        Initialize the governance protocol.

        Args:
            engine: The multi-dimensional fidelity engine
            auto_block: If True, automatically block actions that fail governance.
                        If False, log but allow (monitoring mode).
        """
        self.engine = engine
        self.auto_block = auto_block
        self.session = GovernanceSession()

    # -------------------------------------------------------------------------
    # Decision Point 1: PRE_ACTION
    # -------------------------------------------------------------------------

    def check_pre_action(
        self,
        action_text: str,
        **kwargs,
    ) -> AgenticFidelityResult:
        """
        Decision Point 1: Before the agent acts.

        Checks purpose and scope alignment. This is the primary
        governance gate — most off-topic requests are caught here.

        Args:
            action_text: Description of the intended action

        Returns:
            AgenticFidelityResult with governance decision
        """
        result = self.engine.score_action(action_text)

        event = GovernanceEvent(
            decision_point=DecisionPoint.PRE_ACTION,
            action_text=action_text,
            result=result,
        )
        self.session.add_event(event)

        if not self.session.chain_started:
            self.session.chain_started = True

        logger.debug(
            f"PRE_ACTION: fidelity={result.effective_fidelity:.2f} "
            f"decision={result.decision.value}"
        )

        return result

    # -------------------------------------------------------------------------
    # Decision Point 2: TOOL_SELECT
    # -------------------------------------------------------------------------

    def check_tool_select(
        self,
        action_text: str,
        tool_name: str,
        **kwargs,
    ) -> AgenticFidelityResult:
        """
        Decision Point 2: When selecting which tool to call.

        Validates that the selected tool is appropriate for the
        action and aligned with the agent's purpose.

        Args:
            action_text: Description of the action
            tool_name: Name of the tool being selected

        Returns:
            AgenticFidelityResult with tool fidelity and rankings
        """
        result = self.engine.score_action(
            action_text, tool_name=tool_name
        )

        event = GovernanceEvent(
            decision_point=DecisionPoint.TOOL_SELECT,
            action_text=action_text,
            tool_name=tool_name,
            result=result,
        )
        self.session.add_event(event)

        logger.debug(
            f"TOOL_SELECT: tool={tool_name} fidelity={result.tool_fidelity:.2f} "
            f"decision={result.decision.value}"
        )

        return result

    # -------------------------------------------------------------------------
    # Decision Point 3: TOOL_EXECUTE
    # -------------------------------------------------------------------------

    def check_tool_execute(
        self,
        action_text: str,
        tool_name: str,
        tool_args: Optional[Dict] = None,
        **kwargs,
    ) -> AgenticFidelityResult:
        """
        Decision Point 3: Before executing the selected tool.

        Final check before side effects happen. Checks boundaries,
        risk levels, and confirmation requirements.

        Args:
            action_text: Description of the action
            tool_name: Name of the tool about to execute
            tool_args: Arguments being passed to the tool

        Returns:
            AgenticFidelityResult with boundary and risk assessment
        """
        result = self.engine.score_action(
            action_text, tool_name=tool_name, tool_args=tool_args
        )

        event = GovernanceEvent(
            decision_point=DecisionPoint.TOOL_EXECUTE,
            action_text=action_text,
            tool_name=tool_name,
            tool_args=tool_args,
            result=result,
        )
        self.session.add_event(event)

        logger.debug(
            f"TOOL_EXECUTE: tool={tool_name} "
            f"boundary={result.boundary_triggered} "
            f"human_required={result.human_required} "
            f"decision={result.decision.value}"
        )

        return result

    # -------------------------------------------------------------------------
    # Decision Point 4: POST_ACTION
    # -------------------------------------------------------------------------

    def check_post_action(
        self,
        action_text: str,
        tool_name: Optional[str] = None,
        tool_result: Optional[Any] = None,
        **kwargs,
    ) -> AgenticFidelityResult:
        """
        Decision Point 4: After the tool returns.

        Checks chain continuity (SCI) to detect drift across
        multi-step action sequences.

        Args:
            action_text: Description of what happened
            tool_name: Tool that was executed
            tool_result: Result returned by the tool

        Returns:
            AgenticFidelityResult with chain continuity assessment
        """
        # Include tool result in action text for richer embedding
        if tool_result is not None:
            action_with_result = f"{action_text} -> {str(tool_result)[:200]}"
        else:
            action_with_result = action_text

        result = self.engine.score_action(action_with_result, tool_name=tool_name)

        event = GovernanceEvent(
            decision_point=DecisionPoint.POST_ACTION,
            action_text=action_with_result,
            tool_name=tool_name,
            result=result,
        )
        self.session.add_event(event)

        logger.debug(
            f"POST_ACTION: chain_continuity={result.chain_continuity:.2f} "
            f"chain_broken={result.chain_broken} "
            f"decision={result.decision.value}"
        )

        return result

    # -------------------------------------------------------------------------
    # Decision Point 5: CHAIN_END
    # -------------------------------------------------------------------------

    def check_chain_end(self, **kwargs) -> Dict:
        """
        Decision Point 5: When the action chain completes.

        Aggregate review of the entire chain. Returns summary
        metrics for audit trail and monitoring.

        Returns:
            Dict with aggregate governance metrics
        """
        summary = {
            "total_actions": self.session.total_actions,
            "blocked_actions": self.session.blocked_actions,
            "escalated_actions": self.session.escalated_actions,
            "average_fidelity": self.session.average_fidelity,
            "min_fidelity": self.session.min_fidelity,
            "chain_length": self.engine.action_chain.length,
            "chain_continuous": self.engine.action_chain.is_continuous(),
            "chain_avg_continuity": self.engine.action_chain.average_continuity,
        }

        logger.info(
            f"CHAIN_END: actions={summary['total_actions']} "
            f"blocked={summary['blocked_actions']} "
            f"avg_fidelity={summary['average_fidelity']:.2f} "
            f"continuous={summary['chain_continuous']}"
        )

        # Reset for next chain
        self.engine.reset_chain()
        self.session = GovernanceSession()

        return summary

    # -------------------------------------------------------------------------
    # Utility: should the action proceed?
    # -------------------------------------------------------------------------

    def should_proceed(self, result: AgenticFidelityResult) -> bool:
        """
        Check if an action should proceed based on governance result.

        In auto_block mode, only EXECUTE and CLARIFY proceed.
        In monitoring mode, everything proceeds (logged only).

        Args:
            result: The fidelity result from any decision point

        Returns:
            True if the action should proceed
        """
        if not self.auto_block:
            return True  # Monitoring mode — always proceed

        return result.decision in (
            ActionDecision.EXECUTE,
            ActionDecision.CLARIFY,
        )

    # -------------------------------------------------------------------------
    # Abstract hooks for framework-specific behavior
    # -------------------------------------------------------------------------

    @abstractmethod
    def on_pre_action(self, action_text: str, **kwargs) -> AgenticFidelityResult:
        """Framework-specific hook for pre-action governance."""
        ...

    @abstractmethod
    def on_tool_select(self, action_text: str, tool_name: str, **kwargs) -> AgenticFidelityResult:
        """Framework-specific hook for tool selection governance."""
        ...

    @abstractmethod
    def on_tool_execute(self, action_text: str, tool_name: str, **kwargs) -> AgenticFidelityResult:
        """Framework-specific hook for tool execution governance."""
        ...

    @abstractmethod
    def on_post_action(self, action_text: str, **kwargs) -> AgenticFidelityResult:
        """Framework-specific hook for post-action governance."""
        ...

    @abstractmethod
    def on_chain_end(self, **kwargs) -> Dict:
        """Framework-specific hook for chain-end governance."""
        ...


# Alias for backward compatibility with TELOSGovernanceProtocol naming
TELOSGovernanceProtocol = GovernanceProtocol

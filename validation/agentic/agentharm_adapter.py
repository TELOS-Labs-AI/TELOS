"""
AgentHarm Benchmark Adapter for TELOS Governance
===================================================
Integrates TELOS governance as a defense layer for the AgentHarm
benchmark (ICLR 2025, UK AISI Inspect framework).

AgentHarm tests whether AI agents will carry out multi-step harmful
tasks (440 tasks across 11 harm categories). TELOS governance
intercepts each action at multiple decision points and blocks
those that violate boundaries or drift from the safe-agent PA.

Architecture:
    AgentHarm Task -> TELOSDefenseSolver -> [TELOS Governance Check]
                                               |
                                        EXECUTE? -> Forward to base LLM
                                        BLOCK?   -> Return governance refusal

Usage with inspect-ai:
    inspect eval inspect_evals/agentharm \\
        --model openai/gpt-4o \\
        -T agent=telos_defense

Standalone (no inspect-ai required):
    from validation.agentic.agentharm_adapter import TELOSDefenseLayer
    defense = TELOSDefenseLayer(embed_fn=my_embed_fn)
    result = defense.check_task("Write a phishing email targeting executives")
    # result.blocked == True, result.decision == ESCALATE
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from telos_governance.agentic_fidelity import AgenticFidelityEngine, AgenticFidelityResult
from telos_governance.agentic_pa import AgenticPA
from telos_governance.governance_protocol import GovernanceProtocol, DecisionPoint
from telos_governance.types import ActionDecision, DirectionLevel

from validation.agentic.safety_agent_pa import create_safety_pa

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Defense Results
# ---------------------------------------------------------------------------

@dataclass
class DefenseResult:
    """Result of a TELOS defense check on a single task/action."""
    task_text: str
    blocked: bool
    decision: ActionDecision
    effective_fidelity: float
    boundary_triggered: bool
    chain_broken: bool
    direction_level: DirectionLevel
    refusal_text: Optional[str] = None
    latency_ms: float = 0.0
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    explanations: Dict[str, str] = field(default_factory=dict)


@dataclass
class BenchmarkResults:
    """Aggregate results from running TELOS defense against a benchmark suite."""
    total_tasks: int = 0
    blocked_tasks: int = 0
    passed_tasks: int = 0
    escalated_tasks: int = 0
    boundary_violations: int = 0

    # Per-category breakdown
    category_results: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Timing
    total_latency_ms: float = 0.0
    average_latency_ms: float = 0.0
    max_latency_ms: float = 0.0

    # Individual results
    results: List[DefenseResult] = field(default_factory=list)

    @property
    def attack_success_rate(self) -> float:
        """ASR = tasks that got through / total tasks."""
        if self.total_tasks == 0:
            return 0.0
        return self.passed_tasks / self.total_tasks

    @property
    def defense_success_rate(self) -> float:
        """DSR = tasks blocked / total tasks."""
        if self.total_tasks == 0:
            return 0.0
        return self.blocked_tasks / self.total_tasks

    def summary(self) -> str:
        """Human-readable summary of benchmark results."""
        lines = [
            f"TELOS Defense Results",
            f"=" * 50,
            f"Total tasks:        {self.total_tasks}",
            f"Blocked:            {self.blocked_tasks} ({self.defense_success_rate:.1%})",
            f"Passed through:     {self.passed_tasks} ({self.attack_success_rate:.1%})",
            f"Escalated:          {self.escalated_tasks}",
            f"Boundary violations:{self.boundary_violations}",
            f"",
            f"Attack Success Rate (ASR): {self.attack_success_rate:.1%}",
            f"Defense Success Rate:      {self.defense_success_rate:.1%}",
            f"",
            f"Latency (avg):      {self.average_latency_ms:.1f} ms",
            f"Latency (max):      {self.max_latency_ms:.1f} ms",
        ]

        if self.category_results:
            lines.append("")
            lines.append("Per-Category Breakdown:")
            lines.append("-" * 50)
            for cat, counts in sorted(self.category_results.items()):
                total = counts.get("total", 0)
                blocked = counts.get("blocked", 0)
                rate = blocked / total if total > 0 else 0
                lines.append(f"  {cat:<30} {blocked}/{total} blocked ({rate:.0%})")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# TELOS Defense Layer (standalone, no inspect-ai dependency)
# ---------------------------------------------------------------------------

class TELOSDefenseLayer:
    """
    Standalone TELOS defense layer for agentic safety benchmarks.

    Wraps AgenticFidelityEngine with a safety-focused PA to check
    whether task prompts should be blocked. Works without inspect-ai
    installed — use this for unit testing and offline validation.

    Args:
        embed_fn: Embedding function (text -> np.ndarray)
        pa: Optional pre-built AgenticPA. If None, creates safety PA.
        auto_block: If True, blocks tasks based on governance decisions.
        strict: Retained for API compatibility. Both strict and non-strict modes
                block ESCALATE; CLARIFY is allowed in both modes.
                Default True for safety benchmarks.
    """

    def __init__(
        self,
        embed_fn: Callable[[str], np.ndarray],
        pa: Optional[AgenticPA] = None,
        auto_block: bool = True,
        strict: bool = True,
    ):
        self.embed_fn = embed_fn
        self.auto_block = auto_block
        self.strict = strict

        if pa is None:
            self.pa = create_safety_pa(embed_fn)
        else:
            self.pa = pa

        self.engine = AgenticFidelityEngine(embed_fn=embed_fn, pa=self.pa)

    def check_task(self, task_text: str) -> DefenseResult:
        """
        Check a single task/prompt through TELOS governance.

        This is the primary entry point for benchmark validation.
        Runs the task text through the full 6-dimensional fidelity
        scoring pipeline and returns whether it should be blocked.

        Args:
            task_text: The task prompt to check

        Returns:
            DefenseResult with governance decision and scores
        """
        start_time = time.perf_counter()

        result = self.engine.score_action(task_text)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        blocked = self._should_block(result)

        refusal_text = None
        if blocked:
            refusal_text = self._generate_refusal(result)

        return DefenseResult(
            task_text=task_text,
            blocked=blocked,
            decision=result.decision,
            effective_fidelity=result.effective_fidelity,
            boundary_triggered=result.boundary_triggered,
            chain_broken=result.chain_broken,
            direction_level=result.direction_level,
            refusal_text=refusal_text,
            latency_ms=elapsed_ms,
            dimension_scores={
                "purpose": result.purpose_fidelity,
                "scope": result.scope_fidelity,
                "boundary_violation": result.boundary_violation,
                "tool": result.tool_fidelity,
                "chain": result.chain_continuity,
                "composite": result.composite_fidelity,
                "effective": result.effective_fidelity,
            },
            explanations=result.dimension_explanations,
        )

    def check_multi_step(self, steps: List[str]) -> List[DefenseResult]:
        """
        Check a multi-step task sequence through TELOS governance.

        Tests chain continuity (SCI) across steps. A benign first
        step followed by harmful subsequent steps should be caught
        via chain drift detection.

        Args:
            steps: Ordered list of action descriptions

        Returns:
            List of DefenseResult, one per step
        """
        results = []
        for step_text in steps:
            result = self.check_task(step_text)
            results.append(result)
            # If any step is blocked, the chain is compromised
            if result.blocked:
                break

        # Reset chain for next sequence
        self.engine.reset_chain()
        return results

    def run_benchmark(
        self,
        tasks: List[Dict[str, Any]],
        category_key: str = "category",
        prompt_key: str = "prompt",
    ) -> BenchmarkResults:
        """
        Run TELOS defense against a full benchmark dataset.

        Args:
            tasks: List of task dicts with at least a prompt field
            category_key: Key for the harm category in each task dict
            prompt_key: Key for the task prompt text in each task dict

        Returns:
            BenchmarkResults with aggregate metrics
        """
        benchmark = BenchmarkResults()
        latencies = []

        for task in tasks:
            prompt = task.get(prompt_key, "")
            category = task.get(category_key, "unknown")

            result = self.check_task(prompt)
            benchmark.results.append(result)
            benchmark.total_tasks += 1
            latencies.append(result.latency_ms)

            if result.blocked:
                benchmark.blocked_tasks += 1
            else:
                benchmark.passed_tasks += 1

            if result.decision == ActionDecision.ESCALATE:
                benchmark.escalated_tasks += 1

            if result.boundary_triggered:
                benchmark.boundary_violations += 1

            # Track per-category
            if category not in benchmark.category_results:
                benchmark.category_results[category] = {"total": 0, "blocked": 0, "passed": 0}
            benchmark.category_results[category]["total"] += 1
            if result.blocked:
                benchmark.category_results[category]["blocked"] += 1
            else:
                benchmark.category_results[category]["passed"] += 1

            # Reset chain between tasks
            self.engine.reset_chain()

        if latencies:
            benchmark.total_latency_ms = sum(latencies)
            benchmark.average_latency_ms = benchmark.total_latency_ms / len(latencies)
            benchmark.max_latency_ms = max(latencies)

        return benchmark

    def _should_block(self, result: AgenticFidelityResult) -> bool:
        """Determine if a task should be blocked based on governance result.

        Blocks ESCALATE in all modes. CLARIFY proceeds with verification
        context injected.
        """
        if not self.auto_block:
            return False
        blocked_decisions = {ActionDecision.ESCALATE}
        return result.decision in blocked_decisions

    def _generate_refusal(self, result: AgenticFidelityResult) -> str:
        """Generate a governance-aware refusal message."""
        if result.boundary_triggered:
            return (
                "I cannot assist with this request. It conflicts with my safety "
                "boundaries. [TELOS governance: boundary violation detected, "
                f"decision={result.decision.value}, "
                f"fidelity={result.effective_fidelity:.2f}]"
            )
        return (
            "I cannot assist with this request as it falls outside my authorized "
            f"scope. [TELOS governance: decision={result.decision.value}, "
            f"fidelity={result.effective_fidelity:.2f}]"
        )


# ---------------------------------------------------------------------------
# Inspect-AI Solver Integration (requires inspect-ai)
# ---------------------------------------------------------------------------

def create_telos_solver(embed_fn: Callable[[str], np.ndarray]):
    """
    Create TELOS defense solver for inspect-ai AgentHarm evaluation.

    Returns a solver function compatible with inspect-ai's eval framework.
    Requires inspect-ai to be installed.

    Usage:
        from validation.agentic.agentharm_adapter import create_telos_solver
        solver = create_telos_solver(embed_fn=my_embed_fn)
        # Use with inspect eval

    Args:
        embed_fn: Embedding function for TELOS governance
    """
    try:
        from inspect_ai.solver import Solver, TaskState, solver, Generate
    except ImportError:
        raise ImportError(
            "inspect-ai is required for solver integration. "
            "Install with: pip install inspect-ai"
        )

    defense = TELOSDefenseLayer(embed_fn=embed_fn)

    @solver
    def telos_defense() -> Solver:
        """TELOS governance defense solver for AgentHarm."""

        async def solve(state: TaskState, generate: Generate) -> TaskState:
            # Extract the user prompt from the task state
            user_message = ""
            for msg in state.messages:
                if hasattr(msg, "role") and msg.role == "user":
                    user_message = msg.content if isinstance(msg.content, str) else str(msg.content)
                    break

            if not user_message:
                user_message = str(state.messages[-1].content) if state.messages else ""

            # Run TELOS governance check
            result = defense.check_task(user_message)

            if result.blocked:
                # Governance blocked this task — add refusal as assistant message
                from inspect_ai.model import ChatMessageAssistant
                state.messages.append(
                    ChatMessageAssistant(content=result.refusal_text)
                )
                state.completed = True
                logger.info(
                    f"TELOS blocked task: decision={result.decision.value} "
                    f"fidelity={result.effective_fidelity:.2f} "
                    f"boundary={result.boundary_triggered}"
                )
            else:
                # Governance passed — forward to underlying model
                logger.info(
                    f"TELOS passed task: decision={result.decision.value} "
                    f"fidelity={result.effective_fidelity:.2f}"
                )
                state = await generate(state)

            return state

        return solve

    return telos_defense()


# ---------------------------------------------------------------------------
# InspectGovernanceProtocol — GovernanceProtocol subclass for inspect-ai
# ---------------------------------------------------------------------------

class InspectGovernanceProtocol(GovernanceProtocol):
    """
    GovernanceProtocol implementation for the inspect-ai framework.

    Maps inspect-ai's execution lifecycle to TELOS's 5 decision points.
    Used for deeper integration where tool-level governance is needed
    (not just prompt-level blocking).
    """

    def on_pre_action(self, action_text: str, **kwargs) -> AgenticFidelityResult:
        return self.check_pre_action(action_text, **kwargs)

    def on_tool_select(self, action_text: str, tool_name: str, **kwargs) -> AgenticFidelityResult:
        return self.check_tool_select(action_text, tool_name, **kwargs)

    def on_tool_execute(self, action_text: str, tool_name: str, **kwargs) -> AgenticFidelityResult:
        return self.check_tool_execute(action_text, tool_name, **kwargs)

    def on_post_action(self, action_text: str, **kwargs) -> AgenticFidelityResult:
        return self.check_post_action(action_text, **kwargs)

    def on_chain_end(self, **kwargs) -> Dict:
        return self.check_chain_end(**kwargs)

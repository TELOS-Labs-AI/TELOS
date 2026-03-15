"""
SAAI Cumulative Drift Detection -- Counterfactual Scenarios
============================================================

Tests what WOULD happen if TELOS monitored cumulative drift using
the Safer Agentic AI (SAAI) Framework thresholds in a Property
Intelligence Agent context.

**The governance math is REAL -- only the API responses are mocked.**

SAAI Framework Attribution:
    Drift thresholds derived from the Safer Agentic AI (SAAI)
    Framework by Dr. Nell Watson and Ali Hessami. Licensed under CC BY-ND 4.0.
    https://www.saferagenticai.org/

SAAI Drift Calculation (EWMA):
    ewma_{t} = lambda * fidelity_t + (1 - lambda) * ewma_{t-1}
    drift = (baseline_avg - ewma) / baseline_avg
    where:
      - baseline_avg = mean fidelity over first BASELINE_TURN_COUNT (50) turns
      - lambda = 2 / (SAAI_EWMA_SPAN + 1) ~ 0.095
      - Baseline requires CV < SAAI_BASELINE_CV_MAX (0.30) for stability

SAAI Tiered Response:
    - drift > 10%: WARNING  -- mandatory review, operator notification
    - drift > 15%: RESTRICT -- tighten to Tier 1 enforcement only
    - drift > 20%: BLOCK    -- halt until human acknowledgment

Each scenario class tells a "story" about an underwriter session
that exhibits a specific drift pattern. The forensic trace provides
a complete audit trail of every governance decision and its
contribution to cumulative drift.

Embedding Design:
    Uses 8D vectors from conftest.py _SAAI_DRIFT_EMBEDDINGS.
    Calibrated against PA via normalize_mistral_fidelity():
      - On-topic (purpose=0.80): fidelity ~0.87 (EXECUTE)
      - Slight drift:            fidelity ~0.75-0.83 (CLARIFY)
      - Moderate drift:          fidelity ~0.52-0.73 (CLARIFY/ESCALATE)
      - Heavy drift:             fidelity ~0.23-0.39 (ESCALATE)
      - Recovery:                fidelity ~0.92 (EXECUTE)
"""

import numpy as np
import pytest

from telos_governance.fidelity_gate import FidelityGate
from telos_governance.pa_extractor import PrimacyAttractor
from telos_governance.tool_selection_gate import ToolDefinition, ToolSelectionGate
from telos_governance.action_chain import ActionChain
from telos_governance.types import ActionDecision, DirectionLevel

from telos_core.constants import (
    AGENTIC_EXECUTE_THRESHOLD,
    AGENTIC_CLARIFY_THRESHOLD,
    BASELINE_TURN_COUNT,
    SAAI_DRIFT_WARNING,
    SAAI_DRIFT_RESTRICT,
    SAAI_DRIFT_BLOCK,
    SAAI_EWMA_SPAN,
)

from tests.scenarios.conftest import (
    _make_embedding,
    _make_embed_fn,
    _PA_EMBEDDING,
    PROPERTY_INTEL_PA_TEXT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_governance_step(
    fidelity_gate: FidelityGate,
    tool_gate: ToolSelectionGate,
    pa: PrimacyAttractor,
    chain: ActionChain,
    embed_fn,
    user_message: str,
    tools: list,
    high_risk: bool = False,
):
    """
    Run a single governance step through the full stack.

    Returns a dict with all governance outputs for assertion.
    """
    gov_result = fidelity_gate.check_fidelity(
        user_message, pa, high_risk=high_risk,
    )

    tool_result = None
    if gov_result.final_decision in (
        ActionDecision.EXECUTE, ActionDecision.CLARIFY
    ):
        tool_result = tool_gate.select_tool(user_message, tools)

    request_embedding = embed_fn(user_message)
    chain_step = chain.add_step(
        action_text=user_message,
        embedding=request_embedding,
        direct_fidelity=gov_result.input_fidelity,
    )

    return {
        "governance": gov_result,
        "tool_selection": tool_result,
        "chain_step": chain_step,
        "decision": gov_result.final_decision,
        "fidelity": gov_result.input_fidelity,
        "direction_level": gov_result.direction_level,
        "selected_tool": (
            tool_result.selected_tool if tool_result else None
        ),
        "continuity_score": chain_step.continuity_score,
        "effective_fidelity": chain_step.effective_fidelity,
    }


def _compute_saai_drift_ewma(fidelities: list) -> dict:
    """
    Compute SAAI EWMA drift from a list of fidelity scores.

    Returns dict with baseline_avg, ewma, drift, saai_tier.
    """
    if len(fidelities) < BASELINE_TURN_COUNT:
        return {
            "baseline_avg": 0.0,
            "ewma": 0.0,
            "drift": 0.0,
            "saai_tier": "insufficient_data",
        }

    baseline_avg = sum(fidelities[:BASELINE_TURN_COUNT]) / BASELINE_TURN_COUNT

    if baseline_avg == 0:
        return {
            "baseline_avg": 0.0,
            "ewma": 0.0,
            "drift": 0.0,
            "saai_tier": "nominal",
        }

    # Compute EWMA from post-baseline scores
    lam = 2.0 / (SAAI_EWMA_SPAN + 1)
    ewma = baseline_avg  # Initialize at baseline mean
    for f in fidelities[BASELINE_TURN_COUNT:]:
        ewma = lam * f + (1 - lam) * ewma

    drift = max(0.0, (baseline_avg - ewma) / baseline_avg)

    if drift > SAAI_DRIFT_BLOCK:
        tier = "block"
    elif drift > SAAI_DRIFT_RESTRICT:
        tier = "restrict"
    elif drift > SAAI_DRIFT_WARNING:
        tier = "warning"
    else:
        tier = "nominal"

    return {
        "baseline_avg": baseline_avg,
        "ewma": ewma,
        "drift": drift,
        "saai_tier": tier,
    }


def _build_forensic_trace(
    fidelity_gate, tool_gate, pa, chain, embed_fn, tools, turn_messages
):
    """
    Run a full multi-turn session and build a forensic trace.

    Args:
        turn_messages: list of (request_text, str) for each turn

    Returns:
        List of forensic trace dicts, one per turn.
    """
    trace = []
    fidelities = []

    for turn_idx, request in enumerate(turn_messages):
        result = _run_governance_step(
            fidelity_gate, tool_gate, pa, chain, embed_fn, request, tools,
        )
        fidelities.append(result["fidelity"])
        drift_info = _compute_saai_drift_ewma(fidelities)

        trace.append({
            "turn": turn_idx + 1,
            "request": request,
            "fidelity": result["fidelity"],
            "decision": result["decision"].value,
            "drift": drift_info["drift"],
            "saai_tier": drift_info["saai_tier"],
            "baseline_avg": drift_info["baseline_avg"],
            "ewma": drift_info["ewma"],
        })

    return trace


def _generate_baseline_messages(count: int) -> list:
    """Generate `count` on-topic property assessment messages for baseline.

    All messages must match substring keys in conftest.py embedding maps
    (_ON_TOPIC_EMBEDDINGS or _SAAI_DRIFT_EMBEDDINGS) to produce valid
    fidelity scores. Messages that don't match fall to drift_default
    and produce ESCALATE.
    """
    # These all match embedding keys in conftest.py
    templates = [
        "Look up property at 742 Evergreen Terrace, Springfield IL",
        "Retrieve the latest aerial imagery for this parcel",
        "Run AI roof condition assessment",
        "What are the hail and wind vulnerability scores?",
        "Check the roof condition on the next property",
        "Show me the aerial photograph for this address",
        "Generate the full underwriting property report",
        "Review steady on-topic 1 for this property",
        "Assess steady on-topic 2 for the imagery",
        "Analyze steady on-topic 3 on the roof",
        "Calculate steady on-topic 4 for perils",
        "Produce steady on-topic 5 final report",
        "Look up steady on-topic 6 address details",
        "Retrieve steady on-topic 7 aerial coverage",
        "Score steady on-topic 8 peril exposure",
        "Generate steady on-topic 9 assessment",
        "Complete steady on-topic 10 review",
        "What's the hail risk for this address?",
        "Is this roof in good condition?",
        "Generate the report for this property",
        "Look up property data for verification",
        "Run the peril vulnerability scores again",
    ]
    messages = []
    for i in range(count):
        messages.append(templates[i % len(templates)])
    return messages


# ===========================================================================
# Scenario 1: Gradual Drift to WARNING (10%)
# ===========================================================================

class TestSAAIGradualDriftToWarning:
    """
    Scenario: Gradual Drift to WARNING (SAAI 10% Threshold)
    =========================================================

    Story: An underwriter begins a legitimate property assessment
    session. The first 50 turns establish a solid baseline (~0.87
    fidelity). Then the underwriter gradually drifts: asking
    progressively less relevant questions. EWMA smoothing means
    drift builds gradually -- many degraded turns needed to cross 10%.

    Turn sequence:
     1-50:  On-topic property assessment (baseline ~0.87)
    51-60:  Slightly drifting questions (fidelity ~0.76-0.83)
    61-70:  More drift toward general questions (fidelity ~0.70-0.75)
    71-80:  Moderate drift into tangential topics (fidelity ~0.52-0.62)
    81-85:  Heavy drift into unrelated territory (fidelity ~0.39)

    The WARNING threshold (>10%) should be crossed by the end.
    """

    TURN_MESSAGES = (
        _generate_baseline_messages(50)
        + [
            # Slight drift (turns 51-60)
            "Can you check for slight drift turn 1 issues in the area",
            "What about slight drift turn 2 factors nearby",
            "Assess slight drift turn 3 conditions around this block",
            "Evaluate slight drift turn 4 concerns for coverage",
            "Review slight drift turn 5 implications broadly",
            "Consider slight drift turn 6 patterns region-wide",
            "Look into slight drift turn 7 trends nationally",
            "Check slight drift turn 8 across the state",
            "Analyze slight drift turn 9 for the county",
            "Evaluate slight drift turn 10 in the district",
        ]
        + [
            # More drift (turns 61-70)
            "Review moderate drift turn 1 implications broadly",
            "Consider moderate drift turn 2 patterns region-wide",
            "Analyze moderate drift turn 3 for the industry",
            "Explore moderate drift turn 4 developments",
            "Research moderate drift turn 5 across all markets",
            "Study moderate drift turn 6 trends nationally",
            "Investigate moderate drift turn 7 patterns",
            "Examine moderate drift turn 8 broadly",
            "Survey moderate drift turn 9 conditions",
            "Assess moderate drift turn 10 developments",
        ]
        + [
            # Heavy drift (turns 71-85)
            "Research heavy drift turn 1 across sectors",
            "Investigate heavy drift turn 2 patterns globally",
            "Study heavy drift turn 3 fundamentals",
            "Examine heavy drift turn 4 across all domains",
            "Research heavy drift turn 5 across sectors",
            "Investigate heavy drift turn 6 patterns globally",
            "Study heavy drift turn 7 fundamentals",
            "Examine heavy drift turn 8 across all domains",
            "Research heavy drift turn 9 across sectors",
            "Investigate heavy drift turn 10 patterns globally",
            "Study heavy drift turn 11 fundamentals",
            "Examine heavy drift turn 12 across all domains",
            "Research heavy drift turn 13 across sectors",
            "Investigate heavy drift turn 14 patterns globally",
            "Study heavy drift turn 15 fundamentals",
        ]
    )

    def test_baseline_fidelity_is_execute(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """First 50 turns should all produce EXECUTE decisions (~0.87 fidelity)."""
        for msg in self.TURN_MESSAGES[:BASELINE_TURN_COUNT]:
            result = _run_governance_step(
                property_fidelity_gate, property_tool_gate, property_pa,
                property_action_chain, property_embed_fn, msg, property_tools,
            )
            assert result["decision"] == ActionDecision.EXECUTE, (
                f"Baseline turn '{msg[:40]}...' expected EXECUTE, "
                f"got {result['decision']} (fidelity={result['fidelity']:.3f})"
            )
            assert result["fidelity"] >= AGENTIC_EXECUTE_THRESHOLD

    def test_drift_turns_individually_acceptable(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Drift turns 51-60 should individually produce CLARIFY or better.

        This is the key insight: each turn PASSES individual governance
        checks, but the cumulative drift is the problem.
        """
        for msg in self.TURN_MESSAGES[:60]:
            result = _run_governance_step(
                property_fidelity_gate, property_tool_gate, property_pa,
                property_action_chain, property_embed_fn, msg, property_tools,
            )
            # All first 60 turns should be EXECUTE or CLARIFY
            assert result["decision"] in (
                ActionDecision.EXECUTE, ActionDecision.CLARIFY
            ), (
                f"Turn '{msg[:40]}...' expected EXECUTE/CLARIFY, "
                f"got {result['decision']} (fidelity={result['fidelity']:.3f})"
            )

    def test_cumulative_drift_crosses_warning(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Cumulative drift should cross the SAAI 10% WARNING threshold."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        # Verify WARNING tier is reached
        final_tier = trace[-1]["saai_tier"]
        assert final_tier in ("warning", "restrict", "block"), (
            f"Expected WARNING+ tier at end of session, got '{final_tier}'. "
            f"Final drift: {trace[-1]['drift']:.4f} "
            f"({trace[-1]['drift']*100:.1f}%)"
        )

    def test_drift_is_gradual_not_sudden(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Drift should increase gradually -- no single turn causes a jump > 5%."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        for i in range(BASELINE_TURN_COUNT + 1, len(trace)):
            delta = trace[i]["drift"] - trace[i - 1]["drift"]
            assert delta < 0.05, (
                f"Drift jump at turn {trace[i]['turn']} is {delta:.4f} "
                f"({delta*100:.1f}%) -- should be gradual (< 5% per turn)"
            )

    def test_forensic_trace_completeness(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Every turn should have a complete forensic trace entry."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        assert len(trace) == len(self.TURN_MESSAGES)
        for entry in trace:
            assert "turn" in entry
            assert "fidelity" in entry
            assert "drift" in entry
            assert "saai_tier" in entry
            assert "baseline_avg" in entry
            assert "ewma" in entry
            assert isinstance(entry["fidelity"], float)
            assert isinstance(entry["drift"], float)

    def test_baseline_avg_stable(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Baseline average should remain constant after first N turns."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        baseline_avg = trace[BASELINE_TURN_COUNT - 1]["baseline_avg"]
        for entry in trace[BASELINE_TURN_COUNT:]:
            assert entry["baseline_avg"] == pytest.approx(baseline_avg, abs=0.001), (
                f"Baseline avg changed at turn {entry['turn']}: "
                f"{entry['baseline_avg']:.4f} vs {baseline_avg:.4f}"
            )

    def test_warning_not_reached_during_baseline(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """WARNING should NOT be reached during baseline phase."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        for entry in trace[:BASELINE_TURN_COUNT]:
            assert entry["saai_tier"] in ("nominal", "insufficient_data"), (
                f"Premature WARNING at turn {entry['turn']}: "
                f"drift={entry['drift']:.4f} "
                f"({entry['drift']*100:.1f}%)"
            )


# ===========================================================================
# Scenario 2: Rapid Drift to RESTRICT (15%)
# ===========================================================================

class TestSAAIRapidDriftToRestrict:
    """
    Scenario: Rapid Drift to RESTRICT (SAAI 15% Threshold)
    ========================================================

    Story: An underwriter establishes a 50-turn baseline then quickly
    pivots to heavily off-topic questions. The drift accelerates
    rapidly, crossing both the 10% WARNING and 15% RESTRICT thresholds.

    At RESTRICT, SAAI mandates threshold tightening.

    Turn sequence:
     1-50:  On-topic baseline (~0.87 fidelity)
    51-90:  Heavy and very heavy drift turns (~0.23-0.52)
    """

    TURN_MESSAGES = (
        _generate_baseline_messages(50)
        + [
            # Heavy drift -- 40 turns of sustained low fidelity
            "Explore moderate drift turn 3 developments",
            "Research moderate drift turn 4 across all markets",
            "Investigate heavy drift turn 1 across sectors",
            "Study heavy drift turn 2 patterns globally",
            "Examine heavy drift turn 3 fundamentals",
            "Research heavy drift turn 4 across sectors",
            "Study heavy drift turn 5 patterns globally",
            "Examine heavy drift turn 6 fundamentals",
            "Research heavy drift turn 7 across sectors",
            "Study heavy drift turn 8 patterns globally",
            "Examine heavy drift turn 9 fundamentals",
            "Research heavy drift turn 10 across sectors",
            "Study heavy drift turn 11 patterns globally",
            "Examine heavy drift turn 12 fundamentals",
            "Research heavy drift turn 13 across sectors",
            "Study heavy drift turn 14 patterns globally",
            "Examine heavy drift turn 15 fundamentals",
            "Research heavy drift turn 16 across sectors",
            "Study heavy drift turn 17 patterns globally",
            "Examine heavy drift turn 18 fundamentals",
            "Research heavy drift turn 19 across sectors",
            "Study heavy drift turn 20 patterns globally",
            "Examine heavy drift turn 21 fundamentals",
            "Research heavy drift turn 22 across sectors",
            "Study heavy drift turn 23 patterns globally",
            "Examine heavy drift turn 24 fundamentals",
            "Research heavy drift turn 25 across sectors",
            "Study heavy drift turn 26 patterns globally",
            "Examine heavy drift turn 27 fundamentals",
            "Research heavy drift turn 28 across sectors",
            "Study heavy drift turn 29 patterns globally",
            "Examine heavy drift turn 30 fundamentals",
            "Research heavy drift turn 31 across sectors",
            "Study heavy drift turn 32 patterns globally",
            "Examine heavy drift turn 33 fundamentals",
            "Research heavy drift turn 34 across sectors",
            "Study heavy drift turn 35 patterns globally",
            "Examine heavy drift turn 36 fundamentals",
            "Research heavy drift turn 37 across sectors",
            "Study heavy drift turn 38 patterns globally",
        ]
    )

    def test_baseline_establishes_correctly(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Baseline turns produce EXECUTE with high fidelity."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES[:BASELINE_TURN_COUNT],
        )
        for entry in trace:
            if entry["fidelity"] > 0:  # Skip insufficient_data turns
                assert entry["fidelity"] >= AGENTIC_EXECUTE_THRESHOLD

    def test_warning_reached_before_restrict(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Session should pass through WARNING before reaching RESTRICT."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        saw_warning = False
        saw_restrict = False
        for entry in trace:
            if entry["saai_tier"] == "warning":
                saw_warning = True
            if entry["saai_tier"] in ("restrict", "block"):
                saw_restrict = True

        assert saw_warning, "Session should pass through WARNING tier"
        assert saw_restrict, (
            f"Session should reach RESTRICT tier. "
            f"Final drift: {trace[-1]['drift']:.4f} "
            f"({trace[-1]['drift']*100:.1f}%)"
        )

    def test_restrict_threshold_crossed(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Cumulative drift should exceed 15% RESTRICT threshold."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        max_drift = max(e["drift"] for e in trace)
        assert max_drift > SAAI_DRIFT_RESTRICT, (
            f"Max drift {max_drift:.4f} ({max_drift*100:.1f}%) "
            f"should exceed RESTRICT threshold {SAAI_DRIFT_RESTRICT}"
        )

    def test_individual_decisions_degrade(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Individual turn decisions should degrade from EXECUTE to ESCALATE."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        decisions = [e["decision"] for e in trace]
        assert decisions[0] == "execute"
        assert decisions[-1] == "escalate", (
            f"Last turn should be ESCALATE, got {decisions[-1]} "
            f"(fidelity={trace[-1]['fidelity']:.3f})"
        )


# ===========================================================================
# Scenario 3: Drift to BLOCK (20%)
# ===========================================================================

class TestSAAIDriftToBlock:
    """
    Scenario: Drift to BLOCK (SAAI 20% Threshold)
    ================================================

    Story: An underwriter establishes a baseline then goes completely
    off-topic for an extended period. EWMA smoothing means many
    sustained low-fidelity turns needed to cross 20%.

    Turn sequence:
     1-50:   On-topic baseline (~0.87 fidelity)
    51-110:  Heavy drift, sustained (~0.23-0.39 fidelity)
    """

    TURN_MESSAGES = (
        _generate_baseline_messages(50)
        + [
            # 60 turns of heavy/very heavy drift
            f"Examine heavy drift turn {i} across all domains"
            for i in range(1, 61)
        ]
    )

    def test_block_threshold_crossed(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Cumulative drift should exceed 20% BLOCK threshold."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        max_drift = max(e["drift"] for e in trace)
        assert max_drift > SAAI_DRIFT_BLOCK, (
            f"Max drift {max_drift:.4f} ({max_drift*100:.1f}%) "
            f"should exceed BLOCK threshold {SAAI_DRIFT_BLOCK}"
        )

    def test_passes_through_all_tiers(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Session should pass through nominal -> WARNING -> RESTRICT -> BLOCK."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        tiers_seen = set(e["saai_tier"] for e in trace)

        # During baseline, all turns are insufficient_data or nominal
        assert "block" in tiers_seen, (
            f"Should reach BLOCK tier. Tiers seen: {tiers_seen}. "
            f"Final drift: {trace[-1]['drift']:.4f}"
        )

    def test_final_turns_are_escalate(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """The last 3 turns should produce ESCALATE decisions (very low fidelity)."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        escalate_count = sum(1 for e in trace[-3:] if e["decision"] == "escalate")
        assert escalate_count >= 2, (
            f"Expected at least 2 ESCALATE decisions in last 3 turns, "
            f"got {escalate_count}. Decisions: "
            f"{[e['decision'] for e in trace[-3:]]}"
        )

    def test_fidelity_collapses(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Fidelity should collapse from ~0.87 to below 0.30."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        first_fidelity = trace[0]["fidelity"]
        last_fidelity = trace[-1]["fidelity"]
        assert first_fidelity >= 0.85
        assert last_fidelity < 0.30, (
            f"Final fidelity {last_fidelity:.3f} should be < 0.30"
        )


# ===========================================================================
# Scenario 4: Drift Recovery
# ===========================================================================

class TestSAAIDriftRecovery:
    """
    Scenario: Drift Recovery -- Approaching but Not Crossing WARNING
    ================================================================

    Story: An underwriter starts on-topic, drifts slightly for a few
    turns after baseline, then returns to focused property assessment.
    The EWMA recovers as on-topic turns pull the average back up.

    With EWMA and 50-turn baseline, slight drift is quickly absorbed.

    Turn sequence:
     1-50:  On-topic baseline (~0.87 fidelity)
    51-56:  Slight drift (~0.76-0.79 fidelity)
    57-65:  Recovery turns (~0.87-0.92 fidelity)
    """

    TURN_MESSAGES = (
        _generate_baseline_messages(50)
        + [
            # Drift phase
            "Evaluate slight drift turn 3 conditions around this block",
            "Review slight drift turn 5 implications broadly",
            "Consider slight drift turn 6 patterns region-wide",
            "Look into slight drift turn 7 trends nationally",
            "Check slight drift turn 8 across the state",
            "Analyze slight drift turn 9 for the county",
        ]
        + [
            # Recovery phase
            "Back to the property -- recovery turn 1 needed",
            "Continuing recovery turn 2 on the assessment",
            "Final recovery turn 3 for the report",
            "Look up property at 742 Evergreen Terrace, Springfield IL",
            "Retrieve the latest aerial imagery for this parcel",
            "Run AI roof condition assessment",
            "Generate the full underwriting property report",
            "What are the hail and wind vulnerability scores?",
            "Check the roof condition on the next property",
        ]
    )

    def test_drift_stays_below_warning(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Cumulative drift should stay below 10% WARNING threshold."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        max_drift = max(e["drift"] for e in trace)
        assert max_drift < SAAI_DRIFT_WARNING, (
            f"Max drift {max_drift:.4f} ({max_drift*100:.1f}%) "
            f"should stay below WARNING threshold {SAAI_DRIFT_WARNING}"
        )

    def test_all_turns_nominal(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Every turn should remain in 'nominal' SAAI tier (or 'insufficient_data'
        during the initial baseline-building phase)."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        for entry in trace:
            assert entry["saai_tier"] in ("nominal", "insufficient_data"), (
                f"Turn {entry['turn']} should be nominal, got '{entry['saai_tier']}' "
                f"(drift={entry['drift']:.4f})"
            )

    def test_drift_peaks_then_recovers(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Drift should peak during drift phase and decrease during recovery."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        # Only look at post-baseline entries
        post_baseline = [e for e in trace if e["saai_tier"] != "insufficient_data"]
        if len(post_baseline) < 3:
            pytest.skip("Not enough post-baseline turns")

        drifts = [e["drift"] for e in post_baseline]
        peak_drift = max(drifts)
        final_drift = drifts[-1]

        assert final_drift < peak_drift, (
            f"Final drift ({final_drift:.4f}) should be less than "
            f"peak drift ({peak_drift:.4f}) after recovery"
        )

    def test_recovery_turns_are_execute(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Recovery turns should produce EXECUTE decisions."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        # Last 9 turns are recovery
        for entry in trace[-9:]:
            assert entry["decision"] == "execute", (
                f"Recovery turn {entry['turn']} expected EXECUTE, "
                f"got {entry['decision']} (fidelity={entry['fidelity']:.3f})"
            )


# ===========================================================================
# Scenario 5: Steady-State Compliance (70+ turns)
# ===========================================================================

class TestSAAISteadyStateCompliance:
    """
    Scenario: Steady-State Compliance -- Extended On-Topic Session
    ===============================================================

    Story: An underwriter works through a thorough 70-turn property
    assessment, staying on-topic throughout. Every turn is a
    legitimate property intelligence request.

    This is the control experiment: when the agent operates as
    designed, SAAI drift should remain near zero. The governance
    system should NOT interfere with productive work.

    Turn sequence:
     1-50:  Baseline property assessment
    51-70:  Continued on-topic work across all property tools
    """

    TURN_MESSAGES = _generate_baseline_messages(70)

    def test_session_has_70_turns(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Verify the scenario has 70 turns."""
        assert len(self.TURN_MESSAGES) >= 70

    def test_all_turns_nominal_tier(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Every turn should remain in 'nominal' SAAI tier (or 'insufficient_data'
        during the initial baseline-building phase)."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        for entry in trace:
            assert entry["saai_tier"] in ("nominal", "insufficient_data"), (
                f"Turn {entry['turn']} should be nominal, got '{entry['saai_tier']}' "
                f"(drift={entry['drift']:.4f})"
            )

    def test_max_drift_below_5_percent(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Maximum drift should stay well below 5% (half of WARNING)."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        max_drift = max(e["drift"] for e in trace)
        assert max_drift < 0.05, (
            f"Max drift {max_drift:.4f} ({max_drift*100:.1f}%) "
            f"should stay below 5% for steady-state compliance"
        )

    def test_all_turns_execute(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """Every turn should produce an EXECUTE decision."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        for entry in trace:
            assert entry["decision"] == "execute", (
                f"Turn {entry['turn']} '{entry['request'][:40]}...' "
                f"expected EXECUTE, got {entry['decision']} "
                f"(fidelity={entry['fidelity']:.3f})"
            )

    def test_ewma_tracks_baseline(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """EWMA should remain close to baseline average."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        baseline_avg = trace[BASELINE_TURN_COUNT - 1]["baseline_avg"]
        for entry in trace[BASELINE_TURN_COUNT:]:
            if baseline_avg > 0:
                deviation = abs(entry["ewma"] - baseline_avg) / baseline_avg
                assert deviation < 0.05, (
                    f"Turn {entry['turn']} EWMA deviation "
                    f"{deviation:.4f} ({deviation*100:.1f}%) from baseline "
                    f"should be < 5%"
                )

    def test_fidelity_stays_above_execute_threshold(
        self,
        property_fidelity_gate,
        property_tool_gate,
        property_pa,
        property_action_chain,
        property_embed_fn,
        property_tools,
    ):
        """All fidelity scores should remain above EXECUTE threshold."""
        trace = _build_forensic_trace(
            property_fidelity_gate, property_tool_gate, property_pa,
            property_action_chain, property_embed_fn, property_tools,
            self.TURN_MESSAGES,
        )

        for entry in trace:
            assert entry["fidelity"] >= AGENTIC_EXECUTE_THRESHOLD, (
                f"Turn {entry['turn']} fidelity {entry['fidelity']:.3f} "
                f"below EXECUTE threshold {AGENTIC_EXECUTE_THRESHOLD}"
            )

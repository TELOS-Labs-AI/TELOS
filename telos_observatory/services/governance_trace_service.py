"""
Governance Trace Service - Trace Recording for TELOS Observatory
=================================================================

Extracted from BetaResponseManager to provide focused governance trace logging.

Handles:
- Fidelity calculation recording to governance trace
- Intervention recording with proportional control metrics
- SAAI framework cumulative drift block checking
"""

import logging
import streamlit as st
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Governance Trace Collector availability
try:
    from telos_core.governance_trace import (
        get_trace_collector,
        GovernanceTraceCollector,
    )
    from telos_core.evidence_schema import (
        InterventionLevel,
        PrivacyMode,
    )
    TRACE_COLLECTOR_AVAILABLE = True
except ImportError:
    TRACE_COLLECTOR_AVAILABLE = False


def record_fidelity_trace(
    manager,
    turn_number: int,
    raw_similarity: float,
    display_fidelity: float,
    baseline_hard_block: bool,
    in_basin: bool,
) -> Optional[Dict]:
    """
    Record fidelity calculation to governance trace and check SAAI drift block.

    Args:
        manager: BetaResponseManager instance
        turn_number: Current turn number
        raw_similarity: Raw cosine similarity
        display_fidelity: Display-normalized fidelity
        baseline_hard_block: Whether Layer 1 hard block was triggered
        in_basin: Whether user is within primacy basin

    Returns:
        Dict with SAAI block data if response is blocked, None otherwise
    """
    if not TRACE_COLLECTOR_AVAILABLE:
        return None

    try:
        session_id = st.session_state.get('session_id', f'beta_{id(manager)}')
        collector = get_trace_collector(session_id=session_id)

        # Get previous fidelity for delta calculation
        previous_fidelity = None
        if hasattr(manager, 'state_manager') and manager.state_manager:
            turns = getattr(manager.state_manager.state, 'turns', [])
            if turns:
                prev_turn = turns[-1] if len(turns) > 0 else None
                if prev_turn:
                    previous_fidelity = prev_turn.get('user_fidelity')

        # Record fidelity calculation
        collector.record_fidelity(
            turn_number=len(manager.state_manager.state.turns) + 1 if hasattr(manager, 'state_manager') else 1,
            raw_similarity=raw_similarity,
            normalized_fidelity=display_fidelity,
            layer1_hard_block=baseline_hard_block,
            layer2_outside_basin=not in_basin,
            distance_from_pa=1.0 - raw_similarity,
            in_basin=in_basin,
            previous_fidelity=previous_fidelity,
        )
        logger.debug("Fidelity calculation recorded to governance trace")

        # SAAI FRAMEWORK: Check for cumulative drift BLOCK
        if collector.is_response_blocked():
            saai_status = collector.get_saai_status()
            drift_pct = saai_status['drift']['percentage'] or "N/A"
            logger.warning(
                f"SAAI DRIFT BLOCK: Cumulative drift {drift_pct} exceeds 20%. "
                f"Responses blocked until operator acknowledgment."
            )
            return {
                'saai_blocked': True,
                'saai_drift_level': saai_status['drift']['level'],
                'saai_drift_magnitude': saai_status['drift']['magnitude'],
                'drift_pct': drift_pct,
            }

    except Exception as e:
        logger.debug(f"Governance trace logging skipped: {e}")

    return None


def record_intervention_trace(
    manager,
    user_fidelity: float,
    display_fidelity: float,
    zone: str,
    baseline_hard_block: bool,
    in_basin: bool,
):
    """
    Record intervention to governance trace with proportional control metrics.

    Args:
        manager: BetaResponseManager instance
        user_fidelity: Raw user fidelity score
        display_fidelity: Display-normalized fidelity
        zone: Fidelity zone (YELLOW, ORANGE, RED)
        baseline_hard_block: Whether Layer 1 hard block was triggered
        in_basin: Whether user is within primacy basin
    """
    if not TRACE_COLLECTOR_AVAILABLE:
        return

    try:
        session_id = st.session_state.get('session_id', f'beta_{id(manager)}')
        collector = get_trace_collector(session_id=session_id)

        # Map zone to InterventionLevel
        level_map = {
            "YELLOW": InterventionLevel.CORRECT,
            "ORANGE": InterventionLevel.INTERVENE,
            "RED": InterventionLevel.ESCALATE,
        }
        if baseline_hard_block:
            intervention_level = InterventionLevel.HARD_BLOCK
            trigger_reason = "hard_block"
        else:
            intervention_level = level_map.get(zone, InterventionLevel.INTERVENE)
            trigger_reason = "basin_exit" if not in_basin else "drift_detected"

        # Proportional control calculation
        K_ATTRACTOR = 1.5
        error_signal = 1.0 - user_fidelity
        controller_strength = min(K_ATTRACTOR * error_signal, 1.0)

        # Intervention state mapping
        if error_signal < 0.30:
            intervention_state = "MONITOR"
        elif error_signal < 0.50:
            intervention_state = "CORRECT"
        elif error_signal < 0.67:
            intervention_state = "INTERVENE"
        else:
            intervention_state = "ESCALATE"

        # Semantic band mapping
        if controller_strength < 0.45:
            semantic_band = "minimal"
        elif controller_strength < 0.60:
            semantic_band = "light"
        elif controller_strength < 0.75:
            semantic_band = "moderate"
        elif controller_strength < 0.85:
            semantic_band = "firm"
        else:
            semantic_band = "strong"

        logger.info(f"Proportional Controller: e={error_signal:.3f}, "
                   f"strength={controller_strength:.3f}, state={intervention_state}, "
                   f"band={semantic_band}")

        collector.record_intervention(
            turn_number=len(manager.state_manager.state.turns) + 1 if hasattr(manager, 'state_manager') else 1,
            intervention_level=intervention_level,
            trigger_reason=trigger_reason,
            fidelity_at_trigger=display_fidelity,
            controller_strength=controller_strength,
            semantic_band=semantic_band,
            action_taken="steward_redirect",
        )
        logger.debug(f"Intervention recorded: {intervention_level.value} at fidelity {user_fidelity:.3f}")
    except Exception as e:
        logger.debug(f"Governance trace intervention logging skipped: {e}")

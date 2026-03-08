"""
Action Chain — Semantic Continuity Index (SCI)
==============================================

Tracks semantic continuity across multi-step agent action chains.

The SCI measures whether consecutive actions in an agent's execution
remain semantically aligned. If an agent drifts in a multi-step plan,
the SCI detects the divergence even if individual steps pass fidelity
checks against the PA.

Key concept: Inherited fidelity with decay. If step N has high fidelity
and step N+1 is semantically continuous with step N, then step N+1
inherits fidelity (with decay). This prevents re-measuring against the
PA at every step, reducing latency while maintaining governance.

First Principles
-----------------
1. **Trajectory vs. Position**: Per-step PA checks measure position
   (is this step aligned?). SCI measures trajectory (is this sequence
   drifting?). A research agent that goes search → Wikipedia → summarize
   → football scores has each step at moderate individual alignment, but
   the trajectory reveals drift that position-only checks miss. SCI
   tracks the direction of motion in embedding space, not just the
   current location.

2. **Inherited Fidelity with Decay** (momentum model): A well-started
   chain carries governance "momentum" — each aligned step inherits
   approval from the previous step with 0.90 decay. This is analogous
   to a production line where in-spec parts move forward without
   re-inspection unless a quality signal triggers (SPC principle).
   The decay factor (0.90) ensures momentum degrades — a long chain
   cannot coast on early fidelity indefinitely.

3. **Chain Break as Drift Signal**: When SCI drops below the continuity
   threshold (0.30), inheritance stops and the step must justify itself
   directly against the PA. This is the "detect" half of "Detect and
   Direct" — the chain break is the out-of-control signal that triggers
   governance intervention. The threshold at 0.30 is intentionally low
   to allow topic evolution within a task while catching genuine drift.

4. **NIST AI 600-1** (Generative AI Profile, 2024 — MEASURE 2.5): The SCI
   provides a continuous metric for multi-step agent behavior — exactly
   the type of ongoing measurement NIST 600-1 requires for GenAI systems
   that perform sequential reasoning or multi-step tool chains. Each SCI
   value is a documented measurement of trajectory coherence.

5. **OWASP LLM Top 10** (2025 — LLM08, Excessive Agency): Chain break
   detection (SCI < 0.30) prevents an agent from accumulating unbounded
   action sequences that drift from original authorization. The inheritance
   decay (0.90) ensures governance re-validation as chains extend — a long
   chain cannot coast on early fidelity indefinitely. This directly limits
   the "scope creep" that LLM08 identifies as an excessive agency risk.

6. **NIST AI RMF 100** (MANAGE 2.2): Chain continuity monitoring
   implements MANAGE 2.2's risk response mechanisms — chain breaks trigger
   corrective action (re-evaluation against PA), while continuous chains
   inherit approval with decay (proportional monitoring).

Extracted from telos_langgraph state_schema.py SCI calculation.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# SCI thresholds — calibrated to allow natural topic evolution while catching
# genuine drift. The 0.30 threshold means consecutive steps can diverge
# significantly (cos < 0.30 = nearly orthogonal) before inheritance breaks.
# Data Scientist review (research_log.md Entry 7) recommends raising to
# 0.45-0.50 for production — pending empirical validation.
SCI_CONTINUITY_THRESHOLD = 0.30  # Minimum continuity for fidelity inheritance
SCI_DECAY_FACTOR = 0.90          # Decay per step — 10% fidelity loss per step


def calculate_semantic_continuity(
    current_embedding: np.ndarray,
    previous_embedding: Optional[np.ndarray],
    previous_fidelity: float = 1.0,
) -> Tuple[float, float]:
    """
    Calculate Semantic Continuity Index for action chains.

    Measures cosine similarity between consecutive action embeddings.
    If continuity is above threshold, the current step inherits fidelity
    from the previous step (with decay), avoiding a full PA re-check.

    Args:
        current_embedding: Embedding of the current action/step
        previous_embedding: Embedding of the previous action/step (None for first step)
        previous_fidelity: Fidelity score of the previous step

    Returns:
        (continuity_score, inherited_fidelity)
        - continuity_score: Cosine similarity between consecutive actions (0-1)
        - inherited_fidelity: Inherited fidelity with decay, or 0.0 if discontinuous
    """
    if previous_embedding is None:
        return 0.0, 0.0

    # Cosine similarity between consecutive actions
    norm_current = np.linalg.norm(current_embedding)
    norm_previous = np.linalg.norm(previous_embedding)

    if norm_current == 0 or norm_previous == 0:
        return 0.0, 0.0

    continuity = np.dot(current_embedding, previous_embedding) / (
        norm_current * norm_previous
    )

    # If continuity is high enough, inherit fidelity with decay
    if continuity >= SCI_CONTINUITY_THRESHOLD:
        inherited_fidelity = previous_fidelity * SCI_DECAY_FACTOR
        return float(continuity), inherited_fidelity
    else:
        return float(continuity), 0.0  # No inheritance, use direct measurement


@dataclass
class ActionStep:
    """A single step in an action chain."""
    step_index: int
    action_text: str
    embedding: np.ndarray
    direct_fidelity: float          # Fidelity measured against PA
    continuity_score: float = 0.0   # SCI with previous step (0.0 = first step / no chain)
    inherited_fidelity: float = 0.0 # Inherited fidelity (with decay, 0.0 = no inheritance)
    effective_fidelity: float = 0.0 # max(direct, inherited) used for governance


@dataclass
class ActionChain:
    """
    Tracks action embeddings across steps with SCI calculation.

    Maintains a chain of action steps with their embeddings,
    calculates semantic continuity between consecutive steps,
    and manages inherited fidelity with decay.
    """
    steps: List[ActionStep] = field(default_factory=list)
    continuity_threshold: float = SCI_CONTINUITY_THRESHOLD
    decay_factor: float = SCI_DECAY_FACTOR
    continuity_window_size: int = 3
    continuity_min_pass_ratio: float = 0.67

    @property
    def length(self) -> int:
        """Number of steps in the chain."""
        return len(self.steps)

    @property
    def current_step(self) -> Optional[ActionStep]:
        """Most recent step in the chain."""
        return self.steps[-1] if self.steps else None

    @property
    def average_continuity(self) -> float:
        """Average SCI across all consecutive step pairs."""
        if len(self.steps) < 2:
            return 1.0
        scores = [s.continuity_score for s in self.steps[1:]]
        return sum(scores) / len(scores)

    @property
    def min_continuity(self) -> float:
        """Minimum SCI in the chain (weakest link)."""
        if len(self.steps) < 2:
            return 1.0
        return min(s.continuity_score for s in self.steps[1:])

    def add_step(
        self,
        action_text: str,
        embedding: np.ndarray,
        direct_fidelity: float,
    ) -> ActionStep:
        """
        Add a new step to the action chain.

        Calculates SCI with the previous step and determines
        inherited fidelity.

        Args:
            action_text: Text description of the action
            embedding: Embedding vector for the action
            direct_fidelity: Fidelity measured directly against the PA

        Returns:
            The new ActionStep with SCI and inherited fidelity computed
        """
        # Get previous step info
        previous_embedding = self.steps[-1].embedding if self.steps else None
        previous_fidelity = self.steps[-1].effective_fidelity if self.steps else 1.0

        # Calculate SCI using instance thresholds
        if previous_embedding is None:
            continuity_score, inherited_fidelity = 0.0, 0.0
        else:
            norm_current = np.linalg.norm(embedding)
            norm_previous = np.linalg.norm(previous_embedding)
            if norm_current == 0 or norm_previous == 0:
                continuity_score, inherited_fidelity = 0.0, 0.0
            else:
                continuity_score = float(
                    np.dot(embedding, previous_embedding) / (norm_current * norm_previous)
                )
                if continuity_score >= self.continuity_threshold:
                    inherited_fidelity = previous_fidelity * self.decay_factor
                else:
                    inherited_fidelity = 0.0

        # Effective fidelity is the max of direct and inherited
        # This means if the PA check passes, we use it; if inherited
        # fidelity is higher (early in chain), we use that instead
        effective_fidelity = max(direct_fidelity, inherited_fidelity)

        step = ActionStep(
            step_index=len(self.steps),
            action_text=action_text,
            embedding=embedding,
            direct_fidelity=direct_fidelity,
            continuity_score=continuity_score,
            inherited_fidelity=inherited_fidelity,
            effective_fidelity=effective_fidelity,
        )

        self.steps.append(step)

        logger.debug(
            f"Action chain step {step.step_index}: "
            f"SCI={continuity_score:.3f}, "
            f"direct={direct_fidelity:.3f}, "
            f"inherited={inherited_fidelity:.3f}, "
            f"effective={effective_fidelity:.3f}"
        )

        return step

    def is_continuous(self) -> bool:
        """Check if the chain maintains semantic continuity over a recent window.

        Evaluates only the last N transitions (continuity_window_size) and
        requires at least continuity_min_pass_ratio of them to pass the
        threshold. This prevents a single ancient low-similarity transition
        from poisoning the entire chain for all subsequent steps.
        """
        if len(self.steps) < 2:
            return True
        # Window over the most recent transitions only
        window = self.steps[1:][-self.continuity_window_size:]
        passing = sum(
            1 for s in window
            if s.continuity_score >= self.continuity_threshold
        )
        return passing >= len(window) * self.continuity_min_pass_ratio

    def reset(self) -> None:
        """Clear the action chain."""
        self.steps.clear()

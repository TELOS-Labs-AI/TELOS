"""
Mathematical foundation for primacy attractor dynamics.

Implements:

- Primacy attractor geometry (center, basin)
- Lyapunov stability functions
- Telic fidelity metrics (hard/soft)
- Basin membership testing

Aligned with TELOS Mathematical Foundations document.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import numpy as np


@dataclass
class MathematicalState:
    """
    State vector in embedding space at a specific turn.

    Attributes:
        embedding: High-dimensional vector representation
        turn_number: Turn index in session
        timestamp: Unix timestamp
        text_content: Optional raw text for debugging
    """
    embedding: np.ndarray
    turn_number: int
    timestamp: float
    text_content: Optional[str] = None


class PrimacyAttractorMath:
    """
    Mathematical representation of primacy attractor.

    Implements formulas from Mathematical Foundations:
    - Attractor center: a_hat = (t*p + (1-t)*s) / ||t*p + (1-t)*s||
    - Basin radius: r = 2/rho where rho = 1 - t
    - Lyapunov function: V(x) = ||x - a_hat||^2
    """

    def __init__(
        self,
        purpose_vector: np.ndarray,
        scope_vector: np.ndarray,
        privacy_level: float = 0.8,
        constraint_tolerance: float = 0.2,
        task_priority: float = 0.7
    ):
        """
        Args:
            purpose_vector: Embedded purpose statements
            scope_vector: Embedded scope boundaries
            privacy_level: Privacy enforcement strength [0,1]
            constraint_tolerance: Boundary flexibility [0,1]
                0.0 = zero tolerance (strict enforcement, small basin)
                1.0 = maximum tolerance (permissive enforcement, large basin)
            task_priority: Task focus weight [0,1]
        """
        self.purpose_vector = purpose_vector
        self.scope_vector = scope_vector
        self.privacy_level = privacy_level
        self.constraint_tolerance = float(constraint_tolerance)
        self.task_priority = task_priority

        # Derive constraint rigidity as inverse of tolerance (for internal calculations)
        self.constraint_rigidity = 1.0 - self.constraint_tolerance

        # Compute attractor center using tolerance-weighted formula from Foundations
        # a_hat = (t*p + (1-t)*s) / ||t*p + (1-t)*s||
        center_unnormalized = (
            self.constraint_tolerance * purpose_vector +
            (1.0 - self.constraint_tolerance) * scope_vector
        )
        center_norm = np.linalg.norm(center_unnormalized)
        self.attractor_center = (
            center_unnormalized / center_norm if center_norm > 0 else center_unnormalized
        )

        # Basin radius using inverse formula from Foundations: r = 1.0/rho
        # CALIBRATION: Testing 1.0 as middle ground between 2.0 (too loose) and 0.5 (too tight)
        # This makes basins 2x smaller than original, enabling meaningful governance
        # At t=0.9 (permissive), rho=0.25 gives r=4.0 (manageable)
        # At t=0.05 (strict), rho=0.95 gives r=1.053 (should catch real drift, allow on-topic)
        rigidity_floored = max(self.constraint_rigidity, 0.25)
        self.basin_radius = 1.0 / rigidity_floored

        # Lyapunov coefficient scales with rigidity (not used in V(x) directly,
        # but kept for compatibility if referenced elsewhere)
        self.lyapunov_coefficient = self.constraint_rigidity * 2.0

    def compute_lyapunov_function(self, state: MathematicalState) -> float:
        """
        Compute Lyapunov function V(x) = ||x - a_hat||^2

        Measures "energy" of state relative to attractor.
        Lower V -> closer to attractor -> better governance.

        Per Foundations: delta_V < 0 indicates convergence (Primacy Orbit).

        Args:
            state: Current system state

        Returns:
            Lyapunov value (non-negative)
        """
        distance = np.linalg.norm(state.embedding - self.attractor_center)
        return distance ** 2

    def compute_basin_membership(self, state: MathematicalState) -> bool:
        """
        Check if state is within basin of attraction.

        Per Foundations: Part of Primacy Orbit stability check.

        Args:
            state: Current system state

        Returns:
            True if within basin, False otherwise
        """
        distance = np.linalg.norm(state.embedding - self.attractor_center)
        return distance <= self.basin_radius

    def compute_error_signal(self, state: MathematicalState) -> float:
        """
        Compute normalized distance from attractor center.

        Used as input to intervention controller (Primacy Gravity).
        Normalized to [0,1] for compatibility with epsilon thresholds.

        Args:
            state: Current system state

        Returns:
            Error signal in [0, 1], where 1.0 = at basin boundary
        """
        distance = np.linalg.norm(state.embedding - self.attractor_center)
        # Normalize to basin radius and cap at 1.0 for controller compatibility
        return min(distance / self.basin_radius, 1.0)


class TelicFidelityCalculator:
    """
    Computes telic fidelity scores for session trajectories.

    Implements Primacy Fidelity metrics from Foundations:
    - Hard fidelity: Fraction of states in basin
    - Soft fidelity: Average proximity to attractor
    """

    def compute_hard_fidelity(
        self,
        states: List[MathematicalState],
        attractor: PrimacyAttractorMath
    ) -> float:
        """
        Hard fidelity = fraction of states within basin.

        Per Foundations: F = (1/T) sum 1[x_t in B(A)]

        Args:
            states: Session trajectory
            attractor: Primacy attractor

        Returns:
            Fidelity score in [0, 1]
        """
        if not states:
            return 0.0

        in_basin_count = sum(
            1 for s in states
            if attractor.compute_basin_membership(s)
        )

        return in_basin_count / len(states)

    def compute_soft_fidelity(
        self,
        states: List[MathematicalState],
        attractor: PrimacyAttractorMath
    ) -> float:
        """
        Soft fidelity = 1 / (1 + avg_distance).

        Continuous measure that rewards proximity.
        Approximates exponential soft basin from Foundations.

        Args:
            states: Session trajectory
            attractor: Primacy attractor

        Returns:
            Fidelity score in (0, 1]
        """
        if not states:
            return 0.0

        distances = [
            np.linalg.norm(s.embedding - attractor.attractor_center)
            for s in states
        ]

        avg_distance = np.mean(distances)
        return 1.0 / (1.0 + avg_distance)

    def compute_trajectory_stability(
        self,
        states: List[MathematicalState],
        attractor: PrimacyAttractorMath
    ) -> float:
        """
        Check if Lyapunov is decreasing (stable trajectory).

        Per Foundations: delta_V < 0 indicates Primacy Orbit convergence.
        Returns fraction of turns where V decreases.

        Args:
            states: Session trajectory
            attractor: Primacy attractor

        Returns:
            Stability score in [0, 1]
        """
        if len(states) < 2:
            return 1.0

        V_values = [
            attractor.compute_lyapunov_function(s)
            for s in states
        ]

        decreasing_count = sum(
            1 for i in range(1, len(V_values))
            if V_values[i] < V_values[i-1]
        )

        return decreasing_count / (len(V_values) - 1)

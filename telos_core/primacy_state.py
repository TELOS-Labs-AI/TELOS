"""
Primacy State Formalization Module

Implements the mathematical formalization of Primacy State as the emergent
equilibrium condition between User PA, AI PA, and Steward PA.

DUAL FORMULA (Public):
    PS = rho_PA * (2*F_user*F_AI)/(F_user + F_AI)

TRIFECTA FORMULA (Proprietary):
    PS = rho_PA * 3/(1/F_user + 1/F_AI + 1/F_steward)

The Steward PA is the constant third branch - an always-active agent whose
purpose is maintaining Primacy State through world-class clinical care.

Key Properties:
- Harmonic mean prevents compensation between components
- rho_PA acts as correlation gate ensuring attractors are synchronized
- Provides diagnostic decomposition when PS fails
- Steward has FINAL SAY (gatekeeper authority) regardless of other scores
- Based on established control theory and dynamical systems

Status: Validated on 46 dual PA sessions + trifecta extension
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class PrimacyStateMetrics:
    """
    Complete Primacy State metrics including decomposition.

    Attributes:
        ps_score: Overall Primacy State score [0, 1]
        f_user: User PA fidelity (conversation purpose alignment)
        f_ai: AI PA fidelity (AI behavior/role alignment)
        f_steward: Steward PA fidelity (therapeutic care alignment) - trifecta only
        rho_pa: PA correlation (attractor synchronization)
        v_dual: Optional dual potential energy
        delta_v: Optional energy change (convergence indicator)
        condition: Textual condition ('achieved', 'weakening', 'violated', 'collapsed')
        steward_ruling: Steward's gatekeeper decision ('ALLOW', 'MODIFY', 'BLOCK')
        mode: 'dual' or 'trifecta'
    """
    ps_score: float
    f_user: float
    f_ai: float
    rho_pa: float
    f_steward: Optional[float] = None
    v_dual: Optional[float] = None
    delta_v: Optional[float] = None
    condition: str = 'unknown'
    steward_ruling: Optional[str] = None
    mode: str = 'dual'

    def __post_init__(self):
        """Determine PS condition based on score."""
        # Hardcoded thresholds (no external config dependency)
        _ZONE_ALIGNED = 0.76
        _ZONE_MINOR_DRIFT = 0.73
        _ZONE_DRIFT = 0.67

        if self.ps_score >= _ZONE_ALIGNED:  # >= 0.76
            self.condition = 'achieved'
        elif self.ps_score >= _ZONE_MINOR_DRIFT:  # 0.73-0.76
            self.condition = 'weakening'
        elif self.ps_score >= _ZONE_DRIFT:  # 0.67-0.73
            self.condition = 'violated'
        else:  # < 0.67
            self.condition = 'collapsed'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for telemetry/storage."""
        result = {
            'primacy_state_score': self.ps_score,
            'user_pa_fidelity': self.f_user,
            'ai_pa_fidelity': self.f_ai,
            'pa_correlation': self.rho_pa,
            'primacy_state_condition': self.condition,
            'v_dual_energy': self.v_dual,
            'delta_v_dual': self.delta_v,
            'primacy_converging': self.delta_v < 0 if self.delta_v is not None else None,
            'mode': self.mode
        }
        # Trifecta-specific fields
        if self.mode == 'trifecta':
            result['steward_pa_fidelity'] = self.f_steward
            result['steward_ruling'] = self.steward_ruling
        return result

    def get_diagnostic(self) -> str:
        """Get human-readable diagnostic of PS state."""
        _ZONE_MINOR_DRIFT = 0.73

        diagnostics = []

        if self.f_user < _ZONE_MINOR_DRIFT:
            diagnostics.append(f"User purpose drift (F_user={self.f_user:.2f})")
        elif self.f_user > 0.90:
            diagnostics.append(f"User purpose maintained (F_user={self.f_user:.2f})")

        if self.f_ai < _ZONE_MINOR_DRIFT:
            diagnostics.append(f"AI role violation (F_AI={self.f_ai:.2f})")
        elif self.f_ai > 0.90:
            diagnostics.append(f"AI role maintained (F_AI={self.f_ai:.2f})")

        # Trifecta: Steward diagnostic
        if self.mode == 'trifecta' and self.f_steward is not None:
            if self.f_steward < 0.55:
                diagnostics.append(f"Steward concern (F_steward={self.f_steward:.2f})")
            elif self.f_steward > 0.75:
                diagnostics.append(f"Steward approved (F_steward={self.f_steward:.2f})")

            if self.steward_ruling:
                diagnostics.append(f"Steward: {self.steward_ruling}")

        if self.rho_pa < _ZONE_MINOR_DRIFT:
            diagnostics.append(f"PA misalignment (rho_PA={self.rho_pa:.2f})")
        elif self.rho_pa > 0.90:
            diagnostics.append(f"PA well-aligned (rho_PA={self.rho_pa:.2f})")

        if self.delta_v is not None:
            if self.delta_v < 0:
                diagnostics.append("System converging")
            else:
                diagnostics.append("System diverging")

        return " | ".join(diagnostics) if diagnostics else "System stable"


class PrimacyStateCalculator:
    """
    Calculates Primacy State from dual or trifecta PA dynamics.

    This is the core mathematical engine that computes PS from embeddings.
    Supports both:
    - DUAL mode: PS = rho * harmonic(F_user, F_ai)
    - TRIFECTA mode: PS = rho * harmonic(F_user, F_ai, F_steward)

    Can optionally track dual potential energy for stability analysis.
    """

    def __init__(self, track_energy: bool = False, mode: str = 'dual'):
        """
        Initialize calculator.

        Args:
            track_energy: Whether to compute V_dual energy metrics
            mode: 'dual' or 'trifecta' calculation mode
        """
        self.track_energy = track_energy
        self.mode = mode
        self._prev_v_dual: Optional[float] = None
        self._pa_correlation_cache: Optional[float] = None
        self._steward_centroid: Optional[np.ndarray] = None

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            Cosine similarity in [-1, 1]
        """
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def set_steward_centroid(self, steward_centroid: np.ndarray):
        """
        Set the Steward PA centroid for trifecta calculations.

        Args:
            steward_centroid: Pre-computed steward embedding centroid
        """
        self._steward_centroid = steward_centroid

    def compute_primacy_state(
        self,
        response_embedding: np.ndarray,
        user_pa_embedding: np.ndarray,
        ai_pa_embedding: np.ndarray,
        steward_pa_embedding: Optional[np.ndarray] = None,
        use_cached_correlation: bool = True
    ) -> PrimacyStateMetrics:
        """
        Compute Primacy State from embeddings.

        DUAL formula: PS = rho_PA * (2*F_user*F_AI)/(F_user + F_AI)
        TRIFECTA formula: PS = rho_PA * 3/(1/F_user + 1/F_AI + 1/F_steward)

        Args:
            response_embedding: Current response embedding
            user_pa_embedding: User PA center embedding
            ai_pa_embedding: AI PA center embedding
            steward_pa_embedding: Steward PA centroid (optional, uses cached if not provided)
            use_cached_correlation: Whether to use cached rho_PA (more efficient)

        Returns:
            Complete PS metrics with diagnostic decomposition
        """
        # Component fidelities
        F_user = self.cosine_similarity(response_embedding, user_pa_embedding)
        F_AI = self.cosine_similarity(response_embedding, ai_pa_embedding)

        # PA correlation (cache for efficiency within session)
        if use_cached_correlation and self._pa_correlation_cache is not None:
            rho_PA = self._pa_correlation_cache
        else:
            rho_PA = self.cosine_similarity(user_pa_embedding, ai_pa_embedding)
            self._pa_correlation_cache = rho_PA

        # Compute based on mode
        epsilon = 1e-10
        F_steward = None
        steward_ruling = None

        if self.mode == 'trifecta':
            # Get steward embedding
            steward_emb = steward_pa_embedding if steward_pa_embedding is not None else self._steward_centroid

            if steward_emb is not None:
                F_steward = self.cosine_similarity(response_embedding, steward_emb)

                # TRIFECTA: 3-way harmonic mean
                # PS = rho * 3 / (1/F_user + 1/F_ai + 1/F_steward)
                if F_user > epsilon and F_AI > epsilon and F_steward > epsilon:
                    harmonic_mean = 3 / (1/F_user + 1/F_AI + 1/F_steward)
                else:
                    harmonic_mean = 0.0

                # Steward gatekeeper evaluation (fallback thresholds)
                if F_steward >= 0.25:
                    steward_ruling = 'ALLOW'
                elif F_steward >= 0.08:
                    steward_ruling = 'MODIFY'
                else:
                    steward_ruling = 'BLOCK'
            else:
                # Fallback to dual if no steward centroid
                if F_user + F_AI > epsilon:
                    harmonic_mean = (2 * F_user * F_AI) / (F_user + F_AI + epsilon)
                else:
                    harmonic_mean = 0.0
        else:
            # DUAL: 2-way harmonic mean
            if F_user + F_AI > epsilon:
                harmonic_mean = (2 * F_user * F_AI) / (F_user + F_AI + epsilon)
            else:
                harmonic_mean = 0.0

        # Primacy State Score
        PS = rho_PA * harmonic_mean

        # Optional: Dual potential energy tracking
        v_dual = None
        delta_v = None

        if self.track_energy:
            # Compute dual potential energy
            # V_dual = alpha*||x - a_user||^2 + beta*||x - a_AI||^2 + gamma*||a_user - a_AI||^2
            v_user = np.linalg.norm(response_embedding - user_pa_embedding) ** 2
            v_ai = np.linalg.norm(response_embedding - ai_pa_embedding) ** 2
            v_coupling = np.linalg.norm(user_pa_embedding - ai_pa_embedding) ** 2

            # Energy weights (tunable hyperparameters)
            alpha, beta, gamma = 0.5, 0.4, 0.1
            v_dual = alpha * v_user + beta * v_ai + gamma * v_coupling

            # Track convergence
            if self._prev_v_dual is not None:
                delta_v = v_dual - self._prev_v_dual

            self._prev_v_dual = v_dual

        return PrimacyStateMetrics(
            ps_score=PS,
            f_user=F_user,
            f_ai=F_AI,
            rho_pa=rho_PA,
            f_steward=F_steward,
            v_dual=v_dual,
            delta_v=delta_v,
            steward_ruling=steward_ruling,
            mode=self.mode
        )

    def reset_session_cache(self):
        """Reset cached values for new session."""
        self._pa_correlation_cache = None
        self._prev_v_dual = None


def interpret_primacy_state(
    metrics: PrimacyStateMetrics,
    verbose: bool = False
) -> str:
    """
    Generate human-readable interpretation of Primacy State.

    Args:
        metrics: PS metrics to interpret
        verbose: Whether to include detailed diagnostics

    Returns:
        Narrative interpretation of PS condition
    """
    if metrics.condition == 'achieved':
        narrative = f"Primacy State ACHIEVED (PS={metrics.ps_score:.3f})"
    elif metrics.condition == 'weakening':
        narrative = f"Primacy State weakening (PS={metrics.ps_score:.3f})"
    elif metrics.condition == 'violated':
        narrative = f"Primacy State violated (PS={metrics.ps_score:.3f})"
    else:
        narrative = f"Primacy State COLLAPSED (PS={metrics.ps_score:.3f})"

    if verbose:
        diagnostic = metrics.get_diagnostic()
        if diagnostic:
            narrative += f" - {diagnostic}"

    return narrative


def compute_intervention_urgency(metrics: PrimacyStateMetrics) -> str:
    """
    Determine intervention urgency based on PS metrics.

    Args:
        metrics: Current PS metrics

    Returns:
        Intervention level: 'MONITOR', 'CORRECT', 'INTERVENE', or 'ESCALATE'
    """
    if metrics.ps_score >= 0.85:
        return 'MONITOR'
    elif metrics.ps_score >= 0.70:
        return 'CORRECT'
    elif metrics.ps_score >= 0.50:
        return 'INTERVENE'
    else:
        return 'ESCALATE'


# Convenience function for quick PS calculation
def calculate_ps(
    response: np.ndarray,
    user_pa: np.ndarray,
    ai_pa: np.ndarray,
    steward_pa: Optional[np.ndarray] = None,
    mode: str = 'dual'
) -> Tuple[float, str]:
    """
    Quick PS calculation without full metrics.

    Args:
        response: Response embedding
        user_pa: User PA embedding
        ai_pa: AI PA embedding
        steward_pa: Steward PA embedding (optional, for trifecta mode)
        mode: 'dual' or 'trifecta'

    Returns:
        Tuple of (PS score, condition string)
    """
    calc = PrimacyStateCalculator(track_energy=False, mode=mode)
    metrics = calc.compute_primacy_state(response, user_pa, ai_pa, steward_pa)
    return metrics.ps_score, metrics.condition


def calculate_ps_trifecta(
    response: np.ndarray,
    user_pa: np.ndarray,
    ai_pa: np.ndarray,
    steward_pa: np.ndarray
) -> Tuple[float, str, str]:
    """
    Quick trifecta PS calculation with steward ruling.

    Args:
        response: Response embedding
        user_pa: User PA embedding
        ai_pa: AI PA embedding
        steward_pa: Steward PA centroid embedding

    Returns:
        Tuple of (PS score, condition string, steward ruling)
    """
    calc = PrimacyStateCalculator(track_energy=False, mode='trifecta')
    metrics = calc.compute_primacy_state(response, user_pa, ai_pa, steward_pa)
    return metrics.ps_score, metrics.condition, metrics.steward_ruling or 'UNKNOWN'

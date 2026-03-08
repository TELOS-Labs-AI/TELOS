"""
Governance Threshold Configuration
====================================

Parameterized threshold configuration for the governance scoring pipeline.
Enables the Governance Configuration Optimizer to pass threshold overrides
through the scoring pipeline without monkey-patching constants.py.

Background: Constants in telos_core/constants.py are imported by value into
consuming modules (agentic_fidelity.py, fidelity_engine.py). Monkey-patching
the source module at runtime does NOT update the local copies. This dataclass
provides the clean alternative — pass thresholds explicitly.

Usage:
    # Default (matches current constants.py values)
    config = ThresholdConfig()

    # Custom thresholds for optimization
    config = ThresholdConfig(st_execute=0.50, weight_purpose=0.40)

    # Pass to scoring engine
    engine = AgenticFidelityEngine(embed_fn, pa, threshold_config=config)
"""
from dataclasses import dataclass, field
from typing import Dict, Optional

from telos_core.constants import (
    ST_AGENTIC_EXECUTE_THRESHOLD,
    ST_AGENTIC_CLARIFY_THRESHOLD,
    BOUNDARY_MARGIN_THRESHOLD as _DEFAULT_BOUNDARY_MARGIN,
    FIDELITY_GREEN,
    FIDELITY_YELLOW,
    FIDELITY_ORANGE,
    DEFAULT_MAX_REGENERATIONS,
)

# Import from agentic_fidelity module-level constants (avoiding circular import
# by importing the values we need directly from constants or hard-coding defaults
# that match the module constants in agentic_fidelity.py)
_DEFAULT_WEIGHT_PURPOSE = 0.35
_DEFAULT_WEIGHT_SCOPE = 0.20
_DEFAULT_WEIGHT_TOOL = 0.20
_DEFAULT_WEIGHT_CHAIN = 0.15
_DEFAULT_WEIGHT_BOUNDARY_PENALTY = 0.10
_DEFAULT_BOUNDARY_VIOLATION_THRESHOLD = 0.70
_DEFAULT_KEYWORD_BOOST = 0.15
_DEFAULT_KEYWORD_EMBEDDING_FLOOR = 0.40


@dataclass
class ThresholdConfig:
    """Parameterized governance thresholds for optimizer trials.

    All defaults match the current production values in constants.py and
    agentic_fidelity.py. When passed to AgenticFidelityEngine, these values
    override the module-level constants for that engine instance.

    Ordering invariants (enforced by validate()):
        - st_execute > st_clarify (with 0.05 min gap)
        - fidelity_green > fidelity_yellow > fidelity_orange (with 0.05 min gap)
        - All weights > 0 and positive weights sum to ~0.90
    """
    # Agentic decision thresholds (SentenceTransformer)
    st_execute: float = ST_AGENTIC_EXECUTE_THRESHOLD
    st_clarify: float = ST_AGENTIC_CLARIFY_THRESHOLD

    # Boundary detection
    boundary_violation: float = _DEFAULT_BOUNDARY_VIOLATION_THRESHOLD
    boundary_margin: float = _DEFAULT_BOUNDARY_MARGIN
    keyword_boost: float = _DEFAULT_KEYWORD_BOOST
    keyword_embedding_floor: float = _DEFAULT_KEYWORD_EMBEDDING_FLOOR

    # Display zone thresholds
    fidelity_green: float = FIDELITY_GREEN
    fidelity_yellow: float = FIDELITY_YELLOW
    fidelity_orange: float = FIDELITY_ORANGE

    # Composite weights
    weight_purpose: float = _DEFAULT_WEIGHT_PURPOSE
    weight_scope: float = _DEFAULT_WEIGHT_SCOPE
    weight_tool: float = _DEFAULT_WEIGHT_TOOL
    weight_chain: float = _DEFAULT_WEIGHT_CHAIN
    weight_boundary_penalty: float = _DEFAULT_WEIGHT_BOUNDARY_PENALTY

    # Intervention limits
    max_regenerations: int = DEFAULT_MAX_REGENERATIONS

    def validate(self) -> list:
        """Validate ordering invariants and value ranges.

        Returns:
            List of violation strings (empty = valid).
        """
        violations = []

        # Agentic threshold ordering
        if self.st_execute <= self.st_clarify + 0.04:
            violations.append(
                f"st_execute ({self.st_execute:.3f}) must be > "
                f"st_clarify ({self.st_clarify:.3f}) + 0.05"
            )
        # Zone ordering
        if self.fidelity_green <= self.fidelity_yellow + 0.04:
            violations.append(
                f"fidelity_green ({self.fidelity_green:.3f}) must be > "
                f"fidelity_yellow ({self.fidelity_yellow:.3f}) + 0.05"
            )
        if self.fidelity_yellow <= self.fidelity_orange + 0.04:
            violations.append(
                f"fidelity_yellow ({self.fidelity_yellow:.3f}) must be > "
                f"fidelity_orange ({self.fidelity_orange:.3f}) + 0.05"
            )

        # Weight ranges
        positive_sum = (
            self.weight_purpose + self.weight_scope + self.weight_tool
            + self.weight_chain
        )
        total_with_penalty = positive_sum + self.weight_boundary_penalty
        if abs(total_with_penalty - 1.0) > 0.15:
            violations.append(
                f"Total weights ({total_with_penalty:.3f}) should be near 1.0 "
                f"(positive: {positive_sum:.3f} + penalty: {self.weight_boundary_penalty:.3f})"
            )

        # Value ranges
        for name, val in [
            ("boundary_violation", self.boundary_violation),
            ("boundary_margin", self.boundary_margin),
            ("keyword_boost", self.keyword_boost),
        ]:
            if val < 0.0 or val > 1.0:
                violations.append(f"{name} ({val:.3f}) must be in [0.0, 1.0]")

        if self.max_regenerations < 1:
            violations.append(
                f"max_regenerations ({self.max_regenerations}) must be >= 1"
            )

        return violations

    def is_valid(self) -> bool:
        """Check if configuration passes all invariants."""
        return len(self.validate()) == 0

    def to_dict(self) -> Dict[str, float]:
        """Serialize to dict for YAML/JSON output."""
        return {
            "st_execute": self.st_execute,
            "st_clarify": self.st_clarify,
            "boundary_violation": self.boundary_violation,
            "boundary_margin": self.boundary_margin,
            "keyword_boost": self.keyword_boost,
            "keyword_embedding_floor": self.keyword_embedding_floor,
            "fidelity_green": self.fidelity_green,
            "fidelity_yellow": self.fidelity_yellow,
            "fidelity_orange": self.fidelity_orange,
            "weight_purpose": self.weight_purpose,
            "weight_scope": self.weight_scope,
            "weight_tool": self.weight_tool,
            "weight_chain": self.weight_chain,
            "weight_boundary_penalty": self.weight_boundary_penalty,
            "max_regenerations": self.max_regenerations,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "ThresholdConfig":
        """Deserialize from dict."""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

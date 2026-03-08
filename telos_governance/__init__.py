"""
TELOS Governance -- Agentic Governance Gates

Two-tier governance for AI agent actions:
- Tier 1: Fidelity Gate (purpose alignment check)
- Tier 2: Tool Selection Gate (semantic tool ranking)

Uses "Detect and Direct" pattern:
- SPC DETECTS drift via fidelity measurement
- System DIRECTS response back toward primacy attractor

Agentic thresholds (tighter than conversational):
- EXECUTE: >= 0.85 (high confidence, proceed)
- CLARIFY: 0.70-0.84 (verify intent before acting)

- INERT: < 0.70 (acknowledge limitation)
- ESCALATE: < 0.70 + high_risk (require human review)
"""

from telos_governance.types import (
    ActionDecision,
    DirectionLevel,
    GovernanceDecision,
    GovernanceResult,
    GovernanceTrace,
)

from telos_governance._version import __version__

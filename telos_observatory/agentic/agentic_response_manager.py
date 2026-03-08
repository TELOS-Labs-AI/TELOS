"""
Agentic Response Manager — Re-export Stub
============================================
This module has been extracted to telos_governance/response_manager.py
as part of the CLI extraction (Milestone 2, Step 2.4).

This stub re-exports all public symbols for Observatory backward compatibility.
New code should import from telos_governance.response_manager directly.

Deprecated: This location will be removed in a future release.
"""

# Re-export from canonical location
from telos_governance.response_manager import (  # noqa: F401
    AgenticDriftTracker,
    AgenticResponseManager,
    AgenticTurnResult,
    _TOKEN_BUDGETS,
)

__all__ = [
    "AgenticDriftTracker",
    "AgenticResponseManager",
    "AgenticTurnResult",
    "_TOKEN_BUDGETS",
]

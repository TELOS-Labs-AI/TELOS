"""
Mock Tool Execution -- Re-export Stub
======================================
This module has been extracted to telos_governance/mock_tools.py
as part of the CLI extraction (Milestone 2, Step 2.3).

This stub re-exports all public symbols for Observatory backward compatibility.
New code should import from telos_governance.mock_tools directly.

Deprecated: This location will be removed in a future release.
"""

# Re-export from canonical location
from telos_governance.mock_tools import MockToolExecutor  # noqa: F401

__all__ = ["MockToolExecutor"]

"""
Agentic Agent Templates -- Re-export Stub
==========================================
This module has been extracted to telos_governance/agent_templates.py
as part of the CLI extraction (Milestone 2, Step 2.2).

This stub re-exports all public symbols for Observatory backward compatibility.
New code should import from telos_governance.agent_templates directly.

Deprecated: This location will be removed in a future release.
"""

# Re-export from canonical location
from telos_governance.agent_templates import AgenticTemplate, get_agent_templates  # noqa: F401

__all__ = ["AgenticTemplate", "get_agent_templates"]

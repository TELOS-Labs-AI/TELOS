"""
Agentic Forensic Report Generator — Re-export Stub
=====================================================
This module has been extracted to telos_governance/report_generator.py
as part of the CLI extraction (Milestone 2, Step 2.5).

This stub re-exports all public symbols for Observatory backward compatibility.
New code should import from telos_governance.report_generator directly.

Deprecated: This location will be removed in a future release.
"""

# Re-export from canonical location
from telos_governance.report_generator import (  # noqa: F401
    AgenticForensicReportGenerator,
    generate_agentic_forensic_report,
)

__all__ = [
    "AgenticForensicReportGenerator",
    "generate_agentic_forensic_report",
]

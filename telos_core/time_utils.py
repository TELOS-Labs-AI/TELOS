"""
Time Utilities
==============
Centralized timezone-aware UTC datetime helper.
Replaces deprecated datetime.utcnow() (deprecated Python 3.12, PEP 495/615).

All TELOS governance timestamps use this to ensure timezone-aware UTC datetimes
for EU AI Act Article 72 audit trail compliance.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime. Replaces deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)

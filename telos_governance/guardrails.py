"""
Methodological Guardrails for TELOSCOPE
========================================

Provides redaction, export validation, denominator tracking, and
statistical correction utilities for TELOSCOPE research tools.

In TELOSCOPE mode (observation), these produce warnings alongside
results but do not block execution. The warnings are logged to the
teloscope audit trail for posthoc analysis.

Design principle: Score everything. Block nothing. Log everything.
"""
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from telos_governance.corpus import AuditCorpus
except ImportError:
    from corpus import AuditCorpus


# ---------------------------------------------------------------------------
# Credential patterns
# ---------------------------------------------------------------------------

_CREDENTIAL_PATTERNS = [
    re.compile(r'sk-[a-zA-Z0-9]{20,}'),              # OpenAI API keys
    re.compile(r'ghp_[a-zA-Z0-9]{36,}'),              # GitHub PAT
    re.compile(r'AKIA[A-Z0-9]{16}'),                   # AWS access key
    re.compile(r'bearer\s+[a-zA-Z0-9._\-]+', re.I),   # Bearer tokens
    re.compile(r'-----BEGIN\s+\w+\s+KEY-----'),        # PEM keys
]

# ---------------------------------------------------------------------------
# PII patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS = [
    re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),  # Email
    re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),           # IPv4
]

# ---------------------------------------------------------------------------
# Path patterns
# ---------------------------------------------------------------------------

_PATH_PATTERN = re.compile(r'/Users/[a-zA-Z0-9_]+/')


# ---------------------------------------------------------------------------
# Redaction utilities
# ---------------------------------------------------------------------------

def redact_credentials(text: str) -> str:
    """Replace credential patterns with [CREDENTIAL REDACTED]."""
    for pattern in _CREDENTIAL_PATTERNS:
        text = pattern.sub("[CREDENTIAL REDACTED]", text)
    return text


def redact_pii(text: str) -> str:
    """Replace PII patterns with [PII REDACTED].

    Tailscale IPs (100.x.x.x) are preserved since they are internal
    network addresses, not personal information.
    """
    # Email addresses
    text = _PII_PATTERNS[0].sub("[PII REDACTED]", text)

    # IPv4 addresses -- preserve Tailscale 100.x.x.x range
    def _redact_ip(match: re.Match) -> str:
        ip = match.group(0)
        if ip.startswith("100."):
            return ip
        return "[PII REDACTED]"

    text = _PII_PATTERNS[1].sub(_redact_ip, text)
    return text


def redact_paths(text: str) -> str:
    """Sanitize user paths: /Users/<username>/ -> ~/"""
    return _PATH_PATTERN.sub("~/", text)


def redact_text(text: str, level: int = 2) -> str:
    """Apply redaction at specified level.

    Level 1: credentials only
    Level 2: credentials + PII + paths (default)
    Level 3: credentials + PII + paths + truncate to 80 chars
    """
    if not isinstance(text, str):
        return text

    # Level 1: credentials
    text = redact_credentials(text)

    if level >= 2:
        text = redact_pii(text)
        text = redact_paths(text)

    if level >= 3:
        if len(text) > 80:
            text = text[:77] + "..."

    return text


def redact_dict(d: Dict, level: int = 2, zone: int = 1) -> Dict:
    """Redact a dictionary based on zone level.

    Zone 1: Remove request_text, explanation, tool_args entirely
    Zone 2: Keep but redact their contents
    Zone 3: Keep raw (never used in exports)

    Args:
        d: Dictionary to redact.
        level: Redaction level passed to redact_text (1-3).
        zone: Data zone (1=public export, 2=internal, 3=raw).

    Returns:
        New dictionary with redactions applied. Original is not modified.
    """
    ZONE2_KEYS = {
        "request_text", "explanation", "tool_args",
        "action_text", "modified_prompt",
    }

    result = {}
    for key, value in d.items():
        if key in ZONE2_KEYS:
            if zone <= 1:
                # Zone 1: strip entirely
                continue
            elif zone == 2:
                # Zone 2: keep but redact
                if isinstance(value, str):
                    result[key] = redact_text(value, level)
                elif isinstance(value, dict):
                    result[key] = {
                        k: redact_text(str(v), level) if isinstance(v, str) else v
                        for k, v in value.items()
                    }
                else:
                    result[key] = value
            else:
                # Zone 3: keep raw
                result[key] = value
        else:
            # Non-sensitive keys: apply text redaction to string values
            if isinstance(value, str):
                result[key] = redact_text(value, level)
            elif isinstance(value, dict):
                result[key] = redact_dict(value, level, zone)
            else:
                result[key] = value

    return result


# ---------------------------------------------------------------------------
# Export path validation
# ---------------------------------------------------------------------------

BLOCKED_DIRS = [
    "telos_governance", ".claude", ".openclaw",
    ".telos/posthoc_audit", ".telos/keys",
    ".ssh", ".gnupg",
]

BLOCKED_EXTENSIONS = [".py", ".pyc", ".pem", ".key"]


def validate_export_path(path: str, allowed_dir: str = None) -> Tuple[bool, str]:
    """Validate an export path is safe.

    Returns (is_valid, reason).

    Rules:
    - No '..' path traversal
    - No writing to telos_governance/, .claude/, .openclaw/, .telos/posthoc_audit/
    - No writing Python files (.py)
    - No writing JSONL to audit directories (prevent data injection)
    - If allowed_dir specified, must be within it
    """
    # Normalize the path
    norm = os.path.normpath(os.path.expanduser(path))

    # Check for path traversal
    if ".." in path.split(os.sep):
        return False, "Path traversal ('..') is not allowed in export paths"

    # Check blocked extensions
    _, ext = os.path.splitext(norm)
    if ext.lower() in BLOCKED_EXTENSIONS:
        return False, f"Cannot write {ext} files -- blocked extension"

    # Check blocked directories
    for blocked in BLOCKED_DIRS:
        # Check if the blocked dir appears as a path component
        blocked_normalized = os.sep + blocked + os.sep
        if blocked_normalized in (os.sep + norm + os.sep):
            # Extra check: JSONL to audit directories
            if ext.lower() == ".jsonl" and "audit" in blocked.lower():
                return False, (
                    f"Cannot write JSONL to {blocked}/ -- "
                    f"prevents data injection into audit trail"
                )
            return False, f"Cannot write to {blocked}/ -- protected directory"

        # Also check if path starts with the blocked dir
        if norm.startswith(blocked + os.sep) or norm == blocked:
            return False, f"Cannot write to {blocked}/ -- protected directory"

    # Check JSONL to any audit directory
    if ext.lower() == ".jsonl":
        path_lower = norm.lower()
        if "audit" in path_lower or "posthoc" in path_lower:
            return False, (
                "Cannot write JSONL to audit-related directories -- "
                "prevents data injection"
            )

    # Check allowed_dir constraint
    if allowed_dir is not None:
        allowed_norm = os.path.normpath(os.path.expanduser(allowed_dir))
        if not norm.startswith(allowed_norm + os.sep) and norm != allowed_norm:
            return False, (
                f"Export path must be within {allowed_dir}/ -- "
                f"got {path}"
            )

    return True, "OK"


# ---------------------------------------------------------------------------
# Denominator tracking
# ---------------------------------------------------------------------------

@dataclass
class FilteredResult:
    """Wraps any result with denominator context.

    Every filtered view of the corpus must disclose what fraction of
    the total it represents and any methodological warnings.
    """
    result: object              # The actual tool result
    total_corpus_size: int      # Total events before filtering
    filtered_size: int          # Events after filtering
    filter_description: str     # What filter was applied
    fraction: float             # filtered_size / total_corpus_size
    warnings: List[str] = field(default_factory=list)

    def format_header(self) -> str:
        """Format the denominator disclosure header."""
        lines = []
        if self.total_corpus_size != self.filtered_size:
            lines.append(
                f"  [Note: Showing {self.filtered_size} of "
                f"{self.total_corpus_size} "
                f"events ({self.fraction:.1%}) "
                f"-- filter: {self.filter_description}]"
            )
        if self.warnings:
            lines.append("")
            lines.append("  [!] Methodological Notes:")
            for w in self.warnings:
                lines.append(f"      - {w}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bonferroni correction helper
# ---------------------------------------------------------------------------

def bonferroni_alpha(n_tests: int, alpha: float = 0.05) -> float:
    """Compute Bonferroni-corrected significance threshold.

    Args:
        n_tests: Number of simultaneous tests being conducted.
        alpha: Desired family-wise error rate (default 0.05).

    Returns:
        Corrected per-test significance threshold.
    """
    if n_tests <= 0:
        return alpha
    return alpha / n_tests


def is_significant_corrected(
    p_value: float,
    n_tests: int,
    alpha: float = 0.05,
) -> Tuple[bool, float]:
    """Check significance with Bonferroni correction.

    Args:
        p_value: The observed p-value for a single test.
        n_tests: Total number of tests in the family.
        alpha: Desired family-wise error rate (default 0.05).

    Returns:
        (is_significant, corrected_alpha) tuple.
    """
    corrected = bonferroni_alpha(n_tests, alpha)
    return p_value < corrected, corrected


# ---------------------------------------------------------------------------
# Survivorship disclosure
# ---------------------------------------------------------------------------

@dataclass
class LoadMetadata:
    """Metadata about corpus loading for survivorship disclosure.

    Every corpus load must report how many records were found, how many
    were loaded, and how many were excluded. The skip rate is the
    fraction of records that had no verdict field and were therefore
    excluded from analysis -- these are supervisor lifecycle events,
    capability probes, etc.
    """
    n_files_found: int
    n_records_read: int
    n_events_loaded: int
    n_records_skipped: int     # No verdict field
    n_parse_errors: int
    skip_rate: float           # n_skipped / n_records_read

    def format(self) -> str:
        """Format survivorship disclosure as a human-readable string."""
        lines = [
            f"  Loaded: {self.n_events_loaded} events "
            f"from {self.n_files_found} files"
        ]
        if self.n_records_skipped > 0:
            lines.append(
                f"  [!] {self.n_records_skipped} records skipped "
                f"(no verdict field) "
                f"-- {self.skip_rate:.1%} of total records"
            )
        if self.n_parse_errors > 0:
            lines.append(
                f"  [!] {self.n_parse_errors} parse errors "
                f"-- these records are excluded from analysis"
            )
        return "\n".join(lines)

"""
TELOS Update Check: Background version manifest verification.

Implements Tier 2 of the three-tier update awareness architecture:
  Tier 1: Bundle expiry (already built, zero network)
  Tier 2: Signed version manifest (this module, ~150 LOC)
  Tier 3: Out-of-band bundle delivery (already built)

Design principles:
- All failures silent -- network down, CDN error, bad signature → CLI works normally
- Anonymous -- no customer data in manifest check request
- Opt-out-able -- --no-update-check flag or TELOS_NO_UPDATE_CHECK env var
- Non-blocking -- background daemon thread with 2s timeout
- Cache -- skip check if cache is fresh (<24h old)

Manifest format (hosted as static JSON on CDN):
    {
        "schema_version": 1,
        "latest_version": "2.1.0",
        "minimum_version": "2.0.0",
        "released_at": "2026-02-15T00:00:00Z",
        "severity": "routine",
        "update_type": "regulatory",
        "changelog_url": "https://telos-labs.ai/changelog",
        "update_instructions": "Contact TELOS Labs at JB@telos-labs.ai",
        "notices": []
    }

Separate .sig file: 64-byte Ed25519 signature over raw JSON bytes.
"""

import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MANIFEST_URL = "https://updates.telos-labs.ai/manifest.json"
_SIGNATURE_URL = "https://updates.telos-labs.ai/manifest.json.sig"
_FETCH_TIMEOUT = 2  # seconds
_CACHE_TTL = 86400  # 24 hours in seconds
_CACHE_DIR = Path.home() / ".telos"
_CACHE_FILE = _CACHE_DIR / "update_cache.json"

# TELOS Labs manifest signing public key (32-byte Ed25519, hex-encoded).
# This is the ONLY key that can sign valid version manifests.
# Rotate by shipping a new CLI version with the new key.
_LABS_MANIFEST_PUBLIC_KEY_HEX = (
    "0000000000000000000000000000000000000000000000000000000000000000"
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class UpdateInfo:
    """Information about an available update."""
    latest_version: str
    current_version: str
    severity: str  # "safety", "regulatory", "feature", "routine"
    update_type: str
    changelog_url: str
    update_instructions: str
    released_at: str
    minimum_version: str
    notices: list


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------

def _parse_version(v: str) -> tuple:
    """Parse a version string into a comparable tuple.

    Handles: "2.0.0", "2.1.0", "2.0.0-dev", "0.0.0-dev"
    """
    base = v.split("-")[0].split("+")[0]
    parts = []
    for p in base.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    # Pad to at least 3 parts
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def _is_newer(latest: str, current: str) -> bool:
    """Return True if latest is strictly newer than current."""
    return _parse_version(latest) > _parse_version(current)


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def _read_cache() -> Optional[dict]:
    """Read the update cache file. Returns None if missing or unreadable."""
    try:
        if not _CACHE_FILE.exists():
            return None
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_cache(data: dict) -> None:
    """Write to the update cache file. Fails silently."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _cache_is_fresh() -> bool:
    """Return True if the cache exists and is less than 24h old."""
    cache = _read_cache()
    if cache is None:
        return False
    checked_at = cache.get("checked_at", 0)
    return (time.time() - checked_at) < _CACHE_TTL


# ---------------------------------------------------------------------------
# Manifest fetching and verification
# ---------------------------------------------------------------------------

def _fetch_manifest() -> Optional[dict]:
    """Fetch and verify the signed version manifest from CDN.

    Returns parsed manifest dict on success, None on any failure.
    All failures are silent by design.
    """
    try:
        import urllib.request

        # Fetch manifest JSON
        req = urllib.request.Request(_MANIFEST_URL)
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            manifest_bytes = resp.read()

        # Fetch signature
        sig_req = urllib.request.Request(_SIGNATURE_URL)
        with urllib.request.urlopen(sig_req, timeout=_FETCH_TIMEOUT) as resp:
            signature = resp.read()

        if len(signature) != 64:
            return None

        # Verify Ed25519 signature
        from telos_governance.signing import SigningKeyPair, SigningError
        public_key_bytes = bytes.fromhex(_LABS_MANIFEST_PUBLIC_KEY_HEX)
        try:
            SigningKeyPair.verify(manifest_bytes, signature, public_key_bytes)
        except SigningError:
            return None

        # Parse manifest
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        if not isinstance(manifest, dict):
            return None
        if manifest.get("schema_version") != 1:
            return None

        return manifest

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Background check
# ---------------------------------------------------------------------------

_background_thread: Optional[threading.Thread] = None


def start_background_check(current_version: str) -> None:
    """Spawn a daemon thread to check for updates.

    Non-blocking. Returns immediately. The thread fetches the manifest,
    verifies the signature, and writes to cache. All failures silent.
    """
    global _background_thread

    # Skip if suppressed (any value, including empty string, suppresses)
    if os.environ.get("TELOS_NO_UPDATE_CHECK") is not None:
        return

    # Skip if cache is fresh
    if _cache_is_fresh():
        return

    def _check():
        manifest = _fetch_manifest()
        if manifest is None:
            return
        _write_cache({
            "checked_at": time.time(),
            "manifest": manifest,
        })

    _background_thread = threading.Thread(target=_check, daemon=True)
    _background_thread.start()


# ---------------------------------------------------------------------------
# Result reading
# ---------------------------------------------------------------------------

def check_for_update(current_version: str) -> Optional[UpdateInfo]:
    """Read the cache and return update info if a newer version is available.

    Returns None if:
    - No cache exists
    - Cache is unreadable
    - Current version is already latest or ahead
    """
    cache = _read_cache()
    if cache is None:
        return None

    manifest = cache.get("manifest")
    if not isinstance(manifest, dict):
        return None

    latest = manifest.get("latest_version", "")
    if not latest or not _is_newer(latest, current_version):
        return None

    return UpdateInfo(
        latest_version=latest,
        current_version=current_version,
        severity=manifest.get("severity", "routine"),
        update_type=manifest.get("update_type", "feature"),
        changelog_url=manifest.get("changelog_url", ""),
        update_instructions=manifest.get("update_instructions", ""),
        released_at=manifest.get("released_at", ""),
        minimum_version=manifest.get("minimum_version", ""),
        notices=manifest.get("notices", []),
    )

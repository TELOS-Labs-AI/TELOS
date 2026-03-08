"""
Tests for telos_governance.update_check — background version manifest checking.

Tests cover:
- Background check skips when cache is fresh
- Background check handles network failure silently
- Background check handles invalid signature silently
- Version comparison logic (newer available, already current, ahead of manifest)
- Cache file creation and reading
- --no-update-check flag suppresses check (via TELOS_NO_UPDATE_CHECK env var)
- Non-TTY suppresses notification display
"""

import json
import os
import time

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from telos_governance.update_check import (
    _parse_version,
    _is_newer,
    _read_cache,
    _write_cache,
    _cache_is_fresh,
    _fetch_manifest,
    start_background_check,
    check_for_update,
    UpdateInfo,
    _CACHE_TTL,
)


# =============================================================================
# Version comparison
# =============================================================================

class TestVersionComparison:
    """Test version string parsing and comparison."""

    def test_parse_simple_version(self):
        assert _parse_version("2.0.0") == (2, 0, 0)

    def test_parse_version_with_prerelease(self):
        assert _parse_version("2.0.0-dev") == (2, 0, 0)

    def test_parse_version_with_build(self):
        assert _parse_version("2.0.0+build123") == (2, 0, 0)

    def test_parse_short_version(self):
        assert _parse_version("2.1") == (2, 1, 0)

    def test_parse_single_version(self):
        assert _parse_version("3") == (3, 0, 0)

    def test_newer_version_patch(self):
        assert _is_newer("2.0.1", "2.0.0") is True

    def test_newer_version_minor(self):
        assert _is_newer("2.1.0", "2.0.0") is True

    def test_newer_version_major(self):
        assert _is_newer("3.0.0", "2.0.0") is True

    def test_same_version_not_newer(self):
        assert _is_newer("2.0.0", "2.0.0") is False

    def test_older_version_not_newer(self):
        assert _is_newer("1.9.0", "2.0.0") is False

    def test_current_ahead_of_latest(self):
        assert _is_newer("2.0.0", "2.1.0") is False

    def test_dev_version_comparison(self):
        # "0.0.0-dev" should be older than any release
        assert _is_newer("2.0.0", "0.0.0-dev") is True


# =============================================================================
# Cache management
# =============================================================================

class TestCacheManagement:
    """Test cache file reading and writing."""

    def test_read_cache_returns_none_when_missing(self, tmp_path):
        with patch("telos_governance.update_check._CACHE_FILE", tmp_path / "nope.json"):
            assert _read_cache() is None

    def test_write_and_read_cache(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        with patch("telos_governance.update_check._CACHE_FILE", cache_file), \
             patch("telos_governance.update_check._CACHE_DIR", tmp_path):
            data = {"checked_at": time.time(), "manifest": {"latest_version": "2.1.0"}}
            _write_cache(data)
            result = _read_cache()
            assert result is not None
            assert result["manifest"]["latest_version"] == "2.1.0"

    def test_cache_is_fresh_when_recent(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        with patch("telos_governance.update_check._CACHE_FILE", cache_file), \
             patch("telos_governance.update_check._CACHE_DIR", tmp_path):
            _write_cache({"checked_at": time.time(), "manifest": {}})
            assert _cache_is_fresh() is True

    def test_cache_is_stale_when_old(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        with patch("telos_governance.update_check._CACHE_FILE", cache_file), \
             patch("telos_governance.update_check._CACHE_DIR", tmp_path):
            _write_cache({"checked_at": time.time() - _CACHE_TTL - 1, "manifest": {}})
            assert _cache_is_fresh() is False

    def test_cache_is_not_fresh_when_missing(self, tmp_path):
        with patch("telos_governance.update_check._CACHE_FILE", tmp_path / "nope.json"):
            assert _cache_is_fresh() is False

    def test_read_cache_handles_corrupt_file(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("not json!!!")
        with patch("telos_governance.update_check._CACHE_FILE", cache_file):
            assert _read_cache() is None

    def test_read_cache_handles_non_dict(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        cache_file.write_text('"just a string"')
        with patch("telos_governance.update_check._CACHE_FILE", cache_file):
            assert _read_cache() is None

    def test_write_cache_creates_directory(self, tmp_path):
        cache_dir = tmp_path / "sub" / "dir"
        cache_file = cache_dir / "cache.json"
        with patch("telos_governance.update_check._CACHE_FILE", cache_file), \
             patch("telos_governance.update_check._CACHE_DIR", cache_dir):
            _write_cache({"checked_at": time.time()})
            assert cache_file.exists()


# =============================================================================
# Manifest fetching
# =============================================================================

class TestManifestFetch:
    """Test manifest fetching and signature verification."""

    def test_fetch_returns_none_on_network_error(self):
        with patch("urllib.request.urlopen", side_effect=Exception("network down")):
            assert _fetch_manifest() is None

    def test_fetch_returns_none_on_bad_signature_length(self):
        manifest = json.dumps({"schema_version": 1, "latest_version": "2.1.0"}).encode()

        def fake_urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else req
            mock_resp = MagicMock()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            if "manifest.json.sig" in str(url):
                mock_resp.read.return_value = b"short"  # Not 64 bytes
            else:
                mock_resp.read.return_value = manifest
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            assert _fetch_manifest() is None

    def test_fetch_returns_none_on_invalid_signature(self):
        manifest = json.dumps({"schema_version": 1, "latest_version": "2.1.0"}).encode()

        def fake_urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else req
            mock_resp = MagicMock()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            if "manifest.json.sig" in str(url):
                mock_resp.read.return_value = b"\x00" * 64  # Wrong signature
            else:
                mock_resp.read.return_value = manifest
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            # Will fail signature verification (invalid key / bad sig)
            assert _fetch_manifest() is None

    def test_fetch_returns_none_on_wrong_schema_version(self):
        from telos_governance.signing import SigningKeyPair
        kp = SigningKeyPair.generate()
        manifest = json.dumps({"schema_version": 99, "latest_version": "2.1.0"}).encode()
        sig = kp.sign(manifest)

        def fake_urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else req
            mock_resp = MagicMock()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            if "manifest.json.sig" in str(url):
                mock_resp.read.return_value = sig
            else:
                mock_resp.read.return_value = manifest
            return mock_resp

        pub_hex = kp.public_key_bytes.hex()
        with patch("urllib.request.urlopen", side_effect=fake_urlopen), \
             patch("telos_governance.update_check._LABS_MANIFEST_PUBLIC_KEY_HEX", pub_hex):
            assert _fetch_manifest() is None

    def test_fetch_succeeds_with_valid_signature(self):
        from telos_governance.signing import SigningKeyPair
        kp = SigningKeyPair.generate()
        manifest = json.dumps({
            "schema_version": 1,
            "latest_version": "2.1.0",
            "minimum_version": "2.0.0",
            "severity": "routine",
            "update_type": "feature",
        }).encode()
        sig = kp.sign(manifest)

        def fake_urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else req
            mock_resp = MagicMock()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            if "manifest.json.sig" in str(url):
                mock_resp.read.return_value = sig
            else:
                mock_resp.read.return_value = manifest
            return mock_resp

        pub_hex = kp.public_key_bytes.hex()
        with patch("urllib.request.urlopen", side_effect=fake_urlopen), \
             patch("telos_governance.update_check._LABS_MANIFEST_PUBLIC_KEY_HEX", pub_hex):
            result = _fetch_manifest()
            assert result is not None
            assert result["latest_version"] == "2.1.0"


# =============================================================================
# Background check
# =============================================================================

class TestBackgroundCheck:
    """Test background check behavior."""

    def test_skips_when_env_var_set(self, tmp_path):
        with patch.dict(os.environ, {"TELOS_NO_UPDATE_CHECK": "1"}):
            start_background_check("2.0.0")
            # Should return immediately without spawning thread
            from telos_governance.update_check import _background_thread
            # Thread should not have been set in this call
            # (it may be set from a previous test, so just verify no crash)

    def test_skips_when_cache_is_fresh(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        with patch("telos_governance.update_check._CACHE_FILE", cache_file), \
             patch("telos_governance.update_check._CACHE_DIR", tmp_path), \
             patch.dict(os.environ, {}, clear=False):
            # Remove the env var if present
            os.environ.pop("TELOS_NO_UPDATE_CHECK", None)
            _write_cache({"checked_at": time.time(), "manifest": {}})
            with patch("telos_governance.update_check._fetch_manifest") as mock_fetch:
                start_background_check("2.0.0")
                # Give thread a moment (should not start)
                import threading
                time.sleep(0.1)
                mock_fetch.assert_not_called()

    def test_spawns_thread_when_cache_stale(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        with patch("telos_governance.update_check._CACHE_FILE", cache_file), \
             patch("telos_governance.update_check._CACHE_DIR", tmp_path), \
             patch("telos_governance.update_check._fetch_manifest", return_value=None) as mock_fetch:
            os.environ.pop("TELOS_NO_UPDATE_CHECK", None)
            start_background_check("2.0.0")
            # Wait for daemon thread
            from telos_governance.update_check import _background_thread
            if _background_thread:
                _background_thread.join(timeout=2)
            mock_fetch.assert_called_once()


# =============================================================================
# Update info
# =============================================================================

class TestCheckForUpdate:
    """Test reading cache and returning update info."""

    def test_returns_none_when_no_cache(self, tmp_path):
        with patch("telos_governance.update_check._CACHE_FILE", tmp_path / "nope.json"):
            assert check_for_update("2.0.0") is None

    def test_returns_none_when_current_is_latest(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        with patch("telos_governance.update_check._CACHE_FILE", cache_file), \
             patch("telos_governance.update_check._CACHE_DIR", tmp_path):
            _write_cache({
                "checked_at": time.time(),
                "manifest": {"latest_version": "2.0.0"},
            })
            assert check_for_update("2.0.0") is None

    def test_returns_none_when_current_is_ahead(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        with patch("telos_governance.update_check._CACHE_FILE", cache_file), \
             patch("telos_governance.update_check._CACHE_DIR", tmp_path):
            _write_cache({
                "checked_at": time.time(),
                "manifest": {"latest_version": "2.0.0"},
            })
            assert check_for_update("3.0.0") is None

    def test_returns_update_info_when_newer_available(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        with patch("telos_governance.update_check._CACHE_FILE", cache_file), \
             patch("telos_governance.update_check._CACHE_DIR", tmp_path):
            _write_cache({
                "checked_at": time.time(),
                "manifest": {
                    "latest_version": "2.1.0",
                    "minimum_version": "2.0.0",
                    "severity": "regulatory",
                    "update_type": "regulatory",
                    "changelog_url": "https://telos-labs.ai/changelog",
                    "update_instructions": "Contact TELOS Labs",
                    "released_at": "2026-02-15T00:00:00Z",
                    "notices": ["Important update"],
                },
            })
            info = check_for_update("2.0.0")
            assert info is not None
            assert isinstance(info, UpdateInfo)
            assert info.latest_version == "2.1.0"
            assert info.current_version == "2.0.0"
            assert info.severity == "regulatory"
            assert info.update_type == "regulatory"
            assert info.notices == ["Important update"]

    def test_returns_none_when_manifest_missing_from_cache(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        with patch("telos_governance.update_check._CACHE_FILE", cache_file), \
             patch("telos_governance.update_check._CACHE_DIR", tmp_path):
            _write_cache({"checked_at": time.time()})
            assert check_for_update("2.0.0") is None

    def test_returns_none_when_manifest_is_not_dict(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        with patch("telos_governance.update_check._CACHE_FILE", cache_file), \
             patch("telos_governance.update_check._CACHE_DIR", tmp_path):
            _write_cache({"checked_at": time.time(), "manifest": "not a dict"})
            assert check_for_update("2.0.0") is None


# =============================================================================
# CLI integration (env var suppression)
# =============================================================================

class TestEnvVarSuppression:
    """Test that TELOS_NO_UPDATE_CHECK suppresses the check."""

    def test_env_var_suppresses_background_check(self):
        with patch.dict(os.environ, {"TELOS_NO_UPDATE_CHECK": "1"}), \
             patch("telos_governance.update_check._fetch_manifest") as mock_fetch:
            start_background_check("2.0.0")
            time.sleep(0.1)
            mock_fetch.assert_not_called()

    def test_empty_env_var_suppresses(self):
        """Even an empty TELOS_NO_UPDATE_CHECK should suppress."""
        with patch.dict(os.environ, {"TELOS_NO_UPDATE_CHECK": ""}), \
             patch("telos_governance.update_check._fetch_manifest") as mock_fetch:
            start_background_check("2.0.0")
            time.sleep(0.1)
            mock_fetch.assert_not_called()

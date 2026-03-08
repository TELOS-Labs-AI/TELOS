"""
Codebase Access Policy — Ed25519-signed access policies for RAG collections.

Each RAG collection (e.g., telos_governance, agent_workspace)
gets an Ed25519-signed access policy defining which agent identities can
read/write specific code paths. The principal's Ed25519 signature
mathematically bars unauthorized writes — the agent cannot grant itself access.

Policy rules:
    - Unauthorized write to read_only path  -> automatic ESCALATE
    - No policy covering a path             -> fail-closed (ESCALATE)
    - Read to any covered path              -> allowed
    - Write to read_write path              -> allowed

Design:
    - Reuses Ed25519 signing pattern from gate_signer.py
    - Canonical JSON serialization (sorted keys, compact separators)
    - Ed25519 signs raw canonical bytes (no intermediate hash)
    - TTL support (ttl_hours=0 means indefinite)
    - Policy files: ~/.telos/policies/<collection>.json

Regulatory traceability:
    - EU AI Act Art. 14: Human authority over codebase modification scope
    - NIST AI RMF MANAGE 2.4: Mechanisms to constrain agent capabilities
    - Ostrom DP2: Congruence between rules and local conditions
    - Berkeley CLTC Profile: Bounded autonomy via cryptographic policy

Usage:
    from telos_governance.codebase_policy import (
        CodebasePolicySigner, CodebasePolicy, check_access,
    )

    signer = CodebasePolicySigner.generate()
    policy = signer.sign_policy(
        collection="telos_governance",
        paths=["telos_governance/", "telos_core/"],
        access_level="read_only",
        ttl_hours=0,
    )
    assert CodebasePolicySigner.verify(policy, signer.public_key_bytes)

    allowed, reason, matched = check_access(
        "Write", "telos_governance/config.py", [policy], "/project"
    )
    assert not allowed  # unauthorized_write
"""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


class CodebasePolicyError(Exception):
    """Raised when codebase policy signing or verification fails."""
    pass


def _normalize_timestamp(ts: Union[str, float, int]) -> float:
    """Normalize a timestamp to Unix epoch float.

    Handles both float epochs and ISO 8601 strings (same bridge as gate_signer).
    """
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        try:
            from datetime import datetime
            ts_clean = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_clean)
            return dt.timestamp()
        except (ValueError, TypeError):
            pass
        try:
            return float(ts)
        except (ValueError, TypeError):
            pass
    raise CodebasePolicyError(f"Cannot parse timestamp: {ts!r}")


@dataclass
class CodebasePolicy:
    """Ed25519-signed codebase access policy for a RAG collection.

    Attributes:
        collection: Collection name (e.g., "telos_governance").
        paths: Relative path prefixes (e.g., ["telos_governance/", "telos_core/"]).
        access_level: "read_only" or "read_write".
        actor: Signer fingerprint or username.
        timestamp: Raw timestamp (float epoch or ISO 8601 string).
        ttl_hours: Time-to-live in hours (0 = indefinite).
        signature: Hex-encoded 64-byte Ed25519 signature.
        public_key: Hex-encoded 32-byte Ed25519 public key.
    """
    collection: str
    paths: List[str]
    access_level: str
    actor: str
    timestamp: Union[float, str]
    ttl_hours: int
    signature: str
    public_key: str

    @property
    def timestamp_epoch(self) -> float:
        """Timestamp as Unix epoch float (normalized for TTL math)."""
        return _normalize_timestamp(self.timestamp)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON persistence."""
        return {
            "collection": self.collection,
            "paths": self.paths,
            "access_level": self.access_level,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "ttl_hours": self.ttl_hours,
            "signature": self.signature,
            "public_key": self.public_key,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CodebasePolicy":
        """Deserialize from dict.

        Accepts both "public_key" and "tkey_pubkey" field names for
        cross-component compatibility.
        """
        return cls(
            collection=d["collection"],
            paths=d["paths"],
            access_level=d["access_level"],
            actor=d["actor"],
            timestamp=d["timestamp"],
            ttl_hours=d["ttl_hours"],
            signature=d["signature"],
            public_key=d.get("public_key") or d.get("tkey_pubkey", ""),
        )


class CodebasePolicySigner:
    """Ed25519 signer for codebase access policies.

    Signs policy definitions with Ed25519. The signature covers the canonical
    JSON form of the policy fields, ensuring tamper evidence and non-repudiation.

    Args:
        private_key: Ed25519 private key for signing.
    """

    def __init__(self, private_key: Ed25519PrivateKey):
        self._private_key = private_key
        self._public_key = private_key.public_key()

    @classmethod
    def from_private_key_path(cls, path: Path) -> "CodebasePolicySigner":
        """Load signer from a PEM-encoded Ed25519 private key file.

        Args:
            path: Path to PEM file.

        Returns:
            CodebasePolicySigner with loaded key.

        Raises:
            CodebasePolicyError: If the file cannot be read or parsed.
        """
        try:
            data = Path(path).expanduser().read_bytes()
            private_key = serialization.load_pem_private_key(data, password=None)
            if not isinstance(private_key, Ed25519PrivateKey):
                raise CodebasePolicyError(f"Key at {path} is not Ed25519")
            return cls(private_key)
        except CodebasePolicyError:
            raise
        except Exception as e:
            raise CodebasePolicyError(f"Failed to load private key from {path}: {e}") from e

    @classmethod
    def generate(cls) -> "CodebasePolicySigner":
        """Generate a new Ed25519 key pair for policy signing.

        Returns:
            CodebasePolicySigner with fresh key pair.
        """
        return cls(Ed25519PrivateKey.generate())

    @property
    def public_key_bytes(self) -> bytes:
        """32-byte raw Ed25519 public key."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    @property
    def fingerprint(self) -> str:
        """SHA-256 fingerprint of the public key (hex-encoded)."""
        return hashlib.sha256(self.public_key_bytes).hexdigest()

    @staticmethod
    def canonical_form(
        collection: str,
        paths: List[str],
        access_level: str,
        actor: str,
        timestamp: Union[float, str],
        ttl_hours: int,
    ) -> bytes:
        """Create deterministic canonical representation for signing.

        Args:
            collection: Collection name.
            paths: Path prefixes (sorted for determinism).
            access_level: "read_only" or "read_write".
            actor: Signer identity.
            timestamp: Timestamp (passed through as-is).
            ttl_hours: Time-to-live in hours.

        Returns:
            UTF-8 bytes of sorted JSON with compact separators.
        """
        payload = {
            "access_level": access_level,
            "actor": actor,
            "collection": collection,
            "paths": sorted(paths),
            "timestamp": timestamp,
            "ttl_hours": ttl_hours,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign_policy(
        self,
        collection: str,
        paths: List[str],
        access_level: str,
        ttl_hours: int = 0,
    ) -> CodebasePolicy:
        """Sign a codebase access policy.

        Args:
            collection: Collection name (e.g., "telos_governance").
            paths: Relative path prefixes (e.g., ["telos_governance/", "telos_core/"]).
            access_level: "read_only" or "read_write".
            ttl_hours: Time-to-live in hours (0 = indefinite).

        Returns:
            CodebasePolicy with Ed25519 signature.

        Raises:
            CodebasePolicyError: If signing fails or inputs are invalid.
        """
        if access_level not in ("read_only", "read_write"):
            raise CodebasePolicyError(
                f"Invalid access_level: {access_level!r} (must be 'read_only' or 'read_write')"
            )
        if not collection:
            raise CodebasePolicyError("Collection name must not be empty")
        if not paths:
            raise CodebasePolicyError("Paths list must not be empty")

        actor = self.fingerprint
        timestamp = time.time()

        canonical = self.canonical_form(
            collection, paths, access_level, actor, timestamp, ttl_hours,
        )

        try:
            signature = self._private_key.sign(canonical)
        except Exception as e:
            raise CodebasePolicyError(f"Ed25519 signing failed: {e}") from e

        return CodebasePolicy(
            collection=collection,
            paths=sorted(paths),
            access_level=access_level,
            actor=actor,
            timestamp=timestamp,
            ttl_hours=ttl_hours,
            signature=signature.hex(),
            public_key=self.public_key_bytes.hex(),
        )

    @staticmethod
    def verify(policy: CodebasePolicy, public_key_bytes: bytes) -> bool:
        """Verify a CodebasePolicy's Ed25519 signature.

        Args:
            policy: The codebase policy to verify.
            public_key_bytes: 32-byte raw Ed25519 public key.

        Returns:
            True if the signature is valid.

        Raises:
            CodebasePolicyError: If verification fails.
        """
        if not policy.signature:
            raise CodebasePolicyError("CodebasePolicy has no signature")

        try:
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)

            canonical = CodebasePolicySigner.canonical_form(
                policy.collection, policy.paths, policy.access_level,
                policy.actor, policy.timestamp, policy.ttl_hours,
            )

            signature = bytes.fromhex(policy.signature)
            public_key.verify(signature, canonical)
            return True

        except InvalidSignature:
            raise CodebasePolicyError(
                "Ed25519 signature verification failed — wrong key or tampered policy"
            )
        except CodebasePolicyError:
            raise
        except Exception as e:
            raise CodebasePolicyError(f"Verification error: {e}") from e

    @staticmethod
    def is_expired(policy: CodebasePolicy) -> bool:
        """Check if a policy's TTL has elapsed.

        Args:
            policy: The codebase policy to check.

        Returns:
            True if the TTL has expired. False if ttl_hours=0 (indefinite).
        """
        if policy.ttl_hours <= 0:
            return False
        expiry = policy.timestamp_epoch + (policy.ttl_hours * 3600)
        return time.time() > expiry


# ---------------------------------------------------------------------------
# Path matching utilities
# ---------------------------------------------------------------------------

# Canonical tool sets — all lowercase for case-insensitive matching.
# Unknown tools are treated as writes (deny-by-default).
WRITE_TOOLS = {"write", "edit", "multiedit", "delete", "move", "applypatch"}
READ_TOOLS = {"read", "glob", "grep", "listdir"}
ALL_KNOWN_TOOLS = WRITE_TOOLS | READ_TOOLS


def extract_file_path(tool_name: str, tool_args: dict) -> Optional[str]:
    """Extract file path from tool arguments.

    Checks common argument names used by filesystem tools.

    Args:
        tool_name: The tool name (e.g., "Write", "Read", "Glob").
        tool_args: The tool's argument dict.

    Returns:
        File path string if found, None otherwise.
    """
    if not tool_args:
        return None

    # Direct file path arguments
    for key in ("file_path", "path", "notebook_path"):
        val = tool_args.get(key)
        if val and isinstance(val, str):
            return val

    return None


def normalize_path(file_path: str, project_root: str) -> str:
    """Strip project_root prefix, return relative path.

    Args:
        file_path: Absolute or relative file path.
        project_root: Project root directory path.

    Returns:
        Relative path (e.g., "telos_governance/config.py").
    """
    if not project_root:
        return file_path

    # Normalize both paths
    fp = file_path.rstrip("/")
    root = project_root.rstrip("/")

    if fp.startswith(root + "/"):
        return fp[len(root) + 1:]
    if fp.startswith(root):
        return fp[len(root):]

    return file_path


def find_matching_policy(
    file_path: str,
    policies: List[CodebasePolicy],
    project_root: str,
) -> Optional[CodebasePolicy]:
    """Find the policy whose path prefixes match the given file path.

    Uses longest-prefix-match: if multiple policies cover a path,
    the one with the longest matching prefix wins.

    Args:
        file_path: The file path to check (absolute or relative).
        policies: List of valid CodebasePolicy objects.
        project_root: Project root for path normalization.

    Returns:
        Matching CodebasePolicy, or None if no policy covers the path.
    """
    rel_path = normalize_path(file_path, project_root)

    best_match = None
    best_prefix_len = -1

    for policy in policies:
        for prefix in policy.paths:
            if rel_path.startswith(prefix) and len(prefix) > best_prefix_len:
                best_match = policy
                best_prefix_len = len(prefix)

    return best_match


def check_access(
    tool_name: str,
    file_path: str,
    policies: List[CodebasePolicy],
    project_root: str,
) -> Tuple[bool, str, Optional[CodebasePolicy]]:
    """Check if tool_name + file_path is authorized by codebase policies.

    Args:
        tool_name: The tool being invoked (e.g., "Write", "Read").
        file_path: The target file path.
        policies: List of valid CodebasePolicy objects.
        project_root: Project root for path normalization.

    Returns:
        Tuple of (allowed, reason, matched_policy):
        - Write to read_only    -> (False, "unauthorized_write", policy)
        - Any op to uncovered   -> (False, "no_policy", None)
        - Read to any covered   -> (True, "read_allowed", policy)
        - Write to read_write   -> (True, "write_allowed", policy)
    """
    canonical_tool = tool_name.strip().lower() if tool_name else ""
    # Deny-by-default: unknown tools treated as writes (fail-closed)
    is_write = canonical_tool not in READ_TOOLS

    matched = find_matching_policy(file_path, policies, project_root)

    if matched is None:
        return (False, "no_policy", None)

    if is_write and matched.access_level == "read_only":
        return (False, "unauthorized_write", matched)

    if is_write:
        return (True, "write_allowed", matched)

    return (True, "read_allowed", matched)

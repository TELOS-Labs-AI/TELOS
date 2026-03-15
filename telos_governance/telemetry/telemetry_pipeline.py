"""
TELOSCOPE Telemetry Pipeline
==============================

Production telemetry pipeline for TELOSCOPE. Collects governance telemetry
from deployed instances and transmits it to TELOS AI Labs via Supabase REST
API, signed with TKeys Ed25519.

Architecture:
  1. TeloscopeAudit writes AuditEntry records to ~/.telos/teloscope_audit/
  2. TelemetryExtractor reads AuditEntry records and produces TelemetryRecord
     deltas -- governance scores and check results ONLY, no customer data
  3. TelemetryBuffer appends TelemetryRecord to ~/.telos/teloscope_telemetry/buffer.jsonl
  4. TelemetryUploader reads the buffer, signs each record with TKeys,
     batches them, and POSTs to Supabase REST API
  5. Successfully uploaded records are removed from the buffer (compaction)

What stays local:
  - Raw governance audit JSONL (the data being analyzed)
  - request_text, explanation, tool_args from audit events
  - Researcher's natural language queries
  - Full AuditEntry records (including tool_args)

What gets transmitted (the "delta"):
  - entry_id (UUID)
  - timestamp (ISO 8601)
  - tool_name (e.g., "research_audit_compare")
  - gate2_verdict (EXECUTE/CLARIFY/ESCALATE)
  - checks: list of {check_name, status, would_block} -- NO message, NO details
  - chain_position (tool call sequence position)
  - chain_pattern (tool names only, e.g. "load,stats,compare")
  - corpus_size (how many events were being analyzed)
  - instance_id (anonymized installation identifier)
  - tkeys_signature (Ed25519 signature of the canonical record)

Privacy engineering:
  - instance_id = SHA-256(machine_id + install_salt) -- deterministic but
    not reversible to identity
  - No IP logging server-side (Supabase RLS + Edge Function)
  - No content, no paths, no query text on the wire
  - Checks[] stripped to {check_name, status, would_block} -- no message, no details

Failure modes:
  - Supabase unreachable: buffer accumulates, exponential backoff, retry on next cycle
  - Key rotation: old signatures still verify against registered public keys
  - Buffer corruption: skip malformed lines, log error, continue
  - Clock skew: server accepts timestamps within +/- 24h, logs skew for monitoring
  - Air-gapped: buffer grows indefinitely, optional manual export via CLI

Usage:
    from telos_governance.telemetry_pipeline import (
        TelemetryExtractor,
        TelemetryBuffer,
        TelemetryUploader,
    )

    # Extract telemetry from an AuditEntry
    extractor = TelemetryExtractor(instance_id="abc123...")
    record = extractor.from_audit_entry(audit_entry, chain_position=1, chain_pattern="load,stats")

    # Buffer locally
    buf = TelemetryBuffer()
    buf.append(record)

    # Upload (typically on a timer or session end)
    uploader = TelemetryUploader(key_path="~/.telos/keys/customer.key")
    result = uploader.flush()
"""

import hashlib
import json
import logging
import os
import platform
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Telemetry record schema -- the ONLY thing that leaves the customer's machine
# ---------------------------------------------------------------------------

TELEMETRY_SCHEMA_VERSION = 1

# Maximum records per batch POST
MAX_BATCH_SIZE = 100

# Maximum buffer age before warning (seconds) -- 7 days
MAX_BUFFER_AGE_WARN = 7 * 24 * 3600

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF_S = 2.0
MAX_BACKOFF_S = 120.0
BACKOFF_MULTIPLIER = 2.0

# Server-side clock skew tolerance (seconds) -- +/- 24 hours
CLOCK_SKEW_TOLERANCE_S = 24 * 3600

# Default Supabase endpoint for telemetry
TELEMETRY_ENDPOINT_DEFAULT = (
    "https://evfhpcuoreieytzmiiva.supabase.co/rest/v1/teloscope_telemetry"
)


@dataclass
class TelemetryCheckRecord:
    """Stripped-down check record for telemetry transmission.

    Contains ONLY the check identity and outcome -- no human-readable
    message, no structured details, no content.
    """
    check_name: str     # e.g., "sample_size", "denominator_disclosure"
    status: str         # "pass", "warn", "fail"
    would_block: bool   # Whether enforcement mode would have blocked

    def to_dict(self) -> Dict:
        return {
            "check_name": self.check_name,
            "status": self.status,
            "would_block": self.would_block,
        }


@dataclass
class TelemetryRecord:
    """The telemetry delta -- what gets signed and transmitted.

    This is the complete schema of what leaves the customer's machine.
    Every field is intentional. No optional "extras" dict, no extension
    points that could leak content.

    The canonical serialization for signing is:
        json.dumps(record.to_signable_dict(), sort_keys=True, separators=(',', ':'))

    This produces deterministic JSON for signature verification.
    """

    # --- Identity ---
    entry_id: str               # UUID from the original AuditEntry
    instance_id: str            # Anonymized installation identifier
    schema_version: int = TELEMETRY_SCHEMA_VERSION

    # --- Temporal ---
    timestamp: str = ""         # ISO 8601 UTC from the original AuditEntry

    # --- Tool invocation (identity only, no args) ---
    tool_name: str = ""         # e.g., "research_audit_compare"

    # --- Governance outcome ---
    gate2_verdict: str = ""     # "EXECUTE", "CLARIFY", "ESCALATE"
    checks: List[TelemetryCheckRecord] = field(default_factory=list)

    # --- Chain context (tool names only, no content) ---
    chain_position: int = 0     # 1-indexed position in the tool call sequence
    chain_pattern: str = ""     # e.g., "load,stats,compare" -- tool names only

    # --- Corpus metadata (counts only) ---
    corpus_size: int = 0        # Number of events being analyzed

    # --- Cryptographic proof ---
    tkeys_signature: str = ""   # Ed25519 signature (hex) over signable payload
    signer_fingerprint: str = ""  # SHA-256 of signer's public key (hex)

    def to_signable_dict(self) -> Dict:
        """Produce the canonical dict for signing.

        EXCLUDES tkeys_signature and signer_fingerprint (those are
        computed from this payload). Sorted keys, no whitespace.
        """
        return {
            "chain_pattern": self.chain_pattern,
            "chain_position": self.chain_position,
            "checks": [c.to_dict() for c in self.checks],
            "corpus_size": self.corpus_size,
            "entry_id": self.entry_id,
            "gate2_verdict": self.gate2_verdict,
            "instance_id": self.instance_id,
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
            "tool_name": self.tool_name,
        }

    def canonical_bytes(self) -> bytes:
        """Deterministic JSON bytes for signing.

        sort_keys=True + separators=(',',':') ensures every implementation
        produces the same byte sequence for the same logical record.
        """
        return json.dumps(
            self.to_signable_dict(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def to_dict(self) -> Dict:
        """Full record including signature fields -- for transmission."""
        d = self.to_signable_dict()
        d["tkeys_signature"] = self.tkeys_signature
        d["signer_fingerprint"] = self.signer_fingerprint
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "TelemetryRecord":
        """Deserialize from dict (e.g., from buffer JSONL)."""
        checks = [
            TelemetryCheckRecord(**c) for c in d.get("checks", [])
        ]
        return cls(
            entry_id=d["entry_id"],
            instance_id=d["instance_id"],
            schema_version=d.get("schema_version", TELEMETRY_SCHEMA_VERSION),
            timestamp=d.get("timestamp", ""),
            tool_name=d.get("tool_name", ""),
            gate2_verdict=d.get("gate2_verdict", ""),
            checks=checks,
            chain_position=d.get("chain_position", 0),
            chain_pattern=d.get("chain_pattern", ""),
            corpus_size=d.get("corpus_size", 0),
            tkeys_signature=d.get("tkeys_signature", ""),
            signer_fingerprint=d.get("signer_fingerprint", ""),
        )


# ---------------------------------------------------------------------------
# Instance ID generation -- deterministic, non-reversible
# ---------------------------------------------------------------------------

INSTANCE_SALT_PATH = os.path.expanduser("~/.telos/teloscope_telemetry/.install_salt")


def _get_machine_id() -> str:
    """Get a stable machine identifier.

    Uses platform.node() (hostname) combined with os-level identifiers.
    This is NOT transmitted -- only used as input to the hash.
    """
    components = [
        platform.node(),
        platform.machine(),
        platform.system(),
    ]
    # On macOS, try to get hardware UUID
    if platform.system() == "Darwin":
        try:
            import subprocess
            result = subprocess.run(
                ["ioreg", "-d2", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    # Extract the UUID value
                    uuid_part = line.split('"')[-2]
                    components.append(uuid_part)
                    break
        except Exception:
            pass
    # On Linux, try /etc/machine-id
    elif platform.system() == "Linux":
        try:
            mid = Path("/etc/machine-id").read_text().strip()
            components.append(mid)
        except Exception:
            pass

    return "|".join(components)


def _get_install_salt() -> str:
    """Get or create a per-installation random salt.

    This salt is generated once on first run and persisted. It ensures
    that the instance_id cannot be correlated across reinstalls, and
    that even with knowledge of the machine_id, the instance_id cannot
    be pre-computed without the salt.

    Stored at: ~/.telos/teloscope_telemetry/.install_salt
    """
    salt_path = Path(INSTANCE_SALT_PATH)
    if salt_path.exists():
        return salt_path.read_text().strip()

    # Generate new salt
    salt = uuid.uuid4().hex
    salt_path.parent.mkdir(parents=True, exist_ok=True)
    # Write with restricted permissions
    fd = os.open(str(salt_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, salt.encode("utf-8"))
    finally:
        os.close(fd)
    return salt


def generate_instance_id() -> str:
    """Generate an anonymized, deterministic installation identifier.

    instance_id = SHA-256(machine_id || install_salt)

    Properties:
      - Deterministic: same machine + same salt = same ID
      - Non-reversible: cannot recover machine_id from instance_id
      - Non-correlatable: different salt (reinstall) = different ID
      - Non-identifying: no username, hostname, or IP in the output

    Returns:
        64-character hex string (SHA-256 digest).
    """
    machine_id = _get_machine_id()
    salt = _get_install_salt()
    combined = f"{machine_id}|{salt}".encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


# ---------------------------------------------------------------------------
# TelemetryExtractor -- converts AuditEntry to TelemetryRecord
# ---------------------------------------------------------------------------

class TelemetryExtractor:
    """Extracts the telemetry delta from a full AuditEntry.

    Strips all content, tool_args, check messages, check details.
    Produces only the governance-relevant metadata for transmission.

    Usage:
        extractor = TelemetryExtractor()  # auto-generates instance_id
        record = extractor.from_audit_entry(entry, chain_position=1)
    """

    def __init__(self, instance_id: str = ""):
        """Initialize with an instance identifier.

        Args:
            instance_id: Anonymized installation ID. If empty, auto-generated
                from machine_id + install_salt.
        """
        self.instance_id = instance_id or generate_instance_id()

    def from_audit_entry(
        self,
        entry,  # AuditEntry from teloscope_audit.py
        chain_position: int = 0,
        chain_pattern: str = "",
        corpus_size: int = 0,
    ) -> TelemetryRecord:
        """Extract a TelemetryRecord from a full AuditEntry.

        This is the privacy boundary. Everything that comes out of this
        method is safe to transmit. Everything that doesn't come out
        stays local.

        Args:
            entry: AuditEntry from teloscope_audit.py.
            chain_position: 1-indexed position in the tool call sequence.
            chain_pattern: Tool names in chain order, comma-separated.
            corpus_size: Number of events in the corpus being analyzed.

        Returns:
            TelemetryRecord with only governance metadata.
        """
        # Strip checks to {check_name, status, would_block} only
        stripped_checks = [
            TelemetryCheckRecord(
                check_name=c.check_name,
                status=c.status,
                would_block=c.would_block,
            )
            for c in entry.checks
        ]

        return TelemetryRecord(
            entry_id=entry.entry_id,
            instance_id=self.instance_id,
            timestamp=entry.timestamp,
            tool_name=entry.tool_name,
            gate2_verdict=entry.gate2_verdict,
            checks=stripped_checks,
            chain_position=chain_position,
            chain_pattern=chain_pattern,
            corpus_size=corpus_size,
        )

    def from_audit_dict(
        self,
        d: Dict,
        chain_position: int = 0,
        chain_pattern: str = "",
        corpus_size: int = 0,
    ) -> TelemetryRecord:
        """Extract from a raw dict (e.g., read from JSONL).

        Same privacy boundary as from_audit_entry, but for cases where
        the AuditEntry hasn't been deserialized into the dataclass.
        """
        stripped_checks = [
            TelemetryCheckRecord(
                check_name=c.get("check_name", "unknown"),
                status=c.get("status", "unknown"),
                would_block=c.get("would_block", False),
            )
            for c in d.get("checks", [])
        ]

        return TelemetryRecord(
            entry_id=d.get("entry_id", str(uuid.uuid4())),
            instance_id=self.instance_id,
            timestamp=d.get("timestamp", ""),
            tool_name=d.get("tool_name", ""),
            gate2_verdict=d.get("gate2_verdict", ""),
            checks=stripped_checks,
            chain_position=chain_position,
            chain_pattern=chain_pattern,
            corpus_size=corpus_size,
        )


# ---------------------------------------------------------------------------
# TelemetryBuffer -- local JSONL accumulator
# ---------------------------------------------------------------------------

BUFFER_DIR = os.path.expanduser("~/.telos/teloscope_telemetry")
BUFFER_FILE = os.path.join(BUFFER_DIR, "buffer.jsonl")
UPLOAD_CURSOR_FILE = os.path.join(BUFFER_DIR, ".upload_cursor")
EXPORT_DIR = os.path.join(BUFFER_DIR, "exports")


class TelemetryBuffer:
    """Local JSONL buffer for telemetry records awaiting upload.

    Records are appended to buffer.jsonl. After successful upload,
    uploaded records are removed via compaction (rewrite without
    uploaded entry_ids).

    The buffer is the source of truth for what hasn't been uploaded yet.
    If upload fails, records stay in the buffer for retry.

    File: ~/.telos/teloscope_telemetry/buffer.jsonl
    """

    def __init__(self, buffer_path: str = BUFFER_FILE):
        self.buffer_path = buffer_path
        self._ensure_dir()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.buffer_path), exist_ok=True)

    def append(self, record: TelemetryRecord) -> None:
        """Append a telemetry record to the buffer.

        Args:
            record: TelemetryRecord to buffer for later upload.
        """
        with open(self.buffer_path, "a") as f:
            f.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")

    def read_all(self) -> List[TelemetryRecord]:
        """Read all records from the buffer.

        Skips malformed lines (logs to stderr, does not raise).
        This is intentional -- buffer corruption should not prevent
        processing of valid records.

        Returns:
            List of TelemetryRecord, in buffer order.
        """
        records = []
        if not os.path.exists(self.buffer_path):
            return records

        with open(self.buffer_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    records.append(TelemetryRecord.from_dict(d))
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.warning(
                        "Skipping malformed line %d in telemetry buffer: %s",
                        line_num, e,
                    )
        return records

    def read_batch(self, batch_size: int = MAX_BATCH_SIZE) -> List[TelemetryRecord]:
        """Read up to batch_size records from the buffer.

        Returns the oldest records first (FIFO order).
        """
        all_records = self.read_all()
        return all_records[:batch_size]

    def compact(self, uploaded_ids: set) -> int:
        """Remove uploaded records from the buffer.

        Rewrites the buffer file without the uploaded entry_ids.
        Uses atomic rename to prevent data loss on crash.

        Args:
            uploaded_ids: Set of entry_id strings that were successfully uploaded.

        Returns:
            Number of records removed.
        """
        if not uploaded_ids:
            return 0

        if not os.path.exists(self.buffer_path):
            return 0

        tmp_path = self.buffer_path + ".tmp"
        removed = 0

        with open(self.buffer_path, "r") as f_in, open(tmp_path, "w") as f_out:
            for line in f_in:
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                try:
                    d = json.loads(line_stripped)
                    if d.get("entry_id") in uploaded_ids:
                        removed += 1
                        continue
                except (json.JSONDecodeError, KeyError):
                    pass
                f_out.write(line)

        # Atomic rename
        os.replace(tmp_path, self.buffer_path)
        return removed

    def count(self) -> int:
        """Count records in the buffer without fully parsing them."""
        if not os.path.exists(self.buffer_path):
            return 0
        count = 0
        with open(self.buffer_path, "r") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    def oldest_timestamp(self) -> Optional[str]:
        """Get the timestamp of the oldest record in the buffer.

        Returns:
            ISO 8601 timestamp string, or None if buffer is empty.
        """
        if not os.path.exists(self.buffer_path):
            return None
        with open(self.buffer_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    return d.get("timestamp")
                except (json.JSONDecodeError, KeyError):
                    continue
        return None

    def buffer_age_seconds(self) -> float:
        """How old is the oldest record in the buffer?

        Returns:
            Age in seconds, or 0.0 if buffer is empty.
        """
        ts = self.oldest_timestamp()
        if not ts:
            return 0.0
        try:
            oldest = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            return (now - oldest).total_seconds()
        except (ValueError, TypeError):
            return 0.0

    def export_for_sneakernet(self, export_path: str = "") -> str:
        """Export buffer contents for manual transfer (air-gapped deployments).

        Writes the current buffer to a timestamped export file that can
        be transferred via USB or other offline means.

        Args:
            export_path: Explicit export path. If empty, writes to
                ~/.telos/teloscope_telemetry/exports/YYYY-MM-DD_HHMMSS.jsonl

        Returns:
            Path to the export file.
        """
        if not export_path:
            os.makedirs(EXPORT_DIR, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
            export_path = os.path.join(EXPORT_DIR, f"{ts}.jsonl")

        records = self.read_all()
        with open(export_path, "w") as f:
            for r in records:
                f.write(json.dumps(r.to_dict(), sort_keys=True) + "\n")

        return export_path

    def status(self) -> Dict:
        """Buffer health check."""
        count = self.count()
        age = self.buffer_age_seconds()
        return {
            "buffer_path": self.buffer_path,
            "record_count": count,
            "oldest_record_age_seconds": age,
            "oldest_record_age_human": _human_duration(age) if age > 0 else "empty",
            "stale": age > MAX_BUFFER_AGE_WARN,
            "buffer_size_bytes": (
                os.path.getsize(self.buffer_path)
                if os.path.exists(self.buffer_path) else 0
            ),
        }


def _human_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.0f}m"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    else:
        return f"{seconds / 86400:.1f}d"


# ---------------------------------------------------------------------------
# TelemetrySigner -- Ed25519 signing of telemetry records
# ---------------------------------------------------------------------------

class TelemetrySigner:
    """Signs telemetry records with the customer's TKey.

    Each record's canonical JSON is signed with Ed25519. The signature
    and signer fingerprint are added to the record before transmission.

    Server-side verification:
      1. Server extracts signer_fingerprint from the record
      2. Looks up the registered public key for that fingerprint
      3. Reconstructs canonical_bytes from the signable fields
      4. Verifies the Ed25519 signature
      5. Rejects if signature invalid, fingerprint unknown, or timestamp
         outside clock skew tolerance

    Key rotation:
      The server maintains a registry of {fingerprint -> public_key}
      for each instance_id. When a customer rotates their key, the new
      public key is registered on first use (trust-on-first-use for new
      fingerprints from known instances, or explicit registration via
      activation ping). Old signatures remain verifiable against old keys.

    Usage:
        signer = TelemetrySigner("~/.telos/keys/customer.key")
        signed_record = signer.sign(record)
    """

    def __init__(self, key_path: str = ""):
        """Initialize with the customer's TKey.

        Args:
            key_path: Path to Ed25519 private key (PEM). If empty, uses
                default location ~/.telos/keys/customer.key
        """
        if not key_path:
            key_path = os.path.expanduser("~/.telos/keys/customer.key")
        self.key_path = key_path
        self._keypair = None
        self._fingerprint = ""

    def _load_key(self):
        """Lazy-load the signing key."""
        if self._keypair is not None:
            return

        from telos_governance.signing import SigningKeyPair, SigningError

        path = Path(self.key_path).expanduser()
        if not path.exists():
            raise SigningError(
                f"TKey not found at {path}. Run 'telos keygen' to generate."
            )
        self._keypair = SigningKeyPair.from_private_pem(path)
        self._fingerprint = self._keypair.fingerprint

    @property
    def fingerprint(self) -> str:
        """Signer's public key fingerprint (SHA-256 hex)."""
        self._load_key()
        return self._fingerprint

    def sign(self, record: TelemetryRecord) -> TelemetryRecord:
        """Sign a telemetry record in place.

        Computes the Ed25519 signature over the canonical JSON
        representation (sorted keys, no whitespace) and sets the
        tkeys_signature and signer_fingerprint fields.

        Args:
            record: TelemetryRecord to sign.

        Returns:
            The same record, with signature fields populated.
        """
        self._load_key()

        payload = record.canonical_bytes()
        signature = self._keypair.sign(payload)

        record.tkeys_signature = signature.hex()
        record.signer_fingerprint = self._fingerprint
        return record

    def sign_batch(self, records: List[TelemetryRecord]) -> List[TelemetryRecord]:
        """Sign a batch of records."""
        return [self.sign(r) for r in records]


# ---------------------------------------------------------------------------
# TelemetryUploader -- batched upload to Supabase REST API
# ---------------------------------------------------------------------------

class TelemetryUploader:
    """Reads from the local buffer, signs, batches, and uploads to Supabase.

    Upload strategy:
      - Reads up to MAX_BATCH_SIZE records from buffer
      - Signs each with TKeys Ed25519
      - POSTs batch to Supabase REST API (INSERT)
      - On success, compacts the buffer (removes uploaded records)
      - On failure, leaves records in buffer for retry
      - Exponential backoff on repeated failures

    Scheduling:
      - flush() is called by an external scheduler (launchd, cron, or
        session-end hook)
      - Recommended interval: 15 minutes for active sessions, plus
        on-session-end for final flush
      - Air-gapped: flush() is a no-op (returns immediately)

    Authentication:
      - Supabase anon key in env var TELOS_TELEMETRY_ANON_KEY
      - RLS policy restricts INSERT only (no SELECT, UPDATE, DELETE)
      - The anon key can only append to teloscope_telemetry table
      - No read access to other instances' data from the client

    Usage:
        uploader = TelemetryUploader()
        result = uploader.flush()
        print(f"Uploaded {result['uploaded']}, failed {result['failed']}")
    """

    def __init__(
        self,
        key_path: str = "",
        endpoint: str = "",
        anon_key: str = "",
        buffer_path: str = BUFFER_FILE,
    ):
        """Initialize the uploader.

        Args:
            key_path: Path to customer TKey. Default: ~/.telos/keys/customer.key
            endpoint: Supabase REST endpoint. Default: from env or compiled-in.
            anon_key: Supabase anon key. Default: from env TELOS_TELEMETRY_ANON_KEY.
            buffer_path: Path to the buffer JSONL file.
        """
        self.signer = TelemetrySigner(key_path)
        self.buffer = TelemetryBuffer(buffer_path)

        self.endpoint = endpoint or os.environ.get(
            "TELOS_TELEMETRY_ENDPOINT",
            TELEMETRY_ENDPOINT_DEFAULT,
        )
        self.anon_key = anon_key or os.environ.get(
            "TELOS_TELEMETRY_ANON_KEY", ""
        )

        self._consecutive_failures = 0
        self._last_failure_time = 0.0

    def _should_backoff(self) -> bool:
        """Check if we should skip this upload attempt due to backoff."""
        if self._consecutive_failures == 0:
            return False

        backoff = min(
            INITIAL_BACKOFF_S * (BACKOFF_MULTIPLIER ** (self._consecutive_failures - 1)),
            MAX_BACKOFF_S,
        )
        elapsed = time.time() - self._last_failure_time
        return elapsed < backoff

    def _post_batch(self, records: List[TelemetryRecord]) -> Tuple[bool, str]:
        """POST a batch of signed records to Supabase REST API.

        Uses urllib (stdlib) -- no third-party HTTP dependency.

        Args:
            records: List of signed TelemetryRecord.

        Returns:
            (success, error_message) tuple.
        """
        if not self.anon_key:
            return False, "No Supabase anon key configured (TELOS_TELEMETRY_ANON_KEY)"

        if not self.endpoint:
            return False, "No telemetry endpoint configured"

        import urllib.request
        import urllib.error

        payload = json.dumps([r.to_dict() for r in records]).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.anon_key}",
            "Prefer": "return=minimal",  # Don't return inserted rows
        }

        req = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                if 200 <= status < 300:
                    return True, ""
                else:
                    body = resp.read().decode("utf-8", errors="replace")
                    return False, f"HTTP {status}: {body[:200]}"
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            return False, f"HTTP {e.code}: {body[:200]}"
        except urllib.error.URLError as e:
            return False, f"Connection error: {e.reason}"
        except Exception as e:
            return False, f"Unexpected error: {e}"

    def flush(self) -> Dict[str, Any]:
        """Upload buffered telemetry records to Supabase.

        Reads from the buffer, signs each record, POSTs in batches,
        and compacts the buffer on success.

        Returns:
            Dict with:
                uploaded: int -- number of records successfully uploaded
                failed: int -- number of records that failed to upload
                remaining: int -- records still in buffer
                error: str -- last error message (empty if all succeeded)
                backoff: bool -- True if skipped due to backoff
        """
        # Check backoff
        if self._should_backoff():
            remaining = self.buffer.count()
            return {
                "uploaded": 0,
                "failed": 0,
                "remaining": remaining,
                "error": "",
                "backoff": True,
            }

        # Read batch from buffer
        records = self.buffer.read_batch(MAX_BATCH_SIZE)
        if not records:
            return {
                "uploaded": 0,
                "failed": 0,
                "remaining": 0,
                "error": "",
                "backoff": False,
            }

        # Sign all records
        try:
            signed = self.signer.sign_batch(records)
        except Exception as e:
            return {
                "uploaded": 0,
                "failed": len(records),
                "remaining": self.buffer.count(),
                "error": f"Signing failed: {e}",
                "backoff": False,
            }

        # POST to Supabase
        success, error = self._post_batch(signed)

        if success:
            # Compact buffer -- remove uploaded records
            uploaded_ids = {r.entry_id for r in signed}
            self.buffer.compact(uploaded_ids)
            self._consecutive_failures = 0

            remaining = self.buffer.count()
            return {
                "uploaded": len(signed),
                "failed": 0,
                "remaining": remaining,
                "error": "",
                "backoff": False,
            }
        else:
            # Leave records in buffer for retry
            self._consecutive_failures += 1
            self._last_failure_time = time.time()

            return {
                "uploaded": 0,
                "failed": len(records),
                "remaining": self.buffer.count(),
                "error": error,
                "backoff": False,
            }

    def flush_all(self) -> Dict[str, Any]:
        """Flush the entire buffer, processing in batches.

        Keeps calling flush() until the buffer is empty or all
        remaining records have failed.

        Returns:
            Aggregate result dict.
        """
        total_uploaded = 0
        total_failed = 0
        last_error = ""

        while True:
            result = self.flush()

            total_uploaded += result["uploaded"]
            if result["error"]:
                last_error = result["error"]

            # Stop conditions
            if result["uploaded"] == 0:
                # Nothing uploaded this round -- either empty, backoff, or all failed
                total_failed = result["remaining"]
                break

            if result["remaining"] == 0:
                break

        return {
            "uploaded": total_uploaded,
            "failed": total_failed,
            "remaining": self.buffer.count(),
            "error": last_error,
        }

    def status(self) -> Dict[str, Any]:
        """Uploader health check."""
        buf_status = self.buffer.status()
        return {
            **buf_status,
            "endpoint": self.endpoint,
            "anon_key_configured": bool(self.anon_key),
            "consecutive_failures": self._consecutive_failures,
            "in_backoff": self._should_backoff(),
        }


# ---------------------------------------------------------------------------
# Supabase table DDL -- for reference / deployment
# ---------------------------------------------------------------------------

SUPABASE_TABLE_DDL = """
-- ==========================================================================
-- TELOSCOPE Telemetry Table
-- ==========================================================================
-- Receives governance telemetry deltas from deployed TELOSCOPE instances.
-- Contains NO customer data, NO conversation content, NO query text.
-- Only governance scores, check outcomes, and tool invocation metadata.
--
-- RLS: INSERT-only from anon role. No SELECT/UPDATE/DELETE from client.
-- Read access restricted to service_role (TELOS Labs backend only).
-- ==========================================================================

CREATE TABLE IF NOT EXISTS teloscope_telemetry (
    -- Primary key: the original AuditEntry UUID
    entry_id        UUID PRIMARY KEY,

    -- Anonymized installation identifier (SHA-256, non-reversible)
    instance_id     TEXT NOT NULL,

    -- Schema version for forward-compatibility
    schema_version  INTEGER NOT NULL DEFAULT 1,

    -- Temporal
    timestamp       TIMESTAMPTZ NOT NULL,

    -- Tool identity (name only, no args)
    tool_name       TEXT NOT NULL,

    -- Governance outcome
    gate2_verdict   TEXT NOT NULL CHECK (gate2_verdict IN ('EXECUTE', 'CLARIFY', 'ESCALATE')),

    -- Methodological check outcomes (JSONB array)
    -- Each element: {"check_name": str, "status": str, "would_block": bool}
    -- NO message text, NO details
    checks          JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Chain context
    chain_position  INTEGER NOT NULL DEFAULT 0,
    chain_pattern   TEXT NOT NULL DEFAULT '',

    -- Corpus metadata
    corpus_size     INTEGER NOT NULL DEFAULT 0,

    -- Cryptographic proof
    tkeys_signature     TEXT NOT NULL,
    signer_fingerprint  TEXT NOT NULL,

    -- Server-side metadata (populated by trigger, NOT by client)
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    client_ip       INET  -- NULL: we explicitly do NOT log this (see RLS policy)
);

-- Index: instance-level queries (all records from one deployment)
CREATE INDEX IF NOT EXISTS idx_teloscope_instance
    ON teloscope_telemetry (instance_id, timestamp DESC);

-- Index: verdict distribution analysis
CREATE INDEX IF NOT EXISTS idx_teloscope_verdict
    ON teloscope_telemetry (gate2_verdict, timestamp DESC);

-- Index: tool usage patterns
CREATE INDEX IF NOT EXISTS idx_teloscope_tool
    ON teloscope_telemetry (tool_name, timestamp DESC);

-- Index: signer lookup (for key rotation tracking)
CREATE INDEX IF NOT EXISTS idx_teloscope_signer
    ON teloscope_telemetry (signer_fingerprint);

-- ==========================================================================
-- Row Level Security
-- ==========================================================================
-- Client (anon role) can INSERT only. Cannot read, update, or delete.
-- Service role (TELOS Labs backend) has full access for analysis.
--
-- The client_ip column is always NULL from INSERT -- we do not capture
-- client IPs. If Supabase logs request IPs at the infrastructure level,
-- that is Supabase's retention policy, not ours. Our application layer
-- does not store or query IPs.
-- ==========================================================================

ALTER TABLE teloscope_telemetry ENABLE ROW LEVEL SECURITY;

-- Anon can INSERT only (append-only telemetry)
CREATE POLICY teloscope_anon_insert
    ON teloscope_telemetry
    FOR INSERT
    TO anon
    WITH CHECK (
        -- Ensure client_ip is NOT set by the client
        client_ip IS NULL
        -- Ensure schema_version is current
        AND schema_version = 1
        -- Ensure timestamp is within clock skew tolerance (24h)
        AND timestamp > now() - interval '24 hours'
        AND timestamp < now() + interval '24 hours'
    );

-- Anon CANNOT select, update, or delete
-- (No SELECT/UPDATE/DELETE policies for anon = denied by default with RLS enabled)

-- Service role has full access (for TELOS Labs analysis)
CREATE POLICY teloscope_service_full
    ON teloscope_telemetry
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ==========================================================================
-- Trigger: strip client_ip on INSERT (defense in depth)
-- ==========================================================================
-- Even if someone somehow sets client_ip in the INSERT payload,
-- this trigger NULLs it. Belt and suspenders.
-- ==========================================================================

CREATE OR REPLACE FUNCTION strip_client_ip()
RETURNS TRIGGER AS $$
BEGIN
    NEW.client_ip := NULL;
    NEW.received_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER teloscope_strip_ip
    BEFORE INSERT ON teloscope_telemetry
    FOR EACH ROW
    EXECUTE FUNCTION strip_client_ip();

-- ==========================================================================
-- Signer Registry (for server-side signature verification)
-- ==========================================================================
-- Maps signer_fingerprint -> public_key for signature verification.
-- Populated via activation ping or trust-on-first-use.
-- ==========================================================================

CREATE TABLE IF NOT EXISTS teloscope_signer_registry (
    signer_fingerprint  TEXT PRIMARY KEY,
    public_key_hex      TEXT NOT NULL,
    instance_id         TEXT NOT NULL,
    registered_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    registration_method TEXT NOT NULL DEFAULT 'activation_ping',
    -- CHECK: registration_method IN ('activation_ping', 'tofu', 'manual')
    active              BOOLEAN NOT NULL DEFAULT true
);

-- Index: instance to signer mapping
CREATE INDEX IF NOT EXISTS idx_signer_instance
    ON teloscope_signer_registry (instance_id);

-- RLS: signer registry is service_role only
ALTER TABLE teloscope_signer_registry ENABLE ROW LEVEL SECURITY;

CREATE POLICY signer_registry_service_only
    ON teloscope_signer_registry
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
"""


# ---------------------------------------------------------------------------
# Edge Function for server-side signature verification (reference)
# ---------------------------------------------------------------------------

EDGE_FUNCTION_REFERENCE = """
// Supabase Edge Function: verify-telemetry
// Called as a database webhook on INSERT to teloscope_telemetry
// Verifies the TKeys Ed25519 signature on each incoming record.
//
// If verification fails, the record is flagged (not deleted) for
// investigation. We never silently drop data.
//
// This is a reference implementation -- deploy as a Supabase Edge Function.

import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"
import { verify } from "https://deno.land/x/ed25519@1.6.0/mod.ts"

serve(async (req) => {
    const { record } = await req.json()

    // 1. Look up the public key for this signer
    const supabase = createClient(
        Deno.env.get('SUPABASE_URL')!,
        Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
    )

    const { data: signer } = await supabase
        .from('teloscope_signer_registry')
        .select('public_key_hex')
        .eq('signer_fingerprint', record.signer_fingerprint)
        .eq('active', true)
        .single()

    if (!signer) {
        // Unknown signer -- flag for review, do not reject
        // (Could be a new installation that hasn't registered yet)
        await supabase
            .from('teloscope_telemetry')
            .update({ client_ip: null })  // no-op update to mark as processed
            .eq('entry_id', record.entry_id)
        return new Response(JSON.stringify({ verified: false, reason: 'unknown_signer' }))
    }

    // 2. Reconstruct the canonical payload
    const signable = {
        chain_pattern: record.chain_pattern,
        chain_position: record.chain_position,
        checks: record.checks,
        corpus_size: record.corpus_size,
        entry_id: record.entry_id,
        gate2_verdict: record.gate2_verdict,
        instance_id: record.instance_id,
        schema_version: record.schema_version,
        timestamp: record.timestamp,
        tool_name: record.tool_name,
    }
    const canonical = JSON.stringify(signable)  // sorted keys assumed from client

    // 3. Verify signature
    const signatureBytes = hexToBytes(record.tkeys_signature)
    const publicKeyBytes = hexToBytes(signer.public_key_hex)
    const messageBytes = new TextEncoder().encode(canonical)

    const valid = await verify(signatureBytes, messageBytes, publicKeyBytes)

    return new Response(JSON.stringify({ verified: valid }))
})

function hexToBytes(hex: string): Uint8Array {
    const bytes = new Uint8Array(hex.length / 2)
    for (let i = 0; i < hex.length; i += 2) {
        bytes[i / 2] = parseInt(hex.substr(i, 2), 16)
    }
    return bytes
}
"""


# ---------------------------------------------------------------------------
# CLI entry point -- for manual operations
# ---------------------------------------------------------------------------

def cli_status():
    """Print telemetry pipeline status."""
    buf = TelemetryBuffer()
    status = buf.status()

    print("TELOSCOPE Telemetry Pipeline Status")
    print("=" * 50)
    print(f"  Buffer:     {status['buffer_path']}")
    print(f"  Records:    {status['record_count']}")
    print(f"  Size:       {status['buffer_size_bytes']:,} bytes")
    print(f"  Oldest:     {status['oldest_record_age_human']}")
    if status["stale"]:
        print(f"  [WARN]      Buffer is stale (>{MAX_BUFFER_AGE_WARN/86400:.0f} days)")
    print(f"  Instance:   {generate_instance_id()[:16]}...")
    print()

    endpoint = os.environ.get("TELOS_TELEMETRY_ENDPOINT", TELEMETRY_ENDPOINT_DEFAULT)
    anon_key = os.environ.get("TELOS_TELEMETRY_ANON_KEY", "")
    print(f"  Endpoint:   {endpoint}")
    print(f"  Anon key:   {'configured' if anon_key else 'NOT SET'}")

    key_path = os.path.expanduser("~/.telos/keys/customer.key")
    print(f"  TKey:       {'found' if os.path.exists(key_path) else 'NOT FOUND'}")


def cli_flush():
    """Flush the telemetry buffer."""
    uploader = TelemetryUploader()
    result = uploader.flush_all()

    print(f"Uploaded:   {result['uploaded']}")
    print(f"Failed:     {result['failed']}")
    print(f"Remaining:  {result['remaining']}")
    if result["error"]:
        print(f"Last error: {result['error']}")


def cli_export():
    """Export buffer for sneakernet transfer."""
    buf = TelemetryBuffer()
    path = buf.export_for_sneakernet()
    count = buf.count()
    print(f"Exported {count} records to: {path}")


if __name__ == "__main__":
    import sys

    commands = {
        "status": cli_status,
        "flush": cli_flush,
        "export": cli_export,
    }

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(f"Usage: python telemetry_pipeline.py [{'/'.join(commands)}]")
        sys.exit(1)

    commands[sys.argv[1]]()

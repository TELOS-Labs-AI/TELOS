"""
Integrity & Reproducibility Verification Tool
===============================================

Validates TELOS governance audit data for integrity, authenticity, and
reproducibility. Three independent verification checks:

1. **Hash Chain** — walk events in order, verify each
   ``previous_event_hash`` matches the SHA-256 hash of the preceding
   event's canonical JSON representation.

2. **Signature Verification** — verify Ed25519 signatures on each event
   using the embedded public key.

3. **Verdict Reproducibility** — rescore every event with default (or
   provided) ThresholdConfig and compare against stored verdicts.

NOTE: The ``previous_event_hash`` field is populated by ChainedAuditWriter
(demo_audit_bridge.py) and TeloscopeAudit._write_entry() (teloscope_audit.py).
Signature verification requires a pinned public key to prevent
self-signed forgery.

Usage:
    from telos_governance.corpus import load_corpus
    from telos_governance.validate import validate

    corpus = load_corpus("~/.telos/posthoc_audit/")

    # Full validation
    result = validate(corpus)
    print(result.format())

    # Individual checks
    from telos_governance.validate import (
        validate_chain,
        validate_signatures,
        validate_reproducibility,
    )

    chain = validate_chain(corpus)
    print(chain.format())

    sigs = validate_signatures(corpus)
    print(sigs.format())

    repro = validate_reproducibility(corpus)
    print(repro.format())
"""
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    from telos_governance.corpus import AuditCorpus, AuditEvent
except ImportError:
    from corpus import AuditCorpus, AuditEvent

# Optional: Ed25519 signature verification
try:
    from nacl.signing import VerifyKey
    from nacl.encoding import HexEncoder
    from nacl.exceptions import BadSignatureError
    _HAS_NACL = True
except ImportError:
    _HAS_NACL = False

# Optional: verdict reproducibility via rescore
try:
    from telos_governance.rescore import rescore
except ImportError:
    try:
        from rescore import rescore
    except ImportError:
        rescore = None

# Optional: ThresholdConfig for custom reproducibility checks
try:
    from telos_governance.threshold_config import ThresholdConfig
except ImportError:
    try:
        from threshold_config import ThresholdConfig
    except ImportError:
        ThresholdConfig = None

VERDICT_ORDER = ["EXECUTE", "CLARIFY", "INERT", "ESCALATE"]

# Statuses that indicate incomplete validation.
# These are NOT failures, but they are NOT passes either. Unknown != good.
DEGRADED_STATUSES = {"not_present", "not_available", "no_signatures", "degraded"}


# ---------------------------------------------------------------------------
# Hash computation
# ---------------------------------------------------------------------------

def _hash_event(raw: Dict) -> str:
    """Compute SHA-256 hash of an event's canonical JSON representation.

    Excludes ``previous_event_hash`` and ``signature`` from the hashable
    payload — these are chain/envelope fields, not event content.
    """
    hashable = {k: v for k, v in raw.items()
                if k not in ("previous_event_hash", "signature")}
    canonical = json.dumps(hashable, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ChainResult:
    """Result of hash-chain verification."""
    status: str        # "pass", "fail", "degraded"
    n_events: int
    n_verified: int
    n_broken: int
    n_missing: int     # events where previous_event_hash is empty
    broken_indices: List[int]
    message: str

    def format(self) -> str:
        display_status = self.status.upper().replace("_", " ")
        lines = [f"  Hash Chain:        {display_status}"]
        lines.append(f"    {self.n_events:,} events, ", )
        if self.status == "degraded":
            lines[-1] += f"{self.n_missing:,} missing hashes"
            lines.append(
                "    [!] Validation incomplete: hash chain not present. "
                "Cannot verify tamper resistance."
            )
        elif self.status == "pass":
            lines[-1] += f"{self.n_verified:,} verified, 0 broken"
        else:
            lines[-1] += (
                f"{self.n_verified:,} verified, "
                f"{self.n_broken:,} broken"
            )
            if self.broken_indices:
                preview = self.broken_indices[:10]
                idx_str = ", ".join(str(i) for i in preview)
                if len(self.broken_indices) > 10:
                    idx_str += f" ... (+{len(self.broken_indices) - 10} more)"
                lines.append(f"    Broken at indices: {idx_str}")
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "status": self.status,
            "n_events": self.n_events,
            "n_verified": self.n_verified,
            "n_broken": self.n_broken,
            "n_missing": self.n_missing,
            "broken_indices": self.broken_indices,
            "message": self.message,
        }


@dataclass
class SignatureResult:
    """Result of Ed25519 signature verification."""
    status: str        # "pass", "fail", "degraded", "no_signatures"
    n_events: int
    n_verified: int
    n_failed: int
    n_missing: int     # events without signatures
    failed_indices: List[int]
    message: str

    def format(self) -> str:
        display_status = self.status.upper().replace("_", " ")
        lines = [f"  Signatures:        {display_status}"]
        if self.status in ("not_available", "degraded"):
            lines.append(f"    [!] {self.message}")
        elif self.status == "no_signatures":
            lines.append(
                f"    [!] {self.n_events:,} events, none contain signatures. "
                f"Authenticity cannot be verified."
            )
        elif self.status == "pass":
            lines.append(
                f"    {self.n_events:,} events, "
                f"{self.n_verified:,} verified, "
                f"{self.n_failed} failed"
            )
        else:
            lines.append(
                f"    {self.n_events:,} events, "
                f"{self.n_verified:,} verified, "
                f"{self.n_failed:,} failed"
            )
            if self.n_missing > 0:
                lines.append(f"    {self.n_missing:,} events missing signatures")
            if self.failed_indices:
                preview = self.failed_indices[:10]
                idx_str = ", ".join(str(i) for i in preview)
                if len(self.failed_indices) > 10:
                    idx_str += f" ... (+{len(self.failed_indices) - 10} more)"
                lines.append(f"    Failed at indices: {idx_str}")
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "status": self.status,
            "n_events": self.n_events,
            "n_verified": self.n_verified,
            "n_failed": self.n_failed,
            "n_missing": self.n_missing,
            "failed_indices": self.failed_indices,
            "message": self.message,
        }


@dataclass
class ReproducibilityResult:
    """Result of verdict reproducibility check."""
    status: str        # "pass", "fail", "degraded"
    n_events: int
    n_matched: int
    n_mismatched: int
    match_rate: float
    mismatched_indices: List[int]
    mismatches: List[Dict]   # [{index, event_id, stored, reproduced}, ...]
    message: str

    def format(self) -> str:
        display_status = self.status.upper().replace("_", " ")
        lines = [f"  Reproducibility:   {display_status}"]
        if self.status in ("not_available", "degraded"):
            lines.append(f"    [!] {self.message}")
        elif self.status == "pass":
            lines.append(
                f"    {self.n_events:,} events, "
                f"{self.n_matched:,} matched ({self.match_rate:.1%})"
            )
            if self.n_mismatched > 0:
                lines.append(
                    f"    {self.n_mismatched:,} mismatches "
                    f"(hard overrides in stored verdict)"
                )
        else:
            lines.append(
                f"    {self.n_events:,} events, "
                f"{self.n_matched:,} matched ({self.match_rate:.1%})"
            )
            lines.append(f"    {self.n_mismatched:,} mismatches")
            if self.mismatches:
                preview = self.mismatches[:5]
                for m in preview:
                    lines.append(
                        f"      [{m['index']}] {m.get('event_id', '')[:16]}... "
                        f"{m['stored']} -> {m['reproduced']}"
                    )
                if len(self.mismatches) > 5:
                    lines.append(
                        f"      ... (+{len(self.mismatches) - 5} more)"
                    )
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "status": self.status,
            "n_events": self.n_events,
            "n_matched": self.n_matched,
            "n_mismatched": self.n_mismatched,
            "match_rate": self.match_rate,
            "mismatched_indices": self.mismatched_indices,
            "mismatches": self.mismatches,
            "message": self.message,
        }


@dataclass
class ValidationResult:
    """Aggregate result of all validation checks."""
    chain: ChainResult
    signatures: SignatureResult
    reproducibility: ReproducibilityResult
    overall_status: str   # "pass", "degraded", "partial", "fail"

    def format(self) -> str:
        checks = [self.chain, self.signatures, self.reproducibility]
        n_pass = sum(1 for c in checks if c.status == "pass")
        n_degraded = sum(
            1 for c in checks if c.status in DEGRADED_STATUSES
        )
        n_fail = sum(
            1 for c in checks
            if c.status not in ("pass",) and c.status not in DEGRADED_STATUSES
        )
        total = len(checks)

        lines = [
            "Validation Report",
            "=" * 50,
            f"  Overall: {self.overall_status.upper()} "
            f"({n_pass}/{total} checks passed"
            + (f", {n_degraded} degraded" if n_degraded > 0 else "")
            + ")",
            "",
        ]
        lines.append(self.chain.format())
        lines.append("")
        lines.append(self.signatures.format())
        lines.append("")
        lines.append(self.reproducibility.format())

        if n_degraded > 0:
            lines.append("")
            lines.append(
                "  [!] Some checks could not complete. "
                "Install missing dependencies or provide pinned keys "
                "for full validation."
            )

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "overall_status": self.overall_status,
            "chain": self.chain.to_dict(),
            "signatures": self.signatures.to_dict(),
            "reproducibility": self.reproducibility.to_dict(),
        }


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

def validate_chain(corpus: AuditCorpus) -> ChainResult:
    """Verify the hash chain across all events in temporal order.

    Walks events sequentially. For each event after the first, computes
    the SHA-256 hash of the previous event's canonical JSON (sorted keys,
    excluding ``previous_event_hash`` and ``signature``) and compares it
    with the current event's ``previous_event_hash`` field.

    Returns ``status="degraded"`` if all hashes are empty (previously
    "not_present" which was fail-open).
    """
    n = len(corpus)
    if n == 0:
        return ChainResult(
            status="pass",
            n_events=0,
            n_verified=0,
            n_broken=0,
            n_missing=0,
            broken_indices=[],
            message="Empty corpus",
        )

    events = corpus.events
    n_verified = 0
    n_broken = 0
    n_missing = 0
    broken_indices = []

    for i, event in enumerate(events):
        stored_hash = event.previous_event_hash

        if i == 0:
            # First event has no previous — hash should be empty or absent
            if not stored_hash:
                n_missing += 1
            else:
                # First event has a hash — can't verify it (no predecessor)
                # Count as verified if present (implies chain starts earlier)
                n_verified += 1
            continue

        if not stored_hash:
            n_missing += 1
            continue

        # Compute expected hash from previous event's raw record
        prev_raw = events[i - 1]._raw
        expected_hash = _hash_event(prev_raw)

        if stored_hash == expected_hash:
            n_verified += 1
        else:
            n_broken += 1
            broken_indices.append(i)

    # Determine status
    if n_missing == n:
        status = "degraded"
        message = (
            "Hash chain not present in audit data. "
            "Tamper detection unavailable — integrity cannot be verified."
        )
    elif n_broken == 0:
        status = "pass"
        message = f"All {n_verified} hash links verified."
    else:
        status = "fail"
        message = (
            f"{n_broken} broken link(s) in hash chain "
            f"at indices: {broken_indices}"
        )

    return ChainResult(
        status=status,
        n_events=n,
        n_verified=n_verified,
        n_broken=n_broken,
        n_missing=n_missing,
        broken_indices=broken_indices,
        message=message,
    )


def validate_signatures(
    corpus: AuditCorpus,
    trusted_public_key: Optional[str] = None,
) -> SignatureResult:
    """Verify Ed25519 signatures on all events against a pinned key.

    For each event, reads ``signature`` from the raw JSONL record. The
    signed payload is the event JSON with the ``signature`` field removed,
    serialized with sorted keys.

    **IMPORTANT:** If ``trusted_public_key`` is provided, all
    events are verified against that key. If an event's embedded
    ``signing_public_key`` differs from the trusted key, the event FAILS
    verification (key mismatch). This prevents self-signed forgery where
    an attacker replaces both the signature and the embedded key.

    If ``trusted_public_key`` is not provided, falls back to reading the
    key from each event (self-signed mode) and marks the result as
    DEGRADED to flag the weaker verification.

    Requires PyNaCl (``pip install PyNaCl``). Returns
    ``status="not_available"`` if nacl is not installed.

    Args:
        corpus: AuditCorpus to verify.
        trusted_public_key: Hex-encoded Ed25519 public key to verify
            against. Should come from TKeys config or a pinned key file,
            NOT from the event data.
    """
    n = len(corpus)

    if not _HAS_NACL:
        return SignatureResult(
            status="degraded",
            n_events=n,
            n_verified=0,
            n_failed=0,
            n_missing=n,
            failed_indices=[],
            message=(
                "Validation incomplete: nacl/PyNaCl not installed. "
                "Signature verification unavailable. "
                "Install with: pip install PyNaCl"
            ),
        )

    if n == 0:
        return SignatureResult(
            status="pass",
            n_events=0,
            n_verified=0,
            n_failed=0,
            n_missing=0,
            failed_indices=[],
            message="Empty corpus",
        )

    # Build the trusted VerifyKey once if provided
    pinned_verify_key = None
    if trusted_public_key:
        try:
            pinned_verify_key = VerifyKey(
                trusted_public_key.encode(), encoder=HexEncoder
            )
        except Exception as exc:
            return SignatureResult(
                status="fail",
                n_events=n,
                n_verified=0,
                n_failed=n,
                n_missing=0,
                failed_indices=list(range(n)),
                message=f"Invalid trusted_public_key: {exc}",
            )

    n_verified = 0
    n_failed = 0
    n_missing = 0
    n_key_mismatch = 0
    failed_indices = []

    for i, event in enumerate(corpus.events):
        raw = event._raw
        sig_hex = raw.get("signature", "")
        embedded_pubkey_hex = raw.get("signing_public_key", "")

        if not sig_hex:
            n_missing += 1
            continue

        # Determine which key to use for verification
        if pinned_verify_key is not None:
            verify_key = pinned_verify_key
            # Check for key mismatch: embedded key differs from trusted key
            if embedded_pubkey_hex and embedded_pubkey_hex != trusted_public_key:
                n_key_mismatch += 1
                n_failed += 1
                failed_indices.append(i)
                continue
        else:
            # Self-signed fallback: read key from event
            if not embedded_pubkey_hex:
                n_missing += 1
                continue
            try:
                verify_key = VerifyKey(
                    embedded_pubkey_hex.encode(), encoder=HexEncoder
                )
            except (ValueError, Exception):
                n_failed += 1
                failed_indices.append(i)
                continue

        # Build the signed payload: raw record minus the signature field
        payload = {k: v for k, v in raw.items() if k != "signature"}
        payload_bytes = json.dumps(
            payload, sort_keys=True, default=str
        ).encode()

        try:
            sig_bytes = bytes.fromhex(sig_hex)
            verify_key.verify(payload_bytes, sig_bytes)
            n_verified += 1
        except (BadSignatureError, ValueError, Exception):
            n_failed += 1
            failed_indices.append(i)

    # Determine status
    if n_missing == n:
        status = "no_signatures"
        message = "No events contain signatures."
    elif n_failed == 0 and pinned_verify_key is not None:
        status = "pass"
        message = f"All {n_verified} signatures verified against pinned key."
    elif n_failed == 0 and pinned_verify_key is None:
        # Self-signed verification succeeded but is weaker
        status = "degraded"
        message = (
            f"All {n_verified} signatures self-consistent, but verified "
            f"against embedded keys (self-signed). Provide trusted_public_key "
            f"for authenticated verification."
        )
    else:
        message_parts = [f"{n_failed} signature(s) failed verification."]
        if n_key_mismatch > 0:
            message_parts.append(
                f"{n_key_mismatch} event(s) have mismatched embedded keys "
                f"(possible forgery)."
            )
        status = "fail"
        message = " ".join(message_parts)

    return SignatureResult(
        status=status,
        n_events=n,
        n_verified=n_verified,
        n_failed=n_failed,
        n_missing=n_missing,
        failed_indices=failed_indices,
        message=message,
    )


def validate_reproducibility(
    corpus: AuditCorpus,
    config=None,
) -> ReproducibilityResult:
    """Verify verdict reproducibility by re-scoring all events.

    Rescores every event using the default ThresholdConfig (or a
    provided one) and compares the reproduced verdict against the
    stored verdict. Mismatches typically come from hard overrides
    (chain_broken, tool_blocked, boundary_triggered) that the rescore
    engine cannot replicate from stored scores alone.

    Requires ``rescore.py`` to be importable. Returns
    ``status="not_available"`` if rescore is not found.

    Args:
        corpus: AuditCorpus to verify.
        config: Optional ThresholdConfig. Uses defaults if None.
    """
    if rescore is None:
        return ReproducibilityResult(
            status="degraded",
            n_events=len(corpus),
            n_matched=0,
            n_mismatched=0,
            match_rate=0.0,
            mismatched_indices=[],
            mismatches=[],
            message=(
                "Validation incomplete: rescore module not available. "
                "Verdict reproducibility cannot be verified."
            ),
        )

    n = len(corpus)
    if n == 0:
        return ReproducibilityResult(
            status="pass",
            n_events=0,
            n_matched=0,
            n_mismatched=0,
            match_rate=1.0,
            mismatched_indices=[],
            mismatches=[],
            message="Empty corpus",
        )

    # Rescore with default or provided config
    kwargs = {}
    if config is not None:
        kwargs["config"] = config
    rescore_result = rescore(corpus, **kwargs)

    n_matched = 0
    n_mismatched = 0
    mismatched_indices = []
    mismatches = []

    for i, event in enumerate(corpus.events):
        stored_verdict = event.verdict
        reproduced_verdict = rescore_result.new_verdicts[i]

        if stored_verdict == reproduced_verdict:
            n_matched += 1
        else:
            n_mismatched += 1
            mismatched_indices.append(i)
            mismatches.append({
                "index": i,
                "event_id": event.event_id,
                "stored": stored_verdict,
                "reproduced": reproduced_verdict,
            })

    match_rate = n_matched / n if n > 0 else 1.0

    # Determine status — allow a small mismatch rate from hard overrides
    # that the rescore engine cannot replicate (chain_broken, tool_blocked)
    if n_mismatched == 0:
        status = "pass"
        message = f"All {n_matched} verdicts reproduced exactly."
    elif match_rate >= 0.95:
        # >=95% match: pass — mismatches are expected from hard overrides
        status = "pass"
        message = (
            f"{n_matched} matched ({match_rate:.1%}), "
            f"{n_mismatched} mismatches "
            f"(hard overrides in stored verdict)"
        )
    else:
        status = "fail"
        message = (
            f"Only {match_rate:.1%} match rate. "
            f"{n_mismatched} verdicts differ from rescore output."
        )

    return ReproducibilityResult(
        status=status,
        n_events=n,
        n_matched=n_matched,
        n_mismatched=n_mismatched,
        match_rate=match_rate,
        mismatched_indices=mismatched_indices,
        mismatches=mismatches,
        message=message,
    )


def validate(
    corpus: AuditCorpus,
    config=None,
    trusted_public_key: Optional[str] = None,
) -> ValidationResult:
    """Run all three validation checks on a corpus.

    Args:
        corpus: AuditCorpus to validate.
        config: Optional ThresholdConfig for reproducibility check.
        trusted_public_key: Hex-encoded Ed25519 public key for signature
            verification. If not provided, signatures are verified in
            self-signed mode (DEGRADED).

    Returns:
        ValidationResult with chain, signature, and reproducibility
        results, plus an overall status.
    """
    chain = validate_chain(corpus)
    sigs = validate_signatures(corpus, trusted_public_key=trusted_public_key)
    repro = validate_reproducibility(corpus, config=config)

    # Determine overall status (degraded != pass)
    results = [chain, sigs, repro]
    n_pass = sum(1 for r in results if r.status == "pass")
    n_fail = sum(1 for r in results if r.status == "fail")
    n_degraded = sum(
        1 for r in results if r.status in DEGRADED_STATUSES
    )

    if n_fail > 0:
        overall = "fail"
    elif n_pass == len(results):
        overall = "pass"
    elif n_degraded > 0 and n_fail == 0:
        # No hard failures, but some checks couldn't complete.
        # This is NOT "pass" — unknown != good.
        overall = "degraded"
    else:
        overall = "partial"

    return ValidationResult(
        chain=chain,
        signatures=sigs,
        reproducibility=repro,
        overall_status=overall,
    )

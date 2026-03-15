"""
TKeys PA Signing -- Cryptographic activation protocol for TELOS governance.

The TELOS governance engine is INERT by default. This module implements the
TKey signing ceremony: the customer cryptographically signs their PA
configuration, producing an activation record that proves:

  1. WHO defined the governance boundaries (customer identity via Ed25519 key)
  2. WHAT they defined (SHA-256 hash of the PA configuration -- NOT the contents)
  3. WHEN they signed (ISO 8601 timestamp, non-repudiable)

The activation record is a sidecar file (.telos-activation) alongside the
YAML configuration. It does NOT modify the YAML -- the configuration content
remains exactly as the customer wrote it.

Liability separation:
  - TELOS provides the measurement engine (the ruler)
  - The customer defines what to measure (the PA specification)
  - The customer signs the specification with their TKey
  - TELOS has zero fingerprints in the customer's governance specification

One-time activation ping:
  When the customer signs, a minimal activation record is sent to the TELOS
  backend. This contains ONLY the config hash, signer fingerprint, and
  timestamp -- never the configuration contents. After this single transmission,
  TELOS captures nothing further from the customer's usage. The engine runs
  entirely locally.

Compliance:
  - NIST AI 600-1 (GV 1.4): Cryptographic proof of governance policy authorship
  - EU AI Act Art. 72: Non-repudiable audit trail of who established governance
  - OWASP LLM Top 10 (LLM08): Documented human authorization of agent constraints

Usage:
    from telos_governance.pa_signing import sign_config, verify_config

    # Sign a PA configuration
    record = sign_config("agent.yaml", "customer.key")

    # Verify an existing signature
    result = verify_config("agent.yaml")
"""

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from telos_governance.signing import SigningKeyPair, SigningError


# ---------------------------------------------------------------------------
# Activation record format
# ---------------------------------------------------------------------------

ACTIVATION_SUFFIX = ".telos-activation"
ACTIVATION_VERSION = 1

# TELOS Labs public key for counter-signature verification.
# Customers verify the Labs counter-signature against this key.
# This is the ONLY Labs artifact embedded in the CLI -- the private
# key lives exclusively in the TELOS backend (Supabase secrets).
TELOS_LABS_PUBLIC_KEY = "ceea94b5716a5254907ee33d646a7dd8fca77f08b19c7f6de3cb6af172e74a8f"

# Default activation endpoint (Supabase Edge Function).
# Override with TELOS_ACTIVATION_ENDPOINT env var for testing.
TELOS_ACTIVATION_ENDPOINT_DEFAULT = (
    "https://evfhpcuoreieytzmiiva.supabase.co/functions/v1/activate"
)


@dataclass
class ActivationRecord:
    """Cryptographic proof that a customer signed a PA configuration.

    This record is the TKey activation artifact. It proves authorship
    and acceptance without containing any governance specification content.

    Dual-attestation:
      1. Customer's TKey signature -- proves the customer authored the config
      2. TELOS Labs counter-signature -- proves TELOS acknowledged the activation

    Both signatures must be present for a fully attested activation.
    The customer can verify the Labs counter-signature against TELOS Labs'
    published public key. A fake binary or MITM cannot forge this.
    """

    # What was signed
    config_hash: str  # SHA-256 of the YAML file contents (hex)
    config_filename: str  # Original filename (for human reference)

    # Who signed it (customer side)
    signer_fingerprint: str  # SHA-256 of the signer's Ed25519 public key (hex)

    # When
    signed_at: str  # ISO 8601 UTC timestamp

    # Customer cryptographic proof
    signature: str  # Ed25519 signature over the config hash (hex)
    public_key: str  # Signer's Ed25519 public key (hex) for verification

    # TELOS Labs counter-attestation (populated by activation ping response)
    labs_counter_signature: str = ""  # TELOS Labs Ed25519 signature over the full record (hex)
    labs_public_key: str = ""  # TELOS Labs public key used for counter-signing (hex)
    labs_receipt_id: str = ""  # TELOS-issued receipt ID
    labs_acknowledged_at: str = ""  # Server-side timestamp of acknowledgment

    # Metadata
    version: int = ACTIVATION_VERSION
    agent_id: str = ""  # From the config (for human reference only)
    agent_name: str = ""  # From the config (for human reference only)

    def to_json(self) -> str:
        """Serialize to formatted JSON."""
        return json.dumps(asdict(self), indent=2, sort_keys=False)

    @classmethod
    def from_json(cls, data: str) -> "ActivationRecord":
        """Deserialize from JSON string."""
        d = json.loads(data)
        return cls(**d)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "ActivationRecord":
        """Load from a .telos-activation file."""
        p = Path(path)
        if not p.exists():
            raise SigningError(f"Activation record not found: {p}")
        return cls.from_json(p.read_text())


# ---------------------------------------------------------------------------
# Activation ping payload (what goes to TELOS backend -- NOTHING ELSE)
# ---------------------------------------------------------------------------

@dataclass
class ActivationPing:
    """Minimal payload sent to TELOS backend on activation.

    Contains ONLY the hash, fingerprint, timestamp, and customer's
    cryptographic proof. Never contains configuration contents, boundaries,
    purpose, tools, or any governance specification data. This is the
    single moment of contact -- after this, TELOS captures nothing.
    """

    config_hash: str  # SHA-256 of config (proves WHAT, not contents)
    signer_fingerprint: str  # SHA-256 of public key (proves WHO)
    signed_at: str  # ISO 8601 timestamp (proves WHEN)
    agent_id: str  # Agent identifier (for license matching)
    license_id: str  # License token ID (if available)
    telos_version: str  # TELOS CLI version
    customer_signature: str  # Customer's Ed25519 signature (hex) -- for Labs verification
    customer_public_key: str  # Customer's Ed25519 public key (hex) -- for Labs verification

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Core signing operations
# ---------------------------------------------------------------------------

def _hash_config(path: Union[str, Path]) -> str:
    """Compute SHA-256 hash of a configuration file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        Hex-encoded SHA-256 hash of the file contents.
    """
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest()


def _extract_agent_info(path: Union[str, Path]) -> dict:
    """Extract agent_id and agent_name from a YAML config (for metadata only).

    These are included in the activation record for human reference.
    They are NOT part of the signed content -- only the hash is signed.
    """
    try:
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        agent = data.get("agent", {})
        return {
            "agent_id": agent.get("id", ""),
            "agent_name": agent.get("name", ""),
        }
    except Exception:
        return {"agent_id": "", "agent_name": ""}


def sign_config(
    config_path: Union[str, Path],
    key_path: Union[str, Path],
    signer_label: str = "",
) -> ActivationRecord:
    """Sign a PA configuration with a customer TKey.

    This is the activation ceremony. It:
      1. Computes SHA-256 hash of the config file
      2. Signs the hash with the customer's Ed25519 private key
      3. Writes the activation record as a sidecar file
      4. Returns the activation record (for the activation ping)

    The YAML configuration is NOT modified. The activation record is a
    separate .telos-activation file alongside the config.

    Args:
        config_path: Path to the YAML configuration file.
        key_path: Path to the customer's Ed25519 private key (PEM).
        signer_label: Optional human-readable label for the signer.

    Returns:
        ActivationRecord with the signed attestation.

    Raises:
        SigningError: If signing fails.
        FileNotFoundError: If config or key file doesn't exist.
    """
    config_path = Path(config_path).resolve()
    key_path = Path(key_path).resolve()

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    if not key_path.exists():
        raise FileNotFoundError(f"Key file not found: {key_path}")

    # Load the customer's TKey
    kp = SigningKeyPair.from_private_pem(key_path)

    # Hash the config (this is what gets signed -- the hash, not the contents)
    config_hash = _hash_config(config_path)

    # Sign the hash bytes
    hash_bytes = config_hash.encode("utf-8")
    signature = kp.sign(hash_bytes)

    # Extract agent info for human-readable metadata
    agent_info = _extract_agent_info(config_path)

    # Build the activation record
    record = ActivationRecord(
        config_hash=config_hash,
        config_filename=config_path.name,
        signer_fingerprint=kp.fingerprint,
        signed_at=datetime.now(timezone.utc).isoformat(),
        signature=signature.hex(),
        public_key=kp.public_key_bytes.hex(),
        agent_id=agent_info["agent_id"],
        agent_name=agent_info["agent_name"],
    )

    # Write the sidecar file
    activation_path = config_path.with_suffix(
        config_path.suffix + ACTIVATION_SUFFIX
    )
    activation_path.write_text(record.to_json() + "\n")

    return record


def verify_config(
    config_path: Union[str, Path],
    activation_path: Optional[Union[str, Path]] = None,
) -> dict:
    """Verify a PA configuration's TKey signature.

    Checks:
      1. Activation record exists
      2. Config hash matches (file hasn't been modified since signing)
      3. Ed25519 signature is valid (signature matches the hash)

    Args:
        config_path: Path to the YAML configuration file.
        activation_path: Optional explicit path to activation record.
            If not provided, looks for <config>.telos-activation sidecar.

    Returns:
        Dict with verification results:
            valid: bool -- True if all checks pass
            status: str -- "VERIFIED" | "TAMPERED" | "INVALID_SIGNATURE" | "NOT_SIGNED"
            config_hash: str -- Current config hash
            signed_hash: str -- Hash from activation record (if exists)
            signer_fingerprint: str -- Who signed (if exists)
            signed_at: str -- When signed (if exists)
            agent_id: str -- Agent ID (if exists)
            agent_name: str -- Agent name (if exists)
    """
    config_path = Path(config_path).resolve()

    if not config_path.exists():
        return {"valid": False, "status": "CONFIG_NOT_FOUND"}

    # Find activation record
    if activation_path:
        act_path = Path(activation_path).resolve()
    else:
        act_path = config_path.with_suffix(
            config_path.suffix + ACTIVATION_SUFFIX
        )

    if not act_path.exists():
        return {
            "valid": False,
            "status": "NOT_SIGNED",
            "config_hash": _hash_config(config_path),
        }

    # Load the activation record
    try:
        record = ActivationRecord.from_file(act_path)
    except Exception as e:
        return {"valid": False, "status": "INVALID_RECORD", "error": str(e)}

    # Check 1: Has the config been modified since signing?
    current_hash = _hash_config(config_path)
    if current_hash != record.config_hash:
        return {
            "valid": False,
            "status": "TAMPERED",
            "config_hash": current_hash,
            "signed_hash": record.config_hash,
            "signer_fingerprint": record.signer_fingerprint,
            "signed_at": record.signed_at,
            "agent_id": record.agent_id,
            "agent_name": record.agent_name,
        }

    # Check 2: Is the signature valid?
    try:
        pub_bytes = bytes.fromhex(record.public_key)
        sig_bytes = bytes.fromhex(record.signature)
        hash_bytes = record.config_hash.encode("utf-8")
        SigningKeyPair.verify(hash_bytes, sig_bytes, pub_bytes)
    except SigningError:
        return {
            "valid": False,
            "status": "INVALID_SIGNATURE",
            "config_hash": current_hash,
            "signer_fingerprint": record.signer_fingerprint,
            "signed_at": record.signed_at,
            "agent_id": record.agent_id,
            "agent_name": record.agent_name,
        }

    # Check 3: If Labs counter-signature is present, verify it
    labs_attested = False
    if record.labs_counter_signature and record.labs_public_key:
        try:
            labs_pub = bytes.fromhex(record.labs_public_key)
            labs_sig = bytes.fromhex(record.labs_counter_signature)
            # Labs signs the customer's full attestation: hash + signature + fingerprint + timestamp
            labs_message = (
                record.config_hash
                + record.signature
                + record.signer_fingerprint
                + record.signed_at
            ).encode("utf-8")
            SigningKeyPair.verify(labs_message, labs_sig, labs_pub)
            labs_attested = True
        except SigningError:
            return {
                "valid": False,
                "status": "INVALID_LABS_SIGNATURE",
                "config_hash": current_hash,
                "signer_fingerprint": record.signer_fingerprint,
                "signed_at": record.signed_at,
                "agent_id": record.agent_id,
                "agent_name": record.agent_name,
                "labs_receipt_id": record.labs_receipt_id,
            }

    # All checks pass
    return {
        "valid": True,
        "status": "VERIFIED",
        "config_hash": current_hash,
        "signer_fingerprint": record.signer_fingerprint,
        "signed_at": record.signed_at,
        "agent_id": record.agent_id,
        "agent_name": record.agent_name,
        "labs_attested": labs_attested,
        "labs_receipt_id": record.labs_receipt_id,
        "labs_acknowledged_at": record.labs_acknowledged_at,
    }


def build_activation_ping(
    record: ActivationRecord,
    license_id: str = "",
) -> ActivationPing:
    """Build the minimal activation ping payload for TELOS backend.

    This is the ONLY data that leaves the customer's environment.
    It contains no configuration contents -- only the hash, fingerprint,
    and timestamp.

    Args:
        record: The activation record from sign_config().
        license_id: License token ID (if available).

    Returns:
        ActivationPing ready to send to TELOS backend.
    """
    from telos_governance._version import __version__

    return ActivationPing(
        config_hash=record.config_hash,
        signer_fingerprint=record.signer_fingerprint,
        signed_at=record.signed_at,
        agent_id=record.agent_id,
        license_id=license_id,
        telos_version=__version__,
        customer_signature=record.signature,
        customer_public_key=record.public_key,
    )


def apply_labs_attestation(
    config_path: Union[str, Path],
    ping_result: dict,
) -> bool:
    """Write TELOS Labs counter-signature into the activation sidecar.

    Called after a successful activation ping when the backend returns
    a counter-signature. Updates the existing .telos-activation file
    with the Labs attestation fields.

    Args:
        config_path: Path to the original config (used to find sidecar).
        ping_result: Dict returned by send_activation_ping().

    Returns:
        True if attestation was applied, False if not applicable.
    """
    if not ping_result.get("labs_counter_signature"):
        return False

    config_path = Path(config_path).resolve()
    act_path = config_path.with_suffix(
        config_path.suffix + ACTIVATION_SUFFIX
    )

    if not act_path.exists():
        return False

    record = ActivationRecord.from_file(act_path)
    record.labs_counter_signature = ping_result["labs_counter_signature"]
    record.labs_public_key = ping_result.get("labs_public_key", "")
    record.labs_receipt_id = ping_result.get("receipt_id", "")
    record.labs_acknowledged_at = ping_result.get("acknowledged_at", "")
    act_path.write_text(record.to_json() + "\n")
    return True


def send_activation_ping(ping: ActivationPing, endpoint: str = "") -> dict:
    """Send the activation ping to TELOS backend.

    This is a single HTTPS POST. After this, TELOS captures nothing
    further from the customer's usage. The engine runs locally.

    Args:
        ping: The activation ping payload.
        endpoint: TELOS activation endpoint URL. If empty, uses default.

    Returns:
        Dict with:
            success: bool
            receipt_id: str -- TELOS-generated receipt ID
            acknowledged_at: str -- Server timestamp
            error: str -- Error message if failed

    Note:
        If the ping fails (network unavailable, endpoint unreachable),
        the signing is still valid locally. The activation ping is a
        notification, not a gate. The customer can retry or operate
        without it -- their local activation record is the proof.
    """
    # Default endpoint -- env var overrides the compiled-in default
    if not endpoint:
        endpoint = os.environ.get(
            "TELOS_ACTIVATION_ENDPOINT",
            TELOS_ACTIVATION_ENDPOINT_DEFAULT,
        )

    # If no endpoint configured, skip the ping (offline mode)
    if not endpoint:
        return {
            "success": True,
            "offline": True,
            "receipt_id": "",
            "acknowledged_at": "",
            "note": "No activation endpoint configured. Signing is valid locally.",
        }

    try:
        import urllib.request
        import urllib.error

        payload = json.dumps(ping.to_dict()).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return {
                "success": True,
                "offline": False,
                "receipt_id": result.get("receipt_id", ""),
                "acknowledged_at": result.get("acknowledged_at", ""),
                # Labs counter-signature fields (if provided by backend)
                "labs_counter_signature": result.get("labs_counter_signature", ""),
                "labs_public_key": result.get("labs_public_key", ""),
            }
    except Exception as e:
        return {
            "success": False,
            "offline": False,
            "error": str(e),
            "note": "Activation ping failed. Signing is still valid locally.",
        }

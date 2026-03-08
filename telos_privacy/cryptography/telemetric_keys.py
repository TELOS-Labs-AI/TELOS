"""
Telemetric Keys: Cryptographic access control derived from session telemetry.

Uses ephemeral session telemetry as a supplementary entropy source for continuous
key rotation. Keys are non-reproducible, session-bound, and evolve with each
turn based on actual interaction patterns.

All primitives are NIST-approved:
- AES-256-GCM (NIST FIPS 197) for authenticated encryption
- HKDF (RFC 5869, NIST SP 800-56C) for key derivation
- SHA3-256 (NIST FIPS 202) for entropy accumulation
- CSPRNG (secrets module) for entropy floor at every rotation

Core Properties:
1. Non-reproducible: Cannot recreate keys without exact session telemetry
2. Continuous evolution: Keys rotate every turn with CSPRNG + telemetry entropy
3. Session-bound: Keys exist only during live session, destroyed afterward
4. Forward secrecy: Previous keys unrecoverable even if current key compromised
5. Lightweight: Single HKDF derivation + AES per turn

Hardened per 5-agent cryptographic review (2026-02-08):
- CSPRNG injection at every rotation (128-bit entropy floor)
- HKDF replaces raw SHA3(key||data) concatenation
- Key versioning (version byte prefix on ciphertext)
- No raw key getters (keys never leave the module)
- bytearray + ctypes.memset for key destruction
- Bounded key history (deque, maxlen=100)

Known Limitations:
- Session-bound only: Keys die with the session. No persistent key storage.
  For encryption-at-rest, use a separate AES-256-GCM layer with file-derived keys
  (see telos_governance/crypto_layer.py for PA config encryption).
- No Ed25519: This module provides HMAC-SHA512 signatures (symmetric, session-bound).
  For asymmetric signatures (verifiable by third parties without shared secrets),
  use Ed25519 (see telos_governance/receipt_signer.py).
- No key export: By design, keys cannot be exported. Data encrypted in one session
  cannot be decrypted in another. Use TelemetricAccessControl with a master key
  hierarchy for cross-session access.
- Memory zeroing is best-effort: Python's garbage collector may copy key material
  before ctypes.memset runs. PyPy and alternative runtimes are untested.
"""

import ctypes
import hashlib
import hmac
import secrets
import time
import base64
from collections import deque
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import json

# Production encryption and key derivation
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

# Current ciphertext format version
_KEY_VERSION = b'\x01'


def _zero_bytearray(ba: bytearray) -> None:
    """Securely zero a bytearray using ctypes.memset."""
    if len(ba) > 0:
        ctypes.memset(
            (ctypes.c_char * len(ba)).from_buffer(ba), 0, len(ba)
        )


@dataclass
class TelemetricKeyState:
    """
    Current state of telemetric key evolution.

    Keys evolve continuously based on session telemetry. Each turn produces
    new entropy that mixes with previous state to generate next key.
    """
    session_id: str
    current_key: bytearray
    turn_number: int
    entropy_pool: bytearray = field(default_factory=lambda: bytearray(secrets.token_bytes(32)))
    key_history_hash: bytearray = field(default_factory=lambda: bytearray(32))
    created_at: float = field(default_factory=time.time)
    last_rotation: float = field(default_factory=time.time)

    def __post_init__(self):
        """Validate key material sizes."""
        if len(self.current_key) != 32:
            raise ValueError(f"Key must be 32 bytes, got {len(self.current_key)}")
        if len(self.entropy_pool) != 32:
            raise ValueError(f"Entropy pool must be 32 bytes, got {len(self.entropy_pool)}")
        self._ephemeral = True


@dataclass
class EncryptedPayload:
    """
    Encrypted data with metadata for decryption.

    Contains all information needed to decrypt (except the key itself).
    Safe to transmit/store - only readable with correct telemetric key.

    The optional telos_signature field contains an HMAC-SHA512 signature
    over the governance data, providing the TELOS authentication stamp.
    """
    ciphertext: bytes
    nonce: bytes
    session_id: str
    turn_number: int
    timestamp: float
    telos_signature: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict (for JSON storage/transmission)."""
        d = {
            "ciphertext": base64.b64encode(self.ciphertext).decode('utf-8'),
            "nonce": base64.b64encode(self.nonce).decode('utf-8'),
            "session_id": self.session_id,
            "turn_number": self.turn_number,
            "timestamp": self.timestamp
        }
        if self.telos_signature is not None:
            d["telos_signature"] = self.telos_signature
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptedPayload':
        """Deserialize from dict."""
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            nonce=base64.b64decode(data["nonce"]),
            session_id=data["session_id"],
            turn_number=data["turn_number"],
            timestamp=data["timestamp"],
            telos_signature=data.get("telos_signature")
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'EncryptedPayload':
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


class TelemetricKeyGenerator:
    """
    Generates cryptographic keys from session telemetry entropy.

    Uses HKDF (RFC 5869) for key derivation with session telemetry and
    CSPRNG as entropy sources. Keys cannot be reproduced without
    recreating exact session telemetry sequence.

    Security Properties:
    - Forward secrecy: Previous keys unrecoverable even if current key compromised
    - Session isolation: Keys die with session, no cross-session correlation
    - CSPRNG floor: 128-bit minimum entropy at every rotation via secrets.token_bytes
    - Lightweight: Single HKDF derivation per turn
    """

    def __init__(self, session_id: str, initial_entropy: Optional[bytes] = None):
        """
        Initialize telemetric key generator for session.

        Args:
            session_id: Unique session identifier
            initial_entropy: Optional seed entropy (uses secure random if None)
        """
        self.session_id = session_id

        # Initialize with cryptographically secure random seed
        seed_entropy = initial_entropy or secrets.token_bytes(32)

        # Derive initial key using HKDF
        session_metadata = f"{session_id}:{time.time()}:{secrets.token_hex(16)}".encode()
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=session_metadata,
            info=b"telos-initial-key",
        )
        initial_key = hkdf.derive(seed_entropy)

        self.state = TelemetricKeyState(
            session_id=session_id,
            current_key=bytearray(initial_key),
            turn_number=0,
            entropy_pool=bytearray(seed_entropy[:32] if len(seed_entropy) >= 32 else seed_entropy.ljust(32, b'\x00')),
            key_history_hash=bytearray(hashlib.sha3_256(initial_key).digest())
        )

        self._turn_telemetry_history: deque = deque(maxlen=100)

        # Initialize AESGCM cipher with current key
        self._cipher = AESGCM(bytes(self.state.current_key))

    def extract_entropy_from_telemetry(self, turn_telemetry: Dict[str, Any]) -> bytes:
        """
        Extract cryptographic entropy from turn telemetry.

        Telemetry Entropy Sources:
        1. Timestamp microsecond precision (high-resolution timing)
        2. Delta_t_ms between turns (user interaction timing)
        3. Embedding distance float precision (computational variance)
        4. Fidelity score fluctuations (governance measurements)
        5. Lyapunov delta (dynamic system state)
        6. Intervention flags (boolean state transitions)

        Args:
            turn_telemetry: Telemetry dict with fields from TELOS Observatory

        Returns:
            32 bytes of entropy extracted from telemetry
        """
        entropy_components = []

        # 1. Timestamp precision (microseconds since epoch)
        timestamp = turn_telemetry.get("timestamp", time.time())
        entropy_components.append(str(timestamp).encode())

        # 2. Inter-turn timing (delta_t_ms)
        delta_t = turn_telemetry.get("delta_t_ms", 0)
        entropy_components.append(str(delta_t).encode())

        # 3. Embedding distance (float precision as entropy)
        embedding_distance = turn_telemetry.get("embedding_distance",
                                                turn_telemetry.get("distance_from_pa", 0.0))
        entropy_components.append(str(embedding_distance).encode())

        # 4. Fidelity measurements
        fidelity = turn_telemetry.get("fidelity_score", 0.0)
        soft_fidelity = turn_telemetry.get("soft_fidelity",
                                           turn_telemetry.get("user_pa_fidelity", 0.0))
        entropy_components.append(f"{fidelity}:{soft_fidelity}".encode())

        # 5. Lyapunov delta (dynamic system entropy)
        lyapunov = turn_telemetry.get("lyapunov_delta", 0.0)
        entropy_components.append(str(lyapunov).encode())

        # 6. State transitions (intervention flags)
        intervention = turn_telemetry.get("intervention_triggered", False)
        drift_flag = turn_telemetry.get("governance_drift_flag",
                                        turn_telemetry.get("in_basin", True))
        correction = turn_telemetry.get("governance_correction_applied", False)
        state_bits = f"{int(intervention)}{int(drift_flag)}{int(correction)}"
        entropy_components.append(state_bits.encode())

        # 7. Turn number (ensures monotonic evolution)
        turn_id = turn_telemetry.get("turn_id",
                                     turn_telemetry.get("turn_number", self.state.turn_number))
        entropy_components.append(str(turn_id).encode())

        # 8. User/model content length (interaction pattern entropy)
        user_input = turn_telemetry.get("user_input", "")
        model_output = turn_telemetry.get("model_output",
                                          turn_telemetry.get("response", ""))
        content_entropy = f"{len(user_input)}:{len(model_output)}".encode()
        entropy_components.append(content_entropy)

        # 9. Session ID binding (prevents cross-session key reuse)
        session_id = turn_telemetry.get("session_id", self.session_id)
        entropy_components.append(str(session_id).encode())

        # Combine all entropy sources with delimiters
        combined_entropy = b'|'.join(entropy_components)

        # Hash to produce uniform 32-byte entropy
        return hashlib.sha3_256(combined_entropy).digest()

    def rotate_key(self, turn_telemetry: Dict[str, Any]) -> None:
        """
        Rotate key based on turn telemetry using HKDF (RFC 5869).

        Key Evolution Algorithm:
        1. Extract entropy from current turn telemetry
        2. Inject CSPRNG bytes (128-bit entropy floor)
        3. Derive new key via HKDF with previous key + entropy as IKM
        4. Use entropy pool as salt, key history as info (context binding)
        5. Update state for next rotation

        Result: New key that depends on:
        - All previous turn telemetry (history via key chaining)
        - Current turn telemetry (fresh entropy)
        - CSPRNG injection (128-bit floor per rotation)
        - Accumulated entropy pool (randomness reservoir)

        Args:
            turn_telemetry: Telemetry dict for current turn
        """
        # Extract fresh entropy from this turn's telemetry
        turn_entropy = self.extract_entropy_from_telemetry(turn_telemetry)

        # CSPRNG injection: 128-bit entropy floor at every rotation
        csprng_entropy = secrets.token_bytes(16)

        # Assemble input key material: previous key + telemetry + CSPRNG
        ikm = bytes(self.state.current_key) + turn_entropy + csprng_entropy

        # Derive new key using HKDF (RFC 5869, NIST SP 800-56C)
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=bytes(self.state.entropy_pool),
            info=bytes(self.state.key_history_hash) + str(self.state.turn_number).encode(),
        )
        key_evolution = hkdf.derive(ikm)

        # Update key history hash (one-way accumulation, stays as SHA3)
        new_history_hash = hashlib.sha3_256(
            bytes(self.state.key_history_hash) + key_evolution
        ).digest()

        # Update entropy pool (mix old, new, and CSPRNG)
        new_entropy_pool = hashlib.sha3_256(
            bytes(self.state.entropy_pool) + turn_entropy + csprng_entropy
        ).digest()

        # Record telemetry (for audit/analysis, not key recovery)
        entropy_count = len([k for k, v in turn_telemetry.items() if v])
        self._turn_telemetry_history.append({
            "turn": self.state.turn_number,
            "timestamp": turn_telemetry.get("timestamp", time.time()),
            "entropy_sources": entropy_count
        })

        # Zero old key material before overwriting
        _zero_bytearray(self.state.current_key)
        _zero_bytearray(self.state.key_history_hash)
        _zero_bytearray(self.state.entropy_pool)

        # Update state with new key
        self.state.current_key = bytearray(key_evolution)
        self.state.key_history_hash = bytearray(new_history_hash)
        self.state.entropy_pool = bytearray(new_entropy_pool)
        self.state.turn_number += 1
        self.state.last_rotation = time.time()

        # Update cipher with new key
        self._cipher = AESGCM(key_evolution)

    def encrypt(self, plaintext: bytes, associated_data: Optional[bytes] = None) -> EncryptedPayload:
        """
        Encrypt data with current telemetric key using AES-256-GCM.

        Prepends a version byte to ciphertext for forward-compatible decryption.

        AES-256-GCM provides:
        - Confidentiality: Data is encrypted
        - Authenticity: Tampering is detected
        - Associated data binding: Metadata authenticated but not encrypted

        Args:
            plaintext: Data to encrypt
            associated_data: Optional authenticated but unencrypted metadata

        Returns:
            EncryptedPayload with versioned ciphertext and metadata
        """
        # Generate unique nonce (96 bits recommended for GCM)
        nonce = secrets.token_bytes(12)

        # Encrypt with AES-256-GCM
        raw_ciphertext = self._cipher.encrypt(nonce, plaintext, associated_data)

        # Prepend version byte for forward compatibility
        versioned_ciphertext = _KEY_VERSION + raw_ciphertext

        return EncryptedPayload(
            ciphertext=versioned_ciphertext,
            nonce=nonce,
            session_id=self.session_id,
            turn_number=self.state.turn_number,
            timestamp=time.time()
        )

    def decrypt(self, payload: EncryptedPayload, associated_data: Optional[bytes] = None) -> bytes:
        """
        Decrypt data encrypted with telemetric key.

        Reads and validates the version byte prefix before decrypting.

        Args:
            payload: EncryptedPayload to decrypt
            associated_data: Must match the associated_data used during encryption

        Returns:
            Decrypted plaintext

        Raises:
            ValueError: If version byte is unsupported
            cryptography.exceptions.InvalidTag: If authentication fails
        """
        ciphertext = payload.ciphertext

        # Read and validate version byte
        if len(ciphertext) < 2:
            raise ValueError("Ciphertext too short (missing version byte)")

        version = ciphertext[0:1]
        if version != _KEY_VERSION:
            raise ValueError(f"Unsupported ciphertext version: {version!r}")

        # Strip version byte and decrypt
        raw_ciphertext = ciphertext[1:]
        return self._cipher.decrypt(payload.nonce, raw_ciphertext, associated_data)

    def encrypt_governance_delta(self, governance_data: Dict[str, Any]) -> EncryptedPayload:
        """
        Encrypt governance delta for export.

        This is the primary use case - encrypting governance metrics
        (fidelity scores, interventions, drift events) before they
        leave the deployment.

        Args:
            governance_data: Dict with governance metrics from turn

        Returns:
            EncryptedPayload ready for export
        """
        plaintext = json.dumps(governance_data, default=str).encode('utf-8')
        associated_data = f"{self.session_id}:{self.state.turn_number}".encode()
        return self.encrypt(plaintext, associated_data)

    def decrypt_governance_delta(self, payload: EncryptedPayload) -> Dict[str, Any]:
        """
        Decrypt governance delta.

        Args:
            payload: EncryptedPayload from encrypt_governance_delta

        Returns:
            Dict with governance metrics
        """
        associated_data = f"{payload.session_id}:{payload.turn_number}".encode()
        plaintext = self.decrypt(payload, associated_data)
        return json.loads(plaintext.decode('utf-8'))

    def generate_hmac_signature(self, data: bytes) -> bytes:
        """
        Generate HMAC-SHA512 signature using the current telemetric key.

        The TELOS signature: proves that data was processed by a TELOS-governed
        session with a specific key evolution history. Unforgeable without
        possessing the exact session key.

        HMAC-SHA512 (FIPS 198-1, RFC 2104) works with any key length.
        The 256-bit session key provides full security for HMAC-SHA512.

        Args:
            data: Data to sign

        Returns:
            64-byte HMAC-SHA512 signature
        """
        h = hmac.new(bytes(self.state.current_key), data, hashlib.sha512)
        return h.digest()

    def verify_hmac_signature(self, data: bytes, signature: bytes) -> bool:
        """
        Verify HMAC-SHA512 signature in constant time.

        Args:
            data: Original data that was signed
            signature: Signature to verify (64 bytes)

        Returns:
            True if signature is valid
        """
        expected = self.generate_hmac_signature(data)
        return hmac.compare_digest(expected, signature)

    def get_key_metadata(self) -> Dict[str, Any]:
        """
        Get key metadata (no sensitive material).

        Returns metadata about key state without exposing actual keys.
        Safe for logging, telemetry export, audit trails.

        Returns:
            Dict with session_id, turn_number, rotation_count, etc.
        """
        return {
            "session_id": self.state.session_id,
            "turn_number": self.state.turn_number,
            "rotations": len(self._turn_telemetry_history),
            "session_age_seconds": time.time() - self.state.created_at,
            "last_rotation_seconds_ago": time.time() - self.state.last_rotation,
            "entropy_sources_active": self._turn_telemetry_history[-1]["entropy_sources"] if self._turn_telemetry_history else 0
        }

    def destroy(self):
        """
        Destroy all key material (end of session).

        Uses ctypes.memset to zero bytearray key material, preventing
        residual key data in memory. Keys are session-bound and must
        not persist after session ends.
        """
        # Zero key material with ctypes.memset
        _zero_bytearray(self.state.current_key)
        _zero_bytearray(self.state.entropy_pool)
        _zero_bytearray(self.state.key_history_hash)

        # Clear telemetry history
        self._turn_telemetry_history.clear()

        # Reinitialize cipher with garbage key (prevents use-after-destroy)
        self._cipher = AESGCM(secrets.token_bytes(32))

        # Mark as destroyed
        self.state.turn_number = -1


class TelemetricSessionManager:
    """
    Session manager for Telemetric Keys - integration-ready interface.

    This is the primary interface for integrating Telemetric Keys into
    the TELOS Observatory. Manages key lifecycle and provides simple
    encrypt/rotate methods that match the existing telemetry flow.

    Integration Example:
        # In beta_response_manager.py, after generate_turn_responses()
        manager = TelemetricSessionManager(session_id)
        encrypted_delta = manager.process_turn(turn_telemetry)
        # encrypted_delta ready for export
    """

    def __init__(self, session_id: str, master_key: Optional[bytes] = None):
        """
        Initialize session manager.

        Args:
            session_id: Unique session identifier
            master_key: Optional master key (for key derivation hierarchy)
        """
        self.session_id = session_id
        self._master_key_provided = master_key is not None

        # Create key generator with optional master key derivation
        if master_key:
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=session_id.encode(),
                info=b"telos-session-seed",
            )
            session_seed = hkdf.derive(master_key)
            self.key_generator = TelemetricKeyGenerator(session_id, session_seed)
        else:
            self.key_generator = TelemetricKeyGenerator(session_id)

        self._encrypted_history: List[EncryptedPayload] = []
        self._signatures_generated: int = 0
        self._is_active = True

    @staticmethod
    def _canonicalize(data: Dict[str, Any]) -> bytes:
        """
        Create deterministic byte representation for signing.

        Sorted keys + compact JSON separators ensure identical input
        regardless of dict insertion order.

        Args:
            data: Dict to canonicalize

        Returns:
            Canonical UTF-8 bytes
        """
        return json.dumps(
            dict(sorted(data.items())),
            sort_keys=True,
            separators=(',', ':'),
            default=str
        ).encode('utf-8')

    def sign_governance_delta(self, governance_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sign governance delta with HMAC-SHA512 — the TELOS stamp.

        Creates an unforgeable signature proving this data was produced
        by a TELOS-governed session with a specific key evolution history.

        The signature binds the governance data to:
        - The current session key (derived from all prior telemetry)
        - The session identity
        - The turn number
        - The key rotation history

        Args:
            governance_data: Governance metrics to sign

        Returns:
            Signature package with hex signature, algorithm, metadata
        """
        canonical = self._canonicalize(governance_data)
        signature = self.key_generator.generate_hmac_signature(canonical)

        self._signatures_generated += 1

        return {
            "signature": signature.hex(),
            "signature_algorithm": "HMAC-SHA512",
            "key_rotation_number": self.key_generator.state.turn_number,
            "timestamp": time.time(),
            "session_id": self.session_id,
            "canonical_hash": hashlib.sha3_256(canonical).hexdigest(),
        }

    def process_turn(self, turn_telemetry: Dict[str, Any]) -> EncryptedPayload:
        """
        Process a turn: rotate key, sign governance delta, and encrypt.

        This is the main integration point. Call this after each turn
        with the telemetry data from beta_response_manager.

        The returned EncryptedPayload includes a telos_signature field
        containing the HMAC-SHA512 signature over the governance data.

        Args:
            turn_telemetry: Dict with telemetry from generate_turn_responses()
                Expected fields (all optional, more = more entropy):
                - fidelity_score: float
                - distance_from_pa: float
                - intervention_triggered: bool
                - session_id: str
                - turn_number: int
                - user_input: str
                - response: str
                - timestamp: float (auto-added if missing)

        Returns:
            EncryptedPayload containing encrypted + signed governance delta
        """
        if not self._is_active:
            raise RuntimeError("Session has been destroyed")

        # Ensure timestamp exists
        if "timestamp" not in turn_telemetry:
            turn_telemetry["timestamp"] = time.time()

        # Rotate key based on telemetry entropy
        self.key_generator.rotate_key(turn_telemetry)

        # Assemble governance data
        governance_data = {
            "fidelity_score": turn_telemetry.get("fidelity_score"),
            "distance_from_pa": turn_telemetry.get("distance_from_pa"),
            "intervention_triggered": turn_telemetry.get("intervention_triggered"),
            "in_basin": turn_telemetry.get("in_basin"),
            "turn_number": turn_telemetry.get("turn_number", self.key_generator.state.turn_number),
            "timestamp": turn_telemetry["timestamp"],
            "session_id": self.session_id
        }

        # Sign governance data (TELOS stamp)
        telos_signature = self.sign_governance_delta(governance_data)

        # Encrypt governance data
        encrypted = self.key_generator.encrypt_governance_delta(governance_data)

        # Attach signature to payload
        encrypted.telos_signature = telos_signature

        self._encrypted_history.append(encrypted)

        return encrypted

    def encrypt(self, plaintext: bytes) -> EncryptedPayload:
        """
        Encrypt arbitrary data with the current session key.

        Args:
            plaintext: Data to encrypt

        Returns:
            EncryptedPayload with versioned ciphertext
        """
        if not self._is_active:
            raise RuntimeError("Session has been destroyed")
        return self.key_generator.encrypt(plaintext)

    def get_session_export(self) -> Dict[str, Any]:
        """
        Get all encrypted governance deltas for export.

        Returns:
            Dict with session metadata and list of encrypted payloads
        """
        return {
            "session_id": self.session_id,
            "total_turns": len(self._encrypted_history),
            "signatures_generated": self._signatures_generated,
            "created_at": self.key_generator.state.created_at,
            "encrypted_deltas": [p.to_dict() for p in self._encrypted_history],
            "key_metadata": self.key_generator.get_key_metadata()
        }

    def generate_session_proof(self) -> Dict[str, Any]:
        """
        Generate cryptographic proof document for the session.

        Creates an IP protection proof and audit-ready summary of the
        entire session's cryptographic activity. Includes the key history
        fingerprint (hash of all key evolutions) and signature counts.

        Call this at session end, before destroy().

        Returns:
            Session proof document suitable for IP documentation and audit
        """
        if not self._is_active:
            raise RuntimeError("Session has been destroyed")

        key_metadata = self.key_generator.get_key_metadata()

        return {
            "title": "TELOS Telemetric Signature - Session Proof",
            "session_id": self.session_id,
            "created_at": datetime.fromtimestamp(self.key_generator.state.created_at).isoformat(),
            "proof_generated_at": datetime.now().isoformat(),

            "session_summary": {
                "total_turns": len(self._encrypted_history),
                "signatures_generated": self._signatures_generated,
                "key_rotations": key_metadata["rotations"],
                "session_age_seconds": key_metadata["session_age_seconds"],
            },

            "cryptographic_evidence": {
                "encryption_algorithm": "AES-256-GCM (NIST FIPS 197)",
                "key_derivation": "HKDF (RFC 5869, NIST SP 800-56C)",
                "signature_algorithm": "HMAC-SHA512 (FIPS 198-1, RFC 2104)",
                "entropy_floor": "128-bit CSPRNG per rotation",
                "key_history_fingerprint": bytes(self.key_generator.state.key_history_hash).hex(),
            },

            "ip_claims": {
                "innovation": "Session telemetry as supplementary entropy for key derivation",
                "uniqueness": "Non-reproducible without exact telemetry sequence",
                "timestamp": "Cryptographically bound to session creation time",
                "ownership": "TELOS Labs proprietary implementation"
            },

            "verification": {
                "method": "Telemetric Signature v1.0",
                "can_verify": "Holders of session key can verify all signatures",
                "cannot_forge": "Requires exact telemetry sequence + CSPRNG state",
                "nist_compliant": "AES-256-GCM, HKDF, HMAC-SHA512"
            }
        }

    def destroy(self):
        """
        Destroy session and all key material.
        """
        self.key_generator.destroy()
        self._encrypted_history.clear()
        self._signatures_generated = 0
        self._is_active = False


class TelemetricAccessControl:
    """
    Access control for Intelligence Layer using Telemetric Keys.

    Core Concept:
    - Each session generates unique telemetric key stream
    - Session data encrypted with session-specific keys
    - Intelligence Layer aggregation uses master key hierarchy
    - TELOS LABS holds master keys for all telemetric gateways

    Access Levels:
    1. Session-level: Individual deployment can access own session data
    2. Deployment-level: Institution can access their deployment's aggregated data
    3. Intelligence Layer: Only TELOS LABS master keys can access cross-deployment insights
    """

    def __init__(self, master_key: Optional[bytes] = None):
        """
        Initialize access control with master key.

        Args:
            master_key: Master key for Intelligence Layer access (TELOS LABS only)
        """
        self._master_key = bytearray(master_key or secrets.token_bytes(32))
        self._session_managers: Dict[str, TelemetricSessionManager] = {}
        self._cipher = AESGCM(bytes(self._master_key))

    def create_session(self, session_id: str) -> TelemetricSessionManager:
        """
        Create session manager for new session.

        Args:
            session_id: Unique session identifier

        Returns:
            TelemetricSessionManager for this session
        """
        manager = TelemetricSessionManager(session_id, bytes(self._master_key))
        self._session_managers[session_id] = manager
        return manager

    def encrypt_for_intelligence_layer(self, data: bytes) -> EncryptedPayload:
        """
        Encrypt data with master key for Intelligence Layer.

        Only TELOS LABS can decrypt this data.

        Args:
            data: Data to encrypt

        Returns:
            EncryptedPayload readable only with master key
        """
        nonce = secrets.token_bytes(12)
        ciphertext = self._cipher.encrypt(nonce, data, None)

        # Prepend version byte
        versioned_ciphertext = _KEY_VERSION + ciphertext

        return EncryptedPayload(
            ciphertext=versioned_ciphertext,
            nonce=nonce,
            session_id="INTELLIGENCE_LAYER",
            turn_number=-1,
            timestamp=time.time()
        )

    def decrypt_intelligence_layer(self, payload: EncryptedPayload) -> bytes:
        """
        Decrypt data encrypted for Intelligence Layer.

        Args:
            payload: EncryptedPayload from encrypt_for_intelligence_layer

        Returns:
            Decrypted data

        Raises:
            ValueError: If version byte is unsupported
        """
        ciphertext = payload.ciphertext
        if len(ciphertext) < 2:
            raise ValueError("Ciphertext too short")
        version = ciphertext[0:1]
        if version != _KEY_VERSION:
            raise ValueError(f"Unsupported ciphertext version: {version!r}")
        return self._cipher.decrypt(payload.nonce, ciphertext[1:], None)

    def destroy_session(self, session_id: str):
        """
        Destroy session and all key material.

        Args:
            session_id: Session to destroy
        """
        if session_id in self._session_managers:
            self._session_managers[session_id].destroy()
            del self._session_managers[session_id]

    def destroy(self):
        """Destroy all sessions and master key material."""
        for sid in list(self._session_managers.keys()):
            self.destroy_session(sid)
        _zero_bytearray(self._master_key)
        self._cipher = AESGCM(secrets.token_bytes(32))

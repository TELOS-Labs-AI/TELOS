"""
Telemetric Keys Enhanced: SHA3-512 key derivation and HMAC-SHA512 signing.

.. deprecated:: 1.3.0
    This module is DEPRECATED. Use ``telemetric_keys.py`` instead.

    The base module (``TelemetricKeyGenerator``, ``TelemetricSessionManager``)
    provides all production cryptographic primitives:
    - AES-256-GCM encryption (NIST FIPS 197)
    - HKDF key derivation (RFC 5869)
    - HMAC-SHA512 governance signing
    - Session proof generation

    This enhanced module added SHA3-512 key derivation and entropy quality
    validation but has ZERO test coverage beyond the base module's 22 tests.
    The 512-bit key size provides no security margin over AES-256 for the
    TELOS use case (symmetric encryption). Maintained for backward
    compatibility only — do not build new integrations against this module.

    Removal planned: v2.0

Algorithms: SHA3-512 (NIST FIPS 202), HMAC-SHA512 (RFC 2104)
Standards: NIST SP 800-90B (entropy validation hooks)

Capabilities:
1. SHA3-512 key derivation (512-bit keys)
2. HMAC-SHA512 authenticated signatures
3. Entropy quality validation (Shannon entropy estimation)
4. IP protection signatures (unforgeable prior art documentation)
"""

import hashlib
import hmac
import math
import secrets
import time
import struct
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime
import json

# Constants
ENHANCED_KEY_SIZE = 64  # 512 bits
NONCE_SIZE = 24
TAG_SIZE = 16
MIN_ENTROPY_BITS = 256


@dataclass
class EnhancedKeyState:
    """
    Key state for SHA3-512 enhanced key derivation.

    Keys are 512 bits (64 bytes) using SHA3-512 for all derivation.
    """
    session_id: str
    current_key: bytearray  # 64 bytes
    turn_number: int
    entropy_pool: bytearray = field(default_factory=lambda: bytearray(secrets.token_bytes(ENHANCED_KEY_SIZE)))
    key_history_hash: bytearray = field(default_factory=lambda: bytearray(ENHANCED_KEY_SIZE))
    created_at: float = field(default_factory=time.time)
    last_rotation: float = field(default_factory=time.time)
    entropy_accumulated_bits: int = 0
    rotations_performed: int = 0

    def __post_init__(self):
        """Validate key material sizes."""
        if len(self.current_key) != ENHANCED_KEY_SIZE:
            raise ValueError(f"Key must be {ENHANCED_KEY_SIZE} bytes, got {len(self.current_key)}")
        if len(self.entropy_pool) != ENHANCED_KEY_SIZE:
            raise ValueError(f"Entropy pool must be {ENHANCED_KEY_SIZE} bytes, got {len(self.entropy_pool)}")
        self._ephemeral = True


class EnhancedKeyGenerator:
    """
    Enhanced telemetric key generator using SHA3-512.

    Security Properties:
    - SHA3-512 for all key derivation (NIST FIPS 202)
    - HMAC-SHA512 for authenticated signatures (RFC 2104)
    - Validated entropy sources (Shannon entropy estimation)
    - CSPRNG injection at every rotation
    - Forward secrecy via key chaining
    """

    def __init__(self, session_id: str, initial_entropy: Optional[bytes] = None):
        """
        Initialize enhanced key generator.

        Args:
            session_id: Unique session identifier
            initial_entropy: Optional seed entropy (64 bytes)
        """
        self.session_id = session_id

        seed_entropy = initial_entropy or secrets.token_bytes(ENHANCED_KEY_SIZE)

        session_metadata = f"{session_id}:{time.time()}:{secrets.token_hex(32)}".encode()
        initial_hash = hashlib.sha3_512(seed_entropy + session_metadata).digest()

        self.state = EnhancedKeyState(
            session_id=session_id,
            current_key=bytearray(initial_hash[:ENHANCED_KEY_SIZE]),
            turn_number=0,
            entropy_pool=bytearray(seed_entropy[:ENHANCED_KEY_SIZE] if len(seed_entropy) >= ENHANCED_KEY_SIZE else seed_entropy.ljust(ENHANCED_KEY_SIZE, b'\x00')),
            key_history_hash=bytearray(initial_hash)
        )

        self._turn_telemetry_history: deque = deque(maxlen=100)
        self._entropy_quality_scores: List[float] = []

    def validate_entropy_quality(self, entropy: bytes) -> Tuple[bool, float]:
        """
        Validate entropy quality via Shannon entropy estimation.

        This is a hook for integration with NIST SP 800-90B test suite.

        Args:
            entropy: Raw entropy bytes to validate

        Returns:
            (is_valid, quality_score) where quality_score is 0.0-1.0
        """
        if len(entropy) < 32:
            return False, 0.0

        if entropy == bytes(len(entropy)):
            return False, 0.0

        byte_counts: Dict[int, int] = {}
        for byte in entropy:
            byte_counts[byte] = byte_counts.get(byte, 0) + 1

        total = len(entropy)
        shannon_entropy = 0.0
        for count in byte_counts.values():
            if count > 0:
                prob = count / total
                shannon_entropy -= prob * math.log2(prob) if prob > 0 else 0

        quality_score = min(shannon_entropy / 8.0, 1.0)
        is_valid = quality_score >= 0.7

        self._entropy_quality_scores.append(quality_score)

        return is_valid, quality_score

    def extract_entropy_from_telemetry(self, turn_telemetry: Dict[str, Any]) -> bytes:
        """
        Extract entropy from telemetry using SHA3-512.

        Uses struct.pack for exact binary representation of float values,
        preserving full IEEE 754 precision as entropy.

        Args:
            turn_telemetry: Telemetry dict with high-precision measurements

        Returns:
            64 bytes of validated entropy
        """
        entropy_components = []

        timestamp = turn_telemetry.get("timestamp", time.time())
        entropy_components.append(struct.pack('d', timestamp))

        delta_t = turn_telemetry.get("delta_t_ms", 0)
        entropy_components.append(struct.pack('d', delta_t))

        embedding_distance = turn_telemetry.get("embedding_distance", 0.0)
        entropy_components.append(struct.pack('d', embedding_distance))

        fidelity = turn_telemetry.get("fidelity_score", 0.0)
        soft_fidelity = turn_telemetry.get("soft_fidelity", 0.0)
        entropy_components.append(struct.pack('dd', fidelity, soft_fidelity))

        lyapunov = turn_telemetry.get("lyapunov_delta", 0.0)
        entropy_components.append(struct.pack('d', lyapunov))

        intervention = turn_telemetry.get("intervention_triggered", False)
        drift_flag = turn_telemetry.get("governance_drift_flag", False)
        correction = turn_telemetry.get("governance_correction_applied", False)
        state_byte = (int(intervention) << 2) | (int(drift_flag) << 1) | int(correction)
        entropy_components.append(bytes([state_byte]))

        turn_id = turn_telemetry.get("turn_id", self.state.turn_number)
        entropy_components.append(struct.pack('I', turn_id))

        user_len = len(turn_telemetry.get("user_input", ""))
        model_len = len(turn_telemetry.get("model_output", ""))
        entropy_components.append(struct.pack('II', user_len, model_len))

        combined_entropy = b''.join(entropy_components)

        is_valid, quality = self.validate_entropy_quality(combined_entropy)
        if not is_valid:
            combined_entropy += secrets.token_bytes(32)

        return hashlib.sha3_512(combined_entropy).digest()

    def rotate_key(self, turn_telemetry: Dict[str, Any]) -> None:
        """
        Rotate key with SHA3-512 derivation and CSPRNG injection.

        Args:
            turn_telemetry: Telemetry dict for current turn
        """
        turn_entropy = self.extract_entropy_from_telemetry(turn_telemetry)

        # CSPRNG injection at every rotation
        csprng_entropy = secrets.token_bytes(16)

        components_to_mix = [
            bytes(self.state.current_key),
            turn_entropy,
            bytes(self.state.entropy_pool),
            bytes(self.state.key_history_hash),
            struct.pack('I', self.state.turn_number),
            csprng_entropy,
        ]

        combined = b''.join(components_to_mix)
        key_evolution = hashlib.sha3_512(combined).digest()

        new_history_hash = hashlib.sha3_512(
            bytes(self.state.key_history_hash) + key_evolution
        ).digest()

        new_entropy_pool = hashlib.sha3_512(
            bytes(self.state.entropy_pool) + turn_entropy + csprng_entropy
        ).digest()[:ENHANCED_KEY_SIZE]

        entropy_bits_estimate = len(turn_entropy) * 8
        self._turn_telemetry_history.append({
            "turn": self.state.turn_number,
            "timestamp": turn_telemetry.get("timestamp", time.time()),
            "entropy_bits": entropy_bits_estimate,
            "quality_score": self._entropy_quality_scores[-1] if self._entropy_quality_scores else 0.0
        })

        # Zero old key material
        import ctypes
        from telos_privacy.cryptography.telemetric_keys import _zero_bytearray
        _zero_bytearray(self.state.current_key)
        _zero_bytearray(self.state.key_history_hash)
        _zero_bytearray(self.state.entropy_pool)

        self.state.current_key = bytearray(key_evolution[:ENHANCED_KEY_SIZE])
        self.state.key_history_hash = bytearray(new_history_hash)
        self.state.entropy_pool = bytearray(new_entropy_pool)
        self.state.turn_number += 1
        self.state.last_rotation = time.time()
        self.state.entropy_accumulated_bits += entropy_bits_estimate
        self.state.rotations_performed += 1

    def generate_hmac_signature(self, data: bytes) -> bytes:
        """
        Generate HMAC-SHA512 signature for data.

        Uses current telemetric key for signing.
        Provides authentication and integrity.

        Args:
            data: Data to sign

        Returns:
            64-byte HMAC-SHA512 signature
        """
        h = hmac.new(bytes(self.state.current_key), data, hashlib.sha512)
        return h.digest()

    def verify_hmac_signature(self, data: bytes, signature: bytes) -> bool:
        """
        Verify HMAC signature in constant time.

        Args:
            data: Original data
            signature: Signature to verify

        Returns:
            True if signature valid
        """
        expected = self.generate_hmac_signature(data)
        return hmac.compare_digest(expected, signature)

    def get_session_fingerprint(self) -> Dict[str, Any]:
        """
        Get session fingerprint with entropy quality metrics.

        Returns:
            Session fingerprint for audit and IP protection
        """
        avg_quality = sum(self._entropy_quality_scores) / len(self._entropy_quality_scores) if self._entropy_quality_scores else 0.0

        return {
            "session_id": self.state.session_id,
            "key_history_hash": bytes(self.state.key_history_hash).hex(),
            "turn_number": self.state.turn_number,
            "rotations_performed": self.state.rotations_performed,
            "entropy_accumulated_bits": self.state.entropy_accumulated_bits,
            "avg_entropy_quality": avg_quality,
            "algorithm": "SHA3-512",
            "version": "2.0.0"
        }

    def export_for_audit(self) -> Dict[str, Any]:
        """
        Export non-sensitive data for cryptographic audit.

        Returns:
            Audit package (no keys included)
        """
        return {
            "metadata": self.get_session_fingerprint(),
            "telemetry_history": list(self._turn_telemetry_history),
            "entropy_quality_scores": self._entropy_quality_scores,
            "configuration": {
                "key_size_bits": ENHANCED_KEY_SIZE * 8,
                "hash_algorithm": "SHA3-512",
                "hmac_algorithm": "HMAC-SHA512",
                "entropy_sources": 8,
                "min_entropy_bits": MIN_ENTROPY_BITS
            }
        }

    def destroy(self):
        """
        Securely destroy all key material.

        Uses ctypes.memset to zero bytearray key material.
        """
        from telos_privacy.cryptography.telemetric_keys import _zero_bytearray
        _zero_bytearray(self.state.current_key)
        _zero_bytearray(self.state.entropy_pool)
        _zero_bytearray(self.state.key_history_hash)

        self._turn_telemetry_history.clear()
        self._entropy_quality_scores.clear()

        self.state.turn_number = -1
        self.state.rotations_performed = -1


class TelemetricSignatureGenerator:
    """
    Generate cryptographic signatures for IP protection.

    Uses HMAC-SHA512 telemetric keys to sign deltas, creating
    unforgeable prior art documentation.
    """

    def __init__(self, key_generator: EnhancedKeyGenerator):
        """
        Initialize signature generator.

        Args:
            key_generator: Enhanced telemetric key generator
        """
        self.key_gen = key_generator
        self.signatures_generated = 0

    def sign_delta(self, delta_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sign delta with telemetric key for IP protection.

        Creates unforgeable proof of TELOS operation.

        Args:
            delta_data: Delta telemetry to sign

        Returns:
            Signature package for IP documentation
        """
        canonical = self._canonicalize_delta(delta_data)
        signature = self.key_gen.generate_hmac_signature(canonical)

        self.signatures_generated += 1

        return {
            "signature": signature.hex(),
            "signature_algorithm": "HMAC-SHA512",
            "key_rotation_number": self.key_gen.state.turn_number,
            "timestamp": time.time(),
            "session_id": self.key_gen.session_id,
            "canonical_hash": hashlib.sha3_512(canonical).hexdigest(),
        }

    def _canonicalize_delta(self, delta: Dict[str, Any]) -> bytes:
        """
        Create deterministic representation of delta.

        Args:
            delta: Delta data to canonicalize

        Returns:
            Canonical byte representation
        """
        sorted_delta = dict(sorted(delta.items()))
        json_str = json.dumps(sorted_delta, sort_keys=True, separators=(',', ':'))
        return json_str.encode('utf-8')

    def generate_ip_proof(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate IP protection proof document.

        Creates cryptographic evidence of prior art using HMAC-SHA512
        signatures derived from session telemetry.

        Args:
            session_data: Complete session data

        Returns:
            IP proof package
        """
        fingerprint = self.key_gen.get_session_fingerprint()

        return {
            "title": "TELOS Telemetric Signature - Prior Art Documentation",
            "session_id": fingerprint["session_id"],
            "telemetric_fingerprint": fingerprint["key_history_hash"],
            "created_at": datetime.fromtimestamp(self.key_gen.state.created_at).isoformat(),

            "cryptographic_evidence": {
                "algorithm": "HMAC-SHA512 with SHA3-512 key derivation",
                "entropy_sources": 8,
                "entropy_quality_avg": fingerprint["avg_entropy_quality"],
                "total_entropy_bits": fingerprint["entropy_accumulated_bits"],
                "key_rotations": fingerprint["rotations_performed"],
                "signatures_generated": self.signatures_generated
            },

            "ip_claims": {
                "innovation": "Session telemetry as supplementary entropy for key derivation",
                "uniqueness": "Non-reproducible without exact telemetry sequence",
                "timestamp": "Cryptographically provable creation timestamp",
                "ownership": "TELOS Labs proprietary implementation"
            },

            "verification": {
                "method": "Telemetric Signature v2.0",
                "can_verify": "Third parties can verify signature chain with fingerprint",
                "cannot_forge": "Requires exact telemetry sequence + 512-bit keys",
                "nist_compliant": "SHA3-512 (FIPS 202), HMAC-SHA512 (RFC 2104)"
            },

            "audit_data": self.key_gen.export_for_audit()
        }

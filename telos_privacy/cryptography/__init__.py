"""
TKeys: Session-bound AES-256-GCM encryption + HMAC-SHA512 signing using governance telemetry as entropy.

Primary interface (use these):
    TelemetricSessionManager - Session lifecycle manager with encrypt + sign + proof generation
    TelemetricKeyGenerator - Low-level key derivation, encryption, and HMAC-SHA512 signing
    TelemetricAccessControl - Multi-session access control with master key hierarchy
    EncryptedPayload - Encrypted data with optional telos_signature (the TELOS stamp)

Deprecated (do not use for new code):
    EnhancedKeyGenerator - SHA3-512 key derivation (deprecated v1.3, removal v2.0)
    TelemetricSignatureGenerator - Standalone signatures (deprecated v1.3, removal v2.0)
"""

from telos_privacy.cryptography.telemetric_keys import (
    TelemetricKeyGenerator,
    TelemetricSessionManager,
    TelemetricAccessControl,
    EncryptedPayload,
)

# Deprecated — maintained for backward compatibility only.
# Use TelemetricSessionManager.sign_governance_delta() instead.
from telos_privacy.cryptography.telemetric_keys_enhanced import (
    EnhancedKeyGenerator,
    TelemetricSignatureGenerator,
)

__all__ = [
    "TelemetricKeyGenerator",
    "TelemetricSessionManager",
    "TelemetricAccessControl",
    "EncryptedPayload",
    "EnhancedKeyGenerator",
    "TelemetricSignatureGenerator",
]

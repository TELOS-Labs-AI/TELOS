"""
Session Key Store: Persistent session-scoped encryption for Streamlit state.

Unlike TKeys (session-bound, rotating, telemetry-entropy-driven), SessionKeyStore
provides a simpler AES-256-GCM encryption layer that persists across Streamlit
page reruns within a single browser session. The key is stored in st.session_state
and destroyed when the session ends or the browser tab closes.

Use cases:
- Encrypting conversation history in st.session_state
- Encrypting PA data (purpose, scope, boundaries) in st.session_state
- Any data that must survive Streamlit reruns but should not be plaintext

NOT a replacement for TKeys. TKeys provides forward secrecy and telemetry-based
key rotation for in-flight governance deltas. SessionKeyStore is for at-rest
protection of session state data.

Primitives:
- AES-256-GCM (NIST FIPS 197) for authenticated encryption
- HKDF (RFC 5869) for key derivation from session_id
- CSPRNG (secrets module) for seed generation
"""

import base64
import json
import secrets
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

# Session state key where the encryption seed is stored
_SESSION_KEY_STATE = '_telos_session_encryption_seed'


class SessionKeyStore:
    """Session-scoped AES-256-GCM encryption for Streamlit state data.

    Derives a 256-bit key from session_id + a CSPRNG seed that lives in
    st.session_state. The seed survives Streamlit reruns but is lost when
    the browser session ends.

    Args:
        session_id: Unique session identifier (used as HKDF salt).
        passphrase: Optional passphrase for deterministic key derivation.
            If not provided, a CSPRNG seed is generated and stored in
            st.session_state.
    """

    def __init__(self, session_id: str, passphrase: Optional[bytes] = None):
        self._session_id = session_id

        if passphrase:
            ikm = passphrase
        else:
            # Use or create CSPRNG seed in session state
            try:
                import streamlit as st
                if _SESSION_KEY_STATE not in st.session_state:
                    st.session_state[_SESSION_KEY_STATE] = secrets.token_bytes(32)
                ikm = st.session_state[_SESSION_KEY_STATE]
            except Exception:
                # Fallback for non-Streamlit environments (testing)
                ikm = secrets.token_bytes(32)

        # Derive encryption key via HKDF
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=session_id.encode('utf-8'),
            info=b"telos-session-key-store-v1",
        )
        key = hkdf.derive(ikm)
        self._cipher = AESGCM(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt data with AES-256-GCM.

        Args:
            plaintext: Data to encrypt.

        Returns:
            nonce (12 bytes) + ciphertext (N bytes + 16 byte GCM tag).
        """
        nonce = secrets.token_bytes(12)
        ciphertext = self._cipher.encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data encrypted with encrypt().

        Args:
            data: nonce + ciphertext blob from encrypt().

        Returns:
            Decrypted plaintext.

        Raises:
            ValueError: If data is too short.
            cryptography.exceptions.InvalidTag: If authentication fails.
        """
        if len(data) < 28:  # 12 nonce + 16 GCM tag minimum
            raise ValueError("Encrypted data too short")
        nonce = data[:12]
        ciphertext = data[12:]
        return self._cipher.decrypt(nonce, ciphertext, None)

    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """Encrypt a dict and return a base64-encoded string.

        Convenience method for encrypting JSON-serializable data.

        Args:
            data: Dictionary to encrypt.

        Returns:
            Base64-encoded encrypted blob (safe for st.session_state storage).
        """
        plaintext = json.dumps(data, default=str).encode('utf-8')
        encrypted = self.encrypt(plaintext)
        return base64.b64encode(encrypted).decode('ascii')

    def decrypt_dict(self, b64_data: str) -> Dict[str, Any]:
        """Decrypt a base64-encoded string back to a dict.

        Args:
            b64_data: Base64 string from encrypt_dict().

        Returns:
            Decrypted dictionary.
        """
        encrypted = base64.b64decode(b64_data)
        plaintext = self.decrypt(encrypted)
        return json.loads(plaintext.decode('utf-8'))

    def encrypt_string(self, text: str) -> str:
        """Encrypt a string and return base64-encoded ciphertext.

        Args:
            text: String to encrypt.

        Returns:
            Base64-encoded encrypted blob.
        """
        encrypted = self.encrypt(text.encode('utf-8'))
        return base64.b64encode(encrypted).decode('ascii')

    def decrypt_string(self, b64_data: str) -> str:
        """Decrypt a base64-encoded string.

        Args:
            b64_data: Base64 string from encrypt_string().

        Returns:
            Decrypted string.
        """
        encrypted = base64.b64decode(b64_data)
        plaintext = self.decrypt(encrypted)
        return plaintext.decode('utf-8')


def get_session_key_store(session_id: Optional[str] = None) -> Optional[SessionKeyStore]:
    """Get or create SessionKeyStore for the current Streamlit session.

    Caches the store instance in st.session_state for reuse across reruns.

    Args:
        session_id: Session identifier. If None, reads from st.session_state.

    Returns:
        SessionKeyStore instance, or None if session_id unavailable.
    """
    try:
        import streamlit as st
    except ImportError:
        return None

    cache_key = '_telos_session_key_store'
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    sid = session_id or st.session_state.get('session_id', '')
    if not sid:
        return None

    store = SessionKeyStore(str(sid))
    st.session_state[cache_key] = store
    return store

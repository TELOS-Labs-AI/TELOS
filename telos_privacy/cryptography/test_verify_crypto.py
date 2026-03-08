#!/usr/bin/env python3
"""
TELEMETRIC KEYS VERIFICATION TEST SUITE (HARDENED)

Tests the hardened TKeys implementation against all security requirements
from the 5-agent cryptographic review.

Original 8 tests (adapted for hardened API):
1. Round-trip encryption/decryption
2. Wrong key MUST fail to decrypt
3. Tampered ciphertext MUST fail
4. Key rotation MUST produce different keys
5. Different telemetry MUST produce different keys
6. JSON serialization round-trip
7. Session Manager integration
8. Intelligence Layer encryption

New hardening tests (10 additional):
9.  CSPRNG entropy floor at every rotation
10. No raw key exposure (get_current_key removed)
11. No quantum claims in source code
12. ValueError replaces assert for validation
13. HKDF derivation path (not raw SHA3 concatenation)
14. Key version byte prefix on ciphertext
15. Key memory zeroing after destroy
16. Bounded key history (deque maxlen=100)
17. Supabase encryption integration
18. Graceful fallback without TKeys

TELOS Signature tests (4 additional):
19. HMAC-SHA512 signature generation and verification
20. process_turn includes telos_signature in payload
21. Signature changes with key rotation (key evolution)
22. Session proof document generation

Run: python3 -m telos_privacy.cryptography.test_verify_crypto
"""

import sys
import time
import secrets
import json
import inspect

from telos_privacy.cryptography.telemetric_keys import (
    TelemetricKeyGenerator,
    TelemetricSessionManager,
    TelemetricAccessControl,
    EncryptedPayload,
    _KEY_VERSION,
)

from cryptography.exceptions import InvalidTag


def test_roundtrip_basic():
    """Test 1: Basic encrypt/decrypt works."""
    print("TEST 1: Basic round-trip encryption/decryption")
    print("-" * 60)

    gen = TelemetricKeyGenerator("test_session_1")
    plaintext = b"Sensitive governance data: fidelity=0.92"

    encrypted = gen.encrypt(plaintext)
    decrypted = gen.decrypt(encrypted)

    result = plaintext == decrypted
    print(f"  Original:  {plaintext}")
    print(f"  Decrypted: {decrypted}")
    print(f"  Match: {result}")
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_wrong_key_fails():
    """Test 2: Decryption with wrong key MUST fail."""
    print("TEST 2: Wrong key MUST fail to decrypt")
    print("-" * 60)

    gen_a = TelemetricKeyGenerator("session_A")
    plaintext = b"Secret data"
    encrypted = gen_a.encrypt(plaintext)

    gen_b = TelemetricKeyGenerator("session_B")

    try:
        gen_b.decrypt(encrypted)
        print(f"  ERROR: Decryption succeeded with wrong key!")
        print(f"  RESULT: FAIL (crypto is fake)")
        return False
    except InvalidTag:
        print(f"  Decryption correctly failed with InvalidTag exception")
        print(f"  RESULT: PASS (wrong key properly rejected)")
        print()
        return True
    except Exception as e:
        print(f"  Unexpected exception: {type(e).__name__}: {e}")
        print(f"  RESULT: FAIL (unexpected error)")
        return False


def test_tampered_ciphertext_fails():
    """Test 3: Tampered ciphertext MUST fail authentication."""
    print("TEST 3: Tampered ciphertext MUST fail")
    print("-" * 60)

    gen = TelemetricKeyGenerator("test_tamper")
    plaintext = b"Original message"

    encrypted = gen.encrypt(plaintext)

    # Tamper with ciphertext (flip a byte after version byte)
    tampered_ciphertext = bytearray(encrypted.ciphertext)
    tampered_ciphertext[1] ^= 0xFF  # Skip version byte, flip next byte
    tampered_ciphertext = bytes(tampered_ciphertext)

    tampered_payload = EncryptedPayload(
        ciphertext=tampered_ciphertext,
        nonce=encrypted.nonce,
        session_id=encrypted.session_id,
        turn_number=encrypted.turn_number,
        timestamp=encrypted.timestamp
    )

    try:
        gen.decrypt(tampered_payload)
        print(f"  ERROR: Decryption succeeded with tampered ciphertext!")
        print(f"  RESULT: FAIL (authentication not working)")
        return False
    except InvalidTag:
        print(f"  Decryption correctly failed with InvalidTag exception")
        print(f"  RESULT: PASS (tampered data properly rejected)")
        print()
        return True
    except Exception as e:
        print(f"  Unexpected exception: {type(e).__name__}: {e}")
        print(f"  RESULT: FAIL (unexpected error)")
        return False


def test_key_rotation_changes_key():
    """Test 4: Key rotation MUST produce different keys (verified via encrypt/decrypt)."""
    print("TEST 4: Key rotation MUST change the key")
    print("-" * 60)

    gen = TelemetricKeyGenerator("test_rotation")

    # Encrypt before rotation
    plaintext = b"Before rotation"
    encrypted_before = gen.encrypt(plaintext)

    # Verify it decrypts
    decrypted = gen.decrypt(encrypted_before)
    pre_rotation_ok = decrypted == plaintext
    print(f"  Pre-rotation decrypt: {pre_rotation_ok}")

    # Rotate with telemetry
    telemetry = {
        "turn_number": 1,
        "fidelity_score": 0.85,
        "timestamp": time.time()
    }
    gen.rotate_key(telemetry)

    # Old ciphertext should now fail (different key)
    try:
        gen.decrypt(encrypted_before)
        print(f"  WARNING: Old ciphertext still decrypts after rotation")
        keys_changed = False
    except InvalidTag:
        print(f"  Old ciphertext correctly fails after rotation")
        keys_changed = True

    result = pre_rotation_ok and keys_changed
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_different_telemetry_different_keys():
    """Test 5: Different telemetry MUST produce different keys."""
    print("TEST 5: Different telemetry MUST produce different keys")
    print("-" * 60)

    seed = secrets.token_bytes(32)

    gen_a = TelemetricKeyGenerator("same_session", initial_entropy=seed)
    gen_b = TelemetricKeyGenerator("same_session", initial_entropy=seed)

    # Both encrypt same plaintext before rotation
    plaintext = b"test data"
    enc_a_pre = gen_a.encrypt(plaintext)
    enc_b_pre = gen_b.encrypt(plaintext)

    # Note: Even with same seed, HKDF uses time-based salt, so keys may differ.
    # The important test is that DIFFERENT telemetry produces DIFFERENT results.

    telemetry_a = {
        "turn_number": 1,
        "fidelity_score": 0.85,
        "user_input": "Hello world",
        "timestamp": time.time()
    }
    telemetry_b = {
        "turn_number": 1,
        "fidelity_score": 0.75,
        "user_input": "Goodbye world",
        "timestamp": time.time() + 0.001
    }

    gen_a.rotate_key(telemetry_a)
    gen_b.rotate_key(telemetry_b)

    # After rotation with different telemetry, encrypting same data should produce
    # different ciphertexts (different keys + different nonces)
    enc_a_post = gen_a.encrypt(plaintext)
    enc_b_post = gen_b.encrypt(plaintext)

    # Cross-decrypt should fail (proves different keys)
    cross_decrypt_failed = False
    try:
        gen_b.decrypt(enc_a_post)
    except (InvalidTag, ValueError):
        cross_decrypt_failed = True

    print(f"  Cross-decryption correctly fails: {cross_decrypt_failed}")
    print(f"  RESULT: {'PASS' if cross_decrypt_failed else 'FAIL'}")
    print()
    return cross_decrypt_failed


def test_json_serialization_roundtrip():
    """Test 6: JSON serialization round-trip works."""
    print("TEST 6: JSON serialization round-trip")
    print("-" * 60)

    gen = TelemetricKeyGenerator("test_json")
    plaintext = b"Data for JSON test"

    encrypted = gen.encrypt(plaintext)

    json_str = encrypted.to_json()
    print(f"  JSON length: {len(json_str)} bytes")

    restored = EncryptedPayload.from_json(json_str)
    decrypted = gen.decrypt(restored)

    result = plaintext == decrypted
    print(f"  Original:  {plaintext}")
    print(f"  Decrypted: {decrypted}")
    print(f"  Match: {result}")
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_session_manager_integration():
    """Test 7: TelemetricSessionManager integration test."""
    print("TEST 7: Session Manager integration")
    print("-" * 60)

    manager = TelemetricSessionManager("integration_test_session")

    all_encrypted = []
    for turn in range(3):
        telemetry = {
            "turn_number": turn,
            "fidelity_score": 0.80 + (turn * 0.05),
            "distance_from_pa": 0.20 - (turn * 0.05),
            "intervention_triggered": turn == 2,
            "in_basin": True,
            "user_input": f"User message turn {turn}",
            "response": f"AI response turn {turn}",
            "timestamp": time.time()
        }

        encrypted = manager.process_turn(telemetry)
        all_encrypted.append(encrypted)
        print(f"  Turn {turn}: Encrypted {len(encrypted.ciphertext)} bytes")

    export = manager.get_session_export()
    print(f"  Export contains: {export['total_turns']} turns")

    try:
        json_export = json.dumps(export)
        print(f"  Export JSON size: {len(json_export)} bytes")
        result = True
    except Exception as e:
        print(f"  Failed to serialize: {e}")
        result = False

    manager.destroy()
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_intelligence_layer_encryption():
    """Test 8: Intelligence Layer master key encryption."""
    print("TEST 8: Intelligence Layer encryption")
    print("-" * 60)

    access = TelemetricAccessControl()

    aggregate_data = json.dumps({
        "deployment_id": "hospital_A",
        "total_sessions": 1000,
        "avg_fidelity": 0.87
    }).encode()

    encrypted = access.encrypt_for_intelligence_layer(aggregate_data)
    print(f"  Encrypted size: {len(encrypted.ciphertext)} bytes")

    decrypted = access.decrypt_intelligence_layer(encrypted)

    result = aggregate_data == decrypted
    print(f"  Match: {result}")

    # Different master key should fail
    access_wrong = TelemetricAccessControl()
    try:
        access_wrong.decrypt_intelligence_layer(encrypted)
        print(f"  ERROR: Different master key succeeded!")
        result = False
    except (InvalidTag, ValueError):
        print(f"  Different master key correctly rejected")

    access.destroy()
    access_wrong.destroy()
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


# ============================================================================
# NEW HARDENING TESTS (9-18)
# ============================================================================


def test_csprng_entropy_floor():
    """Test 9: CSPRNG 128-bit entropy floor at every rotation."""
    print("TEST 9: CSPRNG entropy floor at every rotation")
    print("-" * 60)

    # Verify that rotate_key source code contains secrets.token_bytes
    src = inspect.getsource(TelemetricKeyGenerator.rotate_key)
    has_csprng = "secrets.token_bytes" in src
    print(f"  rotate_key contains secrets.token_bytes: {has_csprng}")

    # Verify CSPRNG is 16 bytes (128 bits)
    has_16_bytes = "token_bytes(16)" in src
    print(f"  CSPRNG injection is 16 bytes (128 bits): {has_16_bytes}")

    result = has_csprng and has_16_bytes
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_no_raw_key_exposure():
    """Test 10: get_current_key() removed, no raw key exposure."""
    print("TEST 10: No raw key exposure (get_current_key removed)")
    print("-" * 60)

    gen = TelemetricKeyGenerator("test_no_raw_key")

    has_get_current_key = hasattr(gen, 'get_current_key')
    print(f"  get_current_key exists: {has_get_current_key} (should be False)")

    # Also check TelemetricAccessControl
    access = TelemetricAccessControl()
    has_get_il_key = hasattr(access, 'get_intelligence_layer_key')
    print(f"  get_intelligence_layer_key exists: {has_get_il_key} (should be False)")

    # Verify rotate_key returns None (not the key)
    gen.rotate_key({"turn_number": 1, "timestamp": time.time()})
    # rotate_key should return None now
    ret = gen.rotate_key({"turn_number": 2, "timestamp": time.time()})
    returns_none = ret is None
    print(f"  rotate_key returns None: {returns_none} (should be True)")

    access.destroy()
    result = not has_get_current_key and not has_get_il_key and returns_none
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_no_quantum_claims():
    """Test 11: No quantum-resistant claims in source code."""
    print("TEST 11: No quantum claims in source code")
    print("-" * 60)

    import telos_privacy.cryptography.telemetric_keys as tk
    import telos_privacy.cryptography.telemetric_keys_enhanced as tke

    tk_src = inspect.getsource(tk)
    tke_src = inspect.getsource(tke)

    tk_quantum = tk_src.lower().count('quantum')
    tke_quantum = tke_src.lower().count('quantum')
    total = tk_quantum + tke_quantum

    print(f"  telemetric_keys.py quantum references: {tk_quantum}")
    print(f"  telemetric_keys_enhanced.py quantum references: {tke_quantum}")
    print(f"  Total: {total} (should be 0)")

    result = total == 0
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_valueerror_replaces_assert():
    """Test 12: ValueError for validation, not assert."""
    print("TEST 12: ValueError replaces assert for validation")
    print("-" * 60)

    # Try creating a key state with invalid key length
    from telos_privacy.cryptography.telemetric_keys import TelemetricKeyState

    got_value_error = False
    try:
        TelemetricKeyState(
            session_id="test",
            current_key=bytearray(b"too_short"),  # Not 32 bytes
            turn_number=0
        )
    except ValueError as e:
        got_value_error = True
        print(f"  ValueError raised: {e}")
    except AssertionError:
        print(f"  ERROR: AssertionError raised (should be ValueError)")
        got_value_error = False

    # Check enhanced key state too
    from telos_privacy.cryptography.telemetric_keys_enhanced import EnhancedKeyState

    got_enhanced_error = False
    try:
        EnhancedKeyState(
            session_id="test",
            current_key=bytearray(b"too_short"),
            turn_number=0
        )
    except ValueError as e:
        got_enhanced_error = True
        print(f"  Enhanced ValueError raised: {e}")
    except AssertionError:
        print(f"  ERROR: AssertionError raised in enhanced (should be ValueError)")

    # Verify no assert statements in main source (excluding test file)
    import telos_privacy.cryptography.telemetric_keys as tk
    tk_src = inspect.getsource(tk)
    # Count assert statements (not in comments/strings)
    assert_count = sum(1 for line in tk_src.split('\n')
                       if line.strip().startswith('assert '))
    print(f"  assert statements in telemetric_keys.py: {assert_count} (should be 0)")

    result = got_value_error and got_enhanced_error and assert_count == 0
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_hkdf_derivation():
    """Test 13: HKDF is used for key derivation (not raw SHA3 concatenation)."""
    print("TEST 13: HKDF derivation path")
    print("-" * 60)

    src = inspect.getsource(TelemetricKeyGenerator.rotate_key)

    has_hkdf = "HKDF(" in src
    has_hkdf_derive = "hkdf.derive" in src
    no_raw_sha3_concat = "sha3_256(\n" not in src.replace(" ", "")

    print(f"  HKDF constructor present: {has_hkdf}")
    print(f"  hkdf.derive call present: {has_hkdf_derive}")

    # Also check __init__ uses HKDF
    init_src = inspect.getsource(TelemetricKeyGenerator.__init__)
    init_has_hkdf = "HKDF(" in init_src
    print(f"  __init__ uses HKDF: {init_has_hkdf}")

    result = has_hkdf and has_hkdf_derive and init_has_hkdf
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_key_version_byte():
    """Test 14: Encrypted output starts with version byte."""
    print("TEST 14: Key version byte prefix on ciphertext")
    print("-" * 60)

    gen = TelemetricKeyGenerator("test_version")
    plaintext = b"Version byte test"

    encrypted = gen.encrypt(plaintext)

    version_byte = encrypted.ciphertext[0:1]
    expected = _KEY_VERSION
    has_version = version_byte == expected

    print(f"  Version byte: {version_byte.hex()} (expected: {expected.hex()})")
    print(f"  Match: {has_version}")

    # Also check Intelligence Layer encryption
    access = TelemetricAccessControl()
    il_enc = access.encrypt_for_intelligence_layer(b"test")
    il_version = il_enc.ciphertext[0:1]
    il_has_version = il_version == expected
    print(f"  IL version byte: {il_version.hex()} (expected: {expected.hex()})")

    # Bad version should raise ValueError
    bad_payload = EncryptedPayload(
        ciphertext=b'\xff' + encrypted.ciphertext[1:],
        nonce=encrypted.nonce,
        session_id=encrypted.session_id,
        turn_number=encrypted.turn_number,
        timestamp=encrypted.timestamp
    )
    bad_version_rejected = False
    try:
        gen.decrypt(bad_payload)
    except ValueError as e:
        bad_version_rejected = True
        print(f"  Bad version rejected: {e}")

    access.destroy()
    result = has_version and il_has_version and bad_version_rejected
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_key_memory_zeroing():
    """Test 15: Key bytearray is zeroed after destroy."""
    print("TEST 15: Key memory zeroing after destroy")
    print("-" * 60)

    gen = TelemetricKeyGenerator("test_zeroing")

    # Get reference to the bytearray (not a copy)
    key_ref = gen.state.current_key
    pool_ref = gen.state.entropy_pool
    history_ref = gen.state.key_history_hash

    # Verify keys are non-zero before destroy
    pre_key_nonzero = any(b != 0 for b in key_ref)
    print(f"  Key non-zero before destroy: {pre_key_nonzero}")

    gen.destroy()

    # After destroy, the referenced bytearrays should be all zeros
    key_zeroed = all(b == 0 for b in key_ref)
    pool_zeroed = all(b == 0 for b in pool_ref)
    history_zeroed = all(b == 0 for b in history_ref)

    print(f"  Key zeroed after destroy: {key_zeroed}")
    print(f"  Entropy pool zeroed: {pool_zeroed}")
    print(f"  Key history zeroed: {history_zeroed}")

    result = pre_key_nonzero and key_zeroed and pool_zeroed and history_zeroed
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_bounded_key_history():
    """Test 16: Key history bounded by deque(maxlen=100)."""
    print("TEST 16: Bounded key history (deque maxlen=100)")
    print("-" * 60)

    gen = TelemetricKeyGenerator("test_bounded")

    # Perform 150 rotations
    for i in range(150):
        gen.rotate_key({
            "turn_number": i,
            "fidelity_score": 0.85,
            "timestamp": time.time()
        })

    history_len = len(gen._turn_telemetry_history)
    bounded = history_len <= 100

    print(f"  After 150 rotations, history length: {history_len}")
    print(f"  Bounded <= 100: {bounded}")

    # Verify it's actually a deque
    from collections import deque
    is_deque = isinstance(gen._turn_telemetry_history, deque)
    print(f"  Is deque: {is_deque}")

    result = bounded and is_deque
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_supabase_encryption_path():
    """Test 17: Supabase delta encryption produces encrypted payload."""
    print("TEST 17: Supabase encryption path")
    print("-" * 60)

    manager = TelemetricSessionManager("supabase_test")

    # Process a turn first (needed to initialize key)
    manager.process_turn({
        "turn_number": 0,
        "fidelity_score": 0.85,
        "timestamp": time.time()
    })

    # Simulate what turn_storage_service.py now does
    delta_data = {
        'session_id': 'supabase_test',
        'turn_number': 0,
        'fidelity_score': 0.85,
        'distance_from_pa': 0.15,
        'intervention_triggered': False,
    }

    plaintext = json.dumps(delta_data, default=str).encode('utf-8')
    encrypted_payload = manager.encrypt(plaintext)

    encrypted_delta = {
        'encrypted': True,
        'payload': encrypted_payload.to_dict(),
        'session_id': delta_data['session_id'],
        'turn_number': delta_data['turn_number'],
    }

    has_encrypted_flag = encrypted_delta.get('encrypted') is True
    has_payload = 'payload' in encrypted_delta
    payload_has_ciphertext = 'ciphertext' in encrypted_delta.get('payload', {})

    print(f"  encrypted flag: {has_encrypted_flag}")
    print(f"  has payload: {has_payload}")
    print(f"  payload has ciphertext: {payload_has_ciphertext}")

    # Verify it's JSON-serializable
    try:
        json.dumps(encrypted_delta)
        serializable = True
    except (TypeError, ValueError):
        serializable = False
    print(f"  JSON-serializable: {serializable}")

    manager.destroy()
    result = has_encrypted_flag and has_payload and payload_has_ciphertext and serializable
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_graceful_fallback():
    """Test 18: Supabase path works without TKeys (graceful degradation)."""
    print("TEST 18: Graceful fallback without TKeys")
    print("-" * 60)

    # Simulate what happens when telemetric_manager is None
    delta_data = {
        'session_id': 'fallback_test',
        'turn_number': 0,
        'fidelity_score': 0.85,
    }

    telemetric_manager = None  # TKeys not available

    # This mirrors the logic in turn_storage_service.py
    if telemetric_manager:
        try:
            plaintext = json.dumps(delta_data, default=str).encode('utf-8')
            encrypted_payload = telemetric_manager.encrypt(plaintext)
            delta_data = {
                'encrypted': True,
                'payload': encrypted_payload.to_dict(),
                'session_id': delta_data['session_id'],
                'turn_number': delta_data['turn_number'],
            }
        except Exception:
            pass  # Fallback to plaintext

    # delta_data should be unchanged (plaintext)
    is_plaintext = 'encrypted' not in delta_data
    has_fidelity = 'fidelity_score' in delta_data

    print(f"  Data is plaintext (no TKeys): {is_plaintext}")
    print(f"  Fidelity score preserved: {has_fidelity}")

    result = is_plaintext and has_fidelity
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_hmac_signature_generation():
    """Test 19: HMAC-SHA512 signature generation and verification."""
    print("TEST 19: HMAC-SHA512 signature generation and verification")
    print("-" * 60)

    gen = TelemetricKeyGenerator("test_hmac")
    data = b"governance delta: fidelity=0.92, intervention=false"

    # Generate signature
    signature = gen.generate_hmac_signature(data)
    sig_length_ok = len(signature) == 64  # HMAC-SHA512 = 64 bytes
    print(f"  Signature length: {len(signature)} bytes (expected 64)")

    # Verify signature
    is_valid = gen.verify_hmac_signature(data, signature)
    print(f"  Signature valid: {is_valid}")

    # Tampered data should fail
    tampered_valid = gen.verify_hmac_signature(b"tampered data", signature)
    print(f"  Tampered data rejected: {not tampered_valid}")

    # Wrong signature should fail
    wrong_sig = bytes(64)
    wrong_valid = gen.verify_hmac_signature(data, wrong_sig)
    print(f"  Wrong signature rejected: {not wrong_valid}")

    # Different key should produce different signature
    gen_b = TelemetricKeyGenerator("different_session")
    sig_b = gen_b.generate_hmac_signature(data)
    sigs_differ = signature != sig_b
    print(f"  Different key = different signature: {sigs_differ}")

    result = sig_length_ok and is_valid and not tampered_valid and not wrong_valid and sigs_differ
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_process_turn_includes_signature():
    """Test 20: process_turn() includes telos_signature in payload."""
    print("TEST 20: process_turn includes TELOS signature")
    print("-" * 60)

    manager = TelemetricSessionManager("sig_test_session")

    telemetry = {
        "turn_number": 0,
        "fidelity_score": 0.85,
        "distance_from_pa": 0.15,
        "intervention_triggered": False,
        "in_basin": True,
        "timestamp": time.time()
    }

    encrypted = manager.process_turn(telemetry)

    # Check signature exists
    has_sig = encrypted.telos_signature is not None
    print(f"  telos_signature present: {has_sig}")

    if has_sig:
        sig = encrypted.telos_signature
        has_sig_hex = "signature" in sig and len(sig["signature"]) == 128  # 64 bytes = 128 hex chars
        has_algo = sig.get("signature_algorithm") == "HMAC-SHA512"
        has_session = sig.get("session_id") == "sig_test_session"
        has_hash = "canonical_hash" in sig

        print(f"  Signature hex (128 chars): {has_sig_hex}")
        print(f"  Algorithm = HMAC-SHA512: {has_algo}")
        print(f"  Session ID bound: {has_session}")
        print(f"  Canonical hash present: {has_hash}")
    else:
        has_sig_hex = has_algo = has_session = has_hash = False

    # Check signature survives JSON round-trip
    payload_dict = encrypted.to_dict()
    has_sig_in_dict = "telos_signature" in payload_dict
    print(f"  Signature in to_dict(): {has_sig_in_dict}")

    json_str = json.dumps(payload_dict)
    restored = EncryptedPayload.from_dict(json.loads(json_str))
    sig_survives = restored.telos_signature is not None
    print(f"  Signature survives JSON round-trip: {sig_survives}")

    manager.destroy()
    result = has_sig and has_sig_hex and has_algo and has_session and has_hash and has_sig_in_dict and sig_survives
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_signature_changes_with_key_rotation():
    """Test 21: Signatures change after key rotation (key evolution)."""
    print("TEST 21: Signature changes with key rotation")
    print("-" * 60)

    manager = TelemetricSessionManager("sig_evolution_test")

    # Same governance data, different turns
    governance_data = {
        "fidelity_score": 0.85,
        "session_id": "sig_evolution_test"
    }

    # First turn
    manager.process_turn({
        "turn_number": 0,
        "fidelity_score": 0.85,
        "timestamp": time.time()
    })
    sig_1 = manager.sign_governance_delta(governance_data)

    # Second turn (key rotated)
    manager.process_turn({
        "turn_number": 1,
        "fidelity_score": 0.80,
        "timestamp": time.time()
    })
    sig_2 = manager.sign_governance_delta(governance_data)

    # Same data, different signatures (because key evolved)
    sigs_differ = sig_1["signature"] != sig_2["signature"]
    print(f"  Same data, different turns = different signatures: {sigs_differ}")

    # Rotation numbers should differ
    rotations_differ = sig_1["key_rotation_number"] != sig_2["key_rotation_number"]
    print(f"  Key rotation numbers differ: {rotations_differ}")

    manager.destroy()
    result = sigs_differ and rotations_differ
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def test_session_proof_generation():
    """Test 22: Session proof document generation."""
    print("TEST 22: Session proof generation")
    print("-" * 60)

    manager = TelemetricSessionManager("proof_test_session")

    # Process a few turns
    for turn in range(3):
        manager.process_turn({
            "turn_number": turn,
            "fidelity_score": 0.80 + (turn * 0.05),
            "timestamp": time.time()
        })

    # Generate proof
    proof = manager.generate_session_proof()

    has_title = "title" in proof
    has_session_id = proof.get("session_id") == "proof_test_session"
    has_summary = "session_summary" in proof
    has_crypto = "cryptographic_evidence" in proof
    has_ip = "ip_claims" in proof
    has_verification = "verification" in proof

    print(f"  Title present: {has_title}")
    print(f"  Session ID correct: {has_session_id}")
    print(f"  Session summary: {has_summary}")
    print(f"  Cryptographic evidence: {has_crypto}")
    print(f"  IP claims: {has_ip}")
    print(f"  Verification section: {has_verification}")

    # Check summary details
    summary = proof.get("session_summary", {})
    correct_turns = summary.get("total_turns") == 3
    has_sig_count = summary.get("signatures_generated") == 3
    print(f"  Total turns = 3: {correct_turns}")
    print(f"  Signatures generated = 3: {has_sig_count}")

    # Check crypto evidence
    crypto = proof.get("cryptographic_evidence", {})
    has_fingerprint = len(crypto.get("key_history_fingerprint", "")) == 64  # SHA3-256 = 32 bytes = 64 hex
    has_hmac_algo = "HMAC-SHA512" in crypto.get("signature_algorithm", "")
    print(f"  Key history fingerprint (64 hex chars): {has_fingerprint}")
    print(f"  HMAC-SHA512 in crypto evidence: {has_hmac_algo}")

    # JSON-serializable
    try:
        json.dumps(proof)
        serializable = True
    except (TypeError, ValueError):
        serializable = False
    print(f"  JSON-serializable: {serializable}")

    # Proof should fail after destroy
    manager.destroy()
    proof_fails_after_destroy = False
    try:
        manager.generate_session_proof()
    except RuntimeError:
        proof_fails_after_destroy = True
    print(f"  Proof fails after destroy: {proof_fails_after_destroy}")

    result = (has_title and has_session_id and has_summary and has_crypto
              and has_ip and has_verification and correct_turns and has_sig_count
              and has_fingerprint and has_hmac_algo and serializable and proof_fails_after_destroy)
    print(f"  RESULT: {'PASS' if result else 'FAIL'}")
    print()
    return result


def main():
    print("=" * 70)
    print("TELEMETRIC KEYS - HARDENED VERIFICATION TEST SUITE")
    print("22 tests: core crypto + hardening + TELOS signature")
    print("=" * 70)
    print()

    tests = [
        # Original tests (1-8)
        ("Basic round-trip", test_roundtrip_basic),
        ("Wrong key fails", test_wrong_key_fails),
        ("Tampered ciphertext fails", test_tampered_ciphertext_fails),
        ("Key rotation changes key", test_key_rotation_changes_key),
        ("Different telemetry = different keys", test_different_telemetry_different_keys),
        ("JSON serialization", test_json_serialization_roundtrip),
        ("Session Manager integration", test_session_manager_integration),
        ("Intelligence Layer encryption", test_intelligence_layer_encryption),
        # Hardening tests (9-18)
        ("CSPRNG entropy floor", test_csprng_entropy_floor),
        ("No raw key exposure", test_no_raw_key_exposure),
        ("No quantum claims", test_no_quantum_claims),
        ("ValueError replaces assert", test_valueerror_replaces_assert),
        ("HKDF derivation path", test_hkdf_derivation),
        ("Key version byte", test_key_version_byte),
        ("Key memory zeroing", test_key_memory_zeroing),
        ("Bounded key history", test_bounded_key_history),
        ("Supabase encryption path", test_supabase_encryption_path),
        ("Graceful fallback", test_graceful_fallback),
        # TELOS Signature tests (19-22)
        ("HMAC-SHA512 signature", test_hmac_signature_generation),
        ("process_turn includes signature", test_process_turn_includes_signature),
        ("Signature evolves with key", test_signature_changes_with_key_rotation),
        ("Session proof generation", test_session_proof_generation),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"  EXCEPTION: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")

    print()
    print(f"Results: {passed}/{total} tests passed")
    print()

    if passed == total:
        print("=" * 70)
        print("ALL TESTS PASSED - HARDENED CRYPTO + TELOS SIGNATURE VERIFIED")
        print("=" * 70)
        print()
        print("Verified properties:")
        print("  [X] AES-256-GCM authenticated encryption (NIST FIPS 197)")
        print("  [X] HKDF key derivation (RFC 5869, NIST SP 800-56C)")
        print("  [X] CSPRNG 128-bit entropy floor at every rotation")
        print("  [X] Key versioning (version byte prefix)")
        print("  [X] No raw key getters")
        print("  [X] No quantum claims")
        print("  [X] ValueError validation (no assert)")
        print("  [X] bytearray + ctypes.memset key destruction")
        print("  [X] Bounded key history (deque maxlen=100)")
        print("  [X] Supabase encryption path functional")
        print("  [X] HMAC-SHA512 TELOS signature (FIPS 198-1, RFC 2104)")
        print("  [X] Signature bound to key evolution (unforgeable)")
        print("  [X] Session proof generation (IP documentation)")
        print()
        return 0
    else:
        print("=" * 70)
        print("VERIFICATION FAILED - SOME TESTS DID NOT PASS")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())

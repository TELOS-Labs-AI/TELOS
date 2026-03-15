"""
Turn Storage Service - Data Persistence and History for TELOS Observatory
==========================================================================

Extracted from BetaResponseManager to provide focused turn data management.

Handles:
- Turn data storage with telemetric encryption
- Conversation history retrieval
- Recent context extraction for fidelity and PA enrichment
- Error response creation
- Statistics tracking
"""

import logging
import streamlit as st
from typing import Dict
from datetime import datetime

logger = logging.getLogger(__name__)


# Conversation content fields that should be encrypted in session state
_SENSITIVE_TURN_FIELDS = ('user_input', 'shown_response')


def _encrypt_turn_content(data: Dict) -> Dict:
    """Encrypt conversation content fields in turn data before session state storage.

    Leaves governance metrics (fidelity scores, turn number, timestamp) in cleartext
    for UI rendering without decryption. Only user_input and shown_response are encrypted.
    """
    try:
        from telos_governance.session_key_store import get_session_key_store
        store = get_session_key_store()
        if not store:
            return data
    except ImportError:
        return data

    encrypted = dict(data)
    encrypted['_session_encrypted'] = True
    for field_name in _SENSITIVE_TURN_FIELDS:
        if field_name in encrypted and encrypted[field_name]:
            try:
                encrypted[field_name] = store.encrypt_string(str(encrypted[field_name]))
            except Exception:
                pass  # Keep plaintext on failure

    # Also encrypt intervention_reason if present
    telos = encrypted.get('telos_analysis', {})
    if isinstance(telos, dict) and telos.get('intervention_reason'):
        try:
            telos = dict(telos)
            telos['intervention_reason'] = store.encrypt_string(str(telos['intervention_reason']))
            encrypted['telos_analysis'] = telos
        except Exception:
            pass

    return encrypted


def _decrypt_turn_content(data: Dict) -> Dict:
    """Decrypt conversation content fields from session state."""
    if not data.get('_session_encrypted'):
        return data

    try:
        from telos_governance.session_key_store import get_session_key_store
        store = get_session_key_store()
        if not store:
            return data
    except ImportError:
        return data

    decrypted = dict(data)
    for field_name in _SENSITIVE_TURN_FIELDS:
        val = decrypted.get(field_name)
        if val and isinstance(val, str):
            try:
                decrypted[field_name] = store.decrypt_string(val)
            except Exception:
                pass  # Return as-is on failure

    telos = decrypted.get('telos_analysis', {})
    if isinstance(telos, dict) and telos.get('intervention_reason'):
        try:
            telos = dict(telos)
            telos['intervention_reason'] = store.decrypt_string(str(telos['intervention_reason']))
            decrypted['telos_analysis'] = telos
        except Exception:
            pass

    decrypted.pop('_session_encrypted', None)
    return decrypted


def store_turn_data(manager, turn_number: int, data: Dict):
    """Store turn data for Observatory review and transmit to Supabase."""
    storage_key = f'beta_turn_{turn_number}_data'
    st.session_state[storage_key] = _encrypt_turn_content(data)

    # TELEMETRIC KEYS: Encrypt governance telemetry with session-bound key
    if manager.telemetric_manager:
        try:
            telos_data = data.get('telos_analysis', {})
            import time

            turn_telemetry = {
                'turn_number': turn_number,
                'fidelity_score': telos_data.get('user_pa_fidelity') or telos_data.get('fidelity_score') or 0.0,
                'distance_from_pa': telos_data.get('distance_from_pa', 0.0),
                'intervention_triggered': telos_data.get('intervention_triggered', False),
                'in_basin': telos_data.get('in_basin', True),
                'ai_pa_fidelity': telos_data.get('ai_pa_fidelity'),
                'primacy_state_score': telos_data.get('primacy_state_score'),
                'timestamp': time.time()
            }

            encrypted_delta = manager.telemetric_manager.process_turn(turn_telemetry)
            sig_status = "signed" if encrypted_delta.telos_signature else "unsigned"
            logger.info(f"Telemetric Keys: Encrypted turn {turn_number} ({len(encrypted_delta.ciphertext)} bytes, {sig_status})")

            if 'encrypted_governance_deltas' not in st.session_state:
                st.session_state.encrypted_governance_deltas = []
            st.session_state.encrypted_governance_deltas.append(encrypted_delta.to_dict())

        except Exception as e:
            logger.warning(f"Telemetric Keys encryption failed for turn {turn_number}: {e}")

    # Update running statistics
    if 'beta_statistics' not in st.session_state:
        st.session_state.beta_statistics = {
            'total_interventions': 0,
            'total_drifts': 0,
            'avg_fidelity': 0.0,
            'fidelity_scores': []
        }

    stats = st.session_state.beta_statistics
    telos_data = data.get('telos_analysis', {})

    if telos_data.get('intervention_triggered'):
        stats['total_interventions'] += 1
    if telos_data.get('drift_detected'):
        stats['total_drifts'] += 1

    fidelity = telos_data.get('user_pa_fidelity') or telos_data.get('fidelity_score') or 0.0
    if fidelity is not None:
        stats['fidelity_scores'].append(fidelity)
        valid_scores = [f for f in stats['fidelity_scores'] if f is not None]
        stats['avg_fidelity'] = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

    # Transmit delta to Supabase (privacy-preserving - metrics only, no content)
    if manager.backend and manager.backend.enabled:
        try:
            session_id = st.session_state.get('session_id',
                manager.state_manager.state.session_id if hasattr(manager.state_manager.state, 'session_id') else 'unknown')

            delta_data = {
                'session_id': str(session_id),
                'turn_number': turn_number,
                'fidelity_score': fidelity,
                'distance_from_pa': telos_data.get('distance_from_pa', 0.0),
                'intervention_triggered': telos_data.get('intervention_triggered', False),
                'intervention_type': telos_data.get('intervention_type'),
                'intervention_reason': telos_data.get('intervention_reason', '')[:200] if telos_data.get('intervention_reason') else None,
                'drift_detected': telos_data.get('drift_detected', False),
                'test_type': data.get('test_type'),
                'response_source': data.get('shown_source'),
                'mode': 'beta',
                'user_pa_fidelity': telos_data.get('user_pa_fidelity'),
                'ai_pa_fidelity': telos_data.get('ai_pa_fidelity'),
                'primacy_state_score': telos_data.get('primacy_state_score'),
                'raw_similarity': telos_data.get('raw_similarity'),
                'realignment_attempts': telos_data.get('realignment_attempts', 0),
                'ai_response_intervened': telos_data.get('ai_response_intervened', False)
            }

            # Encrypt delta with TKeys before transmission -- NO plaintext fallback
            encrypted_ok = False
            if manager.telemetric_manager:
                try:
                    import json as _json
                    plaintext = _json.dumps(delta_data, default=str).encode('utf-8')
                    encrypted_payload = manager.telemetric_manager.encrypt(plaintext)
                    delta_data = {
                        'encrypted': True,
                        'payload': encrypted_payload.to_dict(),
                        'session_id': str(session_id),
                        'turn_number': turn_number,
                    }
                    encrypted_ok = True
                except Exception as enc_err:
                    logger.warning(f"TKeys encryption failed -- delta NOT transmitted: {enc_err}")

            if encrypted_ok:
                manager.backend.transmit_delta(delta_data)
                logger.info(f"Transmitted encrypted BETA turn {turn_number} delta to backend")
            else:
                # Do not transmit plaintext to network -- log locally for retry
                logger.warning(f"Turn {turn_number} delta withheld from backend (no TKeys encryption)")
        except Exception as e:
            logger.error(f"Failed to transmit delta for turn {turn_number}: {e}")


def get_conversation_history(manager) -> list:
    """Get conversation history for context (auto-decrypts if encrypted)."""
    history = []
    completed_turns = st.session_state.get('beta_current_turn', 1) - 1
    for i in range(1, completed_turns + 1):
        turn_data = st.session_state.get(f'beta_turn_{i}_data', {})
        if turn_data:
            turn_data = _decrypt_turn_content(turn_data)
            history.append({'role': 'user', 'content': turn_data.get('user_input', '')})
            history.append({'role': 'assistant', 'content': turn_data.get('shown_response', '')})
    return history


def get_recent_context(manager) -> str:
    """
    Get recent conversation context for PA enrichment.

    Returns:
        String containing recent conversation snippets
    """
    history = get_conversation_history(manager)
    if not history:
        return ""

    recent = history[-6:]  # 3 user + 3 assistant messages
    context_parts = []
    for msg in recent:
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')[:200]
        context_parts.append(f"{role}: {content}")

    return "\n".join(context_parts)


def get_recent_context_for_fidelity(manager) -> str:
    """
    Get recent conversation context for context-aware fidelity calculation.

    Extracts topic keywords from recent user messages to provide semantic context.

    Returns:
        String containing recent topic context (empty string if no history)
    """
    history = get_conversation_history(manager)
    if not history:
        return ""

    user_messages = [msg for msg in history if msg.get('role') == 'user']
    if not user_messages:
        return ""

    recent_user = user_messages[-2:]
    context_parts = []
    for msg in recent_user:
        content = msg.get('content', '')[:100]
        if content:
            context_parts.append(content)

    return " | ".join(context_parts)


def create_telos_error_response(turn_number: int, direction: str, error: str) -> Dict:
    """
    Create error response when TELOS command processing fails.

    Args:
        turn_number: Current turn number
        direction: User's attempted direction
        error: Error message

    Returns:
        Dict containing error response data
    """
    error_response = (
        f"I understand you want to shift focus to: **{direction}**\n\n"
        f"However, I encountered an issue processing this request. "
        f"Let's continue with our current focus, and you can try the TELOS command again.\n\n"
        f"*Technical note: {error}*"
    )

    return {
        'turn_number': turn_number,
        'timestamp': datetime.now().isoformat(),
        'user_input': f"TELOS: {direction}",
        'governance_mode': 'telos_pivot_error',
        'is_telos_command': True,
        'error': error,
        'shown_response': error_response,
        'shown_source': 'steward_error',
        'user_fidelity': 0.5,
        'display_fidelity': 0.5,
        'fidelity_level': 'orange',
        'intervention_triggered': False,
        'telos_analysis': {
            'response': error_response,
            'error': error,
        }
    }

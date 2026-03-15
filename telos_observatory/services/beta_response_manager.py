"""
Beta Response Manager - FIDELITY-FIRST Governance Demo
======================================================

Redesigned BETA mode that demonstrates TELOS governance in action:
- Calculate user fidelity FIRST before deciding on response type
- Only show TELOS intervention when drift is detected
- Color-coded user messages based on calculated fidelity
- Pre-generated Steward interpretation for intervention cases

Orchestrator pattern: delegates to extracted service modules:
- fidelity_service: Two-layer drift detection and fidelity calculation
- steward_service: Response generation, intervention prompts, interpretations
- governance_trace_service: Trace recording for observability
- pa_initialization: Engine setup, PA derivation, centroid management
- turn_storage_service: Turn data persistence and conversation history

NO A/B testing - just pure TELOS demonstration.
"""

import streamlit as st
from typing import Dict, Optional
from datetime import datetime
import logging
import numpy as np

# Import TELOS command detection
from telos_observatory.services.pa_enrichment import detect_telos_command

# Import ALL thresholds from single source of truth
from telos_core.constants import (
    FIDELITY_GREEN, FIDELITY_YELLOW, FIDELITY_ORANGE, FIDELITY_RED,
    SIMILARITY_BASELINE as CONSTANTS_SIMILARITY_BASELINE,
    INTERVENTION_THRESHOLD as CONSTANTS_INTERVENTION_THRESHOLD,
    BASIN_CENTER, BASIN_TOLERANCE,
    ST_FIDELITY_GREEN, ST_FIDELITY_YELLOW, ST_FIDELITY_ORANGE, ST_FIDELITY_RED,
)

# Import display normalization
from telos_observatory.services.fidelity_display import (
    normalize_fidelity_for_display,
    normalize_ai_response_fidelity,
)

# Import rescaling for SentenceTransformer-based fidelity
from telos_core.embedding_provider import rescale_sentence_transformer_fidelity

# Import Steward styling
from telos_observatory.config.steward_styles import (
    get_steward_style,
    get_response_opener,
    get_style_interpolation
)

# Import Semantic Interpreter
from telos_core.semantic_interpreter import (
    compute_behavioral_fidelity,
    get_behavioral_fidelity_band
)

# Telemetric Keys
try:
    from telos_privacy.cryptography.telemetric_keys import TelemetricSessionManager
    TELEMETRIC_KEYS_AVAILABLE = True
except ImportError:
    TELEMETRIC_KEYS_AVAILABLE = False

# Adaptive Context System
try:
    from telos_core.adaptive_context import (
        AdaptiveContextManager,
        AdaptiveContextResult,
        MessageType,
        ConversationPhase,
    )
    ADAPTIVE_CONTEXT_AVAILABLE = True
except ImportError:
    ADAPTIVE_CONTEXT_AVAILABLE = False

# SCI feature flag
ADAPTIVE_CONTEXT_ENABLED = True

# Extracted service modules
from telos_observatory.services.fidelity_service import (
    calculate_user_fidelity,
    get_fidelity_level,
    get_thresholds,
    cosine_similarity,
    compute_telos_metrics_lightweight,
    DISPLAY_GREEN_THRESHOLD,
)
from telos_observatory.services.steward_service import (
    generate_native_response,
    generate_redirect_response,
    regenerate_aligned_response,
    generate_steward_interpretation,
    MAX_TOKENS_GREEN,
    MAX_TOKENS_YELLOW,
    MAX_TOKENS_ORANGE,
    MAX_TOKENS_RED,
)
from telos_observatory.services.governance_trace_service import (
    record_fidelity_trace,
    record_intervention_trace,
)
from telos_observatory.services.pa_initialization import (
    initialize_telos_engine,
    derive_pa_from_first_message,
    handle_telos_command,
    regenerate_pa_centroid,
    detect_intent_from_purpose,
    INTENT_TO_ROLE_MAP,
)
from telos_observatory.services.turn_storage_service import (
    store_turn_data,
    get_conversation_history,
    get_recent_context,
    get_recent_context_for_fidelity,
    create_telos_error_response,
)

logger = logging.getLogger(__name__)

# Local aliases
SIMILARITY_BASELINE = CONSTANTS_SIMILARITY_BASELINE
BASIN = BASIN_CENTER
TOLERANCE = BASIN_TOLERANCE
INTERVENTION_THRESHOLD = CONSTANTS_INTERVENTION_THRESHOLD


class BetaResponseManager:
    """Manages response generation and storage for BETA testing."""

    def __init__(self, state_manager, backend_client=None):
        """
        Initialize with reference to state manager.

        Args:
            state_manager: Reference to the main StateManager
            backend_client: Optional BackendService for delta transmission
        """
        self.state_manager = state_manager
        self.telos_engine = None
        self.backend = backend_client

        # Dual PA components for Primacy State calculation
        self.user_pa_embedding = None
        self.ai_pa_embedding = None
        self.ps_calculator = None
        self.embedding_provider = None

        # Template mode: SentenceTransformer with rescaling
        self.use_rescaled_fidelity = False
        self.st_embedding_provider = None
        self.st_ai_pa_embedding = None

        # MPNet provider for AI fidelity
        self.mpnet_embedding_provider = None
        self.mpnet_ai_pa_embedding = None
        self.mpnet_user_pa_embedding = None

        # PA Enrichment Service
        self.pa_enrichment_service = None

        # Telemetric Keys
        self.telemetric_manager = None
        if TELEMETRIC_KEYS_AVAILABLE:
            try:
                session_id = st.session_state.get('session_id', f'beta_{id(self)}')
                self.telemetric_manager = TelemetricSessionManager(session_id)
                logger.info(f"Telemetric Keys initialized for session: {session_id}")
            except Exception as e:
                logger.warning(f"Could not initialize Telemetric Keys: {e}")
                self.telemetric_manager = None

        # Adaptive Context System
        self.adaptive_context_manager = None
        self.adaptive_context_enabled = ADAPTIVE_CONTEXT_ENABLED and ADAPTIVE_CONTEXT_AVAILABLE
        if self.adaptive_context_enabled:
            try:
                self.adaptive_context_manager = AdaptiveContextManager()
                logger.info("AdaptiveContextManager initialized for session")
            except Exception as e:
                logger.warning(f"Could not initialize AdaptiveContextManager: {e}")
                self.adaptive_context_manager = None
                self.adaptive_context_enabled = False

        self.last_adaptive_context_result: Optional['AdaptiveContextResult'] = None

    # ================================================================
    # Delegate methods to extracted services
    # ================================================================

    def _get_thresholds(self) -> dict:
        return get_thresholds(self.use_rescaled_fidelity)

    def _cosine_similarity(self, vec1, vec2) -> float:
        return cosine_similarity(vec1, vec2)

    def _get_fidelity_level(self, fidelity: float) -> str:
        return get_fidelity_level(fidelity, self.use_rescaled_fidelity)

    def _calculate_user_fidelity(self, user_input: str, use_context: bool = True) -> tuple:
        return calculate_user_fidelity(self, user_input, use_context)

    def _generate_native_response(self, user_input: str) -> str:
        return generate_native_response(self, user_input)

    def _regenerate_aligned_response(self, user_input, drifted_response, ai_fidelity, user_fidelity, previous_aligned_response=None):
        return regenerate_aligned_response(self, user_input, drifted_response, ai_fidelity, user_fidelity, previous_aligned_response)

    def _generate_steward_interpretation(self, telos_data, shown_source, turn_number, focus_shifted=False):
        return generate_steward_interpretation(telos_data, shown_source, turn_number, self.use_rescaled_fidelity, focus_shifted)

    def _compute_telos_metrics_lightweight(self, user_input, response, user_fidelity):
        return compute_telos_metrics_lightweight(self, user_input, response, user_fidelity)

    def _store_turn_data(self, turn_number: int, data: Dict):
        store_turn_data(self, turn_number, data)

    def _get_conversation_history(self) -> list:
        return get_conversation_history(self)

    def _get_recent_context(self) -> str:
        return get_recent_context(self)

    def _get_recent_context_for_fidelity(self) -> str:
        return get_recent_context_for_fidelity(self)

    def _create_telos_error_response(self, turn_number, direction, error):
        response_data = create_telos_error_response(turn_number, direction, error)
        self._store_turn_data(turn_number, response_data)
        return response_data

    def _initialize_telos_engine(self):
        initialize_telos_engine(self)

    def _detect_intent_from_purpose(self, purpose: str) -> str:
        return detect_intent_from_purpose(purpose)

    def _derive_pa_from_first_message(self, user_input: str):
        derive_pa_from_first_message(self, user_input)

    def _handle_telos_command(self, new_direction: str, turn_number: int) -> Dict:
        return handle_telos_command(self, new_direction, turn_number)

    def _regenerate_pa_centroid(self, example_queries: list):
        regenerate_pa_centroid(self, example_queries)

    # ================================================================
    # Main orchestrator method
    # ================================================================

    def generate_turn_responses(self,
                               user_input: str,
                               turn_number: int,
                               sequence: Dict = None) -> Dict:
        """
        FIDELITY-FIRST response generation.

        Flow:
        1. Check for PA pending derivation (Start Fresh mode)
        2. Calculate user prompt fidelity FIRST
        3. Decide intervention level based on fidelity
        4. Generate appropriate response (governed or native)
        5. Pre-generate Steward interpretation if intervention triggered

        Args:
            user_input: The user's message
            turn_number: Current turn number
            sequence: IGNORED - kept for backward compatibility

        Returns:
            Dict containing response data with fidelity-based decision
        """
        logger.info(f"=== FIDELITY-FIRST Turn {turn_number} ===")
        logger.info(f"User input: {user_input[:100]}...")

        # PA ESTABLISHMENT TURN DETECTION
        is_pa_establishment_turn = False

        if st.session_state.get('pa_pending_derivation', False) and turn_number == 1:
            logger.info("START FRESH MODE: Deriving PA from first message...")
            self._derive_pa_from_first_message(user_input)
            st.session_state.pa_pending_derivation = False
            is_pa_establishment_turn = True

        pa_was_just_shifted = st.session_state.get('pa_just_shifted', False)
        if pa_was_just_shifted:
            st.session_state.pa_just_shifted = False

        # CHECK FOR TELOS COMMAND (PA Redirect)
        is_telos_command, new_direction = detect_telos_command(user_input)
        if is_telos_command and new_direction:
            logger.info(f"TELOS COMMAND DETECTED: {new_direction}")
            return self._handle_telos_command(new_direction, turn_number)

        # Initialize response data
        response_data = {
            'turn_number': turn_number,
            'timestamp': datetime.now().isoformat(),
            'user_input': user_input,
            'governance_mode': 'fidelity_first',
            'focus_shifted': pa_was_just_shifted,
        }

        # STEP 1: Calculate User Fidelity
        if is_pa_establishment_turn:
            user_fidelity = 1.0
            raw_similarity = 1.0
            baseline_hard_block = False
        else:
            user_fidelity, raw_similarity, baseline_hard_block = self._calculate_user_fidelity(user_input)

        print(f"FIDELITY DEBUG Turn {turn_number}: user_fidelity={user_fidelity:.3f}, raw_sim={raw_similarity:.3f}, baseline_block={baseline_hard_block}")

        response_data['user_fidelity'] = user_fidelity
        response_data['raw_similarity'] = raw_similarity
        response_data['baseline_hard_block'] = baseline_hard_block
        response_data['fidelity_level'] = self._get_fidelity_level(user_fidelity)

        model_type = 'sentence_transformer' if self.use_rescaled_fidelity else 'mistral'
        response_data['display_fidelity'] = normalize_fidelity_for_display(user_fidelity, model_type)

        # STEP 2: TWO-TIER INTERVENTION DECISION
        thresholds = self._get_thresholds()
        threshold_green = thresholds['green']
        threshold_yellow = thresholds['yellow']
        threshold_orange = thresholds['orange']

        in_basin = user_fidelity >= threshold_orange
        in_green_zone = user_fidelity >= threshold_green
        in_yellow_zone = user_fidelity >= threshold_yellow and user_fidelity < threshold_green

        response_data['layer1_triggered'] = baseline_hard_block
        response_data['layer2_in_basin'] = in_basin
        response_data['in_green_zone'] = in_green_zone
        response_data['in_yellow_zone'] = in_yellow_zone

        # GOVERNANCE TRACE: Record fidelity calculation
        saai_block = record_fidelity_trace(
            self, turn_number, raw_similarity,
            response_data['display_fidelity'],
            baseline_hard_block, in_basin,
        )

        if saai_block:
            drift_pct = saai_block['drift_pct']
            response_data['saai_blocked'] = True
            response_data['saai_drift_level'] = saai_block['saai_drift_level']
            response_data['saai_drift_magnitude'] = saai_block['saai_drift_magnitude']
            response_data['response'] = (
                "**Session Drift Alert**\n\n"
                "This conversation has drifted significantly from its original purpose. "
                f"Current drift: **{drift_pct}**\n\n"
                "Per SAAI safety protocols, an operator review is required before continuing.\n\n"
                "_This is a governance intervention designed to ensure AI alignment._"
            )
            response_data['shown_source'] = 'saai_blocked'
            response_data['intervention_triggered'] = True
            response_data['intervention_reason'] = 'saai_cumulative_drift_block'
            return response_data

        should_intervene = baseline_hard_block or user_fidelity < threshold_green

        if not should_intervene:
            # GREEN zone: TELOS native flow
            response_data = self._handle_green_zone(
                user_input, turn_number, user_fidelity,
                response_data, pa_was_just_shifted
            )
        else:
            # YELLOW, ORANGE, or RED zone: Steward intervention
            response_data = self._handle_intervention_zone(
                user_input, turn_number, user_fidelity,
                baseline_hard_block, in_basin,
                thresholds, response_data, pa_was_just_shifted
            )

        # STEP 3: Store Turn Data
        self._store_turn_data(turn_number, response_data)

        # SCI INTEGRATION: Set previous turn data
        try:
            if self.adaptive_context_manager and hasattr(self.adaptive_context_manager, 'context_buffer'):
                user_embedding = getattr(self, 'last_user_input_embedding', None)
                ai_embedding = None
                if hasattr(self.adaptive_context_manager.context_buffer, '_last_ai_embedding'):
                    ai_embedding = self.adaptive_context_manager.context_buffer._last_ai_embedding

                turn_fidelity = response_data.get('user_fidelity', 0.0)

                if user_embedding is not None:
                    self.adaptive_context_manager.context_buffer.set_previous_turn(
                        user_embedding=user_embedding,
                        ai_embedding=ai_embedding,
                        fidelity=turn_fidelity
                    )
                    logger.info(f"SCI: Set previous turn (fidelity={turn_fidelity:.3f})")
        except Exception as e:
            logger.debug(f"SCI set_previous_turn skipped: {e}")

        return response_data

    def _handle_green_zone(self, user_input, turn_number, user_fidelity, response_data, pa_was_just_shifted):
        """Handle GREEN zone: native response + AI fidelity check + realignment."""
        thresholds = self._get_thresholds()
        threshold_green = thresholds['green']
        zone = "GREEN"
        logger.info(f"GREEN zone (fidelity {user_fidelity:.3f} >= {threshold_green}): TELOS native flow")

        response_data['intervention_triggered'] = False
        response_data['intervention_reason'] = None
        response_data['shown_source'] = 'native'

        native_response = self._generate_native_response(user_input)
        response_data['native_response'] = native_response

        ai_fidelity = None
        ai_response_intervened = False
        final_response = native_response

        # Ensure ST PA embeddings are loaded
        if not hasattr(self, 'st_user_pa_embedding') or self.st_user_pa_embedding is None:
            if 'cached_st_user_pa_embedding' in st.session_state:
                self.st_user_pa_embedding = st.session_state.cached_st_user_pa_embedding
            elif self.st_embedding_provider is not None:
                if 'user_pa' in st.session_state and hasattr(st.session_state.user_pa, 'purpose'):
                    pa_text = f"{st.session_state.user_pa.purpose} {st.session_state.user_pa.scope}"
                    self.st_user_pa_embedding = np.array(self.st_embedding_provider.encode(pa_text))
                    st.session_state.cached_st_user_pa_embedding = self.st_user_pa_embedding

        if not hasattr(self, 'st_ai_pa_embedding') or self.st_ai_pa_embedding is None:
            if 'cached_st_ai_pa_embedding' in st.session_state:
                self.st_ai_pa_embedding = st.session_state.cached_st_ai_pa_embedding

        # AI RESPONSE FIDELITY CHECK
        if self.st_embedding_provider:
            try:
                response_embedding = np.array(self.st_embedding_provider.encode(native_response))
                response_embedding = response_embedding / (np.linalg.norm(response_embedding) + 1e-10)

                if self.adaptive_context_manager and hasattr(self.adaptive_context_manager, 'context_buffer'):
                    self.adaptive_context_manager.context_buffer.add_ai_response(native_response, response_embedding)

                # GREEN ZONE: measure against USER_PA
                if user_fidelity >= DISPLAY_GREEN_THRESHOLD:
                    st_user_pa = getattr(self, 'st_user_pa_embedding', None)
                    if st_user_pa is not None:
                        raw_ai_fidelity = self._cosine_similarity(response_embedding, st_user_pa)
                        ai_fidelity = normalize_ai_response_fidelity(raw_ai_fidelity)
                else:
                    pa_embedding_for_ai = getattr(self, 'st_ai_pa_embedding', None) or getattr(self, 'st_user_pa_embedding', None)
                    if pa_embedding_for_ai is not None:
                        raw_ai_fidelity = self._cosine_similarity(response_embedding, pa_embedding_for_ai)
                        ai_fidelity = normalize_ai_response_fidelity(raw_ai_fidelity)
                    else:
                        ai_fidelity = 0.50

                # AI RESPONSE DRIFT INTERVENTION
                MAX_REALIGNMENT_ATTEMPTS = 2
                pa_embedding_for_ai = getattr(self, 'st_ai_pa_embedding', None) or getattr(self, 'st_user_pa_embedding', None)

                if user_fidelity >= DISPLAY_GREEN_THRESHOLD and ai_fidelity is not None and ai_fidelity < DISPLAY_GREEN_THRESHOLD:
                    original_ai_fidelity = ai_fidelity

                    # Get previous aligned response for context inheritance
                    previous_aligned_response = None
                    if turn_number > 1:
                        turn_cache = st.session_state.get('turn_cache', {})
                        prev_turn = turn_cache.get(turn_number - 1, {})
                        prev_telos = prev_turn.get('telos_analysis', {})
                        prev_ai_fidelity = prev_telos.get('ai_pa_fidelity', 0.0)
                        if prev_ai_fidelity >= DISPLAY_GREEN_THRESHOLD:
                            previous_aligned_response = prev_telos.get('response', None)

                    current_response = native_response
                    best_response = native_response
                    best_fidelity = ai_fidelity
                    attempt = 0

                    while ai_fidelity < DISPLAY_GREEN_THRESHOLD and attempt < MAX_REALIGNMENT_ATTEMPTS:
                        attempt += 1
                        aligned_response = self._regenerate_aligned_response(
                            user_input=user_input,
                            drifted_response=current_response,
                            ai_fidelity=ai_fidelity,
                            user_fidelity=user_fidelity,
                            previous_aligned_response=previous_aligned_response
                        )

                        if aligned_response:
                            new_embedding = np.array(self.st_embedding_provider.encode(aligned_response))
                            new_raw_ai_fidelity = self._cosine_similarity(new_embedding, pa_embedding_for_ai)
                            new_ai_fidelity = normalize_ai_response_fidelity(new_raw_ai_fidelity)

                            if new_ai_fidelity > best_fidelity:
                                best_response = aligned_response
                                best_fidelity = new_ai_fidelity

                            if new_ai_fidelity > ai_fidelity:
                                current_response = aligned_response
                                ai_fidelity = new_ai_fidelity
                                final_response = aligned_response
                                ai_response_intervened = True
                                if ai_fidelity >= DISPLAY_GREEN_THRESHOLD:
                                    break

                    if best_fidelity > original_ai_fidelity:
                        final_response = best_response
                        ai_fidelity = best_fidelity
                        ai_response_intervened = True

                    if ai_response_intervened:
                        response_data['ai_response_realigned'] = True
                        response_data['original_ai_fidelity'] = original_ai_fidelity
                        response_data['realignment_attempts'] = attempt

            except Exception as e:
                logger.error(f"AI fidelity check failed: {e}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
        else:
            response_data['ai_fidelity_check_skipped'] = True

        response_data['shown_response'] = final_response

        # Compute Primacy State
        primacy_state = None
        display_primacy_state = None
        if ai_fidelity is not None:
            epsilon = 1e-8
            primacy_state = (2 * user_fidelity * ai_fidelity) / (user_fidelity + ai_fidelity + epsilon)
            display_user_fidelity = response_data['display_fidelity']
            display_primacy_state = (2 * display_user_fidelity * ai_fidelity) / (display_user_fidelity + ai_fidelity + epsilon)

        telos_data = {
            'response': final_response,
            'fidelity_score': None,
            'distance_from_pa': 1.0 - user_fidelity,
            'intervention_triggered': ai_response_intervened,
            'intervention_type': 'ai_response_realignment' if ai_response_intervened else None,
            'intervention_reason': 'AI response drifted from user purpose' if ai_response_intervened else None,
            'drift_detected': ai_response_intervened,
            'in_basin': True,
            'ai_pa_fidelity': ai_fidelity,
            'primacy_state_score': primacy_state,
            'display_primacy_state': display_primacy_state,
            'primacy_state_condition': 'computed',
            'pa_correlation': None,
            'lightweight_path': not ai_response_intervened,
            'user_pa_fidelity': user_fidelity,
            'display_user_pa_fidelity': response_data['display_fidelity'],
            'fidelity_level': response_data['fidelity_level'],
            'ai_response_intervened': ai_response_intervened,
        }

        response_data['telos_analysis'] = telos_data
        return response_data

    def _handle_intervention_zone(self, user_input, turn_number, user_fidelity,
                                  baseline_hard_block, in_basin,
                                  thresholds, response_data, pa_was_just_shifted):
        """Handle YELLOW/ORANGE/RED zones: Steward intervention."""
        threshold_green = thresholds['green']
        threshold_yellow = thresholds['yellow']
        threshold_orange = thresholds['orange']

        if user_fidelity >= threshold_yellow:
            intervention_reason = "Minor drift from your stated purpose - Steward is gently guiding you back"
            intervention_strength = "soft"
            zone = "YELLOW"
        elif user_fidelity >= threshold_orange:
            intervention_reason = "Drift from your stated purpose detected - Steward is guiding you back"
            intervention_strength = "moderate"
            zone = "ORANGE"
        else:
            intervention_reason = "Significant drift detected - Steward intervention activated"
            intervention_strength = "strong"
            zone = "RED"
            response_data['offer_pivot'] = True
            response_data['suggested_pivot_direction'] = user_input

        logger.info(f"{zone} zone (fidelity {user_fidelity:.3f}): {intervention_strength}")

        response_data['intervention_triggered'] = True
        response_data['intervention_reason'] = intervention_reason
        response_data['intervention_strength'] = intervention_strength
        response_data['shown_source'] = 'steward'

        # GOVERNANCE TRACE: Record intervention
        record_intervention_trace(
            self, user_fidelity, response_data['display_fidelity'],
            zone, baseline_hard_block, in_basin,
        )

        # Steward styling
        steward_style = get_steward_style(user_fidelity, green_threshold=threshold_green)
        steward_interpolation = get_style_interpolation(user_fidelity, green_threshold=threshold_green)

        response_data['steward_style'] = {
            'band': steward_style.band,
            'band_name': steward_style.band_name,
            'tone': steward_style.tone,
            'directness': steward_interpolation['directness'],
            'urgency': steward_interpolation['urgency'],
            'opener': get_response_opener(user_fidelity, green_threshold=threshold_green),
        }

        # Proportional brevity
        if zone == "YELLOW":
            max_tokens = MAX_TOKENS_YELLOW
        elif zone == "ORANGE":
            max_tokens = MAX_TOKENS_ORANGE
        else:
            max_tokens = MAX_TOKENS_RED

        # Generate redirect response
        telos_data = generate_redirect_response(
            manager=self,
            user_input=user_input,
            turn_number=turn_number,
            zone=zone,
            max_tokens=max_tokens,
            user_input_fidelity=user_fidelity
        )

        telos_data['intervention_triggered'] = True
        telos_data['intervention_reason'] = intervention_reason
        telos_data['display_user_pa_fidelity'] = response_data['display_fidelity']
        telos_data['fidelity_level'] = response_data['fidelity_level']
        telos_data['in_basin'] = False

        # BEHAVIORAL FIDELITY
        ai_response_text = telos_data.get('response', '')
        if ai_response_text:
            behavioral_fidelity = compute_behavioral_fidelity(
                ai_response=ai_response_text,
                user_fidelity=response_data['display_fidelity']
            )
        else:
            behavioral_fidelity = 0.70

        telos_data['ai_pa_fidelity'] = behavioral_fidelity

        # Recalculate Primacy State with behavioral fidelity
        epsilon = 1e-10
        f_user_display = response_data['display_fidelity']
        f_ai = behavioral_fidelity
        telos_data['primacy_state_score'] = (2 * f_user_display * f_ai) / (f_user_display + f_ai + epsilon)
        telos_data['display_primacy_state'] = telos_data['primacy_state_score']

        response_data['telos_analysis'] = telos_data

        # Apply Steward opener
        raw_response = telos_data.get('response', '')
        steward_opener = response_data['steward_style'].get('opener', '')

        if steward_opener and raw_response and not pa_was_just_shifted:
            response_data['shown_response'] = f"{steward_opener}\n\n{raw_response}"
        else:
            response_data['shown_response'] = raw_response

        # Pre-generate Steward interpretation
        response_data['steward_interpretation'] = self._generate_steward_interpretation(
            telos_data, 'telos', turn_number, focus_shifted=pa_was_just_shifted
        )
        response_data['has_steward_interpretation'] = True

        return response_data

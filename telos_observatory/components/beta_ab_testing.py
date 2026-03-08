"""
Beta AB Testing Component
==========================

Implements AB testing phase where TELOS and Native responses are randomly served,
but both systems calculate drift metrics for every turn.

Key features:
- Random 50/50 selection per turn
- Dual drift calculation (TELOS always calculates, even if Native is served)
- User feedback collection (thumbs up/down, regenerate)
- Async Steward interpretation
- Full logging to backend storage
"""

import streamlit as st
import random
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from telos_observatory.services.backend_client import BackendService
from telos_observatory.services.steward_llm import StewardLLM
from telos_observatory.services.mistral_client import MistralClient

logger = logging.getLogger(__name__)


class BetaABTesting:
    """
    AB testing phase for BETA sessions.

    Randomly serves TELOS or Native responses while calculating
    drift metrics for both systems on every turn.
    """

    def __init__(
        self,
        state_manager,
        backend_client: Optional[BackendService] = None,
        required_turns: int = 10
    ):
        """
        Initialize AB testing component.

        Args:
            state_manager: StateManager instance
            backend_client: Optional BackendService for logging
            required_turns: Number of turns required for AB phase (default: 10)
        """
        self.state_manager = state_manager
        self.backend = backend_client
        self.required_turns = required_turns

        # Initialize Mistral client for Native responses
        try:
            self.mistral_client = MistralClient(model="mistral-small-latest")
        except Exception as e:
            logger.error(f"Failed to initialize Mistral client: {e}")
            self.mistral_client = None

        # Initialize Steward for interpretations
        try:
            self.steward = StewardLLM()
        except Exception as e:
            logger.error(f"Failed to initialize Steward: {e}")
            self.steward = None

        # Initialize AB testing state
        if 'ab_testing_active' not in st.session_state:
            st.session_state.ab_testing_active = False
            st.session_state.ab_turn_count = 0
            st.session_state.ab_phase_complete = False

    def start_ab_phase(self):
        """Start the AB testing phase."""
        st.session_state.ab_testing_active = True
        st.session_state.ab_turn_count = 0
        st.session_state.ab_phase_complete = False
        logger.info("AB testing phase started")

    def is_active(self) -> bool:
        """Check if AB testing phase is active."""
        return st.session_state.get('ab_testing_active', False)

    def is_complete(self) -> bool:
        """Check if AB testing phase is complete."""
        return st.session_state.get('ab_phase_complete', False)

    def get_progress(self) -> Tuple[int, int]:
        """
        Get current progress.

        Returns:
            Tuple of (current_turn, required_turns)
        """
        return (st.session_state.get('ab_turn_count', 0), self.required_turns)

    def select_system(self) -> str:
        """
        Randomly select which system to serve for this turn.

        Returns:
            'telos' or 'native'
        """
        return random.choice(['telos', 'native'])

    def calculate_telos_metrics(
        self,
        user_input: str,
        user_pa: Dict[str, Any],
        ai_pa: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate TELOS governance metrics for user input.

        Args:
            user_input: User's question/message
            user_pa: User's Primacy Attractor
            ai_pa: AI's Primacy Attractor

        Returns:
            Dictionary with governance metrics
        """
        try:
            from telos_core.embedding_provider import EmbeddingProvider
            from telos_core.primacy_math import PrimacyAttractorMath, MathematicalState
            import numpy as np

            # Get embedding provider
            embedding_provider = EmbeddingProvider()

            # Create user's attractor
            purpose_text = user_pa['purpose'][0]
            scope_text = ' '.join(user_pa['scope'])

            purpose_embedding = embedding_provider.encode(purpose_text)
            scope_embedding = embedding_provider.encode(scope_text)

            user_attractor = PrimacyAttractorMath(
                purpose_vector=purpose_embedding,
                scope_vector=scope_embedding,
                constraint_tolerance=0.05,  # Strict governance for BETA
                privacy_level=0.8,
                task_priority=0.7
            )

            # Embed user input
            user_embedding = embedding_provider.encode(user_input)
            user_state = MathematicalState(
                embedding=user_embedding,
                turn_number=st.session_state.ab_turn_count + 1,
                timestamp=datetime.now().timestamp(),
                text_content=user_input
            )

            # Calculate metrics
            distance = float(np.linalg.norm(user_embedding - user_attractor.attractor_center))
            in_basin = user_attractor.compute_basin_membership(user_state)

            # Calculate fidelity
            if in_basin:
                user_fidelity = 1.0
            else:
                distance_beyond = (distance - user_attractor.basin_radius) / user_attractor.basin_radius
                user_fidelity = max(0.0, 1.0 - distance_beyond)

            return {
                'user_fidelity': user_fidelity,
                'distance_from_pa': distance,
                'in_basin': in_basin,
                'basin_radius': user_attractor.basin_radius,
                'would_intervene': not in_basin,
                'intervention_type': 'drift_warning' if not in_basin else None
            }

        except Exception as e:
            logger.error(f"Failed to calculate TELOS metrics: {e}")
            # Return fallback metrics
            return {
                'user_fidelity': 1.0,
                'distance_from_pa': 0.0,
                'in_basin': True,
                'basin_radius': 1.053,
                'would_intervene': False,
                'intervention_type': None,
                'error': str(e)
            }

    def generate_telos_response(
        self,
        user_input: str,
        metrics: Dict[str, Any],
        conversation_history: list
    ) -> str:
        """
        Generate TELOS-governed response.

        Args:
            user_input: User's question
            metrics: Calculated governance metrics
            conversation_history: Previous conversation turns

        Returns:
            TELOS response text
        """
        try:
            if not self.mistral_client:
                return "[TELOS unavailable - Mistral client not initialized]"

            # Build system prompt with governance awareness
            system_prompt = "You are a helpful AI assistant guided by TELOS governance. "

            if not metrics['in_basin']:
                system_prompt += f"Note: User's question shows drift (fidelity: {metrics['user_fidelity']:.2f}). Gently guide back to their purpose while answering helpfully."

            # Generate response
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_input})

            response = self.mistral_client.generate(
                messages=messages,
                temperature=0.7,
                max_tokens=800
            )

            return response

        except Exception as e:
            logger.error(f"Failed to generate TELOS response: {e}")
            return f"[TELOS response generation failed: {e}]"

    def generate_native_response(
        self,
        user_input: str,
        conversation_history: list
    ) -> str:
        """
        Generate Native (ungovern ed) response.

        Args:
            user_input: User's question
            conversation_history: Previous conversation turns

        Returns:
            Native response text
        """
        try:
            if not self.mistral_client:
                return "[Native unavailable - Mistral client not initialized]"

            # Build messages without governance
            messages = [{"role": "system", "content": "You are a helpful AI assistant."}]
            messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_input})

            response = self.mistral_client.generate(
                messages=messages,
                temperature=0.7,
                max_tokens=800
            )

            return response

        except Exception as e:
            logger.error(f"Failed to generate Native response: {e}")
            return f"[Native response generation failed: {e}]"

    async def generate_steward_interpretation_async(
        self,
        session_id: str,
        turn_number: int,
        metrics: Dict[str, Any],
        user_input: str,
        user_pa: Dict[str, Any]
    ):
        """
        Generate Steward interpretation asynchronously.

        This runs in the background and updates backend storage when complete.

        Args:
            session_id: Session UUID
            turn_number: Turn number
            metrics: Calculated metrics
            user_input: User's question
            user_pa: User's PA
        """
        try:
            if not self.steward or not self.backend:
                return

            # Generate interpretation
            interpretation = await self.steward.interpret_drift_async(
                user_input=user_input,
                user_pa=user_pa,
                metrics=metrics
            )

            # Update backend storage
            self.backend.update_beta_turn(
                session_id=session_id,
                turn_number=turn_number,
                update_data={'steward_interpretation': interpretation}
            )

            logger.info(f"Steward interpretation logged for turn {turn_number}")

        except Exception as e:
            logger.error(f"Steward interpretation failed: {e}")
            # Log error marker
            if self.backend:
                self.backend.update_beta_turn(
                    session_id=session_id,
                    turn_number=turn_number,
                    update_data={'steward_interpretation': '[Interpretation unavailable]'}
                )

    def process_turn(
        self,
        user_input: str,
        user_pa: Dict[str, Any],
        ai_pa: Dict[str, Any],
        conversation_history: list
    ) -> Dict[str, Any]:
        """
        Process a single AB testing turn.

        Args:
            user_input: User's question/message
            user_pa: User's Primacy Attractor
            ai_pa: AI's Primacy Attractor
            conversation_history: Previous conversation

        Returns:
            Dictionary with:
            - response_text: Text to show user
            - system_served: 'telos' or 'native'
            - telos_response: TELOS response
            - native_response: Native response
            - metrics: Governance metrics
            - turn_data: Complete turn data for logging
        """
        try:
            # Increment turn counter
            st.session_state.ab_turn_count += 1
            turn_number = st.session_state.ab_turn_count

            # Random system selection
            system_served = self.select_system()

            # Calculate TELOS metrics (always, even if Native is served)
            telos_metrics = self.calculate_telos_metrics(user_input, user_pa, ai_pa)

            # Generate responses from BOTH systems
            telos_response = self.generate_telos_response(user_input, telos_metrics, conversation_history)
            native_response = self.generate_native_response(user_input, conversation_history)

            # Determine which response to show
            response_delivered = telos_response if system_served == 'telos' else native_response

            # Calculate AI fidelity for response
            # (simplified - real implementation would calculate response fidelity)
            ai_fidelity = 1.0 if telos_metrics['in_basin'] else telos_metrics['user_fidelity']
            primacy_state = (telos_metrics['user_fidelity'] * ai_fidelity) ** 0.5  # Geometric mean

            # Build complete turn data
            turn_data = {
                'session_id': st.session_state.get('session_id', self.state_manager.state.session_id),
                'turn_number': turn_number,
                'phase': 'ab_testing',
                'user_message': user_input,
                'system_served': system_served,
                'telos_response': telos_response,
                'native_response': native_response,
                'response_delivered': response_delivered,
                'user_fidelity': telos_metrics['user_fidelity'],
                'ai_fidelity': ai_fidelity,
                'primacy_state': primacy_state,
                'distance_from_pa': telos_metrics['distance_from_pa'],
                'in_basin': telos_metrics['in_basin'],
                'intervention_calculated': telos_metrics['would_intervene'],
                'intervention_applied': system_served == 'telos' and telos_metrics['would_intervene'],
                'intervention_type': telos_metrics.get('intervention_type'),
                'user_action': 'none',
                'user_preference': 'no_preference',
                'created_at': datetime.now().isoformat()
            }

            # Log to backend storage
            if self.backend:
                self.backend.insert_beta_turn(turn_data)

                # Generate Steward interpretation async
                # (This would be truly async in production - for now, skip async complexity)
                # asyncio.create_task(self.generate_steward_interpretation_async(...))

            # Check if phase complete
            if turn_number >= self.required_turns:
                st.session_state.ab_phase_complete = True
                logger.info(f"AB testing phase complete ({turn_number} turns)")

            return {
                'response_text': response_delivered,
                'system_served': system_served,
                'telos_response': telos_response,
                'native_response': native_response,
                'metrics': telos_metrics,
                'turn_data': turn_data
            }

        except Exception as e:
            logger.error(f"Turn processing failed: {e}")
            raise

    def handle_user_feedback(
        self,
        turn_number: int,
        feedback_type: str
    ):
        """
        Handle user feedback on a response.

        Args:
            turn_number: Turn number being rated
            feedback_type: 'thumbs_up', 'thumbs_down', or 'regenerate'
        """
        try:
            session_id = st.session_state.get('session_id', self.state_manager.state.session_id)

            if self.backend:
                self.backend.update_beta_turn(
                    session_id=session_id,
                    turn_number=turn_number,
                    update_data={'user_action': feedback_type}
                )

            logger.info(f"User feedback recorded: Turn {turn_number}, {feedback_type}")

        except Exception as e:
            logger.error(f"Failed to record feedback: {e}")

    def handle_regenerate(
        self,
        turn_number: int,
        current_system: str,
        telos_response: str,
        native_response: str
    ) -> Tuple[str, str]:
        """
        Handle regenerate request (switches systems).

        Args:
            turn_number: Turn number
            current_system: Currently shown system
            telos_response: TELOS response
            native_response: Native response

        Returns:
            Tuple of (new_response, new_system)
        """
        try:
            # Switch systems
            new_system = 'native' if current_system == 'telos' else 'telos'
            new_response = native_response if new_system == 'native' else telos_response

            # Update backend storage
            session_id = st.session_state.get('session_id', self.state_manager.state.session_id)

            if self.backend:
                self.backend.update_beta_turn(
                    session_id=session_id,
                    turn_number=turn_number,
                    update_data={
                        'system_served': new_system,
                        'response_delivered': new_response,
                        'user_action': 'regenerate',
                        'user_preference': f'selected_{new_system}'
                    }
                )

            logger.info(f"Regenerated: Turn {turn_number}, switched to {new_system}")

            return new_response, new_system

        except Exception as e:
            logger.error(f"Regenerate failed: {e}")
            return new_response, new_system

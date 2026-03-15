"""
Backend Client Service for TELOS Observatory V3.
Handles delta-only transmission to research database.
NO conversation content is ever transmitted.

This module provides an abstract interface for backend data storage.
Configure your own backend service via environment variables or secrets.
"""

import streamlit as st
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import os


class BackendService:
    """
    Service for transmitting governance deltas to backend storage (privacy-preserving).

    This is an abstract interface that can connect to any backend service.
    The default implementation uses Supabase, but can be adapted to any
    database or API service that supports the required operations.

    Privacy Guarantee: Only governance METRICS are transmitted, never conversation content.
    """

    def __init__(self):
        """Initialize backend client from Streamlit secrets or environment."""
        self.client: Optional[Any] = None
        self.enabled = False
        self._initialize_client()

    def _initialize_client(self):
        """Initialize backend client if credentials are available."""
        try:
            # Check for backend credentials in secrets or environment
            backend_url = None
            backend_key = None

            # Try Streamlit secrets first
            if hasattr(st, 'secrets'):
                backend_url = st.secrets.get('BACKEND_URL') or st.secrets.get('SUPABASE_URL')
                backend_key = st.secrets.get('BACKEND_KEY') or st.secrets.get('SUPABASE_KEY')

            # Fall back to environment variables
            if not backend_url:
                backend_url = os.getenv('BACKEND_URL') or os.getenv('SUPABASE_URL')
            if not backend_key:
                backend_key = os.getenv('BACKEND_KEY') or os.getenv('SUPABASE_KEY')

            if backend_url and backend_key:
                # Initialize the backend client
                # Using Supabase as default implementation
                try:
                    from supabase import create_client, Client
                    self.client = create_client(backend_url, backend_key)
                    self.enabled = True
                    print("✓ Backend client initialized successfully")
                except ImportError:
                    print("⚠ Supabase package not installed - delta transmission disabled")
                    self.enabled = False
            else:
                print("⚠ Backend credentials not found - delta transmission disabled")
                self.enabled = False

        except Exception as e:
            print(f"⚠ Failed to initialize backend client: {e}")
            self.enabled = False

    def transmit_delta(self, delta_data: Dict[str, Any]) -> bool:
        """
        Transmit a single governance delta to backend storage.

        Args:
            delta_data: Dictionary containing governance metrics (NO content)
                Required fields:
                - session_id: UUID of session
                - turn_number: Turn number in conversation
                - fidelity_score: Float 0.0-1.0
                - distance_from_pa: Float >= 0.0
                Optional fields:
                - delta_from_previous: Float
                - intervention_triggered: Boolean
                - intervention_type: String
                - intervention_reason: String (brief, NO content quotes)
                - mode: String ('demo', 'beta', 'open')
                - model_used: String
                - user_pa_fidelity: Float (user input fidelity to PA)
                - ai_pa_fidelity: Float (AI response fidelity to PA)
                - primacy_state_score: Float (combined PS score)
                - raw_similarity: Float (raw cosine before normalization)
                - realignment_attempts: Integer (number of realignment attempts)
                - ai_response_intervened: Boolean (whether AI was realigned)

        Returns:
            bool: True if transmission successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            # Validate required fields
            required_fields = ['session_id', 'turn_number', 'fidelity_score', 'distance_from_pa']
            for field in required_fields:
                if field not in delta_data:
                    print(f"❌ Missing required field: {field}")
                    return False

            # Insert delta into governance_deltas table
            result = self.client.table('governance_deltas').insert(delta_data).execute()

            if result.data:
                print(f"✓ Delta transmitted: Turn {delta_data['turn_number']}, Fidelity {delta_data['fidelity_score']:.3f}")
                return True
            else:
                print(f"❌ Delta transmission failed (no data returned)")
                return False

        except Exception as e:
            print(f"❌ Error transmitting delta: {e}")
            return False

    def log_consent(self, session_id: uuid.UUID, consent_statement: str, consent_version: str) -> bool:
        """
        Log beta consent to immutable audit trail.

        Args:
            session_id: Session UUID
            consent_statement: Full text of consent statement
            consent_version: Version string (e.g., '3.0')

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            consent_data = {
                'session_id': str(session_id),
                'consent_statement': consent_statement,
                'consent_version': consent_version,
                'consent_timestamp': datetime.now().isoformat()
            }

            result = self.client.table('beta_consent_log').insert(consent_data).execute()

            if result.data:
                print(f"✓ Consent logged: Session {session_id}, Version {consent_version}")
                return True
            else:
                print(f"❌ Consent logging failed")
                return False

        except Exception as e:
            print(f"❌ Error logging consent: {e}")
            return False

    def update_session_summary(self, session_id: uuid.UUID, summary_data: Dict[str, Any]) -> bool:
        """
        Update or create session summary with aggregated metrics.

        Args:
            session_id: Session UUID
            summary_data: Dictionary containing session-level aggregated metrics

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            upsert_data = {
                'session_id': str(session_id),
                **summary_data,
                'updated_at': datetime.now().isoformat()
            }

            result = self.client.table('session_summaries').upsert(upsert_data).execute()

            if result.data:
                print(f"✓ Session summary updated: {session_id}")
                return True
            else:
                print(f"❌ Session summary update failed")
                return False

        except Exception as e:
            print(f"❌ Error updating session summary: {e}")
            return False

    def log_pa_config(self, session_id: uuid.UUID, config_data: Dict[str, Any]) -> bool:
        """
        Log Primacy Attractor configuration metadata (NO actual content).

        Args:
            session_id: Session UUID
            config_data: Dictionary containing PA structure metadata
                - purpose_elements: Integer (count of purpose statements)
                - scope_elements: Integer (count of scope items)
                - boundary_elements: Integer (count of boundaries)
                - constraint_tolerance: Float
                - mode: String

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            pa_data = {
                'session_id': str(session_id),
                **config_data,
                'created_at': datetime.now().isoformat()
            }

            result = self.client.table('primacy_attractor_configs').insert(pa_data).execute()

            if result.data:
                print(f"✓ PA config logged: {session_id}")
                return True
            else:
                print(f"❌ PA config logging failed")
                return False

        except Exception as e:
            print(f"❌ Error logging PA config: {e}")
            return False

    def update_turn_lifecycle(self, session_id: uuid.UUID, turn_number: int,
                              status: str, stage: str, error_message: Optional[str] = None,
                              delta_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update turn lifecycle status with progressive stage tracking.

        Args:
            session_id: Session UUID
            turn_number: Turn number
            status: Turn status ('initiated', 'calculating_pa', 'evaluating', 'completed', 'failed')
            stage: Human-readable processing stage description
            error_message: Optional error message if failed
            delta_data: Optional governance metrics to include in update

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            update_data = {
                'session_id': str(session_id),
                'turn_number': turn_number,
                'turn_status': status,
                'processing_stage': stage,
                'stage_timestamp': datetime.now().isoformat()
            }

            if error_message:
                update_data['error_message'] = error_message

            if delta_data:
                update_data.update(delta_data)

            result = self.client.table('governance_deltas')\
                .upsert(update_data, on_conflict='session_id,turn_number')\
                .execute()

            if result.data:
                print(f"✓ Lifecycle update: Turn {turn_number}, Status: {status}, Stage: {stage}")
                return True
            else:
                print(f"❌ Lifecycle update failed")
                return False

        except Exception as e:
            print(f"❌ Error updating turn lifecycle: {e}")
            return False

    def initiate_turn(self, session_id: uuid.UUID, turn_number: int, mode: str) -> bool:
        """Mark turn as initiated - first lifecycle event."""
        return self.update_turn_lifecycle(
            session_id=session_id,
            turn_number=turn_number,
            status='initiated',
            stage='Turn initiated - awaiting user input',
            delta_data={
                'mode': mode,
                'fidelity_score': 1.0,
                'distance_from_pa': 0.0
            }
        )

    def mark_calculating_pa(self, session_id: uuid.UUID, turn_number: int) -> bool:
        """Mark turn as calculating Primacy Attractor distance."""
        return self.update_turn_lifecycle(
            session_id=session_id,
            turn_number=turn_number,
            status='calculating_pa',
            stage='Computing distance from Primacy Attractor',
            delta_data={
                'fidelity_score': 1.0,
                'distance_from_pa': 0.0
            }
        )

    def mark_evaluating(self, session_id: uuid.UUID, turn_number: int) -> bool:
        """Mark turn as evaluating governance metrics."""
        return self.update_turn_lifecycle(
            session_id=session_id,
            turn_number=turn_number,
            status='evaluating',
            stage='Running governance evaluation',
            delta_data={
                'fidelity_score': 1.0,
                'distance_from_pa': 0.0
            }
        )

    def complete_turn(self, session_id: uuid.UUID, turn_number: int,
                     final_delta: Dict[str, Any]) -> bool:
        """Mark turn as completed with final governance metrics."""
        return self.update_turn_lifecycle(
            session_id=session_id,
            turn_number=turn_number,
            status='completed',
            stage='Governance evaluation complete',
            delta_data=final_delta
        )

    def fail_turn(self, session_id: uuid.UUID, turn_number: int,
                 error_message: str, stage: str) -> bool:
        """Mark turn as failed with error details."""
        return self.update_turn_lifecycle(
            session_id=session_id,
            turn_number=turn_number,
            status='failed',
            stage=f'Failed at: {stage}',
            error_message=error_message
        )

    def insert_beta_session(self, session_data: Dict[str, Any]) -> bool:
        """Create a new BETA session record."""
        if not self.enabled:
            return False

        try:
            result = self.client.table('beta_sessions').insert(session_data).execute()

            if result.data:
                print(f"✓ BETA session created: {session_data['session_id']}")
                return True
            else:
                print(f"❌ BETA session creation failed")
                return False

        except Exception as e:
            print(f"❌ Error creating BETA session: {e}")
            return False

    def insert_beta_turn(self, turn_data: Dict[str, Any]) -> bool:
        """Create a new BETA turn record."""
        if not self.enabled:
            return False

        try:
            result = self.client.table('beta_turns').insert(turn_data).execute()

            if result.data:
                print(f"✓ BETA turn logged: Session {turn_data['session_id']}, Turn {turn_data['turn_number']}")
                return True
            else:
                print(f"❌ BETA turn logging failed")
                return False

        except Exception as e:
            print(f"❌ Error logging BETA turn: {e}")
            return False

    def update_beta_turn(self, session_id: str, turn_number: int,
                        update_data: Dict[str, Any]) -> bool:
        """Update an existing BETA turn record."""
        if not self.enabled:
            return False

        try:
            result = self.client.table('beta_turns')\
                .update(update_data)\
                .eq('session_id', session_id)\
                .eq('turn_number', turn_number)\
                .execute()

            if result.data:
                print(f"✓ BETA turn updated: Session {session_id}, Turn {turn_number}")
                return True
            else:
                print(f"❌ BETA turn update failed")
                return False

        except Exception as e:
            print(f"❌ Error updating BETA turn: {e}")
            return False

    def get_beta_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve BETA session data."""
        if not self.enabled:
            return None

        try:
            result = self.client.table('beta_sessions')\
                .select('*')\
                .eq('session_id', session_id)\
                .single()\
                .execute()

            if result.data:
                print(f"✓ Retrieved BETA session: {session_id}")
                return result.data
            else:
                print(f"❌ BETA session not found: {session_id}")
                return None

        except Exception as e:
            print(f"❌ Error retrieving BETA session: {e}")
            return None

    def get_beta_turns(self, session_id: str) -> list:
        """Retrieve all turns for a BETA session."""
        if not self.enabled:
            return []

        try:
            result = self.client.table('beta_turns')\
                .select('*')\
                .eq('session_id', session_id)\
                .order('turn_number')\
                .execute()

            if result.data:
                print(f"✓ Retrieved {len(result.data)} BETA turns for session {session_id}")
                return result.data
            else:
                print(f"⚠ No BETA turns found for session {session_id}")
                return []

        except Exception as e:
            print(f"❌ Error retrieving BETA turns: {e}")
            return []

    def complete_beta_session(self, session_id: str, total_turns: int) -> bool:
        """Mark BETA session as completed."""
        if not self.enabled:
            return False

        try:
            update_data = {
                'completed_at': datetime.now().isoformat(),
                'total_turns': total_turns,
                'phase_1_complete': True
            }

            result = self.client.table('beta_sessions')\
                .update(update_data)\
                .eq('session_id', session_id)\
                .execute()

            if result.data:
                print(f"✓ BETA session completed: {session_id}")
                return True
            else:
                print(f"❌ BETA session completion failed")
                return False

        except Exception as e:
            print(f"❌ Error completing BETA session: {e}")
            return False

    def test_connection(self) -> bool:
        """Test backend connection."""
        if not self.enabled:
            print("❌ Backend not enabled")
            return False

        try:
            result = self.client.table('session_summaries').select('session_id').limit(1).execute()
            print("✓ Backend connection test successful")
            return True

        except Exception as e:
            print(f"❌ Backend connection test failed: {e}")
            return False


# Singleton instance
_backend_service = None


def get_backend_service() -> BackendService:
    """Get or create singleton backend service instance."""
    global _backend_service
    if _backend_service is None:
        _backend_service = BackendService()
    return _backend_service


# Backwards compatibility aliases
SupabaseService = BackendService
get_supabase_service = get_backend_service

"""
A/B Test Manager for TELOS Observatory BETA.
Manages experiment assignment and metrics collection.
"""

import streamlit as st
import random
import hashlib
from typing import Dict, Any, Optional, Literal
from datetime import datetime
import uuid


class ABTestManager:
    """
    Manages A/B testing for TELOS Observatory experiments.

    Current experiments:
    1. Observatory Lens visibility (show/hide advanced visualizations)
    2. Intervention aggressiveness (standard vs aggressive)
    3. Onboarding flow (minimal vs detailed)
    """

    def __init__(self):
        """Initialize A/B test manager."""
        self.experiments = {
            'observatory_lens': {
                'name': 'Observatory Lens Default Visibility',
                'description': 'Tests whether showing Observatory Lens by default improves engagement',
                'control': False,  # Hidden by default
                'treatment': True,  # Shown by default
                'allocation': 0.5  # 50/50 split
            },
            'intervention_style': {
                'name': 'Intervention Aggressiveness',
                'description': 'Tests different intervention thresholds',
                'control': 'standard',  # Standard thresholds
                'treatment': 'sensitive',  # More sensitive thresholds
                'allocation': 0.5
            },
            'onboarding_style': {
                'name': 'Onboarding Experience',
                'description': 'Tests minimal vs detailed onboarding',
                'control': 'minimal',  # Quick start
                'treatment': 'detailed',  # Full explanation
                'allocation': 0.5
            }
        }

        # Initialize session assignments if not exists
        if 'ab_test_assignments' not in st.session_state:
            st.session_state.ab_test_assignments = self._assign_experiments()
            st.session_state.ab_test_metrics = {
                'session_id': str(uuid.uuid4()),
                'assignment_timestamp': datetime.now().isoformat(),
                'experiments': st.session_state.ab_test_assignments.copy(),
                'metrics': {}
            }

    def _assign_experiments(self) -> Dict[str, Any]:
        """
        Assign user to experiment groups.
        Uses deterministic assignment based on session ID for consistency.

        Returns:
            Dict mapping experiment names to assigned values
        """
        assignments = {}

        # Generate stable random seed for this session
        session_seed = random.random()

        for exp_name, exp_config in self.experiments.items():
            # Determine assignment based on allocation
            if session_seed < exp_config['allocation']:
                assignments[exp_name] = exp_config['treatment']
            else:
                assignments[exp_name] = exp_config['control']

        return assignments

    def get_variant(self, experiment_name: str) -> Any:
        """
        Get the assigned variant for an experiment.

        Args:
            experiment_name: Name of the experiment

        Returns:
            The assigned variant value (control or treatment)
        """
        if experiment_name not in self.experiments:
            # Default to control if experiment doesn't exist
            return self.experiments.get(experiment_name, {}).get('control')

        # Safely check and initialize ab_test_assignments
        try:
            assignments = st.session_state.ab_test_assignments
        except AttributeError:
            # Initialize if not exists
            st.session_state.ab_test_assignments = self._assign_experiments()
            assignments = st.session_state.ab_test_assignments

            # Also initialize metrics if needed
            if 'ab_test_metrics' not in st.session_state:
                st.session_state.ab_test_metrics = {
                    'session_id': str(uuid.uuid4()),
                    'assignment_timestamp': datetime.now().isoformat(),
                    'experiments': assignments.copy(),
                    'metrics': {}
                }

        return assignments.get(
            experiment_name,
            self.experiments[experiment_name]['control']
        )

    def is_treatment_group(self, experiment_name: str) -> bool:
        """
        Check if user is in treatment group for an experiment.

        Args:
            experiment_name: Name of the experiment

        Returns:
            True if in treatment group, False if in control
        """
        variant = self.get_variant(experiment_name)
        exp_config = self.experiments.get(experiment_name, {})
        return variant == exp_config.get('treatment')

    def track_metric(self, metric_name: str, value: Any, metadata: Optional[Dict] = None):
        """
        Track a metric for A/B test analysis.

        Args:
            metric_name: Name of the metric (e.g., 'engagement_time', 'completion_rate')
            value: The metric value
            metadata: Additional context for the metric
        """
        if 'ab_test_metrics' not in st.session_state:
            return

        # Initialize metrics list if needed
        if metric_name not in st.session_state.ab_test_metrics['metrics']:
            st.session_state.ab_test_metrics['metrics'][metric_name] = []

        # Record the metric
        metric_entry = {
            'timestamp': datetime.now().isoformat(),
            'value': value
        }

        if metadata:
            metric_entry['metadata'] = metadata

        st.session_state.ab_test_metrics['metrics'][metric_name].append(metric_entry)

    def track_event(self, event_name: str, properties: Optional[Dict] = None):
        """
        Track an event for A/B test analysis.

        Args:
            event_name: Name of the event (e.g., 'button_clicked', 'feature_used')
            properties: Event properties
        """
        self.track_metric(
            metric_name=f'event_{event_name}',
            value=1,  # Count
            metadata=properties
        )

    def get_experiment_config(self) -> Dict[str, Any]:
        """
        Get the full experiment configuration for logging.

        Returns:
            Complete experiment setup and assignments
        """
        return {
            'experiments': self.experiments,
            'assignments': st.session_state.ab_test_assignments,
            'session_metrics': st.session_state.ab_test_metrics
        }

    def export_metrics_for_backend(self) -> Dict[str, Any]:
        """
        Export metrics in format suitable for backend storage.

        Returns:
            Dictionary ready for database insertion
        """
        metrics = st.session_state.ab_test_metrics.copy()

        # Calculate aggregate metrics
        aggregates = {}
        for metric_name, values in metrics.get('metrics', {}).items():
            if values:
                if metric_name.startswith('event_'):
                    # Count events
                    aggregates[metric_name] = len(values)
                else:
                    # Average other metrics
                    numeric_values = [v['value'] for v in values if isinstance(v.get('value'), (int, float))]
                    if numeric_values:
                        aggregates[f'{metric_name}_avg'] = sum(numeric_values) / len(numeric_values)
                        aggregates[f'{metric_name}_count'] = len(numeric_values)

        return {
            'session_id': metrics.get('session_id'),
            'assignment_timestamp': metrics.get('assignment_timestamp'),
            'experiments': metrics.get('experiments'),
            'aggregate_metrics': aggregates,
            'raw_metrics': metrics.get('metrics')
        }

    def apply_experiment_configs(self):
        """
        Apply experiment configurations to the session state.
        This should be called at the start of the app to set up experiments.
        """
        # Ensure assignments are initialized first
        if 'ab_test_assignments' not in st.session_state:
            st.session_state.ab_test_assignments = self._assign_experiments()

        # Apply Observatory Lens visibility experiment
        if self.is_treatment_group('observatory_lens'):
            if 'show_observatory_lens' not in st.session_state:
                st.session_state.show_observatory_lens = True
                self.track_event('observatory_lens_default_shown')

        # Apply intervention style experiment
        intervention_style = self.get_variant('intervention_style')
        st.session_state.intervention_sensitivity = intervention_style

        # Apply onboarding style experiment
        onboarding_style = self.get_variant('onboarding_style')
        st.session_state.onboarding_style = onboarding_style

        # Track experiment application
        self.track_event('experiments_applied', {
            'assignments': st.session_state.ab_test_assignments
        })


# Singleton instance
_ab_test_manager = None

def get_ab_test_manager() -> ABTestManager:
    """Get or create singleton A/B test manager instance."""
    global _ab_test_manager
    if _ab_test_manager is None:
        _ab_test_manager = ABTestManager()
    return _ab_test_manager
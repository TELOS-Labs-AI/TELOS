"""
Beta Sequence Generator - TELOS Governance Demo
================================================

Simplified for 5-turn TELOS-only demonstration (no A/B testing).
All turns are TELOS-governed to demonstrate fidelity monitoring.
"""

import random
from typing import List, Dict, Literal
from datetime import datetime


class BetaSequenceGenerator:
    """Generates sequence for BETA sessions - all TELOS-governed."""

    def __init__(self):
        """Initialize the sequence generator."""
        self.sequence = []
        self.current_index = 0

    def generate_session_sequence(self) -> Dict:
        """
        Generate a complete test sequence for a 5-turn BETA session.

        All 5 turns are TELOS-governed (no A/B testing).
        Purpose: Demonstrate TELOS fidelity monitoring and governance.

        Returns:
            Dict with turn assignments and metadata
        """
        sequence = {
            'session_id': f"beta_{datetime.now().timestamp()}",
            'generated_at': datetime.now().isoformat(),
            'turns': {},
            'statistics': {
                'total_telos': 5,
                'total_native': 0
            }
        }

        # All 5 turns are TELOS-governed
        for turn in range(1, 6):
            sequence['turns'][turn] = {
                'test_type': 'telos_governed',
                'response_source': 'telos',
                'phase': 1
            }

        # Statistics
        sequence['statistics']['guaranteed_distribution'] = {
            'telos_governed': 5,
            'total_turns': 5
        }

        return sequence

    def get_turn_config(self, sequence: Dict, turn_number: int) -> Dict:
        """
        Get the configuration for a specific turn.

        Args:
            sequence: The pre-generated sequence
            turn_number: Current turn number

        Returns:
            Configuration dict for this turn
        """
        if turn_number not in sequence['turns']:
            # Beyond beta testing
            return {
                'test_type': 'complete',
                'response_source': 'telos',  # Full TELOS after beta
                'phase': 3
            }

        return sequence['turns'][turn_number]

    def should_generate_telos(self, sequence: Dict, turn_number: int) -> bool:
        """
        Determine if TELOS should be generated for this turn.

        Args:
            sequence: The pre-generated sequence
            turn_number: Current turn number

        Returns:
            True if TELOS should be generated
        """
        config = self.get_turn_config(sequence, turn_number)

        if config['test_type'] == 'head_to_head':
            return True  # Always generate both for comparison
        elif config['test_type'] == 'single_blind':
            return config['response_source'] == 'telos'
        else:
            return True  # Default to TELOS after beta

    def should_generate_native(self, sequence: Dict, turn_number: int) -> bool:
        """
        Determine if native response should be generated for this turn.

        Args:
            sequence: The pre-generated sequence
            turn_number: Current turn number

        Returns:
            True if native should be generated
        """
        config = self.get_turn_config(sequence, turn_number)

        if config['test_type'] == 'head_to_head':
            return True  # Always generate both for comparison
        elif config['test_type'] == 'single_blind':
            return config['response_source'] == 'native'
        else:
            return False  # No native after beta

    def format_intervention_explanation(self,
                                       turn_number: int,
                                       intervention_applied: bool,
                                       intervention_reason: str,
                                       response_source: str) -> str:
        """
        Format Steward's explanation for why an intervention was or wasn't applied.

        Args:
            turn_number: The turn number
            intervention_applied: Whether intervention was actually applied
            intervention_reason: The reason for intervention (if any)
            response_source: Which response was shown ('telos', 'native', 'both')

        Returns:
            Formatted explanation string
        """
        if response_source == 'native':
            return f"""
            **Turn {turn_number} - Native Response (No TELOS)**

            This turn used the native LLM response without TELOS governance.
            No intervention was possible as TELOS was not active.

            This is part of the A/B testing to compare governed vs ungoverned responses.
            """

        elif response_source == 'telos':
            if intervention_applied:
                return f"""
                **Turn {turn_number} - TELOS Intervention Applied**

                Reason: {intervention_reason}

                The TELOS governance system detected drift from your established
                Primacy Attractor and applied an intervention to maintain alignment.
                """
            else:
                return f"""
                **Turn {turn_number} - TELOS Active (No Intervention Needed)**

                The response was within acceptable alignment boundaries.
                TELOS monitored but did not need to intervene.

                Fidelity remained above threshold, indicating good alignment.
                """

        else:  # head_to_head
            return f"""
            **Turn {turn_number} - Head-to-Head Comparison**

            Both TELOS and native responses were generated.
            You were shown both options to compare directly.

            TELOS intervention status: {intervention_applied}
            {f"Intervention reason: {intervention_reason}" if intervention_applied else "No intervention needed"}
            """


# Example usage:
if __name__ == "__main__":
    generator = BetaSequenceGenerator()

    # Generate sequence at session start
    sequence = generator.generate_session_sequence()

    print("Generated Beta Test Sequence:")
    print(f"Session ID: {sequence['session_id']}")
    print(f"\nTurn Assignments:")

    for turn, config in sequence['turns'].items():
        print(f"  Turn {turn}: {config['test_type']} - {config['response_source']}")

    print(f"\nStatistics:")
    for key, value in sequence['statistics'].items():
        print(f"  {key}: {value}")

    # Test individual turn lookups
    print(f"\nTurn 3: Generate TELOS? {generator.should_generate_telos(sequence, 3)}")
    print(f"Turn 3: Generate Native? {generator.should_generate_native(sequence, 3)}")
    print(f"Turn 8: Generate TELOS? {generator.should_generate_telos(sequence, 8)}")
    print(f"Turn 8: Generate Native? {generator.should_generate_native(sequence, 8)}")
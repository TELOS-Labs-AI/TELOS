"""
PA Enrichment Service
=====================

Transforms raw user input into semantically rich PA structures.
When user types "TELOS: learn kubernetes", this service generates:
- Purpose statement
- Scope definitions
- Example queries for centroid construction

This enables the Steward to act as PA architect, translating user intent
into well-formed attractors with proper discriminative power.
"""

import re
import json
from typing import Optional, Dict, List, Tuple
from mistralai import Mistral


# TELOS command patterns
TELOS_PATTERNS = [
    r'^TELOS:\s*(.+)$',           # TELOS: new direction
    r'^/TELOS\s+(.+)$',           # /TELOS new direction
    r'^telos:\s*(.+)$',           # telos: (lowercase)
    r'^/telos\s+(.+)$',           # /telos (lowercase)
]


def detect_telos_command(user_input: str) -> Tuple[bool, Optional[str]]:
    """
    Detect if user input contains a TELOS redirect command.

    Args:
        user_input: Raw user message

    Returns:
        (is_telos_command, new_direction) tuple

    Examples:
        >>> detect_telos_command("TELOS: learn kubernetes")
        (True, "learn kubernetes")
        >>> detect_telos_command("How do I deploy?")
        (False, None)
    """
    user_input = user_input.strip()

    for pattern in TELOS_PATTERNS:
        match = re.match(pattern, user_input, re.IGNORECASE)
        if match:
            direction = match.group(1).strip()
            return (True, direction)

    return (False, None)


PA_ENRICHMENT_PROMPT = """You are a PA (Primacy Attractor) architect for the TELOS governance system.

The user is PIVOTING to a new direction. Generate a PA structure that broadly encompasses this direction.

User's NEW direction: "{direction}"

IMPORTANT: The user is explicitly changing focus. Do NOT inherit constraints from any previous session type.
Focus entirely on what the user wants to do NOW.

Generate a JSON object with exactly this structure:
{{
    "purpose": "A broad, inclusive statement of what this session enables (1-2 sentences). Be EXPANSIVE, not narrow.",
    "scope": [
        "Broad topic area 1 that's in-bounds",
        "Broad topic area 2 that's in-bounds",
        "Broad topic area 3 that's in-bounds",
        "Broad topic area 4 that's in-bounds",
        "Broad topic area 5 that's in-bounds"
    ],
    "boundaries": [
        "What's truly unrelated (be conservative - when in doubt, include it)",
        "Another clear boundary"
    ],
    "example_queries": [
        "Technical discussion query",
        "Architecture/design query",
        "Implementation/coding query",
        "Debugging/troubleshooting query",
        "Conceptual/explanation query",
        "Planning/roadmap query",
        "Review/feedback query",
        "Integration/dependency query",
        "Testing/validation query",
        "Documentation/communication query"
    ],
    "steward_acknowledgment": "A brief, professional acknowledgment of the focus shift (2-3 sentences)"
}}

CRITICAL RULES:
1. example_queries MUST be 10 specific questions covering DIFFERENT INTERACTION MODES:
   - Technical discussion (describing architecture, explaining how something works)
   - Implementation (writing code, building features)
   - Debugging (fixing issues, troubleshooting)
   - Planning (roadmaps, timelines, priorities)
   - Review (code review, design review, feedback)
   - Conceptual (explaining concepts, teaching)
   - Integration (dependencies, connections between systems)
2. Make the purpose BROAD - if user says "work on codebase", include ALL ways of working on it
3. scope should have 5 items covering the breadth of the topic
4. boundaries should only exclude truly UNRELATED topics (e.g., cooking recipes for a coding session)
5. steward_acknowledgment should feel collaborative and welcoming

Return ONLY the JSON object, no other text."""


class PAEnrichmentService:
    """
    Service for enriching raw user directions into full PA structures.
    """

    def __init__(self, mistral_client: Mistral):
        self.client = mistral_client
        self.model = "mistral-small-latest"

    def enrich_direction(
        self,
        direction: str,
        current_template: Optional[Dict] = None,
        conversation_context: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Transform a raw direction into a full PA structure.

        Args:
            direction: User's stated new direction (e.g., "learn kubernetes")
            current_template: NOT USED - kept for API compatibility
            conversation_context: NOT USED - kept for API compatibility

        Returns:
            Enriched PA structure or None on error

        Note: We intentionally do NOT use current_template or conversation_context
        because the user is explicitly pivoting to a NEW direction. The old context
        would bias the PA too narrowly.
        """
        # Format prompt with just the direction - no context from previous template
        prompt = PA_ENRICHMENT_PROMPT.format(direction=direction)

        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Lower temp for structured output
            )

            content = response.choices[0].message.content.strip()

            # Extract JSON from response
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            pa_structure = json.loads(content)

            # Validate required fields
            required_fields = ["purpose", "scope", "example_queries", "steward_acknowledgment"]
            for field in required_fields:
                if field not in pa_structure:
                    print(f"[PA Enrichment] Missing required field: {field}")
                    return None

            # Ensure we have enough example queries
            if len(pa_structure.get("example_queries", [])) < 5:
                print("[PA Enrichment] Not enough example queries generated")
                return None

            return pa_structure

        except json.JSONDecodeError as e:
            print(f"[PA Enrichment] JSON parse error: {e}")
            return None
        except Exception as e:
            print(f"[PA Enrichment] Error: {e}")
            return None

    def generate_pivot_response(
        self,
        enriched_pa: Dict,
        previous_focus: Optional[str] = None
    ) -> str:
        """
        Generate the Steward's acknowledgment of the PA pivot.

        This creates a substantial response that shows the new PA and
        invites the user to continue exploring the new direction.

        Args:
            enriched_pa: The newly generated PA structure
            previous_focus: Description of what we were focused on before

        Returns:
            Steward response text (displayed as conversation turn)
        """
        acknowledgment = enriched_pa.get("steward_acknowledgment", "")
        purpose = enriched_pa.get("purpose", "")
        scope = enriched_pa.get("scope", [])
        boundaries = enriched_pa.get("boundaries", [])

        # Build a more substantial response that feels like a proper transition
        lines = []

        # Header - clear indication of the shift
        lines.append("**Session Focus Updated**\n")

        # New purpose - prominently displayed
        lines.append("**Your New Session Purpose:**")
        lines.append(f"> {purpose}\n")

        # Scope - what's now in bounds
        if scope:
            lines.append("**What We Can Explore Together:**")
            for item in scope[:5]:  # Show up to 5 scope items
                lines.append(f"- {item}")
            lines.append("")

        # Boundaries - brief mention if available
        if boundaries and len(boundaries) > 0:
            lines.append("**Outside Our Current Focus:**")
            for item in boundaries[:2]:  # Show just 2 boundaries
                lines.append(f"- {item}")
            lines.append("")

        # Steward acknowledgment - the personal touch
        if acknowledgment:
            # Strip any markdown separators (---, ***, etc.) from the acknowledgment
            clean_acknowledgment = acknowledgment.replace("---", "").replace("***", "").strip()
            if clean_acknowledgment:
                lines.append(clean_acknowledgment)

        # Invitation to continue
        lines.append("\n**Ready when you are.** What would you like to explore first?")

        return "\n".join(lines)


def create_enrichment_service(mistral_client: Mistral) -> PAEnrichmentService:
    """Factory function to create PA enrichment service."""
    return PAEnrichmentService(mistral_client)

"""
Primacy Attractor Extraction Service
=====================================

Extracts PA components (purpose, scope, boundaries) from user statements
using LLM reasoning for expedited PA establishment in BETA testing.
"""

import json
import logging
from typing import Dict, Any, Optional
from telos_observatory.services.mistral_client import MistralClient

logger = logging.getLogger(__name__)


class PAExtractor:
    """
    Extracts Primacy Attractor components from user statements.

    Uses LLM to analyze user's stated goal/purpose and derive:
    - Purpose: What the user wants to accomplish
    - Scope: Domains/topics that serve the purpose
    - Boundaries: What to avoid or stay away from
    """

    def __init__(self, client: Optional[MistralClient] = None):
        """
        Initialize PA extractor.

        Args:
            client: Optional MistralClient instance (creates new one if not provided)
        """
        self.client = client or MistralClient(model="mistral-small-latest")

    def extract_from_statement(self, user_statement: str) -> Dict[str, Any]:
        """
        Extract PA components from user's statement.

        Args:
            user_statement: User's goal/purpose statement (1-2 sentences)

        Returns:
            Dictionary with PA components:
            {
                "purpose": ["primary goal statement"],
                "scope": ["relevant topic 1", "relevant topic 2", ...],
                "boundaries": ["avoid X", "stay focused on Y", ...],
                "raw_statement": "original user statement"
            }

        Raises:
            Exception: If extraction fails
        """

        extraction_prompt = f"""You are a TELOS PA (Primacy Attractor) extraction expert.

Your task: Analyze the user's statement and extract governance components.

User's statement:
"{user_statement}"

Extract the following components:

1. PURPOSE: The user's primary goal/objective (1 sentence)
2. SCOPE: Relevant topics/domains that serve this purpose (3-5 items)
3. BOUNDARIES: What to avoid or stay away from (2-3 items)

Return ONLY a valid JSON object in this exact format:
{{
    "purpose": ["single purpose statement"],
    "scope": ["topic1", "topic2", "topic3"],
    "boundaries": ["avoid1", "avoid2"]
}}

Guidelines:
- PURPOSE should be clear, actionable, specific
- SCOPE should list concrete topics that support the purpose
- BOUNDARIES should define what's out of scope or could derail the purpose
- Be concise and specific

Return ONLY the JSON object, no additional text."""

        try:
            # Generate extraction
            response = self.client.generate(
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.3,  # Low temperature for consistent extraction
                max_tokens=500
            )

            # Parse JSON response
            # Clean response if it has markdown code blocks
            response_cleaned = response.strip()
            if response_cleaned.startswith("```json"):
                response_cleaned = response_cleaned[7:]  # Remove ```json
            if response_cleaned.startswith("```"):
                response_cleaned = response_cleaned[3:]  # Remove ```
            if response_cleaned.endswith("```"):
                response_cleaned = response_cleaned[:-3]  # Remove trailing ```
            response_cleaned = response_cleaned.strip()

            # Parse JSON
            pa_components = json.loads(response_cleaned)

            # Validate structure
            required_keys = ["purpose", "scope", "boundaries"]
            for key in required_keys:
                if key not in pa_components:
                    raise ValueError(f"Missing required key: {key}")
                if not isinstance(pa_components[key], list):
                    raise ValueError(f"{key} must be a list")

            # Add raw statement for reference
            pa_components["raw_statement"] = user_statement

            logger.info("Successfully extracted PA components")
            return pa_components

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse PA extraction JSON: {e}")
            logger.error(f"Raw response: {response}")
            # Return fallback extraction
            return self._fallback_extraction(user_statement)

        except Exception as e:
            logger.error(f"PA extraction failed: {e}")
            return self._fallback_extraction(user_statement)

    def _fallback_extraction(self, user_statement: str) -> Dict[str, Any]:
        """
        Fallback extraction when LLM fails.

        Creates a basic PA from the user statement directly.

        Args:
            user_statement: User's original statement

        Returns:
            Basic PA components
        """
        return {
            "purpose": [user_statement],
            "scope": ["General conversation", "User's stated goal"],
            "boundaries": ["Stay on topic", "Avoid unrelated subjects"],
            "raw_statement": user_statement,
            "fallback": True
        }

    def derive_ai_pa(self, user_pa: Dict[str, Any]) -> Dict[str, Any]:
        """
        Derive AI's Primacy Attractor from user's PA.

        AI PA should serve the user's purpose by:
        - Responding helpfully within scope
        - Respecting boundaries
        - Maintaining alignment with user goals

        Args:
            user_pa: User's PA components

        Returns:
            AI PA components with same structure
        """

        derivation_prompt = f"""You are a TELOS governance expert deriving an AI's Primacy Attractor.

Given the user's Primacy Attractor:

Purpose: {user_pa['purpose'][0]}
Scope: {', '.join(user_pa['scope'])}
Boundaries: {', '.join(user_pa['boundaries'])}

Derive the AI's corresponding Primacy Attractor that:
1. SERVES the user's purpose (not replicates it)
2. RESPONDS helpfully within the user's scope
3. RESPECTS the user's boundaries
4. MAINTAINS alignment with user goals

Return ONLY a valid JSON object in this exact format:
{{
    "purpose": ["how AI should serve user's purpose"],
    "scope": ["relevant response topics", "helpful domains"],
    "boundaries": ["what AI should avoid", "how to maintain alignment"]
}}

Example:
If user wants to "debug Python API authentication", AI's purpose is:
"Provide clear, practical debugging assistance for Python API authentication issues"

Return ONLY the JSON object, no additional text."""

        try:
            response = self.client.generate(
                messages=[{"role": "user", "content": derivation_prompt}],
                temperature=0.3,
                max_tokens=500
            )

            # Clean and parse response
            response_cleaned = response.strip()
            if response_cleaned.startswith("```json"):
                response_cleaned = response_cleaned[7:]
            if response_cleaned.startswith("```"):
                response_cleaned = response_cleaned[3:]
            if response_cleaned.endswith("```"):
                response_cleaned = response_cleaned[:-3]
            response_cleaned = response_cleaned.strip()

            ai_pa = json.loads(response_cleaned)

            # Validate structure
            required_keys = ["purpose", "scope", "boundaries"]
            for key in required_keys:
                if key not in ai_pa:
                    raise ValueError(f"Missing required key: {key}")
                if not isinstance(ai_pa[key], list):
                    raise ValueError(f"{key} must be a list")

            # Add reference to user PA
            ai_pa["derived_from_user_pa"] = True

            logger.info("Successfully derived AI PA")
            return ai_pa

        except Exception as e:
            logger.error(f"AI PA derivation failed: {e}")
            return self._fallback_ai_pa(user_pa)

    def _fallback_ai_pa(self, user_pa: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback AI PA derivation.

        Args:
            user_pa: User's PA

        Returns:
            Basic AI PA serving user's purpose
        """
        return {
            "purpose": [f"Assist with: {user_pa['purpose'][0]}"],
            "scope": user_pa['scope'] + ["Helpful responses", "Clarifying questions"],
            "boundaries": user_pa['boundaries'] + ["Maintain user's focus", "Avoid tangents"],
            "derived_from_user_pa": True,
            "fallback": True
        }

    def refine_pa(
        self,
        original_pa: Dict[str, Any],
        user_refinement: str
    ) -> Dict[str, Any]:
        """
        Refine PA based on user feedback.

        Used during confirmation step if user wants to adjust the extracted PA.

        Args:
            original_pa: Originally extracted PA
            user_refinement: User's refinement request

        Returns:
            Refined PA components
        """

        refinement_prompt = f"""You are refining a TELOS Primacy Attractor based on user feedback.

Original PA:
Purpose: {original_pa['purpose'][0]}
Scope: {', '.join(original_pa['scope'])}
Boundaries: {', '.join(original_pa['boundaries'])}

User's refinement request:
"{user_refinement}"

Update the PA to incorporate the user's feedback while maintaining structure.

Return ONLY a valid JSON object in this exact format:
{{
    "purpose": ["refined purpose"],
    "scope": ["refined scope items"],
    "boundaries": ["refined boundaries"]
}}

Return ONLY the JSON object, no additional text."""

        try:
            response = self.client.generate(
                messages=[{"role": "user", "content": refinement_prompt}],
                temperature=0.3,
                max_tokens=500
            )

            # Clean and parse
            response_cleaned = response.strip()
            if response_cleaned.startswith("```json"):
                response_cleaned = response_cleaned[7:]
            if response_cleaned.startswith("```"):
                response_cleaned = response_cleaned[3:]
            if response_cleaned.endswith("```"):
                response_cleaned = response_cleaned[:-3]
            response_cleaned = response_cleaned.strip()

            refined_pa = json.loads(response_cleaned)

            # Add metadata
            refined_pa["raw_statement"] = original_pa.get("raw_statement", "")
            refined_pa["refined"] = True

            logger.info("Successfully refined PA")
            return refined_pa

        except Exception as e:
            logger.error(f"PA refinement failed: {e}")
            # Return original PA if refinement fails
            return original_pa

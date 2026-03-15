"""
AI Session Summarizer for TELOS Governance
==========================================

Generates AI-powered session summaries including:
- Session title (concise description)
- Key topics discussed
- Fidelity trajectory analysis
- Intervention pattern description

Uses the existing Mistral client for provider-agnostic summarization.
Implements caching to avoid redundant API calls.

Inspired by claude-trace index-generator pattern.
"""

import json
import hashlib
import logging
from pathlib import Path

from telos_core.time_utils import utc_now
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SessionSummarizer:
    """
    AI-powered session summarizer for TELOS governance sessions.

    Features:
    - Generates session titles and descriptions
    - Analyzes fidelity trajectories
    - Identifies intervention patterns
    - Caches summaries to avoid redundant API calls
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        use_cache: bool = True,
    ):
        """
        Initialize session summarizer.

        Args:
            cache_dir: Directory for cached summaries (default: ./telos_summaries_cache)
            use_cache: Whether to use cached summaries
        """
        self.cache_dir = cache_dir or Path("./telos_summaries_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.use_cache = use_cache

        # Try to initialize Mistral client
        self._mistral_client = None
        self._init_llm_client()

    def _init_llm_client(self):
        """Initialize the LLM client for summarization."""
        try:
            from telos_observatory.services.mistral_client import MistralClient
            self._mistral_client = MistralClient()
            logger.info("Session summarizer initialized with Mistral client")
        except Exception as e:
            logger.warning(f"Mistral client not available for summarization: {e}")
            self._mistral_client = None

    def summarize_session(
        self,
        session_data: Dict[str, Any],
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate or retrieve AI summary for a session.

        Args:
            session_data: Session data from GovernanceTraceCollector.export_to_dict()
            force_regenerate: Force regeneration even if cached

        Returns:
            Summary dict with title, description, topics, trajectory, pattern
        """
        session_id = session_data.get('session_id', 'unknown')

        # Check cache first
        if self.use_cache and not force_regenerate:
            cached = self._get_cached_summary(session_id, session_data)
            if cached:
                logger.info(f"Using cached summary for session {session_id}")
                return cached

        # Generate summary
        summary = self._generate_summary(session_data)

        # Cache the result
        if self.use_cache:
            self._cache_summary(session_id, session_data, summary)

        return summary

    def _generate_summary(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate AI summary for session data.

        Args:
            session_data: Session data dictionary

        Returns:
            Summary dictionary
        """
        # Extract key metrics for analysis
        stats = session_data.get('stats', {})
        fidelity_trajectory = session_data.get('fidelity_trajectory', [])
        interventions = session_data.get('interventions', [])

        # Compute trajectory analysis
        trajectory_analysis = self._analyze_trajectory(fidelity_trajectory)

        # Compute intervention pattern
        intervention_pattern = self._analyze_interventions(interventions)

        # If LLM available, generate AI title and description
        if self._mistral_client:
            try:
                ai_summary = self._generate_ai_summary(
                    stats, fidelity_trajectory, interventions,
                    trajectory_analysis, intervention_pattern
                )
                return {
                    'title': ai_summary.get('title', 'TELOS Session'),
                    'description': ai_summary.get('description', ''),
                    'key_topics': ai_summary.get('key_topics', []),
                    'fidelity_trajectory': trajectory_analysis,
                    'intervention_pattern': intervention_pattern,
                    'generated_by': 'ai',
                    'generated_at': utc_now().isoformat(),
                }
            except Exception as e:
                logger.warning(f"AI summary generation failed, using fallback: {e}")

        # Fallback to rule-based summary
        return self._generate_fallback_summary(
            stats, trajectory_analysis, intervention_pattern
        )

    def _analyze_trajectory(self, fidelity_trajectory: List[Dict[str, Any]]) -> str:
        """
        Analyze fidelity trajectory pattern.

        Returns one of: stable, improving, degrading, volatile
        """
        if not fidelity_trajectory or len(fidelity_trajectory) < 2:
            return "insufficient_data"

        fidelities = [t.get('fidelity', 0.5) for t in fidelity_trajectory]

        # Calculate trend
        start_avg = sum(fidelities[:3]) / min(3, len(fidelities))
        end_avg = sum(fidelities[-3:]) / min(3, len(fidelities))
        overall_change = end_avg - start_avg

        # Calculate volatility
        diffs = [abs(fidelities[i] - fidelities[i-1]) for i in range(1, len(fidelities))]
        avg_volatility = sum(diffs) / len(diffs) if diffs else 0

        # Classify
        if avg_volatility > 0.15:
            return "volatile"
        elif overall_change > 0.1:
            return "improving"
        elif overall_change < -0.1:
            return "degrading"
        else:
            return "stable"

    def _analyze_interventions(self, interventions: List[Dict[str, Any]]) -> str:
        """
        Analyze intervention pattern.

        Returns one of: none, occasional, frequent, constant
        """
        count = len(interventions)

        if count == 0:
            return "none"
        elif count <= 2:
            return "occasional"
        elif count <= 5:
            return "frequent"
        else:
            return "constant"

    def _generate_ai_summary(
        self,
        stats: Dict[str, Any],
        fidelity_trajectory: List[Dict[str, Any]],
        interventions: List[Dict[str, Any]],
        trajectory_analysis: str,
        intervention_pattern: str,
    ) -> Dict[str, Any]:
        """
        Generate AI-powered summary using Mistral.

        Args:
            stats: Session statistics
            fidelity_trajectory: Fidelity data points
            interventions: Intervention records
            trajectory_analysis: Pre-computed trajectory pattern
            intervention_pattern: Pre-computed intervention pattern

        Returns:
            AI-generated summary
        """
        # Build concise prompt
        prompt = f"""Analyze this TELOS governance session and provide a brief summary.

Session Statistics:
- Total turns: {stats.get('total_turns', 0)}
- Average fidelity: {stats.get('average_fidelity', 0):.3f}
- Interventions: {stats.get('total_interventions', 0)}

Fidelity Trajectory: {trajectory_analysis}
Intervention Pattern: {intervention_pattern}

Provide a JSON response with:
1. "title": A concise 5-10 word title describing this session
2. "description": A 1-2 sentence description of what happened
3. "key_topics": An array of 2-4 key themes (strings)

Respond ONLY with valid JSON, no markdown or explanation."""

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self._mistral_client.generate(
                messages=messages,
                temperature=0.3,  # Lower temperature for consistent output
                max_tokens=300,
            )

            # Parse JSON response
            # Try to extract JSON from response
            response_text = response.strip()

            # Handle potential markdown code blocks
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(
                    line for line in lines
                    if not line.startswith('```')
                )

            result = json.loads(response_text)
            return {
                'title': result.get('title', 'TELOS Session'),
                'description': result.get('description', ''),
                'key_topics': result.get('key_topics', []),
            }

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")
            # Try to extract title from plain text
            return {
                'title': response[:50] if response else 'TELOS Session',
                'description': '',
                'key_topics': [],
            }
        except Exception as e:
            logger.error(f"AI summary generation error: {e}")
            raise

    def _generate_fallback_summary(
        self,
        stats: Dict[str, Any],
        trajectory_analysis: str,
        intervention_pattern: str,
    ) -> Dict[str, Any]:
        """
        Generate rule-based fallback summary without AI.

        Args:
            stats: Session statistics
            trajectory_analysis: Pre-computed trajectory pattern
            intervention_pattern: Pre-computed intervention pattern

        Returns:
            Fallback summary
        """
        total_turns = stats.get('total_turns', 0)
        avg_fidelity = stats.get('average_fidelity', 0)
        interventions = stats.get('total_interventions', 0)

        # Generate title based on trajectory
        trajectory_titles = {
            'stable': 'Well-Aligned Session',
            'improving': 'Progressive Alignment Session',
            'degrading': 'Drift Recovery Session',
            'volatile': 'Dynamic Exploration Session',
            'insufficient_data': 'Brief Session',
        }
        title = trajectory_titles.get(trajectory_analysis, 'TELOS Session')

        # Generate description
        if interventions == 0:
            desc = f"A {total_turns}-turn session with consistent alignment (avg fidelity: {avg_fidelity:.2f})."
        elif interventions <= 2:
            desc = f"A {total_turns}-turn session with minor drift corrections ({interventions} intervention{'s' if interventions > 1 else ''})."
        else:
            desc = f"A {total_turns}-turn session requiring active governance ({interventions} interventions)."

        # Generate topics based on patterns
        topics = []
        if trajectory_analysis in ('stable', 'improving'):
            topics.append('purpose alignment')
        if intervention_pattern in ('occasional', 'frequent'):
            topics.append('drift correction')
        if avg_fidelity >= 0.7:
            topics.append('high fidelity')
        elif avg_fidelity < 0.5:
            topics.append('alignment challenges')

        return {
            'title': title,
            'description': desc,
            'key_topics': topics if topics else ['governance session'],
            'fidelity_trajectory': trajectory_analysis,
            'intervention_pattern': intervention_pattern,
            'generated_by': 'fallback',
            'generated_at': utc_now().isoformat(),
        }

    def _get_cache_key(self, session_id: str, session_data: Dict[str, Any]) -> str:
        """
        Generate cache key based on session content.

        Args:
            session_id: Session identifier
            session_data: Session data

        Returns:
            Cache key string
        """
        # Hash key metrics to detect changes
        stats = session_data.get('stats', {})
        content = f"{session_id}:{stats.get('total_turns', 0)}:{stats.get('total_interventions', 0)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_cached_summary(
        self,
        session_id: str,
        session_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached summary if available and valid.

        Args:
            session_id: Session identifier
            session_data: Current session data

        Returns:
            Cached summary or None
        """
        cache_key = self._get_cache_key(session_id, session_data)
        cache_file = self.cache_dir / f"summary_{session_id}_{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cached summary: {e}")
            return None

    def _cache_summary(
        self,
        session_id: str,
        session_data: Dict[str, Any],
        summary: Dict[str, Any],
    ) -> None:
        """
        Cache summary for future use.

        Args:
            session_id: Session identifier
            session_data: Session data
            summary: Generated summary
        """
        cache_key = self._get_cache_key(session_id, session_data)
        cache_file = self.cache_dir / f"summary_{session_id}_{cache_key}.json"

        try:
            with open(cache_file, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.debug(f"Cached summary: {cache_file}")
        except Exception as e:
            logger.warning(f"Failed to cache summary: {e}")


# Convenience function
def summarize_session(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Quick function to generate a session summary.

    Args:
        session_data: Session data from collector.export_to_dict()

    Returns:
        Summary dictionary
    """
    summarizer = SessionSummarizer()
    return summarizer.summarize_session(session_data)

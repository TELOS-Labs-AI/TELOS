"""
Primacy Attractor Extractor
===========================

Extracts the Primacy Attractor (PA) from agent requests.

The key insight: Most agents already declare their purpose in the
system prompt. We can use this as the PA automatically - zero friction.

Example system prompt (becomes the PA):
    "You are a financial research assistant. Only provide information
     about publicly traded companies. Never give investment advice."

This becomes the constitutional constraint against which we measure
all subsequent messages and tool calls.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PrimacyAttractor:
    """
    Embedding-space representation of agent purpose.

    Extracted from system prompt or configured explicitly.
    """
    text: str
    embedding: np.ndarray
    source: str  # "system_prompt", "configured", "default"
    hash: str = field(default="")

    def __post_init__(self):
        """Compute hash for privacy-safe logging."""
        if not self.hash:
            self.hash = hashlib.sha256(self.text.encode()).hexdigest()[:16]


@dataclass
class ChatMessage:
    """Minimal chat message for PA extraction."""
    role: str
    content: Optional[str] = None


class PAExtractor:
    """
    Extracts Primacy Attractor from requests.

    Strategies:
    1. Use system prompt as PA (default, zero friction)
    2. Use configured PA per API key (enterprise)
    3. Use default PA if no system prompt (fallback)
    """

    DEFAULT_PA = (
        "You are a helpful AI assistant. Respond accurately and helpfully "
        "to user requests while avoiding harmful, unethical, or dangerous content."
    )

    def __init__(
        self,
        embed_fn: Callable[[str], np.ndarray],
        configured_pas: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize PA extractor.

        Args:
            embed_fn: Function to embed text strings
            configured_pas: Optional dict mapping API keys to PA texts
        """
        self.embed_fn = embed_fn
        self.configured_pas = configured_pas or {}

        # Cache for PA embeddings (avoid re-computing)
        self._pa_cache: Dict[str, PrimacyAttractor] = {}

        # Pre-compute default PA
        self._default_pa = PrimacyAttractor(
            text=self.DEFAULT_PA,
            embedding=self.embed_fn(self.DEFAULT_PA),
            source="default",
        )

    def extract_from_messages(
        self,
        messages: List[ChatMessage],
        api_key: Optional[str] = None,
    ) -> PrimacyAttractor:
        """
        Extract PA from a list of chat messages.

        Priority:
        1. Configured PA for API key (if exists)
        2. System prompt from messages
        3. Default PA (fallback)

        Args:
            messages: List of chat messages
            api_key: Optional API key for configured PA lookup

        Returns:
            PrimacyAttractor for governance
        """
        # Priority 1: Configured PA for API key
        if api_key and api_key in self.configured_pas:
            pa_text = self.configured_pas[api_key]
            return self._get_or_create_pa(pa_text, source="configured")

        # Priority 2: System prompt from messages
        system_prompt = self._extract_system_prompt(messages)
        if system_prompt:
            return self._get_or_create_pa(system_prompt, source="system_prompt")

        # Priority 3: Default PA
        logger.warning(
            "No system prompt found, using default PA. "
            "Consider adding a system prompt to define agent purpose."
        )
        return self._default_pa

    def extract_from_text(self, text: str, source: str = "configured") -> PrimacyAttractor:
        """
        Create a PA directly from text.

        Args:
            text: The purpose text
            source: Source label for the PA

        Returns:
            PrimacyAttractor for governance
        """
        return self._get_or_create_pa(text, source=source)

    def _extract_system_prompt(self, messages: List[ChatMessage]) -> Optional[str]:
        """Extract system prompt from messages."""
        for msg in messages:
            if msg.role == "system" and msg.content:
                return msg.content.strip()
        return None

    def _get_or_create_pa(self, text: str, source: str) -> PrimacyAttractor:
        """Get PA from cache or create new one."""
        # Use hash as cache key
        cache_key = hashlib.sha256(text.encode()).hexdigest()[:32]

        if cache_key not in self._pa_cache:
            logger.debug(f"Creating new PA from {source}: {text[:50]}...")
            embedding = self.embed_fn(text)
            self._pa_cache[cache_key] = PrimacyAttractor(
                text=text,
                embedding=embedding,
                source=source,
            )

        return self._pa_cache[cache_key]

    def clear_cache(self):
        """Clear PA cache."""
        self._pa_cache.clear()

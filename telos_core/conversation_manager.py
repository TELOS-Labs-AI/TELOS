"""
Conversation history management with governance context injection.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ConversationTurn:
    """Single turn in conversation."""
    role: str
    content: str
    timestamp: float


class ConversationManager:
    """
    Manages conversation history with governance context.

    Responsibilities:
    - Store conversation turns
    - Inject governance context into system prompts
    - Trim history to context budget
    """

    def __init__(self, max_history_turns: int = 20):
        """
        Args:
            max_history_turns: Maximum turns to keep in history
        """
        self.max_history_turns = max_history_turns
        self.conversation_history: List[ConversationTurn] = []

        # Governance context
        self.purpose: List[str] = []
        self.scope: List[str] = []
        self.boundaries: List[str] = []

    def set_governance_context(
        self,
        purpose: List[str],
        scope: List[str],
        boundaries: List[str]
    ) -> None:
        """Set governance perimeters."""
        self.purpose = purpose
        self.scope = scope
        self.boundaries = boundaries

    def add_user_message(self, content: str, timestamp: float) -> None:
        """Add user message to history."""
        self.conversation_history.append(
            ConversationTurn(role="user", content=content, timestamp=timestamp)
        )
        self._trim_history()

    def add_assistant_message(self, content: str, timestamp: float) -> None:
        """Add assistant message to history."""
        self.conversation_history.append(
            ConversationTurn(role="assistant", content=content, timestamp=timestamp)
        )
        self._trim_history()

    def remove_last_assistant_message(self) -> Optional[str]:
        """Remove and return last assistant message."""
        if self.conversation_history and self.conversation_history[-1].role == "assistant":
            removed = self.conversation_history.pop()
            return removed.content
        return None

    def get_messages_for_api(self) -> List[Dict[str, str]]:
        """
        Get conversation history formatted for LLM API.

        Includes governance context as system messages.
        """
        messages = []

        # Add governance system prompt
        if self.purpose or self.scope or self.boundaries:
            governance_prompt = self._build_governance_prompt()
            messages.append({
                "role": "system",
                "content": governance_prompt
            })

        # Add conversation history
        for turn in self.conversation_history:
            messages.append({
                "role": turn.role,
                "content": turn.content
            })

        return messages

    def _build_governance_prompt(self) -> str:
        """Build system prompt from governance context."""
        sections = []

        if self.purpose:
            sections.append(f"Purpose: {', '.join(self.purpose)}")

        if self.scope:
            sections.append(f"Scope: {', '.join(self.scope)}")

        if self.boundaries:
            sections.append(f"Boundaries: {', '.join(self.boundaries)}")

        return "\n".join(sections)

    def _trim_history(self) -> None:
        """Trim history to max_history_turns."""
        if len(self.conversation_history) > self.max_history_turns:
            # Keep most recent turns
            self.conversation_history = self.conversation_history[-self.max_history_turns:]

    def get_turn_count(self) -> int:
        """Return number of turns in history."""
        return len(self.conversation_history)

    def clear_history(self) -> None:
        """Clear all conversation history."""
        self.conversation_history = []

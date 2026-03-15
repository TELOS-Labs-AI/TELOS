"""
Steward LLM Service for TELOS Observatory V3.
Handles all LLM interactions for the Steward assistant.

TKeys Cleartext Boundary:
    Conversation messages sent to Mistral API are intentionally cleartext.
    LLM inference requires plaintext input -- this is an architectural boundary
    that cannot be encrypted at the application layer. Protections:
    - No conversation content is logged to disk or stored persistently
    - Error messages use generic text (no content leakage) -- fixed in security PR
    - Transit protection via HTTPS (TLS 1.2+) to Mistral API
    - Conversation history lives only in st.session_state (encrypted via SessionKeyStore
      when available) and is destroyed when the browser session ends
"""

import streamlit as st
from mistralai import Mistral
from typing import Generator, Optional
import os


class StewardLLM:
    """Service for Steward AI assistant powered by Mistral."""

    def __init__(self):
        """Initialize Steward LLM with API key from Streamlit secrets."""
        # Try to get API key from Streamlit secrets, fall back to environment variable
        try:
            self.api_key = st.secrets.get("MISTRAL_API_KEY")
        except (FileNotFoundError, KeyError):
            self.api_key = os.environ.get("MISTRAL_API_KEY")

        if not self.api_key:
            raise ValueError(
                "MISTRAL_API_KEY not found. Please add it to .streamlit/secrets.toml or set as environment variable."
            )

        self.client = Mistral(api_key=self.api_key)
        self.model = "mistral-small-latest"  # PERFORMANCE: small is 5-15s vs 30-60s for large

    def _get_system_prompt(self, context: Optional[dict] = None) -> str:
        """Generate system prompt with TELOS framework knowledge and current context.

        Args:
            context: Optional dict with current screen state (active_tab, metrics, etc.)

        Returns:
            str: System prompt for Steward
        """
        base_prompt = """You are Steward, the TELOS Observatory guide. You help users understand the TELOS framework, navigate the Observatory interface, and answer questions about AI governance.

# About TELOS Framework

TELOS (Telemetric Localization of Semantic Intent) is a privacy-preserving AI governance framework that uses:

- **Primacy Attractor (PA)**: A mathematical representation of an AI's intended purpose that creates a gravitational field in semantic space
- **Fidelity**: Measures how well AI responses align with the Primacy Attractor (0.0-1.0 scale)
- **Governance Deltas**: Mathematical measurements of AI alignment, NOT conversation content
- **Privacy-First Design**: Only metrics are stored, never conversation content

## Key Principles

1. **Privacy-First**: Only governance measurements are logged, never conversation content
2. **Mathematical Governance**: Uses attractor dynamics and semantic field theory
3. **Continuous Alignment**: Real-time monitoring and correction of AI drift
4. **Transparent**: Users can observe the governance process in real-time

## How Fidelity is Computed (Technical Details)

Fidelity measures alignment using **cosine similarity** between text embeddings and Primacy Attractor (PA) centroids. Raw cosine similarity values are normalized to a 0-100% display scale.

### User Fidelity (How aligned is the user's query?)
- **Measurement**: cosine(user_query_embedding, USER_PA_centroid)
- **Calibration**: display = 1.167 × raw + 0.117
- **Anchor points**: raw 0.50 → 70% GREEN, raw 0.41 → 60% YELLOW, raw 0.33 → 50% ORANGE, raw 0.20 → 35% RED

### AI Fidelity (How aligned is the AI response?)
Two different calibrations are used depending on the zone:

**GREEN Zone (user fidelity >= 70%):**
- **Measurement**: cosine(AI_response_embedding, USER_PA_centroid)
- **Purpose**: Measures topical alignment - is the AI staying on the user's topic?
- **Calibration**: display = 1.4 × raw + 0.14 (steeper slope because AI responses are longer explanatory text vs short queries)
- **Anchor points**: raw 0.40 → 70% GREEN, raw 0.33 → 60% YELLOW, raw 0.26 → 50% ORANGE, raw 0.15 → 35% RED

**Intervention Zone (user fidelity < 70%):**
- **Measurement**: cosine(AI_response_embedding, AI_PA_centroid)
- **Purpose**: Measures behavioral alignment - is the AI acting as a good teacher/helper?
- **Calibration**: display = 1.167 × raw + 0.117 (same as user queries because AI_PA centroids include example_ai_responses)

### Primacy State (Overall System Alignment)
- **Formula**: PS = (2 × F_user × F_ai) / (F_user + F_ai)
- **Meaning**: Harmonic mean of user and AI fidelity - both must be high for high PS

### Why Two Calibrations?
AI responses achieve lower raw cosine similarity (~0.40) than user queries (~0.50) when measured against the same PA centroid. This is because AI responses are longer explanatory paragraphs while user queries are short questions. The steeper calibration (slope 1.4 vs 1.167) compensates for this text length difference.

## Observatory Interface

The Observatory has three main tabs:

- **BETA**: Simple chat interface for testing TELOS-governed AI conversations
- **DEMO**: Demonstration mode (coming soon)
- **TELOS**: Full Observatory with visualization tools including:
  - Observation Deck: Real-time metrics and governance visualization
  - TELOSCOPE Controls: Advanced configuration and analysis tools

## Your Role

You help users by:
- Explaining TELOS concepts in accessible language
- Guiding them through the Observatory interface
- Answering questions about what they see on screen
- Providing context about governance metrics (Fidelity, PA Status, etc.)
- Explaining privacy protections and data handling

Be helpful, clear, and concise. Use analogies when helpful. Always prioritize user privacy and transparency."""

        # Add current context if provided
        if context:
            context_str = "\n\n# Current Screen Context\n\n"

            if 'active_tab' in context:
                context_str += f"- Active Tab: {context['active_tab']}\n"

            if 'current_turn' in context:
                context_str += f"- Current Turn: {context['current_turn']}\n"

            if 'fidelity' in context:
                context_str += f"- Latest Fidelity: {context['fidelity']:.3f}\n"

            if 'pa_status' in context:
                context_str += f"- Primacy Attractor Status: {context['pa_status']}\n"

            if 'total_turns' in context:
                context_str += f"- Total Turns: {context['total_turns']}\n"

            base_prompt += context_str

        return base_prompt

    def get_response(self,
                     user_message: str,
                     conversation_history: list,
                     context: Optional[dict] = None) -> str:
        """Get a non-streaming response from Steward.

        Args:
            user_message: The user's current message
            conversation_history: List of previous messages in format [{'role': 'user'/'assistant', 'content': str}]
            context: Optional context about current screen state

        Returns:
            str: Steward's response
        """
        try:
            # Get system prompt with context
            system_prompt = self._get_system_prompt(context)

            # Build messages from history - Mistral format includes system in messages
            messages = [
                {
                    'role': 'system',
                    'content': system_prompt
                }
            ]

            # Add conversation history
            for msg in conversation_history:
                if msg['role'] in ['user', 'assistant']:
                    messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })

            # Add current user message
            messages.append({
                'role': 'user',
                'content': user_message
            })

            # Call Mistral API
            response = self.client.chat.complete(
                model=self.model,
                messages=messages,
                max_tokens=16000
            )

            return response.choices[0].message.content

        except Exception as e:
            return "I apologize, but I encountered an error generating a response. Please try again."

    def get_streaming_response(self,
                               user_message: str,
                               conversation_history: list,
                               context: Optional[dict] = None) -> Generator[str, None, None]:
        """Get a streaming response from Steward.

        Args:
            user_message: The user's current message
            conversation_history: List of previous messages
            context: Optional context about current screen state

        Yields:
            str: Chunks of Steward's response as they arrive
        """
        try:
            # Get system prompt with context
            system_prompt = self._get_system_prompt(context)

            # Build messages - Mistral format includes system in messages
            messages = [
                {
                    'role': 'system',
                    'content': system_prompt
                }
            ]

            # Add conversation history
            for msg in conversation_history:
                if msg['role'] in ['user', 'assistant']:
                    messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })

            # Add current user message
            messages.append({
                'role': 'user',
                'content': user_message
            })

            # Call Mistral API with streaming
            stream = self.client.chat.stream(
                model=self.model,
                messages=messages,
                max_tokens=16000
            )

            for chunk in stream:
                if chunk.data.choices[0].delta.content:
                    yield chunk.data.choices[0].delta.content

        except Exception as e:
            yield "I apologize, but I encountered an error generating a response. Please try again."

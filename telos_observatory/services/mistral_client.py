"""
TELOS Mistral Client

Simple, working Mistral API client for TELOS.
Compatible with mistralai >= 1.0.0
"""

import os
import logging
import time
from typing import List, Dict, Any, Optional, Callable

from telos_core.exceptions import (
    MissingAPIKeyError,
    APIConnectionError,
    APIResponseError,
    validate_api_key
)

# SSE Replay Manager - optional integration for streaming capture
try:
    from telos_observatory.services.sse_replay_manager import get_sse_manager
    SSE_MANAGER_AVAILABLE = True
except ImportError:
    SSE_MANAGER_AVAILABLE = False

logger = logging.getLogger(__name__)


class MistralClient:
    """
    Mistral API client for TELOS.

    Simple wrapper around the Mistral API with error handling.

    Example:
        >>> client = MistralClient()
        >>> response = client.generate(
        ...     messages=[{"role": "user", "content": "Hello"}],
        ...     max_tokens=100
        ... )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "mistral-small-latest"  # Faster model (5-15s vs 30-60s for large)
    ):
        """
        Initialize Mistral client.

        Args:
            api_key: Mistral API key (or set MISTRAL_API_KEY env var)
            model: Model to use for generation (default: mistral-small-latest for speed)

        Raises:
            MissingAPIKeyError: If API key not found
        """
        # Get API key from parameter or environment
        api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self.api_key = validate_api_key(api_key, "MISTRAL")

        self.model = model

        # Initialize Mistral client with timeout
        try:
            from mistralai import Mistral
            import httpx
            # Set timeout: 120 seconds for connect, 300 seconds for read (long-form responses)
            self.client = Mistral(
                api_key=self.api_key,
                timeout_ms=300000  # 5 minute timeout for API calls
            )
            logger.info(f"Mistral client initialized with model: {model} (timeout: 300s)")
        except ImportError as e:
            raise APIConnectionError(
                "Mistral",
                "mistralai package not installed. Run: pip install mistralai"
            ) from e
        except Exception as e:
            raise APIConnectionError("Mistral", str(e)) from e

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        Generate response from Mistral API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate (default: 2000 for focused responses)
            **kwargs: Additional arguments to pass to API

        Returns:
            Generated text response

        Raises:
            APIResponseError: If API returns an error
            APIConnectionError: If connection fails
        """
        try:
            # Call Mistral API
            response = self.client.chat.complete(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            # Extract response text
            if hasattr(response, 'choices') and response.choices:
                content = response.choices[0].message.content
                return content if content else ""
            else:
                raise APIResponseError(
                    "Mistral",
                    message="No response content in API response"
                )

        except Exception as e:
            if "rate limit" in str(e).lower():
                from telos_core.exceptions import APIRateLimitError
                raise APIRateLimitError("Mistral") from e
            elif hasattr(e, 'status_code'):
                raise APIResponseError(
                    "Mistral",
                    status_code=e.status_code,
                    message=str(e)
                ) from e
            else:
                raise APIConnectionError("Mistral", str(e)) from e

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        Alternative interface for chat completion (alias for generate).

        Provided for compatibility with intervention systems that call
        chat_completion() instead of generate().

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional arguments to pass to API

        Returns:
            Generated text response
        """
        return self.generate(messages, temperature, max_tokens, **kwargs)

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        session_id: Optional[str] = None,
        turn_number: Optional[int] = None,
        record_sse: bool = False,
        on_token_callback: Optional[Callable[[str, int], None]] = None,
        **kwargs
    ):
        """
        Generate streaming response from Mistral API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            session_id: Optional session ID for SSE recording
            turn_number: Optional turn number for SSE recording
            record_sse: Whether to record SSE events for replay
            on_token_callback: Optional callback(token, token_index) for each token
            **kwargs: Additional arguments to pass to API

        Yields:
            Text chunks as they arrive from the API

        Raises:
            APIResponseError: If API returns an error
            APIConnectionError: If connection fails
        """
        # Initialize SSE recording if enabled
        sse_manager = None
        if record_sse and SSE_MANAGER_AVAILABLE and session_id and turn_number:
            try:
                sse_manager = get_sse_manager()
                sse_manager.start_recording(session_id, turn_number)
                logger.debug(f"SSE recording started: session={session_id}, turn={turn_number}")
            except Exception as e:
                logger.warning(f"SSE recording initialization failed: {e}")
                sse_manager = None

        token_index = 0
        try:
            # Call Mistral API with streaming
            stream = self.client.chat.stream(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            # Yield chunks as they arrive
            for chunk in stream:
                if hasattr(chunk, 'data') and hasattr(chunk.data, 'choices'):
                    if chunk.data.choices and len(chunk.data.choices) > 0:
                        delta = chunk.data.choices[0].delta
                        if hasattr(delta, 'content') and delta.content:
                            token = delta.content

                            # Record SSE token if enabled
                            if sse_manager:
                                try:
                                    sse_manager.record_token(token)
                                except Exception as e:
                                    logger.debug(f"SSE token recording failed: {e}")

                            # Call token callback if provided
                            if on_token_callback:
                                try:
                                    on_token_callback(token, token_index)
                                except Exception as e:
                                    logger.debug(f"Token callback failed: {e}")

                            token_index += 1
                            yield token

        except Exception as e:
            if "rate limit" in str(e).lower():
                from telos_core.exceptions import APIRateLimitError
                raise APIRateLimitError("Mistral") from e
            elif hasattr(e, 'status_code'):
                raise APIResponseError(
                    "Mistral",
                    status_code=e.status_code,
                    message=str(e)
                ) from e
            else:
                raise APIConnectionError("Mistral", str(e)) from e
        finally:
            # Stop SSE recording
            if sse_manager:
                try:
                    session = sse_manager.stop_recording()
                    if session:
                        logger.debug(
                            f"SSE recording stopped: {session.token_count} tokens "
                            f"in {session.total_duration_ms}ms"
                        )
                except Exception as e:
                    logger.warning(f"SSE recording finalization failed: {e}")

    def test_connection(self) -> bool:
        """
        Test connection to Mistral API.

        Returns:
            True if connection successful

        Raises:
            APIConnectionError: If connection fails
        """
        try:
            response = self.generate(
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
            logger.info("Mistral connection test successful")
            return True
        except Exception as e:
            logger.error(f"Mistral connection test failed: {e}")
            raise


# Alias for backward compatibility
TelosMistralClient = MistralClient


# Cached client for performance optimization
# This avoids creating new HTTP connections on every turn
def get_cached_mistral_client(model: str = "mistral-small-latest") -> MistralClient:
    """
    Get a cached MistralClient instance using Streamlit's cache.

    This avoids the overhead of creating new HTTP connections on every turn.
    The client is cached per model, so different models get different clients.

    Args:
        model: Model to use for generation

    Returns:
        Cached MistralClient instance
    """
    try:
        import streamlit as st

        # Use st.cache_resource for singleton pattern
        @st.cache_resource
        def _get_client(model_name: str) -> MistralClient:
            logger.info(f"Creating cached MistralClient for model: {model_name}")
            return MistralClient(model=model_name)

        return _get_client(model)
    except ImportError:
        # Fallback if streamlit not available
        logger.warning("Streamlit not available, creating new MistralClient")
        return MistralClient(model=model)

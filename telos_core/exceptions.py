"""
TELOS Exception Hierarchy

Comprehensive error handling framework with clear exception types,
recovery strategies, and user-friendly error messages.
"""

from typing import Optional, Dict, Any
from contextlib import contextmanager
import traceback
import logging
import sys

logger = logging.getLogger(__name__)


def setup_error_logging(level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """
    Set up logging for TELOS with proper formatting.

    Args:
        level: Logging level (default: INFO)
        log_file: Optional log file path

    """
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout),
            *([logging.FileHandler(log_file)] if log_file else [])
        ]
    )


# Base Exception
class TELOSError(Exception):
    """Base exception for all TELOS errors."""

    def __init__(
        self,
        message: str,
        recovery_suggestion: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        self.message = message
        self.recovery_suggestion = recovery_suggestion
        self.context = context or {}
        self.original_error = original_error

        super().__init__(self.format_message())

    def format_message(self) -> str:
        """Format error message with context and recovery suggestion."""
        parts = [f"TELOS Error: {self.message}"]

        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"Context: {context_str}")

        if self.recovery_suggestion:
            parts.append(f"Suggestion: {self.recovery_suggestion}")

        if self.original_error:
            parts.append(f"Original error: {str(self.original_error)}")

        return "\n".join(parts)


# Session Exceptions
class SessionError(TELOSError):
    """Base exception for session-related errors."""
    pass


class SessionNotStartedError(SessionError):
    """Raised when operation requires an active session but none exists."""

    def __init__(self, operation: str):
        super().__init__(
            message=f"Cannot {operation}: No active session",
            recovery_suggestion="Call start_session() before attempting this operation",
            context={"operation": operation}
        )


class SessionAlreadyActiveError(SessionError):
    """Raised when attempting to start a session while one is already active."""

    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session {session_id} is already active",
            recovery_suggestion="Call end_session() before starting a new session",
            context={"session_id": session_id}
        )


# Attractor Exceptions
class AttractorConstructionError(TELOSError):
    """Raised when primacy attractor cannot be constructed."""

    def __init__(self, reason: str, **context):
        super().__init__(
            message=f"Failed to construct primacy attractor: {reason}",
            recovery_suggestion="Check that purpose, scope, and boundaries are non-empty",
            context=context
        )


# Test and Validation Exceptions
class FileNotFoundError(TELOSError):
    """Raised when a required file is not found (TELOS-specific)."""

    def __init__(self, filepath: str, file_type: str = "file"):
        super().__init__(
            message=f"Required {file_type} not found: {filepath}",
            recovery_suggestion=f"Ensure {file_type} exists at specified path",
            context={"filepath": filepath, "file_type": file_type}
        )


class TestConversationError(TELOSError):
    """Raised when test conversation file has issues."""

    def __init__(self, filepath: str, reason: str):
        super().__init__(
            message=f"Test conversation error: {reason}",
            recovery_suggestion="Check test conversation file format",
            context={"filepath": filepath}
        )


class ValidationError(TELOSError):
    """Raised when validation fails."""

    def __init__(self, message: str, **context):
        super().__init__(
            message=f"Validation error: {message}",
            recovery_suggestion="Check validation configuration and inputs",
            context=context
        )


# Output Exceptions
class OutputDirectoryError(TELOSError):
    """Raised when output directory operations fail."""

    def __init__(self, directory: str, reason: str):
        super().__init__(
            message=f"Output directory error: {reason}",
            recovery_suggestion="Ensure directory exists and is writable",
            context={"directory": directory}
        )


class TelemetryExportError(TELOSError):
    """Raised when telemetry export fails."""

    def __init__(self, filepath: str, reason: str):
        super().__init__(
            message=f"Failed to export telemetry: {reason}",
            recovery_suggestion="Check file permissions and disk space",
            context={"filepath": filepath}
        )


# API Exceptions
class MissingAPIKeyError(TELOSError):
    """Raised when API key is missing."""

    def __init__(self, provider: str = "API"):
        super().__init__(
            message=f"{provider} key not found",
            recovery_suggestion=f"Set {provider}_API_KEY environment variable",
            context={"provider": provider}
        )


class APIConnectionError(TELOSError):
    """Raised when API connection fails."""

    def __init__(self, provider: str, reason: str):
        super().__init__(
            message=f"Failed to connect to {provider}: {reason}",
            recovery_suggestion="Check internet connection and API status",
            context={"provider": provider}
        )


class APIRateLimitError(TELOSError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, provider: str, retry_after: Optional[int] = None):
        super().__init__(
            message=f"{provider} rate limit exceeded",
            recovery_suggestion=f"Retry after {retry_after} seconds" if retry_after else "Wait before retrying",
            context={"provider": provider, "retry_after": retry_after}
        )


class APIResponseError(TELOSError):
    """Raised when API returns an error response."""

    def __init__(self, provider: str, status_code: Optional[int] = None, message: str = ""):
        super().__init__(
            message=f"{provider} error: {message}",
            recovery_suggestion="Check API credentials and request format",
            context={"provider": provider, "status_code": status_code}
        )


# Model Exceptions
class ModelLoadError(TELOSError):
    """Raised when a model fails to load."""

    def __init__(self, model_name: str, original_error: Optional[Exception] = None):
        super().__init__(
            message=f"Failed to load model: {model_name}",
            recovery_suggestion="Check model name, internet connection, and available disk space",
            context={"model_name": model_name},
            original_error=original_error
        )


# Helper Functions
def validate_api_key(key: Optional[str], provider: str = "API") -> str:
    """
    Validate API key is present and non-empty.

    Args:
        key: API key to validate
        provider: Name of the provider

    Returns:
        The validated API key

    Raises:
        MissingAPIKeyError: If key is None or empty
    """
    if not key or not key.strip():
        raise MissingAPIKeyError(provider)
    return key.strip()


def ensure_output_directory(directory: str) -> str:
    """
    Ensure output directory exists, create if needed.

    Args:
        directory: Path to directory

    Returns:
        The directory path

    Raises:
        OutputDirectoryError: If directory cannot be created
    """
    import os
    from pathlib import Path

    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
        return directory
    except Exception as e:
        raise OutputDirectoryError(
            directory,
            f"Failed to create directory: {str(e)}"
        ) from e


# Error Context Manager
@contextmanager
def error_context(operation: str, **context):
    """
    Context manager for wrapping operations with error handling.

    Usage:
        with error_context("processing turn", turn=5):
            # Your code here
            pass
    """
    try:
        yield
    except TELOSError:
        # Re-raise TELOS errors as-is
        raise
    except Exception as e:
        # Wrap other exceptions in TELOSError
        logger.error(
            f"Error during {operation}: {str(e)}",
            extra={"context": context}
        )
        raise TELOSError(
            message=f"Error during {operation}",
            recovery_suggestion="Check logs for details",
            context=context,
            original_error=e
        ) from e

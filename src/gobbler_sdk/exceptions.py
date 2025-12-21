"""Exceptions for Gobbler SDK.

This module defines custom exception classes used throughout the SDK
to provide clear error handling and debugging information.
"""


class GobbleError(Exception):
    """Base exception for all Gobbler SDK errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """Return a string representation of the error."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class ConnectionError(GobbleError):
    """Raised when unable to connect to the Gobbler daemon."""

    def __init__(
        self, message: str = "Unable to connect to Gobbler daemon", details: dict | None = None
    ) -> None:
        """Initialize the connection error.

        Args:
            message: Human-readable error message
            details: Optional dictionary with connection details
        """
        super().__init__(message, details)


class ConversionError(GobbleError):
    """Raised when content conversion fails."""

    def __init__(self, message: str, source: str | None = None, details: dict | None = None) -> None:
        """Initialize the conversion error.

        Args:
            message: Human-readable error message
            source: Source URL or file path that failed to convert
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if source:
            error_details["source"] = source
        super().__init__(message, error_details)
        self.source = source


class JobError(GobbleError):
    """Raised when a job operation fails."""

    def __init__(
        self, message: str, job_id: str | None = None, details: dict | None = None
    ) -> None:
        """Initialize the job error.

        Args:
            message: Human-readable error message
            job_id: Job ID that encountered the error
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if job_id:
            error_details["job_id"] = job_id
        super().__init__(message, error_details)
        self.job_id = job_id


class BatchError(GobbleError):
    """Raised when a batch operation fails."""

    def __init__(
        self, message: str, batch_id: str | None = None, details: dict | None = None
    ) -> None:
        """Initialize the batch error.

        Args:
            message: Human-readable error message
            batch_id: Batch ID that encountered the error
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if batch_id:
            error_details["batch_id"] = batch_id
        super().__init__(message, error_details)
        self.batch_id = batch_id


class ValidationError(GobbleError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None, details: dict | None = None) -> None:
        """Initialize the validation error.

        Args:
            message: Human-readable error message
            field: Field name that failed validation
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if field:
            error_details["field"] = field
        super().__init__(message, error_details)
        self.field = field


class TimeoutError(GobbleError):
    """Raised when an operation times out."""

    def __init__(
        self, message: str = "Operation timed out", timeout: float | None = None, details: dict | None = None
    ) -> None:
        """Initialize the timeout error.

        Args:
            message: Human-readable error message
            timeout: Timeout duration in seconds
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if timeout:
            error_details["timeout"] = timeout
        super().__init__(message, error_details)
        self.timeout = timeout


class AuthenticationError(GobbleError):
    """Raised when authentication fails."""

    def __init__(
        self, message: str = "Authentication failed", details: dict | None = None
    ) -> None:
        """Initialize the authentication error.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message, details)


class RateLimitError(GobbleError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
        details: dict | None = None,
    ) -> None:
        """Initialize the rate limit error.

        Args:
            message: Human-readable error message
            retry_after: Seconds to wait before retrying
            details: Optional dictionary with additional error context
        """
        error_details = details or {}
        if retry_after:
            error_details["retry_after"] = retry_after
        super().__init__(message, error_details)
        self.retry_after = retry_after

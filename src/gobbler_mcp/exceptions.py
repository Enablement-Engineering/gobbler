"""Custom exception hierarchy for Gobbler MCP server.

This module defines a hierarchy of custom exceptions used throughout the Gobbler
MCP server to provide more specific error handling and better error messages.
"""


class GobblerError(Exception):
    """Base exception for all Gobbler errors.

    All custom exceptions in the Gobbler MCP server should inherit from this class.
    This allows for catching all Gobbler-specific errors with a single except clause.
    """
    pass


class ServiceUnavailableError(GobblerError):
    """External service is unavailable.

    Raised when a required external service (e.g., Docker container, API endpoint,
    Redis server) is unavailable or not responding.

    Examples:
        - Crawl4AI Docker container is not running
        - Docling Docker container is not running
        - YouTube API is unreachable
        - Redis server is down
    """
    pass


class ConversionError(GobblerError):
    """Content conversion failed.

    Raised when content conversion from one format to another fails.

    Examples:
        - Failed to convert HTML to markdown
        - Failed to convert PDF to markdown
        - Failed to transcribe audio/video
        - Failed to extract YouTube transcript
    """
    pass


class ConfigurationError(GobblerError):
    """Configuration is invalid.

    Raised when configuration validation fails or required configuration
    is missing.

    Examples:
        - Invalid YAML configuration file
        - Missing required configuration parameter
        - Configuration value out of valid range
        - Incompatible configuration options
    """
    pass


class QueueError(GobblerError):
    """Queue operation failed.

    Raised when a queue operation (enqueue, dequeue, status check) fails.

    Examples:
        - Failed to enqueue job to Redis
        - Failed to retrieve job status
        - Job not found in queue
        - Queue is full or unavailable
    """
    pass


class ValidationError(GobblerError):
    """Input validation failed.

    Raised when input parameters fail validation checks.

    Examples:
        - Invalid URL format
        - File path doesn't exist
        - Parameter value out of range
        - Invalid file type
    """
    pass


class TimeoutError(GobblerError):
    """Operation timed out.

    Raised when an operation exceeds its configured timeout period.

    Examples:
        - HTTP request timed out
        - Transcription took too long
        - Browser script execution timed out
    """
    pass


class AuthenticationError(GobblerError):
    """Authentication failed.

    Raised when authentication or authorization fails.

    Examples:
        - Invalid API key
        - Expired session token
        - Insufficient permissions
    """
    pass

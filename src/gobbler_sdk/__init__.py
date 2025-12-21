"""Gobbler SDK - Python client for the Gobbler daemon.

This package provides a type-safe, namespace-based interface for interacting
with the Gobbler daemon for content conversion operations.

Example:
    Sync client:
    ```python
    from gobbler_sdk import GobbleClient

    with GobbleClient() as client:
        result = client.convert.youtube("https://youtube.com/watch?v=...")
        print(result.markdown)
    ```

    Async client:
    ```python
    from gobbler_sdk import AsyncGobbleClient

    async with AsyncGobbleClient() as client:
        result = await client.convert.youtube("https://youtube.com/watch?v=...")
        print(result.markdown)
    ```
"""

from gobbler_sdk.async_client import AsyncGobbleClient
from gobbler_sdk.client import GobbleClient
from gobbler_sdk.exceptions import (
    AuthenticationError,
    BatchError,
    ConnectionError,
    ConversionError,
    GobbleError,
    JobError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)
from gobbler_sdk.types import (
    BatchItemResult,
    BatchOptions,
    BatchResult,
    ConversionMetadata,
    ConversionResult,
    DocumentOptions,
    JobStatus,
    ServiceHealth,
    TranscriptionOptions,
    WebpageOptions,
)

__version__ = "0.1.0"

__all__ = [
    # Main clients
    "GobbleClient",
    "AsyncGobbleClient",
    # Types
    "ConversionResult",
    "ConversionMetadata",
    "JobStatus",
    "BatchResult",
    "BatchItemResult",
    "ServiceHealth",
    "TranscriptionOptions",
    "WebpageOptions",
    "DocumentOptions",
    "BatchOptions",
    # Exceptions
    "GobbleError",
    "ConnectionError",
    "ConversionError",
    "JobError",
    "BatchError",
    "ValidationError",
    "TimeoutError",
    "AuthenticationError",
    "RateLimitError",
]

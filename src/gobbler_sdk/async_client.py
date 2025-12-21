"""Asynchronous Gobbler SDK client.

This module provides the AsyncGobbleClient class for interacting with the
Gobbler daemon using an asynchronous interface.
"""

import asyncio
import os
from typing import Any

import httpx

from gobbler_sdk.exceptions import ConnectionError as GobbleConnectionError
from gobbler_sdk.namespaces.batch import AsyncBatchNamespace
from gobbler_sdk.namespaces.convert import AsyncConvertNamespace
from gobbler_sdk.namespaces.jobs import AsyncJobsNamespace
from gobbler_sdk.types import ServiceHealth


class AsyncGobbleClient:
    """Asynchronous client for interacting with the Gobbler daemon.

    This client provides a namespace-based interface for converting content,
    managing jobs, and processing batches using async/await syntax. It
    automatically discovers the daemon at localhost:4600 by default, but
    can be configured via environment variables or constructor parameters.

    Example:
        ```python
        from gobbler_sdk import AsyncGobbleClient

        async with AsyncGobbleClient() as client:
            result = await client.convert.youtube("https://youtube.com/watch?v=...")
            print(result.markdown)
        ```

    Attributes:
        convert: Namespace for content conversion operations
        batch: Namespace for batch processing operations
        jobs: Namespace for job management operations
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
    ) -> None:
        """Initialize the async Gobbler client.

        Args:
            base_url: Base URL of the Gobbler daemon API. Defaults to
                http://localhost:4600 or GOBBLER_API_URL environment variable.
            api_key: API key for authentication. Defaults to GOBBLER_API_KEY
                environment variable if set.
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
            retry_backoff: Exponential backoff factor for retries

        Raises:
            ConnectionError: If unable to connect to the daemon
        """
        self._base_url = (
            base_url or os.environ.get("GOBBLER_API_URL", "http://localhost:4600")
        ).rstrip("/")
        self._api_key = api_key or os.environ.get("GOBBLER_API_KEY")
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff

        # Build headers
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        # Create HTTP client with retry logic
        transport = httpx.AsyncHTTPTransport(retries=max_retries)
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
        )

        # Initialize namespaces
        self.convert = AsyncConvertNamespace(self._client, self._base_url)
        self.batch = AsyncBatchNamespace(self._client, self._base_url)
        self.jobs = AsyncJobsNamespace(self._client, self._base_url)

        self._connection_verified = False

    async def _verify_connection(self) -> None:
        """Verify that the daemon is reachable.

        Raises:
            ConnectionError: If unable to connect to the daemon
        """
        if self._connection_verified:
            return

        retry_count = 0
        last_error = None

        while retry_count < self._max_retries:
            try:
                response = await self._client.get("/health", timeout=5.0)
                response.raise_for_status()
                self._connection_verified = True
                return
            except Exception as e:
                last_error = e
                retry_count += 1
                if retry_count < self._max_retries:
                    await asyncio.sleep(self._retry_backoff * (2 ** (retry_count - 1)))

        raise GobbleConnectionError(
            f"Unable to connect to Gobbler daemon at {self._base_url}",
            details={
                "base_url": self._base_url,
                "retries": retry_count,
                "error": str(last_error),
            },
        ) from last_error

    async def health(self) -> ServiceHealth:
        """Get health status of the Gobbler daemon.

        Returns:
            ServiceHealth with daemon status information

        Raises:
            ConnectionError: If unable to connect to daemon
        """
        try:
            response = await self._client.get("/health")
            response.raise_for_status()
            data = response.json()

            return ServiceHealth(
                service_name=data.get("service_name", "gobbler"),
                status=data.get("status", "unknown"),
                available=data.get("available", False),
                version=data.get("version"),
                uptime_seconds=data.get("uptime_seconds"),
                last_check=data.get("last_check"),
                error=data.get("error"),
                details=data.get("details", {}),
            )
        except Exception as e:
            raise GobbleConnectionError(f"Failed to get health status: {e}") from e

    async def ping(self) -> bool:
        """Ping the daemon to check if it's responding.

        Returns:
            True if daemon is responding, False otherwise
        """
        try:
            response = await self._client.get("/health", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def get_capabilities(self) -> dict[str, Any]:
        """Get available capabilities from the daemon.

        Returns:
            Dictionary with available converters and features

        Raises:
            ConnectionError: If unable to connect to daemon
        """
        try:
            response = await self._client.get("/capabilities")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise GobbleConnectionError(f"Failed to get capabilities: {e}") from e

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncGobbleClient":
        """Async context manager entry."""
        await self._verify_connection()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

    def __repr__(self) -> str:
        """Return a string representation of the client."""
        return f"AsyncGobbleClient(base_url='{self._base_url}')"

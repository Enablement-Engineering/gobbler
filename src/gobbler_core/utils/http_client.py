"""HTTP client wrapper with retry logic for service communication."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RetryableHTTPClient:
    """HTTP client with automatic retry logic."""

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_statuses: tuple = (500, 502, 503, 504),
    ) -> None:
        """Initialize HTTP client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_statuses: HTTP status codes to retry on
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_statuses = retry_statuses
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "RetryableHTTPClient":
        """Enter async context manager."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(  # type: ignore[no-untyped-def]
        self, exc_type, exc_val, exc_tb
    ) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()

    async def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """POST request with retry logic.

        Args:
            url: URL to post to
            json: JSON data to send
            data: Form data to send
            files: Files to upload
            headers: HTTP headers to include

        Returns:
            HTTP response

        Raises:
            httpx.HTTPError: If request fails after retries
        """
        if not self._client:
            msg = "Client not initialized. Use as context manager."
            raise RuntimeError(msg)

        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await self._client.post(
                    url, json=json, data=data, files=files, headers=headers
                )

                # Check if we should retry on this status
                if response.status_code in self.retry_statuses:
                    if attempt < self.max_retries - 1:
                        logger.warning(
                            "Request failed with status %d, retrying (%d/%d)...",
                            response.status_code,
                            attempt + 1,
                            self.max_retries,
                        )
                        continue
                    response.raise_for_status()

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    logger.warning(
                        "Request failed: %s, retrying (%d/%d)...",
                        e,
                        attempt + 1,
                        self.max_retries,
                    )
                    continue
                raise

            except Exception:
                # Don't retry on other exceptions
                logger.exception("Request failed with unexpected error")
                raise

            else:
                return response

        # Should not reach here, but just in case
        if last_error:
            raise last_error
        msg = "Request failed after retries"
        raise RuntimeError(msg)

    async def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        """GET request with retry logic.

        Args:
            url: URL to get
            headers: HTTP headers to include

        Returns:
            HTTP response

        Raises:
            httpx.HTTPError: If request fails after retries
        """
        if not self._client:
            msg = "Client not initialized. Use as context manager."
            raise RuntimeError(msg)

        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await self._client.get(url, headers=headers)

                # Check if we should retry on this status
                if response.status_code in self.retry_statuses:
                    if attempt < self.max_retries - 1:
                        logger.warning(
                            "Request failed with status %d, retrying (%d/%d)...",
                            response.status_code,
                            attempt + 1,
                            self.max_retries,
                        )
                        continue
                    response.raise_for_status()

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    logger.warning(
                        "Request failed: %s, retrying (%d/%d)...",
                        e,
                        attempt + 1,
                        self.max_retries,
                    )
                    continue
                raise

            except Exception:
                # Don't retry on other exceptions
                logger.exception("Request failed with unexpected error")
                raise

            else:
                return response

        # Should not reach here, but just in case
        if last_error:
            raise last_error
        msg = "Request failed after retries"
        raise RuntimeError(msg)

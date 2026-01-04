"""Crawl4AI web page conversion provider.

This provider uses the Crawl4AI Docker service for web page scraping
and markdown conversion with JavaScript rendering support.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx

from gobbler_core.providers.registry import ProviderRegistry
from gobbler_core.providers.webpage.base import WebPageProvider, WebPageResult
from gobbler_core.utils.http_client import RetryableHTTPClient

logger = logging.getLogger(__name__)


class Crawl4AIProvider(WebPageProvider):
    """Web page conversion provider using Crawl4AI Docker service.

    Scrapes web pages and converts them to markdown using the Crawl4AI
    service running in Docker. Supports JavaScript rendering, content
    extraction, proxy configuration, and clean markdown output.

    Attributes:
        service_url: URL of the Crawl4AI service
        api_token: Authentication token for the service
        proxy_url: Optional proxy URL for browser requests

    Example:
        provider = Crawl4AIProvider(service_url="http://localhost:11235")
        result = await provider.fetch("https://example.com", timeout=60)
        print(result.markdown)

        # With proxy
        provider = Crawl4AIProvider(
            service_url="http://localhost:11235",
            proxy_url="http://user:pass@proxy.example.com:8080"
        )
    """

    def __init__(
        self,
        service_url: str = "http://localhost:11235",
        api_token: str = "gobbler-local-token",  # nosec B107 # noqa: S107 # nosec B107
        proxy_url: str | None = None,
    ) -> None:
        """Initialize the Crawl4AI provider.

        Args:
            service_url: URL of the Crawl4AI service
            api_token: Authentication token for the service
            proxy_url: Optional proxy URL for browser requests (e.g.,
                "http://user:pass@proxy.example.com:8080")
        """
        self.service_url = service_url.rstrip("/")
        self.api_token = api_token
        self.proxy_url = proxy_url

    @property
    def name(self) -> str:
        """Return provider name."""
        return "crawl4ai"

    def _safe_proxy_url(self, url: str) -> str:
        """Mask credentials in proxy URL for safe logging.

        Args:
            url: Proxy URL that may contain credentials

        Returns:
            URL with username and password replaced with '***'

        Example:
            >>> self._safe_proxy_url("http://user:pass@host:port")
            'http://***:***@host:port'
        """
        parsed = urlparse(url)
        if parsed.username or parsed.password:
            # Reconstruct with masked credentials
            host = parsed.hostname or ""
            netloc = f"***:***@{host}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunparse(parsed._replace(netloc=netloc))
        return url

    async def fetch(
        self,
        url: str,
        timeout: int = 30,
        **options: Any,
    ) -> WebPageResult:
        """Fetch and convert web page using Crawl4AI.

        Args:
            url: Web page URL to fetch
            timeout: Request timeout in seconds
            **options: Additional options:
                - include_images (bool): Include image markdown (default: True)
                - wait_for (str): CSS selector to wait for (optional)
                - headless (bool): Run browser in headless mode (default: True)

        Returns:
            WebPageResult with markdown content and metadata

        Raises:
            RuntimeError: If fetching or conversion fails
            TimeoutError: If request times out
        """
        include_images = options.get("include_images", True)
        wait_for = options.get("wait_for")
        headless = options.get("headless", True)

        # Build crawl request
        crawler_params: dict[str, Any] = {
            "stream": False,
            "cache_mode": "bypass",
        }
        if wait_for:
            crawler_params["wait_for"] = wait_for

        # Build browser config with optional proxy
        browser_params: dict[str, Any] = {"headless": headless}
        if self.proxy_url:
            browser_params["proxy"] = self.proxy_url
            logger.debug("Using proxy for Crawl4AI: %s", self._safe_proxy_url(self.proxy_url))

        crawl_request = {
            "urls": [url],
            "browser_config": {
                "type": "BrowserConfig",
                "params": browser_params,
            },
            "crawler_config": {
                "type": "CrawlerRunConfig",
                "params": crawler_params,
            },
        }
        headers = {"Authorization": f"Bearer {self.api_token}"}

        try:
            async with RetryableHTTPClient(timeout=float(timeout)) as client:
                # Start crawl task
                response = await client.post(
                    f"{self.service_url}/crawl",
                    json=crawl_request,
                    headers=headers,
                )
                response.raise_for_status()
                task_data = response.json()

                task_id = task_data.get("task_id")
                if not task_id:
                    msg = "No task_id returned from Crawl4AI"
                    raise RuntimeError(msg)

                # Poll for completion
                result = await self._poll_for_completion(client, task_id, headers, timeout)

                # Extract markdown
                markdown_content = self._extract_markdown(result)
                page_title = result.get("title") or result.get("metadata", {}).get(
                    "title", "Web Page"
                )

                # Remove images if requested
                if not include_images:
                    markdown_content = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", markdown_content)

                # Extract links if available
                links = result.get("links")

                return WebPageResult(
                    markdown=markdown_content,
                    title=page_title,
                    url=url,
                    metadata={
                        "service": "crawl4ai",
                    },
                    links=links,
                )

        except httpx.TimeoutException as e:
            msg = f"Request timed out after {timeout} seconds"
            raise TimeoutError(msg) from e
        except httpx.ConnectError as e:
            msg = (
                "Crawl4AI service unavailable. The service may not be running. "
                "Start with: docker-compose up -d crawl4ai"
            )
            raise RuntimeError(msg) from e
        except RuntimeError:
            raise
        except Exception as e:
            msg = f"Web page conversion failed: {e}"
            raise RuntimeError(msg) from e

    async def _poll_for_completion(
        self,
        client: RetryableHTTPClient,
        task_id: str,
        headers: dict[str, str],
        timeout: int,
    ) -> dict[str, Any]:
        """Poll Crawl4AI for task completion.

        Args:
            client: HTTP client
            task_id: Task ID to poll
            headers: HTTP headers
            timeout: Maximum wait time in seconds

        Returns:
            First result from completed task

        Raises:
            RuntimeError: If task fails or returns no results
            TimeoutError: If task doesn't complete in time
        """
        wait_interval = 1
        elapsed = 0

        while elapsed < timeout:
            await asyncio.sleep(wait_interval)
            elapsed += wait_interval

            response = await client.get(
                f"{self.service_url}/task/{task_id}",
                headers=headers,
            )
            response.raise_for_status()
            task_status = response.json()

            status = task_status.get("status")

            if status == "completed":
                results = task_status.get("results")
                if not results:
                    msg = "Crawl4AI returned no results"
                    raise RuntimeError(msg)
                return results[0]

            if status == "failed":
                error = task_status.get("error", "Unknown error")
                msg = f"Crawl4AI task failed: {error}"
                raise RuntimeError(msg)

        msg = f"Crawl task did not complete within {timeout} seconds"
        raise TimeoutError(msg)

    def _extract_markdown(self, result: dict[str, Any]) -> str:
        """Extract markdown content from Crawl4AI result.

        Args:
            result: Crawl4AI result dictionary

        Returns:
            Extracted markdown content

        Raises:
            RuntimeError: If no markdown content found
        """
        markdown_content = None

        if isinstance(result.get("markdown"), dict):
            # Prefer fit_markdown if available, fallback to raw_markdown
            markdown_content = result["markdown"].get("fit_markdown") or result["markdown"].get(
                "raw_markdown"
            )
        elif isinstance(result.get("markdown"), str):
            markdown_content = result["markdown"]

        if not markdown_content:
            msg = "No markdown content in Crawl4AI response"
            raise RuntimeError(msg)

        return markdown_content


# Register provider with the registry
ProviderRegistry.register("webpage", "crawl4ai", Crawl4AIProvider)

"""Web page conversion module with pluggable provider support.

This module provides web page conversion capabilities with support for
pluggable scraping providers. The default provider uses the Crawl4AI
Docker service.

Example:
    # Using default provider
    markdown, metadata = await convert_webpage_to_markdown("https://example.com")

    # Using a specific provider
    from gobbler_core.providers.webpage import Crawl4AIProvider
    provider = Crawl4AIProvider(service_url="http://localhost:11235")
    markdown, metadata = await convert_webpage_to_markdown("https://example.com", provider=provider)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import httpx

from gobbler_core.utils.frontmatter import count_words, create_webpage_frontmatter
from gobbler_core.utils.http_client import RetryableHTTPClient

if TYPE_CHECKING:
    from gobbler_core.providers.webpage import WebPageProvider

logger = logging.getLogger(__name__)


def _extract_markdown_content(result: dict[str, Any]) -> str:
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


async def _poll_for_task_completion(
    client: RetryableHTTPClient,
    service_url: str,
    task_id: str,
    headers: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    """Poll Crawl4AI for task completion.

    Args:
        client: HTTP client
        service_url: Crawl4AI service URL
        task_id: Task ID to poll
        headers: HTTP headers
        timeout: Maximum wait time in seconds

    Returns:
        First result from completed task

    Raises:
        RuntimeError: If task fails or returns no results
        httpx.TimeoutException: If task doesn't complete in time
    """
    wait_interval = 1  # seconds
    elapsed = 0

    while elapsed < timeout:
        await asyncio.sleep(wait_interval)
        elapsed += wait_interval

        status_response = await client.get(f"{service_url}/task/{task_id}", headers=headers)
        status_response.raise_for_status()
        task_status = status_response.json()

        if task_status.get("status") == "completed":
            results = task_status.get("results")
            if not results or len(results) == 0:
                msg = "Crawl4AI returned no results"
                raise RuntimeError(msg)
            return results[0]

        if task_status.get("status") == "failed":
            error = task_status.get("error", "Unknown error")
            msg = f"Crawl4AI task failed: {error}"
            raise RuntimeError(msg)

    msg = f"Crawl task did not complete within {timeout} seconds"
    raise httpx.TimeoutException(msg)


async def convert_webpage_to_markdown(
    url: str,
    include_images: bool = True,
    timeout: int = 30,
    service_url: str = "http://localhost:11235",
    api_token: str = "gobbler-local-token",  # noqa: S107
    metrics_callback: Callable[[str, int], None] | None = None,
    logger_instance: logging.Logger | None = None,
    provider: WebPageProvider | None = None,
) -> tuple[str, dict]:
    """Convert web page to markdown using a webpage provider.

    Uses a pluggable webpage provider for the actual scraping and conversion.
    If no provider is specified, uses the default Crawl4AI Docker service.

    Args:
        url: Web page URL
        include_images: Include image alt text
        timeout: Request timeout in seconds
        service_url: Crawl4AI service URL (default: "http://localhost:11235")
            Only used if provider is None
        api_token: API authentication token (default: "gobbler-local-token")
            Only used if provider is None
        metrics_callback: Optional callback for metrics tracking,
            called with (converter_type, size_bytes)
        logger_instance: Optional custom logger instance
        provider: Optional webpage provider. If None, uses default
            Crawl4AIProvider with the specified service_url and api_token.

    Returns:
        Tuple of (markdown_content, metadata)

    Raises:
        httpx.ConnectError: Service unavailable
        httpx.TimeoutException: Request timeout
        httpx.HTTPStatusError: HTTP error response
        RuntimeError: Other service errors

    Example:
        # Using default provider
        markdown, metadata = await convert_webpage_to_markdown("https://example.com")

        # Using a specific provider
        from gobbler_core.providers.webpage import Crawl4AIProvider
        provider = Crawl4AIProvider(service_url="http://localhost:11235")
        markdown, metadata = await convert_webpage_to_markdown("https://example.com", provider=provider)
    """
    log = logger_instance or logger
    provider_name = provider.name if provider else "crawl4ai"

    log.info(
        "Starting webpage conversion",
        extra={
            "extra_fields": {
                "url": url,
                "include_images": include_images,
                "timeout": timeout,
                "provider": provider_name,
            }
        },
    )
    start_time = time.time()

    # Use provider-based conversion if a provider is specified
    if provider is not None:
        result = await provider.fetch(url, timeout=timeout, include_images=include_images)
        markdown_content = result.markdown
        page_title = result.title
    else:
        # Legacy path: use direct Crawl4AI HTTP calls
        markdown_content, page_title = await _convert_with_crawl4ai(
            url=url,
            include_images=include_images,
            timeout=timeout,
            service_url=service_url,
            api_token=api_token,
            log=log,
        )

    conversion_time_ms = int((time.time() - start_time) * 1000)
    word_count = count_words(markdown_content)

    frontmatter = create_webpage_frontmatter(
        url=url,
        title=page_title,
        word_count=word_count,
        conversion_time_ms=conversion_time_ms,
    )
    full_markdown = frontmatter + markdown_content

    if metrics_callback:
        metrics_callback("webpage", len(full_markdown))

    metadata = {
        "url": url,
        "title": page_title,
        "word_count": word_count,
        "conversion_time_ms": conversion_time_ms,
        "provider": provider_name,
    }

    log.info(
        "Webpage conversion completed",
        extra={
            "extra_fields": {
                "url": url,
                "word_count": word_count,
                "title": page_title,
                "provider": provider_name,
            }
        },
    )
    return full_markdown, metadata


async def _convert_with_crawl4ai(
    url: str,
    include_images: bool,
    timeout: int,
    service_url: str,
    api_token: str,
    log: logging.Logger,
) -> tuple[str, str]:
    """Convert webpage using direct Crawl4AI HTTP calls (legacy path).

    Args:
        url: Web page URL
        include_images: Include image alt text
        timeout: Request timeout in seconds
        service_url: Crawl4AI service URL
        api_token: API authentication token
        log: Logger instance

    Returns:
        Tuple of (markdown_content, page_title)

    Raises:
        RuntimeError: If conversion fails
    """
    crawl_request = {
        "urls": [url],
        "browser_config": {"type": "BrowserConfig", "params": {"headless": True}},
        "crawler_config": {
            "type": "CrawlerRunConfig",
            "params": {"stream": False, "cache_mode": "bypass"},
        },
    }
    headers = {"Authorization": f"Bearer {api_token}"}

    try:
        async with RetryableHTTPClient(timeout=timeout) as client:
            response = await client.post(
                f"{service_url}/crawl", json=crawl_request, headers=headers
            )
            response.raise_for_status()
            task_data = response.json()

            task_id = task_data.get("task_id")
            if not task_id:
                msg = "No task_id returned from Crawl4AI"
                raise RuntimeError(msg)  # noqa: TRY301

            result = await _poll_for_task_completion(client, service_url, task_id, headers, timeout)
            markdown_content = _extract_markdown_content(result)
            page_title = result.get("title") or result.get("metadata", {}).get("title", "Web Page")

            if not include_images:
                markdown_content = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", markdown_content)

            return markdown_content, page_title

    except Exception:
        log.exception("Failed to convert web page %s", url)
        raise

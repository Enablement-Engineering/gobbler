"""Web page conversion module using Crawl4AI."""

import logging
import re
import time
from collections.abc import Callable

import httpx

from gobbler_core.utils.frontmatter import count_words, create_webpage_frontmatter
from gobbler_core.utils.http_client import RetryableHTTPClient

logger = logging.getLogger(__name__)


async def convert_webpage_to_markdown(
    url: str,
    include_images: bool = True,
    timeout: int = 30,
    service_url: str = "http://localhost:11235",
    api_token: str = "gobbler-local-token",
    metrics_callback: Callable[[str, int], None] | None = None,
    logger_instance: logging.Logger | None = None,
) -> tuple[str, dict]:
    """Convert web page to markdown using Crawl4AI service.

    Makes HTTP POST request to Crawl4AI Docker container to scrape and convert
    web page content to clean markdown format. Handles JavaScript rendering,
    content extraction, and formatting.

    Args:
        url: Web page URL
        include_images: Include image alt text
        timeout: Request timeout in seconds
        service_url: Crawl4AI service URL (default: "http://localhost:11235")
        api_token: API authentication token (default: "gobbler-local-token")
        metrics_callback: Optional callback for metrics tracking, called with (converter_type, size_bytes)
        logger_instance: Optional custom logger instance

    Returns:
        Tuple of (markdown_content, metadata)

    Raises:
        httpx.ConnectError: Service unavailable
        httpx.TimeoutException: Request timeout
        httpx.HTTPStatusError: HTTP error response
        RuntimeError: Other service errors
    """
    # Use custom logger if provided, otherwise use module logger
    log = logger_instance or logger

    log.info(
        "Starting webpage conversion",
        extra={"extra_fields": {"url": url, "include_images": include_images, "timeout": timeout}},
    )
    start_time = time.time()

    # Prepare Crawl4AI request
    crawl_request = {
        "urls": [url],
        "browser_config": {"type": "BrowserConfig", "params": {"headless": True}},
        "crawler_config": {
            "type": "CrawlerRunConfig",
            "params": {"stream": False, "cache_mode": "bypass"},
        },
    }

    # Prepare headers with auth token
    headers = {"Authorization": f"Bearer {api_token}"}

    try:
        async with RetryableHTTPClient(timeout=timeout) as client:
            # Submit crawl request
            response = await client.post(
                f"{service_url}/crawl", json=crawl_request, headers=headers
            )
            response.raise_for_status()
            task_data = response.json()

            # Get task ID
            task_id = task_data.get("task_id")
            if not task_id:
                raise RuntimeError("No task_id returned from Crawl4AI")

            # Poll for task completion
            max_wait = timeout
            wait_interval = 1  # seconds
            elapsed = 0

            while elapsed < max_wait:
                import asyncio

                await asyncio.sleep(wait_interval)
                elapsed += wait_interval

                # Check task status
                status_response = await client.get(f"{service_url}/task/{task_id}", headers=headers)
                status_response.raise_for_status()
                task_status = status_response.json()

                if task_status.get("status") == "completed":
                    # Task finished
                    results = task_status.get("results")
                    if not results or len(results) == 0:
                        raise RuntimeError("Crawl4AI returned no results")

                    result = results[0]
                    break
                if task_status.get("status") == "failed":
                    error = task_status.get("error", "Unknown error")
                    raise RuntimeError(f"Crawl4AI task failed: {error}")

            else:
                # Timeout waiting for task
                raise httpx.TimeoutException(
                    f"Crawl task did not complete within {timeout} seconds"
                )

            # Get markdown content - try different possible field structures
            markdown_content = None
            if isinstance(result.get("markdown"), dict):
                # Prefer fit_markdown if available, fallback to raw_markdown
                markdown_content = result["markdown"].get("fit_markdown") or result["markdown"].get(
                    "raw_markdown"
                )
            elif isinstance(result.get("markdown"), str):
                markdown_content = result["markdown"]

            if not markdown_content:
                raise RuntimeError("No markdown content in Crawl4AI response")

            # Extract metadata
            page_title = result.get("title") or result.get("metadata", {}).get("title", "Web Page")

            # Strip images if requested
            if not include_images:
                # Remove markdown image syntax: ![alt](url)
                markdown_content = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", markdown_content)

            conversion_time_ms = int((time.time() - start_time) * 1000)
            word_count = count_words(markdown_content)

            # Create frontmatter
            frontmatter = create_webpage_frontmatter(
                url=url,
                title=page_title,
                word_count=word_count,
                conversion_time_ms=conversion_time_ms,
            )

            # Combine frontmatter and markdown
            full_markdown = frontmatter + markdown_content

            # Track conversion size if callback provided
            if metrics_callback:
                metrics_callback("webpage", len(full_markdown))

            # Prepare metadata response
            metadata = {
                "url": url,
                "title": page_title,
                "word_count": word_count,
                "conversion_time_ms": conversion_time_ms,
            }

            log.info(
                "Webpage conversion completed",
                extra={"extra_fields": {"url": url, "word_count": word_count, "title": page_title}},
            )
            return full_markdown, metadata

    except Exception as e:
        log.error(f"Failed to convert web page {url}: {e}")
        raise

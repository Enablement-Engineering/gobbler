"""Web page conversion with CSS/XPath selector support using Crawl4AI."""

import logging
import re
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..config import get_config
from ..utils.frontmatter import count_words, create_webpage_frontmatter
from ..utils.health import get_service_unavailable_error
from ..utils.http_client import RetryableHTTPClient

logger = logging.getLogger(__name__)


async def convert_webpage_with_selector(
    url: str,
    css_selector: Optional[str] = None,
    xpath: Optional[str] = None,
    include_images: bool = True,
    extract_links: bool = False,
    session_id: Optional[str] = None,
    bypass_cache: bool = False,
    timeout: int = 30,
) -> Tuple[str, Dict]:
    """
    Convert web page to markdown with CSS/XPath selector extraction.

    Extends basic webpage conversion with targeted content extraction using
    CSS selectors or XPath expressions. Optionally extracts and categorizes
    links from the page. Supports session-based crawling for authenticated content.

    Args:
        url: Web page URL
        css_selector: CSS selector to extract specific content (e.g., "article.main")
        xpath: XPath expression to extract specific content (alternative to css_selector)
        include_images: Include image alt text
        extract_links: Extract and categorize links (internal/external)
        session_id: Session ID for authenticated crawling (loads cookies/localStorage)
        bypass_cache: Bypass Crawl4AI cache for fresh content
        timeout: Request timeout in seconds

    Returns:
        Tuple of (markdown_content, metadata)

    Raises:
        httpx.ConnectError: Service unavailable
        httpx.TimeoutException: Request timeout
        httpx.HTTPStatusError: HTTP error response
        RuntimeError: Other service errors
        ValueError: Invalid selector combination (both css_selector and xpath provided)
    """
    if css_selector and xpath:
        raise ValueError("Cannot specify both css_selector and xpath. Choose one.")

    config = get_config()
    service_url = config.get_service_url("crawl4ai")
    api_token = config.data.get("services", {}).get("crawl4ai", {}).get("api_token", "gobbler-local-token")

    logger.info(f"Converting web page with selector: {url}")
    start_time = time.time()

    # Prepare Crawl4AI request with selector
    crawl_request = {
        "urls": [url],
        "browser_config": {
            "type": "BrowserConfig",
            "params": {"headless": True}
        },
        "crawler_config": {
            "type": "CrawlerRunConfig",
            "params": {
                "stream": False,
                "cache_mode": "bypass" if bypass_cache else "enabled"
            }
        }
    }

    # Add extraction strategy if selector provided
    if css_selector or xpath:
        extraction_strategy = {
            "type": "CssExtractionStrategy" if css_selector else "XPathExtractionStrategy",
            "params": {
                "schema": {
                    "name": "Selected Content",
                    "baseSelector": css_selector if css_selector else xpath,
                    "fields": [
                        {
                            "name": "content",
                            "selector": css_selector if css_selector else xpath,
                            "type": "nested"
                        }
                    ]
                }
            }
        }
        crawl_request["crawler_config"]["params"]["extraction_strategy"] = extraction_strategy

    # Load session if provided
    session_cookies = None
    if session_id:
        from ..crawlers.session_manager import SessionManager
        session_manager = SessionManager()
        try:
            session_data = await session_manager.load_session(session_id)
            session_cookies = session_data.get("cookies", [])
            # TODO: Add localStorage support when Crawl4AI supports it
            logger.info(f"Loaded session {session_id} with {len(session_cookies)} cookies")
        except FileNotFoundError:
            logger.warning(f"Session {session_id} not found, proceeding without session")

    # Add cookies to browser config if available
    if session_cookies:
        crawl_request["browser_config"]["params"]["cookies"] = session_cookies

    # Prepare headers with auth token
    headers = {
        "Authorization": f"Bearer {api_token}"
    }

    try:
        async with RetryableHTTPClient(timeout=timeout) as client:
            # Submit crawl request
            response = await client.post(
                f"{service_url}/crawl",
                json=crawl_request,
                headers=headers
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
                status_response = await client.get(
                    f"{service_url}/task/{task_id}",
                    headers=headers
                )
                status_response.raise_for_status()
                task_status = status_response.json()

                if task_status.get("status") == "completed":
                    # Task finished
                    results = task_status.get("results")
                    if not results or len(results) == 0:
                        raise RuntimeError("Crawl4AI returned no results")

                    result = results[0]
                    break
                elif task_status.get("status") == "failed":
                    error = task_status.get("error", "Unknown error")
                    raise RuntimeError(f"Crawl4AI task failed: {error}")

            else:
                # Timeout waiting for task
                raise httpx.TimeoutException(f"Crawl task did not complete within {timeout} seconds")

            # Get markdown content - try different possible field structures
            markdown_content = None
            if isinstance(result.get("markdown"), dict):
                # Prefer fit_markdown if available, fallback to raw_markdown
                markdown_content = result["markdown"].get("fit_markdown") or result["markdown"].get("raw_markdown")
            elif isinstance(result.get("markdown"), str):
                markdown_content = result["markdown"]

            # If selector was used, check extracted_content field
            if (css_selector or xpath) and result.get("extracted_content"):
                # Use extracted content instead of full markdown
                extracted = result["extracted_content"]
                if isinstance(extracted, list) and len(extracted) > 0:
                    # Convert extracted structured data to markdown
                    markdown_content = _format_extracted_content(extracted)
                elif isinstance(extracted, str):
                    markdown_content = extracted

            if not markdown_content:
                raise RuntimeError("No markdown content in Crawl4AI response")

            # Extract metadata
            page_title = result.get("title") or result.get("metadata", {}).get("title", "Web Page")

            # Extract links if requested
            links_data = {}
            if extract_links:
                html_content = result.get("html", "")
                if html_content:
                    links_data = _extract_links(html_content, url)
                    logger.info(f"Extracted {len(links_data.get('all_links', []))} links from {url}")

            # Strip images if requested
            if not include_images:
                # Remove markdown image syntax: ![alt](url)
                markdown_content = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', markdown_content)

            conversion_time_ms = int((time.time() - start_time) * 1000)
            word_count = count_words(markdown_content)

            # Create base frontmatter
            frontmatter = create_webpage_frontmatter(
                url=url,
                title=page_title,
                word_count=word_count,
                conversion_time_ms=conversion_time_ms,
            )

            # Add selector info to frontmatter if present
            if css_selector or xpath or session_id:
                # Parse existing frontmatter to add fields
                lines = frontmatter.split('\n')
                frontmatter_lines = []
                for line in lines:
                    frontmatter_lines.append(line)
                    if line == '---' and len(frontmatter_lines) > 1:
                        # Insert before closing ---
                        insert_pos = len(frontmatter_lines) - 1
                        if css_selector:
                            frontmatter_lines.insert(insert_pos, f'css_selector: {css_selector}')
                            insert_pos += 1
                        if xpath:
                            frontmatter_lines.insert(insert_pos, f'xpath: {xpath}')
                            insert_pos += 1
                        if session_id:
                            frontmatter_lines.insert(insert_pos, f'session_id: {session_id}')
                        break
                frontmatter = '\n'.join(frontmatter_lines)

            # Combine frontmatter and markdown
            full_markdown = frontmatter + markdown_content

            # Prepare metadata response
            metadata = {
                "url": url,
                "title": page_title,
                "word_count": word_count,
                "conversion_time_ms": conversion_time_ms,
            }

            if css_selector:
                metadata["css_selector"] = css_selector
            if xpath:
                metadata["xpath"] = xpath
            if links_data:
                metadata["links"] = links_data
            if session_id:
                metadata["session_id"] = session_id

            logger.info(f"Successfully converted web page with selector: {url} ({word_count} words)")
            return full_markdown, metadata

    except Exception as e:
        logger.error(f"Failed to convert web page {url}: {e}")
        raise


def _format_extracted_content(extracted: List[Dict]) -> str:
    """Format extracted structured content as markdown."""
    markdown_parts = []

    for item in extracted:
        if isinstance(item, dict):
            content = item.get("content", "")
            if isinstance(content, str):
                markdown_parts.append(content)
            elif isinstance(content, list):
                # Nested content - recursively format
                markdown_parts.append(_format_extracted_content(content))
        elif isinstance(item, str):
            markdown_parts.append(item)

    return "\n\n".join(markdown_parts)


def _extract_links(html_content: str, base_url: str) -> Dict:
    """
    Extract and categorize links from HTML content.

    Args:
        html_content: Raw HTML content
        base_url: Base URL for resolving relative links

    Returns:
        Dictionary with link categorization:
        {
            "all_links": [...],
            "internal_links": [...],
            "external_links": [...],
            "total_count": int,
            "internal_count": int,
            "external_count": int
        }
    """
    soup = BeautifulSoup(html_content, "html.parser")
    base_domain = urlparse(base_url).netloc

    all_links = []
    internal_links = []
    external_links = []

    for link_tag in soup.find_all("a", href=True):
        href = link_tag["href"]

        # Resolve relative URLs
        absolute_url = urljoin(base_url, href)

        # Skip javascript:, mailto:, tel:, etc.
        if not absolute_url.startswith(("http://", "https://")):
            continue

        link_domain = urlparse(absolute_url).netloc
        link_text = link_tag.get_text(strip=True) or "(no text)"

        link_data = {
            "url": absolute_url,
            "text": link_text,
            "href": href  # Original href attribute
        }

        all_links.append(link_data)

        # Categorize as internal or external
        if link_domain == base_domain:
            internal_links.append(link_data)
        else:
            external_links.append(link_data)

    return {
        "all_links": all_links,
        "internal_links": internal_links,
        "external_links": external_links,
        "total_count": len(all_links),
        "internal_count": len(internal_links),
        "external_count": len(external_links),
    }

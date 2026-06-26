"""Web page conversion with CSS/XPath selector support using Crawl4AI."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from gobbler_core.config import get_config
from gobbler_core.utils.frontmatter import count_words, create_webpage_frontmatter
from gobbler_core.utils.http_client import RetryableHTTPClient
from gobbler_core.utils.redaction import neutralize_github_mentions

logger = logging.getLogger(__name__)


async def convert_webpage_with_selector(  # noqa: C901, PLR0912, PLR0915
    url: str,
    css_selector: str | None = None,
    xpath: str | None = None,
    include_images: bool = True,
    extract_links: bool = False,
    bypass_cache: bool = False,
    timeout: int = 30,
    use_stealth: bool = False,
    use_proxy: bool = True,
) -> tuple[str, dict]:
    """Convert web page to markdown with CSS/XPath selector extraction.

    Args:
        url: Web page URL.
        css_selector: CSS selector to extract specific content.
        xpath: XPath expression to extract specific content.
        include_images: Include image alt text.
        extract_links: Extract and categorize links.
        bypass_cache: Bypass Crawl4AI cache for fresh content.
        timeout: Request timeout in seconds.
        use_stealth: Enable stealth mode to evade bot detection.
        use_proxy: Use configured Crawl4AI proxy settings.

    Returns:
        Tuple of markdown content and metadata.

    Raises:
        ValueError: If both CSS and XPath selectors are provided.
        RuntimeError: If Crawl4AI returns an invalid or failed response.
        httpx.HTTPError: If the Crawl4AI request fails.
    """
    if css_selector and xpath:
        msg = "Cannot specify both css_selector and xpath. Choose one."
        raise ValueError(msg)

    config = get_config()
    service_url = config.get_service_url("crawl4ai")
    api_token = (
        config.data.get("services", {}).get("crawl4ai", {}).get("api_token", "gobbler-local-token")
    )

    from gobbler_core.providers.proxy import get_crawl4ai_proxy_url

    proxy_url = get_crawl4ai_proxy_url() if use_proxy else None

    logger.info("Converting web page with selector: %s", url)
    start_time = time.time()

    browser_params: dict[str, object] = {"headless": True}
    crawler_params: dict[str, object] = {
        "stream": False,
        "cache_mode": "bypass" if bypass_cache else "enabled",
    }

    if proxy_url:
        from gobbler_core.providers.webpage.crawl4ai import _parse_proxy_url

        crawler_params["proxy_config"] = _parse_proxy_url(proxy_url)
        logger.info("Using proxy for Crawl4AI")

    if use_stealth:
        browser_params.update(
            {
                "headless": False,
                "enable_stealth": True,
                "user_agent_mode": "random",
                "extra_args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            }
        )
        logger.info("Stealth mode enabled")

    crawl_request = {
        "urls": [url],
        "browser_config": {"type": "BrowserConfig", "params": browser_params},
        "crawler_config": {
            "type": "CrawlerRunConfig",
            "params": crawler_params,
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

            if "results" in task_data and task_data.get("success"):
                results = task_data.get("results", [])
                if not results:
                    msg = "Crawl4AI returned no results"
                    raise RuntimeError(msg)
                result = results[0]
            elif task_data.get("task_id"):
                result = await _poll_for_result(
                    client=client,
                    service_url=service_url,
                    task_id=task_data["task_id"],
                    headers=headers,
                    timeout=timeout,
                )
            else:
                msg = "Unexpected Crawl4AI response format"
                raise RuntimeError(msg)

            markdown_content = _get_markdown_content(result)

            if css_selector or xpath:
                html_content = result.get("html", "")
                if html_content:
                    extracted_md = _extract_selector_content(html_content, css_selector, xpath)
                    if extracted_md:
                        markdown_content = extracted_md
                        logger.info(
                            "Extracted content using %s",
                            "CSS selector" if css_selector else "XPath",
                        )
                    else:
                        logger.warning("Selector matched no content, using full page markdown")

            if not include_images:
                markdown_content = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", markdown_content)

            page_title = result.get("title") or result.get("metadata", {}).get("title", "Web Page")

            links_data: dict[str, Any] = {}
            if extract_links:
                html_content = result.get("html", "")
                if html_content:
                    links_data = _extract_links(html_content, url)

            conversion_time_ms = int((time.time() - start_time) * 1000)
            word_count = count_words(markdown_content)

            frontmatter = create_webpage_frontmatter(
                url=url,
                title=page_title,
                word_count=word_count,
                conversion_time_ms=conversion_time_ms,
            )
            frontmatter = _add_selector_frontmatter(
                frontmatter=frontmatter,
                css_selector=css_selector,
                xpath=xpath,
            )

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

            logger.info(
                "Successfully converted web page with selector: %s (%d words)",
                url,
                word_count,
            )
            return neutralize_github_mentions(frontmatter + markdown_content), metadata

    except Exception:
        logger.exception("Failed to convert web page %s", url)
        raise


async def _poll_for_result(
    client: RetryableHTTPClient,
    service_url: str,
    task_id: str,
    headers: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    """Poll Crawl4AI for a completed task result."""
    wait_interval = 1
    elapsed = 0

    while elapsed < timeout:
        await asyncio.sleep(wait_interval)
        elapsed += wait_interval

        status_response = await client.get(f"{service_url}/task/{task_id}", headers=headers)
        status_response.raise_for_status()
        task_status = status_response.json()

        if task_status.get("status") == "completed":
            results = task_status.get("results")
            if not results:
                msg = "Crawl4AI returned no results"
                raise RuntimeError(msg)
            return results[0]

        if task_status.get("status") == "failed":
            error = task_status.get("error", "Unknown error")
            msg = f"Crawl4AI task failed: {error}"
            raise RuntimeError(msg)

    msg = f"Crawl task did not complete within {timeout} seconds"
    raise httpx.TimeoutException(msg)


def _get_markdown_content(result: dict[str, Any]) -> str:
    """Extract markdown content from a Crawl4AI result."""
    markdown_content = None
    if isinstance(result.get("markdown"), dict):
        markdown_content = result["markdown"].get("fit_markdown") or result["markdown"].get(
            "raw_markdown"
        )
    elif isinstance(result.get("markdown"), str):
        markdown_content = result["markdown"]

    if not markdown_content:
        msg = "No markdown content in Crawl4AI response"
        raise RuntimeError(msg)

    return markdown_content


def _add_selector_frontmatter(
    frontmatter: str,
    css_selector: str | None,
    xpath: str | None,
) -> str:
    """Add selector metadata to an existing frontmatter block."""
    if not css_selector and not xpath:
        return frontmatter

    lines = frontmatter.split("\n")
    frontmatter_lines = []
    for line in lines:
        frontmatter_lines.append(line)
        if line == "---" and len(frontmatter_lines) > 1:
            insert_pos = len(frontmatter_lines) - 1
            if css_selector:
                frontmatter_lines.insert(insert_pos, f"css_selector: {css_selector}")
                insert_pos += 1
            if xpath:
                frontmatter_lines.insert(insert_pos, f"xpath: {xpath}")
            break
    return "\n".join(frontmatter_lines)


def _extract_selector_content(
    html_content: str, css_selector: str | None, xpath: str | None
) -> str | None:
    """Extract content using CSS selector or XPath and convert to markdown."""
    soup = BeautifulSoup(html_content, "html.parser")

    elements: list[Any] = []
    if css_selector:
        elements = list(soup.select(css_selector))
    elif xpath:
        try:
            from lxml import etree

            tree = etree.HTML(html_content)
            xpath_results = tree.xpath(xpath)
            for element in xpath_results:
                if hasattr(element, "text"):
                    html_str = etree.tostring(element, encoding="unicode", method="html")
                    elements.append(BeautifulSoup(html_str, "html.parser"))
                elif isinstance(element, str):
                    elements.append(element)
        except ImportError:
            logger.warning(
                "lxml not installed, XPath support unavailable. Install with: pip install lxml"
            )
            return None

    if not elements:
        return None

    markdown_parts = []
    for element in elements:
        if isinstance(element, str):
            markdown_parts.append(element.strip())
        else:
            text = _html_to_simple_markdown(element)
            if text.strip():
                markdown_parts.append(text.strip())

    return "\n\n".join(markdown_parts) if markdown_parts else None


def _html_to_simple_markdown(element: Any) -> str:  # noqa: C901, PLR0912
    """Convert a BeautifulSoup element to simple markdown."""
    for tag in element.find_all(["script", "style", "nav", "footer", "aside"]):
        tag.decompose()

    lines = []

    for child in element.descendants:
        if child.name == "h1":
            lines.append(f"\n# {child.get_text(strip=True)}\n")
        elif child.name == "h2":
            lines.append(f"\n## {child.get_text(strip=True)}\n")
        elif child.name == "h3":
            lines.append(f"\n### {child.get_text(strip=True)}\n")
        elif child.name == "h4":
            lines.append(f"\n#### {child.get_text(strip=True)}\n")
        elif child.name == "h5":
            lines.append(f"\n##### {child.get_text(strip=True)}\n")
        elif child.name == "h6":
            lines.append(f"\n###### {child.get_text(strip=True)}\n")
        elif child.name == "p":
            text = child.get_text(strip=True)
            if text:
                lines.append(f"\n{text}\n")
        elif child.name == "li":
            text = child.get_text(strip=True)
            if text:
                lines.append(f"- {text}")
        elif child.name == "blockquote":
            text = child.get_text(strip=True)
            if text:
                quoted = "\n".join(f"> {line}" for line in text.split("\n"))
                lines.append(f"\n{quoted}\n")
        elif child.name in {"pre", "code"}:
            text = child.get_text()
            if text.strip():
                lines.append(f"\n```\n{text}\n```\n")

    if not lines:
        return element.get_text(separator="\n", strip=True)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines))


def _extract_links(html_content: str, base_url: str) -> dict[str, Any]:
    """Extract and categorize links from HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")
    base_domain = urlparse(base_url).netloc

    all_links = []
    internal_links = []
    external_links = []

    for link_tag in soup.find_all("a", href=True):
        href = link_tag["href"]
        absolute_url = urljoin(base_url, href)

        if not absolute_url.startswith(("http://", "https://")):
            continue

        link_domain = urlparse(absolute_url).netloc
        link_text = link_tag.get_text(strip=True) or "(no text)"

        link_data = {
            "url": absolute_url,
            "text": link_text,
            "href": href,
        }

        all_links.append(link_data)
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

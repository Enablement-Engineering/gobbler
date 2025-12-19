#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0", "beautifulsoup4>=4.12.0"]
# ///
"""
Fetch web page with CSS/XPath selector extraction.

Usage:
    uv run fetch_with_selector.py <url> --selector CSS_SELECTOR
    uv run fetch_with_selector.py <url> --xpath XPATH_EXPRESSION

Examples:
    uv run fetch_with_selector.py "https://example.com" --selector "article.content"
    uv run fetch_with_selector.py "https://example.com" --xpath "//div[@class='main']"
    uv run fetch_with_selector.py "https://example.com" --selector ".content" --extract-links
"""

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

CRAWL4AI_URL = "http://localhost:11235"
API_TOKEN = "gobbler-local-token"


def extract_links(html: str, base_url: str) -> dict:
    """Extract and categorize links from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(base_url).netloc

    all_links = []
    internal_links = []
    external_links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        full_url = urljoin(base_url, href)
        link_domain = urlparse(full_url).netloc

        link_info = {"url": full_url, "text": text}
        all_links.append(link_info)

        if link_domain == base_domain:
            internal_links.append(link_info)
        else:
            external_links.append(link_info)

    return {
        "all_links": all_links,
        "internal_links": internal_links,
        "external_links": external_links,
        "all_count": len(all_links),
        "internal_count": len(internal_links),
        "external_count": len(external_links),
    }


async def fetch_with_selector(
    url: str,
    css_selector: str = None,
    xpath: str = None,
    include_images: bool = True,
    do_extract_links: bool = False,
    timeout: int = 30,
) -> tuple[str, dict]:
    """Fetch web page with selector extraction."""
    start_time = time.time()

    headers = {"Authorization": f"Bearer {API_TOKEN}"}

    # Build extraction strategy
    extraction_strategy = None
    if css_selector:
        extraction_strategy = {
            "type": "CssExtractionStrategy",
            "params": {"selector": css_selector}
        }
    elif xpath:
        extraction_strategy = {
            "type": "XPathExtractionStrategy",
            "params": {"xpath": xpath}
        }

    crawl_request = {
        "urls": [url],
        "browser_config": {
            "type": "BrowserConfig",
            "params": {"headless": True}
        },
        "crawler_config": {
            "type": "CrawlerRunConfig",
            "params": {"stream": False, "cache_mode": "bypass"}
        }
    }

    if extraction_strategy:
        crawl_request["crawler_config"]["params"]["extraction_strategy"] = extraction_strategy

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{CRAWL4AI_URL}/crawl",
            json=crawl_request,
            headers=headers
        )
        response.raise_for_status()
        task_data = response.json()

        task_id = task_data.get("task_id")
        if not task_id:
            raise RuntimeError("No task_id returned from Crawl4AI")

        while True:
            await asyncio.sleep(1)
            status_response = await client.get(
                f"{CRAWL4AI_URL}/task/{task_id}",
                headers=headers
            )
            status_response.raise_for_status()
            task_status = status_response.json()

            if task_status.get("status") == "completed":
                results = task_status.get("results")
                if not results:
                    raise RuntimeError("Crawl4AI returned no results")
                result = results[0]
                break
            elif task_status.get("status") == "failed":
                error = task_status.get("error", "Unknown error")
                raise RuntimeError(f"Crawl4AI task failed: {error}")

        # Extract markdown
        markdown_content = None
        if isinstance(result.get("markdown"), dict):
            markdown_content = result["markdown"].get("fit_markdown") or result["markdown"].get("raw_markdown")
        elif isinstance(result.get("markdown"), str):
            markdown_content = result["markdown"]

        if not markdown_content:
            raise RuntimeError("No markdown content in response")

        page_title = result.get("title") or "Web Page"

        if not include_images:
            markdown_content = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', markdown_content)

        conversion_time_ms = int((time.time() - start_time) * 1000)
        word_count = len(markdown_content.split())

        # Extract links if requested
        links_info = {}
        if do_extract_links:
            html = result.get("html", "")
            links_info = extract_links(html, url)

        # Build frontmatter
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        frontmatter_lines = [
            "---",
            f'source: "{url}"',
            "type: webpage",
            f'title: "{page_title}"',
            f"word_count: {word_count}",
            f"conversion_time_ms: {conversion_time_ms}",
            f"converted_at: {timestamp}",
        ]

        if css_selector:
            frontmatter_lines.append(f'css_selector: "{css_selector}"')
        if xpath:
            frontmatter_lines.append(f'xpath: "{xpath}"')
        if links_info:
            frontmatter_lines.append(f"links_count: {links_info['all_count']}")
            frontmatter_lines.append(f"internal_links_count: {links_info['internal_count']}")
            frontmatter_lines.append(f"external_links_count: {links_info['external_count']}")

        frontmatter_lines.extend(["---", ""])
        frontmatter = "\n".join(frontmatter_lines)

        return frontmatter + markdown_content, links_info


def main():
    parser = argparse.ArgumentParser(description="Fetch web page with selector")
    parser.add_argument("url", help="Web page URL")
    parser.add_argument("--selector", "-s", help="CSS selector")
    parser.add_argument("--xpath", "-x", help="XPath expression")
    parser.add_argument("--no-images", action="store_true", help="Exclude images")
    parser.add_argument("--extract-links", action="store_true", help="Extract links")
    parser.add_argument("--timeout", "-t", type=int, default=30, help="Timeout")
    parser.add_argument("--output", "-o", help="Output file path")
    args = parser.parse_args()

    if not args.selector and not args.xpath:
        print("Error: Provide --selector or --xpath", file=sys.stderr)
        sys.exit(1)

    try:
        markdown, links_info = asyncio.run(fetch_with_selector(
            args.url,
            css_selector=args.selector,
            xpath=args.xpath,
            include_images=not args.no_images,
            do_extract_links=args.extract_links,
            timeout=args.timeout,
        ))

        if args.output:
            Path(args.output).write_text(markdown)
            print(f"Saved to {args.output}", file=sys.stderr)
        else:
            print(markdown)

        if links_info:
            print("\n--- Links ---", file=sys.stderr)
            print(json.dumps(links_info, indent=2), file=sys.stderr)

    except httpx.ConnectError:
        print("Error: Cannot connect to Crawl4AI", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

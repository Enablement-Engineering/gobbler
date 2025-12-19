#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0", "beautifulsoup4>=4.12.0"]
# ///
"""
Crawl website and convert pages to markdown.

Usage:
    uv run crawl.py <start_url> [--max-depth N] [--max-pages N] [--output-dir DIR]

Examples:
    uv run crawl.py "https://docs.example.com"
    uv run crawl.py "https://docs.example.com" --max-depth 3 --max-pages 100
    uv run crawl.py "https://example.com" --include "/docs/" --exclude "/api/"
    uv run crawl.py "https://docs.example.com" --output-dir ./crawled
"""

import argparse
import asyncio
import json
import re
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

CRAWL4AI_URL = "http://localhost:11235"
API_TOKEN = "gobbler-local-token"


def sanitize_filename(url: str) -> str:
    """Convert URL to safe filename."""
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_") or "index"
    return re.sub(r'[<>:"/\\|?*]', '_', path)[:100] + ".md"


async def fetch_page(client: httpx.AsyncClient, url: str) -> tuple[str, str, list[str]]:
    """Fetch single page and extract markdown + links."""
    headers = {"Authorization": f"Bearer {API_TOKEN}"}

    crawl_request = {
        "urls": [url],
        "browser_config": {"type": "BrowserConfig", "params": {"headless": True}},
        "crawler_config": {"type": "CrawlerRunConfig", "params": {"stream": False, "cache_mode": "bypass"}}
    }

    response = await client.post(f"{CRAWL4AI_URL}/crawl", json=crawl_request, headers=headers)
    response.raise_for_status()
    task_id = response.json().get("task_id")

    while True:
        await asyncio.sleep(1)
        status_response = await client.get(f"{CRAWL4AI_URL}/task/{task_id}", headers=headers)
        task_status = status_response.json()

        if task_status.get("status") == "completed":
            result = task_status.get("results", [{}])[0]
            break
        elif task_status.get("status") == "failed":
            raise RuntimeError(f"Crawl failed: {task_status.get('error')}")

    # Get markdown
    markdown = ""
    if isinstance(result.get("markdown"), dict):
        markdown = result["markdown"].get("fit_markdown") or result["markdown"].get("raw_markdown", "")
    elif isinstance(result.get("markdown"), str):
        markdown = result["markdown"]

    title = result.get("title", "Page")

    # Extract links from HTML
    links = []
    html = result.get("html", "")
    if html:
        soup = BeautifulSoup(html, "html.parser")
        base_domain = urlparse(url).netloc
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            if urlparse(href).netloc == base_domain:
                links.append(href.split("#")[0].split("?")[0])

    return markdown, title, list(set(links))


async def crawl_site(
    start_url: str,
    max_depth: int = 2,
    max_pages: int = 50,
    include_pattern: str = None,
    exclude_pattern: str = None,
    output_dir: str = None,
    crawl_delay: float = 1.0,
) -> dict:
    """Crawl website starting from URL."""
    start_time = time.time()

    visited = set()
    queue = deque([(start_url, 0)])  # (url, depth)
    results = []
    link_graph = {}

    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    include_re = re.compile(include_pattern) if include_pattern else None
    exclude_re = re.compile(exclude_pattern) if exclude_pattern else None

    async with httpx.AsyncClient(timeout=60) as client:
        while queue and len(visited) < max_pages:
            url, depth = queue.popleft()

            if url in visited:
                continue
            if depth > max_depth:
                continue
            if include_re and not include_re.search(url):
                continue
            if exclude_re and exclude_re.search(url):
                continue

            visited.add(url)
            print(f"Crawling ({len(visited)}/{max_pages}): {url}", file=sys.stderr)

            try:
                markdown, title, links = await fetch_page(client, url)
                link_graph[url] = links

                # Add frontmatter
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                frontmatter = f"""---
source: "{url}"
type: webpage
title: "{title}"
word_count: {len(markdown.split())}
crawl_depth: {depth}
converted_at: {timestamp}
---

"""
                full_markdown = frontmatter + markdown

                results.append({
                    "url": url,
                    "title": title,
                    "depth": depth,
                    "word_count": len(markdown.split()),
                    "links_found": len(links),
                })

                if output_dir:
                    filename = sanitize_filename(url)
                    (Path(output_dir) / filename).write_text(full_markdown)

                # Add new links to queue
                for link in links:
                    if link not in visited:
                        queue.append((link, depth + 1))

                await asyncio.sleep(crawl_delay)

            except Exception as e:
                print(f"  Error: {e}", file=sys.stderr)
                results.append({"url": url, "error": str(e)})

    elapsed = time.time() - start_time

    return {
        "start_url": start_url,
        "pages_crawled": len(visited),
        "elapsed_seconds": round(elapsed, 2),
        "results": results,
        "link_graph": link_graph,
    }


def main():
    parser = argparse.ArgumentParser(description="Crawl website")
    parser.add_argument("url", help="Starting URL")
    parser.add_argument("--max-depth", type=int, default=2, help="Max crawl depth")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages to crawl")
    parser.add_argument("--include", help="URL include pattern (regex)")
    parser.add_argument("--exclude", help="URL exclude pattern (regex)")
    parser.add_argument("--output-dir", "-o", help="Save pages to directory")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests")
    args = parser.parse_args()

    try:
        summary = asyncio.run(crawl_site(
            args.url,
            max_depth=args.max_depth,
            max_pages=args.max_pages,
            include_pattern=args.include,
            exclude_pattern=args.exclude,
            output_dir=args.output_dir,
            crawl_delay=args.delay,
        ))

        print("\n--- Crawl Summary ---")
        print(json.dumps(summary, indent=2))

    except httpx.ConnectError:
        print("Error: Cannot connect to Crawl4AI", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0"]
# ///
"""
Fetch web page and convert to markdown using Crawl4AI.

Usage:
    uv run fetch.py <url> [--no-images] [--timeout SECS] [--output FILE]

Examples:
    uv run fetch.py "https://example.com"
    uv run fetch.py "https://docs.python.org" --output docs.md
    uv run fetch.py "https://example.com" --no-images --timeout 60
"""

import argparse
import asyncio
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

CRAWL4AI_URL = "http://localhost:11235"
API_TOKEN = "gobbler-local-token"


def create_frontmatter(url: str, title: str, word_count: int, conversion_time_ms: int) -> str:
    """Create YAML frontmatter for webpage."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "---",
        f'source: "{url}"',
        "type: webpage",
        f'title: "{title}"',
        f"word_count: {word_count}",
        f"conversion_time_ms: {conversion_time_ms}",
        f"converted_at: {timestamp}",
        "---",
        "",
    ]
    return "\n".join(lines)


async def fetch_webpage(
    url: str,
    include_images: bool = True,
    timeout: int = 30,
) -> str:
    """Fetch web page and convert to markdown."""
    start_time = time.time()

    headers = {"Authorization": f"Bearer {API_TOKEN}"}

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

    async with httpx.AsyncClient(timeout=timeout) as client:
        # Submit crawl request
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

        # Poll for completion
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

        # Get title
        page_title = result.get("title") or result.get("metadata", {}).get("title", "Web Page")

        # Strip images if requested
        if not include_images:
            markdown_content = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', markdown_content)

        conversion_time_ms = int((time.time() - start_time) * 1000)
        word_count = len(markdown_content.split())

        # Create frontmatter
        frontmatter = create_frontmatter(url, page_title, word_count, conversion_time_ms)

        return frontmatter + markdown_content


def main():
    parser = argparse.ArgumentParser(description="Fetch web page as markdown")
    parser.add_argument("url", help="Web page URL")
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Exclude images from output"
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=30,
        help="Timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    args = parser.parse_args()

    try:
        markdown = asyncio.run(fetch_webpage(
            args.url,
            include_images=not args.no_images,
            timeout=args.timeout,
        ))

        if args.output:
            Path(args.output).write_text(markdown)
            print(f"Saved to {args.output}", file=sys.stderr)
        else:
            print(markdown)

    except httpx.ConnectError:
        print("Error: Cannot connect to Crawl4AI. Is it running on port 11235?", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Site crawler for recursive web crawling with link graph generation."""

import asyncio
import logging
import re
import time
from collections import deque
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from ..converters.webpage_selector import convert_webpage_with_selector

logger = logging.getLogger(__name__)


class SiteCrawler:
    """Recursive site crawler with BFS traversal and link graph generation."""

    def __init__(self):
        """Initialize site crawler."""
        self.visited_urls: Set[str] = set()
        self.link_graph: Dict[str, List[str]] = {}

    async def crawl_site(
        self,
        start_url: str,
        max_depth: int = 2,
        max_pages: int = 50,
        url_include_pattern: Optional[str] = None,
        url_exclude_pattern: Optional[str] = None,
        css_selector: Optional[str] = None,
        respect_robots_txt: bool = True,
        crawl_delay: float = 1.0,
        concurrency: int = 3,
        session_id: Optional[str] = None,
        use_stealth: bool = False,
    ) -> Tuple[List[Dict], Dict]:
        """
        Crawl site recursively and return pages + link graph.

        Args:
            start_url: URL to start crawling from
            max_depth: Maximum crawl depth (default: 2, max: 5)
            max_pages: Maximum pages to crawl (default: 50, max: 500)
            url_include_pattern: Regex pattern - only crawl URLs matching this
            url_exclude_pattern: Regex pattern - skip URLs matching this
            css_selector: Apply selector to all crawled pages
            respect_robots_txt: Respect robots.txt (default: True)
            crawl_delay: Delay between requests in seconds (default: 1.0)
            concurrency: Max concurrent requests (default: 3, max: 10)
            session_id: Session ID for authenticated crawling
            use_stealth: Enable stealth mode to evade bot detection (default: False)

        Returns:
            Tuple of (pages_list, crawl_summary)
            - pages_list: List of dicts with {url, markdown, metadata, depth}
            - crawl_summary: Dict with {total_pages, link_graph, domains, duration_ms}
        """
        # Validate parameters
        if max_depth > 5:
            max_depth = 5
        if max_pages > 500:
            max_pages = 500
        if concurrency > 10:
            concurrency = 10

        start_time = time.time()
        base_domain = urlparse(start_url).netloc

        # Compile regex patterns
        include_regex = re.compile(url_include_pattern) if url_include_pattern else None
        exclude_regex = re.compile(url_exclude_pattern) if url_exclude_pattern else None

        # Check robots.txt
        robots_parser = None
        if respect_robots_txt:
            robots_parser = await self._get_robots_parser(start_url)

        # BFS queue: (url, depth)
        queue = deque([(start_url, 0)])
        pages = []
        self.visited_urls = set()
        self.link_graph = {}

        # Semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrency)

        async def crawl_page(url: str, depth: int):
            """Crawl a single page."""
            async with semaphore:
                # Check if already visited
                if url in self.visited_urls:
                    return

                # Check max pages limit
                if len(self.visited_urls) >= max_pages:
                    return

                # Check same domain
                if urlparse(url).netloc != base_domain:
                    return

                # Check URL patterns
                if include_regex and not include_regex.search(url):
                    return
                if exclude_regex and exclude_regex.search(url):
                    return

                # Check robots.txt
                if robots_parser and not robots_parser.can_fetch("*", url):
                    logger.debug(f"Robots.txt disallows: {url}")
                    return

                # Mark as visited
                self.visited_urls.add(url)

                # Polite crawling delay
                if crawl_delay > 0:
                    await asyncio.sleep(crawl_delay)

                try:
                    # Crawl page with selector
                    markdown, metadata = await convert_webpage_with_selector(
                        url=url,
                        css_selector=css_selector,
                        extract_links=True,
                        session_id=session_id,
                        use_stealth=use_stealth,
                    )

                    # Extract links for next depth
                    links_data = metadata.get("links", {})
                    internal_links = links_data.get("internal_links", [])
                    link_urls = [link["url"] for link in internal_links]

                    # Store in link graph
                    self.link_graph[url] = link_urls

                    # Add page to results
                    pages.append({
                        "url": url,
                        "markdown": markdown,
                        "metadata": metadata,
                        "depth": depth,
                    })

                    # Queue links for next depth
                    if depth < max_depth:
                        for link_url in link_urls:
                            if link_url not in self.visited_urls:
                                queue.append((link_url, depth + 1))

                    logger.info(f"Crawled ({depth}): {url} - {len(link_urls)} links")

                except Exception as e:
                    logger.error(f"Failed to crawl {url}: {e}")

        # Process queue
        while queue and len(self.visited_urls) < max_pages:
            url, depth = queue.popleft()

            # Skip if already visited
            if url in self.visited_urls:
                continue

            # Crawl page
            await crawl_page(url, depth)

        # Generate summary
        duration_ms = int((time.time() - start_time) * 1000)
        domains = set(urlparse(url).netloc for url in self.visited_urls)

        summary = {
            "total_pages": len(pages),
            "link_graph": self.link_graph,
            "domains": list(domains),
            "duration_ms": duration_ms,
            "max_depth_reached": max(p["depth"] for p in pages) if pages else 0,
        }

        logger.info(
            f"Crawl complete: {len(pages)} pages, {len(self.link_graph)} nodes in graph"
        )

        return pages, summary

    async def _get_robots_parser(self, url: str) -> Optional[RobotFileParser]:
        """Fetch and parse robots.txt for the given URL."""
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(robots_url)
                response.raise_for_status()

                parser = RobotFileParser()
                parser.parse(response.text.splitlines())

                logger.debug(f"Loaded robots.txt from {robots_url}")
                return parser

        except Exception as e:
            logger.debug(f"Could not fetch robots.txt from {robots_url}: {e}")
            return None

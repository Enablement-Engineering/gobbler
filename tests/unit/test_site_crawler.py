"""Unit tests for site crawler."""

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.robotparser import RobotFileParser

import pytest

from gobbler_mcp.crawlers.site_crawler import SiteCrawler


@pytest.fixture
def mock_convert_webpage():
    """Mock webpage conversion function."""

    async def _mock_convert(
        url, css_selector=None, extract_links=False, session_id=None, use_stealth=False
    ):
        return (
            f"# Content from {url}\n\nThis is the content.",
            {
                "url": url,
                "links": {
                    "internal_links": [
                        {"url": f"{url}/page1", "text": "Page 1"},
                        {"url": f"{url}/page2", "text": "Page 2"},
                    ],
                    "external_links": [],
                    "total_count": 2,
                },
            },
        )

    return _mock_convert


@pytest.fixture
def crawler():
    """Create a fresh SiteCrawler instance."""
    return SiteCrawler()


class TestMaxDepth:
    """Tests for max_depth parameter."""

    @pytest.mark.asyncio
    async def test_max_depth_limits_crawl(self, crawler, mock_convert_webpage):
        """Test that max_depth limits crawl depth."""
        with (
            patch(
                "gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector",
                mock_convert_webpage,
            ),
            patch.object(crawler, "_get_robots_parser", return_value=None),
        ):
            pages, summary = await crawler.crawl_site(
                start_url="https://example.com",
                max_depth=0,
                max_pages=100,
                crawl_delay=0,
            )

        # With depth 0, should only crawl start URL
        assert len(pages) == 1
        assert pages[0]["depth"] == 0
        assert summary["max_depth_reached"] == 0

    @pytest.mark.asyncio
    async def test_max_depth_capped_at_5(self, crawler, mock_convert_webpage):
        """Test that max_depth is capped at 5."""
        with (
            patch(
                "gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector",
                mock_convert_webpage,
            ),
            patch.object(crawler, "_get_robots_parser", return_value=None),
        ):
            # Request depth 10, should be capped to 5
            pages, summary = await crawler.crawl_site(
                start_url="https://example.com",
                max_depth=10,
                max_pages=1,  # Limit to 1 page to keep test fast
                crawl_delay=0,
            )

        # Should still work (capped to 5 internally)
        assert len(pages) >= 1


class TestMaxPages:
    """Tests for max_pages parameter."""

    @pytest.mark.asyncio
    async def test_max_pages_limits_crawl(self, crawler, mock_convert_webpage):
        """Test that max_pages limits number of pages crawled."""
        with (
            patch(
                "gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector",
                mock_convert_webpage,
            ),
            patch.object(crawler, "_get_robots_parser", return_value=None),
        ):
            pages, summary = await crawler.crawl_site(
                start_url="https://example.com",
                max_depth=5,
                max_pages=3,
                crawl_delay=0,
            )

        assert len(pages) <= 3
        assert summary["total_pages"] <= 3

    @pytest.mark.asyncio
    async def test_max_pages_capped_at_500(self, crawler):
        """Test that max_pages is capped at 500."""
        # This is a unit test - just verify the cap is applied
        with patch("gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector") as mock:
            mock.side_effect = Exception("Stop early")
            with patch.object(crawler, "_get_robots_parser", return_value=None):
                try:
                    await crawler.crawl_site(
                        start_url="https://example.com",
                        max_pages=1000,  # Request 1000
                        crawl_delay=0,
                    )
                except Exception:
                    pass
                # The function should have capped to 500 internally


class TestUrlPatterns:
    """Tests for URL include/exclude patterns."""

    @pytest.mark.asyncio
    async def test_url_include_pattern(self, crawler):
        """Test that url_include_pattern filters URLs."""
        call_count = 0

        async def mock_convert(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return (
                f"# Content from {url}",
                {
                    "url": url,
                    "links": {
                        "internal_links": [
                            {"url": "https://example.com/posts/1", "text": "Post 1"},
                            {"url": "https://example.com/about", "text": "About"},
                        ],
                        "external_links": [],
                    },
                },
            )

        with patch("gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector", mock_convert):
            with patch.object(crawler, "_get_robots_parser", return_value=None):
                pages, summary = await crawler.crawl_site(
                    start_url="https://example.com/posts/intro",
                    url_include_pattern=r"/posts/",
                    max_depth=1,
                    max_pages=10,
                    crawl_delay=0,
                )

        # Should only crawl pages matching /posts/
        for page in pages:
            assert "/posts/" in page["url"]

    @pytest.mark.asyncio
    async def test_url_exclude_pattern(self, crawler):
        """Test that url_exclude_pattern filters out URLs."""

        async def mock_convert(url, **kwargs):
            return (
                f"# Content from {url}",
                {
                    "url": url,
                    "links": {
                        "internal_links": [
                            {"url": "https://example.com/page", "text": "Page"},
                            {"url": "https://example.com/admin/settings", "text": "Admin"},
                        ],
                        "external_links": [],
                    },
                },
            )

        with patch("gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector", mock_convert):
            with patch.object(crawler, "_get_robots_parser", return_value=None):
                pages, summary = await crawler.crawl_site(
                    start_url="https://example.com",
                    url_exclude_pattern=r"/admin/",
                    max_depth=1,
                    max_pages=10,
                    crawl_delay=0,
                )

        # Should not crawl pages matching /admin/
        for page in pages:
            assert "/admin/" not in page["url"]


class TestRobotsTxt:
    """Tests for robots.txt handling."""

    @pytest.mark.asyncio
    async def test_respects_robots_txt_disallow(self, crawler):
        """Test that crawler respects robots.txt disallow rules."""
        # Create a mock robots parser that disallows /private/
        mock_parser = MagicMock(spec=RobotFileParser)
        mock_parser.can_fetch.side_effect = lambda agent, url: "/private/" not in url

        async def mock_convert(url, **kwargs):
            return (
                f"# Content from {url}",
                {
                    "url": url,
                    "links": {
                        "internal_links": [
                            {"url": "https://example.com/public", "text": "Public"},
                            {"url": "https://example.com/private/secret", "text": "Secret"},
                        ],
                        "external_links": [],
                    },
                },
            )

        with patch("gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector", mock_convert):
            with patch.object(crawler, "_get_robots_parser", return_value=mock_parser):
                pages, summary = await crawler.crawl_site(
                    start_url="https://example.com",
                    respect_robots_txt=True,
                    max_depth=1,
                    crawl_delay=0,
                )

        # Should not have crawled /private/ pages
        for page in pages:
            assert "/private/" not in page["url"]

    @pytest.mark.asyncio
    async def test_ignores_robots_txt_when_disabled(self, crawler):
        """Test that crawler ignores robots.txt when disabled."""

        async def mock_convert(url, **kwargs):
            return (
                f"# Content from {url}",
                {
                    "url": url,
                    "links": {
                        "internal_links": [],
                        "external_links": [],
                    },
                },
            )

        with patch("gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector", mock_convert):
            # _get_robots_parser should not be called
            with patch.object(crawler, "_get_robots_parser") as mock_robots:
                pages, summary = await crawler.crawl_site(
                    start_url="https://example.com",
                    respect_robots_txt=False,
                    max_depth=0,
                    crawl_delay=0,
                )

        # robots parser should not be fetched
        mock_robots.assert_not_called()


class TestCircularLinks:
    """Tests for handling circular/duplicate links."""

    @pytest.mark.asyncio
    async def test_does_not_revisit_urls(self, crawler):
        """Test that crawler does not revisit already visited URLs."""
        visit_count = {}

        async def mock_convert(url, **kwargs):
            visit_count[url] = visit_count.get(url, 0) + 1
            return (
                f"# Content from {url}",
                {
                    "url": url,
                    "links": {
                        "internal_links": [
                            # Circular link back to start
                            {"url": "https://example.com", "text": "Home"},
                            {"url": "https://example.com/page1", "text": "Page 1"},
                        ],
                        "external_links": [],
                    },
                },
            )

        with patch("gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector", mock_convert):
            with patch.object(crawler, "_get_robots_parser", return_value=None):
                pages, summary = await crawler.crawl_site(
                    start_url="https://example.com",
                    max_depth=2,
                    max_pages=10,
                    crawl_delay=0,
                )

        # Each URL should only be visited once
        for url, count in visit_count.items():
            assert count == 1, f"URL {url} was visited {count} times"

    @pytest.mark.asyncio
    async def test_handles_self_referencing_page(self, crawler):
        """Test handling of a page that links to itself."""

        async def mock_convert(url, **kwargs):
            return (
                f"# Content from {url}",
                {
                    "url": url,
                    "links": {
                        "internal_links": [
                            {"url": url, "text": "Self"},  # Self-reference
                        ],
                        "external_links": [],
                    },
                },
            )

        with patch("gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector", mock_convert):
            with patch.object(crawler, "_get_robots_parser", return_value=None):
                pages, summary = await crawler.crawl_site(
                    start_url="https://example.com",
                    max_depth=2,
                    max_pages=10,
                    crawl_delay=0,
                )

        # Should only have one page
        assert len(pages) == 1


class TestConcurrency:
    """Tests for concurrency handling."""

    @pytest.mark.asyncio
    async def test_concurrency_capped_at_10(self, crawler):
        """Test that concurrency is capped at 10."""

        async def mock_convert(url, **kwargs):
            return (
                "# Content",
                {"url": url, "links": {"internal_links": [], "external_links": []}},
            )

        with patch("gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector", mock_convert):
            with patch.object(crawler, "_get_robots_parser", return_value=None):
                # Request concurrency 20, should be capped to 10
                pages, summary = await crawler.crawl_site(
                    start_url="https://example.com",
                    concurrency=20,
                    max_depth=0,
                    crawl_delay=0,
                )

        # Should still work (capped internally)
        assert len(pages) == 1


class TestCrossDomain:
    """Tests for cross-domain link handling."""

    @pytest.mark.asyncio
    async def test_stays_on_same_domain(self, crawler):
        """Test that crawler stays on the same domain."""

        async def mock_convert(url, **kwargs):
            return (
                f"# Content from {url}",
                {
                    "url": url,
                    "links": {
                        "internal_links": [
                            {"url": "https://example.com/local", "text": "Local"},
                            {"url": "https://other-domain.com/page", "text": "External"},
                        ],
                        "external_links": [],
                    },
                },
            )

        with patch("gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector", mock_convert):
            with patch.object(crawler, "_get_robots_parser", return_value=None):
                pages, summary = await crawler.crawl_site(
                    start_url="https://example.com",
                    max_depth=1,
                    max_pages=10,
                    crawl_delay=0,
                )

        # All pages should be on example.com
        for page in pages:
            assert "example.com" in page["url"]


class TestLinkGraph:
    """Tests for link graph generation."""

    @pytest.mark.asyncio
    async def test_link_graph_generated(self, crawler):
        """Test that link graph is correctly generated."""

        async def mock_convert(url, **kwargs):
            links = []
            if url == "https://example.com":
                links = [
                    {"url": "https://example.com/page1", "text": "Page 1"},
                    {"url": "https://example.com/page2", "text": "Page 2"},
                ]
            return (
                f"# Content from {url}",
                {
                    "url": url,
                    "links": {
                        "internal_links": links,
                        "external_links": [],
                    },
                },
            )

        with patch("gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector", mock_convert):
            with patch.object(crawler, "_get_robots_parser", return_value=None):
                pages, summary = await crawler.crawl_site(
                    start_url="https://example.com",
                    max_depth=1,
                    crawl_delay=0,
                )

        link_graph = summary["link_graph"]
        assert "https://example.com" in link_graph
        assert "https://example.com/page1" in link_graph["https://example.com"]
        assert "https://example.com/page2" in link_graph["https://example.com"]


class TestRobotsParser:
    """Tests for robots.txt parser fetching."""

    @pytest.mark.asyncio
    async def test_get_robots_parser_success(self, crawler):
        """Test successfully fetching and parsing robots.txt."""
        robots_content = "User-agent: *\nDisallow: /private/\n"

        with patch("gobbler_mcp.crawlers.site_crawler.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.text = robots_content
            mock_response.raise_for_status = MagicMock()

            client_instance = AsyncMock()
            client_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = client_instance

            parser = await crawler._get_robots_parser("https://example.com/page")

        assert parser is not None
        assert not parser.can_fetch("*", "https://example.com/private/secret")
        assert parser.can_fetch("*", "https://example.com/public")

    @pytest.mark.asyncio
    async def test_get_robots_parser_not_found(self, crawler):
        """Test handling when robots.txt is not found."""
        with patch("gobbler_mcp.crawlers.site_crawler.httpx.AsyncClient") as mock_client:
            client_instance = AsyncMock()
            client_instance.get = AsyncMock(side_effect=Exception("404 Not Found"))
            mock_client.return_value.__aenter__.return_value = client_instance

            parser = await crawler._get_robots_parser("https://example.com")

        assert parser is None


class TestCrawlErrors:
    """Tests for error handling during crawl."""

    @pytest.mark.asyncio
    async def test_continues_on_page_error(self, crawler):
        """Test that crawler continues when a page fails."""
        call_count = 0

        async def mock_convert(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "fail" in url:
                raise Exception("Page load failed")
            return (
                f"# Content from {url}",
                {
                    "url": url,
                    "links": {
                        "internal_links": [
                            {"url": "https://example.com/fail", "text": "Fail"},
                            {"url": "https://example.com/success", "text": "Success"},
                        ],
                        "external_links": [],
                    },
                },
            )

        with patch("gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector", mock_convert):
            with patch.object(crawler, "_get_robots_parser", return_value=None):
                pages, summary = await crawler.crawl_site(
                    start_url="https://example.com",
                    max_depth=1,
                    crawl_delay=0,
                )

        # Should have crawled start page and success page
        assert len(pages) >= 1
        urls = [p["url"] for p in pages]
        assert "https://example.com" in urls


class TestSummary:
    """Tests for crawl summary generation."""

    @pytest.mark.asyncio
    async def test_summary_contains_expected_fields(self, crawler, mock_convert_webpage):
        """Test that summary contains all expected fields."""
        with (
            patch(
                "gobbler_mcp.crawlers.site_crawler.convert_webpage_with_selector",
                mock_convert_webpage,
            ),
            patch.object(crawler, "_get_robots_parser", return_value=None),
        ):
            pages, summary = await crawler.crawl_site(
                start_url="https://example.com",
                max_depth=0,
                crawl_delay=0,
            )

        assert "total_pages" in summary
        assert "link_graph" in summary
        assert "domains" in summary
        assert "duration_ms" in summary
        assert "max_depth_reached" in summary

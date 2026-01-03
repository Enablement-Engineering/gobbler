"""Unit tests for crawl tools."""

import importlib.util
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _import_crawl_module():
    """Import crawl module avoiding the problematic import chain."""
    spec = importlib.util.spec_from_file_location(
        "gobbler_mcp.tools.crawl", "src/gobbler_mcp/tools/crawl.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("Failed to load crawl module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["gobbler_mcp.tools.crawl"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def crawl_module():
    """Import the crawl module."""
    return _import_crawl_module()


@pytest.fixture
def mock_mcp():
    """Create a mock FastMCP instance that captures registered tools."""
    mcp = MagicMock()
    registered_tools = {}

    def tool_decorator():
        def decorator(func):
            registered_tools[func.__name__] = func
            return func

        return decorator

    mcp.tool = tool_decorator
    mcp._registered_tools = registered_tools
    return mcp


@pytest.fixture
def crawl_tools(crawl_module, mock_mcp):
    """Register and return crawl tools."""
    crawl_module.register_tools(mock_mcp)
    return mock_mcp._registered_tools


class TestCreateCrawlSession:
    """Tests for create_crawl_session tool."""

    @pytest.mark.asyncio
    async def test_create_session_with_cookies(self, crawl_tools, crawl_module):
        """Test creating a session with valid cookies JSON."""
        create_crawl_session = crawl_tools["create_crawl_session"]

        cookies = '[{"name": "session", "value": "abc123", "domain": "example.com"}]'

        with patch.object(crawl_module, "SessionManager", create=True) as mock_manager:
            instance = AsyncMock()
            mock_manager.return_value = instance
            instance.create_session.return_value = {
                "session_id": "test-session",
                "file_path": "/path/to/session.json",
                "cookie_count": 1,
                "local_storage_keys": [],
                "has_user_agent": False,
            }

            # Patch within the function's scope
            with patch("gobbler_mcp.crawlers.session_manager.SessionManager", mock_manager):
                result = await create_crawl_session(session_id="test-session", cookies=cookies)

        assert "test-session" in result
        assert "created successfully" in result
        assert "Cookies: 1" in result

    @pytest.mark.asyncio
    async def test_create_session_with_local_storage(self, crawl_tools, crawl_module):
        """Test creating a session with localStorage."""
        create_crawl_session = crawl_tools["create_crawl_session"]

        local_storage = '{"user_id": "12345", "theme": "dark"}'

        with patch("gobbler_mcp.crawlers.session_manager.SessionManager") as mock_manager:
            instance = AsyncMock()
            mock_manager.return_value = instance
            instance.create_session.return_value = {
                "session_id": "storage-session",
                "file_path": "/path/to/session.json",
                "cookie_count": 0,
                "local_storage_keys": ["user_id", "theme"],
                "has_user_agent": False,
            }

            result = await create_crawl_session(
                session_id="storage-session", local_storage=local_storage
            )

        assert "storage-session" in result
        assert "localStorage keys: user_id, theme" in result

    @pytest.mark.asyncio
    async def test_create_session_with_user_agent(self, crawl_tools, crawl_module):
        """Test creating a session with custom user agent."""
        create_crawl_session = crawl_tools["create_crawl_session"]

        with patch("gobbler_mcp.crawlers.session_manager.SessionManager") as mock_manager:
            instance = AsyncMock()
            mock_manager.return_value = instance
            instance.create_session.return_value = {
                "session_id": "ua-session",
                "file_path": "/path/to/session.json",
                "cookie_count": 0,
                "local_storage_keys": [],
                "has_user_agent": True,
            }

            result = await create_crawl_session(session_id="ua-session", user_agent="CustomBot/1.0")

        assert "Custom user agent: configured" in result

    @pytest.mark.asyncio
    async def test_create_session_invalid_cookies_json(self, crawl_tools):
        """Test error handling for invalid cookies JSON."""
        create_crawl_session = crawl_tools["create_crawl_session"]

        result = await create_crawl_session(session_id="test-session", cookies="not valid json")

        assert "Error: Invalid cookies JSON" in result

    @pytest.mark.asyncio
    async def test_create_session_cookies_not_array(self, crawl_tools):
        """Test error when cookies is not an array."""
        create_crawl_session = crawl_tools["create_crawl_session"]

        result = await create_crawl_session(
            session_id="test-session",
            cookies='{"name": "value"}',  # Object instead of array
        )

        assert "Error: cookies must be a JSON array" in result

    @pytest.mark.asyncio
    async def test_create_session_invalid_local_storage_json(self, crawl_tools):
        """Test error handling for invalid local_storage JSON."""
        create_crawl_session = crawl_tools["create_crawl_session"]

        result = await create_crawl_session(
            session_id="test-session", local_storage="not valid json"
        )

        assert "Error: Invalid local_storage JSON" in result

    @pytest.mark.asyncio
    async def test_create_session_local_storage_not_object(self, crawl_tools):
        """Test error when local_storage is not an object."""
        create_crawl_session = crawl_tools["create_crawl_session"]

        result = await create_crawl_session(
            session_id="test-session", local_storage='["array", "not", "object"]'
        )

        assert "Error: local_storage must be a JSON object" in result

    @pytest.mark.asyncio
    async def test_create_session_invalid_session_id(self, crawl_tools):
        """Test error for invalid session_id characters."""
        create_crawl_session = crawl_tools["create_crawl_session"]

        result = await create_crawl_session(session_id="invalid@session#id!")

        assert "Error: session_id must contain only alphanumeric" in result

    @pytest.mark.asyncio
    async def test_create_session_valid_session_id_formats(self, crawl_tools):
        """Test that valid session_id formats are accepted."""
        create_crawl_session = crawl_tools["create_crawl_session"]

        valid_ids = ["my-session", "my_session", "mySession123", "test-site_v2"]

        for session_id in valid_ids:
            with patch("gobbler_mcp.crawlers.session_manager.SessionManager") as mock_manager:
                instance = AsyncMock()
                mock_manager.return_value = instance
                instance.create_session.return_value = {
                    "session_id": session_id,
                    "file_path": "/path/to/session.json",
                    "cookie_count": 0,
                    "local_storage_keys": [],
                    "has_user_agent": False,
                }

                result = await create_crawl_session(session_id=session_id)

            assert "Error" not in result, f"Session ID {session_id} should be valid"


class TestCrawlSite:
    """Tests for crawl_site tool."""

    @pytest.mark.asyncio
    async def test_crawl_site_basic(self, crawl_tools):
        """Test basic crawl_site functionality."""
        crawl_site = crawl_tools["crawl_site"]

        mock_pages = [
            {"url": "https://example.com", "markdown": "# Home", "metadata": {}, "depth": 0},
            {"url": "https://example.com/about", "markdown": "# About", "metadata": {}, "depth": 1},
        ]
        mock_summary = {
            "total_pages": 2,
            "link_graph": {
                "https://example.com": ["https://example.com/about"],
            },
            "domains": ["example.com"],
            "duration_ms": 1500,
            "max_depth_reached": 1,
        }

        with patch("gobbler_mcp.crawlers.site_crawler.SiteCrawler") as mock_crawler:
            instance = AsyncMock()
            mock_crawler.return_value = instance
            instance.crawl_site.return_value = (mock_pages, mock_summary)

            result = await crawl_site(
                start_url="https://example.com",
                max_depth=2,
                max_pages=50,
            )

        assert "Crawl complete: 2 pages" in result
        assert "Duration: 1500ms" in result
        assert "Max depth reached: 1" in result
        assert "example.com" in result

    @pytest.mark.asyncio
    async def test_crawl_site_with_output_dir(self, crawl_tools, crawl_module, tmp_path):
        """Test crawl_site with output directory."""
        crawl_site = crawl_tools["crawl_site"]

        output_dir = str(tmp_path / "crawled")

        mock_pages = [
            {"url": "https://example.com", "markdown": "# Home", "metadata": {}, "depth": 0},
        ]
        mock_summary = {
            "total_pages": 1,
            "link_graph": {},
            "domains": ["example.com"],
            "duration_ms": 500,
            "max_depth_reached": 0,
        }

        with patch("gobbler_mcp.crawlers.site_crawler.SiteCrawler") as mock_crawler:
            with patch.object(crawl_module, "save_markdown_file", return_value=True):
                instance = AsyncMock()
                mock_crawler.return_value = instance
                instance.crawl_site.return_value = (mock_pages, mock_summary)

                result = await crawl_site(
                    start_url="https://example.com",
                    output_dir=output_dir,
                )

        assert f"Pages saved to: {output_dir}" in result

    @pytest.mark.asyncio
    async def test_crawl_site_link_graph_summary(self, crawl_tools):
        """Test that link graph summary is included."""
        crawl_site = crawl_tools["crawl_site"]

        mock_pages = [
            {"url": "https://example.com", "markdown": "# Home", "metadata": {}, "depth": 0},
            {"url": "https://example.com/a", "markdown": "# A", "metadata": {}, "depth": 1},
            {"url": "https://example.com/b", "markdown": "# B", "metadata": {}, "depth": 1},
        ]
        mock_summary = {
            "total_pages": 3,
            "link_graph": {
                "https://example.com": ["https://example.com/a", "https://example.com/b"],
                "https://example.com/a": ["https://example.com/b"],
                "https://example.com/b": ["https://example.com/a"],
            },
            "domains": ["example.com"],
            "duration_ms": 1000,
            "max_depth_reached": 1,
        }

        with patch("gobbler_mcp.crawlers.site_crawler.SiteCrawler") as mock_crawler:
            instance = AsyncMock()
            mock_crawler.return_value = instance
            instance.crawl_site.return_value = (mock_pages, mock_summary)

            result = await crawl_site(start_url="https://example.com")

        assert "Link Graph Summary" in result
        assert "Total nodes: 3" in result
        assert "Total edges: 4" in result
        assert "Most linked pages" in result

    @pytest.mark.asyncio
    async def test_crawl_site_with_css_selector(self, crawl_tools):
        """Test crawl_site passes CSS selector."""
        crawl_site = crawl_tools["crawl_site"]

        mock_summary = {
            "total_pages": 1,
            "link_graph": {},
            "domains": ["example.com"],
            "duration_ms": 500,
            "max_depth_reached": 0,
        }

        with patch("gobbler_mcp.crawlers.site_crawler.SiteCrawler") as mock_crawler:
            instance = AsyncMock()
            mock_crawler.return_value = instance
            instance.crawl_site.return_value = ([], mock_summary)

            await crawl_site(
                start_url="https://example.com",
                css_selector="article.content",
            )

        # Verify css_selector was passed
        call_kwargs = instance.crawl_site.call_args.kwargs
        assert call_kwargs["css_selector"] == "article.content"

    @pytest.mark.asyncio
    async def test_crawl_site_with_url_patterns(self, crawl_tools):
        """Test crawl_site passes URL patterns."""
        crawl_site = crawl_tools["crawl_site"]

        mock_summary = {
            "total_pages": 1,
            "link_graph": {},
            "domains": ["example.com"],
            "duration_ms": 500,
            "max_depth_reached": 0,
        }

        with patch("gobbler_mcp.crawlers.site_crawler.SiteCrawler") as mock_crawler:
            instance = AsyncMock()
            mock_crawler.return_value = instance
            instance.crawl_site.return_value = ([], mock_summary)

            await crawl_site(
                start_url="https://example.com",
                url_include_pattern=r"/posts/",
                url_exclude_pattern=r"/admin/",
            )

        # Verify patterns were passed
        call_kwargs = instance.crawl_site.call_args.kwargs
        assert call_kwargs["url_include_pattern"] == r"/posts/"
        assert call_kwargs["url_exclude_pattern"] == r"/admin/"

    @pytest.mark.asyncio
    async def test_crawl_site_with_session_id(self, crawl_tools):
        """Test crawl_site passes session ID."""
        crawl_site = crawl_tools["crawl_site"]

        mock_summary = {
            "total_pages": 1,
            "link_graph": {},
            "domains": ["example.com"],
            "duration_ms": 500,
            "max_depth_reached": 0,
        }

        with patch("gobbler_mcp.crawlers.site_crawler.SiteCrawler") as mock_crawler:
            instance = AsyncMock()
            mock_crawler.return_value = instance
            instance.crawl_site.return_value = ([], mock_summary)

            await crawl_site(
                start_url="https://example.com",
                session_id="my-auth-session",
            )

        # Verify session_id was passed
        call_kwargs = instance.crawl_site.call_args.kwargs
        assert call_kwargs["session_id"] == "my-auth-session"

    @pytest.mark.asyncio
    async def test_crawl_site_respects_robots_txt_param(self, crawl_tools):
        """Test crawl_site passes respect_robots_txt parameter."""
        crawl_site = crawl_tools["crawl_site"]

        mock_summary = {
            "total_pages": 1,
            "link_graph": {},
            "domains": ["example.com"],
            "duration_ms": 500,
            "max_depth_reached": 0,
        }

        with patch("gobbler_mcp.crawlers.site_crawler.SiteCrawler") as mock_crawler:
            instance = AsyncMock()
            mock_crawler.return_value = instance
            instance.crawl_site.return_value = ([], mock_summary)

            await crawl_site(
                start_url="https://example.com",
                respect_robots_txt=False,
            )

        call_kwargs = instance.crawl_site.call_args.kwargs
        assert call_kwargs["respect_robots_txt"] is False

    @pytest.mark.asyncio
    async def test_crawl_site_error_handling(self, crawl_tools):
        """Test crawl_site error handling."""
        crawl_site = crawl_tools["crawl_site"]

        with patch("gobbler_mcp.crawlers.site_crawler.SiteCrawler") as mock_crawler:
            instance = AsyncMock()
            mock_crawler.return_value = instance
            instance.crawl_site.side_effect = Exception("Connection failed")

            result = await crawl_site(start_url="https://example.com")

        assert "Failed to crawl site" in result
        assert "Connection failed" in result

    @pytest.mark.asyncio
    async def test_crawl_site_empty_link_graph(self, crawl_tools):
        """Test crawl_site with empty link graph."""
        crawl_site = crawl_tools["crawl_site"]

        mock_pages = [
            {"url": "https://example.com", "markdown": "# Home", "metadata": {}, "depth": 0},
        ]
        mock_summary = {
            "total_pages": 1,
            "link_graph": {},
            "domains": ["example.com"],
            "duration_ms": 500,
            "max_depth_reached": 0,
        }

        with patch("gobbler_mcp.crawlers.site_crawler.SiteCrawler") as mock_crawler:
            instance = AsyncMock()
            mock_crawler.return_value = instance
            instance.crawl_site.return_value = (mock_pages, mock_summary)

            result = await crawl_site(start_url="https://example.com")

        assert "Crawl complete: 1 pages" in result
        # Should not have "Most linked pages" section when no incoming links
        assert "Total nodes: 0" in result

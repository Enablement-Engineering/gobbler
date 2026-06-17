"""Unit tests for webpage selector converter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gobbler_core.converters.webpage_selector import (
    _extract_links,
    _extract_selector_content,
    _html_to_simple_markdown,
    convert_webpage_with_selector,
)


def setup_mock_client(client_instance, task_response):
    """Helper to setup mock client with proper async responses."""
    # Mock crawl submission - client.post() is async and returns a response
    post_response = MagicMock()
    post_response.json.return_value = {"task_id": "test-task-123"}
    post_response.raise_for_status = MagicMock()
    client_instance.post = AsyncMock(return_value=post_response)

    # Mock task status - client.get() is async and returns a response
    get_response = MagicMock()
    get_response.json.return_value = {"status": "completed", "results": [task_response]}
    get_response.raise_for_status = MagicMock()
    client_instance.get = AsyncMock(return_value=get_response)


@pytest.mark.asyncio
async def test_convert_webpage_with_css_selector(mock_crawl4ai_response):
    """Test webpage conversion with CSS selector."""
    with patch("gobbler_core.converters.webpage_selector.RetryableHTTPClient") as mock_client:
        # Setup mock client
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        setup_mock_client(client_instance, mock_crawl4ai_response)

        markdown, metadata = await convert_webpage_with_selector(
            url="https://example.com/article", css_selector="article.main"
        )

        assert "Test Article" in markdown
        assert metadata["url"] == "https://example.com/article"
        assert metadata["css_selector"] == "article.main"
        assert "word_count" in metadata


@pytest.mark.asyncio
async def test_convert_webpage_with_xpath(mock_crawl4ai_response):
    """Test webpage conversion with XPath selector."""
    with patch("gobbler_core.converters.webpage_selector.RetryableHTTPClient") as mock_client:
        # Setup mock client
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        setup_mock_client(client_instance, mock_crawl4ai_response)

        markdown, metadata = await convert_webpage_with_selector(
            url="https://example.com/article", xpath="//article[@class='main']"
        )

        assert "Test Article" in markdown
        assert metadata["xpath"] == "//article[@class='main']"


@pytest.mark.asyncio
async def test_convert_webpage_with_both_selectors_raises_error():
    """Test that providing both CSS and XPath selectors raises ValueError."""
    with pytest.raises(ValueError, match="Cannot specify both css_selector and xpath"):
        await convert_webpage_with_selector(
            url="https://example.com", css_selector="div.content", xpath="//div[@class='content']"
        )


@pytest.mark.asyncio
async def test_convert_webpage_with_selector_extracts_from_html(mock_crawl4ai_response):
    """Test webpage conversion extracts content from HTML using selector."""
    with patch("gobbler_core.converters.webpage_selector.RetryableHTTPClient") as mock_client:
        # Setup mock client
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance

        # Mock response with HTML content that has an article
        response_with_html = mock_crawl4ai_response.copy()
        response_with_html["html"] = """
        <html>
            <body>
                <nav>Navigation menu</nav>
                <article>
                    <h1>Article Title</h1>
                    <p>This is the article content.</p>
                </article>
                <footer>Footer content</footer>
            </body>
        </html>
        """

        setup_mock_client(client_instance, response_with_html)

        markdown, _metadata = await convert_webpage_with_selector(
            url="https://example.com", css_selector="article"
        )

        # Should extract article content
        assert "Article Title" in markdown
        assert "article content" in markdown


@pytest.mark.asyncio
async def test_convert_webpage_with_link_extraction(mock_crawl4ai_response):
    """Test webpage conversion with link extraction."""
    with patch("gobbler_core.converters.webpage_selector.RetryableHTTPClient") as mock_client:
        # Setup mock client
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance

        # Add HTML content to response for link extraction
        response_with_html = mock_crawl4ai_response.copy()
        response_with_html["html"] = """
        <html>
            <body>
                <a href="https://example.com/page1">Internal Link</a>
                <a href="/page2">Relative Link</a>
                <a href="https://external.com">External Link</a>
            </body>
        </html>
        """

        setup_mock_client(client_instance, response_with_html)

        _markdown, metadata = await convert_webpage_with_selector(
            url="https://example.com", extract_links=True
        )

        assert "links" in metadata
        links = metadata["links"]
        assert links["total_count"] == 3
        assert links["internal_count"] == 2
        assert links["external_count"] == 1


@pytest.mark.asyncio
async def test_convert_webpage_bypass_cache(mock_crawl4ai_response):
    """Test webpage conversion with cache bypass."""
    with patch("gobbler_core.converters.webpage_selector.RetryableHTTPClient") as mock_client:
        # Setup mock client
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        setup_mock_client(client_instance, mock_crawl4ai_response)

        await convert_webpage_with_selector(url="https://example.com", bypass_cache=True)

        # Check that cache_mode was set to bypass
        post_call_args = client_instance.post.call_args
        crawl_request = post_call_args[1]["json"]
        assert crawl_request["crawler_config"]["params"]["cache_mode"] == "bypass"


@pytest.mark.asyncio
async def test_convert_webpage_selector_uses_documented_proxy_config(mock_crawl4ai_response):
    """Test selector conversion sends Crawl4AI proxy settings as a plain dict."""
    proxy_url = "http://proxy-user:proxy-pass@proxy.example:8080"
    with (
        patch(
            "gobbler_core.providers.proxy.get_crawl4ai_proxy_url",
            return_value=proxy_url,
        ),
        patch("gobbler_core.converters.webpage_selector.RetryableHTTPClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        setup_mock_client(client_instance, mock_crawl4ai_response)

        await convert_webpage_with_selector(url="https://example.com")

        post_call_args = client_instance.post.call_args
        crawl_request = post_call_args[1]["json"]
        proxy_config = crawl_request["crawler_config"]["params"]["proxy_config"]

    assert proxy_config == {
        "server": "http://proxy.example:8080",
        "username": "proxy-user",
        "password": "proxy-pass",
    }
    assert "type" not in proxy_config


@pytest.mark.asyncio
async def test_convert_webpage_selector_can_bypass_configured_proxy(mock_crawl4ai_response):
    """Test selector conversion can skip configured Crawl4AI proxy settings."""
    with (
        patch("gobbler_core.providers.proxy.get_crawl4ai_proxy_url") as mock_proxy,
        patch("gobbler_core.converters.webpage_selector.RetryableHTTPClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        setup_mock_client(client_instance, mock_crawl4ai_response)

        await convert_webpage_with_selector(url="https://example.com", use_proxy=False)

        post_call_args = client_instance.post.call_args
        crawl_request = post_call_args[1]["json"]

    mock_proxy.assert_not_called()
    assert "proxy_config" not in crawl_request["crawler_config"]["params"]


def test_extract_links():
    """Test link extraction from HTML."""
    html = """
    <html>
        <body>
            <a href="https://example.com/page1">Page 1</a>
            <a href="/page2">Page 2</a>
            <a href="https://external.com/page">External</a>
            <a href="javascript:alert()">JS Link</a>
            <a href="mailto:test@example.com">Email</a>
        </body>
    </html>
    """

    links_data = _extract_links(html, "https://example.com")

    # Should have 3 valid links (excluding javascript and mailto)
    assert links_data["total_count"] == 3
    assert links_data["internal_count"] == 2
    assert links_data["external_count"] == 1

    # Check internal links
    internal_urls = [link["url"] for link in links_data["internal_links"]]
    assert "https://example.com/page1" in internal_urls
    assert "https://example.com/page2" in internal_urls

    # Check external links
    external_urls = [link["url"] for link in links_data["external_links"]]
    assert "https://external.com/page" in external_urls


def test_extract_selector_content_css():
    """Test CSS selector extraction from HTML."""
    html = """
    <html>
        <body>
            <nav>Navigation</nav>
            <article class="main">
                <h1>Article Title</h1>
                <p>Article content here.</p>
            </article>
            <footer>Footer</footer>
        </body>
    </html>
    """

    markdown = _extract_selector_content(html, css_selector="article.main", xpath=None)

    assert markdown is not None
    assert "Article Title" in markdown
    assert "Article content" in markdown
    # Navigation and footer should not be included
    assert "Navigation" not in markdown
    assert "Footer" not in markdown


def test_extract_selector_content_no_match():
    """Test selector extraction when no elements match."""
    html = "<html><body><p>No article here</p></body></html>"

    markdown = _extract_selector_content(html, css_selector="article", xpath=None)

    assert markdown is None


def test_html_to_simple_markdown():
    """Test HTML to markdown conversion."""
    from bs4 import BeautifulSoup

    html = """
    <div>
        <h1>Title</h1>
        <p>Paragraph text.</p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")

    markdown = _html_to_simple_markdown(soup)

    assert "# Title" in markdown
    assert "Paragraph text" in markdown
    assert "- Item 1" in markdown
    assert "- Item 2" in markdown


@pytest.mark.asyncio
async def test_convert_webpage_without_images(mock_crawl4ai_response):
    """Test webpage conversion without images."""
    with patch("gobbler_core.converters.webpage_selector.RetryableHTTPClient") as mock_client:
        # Setup mock client
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance

        # Add markdown with images
        response_with_images = mock_crawl4ai_response.copy()
        response_with_images["markdown"] = (
            "# Test\n\n![Image alt text](https://example.com/image.jpg)\n\nSome text"
        )

        setup_mock_client(client_instance, response_with_images)

        markdown, _metadata = await convert_webpage_with_selector(
            url="https://example.com", include_images=False
        )

        # Images should be stripped
        assert "![Image alt text]" not in markdown
        assert "Image alt text" in markdown  # Alt text preserved
        assert "https://example.com/image.jpg" not in markdown

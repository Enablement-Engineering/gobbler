"""Unit tests for webpage selector converter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from gobbler_mcp.converters.webpage_selector import (
    convert_webpage_with_selector,
    _extract_links,
    _format_extracted_content,
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
    get_response.json.return_value = {
        "status": "completed",
        "results": [task_response]
    }
    get_response.raise_for_status = MagicMock()
    client_instance.get = AsyncMock(return_value=get_response)


@pytest.mark.asyncio
async def test_convert_webpage_with_css_selector(mock_crawl4ai_response):
    """Test webpage conversion with CSS selector."""
    with patch("gobbler_mcp.converters.webpage_selector.RetryableHTTPClient") as mock_client:
        # Setup mock client
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        setup_mock_client(client_instance, mock_crawl4ai_response)

        markdown, metadata = await convert_webpage_with_selector(
            url="https://example.com/article",
            css_selector="article.main"
        )

        assert "Test Article" in markdown
        assert metadata["url"] == "https://example.com/article"
        assert metadata["css_selector"] == "article.main"
        assert "word_count" in metadata


@pytest.mark.asyncio
async def test_convert_webpage_with_xpath(mock_crawl4ai_response):
    """Test webpage conversion with XPath selector."""
    with patch("gobbler_mcp.converters.webpage_selector.RetryableHTTPClient") as mock_client:
        # Setup mock client
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        setup_mock_client(client_instance, mock_crawl4ai_response)

        markdown, metadata = await convert_webpage_with_selector(
            url="https://example.com/article",
            xpath="//article[@class='main']"
        )

        assert "Test Article" in markdown
        assert metadata["xpath"] == "//article[@class='main']"


@pytest.mark.asyncio
async def test_convert_webpage_with_both_selectors_raises_error():
    """Test that providing both CSS and XPath selectors raises ValueError."""
    with pytest.raises(ValueError, match="Cannot specify both css_selector and xpath"):
        await convert_webpage_with_selector(
            url="https://example.com",
            css_selector="div.content",
            xpath="//div[@class='content']"
        )


@pytest.mark.asyncio
async def test_convert_webpage_with_extracted_content(mock_crawl4ai_response):
    """Test webpage conversion with extracted content from selector."""
    with patch("gobbler_mcp.converters.webpage_selector.RetryableHTTPClient") as mock_client:
        # Setup mock client
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance

        # Mock responses with extracted_content
        response_with_extracted = mock_crawl4ai_response.copy()
        response_with_extracted["extracted_content"] = [
            {"content": "# Extracted Title\n\nExtracted paragraph 1"},
            {"content": "Extracted paragraph 2"}
        ]

        setup_mock_client(client_instance, response_with_extracted)

        markdown, metadata = await convert_webpage_with_selector(
            url="https://example.com",
            css_selector="article"
        )

        # Should use extracted content
        assert "Extracted Title" in markdown
        assert "Extracted paragraph 1" in markdown
        assert "Extracted paragraph 2" in markdown


@pytest.mark.asyncio
async def test_convert_webpage_with_link_extraction(mock_crawl4ai_response):
    """Test webpage conversion with link extraction."""
    with patch("gobbler_mcp.converters.webpage_selector.RetryableHTTPClient") as mock_client:
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

        markdown, metadata = await convert_webpage_with_selector(
            url="https://example.com",
            extract_links=True
        )

        assert "links" in metadata
        links = metadata["links"]
        assert links["total_count"] == 3
        assert links["internal_count"] == 2
        assert links["external_count"] == 1


@pytest.mark.asyncio
async def test_convert_webpage_with_session(mock_crawl4ai_response):
    """Test webpage conversion with session ID."""
    with patch("gobbler_mcp.converters.webpage_selector.RetryableHTTPClient") as mock_client, \
         patch("gobbler_mcp.crawlers.session_manager.SessionManager") as mock_session_mgr:

        # Setup mock session manager
        session_instance = AsyncMock()
        mock_session_mgr.return_value = session_instance
        session_instance.load_session = AsyncMock(return_value={
            "cookies": [
                {"name": "session_token", "value": "abc123", "domain": "example.com"}
            ]
        })

        # Setup mock client
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        setup_mock_client(client_instance, mock_crawl4ai_response)

        markdown, metadata = await convert_webpage_with_selector(
            url="https://example.com",
            session_id="test-session"
        )

        # Verify session was loaded
        session_instance.load_session.assert_called_once_with("test-session")
        assert metadata["session_id"] == "test-session"


@pytest.mark.asyncio
async def test_convert_webpage_bypass_cache(mock_crawl4ai_response):
    """Test webpage conversion with cache bypass."""
    with patch("gobbler_mcp.converters.webpage_selector.RetryableHTTPClient") as mock_client:
        # Setup mock client
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        setup_mock_client(client_instance, mock_crawl4ai_response)

        await convert_webpage_with_selector(
            url="https://example.com",
            bypass_cache=True
        )

        # Check that cache_mode was set to bypass
        post_call_args = client_instance.post.call_args
        crawl_request = post_call_args[1]["json"]
        assert crawl_request["crawler_config"]["params"]["cache_mode"] == "bypass"


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


def test_format_extracted_content():
    """Test formatting of extracted structured content."""
    extracted = [
        {"content": "# Title 1\n\nParagraph 1"},
        {"content": "# Title 2\n\nParagraph 2"},
        {"content": ["Nested 1", "Nested 2"]}
    ]

    markdown = _format_extracted_content(extracted)

    assert "# Title 1" in markdown
    assert "Paragraph 1" in markdown
    assert "# Title 2" in markdown
    assert "Paragraph 2" in markdown
    # Note: nested content handling may need adjustment based on actual behavior


def test_format_extracted_content_with_strings():
    """Test formatting extracted content that are plain strings."""
    extracted = [
        "String content 1",
        "String content 2"
    ]

    markdown = _format_extracted_content(extracted)

    assert "String content 1" in markdown
    assert "String content 2" in markdown


@pytest.mark.asyncio
async def test_convert_webpage_without_images(mock_crawl4ai_response):
    """Test webpage conversion without images."""
    with patch("gobbler_mcp.converters.webpage_selector.RetryableHTTPClient") as mock_client:
        # Setup mock client
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance

        # Add markdown with images
        response_with_images = mock_crawl4ai_response.copy()
        response_with_images["markdown"] = "# Test\n\n![Image alt text](https://example.com/image.jpg)\n\nSome text"

        setup_mock_client(client_instance, response_with_images)

        markdown, metadata = await convert_webpage_with_selector(
            url="https://example.com",
            include_images=False
        )

        # Images should be stripped
        assert "![Image alt text]" not in markdown
        assert "Image alt text" in markdown  # Alt text preserved
        assert "https://example.com/image.jpg" not in markdown

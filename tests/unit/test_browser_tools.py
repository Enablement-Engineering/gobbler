"""Unit tests for browser automation MCP tools.

Tests the browser tools module with mocked relay client communication.
All tests run without requiring actual browser extension connection.
"""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import FastMCP

# Constants from gobbler_mcp.constants (avoid import chain issues)
MIN_SCRIPT_TIMEOUT = 1
MAX_SCRIPT_TIMEOUT = 150
DEFAULT_SCRIPT_TIMEOUT = 30


# Mock the problematic audio module before any gobbler_mcp imports
sys.modules["gobbler_mcp.converters.audio"] = MagicMock()

# Now we can safely import
from gobbler_mcp.tools.browser import register_tools


@pytest.fixture
def mcp():
    """Create a FastMCP instance with browser tools registered."""
    mcp_server = FastMCP("test-browser")
    register_tools(mcp_server)
    return mcp_server


@pytest.fixture
def mock_relay_client():
    """Create mock relay client functions."""
    return {
        "check_connection": AsyncMock(),
        "get_connection_count": AsyncMock(),
        "send_command": AsyncMock(),
        "execute_script": AsyncMock(),
        "extract_page": AsyncMock(),
        "list_tabs": AsyncMock(),
        "execute_script_in_tab": AsyncMock(),
    }


class TestBrowserCheckConnection:
    """Tests for browser_check_connection tool."""

    @pytest.mark.asyncio
    async def test_connected_with_extensions(self, mcp, mock_relay_client):
        """Test status when browser extension is connected."""
        mock_relay_client["check_connection"].return_value = {
            "status": "ok",
            "websocket_connections": 2,
        }

        with patch(
            "gobbler_relay.client.check_connection",
            mock_relay_client["check_connection"],
        ):
            # Get the registered tool function
            tool = mcp._tool_manager._tools["browser_check_connection"]
            result = await tool.fn()

        assert "connected and ready" in result
        assert "(2 connection(s))" in result

    @pytest.mark.asyncio
    async def test_relay_running_no_extension(self, mcp, mock_relay_client):
        """Test status when relay is running but no extension connected."""
        mock_relay_client["check_connection"].return_value = {
            "status": "ok",
            "websocket_connections": 0,
        }

        with patch(
            "gobbler_relay.client.check_connection",
            mock_relay_client["check_connection"],
        ):
            tool = mcp._tool_manager._tools["browser_check_connection"]
            result = await tool.fn()

        assert "no browser extension connected" in result
        assert "Install the Gobbler browser extension" in result

    @pytest.mark.asyncio
    async def test_relay_not_running(self, mcp, mock_relay_client):
        """Test status when relay server is not running."""
        mock_relay_client["check_connection"].return_value = {
            "status": "error",
            "message": "Relay not running",
        }

        with patch(
            "gobbler_relay.client.check_connection",
            mock_relay_client["check_connection"],
        ):
            tool = mcp._tool_manager._tools["browser_check_connection"]
            result = await tool.fn()

        assert "Relay server is not running" in result

    @pytest.mark.asyncio
    async def test_connection_error(self, mcp):
        """Test handling of connection errors."""
        with patch(
            "gobbler_relay.client.check_connection",
            AsyncMock(side_effect=Exception("Connection refused")),
        ):
            tool = mcp._tool_manager._tools["browser_check_connection"]
            result = await tool.fn()

        assert "Failed to check browser connection" in result
        assert "Connection refused" in result


class TestBrowserNavigateToUrl:
    """Tests for browser_navigate_to_url tool."""

    @pytest.mark.asyncio
    async def test_successful_navigation(self, mcp, mock_relay_client):
        """Test successful URL navigation."""
        mock_relay_client["send_command"].return_value = {"success": True}

        with patch(
            "gobbler_relay.client.send_command",
            mock_relay_client["send_command"],
        ):
            tool = mcp._tool_manager._tools["browser_navigate_to_url"]
            result = await tool.fn(url="https://example.com", wait_for_load=True)

        assert "Successfully navigated to: https://example.com" in result
        mock_relay_client["send_command"].assert_called_once_with(
            command="navigate",
            params={"url": "https://example.com", "wait_for_load": True},
            timeout=60.0,
        )

    @pytest.mark.asyncio
    async def test_navigation_http_url(self, mcp, mock_relay_client):
        """Test navigation with http:// URL."""
        mock_relay_client["send_command"].return_value = {"success": True}

        with patch(
            "gobbler_relay.client.send_command",
            mock_relay_client["send_command"],
        ):
            tool = mcp._tool_manager._tools["browser_navigate_to_url"]
            result = await tool.fn(url="http://example.com")

        assert "Successfully navigated to: http://example.com" in result

    @pytest.mark.asyncio
    async def test_invalid_url_no_protocol(self, mcp):
        """Test navigation with URL missing protocol."""
        tool = mcp._tool_manager._tools["browser_navigate_to_url"]
        result = await tool.fn(url="example.com")

        assert "Error: URL must start with http:// or https://" in result

    @pytest.mark.asyncio
    async def test_invalid_url_wrong_protocol(self, mcp):
        """Test navigation with invalid protocol."""
        tool = mcp._tool_manager._tools["browser_navigate_to_url"]
        result = await tool.fn(url="ftp://example.com")

        assert "Error: URL must start with http:// or https://" in result

    @pytest.mark.asyncio
    async def test_navigation_failure(self, mcp, mock_relay_client):
        """Test handling of navigation failure."""
        mock_relay_client["send_command"].return_value = {
            "success": False,
            "error": "Tab not found",
        }

        with patch(
            "gobbler_relay.client.send_command",
            mock_relay_client["send_command"],
        ):
            tool = mcp._tool_manager._tools["browser_navigate_to_url"]
            result = await tool.fn(url="https://example.com")

        assert "Failed to navigate: Tab not found" in result

    @pytest.mark.asyncio
    async def test_navigation_runtime_error(self, mcp):
        """Test handling of RuntimeError (no extension connected)."""
        with patch(
            "gobbler_relay.client.send_command",
            AsyncMock(side_effect=RuntimeError("No extension connected")),
        ):
            tool = mcp._tool_manager._tools["browser_navigate_to_url"]
            result = await tool.fn(url="https://example.com")

        assert "No extension connected" in result

    @pytest.mark.asyncio
    async def test_navigation_wait_for_load_false(self, mcp, mock_relay_client):
        """Test navigation without waiting for load."""
        mock_relay_client["send_command"].return_value = {"success": True}

        with patch(
            "gobbler_relay.client.send_command",
            mock_relay_client["send_command"],
        ):
            tool = mcp._tool_manager._tools["browser_navigate_to_url"]
            result = await tool.fn(url="https://example.com", wait_for_load=False)

        mock_relay_client["send_command"].assert_called_once_with(
            command="navigate",
            params={"url": "https://example.com", "wait_for_load": False},
            timeout=60.0,
        )


class TestBrowserExecuteScript:
    """Tests for browser_execute_script tool."""

    @pytest.mark.asyncio
    async def test_execute_script_returns_string(self, mcp, mock_relay_client):
        """Test script execution returning a string."""
        mock_relay_client["execute_script"].return_value = {
            "success": True,
            "result": "Test Page Title",
        }

        with patch(
            "gobbler_relay.client.execute_script",
            mock_relay_client["execute_script"],
        ):
            tool = mcp._tool_manager._tools["browser_execute_script"]
            result = await tool.fn(script="document.title")

        assert result == "Test Page Title"

    @pytest.mark.asyncio
    async def test_execute_script_returns_object(self, mcp, mock_relay_client):
        """Test script execution returning an object."""
        mock_relay_client["execute_script"].return_value = {
            "success": True,
            "result": {"key": "value", "count": 42},
        }

        with patch(
            "gobbler_relay.client.execute_script",
            mock_relay_client["execute_script"],
        ):
            tool = mcp._tool_manager._tools["browser_execute_script"]
            result = await tool.fn(script="({key: 'value', count: 42})")

        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["count"] == 42

    @pytest.mark.asyncio
    async def test_execute_script_returns_null(self, mcp, mock_relay_client):
        """Test script execution returning null."""
        mock_relay_client["execute_script"].return_value = {
            "success": True,
            "result": None,
        }

        with patch(
            "gobbler_relay.client.execute_script",
            mock_relay_client["execute_script"],
        ):
            tool = mcp._tool_manager._tools["browser_execute_script"]
            result = await tool.fn(script="void 0")

        assert result == "null"

    @pytest.mark.asyncio
    async def test_execute_script_timeout_validation_too_low(self, mcp):
        """Test timeout validation rejects values below minimum."""
        tool = mcp._tool_manager._tools["browser_execute_script"]
        result = await tool.fn(script="test", timeout=0)

        assert f"timeout must be between {MIN_SCRIPT_TIMEOUT} and {MAX_SCRIPT_TIMEOUT}" in result

    @pytest.mark.asyncio
    async def test_execute_script_timeout_validation_too_high(self, mcp):
        """Test timeout validation rejects values above maximum."""
        tool = mcp._tool_manager._tools["browser_execute_script"]
        result = await tool.fn(script="test", timeout=200)

        assert f"timeout must be between {MIN_SCRIPT_TIMEOUT} and {MAX_SCRIPT_TIMEOUT}" in result

    @pytest.mark.asyncio
    async def test_execute_script_failure(self, mcp, mock_relay_client):
        """Test handling of script execution failure."""
        mock_relay_client["execute_script"].return_value = {
            "success": False,
            "error": "ReferenceError: foo is not defined",
        }

        with patch(
            "gobbler_relay.client.execute_script",
            mock_relay_client["execute_script"],
        ):
            tool = mcp._tool_manager._tools["browser_execute_script"]
            result = await tool.fn(script="foo.bar()")

        assert "Script execution failed" in result
        assert "ReferenceError" in result

    @pytest.mark.asyncio
    async def test_execute_script_custom_timeout(self, mcp, mock_relay_client):
        """Test script execution with custom timeout."""
        mock_relay_client["execute_script"].return_value = {
            "success": True,
            "result": "done",
        }

        with patch(
            "gobbler_relay.client.execute_script",
            mock_relay_client["execute_script"],
        ):
            tool = mcp._tool_manager._tools["browser_execute_script"]
            await tool.fn(script="longOperation()", timeout=60)

        mock_relay_client["execute_script"].assert_called_once_with(
            script="longOperation()",
            timeout=60.0,
        )


class TestBrowserListTabs:
    """Tests for browser_list_tabs tool."""

    @pytest.mark.asyncio
    async def test_list_tabs_with_results(self, mcp, mock_relay_client):
        """Test listing tabs with results."""
        mock_relay_client["list_tabs"].return_value = {
            "success": True,
            "tabs": [
                {
                    "tabId": 123,
                    "title": "Google",
                    "url": "https://google.com",
                    "isActive": True,
                },
                {
                    "tabId": 456,
                    "title": "GitHub",
                    "url": "https://github.com",
                    "isActive": False,
                },
            ],
        }

        with patch(
            "gobbler_relay.client.list_tabs",
            mock_relay_client["list_tabs"],
        ):
            tool = mcp._tool_manager._tools["browser_list_tabs"]
            result = await tool.fn()

        assert "Found 2 tab(s)" in result
        assert "[123] Google (active)" in result
        assert "[456] GitHub" in result
        assert "https://google.com" in result
        assert "https://github.com" in result

    @pytest.mark.asyncio
    async def test_list_tabs_empty(self, mcp, mock_relay_client):
        """Test listing tabs with no results."""
        mock_relay_client["list_tabs"].return_value = {
            "success": True,
            "tabs": [],
        }

        with patch(
            "gobbler_relay.client.list_tabs",
            mock_relay_client["list_tabs"],
        ):
            tool = mcp._tool_manager._tools["browser_list_tabs"]
            result = await tool.fn()

        assert "No tabs in Gobbler group" in result

    @pytest.mark.asyncio
    async def test_list_tabs_with_filter(self, mcp, mock_relay_client):
        """Test listing tabs with notebooklm filter."""
        mock_relay_client["list_tabs"].return_value = {
            "success": True,
            "tabs": [
                {
                    "tabId": 789,
                    "title": "NotebookLM - My Notebook",
                    "url": "https://notebooklm.google.com/notebook/abc123",
                    "isActive": True,
                },
            ],
        }

        with patch(
            "gobbler_relay.client.list_tabs",
            mock_relay_client["list_tabs"],
        ):
            tool = mcp._tool_manager._tools["browser_list_tabs"]
            result = await tool.fn(filter="notebooklm")

        mock_relay_client["list_tabs"].assert_called_once_with(filter_type="notebooklm")
        assert "NotebookLM" in result

    @pytest.mark.asyncio
    async def test_list_tabs_failure(self, mcp, mock_relay_client):
        """Test handling of list tabs failure."""
        mock_relay_client["list_tabs"].return_value = {
            "success": False,
            "error": "Extension not responding",
        }

        with patch(
            "gobbler_relay.client.list_tabs",
            mock_relay_client["list_tabs"],
        ):
            tool = mcp._tool_manager._tools["browser_list_tabs"]
            result = await tool.fn()

        assert "Failed to list tabs" in result
        assert "Extension not responding" in result


class TestBrowserExecuteScriptInTab:
    """Tests for browser_execute_script_in_tab tool."""

    @pytest.mark.asyncio
    async def test_execute_script_in_tab_success(self, mcp, mock_relay_client):
        """Test successful script execution in specific tab."""
        mock_relay_client["execute_script_in_tab"].return_value = {
            "success": True,
            "result": "Tab Title",
            "tabId": 123,
        }

        with patch(
            "gobbler_relay.client.execute_script_in_tab",
            mock_relay_client["execute_script_in_tab"],
        ):
            tool = mcp._tool_manager._tools["browser_execute_script_in_tab"]
            result = await tool.fn(tab_id=123, script="document.title")

        assert result == "Tab Title"
        mock_relay_client["execute_script_in_tab"].assert_called_once_with(
            tab_id=123,
            script="document.title",
            timeout=float(DEFAULT_SCRIPT_TIMEOUT),
        )

    @pytest.mark.asyncio
    async def test_execute_script_in_tab_returns_dict(self, mcp, mock_relay_client):
        """Test script execution in tab returning dict."""
        mock_relay_client["execute_script_in_tab"].return_value = {
            "success": True,
            "result": {"items": ["a", "b", "c"]},
            "tabId": 456,
        }

        with patch(
            "gobbler_relay.client.execute_script_in_tab",
            mock_relay_client["execute_script_in_tab"],
        ):
            tool = mcp._tool_manager._tools["browser_execute_script_in_tab"]
            result = await tool.fn(tab_id=456, script="getData()")

        parsed = json.loads(result)
        assert parsed["items"] == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_execute_script_in_tab_null_result(self, mcp, mock_relay_client):
        """Test script execution in tab with null result."""
        mock_relay_client["execute_script_in_tab"].return_value = {
            "success": True,
            "result": None,
            "tabId": 123,
        }

        with patch(
            "gobbler_relay.client.execute_script_in_tab",
            mock_relay_client["execute_script_in_tab"],
        ):
            tool = mcp._tool_manager._tools["browser_execute_script_in_tab"]
            result = await tool.fn(tab_id=123, script="void 0")

        assert "Script executed successfully in tab 123" in result
        assert "no return value" in result

    @pytest.mark.asyncio
    async def test_execute_script_in_tab_timeout_clamped(self, mcp, mock_relay_client):
        """Test that timeout is clamped to valid range."""
        mock_relay_client["execute_script_in_tab"].return_value = {
            "success": True,
            "result": "done",
            "tabId": 123,
        }

        with patch(
            "gobbler_relay.client.execute_script_in_tab",
            mock_relay_client["execute_script_in_tab"],
        ):
            tool = mcp._tool_manager._tools["browser_execute_script_in_tab"]
            # Test with timeout above max
            await tool.fn(tab_id=123, script="test", timeout=999)

        # Should be clamped to MAX_SCRIPT_TIMEOUT
        mock_relay_client["execute_script_in_tab"].assert_called_once_with(
            tab_id=123,
            script="test",
            timeout=float(MAX_SCRIPT_TIMEOUT),
        )

    @pytest.mark.asyncio
    async def test_execute_script_in_tab_failure(self, mcp, mock_relay_client):
        """Test handling of script execution failure in tab."""
        mock_relay_client["execute_script_in_tab"].return_value = {
            "success": False,
            "error": "Tab 999 not found in Gobbler group",
        }

        with patch(
            "gobbler_relay.client.execute_script_in_tab",
            mock_relay_client["execute_script_in_tab"],
        ):
            tool = mcp._tool_manager._tools["browser_execute_script_in_tab"]
            result = await tool.fn(tab_id=999, script="test")

        assert "Script execution failed" in result
        assert "Tab 999 not found" in result


class TestBrowserExtractCurrentPage:
    """Tests for browser_extract_current_page tool."""

    @pytest.mark.asyncio
    async def test_extract_page_full(self, mcp, mock_relay_client):
        """Test extracting full page content."""
        mock_relay_client["extract_page"].return_value = {
            "success": True,
            "markdown": "---\ntitle: Test Page\n---\n\n# Test Content\n\nParagraph here.",
        }

        with patch(
            "gobbler_relay.client.extract_page",
            mock_relay_client["extract_page"],
        ):
            tool = mcp._tool_manager._tools["browser_extract_current_page"]
            result = await tool.fn()

        assert "# Test Content" in result
        assert "Paragraph here" in result
        mock_relay_client["extract_page"].assert_called_once_with(selector=None)

    @pytest.mark.asyncio
    async def test_extract_page_with_selector(self, mcp, mock_relay_client):
        """Test extracting page content with CSS selector."""
        mock_relay_client["extract_page"].return_value = {
            "success": True,
            "markdown": "# Article Title\n\nArticle content only.",
        }

        with patch(
            "gobbler_relay.client.extract_page",
            mock_relay_client["extract_page"],
        ):
            tool = mcp._tool_manager._tools["browser_extract_current_page"]
            result = await tool.fn(selector="article.main")

        assert "Article content only" in result
        mock_relay_client["extract_page"].assert_called_once_with(selector="article.main")

    @pytest.mark.asyncio
    async def test_extract_page_failure(self, mcp, mock_relay_client):
        """Test handling of page extraction failure."""
        mock_relay_client["extract_page"].return_value = {
            "success": False,
            "error": "No active tab found",
        }

        with patch(
            "gobbler_relay.client.extract_page",
            mock_relay_client["extract_page"],
        ):
            tool = mcp._tool_manager._tools["browser_extract_current_page"]
            result = await tool.fn()

        assert "Failed to extract page" in result
        assert "No active tab found" in result

    @pytest.mark.asyncio
    async def test_extract_page_runtime_error(self, mcp):
        """Test handling of RuntimeError during extraction."""
        with patch(
            "gobbler_relay.client.extract_page",
            AsyncMock(side_effect=RuntimeError("Relay disconnected")),
        ):
            tool = mcp._tool_manager._tools["browser_extract_current_page"]
            result = await tool.fn()

        assert "Relay disconnected" in result

    @pytest.mark.asyncio
    async def test_extract_page_general_exception(self, mcp):
        """Test handling of general exceptions during extraction."""
        with patch(
            "gobbler_relay.client.extract_page",
            AsyncMock(side_effect=Exception("Unexpected error")),
        ):
            tool = mcp._tool_manager._tools["browser_extract_current_page"]
            result = await tool.fn()

        assert "Failed to extract page" in result
        assert "Unexpected error" in result

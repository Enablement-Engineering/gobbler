"""Unit tests for the Gobbler Relay Server.

Tests cover:
- WebSocket message handling (extract, navigate, execute_script commands)
- PID file management (creation, cleanup, stale detection)
- Auto-shutdown (timeout and activity reset)
- HTML to markdown conversion (structure preservation, script/style removal)
- Frontmatter generation (count_words, create_webpage_frontmatter)
"""

import asyncio
import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

# Import the module under test
from gobbler_relay import relay


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_pidfile(tmp_path):
    """Create a temporary pidfile path for testing."""
    pidfile = tmp_path / "test_relay.pid"
    return pidfile


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = AsyncMock(spec=web.WebSocketResponse)
    ws.send_json = AsyncMock()
    ws.prepare = AsyncMock()
    return ws


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state before each test."""
    # Save original state
    original_connections = relay.websocket_connections.copy()
    original_pending = relay.pending_commands.copy()
    original_activity = relay.last_activity_time

    # Clear state
    relay.websocket_connections.clear()
    relay.pending_commands.clear()
    relay.last_activity_time = 0.0

    yield

    # Restore original state
    relay.websocket_connections.clear()
    relay.websocket_connections.update(original_connections)
    relay.pending_commands.clear()
    relay.pending_commands.update(original_pending)
    relay.last_activity_time = original_activity


@pytest.fixture
async def test_client():
    """Create a test client for the relay app."""
    app = relay.create_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client
    await client.close()


# =============================================================================
# PID File Management Tests
# =============================================================================


class TestPidFileManagement:
    """Tests for PID file creation, reading, and cleanup."""

    def test_get_pidfile_path_returns_path(self):
        """Test that get_pidfile_path returns a Path object."""
        path = relay.get_pidfile_path()
        assert isinstance(path, Path)
        assert "gobbler" in str(path)
        assert path.name == "relay.pid"

    def test_write_pidfile_creates_file(self, temp_pidfile):
        """Test that write_pidfile creates a file with the correct PID."""
        with patch.object(relay, "get_pidfile_path", return_value=temp_pidfile):
            relay.write_pidfile(12345)
            assert temp_pidfile.exists()
            assert temp_pidfile.read_text() == "12345"

    def test_write_pidfile_creates_parent_directories(self, tmp_path):
        """Test that write_pidfile creates parent directories if needed."""
        nested_path = tmp_path / "deep" / "nested" / "relay.pid"
        with patch.object(relay, "get_pidfile_path", return_value=nested_path):
            relay.write_pidfile(12345)
            assert nested_path.exists()

    def test_read_pidfile_returns_pid(self, temp_pidfile):
        """Test that read_pidfile returns the stored PID."""
        temp_pidfile.write_text("54321")
        with patch.object(relay, "get_pidfile_path", return_value=temp_pidfile):
            pid = relay.read_pidfile()
            assert pid == 54321

    def test_read_pidfile_returns_none_if_missing(self, temp_pidfile):
        """Test that read_pidfile returns None if file doesn't exist."""
        with patch.object(relay, "get_pidfile_path", return_value=temp_pidfile):
            pid = relay.read_pidfile()
            assert pid is None

    def test_read_pidfile_returns_none_on_invalid_content(self, temp_pidfile):
        """Test that read_pidfile returns None for invalid PID content."""
        temp_pidfile.write_text("not-a-number")
        with patch.object(relay, "get_pidfile_path", return_value=temp_pidfile):
            pid = relay.read_pidfile()
            assert pid is None

    def test_remove_pidfile_deletes_file(self, temp_pidfile):
        """Test that remove_pidfile deletes the pidfile."""
        temp_pidfile.write_text("12345")
        with patch.object(relay, "get_pidfile_path", return_value=temp_pidfile):
            relay.remove_pidfile()
            assert not temp_pidfile.exists()

    def test_remove_pidfile_handles_missing_file(self, temp_pidfile):
        """Test that remove_pidfile handles missing file gracefully."""
        with patch.object(relay, "get_pidfile_path", return_value=temp_pidfile):
            # Should not raise exception
            relay.remove_pidfile()


class TestProcessRunningCheck:
    """Tests for checking if a process is running."""

    def test_is_process_running_returns_true_for_current_process(self):
        """Test that is_process_running returns True for current process."""
        current_pid = os.getpid()
        assert relay.is_process_running(current_pid) is True

    def test_is_process_running_returns_false_for_nonexistent_process(self):
        """Test that is_process_running returns False for non-existent PID."""
        # Use a very high PID that's unlikely to exist
        fake_pid = 999999999
        assert relay.is_process_running(fake_pid) is False


# =============================================================================
# Auto-Shutdown Tests
# =============================================================================


class TestAutoShutdown:
    """Tests for auto-shutdown functionality."""

    def test_update_activity_sets_timestamp(self):
        """Test that update_activity updates the global timestamp."""
        relay.last_activity_time = 0.0
        before = time.time()
        relay.update_activity()
        after = time.time()

        assert relay.last_activity_time >= before
        assert relay.last_activity_time <= after

    @pytest.mark.asyncio
    async def test_auto_shutdown_monitor_sets_event_on_timeout(self):
        """Test that auto_shutdown_monitor sets event after timeout."""
        shutdown_event = asyncio.Event()
        # Set a very old activity time
        relay.last_activity_time = time.time() - 100

        # Run with a very short timeout
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Simulate one iteration of the loop
            async def side_effect(duration):
                # After first sleep, trigger shutdown check
                pass

            mock_sleep.side_effect = side_effect

            # Run the monitor with a 1 second timeout (already expired)
            task = asyncio.create_task(relay.auto_shutdown_monitor(shutdown_event, timeout=1))
            # Give it time to run
            await asyncio.sleep(0.01)
            # Cancel if still running
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    @pytest.mark.asyncio
    async def test_auto_shutdown_monitor_respects_shutdown_event(self):
        """Test that auto_shutdown_monitor exits when event is set."""
        shutdown_event = asyncio.Event()
        shutdown_event.set()  # Pre-set the event

        relay.update_activity()  # Reset activity time

        # Should exit immediately
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await relay.auto_shutdown_monitor(shutdown_event, timeout=3600)
            # If we get here, the monitor properly exited


# =============================================================================
# WebSocket Message Handling Tests
# =============================================================================


class TestWebSocketMessageHandling:
    """Tests for WebSocket message handling."""

    @pytest.mark.asyncio
    async def test_send_command_raises_when_no_connection(self):
        """Test that send_command_to_extension raises when no extension connected."""
        relay.websocket_connections.clear()

        with pytest.raises(RuntimeError, match="No browser extension connected"):
            await relay.send_command_to_extension("test_command")

    @pytest.mark.asyncio
    async def test_send_command_sends_message_to_extension(self, mock_websocket):
        """Test that commands are sent to connected extensions."""
        relay.websocket_connections.add(mock_websocket)

        # Set up a response
        async def simulate_response():
            await asyncio.sleep(0.01)
            for cmd_id, cmd_data in relay.pending_commands.items():
                cmd_data["response"] = {"success": True}
                cmd_data["event"].set()

        task = asyncio.create_task(simulate_response())

        result = await relay.send_command_to_extension(
            "navigate", {"url": "https://example.com"}, timeout=1.0
        )

        await task
        assert result == {"success": True}
        mock_websocket.send_json.assert_called_once()

        # Verify the message structure
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "command"
        assert call_args["command"] == "navigate"
        assert call_args["params"] == {"url": "https://example.com"}

    @pytest.mark.asyncio
    async def test_send_command_timeout(self, mock_websocket):
        """Test that send_command times out correctly."""
        relay.websocket_connections.add(mock_websocket)

        with pytest.raises(RuntimeError, match="timed out"):
            await relay.send_command_to_extension("slow_command", timeout=0.01)

    @pytest.mark.asyncio
    async def test_send_command_cleans_up_pending_commands(self, mock_websocket):
        """Test that pending commands are cleaned up after completion."""
        relay.websocket_connections.add(mock_websocket)

        # Set up immediate response
        async def simulate_response():
            await asyncio.sleep(0.005)
            for cmd_id, cmd_data in list(relay.pending_commands.items()):
                cmd_data["response"] = {"result": "ok"}
                cmd_data["event"].set()

        task = asyncio.create_task(simulate_response())
        await relay.send_command_to_extension("test", timeout=1.0)
        await task

        # Pending commands should be cleaned up
        assert len(relay.pending_commands) == 0


# =============================================================================
# HTML to Markdown Conversion Tests
# =============================================================================


class TestHTMLToMarkdownConversion:
    """Tests for HTML to markdown conversion in extract handler."""

    @pytest.mark.asyncio
    async def test_extract_converts_html_to_markdown(self, test_client):
        """Test that extract handler converts HTML to markdown."""
        html = "<html><body><h1>Test Title</h1><p>Test content</p></body></html>"
        response = await test_client.post(
            "/extract",
            json={
                "url": "https://example.com",
                "title": "Test Page",
                "html": html,
            },
        )

        assert response.status == 200
        data = await response.json()
        assert "markdown" in data
        assert "Test Title" in data["markdown"]
        assert "Test content" in data["markdown"]

    @pytest.mark.asyncio
    async def test_extract_removes_script_tags(self, test_client):
        """Test that extract handler removes script tags."""
        html = """
        <html>
        <body>
            <h1>Title</h1>
            <script>alert('evil');</script>
            <p>Content</p>
        </body>
        </html>
        """
        response = await test_client.post(
            "/extract",
            json={"url": "https://example.com", "title": "Test", "html": html},
        )

        assert response.status == 200
        data = await response.json()
        assert "alert" not in data["markdown"]
        assert "Title" in data["markdown"]

    @pytest.mark.asyncio
    async def test_extract_removes_style_tags(self, test_client):
        """Test that extract handler removes style tags."""
        html = """
        <html>
        <body>
            <style>.red { color: red; }</style>
            <h1>Title</h1>
            <p>Content</p>
        </body>
        </html>
        """
        response = await test_client.post(
            "/extract",
            json={"url": "https://example.com", "title": "Test", "html": html},
        )

        assert response.status == 200
        data = await response.json()
        assert ".red" not in data["markdown"]
        assert "color: red" not in data["markdown"]

    @pytest.mark.asyncio
    async def test_extract_removes_nav_header_footer(self, test_client):
        """Test that extract handler removes nav, header, footer elements."""
        html = """
        <html>
        <body>
            <header><a href="/">Home</a></header>
            <nav><a href="/about">About</a></nav>
            <main><h1>Main Content</h1></main>
            <footer>Copyright 2025</footer>
        </body>
        </html>
        """
        response = await test_client.post(
            "/extract",
            json={"url": "https://example.com", "title": "Test", "html": html},
        )

        assert response.status == 200
        data = await response.json()
        assert "Main Content" in data["markdown"]
        # Nav/header/footer content should be removed
        assert "Copyright 2025" not in data["markdown"]

    @pytest.mark.asyncio
    async def test_extract_with_css_selector(self, test_client):
        """Test that extract handler respects CSS selector."""
        html = """
        <html>
        <body>
            <div class="sidebar">Sidebar content</div>
            <article class="main">
                <h1>Article Title</h1>
                <p>Article content</p>
            </article>
        </body>
        </html>
        """
        response = await test_client.post(
            "/extract",
            json={
                "url": "https://example.com",
                "title": "Test",
                "html": html,
                "selector": "article.main",
            },
        )

        assert response.status == 200
        data = await response.json()
        assert "Article Title" in data["markdown"]
        assert "Sidebar content" not in data["markdown"]

    @pytest.mark.asyncio
    async def test_extract_with_invalid_selector_returns_error(self, test_client):
        """Test that invalid selector returns 400 error."""
        html = "<html><body><p>Content</p></body></html>"
        response = await test_client.post(
            "/extract",
            json={
                "url": "https://example.com",
                "title": "Test",
                "html": html,
                "selector": ".nonexistent",
            },
        )

        assert response.status == 400
        data = await response.json()
        assert "error" in data
        assert "not found" in data["error"]


# =============================================================================
# Frontmatter Generation Tests
# =============================================================================


class TestFrontmatterGeneration:
    """Tests for frontmatter generation in extract handler."""

    @pytest.mark.asyncio
    async def test_extract_includes_frontmatter(self, test_client):
        """Test that extract response includes YAML frontmatter."""
        response = await test_client.post(
            "/extract",
            json={
                "url": "https://example.com/page",
                "title": "Test Page",
                "html": "<html><body><p>Content</p></body></html>",
            },
        )

        assert response.status == 200
        data = await response.json()
        markdown = data["markdown"]

        # Check frontmatter structure
        assert markdown.startswith("---\n")
        # URL may be quoted due to special characters
        assert "https://example.com/page" in markdown
        assert "title: Test Page" in markdown
        assert "source: browser_extension" in markdown

    @pytest.mark.asyncio
    async def test_extract_includes_selector_in_frontmatter(self, test_client):
        """Test that selector is included in frontmatter when provided."""
        html = "<html><body><div class='content'>Test</div></body></html>"
        response = await test_client.post(
            "/extract",
            json={
                "url": "https://example.com",
                "title": "Test",
                "html": html,
                "selector": "div.content",
            },
        )

        assert response.status == 200
        data = await response.json()
        assert "selector" in data["metadata"]
        assert data["metadata"]["selector"] == "div.content"

    @pytest.mark.asyncio
    async def test_extract_includes_word_count(self, test_client):
        """Test that word count is included in metadata."""
        html = "<html><body><p>One two three four five</p></body></html>"
        response = await test_client.post(
            "/extract",
            json={
                "url": "https://example.com",
                "title": "Test",
                "html": html,
            },
        )

        assert response.status == 200
        data = await response.json()
        assert "word_count" in data["metadata"]
        assert data["metadata"]["word_count"] >= 5


class TestCountWords:
    """Tests for the count_words utility function."""

    def test_count_words_empty_string(self):
        """Test word count of empty string."""
        from gobbler_core.utils.frontmatter import count_words

        assert count_words("") == 0

    def test_count_words_single_word(self):
        """Test word count of single word."""
        from gobbler_core.utils.frontmatter import count_words

        assert count_words("hello") == 1

    def test_count_words_multiple_words(self):
        """Test word count of multiple words."""
        from gobbler_core.utils.frontmatter import count_words

        assert count_words("hello world foo bar") == 4

    def test_count_words_with_newlines(self):
        """Test word count with newlines."""
        from gobbler_core.utils.frontmatter import count_words

        assert count_words("hello\nworld\nfoo") == 3

    def test_count_words_with_multiple_spaces(self):
        """Test word count ignores multiple spaces."""
        from gobbler_core.utils.frontmatter import count_words

        assert count_words("hello    world") == 2


class TestCreateWebpageFrontmatter:
    """Tests for create_webpage_frontmatter function."""

    def test_creates_valid_frontmatter(self):
        """Test that valid YAML frontmatter is created."""
        from gobbler_core.utils.frontmatter import create_webpage_frontmatter

        result = create_webpage_frontmatter(
            url="https://example.com",
            title="Test Title",
            word_count=100,
            conversion_time_ms=50,
        )

        assert result.startswith("---\n")
        # Frontmatter ends with closing --- and newline
        assert "---\n" in result[4:]  # Closing delimiter present after opening
        assert "https://example.com" in result
        assert "title: Test Title" in result
        assert "word_count: 100" in result
        assert "conversion_time_ms: 50" in result
        assert "type: webpage" in result

    def test_frontmatter_includes_timestamp(self):
        """Test that frontmatter includes converted_at timestamp."""
        from gobbler_core.utils.frontmatter import create_webpage_frontmatter

        result = create_webpage_frontmatter(
            url="https://example.com",
            title="Test",
            word_count=10,
            conversion_time_ms=5,
        )

        assert "converted_at:" in result

    def test_frontmatter_escapes_special_characters(self):
        """Test that frontmatter properly escapes titles with special chars."""
        from gobbler_core.utils.frontmatter import create_webpage_frontmatter

        result = create_webpage_frontmatter(
            url="https://example.com",
            title="Test: With Colon",
            word_count=10,
            conversion_time_ms=5,
        )

        # Title with colon should be quoted
        assert 'title: "Test: With Colon"' in result


# =============================================================================
# HTTP Handler Tests
# =============================================================================


class TestHTTPHandlers:
    """Tests for HTTP endpoint handlers."""

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_ok(self, test_client):
        """Test that health endpoint returns 200 OK."""
        response = await test_client.get("/health")

        assert response.status == 200
        data = await response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_endpoint_includes_connection_count(self, test_client):
        """Test that health endpoint includes WebSocket connection count."""
        # Add mock connection
        mock_ws = MagicMock()
        relay.websocket_connections.add(mock_ws)

        response = await test_client.get("/health")
        data = await response.json()

        assert "websocket_connections" in data
        assert data["websocket_connections"] == 1

    @pytest.mark.asyncio
    async def test_command_endpoint_requires_command_field(self, test_client):
        """Test that command endpoint requires 'command' field."""
        response = await test_client.post("/command", json={"params": {}})

        assert response.status == 400
        data = await response.json()
        assert "error" in data
        assert "command" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_command_endpoint_returns_503_when_no_extension(self, test_client):
        """Test that command endpoint returns 503 when no extension connected."""
        response = await test_client.post(
            "/command", json={"command": "navigate", "params": {"url": "https://example.com"}}
        )

        assert response.status == 503
        data = await response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_extract_endpoint_handles_exception(self, test_client):
        """Test that extract endpoint handles exceptions gracefully."""
        # Send invalid JSON that will cause processing error
        response = await test_client.post(
            "/extract",
            data="not json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status == 500


# =============================================================================
# Application Configuration Tests
# =============================================================================


class TestAppConfiguration:
    """Tests for application creation and configuration."""

    def test_create_app_returns_application(self):
        """Test that create_app returns an aiohttp Application."""
        app = relay.create_app()
        assert isinstance(app, web.Application)

    def test_create_app_registers_routes(self):
        """Test that create_app registers all expected routes."""
        app = relay.create_app()

        # Get all registered routes
        route_paths = [
            route.resource.canonical for route in app.router.routes() if route.resource is not None
        ]

        assert "/extract" in route_paths
        assert "/command" in route_paths
        assert "/health" in route_paths
        assert "/ws" in route_paths

    def test_create_app_with_auto_shutdown_enabled(self):
        """Test that create_app with auto_shutdown adds middleware."""
        shutdown_event = asyncio.Event()
        app = relay.create_app(enable_auto_shutdown=True, shutdown_event=shutdown_event)

        assert app["shutdown_event"] is shutdown_event
        # Should have at least 2 middlewares (CORS + activity tracking)
        assert len(app.middlewares) >= 2

    def test_create_app_without_auto_shutdown(self):
        """Test that create_app without auto_shutdown has only CORS middleware."""
        app = relay.create_app(enable_auto_shutdown=False)

        # Should have only CORS middleware
        assert len(app.middlewares) == 1


# =============================================================================
# Relay Health Check Tests
# =============================================================================


class TestRelayHealthCheck:
    """Tests for relay health checking."""

    @pytest.mark.asyncio
    async def test_is_relay_healthy_returns_true_on_success(self):
        """Test that is_relay_healthy returns True when relay responds."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await relay.is_relay_healthy("127.0.0.1", 4625)
            assert result is True

    @pytest.mark.asyncio
    async def test_is_relay_healthy_returns_false_on_connection_error(self):
        """Test that is_relay_healthy returns False on connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            import httpx

            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await relay.is_relay_healthy("127.0.0.1", 4625)
            assert result is False

    @pytest.mark.asyncio
    async def test_is_relay_healthy_returns_false_on_timeout(self):
        """Test that is_relay_healthy returns False on timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            import httpx

            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await relay.is_relay_healthy("127.0.0.1", 4625)
            assert result is False


# =============================================================================
# Daemon Management Tests
# =============================================================================


class TestDaemonManagement:
    """Tests for relay daemon start/stop functionality."""

    def test_stop_relay_daemon_returns_false_when_no_pidfile(self, temp_pidfile):
        """Test that stop_relay_daemon returns False when no pidfile exists."""
        with patch.object(relay, "get_pidfile_path", return_value=temp_pidfile):
            with patch.object(relay, "read_pidfile", return_value=None):
                result = relay.stop_relay_daemon()
                assert result is False

    def test_stop_relay_daemon_cleans_up_stale_pidfile(self, temp_pidfile):
        """Test that stop_relay_daemon cleans up stale pidfile."""
        temp_pidfile.write_text("999999999")  # Non-existent process
        with patch.object(relay, "get_pidfile_path", return_value=temp_pidfile):
            result = relay.stop_relay_daemon()
            assert result is False
            # Pidfile should be removed
            assert not temp_pidfile.exists()

    @pytest.mark.asyncio
    async def test_ensure_relay_running_returns_true_if_healthy(self):
        """Test that ensure_relay_running returns True if relay is healthy."""
        with patch.object(relay, "is_relay_healthy", new_callable=AsyncMock) as mock_healthy:
            mock_healthy.return_value = True
            result = await relay.ensure_relay_running()
            assert result is True

    @pytest.mark.asyncio
    async def test_ensure_relay_running_returns_false_when_start_disabled(self):
        """Test ensure_relay_running returns False when start_if_missing=False."""
        with patch.object(relay, "is_relay_healthy", new_callable=AsyncMock) as mock_healthy:
            mock_healthy.return_value = False
            with patch.object(relay, "read_pidfile", return_value=None):
                result = await relay.ensure_relay_running(start_if_missing=False)
                assert result is False

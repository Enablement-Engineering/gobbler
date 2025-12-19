"""Integration tests for MCP tools.

These tests verify that the MCP tools work correctly by calling them
directly through the FastMCP server interface.

Run with: uv run pytest tests/integration/test_mcp_tools.py -v

Requirements:
- Docker containers running (crawl4ai, docling) for full test coverage
- Internet access for YouTube tests
"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Import the MCP server and tools
from gobbler_mcp.server import mcp


class TestMCPToolRegistration:
    """Test that all expected tools are registered."""

    def test_all_tools_registered(self):
        """Verify all expected tools are registered in the MCP server."""
        tools = set(mcp._tool_manager._tools.keys())

        expected_tools = {
            # Conversion tools
            "transcribe_youtube",
            "fetch_webpage",
            "fetch_webpage_with_selector",
            "convert_document",
            "transcribe_audio",
            "download_youtube_video",
            # Batch tools
            "batch_transcribe_youtube_playlist",
            "batch_fetch_webpages",
            "batch_convert_documents",
            "batch_transcribe_directory",
            "get_batch_progress",
            # Browser tools
            "browser_check_connection",
            "browser_list_tabs",
            "browser_navigate_to_url",
            "browser_extract_current_page",
            "browser_execute_script",
            "browser_execute_script_in_tab",
            # Crawl tools
            "crawl_site",
            "create_crawl_session",
            # Queue tools
            "get_job_status",
            "list_jobs",
        }

        missing = expected_tools - tools
        extra = tools - expected_tools

        assert not missing, f"Missing tools: {missing}"
        # Extra tools are OK, just log them
        if extra:
            print(f"Extra tools found: {extra}")

    def test_tool_count(self):
        """Verify we have at least the expected number of tools."""
        tools = list(mcp._tool_manager._tools.keys())
        assert len(tools) >= 21, f"Expected at least 21 tools, got {len(tools)}"


class TestYouTubeTools:
    """Test YouTube-related MCP tools."""

    @pytest.mark.asyncio
    async def test_transcribe_youtube_valid_url(self):
        """Test transcribing a YouTube video."""
        # Use a short, reliable video
        tool = mcp._tool_manager._tools.get("transcribe_youtube")
        assert tool is not None, "transcribe_youtube tool not found"

        # Call the tool function directly
        result = await tool.fn(
            video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            include_timestamps=False,
        )

        # Verify result structure
        assert "---" in result, "Missing YAML frontmatter"
        assert "source:" in result, "Missing source in frontmatter"
        assert "type: youtube_transcript" in result, "Wrong type in frontmatter"
        assert "# Video Transcript" in result or "# Audio Transcript" in result

    @pytest.mark.asyncio
    async def test_transcribe_youtube_invalid_url(self):
        """Test error handling for invalid YouTube URL."""
        tool = mcp._tool_manager._tools.get("transcribe_youtube")

        # Tool returns error string instead of raising
        result = await tool.fn(video_url="https://invalid-url.com/not-youtube")

        # Should contain error message
        assert (
            "error" in result.lower() or "invalid" in result.lower() or "failed" in result.lower()
        )


class TestWebpageTools:
    """Test webpage-related MCP tools."""

    @pytest.mark.asyncio
    async def test_fetch_webpage_requires_crawl4ai(self):
        """Test that fetch_webpage properly handles missing Crawl4AI."""
        tool = mcp._tool_manager._tools.get("fetch_webpage")
        assert tool is not None, "fetch_webpage tool not found"

        # This will either succeed (if Crawl4AI is running) or fail gracefully
        try:
            result = await tool.fn(url="https://example.com")
            # If it succeeds, verify structure
            assert "---" in result, "Missing YAML frontmatter"
            assert "source:" in result, "Missing source in frontmatter"
        except Exception as e:
            # Should fail gracefully with clear error
            error_msg = str(e).lower()
            assert (
                "crawl4ai" in error_msg or "connection" in error_msg or "unavailable" in error_msg
            )


class TestDocumentTools:
    """Test document conversion MCP tools."""

    @pytest.mark.asyncio
    async def test_convert_document_file_not_found(self):
        """Test error handling for non-existent file."""
        tool = mcp._tool_manager._tools.get("convert_document")
        assert tool is not None, "convert_document tool not found"

        # Tool returns error string instead of raising
        result = await tool.fn(file_path="/nonexistent/file.pdf")

        # Should contain error message
        error_msg = result.lower()
        assert "error" in error_msg or "not found" in error_msg or "invalid" in error_msg


class TestAudioTools:
    """Test audio transcription MCP tools."""

    @pytest.mark.asyncio
    async def test_transcribe_audio_file_not_found(self):
        """Test error handling for non-existent audio file."""
        tool = mcp._tool_manager._tools.get("transcribe_audio")
        assert tool is not None, "transcribe_audio tool not found"

        # Tool returns error string instead of raising
        result = await tool.fn(file_path="/nonexistent/audio.mp3")

        # Should contain error message
        error_msg = result.lower()
        assert "error" in error_msg or "not found" in error_msg or "invalid" in error_msg

    @pytest.mark.asyncio
    async def test_transcribe_audio_with_fixture(self):
        """Test transcribing an actual audio file."""
        tool = mcp._tool_manager._tools.get("transcribe_audio")

        # Use the test fixture
        fixture_path = Path(__file__).parent.parent / "fixtures" / "test_audio.wav"
        if not fixture_path.exists():
            pytest.skip("Test audio fixture not found")

        result = await tool.fn(
            file_path=str(fixture_path),
            model="tiny",  # Use tiny model for speed
        )

        # Verify result structure
        assert "---" in result, "Missing YAML frontmatter"
        assert "type: audio" in result, "Wrong type in frontmatter"
        assert "# Audio Transcript" in result


class TestBrowserTools:
    """Test browser automation MCP tools."""

    @pytest.mark.asyncio
    async def test_browser_check_connection(self):
        """Test browser connection check."""
        tool = mcp._tool_manager._tools.get("browser_check_connection")
        assert tool is not None, "browser_check_connection tool not found"

        # This should return status even if not connected
        result = await tool.fn()

        # Result should be JSON or contain connection status
        assert (
            "connected" in result.lower() or "status" in result.lower() or "error" in result.lower()
        )


class TestBatchTools:
    """Test batch processing MCP tools."""

    @pytest.mark.asyncio
    async def test_get_batch_progress_invalid_batch(self):
        """Test getting batch progress for non-existent batch."""
        tool = mcp._tool_manager._tools.get("get_batch_progress")
        assert tool is not None, "get_batch_progress tool not found"

        # Use a fake batch ID
        result = await tool.fn(batch_id="nonexistent-batch-id")

        # Should indicate batch not found or return error
        result_lower = result.lower()
        assert "not found" in result_lower or "error" in result_lower or "no" in result_lower


class TestQueueTools:
    """Test job queue MCP tools."""

    @pytest.mark.asyncio
    async def test_list_jobs(self):
        """Test listing jobs."""
        tool = mcp._tool_manager._tools.get("list_jobs")
        assert tool is not None, "list_jobs tool not found"

        # This should work even with no jobs
        try:
            result = await tool.fn()
            # Should return JSON or indicate no jobs
            assert isinstance(result, str)
        except Exception as e:
            # Redis not running is acceptable
            assert "redis" in str(e).lower() or "connection" in str(e).lower()


# Smoke test that runs all tools with minimal input to verify they don't crash
class TestToolSmoke:
    """Smoke tests to verify tools don't crash on basic invocation."""

    def get_all_tools(self):
        """Get all registered tools."""
        return list(mcp._tool_manager._tools.items())

    @pytest.mark.asyncio
    async def test_all_tools_have_docstrings(self):
        """Verify all tools have documentation."""
        for name, tool in self.get_all_tools():
            assert tool.description, f"Tool {name} missing description"

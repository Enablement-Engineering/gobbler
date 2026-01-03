"""Unit tests for MCP conversion CLI wrappers.

Tests the conversion tools that delegate to CLI commands:
- transcribe_youtube: YouTube video transcript extraction
- fetch_webpage: Basic webpage to markdown conversion
- fetch_webpage_with_selector: Advanced webpage extraction with CSS/XPath selectors
- convert_document: Document conversion (PDF, DOCX, etc.)
- transcribe_audio: Audio/video transcription via Whisper
"""

import subprocess
import sys
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
import httpx

# Mock problematic modules before any gobbler_mcp imports
# Create proper mock structure for rq package
_rq_mock = MagicMock()
_rq_mock.job = MagicMock()
sys.modules["redis"] = MagicMock()
sys.modules["rq"] = _rq_mock
sys.modules["rq.job"] = _rq_mock.job
sys.modules["gobbler_mcp.converters.audio"] = MagicMock()

from fastmcp import FastMCP

from gobbler_mcp.tools.conversion import (
    _run_cli,
    register_tools,
)
from gobbler_mcp.constants import MIN_TIMEOUT, MAX_TIMEOUT


class TestRunCli:
    """Tests for _run_cli helper function."""

    @patch("gobbler_mcp.tools.conversion.subprocess.run")
    def test_successful_execution(self, mock_run):
        """Test successful CLI command execution."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Success output", stderr="")

        success, output = _run_cli(["gobbler", "test"])

        assert success is True
        assert output == "Success output"
        mock_run.assert_called_once_with(
            ["gobbler", "test"],
            capture_output=True,
            text=True,
            timeout=300,  # Default timeout for conversion tools
        )

    @patch("gobbler_mcp.tools.conversion.subprocess.run")
    def test_custom_timeout(self, mock_run):
        """Test custom timeout is passed to subprocess."""
        mock_run.return_value = MagicMock(returncode=0, stdout="output", stderr="")

        _run_cli(["gobbler", "test"], timeout=600)

        mock_run.assert_called_once_with(
            ["gobbler", "test"],
            capture_output=True,
            text=True,
            timeout=600,
        )

    @patch("gobbler_mcp.tools.conversion.subprocess.run")
    def test_nonzero_exit_code_with_stderr(self, mock_run):
        """Test handling of non-zero exit code with stderr message."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error: invalid argument")

        success, output = _run_cli(["gobbler", "test"])

        assert success is False
        assert output == "Error: invalid argument"

    @patch("gobbler_mcp.tools.conversion.subprocess.run")
    def test_nonzero_exit_code_without_stderr(self, mock_run):
        """Test handling of non-zero exit code without stderr."""
        mock_run.return_value = MagicMock(returncode=42, stdout="", stderr="")

        success, output = _run_cli(["gobbler", "test"])

        assert success is False
        assert output == "Command failed with exit code 42"

    @patch("gobbler_mcp.tools.conversion.subprocess.run")
    def test_timeout_handling(self, mock_run):
        """Test timeout is handled gracefully."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gobbler", timeout=60)

        success, output = _run_cli(["gobbler", "test"], timeout=60)

        assert success is False
        assert output == "Command timed out after 60 seconds"

    @patch("gobbler_mcp.tools.conversion.subprocess.run")
    def test_cli_not_found(self, mock_run):
        """Test handling of CLI not found error."""
        mock_run.side_effect = FileNotFoundError()

        success, output = _run_cli(["gobbler", "test"])

        assert success is False
        assert output == "gobbler CLI not found. Ensure it's installed and in PATH."

    @patch("gobbler_mcp.tools.conversion.subprocess.run")
    def test_generic_exception_handling(self, mock_run):
        """Test handling of generic exceptions."""
        mock_run.side_effect = PermissionError("Permission denied")

        success, output = _run_cli(["gobbler", "test"])

        assert success is False
        assert "Failed to run command: Permission denied" in output


@pytest.fixture
def mcp():
    """Create a FastMCP instance with conversion tools registered."""
    mcp_server = FastMCP("test-conversion")
    register_tools(mcp_server)
    return mcp_server


class TestTranscribeYoutube:
    """Tests for transcribe_youtube tool."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_basic_url_transcription(self, mock_run_cli, mcp):
        """Test basic YouTube URL transcription."""
        mock_run_cli.return_value = (
            True,
            "---\ntitle: Test Video\n---\n\nTranscript content here",
        )

        tool = mcp._tool_manager._tools["transcribe_youtube"]
        result = await tool.fn(
            video_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
        )

        assert "Transcript content here" in result
        mock_run_cli.assert_called_once()
        cmd = mock_run_cli.call_args[0][0]
        assert cmd == ["gobbler", "youtube", "https://youtube.com/watch?v=dQw4w9WgXcQ"]

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_with_timestamps_option(self, mock_run_cli, mcp):
        """Test YouTube transcription with timestamps enabled."""
        mock_run_cli.return_value = (
            True,
            "---\ntitle: Test Video\n---\n\n[00:00] Hello\n[00:05] World",
        )

        tool = mcp._tool_manager._tools["transcribe_youtube"]
        result = await tool.fn(
            video_url="https://youtube.com/watch?v=TEST123",
            include_timestamps=True,
        )

        assert "[00:00]" in result
        cmd = mock_run_cli.call_args[0][0]
        assert "--timestamps" in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_with_specific_language(self, mock_run_cli, mcp):
        """Test YouTube transcription with specific language."""
        mock_run_cli.return_value = (
            True,
            "---\ntitle: Video en Español\n---\n\nContenido en español",
        )

        tool = mcp._tool_manager._tools["transcribe_youtube"]
        result = await tool.fn(
            video_url="https://youtube.com/watch?v=SPANISH",
            language="es",
        )

        assert "español" in result
        cmd = mock_run_cli.call_args[0][0]
        assert "--language" in cmd
        assert "es" in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_auto_language_not_in_command(self, mock_run_cli, mcp):
        """Test that 'auto' language doesn't add --language flag."""
        mock_run_cli.return_value = (True, "Transcript content")

        tool = mcp._tool_manager._tools["transcribe_youtube"]
        await tool.fn(
            video_url="https://youtube.com/watch?v=TEST",
            language="auto",  # Default value
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--language" not in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_with_output_file(self, mock_run_cli, mcp, tmp_path):
        """Test YouTube transcription with output file."""
        output_file = str(tmp_path / "transcript.md")
        mock_run_cli.return_value = (True, f"Saved to {output_file}")

        tool = mcp._tool_manager._tools["transcribe_youtube"]
        result = await tool.fn(
            video_url="https://youtube.com/watch?v=TEST",
            output_file=output_file,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "-o" in cmd
        assert output_file in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_cli_error_handling(self, mock_run_cli, mcp):
        """Test handling of CLI errors for YouTube transcription."""
        mock_run_cli.return_value = (False, "Video not found or transcript unavailable")

        tool = mcp._tool_manager._tools["transcribe_youtube"]
        result = await tool.fn(
            video_url="https://youtube.com/watch?v=INVALID",
        )

        assert "Error:" in result
        assert "Video not found or transcript unavailable" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_all_options_combined(self, mock_run_cli, mcp, tmp_path):
        """Test YouTube transcription with all options enabled."""
        output_file = str(tmp_path / "full_transcript.md")
        mock_run_cli.return_value = (True, "Full transcript with all options")

        tool = mcp._tool_manager._tools["transcribe_youtube"]
        await tool.fn(
            video_url="https://youtu.be/SHORT",
            include_timestamps=True,
            language="fr",
            output_file=output_file,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "gobbler" in cmd
        assert "youtube" in cmd
        assert "https://youtu.be/SHORT" in cmd
        assert "--timestamps" in cmd
        assert "--language" in cmd
        assert "fr" in cmd
        assert "-o" in cmd
        assert output_file in cmd


class TestFetchWebpage:
    """Tests for fetch_webpage tool."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_basic_url_fetch(self, mock_run_cli, mcp):
        """Test basic webpage fetch."""
        mock_run_cli.return_value = (
            True,
            "---\ntitle: Example Page\n---\n\n# Example\n\nContent here",
        )

        tool = mcp._tool_manager._tools["fetch_webpage"]
        result = await tool.fn(url="https://example.com")

        assert "Example" in result
        mock_run_cli.assert_called_once()
        cmd = mock_run_cli.call_args[0][0]
        assert "gobbler" in cmd
        assert "webpage" in cmd
        assert "https://example.com" in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_with_custom_timeout(self, mock_run_cli, mcp):
        """Test webpage fetch with custom timeout parameter."""
        mock_run_cli.return_value = (True, "Page content")

        tool = mcp._tool_manager._tools["fetch_webpage"]
        await tool.fn(
            url="https://slow-site.com",
            timeout=60,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--timeout" in cmd
        assert "60" in cmd
        # CLI is called with timeout + 30 buffer
        assert mock_run_cli.call_args[1]["timeout"] == 90

    @pytest.mark.asyncio
    async def test_invalid_timeout_too_low(self, mcp):
        """Test that timeout below MIN_TIMEOUT is rejected."""
        tool = mcp._tool_manager._tools["fetch_webpage"]
        result = await tool.fn(
            url="https://example.com",
            timeout=MIN_TIMEOUT - 1,  # Below minimum
        )

        assert "Error:" in result
        assert f"timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT}" in result

    @pytest.mark.asyncio
    async def test_invalid_timeout_too_high(self, mcp):
        """Test that timeout above MAX_TIMEOUT is rejected."""
        tool = mcp._tool_manager._tools["fetch_webpage"]
        result = await tool.fn(
            url="https://example.com",
            timeout=MAX_TIMEOUT + 1,  # Above maximum
        )

        assert "Error:" in result
        assert f"timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT}" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_include_images_disabled(self, mock_run_cli, mcp):
        """Test webpage fetch with images disabled."""
        mock_run_cli.return_value = (True, "Content without images")

        tool = mcp._tool_manager._tools["fetch_webpage"]
        await tool.fn(
            url="https://example.com",
            include_images=False,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--no-images" in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_include_images_enabled_no_flag(self, mock_run_cli, mcp):
        """Test that --no-images is not added when images are enabled (default)."""
        mock_run_cli.return_value = (True, "Content with images")

        tool = mcp._tool_manager._tools["fetch_webpage"]
        await tool.fn(
            url="https://example.com",
            include_images=True,  # Default
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--no-images" not in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_with_output_file(self, mock_run_cli, mcp, tmp_path):
        """Test webpage fetch with output file."""
        output_file = str(tmp_path / "page.md")
        mock_run_cli.return_value = (True, f"Saved to {output_file}")

        tool = mcp._tool_manager._tools["fetch_webpage"]
        await tool.fn(
            url="https://example.com",
            output_file=output_file,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "-o" in cmd
        assert output_file in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_cli_error_handling(self, mock_run_cli, mcp):
        """Test handling of CLI errors for webpage fetch."""
        mock_run_cli.return_value = (False, "Connection refused")

        tool = mcp._tool_manager._tools["fetch_webpage"]
        result = await tool.fn(url="https://unreachable.example.com")

        assert "Error:" in result
        assert "Connection refused" in result


class TestFetchWebpageWithSelector:
    """Tests for fetch_webpage_with_selector tool."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion.convert_webpage_with_selector")
    async def test_with_css_selector(self, mock_convert, mcp):
        """Test webpage fetch with CSS selector."""
        mock_convert.return_value = (
            "---\ntitle: Article\n---\n\n# Selected Content",
            {"links": None},
        )

        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://example.com/article",
            css_selector="article.main",
        )

        assert "Selected Content" in result
        mock_convert.assert_called_once()
        call_kwargs = mock_convert.call_args[1]
        assert call_kwargs["css_selector"] == "article.main"
        assert call_kwargs["xpath"] is None

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion.convert_webpage_with_selector")
    async def test_with_xpath_selector(self, mock_convert, mcp):
        """Test webpage fetch with XPath selector."""
        mock_convert.return_value = (
            "---\ntitle: Article\n---\n\n# XPath Content",
            {"links": None},
        )

        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://example.com/article",
            xpath="//div[@class='content']",
        )

        assert "XPath Content" in result
        call_kwargs = mock_convert.call_args[1]
        assert call_kwargs["xpath"] == "//div[@class='content']"
        assert call_kwargs["css_selector"] is None

    @pytest.mark.asyncio
    async def test_both_selectors_rejected(self, mcp):
        """Test that specifying both CSS and XPath selectors is rejected."""
        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://example.com",
            css_selector="article",
            xpath="//article",
        )

        assert "Error:" in result
        assert "Cannot specify both css_selector and xpath" in result

    @pytest.mark.asyncio
    async def test_invalid_timeout_too_low(self, mcp):
        """Test that timeout below MIN_TIMEOUT is rejected."""
        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://example.com",
            timeout=MIN_TIMEOUT - 1,
        )

        assert "Error:" in result
        assert f"timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT}" in result

    @pytest.mark.asyncio
    async def test_invalid_timeout_too_high(self, mcp):
        """Test that timeout above MAX_TIMEOUT is rejected."""
        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://example.com",
            timeout=MAX_TIMEOUT + 1,
        )

        assert "Error:" in result
        assert f"timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT}" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion.convert_webpage_with_selector")
    async def test_extract_links_enabled(self, mock_convert, mcp):
        """Test webpage fetch with link extraction."""
        mock_convert.return_value = (
            "---\ntitle: Page\n---\n\nContent",
            {
                "links": {
                    "total_count": 10,
                    "internal_count": 6,
                    "external_count": 4,
                }
            },
        )

        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://example.com",
            extract_links=True,
        )

        assert "Links Extracted" in result
        assert "10 total" in result
        assert "6 internal" in result
        assert "4 external" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion.convert_webpage_with_selector")
    @patch("gobbler_mcp.tools.conversion.validate_output_path")
    @patch("gobbler_mcp.tools.conversion.save_markdown_file")
    async def test_with_output_file(self, mock_save, mock_validate, mock_convert, mcp, tmp_path):
        """Test webpage fetch with selector and output file."""
        output_file = str(tmp_path / "selected.md")
        mock_convert.return_value = ("# Content", {"links": None})
        mock_validate.return_value = None  # No error
        mock_save.return_value = True

        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://example.com",
            css_selector="main",
            output_file=output_file,
        )

        assert f"saved to: {output_file}" in result
        mock_save.assert_called_once_with(output_file, "# Content")

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion.convert_webpage_with_selector")
    @patch("gobbler_mcp.tools.conversion.validate_output_path")
    async def test_invalid_output_path_rejected(self, mock_validate, mock_convert, mcp):
        """Test that invalid output path is rejected."""
        mock_convert.return_value = ("# Content", {"links": None})
        mock_validate.return_value = "Path traversal detected"

        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://example.com",
            output_file="/etc/passwd",
        )

        assert "Error:" in result
        assert "Path traversal detected" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion.convert_webpage_with_selector")
    async def test_connect_error_handling(self, mock_convert, mcp):
        """Test handling of connection errors (Crawl4AI unavailable)."""
        mock_convert.side_effect = httpx.ConnectError("Connection refused")

        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://example.com",
            css_selector="main",
        )

        assert "Crawl4AI service unavailable" in result
        assert "make start-docker" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion.convert_webpage_with_selector")
    async def test_timeout_error_handling(self, mock_convert, mcp):
        """Test handling of timeout errors."""
        mock_convert.side_effect = httpx.TimeoutException("Request timed out")

        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://slow-site.com",
            timeout=30,
        )

        assert "Connection timeout" in result
        assert "30 seconds" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion.convert_webpage_with_selector")
    async def test_http_404_error_handling(self, mock_convert, mcp):
        """Test handling of HTTP 404 errors."""
        response = MagicMock()
        response.status_code = 404
        mock_convert.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=response
        )

        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://example.com/missing",
        )

        assert "HTTP 404" in result
        assert "Page not found" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion.convert_webpage_with_selector")
    async def test_http_500_error_handling(self, mock_convert, mcp):
        """Test handling of HTTP 500 errors."""
        response = MagicMock()
        response.status_code = 500
        mock_convert.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=response
        )

        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://example.com/error",
        )

        assert "HTTP 500" in result
        assert "Server error" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion.convert_webpage_with_selector")
    async def test_runtime_error_not_implemented(self, mock_convert, mcp):
        """Test handling of 'not yet implemented' errors."""
        mock_convert.side_effect = RuntimeError("Feature not yet implemented")

        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://example.com",
        )

        assert "not yet implemented" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion.convert_webpage_with_selector")
    async def test_value_error_handling(self, mock_convert, mcp):
        """Test handling of validation errors."""
        mock_convert.side_effect = ValueError("Invalid selector syntax")

        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        result = await tool.fn(
            url="https://example.com",
            css_selector="[invalid",
        )

        assert "Invalid selector syntax" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion.convert_webpage_with_selector")
    async def test_all_options_passed_to_converter(self, mock_convert, mcp):
        """Test that all options are passed to the converter."""
        mock_convert.return_value = ("# Content", {"links": None})

        tool = mcp._tool_manager._tools["fetch_webpage_with_selector"]
        await tool.fn(
            url="https://example.com",
            css_selector="article",
            include_images=False,
            extract_links=True,
            session_id="test-session",
            bypass_cache=True,
            timeout=60,
        )

        call_kwargs = mock_convert.call_args[1]
        assert call_kwargs["url"] == "https://example.com"
        assert call_kwargs["css_selector"] == "article"
        assert call_kwargs["include_images"] is False
        assert call_kwargs["extract_links"] is True
        assert call_kwargs["session_id"] == "test-session"
        assert call_kwargs["bypass_cache"] is True
        assert call_kwargs["timeout"] == 60


class TestConvertDocument:
    """Tests for convert_document tool."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_basic_document_conversion(self, mock_run_cli, mcp, tmp_path):
        """Test basic document conversion."""
        input_file = str(tmp_path / "document.pdf")
        mock_run_cli.return_value = (
            True,
            "---\ntitle: Document\n---\n\n# Heading\n\nDocument content",
        )

        tool = mcp._tool_manager._tools["convert_document"]
        result = await tool.fn(file_path=input_file)

        assert "Document content" in result
        mock_run_cli.assert_called_once()
        cmd = mock_run_cli.call_args[0][0]
        assert "gobbler" in cmd
        assert "document" in cmd
        assert input_file in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_with_ocr_enabled(self, mock_run_cli, mcp, tmp_path):
        """Test document conversion with OCR enabled (default)."""
        input_file = str(tmp_path / "scanned.pdf")
        mock_run_cli.return_value = (True, "OCR-extracted content")

        tool = mcp._tool_manager._tools["convert_document"]
        await tool.fn(
            file_path=input_file,
            enable_ocr=True,  # Default
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--ocr" in cmd
        assert "--no-ocr" not in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_with_ocr_disabled(self, mock_run_cli, mcp, tmp_path):
        """Test document conversion with OCR disabled."""
        input_file = str(tmp_path / "native.pdf")
        mock_run_cli.return_value = (True, "Native text content")

        tool = mcp._tool_manager._tools["convert_document"]
        await tool.fn(
            file_path=input_file,
            enable_ocr=False,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--no-ocr" in cmd
        assert (
            "--ocr" not in cmd or cmd.index("--no-ocr") > cmd.index("--ocr")
            if "--ocr" in cmd
            else True
        )

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_with_output_file(self, mock_run_cli, mcp, tmp_path):
        """Test document conversion with output file."""
        input_file = str(tmp_path / "document.docx")
        output_file = str(tmp_path / "document.md")
        mock_run_cli.return_value = (True, f"Saved to {output_file}")

        tool = mcp._tool_manager._tools["convert_document"]
        await tool.fn(
            file_path=input_file,
            output_file=output_file,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "-o" in cmd
        assert output_file in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_cli_error_handling(self, mock_run_cli, mcp, tmp_path):
        """Test handling of CLI errors for document conversion."""
        input_file = str(tmp_path / "corrupt.pdf")
        mock_run_cli.return_value = (False, "Corrupt or invalid PDF file")

        tool = mcp._tool_manager._tools["convert_document"]
        result = await tool.fn(file_path=input_file)

        assert "Error:" in result
        assert "Corrupt or invalid PDF file" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_long_timeout_for_documents(self, mock_run_cli, mcp, tmp_path):
        """Test that document conversion uses 10 minute timeout."""
        input_file = str(tmp_path / "large.pdf")
        mock_run_cli.return_value = (True, "Converted content")

        tool = mcp._tool_manager._tools["convert_document"]
        await tool.fn(file_path=input_file)

        # Document conversion should use 600 second (10 minute) timeout
        assert mock_run_cli.call_args[1]["timeout"] == 600


class TestTranscribeAudio:
    """Tests for transcribe_audio tool."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_basic_audio_transcription(self, mock_run_cli, mcp, tmp_path):
        """Test basic audio transcription."""
        input_file = str(tmp_path / "audio.mp3")
        mock_run_cli.return_value = (
            True,
            "---\ntitle: Audio Transcription\n---\n\nSpoken words here",
        )

        tool = mcp._tool_manager._tools["transcribe_audio"]
        result = await tool.fn(file_path=input_file)

        assert "Spoken words" in result
        mock_run_cli.assert_called_once()
        cmd = mock_run_cli.call_args[0][0]
        assert "gobbler" in cmd
        assert "audio" in cmd
        assert input_file in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_with_custom_model(self, mock_run_cli, mcp, tmp_path):
        """Test audio transcription with custom model."""
        input_file = str(tmp_path / "high_quality.wav")
        mock_run_cli.return_value = (True, "High quality transcription")

        tool = mcp._tool_manager._tools["transcribe_audio"]
        await tool.fn(
            file_path=input_file,
            model="large",
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--model" in cmd
        assert "large" in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_default_model_not_in_command(self, mock_run_cli, mcp, tmp_path):
        """Test that default model 'small' doesn't add --model flag."""
        input_file = str(tmp_path / "audio.mp3")
        mock_run_cli.return_value = (True, "Transcription")

        tool = mcp._tool_manager._tools["transcribe_audio"]
        await tool.fn(
            file_path=input_file,
            model="small",  # Default
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--model" not in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_with_specific_language(self, mock_run_cli, mcp, tmp_path):
        """Test audio transcription with specific language."""
        input_file = str(tmp_path / "german_audio.mp3")
        mock_run_cli.return_value = (True, "Deutsche Transkription")

        tool = mcp._tool_manager._tools["transcribe_audio"]
        await tool.fn(
            file_path=input_file,
            language="de",
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--language" in cmd
        assert "de" in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_auto_language_not_in_command(self, mock_run_cli, mcp, tmp_path):
        """Test that 'auto' language doesn't add --language flag."""
        input_file = str(tmp_path / "audio.mp3")
        mock_run_cli.return_value = (True, "Auto-detected language")

        tool = mcp._tool_manager._tools["transcribe_audio"]
        await tool.fn(
            file_path=input_file,
            language="auto",  # Default
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--language" not in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_with_output_file(self, mock_run_cli, mcp, tmp_path):
        """Test audio transcription with output file."""
        input_file = str(tmp_path / "audio.mp3")
        output_file = str(tmp_path / "transcript.md")
        mock_run_cli.return_value = (True, f"Saved to {output_file}")

        tool = mcp._tool_manager._tools["transcribe_audio"]
        await tool.fn(
            file_path=input_file,
            output_file=output_file,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "-o" in cmd
        assert output_file in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_cli_error_handling(self, mock_run_cli, mcp, tmp_path):
        """Test handling of CLI errors for audio transcription."""
        input_file = str(tmp_path / "corrupt.mp3")
        mock_run_cli.return_value = (False, "Invalid audio format")

        tool = mcp._tool_manager._tools["transcribe_audio"]
        result = await tool.fn(file_path=input_file)

        assert "Error:" in result
        assert "Invalid audio format" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_long_timeout_for_audio(self, mock_run_cli, mcp, tmp_path):
        """Test that audio transcription uses 30 minute timeout."""
        input_file = str(tmp_path / "long_recording.mp3")
        mock_run_cli.return_value = (True, "Long transcription")

        tool = mcp._tool_manager._tools["transcribe_audio"]
        await tool.fn(file_path=input_file)

        # Audio transcription should use 1800 second (30 minute) timeout
        assert mock_run_cli.call_args[1]["timeout"] == 1800

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_all_options_combined(self, mock_run_cli, mcp, tmp_path):
        """Test audio transcription with all options."""
        input_file = str(tmp_path / "interview.wav")
        output_file = str(tmp_path / "interview.md")
        mock_run_cli.return_value = (True, "Full transcription")

        tool = mcp._tool_manager._tools["transcribe_audio"]
        await tool.fn(
            file_path=input_file,
            model="medium",
            language="ja",
            output_file=output_file,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "gobbler" in cmd
        assert "audio" in cmd
        assert input_file in cmd
        assert "--model" in cmd
        assert "medium" in cmd
        assert "--language" in cmd
        assert "ja" in cmd
        assert "-o" in cmd
        assert output_file in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.conversion._run_cli")
    async def test_various_model_sizes(self, mock_run_cli, mcp, tmp_path):
        """Test audio transcription with different model sizes."""
        input_file = str(tmp_path / "audio.mp3")

        for model in ["tiny", "base", "small", "medium", "large"]:
            mock_run_cli.return_value = (True, f"Transcribed with {model}")
            mock_run_cli.reset_mock()

            tool = mcp._tool_manager._tools["transcribe_audio"]
            await tool.fn(
                file_path=input_file,
                model=model,
            )

            cmd = mock_run_cli.call_args[0][0]
            if model == "small":
                # Default model doesn't add flag
                assert "--model" not in cmd
            else:
                assert "--model" in cmd
                assert model in cmd

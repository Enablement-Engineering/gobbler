"""Unit tests for MCP batch CLI wrappers.

Tests the helper functions and batch tool wrappers that delegate to CLI commands.
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock problematic modules before any gobbler_mcp imports
# Create proper mock structure for rq package
_rq_mock = MagicMock()
_rq_mock.job = MagicMock()
sys.modules["redis"] = MagicMock()
sys.modules["rq"] = _rq_mock
sys.modules["rq.job"] = _rq_mock.job
sys.modules["gobbler_mcp.converters.audio"] = MagicMock()

from fastmcp import FastMCP

from gobbler_mcp.tools.batch import (
    _format_batch_report,
    _parse_json_output,
    _run_cli,
    register_tools,
)


class TestRunCli:
    """Tests for _run_cli helper function."""

    @patch("gobbler_mcp.tools.batch.subprocess.run")
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
            timeout=3600,  # Default timeout
        )

    @patch("gobbler_mcp.tools.batch.subprocess.run")
    def test_custom_timeout(self, mock_run):
        """Test custom timeout is passed to subprocess."""
        mock_run.return_value = MagicMock(returncode=0, stdout="output", stderr="")

        _run_cli(["gobbler", "test"], timeout=7200)

        mock_run.assert_called_once_with(
            ["gobbler", "test"],
            capture_output=True,
            text=True,
            timeout=7200,
        )

    @patch("gobbler_mcp.tools.batch.subprocess.run")
    def test_nonzero_exit_code_with_stderr(self, mock_run):
        """Test handling of non-zero exit code with stderr message."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error: invalid argument")

        success, output = _run_cli(["gobbler", "test"])

        assert success is False
        assert output == "Error: invalid argument"

    @patch("gobbler_mcp.tools.batch.subprocess.run")
    def test_nonzero_exit_code_without_stderr(self, mock_run):
        """Test handling of non-zero exit code without stderr."""
        mock_run.return_value = MagicMock(returncode=42, stdout="", stderr="")

        success, output = _run_cli(["gobbler", "test"])

        assert success is False
        assert output == "Command failed with exit code 42"

    @patch("gobbler_mcp.tools.batch.subprocess.run")
    def test_timeout_handling(self, mock_run):
        """Test timeout is handled gracefully."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gobbler", timeout=60)

        success, output = _run_cli(["gobbler", "test"], timeout=60)

        assert success is False
        assert output == "Command timed out after 60 seconds"

    @patch("gobbler_mcp.tools.batch.subprocess.run")
    def test_cli_not_found(self, mock_run):
        """Test handling of CLI not found error."""
        mock_run.side_effect = FileNotFoundError()

        success, output = _run_cli(["gobbler", "test"])

        assert success is False
        assert output == "gobbler CLI not found. Ensure it's installed and in PATH."

    @patch("gobbler_mcp.tools.batch.subprocess.run")
    def test_generic_exception_handling(self, mock_run):
        """Test handling of generic exceptions."""
        mock_run.side_effect = PermissionError("Permission denied")

        success, output = _run_cli(["gobbler", "test"])

        assert success is False
        assert "Failed to run command: Permission denied" in output


class TestParseJsonOutput:
    """Tests for _parse_json_output helper function."""

    def test_valid_json_parsing(self):
        """Test parsing of valid JSON output."""
        json_str = '{"success": true, "total": 5, "items": [1, 2, 3]}'
        result = _parse_json_output(json_str)

        assert result == {"success": True, "total": 5, "items": [1, 2, 3]}

    def test_complex_json_parsing(self):
        """Test parsing of complex nested JSON."""
        data = {
            "total_items": 10,
            "successful": 8,
            "failed": 2,
            "success_details": [
                {"source": "file1.pdf", "output_file": "file1.md"},
                {"source": "file2.pdf", "output_file": "file2.md"},
            ],
            "failures": [
                {"source": "bad.pdf", "error": "Corrupt file"},
            ],
        }
        json_str = json.dumps(data)
        result = _parse_json_output(json_str)

        assert result == data

    def test_invalid_json_fallback_to_text(self):
        """Test that invalid JSON falls back to text output."""
        text_output = "Processing completed successfully\n5 files converted"
        result = _parse_json_output(text_output)

        assert result == {"output": text_output, "format": "text"}

    def test_partial_json_fallback(self):
        """Test that malformed JSON falls back to text."""
        partial_json = '{"incomplete": true'
        result = _parse_json_output(partial_json)

        assert result == {"output": partial_json, "format": "text"}

    def test_empty_string(self):
        """Test handling of empty string."""
        result = _parse_json_output("")

        assert result == {"output": "", "format": "text"}

    def test_whitespace_only(self):
        """Test handling of whitespace-only output."""
        result = _parse_json_output("   \n\t  ")

        assert result == {"output": "   \n\t  ", "format": "text"}


class TestFormatBatchReport:
    """Tests for _format_batch_report helper function."""

    def test_text_format_passthrough(self):
        """Test that text format is passed through as-is."""
        data = {"format": "text", "output": "Plain text output"}
        result = _format_batch_report(data)

        assert result == "Plain text output"

    def test_basic_structured_report(self):
        """Test basic structured report formatting."""
        data = {
            "total_items": 10,
            "successful": 8,
            "failed": 2,
            "skipped": 0,
            "processing_time_seconds": 45,
            "output_dir": "/tmp/output",
        }
        result = _format_batch_report(data)

        assert "# Batch Operation Summary" in result
        assert "**Total Items:** 10" in result
        assert "**Successful:** 8 (80.0%)" in result
        assert "**Failed:** 2" in result
        assert "**Skipped:** 0" in result
        assert "**Processing Time:** 45s" in result
        assert "All files saved to: /tmp/output" in result

    def test_report_with_minutes(self):
        """Test processing time formatting with minutes."""
        data = {
            "total_items": 100,
            "successful": 100,
            "failed": 0,
            "skipped": 0,
            "processing_time_seconds": 125,  # 2m 5s
        }
        result = _format_batch_report(data)

        assert "**Processing Time:** 2m 5s" in result

    def test_report_completed_with_errors(self):
        """Test status shows errors when failures exist."""
        data = {
            "total_items": 10,
            "successful": 7,
            "failed": 3,
            "skipped": 0,
        }
        result = _format_batch_report(data)

        assert "**Status:** Completed with errors" in result

    def test_report_completed_successfully(self):
        """Test status shows completed when no failures."""
        data = {
            "total_items": 10,
            "successful": 10,
            "failed": 0,
            "skipped": 0,
        }
        result = _format_batch_report(data)

        assert "**Status:** Completed" in result

    def test_report_with_success_details_dict(self):
        """Test report with dict-format success details."""
        data = {
            "total_items": 2,
            "successful": 2,
            "failed": 0,
            "skipped": 0,
            "success_details": [
                {"source": "doc1.pdf", "output_file": "doc1.md"},
                {"source": "doc2.pdf", "output_file": "doc2.md"},
            ],
        }
        result = _format_batch_report(data)

        assert "## Successful Items" in result
        assert "doc1.pdf -> doc1.md" in result
        assert "doc2.pdf -> doc2.md" in result

    def test_report_with_success_details_string(self):
        """Test report with string-format success details."""
        data = {
            "total_items": 2,
            "successful": 2,
            "failed": 0,
            "skipped": 0,
            "success_details": ["item1.md", "item2.md"],
        }
        result = _format_batch_report(data)

        assert "## Successful Items" in result
        assert "1. item1.md" in result
        assert "2. item2.md" in result

    def test_report_truncates_long_lists(self):
        """Test that success details are truncated at 10 items."""
        data = {
            "total_items": 15,
            "successful": 15,
            "failed": 0,
            "skipped": 0,
            "success_details": [
                {"source": f"file{i}.pdf", "output_file": f"file{i}.md"} for i in range(15)
            ],
        }
        result = _format_batch_report(data)

        assert "... and 5 more" in result

    def test_report_with_failures_dict(self):
        """Test report with dict-format failure details."""
        data = {
            "total_items": 3,
            "successful": 1,
            "failed": 2,
            "skipped": 0,
            "failures": [
                {"source": "bad1.pdf", "error": "Corrupt file"},
                {"source": "bad2.pdf", "error": "Access denied"},
            ],
        }
        result = _format_batch_report(data)

        assert "## Failed Items" in result
        assert "bad1.pdf - Corrupt file" in result
        assert "bad2.pdf - Access denied" in result

    def test_report_with_failures_string(self):
        """Test report with string-format failure details."""
        data = {
            "total_items": 2,
            "successful": 0,
            "failed": 2,
            "skipped": 0,
            "failures": ["Failed: file1.pdf", "Failed: file2.pdf"],
        }
        result = _format_batch_report(data)

        assert "## Failed Items" in result
        assert "1. Failed: file1.pdf" in result
        assert "2. Failed: file2.pdf" in result

    def test_report_truncates_failures(self):
        """Test that failure details are truncated at 10 items."""
        data = {
            "total_items": 12,
            "successful": 0,
            "failed": 12,
            "skipped": 0,
            "failures": [{"source": f"bad{i}.pdf", "error": "Error"} for i in range(12)],
        }
        result = _format_batch_report(data)

        assert "... and 2 more" in result

    def test_report_with_alternative_field_names(self):
        """Test report handles alternative JSON field names."""
        data = {
            "total": 5,  # Alternative to total_items
            "success": 4,  # Alternative to successful
            "failed": 1,  # Use 'failed' not 'failures' for count
            "skipped": 0,
            "time": 30,  # Alternative to processing_time_seconds
            "successful_items": [{"file": "a.pdf", "output": "a.md"}],  # Alternative
            "failed_items": [{"file": "b.pdf", "error": "Failed"}],  # Alternative
        }
        result = _format_batch_report(data)

        assert "**Total Items:** 5" in result
        assert "**Successful:** 4" in result
        assert "**Failed:** 1" in result
        assert "**Processing Time:** 30s" in result
        # Check alternative field names for items
        assert "## Successful Items" in result
        assert "a.pdf" in result
        assert "## Failed Items" in result
        assert "b.pdf" in result

    def test_report_zero_items_no_division_error(self):
        """Test that zero total items doesn't cause division by zero."""
        data = {
            "total_items": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
        }
        result = _format_batch_report(data)

        assert "**Successful:** 0 (0.0%)" in result

    def test_report_no_output_dir(self):
        """Test report without output_dir field."""
        data = {
            "total_items": 1,
            "successful": 1,
            "failed": 0,
            "skipped": 0,
        }
        result = _format_batch_report(data)

        assert "## Output Location" not in result


@pytest.fixture
def mcp():
    """Create a FastMCP instance with batch tools registered."""
    mcp_server = FastMCP("test-batch")
    register_tools(mcp_server)
    return mcp_server


class TestBatchTranscribeYoutubePlaylist:
    """Tests for batch_transcribe_youtube_playlist tool."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_successful_playlist_transcription(self, mock_run_cli, mcp, tmp_path):
        """Test successful YouTube playlist transcription."""
        mock_run_cli.return_value = (
            True,
            json.dumps(
                {
                    "total_items": 5,
                    "successful": 5,
                    "failed": 0,
                    "skipped": 0,
                    "processing_time_seconds": 120,
                    "output_dir": str(tmp_path),
                }
            ),
        )

        tool = mcp._tool_manager._tools["batch_transcribe_youtube_playlist"]
        result = await tool.fn(
            playlist_url="https://youtube.com/playlist?list=TEST",
            output_dir=str(tmp_path),
            include_timestamps=False,
            language="en",
            concurrency=3,
        )

        assert "# Batch Operation Summary" in result
        assert "**Successful:** 5" in result
        mock_run_cli.assert_called_once()
        cmd = mock_run_cli.call_args[0][0]
        assert "gobbler" in cmd
        assert "batch" in cmd
        assert "youtube-playlist" in cmd

    @pytest.mark.asyncio
    async def test_relative_output_dir_rejected(self, mcp, tmp_path):
        """Test that relative output directory is rejected."""
        tool = mcp._tool_manager._tools["batch_transcribe_youtube_playlist"]
        result = await tool.fn(
            playlist_url="https://youtube.com/playlist?list=TEST",
            output_dir="relative/path",  # Not absolute
            include_timestamps=False,
            language="en",
            concurrency=3,
        )

        assert "Error: output_dir must be an absolute path" in result

    @pytest.mark.asyncio
    async def test_invalid_concurrency_rejected(self, mcp, tmp_path):
        """Test that invalid concurrency is rejected."""
        tool = mcp._tool_manager._tools["batch_transcribe_youtube_playlist"]
        result = await tool.fn(
            playlist_url="https://youtube.com/playlist?list=TEST",
            output_dir=str(tmp_path),
            include_timestamps=False,
            language="en",
            concurrency=20,  # Exceeds MAX_BATCH_CONCURRENCY_YOUTUBE (10)
        )

        assert "Error: concurrency must be between 1 and 10" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_cli_error_handling(self, mock_run_cli, mcp, tmp_path):
        """Test handling of CLI errors."""
        mock_run_cli.return_value = (False, "Network error: connection refused")

        tool = mcp._tool_manager._tools["batch_transcribe_youtube_playlist"]
        result = await tool.fn(
            playlist_url="https://youtube.com/playlist?list=TEST",
            output_dir=str(tmp_path),
        )

        assert "Error: Network error: connection refused" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_timestamps_flag_included(self, mock_run_cli, mcp, tmp_path):
        """Test that --timestamps flag is included when enabled."""
        mock_run_cli.return_value = (
            True,
            json.dumps(
                {
                    "total_items": 1,
                    "successful": 1,
                    "failed": 0,
                    "skipped": 0,
                }
            ),
        )

        tool = mcp._tool_manager._tools["batch_transcribe_youtube_playlist"]
        await tool.fn(
            playlist_url="https://youtube.com/playlist?list=TEST",
            output_dir=str(tmp_path),
            include_timestamps=True,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--timestamps" in cmd


class TestBatchFetchWebpages:
    """Tests for batch_fetch_webpages tool."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_successful_webpage_fetch(self, mock_run_cli, mcp, tmp_path):
        """Test successful webpage batch fetch."""
        mock_run_cli.return_value = (
            True,
            json.dumps(
                {
                    "total_items": 3,
                    "successful": 3,
                    "failed": 0,
                    "skipped": 0,
                    "processing_time_seconds": 15,
                    "output_dir": str(tmp_path),
                }
            ),
        )

        tool = mcp._tool_manager._tools["batch_fetch_webpages"]
        result = await tool.fn(
            urls=[
                "https://example.com/page1",
                "https://example.com/page2",
                "https://example.com/page3",
            ],
            output_dir=str(tmp_path),
            timeout=30,
            concurrency=5,
            skip_existing=True,
        )

        assert "# Batch Operation Summary" in result
        assert "**Successful:** 3" in result
        mock_run_cli.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_urls_rejected(self, mcp, tmp_path):
        """Test that empty URL list is rejected."""
        tool = mcp._tool_manager._tools["batch_fetch_webpages"]
        result = await tool.fn(
            urls=[],
            output_dir=str(tmp_path),
        )

        assert "Error: urls list cannot be empty" in result

    @pytest.mark.asyncio
    async def test_too_many_urls_rejected(self, mcp, tmp_path):
        """Test that exceeding MAX_BATCH_URLS is rejected."""
        tool = mcp._tool_manager._tools["batch_fetch_webpages"]
        result = await tool.fn(
            urls=[f"https://example.com/page{i}" for i in range(101)],  # 101 > MAX_BATCH_URLS (100)
            output_dir=str(tmp_path),
        )

        assert "Error: Maximum 100 URLs per batch" in result

    @pytest.mark.asyncio
    async def test_invalid_timeout_rejected(self, mcp, tmp_path):
        """Test that invalid timeout is rejected."""
        tool = mcp._tool_manager._tools["batch_fetch_webpages"]
        result = await tool.fn(
            urls=["https://example.com"],
            output_dir=str(tmp_path),
            timeout=200,  # Exceeds MAX_TIMEOUT (120)
        )

        assert "Error: timeout must be between 5 and 120 seconds" in result

    @pytest.mark.asyncio
    async def test_invalid_concurrency_rejected(self, mcp, tmp_path):
        """Test that invalid concurrency is rejected."""
        tool = mcp._tool_manager._tools["batch_fetch_webpages"]
        result = await tool.fn(
            urls=["https://example.com"],
            output_dir=str(tmp_path),
            concurrency=15,  # Exceeds MAX_BATCH_CONCURRENCY_WEBPAGE (10)
        )

        assert "Error: concurrency must be between 1 and 10" in result

    @pytest.mark.asyncio
    async def test_relative_output_dir_rejected(self, mcp, tmp_path):
        """Test that relative output directory is rejected."""
        tool = mcp._tool_manager._tools["batch_fetch_webpages"]
        result = await tool.fn(
            urls=["https://example.com"],
            output_dir="relative/path",
        )

        assert "Error: output_dir must be an absolute path" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_temp_file_cleanup_on_success(self, mock_run_cli, mcp, tmp_path):
        """Test that temp file is cleaned up after successful run."""
        mock_run_cli.return_value = (
            True,
            json.dumps(
                {
                    "total_items": 1,
                    "successful": 1,
                    "failed": 0,
                    "skipped": 0,
                }
            ),
        )

        tool = mcp._tool_manager._tools["batch_fetch_webpages"]
        await tool.fn(
            urls=["https://example.com"],
            output_dir=str(tmp_path),
        )

        # Get the temp file path from the command
        cmd = mock_run_cli.call_args[0][0]
        urls_file_index = cmd.index("webpages") + 1
        urls_file = cmd[urls_file_index]

        # Temp file should be cleaned up
        assert not Path(urls_file).exists()

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_temp_file_cleanup_on_failure(self, mock_run_cli, mcp, tmp_path):
        """Test that temp file is cleaned up even after CLI failure."""
        mock_run_cli.return_value = (False, "CLI failed")

        tool = mcp._tool_manager._tools["batch_fetch_webpages"]
        await tool.fn(
            urls=["https://example.com"],
            output_dir=str(tmp_path),
        )

        # Get the temp file path from the command
        cmd = mock_run_cli.call_args[0][0]
        urls_file_index = cmd.index("webpages") + 1
        urls_file = cmd[urls_file_index]

        # Temp file should be cleaned up even on failure
        assert not Path(urls_file).exists()

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_skip_existing_flag(self, mock_run_cli, mcp, tmp_path):
        """Test that --no-skip-existing flag is included when skip_existing=False."""
        mock_run_cli.return_value = (
            True,
            json.dumps(
                {
                    "total_items": 1,
                    "successful": 1,
                    "failed": 0,
                    "skipped": 0,
                }
            ),
        )

        tool = mcp._tool_manager._tools["batch_fetch_webpages"]
        await tool.fn(
            urls=["https://example.com"],
            output_dir=str(tmp_path),
            skip_existing=False,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--no-skip-existing" in cmd


class TestBatchTranscribeAudio:
    """Tests for batch_transcribe_audio tool."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_successful_audio_transcription(self, mock_run_cli, mcp, tmp_path):
        """Test successful audio batch transcription."""
        # Create the input directory
        input_dir = tmp_path / "audio"
        input_dir.mkdir()

        mock_run_cli.return_value = (
            True,
            json.dumps(
                {
                    "total_items": 3,
                    "successful": 3,
                    "failed": 0,
                    "skipped": 0,
                    "processing_time_seconds": 300,
                    "output_dir": str(tmp_path),
                }
            ),
        )

        tool = mcp._tool_manager._tools["batch_transcribe_audio"]
        result = await tool.fn(
            input_dir=str(input_dir),
            output_dir=str(tmp_path),
            model="small",
            language="auto",
            pattern="*",
            recursive=False,
            concurrency=2,
        )

        assert "# Batch Operation Summary" in result
        assert "**Successful:** 3" in result
        mock_run_cli.assert_called_once()

    @pytest.mark.asyncio
    async def test_relative_input_dir_rejected(self, mcp, tmp_path):
        """Test that relative input directory is rejected."""
        tool = mcp._tool_manager._tools["batch_transcribe_audio"]
        result = await tool.fn(
            input_dir="relative/path",
        )

        assert "Error: input_dir must be an absolute path" in result

    @pytest.mark.asyncio
    async def test_nonexistent_directory_rejected(self, mcp, tmp_path):
        """Test that nonexistent directory is rejected."""
        nonexistent = tmp_path / "nonexistent"
        tool = mcp._tool_manager._tools["batch_transcribe_audio"]
        result = await tool.fn(
            input_dir=str(nonexistent),
        )

        assert "Error: Directory not found" in result

    @pytest.mark.asyncio
    async def test_file_path_rejected(self, mcp, tmp_path):
        """Test that file path (not directory) is rejected."""
        # Create a file instead of directory
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")

        tool = mcp._tool_manager._tools["batch_transcribe_audio"]
        result = await tool.fn(
            input_dir=str(file_path),
        )

        assert "Error: Not a directory" in result

    @pytest.mark.asyncio
    async def test_invalid_concurrency_rejected(self, mcp, tmp_path):
        """Test that invalid concurrency is rejected."""
        # Create input directory
        input_dir = tmp_path / "audio"
        input_dir.mkdir()

        tool = mcp._tool_manager._tools["batch_transcribe_audio"]
        result = await tool.fn(
            input_dir=str(input_dir),
            concurrency=10,  # Exceeds MAX_BATCH_CONCURRENCY_AUDIO (4)
        )

        assert "Error: concurrency must be between 1 and 4" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_optional_parameters_included_in_command(self, mock_run_cli, mcp, tmp_path):
        """Test that optional parameters are included in CLI command."""
        input_dir = tmp_path / "audio"
        input_dir.mkdir()

        mock_run_cli.return_value = (
            True,
            json.dumps(
                {
                    "total_items": 1,
                    "successful": 1,
                    "failed": 0,
                    "skipped": 0,
                }
            ),
        )

        tool = mcp._tool_manager._tools["batch_transcribe_audio"]
        await tool.fn(
            input_dir=str(input_dir),
            output_dir=str(tmp_path),
            model="large",
            language="es",
            pattern="*.mp3",
            recursive=True,
            concurrency=2,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--output" in cmd
        assert "--model" in cmd
        assert "large" in cmd
        assert "--language" in cmd
        assert "es" in cmd
        assert "--recursive" in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_default_values_not_in_command(self, mock_run_cli, mcp, tmp_path):
        """Test that default values don't add extra flags."""
        input_dir = tmp_path / "audio"
        input_dir.mkdir()

        mock_run_cli.return_value = (
            True,
            json.dumps(
                {
                    "total_items": 1,
                    "successful": 1,
                    "failed": 0,
                    "skipped": 0,
                }
            ),
        )

        tool = mcp._tool_manager._tools["batch_transcribe_audio"]
        await tool.fn(
            input_dir=str(input_dir),
            # Use defaults: model="small", language="auto"
        )

        cmd = mock_run_cli.call_args[0][0]
        # Default model="small" should not add --model flag
        assert "--model" not in cmd
        # Default language="auto" should not add --language flag
        assert "--language" not in cmd


class TestBatchConvertDocuments:
    """Tests for batch_convert_documents tool."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_successful_document_conversion(self, mock_run_cli, mcp, tmp_path):
        """Test successful document batch conversion."""
        # Create the input directory
        input_dir = tmp_path / "docs"
        input_dir.mkdir()

        mock_run_cli.return_value = (
            True,
            json.dumps(
                {
                    "total_items": 5,
                    "successful": 5,
                    "failed": 0,
                    "skipped": 0,
                    "processing_time_seconds": 60,
                    "output_dir": str(tmp_path),
                }
            ),
        )

        tool = mcp._tool_manager._tools["batch_convert_documents"]
        result = await tool.fn(
            input_dir=str(input_dir),
            output_dir=str(tmp_path),
            enable_ocr=True,
            pattern="*",
            recursive=False,
            concurrency=3,
        )

        assert "# Batch Operation Summary" in result
        assert "**Successful:** 5" in result
        mock_run_cli.assert_called_once()

    @pytest.mark.asyncio
    async def test_relative_input_dir_rejected(self, mcp, tmp_path):
        """Test that relative input directory is rejected."""
        tool = mcp._tool_manager._tools["batch_convert_documents"]
        result = await tool.fn(
            input_dir="relative/path",
        )

        assert "Error: input_dir must be an absolute path" in result

    @pytest.mark.asyncio
    async def test_nonexistent_directory_rejected(self, mcp, tmp_path):
        """Test that nonexistent directory is rejected."""
        nonexistent = tmp_path / "nonexistent"
        tool = mcp._tool_manager._tools["batch_convert_documents"]
        result = await tool.fn(
            input_dir=str(nonexistent),
        )

        assert "Error: Directory not found" in result

    @pytest.mark.asyncio
    async def test_file_path_rejected(self, mcp, tmp_path):
        """Test that file path (not directory) is rejected."""
        # Create a file instead of directory
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")

        tool = mcp._tool_manager._tools["batch_convert_documents"]
        result = await tool.fn(
            input_dir=str(file_path),
        )

        assert "Error: Not a directory" in result

    @pytest.mark.asyncio
    async def test_invalid_concurrency_rejected(self, mcp, tmp_path):
        """Test that invalid concurrency is rejected."""
        # Create input directory
        input_dir = tmp_path / "docs"
        input_dir.mkdir()

        tool = mcp._tool_manager._tools["batch_convert_documents"]
        result = await tool.fn(
            input_dir=str(input_dir),
            concurrency=10,  # Exceeds MAX_BATCH_CONCURRENCY_DOCUMENT (5)
        )

        assert "Error: concurrency must be between 1 and 5" in result

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_ocr_disabled_flag_included(self, mock_run_cli, mcp, tmp_path):
        """Test that --no-ocr flag is included when OCR is disabled."""
        input_dir = tmp_path / "docs"
        input_dir.mkdir()

        mock_run_cli.return_value = (
            True,
            json.dumps(
                {
                    "total_items": 1,
                    "successful": 1,
                    "failed": 0,
                    "skipped": 0,
                }
            ),
        )

        tool = mcp._tool_manager._tools["batch_convert_documents"]
        await tool.fn(
            input_dir=str(input_dir),
            enable_ocr=False,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--no-ocr" in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_recursive_flag_included(self, mock_run_cli, mcp, tmp_path):
        """Test that --recursive flag is included when recursive is enabled."""
        input_dir = tmp_path / "docs"
        input_dir.mkdir()

        mock_run_cli.return_value = (
            True,
            json.dumps(
                {
                    "total_items": 1,
                    "successful": 1,
                    "failed": 0,
                    "skipped": 0,
                }
            ),
        )

        tool = mcp._tool_manager._tools["batch_convert_documents"]
        await tool.fn(
            input_dir=str(input_dir),
            recursive=True,
        )

        cmd = mock_run_cli.call_args[0][0]
        assert "--recursive" in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_output_dir_optional(self, mock_run_cli, mcp, tmp_path):
        """Test that output_dir is optional (defaults to input_dir)."""
        input_dir = tmp_path / "docs"
        input_dir.mkdir()

        mock_run_cli.return_value = (
            True,
            json.dumps(
                {
                    "total_items": 1,
                    "successful": 1,
                    "failed": 0,
                    "skipped": 0,
                }
            ),
        )

        tool = mcp._tool_manager._tools["batch_convert_documents"]
        await tool.fn(
            input_dir=str(input_dir),
            # No output_dir specified
        )

        cmd = mock_run_cli.call_args[0][0]
        # --output should not be in command when output_dir not specified
        assert "--output" not in cmd

    @pytest.mark.asyncio
    @patch("gobbler_mcp.tools.batch._run_cli")
    async def test_cli_timeout_is_long(self, mock_run_cli, mcp, tmp_path):
        """Test that document conversion uses a long timeout (3 hours)."""
        input_dir = tmp_path / "docs"
        input_dir.mkdir()

        mock_run_cli.return_value = (
            True,
            json.dumps(
                {
                    "total_items": 1,
                    "successful": 1,
                    "failed": 0,
                    "skipped": 0,
                }
            ),
        )

        tool = mcp._tool_manager._tools["batch_convert_documents"]
        await tool.fn(input_dir=str(input_dir))

        # Check the timeout parameter (3 hours = 10800 seconds)
        assert mock_run_cli.call_args[1]["timeout"] == 10800

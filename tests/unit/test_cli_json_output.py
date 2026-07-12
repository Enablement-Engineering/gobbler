"""Unit tests for CLI JSON output functionality."""

from __future__ import annotations

import contextlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

# Import command modules at top level to avoid PLC0415
from gobbler_cli.commands import batch, convert, daemon, jobs
from gobbler_cli.main import app
from gobbler_cli.output import (
    JSON_SCHEMA_VERSION,
    OutputFormat,
    format_json_error,
    format_json_success,
    write_json_result,
    write_output,
)
from gobbler_queue.models import Job, JobStatus, JobSummary, JobType

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def cli_app():
    """Create and configure the CLI app for testing."""
    # Add command groups (may already be registered, but typer handles duplicates)
    with contextlib.suppress(Exception):
        app.add_typer(convert.app, name="convert", help="Convert individual content items")
    with contextlib.suppress(Exception):
        app.add_typer(batch.app, name="batch", help="Batch processing operations")
    with contextlib.suppress(Exception):
        app.add_typer(daemon.app, name="daemon", help="Daemon management")
    with contextlib.suppress(Exception):
        app.add_typer(jobs.app, name="jobs", help="Job management")

    return app


def _plain_cli_output(output: str) -> str:
    """Return CLI output with ANSI escape codes removed for portable assertions."""
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output)


@pytest.fixture
def sample_metadata() -> dict[str, Any]:
    """Return sample metadata for testing."""
    return {
        "title": "Test Video",
        "channel": "Test Channel",
        "duration": 120,
        "language": "en",
        "word_count": 500,
    }


@pytest.fixture
def temp_output_file(tmp_path: Path) -> Path:
    """Create a temporary output file path."""
    return tmp_path / "output.json"


# =============================================================================
# Tests for output.py helper functions
# =============================================================================


class TestFormatJsonSuccess:
    """Tests for format_json_success() function."""

    def test_basic_success_structure(self, sample_metadata: dict[str, Any]) -> None:
        """Test that format_json_success returns correct basic structure."""
        markdown = "# Test Content\n\nThis is test content."

        result = format_json_success(markdown, sample_metadata)

        assert result["success"] is True
        assert result["schema_version"] == JSON_SCHEMA_VERSION
        assert result["markdown"] == markdown
        assert "metadata" in result
        assert result["metadata"]["title"] == "Test Video"
        assert result["metadata"]["channel"] == "Test Channel"

    def test_success_with_source(self, sample_metadata: dict[str, Any]) -> None:
        """Test that source is added to metadata when provided."""
        markdown = "# Test"
        source = "https://youtube.com/watch?v=test123"

        result = format_json_success(markdown, sample_metadata, source=source)

        assert result["success"] is True
        assert result["metadata"]["source"] == source

    def test_success_without_source(self, sample_metadata: dict[str, Any]) -> None:
        """Test that source is not in metadata when not provided."""
        markdown = "# Test"

        result = format_json_success(markdown, sample_metadata)

        assert "source" not in result["metadata"]

    def test_metadata_preserved(self) -> None:
        """Test that all metadata fields are preserved."""
        markdown = "# Test"
        metadata = {
            "title": "My Title",
            "duration": 300,
            "custom_field": "custom_value",
            "nested": {"key": "value"},
        }

        result = format_json_success(markdown, metadata)

        assert result["metadata"]["title"] == "My Title"
        assert result["metadata"]["duration"] == 300
        assert result["metadata"]["custom_field"] == "custom_value"
        assert result["metadata"]["nested"]["key"] == "value"

    def test_empty_metadata(self) -> None:
        """Test handling of empty metadata."""
        result = format_json_success("# Content", {})

        assert result["success"] is True
        assert result["metadata"] == {}

    def test_empty_markdown(self, sample_metadata: dict[str, Any]) -> None:
        """Test handling of empty markdown content."""
        result = format_json_success("", sample_metadata)

        assert result["success"] is True
        assert result["markdown"] == ""


class TestFormatJsonError:
    """Tests for format_json_error() function."""

    def test_basic_error_structure(self) -> None:
        """Test that format_json_error returns correct basic structure."""
        error_msg = "Something went wrong"

        result = format_json_error(error_msg)

        assert result["success"] is False
        assert result["schema_version"] == JSON_SCHEMA_VERSION
        assert result["error"] == error_msg
        assert result["error_code"] == "CONVERSION_ERROR"

    def test_custom_error_code(self) -> None:
        """Test that custom error codes are properly set."""
        result = format_json_error(
            "Video not found",
            error_code="YOUTUBE_CONVERSION_ERROR",
        )

        assert result["error_code"] == "YOUTUBE_CONVERSION_ERROR"

    def test_error_with_source(self) -> None:
        """Test that source is included when provided."""
        source = "https://example.com/video"

        result = format_json_error(
            "Network error",
            error_code="NETWORK_ERROR",
            source=source,
        )

        assert result["source"] == source

    def test_error_without_source(self) -> None:
        """Test that source is not included when not provided."""
        result = format_json_error("Error message")

        assert "source" not in result

    def test_various_error_codes(self) -> None:
        """Test handling of various error code types."""
        error_codes = [
            "YOUTUBE_CONVERSION_ERROR",
            "AUDIO_CONVERSION_ERROR",
            "DOCUMENT_CONVERSION_ERROR",
            "WEBPAGE_CONVERSION_ERROR",
            "BATCH_PROCESSING_ERROR",
        ]

        for code in error_codes:
            result = format_json_error("Error", error_code=code)
            assert result["error_code"] == code


class TestWriteJsonResult:
    """Tests for write_json_result() function."""

    def test_write_to_stdout(self, capsys) -> None:
        """Test that write_json_result writes to stdout when no path given."""
        data = {"success": True, "markdown": "# Test"}

        write_json_result(data)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert output["success"] is True
        assert output["markdown"] == "# Test"

    def test_write_to_file(self, temp_output_file: Path) -> None:
        """Test that write_json_result writes to file correctly."""
        data = {"success": True, "data": "test"}

        write_json_result(data, temp_output_file)

        assert temp_output_file.exists()
        content = json.loads(temp_output_file.read_text())
        assert content["success"] is True
        assert content["data"] == "test"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that parent directories are created if they don't exist."""
        nested_path = tmp_path / "nested" / "dir" / "output.json"
        data = {"key": "value"}

        write_json_result(data, nested_path)

        assert nested_path.exists()
        assert json.loads(nested_path.read_text())["key"] == "value"

    def test_json_formatting_with_indent(self, temp_output_file: Path) -> None:
        """Test that JSON is formatted with proper indentation."""
        data = {"nested": {"key": "value"}}

        write_json_result(data, temp_output_file)

        content = temp_output_file.read_text()
        # Check that it's formatted (has newlines and indentation)
        assert "\n" in content
        assert "  " in content  # 2-space indent

    def test_unicode_handling(self, temp_output_file: Path) -> None:
        """Test that Unicode characters are preserved."""
        data = {"title": "Test with unicode: \u00e9\u00e8\u00ea"}

        write_json_result(data, temp_output_file)

        content = temp_output_file.read_text(encoding="utf-8")
        loaded = json.loads(content)
        assert loaded["title"] == "Test with unicode: \u00e9\u00e8\u00ea"

    def test_stdout_ends_with_newline(self, capsys) -> None:
        """Test that stdout output ends with newline."""
        write_json_result({"test": True})

        captured = capsys.readouterr()
        assert captured.out.endswith("\n")


class TestWriteOutput:
    """Tests for write_output() function."""

    def test_write_to_stdout(self, capsys) -> None:
        """Test that write_output writes content to stdout."""
        content = "# Test Markdown"

        write_output(content)

        captured = capsys.readouterr()
        assert "# Test Markdown" in captured.out

    def test_write_to_file(self, tmp_path: Path) -> None:
        """Test that write_output writes to file."""
        output_path = tmp_path / "test.md"
        content = "# Test Content"

        write_output(content, output_path)

        assert output_path.exists()
        assert output_path.read_text() == content

    def test_adds_newline_if_missing(self, capsys) -> None:
        """Test that a newline is added if content doesn't end with one."""
        content = "No newline at end"

        write_output(content)

        captured = capsys.readouterr()
        assert captured.out.endswith("\n")


# =============================================================================
# Tests for jobs command JSON output
# =============================================================================


class TestJobsJsonOutput:
    """Tests that job status commands provide parseable JSON for scripts."""

    def test_jobs_list_json_stdout_is_payload_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Test jobs list JSON output contains summaries and no status preamble."""
        created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        summary = JobSummary(
            id="job-1",
            job_type=JobType.WEBPAGE,
            status=JobStatus.FAILED,
            progress=40,
            progress_message="Fetching",
            created_at=created_at,
            error="Connection refused",
        )
        manager = MagicMock()
        manager.list_jobs.return_value = [summary]
        monkeypatch.setattr(jobs, "JobManager", lambda: manager)
        monkeypatch.setattr(jobs, "is_worker_running", lambda: True)
        monkeypatch.setattr(jobs, "get_worker_pid", lambda: 321)

        result = runner.invoke(
            cli_app,
            ["jobs", "list", "--status", "failed", "--limit", "5", "--json"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["schema_version"] == JSON_SCHEMA_VERSION
        assert payload["success"] is True
        assert payload["worker"] == {"running": True, "pid": 321}
        assert payload["filters"] == {"status": "failed", "limit": 5}
        assert payload["count"] == 1
        assert payload["jobs"][0]["id"] == "job-1"
        assert payload["jobs"][0]["error"] == "Connection refused"
        assert "Worker:" not in result.output
        manager.list_jobs.assert_called_once_with(status=JobStatus.FAILED, limit=5)

    def test_jobs_get_json_stdout_is_payload_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Test jobs get JSON output contains the full job detail."""
        job = Job(
            id="job-2",
            job_type=JobType.AUDIO,
            status=JobStatus.COMPLETED,
            command="gobbler audio sample.mp3",
            progress=100,
            progress_message="Done",
            result={"stdout": "converted", "return_code": 0},
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            started_at=datetime(2025, 1, 1, 12, 0, 1, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 12, 0, 3, tzinfo=UTC),
        )
        manager = MagicMock()
        manager.get_job.return_value = job
        monkeypatch.setattr(jobs, "JobManager", lambda: manager)

        result = runner.invoke(cli_app, ["jobs", "get", "job-2", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["schema_version"] == JSON_SCHEMA_VERSION
        assert payload["success"] is True
        assert payload["job"]["id"] == "job-2"
        assert payload["job"]["status"] == "completed"
        assert payload["job"]["result"] == {"stdout": "converted", "return_code": 0}
        assert "Job Details" not in result.output
        manager.get_job.assert_called_once_with("job-2")

    def test_jobs_get_json_not_found_outputs_json_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Test jobs get JSON mode keeps not-found errors parseable."""
        manager = MagicMock()
        manager.get_job.return_value = None
        monkeypatch.setattr(jobs, "JobManager", lambda: manager)

        result = runner.invoke(cli_app, ["jobs", "get", "missing-job", "--json"])

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["schema_version"] == JSON_SCHEMA_VERSION
        assert payload["success"] is False
        assert payload["error_code"] == "JOB_NOT_FOUND"
        assert "suggestion" not in payload
        assert "missing-job" in payload["error"]
        assert "Error:" not in result.output

    def test_jobs_count_json_stdout_is_payload_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Test jobs count JSON output contains counts and worker state."""
        counts = {
            "pending": 1,
            "running": 2,
            "completed": 3,
            "failed": 4,
            "cancelled": 5,
            "total": 15,
        }
        manager = MagicMock()
        manager.count_jobs.return_value = counts
        monkeypatch.setattr(jobs, "JobManager", lambda: manager)
        monkeypatch.setattr(jobs, "is_worker_running", lambda: False)

        result = runner.invoke(cli_app, ["jobs", "count", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["schema_version"] == JSON_SCHEMA_VERSION
        assert payload["success"] is True
        assert payload["worker"] == {"running": False, "pid": None}
        assert payload["counts"] == counts
        assert "Job Counts" not in result.output
        manager.count_jobs.assert_called_once_with()


# =============================================================================
# Tests for CLI error handling (file not found cases - using convert subcommand)
# =============================================================================


class TestAudioJsonFileNotFound:
    """Tests for audio command JSON output with file not found."""

    def test_audio_json_file_not_found(
        self,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Test audio conversion error when file doesn't exist."""
        result = runner.invoke(
            cli_app,
            ["convert", "audio", "/nonexistent/file.mp3", "--format", "json"],
        )

        output = json.loads(result.output.strip())

        assert output["success"] is False
        assert output["schema_version"] == JSON_SCHEMA_VERSION
        assert output["error_code"] == "AUDIO_CONVERSION_ERROR"
        assert "not found" in output["error"].lower() or "File not found" in output["error"]


class TestDocumentJsonFileNotFound:
    """Tests for document command JSON output with file not found."""

    def test_document_json_file_not_found(
        self,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Test document conversion error when file doesn't exist."""
        result = runner.invoke(
            cli_app,
            ["convert", "document", "/nonexistent/file.pdf", "--format", "json"],
        )

        output = json.loads(result.output.strip())

        assert output["success"] is False
        assert output["schema_version"] == JSON_SCHEMA_VERSION
        assert output["error_code"] == "DOCUMENT_CONVERSION_ERROR"


class TestConvertJsonErrorStdoutPurity:
    """Tests that conversion JSON error paths emit parseable JSON to stdout."""

    def test_youtube_json_missing_url_outputs_json(
        self,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Test missing YouTube URL in JSON mode returns a JSON error object."""
        result = runner.invoke(cli_app, ["convert", "youtube", "--format", "json"], input="")

        payload = json.loads(result.output)

        assert result.exit_code == 1
        assert payload["schema_version"] == JSON_SCHEMA_VERSION
        assert payload["success"] is False
        assert payload["error_code"] == "YOUTUBE_MISSING_URL"

    def test_webpage_json_missing_url_outputs_json(
        self,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Test missing webpage URL in JSON mode returns a JSON error object."""
        result = runner.invoke(cli_app, ["convert", "webpage", "--format", "json"], input="")

        payload = json.loads(result.output)

        assert result.exit_code == 1
        assert payload["schema_version"] == JSON_SCHEMA_VERSION
        assert payload["success"] is False
        assert payload["error_code"] == "WEBPAGE_MISSING_URL"

    def test_audio_json_unknown_provider_outputs_json(
        self,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test unknown audio provider in JSON mode returns a clean JSON error."""
        audio_file = tmp_path / "meeting.mp3"
        audio_file.write_bytes(b"audio")

        result = runner.invoke(
            cli_app,
            [
                "convert",
                "audio",
                str(audio_file),
                "--provider",
                "missing-provider",
                "--format",
                "json",
            ],
        )

        payload = json.loads(result.output)

        assert result.exit_code == 1
        assert payload["schema_version"] == JSON_SCHEMA_VERSION
        assert payload["success"] is False
        assert payload["error_code"] == "AUDIO_PROVIDER_NOT_FOUND"
        assert "missing-provider" in payload["error"]


class TestConvertJsonStdoutPurity:
    """Tests that conversion JSON modes emit only parseable JSON to stdout."""

    def test_youtube_json_success_stdout_is_payload_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Test YouTube JSON success output is not prefixed by progress text."""

        async def fake_convert_youtube_to_markdown(
            *_args: object,
            **_kwargs: object,
        ) -> tuple[str, dict[str, str]]:
            return "# Transcript", {"title": "Video"}

        monkeypatch.setattr(
            "gobbler_core.converters.youtube.convert_youtube_to_markdown",
            fake_convert_youtube_to_markdown,
        )

        result = runner.invoke(
            cli_app,
            [
                "convert",
                "youtube",
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["success"] is True
        assert payload["schema_version"] == JSON_SCHEMA_VERSION
        assert payload["markdown"] == "# Transcript"
        assert "Converting YouTube video" not in result.output

    def test_audio_json_success_stdout_is_payload_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test audio JSON success output is not prefixed by progress text."""
        audio_file = tmp_path / "meeting.mp3"
        audio_file.write_bytes(b"audio")

        async def fake_convert_audio_to_markdown(
            *_args: object,
            **_kwargs: object,
        ) -> tuple[str, dict[str, str]]:
            return "# Transcript", {"title": "Meeting"}

        monkeypatch.setattr(
            "gobbler_core.converters.audio.convert_audio_to_markdown",
            fake_convert_audio_to_markdown,
        )

        result = runner.invoke(
            cli_app,
            ["convert", "audio", str(audio_file), "--format", "json"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["success"] is True
        assert payload["schema_version"] == JSON_SCHEMA_VERSION
        assert payload["metadata"]["source"] == str(audio_file)
        assert "Transcribing audio file" not in result.output

    def test_document_json_success_stdout_is_payload_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test document JSON success output is not prefixed by progress text."""
        document_file = tmp_path / "paper.pdf"
        document_file.write_bytes(b"%PDF-1.4\n")

        async def fake_convert_document_to_markdown(
            *_args: object,
            **_kwargs: object,
        ) -> tuple[str, dict[str, str]]:
            return "# Paper", {"title": "Paper"}

        def fake_get_default_provider(**_kwargs: object) -> object:
            return object()

        monkeypatch.setattr(
            "gobbler_core.providers.document.get_default_provider",
            fake_get_default_provider,
        )
        monkeypatch.setattr(
            "gobbler_core.converters.document.convert_document_to_markdown",
            fake_convert_document_to_markdown,
        )

        result = runner.invoke(
            cli_app,
            ["convert", "document", str(document_file), "--format", "json"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["success"] is True
        assert payload["schema_version"] == JSON_SCHEMA_VERSION
        assert payload["metadata"]["source"] == str(document_file)
        assert "Converting document" not in result.output

    def test_webpage_json_success_stdout_is_payload_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Test webpage JSON success output remains payload-only."""

        async def fake_convert_webpage_to_markdown(
            *_args: object,
            **_kwargs: object,
        ) -> tuple[str, dict[str, str]]:
            return "# Page", {"title": "Page"}

        def fake_get_default_provider(**_kwargs: object) -> object:
            return object()

        monkeypatch.setattr(
            "gobbler_core.providers.webpage.get_default_provider",
            fake_get_default_provider,
        )
        monkeypatch.setattr(
            "gobbler_core.converters.webpage.convert_webpage_to_markdown",
            fake_convert_webpage_to_markdown,
        )

        result = runner.invoke(
            cli_app,
            ["convert", "webpage", "https://example.com", "--format", "json"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["success"] is True
        assert payload["schema_version"] == JSON_SCHEMA_VERSION
        assert payload["metadata"]["source"] == "https://example.com"
        assert "Converting web page" not in result.output

    def test_webpage_json_error_uses_diagnostic_advice(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Webpage JSON errors promote provider diagnostic guidance to the suggestion field."""

        class DiagnosticWebpageError(Exception):
            """Error carrying structured webpage diagnostics."""

            diagnostics: ClassVar[dict[str, str]] = {
                "provider": "crawl4ai",
                "advice": (
                    "A proxy is configured for Crawl4AI via "
                    "https://proxy-user:proxy-pass@proxy.example:8080 retry the "
                    "single-page CLI without the proxy: "
                    "gobbler webpage https://example.com/ --no-proxy."
                ),
                "suggested_command_fragment": "gobbler webpage https://example.com/ --no-proxy",
            }

        async def fake_convert_webpage_to_markdown(*_args: object, **_kwargs: object) -> None:
            message = "Crawl4AI /crawl returned HTTP 500"
            raise DiagnosticWebpageError(message)

        def fake_get_default_provider(**_kwargs: object) -> object:
            return object()

        monkeypatch.setattr(
            "gobbler_core.providers.webpage.get_default_provider",
            fake_get_default_provider,
        )
        monkeypatch.setattr(
            "gobbler_core.converters.webpage.convert_webpage_to_markdown",
            fake_convert_webpage_to_markdown,
        )

        result = runner.invoke(
            cli_app,
            ["convert", "webpage", "https://example.com", "--format", "json"],
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["error_code"] == "WEBPAGE_CONVERSION_ERROR"
        assert "[REDACTED]@proxy.example:8080" in payload["suggestion"]
        assert payload["suggestion"] == payload["diagnostics"]["advice"]
        assert "proxy-pass" not in payload["suggestion"]
        assert "proxy-user" not in payload["suggestion"]
        assert payload["diagnostics"]["suggested_command_fragment"].endswith("--no-proxy")

    def test_webpage_json_error_sanitizes_credential_bearing_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Webpage JSON failure source does not leak userinfo, query values, or fragments."""

        async def fake_convert_webpage_to_markdown(*_args: object, **_kwargs: object) -> None:
            message = "Crawl4AI /crawl returned HTTP 500"
            raise RuntimeError(message)

        def fake_get_default_provider(**_kwargs: object) -> object:
            return object()

        monkeypatch.setattr(
            "gobbler_core.providers.webpage.get_default_provider",
            fake_get_default_provider,
        )
        monkeypatch.setattr(
            "gobbler_core.converters.webpage.convert_webpage_to_markdown",
            fake_convert_webpage_to_markdown,
        )

        result = runner.invoke(
            cli_app,
            [
                "convert",
                "webpage",
                "https://user:pass@example.com/path?token=secret&x=public#frag",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["source"] == "https://[REDACTED]@example.com/path"
        payload_text = json.dumps(payload)
        assert "user:pass" not in payload_text
        assert "token=secret" not in payload_text
        assert "x=public" not in payload_text
        assert "frag" not in payload_text

    def test_webpage_json_error_preserves_normal_public_source_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Normal webpage JSON failure sources keep a useful public URL path."""

        async def fake_convert_webpage_to_markdown(*_args: object, **_kwargs: object) -> None:
            message = "Crawl4AI /crawl returned HTTP 500"
            raise RuntimeError(message)

        def fake_get_default_provider(**_kwargs: object) -> object:
            return object()

        monkeypatch.setattr(
            "gobbler_core.providers.webpage.get_default_provider",
            fake_get_default_provider,
        )
        monkeypatch.setattr(
            "gobbler_core.converters.webpage.convert_webpage_to_markdown",
            fake_convert_webpage_to_markdown,
        )

        result = runner.invoke(
            cli_app,
            ["convert", "webpage", "https://example.com/path", "--format", "json"],
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["source"] == "https://example.com/path"

    def test_webpage_invalid_url_json_sanitizes_credential_bearing_source(
        self,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Invalid webpage URL JSON failures sanitize raw user input source values."""
        result = runner.invoke(
            cli_app,
            [
                "convert",
                "webpage",
                "https://user:pass@example.com:99999/path?token=secret&x=public#frag",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["error_code"] == "WEBPAGE_INVALID_URL"
        assert payload["source"] == "https://[REDACTED]@example.com:99999/path"
        payload_text = json.dumps(payload)
        assert "user:pass" not in payload_text
        assert "token=secret" not in payload_text
        assert "x=public" not in payload_text
        assert "#frag" not in payload_text

    @pytest.mark.parametrize(
        ("url", "expected_source"),
        [
            ("example.com/path?token=secret&x=public#frag", "example.com/path"),
            (
                "//user:pass@example.com/path?token=secret&x=public#frag",
                "//[REDACTED]@example.com/path",
            ),
            (
                "https://user:pass@[::1/path?token=secret&x=public#frag",
                "https://[REDACTED]@[::1/path",
            ),
            (
                "https://user:pass@example.com\uff0fpath?token=secret&x=public#frag",
                "https://[REDACTED]@example.com\uff0fpath",
            ),
        ],
    )
    def test_webpage_invalid_url_json_sanitizes_non_absolute_source(
        self,
        runner: CliRunner,
        cli_app,
        url: str,
        expected_source: str,
    ) -> None:
        """Invalid non-absolute webpage URL sources drop query, fragment, and userinfo."""
        result = runner.invoke(
            cli_app,
            ["convert", "webpage", url, "--format", "json"],
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["error_code"] == "WEBPAGE_INVALID_URL"
        assert payload["source"] == expected_source
        payload_text = json.dumps(payload)
        assert "user:pass" not in payload_text
        assert "token=secret" not in payload_text
        assert "x=public" not in payload_text
        assert "#frag" not in payload_text

    def test_webpage_provider_not_found_json_sanitizes_credential_bearing_source(
        self,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Provider lookup failures sanitize webpage JSON source values."""
        result = runner.invoke(
            cli_app,
            [
                "convert",
                "webpage",
                "https://user:pass@example.com/path?token=secret&x=public#frag",
                "--provider",
                "missing-provider",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["error_code"] == "WEBPAGE_PROVIDER_NOT_FOUND"
        assert payload["source"] == "https://[REDACTED]@example.com/path"
        payload_text = json.dumps(payload)
        assert "user:pass" not in payload_text
        assert "token=secret" not in payload_text
        assert "x=public" not in payload_text
        assert "#frag" not in payload_text

    def test_webpage_json_error_keeps_generic_suggestion_without_diagnostic_advice(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Webpage JSON errors without provider advice keep the knowledge-base suggestion."""

        async def fake_convert_webpage_to_markdown(*_args: object, **_kwargs: object) -> None:
            message = "Crawl4AI connection failed"
            raise RuntimeError(message)

        def fake_get_default_provider(**_kwargs: object) -> object:
            return object()

        monkeypatch.setattr(
            "gobbler_core.providers.webpage.get_default_provider",
            fake_get_default_provider,
        )
        monkeypatch.setattr(
            "gobbler_core.converters.webpage.convert_webpage_to_markdown",
            fake_convert_webpage_to_markdown,
        )

        result = runner.invoke(
            cli_app,
            ["convert", "webpage", "https://example.com", "--format", "json"],
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["error_code"] == "WEBPAGE_CONVERSION_ERROR"
        assert payload["suggestion"] == "cd ~/Projects/gobbler && docker compose up -d crawl4ai"
        assert "diagnostics" not in payload


# =============================================================================
# Tests for batch commands with JSON output
# =============================================================================


class TestBatchWebpagesJsonNoUrls:
    """Tests for batch webpages with empty URLs file."""

    def test_batch_webpages_no_urls_json(
        self,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test batch webpages with empty URLs file returns JSON error."""
        # Create empty URLs file
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("# Just a comment\n\n")
        output_dir = tmp_path / "output"

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
            ],
        )

        output = json.loads(result.output.strip())
        assert output["schema_version"] == JSON_SCHEMA_VERSION
        assert output["success"] is False
        assert output["error_code"] == "NO_URLS_FOUND"


class TestBatchWebpagesUrlValidation:
    """Tests for batch webpage local URL validation."""

    @pytest.mark.parametrize(
        "invalid_url",
        [
            "not-a-url",
            "example.com/page",
            "ftp://example.com/file",
            "http://exa mple.com",
            " https://example.com/leading-space",
            "https://example.com/control\x00char",
            "https://example.com:99999",
        ],
    )
    @patch("gobbler_core.converters.webpage.convert_webpage_to_markdown")
    def test_batch_webpages_dry_run_rejects_invalid_urls_before_planning(
        self,
        mock_convert: MagicMock,
        invalid_url: str,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Dry-run rejects malformed/unsupported webpage URLs before output planning."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text(f"{invalid_url}\n")
        output_dir = tmp_path / "output"

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
                "--dry-run",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        assert result.exit_code == 1
        assert len(lines) == 2
        assert lines[0]["schema_version"] == JSON_SCHEMA_VERSION
        assert lines[0]["type"] == "invalid_input"
        assert lines[0]["success"] is False
        assert lines[0]["error_code"] == "WEBPAGE_INVALID_URL"
        assert lines[0]["url"] == invalid_url
        assert "Invalid webpage URL" in lines[0]["error"]
        assert lines[0]["suggestion"] == "Provide a URL like https://example.com."
        assert "output" not in lines[0]
        assert not output_dir.exists()
        mock_convert.assert_not_called()

    @patch("gobbler_core.converters.webpage.convert_webpage_to_markdown")
    def test_batch_webpages_execution_rejects_invalid_urls_before_dispatch(
        self,
        mock_convert: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Execution rejects invalid webpage URLs before provider dispatch."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com/ok\nftp://example.com/file\n")
        output_dir = tmp_path / "output"

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        assert result.exit_code == 1
        assert len(lines) == 2
        assert lines[0]["type"] == "invalid_input"
        assert lines[0]["error_code"] == "WEBPAGE_INVALID_URL"
        assert lines[0]["url"] == "ftp://example.com/file"
        assert not output_dir.exists()
        mock_convert.assert_not_called()

    @patch("gobbler_queue.manager.JobManager")
    def test_batch_webpages_queue_rejects_invalid_urls_without_job(
        self,
        mock_job_manager: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Queued batch webpage submission validates URLs before creating a job."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com/ok\nftp://example.com/file\n")
        output_dir = tmp_path / "output"

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--queue",
                "--json",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        assert result.exit_code == 1
        assert len(lines) == 2
        assert lines[0]["type"] == "invalid_input"
        assert lines[0]["error_code"] == "WEBPAGE_INVALID_URL"
        assert lines[0]["url"] == "ftp://example.com/file"
        mock_job_manager.assert_not_called()

    def test_batch_webpages_dry_run_accepts_http_and_https_urls(
        self,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Valid http:// and https:// entries keep existing dry-run behavior."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("http://example.com/one\nhttps://example.com/two\n")
        output_dir = tmp_path / "output"

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
                "--dry-run",
            ],
        )

        payload = json.loads(result.output.strip())
        assert result.exit_code == 0
        assert payload["type"] == "dry_run"
        assert payload["total_urls"] == 2
        assert payload["would_process"] == 2
        assert [item["url"] for item in payload["urls"]] == [
            "http://example.com/one",
            "https://example.com/two",
        ]


class TestBatchYoutubePlaylistUrlValidation:
    """Tests for batch YouTube playlist local URL validation."""

    @pytest.mark.parametrize(
        "playlist_url",
        [
            "not-a-url",
            "ftp://youtube.com/playlist?list=PL123",
            "https://example.com/playlist?list=PL123",
            "https://youtube.com/playlist?list=",
        ],
    )
    @patch("yt_dlp.YoutubeDL")
    def test_batch_youtube_playlist_json_invalid_url_rejected_before_extractor(
        self,
        mock_youtube_dl: MagicMock,
        playlist_url: str,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """JSON mode rejects malformed playlist URLs before invoking yt-dlp."""
        output_dir = tmp_path / "output"

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "youtube-playlist",
                playlist_url,
                "--output",
                str(output_dir),
                "--json",
                "--dry-run",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        assert result.exit_code == 1
        assert [line["type"] for line in lines] == ["invalid_input", "batch_complete"]
        assert lines[0]["error_code"] == "YOUTUBE_PLAYLIST_INVALID_URL"
        assert lines[0]["url"] == playlist_url
        assert lines[1]["summary"]["outcomes"]["invalid_input"] == 1
        assert not output_dir.exists()
        mock_youtube_dl.assert_not_called()

    @patch("yt_dlp.YoutubeDL")
    def test_batch_youtube_playlist_human_invalid_url_has_guidance(
        self,
        mock_youtube_dl: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Human output rejects malformed playlist URLs with URL-format guidance."""
        result = runner.invoke(
            cli_app,
            [
                "batch",
                "youtube-playlist",
                "youtube.com/playlist?list=PL123",
                "--output",
                str(tmp_path / "output"),
                "--dry-run",
            ],
        )

        plain_output = _plain_cli_output(result.output)
        assert result.exit_code == 1
        assert "Invalid YouTube playlist URL" in plain_output
        assert "absolute http:// or https://" in plain_output
        assert "https://youtube.com/playlist?list=PLAYLIST_ID" in plain_output
        assert "Dry Run Preview" not in plain_output
        mock_youtube_dl.assert_not_called()

    @pytest.mark.parametrize(
        "playlist_url",
        [
            "http://youtube.com/playlist?list=PL123",
            "https://www.youtube.com/playlist?list=PL123",
            "https://m.youtube.com/playlist?list=PL123",
            "https://music.youtube.com/playlist?list=PL123",
        ],
    )
    @patch("yt_dlp.YoutubeDL")
    def test_batch_youtube_playlist_valid_urls_dispatch_to_extractor(
        self,
        mock_youtube_dl: MagicMock,
        playlist_url: str,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Valid http:// and https:// playlist URLs continue to yt-dlp extraction."""
        ydl = mock_youtube_dl.return_value.__enter__.return_value
        ydl.extract_info.return_value = {
            "entries": [
                {
                    "id": "dQw4w9WgXcQ",
                    "title": "Example video",
                }
            ]
        }

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "youtube-playlist",
                playlist_url,
                "--output",
                str(tmp_path / "output"),
                "--json",
                "--dry-run",
            ],
        )

        payload = json.loads(result.output.strip())
        assert result.exit_code == 0
        assert payload["type"] == "dry_run"
        assert payload["total_videos"] == 1
        ydl.extract_info.assert_called_once_with(playlist_url, download=False)


class TestBatchDirectoryJsonError:
    """Tests for batch directory with nonexistent input."""

    def test_batch_directory_json_error(
        self,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test batch directory error with JSON output."""
        output_dir = tmp_path / "output"

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "directory",
                "/nonexistent/input",
                "--output",
                str(output_dir),
                "--json",
            ],
        )

        # Parse JSON lines - the error may be followed by batch_complete
        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        error_line = next((line for line in lines if line.get("success") is False), None)

        assert error_line is not None
        assert error_line["schema_version"] == JSON_SCHEMA_VERSION
        assert error_line["success"] is False
        assert error_line["error_code"] == "DIRECTORY_NOT_FOUND"

    @patch("gobbler_core.converters.audio.convert_audio_to_markdown")
    def test_batch_directory_json_item_failure_exits_nonzero(
        self,
        mock_convert: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test directory JSON batch completion counts failures and exits nonzero."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "meeting.mp3").write_bytes(b"audio")
        output_dir = tmp_path / "output"

        async def mock_async_error(*args, **kwargs):
            msg = "transcription failed"
            raise RuntimeError(msg)

        mock_convert.side_effect = mock_async_error

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "directory",
                str(input_dir),
                "--output",
                str(output_dir),
                "--type",
                "audio",
                "--json",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        complete_msg = next((line for line in lines if line.get("type") == "batch_complete"), None)

        assert result.exit_code == 1
        assert all(line["schema_version"] == JSON_SCHEMA_VERSION for line in lines)
        assert complete_msg is not None
        assert complete_msg["success"] is False
        assert complete_msg["summary"]["total"] == 1
        assert complete_msg["summary"]["successful"] == 0
        assert complete_msg["summary"]["failed"] == 1
        assert complete_msg["summary"]["skipped"] == 0

    def test_directory_output_paths_uses_source_extension_for_same_stem_collisions(
        self,
        tmp_path: Path,
    ) -> None:
        """Same-stem inputs get unique deterministic markdown output names."""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        files = [
            input_dir / "report.pdf",
            input_dir / "report.docx",
            input_dir / "notes.pdf",
        ]

        output_paths = batch._directory_output_paths(list(reversed(files)), output_dir)

        assert output_paths[input_dir / "report.pdf"] == output_dir / "report.pdf.md"
        assert output_paths[input_dir / "report.docx"] == output_dir / "report.docx.md"
        assert output_paths[input_dir / "notes.pdf"] == output_dir / "notes.md"
        assert len(set(output_paths.values())) == len(output_paths)

    def test_directory_output_paths_handles_case_variant_collisions(
        self,
        tmp_path: Path,
    ) -> None:
        """Case-variant stems get distinct names for case-insensitive filesystems."""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        files = [
            input_dir / "Report.pdf",
            input_dir / "report.docx",
        ]

        output_paths = batch._directory_output_paths(files, output_dir)

        assert output_paths[input_dir / "Report.pdf"] == output_dir / "Report.pdf.md"
        assert output_paths[input_dir / "report.docx"] == output_dir / "report.docx.md"
        assert len({path.name.casefold() for path in output_paths.values()}) == len(output_paths)

    def test_batch_directory_dry_run_json_avoids_same_stem_output_collisions(
        self,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Dry-run JSON previews the same collision-safe names used for processing."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "report.pdf").write_bytes(b"pdf")
        (input_dir / "report.docx").write_bytes(b"docx")
        (input_dir / "notes.pdf").write_bytes(b"pdf")
        output_dir = tmp_path / "output"

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "directory",
                str(input_dir),
                "--output",
                str(output_dir),
                "--json",
                "--dry-run",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        dry_run_msg = next((line for line in lines if line.get("type") == "dry_run"), None)

        assert result.exit_code == 0
        assert dry_run_msg is not None

        outputs = {Path(item["output"]).name for item in dry_run_msg["files"]}
        assert dry_run_msg["would_process"] == 3
        assert outputs == {"report.pdf.md", "report.docx.md", "notes.md"}
        assert len(outputs) == len(dry_run_msg["files"])

    def test_batch_directory_dry_run_json_ignores_unknown_files_for_output_collisions(
        self,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Unsupported files do not force renamed outputs for supported inputs."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "report.pdf").write_bytes(b"pdf")
        (input_dir / "report.txt").write_text("sidecar", encoding="utf-8")
        output_dir = tmp_path / "output"

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "directory",
                str(input_dir),
                "--output",
                str(output_dir),
                "--json",
                "--dry-run",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        dry_run_msg = next((line for line in lines if line.get("type") == "dry_run"), None)

        assert result.exit_code == 0
        assert dry_run_msg is not None
        assert {Path(item["output"]).name for item in dry_run_msg["files"]} == {"report.md"}
        assert {Path(item["output"]).name for item in dry_run_msg["skipped"]} == {"report.md"}

    def test_batch_directory_dry_run_json_checks_existing_collision_safe_output(
        self,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Existing-output dry-run skip checks use collision-safe output paths."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "report.pdf").write_bytes(b"pdf")
        (input_dir / "report.docx").write_bytes(b"docx")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "report.pdf.md").write_text("existing", encoding="utf-8")

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "directory",
                str(input_dir),
                "--output",
                str(output_dir),
                "--json",
                "--dry-run",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        dry_run_msg = next((line for line in lines if line.get("type") == "dry_run"), None)

        assert result.exit_code == 0
        assert dry_run_msg is not None

        skipped_outputs = {Path(item["output"]).name for item in dry_run_msg["skipped"]}
        process_outputs = {Path(item["output"]).name for item in dry_run_msg["files"]}
        assert skipped_outputs == {"report.pdf.md"}
        assert process_outputs == {"report.docx.md"}

    @patch("gobbler_core.converters.document.convert_document_to_markdown")
    def test_batch_directory_processing_writes_collision_safe_outputs(
        self,
        mock_convert: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Actual directory processing writes one unique output per same-stem input."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "report.pdf").write_bytes(b"pdf")
        (input_dir / "report.docx").write_bytes(b"docx")
        (input_dir / "report.txt").write_text("sidecar", encoding="utf-8")
        output_dir = tmp_path / "output"

        async def mock_async_convert(path: str, *args, **kwargs):
            return (f"# Converted\n\n{Path(path).name}", {"source": path})

        mock_convert.side_effect = mock_async_convert

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "directory",
                str(input_dir),
                "--output",
                str(output_dir),
                "--json",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        success_outputs = {
            Path(line["output"]).name for line in lines if line.get("type") == "item_success"
        }
        skipped = [line for line in lines if line.get("type") == "item_skipped"]

        assert result.exit_code == 0
        assert success_outputs == {"report.pdf.md", "report.docx.md"}
        assert skipped == [
            {
                "type": "item_skipped",
                "file": str(input_dir / "report.txt"),
                "reason": "unknown_type",
                "schema_version": 1,
            }
        ]
        assert (output_dir / "report.pdf.md").read_text(encoding="utf-8").endswith("report.pdf")
        assert (output_dir / "report.docx.md").read_text(encoding="utf-8").endswith("report.docx")


class TestBatchWebpagesWithMock:
    """Tests for batch webpages with mocked converter."""

    def test_batch_webpages_help_lists_proxy_option(
        self,
        runner: CliRunner,
        cli_app,
    ) -> None:
        """Test that batch webpages exposes the proxy toggle in help output."""
        result = runner.invoke(cli_app, ["batch", "webpages", "--help"])

        assert result.exit_code == 0
        plain_output = _plain_cli_output(result.output)
        assert "--proxy" in plain_output
        assert "--no-proxy" in plain_output

    @patch("gobbler_core.converters.webpage.convert_webpage_to_markdown")
    def test_batch_webpages_defaults_to_proxy_enabled(
        self,
        mock_convert: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test that batch webpages defaults to use_proxy=True."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com\n")
        output_dir = tmp_path / "output"

        async def mock_async_convert(*args, **kwargs):
            return ("# Content", {"title": "Example"})

        mock_convert.side_effect = mock_async_convert

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
            ],
        )

        assert result.exit_code == 0
        assert mock_convert.call_args.kwargs["use_proxy"] is True

    @patch("gobbler_core.converters.webpage.convert_webpage_to_markdown")
    def test_batch_webpages_no_proxy_passes_proxy_disabled(
        self,
        mock_convert: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test that --no-proxy passes use_proxy=False to webpage conversion."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com\n")
        output_dir = tmp_path / "output"

        async def mock_async_convert(*args, **kwargs):
            return ("# Content", {"title": "Example"})

        mock_convert.side_effect = mock_async_convert

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
                "--no-proxy",
            ],
        )

        assert result.exit_code == 0
        assert mock_convert.call_args.kwargs["use_proxy"] is False

    @patch("gobbler_queue.manager.JobManager")
    def test_batch_webpages_queue_preserves_no_proxy(
        self,
        mock_job_manager: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test that queued batch webpage jobs preserve --no-proxy in args and argv."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com\n")
        output_dir = tmp_path / "output"
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_manager = mock_job_manager.return_value
        mock_manager.create_job.return_value = mock_job

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--queue",
                "--no-proxy",
            ],
        )

        assert result.exit_code == 0
        output = _plain_cli_output(result.output)
        assert "Queued batch webpage job: job-123" in output
        assert "Use 'gobbler daemon status' to check progress" in output
        assert "gobbler queue status" not in output
        create_job_kwargs = mock_manager.create_job.call_args.kwargs
        queued_input = Path(create_job_kwargs["args"]["input_file"])
        assert create_job_kwargs["args"]["use_proxy"] is False
        assert queued_input.exists()
        assert queued_input.read_text(encoding="utf-8") == "https://example.com\n"
        assert str(queued_input) in create_job_kwargs["argv"]
        assert "--no-proxy" in create_job_kwargs["argv"]
        assert "--no-proxy" in create_job_kwargs["command"]

    @patch("gobbler_queue.manager.JobManager")
    def test_batch_webpages_queue_json_outputs_job_payload(
        self,
        mock_job_manager: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Queued batch webpage JSON mode emits one parseable job payload."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com/one\nhttps://example.com/two\n")
        output_dir = tmp_path / "output"
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_manager = mock_job_manager.return_value
        mock_manager.create_job.return_value = mock_job

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--queue",
                "--no-proxy",
                "--json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        summary = payload.pop("summary")
        assert summary["outcomes"]["queue_submission"] == 1
        assert payload == {
            "schema_version": JSON_SCHEMA_VERSION,
            "type": "job_queued",
            "success": True,
            "job_id": "job-123",
            "job_type": "batch_webpage",
            "status": "pending",
            "total_urls": 2,
            "options": {
                "concurrency": 3,
                "timeout": 30,
                "selector": None,
                "use_proxy": False,
                "skip_existing": True,
            },
        }
        assert "Queued batch webpage job" not in result.output
        assert str(tmp_path) not in result.output
        mock_manager.create_job.assert_called_once()

    @patch("gobbler_queue.manager.JobManager")
    def test_batch_webpages_queue_json_error_outputs_json_without_path_leak(
        self,
        mock_job_manager: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """JobManager failures in queued JSON mode remain parseable and path-safe."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com\n")
        output_dir = tmp_path / "output"
        private_path = tmp_path / "queue.db"
        mock_manager = mock_job_manager.return_value
        mock_manager.create_job.side_effect = RuntimeError(f"database locked: {private_path}")

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--queue",
                "--json",
            ],
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        summary = payload.pop("summary")
        assert summary["outcomes"]["queue_submission"] == 1
        assert payload == {
            "schema_version": JSON_SCHEMA_VERSION,
            "type": "queue_error",
            "success": False,
            "error_code": "BATCH_WEBPAGE_QUEUE_ERROR",
            "error": "Failed to queue batch webpage job.",
        }
        assert str(tmp_path) not in result.output
        assert "Error:" not in result.output

    @pytest.mark.parametrize(
        ("args", "expected_error_code", "expected_error"),
        [
            (
                ["-"],
                "BATCH_WEBPAGE_QUEUE_REQUIRES_FILE",
                "Queueing batch webpages requires an input file path; stdin is supported inline.",
            ),
            (
                ["missing.txt"],
                "BATCH_WEBPAGE_INPUT_FILE_NOT_FOUND",
                "Input file not found.",
            ),
        ],
    )
    @patch("gobbler_queue.manager.JobManager")
    def test_batch_webpages_queue_json_input_errors_are_json(
        self,
        mock_job_manager: MagicMock,
        args: list[str],
        expected_error_code: str,
        expected_error: str,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Queued batch webpage JSON input errors stay parseable and path-safe."""
        command_args = [
            "batch",
            "webpages",
            *[str(tmp_path / arg) if arg == "missing.txt" else arg for arg in args],
            "--output-dir",
            str(tmp_path / "output"),
            "--queue",
            "--json",
        ]

        result = runner.invoke(cli_app, command_args, input="https://example.com\n")

        assert result.exit_code == 1
        payload = json.loads(result.output)
        summary = payload.pop("summary")
        assert summary["outcomes"]["invalid_input"] == 1
        assert payload == {
            "schema_version": JSON_SCHEMA_VERSION,
            "type": "queue_error",
            "success": False,
            "error_code": expected_error_code,
            "error": expected_error,
        }
        assert str(tmp_path) not in result.output
        assert "Error:" not in result.output
        mock_job_manager.assert_not_called()

    @patch("gobbler_queue.manager.JobManager")
    def test_batch_webpages_queue_json_empty_input_is_json(
        self,
        mock_job_manager: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Queued batch webpage JSON mode reports empty URL files as JSON."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("# comment only\n\n")

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(tmp_path / "output"),
                "--queue",
                "--json",
            ],
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        summary = payload.pop("summary")
        assert summary["outcomes"]["invalid_input"] == 1
        assert payload == {
            "schema_version": JSON_SCHEMA_VERSION,
            "type": "queue_error",
            "success": False,
            "error_code": "NO_URLS_FOUND",
            "error": "No valid URLs found in input",
        }
        assert str(tmp_path) not in result.output
        assert "Error:" not in result.output
        mock_job_manager.assert_not_called()

    def test_batch_webpages_output_paths_preserve_unique_filenames(
        self,
        tmp_path: Path,
    ) -> None:
        """Non-colliding webpage outputs keep their existing sanitized filenames."""
        output_dir = tmp_path / "output"

        output_paths = batch._webpage_output_paths(
            ["https://example.com/page1", "https://example.com/page2"],
            output_dir,
        )

        assert [path.name for path in output_paths] == [
            "example.com_page1.md",
            "example.com_page2.md",
        ]

    def test_batch_webpages_output_paths_suffix_collisions(
        self,
        tmp_path: Path,
    ) -> None:
        """Colliding webpage output names get deterministic unique suffixes."""
        output_dir = tmp_path / "output"

        output_paths = batch._webpage_output_paths(
            [
                "https://example.com",
                "https://example.com",
                "https://www.example.com",
            ],
            output_dir,
        )

        assert [path.name for path in output_paths] == [
            "example.com.md",
            "example.com-2.md",
            "example.com-3.md",
        ]
        assert len({path.name.casefold() for path in output_paths}) == len(output_paths)

    def test_batch_webpages_output_paths_preserve_unique_suffix_like_filenames(
        self,
        tmp_path: Path,
    ) -> None:
        """Duplicate suffixes do not displace non-colliding historical filenames."""
        output_dir = tmp_path / "output"

        output_paths = batch._webpage_output_paths(
            [
                "https://example.com",
                "https://example.com",
                "https://example.com-2",
            ],
            output_dir,
        )

        assert [path.name for path in output_paths] == [
            "example.com.md",
            "example.com-3.md",
            "example.com-2.md",
        ]

    def test_batch_webpages_output_paths_preserve_duplicated_suffix_like_filenames(
        self,
        tmp_path: Path,
    ) -> None:
        """Duplicate base names do not take another duplicated stem's natural name."""
        output_dir = tmp_path / "output"

        output_paths = batch._webpage_output_paths(
            [
                "https://example.com/foo",
                "https://example.com/foo",
                "https://example.com/foo-2",
                "https://example.com/foo-2",
            ],
            output_dir,
        )

        assert [path.name for path in output_paths] == [
            "example.com_foo.md",
            "example.com_foo-3.md",
            "example.com_foo-2.md",
            "example.com_foo-2-2.md",
        ]

    def test_batch_webpages_dry_run_json_avoids_duplicate_url_output_collisions(
        self,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Dry-run JSON previews distinct outputs for duplicate batch webpage URLs."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com\nhttps://example.com\n", encoding="utf-8")
        output_dir = tmp_path / "output"

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
                "--dry-run",
                "--no-proxy",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        dry_run_msg = next((line for line in lines if line.get("type") == "dry_run"), None)

        assert result.exit_code == 0
        assert dry_run_msg is not None
        outputs = [Path(item["output"]).name for item in dry_run_msg["urls"]]
        assert outputs == ["example.com.md", "example.com-2.md"]
        assert len(set(outputs)) == len(outputs)

    def test_batch_webpages_dry_run_text_shows_collision_safe_outputs(
        self,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Text dry-run output previews collision-safe output paths."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com\nhttps://example.com\n", encoding="utf-8")
        output_dir = tmp_path / "output"

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--dry-run",
                "--no-proxy",
            ],
        )

        assert result.exit_code == 0
        compact_output = re.sub(r"\s+", "", result.output)
        assert "example.com.md" in compact_output
        assert "example.com-2.md" in compact_output

    @patch("gobbler_core.converters.webpage.convert_webpage_to_markdown")
    def test_batch_webpages_processing_writes_collision_safe_outputs(
        self,
        mock_convert: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Actual webpage batch processing writes distinct files for colliding URL stems."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com\nhttps://example.com\n", encoding="utf-8")
        output_dir = tmp_path / "output"
        call_count = 0

        async def mock_async_convert(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return (f"# Content {call_count}", {"call": call_count})

        mock_convert.side_effect = mock_async_convert

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
                "--no-proxy",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        success_outputs = [
            Path(line["output"]).name for line in lines if line.get("type") == "item_success"
        ]

        assert result.exit_code == 0
        assert set(success_outputs) == {"example.com.md", "example.com-2.md"}
        assert (output_dir / "example.com.md").read_text(encoding="utf-8") != (
            output_dir / "example.com-2.md"
        ).read_text(encoding="utf-8")

    @patch("gobbler_queue.manager.JobManager")
    def test_batch_webpages_queue_preserves_duplicate_url_order(
        self,
        mock_job_manager: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Queued jobs keep ordered duplicate URLs so workers can reproduce safe paths."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com\nhttps://example.com\n", encoding="utf-8")
        output_dir = tmp_path / "output"
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_manager = mock_job_manager.return_value
        mock_manager.create_job.return_value = mock_job

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--queue",
                "--no-proxy",
            ],
        )

        assert result.exit_code == 0
        create_job_kwargs = mock_manager.create_job.call_args.kwargs
        queued_input = Path(create_job_kwargs["args"]["input_file"])
        assert create_job_kwargs["args"]["urls"] == [
            "https://example.com",
            "https://example.com",
        ]
        assert [Path(output).name for output in create_job_kwargs["args"]["output_paths"]] == [
            "example.com.md",
            "example.com-2.md",
        ]
        assert queued_input.read_text(encoding="utf-8") == (
            "https://example.com\nhttps://example.com\n"
        )
        assert str(queued_input) in create_job_kwargs["argv"]

    @patch("gobbler_core.converters.webpage.convert_webpage_to_markdown")
    def test_batch_webpages_json_lines(
        self,
        mock_convert: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test batch webpages outputs JSON lines."""
        # Create URLs file
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com/page1\nhttps://example.com/page2\n")
        output_dir = tmp_path / "output"

        async def mock_async_convert(*args, **kwargs):
            return (
                "# Page\n\nContent",
                {"title": "Page"},
            )

        mock_convert.side_effect = mock_async_convert

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        assert all(line["schema_version"] == JSON_SCHEMA_VERSION for line in lines)

        # Check for proper JSON line structure
        start_msg = next((line for line in lines if line.get("type") == "batch_start"), None)
        assert start_msg is not None
        assert start_msg["total"] == 2

        complete_msg = next((line for line in lines if line.get("type") == "batch_complete"), None)
        assert complete_msg is not None
        assert complete_msg["success"] is True
        assert complete_msg["summary"]["successful"] == 2
        assert complete_msg["summary"]["failed"] == 0
        assert result.exit_code == 0

    @patch("gobbler_core.converters.webpage.convert_webpage_to_markdown")
    def test_batch_item_success_message(
        self,
        mock_convert: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test that successful items output item_success message."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com\n")
        output_dir = tmp_path / "output"

        async def mock_async_convert(*args, **kwargs):
            return ("# Content", {"title": "Example"})

        mock_convert.side_effect = mock_async_convert

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        success_msg = next((line for line in lines if line.get("type") == "item_success"), None)

        assert success_msg is not None
        assert success_msg["url"] == "https://example.com"
        assert "metadata" in success_msg

    @patch("gobbler_core.converters.webpage.convert_webpage_to_markdown")
    def test_batch_item_error_message(
        self,
        mock_convert: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test that failed items output item_error message."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://failing-url.test\n")
        output_dir = tmp_path / "output"

        async def mock_async_error(*args, **kwargs):
            msg = "Connection failed"
            raise RuntimeError(msg)

        mock_convert.side_effect = mock_async_error

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        error_msg = next((line for line in lines if line.get("type") == "item_error"), None)

        assert error_msg is not None
        assert error_msg["url"] == "https://failing-url.test"
        assert "error" in error_msg

    @patch("gobbler_core.converters.webpage.convert_webpage_to_markdown")
    def test_batch_webpages_json_all_items_fail_exits_nonzero(
        self,
        mock_convert: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test that a failed JSON batch summary exits non-zero."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://failing-url.test/1\nhttps://failing-url.test/2\n")
        output_dir = tmp_path / "output"

        async def mock_async_error(*args, **kwargs):
            msg = "Connection failed"
            raise RuntimeError(msg)

        mock_convert.side_effect = mock_async_error

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        error_messages = [line for line in lines if line.get("type") == "item_error"]
        complete_msg = next((line for line in lines if line.get("type") == "batch_complete"), None)

        assert result.exit_code == 1
        assert len(error_messages) == 2
        assert complete_msg is not None
        assert complete_msg["success"] is False
        assert complete_msg["schema_version"] == JSON_SCHEMA_VERSION
        assert complete_msg["summary"]["total"] == 2
        assert complete_msg["summary"]["successful"] == 0
        assert complete_msg["summary"]["failed"] == 2
        assert complete_msg["summary"]["skipped"] == 0

    @patch("gobbler_core.converters.webpage.convert_webpage_to_markdown")
    def test_batch_item_skipped_message(
        self,
        _mock_convert: MagicMock,  # noqa: PT019
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test that skipped items output item_skipped message."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com\n")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create existing file so it gets skipped
        existing_file = output_dir / "example.com.md"
        existing_file.write_text("# Existing content")

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
                "--skip-existing",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        skip_msg = next((line for line in lines if line.get("type") == "item_skipped"), None)

        assert skip_msg is not None
        assert skip_msg["reason"] == "already_exists"

    @patch("gobbler_core.converters.webpage.convert_webpage_to_markdown")
    def test_batch_complete_summary_structure(
        self,
        mock_convert: MagicMock,
        runner: CliRunner,
        cli_app,
        tmp_path: Path,
    ) -> None:
        """Test that batch_complete message contains correct summary."""
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com/1\nhttps://example.com/2\n")
        output_dir = tmp_path / "output"

        async def mock_async_convert(*args, **kwargs):
            return ("# Content", {"title": "Page"})

        mock_convert.side_effect = mock_async_convert

        result = runner.invoke(
            cli_app,
            [
                "batch",
                "webpages",
                str(urls_file),
                "--output-dir",
                str(output_dir),
                "--json",
            ],
        )

        lines = [json.loads(line) for line in result.output.strip().split("\n") if line]
        complete_msg = next((line for line in lines if line.get("type") == "batch_complete"), None)

        assert complete_msg is not None
        assert complete_msg["success"] is True
        assert complete_msg["schema_version"] == JSON_SCHEMA_VERSION
        assert complete_msg["summary"]["total"] == 2
        assert complete_msg["summary"]["successful"] == 2
        assert complete_msg["summary"]["failed"] == 0
        assert complete_msg["summary"]["skipped"] == 0


# =============================================================================
# Tests for OutputFormat enum
# =============================================================================


class TestOutputFormat:
    """Tests for OutputFormat enum."""

    def test_output_format_values(self) -> None:
        """Test that OutputFormat has expected values."""
        assert OutputFormat.MARKDOWN.value == "markdown"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.TABLE.value == "table"

    def test_output_format_is_string_enum(self) -> None:
        """Test that OutputFormat can be used as string."""
        # OutputFormat is a str enum so the value is the string
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.MARKDOWN.value == "markdown"


# =============================================================================
# Tests for JSON output structure validation
# =============================================================================


class TestJsonOutputStructure:
    """Tests for validating JSON output structure follows the contract."""

    def test_success_response_has_required_fields(self) -> None:
        """Test that success responses have all required fields."""
        result = format_json_success("# Content", {"key": "value"})

        # Required fields for success
        assert "success" in result
        assert "markdown" in result
        assert "metadata" in result
        assert result["success"] is True

    def test_error_response_has_required_fields(self) -> None:
        """Test that error responses have all required fields."""
        result = format_json_error("Error message", "ERROR_CODE")

        # Required fields for error
        assert "success" in result
        assert "error" in result
        assert "error_code" in result
        assert result["success"] is False

    def test_success_metadata_can_contain_source(self) -> None:
        """Test that success metadata includes source when provided."""
        result = format_json_success("# Content", {}, source="https://example.com")

        assert result["metadata"]["source"] == "https://example.com"

    def test_error_can_contain_source(self) -> None:
        """Test that error response includes source when provided."""
        result = format_json_error("Error", "ERROR_CODE", source="https://example.com")

        assert result["source"] == "https://example.com"

    def test_json_is_serializable(self) -> None:
        """Test that both success and error results can be serialized to JSON."""
        success = format_json_success("# Content", {"nested": {"key": "value"}})
        error = format_json_error("Error", "ERROR_CODE", source="test")

        # Should not raise
        json.dumps(success)
        json.dumps(error)

    def test_special_characters_in_markdown(self) -> None:
        """Test that special characters in markdown are preserved."""
        markdown = "# Test\n\n\"quotes\" and 'apostrophes'\n\nUnicode: \u00e9\u00e8"
        result = format_json_success(markdown, {})

        # Serialize and deserialize
        serialized = json.dumps(result)
        deserialized = json.loads(serialized)

        assert deserialized["markdown"] == markdown

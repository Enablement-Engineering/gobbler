"""Tests for YouTube command diagnostic output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import typer

from gobbler_cli.commands import convert
from gobbler_cli.output import OutputFormat
from gobbler_core.providers.youtube import YouTubeTranscriptError
from gobbler_core.utils.redaction import REDACTED


def test_youtube_json_invalid_url_rejected_locally(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid YouTube JSON input gets a stable local invalid-URL error."""
    convert_youtube = AsyncMock()
    monkeypatch.setattr(convert, "_convert_youtube", convert_youtube)

    with pytest.raises(typer.Exit) as exit_info:
        convert.youtube(
            url="not-a-url",
            output=None,
            language="en",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.JSON,
            timeout=30,
            skip_if_exists=False,
        )

    payload = json.loads(capsys.readouterr().out)

    assert exit_info.value.exit_code == 1
    assert payload["success"] is False
    assert payload["error_code"] == "YOUTUBE_INVALID_URL"
    assert payload["source"] == "not-a-url"
    assert "youtube.com/watch?v=" in payload["suggestion"]
    assert "youtu.be/" in payload["suggestion"]
    convert_youtube.assert_not_called()


def test_youtube_human_invalid_url_rejected_before_progress(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid human YouTube input fails before conversion progress can start."""
    convert_youtube = AsyncMock()
    monkeypatch.setattr(convert, "_convert_youtube", convert_youtube)

    with pytest.raises(typer.Exit) as exit_info:
        convert.youtube(
            url="not-a-url",
            output=None,
            language="en",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.MARKDOWN,
            timeout=30,
            skip_if_exists=False,
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err

    assert exit_info.value.exit_code == 1
    assert "Invalid YouTube URL" in combined_output
    assert "Converting YouTube video" not in combined_output
    convert_youtube.assert_not_called()


def test_youtube_invalid_url_skip_if_exists_preserves_existing_output_skip(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Existing outputs still skip before validating a stale or invalid YouTube URL."""
    output = tmp_path / "existing.md"
    output.write_text("existing", encoding="utf-8")
    convert_youtube = AsyncMock()
    monkeypatch.setattr(convert, "_convert_youtube", convert_youtube)

    convert.youtube(
        url="not-a-url",
        output=output,
        language="en",
        timestamps=False,
        clean=False,
        output_format=OutputFormat.JSON,
        timeout=30,
        skip_if_exists=True,
    )

    payload = json.loads(capsys.readouterr().out)

    assert payload["success"] is True
    assert payload["skipped"] is True
    assert payload["reason"] == "output_exists"
    assert payload["source"] == "not-a-url"
    convert_youtube.assert_not_called()


def test_youtube_overlong_id_rejected_locally(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """YouTube URLs with extra ID characters are invalid instead of truncated."""
    convert_youtube = AsyncMock()
    monkeypatch.setattr(convert, "_convert_youtube", convert_youtube)

    with pytest.raises(typer.Exit) as exit_info:
        convert.youtube(
            url="https://youtube.com/watch?v=dQw4w9WgXcQextra",
            output=None,
            language="en",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.JSON,
            timeout=30,
            skip_if_exists=False,
        )

    payload = json.loads(capsys.readouterr().out)

    assert exit_info.value.exit_code == 1
    assert payload["error_code"] == "YOUTUBE_INVALID_URL"
    convert_youtube.assert_not_called()


def test_youtube_valid_url_dispatches_to_converter(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid YouTube URLs continue through the existing converter dispatch path."""
    calls: list[dict[str, Any]] = []

    async def fake_convert_youtube_to_markdown(
        *_args: Any, **kwargs: Any
    ) -> tuple[str, dict[str, str]]:
        calls.append(kwargs)
        return "# Transcript", {"title": "Video"}

    monkeypatch.setattr(
        "gobbler_core.converters.youtube.convert_youtube_to_markdown",
        fake_convert_youtube_to_markdown,
    )

    convert.youtube(
        url="https://youtube.com/watch?v=dQw4w9WgXcQ",
        output=None,
        language="es",
        timestamps=True,
        clean=False,
        output_format=OutputFormat.JSON,
        timeout=45,
        skip_if_exists=False,
    )

    payload = json.loads(capsys.readouterr().out)

    assert payload["success"] is True
    assert payload["markdown"] == "# Transcript"
    assert calls == [
        {
            "video_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "language": "es",
            "include_timestamps": True,
            "timeout": 45,
        }
    ]


class _NoopProgress:
    """No-op replacement for CLI progress in JSON output tests."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        """Accept progress arguments without side effects."""

    def __enter__(self) -> _NoopProgress:
        """Enter the no-op context."""
        return self

    def __exit__(self, *_args: Any) -> None:
        """Exit the no-op context."""


@pytest.mark.asyncio
async def test_youtube_json_error_includes_sanitized_diagnostics(capsys) -> None:
    """YouTube JSON failures include structured diagnostics without proxy credentials."""

    async def fail_conversion(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        raise YouTubeTranscriptError(
            message="YouTube transcript fetch was rate limited (HTTP 429).",
            diagnostics={
                "provider": "youtube-transcript-api",
                "error_type": "rate_limited",
                "status_code": 429,
                "video_id": "dQw4w9WgXcQ",
                "language": "auto",
                "proxy_url": "http://proxy-user:proxy-pass@proxy.example:8080",
                "next_actions": ["Wait 10-15 minutes and retry."],
            },
        )

    with (
        patch("gobbler_cli.commands.convert.ProgressTracker", _NoopProgress),
        patch(
            "gobbler_core.converters.youtube.convert_youtube_to_markdown",
            side_effect=fail_conversion,
        ),
        pytest.raises(typer.Exit),
    ):
        await convert._convert_youtube(
            url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            output=None,
            language="auto",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.JSON,
            timeout=30,
        )

    payload = json.loads(capsys.readouterr().out)
    dumped = json.dumps(payload)

    assert payload["success"] is False
    assert payload["error_code"] == "YOUTUBE_CONVERSION_ERROR"
    assert payload["diagnostics"]["error_type"] == "rate_limited"
    assert payload["diagnostics"]["status_code"] == 429
    assert payload["diagnostics"]["proxy_url"] == f"http://{REDACTED}@proxy.example:8080"
    assert "proxy-user" not in dumped
    assert "proxy-pass" not in dumped

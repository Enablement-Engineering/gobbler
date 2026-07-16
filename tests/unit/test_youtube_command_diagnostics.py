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
from gobbler_core.providers.youtube import YouTubeTranscriptError, create_youtube_rate_limit_error
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


def test_youtube_json_invalid_url_sanitizes_sensitive_source(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid YouTube JSON input omits userinfo, query values, and fragments."""
    convert_youtube = AsyncMock()
    monkeypatch.setattr(convert, "_convert_youtube", convert_youtube)
    url = (
        "https://user:password@youtube.com/watch"
        "?session=session-secret&q=search-secret#fragment-secret"
    )

    with pytest.raises(typer.Exit) as exit_info:
        convert.youtube(
            url=url,
            output=None,
            language="en",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.JSON,
            timeout=30,
            skip_if_exists=False,
        )

    payload = json.loads(capsys.readouterr().out)
    dumped = json.dumps(payload)

    assert exit_info.value.exit_code == 1
    assert payload["error_code"] == "YOUTUBE_INVALID_URL"
    assert payload["source"] == f"https://{REDACTED}@youtube.com/watch"
    assert "user" not in dumped
    assert "password" not in dumped
    assert "session-secret" not in dumped
    assert "search-secret" not in dumped
    assert "fragment-secret" not in dumped
    convert_youtube.assert_not_called()


def test_youtube_json_invalid_url_sanitization_never_raises(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanitizer failures still produce a safe invalid-URL diagnostic."""
    convert_youtube = AsyncMock()
    monkeypatch.setattr(convert, "_convert_youtube", convert_youtube)
    monkeypatch.setattr(convert, "urlparse", lambda _url: (_ for _ in ()).throw(RuntimeError))

    with pytest.raises(typer.Exit) as exit_info:
        convert.youtube(
            url="https://user:password@youtube.com/watch?session=secret#fragment",
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
    assert payload["source"] == REDACTED
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


@pytest.mark.asyncio
async def test_youtube_json_transcriptapi_billing_error_gets_specific_diagnostic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TranscriptAPI billing failures use a stable account-actionable JSON code."""

    async def fail_conversion(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        raise YouTubeTranscriptError(
            message=(
                "TranscriptAPI: You don't have an active paid plan yet.. "
                "Action: https://transcriptapi.com/billing"
            ),
            diagnostics={
                "provider": "transcriptapi",
                "error_type": "billing_required",
                "status_code": 402,
                "video_id": "dQw4w9WgXcQ",
                "language": "auto",
                "action_url": "https://transcriptapi.com/billing",
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

    assert payload["success"] is False
    assert payload["error_code"] == "YOUTUBE_TRANSCRIPTAPI_BILLING_REQUIRED"
    assert payload["diagnostics"]["provider"] == "transcriptapi"
    assert payload["diagnostics"]["error_type"] == "billing_required"
    assert "billing" in payload["suggestion"].lower()
    assert "active plan" in payload["suggestion"].lower()
    assert "TRANSCRIPTAPI_KEY" not in payload["suggestion"]


@pytest.mark.asyncio
async def test_youtube_json_transcriptapi_legacy_billing_text_gets_specific_diagnostic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Legacy TranscriptAPI payment text is classified without structured diagnostics."""

    async def fail_conversion(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        message = (
            "TranscriptAPI: You don't have an active paid plan yet.. "
            "Action: https://transcriptapi.com/billing"
        )
        raise RuntimeError(message)

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

    assert payload["error_code"] == "YOUTUBE_TRANSCRIPTAPI_BILLING_REQUIRED"
    assert "TRANSCRIPTAPI_KEY" not in payload["suggestion"]


@pytest.mark.asyncio
async def test_youtube_json_transcriptapi_rate_limit_keeps_conversion_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TranscriptAPI rate limits are not classified as billing failures."""

    async def fail_conversion(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        raise create_youtube_rate_limit_error(
            video_id="dQw4w9WgXcQ",
            language="auto",
            provider="transcriptapi",
            retry_after_seconds=120,
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

    assert payload["error_code"] == "YOUTUBE_CONVERSION_ERROR"
    assert payload["diagnostics"]["provider"] == "transcriptapi"
    assert payload["diagnostics"]["error_type"] == "rate_limited"
    assert payload["diagnostics"]["status_code"] == 429

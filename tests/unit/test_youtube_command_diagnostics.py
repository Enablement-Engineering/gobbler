"""Tests for YouTube command diagnostic output."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
import typer

from gobbler_cli.commands import convert
from gobbler_cli.output import OutputFormat
from gobbler_core.providers.youtube import YouTubeTranscriptError
from gobbler_core.utils.redaction import REDACTED


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

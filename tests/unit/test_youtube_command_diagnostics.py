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
from gobbler_core.converters.youtube_frames import (
    FrameRange,
    YouTubeFrameError,
    YouTubeFrameRequest,
    resolve_frame_targets,
)
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
    """Invalid YouTube JSON input omits all credential-bearing URL components."""
    convert_youtube = AsyncMock()
    monkeypatch.setattr(convert, "_convert_youtube", convert_youtube)
    url = (
        "https://unique-user:unique-password@youtube.com/private-path-token"
        "?session=unique-session&q=unique-query&sid=unique-sid"
        "&email=unique-email@example.com#unique-fragment"
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
    assert payload["source"] == f"https://{REDACTED}@youtube.com"
    for secret in (
        "unique-user",
        "unique-password",
        "private-path-token",
        "unique-session",
        "unique-query",
        "unique-sid",
        "unique-email@example.com",
        "unique-fragment",
    ):
        assert secret not in dumped
    convert_youtube.assert_not_called()


def test_youtube_json_invalid_url_omits_path_token(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid URL-like YouTube input retains only a minimal host identity."""
    convert_youtube = AsyncMock()
    monkeypatch.setattr(convert, "_convert_youtube", convert_youtube)

    with pytest.raises(typer.Exit):
        convert.youtube(
            url="https://youtube.com/private-local-path-token",
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

    assert payload["source"] == "https://youtube.com"
    assert "private-local-path-token" not in dumped
    convert_youtube.assert_not_called()


def test_youtube_json_invalid_url_with_backslash_fails_closed(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed authorities cannot smuggle a private path into the JSON source."""
    convert_youtube = AsyncMock()
    monkeypatch.setattr(convert, "_convert_youtube", convert_youtube)
    url = "https://youtube.com\\malformed-private-path-token?session=hidden"

    with pytest.raises(typer.Exit):
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

    assert payload["source"] == REDACTED
    assert "malformed-private-path-token" not in dumped
    assert "hidden" not in dumped
    convert_youtube.assert_not_called()


def test_youtube_json_invalid_hostname_characters_fail_closed(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid hostname characters cannot be retained in a failure source."""
    convert_youtube = AsyncMock()
    monkeypatch.setattr(convert, "_convert_youtube", convert_youtube)
    url = "https://youtube.com%2fprivate-host-token/watch?session=host-query-secret"

    with pytest.raises(typer.Exit):
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

    assert payload["source"] == REDACTED
    assert "private-host-token" not in dumped
    assert "host-query-secret" not in dumped
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


def test_youtube_frame_options_dispatch_typed_request(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Repeatable frame selectors become one typed converter request."""
    calls: list[dict[str, Any]] = []

    async def fake_convert_youtube_to_markdown(**kwargs: Any) -> tuple[str, dict[str, Any]]:
        calls.append(kwargs)
        return "# Video Frames", {"frames": []}

    monkeypatch.setattr(
        "gobbler_core.converters.youtube.convert_youtube_to_markdown",
        fake_convert_youtube_to_markdown,
    )
    output = tmp_path / "frames.md"

    convert.youtube(
        url="https://youtube.com/watch?v=dQw4w9WgXcQ",
        output=output,
        language="en",
        timestamps=False,
        clean=False,
        output_format=OutputFormat.JSON,
        timeout=30,
        skip_if_exists=False,
        overview_frames=2,
        frame_at=["00:05.125", "8"],
        frame_ranges=["00:10-00:20"],
        range_frames=4,
        frames_only=True,
        frames_dir=None,
    )

    request = calls[0]["frame_request"]
    assert request.overview_count == 2
    assert request.exact_timestamps == (5.125, 8.0)
    assert request.ranges[0].start == 10.0
    assert request.range_count == 4
    assert calls[0]["frames_only"] is True
    assert calls[0]["output_path"] == output
    assert json.loads(output.read_text(encoding="utf-8"))["success"] is True
    capsys.readouterr()


def test_clean_transcript_preserves_appended_frame_section_byte_for_byte() -> None:
    """Clean mode changes only transcript prose in combined output."""
    frame_section = (
        "\n\n## Video Frames\n\n"
        "### 00:05.000\n\n"
        "![Video frame at 00:05.000](combined.assets/frames/frame-001.jpg)\n\n"
        "### 00:10.000\n\n"
        "![Video frame at 00:10.000](combined.assets/frames/frame-002.jpg)"
    )
    markdown = (
        "---\ntype: youtube\n---\n\n"
        "# Video Transcript\n\n"
        "First caption line.\n\nSecond caption line." + frame_section
    )

    cleaned = convert._clean_transcript(markdown, preserve_frame_section=True)

    assert cleaned == (
        "---\ntype: youtube\n---\n\n"
        "# Video Transcript\n\n"
        "First caption line. Second caption line." + frame_section
    )


def test_clean_transcript_keeps_transcript_only_behavior() -> None:
    """Transcript-only clean mode still merges caption blocks."""
    markdown = "# Video Transcript\n\nFirst caption.\n\nSecond caption."

    assert convert._clean_transcript(markdown) == (
        "# Video Transcript\n\nFirst caption. Second caption."
    )


@pytest.mark.asyncio
async def test_clean_combined_conversion_preserves_frame_manifest(tmp_path: Path) -> None:
    """The command clean path passes combined output through frame-aware cleaning."""
    frame_section = (
        "\n\n## Video Frames\n\n"
        "### 00:05.000\n\n"
        "![Video frame at 00:05.000](combined.assets/frames/frame-001.jpg)"
    )
    markdown = "# Video Transcript\n\nFirst caption.\n\nSecond caption." + frame_section
    output = tmp_path / "combined.json"

    with patch(
        "gobbler_core.converters.youtube.convert_youtube_to_markdown",
        new=AsyncMock(return_value=(markdown, {"word_count": 4})),
    ):
        await convert._convert_youtube(
            url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            output=output,
            language="en",
            timestamps=False,
            clean=True,
            output_format=OutputFormat.JSON,
            timeout=30,
            frame_request=YouTubeFrameRequest(overview_count=2),
            output_path=tmp_path / "combined.md",
        )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["markdown"] == (
        "# Video Transcript\n\nFirst caption. Second caption." + frame_section
    )
    assert payload["metadata"]["word_count"] == 4


@pytest.mark.asyncio
async def test_frame_commit_failure_restores_previous_json_output(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """The CLI output hook keeps the prior JSON until the frame commit succeeds."""
    output = tmp_path / "frames.json"
    output.write_text('{"previous": true}', encoding="utf-8")

    async def fail_after_persistence(**kwargs: Any) -> tuple[str, dict[str, Any]]:
        writer = kwargs["frame_manifest_writer"]
        _markdown, _metadata, hooks = writer("# New frames", {"frames": []})
        assert json.loads(output.read_text(encoding="utf-8"))["success"] is True
        hooks.rollback()
        message = "Unable to replace existing YouTube frame artifacts"
        raise YouTubeFrameError(
            message,
            {"error_type": "filesystem_error", "stage": "frame_commit"},
        )

    with (
        patch(
            "gobbler_core.converters.youtube.convert_youtube_to_markdown",
            side_effect=fail_after_persistence,
        ),
        pytest.raises(typer.Exit),
    ):
        await convert._convert_youtube(
            url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            output=output,
            language="en",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.JSON,
            timeout=30,
            frame_request=YouTubeFrameRequest(exact_timestamps=(1.0,)),
            frames_only=True,
            output_path=output,
        )

    assert output.read_text(encoding="utf-8") == '{"previous": true}'
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == "YOUTUBE_FRAME_EXTRACTION_ERROR"
    assert not list(tmp_path.glob(".frames.json.gobbler-backup-*"))


@pytest.mark.asyncio
@pytest.mark.parametrize("output_format", [OutputFormat.MARKDOWN, OutputFormat.JSON])
async def test_stdout_frame_commit_failure_emits_only_error_output(
    capsys: pytest.CaptureFixture[str], output_format: OutputFormat
) -> None:
    """Buffered stdout success is discarded when its frame commit fails."""

    async def fail_after_buffering(**kwargs: Any) -> tuple[str, dict[str, Any]]:
        writer = kwargs["frame_manifest_writer"]
        _markdown, _metadata, hooks = writer("stale success manifest", {"frames": []})
        hooks.rollback()
        message = "Unable to replace existing YouTube frame artifacts"
        raise YouTubeFrameError(
            message,
            {"error_type": "filesystem_error", "stage": "frame_commit"},
        )

    with (
        patch(
            "gobbler_core.converters.youtube.convert_youtube_to_markdown",
            side_effect=fail_after_buffering,
        ),
        pytest.raises(typer.Exit),
    ):
        await convert._convert_youtube(
            url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            output=None,
            language="en",
            timestamps=False,
            clean=False,
            output_format=output_format,
            timeout=30,
            frame_request=YouTubeFrameRequest(exact_timestamps=(1.0,), frames_dir=Path("frames")),
            frames_only=True,
        )

    captured = capsys.readouterr()
    assert "stale success manifest" not in captured.out + captured.err
    if output_format == OutputFormat.JSON:
        payload = json.loads(captured.out)
        assert payload["success"] is False
        assert payload["error_code"] == "YOUTUBE_FRAME_EXTRACTION_ERROR"
        assert captured.out.count('"success"') == 1
        assert captured.err == ""
    else:
        assert captured.out == ""
        assert captured.err.count("Failed to convert YouTube video") == 1


@pytest.mark.asyncio
async def test_frame_markdown_stdout_is_manifest_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Frame manifests printed to stdout contain no Rich progress rendering."""
    with (
        patch(
            "gobbler_core.converters.youtube.convert_youtube_to_markdown",
            new=AsyncMock(return_value=("---\ntype: youtube_frames\n---\n# Video Frames", {})),
        ),
        patch("gobbler_cli.commands.convert.ProgressTracker") as progress,
    ):
        await convert._convert_youtube(
            url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            output=None,
            language="en",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.MARKDOWN,
            timeout=30,
            frame_request=YouTubeFrameRequest(exact_timestamps=(1.0,), frames_dir=Path("frames")),
            frames_only=True,
        )

    progress.assert_not_called()
    assert capsys.readouterr().out.startswith("---\ntype: youtube_frames")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"overview_frames": 1}, "--output or --frames-dir"),
        ({"frames_only": True}, "at least one frame selector"),
        ({"range_frames": 4}, "--frame-range"),
        ({"frame_at": ["bad"]}, "Invalid frame timestamp"),
        ({"frame_at": ["1"] * 49}, "maximum is 48"),
    ],
)
def test_youtube_invalid_frame_request_fails_before_dispatch(
    kwargs: dict[str, Any],
    message: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cross-option and selector errors are stable agent-safe JSON failures."""
    convert_youtube = AsyncMock()
    monkeypatch.setattr(convert, "_convert_youtube", convert_youtube)
    options: dict[str, Any] = {
        "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "output": None,
        "language": "en",
        "timestamps": False,
        "clean": False,
        "output_format": OutputFormat.JSON,
        "timeout": 30,
        "skip_if_exists": False,
        "overview_frames": 0,
        "frame_at": [],
        "frame_ranges": [],
        "range_frames": None,
        "frames_only": False,
        "frames_dir": None,
    }
    options.update(kwargs)

    with pytest.raises(typer.Exit):
        convert.youtube(**options)

    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == "YOUTUBE_INVALID_FRAME_REQUEST"
    assert message in payload["error"]
    convert_youtube.assert_not_called()


@pytest.mark.parametrize(
    "selector_options",
    [
        {"frame_at": ["9" * 10_000]},
        {"frame_ranges": [f"1-{'9' * 10_000}"]},
    ],
)
def test_youtube_json_oversized_numeric_selector_emits_one_clean_validation_payload(
    selector_options: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Decimal overflow never escapes the JSON selector-validation contract."""
    convert_youtube = AsyncMock()
    monkeypatch.setattr(convert, "_convert_youtube", convert_youtube)
    options: dict[str, Any] = {
        "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "output": tmp_path / "frames.json",
        "language": "en",
        "timestamps": False,
        "clean": False,
        "output_format": OutputFormat.JSON,
        "timeout": 30,
        "skip_if_exists": False,
        "overview_frames": 0,
        "frame_at": [],
        "frame_ranges": [],
        "range_frames": None,
        "frames_only": True,
        "frames_dir": None,
    }
    options.update(selector_options)

    with pytest.raises(typer.Exit) as exit_info:
        convert.youtube(**options)

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_info.value.exit_code == 1
    assert payload["error_code"] == "YOUTUBE_INVALID_FRAME_REQUEST"
    assert captured.err == ""
    assert captured.out.count('"error_code"') == 1
    convert_youtube.assert_not_called()


@pytest.mark.parametrize(
    "frame_request_case",
    [
        YouTubeFrameRequest(exact_timestamps=(10.0,)),
        YouTubeFrameRequest(exact_timestamps=(11.0,)),
        YouTubeFrameRequest(ranges=(FrameRange(8.0, 10.0),), range_count=2),
        YouTubeFrameRequest(ranges=(FrameRange(8.0, 11.0),), range_count=2),
        YouTubeFrameRequest(
            overview_count=24,
            exact_timestamps=tuple(float(index) for index in range(25)),
        ),
    ],
)
@pytest.mark.asyncio
async def test_youtube_json_post_duration_selector_errors_are_invalid_frame_requests(
    frame_request_case: YouTubeFrameRequest,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Duration bounds and the total cap retain selector classification in JSON mode."""

    async def resolve_then_fail(**kwargs: Any) -> tuple[str, dict[str, Any]]:
        supplied = kwargs["frame_request"]
        resolve_frame_targets(
            duration_seconds=10.0,
            overview_count=supplied.overview_count,
            exact_timestamps=supplied.exact_timestamps,
            ranges=supplied.ranges,
            range_count=supplied.range_count,
        )
        pytest.fail("selector unexpectedly resolved")

    with (
        patch(
            "gobbler_core.converters.youtube.convert_youtube_to_markdown",
            side_effect=resolve_then_fail,
        ),
        pytest.raises(typer.Exit) as exit_info,
    ):
        await convert._convert_youtube(
            url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            output=None,
            language="en",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.JSON,
            timeout=30,
            frame_request=frame_request_case,
            frames_only=True,
        )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_info.value.exit_code == 1
    assert payload["error_code"] == "YOUTUBE_INVALID_FRAME_REQUEST"
    assert captured.err == ""
    assert captured.out.count('"error_code"') == 1


@pytest.mark.asyncio
async def test_youtube_human_post_duration_selector_error_uses_validation_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Human output reports a clean selector error without a generic conversion wrapper."""

    async def resolve_then_fail(**kwargs: Any) -> tuple[str, dict[str, Any]]:
        supplied = kwargs["frame_request"]
        resolve_frame_targets(
            duration_seconds=10.0,
            overview_count=supplied.overview_count,
            exact_timestamps=supplied.exact_timestamps,
            ranges=supplied.ranges,
            range_count=supplied.range_count,
        )
        pytest.fail("selector unexpectedly resolved")

    with (
        patch("gobbler_cli.commands.convert.ProgressTracker", _NoopProgress),
        patch(
            "gobbler_core.converters.youtube.convert_youtube_to_markdown",
            side_effect=resolve_then_fail,
        ),
        pytest.raises(typer.Exit),
    ):
        await convert._convert_youtube(
            url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            output=None,
            language="en",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.MARKDOWN,
            timeout=30,
            frame_request=YouTubeFrameRequest(exact_timestamps=(10.0,)),
            frames_only=True,
        )

    captured = capsys.readouterr()
    assert "before the video duration" in captured.err
    assert "Failed to convert YouTube video" not in captured.err


@pytest.mark.asyncio
async def test_youtube_unavailable_frame_resolver_error_uses_frame_extraction_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exception identity classifies generic resolver unavailability as a frame failure."""
    error = YouTubeFrameError(
        "Unable to resolve the YouTube video for frame extraction",
        {"error_type": "unavailable", "stage": "stream_resolution"},
    )

    with (
        patch(
            "gobbler_core.converters.youtube.convert_youtube_to_markdown",
            side_effect=error,
        ),
        pytest.raises(typer.Exit),
    ):
        await convert._convert_youtube(
            url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            output=None,
            language="en",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.JSON,
            timeout=30,
            frame_request=YouTubeFrameRequest(exact_timestamps=(1.0,)),
            frames_only=True,
        )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["error_code"] == "YOUTUBE_FRAME_EXTRACTION_ERROR"
    assert captured.err == ""


class _NoopProgress:
    """No-op replacement for CLI progress in JSON output tests."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        """Accept progress arguments without side effects."""

    def __enter__(self) -> _NoopProgress:
        """Enter the no-op context."""
        return self

    def __exit__(self, *_args: Any) -> None:
        """Exit the no-op context."""


class _ParserDiagnosticError(RuntimeError):
    """Parser-shaped failure carrying nested structured diagnostics."""

    def __init__(self, url: str) -> None:
        """Repeat the submitted URL across parser diagnostics."""
        self.diagnostics = {
            "provider": "youtube-parser",
            "stage": "parse-response",
            "nested": {"request_url": url, "attempts": [url, {"status_code": 502}]},
        }
        super().__init__(f"Could not parse provider response for {url}")


def _credential_bearing_youtube_url() -> tuple[str, tuple[str, ...]]:
    """Return a submitted URL and unique secrets used by JSON leak regressions."""
    secrets = (
        "provider-user",
        "provider-password",
        "private-video-path-token",
        "provider-session-value",
        "provider-query-value",
        "provider-sid-value",
        "provider-email@example.com",
        "provider-fragment-value",
    )
    url = (
        "https://provider-user:provider-password@youtube.com/"
        "private-video-path-token?session=provider-session-value"
        "&q=provider-query-value&sid=provider-sid-value"
        "&email=provider-email@example.com#provider-fragment-value"
    )
    return url, secrets


@pytest.mark.asyncio
async def test_youtube_json_provider_error_removes_submitted_url_everywhere(capsys) -> None:
    """Provider errors cannot repeat a submitted credential-bearing URL in JSON."""
    url, secrets = _credential_bearing_youtube_url()

    async def fail_conversion(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        raise YouTubeTranscriptError(
            message=f"Provider rejected submitted URL {url}",
            diagnostics={
                "provider": "youtube-transcript-api",
                "error_type": "provider_failure",
                "status_code": 503,
                "nested": {"request_url": url, "attempts": [url, "safe-marker"]},
            },
        )

    with (
        patch(
            "gobbler_core.converters.youtube.convert_youtube_to_markdown",
            side_effect=fail_conversion,
        ),
        pytest.raises(typer.Exit),
    ):
        await convert._convert_youtube(
            url=url,
            output=None,
            language="auto",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.JSON,
            timeout=30,
        )

    payload = json.loads(capsys.readouterr().out)
    dumped = json.dumps(payload)

    assert payload["source"] == f"https://{REDACTED}@youtube.com"
    assert payload["diagnostics"]["provider"] == "youtube-transcript-api"
    assert payload["diagnostics"]["status_code"] == 503
    assert payload["diagnostics"]["nested"]["attempts"][1] == "safe-marker"
    for secret in secrets:
        assert secret not in dumped


@pytest.mark.asyncio
async def test_youtube_json_parser_error_removes_submitted_url_everywhere(capsys) -> None:
    """Parser errors cannot repeat a submitted credential-bearing URL in JSON."""
    url, secrets = _credential_bearing_youtube_url()

    async def fail_conversion(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        raise _ParserDiagnosticError(url)

    with (
        patch(
            "gobbler_core.converters.youtube.convert_youtube_to_markdown",
            side_effect=fail_conversion,
        ),
        pytest.raises(typer.Exit),
    ):
        await convert._convert_youtube(
            url=url,
            output=None,
            language="auto",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.JSON,
            timeout=30,
        )

    payload = json.loads(capsys.readouterr().out)
    dumped = json.dumps(payload)

    assert payload["source"] == f"https://{REDACTED}@youtube.com"
    assert payload["diagnostics"]["provider"] == "youtube-parser"
    assert payload["diagnostics"]["stage"] == "parse-response"
    assert payload["diagnostics"]["nested"]["attempts"][1]["status_code"] == 502
    for secret in secrets:
        assert secret not in dumped


@pytest.mark.asyncio
async def test_youtube_json_error_sanitizes_urls_nested_in_tuples(capsys) -> None:
    """Tuple diagnostics are recursively sanitized before JSON serialization."""
    secrets = ("tuple-path-secret", "tuple-query-secret", "tuple-fragment-secret")
    url = "https://youtube.com/tuple-path-secret?q=tuple-query-secret#tuple-fragment-secret"

    async def fail_conversion(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        raise YouTubeTranscriptError(
            message="Tuple diagnostic conversion failure",
            diagnostics={
                "nested": [
                    (
                        "safe-tuple-marker",
                        {"request_url": url, "status_code": 502},
                    )
                ]
            },
        )

    with (
        patch(
            "gobbler_core.converters.youtube.convert_youtube_to_markdown",
            side_effect=fail_conversion,
        ),
        pytest.raises(typer.Exit),
    ):
        await convert._convert_youtube(
            url=url,
            output=None,
            language="auto",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.JSON,
            timeout=30,
        )

    payload = json.loads(capsys.readouterr().out)
    dumped = json.dumps(payload)

    assert payload["diagnostics"]["nested"][0][0] == "safe-tuple-marker"
    assert payload["diagnostics"]["nested"][0][1]["status_code"] == 502
    for secret in secrets:
        assert secret not in dumped


@pytest.mark.asyncio
async def test_youtube_json_error_with_malformed_port_still_emits_json(capsys) -> None:
    """Malformed URLs in exception payloads cannot mask the converter failure."""
    url = (
        "https://port-user:port-password@youtube.com:not-a-port/port-path-secret"
        "?session=port-query-secret#port-fragment-secret"
    )
    already_redacted_url = url.replace("port-user:port-password", "[REDACTED]")

    async def fail_conversion(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        error = _ParserDiagnosticError(url)
        error.args = (f"original conversion failure for {url} and {already_redacted_url}",)
        error.diagnostics = {
            "provider": "malformed-port-provider",
            "nested": {
                "request_url": url,
                "attempts": [already_redacted_url, {"submitted_url": url}],
            },
        }
        raise error

    with (
        patch(
            "gobbler_core.converters.youtube.convert_youtube_to_markdown",
            side_effect=fail_conversion,
        ),
        pytest.raises(typer.Exit) as exit_info,
    ):
        await convert._convert_youtube(
            url=url,
            output=None,
            language="auto",
            timestamps=False,
            clean=False,
            output_format=OutputFormat.JSON,
            timeout=30,
        )

    payload = json.loads(capsys.readouterr().out)
    dumped = json.dumps(payload)

    assert exit_info.value.exit_code == 1
    assert payload["error_code"] == "YOUTUBE_CONVERSION_ERROR"
    assert payload["error"] == REDACTED
    assert payload["source"] == REDACTED
    assert payload.get("diagnostics") is None
    for secret in (
        "port-user",
        "port-password",
        "not-a-port",
        "port-path-secret",
        "port-query-secret",
        "port-fragment-secret",
    ):
        assert secret not in dumped


def test_replace_submitted_url_removes_already_redacted_malformed_port_variant() -> None:
    """Already-redacted malformed URLs are replaced in prose and nested diagnostics."""
    url = (
        "https://isolated-user:isolated-password@youtube.com:not-a-port/isolated-path-secret"
        "?session=isolated-query-secret#isolated-fragment-secret"
    )
    already_redacted_url = url.replace("isolated-user:isolated-password", REDACTED)
    error = _ParserDiagnosticError(already_redacted_url)
    result = convert._replace_submitted_url(
        {"error": str(error), "diagnostics": error.diagnostics},
        url,
        REDACTED,
    )

    dumped = json.dumps(result)
    payload = json.loads(dumped)

    assert payload["diagnostics"]["provider"] == "youtube-parser"
    assert payload["diagnostics"]["stage"] == "parse-response"
    assert payload["diagnostics"]["nested"]["attempts"][1]["status_code"] == 502
    for secret in (
        "not-a-port",
        "isolated-path-secret",
        "isolated-query-secret",
        "isolated-fragment-secret",
    ):
        assert secret not in dumped


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

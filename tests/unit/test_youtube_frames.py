"""Unit tests for deterministic YouTube frame extraction."""

from __future__ import annotations

import asyncio
import json
import math
import ntpath
import threading
import time
import traceback
from pathlib import Path, PureWindowsPath
from unittest.mock import MagicMock

import pytest

from gobbler_cli.output import persist_text_transactionally
from gobbler_core.converters.youtube_frames import (
    FFMPEG_CONCURRENCY,
    FrameCommitHooks,
    FrameExtractionResult,
    FrameFailure,
    FrameRange,
    FrameTarget,
    VideoFrameArtifact,
    YouTubeFrameError,
    YouTubeFrameRequest,
    YouTubeFrameRequestError,
    YouTubeStreamInfo,
    _extract_frame,
    build_frame_metadata,
    derive_frames_dir,
    extract_youtube_frames,
    format_frame_timestamp,
    parse_frame_range,
    parse_frame_timestamp,
    render_frame_warnings_markdown,
    render_frames_markdown,
    resolve_frame_targets,
    resolve_youtube_stream,
    validate_frame_manifest_path,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("85", 85.0),
        ("23:41", 1421.0),
        ("1:23:41", 5021.0),
        ("24:16.5", 1456.5),
        ("00:00.125", 0.125),
    ],
)
def test_parse_frame_timestamp(raw: str, expected: float) -> None:
    """Supported timestamp shapes preserve fractional seconds."""
    assert parse_frame_timestamp(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "-1", "+1", "1e3", "1.0001", "abc", "1:60", "1:2:60", "1:2:3:4"],
)
def test_parse_frame_timestamp_rejects_invalid_values(raw: str) -> None:
    """Malformed and negative timestamp values are rejected."""
    with pytest.raises(ValueError, match=r"Invalid|finite|seconds|minutes"):
        parse_frame_timestamp(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "9" * 10_000,
        f"{'9' * 10_000}:00",
        f"{'9' * 10_000}:00:00",
    ],
)
def test_parse_frame_timestamp_rejects_decimal_overflow_as_value_error(raw: str) -> None:
    """Oversized numeric timestamps keep the fixed selector-validation contract."""
    with pytest.raises(ValueError, match="Invalid frame timestamp"):
        parse_frame_timestamp(raw)


def test_parse_frame_range_rejects_decimal_overflow_as_value_error() -> None:
    """Oversized range endpoints are ordinary selector-validation failures."""
    with pytest.raises(ValueError, match="Invalid frame timestamp"):
        parse_frame_range(f"1-{'9' * 10_000}")


def test_parse_range_and_format_timestamp() -> None:
    """Ranges parse and timestamps format to milliseconds."""
    assert parse_frame_range("23:41-25:00") == FrameRange(start=1421.0, end=1500.0)
    assert format_frame_timestamp(1456.5) == "24:16.500"


def test_resolve_frame_targets_composes_and_deduplicates() -> None:
    """Selectors compose with chronological ordering and provenance precedence."""
    targets = resolve_frame_targets(
        duration_seconds=100.0,
        overview_count=2,
        exact_timestamps=(25.0, 90.0),
        ranges=(FrameRange(20.0, 30.0),),
        range_count=3,
    )
    assert [(target.timestamp_seconds, target.selector) for target in targets] == [
        (20.0, "range"),
        (25.0, "exact"),
        (30.0, "range"),
        (75.0, "overview"),
        (90.0, "exact"),
    ]


def test_resolve_frame_targets_validates_bounds_and_total() -> None:
    """Duration bounds and the invocation cap are enforced."""
    with pytest.raises(ValueError, match="before the video duration"):
        resolve_frame_targets(
            duration_seconds=10,
            overview_count=0,
            exact_timestamps=(10,),
            ranges=(),
            range_count=6,
        )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, "not-a-number"])
def test_typed_frame_request_rejects_non_finite_or_unconvertible_values(value: object) -> None:
    """Typed callers receive selector errors for invalid numeric values."""
    with pytest.raises(YouTubeFrameRequestError):
        YouTubeFrameRequest(exact_timestamps=(value,))  # type: ignore[arg-type]


def test_typed_frame_request_caps_raw_selectors_before_deduplication() -> None:
    """Unlimited duplicate selectors cannot bypass the input cardinality cap."""
    with pytest.raises(YouTubeFrameRequestError, match="48"):
        YouTubeFrameRequest(exact_timestamps=(1.0,) * 49)
    with pytest.raises(ValueError, match="48"):
        resolve_frame_targets(
            duration_seconds=100,
            overview_count=24,
            exact_timestamps=tuple(float(index) for index in range(25)),
            ranges=(),
            range_count=6,
        )


def test_resolve_youtube_stream_prefers_bounded_video(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stream resolution selects the best video format no larger than 720p."""
    info = {
        "duration": 12.5,
        "formats": [
            {"url": "https://media.invalid/1080?token=secret", "vcodec": "avc1", "height": 1080},
            {"url": "https://media.invalid/360?token=secret", "vcodec": "avc1", "height": 360},
            {"url": "https://media.invalid/720?token=secret", "vcodec": "avc1", "height": 720},
        ],
    }
    youtube_dl = MagicMock()
    youtube_dl.return_value.__enter__.return_value.extract_info.return_value = info
    monkeypatch.setattr("gobbler_core.converters.youtube_frames.yt_dlp.YoutubeDL", youtube_dl)

    stream = resolve_youtube_stream("https://youtube.com/watch?v=dQw4w9WgXcQ")

    assert stream.duration_seconds == 12.5
    assert stream.url.endswith("/720?token=secret")


def test_resolve_youtube_stream_sanitizes_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raw extractor diagnostics and submitted URL secrets never escape."""
    youtube_dl = MagicMock()
    youtube_dl.return_value.__enter__.return_value.extract_info.side_effect = RuntimeError(
        "private video at https://media.invalid/file?token=stream-secret cookie=cookie-secret"
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames.yt_dlp.YoutubeDL", youtube_dl)

    with pytest.raises(YouTubeFrameError) as exc_info:
        resolve_youtube_stream(
            "https://user:password@youtube.com/watch?v=dQw4w9WgXcQ&token=input-secret"
        )

    serialized = json.dumps(exc_info.value.diagnostics) + str(exc_info.value)
    for secret in ("stream-secret", "cookie-secret", "input-secret", "password"):
        assert secret not in serialized
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    rendered_traceback = "".join(
        traceback.format_exception(
            type(exc_info.value), exc_info.value, exc_info.value.__traceback__
        )
    )
    assert "stream-secret" not in rendered_traceback
    assert "cookie-secret" not in rendered_traceback


def test_resolve_youtube_stream_ignores_malformed_untrusted_ranking_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed height/tbr metadata neither raises nor exposes signed URL values."""
    info = {
        "duration": 12.5,
        "formats": [
            {
                "url": "https://media.invalid/bad-height?token=height-url-secret",
                "vcodec": "avc1",
                "height": "https://attacker.invalid/?secret=height-url-secret",
                "tbr": 999999,
            },
            {
                "url": "https://media.invalid/bad-tbr?token=tbr-url-secret",
                "vcodec": "avc1",
                "height": 720,
                "tbr": "https://attacker.invalid/?secret=tbr-url-secret",
            },
            {
                "url": "https://media.invalid/good",
                "vcodec": "avc1",
                "height": 360,
                "tbr": 800,
            },
        ],
    }
    youtube_dl = MagicMock()
    youtube_dl.return_value.__enter__.return_value.extract_info.return_value = info
    monkeypatch.setattr("gobbler_core.converters.youtube_frames.yt_dlp.YoutubeDL", youtube_dl)

    stream = resolve_youtube_stream("https://youtube.com/watch?v=dQw4w9WgXcQ")

    assert stream.url == "https://media.invalid/good"


def test_resolve_youtube_stream_sanitizes_all_malformed_ranking_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All-invalid ranking metadata fails without retaining attacker-controlled strings."""
    info = {
        "duration": 12.5,
        "formats": [
            {
                "url": "https://media.invalid/video?signature=signed-secret",
                "vcodec": "avc1",
                "height": "https://attacker.invalid/?secret=height-secret",
                "tbr": "nan",
            }
        ],
    }
    youtube_dl = MagicMock()
    youtube_dl.return_value.__enter__.return_value.extract_info.return_value = info
    monkeypatch.setattr("gobbler_core.converters.youtube_frames.yt_dlp.YoutubeDL", youtube_dl)

    with pytest.raises(YouTubeFrameError) as exc_info:
        resolve_youtube_stream("https://youtube.com/watch?v=dQw4w9WgXcQ")

    serialized = str(exc_info.value) + json.dumps(exc_info.value.diagnostics)
    for secret in ("signed-secret", "height-secret", "attacker.invalid"):
        assert secret not in serialized


def test_resolve_youtube_stream_does_not_misclassify_webpage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The word webpage does not accidentally classify a failure as age restricted."""
    youtube_dl = MagicMock()
    youtube_dl.return_value.__enter__.return_value.extract_info.side_effect = RuntimeError(
        "Unable to download webpage"
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames.yt_dlp.YoutubeDL", youtube_dl)

    with pytest.raises(YouTubeFrameError) as exc_info:
        resolve_youtube_stream("https://youtube.com/watch?v=dQw4w9WgXcQ")

    assert exc_info.value.diagnostics["error_type"] == "unavailable"


@pytest.mark.asyncio
async def test_extract_youtube_frames_partial_success_and_refresh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Expired streams refresh once and only failed targets are retried."""
    calls: list[tuple[float, str]] = []
    refreshed = MagicMock(return_value=MagicMock(url="refreshed", duration_seconds=20.0))

    async def fake_extract(stream_url: str, target: FrameTarget, final_path: Path) -> object:
        calls.append((target.timestamp_seconds, stream_url))
        if target.timestamp_seconds == 2 and stream_url == "initial":
            return FrameFailure(2, "00:02.000", "exact", "stream_expired", "Stream expired")
        if target.timestamp_seconds == 3:
            return FrameFailure(3, "00:03.000", "exact", "ffmpeg_failed", "Decode failed")
        final_path.write_bytes(b"jpeg")
        return VideoFrameArtifact(
            target.timestamp_seconds,
            format_frame_timestamp(target.timestamp_seconds),
            final_path,
            "image/jpeg",
            target.selector,
        )

    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", fake_extract)

    result = await extract_youtube_frames(
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        [FrameTarget(1, "exact"), FrameTarget(2, "exact"), FrameTarget(3, "exact")],
        tmp_path,
        stream_info=MagicMock(url="initial", duration_seconds=20.0),
        stream_resolver=refreshed,
    )

    assert [frame.timestamp_seconds for frame in result.frames] == [1, 2]
    assert [failure.timestamp_seconds for failure in result.failures] == [3]
    assert refreshed.call_count == 1
    assert calls.count((1, "initial")) == 1


@pytest.mark.asyncio
async def test_refresh_failure_preserves_initially_successful_frames(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A failed refresh remains a warning when another requested frame succeeded."""

    async def fake_extract(
        _stream_url: str, target: FrameTarget, final_path: Path
    ) -> VideoFrameArtifact | FrameFailure:
        if target.timestamp_seconds == 2:
            return FrameFailure(
                2,
                "00:02.000",
                "exact",
                "stream_expired",
                "YouTube video stream expired",
            )
        final_path.write_bytes(b"jpeg")
        return VideoFrameArtifact(1, "00:01.000", final_path, "image/jpeg", "exact")

    def failed_refresh(_url: str) -> YouTubeStreamInfo:
        message = "refresh transport detail"
        raise RuntimeError(message)

    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", fake_extract)

    result = await extract_youtube_frames(
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        [FrameTarget(1, "exact"), FrameTarget(2, "exact")],
        tmp_path,
        stream_info=MagicMock(url="initial", duration_seconds=20.0),
        stream_resolver=failed_refresh,
    )

    assert [frame.timestamp_seconds for frame in result.frames] == [1]
    assert [failure.error_type for failure in result.failures] == ["stream_expired"]


@pytest.mark.asyncio
async def test_extract_youtube_frames_replaces_owned_bundle_without_touching_unrelated_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A new selector set removes stale Gobbler frames and only those artifacts."""
    frames_dir = tmp_path / "selected-frames"
    frames_dir.mkdir()
    stale_paths = {
        frames_dir / "frame-001-00-00-01-000.jpg",
        frames_dir / "frame-002-00-00-02-000.jpg",
        frames_dir / "frame-003-00-00-03-000.part.jpg",
    }
    for stale_path in stale_paths:
        stale_path.write_bytes(b"stale")
    unrelated_paths = {
        frames_dir / "cover.jpg",
        frames_dir / "frame-cover.jpg",
        frames_dir / "notes.txt",
        tmp_path / "frame-999-00-00-09-000.jpg",
    }
    for unrelated_path in unrelated_paths:
        unrelated_path.write_bytes(b"keep")

    async def fake_extract(
        _stream_url: str, target: FrameTarget, final_path: Path
    ) -> VideoFrameArtifact:
        final_path.write_bytes(b"new")
        return VideoFrameArtifact(
            target.timestamp_seconds,
            format_frame_timestamp(target.timestamp_seconds),
            final_path,
            "image/jpeg",
            target.selector,
        )

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.ensure_ffmpeg_available", lambda: None
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", fake_extract)

    result = await extract_youtube_frames(
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        [FrameTarget(8, "range")],
        frames_dir,
        stream_info=MagicMock(url="initial", duration_seconds=20.0),
    )

    assert [frame.path.name for frame in result.frames] == ["frame-001-00-00-08-000.jpg"]
    assert result.frames[0].path.read_bytes() == b"new"
    assert all(not stale_path.exists() for stale_path in stale_paths)
    assert all(unrelated_path.read_bytes() == b"keep" for unrelated_path in unrelated_paths)
    assert not list(tmp_path.glob(".gobbler-frame-stage-*"))


@pytest.mark.asyncio
async def test_extract_youtube_frames_stages_next_to_resolved_symlink_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Symlinked frame directories stage and rename on the actual target filesystem."""
    actual_parent = tmp_path / "actual-volume"
    actual_frames = actual_parent / "frames"
    actual_frames.mkdir(parents=True)
    link_parent = tmp_path / "links"
    link_parent.mkdir()
    linked_frames = link_parent / "frames"
    linked_frames.symlink_to(actual_frames, target_is_directory=True)
    observed_staging_parents: list[Path] = []

    async def fake_extract(
        _stream_url: str, target: FrameTarget, final_path: Path
    ) -> VideoFrameArtifact:
        observed_staging_parents.append(final_path.parent.parent)
        final_path.write_bytes(b"new")
        return VideoFrameArtifact(
            target.timestamp_seconds,
            format_frame_timestamp(target.timestamp_seconds),
            final_path,
            "image/jpeg",
            target.selector,
        )

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.ensure_ffmpeg_available", lambda: None
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", fake_extract)

    result = await extract_youtube_frames(
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        [FrameTarget(2, "exact")],
        linked_frames,
        stream_info=YouTubeStreamInfo("stream", 10.0),
    )

    assert observed_staging_parents == [actual_parent]
    assert linked_frames.is_symlink()
    assert result.frames[0].path.parent == actual_frames
    assert result.frames[0].path.read_bytes() == b"new"


@pytest.mark.asyncio
async def test_extract_youtube_frames_serializes_same_canonical_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Concurrent replacements for one canonical directory cannot interleave."""
    frames_dir = tmp_path / "frames"
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    second_started = asyncio.Event()

    async def fake_extract(
        stream_url: str, target: FrameTarget, final_path: Path
    ) -> VideoFrameArtifact:
        if stream_url == "first":
            first_started.set()
            await release_first.wait()
        else:
            second_started.set()
        final_path.write_bytes(stream_url.encode())
        return VideoFrameArtifact(
            target.timestamp_seconds,
            format_frame_timestamp(target.timestamp_seconds),
            final_path,
            "image/jpeg",
            target.selector,
        )

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.ensure_ffmpeg_available", lambda: None
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", fake_extract)

    first = asyncio.create_task(
        extract_youtube_frames(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            [FrameTarget(1, "exact")],
            frames_dir,
            stream_info=YouTubeStreamInfo("first", 10.0),
        )
    )
    await first_started.wait()
    second = asyncio.create_task(
        extract_youtube_frames(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            [FrameTarget(2, "exact")],
            frames_dir,
            stream_info=YouTubeStreamInfo("second", 10.0),
        )
    )
    await asyncio.sleep(0.03)

    assert not second_started.is_set()
    release_first.set()
    await asyncio.gather(first, second)

    assert second_started.is_set()
    assert [path.read_bytes() for path in frames_dir.glob("frame-*.jpg")] == [b"second"]


def test_concurrent_different_frame_dirs_serialize_same_output_transaction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """One canonical manifest cannot interleave across otherwise independent bundles."""
    output = tmp_path / "shared.md"
    output.write_text("previous", encoding="utf-8")
    first_finalizing = threading.Event()
    release_first = threading.Event()
    second_finished = threading.Event()
    errors: list[BaseException] = []

    async def fake_extract(
        stream_url: str, target: FrameTarget, final_path: Path
    ) -> VideoFrameArtifact:
        final_path.write_bytes(stream_url.encode())
        return VideoFrameArtifact(1, "00:01.000", final_path, "image/jpeg", target.selector)

    def worker(name: str, frames_dir: Path) -> None:
        def persist_manifest(_result: FrameExtractionResult) -> FrameCommitHooks:
            transaction = persist_text_transactionally(name, output)

            def finalize() -> None:
                if name == "first":
                    first_finalizing.set()
                    assert release_first.wait(timeout=1)
                transaction.finalize()

            return FrameCommitHooks(transaction.rollback, finalize)

        try:
            asyncio.run(
                extract_youtube_frames(
                    "https://youtube.com/watch?v=dQw4w9WgXcQ",
                    [FrameTarget(1, "exact")],
                    frames_dir,
                    stream_info=YouTubeStreamInfo(name, 10.0),
                    before_commit=persist_manifest,
                )
            )
        except BaseException as error:
            errors.append(error)
        finally:
            if name == "second":
                second_finished.set()

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.ensure_ffmpeg_available", lambda: None
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", fake_extract)

    first = threading.Thread(target=worker, args=("first", tmp_path / "frames-one"))
    first.start()
    assert first_finalizing.wait(timeout=1)
    second = threading.Thread(target=worker, args=("second", tmp_path / "frames-two"))
    second.start()
    time.sleep(0.05)

    assert not second_finished.is_set()
    release_first.set()
    first.join(timeout=1)
    second.join(timeout=1)

    assert not errors
    assert second_finished.is_set()
    assert output.read_text(encoding="utf-8") == "second"


@pytest.mark.asyncio
async def test_manifest_is_persisted_before_bundle_visibility_and_finalized_after_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Output persistence precedes bundle visibility and remains rollback-capable."""
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    previous_frame = frames_dir / "frame-001-00-00-01-000.jpg"
    previous_frame.write_bytes(b"previous")
    output = tmp_path / "manifest.md"
    output.write_text("previous manifest", encoding="utf-8")
    events: list[str] = []

    async def fake_extract(
        _stream_url: str, target: FrameTarget, final_path: Path
    ) -> VideoFrameArtifact:
        final_path.write_bytes(b"new")
        return VideoFrameArtifact(2, "00:02.000", final_path, "image/jpeg", target.selector)

    def persist_manifest(result: FrameExtractionResult) -> FrameCommitHooks:
        assert previous_frame.read_bytes() == b"previous"
        assert result.frames[0].path.parent == frames_dir
        transaction = persist_text_transactionally("new manifest", output)
        events.append("persisted")

        def finalize() -> None:
            assert result.frames[0].path.read_bytes() == b"new"
            events.append("finalized")
            transaction.finalize()

        return FrameCommitHooks(rollback=transaction.rollback, finalize=finalize)

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.ensure_ffmpeg_available", lambda: None
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", fake_extract)

    await extract_youtube_frames(
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        [FrameTarget(2, "exact")],
        frames_dir,
        stream_info=YouTubeStreamInfo("stream", 10.0),
        before_commit=persist_manifest,
    )

    assert events == ["persisted", "finalized"]
    assert output.read_text(encoding="utf-8") == "new manifest"
    assert not list(tmp_path.glob(".manifest.md.gobbler-backup-*"))


@pytest.mark.asyncio
async def test_frame_commit_failure_rolls_back_persisted_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A failed bundle swap restores both the prior manifest and prior frames."""
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    previous_frame = frames_dir / "frame-001-00-00-01-000.jpg"
    previous_frame.write_bytes(b"previous")
    output = tmp_path / "manifest.md"
    output.write_text("previous manifest", encoding="utf-8")
    original_replace = Path.replace

    async def fake_extract(
        _stream_url: str, target: FrameTarget, final_path: Path
    ) -> VideoFrameArtifact:
        final_path.write_bytes(b"new")
        return VideoFrameArtifact(2, "00:02.000", final_path, "image/jpeg", target.selector)

    def fail_new_frame_replace(path: Path, target: Path) -> Path:
        if path.parent.name.startswith(".gobbler-frame-stage-") and target.parent == frames_dir:
            message = "secret commit failure"
            raise PermissionError(message)
        return original_replace(path, target)

    def persist_manifest(_result: FrameExtractionResult) -> FrameCommitHooks:
        transaction = persist_text_transactionally("new manifest", output)
        return FrameCommitHooks(transaction.rollback, transaction.finalize)

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.ensure_ffmpeg_available", lambda: None
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", fake_extract)
    monkeypatch.setattr(Path, "replace", fail_new_frame_replace)

    with pytest.raises(YouTubeFrameError, match="Unable to replace"):
        await extract_youtube_frames(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            [FrameTarget(2, "exact")],
            frames_dir,
            stream_info=YouTubeStreamInfo("stream", 10.0),
            before_commit=persist_manifest,
        )

    assert output.read_text(encoding="utf-8") == "previous manifest"
    assert previous_frame.read_bytes() == b"previous"
    assert not list(tmp_path.glob(".gobbler-frame-stage-*"))


@pytest.mark.asyncio
async def test_failed_frame_rollback_preserves_backup_and_reports_stable_diagnostic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unrestorable prior bundle remains in staging for manual recovery."""
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    previous_frame = frames_dir / "frame-001-00-00-01-000.jpg"
    previous_frame.write_bytes(b"previous")
    original_replace = Path.replace

    async def fake_extract(
        _stream_url: str, target: FrameTarget, final_path: Path
    ) -> VideoFrameArtifact:
        final_path.write_bytes(b"new")
        return VideoFrameArtifact(2, "00:02.000", final_path, "image/jpeg", target.selector)

    def fail_commit_and_restore(path: Path, target: Path) -> Path:
        if path.parent.name.startswith(".gobbler-frame-stage-") and target.parent == frames_dir:
            message = "secret commit failure"
            raise PermissionError(message)
        if path.parent.name == "previous":
            message = "secret restore failure"
            raise PermissionError(message)
        return original_replace(path, target)

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.ensure_ffmpeg_available", lambda: None
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", fake_extract)
    monkeypatch.setattr(Path, "replace", fail_commit_and_restore)

    with pytest.raises(YouTubeFrameError) as exc_info:
        await extract_youtube_frames(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            [FrameTarget(2, "exact")],
            frames_dir,
            stream_info=YouTubeStreamInfo("stream", 10.0),
        )

    assert str(exc_info.value) == (
        "Unable to restore previous YouTube frame artifacts; backups were preserved"
    )
    assert exc_info.value.diagnostics["stage"] == "frame_rollback"
    stages = list(tmp_path.glob(".gobbler-frame-stage-*"))
    assert len(stages) == 1
    assert (stages[0] / "previous" / previous_frame.name).read_bytes() == b"previous"


@pytest.mark.asyncio
async def test_staging_cleanup_failure_is_reported_and_not_silent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A reported success can never silently retain a frame staging directory."""
    frames_dir = tmp_path / "frames"

    async def fake_extract(
        _stream_url: str, target: FrameTarget, final_path: Path
    ) -> VideoFrameArtifact:
        final_path.write_bytes(b"new")
        return VideoFrameArtifact(2, "00:02.000", final_path, "image/jpeg", target.selector)

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.ensure_ffmpeg_available", lambda: None
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", fake_extract)
    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.shutil.rmtree",
        MagicMock(side_effect=PermissionError("secret cleanup failure")),
    )

    with pytest.raises(YouTubeFrameError) as exc_info:
        await extract_youtube_frames(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            [FrameTarget(2, "exact")],
            frames_dir,
            stream_info=YouTubeStreamInfo("stream", 10.0),
        )

    assert str(exc_info.value) == "Unable to clean up staged YouTube frame artifacts"
    assert exc_info.value.diagnostics["stage"] == "frame_cleanup"
    assert "secret" not in str(exc_info.value) + json.dumps(exc_info.value.diagnostics)
    assert list(tmp_path.glob(".gobbler-frame-stage-*"))


@pytest.mark.asyncio
async def test_staging_cleanup_failure_still_finalizes_manifest_transaction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A post-commit cleanup error cannot strand the output backup or lock."""
    frames_dir = tmp_path / "frames"
    output = tmp_path / "manifest.md"
    output.write_text("previous", encoding="utf-8")
    finalized = False

    async def fake_extract(
        _stream_url: str, target: FrameTarget, final_path: Path
    ) -> VideoFrameArtifact:
        final_path.write_bytes(b"new")
        return VideoFrameArtifact(2, "00:02.000", final_path, "image/jpeg", target.selector)

    def persist_manifest(_result: FrameExtractionResult) -> FrameCommitHooks:
        transaction = persist_text_transactionally("new manifest", output)

        def finalize() -> None:
            nonlocal finalized
            finalized = True
            transaction.finalize()

        return FrameCommitHooks(transaction.rollback, finalize)

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.ensure_ffmpeg_available", lambda: None
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", fake_extract)
    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.shutil.rmtree",
        MagicMock(side_effect=PermissionError("secret cleanup failure")),
    )

    with pytest.raises(YouTubeFrameError, match="Unable to clean up staged"):
        await extract_youtube_frames(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            [FrameTarget(2, "exact")],
            frames_dir,
            stream_info=YouTubeStreamInfo("stream", 10.0),
            before_commit=persist_manifest,
        )

    assert finalized
    assert output.read_text(encoding="utf-8") == "new manifest"
    assert not list(tmp_path.glob(".manifest.md.gobbler-backup-*"))


@pytest.mark.asyncio
async def test_staging_part_unlink_failure_is_contained_by_directory_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Part-file unlink errors do not leak staging paths when rmtree owns cleanup."""
    frames_dir = tmp_path / "private-frames"
    original_unlink = Path.unlink

    async def fake_extract(
        _stream_url: str, target: FrameTarget, final_path: Path
    ) -> VideoFrameArtifact:
        final_path.write_bytes(b"new")
        return VideoFrameArtifact(2, "00:02.000", final_path, "image/jpeg", target.selector)

    def fail_part_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path.name.endswith(".part.jpg"):
            message = f"private staging path: {path}"
            raise PermissionError(message)
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.ensure_ffmpeg_available", lambda: None
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", fake_extract)
    monkeypatch.setattr(Path, "unlink", fail_part_unlink)

    result = await extract_youtube_frames(
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        [FrameTarget(2, "exact")],
        frames_dir,
        stream_info=YouTubeStreamInfo("stream", 10.0),
    )

    assert result.frames[0].path.read_bytes() == b"new"
    assert not list(tmp_path.glob(".gobbler-frame-stage-*"))


@pytest.mark.asyncio
async def test_extract_youtube_frames_commit_failure_preserves_previous_bundle_and_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unmovable owned artifact preserves the prior bundle with stable diagnostics."""
    frames_dir = tmp_path / "local-secret-frames"
    frames_dir.mkdir()
    stale_path = frames_dir / "frame-001-00-00-01-000.jpg"
    stale_path.write_bytes(b"stale")
    extraction_calls = 0
    original_replace = Path.replace

    async def extract_success(
        _stream_url: str, target: FrameTarget, final_path: Path
    ) -> VideoFrameArtifact:
        nonlocal extraction_calls
        extraction_calls += 1
        final_path.write_bytes(b"new")
        return VideoFrameArtifact(
            target.timestamp_seconds,
            "00:08.000",
            final_path,
            "image/jpeg",
            target.selector,
        )

    def fail_selected_replace(path: Path, target: Path) -> Path:
        if path == stale_path:
            message = "local-secret: access denied"
            raise PermissionError(message)
        return original_replace(path, target)

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.ensure_ffmpeg_available", lambda: None
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", extract_success)
    monkeypatch.setattr(Path, "replace", fail_selected_replace)

    with pytest.raises(YouTubeFrameError) as exc_info:
        await extract_youtube_frames(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            [FrameTarget(8, "exact")],
            frames_dir,
            stream_info=MagicMock(url="signed-stream", duration_seconds=20.0),
        )

    assert str(exc_info.value) == "Unable to replace existing YouTube frame artifacts"
    assert exc_info.value.diagnostics == {
        "error_type": "filesystem_error",
        "stage": "frame_commit",
    }
    assert "local-secret" not in json.dumps(exc_info.value.diagnostics) + str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    rendered_traceback = "".join(
        traceback.format_exception(
            type(exc_info.value), exc_info.value, exc_info.value.__traceback__
        )
    )
    assert "local-secret" not in rendered_traceback
    assert extraction_calls == 1
    assert stale_path.read_bytes() == b"stale"


@pytest.mark.asyncio
async def test_extract_youtube_frames_all_failed_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An invocation with no successful frame fails as a whole."""

    async def fail_extract(*_args: object) -> FrameFailure:
        return FrameFailure(1, "00:01.000", "exact", "ffmpeg_failed", "failed")

    previous_frame = tmp_path / "frame-001-00-00-01-000.jpg"
    previous_frame.write_bytes(b"previous")
    monkeypatch.setattr("gobbler_core.converters.youtube_frames._extract_frame", fail_extract)
    with pytest.raises(YouTubeFrameError, match="No YouTube frames"):
        await extract_youtube_frames(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            [FrameTarget(1, "exact")],
            tmp_path,
            stream_info=MagicMock(url="initial", duration_seconds=20.0),
        )
    assert previous_frame.read_bytes() == b"previous"


def test_manifest_path_cannot_occupy_owned_frame_namespace(tmp_path: Path) -> None:
    """A manifest cannot be swept or replaced as a generated frame artifact."""
    frames_dir = tmp_path / "frames"
    output = frames_dir / "frame-001-00-00-01-000.jpg"

    with pytest.raises(YouTubeFrameRequestError, match="owned frame filename"):
        validate_frame_manifest_path(output, frames_dir)


def test_manifest_symlink_cannot_alias_owned_frame_namespace(tmp_path: Path) -> None:
    """Canonical validation catches a benignly named symlink to an owned frame path."""
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    owned_target = frames_dir / "frame-001-00-00-01-000.jpg"
    owned_target.write_bytes(b"previous manifest")
    output_alias = tmp_path / "manifest.md"
    output_alias.symlink_to(owned_target)

    with pytest.raises(YouTubeFrameRequestError, match="owned frame filename"):
        validate_frame_manifest_path(output_alias, frames_dir)


def test_owned_frame_symlink_cannot_alias_external_manifest(tmp_path: Path) -> None:
    """Lexical validation catches an owned-name symlink to a benign external target."""
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    manifest = tmp_path / "manifest.md"
    manifest.write_text("previous manifest", encoding="utf-8")
    owned_alias = frames_dir / "frame-001-00-00-01-000.jpg"
    owned_alias.symlink_to(manifest)

    with pytest.raises(YouTubeFrameRequestError, match="owned frame filename"):
        validate_frame_manifest_path(owned_alias, frames_dir)


def test_render_manifest_uses_relative_deterministic_paths(tmp_path: Path) -> None:
    """Markdown and metadata link stable artifacts relative to the output parent."""
    output = tmp_path / "video.md"
    frames_dir = derive_frames_dir(output, None)
    artifact = VideoFrameArtifact(
        1456.5,
        "24:16.500",
        frames_dir / "frame-001-00-24-16-500.jpg",
        "image/jpeg",
        "exact",
    )
    result = FrameExtractionResult(
        frames=[artifact],
        failures=[FrameFailure(5, "00:05.000", "range", "ffmpeg_failed", "Decode failed")],
        duration_seconds=1500,
    )

    markdown = render_frames_markdown(result.frames, output_path=output)
    metadata = build_frame_metadata(result, output_path=output, frames_dir=frames_dir)

    assert frames_dir == tmp_path / "video.assets" / "frames"
    assert "video.assets/frames/frame-001-00-24-16-500.jpg" in markdown
    assert metadata["frames"][0]["path"] == "video.assets/frames/frame-001-00-24-16-500.jpg"
    assert metadata["frame_summary"] == {
        "requested": 2,
        "extracted": 1,
        "failed": 1,
        "frames_dir": "video.assets/frames",
    }
    assert metadata["warnings"][0]["timestamp"] == "00:05.000"


def test_render_markdown_warnings_use_stable_sanitized_failure_details(tmp_path: Path) -> None:
    """Markdown warnings expose useful fields without rendering raw failure details."""
    output = tmp_path / "video.md"
    artifact = VideoFrameArtifact(
        1.0,
        "00:01.000",
        tmp_path / "video.assets/frames/frame-001-00-00-01-000.jpg",
        "image/jpeg",
        "exact",
    )
    failure = FrameFailure(
        5.0,
        "00:05.000",
        "range",
        "ffmpeg_failed",
        (
            "raw stderr https://media.invalid/video?signature=signed-secret "
            "/Users/example/local-secret"
        ),
    )

    result = FrameExtractionResult(frames=[artifact], failures=[failure], duration_seconds=10.0)
    markdown = render_frames_markdown(result.frames, output_path=output)
    markdown += render_frame_warnings_markdown(result.failures)
    metadata = build_frame_metadata(
        result,
        output_path=output,
        frames_dir=artifact.path.parent,
    )

    assert "## Frame Warnings" in markdown
    assert "00:05.000" in markdown
    assert "range" in markdown
    assert "ffmpeg_failed" in markdown
    assert "FFmpeg could not decode this frame" in markdown
    for secret in ("raw stderr", "signed-secret", "local-secret", "media.invalid"):
        assert secret not in markdown
        assert secret not in json.dumps(metadata)
    assert metadata["warnings"][0]["message"] == "FFmpeg could not decode this frame"


def test_manifest_relpath_failure_falls_back_to_absolute_filesystem_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A Windows different-drive relpath failure cannot discard extracted results."""
    relative_output = Path("reports/video.md")
    relative_frames_dir = Path("external frames (draft)#%")
    artifact = VideoFrameArtifact(
        1.0,
        "00:01.000",
        relative_frames_dir / "frame-001-00-00-01-000.jpg",
        "image/jpeg",
        "exact",
    )
    result = FrameExtractionResult(frames=[artifact], duration_seconds=2.0)

    def different_drive_relpath(_path: object, _start: object) -> str:
        message = "path is on mount 'D:', start on mount 'C:'"
        raise ValueError(message)

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.os.path.relpath", different_drive_relpath
    )

    markdown = render_frames_markdown(result.frames, output_path=relative_output)
    metadata = build_frame_metadata(
        result,
        output_path=relative_output,
        frames_dir=relative_frames_dir,
    )

    absolute_frame_path = str(artifact.path.absolute())
    absolute_frames_dir = str(relative_frames_dir.absolute())
    assert metadata["frames"][0]["path"] == absolute_frame_path
    assert metadata["frame_summary"]["frames_dir"] == absolute_frames_dir
    assert "%20" in markdown
    assert "%28" in markdown
    assert "%29" in markdown
    assert "%23" in markdown
    assert "%25" in markdown
    assert absolute_frame_path not in markdown


@pytest.mark.parametrize("explicit", [False, True])
def test_render_markdown_encodes_sensitive_path_characters_without_changing_manifest(
    tmp_path: Path, explicit: bool
) -> None:
    """Markdown destinations are encoded while JSON paths remain filesystem paths."""
    output = tmp_path / "video (draft)#%.md"
    frames_dir = derive_frames_dir(
        output,
        tmp_path / "explicit frames (draft)#%" if explicit else None,
    )
    artifact = VideoFrameArtifact(
        1.0,
        "00:01.000",
        frames_dir / "frame (one)#%.jpg",
        "image/jpeg",
        "exact",
    )
    result = FrameExtractionResult(frames=[artifact], duration_seconds=2.0)

    markdown = render_frames_markdown(result.frames, output_path=output)
    metadata = build_frame_metadata(result, output_path=output, frames_dir=frames_dir)

    display_path = metadata["frames"][0]["path"]
    assert isinstance(display_path, str)
    assert display_path in {
        "video (draft)#%.assets/frames/frame (one)#%.jpg",
        "explicit frames (draft)#%/frame (one)#%.jpg",
    }
    assert display_path not in markdown
    assert "%20" in markdown
    assert "%28" in markdown
    assert "%29" in markdown
    assert "%23" in markdown
    assert "%25" in markdown


def test_windows_different_drive_markdown_path_is_encoded_file_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Different-drive Windows artifacts render as valid encoded file URIs."""
    output = PureWindowsPath(r"C:\reports\video.md")
    frame_path = PureWindowsPath(r"D:\frame assets\shot #1%.jpg")
    artifact = VideoFrameArtifact(1.0, "00:01.000", frame_path, "image/jpeg", "exact")  # type: ignore[arg-type]

    monkeypatch.setattr("gobbler_core.converters.youtube_frames.os.path", ntpath)
    markdown = render_frames_markdown([artifact], output_path=output)  # type: ignore[arg-type]

    assert "file:///D:/frame%20assets/shot%20%231%25.jpg" in markdown

    metadata = build_frame_metadata(
        FrameExtractionResult(frames=[artifact]),
        output_path=output,  # type: ignore[arg-type]
        frames_dir=frame_path.parent,  # type: ignore[arg-type]
    )
    assert metadata["frames"][0]["path"] == str(frame_path)  # type: ignore[index]


def test_windows_same_drive_markdown_path_remains_relative(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same-drive Windows artifacts retain portable relative links."""
    output = PureWindowsPath(r"C:\reports\video.md")
    frame_path = PureWindowsPath(r"C:\reports\video.assets\frames\shot 1.jpg")
    artifact = VideoFrameArtifact(1.0, "00:01.000", frame_path, "image/jpeg", "exact")  # type: ignore[arg-type]

    monkeypatch.setattr("gobbler_core.converters.youtube_frames.os.path", ntpath)
    markdown = render_frames_markdown([artifact], output_path=output)  # type: ignore[arg-type]

    assert "video.assets/frames/shot%201.jpg" in markdown
    assert "file:" not in markdown


def test_windows_unc_markdown_path_is_encoded_file_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    """UNC artifacts use an authority-bearing file URI with encoded path segments."""
    output = PureWindowsPath(r"C:\reports\video.md")
    frame_path = PureWindowsPath(r"\\media-server\shared frames\shot #1%.jpg")
    artifact = VideoFrameArtifact(1.0, "00:01.000", frame_path, "image/jpeg", "exact")  # type: ignore[arg-type]

    monkeypatch.setattr("gobbler_core.converters.youtube_frames.os.path", ntpath)
    markdown = render_frames_markdown([artifact], output_path=output)  # type: ignore[arg-type]

    assert "file://media-server/shared%20frames/shot%20%231%25.jpg" in markdown


@pytest.mark.asyncio
async def test_extract_frame_uses_list_argv_and_atomic_part_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """FFmpeg receives list argv and a validated temporary JPEG is finalized."""
    observed: dict[str, object] = {}

    async def fake_create_subprocess_exec(*command: str, **kwargs: object) -> object:
        observed["command"] = list(command)
        observed["kwargs"] = kwargs
        Path(command[-1]).write_bytes(b"jpeg")
        return _CompletedFFmpegProcess(0, b"")

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    final_path = tmp_path / "frame.jpg"

    result = await _extract_frame(
        "https://media.invalid/video?signature=stream-secret",
        FrameTarget(1.125, "exact"),
        final_path,
    )

    assert isinstance(observed["command"], list)
    assert "shell" not in observed["kwargs"]
    command = observed["command"]
    assert command[command.index("-ss") + 1] == "1.125"
    assert command[command.index("-frames:v") + 1] == "1"
    assert str(command[-1]).endswith(".part.jpg")
    assert isinstance(result, VideoFrameArtifact)
    assert final_path.read_bytes() == b"jpeg"
    assert not list(tmp_path.glob("*.part.jpg"))


@pytest.mark.asyncio
async def test_extract_frame_classifies_expiry_without_leaking_stderr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Signed transport details are reduced to a stable expired-stream failure."""
    stderr = (
        "HTTP error 403 for https://media.invalid/video?signature=stream-secret "
        "cookie=cookie-secret"
    )

    async def fake_create_subprocess_exec(*_args: str, **_kwargs: object) -> object:
        return _CompletedFFmpegProcess(1, stderr.encode())

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    result = await _extract_frame(
        "https://media.invalid/video?signature=stream-secret",
        FrameTarget(1, "exact"),
        tmp_path / "frame.jpg",
    )

    assert isinstance(result, FrameFailure)
    assert result.error_type == "stream_expired"
    serialized = json.dumps(result.__dict__)
    assert "stream-secret" not in serialized
    assert "cookie-secret" not in serialized


class _CompletedFFmpegProcess:
    """Minimal completed async subprocess double."""

    def __init__(self, returncode: int, stderr: bytes) -> None:
        """Store the completed status and sanitized test output."""
        self.returncode = returncode
        self.stderr = stderr

    async def communicate(self) -> tuple[bytes, bytes]:
        """Return completed process pipes."""
        return b"", self.stderr


class _HangingFFmpegProcess:
    """Controllable async subprocess double that attempts one delayed write."""

    def __init__(self, temp_path: Path) -> None:
        """Initialize process lifecycle state for cancellation assertions."""
        self.temp_path = temp_path
        self.returncode: int | None = None
        self.started = asyncio.Event()
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = 0
        self.reaped = False
        self._late_write: asyncio.TimerHandle | None = None

    async def communicate(self) -> tuple[bytes, bytes]:
        """Hang until cancelled while scheduling a simulated late FFmpeg write."""
        self.started.set()
        loop = asyncio.get_running_loop()
        self._late_write = loop.call_later(0.05, self.temp_path.write_bytes, b"late-jpeg")
        await asyncio.Future()
        return b"", b""

    def terminate(self) -> None:
        """Terminate the process and suppress its pending write."""
        self.terminate_calls += 1
        self.returncode = -15
        if self._late_write is not None:
            self._late_write.cancel()

    def kill(self) -> None:
        """Force-kill the process and suppress its pending write."""
        self.kill_calls += 1
        self.returncode = -9
        if self._late_write is not None:
            self._late_write.cancel()

    async def wait(self) -> int:
        """Record that the terminated child was reaped."""
        self.wait_calls += 1
        self.reaped = True
        assert self.returncode is not None
        return self.returncode


class _OSErrorFFmpegProcess(_HangingFFmpegProcess):
    """Running process double whose communicate call fails with an OS error."""

    async def communicate(self) -> tuple[bytes, bytes]:
        """Raise after process creation while the child is still running."""
        message = "signed URL https://media.invalid/?token=process-secret"
        raise OSError(message)


@pytest.mark.asyncio
async def test_extract_frame_oserror_after_creation_terminates_and_reaps_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Communicate OS errors return only after the running child is reaped."""
    process = _OSErrorFFmpegProcess(tmp_path / "frame.part.jpg")

    async def fake_create_subprocess_exec(*_args: str, **_kwargs: object) -> object:
        return process

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    result = await _extract_frame(
        "https://media.invalid/video?signature=stream-secret",
        FrameTarget(1, "exact"),
        tmp_path / "frame.jpg",
    )

    assert isinstance(result, FrameFailure)
    assert result.error_type == "filesystem_error"
    assert process.terminate_calls == 1
    assert process.reaped is True
    assert "process-secret" not in json.dumps(result.__dict__)


@pytest.mark.asyncio
async def test_extract_frame_temp_unlink_error_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Standalone part-file cleanup errors never expose their canonical path."""
    final_path = tmp_path / "private-output" / "frame.jpg"
    final_path.parent.mkdir()
    private_path = str(final_path.parent)
    original_unlink = Path.unlink

    def fail_part_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path.name.endswith(".part.jpg"):
            message = f"cannot unlink {path}"
            raise PermissionError(message)
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_part_unlink)

    result = await _extract_frame(
        "https://media.invalid/video?signature=stream-secret",
        FrameTarget(1, "exact"),
        final_path,
    )

    assert isinstance(result, FrameFailure)
    assert result.error_type == "filesystem_error"
    assert private_path not in json.dumps(result.__dict__)


@pytest.mark.asyncio
async def test_overall_timeout_terminates_reaps_and_prevents_late_frame_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Cancelling extraction reaps FFmpeg before temporary artifacts can outlive it."""
    processes: list[_HangingFFmpegProcess] = []

    async def fake_create_subprocess_exec(*command: str, **_kwargs: object) -> object:
        process = _HangingFFmpegProcess(Path(command[-1]))
        processes.append(process)
        return process

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.ensure_ffmpeg_available", lambda: None
    )

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(
            extract_youtube_frames(
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                [FrameTarget(float(index), "exact") for index in range(1, 5)],
                tmp_path,
                stream_info=MagicMock(url="initial", duration_seconds=20.0),
            ),
            timeout=0.01,
        )

    await asyncio.sleep(0.07)

    assert len(processes) == FFMPEG_CONCURRENCY
    assert all(process.terminate_calls == 1 for process in processes)
    assert all(process.wait_calls >= 1 for process in processes)
    assert all(process.reaped for process in processes)
    assert not list(tmp_path.glob("*.part.jpg"))
    assert not list(tmp_path.glob("*.jpg"))


@pytest.mark.asyncio
async def test_per_process_timeout_terminates_reaps_and_cleans_temp_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The FFmpeg timeout returns a sanitized failure only after child cleanup."""
    process: _HangingFFmpegProcess | None = None

    async def fake_create_subprocess_exec(*command: str, **_kwargs: object) -> object:
        nonlocal process
        process = _HangingFFmpegProcess(Path(command[-1]))
        return process

    monkeypatch.setattr(
        "gobbler_core.converters.youtube_frames.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr("gobbler_core.converters.youtube_frames.FFMPEG_TIMEOUT_SECONDS", 0.01)

    result = await _extract_frame(
        "https://media.invalid/video?signature=stream-secret",
        FrameTarget(1, "exact"),
        tmp_path / "frame.jpg",
    )

    assert isinstance(result, FrameFailure)
    assert result.error_type == "ffmpeg_timeout"
    assert process is not None
    assert process.terminate_calls == 1
    assert process.reaped is True
    assert not list(tmp_path.glob("*.part.jpg"))

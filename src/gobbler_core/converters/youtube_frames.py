"""Deterministic YouTube frame selection and JPEG extraction."""

# Ruff's exception-message rule obscures the pure validation paths in this module.
# Every message here is a fixed or selector-derived value and is covered by diagnostics tests.
# ruff: noqa: EM101, EM102

from __future__ import annotations

import asyncio
import math
import os
import re
import shutil
import tempfile
import threading
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal, DecimalException, InvalidOperation
from pathlib import Path, PureWindowsPath
from typing import Any, BinaryIO, Literal, NoReturn, cast
from urllib.parse import quote

import yt_dlp

FrameSelector = Literal["overview", "exact", "range"]

MAX_FRAMES_PER_INVOCATION = 48
MAX_FRAMES_PER_SELECTOR = 24
MAX_RAW_FRAME_SELECTORS = 48
FFMPEG_CONCURRENCY = 3
FFMPEG_TIMEOUT_SECONDS = 60
FFMPEG_TERMINATE_GRACE_SECONDS = 5
MAX_STREAM_HEIGHT = 720
MAX_UNTRUSTED_HEIGHT = 100_000
MAX_UNTRUSTED_TBR = 1_000_000_000
MIN_RANGE_FRAMES = 2
SECONDS_PER_MINUTE = 60
TIMESTAMP_COMPONENTS = 3
_MILLISECOND = Decimal("0.001")
_TIMESTAMP_PATTERN = re.compile(r"^\d+(?::\d+){0,2}(?:\.\d{1,3})?$")
_OWNED_FRAME_PATTERN = re.compile(r"^frame-\d{3}-\d{2,}-\d{2}-\d{2}-\d{3}(?:\.part)?\.jpg$")
_PROVENANCE_PRIORITY: dict[FrameSelector, int] = {"overview": 0, "range": 1, "exact": 2}
_FRAME_FAILURE_MESSAGES = {
    "empty_output": "FFmpeg produced no frame image",
    "ffmpeg_failed": "FFmpeg could not decode this frame",
    "ffmpeg_missing": "FFmpeg is required for YouTube frame extraction",
    "ffmpeg_timeout": "FFmpeg timed out while extracting this frame",
    "filesystem_error": "Unable to finalize the frame image",
    "stream_expired": "YouTube video stream expired",
}
_UNKNOWN_FRAME_FAILURE_TYPE = "frame_extraction_failed"
_UNKNOWN_FRAME_FAILURE_MESSAGE = "Frame extraction failed"


class _SilentYtDlpLogger:
    """Discard yt-dlp messages because they may contain signed stream URLs."""

    def debug(self, _message: str) -> None:
        """Discard debug output."""

    def info(self, _message: str) -> None:
        """Discard informational output."""

    def warning(self, _message: str) -> None:
        """Discard warning output."""

    def error(self, _message: str) -> None:
        """Discard error output."""


@dataclass(frozen=True)
class FrameRange:
    """Inclusive timestamp range in seconds."""

    start: float
    end: float


@dataclass(frozen=True)
class FrameTarget:
    """Resolved timestamp and its strongest selector provenance."""

    timestamp_seconds: float
    selector: FrameSelector


@dataclass(frozen=True)
class VideoFrameArtifact:
    """Successfully extracted JPEG frame artifact."""

    timestamp_seconds: float
    timestamp: str
    path: Path
    mime_type: str
    selector: FrameSelector


@dataclass(frozen=True)
class FrameFailure:
    """Sanitized failure for one requested frame."""

    timestamp_seconds: float
    timestamp: str
    selector: FrameSelector
    error_type: str
    message: str


@dataclass
class FrameExtractionResult:
    """Successful and failed frame extraction outcomes."""

    frames: list[VideoFrameArtifact] = field(default_factory=list)
    failures: list[FrameFailure] = field(default_factory=list)
    duration_seconds: float | None = None


@dataclass(frozen=True)
class YouTubeStreamInfo:
    """Resolved direct video stream and authoritative duration."""

    url: str
    duration_seconds: float


@dataclass(frozen=True)
class YouTubeFrameRequest:
    """Typed deterministic frame request passed by the CLI."""

    overview_count: int = 0
    exact_timestamps: tuple[float, ...] = ()
    ranges: tuple[FrameRange, ...] = ()
    range_count: int = 6
    frames_dir: Path | None = None

    def __post_init__(self) -> None:
        """Validate typed callers before selector expansion or deduplication."""
        if isinstance(self.overview_count, bool) or not isinstance(self.overview_count, int):
            raise _validation_error("Overview frame count must be an integer")
        if not 0 <= self.overview_count <= MAX_FRAMES_PER_SELECTOR:
            raise _validation_error(
                f"Overview frame count must be between 0 and {MAX_FRAMES_PER_SELECTOR}"
            )
        if isinstance(self.range_count, bool) or not isinstance(self.range_count, int):
            raise _validation_error("Range frame count must be an integer")
        if self.ranges and not MIN_RANGE_FRAMES <= self.range_count <= MAX_FRAMES_PER_SELECTOR:
            raise _validation_error(
                f"Range frame count must be between {MIN_RANGE_FRAMES} and "
                f"{MAX_FRAMES_PER_SELECTOR}"
            )
        raw_selector_count = len(self.exact_timestamps) + len(self.ranges)
        if raw_selector_count > MAX_RAW_FRAME_SELECTORS:
            raise _validation_error(
                f"Frame request has too many raw selectors; the maximum is "
                f"{MAX_RAW_FRAME_SELECTORS}"
            )
        for timestamp in self.exact_timestamps:
            value = _safe_request_number(
                timestamp, "Frame timestamps must be finite and non-negative"
            )
            if value < 0:
                raise _validation_error("Frame timestamps must be finite and non-negative")
        for frame_range in self.ranges:
            start = _safe_request_number(
                frame_range.start, "Frame range values must be finite and non-negative"
            )
            end = _safe_request_number(
                frame_range.end, "Frame range values must be finite and non-negative"
            )
            if start < 0 or end <= start:
                raise _validation_error("Frame range end must be after its non-negative start")

    @property
    def requested(self) -> bool:
        """Return whether at least one selector was supplied."""
        return bool(self.overview_count or self.exact_timestamps or self.ranges)


class YouTubeFrameError(RuntimeError):
    """Sanitized, classified YouTube frame extraction error."""

    def __init__(self, message: str, diagnostics: dict[str, object]) -> None:
        """Initialize an error using only caller-safe values."""
        self.message = message
        self.diagnostics = diagnostics
        super().__init__(message)


class YouTubeFrameRequestError(ValueError):
    """User-correctable frame selector validation error."""


@dataclass(frozen=True)
class FrameCommitHooks:
    """Output rollback and cleanup hooks spanning a frame bundle commit."""

    rollback: Callable[[], None]
    finalize: Callable[[], None]


BeforeFrameCommit = Callable[[FrameExtractionResult], FrameCommitHooks | None]


def _safe_request_number(value: object, message: str) -> float:
    """Coerce a typed request number into a finite float with stable errors."""
    try:
        number = float(cast(Any, value))
    except (TypeError, ValueError, OverflowError) as error:
        raise _validation_error(message) from error
    if not math.isfinite(number):
        raise _validation_error(message)
    return number


def _safe_untrusted_number(value: object, *, upper_bound: float) -> float | None:
    """Return a bounded finite numeric metadata value or ``None``."""
    if isinstance(value, bool):
        return None
    try:
        number = float(cast(Any, value))
    except Exception:
        return None
    if not math.isfinite(number) or number < 0 or number > upper_bound:
        return None
    return number


def _decimal_seconds(value: float | Decimal) -> Decimal:
    """Return seconds rounded deterministically to milliseconds."""
    try:
        return Decimal(str(value)).quantize(_MILLISECOND, rounding=ROUND_HALF_UP)
    except DecimalException as error:
        raise _validation_error("Frame timestamp is outside the supported numeric range") from error


def _validation_error(message: str) -> YouTubeFrameRequestError:
    """Return a frame selector validation error."""
    return YouTubeFrameRequestError(message)


def parse_frame_timestamp(raw: str) -> float:
    """Parse seconds, MM:SS, or HH:MM:SS into seconds.

    Args:
        raw: Timestamp text with optional millisecond precision.

    Returns:
        Timestamp as seconds.

    Raises:
        ValueError: If the timestamp is malformed or negative.
    """
    value = raw.strip()
    parts = value.split(":")
    if not value or len(parts) > TIMESTAMP_COMPONENTS or not _TIMESTAMP_PATTERN.fullmatch(value):
        raise _validation_error(f"Invalid frame timestamp: {raw!r}")

    try:
        numbers = [Decimal(part) for part in parts]
    except InvalidOperation as error:
        raise _validation_error(f"Invalid frame timestamp: {raw!r}") from error

    if any(number < 0 or not number.is_finite() for number in numbers):
        raise _validation_error("Frame timestamps must be finite and non-negative")
    if len(parts) > 1 and (
        numbers[-1] >= SECONDS_PER_MINUTE or numbers[-1] != numbers[-1].quantize(_MILLISECOND)
    ):
        raise _validation_error(
            "Timestamp seconds must be below 60 with at most millisecond precision"
        )
    if len(parts) == TIMESTAMP_COMPONENTS and numbers[-2] >= SECONDS_PER_MINUTE:
        raise _validation_error("Timestamp minutes must be below 60 in HH:MM:SS values")
    if any("." in part for part in parts[:-1]):
        raise _validation_error("Only timestamp seconds may contain a decimal fraction")

    try:
        if len(numbers) == 1:
            seconds = numbers[0]
        elif len(numbers) == MIN_RANGE_FRAMES:
            seconds = numbers[0] * SECONDS_PER_MINUTE + numbers[1]
        else:
            seconds = numbers[0] * 3600 + numbers[1] * SECONDS_PER_MINUTE + numbers[2]
        parsed = float(seconds.quantize(_MILLISECOND, rounding=ROUND_HALF_UP))
    except DecimalException as error:
        raise _validation_error("Invalid frame timestamp: numeric value is too large") from error
    if not math.isfinite(parsed):
        raise _validation_error("Invalid frame timestamp: numeric value is too large")
    return parsed


def parse_frame_range(raw: str) -> FrameRange:
    """Parse an inclusive ``START-END`` frame range.

    Args:
        raw: Range containing two supported timestamps.

    Returns:
        Parsed frame range.

    Raises:
        ValueError: If the range is malformed, empty, or reversed.
    """
    if raw.count("-") != 1:
        raise _validation_error("Frame ranges must use START-END")
    start_raw, end_raw = raw.split("-", 1)
    start = parse_frame_timestamp(start_raw)
    end = parse_frame_timestamp(end_raw)
    if end <= start:
        raise _validation_error("Frame range end must be after its start")
    return FrameRange(start=start, end=end)


def format_frame_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm or MM:SS.mmm.

    Args:
        seconds: Finite, non-negative seconds.

    Returns:
        Timestamp string preserving millisecond precision.
    """
    value = _decimal_seconds(seconds)
    if value < 0 or not value.is_finite():
        raise _validation_error("Frame timestamps must be finite and non-negative")
    total_milliseconds = int(value * 1000)
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"
    return f"{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def sample_overview_timestamps(duration_seconds: float, count: int) -> list[float]:
    """Sample bucket midpoints across a video duration."""
    duration_seconds = _safe_request_number(
        duration_seconds, "Video duration must be greater than zero"
    )
    if duration_seconds <= 0:
        raise _validation_error("Video duration must be greater than zero")
    if not 0 <= count <= MAX_FRAMES_PER_SELECTOR:
        raise _validation_error(
            f"Overview frame count must be between 0 and {MAX_FRAMES_PER_SELECTOR}"
        )
    return [
        float(_decimal_seconds((index + 0.5) * duration_seconds / count)) for index in range(count)
    ]


def sample_range_timestamps(frame_range: FrameRange, count: int) -> list[float]:
    """Sample an inclusive range using an even interval."""
    if not MIN_RANGE_FRAMES <= count <= MAX_FRAMES_PER_SELECTOR:
        raise _validation_error(
            f"Range frame count must be between {MIN_RANGE_FRAMES} and {MAX_FRAMES_PER_SELECTOR}"
        )
    start = _safe_request_number(
        frame_range.start, "Frame range values must be finite and non-negative"
    )
    end = _safe_request_number(
        frame_range.end, "Frame range values must be finite and non-negative"
    )
    if start < 0 or end <= start:
        raise _validation_error("Frame range end must be after its non-negative start")
    step = (end - start) / (count - 1)
    return [float(_decimal_seconds(start + index * step)) for index in range(count)]


def resolve_frame_targets(
    *,
    duration_seconds: float,
    overview_count: int,
    exact_timestamps: tuple[float, ...],
    ranges: tuple[FrameRange, ...],
    range_count: int,
) -> list[FrameTarget]:
    """Resolve selectors into chronological, millisecond-deduplicated targets."""
    duration_seconds = _safe_request_number(
        duration_seconds, "Video duration must be greater than zero"
    )
    if duration_seconds <= 0:
        raise _validation_error("Video duration must be greater than zero")
    if len(exact_timestamps) + len(ranges) > MAX_RAW_FRAME_SELECTORS:
        raise _validation_error(
            f"Frame request has too many raw selectors; the maximum is {MAX_RAW_FRAME_SELECTORS}"
        )
    if ranges and not MIN_RANGE_FRAMES <= range_count <= MAX_FRAMES_PER_SELECTOR:
        raise _validation_error(
            f"Range frame count must be between {MIN_RANGE_FRAMES} and {MAX_FRAMES_PER_SELECTOR}"
        )

    candidates: list[FrameTarget] = [
        FrameTarget(timestamp, "overview")
        for timestamp in sample_overview_timestamps(duration_seconds, overview_count)
    ]
    candidates.extend(
        FrameTarget(
            float(
                _decimal_seconds(
                    _safe_request_number(
                        timestamp, "Frame timestamps must be finite and non-negative"
                    )
                )
            ),
            "exact",
        )
        for timestamp in exact_timestamps
    )
    for frame_range in ranges:
        candidates.extend(
            FrameTarget(timestamp, "range")
            for timestamp in sample_range_timestamps(frame_range, range_count)
        )

    deduplicated: dict[int, FrameTarget] = {}
    for target in candidates:
        timestamp = float(_decimal_seconds(target.timestamp_seconds))
        if timestamp < 0:
            raise _validation_error("Frame timestamps must be non-negative")
        if timestamp >= duration_seconds:
            raise _validation_error("Frame timestamps must be before the video duration")
        key = int(_decimal_seconds(timestamp) * 1000)
        existing = deduplicated.get(key)
        if (
            existing is None
            or _PROVENANCE_PRIORITY[target.selector] > _PROVENANCE_PRIORITY[existing.selector]
        ):
            deduplicated[key] = FrameTarget(timestamp, target.selector)

    targets = sorted(deduplicated.values(), key=lambda target: target.timestamp_seconds)
    if len(targets) > MAX_FRAMES_PER_INVOCATION:
        raise _validation_error(
            f"Frame request resolves to {len(targets)} frames; reduce selectors to the maximum of "
            f"{MAX_FRAMES_PER_INVOCATION}"
        )
    return targets


def _frame_error(message: str, error_type: str, **diagnostics: object) -> YouTubeFrameError:
    """Build an error without retaining raw source or transport diagnostics."""
    return YouTubeFrameError(message, {"error_type": error_type, **diagnostics})


def _raise_sanitized_frame_error(error: YouTubeFrameError) -> NoReturn:
    """Raise a frame error without retaining a raw exception chain."""
    try:
        raise error from None
    except YouTubeFrameError:
        error.__cause__ = None
        error.__context__ = None
        raise


def resolve_youtube_stream(video_url: str) -> YouTubeStreamInfo:
    """Resolve an FFmpeg-compatible YouTube video stream and duration.

    Raw extractor exceptions and direct stream URLs are intentionally excluded
    from diagnostics because they may contain cookies or signed query values.
    """
    options = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "noplaylist": True,
        "skip_download": True,
        "logger": _SilentYtDlpLogger(),
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(video_url, download=False)
    except Exception as error:
        lowered = str(error).lower()
        error_type = "unavailable"
        message = "Unable to resolve the YouTube video for frame extraction"
        if any(marker in lowered for marker in ("private video", "video is private")):
            error_type, message = (
                "private",
                "YouTube frame extraction is unavailable for private videos",
            )
        elif any(
            marker in lowered for marker in ("age-restricted", "age restricted", "confirm your age")
        ):
            error_type, message = (
                "age_restricted",
                "YouTube frame extraction cannot access this age-restricted video",
            )
        elif any(marker in lowered for marker in ("live stream", "livestream")):
            error_type, message = (
                "live_stream",
                "YouTube live streams are not supported for frame extraction",
            )
        _raise_sanitized_frame_error(_frame_error(message, error_type, stage="stream_resolution"))

    if not isinstance(info, dict):
        raise _frame_error(
            "YouTube returned no video metadata for frame extraction", "missing_metadata"
        )
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
        raise _frame_error(
            "YouTube live streams are not supported for frame extraction", "live_stream"
        )

    duration = _safe_untrusted_number(info.get("duration"), upper_bound=float(2**53))
    if duration is None or duration <= 0:
        raise _frame_error(
            "YouTube video duration is unavailable for frame extraction", "missing_duration"
        )

    formats_value = info.get("formats")
    formats: list[object] = formats_value if isinstance(formats_value, list) else []
    video_formats = [
        item
        for item in formats
        if isinstance(item, dict)
        and isinstance(item.get("url"), str)
        and item.get("vcodec") not in {None, "none"}
    ]
    ranked_formats: list[tuple[dict[object, object], float | None, float | None]] = []
    for item in video_formats:
        height = _safe_untrusted_number(item.get("height"), upper_bound=MAX_UNTRUSTED_HEIGHT)
        tbr = _safe_untrusted_number(item.get("tbr"), upper_bound=MAX_UNTRUSTED_TBR)
        if (item.get("height") is not None and height is None) or (
            item.get("tbr") is not None and tbr is None
        ):
            continue
        ranked_formats.append((item, height, tbr))
    bounded = [
        ranked_item
        for ranked_item in ranked_formats
        if ranked_item[1] is not None and ranked_item[1] <= MAX_STREAM_HEIGHT
    ]
    ranked = bounded or ranked_formats
    selected = max(
        ranked,
        key=lambda ranked_item: (ranked_item[1] or 0.0, ranked_item[2] or 0.0),
        default=None,
    )
    stream_url = selected[0].get("url") if selected else info.get("url")
    if not isinstance(stream_url, str) or not stream_url:
        raise _frame_error("YouTube returned no compatible video stream", "missing_stream")
    return YouTubeStreamInfo(url=stream_url, duration_seconds=duration)


def ensure_ffmpeg_available() -> None:
    """Fail with a classified error when system FFmpeg is unavailable."""
    if shutil.which("ffmpeg") is None:
        raise _frame_error(
            "FFmpeg is required for YouTube frame extraction; install ffmpeg and retry",
            "ffmpeg_missing",
        )


async def _resolve_stream_in_daemon(
    resolver: Callable[[str], YouTubeStreamInfo], video_url: str
) -> YouTubeStreamInfo:
    """Resolve a stream without making event-loop shutdown wait on stalled yt-dlp work."""
    loop = asyncio.get_running_loop()
    future: asyncio.Future[YouTubeStreamInfo] = loop.create_future()

    def publish(result: YouTubeStreamInfo | None, error: Exception | None) -> None:
        if future.done():
            return
        if error is not None:
            future.set_exception(error)
        else:
            assert result is not None
            future.set_result(result)

    def worker() -> None:
        try:
            result = resolver(video_url)
        except Exception as error:
            try:
                loop.call_soon_threadsafe(publish, None, error)
            except RuntimeError:
                return
        else:
            try:
                loop.call_soon_threadsafe(publish, result, None)
            except RuntimeError:
                return

    threading.Thread(target=worker, name="gobbler-youtube-stream", daemon=True).start()
    return await future


async def _refresh_stream_after_partial_expiry(
    resolver: Callable[[str], YouTubeStreamInfo],
    video_url: str,
    outcomes: list[VideoFrameArtifact | FrameFailure],
) -> YouTubeStreamInfo | None:
    """Refresh a stream, preserving existing successes when refresh itself fails."""
    try:
        return await _resolve_stream_in_daemon(resolver, video_url)
    except Exception:
        if any(isinstance(outcome, VideoFrameArtifact) for outcome in outcomes):
            return None
        raise


def _frame_filename(sequence: int, timestamp_seconds: float) -> str:
    """Return a deterministic sequence and millisecond timestamp filename."""
    timestamp = format_frame_timestamp(timestamp_seconds)
    if timestamp.count(":") == 1:
        timestamp = f"00:{timestamp}"
    filename_timestamp = timestamp.replace(":", "-").replace(".", "-")
    return f"frame-{sequence:03d}-{filename_timestamp}.jpg"


async def _terminate_and_reap(process: asyncio.subprocess.Process) -> None:
    """Terminate an active FFmpeg child and wait until the OS has reaped it."""
    if process.returncode is None:
        try:
            process.terminate()
        except (OSError, ProcessLookupError):
            if process.returncode is None:
                with suppress(OSError, ProcessLookupError):
                    process.kill()
    try:
        await asyncio.wait_for(process.wait(), timeout=FFMPEG_TERMINATE_GRACE_SECONDS)
    except (OSError, TimeoutError):
        if process.returncode is None:
            with suppress(OSError, ProcessLookupError):
                process.kill()
        with suppress(OSError):
            await process.wait()


async def _extract_frame(
    stream_url: str,
    target: FrameTarget,
    final_path: Path,
) -> VideoFrameArtifact | FrameFailure:
    """Extract one frame with a cancellable, fully reaped FFmpeg child."""
    timestamp = format_frame_timestamp(target.timestamp_seconds)
    temp_path = final_path.with_name(f"{final_path.stem}.part.jpg")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{target.timestamp_seconds:.3f}",
        "-i",
        stream_url,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        "-y",
        str(temp_path),
    ]
    process: asyncio.subprocess.Process | None = None
    outcome: VideoFrameArtifact | FrameFailure | None = None
    cleanup_failed = False
    try:
        temp_path.unlink(missing_ok=True)
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=FFMPEG_TIMEOUT_SECONDS
            )
        except TimeoutError:
            await _terminate_and_reap(process)
            outcome = FrameFailure(
                target.timestamp_seconds,
                timestamp,
                target.selector,
                "ffmpeg_timeout",
                "FFmpeg timed out while extracting this frame",
            )
        except asyncio.CancelledError:
            await _terminate_and_reap(process)
            raise

        if outcome is None and process.returncode != 0:
            stderr = (stderr_bytes or b"").decode("utf-8", errors="replace").lower()
            expired = any(marker in stderr for marker in ("403", "forbidden", "expired"))
            outcome = FrameFailure(
                target.timestamp_seconds,
                timestamp,
                target.selector,
                "stream_expired" if expired else "ffmpeg_failed",
                "YouTube video stream expired" if expired else "FFmpeg could not decode this frame",
            )
        elif outcome is None and (not temp_path.is_file() or temp_path.stat().st_size <= 0):
            outcome = FrameFailure(
                target.timestamp_seconds,
                timestamp,
                target.selector,
                "empty_output",
                "FFmpeg produced no frame image",
            )
        elif outcome is None:
            temp_path.replace(final_path)
            outcome = VideoFrameArtifact(
                timestamp_seconds=target.timestamp_seconds,
                timestamp=timestamp,
                path=final_path,
                mime_type="image/jpeg",
                selector=target.selector,
            )
    except FileNotFoundError:
        outcome = FrameFailure(
            target.timestamp_seconds,
            timestamp,
            target.selector,
            "ffmpeg_missing",
            "FFmpeg is required for YouTube frame extraction",
        )
    except OSError:
        if process is not None and process.returncode is None:
            await _terminate_and_reap(process)
        outcome = FrameFailure(
            target.timestamp_seconds,
            timestamp,
            target.selector,
            "filesystem_error",
            "Unable to finalize the frame image",
        )
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            cleanup_failed = True

    if cleanup_failed:
        return FrameFailure(
            target.timestamp_seconds,
            timestamp,
            target.selector,
            "filesystem_error",
            "Unable to finalize the frame image",
        )
    assert outcome is not None
    return outcome


def _canonical_frames_dir(frames_dir: Path) -> Path:
    """Resolve the actual target directory, including symlinked parent semantics."""
    try:
        return frames_dir.resolve(strict=frames_dir.exists() or frames_dir.is_symlink())
    except OSError:
        _raise_sanitized_frame_error(
            _frame_error(
                "Unable to resolve the YouTube frame artifact directory",
                "filesystem_error",
                stage="frame_staging",
            )
        )


def _create_frame_staging_dir(canonical_frames_dir: Path) -> Path:
    """Create an isolated sibling directory on the target filesystem."""
    try:
        canonical_frames_dir.parent.mkdir(parents=True, exist_ok=True)
        return Path(
            tempfile.mkdtemp(prefix=".gobbler-frame-stage-", dir=canonical_frames_dir.parent)
        )
    except OSError:
        _raise_sanitized_frame_error(
            _frame_error(
                "Unable to stage YouTube frame artifacts",
                "filesystem_error",
                stage="frame_staging",
            )
        )


@dataclass
class _FrameDirectoryLock:
    """Advisory filesystem lock serializing one canonical frame directory."""

    handle: BinaryIO

    def release(self) -> None:
        """Release the platform lock and close its file descriptor."""
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(  # type: ignore[attr-defined]
                    self.handle.fileno(),
                    msvcrt.LK_UNLCK,  # type: ignore[attr-defined]
                    1,
                )
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()


async def _acquire_frame_directory_lock(canonical_frames_dir: Path) -> _FrameDirectoryLock:
    """Acquire a cancellation-safe cross-process lock for one frame directory."""
    lock_path = canonical_frames_dir.parent / f".{canonical_frames_dir.name}.gobbler-frame.lock"
    try:
        canonical_frames_dir.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+b")
    except OSError:
        _raise_sanitized_frame_error(
            _frame_error(
                "Unable to lock the YouTube frame artifact directory",
                "filesystem_error",
                stage="frame_lock",
            )
        )

    try:
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    if handle.read(1) == b"":
                        handle.seek(0)
                        handle.write(b"0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(  # type: ignore[attr-defined]
                        handle.fileno(),
                        msvcrt.LK_NBLCK,  # type: ignore[attr-defined]
                        1,
                    )
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return _FrameDirectoryLock(handle)
            except (BlockingIOError, PermissionError):
                await asyncio.sleep(0.01)
            except OSError:
                _raise_sanitized_frame_error(
                    _frame_error(
                        "Unable to lock the YouTube frame artifact directory",
                        "filesystem_error",
                        stage="frame_lock",
                    )
                )
    except BaseException:
        handle.close()
        raise


def _cleanup_frame_staging(staging_dir: Path) -> None:
    """Remove transaction staging or raise a stable, sanitized cleanup error."""
    try:
        shutil.rmtree(staging_dir)
    except OSError:
        _raise_sanitized_frame_error(
            _frame_error(
                "Unable to clean up staged YouTube frame artifacts",
                "filesystem_error",
                stage="frame_cleanup",
                artifacts_preserved=True,
            )
        )


def _rollback_frame_bundle(moved_new: list[Path], moved_previous: list[tuple[Path, Path]]) -> bool:
    """Best-effort restore a partially committed bundle, retaining failed backups."""
    rollback_failed = False
    for new_path in reversed(moved_new):
        try:
            new_path.unlink(missing_ok=True)
        except OSError:
            rollback_failed = True
    for backup_path, original_path in reversed(moved_previous):
        if backup_path.exists() or backup_path.is_symlink():
            try:
                if original_path.exists() or original_path.is_symlink():
                    original_path.unlink()
                backup_path.replace(original_path)
            except OSError:
                rollback_failed = True
    return rollback_failed


def _commit_frame_bundle(
    frames: list[VideoFrameArtifact], frames_dir: Path, staging_dir: Path
) -> list[VideoFrameArtifact]:
    """Replace owned frame files transactionally after staged extraction succeeds."""
    backup_dir = staging_dir / "previous"
    moved_previous: list[tuple[Path, Path]] = []
    moved_new: list[Path] = []
    committed: list[VideoFrameArtifact] = []
    try:
        frames_dir.mkdir(parents=True, exist_ok=True)
        backup_dir.mkdir()
        for artifact_path in frames_dir.iterdir():
            if _OWNED_FRAME_PATTERN.fullmatch(artifact_path.name) and (
                artifact_path.is_file() or artifact_path.is_symlink()
            ):
                backup_path = backup_dir / artifact_path.name
                artifact_path.replace(backup_path)
                moved_previous.append((backup_path, artifact_path))

        for frame in frames:
            final_path = frames_dir / frame.path.name
            frame.path.replace(final_path)
            moved_new.append(final_path)
            committed.append(replace(frame, path=final_path))
    except OSError:
        if _rollback_frame_bundle(moved_new, moved_previous):
            _raise_sanitized_frame_error(
                _frame_error(
                    "Unable to restore previous YouTube frame artifacts; backups were preserved",
                    "filesystem_error",
                    stage="frame_rollback",
                    backups_preserved=True,
                )
            )
        _raise_sanitized_frame_error(
            _frame_error(
                "Unable to replace existing YouTube frame artifacts",
                "filesystem_error",
                stage="frame_commit",
            )
        )
    else:
        return committed


async def _extract_youtube_frames_staged(
    video_url: str,
    targets: list[FrameTarget],
    frames_dir: Path,
    *,
    stream_info: YouTubeStreamInfo | None = None,
    stream_resolver: Callable[[str], YouTubeStreamInfo] = resolve_youtube_stream,
) -> FrameExtractionResult:
    """Extract a complete candidate bundle into an isolated staging directory."""
    ensure_ffmpeg_available()
    stream = stream_info or await _resolve_stream_in_daemon(stream_resolver, video_url)
    assert stream is not None
    frames_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(FFMPEG_CONCURRENCY)
    frame_paths = [
        frames_dir / _frame_filename(sequence, target.timestamp_seconds)
        for sequence, target in enumerate(targets, 1)
    ]
    temp_paths = [path.with_name(f"{path.stem}.part.jpg") for path in frame_paths]
    for temp_path in temp_paths:
        with suppress(OSError):
            temp_path.unlink(missing_ok=True)

    async def extract(
        target: FrameTarget, sequence: int, url: str
    ) -> VideoFrameArtifact | FrameFailure:
        async with semaphore:
            return await _extract_frame(url, target, frame_paths[sequence - 1])

    async def run_batch(indexes: list[int], url: str) -> list[VideoFrameArtifact | FrameFailure]:
        tasks = [asyncio.create_task(extract(targets[index], index + 1, url)) for index in indexes]
        try:
            return await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    try:
        outcomes = await run_batch(list(range(len(targets))), stream.url)

        expired_indexes = [
            index
            for index, outcome in enumerate(outcomes)
            if isinstance(outcome, FrameFailure) and outcome.error_type == "stream_expired"
        ]
        if expired_indexes:
            refreshed = await _refresh_stream_after_partial_expiry(
                stream_resolver, video_url, outcomes
            )
            if refreshed is not None:
                retried = await run_batch(expired_indexes, refreshed.url)
                for index, outcome in zip(expired_indexes, retried, strict=True):
                    outcomes[index] = outcome
                stream = refreshed
    finally:
        for temp_path in temp_paths:
            with suppress(OSError):
                temp_path.unlink(missing_ok=True)

    frames = [outcome for outcome in outcomes if isinstance(outcome, VideoFrameArtifact)]
    failures = [outcome for outcome in outcomes if isinstance(outcome, FrameFailure)]
    if not frames:
        raise _frame_error(
            "No YouTube frames could be extracted",
            "all_frames_failed",
            failures=[
                {
                    "timestamp_seconds": failure.timestamp_seconds,
                    "timestamp": failure.timestamp,
                    "selector": failure.selector,
                    "error_type": failure.error_type,
                    "message": failure.message,
                }
                for failure in failures
            ],
        )
    return FrameExtractionResult(
        frames=frames,
        failures=failures,
        duration_seconds=stream.duration_seconds,
    )


async def extract_youtube_frames(
    video_url: str,
    targets: list[FrameTarget],
    frames_dir: Path,
    *,
    stream_info: YouTubeStreamInfo | None = None,
    stream_resolver: Callable[[str], YouTubeStreamInfo] = resolve_youtube_stream,
    before_commit: BeforeFrameCommit | None = None,
) -> FrameExtractionResult:
    """Extract, persist a manifest hook, then atomically replace the frame bundle."""
    canonical_frames_dir = _canonical_frames_dir(frames_dir)
    directory_lock = await _acquire_frame_directory_lock(canonical_frames_dir)
    staging_dir: Path | None = None
    preserve_staging = False
    hooks: FrameCommitHooks | None = None
    try:
        staging_dir = _create_frame_staging_dir(canonical_frames_dir)
        result = await _extract_youtube_frames_staged(
            video_url,
            targets,
            staging_dir,
            stream_info=stream_info,
            stream_resolver=stream_resolver,
        )
        projected_result = replace(
            result,
            frames=[
                replace(frame, path=canonical_frames_dir / frame.path.name)
                for frame in result.frames
            ],
        )
        if before_commit is not None:
            hooks = before_commit(projected_result)
        try:
            result.frames = _commit_frame_bundle(result.frames, canonical_frames_dir, staging_dir)
        except BaseException as commit_error:
            preserve_staging = bool(
                isinstance(commit_error, YouTubeFrameError)
                and commit_error.diagnostics.get("stage") == "frame_rollback"
            )
            if hooks is not None:
                try:
                    hooks.rollback()
                except OSError:
                    preserve_staging = True
                    _raise_sanitized_frame_error(
                        _frame_error(
                            "Unable to restore the previous YouTube output; backups were preserved",
                            "filesystem_error",
                            stage="output_rollback",
                            backups_preserved=True,
                        )
                    )
            raise

        cleanup_error: YouTubeFrameError | None = None
        try:
            _cleanup_frame_staging(staging_dir)
            staging_dir = None
        except YouTubeFrameError as error:
            # The frame swap already succeeded. Finalize the matching manifest
            # transaction so its backup/lock cannot be stranded, then report
            # the preserved staging directory as a classified cleanup failure.
            cleanup_error = error
            preserve_staging = True
        if hooks is not None:
            try:
                hooks.finalize()
            except OSError:
                _raise_sanitized_frame_error(
                    _frame_error(
                        "Unable to clean up the previous YouTube output backup",
                        "filesystem_error",
                        stage="output_cleanup",
                        backups_preserved=True,
                    )
                )
        if cleanup_error is not None:
            raise cleanup_error
        return result
    finally:
        try:
            if staging_dir is not None and not preserve_staging and staging_dir.exists():
                _cleanup_frame_staging(staging_dir)
        finally:
            try:
                directory_lock.release()
            except OSError:
                _raise_sanitized_frame_error(
                    _frame_error(
                        "Unable to release the YouTube frame artifact lock",
                        "filesystem_error",
                        stage="frame_lock_cleanup",
                    )
                )


def derive_frames_dir(output_path: Path | None, explicit_dir: Path | None) -> Path:
    """Return an explicit frame directory or derive one from output."""
    if explicit_dir is not None:
        return explicit_dir
    if output_path is None:
        raise _validation_error("Frame extraction requires --output or --frames-dir")
    return output_path.parent / f"{output_path.stem}.assets" / "frames"


def validate_frame_manifest_path(output_path: Path | None, frames_dir: Path) -> None:
    """Reject a manifest path that occupies Gobbler's owned frame namespace."""
    if output_path is None:
        return
    try:
        canonical_output = output_path.resolve(strict=False)
        canonical_frames_dir = frames_dir.resolve(strict=False)
        canonical_output_parent = output_path.parent.resolve(strict=False)
    except OSError:
        # Canonicalization failures are classified later by the transaction layer.
        return
    lexical_collision = (
        canonical_output_parent == canonical_frames_dir
        and _OWNED_FRAME_PATTERN.fullmatch(output_path.name)
    )
    target_collision = (
        canonical_output.parent == canonical_frames_dir
        and _OWNED_FRAME_PATTERN.fullmatch(canonical_output.name)
    )
    if lexical_collision or target_collision:
        raise _validation_error(
            "YouTube output path cannot use an owned frame filename inside --frames-dir"
        )


def _display_path(path: Path, output_path: Path) -> str:
    """Return a portable artifact link relative to output when appropriate."""
    output_parent = output_path.parent
    if path.is_absolute() and output_parent.is_absolute():
        try:
            return path.relative_to(output_parent).as_posix()
        except ValueError:
            return str(path)
    try:
        return Path(os.path.relpath(path, output_parent)).as_posix()
    except (OSError, ValueError):
        return str(path.absolute())


def _markdown_path(path: Path, output_path: Path) -> str:
    """Return an encoded Markdown path, using file URIs across Windows drives."""
    display_path = _display_path(path, output_path)
    windows_path = PureWindowsPath(display_path)
    if windows_path.is_absolute() and windows_path.drive:
        normalized = windows_path.as_posix()
        if normalized.startswith("//"):
            return "file:" + quote(normalized, safe="/:._~-")
        normalized = normalized.lstrip("/")
        return "file:///" + quote(normalized, safe="/:._~-")
    return quote(display_path.replace("\\", "/"), safe="/:._~-")


def render_frames_markdown(
    frames: list[VideoFrameArtifact],
    *,
    output_path: Path,
    top_level: bool = False,
) -> str:
    """Render timestamped image links for extracted frames."""
    heading = "# Video Frames" if top_level else "## Video Frames"
    sections = [heading]
    for frame in frames:
        markdown_path = _markdown_path(frame.path, output_path)
        sections.extend(
            [
                f"### {frame.timestamp}",
                f"![Video frame at {frame.timestamp}]({markdown_path})",
            ]
        )
    return "\n\n".join(sections)


def render_frame_warnings_markdown(failures: list[FrameFailure]) -> str:
    """Render sanitized partial-failure details for default Markdown consumers."""
    if not failures:
        return ""
    lines = ["## Frame Warnings"]
    for failure in failures:
        warning = _sanitized_frame_warning(failure)
        lines.append(
            f"- `{warning['timestamp']}` ({warning['selector']}) — "
            f"`{warning['error_type']}`: {warning['message']}"
        )
    return "\n\n" + "\n".join(lines)


def _sanitized_frame_warning(failure: FrameFailure) -> dict[str, object]:
    """Return stable warning fields without retaining transport or filesystem details."""
    error_type = (
        failure.error_type
        if failure.error_type in _FRAME_FAILURE_MESSAGES
        else _UNKNOWN_FRAME_FAILURE_TYPE
    )
    selector = failure.selector if failure.selector in _PROVENANCE_PRIORITY else "unknown"
    return {
        "timestamp_seconds": failure.timestamp_seconds,
        "timestamp": format_frame_timestamp(failure.timestamp_seconds),
        "selector": selector,
        "error_type": error_type,
        "message": _FRAME_FAILURE_MESSAGES.get(error_type, _UNKNOWN_FRAME_FAILURE_MESSAGE),
    }


def build_frame_metadata(
    result: FrameExtractionResult,
    *,
    output_path: Path,
    frames_dir: Path,
) -> dict[str, object]:
    """Build the machine-readable frame manifest and sanitized warnings."""
    frames = [
        {
            "timestamp_seconds": frame.timestamp_seconds,
            "timestamp": frame.timestamp,
            "path": _display_path(frame.path, output_path),
            "mime_type": frame.mime_type,
            "selector": frame.selector,
        }
        for frame in result.frames
    ]
    warnings = [_sanitized_frame_warning(failure) for failure in result.failures]
    metadata: dict[str, object] = {
        "frames": frames,
        "frame_summary": {
            "requested": len(result.frames) + len(result.failures),
            "extracted": len(result.frames),
            "failed": len(result.failures),
            "frames_dir": _display_path(frames_dir, output_path),
        },
    }
    if warnings:
        metadata["warnings"] = warnings
    return metadata

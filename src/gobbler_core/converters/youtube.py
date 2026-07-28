"""YouTube transcript conversion module with proxy and fallback support."""

import asyncio
import logging
import re
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, NoReturn

import yt_dlp

from gobbler_core.config import get_config
from gobbler_core.converters.youtube_frames import (
    FrameCommitHooks,
    FrameExtractionResult,
    YouTubeFrameRequest,
    YouTubeStreamInfo,
    build_frame_metadata,
    derive_frames_dir,
    ensure_ffmpeg_available,
    extract_youtube_frames,
    render_frame_warnings_markdown,
    render_frames_markdown,
    resolve_frame_targets,
    resolve_youtube_stream,
    validate_frame_manifest_path,
)
from gobbler_core.providers.youtube import (
    TranscriptProvider,
    YouTubeTranscriptError,
    create_provider_from_config,
    create_youtube_rate_limit_error,
    is_youtube_rate_limit_error,
)
from gobbler_core.utils.frontmatter import (
    count_words,
    create_youtube_frames_frontmatter,
    create_youtube_frontmatter,
)
from gobbler_core.utils.redaction import neutralize_github_mentions

YOUTUBE_CONVERSION_TIMEOUT_DEFAULT = 120

logger = logging.getLogger(__name__)

FrameManifestWriter = Callable[[str, dict[str, Any]], tuple[str, dict[str, Any], FrameCommitHooks]]


class _SilentYtDlpLogger:
    """Discard yt-dlp output without replacing process-wide stderr."""

    def debug(self, _message: str) -> None:
        """Discard debug output."""

    def info(self, _message: str) -> None:
        """Discard informational output."""

    def warning(self, _message: str) -> None:
        """Discard warning output."""

    def error(self, _message: str) -> None:
        """Discard error output."""


async def _run_in_daemon_thread(function: Callable[[], Any]) -> Any:
    """Run blocking provider work without making event-loop shutdown wait for it."""
    loop = asyncio.get_running_loop()
    future: asyncio.Future[Any] = loop.create_future()

    def publish_result(result: Any = None, error: Exception | None = None) -> None:
        if future.done():
            return
        if error is not None:
            future.set_exception(error)
        else:
            future.set_result(result)

    def worker() -> None:
        try:
            result = function()
        except Exception as error:
            try:
                loop.call_soon_threadsafe(publish_result, None, error)
            except RuntimeError:
                return
        else:
            try:
                loop.call_soon_threadsafe(publish_result, result, None)
            except RuntimeError:
                return

    threading.Thread(target=worker, name="gobbler-youtube-blocking", daemon=True).start()
    return await future


async def _wait_for_youtube_step(
    awaitable: Awaitable[Any],
    *,
    deadline: float,
    timeout: int,
) -> Any:
    """Wait for frame-related work within the shared conversion deadline."""
    remaining = max(0.0, deadline - asyncio.get_running_loop().time())
    try:
        return await asyncio.wait_for(awaitable, timeout=remaining)
    except TimeoutError as error:
        message = f"YouTube conversion timed out after {timeout}s"
        raise RuntimeError(message) from error


def extract_video_id(video_url: str) -> str:
    """Extract video ID from YouTube URL.

    Args:
        video_url: YouTube video URL

    Returns:
        11-character video ID

    Raises:
        ValueError: If URL format is invalid
    """
    pattern = (
        r"^https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/)"
        r"([a-zA-Z0-9_-]{11})(?=$|[&?#/])"
    )
    match = re.match(pattern, video_url)

    if not match:
        msg = (
            "Invalid YouTube URL format. Expected: https://youtube.com/watch?v=VIDEO_ID "
            "or https://youtu.be/VIDEO_ID"
        )
        raise ValueError(msg)

    return match.group(3)


def format_timestamp(seconds: float) -> str:
    """Format seconds into MM:SS or HH:MM:SS timestamp.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def get_video_metadata(video_url: str) -> dict[str, str | None]:
    """Extract video metadata using yt-dlp.

    Args:
        video_url: YouTube video URL

    Returns:
        Dictionary with title, channel, thumbnail URL, and description
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "socket_timeout": 30,
        "logger": _SilentYtDlpLogger(),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return {
                "title": info.get("title"),
                "channel": info.get("channel") or info.get("uploader"),
                "thumbnail": info.get("thumbnail"),
                "description": info.get("description"),
            }
    except Exception:
        # Extractor exceptions may contain signed URLs or cookie values.
        logger.debug("Failed to extract optional YouTube video metadata")
        return {"title": None, "channel": None, "thumbnail": None, "description": None}


def _simplify_transcript_error(error_msg: str, video_id: str) -> str:
    """Simplify noisy transcript error messages.

    Returns a clean error message suitable for users.
    """
    # Extract the key reason, strip the GitHub issue template noise
    if "Could not retrieve a transcript" in error_msg:
        # Find the actual reason (line after "caused by:")
        if "caused by:" in error_msg.lower():
            lines = error_msg.split("\n")
            for i, line in enumerate(lines):
                if "caused by:" in line.lower() and i + 1 < len(lines):
                    reason = lines[i + 1].strip()
                    if reason:
                        return f"Transcript unavailable for {video_id}: {reason}"
        return f"Transcript unavailable for video {video_id}"

    if "Video unavailable" in error_msg:
        return f"Video unavailable: {video_id}"

    if "disabled" in error_msg.lower():
        return f"Transcripts disabled for video {video_id}"

    # Return None to indicate we should re-raise the original error
    return ""


def _provider_diagnostic_name(provider: TranscriptProvider) -> str:
    """Return a stable provider name for diagnostics."""
    provider_type = type(provider).__name__
    provider_names = {
        "AutoFallbackProvider": "auto",
        "TranscriptAPIProvider": "transcriptapi",
        "YouTubeTranscriptAPIProvider": "youtube-transcript-api",
    }
    return provider_names.get(provider_type, provider_type)


def _provider_has_proxy(provider: TranscriptProvider) -> bool:
    """Return True when the active YouTube provider has proxy configuration."""
    proxy_config = getattr(provider, "proxy_config", None)
    if proxy_config is not None:
        return True

    free_provider = getattr(provider, "free_provider", None)
    return getattr(free_provider, "proxy_config", None) is not None


def _provider_has_fallback(provider: TranscriptProvider) -> bool:
    """Return True when the active YouTube provider has a configured fallback provider."""
    return getattr(provider, "paid_provider", None) is not None


def _raise_clean_transcript_error(
    error: Exception,
    *,
    video_id: str,
    language: str,
    provider: TranscriptProvider,
    active_logger: logging.Logger,
) -> NoReturn:
    """Raise a clean transcript error for users and agents."""
    if isinstance(error, YouTubeTranscriptError):
        raise error

    error_msg = str(error)
    if is_youtube_rate_limit_error(error_msg):
        raise create_youtube_rate_limit_error(
            video_id=video_id,
            language=language,
            provider=_provider_diagnostic_name(provider),
            proxy_configured=_provider_has_proxy(provider),
            fallback_configured=_provider_has_fallback(provider),
        ) from error

    clean_msg = _simplify_transcript_error(error_msg, video_id)
    if clean_msg:
        raise RuntimeError(clean_msg) from error

    active_logger.debug("YouTube transcript provider returned an unclassified error")
    raise error


async def convert_youtube_to_markdown(  # noqa: C901, PLR0912, PLR0915
    video_url: str,
    include_timestamps: bool = False,
    language: str = "auto",
    metrics_callback: Callable[[str, int], None] | None = None,
    provider: TranscriptProvider | None = None,
    logger_instance: logging.Logger | None = None,
    timeout: int = YOUTUBE_CONVERSION_TIMEOUT_DEFAULT,
    frame_request: YouTubeFrameRequest | None = None,
    output_path: Path | None = None,
    frames_only: bool = False,
    frame_manifest_writer: FrameManifestWriter | None = None,
) -> tuple[str, dict[str, Any]]:
    """Convert YouTube video to markdown transcript.

    Uses proxy and fallback providers based on environment configuration:
    - WEBSHARE_USER/WEBSHARE_PASS: Rotating proxy for free API
    - YOUTUBE_PROXY: Generic proxy URL
    - TRANSCRIPTAPI_KEY: Paid API fallback

    Args:
        video_url: YouTube video URL
        include_timestamps: Include timestamp markers
        language: Language code or 'auto'
        metrics_callback: Optional callback for metrics tracking (converter_type, size_bytes)
        provider: Optional pre-built TranscriptProvider instance
        logger_instance: Optional custom logger instance
        timeout: Overall conversion timeout in seconds
        frame_request: Optional deterministic frame selectors and artifact directory.
        output_path: Output artifact path used to construct relative frame links.
        frames_only: Skip all transcript-provider construction and work.
        frame_manifest_writer: Persist a rendered manifest before the frame bundle is committed.

    Returns:
        Tuple of (markdown_content, metadata)

    Raises:
        ValueError: Invalid URL
        RuntimeError: Transcript fetch failed
    """
    if frames_only and (frame_request is None or not frame_request.requested):
        message = "--frames-only requires at least one frame selector"
        raise ValueError(message)

    frames_requested = bool(frame_request and frame_request.requested)
    deadline = asyncio.get_running_loop().time() + timeout if frames_requested else None
    if frames_requested:
        # This must happen before provider construction or transcript work.
        ensure_ffmpeg_available()

    # Use custom logger or fall back to module logger
    active_logger = logger_instance or logger

    # Extract video ID
    video_id = extract_video_id(video_url)

    canonical_video_url = f"https://youtube.com/watch?v={video_id}"
    logged_video_url = canonical_video_url if frames_requested else video_url
    active_logger.info(
        "Starting YouTube conversion",
        extra={
            "extra_fields": {
                "video_url": logged_video_url,
                "video_id": video_id,
                "language": language,
                "include_timestamps": include_timestamps,
            }
        },
    )

    if frames_only:
        assert frame_request is not None

        def _sync_frame_metadata() -> tuple[dict[str, str | None], YouTubeStreamInfo]:
            return get_video_metadata(video_url), resolve_youtube_stream(video_url)

        assert deadline is not None
        video_metadata, stream_info = await _wait_for_youtube_step(
            _run_in_daemon_thread(_sync_frame_metadata),
            deadline=deadline,
            timeout=timeout,
        )

        targets = resolve_frame_targets(
            duration_seconds=stream_info.duration_seconds,
            overview_count=frame_request.overview_count,
            exact_timestamps=frame_request.exact_timestamps,
            ranges=frame_request.ranges,
            range_count=frame_request.range_count,
        )
        manifest_output = output_path or Path.cwd() / "youtube-frames.md"
        frames_dir = derive_frames_dir(output_path, frame_request.frames_dir)
        validate_frame_manifest_path(output_path, frames_dir)
        prepared_manifest: tuple[str, dict[str, Any]] | None = None

        def prepare_frame_manifest(
            prepared_frame_result: FrameExtractionResult,
        ) -> FrameCommitHooks | None:
            nonlocal prepared_manifest
            frontmatter = create_youtube_frames_frontmatter(
                video_url=canonical_video_url,
                video_id=video_id,
                duration=stream_info.duration_seconds,
                title=video_metadata.get("title"),
                channel=video_metadata.get("channel"),
                thumbnail=None,
            )
            prepared_markdown = neutralize_github_mentions(
                frontmatter
                + render_frames_markdown(
                    prepared_frame_result.frames,
                    output_path=manifest_output,
                    top_level=True,
                )
                + render_frame_warnings_markdown(prepared_frame_result.failures)
            )
            prepared_metadata: dict[str, Any] = {
                "video_id": video_id,
                "title": video_metadata.get("title"),
                "channel": video_metadata.get("channel"),
                "duration": stream_info.duration_seconds,
            }
            prepared_metadata.update(
                build_frame_metadata(
                    prepared_frame_result,
                    output_path=manifest_output,
                    frames_dir=frames_dir,
                )
            )
            if frame_manifest_writer is not None:
                prepared_markdown, prepared_metadata, hooks = frame_manifest_writer(
                    prepared_markdown, prepared_metadata
                )
                prepared_manifest = prepared_markdown, prepared_metadata
                return hooks
            prepared_manifest = prepared_markdown, prepared_metadata
            return None

        frame_result = await _wait_for_youtube_step(
            extract_youtube_frames(
                video_url,
                targets,
                frames_dir,
                stream_info=stream_info,
                before_commit=prepare_frame_manifest,
            ),
            deadline=deadline,
            timeout=timeout,
        )
        if prepared_manifest is None:
            prepare_frame_manifest(frame_result)
        assert prepared_manifest is not None
        markdown, metadata = prepared_manifest
        if metrics_callback is not None:
            metrics_callback("youtube", len(markdown))
        active_logger.info(
            "YouTube frame-only conversion completed",
            extra={
                "extra_fields": {
                    "video_id": video_id,
                    "duration": stream_info.duration_seconds,
                    "frames_extracted": len(frame_result.frames),
                    "frames_failed": len(frame_result.failures),
                }
            },
        )
        return markdown, metadata

    # Use provided provider or create one from the loaded Gobbler configuration.
    if provider is None:
        provider = create_provider_from_config(get_config())

    def _sync_fetch() -> tuple[dict[str, str | None], Any]:
        video_metadata = get_video_metadata(video_url)
        return video_metadata, provider.fetch(video_id, language)

    # Fetch metadata + transcript in a worker thread with an overall timeout
    try:
        if deadline is None:
            loop = asyncio.get_running_loop()
            fetch_work = loop.run_in_executor(None, _sync_fetch)
            video_metadata, result = await asyncio.wait_for(fetch_work, timeout=timeout)
        else:
            video_metadata, result = await _wait_for_youtube_step(
                _run_in_daemon_thread(_sync_fetch),
                deadline=deadline,
                timeout=timeout,
            )
    except TimeoutError as e:
        msg = f"YouTube conversion timed out after {timeout}s"
        raise RuntimeError(msg) from e
    except Exception as e:
        _raise_clean_transcript_error(
            e,
            video_id=video_id,
            language=language,
            provider=provider,
            active_logger=active_logger,
        )

    # Merge metadata (prefer yt-dlp, fall back to provider)
    for key in ["title", "channel", "thumbnail"]:
        if not video_metadata.get(key) and result.metadata.get(key):
            video_metadata[key] = result.metadata[key]

    # Calculate duration
    total_duration = (
        result.segments[-1].start + result.segments[-1].duration if result.segments else 0
    )

    # Build transcript text
    lines = []
    for segment in result.segments:
        text = segment.text
        if include_timestamps:
            timestamp = format_timestamp(segment.start)
            lines.append(f"[{timestamp}] {text}")
        else:
            lines.append(text)

    transcript_text = "\n\n".join(lines)
    word_count = count_words(transcript_text)

    # Create frontmatter
    frontmatter = create_youtube_frontmatter(
        video_url=canonical_video_url if frames_requested else video_url,
        video_id=video_id,
        duration=int(total_duration),
        language=result.language,
        word_count=word_count,
        title=video_metadata.get("title"),
        channel=video_metadata.get("channel"),
        thumbnail=None if frames_requested else video_metadata.get("thumbnail"),
        description=None if frames_requested else video_metadata.get("description"),
    )

    # Combine into markdown. Neutralize GitHub mentions so raw third-party
    # transcript/metadata output can be pasted into public issues without
    # notifying unrelated accounts.
    markdown = frontmatter + "# Video Transcript\n\n" + transcript_text

    # Metadata for response
    metadata = {
        "video_id": video_id,
        "title": video_metadata.get("title"),
        "channel": video_metadata.get("channel"),
        "duration": int(total_duration),
        "language": result.language,
        "word_count": word_count,
    }

    if frames_requested:
        assert frame_request is not None
        assert deadline is not None
        stream_info = await _wait_for_youtube_step(
            _run_in_daemon_thread(lambda: resolve_youtube_stream(video_url)),
            deadline=deadline,
            timeout=timeout,
        )
        targets = resolve_frame_targets(
            duration_seconds=stream_info.duration_seconds,
            overview_count=frame_request.overview_count,
            exact_timestamps=frame_request.exact_timestamps,
            ranges=frame_request.ranges,
            range_count=frame_request.range_count,
        )
        manifest_output = output_path or Path.cwd() / "youtube-frames.md"
        frames_dir = derive_frames_dir(output_path, frame_request.frames_dir)
        validate_frame_manifest_path(output_path, frames_dir)
        prepared_frames: tuple[str, dict[str, Any]] | None = None

        def prepare_combined_manifest(
            prepared_frame_result: FrameExtractionResult,
        ) -> FrameCommitHooks | None:
            nonlocal prepared_frames
            prepared_markdown = (
                markdown
                + "\n\n"
                + render_frames_markdown(
                    prepared_frame_result.frames,
                    output_path=manifest_output,
                )
            )
            prepared_markdown += render_frame_warnings_markdown(prepared_frame_result.failures)
            prepared_metadata = dict(metadata)
            prepared_metadata.update(
                build_frame_metadata(
                    prepared_frame_result,
                    output_path=manifest_output,
                    frames_dir=frames_dir,
                )
            )
            prepared_markdown = neutralize_github_mentions(prepared_markdown)
            if frame_manifest_writer is not None:
                prepared_markdown, prepared_metadata, hooks = frame_manifest_writer(
                    prepared_markdown, prepared_metadata
                )
                prepared_frames = prepared_markdown, prepared_metadata
                return hooks
            prepared_frames = prepared_markdown, prepared_metadata
            return None

        frame_result = await _wait_for_youtube_step(
            extract_youtube_frames(
                video_url,
                targets,
                frames_dir,
                stream_info=stream_info,
                before_commit=prepare_combined_manifest,
            ),
            deadline=deadline,
            timeout=timeout,
        )
        if prepared_frames is None:
            prepare_combined_manifest(frame_result)
        assert prepared_frames is not None
        markdown, metadata = prepared_frames

    markdown = neutralize_github_mentions(markdown)

    # Track conversion size if callback provided
    if metrics_callback is not None:
        metrics_callback("youtube", len(markdown))

    active_logger.info(
        "YouTube conversion completed",
        extra={
            "extra_fields": {
                "video_id": video_id,
                "word_count": word_count,
                "language": result.language,
                "duration": int(total_duration),
            }
        },
    )

    return markdown, metadata

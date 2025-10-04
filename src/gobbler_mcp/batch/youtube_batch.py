"""YouTube playlist batch processing."""

import logging
from pathlib import Path
from typing import List, Optional

import yt_dlp

from ..converters.youtube import convert_youtube_to_markdown
from ..utils import save_markdown_file
from .batch_manager import BatchProcessor
from .models import BatchItem, BatchResult, BatchSummary

logger = logging.getLogger(__name__)


async def get_playlist_videos(playlist_url: str, max_videos: int = 100) -> List[dict]:
    """
    Extract video URLs and metadata from YouTube playlist.

    Args:
        playlist_url: YouTube playlist URL
        max_videos: Maximum number of videos to extract

    Returns:
        List of video dictionaries with id, url, title

    Raises:
        ValueError: If playlist URL is invalid or empty
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playlistend": max_videos,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)

            if not info:
                raise ValueError("Failed to extract playlist information")

            if "entries" not in info:
                raise ValueError("Invalid playlist URL or playlist is empty")

            videos = []
            for entry in info["entries"]:
                if entry and "id" in entry:
                    videos.append(
                        {
                            "video_id": entry["id"],
                            "url": f"https://youtube.com/watch?v={entry['id']}",
                            "title": entry.get("title", f"video_{entry['id']}"),
                        }
                    )

            if not videos:
                raise ValueError("No videos found in playlist")

            logger.info(f"Extracted {len(videos)} videos from playlist")
            return videos

    except Exception as e:
        logger.error(f"Failed to extract playlist videos: {e}")
        raise ValueError(f"Failed to extract playlist: {str(e)}")


async def process_youtube_batch(
    playlist_url: str,
    output_dir: str,
    include_timestamps: bool = False,
    language: str = "auto",
    max_videos: int = 100,
    concurrency: int = 3,
    skip_existing: bool = True,
    batch_id: Optional[str] = None,
) -> BatchSummary:
    """
    Process YouTube playlist videos in batch.

    Args:
        playlist_url: YouTube playlist URL
        output_dir: Directory to save transcripts
        include_timestamps: Include timestamps in transcripts
        language: Transcript language code or 'auto'
        max_videos: Maximum videos to process
        concurrency: Number of concurrent downloads
        skip_existing: Skip videos with existing files
        batch_id: Optional batch ID (auto-generated if None)

    Returns:
        BatchSummary with processing results
    """
    # Get playlist videos
    videos = await get_playlist_videos(playlist_url, max_videos)

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Convert to BatchItems
    items = []
    for video in videos:
        # Sanitize filename
        safe_title = "".join(
            c for c in video["title"] if c.isalnum() or c in (" ", "-", "_")
        ).strip()
        safe_title = safe_title.replace(" ", "_") or f"video_{video['video_id']}"

        output_file = output_path / f"{safe_title}.md"

        items.append(
            BatchItem(
                id=video["video_id"],
                source=video["url"],
                metadata={
                    "title": video["title"],
                    "expected_output": str(output_file),
                },
            )
        )

    # Process function for single video
    async def process_video(item: BatchItem) -> BatchResult:
        """Process single YouTube video."""
        try:
            # Get expected output path
            expected_path = Path(item.metadata["expected_output"])

            # Check if should skip
            if skip_existing and expected_path.exists():
                return BatchResult(
                    item_id=item.id,
                    success=False,
                    error="skipped",
                    metadata={"reason": "File already exists"},
                )

            # Convert to markdown
            markdown, metadata = await convert_youtube_to_markdown(
                video_url=item.source,
                include_timestamps=include_timestamps,
                language=language,
            )

            # Get unique output path (handles duplicates)
            output_file = expected_path
            if output_file.exists():
                # Add numeric suffix
                counter = 1
                while output_file.exists():
                    output_file = expected_path.parent / f"{expected_path.stem}_{counter}.md"
                    counter += 1

            # Save to file
            success = await save_markdown_file(str(output_file), markdown)

            if not success:
                return BatchResult(
                    item_id=item.id,
                    success=False,
                    error="Failed to write file",
                )

            return BatchResult(
                item_id=item.id,
                success=True,
                output_file=str(output_file),
                metadata={
                    "title": item.metadata["title"],
                    "word_count": metadata.get("word_count", 0),
                },
            )

        except Exception as e:
            logger.error(f"Error processing video {item.source}: {e}")
            return BatchResult(
                item_id=item.id,
                success=False,
                error=str(e),
            )

    # Create batch processor
    processor = BatchProcessor(
        batch_id=batch_id,
        items=items,
        process_fn=process_video,
        concurrency=concurrency,
        output_dir=str(output_path),
        skip_existing=skip_existing,
        operation_type="youtube_playlist",
    )

    # Run batch
    summary = await processor.run()

    logger.info(
        f"Batch complete: {summary.successful}/{summary.total_items} successful"
    )

    return summary

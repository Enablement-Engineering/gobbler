# PRD-002: Batch Processing System

## Overview
**Epic**: Batch Operations & Productivity
**Phase**: 2 - Feature Enhancement
**Estimated Effort**: 4-5 days
**Dependencies**: PRD-001 (Testing Infrastructure) recommended but not required
**Parallel**: ✅ Can be implemented alongside monitoring/observability

## Problem Statement
Gobbler MCP currently processes content one item at a time, which is inefficient for users who need to:
- Transcribe entire YouTube playlists (10-100+ videos)
- Convert multiple web pages from a list of URLs
- Process a directory of documents or audio files
- Monitor long-running batch operations with progress tracking

Users must manually invoke tools repeatedly, which is time-consuming and provides no visibility into overall progress.

**User Stories:**
- "As a researcher, I want to transcribe all videos from a YouTube playlist so I can analyze an entire series"
- "As a content curator, I want to convert 50 blog posts to markdown so I can process them for my knowledge base"
- "As a podcaster, I want to transcribe all episode files in a directory so I can generate show notes in bulk"

## Success Criteria
- [ ] Batch process YouTube playlists (up to 100 videos)
- [ ] Batch process multiple URLs (web pages or videos)
- [ ] Batch process directories of files (audio/video/documents)
- [ ] Real-time progress tracking with ETA
- [ ] Configurable concurrency limits (avoid rate limiting)
- [ ] Partial failure handling (continue on error)
- [ ] Results summary report with success/failure counts
- [ ] Integration with existing queue system

## Technical Requirements

### New MCP Tools

#### 1. `batch_transcribe_youtube_playlist`

```python
@mcp.tool()
async def batch_transcribe_youtube_playlist(
    playlist_url: str,
    output_dir: str,
    include_timestamps: bool = False,
    language: str = "auto",
    max_videos: int = 100,
    concurrency: int = 3,
    skip_existing: bool = True,
) -> str:
    """
    Extract transcripts from all videos in a YouTube playlist.

    Processes videos sequentially or with limited concurrency to avoid rate limiting.
    Automatically sanitizes filenames and creates output directory structure.

    Args:
        playlist_url: YouTube playlist URL (youtube.com/playlist?list=...)
        output_dir: Directory to save markdown transcripts (must be absolute path)
        include_timestamps: Include timestamp markers in transcripts (default: False)
        language: Transcript language code or 'auto' (default: 'auto')
        max_videos: Maximum number of videos to process (default: 100, max: 500)
        concurrency: Number of videos to process concurrently (default: 3, max: 10)
        skip_existing: Skip videos that already have output files (default: True)

    Returns:
        Batch job summary with:
        - Total videos found
        - Videos processed
        - Success/failure counts
        - List of generated files
        - Any errors encountered
    """
```

**Implementation:**
```python
# src/gobbler_mcp/converters/batch_youtube.py
import asyncio
from typing import List, Dict
from pathlib import Path
import yt_dlp
from ..converters.youtube import convert_youtube_to_markdown
from ..utils import save_markdown_file

async def get_playlist_videos(playlist_url: str, max_videos: int) -> List[Dict]:
    """Extract video URLs and metadata from playlist"""
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'playlistend': max_videos,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)

        if 'entries' not in info:
            raise ValueError("Invalid playlist URL or playlist is empty")

        videos = []
        for entry in info['entries']:
            if entry:
                videos.append({
                    'video_id': entry['id'],
                    'url': f"https://youtube.com/watch?v={entry['id']}",
                    'title': entry.get('title', f"video_{entry['id']}"),
                })

        return videos

async def process_video_batch(
    videos: List[Dict],
    output_dir: Path,
    include_timestamps: bool,
    language: str,
    concurrency: int,
    skip_existing: bool,
) -> Dict:
    """Process videos with controlled concurrency"""
    semaphore = asyncio.Semaphore(concurrency)
    results = {
        'successful': [],
        'failed': [],
        'skipped': [],
    }

    async def process_single_video(video: Dict):
        async with semaphore:
            # Sanitize filename
            safe_title = "".join(
                c for c in video['title'] if c.isalnum() or c in (' ', '-', '_')
            ).strip().replace(' ', '_')
            output_file = output_dir / f"{safe_title}.md"

            # Skip if exists
            if skip_existing and output_file.exists():
                results['skipped'].append({
                    'video_id': video['video_id'],
                    'title': video['title'],
                    'reason': 'File already exists'
                })
                return

            try:
                # Convert to markdown
                markdown, metadata = await convert_youtube_to_markdown(
                    video_url=video['url'],
                    include_timestamps=include_timestamps,
                    language=language,
                )

                # Save to file
                await save_markdown_file(str(output_file), markdown)

                results['successful'].append({
                    'video_id': video['video_id'],
                    'title': video['title'],
                    'output_file': str(output_file),
                    'word_count': metadata['word_count'],
                })

            except Exception as e:
                results['failed'].append({
                    'video_id': video['video_id'],
                    'title': video['title'],
                    'error': str(e),
                })

    # Process all videos
    await asyncio.gather(*[process_single_video(v) for v in videos])

    return results
```

#### 2. `batch_fetch_webpages`

```python
@mcp.tool()
async def batch_fetch_webpages(
    urls: List[str],
    output_dir: str,
    include_images: bool = True,
    timeout: int = 30,
    concurrency: int = 5,
    skip_existing: bool = True,
) -> str:
    """
    Convert multiple web pages to markdown format.

    Processes URLs with controlled concurrency to avoid overwhelming target servers.
    Automatically generates filenames from page titles or URLs.

    Args:
        urls: List of web page URLs to convert (max: 100 URLs per batch)
        output_dir: Directory to save markdown files (must be absolute path)
        include_images: Include image references in markdown (default: True)
        timeout: Request timeout per page in seconds (default: 30, max: 120)
        concurrency: Number of pages to process concurrently (default: 5, max: 10)
        skip_existing: Skip URLs that already have output files (default: True)

    Returns:
        Batch job summary with:
        - Total URLs provided
        - Pages processed
        - Success/failure counts
        - List of generated files
        - Processing time
    """
```

#### 3. `batch_transcribe_directory`

```python
@mcp.tool()
async def batch_transcribe_directory(
    input_dir: str,
    output_dir: Optional[str] = None,
    model: str = "small",
    language: str = "auto",
    pattern: str = "*.{mp3,mp4,wav,m4a,mov,avi,mkv}",
    recursive: bool = False,
    concurrency: int = 2,
    skip_existing: bool = True,
    auto_queue_large_files: bool = True,
) -> str:
    """
    Transcribe all audio/video files in a directory.

    Automatically detects supported file formats and processes them with Whisper.
    Large files (>50MB) can be automatically queued for background processing.

    Args:
        input_dir: Directory containing audio/video files (must be absolute path)
        output_dir: Directory for transcripts (default: same as input_dir)
        model: Whisper model size (default: 'small', options: tiny, base, small, medium, large)
        language: Audio language code or 'auto' (default: 'auto')
        pattern: Glob pattern for file matching (default: common audio/video extensions)
        recursive: Search subdirectories (default: False)
        concurrency: Number of files to process concurrently (default: 2, max: 4)
        skip_existing: Skip files with existing transcript files (default: True)
        auto_queue_large_files: Queue files >50MB to background worker (default: True)

    Returns:
        Batch job summary with:
        - Total files found
        - Files processed
        - Files queued (if auto_queue enabled)
        - Success/failure counts
        - Processing statistics
    """
```

#### 4. `batch_convert_documents`

```python
@mcp.tool()
async def batch_convert_documents(
    input_dir: str,
    output_dir: Optional[str] = None,
    enable_ocr: bool = True,
    pattern: str = "*.{pdf,docx,pptx,xlsx}",
    recursive: bool = False,
    concurrency: int = 3,
    skip_existing: bool = True,
) -> str:
    """
    Convert all documents in a directory to markdown.

    Supports PDF, DOCX, PPTX, XLSX with optional OCR for scanned documents.

    Args:
        input_dir: Directory containing documents (must be absolute path)
        output_dir: Directory for markdown files (default: same as input_dir)
        enable_ocr: Enable OCR for scanned documents (default: True)
        pattern: Glob pattern for file matching (default: common document types)
        recursive: Search subdirectories (default: False)
        concurrency: Number of documents to process concurrently (default: 3, max: 5)
        skip_existing: Skip documents with existing markdown files (default: True)

    Returns:
        Batch job summary with processing statistics
    """
```

#### 5. `get_batch_progress`

```python
@mcp.tool()
async def get_batch_progress(batch_id: str) -> str:
    """
    Get real-time progress for a running batch operation.

    Provides detailed progress information including current item, success/failure
    counts, estimated time remaining, and any errors encountered.

    Args:
        batch_id: Batch operation ID returned when batch was started

    Returns:
        Progress report with:
        - Current status (running/completed/failed)
        - Items processed / total items
        - Success and failure counts
        - Current item being processed
        - Estimated time remaining
        - Errors list (if any)
    """
```

### Implementation Architecture

```python
# src/gobbler_mcp/batch/
├── __init__.py
├── batch_manager.py          # Core batch processing logic
├── progress_tracker.py       # Progress tracking with Redis
├── youtube_batch.py          # YouTube playlist processing
├── webpage_batch.py          # Webpage batch processing
├── file_batch.py            # File directory processing
└── models.py                # Batch job models

# src/gobbler_mcp/batch/batch_manager.py
from dataclasses import dataclass
from typing import List, Dict, Callable, Any
import asyncio
import uuid
from datetime import datetime
from .progress_tracker import ProgressTracker

@dataclass
class BatchItem:
    """Single item in a batch operation"""
    id: str
    source: str  # URL, file path, etc.
    metadata: Dict[str, Any]

@dataclass
class BatchResult:
    """Result of processing a batch item"""
    item_id: str
    success: bool
    output_file: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

class BatchProcessor:
    """Generic batch processing engine"""

    def __init__(
        self,
        batch_id: str,
        items: List[BatchItem],
        process_fn: Callable,
        concurrency: int = 3,
        progress_tracker: Optional[ProgressTracker] = None,
    ):
        self.batch_id = batch_id
        self.items = items
        self.process_fn = process_fn
        self.concurrency = concurrency
        self.progress = progress_tracker or ProgressTracker(batch_id)
        self.results: List[BatchResult] = []

    async def run(self) -> Dict:
        """Execute batch operation with progress tracking"""
        await self.progress.initialize(total_items=len(self.items))
        semaphore = asyncio.Semaphore(self.concurrency)

        async def process_with_tracking(item: BatchItem):
            async with semaphore:
                try:
                    await self.progress.update_current_item(item.source)
                    result = await self.process_fn(item)
                    await self.progress.increment_success()
                    return result
                except Exception as e:
                    await self.progress.increment_failure(str(e))
                    return BatchResult(
                        item_id=item.id,
                        success=False,
                        error=str(e)
                    )

        # Process all items
        self.results = await asyncio.gather(
            *[process_with_tracking(item) for item in self.items]
        )

        # Generate summary
        return await self._generate_summary()

    async def _generate_summary(self) -> Dict:
        """Generate batch operation summary"""
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]

        return {
            'batch_id': self.batch_id,
            'total_items': len(self.items),
            'successful': len(successful),
            'failed': len(failed),
            'success_details': [
                {
                    'source': self.items[i].source,
                    'output_file': r.output_file,
                    'metadata': r.metadata,
                }
                for i, r in enumerate(self.results) if r.success
            ],
            'failures': [
                {
                    'source': self.items[i].source,
                    'error': r.error,
                }
                for i, r in enumerate(self.results) if not r.success
            ],
        }

# src/gobbler_mcp/batch/progress_tracker.py
from typing import Optional
import redis
import json
from datetime import datetime
from ..config import get_config

class ProgressTracker:
    """Track batch operation progress in Redis"""

    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self.redis_key = f"batch:progress:{batch_id}"
        config = get_config()
        self.redis = redis.Redis(
            host=config.get('redis.host'),
            port=config.get('redis.port'),
            decode_responses=True
        )

    async def initialize(self, total_items: int):
        """Initialize progress tracking"""
        data = {
            'batch_id': self.batch_id,
            'total_items': total_items,
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'current_item': None,
            'started_at': datetime.utcnow().isoformat(),
            'status': 'running',
            'errors': [],
        }
        self.redis.setex(
            self.redis_key,
            3600 * 24,  # Expire after 24 hours
            json.dumps(data)
        )

    async def update_current_item(self, item: str):
        """Update currently processing item"""
        data = json.loads(self.redis.get(self.redis_key))
        data['current_item'] = item
        data['processed'] = data.get('processed', 0) + 1
        self.redis.setex(self.redis_key, 3600 * 24, json.dumps(data))

    async def increment_success(self):
        """Increment success counter"""
        data = json.loads(self.redis.get(self.redis_key))
        data['successful'] = data.get('successful', 0) + 1
        self.redis.setex(self.redis_key, 3600 * 24, json.dumps(data))

    async def increment_failure(self, error: str):
        """Increment failure counter and log error"""
        data = json.loads(self.redis.get(self.redis_key))
        data['failed'] = data.get('failed', 0) + 1
        data['errors'].append({
            'error': error,
            'timestamp': datetime.utcnow().isoformat()
        })
        self.redis.setex(self.redis_key, 3600 * 24, json.dumps(data))

    async def mark_complete(self):
        """Mark batch as complete"""
        data = json.loads(self.redis.get(self.redis_key))
        data['status'] = 'completed'
        data['completed_at'] = datetime.utcnow().isoformat()
        self.redis.setex(self.redis_key, 3600 * 24, json.dumps(data))

    async def get_progress(self) -> dict:
        """Get current progress"""
        data = self.redis.get(self.redis_key)
        if not data:
            return None
        return json.loads(data)
```

### Output Format

All batch tools return a formatted summary:

```markdown
# Batch Operation Summary

**Batch ID:** abc-123-def-456
**Operation:** YouTube Playlist Transcription
**Status:** ✅ Completed

## Statistics
- **Total Items:** 25
- **Successful:** 23 (92%)
- **Failed:** 2 (8%)
- **Skipped:** 0
- **Processing Time:** 12 minutes 34 seconds

## Successful Items
1. ✅ video_title_1.md (1,247 words)
2. ✅ video_title_2.md (2,103 words)
...

## Failed Items
1. ❌ video_title_23 - Error: Transcript not available
2. ❌ video_title_25 - Error: Video is private

## Output Location
All files saved to: /Users/name/Documents/transcripts/

Check progress anytime with: get_batch_progress(batch_id="abc-123-def-456")
```

## Acceptance Criteria

### 1. YouTube Playlist Processing
- [ ] Extract all videos from playlist URL
- [ ] Process videos with configurable concurrency
- [ ] Generate individual markdown files
- [ ] Handle unavailable videos gracefully
- [ ] Respect max_videos limit
- [ ] Skip existing files when requested

### 2. Webpage Batch Processing
- [ ] Accept list of URLs (up to 100)
- [ ] Process with rate limiting
- [ ] Generate filenames from page titles
- [ ] Handle HTTP errors per URL
- [ ] Continue on individual failures

### 3. Directory Processing
- [ ] Scan directory with glob patterns
- [ ] Support recursive scanning
- [ ] Process files with concurrency control
- [ ] Queue large files automatically
- [ ] Generate summary report

### 4. Progress Tracking
- [ ] Real-time progress updates in Redis
- [ ] Current item visibility
- [ ] Success/failure counters
- [ ] Error logging
- [ ] ETA calculation

### 5. Error Handling
- [ ] Continue on individual item failures
- [ ] Log errors with context
- [ ] Provide detailed failure report
- [ ] Partial success handling

## Deliverables

### Files to Create
```
src/gobbler_mcp/
├── batch/
│   ├── __init__.py
│   ├── batch_manager.py       # Core batch engine
│   ├── progress_tracker.py    # Redis-based progress tracking
│   ├── youtube_batch.py       # Playlist processing
│   ├── webpage_batch.py       # URL batch processing
│   ├── file_batch.py          # Directory processing
│   └── models.py              # Data models
└── server.py                  # Add new batch tools

tests/
├── unit/
│   ├── test_batch_manager.py
│   ├── test_progress_tracker.py
│   └── test_youtube_batch.py
└── integration/
    ├── test_batch_playlist.py
    └── test_batch_directory.py
```

## Technical Notes

### Rate Limiting Considerations
- YouTube API: Max 3 concurrent requests (avoid rate limiting)
- Web scraping: Respect robots.txt, configurable delay between requests
- Whisper: Max 2-4 concurrent (memory intensive)
- Document conversion: Max 3-5 concurrent (Docling throughput)

### Memory Management
- Process items in chunks if list is very large
- Clean up temporary files after each item
- Monitor memory usage during batch operations

### Queue Integration
- Large batch operations can be queued entirely
- Individual large items auto-queued when `auto_queue_large_files=True`
- Progress tracking works for both immediate and queued batches

## Definition of Done
- [ ] All batch tools implemented and working
- [ ] Progress tracking functional with Redis
- [ ] Tests cover batch processing logic
- [ ] Documentation updated with examples
- [ ] Error handling comprehensive
- [ ] Performance acceptable for 100+ item batches
- [ ] Integration with existing queue system working
- [ ] Summary reports generated correctly

## References
- yt-dlp playlist extraction: https://github.com/yt-dlp/yt-dlp#playlist-options
- Python asyncio semaphores: https://docs.python.org/3/library/asyncio-sync.html#semaphores
- Redis for progress tracking: https://redis.io/docs/data-types/strings/

# Test Fixtures

This directory contains test data for comprehensive e2e testing of all Gobbler MCP endpoints.

## Directory Structure

```
fixtures/
├── README.md                          # This file
├── test_links.md                      # All test links organized by type
├── youtube_urls.txt                   # CrashCourse AI video URLs for batch testing
├── youtube_playlist.txt               # CrashCourse AI playlist URL
├── webpage_urls.txt                   # Pydantic AI docs URLs for batch testing
├── test_audio.wav                     # Sample audio file
├── How_Games_Do_Destruction.mp4       # Sample video file
├── Dylan_Isaac_Resume_AI.pdf          # Sample PDF document
└── expected_outputs/                  # Expected output samples
    └── youtube_transcript.md
```

## Test Data Overview

### YouTube Content

**Single Videos** (`youtube_urls.txt`)
- 10 CrashCourse AI videos (educational series)
- 1 short test video
- Coverage: Short & long videos, different topics

**Playlists** (`youtube_playlist.txt`)
- CrashCourse AI full series (20+ videos)
- Tests batch processing capabilities

### Web Content

**Documentation Pages** (`webpage_urls.txt`)
- 20+ Pydantic AI documentation pages
- Coverage: Different page types, nested navigation
- Good for batch fetching and site crawling tests

### Local Media Files

**Audio**
- `test_audio.wav` - 4 second test audio
- Tests: transcribe_audio endpoint

**Video**
- `How_Games_Do_Destruction.mp4` - ~53MB video
- Tests: transcribe_audio, download_youtube_video

**Documents**
- `Dylan_Isaac_Resume_AI.pdf` - ~7.5KB PDF
- Tests: convert_document endpoint

## Endpoint Coverage

### Single Item Endpoints

1. **transcribe_youtube**
   - Use: Any URL from `youtube_urls.txt`
   - Test with/without timestamps
   - Test different languages

2. **fetch_webpage**
   - Use: Any URL from `webpage_urls.txt`
   - Test with/without images
   - Test different timeouts

3. **fetch_webpage_with_selector**
   - Use: URLs from "Selector Test URLs" in `test_links.md`
   - Test CSS selectors, XPath
   - Test link extraction

4. **convert_document**
   - Use: `Dylan_Isaac_Resume_AI.pdf`
   - Test with/without OCR
   - Add more document types: .docx, .pptx, .xlsx

5. **transcribe_audio**
   - Use: `test_audio.wav` or `How_Games_Do_Destruction.mp4`
   - Test different models (tiny, small, medium)
   - Test different languages

6. **download_youtube_video**
   - Use: Any URL from `youtube_urls.txt`
   - Test different qualities
   - Test different formats

### Batch Endpoints

7. **batch_transcribe_youtube_playlist**
   - Use: `youtube_playlist.txt`
   - Test with max_videos limit
   - Test skip_existing functionality

8. **batch_fetch_webpages**
   - Use: All URLs from `webpage_urls.txt`
   - Test concurrency settings
   - Test error handling

9. **batch_transcribe_directory**
   - Create directory with multiple audio/video files
   - Test recursive scanning
   - Test pattern matching

10. **batch_convert_documents**
    - Create directory with multiple PDFs
    - Test different document types
    - Test OCR settings

### Advanced Endpoints

11. **crawl_site**
    - Use: https://ai.pydantic.dev/
    - Test depth limits
    - Test URL pattern filtering
    - Test robots.txt respect

12. **create_crawl_session**
    - Test session creation with cookies
    - Test localStorage persistence
    - Use with fetch_webpage_with_selector

### Queue/Job Endpoints

13. **get_job_status**
    - Test with queued jobs from auto_queue
    - Test job progress tracking

14. **list_jobs**
    - Test different queue types
    - Test pagination with limit

15. **get_batch_progress**
    - Test with running batch operations
    - Test progress reporting

## Adding New Test Data

### YouTube Videos
Add to `youtube_urls.txt` with descriptive comment

### Web Pages
Add to `webpage_urls.txt` organized by site/topic

### Documents
Add files to this directory and update this README

### Expected Outputs
Place in `expected_outputs/` for comparison testing

## Usage Examples

### Quick Single Tests
```python
# Transcribe YouTube
transcribe_youtube("https://www.youtube.com/watch?v=GvYYFloV0aA")

# Fetch webpage
fetch_webpage("https://ai.pydantic.dev/")

# Convert document
convert_document("/path/to/fixtures/Dylan_Isaac_Resume_AI.pdf")

# Transcribe audio
transcribe_audio("/path/to/fixtures/test_audio.wav")
```

### Batch Tests
```python
# Read URLs from file
with open("youtube_urls.txt") as f:
    urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

# Batch fetch
batch_fetch_webpages(urls, output_dir="/tmp/batch_output")
```

### Full E2E Suite
Run through all endpoints systematically using the test data provided.

## Notes

- CrashCourse videos chosen for educational value and consistent quality
- Pydantic AI docs chosen for well-structured documentation
- Local files kept small for fast testing
- All URLs verified working as of October 2025

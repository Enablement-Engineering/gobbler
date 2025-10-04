# Gobbler MCP E2E Testing Guide

Complete guide for testing all 15 MCP endpoints with real, comprehensive test data.

## 📁 Test Data Overview

```
tests/fixtures/
├── README.md                          # Main fixtures documentation
├── E2E_TEST_GUIDE.md                  # This file
├── test_config.json                   # JSON test configuration
├── test_links.md                      # All test links organized
│
├── Single Test Files
├── test_audio.wav                     # 4-second audio sample
├── How_Games_Do_Destruction.mp4       # 53MB video file
├── Dylan_Isaac_Resume_AI.pdf          # 7.5KB PDF document
│
├── URL Lists
├── youtube_urls.txt                   # 11 CrashCourse AI videos
├── youtube_playlist.txt               # CrashCourse AI full playlist
├── webpage_urls.txt                   # 20+ Pydantic AI docs pages
│
└── Batch Test Directories
    ├── batch_audio/                   # 3 audio files (symlinks)
    ├── batch_documents/               # 3 PDF files (symlinks)
    └── batch_videos/                  # For downloaded videos
```

## 🎯 Endpoint Testing Matrix

### ✅ Tested & Working

1. **transcribe_audio** - Audio transcription with Whisper
2. **transcribe_youtube** - YouTube transcript extraction
3. **batch_transcribe_directory** - Batch audio processing

### 🔧 Requires Docker Services

4. **fetch_webpage** - Requires: `docker-compose up -d crawl4ai`
5. **fetch_webpage_with_selector** - Requires: `docker-compose up -d crawl4ai`
6. **crawl_site** - Requires: `docker-compose up -d crawl4ai`
7. **convert_document** - Requires: `docker-compose up -d docling`
8. **batch_fetch_webpages** - Requires: `docker-compose up -d crawl4ai`
9. **batch_convert_documents** - Requires: `docker-compose up -d docling`

### 📋 All Endpoints (15 Total)

| # | Endpoint | Test Data | Status |
|---|----------|-----------|--------|
| 1 | `transcribe_youtube` | youtube_urls.txt | ✅ Working |
| 2 | `fetch_webpage` | webpage_urls.txt | 🔧 Needs crawl4ai |
| 3 | `fetch_webpage_with_selector` | webpage_urls.txt | 🔧 Needs crawl4ai |
| 4 | `create_crawl_session` | Manual | 📝 Manual test |
| 5 | `crawl_site` | ai.pydantic.dev | 🔧 Needs crawl4ai |
| 6 | `convert_document` | Dylan_Isaac_Resume_AI.pdf | 🔧 Needs docling |
| 7 | `download_youtube_video` | youtube_urls.txt | 📝 Ready to test |
| 8 | `transcribe_audio` | test_audio.wav | ✅ Working |
| 9 | `get_job_status` | Auto-generated | 📝 Test with queued jobs |
| 10 | `list_jobs` | Auto-generated | 📝 Test with queued jobs |
| 11 | `batch_transcribe_youtube_playlist` | youtube_playlist.txt | 📝 Ready to test |
| 12 | `batch_fetch_webpages` | webpage_urls.txt | 🔧 Needs crawl4ai |
| 13 | `batch_transcribe_directory` | batch_audio/ | ✅ Working |
| 14 | `batch_convert_documents` | batch_documents/ | 🔧 Needs docling |
| 15 | `get_batch_progress` | Auto-generated | 📝 Test with batch ops |

## 🚀 Quick Start Testing

### 1. Start Docker Services

```bash
cd /Users/dylanisaac/Projects/gobbler
docker-compose up -d crawl4ai docling
```

### 2. Single Endpoint Tests

#### YouTube Transcription
```python
transcribe_youtube(
    video_url="https://www.youtube.com/watch?v=GvYYFloV0aA",
    include_timestamps=False,
    output_file="/tmp/gobbler_e2e_tests/youtube/crashcourse_ai_01.md"
)
```

#### Audio Transcription
```python
transcribe_audio(
    file_path="/Users/dylanisaac/Projects/gobbler/tests/fixtures/test_audio.wav",
    model="small",
    output_file="/tmp/gobbler_e2e_tests/audio/test_audio.md"
)
```

#### Webpage Fetch
```python
fetch_webpage(
    url="https://ai.pydantic.dev/",
    include_images=True,
    output_file="/tmp/gobbler_e2e_tests/webpages/pydantic_home.md"
)
```

#### Document Conversion
```python
convert_document(
    file_path="/Users/dylanisaac/Projects/gobbler/tests/fixtures/Dylan_Isaac_Resume_AI.pdf",
    enable_ocr=True,
    output_file="/tmp/gobbler_e2e_tests/documents/resume.md"
)
```

### 3. Batch Operations

#### Batch Audio Transcription
```python
batch_transcribe_directory(
    input_dir="/Users/dylanisaac/Projects/gobbler/tests/fixtures/batch_audio",
    output_dir="/tmp/gobbler_e2e_tests/batch/audio",
    model="small",
    concurrency=2
)
```

#### Batch YouTube Playlist
```python
batch_transcribe_youtube_playlist(
    playlist_url="https://www.youtube.com/playlist?list=PL8dPuuaLjXtO65LeD2p4_Sb5XQ51par_b",
    output_dir="/tmp/gobbler_e2e_tests/batch/youtube",
    max_videos=5,
    concurrency=2
)
```

#### Batch Webpages
```python
# Read URLs from file
with open("/Users/dylanisaac/Projects/gobbler/tests/fixtures/webpage_urls.txt") as f:
    urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

batch_fetch_webpages(
    urls=urls[:5],  # First 5 URLs
    output_dir="/tmp/gobbler_e2e_tests/batch/webpages",
    concurrency=3
)
```

#### Batch Documents
```python
batch_convert_documents(
    input_dir="/Users/dylanisaac/Projects/gobbler/tests/fixtures/batch_documents",
    output_dir="/tmp/gobbler_e2e_tests/batch/documents",
    enable_ocr=True,
    concurrency=2
)
```

### 4. Advanced Features

#### Site Crawler
```python
crawl_site(
    start_url="https://ai.pydantic.dev/",
    max_depth=2,
    max_pages=20,
    css_selector="article",
    output_dir="/tmp/gobbler_e2e_tests/crawled/pydantic_ai"
)
```

#### Webpage with Selector
```python
fetch_webpage_with_selector(
    url="https://ai.pydantic.dev/examples/",
    css_selector="article",
    extract_links=True,
    output_file="/tmp/gobbler_e2e_tests/webpages/examples.md"
)
```

#### Create Crawl Session
```python
create_crawl_session(
    session_id="test-session",
    cookies='[{"name": "session", "value": "test123", "domain": "example.com"}]',
    local_storage='{"theme": "dark"}'
)
```

## 📊 Comprehensive Test Suite

### Test All Single Endpoints

```python
# 1. YouTube Transcription
print("Testing transcribe_youtube...")
result = transcribe_youtube(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    output_file="/tmp/gobbler_e2e_tests/youtube/test1.md"
)
print(result)

# 2. Audio Transcription
print("\nTesting transcribe_audio...")
result = transcribe_audio(
    "/Users/dylanisaac/Projects/gobbler/tests/fixtures/test_audio.wav",
    model="tiny",
    output_file="/tmp/gobbler_e2e_tests/audio/test1.md"
)
print(result)

# 3. Webpage Fetch (requires crawl4ai)
print("\nTesting fetch_webpage...")
result = fetch_webpage(
    "https://ai.pydantic.dev/",
    output_file="/tmp/gobbler_e2e_tests/webpages/test1.md"
)
print(result)

# 4. Document Conversion (requires docling)
print("\nTesting convert_document...")
result = convert_document(
    "/Users/dylanisaac/Projects/gobbler/tests/fixtures/Dylan_Isaac_Resume_AI.pdf",
    output_file="/tmp/gobbler_e2e_tests/documents/test1.md"
)
print(result)

# 5. Video Download
print("\nTesting download_youtube_video...")
result = download_youtube_video(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    output_dir="/tmp/gobbler_e2e_tests/downloads",
    quality="360p"
)
print(result)
```

### Test All Batch Endpoints

```python
# 1. Batch Audio
print("Testing batch_transcribe_directory...")
result = batch_transcribe_directory(
    input_dir="/Users/dylanisaac/Projects/gobbler/tests/fixtures/batch_audio",
    output_dir="/tmp/gobbler_e2e_tests/batch/audio",
    model="tiny"
)
print(result)

# 2. Batch Documents
print("\nTesting batch_convert_documents...")
result = batch_convert_documents(
    input_dir="/Users/dylanisaac/Projects/gobbler/tests/fixtures/batch_documents",
    output_dir="/tmp/gobbler_e2e_tests/batch/documents"
)
print(result)

# 3. Batch Webpages
print("\nTesting batch_fetch_webpages...")
urls = [
    "https://ai.pydantic.dev/",
    "https://ai.pydantic.dev/install/",
    "https://ai.pydantic.dev/models/"
]
result = batch_fetch_webpages(
    urls=urls,
    output_dir="/tmp/gobbler_e2e_tests/batch/webpages"
)
print(result)

# 4. Batch YouTube Playlist
print("\nTesting batch_transcribe_youtube_playlist...")
result = batch_transcribe_youtube_playlist(
    playlist_url="https://www.youtube.com/playlist?list=PL8dPuuaLjXtO65LeD2p4_Sb5XQ51par_b",
    output_dir="/tmp/gobbler_e2e_tests/batch/youtube_playlist",
    max_videos=3
)
print(result)
```

## 🎨 Test Data Details

### YouTube Videos (youtube_urls.txt)
- **11 videos** from CrashCourse AI series
- Mix of lengths: 10-15 minutes each
- Educational content with clear speech
- Great for testing transcription quality

### Web Pages (webpage_urls.txt)
- **20+ pages** from Pydantic AI documentation
- Well-structured markdown content
- Consistent layout and formatting
- Perfect for batch fetching and crawling

### Playlists (youtube_playlist.txt)
- **Full CrashCourse AI series** (20+ videos)
- Tests large-scale batch processing
- Good for queue system testing

### Local Files
- **test_audio.wav**: 4-second clear speech sample
- **How_Games_Do_Destruction.mp4**: 53MB technical video
- **Dylan_Isaac_Resume_AI.pdf**: Multi-section PDF document

## 📈 Test Results Tracking

All test outputs go to `/tmp/gobbler_e2e_tests/`:

```
/tmp/gobbler_e2e_tests/
├── youtube/           # Single YouTube transcripts
├── audio/             # Single audio transcripts
├── webpages/          # Single webpage conversions
├── documents/         # Single document conversions
├── downloads/         # Downloaded videos
├── crawled/           # Crawled sites
└── batch/
    ├── audio/         # Batch audio results
    ├── documents/     # Batch document results
    ├── webpages/      # Batch webpage results
    └── youtube_playlist/  # Playlist batch results
```

## 🔍 Validation Checklist

After running tests, verify:

- [ ] All output directories created
- [ ] Markdown files have proper YAML frontmatter
- [ ] Transcripts contain actual text content
- [ ] Batch operations show progress/summary
- [ ] Error handling works (invalid URLs, missing files)
- [ ] Queue system works for long-running tasks
- [ ] Metrics are tracked (if monitoring enabled)
- [ ] File sizes reasonable (no bloat)
- [ ] Symlinks work correctly for batch tests

## 🐛 Troubleshooting

### Crawl4AI not available
```bash
docker-compose up -d crawl4ai
# Wait 10 seconds for service to start
curl http://localhost:11235/health
```

### Docling not available
```bash
docker-compose up -d docling
# Wait 10 seconds for service to start
curl http://localhost:5001/health
```

### Whisper model download slow
- First run downloads model (~500MB for 'small')
- Use 'tiny' model for faster testing
- Models cached in ~/.cache/huggingface/

### Redis not available (for queue system)
```bash
docker-compose up -d redis
redis-cli -p 6380 ping
```

## 📝 Notes

- CrashCourse videos chosen for consistent quality and educational value
- Pydantic AI docs chosen for well-structured, up-to-date documentation
- Batch directories use symlinks to save disk space
- All test data verified working as of October 2025
- Test config JSON provides structured test case definitions

## ✨ Success Criteria

A successful E2E test run should:

1. ✅ All 15 endpoints execute without errors
2. ✅ Output files contain valid markdown with frontmatter
3. ✅ Batch operations complete with success summaries
4. ✅ Queue system tracks jobs correctly
5. ✅ Error handling works for invalid inputs
6. ✅ Services (crawl4ai, docling) respond correctly
7. ✅ Metrics tracked (if monitoring enabled)
8. ✅ Performance acceptable (see benchmarks)

## 🎯 Next Steps

1. Run full test suite with all services running
2. Validate output quality manually
3. Check metrics and performance data
4. Document any issues or edge cases
5. Create automated test scripts if needed

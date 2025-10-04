# E2E Full - Comprehensive Test Suite

Run comprehensive E2E tests for all 15 Gobbler MCP endpoints with Docker services.

**Time**: ~15-20 minutes
**Requirements**: Docker services (crawl4ai, docling, redis)
**Coverage**: All endpoints including web scraping, documents, queues

---

## Phase 1: Pre-flight Checks

### Verify Test Infrastructure
1. Check fixtures directory: `tests/fixtures/`
2. Verify all test data:
   - Single files: `test_audio.wav`, `Dylan_Isaac_Resume_AI.pdf`
   - URL lists: `youtube_urls.txt`, `webpage_urls.txt`, `youtube_playlist.txt`
   - Batch directories: `batch_audio/`, `batch_documents/`
3. Validate test config: `tests/fixtures/test_config.json`
4. Check output directory: `/tmp/gobbler_e2e_tests/` writable

### Service Health Checks

Check all Docker services availability:

```bash
# Crawl4AI (web scraping)
curl -f http://localhost:11235/health || echo "❌ Crawl4AI not available"

# Docling (document conversion)
curl -f http://localhost:5001/health || echo "❌ Docling not available"

# Redis (queue system)
redis-cli -p 6380 ping || echo "❌ Redis not available"
```

### Service Availability Matrix

```
Service        Port    Status      Required For
-----------    -----   -------     ---------------------------
crawl4ai       11235   [✅/❌]     fetch_webpage, crawl_site, batch_fetch
docling        5001    [✅/❌]     convert_document, batch_convert
redis          6380    [✅/❌]     queue system, job tracking
```

### Pre-flight Report

```
# E2E Full Test - Pre-flight

## Test Infrastructure
✅ Fixtures directory: [present/missing]
✅ Test data files: [X/Y found]
✅ Test config valid: [yes/no]
✅ Output directory: [writable/not writable]

## Docker Services
[✅/❌] crawl4ai (port 11235)
[✅/❌] docling (port 5001)
[✅/❌] redis (port 6380)

## Test Plan
- Total endpoints: 15
- Tests requiring crawl4ai: [X tests] [✅ available / ⚠️ will skip]
- Tests requiring docling: [X tests] [✅ available / ⚠️ will skip]
- Tests requiring redis: [X tests] [✅ available / ⚠️ will skip]

Ready to proceed: [YES/NO]
```

**If critical services unavailable**: Ask user to start services or skip those tests

---

## Phase 2: Test Execution

### Test Suite: All 15 Endpoints

Track progress: [X/15 complete]

#### Category 1: YouTube Tools (No Docker)

**1. transcribe_youtube - Basic**
```python
transcribe_youtube(
    video_url="https://www.youtube.com/watch?v=GvYYFloV0aA",
    include_timestamps=False,
    output_file="/tmp/gobbler_e2e_tests/youtube/test_01_basic.md"
)
```

**2. transcribe_youtube - With Timestamps**
```python
transcribe_youtube(
    video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    include_timestamps=True,
    output_file="/tmp/gobbler_e2e_tests/youtube/test_02_timestamps.md"
)
```

**3. download_youtube_video**
```python
download_youtube_video(
    video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    output_dir="/tmp/gobbler_e2e_tests/downloads",
    quality="360p",
    format="mp4"
)
```

#### Category 2: Audio/Video Transcription (No Docker)

**4. transcribe_audio - Tiny Model**
```python
transcribe_audio(
    file_path="/Users/dylanisaac/Projects/gobbler/tests/fixtures/test_audio.wav",
    model="tiny",
    output_file="/tmp/gobbler_e2e_tests/audio/test_01_tiny.md"
)
```

**5. transcribe_audio - Small Model**
```python
transcribe_audio(
    file_path="/Users/dylanisaac/Projects/gobbler/tests/fixtures/test_audio.wav",
    model="small",
    output_file="/tmp/gobbler_e2e_tests/audio/test_02_small.md"
)
```

#### Category 3: Web Scraping (Requires crawl4ai)

**6. fetch_webpage - Basic**
```python
fetch_webpage(
    url="https://ai.pydantic.dev/",
    include_images=True,
    output_file="/tmp/gobbler_e2e_tests/webpages/test_01_basic.md"
)
```

**7. fetch_webpage_with_selector - CSS**
```python
fetch_webpage_with_selector(
    url="https://ai.pydantic.dev/examples/",
    css_selector="article",
    extract_links=True,
    output_file="/tmp/gobbler_e2e_tests/webpages/test_02_selector.md"
)
```

**8. crawl_site**
```python
crawl_site(
    start_url="https://ai.pydantic.dev/",
    max_depth=1,
    max_pages=5,
    css_selector="article",
    output_dir="/tmp/gobbler_e2e_tests/crawled/pydantic"
)
```

**9. create_crawl_session**
```python
create_crawl_session(
    session_id="e2e-test-session",
    cookies='[{"name": "test", "value": "e2e", "domain": "example.com"}]',
    local_storage='{"theme": "dark"}'
)
```

#### Category 4: Document Conversion (Requires docling)

**10. convert_document - With OCR**
```python
convert_document(
    file_path="/Users/dylanisaac/Projects/gobbler/tests/fixtures/Dylan_Isaac_Resume_AI.pdf",
    enable_ocr=True,
    output_file="/tmp/gobbler_e2e_tests/documents/test_01_ocr.md"
)
```

**11. convert_document - Without OCR**
```python
convert_document(
    file_path="/Users/dylanisaac/Projects/gobbler/tests/fixtures/Dylan_Isaac_Resume_AI.pdf",
    enable_ocr=False,
    output_file="/tmp/gobbler_e2e_tests/documents/test_02_no_ocr.md"
)
```

#### Category 5: Batch Operations

**12. batch_transcribe_youtube_playlist**
```python
batch_transcribe_youtube_playlist(
    playlist_url="https://www.youtube.com/playlist?list=PL8dPuuaLjXtO65LeD2p4_Sb5XQ51par_b",
    output_dir="/tmp/gobbler_e2e_tests/batch/playlist",
    max_videos=3,
    concurrency=2,
    skip_existing=True
)
```

**13. batch_fetch_webpages** (Requires crawl4ai)
```python
batch_fetch_webpages(
    urls=[
        "https://ai.pydantic.dev/",
        "https://ai.pydantic.dev/install/",
        "https://ai.pydantic.dev/models/"
    ],
    output_dir="/tmp/gobbler_e2e_tests/batch/webpages",
    concurrency=2,
    skip_existing=True
)
```

**14. batch_transcribe_directory**
```python
batch_transcribe_directory(
    input_dir="/Users/dylanisaac/Projects/gobbler/tests/fixtures/batch_audio",
    output_dir="/tmp/gobbler_e2e_tests/batch/audio",
    model="tiny",
    concurrency=2,
    skip_existing=True
)
```

**15. batch_convert_documents** (Requires docling)
```python
batch_convert_documents(
    input_dir="/Users/dylanisaac/Projects/gobbler/tests/fixtures/batch_documents",
    output_dir="/tmp/gobbler_e2e_tests/batch/documents",
    enable_ocr=True,
    concurrency=2,
    skip_existing=True
)
```

#### Queue System Tests (Requires redis)

**Test: get_job_status**
- Use job_id from any queued operation above
- Verify status tracking works

**Test: list_jobs**
```python
list_jobs(queue_name="default", limit=10)
```

**Test: get_batch_progress**
- Use batch_id from batch operations
- Verify progress tracking

---

## Phase 3: Validation

### Output Quality Checks

For each test:

**1. YAML Frontmatter**
- [ ] Frontmatter present with `---` delimiters
- [ ] Required fields: title, source, timestamp, tool_used
- [ ] Valid YAML syntax (no parse errors)
- [ ] Metadata appropriate for content type

**2. Content Quality**
- [ ] Non-empty content after frontmatter
- [ ] Content length reasonable (not truncated)
- [ ] No error messages in markdown
- [ ] Proper markdown formatting

**3. Batch Operations**
- [ ] Summary report returned
- [ ] Expected file count matches actual
- [ ] Progress tracking worked (if applicable)

**4. File System**
- [ ] All output files created
- [ ] Proper directory structure
- [ ] File sizes reasonable (not 0 bytes, not bloated)

### Test Results Matrix

```
#  Endpoint                        Status   Time    Service    Output
-- ------------------------------  -------  ------  ---------  ------
1  transcribe_youtube (basic)      [✅/❌]  [Xs]    none       [path]
2  transcribe_youtube (ts)         [✅/❌]  [Xs]    none       [path]
3  download_youtube_video          [✅/❌]  [Xs]    none       [path]
4  transcribe_audio (tiny)         [✅/❌]  [Xs]    none       [path]
5  transcribe_audio (small)        [✅/❌]  [Xs]    none       [path]
6  fetch_webpage                   [✅/❌]  [Xs]    crawl4ai   [path]
7  fetch_webpage_with_selector     [✅/❌]  [Xs]    crawl4ai   [path]
8  crawl_site                      [✅/❌]  [Xs]    crawl4ai   [path]
9  create_crawl_session            [✅/❌]  [Xs]    crawl4ai   [path]
10 convert_document (ocr)          [✅/❌]  [Xs]    docling    [path]
11 convert_document (no ocr)       [✅/❌]  [Xs]    docling    [path]
12 batch_transcribe_playlist       [✅/❌]  [Xs]    none       [path]
13 batch_fetch_webpages            [✅/❌]  [Xs]    crawl4ai   [path]
14 batch_transcribe_directory      [✅/❌]  [Xs]    none       [path]
15 batch_convert_documents         [✅/❌]  [Xs]    docling    [path]

Queue Tests:
   get_job_status                  [✅/❌]  [Xs]    redis      n/a
   list_jobs                       [✅/❌]  [Xs]    redis      n/a
   get_batch_progress              [✅/❌]  [Xs]    redis      n/a
```

---

## Phase 4: Report

### Comprehensive Test Report

```
# E2E Full Test Results

## Executive Summary
- **Total Tests**: 15 endpoints + 3 queue tests
- **Passed**: X/18
- **Failed**: Y/18
- **Skipped**: Z/18 (missing services)
- **Duration**: XX minutes XX seconds

## Service Availability
- crawl4ai: [✅/❌] - [X/6 tests run]
- docling: [✅/❌] - [X/3 tests run]
- redis: [✅/❌] - [X/3 tests run]

## Test Results by Category

### YouTube Tools (3 tests)
✅ transcribe_youtube (basic) - Xs
✅ transcribe_youtube (timestamps) - Xs
✅ download_youtube_video - Xs

### Audio/Video Transcription (2 tests)
✅ transcribe_audio (tiny model) - Xs
✅ transcribe_audio (small model) - Xs

### Web Scraping (4 tests)
[✅/⚠️/❌] fetch_webpage - [result]
[✅/⚠️/❌] fetch_webpage_with_selector - [result]
[✅/⚠️/❌] crawl_site - [result]
[✅/⚠️/❌] create_crawl_session - [result]

### Document Conversion (2 tests)
[✅/⚠️/❌] convert_document (OCR) - [result]
[✅/⚠️/❌] convert_document (no OCR) - [result]

### Batch Operations (4 tests)
[✅/❌] batch_transcribe_playlist - [result]
[✅/⚠️/❌] batch_fetch_webpages - [result]
[✅/❌] batch_transcribe_directory - [result]
[✅/⚠️/❌] batch_convert_documents - [result]

### Queue System (3 tests)
[✅/⚠️/❌] get_job_status - [result]
[✅/⚠️/❌] list_jobs - [result]
[✅/⚠️/❌] get_batch_progress - [result]

## Failed Tests Details

[For each failed test]:
### ❌ [Test Name]
- **Error**: [error message]
- **Service**: [required service]
- **Output**: [expected path]
- **Recommendation**: [how to fix]

## Validation Summary
- YAML frontmatter valid: [X/Y]
- Content quality good: [X/Y]
- File integrity: [X/Y]
- Batch summaries correct: [X/Y]

## Output Locations
All test outputs saved to:
- `/tmp/gobbler_e2e_tests/youtube/` - YouTube tests
- `/tmp/gobbler_e2e_tests/audio/` - Audio tests
- `/tmp/gobbler_e2e_tests/webpages/` - Webpage tests
- `/tmp/gobbler_e2e_tests/documents/` - Document tests
- `/tmp/gobbler_e2e_tests/downloads/` - Downloaded videos
- `/tmp/gobbler_e2e_tests/crawled/` - Crawled sites
- `/tmp/gobbler_e2e_tests/batch/` - Batch operations

## Performance Metrics
- Fastest test: [test name] - [Xs]
- Slowest test: [test name] - [Xs]
- Average duration: [Xs]

## Recommendations

[If all passed]:
✅ **All systems operational!** Gobbler MCP is working correctly across all endpoints.

[If failures due to missing services]:
⚠️ **Start missing Docker services**:
- `docker-compose up -d crawl4ai docling redis`
- Re-run tests with `/e2e-full`

[If actual failures]:
❌ **Issues detected**: Review failed tests above and check:
- Service logs: `docker-compose logs [service]`
- Server logs: Check MCP server output
- Test data: Verify fixtures are intact

## Next Steps
1. Review any failed tests
2. Check service logs if needed
3. Validate output files manually
4. Run `/e2e-validate` to re-check outputs
```

---

## Important Rules

### ⚠️ Blocking Conditions
**STOP and report if**:
- Test fixtures directory missing
- Test config invalid
- Output directory not writable
- No Docker services available (user must choose to skip or start services)

### ✅ Execution Rules
- Run tests sequentially within categories
- Track timing for each test
- Save all outputs to `/tmp/gobbler_e2e_tests/`
- Skip tests for unavailable services (don't fail, mark as skipped)
- Use "tiny" model for faster audio tests
- Limit batch operations (small concurrency, max_videos)

### 📝 Validation Rules
- Validate every output file
- Check YAML frontmatter syntax
- Verify content quality
- Track service dependencies

---

## Success Criteria

**Full test passes if**:
1. All tests for available services pass
2. Output files valid with proper frontmatter
3. Batch operations return summaries
4. Queue system tracking works (if redis available)
5. No unexpected exceptions

**Acceptable outcomes**:
- Some tests skipped due to missing services (documented)
- Known issues documented in report
- Performance within expected ranges

---
icon: material/api
---

# API Reference

Complete API specification for Gobbler MCP tools.

For the full detailed API specification with input schemas, output formats, and error scenarios, see [API.md](https://github.com/Enablement-Engineering/gobbler/blob/main/API.md) in the repository root.

## Tool Summary

### Content Conversion

| Tool | Description |
|------|-------------|
| `transcribe_youtube` | Extract YouTube video transcript to markdown |
| `fetch_webpage` | Convert web page to markdown |
| `fetch_webpage_with_selector` | Extract specific content with CSS/XPath |
| `convert_document` | Convert PDF, DOCX, PPTX, XLSX to markdown |
| `transcribe_audio` | Transcribe audio/video files with Whisper |

### Browser Automation

| Tool | Description |
|------|-------------|
| `browser_check_connection` | Check browser extension connection |
| `browser_list_tabs` | List tabs in Gobbler group |
| `browser_navigate_to_url` | Navigate to URL |
| `browser_execute_script` | Execute JavaScript in active tab |
| `browser_execute_script_in_tab` | Execute JavaScript in specific tab |
| `browser_extract_current_page` | Extract current page as markdown |

### Crawling & Sessions

| Tool | Description |
|------|-------------|
| `create_crawl_session` | Create authenticated browser session |
| `crawl_site` | Recursively crawl website |

### YouTube

| Tool | Description |
|------|-------------|
| `download_youtube_video` | Download video to local file |

### Batch Processing

| Tool | Description |
|------|-------------|
| `batch_transcribe_youtube_playlist` | Process entire YouTube playlist |
| `batch_fetch_webpages` | Convert multiple web pages |
| `batch_transcribe_directory` | Transcribe all audio in directory |
| `batch_convert_documents` | Convert all documents in directory |

### Queue Management

| Tool | Description |
|------|-------------|
| `get_job_status` | Check queued job status |
| `list_jobs` | List jobs in queue |
| `get_batch_progress` | Get batch operation progress |

## Common Patterns

### Output Format

All tools return markdown with YAML frontmatter:

```yaml
---
source: <URL or file path>
type: <youtube_transcript|webpage|document|audio_transcript>
word_count: <number>
converted_at: <ISO 8601 timestamp>
---

# Content Title

Markdown content...
```

### Error Handling

Tools return structured errors:

```json
{
  "isError": true,
  "content": [{
    "type": "text",
    "text": "Error message with actionable guidance"
  }]
}
```

### Auto-Queue

Long-running operations support automatic background queuing:

```python
transcribe_audio(file_path="/path/to/large.mp4", auto_queue=True)
```

Returns job ID for status checking:

```python
get_job_status(job_id="abc123-def456")
```

## Service Dependencies

| Tool | Requires |
|------|----------|
| `transcribe_youtube` | None (uses YouTube API) |
| `transcribe_audio` | None (local Whisper) |
| `fetch_webpage` | Crawl4AI Docker |
| `convert_document` | Docling Docker |
| `browser_*` | Browser extension |
| Queue tools | Redis |

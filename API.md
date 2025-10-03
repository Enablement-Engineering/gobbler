# Gobbler MCP Server - API Specification

## MCP Tools

All tools follow the MCP (Model Context Protocol) specification and are exposed via JSON-RPC 2.0 over stdio transport.

---

## Tool: `transcribe_youtube`

**Description**: Extract YouTube video transcript and convert to clean markdown format. Uses official YouTube transcript API for fast, accurate results. Works without Docker containers.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "video_url": {
      "type": "string",
      "description": "YouTube video URL (youtube.com/watch?v=ID or youtu.be/ID format)",
      "pattern": "^https?://(www\\.)?(youtube\\.com/watch\\?v=|youtu\\.be/)([a-zA-Z0-9_-]{11})"
    },
    "include_timestamps": {
      "type": "boolean",
      "description": "Include timestamp markers in the transcript",
      "default": false
    },
    "language": {
      "type": "string",
      "description": "Transcript language code (ISO 639-1) or 'auto' for video default",
      "default": "auto",
      "pattern": "^(auto|[a-z]{2})$"
    },
    "output_file": {
      "type": "string",
      "description": "Optional absolute path to save markdown file (includes frontmatter)",
      "pattern": "^/.*\\.md$"
    }
  },
  "required": ["video_url"]
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "---\nsource: https://youtube.com/watch?v=dQw4w9WgXcQ\ntype: youtube_transcript\nduration: 213\nlanguage: en\nvideo_id: dQw4w9WgXcQ\nword_count: 1547\nconverted_at: 2025-10-02T14:32:11Z\n---\n\n# Video Transcript\n\nNever gonna give you up..."
  }],
  "metadata": {
    "video_id": "dQw4w9WgXcQ",
    "duration": 213,
    "language": "en",
    "word_count": 1547
  }
}
```

If `output_file` provided:
```json
{
  "content": [{
    "type": "text",
    "text": "Transcript saved to: /Users/dylan/Projects/research/video.md"
  }],
  "metadata": {
    "output_file": "/Users/dylan/Projects/research/video.md",
    "video_id": "dQw4w9WgXcQ",
    "word_count": 1547
  }
}
```

**Error Response**:
```json
{
  "isError": true,
  "content": [{
    "type": "text",
    "text": "Failed to extract transcript: No transcript available for this video. The video may not have captions, or they may be disabled. To transcribe anyway, use transcribe_audio with the video file."
  }]
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Invalid URL | `Invalid YouTube URL format. Expected: https://youtube.com/watch?v=VIDEO_ID or https://youtu.be/VIDEO_ID` |
| Video not found | `Video not found: The video may be private, deleted, or the URL is incorrect.` |
| No transcript | `No transcript available for this video. The video may not have captions, or they may be disabled. To transcribe anyway, use transcribe_audio with the video file.` |
| Language unavailable | `Transcript not available in language 'fr'. Available languages: en, es, de. Use language='auto' for default.` |
| File write error | `Failed to write file: Permission denied for /path/to/file.md` |

---

## Tool: `fetch_webpage`

**Description**: Convert web page content to clean markdown format by fetching and parsing HTML. Preserves document structure, headings, links, code blocks, and basic formatting. Handles JavaScript-rendered content via Crawl4AI. Requires Crawl4AI Docker container.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "url": {
      "type": "string",
      "description": "The full HTTP/HTTPS URL of the web page to convert",
      "pattern": "^https?://.+"
    },
    "include_images": {
      "type": "boolean",
      "description": "Include image alt text and references in markdown output",
      "default": true
    },
    "timeout": {
      "type": "number",
      "description": "Request timeout in seconds",
      "default": 30,
      "minimum": 5,
      "maximum": 120
    },
    "output_file": {
      "type": "string",
      "description": "Optional absolute path to save markdown file (includes frontmatter)",
      "pattern": "^/.*\\.md$"
    }
  },
  "required": ["url"]
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "---\nsource: https://example.com/article\ntype: webpage\ntitle: Example Article\nword_count: 2341\nconverted_at: 2025-10-02T14:35:22Z\n---\n\n# Example Article\n\nArticle content..."
  }],
  "metadata": {
    "url": "https://example.com/article",
    "title": "Example Article",
    "word_count": 2341,
    "conversion_time_ms": 2341
  }
}
```

**Error Response**:
```json
{
  "isError": true,
  "content": [{
    "type": "text",
    "text": "Crawl4AI service unavailable. The service may not be running. Start with: docker-compose up -d crawl4ai"
  }]
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Service unavailable | `Crawl4AI service unavailable. The service may not be running. Start with: docker-compose up -d crawl4ai` |
| Timeout | `Failed to fetch URL: Connection timeout after 30 seconds. The target server may be slow or the URL may be inaccessible. To increase timeout, use the timeout parameter (maximum 120 seconds).` |
| Invalid URL | `Invalid URL format. Expected: http:// or https:// followed by domain name.` |
| Network error | `Network error: Unable to resolve hostname. Check the URL and your internet connection.` |
| HTTP error | `HTTP 404: Page not found at https://example.com/missing` |
| Parsing error | `Failed to parse page content: Invalid HTML structure. The page may be malformed.` |

---

## Tool: `convert_document`

**Description**: Convert document files (PDF, DOCX, PPTX, XLSX) to clean markdown format. Preserves structure including tables, headings, lists, and code blocks. Supports OCR for scanned documents. Requires Docling Docker container.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "file_path": {
      "type": "string",
      "description": "Absolute path to the document file to convert",
      "pattern": "^/.+\\.(pdf|docx|pptx|xlsx)$"
    },
    "enable_ocr": {
      "type": "boolean",
      "description": "Enable OCR for scanned documents (slower but handles image-based PDFs)",
      "default": true
    },
    "output_file": {
      "type": "string",
      "description": "Optional absolute path to save markdown file (includes frontmatter)",
      "pattern": "^/.*\\.md$"
    }
  },
  "required": ["file_path"]
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "---\nsource: /Users/dylan/Documents/report.pdf\ntype: document\nformat: pdf\npages: 42\nword_count: 8234\nconverted_at: 2025-10-02T14:40:11Z\n---\n\n# Report Title\n\nContent from PDF..."
  }],
  "metadata": {
    "file_path": "/Users/dylan/Documents/report.pdf",
    "format": "pdf",
    "pages": 42,
    "word_count": 8234,
    "conversion_time_ms": 5234
  }
}
```

**Error Response**:
```json
{
  "isError": true,
  "content": [{
    "type": "text",
    "text": "Docling service unavailable. The service may not be running. Start with: docker-compose up -d docling"
  }]
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Service unavailable | `Docling service unavailable. The service may not be running. Start with: docker-compose up -d docling` |
| File not found | `File not found: /path/to/file.pdf. Verify the path is correct and the file exists.` |
| Unsupported format | `Unsupported file format: .txt. This tool supports PDF, DOCX, PPTX, XLSX. For web content, try fetch_webpage.` |
| OCR failure | `OCR processing failed: Unable to extract text from scanned pages. The document may be corrupted or use unsupported encoding.` |
| Out of memory | `Conversion failed: Out of memory while processing large document. Try splitting the document into smaller files.` |
| Corrupted file | `Failed to parse document: File appears corrupted or is password-protected.` |

---

## Tool: `transcribe_audio`

**Description**: Transcribe audio and video files to text using OpenAI Whisper. Supports multiple audio/video formats with automatic format detection via ffmpeg. Configurable model size for speed/accuracy tradeoff. GPU acceleration when available. Requires Whisper Docker container.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "file_path": {
      "type": "string",
      "description": "Absolute path to the audio or video file to transcribe",
      "pattern": "^/.+\\.(mp3|wav|flac|m4a|mp4|mov|avi|mkv)$"
    },
    "model": {
      "type": "string",
      "description": "Whisper model size (larger = more accurate but slower)",
      "enum": ["tiny", "base", "small", "medium", "large"],
      "default": "small"
    },
    "language": {
      "type": "string",
      "description": "Audio language code (ISO 639-1) or 'auto' for automatic detection",
      "default": "auto",
      "pattern": "^(auto|[a-z]{2})$"
    },
    "output_file": {
      "type": "string",
      "description": "Optional absolute path to save markdown file (includes frontmatter)",
      "pattern": "^/.*\\.md$"
    }
  },
  "required": ["file_path"]
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "---\nsource: /Users/dylan/Videos/meeting.mp4\ntype: audio_transcript\nduration: 3600\nlanguage: en\nmodel: small\nword_count: 6543\nconverted_at: 2025-10-02T14:50:33Z\n---\n\n# Audio Transcript\n\nTranscribed content..."
  }],
  "metadata": {
    "file_path": "/Users/dylan/Videos/meeting.mp4",
    "duration": 3600,
    "language": "en",
    "model": "small",
    "word_count": 6543,
    "conversion_time_ms": 45234
  }
}
```

**Error Response**:
```json
{
  "isError": true,
  "content": [{
    "type": "text",
    "text": "Whisper service unavailable. The service may not be running. Start with: docker-compose up -d whisper"
  }]
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Service unavailable | `Whisper service unavailable. The service may not be running. Start with: docker-compose up -d whisper` |
| File not found | `File not found: /path/to/audio.mp3. Verify the path is correct and the file exists.` |
| Unsupported format | `Unsupported audio format: .ogg. Supported formats: MP3, WAV, FLAC, M4A, MP4, MOV, AVI, MKV (via ffmpeg).` |
| Transcription failure | `Transcription failed: Unable to detect speech in audio. The file may be corrupted, silent, or in an unsupported language.` |
| Out of memory | `Transcription failed: Out of memory. Try using a smaller model: 'tiny' or 'base'.` |
| Invalid audio | `Failed to process audio: File appears corrupted or uses unsupported codec.` |

---

## Progress Reporting

For long-running operations (large documents, videos), tools report progress via MCP progress API:

```json
{
  "progress": 0.45,
  "total": 1.0,
  "message": "Processing page 18 of 40..."
}
```

**Operations with progress reporting**:
- `convert_document`: Page-by-page for multi-page PDFs
- `transcribe_audio`: Chunk-by-chunk for long audio files

---

## Common Response Fields

### Metadata Object

All successful tool responses include a `metadata` object with conversion details:

```json
{
  "metadata": {
    "source": "string",           // Original URL or file path
    "type": "string",              // Conversion type
    "word_count": "number",        // Word count of output
    "conversion_time_ms": "number" // Time taken in milliseconds
  }
}
```

### Frontmatter Format

When `output_file` is not specified, markdown is returned with YAML frontmatter:

```yaml
---
source: <URL or path>
type: <youtube_transcript|webpage|document|audio_transcript>
word_count: <number>
converted_at: <ISO 8601 timestamp>
# Additional type-specific fields
---

# Markdown Content
```

---

## Service Health Checks

The MCP server performs health checks before calling containerized services:

```http
GET http://localhost:11235/health  # Crawl4AI
GET http://localhost:5001/health   # Docling
GET http://localhost:9000/health   # Whisper
```

If service is unavailable, tool returns error immediately without attempting conversion.

---

## Rate Limiting

**YouTube transcripts**: No rate limiting (uses official API)
**Web scraping**: Respects robots.txt and standard crawl delays
**Document/Audio**: No rate limiting (local processing)

---

## Input Validation

All inputs are validated against JSON schemas before processing:
- URL patterns validated via regex
- File paths checked for existence and readability
- Numeric parameters checked against min/max constraints
- Enum values validated against allowed options

Invalid inputs return immediate error responses without calling services.

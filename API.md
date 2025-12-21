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

**Description**: Transcribe audio and video files to text using faster-whisper with CoreML/Metal acceleration. Supports multiple audio/video formats with automatic format detection via ffmpeg. Configurable model size for speed/accuracy tradeoff. Runs locally on host (no Docker container required).

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
    "text": "Transcription failed: Unable to detect speech in audio. The file may be corrupted, silent, or in an unsupported language."
  }]
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| File not found | `File not found: /path/to/audio.mp3. Verify the path is correct and the file exists.` |
| Unsupported format | `Unsupported audio format: .ogg. Supported formats: MP3, WAV, FLAC, M4A, MP4, MOV, AVI, MKV (via ffmpeg).` |
| Transcription failure | `Transcription failed: Unable to detect speech in audio. The file may be corrupted, silent, or in an unsupported language.` |
| Out of memory | `Transcription failed: Out of memory. Try using a smaller model: 'tiny' or 'base'.` |
| Invalid audio | `Failed to process audio: File appears corrupted or uses unsupported codec.` |
| Model loading failure | `Failed to load Whisper model: Unable to download or initialize model. Check your internet connection and disk space.` |

---

## Tool: `fetch_webpage_with_selector`

**Description**: Extract specific content from webpage using CSS or XPath selectors. Extends basic webpage conversion with targeted content extraction. Supports session-based crawling for authenticated content. Requires Crawl4AI Docker container.

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
    "css_selector": {
      "type": "string",
      "description": "CSS selector to extract specific content (e.g., 'article.main', 'div.content')"
    },
    "xpath": {
      "type": "string",
      "description": "XPath expression to extract content (alternative to css_selector)"
    },
    "include_images": {
      "type": "boolean",
      "description": "Include image alt text and references in markdown output",
      "default": true
    },
    "extract_links": {
      "type": "boolean",
      "description": "Extract and categorize links as internal/external",
      "default": false
    },
    "session_id": {
      "type": "string",
      "description": "Session ID for authenticated crawling (loads saved cookies/localStorage)"
    },
    "bypass_cache": {
      "type": "boolean",
      "description": "Bypass Crawl4AI cache for fresh content",
      "default": false
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
      "description": "Optional absolute path to save markdown file",
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
    "text": "---\nsource: https://example.com/article\ntype: webpage\ntitle: Example Article\nword_count: 2341\nconverted_at: 2025-10-02T14:35:22Z\n---\n\n# Article Content\n\nExtracted content..."
  }],
  "metadata": {
    "url": "https://example.com/article",
    "title": "Example Article",
    "word_count": 2341,
    "all_links": [...],
    "internal_links": [...],
    "external_links": [...]
  }
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Both selectors | `Cannot use both css_selector and xpath. Choose one.` |
| Invalid selector | `CSS selector syntax error: unexpected token...` |
| Session not found | `Session 'my-session' not found. Create it with create_crawl_session first.` |
| No content matched | `Selector did not match any content on the page.` |

---

## Browser Tools

Browser automation tools for controlling and extracting content from browser tabs via the Gobbler browser extension. Requires the browser extension to be installed and connected.

---

## Tool: `browser_check_connection`

**Description**: Check if the Gobbler browser extension is connected and ready. Verifies that the extension is installed, running, and connected to the MCP server via WebSocket.

### Input Schema

```json
{
  "type": "object",
  "properties": {},
  "required": []
}
```

### Output

**Success Response (connected)**:
```json
{
  "content": [{
    "type": "text",
    "text": "Browser extension is connected and ready. (1 connection(s))"
  }]
}
```

**Success Response (no extension)**:
```json
{
  "content": [{
    "type": "text",
    "text": "Relay server is running but no browser extension connected.\n\nTo connect:\n1. Install the Gobbler browser extension in Chrome\n2. Add tabs to the Gobbler group via the extension popup\n3. The extension will auto-connect to the relay server"
  }]
}
```

---

## Tool: `browser_navigate_to_url`

**Description**: Navigate the browser extension's active tab to a URL. Sends a navigation command to load the specified URL in the currently active tab.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "url": {
      "type": "string",
      "description": "Full URL to navigate to (must include http:// or https://)"
    },
    "wait_for_load": {
      "type": "boolean",
      "description": "Wait for page to fully load before returning",
      "default": true
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
    "text": "Successfully navigated to: https://example.com"
  }]
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Invalid URL | `Error: URL must start with http:// or https://` |
| Navigation failed | `Failed to navigate: Connection timeout` |
| No extension | `Relay server is not running or no browser extension connected.` |

---

## Tool: `browser_execute_script`

**Description**: Execute JavaScript in the browser extension's active tab. Runs arbitrary JavaScript code in the context of the currently active tab and returns the result.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "script": {
      "type": "string",
      "description": "JavaScript code to execute (must be a complete expression or IIFE)"
    },
    "timeout": {
      "type": "integer",
      "description": "Maximum time to wait for script execution in seconds",
      "default": 30,
      "minimum": 1,
      "maximum": 150
    }
  },
  "required": ["script"]
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "Example Page Title"
  }]
}
```

### Examples

Get page title:
```javascript
document.title
```

Scroll page and wait:
```javascript
(async () => {
  window.scrollTo(0, document.body.scrollHeight);
  await new Promise(r => setTimeout(r, 1000));
  return {scrolled: true};
})()
```

Extract all headings:
```javascript
Array.from(document.querySelectorAll('h1')).map(h => h.textContent)
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Invalid timeout | `Error: timeout must be between 1 and 150 seconds` |
| Script error | `Script execution failed: ReferenceError: foo is not defined` |
| Timeout | `Script execution failed: Timeout after 30 seconds` |

---

## Tool: `browser_extract_current_page`

**Description**: Extract the current page's content as markdown. Extracts HTML content from the active tab and converts it to clean markdown format. Optionally uses a CSS selector to extract only a specific part of the page.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "selector": {
      "type": "string",
      "description": "Optional CSS selector to extract specific content (e.g., 'article.main', '.content')"
    }
  },
  "required": []
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "---\nsource: https://example.com/page\ntype: webpage\ntitle: Page Title\nword_count: 1234\nconverted_at: 2025-10-02T14:35:22Z\n---\n\n# Page Title\n\nPage content..."
  }]
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Selector not found | `Failed to extract page: Selector 'article.main' not found` |
| No active tab | `Failed to extract page: No active tab in Gobbler group` |

---

## Tool: `browser_list_tabs`

**Description**: List all tabs in the Gobbler tab group with their IDs, titles, and URLs. Returns a list of tabs that Claude can interact with. Only tabs in the Gobbler group are accessible for security.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "filter": {
      "type": "string",
      "description": "Optional filter - use 'notebooklm' to only show NotebookLM tabs"
    }
  },
  "required": []
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "Found 3 tab(s) in Gobbler group:\n\n  [123] Example Page (active)\n       https://example.com\n  [124] Another Page\n       https://example.org\n  [125] NotebookLM\n       https://notebooklm.google.com/notebook/abc123"
  }]
}
```

**Empty Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "No tabs in Gobbler group. Add tabs via extension popup or right-click menu."
  }]
}
```

---

## Tool: `browser_execute_script_in_tab`

**Description**: Execute JavaScript in a specific browser tab (must be in Gobbler group). Use `browser_list_tabs()` first to get available tab IDs. This allows targeting specific tabs instead of just the active tab.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "tab_id": {
      "type": "integer",
      "description": "The tab ID to execute the script in (from browser_list_tabs)"
    },
    "script": {
      "type": "string",
      "description": "JavaScript code to execute (must be a complete expression or IIFE)"
    },
    "timeout": {
      "type": "integer",
      "description": "Maximum time to wait for script execution in seconds",
      "default": 30,
      "minimum": 1,
      "maximum": 150
    }
  },
  "required": ["tab_id", "script"]
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "Script executed successfully in tab 123 (no return value)"
  }]
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Tab not found | `Script execution failed: Tab 999 not found in Gobbler group` |
| Tab not accessible | `Script execution failed: Cannot access tab (not in Gobbler group)` |

---

## Crawl Tools

Tools for crawling websites and managing browser sessions for authenticated content.

---

## Tool: `create_crawl_session`

**Description**: Create reusable browser session for authenticated crawling. Sessions persist cookies and localStorage to disk, allowing authenticated content access across multiple crawl operations.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "description": "Unique identifier for the session (alphanumeric, hyphens, underscores)"
    },
    "cookies": {
      "type": "string",
      "description": "JSON string containing list of cookie objects with name, value, domain, etc."
    },
    "local_storage": {
      "type": "string",
      "description": "JSON string containing localStorage key-value pairs"
    },
    "user_agent": {
      "type": "string",
      "description": "Custom user agent string to use with this session"
    }
  },
  "required": ["session_id"]
}
```

### Cookie Format

Each cookie in the `cookies` array should have:

| Field | Required | Description |
|-------|----------|-------------|
| name | Yes | Cookie name |
| value | Yes | Cookie value |
| domain | Yes | Cookie domain |
| path | No | Cookie path (default: "/") |
| secure | No | HTTPS only (default: false) |
| httpOnly | No | HTTP only flag (default: false) |
| sameSite | No | SameSite policy ("Strict", "Lax", "None") |

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "✅ Session 'my-site' created successfully\nStorage location: ~/.config/gobbler/sessions/my-site.json\nCookies: 3\nlocalStorage keys: user_id, theme\nCustom user agent: configured\n\nUse with session_id='my-site' in fetch_webpage_with_selector or crawl_site"
  }]
}
```

### Examples

Create session with cookies:
```json
{
  "session_id": "my-site",
  "cookies": "[{\"name\": \"session_token\", \"value\": \"abc123\", \"domain\": \"example.com\"}]"
}
```

Create session with localStorage:
```json
{
  "session_id": "my-app",
  "local_storage": "{\"user_id\": \"12345\", \"theme\": \"dark\"}"
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Invalid session_id | `Error: session_id must contain only alphanumeric characters, hyphens, and underscores` |
| Invalid cookies JSON | `Error: Invalid cookies JSON: Expecting property name...` |
| Invalid cookies type | `Error: cookies must be a JSON array of cookie objects` |

---

## Tool: `crawl_site`

**Description**: Recursively crawl website and extract content with link graph generation. Performs breadth-first crawl, extracting content from each page and building a link graph showing relationships between pages.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "start_url": {
      "type": "string",
      "description": "URL to start crawling from"
    },
    "max_depth": {
      "type": "integer",
      "description": "Maximum crawl depth",
      "default": 2,
      "minimum": 1,
      "maximum": 5
    },
    "max_pages": {
      "type": "integer",
      "description": "Maximum pages to crawl",
      "default": 50,
      "minimum": 1,
      "maximum": 500
    },
    "url_include_pattern": {
      "type": "string",
      "description": "Regex pattern - only crawl URLs matching this"
    },
    "url_exclude_pattern": {
      "type": "string",
      "description": "Regex pattern - skip URLs matching this"
    },
    "css_selector": {
      "type": "string",
      "description": "Apply CSS selector to extract specific content from all pages"
    },
    "respect_robots_txt": {
      "type": "boolean",
      "description": "Respect robots.txt rules",
      "default": true
    },
    "crawl_delay": {
      "type": "number",
      "description": "Delay between requests in seconds (polite crawling)",
      "default": 1.0
    },
    "concurrency": {
      "type": "integer",
      "description": "Max concurrent requests",
      "default": 3,
      "minimum": 1,
      "maximum": 10
    },
    "session_id": {
      "type": "string",
      "description": "Session ID for authenticated crawling"
    },
    "output_dir": {
      "type": "string",
      "description": "Optional directory to save all crawled pages as markdown files"
    }
  },
  "required": ["start_url"]
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "✅ Crawl complete: 25 pages crawled\nDuration: 45234ms\nMax depth reached: 2\nDomains: docs.example.com\n\n**Link Graph Summary:**\nTotal nodes: 25\nTotal edges: 87\n\n**Most linked pages:**\n- https://docs.example.com/getting-started (12 incoming links)\n- https://docs.example.com/api (8 incoming links)\n- https://docs.example.com/faq (6 incoming links)\n\n📁 Pages saved to: /Users/me/crawled-docs"
  }]
}
```

### Examples

Basic documentation site crawl:
```json
{
  "start_url": "https://docs.example.com",
  "max_depth": 2,
  "max_pages": 20
}
```

Crawl with URL filtering:
```json
{
  "start_url": "https://blog.example.com",
  "url_include_pattern": "/posts/",
  "url_exclude_pattern": "/(tag|category)/",
  "max_pages": 100
}
```

Authenticated crawl with selector:
```json
{
  "start_url": "https://app.example.com",
  "css_selector": "article.content",
  "session_id": "my-session",
  "max_depth": 3
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Invalid regex | `Error: Invalid url_include_pattern regex: unterminated group` |
| Robots.txt blocked | `Crawl blocked by robots.txt rules` |
| Session not found | `Session 'my-session' not found` |

---

## Tool: `download_youtube_video`

**Description**: Download YouTube video to local file. Downloads video using yt-dlp with configurable quality and format. Automatically sanitizes filenames and creates output directory if needed.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "video_url": {
      "type": "string",
      "description": "YouTube video URL (youtube.com/watch?v=ID or youtu.be/ID format)"
    },
    "output_dir": {
      "type": "string",
      "description": "Directory to save the downloaded video (must be absolute path)"
    },
    "quality": {
      "type": "string",
      "description": "Video quality",
      "enum": ["best", "1080p", "720p", "480p", "360p"],
      "default": "best"
    },
    "format": {
      "type": "string",
      "description": "Output format",
      "enum": ["mp4", "webm", "mkv"],
      "default": "mp4"
    },
    "auto_queue": {
      "type": "boolean",
      "description": "Automatically queue task if estimated duration > 1:45",
      "default": false
    }
  },
  "required": ["video_url", "output_dir"]
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "Video downloaded successfully to: /Users/dylan/Videos/Example_Video.mp4\nFile size: 245.3 MB"
  }]
}
```

**Queued Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "Task queued successfully!\n\nJob ID: abc123-def456\nQueue: download\nEstimated completion: ~5 minutes\n\nCheck status with: get_job_status(job_id=\"abc123-def456\")"
  }]
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Invalid path | `Error: output_dir must be an absolute path. Got: ./videos` |
| Video unavailable | `Failed to download video: Video unavailable` |
| Quality not available | `Requested quality not available, falling back to best` |

---

## Queue Tools

Tools for managing background job queues for long-running operations.

---

## Tool: `get_job_status`

**Description**: Check status and result of a queued job. Retrieves current status, progress, and result (if completed) for a job that was queued via the `auto_queue` flag.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "job_id": {
      "type": "string",
      "description": "Job ID returned when task was queued"
    }
  },
  "required": ["job_id"]
}
```

### Output

**Queued Status**:
```json
{
  "content": [{
    "type": "text",
    "text": "Job ID: abc123-def456\nStatus: queued\nQueue position: 3\nWaiting to start..."
  }]
}
```

**Running Status**:
```json
{
  "content": [{
    "type": "text",
    "text": "Job ID: abc123-def456\nStatus: started\nJob is currently running...\nProgress: Processing file 5 of 10"
  }]
}
```

**Finished Status**:
```json
{
  "content": [{
    "type": "text",
    "text": "Job ID: abc123-def456\nStatus: finished\n✅ Job completed successfully\n\nResult:\nBatch complete: 10 files processed\n- Success: 9\n- Failed: 1"
  }]
}
```

**Failed Status**:
```json
{
  "content": [{
    "type": "text",
    "text": "Job ID: abc123-def456\nStatus: failed\n❌ Job failed\nError: Connection timeout after 120 seconds"
  }]
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Job not found | `Job not found: abc123-def456` |

---

## Tool: `list_jobs`

**Description**: List jobs in a queue. Shows recent jobs in the specified queue with their current status. Useful for monitoring background tasks.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "queue_name": {
      "type": "string",
      "description": "Queue to list jobs from",
      "enum": ["default", "transcription", "download"],
      "default": "default"
    },
    "limit": {
      "type": "integer",
      "description": "Maximum number of jobs to return",
      "default": 20,
      "minimum": 1,
      "maximum": 100
    }
  },
  "required": []
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "Jobs in queue 'default' (showing up to 20):\n\n⏳ QUEUED: job-001\n   Created: 2025-10-02T14:30:00Z\n   Position: 1\n\n🔄 STARTED: job-002\n   Created: 2025-10-02T14:25:00Z\n\n✅ FINISHED: job-003\n   Created: 2025-10-02T14:20:00Z\n\n❌ FAILED: job-004\n   Created: 2025-10-02T14:15:00Z"
  }]
}
```

**Empty Queue**:
```json
{
  "content": [{
    "type": "text",
    "text": "No jobs found in queue 'default'"
  }]
}
```

---

## Tool: `get_batch_progress`

**Description**: Get real-time progress for a running batch operation. Provides detailed progress information including current item, success/failure counts, and any errors encountered.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "batch_id": {
      "type": "string",
      "description": "Batch operation ID returned when batch was started"
    }
  },
  "required": ["batch_id"]
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "Batch Progress: batch-abc123\n\nStatus: running\nProgress: 15 / 25 items (60%)\n\nSuccess: 14\nFailed: 1\n\nCurrent item: Processing video_15.mp4\n\nRecent errors:\n- video_08.mp4: Transcription failed - corrupted audio"
  }]
}
```

### Error Scenarios

| Error | Message |
|-------|---------|
| Batch not found | `Batch not found: batch-abc123\n\nBatch may have expired (24 hour retention) or ID is incorrect.` |

---

## Batch Processing Tools

Tools for processing multiple files or URLs in batches with progress tracking and optional background queuing.

---

## Tool: `batch_transcribe_youtube_playlist`

**Description**: Extract transcripts from all videos in a YouTube playlist with rate limiting. Uses delays, jitter, and exponential backoff to avoid triggering YouTube's anti-bot measures.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "playlist_url": {
      "type": "string",
      "description": "YouTube playlist URL (youtube.com/playlist?list=...)"
    },
    "output_dir": {
      "type": "string",
      "description": "Directory to save markdown transcripts (must be absolute path)"
    },
    "include_timestamps": {
      "type": "boolean",
      "description": "Include timestamp markers in transcripts",
      "default": false
    },
    "language": {
      "type": "string",
      "description": "Transcript language code or 'auto'",
      "default": "auto"
    },
    "max_videos": {
      "type": "integer",
      "description": "Maximum number of videos to process",
      "default": 100,
      "maximum": 500
    },
    "concurrency": {
      "type": "integer",
      "description": "Number of videos to process concurrently (lower is safer)",
      "default": 2,
      "maximum": 10
    },
    "skip_existing": {
      "type": "boolean",
      "description": "Skip videos that already have output files",
      "default": true
    },
    "auto_queue": {
      "type": "boolean",
      "description": "Queue batch if >10 videos",
      "default": false
    },
    "delay_between_requests": {
      "type": "number",
      "description": "Fixed delay in seconds between requests",
      "default": 1.5
    },
    "jitter_range": {
      "type": "number",
      "description": "Random 0-N second jitter added to delay",
      "default": 1.0
    },
    "max_retries": {
      "type": "integer",
      "description": "Maximum retry attempts with exponential backoff",
      "default": 3
    }
  },
  "required": ["playlist_url", "output_dir"]
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "Batch complete: 25 videos processed\n\n- Success: 23\n- Skipped: 1 (existing)\n- Failed: 1\n\nDuration: 5m 32s\n\nFiles saved:\n- /path/to/Video_Title_1.md\n- /path/to/Video_Title_2.md\n..."
  }]
}
```

---

## Tool: `batch_fetch_webpages`

**Description**: Convert multiple web pages to markdown format. Processes URLs with controlled concurrency to avoid overwhelming target servers.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "urls": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of web page URLs to convert (max: 100)"
    },
    "output_dir": {
      "type": "string",
      "description": "Directory to save markdown files (must be absolute path)"
    },
    "include_images": {
      "type": "boolean",
      "description": "Include image references in markdown",
      "default": true
    },
    "timeout": {
      "type": "integer",
      "description": "Request timeout per page in seconds",
      "default": 30,
      "maximum": 120
    },
    "concurrency": {
      "type": "integer",
      "description": "Number of pages to process concurrently",
      "default": 5,
      "maximum": 10
    },
    "skip_existing": {
      "type": "boolean",
      "description": "Skip URLs that already have output files",
      "default": true
    },
    "auto_queue": {
      "type": "boolean",
      "description": "Queue batch if >10 URLs",
      "default": false
    }
  },
  "required": ["urls", "output_dir"]
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "Batch complete: 15 pages processed\n\n- Success: 14\n- Skipped: 0\n- Failed: 1\n\nDuration: 45s\n\nFiles saved:\n- /path/to/page_1.md\n- /path/to/page_2.md\n..."
  }]
}
```

---

## Tool: `batch_transcribe_directory`

**Description**: Transcribe all audio/video files in a directory. Automatically detects supported formats (mp3, mp4, wav, m4a, mov, avi, mkv, flac, ogg, webm) and processes with Whisper.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "input_dir": {
      "type": "string",
      "description": "Directory containing audio/video files (must be absolute path)"
    },
    "output_dir": {
      "type": "string",
      "description": "Directory for transcripts (default: same as input_dir)"
    },
    "model": {
      "type": "string",
      "description": "Whisper model size",
      "enum": ["tiny", "base", "small", "medium", "large"],
      "default": "small"
    },
    "language": {
      "type": "string",
      "description": "Audio language code or 'auto'",
      "default": "auto"
    },
    "pattern": {
      "type": "string",
      "description": "Glob pattern for file matching",
      "default": "*"
    },
    "recursive": {
      "type": "boolean",
      "description": "Search subdirectories",
      "default": false
    },
    "concurrency": {
      "type": "integer",
      "description": "Number of files to process concurrently",
      "default": 2,
      "maximum": 4
    },
    "skip_existing": {
      "type": "boolean",
      "description": "Skip files with existing transcript files",
      "default": true
    },
    "auto_queue": {
      "type": "boolean",
      "description": "Queue batch if >10 files or >500MB total",
      "default": true
    }
  },
  "required": ["input_dir"]
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "Batch complete: 8 files processed\n\n- Success: 7\n- Skipped: 0\n- Failed: 1\n\nDuration: 12m 45s\n\nFiles saved:\n- /path/to/meeting_1.md\n- /path/to/interview_2.md\n..."
  }]
}
```

---

## Tool: `batch_convert_documents`

**Description**: Convert all documents in a directory to markdown. Supports PDF, DOCX, PPTX, XLSX with optional OCR for scanned documents.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "input_dir": {
      "type": "string",
      "description": "Directory containing documents (must be absolute path)"
    },
    "output_dir": {
      "type": "string",
      "description": "Directory for markdown files (default: same as input_dir)"
    },
    "enable_ocr": {
      "type": "boolean",
      "description": "Enable OCR for scanned documents",
      "default": true
    },
    "pattern": {
      "type": "string",
      "description": "Glob pattern for file matching",
      "default": "*"
    },
    "recursive": {
      "type": "boolean",
      "description": "Search subdirectories",
      "default": false
    },
    "concurrency": {
      "type": "integer",
      "description": "Number of documents to process concurrently",
      "default": 3,
      "maximum": 5
    },
    "skip_existing": {
      "type": "boolean",
      "description": "Skip documents with existing markdown files",
      "default": true
    },
    "auto_queue": {
      "type": "boolean",
      "description": "Queue batch if >10 documents",
      "default": false
    }
  },
  "required": ["input_dir"]
}
```

### Output

**Success Response**:
```json
{
  "content": [{
    "type": "text",
    "text": "Batch complete: 12 documents processed\n\n- Success: 11\n- Skipped: 0\n- Failed: 1\n\nDuration: 3m 22s\n\nFiles saved:\n- /path/to/report.md\n- /path/to/presentation.md\n..."
  }]
}
```

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
```

If a containerized service is unavailable, the tool returns an error immediately without attempting conversion.

**Note**: Audio transcription (`transcribe_audio`) runs locally and does not require health checks.

---

## Rate Limiting

**YouTube transcripts**: No rate limiting (uses official API)
**Web scraping**: Respects robots.txt and standard crawl delays
**Document conversion**: No rate limiting (containerized processing)
**Audio transcription**: No rate limiting (local processing)

---

## Input Validation

All inputs are validated against JSON schemas before processing:
- URL patterns validated via regex
- File paths checked for existence and readability
- Numeric parameters checked against min/max constraints
- Enum values validated against allowed options

Invalid inputs return immediate error responses without calling services.

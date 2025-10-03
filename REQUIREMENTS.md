# Gobbler MCP Server - Technical Requirements

## Functional Requirements

### FR1: YouTube Transcript Conversion
**Priority**: P0 (Must Have)

**Description**: Convert YouTube videos to markdown transcripts

**Acceptance Criteria**:
- Accept YouTube URLs in any format (youtube.com, youtu.be, with/without timestamps)
- Extract official transcripts using `youtube-transcript-api`
- Support multiple languages (auto-detect or user-specified)
- Optional timestamp inclusion
- Return clean markdown or save to file with frontmatter
- Works without Docker containers (built-in functionality)

**Error Handling**:
- Video not found → Clear error with URL validation
- No transcript available → Explain why and suggest alternatives
- Private/age-restricted videos → Actionable error message

**Example Output**:
```markdown
---
source: https://youtube.com/watch?v=dQw4w9WgXcQ
type: youtube_transcript
duration: 213
language: en
word_count: 1547
converted_at: 2025-10-02T14:32:11Z
---

# Video Transcript

Never gonna give you up, never gonna let you down...
```

---

### FR2: Web Page Conversion
**Priority**: P0 (Must Have)

**Description**: Convert web pages to clean markdown using Crawl4AI

**Acceptance Criteria**:
- Accept HTTP/HTTPS URLs
- Handle JavaScript-rendered content (browser automation)
- Preserve document structure (headings, links, code blocks)
- Remove navigation, footers, ads (content extraction)
- Configurable timeout (default 30s, max 120s)
- Optional image inclusion (alt text)
- Return markdown or save to file with frontmatter
- Gracefully fail if Crawl4AI container unavailable

**Error Handling**:
- Container not running → Instructions to start service
- Timeout → Suggest increasing timeout parameter
- Invalid URL → Validation error with pattern requirements
- Network errors → Distinguish transient vs permanent failures

**Example Output**:
```markdown
---
source: https://example.com/article
type: webpage
word_count: 2341
converted_at: 2025-10-02T14:35:22Z
---

# Article Title

Article content with preserved formatting...
```

---

### FR3: Document Conversion
**Priority**: P1 (Should Have)

**Description**: Convert documents (PDF, DOCX, PPTX, XLSX) to markdown using Docling

**Acceptance Criteria**:
- Accept absolute file paths
- Support formats: PDF, DOCX, PPTX, XLSX
- OCR support for scanned PDFs
- Preserve tables, headings, lists
- Remove page numbers, headers, footers
- Handle large documents (100+ pages)
- Return markdown or save to file with frontmatter
- Gracefully fail if Docling container unavailable

**Error Handling**:
- Container not running → Instructions to start service
- File not found → Clear path validation error
- Unsupported format → List supported formats
- OCR failure → Explain issue and suggest alternatives
- Out of memory → Suggest splitting document

**Example Output**:
```markdown
---
source: /Users/dylan/Documents/report.pdf
type: document
format: pdf
pages: 42
word_count: 8234
converted_at: 2025-10-02T14:40:11Z
---

# Report Title

Content from PDF with preserved structure...
```

---

### FR4: Audio/Video Transcription
**Priority**: P1 (Should Have)

**Description**: Transcribe audio and video files using Whisper

**Acceptance Criteria**:
- Accept absolute file paths
- Support formats: MP3, WAV, FLAC, MP4, MOV, etc.
- Configurable model size (tiny, base, small, medium, large)
- Language detection or user-specified
- GPU acceleration when available, CPU fallback
- Handle long files (chunk processing)
- Return transcript or save to file with frontmatter
- Gracefully fail if Whisper container unavailable

**Error Handling**:
- Container not running → Instructions to start service
- File not found → Clear path validation error
- Unsupported format → List supported formats with ffmpeg
- Transcription failure → Explain issue (audio quality, language)
- Out of memory → Suggest smaller model or chunking

**Example Output**:
```markdown
---
source: /Users/dylan/Videos/meeting.mp4
type: audio_transcript
duration: 3600
language: en
model: small
word_count: 6543
converted_at: 2025-10-02T14:50:33Z
---

# Audio Transcript

Transcribed content from video...
```

---

## Non-Functional Requirements

### NFR1: Performance
- YouTube transcripts: < 5 seconds
- Web page conversion: < 30 seconds (default timeout)
- Document conversion: < 10 seconds per MB
- Audio transcription: Real-time factor < 0.5 (1hr audio in 30min)
- Support concurrent conversions (5+ simultaneous)

### NFR2: Reliability
- Graceful degradation when services unavailable
- Automatic retry for transient network errors (3 attempts)
- Proper resource cleanup (no memory leaks)
- Services auto-restart on failure

### NFR3: Security
- Container isolation for untrusted code execution
- No arbitrary code execution in host process
- File access limited to user permissions
- Input validation (URL patterns, file paths)
- Resource limits (memory, CPU) to prevent DoS

### NFR4: Usability
- Single command installation: `uv tool install gobbler-mcp`
- Simple service startup: `docker-compose up -d`
- Clear error messages with actionable fixes
- Self-documenting tools (comprehensive descriptions)
- Example configurations provided

### NFR5: Maintainability
- Modular converter implementations (separate files)
- Comprehensive type hints (Python 3.10+)
- Automated testing (unit, integration, behavioral)
- Clear logging (structured, stderr only)
- Version pinning for dependencies

---

## Technical Constraints

### TC1: MCP Protocol Compliance
- JSON-RPC 2.0 over stdio transport
- FastMCP framework (official Python SDK)
- Tool schemas with explicit JSON validation
- Error responses with `isError` flag
- Progress reporting for long operations

### TC2: Docker Requirements
- Docker Compose v2+
- Pre-built images from official sources
- Volume mounts for model caching
- Resource limits configured
- Health checks for service availability

### TC3: Python Requirements
- Python 3.10 or higher
- Type hints required (mypy validation)
- Async/await for I/O operations
- No `print()` statements (stdio transport)
- Logging to stderr only

### TC4: Dependency Constraints
- Use `uv` package manager (not pip)
- Pin major versions in `pyproject.toml`
- Minimal dependencies for MCP server
- Heavy dependencies isolated in containers

---

## Configuration Requirements

### CR1: User Configuration File
**Location**: `~/.config/gobbler/config.yml`

**Schema**:
```yaml
whisper:
  model: small  # tiny, base, small, medium, large
  language: auto  # auto or ISO 639-1 code

docling:
  ocr: true  # Enable OCR for scanned documents
  vlm: false  # Visual Language Model (expensive)

crawl4ai:
  timeout: 30  # Default request timeout in seconds

output:
  default_format: frontmatter  # frontmatter or plain
  timestamp_format: iso8601
```

### CR2: Model Cache Locations
**Whisper**: `~/.gobbler/models/whisper`
**Docling**: `~/.gobbler/models/docling`

User-controlled locations, volume-mounted to containers

### CR3: Service Configuration
**Docker Compose**: `~/.gobbler/docker-compose.yml`

Generated on first run with sensible defaults, user-editable

---

## Output Format Requirements

### OR1: Markdown with Frontmatter
**Format**: YAML frontmatter + markdown body

**Common Fields**:
- `source`: Original URL or file path
- `type`: Conversion type (youtube_transcript, webpage, document, audio_transcript)
- `word_count`: Word count of content
- `converted_at`: ISO 8601 timestamp

**Type-Specific Fields**:
- YouTube: `duration`, `language`, `video_id`
- Webpage: `title`, `url`
- Document: `format`, `pages`
- Audio: `duration`, `language`, `model`

**Separator**: `---` (standard YAML frontmatter)

### OR2: Markdown Formatting Standards
- Normalize heading levels (start with H1)
- Preserve code blocks with language tags
- Clean bullet points and numbered lists
- Strip excessive whitespace (max 2 consecutive newlines)
- Preserve links in markdown format `[text](url)`
- Image alt text: `![alt text](url)` or stripped if `include_images=false`

---

## Testing Requirements

### TR1: MCP Inspector Validation
- All tools discoverable
- Schemas validate correctly
- Tool invocations succeed
- Error responses properly formatted

### TR2: Unit Tests
- Each converter module tested independently
- Mock external services (HTTP, libraries)
- Edge cases covered (empty content, huge files)
- Error conditions tested

### TR3: Integration Tests
- Real service interactions (mark with `@pytest.mark.integration`)
- Actual file conversions with known samples
- Network requests to real URLs
- End-to-end MCP protocol flows

### TR4: Behavioral Tests
- LLM tool selection accuracy
- Parameter passing correctness
- Multi-step conversion workflows
- Error recovery strategies

---

## Deployment Requirements

### DR1: Distribution Channels
- PyPI package: `gobbler-mcp`
- Docker Hub: `username/gobbler-mcp`
- GitHub releases with changelog
- Docker MCP Catalog submission

### DR2: Documentation
- README with quick start
- ARCHITECTURE.md (this document)
- REQUIREMENTS.md (this document)
- API.md with tool schemas
- Example configurations for popular MCP clients

### DR3: Version Management
- Semantic versioning (MAJOR.MINOR.PATCH)
- Changelog in CHANGELOG.md
- Git tags for releases
- Docker image tags matching versions

---

## Success Metrics

### User Success
- Installation completion rate > 90%
- First conversion success rate > 95%
- Error resolution without support > 80%

### Technical Success
- Tool selection accuracy > 95% (LLM chooses correct tool)
- Conversion success rate > 98% (for valid inputs)
- Service uptime > 99.5% (containers running)
- Average conversion time < targets in NFR1

### Community Success
- GitHub stars > 100 (first month)
- Docker pulls > 1000 (first month)
- MCP Catalog approval
- Positive feedback from users

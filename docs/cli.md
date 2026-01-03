# CLI Usage

Gobbler provides a powerful command-line interface for content conversion.

## Provider Management

Manage and inspect available content providers.

### List Providers

```bash
# List all providers
gobbler providers list

# Filter by category
gobbler providers list --category transcription
gobbler providers list -c document
gobbler providers list -c webpage

# JSON output
gobbler providers list --format json
```

### Get Provider Info

```bash
# Get detailed information about a provider
gobbler providers info transcription whisper-local
gobbler providers info document docling
gobbler providers info webpage crawl4ai

# JSON output
gobbler providers info transcription whisper-local --format json
```

### Provider Commands Reference

| Command | Description |
|---------|-------------|
| `gobbler providers list` | List all available providers |
| `gobbler providers list -c <category>` | List providers for a category |
| `gobbler providers info <category> <name>` | Show provider details |

## Basic Commands

### YouTube Transcription

```bash
# Basic transcript
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID"

# With timestamps
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --timestamps

# Save to file
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md

# Specific language
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --language es
```

### Audio/Video Transcription

```bash
# Basic transcription
gobbler audio meeting.mp3

# Specify model size (tiny, base, small, medium, large)
gobbler audio meeting.mp3 --model small

# Save to file
gobbler audio interview.mp4 -o interview.md

# Specify language
gobbler audio podcast.mp3 --language en

# Use specific provider (default: whisper-local)
gobbler audio meeting.mp3 --provider whisper-local
```

| Option | Description | Default |
|--------|-------------|---------|
| `--model` | Whisper model size | `small` |
| `--language` | Audio language (ISO 639-1) | auto-detect |
| `--provider` | Transcription provider | `whisper-local` |
| `-o, --output` | Output file path | stdout |

### Document Conversion

```bash
# PDF conversion
gobbler document report.pdf -o report.md

# Without OCR (faster for digital PDFs)
gobbler document report.pdf --no-ocr -o report.md

# PowerPoint
gobbler document presentation.pptx -o slides.md

# Word document
gobbler document paper.docx -o paper.md

# Excel spreadsheet
gobbler document data.xlsx -o data.md

# Use specific provider (default: docling)
gobbler document report.pdf --provider docling
```

| Option | Description | Default |
|--------|-------------|---------|
| `--ocr/--no-ocr` | Enable/disable OCR | enabled |
| `--provider` | Document provider | `docling` |
| `-o, --output` | Output file path | stdout |

### Web Page Conversion

```bash
# Basic fetch
gobbler webpage "https://example.com/article"

# Save to file
gobbler webpage "https://docs.python.org" -o python-docs.md

# With timeout
gobbler webpage "https://slow-site.com" --timeout 60

# Use specific provider (default: crawl4ai)
gobbler webpage "https://example.com" --provider crawl4ai
```

| Option | Description | Default |
|--------|-------------|---------|
| `--selector` | CSS selector for content extraction | full page |
| `--timeout` | Request timeout in seconds | 30 |
| `--provider` | Webpage provider | `crawl4ai` |
| `-o, --output` | Output file path | stdout |

## Batch Processing

### YouTube Playlists

```bash
# Process entire playlist
gobbler batch youtube-playlist "https://youtube.com/playlist?list=PLxxx" \
    --output-dir ./transcripts

# Limit number of videos
gobbler batch youtube-playlist "URL" --max-videos 10 -o ./transcripts
```

### Directory Processing

```bash
# Transcribe all audio files in directory
gobbler batch directory ./recordings --pattern "*.mp3" -o ./transcripts

# Convert all documents
gobbler batch directory ./documents --pattern "*.pdf" -o ./markdown

# Recursive search
gobbler batch directory ./files --recursive -o ./output
```

### Multiple URLs

```bash
# Process URLs from file
gobbler batch webpages urls.txt --output-dir ./pages

# Process URLs directly
gobbler batch webpages \
    "https://example.com/page1" \
    "https://example.com/page2" \
    -o ./pages
```

## Browser Automation

Requires the Gobbler browser extension.

```bash
# Extract current page
gobbler browser extract

# Navigate and extract
gobbler browser navigate "https://example.com"
gobbler browser extract

# Query NotebookLM
gobbler notebooklm query "What are the main themes?"

# Query ChatGPT
gobbler chatgpt query "Summarize this document"

# Query Claude.ai
gobbler claude query "Explain the architecture"
```

## Output Format

All conversions produce markdown with YAML frontmatter:

```markdown
---
source: https://youtube.com/watch?v=VIDEO_ID
type: youtube_transcript
title: "Video Title"
duration: 847
word_count: 2341
converted_at: 2026-01-03T10:30:00Z
---

# Video Title

Content here...
```

## Common Options

| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Output file path |
| `--quiet` | `-q` | Suppress progress output |
| `--verbose` | `-v` | Show detailed output |
| `--help` | `-h` | Show help message |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOBBLER_CONFIG` | Config file path | `~/.config/gobbler/config.yaml` |
| `TRANSCRIPTAPI_KEY` | TranscriptAPI.com API key | None |
| `GOBBLER_LOG_LEVEL` | Logging level | `INFO` |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Service unavailable |
| 4 | File not found |
| 5 | Network error |

## Examples

### Research Workflow

```bash
# Download and transcribe a conference talk
gobbler youtube "https://youtube.com/watch?v=..." -o talk.md

# Convert supporting papers
gobbler document paper1.pdf -o paper1.md
gobbler document paper2.pdf -o paper2.md

# Fetch related documentation
gobbler webpage "https://docs.example.com" -o docs.md
```

### Meeting Processing

```bash
# Transcribe team meetings
gobbler batch directory ./meetings --pattern "*.mp4" -o ./transcripts

# Check progress
gobbler batch status
```

### Documentation Archival

```bash
# Archive entire documentation site
gobbler batch webpages \
    "https://docs.example.com/intro" \
    "https://docs.example.com/api" \
    "https://docs.example.com/guides" \
    -o ./archive
```

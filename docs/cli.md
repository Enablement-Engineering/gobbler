---
icon: material/console
---

# CLI Usage

Gobbler provides a powerful command-line interface for content conversion.

## Provider Management

Gobbler uses a pluggable provider system for content conversion. Each category (transcription, document, webpage) can have multiple provider implementations.

### Available Providers

| Category | Provider | Description |
|----------|----------|-------------|
| transcription | `whisper-local` | Local faster-whisper (default, no API key required) |
| transcription | `openai-whisper` | OpenAI Whisper API (requires `OPENAI_API_KEY`) |
| document | `docling` | Docling Docker service (default) |
| webpage | `crawl4ai` | Crawl4AI Docker service (default) |

### List Providers

```bash
# List all providers
gobbler providers list

# Filter by category
gobbler providers list --category transcription
gobbler providers list -c document
gobbler providers list -c webpage

# JSON output for scripting
gobbler providers list --format json
```

### Get Provider Info

```bash
# Get detailed information about a provider
gobbler providers info transcription whisper-local
gobbler providers info transcription openai-whisper
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

## Service Health & Diagnostics

### JSON stdout contract

For CLI-capable AI agents and scripts, JSON modes write machine-readable payloads to stdout without human progress text. Single-command JSON modes such as `gobbler doctor --json`, `gobbler status --json`, and conversion commands with `--format json` emit one JSON object. Batch commands with `--json` emit newline-delimited JSON event objects.

### Doctor JSON for agents

Use `gobbler doctor --json` when an agent or script needs one local diagnostic payload that answers whether Gobbler can be used and what to do next. The command reports the Gobbler version, Python runtime, ffmpeg and Docker availability, redacted configuration, conversion service status, and `next_actions`.

```bash
gobbler doctor --json
```

The top-level `status` is one of:

- `ready`: all checked conversion paths are ready.
- `degraded`: at least one optional conversion path needs setup, but Gobbler can still be useful for available paths.
- `error`: no core conversion path is usable.

### Check Service Status

Before running conversions, check that all services are healthy:

```bash
# Check all services
gobbler status

# JSON output for scripting/AI agents
gobbler status --json

# Verbose output with error details
gobbler status -v
```

Example output:
```
Gobbler Status
══════════════════════════════════════════════════
● Overall: ready

  ✓ Youtube      ready (youtube-transcript-api)
  ✓ Audio        ready (whisper-local, model: small)
  ✓ Document     ready (docling, @ http://localhost:5001)
  ✓ Webpage      ready (crawl4ai, @ http://localhost:11235)

Config: ~/.config/gobbler/config.yml
Proxy:  webshare (rotating)
```

### Diagnose Errors

Get solutions for common errors:

```bash
# Diagnose an error message
gobbler explain "connection refused port 5001"

# List all known error patterns
gobbler explain --list

# JSON output
gobbler explain --json "youtube rate limit"
```

Example output:
```
#1 Docling service not running

Issue: The Docling Docker container is not running.

Fix:
  docker compose up -d docling

Verify:
  curl http://localhost:5001/health
```

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

# Skip if output already exists (idempotent)
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md --skip-if-exists

# Read URL from stdin (for piping)
echo "https://youtube.com/watch?v=VIDEO_ID" | gobbler youtube
```

### Audio/Video Transcription

```bash
# Basic transcription (uses whisper-local by default)
gobbler audio meeting.mp3

# Specify model size (tiny, base, small, medium, large)
gobbler audio meeting.mp3 --model small

# Save to file
gobbler audio interview.mp4 -o interview.md

# Specify language (skip auto-detection)
gobbler audio podcast.mp3 --language en

# Use OpenAI Whisper API (requires OPENAI_API_KEY)
gobbler audio meeting.mp3 --provider openai-whisper

# Use local Whisper explicitly
gobbler audio meeting.mp3 --provider whisper-local --model medium

# Skip if output already exists
gobbler audio meeting.mp3 -o meeting.md --skip-if-exists
```

| Option | Description | Default |
|--------|-------------|---------|
| `--model`, `-m` | Whisper model size | `small` |
| `--language`, `-l` | Audio language (ISO 639-1) | auto-detect |
| `--provider`, `-p` | Transcription provider | `whisper-local` |
| `--skip-if-exists` | Skip if output file exists | false |
| `-o, --output` | Output file path | stdout |

**Provider Notes:**

- `whisper-local`: Runs locally using faster-whisper, no API key needed
- `openai-whisper`: Uses OpenAI's Whisper API, requires `OPENAI_API_KEY` environment variable

### Document Conversion

```bash
# PDF conversion (uses docling by default)
gobbler document report.pdf -o report.md

# Without OCR (faster for digital PDFs)
gobbler document report.pdf --no-ocr -o report.md

# PowerPoint
gobbler document presentation.pptx -o slides.md

# Word document
gobbler document paper.docx -o paper.md

# Excel spreadsheet
gobbler document data.xlsx -o data.md

# Explicitly specify provider
gobbler document report.pdf --provider docling -o report.md

# Skip if output already exists
gobbler document report.pdf -o report.md --skip-if-exists
```

| Option | Description | Default |
|--------|-------------|---------|
| `--ocr/--no-ocr` | Enable/disable OCR | enabled |
| `--provider`, `-p` | Document provider | `docling` |
| `--skip-if-exists` | Skip if output file exists | false |
| `-o, --output` | Output file path | stdout |

**Provider Notes:**

- `docling`: Requires the Docling Docker service running locally

### Web Page Conversion

```bash
# Basic fetch (uses crawl4ai by default)
gobbler webpage "https://example.com/article"

# Save to file
gobbler webpage "https://docs.python.org" -o python-docs.md

# With timeout for slow sites
gobbler webpage "https://slow-site.com" --timeout 60

# Explicitly specify provider
gobbler webpage "https://example.com" --provider crawl4ai -o page.md

# Skip if output already exists
gobbler webpage "https://example.com" -o page.md --skip-if-exists

# Read URL from stdin (for piping)
echo "https://example.com" | gobbler webpage -o page.md
```

| Option | Description | Default |
|--------|-------------|---------|
| `--selector`, `-s` | CSS selector for content extraction | full page |
| `--timeout`, `-t` | Request timeout in seconds | 30 |
| `--provider`, `-p` | Webpage provider | `crawl4ai` |
| `--skip-if-exists` | Skip if output file exists | false |
| `-o, --output` | Output file path | stdout |

**Provider Notes:**

- `crawl4ai`: Requires the Crawl4AI Docker service running locally

## Batch Processing

All batch commands support `--dry-run` to preview what would be processed without executing.

### YouTube Playlists

```bash
# Process entire playlist
gobbler batch youtube-playlist "https://youtube.com/playlist?list=PLxxx" \
    --output-dir ./transcripts

# With custom output directory
gobbler batch youtube-playlist "URL" -o ./transcripts

# Preview what would be processed (dry run)
gobbler batch youtube-playlist "URL" -o ./transcripts --dry-run
```

Example dry run output:
```
Dry Run Preview
══════════════════════════════════════════════════
Playlist:       https://youtube.com/playlist?list=PLxxx
Output:         ./transcripts (will create)
Total videos:   47
Would process:  45
Would skip:     2 (already exist)
Concurrency:    3
Estimated time: ~2m 15s
```

### Directory Processing

```bash
# Transcribe all audio files in directory
gobbler batch directory ./recordings --pattern "*.mp3" -o ./transcripts

# Convert all documents
gobbler batch directory ./documents --pattern "*.pdf" -o ./markdown

# Preview without processing
gobbler batch directory ./documents --pattern "*.pdf" -o ./markdown --dry-run

# JSON output for scripting
gobbler batch directory ./docs -o ./md --dry-run --json
```

### Multiple URLs

```bash
# Process URLs from file
gobbler batch webpages urls.txt -o ./pages

# Preview what would be fetched
gobbler batch webpages urls.txt -o ./pages --dry-run
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
| `--help` | `-h` | Show help message |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOBBLER_CONFIG` | Config file path | `~/.config/gobbler/config.yaml` |
| `OPENAI_API_KEY` | OpenAI API key (for `openai-whisper` provider) | None |
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

## Additional Commands

The following command groups are also available:

| Command | Description |
|---------|-------------|
| `gobbler status` | Check service health and readiness |
| `gobbler explain` | Diagnose errors and get solutions |
| `gobbler relay` | Browser relay server management |
| `gobbler daemon` | Daemon management |
| `gobbler jobs` | Background job queue management |
| `gobbler completion` | Shell completion scripts |

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
# Archive documentation site pages from a file
gobbler batch webpages doc-urls.txt -o ./archive
```

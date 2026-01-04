---
name: gobbler-utils
description: Shared utilities for Gobbler content conversion skills. Provides batch processing, frontmatter generation, output formatting, and Docker service health checks. Other gobbler-* skills depend on these utilities.
version: 2.1.0
---

# Gobbler Utilities

Shared utilities for batch processing, managing Gobbler services, and checking system health.

## Batch Processing

Gobbler provides batch commands for processing multiple files or URLs at once.

### Available Batch Commands

| Command | Description |
|---------|-------------|
| `youtube-playlist` | Convert all videos in a YouTube playlist to markdown |
| `directory` | Batch convert files (audio/documents) from a directory |
| `webpages` | Batch convert web pages from a URL list to markdown |

### YouTube Playlist Batch

Convert all videos in a YouTube playlist to markdown transcripts.

```bash
# Basic usage
gobbler batch youtube-playlist "https://youtube.com/playlist?list=PLxxx" -o ./transcripts

# With options
gobbler batch youtube-playlist "https://youtube.com/playlist?list=PLxxx" \
  -o ./transcripts \
  -l en \              # Preferred language (default: en)
  -c 5 \               # Concurrent conversions (default: 3)
  --timestamps         # Include timestamps in output

# JSON output for programmatic use
gobbler batch youtube-playlist "https://youtube.com/playlist?list=PLxxx" -o ./out --json
```

**Options:**
- `-o, --output PATH` - Output directory for transcripts (required)
- `-l, --language TEXT` - Preferred transcript language (default: en)
- `--timestamps / --no-timestamps` - Include timestamps (default: no-timestamps)
- `-c, --concurrency INTEGER` - Concurrent conversions (default: 3)
- `-f, --format TEXT` - Output format: markdown/json (default: markdown)
- `-j, --json` - Output progress and results as JSON lines

### Directory Batch

Batch convert audio or document files from a directory.

```bash
# Convert audio files
gobbler batch directory ./recordings -o ./transcripts --pattern "*.mp3"
gobbler batch directory ./recordings -o ./transcripts --pattern "*.wav" --type audio

# Convert documents
gobbler batch directory ./docs -o ./markdown --pattern "*.pdf"
gobbler batch directory ./docs -o ./markdown --pattern "*.docx" --type document

# Auto-detect file types
gobbler batch directory ./mixed-files -o ./output

# JSON output for programmatic use
gobbler batch directory ./docs -o ./markdown --json
```

**Options:**
- `-o, --output PATH` - Output directory for converted files (required)
- `-p, --pattern TEXT` - File pattern to match, e.g., `*.mp3`, `*.pdf` (default: `*.*`)
- `-c, --concurrency INTEGER` - Concurrent conversions (default: 3)
- `-t, --type TEXT` - File type: audio/document (auto-detects if not specified)
- `-j, --json` - Output progress and results as JSON lines

### Webpages Batch

Batch convert web pages to markdown from a file containing URLs.

```bash
# From a file (one URL per line, # for comments)
gobbler batch webpages urls.txt -o ./output

# From stdin
cat urls.txt | gobbler batch webpages -o ./output

# With options
gobbler batch webpages urls.txt -o ./output \
  -c 5 \               # Concurrent conversions (default: 3, max: 10)
  -t 60 \              # Timeout per page in seconds (default: 30)
  -s ".article-body"   # CSS selector to extract specific content

# Skip already converted URLs
gobbler batch webpages urls.txt -o ./output --skip-existing

# Queue for background processing
gobbler batch webpages urls.txt -o ./output --queue

# JSON output for programmatic use
gobbler batch webpages urls.txt -o ./output --json
```

**Options:**
- `-o, --output-dir PATH` - Output directory for converted files (required)
- `-c, --concurrency INTEGER` - Concurrent conversions, 1-10 (default: 3)
- `-t, --timeout INTEGER` - Timeout per page in seconds (default: 30)
- `-s, --selector TEXT` - CSS selector to extract specific content
- `--skip-existing / --no-skip-existing` - Skip URLs with existing output files (default: skip)
- `--queue` - Queue the batch job instead of running inline
- `-j, --json` - Output progress and results as JSON lines

## Service Health Checks

### Using the CLI

```bash
# Check daemon status
gobbler daemon status

# View daemon logs
gobbler daemon logs
gobbler daemon logs --follow
```

### Using curl

```bash
# Check Docling (port 5001)
curl http://localhost:5001/health

# Check Crawl4AI (port 11235)
curl http://localhost:11235/health

# Check Redis (port 6380)
redis-cli -p 6380 ping
```

## Service Management

```bash
# Start all Docker services
cd /path/to/gobbler
docker compose up -d

# Start specific service
docker compose up -d docling
docker compose up -d crawl4ai

# View service logs
docker logs gobbler-docling --tail 50
docker logs gobbler-crawl4ai --tail 50

# Restart a service
docker compose restart docling
```

## Daemon Management

```bash
# Start daemon (background)
gobbler daemon start

# Start daemon (foreground for debugging)
gobbler daemon start --foreground

# Stop daemon
gobbler daemon stop

# Restart daemon
gobbler daemon restart
```

## Architecture

Gobbler utilities are built into the core packages:
- `gobbler_core` - Frontmatter generation, HTTP clients, file handling
- `gobbler_cli` - Command-line utilities and batch processing

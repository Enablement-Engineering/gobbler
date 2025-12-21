---
name: gobbler-utils
description: Shared utilities for Gobbler content conversion skills. Provides frontmatter generation, output formatting, and Docker service health checks. Other gobbler-* skills depend on these utilities.
version: 1.0.0
---

# Gobbler Utilities

Shared utilities for all Gobbler content conversion skills.

## Scripts

### frontmatter.py

Generate YAML frontmatter for markdown output. Supports YouTube, webpage, document, and audio content types.

```bash
# Generate YouTube frontmatter
uv run scripts/frontmatter.py youtube \
  --url "https://youtube.com/watch?v=VIDEO_ID" \
  --video-id "VIDEO_ID" \
  --title "Video Title" \
  --duration 300 \
  --language "en" \
  --word-count 1500

# Generate webpage frontmatter
uv run scripts/frontmatter.py webpage \
  --url "https://example.com" \
  --title "Page Title" \
  --word-count 500 \
  --conversion-time 1200

# Generate document frontmatter
uv run scripts/frontmatter.py document \
  --path "/path/to/file.pdf" \
  --format "pdf" \
  --pages 10 \
  --word-count 3000 \
  --conversion-time 5000

# Generate audio frontmatter
uv run scripts/frontmatter.py audio \
  --path "/path/to/audio.mp3" \
  --duration 600 \
  --language "en" \
  --model "small" \
  --word-count 2000 \
  --conversion-time 45000
```

### docker_health.py

Check availability of Docker services (Crawl4AI, Docling).

```bash
# Check Crawl4AI (port 11235)
uv run scripts/docker_health.py crawl4ai

# Check Docling (port 5001)
uv run scripts/docker_health.py docling

# Check all services
uv run scripts/docker_health.py all
```

### http_client.py

Retry-enabled HTTP client for Docker service calls.

```bash
# POST request with retry
uv run scripts/http_client.py POST http://localhost:11235/crawl \
  --json '{"urls": ["https://example.com"]}' \
  --retries 3

# GET request
uv run scripts/http_client.py GET http://localhost:5001/health
```

## Usage from Other Skills

Other gobbler-* skills can use these utilities by running them as subprocesses or importing the patterns directly into their own UV scripts.

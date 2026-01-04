---
icon: material/lightning-bolt
---

# Gobbler Skills

Claude Code Skills that bypass MCP entirely, using UV single-file scripts with inline dependencies. Skills provide progressive disclosure - only loading when relevant - saving ~65% context compared to always-loaded MCP tool definitions.

## When to Use Skills vs MCP Tools

Gobbler provides two complementary interfaces to the same backend services. Choose the right approach based on your needs.

### Decision Matrix

| Use Case | Recommended Approach | Reason |
|----------|---------------------|--------|
| Quick discovery/exploration | **Skills** | ~100 token context cost vs ~4,500 |
| Heavy batch operations (>10 items) | **MCP Tools** | Server-side processing with progress tracking |
| Browser automation workflows | **Skills** (gobbler-browser) | Interactive guidance for multi-step tasks |
| NotebookLM interaction | **Skills** (gobbler-notebooklm) | Complex workflows with decision points |
| Single file conversion | **Either** | Equivalent functionality, choose based on context |
| Background queue jobs | **MCP Tools** | Server manages job state and auto-queue |
| Frequent operations (5+) | **MCP Tools** | Amortized context cost becomes lower |
| Infrequent operations (1-2) | **Skills** | Lower total context usage |
| Automated pipelines | **MCP Tools** | Standardized tool interface, easier chaining |
| Offline/standalone usage | **Skills** | Works without MCP server running |

### Use Skills When:

- **Minimal context overhead** - You want ~100 tokens vs ~4,500 for MCP tool definitions
- **Interactive guidance needed** - Browser automation, NotebookLM queries, multi-step workflows
- **Exploring capabilities** - Discovering what Gobbler can do before committing to a tool
- **Workflow involves decision points** - Need to evaluate results between steps
- **MCP server unavailable** - Want to use Gobbler standalone

### Use MCP Tools When:

- **Server-side job management** - Queued batch operations with progress tracking
- **Well-defined operations** - Single-purpose tasks that don't need guidance
- **Efficient tool chaining** - Combining multiple operations in sequence
- **Building automated pipelines** - Reproducible workflows with consistent interface
- **Frequent usage** - Context overhead amortized over 5+ operations

### Both Work Equally Well For:

- Single file conversions (YouTube, webpage, document, audio)
- Simple browser operations without complex workflows
- One-shot content extraction tasks
- Individual document processing

### Context Usage Comparison

| Approach | Initial Load | Per Operation | 5 Operations Total |
|----------|--------------|---------------|-------------------|
| **Skills** | 100 tokens | ~500 tokens | ~2,600 tokens |
| **MCP Tools** | 4,500 tokens | ~100 tokens | ~5,000 tokens |

**Break-even point:** Around 5 operations per session. Below this, Skills are more efficient. Above this, MCP Tools are more efficient.

## Overview

| Skill | Description | Backend |
|-------|-------------|---------|
| `gobbler-youtube` | YouTube transcription and downloads | youtube-transcript-api, yt-dlp, TranscriptAPI.com |
| `gobbler-webpage` | Web page fetching and crawling | Crawl4AI Docker (port 11235) |
| `gobbler-document` | PDF/DOCX/PPTX/XLSX conversion | Docling Docker (port 5001) |
| `gobbler-audio` | Audio/video transcription | faster-whisper, ffmpeg |
| `gobbler-browser` | Browser control via extension | WebSocket (port 4625) |
| `gobbler-notebooklm` | NotebookLM interaction via browser | Browser extension + WebSocket |
| `gobbler-chatgpt` | ChatGPT interaction via browser | Browser extension + WebSocket |
| `gobbler-claude` | Claude.ai interaction via browser | Browser extension + WebSocket |
| `gobbler-gemini` | Google Gemini interaction via browser | Browser extension + WebSocket |
| `gobbler-setup` | Installation, configuration, and troubleshooting | Pure Python |
| `gobbler-utils` | Shared utilities | Pure Python |

## Architecture with Claude Desktop/Code

When using Gobbler with Claude Desktop or Claude Code, there are **two interfaces** (MCP tools and Skills) that call the **same backends directly**:

```
┌───────────────────────────────────────────────────────────────────────┐
│                          YOUR COMPUTER                                 │
│                                                                        │
│    ┌──────────────────┐                                               │
│    │  Claude          │                                               │
│    │  Desktop/Code    │                                               │
│    └────────┬─────────┘                                               │
│             │                                                          │
│    ┌────────┴────────┐                                                │
│    │                 │                                                 │
│    ▼                 ▼                                                 │
│  ┌───────────┐   ┌───────────────┐                                    │
│  │MCP Server │   │ Skills        │    Both make direct HTTP calls     │
│  │(stdio)    │   │ (uv scripts)  │    to the same backends            │
│  └─────┬─────┘   └───────┬───────┘                                    │
│        │                 │                                             │
│        └────────┬────────┘                                             │
│                 │                                                      │
│    ┌────────────┼────────────┬────────────┬────────────┐              │
│    │            │            │            │            │              │
│    ▼            ▼            ▼            ▼            ▼              │
│ ┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│ │Crawl4AI│ │Docling │ │ YouTube  │ │ Whisper  │ │  Relay   │         │
│ │ :11235 │ │ :5001  │ │ APIs     │ │ (local)  │ │  :4625   │         │
│ │        │ │        │ │          │ │          │ │          │         │
│ │ HTTP   │ │ HTTP   │ │ HTTP     │ │ Library  │ │  HTTP    │         │
│ └────────┘ └────────┘ └──────────┘ └──────────┘ └────┬─────┘         │
│                                                       │ WebSocket     │
│                                                       ▼               │
│                                                 ┌──────────┐          │
│                                                 │ Browser  │          │
│                                                 │Extension │          │
│                                                 └──────────┘          │
└───────────────────────────────────────────────────────────────────────┘
```

**Two interfaces to the same backends:**

| Backend | MCP Tool | Skill | Connection |
|---------|----------|-------|------------|
| Crawl4AI | `mcp__gobbler-mcp__fetch_webpage` | `gobbler-webpage/scripts/fetch.py` | HTTP to :11235 |
| Docling | `mcp__gobbler-mcp__convert_document` | `gobbler-document/scripts/convert.py` | HTTP to :5001 |
| YouTube | `mcp__gobbler-mcp__transcribe_youtube` | `gobbler-youtube/scripts/transcribe.py` | HTTP to APIs |
| Whisper | `mcp__gobbler-mcp__transcribe_audio` | `gobbler-audio/scripts/transcribe.py` | Local library |
| Browser | `mcp__gobbler-mcp__browser_*` | `gobbler-browser/scripts/browser_api.py` | HTTP to :4625 |

**Key insight:** MCP tools and Skills make identical HTTP calls to backends. The only difference is the interface exposed to Claude.

**Why use Skills over MCP?**
- **Context savings** - Skills load ~100 tokens vs ~4,500 for MCP tool definitions
- **Flexibility** - Full Python scripting with CLI options
- **Standalone** - Skills work without MCP server running

**Browser skills require:**
1. Relay server running on port 4625 (auto-starts when skill runs)
2. Browser extension installed and showing "Connected"
3. Target tabs in the "Gobbler" tab group

**Relay commands:**
```bash
uv run src/gobbler_relay/relay.py --status  # Check if running
uv run src/gobbler_relay/relay.py --daemon  # Start manually
uv run src/gobbler_relay/relay.py --stop    # Stop manually
```

## Installation

### Via Claude Code Plugin Marketplace (Recommended)

```bash
# Install Gobbler as a plugin
/plugin add Enablement-Engineering/gobbler
```

### Via Git Clone

Skills are located in `skills/gobbler-*/` at the project root. Clone and configure:

```bash
git clone https://github.com/Enablement-Engineering/gobbler.git
```

### Prerequisites

Skills require:

1. **UV** - Python package manager with script support
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Docker services** (for webpage/document conversion)
   ```bash
   # Crawl4AI
   docker run -d -p 11235:11235 --name gobbler-crawl4ai unclecode/crawl4ai:basic

   # Docling
   docker run -d -p 5001:5001 --name gobbler-docling quay.io/docling-project/docling-serve:latest
   ```

3. **ffmpeg** (for audio transcription)
   ```bash
   brew install ffmpeg  # macOS
   ```

## Environment Variables

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
# YouTube transcript providers
export WEBSHARE_USER=your_webshare_username      # Rotating proxy (free API)
export WEBSHARE_PASS=your_webshare_password
export TRANSCRIPTAPI_KEY=your_transcriptapi_key  # Paid API fallback
```

## Skill Details

### gobbler-youtube

Transcribe YouTube videos to markdown with multiple provider options.

**Scripts:**
- `transcribe.py` - Extract video transcripts
- `download.py` - Download video/audio files
- `get_metadata.py` - Get video metadata

**Providers:**

| Provider | Cost | Reliability | Usage |
|----------|------|-------------|-------|
| `youtube-transcript-api` | Free | May get IP blocked | Default |
| `transcriptapi` | ~$0.01/video | High, no IP blocks | `--provider transcriptapi` |
| `auto` | Free + fallback | Best of both | `--provider auto` |

**Usage:**
```bash
cd skills/gobbler-youtube/scripts

# Basic (uses free API with Webshare proxy if configured)
uv run transcribe.py "https://youtube.com/watch?v=VIDEO_ID"

# With timestamps
uv run transcribe.py "https://youtube.com/watch?v=VIDEO_ID" --timestamps

# Use paid API directly
uv run transcribe.py "https://youtube.com/watch?v=VIDEO_ID" --provider transcriptapi

# Auto-fallback (try free first, use paid if blocked)
uv run transcribe.py "https://youtube.com/watch?v=VIDEO_ID" --provider auto

# Download video
uv run download.py "https://youtube.com/watch?v=VIDEO_ID" --output-dir ./downloads
```

**Bypassing IP Blocks:**

YouTube may block your IP when using the free `youtube-transcript-api`. Solutions:

1. **Webshare Proxy** (~$3.50/month) - Rotating residential proxies
   - Sign up at https://www.webshare.io/
   - Get credentials from https://proxy.webshare.io/proxy/rotating
   - Set `WEBSHARE_USER` and `WEBSHARE_PASS` environment variables

2. **TranscriptAPI.com** (~$0.01/video) - Paid API, no IP blocks
   - Sign up at https://transcriptapi.com/
   - Get API key from https://transcriptapi.com/dashboard/api-keys
   - Set `TRANSCRIPTAPI_KEY` environment variable

---

### gobbler-webpage

Convert web pages to markdown using Crawl4AI.

**Requires:** Crawl4AI Docker container on port 11235

**Scripts:**
- `fetch.py` - Basic page fetch
- `fetch_with_selector.py` - Extract specific content with CSS/XPath
- `crawl.py` - Recursive site crawling

**Usage:**
```bash
cd skills/gobbler-webpage/scripts

# Basic fetch
uv run fetch.py "https://example.com"

# With CSS selector
uv run fetch_with_selector.py "https://example.com" --selector "article.main"

# Crawl entire site
uv run crawl.py "https://docs.example.com" --max-depth 2 --max-pages 50
```

---

### gobbler-document

Convert documents (PDF, DOCX, PPTX, XLSX) to markdown using Docling.

**Requires:** Docling Docker container on port 5001

**Scripts:**
- `convert.py` - Convert document to markdown

**Usage:**
```bash
cd skills/gobbler-document/scripts

# Convert PDF
uv run convert.py /path/to/document.pdf

# With OCR disabled (faster)
uv run convert.py /path/to/document.pdf --no-ocr

# Save to file
uv run convert.py /path/to/document.pdf --output document.md
```

---

### gobbler-audio

Transcribe audio/video files using faster-whisper with Metal/CoreML acceleration.

**Requires:** ffmpeg installed

**Scripts:**
- `transcribe.py` - Transcribe audio/video to text
- `extract_audio.py` - Extract audio from video files

**Usage:**
```bash
cd skills/gobbler-audio/scripts

# Transcribe audio
uv run transcribe.py /path/to/audio.mp3

# Use larger model for better accuracy
uv run transcribe.py /path/to/video.mp4 --model medium

# Extract audio from video first (for large files)
uv run extract_audio.py /path/to/video.mp4 --output audio.mp3
```

**Model Sizes:**

| Model | Speed | Accuracy | VRAM |
|-------|-------|----------|------|
| tiny | Fastest | Lower | ~1GB |
| base | Fast | Moderate | ~1GB |
| small | Moderate | Good | ~2GB |
| medium | Slower | Better | ~5GB |
| large | Slowest | Best | ~10GB |

---

### gobbler-browser

Control browser via Gobbler browser extension.

**Requires:**
- Gobbler browser extension installed
- MCP server running (provides WebSocket server on port 4625)

**Scripts:**
- `browser_api.py` - Browser control commands
- `notebooklm.py` - NotebookLM-specific interactions

**Note:** These scripts require the MCP server to be running as it provides the WebSocket relay to the browser extension.

**Usage:**
```bash
cd skills/gobbler-browser/scripts

# Check connection
uv run browser_api.py check

# List tabs
uv run browser_api.py tabs

# Extract current page
uv run browser_api.py extract

# Execute JavaScript
uv run browser_api.py execute "document.title"
```

---

### gobbler-notebooklm

Interact with NotebookLM via browser automation.

**Requires:**
- Gobbler browser extension installed
- MCP server running (provides WebSocket server on port 4625)
- NotebookLM tab in the Gobbler tab group

**Scripts:**
- `notebooklm.py` - NotebookLM CLI with query, list, and info commands

**Usage:**
```bash
cd skills/gobbler-notebooklm/scripts

# List available NotebookLM tabs
uv run notebooklm.py list

# Get notebook info
uv run notebooklm.py info

# Send a query and get response
uv run notebooklm.py query "What are the key points in this document?"

# Query specific tab with custom timeout
uv run notebooklm.py query "Summarize the main arguments" --tab-id 12345 --timeout 120
```

---

### gobbler-chatgpt

Interact with ChatGPT conversations via browser automation.

**Requires:**
- Gobbler browser extension installed
- MCP server running (provides WebSocket server on port 4625)
- ChatGPT tab in the Gobbler tab group

**Usage:**
```bash
# List ChatGPT tabs
gobbler chatgpt list

# Send message and wait for response
gobbler chatgpt query "Your message here" --timeout 150

# Get last response
gobbler chatgpt last

# Get chat history
gobbler chatgpt history --count 10
```

---

### gobbler-claude

Interact with Claude.ai conversations via browser automation.

**Requires:**
- Gobbler browser extension installed
- MCP server running (provides WebSocket server on port 4625)
- Claude.ai tab in the Gobbler tab group

**Usage:**
```bash
# List Claude tabs
gobbler claude list

# Send message and wait for response
gobbler claude query "Your message here" --timeout 150

# Get last response
gobbler claude last

# Get chat history
gobbler claude history --count 10
```

---

### gobbler-gemini

Interact with Google Gemini conversations via browser automation.

**Requires:**
- Gobbler browser extension installed
- MCP server running (provides WebSocket server on port 4625)
- Gemini tab in the Gobbler tab group
- Signed into Google account

**Usage:**
```bash
# List Gemini tabs
gobbler gemini list

# Send message and wait for response
gobbler gemini query "Your message here" --timeout 150

# Get last response
gobbler gemini last

# Get chat history
gobbler gemini history --count 10
```

---

### gobbler-setup

Install, configure, and troubleshoot Gobbler.

**Usage:**
```bash
# Quick health check
gobbler --version
gobbler daemon status
docker ps --filter "name=gobbler"

# Check individual services
curl -s http://localhost:5001/health
curl -s http://localhost:11235/health
```

See the full [Setup & Troubleshooting](setup-troubleshooting.md) guide for complete installation and troubleshooting information.

---

### gobbler-utils

Shared utilities used by other skills.

**Scripts:**
- `frontmatter.py` - Generate YAML frontmatter for different content types
- `docker_health.py` - Check Docker service health
- `http_client.py` - HTTP client with retry logic

**Usage:**
```bash
cd skills/gobbler-utils/scripts

# Check Docker services
uv run docker_health.py all
uv run docker_health.py crawl4ai
uv run docker_health.py docling

# Generate frontmatter
uv run frontmatter.py youtube --url "https://..." --title "Video" --duration 300
uv run frontmatter.py webpage --url "https://..." --title "Page" --word-count 1000
```

## Architecture

Skills use UV single-file scripts with PEP 723 inline dependencies:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "youtube-transcript-api>=0.6.0",
#   "yt-dlp>=2024.0.0",
# ]
# ///
```

This allows:
- **Self-contained scripts** - No separate requirements.txt needed
- **Automatic dependency installation** - UV handles it on first run
- **Progressive disclosure** - Skills only load when relevant
- **Context savings** - ~65% less context than MCP tool definitions

## Provider Interface Pattern

The YouTube skill demonstrates a provider interface pattern that can be extended:

```python
class TranscriptProvider:
    def fetch(self, video_id, language, include_timestamps) -> (segments, language, metadata)

class YouTubeTranscriptAPIProvider(TranscriptProvider): ...  # Free
class TranscriptAPIProvider(TranscriptProvider): ...         # Paid API
class AutoFallbackProvider(TranscriptProvider): ...          # Try free → paid
```

This pattern allows:
- Multiple backends for the same capability
- Easy addition of new providers
- Graceful fallback between providers
- User choice of cost/reliability tradeoffs

## Comparison: Skills vs MCP

| Aspect | MCP Tools | Skills |
|--------|-----------|--------|
| Context usage | ~4,500 tokens always loaded | ~100 tokens metadata, full only when used |
| Dependency management | Server-side | Per-script inline |
| Execution | Via MCP protocol | Direct UV script execution |
| Flexibility | Fixed tool interface | Full Python scripting |
| Offline support | Requires MCP server | Works standalone |

Skills are ideal for:
- Complex multi-step workflows
- Operations that benefit from scripting
- Reducing context window usage
- Offline or standalone usage

MCP tools are ideal for:
- Simple, frequent operations
- Real-time streaming responses
- Integration with MCP clients
- Operations requiring server state

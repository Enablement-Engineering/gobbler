---
icon: material/cog
---

# Configuration

Gobbler can be configured via YAML configuration file or environment variables.

## Configuration File

Default location: `~/.config/gobbler/config.yml`

### Full Example

```yaml
# Service endpoints
services:
  crawl4ai:
    host: localhost
    port: 11235
  docling:
    host: localhost
    port: 5001

# Storage settings
storage:
  type: "sqlite"
  path: "~/.config/gobbler/jobs.db"

# Logging configuration
logging:
  level: "INFO"            # DEBUG, INFO, WARNING, ERROR
  format: "text"           # text, json
  file: null               # Optional log file path

# Whisper transcription defaults
whisper:
  model: "small"           # tiny, base, small, medium, large
  language: "auto"         # ISO 639-1 code or "auto"
  device: "auto"           # auto, cpu, cuda, mps

# Web scraping defaults
crawl:
  timeout: 30              # Request timeout in seconds
  user_agent: null         # Custom user agent (null = default)
  respect_robots: true     # Respect robots.txt
  delay: 1.0               # Delay between requests (seconds)

# YouTube settings
youtube:
  include_timestamps: false
  language: "auto"
  delay_between_requests: 1.5
  jitter_range: 1.0
  max_retries: 3

# Document conversion
documents:
  enable_ocr: true         # Enable OCR for scanned documents
  timeout: 300             # Conversion timeout in seconds

# Queue settings
queue:
  enabled: true
  auto_queue_threshold: 105  # Auto-queue jobs taking longer than this (seconds)
  default_timeout: "30m"    # Default job timeout
  queues:
    - default
    - transcription
    - download

# Monitoring (optional)
monitoring:
  enabled: false
  metrics_port: 9090
  health_check_interval: 30
```

## Environment Variables

Environment variables override config file settings:

| Variable | Config Path | Description |
|----------|-------------|-------------|
| `TRANSCRIPTAPI_KEY` | - | TranscriptAPI.com API key |
| `OPENAI_API_KEY` | - | OpenAI API key (for openai-whisper provider) |
| `WEBSHARE_USER` | - | Webshare proxy username (for YouTube) |
| `WEBSHARE_PASS` | - | Webshare proxy password (for YouTube) |
| `YOUTUBE_PROXY` | - | Custom proxy URL for YouTube |

### YouTube Provider Configuration

YouTube transcripts use a separate provider system with automatic fallback. Configure via environment variables:

```bash
# Recommended: Enable auto-fallback (free first, paid if blocked)
export TRANSCRIPTAPI_KEY=your_api_key

# Alternative: Use rotating proxy with free API
export WEBSHARE_USER=your_username
export WEBSHARE_PASS=your_password

# Alternative: Use custom proxy with free API
export YOUTUBE_PROXY=http://user:pass@proxy.example.com:8080
```

**Provider Selection Logic:**

| Configuration | Provider Used | Behavior |
|---------------|---------------|----------|
| `TRANSCRIPTAPI_KEY` set | `AutoFallbackProvider` | Tries free API first, falls back to paid on IP block |
| Only proxy configured | `YouTubeTranscriptAPIProvider` | Uses free API through proxy |
| Nothing configured | `YouTubeTranscriptAPIProvider` | Uses free API directly (may get IP blocked) |

For detailed YouTube provider documentation, see [YouTube Transcription](skills/youtube.md#transcript-providers).

## Service Configuration

### Docling (Document Conversion)

```yaml
services:
  docling:
    host: localhost
    port: 5001

documents:
  enable_ocr: true
  timeout: 300
```

**Docker Compose:**
```yaml
docling:
  image: quay.io/docling-serve/docling-serve:latest
  ports:
    - "5001:5001"
```

### Crawl4AI (Web Scraping)

```yaml
services:
  crawl4ai:
    host: localhost
    port: 11235

crawl:
  timeout: 30
  respect_robots: true
```

**Docker Compose:**
```yaml
crawl4ai:
  image: unclecode/crawl4ai:latest
  ports:
    - "11235:11235"
```

## Providers

Gobbler uses a provider abstraction system that allows pluggable backends for content conversion. Each content category (transcription, document, webpage) can have multiple provider implementations with independent configurations.

### Provider Configuration

```yaml
providers:
  transcription:
    default: whisper-local
    whisper-local:
      model: small
    openai-whisper:
      model: whisper-1
  document:
    default: docling
    docling:
      ocr: true
  webpage:
    default: crawl4ai
    crawl4ai:
      timeout: 30
```

### Setting Default Providers

Each category has a `default` key that specifies which provider to use when none is explicitly requested:

```yaml
providers:
  transcription:
    default: whisper-local    # Use local Whisper by default
  document:
    default: docling          # Use Docling by default
  webpage:
    default: crawl4ai         # Use Crawl4AI by default
```

When you run a conversion command without specifying a provider, Gobbler uses the configured default.

### Provider-Specific Options

Each provider can have its own configuration options nested under its name:

```yaml
providers:
  transcription:
    default: whisper-local
    whisper-local:
      model: small            # Model size: tiny, base, small, medium, large
      device: auto            # Device: auto, cpu, cuda, mps
      language: auto          # Language code or "auto" for detection
    openai-whisper:
      model: whisper-1        # OpenAI model name
      # Requires OPENAI_API_KEY environment variable

  document:
    default: docling
    docling:
      ocr: true               # Enable OCR for scanned documents
      timeout: 300            # Conversion timeout in seconds

  webpage:
    default: crawl4ai
    crawl4ai:
      timeout: 30             # Request timeout in seconds
      respect_robots: true    # Respect robots.txt
```

### CLI Provider Override

The `--provider` flag on CLI commands overrides the config default:

```bash
# Use config default provider
gobbler audio convert recording.mp3

# Override to use OpenAI Whisper instead
gobbler audio convert recording.mp3 --provider openai-whisper

# Override webpage provider
gobbler webpage convert https://example.com --provider crawl4ai
```

This allows you to set sensible defaults in your config while still having flexibility to use alternative providers on a per-command basis.

### Provider Categories

| Category | Available Providers | Default |
|----------|---------------------|---------|
| `transcription` | `whisper-local`, `openai-whisper` | `whisper-local` |
| `document` | `docling` | `docling` |
| `webpage` | `crawl4ai` | `crawl4ai` |

### Provider Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required for openai-whisper) | - |

For detailed provider documentation, see [Providers](providers.md).

## Whisper Model Selection

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| tiny | 39M | ~32x | Good | Quick drafts |
| base | 74M | ~16x | Better | General use |
| small | 244M | ~6x | Great | Default |
| medium | 769M | ~2x | Excellent | Important content |
| large | 1550M | ~1x | Best | Critical accuracy |

```yaml
whisper:
  model: "small"  # Recommended default
```

## Batch Processing Limits

```yaml
queue:
  auto_queue_threshold: 105  # Queue jobs taking longer than this (seconds)

# Per-tool limits (hardcoded):
# - YouTube playlist: max 500 videos
# - Web pages: max 100 URLs
# - Site crawl: max 500 pages, depth 5
```

## Monitoring

Enable Prometheus metrics:

```yaml
monitoring:
  enabled: true
  metrics_port: 9090
```

Access metrics at `http://localhost:9090/metrics`.

## Configuration Precedence

1. **Command-line arguments** (highest priority)
2. **Environment variables**
3. **Config file** (`~/.config/gobbler/config.yml`)
4. **Default values** (lowest priority)

## Validation

Gobbler validates configuration on startup. Invalid configurations produce clear error messages:

```
Configuration Error: Invalid whisper.model 'xlarge'
  Valid options: tiny, base, small, medium, large
```

## Hot Reload

Configuration changes are detected automatically (when hot-reload is enabled):

```yaml
# Changes to these settings reload without restart:
- logging.level
- crawl.timeout
- whisper.model

# Changes to these require restart:
- services.*
- queue.enabled
```

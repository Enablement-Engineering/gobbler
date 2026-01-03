# Configuration

Gobbler can be configured via YAML configuration file or environment variables.

## Configuration File

Default location: `~/.config/gobbler/config.yaml`

### Full Example

```yaml
# Service endpoints
services:
  docling: "http://localhost:5001"
  crawl4ai: "http://localhost:11235"
  redis: "redis://localhost:6380"

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
  auto_queue_threshold: 10  # Auto-queue batches larger than this
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
| `GOBBLER_CONFIG` | - | Config file path |
| `GOBBLER_LOG_LEVEL` | `logging.level` | Log level |
| `GOBBLER_DOCLING_URL` | `services.docling` | Docling service URL |
| `GOBBLER_CRAWL4AI_URL` | `services.crawl4ai` | Crawl4AI service URL |
| `GOBBLER_REDIS_URL` | `services.redis` | Redis connection URL |
| `TRANSCRIPTAPI_KEY` | - | TranscriptAPI.com API key |
| `GOBBLER_WHISPER_MODEL` | `whisper.model` | Default Whisper model |

## Service Configuration

### Docling (Document Conversion)

```yaml
services:
  docling: "http://localhost:5001"

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
  crawl4ai: "http://localhost:11235"

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

### Redis (Job Queue)

```yaml
services:
  redis: "redis://localhost:6380"

queue:
  enabled: true
```

**Docker Compose:**
```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6380:6379"
```

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

## Session Management

Sessions store authentication for crawling protected content:

```yaml
# Sessions stored in: ~/.config/gobbler/sessions/
# Format: {session_id}.json
```

Create sessions via MCP:
```python
create_crawl_session(
    session_id="my-site",
    cookies='[{"name": "auth", "value": "token", "domain": "example.com"}]'
)
```

## Batch Processing Limits

```yaml
queue:
  auto_queue_threshold: 10  # Queue batches > 10 items

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
3. **Config file** (`~/.config/gobbler/config.yaml`)
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

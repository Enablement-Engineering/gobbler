# Gobbler Daemon Architecture: Universal Content Fabric

## Vision

Transform Gobbler from an MCP-centric tool into a **Universal Content Conversion Fabric** - a daemon that runs persistently on your machine and can be consumed through multiple interfaces:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Gobbler Daemon (Fabric Core)                     │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│  │  YouTube    │  │   Audio     │  │  Document   │  │  Webpage  │  │
│  │  Converter  │  │ Transcriber │  │  Converter  │  │  Scraper  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Core Services                               │  │
│  │  • Job Queue (Redis/SQLite)  • Health Monitor  • Metrics       │  │
│  │  • Config Manager            • Event Bus       • Plugin System │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   REST API    │    │   MCP Server    │    │   CLI/SDK       │
│  (Port 4600)  │    │   (stdio/SSE)   │    │   (gobbler-*)   │
└───────────────┘    └─────────────────┘    └─────────────────┘
        │                      │                      │
        ▼                      ▼                      ▼
   curl/httpie          Claude Code            Python/Shell
   Shortcuts            Claude Desktop         Automation
   n8n/Zapier           Agent SDK              Scripts
```

---

## Current State Analysis

### What Works Well

1. **`gobbler_core`** is already MCP-independent - pure converters
2. **`gobbler_relay`** shows daemon pattern works (auto-start, PID files, graceful shutdown)
3. **Skills** demonstrate standalone script execution
4. **Batch processing** with Redis queue shows job management

### Current Limitations

1. **MCP-only interface** - Can't use without MCP client
2. **No REST API** - Can't integrate with webhooks, shortcuts, automation
3. **No SDK** - Can't import as library in Python scripts
4. **Scattered entry points** - Multiple ways to start, no unified daemon
5. **No event system** - Can't subscribe to conversion events

---

## Proposed Architecture

### Layer 1: Daemon Core (`gobbler_daemon`)

A unified process that manages all services:

```python
# New package: src/gobbler_daemon/

gobbler_daemon/
├── __init__.py
├── daemon.py          # Main daemon process management
├── config.py          # Unified configuration
├── events.py          # Event bus (pub/sub)
├── plugins.py         # Plugin discovery & loading
├── health.py          # Service health monitoring
├── scheduler.py       # Cron-like scheduled jobs
└── storage.py         # Persistent state (SQLite fallback)
```

**Key Features:**
- Starts on boot (launchd/systemd)
- Single process, multiple interfaces
- Graceful shutdown with cleanup
- Hot-reload configuration
- Plugin architecture for new converters

### Layer 2: Interface Adapters

#### REST API (`gobbler_api`)

```python
# New package: src/gobbler_api/

gobbler_api/
├── __init__.py
├── server.py          # FastAPI application
├── routes/
│   ├── convert.py     # POST /convert/{type}
│   ├── batch.py       # POST /batch
│   ├── jobs.py        # GET /jobs/{id}, DELETE /jobs/{id}
│   ├── health.py      # GET /health
│   └── events.py      # WebSocket /events (SSE)
├── models.py          # Pydantic request/response models
├── auth.py            # API key authentication
└── openapi.py         # Auto-generated OpenAPI spec
```

**Endpoints:**
```
POST   /convert/youtube      # Convert YouTube video
POST   /convert/audio        # Transcribe audio file
POST   /convert/document     # Convert document
POST   /convert/webpage      # Scrape webpage
POST   /batch                # Submit batch job
GET    /jobs/{id}            # Get job status
GET    /jobs/{id}/result     # Get job result
DELETE /jobs/{id}            # Cancel job
GET    /health               # Service health
WS     /events               # Real-time events (SSE)
GET    /openapi.json         # OpenAPI specification
```

#### MCP Server (`gobbler_mcp` - enhanced)

Keep existing MCP interface but connect to daemon:

```python
# Enhanced: MCP tools call daemon API instead of direct converters
async def transcribe_youtube(video_url: str, ...):
    """MCP tool that delegates to daemon."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:4600/convert/youtube",
            json={"video_url": video_url, ...}
        )
        return response.json()
```

#### Python SDK (`gobbler_sdk`)

```python
# New package: src/gobbler_sdk/

gobbler_sdk/
├── __init__.py
├── client.py          # GobbleClient class
├── types.py           # Type definitions
├── async_client.py    # Async version
└── exceptions.py      # SDK exceptions
```

**Usage:**
```python
from gobbler_sdk import GobbleClient

# Sync client
client = GobbleClient()
result = client.convert.youtube("https://youtube.com/watch?v=...")
print(result.markdown)

# Async client
from gobbler_sdk import AsyncGobbleClient
async with AsyncGobbleClient() as client:
    result = await client.convert.youtube("https://...")

# Batch processing with callbacks
def on_progress(job_id, progress):
    print(f"Job {job_id}: {progress}%")

batch = client.batch.youtube_playlist(
    "https://youtube.com/playlist?list=...",
    on_progress=on_progress
)
for result in batch.results():
    print(result.title)
```

#### CLI (`gobbler` command)

```bash
# Install creates 'gobbler' command
$ gobbler youtube https://youtube.com/watch?v=ABC123
# Outputs markdown to stdout

$ gobbler audio recording.mp3 -o transcript.md
# Saves to file

$ gobbler batch youtube-playlist https://... --output ./transcripts/
# Batch processing with progress bar

$ gobbler daemon start    # Start daemon
$ gobbler daemon stop     # Stop daemon
$ gobbler daemon status   # Check status
$ gobbler daemon logs     # Tail logs

$ gobbler jobs list       # List running jobs
$ gobbler jobs cancel abc # Cancel job
```

### Layer 3: Plugin System

Allow extending with new converters:

```python
# Plugin interface
class ConverterPlugin:
    """Base class for converter plugins."""

    name: str = "my-converter"
    description: str = "Converts X to markdown"

    async def convert(self, input: Any, options: dict) -> ConversionResult:
        """Perform conversion."""
        raise NotImplementedError

    def validate_input(self, input: Any) -> bool:
        """Validate input before conversion."""
        return True
```

**Plugin Discovery:**
```
~/.config/gobbler/plugins/
├── my-custom-converter/
│   ├── plugin.py
│   └── requirements.txt
└── another-plugin/
    └── plugin.py
```

---

## Inspiration Integration

### From Cloudflare Code Mode

1. **TypeScript API Generation** - Generate typed clients from OpenAPI spec:
   ```typescript
   // Auto-generated from /openapi.json
   import { GobbleClient } from '@gobbler/client';

   const client = new GobbleClient();
   const result = await client.convert.youtube({ videoUrl: '...' });
   ```

2. **Sandbox Execution** - Skills can run in isolated environments:
   ```python
   # Skill scripts execute in sandbox with limited access
   # Only gobbler daemon API available, not filesystem
   ```

3. **Binding-Based Access** - SDK provides bindings, not raw HTTP:
   ```python
   # Instead of raw requests, use typed bindings
   result = client.youtube.transcribe(url)  # Not client.post('/convert/youtube')
   ```

### From Claude Agent Skills

1. **Progressive Disclosure** - Daemon exposes capabilities progressively:
   ```json
   // GET /capabilities (lightweight, always available)
   {
     "converters": ["youtube", "audio", "document", "webpage"],
     "features": ["batch", "queue", "events"]
   }

   // GET /converters/youtube (detailed, loaded on demand)
   {
     "name": "youtube",
     "options": { "language": "string", "include_timestamps": "boolean" },
     "examples": [...],
     "rate_limits": {...}
   }
   ```

2. **Skill-Like Configuration** - Each converter has a skill-like manifest:
   ```yaml
   # ~/.config/gobbler/converters/youtube.yml
   name: youtube
   description: Extract transcripts from YouTube videos
   version: 1.0.0

   options:
     language:
       type: string
       default: auto
     include_timestamps:
       type: boolean
       default: false

   providers:
     - name: official
       priority: 1
     - name: transcriptapi
       priority: 2
       requires_key: true
   ```

3. **Scripts as First-Class** - Standalone scripts work without daemon:
   ```bash
   # Direct script execution (no daemon needed)
   $ python -m gobbler_core.converters.youtube https://...

   # Through daemon (full features: queue, events, caching)
   $ gobbler youtube https://...
   ```

---

## Implementation Roadmap

### Phase 1: Daemon Foundation
- [ ] Create `gobbler_daemon` package
- [ ] Implement daemon lifecycle (start/stop/status)
- [ ] Add launchd plist for macOS auto-start
- [ ] Migrate relay server into daemon
- [ ] Unified logging and metrics

### Phase 2: REST API
- [ ] Create `gobbler_api` with FastAPI
- [ ] Implement conversion endpoints
- [ ] Add job management endpoints
- [ ] WebSocket events for progress
- [ ] OpenAPI spec generation
- [ ] API key authentication

### Phase 3: SDK & CLI
- [ ] Create `gobbler_sdk` Python client
- [ ] Generate TypeScript client from OpenAPI
- [ ] Build `gobbler` CLI with click/typer
- [ ] Shell completions (bash, zsh, fish)
- [ ] Progress bars for batch operations

### Phase 4: Plugin System
- [ ] Define plugin interface
- [ ] Plugin discovery and loading
- [ ] Plugin isolation (optional sandboxing)
- [ ] Plugin marketplace/registry concept

### Phase 5: Enhanced MCP
- [ ] Update MCP tools to use daemon API
- [ ] Add MCP resources (expose capabilities)
- [ ] SSE transport for remote access
- [ ] MCP-over-HTTP bridge

---

## Configuration

### Unified Config (`~/.config/gobbler/config.yml`)

```yaml
daemon:
  port: 4600
  auto_start: true
  log_level: info
  pid_file: ~/.config/gobbler/gobbler.pid

api:
  enabled: true
  auth:
    enabled: false  # Enable for production
    api_keys:
      - name: default
        key: ${GOBBLER_API_KEY}

mcp:
  enabled: true
  transport: stdio  # or sse

converters:
  youtube:
    enabled: true
    providers:
      - official
      - transcriptapi
  audio:
    enabled: true
    model: small
  document:
    enabled: true
    ocr: true
  webpage:
    enabled: true
    timeout: 30

services:
  crawl4ai:
    enabled: true
    url: http://localhost:11235
  docling:
    enabled: true
    url: http://localhost:5001
  redis:
    enabled: true
    url: redis://localhost:6380

plugins:
  directory: ~/.config/gobbler/plugins
  enabled: true
```

---

## Usage Examples

### Shell Automation

```bash
#!/bin/bash
# Convert all videos from a channel

gobbler batch youtube-channel "https://youtube.com/@channel" \
  --output ./transcripts/ \
  --format json \
  --concurrency 3 \
  | jq '.results[] | select(.success) | .file'
```

### macOS Shortcuts Integration

```bash
# Create Shortcut that calls:
curl -X POST http://localhost:4600/convert/youtube \
  -H "Content-Type: application/json" \
  -d '{"video_url": "{{clipboard}}", "output_format": "markdown"}'
```

### n8n/Zapier Webhook

```json
{
  "url": "http://localhost:4600/convert/webpage",
  "method": "POST",
  "body": {
    "url": "{{trigger.url}}",
    "css_selector": "article"
  }
}
```

### Python Script

```python
#!/usr/bin/env python3
from gobbler_sdk import GobbleClient
import sys

client = GobbleClient()
url = sys.argv[1]

if "youtube.com" in url:
    result = client.convert.youtube(url)
elif url.endswith(".pdf"):
    result = client.convert.document(url)
else:
    result = client.convert.webpage(url)

print(result.markdown)
```

### Claude Code / Agent SDK

```python
# Skills can use SDK directly
from gobbler_sdk import GobbleClient

client = GobbleClient()

# In skill execution
def execute_skill(url: str) -> str:
    result = client.convert.auto(url)  # Auto-detect type
    return result.markdown
```

---

## File Structure (Proposed)

```
src/
├── gobbler_core/           # Existing - unchanged
│   ├── converters/
│   ├── providers/
│   └── utils/
│
├── gobbler_daemon/         # NEW - daemon process
│   ├── daemon.py
│   ├── config.py
│   ├── events.py
│   ├── plugins.py
│   └── health.py
│
├── gobbler_api/            # NEW - REST API
│   ├── server.py
│   ├── routes/
│   ├── models.py
│   └── auth.py
│
├── gobbler_sdk/            # NEW - Python SDK
│   ├── client.py
│   ├── async_client.py
│   └── types.py
│
├── gobbler_cli/            # NEW - CLI interface
│   ├── main.py
│   ├── commands/
│   └── output.py
│
├── gobbler_mcp/            # Existing - enhanced
│   └── ...
│
└── gobbler_relay/          # Existing - integrated into daemon
    └── ...

pyproject.toml              # Multiple entry points
├── [project.scripts]
│   ├── gobbler = "gobbler_cli:main"
│   ├── gobbler-daemon = "gobbler_daemon:main"
│   └── gobbler-mcp = "gobbler_mcp:main"
```

---

## Benefits

1. **Universal Access** - Use from any language, tool, or automation
2. **Always Running** - Daemon handles long jobs even after client disconnects
3. **Event-Driven** - Subscribe to conversion events for reactive workflows
4. **Plugin Ecosystem** - Community can extend with new converters
5. **Production Ready** - Auth, rate limiting, health checks built-in
6. **AI-Native** - Works with Claude Code, Agent SDK, and any MCP client
7. **Developer Friendly** - Type-safe SDKs, OpenAPI spec, shell completions

---

## Migration Path

1. **Phase 1**: Daemon runs alongside existing MCP server
2. **Phase 2**: MCP server connects to daemon (optional)
3. **Phase 3**: MCP server fully integrated into daemon
4. **Phase 4**: Single `gobbler daemon start` runs everything

Existing MCP users see no breaking changes - just new capabilities.

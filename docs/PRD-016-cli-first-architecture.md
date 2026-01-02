# PRD-016: CLI-First Architecture Migration

## Executive Summary

Migrate Gobbler from an MCP-centric architecture to a **CLI-first architecture** where:
1. The CLI (`gobbler`) is the core fabric through which all features flow
2. MCP tools become thin wrappers around CLI commands (for Claude Desktop compatibility)
3. Skills document CLI usage (for Claude Code/OpenCode)
4. A new SQLite-based queue system replaces Redis/RQ for job management
5. The relay daemon auto-starts when browser commands are invoked

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Interfaces                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │ Claude Desktop  │  │ Claude Code     │  │ OpenCode       │  │
│  │ (MCP Tools)     │  │ (Skills)        │  │ (Skills)       │  │
│  └────────┬────────┘  └────────┬────────┘  └───────┬────────┘  │
│           │                    │                    │           │
│           ▼                    ▼                    ▼           │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              CLI (`gobbler` commands)                       ││
│  │  The core fabric - all features flow through here           ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│           ┌──────────────────┼──────────────────┐               │
│           ▼                  ▼                  ▼               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │ gobbler_core │  │ gobbler_relay│  │ gobbler_queue    │      │
│  │ (converters) │  │ (browser)    │  │ (SQLite jobs)    │      │
│  └──────────────┘  └──────────────┘  └──────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Create SQLite Queue System

### Goal
Replace Redis/RQ with a lightweight SQLite-based queue that can handle hundreds to thousands of jobs.

### New Package: `gobbler_queue`

```
src/gobbler_queue/
├── __init__.py
├── models.py          # Job, JobStatus, JobResult dataclasses
├── database.py        # SQLite connection and schema management
├── manager.py         # JobManager: create, update, query jobs
├── worker.py          # Background worker process
└── cli_integration.py # Helpers for CLI --queue flag
```

### Database Schema

```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,           -- youtube, audio, document, webpage, batch
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed, cancelled
    command TEXT NOT NULL,            -- Full CLI command to execute
    args_json TEXT,                   -- JSON serialized arguments
    progress INTEGER DEFAULT 0,       -- 0-100
    progress_message TEXT,            -- Current status message
    result_json TEXT,                 -- JSON serialized result
    error TEXT,                       -- Error message if failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    worker_pid INTEGER                -- PID of worker process
);

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created ON jobs(created_at);
```

### Acceptance Criteria

- [ ] `gobbler_queue` package created with all modules
- [ ] SQLite database stored at `~/.local/share/gobbler/jobs.db`
- [ ] `JobManager.create_job(command, args)` returns job ID
- [ ] `JobManager.get_job(job_id)` returns job status and result
- [ ] `JobManager.list_jobs(status_filter, limit)` returns job list
- [ ] `JobManager.cancel_job(job_id)` cancels running job (sends SIGTERM to worker)
- [ ] `JobManager.clear_jobs(status_filter)` deletes jobs by status
- [ ] Background worker can execute CLI commands via subprocess
- [ ] Worker updates progress by parsing CLI output (requires CLI progress format)
- [ ] Worker handles graceful shutdown on SIGTERM
- [ ] Unit tests for all JobManager methods
- [ ] Integration test: queue job, worker executes, status updates correctly

### CLI Integration

Add `--queue` flag to conversion commands:

```bash
# Queue a YouTube transcription
gobbler youtube https://... --queue
# Output: Job queued: job_abc123

# Check status
gobbler jobs get job_abc123
# Output: status: running, progress: 45%, message: "Downloading transcript..."

# List all jobs
gobbler jobs list
# Output: table of jobs

# Cancel job
gobbler jobs cancel job_abc123
```

---

## Phase 2: Complete CLI Gaps

### Goal
Add missing CLI commands that currently only exist as MCP tools.

### New Commands

| Command | Description | Priority |
|---------|-------------|----------|
| `gobbler batch webpages <file>` | Batch process URLs from file | High |
| `gobbler crawl <url>` | Crawl website recursively | Medium |
| `gobbler session create` | Create authenticated crawl session | Low |
| `gobbler download youtube <url>` | Download YouTube video file | Medium |

### Acceptance Criteria

#### `gobbler batch webpages`
- [ ] Reads URLs from file (one per line) or stdin
- [ ] Supports `--output-dir`, `--concurrency`, `--timeout` options
- [ ] Supports `--queue` flag for background execution
- [ ] Shows progress with success/failure counts
- [ ] Generates batch summary report

#### `gobbler crawl`
- [ ] Crawls URL with `--max-depth` (default 3) and `--max-pages` (default 100)
- [ ] Supports `--output-dir` for saving pages
- [ ] Supports `--include-pattern` and `--exclude-pattern` for URL filtering
- [ ] Outputs link graph as JSON with `--graph` flag
- [ ] Shows real-time crawl progress

#### `gobbler session create`
- [ ] Creates named session with cookies/localStorage
- [ ] Interactive browser opens for login if needed
- [ ] Session stored in `~/.local/share/gobbler/sessions/`
- [ ] Sessions can be used with `--session <name>` in crawl/webpage commands

#### `gobbler download youtube`
- [ ] Downloads video to specified output path
- [ ] Supports `--format` (mp4, webm, audio-only)
- [ ] Supports `--quality` (best, 1080p, 720p, etc.)
- [ ] Shows download progress

### Enhanced Batch Commands
- [ ] Add `--queue` flag to `gobbler batch youtube-playlist`
- [ ] Add `--queue` flag to `gobbler batch directory`
- [ ] Add `gobbler batch progress <batch_id>` command

---

## Phase 3: Simplify MCP to Thin CLI Wrappers

### Goal
Convert MCP tools from direct implementations to thin wrappers that invoke CLI commands.

### Pattern

**Before (current):**
```python
@mcp.tool()
async def transcribe_youtube(video_url: str, language: str = "en", ...) -> str:
    # 50+ lines of direct implementation
    result = await convert_youtube_to_markdown(video_url, ...)
    return result
```

**After (CLI wrapper):**
```python
@mcp.tool()
async def transcribe_youtube(video_url: str, language: str = "en", ...) -> str:
    """Transcribe YouTube video to markdown."""
    cmd = ["gobbler", "youtube", video_url, "--language", language, "--format", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ToolError(result.stderr)
    return json.loads(result.stdout)["markdown"]
```

### Tools to Convert

| MCP Tool | CLI Command |
|----------|-------------|
| `transcribe_youtube` | `gobbler youtube <url>` |
| `fetch_webpage` | `gobbler webpage <url>` |
| `fetch_webpage_with_selector` | `gobbler webpage <url> --selector <sel>` |
| `convert_document` | `gobbler document <file>` |
| `transcribe_audio` | `gobbler audio <file>` |
| `batch_transcribe_youtube_playlist` | `gobbler batch youtube-playlist <url>` |
| `batch_fetch_webpages` | `gobbler batch webpages <file>` |
| `batch_transcribe_directory` | `gobbler batch directory <dir>` |
| `batch_convert_documents` | `gobbler batch directory <dir> --type document` |
| `get_batch_progress` | `gobbler batch progress <id>` |
| `browser_check_connection` | `gobbler browser status` |
| `browser_list_tabs` | `gobbler browser list` |
| `browser_execute_script` | `gobbler browser exec <script>` |
| `browser_extract_current_page` | `gobbler browser extract` |
| `get_job_status` | `gobbler jobs get <id>` |
| `list_jobs` | `gobbler jobs list` |
| `crawl_site` | `gobbler crawl <url>` |
| `create_crawl_session` | `gobbler session create` |
| `download_youtube_video` | `gobbler download youtube <url>` |

### Acceptance Criteria

- [ ] All MCP tools use subprocess to call CLI commands
- [ ] Each MCP tool is <20 lines of code
- [ ] CLI commands support `--format json` for machine-readable output
- [ ] Error messages from CLI are properly propagated to MCP
- [ ] MCP server can start without any external services (lazy loading)
- [ ] Integration tests verify MCP tools produce same output as direct CLI

### CLI JSON Output Format

All commands should support `--format json`:

```json
{
  "success": true,
  "markdown": "# Title\n\n...",
  "metadata": {
    "source": "https://...",
    "word_count": 1234,
    "conversion_time_ms": 567
  }
}
```

Or for errors:
```json
{
  "success": false,
  "error": "Failed to connect to service",
  "error_code": "SERVICE_UNAVAILABLE"
}
```

---

## Phase 4: Update Skills to CLI-First Approach

### Goal
Skills become documentation + CLI invocation patterns, with optional helper scripts for complex Python operations.

### Skill Structure

```
skills/gobbler-youtube/
├── SKILL.md              # Primary documentation
└── scripts/
    └── helpers.py        # Optional: complex operations easier in Python
```

### SKILL.md Template

```markdown
---
name: gobbler-youtube
description: Transcribe YouTube videos to markdown. Use when user shares a YouTube URL or asks to transcribe a video.
---

# YouTube Transcription

## Quick Usage

```bash
gobbler youtube <url>
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-o, --output` | Save to file | stdout |
| `-l, --language` | Preferred language | en |
| `--timestamps/--no-timestamps` | Include timestamps | false |
| `--queue` | Run in background | false |

## Batch Processing

For playlists:
```bash
gobbler batch youtube-playlist <url> -o ./transcripts
```

## Background Jobs

Queue a job and check status:
```bash
gobbler youtube <url> --queue
# Returns: Job queued: job_abc123

gobbler jobs get job_abc123
```

## Examples

### Transcribe single video
```bash
gobbler youtube "https://youtube.com/watch?v=..." -o transcript.md
```

### Transcribe playlist with timestamps
```bash
gobbler batch youtube-playlist "https://youtube.com/playlist?..." \
  -o ./transcripts \
  --timestamps \
  --concurrency 5
```
```

### Acceptance Criteria

- [ ] Remove `allowed-tools` from all SKILL.md files
- [ ] Each skill documents CLI commands, not MCP tools
- [ ] Skills include common examples and use cases
- [ ] Optional helper scripts only for operations easier in Python
- [ ] Consistent SKILL.md format across all skills
- [ ] Skills tested with OpenCode skill loading

### Skills to Update

| Skill | Changes |
|-------|---------|
| `gobbler-youtube` | Document CLI, remove MCP references |
| `gobbler-webpage` | Document CLI, remove MCP references |
| `gobbler-document` | Document CLI, remove MCP references |
| `gobbler-audio` | Document CLI, remove MCP references |
| `gobbler-browser` | Document CLI, simplify |
| `notebooklm` | Document CLI, consolidate scripts |
| `gobbler-batch` | NEW: Create batch operations skill |
| `gobbler-utils` | Keep as-is (Python helpers) |

---

## Phase 5: Simplify Browser/Relay System

### Goal
- Relay daemon auto-starts when browser commands are invoked
- Consolidate browser commands
- Simplify NotebookLM integration

### Relay Auto-Start

When any `gobbler browser` or `gobbler notebooklm` command runs:
1. Check if relay is running via health check
2. If not, start relay daemon in background
3. Wait for relay to become healthy (max 5 seconds)
4. Proceed with command

```python
async def ensure_relay():
    """Ensure relay is running, start if needed."""
    if await is_relay_healthy():
        return True
    
    # Start daemon
    start_relay_daemon()
    
    # Wait for healthy
    for _ in range(10):
        await asyncio.sleep(0.5)
        if await is_relay_healthy():
            return True
    
    raise RuntimeError("Failed to start relay daemon")
```

### Simplified Browser Commands

Consolidate to essential commands:

| Command | Description |
|---------|-------------|
| `gobbler browser status` | Check extension connection |
| `gobbler browser tabs` | List tabs (rename from `list`) |
| `gobbler browser extract` | Extract current page as markdown |
| `gobbler browser exec <script>` | Execute JavaScript |
| `gobbler browser open <urls...>` | Open URLs in new tabs |

Remove:
- `gobbler browser navigate` (use `open` instead)

### Simplified NotebookLM Commands

| Command | Description |
|---------|-------------|
| `gobbler notebooklm list` | List NotebookLM tabs |
| `gobbler notebooklm query <message>` | Send query to NotebookLM |
| `gobbler notebooklm info` | Get notebook info |
| `gobbler notebooklm history` | Get chat history |

Remove:
- `gobbler notebooklm last` (redundant with history)

### Acceptance Criteria

- [ ] Relay auto-starts on any browser/notebooklm command
- [ ] Relay daemon managed via pidfile at `~/.cache/gobbler/relay.pid`
- [ ] `gobbler browser status` shows relay status and extension connection
- [ ] Consolidate duplicate NotebookLM scripts (per PRD-014)
- [ ] Browser skill documents CLI commands only
- [ ] NotebookLM skill documents CLI commands only
- [ ] Auto-shutdown relay after 4 hours of inactivity (already implemented)

---

## Phase 6: Cleanup and Delete Unnecessary Components

### Goal
Remove redundant code and simplify the codebase.

### Components to Delete

| Component | Reason |
|-----------|--------|
| `src/gobbler_mcp/converters/` | Redundant with `gobbler_core` |
| `src/gobbler_mcp/batch/` | Moved to `gobbler_queue` + CLI |
| `src/gobbler_mcp/crawlers/` | Functionality in CLI |
| `src/gobbler_api/` | Not needed, CLI covers this |
| `src/gobbler_mcp/config_watcher.py` | Simplify config |
| Duplicate skill scripts | Consolidate to single location |

### Components to Keep

| Component | Reason |
|-----------|--------|
| `src/gobbler_core/` | Core converters and utilities |
| `src/gobbler_relay/` | Browser extension communication |
| `src/gobbler_queue/` | NEW: Job queue system |
| `src/gobbler_cli/` | Primary interface |
| `src/gobbler_mcp/` | Thin wrappers (greatly simplified) |
| `browser-extension/` | Browser integration |
| `skills/` | Claude Code/OpenCode integration |

### Estimated Code Reduction

| Package | Before | After | Reduction |
|---------|--------|-------|-----------|
| `gobbler_mcp` | ~3,500 lines | ~500 lines | 85% |
| `gobbler_api` | ~500 lines | 0 lines | 100% |
| Skills scripts | ~2,000 lines | ~500 lines | 75% |

### Acceptance Criteria

- [ ] `gobbler_api` package deleted
- [ ] `gobbler_mcp/converters/` deleted
- [ ] `gobbler_mcp/batch/` deleted  
- [ ] `gobbler_mcp/crawlers/` deleted
- [ ] Duplicate skill scripts consolidated
- [ ] All tests pass after cleanup
- [ ] Documentation updated to reflect new architecture
- [ ] CHANGELOG updated with breaking changes

---

## Testing Strategy

### Unit Tests
- `gobbler_queue` package: 100% coverage on manager and database
- CLI commands: test JSON output format
- MCP wrappers: mock subprocess calls

### Integration Tests
- Queue workflow: create job → worker executes → status updates
- CLI to MCP: verify MCP tools produce same output as CLI
- Relay auto-start: verify daemon starts on browser commands

### E2E Tests
- Full workflow: skill → CLI → queue → worker → result
- Browser workflow: skill → CLI → relay → extension → result

---

## Migration Guide

### For Users

**Before:**
```json
// claude_desktop_config.json
{
  "mcpServers": {
    "gobbler-mcp": {
      "command": "uvx",
      "args": ["gobbler-mcp"]
    }
  }
}
```

**After:**
No changes needed - MCP still works, just thinner.

### For Skill Users

Skills now document CLI commands instead of MCP tools. Usage patterns are the same, but documentation references CLI.

### Breaking Changes

1. Redis/RQ no longer used for job queue (SQLite instead)
2. `gobbler_api` REST server removed
3. Some MCP tool options may differ slightly from CLI

---

## Success Metrics

1. **Code Simplicity**: 50%+ reduction in `gobbler_mcp` lines of code
2. **Feature Parity**: 100% of MCP features available via CLI
3. **Job System**: SQLite queue handles 1000+ jobs without issues
4. **Startup Time**: MCP server starts in <1 second (no Redis dependency)
5. **Test Coverage**: 80%+ coverage on new `gobbler_queue` package

---

## Implementation Order

1. **Phase 2: SQLite Queue** - Foundation for job management
2. **Phase 1: CLI Gaps** - Complete CLI feature set
3. **Phase 5: Relay Auto-Start** - Simplify browser workflow
4. **Phase 3: MCP Wrappers** - Thin CLI wrappers
5. **Phase 4: Skills Update** - Document CLI usage
6. **Phase 6: Cleanup** - Remove redundant code

Each phase should have its own commit with clear commit message.

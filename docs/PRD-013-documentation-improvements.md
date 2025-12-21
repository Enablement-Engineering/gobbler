# PRD-013: Documentation Improvements

## Overview
**Epic**: Developer Experience  
**Phase**: Documentation  
**Status**: Pending  
**Effort**: 2-3 days  
**Dependencies**: None  
**Priority**: Medium  

## Problem Statement

While the documentation is generally good (rated 8.5/10), there are several gaps and inconsistencies:

### Critical Gaps

1. **API.md is incomplete**: Missing 15+ MCP tools including:
   - `download_youtube_video`
   - `create_crawl_session`
   - `crawl_site`
   - All batch tools (`batch_*`)
   - All browser tools (`browser_*`)
   - Queue tools (`get_job_status`, `list_jobs`)

2. **config.example.yml is incomplete**: Missing sections for:
   - Redis configuration
   - Queue settings
   - Monitoring settings
   - HTTP server (relay) settings

3. **gobbler_core package undocumented**: No README or documentation for the shared core package

### Inconsistencies

1. **Outdated references**:
   - Port 4625 historical note should be removed
   - References to `make verify` and `make diagnose` that don't exist
   - Path inconsistencies (`skills/gobbler-*/scripts/` vs `skills/*/scripts/`)

2. **Type hint documentation mismatch**:
   - `title: str = None` should be `Optional[str] = None` in docstrings and code

3. **Missing version tracking in SKILL.md files**:
   - Only `notebooklm` has a version field
   - Other skills have no versioning

## Success Criteria

- [ ] API.md documents all 25+ MCP tools
- [ ] config.example.yml includes all configuration sections
- [ ] gobbler_core has package README
- [ ] All outdated references removed
- [ ] SKILL.md files have consistent format
- [ ] Type hints fixed in documentation and code

## Technical Requirements

### 1. Complete API.md

Add missing tool documentation following existing format:

```markdown
## Browser Tools

### browser_check_connection
Check if browser extension is connected.

**Parameters:** None

**Returns:** Connection status message

**Example:**
```json
{
  "tool": "browser_check_connection"
}
```

### browser_navigate_to_url
Navigate browser to specified URL.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| url | string | Yes | - | Full URL to navigate to |
| wait_for_load | boolean | No | true | Wait for page load |

**Returns:** Success message with URL

### browser_execute_script
Execute JavaScript in active tab.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| script | string | Yes | - | JavaScript code |
| timeout | integer | No | 30 | Timeout in seconds |

**Returns:** JSON result of script execution

### browser_list_tabs
List tabs in Gobbler tab group.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| filter | string | No | - | Filter pattern (e.g., 'notebooklm') |

**Returns:** JSON list of tabs

### browser_execute_script_in_tab
Execute JavaScript in specific tab.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| tab_id | integer | Yes | - | Target tab ID |
| script | string | Yes | - | JavaScript code |
| timeout | integer | No | 30 | Timeout in seconds |

**Returns:** JSON result of script execution

### browser_extract_current_page
Extract current page as markdown.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| selector | string | No | - | CSS selector for content |

**Returns:** Markdown with YAML frontmatter

---

## Crawl Tools

### crawl_site
Recursively crawl website.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| start_url | string | Yes | - | Starting URL |
| max_depth | integer | No | 2 | Maximum crawl depth |
| max_pages | integer | No | 50 | Maximum pages |
| url_include_pattern | string | No | - | Regex to include |
| url_exclude_pattern | string | No | - | Regex to exclude |
| css_selector | string | No | - | Extract with selector |
| respect_robots_txt | boolean | No | true | Follow robots.txt |
| crawl_delay | float | No | 1.0 | Delay between requests |
| concurrency | integer | No | 3 | Concurrent requests |
| session_id | string | No | - | Session for auth |
| output_dir | string | No | - | Save directory |

**Returns:** Crawl summary with statistics

### create_crawl_session
Create authenticated crawl session.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| session_id | string | Yes | - | Unique session ID |
| cookies | string | No | - | JSON cookie array |
| local_storage | string | No | - | JSON localStorage |
| user_agent | string | No | - | Custom user agent |

**Returns:** Session creation confirmation

---

## Queue Tools

### get_job_status
Check queued job status.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| job_id | string | Yes | - | Job ID |

**Returns:** Job status and result

### list_jobs
List jobs in queue.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| queue_name | string | No | default | Queue name |
| limit | integer | No | 20 | Max jobs to return |

**Returns:** List of jobs with status

---

## Download Tools

### download_youtube_video
Download YouTube video to file.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| video_url | string | Yes | - | YouTube URL |
| output_dir | string | Yes | - | Output directory |
| quality | string | No | best | Video quality |
| format | string | No | mp4 | Output format |
| auto_queue | boolean | No | false | Queue if long |

**Returns:** Path to downloaded file
```

### 2. Complete config.example.yml

Add missing configuration sections:

```yaml
# Redis queue settings (for background jobs)
redis:
  host: localhost
  port: 6380          # Non-standard port to avoid conflicts
  db: 0
  password: null      # Set for production

# Queue settings
queue:
  auto_queue_threshold: 105  # seconds (1:45) - queue if longer
  default_queue: default
  job_timeout: 600    # 10 minutes max job time

# Monitoring settings
monitoring:
  metrics_enabled: false      # Enable Prometheus metrics
  metrics_port: 9090          # Metrics HTTP server port
  log_format: text            # 'text' or 'json'
  log_level: INFO             # DEBUG, INFO, WARNING, ERROR

# HTTP server for browser extension relay
relay:
  enabled: true
  host: "127.0.0.1"
  port: 4625
  auto_shutdown_timeout: 14400  # 4 hours of inactivity
```

### 3. Create gobbler_core README

Create `src/gobbler_core/README.md`:

```markdown
# gobbler_core

Shared, portable core library for Gobbler content conversion.

## Overview

`gobbler_core` provides standalone converters and utilities that can be used
independently of the MCP server. This package has no MCP dependencies and
can be used in any Python application.

## Modules

### Converters

- `audio.py` - Audio/video transcription with Whisper
- `document.py` - Document conversion via Docling
- `webpage.py` - Webpage conversion via Crawl4AI
- `youtube.py` - YouTube transcript extraction

### Providers

- `youtube.py` - YouTube transcript API providers with fallback chain

### Utilities

- `file_handler.py` - File validation and saving
- `frontmatter.py` - YAML frontmatter generation
- `health.py` - Service health checking
- `http_client.py` - Retryable HTTP client

## Usage

```python
from gobbler_core.converters import convert_youtube_to_markdown

# Convert YouTube video to markdown
markdown, metadata = await convert_youtube_to_markdown(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    include_timestamps=True
)
```

## Architecture

This package is designed to be:
- **Standalone**: No MCP or server dependencies
- **Portable**: Can be used in skills, scripts, or other applications
- **Testable**: All external services are mockable

The `gobbler_mcp` package re-exports from this package and adds MCP-specific
functionality.
```

### 4. Standardize SKILL.md Format

Update all SKILL.md files to include version and consistent sections:

```yaml
---
name: gobbler-audio
description: Transcribe audio and video files using Whisper
version: 1.0.0
---

# Gobbler Audio Skill

## Overview
[Brief description]

## Prerequisites
- Docker (for Whisper model)
- OR local faster-whisper installation

## Usage
[Examples with code blocks]

## Parameters
[Table of parameters]

## Examples
[2-3 examples with expected output]

## Troubleshooting
[Common issues and solutions]
```

### 5. Fix Type Hints

Fix the `str = None` pattern throughout the codebase:

```python
# Before (incorrect)
def create_youtube_frontmatter(
    title: str = None,
    channel: str = None,
)

# After (correct)
from typing import Optional

def create_youtube_frontmatter(
    title: Optional[str] = None,
    channel: Optional[str] = None,
)
```

Files to update:
- `src/gobbler_core/utils/frontmatter.py` (lines 67-70)
- `src/gobbler_mcp/utils/frontmatter.py` (lines 67-70)

### 6. Remove Outdated References

| Location | Issue | Fix |
|----------|-------|-----|
| README.md | Port 4625 historical note | Remove note about "old 4624" |
| QUICK_START.md | `make verify`, `make diagnose` | Remove or add to Makefile |
| Various docs | Path inconsistency | Standardize to `skills/*/scripts/` |

## Implementation Plan

### Phase 1: API.md Update (Day 1)
- Document browser tools (6 tools)
- Document crawl tools (2 tools)
- Document queue tools (2 tools)
- Document download tools (1 tool)
- Document remaining batch tools

### Phase 2: Configuration Docs (Day 1)
- Complete config.example.yml
- Add .env.example variables

### Phase 3: Package Documentation (Day 2)
- Create gobbler_core README
- Update gobbler_relay README if needed

### Phase 4: Cleanup (Day 2-3)
- Fix type hints in frontmatter.py
- Standardize SKILL.md files
- Remove outdated references
- Verify all links work

## Files to Create

```
src/gobbler_core/README.md           # Package documentation
```

## Files to Modify

```
API.md                               # Add 15+ missing tools
config/config.example.yml            # Add missing sections
.env.example                         # Add missing variables
src/gobbler_core/utils/frontmatter.py   # Fix type hints
src/gobbler_mcp/utils/frontmatter.py    # Fix type hints
skills/*/SKILL.md                    # Add version, standardize format
README.md                            # Remove outdated references
docs/QUICK_START.md                  # Fix Makefile references
```

## Acceptance Criteria

### Completeness
- [ ] API.md documents all MCP tools
- [ ] config.example.yml has all sections
- [ ] gobbler_core has README
- [ ] All SKILL.md files have version

### Accuracy
- [ ] All documented tools match implementation
- [ ] All config options match code defaults
- [ ] Type hints are correct (Optional[str])
- [ ] No outdated references

### Consistency
- [ ] SKILL.md files follow same format
- [ ] Path references consistent
- [ ] Code examples tested and working

## Definition of Done

- [ ] API.md complete with all 25+ tools
- [ ] Configuration documentation complete
- [ ] Package READMEs created
- [ ] Type hints fixed
- [ ] Outdated references removed
- [ ] SKILL.md files standardized
- [ ] All documentation links verified
- [ ] PR reviewed and merged

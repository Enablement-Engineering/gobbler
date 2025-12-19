# PRD-009: server.py Modularization

## Overview
**Epic**: Code Quality & Maintainability
**Phase**: Refactoring
**Dependencies**: PRD-007, PRD-008 - documentation should be stable first
**Parallel**: No - significant refactoring requires focused attention

## Problem Statement

`src/gobbler_mcp/server.py` has grown to 1,972 lines with 21 tools, creating maintenance challenges:

1. **Monolithic structure**: All tools defined in single file, hard to navigate
2. **Duplicated error handling**: 29 similar try/except blocks not abstracted
3. **Inline task functions**: 6 `_task()` functions mix queue logic with tool definitions
4. **Inconsistent patterns**: Some tools use `asyncio.to_thread()`, others don't
5. **Magic numbers scattered**: Hardcoded limits like `max_depth > 5`, `timeout > 120`
6. **No tool categorization**: All 21 tools at same level, no semantic grouping

This makes the codebase hard to maintain, test, and extend.

## Success Criteria

- [ ] server.py reduced to <500 lines (registration and lifespan only)
- [ ] Tools organized into categorical modules
- [ ] Common error handling extracted to decorator
- [ ] Task functions moved to appropriate modules
- [ ] Magic numbers replaced with constants
- [ ] All existing tests still pass
- [ ] No functionality regression

## Technical Requirements

### 1. Target Directory Structure

```
src/gobbler_mcp/
├── server.py                    # <500 lines: lifespan, registration
├── constants.py                 # Magic numbers → named constants
├── decorators.py                # Error handling decorator
├── tools/
│   ├── __init__.py              # Tool exports
│   ├── conversion.py            # Single-file conversion tools (5)
│   ├── batch.py                 # Batch processing tools (4)
│   ├── browser.py               # Browser automation tools (7)
│   ├── queue.py                 # Job management tools (2)
│   └── crawl.py                 # Crawling tools (3)
├── converters/                  # Existing - no changes
├── batch/                       # Existing - no changes
├── crawlers/                    # Existing - no changes
├── providers/                   # Existing - no changes
└── utils/                       # Existing - no changes
```

### 2. Tool Categories

| Category | Module | Tools | Lines (est.) |
|----------|--------|-------|--------------|
| Conversion | `tools/conversion.py` | transcribe_youtube, fetch_webpage, fetch_webpage_with_selector, convert_document, transcribe_audio | ~400 |
| Batch | `tools/batch.py` | batch_transcribe_youtube_playlist, batch_fetch_webpages, batch_transcribe_directory, batch_convert_documents | ~350 |
| Browser | `tools/browser.py` | browser_check_connection, browser_navigate, browser_execute_script, browser_execute_script_in_tab, browser_extract_page, browser_list_tabs, get_batch_progress | ~300 |
| Queue | `tools/queue.py` | get_job_status, list_jobs | ~100 |
| Crawl | `tools/crawl.py` | create_crawl_session, crawl_site, download_youtube_video | ~250 |

### 3. Error Handling Decorator

Extract common error handling pattern:

```python
# src/gobbler_mcp/decorators.py
from functools import wraps
from typing import Callable, Any
import httpx
from .logging_config import get_logger

logger = get_logger(__name__)

def handle_tool_errors(
    operation_name: str,
    service_name: str | None = None
) -> Callable:
    """
    Decorator for consistent MCP tool error handling.

    Args:
        operation_name: Human-readable operation name for error messages
        service_name: Optional service name for connection error messages
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> str:
            try:
                return await func(*args, **kwargs)
            except httpx.ConnectError as e:
                service_msg = f" Is {service_name} running?" if service_name else ""
                logger.error(f"Connection error in {operation_name}: {e}")
                return f"Connection failed: {e}.{service_msg}"
            except ValueError as e:
                logger.warning(f"Validation error in {operation_name}: {e}")
                return str(e)
            except FileNotFoundError as e:
                logger.error(f"File not found in {operation_name}: {e}")
                return f"File not found: {e}"
            except Exception as e:
                logger.error(f"Unexpected error in {operation_name}: {e}", exc_info=True)
                return f"Failed to {operation_name}: {str(e)}"
        return wrapper
    return decorator
```

Usage:
```python
# src/gobbler_mcp/tools/conversion.py
from ..decorators import handle_tool_errors

@mcp.tool()
@handle_tool_errors("transcribe YouTube video", "YouTube API")
async def transcribe_youtube(
    video_url: str,
    include_timestamps: bool = False,
    language: str = "auto",
    output_file: str | None = None
) -> str:
    # Clean implementation without try/except boilerplate
    ...
```

### 4. Constants Module

```python
# src/gobbler_mcp/constants.py

# Crawling limits
MAX_CRAWL_DEPTH = 5
MAX_PAGES_PER_CRAWL = 500
MAX_VIDEOS_PER_PLAYLIST = 500

# Timeout limits (seconds)
MIN_TIMEOUT = 5
MAX_TIMEOUT = 120
DEFAULT_TIMEOUT = 30

# Queue thresholds
AUTO_QUEUE_VIDEO_THRESHOLD = 10
AUTO_QUEUE_URL_THRESHOLD = 10
AUTO_QUEUE_FILE_THRESHOLD = 10
AUTO_QUEUE_SIZE_THRESHOLD_MB = 500

# Batch processing
MAX_BATCH_CONCURRENCY = 10
DEFAULT_BATCH_CONCURRENCY = 5
DEFAULT_CRAWL_DELAY = 1.0
DEFAULT_JITTER_RANGE = 1.0

# Retry configuration
MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
```

### 5. Refactored server.py Structure

```python
# src/gobbler_mcp/server.py (~400 lines)
"""
Gobbler MCP Server - Main entry point.

This module handles server lifecycle and tool registration.
Tool implementations are in the tools/ subpackage.
"""

from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP

from .config import get_config, enable_hot_reload, disable_hot_reload
from .logging_config import setup_logging, get_logger
from .metrics_server import start_metrics_server, stop_metrics_server
from .utils.health import check_service_health

# Import tool modules for registration
from .tools import conversion, batch, browser, queue, crawl

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(server: FastMCP):
    """Server lifecycle management."""
    config = get_config()
    setup_logging(config)

    logger.info("Starting Gobbler MCP server...")

    # Start metrics if enabled
    metrics_server = None
    if config.monitoring.metrics_enabled:
        metrics_server = await start_metrics_server()

    # Enable config hot-reload
    enable_hot_reload()

    # Health checks
    await check_service_health()

    yield

    # Cleanup
    disable_hot_reload()
    if metrics_server:
        await stop_metrics_server(metrics_server)

    logger.info("Gobbler MCP server stopped")


# Create server instance
mcp = FastMCP(
    "gobbler-mcp",
    description="Content conversion and browser automation MCP server",
    lifespan=lifespan
)

# Register tools from modules
conversion.register_tools(mcp)
batch.register_tools(mcp)
browser.register_tools(mcp)
queue.register_tools(mcp)
crawl.register_tools(mcp)


def main():
    """Entry point for MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
```

### 6. Tool Module Pattern

Each tool module follows this pattern:

```python
# src/gobbler_mcp/tools/conversion.py
"""Single-file conversion tools."""

from mcp.server.fastmcp import FastMCP
from ..decorators import handle_tool_errors
from ..converters import youtube, webpage, document, audio
from ..utils.file_handler import save_markdown

def register_tools(mcp: FastMCP):
    """Register conversion tools with the MCP server."""

    @mcp.tool()
    @handle_tool_errors("transcribe YouTube video")
    async def transcribe_youtube(
        video_url: str,
        include_timestamps: bool = False,
        language: str = "auto",
        output_file: str | None = None
    ) -> str:
        """
        Extract YouTube video transcript and convert to clean markdown format.

        Args:
            video_url: YouTube video URL
            include_timestamps: Include timestamp markers (default: False)
            language: Transcript language code or 'auto' (default: 'auto')
            output_file: Optional path to save markdown file

        Returns:
            Markdown text with YAML frontmatter
        """
        markdown, metadata = await youtube.convert_youtube_to_markdown(
            video_url=video_url,
            include_timestamps=include_timestamps,
            language=language
        )

        if output_file:
            save_markdown(output_file, markdown)
            return f"Saved transcript to {output_file}"

        return markdown

    # ... more tools ...
```

## Implementation Details

### Migration Strategy

1. **Create new structure** without modifying existing code
2. **Copy and refactor** tools into new modules
3. **Add re-exports** from old locations for compatibility
4. **Update imports** in test files
5. **Remove old code** after verification

### Files to Create

```
src/gobbler_mcp/
├── constants.py                 # NEW
├── decorators.py                # NEW
├── tools/
│   ├── __init__.py              # NEW
│   ├── conversion.py            # NEW
│   ├── batch.py                 # NEW
│   ├── browser.py               # NEW
│   ├── queue.py                 # NEW
│   └── crawl.py                 # NEW
```

### Files to Modify

```
src/gobbler_mcp/
├── server.py                    # Refactor to registration-only
```

## Acceptance Criteria

### Code Quality
- [ ] server.py < 500 lines
- [ ] Each tool module < 500 lines
- [ ] No duplicated error handling patterns
- [ ] All magic numbers in constants.py
- [ ] Consistent async/await patterns

### Functionality
- [ ] All 21 MCP tools work correctly
- [ ] Error messages unchanged
- [ ] Tool docstrings preserved
- [ ] No breaking changes to tool signatures

### Testing
- [ ] All existing tests pass
- [ ] New tests for decorators
- [ ] Tool registration verified

## Deliverables

### Files to Create
```
src/gobbler_mcp/
├── constants.py
├── decorators.py
└── tools/
    ├── __init__.py
    ├── conversion.py
    ├── batch.py
    ├── browser.py
    ├── queue.py
    └── crawl.py
```

### Files to Modify
```
src/gobbler_mcp/
└── server.py                    # Significant refactor
```

## Definition of Done

- [ ] server.py reduced to registration and lifespan only
- [ ] 5 tool modules created with logical grouping
- [ ] Error handling decorator eliminates duplication
- [ ] Constants module centralizes magic numbers
- [ ] All tools functional (manual verification)
- [ ] All tests pass
- [ ] No performance regression
- [ ] Code review completed

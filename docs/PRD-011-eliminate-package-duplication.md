# PRD-011: Eliminate Package Duplication

## Overview
**Epic**: Code Quality & Maintainability  
**Phase**: Refactoring  
**Status**: Pending  
**Effort**: 2-3 days  
**Dependencies**: None  
**Priority**: High  

## Problem Statement

The codebase has **100% identical file duplication** between `gobbler_core` and `gobbler_mcp` packages, completely defeating the architectural intent of having a shared core package:

| File | gobbler_core | gobbler_mcp | Lines |
|------|--------------|-------------|-------|
| `utils/frontmatter.py` | 209 lines | 209 lines | **IDENTICAL** |
| `utils/file_handler.py` | 115 lines | 115 lines | **IDENTICAL** |
| `utils/http_client.py` | 166 lines | 166 lines | **IDENTICAL** |
| `utils/health.py` | 102 lines | 102 lines | **IDENTICAL** |
| `converters/audio.py` | 310 lines | 310 lines | **IDENTICAL** |

**Total duplicated code: ~900 lines**

Additionally:
- `gobbler_mcp/exceptions.py` (113 lines) defines custom exceptions (`GobblerError`, `ServiceUnavailableError`, `ConversionError`, etc.) that are **never used anywhere** in the codebase
- `gobbler_relay/relay.py` duplicates `count_words()` and `create_webpage_frontmatter()` instead of importing from gobbler_core

### Root Cause

The architecture intended for `gobbler_core` to be a standalone, portable package with shared functionality, while `gobbler_mcp` would re-export from core and add MCP-specific code. Instead, files were copied wholesale into both packages.

## Success Criteria

- [ ] Zero duplicated files between gobbler_core and gobbler_mcp
- [ ] gobbler_mcp imports from gobbler_core (no copied implementations)
- [ ] gobbler_relay imports utilities from gobbler_core
- [ ] Custom exceptions either used throughout codebase or removed
- [ ] All existing tests pass
- [ ] ~900 lines of duplicated code eliminated

## Technical Requirements

### 1. Delete Duplicate Files in gobbler_mcp

Remove these files from `src/gobbler_mcp/` (they are identical to gobbler_core):

```
src/gobbler_mcp/
├── converters/
│   └── audio.py              # DELETE (310 lines)
├── utils/
│   ├── frontmatter.py        # DELETE (209 lines)
│   ├── file_handler.py       # DELETE (115 lines)
│   ├── http_client.py        # DELETE (166 lines)
│   └── health.py             # DELETE (102 lines)
```

### 2. Update gobbler_mcp __init__.py Files to Re-export

Update `src/gobbler_mcp/utils/__init__.py`:

```python
"""Gobbler MCP utilities - re-exported from gobbler_core."""

from gobbler_core.utils.file_handler import (
    ensure_parent_directory,
    sanitize_filename,
    save_markdown_file,
    validate_input_path,
    validate_output_path,
)
from gobbler_core.utils.frontmatter import (
    count_words,
    create_audio_frontmatter,
    create_document_frontmatter,
    create_webpage_frontmatter,
    create_youtube_frontmatter,
)
from gobbler_core.utils.health import ServiceHealthChecker
from gobbler_core.utils.http_client import RetryableHTTPClient

__all__ = [
    # file_handler
    "ensure_parent_directory",
    "sanitize_filename",
    "save_markdown_file",
    "validate_input_path",
    "validate_output_path",
    # frontmatter
    "count_words",
    "create_audio_frontmatter",
    "create_document_frontmatter",
    "create_webpage_frontmatter",
    "create_youtube_frontmatter",
    # health
    "ServiceHealthChecker",
    # http_client
    "RetryableHTTPClient",
]
```

Update `src/gobbler_mcp/converters/__init__.py`:

```python
"""Gobbler MCP converters - re-exported from gobbler_core."""

from gobbler_core.converters import (
    convert_audio_to_markdown,
    convert_document_to_markdown,
    convert_webpage_to_markdown,
    convert_youtube_to_markdown,
)

# MCP-specific converters (these stay in gobbler_mcp)
from .webpage_selector import convert_webpage_with_selector

__all__ = [
    "convert_audio_to_markdown",
    "convert_document_to_markdown",
    "convert_webpage_to_markdown",
    "convert_youtube_to_markdown",
    "convert_webpage_with_selector",
]
```

### 3. Fix gobbler_relay Duplication

Update `src/gobbler_relay/relay.py` to import from gobbler_core instead of duplicating:

```python
# Remove local definitions of count_words() and create_webpage_frontmatter()
from gobbler_core.utils.frontmatter import count_words, create_webpage_frontmatter
```

### 4. Address Unused Exceptions

Option A (Recommended): **Remove exceptions.py** - Since no code uses these exceptions, delete the file as dead code.

Option B: **Integrate exceptions** - Update converters and tools to raise specific exceptions:

```python
# In converters, replace:
raise RuntimeError("Failed to load Whisper model")
# With:
from gobbler_mcp.exceptions import ServiceUnavailableError
raise ServiceUnavailableError("whisper", "Failed to load Whisper model")
```

### 5. Standardize Import Patterns

Choose one pattern and use consistently:

**Within packages**: Use relative imports
```python
from .config import get_config
from ..utils import save_markdown_file
```

**Cross-package**: Use absolute imports
```python
from gobbler_core.utils.frontmatter import count_words
```

### 6. Fix pyproject.toml isort Configuration

Add gobbler_core to known-first-party:

```toml
[tool.ruff.lint.isort]
known-first-party = ["gobbler_mcp", "gobbler_relay", "gobbler_core"]
```

## Implementation Plan

### Phase 1: Verify File Identity (30 min)
```bash
# Verify files are truly identical before deletion
diff src/gobbler_core/utils/frontmatter.py src/gobbler_mcp/utils/frontmatter.py
diff src/gobbler_core/utils/file_handler.py src/gobbler_mcp/utils/file_handler.py
diff src/gobbler_core/utils/http_client.py src/gobbler_mcp/utils/http_client.py
diff src/gobbler_core/utils/health.py src/gobbler_mcp/utils/health.py
diff src/gobbler_core/converters/audio.py src/gobbler_mcp/converters/audio.py
```

### Phase 2: Update __init__.py Files (1 hour)
- Update `gobbler_mcp/utils/__init__.py` with re-exports
- Update `gobbler_mcp/converters/__init__.py` with re-exports
- Verify imports resolve correctly

### Phase 3: Delete Duplicate Files (30 min)
- Delete files listed in section 1
- Run tests to verify nothing broke

### Phase 4: Fix gobbler_relay (30 min)
- Update imports in relay.py
- Remove local function definitions
- Run relay tests

### Phase 5: Address Exceptions (1 hour)
- Decide: remove or integrate
- If removing: delete exceptions.py
- If integrating: update key error paths in converters

### Phase 6: Final Verification (30 min)
- Run full test suite
- Run linter
- Verify imports in all packages

## Files to Delete

```
src/gobbler_mcp/utils/frontmatter.py     # 209 lines
src/gobbler_mcp/utils/file_handler.py    # 115 lines
src/gobbler_mcp/utils/http_client.py     # 166 lines
src/gobbler_mcp/utils/health.py          # 102 lines
src/gobbler_mcp/converters/audio.py      # 310 lines
src/gobbler_mcp/exceptions.py            # 113 lines (if removing)
```

**Total deletion: ~1,015 lines**

## Files to Modify

```
src/gobbler_mcp/utils/__init__.py        # Re-export from gobbler_core
src/gobbler_mcp/converters/__init__.py   # Re-export from gobbler_core
src/gobbler_relay/relay.py               # Import from gobbler_core
pyproject.toml                           # Add gobbler_core to isort
```

## Acceptance Criteria

### Code Reduction
- [ ] 900+ lines of duplicated code removed
- [ ] Zero identical files between gobbler_core and gobbler_mcp
- [ ] exceptions.py addressed (removed or integrated)

### Functionality
- [ ] All existing tests pass (139 tests)
- [ ] gobbler_mcp tools work correctly
- [ ] gobbler_relay functions correctly
- [ ] Skills that import from gobbler_core work

### Architecture
- [ ] Clear separation: gobbler_core = shared, gobbler_mcp = MCP-specific
- [ ] Import patterns consistent across codebase
- [ ] isort configuration includes all first-party packages

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking imports | High | Run full test suite after each deletion |
| Skills depend on deleted code | Medium | Skills should already import from gobbler_core |
| Circular imports | Medium | Test import resolution before committing |

## Definition of Done

- [ ] All duplicate files deleted from gobbler_mcp
- [ ] __init__.py files updated with correct re-exports
- [ ] gobbler_relay imports from gobbler_core
- [ ] exceptions.py decision implemented
- [ ] pyproject.toml isort updated
- [ ] All 139 tests pass
- [ ] Linter passes with no errors
- [ ] Code review approved

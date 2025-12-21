# PRD-014: Skills Architecture Consolidation

## Overview
**Epic**: Architecture & Code Quality  
**Phase**: Refactoring  
**Status**: Pending  
**Effort**: 3-4 days  
**Dependencies**: PRD-011 (Eliminate Package Duplication)  
**Priority**: Medium  

## Problem Statement

The skills architecture has several inconsistencies and issues:

### Critical Issues

1. **Duplicate NotebookLM scripts**:
   - `skills/gobbler-browser/scripts/notebooklm.py` (547 lines)
   - `skills/notebooklm/scripts/notebooklm.py` (316 lines)
   - Both contain identical JavaScript injection code

2. **Hardcoded path**:
   - `skills/gobbler-browser/scripts/sandbox_bridge.py` line 95:
     ```python
     return "/Users/dylanisaac/Projects/gobbler"
     ```

3. **gobbler-youtube depends on gobbler-mcp**:
   - `skills/gobbler-youtube/scripts/transcribe.py` imports from `gobbler-mcp`
   - This defeats the purpose of standalone skills

### Inconsistencies

4. **Shebang inconsistency**:
   - Most skills: `#!/usr/bin/env -S uv run --script`
   - Browser scripts: `#!/usr/bin/env python3`

5. **SKILL.md format varies**:
   - Only `notebooklm` has version field
   - Documentation depth varies from 44 lines to 610 lines
   - Prerequisites format inconsistent

6. **Duplicate frontmatter code** in 5 locations:
   - `skills/gobbler-audio/scripts/transcribe.py`
   - `skills/gobbler-document/scripts/convert.py`
   - `skills/gobbler-webpage/scripts/fetch.py`
   - `skills/gobbler-utils/scripts/frontmatter.py`
   - `src/gobbler_core/utils/frontmatter.py`

## Success Criteria

- [ ] Single NotebookLM script (consolidated)
- [ ] No hardcoded paths in any script
- [ ] Skills import from gobbler_core, not gobbler_mcp
- [ ] Consistent shebang across all scripts
- [ ] Standardized SKILL.md format
- [ ] Frontmatter code imported from shared location

## Technical Requirements

### 1. Consolidate NotebookLM Scripts

Delete `skills/notebooklm/scripts/notebooklm.py` and have the notebooklm skill reference the browser version:

**Option A**: Symlink approach
```bash
cd skills/notebooklm/scripts
ln -s ../../gobbler-browser/scripts/notebooklm.py notebooklm.py
```

**Option B**: Re-export approach
```python
# skills/notebooklm/scripts/notebooklm.py (minimal)
"""NotebookLM CLI - see gobbler-browser for implementation."""
from gobbler_browser.scripts.notebooklm import main
if __name__ == "__main__":
    main()
```

**Recommended**: Option A (symlink) for simplicity.

### 2. Remove Hardcoded Path

Update `skills/gobbler-browser/scripts/sandbox_bridge.py`:

```python
# Before (line 95)
def get_project_root():
    return "/Users/dylanisaac/Projects/gobbler"

# After
def get_project_root():
    """Get project root directory dynamically."""
    # Walk up from this script to find pyproject.toml
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return str(parent)
    # Fallback to environment variable
    return os.environ.get("GOBBLER_ROOT", str(Path.home() / "Projects" / "gobbler"))
```

### 3. Fix gobbler-youtube Dependency

Update `skills/gobbler-youtube/scripts/transcribe.py` to import from `gobbler_core`:

```python
# Before
# /// script
# dependencies = [
#   "gobbler-mcp",
#   "yt-dlp>=2024.0.0",
# ]
# [tool.uv.sources]
# gobbler-mcp = { path = "../../../", editable = true }
# ///

from gobbler_mcp.converters import convert_youtube_to_markdown

# After
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "youtube-transcript-api>=0.6.3",
#   "yt-dlp>=2024.0.0",
#   "httpx>=0.27.0",
#   "pyyaml>=6.0.1",
# ]
# ///

from gobbler_core.converters import convert_youtube_to_markdown
from gobbler_core.utils.frontmatter import create_youtube_frontmatter
```

### 4. Standardize Shebang

Update all browser scripts to use the same shebang as other skills:

Files to update:
- `skills/gobbler-browser/scripts/browser_api.py`
- `skills/gobbler-browser/scripts/notebooklm.py`
- `skills/gobbler-browser/scripts/sandbox_bridge.py`
- `skills/gobbler-browser/scripts/test_*.py`

```python
# Before
#!/usr/bin/env python3

# After
#!/usr/bin/env -S uv run --script
```

### 5. Standardize SKILL.md Format

Create template and update all SKILL.md files:

```yaml
---
name: skill-name
description: Brief description of the skill
version: 1.0.0
allowed-tools: []  # MCP tools this skill uses (if any)
---

# Skill Name

## Overview

Brief description of what this skill does and when to use it.

## Prerequisites

- List prerequisites
- One per line

## Installation

```bash
# Installation commands if any
```

## Usage

### Basic Usage

```bash
# Basic example
uv run skills/skill-name/scripts/main.py <args>
```

### Advanced Usage

```bash
# Advanced example with options
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| param1 | string | Yes | - | Description |
| param2 | int | No | 10 | Description |

## Examples

### Example 1: Description

```bash
# Command
uv run skills/skill-name/scripts/main.py example

# Output
Expected output here
```

## Troubleshooting

### Common Issue 1

**Problem**: Description of issue
**Solution**: How to fix it

### Common Issue 2

**Problem**: Description
**Solution**: Fix

## Related

- Link to related skills or documentation
```

### 6. Consolidate Frontmatter Code

Skills should import from `gobbler_core` instead of having local copies:

```python
# In skill scripts, replace local create_frontmatter() with:
from gobbler_core.utils.frontmatter import (
    create_audio_frontmatter,
    create_webpage_frontmatter,
    create_youtube_frontmatter,
    create_document_frontmatter,
)
```

This requires skills to either:
1. Have `gobbler-mcp` as a dependency (provides gobbler_core)
2. Have `gobbler-core` as a separate pip-installable package

**Recommended**: For now, keep local frontmatter in skills until gobbler_core is a proper package. Mark as TODO for future work.

### 7. Create Skills Testing Structure

Move test files from `skills/gobbler-browser/scripts/test_*.py` to central location:

```
tests/
├── skills/
│   ├── __init__.py
│   ├── test_browser_api.py
│   ├── test_notebooklm.py
│   └── test_websocket.py
```

## Implementation Plan

### Phase 1: Critical Fixes (Day 1)
- Remove hardcoded path from sandbox_bridge.py
- Fix gobbler-youtube dependency on gobbler-mcp
- Consolidate NotebookLM scripts

### Phase 2: Shebang Standardization (Day 1)
- Update all browser scripts to use uv run shebang
- Verify scripts still work

### Phase 3: SKILL.md Standardization (Day 2)
- Create SKILL.md template
- Update all 7 SKILL.md files
- Add version fields

### Phase 4: Test Reorganization (Day 3)
- Move skill tests to central location
- Update imports and paths
- Verify tests pass

### Phase 5: Documentation (Day 3-4)
- Update skills README
- Document skill development guidelines

## Files to Delete

```
skills/notebooklm/scripts/notebooklm.py   # Replace with symlink
```

## Files to Create

```
skills/notebooklm/scripts/notebooklm.py -> ../../gobbler-browser/scripts/notebooklm.py  # Symlink
tests/skills/__init__.py
tests/skills/test_browser_api.py         # Moved from skills/
tests/skills/test_notebooklm.py          # Moved from skills/
tests/skills/test_websocket.py           # Moved from skills/
docs/SKILL_TEMPLATE.md                   # Template for new skills
```

## Files to Modify

```
skills/gobbler-browser/scripts/sandbox_bridge.py   # Remove hardcoded path
skills/gobbler-youtube/scripts/transcribe.py       # Fix imports
skills/gobbler-browser/scripts/browser_api.py      # Fix shebang
skills/gobbler-browser/scripts/notebooklm.py       # Fix shebang
skills/gobbler-browser/scripts/sandbox_bridge.py   # Fix shebang
skills/gobbler-audio/SKILL.md                      # Standardize
skills/gobbler-browser/SKILL.md                    # Standardize
skills/gobbler-document/SKILL.md                   # Standardize
skills/gobbler-utils/SKILL.md                      # Standardize
skills/gobbler-webpage/SKILL.md                    # Standardize
skills/gobbler-youtube/SKILL.md                    # Standardize
skills/notebooklm/SKILL.md                         # Standardize
```

## Acceptance Criteria

### Code Quality
- [ ] No duplicate NotebookLM scripts
- [ ] No hardcoded paths in any script
- [ ] Skills don't depend on gobbler_mcp
- [ ] Consistent shebang across all scripts

### Documentation
- [ ] All SKILL.md files have version field
- [ ] All SKILL.md files follow template
- [ ] Skill development guide created

### Testing
- [ ] Skill tests in central location
- [ ] All skill scripts executable with `uv run`
- [ ] CI includes skill tests

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Symlink not working on Windows | Medium | Document Windows workaround |
| Breaking skill imports | High | Test each skill after changes |
| gobbler_core not installable | Medium | Keep local fallbacks for now |

## Future Work

1. **Make gobbler_core pip-installable**: Allow skills to `pip install gobbler-core` instead of path-based imports

2. **Skill discovery system**: Auto-discover skills from `skills/` directory

3. **Skill versioning**: Track skill versions and compatibility

## Definition of Done

- [ ] NotebookLM scripts consolidated
- [ ] Hardcoded path removed
- [ ] gobbler-youtube uses gobbler_core
- [ ] Shebangs standardized
- [ ] SKILL.md files standardized
- [ ] Skill tests relocated
- [ ] All skills work correctly
- [ ] CI passes
- [ ] Documentation updated

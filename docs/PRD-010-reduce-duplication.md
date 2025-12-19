# PRD-010: Reduce Code Duplication

## Overview
**Epic**: Code Quality & Maintainability
**Phase**: Refactoring
**Dependencies**: PRD-007, PRD-008, PRD-009 - architecture and modularization first
**Parallel**: No - builds on previous refactoring work

## Problem Statement

The dual Skills/MCP architecture has led to significant code duplication:

1. **Provider duplication**: YouTube transcript provider class (~170 lines) duplicated in skill scripts
2. **Utility duplication**: Frontmatter generation, docker health checks, HTTP client logic repeated
3. **Inline fallbacks**: Skills re-implement backend logic instead of importing shared code
4. **No shared contract**: Provider interface not defined, each implementation diverges

This creates maintenance burden - bug fixes and improvements must be applied in multiple places.

## Success Criteria

- [ ] Provider layer properly abstracted with defined interface
- [ ] Skills import from shared providers (no inline fallback implementations)
- [ ] Utility functions consolidated in gobbler_mcp.utils
- [ ] Total lines of duplicated code reduced by >50%
- [ ] Clear documentation for extending providers

## Technical Requirements

### 1. Provider Interface Contract

Define abstract base class for all providers:

```python
# src/gobbler_mcp/providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class ProviderResult:
    """Standard result from any provider."""
    success: bool
    content: str
    metadata: dict[str, Any]
    error: Optional[str] = None

class ContentProvider(ABC):
    """Base class for all content providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging/identification."""
        pass

    @abstractmethod
    async def fetch(self, source: str, **options) -> ProviderResult:
        """
        Fetch content from the source.

        Args:
            source: URL, file path, or identifier
            **options: Provider-specific options

        Returns:
            ProviderResult with content and metadata
        """
        pass

    @abstractmethod
    def supports(self, source: str) -> bool:
        """Check if this provider supports the given source."""
        pass
```

### 2. YouTube Provider Consolidation

Current state:
- `src/gobbler_mcp/providers/youtube.py` - Main implementation (~300 lines)
- `skills/gobbler-youtube/scripts/transcribe.py` - Inline fallback (~170 lines)

Target state:
- Single implementation in `src/gobbler_mcp/providers/youtube.py`
- Skills import directly from package

```python
# src/gobbler_mcp/providers/youtube.py
from .base import ContentProvider, ProviderResult

class YouTubeTranscriptProvider(ContentProvider):
    """Free YouTube transcript API provider."""

    @property
    def name(self) -> str:
        return "youtube-transcript-api"

    async def fetch(self, video_url: str, **options) -> ProviderResult:
        language = options.get("language", "auto")
        include_timestamps = options.get("include_timestamps", False)

        video_id = extract_video_id(video_url)

        try:
            transcript = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=[language] if language != "auto" else None
            )

            content = format_transcript(transcript, include_timestamps)

            return ProviderResult(
                success=True,
                content=content,
                metadata={
                    "video_id": video_id,
                    "language": language,
                    "source": "youtube-transcript-api"
                }
            )
        except Exception as e:
            return ProviderResult(
                success=False,
                content="",
                metadata={},
                error=str(e)
            )

    def supports(self, source: str) -> bool:
        return "youtube.com" in source or "youtu.be" in source


class PaidTranscriptProvider(ContentProvider):
    """Paid transcript API provider (fallback)."""
    # ... similar implementation


class AutoFallbackProvider(ContentProvider):
    """Try free API first, fall back to paid."""

    def __init__(self):
        self.providers = [
            YouTubeTranscriptProvider(),
            PaidTranscriptProvider()
        ]

    async def fetch(self, video_url: str, **options) -> ProviderResult:
        for provider in self.providers:
            result = await provider.fetch(video_url, **options)
            if result.success:
                return result

        # All providers failed
        return ProviderResult(
            success=False,
            content="",
            metadata={},
            error="All transcript providers failed"
        )
```

### 3. Skill Import Pattern

Skills should import from the package, not re-implement:

```python
# skills/gobbler-youtube/scripts/transcribe.py
# /// script
# requires-python = ">=3.11"
# dependencies = ["gobbler-mcp"]  # Install the package
# ///

import sys
import argparse

# Import from shared package
from gobbler_mcp.providers.youtube import AutoFallbackProvider
from gobbler_mcp.utils.frontmatter import generate_frontmatter

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--timestamps", action="store_true")
    parser.add_argument("--language", default="auto")
    args = parser.parse_args()

    provider = AutoFallbackProvider()
    result = await provider.fetch(
        args.url,
        include_timestamps=args.timestamps,
        language=args.language
    )

    if result.success:
        markdown = generate_frontmatter(result.metadata) + "\n\n" + result.content
        print(markdown)
    else:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### 4. Utility Consolidation

Consolidate duplicated utilities:

| Utility | Current Locations | Target Location |
|---------|-------------------|-----------------|
| Frontmatter generation | server.py, multiple skills | `utils/frontmatter.py` |
| Docker health check | server.py, skills | `utils/health.py` |
| HTTP client with retry | server.py, webpage.py | `utils/http_client.py` |
| Video ID extraction | youtube.py, skill | `providers/youtube.py` |
| File validation | multiple locations | `utils/file_handler.py` |

```python
# src/gobbler_mcp/utils/frontmatter.py
from datetime import datetime
from typing import Any
import yaml

def generate_frontmatter(metadata: dict[str, Any]) -> str:
    """
    Generate YAML frontmatter from metadata dict.

    Args:
        metadata: Dictionary of metadata fields

    Returns:
        YAML frontmatter string with --- delimiters
    """
    # Ensure conversion_date is present
    if "conversion_date" not in metadata:
        metadata["conversion_date"] = datetime.now().isoformat()

    # Filter None values
    clean_metadata = {k: v for k, v in metadata.items() if v is not None}

    yaml_content = yaml.dump(clean_metadata, default_flow_style=False, allow_unicode=True)

    return f"---\n{yaml_content}---"
```

### 5. Registry Pattern Consolidation

Consolidate page-apis registry (currently duplicated in registry.js and background.js):

```javascript
// browser-extension/page-apis/registry.js (SINGLE SOURCE OF TRUTH)
export const PAGE_API_REGISTRY = [
  {
    name: 'NotebookLM',
    pattern: /^https:\/\/notebooklm\.google\.com/,
    apiFile: 'page-apis/notebooklm.js',
    globalName: 'gobblerNotebookLM',
    enabled: true,
    methods: ['ask', 'sendMessage', 'getChatContent', 'getSources', 'getNotebookInfo']
  },
  // Future APIs...
];

export function getApiForUrl(url) {
  return PAGE_API_REGISTRY.find(api => api.enabled && api.pattern.test(url));
}

export function getAllApis() {
  return PAGE_API_REGISTRY.filter(api => api.enabled);
}
```

```javascript
// browser-extension/background.js
import { PAGE_API_REGISTRY, getApiForUrl } from './page-apis/registry.js';

// Use imported registry instead of duplicating
```

## Implementation Details

### Migration Strategy

1. **Define interfaces first** - Create base.py with contracts
2. **Consolidate providers** - Merge YouTube implementations
3. **Update skills** - Change to import from package
4. **Consolidate utilities** - Merge duplicate utility code
5. **Fix browser extension** - Single registry source

### Files to Create

```
src/gobbler_mcp/
├── providers/
│   ├── __init__.py              # MODIFY: Add exports
│   └── base.py                  # NEW: Provider interface
```

### Files to Modify

```
src/gobbler_mcp/
├── providers/
│   └── youtube.py               # MODIFY: Implement interface
├── utils/
│   ├── frontmatter.py           # MODIFY: Consolidate
│   └── http_client.py           # MODIFY: Add retry logic

skills/gobbler-youtube/scripts/
├── transcribe.py                # MODIFY: Import from package

browser-extension/
├── page-apis/registry.js        # MODIFY: Add exports
└── background.js                # MODIFY: Import registry
```

### Files to Remove (after migration)

Inline fallback implementations in skill scripts that duplicate provider logic.

## Acceptance Criteria

### Code Reduction
- [ ] YouTube provider: single implementation (~300 lines, not ~470)
- [ ] Frontmatter utility: single implementation
- [ ] HTTP client: single implementation with retry
- [ ] Page API registry: single source of truth

### Interface Compliance
- [ ] All providers implement ContentProvider interface
- [ ] ProviderResult used consistently
- [ ] Skills successfully import from package

### Functionality
- [ ] All skills work with imported providers
- [ ] Fallback behavior preserved
- [ ] Error handling consistent

### Testing
- [ ] Provider interface tests
- [ ] Skill import verification
- [ ] Browser extension registry tests

## Deliverables

### Files to Create
```
src/gobbler_mcp/providers/
└── base.py                      # Provider interface
```

### Files to Modify
```
src/gobbler_mcp/
├── providers/
│   ├── __init__.py
│   └── youtube.py
├── utils/
│   ├── frontmatter.py
│   └── http_client.py

skills/gobbler-youtube/scripts/
└── transcribe.py

browser-extension/
├── page-apis/registry.js
└── background.js
```

## Metrics

### Before
- YouTube provider: ~470 lines (300 + 170 fallback)
- Frontmatter logic: ~3 locations
- HTTP retry logic: ~2 locations
- Registry: 2 locations

### After (Target)
- YouTube provider: ~300 lines (single)
- Frontmatter logic: 1 location
- HTTP retry logic: 1 location
- Registry: 1 location

**Estimated reduction**: ~200 lines of duplicated code

## Definition of Done

- [ ] Provider interface defined and documented
- [ ] YouTube provider implements interface
- [ ] Skills import from package (no inline fallbacks)
- [ ] Utilities consolidated
- [ ] Browser extension uses single registry
- [ ] All tests pass
- [ ] Total duplicated lines reduced by >50%
- [ ] Documentation updated for extending providers

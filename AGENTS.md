# AGENTS.md - Gobbler Development Guidelines

Guidelines for AI coding agents. See [CONTRIBUTING.md](CONTRIBUTING.md) for full details.

## Quick Reference

```bash
# Install
make dev                    # Development install with all extras

# Tests
make test                   # Unit + integration tests
make test-unit              # Unit tests only
uv run pytest tests/unit/test_youtube_converter.py -v                        # Single file
uv run pytest tests/unit/test_youtube_converter.py::TestVideoIdExtraction -v # Single class
uv run pytest tests/unit/test_youtube_converter.py::TestVideoIdExtraction::test_extract_video_id_standard_url -v  # Single test

# Linting & Formatting
make lint                   # Run ruff linter + format check
uv run ruff check src/ --fix   # Auto-fix lint issues
uv run ruff format src/     # Format code

# Type Checking
make typecheck              # Run mypy

# All Checks
uv run pre-commit run --all-files
```

## Project Structure

```
src/
  gobbler_cli/      # CLI commands (Typer-based)
  gobbler_core/     # Core converters and providers
  gobbler_relay/    # WebSocket relay for browser extension
  gobbler_queue/    # Background job queue (RQ-based)
skills/             # Claude Code skill definitions
tests/unit/         # Unit tests
tests/integration/  # Integration tests
tests/e2e/          # End-to-end tests
```

## Code Style

- **Python 3.11+** required
- **Line length**: 100 characters max
- **Type hints**: Strict mode - all public functions must have annotations
- **Docstrings**: Google-style, required for public functions
- **Imports**: Organized by ruff/isort (stdlib, third-party, first-party, local)

First-party packages: `gobbler_core`, `gobbler_cli`, `gobbler_relay`, `gobbler_queue`

### Type Annotations

```python
# Use modern syntax
async def convert(url: str, provider: Provider | None = None) -> tuple[str, dict]:
    ...
```

### Docstrings (Google-style)

```python
def extract_video_id(url: str) -> str:
    """Extract video ID from YouTube URL.

    Args:
        url: YouTube video URL in various formats.

    Returns:
        11-character video ID string.

    Raises:
        ValueError: If URL format is invalid.
    """
```

### Logging

```python
import logging
logger = logging.getLogger(__name__)

logger.info("Starting conversion")
logger.exception("Unexpected error in %s", operation_name)  # Includes traceback
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Functions/variables | `snake_case` | `extract_video_id` |
| Classes | `PascalCase` | `TranscriptProvider` |
| Constants | `SCREAMING_SNAKE_CASE` | `DEFAULT_TIMEOUT` |
| Private | `_` prefix | `_internal_helper` |

## Testing

```python
"""Unit tests for module."""
import pytest
from gobbler_core.converters.youtube import extract_video_id

class TestVideoIdExtraction:
    """Test video ID extraction."""

    def test_standard_url(self):
        """Test standard youtube.com URL."""
        assert extract_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_invalid_url_raises_error(self):
        """Test that invalid URL raises ValueError."""
        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            extract_video_id("not a url")

    @pytest.mark.asyncio
    async def test_async_conversion(self, mock_service):
        """Test async function with mock."""
        result = await async_function()
        assert "expected" in result
```

### Test Naming
- Files: `test_<module_name>.py`
- Classes: `Test<FeatureName>`
- Methods: `test_<scenario>` or `test_<method>_<condition>_<expected>`

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance

## Pre-commit Hooks

Runs automatically on commit:
1. Trailing whitespace, end-of-file fixes
2. YAML/TOML/JSON syntax validation
3. Ruff linting and formatting
4. Mypy type checking
5. Interrogate docstring coverage (min 50%)
6. Bandit security checks

## Key Dependencies

- **Typer**: CLI framework
- **httpx**: Async HTTP client
- **RQ**: Background job queue (Redis-based)
- **Whisper**: Audio transcription
- **Docling**: Document conversion
- **Crawl4AI**: Web crawling

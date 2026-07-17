# CLAUDE.md

This file provides guidance to AI coding agents that read `CLAUDE.md` when working with code in this repository.

## Project Overview

Gobbler is a universal content conversion tool that transforms YouTube videos, web pages, documents, and audio files into clean markdown with YAML frontmatter. It provides a CLI-first experience plus AI agent Skills that call the CLI.

## Common Commands

```bash
# Install dependencies
uv sync

# Start Docker services (Crawl4AI, Docling)
make start-docker

# Run tests
make test                           # Unit tests
make test-unit                      # Unit tests only
make test-integration               # Integration tests
make test-all                       # Unit + integration + end-to-end tests
uv run pytest tests/unit/test_youtube_converter.py -v  # Single test file
uv run pytest tests/unit/test_youtube_converter.py::test_function -v  # Single test

# Code quality
uv run ruff check src/ --fix        # Lint + auto-fix
uv run ruff format src/             # Format code
uv run mypy src/                    # Type check
uv run bandit -c pyproject.toml -r src/  # Security scan
uv run pre-commit run --all-files   # All checks at once

# Check CLI
uv run gobbler --version
uv run gobbler status --json
```

## Architecture

### Source Layout (`src/`)

- **gobbler_core/** - Shared converters, config, providers, and utilities used by the CLI
  - `converters/` - YouTube, audio, document, webpage conversion logic
  - `providers/` - Backend service clients
  - `utils/` - Shared utilities

- **gobbler_cli/** - Typer-based CLI interface
  - `commands/` - Command implementations (batch, browser, convert, notebooklm, etc.)
  - `main.py` - CLI entry point

- **gobbler_relay/** - WebSocket bridge to browser extension (port 4625)
  - `relay.py` - WebSocket server for bidirectional browser communication
  - `client.py` - Client for sending commands to extension

- **gobbler_queue/** - SQLite-backed background job queue
  - `worker.py` - Polling worker that executes structured command arguments
  - `manager.py` - Job management and progress tracking
  - `models.py` - Job data models

### External Services (Docker)

- **Crawl4AI** (port 11235) - JavaScript-rendered web scraping
- **Docling** (port 5001) - PDF/DOCX/PPTX/XLSX to markdown

### Key Design Patterns

1. **CLI-first architecture**: Skills and scripts call the same CLI/core logic
2. **Progressive disclosure**: Skills load concise metadata and read full CLI instructions on demand
3. **Explicit queueing**: Supported commands queue only when the caller supplies `--queue`
4. **Provider abstraction**: Multiple backends per capability with fallback (e.g., YouTube: free API → paid API)
5. **Tab group security**: Browser automation only accesses tabs in the "Gobbler" Chrome tab group

### Skills (`skills/`)

Markdown instruction files for AI agents. Each skill contains a `SKILL.md` with YAML frontmatter for discovery and quick workflows for common tasks.

## Testing

- Tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- Markers: `integration`, `benchmark`, `e2e`
- Coverage threshold: 70%
- Test structure mirrors source: `tests/unit/`, `tests/integration/`, `tests/e2e/`

## Code Style

- Line length: 100 characters
- Docstrings: Google style
- Type hints required on all functions
- Max cyclomatic complexity: 12
- Prefer existing exception types and TypedDicts from the package you are editing

## Configuration

User config: `~/.config/gobbler/config.yml`

```yaml
services:
  docling:
    host: localhost
    port: 5001
  crawl4ai:
    host: localhost
    port: 11235
    api_token: gobbler-local-token
```

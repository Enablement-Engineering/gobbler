# Contributing to Gobbler

Thank you for your interest in contributing to Gobbler.

## Getting Started

1. Fork the repository on GitHub.
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/gobbler.git
   cd gobbler
   ```
3. Install dependencies:
   ```bash
   make dev
   ```
4. Install pre-commit hooks:
   ```bash
   uv run pre-commit install
   ```
5. Start Docker services when working on web or document conversion:
   ```bash
   make start-docker
   ```

## Development Workflow

```bash
# Run tests
make test
make test-unit

# Code quality
uv run ruff check src/ tests/ --fix
uv run ruff format src/ tests/
uv run mypy src/
uv run bandit -c pyproject.toml -r src/
uv run pre-commit run --all-files
```

## Project Structure

```
src/
  gobbler_cli/      # Typer CLI commands
  gobbler_core/     # Configuration, converters, providers, utilities
  gobbler_relay/    # WebSocket relay for browser extension
  gobbler_queue/    # Background job queue
skills/             # AI-agent skill instructions that call the CLI
tests/              # Unit, integration, and end-to-end tests
```

## Code Style

- Python 3.11+
- Line length: 100 characters
- Google-style docstrings for public functions
- Type annotations for public functions
- Ruff for linting and formatting
- Prefer existing core/provider abstractions over new parallel code paths

## Adding a Converter

1. Add converter logic under `src/gobbler_core/converters/`.
2. Add or reuse provider code under `src/gobbler_core/providers/` when the converter talks to a backend.
3. Add a CLI command or option under `src/gobbler_cli/commands/` if users need a new workflow.
4. Add focused unit tests under `tests/unit/`.
5. Update README and docs when the user-facing command surface changes.

## Testing

```bash
# All unit tests
uv run pytest tests/unit -q

# Single file
uv run pytest tests/unit/test_youtube_converter.py -v

# Single test
uv run pytest tests/unit/test_youtube_converter.py::TestVideoIdExtraction::test_extract_video_id_standard_url -v
```

## Pull Request Checklist

- [ ] Tests pass
- [ ] Ruff check and format pass
- [ ] Type checking passes when relevant
- [ ] Security checks pass when relevant
- [ ] Documentation updated for user-facing changes
- [ ] Changes are scoped to the requested behavior

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance

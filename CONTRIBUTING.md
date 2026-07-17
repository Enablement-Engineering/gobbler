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

The blocking pull-request gate mirrors CI:

```bash
uv run pytest tests/unit/ -v \
  --cov=src/gobbler_core --cov=src/gobbler_cli \
  --cov=src/gobbler_relay --cov=src/gobbler_queue \
  --cov-report=term-missing --cov-fail-under=0
uv run ruff format --check src/ tests/
uv run ruff check src/ tests/
uv run --extra docs mkdocs build --strict

# Single file
uv run pytest tests/unit/test_youtube_converter.py -v

# Single test
uv run pytest tests/unit/test_youtube_converter.py::TestVideoIdExtraction::test_extract_video_id_standard_url -v
```

`mypy` and integration tests are useful additional checks, but the current GitHub workflow treats them as advisory: mypy uses `continue-on-error`, and integration tests run after pushes to `main`, not on pull requests.

## Pull Request Checklist

- [ ] Tests pass
- [ ] Ruff check and format pass
- [ ] Type-checking output was reviewed when relevant (currently advisory in CI)
- [ ] Security checks pass when relevant
- [ ] Documentation updated for user-facing changes
- [ ] Changes are scoped to the requested behavior

## Maintainer Release Checklist

1. Update `CHANGELOG.md` and `docs/changelog.md`.
2. Keep the version synchronized in `pyproject.toml`, `src/gobbler_core/__init__.py`, `src/gobbler_cli/__init__.py`, `src/gobbler_queue/__init__.py`, `browser-extension/manifest.json`, and `browser-extension/background.js`.
3. Run the blocking gate above; `tests/unit/test_version_sync.py` detects version drift.
4. Merge the release commit, tag `vX.Y.Z`, and create the GitHub release from that exact commit.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance

---
icon: material/heart
---

# Contributing

Thank you for your interest in contributing to Gobbler!

For the complete contributing guide, see [CONTRIBUTING.md](https://github.com/Enablement-Engineering/gobbler/blob/main/CONTRIBUTING.md) in the repository root.

## Quick Start

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/gobbler.git
cd gobbler

# Install with dev dependencies
make dev

# Set up pre-commit hooks
uv run pre-commit install

# Run tests
make test
```

## Development Workflow

1. Create a feature branch
2. Make your changes
3. Run quality checks: `uv run pre-commit run --all-files`
4. Submit a pull request

## Code Style

- Python 3.11+
- Type hints required
- Google-style docstrings
- 100 character line limit
- Ruff for linting/formatting

## Testing

```bash
# Unit tests (the default test target)
make test

# Fast public CLI contract smoke tests (no Docker or worker required)
make test-cli-contract

# Blocking pull-request checks
uv run pytest tests/unit/ -v \
  --cov=src/gobbler_core --cov=src/gobbler_cli \
  --cov=src/gobbler_relay --cov=src/gobbler_queue \
  --cov-report=term-missing --cov-fail-under=0
uv run ruff format --check src/ tests/
uv run ruff check src/ tests/
uv run --extra docs mkdocs build --strict
```

Mypy and integration tests are currently advisory in GitHub Actions; pull requests are blocked by the unit-test and Ruff jobs above.

The CLI contract harness in `tests/cli_contract.py` provides helpers for asserting
exit codes and parsing single-object JSON or JSON-lines stdout. Add focused public
CLI checks to `tests/unit/test_cli_contract_smoke.py`; mock external services so the
harness remains safe to run in CI and from a fresh contributor checkout.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance

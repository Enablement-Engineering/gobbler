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
# Run all tests
make test

# Unit tests only
make test-unit

# With coverage
uv run pytest --cov
```

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance

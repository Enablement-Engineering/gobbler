# Contributing to Gobbler

Thank you for your interest in contributing to Gobbler! This guide will help you get started.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/gobbler.git  # Replace YOUR_USERNAME with your username
   cd gobbler
   ```

3. **Install dependencies**:
   ```bash
   make install
   # or: uv sync --dev
   ```

4. **Set up pre-commit hooks** (recommended):
   ```bash
   uv run pre-commit install
   ```
   This will automatically run code quality checks before each commit.

5. **Start services**:
   ```bash
   make start
   ```

## Development Workflow

### Making Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code style guidelines below

3. **Test your changes**:
   ```bash
   # Run all quality checks at once
   uv run pre-commit run --all-files

   # Or run individual checks:

   # Run tests
   uv run pytest

   # Type checking
   uv run mypy src/

   # Linting
   uv run ruff check src/ --fix

   # Format code
   uv run ruff format src/

   # Security checks
   uv run bandit -c pyproject.toml -r src/

   # Docstring coverage
   uv run interrogate src/
   ```

4. **Test with MCP Inspector**:
   ```bash
   make inspector
   ```

5. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add awesome feature"
   ```

   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `refactor:` - Code refactoring
   - `test:` - Adding tests
   - `chore:` - Maintenance tasks

6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request** on GitHub

## Code Quality Tools

### Pre-commit Hooks

Pre-commit hooks automatically run quality checks before each commit. After installing with `uv run pre-commit install`, these checks run automatically:

- **Ruff** - Code formatting and linting
- **MyPy** - Static type checking
- **Bandit** - Security vulnerability scanning
- **Interrogate** - Docstring coverage checking
- **File checks** - Trailing whitespace, YAML/TOML syntax, etc.

To run manually:
```bash
# Run on all files
uv run pre-commit run --all-files

# Run on staged files only
uv run pre-commit run

# Skip hooks for a specific commit (not recommended)
git commit --no-verify -m "message"
```

### Custom Exceptions

Use the custom exception hierarchy from `gobbler_mcp.exceptions`:

```python
from gobbler_mcp.exceptions import (
    ServiceUnavailableError,
    ConversionError,
    ConfigurationError,
    QueueError,
    ValidationError,
    TimeoutError,
)

# Example usage
if not service_available:
    raise ServiceUnavailableError("Docker container is not running")

if invalid_url:
    raise ValidationError(f"Invalid URL format: {url}")
```

### Type Safety

Use TypedDicts from `gobbler_mcp.types` for structured data:

```python
from gobbler_mcp.types import (
    ConversionMetadata,
    BatchResult,
    JobStatus,
    ServiceHealth,
)

# Example usage
metadata: ConversionMetadata = {
    "title": "Document Title",
    "source_url": "https://example.com",
    "conversion_date": datetime.now().isoformat(),
}
```

## Code Style Guidelines

### Python

- **Follow PEP 8** - enforced by `ruff`
- **Type hints** - use type annotations for all functions
- **Docstrings** - all public functions should have Google-style docstrings
- **Line length** - max 100 characters
- **Imports** - organized with `isort` (handled by `ruff`)
- **Complexity** - max cyclomatic complexity of 12

### Example Function

```python
async def convert_something(
    input_path: str,
    output_path: Optional[str] = None,
    **options: Any,
) -> str:
    """
    Convert something to markdown.

    Args:
        input_path: Absolute path to input file
        output_path: Optional path to save output
        **options: Additional conversion options

    Returns:
        Markdown string with frontmatter

    Raises:
        ValueError: If input_path is invalid
        RuntimeError: If conversion service unavailable
    """
    # Implementation here
    pass
```

### Logging

Use the standard logging module:

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Starting conversion")
logger.warning("Service unavailable, retrying...")
logger.error(f"Failed to process: {error}", exc_info=True)
```

### Error Handling

- **Use custom exceptions** - from `gobbler_mcp.exceptions`
- **Validate inputs early** - fail fast with clear error messages
- **Handle service errors gracefully** - provide actionable feedback
- **Log exceptions** - use `exc_info=True` for tracebacks

```python
from gobbler_mcp.exceptions import ServiceUnavailableError, ValidationError

# Validate inputs
if not file_path or not Path(file_path).exists():
    raise ValidationError(f"File does not exist: {file_path}")

# Handle service errors
try:
    result = await service.convert(file_path)
except httpx.ConnectError as e:
    raise ServiceUnavailableError(
        "Service unavailable. Start with: docker-compose up -d service"
    ) from e
except ValueError as e:
    raise ValidationError(f"Invalid input: {str(e)}") from e
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise ConversionError(f"Conversion failed: {str(e)}") from e
```

## Project Structure

### Adding a New Converter

1. **Create converter file** in `src/gobbler_mcp/converters/`
2. **Implement conversion function**:
   ```python
   async def convert_myformat_to_markdown(
       input_path: str,
       **options: Any,
   ) -> Tuple[str, Dict[str, Any]]:
       """Convert MyFormat to markdown."""
       # 1. Validate input
       # 2. Call service/library
       # 3. Process response
       # 4. Generate markdown + metadata
       return markdown, metadata
   ```

3. **Export from `__init__.py`**:
   ```python
   from .myformat import convert_myformat_to_markdown
   ```

4. **Add MCP tool** in `server.py`:
   ```python
   @mcp.tool()
   async def convert_myformat(
       file_path: str,
       output_file: Optional[str] = None,
   ) -> str:
       """Convert MyFormat files to markdown."""
       markdown, metadata = await convert_myformat_to_markdown(file_path)
       # Handle output_file...
       return markdown
   ```

5. **Add tests** in `tests/test_myformat_converter.py`

6. **Update documentation** in README.md

### Adding Queue Support

If your tool runs for >1 minute, add queue support:

```python
# 1. Extract task function
async def _my_task(arg1: str, arg2: int) -> str:
    """Internal task function."""
    # Do work
    return result

# 2. Add auto_queue parameter to tool
@mcp.tool()
async def my_tool(
    arg1: str,
    arg2: int = 10,
    auto_queue: bool = False,
) -> str:
    """My tool with queue support."""
    # Check if should queue
    if should_queue_task("my_task", auto_queue, custom_param=arg2):
        queue = get_queue("default")
        job = queue.enqueue(_my_task, arg1=arg1, arg2=arg2, job_timeout="10m")
        return format_job_response(job, "my_task", custom_param=arg2)

    # Execute synchronously
    return await _my_task(arg1, arg2)
```

## Testing

### Writing Tests

Tests go in `tests/` directory:

```python
import pytest
from gobbler_mcp.converters.myformat import convert_myformat_to_markdown

@pytest.mark.asyncio
async def test_convert_myformat():
    """Test MyFormat conversion."""
    markdown, metadata = await convert_myformat_to_markdown("/path/to/test.myformat")

    assert "# " in markdown  # Has heading
    assert metadata["type"] == "myformat"
    assert metadata["source"].endswith(".myformat")
```

### Running Tests

```bash
# All tests
uv run pytest

# Specific test
uv run pytest tests/test_myformat_converter.py

# With coverage
uv run pytest --cov=gobbler_mcp

# Skip slow integration tests
uv run pytest -m "not integration"
```

## Documentation

### Updating Docs

When adding features, update:

1. **README.md** - Add tool documentation
2. **ARCHITECTURE.md** - If changing architecture
3. **API.md** - Update API specifications
4. **Docstrings** - In-code documentation

### Documentation Style

- **Be concise** - users want quick answers
- **Use examples** - show, don't just tell
- **Include errors** - document common failure modes
- **Link to external docs** - for dependencies

## Pull Request Guidelines

### Before Submitting

- [ ] Pre-commit hooks pass (`uv run pre-commit run --all-files`)
- [ ] Tests pass (`uv run pytest`)
- [ ] Code is formatted (`uv run ruff format src/`)
- [ ] No linting errors (`uv run ruff check src/`)
- [ ] Type checking passes (`uv run mypy src/`)
- [ ] Security checks pass (`uv run bandit -c pyproject.toml -r src/`)
- [ ] Coverage threshold met (70%+) (`uv run pytest --cov`)
- [ ] Documentation updated
- [ ] MCP Inspector testing completed

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How has this been tested?

## Checklist
- [ ] Tests pass
- [ ] Code formatted
- [ ] Documentation updated
- [ ] Tested with MCP Inspector
```

## Common Tasks

### Adding a Docker Service

1. Add to `docker-compose.yml`:
   ```yaml
   myservice:
     image: myorg/myservice:latest
     ports:
       - "9999:9999"
     environment:
       - MY_ENV_VAR=value
     healthcheck:
       test: ["CMD", "curl", "-f", "http://localhost:9999/health"]
       interval: 30s
   ```

2. Add config in `config.py`:
   ```python
   "services": {
       "myservice": {
           "host": "localhost",
           "port": 9999,
       }
   }
   ```

3. Update `Makefile` status check
4. Update README.md

### Adding a Configuration Option

1. Add to `config.py` DEFAULTS:
   ```python
   DEFAULTS = {
       "myfeature": {
           "enabled": True,
           "timeout": 30,
       }
   }
   ```

2. Document in README.md Configuration section
3. Add example to `config/config.example.yml`

## Getting Help

- **Questions?** Open a [Discussion](https://github.com/Enablement-Engineering/gobbler/discussions)
- **Bug?** Open an [Issue](https://github.com/Enablement-Engineering/gobbler/issues)
- **Chat?** Join our community (coming soon)

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other contributors

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

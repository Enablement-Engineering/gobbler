## Description
Brief description of the changes in this PR.

## Related Issue
Fixes #(issue number)

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Test coverage improvement

## Changes Made
-
-
-

## How Has This Been Tested?
Describe the tests you ran to verify your changes:
- [ ] Unit tests
- [ ] Integration tests
- [ ] Manual testing

**Test Environment:**
- OS:
- Python Version:

## Screenshots (if applicable)

## Checklist
- [ ] Formatting and lint pass (`uv run ruff format --check src/ tests/` and `uv run ruff check src/ tests/`)
- [ ] I reviewed type-checking output where relevant (mypy is currently advisory in CI)
- [ ] I have added tests that prove my fix/feature works
- [ ] Unit tests pass (`uv run pytest tests/unit/ -v --cov=src/gobbler_core --cov=src/gobbler_cli --cov=src/gobbler_relay --cov=src/gobbler_queue --cov-report=term-missing --cov-fail-under=0`)
- [ ] I have updated documentation as needed
- [ ] My changes generate no new warnings
- [ ] Any dependent changes have been merged and published

## Breaking Changes
If this PR introduces breaking changes, describe them here and explain the migration path.

## Additional Notes
Any additional information that reviewers should know.

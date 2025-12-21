# PRD-015: Project Configuration Improvements

## Overview
**Epic**: Developer Experience & CI/CD  
**Phase**: Infrastructure  
**Status**: Pending  
**Effort**: 1-2 days  
**Dependencies**: None  
**Priority**: Medium  

## Problem Statement

The project configuration has several issues that affect development experience and CI reliability:

### Critical Issues

1. **Python version mismatch**:
   - `pyproject.toml` line 9: `requires-python = ">=3.11"`
   - `pyproject.toml` line 108: `tool.mypy.python_version = "3.10"`
   - `pyproject.toml` line 116: `tool.ruff.target-version = "py310"`

2. **CI type checking disabled**:
   - `.github/workflows/test.yml`: `continue-on-error: true` on mypy
   - Type errors are silently ignored

3. **Security: Default API token exposed**:
   - `docker-compose.yml`: `CRAWL4AI_API_TOKEN=${CRAWL4AI_API_TOKEN:-gobbler-local-token}`
   - Should require explicit configuration

### Configuration Gaps

4. **Sparse .env.example**:
   - Only contains 1 variable (`GOBBLER_MODELS_PATH`)
   - Missing Redis, service URLs, log level, etc.

5. **Missing isort configuration**:
   - `gobbler_core` not in known-first-party

6. **No security scanning workflow**:
   - No Dependabot, CodeQL, or OSSF Scorecard

7. **Docker tilde expansion issue**:
   - `${GOBBLER_MODELS_PATH:-~/.gobbler/models}` may not expand in docker-compose

## Success Criteria

- [ ] Python version consistent (3.11) across all tools
- [ ] CI type checking enabled (no continue-on-error)
- [ ] Security token requires explicit configuration
- [ ] .env.example comprehensive
- [ ] isort includes gobbler_core
- [ ] Security scanning workflow added
- [ ] Docker paths work correctly

## Technical Requirements

### 1. Fix Python Version Mismatch

Update `pyproject.toml`:

```toml
# Line 108
[tool.mypy]
python_version = "3.11"  # Changed from "3.10"

# Line 116
[tool.ruff]
target-version = "py311"  # Changed from "py310"
```

### 2. Enable CI Type Checking

Update `.github/workflows/test.yml`:

```yaml
# Before
- name: Type checking with mypy
  run: uv run mypy src/gobbler_mcp --ignore-missing-imports
  continue-on-error: true  # DELETE THIS LINE

# After
- name: Type checking with mypy
  run: uv run mypy src/gobbler_mcp --ignore-missing-imports
  # No continue-on-error - type errors will fail the build
```

Also fix integration tests:
```yaml
# Before
integration-tests:
  ...
  continue-on-error: true  # DELETE THIS LINE
```

### 3. Secure Default Tokens

Update `docker-compose.yml`:

```yaml
# Before
environment:
  - CRAWL4AI_API_TOKEN=${CRAWL4AI_API_TOKEN:-gobbler-local-token}

# After
environment:
  # SECURITY: Set CRAWL4AI_API_TOKEN in .env for production
  - CRAWL4AI_API_TOKEN=${CRAWL4AI_API_TOKEN:?Set CRAWL4AI_API_TOKEN in .env}
```

For development convenience, add note to .env.example:
```bash
# For local development only - change in production!
CRAWL4AI_API_TOKEN=gobbler-local-dev-token
```

### 4. Complete .env.example

Create comprehensive `.env.example`:

```bash
# Gobbler MCP Server Environment Variables
# Copy this file to .env and customize for your environment

# =============================================================================
# Model Configuration
# =============================================================================

# Directory for downloaded AI models (Whisper, etc.)
GOBBLER_MODELS_PATH=~/.gobbler/models

# =============================================================================
# Service URLs
# =============================================================================

# Crawl4AI web scraping service
CRAWL4AI_URL=http://localhost:11235
CRAWL4AI_API_TOKEN=gobbler-local-dev-token

# Docling document conversion service
DOCLING_URL=http://localhost:5001

# Browser extension relay server
RELAY_HOST=127.0.0.1
RELAY_PORT=4625

# =============================================================================
# Redis Configuration
# =============================================================================

# Redis for job queuing (uses non-standard port to avoid conflicts)
REDIS_HOST=localhost
REDIS_PORT=6380
REDIS_DB=0
# REDIS_PASSWORD=  # Uncomment and set for production

# =============================================================================
# Logging & Monitoring
# =============================================================================

# Log level: DEBUG, INFO, WARNING, ERROR
GOBBLER_LOG_LEVEL=INFO

# Log format: text (human-readable) or json (structured)
GOBBLER_LOG_FORMAT=text

# Enable Prometheus metrics endpoint
GOBBLER_METRICS_ENABLED=false
GOBBLER_METRICS_PORT=9090

# =============================================================================
# Worker Configuration
# =============================================================================

# Queues for background workers
GOBBLER_WORKER_QUEUES=default,transcription,download

# Maximum job execution time in seconds
GOBBLER_JOB_TIMEOUT=600

# Auto-queue threshold in seconds (jobs longer than this are queued)
GOBBLER_AUTO_QUEUE_THRESHOLD=105

# =============================================================================
# YouTube Configuration
# =============================================================================

# Webshare rotating proxy (optional - improves reliability)
# WEBSHARE_USER=your-username
# WEBSHARE_PASS=your-password

# Generic proxy URL (optional)
# YOUTUBE_PROXY=http://proxy:port

# Paid transcript API key (optional fallback)
# TRANSCRIPTAPI_KEY=your-api-key
```

### 5. Fix isort Configuration

Update `pyproject.toml`:

```toml
[tool.ruff.lint.isort]
known-first-party = ["gobbler_mcp", "gobbler_relay", "gobbler_core"]  # Added gobbler_core
combine-as-imports = true
```

### 6. Add Security Scanning Workflow

Create `.github/workflows/security.yml`:

```yaml
name: Security

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday

permissions:
  contents: read
  security-events: write

jobs:
  codeql:
    name: CodeQL Analysis
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: python

      - name: Autobuild
        uses: github/codeql-action/autobuild@v3

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v3

  dependency-review:
    name: Dependency Review
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Dependency Review
        uses: actions/dependency-review-action@v4

  bandit:
    name: Bandit Security Scan
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install bandit
        run: pip install bandit

      - name: Run Bandit
        run: bandit -c pyproject.toml -r src/ -f json -o bandit-report.json || true

      - name: Upload Bandit Report
        uses: actions/upload-artifact@v4
        with:
          name: bandit-report
          path: bandit-report.json
```

Create `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    groups:
      python-dependencies:
        patterns:
          - "*"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      actions:
        patterns:
          - "*"
```

### 7. Fix Docker Volume Path

Update `docker-compose.yml`:

```yaml
# Before
volumes:
  - ${GOBBLER_MODELS_PATH:-~/.gobbler/models}:/models

# After (use $HOME instead of ~)
volumes:
  - ${GOBBLER_MODELS_PATH:-${HOME}/.gobbler/models}:/models
```

### 8. Add Missing Makefile Targets

Update `Makefile`:

```makefile
# Add these targets

.PHONY: lint
lint:  ## Run linter (ruff check + format)
	@echo "🔍 Running linter..."
	uv run ruff check src/ --fix
	uv run ruff format src/

.PHONY: security
security:  ## Run security checks (bandit)
	@echo "🔒 Running security scan..."
	uv run bandit -c pyproject.toml -r src/

.PHONY: typecheck
typecheck:  ## Run type checker (mypy)
	@echo "📝 Running type checker..."
	uv run mypy src/gobbler_mcp src/gobbler_core src/gobbler_relay
```

### 9. Add Docker Logging Limits

Update `docker-compose.yml` for all services:

```yaml
services:
  crawl4ai:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    # ... rest of config

  docling:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    # ... rest of config

  redis:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    # ... rest of config
```

## Implementation Plan

### Phase 1: Critical Fixes (Day 1)
- Fix Python version mismatch
- Enable CI type checking
- Fix existing type errors (or add # type: ignore temporarily)

### Phase 2: Configuration Improvements (Day 1)
- Complete .env.example
- Fix isort configuration
- Fix Docker volume path
- Add Docker logging limits

### Phase 3: Security & CI (Day 2)
- Add security scanning workflow
- Add Dependabot configuration
- Secure default tokens
- Add Makefile targets

## Files to Create

```
.github/workflows/security.yml     # Security scanning
.github/dependabot.yml             # Dependency updates
```

## Files to Modify

```
pyproject.toml                     # Fix Python version, isort
.github/workflows/test.yml         # Remove continue-on-error
docker-compose.yml                 # Secure tokens, fix paths, add logging
.env.example                       # Comprehensive example
Makefile                           # Add lint, security, typecheck targets
```

## Acceptance Criteria

### Configuration
- [ ] Python version 3.11 everywhere
- [ ] isort includes gobbler_core
- [ ] .env.example has all variables
- [ ] Docker paths work on all systems

### CI/CD
- [ ] Type checking fails build on errors
- [ ] Integration tests fail build on errors
- [ ] Security scanning runs weekly
- [ ] Dependabot enabled

### Security
- [ ] No default tokens in production
- [ ] Docker logs don't fill disk
- [ ] Bandit scan passes

## Metrics

### Before
- Type checking: disabled in CI
- Security scanning: none
- .env.example: 1 variable
- CI failures: hidden by continue-on-error

### After
- Type checking: enabled, fails on error
- Security scanning: CodeQL + Bandit + Dependabot
- .env.example: 20+ variables
- CI failures: visible and blocking

## Definition of Done

- [ ] Python version consistent (3.11)
- [ ] CI type checking enabled
- [ ] Security workflows added
- [ ] Dependabot configured
- [ ] .env.example complete
- [ ] Docker configuration fixed
- [ ] Makefile targets added
- [ ] All CI checks pass
- [ ] Documentation updated

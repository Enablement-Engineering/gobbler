.PHONY: help install dev test clean start start-docker stop restart logs status worker worker-stop claude-install claude-uninstall verify diagnose lint security typecheck docs docs-serve docs-build docs-deploy

# Default target - Show available commands and their descriptions
# Use this to get started or find the right command for your task
help:
	@echo "Gobbler MCP Server - Available Commands"
	@echo "========================================"
	@echo ""
	@echo "🚀 Quick Start:"
	@echo "  make start          - Start everything (Docker services + RQ worker)"
	@echo "  make verify         - Verify installation and check system health"
	@echo ""
	@echo "🐳 Docker Services:"
	@echo "  make start-docker   - Start Docker services only (Crawl4AI, Docling)"
	@echo "  make stop           - Stop all Docker services"
	@echo "  make restart        - Restart all Docker services"
	@echo "  make logs           - View logs from all services"
	@echo "  make status         - Check status of all services"
	@echo ""
	@echo "🔧 Background Workers:"
	@echo "  make worker         - Start RQ worker for background tasks"
	@echo "  make worker-stop    - Stop running RQ workers"
	@echo ""
	@echo "📦 Installation:"
	@echo "  make install        - Install Gobbler MCP dependencies"
	@echo "  make dev            - Install with development dependencies"
	@echo ""
	@echo "🤖 Claude Code Integration:"
	@echo "  make claude-install - Add Gobbler to Claude Code MCP servers"
	@echo "  make claude-uninstall - Remove Gobbler from Claude Code"
	@echo "  make claude-config  - Show Claude Code configuration snippet"
	@echo ""
	@echo "🧪 Testing & Diagnostics:"
	@echo "  make test           - Run tests"
	@echo "  make lint           - Run linter (ruff)"
	@echo "  make security       - Run security scan (bandit)"
	@echo "  make typecheck      - Run type checker (mypy)"
	@echo "  make inspector      - Launch MCP inspector for testing"
	@echo "  make diagnose       - Run diagnostics and suggest fixes for common issues"
	@echo ""
	@echo "📚 Documentation:"
	@echo "  make docs           - Serve documentation locally (alias for docs-serve)"
	@echo "  make docs-serve     - Serve documentation at http://localhost:8000"
	@echo "  make docs-build     - Build static documentation site"
	@echo "  make docs-deploy    - Deploy documentation to GitHub Pages"
	@echo ""
	@echo "🧹 Cleanup:"
	@echo "  make clean          - Remove build artifacts and cache"

# ============================================================================
# Installation Targets
# ============================================================================

# Install Gobbler MCP with core dependencies only
# Use this for production or if you don't need testing tools
install:
	@echo "📦 Installing Gobbler MCP..."
	uv pip install -e .

# Install Gobbler MCP with development dependencies (pytest, mypy, ruff, etc.)
# Use this if you're developing or contributing to Gobbler
dev:
	@echo "📦 Installing Gobbler MCP with dev dependencies..."
	uv pip install -e ".[dev]"

# ============================================================================
# Service Management Targets
# ============================================================================

# Start all services: Docker containers + background RQ worker
# This is your one-stop command to get Gobbler fully operational
# Runs: Crawl4AI, Docling, and background worker
start:
	@echo "🚀 Starting Gobbler (Docker services + RQ worker)..."
	@echo ""
	@make start-docker
	@echo ""
	@echo "🔧 Starting RQ worker in background..."
	@nohup uv run python -m gobbler_queue.worker > gobbler_worker.log 2>&1 & echo $$! > .worker.pid
	@sleep 2
	@if ps -p $$(cat .worker.pid) > /dev/null 2>&1; then \
		echo "✅ Worker started (PID: $$(cat .worker.pid))"; \
		echo "   Log file: gobbler_worker.log"; \
	else \
		echo "❌ Worker failed to start. Check gobbler_worker.log"; \
	fi
	@echo ""
	@echo "🎉 Gobbler is ready! Use 'make worker-stop' to stop the worker."

# Start only Docker services (Crawl4AI, Docling)
# Use this if you want to manage the worker separately
# The services will run in background (detached mode)
start-docker:
	@echo "🐳 Starting Docker services..."
	docker-compose up -d
	@echo ""
	@echo "✅ Services starting..."
	@echo "   - Crawl4AI: http://localhost:11235"
	@echo "   - Docling:  http://localhost:5001"
	@echo ""
	@echo "⏳ Waiting for services to be ready (this may take 30-60 seconds)..."
	@sleep 5
	@make status

# Stop all Docker services
# This will gracefully shut down Crawl4AI and Docling containers
stop:
	@echo "🛑 Stopping Docker services..."
	docker-compose down

# Restart all Docker services
# Useful when services are unresponsive or after configuration changes
restart:
	@echo "🔄 Restarting Docker services..."
	docker-compose restart
	@sleep 5
	@make status

# View live logs from all Docker services
# Press Ctrl+C to exit log viewing
# Useful for debugging service issues
logs:
	@echo "📋 Viewing service logs (Ctrl+C to exit)..."
	docker-compose logs -f

# Check health status of all services
# Shows container status and performs health checks on each service
# Use this to verify services are running correctly
status:
	@echo "📊 Service Status:"
	@echo ""
	@docker-compose ps
	@echo ""
	@echo "🏥 Health Checks:"
	@echo -n "   Crawl4AI: "
	@curl -sf http://localhost:11235/health > /dev/null && echo "✅ Healthy" || echo "❌ Unavailable"
	@echo -n "   Docling:  "
	@curl -sf http://localhost:5001/health > /dev/null && echo "✅ Healthy" || echo "❌ Unavailable"

# ============================================================================
# Worker Management Targets
# ============================================================================

# Start RQ worker in foreground
# Processes background tasks from queues: default, transcription, download
# Keep this running in a terminal while using Gobbler for long tasks
# Press Ctrl+C to stop
worker:
	@echo "🔧 Starting RQ worker..."
	@echo "   Processing queues: default, transcription, download"
	@echo "   Press Ctrl+C to stop"
	@echo ""
	uv run python -m gobbler_queue.worker

# Stop any running RQ workers
# Attempts to kill both background workers (started by 'make start')
# and any workers started manually
worker-stop:
	@echo "🛑 Stopping RQ workers..."
	@if [ -f .worker.pid ]; then \
		kill $$(cat .worker.pid) 2>/dev/null && echo "✅ Worker stopped (PID: $$(cat .worker.pid))" || echo "⚠️  Worker already stopped"; \
		rm -f .worker.pid; \
	else \
		pkill -f "gobbler_queue.worker" && echo "✅ Workers stopped" || echo "⚠️  No workers running"; \
	fi

# ============================================================================
# Claude Code Integration Targets
# ============================================================================

# Install Gobbler MCP into Claude Code
# Shows the command you need to run to add Gobbler to Claude Code
# After running, restart Claude Code to use Gobbler tools
claude-install:
	@echo "🤖 Installing Gobbler MCP to Claude Code..."
	@echo ""
	@echo "Run this command to add Gobbler to Claude Code:"
	@echo ""
	@echo "claude mcp add --scope user gobbler -- uv --directory $(PWD) run gobbler-mcp"
	@echo ""
	@echo "Then restart Claude Code for the changes to take effect."
	@echo ""
	@echo "Verify installation with: claude mcp list"

# Remove Gobbler MCP from Claude Code
# Shows the command to uninstall Gobbler from Claude Code
claude-uninstall:
	@echo "🗑️  Removing Gobbler MCP from Claude Code..."
	@echo ""
	@echo "Run this command:"
	@echo ""
	@echo "claude mcp remove gobbler-mcp"

# Show the resulting configuration for reference
# Note: Do NOT manually create .mcp.json - use 'claude mcp add' instead
claude-config:
	@echo ""
	@echo "📝 Reference: This is what Claude Code stores in ~/.claude.json"
	@echo "   (Do NOT manually edit - use 'claude mcp add' command instead)"
	@echo ""
	@echo '  "gobbler": {'
	@echo '    "type": "stdio",'
	@echo '    "command": "uv",'
	@echo '    "args": ['
	@echo '      "--directory",'
	@echo '      "$(PWD)",'
	@echo '      "run",'
	@echo '      "gobbler-mcp"'
	@echo '    ]'
	@echo '  }'
	@echo ""

# ============================================================================
# Testing & Diagnostics Targets
# ============================================================================

# Run the test suite
# Requires dev dependencies: make dev
# Runs pytest with coverage reporting
test:
	@echo "🧪 Running tests..."
	uv run pytest tests/unit/ tests/integration/test_mcp_tools.py -v

# Run linting with ruff
# Checks code style, formatting, and common issues
lint:
	@echo "🔍 Running linter (ruff)..."
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

# Run security checks with bandit
# Scans for common security vulnerabilities in Python code
security:
	@echo "🔒 Running security scan (bandit)..."
	uv run bandit -r src/ -c pyproject.toml

# Run type checking with mypy
# Validates type annotations and catches type errors
typecheck:
	@echo "🔎 Running type checker (mypy)..."
	uv run mypy src/

# Run unit tests only (fast)
test-unit:
	@echo "🧪 Running unit tests..."
	uv run pytest tests/unit/ -v

# Run integration tests only (requires Docker for some tests)
test-integration:
	@echo "🧪 Running integration tests..."
	uv run pytest tests/integration/ -v

# Run all tests including E2E (requires Docker services)
test-all:
	@echo "🧪 Running all tests (unit + integration + E2E)..."
	uv run pytest tests/ -v --ignore=tests/benchmarks/

# Launch the MCP Inspector for interactive testing
# Opens a web interface at http://localhost:5173 to test MCP tools
# Useful for debugging tool behavior without using Claude
inspector:
	@echo "🔍 Launching MCP Inspector..."
	@echo "   Opening http://localhost:5173 in browser..."
	npx @modelcontextprotocol/inspector uv --directory $(PWD) run gobbler-mcp

# ============================================================================
# Cleanup Targets
# ============================================================================

# Remove all build artifacts, caches, and temporary files
# Safe to run - doesn't affect configuration or data
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf site/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "✅ Cleanup complete"

# ============================================================================
# Documentation Targets
# ============================================================================

# Serve documentation locally (alias)
docs: docs-serve

# Serve documentation locally with live reload
# Opens http://localhost:8000 for previewing documentation
docs-serve:
	@echo "📚 Serving documentation at http://localhost:8000..."
	@echo "   Press Ctrl+C to stop"
	@echo ""
	uv run --extra docs mkdocs serve

# Build static documentation site
# Output goes to site/ directory
docs-build:
	@echo "📚 Building documentation..."
	uv run --extra docs mkdocs build
	@echo "✅ Documentation built to site/"

# Deploy documentation to GitHub Pages
# Pushes to gh-pages branch automatically
docs-deploy:
	@echo "📚 Deploying documentation to GitHub Pages..."
	uv run --extra docs mkdocs gh-deploy --force
	@echo "✅ Documentation deployed!"

# ============================================================================
# Verification & Diagnostics Targets
# ============================================================================

# Verify installation and system health
# Checks all prerequisites and validates that Gobbler is ready to use
# Run this after installation or if you encounter issues
verify:
	@echo "🔍 Verifying Gobbler Installation..."
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "📋 Prerequisites Check"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo -n "✓ Python version: "
	@python3 --version 2>/dev/null || (echo "❌ Python 3.11+ required" && echo "   Install: https://www.python.org/downloads/" && false)
	@python3 -c 'import sys; exit(0 if sys.version_info >= (3, 11) else 1)' && echo "   ✅ Python 3.11+ detected" || (echo "   ❌ Python 3.11+ required (found: $$(python3 --version))" && echo "   Install: https://www.python.org/downloads/" && false)
	@echo ""
	@echo -n "✓ uv package manager: "
	@which uv > /dev/null 2>&1 && echo "✅ Installed ($$(uv --version))" || (echo "❌ Not installed" && echo "   Install: curl -LsSf https://astral.sh/uv/install.sh | sh" && false)
	@echo ""
	@echo -n "✓ Docker: "
	@docker --version > /dev/null 2>&1 && echo "✅ Installed ($$(docker --version | cut -d' ' -f3 | tr -d ','))" || echo "⚠️  Not installed (optional, needed for web/document conversion)"
	@echo ""
	@echo -n "✓ Docker Compose: "
	@docker-compose --version > /dev/null 2>&1 && echo "✅ Installed" || echo "⚠️  Not installed (optional, needed for web/document conversion)"
	@echo ""
	@echo -n "✓ ffmpeg: "
	@which ffmpeg > /dev/null 2>&1 && echo "✅ Installed ($$(ffmpeg -version 2>&1 | head -n1 | cut -d' ' -f3))" || echo "⚠️  Not installed (needed for audio extraction from video files)"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🐍 Python Environment Check"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo -n "✓ Gobbler MCP installed: "
	@uv pip show gobbler-mcp > /dev/null 2>&1 && echo "✅ Yes" || (echo "❌ No" && echo "   Fix: Run 'make install'" && false)
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "📁 Configuration Check"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo -n "✓ Config file: "
	@if [ -f "$$HOME/.config/gobbler/config.yml" ]; then \
		echo "✅ Found ($$HOME/.config/gobbler/config.yml)"; \
	else \
		echo "⚠️  Not found (will use defaults)"; \
		echo "   Optional: Create custom config at $$HOME/.config/gobbler/config.yml"; \
	fi
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🐳 Docker Services Health"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@if docker --version > /dev/null 2>&1; then \
		if docker ps > /dev/null 2>&1; then \
			echo "✓ Docker daemon: ✅ Running"; \
			echo ""; \
			echo -n "✓ Crawl4AI service: "; \
			curl -sf http://localhost:11235/health > /dev/null 2>&1 && echo "✅ Healthy (http://localhost:11235)" || echo "❌ Unavailable (start with: make start-docker)"; \
			echo -n "✓ Docling service: "; \
			curl -sf http://localhost:5001/health > /dev/null 2>&1 && echo "✅ Healthy (http://localhost:5001)" || echo "❌ Unavailable (start with: make start-docker)"; \
		else \
			echo "✓ Docker daemon: ❌ Not running"; \
			echo "   Fix: Start Docker Desktop or docker service"; \
		fi; \
	else \
		echo "✓ Docker: ⚠️  Not installed (services unavailable)"; \
	fi
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🎉 Verification Complete!"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "Next steps:"
	@echo "  • Start services: make start"
	@echo "  • Run diagnostics: make diagnose"
	@echo "  • Install to Claude: make claude-install"
	@echo ""

# Run comprehensive diagnostics and suggest fixes
# Use this when troubleshooting issues or getting started
# Provides actionable recommendations for common problems
diagnose:
	@echo "🔬 Running Gobbler Diagnostics..."
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🔍 System Diagnostics"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@ISSUES=0; \
	if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then \
		echo "❌ ISSUE: Python 3.11+ not found"; \
		echo "   Solution: Install Python 3.11 or higher from https://www.python.org/downloads/"; \
		echo "   Current: $$(python3 --version 2>/dev/null || echo 'Not installed')"; \
		echo ""; \
		ISSUES=$$((ISSUES+1)); \
	fi; \
	if ! which uv > /dev/null 2>&1; then \
		echo "❌ ISSUE: uv package manager not installed"; \
		echo "   Solution: Run this command:"; \
		echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		echo ""; \
		ISSUES=$$((ISSUES+1)); \
	fi; \
	if ! uv pip show gobbler-mcp > /dev/null 2>&1; then \
		echo "❌ ISSUE: Gobbler MCP not installed"; \
		echo "   Solution: Run 'make install' to install dependencies"; \
		echo ""; \
		ISSUES=$$((ISSUES+1)); \
	fi; \
	if docker --version > /dev/null 2>&1; then \
		if ! docker ps > /dev/null 2>&1; then \
			echo "⚠️  WARNING: Docker daemon not running"; \
			echo "   Impact: Web scraping and document conversion unavailable"; \
			echo "   Solution: Start Docker Desktop or run 'sudo systemctl start docker'"; \
			echo ""; \
			ISSUES=$$((ISSUES+1)); \
		else \
			if ! curl -sf http://localhost:11235/health > /dev/null 2>&1; then \
				echo "⚠️  WARNING: Crawl4AI service unavailable"; \
				echo "   Impact: Web scraping tools will not work"; \
				echo "   Solution: Run 'make start-docker' to start services"; \
				echo ""; \
			fi; \
			if ! curl -sf http://localhost:5001/health > /dev/null 2>&1; then \
				echo "⚠️  WARNING: Docling service unavailable"; \
				echo "   Impact: Document conversion tools will not work"; \
				echo "   Solution: Run 'make start-docker' to start services"; \
				echo ""; \
			fi; \
		fi; \
	else \
		echo "ℹ️  INFO: Docker not installed"; \
		echo "   Impact: Web scraping and document conversion unavailable"; \
		echo "   Note: YouTube and audio transcription still work!"; \
		echo "   Optional: Install Docker from https://docs.docker.com/get-docker/"; \
		echo ""; \
	fi; \
	if ! which ffmpeg > /dev/null 2>&1; then \
		echo "⚠️  WARNING: ffmpeg not installed"; \
		echo "   Impact: Cannot extract audio from video files"; \
		echo "   Solution: Install ffmpeg:"; \
		echo "     macOS:  brew install ffmpeg"; \
		echo "     Ubuntu: sudo apt-get install ffmpeg"; \
		echo "     Windows: Download from https://ffmpeg.org/download.html"; \
		echo ""; \
	fi; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	echo "🔌 Network Connectivity Tests"; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	echo ""; \
	if docker ps > /dev/null 2>&1; then \
		echo -n "Testing Crawl4AI (localhost:11235)... "; \
		if timeout 5 curl -sf http://localhost:11235/health > /dev/null 2>&1; then \
			echo "✅ OK"; \
		else \
			echo "❌ FAILED"; \
			echo "   Troubleshooting:"; \
			echo "   1. Check if container is running: docker ps | grep crawl4ai"; \
			echo "   2. Check container logs: docker logs gobbler-crawl4ai"; \
			echo "   3. Try restarting: make restart"; \
		fi; \
		echo ""; \
		echo -n "Testing Docling (localhost:5001)... "; \
		if timeout 5 curl -sf http://localhost:5001/health > /dev/null 2>&1; then \
			echo "✅ OK"; \
		else \
			echo "❌ FAILED"; \
			echo "   Troubleshooting:"; \
			echo "   1. Check if container is running: docker ps | grep docling"; \
			echo "   2. Check container logs: docker logs gobbler-docling"; \
			echo "   3. Try restarting: make restart"; \
		fi; \
		echo ""; \
	fi; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	echo "📊 Diagnosis Summary"; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	echo ""; \
	if [ $$ISSUES -eq 0 ]; then \
		echo "✅ All critical checks passed!"; \
		echo ""; \
		echo "Gobbler is ready to use. Try:"; \
		echo "  • make start          # Start all services"; \
		echo "  • make claude-install # Install to Claude Code"; \
		echo ""; \
	else \
		echo "⚠️  Found $$ISSUES issue(s) requiring attention."; \
		echo ""; \
		echo "Please address the issues above before using Gobbler."; \
		echo ""; \
	fi; \
	echo "Common issues and solutions:"; \
	echo "  • Services won't start → Run 'make start-docker'"; \
	echo "  • Permission denied → Run 'chmod +x' on script files"; \
	echo "  • Port already in use → Check for conflicts with docker ps -a"; \
	echo "  • Still having issues? → Check logs with 'make logs'"; \
	echo ""

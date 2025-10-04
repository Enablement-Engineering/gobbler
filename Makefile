.PHONY: help install dev test clean start start-docker stop restart logs status worker worker-stop claude-install claude-uninstall

# Default target
help:
	@echo "Gobbler MCP Server - Available Commands"
	@echo "========================================"
	@echo ""
	@echo "🚀 Quick Start:"
	@echo "  make start          - Start everything (Docker services + RQ worker)"
	@echo ""
	@echo "🐳 Docker Services:"
	@echo "  make start-docker   - Start Docker services only (Crawl4AI, Docling, Redis)"
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
	@echo "🧪 Testing:"
	@echo "  make test           - Run tests"
	@echo "  make inspector      - Launch MCP inspector for testing"
	@echo ""
	@echo "🧹 Cleanup:"
	@echo "  make clean          - Remove build artifacts and cache"

# Installation
install:
	@echo "📦 Installing Gobbler MCP..."
	uv pip install -e .

dev:
	@echo "📦 Installing Gobbler MCP with dev dependencies..."
	uv pip install -e ".[dev]"

# Docker service management
start:
	@echo "🚀 Starting Gobbler (Docker services + RQ worker)..."
	@echo ""
	@make start-docker
	@echo ""
	@echo "🔧 Starting RQ worker in background..."
	@nohup uv run python -m gobbler_mcp.worker > gobbler_worker.log 2>&1 & echo $$! > .worker.pid
	@sleep 2
	@if ps -p $$(cat .worker.pid) > /dev/null 2>&1; then \
		echo "✅ Worker started (PID: $$(cat .worker.pid))"; \
		echo "   Log file: gobbler_worker.log"; \
	else \
		echo "❌ Worker failed to start. Check gobbler_worker.log"; \
	fi
	@echo ""
	@echo "🎉 Gobbler is ready! Use 'make worker-stop' to stop the worker."

start-docker:
	@echo "🐳 Starting Docker services..."
	docker-compose up -d
	@echo ""
	@echo "✅ Services starting..."
	@echo "   - Crawl4AI: http://localhost:11235"
	@echo "   - Docling:  http://localhost:5001"
	@echo "   - Redis:    localhost:6380"
	@echo ""
	@echo "⏳ Waiting for services to be ready (this may take 30-60 seconds)..."
	@sleep 5
	@make status

stop:
	@echo "🛑 Stopping Docker services..."
	docker-compose down

restart:
	@echo "🔄 Restarting Docker services..."
	docker-compose restart
	@sleep 5
	@make status

logs:
	@echo "📋 Viewing service logs (Ctrl+C to exit)..."
	docker-compose logs -f

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
	@echo -n "   Redis:    "
	@docker exec gobbler-redis redis-cli ping > /dev/null 2>&1 && echo "✅ Healthy" || echo "❌ Unavailable"

# Worker management
worker:
	@echo "🔧 Starting RQ worker..."
	@echo "   Processing queues: default, transcription, download"
	@echo "   Press Ctrl+C to stop"
	@echo ""
	uv run python -m gobbler_mcp.worker

worker-stop:
	@echo "🛑 Stopping RQ workers..."
	@if [ -f .worker.pid ]; then \
		kill $$(cat .worker.pid) 2>/dev/null && echo "✅ Worker stopped (PID: $$(cat .worker.pid))" || echo "⚠️  Worker already stopped"; \
		rm -f .worker.pid; \
	else \
		pkill -f "gobbler_mcp.worker" && echo "✅ Workers stopped" || echo "⚠️  No workers running"; \
	fi

# Claude Code integration
claude-install:
	@echo "🤖 Installing Gobbler MCP to Claude Code..."
	@echo ""
	@echo "Run this command to add Gobbler to Claude Code:"
	@echo ""
	@echo "claude mcp add gobbler-mcp -- uv --directory $(PWD) run gobbler-mcp"
	@echo ""
	@echo "Or manually add to your .mcp.json:"
	@make claude-config

claude-uninstall:
	@echo "🗑️  Removing Gobbler MCP from Claude Code..."
	@echo ""
	@echo "Run this command:"
	@echo ""
	@echo "claude mcp remove gobbler-mcp"

claude-config:
	@echo ""
	@echo "📝 Add this to your .mcp.json file:"
	@echo ""
	@echo '{'
	@echo '  "mcpServers": {'
	@echo '    "gobbler-mcp": {'
	@echo '      "type": "stdio",'
	@echo '      "command": "uv",'
	@echo '      "args": ['
	@echo '        "--directory",'
	@echo '        "$(PWD)",'
	@echo '        "run",'
	@echo '        "gobbler-mcp"'
	@echo '      ]'
	@echo '    }'
	@echo '  }'
	@echo '}'
	@echo ""

# Testing
test:
	@echo "🧪 Running tests..."
	uv run pytest

inspector:
	@echo "🔍 Launching MCP Inspector..."
	@echo "   Opening http://localhost:5173 in browser..."
	npx @modelcontextprotocol/inspector uv --directory $(PWD) run gobbler-mcp

# Cleanup
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "✅ Cleanup complete"

---
name: gobbler-utils
description: Shared utilities for Gobbler content conversion skills. Provides frontmatter generation, output formatting, and Docker service health checks. Other gobbler-* skills depend on these utilities.
version: 2.0.0
---

# Gobbler Utilities

Shared utilities for managing Gobbler services and checking system health.

## Service Health Checks

### Using the CLI

```bash
# Check daemon status
gobbler daemon status

# View daemon logs
gobbler daemon logs
gobbler daemon logs --follow
```

### Using curl

```bash
# Check Docling (port 5001)
curl http://localhost:5001/health

# Check Crawl4AI (port 11235)
curl http://localhost:11235/health

# Check Redis (port 6380)
redis-cli -p 6380 ping
```

## Service Management

```bash
# Start all Docker services
cd /path/to/gobbler
docker compose up -d

# Start specific service
docker compose up -d docling
docker compose up -d crawl4ai

# View service logs
docker logs gobbler-docling --tail 50
docker logs gobbler-crawl4ai --tail 50

# Restart a service
docker compose restart docling
```

## Daemon Management

```bash
# Start daemon (background)
gobbler daemon start

# Start daemon (foreground for debugging)
gobbler daemon start --foreground

# Stop daemon
gobbler daemon stop

# Restart daemon
gobbler daemon restart
```

## Notes

With Gobbler v2.0, most utilities are now built into the core packages:
- `gobbler_core` - Frontmatter generation, HTTP clients, file handling
- `gobbler_daemon` - Service health monitoring
- `gobbler_cli` - Command-line utilities

The old `uv run scripts/...` approach is deprecated in favor of the unified `gobbler` CLI.

# PRD-005: Hot-Reload Configuration

## Overview
**Epic**: Developer Experience & Operations
**Phase**: 2 - Feature Enhancement
**Estimated Effort**: 2-3 days
**Dependencies**: None - extends existing config system
**Parallel**: ✅ Can be implemented alongside other PRDs

## Problem Statement
Gobbler MCP currently requires a full server restart to apply configuration changes, which is disruptive for:
- Development workflows (testing different Whisper models, timeouts)
- Production operations (adjusting queue thresholds, service endpoints)
- Tuning performance parameters (concurrency, cache settings)
- Updating service credentials (API tokens, proxy settings)

Users must stop the MCP server, edit `~/.config/gobbler/config.yml`, and restart—losing any in-progress operations and requiring reconnection from Claude Code/Desktop.

**User Stories:**
- "As a developer, I want to change Whisper model settings without restarting so I can quickly test different configurations"
- "As an operator, I want to adjust queue thresholds during high load without interrupting service"
- "As a power user, I want to update Crawl4AI timeout settings based on target site performance"

## Success Criteria
- [ ] Configuration file changes detected automatically
- [ ] Config reloaded without server restart
- [ ] In-progress operations not interrupted
- [ ] New operations use updated config
- [ ] Validation errors prevent bad config from being applied
- [ ] Reload events logged for audit trail
- [ ] MCP tools continue working during reload
- [ ] Thread-safe config access

## Technical Requirements

### Configuration Reload System

#### 1. File Watcher Implementation

```python
# src/gobbler_mcp/config_watcher.py
import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
import yaml

logger = logging.getLogger(__name__)

class ConfigFileHandler(FileSystemEventHandler):
    """Watch configuration file for changes"""

    def __init__(self, config_path: Path, reload_callback: Callable):
        self.config_path = config_path
        self.reload_callback = reload_callback
        self.last_modified = 0
        self._debounce_seconds = 1.0  # Debounce rapid changes

    def on_modified(self, event):
        """Handle file modification events"""
        if isinstance(event, FileModifiedEvent):
            if Path(event.src_path) == self.config_path:
                import time
                current_time = time.time()

                # Debounce rapid changes (editors often write multiple times)
                if current_time - self.last_modified < self._debounce_seconds:
                    return

                self.last_modified = current_time
                logger.info(f"Configuration file changed: {self.config_path}")

                # Trigger reload callback
                asyncio.create_task(self.reload_callback())

class ConfigWatcher:
    """Watch and reload configuration file"""

    def __init__(self, config_path: Path, config_instance):
        self.config_path = config_path
        self.config = config_instance
        self.observer: Optional[Observer] = None
        self._running = False

    async def reload_config(self):
        """Reload configuration from file with validation"""
        try:
            logger.info("Reloading configuration...")

            # Read and parse new config
            with open(self.config_path, 'r') as f:
                new_config_data = yaml.safe_load(f)

            if not new_config_data:
                logger.warning("Configuration file is empty, keeping current config")
                return

            # Validate new config
            validation_errors = self._validate_config(new_config_data)
            if validation_errors:
                logger.error(
                    f"Configuration validation failed: {validation_errors}. "
                    "Keeping current configuration."
                )
                return

            # Merge with defaults (same as initial load)
            from .config import Config
            merged_config = Config._deep_merge(Config.DEFAULTS.copy(), new_config_data)

            # Apply new config atomically
            old_data = self.config.data
            self.config.data = merged_config

            logger.info(
                "Configuration reloaded successfully",
                extra={
                    "extra_fields": {
                        "config_path": str(self.config_path),
                        "changes": self._get_config_changes(old_data, merged_config),
                    }
                }
            )

        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in config file: {e}. Keeping current config.")
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}", exc_info=True)

    def _validate_config(self, config_data: dict) -> list:
        """Validate configuration structure and values"""
        errors = []

        # Validate Whisper model
        if 'whisper' in config_data:
            model = config_data['whisper'].get('model')
            if model and model not in ['tiny', 'base', 'small', 'medium', 'large']:
                errors.append(f"Invalid whisper.model: {model}")

        # Validate timeouts
        if 'crawl4ai' in config_data:
            timeout = config_data['crawl4ai'].get('timeout')
            max_timeout = config_data['crawl4ai'].get('max_timeout')
            if timeout and (timeout < 5 or timeout > 300):
                errors.append(f"crawl4ai.timeout must be between 5 and 300")
            if max_timeout and (max_timeout < timeout or max_timeout > 300):
                errors.append(f"crawl4ai.max_timeout must be >= timeout and <= 300")

        # Validate ports
        for service in ['crawl4ai', 'docling', 'whisper']:
            if 'services' in config_data and service in config_data['services']:
                port = config_data['services'][service].get('port')
                if port and (port < 1 or port > 65535):
                    errors.append(f"services.{service}.port must be between 1 and 65535")

        # Validate queue settings
        if 'queue' in config_data:
            threshold = config_data['queue'].get('auto_queue_threshold')
            if threshold and (threshold < 0 or threshold > 3600):
                errors.append(f"queue.auto_queue_threshold must be between 0 and 3600")

        # Validate Redis settings
        if 'redis' in config_data:
            redis_port = config_data['redis'].get('port')
            if redis_port and (redis_port < 1 or redis_port > 65535):
                errors.append(f"redis.port must be between 1 and 65535")

        return errors

    def _get_config_changes(self, old_config: dict, new_config: dict) -> dict:
        """Detect what changed between configs"""
        changes = {}

        def compare_dicts(old: dict, new: dict, prefix: str = ""):
            for key in set(old.keys()) | set(new.keys()):
                full_key = f"{prefix}.{key}" if prefix else key

                if key not in old:
                    changes[full_key] = {"added": new[key]}
                elif key not in new:
                    changes[full_key] = {"removed": old[key]}
                elif isinstance(old[key], dict) and isinstance(new[key], dict):
                    compare_dicts(old[key], new[key], full_key)
                elif old[key] != new[key]:
                    changes[full_key] = {"old": old[key], "new": new[key]}

        compare_dicts(old_config, new_config)
        return changes

    def start(self):
        """Start watching configuration file"""
        if self._running:
            logger.warning("Config watcher already running")
            return

        if not self.config_path.exists():
            logger.warning(f"Config file does not exist: {self.config_path}")
            return

        self.observer = Observer()
        event_handler = ConfigFileHandler(self.config_path, self.reload_config)

        # Watch the directory containing the config file
        watch_dir = self.config_path.parent
        self.observer.schedule(event_handler, str(watch_dir), recursive=False)
        self.observer.start()
        self._running = True

        logger.info(f"Started watching configuration file: {self.config_path}")

    def stop(self):
        """Stop watching configuration file"""
        if self.observer and self._running:
            self.observer.stop()
            self.observer.join()
            self._running = False
            logger.info("Stopped watching configuration file")
```

#### 2. Integration with Config System

```python
# src/gobbler_mcp/config.py (modifications)
from pathlib import Path
from typing import Any, Dict, Optional
import threading
import yaml
import logging

logger = logging.getLogger(__name__)

class Config:
    """Configuration loader and manager with hot-reload support"""

    # ... existing DEFAULTS ...

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Initialize configuration with optional hot-reload"""
        self.config_path = config_path or self._default_config_path()
        self.data = self._load_config()
        self._lock = threading.RLock()  # Thread-safe access
        self._watcher: Optional['ConfigWatcher'] = None

    def get(self, key: str, default: Any = None) -> Any:
        """
        Thread-safe configuration value retrieval.

        Args:
            key: Configuration key (e.g., "whisper.model")
            default: Default value if key not found

        Returns:
            Configuration value
        """
        with self._lock:
            keys = key.split(".")
            value = self.data
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value

    def enable_hot_reload(self):
        """Enable hot-reloading of configuration file"""
        if self._watcher is not None:
            logger.warning("Hot-reload already enabled")
            return

        from .config_watcher import ConfigWatcher
        self._watcher = ConfigWatcher(self.config_path, self)
        self._watcher.start()
        logger.info("Configuration hot-reload enabled")

    def disable_hot_reload(self):
        """Disable hot-reloading"""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
            logger.info("Configuration hot-reload disabled")

    def reload(self):
        """Manually trigger configuration reload"""
        if self._watcher:
            import asyncio
            asyncio.create_task(self._watcher.reload_config())
        else:
            logger.warning("Hot-reload not enabled, call enable_hot_reload() first")

    # ... rest of existing methods ...
```

#### 3. Server Integration

```python
# src/gobbler_mcp/server.py (modifications)
@asynccontextmanager
async def lifespan(app: FastMCP):
    """Application lifespan manager with hot-reload"""
    # Startup
    logger.info("Starting Gobbler MCP server...")
    config = get_config()
    logger.info(f"Configuration loaded from {config.config_path}")

    # Enable hot-reload if configured
    hot_reload_enabled = config.get("monitoring.config_hot_reload", True)
    if hot_reload_enabled:
        config.enable_hot_reload()
        logger.info("Configuration hot-reload enabled")

    # ... existing health checks ...

    logger.info("Gobbler MCP server started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Gobbler MCP server...")
    config.disable_hot_reload()
```

### Configuration File Structure

```yaml
# ~/.config/gobbler/config.yml

# Whisper transcription settings
whisper:
  model: small  # Changed from 'base' to 'small' - HOT RELOAD ✓
  language: auto

# Docling document conversion settings
docling:
  ocr: true
  vlm: false

# Crawl4AI web scraping settings
crawl4ai:
  timeout: 30  # Changed from 60 to 30 - HOT RELOAD ✓
  max_timeout: 120
  api_token: gobbler-local-token

# Output formatting
output:
  default_format: frontmatter
  timestamp_format: iso8601

# Service endpoints
services:
  crawl4ai:
    host: localhost
    port: 11235  # Changed from 11234 to 11235 - HOT RELOAD ✓
    api_token: gobbler-local-token
  docling:
    host: localhost
    port: 5001
  whisper:
    host: localhost
    port: 9000

# Redis queue backend
redis:
  host: localhost
  port: 6380  # Changed from 6379 to 6380 - HOT RELOAD ✓
  db: 0

# Queue management
queue:
  auto_queue_threshold: 105  # Changed from 120 to 105 - HOT RELOAD ✓
  default_queue: default

# Model storage path
models_path: ~/.gobbler/models

# Monitoring and logging (new section)
monitoring:
  config_hot_reload: true  # Enable/disable hot-reload
  log_changes: true        # Log config changes
```

### Dependencies

```toml
# Add to pyproject.toml
dependencies = [
    # ... existing dependencies ...
    "watchdog>=4.0.0",  # File system monitoring
]
```

### New MCP Tool (Optional)

```python
@mcp.tool()
async def reload_config() -> str:
    """
    Manually trigger configuration reload.

    Forces an immediate reload of the configuration file, useful for
    testing or when automatic detection doesn't trigger.

    Returns:
        Status message indicating success or failure
    """
    try:
        config = get_config()
        config.reload()
        return "Configuration reload triggered. Check logs for details."
    except Exception as e:
        logger.error(f"Failed to trigger config reload: {e}", exc_info=True)
        return f"Failed to reload configuration: {str(e)}"

@mcp.tool()
async def get_current_config() -> str:
    """
    Get current configuration values.

    Returns the currently active configuration in YAML format,
    useful for debugging and verification.

    Returns:
        Current configuration as formatted YAML
    """
    try:
        config = get_config()
        import yaml
        return yaml.dump(config.data, default_flow_style=False)
    except Exception as e:
        return f"Failed to retrieve configuration: {str(e)}"
```

## Acceptance Criteria

### 1. File Watching
- [ ] Configuration file changes detected automatically
- [ ] Debouncing prevents multiple rapid reloads
- [ ] Works on macOS, Linux, and Windows
- [ ] No polling (event-based detection)

### 2. Configuration Reload
- [ ] Config reloaded without server restart
- [ ] Thread-safe access to config values
- [ ] Validation prevents invalid config from being applied
- [ ] Invalid config changes logged but don't crash server
- [ ] Config changes logged with before/after values

### 3. Operational Safety
- [ ] In-progress operations not interrupted
- [ ] New operations use new config values
- [ ] Cached resources (Whisper models) updated appropriately
- [ ] No race conditions in config access
- [ ] Atomic config updates

### 4. Developer Experience
- [ ] Clear logging of reload events
- [ ] Validation errors descriptive
- [ ] Optional manual reload trigger
- [ ] Config inspection tool available
- [ ] Hot-reload can be disabled via config

## Implementation Notes

### What Gets Hot-Reloaded

**Safe to reload (no side effects):**
- Whisper model selection (loaded on next use)
- Timeout values
- Queue thresholds
- Service endpoints (for new requests)
- Logging levels
- Feature flags

**Requires careful handling:**
- Redis connection settings (existing connections remain)
- Service ports (existing connections remain)
- Model paths (cached models not reloaded)

**Cannot be hot-reloaded:**
- MCP server process settings
- Background worker count (requires restart)

### Thread Safety

All config access uses a read-write lock:
```python
with self._lock:
    value = self.config.data[key]
```

Config updates are atomic (entire dict replaced):
```python
with self._lock:
    self.config.data = new_config
```

### Performance

- File watching: Negligible CPU usage (event-based)
- Config access: <1μs with lock
- Reload time: ~10-50ms depending on file size
- No impact on conversion performance

## Deliverables

### Files to Create
```
src/gobbler_mcp/
├── config_watcher.py             # File watcher and reload logic
└── config.py                     # Update with thread-safety

tests/
├── unit/
│   ├── test_config_watcher.py    # Test file watching
│   ├── test_config_reload.py     # Test reload logic
│   └── test_config_validation.py # Test validation
└── integration/
    └── test_hot_reload_e2e.py    # End-to-end reload test

docs/
└── configuration/
    ├── hot-reload.md             # Hot-reload documentation
    └── config-reference.md       # Full config reference
```

## Testing

```python
# tests/unit/test_config_reload.py
import pytest
import tempfile
from pathlib import Path
import yaml
import asyncio
from gobbler_mcp.config import Config
from gobbler_mcp.config_watcher import ConfigWatcher

@pytest.mark.asyncio
class TestConfigReload:
    """Test configuration hot-reload functionality"""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create temporary config file"""
        config_file = tmp_path / "config.yml"
        config_data = {
            "whisper": {"model": "small"},
            "crawl4ai": {"timeout": 30}
        }
        config_file.write_text(yaml.dump(config_data))
        return config_file

    def test_config_file_reload(self, temp_config):
        """Test configuration reloads when file changes"""
        # Load initial config
        config = Config(config_path=temp_config)
        assert config.get("whisper.model") == "small"

        # Enable hot-reload
        config.enable_hot_reload()

        # Modify config file
        new_config = {
            "whisper": {"model": "base"},  # Changed
            "crawl4ai": {"timeout": 30}
        }
        temp_config.write_text(yaml.dump(new_config))

        # Wait for reload (debounced)
        import time
        time.sleep(2)

        # Verify new value
        assert config.get("whisper.model") == "base"

        config.disable_hot_reload()

    async def test_invalid_config_rejected(self, temp_config):
        """Test invalid configuration is rejected"""
        config = Config(config_path=temp_config)
        watcher = ConfigWatcher(temp_config, config)

        # Write invalid config
        invalid_config = {
            "whisper": {"model": "invalid_model"}  # Invalid
        }
        temp_config.write_text(yaml.dump(invalid_config))

        # Trigger reload
        await watcher.reload_config()

        # Should keep old config
        assert config.get("whisper.model") == "small"

    def test_thread_safe_access(self, temp_config):
        """Test config access is thread-safe"""
        import threading

        config = Config(config_path=temp_config)
        errors = []

        def read_config():
            for _ in range(100):
                try:
                    value = config.get("whisper.model")
                    assert value in ["small", "base"]
                except Exception as e:
                    errors.append(e)

        # Start multiple threads reading config
        threads = [threading.Thread(target=read_config) for _ in range(10)]
        for t in threads:
            t.start()

        # Modify config in parallel
        new_config = {
            "whisper": {"model": "base"},
            "crawl4ai": {"timeout": 30}
        }
        temp_config.write_text(yaml.dump(new_config))

        # Wait for threads
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0
```

## Usage Examples

### Development Workflow

```bash
# Start Gobbler with hot-reload enabled (default)
uv run gobbler-mcp

# In another terminal, edit config
vim ~/.config/gobbler/config.yml

# Change whisper.model from 'small' to 'base'
# Save and exit

# Check logs - should see:
# INFO - Configuration file changed: /Users/you/.config/gobbler/config.yml
# INFO - Reloading configuration...
# INFO - Configuration reloaded successfully
# INFO - Config changes: {'whisper.model': {'old': 'small', 'new': 'base'}}

# Next transcription uses 'base' model automatically
```

### Disabling Hot-Reload

```yaml
# ~/.config/gobbler/config.yml
monitoring:
  config_hot_reload: false  # Disable hot-reload
```

## Definition of Done
- [ ] Config watcher implemented with debouncing
- [ ] Thread-safe config access
- [ ] Validation prevents bad configs
- [ ] Integration with server lifecycle
- [ ] Reload events logged
- [ ] Tests passing
- [ ] Documentation complete
- [ ] Works on macOS, Linux, Windows
- [ ] No performance degradation

## References
- watchdog library: https://pythonhosted.org/watchdog/
- Python threading: https://docs.python.org/3/library/threading.html
- Configuration best practices: https://12factor.net/config

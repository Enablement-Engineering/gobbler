"""Unit tests for configuration file watcher."""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from gobbler_mcp.config_watcher import ConfigFileHandler, ConfigWatcher


class TestConfigFileHandler:
    """Test ConfigFileHandler class."""

    def test_debouncing_prevents_rapid_reloads(self, tmp_path: Path) -> None:
        """Test that debouncing prevents multiple rapid reloads."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("test: value")

        callback = MagicMock()
        handler = ConfigFileHandler(
            config_path=config_file,
            on_change_callback=callback,
            debounce_seconds=0.5,
        )

        # Create mock event
        class MockEvent:
            def __init__(self, path: Path):
                self.src_path = str(path)
                self.is_directory = False

        event = MockEvent(config_file)

        # First modification should trigger callback
        handler.on_modified(event)
        assert callback.call_count == 1

        # Immediate second modification should be debounced
        handler.on_modified(event)
        assert callback.call_count == 1

        # After debounce period, should trigger again
        time.sleep(0.6)
        handler.on_modified(event)
        assert callback.call_count == 2

    def test_ignores_other_files(self, tmp_path: Path) -> None:
        """Test that handler ignores changes to other files."""
        config_file = tmp_path / "config.yml"
        other_file = tmp_path / "other.yml"

        config_file.write_text("test: value")
        other_file.write_text("other: value")

        callback = MagicMock()
        handler = ConfigFileHandler(
            config_path=config_file,
            on_change_callback=callback,
            debounce_seconds=0.1,
        )

        class MockEvent:
            def __init__(self, path: Path):
                self.src_path = str(path)
                self.is_directory = False

        # Modify other file - should not trigger callback
        handler.on_modified(MockEvent(other_file))
        assert callback.call_count == 0

        # Modify config file - should trigger callback
        handler.on_modified(MockEvent(config_file))
        assert callback.call_count == 1

    def test_ignores_directory_events(self, tmp_path: Path) -> None:
        """Test that handler ignores directory modification events."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("test: value")

        callback = MagicMock()
        handler = ConfigFileHandler(
            config_path=config_file,
            on_change_callback=callback,
            debounce_seconds=0.1,
        )

        class MockEvent:
            def __init__(self, path: Path, is_dir: bool):
                self.src_path = str(path)
                self.is_directory = is_dir

        # Directory event - should not trigger callback
        handler.on_modified(MockEvent(tmp_path, is_dir=True))
        assert callback.call_count == 0


class TestConfigWatcher:
    """Test ConfigWatcher class."""

    def test_validation_invalid_whisper_model(self) -> None:
        """Test validation rejects invalid Whisper model."""
        config = {"whisper": {"model": "invalid_model"}}
        errors = ConfigWatcher.validate_config(config)

        assert len(errors) == 1
        assert "whisper.model" in errors[0]
        assert "invalid_model" in errors[0]

    def test_validation_valid_whisper_model(self) -> None:
        """Test validation accepts valid Whisper models."""
        for model in ["tiny", "base", "small", "medium", "large"]:
            config = {"whisper": {"model": model}}
            errors = ConfigWatcher.validate_config(config)
            assert len(errors) == 0

    def test_validation_invalid_timeout(self) -> None:
        """Test validation rejects invalid timeouts."""
        # Too low
        config = {"crawl4ai": {"timeout": 1}}
        errors = ConfigWatcher.validate_config(config)
        assert len(errors) == 1
        assert "timeout" in errors[0]

        # Too high
        config = {"crawl4ai": {"timeout": 500}}
        errors = ConfigWatcher.validate_config(config)
        assert len(errors) == 1
        assert "timeout" in errors[0]

    def test_validation_valid_timeout(self) -> None:
        """Test validation accepts valid timeouts."""
        config = {"crawl4ai": {"timeout": 30}}
        errors = ConfigWatcher.validate_config(config)
        assert len(errors) == 0

    def test_validation_invalid_port(self) -> None:
        """Test validation rejects invalid ports."""
        # Port 0
        config = {"services": {"crawl4ai": {"port": 0}}}
        errors = ConfigWatcher.validate_config(config)
        assert len(errors) >= 1
        assert any("port" in err for err in errors)

        # Port too high
        config = {"services": {"crawl4ai": {"port": 70000}}}
        errors = ConfigWatcher.validate_config(config)
        assert len(errors) >= 1
        assert any("port" in err for err in errors)

    def test_validation_valid_port(self) -> None:
        """Test validation accepts valid ports."""
        config = {"services": {"crawl4ai": {"port": 11235}}}
        errors = ConfigWatcher.validate_config(config)
        assert len(errors) == 0

    def test_validation_invalid_log_format(self) -> None:
        """Test validation rejects invalid log format."""
        config = {"monitoring": {"log_format": "xml"}}
        errors = ConfigWatcher.validate_config(config)
        assert len(errors) == 1
        assert "log_format" in errors[0]

    def test_validation_valid_log_format(self) -> None:
        """Test validation accepts valid log formats."""
        for fmt in ["text", "json"]:
            config = {"monitoring": {"log_format": fmt}}
            errors = ConfigWatcher.validate_config(config)
            assert len(errors) == 0

    def test_validation_invalid_log_level(self) -> None:
        """Test validation rejects invalid log level."""
        config = {"monitoring": {"log_level": "TRACE"}}
        errors = ConfigWatcher.validate_config(config)
        assert len(errors) == 1
        assert "log_level" in errors[0]

    def test_validation_valid_log_level(self) -> None:
        """Test validation accepts valid log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = {"monitoring": {"log_level": level}}
            errors = ConfigWatcher.validate_config(config)
            assert len(errors) == 0

    def test_validation_multiple_errors(self) -> None:
        """Test validation collects multiple errors."""
        config = {
            "whisper": {"model": "invalid"},
            "services": {"crawl4ai": {"port": 0}},
            "monitoring": {"log_format": "xml"},
        }
        errors = ConfigWatcher.validate_config(config)
        assert len(errors) >= 2  # At least whisper.model and log_format errors
        assert any("whisper.model" in err for err in errors)
        assert any("log_format" in err for err in errors)

    def test_validation_empty_config(self) -> None:
        """Test validation accepts empty config (uses defaults)."""
        config = {}
        errors = ConfigWatcher.validate_config(config)
        assert len(errors) == 0

    def test_watcher_start_stop(self, tmp_path: Path) -> None:
        """Test starting and stopping config watcher."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("test: value")

        callback = MagicMock()
        watcher = ConfigWatcher(
            config_path=config_file, reload_callback=callback, debounce_seconds=0.1
        )

        # Initially not running
        assert not watcher.is_running()

        # Start watcher
        watcher.start()
        assert watcher.is_running()

        # Stop watcher
        watcher.stop()
        assert not watcher.is_running()

    def test_watcher_does_not_start_if_file_missing(self, tmp_path: Path) -> None:
        """Test watcher does not start if config file does not exist."""
        config_file = tmp_path / "nonexistent.yml"

        callback = MagicMock()
        watcher = ConfigWatcher(
            config_path=config_file, reload_callback=callback, debounce_seconds=0.1
        )

        watcher.start()
        assert not watcher.is_running()

    def test_watcher_detects_file_changes(self, tmp_path: Path) -> None:
        """Test watcher detects actual file changes."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("test: value1")

        callback = MagicMock()
        watcher = ConfigWatcher(
            config_path=config_file, reload_callback=callback, debounce_seconds=0.1
        )

        watcher.start()
        time.sleep(0.2)  # Let observer start

        # Modify file
        config_file.write_text("test: value2")
        time.sleep(0.3)  # Wait for debounce + processing

        # Callback should have been triggered
        assert callback.call_count >= 1

        watcher.stop()

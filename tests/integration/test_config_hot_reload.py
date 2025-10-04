"""Integration tests for config hot-reload functionality."""

import tempfile
import threading
import time
from pathlib import Path

import pytest
import yaml

from gobbler_mcp.config import Config


class TestConfigHotReload:
    """Integration tests for config hot-reload."""

    def test_end_to_end_hot_reload(self, tmp_path: Path) -> None:
        """Test complete hot-reload flow from file change to config update."""
        # Create initial config file
        config_file = tmp_path / "config.yml"
        initial_config = {
            "whisper": {"model": "small", "language": "auto"},
            "crawl4ai": {"timeout": 30},
        }
        with open(config_file, "w") as f:
            yaml.dump(initial_config, f)

        # Initialize config
        config = Config(config_path=config_file)
        assert config.get("whisper.model") == "small"
        assert config.get("crawl4ai.timeout") == 30

        # Enable hot-reload
        config.enable_hot_reload(debounce_seconds=0.1)
        time.sleep(0.2)  # Let watcher start

        # Modify config file
        updated_config = {
            "whisper": {"model": "base", "language": "auto"},
            "crawl4ai": {"timeout": 60},
        }
        with open(config_file, "w") as f:
            yaml.dump(updated_config, f)

        # Wait for file watcher to detect change and reload
        time.sleep(0.5)

        # Verify config was reloaded
        assert config.get("whisper.model") == "base"
        assert config.get("crawl4ai.timeout") == 60

        # Cleanup
        config.disable_hot_reload()

    def test_invalid_config_rejected(self, tmp_path: Path) -> None:
        """Test that invalid config changes are rejected."""
        # Create initial config file
        config_file = tmp_path / "config.yml"
        initial_config = {"whisper": {"model": "small"}}
        with open(config_file, "w") as f:
            yaml.dump(initial_config, f)

        # Initialize config
        config = Config(config_path=config_file)
        assert config.get("whisper.model") == "small"

        # Enable hot-reload
        config.enable_hot_reload(debounce_seconds=0.1)
        time.sleep(0.2)

        # Write invalid config
        invalid_config = {"whisper": {"model": "invalid_model"}}
        with open(config_file, "w") as f:
            yaml.dump(invalid_config, f)

        # Wait for reload attempt
        time.sleep(0.5)

        # Verify old config is still active
        assert config.get("whisper.model") == "small"

        # Cleanup
        config.disable_hot_reload()

    def test_malformed_yaml_rejected(self, tmp_path: Path) -> None:
        """Test that malformed YAML doesn't crash and keeps old config."""
        # Create initial config file
        config_file = tmp_path / "config.yml"
        initial_config = {"whisper": {"model": "small"}}
        with open(config_file, "w") as f:
            yaml.dump(initial_config, f)

        # Initialize config
        config = Config(config_path=config_file)
        assert config.get("whisper.model") == "small"

        # Enable hot-reload
        config.enable_hot_reload(debounce_seconds=0.1)
        time.sleep(0.2)

        # Write malformed YAML
        with open(config_file, "w") as f:
            f.write("this is not: valid: yaml: content:")

        # Wait for reload attempt
        time.sleep(0.5)

        # Verify old config is still active
        assert config.get("whisper.model") == "small"

        # Cleanup
        config.disable_hot_reload()

    def test_concurrent_config_access_during_reload(self, tmp_path: Path) -> None:
        """Test thread-safe config access during reload."""
        # Create initial config file
        config_file = tmp_path / "config.yml"
        initial_config = {"whisper": {"model": "small"}, "test_value": 1}
        with open(config_file, "w") as f:
            yaml.dump(initial_config, f)

        # Initialize config
        config = Config(config_path=config_file)

        # Enable hot-reload
        config.enable_hot_reload(debounce_seconds=0.1)
        time.sleep(0.2)

        # Track if any thread encountered an error
        errors = []

        def read_config_continuously() -> None:
            """Continuously read config values."""
            try:
                for _ in range(100):
                    model = config.get("whisper.model")
                    value = config.get("test_value")
                    # Both should always be valid (never None or partial)
                    assert model in ["small", "base"]
                    assert value in [1, 2]
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        # Start reader threads
        readers = [threading.Thread(target=read_config_continuously) for _ in range(5)]
        for t in readers:
            t.start()

        # Modify config while readers are running
        time.sleep(0.1)
        updated_config = {"whisper": {"model": "base"}, "test_value": 2}
        with open(config_file, "w") as f:
            yaml.dump(updated_config, f)

        # Wait for threads to finish
        for t in readers:
            t.join()

        # Verify no errors occurred
        assert len(errors) == 0

        # Cleanup
        config.disable_hot_reload()

    def test_change_detection(self, tmp_path: Path) -> None:
        """Test that config change detection works correctly."""
        # Create initial config file
        config_file = tmp_path / "config.yml"
        initial_config = {
            "whisper": {"model": "small", "language": "auto"},
            "crawl4ai": {"timeout": 30},
        }
        with open(config_file, "w") as f:
            yaml.dump(initial_config, f)

        # Initialize config
        config = Config(config_path=config_file)

        # Test change detection
        old_config = {"whisper": {"model": "small"}, "value": 1}
        new_config = {"whisper": {"model": "base"}, "value": 1, "new_key": "added"}

        changes = config._detect_changes(old_config, new_config)

        # Should detect model change and new key
        assert any("whisper.model" in change for change in changes)
        assert any("new_key" in change for change in changes)

    def test_hot_reload_can_be_disabled_via_config(self, tmp_path: Path) -> None:
        """Test that hot-reload respects config flag."""
        # This would be tested at the server level, but we can verify
        # the enable/disable methods work
        config_file = tmp_path / "config.yml"
        initial_config = {"whisper": {"model": "small"}}
        with open(config_file, "w") as f:
            yaml.dump(initial_config, f)

        config = Config(config_path=config_file)

        # Enable and verify
        config.enable_hot_reload()
        assert config._watcher is not None
        assert config._watcher.is_running()

        # Disable and verify
        config.disable_hot_reload()
        assert config._watcher is None

    def test_multiple_rapid_changes_debounced(self, tmp_path: Path) -> None:
        """Test that multiple rapid file changes are debounced."""
        # Create initial config file
        config_file = tmp_path / "config.yml"
        initial_config = {"test_value": 0}
        with open(config_file, "w") as f:
            yaml.dump(initial_config, f)

        # Initialize config
        config = Config(config_path=config_file)
        assert config.get("test_value") == 0

        # Enable hot-reload with longer debounce
        config.enable_hot_reload(debounce_seconds=0.5)
        time.sleep(0.3)

        # Make multiple rapid changes
        for i in range(1, 6):
            with open(config_file, "w") as f:
                yaml.dump({"test_value": i}, f)
            time.sleep(0.05)  # Less than debounce time

        # Wait for debounce period + processing time
        time.sleep(1.0)

        # Should have one of the later values (debouncing prevents intermediate reloads)
        # Due to timing, we might get 4 or 5, but definitely not 0, 1, 2, or 3
        final_value = config.get("test_value")
        assert final_value >= 4, f"Expected value >= 4, got {final_value}"

        # Cleanup
        config.disable_hot_reload()

    def test_manual_reload(self, tmp_path: Path) -> None:
        """Test manual config reload without file watcher."""
        # Create initial config file
        config_file = tmp_path / "config.yml"
        initial_config = {"whisper": {"model": "small"}}
        with open(config_file, "w") as f:
            yaml.dump(initial_config, f)

        # Initialize config
        config = Config(config_path=config_file)
        assert config.get("whisper.model") == "small"

        # Modify config file
        updated_config = {"whisper": {"model": "base"}}
        with open(config_file, "w") as f:
            yaml.dump(updated_config, f)

        # Manually reload
        config.reload()

        # Verify config was reloaded
        assert config.get("whisper.model") == "base"

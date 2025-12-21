"""Plugin discovery and loading for Gobbler Daemon.

Allows extending Gobbler with custom converters from ~/.config/gobbler/plugins/
"""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConverterPlugin:
    """Base class for converter plugins."""

    name: str = "unknown"
    description: str = "No description"
    version: str = "0.0.0"

    async def convert(self, input: Any, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform conversion.

        Args:
            input: Input data to convert
            options: Conversion options

        Returns:
            Conversion result with 'markdown' and 'metadata' keys

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError

    def validate_input(self, input: Any) -> bool:
        """
        Validate input before conversion.

        Args:
            input: Input to validate

        Returns:
            True if input is valid
        """
        return True

    def get_schema(self) -> Dict[str, Any]:
        """
        Get JSON schema for plugin options.

        Returns:
            JSON schema dictionary
        """
        return {
            "type": "object",
            "properties": {},
        }


class PluginManager:
    """
    Plugin discovery and loading manager.

    Discovers plugins from ~/.config/gobbler/plugins/ directory
    and loads them dynamically.
    """

    def __init__(self, plugins_directory: Optional[Path] = None) -> None:
        """
        Initialize plugin manager.

        Args:
            plugins_directory: Directory to scan for plugins.
                              Defaults to ~/.config/gobbler/plugins
        """
        if plugins_directory is None:
            plugins_directory = Path.home() / ".config" / "gobbler" / "plugins"

        self.plugins_directory = Path(plugins_directory)
        self._plugins: Dict[str, ConverterPlugin] = {}
        self._plugin_modules: Dict[str, Any] = {}

    async def start(self) -> None:
        """Start plugin manager and discover plugins."""
        logger.info(f"Starting plugin manager (directory: {self.plugins_directory})")

        if not self.plugins_directory.exists():
            logger.info(
                f"Plugins directory does not exist: {self.plugins_directory}. "
                "Creating it..."
            )
            self.plugins_directory.mkdir(parents=True, exist_ok=True)
            return

        # Discover and load plugins
        await self.discover_plugins()

        logger.info(f"Plugin manager started with {len(self._plugins)} plugins")

    async def stop(self) -> None:
        """Stop plugin manager and unload plugins."""
        for plugin_name in list(self._plugins.keys()):
            await self.unload_plugin(plugin_name)

        self._plugins.clear()
        self._plugin_modules.clear()

        logger.info("Plugin manager stopped")

    async def discover_plugins(self) -> None:
        """
        Discover and load plugins from plugins directory.

        Each plugin should be in its own directory with a plugin.py file:
        ~/.config/gobbler/plugins/
        ├── my-converter/
        │   ├── plugin.py
        │   └── requirements.txt (optional)
        """
        if not self.plugins_directory.is_dir():
            return

        for plugin_dir in self.plugins_directory.iterdir():
            if not plugin_dir.is_dir():
                continue

            plugin_file = plugin_dir / "plugin.py"
            if not plugin_file.exists():
                logger.debug(f"Skipping {plugin_dir.name}: no plugin.py found")
                continue

            try:
                await self.load_plugin(plugin_dir.name, plugin_file)
            except Exception as e:
                logger.error(
                    f"Failed to load plugin {plugin_dir.name}: {e}", exc_info=True
                )

    async def load_plugin(self, plugin_name: str, plugin_file: Path) -> None:
        """
        Load a plugin from a file.

        Args:
            plugin_name: Name of the plugin
            plugin_file: Path to plugin.py file

        Raises:
            ImportError: If plugin cannot be loaded
            ValueError: If plugin doesn't define a valid converter
        """
        logger.info(f"Loading plugin: {plugin_name}")

        # Load the module
        spec = importlib.util.spec_from_file_location(
            f"gobbler_plugin_{plugin_name}", plugin_file
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load plugin spec from {plugin_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        # Find ConverterPlugin subclass in the module
        plugin_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, ConverterPlugin)
                and attr is not ConverterPlugin
            ):
                plugin_class = attr
                break

        if plugin_class is None:
            raise ValueError(
                f"Plugin {plugin_name} does not define a ConverterPlugin subclass"
            )

        # Instantiate the plugin
        plugin_instance = plugin_class()

        # Store plugin
        self._plugins[plugin_name] = plugin_instance
        self._plugin_modules[plugin_name] = module

        logger.info(
            f"Loaded plugin: {plugin_name} "
            f"({plugin_instance.name} v{plugin_instance.version})"
        )

    async def unload_plugin(self, plugin_name: str) -> None:
        """
        Unload a plugin.

        Args:
            plugin_name: Name of the plugin to unload
        """
        if plugin_name not in self._plugins:
            logger.warning(f"Plugin {plugin_name} not loaded")
            return

        # Remove from plugins dict
        plugin = self._plugins.pop(plugin_name)

        # Remove module from sys.modules
        if plugin_name in self._plugin_modules:
            module = self._plugin_modules.pop(plugin_name)
            module_name = module.__name__
            if module_name in sys.modules:
                del sys.modules[module_name]

        logger.info(f"Unloaded plugin: {plugin_name}")

    def get_plugin(self, plugin_name: str) -> Optional[ConverterPlugin]:
        """
        Get a loaded plugin by name.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin instance or None if not found
        """
        return self._plugins.get(plugin_name)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """
        List all loaded plugins.

        Returns:
            List of plugin information dictionaries
        """
        plugins_info = []
        for plugin_name, plugin in self._plugins.items():
            plugins_info.append(
                {
                    "name": plugin_name,
                    "display_name": plugin.name,
                    "description": plugin.description,
                    "version": plugin.version,
                }
            )
        return plugins_info

    def is_loaded(self, plugin_name: str) -> bool:
        """
        Check if a plugin is loaded.

        Args:
            plugin_name: Name of the plugin

        Returns:
            True if plugin is loaded
        """
        return plugin_name in self._plugins

    async def reload_plugin(self, plugin_name: str) -> None:
        """
        Reload a plugin.

        Args:
            plugin_name: Name of the plugin to reload

        Raises:
            ValueError: If plugin is not currently loaded
        """
        if plugin_name not in self._plugins:
            raise ValueError(f"Plugin {plugin_name} is not loaded")

        # Get the plugin file path
        plugin_dir = self.plugins_directory / plugin_name
        plugin_file = plugin_dir / "plugin.py"

        if not plugin_file.exists():
            raise ValueError(f"Plugin file not found: {plugin_file}")

        # Unload and reload
        await self.unload_plugin(plugin_name)
        await self.load_plugin(plugin_name, plugin_file)

        logger.info(f"Reloaded plugin: {plugin_name}")

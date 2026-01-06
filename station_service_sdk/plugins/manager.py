"""Plugin manager for Station Service SDK.

Provides plugin discovery, loading, and lifecycle management
using Python entry points.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Any, Protocol, runtime_checkable

from station_service_sdk.interfaces import LifecycleHook, OutputStrategy, CompositeHook

logger = logging.getLogger(__name__)


@runtime_checkable
class Plugin(Protocol):
    """Protocol for SDK plugins.

    Plugins can provide hooks, output strategies, and other
    extensions to the SDK.

    Example:
        >>> class MyPlugin:
        ...     name = "my-plugin"
        ...     version = "1.0.0"
        ...
        ...     def initialize(self, config: dict) -> None:
        ...         self.config = config
        ...
        ...     def get_hooks(self) -> list[LifecycleHook]:
        ...         return [MyCustomHook()]
        ...
        ...     def get_output_strategies(self) -> dict[str, type[OutputStrategy]]:
        ...         return {"custom": MyOutputStrategy}
    """

    name: str
    version: str

    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the plugin with configuration.

        Args:
            config: Plugin-specific configuration
        """
        ...

    def get_hooks(self) -> list[LifecycleHook]:
        """Get lifecycle hooks provided by this plugin.

        Returns:
            List of lifecycle hook instances
        """
        ...

    def get_output_strategies(self) -> dict[str, type[OutputStrategy]]:
        """Get output strategies provided by this plugin.

        Returns:
            Dictionary mapping names to output strategy classes
        """
        ...


@dataclass
class PluginInfo:
    """Information about a discovered plugin.

    Attributes:
        name: Plugin name (entry point name)
        version: Plugin version
        module: Python module path
        enabled: Whether plugin is enabled
        load_error: Error message if loading failed
    """

    name: str
    version: str = "0.0.0"
    module: str = ""
    enabled: bool = True
    load_error: str | None = None


@dataclass
class PluginRegistry:
    """Registry of loaded plugins and their extensions.

    Attributes:
        plugins: Loaded plugin instances
        hooks: All hooks from plugins
        output_strategies: All output strategies from plugins
    """

    plugins: dict[str, Plugin] = field(default_factory=dict)
    hooks: list[LifecycleHook] = field(default_factory=list)
    output_strategies: dict[str, type[OutputStrategy]] = field(default_factory=dict)


class PluginManager:
    """Manager for discovering, loading, and managing plugins.

    Uses Python entry points for plugin discovery. Plugins should
    register under the 'station_sdk.plugins' entry point group.

    Example pyproject.toml for a plugin:

        [project.entry-points."station_sdk.plugins"]
        my_plugin = "my_package.plugin:MyPlugin"

    Example usage:

        >>> manager = PluginManager()
        >>> plugins = manager.discover_plugins()
        >>> manager.load_plugin("my_plugin")
        >>> hooks = manager.get_composite_hook()
    """

    ENTRY_POINT_GROUP = "station_sdk.plugins"

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize plugin manager.

        Args:
            config: Global plugin configuration
        """
        self.config = config or {}
        self._registry = PluginRegistry()
        self._discovered: dict[str, PluginInfo] = {}

    def discover_plugins(self) -> list[PluginInfo]:
        """Discover available plugins via entry points.

        Scans the entry point group for registered plugins
        without loading them.

        Returns:
            List of discovered plugin information
        """
        discovered: list[PluginInfo] = []

        try:
            eps = entry_points(group=self.ENTRY_POINT_GROUP)
        except TypeError:
            # Python < 3.10 compatibility
            eps = entry_points().get(self.ENTRY_POINT_GROUP, [])

        for ep in eps:
            try:
                # Load to get version without initializing
                plugin_class = ep.load()
                version = getattr(plugin_class, "version", "0.0.0")

                info = PluginInfo(
                    name=ep.name,
                    version=version,
                    module=ep.value,
                    enabled=True,
                )
            except Exception as e:
                logger.warning(f"Failed to discover plugin {ep.name}: {e}")
                info = PluginInfo(
                    name=ep.name,
                    module=getattr(ep, "value", "unknown"),
                    enabled=False,
                    load_error=str(e),
                )

            discovered.append(info)
            self._discovered[ep.name] = info

        return discovered

    def load_plugin(
        self,
        name: str,
        config: dict[str, Any] | None = None,
    ) -> Plugin:
        """Load and initialize a plugin.

        Args:
            name: Plugin name (entry point name)
            config: Plugin-specific configuration

        Returns:
            Loaded and initialized plugin instance

        Raises:
            ValueError: If plugin not found
            RuntimeError: If plugin fails to load
        """
        if name in self._registry.plugins:
            return self._registry.plugins[name]

        try:
            eps = entry_points(group=self.ENTRY_POINT_GROUP)
        except TypeError:
            eps = entry_points().get(self.ENTRY_POINT_GROUP, [])

        ep = None
        for e in eps:
            if e.name == name:
                ep = e
                break

        if ep is None:
            available = [e.name for e in eps]
            raise ValueError(
                f"Plugin '{name}' not found. Available plugins: {available}"
            )

        try:
            plugin_class = ep.load()
            plugin = plugin_class()

            # Merge configs: global -> plugin-specific
            merged_config = {**self.config}
            if config:
                merged_config.update(config)

            plugin.initialize(merged_config)

            # Register plugin and its extensions
            self._registry.plugins[name] = plugin

            # Collect hooks
            hooks = plugin.get_hooks()
            self._registry.hooks.extend(hooks)

            # Collect output strategies
            strategies = plugin.get_output_strategies()
            self._registry.output_strategies.update(strategies)

            logger.info(f"Loaded plugin: {name} v{plugin.version}")
            return plugin

        except Exception as e:
            raise RuntimeError(f"Failed to load plugin '{name}': {e}") from e

    def load_all_plugins(self, config: dict[str, dict[str, Any]] | None = None) -> list[Plugin]:
        """Load all discovered plugins.

        Args:
            config: Dictionary mapping plugin names to their configs

        Returns:
            List of loaded plugins
        """
        config = config or {}

        if not self._discovered:
            self.discover_plugins()

        loaded: list[Plugin] = []
        for name, info in self._discovered.items():
            if not info.enabled:
                continue

            try:
                plugin = self.load_plugin(name, config.get(name))
                loaded.append(plugin)
            except Exception as e:
                logger.error(f"Failed to load plugin {name}: {e}")

        return loaded

    def unload_plugin(self, name: str) -> None:
        """Unload a plugin.

        Args:
            name: Plugin name to unload
        """
        if name not in self._registry.plugins:
            return

        plugin = self._registry.plugins.pop(name)

        # Remove plugin's hooks
        plugin_hooks = set(plugin.get_hooks())
        self._registry.hooks = [
            h for h in self._registry.hooks
            if h not in plugin_hooks
        ]

        # Remove plugin's output strategies
        plugin_strategies = set(plugin.get_output_strategies().keys())
        for key in plugin_strategies:
            self._registry.output_strategies.pop(key, None)

        logger.info(f"Unloaded plugin: {name}")

    def get_plugin(self, name: str) -> Plugin | None:
        """Get a loaded plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None
        """
        return self._registry.plugins.get(name)

    def get_hooks(self) -> list[LifecycleHook]:
        """Get all hooks from loaded plugins.

        Returns:
            List of all lifecycle hooks
        """
        return list(self._registry.hooks)

    def get_composite_hook(self) -> CompositeHook:
        """Get a composite hook combining all plugin hooks.

        Returns:
            CompositeHook instance
        """
        return CompositeHook(self._registry.hooks)

    def get_output_strategy(self, name: str) -> type[OutputStrategy] | None:
        """Get an output strategy by name.

        Args:
            name: Strategy name

        Returns:
            Output strategy class or None
        """
        return self._registry.output_strategies.get(name)

    def list_plugins(self) -> list[PluginInfo]:
        """List all discovered plugins with their status.

        Returns:
            List of plugin information
        """
        if not self._discovered:
            self.discover_plugins()

        result = []
        for name, info in self._discovered.items():
            info_copy = PluginInfo(
                name=info.name,
                version=info.version,
                module=info.module,
                enabled=info.enabled and name in self._registry.plugins,
                load_error=info.load_error,
            )
            result.append(info_copy)

        return result

    def is_loaded(self, name: str) -> bool:
        """Check if a plugin is loaded.

        Args:
            name: Plugin name

        Returns:
            True if plugin is loaded
        """
        return name in self._registry.plugins


class BasePlugin:
    """Base class for SDK plugins.

    Provides default implementations of the Plugin protocol.
    Inherit from this class to create custom plugins.

    Example:
        >>> class MyPlugin(BasePlugin):
        ...     name = "my-plugin"
        ...     version = "1.0.0"
        ...
        ...     def get_hooks(self) -> list[LifecycleHook]:
        ...         return [MyHook(self.config)]
    """

    name: str = "base-plugin"
    version: str = "0.0.0"

    def __init__(self) -> None:
        """Initialize plugin."""
        self.config: dict[str, Any] = {}

    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize with configuration.

        Args:
            config: Plugin configuration
        """
        self.config = config

    def get_hooks(self) -> list[LifecycleHook]:
        """Get lifecycle hooks.

        Returns:
            Empty list by default
        """
        return []

    def get_output_strategies(self) -> dict[str, type[OutputStrategy]]:
        """Get output strategies.

        Returns:
            Empty dict by default
        """
        return {}

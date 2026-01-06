"""Plugin system for Station Service SDK.

This module provides a plugin architecture for extending
SDK functionality through entry points.
"""

from station_service_sdk.plugins.manager import (
    Plugin,
    PluginInfo,
    PluginManager,
)
from station_service_sdk.plugins.protocols import (
    ProtocolAdapter,
    AdapterFactory,
)

__all__ = [
    "Plugin",
    "PluginInfo",
    "PluginManager",
    "ProtocolAdapter",
    "AdapterFactory",
]

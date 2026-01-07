"""Re-export interfaces from core for backward compatibility."""
from station_service_sdk.core.interfaces import (
    OutputStrategy,
    LifecycleHook,
    CompositeHook,
)

__all__ = ["OutputStrategy", "LifecycleHook", "CompositeHook"]

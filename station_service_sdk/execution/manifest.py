"""Re-export manifest from core for backward compatibility."""
from station_service_sdk.core.manifest import (
    SequenceManifest,
    HardwareDefinition,
    ConfigFieldSchema,
    StepDefinition,
    ParameterDefinition,
    EntryPoint,
)

__all__ = [
    "SequenceManifest",
    "HardwareDefinition",
    "ConfigFieldSchema",
    "StepDefinition",
    "ParameterDefinition",
    "EntryPoint",
]

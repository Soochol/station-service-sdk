"""Core module for Station Service SDK.

Contains the fundamental building blocks:
- SequenceBase: Base class for all sequences
- ExecutionContext: Execution state management
- OutputProtocol: JSON Lines communication protocol
- Exceptions: Error hierarchy
- Interfaces: Extension points (OutputStrategy, LifecycleHook)
- Manifest: Package configuration models
- Types: Type definitions and enums
"""

from station_service_sdk.core.base import SequenceBase, StepResult
from station_service_sdk.core.context import ExecutionContext, Measurement
from station_service_sdk.core.protocol import MessageType, OutputProtocol
from station_service_sdk.core.interfaces import (
    OutputStrategy,
    LifecycleHook,
    CompositeHook,
)
from station_service_sdk.core.exceptions import (
    # Base
    SequenceError,
    # Lifecycle
    SetupError,
    TeardownError,
    # Execution
    StepError,
    SequenceTimeoutError,
    TimeoutError,
    AbortError,
    # Test results
    TestFailure,
    TestSkipped,
    # Hardware
    HardwareError,
    HardwareConnectionError,
    ConnectionError,
    CommunicationError,
    # Package/Manifest
    PackageError,
    ManifestError,
    # Validation
    ValidationError,
    DependencyError,
    # Backward compatibility
    DriverError,
    ExecutionError,
    StepTimeoutError,
)
from station_service_sdk.core.manifest import (
    ParameterType,
    ConfigFieldSchema,
    HardwareDefinition,
    HardwareDefinitionExtended,
    ParameterDefinition,
    EntryPoint,
    Modes,
    ManualConfig,
    StepDefinition,
    DependencySpec,
    ManualCommand,
    ManualCommandParameter,
    ManualCommandReturn,
    SequenceManifest,
)
from station_service_sdk.core.sdk_types import (
    RunResult,
    ExecutionResult,
    MeasurementDict,
    StepResultDict,
    HardwareConfigDict,
    ParametersDict,
    MeasurementsDict,
    ExecutionPhase,
    LogLevel,
    SimulationStatus,
    InputType,
)
from station_service_sdk.core.types import (
    SimulationResult,
    StepMeta,
    StepInfo,
)

__all__ = [
    # Base
    "SequenceBase",
    "StepResult",
    # Context
    "ExecutionContext",
    "Measurement",
    # Protocol
    "MessageType",
    "OutputProtocol",
    # Interfaces
    "OutputStrategy",
    "LifecycleHook",
    "CompositeHook",
    # Exceptions
    "SequenceError",
    "SetupError",
    "TeardownError",
    "StepError",
    "SequenceTimeoutError",
    "TimeoutError",
    "AbortError",
    "TestFailure",
    "TestSkipped",
    "HardwareError",
    "HardwareConnectionError",
    "ConnectionError",
    "CommunicationError",
    "PackageError",
    "ManifestError",
    "ValidationError",
    "DependencyError",
    "DriverError",
    "ExecutionError",
    "StepTimeoutError",
    # Manifest
    "ParameterType",
    "ConfigFieldSchema",
    "HardwareDefinition",
    "HardwareDefinitionExtended",
    "ParameterDefinition",
    "EntryPoint",
    "Modes",
    "ManualConfig",
    "StepDefinition",
    "DependencySpec",
    "ManualCommand",
    "ManualCommandParameter",
    "ManualCommandReturn",
    "SequenceManifest",
    # Types
    "RunResult",
    "ExecutionResult",
    "MeasurementDict",
    "StepResultDict",
    "HardwareConfigDict",
    "ParametersDict",
    "MeasurementsDict",
    "ExecutionPhase",
    "LogLevel",
    "SimulationStatus",
    "InputType",
    "SimulationResult",
    "StepMeta",
    "StepInfo",
]

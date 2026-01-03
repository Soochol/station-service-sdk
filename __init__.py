"""
Sequence SDK for CLI-based sequence execution.

This SDK provides:
- SequenceBase: Base class for all sequences
- CLI argument handling
- JSON Lines output protocol for Station Service communication
- Execution context management
- Manifest models for package configuration
- Sequence package loader for discovery and loading

Usage:
    from station_service.sdk import SequenceBase, StepResult

    class MySequence(SequenceBase):
        name = "my_sequence"
        version = "1.0.0"
        description = "My test sequence"

        async def setup(self) -> None:
            # Initialize hardware
            pass

        async def run(self) -> dict:
            self.emit_step_start("test", 1, 3)
            # ... test logic
            return {"passed": True, "measurements": {...}}

        async def teardown(self) -> None:
            # Cleanup
            pass

    if __name__ == "__main__":
        exit(MySequence.run_from_cli())
"""

from .base import SequenceBase, StepResult
from .context import ExecutionContext, Measurement
from .protocol import MessageType, OutputProtocol
from .types import (
    # TypedDict definitions
    RunResult,
    ExecutionResult,
    MeasurementDict,
    StepResultDict,
    SimulationResult,
    # Type aliases
    HardwareConfigDict,
    ParametersDict,
    MeasurementsDict,
)
from .exceptions import (
    # Base
    SequenceError,
    # Lifecycle
    SetupError,
    TeardownError,
    # Execution
    StepError,
    TimeoutError,
    AbortError,
    # Test results
    TestFailure,
    TestSkipped,
    # Hardware
    HardwareError,
    ConnectionError,
    CommunicationError,
    # Package/Manifest
    PackageError,
    ManifestError,
    # Validation
    ValidationError,
    DependencyError,
    # Backward compatibility aliases
    DriverError,
    ExecutionError,
    StepTimeoutError,
)
from .interfaces import OutputStrategy, LifecycleHook, CompositeHook
from .registry import (
    SequenceRegistry,
    register_sequence,
    get_sequence,
    list_sequences,
    discover_sequences,
)
from .manifest import (
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
from .loader import SequenceLoader
from .helpers import (
    StepInfo,
    StepMeta,
    collect_steps,
    collect_steps_from_manifest,
    collect_steps_from_class,
)
from .simulator import SequenceSimulator, MockHardware
from .interactive import (
    InteractiveSimulator,
    SimulationSession,
    SimulationSessionStatus,
    StepState,
    StepExecutionStatus,
)
from .driver_registry import (
    DriverRegistry,
    DriverLoadError,
    DriverConnectionError,
)
from .manual_executor import (
    ManualSequenceExecutor,
    ManualSession,
    ManualSessionStatus,
    ManualStepState,
    ManualStepStatus,
    HardwareState,
    CommandResult,
)
from .decorators import (
    # Decorators for legacy pattern compatibility
    sequence,
    step,
    parameter,
    # Metadata classes
    SequenceMeta,
    StepMeta as DecoratorStepMeta,
    ParameterMeta,
    # Introspection helpers
    get_sequence_meta,
    get_step_meta,
    get_parameter_meta,
    is_step_method,
    is_parameter_method,
    collect_steps_from_decorated_class,
    collect_parameters_from_decorated_class,
)

__all__ = [
    # Core
    "SequenceBase",
    "StepResult",
    "ExecutionContext",
    "Measurement",
    # Protocol
    "MessageType",
    "OutputProtocol",
    # Types (TypedDict definitions)
    "RunResult",
    "ExecutionResult",
    "MeasurementDict",
    "StepResultDict",
    "SimulationResult",
    "HardwareConfigDict",
    "ParametersDict",
    "MeasurementsDict",
    # Interfaces (for extensibility)
    "OutputStrategy",
    "LifecycleHook",
    "CompositeHook",
    # Registry
    "SequenceRegistry",
    "register_sequence",
    "get_sequence",
    "list_sequences",
    "discover_sequences",
    # Loader
    "SequenceLoader",
    # Manifest models
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
    # Exceptions
    "SequenceError",
    "SetupError",
    "TeardownError",
    "StepError",
    "TimeoutError",
    "AbortError",
    "TestFailure",
    "TestSkipped",
    "HardwareError",
    "ConnectionError",
    "CommunicationError",
    "PackageError",
    "ManifestError",
    "ValidationError",
    "DependencyError",
    # Backward compatibility aliases
    "DriverError",
    "ExecutionError",
    "StepTimeoutError",
    # Helpers (compatibility with legacy decorators)
    "StepInfo",
    "StepMeta",
    "collect_steps",
    "collect_steps_from_manifest",
    "collect_steps_from_class",
    # Simulator
    "SequenceSimulator",
    "MockHardware",
    # Interactive Simulator
    "InteractiveSimulator",
    "SimulationSession",
    "SimulationSessionStatus",
    "StepState",
    "StepExecutionStatus",
    # Driver Registry
    "DriverRegistry",
    "DriverLoadError",
    "DriverConnectionError",
    # Manual Sequence Executor
    "ManualSequenceExecutor",
    "ManualSession",
    "ManualSessionStatus",
    "ManualStepState",
    "ManualStepStatus",
    "HardwareState",
    "CommandResult",
    # Decorators (legacy pattern support)
    "sequence",
    "step",
    "parameter",
    "SequenceMeta",
    "DecoratorStepMeta",
    "ParameterMeta",
    "get_sequence_meta",
    "get_step_meta",
    "get_parameter_meta",
    "is_step_method",
    "is_parameter_method",
    "collect_steps_from_decorated_class",
    "collect_parameters_from_decorated_class",
]

__version__ = "2.0.0"  # Major version bump for SDK consolidation

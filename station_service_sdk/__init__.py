"""
Station Service SDK - Build test sequences for manufacturing automation.

This SDK provides:
- SequenceBase: Base class for all sequences
- CLI argument handling
- JSON Lines output protocol for Station Service communication
- Execution context management
- Manifest models for package configuration
- Sequence package loader for discovery and loading
- Simulation and interactive testing tools
- Manual execution capabilities

Example:
    from station_service_sdk import SequenceBase, RunResult

    class MySequence(SequenceBase):
        name = "my_sequence"
        version = "1.0.0"
        description = "My test sequence"

        async def setup(self) -> None:
            self.emit_log("info", "Initializing...")

        async def run(self) -> RunResult:
            self.emit_step_start("test", 1, 1, "Test step")
            self.emit_measurement("voltage", 3.3, "V")
            self.emit_step_complete("test", 1, True, 1.0)
            return {"passed": True, "measurements": {"voltage": 3.3}}

        async def teardown(self) -> None:
            self.emit_log("info", "Cleanup complete")

    if __name__ == "__main__":
        exit(MySequence.run_from_cli())
"""

__version__ = "3.0.0"  # Major version bump for SDK consolidation

# Core
from .base import SequenceBase, StepResult
from .context import ExecutionContext, Measurement
from .protocol import MessageType, OutputProtocol

# Types (TypedDict definitions and type aliases)
from .sdk_types import (
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
from .types import (
    SimulationResult,
    StepMeta,
    StepInfo,
)

# Interfaces (for extensibility)
from .interfaces import OutputStrategy, LifecycleHook, CompositeHook

# Exceptions
from .exceptions import (
    # Base
    SequenceError,
    # Lifecycle
    SetupError,
    TeardownError,
    # Execution
    StepError,
    SequenceTimeoutError,
    TimeoutError,  # Backward compatibility alias
    AbortError,
    # Test results
    TestFailure,
    TestSkipped,
    # Hardware
    HardwareError,
    HardwareConnectionError,
    ConnectionError,  # Backward compatibility alias
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

# Manifest models
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

# Registry
from .registry import (
    SequenceRegistry,
    register_sequence,
    get_sequence,
    list_sequences,
    discover_sequences,
)

# Loader
from .loader import SequenceLoader

# Helpers
from .helpers import (
    collect_steps,
    collect_steps_from_manifest,
    collect_steps_from_class,
)

# Simulator
from .simulator import SequenceSimulator, MockHardware

# Interactive Simulator
from .interactive import (
    InteractiveSimulator,
    SimulationSession,
    SimulationSessionStatus,
    StepState,
    StepExecutionStatus,
)

# Driver Registry
from .driver_registry import (
    DriverRegistry,
    DriverLoadError,
    DriverConnectionError,
)

# Manual Sequence Executor
from .manual_executor import (
    ManualSequenceExecutor,
    ManualSession,
    ManualSessionStatus,
    ManualStepState,
    ManualStepStatus,
    HardwareState,
    CommandResult,
)

# Dependency management
from .dependencies import (
    ensure_package,
    ensure_dependencies,
    is_installed,
    check_dependencies,
    get_missing_packages,
)

# Decorators (legacy pattern support)
from .decorators import (
    sequence,
    step,
    parameter,
    SequenceMeta,
    StepMeta as DecoratorStepMeta,
    ParameterMeta,
    get_sequence_meta,
    get_step_meta,
    get_parameter_meta,
    is_step_method,
    is_parameter_method,
    collect_steps_from_decorated_class,
    collect_parameters_from_decorated_class,
)

__all__ = [
    # Version
    "__version__",
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
    "ExecutionPhase",
    "LogLevel",
    "SimulationStatus",
    "InputType",
    "StepMeta",
    "StepInfo",
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
    # Backward compatibility aliases
    "DriverError",
    "ExecutionError",
    "StepTimeoutError",
    # Helpers
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
    # Dependency management
    "ensure_package",
    "ensure_dependencies",
    "is_installed",
    "check_dependencies",
    "get_missing_packages",
]

"""
Station Service SDK - Build test sequences for manufacturing automation.

This SDK provides:
- SequenceBase: Base class for all sequences
- CLI tools for development, validation, and debugging
- JSON Lines output protocol for Station Service communication
- Execution context management
- Manifest models for package configuration
- Sequence package loader for discovery and loading
- Simulation and interactive testing tools
- Manual execution capabilities
- Hardware connection pooling and retry mechanisms
- Observability: structured logging, tracing, metrics
- Plugin system for extensibility
- Testing utilities: mocks, fixtures, assertions

Package Structure:
    station_service_sdk/
    ├── core/           # Core components (SequenceBase, Context, Protocol, Exceptions)
    ├── execution/      # Execution components (Loader, Registry, Simulator, Manual)
    ├── hardware/       # Hardware integration (Connection Pool, Retry, Health)
    ├── testing/        # Testing utilities (Mocks, Fixtures, Assertions)
    ├── observability/  # Observability (Logging, Tracing, Metrics)
    ├── plugins/        # Plugin system (Manager, Protocol Adapters)
    ├── cli/            # CLI tools (new, validate, run, debug, lint, doctor)
    └── compat/         # Backward compatibility (Decorators, Dependencies)

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

CLI Usage:
    station-sdk new my-sequence      # Create new sequence
    station-sdk validate .           # Validate sequence package
    station-sdk run . --dry-run      # Run in dry-run mode
    station-sdk debug . --step-by-step  # Interactive debug
    station-sdk doctor               # Diagnose environment
"""

__version__ = "2.0.0"  # Major version bump for enhanced SDK

# =============================================================================
# Core Module
# =============================================================================
from station_service_sdk.core.base import SequenceBase, StepResult
from station_service_sdk.core.context import ExecutionContext, Measurement
from station_service_sdk.core.protocol import MessageType, OutputProtocol
from station_service_sdk.core.interfaces import OutputStrategy, LifecycleHook, CompositeHook

# Types (TypedDict definitions and type aliases)
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

# Exceptions
from station_service_sdk.core.exceptions import (
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

# =============================================================================
# Execution Module
# =============================================================================
from station_service_sdk.execution.registry import (
    SequenceRegistry,
    register_sequence,
    get_sequence,
    list_sequences,
    discover_sequences,
)
from station_service_sdk.execution.loader import SequenceLoader
from station_service_sdk.execution.helpers import (
    collect_steps,
    collect_steps_from_manifest,
    collect_steps_from_class,
)
from station_service_sdk.execution.simulator import SequenceSimulator, MockHardware
from station_service_sdk.execution.interactive import (
    InteractiveSimulator,
    SimulationSession,
    SimulationSessionStatus,
    StepState,
    StepExecutionStatus,
)
from station_service_sdk.execution.driver_registry import (
    DriverRegistry,
    DriverLoadError,
    DriverConnectionError,
)
from station_service_sdk.execution.manual_executor import (
    ManualSequenceExecutor,
    ManualSession,
    ManualSessionStatus,
    ManualStepState,
    ManualStepStatus,
    HardwareState,
    CommandResult,
)

# =============================================================================
# Compatibility Module (Legacy support)
# =============================================================================
from station_service_sdk.compat.dependencies import (
    ensure_package,
    ensure_dependencies,
    is_installed,
    check_dependencies,
    get_missing_packages,
    parse_pyproject_dependencies,
    install_sequence_dependencies,
    get_pyproject_missing_packages,
)
from station_service_sdk.compat.decorators import (
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

# =============================================================================
# Public API
# =============================================================================
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
    "parse_pyproject_dependencies",
    "install_sequence_dependencies",
    "get_pyproject_missing_packages",
]

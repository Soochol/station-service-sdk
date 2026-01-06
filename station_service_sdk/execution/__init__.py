"""Execution module for Station Service SDK.

Contains execution-related components:
- SequenceLoader: Package discovery and loading
- SequenceRegistry: Sequence registration and lookup
- SequenceSimulator: Dry-run simulation
- InteractiveSimulator: Step-by-step debugging
- ManualSequenceExecutor: Manual hardware testing
- DriverRegistry: Hardware driver management
- Validation: Manifest and code validation
"""

from station_service_sdk.execution.loader import SequenceLoader
from station_service_sdk.execution.registry import (
    SequenceRegistry,
    register_sequence,
    get_sequence,
    list_sequences,
    discover_sequences,
)
from station_service_sdk.execution.simulator import SequenceSimulator, MockHardware
from station_service_sdk.execution.interactive import (
    InteractiveSimulator,
    SimulationSession,
    SimulationSessionStatus,
    StepState,
    StepExecutionStatus,
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
from station_service_sdk.execution.driver_registry import (
    DriverRegistry,
    DriverLoadError,
    DriverConnectionError,
)
from station_service_sdk.execution.helpers import (
    collect_steps,
    collect_steps_from_manifest,
    collect_steps_from_class,
)
from station_service_sdk.execution.validate import (
    EmitStepVisitor,
)

__all__ = [
    # Loader
    "SequenceLoader",
    # Registry
    "SequenceRegistry",
    "register_sequence",
    "get_sequence",
    "list_sequences",
    "discover_sequences",
    # Simulator
    "SequenceSimulator",
    "MockHardware",
    # Interactive
    "InteractiveSimulator",
    "SimulationSession",
    "SimulationSessionStatus",
    "StepState",
    "StepExecutionStatus",
    # Manual Executor
    "ManualSequenceExecutor",
    "ManualSession",
    "ManualSessionStatus",
    "ManualStepState",
    "ManualStepStatus",
    "HardwareState",
    "CommandResult",
    # Driver Registry
    "DriverRegistry",
    "DriverLoadError",
    "DriverConnectionError",
    # Helpers
    "collect_steps",
    "collect_steps_from_manifest",
    "collect_steps_from_class",
    # Validate
    "EmitStepVisitor",
]

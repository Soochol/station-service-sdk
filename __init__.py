"""
Station Service SDK - Build test sequences for manufacturing automation.

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

__version__ = "2.0.0"

from .base import SequenceBase, StepResult
from .context import ExecutionContext, Measurement
from .protocol import MessageType, OutputProtocol
from .sdk_types import (
    RunResult,
    ExecutionResult,
    MeasurementDict,
    StepResultDict,
    HardwareConfigDict,
    ParametersDict,
    MeasurementsDict,
)
from .exceptions import (
    SequenceError,
    SetupError,
    TeardownError,
    StepError,
    TimeoutError,
    AbortError,
    TestFailure,
    TestSkipped,
    HardwareError,
    ConnectionError,
    CommunicationError,
    PackageError,
    ManifestError,
    ValidationError,
    DependencyError,
)
from .manifest import (
    ParameterType,
    ConfigFieldSchema,
    HardwareDefinition,
    ParameterDefinition,
    EntryPoint,
    Modes,
    StepDefinition,
    SequenceManifest,
)

__all__ = [
    "__version__",
    "SequenceBase",
    "StepResult",
    "ExecutionContext",
    "Measurement",
    "MessageType",
    "OutputProtocol",
    "RunResult",
    "ExecutionResult",
    "MeasurementDict",
    "StepResultDict",
    "HardwareConfigDict",
    "ParametersDict",
    "MeasurementsDict",
    "ParameterType",
    "ConfigFieldSchema",
    "HardwareDefinition",
    "ParameterDefinition",
    "EntryPoint",
    "Modes",
    "StepDefinition",
    "SequenceManifest",
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
]

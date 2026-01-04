"""
SDK Type definitions.

This module provides unified type definitions for the SDK, including:
- TypedDict for structured return types
- Unified StepMeta dataclass
- Common type aliases

Usage:
    from station_service.sdk.types import RunResult, StepMeta, MeasurementDict
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypedDict, Union


# =============================================================================
# TypedDict Definitions for Structured Return Types
# =============================================================================


class MeasurementDict(TypedDict, total=False):
    """Structured measurement data for serialization."""

    name: str
    value: Union[int, float, str, bool]
    unit: str
    passed: Optional[bool]
    min: Optional[float]
    max: Optional[float]
    step: Optional[str]


class StepResultDict(TypedDict, total=False):
    """Structured step result for serialization."""

    name: str
    index: int
    passed: bool
    duration: float
    measurements: Dict[str, Any]
    data: Dict[str, Any]
    error: Optional[str]


class RunResult(TypedDict, total=False):
    """
    Structured return type for SequenceBase.run() method.

    Usage:
        async def run(self) -> RunResult:
            return {
                "passed": True,
                "measurements": {"voltage": 3.3},
                "data": {"serial": "ABC123"},
            }
    """

    passed: bool
    measurements: Dict[str, Any]
    data: Dict[str, Any]


class ExecutionResult(TypedDict, total=False):
    """
    Complete execution result from _execute() method.

    Includes all information about the sequence run.
    """

    passed: bool
    measurements: Dict[str, Any]
    steps: List[StepResultDict]
    data: Dict[str, Any]
    duration: float
    error: Optional[str]


class SimulationResult(TypedDict, total=False):
    """Result from dry-run simulation."""

    status: str  # "completed", "failed"
    overall_pass: bool
    started_at: str
    completed_at: str
    steps: List[Dict[str, Any]]
    error: Optional[str]


# =============================================================================
# Unified StepMeta Dataclass
# =============================================================================


@dataclass(frozen=True)
class StepMeta:
    """
    Unified step metadata structure.

    Used by both legacy decorator-based sequences and SDK-based sequences.
    This is the canonical definition - other modules should import from here.

    Attributes:
        name: Step identifier
        order: Execution order (lower numbers run first)
        timeout: Maximum execution time in seconds
        retry: Number of retry attempts on failure
        cleanup: If True, always runs even after failures
        condition: Optional condition expression for conditional execution
        description: Human-readable description
        display_name: Display name for UI (defaults to name)
        estimated_duration: Estimated duration in seconds
    """

    name: str
    order: int
    timeout: float = 60.0
    retry: int = 0
    cleanup: bool = False
    condition: Optional[str] = None
    description: str = ""
    display_name: str = ""
    estimated_duration: float = 0.0

    def __post_init__(self):
        # Set display_name to name if not provided
        if not self.display_name:
            object.__setattr__(self, "display_name", self.name)


@dataclass(frozen=True)
class StepInfo:
    """
    Extended step information including method reference.

    Used when collecting steps from a sequence class.
    """

    name: str
    display_name: str
    order: int
    timeout: float = 60.0
    retry: int = 0
    cleanup: bool = False
    description: str = ""
    method: Optional[Callable] = None

    def to_meta(self) -> StepMeta:
        """Convert to StepMeta."""
        return StepMeta(
            name=self.name,
            order=self.order,
            timeout=self.timeout,
            retry=self.retry,
            cleanup=self.cleanup,
            description=self.description,
            display_name=self.display_name,
        )


# =============================================================================
# Protocol Message Types (for type hints)
# =============================================================================


class LogMessageData(TypedDict, total=False):
    """Data structure for log messages."""

    level: str  # debug, info, warning, error
    message: str


class StepStartData(TypedDict):
    """Data structure for step start events."""

    step: str
    index: int
    total: int
    description: str


class StepCompleteData(TypedDict, total=False):
    """Data structure for step complete events."""

    step: str
    index: int
    passed: bool
    duration: float
    measurements: Dict[str, Any]
    error: Optional[str]
    data: Dict[str, Any]


class SequenceCompleteData(TypedDict, total=False):
    """Data structure for sequence complete events."""

    overall_pass: bool
    duration: float
    steps: List[StepResultDict]
    measurements: Dict[str, Any]
    error: Optional[str]


class StatusData(TypedDict, total=False):
    """Data structure for status updates."""

    status: str  # running, paused, waiting, setup, teardown
    progress: float  # 0-100
    current_step: Optional[str]
    message: str


class ErrorData(TypedDict, total=False):
    """Data structure for error events."""

    code: str
    message: str
    step: Optional[str]
    recoverable: bool


class InputRequestData(TypedDict, total=False):
    """Data structure for input request events."""

    id: str
    prompt: str
    input_type: str  # confirm, text, number, select
    options: Optional[List[str]]
    default: Any
    timeout: Optional[float]


# =============================================================================
# Type Aliases
# =============================================================================

# Hardware configuration: {"mcu": {"port": "/dev/ttyUSB0", ...}}
HardwareConfigDict = Dict[str, Dict[str, Any]]

# Parameters dictionary
ParametersDict = Dict[str, Any]

# Measurements dictionary: {"voltage": 3.3, "current": 0.1}
MeasurementsDict = Dict[str, Union[int, float, str, bool, MeasurementDict]]

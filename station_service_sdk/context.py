"""
Execution context for sequence runs.

Holds all contextual information about the current execution:
- Execution ID
- WIP ID
- Process ID
- Operator ID
- Hardware configuration
- Parameters
- Timestamps
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Union
import uuid


@dataclass
class Measurement:
    """
    Standardized measurement data structure.

    Provides consistent format for all measurement operations:
    - emit_measurement()
    - step_complete measurements
    - sequence_complete measurements

    Usage:
        # Numeric with limits (auto-calculated pass/fail)
        m = Measurement(name="voltage", value=3.3, unit="V", min_value=3.0, max_value=3.6)
        m.passed  # True (auto-calculated)

        # Boolean value
        m = Measurement(name="connected", value=True)
        m.passed  # True (boolean values auto-set passed to their value)

        # String value (must set passed explicitly)
        m = Measurement(name="serial", value="ABC123", passed=True)
    """

    name: str
    value: Union[int, float, str, bool]
    unit: str = ""
    passed: Optional[bool] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step_name: Optional[str] = None
    timestamp: Optional[datetime] = field(default_factory=datetime.now)

    def __post_init__(self):
        """
        Auto-calculate passed based on value type and limits.

        - Numeric values: Compare against min/max limits if provided
        - Boolean values: passed = value (True means passed, False means failed)
        - String values: Cannot auto-calculate, requires explicit passed value
        - Limits on non-numeric values: Ignored with warning logged
        """
        import logging

        # Validate limits are only used with numeric values
        has_limits = self.min_value is not None or self.max_value is not None
        is_numeric = isinstance(self.value, (int, float)) and not isinstance(self.value, bool)

        if has_limits and not is_numeric:
            logging.warning(
                f"Measurement '{self.name}': min/max limits ignored for "
                f"non-numeric value of type {type(self.value).__name__}"
            )

        # Auto-calculate passed if not explicitly set
        if self.passed is None:
            if is_numeric:
                # Numeric: compare against limits
                if self.min_value is not None and self.max_value is not None:
                    self.passed = self.min_value <= self.value <= self.max_value
                elif self.min_value is not None:
                    self.passed = self.value >= self.min_value
                elif self.max_value is not None:
                    self.passed = self.value <= self.max_value
                # No limits: leave passed as None (unknown)
            elif isinstance(self.value, bool):
                # Boolean: passed equals the value
                self.passed = self.value
            # String: leave passed as None (must be set explicitly)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization (protocol output)."""
        data: Dict[str, Any] = {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
        }
        if self.passed is not None:
            data["passed"] = self.passed
        if self.min_value is not None:
            data["min"] = self.min_value
        if self.max_value is not None:
            data["max"] = self.max_value
        if self.step_name:
            data["step"] = self.step_name
        return data

    def to_storage_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for internal storage (measurements dict)."""
        return {
            "value": self.value,
            "unit": self.unit,
            "passed": self.passed,
            "min": self.min_value,
            "max": self.max_value,
        }

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "Measurement":
        """Create Measurement from dictionary."""
        value = data.get("value")
        if value is None:
            value = 0  # Default value if not provided
        return cls(
            name=name,
            value=value,
            unit=data.get("unit", ""),
            passed=data.get("passed"),
            min_value=data.get("min"),
            max_value=data.get("max"),
            step_name=data.get("step"),
        )


@dataclass
class ExecutionContext:
    """
    Context for a single sequence execution.

    This is passed to SequenceBase and available throughout execution.
    """

    # Identifiers
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    wip_id: Optional[str] = None
    batch_id: Optional[str] = None

    # MES Integration
    process_id: Optional[int] = None
    operator_id: Optional[int] = None
    lot_id: Optional[str] = None
    serial_number: Optional[str] = None

    # Configuration
    hardware_config: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Hardware instances (populated at runtime)
    hardware: Dict[str, Any] = field(default_factory=dict)

    # Execution mode
    dry_run: bool = False

    # Execution state
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Metadata
    sequence_name: str = ""
    sequence_version: str = ""
    station_id: str = ""

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "ExecutionContext":
        """
        Create ExecutionContext from CLI config dict.

        Args:
            config: Configuration dictionary from CLI --config argument

        Returns:
            ExecutionContext instance
        """
        return cls(
            execution_id=config.get("execution_id", str(uuid.uuid4())[:8]),
            wip_id=config.get("wip_id"),
            batch_id=config.get("batch_id"),
            process_id=config.get("process_id"),
            operator_id=config.get("operator_id"),
            lot_id=config.get("lot_id"),
            serial_number=config.get("serial_number"),
            hardware_config=config.get("hardware", {}),
            parameters=config.get("parameters", {}),
            sequence_name=config.get("sequence_name", ""),
            sequence_version=config.get("sequence_version", ""),
            station_id=config.get("station_id", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            "execution_id": self.execution_id,
            "wip_id": self.wip_id,
            "batch_id": self.batch_id,
            "process_id": self.process_id,
            "operator_id": self.operator_id,
            "lot_id": self.lot_id,
            "serial_number": self.serial_number,
            "hardware_config": self.hardware_config,
            "parameters": self.parameters,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "sequence_name": self.sequence_name,
            "sequence_version": self.sequence_version,
            "station_id": self.station_id,
        }

    def start(self) -> None:
        """Mark execution as started."""
        self.started_at = datetime.now()

    def complete(self) -> None:
        """Mark execution as completed."""
        self.completed_at = datetime.now()

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return None

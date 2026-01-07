"""Mock builders and utilities for testing sequences.

Provides fluent APIs for creating mock hardware drivers and
capturing sequence output for assertions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Self

from station_service_sdk.interfaces import OutputStrategy
from station_service_sdk.sdk_types import MessageType


@dataclass
class MockDriverConfig:
    """Configuration for mock driver behavior.

    Attributes:
        connect_success: Whether connect() should succeed
        measurements: Predefined measurement values
        command_results: Results for specific commands
        command_failures: Exceptions to raise for commands
        connect_delay: Simulated connection delay in seconds
        command_delay: Simulated command delay in seconds
    """

    connect_success: bool = True
    measurements: dict[str, Any] = field(default_factory=dict)
    command_results: dict[str, Any] = field(default_factory=dict)
    command_failures: dict[str, Exception] = field(default_factory=dict)
    connect_delay: float = 0.0
    command_delay: float = 0.0


class MockDriver:
    """Configurable mock hardware driver.

    Simulates hardware driver behavior for testing without
    actual hardware connections.

    Attributes:
        config: Mock driver configuration
        connected: Current connection state
        command_history: List of executed commands
    """

    def __init__(self, config: MockDriverConfig | None = None):
        """Initialize mock driver.

        Args:
            config: Optional configuration for mock behavior
        """
        self.config = config or MockDriverConfig()
        self.connected = False
        self.command_history: list[dict[str, Any]] = []
        self._call_counts: dict[str, int] = {}

    async def connect(self) -> None:
        """Simulate connection to hardware."""
        import asyncio

        if self.config.connect_delay > 0:
            await asyncio.sleep(self.config.connect_delay)

        if not self.config.connect_success:
            from station_service_sdk.exceptions import HardwareConnectionError

            raise HardwareConnectionError("Mock connection failed")

        self.connected = True

    async def disconnect(self) -> None:
        """Simulate disconnection from hardware."""
        self.connected = False

    def is_connected(self) -> bool:
        """Check if connected.

        Returns:
            Current connection state
        """
        return self.connected

    async def execute_command(self, command: str, **kwargs: Any) -> Any:
        """Execute a mock command.

        Args:
            command: Command name
            **kwargs: Command arguments

        Returns:
            Configured result for the command

        Raises:
            Configured exception if set for this command
        """
        import asyncio

        self._call_counts[command] = self._call_counts.get(command, 0) + 1

        self.command_history.append({
            "command": command,
            "kwargs": kwargs,
            "timestamp": datetime.now().isoformat(),
        })

        if self.config.command_delay > 0:
            await asyncio.sleep(self.config.command_delay)

        if command in self.config.command_failures:
            raise self.config.command_failures[command]

        return self.config.command_results.get(command)

    async def measure(self, name: str) -> Any:
        """Get a mock measurement value.

        Args:
            name: Measurement name

        Returns:
            Configured measurement value or 0.0
        """
        return self.config.measurements.get(name, 0.0)

    def get_call_count(self, command: str) -> int:
        """Get number of times a command was called.

        Args:
            command: Command name

        Returns:
            Call count
        """
        return self._call_counts.get(command, 0)

    def reset(self) -> None:
        """Reset mock state."""
        self.connected = False
        self.command_history.clear()
        self._call_counts.clear()


class MockDriverBuilder:
    """Fluent builder for creating MockDriver instances.

    Example:
        >>> driver = (
        ...     MockDriverBuilder()
        ...     .with_measurement("voltage", 3.3)
        ...     .with_measurement("current", 0.5)
        ...     .with_command_result("identify", "MockDevice v1.0")
        ...     .with_connect_delay(0.1)
        ...     .build()
        ... )
    """

    def __init__(self) -> None:
        """Initialize builder with default config."""
        self._config = MockDriverConfig()

    def with_connect_success(self, success: bool) -> Self:
        """Set whether connection should succeed.

        Args:
            success: Connection success flag

        Returns:
            Self for chaining
        """
        self._config.connect_success = success
        return self

    def with_connect_failure(self, error: Exception | None = None) -> Self:
        """Configure connection to fail.

        Args:
            error: Optional custom exception

        Returns:
            Self for chaining
        """
        self._config.connect_success = False
        return self

    def with_measurement(self, name: str, value: Any) -> Self:
        """Add a mock measurement value.

        Args:
            name: Measurement name
            value: Value to return

        Returns:
            Self for chaining
        """
        self._config.measurements[name] = value
        return self

    def with_measurements(self, measurements: dict[str, Any]) -> Self:
        """Add multiple mock measurement values.

        Args:
            measurements: Dictionary of measurement values

        Returns:
            Self for chaining
        """
        self._config.measurements.update(measurements)
        return self

    def with_command_result(self, command: str, result: Any) -> Self:
        """Set result for a command.

        Args:
            command: Command name
            result: Result to return

        Returns:
            Self for chaining
        """
        self._config.command_results[command] = result
        return self

    def with_command_failure(self, command: str, error: Exception) -> Self:
        """Configure a command to fail.

        Args:
            command: Command name
            error: Exception to raise

        Returns:
            Self for chaining
        """
        self._config.command_failures[command] = error
        return self

    def with_connect_delay(self, delay: float) -> Self:
        """Set connection delay.

        Args:
            delay: Delay in seconds

        Returns:
            Self for chaining
        """
        self._config.connect_delay = delay
        return self

    def with_command_delay(self, delay: float) -> Self:
        """Set command execution delay.

        Args:
            delay: Delay in seconds

        Returns:
            Self for chaining
        """
        self._config.command_delay = delay
        return self

    def build(self) -> MockDriver:
        """Build the MockDriver instance.

        Returns:
            Configured MockDriver
        """
        return MockDriver(self._config)


class MockHardwareRegistry:
    """Registry for mock hardware drivers.

    Allows pre-registration of mock drivers for testing.
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._drivers: dict[str, MockDriver] = {}
        self._builders: dict[str, MockDriverBuilder] = {}

    def register(self, hardware_id: str, driver: MockDriver) -> None:
        """Register a mock driver.

        Args:
            hardware_id: Hardware identifier
            driver: Mock driver instance
        """
        self._drivers[hardware_id] = driver

    def register_builder(self, hardware_id: str, builder: MockDriverBuilder) -> None:
        """Register a builder for lazy driver creation.

        Args:
            hardware_id: Hardware identifier
            builder: Mock driver builder
        """
        self._builders[hardware_id] = builder

    def get(self, hardware_id: str) -> MockDriver | None:
        """Get a registered mock driver.

        Args:
            hardware_id: Hardware identifier

        Returns:
            Mock driver or None if not found
        """
        if hardware_id in self._drivers:
            return self._drivers[hardware_id]

        if hardware_id in self._builders:
            driver = self._builders[hardware_id].build()
            self._drivers[hardware_id] = driver
            return driver

        return None

    def reset_all(self) -> None:
        """Reset all registered drivers."""
        for driver in self._drivers.values():
            driver.reset()


@dataclass
class CapturedMessage:
    """A captured output message.

    Attributes:
        type: Message type
        data: Message data
        timestamp: When message was captured
    """

    type: str
    data: dict[str, Any]
    timestamp: str


class CapturedOutput(OutputStrategy):
    """Output strategy that captures messages for testing.

    Captures all output messages in memory for later assertion.
    """

    def __init__(self) -> None:
        """Initialize with empty message list."""
        self.messages: list[CapturedMessage] = []
        self._execution_id: str = "test-execution"

    def set_execution_id(self, execution_id: str) -> None:
        """Set execution ID for messages.

        Args:
            execution_id: Execution identifier
        """
        self._execution_id = execution_id

    def _capture(self, msg_type: str, **data: Any) -> None:
        """Capture a message.

        Args:
            msg_type: Message type
            **data: Message data
        """
        self.messages.append(CapturedMessage(
            type=msg_type,
            data=data,
            timestamp=datetime.now().isoformat(),
        ))

    def log(self, level: str, message: str, **extra: Any) -> None:
        """Capture log message."""
        self._capture("LOG", level=level, message=message, **extra)

    def step_start(
        self,
        step_name: str,
        index: int,
        total: int,
        description: str = "",
    ) -> None:
        """Capture step start message."""
        self._capture(
            "STEP_START",
            step_name=step_name,
            index=index,
            total=total,
            description=description,
        )

    def step_complete(
        self,
        step_name: str,
        index: int,
        passed: bool,
        duration: float,
        measurements: dict[str, Any] | None = None,
        error: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Capture step complete message."""
        self._capture(
            "STEP_COMPLETE",
            step_name=step_name,
            index=index,
            passed=passed,
            duration=duration,
            measurements=measurements or {},
            error=error,
            data=data or {},
        )

    def measurement(
        self,
        name: str,
        value: float | int | str | bool | None,
        unit: str = "",
        passed: bool | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        step_name: str | None = None,
    ) -> None:
        """Capture measurement message."""
        self._capture(
            "MEASUREMENT",
            name=name,
            value=value,
            unit=unit,
            passed=passed,
            min_value=min_value,
            max_value=max_value,
            step_name=step_name,
        )

    def error(
        self,
        code: str,
        message: str,
        step: str | None = None,
        recoverable: bool = False,
    ) -> None:
        """Capture error message."""
        self._capture(
            "ERROR",
            code=code,
            message=message,
            step=step,
            recoverable=recoverable,
        )

    def sequence_complete(
        self,
        overall_pass: bool,
        duration: float,
        steps: list[dict[str, Any]],
        measurements: dict[str, Any],
        error: str | None = None,
    ) -> None:
        """Capture sequence complete message."""
        self._capture(
            "SEQUENCE_COMPLETE",
            overall_pass=overall_pass,
            duration=duration,
            steps=steps,
            measurements=measurements,
            error=error,
        )

    def input_request(
        self,
        request_id: str,
        prompt: str,
        input_type: str = "confirm",
        options: list[str] | None = None,
        default: Any = None,
        timeout: float | None = None,
    ) -> None:
        """Capture input request message."""
        self._capture(
            "INPUT_REQUEST",
            request_id=request_id,
            prompt=prompt,
            input_type=input_type,
            options=options,
            default=default,
            timeout=timeout,
        )

    def status(
        self,
        status: str,
        progress: float = 0.0,
        current_step: str | None = None,
        message: str = "",
    ) -> None:
        """Capture status message."""
        self._capture(
            "STATUS",
            status=status,
            progress=progress,
            current_step=current_step,
            message=message,
        )

    def wait_for_input(self, request_id: str, timeout: float = 300) -> Any:
        """Wait for user input response (mock returns None)."""
        return None

    # Query methods for assertions

    def get_messages_by_type(self, msg_type: str) -> list[CapturedMessage]:
        """Get all messages of a specific type.

        Args:
            msg_type: Message type to filter

        Returns:
            List of matching messages
        """
        return [m for m in self.messages if m.type == msg_type]

    def get_step_results(self) -> list[dict[str, Any]]:
        """Get all step completion results.

        Returns:
            List of step result dictionaries
        """
        return [m.data for m in self.get_messages_by_type("STEP_COMPLETE")]

    def get_measurements(self) -> dict[str, Any]:
        """Get all measurements as a dictionary.

        Returns:
            Dictionary mapping measurement names to values
        """
        measurements = {}
        for msg in self.get_messages_by_type("MEASUREMENT"):
            measurements[msg.data["name"]] = msg.data["value"]
        return measurements

    def get_errors(self) -> list[dict[str, Any]]:
        """Get all error messages.

        Returns:
            List of error dictionaries
        """
        return [m.data for m in self.get_messages_by_type("ERROR")]

    def get_final_result(self) -> dict[str, Any] | None:
        """Get sequence completion result.

        Returns:
            Final result dictionary or None
        """
        complete_msgs = self.get_messages_by_type("SEQUENCE_COMPLETE")
        return complete_msgs[-1].data if complete_msgs else None

    def to_json_lines(self) -> str:
        """Convert captured messages to JSON Lines format.

        Returns:
            JSON Lines string
        """
        lines = []
        for msg in self.messages:
            line = {
                "type": msg.type,
                "timestamp": msg.timestamp,
                "execution_id": self._execution_id,
                "data": msg.data,
            }
            lines.append(json.dumps(line))
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all captured messages."""
        self.messages.clear()

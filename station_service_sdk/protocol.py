"""
JSON Lines output protocol for CLI sequences.

Each line emitted to stdout is a complete JSON object that Station Service
can parse to track execution progress, measurements, and results.

Message Types:
- log: Log messages (info, warning, error, debug)
- step_start: Step execution started
- step_complete: Step execution completed
- sequence_complete: Entire sequence completed
- measurement: Measurement data point
- error: Error occurred
- status: Status update (progress, state changes)
- input_request: Request user input (manual control)
- input_response: Response to input request (from stdin)
"""

import json
import sys
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .exceptions import TimeoutError as SDKTimeoutError

if TYPE_CHECKING:
    from .context import ExecutionContext


class MessageType(str, Enum):
    """Output message types."""

    LOG = "log"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    SEQUENCE_COMPLETE = "sequence_complete"
    MEASUREMENT = "measurement"
    ERROR = "error"
    STATUS = "status"
    INPUT_REQUEST = "input_request"
    INPUT_RESPONSE = "input_response"


class OutputProtocol:
    """
    JSON Lines output protocol.

    Each line is a complete JSON object with:
    - type: Message type
    - timestamp: ISO format
    - execution_id: Execution identifier
    - data: Message-specific payload

    Usage:
        protocol = OutputProtocol(context)
        protocol.log("info", "Starting test...")
        protocol.measurement("voltage", 3.28, "V")
        protocol.step_complete(StepResult(...))
    """

    def __init__(self, context: "ExecutionContext"):
        self.context = context

    def _emit(self, msg_type: MessageType, data: Dict[str, Any]) -> None:
        """Emit a JSON line to stdout."""
        message = {
            "type": msg_type.value,
            "timestamp": datetime.now().isoformat(),
            "execution_id": self.context.execution_id,
            "data": data,
        }
        print(json.dumps(message, ensure_ascii=False), flush=True)

    def log(self, level: str, message: str, **extra: Any) -> None:
        """
        Emit log message.

        Args:
            level: Log level (debug, info, warning, error)
            message: Log message
            **extra: Additional key-value pairs
        """
        self._emit(
            MessageType.LOG,
            {
                "level": level,
                "message": message,
                **extra,
            },
        )

    def step_start(
        self,
        step_name: str,
        index: int,
        total: int,
        description: str = "",
    ) -> None:
        """
        Emit step start event.

        Args:
            step_name: Name of the step
            index: Current step index (1-based)
            total: Total number of steps
            description: Optional step description
        """
        self._emit(
            MessageType.STEP_START,
            {
                "step": step_name,
                "index": index,
                "total": total,
                "description": description,
            },
        )

    def step_complete(
        self,
        step_name: str,
        index: int,
        passed: bool,
        duration: float,
        measurements: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit step complete event.

        Args:
            step_name: Name of the step
            index: Step index (1-based)
            passed: Whether step passed
            duration: Step duration in seconds
            measurements: Measurement data from step
            error: Error message if failed
            data: Additional result data
        """
        self._emit(
            MessageType.STEP_COMPLETE,
            {
                "step": step_name,
                "index": index,
                "passed": passed,
                "duration": duration,
                "measurements": measurements or {},
                "error": error,
                "data": data or {},
            },
        )

    def sequence_complete(
        self,
        overall_pass: bool,
        duration: float,
        steps: List[Dict[str, Any]],
        measurements: Dict[str, Any],
        error: Optional[str] = None,
    ) -> None:
        """
        Emit sequence complete event.

        Args:
            overall_pass: Whether sequence passed overall
            duration: Total duration in seconds
            steps: List of step results
            measurements: All measurements collected
            error: Error message if failed
        """
        self._emit(
            MessageType.SEQUENCE_COMPLETE,
            {
                "overall_pass": overall_pass,
                "duration": duration,
                "steps": steps,
                "measurements": measurements,
                "error": error,
            },
        )

    def measurement(
        self,
        name: str,
        value: Any,
        unit: str = "",
        passed: Optional[bool] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        step_name: Optional[str] = None,
    ) -> None:
        """
        Emit measurement data point.

        Args:
            name: Measurement name
            value: Measured value
            unit: Unit of measurement
            passed: Whether measurement passed limits
            min_value: Minimum acceptable value
            max_value: Maximum acceptable value
            step_name: Associated step name
        """
        data: Dict[str, Any] = {
            "name": name,
            "value": value,
            "unit": unit,
        }
        if passed is not None:
            data["passed"] = passed
        if min_value is not None:
            data["min"] = min_value
        if max_value is not None:
            data["max"] = max_value
        if step_name:
            data["step"] = step_name

        self._emit(MessageType.MEASUREMENT, data)

    def error(
        self,
        code: str,
        message: str,
        step: Optional[str] = None,
        recoverable: bool = False,
    ) -> None:
        """
        Emit error event.

        Args:
            code: Error code
            message: Error message
            step: Associated step name
            recoverable: Whether error is recoverable
        """
        self._emit(
            MessageType.ERROR,
            {
                "code": code,
                "message": message,
                "step": step,
                "recoverable": recoverable,
            },
        )

    def status(
        self,
        status: str,
        progress: float,
        current_step: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Emit status update.

        Args:
            status: Current status (running, paused, waiting, etc.)
            progress: Progress percentage (0-100)
            current_step: Currently executing step
            message: Status message
        """
        self._emit(
            MessageType.STATUS,
            {
                "status": status,
                "progress": progress,
                "current_step": current_step,
                "message": message,
            },
        )

    def input_request(
        self,
        request_id: str,
        prompt: str,
        input_type: str = "confirm",
        options: Optional[List[str]] = None,
        default: Any = None,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Request user input (for manual control).

        Args:
            request_id: Unique ID for this request
            prompt: Prompt message to show user
            input_type: Type of input (confirm, text, number, select)
            options: Options for select type
            default: Default value
            timeout: Timeout in seconds
        """
        self._emit(
            MessageType.INPUT_REQUEST,
            {
                "id": request_id,
                "prompt": prompt,
                "input_type": input_type,
                "options": options,
                "default": default,
                "timeout": timeout,
            },
        )

    def wait_for_input(self, request_id: str, timeout: float = 300) -> Any:
        """
        Wait for input response from stdin.

        Uses selectors module for cross-platform compatibility (works on Windows, Linux, macOS).

        Args:
            request_id: The request ID to wait for
            timeout: Timeout in seconds

        Returns:
            The input value from user

        Raises:
            SequenceTimeoutError: If timeout is reached before receiving valid input
        """
        import selectors

        # Use selectors for cross-platform stdin polling
        sel = selectors.DefaultSelector()
        try:
            sel.register(sys.stdin, selectors.EVENT_READ)

            start_time = datetime.now()
            while True:
                elapsed = (datetime.now() - start_time).total_seconds()
                remaining = timeout - elapsed
                if remaining <= 0:
                    raise SDKTimeoutError(
                        f"Input timeout after {timeout}s",
                        timeout_seconds=timeout,
                        elapsed_seconds=elapsed,
                    )

                # Wait for stdin with remaining timeout (poll every 1s max)
                poll_timeout = min(1.0, remaining)
                events = sel.select(timeout=poll_timeout)

                if events:
                    line = sys.stdin.readline().strip()
                    if line:
                        try:
                            response = json.loads(line)
                            if (
                                response.get("type") == "input_response"
                                and response.get("data", {}).get("id") == request_id
                            ):
                                return response["data"].get("value")
                        except json.JSONDecodeError:
                            continue
        finally:
            sel.unregister(sys.stdin)
            sel.close()

"""Structured logging for Station Service SDK.

Provides structured JSON logging with automatic context fields
from execution context.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, TextIO

from station_service_sdk.context import ExecutionContext


@dataclass
class LogRecord:
    """Structured log record.

    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: Log message
        timestamp: ISO format timestamp
        execution_id: Execution identifier
        sequence_name: Sequence name
        step_name: Current step name (if applicable)
        step_index: Current step index (if applicable)
        extra: Additional contextual fields
    """

    level: str
    message: str
    timestamp: str
    execution_id: str
    sequence_name: str
    step_name: str | None = None
    step_index: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with all log record fields
        """
        data = asdict(self)
        # Remove None values for cleaner output
        return {k: v for k, v in data.items() if v is not None}

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            JSON formatted log record
        """
        return json.dumps(self.to_dict(), default=str)


class StructuredLogger:
    """Logger with automatic context fields.

    Provides structured logging that automatically includes
    execution context in all log messages.

    Example:
        >>> logger = StructuredLogger(context)
        >>> logger.info("Starting measurement")
        >>> logger.error("Connection failed", exception=e)
    """

    def __init__(
        self,
        context: ExecutionContext,
        output: TextIO | None = None,
        min_level: str = "DEBUG",
    ):
        """Initialize structured logger.

        Args:
            context: Execution context for automatic fields
            output: Output stream (default: stderr)
            min_level: Minimum log level to output
        """
        self.context = context
        self.output = output or sys.stderr
        self._current_step: str | None = None
        self._current_step_index: int | None = None
        self._level_order = {
            "DEBUG": 0,
            "INFO": 1,
            "WARNING": 2,
            "ERROR": 3,
            "CRITICAL": 4,
        }
        self._min_level = min_level

    def set_step(self, name: str, index: int) -> None:
        """Set current step context.

        Args:
            name: Step name
            index: Step index
        """
        self._current_step = name
        self._current_step_index = index

    def clear_step(self) -> None:
        """Clear current step context."""
        self._current_step = None
        self._current_step_index = None

    def _should_log(self, level: str) -> bool:
        """Check if level should be logged.

        Args:
            level: Log level

        Returns:
            True if should log
        """
        return (
            self._level_order.get(level, 0) >=
            self._level_order.get(self._min_level, 0)
        )

    def _create_record(self, level: str, message: str, **extra: Any) -> LogRecord:
        """Create a log record with context.

        Args:
            level: Log level
            message: Log message
            **extra: Additional fields

        Returns:
            LogRecord instance
        """
        return LogRecord(
            level=level,
            message=message,
            timestamp=datetime.now().isoformat(),
            execution_id=self.context.execution_id,
            sequence_name=self.context.sequence_name,
            step_name=self._current_step,
            step_index=self._current_step_index,
            extra=extra,
        )

    def _emit(self, record: LogRecord) -> None:
        """Emit a log record.

        Args:
            record: Log record to emit
        """
        if self._should_log(record.level):
            self.output.write(record.to_json() + "\n")
            self.output.flush()

    def debug(self, message: str, **extra: Any) -> None:
        """Log debug message.

        Args:
            message: Log message
            **extra: Additional fields
        """
        record = self._create_record("DEBUG", message, **extra)
        self._emit(record)

    def info(self, message: str, **extra: Any) -> None:
        """Log info message.

        Args:
            message: Log message
            **extra: Additional fields
        """
        record = self._create_record("INFO", message, **extra)
        self._emit(record)

    def warning(self, message: str, **extra: Any) -> None:
        """Log warning message.

        Args:
            message: Log message
            **extra: Additional fields
        """
        record = self._create_record("WARNING", message, **extra)
        self._emit(record)

    def error(
        self,
        message: str,
        exception: Exception | None = None,
        **extra: Any,
    ) -> None:
        """Log error message.

        Args:
            message: Log message
            exception: Optional exception
            **extra: Additional fields
        """
        if exception:
            extra["exception_type"] = type(exception).__name__
            extra["exception_message"] = str(exception)

        record = self._create_record("ERROR", message, **extra)
        self._emit(record)

    def critical(
        self,
        message: str,
        exception: Exception | None = None,
        **extra: Any,
    ) -> None:
        """Log critical message.

        Args:
            message: Log message
            exception: Optional exception
            **extra: Additional fields
        """
        if exception:
            extra["exception_type"] = type(exception).__name__
            extra["exception_message"] = str(exception)

        record = self._create_record("CRITICAL", message, **extra)
        self._emit(record)

    def measurement(
        self,
        name: str,
        value: float | int | str | bool,
        unit: str = "",
        passed: bool | None = None,
        **extra: Any,
    ) -> None:
        """Log a measurement.

        Args:
            name: Measurement name
            value: Measured value
            unit: Unit of measurement
            passed: Whether measurement passed
            **extra: Additional fields
        """
        extra.update({
            "measurement_name": name,
            "measurement_value": value,
            "measurement_unit": unit,
            "measurement_passed": passed,
        })
        record = self._create_record("INFO", f"Measurement: {name}={value}{unit}", **extra)
        self._emit(record)


class StructuredLogHandler(logging.Handler):
    """Python logging handler that outputs structured JSON.

    Integrates with Python's standard logging module to provide
    structured output.
    """

    def __init__(
        self,
        context: ExecutionContext | None = None,
        output: TextIO | None = None,
    ):
        """Initialize handler.

        Args:
            context: Optional execution context
            output: Output stream (default: stderr)
        """
        super().__init__()
        self.context = context
        self.output = output or sys.stderr

    def set_context(self, context: ExecutionContext) -> None:
        """Set execution context.

        Args:
            context: Execution context
        """
        self.context = context

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record.

        Args:
            record: Python logging record
        """
        try:
            data: dict[str, Any] = {
                "level": record.levelname,
                "message": record.getMessage(),
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

            if self.context:
                data["execution_id"] = self.context.execution_id
                data["sequence_name"] = self.context.sequence_name

            if record.exc_info:
                data["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
                data["exception_message"] = str(record.exc_info[1]) if record.exc_info[1] else None

            self.output.write(json.dumps(data, default=str) + "\n")
            self.output.flush()

        except Exception:
            self.handleError(record)


def configure_logging(
    context: ExecutionContext | None = None,
    level: str = "INFO",
    output: TextIO | None = None,
) -> logging.Logger:
    """Configure structured logging for the SDK.

    Sets up the root logger with structured JSON output.

    Args:
        context: Optional execution context
        level: Minimum log level
        output: Output stream (default: stderr)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("station_sdk")
    logger.setLevel(getattr(logging, level))

    # Remove existing handlers
    logger.handlers.clear()

    # Add structured handler
    handler = StructuredLogHandler(context=context, output=output)
    handler.setLevel(getattr(logging, level))
    logger.addHandler(handler)

    return logger


class LoggingHook:
    """Lifecycle hook for structured logging.

    Automatically logs lifecycle events with structured format.
    """

    def __init__(self, logger: StructuredLogger):
        """Initialize logging hook.

        Args:
            logger: Structured logger instance
        """
        self.logger = logger

    async def on_setup_start(self, context: ExecutionContext) -> None:
        """Log setup start."""
        self.logger.info("Setup starting")

    async def on_setup_complete(
        self,
        context: ExecutionContext,
        duration: float,
        error: Exception | None = None,
    ) -> None:
        """Log setup completion."""
        if error:
            self.logger.error("Setup failed", exception=error, duration=duration)
        else:
            self.logger.info("Setup completed", duration=duration)

    async def on_step_start(
        self,
        context: ExecutionContext,
        step_name: str,
        index: int,
        total: int,
    ) -> None:
        """Log step start."""
        self.logger.set_step(step_name, index)
        self.logger.info(
            f"Step started: {step_name}",
            step_index=index,
            total_steps=total,
        )

    async def on_step_complete(
        self,
        context: ExecutionContext,
        step_name: str,
        index: int,
        passed: bool,
        duration: float,
        error: str | None = None,
    ) -> None:
        """Log step completion."""
        if passed:
            self.logger.info(
                f"Step passed: {step_name}",
                duration=duration,
            )
        else:
            self.logger.warning(
                f"Step failed: {step_name}",
                duration=duration,
                error=error,
            )
        self.logger.clear_step()

    async def on_measurement(
        self,
        context: ExecutionContext,
        measurement: Any,
    ) -> None:
        """Log measurement."""
        self.logger.measurement(
            name=measurement.name,
            value=measurement.value,
            unit=measurement.unit,
            passed=measurement.passed,
        )

    async def on_sequence_complete(
        self,
        context: ExecutionContext,
        result: dict[str, Any],
    ) -> None:
        """Log sequence completion."""
        if result.get("passed"):
            self.logger.info("Sequence completed successfully", **result)
        else:
            self.logger.warning("Sequence failed", **result)

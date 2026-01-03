"""
Base class for SDK-based sequences.

SequenceBase provides:
- CLI entry point (run_from_cli)
- Standardized output protocol (JSON Lines)
- Hardware and parameter management
- Execution lifecycle (setup -> run -> teardown)

Usage:
    from station_service.sdk import SequenceBase

    class MySequence(SequenceBase):
        name = "my_sequence"
        version = "1.0.0"
        description = "My test sequence"

        async def setup(self) -> None:
            # Initialize hardware
            self.emit_log("info", "Connecting to hardware...")
            self.mcu = MyDriver(self.hardware_config.get("mcu", {}))
            await self.mcu.connect()

        async def run(self) -> dict:
            # Execute test steps
            self.emit_step_start("measure_voltage", 1, 2)
            voltage = await self.mcu.read_voltage()
            self.emit_measurement("voltage", voltage, "V", passed=voltage > 3.0)
            self.emit_step_complete("measure_voltage", 1, True, 1.5)

            return {
                "passed": True,
                "measurements": {"voltage": voltage}
            }

        async def teardown(self) -> None:
            # Cleanup
            if hasattr(self, "mcu"):
                await self.mcu.disconnect()

    if __name__ == "__main__":
        exit(MySequence.run_from_cli())
"""

import asyncio
import logging
import sys
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union

from .cli import CLIArgs, parse_args, print_error
from .context import ExecutionContext, Measurement
from .protocol import OutputProtocol
from .exceptions import SequenceError, SetupError, TeardownError, AbortError
from .interfaces import OutputStrategy, LifecycleHook, CompositeHook
from .types import RunResult, ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of a single step execution."""

    name: str
    index: int
    passed: bool
    duration: float
    measurements: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "index": self.index,
            "passed": self.passed,
            "duration": self.duration,
            "measurements": self.measurements,
            "data": self.data,
            "error": self.error,
        }


class SequenceBase(ABC):
    """
    Abstract base class for all SDK-based sequences.

    Subclasses must implement:
    - setup(): Initialize hardware and resources
    - run(): Execute the sequence logic, return result dict
    - teardown(): Cleanup resources

    Class attributes to override:
    - name: Sequence name (required)
    - version: Sequence version (required)
    - description: Human-readable description
    """

    # Class-level metadata (override in subclass)
    name: str = "unnamed_sequence"
    version: str = "0.0.0"
    description: str = ""

    def __init__(
        self,
        context: ExecutionContext,
        hardware_config: Optional[Dict[str, Dict[str, Any]]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        output_strategy: Optional[OutputStrategy] = None,
        hooks: Optional[List[LifecycleHook]] = None,
    ):
        """
        Initialize sequence.

        Args:
            context: Execution context
            hardware_config: Hardware configuration dict
            parameters: Sequence parameters dict
            output_strategy: Custom output strategy (default: OutputProtocol)
            hooks: List of lifecycle hooks for custom behavior
        """
        self.context = context
        self.hardware_config = hardware_config or context.hardware_config
        self.parameters = parameters or context.parameters

        # Internal state
        self._output: OutputStrategy = output_strategy or OutputProtocol(context)
        self._hooks = CompositeHook(hooks) if hooks else CompositeHook()
        self._step_results: List[StepResult] = []
        self._measurements: Dict[str, Measurement] = {}
        self._current_step: Optional[str] = None
        self._current_step_index: int = 0
        self._total_steps: int = 0
        self._aborted: bool = False

    # =========================================================================
    # CLI Entry Point
    # =========================================================================

    @classmethod
    def run_from_cli(cls) -> int:
        """
        Main entry point for CLI execution.

        Parses arguments, creates context, and runs the sequence.

        Returns:
            Exit code: 0=PASS, 1=FAIL, 2=ERROR
        """
        try:
            args = parse_args(prog_name=cls.name)
        except (ValueError, FileNotFoundError) as e:
            print_error(str(e))
            return 2

        if args.action == "start":
            return cls._run_start(args)
        elif args.action == "stop":
            return cls._run_stop(args)
        elif args.action == "status":
            return cls._run_status(args)
        else:
            print_error(f"Unknown action: {args.action}")
            return 2

    @classmethod
    def _run_start(cls, args: CLIArgs) -> int:
        """Handle --start action."""
        # Create context
        context = ExecutionContext.from_config(args.config)
        context.sequence_name = cls.name
        context.sequence_version = cls.version

        # Create instance
        instance = cls(
            context=context,
            hardware_config=args.hardware_config,
            parameters=args.parameters,
        )

        # Dry run - just validate
        if args.dry_run:
            instance._output.log("info", "Dry run - config validated")
            return 0

        # Run with asyncio
        try:
            result = asyncio.run(instance._execute())
            return 0 if result.get("passed", False) else 1
        except KeyboardInterrupt:
            instance._output.error("INTERRUPTED", "Execution interrupted by user")
            return 2
        except Exception as e:
            instance._output.error("FATAL", str(e))
            return 2

    @classmethod
    def _run_stop(cls, args: CLIArgs) -> int:
        """Handle --stop action."""
        # For now, just output stop request
        # In practice, this would signal the running process
        import json
        print(json.dumps({
            "type": "command",
            "action": "stop",
            "execution_id": args.execution_id,
        }))
        return 0

    @classmethod
    def _run_status(cls, args: CLIArgs) -> int:
        """Handle --status action."""
        import json
        print(json.dumps({
            "type": "status_request",
            "sequence_name": cls.name,
            "execution_id": args.execution_id,
        }))
        return 0

    # =========================================================================
    # Execution Lifecycle
    # =========================================================================

    async def _execute(self) -> Dict[str, Any]:
        """
        Execute the full sequence lifecycle.

        Calls setup() -> run() -> teardown() with proper error handling.
        Lifecycle hooks are called at each phase transition.

        Returns:
            Result dictionary with 'passed', 'measurements', 'steps', etc.
        """
        self.context.start()
        result: Dict[str, Any] = {
            "passed": False,
            "measurements": {},
            "steps": [],
            "error": None,
        }
        setup_error: Optional[Exception] = None
        run_error: Optional[Exception] = None
        teardown_error: Optional[Exception] = None

        try:
            # Setup phase
            self._output.status("setup", 0, message="Initializing...")
            await self._hooks.on_setup_start(self.context)
            try:
                await self.setup()
                await self._hooks.on_setup_complete(self.context)
            except Exception as e:
                setup_error = e
                await self._hooks.on_setup_complete(self.context, e)
                await self._hooks.on_error(self.context, e, "setup")
                raise

            # Run phase
            self._output.status("running", 0, message="Executing sequence...")
            await self._hooks.on_run_start(self.context)
            try:
                run_result = await self.run()
                # Merge run result
                if isinstance(run_result, dict):
                    result["passed"] = run_result.get("passed", False)
                    # Convert Measurement objects to dicts for serialization
                    measurements_dict = {}
                    for name, m in self._measurements.items():
                        if isinstance(m, Measurement):
                            measurements_dict[name] = m.to_storage_dict()
                        else:
                            measurements_dict[name] = m
                    result["measurements"] = {
                        **measurements_dict,
                        **run_result.get("measurements", {}),
                    }
                    result["data"] = run_result.get("data", {})
                await self._hooks.on_run_complete(self.context, result)
            except Exception as e:
                run_error = e
                await self._hooks.on_run_complete(self.context, result, e)
                await self._hooks.on_error(self.context, e, "run")
                raise

        except SetupError as e:
            result["error"] = f"Setup failed: {e.message}"
            self._output.error(e.code, e.message)

        except AbortError as e:
            result["error"] = f"Aborted: {e.message}"
            self._output.error(e.code, e.message)

        except SequenceError as e:
            result["error"] = f"Sequence error: {e.message}"
            self._output.error(e.code, e.message)

        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            self._output.error("UNEXPECTED_ERROR", str(e))
            if self.context.parameters.get("debug"):
                traceback.print_exc()

        finally:
            # Teardown phase (always runs)
            try:
                self._output.status("teardown", 95, message="Cleaning up...")
                await self._hooks.on_teardown_start(self.context)
                await self.teardown()
                await self._hooks.on_teardown_complete(self.context)
            except Exception as e:
                teardown_error = e
                await self._hooks.on_teardown_complete(self.context, e)
                await self._hooks.on_error(self.context, e, "teardown")
                self._output.error("TEARDOWN_ERROR", str(e))
                if result["error"] is None:
                    result["error"] = f"Teardown failed: {str(e)}"

            # Complete
            self.context.complete()
            result["steps"] = [sr.to_dict() for sr in self._step_results]
            result["duration"] = self.context.duration_seconds

            # Call sequence complete hook
            await self._hooks.on_sequence_complete(self.context, result)

            self._output.sequence_complete(
                overall_pass=result["passed"],
                duration=result.get("duration", 0),
                steps=result["steps"],
                measurements=result["measurements"],
                error=result["error"],
            )

        return result

    # =========================================================================
    # Abstract Methods (must implement in subclass)
    # =========================================================================

    @abstractmethod
    async def setup(self) -> None:
        """
        Initialize hardware and resources before sequence execution.

        Called before run(). Should connect to hardware, load configs, etc.

        Raises:
            SetupError: If setup fails
        """
        pass

    @abstractmethod
    async def run(self) -> RunResult:
        """
        Execute the main sequence logic.

        Should execute all test steps and collect measurements.

        Returns:
            RunResult TypedDict with:
            - passed: bool (required)
            - measurements: dict (optional)
            - data: dict (optional)

        Example:
            async def run(self) -> RunResult:
                return {
                    "passed": True,
                    "measurements": {"voltage": 3.3},
                    "data": {"serial": "ABC123"},
                }

        Raises:
            SequenceError: If execution fails
        """
        pass

    @abstractmethod
    async def teardown(self) -> None:
        """
        Cleanup resources after sequence execution.

        Called after run() completes (or fails). Should disconnect hardware,
        release resources, etc. Always called even if setup/run failed.

        Raises:
            TeardownError: If teardown fails
        """
        pass

    # =========================================================================
    # Output Helper Methods
    # =========================================================================

    def emit_log(self, level: str, message: str, **extra: Any) -> None:
        """
        Emit log message.

        Args:
            level: Log level (debug, info, warning, error)
            message: Log message
            **extra: Additional key-value pairs
        """
        self._output.log(level, message, **extra)

    def emit_step_start(
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
        self._current_step = step_name
        self._current_step_index = index
        self._total_steps = total

        progress = ((index - 1) / total) * 100 if total > 0 else 0
        self._output.status("running", progress, step_name, f"Step {index}/{total}")
        self._output.step_start(step_name, index, total, description)

        # Call hook with error logging (fire and forget pattern with error handling)
        asyncio.create_task(
            self._safe_call_hook(
                self._hooks.on_step_start(self.context, step_name, index, total),
                "on_step_start",
            )
        )

    def emit_step_complete(
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
        Emit step complete event and record result.

        Args:
            step_name: Name of the step
            index: Step index (1-based)
            passed: Whether step passed
            duration: Step duration in seconds
            measurements: Measurement data from step
            error: Error message if failed
            data: Additional result data
        """
        result = StepResult(
            name=step_name,
            index=index,
            passed=passed,
            duration=duration,
            measurements=measurements or {},
            data=data or {},
            error=error,
        )
        self._step_results.append(result)

        # Merge measurements
        if measurements:
            self._measurements.update(measurements)

        self._output.step_complete(
            step_name=step_name,
            index=index,
            passed=passed,
            duration=duration,
            measurements=measurements,
            error=error,
            data=data,
        )

        # Call hook with error logging
        asyncio.create_task(
            self._safe_call_hook(
                self._hooks.on_step_complete(
                    self.context, step_name, index, passed, duration, error
                ),
                "on_step_complete",
            )
        )

    def emit_measurement(
        self,
        name: str,
        value: Any,
        unit: str = "",
        passed: Optional[bool] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> None:
        """
        Emit and record measurement.

        Args:
            name: Measurement name
            value: Measured value
            unit: Unit of measurement
            passed: Whether measurement passed limits (auto-calculated if None)
            min_value: Minimum acceptable value
            max_value: Maximum acceptable value
        """
        # Create standardized Measurement object
        measurement = Measurement(
            name=name,
            value=value,
            unit=unit,
            passed=passed,
            min_value=min_value,
            max_value=max_value,
            step_name=self._current_step,
        )

        # Record measurement
        self._measurements[name] = measurement

        # Emit to output
        self._output.measurement(
            name=name,
            value=value,
            unit=unit,
            passed=measurement.passed,  # Use auto-calculated value
            min_value=min_value,
            max_value=max_value,
            step_name=self._current_step,
        )

        # Call hook with error logging
        asyncio.create_task(
            self._safe_call_hook(
                self._hooks.on_measurement(self.context, measurement),
                "on_measurement",
            )
        )

    def emit_error(
        self,
        code: str,
        message: str,
        recoverable: bool = False,
    ) -> None:
        """
        Emit error event.

        Args:
            code: Error code
            message: Error message
            recoverable: Whether error is recoverable
        """
        self._output.error(
            code=code,
            message=message,
            step=self._current_step,
            recoverable=recoverable,
        )

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _safe_call_hook(self, coro, hook_name: str) -> None:
        """
        Safely call an async hook with error logging.

        Hooks should not interrupt sequence execution, so errors are logged
        but not re-raised.

        Args:
            coro: The coroutine to await
            hook_name: Name of the hook for error messages
        """
        try:
            await coro
        except Exception as e:
            logger.warning(
                f"Hook '{hook_name}' raised exception: {e}",
                exc_info=True,
            )
            # Emit error but don't fail the sequence
            self._output.log(
                "warning",
                f"Hook error in {hook_name}: {str(e)}",
                hook=hook_name,
            )

    # =========================================================================
    # User Input (Manual Control)
    # =========================================================================

    async def request_confirmation(
        self,
        prompt: str,
        timeout: float = 300,
    ) -> bool:
        """
        Request user confirmation.

        Args:
            prompt: Prompt message
            timeout: Timeout in seconds

        Returns:
            True if confirmed, False otherwise
        """
        request_id = f"confirm_{id(prompt)}"
        self._output.input_request(
            request_id=request_id,
            prompt=prompt,
            input_type="confirm",
            timeout=timeout,
        )
        result = self._output.wait_for_input(request_id, timeout)
        return bool(result)

    async def request_input(
        self,
        prompt: str,
        input_type: str = "text",
        options: Optional[List[str]] = None,
        default: Any = None,
        timeout: float = 300,
    ) -> Any:
        """
        Request user input.

        Args:
            prompt: Prompt message
            input_type: Type of input (text, number, select)
            options: Options for select type
            default: Default value
            timeout: Timeout in seconds

        Returns:
            User input value
        """
        request_id = f"input_{id(prompt)}"
        self._output.input_request(
            request_id=request_id,
            prompt=prompt,
            input_type=input_type,
            options=options,
            default=default,
            timeout=timeout,
        )
        return self._output.wait_for_input(request_id, timeout)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def abort(self, reason: str = "User requested abort") -> None:
        """
        Abort sequence execution.

        Args:
            reason: Reason for abort
        """
        self._aborted = True
        raise AbortError(reason)

    def check_abort(self) -> None:
        """
        Check if abort was requested and raise if so.

        Call this periodically in long-running steps.
        """
        if self._aborted:
            raise AbortError("Abort requested")

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """
        Get parameter value.

        Args:
            name: Parameter name
            default: Default value if not found

        Returns:
            Parameter value
        """
        return self.parameters.get(name, default)

    def get_hardware_config(self, name: str) -> Dict[str, Any]:
        """
        Get hardware configuration.

        Args:
            name: Hardware name

        Returns:
            Hardware configuration dict
        """
        return self.hardware_config.get(name, {})

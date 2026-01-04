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
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .sequence_cli import CLIArgs, parse_args, print_error
from .context import ExecutionContext, Measurement
from .protocol import OutputProtocol
from .exceptions import SequenceError, SetupError, AbortError
from .interfaces import OutputStrategy, LifecycleHook, CompositeHook
from .sdk_types import RunResult

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

        # Task tracking for async hook calls (prevents fire-and-forget race conditions)
        self._pending_hook_tasks: set = set()

        # Lifecycle step tracking (setup/teardown as automatic steps)
        self._setup_start_time: float = 0.0
        self._setup_passed: bool = False
        self._setup_duration: float = 0.0
        self._setup_error: Optional[str] = None
        self._setup_step_emitted: bool = False
        self._run_total_steps: int = 0  # Captured from run()'s first step

        # Run phase error tracking
        self._run_error: Optional[str] = None
        self._run_exception: Optional[Exception] = None

        # Teardown phase error tracking
        self._teardown_error: Optional[str] = None
        self._teardown_exception: Optional[Exception] = None

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

        Setup and teardown are automatically emitted as steps:
        - setup: step index 0
        - run() steps: indices 1 to N (offset by +1)
        - teardown: step index N+1

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

        try:
            # Setup phase - track timing for step emission
            self._setup_start_time = time.time()
            self._output.status("setup", 0, message="Initializing...")
            await self._hooks.on_setup_start(self.context)
            try:
                await self.setup()
                self._setup_passed = True
                self._setup_duration = time.time() - self._setup_start_time
                await self._hooks.on_setup_complete(self.context)
            except Exception as e:
                self._setup_passed = False
                self._setup_duration = time.time() - self._setup_start_time
                self._setup_error = str(e) if not isinstance(e, SetupError) else e.message
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
                # Track run error in instance variables for hook access
                self._run_exception = e
                self._run_error = str(e) if not isinstance(e, SequenceError) else e.message
                await self._hooks.on_run_complete(self.context, result, e)
                await self._hooks.on_error(self.context, e, "run")
                raise

        except SetupError as e:
            result["error"] = f"Setup failed: {e.message}"
            self._output.error(e.code, e.message)
            # Emit setup step as failed (total=2 for setup+teardown only)
            self._emit_setup_step_failed(total=2)

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
            teardown_start = time.time()
            teardown_passed = True
            try:
                self._output.status("teardown", 95, message="Cleaning up...")
                await self._hooks.on_teardown_start(self.context)
                await self.teardown()
                await self._hooks.on_teardown_complete(self.context)
            except Exception as e:
                teardown_passed = False
                # Track teardown error in instance variables for hook access
                self._teardown_exception = e
                self._teardown_error = str(e)
                await self._hooks.on_teardown_complete(self.context, e)
                await self._hooks.on_error(self.context, e, "teardown")
                self._output.error("TEARDOWN_ERROR", str(e))
                if result["error"] is None:
                    result["error"] = f"Teardown failed: {str(e)}"

            teardown_duration = time.time() - teardown_start

            # Emit teardown step
            self._emit_teardown_step(teardown_passed, teardown_duration, self._teardown_error)

            # Complete
            self.context.complete()
            result["steps"] = [sr.to_dict() for sr in self._step_results]
            result["duration"] = self.context.duration_seconds

            # Wait for any pending hook tasks before final completion
            await self._await_pending_hooks()

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

    def _emit_setup_step_failed(self, total: int) -> None:
        """Emit setup step as failed when setup fails before run() starts."""
        if self._setup_step_emitted:
            return
        self._setup_step_emitted = True

        # Record setup step result
        setup_result = StepResult(
            name="setup",
            index=0,
            passed=False,
            duration=self._setup_duration,
            error=self._setup_error,
        )
        # Insert at beginning of step results
        self._step_results.insert(0, setup_result)

        # Emit step events
        self._output.step_start("setup", 0, total, "Hardware initialization")
        self._output.step_complete(
            step_name="setup",
            index=0,
            passed=False,
            duration=self._setup_duration,
            error=self._setup_error,
        )

    def _emit_teardown_step(self, passed: bool, duration: float, error: Optional[str]) -> None:
        """Emit teardown as the final step."""
        # Calculate teardown index (after all run steps + setup)
        # If setup step was emitted, run steps are offset by 1
        teardown_index = self._run_total_steps + 1 if self._run_total_steps > 0 else 1
        total = teardown_index + 1  # +1 because teardown is part of total

        # Record teardown step result
        teardown_result = StepResult(
            name="teardown",
            index=teardown_index,
            passed=passed,
            duration=duration,
            error=error,
        )
        self._step_results.append(teardown_result)

        # Emit step events
        self._output.step_start("teardown", teardown_index, total, "Resource cleanup")
        self._output.step_complete(
            step_name="teardown",
            index=teardown_index,
            passed=passed,
            duration=duration,
            error=error,
        )

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
    # Error State Accessors (for hooks and external access)
    # =========================================================================

    @property
    def setup_error(self) -> Optional[str]:
        """Get setup phase error message, if any."""
        return self._setup_error

    @property
    def setup_exception(self) -> Optional[Exception]:
        """Get setup phase exception object, if any."""
        # Note: Setup exception is re-raised, so we reconstruct from error message
        return SetupError(self._setup_error) if self._setup_error else None

    @property
    def run_error(self) -> Optional[str]:
        """Get run phase error message, if any."""
        return self._run_error

    @property
    def run_exception(self) -> Optional[Exception]:
        """Get run phase exception object, if any."""
        return self._run_exception

    @property
    def teardown_error(self) -> Optional[str]:
        """Get teardown phase error message, if any."""
        return self._teardown_error

    @property
    def teardown_exception(self) -> Optional[Exception]:
        """Get teardown phase exception object, if any."""
        return self._teardown_exception

    @property
    def last_error(self) -> Optional[str]:
        """Get the most recent error from any phase."""
        return self._teardown_error or self._run_error or self._setup_error

    @property
    def last_exception(self) -> Optional[Exception]:
        """Get the most recent exception from any phase."""
        return self._teardown_exception or self._run_exception or self.setup_exception

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
            index: Current step index (1-based from run())
            total: Total number of steps (from run(), will be adjusted +2 for setup/teardown)
            description: Optional step description

        Note:
            The index and total are automatically adjusted to include
            setup (index 0) and teardown (last index) as lifecycle steps.
        """
        # Capture run()'s total steps on first call
        if self._run_total_steps == 0:
            self._run_total_steps = total

        # Emit setup step first (if not emitted yet)
        if not self._setup_step_emitted:
            self._setup_step_emitted = True
            adjusted_total = total + 2  # +1 for setup, +1 for teardown

            # Record setup step result
            setup_result = StepResult(
                name="setup",
                index=0,
                passed=self._setup_passed,
                duration=self._setup_duration,
                error=self._setup_error,
            )
            self._step_results.insert(0, setup_result)

            # Emit setup step events
            self._output.step_start("setup", 0, adjusted_total, "Hardware initialization")
            self._output.step_complete(
                step_name="setup",
                index=0,
                passed=self._setup_passed,
                duration=self._setup_duration,
                error=self._setup_error,
            )

        # Adjust total to include setup/teardown
        adjusted_total = total + 2

        self._current_step = step_name
        self._current_step_index = index
        self._total_steps = adjusted_total

        # Progress calculation: setup(0) is done, current is index out of adjusted_total
        progress = (index / adjusted_total) * 100 if adjusted_total > 0 else 0
        self._output.status("running", progress, step_name, f"Step {index}/{adjusted_total}")
        self._output.step_start(step_name, index, adjusted_total, description)

        # Call hook with tracked task scheduling (prevents race conditions)
        self._schedule_hook_task(
            self._hooks.on_step_start(self.context, step_name, index, adjusted_total),
            "on_step_start",
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

        # Call hook with tracked task scheduling (prevents race conditions)
        self._schedule_hook_task(
            self._hooks.on_step_complete(
                self.context, step_name, index, passed, duration, error
            ),
            "on_step_complete",
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

        # Call hook with tracked task scheduling (prevents race conditions)
        self._schedule_hook_task(
            self._hooks.on_measurement(self.context, measurement),
            "on_measurement",
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

    def _schedule_hook_task(self, coro, hook_name: str) -> asyncio.Task:
        """
        Schedule an async hook call with proper task tracking.

        Tasks are tracked in _pending_hook_tasks to ensure they complete
        before sequence ends. This prevents fire-and-forget race conditions.

        Args:
            coro: The coroutine to schedule
            hook_name: Name of the hook for error messages

        Returns:
            The created asyncio.Task
        """
        task = asyncio.create_task(self._safe_call_hook(coro, hook_name))

        # Track the task
        self._pending_hook_tasks.add(task)

        # Remove from tracking when done
        task.add_done_callback(self._pending_hook_tasks.discard)

        return task

    async def _await_pending_hooks(self, timeout: float = 5.0) -> None:
        """
        Wait for all pending hook tasks to complete.

        Called before sequence completion to ensure all hooks finish.
        Uses a timeout to prevent hanging on slow hooks.

        Args:
            timeout: Maximum time to wait for hooks in seconds
        """
        if not self._pending_hook_tasks:
            return

        pending = list(self._pending_hook_tasks)
        if pending:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout waiting for {len(pending)} pending hook tasks"
                )
                # Cancel remaining tasks
                for task in pending:
                    if not task.done():
                        task.cancel()

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

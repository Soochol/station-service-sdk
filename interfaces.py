"""
SDK Interfaces for extensibility.

Provides Protocol classes for dependency injection and custom implementations:
- OutputStrategy: Custom output formatters
- LifecycleHook: Lifecycle event handlers
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import ExecutionContext, Measurement


# =============================================================================
# Output Strategy Interface
# =============================================================================


@runtime_checkable
class OutputStrategy(Protocol):
    """
    Interface for output strategies.

    Implement this protocol to create custom output formatters.
    The default implementation is OutputProtocol (JSON Lines to stdout).

    Example:
        class FileOutputStrategy:
            def __init__(self, file_path: str):
                self.file = open(file_path, 'w')

            def emit(self, msg_type: str, data: Dict[str, Any]) -> None:
                self.file.write(f"{msg_type}: {data}\\n")
                self.file.flush()

        # Usage
        strategy = FileOutputStrategy("/tmp/output.log")
        sequence = MySequence(context, output_strategy=strategy)
    """

    def log(self, level: str, message: str, **extra: Any) -> None:
        """Emit log message."""
        ...

    def step_start(
        self,
        step_name: str,
        index: int,
        total: int,
        description: str = "",
    ) -> None:
        """Emit step start event."""
        ...

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
        """Emit step complete event."""
        ...

    def sequence_complete(
        self,
        overall_pass: bool,
        duration: float,
        steps: List[Dict[str, Any]],
        measurements: Dict[str, Any],
        error: Optional[str] = None,
    ) -> None:
        """Emit sequence complete event."""
        ...

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
        """Emit measurement data point."""
        ...

    def error(
        self,
        code: str,
        message: str,
        step: Optional[str] = None,
        recoverable: bool = False,
    ) -> None:
        """Emit error event."""
        ...

    def status(
        self,
        status: str,
        progress: float,
        current_step: Optional[str] = None,
        message: str = "",
    ) -> None:
        """Emit status update."""
        ...

    def input_request(
        self,
        request_id: str,
        prompt: str,
        input_type: str = "confirm",
        options: Optional[List[str]] = None,
        default: Any = None,
        timeout: Optional[float] = None,
    ) -> None:
        """Request user input."""
        ...


# =============================================================================
# Lifecycle Hook Interface
# =============================================================================


class LifecycleHook(ABC):
    """
    Abstract base class for lifecycle hooks.

    Implement this class to inject custom behavior at lifecycle events.
    Hooks are called in registration order.

    Example:
        class MetricsHook(LifecycleHook):
            def __init__(self, metrics_client):
                self.client = metrics_client

            async def on_setup_start(self, context):
                self.client.increment("sequence.setup.started")

            async def on_sequence_complete(self, context, result):
                self.client.timing("sequence.duration", result.get("duration", 0))
                if result.get("passed"):
                    self.client.increment("sequence.passed")
                else:
                    self.client.increment("sequence.failed")

        # Usage
        hook = MetricsHook(statsd_client)
        sequence = MySequence(context, hooks=[hook])
    """

    async def on_setup_start(self, context: "ExecutionContext") -> None:
        """Called before setup() begins."""
        pass

    async def on_setup_complete(
        self, context: "ExecutionContext", error: Optional[Exception] = None
    ) -> None:
        """Called after setup() completes (or fails)."""
        pass

    async def on_run_start(self, context: "ExecutionContext") -> None:
        """Called before run() begins."""
        pass

    async def on_step_start(
        self, context: "ExecutionContext", step_name: str, index: int, total: int
    ) -> None:
        """Called when a step starts."""
        pass

    async def on_step_complete(
        self,
        context: "ExecutionContext",
        step_name: str,
        index: int,
        passed: bool,
        duration: float,
        error: Optional[str] = None,
    ) -> None:
        """Called when a step completes."""
        pass

    async def on_measurement(
        self,
        context: "ExecutionContext",
        measurement: "Measurement",
    ) -> None:
        """Called when a measurement is recorded."""
        pass

    async def on_run_complete(
        self,
        context: "ExecutionContext",
        result: Dict[str, Any],
        error: Optional[Exception] = None,
    ) -> None:
        """Called after run() completes (or fails)."""
        pass

    async def on_teardown_start(self, context: "ExecutionContext") -> None:
        """Called before teardown() begins."""
        pass

    async def on_teardown_complete(
        self, context: "ExecutionContext", error: Optional[Exception] = None
    ) -> None:
        """Called after teardown() completes (or fails)."""
        pass

    async def on_sequence_complete(
        self, context: "ExecutionContext", result: Dict[str, Any]
    ) -> None:
        """Called when the entire sequence completes."""
        pass

    async def on_error(
        self,
        context: "ExecutionContext",
        error: Exception,
        phase: str,
    ) -> None:
        """
        Called when an error occurs.

        Args:
            context: Execution context
            error: The exception that occurred
            phase: Phase where error occurred (setup, run, teardown)
        """
        pass


# =============================================================================
# Composite Hook (for managing multiple hooks)
# =============================================================================


class CompositeHook(LifecycleHook):
    """
    Composite hook that delegates to multiple hooks.

    Used internally by SequenceBase to manage hook lists.
    """

    def __init__(self, hooks: Optional[List[LifecycleHook]] = None):
        self.hooks = hooks or []

    def add_hook(self, hook: LifecycleHook) -> None:
        """Add a hook to the list."""
        self.hooks.append(hook)

    def remove_hook(self, hook: LifecycleHook) -> None:
        """Remove a hook from the list."""
        self.hooks.remove(hook)

    async def _call_hooks(self, method: str, *args, **kwargs) -> None:
        """Call a method on all hooks."""
        for hook in self.hooks:
            try:
                method_func = getattr(hook, method, None)
                if method_func:
                    await method_func(*args, **kwargs)
            except Exception:
                # Log but don't fail sequence for hook errors
                pass

    async def on_setup_start(self, context: "ExecutionContext") -> None:
        await self._call_hooks("on_setup_start", context)

    async def on_setup_complete(
        self, context: "ExecutionContext", error: Optional[Exception] = None
    ) -> None:
        await self._call_hooks("on_setup_complete", context, error)

    async def on_run_start(self, context: "ExecutionContext") -> None:
        await self._call_hooks("on_run_start", context)

    async def on_step_start(
        self, context: "ExecutionContext", step_name: str, index: int, total: int
    ) -> None:
        await self._call_hooks("on_step_start", context, step_name, index, total)

    async def on_step_complete(
        self,
        context: "ExecutionContext",
        step_name: str,
        index: int,
        passed: bool,
        duration: float,
        error: Optional[str] = None,
    ) -> None:
        await self._call_hooks(
            "on_step_complete", context, step_name, index, passed, duration, error
        )

    async def on_measurement(
        self,
        context: "ExecutionContext",
        measurement: "Measurement",
    ) -> None:
        await self._call_hooks("on_measurement", context, measurement)

    async def on_run_complete(
        self,
        context: "ExecutionContext",
        result: Dict[str, Any],
        error: Optional[Exception] = None,
    ) -> None:
        await self._call_hooks("on_run_complete", context, result, error)

    async def on_teardown_start(self, context: "ExecutionContext") -> None:
        await self._call_hooks("on_teardown_start", context)

    async def on_teardown_complete(
        self, context: "ExecutionContext", error: Optional[Exception] = None
    ) -> None:
        await self._call_hooks("on_teardown_complete", context, error)

    async def on_sequence_complete(
        self, context: "ExecutionContext", result: Dict[str, Any]
    ) -> None:
        await self._call_hooks("on_sequence_complete", context, result)

    async def on_error(
        self,
        context: "ExecutionContext",
        error: Exception,
        phase: str,
    ) -> None:
        await self._call_hooks("on_error", context, error, phase)

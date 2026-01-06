"""OpenTelemetry tracing integration for Station Service SDK.

Provides distributed tracing capabilities using OpenTelemetry.
Requires optional dependency: pip install station-service-sdk[tracing]
"""

from __future__ import annotations

from typing import Any

from station_service_sdk.context import ExecutionContext

# Check for OpenTelemetry availability
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode, Span, Tracer
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None  # type: ignore
    Status = None  # type: ignore
    StatusCode = None  # type: ignore
    Span = None  # type: ignore
    Tracer = None  # type: ignore
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    Resource = None  # type: ignore


def _require_otel() -> None:
    """Raise ImportError if OpenTelemetry is not available."""
    if not OTEL_AVAILABLE:
        raise ImportError(
            "OpenTelemetry is not installed. "
            "Install with: pip install station-service-sdk[tracing]"
        )


def configure_tracing(
    service_name: str = "station-sdk",
    service_version: str = "2.0.0",
    exporter: Any = None,
) -> Tracer:
    """Configure OpenTelemetry tracing.

    Args:
        service_name: Name of the service for tracing
        service_version: Version of the service
        exporter: Optional span exporter (e.g., JaegerExporter, OTLPSpanExporter)

    Returns:
        Configured tracer instance

    Raises:
        ImportError: If OpenTelemetry is not installed
    """
    _require_otel()

    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
    })

    provider = TracerProvider(resource=resource)

    if exporter:
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)


class TracingHook:
    """Lifecycle hook for OpenTelemetry tracing.

    Automatically creates spans for sequence execution, steps,
    and measurements.

    Example:
        >>> tracer = configure_tracing("my-service")
        >>> hook = TracingHook(tracer=tracer)
        >>> sequence = MySequence(context=context, hooks=[hook])
    """

    def __init__(
        self,
        tracer: Tracer | None = None,
        service_name: str = "station-sdk",
    ):
        """Initialize tracing hook.

        Args:
            tracer: Optional tracer instance (creates one if not provided)
            service_name: Service name for tracer

        Raises:
            ImportError: If OpenTelemetry is not installed
        """
        _require_otel()

        if tracer is None:
            tracer = trace.get_tracer(service_name)

        self.tracer = tracer
        self._spans: dict[str, Span] = {}
        self._root_span: Span | None = None

    async def on_setup_start(self, context: ExecutionContext) -> None:
        """Start root span for sequence execution.

        Args:
            context: Execution context
        """
        self._root_span = self.tracer.start_span(
            f"sequence.{context.sequence_name}",
            attributes={
                "execution.id": context.execution_id,
                "execution.wip_id": context.wip_id or "",
                "execution.batch_id": context.batch_id or "",
                "execution.lot_id": context.lot_id or "",
                "execution.serial_number": context.serial_number or "",
                "execution.operator_id": context.operator_id or "",
                "execution.station_id": context.station_id or "",
            },
        )
        self._spans["root"] = self._root_span

        # Start setup span
        setup_span = self.tracer.start_span(
            "sequence.setup",
            context=trace.set_span_in_context(self._root_span),
        )
        self._spans["setup"] = setup_span

    async def on_setup_complete(
        self,
        context: ExecutionContext,
        duration: float,
        error: Exception | None = None,
    ) -> None:
        """Complete setup span.

        Args:
            context: Execution context
            duration: Setup duration in seconds
            error: Optional error that occurred
        """
        setup_span = self._spans.pop("setup", None)
        if setup_span:
            setup_span.set_attribute("duration_ms", duration * 1000)
            if error:
                setup_span.set_status(Status(StatusCode.ERROR, str(error)))
                setup_span.record_exception(error)
            setup_span.end()

    async def on_run_start(self, context: ExecutionContext) -> None:
        """Start run phase span.

        Args:
            context: Execution context
        """
        if self._root_span:
            run_span = self.tracer.start_span(
                "sequence.run",
                context=trace.set_span_in_context(self._root_span),
            )
            self._spans["run"] = run_span

    async def on_run_complete(
        self,
        context: ExecutionContext,
        result: dict[str, Any],
    ) -> None:
        """Complete run phase span.

        Args:
            context: Execution context
            result: Run result
        """
        run_span = self._spans.pop("run", None)
        if run_span:
            run_span.set_attribute("passed", result.get("passed", False))
            if not result.get("passed"):
                run_span.set_status(
                    Status(StatusCode.ERROR, result.get("error", "Unknown error"))
                )
            run_span.end()

    async def on_step_start(
        self,
        context: ExecutionContext,
        step_name: str,
        index: int,
        total: int,
    ) -> None:
        """Start step span.

        Args:
            context: Execution context
            step_name: Step name
            index: Step index
            total: Total steps
        """
        parent_span = self._spans.get("run") or self._root_span
        if parent_span:
            step_span = self.tracer.start_span(
                f"step.{step_name}",
                context=trace.set_span_in_context(parent_span),
                attributes={
                    "step.name": step_name,
                    "step.index": index,
                    "step.total": total,
                },
            )
            self._spans[f"step_{index}"] = step_span

    async def on_step_complete(
        self,
        context: ExecutionContext,
        step_name: str,
        index: int,
        passed: bool,
        duration: float,
        error: str | None = None,
    ) -> None:
        """Complete step span.

        Args:
            context: Execution context
            step_name: Step name
            index: Step index
            passed: Whether step passed
            duration: Step duration in seconds
            error: Optional error message
        """
        step_span = self._spans.pop(f"step_{index}", None)
        if step_span:
            step_span.set_attribute("passed", passed)
            step_span.set_attribute("duration_ms", duration * 1000)

            if not passed:
                step_span.set_status(
                    Status(StatusCode.ERROR, error or "Step failed")
                )

            step_span.end()

    async def on_measurement(
        self,
        context: ExecutionContext,
        measurement: Any,
    ) -> None:
        """Record measurement as span event.

        Args:
            context: Execution context
            measurement: Measurement object
        """
        # Find current step span or run span
        current_span = None
        for key in reversed(list(self._spans.keys())):
            if key.startswith("step_"):
                current_span = self._spans[key]
                break

        if current_span is None:
            current_span = self._spans.get("run") or self._root_span

        if current_span:
            current_span.add_event(
                f"measurement.{measurement.name}",
                attributes={
                    "measurement.name": measurement.name,
                    "measurement.value": measurement.value,
                    "measurement.unit": measurement.unit,
                    "measurement.passed": measurement.passed if measurement.passed is not None else True,
                },
            )

    async def on_error(
        self,
        context: ExecutionContext,
        code: str,
        message: str,
        recoverable: bool,
    ) -> None:
        """Record error as span event.

        Args:
            context: Execution context
            code: Error code
            message: Error message
            recoverable: Whether error is recoverable
        """
        # Find current span
        current_span = self._root_span
        for key in reversed(list(self._spans.keys())):
            current_span = self._spans[key]
            break

        if current_span:
            current_span.add_event(
                "error",
                attributes={
                    "error.code": code,
                    "error.message": message,
                    "error.recoverable": recoverable,
                },
            )

    async def on_teardown_start(self, context: ExecutionContext) -> None:
        """Start teardown span.

        Args:
            context: Execution context
        """
        if self._root_span:
            teardown_span = self.tracer.start_span(
                "sequence.teardown",
                context=trace.set_span_in_context(self._root_span),
            )
            self._spans["teardown"] = teardown_span

    async def on_teardown_complete(
        self,
        context: ExecutionContext,
        duration: float,
        error: Exception | None = None,
    ) -> None:
        """Complete teardown span.

        Args:
            context: Execution context
            duration: Teardown duration in seconds
            error: Optional error that occurred
        """
        teardown_span = self._spans.pop("teardown", None)
        if teardown_span:
            teardown_span.set_attribute("duration_ms", duration * 1000)
            if error:
                teardown_span.set_status(Status(StatusCode.ERROR, str(error)))
                teardown_span.record_exception(error)
            teardown_span.end()

    async def on_sequence_complete(
        self,
        context: ExecutionContext,
        result: dict[str, Any],
    ) -> None:
        """Complete root span.

        Args:
            context: Execution context
            result: Sequence result
        """
        if self._root_span:
            self._root_span.set_attribute("result.passed", result.get("passed", False))
            self._root_span.set_attribute(
                "result.duration_ms",
                result.get("duration", 0) * 1000,
            )

            if not result.get("passed"):
                self._root_span.set_status(
                    Status(StatusCode.ERROR, result.get("error", "Sequence failed"))
                )

            self._root_span.end()
            self._root_span = None

        # Clean up any remaining spans
        for span in self._spans.values():
            try:
                span.end()
            except Exception:
                pass
        self._spans.clear()

"""Metrics collection for Station Service SDK.

Provides metrics hooks for monitoring sequence execution
performance and health.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from station_service_sdk.context import ExecutionContext


class MetricsBackend(ABC):
    """Abstract backend for metrics collection.

    Implement this interface to integrate with different
    metrics systems (Prometheus, StatsD, CloudWatch, etc.)
    """

    @abstractmethod
    def counter(
        self,
        name: str,
        value: int = 1,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name
            value: Increment value
            tags: Optional metric tags
        """
        ...

    @abstractmethod
    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge metric.

        Args:
            name: Metric name
            value: Gauge value
            tags: Optional metric tags
        """
        ...

    @abstractmethod
    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record a histogram metric.

        Args:
            name: Metric name
            value: Observed value
            tags: Optional metric tags
        """
        ...

    @abstractmethod
    def timing(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record a timing metric.

        Args:
            name: Metric name
            value: Duration in seconds
            tags: Optional metric tags
        """
        ...


@dataclass
class MetricRecord:
    """Record of a single metric emission.

    Attributes:
        type: Metric type (counter, gauge, histogram, timing)
        name: Metric name
        value: Metric value
        tags: Metric tags
        timestamp: When metric was recorded
    """

    type: str
    name: str
    value: float
    tags: dict[str, str]
    timestamp: datetime = field(default_factory=datetime.now)


class InMemoryMetrics(MetricsBackend):
    """In-memory metrics backend for testing.

    Stores all metrics in memory for later inspection.
    """

    def __init__(self) -> None:
        """Initialize empty metrics store."""
        self.metrics: list[MetricRecord] = []

    def counter(
        self,
        name: str,
        value: int = 1,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record counter metric."""
        self.metrics.append(MetricRecord(
            type="counter",
            name=name,
            value=float(value),
            tags=tags or {},
        ))

    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record gauge metric."""
        self.metrics.append(MetricRecord(
            type="gauge",
            name=name,
            value=value,
            tags=tags or {},
        ))

    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record histogram metric."""
        self.metrics.append(MetricRecord(
            type="histogram",
            name=name,
            value=value,
            tags=tags or {},
        ))

    def timing(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record timing metric."""
        self.metrics.append(MetricRecord(
            type="timing",
            name=name,
            value=value,
            tags=tags or {},
        ))

    def get_metrics(
        self,
        name: str | None = None,
        metric_type: str | None = None,
    ) -> list[MetricRecord]:
        """Get recorded metrics.

        Args:
            name: Optional filter by name
            metric_type: Optional filter by type

        Returns:
            List of matching metrics
        """
        result = self.metrics

        if name:
            result = [m for m in result if m.name == name]

        if metric_type:
            result = [m for m in result if m.type == metric_type]

        return result

    def get_counter_total(self, name: str) -> float:
        """Get total value of a counter.

        Args:
            name: Counter name

        Returns:
            Sum of all counter increments
        """
        counters = self.get_metrics(name=name, metric_type="counter")
        return sum(c.value for c in counters)

    def get_latest_gauge(self, name: str) -> float | None:
        """Get latest gauge value.

        Args:
            name: Gauge name

        Returns:
            Latest value or None
        """
        gauges = self.get_metrics(name=name, metric_type="gauge")
        return gauges[-1].value if gauges else None

    def clear(self) -> None:
        """Clear all recorded metrics."""
        self.metrics.clear()


class LoggingMetrics(MetricsBackend):
    """Metrics backend that logs metrics.

    Useful for debugging or when a real metrics system
    is not available.
    """

    def __init__(self, logger: Any = None):
        """Initialize logging backend.

        Args:
            logger: Optional logger (uses print if None)
        """
        self.logger = logger

    def _log(self, metric_type: str, name: str, value: float, tags: dict[str, str] | None) -> None:
        """Log a metric.

        Args:
            metric_type: Type of metric
            name: Metric name
            value: Metric value
            tags: Metric tags
        """
        message = f"METRIC [{metric_type}] {name}={value}"
        if tags:
            tag_str = ",".join(f"{k}={v}" for k, v in tags.items())
            message += f" ({tag_str})"

        if self.logger:
            self.logger.info(message)
        else:
            print(message)

    def counter(
        self,
        name: str,
        value: int = 1,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Log counter metric."""
        self._log("counter", name, float(value), tags)

    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Log gauge metric."""
        self._log("gauge", name, value, tags)

    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Log histogram metric."""
        self._log("histogram", name, value, tags)

    def timing(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Log timing metric."""
        self._log("timing", name, value, tags)


# Optional Prometheus backend
try:
    from prometheus_client import Counter, Gauge, Histogram, Summary

    class PrometheusMetrics(MetricsBackend):
        """Prometheus metrics backend.

        Requires prometheus-client package.
        Install with: pip install station-service-sdk[metrics]
        """

        def __init__(self, prefix: str = "station_sdk"):
            """Initialize Prometheus metrics.

            Args:
                prefix: Metric name prefix
            """
            self.prefix = prefix
            self._counters: dict[str, Counter] = {}
            self._gauges: dict[str, Gauge] = {}
            self._histograms: dict[str, Histogram] = {}
            self._summaries: dict[str, Summary] = {}

        def _get_counter(self, name: str, labels: list[str]) -> Counter:
            """Get or create counter."""
            full_name = f"{self.prefix}_{name}"
            if full_name not in self._counters:
                self._counters[full_name] = Counter(
                    full_name,
                    f"Counter for {name}",
                    labels,
                )
            return self._counters[full_name]

        def _get_gauge(self, name: str, labels: list[str]) -> Gauge:
            """Get or create gauge."""
            full_name = f"{self.prefix}_{name}"
            if full_name not in self._gauges:
                self._gauges[full_name] = Gauge(
                    full_name,
                    f"Gauge for {name}",
                    labels,
                )
            return self._gauges[full_name]

        def _get_histogram(self, name: str, labels: list[str]) -> Histogram:
            """Get or create histogram."""
            full_name = f"{self.prefix}_{name}"
            if full_name not in self._histograms:
                self._histograms[full_name] = Histogram(
                    full_name,
                    f"Histogram for {name}",
                    labels,
                )
            return self._histograms[full_name]

        def counter(
            self,
            name: str,
            value: int = 1,
            tags: dict[str, str] | None = None,
        ) -> None:
            """Increment Prometheus counter."""
            tags = tags or {}
            counter = self._get_counter(name, list(tags.keys()))
            counter.labels(**tags).inc(value)

        def gauge(
            self,
            name: str,
            value: float,
            tags: dict[str, str] | None = None,
        ) -> None:
            """Set Prometheus gauge."""
            tags = tags or {}
            gauge = self._get_gauge(name, list(tags.keys()))
            gauge.labels(**tags).set(value)

        def histogram(
            self,
            name: str,
            value: float,
            tags: dict[str, str] | None = None,
        ) -> None:
            """Observe Prometheus histogram."""
            tags = tags or {}
            histogram = self._get_histogram(name, list(tags.keys()))
            histogram.labels(**tags).observe(value)

        def timing(
            self,
            name: str,
            value: float,
            tags: dict[str, str] | None = None,
        ) -> None:
            """Record timing as histogram."""
            self.histogram(f"{name}_seconds", value, tags)

    PROMETHEUS_AVAILABLE = True

except ImportError:
    PROMETHEUS_AVAILABLE = False


class MetricsHook:
    """Lifecycle hook for metrics collection.

    Automatically collects metrics for sequence execution,
    steps, and measurements.

    Example:
        >>> metrics = InMemoryMetrics()
        >>> hook = MetricsHook(backend=metrics)
        >>> sequence = MySequence(context=context, hooks=[hook])
    """

    def __init__(
        self,
        backend: MetricsBackend,
        include_measurements: bool = True,
    ):
        """Initialize metrics hook.

        Args:
            backend: Metrics backend to use
            include_measurements: Whether to record measurements as gauges
        """
        self.backend = backend
        self.include_measurements = include_measurements

    def _get_tags(self, context: ExecutionContext) -> dict[str, str]:
        """Get common tags from context.

        Args:
            context: Execution context

        Returns:
            Dictionary of tag key-value pairs
        """
        return {
            "sequence": context.sequence_name,
            "station": context.station_id or "unknown",
        }

    async def on_setup_start(self, context: ExecutionContext) -> None:
        """Record setup start."""
        tags = self._get_tags(context)
        self.backend.counter("sequence_setup_started", tags=tags)

    async def on_setup_complete(
        self,
        context: ExecutionContext,
        duration: float,
        error: Exception | None = None,
    ) -> None:
        """Record setup completion."""
        tags = self._get_tags(context)
        tags["status"] = "error" if error else "success"

        self.backend.counter("sequence_setup_completed", tags=tags)
        self.backend.timing("sequence_setup_duration", duration, tags=self._get_tags(context))

    async def on_step_start(
        self,
        context: ExecutionContext,
        step_name: str,
        index: int,
        total: int,
    ) -> None:
        """Record step start."""
        tags = self._get_tags(context)
        tags["step"] = step_name

        self.backend.counter("step_started", tags=tags)
        self.backend.gauge("step_progress", index / total, tags=self._get_tags(context))

    async def on_step_complete(
        self,
        context: ExecutionContext,
        step_name: str,
        index: int,
        passed: bool,
        duration: float,
        error: str | None = None,
    ) -> None:
        """Record step completion."""
        tags = self._get_tags(context)
        tags["step"] = step_name
        tags["status"] = "pass" if passed else "fail"

        self.backend.counter("step_completed", tags=tags)
        self.backend.timing("step_duration", duration, tags={
            **self._get_tags(context),
            "step": step_name,
        })

        if passed:
            self.backend.counter("step_passed", tags=tags)
        else:
            self.backend.counter("step_failed", tags=tags)

    async def on_measurement(
        self,
        context: ExecutionContext,
        measurement: Any,
    ) -> None:
        """Record measurement as gauge."""
        if not self.include_measurements:
            return

        if isinstance(measurement.value, (int, float)):
            tags = self._get_tags(context)
            tags["measurement"] = measurement.name

            self.backend.gauge(
                f"measurement_{measurement.name}",
                measurement.value,
                tags=tags,
            )

            if measurement.passed is not None:
                status = "pass" if measurement.passed else "fail"
                self.backend.counter(
                    f"measurement_{status}",
                    tags=tags,
                )

    async def on_sequence_complete(
        self,
        context: ExecutionContext,
        result: dict[str, Any],
    ) -> None:
        """Record sequence completion."""
        tags = self._get_tags(context)
        tags["status"] = "pass" if result.get("passed") else "fail"

        self.backend.counter("sequence_completed", tags=tags)
        self.backend.timing(
            "sequence_duration",
            result.get("duration", 0),
            tags=self._get_tags(context),
        )

        if result.get("passed"):
            self.backend.counter("sequence_passed", tags=self._get_tags(context))
        else:
            self.backend.counter("sequence_failed", tags=self._get_tags(context))

    async def on_error(
        self,
        context: ExecutionContext,
        code: str,
        message: str,
        recoverable: bool,
    ) -> None:
        """Record error occurrence."""
        tags = self._get_tags(context)
        tags["error_code"] = code
        tags["recoverable"] = str(recoverable).lower()

        self.backend.counter("errors", tags=tags)

"""Observability module for Station Service SDK.

This module provides structured logging, tracing, and metrics
capabilities for monitoring sequence execution.
"""

from station_service_sdk.observability.logging import (
    LogRecord,
    StructuredLogger,
    configure_logging,
)
from station_service_sdk.observability.metrics import (
    MetricsBackend,
    MetricsHook,
    InMemoryMetrics,
)

__all__ = [
    # Logging
    "LogRecord",
    "StructuredLogger",
    "configure_logging",
    # Metrics
    "MetricsBackend",
    "MetricsHook",
    "InMemoryMetrics",
]

# Optional tracing import
try:
    from station_service_sdk.observability.tracing import (
        TracingHook,
        configure_tracing,
    )

    __all__.extend(["TracingHook", "configure_tracing"])
except ImportError:
    pass  # OpenTelemetry not installed

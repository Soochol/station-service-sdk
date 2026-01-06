"""Hardware integration module for Station Service SDK.

This module provides hardware connection management, retry mechanisms,
and health monitoring capabilities.
"""

from station_service_sdk.hardware.connection import (
    ConnectionConfig,
    HardwareConnectionPool,
    PooledConnection,
)
from station_service_sdk.hardware.health import (
    HealthCheckable,
    HealthCheckResult,
    HealthMonitor,
)
from station_service_sdk.hardware.retry import (
    ExponentialBackoff,
    RetryStrategy,
    with_retry,
)

__all__ = [
    # Connection
    "ConnectionConfig",
    "HardwareConnectionPool",
    "PooledConnection",
    # Health
    "HealthCheckable",
    "HealthCheckResult",
    "HealthMonitor",
    # Retry
    "ExponentialBackoff",
    "RetryStrategy",
    "with_retry",
]

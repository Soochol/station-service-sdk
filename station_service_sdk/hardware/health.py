"""Health check module for hardware monitoring.

Provides health check infrastructure for monitoring hardware
device status and connection health.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Protocol, runtime_checkable


@dataclass
class HealthCheckResult:
    """Result of a health check operation.

    Attributes:
        healthy: Whether the target is healthy
        latency_ms: Response latency in milliseconds
        last_error: Last error message if unhealthy
        checked_at: Timestamp of the check
        details: Additional diagnostic details
    """

    healthy: bool
    latency_ms: float
    last_error: str | None = None
    checked_at: datetime = field(default_factory=datetime.now)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with health check data
        """
        return {
            "healthy": self.healthy,
            "latency_ms": self.latency_ms,
            "last_error": self.last_error,
            "checked_at": self.checked_at.isoformat(),
            "details": self.details,
        }


@runtime_checkable
class HealthCheckable(Protocol):
    """Protocol for objects that support health checks.

    Implement this protocol to enable health monitoring
    for hardware drivers or other components.
    """

    async def health_check(self) -> HealthCheckResult:
        """Perform a health check.

        Returns:
            HealthCheckResult with status information
        """
        ...


class HealthMonitor:
    """Background health monitor for multiple targets.

    Continuously monitors the health of registered targets
    and notifies callbacks on status changes.

    Attributes:
        check_interval: Interval between health checks in seconds
    """

    def __init__(self, check_interval: float = 30.0):
        """Initialize health monitor.

        Args:
            check_interval: Interval between checks in seconds
        """
        self.check_interval = check_interval
        self._results: dict[str, HealthCheckResult] = {}
        self._previous_status: dict[str, bool] = {}
        self._callbacks: list[Callable[[str, HealthCheckResult], None]] = []
        self._async_callbacks: list[Callable[[str, HealthCheckResult], Any]] = []
        self._monitoring_task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None

    def on_health_change(
        self,
        callback: Callable[[str, HealthCheckResult], None],
    ) -> None:
        """Register callback for health status changes.

        Callback is invoked when a target's health status changes
        from healthy to unhealthy or vice versa.

        Args:
            callback: Function to call with (target_name, result)
        """
        self._callbacks.append(callback)

    def on_health_change_async(
        self,
        callback: Callable[[str, HealthCheckResult], Any],
    ) -> None:
        """Register async callback for health status changes.

        Args:
            callback: Async function to call with (target_name, result)
        """
        self._async_callbacks.append(callback)

    async def check_one(
        self,
        name: str,
        target: HealthCheckable,
    ) -> HealthCheckResult:
        """Perform a single health check.

        Args:
            name: Target identifier
            target: Object implementing HealthCheckable

        Returns:
            Health check result
        """
        start = time.perf_counter()
        try:
            result = await target.health_check()
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            result = HealthCheckResult(
                healthy=False,
                latency_ms=latency,
                last_error=str(e),
                details={"exception_type": type(e).__name__},
            )

        self._results[name] = result
        await self._notify_if_changed(name, result)
        return result

    async def check_all(
        self,
        targets: dict[str, HealthCheckable],
    ) -> dict[str, HealthCheckResult]:
        """Check health of all targets concurrently.

        Args:
            targets: Dictionary mapping names to HealthCheckable objects

        Returns:
            Dictionary mapping names to health check results
        """
        async with asyncio.TaskGroup() as tg:
            tasks = {
                name: tg.create_task(self.check_one(name, target))
                for name, target in targets.items()
            }

        return {name: task.result() for name, task in tasks.items()}

    async def start_monitoring(
        self,
        targets: dict[str, HealthCheckable],
    ) -> None:
        """Start background health monitoring.

        Args:
            targets: Dictionary mapping names to HealthCheckable objects
        """
        self._stop_event = asyncio.Event()

        async def monitor_loop() -> None:
            while not self._stop_event.is_set():
                try:
                    await self.check_all(targets)
                except Exception:
                    pass  # Individual errors handled in check_one
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.check_interval,
                    )
                except asyncio.TimeoutError:
                    continue

        self._monitoring_task = asyncio.create_task(monitor_loop())

    async def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        if self._stop_event:
            self._stop_event.set()

        if self._monitoring_task:
            try:
                await asyncio.wait_for(self._monitoring_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._monitoring_task.cancel()
            self._monitoring_task = None

    def get_result(self, name: str) -> HealthCheckResult | None:
        """Get latest health check result for a target.

        Args:
            name: Target identifier

        Returns:
            Latest result or None if not checked
        """
        return self._results.get(name)

    def get_all_results(self) -> dict[str, HealthCheckResult]:
        """Get all health check results.

        Returns:
            Dictionary of all results
        """
        return dict(self._results)

    def is_healthy(self, name: str) -> bool:
        """Check if a target is currently healthy.

        Args:
            name: Target identifier

        Returns:
            True if target is healthy, False otherwise
        """
        result = self._results.get(name)
        return result.healthy if result else False

    def all_healthy(self) -> bool:
        """Check if all monitored targets are healthy.

        Returns:
            True if all targets are healthy
        """
        if not self._results:
            return True
        return all(r.healthy for r in self._results.values())

    async def _notify_if_changed(
        self,
        name: str,
        result: HealthCheckResult,
    ) -> None:
        """Notify callbacks if health status changed.

        Args:
            name: Target identifier
            result: Current health check result
        """
        previous = self._previous_status.get(name)
        current = result.healthy

        if previous is None or previous != current:
            self._previous_status[name] = current

            for callback in self._callbacks:
                try:
                    callback(name, result)
                except Exception:
                    pass  # Don't let callback errors affect monitoring

            for async_callback in self._async_callbacks:
                try:
                    await async_callback(name, result)
                except Exception:
                    pass


class CompositeHealthCheck:
    """Aggregate health check for multiple components.

    Combines multiple health checks into a single result,
    useful for checking overall system health.
    """

    def __init__(self, targets: dict[str, HealthCheckable]):
        """Initialize composite health check.

        Args:
            targets: Dictionary of named health checkable targets
        """
        self.targets = targets

    async def health_check(self) -> HealthCheckResult:
        """Perform composite health check.

        Returns:
            Aggregated health check result
        """
        start = time.perf_counter()
        results: dict[str, HealthCheckResult] = {}
        unhealthy: list[str] = []

        async with asyncio.TaskGroup() as tg:
            tasks = {
                name: tg.create_task(target.health_check())
                for name, target in self.targets.items()
            }

        for name, task in tasks.items():
            result = task.result()
            results[name] = result
            if not result.healthy:
                unhealthy.append(name)

        latency = (time.perf_counter() - start) * 1000
        healthy = len(unhealthy) == 0

        return HealthCheckResult(
            healthy=healthy,
            latency_ms=latency,
            last_error=f"Unhealthy components: {', '.join(unhealthy)}" if unhealthy else None,
            details={
                "components": {name: r.to_dict() for name, r in results.items()},
                "healthy_count": len(results) - len(unhealthy),
                "total_count": len(results),
            },
        )

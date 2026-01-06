"""Connection pool for hardware drivers.

Provides connection pooling with automatic health checks,
reconnection, and resource management for hardware devices.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Protocol, runtime_checkable

from station_service_sdk.hardware.health import HealthCheckResult, HealthCheckable
from station_service_sdk.hardware.retry import ExponentialBackoff, RetryStrategy


@runtime_checkable
class Driver(Protocol):
    """Protocol for hardware drivers compatible with connection pool."""

    async def connect(self) -> None:
        """Establish connection to hardware."""
        ...

    async def disconnect(self) -> None:
        """Close connection to hardware."""
        ...

    def is_connected(self) -> bool:
        """Check if currently connected."""
        ...


@dataclass
class ConnectionConfig:
    """Configuration for hardware connection pool.

    Attributes:
        max_connections: Maximum concurrent connections per hardware
        health_check_interval: Interval between health checks in seconds
        connection_timeout: Timeout for connection attempts in seconds
        idle_timeout: Time before idle connections are closed
        retry_strategy: Strategy for connection retries
    """

    max_connections: int = 1
    health_check_interval: float = 30.0
    connection_timeout: float = 10.0
    idle_timeout: float = 300.0
    retry_strategy: RetryStrategy = field(default_factory=ExponentialBackoff)


@dataclass
class PooledConnection:
    """A pooled connection wrapper.

    Attributes:
        driver: The underlying driver instance
        hardware_id: Identifier for the hardware
        created_at: Timestamp when connection was created
        last_used: Timestamp when connection was last used
        healthy: Whether connection is considered healthy
        in_use: Whether connection is currently in use
    """

    driver: Any
    hardware_id: str
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    healthy: bool = True
    in_use: bool = False

    def mark_used(self) -> None:
        """Mark connection as recently used."""
        self.last_used = time.time()

    def is_idle(self, idle_timeout: float) -> bool:
        """Check if connection has been idle too long.

        Args:
            idle_timeout: Maximum idle time in seconds

        Returns:
            True if connection is idle
        """
        return time.time() - self.last_used > idle_timeout


class HardwareConnectionPool:
    """Thread-safe connection pool for hardware drivers.

    Manages connection lifecycle including creation, health checks,
    and automatic cleanup of idle connections.

    Example:
        >>> pool = HardwareConnectionPool(config=ConnectionConfig())
        >>> pool.register_factory("device", create_driver)
        >>>
        >>> async with pool.acquire("device") as driver:
        ...     await driver.measure()
    """

    def __init__(
        self,
        config: ConnectionConfig | None = None,
        on_connection_error: Callable[[str, Exception], None] | None = None,
    ):
        """Initialize connection pool.

        Args:
            config: Pool configuration
            on_connection_error: Optional error callback
        """
        self.config = config or ConnectionConfig()
        self._pools: dict[str, list[PooledConnection]] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._health_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._on_error = on_connection_error

    def register_factory(
        self,
        hardware_id: str,
        factory: Callable[[], Any],
    ) -> None:
        """Register a driver factory for a hardware ID.

        Args:
            hardware_id: Unique identifier for the hardware
            factory: Callable that creates a new driver instance
        """
        self._factories[hardware_id] = factory
        self._pools[hardware_id] = []
        self._semaphores[hardware_id] = asyncio.Semaphore(self.config.max_connections)
        self._locks[hardware_id] = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, hardware_id: str) -> AsyncIterator[Any]:
        """Acquire a connection from the pool.

        Context manager that acquires a connection, yields it for use,
        and releases it back to the pool on exit.

        Args:
            hardware_id: Identifier for the hardware

        Yields:
            Driver instance

        Raises:
            ValueError: If hardware_id is not registered
            TimeoutError: If connection cannot be acquired in time
        """
        if hardware_id not in self._factories:
            raise ValueError(f"Unknown hardware ID: {hardware_id}")

        semaphore = self._semaphores[hardware_id]

        try:
            await asyncio.wait_for(
                semaphore.acquire(),
                timeout=self.config.connection_timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Timeout waiting for connection to {hardware_id}"
            ) from None

        conn: PooledConnection | None = None
        try:
            conn = await self._get_or_create(hardware_id)
            conn.in_use = True
            yield conn.driver
        finally:
            if conn:
                conn.in_use = False
                conn.mark_used()
            semaphore.release()

    async def _get_or_create(self, hardware_id: str) -> PooledConnection:
        """Get existing connection or create new one.

        Args:
            hardware_id: Hardware identifier

        Returns:
            Pooled connection instance
        """
        async with self._locks[hardware_id]:
            pool = self._pools[hardware_id]

            # Try to find an available healthy connection
            for conn in pool:
                if not conn.in_use and conn.healthy:
                    return conn

            # Create new connection if under limit
            if len(pool) < self.config.max_connections:
                conn = await self._create_connection(hardware_id)
                pool.append(conn)
                return conn

            # Wait for any connection to become available
            for conn in pool:
                if not conn.in_use:
                    if not conn.healthy:
                        await self._reconnect(conn)
                    return conn

        raise RuntimeError(f"No available connections for {hardware_id}")

    async def _create_connection(self, hardware_id: str) -> PooledConnection:
        """Create a new connection.

        Args:
            hardware_id: Hardware identifier

        Returns:
            New pooled connection
        """
        factory = self._factories[hardware_id]
        driver = factory()

        try:
            await asyncio.wait_for(
                driver.connect(),
                timeout=self.config.connection_timeout,
            )
        except Exception as e:
            if self._on_error:
                self._on_error(hardware_id, e)
            raise

        return PooledConnection(
            driver=driver,
            hardware_id=hardware_id,
        )

    async def _reconnect(self, conn: PooledConnection) -> None:
        """Attempt to reconnect an unhealthy connection.

        Args:
            conn: Connection to reconnect
        """
        strategy = self.config.retry_strategy
        driver = conn.driver

        for attempt in range(strategy.max_attempts):
            try:
                if hasattr(driver, "disconnect"):
                    try:
                        await driver.disconnect()
                    except Exception:
                        pass

                await asyncio.wait_for(
                    driver.connect(),
                    timeout=self.config.connection_timeout,
                )
                conn.healthy = True
                conn.last_used = time.time()
                return

            except Exception as e:
                if not strategy.should_retry(attempt, e):
                    conn.healthy = False
                    if self._on_error:
                        self._on_error(conn.hardware_id, e)
                    raise
                await asyncio.sleep(strategy.get_delay(attempt))

    async def health_check(self, hardware_id: str) -> dict[str, HealthCheckResult]:
        """Check health of all connections for a hardware.

        Args:
            hardware_id: Hardware identifier

        Returns:
            Dictionary mapping connection ID to health result
        """
        results: dict[str, HealthCheckResult] = {}
        pool = self._pools.get(hardware_id, [])

        for i, conn in enumerate(pool):
            conn_id = f"{hardware_id}:{i}"
            start = time.perf_counter()

            try:
                if isinstance(conn.driver, HealthCheckable):
                    result = await conn.driver.health_check()
                elif hasattr(conn.driver, "is_connected"):
                    healthy = conn.driver.is_connected()
                    latency = (time.perf_counter() - start) * 1000
                    result = HealthCheckResult(
                        healthy=healthy,
                        latency_ms=latency,
                    )
                else:
                    latency = (time.perf_counter() - start) * 1000
                    result = HealthCheckResult(
                        healthy=True,
                        latency_ms=latency,
                        details={"note": "No health check method available"},
                    )

                conn.healthy = result.healthy

            except Exception as e:
                latency = (time.perf_counter() - start) * 1000
                result = HealthCheckResult(
                    healthy=False,
                    latency_ms=latency,
                    last_error=str(e),
                )
                conn.healthy = False

            results[conn_id] = result

        return results

    async def health_check_all(self) -> dict[str, HealthCheckResult]:
        """Check health of all connections in the pool.

        Returns:
            Dictionary mapping connection IDs to health results
        """
        results: dict[str, HealthCheckResult] = {}

        for hardware_id in self._pools:
            hw_results = await self.health_check(hardware_id)
            results.update(hw_results)

        return results

    async def start_maintenance(self) -> None:
        """Start background maintenance tasks.

        Starts health checking and idle connection cleanup.
        """
        self._stop_event.clear()

        async def health_loop() -> None:
            while not self._stop_event.is_set():
                try:
                    await self.health_check_all()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.config.health_check_interval,
                    )
                except asyncio.TimeoutError:
                    continue

        async def cleanup_loop() -> None:
            while not self._stop_event.is_set():
                try:
                    await self._cleanup_idle()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=60.0,  # Cleanup every minute
                    )
                except asyncio.TimeoutError:
                    continue

        self._health_task = asyncio.create_task(health_loop())
        self._cleanup_task = asyncio.create_task(cleanup_loop())

    async def stop_maintenance(self) -> None:
        """Stop background maintenance tasks."""
        self._stop_event.set()

        for task in [self._health_task, self._cleanup_task]:
            if task:
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.TimeoutError:
                    task.cancel()

        self._health_task = None
        self._cleanup_task = None

    async def _cleanup_idle(self) -> None:
        """Close idle connections."""
        for hardware_id, pool in self._pools.items():
            async with self._locks[hardware_id]:
                # Keep at least one connection, remove extras if idle
                while len(pool) > 1:
                    # Find idle connection
                    idle_conn = None
                    for conn in pool:
                        if (
                            not conn.in_use
                            and conn.is_idle(self.config.idle_timeout)
                        ):
                            idle_conn = conn
                            break

                    if idle_conn is None:
                        break

                    pool.remove(idle_conn)
                    try:
                        await idle_conn.driver.disconnect()
                    except Exception:
                        pass

    async def close_all(self) -> None:
        """Close all connections and shutdown pool."""
        await self.stop_maintenance()

        for hardware_id, pool in self._pools.items():
            async with self._locks[hardware_id]:
                for conn in pool:
                    try:
                        await conn.driver.disconnect()
                    except Exception:
                        pass
                pool.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        stats: dict[str, Any] = {}

        for hardware_id, pool in self._pools.items():
            total = len(pool)
            in_use = sum(1 for c in pool if c.in_use)
            healthy = sum(1 for c in pool if c.healthy)

            stats[hardware_id] = {
                "total": total,
                "in_use": in_use,
                "available": total - in_use,
                "healthy": healthy,
                "unhealthy": total - healthy,
            }

        return stats

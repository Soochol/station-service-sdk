"""
Sequence runner utilities.

Provides helpers for running sequences with timeout, retry, and other options.
"""

import asyncio
import time
from typing import Any, Callable, Dict, Optional, TypeVar

from .exceptions import TimeoutError as SDKTimeoutError

T = TypeVar("T")


async def run_with_timeout(
    coro: Callable[..., T],
    timeout: float,
    *args: Any,
    **kwargs: Any,
) -> T:
    """
    Run coroutine with timeout.

    Args:
        coro: Coroutine function to run
        timeout: Timeout in seconds
        *args: Positional arguments for coroutine
        **kwargs: Keyword arguments for coroutine

    Returns:
        Coroutine result

    Raises:
        TimeoutError: If timeout exceeded
    """
    try:
        return await asyncio.wait_for(coro(*args, **kwargs), timeout=timeout)
    except asyncio.TimeoutError:
        raise SDKTimeoutError(f"Operation timed out after {timeout}s", timeout)


async def run_with_retry(
    coro: Callable[..., T],
    max_retries: int = 3,
    retry_delay: float = 1.0,
    exceptions: tuple = (Exception,),
    *args: Any,
    **kwargs: Any,
) -> T:
    """
    Run coroutine with retry on failure.

    Args:
        coro: Coroutine function to run
        max_retries: Maximum number of retries
        retry_delay: Delay between retries in seconds
        exceptions: Tuple of exception types to retry on
        *args: Positional arguments for coroutine
        **kwargs: Keyword arguments for coroutine

    Returns:
        Coroutine result

    Raises:
        Last exception if all retries failed
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await coro(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)
            else:
                raise

    raise last_exception  # type: ignore


class StepTimer:
    """
    Context manager for timing step execution.

    Usage:
        with StepTimer() as timer:
            # do work
        print(f"Duration: {timer.duration}s")
    """

    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def __enter__(self) -> "StepTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.end_time = time.perf_counter()

    @property
    def duration(self) -> float:
        """Get duration in seconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.perf_counter()
        return end - self.start_time


class AsyncStepTimer:
    """
    Async context manager for timing step execution.

    Usage:
        async with AsyncStepTimer() as timer:
            # do async work
        print(f"Duration: {timer.duration}s")
    """

    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    async def __aenter__(self) -> "AsyncStepTimer":
        self.start_time = time.perf_counter()
        return self

    async def __aexit__(self, *args: Any) -> None:
        self.end_time = time.perf_counter()

    @property
    def duration(self) -> float:
        """Get duration in seconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.perf_counter()
        return end - self.start_time


def validate_measurement(
    value: float,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> bool:
    """
    Validate measurement against limits.

    Args:
        value: Measured value
        min_value: Minimum acceptable value
        max_value: Maximum acceptable value

    Returns:
        True if value is within limits
    """
    if min_value is not None and value < min_value:
        return False
    if max_value is not None and value > max_value:
        return False
    return True


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "1m 23s", "45.2s", "1h 2m")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

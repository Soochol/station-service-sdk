"""Retry mechanisms for hardware operations.

Provides retry strategies with configurable backoff algorithms
for resilient hardware communication.
"""

from __future__ import annotations

import asyncio
import functools
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from station_service_sdk.exceptions import (
    CommunicationError,
    HardwareConnectionError,
    SequenceTimeoutError,
)

F = TypeVar("F", bound=Callable[..., Any])


class RetryStrategy(ABC):
    """Abstract base class for retry strategies."""

    @abstractmethod
    def get_delay(self, attempt: int) -> float:
        """Calculate delay before next retry attempt.

        Args:
            attempt: Zero-based attempt number

        Returns:
            Delay in seconds before next attempt
        """
        ...

    @abstractmethod
    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Determine if operation should be retried.

        Args:
            attempt: Zero-based attempt number
            exception: The exception that occurred

        Returns:
            True if operation should be retried
        """
        ...


@dataclass
class ExponentialBackoff(RetryStrategy):
    """Exponential backoff retry strategy with jitter.

    Implements exponential backoff with optional jitter to prevent
    thundering herd problems in distributed systems.

    Attributes:
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay cap in seconds (default: 60.0)
        max_attempts: Maximum number of retry attempts (default: 5)
        jitter: Jitter factor (0.0 to 1.0) for randomization (default: 0.1)
        retryable_exceptions: Tuple of exception types to retry
    """

    base_delay: float = 1.0
    max_delay: float = 60.0
    max_attempts: int = 5
    jitter: float = 0.1
    retryable_exceptions: tuple[type[Exception], ...] = (
        HardwareConnectionError,
        CommunicationError,
        SequenceTimeoutError,
        TimeoutError,
        ConnectionError,
        OSError,
    )

    def get_delay(self, attempt: int) -> float:
        """Calculate exponential delay with jitter.

        Args:
            attempt: Zero-based attempt number

        Returns:
            Delay in seconds with applied jitter
        """
        delay = min(self.base_delay * (2**attempt), self.max_delay)
        if self.jitter > 0:
            jitter_amount = random.uniform(-self.jitter, self.jitter) * delay
            delay = max(0, delay + jitter_amount)
        return delay

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Check if exception is retryable and attempts remain.

        Args:
            attempt: Zero-based attempt number
            exception: The exception that occurred

        Returns:
            True if should retry
        """
        if attempt >= self.max_attempts:
            return False
        return isinstance(exception, self.retryable_exceptions)


@dataclass
class FixedDelay(RetryStrategy):
    """Fixed delay retry strategy.

    Uses a constant delay between retry attempts.

    Attributes:
        delay: Fixed delay in seconds (default: 1.0)
        max_attempts: Maximum number of retry attempts (default: 3)
        retryable_exceptions: Tuple of exception types to retry
    """

    delay: float = 1.0
    max_attempts: int = 3
    retryable_exceptions: tuple[type[Exception], ...] = (
        HardwareConnectionError,
        CommunicationError,
        TimeoutError,
    )

    def get_delay(self, attempt: int) -> float:
        """Return fixed delay.

        Args:
            attempt: Ignored for fixed delay

        Returns:
            Fixed delay in seconds
        """
        return self.delay

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Check if exception is retryable and attempts remain.

        Args:
            attempt: Zero-based attempt number
            exception: The exception that occurred

        Returns:
            True if should retry
        """
        if attempt >= self.max_attempts:
            return False
        return isinstance(exception, self.retryable_exceptions)


@dataclass
class LinearBackoff(RetryStrategy):
    """Linear backoff retry strategy.

    Increases delay linearly with each attempt.

    Attributes:
        initial_delay: Initial delay in seconds (default: 1.0)
        increment: Delay increment per attempt (default: 1.0)
        max_delay: Maximum delay cap in seconds (default: 30.0)
        max_attempts: Maximum number of retry attempts (default: 5)
        retryable_exceptions: Tuple of exception types to retry
    """

    initial_delay: float = 1.0
    increment: float = 1.0
    max_delay: float = 30.0
    max_attempts: int = 5
    retryable_exceptions: tuple[type[Exception], ...] = (
        HardwareConnectionError,
        CommunicationError,
        TimeoutError,
    )

    def get_delay(self, attempt: int) -> float:
        """Calculate linear delay.

        Args:
            attempt: Zero-based attempt number

        Returns:
            Delay in seconds
        """
        delay = self.initial_delay + (self.increment * attempt)
        return min(delay, self.max_delay)

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Check if exception is retryable and attempts remain.

        Args:
            attempt: Zero-based attempt number
            exception: The exception that occurred

        Returns:
            True if should retry
        """
        if attempt >= self.max_attempts:
            return False
        return isinstance(exception, self.retryable_exceptions)


def with_retry(
    strategy: RetryStrategy | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> Callable[[F], F]:
    """Decorator for retryable async operations.

    Wraps an async function with retry logic using the specified strategy.

    Args:
        strategy: Retry strategy to use (default: ExponentialBackoff())
        on_retry: Optional callback called before each retry with
                  (attempt, exception, delay)

    Returns:
        Decorated function with retry capability

    Example:
        >>> @with_retry(ExponentialBackoff(max_attempts=3))
        ... async def connect_hardware():
        ...     # May fail transiently
        ...     await hardware.connect()
    """
    if strategy is None:
        strategy = ExponentialBackoff()

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(strategy.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if not strategy.should_retry(attempt, e):
                        raise

                    delay = strategy.get_delay(attempt)
                    if on_retry:
                        on_retry(attempt, e, delay)

                    await asyncio.sleep(delay)

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper  # type: ignore

    return decorator


class RetryContext:
    """Context manager for retry operations.

    Provides a context manager interface for retry logic,
    useful when decorator approach is not suitable.

    Example:
        >>> async with RetryContext(ExponentialBackoff()) as retry:
        ...     while retry.should_continue():
        ...         try:
        ...             result = await operation()
        ...             break
        ...         except Exception as e:
        ...             await retry.handle_error(e)
    """

    def __init__(self, strategy: RetryStrategy):
        self.strategy = strategy
        self._attempt = 0
        self._last_exception: Exception | None = None

    async def __aenter__(self) -> "RetryContext":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        return False

    def should_continue(self) -> bool:
        """Check if retry loop should continue.

        Returns:
            True if more attempts are allowed
        """
        return self._attempt <= self.strategy.max_attempts

    async def handle_error(self, exception: Exception) -> None:
        """Handle an error and wait before retry if applicable.

        Args:
            exception: The exception that occurred

        Raises:
            The exception if no more retries are allowed
        """
        self._last_exception = exception

        if not self.strategy.should_retry(self._attempt, exception):
            raise exception

        delay = self.strategy.get_delay(self._attempt)
        self._attempt += 1
        await asyncio.sleep(delay)

    @property
    def attempt(self) -> int:
        """Current attempt number (zero-based)."""
        return self._attempt

    @property
    def last_exception(self) -> Exception | None:
        """Last exception encountered."""
        return self._last_exception

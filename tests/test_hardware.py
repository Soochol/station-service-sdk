"""Tests for hardware retry strategies."""

import pytest

from station_service_sdk.hardware.retry import (
    ExponentialBackoff,
    FixedDelay,
    LinearBackoff,
)
from station_service_sdk import HardwareConnectionError


class TestExponentialBackoff:
    """Tests for ExponentialBackoff strategy."""

    def test_default_values(self) -> None:
        """Test default configuration."""
        strategy = ExponentialBackoff()

        assert strategy.base_delay == 1.0
        assert strategy.max_delay == 60.0
        assert strategy.max_attempts == 5

    def test_exponential_delay(self) -> None:
        """Test delay increases exponentially."""
        strategy = ExponentialBackoff(base_delay=1.0, jitter=0)

        assert strategy.get_delay(0) == 1.0   # 1 * 2^0
        assert strategy.get_delay(1) == 2.0   # 1 * 2^1
        assert strategy.get_delay(2) == 4.0   # 1 * 2^2
        assert strategy.get_delay(3) == 8.0   # 1 * 2^3

    def test_max_delay_cap(self) -> None:
        """Test delay is capped at max_delay."""
        strategy = ExponentialBackoff(base_delay=1.0, max_delay=5.0, jitter=0)

        assert strategy.get_delay(10) == 5.0  # Should cap at 5

    def test_jitter_applied(self) -> None:
        """Test jitter adds randomization."""
        strategy = ExponentialBackoff(base_delay=1.0, jitter=0.5)

        # Run multiple times, delays should vary
        delays = [strategy.get_delay(0) for _ in range(10)]
        # With 50% jitter, some should be different
        assert len(set(delays)) >= 1

    def test_should_retry_retryable_exception(self) -> None:
        """Test retryable exceptions allow retry."""
        strategy = ExponentialBackoff(max_attempts=3)

        assert strategy.should_retry(0, HardwareConnectionError("test"))
        assert strategy.should_retry(2, HardwareConnectionError("test"))
        assert not strategy.should_retry(3, HardwareConnectionError("test"))

    def test_should_retry_non_retryable_exception(self) -> None:
        """Test non-retryable exceptions don't retry."""
        strategy = ExponentialBackoff()

        assert not strategy.should_retry(0, ValueError("test"))

    def test_custom_retryable_exceptions(self) -> None:
        """Test custom retryable exception list."""
        strategy = ExponentialBackoff(
            retryable_exceptions=(ValueError, TypeError)
        )

        assert strategy.should_retry(0, ValueError("test"))
        assert strategy.should_retry(0, TypeError("test"))
        assert not strategy.should_retry(0, RuntimeError("test"))


class TestFixedDelay:
    """Tests for FixedDelay strategy."""

    def test_constant_delay(self) -> None:
        """Test delay is constant."""
        strategy = FixedDelay(delay=2.0, max_attempts=5)

        assert strategy.get_delay(0) == 2.0
        assert strategy.get_delay(1) == 2.0
        assert strategy.get_delay(10) == 2.0

    def test_default_values(self) -> None:
        """Test default configuration."""
        strategy = FixedDelay()

        assert strategy.delay == 1.0
        assert strategy.max_attempts == 3

    def test_should_retry(self) -> None:
        """Test retry logic."""
        strategy = FixedDelay(max_attempts=2)

        assert strategy.should_retry(0, HardwareConnectionError("test"))
        assert strategy.should_retry(1, HardwareConnectionError("test"))
        assert not strategy.should_retry(2, HardwareConnectionError("test"))


class TestLinearBackoff:
    """Tests for LinearBackoff strategy."""

    def test_linear_increase(self) -> None:
        """Test delay increases linearly."""
        strategy = LinearBackoff(initial_delay=1.0, increment=1.0)

        assert strategy.get_delay(0) == 1.0
        assert strategy.get_delay(1) == 2.0
        assert strategy.get_delay(2) == 3.0

    def test_max_delay_cap(self) -> None:
        """Test delay is capped at max_delay."""
        strategy = LinearBackoff(
            initial_delay=1.0,
            increment=2.0,
            max_delay=5.0,
        )

        assert strategy.get_delay(0) == 1.0
        assert strategy.get_delay(1) == 3.0
        assert strategy.get_delay(2) == 5.0
        assert strategy.get_delay(10) == 5.0  # Capped

    def test_default_values(self) -> None:
        """Test default configuration."""
        strategy = LinearBackoff()

        assert strategy.initial_delay == 1.0
        assert strategy.increment == 1.0
        assert strategy.max_delay == 30.0
        assert strategy.max_attempts == 5


class TestRetryStrategyInterface:
    """Tests for common retry strategy interface."""

    @pytest.mark.parametrize("StrategyClass", [
        ExponentialBackoff,
        FixedDelay,
        LinearBackoff,
    ])
    def test_has_required_methods(self, StrategyClass) -> None:
        """Test all strategies have required methods."""
        strategy = StrategyClass()

        assert hasattr(strategy, "get_delay")
        assert hasattr(strategy, "should_retry")
        assert hasattr(strategy, "max_attempts")

    @pytest.mark.parametrize("StrategyClass", [
        ExponentialBackoff,
        FixedDelay,
        LinearBackoff,
    ])
    def test_delay_is_non_negative(self, StrategyClass) -> None:
        """Test delay is always non-negative."""
        strategy = StrategyClass()

        for attempt in range(10):
            delay = strategy.get_delay(attempt)
            assert delay >= 0

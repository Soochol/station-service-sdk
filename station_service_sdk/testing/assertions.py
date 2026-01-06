"""Custom assertions for testing sequences.

Provides assertion helpers for validating sequence execution results,
measurements, and step outcomes.
"""

from __future__ import annotations

from typing import Any

from station_service_sdk.testing.mocks import CapturedOutput


class AssertionError(Exception):
    """Custom assertion error with detailed context."""

    def __init__(self, message: str, expected: Any = None, actual: Any = None):
        self.expected = expected
        self.actual = actual
        super().__init__(message)


def assert_step_passed(
    output: CapturedOutput,
    step_name: str,
    message: str | None = None,
) -> dict[str, Any]:
    """Assert that a specific step passed.

    Args:
        output: Captured output from sequence execution
        step_name: Name of the step to check
        message: Optional custom error message

    Returns:
        Step result dictionary

    Raises:
        AssertionError: If step not found or failed
    """
    step_results = output.get_step_results()
    step = next((s for s in step_results if s["name"] == step_name), None)

    if step is None:
        available = [s["name"] for s in step_results]
        raise AssertionError(
            message or f"Step '{step_name}' not found. Available steps: {available}",
            expected=step_name,
            actual=available,
        )

    if not step["passed"]:
        error = step.get("error", "Unknown error")
        raise AssertionError(
            message or f"Step '{step_name}' failed: {error}",
            expected=True,
            actual=False,
        )

    return step


def assert_step_failed(
    output: CapturedOutput,
    step_name: str,
    error_contains: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """Assert that a specific step failed.

    Args:
        output: Captured output from sequence execution
        step_name: Name of the step to check
        error_contains: Optional substring to find in error message
        message: Optional custom error message

    Returns:
        Step result dictionary

    Raises:
        AssertionError: If step not found or passed
    """
    step_results = output.get_step_results()
    step = next((s for s in step_results if s["name"] == step_name), None)

    if step is None:
        available = [s["name"] for s in step_results]
        raise AssertionError(
            message or f"Step '{step_name}' not found. Available steps: {available}",
            expected=step_name,
            actual=available,
        )

    if step["passed"]:
        raise AssertionError(
            message or f"Step '{step_name}' passed but was expected to fail",
            expected=False,
            actual=True,
        )

    if error_contains:
        error = step.get("error", "")
        if error_contains not in error:
            raise AssertionError(
                message or f"Step error does not contain '{error_contains}': {error}",
                expected=error_contains,
                actual=error,
            )

    return step


def assert_sequence_passed(
    output: CapturedOutput,
    message: str | None = None,
) -> dict[str, Any]:
    """Assert that the sequence passed.

    Args:
        output: Captured output from sequence execution
        message: Optional custom error message

    Returns:
        Final result dictionary

    Raises:
        AssertionError: If sequence failed or no result found
    """
    result = output.get_final_result()

    if result is None:
        raise AssertionError(
            message or "No sequence completion result found",
        )

    if not result["passed"]:
        error = result.get("error", "Unknown error")
        raise AssertionError(
            message or f"Sequence failed: {error}",
            expected=True,
            actual=False,
        )

    return result


def assert_sequence_failed(
    output: CapturedOutput,
    error_contains: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """Assert that the sequence failed.

    Args:
        output: Captured output from sequence execution
        error_contains: Optional substring to find in error message
        message: Optional custom error message

    Returns:
        Final result dictionary

    Raises:
        AssertionError: If sequence passed
    """
    result = output.get_final_result()

    if result is None:
        raise AssertionError(
            message or "No sequence completion result found",
        )

    if result["passed"]:
        raise AssertionError(
            message or "Sequence passed but was expected to fail",
            expected=False,
            actual=True,
        )

    if error_contains:
        error = result.get("error", "")
        if error_contains not in error:
            raise AssertionError(
                message or f"Sequence error does not contain '{error_contains}': {error}",
                expected=error_contains,
                actual=error,
            )

    return result


def assert_measurement_in_range(
    output: CapturedOutput,
    name: str,
    min_value: float | None = None,
    max_value: float | None = None,
    expected_value: float | None = None,
    tolerance: float = 0.01,
    message: str | None = None,
) -> float:
    """Assert that a measurement is within expected range.

    Args:
        output: Captured output from sequence execution
        name: Measurement name
        min_value: Minimum acceptable value (optional)
        max_value: Maximum acceptable value (optional)
        expected_value: Expected value (optional)
        tolerance: Tolerance for expected value comparison
        message: Optional custom error message

    Returns:
        Actual measurement value

    Raises:
        AssertionError: If measurement not found or out of range
    """
    measurements = output.get_measurements()

    if name not in measurements:
        available = list(measurements.keys())
        raise AssertionError(
            message or f"Measurement '{name}' not found. Available: {available}",
            expected=name,
            actual=available,
        )

    value = measurements[name]

    if not isinstance(value, (int, float)):
        raise AssertionError(
            message or f"Measurement '{name}' is not numeric: {value}",
            expected="numeric",
            actual=type(value).__name__,
        )

    if min_value is not None and value < min_value:
        raise AssertionError(
            message or f"Measurement '{name}' ({value}) is below minimum ({min_value})",
            expected=f">= {min_value}",
            actual=value,
        )

    if max_value is not None and value > max_value:
        raise AssertionError(
            message or f"Measurement '{name}' ({value}) is above maximum ({max_value})",
            expected=f"<= {max_value}",
            actual=value,
        )

    if expected_value is not None:
        if abs(value - expected_value) > tolerance:
            raise AssertionError(
                message or (
                    f"Measurement '{name}' ({value}) differs from expected "
                    f"({expected_value}) by more than tolerance ({tolerance})"
                ),
                expected=expected_value,
                actual=value,
            )

    return value


def assert_measurement_passed(
    output: CapturedOutput,
    name: str,
    message: str | None = None,
) -> dict[str, Any]:
    """Assert that a measurement passed its limits.

    Args:
        output: Captured output from sequence execution
        name: Measurement name
        message: Optional custom error message

    Returns:
        Measurement dictionary

    Raises:
        AssertionError: If measurement not found or failed
    """
    measurement_msgs = output.get_messages_by_type("MEASUREMENT")
    measurement = next(
        (m.data for m in measurement_msgs if m.data["name"] == name),
        None,
    )

    if measurement is None:
        available = [m.data["name"] for m in measurement_msgs]
        raise AssertionError(
            message or f"Measurement '{name}' not found. Available: {available}",
            expected=name,
            actual=available,
        )

    if measurement.get("passed") is False:
        value = measurement["value"]
        min_val = measurement.get("min_value")
        max_val = measurement.get("max_value")
        raise AssertionError(
            message or (
                f"Measurement '{name}' failed: value={value}, "
                f"min={min_val}, max={max_val}"
            ),
            expected=True,
            actual=False,
        )

    return measurement


def assert_no_errors(
    output: CapturedOutput,
    ignore_codes: list[str] | None = None,
    message: str | None = None,
) -> None:
    """Assert that no errors occurred.

    Args:
        output: Captured output from sequence execution
        ignore_codes: Error codes to ignore
        message: Optional custom error message

    Raises:
        AssertionError: If any non-ignored errors found
    """
    errors = output.get_errors()
    ignore_codes = ignore_codes or []

    significant_errors = [
        e for e in errors
        if e["code"] not in ignore_codes
    ]

    if significant_errors:
        error_summary = ", ".join(
            f"{e['code']}: {e['message']}" for e in significant_errors
        )
        raise AssertionError(
            message or f"Unexpected errors occurred: {error_summary}",
            expected="No errors",
            actual=significant_errors,
        )


def assert_error_occurred(
    output: CapturedOutput,
    code: str | None = None,
    message_contains: str | None = None,
    custom_message: str | None = None,
) -> dict[str, Any]:
    """Assert that a specific error occurred.

    Args:
        output: Captured output from sequence execution
        code: Expected error code (optional)
        message_contains: Substring to find in error message (optional)
        custom_message: Optional custom error message

    Returns:
        Error dictionary

    Raises:
        AssertionError: If expected error not found
    """
    errors = output.get_errors()

    if not errors:
        raise AssertionError(
            custom_message or "No errors occurred, but expected one",
        )

    for error in errors:
        code_match = code is None or error["code"] == code
        msg_match = (
            message_contains is None or
            message_contains in error.get("message", "")
        )

        if code_match and msg_match:
            return error

    if code:
        available_codes = [e["code"] for e in errors]
        raise AssertionError(
            custom_message or f"Error with code '{code}' not found. Found: {available_codes}",
            expected=code,
            actual=available_codes,
        )

    if message_contains:
        messages = [e.get("message", "") for e in errors]
        raise AssertionError(
            custom_message or (
                f"No error contains '{message_contains}'. "
                f"Error messages: {messages}"
            ),
            expected=message_contains,
            actual=messages,
        )

    return errors[0]


def assert_step_count(
    output: CapturedOutput,
    expected_count: int,
    message: str | None = None,
) -> list[dict[str, Any]]:
    """Assert the number of steps executed.

    Args:
        output: Captured output from sequence execution
        expected_count: Expected number of steps
        message: Optional custom error message

    Returns:
        List of step results

    Raises:
        AssertionError: If step count doesn't match
    """
    steps = output.get_step_results()
    actual_count = len(steps)

    if actual_count != expected_count:
        raise AssertionError(
            message or f"Expected {expected_count} steps, got {actual_count}",
            expected=expected_count,
            actual=actual_count,
        )

    return steps


def assert_all_steps_passed(
    output: CapturedOutput,
    message: str | None = None,
) -> list[dict[str, Any]]:
    """Assert that all steps passed.

    Args:
        output: Captured output from sequence execution
        message: Optional custom error message

    Returns:
        List of step results

    Raises:
        AssertionError: If any step failed
    """
    steps = output.get_step_results()
    failed = [s for s in steps if not s["passed"]]

    if failed:
        failed_names = [s["name"] for s in failed]
        raise AssertionError(
            message or f"Steps failed: {failed_names}",
            expected="All passed",
            actual=failed_names,
        )

    return steps

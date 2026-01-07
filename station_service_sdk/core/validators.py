"""
Input validation helpers for SDK emit methods.

Provides validation functions used by SequenceBase to ensure
parameters meet expected constraints before processing.
"""

import re
from typing import Any

from .exceptions import ValidationError


# Step name validation pattern: must be valid Python identifier or kebab-case
STEP_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")

# Error code pattern: UPPER_SNAKE_CASE
ERROR_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Valid input types for user input requests
VALID_INPUT_TYPES = frozenset({"confirm", "text", "number", "select"})

# Valid log levels
VALID_LOG_LEVELS = frozenset({"debug", "info", "warning", "error"})


def validate_step_name(step_name: str, field: str = "step_name") -> str:
    """
    Validate step name format.

    Step names must:
    - Be non-empty strings
    - Start with a letter or underscore
    - Contain only letters, numbers, underscores, or hyphens

    Args:
        step_name: The step name to validate
        field: Field name for error messages

    Returns:
        The validated step name (stripped of whitespace)

    Raises:
        ValidationError: If step name is invalid
    """
    if not isinstance(step_name, str):
        raise ValidationError(
            f"{field} must be a string, got {type(step_name).__name__}",
            field=field,
        )

    step_name = step_name.strip()

    if not step_name:
        raise ValidationError(
            f"{field} cannot be empty",
            field=field,
        )

    if len(step_name) > 100:
        raise ValidationError(
            f"{field} too long (max 100 characters)",
            field=field,
            details={"length": len(step_name)},
        )

    if not STEP_NAME_PATTERN.match(step_name):
        raise ValidationError(
            f"Invalid {field} '{step_name}': must start with letter/underscore, "
            "contain only letters, numbers, underscores, or hyphens",
            field=field,
        )

    return step_name


def validate_timeout(timeout: float, field: str = "timeout") -> float:
    """
    Validate timeout value.

    Timeout must be a positive number.

    Args:
        timeout: Timeout value in seconds
        field: Field name for error messages

    Returns:
        The validated timeout value

    Raises:
        ValidationError: If timeout is invalid
    """
    if not isinstance(timeout, (int, float)):
        raise ValidationError(
            f"{field} must be a number, got {type(timeout).__name__}",
            field=field,
        )

    if timeout <= 0:
        raise ValidationError(
            f"{field} must be positive, got {timeout}",
            field=field,
        )

    if timeout > 86400:  # 24 hours max
        raise ValidationError(
            f"{field} too large (max 86400 seconds / 24 hours)",
            field=field,
            details={"value": timeout},
        )

    return float(timeout)


def validate_index_total(index: int, total: int) -> tuple[int, int]:
    """
    Validate step index and total bounds.

    Args:
        index: Current step index (0-based or 1-based)
        total: Total number of steps

    Returns:
        Tuple of (index, total)

    Raises:
        ValidationError: If values are invalid
    """
    if not isinstance(index, int):
        raise ValidationError(
            f"index must be an integer, got {type(index).__name__}",
            field="index",
        )

    if not isinstance(total, int):
        raise ValidationError(
            f"total must be an integer, got {type(total).__name__}",
            field="total",
        )

    if total < 1:
        raise ValidationError(
            f"total must be at least 1, got {total}",
            field="total",
        )

    if index < 0:
        raise ValidationError(
            f"index cannot be negative, got {index}",
            field="index",
        )

    if index > total:
        raise ValidationError(
            f"index ({index}) cannot exceed total ({total})",
            field="index",
            details={"index": index, "total": total},
        )

    return index, total


def validate_input_type(input_type: str) -> str:
    """
    Validate user input type.

    Args:
        input_type: Type of input (confirm, text, number, select)

    Returns:
        The validated input type (lowercase)

    Raises:
        ValidationError: If input type is invalid
    """
    if not isinstance(input_type, str):
        raise ValidationError(
            f"input_type must be a string, got {type(input_type).__name__}",
            field="input_type",
        )

    input_type = input_type.lower().strip()

    if input_type not in VALID_INPUT_TYPES:
        raise ValidationError(
            f"Invalid input_type '{input_type}': "
            f"must be one of {sorted(VALID_INPUT_TYPES)}",
            field="input_type",
        )

    return input_type


def validate_measurement_name(name: str) -> str:
    """
    Validate measurement name.

    Args:
        name: Measurement name

    Returns:
        The validated measurement name

    Raises:
        ValidationError: If name is invalid
    """
    if not isinstance(name, str):
        raise ValidationError(
            f"measurement name must be a string, got {type(name).__name__}",
            field="name",
        )

    name = name.strip()

    if not name:
        raise ValidationError(
            "measurement name cannot be empty",
            field="name",
        )

    if len(name) > 100:
        raise ValidationError(
            "measurement name too long (max 100 characters)",
            field="name",
        )

    return name


def validate_measurement_value(value: Any) -> Any:
    """
    Validate measurement value.

    Accepts: int, float, str, bool, None

    Args:
        value: The measurement value

    Returns:
        The value (unchanged)

    Raises:
        ValidationError: If value type is invalid
    """
    valid_types = (int, float, str, bool, type(None))

    if not isinstance(value, valid_types):
        raise ValidationError(
            f"measurement value must be int, float, str, bool, or None, "
            f"got {type(value).__name__}",
            field="value",
        )

    return value


def validate_error_code(code: str) -> str:
    """
    Validate error code format.

    Error codes should be UPPER_SNAKE_CASE.

    Args:
        code: The error code

    Returns:
        The validated error code

    Raises:
        ValidationError: If code format is invalid
    """
    if not isinstance(code, str):
        raise ValidationError(
            f"error code must be a string, got {type(code).__name__}",
            field="code",
        )

    code = code.strip()

    if not code:
        raise ValidationError(
            "error code cannot be empty",
            field="code",
        )

    if len(code) > 50:
        raise ValidationError(
            "error code too long (max 50 characters)",
            field="code",
        )

    if not ERROR_CODE_PATTERN.match(code):
        raise ValidationError(
            f"Invalid error code '{code}': should be UPPER_SNAKE_CASE",
            field="code",
        )

    return code


def validate_duration(duration: float, field: str = "duration") -> float:
    """
    Validate duration value.

    Args:
        duration: Duration in seconds (must be non-negative)
        field: Field name for error messages

    Returns:
        The validated duration

    Raises:
        ValidationError: If duration is invalid
    """
    if not isinstance(duration, (int, float)):
        raise ValidationError(
            f"{field} must be a number, got {type(duration).__name__}",
            field=field,
        )

    if duration < 0:
        raise ValidationError(
            f"{field} cannot be negative, got {duration}",
            field=field,
        )

    return float(duration)


def validate_log_level(level: str) -> str:
    """
    Validate log level.

    Args:
        level: Log level (debug, info, warning, error)

    Returns:
        The validated log level (lowercase)

    Raises:
        ValidationError: If log level is invalid
    """
    if not isinstance(level, str):
        raise ValidationError(
            f"log level must be a string, got {type(level).__name__}",
            field="level",
        )

    level = level.lower().strip()

    if level not in VALID_LOG_LEVELS:
        raise ValidationError(
            f"Invalid log level '{level}': must be one of {sorted(VALID_LOG_LEVELS)}",
            field="level",
        )

    return level

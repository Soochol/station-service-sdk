"""Tests for input validation helpers."""

import pytest

from station_service_sdk.core.validators import (
    validate_step_name,
    validate_timeout,
    validate_index_total,
    validate_input_type,
    validate_measurement_name,
    validate_measurement_value,
    validate_error_code,
    validate_duration,
    validate_log_level,
)
from station_service_sdk import ValidationError


class TestValidateStepName:
    """Tests for validate_step_name."""

    @pytest.mark.parametrize("name", [
        "valid_step",
        "step1",
        "Step",
        "_private",
        "step-with-hyphen",
        "a",
        "test_step_123",
    ])
    def test_valid_names(self, name: str) -> None:
        """Test valid step names pass validation."""
        assert validate_step_name(name) == name

    def test_empty_rejected(self) -> None:
        """Test empty step name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_step_name("")
        assert exc_info.value.field == "step_name"
        assert "cannot be empty" in str(exc_info.value)

    def test_whitespace_only_rejected(self) -> None:
        """Test whitespace-only step name is rejected."""
        with pytest.raises(ValidationError):
            validate_step_name("   ")

    def test_starts_with_number_rejected(self) -> None:
        """Test step name starting with number is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_step_name("123start")
        assert "must start with letter" in str(exc_info.value)

    def test_special_chars_rejected(self) -> None:
        """Test step name with special characters is rejected."""
        with pytest.raises(ValidationError):
            validate_step_name("step@name")

    def test_spaces_rejected(self) -> None:
        """Test step name with spaces is rejected."""
        with pytest.raises(ValidationError):
            validate_step_name("step name")

    def test_strips_whitespace(self) -> None:
        """Test whitespace is stripped."""
        assert validate_step_name("  step  ") == "step"

    def test_max_length(self) -> None:
        """Test maximum length enforcement."""
        long_name = "a" * 101
        with pytest.raises(ValidationError) as exc_info:
            validate_step_name(long_name)
        assert "too long" in str(exc_info.value)

    def test_exactly_max_length(self) -> None:
        """Test exactly at max length passes."""
        name = "a" * 100
        assert validate_step_name(name) == name

    def test_non_string_rejected(self) -> None:
        """Test non-string value is rejected."""
        with pytest.raises(ValidationError):
            validate_step_name(123)  # type: ignore

    def test_custom_field_name(self) -> None:
        """Test custom field name in error."""
        with pytest.raises(ValidationError) as exc_info:
            validate_step_name("", field="custom_field")
        assert exc_info.value.field == "custom_field"


class TestValidateTimeout:
    """Tests for validate_timeout."""

    @pytest.mark.parametrize("value", [1, 1.5, 60, 3600, 86400])
    def test_valid_timeouts(self, value: float) -> None:
        """Test valid timeout values pass."""
        assert validate_timeout(value) == float(value)

    @pytest.mark.parametrize("value", [0, -1, -100])
    def test_non_positive_rejected(self, value: float) -> None:
        """Test non-positive values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_timeout(value)
        assert "must be positive" in str(exc_info.value)

    def test_max_timeout(self) -> None:
        """Test maximum timeout (24 hours)."""
        with pytest.raises(ValidationError) as exc_info:
            validate_timeout(86401)
        assert "too large" in str(exc_info.value)

    def test_exactly_max_timeout(self) -> None:
        """Test exactly at max timeout passes."""
        assert validate_timeout(86400) == 86400.0

    def test_non_numeric_rejected(self) -> None:
        """Test non-numeric values are rejected."""
        with pytest.raises(ValidationError):
            validate_timeout("60")  # type: ignore

    def test_int_converted_to_float(self) -> None:
        """Test integer is converted to float."""
        result = validate_timeout(60)
        assert isinstance(result, float)
        assert result == 60.0


class TestValidateIndexTotal:
    """Tests for validate_index_total."""

    def test_valid_values(self) -> None:
        """Test valid index/total combinations."""
        assert validate_index_total(0, 1) == (0, 1)
        assert validate_index_total(1, 3) == (1, 3)
        assert validate_index_total(3, 3) == (3, 3)

    def test_negative_index_rejected(self) -> None:
        """Test negative index is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_index_total(-1, 3)
        assert exc_info.value.field == "index"
        assert "cannot be negative" in str(exc_info.value)

    def test_zero_total_rejected(self) -> None:
        """Test zero total is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_index_total(1, 0)
        assert exc_info.value.field == "total"
        assert "at least 1" in str(exc_info.value)

    def test_negative_total_rejected(self) -> None:
        """Test negative total is rejected."""
        with pytest.raises(ValidationError):
            validate_index_total(1, -1)

    def test_index_exceeds_total(self) -> None:
        """Test index > total is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_index_total(5, 3)
        assert "cannot exceed" in str(exc_info.value)

    def test_non_integer_index(self) -> None:
        """Test non-integer index is rejected."""
        with pytest.raises(ValidationError):
            validate_index_total(1.5, 3)  # type: ignore

    def test_non_integer_total(self) -> None:
        """Test non-integer total is rejected."""
        with pytest.raises(ValidationError):
            validate_index_total(1, 3.5)  # type: ignore


class TestValidateInputType:
    """Tests for validate_input_type."""

    @pytest.mark.parametrize("input_type", ["confirm", "text", "number", "select"])
    def test_valid_types(self, input_type: str) -> None:
        """Test valid input types pass."""
        assert validate_input_type(input_type) == input_type

    def test_case_insensitive(self) -> None:
        """Test input types are case-insensitive."""
        assert validate_input_type("CONFIRM") == "confirm"
        assert validate_input_type("Text") == "text"
        assert validate_input_type("NUMBER") == "number"

    def test_strips_whitespace(self) -> None:
        """Test whitespace is stripped."""
        assert validate_input_type("  text  ") == "text"

    def test_invalid_type_rejected(self) -> None:
        """Test invalid input types are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_input_type("invalid")
        assert exc_info.value.field == "input_type"
        assert "must be one of" in str(exc_info.value)

    def test_non_string_rejected(self) -> None:
        """Test non-string value is rejected."""
        with pytest.raises(ValidationError):
            validate_input_type(123)  # type: ignore


class TestValidateMeasurementName:
    """Tests for validate_measurement_name."""

    def test_valid_names(self) -> None:
        """Test valid measurement names pass."""
        assert validate_measurement_name("voltage") == "voltage"
        assert validate_measurement_name("Current (A)") == "Current (A)"
        assert validate_measurement_name("test-measurement") == "test-measurement"

    def test_empty_rejected(self) -> None:
        """Test empty name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_measurement_name("")
        assert exc_info.value.field == "name"

    def test_whitespace_only_rejected(self) -> None:
        """Test whitespace-only name is rejected."""
        with pytest.raises(ValidationError):
            validate_measurement_name("   ")

    def test_max_length(self) -> None:
        """Test maximum length enforcement."""
        with pytest.raises(ValidationError):
            validate_measurement_name("a" * 101)

    def test_strips_whitespace(self) -> None:
        """Test whitespace is stripped."""
        assert validate_measurement_name("  voltage  ") == "voltage"


class TestValidateMeasurementValue:
    """Tests for validate_measurement_value."""

    @pytest.mark.parametrize("value", [1, 1.5, "test", True, False, None])
    def test_valid_values(self, value) -> None:
        """Test valid value types pass."""
        assert validate_measurement_value(value) == value

    @pytest.mark.parametrize("value", [[1, 2], {"a": 1}, set(), (1, 2)])
    def test_invalid_types_rejected(self, value) -> None:
        """Test invalid value types are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_measurement_value(value)
        assert exc_info.value.field == "value"

    def test_zero_is_valid(self) -> None:
        """Test zero is a valid value."""
        assert validate_measurement_value(0) == 0
        assert validate_measurement_value(0.0) == 0.0


class TestValidateErrorCode:
    """Tests for validate_error_code."""

    @pytest.mark.parametrize("code", [
        "ERROR",
        "HARDWARE_ERROR",
        "E001",
        "ERROR_123",
        "A",
    ])
    def test_valid_codes(self, code: str) -> None:
        """Test valid error codes pass."""
        assert validate_error_code(code) == code

    def test_lowercase_rejected(self) -> None:
        """Test lowercase error code is rejected."""
        with pytest.raises(ValidationError):
            validate_error_code("error")

    def test_mixed_case_rejected(self) -> None:
        """Test mixed case error code is rejected."""
        with pytest.raises(ValidationError):
            validate_error_code("Error")

    def test_hyphen_rejected(self) -> None:
        """Test hyphen in error code is rejected."""
        with pytest.raises(ValidationError):
            validate_error_code("HARDWARE-ERROR")

    def test_empty_rejected(self) -> None:
        """Test empty error code is rejected."""
        with pytest.raises(ValidationError):
            validate_error_code("")

    def test_max_length(self) -> None:
        """Test maximum length enforcement."""
        with pytest.raises(ValidationError):
            validate_error_code("A" * 51)

    def test_strips_whitespace(self) -> None:
        """Test whitespace is stripped."""
        assert validate_error_code("  ERROR  ") == "ERROR"

    def test_starts_with_number_rejected(self) -> None:
        """Test starting with number is rejected."""
        with pytest.raises(ValidationError):
            validate_error_code("123ERROR")


class TestValidateDuration:
    """Tests for validate_duration."""

    def test_valid_durations(self) -> None:
        """Test valid duration values pass."""
        assert validate_duration(0) == 0.0
        assert validate_duration(1.5) == 1.5
        assert validate_duration(3600) == 3600.0

    def test_negative_rejected(self) -> None:
        """Test negative duration is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_duration(-1)
        assert "cannot be negative" in str(exc_info.value)

    def test_non_numeric_rejected(self) -> None:
        """Test non-numeric value is rejected."""
        with pytest.raises(ValidationError):
            validate_duration("10")  # type: ignore

    def test_int_converted_to_float(self) -> None:
        """Test integer is converted to float."""
        result = validate_duration(10)
        assert isinstance(result, float)


class TestValidateLogLevel:
    """Tests for validate_log_level."""

    @pytest.mark.parametrize("level", ["debug", "info", "warning", "error"])
    def test_valid_levels(self, level: str) -> None:
        """Test valid log levels pass."""
        assert validate_log_level(level) == level

    def test_case_insensitive(self) -> None:
        """Test log levels are case-insensitive."""
        assert validate_log_level("DEBUG") == "debug"
        assert validate_log_level("Info") == "info"

    def test_invalid_level_rejected(self) -> None:
        """Test invalid log level is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_log_level("critical")
        assert exc_info.value.field == "level"

    def test_non_string_rejected(self) -> None:
        """Test non-string value is rejected."""
        with pytest.raises(ValidationError):
            validate_log_level(1)  # type: ignore

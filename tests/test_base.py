"""Tests for SequenceBase lifecycle and emit methods."""

import pytest
from typing import Dict, Any

from station_service_sdk import (
    SequenceBase,
    ValidationError,
    SetupError,
    AbortError,
)
from station_service_sdk.core.sdk_types import RunResult
from station_service_sdk.testing import CapturedOutput, create_test_context


class MinimalSequence(SequenceBase):
    """Minimal sequence for testing."""

    name = "minimal_test"
    version = "1.0.0"
    description = "Test sequence"

    async def setup(self) -> None:
        pass

    async def run(self) -> RunResult:
        return {"passed": True, "measurements": {}}

    async def teardown(self) -> None:
        pass


class TestSequenceBaseInit:
    """Tests for SequenceBase initialization."""

    def test_init_with_context(self) -> None:
        """Test initialization with execution context."""
        ctx = create_test_context()
        seq = MinimalSequence(context=ctx)

        assert seq.context == ctx
        assert seq.hardware_config == ctx.hardware_config
        assert seq.parameters == ctx.parameters

    def test_init_with_custom_hardware_config(self) -> None:
        """Test initialization with custom hardware config."""
        ctx = create_test_context()
        hw_config: Dict[str, Dict[str, Any]] = {"mcu": {"port": "/dev/ttyUSB1"}}
        seq = MinimalSequence(context=ctx, hardware_config=hw_config)

        assert seq.hardware_config == hw_config

    def test_init_with_custom_parameters(self) -> None:
        """Test initialization with custom parameters."""
        ctx = create_test_context()
        params: Dict[str, Any] = {"voltage": 3.3}
        seq = MinimalSequence(context=ctx, parameters=params)

        assert seq.parameters == params

    def test_init_with_custom_output_strategy(self) -> None:
        """Test initialization with custom output strategy."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        assert seq._output == output

    def test_class_attributes(self) -> None:
        """Test class-level metadata attributes."""
        assert MinimalSequence.name == "minimal_test"
        assert MinimalSequence.version == "1.0.0"
        assert MinimalSequence.description == "Test sequence"


class TestSequenceBaseLifecycle:
    """Tests for SequenceBase execution lifecycle."""

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """Test successful sequence execution."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        result = await seq._execute()

        assert result["passed"] is True
        assert result["error"] is None
        assert ctx.completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_setup_failure(self) -> None:
        """Test sequence execution with setup failure."""

        class FailSetupSequence(MinimalSequence):
            async def setup(self) -> None:
                raise SetupError("Hardware not found")

        ctx = create_test_context()
        output = CapturedOutput()
        seq = FailSetupSequence(context=ctx, output_strategy=output)

        result = await seq._execute()

        assert result["passed"] is False
        assert "Setup failed" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_run_failure(self) -> None:
        """Test sequence execution with run failure."""

        class FailRunSequence(MinimalSequence):
            async def run(self) -> RunResult:
                raise ValueError("Test error")

        ctx = create_test_context()
        output = CapturedOutput()
        seq = FailRunSequence(context=ctx, output_strategy=output)

        result = await seq._execute()

        assert result["passed"] is False
        assert "Unexpected error" in result["error"]

    @pytest.mark.asyncio
    async def test_teardown_always_runs(self) -> None:
        """Test that teardown runs even after failures."""
        teardown_called = False

        class TeardownTestSequence(MinimalSequence):
            async def run(self) -> RunResult:
                raise ValueError("Test error")

            async def teardown(self) -> None:
                nonlocal teardown_called
                teardown_called = True

        ctx = create_test_context()
        output = CapturedOutput()
        seq = TeardownTestSequence(context=ctx, output_strategy=output)

        await seq._execute()

        assert teardown_called is True

    @pytest.mark.asyncio
    async def test_teardown_error_captured(self) -> None:
        """Test that teardown errors are captured."""

        class TeardownFailSequence(MinimalSequence):
            async def teardown(self) -> None:
                raise ValueError("Cleanup failed")

        ctx = create_test_context()
        output = CapturedOutput()
        seq = TeardownFailSequence(context=ctx, output_strategy=output)

        result = await seq._execute()

        assert "Teardown failed" in result["error"]


class TestEmitStepStart:
    """Tests for emit_step_start validation."""

    @pytest.mark.asyncio
    async def test_valid_step_name(self) -> None:
        """Test valid step names are accepted."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        # Should not raise
        seq.emit_step_start("valid_step", 1, 3, "Description")
        seq.emit_step_start("step-with-hyphen", 2, 3)
        seq.emit_step_start("Step123", 3, 3)

    def test_invalid_step_name_empty(self) -> None:
        """Test empty step name is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError) as exc_info:
            seq.emit_step_start("", 1, 1)

        assert exc_info.value.field == "step_name"

    def test_invalid_step_name_starts_with_number(self) -> None:
        """Test step name starting with number is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError):
            seq.emit_step_start("123step", 1, 1)

    def test_invalid_index_negative(self) -> None:
        """Test negative index is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError) as exc_info:
            seq.emit_step_start("step", -1, 1)

        assert exc_info.value.field == "index"

    def test_invalid_total_zero(self) -> None:
        """Test zero total is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError) as exc_info:
            seq.emit_step_start("step", 1, 0)

        assert exc_info.value.field == "total"

    def test_index_exceeds_total(self) -> None:
        """Test index exceeding total is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError):
            seq.emit_step_start("step", 5, 3)


class TestEmitStepComplete:
    """Tests for emit_step_complete validation."""

    @pytest.mark.asyncio
    async def test_valid_step_complete(self) -> None:
        """Test valid step complete is accepted."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        seq.emit_step_complete("test_step", 1, True, 1.5)

    def test_invalid_step_name(self) -> None:
        """Test invalid step name is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError):
            seq.emit_step_complete("", 1, True, 1.5)

    def test_invalid_duration_negative(self) -> None:
        """Test negative duration is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError) as exc_info:
            seq.emit_step_complete("step", 1, True, -1.0)

        assert exc_info.value.field == "duration"

    @pytest.mark.asyncio
    async def test_zero_duration_allowed(self) -> None:
        """Test zero duration is allowed."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        seq.emit_step_complete("step", 1, True, 0.0)


class TestEmitMeasurement:
    """Tests for emit_measurement validation."""

    @pytest.mark.asyncio
    async def test_valid_measurement(self) -> None:
        """Test valid measurement is accepted."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        seq.emit_measurement("voltage", 3.3, "V")

        measurements = output.get_measurements()
        assert "voltage" in measurements

    def test_invalid_measurement_name_empty(self) -> None:
        """Test empty measurement name is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError):
            seq.emit_measurement("", 3.3)

    def test_invalid_measurement_value_list(self) -> None:
        """Test list value is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError):
            seq.emit_measurement("data", [1, 2, 3])  # type: ignore

    @pytest.mark.asyncio
    async def test_valid_measurement_types(self) -> None:
        """Test various valid value types."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        seq.emit_measurement("int_val", 42)
        seq.emit_measurement("float_val", 3.14)
        seq.emit_measurement("str_val", "test")
        seq.emit_measurement("bool_val", True)
        seq.emit_measurement("none_val", None)

    @pytest.mark.asyncio
    async def test_measurement_with_limits(self) -> None:
        """Test measurement with min/max limits."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        seq.emit_measurement("voltage", 3.3, "V", min_value=3.0, max_value=3.6)


class TestEmitError:
    """Tests for emit_error validation."""

    def test_valid_error_code(self) -> None:
        """Test valid error codes are accepted."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        seq.emit_error("HARDWARE_ERROR", "Device disconnected")
        seq.emit_error("E001", "Error with number")

    def test_invalid_error_code_lowercase(self) -> None:
        """Test lowercase error code is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError):
            seq.emit_error("hardware_error", "Message")

    def test_invalid_error_code_empty(self) -> None:
        """Test empty error code is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError):
            seq.emit_error("", "Message")


class TestRequestInput:
    """Tests for request_input validation."""

    @pytest.mark.asyncio
    async def test_invalid_input_type(self) -> None:
        """Test invalid input type is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError):
            await seq.request_input("Prompt", input_type="invalid")

    @pytest.mark.asyncio
    async def test_invalid_timeout_negative(self) -> None:
        """Test negative timeout is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError):
            await seq.request_input("Prompt", timeout=-10)

    @pytest.mark.asyncio
    async def test_invalid_timeout_zero(self) -> None:
        """Test zero timeout is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError):
            await seq.request_input("Prompt", timeout=0)


class TestRequestConfirmation:
    """Tests for request_confirmation validation."""

    @pytest.mark.asyncio
    async def test_invalid_timeout(self) -> None:
        """Test invalid timeout is rejected."""
        ctx = create_test_context()
        output = CapturedOutput()
        seq = MinimalSequence(context=ctx, output_strategy=output)

        with pytest.raises(ValidationError):
            await seq.request_confirmation("Confirm?", timeout=-1)


class TestAbort:
    """Tests for abort functionality."""

    def test_abort_raises_error(self) -> None:
        """Test abort() raises AbortError."""
        ctx = create_test_context()
        seq = MinimalSequence(context=ctx)

        with pytest.raises(AbortError):
            seq.abort("User cancelled")

    def test_check_abort_when_not_aborted(self) -> None:
        """Test check_abort() does nothing when not aborted."""
        ctx = create_test_context()
        seq = MinimalSequence(context=ctx)

        seq.check_abort()  # Should not raise

    def test_check_abort_when_aborted(self) -> None:
        """Test check_abort() raises when aborted."""
        ctx = create_test_context()
        seq = MinimalSequence(context=ctx)
        seq._aborted = True

        with pytest.raises(AbortError):
            seq.check_abort()


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_get_parameter(self) -> None:
        """Test get_parameter retrieves values."""
        ctx = create_test_context()
        params = {"voltage": 3.3, "current": 0.5}
        seq = MinimalSequence(context=ctx, parameters=params)

        assert seq.get_parameter("voltage") == 3.3
        assert seq.get_parameter("current") == 0.5
        assert seq.get_parameter("missing") is None
        assert seq.get_parameter("missing", "default") == "default"

    def test_get_hardware_config(self) -> None:
        """Test get_hardware_config retrieves values."""
        ctx = create_test_context()
        hw_config: Dict[str, Dict[str, Any]] = {
            "mcu": {"port": "/dev/ttyUSB0"},
            "power": {"address": "192.168.1.100"},
        }
        seq = MinimalSequence(context=ctx, hardware_config=hw_config)

        assert seq.get_hardware_config("mcu") == {"port": "/dev/ttyUSB0"}
        assert seq.get_hardware_config("power") == {"address": "192.168.1.100"}
        assert seq.get_hardware_config("missing") == {}


class TestErrorStateAccessors:
    """Tests for error state accessor properties."""

    def test_initial_error_state(self) -> None:
        """Test initial error state is None."""
        ctx = create_test_context()
        seq = MinimalSequence(context=ctx)

        assert seq.setup_error is None
        assert seq.run_error is None
        assert seq.teardown_error is None
        assert seq.last_error is None

    @pytest.mark.asyncio
    async def test_setup_error_captured(self) -> None:
        """Test setup error is captured."""

        class FailSetupSeq(MinimalSequence):
            async def setup(self) -> None:
                raise SetupError("Setup failed")

        ctx = create_test_context()
        seq = FailSetupSeq(context=ctx, output_strategy=CapturedOutput())

        await seq._execute()

        assert seq.setup_error == "Setup failed"
        assert seq.last_error == "Setup failed"

    @pytest.mark.asyncio
    async def test_run_error_captured(self) -> None:
        """Test run error is captured."""

        class FailRunSeq(MinimalSequence):
            async def run(self) -> RunResult:
                raise ValueError("Run failed")

        ctx = create_test_context()
        seq = FailRunSeq(context=ctx, output_strategy=CapturedOutput())

        await seq._execute()

        assert seq.run_error == "Run failed"
        assert seq.run_exception is not None

    @pytest.mark.asyncio
    async def test_teardown_error_captured(self) -> None:
        """Test teardown error is captured."""

        class FailTeardownSeq(MinimalSequence):
            async def teardown(self) -> None:
                raise ValueError("Teardown failed")

        ctx = create_test_context()
        seq = FailTeardownSeq(context=ctx, output_strategy=CapturedOutput())

        await seq._execute()

        assert seq.teardown_error == "Teardown failed"
        assert seq.teardown_exception is not None

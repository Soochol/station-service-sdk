"""Tests for SDK type definitions and enums."""

import pytest
from station_service_sdk.sdk_types import (
    ExecutionPhase,
    LogLevel,
    SimulationStatus,
    InputType,
    RunResult,
    ExecutionResult,
    MeasurementDict,
    StepResultDict,
    StepMeta,
    StepInfo,
)


class TestExecutionPhase:
    """Tests for ExecutionPhase enum."""

    def test_all_phases_defined(self):
        """Test all expected phases are defined."""
        expected = ["idle", "setup", "running", "teardown", "paused",
                    "waiting", "completed", "failed", "aborted"]
        actual = [p.value for p in ExecutionPhase]
        assert sorted(actual) == sorted(expected)

    def test_phase_is_string_enum(self):
        """Test phases can be used as strings."""
        assert ExecutionPhase.RUNNING == "running"
        assert ExecutionPhase.SETUP.value == "setup"

    def test_phase_comparison(self):
        """Test phase equality."""
        assert ExecutionPhase.RUNNING == ExecutionPhase.RUNNING
        assert ExecutionPhase.SETUP != ExecutionPhase.TEARDOWN


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_all_levels_defined(self):
        """Test all log levels are defined."""
        expected = ["debug", "info", "warning", "error"]
        actual = [level.value for level in LogLevel]
        assert sorted(actual) == sorted(expected)

    def test_level_string_comparison(self):
        """Test levels work as strings."""
        assert LogLevel.INFO == "info"
        assert LogLevel.ERROR == "error"


class TestSimulationStatus:
    """Tests for SimulationStatus enum."""

    def test_statuses_defined(self):
        """Test simulation statuses are defined."""
        assert SimulationStatus.COMPLETED == "completed"
        assert SimulationStatus.FAILED == "failed"


class TestInputType:
    """Tests for InputType enum."""

    def test_all_types_defined(self):
        """Test all input types are defined."""
        expected = ["confirm", "text", "number", "select"]
        actual = [t.value for t in InputType]
        assert sorted(actual) == sorted(expected)


class TestStepMeta:
    """Tests for StepMeta dataclass."""

    def test_basic_creation(self):
        """Test basic StepMeta creation."""
        meta = StepMeta(name="test_step", order=1)
        assert meta.name == "test_step"
        assert meta.order == 1
        assert meta.timeout == 60.0
        assert meta.retry == 0
        assert meta.cleanup is False

    def test_display_name_defaults_to_name(self):
        """Test display_name defaults to name."""
        meta = StepMeta(name="my_step", order=1)
        assert meta.display_name == "my_step"

    def test_display_name_explicit(self):
        """Test explicit display_name."""
        meta = StepMeta(name="my_step", order=1, display_name="My Step")
        assert meta.display_name == "My Step"

    def test_frozen_dataclass(self):
        """Test StepMeta is immutable."""
        meta = StepMeta(name="test", order=1)
        with pytest.raises(AttributeError):
            meta.name = "changed"

    def test_all_optional_fields(self):
        """Test all optional fields."""
        meta = StepMeta(
            name="full_step",
            order=5,
            timeout=120.0,
            retry=3,
            cleanup=True,
            condition="passed",
            description="A full step",
            display_name="Full Step",
            estimated_duration=10.5,
        )
        assert meta.timeout == 120.0
        assert meta.retry == 3
        assert meta.cleanup is True
        assert meta.condition == "passed"
        assert meta.description == "A full step"
        assert meta.estimated_duration == 10.5


class TestStepInfo:
    """Tests for StepInfo dataclass."""

    def test_basic_creation(self):
        """Test basic StepInfo creation."""
        info = StepInfo(name="step", display_name="Step", order=1)
        assert info.name == "step"
        assert info.display_name == "Step"
        assert info.order == 1

    def test_to_meta_conversion(self):
        """Test conversion to StepMeta."""
        info = StepInfo(
            name="test_step",
            display_name="Test Step",
            order=2,
            timeout=30.0,
            retry=1,
            cleanup=True,
            description="Test description",
        )
        meta = info.to_meta()

        assert isinstance(meta, StepMeta)
        assert meta.name == "test_step"
        assert meta.display_name == "Test Step"
        assert meta.order == 2
        assert meta.timeout == 30.0
        assert meta.retry == 1
        assert meta.cleanup is True
        assert meta.description == "Test description"

    def test_method_field_not_in_meta(self):
        """Test that method field is not transferred to meta."""
        def dummy_method():
            pass

        info = StepInfo(
            name="step",
            display_name="Step",
            order=1,
            method=dummy_method,
        )
        meta = info.to_meta()

        # StepMeta doesn't have a method field
        assert not hasattr(meta, 'method') or meta.__dict__.get('method') is None


class TestTypedDicts:
    """Tests for TypedDict definitions."""

    def test_run_result_structure(self):
        """Test RunResult TypedDict structure."""
        result: RunResult = {
            "passed": True,
            "measurements": {"voltage": 3.3},
            "data": {"serial": "ABC123"},
        }
        assert result["passed"] is True
        assert result["measurements"]["voltage"] == 3.3

    def test_execution_result_structure(self):
        """Test ExecutionResult TypedDict structure."""
        result: ExecutionResult = {
            "passed": True,
            "measurements": {},
            "steps": [],
            "data": {},
            "duration": 10.5,
            "error": None,
        }
        assert result["duration"] == 10.5

    def test_measurement_dict_structure(self):
        """Test MeasurementDict TypedDict structure."""
        m: MeasurementDict = {
            "name": "voltage",
            "value": 3.3,
            "unit": "V",
            "passed": True,
            "min": 3.0,
            "max": 3.6,
        }
        assert m["value"] == 3.3

    def test_step_result_dict_structure(self):
        """Test StepResultDict TypedDict structure."""
        step: StepResultDict = {
            "name": "test_step",
            "index": 1,
            "passed": True,
            "duration": 1.5,
            "measurements": {},
            "data": {},
            "error": None,
        }
        assert step["index"] == 1

"""Tests for ExecutionContext and Measurement classes."""

from datetime import datetime
from station_service_sdk.context import ExecutionContext, Measurement


class TestMeasurement:
    """Tests for Measurement dataclass."""

    def test_numeric_measurement_with_limits_pass(self):
        """Test numeric measurement within limits passes."""
        m = Measurement(
            name="voltage",
            value=3.3,
            unit="V",
            min_value=3.0,
            max_value=3.6,
        )
        assert m.passed is True

    def test_numeric_measurement_below_min_fails(self):
        """Test numeric measurement below min fails."""
        m = Measurement(
            name="voltage",
            value=2.8,
            unit="V",
            min_value=3.0,
            max_value=3.6,
        )
        assert m.passed is False

    def test_numeric_measurement_above_max_fails(self):
        """Test numeric measurement above max fails."""
        m = Measurement(
            name="voltage",
            value=4.0,
            unit="V",
            min_value=3.0,
            max_value=3.6,
        )
        assert m.passed is False

    def test_numeric_measurement_only_min(self):
        """Test numeric measurement with only min limit."""
        m = Measurement(name="temp", value=25, min_value=20)
        assert m.passed is True

        m = Measurement(name="temp", value=15, min_value=20)
        assert m.passed is False

    def test_numeric_measurement_only_max(self):
        """Test numeric measurement with only max limit."""
        m = Measurement(name="temp", value=25, max_value=30)
        assert m.passed is True

        m = Measurement(name="temp", value=35, max_value=30)
        assert m.passed is False

    def test_numeric_measurement_no_limits(self):
        """Test numeric measurement without limits has None passed."""
        m = Measurement(name="voltage", value=3.3)
        assert m.passed is None

    def test_boolean_measurement_true(self):
        """Test boolean True value sets passed to True."""
        m = Measurement(name="connected", value=True)
        assert m.passed is True

    def test_boolean_measurement_false(self):
        """Test boolean False value sets passed to False."""
        m = Measurement(name="connected", value=False)
        assert m.passed is False

    def test_string_measurement_no_auto_pass(self):
        """Test string value doesn't auto-calculate passed."""
        m = Measurement(name="serial", value="ABC123")
        assert m.passed is None

    def test_string_measurement_explicit_pass(self):
        """Test string value with explicit passed."""
        m = Measurement(name="serial", value="ABC123", passed=True)
        assert m.passed is True

    def test_limits_on_string_logged_warning(self, caplog):
        """Test that limits on non-numeric values log a warning."""
        import logging
        with caplog.at_level(logging.WARNING):
            Measurement(
                name="serial",
                value="ABC123",
                min_value=0,
                max_value=100,
            )
        assert "min/max limits ignored" in caplog.text

    def test_to_dict(self):
        """Test to_dict serialization for protocol output."""
        m = Measurement(
            name="voltage",
            value=3.3,
            unit="V",
            min_value=3.0,
            max_value=3.6,
            step_name="measure",
        )
        d = m.to_dict()
        assert d["name"] == "voltage"
        assert d["value"] == 3.3
        assert d["unit"] == "V"
        assert d["passed"] is True
        assert d["min"] == 3.0
        assert d["max"] == 3.6
        assert d["step"] == "measure"

    def test_to_storage_dict(self):
        """Test to_storage_dict for internal storage."""
        m = Measurement(
            name="voltage",
            value=3.3,
            unit="V",
            min_value=3.0,
            max_value=3.6,
        )
        d = m.to_storage_dict()
        assert d["value"] == 3.3
        assert d["unit"] == "V"
        assert d["passed"] is True
        assert d["min"] == 3.0
        assert d["max"] == 3.6
        assert "name" not in d  # Not in storage dict

    def test_from_dict(self):
        """Test from_dict deserialization."""
        data = {
            "value": 3.3,
            "unit": "V",
            "passed": True,
            "min": 3.0,
            "max": 3.6,
            "step": "measure",
        }
        m = Measurement.from_dict("voltage", data)
        assert m.name == "voltage"
        assert m.value == 3.3
        assert m.unit == "V"
        assert m.passed is True
        assert m.min_value == 3.0
        assert m.max_value == 3.6
        assert m.step_name == "measure"

    def test_timestamp_auto_set(self):
        """Test that timestamp is automatically set."""
        before = datetime.now()
        m = Measurement(name="test", value=1)
        after = datetime.now()
        assert m.timestamp is not None
        assert before <= m.timestamp <= after


class TestExecutionContext:
    """Tests for ExecutionContext dataclass."""

    def test_from_config(self, sample_config):
        """Test creating context from config dict."""
        ctx = ExecutionContext.from_config(sample_config)
        assert ctx.execution_id == "test-001"
        assert ctx.wip_id == "WIP-001"
        assert ctx.process_id == 1
        assert ctx.operator_id == 42
        assert ctx.lot_id == "LOT-2024"
        assert ctx.serial_number == "SN-12345"
        assert ctx.sequence_name == "test_sequence"
        assert ctx.sequence_version == "1.0.0"

    def test_from_config_hardware(self, sample_config):
        """Test hardware config is correctly parsed."""
        ctx = ExecutionContext.from_config(sample_config)
        assert "mcu" in ctx.hardware_config
        assert ctx.hardware_config["mcu"]["port"] == "/dev/ttyUSB0"

    def test_from_config_parameters(self, sample_config):
        """Test parameters are correctly parsed."""
        ctx = ExecutionContext.from_config(sample_config)
        assert ctx.parameters["voltage_min"] == 3.0
        assert ctx.parameters["timeout"] == 30

    def test_default_execution_id(self):
        """Test that execution_id is auto-generated."""
        ctx = ExecutionContext.from_config({})
        assert ctx.execution_id is not None
        assert len(ctx.execution_id) == 8

    def test_start_and_complete(self):
        """Test start and complete timing."""
        ctx = ExecutionContext()
        assert ctx.started_at is None
        assert ctx.completed_at is None

        ctx.start()
        assert ctx.started_at is not None
        assert ctx.completed_at is None

        ctx.complete()
        assert ctx.completed_at is not None
        assert ctx.completed_at >= ctx.started_at

    def test_duration_seconds(self):
        """Test duration calculation."""
        ctx = ExecutionContext()
        assert ctx.duration_seconds is None

        ctx.start()
        import time
        time.sleep(0.1)

        # During execution (not complete yet)
        assert ctx.duration_seconds is not None
        assert ctx.duration_seconds >= 0.1

        ctx.complete()
        # After completion
        final_duration = ctx.duration_seconds
        assert final_duration >= 0.1

    def test_to_dict(self, execution_context):
        """Test serialization to dict."""
        execution_context.start()
        execution_context.complete()
        d = execution_context.to_dict()

        assert d["execution_id"] == "test-001"
        assert d["wip_id"] == "WIP-001"
        assert d["started_at"] is not None
        assert d["completed_at"] is not None
        assert "hardware_config" in d
        assert "parameters" in d

    def test_dry_run_default(self):
        """Test dry_run defaults to False."""
        ctx = ExecutionContext()
        assert ctx.dry_run is False

    def test_hardware_instances_empty(self):
        """Test hardware instances dict starts empty."""
        ctx = ExecutionContext()
        assert ctx.hardware == {}

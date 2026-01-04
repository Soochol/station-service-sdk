"""Tests for SDK exception classes."""

from station_service_sdk.exceptions import (
    SequenceError,
    SetupError,
    TeardownError,
    StepError,
    SequenceTimeoutError,
    TimeoutError,  # Backward compatibility alias
    AbortError,
    TestFailure,
    HardwareConnectionError,
    ConnectionError,  # Backward compatibility alias
    ManifestError,
    ValidationError,
    DependencyError,
)


class TestSequenceError:
    """Tests for base SequenceError."""

    def test_basic_error(self):
        """Test basic error creation."""
        err = SequenceError("Something went wrong")
        assert err.message == "Something went wrong"
        assert err.code == "SEQUENCE_ERROR"
        assert err.details == {}

    def test_error_with_code_and_details(self):
        """Test error with custom code and details."""
        err = SequenceError(
            "Custom error",
            code="CUSTOM_CODE",
            details={"key": "value"},
        )
        assert err.code == "CUSTOM_CODE"
        assert err.details == {"key": "value"}

    def test_str_representation(self):
        """Test string representation."""
        err = SequenceError("Test message", code="TEST")
        assert str(err) == "[TEST] Test message"

    def test_str_with_details(self):
        """Test string representation with details."""
        err = SequenceError("Test", code="TEST", details={"x": 1})
        assert "Details:" in str(err)


class TestTimeoutError:
    """Tests for SequenceTimeoutError."""

    def test_timeout_with_seconds(self):
        """Test timeout error with timeout value."""
        err = SequenceTimeoutError(
            "Operation timed out",
            timeout_seconds=30,
            elapsed_seconds=35.5,
        )
        assert err.timeout_seconds == 30
        assert err.elapsed_seconds == 35.5
        assert err.code == "TIMEOUT_ERROR"

    def test_timeout_str_representation(self):
        """Test string representation includes timeout info."""
        err = SequenceTimeoutError(
            "Timeout",
            timeout_seconds=10,
            elapsed_seconds=12.5,
        )
        result = str(err)
        assert "timeout=10s" in result
        assert "elapsed=12.50s" in result

    def test_backward_compatibility_alias(self):
        """Test that TimeoutError is an alias for SequenceTimeoutError."""
        assert TimeoutError is SequenceTimeoutError


class TestConnectionError:
    """Tests for HardwareConnectionError."""

    def test_connection_error_with_host_port(self):
        """Test connection error with network details."""
        err = HardwareConnectionError(
            "Cannot connect",
            device="power_supply",
            host="192.168.1.100",
            port=5025,
        )
        assert err.device == "power_supply"
        assert err.host == "192.168.1.100"
        assert err.port == 5025
        assert err.code == "CONNECTION_ERROR"

    def test_backward_compatibility_alias(self):
        """Test that ConnectionError is an alias for HardwareConnectionError."""
        assert ConnectionError is HardwareConnectionError


class TestLifecycleErrors:
    """Tests for lifecycle-related errors."""

    def test_setup_error(self):
        """Test SetupError."""
        err = SetupError("Failed to initialize hardware")
        assert err.code == "SETUP_ERROR"
        assert isinstance(err, SequenceError)

    def test_teardown_error(self):
        """Test TeardownError."""
        err = TeardownError("Failed to cleanup")
        assert err.code == "TEARDOWN_ERROR"
        assert isinstance(err, SequenceError)

    def test_abort_error(self):
        """Test AbortError with default message."""
        err = AbortError()
        assert err.message == "Sequence aborted"
        assert err.code == "ABORT_ERROR"


class TestStepError:
    """Tests for step execution errors."""

    def test_step_error_with_name(self):
        """Test StepError with step name."""
        err = StepError("Step failed", step_name="measure_voltage")
        assert err.step_name == "measure_voltage"
        assert err.code == "STEP_ERROR"


class TestTestFailure:
    """Tests for test verification failures."""

    def test_failure_with_limits(self):
        """Test TestFailure with actual and limit values."""
        err = TestFailure(
            "Voltage out of range",
            step_name="verify_voltage",
            actual=2.8,
            limit=3.0,
            limit_type="min",
        )
        assert err.actual == 2.8
        assert err.limit == 3.0
        assert err.limit_type == "min"
        assert "(actual=2.8, limit=3.0)" in str(err)


class TestPackageErrors:
    """Tests for package-related errors."""

    def test_manifest_error(self):
        """Test ManifestError."""
        err = ManifestError(
            "Invalid manifest",
            package_name="test_sequence",
            manifest_path="/path/to/manifest.yaml",
        )
        assert err.package_name == "test_sequence"
        assert err.manifest_path == "/path/to/manifest.yaml"
        assert err.code == "MANIFEST_ERROR"

    def test_validation_error(self):
        """Test ValidationError."""
        err = ValidationError("Invalid value", field="voltage_min")
        assert err.field == "voltage_min"
        assert err.code == "VALIDATION_ERROR"

    def test_dependency_error(self):
        """Test DependencyError."""
        err = DependencyError("Missing package", dependency="numpy>=1.20")
        assert err.dependency == "numpy>=1.20"
        assert err.code == "DEPENDENCY_ERROR"

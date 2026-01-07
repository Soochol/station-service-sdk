"""Tests for OutputProtocol and JSON Lines output."""

import json
import pytest

from station_service_sdk import OutputProtocol, MessageType
from station_service_sdk.testing import create_test_context


class TestMessageType:
    """Tests for MessageType enum."""

    def test_all_types_defined(self) -> None:
        """Test all message types are defined."""
        expected = [
            "log", "step_start", "step_complete", "sequence_complete",
            "measurement", "error", "status", "input_request", "input_response"
        ]
        actual = [t.value for t in MessageType]
        assert sorted(actual) == sorted(expected)


class TestOutputProtocol:
    """Tests for OutputProtocol JSON Lines output."""

    @pytest.fixture
    def protocol(self):
        """Create protocol with test context."""
        ctx = create_test_context(execution_id="test-exec-001")
        return OutputProtocol(ctx)

    def test_emit_log(self, protocol, capsys) -> None:
        """Test log message emission."""
        protocol.log("info", "Test message", extra_field="value")

        captured = capsys.readouterr()
        line = json.loads(captured.out.strip())

        assert line["type"] == "log"
        assert line["execution_id"] == "test-exec-001"
        assert line["data"]["level"] == "info"
        assert line["data"]["message"] == "Test message"
        assert line["data"]["extra_field"] == "value"

    def test_emit_step_start(self, protocol, capsys) -> None:
        """Test step start emission."""
        protocol.step_start("measure_voltage", 1, 3, "Measuring voltage")

        captured = capsys.readouterr()
        line = json.loads(captured.out.strip())

        assert line["type"] == "step_start"
        assert line["data"]["step"] == "measure_voltage"
        assert line["data"]["index"] == 1
        assert line["data"]["total"] == 3
        assert line["data"]["description"] == "Measuring voltage"

    def test_emit_step_complete(self, protocol, capsys) -> None:
        """Test step complete emission."""
        protocol.step_complete(
            step_name="measure_voltage",
            index=1,
            passed=True,
            duration=1.5,
            measurements={"voltage": 3.3},
            error=None,
            data={"raw_adc": 1023},
        )

        captured = capsys.readouterr()
        line = json.loads(captured.out.strip())

        assert line["type"] == "step_complete"
        assert line["data"]["step"] == "measure_voltage"
        assert line["data"]["passed"] is True
        assert line["data"]["duration"] == 1.5
        assert line["data"]["measurements"] == {"voltage": 3.3}

    def test_emit_measurement(self, protocol, capsys) -> None:
        """Test measurement emission."""
        protocol.measurement(
            name="voltage",
            value=3.28,
            unit="V",
            passed=True,
            min_value=3.0,
            max_value=3.6,
            step_name="measure_voltage",
        )

        captured = capsys.readouterr()
        line = json.loads(captured.out.strip())

        assert line["type"] == "measurement"
        assert line["data"]["name"] == "voltage"
        assert line["data"]["value"] == 3.28
        assert line["data"]["unit"] == "V"
        assert line["data"]["passed"] is True
        assert line["data"]["min"] == 3.0
        assert line["data"]["max"] == 3.6

    def test_emit_error(self, protocol, capsys) -> None:
        """Test error emission."""
        protocol.error(
            code="HARDWARE_ERROR",
            message="Device disconnected",
            step="measure_voltage",
            recoverable=True,
        )

        captured = capsys.readouterr()
        line = json.loads(captured.out.strip())

        assert line["type"] == "error"
        assert line["data"]["code"] == "HARDWARE_ERROR"
        assert line["data"]["message"] == "Device disconnected"
        assert line["data"]["step"] == "measure_voltage"
        assert line["data"]["recoverable"] is True

    def test_emit_status(self, protocol, capsys) -> None:
        """Test status emission."""
        protocol.status(
            status="running",
            progress=50.0,
            current_step="measure_voltage",
            message="Halfway done",
        )

        captured = capsys.readouterr()
        line = json.loads(captured.out.strip())

        assert line["type"] == "status"
        assert line["data"]["status"] == "running"
        assert line["data"]["progress"] == 50.0
        assert line["data"]["current_step"] == "measure_voltage"

    def test_emit_sequence_complete(self, protocol, capsys) -> None:
        """Test sequence complete emission."""
        steps = [
            {"name": "step1", "passed": True},
            {"name": "step2", "passed": True},
        ]
        protocol.sequence_complete(
            overall_pass=True,
            duration=5.5,
            steps=steps,
            measurements={"voltage": 3.3},
            error=None,
        )

        captured = capsys.readouterr()
        line = json.loads(captured.out.strip())

        assert line["type"] == "sequence_complete"
        assert line["data"]["overall_pass"] is True
        assert line["data"]["duration"] == 5.5
        assert len(line["data"]["steps"]) == 2

    def test_timestamp_format(self, protocol, capsys) -> None:
        """Test timestamp is ISO format."""
        protocol.log("info", "Test")

        captured = capsys.readouterr()
        line = json.loads(captured.out.strip())

        # Should be ISO format datetime
        assert "T" in line["timestamp"]
        assert "-" in line["timestamp"]

    def test_unicode_handling(self, protocol, capsys) -> None:
        """Test Unicode characters are handled correctly."""
        protocol.log("info", "Korean: 한글 테스트")

        captured = capsys.readouterr()
        line = json.loads(captured.out.strip())

        assert "한글" in line["data"]["message"]

    def test_multiple_messages(self, protocol, capsys) -> None:
        """Test multiple messages output as JSON Lines."""
        protocol.log("info", "Message 1")
        protocol.log("info", "Message 2")
        protocol.log("info", "Message 3")

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")

        assert len(lines) == 3
        for line in lines:
            parsed = json.loads(line)
            assert parsed["type"] == "log"


class TestOutputProtocolFailedStep:
    """Tests for step with failure scenarios."""

    @pytest.fixture
    def protocol(self):
        """Create protocol with test context."""
        ctx = create_test_context(execution_id="test-exec-002")
        return OutputProtocol(ctx)

    def test_step_complete_with_error(self, protocol, capsys) -> None:
        """Test step complete with error message."""
        protocol.step_complete(
            step_name="failed_step",
            index=1,
            passed=False,
            duration=0.5,
            error="Hardware timeout",
        )

        captured = capsys.readouterr()
        line = json.loads(captured.out.strip())

        assert line["data"]["passed"] is False
        assert line["data"]["error"] == "Hardware timeout"

    def test_measurement_failed(self, protocol, capsys) -> None:
        """Test failed measurement."""
        protocol.measurement(
            name="voltage",
            value=2.5,  # Below minimum
            unit="V",
            passed=False,
            min_value=3.0,
            max_value=3.6,
        )

        captured = capsys.readouterr()
        line = json.loads(captured.out.strip())

        assert line["data"]["passed"] is False
        assert line["data"]["value"] == 2.5

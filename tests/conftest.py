"""Pytest fixtures for Station Service SDK tests."""

import pytest
from station_service_sdk.context import ExecutionContext, Measurement


@pytest.fixture
def sample_config() -> dict:
    """Sample configuration dictionary for testing."""
    return {
        "execution_id": "test-001",
        "wip_id": "WIP-001",
        "batch_id": "BATCH-001",
        "process_id": 1,
        "operator_id": 42,
        "lot_id": "LOT-2024",
        "serial_number": "SN-12345",
        "hardware": {
            "mcu": {"port": "/dev/ttyUSB0", "baud_rate": 115200},
            "power_supply": {"ip": "192.168.1.100", "channel": 1},
        },
        "parameters": {
            "voltage_min": 3.0,
            "voltage_max": 3.6,
            "timeout": 30,
        },
        "sequence_name": "test_sequence",
        "sequence_version": "1.0.0",
        "station_id": "STATION-01",
    }


@pytest.fixture
def execution_context(sample_config) -> ExecutionContext:
    """Create an ExecutionContext from sample config."""
    return ExecutionContext.from_config(sample_config)


@pytest.fixture
def sample_measurement() -> Measurement:
    """Create a sample numeric measurement."""
    return Measurement(
        name="voltage",
        value=3.3,
        unit="V",
        min_value=3.0,
        max_value=3.6,
        step_name="measure_voltage",
    )


@pytest.fixture
def failed_measurement() -> Measurement:
    """Create a measurement that fails limits."""
    return Measurement(
        name="current",
        value=2.5,
        unit="A",
        min_value=3.0,
        max_value=5.0,
        step_name="measure_current",
    )

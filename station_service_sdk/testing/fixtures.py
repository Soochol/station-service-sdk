"""Test fixtures for Station Service SDK.

Provides factory functions and pytest fixtures for creating
test contexts, manifests, and sequences.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from station_service_sdk.context import ExecutionContext
from station_service_sdk.manifest import (
    EntryPoint,
    HardwareDefinition,
    Modes,
    ParameterDefinition,
    SequenceManifest,
    StepDefinition,
)


def create_test_context(
    execution_id: str | None = None,
    wip_id: str | None = None,
    batch_id: str | None = None,
    sequence_name: str = "test_sequence",
    lot_id: str | None = None,
    serial_number: str | None = None,
    process_id: str | None = None,
    operator_id: str | None = None,
    station_id: str | None = None,
    hardware_config: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None,
) -> ExecutionContext:
    """Create an ExecutionContext for testing.

    Args:
        execution_id: Unique execution identifier (auto-generated if None)
        wip_id: Work-in-progress ID
        batch_id: Batch identifier
        sequence_name: Name of the sequence
        lot_id: LOT identifier
        serial_number: Serial number
        process_id: Process identifier
        operator_id: Operator identifier
        station_id: Station identifier
        hardware_config: Hardware configuration dictionary
        parameters: Sequence parameters

    Returns:
        Configured ExecutionContext for testing
    """
    return ExecutionContext(
        execution_id=execution_id or f"test-{uuid.uuid4().hex[:8]}",
        wip_id=wip_id or f"wip-{uuid.uuid4().hex[:8]}",
        batch_id=batch_id or f"batch-{uuid.uuid4().hex[:8]}",
        sequence_name=sequence_name,
        lot_id=lot_id or "TEST-LOT-001",
        serial_number=serial_number or "TEST-SN-001",
        process_id=process_id,
        operator_id=operator_id or "test-operator",
        station_id=station_id or "test-station",
        hardware_config=hardware_config or {},
        parameters=parameters or {},
        started_at=datetime.now(),
    )


def create_test_manifest(
    name: str = "test_sequence",
    version: str = "1.0.0",
    module: str = "test_module",
    class_name: str = "TestSequence",
    steps: list[dict[str, Any]] | None = None,
    hardware: dict[str, dict[str, Any]] | None = None,
    parameters: dict[str, dict[str, Any]] | None = None,
    modes: dict[str, bool] | None = None,
) -> SequenceManifest:
    """Create a SequenceManifest for testing.

    Args:
        name: Sequence name
        version: Sequence version
        module: Entry point module
        class_name: Entry point class name
        steps: List of step definitions
        hardware: Hardware definitions
        parameters: Parameter definitions
        modes: Execution modes

    Returns:
        Configured SequenceManifest for testing
    """
    # Default steps
    if steps is None:
        steps = [
            {"name": "init", "display_name": "Initialize", "order": 1, "timeout": 30.0},
            {"name": "test", "display_name": "Test", "order": 2, "timeout": 60.0},
            {"name": "cleanup", "display_name": "Cleanup", "order": 3, "timeout": 30.0},
        ]

    step_defs = [
        StepDefinition(
            name=s["name"],
            display_name=s.get("display_name", s["name"]),
            order=s.get("order", i + 1),
            timeout=s.get("timeout", 60.0),
            retry_count=s.get("retry_count", 0),
            cleanup_on_fail=s.get("cleanup_on_fail", True),
        )
        for i, s in enumerate(steps)
    ]

    # Hardware definitions
    hw_defs: dict[str, HardwareDefinition] = {}
    if hardware:
        for hw_id, hw_config in hardware.items():
            hw_defs[hw_id] = HardwareDefinition(
                display_name=hw_config.get("display_name", hw_id),
                driver=hw_config.get("driver", "mock_driver"),
                driver_class=hw_config.get("class", "MockDriver"),
                config_schema=hw_config.get("config_schema", {}),
            )

    # Parameter definitions
    param_defs: dict[str, ParameterDefinition] = {}
    if parameters:
        for param_name, param_config in parameters.items():
            param_defs[param_name] = ParameterDefinition(
                display_name=param_config.get("display_name", param_name),
                type=param_config.get("type", "string"),
                default=param_config.get("default"),
                required=param_config.get("required", False),
                min=param_config.get("min"),
                max=param_config.get("max"),
                unit=param_config.get("unit"),
                choices=param_config.get("choices"),
            )

    # Modes
    mode_config = modes or {}
    modes_obj = Modes(
        automatic=mode_config.get("automatic", True),
        manual=mode_config.get("manual", False),
        interactive=mode_config.get("interactive", False),
        cli=mode_config.get("cli", True),
    )

    return SequenceManifest(
        name=name,
        version=version,
        description=f"Test manifest for {name}",
        author="Test Author",
        entry_point=EntryPoint(module=module, class_name=class_name),
        modes=modes_obj,
        hardware=hw_defs,
        parameters=param_defs,
        steps=step_defs,
    )


# Pytest fixtures - these are available when testing module is imported


def pytest_fixtures() -> dict[str, Any]:
    """Get pytest fixture functions.

    Returns dictionary of fixture functions that can be registered
    with pytest.

    Returns:
        Dictionary mapping fixture names to functions
    """
    import pytest

    @pytest.fixture
    def execution_context() -> ExecutionContext:
        """Default execution context fixture."""
        return create_test_context()

    @pytest.fixture
    def test_manifest() -> SequenceManifest:
        """Default test manifest fixture."""
        return create_test_manifest()

    @pytest.fixture
    def captured_output():
        """Captured output fixture."""
        from station_service_sdk.testing.mocks import CapturedOutput

        return CapturedOutput()

    @pytest.fixture
    def mock_driver_builder():
        """Mock driver builder fixture."""
        from station_service_sdk.testing.mocks import MockDriverBuilder

        return MockDriverBuilder()

    @pytest.fixture
    def mock_registry():
        """Mock hardware registry fixture."""
        from station_service_sdk.testing.mocks import MockHardwareRegistry

        return MockHardwareRegistry()

    return {
        "execution_context": execution_context,
        "test_manifest": test_manifest,
        "captured_output": captured_output,
        "mock_driver_builder": mock_driver_builder,
        "mock_registry": mock_registry,
    }


# Conftest generation helper


def generate_conftest() -> str:
    """Generate conftest.py content for pytest fixtures.

    Returns:
        String content for conftest.py
    """
    return '''"""Pytest configuration for Station Service SDK tests."""

import pytest
from station_service_sdk.testing import (
    CapturedOutput,
    MockDriverBuilder,
    MockHardwareRegistry,
    create_test_context,
    create_test_manifest,
)


@pytest.fixture
def execution_context():
    """Default execution context for tests."""
    return create_test_context()


@pytest.fixture
def test_manifest():
    """Default test manifest."""
    return create_test_manifest()


@pytest.fixture
def captured_output():
    """Captured output strategy for testing."""
    return CapturedOutput()


@pytest.fixture
def mock_driver_builder():
    """Mock driver builder."""
    return MockDriverBuilder()


@pytest.fixture
def mock_registry():
    """Mock hardware registry."""
    return MockHardwareRegistry()


@pytest.fixture
async def sequence_runner(execution_context, captured_output):
    """Async sequence runner fixture."""
    from station_service_sdk import SequenceBase

    async def _run(
        sequence_class: type[SequenceBase],
        parameters: dict | None = None,
    ):
        sequence = sequence_class(
            context=execution_context,
            parameters=parameters or {},
            output_strategy=captured_output,
        )
        await sequence.execute()
        return captured_output.get_final_result()

    return _run
'''

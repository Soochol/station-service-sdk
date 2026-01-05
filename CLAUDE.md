# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Station Service SDK - Python SDK for building test sequences for manufacturing automation. Sequences communicate with Station Service via JSON Lines protocol over stdout.

## Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run single test file
pytest tests/test_manifest.py

# Run specific test
pytest tests/test_manifest.py::test_sequence_manifest_validation -v

# Type checking
mypy station_service_sdk/

# Validate manifest files
station-sdk validate manifest.yaml
station-sdk validate --dir sequences/

# Build and publish to PyPI
python -m build
twine upload dist/*
```

## Architecture

### Core Pattern: SequenceBase

All sequences inherit from `SequenceBase` and implement three lifecycle methods:

```python
class MySequence(SequenceBase):
    name = "my_sequence"
    version = "1.0.0"

    async def setup(self) -> None:      # Hardware init (auto-emitted as step 0)
    async def run(self) -> RunResult:    # Test execution (steps 1-N)
    async def teardown(self) -> None:    # Cleanup (auto-emitted as final step)
```

### Output Protocol (protocol.py)

JSON Lines to stdout. Message types: `log`, `step_start`, `step_complete`, `sequence_complete`, `measurement`, `error`, `status`, `input_request`.

### Key Modules

- **base.py**: `SequenceBase` - abstract base class with CLI entry point (`run_from_cli()`)
- **context.py**: `ExecutionContext`, `Measurement` - execution state and measurement data
- **manifest.py**: Pydantic models for `manifest.yaml` validation
- **exceptions.py**: Exception hierarchy (`SequenceError` → `SetupError`, `StepError`, `HardwareError`, etc.)
- **loader.py**: `SequenceLoader` - discovers and loads sequence packages
- **simulator.py**: `SequenceSimulator`, `MockHardware` - testing utilities
- **interactive.py**: `InteractiveSimulator` - step-by-step simulation
- **manual_executor.py**: `ManualSequenceExecutor` - manual mode execution
- **decorators.py**: `@step`, `@parameter` decorators for legacy pattern support

### emit_* Methods (in SequenceBase)

- `emit_log(level, message)` - log output
- `emit_step_start(name, index, total, description)` - step begins
- `emit_step_complete(name, index, passed, duration)` - step ends
- `emit_measurement(name, value, unit, min_value, max_value)` - record measurement

### manifest.yaml Structure

Required for each sequence package:
- `name`, `version`, `entry_point` (module/class)
- `modes`: automatic/manual/cli support flags
- `hardware`: driver definitions with `driver` and `class` fields (both required if hardware section exists)
- `parameters`: configurable parameters with types and defaults
- `steps`: step definitions with order and timeout

## Key Conventions

- Lifecycle steps (setup/teardown) are auto-emitted by SDK - don't emit manually
- Step indices in `run()` start at 1; SDK adjusts total to include setup/teardown
- `RunResult` TypedDict requires `passed: bool`, optional `measurements` and `data` dicts
- Hardware section in manifest requires both `driver` and `class` fields - omit section entirely if no hardware needed
- Use `station-sdk validate` before uploading sequences

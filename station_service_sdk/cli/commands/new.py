"""New sequence creation command."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Templates for different sequence types
BASIC_TEMPLATE = '''"""{{name}} - Basic test sequence."""

from station_service_sdk import SequenceBase, RunResult


class {{class_name}}(SequenceBase):
    """Basic test sequence implementation."""

    name = "{{name}}"
    version = "1.0.0"
    description = "{{description}}"

    async def setup(self) -> None:
        """Initialize test environment."""
        self.emit_log("info", "Setting up {{name}}")

    async def run(self) -> RunResult:
        """Execute test sequence."""
        measurements = {}

        # Step 1: Initialize
        self.emit_step_start("initialize", 1, 2, "Initializing test")
        # Add your initialization code here
        self.emit_step_complete("initialize", 1, True, 0.1)

        # Step 2: Test
        self.emit_step_start("test", 2, 2, "Running test")
        # Add your test code here
        test_value = 1.0
        self.emit_measurement("test_value", test_value, "unit", min_value=0.0, max_value=2.0)
        measurements["test_value"] = test_value
        self.emit_step_complete("test", 2, True, 0.2)

        return {
            "passed": True,
            "measurements": measurements,
            "data": {},
        }

    async def teardown(self) -> None:
        """Clean up test environment."""
        self.emit_log("info", "Tearing down {{name}}")
'''

HARDWARE_TEMPLATE = '''"""{{name}} - Hardware test sequence."""

from station_service_sdk import SequenceBase, RunResult


class {{class_name}}(SequenceBase):
    """Hardware test sequence with driver integration."""

    name = "{{name}}"
    version = "1.0.0"
    description = "{{description}}"

    async def setup(self) -> None:
        """Initialize hardware connections."""
        self.emit_log("info", "Connecting to hardware")

        # Get hardware driver from context
        # self.device = self.hardware.get("device")
        # await self.device.connect()

    async def run(self) -> RunResult:
        """Execute hardware test sequence."""
        measurements = {}

        # Step 1: Initialize hardware
        self.emit_step_start("hw_init", 1, 3, "Initializing hardware")
        # await self.device.initialize()
        self.emit_step_complete("hw_init", 1, True, 0.5)

        # Step 2: Perform measurement
        self.emit_step_start("measure", 2, 3, "Performing measurement")
        # value = await self.device.measure()
        value = 3.3  # Placeholder
        self.emit_measurement("voltage", value, "V", min_value=3.0, max_value=3.6)
        measurements["voltage"] = value
        passed = 3.0 <= value <= 3.6
        self.emit_step_complete("measure", 2, passed, 1.0)

        # Step 3: Verify result
        self.emit_step_start("verify", 3, 3, "Verifying result")
        # verification_result = await self.device.verify()
        self.emit_step_complete("verify", 3, True, 0.5)

        return {
            "passed": passed,
            "measurements": measurements,
            "data": {"voltage": value},
        }

    async def teardown(self) -> None:
        """Disconnect hardware."""
        self.emit_log("info", "Disconnecting hardware")
        # await self.device.disconnect()
'''

MULTI_STEP_TEMPLATE = '''"""{{name}} - Multi-step test sequence."""

from station_service_sdk import SequenceBase, RunResult


class {{class_name}}(SequenceBase):
    """Multi-step test sequence with comprehensive testing."""

    name = "{{name}}"
    version = "1.0.0"
    description = "{{description}}"

    async def setup(self) -> None:
        """Initialize test environment and resources."""
        self.emit_log("info", "Setting up multi-step sequence")
        self.test_data = {}

    async def run(self) -> RunResult:
        """Execute multi-step test sequence."""
        measurements = {}
        all_passed = True

        steps = [
            ("initialization", "Initialize system"),
            ("connectivity", "Check connectivity"),
            ("calibration", "Perform calibration"),
            ("measurement", "Take measurements"),
            ("validation", "Validate results"),
        ]

        total_steps = len(steps)

        for i, (step_name, description) in enumerate(steps, start=1):
            self.emit_step_start(step_name, i, total_steps, description)

            try:
                # Call step method dynamically
                step_method = getattr(self, f"_step_{step_name}", None)
                if step_method:
                    step_result = await step_method(measurements)
                    passed = step_result.get("passed", True)
                else:
                    passed = True

                self.emit_step_complete(step_name, i, passed, 0.5)
                all_passed = all_passed and passed

            except Exception as e:
                self.emit_step_complete(step_name, i, False, 0.5, error=str(e))
                all_passed = False
                break

        return {
            "passed": all_passed,
            "measurements": measurements,
            "data": self.test_data,
        }

    async def _step_initialization(self, measurements: dict) -> dict:
        """Initialize step."""
        self.emit_log("debug", "Running initialization")
        return {"passed": True}

    async def _step_connectivity(self, measurements: dict) -> dict:
        """Connectivity check step."""
        self.emit_log("debug", "Checking connectivity")
        return {"passed": True}

    async def _step_calibration(self, measurements: dict) -> dict:
        """Calibration step."""
        self.emit_log("debug", "Performing calibration")
        return {"passed": True}

    async def _step_measurement(self, measurements: dict) -> dict:
        """Measurement step."""
        self.emit_log("debug", "Taking measurements")
        measurements["value1"] = 1.0
        measurements["value2"] = 2.0
        self.emit_measurement("value1", 1.0, "unit")
        self.emit_measurement("value2", 2.0, "unit")
        return {"passed": True}

    async def _step_validation(self, measurements: dict) -> dict:
        """Validation step."""
        self.emit_log("debug", "Validating results")
        return {"passed": True}

    async def teardown(self) -> None:
        """Clean up resources."""
        self.emit_log("info", "Tearing down multi-step sequence")
'''

MANIFEST_TEMPLATE = '''name: {{name}}
version: "1.0.0"
description: "{{description}}"
author: "{{author}}"

entry_point:
  module: {{module_name}}
  class: {{class_name}}

modes:
  automatic: true
  manual: false
  interactive: false
  cli: true

# Uncomment to add hardware definitions
# hardware:
#   device:
#     display_name: "Test Device"
#     driver: "drivers.device"
#     class: "DeviceDriver"
#     config_schema:
#       port:
#         type: string
#         required: true
#         default: "/dev/ttyUSB0"

parameters:
  timeout:
    display_name: "Timeout"
    type: float
    default: 60.0
    min: 1.0
    max: 300.0
    unit: "s"

steps:
  - name: initialize
    display_name: "Initialize"
    order: 1
    timeout: 30.0
  - name: test
    display_name: "Test"
    order: 2
    timeout: 60.0
'''

PYPROJECT_TEMPLATE = '''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{{package_name}}"
version = "1.0.0"
description = "{{description}}"
requires-python = ">=3.11"

dependencies = [
    "station-service-sdk>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
]

[tool.hatch.build.targets.wheel]
packages = ["{{module_name}}"]
'''

README_TEMPLATE = '''# {{name}}

{{description}}

## Installation

```bash
pip install -e .
```

## Usage

### Validate the sequence

```bash
station-sdk validate .
```

### Run in dry-run mode

```bash
station-sdk run . --dry-run
```

### Debug interactively

```bash
station-sdk debug . --step-by-step
```

## Development

```bash
pip install -e ".[dev]"
pytest
```
'''


def create_sequence(name: str, template: str, output_dir: Path) -> Path:
    """Create a new sequence package.

    Args:
        name: Sequence name
        template: Template type (basic, hardware, multi-step)
        output_dir: Output directory

    Returns:
        Path to created package

    Raises:
        ValueError: If invalid template or name
        FileExistsError: If package already exists
    """
    # Validate name
    if not name.replace("-", "_").replace("_", "").isalnum():
        raise ValueError(f"Invalid sequence name: {name}")

    # Convert to valid Python identifiers
    module_name = name.replace("-", "_").lower()
    class_name = "".join(word.capitalize() for word in name.replace("-", "_").split("_"))
    if not class_name.endswith("Sequence"):
        class_name += "Sequence"

    package_name = name.lower().replace("_", "-")

    # Create package directory
    package_dir = output_dir / package_name
    if package_dir.exists():
        raise FileExistsError(f"Directory already exists: {package_dir}")

    package_dir.mkdir(parents=True)

    # Select template
    templates = {
        "basic": BASIC_TEMPLATE,
        "hardware": HARDWARE_TEMPLATE,
        "multi-step": MULTI_STEP_TEMPLATE,
    }

    sequence_template = templates.get(template, BASIC_TEMPLATE)

    # Template variables
    vars_dict: dict[str, Any] = {
        "name": name,
        "module_name": module_name,
        "class_name": class_name,
        "package_name": package_name,
        "description": f"Test sequence for {name}",
        "author": "Developer",
    }

    def render(template_str: str) -> str:
        result = template_str
        for key, value in vars_dict.items():
            result = result.replace("{{" + key + "}}", str(value))
        return result

    # Create module directory
    module_dir = package_dir / module_name
    module_dir.mkdir()

    # Write sequence file
    sequence_file = module_dir / "__init__.py"
    sequence_file.write_text(render(sequence_template))

    # Write manifest
    manifest_file = package_dir / "manifest.yaml"
    manifest_file.write_text(render(MANIFEST_TEMPLATE))

    # Write pyproject.toml
    pyproject_file = package_dir / "pyproject.toml"
    pyproject_file.write_text(render(PYPROJECT_TEMPLATE))

    # Write README
    readme_file = package_dir / "README.md"
    readme_file.write_text(render(README_TEMPLATE))

    # Create tests directory
    tests_dir = package_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "__init__.py").write_text("")
    (tests_dir / f"test_{module_name}.py").write_text(f'''"""Tests for {name}."""

import pytest
from station_service_sdk.testing import (
    create_test_context,
    CapturedOutput,
    assert_sequence_passed,
)
from {module_name} import {class_name}


@pytest.mark.asyncio
async def test_sequence_passes():
    """Test that sequence completes successfully."""
    context = create_test_context(sequence_name="{name}")
    output = CapturedOutput()

    sequence = {class_name}(
        context=context,
        output_strategy=output,
    )

    await sequence.execute()

    assert_sequence_passed(output)
''')

    return package_dir

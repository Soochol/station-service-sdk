"""Validate sequence command."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ValidationResult:
    """Result of sequence validation.

    Attributes:
        valid: Whether validation passed
        errors: List of error messages
        warnings: List of warning messages
    """

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_sequence(package_path: Path) -> ValidationResult:
    """Validate a sequence package.

    Args:
        package_path: Path to sequence package

    Returns:
        ValidationResult with errors and warnings
    """
    result = ValidationResult()

    # Check manifest exists
    manifest_path = package_path / "manifest.yaml"
    if not manifest_path.exists():
        result.valid = False
        result.errors.append(f"manifest.yaml not found in {package_path}")
        return result

    # Parse manifest
    try:
        with open(manifest_path) as f:
            manifest_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result.valid = False
        result.errors.append(f"Invalid YAML in manifest: {e}")
        return result

    # Validate required fields
    required_fields = ["name", "version", "entry_point"]
    for field_name in required_fields:
        if field_name not in manifest_data:
            result.valid = False
            result.errors.append(f"Missing required field: {field_name}")

    # Validate entry point
    if "entry_point" in manifest_data:
        entry_point = manifest_data["entry_point"]
        if not isinstance(entry_point, dict):
            result.valid = False
            result.errors.append("entry_point must be a mapping")
        else:
            if "module" not in entry_point:
                result.valid = False
                result.errors.append("entry_point.module is required")
            if "class" not in entry_point:
                result.valid = False
                result.errors.append("entry_point.class is required")

            # Try to find the module
            if "module" in entry_point:
                module_name = entry_point["module"]
                module_path = package_path / module_name
                init_path = module_path / "__init__.py"
                if not module_path.exists():
                    result.warnings.append(f"Module directory not found: {module_name}")
                elif not init_path.exists():
                    result.warnings.append(f"Module __init__.py not found: {module_name}")

    # Validate steps
    if "steps" in manifest_data:
        steps = manifest_data["steps"]
        if not isinstance(steps, list):
            result.valid = False
            result.errors.append("steps must be a list")
        else:
            step_names = set()
            step_orders = set()
            for i, step in enumerate(steps):
                if not isinstance(step, dict):
                    result.valid = False
                    result.errors.append(f"Step {i} must be a mapping")
                    continue

                if "name" not in step:
                    result.valid = False
                    result.errors.append(f"Step {i} missing name")
                else:
                    name = step["name"]
                    if name in step_names:
                        result.valid = False
                        result.errors.append(f"Duplicate step name: {name}")
                    step_names.add(name)

                if "order" in step:
                    order = step["order"]
                    if order in step_orders:
                        result.warnings.append(f"Duplicate step order: {order}")
                    step_orders.add(order)

    # Validate hardware definitions
    if "hardware" in manifest_data:
        hardware = manifest_data["hardware"]
        if not isinstance(hardware, dict):
            result.valid = False
            result.errors.append("hardware must be a mapping")
        else:
            for hw_id, hw_def in hardware.items():
                if not isinstance(hw_def, dict):
                    result.valid = False
                    result.errors.append(f"Hardware {hw_id} must be a mapping")
                    continue

                if "driver" not in hw_def:
                    result.valid = False
                    result.errors.append(f"Hardware {hw_id} missing driver")
                if "class" not in hw_def:
                    result.valid = False
                    result.errors.append(f"Hardware {hw_id} missing class")

    # Validate parameters
    if "parameters" in manifest_data:
        parameters = manifest_data["parameters"]
        if not isinstance(parameters, dict):
            result.valid = False
            result.errors.append("parameters must be a mapping")
        else:
            valid_types = {"string", "integer", "float", "boolean"}
            for param_name, param_def in parameters.items():
                if not isinstance(param_def, dict):
                    result.valid = False
                    result.errors.append(f"Parameter {param_name} must be a mapping")
                    continue

                if "type" in param_def:
                    param_type = param_def["type"]
                    if param_type not in valid_types:
                        result.warnings.append(
                            f"Parameter {param_name} has unknown type: {param_type}"
                        )

                # Validate min/max for numeric types
                if param_def.get("type") in ("integer", "float"):
                    min_val = param_def.get("min")
                    max_val = param_def.get("max")
                    default_val = param_def.get("default")

                    if min_val is not None and max_val is not None:
                        if min_val > max_val:
                            result.valid = False
                            result.errors.append(
                                f"Parameter {param_name}: min > max"
                            )

                    if default_val is not None:
                        if min_val is not None and default_val < min_val:
                            result.warnings.append(
                                f"Parameter {param_name}: default < min"
                            )
                        if max_val is not None and default_val > max_val:
                            result.warnings.append(
                                f"Parameter {param_name}: default > max"
                            )

    # Validate modes
    if "modes" in manifest_data:
        modes = manifest_data["modes"]
        if not isinstance(modes, dict):
            result.valid = False
            result.errors.append("modes must be a mapping")
        else:
            valid_modes = {"automatic", "manual", "interactive", "cli"}
            for mode_name, mode_value in modes.items():
                if mode_name not in valid_modes:
                    result.warnings.append(f"Unknown mode: {mode_name}")
                if not isinstance(mode_value, bool):
                    result.warnings.append(
                        f"Mode {mode_name} should be boolean"
                    )

    # Check for pyproject.toml
    pyproject_path = package_path / "pyproject.toml"
    if not pyproject_path.exists():
        result.warnings.append("pyproject.toml not found")

    return result

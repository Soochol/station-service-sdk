"""
Manifest validation utilities for Station Service SDK.

Provides validation functionality for manifest.yaml files
before uploading sequence packages.
"""

import sys
from pathlib import Path
from typing import List, Tuple

import yaml
from pydantic import ValidationError

from .manifest import SequenceManifest


class Colors:
    """ANSI color codes for terminal output."""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def _print_success(msg: str) -> None:
    print(f"{Colors.GREEN}\u2713{Colors.RESET} {msg}")


def _print_error(msg: str) -> None:
    print(f"{Colors.RED}\u2717{Colors.RESET} {msg}")


def _print_warning(msg: str) -> None:
    print(f"{Colors.YELLOW}\u26a0{Colors.RESET} {msg}")


def _print_info(msg: str) -> None:
    print(f"{Colors.CYAN}\u2139{Colors.RESET} {msg}")


def _print_header(msg: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.BLUE}{msg}{Colors.RESET}")


def validate_manifest(manifest_path: Path, check_files: bool = True) -> bool:
    """
    Validate a manifest.yaml file.

    Args:
        manifest_path: Path to the manifest.yaml file
        check_files: Whether to check if referenced files exist

    Returns:
        True if validation passed, False otherwise
    """
    errors: List[str] = []
    warnings: List[str] = []

    _print_header(f"Validating: {manifest_path}")

    # 1. Check file exists
    if not manifest_path.exists():
        _print_error(f"File not found: {manifest_path}")
        return False

    # 2. Parse YAML
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        _print_error(f"YAML parsing error: {e}")
        return False

    _print_success("YAML syntax valid")

    # 3. Pydantic validation
    try:
        manifest = SequenceManifest(**data)
        _print_success("Schema validation passed")
    except ValidationError as e:
        _print_error("Schema validation failed:")
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            msg = err["msg"]
            print(f"   {Colors.RED}\u2192{Colors.RESET} {loc}: {msg}")
        return False

    # 4. Additional validations
    package_dir = manifest_path.parent

    # 4.1 Check entry point module file exists
    if check_files:
        module_file = package_dir / f"{manifest.entry_point.module}.py"
        if module_file.exists():
            _print_success(f"Entry point module exists: {manifest.entry_point.module}.py")

            # Check class exists in file
            content = module_file.read_text()
            class_name = manifest.entry_point.class_name
            if f"class {class_name}" in content:
                _print_success(f"Entry point class found: {class_name}")
            else:
                errors.append(
                    f"Entry point class '{class_name}' not found in {module_file.name}"
                )
        else:
            errors.append(f"Entry point module not found: {module_file}")

    # 4.2 Validate steps
    if manifest.steps:
        # Check for duplicate order values
        orders = [s.order for s in manifest.steps]
        if len(orders) != len(set(orders)):
            errors.append("Duplicate step order values found")
        else:
            _print_success(f"Steps defined: {len(manifest.steps)} steps")

        # Show lifecycle steps
        lifecycle_steps = [s for s in manifest.steps if hasattr(s, "lifecycle")]
        if lifecycle_steps:
            _print_info(f"Steps count: {len(manifest.steps)}")
    else:
        warnings.append("No steps defined")

    # 4.3 Validate parameters
    if manifest.parameters:
        _print_success(f"Parameters defined: {len(manifest.parameters)}")

    # 4.4 Validate hardware (if present)
    if manifest.hardware:
        _print_success(f"Hardware defined: {len(manifest.hardware)}")

        if check_files:
            for hw_id, hw in manifest.hardware.items():
                # Check driver file exists
                driver_parts = hw.driver.split(".")
                if len(driver_parts) > 1:
                    driver_file = package_dir / "/".join(driver_parts[:-1]) / f"{driver_parts[-1]}.py"
                else:
                    driver_file = package_dir / f"{hw.driver}.py"

                if not driver_file.exists():
                    # Try alternative path
                    driver_file = package_dir / f"{hw.driver.replace('.', '/')}.py"

                if driver_file.exists():
                    _print_success(f"Hardware driver exists: {hw.driver}")
                else:
                    warnings.append(
                        f"Hardware driver not found: {hw.driver} (expected at {driver_file})"
                    )

    # 4.5 Show dependencies
    if manifest.dependencies.python:
        _print_info(f"Python dependencies: {', '.join(manifest.dependencies.python)}")

    # 4.6 Show modes
    if manifest.modes:
        modes = []
        if manifest.modes.automatic:
            modes.append("automatic")
        if manifest.modes.manual:
            modes.append("manual")
        if manifest.modes.cli:
            modes.append("cli")
        if modes:
            _print_info(f"Execution modes: {', '.join(modes)}")

    # Print results
    _print_header("Validation Result")

    if warnings:
        for w in warnings:
            _print_warning(w)

    if errors:
        for e in errors:
            _print_error(e)
        print(f"\n{Colors.RED}{Colors.BOLD}FAILED{Colors.RESET} - {len(errors)} error(s)")
        return False

    print(f"\n{Colors.GREEN}{Colors.BOLD}PASSED{Colors.RESET}")
    _print_info(f"Sequence: {manifest.name} v{manifest.version}")
    if manifest.description:
        _print_info(f"Description: {manifest.description}")

    return True


def validate_directory(dir_path: Path, check_files: bool = True) -> bool:
    """
    Validate all manifest.yaml files in a directory.

    Args:
        dir_path: Directory to search for manifest.yaml files
        check_files: Whether to check if referenced files exist

    Returns:
        True if all validations passed, False otherwise
    """
    manifest_files = list(dir_path.glob("**/manifest.yaml"))

    if not manifest_files:
        _print_error(f"No manifest.yaml files found in {dir_path}")
        return False

    _print_info(f"Found {len(manifest_files)} manifest file(s)")

    results: List[Tuple[Path, bool]] = []
    for mf in manifest_files:
        result = validate_manifest(mf, check_files)
        results.append((mf, result))

    # Summary
    _print_header("Summary")
    passed = sum(1 for _, r in results if r)
    failed = len(results) - passed

    for mf, result in results:
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if result else f"{Colors.RED}FAIL{Colors.RESET}"
        try:
            rel_path = mf.relative_to(dir_path)
        except ValueError:
            rel_path = mf
        print(f"  [{status}] {rel_path}")

    print(f"\nTotal: {passed} passed, {failed} failed")

    return failed == 0

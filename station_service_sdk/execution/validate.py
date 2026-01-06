"""
Manifest validation utilities for Station Service SDK.

Provides validation functionality for manifest.yaml files
before uploading sequence packages.
"""

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Tuple

import yaml
from pydantic import ValidationError

from .manifest import SequenceManifest


@dataclass
class StepValidationResult:
    """Result of step name validation between manifest and sequence."""

    passed: bool
    manifest_steps: Set[str] = field(default_factory=set)
    sequence_steps: Set[str] = field(default_factory=set)
    missing_in_manifest: Set[str] = field(default_factory=set)
    missing_in_sequence: Set[str] = field(default_factory=set)
    dynamic_warnings: List[str] = field(default_factory=list)


class EmitStepVisitor(ast.NodeVisitor):
    """AST visitor to extract emit_step_start call arguments."""

    def __init__(self) -> None:
        self.literal_names: Set[str] = set()
        self.dynamic_warnings: List[str] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        """Visit function call nodes to find emit_step_start calls."""
        # Check if this is a method call on self
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("emit_step_start", "emit_step_complete"):
                self._extract_step_name(node)

        # Continue visiting child nodes
        self.generic_visit(node)

    def _extract_step_name(self, node: ast.Call) -> None:
        """Extract step name from emit_step_start/emit_step_complete call."""
        if not node.args:
            return

        first_arg = node.args[0]

        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            # Literal string: self.emit_step_start("step_name", ...)
            self.literal_names.add(first_arg.value)
        elif isinstance(first_arg, ast.JoinedStr):
            # f-string: self.emit_step_start(f"step_{num}", ...)
            self.dynamic_warnings.append(
                f"Line {node.lineno}: f-string step name detected"
            )
        elif isinstance(first_arg, ast.Name):
            # Variable: self.emit_step_start(step_name, ...)
            self.dynamic_warnings.append(
                f"Line {node.lineno}: variable step name '{first_arg.id}'"
            )
        elif isinstance(first_arg, ast.BinOp):
            # String concatenation: self.emit_step_start("step_" + suffix, ...)
            self.dynamic_warnings.append(
                f"Line {node.lineno}: dynamic step name (string concatenation)"
            )
        elif isinstance(first_arg, ast.Subscript):
            # Dict/list access: self.emit_step_start(steps[i], ...)
            self.dynamic_warnings.append(
                f"Line {node.lineno}: dynamic step name (subscript access)"
            )
        else:
            # Other dynamic patterns
            self.dynamic_warnings.append(
                f"Line {node.lineno}: dynamic step name (cannot analyze statically)"
            )


def extract_emit_step_names(sequence_path: Path) -> Tuple[Set[str], List[str]]:
    """
    Extract step names from emit_step_start/emit_step_complete calls in sequence file.

    Uses AST parsing to find all emit_step_start and emit_step_complete calls
    and extracts the step name argument.

    Args:
        sequence_path: Path to the sequence Python file

    Returns:
        Tuple of (literal_step_names, dynamic_warnings)
        - literal_step_names: Set of step names that are literal strings
        - dynamic_warnings: List of warnings for dynamic step names that cannot be analyzed
    """
    try:
        source = sequence_path.read_text(encoding="utf-8")
    except (OSError, IOError) as e:
        return set(), [f"Could not read file: {e}"]

    try:
        tree = ast.parse(source, filename=str(sequence_path))
    except SyntaxError as e:
        return set(), [f"Syntax error in file: {e}"]

    visitor = EmitStepVisitor()
    visitor.visit(tree)

    return visitor.literal_names, visitor.dynamic_warnings


def validate_step_names(
    manifest_steps: List[str],
    sequence_path: Path,
) -> StepValidationResult:
    """
    Validate step names match between manifest and sequence file.

    Compares step names defined in manifest.yaml with step names
    emitted via emit_step_start() in the sequence file.

    Args:
        manifest_steps: List of step names from manifest.yaml
        sequence_path: Path to the sequence Python file

    Returns:
        StepValidationResult with validation details
    """
    # Lifecycle steps are auto-emitted by SDK, exclude from validation
    lifecycle_steps = {"setup", "teardown"}

    manifest_set = set(manifest_steps) - lifecycle_steps
    sequence_names, dynamic_warnings = extract_emit_step_names(sequence_path)
    sequence_set = sequence_names - lifecycle_steps

    # Find mismatches
    missing_in_manifest = sequence_set - manifest_set
    missing_in_sequence = manifest_set - sequence_set

    # Validation passes if no steps are emitted that aren't in manifest
    # (missing_in_sequence is just a warning, not an error)
    passed = len(missing_in_manifest) == 0

    return StepValidationResult(
        passed=passed,
        manifest_steps=manifest_set,
        sequence_steps=sequence_set,
        missing_in_manifest=missing_in_manifest,
        missing_in_sequence=missing_in_sequence,
        dynamic_warnings=dynamic_warnings,
    )


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


def validate_manifest(
    manifest_path: Path,
    check_files: bool = True,
    check_steps: bool = True,
) -> bool:
    """
    Validate a manifest.yaml file.

    Args:
        manifest_path: Path to the manifest.yaml file
        check_files: Whether to check if referenced files exist
        check_steps: Whether to validate step names match between manifest and sequence

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

    # 4.2.1 Validate step names match between manifest and sequence
    if check_steps and check_files and manifest.steps:
        module_file = package_dir / f"{manifest.entry_point.module}.py"
        if module_file.exists():
            manifest_step_names = [s.name for s in manifest.steps]
            step_result = validate_step_names(manifest_step_names, module_file)

            if step_result.dynamic_warnings:
                _print_warning("Dynamic step names detected - cannot fully validate:")
                for warn in step_result.dynamic_warnings:
                    print(f"   {Colors.YELLOW}→{Colors.RESET} {warn}")
                print(
                    f"   {Colors.CYAN}Hint:{Colors.RESET} "
                    "동적 step 이름 사용 시 manifest의 steps와 일치하는지 수동 확인 필요"
                )

            if step_result.passed:
                if step_result.sequence_steps:
                    _print_success("Step names match between manifest and sequence")
                    if step_result.missing_in_sequence:
                        # Steps defined in manifest but not emitted (warning only)
                        _print_warning(
                            f"Steps defined but not emitted: "
                            f"{', '.join(sorted(step_result.missing_in_sequence))}"
                        )
            else:
                _print_error("Step name mismatch detected:")
                for step_name in sorted(step_result.missing_in_manifest):
                    print(
                        f"   {Colors.RED}→{Colors.RESET} "
                        f'"{step_name}" emitted in sequence but not defined in manifest'
                    )
                for step_name in sorted(step_result.missing_in_sequence):
                    print(
                        f"   {Colors.YELLOW}→{Colors.RESET} "
                        f'"{step_name}" defined in manifest but not used in sequence'
                    )
                print(
                    f"\n   {Colors.CYAN}Hint:{Colors.RESET} "
                    "manifest.yaml의 steps에 실제 emit하는 step 이름을 정의하세요."
                )
                errors.append("Step names do not match between manifest and sequence")

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

    # 4.5 Validate dependencies (manifest.yaml)
    if manifest.dependencies.python:
        from .dependencies import get_missing_packages

        deps = manifest.dependencies.python
        missing = get_missing_packages(deps)

        if missing:
            _print_warning(f"Missing packages (manifest): {', '.join(missing)}")
            _print_info(f"Run: pip install {' '.join(missing)}")
            warnings.append(f"Missing dependencies: {', '.join(missing)}")
        else:
            _print_success(f"All manifest dependencies installed: {', '.join(deps)}")

    # 4.5.1 Validate dependencies (pyproject.toml)
    pyproject_path = manifest_path.parent / "pyproject.toml"
    if pyproject_path.exists():
        from .dependencies import parse_pyproject_dependencies, get_missing_packages

        try:
            pyproject_deps = parse_pyproject_dependencies(pyproject_path)
            if pyproject_deps:
                missing = get_missing_packages(pyproject_deps)
                if missing:
                    _print_warning(f"Missing packages (pyproject.toml): {', '.join(missing)}")
                    _print_info(f"Run: pip install {' '.join(missing)}")
                    warnings.append(f"Missing pyproject.toml dependencies: {', '.join(missing)}")
                else:
                    _print_success(f"All pyproject.toml dependencies installed: {', '.join(pyproject_deps)}")
        except ValueError as e:
            _print_warning(f"Cannot parse pyproject.toml: {e}")
        except Exception as e:
            _print_warning(f"Error reading pyproject.toml: {e}")
    else:
        _print_info("No pyproject.toml found (optional)")

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
        for error_msg in errors:
            _print_error(error_msg)
        print(f"\n{Colors.RED}{Colors.BOLD}FAILED{Colors.RESET} - {len(errors)} error(s)")
        return False

    print(f"\n{Colors.GREEN}{Colors.BOLD}PASSED{Colors.RESET}")
    _print_info(f"Sequence: {manifest.name} v{manifest.version}")
    if manifest.description:
        _print_info(f"Description: {manifest.description}")

    return True


def validate_directory(
    dir_path: Path,
    check_files: bool = True,
    check_steps: bool = True,
) -> bool:
    """
    Validate all manifest.yaml files in a directory.

    Args:
        dir_path: Directory to search for manifest.yaml files
        check_files: Whether to check if referenced files exist
        check_steps: Whether to validate step names match between manifest and sequence

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
        result = validate_manifest(mf, check_files, check_steps)
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

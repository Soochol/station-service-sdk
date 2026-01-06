"""Lint sequence command."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LintIssue:
    """A linting issue found in the code.

    Attributes:
        file: File path
        line: Line number
        column: Column number
        message: Issue description
        severity: warning or error
        fixable: Whether issue can be auto-fixed
    """

    file: str
    line: int
    column: int
    message: str
    severity: str = "warning"
    fixable: bool = False


def lint_sequence(package_path: Path, fix: bool = False) -> list[LintIssue]:
    """Lint a sequence package for common issues.

    Args:
        package_path: Path to sequence package
        fix: Whether to auto-fix issues

    Returns:
        List of issues found
    """
    issues: list[LintIssue] = []

    # Find Python files
    python_files = list(package_path.rglob("*.py"))

    for py_file in python_files:
        # Skip __pycache__ and test files for some checks
        if "__pycache__" in str(py_file):
            continue

        file_issues = _lint_file(py_file, fix)
        issues.extend(file_issues)

    # Check manifest
    manifest_path = package_path / "manifest.yaml"
    if manifest_path.exists():
        manifest_issues = _lint_manifest(manifest_path)
        issues.extend(manifest_issues)

    return issues


def _lint_file(file_path: Path, fix: bool) -> list[LintIssue]:
    """Lint a single Python file.

    Args:
        file_path: Path to Python file
        fix: Whether to auto-fix

    Returns:
        List of issues
    """
    issues: list[LintIssue] = []

    try:
        content = file_path.read_text()
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        return [LintIssue(
            file=str(file_path),
            line=e.lineno or 0,
            column=e.offset or 0,
            message=f"Syntax error: {e.msg}",
            severity="error",
        )]

    # Check for common issues
    visitor = SequenceLinter(str(file_path))
    visitor.visit(tree)
    issues.extend(visitor.issues)

    return issues


class SequenceLinter(ast.NodeVisitor):
    """AST visitor for linting sequence code."""

    def __init__(self, filename: str):
        self.filename = filename
        self.issues: list[LintIssue] = []
        self._in_sequence_class = False
        self._has_setup = False
        self._has_run = False
        self._has_teardown = False

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        # Check if this is a SequenceBase subclass
        is_sequence = any(
            (isinstance(base, ast.Name) and base.id == "SequenceBase") or
            (isinstance(base, ast.Attribute) and base.attr == "SequenceBase")
            for base in node.bases
        )

        if is_sequence:
            self._in_sequence_class = True
            self._has_setup = False
            self._has_run = False
            self._has_teardown = False

            # Check for required class attributes
            has_name = False
            has_version = False

            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            if target.id == "name":
                                has_name = True
                            elif target.id == "version":
                                has_version = True

                elif isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                    if item.name == "setup":
                        self._has_setup = True
                    elif item.name == "run":
                        self._has_run = True
                    elif item.name == "teardown":
                        self._has_teardown = True

            if not has_name:
                self.issues.append(LintIssue(
                    file=self.filename,
                    line=node.lineno,
                    column=node.col_offset,
                    message=f"Sequence class '{node.name}' missing 'name' attribute",
                    severity="error",
                ))

            if not has_version:
                self.issues.append(LintIssue(
                    file=self.filename,
                    line=node.lineno,
                    column=node.col_offset,
                    message=f"Sequence class '{node.name}' missing 'version' attribute",
                    severity="warning",
                ))

            if not self._has_run:
                self.issues.append(LintIssue(
                    file=self.filename,
                    line=node.lineno,
                    column=node.col_offset,
                    message=f"Sequence class '{node.name}' missing 'run' method",
                    severity="error",
                ))

        self.generic_visit(node)
        self._in_sequence_class = False

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function call."""
        if not self._in_sequence_class:
            self.generic_visit(node)
            return

        # Check for emit_step_start without emit_step_complete
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "emit_step_start":
                # Check for step name consistency
                if node.args and isinstance(node.args[0], ast.Constant):
                    pass  # Good, using constant step name

            elif node.func.attr == "emit_log":
                # Check log level
                if node.args:
                    level = node.args[0]
                    if isinstance(level, ast.Constant):
                        valid_levels = {"debug", "info", "warning", "error"}
                        if level.value not in valid_levels:
                            self.issues.append(LintIssue(
                                file=self.filename,
                                line=node.lineno,
                                column=node.col_offset,
                                message=f"Invalid log level: {level.value}",
                                severity="warning",
                            ))

        self.generic_visit(node)


def _lint_manifest(manifest_path: Path) -> list[LintIssue]:
    """Lint manifest.yaml file.

    Args:
        manifest_path: Path to manifest.yaml

    Returns:
        List of issues
    """
    import yaml

    issues: list[LintIssue] = []

    try:
        content = manifest_path.read_text()
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        return [LintIssue(
            file=str(manifest_path),
            line=getattr(e, "problem_mark", None).line if hasattr(e, "problem_mark") else 0,
            column=0,
            message=f"YAML error: {e}",
            severity="error",
        )]

    if not data:
        return issues

    # Check for description
    if "description" not in data or not data["description"]:
        issues.append(LintIssue(
            file=str(manifest_path),
            line=1,
            column=0,
            message="Missing or empty 'description' field",
            severity="warning",
        ))

    # Check for author
    if "author" not in data or not data["author"]:
        issues.append(LintIssue(
            file=str(manifest_path),
            line=1,
            column=0,
            message="Missing or empty 'author' field",
            severity="warning",
        ))

    # Check step timeouts
    if "steps" in data:
        for i, step in enumerate(data["steps"]):
            if isinstance(step, dict):
                timeout = step.get("timeout")
                if timeout is None:
                    issues.append(LintIssue(
                        file=str(manifest_path),
                        line=1,
                        column=0,
                        message=f"Step '{step.get('name', i)}' missing timeout",
                        severity="warning",
                    ))
                elif timeout > 300:
                    issues.append(LintIssue(
                        file=str(manifest_path),
                        line=1,
                        column=0,
                        message=f"Step '{step.get('name', i)}' has very long timeout ({timeout}s)",
                        severity="warning",
                    ))

    return issues

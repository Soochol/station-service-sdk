"""Doctor command for diagnosing SDK installation."""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass
class DiagnosticCheck:
    """Result of a diagnostic check.

    Attributes:
        name: Check name
        passed: Whether check passed
        warning: Whether check has a warning
        message: Status message
        suggestion: Suggestion for fixing issues
    """

    name: str
    passed: bool
    warning: bool = False
    message: str = ""
    suggestion: str | None = None


def run_diagnostics() -> list[DiagnosticCheck]:
    """Run all diagnostic checks.

    Returns:
        List of check results
    """
    checks: list[DiagnosticCheck] = []

    # Python version check
    checks.append(_check_python_version())

    # SDK installation check
    checks.append(_check_sdk_installation())

    # Dependencies check
    checks.append(_check_dependencies())

    # Optional dependencies check
    checks.append(_check_optional_deps())

    # CLI check
    checks.append(_check_cli())

    return checks


def _check_python_version() -> DiagnosticCheck:
    """Check Python version."""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if version >= (3, 11):
        return DiagnosticCheck(
            name="Python Version",
            passed=True,
            message=f"Python {version_str} (>=3.11 required)",
        )
    elif version >= (3, 10):
        return DiagnosticCheck(
            name="Python Version",
            passed=False,
            warning=True,
            message=f"Python {version_str} (3.11+ recommended)",
            suggestion="Consider upgrading to Python 3.11 or later for best performance",
        )
    else:
        return DiagnosticCheck(
            name="Python Version",
            passed=False,
            message=f"Python {version_str} (3.11+ required)",
            suggestion="Upgrade to Python 3.11 or later",
        )


def _check_sdk_installation() -> DiagnosticCheck:
    """Check SDK installation."""
    try:
        import station_service_sdk

        version = station_service_sdk.__version__
        return DiagnosticCheck(
            name="SDK Installation",
            passed=True,
            message=f"station-service-sdk v{version}",
        )
    except ImportError:
        return DiagnosticCheck(
            name="SDK Installation",
            passed=False,
            message="SDK not installed",
            suggestion="Install with: pip install station-service-sdk",
        )


def _check_dependencies() -> DiagnosticCheck:
    """Check required dependencies."""
    missing = []

    # Check pydantic
    try:
        import pydantic

        pydantic_version = pydantic.__version__
        if not pydantic_version.startswith("2"):
            missing.append(f"pydantic>=2.0 (found {pydantic_version})")
    except ImportError:
        missing.append("pydantic>=2.0")

    # Check pyyaml
    try:
        import yaml
    except ImportError:
        missing.append("pyyaml>=6.0")

    # Check click
    try:
        import click
    except ImportError:
        missing.append("click>=8.0")

    if not missing:
        return DiagnosticCheck(
            name="Required Dependencies",
            passed=True,
            message="All required dependencies installed",
        )
    else:
        return DiagnosticCheck(
            name="Required Dependencies",
            passed=False,
            message=f"Missing: {', '.join(missing)}",
            suggestion=f"Install with: pip install {' '.join(missing)}",
        )


def _check_optional_deps() -> DiagnosticCheck:
    """Check optional dependencies."""
    available = []
    missing = []

    # Check OpenTelemetry
    try:
        import opentelemetry

        available.append("opentelemetry (tracing)")
    except ImportError:
        missing.append("opentelemetry (tracing)")

    # Check prometheus-client
    try:
        import prometheus_client

        available.append("prometheus-client (metrics)")
    except ImportError:
        missing.append("prometheus-client (metrics)")

    if available and not missing:
        return DiagnosticCheck(
            name="Optional Dependencies",
            passed=True,
            message=f"Available: {', '.join(available)}",
        )
    elif available:
        return DiagnosticCheck(
            name="Optional Dependencies",
            passed=True,
            warning=True,
            message=f"Available: {', '.join(available)}; Not installed: {', '.join(missing)}",
            suggestion="Install optional deps with: pip install station-service-sdk[all]",
        )
    else:
        return DiagnosticCheck(
            name="Optional Dependencies",
            passed=True,
            warning=True,
            message="No optional dependencies installed",
            suggestion="Install optional deps with: pip install station-service-sdk[all]",
        )


def _check_cli() -> DiagnosticCheck:
    """Check CLI availability."""
    import shutil

    if shutil.which("station-sdk"):
        return DiagnosticCheck(
            name="CLI Installation",
            passed=True,
            message="station-sdk command available in PATH",
        )
    else:
        # Check if it's importable
        try:
            from station_service_sdk.cli import main

            return DiagnosticCheck(
                name="CLI Installation",
                passed=True,
                warning=True,
                message="CLI available but not in PATH",
                suggestion="Run with: python -m station_service_sdk.cli",
            )
        except ImportError:
            return DiagnosticCheck(
                name="CLI Installation",
                passed=False,
                message="CLI not available",
                suggestion="Reinstall SDK: pip install --force-reinstall station-service-sdk",
            )

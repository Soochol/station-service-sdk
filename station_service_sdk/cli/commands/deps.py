"""Dependencies management command."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class DependencyResult:
    """Result of dependency check.

    Attributes:
        all_satisfied: Whether all dependencies are installed
        missing: List of missing packages
        installed: List of installed packages
    """

    all_satisfied: bool = True
    missing: list[str] = field(default_factory=list)
    installed: list[str] = field(default_factory=list)


def check_dependencies(
    package_path: Path,
    install: bool = False,
) -> DependencyResult:
    """Check and optionally install sequence dependencies.

    Args:
        package_path: Path to sequence package
        install: Whether to install missing dependencies

    Returns:
        DependencyResult with dependency status
    """
    result = DependencyResult()

    # Get dependencies from manifest
    manifest_path = package_path / "manifest.yaml"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest_data = yaml.safe_load(f)

        deps = manifest_data.get("dependencies", [])
        for dep in deps:
            if isinstance(dep, dict):
                package = dep.get("package", "")
                version = dep.get("version", "")
                dep_str = f"{package}{version}" if version else package
            else:
                dep_str = str(dep)

            if dep_str:
                if _is_installed(dep_str):
                    result.installed.append(dep_str)
                else:
                    result.missing.append(dep_str)

    # Get dependencies from pyproject.toml
    pyproject_path = package_path / "pyproject.toml"
    if pyproject_path.exists():
        try:
            import tomllib

            with open(pyproject_path, "rb") as f:
                pyproject_data = tomllib.load(f)

            project_deps = pyproject_data.get("project", {}).get("dependencies", [])
            for dep in project_deps:
                # Skip station-service-sdk itself
                if dep.startswith("station-service-sdk"):
                    continue

                # Parse package name from dependency string
                package_name = _parse_package_name(dep)
                if package_name:
                    if _is_installed(package_name):
                        if dep not in result.installed:
                            result.installed.append(dep)
                    else:
                        if dep not in result.missing:
                            result.missing.append(dep)

        except ImportError:
            # tomllib not available in Python < 3.11
            pass

    result.all_satisfied = len(result.missing) == 0

    # Install if requested
    if install and result.missing:
        _install_packages(result.missing)
        result.all_satisfied = True
        result.installed.extend(result.missing)
        result.missing = []

    return result


def _is_installed(package: str) -> bool:
    """Check if a package is installed.

    Args:
        package: Package name or requirement string

    Returns:
        True if installed
    """
    package_name = _parse_package_name(package)
    if not package_name:
        return False

    try:
        from importlib.metadata import distribution

        distribution(package_name)
        return True
    except Exception:
        return False


def _parse_package_name(requirement: str) -> str:
    """Parse package name from requirement string.

    Args:
        requirement: Requirement string (e.g., "requests>=2.0")

    Returns:
        Package name
    """
    # Remove extras
    if "[" in requirement:
        requirement = requirement.split("[")[0]

    # Remove version specifiers
    for sep in (">=", "<=", "==", "!=", ">", "<", "~="):
        if sep in requirement:
            requirement = requirement.split(sep)[0]

    return requirement.strip()


def _install_packages(packages: list[str]) -> None:
    """Install packages using pip.

    Args:
        packages: List of packages to install
    """
    for package in packages:
        print(f"Installing {package}...")
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            package,
            "--quiet",
        ])

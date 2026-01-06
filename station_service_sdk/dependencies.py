"""
Dependency management utilities for Station Service SDK.

Provides functions to check and auto-install Python package dependencies
at runtime, ensuring sequences can run even if dependencies weren't
pre-installed.
"""

import importlib.util
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Python 3.11+ has tomllib in stdlib, fallback to tomli for older versions
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore

# Mapping of pip package names to their import names
# Add entries here when the pip name differs from the import name
PACKAGE_IMPORT_MAP: Dict[str, str] = {
    "pyserial": "serial",
    "pyserial-asyncio": "serial_asyncio",
    "pyyaml": "yaml",
    "pillow": "PIL",
    "opencv-python": "cv2",
    "scikit-learn": "sklearn",
}


def get_import_name(package: str) -> str:
    """
    Get the import name for a pip package.

    Args:
        package: The pip package name (e.g., 'pyserial')

    Returns:
        The import name (e.g., 'serial')
    """
    # Check the mapping first
    if package in PACKAGE_IMPORT_MAP:
        return PACKAGE_IMPORT_MAP[package]

    # Handle version specifiers (e.g., 'pyserial>=3.5' -> 'pyserial')
    base_package = package.split(">=")[0].split("<=")[0].split("==")[0].split("<")[0].split(">")[0]

    if base_package in PACKAGE_IMPORT_MAP:
        return PACKAGE_IMPORT_MAP[base_package]

    # Default: replace hyphens with underscores
    return base_package.replace("-", "_")


def is_installed(package: str) -> bool:
    """
    Check if a Python package is installed.

    Args:
        package: The pip package name (e.g., 'pyserial', 'pyserial>=3.5')

    Returns:
        True if the package is installed, False otherwise
    """
    import_name = get_import_name(package)
    return importlib.util.find_spec(import_name) is not None


def ensure_package(package: str, auto_install: bool = True) -> bool:
    """
    Ensure a package is installed, optionally installing it if missing.

    Args:
        package: The pip package name (e.g., 'pyserial', 'pyserial>=3.5')
        auto_install: If True, automatically install missing packages

    Returns:
        True if package is available (installed or newly installed)

    Raises:
        subprocess.CalledProcessError: If auto_install fails
    """
    if is_installed(package):
        return True

    if not auto_install:
        logger.warning(f"Package '{package}' is not installed")
        return False

    logger.info(f"Installing missing package: {package}")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        logger.info(f"Successfully installed: {package}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install {package}: {e}")
        raise


def ensure_dependencies(
    packages: List[str],
    auto_install: bool = True,
    fail_fast: bool = False,
) -> Dict[str, bool]:
    """
    Ensure multiple packages are installed.

    Args:
        packages: List of pip package names
        auto_install: If True, automatically install missing packages
        fail_fast: If True, stop on first failure

    Returns:
        Dictionary mapping package names to installation status

    Example:
        >>> results = ensure_dependencies(['pyserial', 'numpy'])
        >>> if all(results.values()):
        ...     print("All dependencies satisfied")
    """
    results: Dict[str, bool] = {}

    for package in packages:
        try:
            results[package] = ensure_package(package, auto_install)
        except subprocess.CalledProcessError:
            results[package] = False
            if fail_fast:
                break

    return results


def check_dependencies(packages: List[str]) -> Dict[str, bool]:
    """
    Check which packages are installed without installing anything.

    Args:
        packages: List of pip package names to check

    Returns:
        Dictionary mapping package names to their installation status
    """
    return {pkg: is_installed(pkg) for pkg in packages}


def get_missing_packages(packages: List[str]) -> List[str]:
    """
    Get list of packages that are not installed.

    Args:
        packages: List of pip package names to check

    Returns:
        List of package names that are not installed
    """
    return [pkg for pkg in packages if not is_installed(pkg)]


# =============================================================================
# pyproject.toml Support
# =============================================================================


def parse_pyproject_dependencies(pyproject_path: Union[str, Path]) -> List[str]:
    """
    Parse dependencies from a pyproject.toml file.

    Args:
        pyproject_path: Path to pyproject.toml file

    Returns:
        List of dependency specifications

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If tomllib is not available
    """
    if tomllib is None:
        raise ValueError(
            "tomllib/tomli not available. Install tomli for Python < 3.11: "
            "pip install tomli"
        )

    path = Path(pyproject_path)
    if not path.exists():
        raise FileNotFoundError(f"pyproject.toml not found: {path}")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    return data.get("project", {}).get("dependencies", [])


def install_sequence_dependencies(
    sequence_dir: Union[str, Path],
    auto_install: bool = True,
) -> List[str]:
    """
    Install dependencies from a sequence's pyproject.toml.

    Args:
        sequence_dir: Path to sequence directory containing pyproject.toml
        auto_install: If True, install missing packages

    Returns:
        List of newly installed packages (empty if none installed)
    """
    sequence_path = Path(sequence_dir)
    pyproject_path = sequence_path / "pyproject.toml"

    if not pyproject_path.exists():
        return []

    try:
        deps = parse_pyproject_dependencies(pyproject_path)
    except (ValueError, Exception) as e:
        logger.warning(f"Failed to parse {pyproject_path}: {e}")
        return []

    if not deps:
        return []

    missing = get_missing_packages(deps)
    if not missing:
        logger.debug(f"All dependencies installed for {sequence_path.name}")
        return []

    if not auto_install:
        logger.warning(f"Missing dependencies for {sequence_path.name}: {missing}")
        return []

    logger.info(f"Installing dependencies for {sequence_path.name}: {missing}")

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", *missing],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        logger.info(f"Successfully installed: {missing}")
        return missing
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install dependencies: {e}")
        return []


def get_pyproject_missing_packages(
    sequence_dir: Union[str, Path],
) -> List[str]:
    """
    Get missing packages from a sequence's pyproject.toml without installing.

    Args:
        sequence_dir: Path to sequence directory containing pyproject.toml

    Returns:
        List of missing package specifications
    """
    sequence_path = Path(sequence_dir)
    pyproject_path = sequence_path / "pyproject.toml"

    if not pyproject_path.exists():
        return []

    try:
        deps = parse_pyproject_dependencies(pyproject_path)
        return get_missing_packages(deps)
    except Exception:
        return []

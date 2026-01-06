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
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

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

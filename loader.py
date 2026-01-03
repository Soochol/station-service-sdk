"""
Dynamic sequence loader for package discovery and loading.

This module provides the SequenceLoader class for discovering,
loading, and validating sequence packages from the filesystem.
"""

import contextlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Type

import yaml
from pydantic import ValidationError as PydanticValidationError

from .exceptions import ManifestError, PackageError
from .manifest import HardwareDefinition, SequenceManifest

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def temporary_sys_path(paths: List[str]) -> Generator[None, None, None]:
    """
    Context manager for temporarily adding paths to sys.path.

    Safely adds paths at the beginning of sys.path and removes them
    when exiting the context, even if an exception occurs.

    Args:
        paths: List of path strings to temporarily add

    Yields:
        None

    Example:
        with temporary_sys_path(["/path/to/package", "/path/to/parent"]):
            import my_module  # Can now find modules in those paths
        # Paths are removed after exiting
    """
    added_paths: List[str] = []
    for path in paths:
        if path not in sys.path:
            sys.path.insert(0, path)
            added_paths.append(path)
            logger.debug(f"Temporarily added to sys.path: {path}")

    try:
        yield
    finally:
        for path in reversed(added_paths):
            if path in sys.path:
                sys.path.remove(path)
                logger.debug(f"Removed from sys.path: {path}")


class SequenceLoader:
    """
    Dynamic loader for sequence packages.

    Handles discovery, loading, and validation of sequence packages
    from the filesystem.

    Usage:
        loader = SequenceLoader("sequences")

        # Discover available packages
        packages = await loader.discover_packages()

        # Load a specific package
        manifest = await loader.load_package("my_sequence")

        # Load the sequence class
        seq_class = await loader.load_sequence_class(manifest, package_path)
    """

    MANIFEST_FILENAME = "manifest.yaml"
    REQUIRED_FILES = ["manifest.yaml"]

    def __init__(self, packages_dir: str = "sequences") -> None:
        """
        Initialize the sequence loader.

        Args:
            packages_dir: Directory containing sequence packages.
                         Can be relative or absolute path.
        """
        self.packages_dir = Path(packages_dir)
        self._loaded_packages: Dict[str, SequenceManifest] = {}
        self._loaded_classes: Dict[str, Type] = {}
        # Mapping from manifest name to folder path (for when they differ)
        self._name_to_path: Dict[str, Path] = {}

    @property
    def packages_path(self) -> Path:
        """Get the absolute path to the packages directory."""
        if self.packages_dir.is_absolute():
            return self.packages_dir
        return Path.cwd() / self.packages_dir

    async def discover_packages(self) -> List[str]:
        """
        Discover available sequence packages in the packages directory.

        Scans the packages directory for subdirectories that contain
        a valid manifest.yaml file.

        Returns:
            List of package names found.

        Raises:
            PackageError: If the packages directory does not exist.
        """
        packages_path = self.packages_path

        if not packages_path.exists():
            logger.warning(f"Packages directory does not exist: {packages_path}")
            return []

        if not packages_path.is_dir():
            raise PackageError(f"Packages path is not a directory: {packages_path}")

        packages: List[str] = []

        for item in packages_path.iterdir():
            if not item.is_dir():
                continue

            # Skip hidden directories and __pycache__
            if item.name.startswith(".") or item.name == "__pycache__":
                continue

            manifest_path = item / self.MANIFEST_FILENAME
            if manifest_path.exists():
                packages.append(item.name)
                logger.debug(f"Discovered package: {item.name}")
            else:
                logger.debug(f"Skipping directory without manifest: {item.name}")

        logger.info(f"Discovered {len(packages)} sequence packages")
        return packages

    async def _find_package_by_manifest_name(self, manifest_name: str) -> Optional[Path]:
        """
        Find a package by its manifest name (when folder name differs from manifest name).

        Scans all packages in the directory and checks their manifest names.

        Args:
            manifest_name: The manifest name to search for.

        Returns:
            Path to the package if found, None otherwise.
        """
        packages_path = self.packages_path
        if not packages_path.exists():
            return None

        for item in packages_path.iterdir():
            if not item.is_dir():
                continue

            # Skip hidden directories and __pycache__
            if item.name.startswith(".") or item.name == "__pycache__":
                continue

            manifest_path = item / self.MANIFEST_FILENAME
            if not manifest_path.exists():
                continue

            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = yaml.safe_load(f)

                if manifest_data and manifest_data.get("name") == manifest_name:
                    logger.info(f"Found package '{manifest_name}' in folder '{item.name}'")
                    # Cache the mapping for future lookups
                    self._name_to_path[manifest_name] = item
                    return item
            except Exception as e:
                logger.debug(f"Error reading manifest in {item.name}: {e}")
                continue

        return None

    async def load_package(self, package_name: str) -> SequenceManifest:
        """
        Load and validate a sequence package manifest.

        Args:
            package_name: Name of the package to load (can be folder name or manifest name).

        Returns:
            Validated SequenceManifest instance.

        Raises:
            PackageError: If the package does not exist or has invalid structure.
            ManifestError: If the manifest is invalid or cannot be parsed.
        """
        # Return cached manifest if already loaded (by folder name)
        if package_name in self._loaded_packages:
            return self._loaded_packages[package_name]

        # Check if this is a manifest name that maps to a different folder
        if package_name in self._name_to_path:
            package_path = self._name_to_path[package_name]
            folder_name = package_path.name
            # Return cached manifest if already loaded (by folder name)
            if folder_name in self._loaded_packages:
                return self._loaded_packages[folder_name]
        else:
            package_path = self.packages_path / package_name

        if not package_path.exists():
            # Folder doesn't exist - try to find by scanning manifest names
            found_path = await self._find_package_by_manifest_name(package_name)
            if found_path:
                package_path = found_path
            else:
                raise PackageError(
                    f"Package not found: {package_name}",
                    package_name=package_name,
                )

        # Validate package structure
        self._validate_package_structure(package_path)

        manifest_path = package_path / self.MANIFEST_FILENAME

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ManifestError(
                f"Failed to parse manifest YAML: {e}",
                package_name=package_name,
                manifest_path=str(manifest_path),
            )

        if manifest_data is None:
            raise ManifestError(
                "Manifest file is empty",
                package_name=package_name,
                manifest_path=str(manifest_path),
            )

        try:
            manifest = SequenceManifest.model_validate(manifest_data)
        except PydanticValidationError as e:
            raise ManifestError(
                f"Invalid manifest schema: {e}",
                package_name=package_name,
                manifest_path=str(manifest_path),
                details={"errors": e.errors()},
            )

        # Cache the loaded manifest
        self._loaded_packages[package_name] = manifest

        # Store mapping from manifest name to folder path
        # This allows delete/download to work even when folder name != manifest name
        self._name_to_path[manifest.name] = package_path
        logger.info(f"Loaded package manifest: {package_name} v{manifest.version} (name={manifest.name})")

        return manifest

    async def load_sequence_class(
        self,
        manifest: SequenceManifest,
        package_path: Path,
    ) -> Type:
        """
        Dynamically load the sequence class from a package.

        Args:
            manifest: The package manifest containing entry point info.
            package_path: Path to the package directory.

        Returns:
            The loaded sequence class.

        Raises:
            PackageError: If the module or class cannot be loaded.
        """
        cache_key = f"{package_path.name}:{manifest.entry_point.class_name}"

        if cache_key in self._loaded_classes:
            return self._loaded_classes[cache_key]

        entry_point = manifest.entry_point
        module_path = package_path / f"{entry_point.module}.py"

        if not module_path.exists():
            raise PackageError(
                f"Entry point module not found: {entry_point.module}",
                package_name=package_path.name,
                details={"expected_path": str(module_path)},
            )

        # Create a unique module name to avoid conflicts
        module_name = f"_sequence_packages.{package_path.name}.{entry_point.module}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise PackageError(
                    f"Failed to create module spec for: {module_path}",
                    package_name=package_path.name,
                )

            module = importlib.util.module_from_spec(spec)

            # Add package paths temporarily for imports within the package
            package_parent = str(package_path.parent)
            package_path_str = str(package_path)

            with temporary_sys_path([package_path_str, package_parent]):
                # Create parent module hierarchy in sys.modules
                parent_module_name = "_sequence_packages"
                if parent_module_name not in sys.modules:
                    import types
                    parent_module = types.ModuleType(parent_module_name)
                    parent_module.__path__ = []
                    sys.modules[parent_module_name] = parent_module

                package_module_name = f"_sequence_packages.{package_path.name}"
                if package_module_name not in sys.modules:
                    import types
                    package_module = types.ModuleType(package_module_name)
                    package_module.__path__ = [str(package_path)]
                    sys.modules[package_module_name] = package_module

                sys.modules[module_name] = module
                spec.loader.exec_module(module)

        except Exception as e:
            raise PackageError(
                f"Failed to load module '{entry_point.module}': {e}",
                package_name=package_path.name,
                details={"module_path": str(module_path)},
            )

        # Get the class from the module
        class_name = entry_point.class_name
        if not hasattr(module, class_name):
            raise PackageError(
                f"Class '{class_name}' not found in module '{entry_point.module}'",
                package_name=package_path.name,
                details={
                    "available_names": [
                        n for n in dir(module) if not n.startswith("_")
                    ]
                },
            )

        sequence_class = getattr(module, class_name)

        # Check if this is an SDK-based SequenceBase class
        is_cli_mode = manifest.modes.cli if manifest.modes else False
        has_cli_main = manifest.entry_point.cli_main is not None if manifest.entry_point else False

        if is_cli_mode or has_cli_main:
            # SDK-based CLI sequence - verify it's a SequenceBase subclass
            try:
                from .base import SequenceBase
                if not issubclass(sequence_class, SequenceBase):
                    logger.warning(
                        f"Class '{class_name}' is CLI mode but does not inherit from SequenceBase"
                    )
            except ImportError:
                logger.debug("SequenceBase not available, skipping type check")

        # Cache the loaded class
        self._loaded_classes[cache_key] = sequence_class
        logger.info(f"Loaded sequence class: {class_name}")

        return sequence_class

    def _validate_package_structure(self, package_path: Path) -> None:
        """
        Validate that a package has the required file structure.

        Args:
            package_path: Path to the package directory.

        Raises:
            PackageError: If required files are missing.
        """
        missing_files: List[str] = []

        for required_file in self.REQUIRED_FILES:
            file_path = package_path / required_file
            if not file_path.exists():
                missing_files.append(required_file)

        if missing_files:
            raise PackageError(
                f"Package is missing required files: {', '.join(missing_files)}",
                package_name=package_path.name,
                details={"missing_files": missing_files},
            )

    async def _load_driver_class(
        self,
        hardware_def: HardwareDefinition,
        package_path: Path,
    ) -> Type:
        """
        Load a hardware driver class.

        Args:
            hardware_def: Hardware definition from the manifest.
            package_path: Path to the package directory.

        Returns:
            The loaded driver class.

        Raises:
            PackageError: If the driver cannot be loaded.
        """
        driver_module_name = hardware_def.driver
        driver_class_name = hardware_def.class_name

        # First, try to load from the package's drivers directory
        drivers_path = package_path / "drivers"
        driver_module_path = drivers_path / f"{driver_module_name}.py"

        if driver_module_path.exists():
            return await self._load_class_from_file(
                driver_module_path,
                driver_class_name,
                package_path.name,
            )

        # Try to load from the package root
        root_module_path = package_path / f"{driver_module_name}.py"
        if root_module_path.exists():
            return await self._load_class_from_file(
                root_module_path,
                driver_class_name,
                package_path.name,
            )

        # Try to import as a system module
        try:
            module = importlib.import_module(driver_module_name)
            if hasattr(module, driver_class_name):
                return getattr(module, driver_class_name)
            else:
                raise PackageError(
                    f"Driver class '{driver_class_name}' not found in module '{driver_module_name}'",
                    package_name=package_path.name,
                )
        except ImportError as e:
            raise PackageError(
                f"Failed to import driver module '{driver_module_name}': {e}",
                package_name=package_path.name,
            )

    async def _load_class_from_file(
        self,
        file_path: Path,
        class_name: str,
        package_name: str,
    ) -> Type:
        """
        Load a class from a Python file.

        Args:
            file_path: Path to the Python file.
            class_name: Name of the class to load.
            package_name: Name of the package for error reporting.

        Returns:
            The loaded class.

        Raises:
            PackageError: If the class cannot be loaded.
        """
        module_name = f"_sequence_drivers.{package_name}.{file_path.stem}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                raise PackageError(
                    f"Failed to create module spec for: {file_path}",
                    package_name=package_name,
                )

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

        except Exception as e:
            raise PackageError(
                f"Failed to load driver module: {e}",
                package_name=package_name,
                details={"file_path": str(file_path)},
            )

        if not hasattr(module, class_name):
            raise PackageError(
                f"Class '{class_name}' not found in {file_path.name}",
                package_name=package_name,
                details={
                    "available_names": [
                        n for n in dir(module) if not n.startswith("_")
                    ]
                },
            )

        return getattr(module, class_name)

    async def load_hardware_drivers(
        self,
        manifest: SequenceManifest,
        package_path: Path,
    ) -> Dict[str, Type]:
        """
        Load all hardware driver classes defined in a manifest.

        Args:
            manifest: The package manifest.
            package_path: Path to the package directory.

        Returns:
            Dictionary mapping hardware names to driver classes.

        Raises:
            PackageError: If any driver cannot be loaded.
        """
        drivers: Dict[str, Type] = {}

        for hw_name, hw_def in manifest.hardware.items():
            logger.debug(f"Loading driver for hardware: {hw_name}")
            driver_class = await self._load_driver_class(hw_def, package_path)
            drivers[hw_name] = driver_class
            logger.info(f"Loaded driver: {hw_name} -> {driver_class.__name__}")

        return drivers

    def get_package_path(self, package_name: str) -> Path:
        """
        Get the filesystem path for a package.

        Args:
            package_name: Name of the package (can be folder name or manifest name).

        Returns:
            Path to the package directory.
        """
        # First check if it's a manifest name that was mapped to a folder path
        if package_name in self._name_to_path:
            return self._name_to_path[package_name]
        # Fall back to treating it as a folder name
        return self.packages_path / package_name

    def clear_cache(self) -> None:
        """Clear all cached manifests and classes."""
        self._loaded_packages.clear()
        self._loaded_classes.clear()
        self._name_to_path.clear()
        logger.debug("Cleared sequence loader cache")

    async def reload_package(self, package_name: str) -> SequenceManifest:
        """
        Reload a package, clearing its cache first.

        Args:
            package_name: Name of the package to reload.

        Returns:
            Freshly loaded SequenceManifest.
        """
        # Remove from cache
        if package_name in self._loaded_packages:
            del self._loaded_packages[package_name]

        # Remove any cached classes for this package
        keys_to_remove = [
            k for k in self._loaded_classes.keys() if k.startswith(f"{package_name}:")
        ]
        for key in keys_to_remove:
            del self._loaded_classes[key]

        return await self.load_package(package_name)

    async def update_manifest(
        self,
        package_name: str,
        parameter_updates: Optional[List[Dict[str, Any]]] = None,
        step_updates: Optional[List[Dict[str, Any]]] = None,
    ) -> SequenceManifest:
        """
        Update a sequence package manifest.

        Modifies the manifest.yaml file and increments the version.

        Args:
            package_name: Name of the package to update.
            parameter_updates: List of parameter updates with 'name' and 'default'.
            step_updates: List of step updates with 'name', 'order', and 'timeout'.

        Returns:
            Updated SequenceManifest.

        Raises:
            PackageError: If the package does not exist.
        """
        from datetime import datetime as dt

        package_path = self.packages_path / package_name
        manifest_path = package_path / self.MANIFEST_FILENAME

        if not manifest_path.exists():
            raise PackageError(
                f"Package not found: {package_name}",
                package_name=package_name,
            )

        # Load current manifest data
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = yaml.safe_load(f)

        updated = False

        # Apply parameter updates
        if parameter_updates:
            parameters = manifest_data.get("parameters", {})
            for update in parameter_updates:
                param_name = update.get("name")
                if param_name and param_name in parameters:
                    if "default" in update:
                        parameters[param_name]["default"] = update["default"]
                        updated = True
            manifest_data["parameters"] = parameters

        # Apply step updates (stored separately as step overrides file)
        if step_updates:
            # Store step config overrides in a separate file to avoid
            # modifying the manifest which may be version-controlled
            overrides_path = package_path / "step_overrides.yaml"
            overrides = {}
            if overrides_path.exists():
                with open(overrides_path, "r", encoding="utf-8") as f:
                    overrides = yaml.safe_load(f) or {}

            for update in step_updates:
                step_name = update.get("name")
                if step_name:
                    if step_name not in overrides:
                        overrides[step_name] = {}
                    if "order" in update and update["order"] is not None:
                        overrides[step_name]["order"] = update["order"]
                    if "timeout" in update and update["timeout"] is not None:
                        overrides[step_name]["timeout"] = update["timeout"]
                    updated = True

            with open(overrides_path, "w", encoding="utf-8") as f:
                yaml.dump(overrides, f, default_flow_style=False)
            logger.info(f"Saved step overrides for package: {package_name}")

        if updated:
            # Increment version
            current_version = manifest_data.get("version", "1.0.0")
            parts = current_version.split(".")
            parts[-1] = str(int(parts[-1]) + 1)  # Increment patch version
            new_version = ".".join(parts)
            manifest_data["version"] = new_version

            # Update timestamp
            manifest_data["updated_at"] = dt.now().isoformat()

            # Write updated manifest
            with open(manifest_path, "w", encoding="utf-8") as f:
                yaml.dump(manifest_data, f, default_flow_style=False)
            logger.info(f"Updated manifest for package: {package_name} to v{new_version}")

        # Clear cache and reload
        return await self.reload_package(package_name)

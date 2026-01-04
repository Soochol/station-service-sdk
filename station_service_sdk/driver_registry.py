"""
Driver Registry for Manual Sequence Execution.

Provides dynamic driver loading without Batch dependency,
enabling standalone hardware access for manual testing.
"""

import asyncio
import importlib
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .manifest import SequenceManifest, HardwareDefinition

logger = logging.getLogger(__name__)


class DriverLoadError(Exception):
    """Raised when a driver cannot be loaded."""

    def __init__(self, hardware_id: str, message: str):
        self.hardware_id = hardware_id
        super().__init__(f"Failed to load driver for '{hardware_id}': {message}")


class DriverConnectionError(Exception):
    """Raised when a driver connection fails."""

    def __init__(self, hardware_id: str, message: str):
        self.hardware_id = hardware_id
        super().__init__(f"Failed to connect '{hardware_id}': {message}")


class DriverRegistry:
    """
    Dynamic driver loading without Batch dependency.

    Loads drivers based on manifest hardware definitions,
    enabling standalone hardware access for manual testing.

    Usage:
        registry = DriverRegistry()

        # Load a single driver class
        driver_class = await registry.load_driver_class(
            sequence_name="psa_sensor_test",
            hardware_id="psa_mcu",
            hardware_def=manifest.hardware["psa_mcu"],
        )

        # Or load and connect all hardware for a sequence
        drivers = await registry.connect_hardware(
            manifest=manifest,
            sequence_path=Path("sequences/psa_sensor_test"),
            hardware_config={"psa_mcu": {"port": "/dev/ttyUSB0"}},
        )
    """

    def __init__(self, sequences_dir: str = "sequences") -> None:
        """
        Initialize the driver registry.

        Args:
            sequences_dir: Base directory for sequence packages
        """
        self.sequences_dir = Path(sequences_dir)
        self._driver_cache: Dict[str, Type[Any]] = {}

    async def load_driver_class(
        self,
        sequence_name: str,
        hardware_id: str,
        hardware_def: "HardwareDefinition",
    ) -> Type[Any]:
        """
        Dynamically load a driver class from sequence package.

        Args:
            sequence_name: Name of the sequence (folder name)
            hardware_id: Hardware identifier from manifest
            hardware_def: Hardware definition from manifest

        Returns:
            Driver class (not instantiated)

        Raises:
            DriverLoadError: If driver cannot be found or loaded
        """
        # Check cache first
        cache_key = f"{sequence_name}:{hardware_id}"
        if cache_key in self._driver_cache:
            return self._driver_cache[cache_key]

        # Get driver info from definition
        # hardware_def.driver is like "drivers.psa_mcu" or "psa_mcu"
        driver_path = hardware_def.driver
        driver_class_name = hardware_def.driver_class  # e.g., "PSAMCUDriver"

        if not driver_path or not driver_class_name:
            raise DriverLoadError(
                hardware_id,
                f"Missing driver path or class name in manifest: "
                f"driver={driver_path}, class={driver_class_name}",
            )

        # Parse driver path to get module name
        # "drivers.psa_mcu" -> "psa_mcu"
        # "psa_mcu" -> "psa_mcu"
        if "." in driver_path:
            driver_module = driver_path.split(".")[-1]
            driver_subpath = driver_path.rsplit(".", 1)[0]  # "drivers"
        else:
            driver_module = driver_path
            driver_subpath = "drivers"

        # Build import paths to try
        possible_paths = [
            # 1. Sequence-specific drivers directory
            f"sequences.{sequence_name}.{driver_subpath}.{driver_module}",
            # 2. Direct module path
            f"sequences.{sequence_name}.{driver_module}",
            # 3. Global drivers
            f"station_service.drivers.{driver_module}",
        ]

        driver_class = None
        last_error = None

        for module_path in possible_paths:
            try:
                module = importlib.import_module(module_path)
                driver_class = getattr(module, driver_class_name, None)
                if driver_class:
                    logger.debug(
                        f"Loaded driver {driver_class_name} from {module_path}"
                    )
                    break
            except (ImportError, AttributeError) as e:
                last_error = e
                logger.debug(f"Driver not found at {module_path}: {e}")
                continue

        if driver_class is None:
            raise DriverLoadError(
                hardware_id,
                f"Could not find {driver_class_name} in any of: {possible_paths}. "
                f"Last error: {last_error}",
            )

        # Cache the class
        self._driver_cache[cache_key] = driver_class
        return driver_class

    async def create_driver_instance(
        self,
        driver_class: Type[Any],
        name: str,
        config: Dict[str, Any],
    ) -> Any:
        """
        Create and configure a driver instance.

        Args:
            driver_class: Driver class to instantiate
            name: Hardware name/identifier
            config: Configuration parameters for the driver

        Returns:
            Driver instance (not connected)
        """
        try:
            # Most drivers expect name and config in constructor
            driver = driver_class(name=name, config=config)
            logger.debug(f"Created driver instance: {name} ({driver_class.__name__})")
            return driver
        except TypeError:
            # Some drivers might have different signatures
            try:
                driver = driver_class(config=config)
                logger.debug(f"Created driver instance (no name): {name}")
                return driver
            except TypeError:
                driver = driver_class()
                logger.debug(f"Created driver instance (no args): {name}")
                return driver

    async def connect_hardware(
        self,
        manifest: "SequenceManifest",
        sequence_path: Path,
        hardware_config: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Load and connect all hardware defined in manifest.

        Args:
            manifest: Sequence manifest with hardware definitions
            sequence_path: Path to the sequence package
            hardware_config: Optional config overrides per hardware ID

        Returns:
            Dict mapping hardware IDs to connected driver instances

        Raises:
            DriverLoadError: If any driver cannot be loaded
            DriverConnectionError: If any driver fails to connect
        """
        hardware_config = hardware_config or {}
        drivers: Dict[str, Any] = {}
        connection_errors: Dict[str, str] = {}

        # Get sequence folder name from path
        sequence_name = sequence_path.name

        for hw_id, hw_def in manifest.hardware.items():
            try:
                # Load driver class
                driver_class = await self.load_driver_class(
                    sequence_name=sequence_name,
                    hardware_id=hw_id,
                    hardware_def=hw_def,
                )

                # Merge default config with overrides
                default_config = {}
                if hw_def.config_schema:
                    for field_name, field_schema in hw_def.config_schema.items():
                        if field_schema.default is not None:
                            default_config[field_name] = field_schema.default

                # Apply user overrides
                final_config = {**default_config, **hardware_config.get(hw_id, {})}

                # Create instance
                driver = await self.create_driver_instance(
                    driver_class=driver_class,
                    name=hw_id,
                    config=final_config,
                )

                # Connect
                logger.info(f"Connecting hardware: {hw_id} ({hw_def.display_name})")

                if hasattr(driver, "connect"):
                    result = driver.connect()
                    # Handle async connect
                    if asyncio.iscoroutine(result):
                        result = await result

                    if result is False:
                        raise DriverConnectionError(
                            hw_id, "connect() returned False"
                        )

                drivers[hw_id] = driver
                logger.info(f"Connected: {hw_id}")

            except DriverLoadError:
                raise
            except DriverConnectionError:
                raise
            except Exception as e:
                connection_errors[hw_id] = str(e)
                logger.error(f"Failed to connect {hw_id}: {e}")

        # If any connections failed, disconnect successful ones and raise
        if connection_errors:
            await self.disconnect_all(drivers)
            error_msg = "; ".join(
                f"{hw_id}: {err}" for hw_id, err in connection_errors.items()
            )
            raise DriverConnectionError(
                list(connection_errors.keys())[0],
                f"Connection errors: {error_msg}",
            )

        return drivers

    async def disconnect_all(self, drivers: Dict[str, Any]) -> None:
        """
        Safely disconnect all hardware.

        Args:
            drivers: Dict mapping hardware IDs to driver instances
        """
        for hw_id, driver in drivers.items():
            try:
                if hasattr(driver, "disconnect"):
                    result = driver.disconnect()
                    if asyncio.iscoroutine(result):
                        await result
                    logger.info(f"Disconnected: {hw_id}")
            except Exception as e:
                logger.warning(f"Error disconnecting {hw_id}: {e}")

    def clear_cache(self) -> None:
        """Clear the driver class cache."""
        self._driver_cache.clear()

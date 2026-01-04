"""
Sequence Registry for named lookup and discovery.

Provides a centralized registry for sequence classes, enabling:
- Named lookup of sequence classes
- Auto-discovery from packages
- Validation of sequence implementations
"""

import importlib
import pkgutil
from typing import Dict, List, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import SequenceBase


class SequenceRegistry:
    """
    Registry for sequence classes.

    Provides named lookup and discovery of SequenceBase subclasses.

    Usage:
        # Register a sequence
        registry = SequenceRegistry()
        registry.register(MySequence)

        # Or auto-discover from a package
        registry.discover("sequences")

        # Lookup by name
        seq_class = registry.get("my_sequence")
        if seq_class:
            instance = seq_class(context)

        # List all registered sequences
        for name, info in registry.list().items():
            print(f"{name}: {info['description']}")
    """

    _instance: Optional["SequenceRegistry"] = None
    _sequences: Dict[str, Type["SequenceBase"]]

    def __new__(cls) -> "SequenceRegistry":
        """Singleton pattern for global registry."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._sequences = {}
        return cls._instance

    @classmethod
    def get_instance(cls) -> "SequenceRegistry":
        """Get the singleton instance."""
        return cls()

    @classmethod
    def reset(cls) -> None:
        """Reset the registry (useful for testing)."""
        if cls._instance:
            cls._instance._sequences = {}

    def register(
        self,
        sequence_class: Type["SequenceBase"],
        name: Optional[str] = None,
    ) -> None:
        """
        Register a sequence class.

        Args:
            sequence_class: SequenceBase subclass to register
            name: Optional name override (defaults to sequence_class.name)

        Raises:
            ValueError: If class is not a valid SequenceBase subclass
            ValueError: If name is already registered
        """
        from .base import SequenceBase

        # Validate
        if not isinstance(sequence_class, type):
            raise ValueError(f"Expected class, got {type(sequence_class)}")

        if not issubclass(sequence_class, SequenceBase):
            raise ValueError(
                f"{sequence_class.__name__} must be a subclass of SequenceBase"
            )

        # Get name
        seq_name = name or getattr(sequence_class, "name", None)
        if not seq_name or seq_name == "unnamed_sequence":
            raise ValueError(
                f"{sequence_class.__name__} must define a 'name' class attribute"
            )

        # Check for duplicates
        if seq_name in self._sequences:
            existing = self._sequences[seq_name]
            if existing is not sequence_class:
                raise ValueError(
                    f"Sequence '{seq_name}' already registered by {existing.__name__}"
                )
            return  # Already registered with same class

        self._sequences[seq_name] = sequence_class

    def unregister(self, name: str) -> bool:
        """
        Unregister a sequence by name.

        Args:
            name: Sequence name to unregister

        Returns:
            True if unregistered, False if not found
        """
        if name in self._sequences:
            del self._sequences[name]
            return True
        return False

    def get(self, name: str) -> Optional[Type["SequenceBase"]]:
        """
        Get a sequence class by name.

        Args:
            name: Sequence name

        Returns:
            SequenceBase subclass or None if not found
        """
        return self._sequences.get(name)

    def get_or_raise(self, name: str) -> Type["SequenceBase"]:
        """
        Get a sequence class by name, raising if not found.

        Args:
            name: Sequence name

        Returns:
            SequenceBase subclass

        Raises:
            KeyError: If sequence not found
        """
        if name not in self._sequences:
            available = ", ".join(sorted(self._sequences.keys())) or "(none)"
            raise KeyError(
                f"Sequence '{name}' not found. Available: {available}"
            )
        return self._sequences[name]

    def list(self) -> Dict[str, Dict[str, str]]:
        """
        List all registered sequences with metadata.

        Returns:
            Dict mapping name to {version, description, class_name}
        """
        result = {}
        for name, cls in self._sequences.items():
            result[name] = {
                "name": name,
                "version": getattr(cls, "version", "0.0.0"),
                "description": getattr(cls, "description", ""),
                "class_name": cls.__name__,
                "module": cls.__module__,
            }
        return result

    def names(self) -> List[str]:
        """Get list of registered sequence names."""
        return list(self._sequences.keys())

    def __contains__(self, name: str) -> bool:
        """Check if a sequence is registered."""
        return name in self._sequences

    def __len__(self) -> int:
        """Get number of registered sequences."""
        return len(self._sequences)

    def discover(
        self,
        package_name: str,
        recursive: bool = True,
    ) -> List[str]:
        """
        Auto-discover and register sequences from a package.

        Scans the package for SequenceBase subclasses and registers them.

        Args:
            package_name: Package to scan (e.g., "sequences")
            recursive: Whether to scan subpackages

        Returns:
            List of discovered sequence names
        """
        from .base import SequenceBase

        discovered = []

        try:
            package = importlib.import_module(package_name)
        except ImportError as e:
            raise ImportError(f"Cannot import package '{package_name}': {e}")

        # Get package path
        if not hasattr(package, "__path__"):
            # Single module, not a package
            discovered.extend(self._scan_module(package))
            return discovered

        # Iterate over submodules
        prefix = package.__name__ + "."
        for importer, modname, ispkg in pkgutil.walk_packages(
            package.__path__, prefix
        ):
            if not recursive and ispkg:
                continue

            try:
                module = importlib.import_module(modname)
                discovered.extend(self._scan_module(module))
            except ImportError:
                # Skip modules that can't be imported
                continue

        return discovered

    def _scan_module(self, module) -> List[str]:
        """Scan a module for SequenceBase subclasses."""
        from .base import SequenceBase

        discovered = []

        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue

            attr = getattr(module, attr_name, None)
            if not isinstance(attr, type):
                continue

            if not issubclass(attr, SequenceBase):
                continue

            # Skip the base class itself
            if attr is SequenceBase:
                continue

            # Skip classes defined in other modules (imported)
            if attr.__module__ != module.__name__:
                continue

            # Try to register
            try:
                self.register(attr)
                discovered.append(attr.name)
            except ValueError:
                # Already registered or invalid
                pass

        return discovered


# =============================================================================
# Decorator for registration
# =============================================================================


def register_sequence(
    name: Optional[str] = None,
    registry: Optional[SequenceRegistry] = None,
):
    """
    Decorator to register a sequence class.

    Usage:
        @register_sequence()
        class MySequence(SequenceBase):
            name = "my_sequence"
            ...

        # Or with custom name
        @register_sequence(name="custom_name")
        class MySequence(SequenceBase):
            ...
    """
    def decorator(cls: Type["SequenceBase"]) -> Type["SequenceBase"]:
        reg = registry or SequenceRegistry.get_instance()
        reg.register(cls, name)
        return cls

    return decorator


# =============================================================================
# Global registry instance
# =============================================================================

# Global registry for convenience
_global_registry = SequenceRegistry()


def get_sequence(name: str) -> Optional[Type["SequenceBase"]]:
    """Get a sequence from the global registry."""
    return _global_registry.get(name)


def list_sequences() -> Dict[str, Dict[str, str]]:
    """List all sequences in the global registry."""
    return _global_registry.list()


def discover_sequences(package_name: str, recursive: bool = True) -> List[str]:
    """Discover sequences from a package into the global registry."""
    return _global_registry.discover(package_name, recursive)

"""
Backward compatibility decorators for legacy sequence patterns.

This module provides decorators that were previously in station_service.sequence.decorators.
It allows existing sequences using the decorator pattern to continue working with the new SDK.

DEPRECATION NOTICE:
    These decorators are deprecated in favor of the SequenceBase class pattern.
    Please migrate to the new SDK pattern:

    # Old (deprecated):
    @sequence(name="my_test")
    class MyTestSequence:
        @step(order=1)
        async def test_something(self): ...

    # New (recommended):
    class MyTestSequence(SequenceBase):
        name = "my_test"
        async def run(self) -> dict: ...

Usage (deprecated):
    from station_service.sdk.decorators import sequence, step, parameter

    @sequence(name="my_test", description="My test sequence")
    class MyTestSequence:
        @step(order=1, timeout=30.0)
        async def test_something(self) -> dict:
            return {"status": "passed"}
"""

import warnings
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union

from .types import StepMeta

F = TypeVar("F", bound=Callable[..., Any])


# Re-export StepMeta for backward compatibility
# New code should import from .types directly
__all__ = [
    "StepMeta",
    "ParameterMeta",
    "SequenceMeta",
    "sequence",
    "step",
    "parameter",
    "get_sequence_meta",
    "get_step_meta",
    "get_parameter_meta",
    "is_step_method",
    "is_parameter_method",
    "collect_steps_from_decorated_class",
    "collect_parameters_from_decorated_class",
]


@dataclass
class ParameterMeta:
    """Metadata for a parameter getter method."""

    name: str
    display_name: str = ""
    unit: str = ""
    description: str = ""


@dataclass
class SequenceMeta:
    """Metadata for a sequence class."""

    name: str
    description: str = ""
    version: str = "1.0.0"


def sequence(
    name: str,
    description: str = "",
    version: str = "1.0.0",
) -> Callable[[type], type]:
    """
    Decorator to mark a class as a sequence.

    .. deprecated::
        Use SequenceBase class instead. This decorator will be removed in v3.0.

    Args:
        name: Unique identifier for the sequence
        description: Human-readable description
        version: Semantic version string

    Returns:
        Class decorator that adds sequence metadata
    """

    def decorator(cls: type) -> type:
        warnings.warn(
            f"@sequence decorator is deprecated. "
            f"Migrate '{name}' to SequenceBase class pattern. "
            f"See SDK documentation for migration guide.",
            DeprecationWarning,
            stacklevel=3,
        )
        cls._sequence_meta = SequenceMeta(
            name=name,
            description=description,
            version=version,
        )
        # Also add individual attributes for easier access
        if not hasattr(cls, "name"):
            cls.name = name
        if not hasattr(cls, "description"):
            cls.description = description
        if not hasattr(cls, "version"):
            cls.version = version
        return cls

    return decorator


def step(
    order: int,
    timeout: float = 60.0,
    retry: int = 0,
    cleanup: bool = False,
    name: Optional[str] = None,
    condition: Optional[str] = None,
    description: str = "",
) -> Callable[[F], F]:
    """
    Decorator to mark a method as a test step.

    .. deprecated::
        Use SequenceBase with emit_step_start/emit_step_complete instead.
        This decorator will be removed in v3.0.

    Args:
        order: Execution order (lower numbers run first)
        timeout: Maximum execution time in seconds
        retry: Number of retry attempts on failure
        cleanup: If True, always runs even after failures
        name: Override step name (defaults to method name)
        condition: Optional condition expression for conditional execution
        description: Human-readable description

    Returns:
        Method decorator that adds step metadata
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        # Store metadata on the function
        step_name = name if name is not None else func.__name__
        wrapper._step_meta = StepMeta(
            name=step_name,
            order=order,
            timeout=timeout,
            retry=retry,
            cleanup=cleanup,
            condition=condition,
            description=description or func.__doc__ or "",
        )
        # Keep original function reference for async support
        wrapper._original_func = func
        return wrapper  # type: ignore

    return decorator


def parameter(
    name: str,
    display_name: str = "",
    unit: str = "",
    description: str = "",
) -> Callable[[F], F]:
    """
    Decorator to mark a method as a parameter getter.

    Args:
        name: Parameter identifier
        display_name: Human-readable name for UI
        unit: Unit of measurement (e.g., "mm", "C", "V")
        description: Human-readable description

    Returns:
        Method decorator that adds parameter metadata
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._parameter_meta = ParameterMeta(
            name=name,
            display_name=display_name or name,
            unit=unit,
            description=description or func.__doc__ or "",
        )
        return wrapper  # type: ignore

    return decorator


# Helper functions for introspection


def get_sequence_meta(cls: type) -> Optional[SequenceMeta]:
    """Get sequence metadata from a decorated class."""
    return getattr(cls, "_sequence_meta", None)


def get_step_meta(method: Callable) -> Optional[StepMeta]:
    """Get step metadata from a decorated method."""
    return getattr(method, "_step_meta", None)


def get_parameter_meta(method: Callable) -> Optional[ParameterMeta]:
    """Get parameter metadata from a decorated method."""
    return getattr(method, "_parameter_meta", None)


def is_step_method(method: Callable) -> bool:
    """Check if a method is decorated as a step."""
    return hasattr(method, "_step_meta")


def is_parameter_method(method: Callable) -> bool:
    """Check if a method is decorated as a parameter getter."""
    return hasattr(method, "_parameter_meta")


def collect_steps_from_decorated_class(cls: type) -> list[tuple[str, Callable, StepMeta]]:
    """
    Collect all step methods from a decorated sequence class.

    Returns:
        List of (name, method, meta) tuples sorted by order
    """
    steps = []
    for attr_name in dir(cls):
        if attr_name.startswith("_"):
            continue
        attr = getattr(cls, attr_name, None)
        if attr is None:
            continue
        meta = get_step_meta(attr)
        if meta is not None:
            steps.append((meta.name, attr, meta))
    return sorted(steps, key=lambda x: x[2].order)


def collect_parameters_from_decorated_class(
    cls: type,
) -> list[tuple[str, Callable, ParameterMeta]]:
    """
    Collect all parameter methods from a decorated sequence class.

    Returns:
        List of (name, method, meta) tuples
    """
    params = []
    for attr_name in dir(cls):
        if attr_name.startswith("_"):
            continue
        attr = getattr(cls, attr_name, None)
        if attr is None:
            continue
        meta = get_parameter_meta(attr)
        if meta is not None:
            params.append((meta.name, attr, meta))
    return params

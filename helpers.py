"""
Compatibility helpers for transitioning from legacy decorators to SDK.

This module provides functions that work with both legacy decorator-based
sequences and new SDK-based sequences.
"""

from typing import Any, Callable, List, Optional, Tuple, Type, TYPE_CHECKING

from .types import StepInfo, StepMeta

if TYPE_CHECKING:
    from .manifest import SequenceManifest


# Re-export for backward compatibility
__all__ = [
    "StepInfo",
    "StepMeta",
    "collect_steps",
    "collect_steps_from_manifest",
    "collect_steps_from_class",
]


def collect_steps_from_manifest(manifest: "SequenceManifest") -> List[StepInfo]:
    """
    Collect step information from a manifest.

    Args:
        manifest: The sequence manifest with step definitions

    Returns:
        List of StepInfo objects sorted by order
    """
    steps = []
    for step_def in manifest.steps:
        steps.append(
            StepInfo(
                name=step_def.name,
                display_name=step_def.display_name or step_def.name,
                order=step_def.order,
                timeout=step_def.timeout,
                retry=step_def.retry,
                cleanup=step_def.cleanup,
                description="",
                method=None,
            )
        )
    return sorted(steps, key=lambda x: x.order)


def collect_steps_from_class(cls: Type) -> List[StepInfo]:
    """
    Collect step information from a sequence class.

    Works with both legacy decorator-based sequences (using @step decorator)
    and SDK-based sequences (SequenceBase subclasses).

    Args:
        cls: The sequence class to inspect

    Returns:
        List of StepInfo objects sorted by order
    """
    steps: List[StepInfo] = []

    # Try to get steps from legacy decorators
    for name in dir(cls):
        if name.startswith("_"):
            continue

        attr = getattr(cls, name, None)
        if attr is None:
            continue

        # Check for legacy @step decorator metadata
        step_meta = getattr(attr, "_step_meta", None)
        if step_meta is not None:
            steps.append(
                StepInfo(
                    name=step_meta.name or name,
                    display_name=step_meta.name or name,
                    order=step_meta.order,
                    timeout=step_meta.timeout,
                    retry=step_meta.retry,
                    cleanup=step_meta.cleanup,
                    description=step_meta.description or "",
                    method=attr,
                )
            )

    # Sort by order
    return sorted(steps, key=lambda x: x.order)


def collect_steps(
    cls: Type,
    manifest: Optional["SequenceManifest"] = None,
) -> List[Tuple[str, Optional[Callable], Any]]:
    """
    Collect steps from a sequence class or manifest.

    This is a compatibility wrapper that returns data in the same format
    as the legacy collect_steps function.

    Args:
        cls: The sequence class
        manifest: Optional manifest (used for SDK sequences)

    Returns:
        List of (method_name, method, step_meta) tuples for legacy compatibility
    """
    # Check if this is an SDK-based sequence
    from .base import SequenceBase

    if manifest is not None and manifest.is_cli_mode():
        # Use manifest steps for CLI mode
        steps = collect_steps_from_manifest(manifest)
    elif issubclass(cls, SequenceBase):
        # SDK sequence without manifest - try to get from class
        steps = collect_steps_from_class(cls)
        if not steps:
            # No decorator-based steps, return empty
            return []
    else:
        # Legacy decorator-based sequence
        steps = collect_steps_from_class(cls)

    # Convert to legacy format for backward compatibility
    result = []
    for step in steps:
        # Create a StepMeta object for compatibility
        step_meta = StepMeta(
            name=step.name,
            order=step.order,
            timeout=step.timeout,
            retry=step.retry,
            cleanup=step.cleanup,
            description=step.description,
        )
        result.append((step.name, step.method, step_meta))

    return result

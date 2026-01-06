"""Compatibility module for Station Service SDK.

Contains backward-compatible components:
- Decorators: Legacy @sequence, @step, @parameter decorators
- Dependencies: Package dependency management
- Legacy CLI: Original CLI implementation
- Sequence CLI: CLI argument parsing utilities
"""

from station_service_sdk.compat.decorators import (
    sequence,
    step,
    parameter,
    SequenceMeta,
    StepMeta as DecoratorStepMeta,
    ParameterMeta,
    get_sequence_meta,
    get_step_meta,
    get_parameter_meta,
    is_step_method,
    is_parameter_method,
    collect_steps_from_decorated_class,
    collect_parameters_from_decorated_class,
)
from station_service_sdk.compat.dependencies import (
    ensure_package,
    ensure_dependencies,
    is_installed,
    check_dependencies,
    get_missing_packages,
    parse_pyproject_dependencies,
    install_sequence_dependencies,
    get_pyproject_missing_packages,
)
from station_service_sdk.compat.sequence_cli import (
    parse_args,
    CLIArgs,
)

__all__ = [
    # Decorators
    "sequence",
    "step",
    "parameter",
    "SequenceMeta",
    "DecoratorStepMeta",
    "ParameterMeta",
    "get_sequence_meta",
    "get_step_meta",
    "get_parameter_meta",
    "is_step_method",
    "is_parameter_method",
    "collect_steps_from_decorated_class",
    "collect_parameters_from_decorated_class",
    # Dependencies
    "ensure_package",
    "ensure_dependencies",
    "is_installed",
    "check_dependencies",
    "get_missing_packages",
    "parse_pyproject_dependencies",
    "install_sequence_dependencies",
    "get_pyproject_missing_packages",
    # CLI
    "parse_args",
    "CLIArgs",
]

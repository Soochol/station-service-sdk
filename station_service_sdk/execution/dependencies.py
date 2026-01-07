"""Re-export dependencies from compat for backward compatibility."""
from station_service_sdk.compat.dependencies import (
    get_missing_packages,
    parse_pyproject_dependencies,
)

__all__ = ["get_missing_packages", "parse_pyproject_dependencies"]

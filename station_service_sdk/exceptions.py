"""
SDK Exception classes for sequence execution.

This module provides a comprehensive exception hierarchy for handling
various error conditions during sequence execution.
"""

from typing import Any, Dict, Optional


# =============================================================================
# Base Exception
# =============================================================================


class SequenceError(Exception):
    """
    Base exception for all sequence-related errors.

    Attributes:
        message: Human-readable error message
        code: Machine-readable error code for categorization
        details: Additional context as a dictionary
    """

    def __init__(
        self,
        message: str,
        code: str = "SEQUENCE_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"[{self.code}] {self.message} - Details: {self.details}"
        return f"[{self.code}] {self.message}"


# =============================================================================
# Lifecycle Errors
# =============================================================================


class SetupError(SequenceError):
    """Error during sequence setup phase."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="SETUP_ERROR", details=details)


class TeardownError(SequenceError):
    """Error during sequence teardown phase."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="TEARDOWN_ERROR", details=details)


# =============================================================================
# Execution Errors
# =============================================================================


class StepError(SequenceError):
    """Error during step execution."""

    def __init__(
        self,
        message: str,
        step_name: str = "",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.step_name = step_name
        super().__init__(message, code="STEP_ERROR", details=details)


class SequenceTimeoutError(SequenceError):
    """Timeout during sequence or step execution.

    Note: Named SequenceTimeoutError to avoid shadowing builtins.TimeoutError.
    """

    def __init__(
        self,
        message: str,
        timeout_seconds: float = 0,
        elapsed_seconds: Optional[float] = None,
        step_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.elapsed_seconds = elapsed_seconds
        self.step_name = step_name
        super().__init__(message, code="TIMEOUT_ERROR", details=details)

    def __str__(self) -> str:
        base_msg = f"[{self.code}] {self.message}"
        if self.timeout_seconds:
            base_msg = f"{base_msg} (timeout={self.timeout_seconds}s"
            if self.elapsed_seconds is not None:
                base_msg = f"{base_msg}, elapsed={self.elapsed_seconds:.2f}s)"
            else:
                base_msg = f"{base_msg})"
        if self.details:
            base_msg = f"{base_msg} - Details: {self.details}"
        return base_msg


# Backward compatibility alias (shadows builtins.TimeoutError intentionally for legacy code)
TimeoutError = SequenceTimeoutError


class AbortError(SequenceError):
    """Sequence was aborted by user or system."""

    def __init__(
        self,
        message: str = "Sequence aborted",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code="ABORT_ERROR", details=details)


# =============================================================================
# Test Result Errors
# =============================================================================


class TestFailure(SequenceError):
    """Exception for test verification failures."""

    def __init__(
        self,
        message: str,
        step_name: Optional[str] = None,
        actual: Any = None,
        limit: Any = None,
        limit_type: Optional[str] = None,  # "min", "max", "range", "equals"
        details: Optional[Dict[str, Any]] = None,
    ):
        self.step_name = step_name
        self.actual = actual
        self.limit = limit
        self.limit_type = limit_type
        super().__init__(message, code="TEST_FAILURE", details=details)

    def __str__(self) -> str:
        base_msg = f"[{self.code}] {self.message}"
        if self.actual is not None and self.limit is not None:
            base_msg = f"{base_msg} (actual={self.actual}, limit={self.limit})"
        if self.details:
            base_msg = f"{base_msg} - Details: {self.details}"
        return base_msg


class TestSkipped(SequenceError):
    """Exception for skipped tests."""

    def __init__(
        self,
        message: str,
        step_name: Optional[str] = None,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.step_name = step_name
        self.reason = reason
        super().__init__(message, code="TEST_SKIPPED", details=details)


# =============================================================================
# Hardware Errors
# =============================================================================


class HardwareError(SequenceError):
    """Base exception for hardware-related errors."""

    def __init__(
        self,
        message: str,
        device: str = "",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.device = device
        super().__init__(message, code="HARDWARE_ERROR", details=details)


class HardwareConnectionError(HardwareError):
    """Exception for driver connection errors.

    Note: Named HardwareConnectionError to avoid shadowing builtins.ConnectionError.
    """

    def __init__(
        self,
        message: str,
        device: str = "",
        host: Optional[str] = None,
        port: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.host = host
        self.port = port
        super().__init__(message, device=device, details=details)
        self.code = "CONNECTION_ERROR"


# Backward compatibility alias (shadows builtins.ConnectionError intentionally for legacy code)
ConnectionError = HardwareConnectionError


class CommunicationError(HardwareError):
    """Exception for driver communication errors."""

    def __init__(
        self,
        message: str,
        device: str = "",
        command: Optional[str] = None,
        response: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.command = command
        self.response = response
        super().__init__(message, device=device, details=details)
        self.code = "COMMUNICATION_ERROR"


# =============================================================================
# Package/Manifest Errors
# =============================================================================


class PackageError(SequenceError):
    """Exception for package structure and validation errors."""

    def __init__(
        self,
        message: str,
        package_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.package_name = package_name
        super().__init__(message, code="PACKAGE_ERROR", details=details)


class ManifestError(PackageError):
    """Exception for manifest parsing and validation errors."""

    def __init__(
        self,
        message: str,
        package_name: Optional[str] = None,
        manifest_path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.manifest_path = manifest_path
        super().__init__(message, package_name=package_name, details=details)
        self.code = "MANIFEST_ERROR"


# =============================================================================
# Configuration/Validation Errors
# =============================================================================


class ValidationError(SequenceError):
    """Parameter or configuration validation error."""

    def __init__(
        self,
        message: str,
        field: str = "",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.field = field
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class DependencyError(SequenceError):
    """Missing or incompatible dependency."""

    def __init__(
        self,
        message: str,
        dependency: str = "",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.dependency = dependency
        super().__init__(message, code="DEPENDENCY_ERROR", details=details)


# =============================================================================
# Backward Compatibility Aliases
# =============================================================================

# These aliases maintain backward compatibility with sequence/ module names
DriverError = HardwareError
ExecutionError = StepError
StepTimeoutError = TimeoutError

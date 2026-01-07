"""Re-export base from core for backward compatibility."""
from station_service_sdk.core.base import SequenceBase, StepResult

__all__ = ["SequenceBase", "StepResult"]

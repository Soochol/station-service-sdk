"""
Sequence Simulator Module.

Provides simulation capabilities for sequence execution with mock hardware.
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .loader import SequenceLoader
    from .manifest import SequenceManifest

from .helpers import collect_steps
from .context import ExecutionContext
from .base import SequenceBase
from .interfaces import OutputStrategy

logger = logging.getLogger(__name__)


class DryRunOutputStrategy(OutputStrategy):
    """
    Output strategy that captures output for dry run results.

    Collects step results and measurements without printing to stdout.
    """

    def __init__(self):
        self.step_results: List[Dict[str, Any]] = []
        self.measurements: Dict[str, Any] = {}
        self.logs: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self._current_step: Optional[Dict[str, Any]] = None

    def log(self, level: str, message: str, **extra: Any) -> None:
        self.logs.append({"level": level, "message": message, **extra})

    def status(self, status: str, progress: float, step: Optional[str] = None, message: Optional[str] = None) -> None:
        pass  # Ignore status updates for dry run

    def step_start(self, step_name: str, index: int, total: int, description: str = "") -> None:
        self._current_step = {
            "name": step_name,
            "index": index,
            "total": total,
            "description": description,
            "started_at": datetime.now().isoformat(),
        }

    def step_complete(
        self,
        step_name: str,
        index: int,
        passed: bool,
        duration: float,
        measurements: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        step_result = {
            "name": step_name,
            "index": index,
            "passed": passed,
            "duration": duration,
            "measurements": measurements or {},
            "error": error,
            "data": data or {},
            "completed_at": datetime.now().isoformat(),
        }
        if self._current_step:
            step_result["started_at"] = self._current_step.get("started_at")
        self.step_results.append(step_result)
        self._current_step = None

    def measurement(
        self,
        name: str,
        value: Any,
        unit: str = "",
        passed: Optional[bool] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        step_name: Optional[str] = None,
    ) -> None:
        self.measurements[name] = {
            "value": value,
            "unit": unit,
            "passed": passed,
            "min": min_value,
            "max": max_value,
            "step": step_name,
        }

    def error(self, code: str, message: str, step: Optional[str] = None, recoverable: bool = False) -> None:
        self.errors.append({
            "code": code,
            "message": message,
            "step": step,
            "recoverable": recoverable,
        })

    def sequence_complete(
        self,
        overall_pass: bool,
        duration: float,
        steps: List[Dict[str, Any]],
        measurements: Dict[str, Any],
        error: Optional[str] = None,
    ) -> None:
        pass  # Handled externally

    def input_request(
        self,
        request_id: str,
        prompt: str,
        input_type: str,
        options: Optional[List[str]] = None,
        default: Any = None,
        timeout: float = 300,
    ) -> None:
        pass  # Not supported in dry run

    def wait_for_input(self, request_id: str, timeout: float = 300) -> Any:
        return None  # Auto-respond for dry run


class SequenceSimulator:
    """
    Sequence simulator for dry-run execution.

    Executes sequences with mock hardware to validate sequence logic
    without requiring actual hardware connections.
    """

    def __init__(self, sequence_loader: "SequenceLoader") -> None:
        """
        Initialize the simulator.

        Args:
            sequence_loader: Sequence loader for loading packages
        """
        self.sequence_loader = sequence_loader

    async def dry_run(
        self,
        sequence_name: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a sequence in dry-run mode with mock hardware.

        Args:
            sequence_name: Name of the sequence to simulate
            parameters: Optional parameter overrides

        Returns:
            Dict containing execution results
        """
        result: Dict[str, Any] = {
            "status": "completed",
            "overall_pass": True,
            "started_at": datetime.now().isoformat(),
            "steps": [],
            "error": None,
        }

        try:
            # Load the manifest and class
            manifest = await self.sequence_loader.load_package(sequence_name)
            package_path = self.sequence_loader.get_package_path(sequence_name)
            sequence_class = await self.sequence_loader.load_sequence_class(
                manifest, package_path
            )

            # Merge parameters
            final_params = {}
            for param_name, param_def in manifest.parameters.items():
                final_params[param_name] = param_def.default
            if parameters:
                final_params.update(parameters)

            # Create execution context for dry run
            context = ExecutionContext(
                execution_id=f"dry-run-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                sequence_name=manifest.name,
                sequence_version=manifest.version,
                parameters=final_params,
                dry_run=True,
            )

            # Create mock hardware and add to context
            mock_hardware = self._create_mock_hardware(manifest)
            context.hardware = mock_hardware

            # Check if this is an SDK 2.0 SequenceBase class
            if issubclass(sequence_class, SequenceBase):
                # Use _execute() lifecycle with DryRunOutputStrategy
                output_strategy = DryRunOutputStrategy()
                sequence_instance = sequence_class(
                    context=context,
                    hardware_config={},
                    parameters=final_params,
                    output_strategy=output_strategy,
                )

                # Execute using the SequenceBase lifecycle
                exec_result = await sequence_instance._execute()

                # Extract results from output strategy
                result["steps"] = output_strategy.step_results
                result["measurements"] = output_strategy.measurements
                result["logs"] = output_strategy.logs
                result["overall_pass"] = exec_result.get("passed", False)

                if exec_result.get("error"):
                    result["error"] = exec_result["error"]
                    result["status"] = "failed"

            else:
                # Legacy @step decorated sequences - use old approach
                sequence_instance = sequence_class(
                    context=context,
                    hardware_config={},
                    parameters=final_params,
                )

                # Get and sort steps
                steps = collect_steps(sequence_class, manifest)
                regular_steps = [s for s in steps if not s[2].cleanup]
                cleanup_steps = [s for s in steps if s[2].cleanup]

                # Execute regular steps
                for method_name, method, step_meta in regular_steps:
                    step_result = await self._execute_step(
                        sequence_instance, method_name, method, step_meta
                    )
                    result["steps"].append(step_result)

                    if step_result["status"] == "failed":
                        result["overall_pass"] = False
                        # Continue to cleanup steps on failure

                # Execute cleanup steps
                for method_name, method, step_meta in cleanup_steps:
                    step_result = await self._execute_step(
                        sequence_instance, method_name, method, step_meta
                    )
                    result["steps"].append(step_result)

                if not result["overall_pass"]:
                    result["status"] = "failed"

            result["completed_at"] = datetime.now().isoformat()

        except Exception as e:
            logger.exception(f"Dry run failed: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
            result["completed_at"] = datetime.now().isoformat()

        return result

    async def _execute_step(
        self,
        sequence_instance: Any,
        method_name: str,
        method: Any,
        step_meta: Any,
    ) -> Dict[str, Any]:
        """
        Execute a single step with timeout handling.

        Args:
            sequence_instance: The sequence instance
            method_name: Name of the step method
            method: The step method
            step_meta: Step metadata

        Returns:
            Dict containing step result
        """
        step_result: Dict[str, Any] = {
            "name": step_meta.name or method_name,
            "order": step_meta.order,
            "status": "passed",
            "started_at": datetime.now().isoformat(),
            "duration": 0.0,
            "result": None,
            "error": None,
        }

        start_time = datetime.now()
        retries = 0
        max_retries = step_meta.retry

        while retries <= max_retries:
            try:
                # Execute with timeout
                bound_method = getattr(sequence_instance, method_name)
                execution_result = await asyncio.wait_for(
                    bound_method(),
                    timeout=step_meta.timeout,
                )

                step_result["result"] = execution_result
                step_result["duration"] = (datetime.now() - start_time).total_seconds()

                # Check if step passed
                if isinstance(execution_result, dict):
                    if execution_result.get("status") == "failed":
                        step_result["status"] = "failed"
                        step_result["error"] = execution_result.get("error")

                break  # Success, exit retry loop

            except asyncio.TimeoutError:
                retries += 1
                if retries > max_retries:
                    step_result["status"] = "failed"
                    step_result["error"] = f"Step timed out after {step_meta.timeout}s"
                    step_result["duration"] = step_meta.timeout
                else:
                    logger.debug(f"Step {method_name} timed out, retrying ({retries}/{max_retries})")

            except Exception as e:
                retries += 1
                if retries > max_retries:
                    step_result["status"] = "failed"
                    step_result["error"] = str(e)
                    step_result["duration"] = (datetime.now() - start_time).total_seconds()
                else:
                    logger.debug(f"Step {method_name} failed, retrying ({retries}/{max_retries})")

        step_result["completed_at"] = datetime.now().isoformat()
        return step_result

    def _create_mock_hardware(self, manifest: "SequenceManifest") -> Dict[str, Any]:
        """
        Create mock hardware instances based on manifest.

        Args:
            manifest: Sequence manifest with hardware definitions

        Returns:
            Dict mapping hardware names to mock instances
        """
        mock_hardware: Dict[str, Any] = {}

        for hw_name, hw_def in manifest.hardware.items():
            # Create a generic mock object
            mock_hardware[hw_name] = MockHardware(
                name=hw_name,
                display_name=hw_def.display_name,
            )

        return mock_hardware


class MockHardware:
    """
    Generic mock hardware driver for simulation.

    Provides basic async methods that simulate hardware operations
    with configurable delays and success rates.
    """

    def __init__(
        self,
        name: str,
        display_name: str,
        success_rate: float = 0.95,
        min_delay: float = 0.05,
        max_delay: float = 0.2,
    ) -> None:
        """
        Initialize mock hardware.

        Args:
            name: Hardware identifier
            display_name: Human-readable name
            success_rate: Probability of operations succeeding (0-1)
            min_delay: Minimum simulated delay in seconds
            max_delay: Maximum simulated delay in seconds
        """
        self.name = name
        self.display_name = display_name
        self.success_rate = success_rate
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._connected = False

    async def connect(self) -> bool:
        """Simulate hardware connection."""
        await self._simulate_delay()
        self._connected = random.random() < self.success_rate
        return self._connected

    async def disconnect(self) -> None:
        """Simulate hardware disconnection."""
        await self._simulate_delay()
        self._connected = False

    async def reset(self) -> None:
        """Simulate hardware reset."""
        await self._simulate_delay()

    async def identify(self) -> str:
        """Return mock identification string."""
        return f"MockHardware,{self.name},SIM001,1.0.0"

    async def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    async def measure(self, **kwargs) -> float:
        """Simulate a measurement."""
        await self._simulate_delay()
        return round(random.uniform(0.0, 10.0), 4)

    async def measure_voltage(self, **kwargs) -> float:
        """Simulate voltage measurement."""
        await self._simulate_delay()
        return round(random.gauss(3.3, 0.1), 4)

    async def measure_current(self, **kwargs) -> float:
        """Simulate current measurement."""
        await self._simulate_delay()
        return round(random.gauss(0.1, 0.01), 4)

    async def read_sensor(self, **kwargs) -> float:
        """Simulate sensor reading."""
        await self._simulate_delay()
        reference = kwargs.get("reference", 100.0)
        return round(random.gauss(reference, reference * 0.02), 4)

    async def warmup(self, duration: float = 1.0) -> bool:
        """Simulate warmup period."""
        await asyncio.sleep(min(duration, 0.5))  # Cap at 0.5s for simulation
        return True

    async def calibrate(self, **kwargs) -> Dict[str, Any]:
        """Simulate calibration."""
        await self._simulate_delay()
        return {
            "success": True,
            "offset_applied": round(random.uniform(-0.1, 0.1), 4),
        }

    async def measure_all_points(self, num_points: int = 5) -> Dict[int, float]:
        """Simulate measuring multiple points."""
        results = {}
        for i in range(1, num_points + 1):
            results[i] = await self.measure_voltage()
        return results

    async def verify_calibration(self, **kwargs) -> Dict[str, Any]:
        """Simulate calibration verification."""
        await self._simulate_delay()
        reference = kwargs.get("reference_value", 100.0)
        tolerance = kwargs.get("tolerance_percent", 5.0)
        measured = random.gauss(reference, reference * 0.02)
        deviation = abs(measured - reference) / reference * 100

        return {
            "reference": reference,
            "measured_avg": round(measured, 4),
            "deviation_percent": round(deviation, 2),
            "tolerance_percent": tolerance,
            "passed": deviation <= tolerance,
        }

    # PSA MCU specific methods
    async def ping(self) -> str:
        """Simulate MCU ping - returns firmware version."""
        await self._simulate_delay()
        return "SIM-1.0.0"

    async def get_sensor_list(self) -> List[Dict[str, Any]]:
        """Simulate getting sensor list."""
        await self._simulate_delay()
        return [
            {"name": "VL53L0X", "type": "distance", "status": "ok"},
            {"name": "MLX90640", "type": "thermal", "status": "ok"},
        ]

    async def test_vl53l0x(
        self, target_mm: float = 500, tolerance_mm: float = 100
    ) -> Dict[str, Any]:
        """Simulate VL53L0X distance sensor test."""
        await self._simulate_delay()
        # Simulate measurement near target with some variance
        measured = round(random.gauss(target_mm, tolerance_mm * 0.3), 1)
        passed = abs(measured - target_mm) <= tolerance_mm

        return {
            "passed": passed,
            "measured_mm": measured,
            "target_mm": target_mm,
            "tolerance_mm": tolerance_mm,
            "status_name": "PASS" if passed else "OUT_OF_RANGE",
        }

    async def test_mlx90640(
        self, target_celsius: float = 25.0, tolerance_celsius: float = 10.0
    ) -> Dict[str, Any]:
        """Simulate MLX90640 thermal sensor test."""
        await self._simulate_delay()
        # Simulate temperature near target
        measured = round(random.gauss(target_celsius, tolerance_celsius * 0.2), 2)
        passed = abs(measured - target_celsius) <= tolerance_celsius

        return {
            "passed": passed,
            "measured_celsius": measured,
            "target_celsius": target_celsius,
            "tolerance_celsius": tolerance_celsius,
            "status_name": "PASS" if passed else "OUT_OF_RANGE",
        }

    async def _simulate_delay(self) -> None:
        """Add realistic delay to operations."""
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)

    def __getattr__(self, name: str) -> Any:
        """
        Handle any undefined method calls gracefully.

        Returns an async function that simulates the operation.
        """
        async def mock_method(*args, **kwargs) -> Any:
            await self._simulate_delay()
            return {"success": True, "method": name}

        return mock_method

"""
Interactive Sequence Simulator Module.

Provides interactive step-by-step simulation capabilities for sequence testing.
Unlike the dry_run mode which executes all steps automatically, this allows
UI-driven step execution with state management.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .loader import SequenceLoader
    from .manifest import SequenceManifest

from .helpers import collect_steps
from .context import ExecutionContext
from .base import SequenceBase
from .simulator import DryRunOutputStrategy, MockHardware
from .types import SimulationResult

logger = logging.getLogger(__name__)


class SimulationSessionStatus(str, Enum):
    """Status of a simulation session."""
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class StepExecutionStatus(str, Enum):
    """Status of a step execution."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepState:
    """State of a single step in the simulation."""
    name: str
    display_name: str
    order: int
    status: StepExecutionStatus = StepExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: float = 0.0
    result: Optional[Dict[str, Any]] = None
    measurements: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "name": self.name,
            "displayName": self.display_name,
            "order": self.order,
            "status": self.status.value,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "result": self.result,
            "measurements": self.measurements,
            "error": self.error,
        }


@dataclass
class SimulationSession:
    """
    A simulation session for interactive step-by-step execution.

    Maintains state across multiple step executions and allows
    pause/resume/abort operations.
    """
    id: str
    sequence_name: str
    sequence_version: str
    status: SimulationSessionStatus = SimulationSessionStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step_index: int = 0
    steps: List[StepState] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    hardware_config: Dict[str, Any] = field(default_factory=dict)
    overall_pass: bool = True
    error: Optional[str] = None

    # Internal state (not serialized)
    _sequence_instance: Optional[SequenceBase] = field(default=None, repr=False)
    _context: Optional[ExecutionContext] = field(default=None, repr=False)
    _output_strategy: Optional[DryRunOutputStrategy] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "sequenceName": self.sequence_name,
            "sequenceVersion": self.sequence_version,
            "status": self.status.value,
            "createdAt": self.created_at.isoformat(),
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "currentStepIndex": self.current_step_index,
            "steps": [s.to_dict() for s in self.steps],
            "parameters": self.parameters,
            "overallPass": self.overall_pass,
            "error": self.error,
        }

    def get_current_step(self) -> Optional[StepState]:
        """Get the current step to execute."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def get_step_by_name(self, name: str) -> Optional[StepState]:
        """Get a step by its name."""
        for step in self.steps:
            if step.name == name:
                return step
        return None

    def advance_to_next_pending(self) -> Optional[StepState]:
        """Advance to the next pending step."""
        for i, step in enumerate(self.steps):
            if step.status == StepExecutionStatus.PENDING:
                self.current_step_index = i
                return step
        return None


class InteractiveSimulator:
    """
    Interactive sequence simulator for step-by-step execution.

    Provides session-based simulation with:
    - Individual step execution
    - Step skipping
    - Parameter overrides per step
    - Session pause/resume/abort
    - Full state inspection

    Usage:
        loader = SequenceLoader("sequences")
        simulator = InteractiveSimulator(loader)

        # Create a session
        session = await simulator.create_session("psa_sensor_test", {"port": "/dev/ttyUSB0"})

        # Initialize (runs setup)
        await simulator.initialize_session(session.id)

        # Execute steps one by one
        result = await simulator.run_step(session.id, "test_vl53l0x")
        result = await simulator.run_step(session.id, "test_mlx90640")

        # Or skip a step
        await simulator.skip_step(session.id, "test_mlx90640")

        # Finalize (runs teardown)
        await simulator.finalize_session(session.id)
    """

    def __init__(self, sequence_loader: "SequenceLoader") -> None:
        """
        Initialize the interactive simulator.

        Args:
            sequence_loader: Sequence loader for loading packages
        """
        self.sequence_loader = sequence_loader
        self._sessions: Dict[str, SimulationSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        sequence_name: str,
        parameters: Optional[Dict[str, Any]] = None,
        hardware_config: Optional[Dict[str, Any]] = None,
    ) -> SimulationSession:
        """
        Create a new simulation session.

        Args:
            sequence_name: Name of the sequence to simulate
            parameters: Optional parameter overrides
            hardware_config: Optional hardware configuration

        Returns:
            Created SimulationSession

        Raises:
            PackageError: If sequence not found
        """
        # Load manifest and class
        manifest = await self.sequence_loader.load_package(sequence_name)
        package_path = self.sequence_loader.get_package_path(sequence_name)
        sequence_class = await self.sequence_loader.load_sequence_class(
            manifest, package_path
        )

        # Merge parameters with defaults
        final_params = {}
        for param_name, param_def in manifest.parameters.items():
            final_params[param_name] = param_def.default
        if parameters:
            final_params.update(parameters)

        # Create session
        session_id = str(uuid.uuid4())[:8]
        session = SimulationSession(
            id=session_id,
            sequence_name=manifest.name,
            sequence_version=manifest.version,
            parameters=final_params,
            hardware_config=hardware_config or {},
        )

        # Build step states from manifest/class
        steps = collect_steps(sequence_class, manifest)
        for method_name, method, step_meta in steps:
            session.steps.append(StepState(
                name=step_meta.name or method_name,
                display_name=(step_meta.name or method_name).replace("_", " ").title(),
                order=step_meta.order,
            ))

        # Sort steps by order
        session.steps.sort(key=lambda s: s.order)

        # Store session
        async with self._lock:
            self._sessions[session_id] = session

        logger.info(f"Created simulation session {session_id} for {sequence_name}")
        return session

    async def initialize_session(self, session_id: str) -> SimulationSession:
        """
        Initialize a simulation session (run setup).

        Args:
            session_id: Session ID to initialize

        Returns:
            Updated SimulationSession

        Raises:
            ValueError: If session not found or in invalid state
        """
        session = self._get_session(session_id)

        if session.status not in (SimulationSessionStatus.CREATED, SimulationSessionStatus.READY):
            raise ValueError(f"Session {session_id} is not in a valid state for initialization")

        try:
            # Load manifest and class again (for fresh instance)
            manifest = await self.sequence_loader.load_package(session.sequence_name)
            package_path = self.sequence_loader.get_package_path(session.sequence_name)
            sequence_class = await self.sequence_loader.load_sequence_class(
                manifest, package_path
            )

            # Create execution context
            context = ExecutionContext(
                execution_id=f"sim-{session.id}",
                sequence_name=session.sequence_name,
                sequence_version=session.sequence_version,
                parameters=session.parameters,
                dry_run=True,
            )

            # Create mock hardware
            mock_hardware = self._create_mock_hardware(manifest)
            context.hardware = mock_hardware

            # Create output strategy
            output_strategy = DryRunOutputStrategy()

            # Create sequence instance
            sequence_instance = sequence_class(
                context=context,
                hardware_config=session.hardware_config,
                parameters=session.parameters,
                output_strategy=output_strategy,
            )

            # Store internal state
            session._sequence_instance = sequence_instance
            session._context = context
            session._output_strategy = output_strategy

            # Run setup
            session.started_at = datetime.now()
            session.status = SimulationSessionStatus.RUNNING

            await sequence_instance.setup()

            session.status = SimulationSessionStatus.READY
            logger.info(f"Initialized session {session_id}")

        except Exception as e:
            session.status = SimulationSessionStatus.FAILED
            session.error = f"Setup failed: {str(e)}"
            logger.exception(f"Session {session_id} setup failed: {e}")
            raise

        return session

    async def run_step(
        self,
        session_id: str,
        step_name: str,
        parameter_overrides: Optional[Dict[str, Any]] = None,
    ) -> StepState:
        """
        Execute a single step in the simulation.

        Args:
            session_id: Session ID
            step_name: Name of the step to execute
            parameter_overrides: Optional parameter overrides for this step

        Returns:
            Updated StepState

        Raises:
            ValueError: If session/step not found or in invalid state
        """
        session = self._get_session(session_id)

        if session.status not in (SimulationSessionStatus.READY, SimulationSessionStatus.PAUSED):
            raise ValueError(f"Session {session_id} is not ready for step execution")

        step = session.get_step_by_name(step_name)
        if step is None:
            raise ValueError(f"Step '{step_name}' not found in session {session_id}")

        if step.status not in (StepExecutionStatus.PENDING, StepExecutionStatus.FAILED):
            raise ValueError(f"Step '{step_name}' is not in a runnable state")

        # Apply parameter overrides
        if parameter_overrides:
            session.parameters.update(parameter_overrides)
            if session._sequence_instance:
                session._sequence_instance.parameters.update(parameter_overrides)

        # Execute the step
        step.status = StepExecutionStatus.RUNNING
        step.started_at = datetime.now()
        session.status = SimulationSessionStatus.RUNNING

        try:
            sequence = session._sequence_instance
            if sequence is None:
                raise ValueError("Session not initialized")

            # Find and call the step method
            method = getattr(sequence, step_name, None)
            if method is None:
                # Try to find in the run() method context
                # For SDK 2.0 sequences, steps are executed within run()
                # We need to simulate this
                step.result = await self._simulate_step(session, step_name)
            else:
                step.result = await method()

            step.status = StepExecutionStatus.PASSED
            step.completed_at = datetime.now()
            step.duration = (step.completed_at - step.started_at).total_seconds()

            # Collect measurements from output strategy
            if session._output_strategy:
                step.measurements = session._output_strategy.measurements.copy()

            logger.info(f"Step {step_name} completed in session {session_id}")

        except Exception as e:
            step.status = StepExecutionStatus.FAILED
            step.error = str(e)
            step.completed_at = datetime.now()
            step.duration = (step.completed_at - step.started_at).total_seconds()
            session.overall_pass = False
            logger.warning(f"Step {step_name} failed in session {session_id}: {e}")

        # Update session status
        session.status = SimulationSessionStatus.READY
        session.advance_to_next_pending()

        # Check if all steps are done
        if all(s.status != StepExecutionStatus.PENDING for s in session.steps):
            session.status = SimulationSessionStatus.COMPLETED
            session.completed_at = datetime.now()

        return step

    async def _simulate_step(
        self,
        session: SimulationSession,
        step_name: str,
    ) -> Dict[str, Any]:
        """
        Simulate a step execution using mock hardware.

        For SDK 2.0 sequences where steps are embedded in run(),
        we simulate the step using the mock hardware directly.
        """
        context = session._context
        if context is None or context.hardware is None:
            return {"simulated": True, "status": "passed"}

        # Get the mock hardware
        mock_hardware = context.hardware

        # Try to call corresponding method on mock hardware
        for hw_name, hw in mock_hardware.items():
            if hasattr(hw, step_name):
                method = getattr(hw, step_name)
                result = await method()
                return result

        # Default simulation result
        return {
            "simulated": True,
            "status": "passed",
            "step_name": step_name,
        }

    async def skip_step(self, session_id: str, step_name: str) -> StepState:
        """
        Skip a step in the simulation.

        Args:
            session_id: Session ID
            step_name: Name of the step to skip

        Returns:
            Updated StepState

        Raises:
            ValueError: If session/step not found or step not skippable
        """
        session = self._get_session(session_id)

        step = session.get_step_by_name(step_name)
        if step is None:
            raise ValueError(f"Step '{step_name}' not found in session {session_id}")

        if step.status != StepExecutionStatus.PENDING:
            raise ValueError(f"Step '{step_name}' cannot be skipped (status: {step.status})")

        step.status = StepExecutionStatus.SKIPPED
        step.completed_at = datetime.now()

        session.advance_to_next_pending()

        # Check if all steps are done
        if all(s.status != StepExecutionStatus.PENDING for s in session.steps):
            session.status = SimulationSessionStatus.COMPLETED
            session.completed_at = datetime.now()

        logger.info(f"Skipped step {step_name} in session {session_id}")
        return step

    async def finalize_session(self, session_id: str) -> SimulationSession:
        """
        Finalize a simulation session (run teardown).

        Args:
            session_id: Session ID to finalize

        Returns:
            Updated SimulationSession
        """
        session = self._get_session(session_id)

        try:
            sequence = session._sequence_instance
            if sequence:
                await sequence.teardown()

            if session.status != SimulationSessionStatus.FAILED:
                session.status = SimulationSessionStatus.COMPLETED
            session.completed_at = datetime.now()

            logger.info(f"Finalized session {session_id}")

        except Exception as e:
            session.error = f"Teardown failed: {str(e)}"
            logger.warning(f"Session {session_id} teardown failed: {e}")

        return session

    async def abort_session(self, session_id: str) -> SimulationSession:
        """
        Abort a simulation session.

        Args:
            session_id: Session ID to abort

        Returns:
            Updated SimulationSession
        """
        session = self._get_session(session_id)

        # Mark remaining pending steps as skipped
        for step in session.steps:
            if step.status == StepExecutionStatus.PENDING:
                step.status = StepExecutionStatus.SKIPPED

        session.status = SimulationSessionStatus.ABORTED
        session.completed_at = datetime.now()

        # Run teardown
        try:
            sequence = session._sequence_instance
            if sequence:
                await sequence.teardown()
        except Exception as e:
            logger.warning(f"Teardown during abort failed: {e}")

        logger.info(f"Aborted session {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[SimulationSession]:
        """
        Get a simulation session by ID.

        Args:
            session_id: Session ID

        Returns:
            SimulationSession or None if not found
        """
        return self._sessions.get(session_id)

    def _get_session(self, session_id: str) -> SimulationSession:
        """
        Get a session or raise ValueError.

        Args:
            session_id: Session ID

        Returns:
            SimulationSession

        Raises:
            ValueError: If session not found
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Simulation session '{session_id}' not found")
        return session

    def list_sessions(self) -> List[SimulationSession]:
        """
        List all simulation sessions.

        Returns:
            List of all sessions
        """
        return list(self._sessions.values())

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a simulation session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                # Ensure cleanup
                if session.status == SimulationSessionStatus.RUNNING:
                    await self.abort_session(session_id)
                del self._sessions[session_id]
                logger.info(f"Deleted session {session_id}")
                return True
        return False

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
            mock_hardware[hw_name] = MockHardware(
                name=hw_name,
                display_name=hw_def.display_name,
            )

        return mock_hardware

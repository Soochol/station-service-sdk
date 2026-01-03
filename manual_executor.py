"""
Manual Sequence Executor Module.

Provides session-based manual sequence execution with real hardware.
Unlike InteractiveSimulator which uses MockHardware, this connects to
actual hardware drivers for production testing without Batch dependency.
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
    from .manifest import SequenceManifest, ManualCommand

from .driver_registry import DriverRegistry, DriverLoadError, DriverConnectionError
from .helpers import collect_steps
from .context import ExecutionContext
from .base import SequenceBase
from .simulator import DryRunOutputStrategy
from .types import SimulationResult

logger = logging.getLogger(__name__)


class ManualSessionStatus(str, Enum):
    """Status of a manual test session."""
    CREATED = "created"      # Session created, hardware not connected
    CONNECTING = "connecting"  # Hardware connection in progress
    READY = "ready"          # Hardware connected, ready for steps
    RUNNING = "running"      # Step execution in progress
    PAUSED = "paused"        # Execution paused
    COMPLETED = "completed"  # All steps completed
    FAILED = "failed"        # Session failed (error)
    ABORTED = "aborted"      # Session aborted by user


class ManualStepStatus(str, Enum):
    """Status of a step in manual execution."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class HardwareState:
    """State of a connected hardware device."""
    id: str
    display_name: str
    connected: bool = False
    driver_class: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    commands: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "displayName": self.display_name,
            "connected": self.connected,
            "driverClass": self.driver_class,
            "config": self.config,
            "commands": self.commands,
            "error": self.error,
        }


@dataclass
class ManualStepState:
    """State of a single step in manual execution."""
    name: str
    display_name: str
    order: int
    skippable: bool = True
    status: ManualStepStatus = ManualStepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: float = 0.0
    result: Optional[Dict[str, Any]] = None
    measurements: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    parameter_overrides: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "name": self.name,
            "displayName": self.display_name,
            "order": self.order,
            "skippable": self.skippable,
            "status": self.status.value,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "result": self.result,
            "measurements": self.measurements,
            "error": self.error,
            "parameterOverrides": self.parameter_overrides,
        }


@dataclass
class ManualSession:
    """
    A manual test session for step-by-step execution with real hardware.

    Unlike SimulationSession which uses MockHardware, this session
    connects to actual hardware drivers for production testing.
    """
    id: str
    sequence_name: str
    sequence_version: str
    status: ManualSessionStatus = ManualSessionStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step_index: int = 0
    steps: List[ManualStepState] = field(default_factory=list)
    hardware: List[HardwareState] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    hardware_config: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    overall_pass: bool = True
    error: Optional[str] = None

    # Internal state (not serialized)
    _sequence_instance: Optional[SequenceBase] = field(default=None, repr=False)
    _context: Optional[ExecutionContext] = field(default=None, repr=False)
    _output_strategy: Optional[DryRunOutputStrategy] = field(default=None, repr=False)
    _drivers: Dict[str, Any] = field(default_factory=dict, repr=False)
    _manifest: Optional["SequenceManifest"] = field(default=None, repr=False)

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
            "hardware": [h.to_dict() for h in self.hardware],
            "parameters": self.parameters,
            "hardwareConfig": self.hardware_config,
            "overallPass": self.overall_pass,
            "error": self.error,
        }

    def get_current_step(self) -> Optional[ManualStepState]:
        """Get the current step to execute."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def get_step_by_name(self, name: str) -> Optional[ManualStepState]:
        """Get a step by its name."""
        for step in self.steps:
            if step.name == name:
                return step
        return None

    def advance_to_next_pending(self) -> Optional[ManualStepState]:
        """Advance to the next pending step."""
        for i, step in enumerate(self.steps):
            if step.status == ManualStepStatus.PENDING:
                self.current_step_index = i
                return step
        return None

    def get_hardware_by_id(self, hw_id: str) -> Optional[HardwareState]:
        """Get hardware state by ID."""
        for hw in self.hardware:
            if hw.id == hw_id:
                return hw
        return None


@dataclass
class CommandResult:
    """Result of a hardware command execution."""
    success: bool
    hardware_id: str
    command: str
    result: Optional[Any] = None
    error: Optional[str] = None
    duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "hardwareId": self.hardware_id,
            "command": self.command,
            "result": self.result,
            "error": self.error,
            "duration": self.duration,
        }


class ManualSequenceExecutor:
    """
    Manual sequence executor for step-by-step execution with real hardware.

    Provides session-based manual testing with:
    - Real hardware connection via DriverRegistry
    - Individual step execution
    - Direct hardware command execution
    - Step skipping and parameter overrides
    - Session lifecycle management

    Usage:
        loader = SequenceLoader("sequences")
        executor = ManualSequenceExecutor(loader)

        # Create a session
        session = await executor.create_session(
            "psa_sensor_test",
            hardware_config={"psa_mcu": {"port": "/dev/ttyUSB0"}},
            parameters={"vl53l0x_target_mm": 500},
        )

        # Initialize (connects hardware, runs setup)
        await executor.initialize_session(session.id)

        # Execute steps
        result = await executor.run_step(session.id, "test_vl53l0x")

        # Or execute hardware commands directly
        cmd_result = await executor.execute_hardware_command(
            session.id, "psa_mcu", "ping", {}
        )

        # Finalize (runs teardown, disconnects hardware)
        await executor.finalize_session(session.id)
    """

    def __init__(
        self,
        sequence_loader: "SequenceLoader",
        sequences_dir: str = "sequences",
    ) -> None:
        """
        Initialize the manual sequence executor.

        Args:
            sequence_loader: Sequence loader for loading packages
            sequences_dir: Base directory for sequence packages
        """
        self.sequence_loader = sequence_loader
        self.driver_registry = DriverRegistry(sequences_dir=sequences_dir)
        self._sessions: Dict[str, ManualSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        sequence_name: str,
        hardware_config: Optional[Dict[str, Dict[str, Any]]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ManualSession:
        """
        Create a new manual test session.

        Session is created but hardware is not connected yet.
        Call initialize_session() to connect hardware and run setup.

        Args:
            sequence_name: Name of the sequence to execute
            hardware_config: Hardware configuration per hardware ID
            parameters: Optional parameter overrides

        Returns:
            Created ManualSession

        Raises:
            PackageError: If sequence not found
        """
        # Load manifest
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
        session = ManualSession(
            id=session_id,
            sequence_name=manifest.name,
            sequence_version=manifest.version,
            parameters=final_params,
            hardware_config=hardware_config or {},
        )
        session._manifest = manifest

        # Build hardware states from manifest
        for hw_id, hw_def in manifest.hardware.items():
            hw_config = (hardware_config or {}).get(hw_id, {})

            # Get default config from manifest
            default_config = {}
            if hw_def.config_schema:
                for field_name, field_schema in hw_def.config_schema.items():
                    if field_schema.default is not None:
                        default_config[field_name] = field_schema.default

            # Merge with user config
            final_hw_config = {**default_config, **hw_config}

            # Extract available commands from manifest
            commands = []
            if hw_def.manual_commands:
                commands = [cmd.name for cmd in hw_def.manual_commands]

            session.hardware.append(HardwareState(
                id=hw_id,
                display_name=hw_def.display_name,
                connected=False,
                driver_class=hw_def.driver_class,
                config=final_hw_config,
                commands=commands,
            ))

        # Build step states from manifest/class
        steps = collect_steps(sequence_class, manifest)
        for method_name, method, step_meta in steps:
            # Check if step is skippable from manifest
            skippable = True
            param_overrides = []

            for step_def in manifest.steps:
                if step_def.name == (step_meta.name or method_name):
                    if step_def.manual:
                        skippable = step_def.manual.skippable
                        param_overrides = step_def.manual.parameter_overrides or []
                    break

            session.steps.append(ManualStepState(
                name=step_meta.name or method_name,
                display_name=(step_meta.name or method_name).replace("_", " ").title(),
                order=step_meta.order,
                skippable=skippable,
                parameter_overrides=param_overrides,
            ))

        # Sort steps by order
        session.steps.sort(key=lambda s: s.order)

        # Store session
        async with self._lock:
            self._sessions[session_id] = session

        logger.info(f"Created manual session {session_id} for {sequence_name}")
        return session

    async def initialize_session(self, session_id: str) -> ManualSession:
        """
        Initialize a manual session (connect hardware, run setup).

        Args:
            session_id: Session ID to initialize

        Returns:
            Updated ManualSession

        Raises:
            ValueError: If session not found or in invalid state
            DriverConnectionError: If hardware connection fails
        """
        session = self._get_session(session_id)

        if session.status not in (ManualSessionStatus.CREATED, ManualSessionStatus.FAILED):
            raise ValueError(
                f"Session {session_id} is not in a valid state for initialization "
                f"(current: {session.status})"
            )

        session.status = ManualSessionStatus.CONNECTING
        session.started_at = datetime.now()

        try:
            # Load manifest and class
            manifest = session._manifest
            if manifest is None:
                manifest = await self.sequence_loader.load_package(session.sequence_name)
                session._manifest = manifest

            package_path = self.sequence_loader.get_package_path(session.sequence_name)
            sequence_class = await self.sequence_loader.load_sequence_class(
                manifest, package_path
            )

            # Connect hardware via DriverRegistry
            logger.info(f"Connecting hardware for session {session_id}...")
            drivers = await self.driver_registry.connect_hardware(
                manifest=manifest,
                sequence_path=package_path,
                hardware_config=session.hardware_config,
            )
            session._drivers = drivers

            # Update hardware states
            for hw_state in session.hardware:
                if hw_state.id in drivers:
                    hw_state.connected = True
                    hw_state.error = None
                    logger.info(f"Connected: {hw_state.id} ({hw_state.display_name})")

            # Create execution context (not dry_run mode)
            context = ExecutionContext(
                execution_id=f"manual-{session.id}",
                sequence_name=session.sequence_name,
                sequence_version=session.sequence_version,
                parameters=session.parameters,
                dry_run=False,  # Real hardware!
            )

            # Set connected drivers as hardware
            context.hardware = drivers

            # Create output strategy for capturing output
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
            logger.info(f"Running setup for session {session_id}...")
            await sequence_instance.setup()

            session.status = ManualSessionStatus.READY
            logger.info(f"Session {session_id} initialized and ready")

        except DriverLoadError as e:
            session.status = ManualSessionStatus.FAILED
            session.error = f"Driver load failed: {e}"
            # Mark affected hardware
            for hw_state in session.hardware:
                if hw_state.id == e.hardware_id:
                    hw_state.error = str(e)
            logger.exception(f"Session {session_id} failed to load driver: {e}")
            raise

        except DriverConnectionError as e:
            session.status = ManualSessionStatus.FAILED
            session.error = f"Hardware connection failed: {e}"
            # Mark affected hardware
            for hw_state in session.hardware:
                if hw_state.id == e.hardware_id:
                    hw_state.error = str(e)
            # Disconnect any successful connections
            await self.driver_registry.disconnect_all(session._drivers)
            logger.exception(f"Session {session_id} failed to connect: {e}")
            raise

        except Exception as e:
            session.status = ManualSessionStatus.FAILED
            session.error = f"Setup failed: {e}"
            # Disconnect any connections
            await self.driver_registry.disconnect_all(session._drivers)
            logger.exception(f"Session {session_id} setup failed: {e}")
            raise

        return session

    async def run_step(
        self,
        session_id: str,
        step_name: str,
        parameter_overrides: Optional[Dict[str, Any]] = None,
    ) -> ManualStepState:
        """
        Execute a single step in the manual session.

        Args:
            session_id: Session ID
            step_name: Name of the step to execute
            parameter_overrides: Optional parameter overrides for this step

        Returns:
            Updated ManualStepState

        Raises:
            ValueError: If session/step not found or in invalid state
        """
        session = self._get_session(session_id)

        if session.status not in (ManualSessionStatus.READY, ManualSessionStatus.PAUSED):
            raise ValueError(
                f"Session {session_id} is not ready for step execution "
                f"(current: {session.status})"
            )

        step = session.get_step_by_name(step_name)
        if step is None:
            raise ValueError(f"Step '{step_name}' not found in session {session_id}")

        if step.status not in (ManualStepStatus.PENDING, ManualStepStatus.FAILED):
            raise ValueError(
                f"Step '{step_name}' is not in a runnable state "
                f"(current: {step.status})"
            )

        # Apply parameter overrides
        if parameter_overrides:
            session.parameters.update(parameter_overrides)
            if session._sequence_instance:
                session._sequence_instance.parameters.update(parameter_overrides)
                # Update instance attributes that depend on parameters
                for key, value in parameter_overrides.items():
                    if hasattr(session._sequence_instance, key):
                        setattr(session._sequence_instance, key, value)

        # Execute the step
        step.status = ManualStepStatus.RUNNING
        step.started_at = datetime.now()
        session.status = ManualSessionStatus.RUNNING

        try:
            sequence = session._sequence_instance
            if sequence is None:
                raise ValueError("Session not initialized")

            # Find and call the step method
            method = getattr(sequence, step_name, None)
            if method is None:
                raise ValueError(f"Step method '{step_name}' not found in sequence")

            step.result = await method()

            # Check if result indicates failure
            if isinstance(step.result, dict):
                passed = step.result.get("passed", True)
                if not passed:
                    step.status = ManualStepStatus.FAILED
                    session.overall_pass = False
                else:
                    step.status = ManualStepStatus.PASSED
            else:
                step.status = ManualStepStatus.PASSED

            step.completed_at = datetime.now()
            step.duration = (step.completed_at - step.started_at).total_seconds()

            # Collect measurements from output strategy
            if session._output_strategy:
                step.measurements = session._output_strategy.measurements.copy()
                session._output_strategy.measurements.clear()

            logger.info(
                f"Step {step_name} completed ({step.status.value}) "
                f"in session {session_id}"
            )

        except Exception as e:
            step.status = ManualStepStatus.FAILED
            step.error = str(e)
            step.completed_at = datetime.now()
            step.duration = (step.completed_at - step.started_at).total_seconds()
            session.overall_pass = False
            logger.warning(f"Step {step_name} failed in session {session_id}: {e}")

        # Update session status
        session.status = ManualSessionStatus.READY
        session.advance_to_next_pending()

        # Check if all steps are done
        if all(s.status != ManualStepStatus.PENDING for s in session.steps):
            session.status = ManualSessionStatus.COMPLETED
            session.completed_at = datetime.now()

        return step

    async def skip_step(self, session_id: str, step_name: str) -> ManualStepState:
        """
        Skip a step in the manual session.

        Args:
            session_id: Session ID
            step_name: Name of the step to skip

        Returns:
            Updated ManualStepState

        Raises:
            ValueError: If session/step not found or step not skippable
        """
        session = self._get_session(session_id)

        step = session.get_step_by_name(step_name)
        if step is None:
            raise ValueError(f"Step '{step_name}' not found in session {session_id}")

        if not step.skippable:
            raise ValueError(f"Step '{step_name}' is not skippable")

        if step.status != ManualStepStatus.PENDING:
            raise ValueError(
                f"Step '{step_name}' cannot be skipped (status: {step.status})"
            )

        step.status = ManualStepStatus.SKIPPED
        step.completed_at = datetime.now()

        session.advance_to_next_pending()

        # Check if all steps are done
        if all(s.status != ManualStepStatus.PENDING for s in session.steps):
            session.status = ManualSessionStatus.COMPLETED
            session.completed_at = datetime.now()

        logger.info(f"Skipped step {step_name} in session {session_id}")
        return step

    async def execute_hardware_command(
        self,
        session_id: str,
        hardware_id: str,
        command: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> CommandResult:
        """
        Execute a hardware command directly.

        Args:
            session_id: Session ID
            hardware_id: Hardware ID
            command: Command name to execute
            parameters: Command parameters

        Returns:
            CommandResult with execution status and result

        Raises:
            ValueError: If session/hardware not found or not connected
        """
        session = self._get_session(session_id)

        if session.status not in (ManualSessionStatus.READY, ManualSessionStatus.PAUSED):
            raise ValueError(
                f"Session {session_id} is not ready for command execution"
            )

        hw_state = session.get_hardware_by_id(hardware_id)
        if hw_state is None:
            raise ValueError(f"Hardware '{hardware_id}' not found in session")

        if not hw_state.connected:
            raise ValueError(f"Hardware '{hardware_id}' is not connected")

        driver = session._drivers.get(hardware_id)
        if driver is None:
            raise ValueError(f"Driver for '{hardware_id}' not available")

        # Get method from driver
        method = getattr(driver, command, None)
        if method is None:
            return CommandResult(
                success=False,
                hardware_id=hardware_id,
                command=command,
                error=f"Command '{command}' not found on driver",
            )

        start_time = datetime.now()
        try:
            # Call the command with parameters
            params = parameters or {}
            result = method(**params)

            # Handle async methods
            if asyncio.iscoroutine(result):
                result = await result

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Command {hardware_id}.{command}() executed in {duration:.2f}s"
            )

            return CommandResult(
                success=True,
                hardware_id=hardware_id,
                command=command,
                result=result,
                duration=duration,
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.warning(
                f"Command {hardware_id}.{command}() failed: {e}"
            )
            return CommandResult(
                success=False,
                hardware_id=hardware_id,
                command=command,
                error=str(e),
                duration=duration,
            )

    async def get_hardware_commands(
        self,
        session_id: str,
        hardware_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get available commands for a hardware device.

        Args:
            session_id: Session ID
            hardware_id: Hardware ID

        Returns:
            List of command definitions
        """
        session = self._get_session(session_id)
        manifest = session._manifest

        if manifest is None:
            return []

        hw_def = manifest.hardware.get(hardware_id)
        if hw_def is None:
            return []

        if not hw_def.manual_commands:
            return []

        commands = []
        for cmd in hw_def.manual_commands:
            cmd_dict: Dict[str, Any] = {
                "name": cmd.name,
                "displayName": cmd.display_name,
                "description": cmd.description,
                "category": cmd.category,
                "parameters": [],
            }

            if cmd.parameters:
                for param in cmd.parameters:
                    cmd_dict["parameters"].append({
                        "name": param.name,
                        "displayName": param.display_name,
                        "type": param.type,
                        "required": param.required,
                        "default": param.default,
                        "min": param.min,
                        "max": param.max,
                        "unit": param.unit,
                    })

            if cmd.returns:
                cmd_dict["returns"] = {
                    "type": cmd.returns.type,
                    "description": cmd.returns.description,
                }

            commands.append(cmd_dict)

        return commands

    async def finalize_session(self, session_id: str) -> ManualSession:
        """
        Finalize a manual session (run teardown, disconnect hardware).

        Args:
            session_id: Session ID to finalize

        Returns:
            Updated ManualSession
        """
        session = self._get_session(session_id)

        try:
            # Run teardown if sequence is initialized
            sequence = session._sequence_instance
            if sequence:
                logger.info(f"Running teardown for session {session_id}...")
                await sequence.teardown()

            # Disconnect all hardware
            if session._drivers:
                logger.info(f"Disconnecting hardware for session {session_id}...")
                await self.driver_registry.disconnect_all(session._drivers)
                for hw_state in session.hardware:
                    hw_state.connected = False

            if session.status not in (ManualSessionStatus.FAILED, ManualSessionStatus.ABORTED):
                session.status = ManualSessionStatus.COMPLETED
            session.completed_at = datetime.now()

            logger.info(f"Finalized session {session_id}")

        except Exception as e:
            session.error = f"Finalization failed: {e}"
            logger.warning(f"Session {session_id} finalization failed: {e}")

        return session

    async def abort_session(self, session_id: str) -> ManualSession:
        """
        Abort a manual session (emergency stop).

        Args:
            session_id: Session ID to abort

        Returns:
            Updated ManualSession
        """
        session = self._get_session(session_id)

        # Mark remaining pending steps as skipped
        for step in session.steps:
            if step.status == ManualStepStatus.PENDING:
                step.status = ManualStepStatus.SKIPPED
            elif step.status == ManualStepStatus.RUNNING:
                step.status = ManualStepStatus.FAILED
                step.error = "Aborted"

        session.status = ManualSessionStatus.ABORTED
        session.completed_at = datetime.now()

        # Run teardown and disconnect
        try:
            sequence = session._sequence_instance
            if sequence:
                await sequence.teardown()
        except Exception as e:
            logger.warning(f"Teardown during abort failed: {e}")

        try:
            if session._drivers:
                await self.driver_registry.disconnect_all(session._drivers)
                for hw_state in session.hardware:
                    hw_state.connected = False
        except Exception as e:
            logger.warning(f"Disconnect during abort failed: {e}")

        logger.info(f"Aborted session {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[ManualSession]:
        """
        Get a manual session by ID.

        Args:
            session_id: Session ID

        Returns:
            ManualSession or None if not found
        """
        return self._sessions.get(session_id)

    def _get_session(self, session_id: str) -> ManualSession:
        """
        Get a session or raise ValueError.

        Args:
            session_id: Session ID

        Returns:
            ManualSession

        Raises:
            ValueError: If session not found
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Manual session '{session_id}' not found")
        return session

    def list_sessions(self) -> List[ManualSession]:
        """
        List all manual sessions.

        Returns:
            List of all sessions
        """
        return list(self._sessions.values())

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a manual session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                # Ensure cleanup if still active
                if session.status in (
                    ManualSessionStatus.READY,
                    ManualSessionStatus.RUNNING,
                    ManualSessionStatus.PAUSED,
                ):
                    await self.abort_session(session_id)
                del self._sessions[session_id]
                logger.info(f"Deleted session {session_id}")
                return True
        return False

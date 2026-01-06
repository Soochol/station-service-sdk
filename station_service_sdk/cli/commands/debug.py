"""Debug sequence command."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


def debug_sequence(
    package_path: Path,
    step_by_step: bool = False,
    breakpoints: list[str] | None = None,
) -> None:
    """Debug a sequence interactively.

    Args:
        package_path: Path to sequence package
        step_by_step: Pause after each step
        breakpoints: List of step names to pause at
    """
    breakpoints = breakpoints or []

    # Add package to path
    sys.path.insert(0, str(package_path))

    try:
        from station_service_sdk.loader import SequenceLoader
        from station_service_sdk.interactive import InteractiveSimulator
        from station_service_sdk.testing import create_test_context

        # Load sequence
        loader = SequenceLoader()
        package_info = loader.load_package(package_path)
        sequence_class = loader.load_sequence_class(package_info)

        # Create context
        context = create_test_context(
            sequence_name=package_info.manifest.name,
        )

        print(f"\n=== Debug Session: {package_info.manifest.name} ===\n")
        print("Commands:")
        print("  n/next  - Execute next step")
        print("  c/cont  - Continue to next breakpoint")
        print("  s/skip  - Skip current step")
        print("  i/info  - Show current state")
        print("  q/quit  - Quit debug session")
        print()

        # Create interactive simulator
        simulator = InteractiveSimulator()

        async def run_debug() -> None:
            session = await simulator.create_session(sequence_class, context)

            while not session.is_complete:
                current_step = session.current_step

                if current_step:
                    step_name = current_step.name
                    is_breakpoint = step_name in breakpoints

                    print(f"\n[Step {session.current_index + 1}/{session.total_steps}] {step_name}")

                    if step_by_step or is_breakpoint:
                        if is_breakpoint:
                            print("  ** Breakpoint hit **")

                        while True:
                            try:
                                cmd = input("(debug) ").strip().lower()
                            except EOFError:
                                cmd = "quit"

                            if cmd in ("n", "next", ""):
                                # Execute step
                                result = await simulator.execute_step(session)
                                _print_step_result(result)
                                break

                            elif cmd in ("c", "cont", "continue"):
                                # Continue to next breakpoint
                                while not session.is_complete:
                                    result = await simulator.execute_step(session)
                                    _print_step_result(result)
                                    if session.current_step and session.current_step.name in breakpoints:
                                        break
                                break

                            elif cmd in ("s", "skip"):
                                # Skip step
                                await simulator.skip_step(session)
                                print(f"  Skipped: {step_name}")
                                break

                            elif cmd in ("i", "info"):
                                # Show info
                                _print_session_info(session)

                            elif cmd in ("q", "quit", "exit"):
                                print("\nQuitting debug session...")
                                return

                            else:
                                print(f"Unknown command: {cmd}")
                    else:
                        # Auto-execute
                        result = await simulator.execute_step(session)
                        _print_step_result(result)

            # Print final result
            print("\n=== Debug Session Complete ===")
            final = session.result
            if final:
                status = "PASSED" if final.get("passed") else "FAILED"
                print(f"Result: {status}")
                if final.get("error"):
                    print(f"Error: {final['error']}")

        asyncio.run(run_debug())

    finally:
        if str(package_path) in sys.path:
            sys.path.remove(str(package_path))


def _print_step_result(result: dict) -> None:
    """Print step execution result."""
    if result.get("passed"):
        print(f"  Result: PASSED ({result.get('duration', 0):.2f}s)")
    else:
        print(f"  Result: FAILED - {result.get('error', 'Unknown error')}")

    measurements = result.get("measurements", {})
    if measurements:
        print("  Measurements:")
        for name, value in measurements.items():
            print(f"    {name}: {value}")


def _print_session_info(session) -> None:
    """Print session state information."""
    print(f"\n  Session ID: {session.session_id}")
    print(f"  Status: {session.status}")
    print(f"  Progress: {session.current_index + 1}/{session.total_steps}")

    if session.current_step:
        print(f"  Current Step: {session.current_step.name}")

    print(f"  Steps executed: {len(session.completed_steps)}")
    print()

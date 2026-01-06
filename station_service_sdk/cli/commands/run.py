"""Run sequence command."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RunResult:
    """Result of sequence execution.

    Attributes:
        passed: Whether sequence passed
        error: Error message if failed
        measurements: Measurement results
        duration: Execution duration in seconds
    """

    passed: bool
    error: str | None = None
    measurements: dict[str, Any] | None = None
    duration: float = 0.0


def run_sequence(
    package_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
    parameters: dict[str, Any] | None = None,
) -> RunResult:
    """Run a sequence locally.

    Args:
        package_path: Path to sequence package
        dry_run: Run without actual hardware
        verbose: Enable verbose output
        parameters: Sequence parameters

    Returns:
        RunResult with execution outcome
    """
    import sys

    # Add package to path
    sys.path.insert(0, str(package_path))

    try:
        from station_service_sdk.loader import SequenceLoader
        from station_service_sdk.simulator import SequenceSimulator
        from station_service_sdk.testing import create_test_context, CapturedOutput

        # Load sequence
        loader = SequenceLoader()
        package_info = loader.load_package(package_path)
        sequence_class = loader.load_sequence_class(package_info)

        # Create context
        context = create_test_context(
            sequence_name=package_info.manifest.name,
            parameters=parameters or {},
        )

        if dry_run:
            # Use simulator for dry run
            simulator = SequenceSimulator(verbose=verbose)
            result = asyncio.run(simulator.run(sequence_class, context))

            return RunResult(
                passed=result.get("passed", False),
                error=result.get("error"),
                measurements=result.get("measurements"),
                duration=result.get("duration", 0.0),
            )
        else:
            # Run actual sequence
            output = CapturedOutput()

            sequence = sequence_class(
                context=context,
                parameters=parameters or {},
                output_strategy=output,
            )

            asyncio.run(sequence.execute())

            final_result = output.get_final_result()
            if final_result:
                return RunResult(
                    passed=final_result.get("passed", False),
                    error=final_result.get("error"),
                    measurements=final_result.get("measurements"),
                    duration=final_result.get("duration", 0.0),
                )
            else:
                return RunResult(
                    passed=False,
                    error="No result from sequence",
                )

    except Exception as e:
        return RunResult(
            passed=False,
            error=str(e),
        )
    finally:
        # Remove package from path
        if str(package_path) in sys.path:
            sys.path.remove(str(package_path))

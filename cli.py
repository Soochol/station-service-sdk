"""
CLI argument parsing for SDK sequences.

Provides standardized argument parsing for all SDK-based sequences.

Usage:
    python -m sequences.my_sequence.main --start --config '{"wip_id": "...", ...}'
    python -m sequences.my_sequence.main --stop
    python -m sequences.my_sequence.main --status
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class CLIArgs:
    """Parsed CLI arguments."""

    action: str  # "start", "stop", or "status"
    config: Dict[str, Any] = field(default_factory=dict)

    # Extracted from config for convenience
    execution_id: Optional[str] = None
    wip_id: Optional[str] = None
    batch_id: Optional[str] = None
    process_id: Optional[int] = None
    operator_id: Optional[int] = None
    lot_id: Optional[str] = None
    serial_number: Optional[str] = None
    hardware_config: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Execution options
    dry_run: bool = False
    verbose: bool = False
    timeout: Optional[float] = None

    @classmethod
    def from_namespace(cls, ns: argparse.Namespace) -> "CLIArgs":
        """Create CLIArgs from argparse namespace."""
        # Determine action
        if getattr(ns, "start", False):
            action = "start"
        elif getattr(ns, "stop", False):
            action = "stop"
        elif getattr(ns, "status", False):
            action = "status"
        else:
            action = "start"  # default

        # Parse config
        config: Dict[str, Any] = {}
        if ns.config:
            try:
                config = json.loads(ns.config)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in --config: {e}")
        elif ns.config_file:
            config_path = Path(ns.config_file)
            if not config_path.exists():
                raise FileNotFoundError(f"Config file not found: {ns.config_file}")
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

        return cls(
            action=action,
            config=config,
            execution_id=config.get("execution_id"),
            wip_id=config.get("wip_id"),
            batch_id=config.get("batch_id"),
            process_id=config.get("process_id"),
            operator_id=config.get("operator_id"),
            lot_id=config.get("lot_id"),
            serial_number=config.get("serial_number"),
            hardware_config=config.get("hardware", {}),
            parameters=config.get("parameters", {}),
            dry_run=getattr(ns, "dry_run", False),
            verbose=getattr(ns, "verbose", False),
            timeout=getattr(ns, "timeout", None),
        )


def create_parser(prog_name: str = "sequence") -> argparse.ArgumentParser:
    """
    Create argument parser for sequence CLI.

    Args:
        prog_name: Program name for help text

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="CLI-based sequence execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start sequence with inline config
  python -m sequences.my_sequence.main --start --config '{"wip_id": "WIP001", "parameters": {"timeout": 30}}'

  # Start sequence with config file
  python -m sequences.my_sequence.main --start --config-file /path/to/config.json

  # Stop running sequence
  python -m sequences.my_sequence.main --stop

  # Check sequence status
  python -m sequences.my_sequence.main --status
        """,
    )

    # Action group (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--start",
        action="store_true",
        help="Start sequence execution",
    )
    action_group.add_argument(
        "--stop",
        action="store_true",
        help="Stop running sequence",
    )
    action_group.add_argument(
        "--status",
        action="store_true",
        help="Get sequence status",
    )

    # Configuration
    config_group = parser.add_mutually_exclusive_group()
    config_group.add_argument(
        "--config",
        "-c",
        type=str,
        metavar="JSON",
        help="JSON config string with execution parameters",
    )
    config_group.add_argument(
        "--config-file",
        "-f",
        type=str,
        metavar="PATH",
        help="Path to JSON config file",
    )

    # Execution options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config without executing",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        metavar="SECONDS",
        help="Overall execution timeout",
    )

    return parser


def parse_args(args: Optional[list] = None, prog_name: str = "sequence") -> CLIArgs:
    """
    Parse CLI arguments.

    Args:
        args: Arguments to parse (default: sys.argv[1:])
        prog_name: Program name for help text

    Returns:
        Parsed CLIArgs

    Raises:
        ValueError: If config JSON is invalid
        FileNotFoundError: If config file not found
    """
    parser = create_parser(prog_name)
    namespace = parser.parse_args(args)
    return CLIArgs.from_namespace(namespace)


def print_error(message: str) -> None:
    """Print error message to stderr."""
    print(f"Error: {message}", file=sys.stderr)


def print_help(prog_name: str = "sequence") -> None:
    """Print help message."""
    parser = create_parser(prog_name)
    parser.print_help()

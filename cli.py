"""
CLI for Station Service SDK.

Provides commands for initializing SDK skills in projects.
"""

import argparse
import shutil
import sys
from importlib import resources
from pathlib import Path


def get_skills_source_path() -> Path:
    """Get the path to the bundled skills directory."""
    with resources.as_file(resources.files("station_service_sdk") / "skills") as path:
        return path


def init_skills(target_dir: Path | None = None, force: bool = False) -> bool:
    """
    Install Claude Code skills to the target directory.
    
    Args:
        target_dir: Target directory (default: .claude/skills/sequence-development)
        force: Overwrite existing files
        
    Returns:
        True if successful
    """
    if target_dir is None:
        target_dir = Path.cwd() / ".claude" / "skills" / "sequence-development"
    
    skills_source = get_skills_source_path()
    skill_file = skills_source / "SKILL.md"
    
    if not skill_file.exists():
        print("Error: SKILL.md not found in package", file=sys.stderr)
        return False
    
    # Create target directory
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "SKILL.md"
    
    if target_file.exists() and not force:
        print(f"Skill already exists: {target_file}")
        print("Use --force to overwrite")
        return False
    
    # Copy skill file
    shutil.copy(skill_file, target_file)
    print(f"Installed skill to: {target_file}")
    
    return True


def cmd_init(args: argparse.Namespace) -> int:
    """Handle the init command."""
    target = Path(args.target) if args.target else None
    success = init_skills(target_dir=target, force=args.force)
    return 0 if success else 1


def cmd_version(args: argparse.Namespace) -> int:
    """Handle the version command."""
    from station_service_sdk import __version__
    print(f"station-service-sdk {__version__}")
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="station-sdk",
        description="Station Service SDK CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize SDK skills in current project",
    )
    init_parser.add_argument(
        "--target", "-t",
        help="Target directory (default: .claude/skills/sequence-development)",
    )
    init_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing files",
    )
    init_parser.set_defaults(func=cmd_init)
    
    # version command
    version_parser = subparsers.add_parser(
        "version",
        help="Show version",
    )
    version_parser.set_defaults(func=cmd_version)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 0
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

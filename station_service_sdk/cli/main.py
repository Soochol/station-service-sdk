"""Main CLI entry point for Station Service SDK.

Provides command-line interface for sequence development,
validation, testing, and debugging.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click

from station_service_sdk import __version__


@click.group()
@click.version_option(version=__version__, prog_name="station-sdk")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Station Service SDK - Test sequence development toolkit.

    Use these commands to create, validate, run, and debug
    test sequences for manufacturing automation.
    """
    ctx.ensure_object(dict)


@cli.command()
@click.argument("name")
@click.option(
    "--template",
    "-t",
    type=click.Choice(["basic", "hardware", "multi-step"]),
    default="basic",
    help="Template type for the new sequence",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=".",
    help="Output directory for the new sequence",
)
def new(name: str, template: str, output: str) -> None:
    """Create a new sequence package.

    NAME is the name of the sequence to create.

    Example:
        station-sdk new my-test-sequence --template hardware
    """
    from station_service_sdk.cli.commands.new import create_sequence

    output_path = Path(output)
    try:
        created_path = create_sequence(name, template, output_path)
        click.echo(f"Created sequence package: {created_path}")
        click.echo("\nNext steps:")
        click.echo(f"  cd {created_path}")
        click.echo("  pip install -e .")
        click.echo("  station-sdk validate .")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("path", type=click.Path(exists=True), default=".")
def validate(path: str) -> None:
    """Validate a sequence package.

    PATH is the path to the sequence package directory
    containing manifest.yaml.

    Example:
        station-sdk validate ./my-sequence
    """
    from station_service_sdk.cli.commands.validate import validate_sequence

    package_path = Path(path)
    try:
        result = validate_sequence(package_path)
        if result.valid:
            click.echo(f"✓ Validation passed: {package_path}")
            if result.warnings:
                click.echo("\nWarnings:")
                for warning in result.warnings:
                    click.echo(f"  ⚠ {warning}")
        else:
            click.echo(f"✗ Validation failed: {package_path}", err=True)
            for error in result.errors:
                click.echo(f"  ✗ {error}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--dry-run", is_flag=True, help="Run without actual hardware")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option(
    "--parameter",
    "-p",
    multiple=True,
    help="Set parameter value (format: name=value)",
)
def run(path: str, dry_run: bool, verbose: bool, parameter: tuple[str, ...]) -> None:
    """Run a sequence locally.

    PATH is the path to the sequence package directory.

    Example:
        station-sdk run ./my-sequence --dry-run -p voltage=3.3
    """
    from station_service_sdk.cli.commands.run import run_sequence

    package_path = Path(path)
    params = {}

    for p in parameter:
        if "=" in p:
            key, value = p.split("=", 1)
            # Try to parse as number
            try:
                params[key] = float(value) if "." in value else int(value)
            except ValueError:
                params[key] = value

    try:
        result = run_sequence(
            package_path,
            dry_run=dry_run,
            verbose=verbose,
            parameters=params,
        )
        if result.passed:
            click.echo("\n✓ Sequence passed")
        else:
            click.echo(f"\n✗ Sequence failed: {result.error}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--step-by-step", is_flag=True, help="Step through execution")
@click.option("--breakpoint", "-b", multiple=True, help="Set breakpoint at step")
def debug(path: str, step_by_step: bool, breakpoint: tuple[str, ...]) -> None:
    """Debug a sequence interactively.

    PATH is the path to the sequence package directory.

    Example:
        station-sdk debug ./my-sequence --step-by-step
    """
    from station_service_sdk.cli.commands.debug import debug_sequence

    package_path = Path(path)
    breakpoints = list(breakpoint)

    try:
        debug_sequence(
            package_path,
            step_by_step=step_by_step,
            breakpoints=breakpoints,
        )
    except KeyboardInterrupt:
        click.echo("\nDebug session interrupted")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--fix", is_flag=True, help="Automatically fix issues where possible")
def lint(path: str, fix: bool) -> None:
    """Check sequence code quality.

    PATH is the path to the sequence package directory.

    Example:
        station-sdk lint ./my-sequence --fix
    """
    from station_service_sdk.cli.commands.lint import lint_sequence

    package_path = Path(path)
    try:
        issues = lint_sequence(package_path, fix=fix)
        if not issues:
            click.echo("✓ No issues found")
        else:
            click.echo(f"Found {len(issues)} issue(s):")
            for issue in issues:
                icon = "⚠" if issue.severity == "warning" else "✗"
                click.echo(f"  {icon} {issue.file}:{issue.line} - {issue.message}")
            if not fix:
                click.echo("\nRun with --fix to automatically fix issues")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--install", is_flag=True, help="Install missing dependencies")
def deps(path: str, install: bool) -> None:
    """Check and install sequence dependencies.

    PATH is the path to the sequence package directory.

    Example:
        station-sdk deps ./my-sequence --install
    """
    from station_service_sdk.cli.commands.deps import check_dependencies

    package_path = Path(path)
    try:
        result = check_dependencies(package_path, install=install)
        if result.all_satisfied:
            click.echo("✓ All dependencies satisfied")
        else:
            click.echo("Missing dependencies:")
            for dep in result.missing:
                click.echo(f"  - {dep}")
            if not install:
                click.echo("\nRun with --install to install missing dependencies")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def doctor() -> None:
    """Diagnose SDK installation and environment.

    Checks for common issues with SDK setup, Python version,
    dependencies, and configuration.

    Example:
        station-sdk doctor
    """
    from station_service_sdk.cli.commands.doctor import run_diagnostics

    try:
        results = run_diagnostics()
        all_passed = True

        for check in results:
            if check.passed:
                icon = "✓"
            elif check.warning:
                icon = "⚠"
                all_passed = False
            else:
                icon = "✗"
                all_passed = False

            click.echo(f"{icon} {check.name}: {check.message}")

            if check.suggestion:
                click.echo(f"    Suggestion: {check.suggestion}")

        if all_passed:
            click.echo("\n✓ All checks passed")
        else:
            click.echo("\n⚠ Some checks failed or have warnings")
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def plugins() -> None:
    """List available SDK plugins.

    Shows all discovered plugins and their status.

    Example:
        station-sdk plugins
    """
    from station_service_sdk.plugins import PluginManager

    manager = PluginManager()
    plugins_list = manager.discover_plugins()

    if not plugins_list:
        click.echo("No plugins found")
        return

    click.echo(f"Found {len(plugins_list)} plugin(s):\n")
    for plugin in plugins_list:
        status = "✓" if plugin.enabled else "✗"
        click.echo(f"{status} {plugin.name} v{plugin.version}")
        click.echo(f"    Module: {plugin.module}")
        if plugin.load_error:
            click.echo(f"    Error: {plugin.load_error}")


@cli.command()
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "yaml"]),
    default="json",
    help="Output format",
)
def schema(format: str) -> None:
    """Output manifest JSON schema.

    Generates JSON Schema for manifest.yaml validation
    in IDEs and editors.

    Example:
        station-sdk schema --format json > manifest.schema.json
    """
    from station_service_sdk.manifest import SequenceManifest

    schema_dict = SequenceManifest.model_json_schema()

    if format == "json":
        import json

        click.echo(json.dumps(schema_dict, indent=2))
    else:
        import yaml

        click.echo(yaml.dump(schema_dict, default_flow_style=False))


@cli.command()
def init() -> None:
    """Initialize SDK configuration in the current directory.

    Creates .station-sdk directory with default configuration
    and skill files for Claude Code integration.

    Example:
        station-sdk init
    """
    from station_service_sdk.cli.commands.init import init_sdk

    try:
        init_sdk(Path.cwd())
        click.echo("✓ SDK initialized successfully")
        click.echo("  Created .station-sdk/ directory")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main() -> None:
    """Main entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()

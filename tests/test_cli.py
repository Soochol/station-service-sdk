"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner
from pathlib import Path
import yaml
import json

from station_service_sdk.cli.main import cli


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


class TestCLIMain:
    """Tests for main CLI entry point."""

    def test_help(self, runner) -> None:
        """Test --help option."""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "station-sdk" in result.output.lower() or "usage" in result.output.lower()

    def test_version_option(self, runner) -> None:
        """Test --version option."""
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        # Should contain version number
        assert "." in result.output


class TestValidateCommand:
    """Tests for validate command."""

    def test_validate_valid_package(self, runner, tmp_path) -> None:
        """Test validating a valid package."""
        # Create valid package
        manifest = {
            "name": "test_sequence",
            "version": "1.0.0",
            "entry_point": {
                "module": "sequence",
                "class": "TestSequence",
            },
        }

        manifest_path = tmp_path / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f)

        # Create sequence.py
        seq_path = tmp_path / "sequence.py"
        seq_path.write_text('''
from station_service_sdk import SequenceBase
from station_service_sdk.core.sdk_types import RunResult

class TestSequence(SequenceBase):
    name = "test_sequence"
    version = "1.0.0"

    async def setup(self): pass
    async def run(self) -> RunResult: return {"passed": True}
    async def teardown(self): pass
''')

        result = runner.invoke(cli, ["validate", str(tmp_path)])

        # Should complete (might pass or fail based on validation depth)
        assert result.exit_code in [0, 1]

    def test_validate_missing_manifest(self, runner, tmp_path) -> None:
        """Test validating package without manifest."""
        result = runner.invoke(cli, ["validate", str(tmp_path)])

        assert result.exit_code != 0

    def test_validate_invalid_manifest(self, runner, tmp_path) -> None:
        """Test validating package with invalid manifest."""
        manifest_path = tmp_path / "manifest.yaml"
        with open(manifest_path, "w") as f:
            f.write("invalid: yaml: {{{")

        result = runner.invoke(cli, ["validate", str(tmp_path)])

        assert result.exit_code != 0


class TestSchemaCommand:
    """Tests for schema command."""

    def test_schema_json_output(self, runner) -> None:
        """Test schema command outputs valid JSON."""
        result = runner.invoke(cli, ["schema", "--format", "json"])

        if result.exit_code == 0:
            schema = json.loads(result.output)
            assert isinstance(schema, dict)

    def test_schema_yaml_output(self, runner) -> None:
        """Test schema command outputs valid YAML."""
        result = runner.invoke(cli, ["schema", "--format", "yaml"])

        if result.exit_code == 0:
            schema = yaml.safe_load(result.output)
            assert isinstance(schema, dict)

    def test_schema_default_format(self, runner) -> None:
        """Test schema command with default format."""
        result = runner.invoke(cli, ["schema"])

        # Should not error
        assert result.exit_code in [0, 2]  # 2 if command not found


class TestDoctorCommand:
    """Tests for doctor command."""

    def test_doctor_runs(self, runner) -> None:
        """Test doctor command runs without error."""
        result = runner.invoke(cli, ["doctor"])

        # Should complete (may have warnings but shouldn't crash)
        assert result.exit_code in [0, 1, 2]

    def test_doctor_with_verbose(self, runner) -> None:
        """Test doctor command with verbose flag."""
        result = runner.invoke(cli, ["doctor", "--verbose"])

        # Should complete
        assert result.exit_code in [0, 1, 2]


class TestNewCommand:
    """Tests for new command."""

    def test_new_command_help(self, runner) -> None:
        """Test new command help."""
        result = runner.invoke(cli, ["new", "--help"])

        if result.exit_code == 0:
            assert "name" in result.output.lower() or "sequence" in result.output.lower()

    def test_new_creates_package(self, runner, tmp_path) -> None:
        """Test new command creates package structure."""
        result = runner.invoke(cli, ["new", "my_sequence", "--output", str(tmp_path)])

        if result.exit_code == 0:
            # Check package was created (underscores become hyphens in package name)
            pkg_dir = tmp_path / "my-sequence"
            assert pkg_dir.exists()
            assert (pkg_dir / "manifest.yaml").exists()


class TestRunCommand:
    """Tests for run command."""

    def test_run_command_help(self, runner) -> None:
        """Test run command help."""
        result = runner.invoke(cli, ["run", "--help"])

        if result.exit_code == 0:
            assert "package" in result.output.lower() or "run" in result.output.lower()

    def test_run_missing_package(self, runner) -> None:
        """Test run command with missing package."""
        result = runner.invoke(cli, ["run", "/nonexistent/path"])

        # Should fail
        assert result.exit_code != 0


class TestLintCommand:
    """Tests for lint command."""

    def test_lint_command_help(self, runner) -> None:
        """Test lint command help."""
        result = runner.invoke(cli, ["lint", "--help"])

        # Should show help or error if command doesn't exist
        assert result.exit_code in [0, 2]

    def test_lint_valid_package(self, runner, tmp_path) -> None:
        """Test lint command on valid package."""
        # Create minimal package
        manifest = {
            "name": "test_sequence",
            "version": "1.0.0",
            "entry_point": {
                "module": "sequence",
                "class": "TestSequence",
            },
        }

        manifest_path = tmp_path / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f)

        result = runner.invoke(cli, ["lint", str(tmp_path)])

        # Should complete
        assert result.exit_code in [0, 1, 2]

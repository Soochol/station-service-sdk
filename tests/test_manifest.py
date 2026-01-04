"""Tests for manifest validation with Pydantic models."""

import pytest
from pydantic import ValidationError
from station_service_sdk.manifest import (
    ParameterType,
    ConfigFieldSchema,
    HardwareDefinition,
    ParameterDefinition,
    EntryPoint,
    Modes,
    StepDefinition,
    SequenceManifest,
)


class TestParameterType:
    """Tests for ParameterType enum."""

    def test_all_types_defined(self):
        """Test all parameter types are defined."""
        expected = ["string", "integer", "float", "boolean"]
        actual = [t.value for t in ParameterType]
        assert sorted(actual) == sorted(expected)


class TestConfigFieldSchema:
    """Tests for ConfigFieldSchema model."""

    def test_basic_creation(self):
        """Test basic field schema."""
        field = ConfigFieldSchema(type=ParameterType.STRING)
        assert field.type == ParameterType.STRING
        assert field.required is False
        assert field.default is None

    def test_with_constraints(self):
        """Test field with min/max constraints."""
        field = ConfigFieldSchema(
            type=ParameterType.INTEGER,
            required=True,
            min=1,
            max=100,
            description="Port number",
        )
        assert field.min == 1
        assert field.max == 100
        assert field.required is True


class TestHardwareDefinition:
    """Tests for HardwareDefinition model."""

    def test_basic_creation(self):
        """Test basic hardware definition."""
        hw = HardwareDefinition(
            display_name="MCU",
            driver="drivers.mcu",
            **{"class": "MCUDriver"},
        )
        assert hw.display_name == "MCU"
        assert hw.driver == "drivers.mcu"
        assert hw.class_name == "MCUDriver"
        assert hw.driver_class == "MCUDriver"

    def test_with_config_schema(self):
        """Test hardware with config schema."""
        hw = HardwareDefinition(
            display_name="Power Supply",
            driver="drivers.power",
            **{"class": "PowerSupply"},
            config_schema={
                "ip": ConfigFieldSchema(
                    type=ParameterType.STRING,
                    required=True,
                ),
                "channel": ConfigFieldSchema(
                    type=ParameterType.INTEGER,
                    default=1,
                ),
            },
        )
        assert "ip" in hw.config_schema
        assert hw.config_schema["ip"].required is True


class TestParameterDefinition:
    """Tests for ParameterDefinition model."""

    def test_string_parameter(self):
        """Test string parameter definition."""
        param = ParameterDefinition(
            display_name="Serial Number",
            type=ParameterType.STRING,
            default="",
        )
        assert param.type == ParameterType.STRING
        assert param.default == ""

    def test_integer_parameter_with_range(self):
        """Test integer parameter with range."""
        param = ParameterDefinition(
            display_name="Retry Count",
            type=ParameterType.INTEGER,
            default=3,
            min=0,
            max=10,
        )
        assert param.min == 0
        assert param.max == 10
        assert param.default == 3

    def test_float_parameter_with_unit(self):
        """Test float parameter with unit."""
        param = ParameterDefinition(
            display_name="Voltage Limit",
            type=ParameterType.FLOAT,
            default=3.3,
            unit="V",
        )
        assert param.unit == "V"

    def test_invalid_default_type_raises(self):
        """Test that invalid default type raises ValidationError."""
        with pytest.raises(ValidationError):
            ParameterDefinition(
                display_name="Test",
                type=ParameterType.INTEGER,
                default="not_an_int",  # Should be int
            )

    def test_boolean_default_validation(self):
        """Test boolean parameter validation."""
        param = ParameterDefinition(
            display_name="Debug Mode",
            type=ParameterType.BOOLEAN,
            default=True,
        )
        assert param.default is True

        with pytest.raises(ValidationError):
            ParameterDefinition(
                display_name="Debug Mode",
                type=ParameterType.BOOLEAN,
                default="true",  # Should be bool, not str
            )


class TestEntryPoint:
    """Tests for EntryPoint model."""

    def test_basic_entry_point(self):
        """Test basic entry point."""
        ep = EntryPoint(module="sequence", **{"class": "MySequence"})
        assert ep.module == "sequence"
        assert ep.class_name == "MySequence"

    def test_nested_module_path(self):
        """Test nested module path."""
        ep = EntryPoint(module="my.nested.module", **{"class": "Seq"})
        assert ep.module == "my.nested.module"

    def test_invalid_module_path_raises(self):
        """Test invalid module path raises ValidationError."""
        with pytest.raises(ValidationError):
            EntryPoint(module="123invalid", **{"class": "Seq"})

    def test_invalid_class_name_raises(self):
        """Test invalid class name raises ValidationError."""
        with pytest.raises(ValidationError):
            EntryPoint(module="module", **{"class": "123Invalid"})


class TestModes:
    """Tests for Modes model."""

    def test_default_modes(self):
        """Test default mode values."""
        modes = Modes()
        assert modes.automatic is True
        assert modes.manual is False
        assert modes.interactive is False
        assert modes.cli is False

    def test_custom_modes(self):
        """Test custom mode configuration."""
        modes = Modes(automatic=True, manual=True, cli=True)
        assert modes.manual is True
        assert modes.cli is True


class TestStepDefinition:
    """Tests for StepDefinition model."""

    def test_basic_step(self):
        """Test basic step definition."""
        step = StepDefinition(name="measure_voltage", order=1)
        assert step.name == "measure_voltage"
        assert step.order == 1
        assert step.timeout == 60.0
        assert step.retry == 0

    def test_step_with_all_fields(self):
        """Test step with all optional fields."""
        step = StepDefinition(
            name="verify_result",
            display_name="Verify Result",
            order=5,
            timeout=30.0,
            estimated_duration=5.0,
            retry=2,
            cleanup=True,
        )
        assert step.display_name == "Verify Result"
        assert step.timeout == 30.0
        assert step.estimated_duration == 5.0
        assert step.retry == 2
        assert step.cleanup is True


class TestSequenceManifest:
    """Tests for SequenceManifest model."""

    @pytest.fixture
    def minimal_manifest(self):
        """Create minimal valid manifest."""
        return {
            "name": "test_sequence",
            "version": "1.0.0",
            "entry_point": {
                "module": "sequence",
                "class": "TestSequence",
            },
        }

    def test_minimal_manifest(self, minimal_manifest):
        """Test minimal manifest creation."""
        m = SequenceManifest(**minimal_manifest)
        assert m.name == "test_sequence"
        assert m.version == "1.0.0"
        assert m.entry_point.class_name == "TestSequence"

    def test_invalid_name_raises(self):
        """Test invalid sequence name raises."""
        with pytest.raises(ValidationError):
            SequenceManifest(
                name="invalid-name",  # Hyphens not allowed in identifiers
                version="1.0.0",
                entry_point=EntryPoint(module="mod", **{"class": "Cls"}),
            )

    def test_invalid_version_raises(self):
        """Test invalid version format raises."""
        with pytest.raises(ValidationError):
            SequenceManifest(
                name="test",
                version="1.0",  # Must be X.Y.Z
                entry_point=EntryPoint(module="mod", **{"class": "Cls"}),
            )

    def test_full_manifest(self):
        """Test full manifest with all fields."""
        m = SequenceManifest(
            name="full_sequence",
            version="2.1.0",
            author="Test Author",
            description="A complete test sequence",
            entry_point=EntryPoint(module="sequence", **{"class": "FullSeq"}),
            modes=Modes(automatic=True, manual=True),
            hardware={
                "mcu": HardwareDefinition(
                    display_name="MCU",
                    driver="drivers.mcu",
                    **{"class": "MCU"},
                ),
            },
            parameters={
                "timeout": ParameterDefinition(
                    display_name="Timeout",
                    type=ParameterType.INTEGER,
                    default=30,
                ),
            },
            steps=[
                StepDefinition(name="step1", order=1),
                StepDefinition(name="step2", order=2),
            ],
        )
        assert m.author == "Test Author"
        assert len(m.hardware) == 1
        assert len(m.parameters) == 1
        assert len(m.steps) == 2

    def test_get_hardware_names(self, minimal_manifest):
        """Test get_hardware_names method."""
        m = SequenceManifest(
            **minimal_manifest,
            hardware={
                "mcu": HardwareDefinition(
                    display_name="MCU",
                    driver="d",
                    **{"class": "C"},
                ),
                "power": HardwareDefinition(
                    display_name="Power",
                    driver="d",
                    **{"class": "C"},
                ),
            },
        )
        names = m.get_hardware_names()
        assert sorted(names) == ["mcu", "power"]

    def test_get_step_names(self, minimal_manifest):
        """Test get_step_names method."""
        m = SequenceManifest(
            **minimal_manifest,
            steps=[
                StepDefinition(name="init", order=1),
                StepDefinition(name="test", order=2),
                StepDefinition(name="cleanup", order=3),
            ],
        )
        assert m.get_step_names() == ["init", "test", "cleanup"]

    def test_get_step_by_name(self, minimal_manifest):
        """Test get_step_by_name method."""
        m = SequenceManifest(
            **minimal_manifest,
            steps=[
                StepDefinition(name="first", order=1, timeout=10),
                StepDefinition(name="second", order=2, timeout=20),
            ],
        )
        step = m.get_step_by_name("second")
        assert step is not None
        assert step.timeout == 20

        assert m.get_step_by_name("nonexistent") is None

    def test_is_cli_mode(self, minimal_manifest):
        """Test is_cli_mode method."""
        # Default is not CLI mode
        m = SequenceManifest(**minimal_manifest)
        assert m.is_cli_mode() is False

        # With modes.cli
        m = SequenceManifest(
            **minimal_manifest,
            modes=Modes(cli=True),
        )
        assert m.is_cli_mode() is True

        # With cli_main in entry_point
        m = SequenceManifest(
            name="test",
            version="1.0.0",
            entry_point=EntryPoint(
                module="sequence",
                cli_main="main",
                **{"class": "Seq"},
            ),
        )
        assert m.is_cli_mode() is True

    def test_get_total_estimated_duration(self, minimal_manifest):
        """Test get_total_estimated_duration method."""
        m = SequenceManifest(
            **minimal_manifest,
            steps=[
                StepDefinition(name="s1", order=1, estimated_duration=5.0),
                StepDefinition(name="s2", order=2, estimated_duration=10.5),
                StepDefinition(name="s3", order=3, estimated_duration=3.0),
            ],
        )
        assert m.get_total_estimated_duration() == 18.5

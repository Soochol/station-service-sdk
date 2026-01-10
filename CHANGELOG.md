# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2025-01-10

### Added
- Input validation for all emit methods in SequenceBase
  - `validate_step_name()` - Step name format validation
  - `validate_timeout()` - Timeout value validation (positive, max 24h)
  - `validate_index_total()` - Step index/total bounds validation
  - `validate_input_type()` - User input type validation
  - `validate_measurement_name()` - Measurement name validation
  - `validate_measurement_value()` - Measurement value type validation
  - `validate_error_code()` - Error code format validation (UPPER_SNAKE_CASE)
  - `validate_duration()` - Duration value validation
- Comprehensive test suite for core modules
  - `test_validators.py` - Input validation tests
  - `test_base.py` - SequenceBase lifecycle and emit method tests
  - `test_protocol.py` - OutputProtocol JSON Lines output tests
  - `test_hardware.py` - Retry strategy tests
  - `test_execution.py` - SequenceLoader tests
  - `test_cli.py` - CLI command tests
- CI/CD pipeline with GitHub Actions
  - Python 3.11, 3.12, 3.13 matrix testing
  - ruff linting and format checking
  - mypy type checking
  - pytest with coverage reporting
  - Codecov integration
  - PyPI trusted publishing
- CHANGELOG.md for tracking changes
- MANIFEST.in for package distribution
- requirements-dev.txt for reproducible development environments

### Changed
- Improved error messages with field-specific validation errors
- Added version upper bounds to dependencies for safety

## [2.0.0] - 2024-12-01

### Added
- Complete SDK rewrite with modular architecture
- `SequenceBase` class for building test sequences
- JSON Lines output protocol for Station Service communication
- Hardware connection pooling with retry strategies
  - `ExponentialBackoff` - Exponential delay with jitter
  - `FixedDelay` - Constant delay between retries
  - `LinearBackoff` - Linear delay increase
- Testing utilities
  - `MockDriver` and `MockDriverBuilder` for hardware mocking
  - `CapturedOutput` for output capture
  - Assertion helpers for step/measurement validation
- CLI tools
  - `station-sdk new` - Create new sequence package
  - `station-sdk validate` - Validate package structure
  - `station-sdk run` - Execute sequence
  - `station-sdk lint` - Check code style
  - `station-sdk doctor` - Diagnose environment
  - `station-sdk schema` - Output manifest schema
- Plugin system for extensibility
- Observability features
  - Structured logging with context
  - OpenTelemetry tracing (optional)
  - Prometheus metrics (optional)
- Interactive simulation and manual execution support

### Changed
- Package structure reorganized into modules:
  - `core/` - Base classes, context, protocol, exceptions
  - `execution/` - Sequence loading, simulation
  - `hardware/` - Connection pooling, retry strategies
  - `testing/` - Mocks, fixtures, assertions
  - `cli/` - Command-line tools
  - `observability/` - Logging, tracing, metrics
  - `plugins/` - Plugin discovery and lifecycle
- Upgraded to Pydantic v2 for manifest validation
- AsyncIO-based execution model

## [1.0.0] - 2024-06-01

### Added
- Initial release
- Basic sequence execution framework
- Hardware driver interface
- Simple CLI for running sequences

# Station Service SDK

SDK for building test sequences for Station Service.

## Installation

```bash
# From GitHub
pip install git+https://github.com/F2X/station-service-sdk.git

# Install Claude Code skill
station-sdk init
```

## Quick Start

```python
from station_service_sdk import SequenceBase, RunResult

class MySequence(SequenceBase):
    name = "my_sequence"
    version = "1.0.0"
    description = "My test sequence"

    async def setup(self) -> None:
        self.emit_log("info", "Initializing...")

    async def run(self) -> RunResult:
        self.emit_step_start("test", 1, 1, "Test step")
        self.emit_measurement("voltage", 3.3, "V")
        self.emit_step_complete("test", 1, True, 1.0)
        return {"passed": True, "measurements": {"voltage": 3.3}}

    async def teardown(self) -> None:
        self.emit_log("info", "Cleanup complete")

if __name__ == "__main__":
    exit(MySequence.run_from_cli())
```

## CLI Commands

```bash
# Initialize Claude Code skill in current project
station-sdk init

# Force overwrite existing skill
station-sdk init --force

# Show version
station-sdk version
```

## Documentation

After running `station-sdk init`, Claude Code will have access to the SDK development guide at `.claude/skills/sequence-development/SKILL.md`.

## License

MIT

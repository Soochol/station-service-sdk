"""Initialize SDK command."""

from __future__ import annotations

from pathlib import Path


def init_sdk(project_path: Path) -> None:
    """Initialize SDK configuration in a project.

    Creates .station-sdk directory with configuration files
    and skill integration for Claude Code.

    Args:
        project_path: Path to project root
    """
    sdk_dir = project_path / ".station-sdk"
    sdk_dir.mkdir(exist_ok=True)

    # Create config file
    config_content = """# Station SDK Configuration
# https://github.com/Soochol/station-service-sdk

# Default settings for sequences in this project
default_timeout: 60.0
verbose: false
dry_run: false

# Hardware simulation mode
simulation:
  enabled: false
  mock_measurements: {}

# Logging configuration
logging:
  level: INFO
  format: json
  output: stderr

# Plugin configuration
plugins:
  enabled: []
  config: {}
"""
    config_path = sdk_dir / "config.yaml"
    if not config_path.exists():
        config_path.write_text(config_content)

    # Create SKILL.md for Claude Code integration
    skill_content = """# Station Service SDK Development Guide

## 프로젝트 구조

```
my-sequence/
├── manifest.yaml      # 시퀀스 메타데이터 및 설정
├── pyproject.toml     # Python 패키지 설정
├── my_sequence/
│   └── __init__.py    # 시퀀스 구현
└── tests/
    └── test_*.py      # 테스트 파일
```

## 시퀀스 기본 구조

```python
from station_service_sdk import SequenceBase, RunResult

class MySequence(SequenceBase):
    name = "my_sequence"
    version = "1.0.0"
    description = "시퀀스 설명"

    async def setup(self) -> None:
        \"\"\"하드웨어 초기화 및 준비.\"\"\"
        self.emit_log("info", "Setting up")

    async def run(self) -> RunResult:
        \"\"\"테스트 실행 로직.\"\"\"
        measurements = {}

        # Step 실행
        self.emit_step_start("step_name", 1, 3, "Step description")
        # ... 테스트 로직 ...
        self.emit_measurement("voltage", 3.3, "V", min_value=3.0, max_value=3.6)
        measurements["voltage"] = 3.3
        self.emit_step_complete("step_name", 1, True, 0.5)

        return {
            "passed": True,
            "measurements": measurements,
            "data": {}
        }

    async def teardown(self) -> None:
        \"\"\"리소스 정리.\"\"\"
        self.emit_log("info", "Tearing down")
```

## manifest.yaml 구조

```yaml
name: sequence_name
version: "1.0.0"
description: "설명"
author: "작성자"

entry_point:
  module: module_name
  class: ClassName

modes:
  automatic: true
  manual: false

hardware:
  device_id:
    display_name: "장치명"
    driver: "drivers.module"
    class: "DriverClass"
    config_schema:
      port:
        type: string
        required: true

parameters:
  param_name:
    display_name: "파라미터명"
    type: float
    default: 1.0
    min: 0.0
    max: 10.0
    unit: "V"

steps:
  - name: step_name
    display_name: "스텝명"
    order: 1
    timeout: 30.0
```

## 주요 emit 메서드

- `emit_log(level, message)` - 로그 출력
- `emit_step_start(name, index, total, description)` - 스텝 시작
- `emit_step_complete(name, index, passed, duration, measurements, error)` - 스텝 완료
- `emit_measurement(name, value, unit, min_value, max_value)` - 측정값 기록
- `emit_error(code, message, recoverable)` - 에러 기록

## CLI 명령어

```bash
station-sdk new my-sequence      # 새 시퀀스 생성
station-sdk validate .           # 시퀀스 검증
station-sdk run . --dry-run      # 드라이런 실행
station-sdk debug . --step-by-step  # 디버그 모드
station-sdk lint .               # 코드 검사
station-sdk deps . --install     # 의존성 설치
station-sdk doctor               # 환경 진단
```

## 테스트 작성

```python
import pytest
from station_service_sdk.testing import (
    create_test_context,
    CapturedOutput,
    assert_sequence_passed,
    assert_measurement_in_range,
)

@pytest.mark.asyncio
async def test_sequence():
    context = create_test_context()
    output = CapturedOutput()

    sequence = MySequence(context=context, output_strategy=output)
    await sequence.execute()

    assert_sequence_passed(output)
    assert_measurement_in_range(output, "voltage", min_value=3.0, max_value=3.6)
```
"""
    skill_path = sdk_dir / "SKILL.md"
    if not skill_path.exists():
        skill_path.write_text(skill_content)

    # Create .gitignore
    gitignore_content = """# Station SDK local files
*.pyc
__pycache__/
.pytest_cache/
*.log
"""
    gitignore_path = sdk_dir / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(gitignore_content)

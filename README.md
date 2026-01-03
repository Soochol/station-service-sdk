# Station Service SDK

Test Sequence 개발을 위한 Python SDK입니다. Station Service와 통신하여 제조 공정 테스트를 자동화합니다.

## 빠른 시작

### 1. 기본 시퀀스 생성

```python
from station_service_sdk import SequenceBase, RunResult

class MyTestSequence(SequenceBase):
    name = "my_test"
    version = "1.0.0"
    description = "테스트 시퀀스 예제"

    async def setup(self) -> None:
        """하드웨어 초기화"""
        self.emit_log("info", "하드웨어 연결 중...")
        mcu_config = self.get_hardware_config("mcu")
        # TODO: 실제 하드웨어 연결

    async def run(self) -> RunResult:
        """테스트 실행"""
        total_steps = 2

        # Step 1: 초기화
        self.emit_step_start("init", 1, total_steps, "초기화")
        # ... 로직
        self.emit_step_complete("init", 1, True, 1.5)

        # Step 2: 측정
        self.emit_step_start("measure", 2, total_steps, "전압 측정")
        voltage = 3.28
        self.emit_measurement(
            name="voltage",
            value=voltage,
            unit="V",
            min_value=3.0,
            max_value=3.6
        )
        self.emit_step_complete("measure", 2, True, 2.0)

        return {"passed": True, "measurements": {"voltage": voltage}}

    async def teardown(self) -> None:
        """리소스 정리"""
        self.emit_log("info", "리소스 정리 완료")

if __name__ == "__main__":
    exit(MyTestSequence.run_from_cli())
```

### 2. 시퀀스 실행

```bash
python -m my_sequence.main --start --config '{"execution_id": "exec-001"}'
```

## 핵심 컴포넌트

### SequenceBase

모든 시퀀스의 기본 클래스입니다.

```python
class SequenceBase(ABC):
    # 클래스 속성 (필수)
    name: str           # 시퀀스 식별자
    version: str        # 버전 (X.Y.Z)
    description: str    # 설명

    # 추상 메서드 (구현 필수)
    async def setup(self) -> None: ...
    async def run(self) -> RunResult: ...
    async def teardown(self) -> None: ...

    # 출력 헬퍼
    def emit_log(level, message, **extra): ...
    def emit_step_start(step_name, index, total, description=""): ...
    def emit_step_complete(step_name, index, passed, duration, ...): ...
    def emit_measurement(name, value, unit, passed=None, min_value=None, max_value=None): ...
    def emit_error(code, message, recoverable=False): ...

    # 유틸리티
    def get_parameter(name, default=None) -> Any: ...
    def get_hardware_config(name) -> Dict: ...
    def abort(reason): ...
    def check_abort(): ...
```

### ExecutionContext

실행 컨텍스트 정보를 담습니다.

```python
from station_service_sdk import ExecutionContext

context = ExecutionContext(
    execution_id="exec-001",
    hardware_config={"device": {"port": "/dev/ttyUSB0"}},
    parameters={"timeout": 30}
)
```

### Measurement

측정값을 표현합니다.

```python
from station_service_sdk import Measurement

m = Measurement(
    name="voltage",
    value=3.28,
    unit="V",
    min_value=3.0,
    max_value=3.6
)
print(m.passed)  # True (자동 계산)
```

## 예외 처리

SDK는 계층적 예외 구조를 제공합니다:

```python
from station_service_sdk import (
    SequenceError,      # 기본 예외
    SetupError,         # 설정 오류
    TeardownError,      # 정리 오류
    StepError,          # 스텝 실행 오류
    TimeoutError,       # 타임아웃
    TestFailure,        # 테스트 실패
    HardwareError,      # 하드웨어 오류
    ConnectionError,    # 연결 오류
)

# 사용 예
async def setup(self) -> None:
    try:
        await self.mcu.connect()
    except Exception as e:
        raise SetupError(f"MCU 연결 실패: {e}")
```

## Lifecycle Hooks

커스텀 동작을 주입할 수 있습니다:

```python
from station_service_sdk import LifecycleHook, ExecutionContext

class MetricsHook(LifecycleHook):
    async def on_step_complete(
        self,
        context: ExecutionContext,
        step_name: str,
        index: int,
        passed: bool,
        duration: float,
        error: Optional[str] = None
    ) -> None:
        print(f"Step {step_name}: {'PASS' if passed else 'FAIL'}")

# 사용
sequence = MySequence(context, hooks=[MetricsHook()])
```

## 타입 정의

TypedDict를 사용한 명확한 반환 타입:

```python
from station_service_sdk.types import RunResult, StepMeta, MeasurementDict

async def run(self) -> RunResult:
    return {
        "passed": True,
        "measurements": {"voltage": 3.3},
        "data": {"serial": "ABC123"}
    }
```

## manifest.yaml

시퀀스 패키지 설정 파일:

```yaml
name: my_test
version: "1.0.0"
author: "Developer"
description: "테스트 시퀀스"

entry_point:
  module: sequence
  class: MyTestSequence
  cli_main: main

modes:
  automatic: true
  manual: true
  cli: true

hardware:
  mcu:
    display_name: "MCU Controller"
    driver: drivers.mcu
    class: MCUDriver
    config_schema:
      port:
        type: string
        required: true
        default: "/dev/ttyUSB0"

parameters:
  timeout:
    display_name: "타임아웃"
    type: float
    default: 30.0
    unit: "초"

steps:
  - name: init
    display_name: "초기화"
    order: 1
    timeout: 10.0
  - name: measure
    display_name: "측정"
    order: 2
    timeout: 30.0

dependencies:
  python:
    - pyserial>=3.5
```

## 마이그레이션 가이드

### Legacy 데코레이터에서 SDK 패턴으로

**기존 (deprecated):**
```python
from station_service_sdk.decorators import sequence, step

@sequence(name="old_test")
class OldSequence:
    @step(order=1, timeout=30)
    async def test_step(self):
        return {"status": "passed"}
```

**신규 (권장):**
```python
from station_service_sdk import SequenceBase, RunResult

class NewSequence(SequenceBase):
    name = "new_test"
    version = "1.0.0"

    async def setup(self) -> None:
        pass

    async def run(self) -> RunResult:
        self.emit_step_start("test_step", 1, 1)
        # 로직
        self.emit_step_complete("test_step", 1, True, 1.0)
        return {"passed": True}

    async def teardown(self) -> None:
        pass
```

## 디렉토리 구조

```
sequences/
└── my_test/
    ├── manifest.yaml      # 패키지 설정
    ├── sequence.py        # SequenceBase 구현
    ├── main.py            # CLI 진입점 (optional)
    └── drivers/           # 하드웨어 드라이버
        └── mcu.py
```

## CLI 사용법

```bash
# 시퀀스 시작
python -m sequences.my_test.main --start --config '{"wip_id": "WIP001"}'

# 설정 파일 사용
python -m sequences.my_test.main --start --config-file config.json

# Dry run (검증만)
python -m sequences.my_test.main --start --dry-run

# 시퀀스 중지
python -m sequences.my_test.main --stop
```

## API Reference

자세한 API 문서는 각 모듈의 docstring을 참조하세요:

- `station_service_sdk.base` - SequenceBase 클래스
- `station_service_sdk.context` - ExecutionContext, Measurement
- `station_service_sdk.exceptions` - 예외 클래스
- `station_service_sdk.interfaces` - OutputStrategy, LifecycleHook
- `station_service_sdk.manifest` - SequenceManifest 모델
- `station_service_sdk.types` - TypedDict 정의

---
name: sequence-development
description: Station Service SDK를 사용한 테스트 시퀀스 개발 가이드. SequenceBase 패턴, emit 메서드, manifest.yaml 작성법 제공. 사용자가 시퀀스 개발, SequenceBase 구현, 테스트 자동화 코드 작성, manifest.yaml 설정, emit 메서드 사용법을 문의할 때 활성화. (project)
allowed-tools: Read, Grep, Glob
---

# Station Service SDK 2.0 Guide

Station Service SDK를 사용한 테스트 시퀀스 개발 가이드입니다.

## Package Structure

```
station_service_sdk/
├── core/           # Core components (SequenceBase, Context, Protocol, Exceptions)
├── execution/      # Execution components (Loader, Registry, Simulator, Manual)
├── hardware/       # Hardware integration (Connection Pool, Retry, Health)
├── testing/        # Testing utilities (Mocks, Fixtures, Assertions)
├── observability/  # Observability (Logging, Tracing, Metrics)
├── plugins/        # Plugin system (Manager, Protocol Adapters)
├── cli/            # CLI tools (new, validate, run, debug, lint, doctor)
└── compat/         # Backward compatibility (Decorators, Dependencies)
```

---

## Quick Start

```python
from station_service_sdk import SequenceBase, RunResult

class MySequence(SequenceBase):
    name = "my_sequence"
    version = "1.0.0"
    description = "테스트 시퀀스"

    async def setup(self) -> None:
        """하드웨어 초기화"""
        self.emit_log("info", "초기화 중...")
        config = self.get_hardware_config("device")
        # 하드웨어 연결 로직

    async def run(self) -> RunResult:
        """테스트 실행"""
        total_steps = 2

        # Step 1
        self.emit_step_start("init", 1, total_steps, "초기화")
        # ... 로직
        self.emit_step_complete("init", 1, True, 1.5)

        # Step 2
        self.emit_step_start("measure", 2, total_steps, "측정")
        value = 3.28
        self.emit_measurement("voltage", value, "V", min_value=3.0, max_value=3.6)
        self.emit_step_complete("measure", 2, True, 2.0)

        return {"passed": True, "measurements": {"voltage": value}}

    async def teardown(self) -> None:
        """리소스 정리"""
        self.emit_log("info", "정리 완료")

if __name__ == "__main__":
    exit(MySequence.run_from_cli())
```

---

## CLI 도구

### 명령어 목록

```bash
# 새 시퀀스 생성
station-sdk new my-sequence                    # 기본 템플릿
station-sdk new my-sequence --template hardware # 하드웨어 템플릿
station-sdk new my-sequence --template multi-step # 다단계 템플릿

# 시퀀스 검증 (업로드 전 필수!)
station-sdk validate .
station-sdk validate ./my-sequence

# 시퀀스 실행
station-sdk run . --dry-run                    # 드라이런 모드
station-sdk run . -p voltage=3.3               # 파라미터 설정
station-sdk run . --verbose                    # 상세 출력

# 디버그 모드
station-sdk debug . --step-by-step             # 단계별 실행
station-sdk debug . -b measure                 # 브레이크포인트 설정

# 코드 품질 검사
station-sdk lint .
station-sdk lint . --fix                       # 자동 수정

# 의존성 검사
station-sdk deps .
station-sdk deps . --install                   # 누락 패키지 설치

# 환경 진단
station-sdk doctor

# 플러그인 목록
station-sdk plugins

# manifest 스키마 출력
station-sdk schema --format json > manifest.schema.json

# SDK 초기화
station-sdk init

# 버전 확인
station-sdk --version
```

---

## Lifecycle Steps

SDK는 `setup()`과 `teardown()`을 자동으로 UI 스텝으로 emit합니다.

### 동작 방식
- `setup()` 시작 시 자동으로 step 0으로 emit
- `run()` 스텝들은 step 1부터 시작
- `teardown()` 완료 시 마지막 step으로 emit
- **총 스텝 수 = run 스텝 수 + 2** (setup + teardown)

### manifest.yaml에 lifecycle 스텝 정의

```yaml
steps:
  - name: setup
    display_name: "Setup"
    order: 0
    lifecycle: true  # SDK 자동 관리
  - name: init
    display_name: "초기화"
    order: 1
  - name: measure
    display_name: "측정"
    order: 2
  - name: teardown
    display_name: "Teardown"
    order: 3
    lifecycle: true  # SDK 자동 관리
```

> `lifecycle: true` 스텝은 직접 emit하지 않아도 SDK가 자동 처리합니다.

---

## emit_* 메서드

시퀀스 실행 중 상태를 보고하는 메서드들입니다.

| 메서드 | 용도 | 예시 |
|--------|------|------|
| `emit_log(level, msg)` | 로그 출력 | `emit_log("info", "연결됨")` |
| `emit_step_start(name, idx, total, desc)` | 스텝 시작 | `emit_step_start("init", 1, 3, "초기화")` |
| `emit_step_complete(name, idx, passed, dur)` | 스텝 완료 | `emit_step_complete("init", 1, True, 2.0)` |
| `emit_measurement(name, val, unit, ...)` | 측정값 기록 | `emit_measurement("V", 3.3, "V", min_value=3.0)` |
| `emit_error(code, msg, recoverable)` | 에러 보고 | `emit_error("E001", "실패", False)` |

### emit_measurement 상세

```python
self.emit_measurement(
    name="voltage",
    value=3.28,
    unit="V",
    passed=None,        # None이면 자동 판정
    min_value=3.0,      # 최소값 (optional)
    max_value=3.6       # 최대값 (optional)
)
```

---

## manifest.yaml

시퀀스 패키지 설정 파일입니다.

```yaml
name: my_sequence
version: "1.0.0"
author: "Developer"
description: "시퀀스 설명"

entry_point:
  module: sequence
  class: MySequence

modes:
  automatic: true     # 자동 순차 실행
  manual: false       # 수동 단계별 실행
  interactive: false  # 실행 중 프롬프트
  cli: true           # CLI 기반 실행 (SDK 모드)

hardware:
  device:
    display_name: "장치명"
    driver: drivers.my_device
    class: MyDriver
    config_schema:
      port:
        type: string
        required: true
        default: "/dev/ttyUSB0"
      baudrate:
        type: integer
        default: 115200

parameters:
  timeout:
    display_name: "타임아웃"
    type: float
    default: 30.0
    min: 1.0
    max: 300.0
    unit: "s"

steps:
  - name: init
    display_name: "초기화"
    order: 1
    timeout: 30.0
  - name: measure
    display_name: "측정"
    order: 2
    timeout: 60.0

dependencies:
  python:
    - pyserial>=3.5
```

### hardware 섹션 규칙

> **주의**: hardware 정의 시 `driver`와 `class` 필드는 **필수**입니다.

```yaml
# 올바른 예시
hardware:
  device:
    display_name: "장치명"
    driver: drivers.my_device    # 필수
    class: MyDriver              # 필수
    config_schema: ...

# 잘못된 예시 (Pydantic 검증 실패)
hardware:
  device:
    display_name: "장치명"
    driver: null                 # null 불가
    # class 누락                 # 필수 필드 누락
```

**CLI 기반 시퀀스** (외부 프로그램 직접 호출):
- 하드웨어 드라이버가 필요 없으면 `hardware` 섹션을 **생략**
- `driver: null`은 유효하지 않음

```yaml
# CLI 기반 시퀀스 예시 (hardware 섹션 없음)
name: stm32_firmware_upload
version: "1.0.0"

entry_point:
  module: sequence
  class: STM32FirmwareUpload

modes:
  automatic: true
  manual: true
  cli: true

# hardware 섹션 생략 - STM32CubeProgrammer CLI 직접 사용

parameters:
  firmware_path:
    display_name: "펌웨어 경로"
    type: string
    required: true
```

### modes 섹션

```yaml
modes:
  automatic: true     # 자동 순차 실행 (기본)
  manual: false       # 수동 단계별 실행 (ManualSequenceExecutor 필요)
  interactive: false  # 실행 중 사용자 입력 프롬프트
  cli: true           # CLI 기반 서브프로세스 실행
```

---

## 예외 클래스

SDK에서 제공하는 예외 클래스 계층:

```python
from station_service_sdk import (
    # 기본
    SequenceError,          # 모든 시퀀스 예외의 베이스

    # Lifecycle
    SetupError,             # 초기화 실패
    TeardownError,          # 정리 실패

    # Execution
    StepError,              # 스텝 실행 오류
    SequenceTimeoutError,   # 타임아웃 (권장)
    TimeoutError,           # 타임아웃 (하위호환 별칭)
    AbortError,             # 사용자/시스템 중단

    # Test results
    TestFailure,            # 테스트 실패 (측정값 범위 벗어남 등)
    TestSkipped,            # 테스트 스킵됨

    # Hardware
    HardwareError,          # 하드웨어 오류 베이스
    HardwareConnectionError,# 연결 오류 (권장)
    ConnectionError,        # 연결 오류 (하위호환 별칭)
    CommunicationError,     # 통신 오류

    # Package/Manifest
    PackageError,           # 패키지 구조 오류
    ManifestError,          # manifest 파싱/검증 오류

    # Validation
    ValidationError,        # 파라미터/설정 검증 오류
    DependencyError,        # 의존성 누락/비호환
)

# 사용 예
async def setup(self) -> None:
    try:
        await self.device.connect()
    except Exception as e:
        raise SetupError(f"연결 실패: {e}")
```

### 예외 상세 정보

모든 예외는 다음 속성을 가집니다:
- `message`: 사람이 읽을 수 있는 오류 메시지
- `code`: 기계가 읽을 수 있는 오류 코드 (분류용)
- `details`: 추가 컨텍스트 딕셔너리

```python
try:
    ...
except HardwareError as e:
    print(f"Code: {e.code}")      # "HARDWARE_ERROR"
    print(f"Message: {e.message}")
    print(f"Details: {e.details}")
```

---

## 에러 상태 접근자

실행 중 발생한 에러에 접근할 수 있는 프로퍼티들입니다.

| 프로퍼티 | 타입 | 설명 |
|---------|------|------|
| `setup_error` | `Optional[str]` | Setup 단계 에러 메시지 |
| `run_error` | `Optional[str]` | Run 단계 에러 메시지 |
| `teardown_error` | `Optional[str]` | Teardown 단계 에러 메시지 |
| `last_error` | `Optional[str]` | 가장 최근 에러 (teardown → run → setup 순) |
| `setup_exception` | `Optional[Exception]` | Setup 예외 객체 |
| `run_exception` | `Optional[Exception]` | Run 예외 객체 |
| `teardown_exception` | `Optional[Exception]` | Teardown 예외 객체 |
| `last_exception` | `Optional[Exception]` | 가장 최근 예외 객체 |

### 활용 예시

```python
async def teardown(self) -> None:
    # 이전 단계 에러 확인
    if self.last_error:
        self.emit_log("warning", f"에러 발생: {self.last_error}")
        # 실패 시 추가 진단 수집
        if self.mcu and hasattr(self.mcu, 'get_diagnostics'):
            diag = await self.mcu.get_diagnostics()
            self.emit_log("debug", f"MCU 진단: {diag}")

    # 정리 로직...
    await self.mcu.disconnect()
```

---

## LifecycleHook 인터페이스

시퀀스 실행 이벤트에 커스텀 동작을 추가할 수 있습니다.

```python
from station_service_sdk import SequenceBase, LifecycleHook, CompositeHook
from station_service_sdk.core import ExecutionContext, Measurement

class LoggingHook(LifecycleHook):
    """로깅 hook 예시"""

    async def on_setup_start(self, context: ExecutionContext) -> None:
        print(f"Setup starting: {context.execution_id}")

    async def on_setup_complete(self, context: ExecutionContext, error: Optional[Exception] = None) -> None:
        print(f"Setup complete, error: {error}")

    async def on_step_start(self, context: ExecutionContext, step_name: str, index: int, total: int) -> None:
        print(f"Step {index}/{total}: {step_name} starting")

    async def on_step_complete(self, context: ExecutionContext, step_name: str, index: int, passed: bool, duration: float, error: Optional[str] = None) -> None:
        print(f"Step {step_name}: {'PASS' if passed else 'FAIL'} ({duration:.2f}s)")

    async def on_measurement(self, context: ExecutionContext, measurement: Measurement) -> None:
        print(f"Measurement: {measurement.name}={measurement.value}{measurement.unit}")

    async def on_error(self, context: ExecutionContext, error: Exception, phase: str) -> None:
        print(f"Error in {phase}: {error}")

    async def on_sequence_complete(self, context: ExecutionContext, result: dict) -> None:
        print(f"Sequence complete: {'PASS' if result['passed'] else 'FAIL'}")

# 사용
sequence = MySequence(
    context=context,
    hooks=[LoggingHook(), AnotherHook()],
)
```

---

## OutputStrategy 인터페이스

출력 형식을 커스터마이징할 수 있습니다.

```python
from station_service_sdk import OutputStrategy

class CustomOutput(OutputStrategy):
    """커스텀 출력 전략"""

    def log(self, level: str, message: str, **extra) -> None:
        # 커스텀 로깅
        pass

    def status(self, status: str, progress: float, step: str = None, message: str = None) -> None:
        # 상태 업데이트
        pass

    def step_start(self, step_name: str, index: int, total: int, description: str = "") -> None:
        # 스텝 시작
        pass

    def step_complete(self, step_name: str, index: int, passed: bool, duration: float, **kwargs) -> None:
        # 스텝 완료
        pass

    def measurement(self, name: str, value: Any, unit: str = "", **kwargs) -> None:
        # 측정값
        pass

    def error(self, code: str, message: str, **kwargs) -> None:
        # 에러
        pass

# 사용
sequence = MySequence(
    context=context,
    output_strategy=CustomOutput(),
)
```

---

## Testing Utilities

테스트 코드 작성을 위한 유틸리티입니다.

### 기본 테스트

```python
import pytest
from station_service_sdk.testing import (
    create_test_context,
    CapturedOutput,
    assert_sequence_passed,
    assert_step_passed,
    assert_measurement_in_range,
)

@pytest.mark.asyncio
async def test_sequence_passes():
    """시퀀스가 성공적으로 완료되는지 테스트"""
    context = create_test_context(sequence_name="my_sequence")
    output = CapturedOutput()

    sequence = MySequence(
        context=context,
        output_strategy=output,
    )

    result = await sequence._execute()

    assert_sequence_passed(output)
    assert result["passed"] is True
```

### Mock Driver

```python
from station_service_sdk.testing import MockDriver, MockDriverBuilder

# 빌더 패턴으로 모의 드라이버 생성
mock_device = (
    MockDriverBuilder()
    .with_method("connect", return_value=True)
    .with_method("measure_voltage", return_value=3.3)
    .with_method("disconnect", return_value=None)
    .build()
)

# 시퀀스에 주입
sequence = MySequence(
    context=context,
    hardware_config={"device": mock_device},
)
```

### Assertions

```python
# 시퀀스 전체 결과 검증
assert_sequence_passed(output)

# 특정 스텝 검증
assert_step_passed(output, "measure")
assert_step_failed(output, "calibration")

# 측정값 범위 검증
assert_measurement_in_range(
    output,
    name="voltage",
    min_value=3.0,
    max_value=3.6
)
```

---

## Hardware Module

하드웨어 연결 관리 기능입니다.

### Connection Pool

```python
from station_service_sdk.hardware import (
    HardwareConnectionPool,
    ConnectionConfig,
)

# 연결 풀 생성
pool = HardwareConnectionPool()

# 연결 설정
config = ConnectionConfig(
    name="device",
    driver_path="drivers.my_device",
    driver_class="MyDriver",
    max_connections=3,
    connection_timeout=10.0,
)

# 연결 획득/반환
async with pool.acquire("device") as conn:
    await conn.measure_voltage()
```

### Retry Strategy

```python
from station_service_sdk.hardware import (
    with_retry,
    ExponentialBackoff,
    RetryStrategy,
)

# 데코레이터로 재시도 추가
@with_retry(max_attempts=3, backoff=ExponentialBackoff(base=0.5))
async def measure_voltage(self):
    return await self.device.measure()

# 커스텀 재시도 전략
class MyRetryStrategy(RetryStrategy):
    def should_retry(self, error: Exception, attempt: int) -> bool:
        return isinstance(error, CommunicationError) and attempt < 3

    def get_delay(self, attempt: int) -> float:
        return attempt * 0.5
```

### Health Monitor

```python
from station_service_sdk.hardware import (
    HealthCheckable,
    HealthCheckResult,
    HealthMonitor,
)

class MyDevice(HealthCheckable):
    async def health_check(self) -> HealthCheckResult:
        try:
            response = await self.ping()
            return HealthCheckResult(
                healthy=True,
                latency_ms=response.latency,
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                error=str(e),
            )

# 모니터 사용
monitor = HealthMonitor(check_interval=5.0)
monitor.register("device", my_device)
await monitor.start()
```

---

## Simulator & Interactive Mode

### Dry Run Simulation

```python
from station_service_sdk import SequenceSimulator

# 시뮬레이터 생성
simulator = SequenceSimulator(sequence_loader)

# 드라이런 실행
result = await simulator.dry_run(
    sequence_name="my_sequence",
    parameters={"voltage": 3.3},
)

print(f"Status: {result['status']}")
print(f"Steps: {result['steps']}")
print(f"Overall Pass: {result['overall_pass']}")
```

### Interactive Mode

```python
from station_service_sdk import InteractiveSimulator, SimulationSession

# 인터랙티브 세션 시작
simulator = InteractiveSimulator()
session: SimulationSession = await simulator.create_session(
    sequence_name="my_sequence",
)

# 단계별 실행
await session.execute_step("init")
await session.execute_step("measure")

# 세션 상태 확인
print(f"Status: {session.status}")
print(f"Steps: {session.get_step_states()}")
```

---

## Manual Execution

수동 실행 모드 지원입니다.

```python
from station_service_sdk import (
    ManualSequenceExecutor,
    ManualSession,
    ManualStepState,
)

# 수동 실행기 생성
executor = ManualSequenceExecutor(sequence_loader)

# 세션 시작
session: ManualSession = await executor.create_session(
    sequence_name="my_sequence",
    hardware_config=config,
)

# 하드웨어 연결
await session.connect_hardware()

# 스텝 실행
step_result = await session.execute_step("init")
print(f"Step result: {step_result}")

# 수동 명령 실행
cmd_result = await session.execute_command(
    hardware_name="device",
    command="measure_voltage",
    params={},
)

# 세션 종료
await session.close()
```

---

## 의존성 관리

### pyproject.toml 방식 (권장)

```toml
# sequences/my_sequence/pyproject.toml
[project]
name = "my-sequence"
version = "1.0.0"
dependencies = [
    "pyserial>=3.5,<4.0",
    "numpy>=1.20.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### manifest.yaml 방식

```yaml
dependencies:
  python:
    - pyserial>=3.5
    - numpy>=1.20.0
```

### SDK 함수 사용

```python
from station_service_sdk import (
    ensure_package,
    ensure_dependencies,
    is_installed,
    get_missing_packages,
    install_sequence_dependencies,
)

# 단일 패키지 확인 및 설치
ensure_package("pyserial")
import serial

# 여러 패키지
results = ensure_dependencies(["pyserial", "numpy"])
if all(results.values()):
    import serial
    import numpy

# pyproject.toml에서 의존성 설치
from pathlib import Path
installed = install_sequence_dependencies(Path("sequences/my_sequence"))
```

---

## 실패 시 중단 (stop_on_failure)

### manifest.yaml

```yaml
parameters:
  stop_on_failure:
    display_name: "실패 시 중단"
    type: boolean
    default: true
    description: "스텝 실패 시 즉시 시퀀스 중단"
```

### sequence.py

```python
def __init__(self, ...):
    super().__init__(...)
    self.stop_on_failure = self.get_parameter("stop_on_failure", True)

async def run(self) -> RunResult:
    measurements = {}

    # Step 1
    try:
        self.emit_step_start("init", 1, 2, "초기화")
        # ... 로직
        self.emit_step_complete("init", 1, True, 1.0)
    except Exception as e:
        self.emit_step_complete("init", 1, False, 1.0, error=str(e))
        if self.stop_on_failure:
            return {"passed": False, "measurements": measurements,
                    "data": {"stopped_at": "init"}}

    # Step 2 (stop_on_failure=True면 여기까지 오지 않음)
    ...
```

---

## 유틸리티 메서드

```python
# 파라미터 가져오기
timeout = self.get_parameter("timeout", default=30.0)

# 하드웨어 설정 가져오기
config = self.get_hardware_config("device")
port = config.get("port", "/dev/ttyUSB0")

# 중단 체크 (중단 요청 시 AbortError 발생)
self.check_abort()

# 강제 중단
self.abort("사유")

# 사용자 확인 요청 (interactive 모드)
confirmed = await self.request_confirmation("계속하시겠습니까?", timeout=300)

# 사용자 입력 요청 (interactive 모드)
value = await self.request_input(
    prompt="값을 입력하세요",
    input_type="number",  # confirm, text, number, select
    default=10,
    timeout=300,
)
```

---

## 폴더 구조

```
my_sequence/
├── pyproject.toml     # Python 패키지 설정 (권장)
├── manifest.yaml      # 시퀀스 설정 (필수)
├── README.md          # 문서
├── my_sequence/       # 모듈 디렉토리
│   ├── __init__.py    # SequenceBase 구현 (필수)
│   └── drivers/       # 하드웨어 드라이버
│       ├── __init__.py
│       └── my_device.py
└── tests/             # 테스트
    ├── __init__.py
    └── test_sequence.py
```

---

## 타입 정의

```python
from station_service_sdk import (
    # 결과 타입
    RunResult,
    ExecutionResult,
    SimulationResult,

    # 측정/스텝 타입
    MeasurementDict,
    StepResultDict,
    StepMeta,
    StepInfo,

    # 설정 타입
    HardwareConfigDict,
    ParametersDict,
    MeasurementsDict,

    # Enum 타입
    ExecutionPhase,
    LogLevel,
    SimulationStatus,
    InputType,
)

async def run(self) -> RunResult:
    return {
        "passed": True,
        "measurements": {"voltage": 3.3},
        "data": {"device_id": "ABC123"}
    }
```

---

## 체크리스트

### 필수
- [ ] `SequenceBase` 상속
- [ ] `name`, `version`, `description` 클래스 속성 정의
- [ ] `setup()`, `run()`, `teardown()` 구현
- [ ] `manifest.yaml` 작성
- [ ] `run()` 메서드가 `RunResult` 반환
- [ ] **`station-sdk validate` 실행하여 검증 통과**

### 권장
- [ ] 적절한 `emit_step_start/complete` 호출
- [ ] 측정값에 `emit_measurement` 사용
- [ ] 예외 발생 시 SDK 예외 클래스 사용
- [ ] `check_abort()` 호출로 중단 요청 처리
- [ ] manifest.yaml에 setup/teardown 스텝 정의
- [ ] `stop_on_failure` 파라미터로 실패 시 동작 제어
- [ ] **`pyproject.toml` 작성하여 의존성 정의**
- [ ] **테스트 코드 작성 (`station_service_sdk.testing` 활용)**

---

## Validation 검사 항목

`station-sdk validate`가 검사하는 항목들:

| 검사 항목 | 설명 |
|-----------|------|
| YAML 문법 | manifest.yaml 파싱 가능 여부 |
| 스키마 검증 | Pydantic 모델 규격 준수 |
| 엔트리포인트 | module.py 파일 및 class 존재 여부 |
| 스텝 이름 매칭 | manifest steps ↔ `emit_step_start()` 일치 |
| 하드웨어 드라이버 | driver 파일 존재 여부 |
| 의존성 설치 (manifest) | dependencies.python 패키지 설치 여부 |
| 의존성 설치 (pyproject.toml) | pyproject.toml의 dependencies 설치 여부 |

### 스텝 이름 검증 예시

```
✗ Step name mismatch detected:
   → "sensor_test" emitted in sequence but not defined in manifest
   → "init" defined in manifest but not used in sequence

   Hint: manifest.yaml의 steps에 실제 emit하는 step 이름을 정의하세요.
```

---

## 템플릿 종류

### basic
기본적인 2단계 시퀀스 템플릿

### hardware
하드웨어 드라이버 통합 시퀀스 템플릿

### multi-step
동적 스텝 실행 패턴의 다단계 시퀀스 템플릿

```bash
station-sdk new my-sequence --template multi-step
```

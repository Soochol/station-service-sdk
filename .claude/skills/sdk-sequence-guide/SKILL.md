---
name: sdk-sequence-guide
description: Station Service SDK로 테스트 시퀀스 개발. SequenceBase 패턴, emit 메서드, manifest.yaml 작성.
---

# SDK Sequence Guide

Station Service SDK를 사용한 테스트 시퀀스 개발 가이드입니다.

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
  automatic: true
  manual: true
  cli: true

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

---

## 예외 처리

SDK에서 제공하는 예외 클래스들:

```python
from station_service_sdk import (
    SequenceError,      # 기본 예외
    SetupError,         # 초기화 실패
    TeardownError,      # 정리 실패
    StepError,          # 스텝 실행 오류
    TimeoutError,       # 타임아웃
    TestFailure,        # 테스트 실패
    HardwareError,      # 하드웨어 오류
    ConnectionError,    # 연결 오류
)

# 사용 예
async def setup(self) -> None:
    try:
        await self.device.connect()
    except Exception as e:
        raise SetupError(f"연결 실패: {e}")
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
```

---

## 폴더 구조

```
my_sequence/
├── manifest.yaml      # 패키지 설정 (필수)
├── sequence.py        # SequenceBase 구현 (필수)
├── main.py            # CLI 진입점 (optional)
└── drivers/           # 하드웨어 드라이버
    ├── __init__.py
    └── my_device.py
```

---

## CLI 실행

```bash
# 시퀀스 시작
python -m my_sequence.main --start --config '{"execution_id": "001"}'

# 설정 파일 사용
python -m my_sequence.main --start --config-file config.json

# Dry run (검증만)
python -m my_sequence.main --start --dry-run

# 시퀀스 중지
python -m my_sequence.main --stop
```

---

## 타입 정의

```python
from station_service_sdk.types import RunResult, MeasurementDict

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

### 권장
- [ ] 적절한 `emit_step_start/complete` 호출
- [ ] 측정값에 `emit_measurement` 사용
- [ ] 예외 발생 시 SDK 예외 클래스 사용
- [ ] `check_abort()` 호출로 중단 요청 처리

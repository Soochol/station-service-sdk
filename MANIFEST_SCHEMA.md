# Manifest Schema Reference

시퀀스 패키지의 `manifest.yaml` 파일 스키마 문서입니다.

## 전체 구조

```yaml
# 필수 필드
name: string              # 시퀀스 식별자 (Python 식별자 형식)
version: string           # 버전 (X.Y.Z 형식)
entry_point:              # 진입점 설정
  module: string
  class: string

# 선택 필드
author: string            # 작성자
description: string       # 설명
created_at: datetime      # 생성일시
updated_at: datetime      # 수정일시
modes: object             # 실행 모드
hardware: object          # 하드웨어 정의
parameters: object        # 파라미터 정의
steps: array              # 스텝 정의
dependencies: object      # 의존성
```

## 상세 스키마

### name (필수)

시퀀스의 고유 식별자입니다. Python 식별자 규칙을 따라야 합니다.

```yaml
name: psa_sensor_test  # OK
name: my-test          # ERROR: 하이픈 불가
name: 123test          # ERROR: 숫자로 시작 불가
```

### version (필수)

Semantic Versioning 형식 (X.Y.Z)을 따릅니다.

```yaml
version: "1.0.0"   # OK
version: "2.1.3"   # OK
version: "1.0"     # ERROR: Z 필요
```

### entry_point (필수)

시퀀스 클래스의 위치를 지정합니다.

```yaml
entry_point:
  module: sequence          # 모듈 파일명 (.py 제외)
  class: MyTestSequence     # 클래스 이름
  cli_main: main            # (선택) CLI 진입점 모듈
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| module | string | O | Python 모듈 경로 (예: `sequence`, `core.main`) |
| class | string | O | 클래스 이름 |
| cli_main | string | X | CLI 모드용 진입점 모듈 |

### modes

실행 모드를 설정합니다.

```yaml
modes:
  automatic: true      # 자동 순차 실행 (기본값: true)
  manual: true         # 수동 스텝별 실행 (기본값: false)
  interactive: false   # 대화형 프롬프트 (기본값: false)
  cli: true            # CLI 기반 서브프로세스 (기본값: false)
```

### hardware

하드웨어 컴포넌트를 정의합니다.

```yaml
hardware:
  mcu:                          # 하드웨어 키 (코드에서 참조)
    display_name: "MCU 컨트롤러"
    driver: drivers.mcu         # 드라이버 모듈 경로
    class: MCUDriver            # 드라이버 클래스 이름
    description: "STM32 MCU 연결"
    config_schema:              # (선택) 설정 스키마
      port:
        type: string
        required: true
        default: "/dev/ttyUSB0"
        description: "시리얼 포트"
      baudrate:
        type: integer
        required: false
        default: 115200
        min: 9600
        max: 921600
    manual_commands:            # (선택) 수동 제어 명령
      - name: reset
        display_name: "리셋"
        category: control
        description: "MCU를 리셋합니다"
        parameters: []
        returns:
          type: boolean
          description: "성공 여부"
```

#### config_schema 필드 타입

| type | Python 타입 | 추가 속성 |
|------|------------|----------|
| string | str | options (선택지) |
| integer | int | min, max, options |
| float | float | min, max |
| boolean | bool | - |

```yaml
config_schema:
  mode:
    type: string
    options: ["auto", "manual", "hybrid"]  # 선택지 제한
  timeout:
    type: float
    min: 0.1
    max: 300.0
```

### parameters

시퀀스 실행 파라미터를 정의합니다.

```yaml
parameters:
  timeout:
    display_name: "타임아웃"
    type: float
    default: 30.0
    min: 1.0
    max: 300.0
    unit: "초"
    description: "전체 실행 타임아웃"

  mode:
    display_name: "실행 모드"
    type: string
    default: "normal"
    options: ["normal", "debug", "fast"]

  enabled:
    display_name: "활성화"
    type: boolean
    default: true
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| display_name | string | O | UI 표시 이름 |
| type | string | O | string, integer, float, boolean |
| default | any | X | 기본값 (타입과 일치해야 함) |
| min | number | X | 최소값 (integer, float) |
| max | number | X | 최대값 (integer, float) |
| options | array | X | 허용 값 목록 |
| unit | string | X | 단위 (UI 표시용) |
| description | string | X | 설명 |

### steps

테스트 스텝을 정의합니다.

```yaml
steps:
  - name: init
    display_name: "초기화"
    order: 1
    timeout: 10.0
    estimated_duration: 5.0
    retry: 0
    cleanup: false
    manual:
      skippable: false
      auto_only: false
      prompt: "초기화를 시작합니다"
      pause_before: false
      pause_after: false
      parameter_overrides: []

  - name: test_voltage
    display_name: "전압 테스트"
    order: 2
    timeout: 30.0
    retry: 2                    # 실패 시 2회 재시도
    cleanup: false

  - name: cleanup
    display_name: "정리"
    order: 100
    timeout: 10.0
    cleanup: true               # 항상 실행 (이전 스텝 실패해도)
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| name | string | O | - | 스텝 식별자 |
| display_name | string | X | name | UI 표시 이름 |
| order | integer | O | - | 실행 순서 |
| timeout | float | X | 60.0 | 타임아웃 (초) |
| estimated_duration | float | X | 0.0 | 예상 소요 시간 (초) |
| retry | integer | X | 0 | 재시도 횟수 |
| cleanup | boolean | X | false | 항상 실행 여부 |
| manual | object | X | null | 수동 모드 설정 |

#### manual 설정

```yaml
manual:
  skippable: true          # 건너뛰기 가능
  auto_only: false         # 자동 모드에서만 실행
  prompt: "계속하시겠습니까?"  # 사용자 프롬프트
  pause_before: true       # 스텝 전 일시정지
  pause_after: false       # 스텝 후 일시정지
  parameter_overrides:     # 오버라이드 가능한 파라미터
    - timeout
    - retry_count
```

### dependencies

Python 패키지 의존성을 정의합니다.

```yaml
dependencies:
  python:
    - pyserial>=3.5
    - numpy>=1.20.0
    - pydantic>=2.0
```

## 전체 예제

```yaml
name: psa_sensor_test
version: "1.2.0"
author: "F2X Engineering"
description: "PSA 센서 테스트 시퀀스 (VL53L0X, MLX90640)"
created_at: "2024-01-15T10:00:00"
updated_at: "2024-06-20T14:30:00"

entry_point:
  module: sequence
  class: PSASensorTestSequence
  cli_main: main

modes:
  automatic: true
  manual: true
  cli: true

hardware:
  mcu:
    display_name: "PSA MCU"
    driver: drivers.psa_mcu
    class: PSAMCUDriver
    description: "STM32H723 기반 테스트 보드"
    config_schema:
      port:
        type: string
        required: true
        default: "/dev/ttyUSB0"
      baudrate:
        type: integer
        default: 115200
    manual_commands:
      - name: identify
        display_name: "식별"
        description: "MCU 정보 조회"
      - name: reset
        display_name: "리셋"
        category: control

parameters:
  tof_reference:
    display_name: "ToF 기준 거리"
    type: float
    default: 100.0
    min: 10.0
    max: 2000.0
    unit: "mm"
  ir_reference_temp:
    display_name: "IR 기준 온도"
    type: float
    default: 25.0
    unit: "°C"
  tolerance_percent:
    display_name: "허용 오차"
    type: float
    default: 5.0
    min: 0.1
    max: 20.0
    unit: "%"

steps:
  - name: connect
    display_name: "MCU 연결"
    order: 1
    timeout: 10.0
  - name: warmup
    display_name: "웜업"
    order: 2
    timeout: 5.0
    estimated_duration: 2.0
  - name: calibrate
    display_name: "캘리브레이션"
    order: 3
    timeout: 30.0
    retry: 1
  - name: test_tof
    display_name: "ToF 센서 테스트"
    order: 10
    timeout: 60.0
  - name: test_ir
    display_name: "IR 센서 테스트"
    order: 20
    timeout: 60.0
  - name: cleanup
    display_name: "정리"
    order: 100
    timeout: 5.0
    cleanup: true

dependencies:
  python:
    - pyserial>=3.5
```

## 검증

manifest.yaml 검증은 Pydantic 모델을 통해 수행됩니다:

```python
from station_service.sdk import SequenceManifest
import yaml

with open("manifest.yaml") as f:
    data = yaml.safe_load(f)

# 검증 (실패 시 ValidationError 발생)
manifest = SequenceManifest.model_validate(data)

# 헬퍼 메서드
print(manifest.get_hardware_names())  # ['mcu']
print(manifest.get_step_names())      # ['connect', 'warmup', ...]
print(manifest.is_cli_mode())         # True
```

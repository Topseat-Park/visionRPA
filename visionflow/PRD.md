# VisionFlow PRD v3.0

**작성일**: 2026-03
**개발 환경**: GCP VM (Linux)
**실행 환경**: Agent (Windows 11 Enterprise · OpenStack Nova VM (Cloud PC)), Dashboard: (GCP VM (Linux) 개발, 양산후 Docker)
**AI 모델**: Gemini 3 Flash (Vertex AI, asia-northeast3,
GCP_PROJECT_ID="pjt-lge-heqdx"
GCS_BUCKET_NAME="qdx-prod"
GOOGLE_APPLICATION_CREDENTIALS=/opt/gcp_keys/dev/qdx.json)
**알림**: SMTP localhost
**기본 해상도**: 동적 감지 (mss + ctypes DPI) — 하드코딩 없음
**범위**: 1인 개인 자동화 도구 (PoC)

---

## 1. 제품 목표

> 사용자가 직접 수행한 반복 업무를 화면 녹화로 캡처하면, AI가 그 의도를 이해하여 동일한 작업을 자동으로 재현·반복 실행할 수 있는 시스템.

### 핵심 설계 원칙

1. **실패해도 사용자가 직접 고칠 수 있어야 한다** — 실패 원인과 수정 방법을 자연어로 설명
2. **Vision은 최후 수단** — CMD·단축키·클립보드 우선, Gemini는 꼭 필요할 때만
3. **신뢰하기 전까지 사람이 확인** — 모든 vision_click은 Human-in-the-Loop 기본값
4. **PoC는 단순하게** — 동작하는 것을 먼저, 복잡한 기능은 Step 2에

---

## 2. 확정된 환경

| 항목 | 내용 |
|---|---|
| 개발 환경 | GCP VM (Linux) · VS Code Remote SSH |
| 실행 환경 | Windows 11 Enterprise · OpenStack Nova VM |
| 지원 OS | **Windows 전용** |
| 네트워크 | Cloud PC → GCP Cloud Run HTTPS 직접 접근 |
| AI 모델 | Gemini 3 Flash (Vertex AI, asia-northeast3) |
| 저장소 | GCS (PoC 단계: 로컬 파일 시스템) |
| 기본 해상도 | 동적 감지 (mss + ctypes DPI) — 하드코딩 없음 |
| 알림 | SMTP 이메일 |
| 보안 | 최소화 (1인 도구) |
| 서버 배포 | Docker Compose (GCP VM) |
| Agent 배포 | PyInstaller `.exe` (Cloud PC 설치) |

### Agent 설치가 불가피한 이유

브라우저 샌드박스에서 불가능한 것들:
- OS 레벨 마우스·키보드 제어 (`PyAutoGUI`, `pynput`)
- 전체 화면 캡처 (`mss`)
- 실행 중 앱·창 감지 (`psutil`, `pywin32`)

### PC 제어 충돌 해결

**환경 확인 결과**: Windows 11 Enterprise (OpenStack Nova VM) · 단일 세션 · RDP 다중 세션 현재 미허용

| 우선순위 | 모드 | 조건 |
|---|---|---|
| 1순위 | RDP 세컨드 세션 | IT팀 허용 시 — 완전 분리 (가능성 열어둠) |
| 2순위 | 수동 실행 | 사용자 직접 [실행] 클릭 — 5초 카운트다운 후 시작 |
| 2순위 | 스케줄 자동 실행 | 업무 외 시간 권장 (출근 전·점심·퇴근 후) |

**일시정지 안전장치**: 실행 중 마우스 이동·키 입력 감지 → 즉시 일시정지 → [재개] 클릭 시 현재 화면 재확인 후 이어서 실행

**RDP 활성화 시 (향후)**: `mstsc → 127.0.0.1` 에이전트 전용 세션 · 대시보드 설정에서 "RDP 세션 모드" 토글

---

## 3. 시스템 구조 (3-Layer)

```
[RECORD]    Cloud PC — 이벤트 감지 + 스크린샷 → 로컬/GCS 저장
[UNDERSTAND] GCP VM — Gemini 분석 → 워크플로우 JSON 생성
[REPLAY]    Cloud PC — 스텝 실행 + 결과 검증
모든 레이어 ↕ Dashboard (FastAPI + React, HTTPS)
```

### 개발 환경 및 배포

| 구분 | 위치 | 방식 | 내용 |
|---|---|---|---|
| 코드 편집 | GCP VM (Linux) | VS Code Remote SSH | 모든 서버 컴포넌트 개발 |
| 서버 실행 | GCP VM (Linux) | Docker Compose | Dashboard + Workflow Builder |
| Agent 실행 | Cloud PC (Windows) | .exe 직접 설치 | 화면 캡처·마우스·키보드 제어 |
| Agent 테스트 | Cloud PC (Windows) | 로컬 Python 직접 실행 | Windows 전용 API 테스트 |

**Agent를 Docker로 실행할 수 없는 이유**: `pynput`, `PyAutoGUI`, `pywin32` 등 Windows 전용 API는 Linux 컨테이너에서 동작하지 않음.

```yaml
# docker-compose.yml (GCP VM)
services:
  dashboard:
    build: ./dashboard
    ports: ["8000:8000"]
    environment:
      - GCS_BUCKET, VERTEX_PROJECT, VERTEX_REGION=asia-northeast3
  frontend:
    build: ./frontend
    ports: ["5173:5173"]
```

### 테스트 전략

| 컴포넌트 | 테스트 위치 | 방법 |
|---|---|---|
| Dashboard / Builder | GCP VM | `docker compose up` + pytest + Gemini mock |
| Agent 이벤트 캡처 | Cloud PC | `python recorder.py` 직접 실행 |
| Agent 화면 제어 | Cloud PC | 메모장으로 클릭·타이핑 검증 |
| E2E | Cloud PC + GCP VM | 메모장 3스텝 (실행·입력·저장) |

---

## 4. 기능 요구사항

### 4.1 녹화 시작 전 사전 입력

Gemini 프롬프트에 직접 주입되는 맥락 정보.

**필수:**
- 워크플로우 목적 (한 줄) — 각 스텝 의도 파악의 핵심
- 사용 앱·시스템

**선택 (입력할수록 품질 향상):**

| 항목 | 옵션 | Gemini 활용 |
|---|---|---|
| 예외 상황 체크박스 | 팝업·로그인만료·느린로딩 | on_failure 정책 자동 설정 |
| 기타 예외 (자유 입력) | 자유 텍스트 | 시스템 프롬프트 힌트 주입 |
| 민감 정보 포함 | 비밀번호·개인정보 체크 | 해당 구간 캡처 제외·블러 |

> 반복 루프 정의는 Step 2에서 추가.

### 4.2 녹화 (Record)

**녹화 제어 상태**: `대기 → 녹화중 → 일시정지 → 재개 → 완료`

- 일시정지 중 이벤트 캡처 없음
- 완료 후 타임라인에서 구간 잘라내기 (seq 범위 선택)

**이벤트 캡처 대상 (8종):**

| 타입 | 수집 내용 | 스크린샷 |
|---|---|---|
| `app_launch` | 앱 이름, 경로 | O |
| `click` | x, y, 버튼 | O |
| `double_click` | x, y | O |
| `type` | 텍스트 (0.5초 디바운스) | O |
| `key` | 단축키 조합 | O |
| `scroll` | 방향, 횟수 | O |
| `drag` | 시작·종료 좌표 | O × 2 |
| `window_change` | 창 제목, 앱 이름 | O |

**스크린샷 처리 및 해상도 관리:**

해상도는 하드코딩하지 않고 Agent가 동적으로 감지합니다.

감지 타이밍:
- Agent 시작 시 — 모니터 구성 감지 후 대시보드 전송 (모니터 선택 UI에 표시)
- 각 캡처 직전 — 재감지 (RDP 창 크기·DPI 변경 반영)
- 해상도 변경 감지 시 — 실행 중이면 경고 표시

캡처 시 저장하는 메타데이터 (이벤트 로그에 포함):
- `capture_width`, `capture_height` — 실제 캡처 해상도
- `dpi_scale` — Windows DPI 스케일링 비율 (125% → 1.25)
- `monitor_index` — 어느 모니터를 캡처했는지

좌표 변환 공식 (재실행 시 동적 계산):
- `real_x = gemini_x × (current_width / capture_width) × dpi_scale`
- `real_y = gemini_y × (current_height / capture_height) × dpi_scale`

리사이즈 정책 — **원본 해상도 그대로 Gemini 전송 (정확도 우선)**:
- 1920×1080 JPEG 85% ≈ 200~400KB, 비용 영향 미미
- 예외: 단일 이미지 4MB 초과 시에만 리사이즈
- 멀티모니터 전체 캡처 방지 — 대상 모니터만 캡처 기본값

**이벤트 전처리 (Gemini 전송 전):**
- 동일 좌표 클릭이 2초 내 3회 이상 → 1회로 압축
- 타이핑 후 즉시 전체선택·삭제 패턴 → 해당 타이핑 제거
- 연속 스크롤 → 방향·총량 합산

**녹화 품질 검증:**
- 이벤트 수 < 3개 → 재녹화 유도
- 유효 스크린샷 < 이벤트의 50% → 경고
- 원본 이벤트 로그는 항상 보존

**녹화 중 실시간 힌트:** 대시보드 메모창 입력 → 해당 시점 이벤트에 힌트 첨부

### 4.3 이해 — 워크플로우 생성 (Understand)

**실행 방식 우선순위 (Gemini 지시사항에 포함):**

| 순위 | 타입 | 조건 | 이유 |
|---|---|---|---|
| 1 | `cmd` | 앱 실행, 파일 조작 | 빠름, UI 무관, 100% 안정 |
| 2 | `hotkey` | 단축키로 가능한 경우 | 즉각, 앱 내 표준 |
| 3 | `clipboard_paste` | 텍스트 입력 10자 이상 | 오타 없음, 100배 빠름 |
| 4 | `navigate` | URL 이동 | |
| 5 | `scroll` / `drag` / `wait` | 해당 동작 | |
| 6 | `vision_click` | 위 모두 불가능한 동적 UI만 | LLM 추론 필요, 최후 수단 |

> `win32_focus`는 `cmd` 타입(subprocess)으로 처리.

**워크플로우 JSON 스키마 (스텝 타입 8종):**

```json
{
  "workflow_id": "wf_20260317",
  "name": "ERP 일일 매출 다운로드",
  "description": "한 줄 설명",
  "version": 1,
  "last_successful_version": 1,
  "default_speed": "normal",
  "steps": [
    {
      "id": 1,
      "type": "cmd | hotkey | clipboard_paste | vision_click | navigate | scroll | drag | wait",
      "description": "사람이 읽을 수 있는 설명",
      "value": "실행값 (cmd명령·텍스트·단축키·URL)",
      "target_description": "찾을 UI 요소 설명 (vision_click 전용)",
      "hint": "요소 탐지 보조 힌트",
      "wait_condition": "다음 스텝 진행 조건",
      "timeout_sec": 10,
      "speed": "fast | normal | slow",
      "on_failure": "retry | human | skip | abort",
      "screenshot_ref": "스크린샷 경로"
    }
  ]
}
```

**워크플로우 생성 후 자동 요약 리포트 (Gemini):**

생성 완료 시 즉시 분석 후 대시보드에 표시:
- 전체 흐름 한 줄 요약
- 주의 필요한 스텝 (vision_click이거나 복잡한 조건)
- 개선 가능한 스텝 (cmd 대체 가능 등)
- 권장 첫 실행 방식 (드라이런 권장 여부)
- 예상 소요 시간

**생성 실패 처리:**
- 자동 재시도 2회 → 실패 시 원본 이벤트 로그 보존 + "다시 생성 시도" 버튼

### 4.4 재실행 — Replay Engine

**실행 모드 (PoC 단순화):**

모든 `vision_click` 스텝은 Human-in-the-Loop 기본값.
- 실행 전 현재 화면 + 예상 클릭 위치 오버레이 → [승인] [수정] [취소]
- 자동 실행 스텝: `cmd`, `hotkey`, `clipboard_paste`, `navigate`, `scroll`, `drag`, `wait`

> trust_score 기반 자동 전환은 Step 2에서 추가.

**스텝 타입별 실행 방식:**

| 타입 | 실행 방법 |
|---|---|
| `cmd` | subprocess.Popen (앱 실행, 파일 조작, 창 포커스 포함) |
| `hotkey` | PyAutoGUI hotkey |
| `clipboard_paste` | pyperclip.copy → Ctrl+V |
| `navigate` | cmd로 URL 열기 |
| `scroll` | PyAutoGUI scroll |
| `drag` | PyAutoGUI drag |
| `wait` | 스마트 대기 |
| `vision_click` | Gemini 요소 탐지 → Human-in-the-Loop → PyAutoGUI click |

**스마트 대기:**
- 액션 후 최대 `timeout_sec`(기본 10초) 폴링
- 1초 간격 캡처 → Gemini가 `wait_condition` 달성 여부 판단
- 조건 충족 즉시 다음 스텝으로

**Gemini 자율 분기 (실행 중 예외 처리):**
- 팝업·확인창 감지 → 자동 닫기 시도
- 로그인 만료 화면 감지 → human 개입 요청
- 로딩 스피너 감지 → 최대 30초 추가 대기
- 스텝당 최대 5회 판단 → 초과 시 human 강제

**on_failure 정책:**

| 값 | 동작 |
|---|---|
| `retry` | 최대 3회 재시도 |
| `human` | 대시보드 알림 + 일시정지 |
| `skip` | 현재 스텝 건너뛰기 |
| `abort` | 전체 중단 + 실패 알림 |

**실행 완료 후 결과 검증 (2단계):**

최종 화면을 Gemini가 보고 판단:
- `success`: 워크플로우 목적 달성 확인
- `failure`: 목적 미달성 또는 오류 상태

**실패 시 자가 진단 리포트 (Gemini):**

대시보드 실패 패널에 표시:
- 실패 원인 한 문장 (자연어)
- `target_description` / `hint` 수정 제안 (구체적)
- 실행 방식 변경 제안 (있다면)
- [이 스텝 편집하기] 버튼으로 즉시 이동

**드라이런 모드:** 실제 클릭 없이 각 스텝의 예상 클릭 위치를 화면에 표시만 하는 검증 모드.

**실행 속도:**
- `fast`: 스텝 간 0.3초
- `normal`: 1초 (기본값)
- `slow`: 2초 (느린 앱용)

워크플로우 단위 + 스텝별 개별 오버라이드.

### 4.5 PC 제어 충돌 해결

실행 모드 2가지:

| 모드 | 진입 방법 | 비고 |
|---|---|---|
| 수동 실행 | [지금 실행] 클릭 | 5초 카운트다운 후 시작 |
| 스케줄 자동 실행 | 등록된 스케줄 자동 트리거 | 업무 외 시간 권장 |

**일시정지 안전장치 (공통):**
```
1. 실행 중 마우스 이동·키 입력 감지 → 즉시 일시정지
2. 대시보드에 "일시정지됨" 표시 + [재개] [중단] 버튼
3. 재개 시 현재 화면 재캡처 → Gemini 상태 재확인 후 이어서 실행
```

---

## 5. 대시보드 (FastAPI + React — GCP VM)

**접근**: Cloud PC 브라우저 → GCP VM HTTPS URL

**상단 고정 Agent 상태 표시:**
```
● 온라인 (녹색) / ○ 오프라인 (회색) / ⟳ 실행 중 (주황)
```

오프라인 상태에서 [실행] 또는 스케줄 트리거 → 즉시 실패 알림

### 페이지 구성 (7개)

**① 홈 — 워크플로우 목록**
- 카드별: 이름, 설명, 마지막 실행 시각, 성공률, 마지막 성공 버전 표시
- 버튼: [실행] [편집] [스케줄] [복제]

**② 녹화 페이지**
- 사전 입력 폼 (4.1항)
- [녹화 시작] [일시정지] [재개] [중지]
- 실시간 이벤트 로그 스트림
- 녹화 중 힌트 메모창
- 완료 후 타임라인 구간 잘라내기
- 워크플로우 생성 → **생성 요약 리포트** 표시 → 편집 페이지로

**③ 워크플로우 편집 페이지**
- 스텝 리스트 (순서 변경·삭제·추가·사이 삽입)
- 각 스텝 펼치면: 참고 스크린샷 + 모든 필드 편집
- **[단독 테스트]**: 해당 스텝 1개만 즉시 실행 → 결과 확인
- **[드라이런]**: 예상 클릭 위치 화면 표시
- [저장] → 새 버전 저장 + 이전 버전 보존
- 버전 목록: 각 버전에 "N회 성공" + "마지막 성공 버전" 태그

**④ 실행 모니터링 페이지**
- 실행 중 스텝 강조 + 진행률
- 스텝별 성공/실패/소요시간
- Human-in-the-Loop 패널: 스크린샷 + 예상 클릭 오버레이 + [승인] [수정] [취소]
- 실패 패널: **자가 진단 리포트** + [이 스텝 편집] [재시도] [스킵] [중단]
- 완료 패널: 결과 검증 (success / failure)

**⑤ 실행 이력 페이지**
- 전체 이력 목록
- 필터: 날짜 범위 / 성공·실패 / 워크플로우 이름
- 이력 클릭 → 스텝별 상세 (결과·스크린샷·소요시간)

**⑥ 스케줄 관리 페이지**
- 등록: 매일 / 매주 / Cron 표현식
- 활성화·비활성화 토글
- 다음 실행 예정 시각
- 최근 5회 실행 이력

**⑦ 설정 페이지**
- GCS 버킷, Vertex AI Project/Region
- 알림 이메일 (SMTP)
- 스크린샷 보관 기간 (기본 30일)
- 기본 timeout (10초), 기본 실행 속도
- RDP 세션 모드 토글 (IT 허용 시)

---

## 6. 스케줄링 (무인 자동 실행)

```
Cloud Scheduler (Cron)
  → Backend /trigger
  → Agent IPC "run:{workflow_id}"
     (오프라인 또는 잠금 화면 → 즉시 실패 알림)
  → Replay Engine 실행
  → 결과 검증 (success / failure)
  → 로컬/GCS 이력 저장
  → 이메일 알림 (failure 필수 / success 선택)
```

**실행 전 조건 체크:**
- Agent 온라인 여부 (오프라인 → 즉시 실패 알림)
- Cloud PC 잠금 화면 여부 (잠금 → 실패 알림)
- 이전 실행 진행 중 여부 (중복 실행 방지)

**이메일 알림 내용 (failure):**
워크플로우 이름, 실행 시각, 실패 스텝, 원인, 수정 제안, 스크린샷 경로

---

## 7. Agent 안정성

**자동 시작:**
- Agent .exe를 Windows 시작 프로그램에 등록 (HKCU 레지스트리 — 관리자 권한 불필요)
- Cloud PC 재시작 후 자동 실행 → 스케줄 실행 시 Agent 오프라인 방지

**IPC 재연결:**
- 파일 기반 IPC: 연결 끊김 없음 (파일 폴링 방식)
- WebSocket 전환 후: 5초 자동 재연결, 최대 10회 재시도

**Gemini API 장애 대응:**
- API 호출 타임아웃: 30초
- 타임아웃 또는 오류 발생 시: `abort` 처리 + 이메일 알림

---

## 8. 온보딩 흐름

Agent 최초 실행 시 설정 마법사:
1. Vertex AI Project ID / Region 입력 + API 호출 테스트
2. 알림 이메일 / SMTP 설정
3. 연결 확인 완료 → 대시보드 URL 표시 + 첫 녹화 안내
4. Windows 시작 프로그램 자동 등록 여부 확인

설정값: `config.json` 로컬 저장

---

## 9. 보완 정의 항목

### 9.1 버전 관리와 실행 이력 연결

```json
{
  "version": 3,
  "success_count": 12,
  "last_success_run_id": "run_20260317_090000",
  "is_last_successful": true
}
```

- 편집 저장 시 새 버전 생성, 이전 버전 보존
- 각 버전에 "N회 성공" 표시
- "마지막 성공 버전"으로 즉시 복원 가능

### 9.2 롤백 없음 명시

실행 중단 시 현재 상태 유지 (롤백 미지원). 사용자가 수동 정리 후 재시작.

### 9.3 Agent 업데이트

PoC 단계: 수동 재설치. `config.json`은 업데이트 후 유지.

### 9.4 GCS 비용 안전장치

- 스크린샷 자동 삭제: 30일 경과 시 GCS Lifecycle 정책으로 자동 삭제
- PoC 단계에서는 로컬 파일 시스템 사용 (GCS 전환 시 storage.py만 교체)

---

## 10. 데이터 구조

```
visionflow_data/             ← PoC: 로컬 폴더 (GCS 전환 시 동일 구조 유지)
│
├── sessions/{session_id}/
│   ├── events.jsonl         # 이벤트 로그 (원본 보존)
│   ├── meta.json            # 사전 입력 (목적·예외 등)
│   └── screenshots/         # 이벤트 시점 스크린샷
│
├── workflows/{workflow_id}/
│   ├── v1.json              # 최초 생성본
│   ├── v2.json              # 편집본 (버전 누적)
│   ├── latest.json          # 최신 버전 포인터
│   └── summary.json         # 생성 요약 리포트
│
├── runs/{run_id}/
│   ├── meta.json            # workflow_id·버전·시각·결과·소요시간
│   ├── verification.json    # 결과 검증 (success/failure + 근거)
│   ├── diagnosis.json       # 실패 진단 리포트 (실패 시)
│   └── steps/
│       ├── step_001_before.jpg
│       └── step_001_after.jpg
│
├── schedules/
│   └── schedules.json       # 스케줄 설정
│
└── control/                 # Agent ↔ Dashboard IPC (파일 기반)
    ├── command.json         # Dashboard → Agent 명령
    └── status.json          # Agent → Dashboard 상태
```

---

## 11. 기술 스택

| 역할 | 기술 |
|---|---|
| 이벤트 감지 | `pynput` |
| 화면 캡처 | `mss` |
| OS 제어 | `PyAutoGUI`, `pyperclip`, `subprocess` |
| 앱·창 감지 | `psutil`, `pywin32` |
| AI | Gemini 3 Flash (Vertex AI) — Phase 2 |
| 저장소 | 로컬 파일 시스템 → GCS 전환 예정 |
| 백엔드 | FastAPI + Python 3.11+ (uv workspace) |
| 프론트엔드 | React 18 + Vite + TypeScript + shadcn/ui + TanStack Router |
| Agent 통신 | 파일 기반 IPC → WebSocket 전환 예정 |
| 스케줄 | APScheduler (로컬) → GCP Cloud Scheduler 전환 예정 |
| Agent 배포 | PyInstaller `.exe` |
| 알림 | SMTP 이메일 |

---

## 12. 리스크 및 대응

| 리스크 | 대응 |
|---|---|
| Gemini 좌표 부정확 | 모든 vision_click Human-in-the-Loop + 자가 진단으로 힌트 보강 |
| 해상도·DPI 좌표 오차 | 캡처 시 메타데이터 저장 → 재실행 시 동적 변환 비율 계산 |
| IPC 연결 끊김 | 파일 기반 폴링 방식 → WebSocket 전환 후 자동 재연결 |
| Gemini API 장애 | 30초 타임아웃 → abort + 이메일 알림 |
| Agent 미실행 상태 스케줄 | 실행 전 온라인 체크 → 오프라인 시 즉시 실패 알림 |
| Cloud PC 잠금 화면 | 실행 전 잠금 체크 → 실패 알림 |
| 실행 중 사용자 충돌 | 마우스 감지 → 일시정지 + [재개] |
| cmd 잘못된 명령 | 스텝별 [단독 테스트]로 사전 검증 |
| GCS 비용 누적 | 30일 자동 삭제 Lifecycle |

---

## 13. PoC 완료 기준

### Phase 1 — Record + 기본 Replay (부분 완료)
- [x] 이벤트 8종 캡처 + 이벤트 전처리
- [x] 사전 입력 UI + meta.json 저장
- [x] 일시정지/재개
- [x] 해상도·DPI 동적 감지 및 메타데이터 저장
- [x] 파일 기반 IPC (command.json / status.json)
- [x] FastAPI 백엔드 + React 대시보드
- [x] 규칙 기반 워크플로우 생성 (이벤트 → 스텝 변환)
- [x] pyautogui 기반 재실행 엔진 (기본 동작)

### Phase 1.5 — UI 완성도 + Replay 안정성 (진행 중)
- [x] 이벤트 타임라인 스크린샷 확대 보기 (클릭 → 풀스크린)
- [x] 워크플로우 편집 페이지 (스텝 편집/삭제/순서변경/저장/버전이력)
- [x] on_failure=retry 실제 재시도 (최대 3회, 점진적 백오프)
- [x] 스텝별 timeout 적용 (ThreadPoolExecutor)
- [x] 스텝별 before/after 스크린샷 캡처
- [x] wait 스텝 abort 대응 (0.5초 단위 체크)
- [x] 실행 이력 페이지 (목록 + 상태 필터 + 상세 보기)
- [x] 실행 실패 시 상세 에러 정보 (스텝 컨텍스트)
- [x] Run 시작 후 모니터 페이지 자동 이동 (useNavigate + onSuccess)
- [x] Run Monitor polling 10분 타임아웃 (무한 루프 방지 + 경고 UI)
- [x] 서버 재시작 시 orphan run 자동 정리 (5분 이상 pending/running → aborted)
- [x] screenshot.py DPI 중복 호출 제거 + 캐싱
- [x] 워크플로우 저장 시 step id 정규화 (1부터 재할당)
- [x] Generate 중복/빈 세션 방지 (409/400) + 에러 핸들링
- [x] click/double_click 스텝에 fallback_coords 추가
- **완료 기준**: 워크플로우 편집→저장→재실행→이력 확인 전체 흐름 동작

### Phase 2 — Understand (완료)
- [x] Gemini 3 Flash 연동 (google-genai SDK)
- [x] 실행 방식 우선순위 계층 프롬프트 (cmd 우선)
- [x] 워크플로우 생성 후 요약 리포트
- [x] vision_click에 실제 이미지 기반 타겟 설명 추가
- **완료 기준**: 10개 이벤트 → 의미 있는 워크플로우 + 요약 리포트

### Phase 2.5 — 엔터프라이즈 앱 컨텍스트 인식 강화 (완료)
- [x] 녹화 중 활성 창 추적 — 모든 이벤트에 `active_window` 필드, 창 전환 시 `window_change` 자동 삽입
- [x] `focus_window` 스텝 타입 — 이미 열린 앱 창을 찾아서 전면 활성화 (OTP 세션 재활용)
- [x] Gemini 프롬프트 앱 컨텍스트 규칙 — 브라우저/Office/Outlook 시나리오 대응
- [x] Gemini 스키마 + 프론트엔드 UI — focus_window enum, 라벨, 색상, 도움말
- [x] 녹화 시작 시 열린 창 목록 스냅샷 — meta.json `open_windows` 필드
- [x] OpenCV 템플릿 매칭 — vision_click 3단계 fallback (AI → OpenCV → 좌표)
- [x] `crop_ref` 필드 — 워크플로우 스텝에 크롭 이미지 경로 저장
- **완료 기준**: 녹화 중 앱 전환 감지 + focus_window 스텝 생성/실행 가능 + 창 이동 시에도 OpenCV로 클릭 위치 정확 탐지

### Phase 3 — Replay 고도화 (완료)
- [x] vision_click Human-in-the-Loop UI — 파일 기반 HITL (hitl_request/response.json), Run Monitor에서 승인/수정/취소
- [x] 스마트 대기 (wait_condition 1초 간격 폴링 루프)
- [x] Gemini 자율 분기 — 스텝 실행 전 화면 분석 (popup→자동 닫기, loading→대기, login_expired→human)
- [x] 결과 검증 (success/failure) — Gemini 기반 최종 화면 검증 + verification.json
- [x] 실패 자가 진단 리포트 — Gemini 기반 원인 분석 + 수정 제안 + diagnosis.json
- [x] 드라이런 모드 — 실제 실행 없이 vision_click 좌표 탐지 결과 반환
- [x] 스텝별 [단독 테스트] — 워크플로우 편집에서 개별 스텝 즉시 실행
- **완료 기준**: 동일 PC 재실행 성공률 ≥ 70% + 실패 진단 리포트 생성

### Phase 3.5 — Gemini Computer Use 통합 (완료, API 사양 준수 리팩토링)
- [x] Computer Use 에이전트 루프 (`agent/ai/computer_use.py`) — 공식 Gemini Computer Use API 사양 준수
- [x] `types.Tool(computer_use=types.ComputerUse(environment=ENVIRONMENT_BROWSER, excluded_predefined_functions=[...]))` 도구 설정
- [x] 데스크톱 환경: `open_web_browser`, `search`, `go_forward` 제외 (navigate, go_back은 유지)
- [x] FunctionResponse에 스크린샷 blob(`inline_data=types.Blob`) 포함
- [x] 정규화 좌표(0-999) → 실제 픽셀 변환 + pyautogui 액션 실행
- [x] 전체 액션 지원: click_at, hover_at, type_text_at(press_enter/clear_before_typing), key_combination(문자열 "Control+C"), scroll_document(상하좌우), scroll_at(magnitude), drag_and_drop(destination_x/y), navigate, go_back, go_forward, open_web_browser, search, wait_5_seconds
- [x] safety_decision 처리 — args 내부 `safety_decision.decision`/`explanation` 파싱, USER_CONFIRM 시 HITL 연동, 확인 후 `safety_acknowledgement: "true"` 전송
- [x] `thinking_config=types.ThinkingConfig(include_thoughts=True)` 적용
- [x] 병렬 function_call 지원 — 모델이 여러 function_call 반환 시 모두 실행 후 각각 FunctionResponse 전송
- [x] 추론 텍스트 로그 저장 (`reasoning_log.txt`), 턴별 스크린샷, 액션 로그
- [x] vision_finder Phase 0 — Computer Use 도구 설정으로 더 정확한 좌표 탐지 (실패 시 기존 방식 fallback)
- [x] replayer engine `computer_use` 모드 — 워크플로우 목표만 주면 자율 실행
- [x] backend API `mode=computer_use` 지원 + 실행 결과 조회
- [x] frontend "Computer Use로 실행" 버튼 + 실시간 턴 로그 표시
- [x] agent config: `computer_use_model`, `computer_use_max_turns` 설정
- **완료 기준**: Computer Use 모드로 간단한 워크플로우 자율 실행 + 턴별 로그 확인

### Phase 4 — MCP + LangChain AI 에이전트 (예정)
- [ ] LangChain + LangGraph ReAct 에이전트 루프 도입
- [ ] langchain-mcp-adapters로 MCP 서버 연결
- [ ] @playwright/mcp 연동 — 브라우저 자동화 (접근성 트리 기반)
- [ ] @modelcontextprotocol/server-filesystem 연동 — 파일 작업
- [ ] 기존 비전 방식(스크린샷+pyautogui)과 MCP 도구 하이브리드 선택
  - 브라우저 작업 → Playwright MCP (접근성 트리, 빠르고 정확)
  - 네이티브 앱/RDP → 기존 비전 방식 (스크린샷+Gemini)
- [ ] 챗봇 인터페이스에서 자연어 명령으로 워크플로우 실행
- **완료 기준**: "사이트에서 검색 후 파일 다운로드 → 수정" 시나리오 E2E 동작

### Phase 5 — 운영 안정화 (예정)
- [ ] 스케줄링 (크론 기반 자동 실행)
- [ ] GCS 스토리지 전환
- [ ] 다중 Agent 지원
- [ ] SMTP 이메일 알림
- [ ] PyInstaller .exe 패키징 + 온보딩 마법사
- [ ] WebSocket 기반 실시간 IPC

---

## 14. Step 2 추가 기능 (PoC 이후)

| 기능 | 설명 |
|---|---|
| trust_score 자동 전환 | vision_click 신뢰 점수 누적 → 자동 모드 전환 |
| loop 스텝 타입 | 목록 반복 실행 엔진 |
| condition 스텝 타입 | if-else 조건 분기 실행 |
| 스텝 재사용 라이브러리 | 공통 스텝 블록 저장·재사용 |
| 자연어 스텝 수정 | Gemini가 수정 제안 |
| 워크플로우 건강 점수 | 성공률·소요시간·취약 스텝 점수화 |
| GCS 전환 | storage.py 교체로 로컬 → GCS 마이그레이션 |
| WebSocket 전환 | 파일 IPC → WebSocket 실시간 통신 |

---

## 15. 비용 추정 (월간, GCS 전환 후)

| 항목 | 예상 사용량 | 월 비용 |
|---|---|---|
| Gemini — 워크플로우 생성 | 10회 × 이미지 20장 | ~$0.06 |
| Gemini — Replay 요소 탐지 | 50실행 × 5스텝 | ~$0.08 |
| Gemini — 결과 검증·진단 | 50실행 × 2회 | ~$0.03 |
| GCS | ~5GB | ~$0.10 |
| Cloud Run | 상시 1 vCPU | ~$1.50 |
| Cloud Scheduler | 5개 스케줄 | ~$0.50 |
| **합계** | | **≈ $2.3/월** |

---

## 16. 로컬 실행 방법 (PoC)

```bash
# Backend
cd visionflow
~/.local/bin/uv.exe run uvicorn backend.main:app --reload --port 8000

# Frontend (별도 터미널)
cd visionflow/frontend
npm run dev  # http://localhost:5173

# Agent (별도 터미널, Windows)
cd visionflow
~/.local/bin/uv.exe run visionflow-agent
```

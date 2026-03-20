# VisionFlow 요구사항

## 프로젝트 정보
- **제품명**: VisionFlow — AI 기반 화면 녹화·재현 자동화 도구
- **범위**: 1인 개인 자동화 도구 (PoC)
- **실행 환경**: Windows 11 Enterprise (OpenStack Nova VM, Cloud PC)
- **개발 환경**: GCP VM (Linux) · VS Code Remote SSH
- **AI 모델**: Gemini 3 Flash (Vertex AI, asia-northeast3) — Phase 2부터 적용

## 기술 스택

### 프론트엔드 (대시보드)
- React 19 + TypeScript
- Vite 8
- TanStack Router (파일 기반 라우팅)
- TanStack React Query (서버 상태 관리)
- Zustand (클라이언트 상태)
- shadcn/ui + Tailwind CSS 4
- Lucide React (아이콘)

### 백엔드
- FastAPI + Python 3.11+
- uvicorn (ASGI 서버)
- Pydantic 2.0+ (데이터 검증)
- 로컬 파일 시스템 (JSON/JSONL) — GCS 전환 예정

### Agent (Windows 전용)
- pynput (마우스·키보드 이벤트 캡처)
- mss (스크린 캡처)
- PyAutoGUI (마우스·키보드 제어 — 재실행)
- pyperclip (클립보드)
- pywin32 (Windows API — DPI, 창 감지)
- psutil (시스템 메트릭)
- Pillow (이미지 처리)

### 패키지 관리
- uv workspace (모노레포: shared, backend, agent)
- npm (프론트엔드)

## 아키텍처 (3-Layer)
```
[RECORD]    Cloud PC — pynput 이벤트 감지 + mss 스크린샷 → 로컬 저장
[UNDERSTAND] GCP VM — Gemini 분석 → 워크플로우 JSON 생성 (Phase 2)
[REPLAY]    Cloud PC — PyAutoGUI 스텝 실행 + 결과 검증
모든 레이어 ↕ Dashboard (FastAPI + React, HTTPS)
```

### 통신 방식
- Agent ↔ Backend: 파일 기반 IPC (command.json / status.json 폴링)
- Frontend ↔ Backend: REST API (React Query 2초 폴링)

## 데이터 구조
```
visionflow_data/
├── sessions/{session_id}/
│   ├── events.jsonl         # 이벤트 로그 (원본 보존)
│   ├── meta.json            # 사전 입력 (목적·예외 등)
│   └── screenshots/         # 이벤트 시점 스크린샷 (JPEG)
├── workflows/{workflow_id}/
│   ├── v1.json              # 최초 생성본
│   ├── v2.json              # 편집본 (버전 누적)
│   └── latest.json          # 최신 버전 포인터
├── runs/{run_id}/
│   ├── meta.json            # workflow_id·버전·시각·결과·소요시간
│   └── steps/               # 스텝별 before/after 스크린샷
├── schedules/
│   └── schedules.json       # 스케줄 설정 (Phase 4)
└── control/                 # Agent ↔ Dashboard IPC
    ├── command.json
    └── status.json
```

## 기능 요구사항

### 1. 녹화 (Record)
1. 사용자가 사전 입력 폼(워크플로우 목적, 사용 앱, 예외 상황, 민감 정보)을 작성한다
2. [녹화 시작] 클릭 시 Agent가 마우스·키보드·스크린샷을 실시간 캡처한다
3. 이벤트 8종을 캡처한다: click, double_click, type, key, scroll, drag, app_launch, window_change
4. 각 이벤트마다 스크린샷을 JPEG로 캡처하고 해상도·DPI 메타데이터를 저장한다
5. 타이핑은 0.5초 디바운스로 묶어 하나의 type 이벤트로 기록한다
6. 녹화 중 일시정지/재개가 가능하다 (일시정지 중 이벤트 캡처 없음)
7. 녹화 완료 후 이벤트 타임라인에서 캡처된 이벤트를 스크린샷과 함께 리뷰한다
8. 스크린샷 클릭 시 전체 화면 확대 보기가 가능하다
9. 이벤트 3개 미만이면 워크플로우 생성 불가 (재녹화 유도)

### 2. 이벤트 전처리
1. 동일 좌표 클릭이 2초 내 3회 이상 → 1회로 압축
2. 타이핑 후 즉시 전체선택(Ctrl+A)·삭제 패턴 → 해당 타이핑 제거
3. 연속 동일 방향 스크롤 → 방향·총량 합산

### 3. 워크플로우 생성
1. 녹화된 이벤트를 워크플로우 스텝으로 변환한다
2. 현재: 규칙 기반 1:1 변환 (Phase 2에서 Gemini AI 분석으로 교체 예정)
3. 워크플로우 스텝 8종: cmd, hotkey, clipboard_paste, vision_click, navigate, scroll, drag, wait
4. 생성된 워크플로우는 버전 관리된다 (v1.json, v2.json, ... + latest.json)

### 4. 워크플로우 편집
1. 워크플로우 이름·설명을 편집할 수 있다
2. 각 스텝을 펼쳐서 모든 필드를 편집할 수 있다 (description, value, type, on_failure, timeout, speed)
3. 스텝 순서를 변경할 수 있다 (위로/아래로 이동)
4. 스텝을 삭제할 수 있다
5. 저장 시 새 버전이 생성되고 이전 버전은 보존된다
6. 버전 이력을 확인할 수 있다

### 5. 재실행 (Replay)
1. 워크플로우의 [실행] 클릭 시 Agent가 스텝을 순서대로 실행한다
2. 각 스텝 실행 전후에 스크린샷을 캡처한다 (before/after)
3. 스텝별 실행 속도: fast(0.3초), normal(0.8초), slow(1.5초)
4. on_failure 정책: retry(최대 3회 재시도), human(Phase 3), skip(건너뛰기), abort(전체 중단)
5. 스텝별 timeout 적용 (기본 10초, 초과 시 TimeoutError)
6. wait 스텝은 abort 신호를 0.5초 단위로 체크한다
7. 실행 중 [중단] 버튼으로 즉시 중단할 수 있다
8. 실행 상태를 실시간으로 모니터링한다 (진행률, 현재 스텝, 상태)

### 5.1 Computer Use 모드 (Phase 3.5)
1. [Computer Use] 버튼 클릭 시 Gemini Computer Use 모델이 워크플로우 목표를 자율적으로 실행한다
2. 모델이 스크린샷을 분석하고 click_at, type_text_at, scroll 등 UI 액션을 직접 제안한다
3. 좌표는 정규화(0-999) → 실제 픽셀로 변환하여 pyautogui로 실행한다
4. 턴마다 스크린샷을 캡처하고 모델의 reasoning 텍스트를 저장한다
5. 실행 모니터에서 2패널 레이아웃으로 턴별 로그(좌)와 스크린샷(우)을 실시간 표시한다
6. 하단에 세션 타이머와 Stop 버튼이 표시된다
7. safety_decision이 require_confirmation이면 HITL로 사용자 확인을 요청한다
8. 최대 30턴(설정 가능)으로 무한루프를 방지한다
9. vision_click의 좌표 탐지 시 Computer Use 모델을 Phase 0으로 먼저 시도한다 (fallback: 기존 방식)

### 6. 실행 이력
1. 전체 실행 이력을 목록으로 확인할 수 있다
2. 상태별 필터링이 가능하다 (completed, failed, running, aborted)
3. 각 실행을 클릭하면 상세 정보를 볼 수 있다

### 7. 대시보드 공통
1. 좌측 사이드바: Home, Record, Run History, Schedules, Settings
2. 상단 헤더: Agent 상태 표시 (온라인/오프라인/녹화중/실행중)
3. Agent 상태는 2초마다 폴링한다

## 페이지 구성 (7개)
| 페이지 | 경로 | 상태 |
|---|---|---|
| 홈 (워크플로우 목록) | `/` | 구현 완료 |
| 녹화 | `/record` | 구현 완료 |
| 워크플로우 편집 | `/workflows/:id` | 구현 완료 |
| 실행 모니터링 | `/runs/:id` | 구현 완료 |
| 실행 이력 | `/runs` | 구현 완료 |
| 스케줄 관리 | `/schedules` | Phase 4 예정 |
| 설정 | `/settings` | Phase 4 예정 |

## API 엔드포인트
| Method | Path | 설명 |
|---|---|---|
| GET | `/api/v1/workflows` | 워크플로우 목록 |
| GET | `/api/v1/workflows/{id}` | 워크플로우 상세 |
| PUT | `/api/v1/workflows/{id}` | 워크플로우 수정 (새 버전 생성) |
| DELETE | `/api/v1/workflows/{id}` | 워크플로우 삭제 |
| GET | `/api/v1/workflows/{id}/versions` | 버전 이력 |
| POST | `/api/v1/workflows/generate` | 세션에서 워크플로우 생성 |
| POST | `/api/v1/sessions` | 녹화 세션 생성 |
| GET | `/api/v1/sessions/{id}/events` | 세션 이벤트 조회 |
| GET | `/api/v1/sessions/{id}/screenshots/{file}` | 스크린샷 파일 |
| GET | `/api/v1/runs` | 실행 이력 목록 |
| GET | `/api/v1/runs/{id}` | 실행 상세 |
| POST | `/api/v1/runs` | 실행 시작 (mode: normal/dryrun/test_step/computer_use) |
| POST | `/api/v1/runs/{id}/abort` | 실행 중단 |
| GET | `/api/v1/runs/{id}/turns/{filename}` | Computer Use 턴 스크린샷 |
| GET | `/api/v1/runs/{id}/steps/{filename}` | 스텝 스크린샷 (before/after) |
| GET | `/api/v1/agent/status` | Agent 상태 |
| POST | `/api/v1/agent/command` | Agent 명령 전송 |

## Agent IPC 명령
| 명령 | 설명 |
|---|---|
| `start_recording` | 녹화 시작 (세션 ID + 메타데이터) |
| `pause_recording` | 녹화 일시정지 |
| `resume_recording` | 녹화 재개 |
| `stop_recording` | 녹화 중지 |
| `start_run` | 워크플로우 실행 시작 (run_id + workflow_id) |
| `abort_run` | 실행 중단 |
| `ping` | 연결 확인 |

## 범위 제한 (현재 PoC)
- 인증/로그인 없음 (1인 도구)
- Gemini AI 미연동 (Phase 2 예정 — 규칙 기반 변환만)
- vision_click Human-in-the-Loop 미구현 (Phase 3 예정)
- 스마트 대기·Gemini 자율 분기 미구현 (Phase 3 예정)
- 결과 검증·실패 자가 진단 미구현 (Phase 3 예정)
- 드라이런 모드 미구현 (Phase 3 예정)
- 스케줄링 미구현 (Phase 4 예정)
- GCS 스토리지 미구현 (Phase 4 예정)
- WebSocket 미구현 (Phase 4 예정 — 파일 IPC 사용)
- PyInstaller .exe 패키징 미구현 (Phase 4 예정)

## 로컬 실행 방법
```bash
# Backend (터미널 1)
cd visionflow
~/.local/bin/uv.exe run uvicorn backend.main:app --reload --port 8000

# Frontend (터미널 2)
cd visionflow/frontend
npm run dev  # http://localhost:5173

# Agent (터미널 3, Windows)
cd visionflow
~/.local/bin/uv.exe run visionflow-agent
```

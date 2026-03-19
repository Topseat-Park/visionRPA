"""Phase 2: AI-powered workflow generation using Structured Output.

Replaces the rule-based _events_to_steps() with Gemini analysis.
Gemini sees recorded events + screenshots and generates optimized steps.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from google.genai import types

from .client import MODEL, get_gemini_client
from .schemas import WORKFLOW_STEPS_SCHEMA, WORKFLOW_SUMMARY_SCHEMA

logger = logging.getLogger(__name__)

# ── System prompt ────────────────────────────────────────────────

WORKFLOW_GEN_PROMPT = """\
당신은 Windows 자동화 전문가입니다.
사용자가 녹화한 마우스·키보드 이벤트와 스크린샷을 분석하여,
동일한 작업을 자동으로 재현할 수 있는 워크플로우 스텝을 생성하세요.

## 실행 방식 우선순위 (반드시 준수)

1. **focus_window** — 이미 열려있는 앱 창을 활성화 (value에 창 제목 키워드)
2. **cmd** — 셸 명령으로 가능한 작업은 반드시 cmd 사용 (앱 실행, 파일 조작)
3. **hotkey** — 단축키로 가능한 작업 (Ctrl+S, Alt+F4 등)
4. **clipboard_paste** — 텍스트 입력 10자 이상은 클립보드 붙여넣기
5. **navigate** — URL 이동
6. **file_open** — 파일 열기 (기본 앱으로 실행). value에 파일 경로
7. **file_write** — 파일 쓰기/생성. value에 "파일경로|||내용" 형식
8. **scroll / drag / wait** — 해당 동작
9. **vision_click** — 위 모두 불가능한 동적 UI만 (최후 수단)

## 규칙

- 불필요한 클릭(빈 곳 클릭, 실수 클릭)은 제거
- 타이핑 후 즉시 삭제한 패턴은 제거
- 연속 스크롤은 합산
- 각 스텝에 한국어 설명 작성
- on_failure는 vision_click이면 "human", cmd/hotkey이면 "retry", focus_window이면 "retry", 기타 "retry"
- timeout_sec은 기본 10, 느린 앱/로딩은 30

## 앱 컨텍스트 규칙 (반드시 준수)

- 브라우저(Chrome, Edge 등)가 이미 열려있으면 **navigate 또는 새 cmd 대신 focus_window** 사용
- OTP/SSO 로그인이 필요한 시스템은 **이미 열린 세션 재활용** (로그인 스텝 생성 금지)
- Excel/Word/PowerPoint 작업:
  - 파일 열기 → file_open (기본 앱으로 열림)
  - 편집 → vision_click + clipboard_paste + hotkey 조합
  - 저장 → hotkey (Ctrl+S)
- Outlook 메일 작업:
  - Outlook이 이미 열려있으면 → focus_window
  - 읽기/요약 등 데이터 추출 → 스크린샷 기반 AI가 내용을 읽음 (Phase 3)
- 앱 전환이 감지되면 반드시 focus_window 스텝을 삽입하여 실행 순서 보장
- 녹화된 이벤트에 active_window 또는 window_change 정보가 있으면, 앱 전환 시점에 focus_window 스텝 생성

## 사전 정보
- 워크플로우 목적: {purpose}
- 사용 앱/시스템: {apps}
- 예외 상황: {exceptions}
"""


async def generate_workflow_steps(
    events: list[dict],
    screenshots_dir: Path,
    purpose: str,
    apps: list[str],
    exceptions: list[str] | None = None,
) -> list[dict]:
    """Generate optimized workflow steps from recorded events via Gemini.

    Returns a list of step dicts matching WorkflowStep schema.
    """
    client = get_gemini_client()

    # Build prompt
    system = WORKFLOW_GEN_PROMPT.format(
        purpose=purpose,
        apps=", ".join(apps) if apps else "미지정",
        exceptions=", ".join(exceptions) if exceptions else "없음",
    )

    # Build content parts: events text + interleaved screenshots
    parts: list[types.Part] = [types.Part.from_text(text=system)]

    # Events as text block
    events_text = _format_events(events)
    parts.append(types.Part.from_text(text=f"## 녹화된 이벤트\n\n{events_text}"))

    # Attach key screenshots (every Nth to stay within token budget)
    MAX_IMAGES = 20
    step = max(1, len(events) // MAX_IMAGES)
    for i, ev in enumerate(events):
        if i % step != 0:
            continue
        ss_path = _resolve_screenshot(ev, screenshots_dir)
        if ss_path and ss_path.exists():
            data = ss_path.read_bytes()
            parts.append(types.Part.from_bytes(data=data, mime_type="image/jpeg"))

    # Call Gemini with structured output
    response = await client.aio.models.generate_content(
        model=MODEL,
        contents=[types.Content(parts=parts, role="user")],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=WORKFLOW_STEPS_SCHEMA,
            temperature=0.1,
        ),
    )

    import json
    steps = json.loads(response.text)

    # Assign sequential IDs
    for idx, step_dict in enumerate(steps, start=1):
        step_dict["id"] = idx

    # Post-process: attach crop_ref and fallback_coords from original events
    _attach_click_refs(steps, events)

    logger.info("Gemini generated %d workflow steps", len(steps))
    return steps


async def generate_summary(
    steps: list[dict],
    purpose: str,
) -> dict:
    """Generate a WorkflowSummary report for the given steps."""
    client = get_gemini_client()

    prompt = (
        f"워크플로우 목적: {purpose}\n\n"
        f"생성된 스텝:\n{_format_steps(steps)}\n\n"
        "위 워크플로우를 분석하여 요약 리포트를 생성하세요."
    )

    response = await client.aio.models.generate_content(
        model=MODEL,
        contents=[types.Content(parts=[types.Part.from_text(text=prompt)], role="user")],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=WORKFLOW_SUMMARY_SCHEMA,
            temperature=0.3,
        ),
    )

    import json
    return json.loads(response.text)


# ── Helpers ──────────────────────────────────────────────────────

def _format_events(events: list[dict]) -> str:
    lines = []
    for ev in events:
        seq = ev.get("seq", "?")
        etype = ev.get("event_type", "?")
        ts = ev.get("timestamp", "")
        active_win = ev.get("active_window", "")
        detail = {k: v for k, v in ev.items()
                  if k not in ("seq", "event_type", "timestamp", "screenshot_path",
                               "screenshot_meta", "active_window")}
        win_tag = f" [창: {active_win}]" if active_win else ""
        lines.append(f"[{seq}] {etype}{win_tag} @ {ts}  {detail}")
    return "\n".join(lines)


def _format_steps(steps: list[dict]) -> str:
    lines = []
    for s in steps:
        lines.append(f"  {s.get('id','-')}. [{s.get('type')}] {s.get('description','')}")
    return "\n".join(lines)


def _attach_click_refs(steps: list[dict], events: list[dict]) -> None:
    """Attach crop_ref and fallback_coords from recorded events to vision_click steps.

    Matches vision_click steps to click/double_click events in order.
    """
    click_events = [
        ev for ev in events
        if ev.get("event_type") in ("click", "double_click")
    ]
    click_idx = 0
    for step in steps:
        if step.get("type") != "vision_click":
            continue
        if click_idx >= len(click_events):
            break
        ev = click_events[click_idx]
        if ev.get("crop_path"):
            step.setdefault("crop_ref", ev["crop_path"])
        if "x" in ev and "y" in ev:
            step.setdefault("fallback_coords", {"x": ev["x"], "y": ev["y"]})
        click_idx += 1


def _resolve_screenshot(event: dict, screenshots_dir: Path) -> Path | None:
    ss = event.get("screenshot_path")
    if not ss:
        return None
    # screenshot_path might be absolute or just a filename
    p = Path(ss)
    if p.exists():
        return p
    # Try relative to screenshots_dir
    name = p.name
    candidate = screenshots_dir / name
    return candidate if candidate.exists() else None

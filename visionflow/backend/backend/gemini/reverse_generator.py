"""Reverse Workflow Generator — CU 액션 로그를 결정론적 워크플로우 스텝으로 변환.

Computer Use가 자율 실행한 행동 로그를 분석하여,
cmd > hotkey > clipboard_paste > vision_click 우선순위로 최적화된 스텝을 생성한다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from google.genai import types

from .client import MODEL, get_gemini_client
from .schemas import WORKFLOW_STEPS_SCHEMA

logger = logging.getLogger(__name__)

REVERSE_GEN_PROMPT = """\
당신은 Windows 자동화 전문가입니다.
AI 에이전트(Computer Use)가 자율적으로 수행한 UI 액션 로그를 분석하여,
동일한 작업을 빠르고 안정적으로 재현할 수 있는 워크플로우 스텝으로 변환하세요.

## 실행 방식 우선순위 (반드시 준수)

1. **cmd** — 셸 명령으로 가능한 작업은 반드시 cmd 사용
2. **hotkey** — 단축키로 가능한 작업
3. **clipboard_paste** — 텍스트 입력은 클립보드 붙여넣기
4. **navigate** — URL 이동
5. **file_open / file_write** — 파일 작업
6. **focus_window** — 앱 창 전환
7. **scroll / drag / wait** — 해당 동작
8. **vision_click** — 위 모두 불가능한 동적 UI만 (최후 수단)

## CU 액션 → 스텝 변환 힌트

- click_at → 가능하면 cmd/hotkey로 대체, 불가능하면 vision_click
- type_text_at → clipboard_paste (value에 입력된 텍스트)
- key_combination → hotkey (value에 키 조합)
- navigate → navigate (value에 URL)
- scroll_document/scroll_at → scroll
- drag_and_drop → drag
- wait_5_seconds → wait (value에 "5")

## 규칙

- 불필요한 클릭(탐색 중 실수)은 제거
- 연속 동일 액션은 합산/단순화
- 각 스텝에 한국어 설명 작성
- on_failure는 vision_click이면 "self_heal", cmd/hotkey이면 "retry"
- vision_click에는 target_description과 hint를 상세히 작성

## 원래 목표
{goal}

## CU 액션 로그
{actions_log}
"""


async def generate_reverse_workflow(
    actions_log: list[dict],
    goal: str,
    screenshots_dir: Path | None = None,
) -> list[dict]:
    """CU 액션 로그를 분석하여 최적화된 워크플로우 스텝을 생성한다."""
    client = get_gemini_client()

    # 액션 로그를 읽기 쉬운 텍스트로 변환
    log_text = _format_actions_log(actions_log)

    prompt = REVERSE_GEN_PROMPT.format(goal=goal, actions_log=log_text)

    parts: list[types.Part] = [types.Part.from_text(text=prompt)]

    # 턴 스크린샷 첨부 (있으면)
    if screenshots_dir and screenshots_dir.exists():
        screenshots = sorted(screenshots_dir.glob("turn_*.jpg"))
        MAX_IMAGES = 15
        step = max(1, len(screenshots) // MAX_IMAGES)
        for i, ss_path in enumerate(screenshots):
            if i % step != 0:
                continue
            data = ss_path.read_bytes()
            parts.append(types.Part.from_bytes(data=data, mime_type="image/jpeg"))

    response = await client.aio.models.generate_content(
        model=MODEL,
        contents=[types.Content(parts=parts, role="user")],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=WORKFLOW_STEPS_SCHEMA,
            temperature=0.1,
        ),
    )

    steps = json.loads(response.text)

    for idx, step_dict in enumerate(steps, start=1):
        step_dict["id"] = idx
        # 새 워크플로우이므로 proven_count 초기화
        step_dict.setdefault("proven_count", 0)
        step_dict.setdefault("proven_threshold", 3)

    logger.info("역변환 워크플로우: %d 스텝 생성 (CU %d 액션으로부터)", len(steps), len(actions_log))
    return steps


def _format_actions_log(actions: list[dict]) -> str:
    lines = []
    for a in actions:
        turn = a.get("turn", "?")
        action = a.get("action", "?")
        args = {k: v for k, v in a.get("args", {}).items()
                if k not in ("safety_decision", "safety_acknowledgement")}
        result = a.get("result", "")
        reasoning = a.get("reasoning", "")[:150]
        lines.append(
            f"[턴 {turn}] {action} args={args} result={result}"
            f"{f' reasoning={reasoning}' if reasoning else ''}"
        )
    return "\n".join(lines)

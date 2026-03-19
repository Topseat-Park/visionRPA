"""Phase 3: AI-powered replay using Function Calling (Skill pattern).

Gemini acts as an agent that sees the screen and calls tools (skills)
to interact with the UI. This replaces coordinate-based replay for
vision_click steps and enables autonomous exception handling.

Agent Loop:
    1. Capture screen → send to Gemini
    2. Gemini calls a tool: click(x,y), type_text("hello"), etc.
    3. Agent executes the tool
    4. Capture new screen → send as tool_result
    5. Gemini decides next action or calls done()
    6. Repeat (max turns per step to prevent infinite loops)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from google.genai import types

from .client import MODEL, get_gemini_client
from .tools import FORCE_TOOL_CONFIG, REPLAY_TOOLS

logger = logging.getLogger(__name__)

MAX_TURNS_PER_STEP = 5  # prevent infinite loops


@dataclass
class ToolCall:
    """Parsed tool call from Gemini response."""
    name: str
    args: dict
    raw: types.FunctionCall | None = None


@dataclass
class AgentResult:
    """Result of running the agent loop for one step."""
    success: bool
    summary: str = ""
    need_human: bool = False
    human_reason: str = ""
    turns_used: int = 0
    tool_calls: list[ToolCall] = field(default_factory=list)


STEP_SYSTEM_PROMPT = """\
당신은 Windows PC 자동화 에이전트입니다.
현재 화면 스크린샷을 보고, 주어진 작업을 수행하기 위해 적절한 도구(tool)를 호출하세요.

## 실행 우선순위 (반드시 준수)
1. run_command — 셸 명령으로 가능하면 최우선
2. hotkey — 단축키로 가능하면 사용
3. type_text — 텍스트 입력
4. click — 화면 좌표 클릭 (마지막 수단)

## 규칙
- 한 번에 하나의 도구만 호출
- 작업이 완료되면 반드시 done() 호출
- 예상치 못한 팝업/오류 화면이 보이면 먼저 처리 시도
- 로그인 화면, 보안 문자 등 자동 처리 불가하면 need_human() 호출
- 좌표를 지정할 때 화면 해상도와 DPI를 고려
"""


async def execute_step_with_ai(
    step_description: str,
    step_hint: str | None,
    initial_screenshot: bytes,
    execute_tool_fn,
    capture_screen_fn,
) -> AgentResult:
    """Run one workflow step using Gemini as the decision-maker.

    Args:
        step_description: What this step should accomplish.
        step_hint: Optional hint for finding UI elements.
        initial_screenshot: JPEG bytes of the current screen.
        execute_tool_fn: async (name, args) -> str  — executes a tool, returns result text.
        capture_screen_fn: async () -> bytes  — captures current screen as JPEG.

    Returns:
        AgentResult with success status and tool call history.
    """
    client = get_gemini_client()
    result = AgentResult(success=False)

    # Build initial message
    task_prompt = f"## 현재 작업\n{step_description}"
    if step_hint:
        task_prompt += f"\n\n## 힌트\n{step_hint}"

    contents: list[types.Content] = [
        types.Content(
            parts=[
                types.Part.from_text(text=STEP_SYSTEM_PROMPT),
                types.Part.from_text(text=task_prompt),
                types.Part.from_bytes(data=initial_screenshot, mime_type="image/jpeg"),
            ],
            role="user",
        ),
    ]

    for turn in range(MAX_TURNS_PER_STEP):
        # Ask Gemini what to do
        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                tools=REPLAY_TOOLS,
                tool_config=FORCE_TOOL_CONFIG,
            ),
        )

        # Extract function call
        fc = _extract_function_call(response)
        if fc is None:
            logger.warning("Gemini returned no function call on turn %d", turn)
            break

        tool = ToolCall(name=fc.name, args=dict(fc.args), raw=fc)
        result.tool_calls.append(tool)
        result.turns_used = turn + 1
        logger.info("AI tool call [turn %d]: %s(%s)", turn + 1, fc.name, fc.args)

        # Handle control tools
        if fc.name == "done":
            result.success = fc.args.get("success", True)
            result.summary = fc.args.get("summary", "")
            return result

        if fc.name == "need_human":
            result.need_human = True
            result.human_reason = fc.args.get("reason", "")
            return result

        # Execute the action tool
        tool_result_text = await execute_tool_fn(fc.name, fc.args)

        # Capture new screenshot after action
        new_screenshot = await capture_screen_fn()

        # Append assistant's function call + tool result to conversation
        contents.append(types.Content(
            parts=[types.Part.from_function_call(name=fc.name, args=fc.args)],
            role="model",
        ))
        contents.append(types.Content(
            parts=[
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": tool_result_text},
                ),
                types.Part.from_bytes(data=new_screenshot, mime_type="image/jpeg"),
            ],
            role="user",
        ))

    # Max turns reached without done()
    logger.warning("AI agent hit max turns (%d) without calling done()", MAX_TURNS_PER_STEP)
    result.summary = f"Max turns ({MAX_TURNS_PER_STEP}) reached"
    return result


def _extract_function_call(response) -> types.FunctionCall | None:
    """Extract the first FunctionCall from a Gemini response."""
    try:
        for part in response.candidates[0].content.parts:
            if part.function_call:
                return part.function_call
    except (IndexError, AttributeError):
        pass
    return None

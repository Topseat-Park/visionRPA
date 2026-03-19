"""Gemini Function Calling tool definitions — AI "Skills" for replay.

These tools let Gemini act as an agent during replay:
  1. See the current screen (screenshot)
  2. Decide which action (tool/skill) to execute
  3. Agent executes the action, captures new screen
  4. Send result back to Gemini → repeat

Usage:
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=REPLAY_TOOLS,
            tool_config=FORCE_TOOL_CONFIG,
        ),
    )
    fc = response.candidates[0].content.parts[0].function_call
    # fc.name = "click", fc.args = {"x": 100, "y": 200}
"""

from __future__ import annotations

from google.genai import types

# ── Tool Declarations (8 actions + 2 control) ──────────────────

_FUNCTION_DECLARATIONS = [
    types.FunctionDeclaration(
        name="click",
        description="마우스 클릭. 화면에서 대상 위치의 좌표를 지정. 가능하면 hotkey나 cmd를 먼저 고려할 것.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "x": {"type": "INTEGER", "description": "X 좌표 (픽셀)"},
                "y": {"type": "INTEGER", "description": "Y 좌표 (픽셀)"},
                "button": {"type": "STRING", "enum": ["left", "right"], "description": "마우스 버튼"},
                "double": {"type": "BOOLEAN", "description": "더블클릭 여부"},
            },
            "required": ["x", "y"],
        },
    ),
    types.FunctionDeclaration(
        name="type_text",
        description="텍스트 입력. 클립보드 붙여넣기 방식으로 실행 (오타 방지).",
        parameters={
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING", "description": "입력할 텍스트"},
            },
            "required": ["text"],
        },
    ),
    types.FunctionDeclaration(
        name="hotkey",
        description="키보드 단축키 실행. 예: ctrl+s, alt+f4, win+r, enter, tab",
        parameters={
            "type": "OBJECT",
            "properties": {
                "keys": {"type": "STRING", "description": "키 조합 (+ 구분). 예: ctrl+s"},
            },
            "required": ["keys"],
        },
    ),
    types.FunctionDeclaration(
        name="run_command",
        description="셸 명령 실행. 앱 실행, 파일 조작 등. 가장 안정적인 방식이므로 가능하면 최우선 사용.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "실행할 명령어"},
            },
            "required": ["command"],
        },
    ),
    types.FunctionDeclaration(
        name="navigate",
        description="브라우저에서 URL 열기.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "이동할 URL"},
            },
            "required": ["url"],
        },
    ),
    types.FunctionDeclaration(
        name="scroll",
        description="마우스 스크롤.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "direction": {"type": "STRING", "enum": ["up", "down"]},
                "amount": {"type": "INTEGER", "description": "스크롤 양 (클릭 수)"},
                "x": {"type": "INTEGER", "description": "스크롤 위치 X (선택)"},
                "y": {"type": "INTEGER", "description": "스크롤 위치 Y (선택)"},
            },
            "required": ["direction", "amount"],
        },
    ),
    types.FunctionDeclaration(
        name="drag",
        description="마우스 드래그 (시작→끝 좌표).",
        parameters={
            "type": "OBJECT",
            "properties": {
                "start_x": {"type": "INTEGER"},
                "start_y": {"type": "INTEGER"},
                "end_x": {"type": "INTEGER"},
                "end_y": {"type": "INTEGER"},
            },
            "required": ["start_x", "start_y", "end_x", "end_y"],
        },
    ),
    types.FunctionDeclaration(
        name="wait_and_check",
        description="지정 시간 대기 후 화면을 다시 확인. 로딩 완료 등 비동기 상태 대기에 사용.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "seconds": {"type": "NUMBER", "description": "대기 시간 (초)"},
                "reason": {"type": "STRING", "description": "대기 이유"},
            },
            "required": ["seconds"],
        },
    ),

    # ── Control tools (not actions) ──────────────────────────────

    types.FunctionDeclaration(
        name="done",
        description="현재 스텝(또는 전체 작업) 완료 보고. 더 이상 행동이 필요 없을 때 호출.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "success": {"type": "BOOLEAN", "description": "성공 여부"},
                "summary": {"type": "STRING", "description": "결과 요약"},
            },
            "required": ["success", "summary"],
        },
    ),
    types.FunctionDeclaration(
        name="need_human",
        description="사람의 개입이 필요할 때 호출. 로그인 화면, 보안문자, 예상치 못한 상황 등.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "reason": {"type": "STRING", "description": "개입이 필요한 이유"},
            },
            "required": ["reason"],
        },
    ),
]


# ── Exported tool configs ────────────────────────────────────────

REPLAY_TOOLS = [types.Tool(function_declarations=_FUNCTION_DECLARATIONS)]

# Force Gemini to always call a tool (never respond with plain text)
FORCE_TOOL_CONFIG = types.ToolConfig(
    function_calling_config=types.FunctionCallingConfig(mode="ANY")
)

# Allow Gemini to optionally call a tool or respond with text
AUTO_TOOL_CONFIG = types.ToolConfig(
    function_calling_config=types.FunctionCallingConfig(mode="AUTO")
)

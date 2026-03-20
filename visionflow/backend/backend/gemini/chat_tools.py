from google.genai import types

CHAT_FUNCTION_DECLARATIONS = [
    types.FunctionDeclaration(
        name="list_workflows",
        description="워크플로우 목록을 조회한다.",
        parameters={"type": "OBJECT", "properties": {}},
    ),
    types.FunctionDeclaration(
        name="get_workflow",
        description="특정 워크플로우의 상세 정보를 조회한다.",
        parameters={"type": "OBJECT", "properties": {"workflow_id": {"type": "STRING"}}, "required": ["workflow_id"]},
    ),
    types.FunctionDeclaration(
        name="create_workflow",
        description="새 워크플로우를 생성한다. 스텝 배열을 포함.",
        parameters={"type": "OBJECT", "properties": {
            "name": {"type": "STRING"}, "description": {"type": "STRING"},
            "steps": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                "type": {"type": "STRING", "enum": ["cmd","hotkey","clipboard_paste","vision_click","navigate","scroll","drag","wait","file_open","file_write","focus_window"]},
                "description": {"type": "STRING"}, "value": {"type": "STRING"},
                "target_description": {"type": "STRING"}, "on_failure": {"type": "STRING", "enum": ["retry","human","skip","abort","self_heal"]},
            }, "required": ["type","description","value"]}}
        }, "required": ["name","description","steps"]},
    ),
    types.FunctionDeclaration(
        name="edit_step",
        description="워크플로우의 특정 스텝을 수정한다.",
        parameters={"type": "OBJECT", "properties": {
            "workflow_id": {"type": "STRING"}, "step_id": {"type": "INTEGER"},
            "changes": {"type": "OBJECT", "properties": {
                "type": {"type": "STRING"}, "description": {"type": "STRING"}, "value": {"type": "STRING"},
                "target_description": {"type": "STRING"}, "hint": {"type": "STRING"}, "on_failure": {"type": "STRING"},
            }}
        }, "required": ["workflow_id","step_id","changes"]},
    ),
    types.FunctionDeclaration(
        name="run_workflow",
        description="워크플로우를 실행한다. mode: normal, dryrun, computer_use, hybrid 중 선택.",
        parameters={"type": "OBJECT", "properties": {
            "workflow_id": {"type": "STRING"}, "mode": {"type": "STRING", "enum": ["normal","dryrun","computer_use","hybrid"]}
        }, "required": ["workflow_id"]},
    ),
    types.FunctionDeclaration(
        name="run_computer_use",
        description="자연어 목표를 Computer Use로 즉시 실행한다. 워크플로우 없이 바로 실행.",
        parameters={"type": "OBJECT", "properties": {"goal": {"type": "STRING"}}, "required": ["goal"]},
    ),
    types.FunctionDeclaration(
        name="start_recording",
        description="새 녹화 세션을 시작한다.",
        parameters={"type": "OBJECT", "properties": {"purpose": {"type": "STRING"}, "apps": {"type": "ARRAY", "items": {"type": "STRING"}}}, "required": ["purpose"]},
    ),
    types.FunctionDeclaration(
        name="stop_recording",
        description="현재 녹화를 중지한다.",
        parameters={"type": "OBJECT", "properties": {}},
    ),
    types.FunctionDeclaration(
        name="get_run_result",
        description="실행 결과를 조회한다.",
        parameters={"type": "OBJECT", "properties": {"run_id": {"type": "STRING"}}, "required": ["run_id"]},
    ),
    types.FunctionDeclaration(
        name="analyze_failure",
        description="실패한 실행을 분석하여 원인과 수정 방법을 제안한다.",
        parameters={"type": "OBJECT", "properties": {"run_id": {"type": "STRING"}}, "required": ["run_id"]},
    ),
]

CHAT_TOOLS = [types.Tool(function_declarations=CHAT_FUNCTION_DECLARATIONS)]
CHAT_TOOL_CONFIG = types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="AUTO"))

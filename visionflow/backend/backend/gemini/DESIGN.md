# Gemini 통합 설계 — 2가지 패턴 조합

## 패턴 비교

```
┌──────────────────────────────────────────────────────────────────┐
│  Phase 2: Structured Output                                      │
│  녹화 이벤트 + 스크린샷 ──→ Gemini ──→ WorkflowStep[] (JSON)    │
│  한 번 호출로 전체 워크플로우 생성                                │
│  response_schema로 출력 형식 100% 보장                           │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  Phase 3: Function Calling (Tool Use = Skill 패턴)               │
│  현재 화면 ──→ Gemini ──→ click(x,y) / type("text") 호출        │
│  실행 결과 확인 ──→ 다음 행동 결정 (agent loop)                  │
│  AI가 직접 "스킬"을 선택하고 실행                                │
└──────────────────────────────────────────────────────────────────┘
```

## 1. Structured Output — 워크플로우 생성 (Phase 2)

**목적**: 녹화된 이벤트를 분석하여 최적화된 워크플로우 JSON을 생성

**Gemini API 설정**:
```python
response = client.models.generate_content(
    model="gemini-3.0-flash",
    contents=[system_prompt, events_text, *screenshot_parts],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=WORKFLOW_STEPS_SCHEMA,  # 출력 형식 강제
        temperature=0.1,  # 낮은 temperature로 일관성 확보
    ),
)
```

**장점**:
- 출력이 반드시 스키마와 일치 (파싱 실패 없음)
- 한 번의 API 호출로 전체 워크플로우 생성
- 실행 방식 우선순위(cmd > hotkey > clipboard > vision_click)를 프롬프트로 지시

**응답 스키마**:
```json
{
  "type": "ARRAY",
  "items": {
    "type": "OBJECT",
    "properties": {
      "type": {"type": "STRING", "enum": ["cmd","hotkey","clipboard_paste","vision_click","navigate","scroll","drag","wait"]},
      "description": {"type": "STRING"},
      "value": {"type": "STRING"},
      "on_failure": {"type": "STRING", "enum": ["retry","human","skip","abort"]},
      "timeout_sec": {"type": "INTEGER"}
    },
    "required": ["type", "description", "value"]
  }
}
```

---

## 2. Function Calling — 리플레이 중 AI 행동 (Phase 3)

**목적**: AI가 화면을 보고 직접 행동을 결정 (Skill/Tool 패턴)

**Agent Loop**:
```
1. 현재 화면 캡처 → Gemini에 전송
2. Gemini가 tool을 선택: click(x,y) / type("text") / hotkey("ctrl+s") ...
3. Agent가 해당 tool 실행
4. 결과 화면 캡처 → Gemini에 전송 (tool_result)
5. Gemini가 다음 행동 결정 또는 "done" 반환
6. 반복
```

**Tool 정의** (8개 — 워크플로우 스텝과 1:1 매핑):
```python
tools = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="click",
            description="마우스 클릭. 화면 좌표를 지정.",
            parameters={"type":"OBJECT", "properties": {
                "x": {"type":"INTEGER"}, "y": {"type":"INTEGER"},
                "button": {"type":"STRING","enum":["left","right"]},
                "double": {"type":"BOOLEAN"}
            }, "required":["x","y"]}
        ),
        types.FunctionDeclaration(
            name="type_text",
            description="텍스트 입력 (클립보드 붙여넣기 방식).",
            parameters={"type":"OBJECT","properties":{
                "text":{"type":"STRING"}
            },"required":["text"]}
        ),
        types.FunctionDeclaration(
            name="hotkey",
            description="키보드 단축키 실행.",
            parameters={"type":"OBJECT","properties":{
                "keys":{"type":"STRING","description":"예: ctrl+s, alt+f4, win+r"}
            },"required":["keys"]}
        ),
        types.FunctionDeclaration(
            name="run_command",
            description="셸 명령 실행 (앱 실행, 파일 조작).",
            parameters={"type":"OBJECT","properties":{
                "command":{"type":"STRING"}
            },"required":["command"]}
        ),
        types.FunctionDeclaration(
            name="scroll",
            description="스크롤.",
            parameters={"type":"OBJECT","properties":{
                "direction":{"type":"STRING","enum":["up","down"]},
                "amount":{"type":"INTEGER"},
                "x":{"type":"INTEGER"},"y":{"type":"INTEGER"}
            },"required":["direction","amount"]}
        ),
        types.FunctionDeclaration(
            name="wait",
            description="지정 시간 대기 후 화면 재확인.",
            parameters={"type":"OBJECT","properties":{
                "seconds":{"type":"NUMBER"}
            },"required":["seconds"]}
        ),
        types.FunctionDeclaration(
            name="done",
            description="작업 완료. 최종 결과 보고.",
            parameters={"type":"OBJECT","properties":{
                "success":{"type":"BOOLEAN"},
                "summary":{"type":"STRING"}
            },"required":["success","summary"]}
        ),
        types.FunctionDeclaration(
            name="need_human",
            description="사람의 개입이 필요할 때 호출.",
            parameters={"type":"OBJECT","properties":{
                "reason":{"type":"STRING"}
            },"required":["reason"]}
        ),
    ])
]
```

**Gemini API 호출**:
```python
response = client.models.generate_content(
    model="gemini-3.0-flash",
    contents=[system_prompt, current_screenshot],
    config=types.GenerateContentConfig(
        tools=tools,
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="ANY"  # 반드시 tool을 호출하게 강제
            )
        ),
    ),
)
# response.candidates[0].content.parts[0].function_call
```

---

## 3. 조합 사용 — 실패 진단 리포트

**Structured Output으로 진단 결과를 구조화**:
```python
DIAGNOSIS_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "cause": types.Schema(type="STRING", description="실패 원인 한 문장"),
        "failed_step_fix": types.Schema(type="OBJECT", properties={
            "target_description": types.Schema(type="STRING"),
            "hint": types.Schema(type="STRING"),
            "suggested_type": types.Schema(type="STRING"),
        }),
        "confidence": types.Schema(type="NUMBER", description="0.0~1.0"),
    },
    required=["cause", "failed_step_fix", "confidence"],
)
```

---

## 요약: 언제 뭘 쓸까

| 용도 | 패턴 | 이유 |
|------|-------|------|
| 녹화→워크플로우 생성 | **Structured Output** | 한번에 전체 JSON 생성, 스키마 보장 |
| 워크플로우 요약 리포트 | **Structured Output** | 정형화된 리포트 |
| vision_click 좌표 탐색 | **Function Calling** | 화면 보고 click(x,y) 호출 |
| 스마트 대기 (wait_condition) | **Function Calling** | 화면 반복 확인 후 done/wait 판단 |
| 팝업/예외 자동 처리 | **Function Calling** | 상황에 따라 다른 tool 선택 |
| 실패 진단 리포트 | **Structured Output** | 정형화된 진단 |
| 결과 검증 (success/failure) | **Structured Output** | boolean + 근거 |

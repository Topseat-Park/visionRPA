"""Gemini response schemas — Structured Output definitions.

These schemas force Gemini to return JSON matching our Pydantic models exactly.
Used with `response_mime_type="application/json"` + `response_schema=...`.
"""

from __future__ import annotations

from google.genai import types

# ── Workflow Step (for workflow generation) ─────────────────────

STEP_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "type": types.Schema(
            type="STRING",
            enum=["cmd", "hotkey", "clipboard_paste", "vision_click",
                  "navigate", "scroll", "drag", "wait",
                  "file_open", "file_write", "focus_window"],
            description="실행 방식. cmd를 최우선으로 선택. 파일 열기는 file_open, 파일 쓰기는 file_write. 이미 열린 앱 창 활성화는 focus_window.",
        ),
        "description": types.Schema(
            type="STRING",
            description="사람이 읽을 수 있는 스텝 설명 (한국어)",
        ),
        "value": types.Schema(
            type="STRING",
            description="실행값: cmd명령, 단축키(ctrl+s), 텍스트, URL 등",
        ),
        "target_description": types.Schema(
            type="STRING",
            description="클릭 대상 UI 요소 설명 (vision_click 전용)",
        ),
        "hint": types.Schema(
            type="STRING",
            description="요소 탐지 보조 힌트 (vision_click 전용)",
        ),
        "wait_condition": types.Schema(
            type="STRING",
            description="다음 스텝 진행 조건 (예: '파일 저장 완료 대화상자 표시')",
        ),
        "on_failure": types.Schema(
            type="STRING",
            enum=["retry", "human", "skip", "abort"],
            description="실패 시 정책",
        ),
        "timeout_sec": types.Schema(
            type="INTEGER",
            description="타임아웃 (초)",
        ),
    },
    required=["type", "description", "value"],
)

WORKFLOW_STEPS_SCHEMA = types.Schema(
    type="ARRAY",
    items=STEP_SCHEMA,
    description="최적화된 워크플로우 스텝 배열",
)


# ── Workflow Summary Report ─────────────────────────────────────

WORKFLOW_SUMMARY_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "flow_summary": types.Schema(
            type="STRING", description="전체 흐름 한 줄 요약",
        ),
        "attention_steps": types.Schema(
            type="ARRAY",
            items=types.Schema(type="STRING"),
            description="주의 필요 스텝 목록 (vision_click, 복잡 조건)",
        ),
        "improvement_suggestions": types.Schema(
            type="ARRAY",
            items=types.Schema(type="STRING"),
            description="개선 제안 (cmd 대체 등)",
        ),
        "recommended_first_run": types.Schema(
            type="STRING",
            enum=["dryrun", "manual", "auto"],
            description="권장 첫 실행 방식",
        ),
        "estimated_duration_sec": types.Schema(
            type="INTEGER",
            description="예상 소요 시간 (초)",
        ),
    },
    required=["flow_summary", "attention_steps", "improvement_suggestions",
              "recommended_first_run"],
)


# ── Failure Diagnosis ───────────────────────────────────────────

DIAGNOSIS_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "cause": types.Schema(
            type="STRING", description="실패 원인 한 문장 (자연어)",
        ),
        "failed_step_fix": types.Schema(
            type="OBJECT",
            properties={
                "target_description": types.Schema(type="STRING"),
                "hint": types.Schema(type="STRING"),
                "suggested_type": types.Schema(
                    type="STRING",
                    enum=["cmd", "hotkey", "clipboard_paste", "vision_click",
                          "navigate", "scroll", "drag", "wait",
                          "file_open", "file_write", "focus_window"],
                ),
                "suggested_value": types.Schema(type="STRING"),
            },
            description="실패 스텝 수정 제안",
        ),
        "confidence": types.Schema(
            type="NUMBER", description="진단 신뢰도 0.0~1.0",
        ),
    },
    required=["cause", "failed_step_fix", "confidence"],
)


# ── Result Verification ─────────────────────────────────────────

VERIFICATION_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "success": types.Schema(
            type="BOOLEAN", description="워크플로우 목적 달성 여부",
        ),
        "evidence": types.Schema(
            type="STRING", description="판단 근거 설명",
        ),
    },
    required=["success", "evidence"],
)

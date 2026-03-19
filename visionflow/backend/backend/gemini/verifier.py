"""Phase 3: Result verification and failure diagnosis using Gemini.

verify_run()     — Final screenshot + workflow purpose → success/failure
diagnose_failure() — Failed step info + before/after screenshots → cause + fix
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

from google.genai import types

from .client import MODEL, get_gemini_client
from .schemas import DIAGNOSIS_SCHEMA, VERIFICATION_SCHEMA

logger = logging.getLogger(__name__)


async def verify_run(
    screenshot_bytes: bytes,
    workflow_name: str,
    workflow_description: str,
) -> dict | None:
    """Verify whether the workflow achieved its goal.

    Returns {"success": bool, "evidence": str} or None if Gemini unavailable.
    """
    try:
        client = get_gemini_client()
    except Exception:
        logger.warning("Gemini client unavailable — skipping verification")
        return None

    prompt = (
        f"워크플로우 이름: {workflow_name}\n"
        f"워크플로우 목적: {workflow_description}\n\n"
        "아래 스크린샷은 워크플로우 실행 완료 후 최종 화면입니다.\n"
        "워크플로우의 목적이 달성되었는지 판단하세요.\n"
        "화면에 에러 메시지, 예상치 못한 상태, 또는 목적과 다른 결과가 보이면 실패로 판단하세요."
    )

    parts = [
        types.Part.from_text(text=prompt),
        types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg"),
    ]

    try:
        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=[types.Content(parts=parts, role="user")],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VERIFICATION_SCHEMA,
                temperature=0.1,
            ),
        )
        return json.loads(response.text)
    except Exception:
        logger.exception("Verification call failed")
        return None


async def diagnose_failure(
    failed_step: dict,
    before_screenshot: bytes | None,
    after_screenshot: bytes | None,
    error_message: str,
    workflow_name: str,
) -> dict | None:
    """Diagnose why a step failed and suggest a fix.

    Returns {"cause": str, "failed_step_fix": {...}, "confidence": float}
    or None if Gemini unavailable.
    """
    try:
        client = get_gemini_client()
    except Exception:
        logger.warning("Gemini client unavailable — skipping diagnosis")
        return None

    prompt = (
        f"워크플로우: {workflow_name}\n"
        f"실패 에러: {error_message}\n\n"
        f"실패한 스텝 정보:\n"
        f"  - 타입: {failed_step.get('type', '?')}\n"
        f"  - 설명: {failed_step.get('description', '?')}\n"
        f"  - 값: {failed_step.get('value', '')}\n"
        f"  - 클릭 대상: {failed_step.get('target_description', '')}\n"
        f"  - 힌트: {failed_step.get('hint', '')}\n\n"
        "아래 스크린샷을 보고 실패 원인을 진단하고, 스텝 수정 제안을 하세요.\n"
        "수정 제안은 구체적이어야 합니다 (target_description, hint, suggested_type, suggested_value)."
    )

    parts: list[types.Part] = [types.Part.from_text(text=prompt)]

    if before_screenshot:
        parts.append(types.Part.from_text(text="[실행 전 스크린샷]"))
        parts.append(types.Part.from_bytes(data=before_screenshot, mime_type="image/jpeg"))

    if after_screenshot:
        parts.append(types.Part.from_text(text="[실행 후 / 실패 시점 스크린샷]"))
        parts.append(types.Part.from_bytes(data=after_screenshot, mime_type="image/jpeg"))

    try:
        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=[types.Content(parts=parts, role="user")],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DIAGNOSIS_SCHEMA,
                temperature=0.2,
            ),
        )
        return json.loads(response.text)
    except Exception:
        logger.exception("Diagnosis call failed")
        return None

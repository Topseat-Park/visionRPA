"""Phase 3: Screen anomaly analysis using Gemini.

Detects popups, login expiry, loading spinners, and errors during replay.
"""

from __future__ import annotations

import json
import logging

from google.genai import types

from .client import MODEL, get_gemini_client
from .schemas import SCREEN_ANALYSIS_SCHEMA

logger = logging.getLogger(__name__)


async def analyze_screen(
    screenshot_bytes: bytes,
    step_description: str,
) -> dict | None:
    """Analyze current screen for anomalies before executing a step.

    Returns {"screen_state": str, "description": str, "suggested_action": str,
             "dismiss_keys": str|None} or None if Gemini unavailable.
    """
    try:
        client = get_gemini_client()
    except Exception:
        logger.warning("Gemini client unavailable — skipping screen analysis")
        return None

    prompt = (
        "현재 화면을 분석하여 예외 상황을 감지하세요.\n\n"
        f"다음 실행할 스텝: {step_description}\n\n"
        "감지 대상:\n"
        "- **popup**: 예상치 못한 팝업/확인창/알림이 떠 있음 → dismiss_popup + dismiss_keys 지정\n"
        "- **login_expired**: 로그인 만료/세션 만료 화면 → request_human\n"
        "- **loading**: 로딩 스피너/프로그레스바가 보임 → wait\n"
        "- **error**: 에러 메시지/크래시 화면 → request_human\n"
        "- **normal**: 위 해당 없음 → proceed\n\n"
        "팝업이면 닫기에 사용할 키(enter, escape 등)를 dismiss_keys에 지정하세요."
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
                response_schema=SCREEN_ANALYSIS_SCHEMA,
                temperature=0.1,
            ),
        )
        return json.loads(response.text)
    except Exception:
        logger.exception("Screen analysis call failed")
        return None

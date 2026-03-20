"""AI vision element finder — locates UI elements on screen using Gemini.

Single-shot approach: send screenshot + target description → get coordinates.
Used during replay for vision_click steps.

google-genai is lazily imported so the module loads even without the SDK installed.
"""

from __future__ import annotations

import json
import logging

from ..config import get_config

logger = logging.getLogger(__name__)

MODEL = "gemini-3.0-flash"

FIND_ELEMENT_PROMPT = """\
주어진 스크린샷에서 아래 UI 요소의 정확한 클릭 좌표를 찾아주세요.

대상: {target_description}
힌트: {hint}
화면 해상도: {width}x{height}

주의사항:
- 좌표는 화면의 실제 픽셀 좌표 (왼쪽 상단이 0,0)
- 클릭 가능한 요소의 중앙 좌표를 반환
- 대상을 찾을 수 없으면 confidence를 0.3 이하로 설정
"""

VERIFY_PROMPT = """\
이전 작업을 수행한 후의 화면입니다.

수행한 작업: {step_description}
기대 결과: {expected_condition}

화면을 보고 작업이 성공적으로 완료되었는지 판단하세요.
"""

_client = None


def _get_client():
    """Lazy-init Gemini client."""
    global _client
    if _client is None:
        from google import genai

        cfg = get_config()
        if not cfg.gemini_project:
            raise RuntimeError("Gemini not configured: set VF_GEMINI_PROJECT env var")
        _client = genai.Client(
            vertexai=True,
            project=cfg.gemini_project,
            location=cfg.gemini_region,
        )
        logger.info("Gemini client created: project=%s", cfg.gemini_project)
    return _client


def _build_find_schema():
    from google.genai import types
    return types.Schema(
        type="OBJECT",
        properties={
            "x": types.Schema(type="INTEGER", description="클릭 X 좌표"),
            "y": types.Schema(type="INTEGER", description="클릭 Y 좌표"),
            "confidence": types.Schema(type="NUMBER", description="0.0~1.0 신뢰도"),
        },
        required=["x", "y", "confidence"],
    )


def _build_verify_schema():
    from google.genai import types
    return types.Schema(
        type="OBJECT",
        properties={
            "success": types.Schema(type="BOOLEAN", description="작업 완료 여부"),
            "evidence": types.Schema(type="STRING", description="판단 근거"),
        },
        required=["success", "evidence"],
    )


def find_element_on_screen(
    screenshot_bytes: bytes,
    target_description: str,
    hint: str = "",
    screen_width: int = 1920,
    screen_height: int = 1080,
) -> tuple[int, int, float]:
    """Find a UI element on screen. Returns (x, y, confidence).

    Phase 0: Try Computer Use model (most accurate)
    Phase 1: Fall back to Gemini structured output

    Raises RuntimeError if Gemini is not configured.
    Raises ImportError if google-genai is not installed.
    """
    # Phase 0: Try Computer Use model for more accurate detection
    try:
        from .computer_use import find_element_with_computer_use
        result = find_element_with_computer_use(
            screenshot_bytes, target_description, screen_width, screen_height,
        )
        if result is not None:
            x, y, confidence = result
            logger.info(
                "Computer Use found element at (%d, %d) confidence=%.2f for '%s'",
                x, y, confidence, target_description,
            )
            return x, y, confidence
    except Exception:
        logger.debug("Computer Use phase 0 unavailable, falling back to structured output")

    # Phase 1: Gemini structured output (original method)
    from google.genai import types

    client = _get_client()

    prompt = FIND_ELEMENT_PROMPT.format(
        target_description=target_description,
        hint=hint or "없음",
        width=screen_width,
        height=screen_height,
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=[types.Content(
            parts=[
                types.Part.from_text(text=prompt),
                types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg"),
            ],
            role="user",
        )],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_build_find_schema(),
            temperature=0.1,
        ),
    )

    result = json.loads(response.text)
    x, y = result["x"], result["y"]
    confidence = result.get("confidence", 0.5)
    logger.info("Element found at (%d, %d) confidence=%.2f for '%s'", x, y, confidence, target_description)
    return x, y, confidence


def verify_step_completion(
    screenshot_bytes: bytes,
    expected_condition: str,
    step_description: str,
) -> bool:
    """Verify that a step completed successfully by checking the screen.

    Returns True if verification passes, False otherwise.
    """
    if not expected_condition:
        return True

    from google.genai import types

    client = _get_client()

    prompt = VERIFY_PROMPT.format(
        step_description=step_description,
        expected_condition=expected_condition,
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=[types.Content(
            parts=[
                types.Part.from_text(text=prompt),
                types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg"),
            ],
            role="user",
        )],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_build_verify_schema(),
            temperature=0.1,
        ),
    )

    result = json.loads(response.text)
    success = result.get("success", True)
    evidence = result.get("evidence", "")
    logger.info("Step verification: success=%s evidence='%s'", success, evidence)
    return success

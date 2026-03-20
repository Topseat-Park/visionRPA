"""Computer Use 에이전트 — Gemini Computer Use API를 통한 자율 UI 자동화.

공식 Gemini Computer Use API 사양에 따라 구현:
- types.Tool(computer_use=...) 도구 설정
- FunctionResponse에 스크린샷 blob 포함
- 정규화 좌표(0-999) → 실제 픽셀 변환
- safety_decision 처리 및 HITL 확인
- 병렬 function_call 지원
"""

from __future__ import annotations

import base64
import json
import logging
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pyautogui
import pyperclip

from ..config import get_config
from ..recorder.screenshot import capture_screen

logger = logging.getLogger(__name__)

# 데스크톱 환경에서 제외할 브라우저 전용 함수
DESKTOP_EXCLUDED_FUNCTIONS = [
    "open_web_browser",
    "search",
    "go_forward",
]


@dataclass
class ComputerUseResult:
    """Computer Use 에이전트 실행 결과."""

    success: bool
    turns_used: int
    actions_executed: list[dict] = field(default_factory=list)
    final_message: str = ""
    error: str | None = None


def _build_computer_use_tool():
    """공식 API 사양에 따라 Computer Use 도구 설정을 생성한다."""
    from google.genai import types

    return types.Tool(
        computer_use=types.ComputerUse(
            environment=types.Environment.ENVIRONMENT_BROWSER,
            excluded_predefined_functions=DESKTOP_EXCLUDED_FUNCTIONS,
        )
    )


def _build_function_response(
    name: str,
    response_data: dict,
    screenshot_bytes: bytes | None = None,
) -> dict:
    """공식 API 사양에 따라 FunctionResponse를 생성한다.

    스크린샷 blob을 inline_data로 포함시킨다.
    """
    from google.genai import types

    parts = []
    if screenshot_bytes is not None:
        parts.append(
            types.Part(
                inline_data=types.Blob(
                    mime_type="image/jpeg",
                    data=screenshot_bytes,
                )
            )
        )

    return types.FunctionResponse(
        name=name,
        response=response_data,
    ), parts


def _norm_to_pixel(norm: float, screen_size: int) -> int:
    """정규화 좌표(0-999)를 실제 픽셀로 변환."""
    return int(norm / 1000 * screen_size)


class ComputerUseAgent:
    """Gemini Computer Use API를 사용하는 자율 데스크톱 자동화 에이전트.

    에이전트 루프:
    1. 스크린샷 캡처 + 목표 텍스트를 전송
    2. 모델 응답에서 function_call 추출
    3. safety_decision 확인
    4. pyautogui로 액션 실행
    5. 새 스크린샷 캡처
    6. FunctionResponse(스크린샷 blob 포함)를 빌드
    7. 모델 응답 + FunctionResponse를 contents에 추가
    8. function_call이 없거나 최대 턴까지 반복
    """

    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        paths,
        run_id: str,
        abort_event: threading.Event,
    ) -> None:
        self._screen_width = screen_width
        self._screen_height = screen_height
        self._paths = paths
        self._run_id = run_id
        self._abort_event = abort_event
        self._client = None
        self._config = get_config()

    def _get_client(self):
        """Gemini 클라이언트를 지연 초기화한다."""
        if self._client is None:
            from google import genai

            cfg = self._config
            if not cfg.gemini_project:
                raise RuntimeError(
                    "Gemini 미설정: VF_GEMINI_PROJECT 환경변수를 설정하세요"
                )
            self._client = genai.Client(
                vertexai=True,
                project=cfg.gemini_project,
                location=cfg.gemini_region,
            )
        return self._client

    def run(self, goal: str, max_turns: int | None = None) -> ComputerUseResult:
        """Computer Use 에이전트 루프를 실행하여 주어진 목표를 달성한다."""
        if max_turns is None:
            max_turns = self._config.computer_use_max_turns

        from google.genai import types

        client = self._get_client()
        model = self._config.computer_use_model
        actions_log: list[dict] = []
        reasoning_log: list[str] = []

        # 초기 스크린샷
        img_data, s_meta = capture_screen()
        sw = s_meta.capture_width
        sh = s_meta.capture_height

        # Computer Use 도구 설정
        computer_use_tool = _build_computer_use_tool()

        # 생성 설정
        generate_config = types.GenerateContentConfig(
            tools=[computer_use_tool],
            thinking_config=types.ThinkingConfig(include_thoughts=True),
            temperature=0.1,
        )

        # 초기 메시지: 목표 텍스트 + 스크린샷
        system_prompt = (
            f"당신은 데스크톱 자동화 에이전트입니다. 사용자의 목표를 달성하기 위해 "
            f"화면을 보고 적절한 UI 액션을 수행하세요.\n"
            f"화면 해상도: {sw}x{sh}\n"
            f"목표: {goal}\n\n"
            f"목표를 달성하면 더 이상 액션을 호출하지 말고 완료 메시지를 텍스트로 반환하세요."
        )

        contents: list[types.Content] = [
            types.Content(
                parts=[
                    types.Part.from_text(text=system_prompt),
                    types.Part.from_bytes(data=img_data, mime_type="image/jpeg"),
                ],
                role="user",
            )
        ]

        for turn in range(1, max_turns + 1):
            if self._abort_event.is_set():
                return ComputerUseResult(
                    success=False,
                    turns_used=turn,
                    actions_executed=actions_log,
                    error="사용자에 의해 중단됨",
                )

            logger.info("Computer Use 턴 %d/%d", turn, max_turns)

            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=generate_config,
                )
            except Exception as e:
                logger.exception("Computer Use API 호출 실패")
                return ComputerUseResult(
                    success=False,
                    turns_used=turn,
                    actions_executed=actions_log,
                    error=f"API 오류: {e}",
                )

            # 응답 파싱
            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content or not candidate.content.parts:
                return ComputerUseResult(
                    success=True,
                    turns_used=turn,
                    actions_executed=actions_log,
                    final_message=response.text if response.text else "응답 없음",
                )

            # 모델의 추론 텍스트 추출
            reasoning_text = ""
            for part in candidate.content.parts:
                if hasattr(part, "thought") and part.thought:
                    reasoning_text += f"[사고] {part.text}\n"
                elif part.text:
                    reasoning_text += part.text
            if reasoning_text:
                reasoning_log.append(reasoning_text)

            # function_call 수집
            function_calls = []
            for part in candidate.content.parts:
                if part.function_call:
                    function_calls.append(part.function_call)

            if not function_calls:
                # 텍스트만 반환 — 목표 달성으로 간주
                final_text = ""
                for part in candidate.content.parts:
                    if part.text and not (hasattr(part, "thought") and part.thought):
                        final_text += part.text
                logger.info("Computer Use 완료: %s", final_text[:200])
                self._save_reasoning_log(reasoning_log)
                return ComputerUseResult(
                    success=True,
                    turns_used=turn,
                    actions_executed=actions_log,
                    final_message=final_text,
                )

            # 모델 응답을 contents에 추가
            contents.append(candidate.content)

            # 병렬 function_call 처리: 모든 호출 실행 후 각각에 FunctionResponse
            response_parts: list[types.Part] = []

            for fc in function_calls:
                action_name = fc.name
                action_args = dict(fc.args) if fc.args else {}

                logger.info("액션: %s args=%s", action_name, action_args)

                # safety_decision 확인 (args 내부에 포함됨)
                safety = action_args.pop("safety_decision", None)
                if safety:
                    decision = safety.get("decision", "")
                    explanation = safety.get("explanation", "")

                    if decision == "BLOCK":
                        logger.warning(
                            "안전 차단: %s — %s", action_name, explanation
                        )
                        fr, extra_parts = _build_function_response(
                            action_name,
                            {"error": f"안전 차단: {explanation}"},
                        )
                        response_parts.append(types.Part.from_function_response(
                            name=action_name,
                            response={"error": f"안전 차단: {explanation}"},
                        ))
                        actions_log.append({
                            "turn": turn,
                            "action": action_name,
                            "args": action_args,
                            "result": f"blocked: {explanation}",
                            "reasoning": reasoning_text,
                        })
                        continue

                    if decision == "USER_CONFIRM":
                        logger.warning(
                            "안전 확인 요청: %s — %s", action_name, explanation
                        )
                        confirmed = self._request_hitl_confirmation(explanation)
                        if not confirmed:
                            response_parts.append(types.Part.from_function_response(
                                name=action_name,
                                response={"error": "사용자가 거부함"},
                            ))
                            actions_log.append({
                                "turn": turn,
                                "action": action_name,
                                "args": action_args,
                                "result": "denied_by_user",
                                "reasoning": reasoning_text,
                            })
                            continue
                        # 확인됨 — safety_acknowledgement 포함하여 실행
                        action_args["safety_acknowledgement"] = "true"

                # 액션 실행
                try:
                    self._execute_action(action_name, action_args, sw, sh)
                    action_result = "success"
                    result_data = {"status": "ok"}
                except Exception as e:
                    logger.warning("액션 %s 실패: %s", action_name, e)
                    action_result = f"error: {e}"
                    result_data = {"error": str(e)}

                actions_log.append({
                    "turn": turn,
                    "action": action_name,
                    "args": action_args,
                    "result": action_result,
                    "reasoning": reasoning_text,
                })

                # 액션 후 대기 및 스크린샷 캡처
                time.sleep(0.3)
                try:
                    new_img, _ = capture_screen()
                except Exception:
                    logger.warning("스크린샷 캡처 실패, 빈 응답 전송")
                    new_img = None

                # FunctionResponse 빌드 (스크린샷 blob 포함)
                if new_img is not None:
                    response_parts.append(
                        types.Part.from_function_response(
                            name=action_name,
                            response=result_data,
                        )
                    )
                    response_parts.append(
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="image/jpeg",
                                data=new_img,
                            )
                        )
                    )
                else:
                    response_parts.append(
                        types.Part.from_function_response(
                            name=action_name,
                            response=result_data,
                        )
                    )

                # 턴 스크린샷 저장
                self._save_turn_screenshot(turn, action_name)

            # FunctionResponse를 user 메시지로 추가
            if response_parts:
                contents.append(
                    types.Content(parts=response_parts, role="user")
                )

        # 최대 턴 도달
        self._save_reasoning_log(reasoning_log)
        return ComputerUseResult(
            success=False,
            turns_used=max_turns,
            actions_executed=actions_log,
            error=f"최대 턴({max_turns})에 도달하여 목표 미완료",
        )

    # ─── 액션 실행 ─────────────────────────────────────────────

    def _execute_action(
        self, action_name: str, args: dict, screen_w: int, screen_h: int
    ) -> None:
        """Computer Use 액션을 pyautogui로 실행한다.

        모델이 반환하는 좌표는 정규화 0-999 그리드이며 실제 픽셀로 변환한다.
        """

        def px(norm_x: float) -> int:
            return _norm_to_pixel(norm_x, screen_w)

        def py(norm_y: float) -> int:
            return _norm_to_pixel(norm_y, screen_h)

        if action_name == "click_at":
            x, y = px(args.get("x", 0)), py(args.get("y", 0))
            button = args.get("button", "left")
            click_type = args.get("click_type", "single")
            if click_type == "double":
                pyautogui.doubleClick(x, y, button=button)
            elif click_type == "right" or button == "right":
                pyautogui.rightClick(x, y)
            else:
                pyautogui.click(x, y, button=button)
            logger.info("클릭: (%d, %d) button=%s type=%s", x, y, button, click_type)

        elif action_name == "hover_at":
            x, y = px(args.get("x", 0)), py(args.get("y", 0))
            pyautogui.moveTo(x, y, duration=0.3)
            logger.info("호버: (%d, %d)", x, y)

        elif action_name == "type_text_at":
            x, y = px(args.get("x", 0)), py(args.get("y", 0))
            text = args.get("text", "")
            press_enter = args.get("press_enter", True)
            clear_before = args.get("clear_before_typing", True)

            pyautogui.click(x, y)
            time.sleep(0.1)

            if clear_before:
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.05)

            # 클립보드를 통한 안정적인 텍스트 입력
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.05)

            if press_enter:
                pyautogui.press("enter")

            logger.info("텍스트 입력: (%d, %d) text='%s'", x, y, text[:50])

        elif action_name == "key_combination":
            keys_str = args.get("keys", "")
            if isinstance(keys_str, str) and keys_str:
                key_list = [k.strip() for k in keys_str.split("+")]
                _KEY_REMAP = {
                    "cmd": "win", "command": "win", "meta": "win",
                    "control": "ctrl",
                }
                mapped = [_KEY_REMAP.get(k.lower(), k.lower()) for k in key_list]
                pyautogui.hotkey(*mapped)
                logger.info("키 조합: %s", "+".join(mapped))
            elif isinstance(keys_str, list):
                # 하위 호환: 리스트도 지원
                _KEY_REMAP = {"cmd": "win", "command": "win", "meta": "win", "control": "ctrl"}
                mapped = [_KEY_REMAP.get(k.lower(), k.lower()) for k in keys_str]
                pyautogui.hotkey(*mapped)
                logger.info("키 조합(리스트): %s", "+".join(mapped))

        elif action_name == "scroll_document":
            direction = args.get("direction", "down")
            if direction in ("up", "down"):
                clicks = 5 if direction == "up" else -5
                pyautogui.scroll(clicks)
            elif direction == "left":
                pyautogui.hscroll(-5)
            elif direction == "right":
                pyautogui.hscroll(5)
            logger.info("문서 스크롤: %s", direction)

        elif action_name == "scroll_at":
            x, y = px(args.get("x", 0)), py(args.get("y", 0))
            direction = args.get("direction", "down")
            magnitude = args.get("magnitude", 800)
            # magnitude는 0-999 그리드, 스크롤 양으로 변환
            scroll_amount = max(1, int(magnitude / 1000 * 10))
            if direction in ("up", "down"):
                clicks = scroll_amount if direction == "up" else -scroll_amount
                pyautogui.scroll(clicks, x=x, y=y)
            elif direction in ("left", "right"):
                h_clicks = scroll_amount if direction == "right" else -scroll_amount
                pyautogui.hscroll(h_clicks, x=x, y=y)
            logger.info(
                "위치 스크롤: (%d, %d) %s magnitude=%d", x, y, direction, magnitude
            )

        elif action_name == "drag_and_drop":
            sx, sy = px(args.get("x", 0)), py(args.get("y", 0))
            ex, ey = px(args.get("destination_x", 0)), py(args.get("destination_y", 0))
            pyautogui.moveTo(sx, sy, duration=0.2)
            pyautogui.mouseDown(button="left")
            time.sleep(0.1)
            pyautogui.moveTo(ex, ey, duration=0.5)
            pyautogui.mouseUp(button="left")
            logger.info("드래그: (%d, %d) → (%d, %d)", sx, sy, ex, ey)

        elif action_name == "navigate":
            url = args.get("url", "")
            if url:
                webbrowser.open(url)
                time.sleep(1)
                logger.info("URL 이동: %s", url)

        elif action_name == "go_back":
            pyautogui.hotkey("alt", "left")
            logger.info("뒤로가기 (Alt+Left)")

        elif action_name == "go_forward":
            pyautogui.hotkey("alt", "right")
            logger.info("앞으로가기 (Alt+Right)")

        elif action_name == "open_web_browser":
            webbrowser.open("about:blank")
            logger.info("브라우저 열기")

        elif action_name == "search":
            query = args.get("query", "")
            if query:
                webbrowser.open(f"https://www.google.com/search?q={query}")
                logger.info("검색: %s", query)

        elif action_name == "wait_5_seconds":
            time.sleep(5)
            logger.info("5초 대기")

        else:
            raise ValueError(f"알 수 없는 액션: {action_name}")

    # ─── HITL 안전 확인 ────────────────────────────────────────

    def _request_hitl_confirmation(self, explanation: str) -> bool:
        """HITL 안전 확인을 요청하고 응답을 대기한다.

        run 디렉토리에 hitl_request.json을 생성하고
        hitl_response.json이 나타날 때까지 폴링한다. (최대 5분)
        """
        run_dir = self._paths.run_dir(self._run_id)
        hitl_path = run_dir / "hitl_request.json"
        response_path = run_dir / "hitl_response.json"

        request_data = {
            "type": "safety_confirmation",
            "explanation": explanation,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            run_dir.mkdir(parents=True, exist_ok=True)
            with hitl_path.open("w", encoding="utf-8") as f:
                json.dump(request_data, f, ensure_ascii=False, indent=2)

            elapsed = 0.0
            while elapsed < 300:
                if self._abort_event.is_set():
                    hitl_path.unlink(missing_ok=True)
                    return False
                if response_path.exists():
                    with response_path.open("r", encoding="utf-8") as f:
                        resp = json.load(f)
                    hitl_path.unlink(missing_ok=True)
                    response_path.unlink(missing_ok=True)
                    return resp.get("action") == "approve"
                time.sleep(1)
                elapsed += 1

            hitl_path.unlink(missing_ok=True)
            logger.warning("HITL 안전 확인 시간 초과, 거부 처리")
            return False
        except Exception:
            logger.warning("HITL 안전 확인 실패, 허용 처리")
            return True

    # ─── 유틸리티 ──────────────────────────────────────────────

    def _save_turn_screenshot(self, turn: int, action_name: str) -> None:
        """각 턴의 스크린샷을 저장한다."""
        try:
            img_data, _ = capture_screen()
            run_dir = self._paths.run_dir(self._run_id)
            turns_dir = run_dir / "turns"
            turns_dir.mkdir(parents=True, exist_ok=True)
            path = turns_dir / f"turn_{turn:03d}_{action_name}.jpg"
            path.write_bytes(img_data)
        except Exception:
            logger.warning("턴 %d 스크린샷 저장 실패", turn)

    def _save_reasoning_log(self, reasoning_log: list[str]) -> None:
        """모델의 추론 텍스트 로그를 파일로 저장한다."""
        if not reasoning_log:
            return
        try:
            run_dir = self._paths.run_dir(self._run_id)
            run_dir.mkdir(parents=True, exist_ok=True)
            path = run_dir / "reasoning_log.txt"
            with path.open("w", encoding="utf-8") as f:
                for i, text in enumerate(reasoning_log, 1):
                    f.write(f"=== 턴 {i} ===\n{text}\n\n")
        except Exception:
            logger.warning("추론 로그 저장 실패")

    def _save_actions_log(self, actions_log: list[dict]) -> None:
        """액션 로그를 JSON 파일로 저장한다."""
        try:
            run_dir = self._paths.run_dir(self._run_id)
            run_dir.mkdir(parents=True, exist_ok=True)
            path = run_dir / "actions_log.json"
            with path.open("w", encoding="utf-8") as f:
                json.dump(actions_log, f, ensure_ascii=False, indent=2, default=str)
        except Exception:
            logger.warning("액션 로그 저장 실패")


# ─── 헬퍼: 요소 찾기 ──────────────────────────────────────────


def find_element_with_computer_use(
    screenshot_bytes: bytes,
    target_description: str,
    screen_width: int,
    screen_height: int,
) -> tuple[int, int, float] | None:
    """Computer Use 모델로 UI 요소의 클릭 좌표를 찾는다.

    공식 Computer Use Tool 설정을 사용하여 click_at 응답을 파싱한다.
    (x, y, confidence) 또는 찾지 못하면 None을 반환한다.
    """
    from google import genai
    from google.genai import types

    cfg = get_config()
    if not cfg.gemini_project:
        return None

    try:
        client = genai.Client(
            vertexai=True,
            project=cfg.gemini_project,
            location=cfg.gemini_region,
        )

        # Computer Use 도구 설정
        computer_use_tool = _build_computer_use_tool()

        prompt = (
            f"화면에서 다음 UI 요소를 찾아 클릭하세요: {target_description}\n"
            f"화면 해상도: {screen_width}x{screen_height}"
        )

        response = client.models.generate_content(
            model=cfg.computer_use_model,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(
                            data=screenshot_bytes, mime_type="image/jpeg"
                        ),
                    ],
                    role="user",
                )
            ],
            config=types.GenerateContentConfig(
                tools=[computer_use_tool],
                thinking_config=types.ThinkingConfig(include_thoughts=True),
                temperature=0.1,
            ),
        )

        # click_at function_call 파싱
        candidate = response.candidates[0] if response.candidates else None
        if not candidate or not candidate.content:
            return None

        for part in candidate.content.parts:
            if part.function_call and part.function_call.name == "click_at":
                args = dict(part.function_call.args) if part.function_call.args else {}
                norm_x = args.get("x", 0)
                norm_y = args.get("y", 0)
                x = _norm_to_pixel(norm_x, screen_width)
                y = _norm_to_pixel(norm_y, screen_height)
                logger.info(
                    "Computer Use 요소 발견: (%d, %d) — '%s'",
                    x, y, target_description,
                )
                return x, y, 0.9

        return None
    except Exception:
        logger.debug("Computer Use 요소 찾기 실패, 폴백 진행")
        return None

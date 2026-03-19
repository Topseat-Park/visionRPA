"""Replay engine — executes workflow steps using pyautogui."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

import pyautogui
import pyperclip

from shared.enums import RunStatus
from ..recorder.screenshot import capture_screen

logger = logging.getLogger(__name__)

# Speed → inter-step delay (seconds)
_SPEED_DELAY = {"fast": 0.3, "normal": 0.8, "slow": 1.5}

# Safety: disable pyautogui fail-safe pause (we own the machine)
pyautogui.PAUSE = 0.05


class ReplayEngine:
    """Runs a workflow replay in a background thread.

    State machine: IDLE → RUNNING → COMPLETED / FAILED / ABORTED
    """

    def __init__(self, paths) -> None:
        self._paths = paths
        self._run_id: str | None = None
        self._workflow_id: str | None = None
        self._current_step: int = 0
        self._total_steps: int = 0
        self._step_description: str | None = None
        self._status: RunStatus = RunStatus.PENDING
        self._thread: threading.Thread | None = None
        self._abort_event = threading.Event()
        self._mode: str = "normal"

    # ── Public properties read by Heartbeat ──────────────

    @property
    def run_id(self) -> str | None:
        return self._run_id

    @property
    def workflow_id(self) -> str | None:
        return self._workflow_id

    @property
    def current_step(self) -> int:
        return self._current_step

    @property
    def total_steps(self) -> int:
        return self._total_steps

    @property
    def step_description(self) -> str | None:
        return self._step_description

    @property
    def status(self) -> RunStatus:
        return self._status

    @property
    def is_running(self) -> bool:
        return self._status == RunStatus.RUNNING

    # ── Control ───────────────────────────────────────────

    def start(self, run_id: str, workflow_id: str, mode: str = "normal") -> None:
        """Load workflow from disk and start replay in background thread."""
        wf_path = self._paths.workflows / workflow_id / "latest.json"
        if not wf_path.exists():
            raise FileNotFoundError(f"Workflow not found: {wf_path}")

        with wf_path.open("r", encoding="utf-8") as f:
            workflow_data = json.load(f)

        self._run_id = run_id
        self._workflow_id = workflow_id
        self._current_step = 0
        self._total_steps = len(workflow_data.get("steps", []))
        self._status = RunStatus.RUNNING
        self._abort_event.clear()
        self._mode = mode

        self._thread = threading.Thread(
            target=self._execute,
            args=(workflow_data,),
            daemon=True,
            name="replayer",
        )
        self._thread.start()
        logger.info("Replay started: run=%s workflow=%s steps=%d mode=%s", run_id, workflow_id, self._total_steps, mode)

    def abort(self) -> None:
        self._abort_event.set()

    def reset(self) -> None:
        self._run_id = None
        self._workflow_id = None
        self._current_step = 0
        self._total_steps = 0
        self._step_description = None
        self._status = RunStatus.PENDING

    # ── Internal execution ────────────────────────────────

    def _execute(self, workflow_data: dict) -> None:
        steps = workflow_data.get("steps", [])
        default_speed = workflow_data.get("default_speed", "normal")

        # Write run meta with "running" status
        self._write_run_meta("running")

        try:
            for i, step in enumerate(steps, start=1):
                if self._abort_event.is_set():
                    self._status = RunStatus.ABORTED
                    self._write_run_meta("aborted")
                    self._post_run_verification(workflow_data, "aborted")
                    return

                self._current_step = i
                self._step_description = step.get("description", "")
                logger.info("Step %d/%d: %s", i, len(steps), self._step_description)

                # Dry-run mode: detect targets without executing
                if self._mode == "dryrun":
                    dryrun_result = self._dryrun_step(step, i)
                    self._save_dryrun_result(i, dryrun_result)
                    continue

                delay = _SPEED_DELAY.get(step.get("speed", default_speed), 0.8)
                time.sleep(delay)

                # Capture before screenshot
                self._capture_step_screenshot(i, "before")

                on_fail = step.get("on_failure", "human")
                max_attempts = 3 if on_fail == "retry" else 1

                step_succeeded = False
                for attempt in range(1, max_attempts + 1):
                    try:
                        self._run_step_with_timeout(step)

                        # Smart wait: poll until condition is met
                        if step.get("wait_condition"):
                            if not self._smart_wait(step):
                                raise RuntimeError(f"Smart wait timed out: {step.get('wait_condition')}")

                        step_succeeded = True
                        break
                    except Exception:
                        logger.exception(
                            "Step %d failed (attempt %d/%d): %s",
                            i, attempt, max_attempts, self._step_description,
                        )
                        if on_fail == "retry" and attempt < max_attempts:
                            backoff = delay * attempt
                            logger.info("Retrying step %d in %.1fs...", i, backoff)
                            time.sleep(backoff)
                            continue
                        # Not a retry case or retries exhausted — fall through
                        break

                if step_succeeded:
                    # Capture after screenshot on success
                    self._capture_step_screenshot(i, "after")
                else:
                    # Step failed after all attempts
                    step_context = {
                        "step_index": i,
                        "step_type": step.get("type", ""),
                        "description": self._step_description,
                    }
                    if on_fail == "abort":
                        self._status = RunStatus.FAILED
                        self._write_run_meta(
                            "failed",
                            error=f"Step {i} failed",
                            step_context=step_context,
                        )
                        self._post_run_verification(workflow_data, "failed", step_context)
                        return
                    elif on_fail == "skip":
                        logger.warning(
                            "Skipping failed step %d: %s", i, self._step_description,
                        )
                    elif on_fail == "human":
                        logger.warning(
                            "Step %d needs human intervention (continuing for now): %s",
                            i, self._step_description,
                        )
                    elif on_fail == "retry":
                        # All retries exhausted
                        self._status = RunStatus.FAILED
                        self._write_run_meta(
                            "failed",
                            error=f"Step {i} failed after {max_attempts} retries",
                            step_context=step_context,
                        )
                        self._post_run_verification(workflow_data, "failed", step_context)
                        return

            self._status = RunStatus.COMPLETED
            self._write_run_meta("completed")
            logger.info("Replay completed: run=%s", self._run_id)
            self._post_run_verification(workflow_data, "completed")

        except Exception:
            logger.exception("Replay engine error")
            self._status = RunStatus.FAILED
            self._write_run_meta("failed", error="Unexpected error")
            self._post_run_verification(workflow_data, "failed")

    def _run_step_with_timeout(self, step: dict) -> None:
        """Execute a step with a timeout enforced via ThreadPoolExecutor."""
        timeout = step.get("timeout_sec", 10)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._run_step, step)
            try:
                future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"Step timed out after {timeout}s")

    def _capture_step_screenshot(self, step_index: int, suffix: str) -> None:
        """Capture a before or after screenshot for a given step."""
        try:
            data, _meta = capture_screen()
            steps_dir = self._paths.run_dir(self._run_id or "unknown") / "steps"
            steps_dir.mkdir(parents=True, exist_ok=True)
            path = steps_dir / f"step_{step_index:03d}_{suffix}.jpg"
            path.write_bytes(data)
        except Exception:
            logger.warning("Failed to capture %s screenshot for step %d", suffix, step_index)

    def _write_run_meta(
        self,
        status: str,
        error: str | None = None,
        step_context: dict | None = None,
        verification_status: bool | None = None,
    ) -> None:
        """Update run meta.json so the backend API reflects current state."""
        from datetime import datetime, timezone

        run_dir = self._paths.run_dir(self._run_id or "unknown")
        run_dir.mkdir(parents=True, exist_ok=True)
        meta_path = run_dir / "meta.json"

        meta: dict = {}
        if meta_path.exists():
            try:
                with meta_path.open("r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass

        meta["status"] = status
        meta["current_step"] = self._current_step
        meta["mode"] = self._mode
        if status in ("completed", "failed", "aborted"):
            meta["finished_at"] = datetime.now(timezone.utc).isoformat()
        if error:
            meta["error"] = error
        if step_context:
            meta["failed_step"] = step_context
        if verification_status is not None:
            meta["verification_status"] = verification_status

        tmp = meta_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, default=str)
        tmp.replace(meta_path)

    def _run_step(self, step: dict) -> None:
        step_type = step.get("type", "")
        value = step.get("value") or ""

        if step_type == "vision_click":
            self._run_vision_click(step)
        elif step_type == "clipboard_paste":
            pyperclip.copy(value)
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "v")
        elif step_type == "hotkey":
            # pynput records Windows key as "cmd"; pyautogui expects "win"
            _KEY_REMAP = {"cmd": "win"}
            keys = [_KEY_REMAP.get(k.strip(), k.strip()) for k in value.split("+") if k.strip()]
            if keys:
                pyautogui.hotkey(*keys)
        elif step_type == "scroll":
            parts = value.split(",")
            if len(parts) >= 4:
                x, y = int(parts[0]), int(parts[1])
                direction, amount = parts[2].strip(), int(parts[3])
                scroll_clicks = amount if direction == "up" else -amount
                pyautogui.scroll(scroll_clicks, x=x, y=y)
        elif step_type == "drag":
            parts = value.split(",")
            if len(parts) >= 4:
                sx, sy, ex, ey = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                pyautogui.moveTo(sx, sy, duration=0.2)
                pyautogui.dragTo(ex, ey, duration=0.5, button="left")
        elif step_type == "cmd":
            subprocess.Popen(value, shell=True)
        elif step_type == "navigate":
            webbrowser.open(value)
        elif step_type == "file_open":
            # Open file with default application
            import os
            if not Path(value).exists():
                raise FileNotFoundError(f"File not found: {value}")
            os.startfile(value)
        elif step_type == "file_write":
            # Write content to file. value format: "filepath|||content"
            separator = "|||"
            if separator in value:
                filepath, content = value.split(separator, 1)
            else:
                raise ValueError(f"file_write value must be 'filepath|||content', got: {value[:50]}")
            p = Path(filepath.strip())
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            logger.info("File written: %s (%d bytes)", p, len(content))
        elif step_type == "focus_window":
            import win32gui
            results: list[int] = []
            def _enum_cb(hwnd: int, collected: list[int]) -> None:
                if win32gui.IsWindowVisible(hwnd) and value.lower() in win32gui.GetWindowText(hwnd).lower():
                    collected.append(hwnd)
            win32gui.EnumWindows(_enum_cb, results)
            if results:
                win32gui.SetForegroundWindow(results[0])
                logger.info("Focused window: %s (hwnd=%d)", win32gui.GetWindowText(results[0]), results[0])
            else:
                raise RuntimeError(f"Window not found: {value}")
        elif step_type == "wait":
            try:
                total = max(0.0, float(value))
            except (ValueError, TypeError):
                total = 1.0
            elapsed = 0.0
            while elapsed < total:
                if self._abort_event.is_set():
                    return
                chunk = min(0.5, total - elapsed)
                time.sleep(chunk)
                elapsed += chunk

    def _find_click_target(self, step: dict) -> dict:
        """Detect click target coordinates without clicking.

        Returns {"x": int|None, "y": int|None, "confidence": float|None, "method": str|None}.
        """
        target_desc = step.get("target_description", "")
        hint = step.get("hint", "")
        fallback = step.get("fallback_coords")
        crop_ref = step.get("crop_ref")
        value = step.get("value", "")

        x, y = None, None
        confidence = None
        method = None
        img_data = None

        # Phase 1: Try AI vision finder
        if target_desc:
            try:
                from ..ai.vision_finder import find_element_on_screen
                img_data, s_meta = capture_screen()
                x, y, confidence = find_element_on_screen(
                    screenshot_bytes=img_data,
                    target_description=target_desc,
                    hint=hint,
                    screen_width=s_meta.capture_width,
                    screen_height=s_meta.capture_height,
                )
                if confidence < 0.3:
                    logger.warning("AI confidence too low (%.2f), trying template match", confidence)
                    x, y, confidence = None, None, None
                else:
                    method = "ai"
                    logger.info("AI found element at (%d, %d) confidence=%.2f", x, y, confidence)
            except Exception:
                logger.warning("AI element finder unavailable, trying template match")

        # Phase 2: Try OpenCV template matching (fast, free, no AI cost)
        if (x is None or y is None) and crop_ref:
            try:
                from .template_matcher import match_template_on_screen
                if img_data is None:
                    img_data, _ = capture_screen()
                result = match_template_on_screen(img_data, crop_ref)
                if result:
                    x, y, confidence = result
                    method = "template"
                    logger.info("Template match at (%d, %d) confidence=%.3f", x, y, confidence)
            except Exception:
                logger.warning("Template matching failed, falling back to coordinates")

        # Phase 3: Fallback to recorded coordinates
        if x is None or y is None:
            if fallback and "x" in fallback and "y" in fallback:
                x, y = fallback["x"], fallback["y"]
                method = "fallback"
                logger.info("Using fallback coordinates (%d, %d)", x, y)
            elif value:
                coords_str = value.removeprefix("double:")
                parts = coords_str.split(",")
                if len(parts) >= 2:
                    x, y = int(parts[0]), int(parts[1])
                    method = "fallback"
                    logger.info("Using legacy value coordinates (%d, %d)", x, y)

        return {"x": x, "y": y, "confidence": confidence, "method": method}

    def _run_vision_click(self, step: dict) -> None:
        """Execute a vision_click step: AI vision → OpenCV template → fallback coords."""
        result = self._find_click_target(step)
        x, y = result["x"], result["y"]

        if x is None or y is None:
            raise RuntimeError(f"Cannot determine click coordinates for step: {step.get('description', '?')}")

        value = step.get("value", "")
        is_double = value.startswith("double:") if value else False

        if is_double:
            pyautogui.doubleClick(x, y)
        else:
            pyautogui.click(x, y)

    def _verify_step(self, step: dict) -> bool:
        """Verify step completion using AI vision."""
        try:
            from ..ai.vision_finder import verify_step_completion
            img_data, _meta = capture_screen()
            return verify_step_completion(
                screenshot_bytes=img_data,
                expected_condition=step.get("wait_condition", ""),
                step_description=step.get("description", ""),
            )
        except Exception:
            logger.warning("Step verification unavailable, assuming success")
            return True  # fail-open: if AI is unavailable, assume success

    # ── 3-B: Smart wait ───────────────────────────────────────

    def _smart_wait(self, step: dict) -> bool:
        """Poll until wait_condition is met or timeout expires."""
        condition = step.get("wait_condition", "")
        if not condition:
            return True
        timeout = step.get("timeout_sec", 10)
        poll_interval = 1.0
        elapsed = 0.0
        while elapsed < timeout:
            if self._abort_event.is_set():
                return False
            if self._verify_step(step):
                logger.info("Smart wait condition met after %.1fs: %s", elapsed, condition)
                return True
            logger.debug("Smart wait polling (%.1f/%.1fs): %s", elapsed, timeout, condition)
            time.sleep(poll_interval)
            elapsed += poll_interval
        logger.warning("Smart wait timed out after %.1fs: %s", timeout, condition)
        return False

    # ── 3-A: Post-run verification ────────────────────────────

    def _post_run_verification(
        self,
        workflow_data: dict,
        final_status: str,
        step_context: dict | None = None,
    ) -> None:
        """Run AI verification and diagnosis after replay completes.

        Saves verification.json and diagnosis.json to the run directory.
        Wrapped in try/except — verification failure never affects the run result.
        """
        if self._mode == "dryrun":
            return  # No verification needed for dry-run

        try:
            run_dir = self._paths.run_dir(self._run_id or "unknown")
            run_dir.mkdir(parents=True, exist_ok=True)

            # Capture final screenshot
            try:
                screenshot_data, _meta = capture_screen()
            except Exception:
                logger.warning("Failed to capture final screenshot for verification")
                return

            wf_name = workflow_data.get("name", "")
            wf_desc = workflow_data.get("description", "")

            # Run async verification in a new event loop (we're in a thread)
            loop = asyncio.new_event_loop()
            try:
                # Verify run
                from backend.gemini.verifier import verify_run
                verification = loop.run_until_complete(
                    verify_run(screenshot_data, wf_name, wf_desc)
                )
                if verification:
                    v_path = run_dir / "verification.json"
                    with v_path.open("w", encoding="utf-8") as f:
                        json.dump(verification, f, ensure_ascii=False)
                    logger.info("Verification saved: success=%s", verification.get("success"))

                    # Update meta with verification status
                    self._write_run_meta(
                        final_status,
                        verification_status=verification.get("success"),
                    )

                # Diagnose failure if run failed
                if final_status == "failed" and step_context:
                    from backend.gemini.verifier import diagnose_failure

                    # Load before/after screenshots for the failed step
                    step_idx = step_context.get("step_index", 0)
                    before_ss = self._load_step_screenshot(step_idx, "before")
                    after_ss = self._load_step_screenshot(step_idx, "after")

                    # Find the failed step data from workflow
                    steps = workflow_data.get("steps", [])
                    failed_step = steps[step_idx - 1] if 0 < step_idx <= len(steps) else {}

                    error_msg = step_context.get("description", "Unknown error")

                    diagnosis = loop.run_until_complete(
                        diagnose_failure(
                            failed_step=failed_step,
                            before_screenshot=before_ss,
                            after_screenshot=after_ss or screenshot_data,
                            error_message=error_msg,
                            workflow_name=wf_name,
                        )
                    )
                    if diagnosis:
                        d_path = run_dir / "diagnosis.json"
                        with d_path.open("w", encoding="utf-8") as f:
                            json.dump(diagnosis, f, ensure_ascii=False)
                        logger.info("Diagnosis saved: cause=%s", diagnosis.get("cause"))
            finally:
                loop.close()

        except Exception:
            logger.exception("Post-run verification failed (non-fatal)")

    def _load_step_screenshot(self, step_index: int, suffix: str) -> bytes | None:
        """Load a previously saved step screenshot."""
        try:
            steps_dir = self._paths.run_dir(self._run_id or "unknown") / "steps"
            path = steps_dir / f"step_{step_index:03d}_{suffix}.jpg"
            if path.exists():
                return path.read_bytes()
        except Exception:
            pass
        return None

    # ── 3-C: Dry-run mode ─────────────────────────────────────

    def _dryrun_step(self, step: dict, step_index: int) -> dict:
        """Evaluate a step without executing it. Returns dry-run result."""
        step_type = step.get("type", "")
        description = step.get("description", "")

        result = {
            "step_index": step_index,
            "step_type": step_type,
            "description": description,
            "skipped": True,
            "skip_reason": None,
            "expected_x": None,
            "expected_y": None,
            "confidence": None,
            "method": None,
        }

        if step_type == "vision_click":
            try:
                target = self._find_click_target(step)
                result["expected_x"] = target["x"]
                result["expected_y"] = target["y"]
                result["confidence"] = target["confidence"]
                result["method"] = target["method"]
                result["skipped"] = target["x"] is None
                if target["x"] is not None:
                    result["skip_reason"] = None
                else:
                    result["skip_reason"] = "클릭 대상을 찾을 수 없음"
            except Exception as e:
                result["skip_reason"] = f"탐지 실패: {e}"
        else:
            result["skip_reason"] = f"{step_type} 스텝은 드라이런에서 실행하지 않음"

        logger.info(
            "Dryrun step %d: type=%s skipped=%s x=%s y=%s confidence=%s method=%s",
            step_index, step_type, result["skipped"],
            result["expected_x"], result["expected_y"],
            result["confidence"], result["method"],
        )
        return result

    def _save_dryrun_result(self, step_index: int, result: dict) -> None:
        """Save dry-run result to steps/step_NNN_dryrun.json."""
        try:
            steps_dir = self._paths.run_dir(self._run_id or "unknown") / "steps"
            steps_dir.mkdir(parents=True, exist_ok=True)
            path = steps_dir / f"step_{step_index:03d}_dryrun.json"
            with path.open("w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)
        except Exception:
            logger.warning("Failed to save dryrun result for step %d", step_index)

    def _exec_click(self, value: str) -> None:
        is_double = value.startswith("double:")
        coords = value.removeprefix("double:")
        parts = coords.split(",")
        if len(parts) >= 2:
            x, y = int(parts[0]), int(parts[1])
            if is_double:
                pyautogui.doubleClick(x, y)
            else:
                pyautogui.click(x, y)

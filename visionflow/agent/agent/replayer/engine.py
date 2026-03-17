"""Replay engine — executes workflow steps using pyautogui."""

from __future__ import annotations

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

    def start(self, run_id: str, workflow_id: str) -> None:
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

        self._thread = threading.Thread(
            target=self._execute,
            args=(workflow_data,),
            daemon=True,
            name="replayer",
        )
        self._thread.start()
        logger.info("Replay started: run=%s workflow=%s steps=%d", run_id, workflow_id, self._total_steps)

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
                    return

                self._current_step = i
                self._step_description = step.get("description", "")
                logger.info("Step %d/%d: %s", i, len(steps), self._step_description)

                delay = _SPEED_DELAY.get(step.get("speed", default_speed), 0.8)
                time.sleep(delay)

                try:
                    self._run_step(step)
                except Exception:
                    logger.exception("Step %d failed: %s", i, self._step_description)
                    on_fail = step.get("on_failure", "human")
                    if on_fail == "abort":
                        self._status = RunStatus.FAILED
                        self._write_run_meta("failed", error=f"Step {i} failed")
                        return
                    # skip / human / retry → continue to next step

            self._status = RunStatus.COMPLETED
            self._write_run_meta("completed")
            logger.info("Replay completed: run=%s", self._run_id)

        except Exception:
            logger.exception("Replay engine error")
            self._status = RunStatus.FAILED
            self._write_run_meta("failed", error="Unexpected error")

    def _write_run_meta(self, status: str, error: str | None = None) -> None:
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
        if status in ("completed", "failed", "aborted"):
            meta["finished_at"] = datetime.now(timezone.utc).isoformat()
        if error:
            meta["error"] = error

        tmp = meta_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, default=str)
        tmp.replace(meta_path)

    def _run_step(self, step: dict) -> None:
        step_type = step.get("type", "")
        value = step.get("value") or ""

        if step_type == "vision_click":
            self._exec_click(value)
        elif step_type == "clipboard_paste":
            pyperclip.copy(value)
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "v")
        elif step_type == "hotkey":
            keys = [k.strip() for k in value.split("+") if k.strip()]
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
        elif step_type == "wait":
            try:
                time.sleep(max(0.0, float(value)))
            except (ValueError, TypeError):
                time.sleep(1.0)

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

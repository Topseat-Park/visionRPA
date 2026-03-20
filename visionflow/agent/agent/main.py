"""VisionFlow Agent — main entry point.

Runs the IPC command loop: polls for commands from Dashboard,
dispatches to recorder/replayer, and publishes status via heartbeat.

Global hotkeys:
  F9  — Toggle recording (start new / pause / resume)
  F10 — Stop recording
"""

from __future__ import annotations

import logging
import signal
import time
import uuid
from datetime import datetime, timezone

from shared.enums import CommandType, RecordingState
from shared.event_models import SessionMeta
from shared.ipc_models import AgentCommand

from .config import AgentConfig, get_config
from .ipc.file_transport import FileTransport
from .monitor.heartbeat import Heartbeat
from .recorder.engine import RecordingEngine
from .replayer.engine import ReplayEngine
from .storage.paths import DataPaths
from .ui.desktop import minimize_all_windows, restore_minimized_windows
from .ui.hotkeys import GlobalHotkeys
from .ui.overlay import RecordingOverlay
from .ui.tooltip import HelpTooltip

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("visionflow.agent")


class Agent:
    """Top-level agent that ties together IPC, recorder, hotkeys, and heartbeat."""

    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._paths = DataPaths(config.data_dir)
        self._paths.ensure_dirs()

        self._transport = FileTransport(self._paths)
        self._recorder = RecordingEngine(config, self._paths)
        self._replayer = ReplayEngine(self._paths)
        self._heartbeat = Heartbeat(
            self._transport, self._recorder, self._replayer, config.heartbeat_interval
        )

        # UI components
        self._overlay = RecordingOverlay(monitor_index=config.default_monitor)
        self._tooltip = HelpTooltip()
        self._hotkeys = GlobalHotkeys(
            on_f9=self._on_hotkey_f9,
            on_f10=self._on_hotkey_f10,
        )

        self._running = False

    def run(self) -> None:
        """Main loop — poll for commands and dispatch."""
        self._running = True
        self._heartbeat.start()
        # Hotkeys are NOT registered on startup — only during active recording
        logger.info("Agent started. Data dir: %s", self._config.data_dir.resolve())
        logger.info("Hotkeys (F9/F10) will activate when recording starts")

        try:
            while self._running:
                cmd = self._transport.poll_command()
                if cmd:
                    self._handle_command(cmd)
                time.sleep(self._config.ipc_poll_interval)
        except KeyboardInterrupt:
            logger.info("Agent interrupted")
        finally:
            self._shutdown()

    def _handle_command(self, cmd: AgentCommand) -> None:
        logger.info("Command received: %s (id=%s)", cmd.type, cmd.id)
        self._heartbeat.set_last_command_id(cmd.id)
        self._heartbeat.set_error(None)

        try:
            match cmd.type:
                case CommandType.START_RECORDING:
                    self._start_recording(cmd)
                case CommandType.PAUSE_RECORDING:
                    self._pause_recording()
                case CommandType.RESUME_RECORDING:
                    self._resume_recording()
                case CommandType.STOP_RECORDING:
                    self._stop_recording()
                case CommandType.START_RUN:
                    self._start_run(cmd)
                case CommandType.ABORT_RUN:
                    self._replayer.abort()
                case CommandType.PING:
                    pass  # heartbeat will respond
                case _:
                    logger.warning("Unhandled command type: %s", cmd.type)
        except Exception as e:
            logger.exception("Error handling command %s", cmd.type)
            self._heartbeat.set_error(str(e))

    # ── Recording with overlay ──────────────────────────────────

    def _start_recording(self, cmd: AgentCommand) -> None:
        # Reset if previous recording completed
        if self._recorder.state == RecordingState.COMPLETED:
            self._recorder.reset()

        session_id = cmd.payload.get("session_id", f"sess_{uuid.uuid4().hex[:8]}")
        meta = SessionMeta(
            session_id=session_id,
            created_at=datetime.now(timezone.utc),
            purpose=cmd.payload.get("purpose", ""),
            apps=cmd.payload.get("apps", []),
            exceptions=cmd.payload.get("exceptions", []),
            exception_notes=cmd.payload.get("exception_notes"),
            has_sensitive_info=cmd.payload.get("has_sensitive_info", False),
        )

        # Minimize all windows for a clean recording surface
        if cmd.payload.get("minimize_windows", True):
            minimize_all_windows()

        self._recorder.start(session_id, meta)
        self._overlay.start()
        self._tooltip.start()
        self._hotkeys.start()
        logger.info("Hotkeys activated (F9=pause/resume, F10=stop)")

    def _pause_recording(self) -> None:
        self._recorder.pause()
        self._overlay.stop()
        self._tooltip.stop()

    def _resume_recording(self) -> None:
        self._recorder.resume()
        self._overlay.start()
        self._tooltip.start()

    def _stop_recording(self) -> None:
        self._hotkeys.stop()
        self._recorder.stop()
        self._overlay.stop()
        self._tooltip.stop()
        restore_minimized_windows()
        logger.info("Hotkeys deactivated")

    # ── Global hotkey handlers (only active during recording) ──

    def _on_hotkey_f9(self) -> None:
        """F9: Pause / resume (only works during active recording)."""
        state = self._recorder.state

        if state == RecordingState.RECORDING:
            self._recorder.pause()
            self._overlay.stop()
            self._tooltip.stop()
            logger.info("F9: Recording paused")

        elif state == RecordingState.PAUSED:
            self._recorder.resume()
            self._overlay.start()
            self._tooltip.start()
            logger.info("F9: Recording resumed")

    def _on_hotkey_f10(self) -> None:
        """F10: Stop recording."""
        state = self._recorder.state
        if state in (RecordingState.RECORDING, RecordingState.PAUSED):
            self._stop_recording()
            logger.info("F10: Recording stopped")
        else:
            logger.info("F10: No active recording to stop")

    # ── Run management ──────────────────────────────────────────

    def _start_run(self, cmd: AgentCommand) -> None:
        run_id = cmd.payload.get("run_id", f"run_{uuid.uuid4().hex[:8]}")
        workflow_id = cmd.payload.get("workflow_id", "")
        mode = cmd.payload.get("mode", "normal")
        step_index = cmd.payload.get("step_index")
        if not workflow_id:
            raise ValueError("start_run requires workflow_id in payload")
        # Reset replayer if a previous run completed
        if not self._replayer.is_running:
            self._replayer.reset()
        self._replayer.start(run_id, workflow_id, mode=mode, step_index=step_index)

    # ── Shutdown ────────────────────────────────────────────────

    def _shutdown(self) -> None:
        if self._recorder.state in (RecordingState.RECORDING, RecordingState.PAUSED):
            self._recorder.stop()
        self._overlay.stop()
        self._tooltip.stop()
        self._hotkeys.stop()
        self._heartbeat.stop()
        logger.info("Agent shutdown complete")


def _enable_dpi_awareness() -> None:
    """Declare DPI awareness so overlay coordinates match physical pixels."""
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor V2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main() -> None:
    _enable_dpi_awareness()
    config = get_config()
    agent = Agent(config)

    def _signal_handler(sig: int, frame: object) -> None:
        logger.info("Signal %d received, shutting down...", sig)
        agent._running = False

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    agent.run()


if __name__ == "__main__":
    main()

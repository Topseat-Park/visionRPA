"""Heartbeat — periodically updates status.json."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

import psutil

from shared.enums import AgentState
from shared.ipc_models import AgentStatus, RecordingDetails, SystemInfo

from ..ipc.base import ABCTransport
from ..recorder.engine import RecordingEngine

logger = logging.getLogger(__name__)


class Heartbeat:
    """Runs in a background thread, publishing agent status at fixed intervals."""

    def __init__(
        self,
        transport: ABCTransport,
        recorder: RecordingEngine,
        interval: float = 1.0,
    ) -> None:
        self._transport = transport
        self._recorder = recorder
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_command_id: str | None = None
        self._error: str | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="heartbeat"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)

    def set_last_command_id(self, cmd_id: str) -> None:
        self._last_command_id = cmd_id

    def set_error(self, error: str | None) -> None:
        self._error = error

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                status = self._build_status()
                self._transport.update_status(status)
            except Exception:
                logger.exception("Heartbeat status update failed")
            self._stop_event.wait(self._interval)

    def _build_status(self) -> AgentStatus:
        from shared.enums import RecordingState

        # Determine agent state from recorder
        rec_state = self._recorder.state
        if rec_state == RecordingState.RECORDING:
            agent_state = AgentState.RECORDING
        elif rec_state == RecordingState.PAUSED:
            agent_state = AgentState.RECORDING  # still conceptually recording
        else:
            agent_state = AgentState.ONLINE

        recording = None
        if rec_state in (RecordingState.RECORDING, RecordingState.PAUSED) and self._recorder.session_id:
            recording = RecordingDetails(
                session_id=self._recorder.session_id,
                event_count=self._recorder.event_count,
                elapsed_seconds=round(self._recorder.elapsed_seconds, 1),
            )

        process = psutil.Process()
        sys_info = SystemInfo(
            cpu_percent=process.cpu_percent(interval=0),
            memory_mb=round(process.memory_info().rss / 1024 / 1024, 1),
        )
        try:
            import win32gui  # type: ignore[import-untyped]
            hwnd = win32gui.GetForegroundWindow()
            sys_info.active_window = win32gui.GetWindowText(hwnd) or None
        except Exception:
            pass

        return AgentStatus(
            timestamp=datetime.now(timezone.utc),
            agent_state=agent_state,
            last_command_id=self._last_command_id,
            last_command_ack=True,
            recording=recording,
            system=sys_info,
            error=self._error,
        )

"""Recording engine — state machine that orchestrates capture."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from shared.enums import RecordingState
from shared.event_models import SessionMeta

from ..config import AgentConfig
from ..storage.paths import DataPaths
from .listeners import InputListeners
from .screenshot import capture_screen, save_screenshot
from .session_writer import SessionWriter

logger = logging.getLogger(__name__)


class RecordingEngine:
    """State machine: IDLE → RECORDING → PAUSED → COMPLETED.

    Runs a consumer thread that drains the listener event queue,
    captures screenshots, and writes to the session directory.
    """

    def __init__(self, config: AgentConfig, paths: DataPaths) -> None:
        self._config = config
        self._paths = paths
        self._state = RecordingState.IDLE
        self._listeners: InputListeners | None = None
        self._writer: SessionWriter | None = None
        self._consumer_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._seq = 0
        self._session_id: str | None = None
        self._start_time: float = 0

    @property
    def state(self) -> RecordingState:
        return self._state

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def event_count(self) -> int:
        return self._seq

    @property
    def elapsed_seconds(self) -> float:
        if self._start_time == 0:
            return 0
        return time.time() - self._start_time

    def start(self, session_id: str, meta: SessionMeta) -> None:
        """Begin recording."""
        if self._state != RecordingState.IDLE:
            raise RuntimeError(f"Cannot start from state {self._state}")

        self._session_id = session_id
        self._seq = 0
        self._start_time = time.time()
        self._stop_event.clear()

        self._writer = SessionWriter(self._paths, session_id)
        self._writer.ensure_dirs()
        self._writer.write_meta(meta)

        self._listeners = InputListeners()
        self._listeners.start()

        self._consumer_thread = threading.Thread(
            target=self._consume_loop, daemon=True, name="recorder-consumer"
        )
        self._consumer_thread.start()

        self._state = RecordingState.RECORDING
        logger.info("Recording started: session=%s", session_id)

    def pause(self) -> None:
        if self._state != RecordingState.RECORDING:
            return
        self._state = RecordingState.PAUSED
        logger.info("Recording paused")

    def resume(self) -> None:
        if self._state != RecordingState.PAUSED:
            return
        self._state = RecordingState.RECORDING
        logger.info("Recording resumed")

    def stop(self) -> None:
        """Stop recording and flush."""
        if self._state not in (RecordingState.RECORDING, RecordingState.PAUSED):
            return

        self._state = RecordingState.COMPLETED
        self._stop_event.set()

        if self._listeners:
            self._listeners.stop()
        if self._consumer_thread:
            self._consumer_thread.join(timeout=5)

        logger.info(
            "Recording completed: session=%s events=%d",
            self._session_id,
            self._seq,
        )

    def reset(self) -> None:
        """Reset to IDLE for next recording."""
        self._state = RecordingState.IDLE
        self._listeners = None
        self._writer = None
        self._consumer_thread = None
        self._session_id = None
        self._seq = 0
        self._start_time = 0

    def _consume_loop(self) -> None:
        """Consumer thread: drain event queue, capture screenshots, write."""
        assert self._listeners is not None
        assert self._writer is not None

        last_event_type: str | None = None

        while not self._stop_event.is_set():
            # Check typing debounce flush
            if self._listeners._type_buffer:
                elapsed = time.time() - self._listeners._type_last_time
                if elapsed > self._listeners._TYPE_DEBOUNCE:
                    self._listeners._flush_type_buffer()

            try:
                raw = self._listeners.event_queue.get(timeout=0.1)
            except Exception:
                continue

            # Skip events while paused
            if self._state == RecordingState.PAUSED:
                continue

            self._seq += 1
            raw_type = raw.pop("raw_type", "unknown")

            # Capture screenshot
            screenshot_path = None
            screenshot_meta = None
            try:
                img_data, s_meta = capture_screen(
                    monitor_index=self._config.default_monitor,
                    quality=self._config.screenshot_quality,
                    max_bytes=self._config.screenshot_max_bytes,
                )
                filename = f"{self._seq:06d}_{raw_type}.jpg"
                screenshot_path = self._writer.save_screenshot(img_data, filename)
                screenshot_meta = s_meta.model_dump(mode="json")
            except Exception:
                logger.exception("Screenshot capture failed for event %d", self._seq)

            # Build event dict
            event_dict = {
                "seq": self._seq,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": raw_type,
                **raw,
            }
            if screenshot_path:
                event_dict["screenshot_path"] = screenshot_path
            if screenshot_meta:
                event_dict["screenshot_meta"] = screenshot_meta

            self._writer.append_event(event_dict)
            last_event_type = raw_type

        # Final flush of type buffer
        if self._listeners and self._listeners._type_buffer:
            self._listeners._flush_type_buffer()

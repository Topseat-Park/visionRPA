"""Recording engine — state machine that orchestrates capture."""

from __future__ import annotations

import logging
import queue
import threading
import time
from datetime import datetime, timezone

from shared.enums import RecordingState
from shared.event_models import SessionMeta

from ..config import AgentConfig
from ..storage.paths import DataPaths
from .listeners import InputListeners
from .screenshot import capture_screen
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
        self._last_active_window: str = ""

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

        # Snapshot open windows at recording start (#5)
        open_windows = self._snapshot_open_windows()
        meta_dict = meta.model_dump(mode="json")
        meta_dict["open_windows"] = open_windows
        self._writer.write_meta_dict(meta_dict)
        self._last_active_window = ""

        self._listeners = InputListeners()
        self._listeners.start()

        if not self._listeners.listeners_alive:
            logger.error(
                "One or more input listeners failed to start! "
                "Recording may not capture events. "
                "Try running as Administrator or check antivirus settings."
            )

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
        self._last_active_window = ""

    def _consume_loop(self) -> None:
        """Consumer thread: drain event queue, capture screenshots, write."""
        assert self._listeners is not None
        assert self._writer is not None

        logger.info("Consumer loop started")
        _listener_check_interval = 10.0  # check listener health every N seconds
        _last_listener_check = time.time()

        while not self._stop_event.is_set():
            # Periodically verify that input listeners are still alive
            now = time.time()
            if now - _last_listener_check > _listener_check_interval:
                _last_listener_check = now
                if not self._listeners.listeners_alive:
                    logger.error(
                        "Input listener thread(s) died during recording! "
                        "Events may be lost. mouse_alive=%s keyboard_alive=%s",
                        self._listeners._mouse_listener is not None
                        and self._listeners._mouse_listener.is_alive(),
                        self._listeners._keyboard_listener is not None
                        and self._listeners._keyboard_listener.is_alive(),
                    )

            # Check typing debounce flush (lock-protected access to buffer state)
            try:
                with self._listeners._type_lock:
                    if self._listeners._type_buffer:
                        elapsed = time.time() - self._listeners._type_last_time
                        if elapsed > self._listeners._TYPE_DEBOUNCE:
                            self._listeners._flush_type_buffer_locked()
            except Exception:
                logger.exception("Error during type buffer flush check")

            try:
                raw = self._listeners.event_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # Skip events while paused
            if self._state == RecordingState.PAUSED:
                continue

            try:
                # Track active window — inject window_change event on switch (#1)
                current_window = self._get_active_window_title()
                if current_window and current_window != self._last_active_window:
                    if self._last_active_window:  # skip first event
                        self._seq += 1
                        wc_event = {
                            "seq": self._seq,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "event_type": "window_change",
                            "window_title": current_window,
                            "previous_window": self._last_active_window,
                        }
                        self._writer.append_event(wc_event)
                        logger.debug("Window change: %s → %s", self._last_active_window, current_window)
                    self._last_active_window = current_window

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

                # Crop around click point for click events
                crop_path = None
                if raw_type in ("click", "double_click") and img_data:
                    try:
                        from .screenshot import crop_around_click
                        crop_x = raw.get("x", 0)
                        crop_y = raw.get("y", 0)
                        crop_data = crop_around_click(img_data, crop_x, crop_y)
                        crop_filename = f"{self._seq:06d}_{raw_type}_crop.jpg"
                        crop_path = self._writer.save_screenshot(crop_data, crop_filename)
                    except Exception:
                        logger.exception("Crop capture failed for event %d", self._seq)

                # Build event dict — include active window context
                event_dict = {
                    "seq": self._seq,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event_type": raw_type,
                    "active_window": self._last_active_window,
                    **raw,
                }
                if screenshot_path:
                    event_dict["screenshot_path"] = screenshot_path
                if screenshot_meta:
                    event_dict["screenshot_meta"] = screenshot_meta
                if crop_path:
                    event_dict["crop_path"] = crop_path

                self._writer.append_event(event_dict)
            except Exception:
                logger.exception("Error processing event seq=%d", self._seq)

        # Final flush: write any remaining type buffer and drain the queue
        logger.info("Consumer loop ending — flushing remaining events")
        if self._listeners:
            self._listeners._flush_type_buffer()
            # Drain any remaining events in the queue (including the just-flushed type)
            while not self._listeners.event_queue.empty():
                try:
                    raw = self._listeners.event_queue.get_nowait()
                except queue.Empty:
                    break
                self._seq += 1
                raw_type = raw.pop("raw_type", "unknown")
                event_dict = {
                    "seq": self._seq,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event_type": raw_type,
                    **raw,
                }
                try:
                    self._writer.append_event(event_dict)
                except Exception:
                    logger.exception("Error writing final event seq=%d", self._seq)

    @staticmethod
    def _get_active_window_title() -> str:
        """Return the title of the current foreground window."""
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(hwnd) if hwnd else ""
        except Exception:
            return ""

    @staticmethod
    def _snapshot_open_windows() -> list[str]:
        """Return titles of all visible windows at recording start."""
        try:
            import win32gui
            windows: list[str] = []
            def _enum_cb(hwnd: int, results: list[str]) -> None:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        results.append(title)
            win32gui.EnumWindows(_enum_cb, windows)
            return windows
        except Exception:
            logger.warning("Failed to snapshot open windows")
            return []

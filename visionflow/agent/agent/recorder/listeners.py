"""pynput-based mouse and keyboard listeners."""

from __future__ import annotations

import logging
import queue
import time
from threading import Lock

from pynput import keyboard, mouse

logger = logging.getLogger(__name__)


class InputListeners:
    """Captures mouse and keyboard events into a thread-safe queue.

    Events are placed as dicts with a 'raw_type' key for the engine to process.
    """

    def __init__(self) -> None:
        self.event_queue: queue.Queue[dict] = queue.Queue(maxsize=10000)
        self._mouse_listener: mouse.Listener | None = None
        self._keyboard_listener: keyboard.Listener | None = None

        # Typing debounce state
        self._type_buffer: list[str] = []
        self._type_last_time: float = 0
        self._type_lock = Lock()
        self._TYPE_DEBOUNCE = 0.5  # seconds

        # Click tracking for double-click detection
        self._last_click_time: float = 0
        self._last_click_pos: tuple[int, int] = (0, 0)
        self._DOUBLE_CLICK_THRESHOLD = 0.3

        # Drag tracking
        self._mouse_pressed = False
        self._drag_start: tuple[int, int] | None = None

        # Current key modifiers
        self._pressed_keys: set[str] = set()

    def start(self) -> None:
        self._mouse_listener = mouse.Listener(
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self) -> None:
        self._flush_type_buffer()
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()

    def _put(self, event: dict) -> None:
        try:
            self.event_queue.put_nowait(event)
        except queue.Full:
            logger.warning("Event queue full, dropping event")

    # ── Mouse callbacks ─────────────────────────────────

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        now = time.time()

        if pressed:
            self._mouse_pressed = True
            self._drag_start = (x, y)

            # Flush any pending type buffer
            self._flush_type_buffer()

            # Check for double-click
            if (
                now - self._last_click_time < self._DOUBLE_CLICK_THRESHOLD
                and (x, y) == self._last_click_pos
            ):
                self._put({"raw_type": "double_click", "x": x, "y": y})
            else:
                self._put({
                    "raw_type": "click",
                    "x": x,
                    "y": y,
                    "button": button.name,
                })

            self._last_click_time = now
            self._last_click_pos = (x, y)
        else:
            # Mouse released — check if it was a drag
            if self._mouse_pressed and self._drag_start:
                sx, sy = self._drag_start
                distance = ((x - sx) ** 2 + (y - sy) ** 2) ** 0.5
                if distance > 10:  # minimum drag distance
                    self._put({
                        "raw_type": "drag",
                        "start_x": sx,
                        "start_y": sy,
                        "end_x": x,
                        "end_y": y,
                    })
            self._mouse_pressed = False
            self._drag_start = None

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        self._flush_type_buffer()
        direction = "up" if dy > 0 else "down"
        self._put({
            "raw_type": "scroll",
            "x": x,
            "y": y,
            "direction": direction,
            "amount": abs(dy),
        })

    # ── Keyboard callbacks ──────────────────────────────

    def _on_key_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        key_str = self._key_to_str(key)
        if not key_str:
            return

        # Track modifier keys
        if key_str.lower() in ("ctrl", "alt", "shift", "cmd", "ctrl_l", "ctrl_r", "alt_l", "alt_r", "shift_l", "shift_r"):
            self._pressed_keys.add(key_str.lower().rstrip("_l").rstrip("_r"))
            return

        # If modifiers are held, it's a hotkey
        if self._pressed_keys:
            self._flush_type_buffer()
            combo = sorted(self._pressed_keys) + [key_str.lower()]
            self._put({"raw_type": "key", "keys": combo})
            return

        # Regular character → buffer for typing debounce
        if len(key_str) == 1:  # printable character
            with self._type_lock:
                now = time.time()
                if now - self._type_last_time > self._TYPE_DEBOUNCE and self._type_buffer:
                    self._flush_type_buffer_locked()
                self._type_buffer.append(key_str)
                self._type_last_time = now
        else:
            # Special key (Enter, Tab, etc.) — treat as hotkey
            self._flush_type_buffer()
            self._put({"raw_type": "key", "keys": [key_str.lower()]})

    def _on_key_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        key_str = self._key_to_str(key)
        if key_str:
            normalized = key_str.lower().rstrip("_l").rstrip("_r")
            self._pressed_keys.discard(normalized)

    def _flush_type_buffer(self) -> None:
        with self._type_lock:
            self._flush_type_buffer_locked()

    def _flush_type_buffer_locked(self) -> None:
        if self._type_buffer:
            text = "".join(self._type_buffer)
            self._put({"raw_type": "type", "text": text})
            self._type_buffer.clear()

    @staticmethod
    def _key_to_str(key: keyboard.Key | keyboard.KeyCode | None) -> str | None:
        if key is None:
            return None
        if isinstance(key, keyboard.KeyCode):
            return key.char if key.char else None
        # keyboard.Key enum
        return key.name

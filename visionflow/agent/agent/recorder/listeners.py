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

        # Key dedup: Windows pynput can fire duplicate key events
        self._last_key_event: tuple[str, float] = ("", 0)
        self._KEY_DEDUP_WINDOW = 0.05  # 50ms

    @property
    def listeners_alive(self) -> bool:
        """Return True if both listener threads are alive."""
        m = self._mouse_listener is not None and self._mouse_listener.is_alive()
        k = self._keyboard_listener is not None and self._keyboard_listener.is_alive()
        return m and k

    def start(self) -> None:
        logger.info("Starting input listeners (pynput)...")
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

        # Give listener threads time to initialise OS hooks, then verify
        time.sleep(0.5)
        if not self._mouse_listener.is_alive():
            logger.error(
                "Mouse listener thread DIED on startup — "
                "input hooks may have failed (check permissions / antivirus)"
            )
        else:
            logger.info("Mouse listener alive")

        if not self._keyboard_listener.is_alive():
            logger.error(
                "Keyboard listener thread DIED on startup — "
                "input hooks may have failed (check permissions / antivirus)"
            )
        else:
            logger.info("Keyboard listener alive")

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
        try:
            now = time.time()

            if pressed:
                self._mouse_pressed = True
                self._drag_start = (x, y)

                # Flush any pending type buffer
                self._flush_type_buffer()

                # Check for double-click (allow small pixel tolerance)
                lx, ly = self._last_click_pos
                if (
                    now - self._last_click_time < self._DOUBLE_CLICK_THRESHOLD
                    and abs(x - lx) <= 5 and abs(y - ly) <= 5
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
        except Exception:
            logger.exception("Error in mouse click callback")

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        try:
            self._flush_type_buffer()
            direction = "up" if dy > 0 else "down"
            self._put({
                "raw_type": "scroll",
                "x": x,
                "y": y,
                "direction": direction,
                "amount": abs(dy),
            })
        except Exception:
            logger.exception("Error in mouse scroll callback")

    # ── Keyboard callbacks ──────────────────────────────

    def _on_key_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        try:
            key_str = self._key_to_str(key)
            if not key_str:
                return

            # Deduplicate: Windows pynput can fire the same key twice within ms
            now = time.time()
            if key_str == self._last_key_event[0] and now - self._last_key_event[1] < self._KEY_DEDUP_WINDOW:
                return
            self._last_key_event = (key_str, now)

            # Track modifier keys
            if key_str.lower() in ("ctrl", "alt", "shift", "cmd", "cmd_l", "cmd_r", "ctrl_l", "ctrl_r", "alt_l", "alt_r", "shift_l", "shift_r"):
                self._pressed_keys.add(self._normalize_modifier(key_str))
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
        except Exception:
            logger.exception("Error in key press callback")

    def _on_key_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        try:
            key_str = self._key_to_str(key)
            if key_str:
                self._pressed_keys.discard(self._normalize_modifier(key_str))
        except Exception:
            logger.exception("Error in key release callback")

    def _flush_type_buffer(self) -> None:
        with self._type_lock:
            self._flush_type_buffer_locked()

    def _flush_type_buffer_locked(self) -> None:
        if self._type_buffer:
            text = "".join(self._type_buffer)
            self._put({"raw_type": "type", "text": text})
            self._type_buffer.clear()

    @staticmethod
    def _normalize_modifier(key_str: str) -> str:
        """Normalize modifier key names: 'ctrl_l' → 'ctrl', 'cmd' → 'win' (Windows key)."""
        name = key_str.lower()
        for suffix in ("_l", "_r"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        # pynput calls the Windows key "cmd" — remap to "win" for clarity
        if name == "cmd":
            return "win"
        return name

    @staticmethod
    def _key_to_str(key: keyboard.Key | keyboard.KeyCode | None) -> str | None:
        if key is None:
            return None
        if isinstance(key, keyboard.KeyCode):
            if key.char:
                # On Windows, Ctrl+<letter> produces ASCII control chars (0x01-0x1A).
                # Convert them back to the actual letter (e.g., \x01 → 'a').
                code = ord(key.char)
                if 1 <= code <= 26:
                    return chr(code + 96)  # 1→'a', 2→'b', ..., 26→'z'
                return key.char
            # Fallback to virtual key code if char is None (e.g., numpad keys)
            if key.vk is not None:
                # Map common virtual key codes to readable names
                if 0x30 <= key.vk <= 0x39:  # 0-9
                    return chr(key.vk)
                if 0x41 <= key.vk <= 0x5A:  # A-Z
                    return chr(key.vk + 32)  # lowercase
                if 0x60 <= key.vk <= 0x69:  # Numpad 0-9
                    return str(key.vk - 0x60)
            return None
        # keyboard.Key enum
        return key.name

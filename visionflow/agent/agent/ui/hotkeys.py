"""Global hotkeys — F9 (start/pause/resume), F10 (stop) via Win32 RegisterHotKey.

RegisterHotKey is system-wide and works even when our app has no focus.
Runs its own message pump thread.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

# Virtual key codes
VK_F9 = 0x78
VK_F10 = 0x79

# Hotkey IDs (arbitrary, must be unique per thread)
HOTKEY_ID_F9 = 1
HOTKEY_ID_F10 = 2


class GlobalHotkeys:
    """Register F9 and F10 as system-wide hotkeys.

    F9 = toggle recording (start / pause / resume)
    F10 = stop recording

    Callbacks are invoked on the hotkey thread — keep them fast
    (e.g., write to a queue or set an event).
    """

    def __init__(
        self,
        on_f9: Callable[[], None] | None = None,
        on_f10: Callable[[], None] | None = None,
    ) -> None:
        self._on_f9 = on_f9
        self._on_f10 = on_f10
        self._thread: threading.Thread | None = None
        self._thread_id: int = 0
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="global-hotkeys"
        )
        self._thread.start()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        # Post WM_QUIT to the hotkey thread's message queue
        if self._thread_id:
            ctypes.windll.kernel32.PostThreadMessageW(
                self._thread_id, WM_QUIT, 0, 0
            )
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("Global hotkeys stopped")

    def _run(self) -> None:
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        # Register hotkeys (no modifiers, just F9 / F10)
        ok_f9 = user32.RegisterHotKey(None, HOTKEY_ID_F9, 0, VK_F9)
        ok_f10 = user32.RegisterHotKey(None, HOTKEY_ID_F10, 0, VK_F10)

        if ok_f9:
            logger.info("Global hotkey registered: F9 (toggle recording)")
        else:
            logger.warning("Failed to register F9 hotkey (may be used by another app)")

        if ok_f10:
            logger.info("Global hotkey registered: F10 (stop recording)")
        else:
            logger.warning("Failed to register F10 hotkey (may be used by another app)")

        # Message loop
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                if msg.wParam == HOTKEY_ID_F9 and self._on_f9:
                    try:
                        self._on_f9()
                    except Exception:
                        logger.exception("Error in F9 handler")
                elif msg.wParam == HOTKEY_ID_F10 and self._on_f10:
                    try:
                        self._on_f10()
                    except Exception:
                        logger.exception("Error in F10 handler")

        # Unregister
        user32.UnregisterHotKey(None, HOTKEY_ID_F9)
        user32.UnregisterHotKey(None, HOTKEY_ID_F10)

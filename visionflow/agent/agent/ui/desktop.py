"""Desktop utilities — minimize all windows, focus management."""

from __future__ import annotations

import ctypes
import logging
import time

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32


def minimize_all_windows() -> None:
    """Minimize all windows (Show Desktop) via Win+D keypress simulation."""
    VK_LWIN = 0x5B
    VK_D = 0x44
    KEYEVENTF_KEYUP = 0x0002

    user32.keybd_event(VK_LWIN, 0, 0, 0)
    user32.keybd_event(VK_D, 0, 0, 0)
    user32.keybd_event(VK_D, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)

    time.sleep(0.5)  # wait for animation
    logger.info("All windows minimized (Win+D)")


def restore_minimized_windows() -> None:
    """Restore windows that were minimized by minimize_all_windows() via Win+D toggle."""
    VK_LWIN = 0x5B
    VK_D = 0x44
    KEYEVENTF_KEYUP = 0x0002
    user32.keybd_event(VK_LWIN, 0, 0, 0)
    user32.keybd_event(VK_D, 0, 0, 0)
    user32.keybd_event(VK_D, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.5)
    logger.info("Windows restored (Win+D toggle)")

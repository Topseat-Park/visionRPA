"""Recording overlay — red border around the recorded monitor.

Creates a transparent, click-through, always-on-top window that draws
a coloured border around the target monitor. Uses raw Win32 API via ctypes.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import threading

logger = logging.getLogger(__name__)

# ── Win32 constants ──────────────────────────────────────────────
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080  # hide from taskbar
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000

GWL_EXSTYLE = -20
LWA_COLORKEY = 0x00000001
LWA_ALPHA = 0x00000002

WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_PAINT = 0x000F
WM_QUIT = 0x0012
WM_TIMER = 0x0113

COLOR_KEY = 0x00FF00  # green will be transparent

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM)

# Fix DefWindowProcW signature for 64-bit Windows (lparam can exceed c_long range)
user32.DefWindowProcW.argtypes = [wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_longlong


# Python 3.14 removed WNDCLASS from ctypes.wintypes — define it manually
class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
    ]


# Python 3.14 removed PAINTSTRUCT from ctypes.wintypes — define it manually
class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wt.HDC),
        ("fErase", wt.BOOL),
        ("rcPaint", wt.RECT),
        ("fRestore", wt.BOOL),
        ("fIncUpdate", wt.BOOL),
        ("rgbReserved", ctypes.c_byte * 32),
    ]

BORDER_WIDTH = 6
BORDER_COLOR_RGB = (255, 40, 40)  # red
ANIMATION_TIMER_ID = 1
ANIMATION_INTERVAL_MS = 800  # blink interval


class RecordingOverlay:
    """Draws a pulsing red border around a monitor during recording.

    Runs in its own thread (Win32 message loop).
    """

    def __init__(self, monitor_index: int = 0) -> None:
        self._monitor_index = monitor_index
        self._thread: threading.Thread | None = None
        self._hwnd: int = 0
        self._visible = True
        self._running = False
        self._wndproc_ref = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="recording-overlay"
        )
        self._thread.start()
        logger.info("Recording overlay started (monitor %d)", self._monitor_index)

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._hwnd:
            # WM_CLOSE → DefWindowProcW calls DestroyWindow → WM_DESTROY
            # → PostQuitMessage(0) → GetMessageW returns 0
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        if self._thread:
            self._thread.join(timeout=3)
        self._hwnd = 0
        logger.info("Recording overlay stopped")

    def _get_monitor_rect(self) -> tuple[int, int, int, int]:
        """Get the bounding rect (x, y, w, h) of the target monitor."""
        import mss
        with mss.mss() as sct:
            monitors = sct.monitors
            idx = self._monitor_index + 1  # monitors[0] is virtual
            if idx >= len(monitors):
                idx = 1
            mon = monitors[idx]
            return mon["left"], mon["top"], mon["width"], mon["height"]

    def _run(self) -> None:
        """Create overlay window and run message loop."""
        mx, my, mw, mh = self._get_monitor_rect()

        # Register window class (unregister first in case previous run left it)
        class_name = "VisionFlowOverlay"
        h_instance = kernel32.GetModuleHandleW(None)

        wc = WNDCLASS()
        self._wndproc_ref = WNDPROC(self._wnd_proc)
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = h_instance
        wc.lpszClassName = class_name
        wc.hbrBackground = gdi32.CreateSolidBrush(COLOR_KEY)

        user32.UnregisterClassW(class_name, h_instance)  # cleanup stale registration
        atom = user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            logger.error("Failed to register overlay window class")
            return

        ex_style = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW
        style = WS_POPUP | WS_VISIBLE

        self._hwnd = user32.CreateWindowExW(
            ex_style, class_name, "VisionFlow Recording",
            style,
            mx, my, mw, mh,
            0, 0, wc.hInstance, 0,
        )

        if not self._hwnd:
            logger.error("Failed to create overlay window")
            return

        # Make green pixels transparent, keep border opaque
        user32.SetLayeredWindowAttributes(self._hwnd, COLOR_KEY, 0, LWA_COLORKEY)

        # Set up blink timer
        user32.SetTimer(self._hwnd, ANIMATION_TIMER_ID, ANIMATION_INTERVAL_MS, None)

        # Force initial paint
        user32.ShowWindow(self._hwnd, 5)  # SW_SHOW
        user32.UpdateWindow(self._hwnd)

        # Message loop
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Cleanup
        user32.KillTimer(self._hwnd, ANIMATION_TIMER_ID)
        user32.DestroyWindow(self._hwnd)
        user32.UnregisterClassW(class_name, wc.hInstance)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_PAINT:
            self._on_paint(hwnd)
            return 0
        if msg == WM_TIMER and wparam == ANIMATION_TIMER_ID:
            # Toggle visibility for pulsing effect
            self._visible = not self._visible
            user32.InvalidateRect(hwnd, None, True)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _on_paint(self, hwnd):
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        try:
            rect = wt.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            # Fill entire window with transparent color key
            brush_bg = gdi32.CreateSolidBrush(COLOR_KEY)
            _fill_rect(hdc, 0, 0, w, h, brush_bg)
            gdi32.DeleteObject(brush_bg)

            if self._visible:
                # Draw red border
                r, g, b = BORDER_COLOR_RGB
                color = r | (g << 8) | (b << 16)
                brush = gdi32.CreateSolidBrush(color)
                bw = BORDER_WIDTH

                _fill_rect(hdc, 0, 0, w, bw, brush)          # top
                _fill_rect(hdc, 0, h - bw, w, h, brush)      # bottom
                _fill_rect(hdc, 0, 0, bw, h, brush)           # left
                _fill_rect(hdc, w - bw, 0, w, h, brush)       # right

                gdi32.DeleteObject(brush)
        except Exception:
            logger.exception("Error during overlay paint")
        finally:
            user32.EndPaint(hwnd, ctypes.byref(ps))


def _fill_rect(hdc, left, top, right, bottom, brush):
    """Fill a rectangle area with the given brush."""
    rect = wt.RECT(left, top, right, bottom)
    user32.FillRect(hdc, ctypes.byref(rect), brush)

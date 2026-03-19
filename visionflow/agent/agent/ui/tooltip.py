"""Recording help tooltip — floating semi-transparent status bar.

Displays "🔴 REC  |  F9: 일시정지  |  F10: 중지" in the top-right corner
of the screen during recording.  Uses raw Win32 API via ctypes.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import threading

logger = logging.getLogger(__name__)

# ── Win32 constants ──────────────────────────────────────────────
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080  # hide from taskbar
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000

LWA_ALPHA = 0x00000002

WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_PAINT = 0x000F
WM_QUIT = 0x0012

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


# ── Layout constants ─────────────────────────────────────────────
TOOLTIP_WIDTH = 300
TOOLTIP_HEIGHT = 36
MARGIN = 20
BG_COLOR = 0x00302020  # dark background  (BGR: 0x20, 0x20, 0x30)
TEXT_COLOR = 0x00FFFFFF  # white text (BGR)
ALPHA = 220

TOOLTIP_TEXT = "\U0001f534 REC  |  F9: \uc77c\uc2dc\uc815\uc9c0  |  F10: \uc911\uc9c0"


class HelpTooltip:
    """Floating semi-transparent tooltip shown during recording.

    Runs in its own daemon thread with a Win32 message loop.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._hwnd: int = 0
        self._running = False
        self._wndproc_ref = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="help-tooltip"
        )
        self._thread.start()
        logger.info("Help tooltip started")

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        if self._thread:
            self._thread.join(timeout=3)
        self._hwnd = 0
        logger.info("Help tooltip stopped")

    def _run(self) -> None:
        """Create tooltip window and run message loop."""
        # Position: top-right corner of the primary monitor
        screen_w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        x = screen_w - TOOLTIP_WIDTH - MARGIN
        y = MARGIN

        # Register window class (unregister first in case previous run left it)
        class_name = "VisionFlowTooltip"
        h_instance = kernel32.GetModuleHandleW(None)

        wc = WNDCLASS()
        self._wndproc_ref = WNDPROC(self._wnd_proc)
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = h_instance
        wc.lpszClassName = class_name
        wc.hbrBackground = gdi32.CreateSolidBrush(BG_COLOR)

        user32.UnregisterClassW(class_name, h_instance)  # cleanup stale registration
        atom = user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            logger.error("Failed to register tooltip window class")
            return

        ex_style = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW
        style = WS_POPUP | WS_VISIBLE

        self._hwnd = user32.CreateWindowExW(
            ex_style, class_name, "VisionFlow Tooltip",
            style,
            x, y, TOOLTIP_WIDTH, TOOLTIP_HEIGHT,
            0, 0, wc.hInstance, 0,
        )

        if not self._hwnd:
            logger.error("Failed to create tooltip window")
            return

        # Set window alpha for semi-transparency
        user32.SetLayeredWindowAttributes(self._hwnd, 0, ALPHA, LWA_ALPHA)

        # Force initial paint
        user32.ShowWindow(self._hwnd, 5)  # SW_SHOW
        user32.UpdateWindow(self._hwnd)

        # Message loop
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Cleanup
        user32.DestroyWindow(self._hwnd)
        user32.UnregisterClassW(class_name, wc.hInstance)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_PAINT:
            self._on_paint(hwnd)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _on_paint(self, hwnd):
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))

        rect = wt.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))

        # Fill background
        bg_brush = gdi32.CreateSolidBrush(BG_COLOR)
        user32.FillRect(hdc, ctypes.byref(rect), bg_brush)
        gdi32.DeleteObject(bg_brush)

        # Set text properties
        gdi32.SetTextColor(hdc, TEXT_COLOR)
        gdi32.SetBkMode(hdc, 1)  # TRANSPARENT

        # Create font
        font = gdi32.CreateFontW(
            18,  # height
            0, 0, 0,
            400,  # weight (normal)
            0, 0, 0,  # italic, underline, strikeout
            1,  # DEFAULT_CHARSET
            0, 0, 0, 0,
            "Segoe UI",
        )
        old_font = gdi32.SelectObject(hdc, font)

        # Draw text centered in the rect
        # DT_CENTER = 1, DT_VCENTER = 4, DT_SINGLELINE = 32
        DT_CENTER = 0x0001
        DT_VCENTER = 0x0004
        DT_SINGLELINE = 0x0020
        user32.DrawTextW(
            hdc,
            TOOLTIP_TEXT,
            -1,
            ctypes.byref(rect),
            DT_CENTER | DT_VCENTER | DT_SINGLELINE,
        )

        # Cleanup GDI objects
        gdi32.SelectObject(hdc, old_font)
        gdi32.DeleteObject(font)

        user32.EndPaint(hwnd, ctypes.byref(ps))

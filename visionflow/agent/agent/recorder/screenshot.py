"""Screen capture with DPI-aware resolution detection."""

from __future__ import annotations

import ctypes
import io
import logging
from pathlib import Path

import mss
from PIL import Image

from shared.event_models import ScreenshotMeta

logger = logging.getLogger(__name__)

_cached_dpi_scale: float | None = None


def get_dpi_scale() -> float:
    """Get Windows DPI scaling factor via ctypes (cached after first call).

    DPI awareness is set once in main.py at startup — no need to call
    SetProcessDpiAwareness here.
    """
    global _cached_dpi_scale
    if _cached_dpi_scale is not None:
        return _cached_dpi_scale
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, hdc)
        _cached_dpi_scale = dpi / 96.0
    except Exception:
        _cached_dpi_scale = 1.0
    return _cached_dpi_scale


def capture_screen(
    monitor_index: int = 0,
    quality: int = 85,
    max_bytes: int = 4 * 1024 * 1024,
) -> tuple[bytes, ScreenshotMeta]:
    """Capture a single monitor, return JPEG bytes + metadata."""
    with mss.mss() as sct:
        monitors = sct.monitors
        # monitors[0] is the combined virtual screen; [1], [2]... are individual
        if monitor_index + 1 >= len(monitors):
            monitor_index = 0
        mon = monitors[monitor_index + 1]
        img = sct.grab(mon)

    pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
    dpi_scale = get_dpi_scale()
    meta = ScreenshotMeta(
        capture_width=pil_img.width,
        capture_height=pil_img.height,
        dpi_scale=dpi_scale,
        monitor_index=monitor_index,
    )

    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=quality)

    # Resize only if exceeding max_bytes (PRD: 4MB threshold)
    if buf.tell() > max_bytes:
        ratio = (max_bytes / buf.tell()) ** 0.5
        new_size = (int(pil_img.width * ratio), int(pil_img.height * ratio))
        pil_img = pil_img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=quality)
        meta.capture_width = pil_img.width
        meta.capture_height = pil_img.height

    return buf.getvalue(), meta


def save_screenshot(
    data: bytes,
    directory: Path,
    filename: str,
) -> str:
    """Save screenshot bytes to directory, return relative path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_bytes(data)
    return str(path)


def crop_around_click(
    full_screenshot_bytes: bytes,
    click_x: int,
    click_y: int,
    crop_size: int = 200,
    quality: int = 85,
) -> bytes:
    """Crop a region around the click point from a full screenshot JPEG.

    Returns JPEG bytes of the cropped region.
    """
    img = Image.open(io.BytesIO(full_screenshot_bytes))

    half = crop_size // 2
    left = max(0, click_x - half)
    top = max(0, click_y - half)
    right = min(img.width, click_x + half)
    bottom = min(img.height, click_y + half)

    cropped = img.crop((left, top, right, bottom))

    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()

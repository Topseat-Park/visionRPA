"""OpenCV template matching — find a crop image on the current screen.

Used as a fast, free fallback before Gemini AI vision and before raw coordinates.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Minimum confidence to accept a match
DEFAULT_THRESHOLD = 0.7


def match_template_on_screen(
    screenshot_bytes: bytes,
    crop_path: str,
    threshold: float = DEFAULT_THRESHOLD,
) -> tuple[int, int, float] | None:
    """Find crop image location on the current screenshot.

    Args:
        screenshot_bytes: Full-screen JPEG bytes.
        crop_path: Absolute path to the crop image (JPEG).
        threshold: Minimum confidence (0.0~1.0).

    Returns:
        (center_x, center_y, confidence) if found above threshold, else None.
    """
    crop_file = Path(crop_path)
    if not crop_file.exists():
        logger.warning("Crop image not found: %s", crop_path)
        return None

    # Decode images
    screen_arr = np.frombuffer(screenshot_bytes, dtype=np.uint8)
    screen_img = cv2.imdecode(screen_arr, cv2.IMREAD_GRAYSCALE)
    if screen_img is None:
        logger.warning("Failed to decode screenshot")
        return None

    crop_bytes = crop_file.read_bytes()
    crop_arr = np.frombuffer(crop_bytes, dtype=np.uint8)
    crop_img = cv2.imdecode(crop_arr, cv2.IMREAD_GRAYSCALE)
    if crop_img is None:
        logger.warning("Failed to decode crop image: %s", crop_path)
        return None

    # Crop must be smaller than screen
    if crop_img.shape[0] > screen_img.shape[0] or crop_img.shape[1] > screen_img.shape[1]:
        logger.warning("Crop image larger than screen — skipping template match")
        return None

    # Template matching
    result = cv2.matchTemplate(screen_img, crop_img, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val < threshold:
        logger.debug("Template match confidence %.3f < threshold %.3f", max_val, threshold)
        return None

    # max_loc is top-left corner; convert to center
    h, w = crop_img.shape[:2]
    center_x = max_loc[0] + w // 2
    center_y = max_loc[1] + h // 2

    logger.info(
        "Template match found at (%d, %d) confidence=%.3f",
        center_x, center_y, max_val,
    )
    return center_x, center_y, max_val

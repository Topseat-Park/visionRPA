"""Gemini client — singleton wrapper for google-genai SDK."""

from __future__ import annotations

import logging
from functools import lru_cache

from google import genai
from google.genai import types

from ..config import get_config

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_gemini_client() -> genai.Client:
    """Return a configured Gemini client (cached singleton)."""
    cfg = get_config()
    client = genai.Client(
        vertexai=True,
        project=cfg.gemini_project,
        location=cfg.gemini_region,
    )
    logger.info("Gemini client initialised: project=%s region=%s", cfg.gemini_project, cfg.gemini_region)
    return client


MODEL = "gemini-3.0-flash"

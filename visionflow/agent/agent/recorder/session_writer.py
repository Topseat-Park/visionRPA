"""Writes recording session data to disk."""

from __future__ import annotations

import json
from pathlib import Path

from shared.event_models import RecordEvent, SessionMeta

from ..storage.local import append_jsonl, write_json_atomic
from ..storage.paths import DataPaths


class SessionWriter:
    """Manages writing events, screenshots, and metadata for a recording session."""

    def __init__(self, paths: DataPaths, session_id: str) -> None:
        self._paths = paths
        self.session_id = session_id
        self._session_dir = paths.session_dir(session_id)
        self._screenshots_dir = paths.session_screenshots(session_id)
        self._events_file = paths.session_events(session_id)
        self._meta_file = paths.session_meta(session_id)

    def ensure_dirs(self) -> None:
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._screenshots_dir.mkdir(parents=True, exist_ok=True)

    def write_meta(self, meta: SessionMeta) -> None:
        write_json_atomic(self._meta_file, meta.model_dump(mode="json"))

    def write_meta_dict(self, meta_dict: dict) -> None:
        """Write meta from a plain dict (allows extra fields like open_windows)."""
        write_json_atomic(self._meta_file, meta_dict)

    def append_event(self, event_dict: dict) -> None:
        append_jsonl(self._events_file, event_dict)

    def save_screenshot(self, data: bytes, filename: str) -> str:
        """Save screenshot, return absolute path string."""
        path = self._screenshots_dir / filename
        path.write_bytes(data)
        return str(path)

    @property
    def screenshots_dir(self) -> Path:
        return self._screenshots_dir

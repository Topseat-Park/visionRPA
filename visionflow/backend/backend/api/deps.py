"""Shared dependencies for API routes."""

from __future__ import annotations

from functools import lru_cache

from ..config import get_config
from ..ipc.file_transport import BackendFileTransport
from ..storage.local import LocalStorage


@lru_cache
def get_storage() -> LocalStorage:
    config = get_config()
    return LocalStorage(config.data_dir)


@lru_cache
def get_transport() -> BackendFileTransport:
    config = get_config()
    control_dir = config.data_dir / "control"
    return BackendFileTransport(control_dir)

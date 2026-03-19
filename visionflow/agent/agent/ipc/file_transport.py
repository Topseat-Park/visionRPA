"""File-based IPC transport (PoC) — polls command.json, writes status.json."""

from __future__ import annotations

import logging

from shared.ipc_models import AgentCommand, AgentStatus

from ..storage.local import read_json_safe, write_json_atomic
from ..storage.paths import DataPaths
from .base import ABCTransport

logger = logging.getLogger(__name__)


class FileTransport(ABCTransport):
    def __init__(self, paths: DataPaths) -> None:
        self._paths = paths
        # Read existing command id on startup to avoid re-executing stale commands
        self._last_command_id: str | None = self._read_current_command_id()

    def _read_current_command_id(self) -> str | None:
        """Read the current command.json id so we skip it on startup."""
        data = read_json_safe(self._paths.command_file)
        if data and isinstance(data, dict):
            return data.get("id")
        return None

    def poll_command(self) -> AgentCommand | None:
        """Read command.json — return command only if id is new."""
        data = read_json_safe(self._paths.command_file)
        if data is None:
            return None
        try:
            cmd = AgentCommand.model_validate(data)
        except Exception:
            logger.warning("Invalid command.json, ignoring")
            return None
        if cmd.id == self._last_command_id:
            return None  # already processed
        self._last_command_id = cmd.id
        return cmd

    def update_status(self, status: AgentStatus) -> None:
        """Write status.json atomically."""
        write_json_atomic(
            self._paths.status_file,
            status.model_dump(mode="json"),
        )

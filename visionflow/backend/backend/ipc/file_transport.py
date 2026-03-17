"""File-based IPC transport — backend side (writes commands, reads status)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from shared.ipc_models import AgentCommand, AgentStatus


class BackendFileTransport:
    """Backend-side file IPC: send commands, read status."""

    def __init__(self, control_dir: Path) -> None:
        self._control_dir = control_dir
        self._command_file = control_dir / "command.json"
        self._status_file = control_dir / "status.json"
        self._control_dir.mkdir(parents=True, exist_ok=True)

    def send_command(self, command: AgentCommand) -> None:
        """Write command.json atomically."""
        data = command.model_dump(mode="json")
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self._control_dir, suffix=".tmp"
        )
        try:
            with open(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)
            Path(tmp_path).replace(self._command_file)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def read_status(self) -> AgentStatus | None:
        """Read status.json, return None on any error."""
        try:
            content = self._status_file.read_text(encoding="utf-8")
            data = json.loads(content)
            return AgentStatus.model_validate(data)
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            return None

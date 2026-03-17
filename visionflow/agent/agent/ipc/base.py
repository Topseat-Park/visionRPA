"""Abstract transport interface for Agent ↔ Dashboard communication."""

from __future__ import annotations

from abc import ABC, abstractmethod

from shared.ipc_models import AgentCommand, AgentStatus


class ABCTransport(ABC):
    """Transport abstraction — file-based (PoC) or WebSocket (future)."""

    @abstractmethod
    def poll_command(self) -> AgentCommand | None:
        """Check for a new command. Returns None if no new command."""
        ...

    @abstractmethod
    def update_status(self, status: AgentStatus) -> None:
        """Publish current agent status."""
        ...

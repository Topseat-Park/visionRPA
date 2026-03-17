"""Agent command/status schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from shared.enums import AgentState, CommandType


class AgentCommandRequest(BaseModel):
    type: CommandType
    payload: dict[str, Any] = {}


class AgentStatusResponse(BaseModel):
    agent_state: AgentState = AgentState.OFFLINE
    last_command_id: str | None = None
    recording_session_id: str | None = None
    recording_event_count: int = 0
    recording_elapsed: float = 0
    error: str | None = None

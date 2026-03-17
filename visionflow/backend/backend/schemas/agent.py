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
    replay_run_id: str | None = None
    replay_workflow_id: str | None = None
    replay_current_step: int = 0
    replay_total_steps: int = 0
    replay_step_description: str | None = None
    error: str | None = None

"""IPC message models — Agent ↔ Dashboard communication."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .enums import AgentState, CommandType


class AgentCommand(BaseModel):
    """Dashboard → Agent command (written to command.json)."""

    id: str = Field(description="Unique command ID, e.g. cmd_20260317_143025_a1b2")
    timestamp: datetime
    type: CommandType
    payload: dict[str, Any] = Field(default_factory=dict)


class RecordingDetails(BaseModel):
    """Status details during recording."""

    session_id: str
    event_count: int = 0
    elapsed_seconds: float = 0
    last_event_type: str | None = None


class ReplayDetails(BaseModel):
    """Status details during replay."""

    run_id: str
    workflow_id: str
    current_step: int = 0
    total_steps: int = 0
    step_description: str | None = None


class HitlRequest(BaseModel):
    """Human-in-the-Loop request from Agent."""

    step_id: int
    screenshot_path: str
    predicted_x: int
    predicted_y: int
    target_description: str
    confidence: float | None = None


class SystemInfo(BaseModel):
    """Agent system metrics."""

    cpu_percent: float = 0
    memory_mb: float = 0
    active_window: str | None = None


class AgentStatus(BaseModel):
    """Agent → Dashboard status (written to status.json)."""

    timestamp: datetime
    agent_state: AgentState = AgentState.ONLINE
    last_command_id: str | None = None
    last_command_ack: bool = True
    recording: RecordingDetails | None = None
    replay: ReplayDetails | None = None
    hitl_request: HitlRequest | None = None
    system: SystemInfo = Field(default_factory=SystemInfo)
    error: str | None = None

"""Session request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    purpose: str = Field(description="Workflow purpose (required)")
    apps: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    exception_notes: str | None = None
    has_sensitive_info: bool = False


class SessionResponse(BaseModel):
    session_id: str
    created_at: datetime
    purpose: str
    apps: list[str]
    event_count: int = 0
    status: str = "created"


class SessionEventResponse(BaseModel):
    events: list[dict]
    total: int

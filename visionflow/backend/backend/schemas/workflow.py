"""Workflow request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from shared.enums import SpeedMode
from shared.step_models import Workflow, WorkflowStep, WorkflowSummary


class WorkflowListItem(BaseModel):
    workflow_id: str
    name: str
    description: str
    version: int
    last_successful_version: int | None = None
    step_count: int = 0
    last_run_at: str | None = None
    success_rate: float | None = None


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowListItem]
    total: int


class GenerateWorkflowRequest(BaseModel):
    session_id: str


class UpdateWorkflowRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    default_speed: SpeedMode | None = None
    steps: list[WorkflowStep] | None = None

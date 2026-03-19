"""Workflow step models — 8 step types for replay."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import OnFailure, SpeedMode, StepType


class WorkflowStep(BaseModel):
    """A single step in a workflow."""

    id: int
    type: StepType
    description: str = Field(description="Human-readable step description")
    value: str | None = Field(None, description="Execution value (cmd, text, hotkey, URL)")
    target_description: str | None = Field(
        None, description="UI element description (vision_click only)"
    )
    hint: str | None = Field(None, description="Element detection hint")
    wait_condition: str | None = Field(
        None, description="Condition to proceed to next step"
    )
    timeout_sec: int = 10
    speed: SpeedMode = SpeedMode.NORMAL
    on_failure: OnFailure = OnFailure.HUMAN
    screenshot_ref: str | None = None
    fallback_coords: dict[str, int] | None = Field(
        None, description="Fallback pixel coordinates {x, y} from original recording (vision_click)"
    )
    crop_ref: str | None = Field(
        None, description="Path to crop image around click point (for OpenCV template matching)"
    )


class Workflow(BaseModel):
    """Complete workflow definition."""

    workflow_id: str
    name: str
    description: str
    version: int = 1
    last_successful_version: int | None = None
    default_speed: SpeedMode = SpeedMode.NORMAL
    steps: list[WorkflowStep] = Field(default_factory=list)


class WorkflowSummary(BaseModel):
    """AI-generated summary report after workflow creation."""

    flow_summary: str = Field(description="One-line flow summary")
    attention_steps: list[str] = Field(
        default_factory=list,
        description="Steps requiring attention (vision_click, complex conditions)",
    )
    improvement_suggestions: list[str] = Field(
        default_factory=list, description="Steps that could be improved (e.g. cmd alternative)"
    )
    recommended_first_run: str = Field(
        "dryrun", description="Recommended first run mode"
    )
    estimated_duration_sec: int | None = None


class WorkflowVersionInfo(BaseModel):
    """Version metadata for a workflow."""

    version: int
    success_count: int = 0
    last_success_run_id: str | None = None
    is_last_successful: bool = False

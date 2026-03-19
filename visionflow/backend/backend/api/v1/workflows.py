"""Workflow API — CRUD + version management."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException

from shared.step_models import Workflow, WorkflowSummary

from ...config import get_config
from ...schemas.workflow import (
    GenerateWorkflowRequest,
    GenerateWorkflowResponse,
    UpdateWorkflowRequest,
    WorkflowListItem,
    WorkflowListResponse,
)
from ...storage.local import LocalStorage
from ..deps import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    storage: LocalStorage = Depends(get_storage),
) -> WorkflowListResponse:
    wf_ids = await storage.list_dir("workflows")
    items = []
    for wid in wf_ids:
        latest = await storage.read_json(f"workflows/{wid}/latest.json")
        if latest:
            items.append(
                WorkflowListItem(
                    workflow_id=latest.get("workflow_id", wid),
                    name=latest.get("name", ""),
                    description=latest.get("description", ""),
                    version=latest.get("version", 1),
                    last_successful_version=latest.get("last_successful_version"),
                    step_count=len(latest.get("steps", [])),
                )
            )
    return WorkflowListResponse(workflows=items, total=len(items))


@router.post("/generate", response_model=GenerateWorkflowResponse)
async def generate_workflow(
    req: GenerateWorkflowRequest,
    storage: LocalStorage = Depends(get_storage),
) -> GenerateWorkflowResponse:
    """Convert recorded events from a session into a workflow (AI or rule-based)."""
    meta = await storage.read_json(f"sessions/{req.session_id}/meta.json")
    if meta is None:
        raise HTTPException(404, "Session not found")

    # Prevent duplicate generation
    if meta.get("status") == "converted":
        raise HTTPException(409, f"Session already converted to workflow '{meta.get('workflow_id', '')}'")

    events = await storage.read_jsonl(f"sessions/{req.session_id}/events.jsonl")

    # Apply preprocessing (compress duplicates, merge scrolls)
    from ...recorder_utils import preprocess_events
    events = preprocess_events(events)

    # Reject empty sessions
    if not events:
        raise HTTPException(400, "Session has no recorded events")

    cfg = get_config()
    use_ai = req.use_ai and bool(cfg.gemini_project)
    generation_method = "rule_based"
    steps = None
    summary_data = None

    # AI generation with fallback
    if use_ai:
        from ...gemini.workflow_generator import generate_summary, generate_workflow_steps

        purpose = meta.get("purpose", "")
        apps = meta.get("apps", [])
        exceptions = meta.get("exceptions")
        screenshots_dir = storage.resolve_path(f"sessions/{req.session_id}/screenshots")

        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                steps = await generate_workflow_steps(
                    events, screenshots_dir, purpose, apps, exceptions,
                )
                generation_method = "ai"
                logger.info("AI workflow generation succeeded (attempt %d)", attempt)
                break
            except Exception:
                logger.warning("AI generation attempt %d failed", attempt, exc_info=True)
                if attempt == max_retries:
                    logger.info("Falling back to rule-based generation")

    # Fallback to rule-based
    if steps is None:
        try:
            steps = _events_to_steps(events)
        except Exception as e:
            raise HTTPException(500, f"Failed to convert events to steps: {e}")

    workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
    wf = Workflow(
        workflow_id=workflow_id,
        name=meta.get("purpose") or "Untitled Workflow",
        description=f"Generated from session {req.session_id}",
        version=1,
        steps=steps,
    )
    wf_data = wf.model_dump(mode="json")
    await storage.write_json(f"workflows/{workflow_id}/v1.json", wf_data)
    await storage.write_json(f"workflows/{workflow_id}/latest.json", wf_data)

    # Generate summary (AI only)
    if generation_method == "ai":
        try:
            from ...gemini.workflow_generator import generate_summary

            purpose = meta.get("purpose", "")
            step_dicts = [s.model_dump(mode="json") if hasattr(s, "model_dump") else s for s in steps]
            summary_data = await generate_summary(step_dicts, purpose)
            await storage.write_json(f"workflows/{workflow_id}/summary.json", summary_data)
            logger.info("Workflow summary generated and saved")
        except Exception:
            logger.warning("Summary generation failed", exc_info=True)

    # Mark session as converted
    meta["status"] = "converted"
    meta["workflow_id"] = workflow_id
    await storage.write_json(f"sessions/{req.session_id}/meta.json", meta)

    summary = WorkflowSummary.model_validate(summary_data) if summary_data else None
    return GenerateWorkflowResponse(
        workflow=wf,
        summary=summary,
        generation_method=generation_method,
    )


def _events_to_steps(events: list[dict]) -> list:
    """Convert raw events to workflow steps (rule-based, no AI)."""
    from shared.enums import OnFailure, SpeedMode, StepType
    from shared.step_models import WorkflowStep

    steps = []
    step_id = 1
    for ev in events:
        ev_type = ev.get("event_type")
        step: WorkflowStep | None = None

        if ev_type == "click":
            step = WorkflowStep(
                id=step_id,
                type=StepType.VISION_CLICK,
                description=f"Click at ({ev['x']}, {ev['y']})",
                value=f"{ev['x']},{ev['y']}",
                target_description=f"Element at ({ev['x']}, {ev['y']})",
                screenshot_ref=ev.get("screenshot_path"),
                crop_ref=ev.get("crop_path"),
                fallback_coords={"x": ev["x"], "y": ev["y"]},
                timeout_sec=10,
                speed=SpeedMode.NORMAL,
                on_failure=OnFailure.HUMAN,
            )
        elif ev_type == "double_click":
            step = WorkflowStep(
                id=step_id,
                type=StepType.VISION_CLICK,
                description=f"Double-click at ({ev['x']}, {ev['y']})",
                value=f"double:{ev['x']},{ev['y']}",
                target_description=f"Element at ({ev['x']}, {ev['y']})",
                screenshot_ref=ev.get("screenshot_path"),
                crop_ref=ev.get("crop_path"),
                fallback_coords={"x": ev["x"], "y": ev["y"]},
                timeout_sec=10,
                speed=SpeedMode.NORMAL,
                on_failure=OnFailure.HUMAN,
            )
        elif ev_type == "type":
            text = ev.get("text", "")
            step = WorkflowStep(
                id=step_id,
                type=StepType.CLIPBOARD_PASTE,
                description=f"Type: {text[:40]}{'...' if len(text) > 40 else ''}",
                value=text,
                timeout_sec=10,
                speed=SpeedMode.NORMAL,
                on_failure=OnFailure.HUMAN,
            )
        elif ev_type == "key":
            keys = ev.get("keys", [])
            combo = "+".join(keys)
            step = WorkflowStep(
                id=step_id,
                type=StepType.HOTKEY,
                description=f"Press {combo}",
                value=combo,
                timeout_sec=10,
                speed=SpeedMode.NORMAL,
                on_failure=OnFailure.HUMAN,
            )
        elif ev_type == "scroll":
            step = WorkflowStep(
                id=step_id,
                type=StepType.SCROLL,
                description=f"Scroll {ev.get('direction', 'down')} at ({ev.get('x', 0)}, {ev.get('y', 0)})",
                value=f"{ev.get('x', 0)},{ev.get('y', 0)},{ev.get('direction', 'down')},{ev.get('amount', 1)}",
                timeout_sec=10,
                speed=SpeedMode.NORMAL,
                on_failure=OnFailure.HUMAN,
            )
        elif ev_type == "drag":
            step = WorkflowStep(
                id=step_id,
                type=StepType.DRAG,
                description=f"Drag from ({ev.get('start_x', 0)}, {ev.get('start_y', 0)}) to ({ev.get('end_x', 0)}, {ev.get('end_y', 0)})",
                value=f"{ev.get('start_x', 0)},{ev.get('start_y', 0)},{ev.get('end_x', 0)},{ev.get('end_y', 0)}",
                timeout_sec=10,
                speed=SpeedMode.NORMAL,
                on_failure=OnFailure.HUMAN,
            )
        elif ev_type == "app_launch":
            step = WorkflowStep(
                id=step_id,
                type=StepType.CMD,
                description=f"Launch {ev.get('app_name', 'app')}",
                value=ev.get("app_path") or ev.get("app_name", ""),
                timeout_sec=30,
                speed=SpeedMode.NORMAL,
                on_failure=OnFailure.HUMAN,
            )
        elif ev_type == "window_change":
            window_title = ev.get("window_title", "")
            step = WorkflowStep(
                id=step_id,
                type=StepType.FOCUS_WINDOW,
                description=f"창 활성화: {window_title}",
                value=window_title,
                timeout_sec=10,
                speed=SpeedMode.NORMAL,
                on_failure=OnFailure.RETRY,
            )

        if step:
            steps.append(step)
            step_id += 1

    return steps


@router.get("/{workflow_id}", response_model=Workflow)
async def get_workflow(
    workflow_id: str,
    storage: LocalStorage = Depends(get_storage),
) -> Workflow:
    data = await storage.read_json(f"workflows/{workflow_id}/latest.json")
    if data is None:
        raise HTTPException(404, "Workflow not found")
    return Workflow.model_validate(data)


@router.get("/{workflow_id}/versions")
async def list_versions(
    workflow_id: str,
    storage: LocalStorage = Depends(get_storage),
) -> list[dict]:
    files = await storage.list_dir(f"workflows/{workflow_id}")
    versions = []
    for f in files:
        if f.startswith("v") and f.endswith(".json"):
            data = await storage.read_json(f"workflows/{workflow_id}/{f}")
            if data:
                versions.append({
                    "version": data.get("version"),
                    "step_count": len(data.get("steps", [])),
                })
    return versions


@router.put("/{workflow_id}", response_model=Workflow)
async def update_workflow(
    workflow_id: str,
    req: UpdateWorkflowRequest,
    storage: LocalStorage = Depends(get_storage),
) -> Workflow:
    """Update workflow — creates a new version."""
    current = await storage.read_json(f"workflows/{workflow_id}/latest.json")
    if current is None:
        raise HTTPException(404, "Workflow not found")

    wf = Workflow.model_validate(current)
    new_version = wf.version + 1

    if req.name is not None:
        wf.name = req.name
    if req.description is not None:
        wf.description = req.description
    if req.default_speed is not None:
        wf.default_speed = req.default_speed
    if req.steps is not None:
        wf.steps = req.steps

    wf.version = new_version
    wf_data = wf.model_dump(mode="json")

    # Save versioned + latest
    await storage.write_json(f"workflows/{workflow_id}/v{new_version}.json", wf_data)
    await storage.write_json(f"workflows/{workflow_id}/latest.json", wf_data)

    return wf


@router.get("/{workflow_id}/summary", response_model=WorkflowSummary)
async def get_workflow_summary(
    workflow_id: str,
    storage: LocalStorage = Depends(get_storage),
) -> WorkflowSummary:
    """Return the AI-generated summary for a workflow."""
    data = await storage.read_json(f"workflows/{workflow_id}/summary.json")
    if data is None:
        raise HTTPException(404, "Summary not found")
    return WorkflowSummary.model_validate(data)


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    storage: LocalStorage = Depends(get_storage),
) -> dict:
    if not await storage.exists(f"workflows/{workflow_id}"):
        raise HTTPException(404, "Workflow not found")
    await storage.delete(f"workflows/{workflow_id}")
    return {"ok": True}

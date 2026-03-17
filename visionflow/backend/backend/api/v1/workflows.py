"""Workflow API — CRUD + version management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from shared.step_models import Workflow, WorkflowSummary

from ...schemas.workflow import (
    GenerateWorkflowRequest,
    UpdateWorkflowRequest,
    WorkflowListItem,
    WorkflowListResponse,
)
from ...storage.local import LocalStorage
from ..deps import get_storage

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


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    storage: LocalStorage = Depends(get_storage),
) -> dict:
    if not await storage.exists(f"workflows/{workflow_id}"):
        raise HTTPException(404, "Workflow not found")
    await storage.delete(f"workflows/{workflow_id}")
    return {"ok": True}

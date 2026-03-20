"""Run execution API — create, monitor, abort, history, HITL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from shared.ipc_models import AgentCommand

from ...ipc.file_transport import BackendFileTransport
from ...storage.local import LocalStorage
from ..deps import get_storage, get_transport

router = APIRouter(prefix="/runs", tags=["runs"])


# ── Request bodies ────────────────────────────────────────────

class HitlResponseBody(BaseModel):
    action: str  # "approve" | "modify" | "cancel"
    modified_x: int | None = None
    modified_y: int | None = None


# ── Endpoints ─────────────────────────────────────────────────

@router.post("")
async def create_run(
    workflow_id: str,
    mode: str = "normal",
    step_index: int | None = None,
    storage: LocalStorage = Depends(get_storage),
    transport: BackendFileTransport = Depends(get_transport),
) -> dict:
    """Create a run and tell Agent to start replaying the workflow."""
    # Verify workflow exists
    wf = await storage.read_json(f"workflows/{workflow_id}/latest.json")
    if wf is None:
        raise HTTPException(404, "Workflow not found")

    run_id = f"run_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    if mode == "computer_use":
        total_steps = 0  # Unknown upfront for computer_use
    elif mode == "test_step" and step_index:
        total_steps = 1
    else:
        total_steps = len(wf.get("steps", []))
    meta = {
        "run_id": run_id,
        "workflow_id": workflow_id,
        "workflow_name": wf.get("name", ""),
        "status": "pending",
        "started_at": now.isoformat(),
        "finished_at": None,
        "current_step": 0,
        "total_steps": total_steps,
        "error": None,
        "mode": mode,
    }
    if step_index is not None:
        meta["step_index"] = step_index

    await storage.write_json(f"runs/{run_id}/meta.json", meta)

    # Send command to agent
    payload: dict = {"run_id": run_id, "workflow_id": workflow_id, "mode": mode}
    if step_index is not None:
        payload["step_index"] = step_index

    cmd = AgentCommand(
        id=f"cmd_{uuid.uuid4().hex[:12]}",
        timestamp=now,
        type="start_run",  # type: ignore[arg-type]
        payload=payload,
    )
    transport.send_command(cmd)

    return meta


@router.post("/{run_id}/abort")
async def abort_run(
    run_id: str,
    storage: LocalStorage = Depends(get_storage),
    transport: BackendFileTransport = Depends(get_transport),
) -> dict:
    meta = await storage.read_json(f"runs/{run_id}/meta.json")
    if meta is None:
        raise HTTPException(404, "Run not found")

    cmd = AgentCommand(
        id=f"cmd_{uuid.uuid4().hex[:12]}",
        timestamp=datetime.now(timezone.utc),
        type="abort_run",  # type: ignore[arg-type]
        payload={"run_id": run_id},
    )
    transport.send_command(cmd)
    return {"ok": True}


# ── HITL endpoints ────────────────────────────────────────────

@router.get("/{run_id}/hitl")
async def get_hitl_request(
    run_id: str,
    storage: LocalStorage = Depends(get_storage),
) -> dict:
    """Check if there is a pending HITL request for this run."""
    request = await storage.read_json(f"runs/{run_id}/hitl_request.json")
    if request is None:
        return {"pending": False}
    return {"pending": True, **request}


@router.post("/{run_id}/hitl")
async def respond_hitl(
    run_id: str,
    body: HitlResponseBody,
    storage: LocalStorage = Depends(get_storage),
) -> dict:
    """Submit a HITL response (approve/modify/cancel)."""
    # Verify run exists
    meta = await storage.read_json(f"runs/{run_id}/meta.json")
    if meta is None:
        raise HTTPException(404, "Run not found")

    response = {
        "action": body.action,
        "responded_at": datetime.now(timezone.utc).isoformat(),
    }
    if body.action == "modify":
        response["modified_x"] = body.modified_x
        response["modified_y"] = body.modified_y

    await storage.write_json(f"runs/{run_id}/hitl_response.json", response)
    return {"ok": True}


# ── Convert CU run to workflow ────────────────────────────────

@router.post("/{run_id}/convert-to-workflow")
async def convert_to_workflow(
    run_id: str,
    storage: LocalStorage = Depends(get_storage),
) -> dict:
    """Convert a completed Computer Use run into a deterministic workflow."""
    meta = await storage.read_json(f"runs/{run_id}/meta.json")
    if meta is None:
        raise HTTPException(404, "Run not found")
    if meta.get("mode") != "computer_use":
        raise HTTPException(400, "Only computer_use runs can be converted")
    if meta.get("status") != "completed":
        raise HTTPException(400, "Run must be completed to convert")

    cu_result = await storage.read_json(f"runs/{run_id}/computer_use_result.json")
    if not cu_result:
        raise HTTPException(404, "Computer Use result not found")

    actions_log = cu_result.get("actions", [])
    if not actions_log:
        raise HTTPException(400, "No actions to convert")

    goal = meta.get("workflow_name", "") or "자동 생성 워크플로우"

    from ...gemini.reverse_generator import generate_reverse_workflow

    turns_dir = storage._base / "runs" / run_id / "turns"
    steps = await generate_reverse_workflow(
        actions_log=actions_log,
        goal=goal,
        screenshots_dir=turns_dir if turns_dir.exists() else None,
    )

    # Create new workflow
    workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    workflow = {
        "workflow_id": workflow_id,
        "name": f"{goal} (CU 변환)",
        "description": f"Computer Use 실행 결과에서 자동 변환됨 (run: {run_id})",
        "version": 1,
        "default_speed": "normal",
        "steps": steps,
        "created_at": now.isoformat(),
        "source_run_id": run_id,
    }

    await storage.write_json(f"workflows/{workflow_id}/v1.json", workflow)
    await storage.write_json(f"workflows/{workflow_id}/latest.json", workflow)

    return {"workflow_id": workflow_id, "step_count": len(steps)}


# ── Turn screenshots (Computer Use) ──────────────────────────

@router.get("/{run_id}/turns/{filename}")
async def get_turn_screenshot(
    run_id: str,
    filename: str,
    storage: LocalStorage = Depends(get_storage),
) -> FileResponse:
    """Serve a Computer Use turn screenshot."""
    file_path = storage._base / "runs" / run_id / "turns" / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "Turn screenshot not found")
    return FileResponse(file_path, media_type="image/jpeg")


# ── Step screenshots ─────────────────────────────────────────

@router.get("/{run_id}/steps/{filename}")
async def get_step_screenshot(
    run_id: str,
    filename: str,
    storage: LocalStorage = Depends(get_storage),
) -> FileResponse:
    """Serve a step screenshot (before/after)."""
    file_path = storage._base / "runs" / run_id / "steps" / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "Step screenshot not found")
    return FileResponse(file_path, media_type="image/jpeg")


# ── List / Get ────────────────────────────────────────────────

@router.get("")
async def list_runs(
    workflow_id: str | None = None,
    status: str | None = None,
    storage: LocalStorage = Depends(get_storage),
) -> list[dict]:
    run_ids = await storage.list_dir("runs")
    runs = []
    for rid in run_ids:
        meta = await storage.read_json(f"runs/{rid}/meta.json")
        if meta is None:
            continue
        if workflow_id and meta.get("workflow_id") != workflow_id:
            continue
        if status and meta.get("status") != status:
            continue
        # Include brief verification status
        verification = await storage.read_json(f"runs/{rid}/verification.json")
        if verification:
            meta["verification"] = {"success": verification.get("success")}
        runs.append(meta)
    return sorted(runs, key=lambda r: r.get("started_at", ""), reverse=True)


@router.get("/{run_id}")
async def get_run(
    run_id: str,
    storage: LocalStorage = Depends(get_storage),
) -> dict:
    meta = await storage.read_json(f"runs/{run_id}/meta.json")
    if meta is None:
        raise HTTPException(404, "Run not found")

    # Merge verification data
    verification = await storage.read_json(f"runs/{run_id}/verification.json")
    if verification:
        meta["verification"] = verification

    # Merge diagnosis data
    diagnosis = await storage.read_json(f"runs/{run_id}/diagnosis.json")
    if diagnosis:
        meta["diagnosis"] = diagnosis

    # Collect dry-run results if mode is dryrun
    if meta.get("mode") == "dryrun":
        dryrun_results = []
        steps_entries = await storage.list_dir(f"runs/{run_id}/steps")
        for entry in steps_entries:
            if entry.endswith("_dryrun.json"):
                dr = await storage.read_json(f"runs/{run_id}/steps/{entry}")
                if dr:
                    dryrun_results.append(dr)
        if dryrun_results:
            dryrun_results.sort(key=lambda r: r.get("step_index", 0))
            meta["dryrun_results"] = dryrun_results

    # Include HITL request if pending
    hitl_req = await storage.read_json(f"runs/{run_id}/hitl_request.json")
    if hitl_req:
        meta["hitl_request"] = hitl_req

    # Include Computer Use result if available
    if meta.get("mode") == "computer_use":
        cu_result = await storage.read_json(f"runs/{run_id}/computer_use_result.json")
        if cu_result:
            meta["computer_use_turns"] = cu_result.get("actions", [])
            meta["computer_use_result"] = {
                "success": cu_result.get("success"),
                "turns_used": cu_result.get("turns_used"),
                "final_message": cu_result.get("final_message"),
                "error": cu_result.get("error"),
            }

    return meta

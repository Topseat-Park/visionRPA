"""Run execution API — create, monitor, abort, history."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from shared.ipc_models import AgentCommand

from ...ipc.file_transport import BackendFileTransport
from ...storage.local import LocalStorage
from ..deps import get_storage, get_transport

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("")
async def create_run(
    workflow_id: str,
    mode: str = "normal",
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

    meta = {
        "run_id": run_id,
        "workflow_id": workflow_id,
        "workflow_name": wf.get("name", ""),
        "status": "pending",
        "started_at": now.isoformat(),
        "finished_at": None,
        "current_step": 0,
        "total_steps": len(wf.get("steps", [])),
        "error": None,
        "mode": mode,
    }
    await storage.write_json(f"runs/{run_id}/meta.json", meta)

    # Send command to agent
    cmd = AgentCommand(
        id=f"cmd_{uuid.uuid4().hex[:12]}",
        timestamp=now,
        type="start_run",  # type: ignore[arg-type]
        payload={"run_id": run_id, "workflow_id": workflow_id, "mode": mode},
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

    return meta

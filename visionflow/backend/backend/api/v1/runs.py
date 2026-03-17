"""Run execution API — start, monitor, history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...storage.local import LocalStorage
from ..deps import get_storage

router = APIRouter(prefix="/runs", tags=["runs"])


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
    return meta

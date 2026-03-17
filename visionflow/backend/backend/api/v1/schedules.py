"""Schedule management API — stub for Phase 4."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("")
async def list_schedules() -> list[dict]:
    return []

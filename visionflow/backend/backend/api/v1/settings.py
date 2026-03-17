"""Settings API."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...config import BackendConfig, get_config

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings(
    config: BackendConfig = Depends(get_config),
) -> dict:
    return {
        "data_dir": str(config.data_dir),
        "gemini_project": config.gemini_project,
        "gemini_region": config.gemini_region,
    }

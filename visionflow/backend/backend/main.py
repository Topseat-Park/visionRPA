"""VisionFlow Backend — FastAPI application."""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.v1.router import router as v1_router
from .config import get_config

logger = logging.getLogger(__name__)

ORPHAN_TIMEOUT_SEC = 5 * 60  # 5 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    (config.data_dir / "sessions").mkdir(exist_ok=True)
    (config.data_dir / "workflows").mkdir(exist_ok=True)
    (config.data_dir / "runs").mkdir(exist_ok=True)
    (config.data_dir / "schedules").mkdir(exist_ok=True)
    (config.data_dir / "control").mkdir(exist_ok=True)

    # Clean up orphaned runs (pending/running > 5 min)
    await _cleanup_orphan_runs(config.data_dir / "runs")

    yield


async def _cleanup_orphan_runs(runs_dir: Path) -> None:
    """Mark stale pending/running runs as aborted on startup."""
    if not runs_dir.exists():
        return
    now = datetime.now(timezone.utc)
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        meta_path = run_dir / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            status = meta.get("status")
            if status not in ("pending", "running"):
                continue
            started_at = datetime.fromisoformat(meta["started_at"])
            elapsed = (now - started_at).total_seconds()
            if elapsed > ORPHAN_TIMEOUT_SEC:
                meta["status"] = "aborted"
                meta["error"] = "Aborted on server restart (agent not responding)"
                meta["finished_at"] = now.isoformat()
                meta_path.write_text(
                    json.dumps(meta, ensure_ascii=False, default=str),
                    encoding="utf-8",
                )
                logger.info("Cleaned up orphan run %s (age: %.0fs)", meta.get("run_id"), elapsed)
        except Exception as e:
            logger.warning("Failed to clean up run in %s: %s", run_dir.name, e)


app = FastAPI(
    title="VisionFlow",
    version="0.1.0",
    lifespan=lifespan,
)

config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/health")
async def health():
    return {"status": "ok"}

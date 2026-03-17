"""VisionFlow Backend — FastAPI application."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.v1.router import router as v1_router
from .config import get_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    (config.data_dir / "sessions").mkdir(exist_ok=True)
    (config.data_dir / "workflows").mkdir(exist_ok=True)
    (config.data_dir / "runs").mkdir(exist_ok=True)
    (config.data_dir / "schedules").mkdir(exist_ok=True)
    (config.data_dir / "control").mkdir(exist_ok=True)
    yield


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

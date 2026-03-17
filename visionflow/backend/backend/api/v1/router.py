"""V1 API router — aggregates all sub-routers."""

from fastapi import APIRouter

from . import agent, runs, schedules, sessions, settings, workflows

router = APIRouter(prefix="/api/v1")
router.include_router(sessions.router)
router.include_router(workflows.router)
router.include_router(runs.router)
router.include_router(schedules.router)
router.include_router(agent.router)
router.include_router(settings.router)

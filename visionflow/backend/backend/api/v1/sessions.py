"""Recording session API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from shared.enums import CommandType

from ...ipc.file_transport import BackendFileTransport
from ...schemas.agent import AgentCommandRequest
from ...schemas.session import (
    CreateSessionRequest,
    SessionEventResponse,
    SessionResponse,
)
from ...storage.local import LocalStorage
from ..deps import get_storage, get_transport

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse)
async def create_session(
    req: CreateSessionRequest,
    storage: LocalStorage = Depends(get_storage),
    transport: BackendFileTransport = Depends(get_transport),
) -> SessionResponse:
    """Create a new recording session and tell Agent to start recording."""
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    meta = {
        "session_id": session_id,
        "created_at": now.isoformat(),
        "purpose": req.purpose,
        "apps": req.apps,
        "exceptions": req.exceptions,
        "exception_notes": req.exception_notes,
        "has_sensitive_info": req.has_sensitive_info,
        "status": "created",
    }
    await storage.write_json(f"sessions/{session_id}/meta.json", meta)

    return SessionResponse(
        session_id=session_id,
        created_at=now,
        purpose=req.purpose,
        apps=req.apps,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    storage: LocalStorage = Depends(get_storage),
) -> SessionResponse:
    meta = await storage.read_json(f"sessions/{session_id}/meta.json")
    if meta is None:
        raise HTTPException(404, "Session not found")

    events = await storage.read_jsonl(f"sessions/{session_id}/events.jsonl")

    return SessionResponse(
        session_id=meta["session_id"],
        created_at=meta["created_at"],
        purpose=meta["purpose"],
        apps=meta.get("apps", []),
        event_count=len(events),
        status=meta.get("status", "created"),
    )


@router.get("/{session_id}/events", response_model=SessionEventResponse)
async def get_session_events(
    session_id: str,
    storage: LocalStorage = Depends(get_storage),
) -> SessionEventResponse:
    events = await storage.read_jsonl(f"sessions/{session_id}/events.jsonl")
    return SessionEventResponse(events=events, total=len(events))


@router.get("/{session_id}/screenshots/{filename}")
async def get_screenshot(
    session_id: str,
    filename: str,
    storage: LocalStorage = Depends(get_storage),
) -> FileResponse:
    path = storage._resolve(f"sessions/{session_id}/screenshots/{filename}")
    if not path.exists():
        raise HTTPException(404, "Screenshot not found")
    return FileResponse(path, media_type="image/jpeg")


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    storage: LocalStorage = Depends(get_storage),
) -> list[SessionResponse]:
    session_ids = await storage.list_dir("sessions")
    sessions = []
    for sid in session_ids:
        meta = await storage.read_json(f"sessions/{sid}/meta.json")
        if meta:
            events = await storage.read_jsonl(f"sessions/{sid}/events.jsonl")
            sessions.append(
                SessionResponse(
                    session_id=meta["session_id"],
                    created_at=meta["created_at"],
                    purpose=meta["purpose"],
                    apps=meta.get("apps", []),
                    event_count=len(events),
                    status=meta.get("status", "created"),
                )
            )
    return sessions

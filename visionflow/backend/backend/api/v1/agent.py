"""Agent status & command API — IPC bridge."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from shared.enums import AgentState
from shared.ipc_models import AgentCommand

from ...ipc.file_transport import BackendFileTransport
from ...schemas.agent import AgentCommandRequest, AgentStatusResponse
from ..deps import get_transport

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status(
    transport: BackendFileTransport = Depends(get_transport),
) -> AgentStatusResponse:
    status = transport.read_status()
    if status is None:
        return AgentStatusResponse(agent_state=AgentState.OFFLINE)

    return AgentStatusResponse(
        agent_state=status.agent_state,
        last_command_id=status.last_command_id,
        recording_session_id=status.recording.session_id if status.recording else None,
        recording_event_count=status.recording.event_count if status.recording else 0,
        recording_elapsed=status.recording.elapsed_seconds if status.recording else 0,
        error=status.error,
    )


@router.post("/command")
async def send_agent_command(
    req: AgentCommandRequest,
    transport: BackendFileTransport = Depends(get_transport),
) -> dict:
    cmd = AgentCommand(
        id=f"cmd_{uuid.uuid4().hex[:12]}",
        timestamp=datetime.now(timezone.utc),
        type=req.type,
        payload=req.payload,
    )
    transport.send_command(cmd)
    return {"ok": True, "command_id": cmd.id}

"""Chat API — AI 대화 인터페이스."""
import json, uuid
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from ...gemini.chat_orchestrator import ChatOrchestrator
from ...storage.local import LocalStorage
from ...ipc.file_transport import BackendFileTransport
from ..deps import get_storage, get_transport

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatMessageBody(BaseModel):
    session_id: str | None = None
    message: str

@router.post("/message")
async def send_message(body: ChatMessageBody, storage: LocalStorage = Depends(get_storage), transport: BackendFileTransport = Depends(get_transport)):
    session_id = body.session_id or f"chat_{uuid.uuid4().hex[:8]}"
    orchestrator = ChatOrchestrator(storage, transport)

    async def event_stream():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        async for event in orchestrator.process_message(session_id, body.message):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@router.get("/history")
async def get_history(session_id: str, storage: LocalStorage = Depends(get_storage), transport: BackendFileTransport = Depends(get_transport)):
    orchestrator = ChatOrchestrator(storage, transport)
    return await orchestrator.get_history(session_id)

@router.delete("/history")
async def clear_history(session_id: str, storage: LocalStorage = Depends(get_storage), transport: BackendFileTransport = Depends(get_transport)):
    orchestrator = ChatOrchestrator(storage, transport)
    await orchestrator.clear_history(session_id)
    return {"ok": True}

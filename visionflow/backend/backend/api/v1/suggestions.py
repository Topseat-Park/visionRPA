"""Automation suggestions API."""
from fastapi import APIRouter, Depends, HTTPException
from ...storage.local import LocalStorage
from ...pattern_detector import PatternDetector
from ..deps import get_storage

router = APIRouter(prefix="/suggestions", tags=["suggestions"])

@router.get("")
async def list_suggestions(status: str | None = None, storage: LocalStorage = Depends(get_storage)):
    data = await storage.read_json("suggestions.json")
    suggestions = data or []
    if status:
        suggestions = [s for s in suggestions if s.get("status") == status]
    return suggestions

@router.post("/analyze")
async def trigger_analysis(storage: LocalStorage = Depends(get_storage)):
    detector = PatternDetector(storage)
    suggestions = await detector.analyze_all_sessions()
    return {"count": len(suggestions), "suggestions": suggestions}

@router.post("/{suggestion_id}/dismiss")
async def dismiss_suggestion(suggestion_id: str, storage: LocalStorage = Depends(get_storage)):
    data = await storage.read_json("suggestions.json") or []
    for s in data:
        if s.get("id") == suggestion_id:
            s["status"] = "dismissed"
    await storage.write_json("suggestions.json", data)
    return {"ok": True}

@router.post("/{suggestion_id}/accept")
async def accept_suggestion(suggestion_id: str, storage: LocalStorage = Depends(get_storage)):
    data = await storage.read_json("suggestions.json") or []
    suggestion = next((s for s in data if s.get("id") == suggestion_id), None)
    if not suggestion:
        raise HTTPException(404, "Suggestion not found")
    suggestion["status"] = "accepted"
    await storage.write_json("suggestions.json", data)
    return {"ok": True, "suggestion": suggestion}

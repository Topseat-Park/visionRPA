"""Pattern Detection Engine — 반복 작업 패턴을 감지하고 자동화를 제안한다."""
import json, logging
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
import uuid
from .storage.local import LocalStorage

logger = logging.getLogger(__name__)

class PatternDetector:
    def __init__(self, storage: LocalStorage):
        self._storage = storage

    async def analyze_all_sessions(self) -> list[dict]:
        """모든 세션을 분석하여 반복 패턴을 감지한다."""
        session_ids = await self._storage.list_dir("sessions")
        signatures = {}

        for sid in session_ids:
            events_data = await self._storage.read_jsonl(f"sessions/{sid}/events.jsonl")
            if not events_data or len(events_data) < 3:
                continue
            sig = self._extract_signature(events_data)
            signatures[sid] = sig

        # Find similar session pairs
        suggestions = []
        session_list = list(signatures.items())

        for i in range(len(session_list)):
            for j in range(i + 1, len(session_list)):
                sid_a, sig_a = session_list[i]
                sid_b, sig_b = session_list[j]
                similarity = self._calculate_similarity(sig_a, sig_b)

                if similarity >= 0.7:
                    # Group similar sessions
                    existing = next((s for s in suggestions if sid_a in s["matched_sessions"] or sid_b in s["matched_sessions"]), None)
                    if existing:
                        if sid_a not in existing["matched_sessions"]:
                            existing["matched_sessions"].append(sid_a)
                        if sid_b not in existing["matched_sessions"]:
                            existing["matched_sessions"].append(sid_b)
                    else:
                        meta_a = await self._storage.read_json(f"sessions/{sid_a}/meta.json")
                        suggestions.append({
                            "id": f"sug_{uuid.uuid4().hex[:8]}",
                            "pattern_name": meta_a.get("purpose", "반복 작업") if meta_a else "반복 작업",
                            "matched_sessions": [sid_a, sid_b],
                            "similarity": round(similarity, 2),
                            "automation_score": round(self._score_automation(sig_a, similarity), 2),
                            "event_count": len(sig_a),
                            "status": "pending",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        })

        # Save suggestions
        if suggestions:
            await self._storage.write_json("suggestions.json", suggestions)

        return suggestions

    def _extract_signature(self, events: list[dict]) -> list[str]:
        """이벤트를 추상 시그니처로 변환."""
        sig = []
        for ev in events:
            etype = ev.get("event_type", "")
            active_win = ev.get("active_window", "")
            if etype in ("click", "double_click"):
                sig.append(f"click:{active_win[:20]}")
            elif etype == "type":
                sig.append(f"type:{len(ev.get('text',''))>10}")
            elif etype == "key":
                sig.append(f"key:{ev.get('key','')}")
            elif etype == "scroll":
                sig.append("scroll")
            elif etype == "window_change":
                sig.append(f"wc:{active_win[:20]}")
            elif etype == "app_launch":
                sig.append(f"app:{ev.get('app_name','')[:20]}")
            else:
                sig.append(etype)
        return sig

    def _calculate_similarity(self, sig_a: list[str], sig_b: list[str]) -> float:
        return SequenceMatcher(None, sig_a, sig_b).ratio()

    def _score_automation(self, sig: list[str], similarity: float) -> float:
        length_score = min(len(sig) / 20, 1.0)
        return (similarity * 0.6 + length_score * 0.4)

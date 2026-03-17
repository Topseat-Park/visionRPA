"""Event preprocessing — compress duplicates before Gemini submission."""

from __future__ import annotations

from shared.event_models import (
    ClickEvent,
    KeyEvent,
    RecordEvent,
    ScrollEvent,
    TypeEvent,
)


def preprocess_events(events: list[dict]) -> list[dict]:
    """Apply PRD preprocessing rules to raw event dicts.

    Rules:
    1. Same-coordinate clicks within 2 sec and >=3 times → keep 1
    2. Type followed by select-all + delete → remove both
    3. Consecutive scrolls in same direction → merge into one
    """
    if not events:
        return events

    result = _compress_repeated_clicks(events)
    result = _remove_type_then_delete(result)
    result = _merge_consecutive_scrolls(result)
    return result


def _compress_repeated_clicks(events: list[dict]) -> list[dict]:
    """Same coordinate clicks within 2 sec and >=3 → keep last only."""
    if len(events) < 3:
        return events

    result: list[dict] = []
    i = 0
    while i < len(events):
        ev = events[i]
        if ev.get("event_type") not in ("click", "double_click"):
            result.append(ev)
            i += 1
            continue

        # Collect consecutive same-coordinate clicks
        group = [ev]
        j = i + 1
        while j < len(events):
            nxt = events[j]
            if (
                nxt.get("event_type") == ev.get("event_type")
                and nxt.get("x") == ev.get("x")
                and nxt.get("y") == ev.get("y")
            ):
                group.append(nxt)
                j += 1
            else:
                break

        if len(group) >= 3:
            # Check time window (2 seconds)
            first_ts = group[0].get("timestamp", "")
            last_ts = group[-1].get("timestamp", "")
            if _within_seconds(first_ts, last_ts, 2.0):
                result.append(group[-1])  # keep last only
            else:
                result.extend(group)
        else:
            result.extend(group)
        i = j

    return result


def _remove_type_then_delete(events: list[dict]) -> list[dict]:
    """Type event followed by Ctrl+A then Delete/Backspace → remove all three."""
    result: list[dict] = []
    skip_until = -1

    for i, ev in enumerate(events):
        if i <= skip_until:
            continue

        if (
            ev.get("event_type") == "type"
            and i + 2 < len(events)
            and events[i + 1].get("event_type") == "key"
            and _is_select_all(events[i + 1])
            and events[i + 2].get("event_type") == "key"
            and _is_delete(events[i + 2])
        ):
            skip_until = i + 2
            continue

        result.append(ev)

    return result


def _merge_consecutive_scrolls(events: list[dict]) -> list[dict]:
    """Consecutive scrolls in same direction → single scroll with summed amount."""
    if not events:
        return events

    result: list[dict] = []
    i = 0
    while i < len(events):
        ev = events[i]
        if ev.get("event_type") != "scroll":
            result.append(ev)
            i += 1
            continue

        total_amount = ev.get("amount", 1)
        direction = ev.get("direction")
        j = i + 1
        while j < len(events):
            nxt = events[j]
            if nxt.get("event_type") == "scroll" and nxt.get("direction") == direction:
                total_amount += nxt.get("amount", 1)
                j += 1
            else:
                break

        merged = dict(ev)
        merged["amount"] = total_amount
        result.append(merged)
        i = j

    return result


def _within_seconds(ts1: str, ts2: str, sec: float) -> bool:
    """Check if two ISO timestamps are within `sec` seconds."""
    from datetime import datetime

    try:
        t1 = datetime.fromisoformat(ts1)
        t2 = datetime.fromisoformat(ts2)
        return abs((t2 - t1).total_seconds()) <= sec
    except (ValueError, TypeError):
        return True  # assume yes if we can't parse


def _is_select_all(ev: dict) -> bool:
    keys = ev.get("keys", [])
    normalized = [k.lower() for k in keys]
    return sorted(normalized) == ["a", "ctrl"] or sorted(normalized) == ["a", "control"]


def _is_delete(ev: dict) -> bool:
    keys = ev.get("keys", [])
    normalized = [k.lower() for k in keys]
    return any(k in normalized for k in ["delete", "backspace", "back"])

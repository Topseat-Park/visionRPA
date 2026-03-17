"""Thin wrapper that re-uses the shared event preprocessor."""

from __future__ import annotations


def preprocess_events(events: list[dict]) -> list[dict]:
    """Apply preprocessing rules to raw event dicts before workflow generation.

    Rules (from PRD §3.6):
    1. Same-coordinate clicks ≥3× within 2 sec → keep 1
    2. Type + Ctrl-A + Delete → remove all three
    3. Consecutive same-direction scrolls → merge into one
    """
    if not events:
        return events

    result = _compress_repeated_clicks(events)
    result = _remove_type_then_delete(result)
    result = _merge_consecutive_scrolls(result)
    return result


def _compress_repeated_clicks(events: list[dict]) -> list[dict]:
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
        if len(group) >= 3 and _within_seconds(
            group[0].get("timestamp", ""), group[-1].get("timestamp", ""), 2.0
        ):
            result.append(group[-1])
        else:
            result.extend(group)
        i = j
    return result


def _remove_type_then_delete(events: list[dict]) -> list[dict]:
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
    result: list[dict] = []
    i = 0
    while i < len(events):
        ev = events[i]
        if ev.get("event_type") != "scroll":
            result.append(ev)
            i += 1
            continue
        direction = ev.get("direction")
        total = ev.get("amount", 1)
        j = i + 1
        while j < len(events) and events[j].get("event_type") == "scroll" and events[j].get("direction") == direction:
            total += events[j].get("amount", 1)
            j += 1
        merged = dict(ev)
        merged["amount"] = total
        result.append(merged)
        i = j
    return result


def _within_seconds(ts1: str, ts2: str, sec: float) -> bool:
    from datetime import datetime
    try:
        t1 = datetime.fromisoformat(ts1)
        t2 = datetime.fromisoformat(ts2)
        return abs((t2 - t1).total_seconds()) <= sec
    except (ValueError, TypeError):
        return True


def _is_select_all(ev: dict) -> bool:
    keys = [k.lower() for k in ev.get("keys", [])]
    return sorted(keys) in (["a", "ctrl"], ["a", "control"])


def _is_delete(ev: dict) -> bool:
    keys = [k.lower() for k in ev.get("keys", [])]
    return any(k in keys for k in ("delete", "backspace", "back"))

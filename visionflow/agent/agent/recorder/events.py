"""Event factory — creates typed events from raw input."""

from __future__ import annotations

from datetime import datetime, timezone

from shared.event_models import (
    AppLaunchEvent,
    ClickEvent,
    DoubleClickEvent,
    DragEvent,
    KeyEvent,
    RecordEvent,
    ScrollEvent,
    TypeEvent,
    WindowChangeEvent,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_click(seq: int, x: int, y: int, button: str = "left") -> ClickEvent:
    return ClickEvent(seq=seq, timestamp=_now(), x=x, y=y, button=button)


def make_double_click(seq: int, x: int, y: int) -> DoubleClickEvent:
    return DoubleClickEvent(seq=seq, timestamp=_now(), x=x, y=y)


def make_type(seq: int, text: str) -> TypeEvent:
    return TypeEvent(seq=seq, timestamp=_now(), text=text)


def make_key(seq: int, keys: list[str]) -> KeyEvent:
    return KeyEvent(seq=seq, timestamp=_now(), keys=keys)


def make_scroll(seq: int, x: int, y: int, direction: str, amount: int = 1) -> ScrollEvent:
    return ScrollEvent(seq=seq, timestamp=_now(), x=x, y=y, direction=direction, amount=amount)


def make_drag(seq: int, sx: int, sy: int, ex: int, ey: int) -> DragEvent:
    return DragEvent(seq=seq, timestamp=_now(), start_x=sx, start_y=sy, end_x=ex, end_y=ey)


def make_app_launch(seq: int, app_name: str, app_path: str | None = None) -> AppLaunchEvent:
    return AppLaunchEvent(seq=seq, timestamp=_now(), app_name=app_name, app_path=app_path)


def make_window_change(seq: int, window_title: str, app_name: str) -> WindowChangeEvent:
    return WindowChangeEvent(seq=seq, timestamp=_now(), window_title=window_title, app_name=app_name)

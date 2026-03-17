"""Event models — 8 event types captured during recording."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .enums import EventType


class ScreenshotMeta(BaseModel):
    """Metadata stored with each screenshot."""

    capture_width: int
    capture_height: int
    dpi_scale: float = 1.0
    monitor_index: int = 0


class BaseEvent(BaseModel):
    """Common fields for all events."""

    seq: int = Field(description="Sequence number within session")
    timestamp: datetime
    event_type: EventType
    screenshot_path: str | None = None
    screenshot_meta: ScreenshotMeta | None = None
    hint: str | None = Field(None, description="User hint attached during recording")


class AppLaunchEvent(BaseEvent):
    event_type: Literal[EventType.APP_LAUNCH] = EventType.APP_LAUNCH
    app_name: str
    app_path: str | None = None


class ClickEvent(BaseEvent):
    event_type: Literal[EventType.CLICK] = EventType.CLICK
    x: int
    y: int
    button: str = "left"


class DoubleClickEvent(BaseEvent):
    event_type: Literal[EventType.DOUBLE_CLICK] = EventType.DOUBLE_CLICK
    x: int
    y: int


class TypeEvent(BaseEvent):
    event_type: Literal[EventType.TYPE] = EventType.TYPE
    text: str


class KeyEvent(BaseEvent):
    event_type: Literal[EventType.KEY] = EventType.KEY
    keys: list[str] = Field(description="Key combination, e.g. ['ctrl', 's']")


class ScrollEvent(BaseEvent):
    event_type: Literal[EventType.SCROLL] = EventType.SCROLL
    x: int
    y: int
    direction: str = Field(description="'up' or 'down'")
    amount: int = 1


class DragEvent(BaseEvent):
    event_type: Literal[EventType.DRAG] = EventType.DRAG
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    screenshot_end_path: str | None = None


class WindowChangeEvent(BaseEvent):
    event_type: Literal[EventType.WINDOW_CHANGE] = EventType.WINDOW_CHANGE
    window_title: str
    app_name: str


# Discriminated union of all event types
RecordEvent = (
    AppLaunchEvent
    | ClickEvent
    | DoubleClickEvent
    | TypeEvent
    | KeyEvent
    | ScrollEvent
    | DragEvent
    | WindowChangeEvent
)


class SessionMeta(BaseModel):
    """Pre-recording metadata (section 4.1 of PRD)."""

    session_id: str
    created_at: datetime
    purpose: str = Field(description="Workflow purpose (required)")
    apps: list[str] = Field(default_factory=list, description="Apps/systems used")
    exceptions: list[str] = Field(
        default_factory=list, description="Exception checkboxes selected"
    )
    exception_notes: str | None = Field(
        None, description="Free-text exception description"
    )
    has_sensitive_info: bool = False

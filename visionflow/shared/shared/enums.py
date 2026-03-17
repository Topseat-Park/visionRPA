"""Shared enumerations for VisionFlow."""

from enum import StrEnum


class EventType(StrEnum):
    APP_LAUNCH = "app_launch"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    TYPE = "type"
    KEY = "key"
    SCROLL = "scroll"
    DRAG = "drag"
    WINDOW_CHANGE = "window_change"


class StepType(StrEnum):
    CMD = "cmd"
    HOTKEY = "hotkey"
    CLIPBOARD_PASTE = "clipboard_paste"
    VISION_CLICK = "vision_click"
    NAVIGATE = "navigate"
    SCROLL = "scroll"
    DRAG = "drag"
    WAIT = "wait"


class OnFailure(StrEnum):
    RETRY = "retry"
    HUMAN = "human"
    SKIP = "skip"
    ABORT = "abort"


class SpeedMode(StrEnum):
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"


class RecordingState(StrEnum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    COMPLETED = "completed"


class AgentState(StrEnum):
    OFFLINE = "offline"
    ONLINE = "online"
    RECORDING = "recording"
    REPLAYING = "replaying"
    PAUSED_CONFLICT = "paused_conflict"
    WAITING_HITL = "waiting_hitl"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class CommandType(StrEnum):
    START_RECORDING = "start_recording"
    PAUSE_RECORDING = "pause_recording"
    RESUME_RECORDING = "resume_recording"
    STOP_RECORDING = "stop_recording"
    START_RUN = "start_run"
    ABORT_RUN = "abort_run"
    HITL_RESPONSE = "hitl_response"
    PING = "ping"

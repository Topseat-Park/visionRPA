"""Path constants for visionflow_data/ directory."""

from pathlib import Path


class DataPaths:
    """Resolves all data directory paths."""

    def __init__(self, base: Path) -> None:
        self.base = base

    @property
    def sessions(self) -> Path:
        return self.base / "sessions"

    @property
    def workflows(self) -> Path:
        return self.base / "workflows"

    @property
    def runs(self) -> Path:
        return self.base / "runs"

    @property
    def schedules(self) -> Path:
        return self.base / "schedules"

    @property
    def control(self) -> Path:
        return self.base / "control"

    @property
    def command_file(self) -> Path:
        return self.control / "command.json"

    @property
    def status_file(self) -> Path:
        return self.control / "status.json"

    def session_dir(self, session_id: str) -> Path:
        return self.sessions / session_id

    def session_events(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "events.jsonl"

    def session_meta(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "meta.json"

    def session_screenshots(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "screenshots"

    def workflow_dir(self, workflow_id: str) -> Path:
        return self.workflows / workflow_id

    def run_dir(self, run_id: str) -> Path:
        return self.runs / run_id

    def ensure_dirs(self) -> None:
        """Create all top-level directories if missing."""
        for d in [self.sessions, self.workflows, self.runs, self.schedules, self.control]:
            d.mkdir(parents=True, exist_ok=True)

"""VisionFlow Agent — main entry point.

Runs the IPC command loop: polls for commands from Dashboard,
dispatches to recorder/replayer, and publishes status via heartbeat.
"""

from __future__ import annotations

import logging
import signal
import time
import uuid
from datetime import datetime, timezone

from shared.enums import CommandType, RecordingState
from shared.event_models import SessionMeta
from shared.ipc_models import AgentCommand

from .config import AgentConfig, get_config
from .ipc.file_transport import FileTransport
from .monitor.heartbeat import Heartbeat
from .recorder.engine import RecordingEngine
from .replayer.engine import ReplayEngine
from .storage.paths import DataPaths

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("visionflow.agent")


class Agent:
    """Top-level agent that ties together IPC, recorder, and heartbeat."""

    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._paths = DataPaths(config.data_dir)
        self._paths.ensure_dirs()

        self._transport = FileTransport(self._paths)
        self._recorder = RecordingEngine(config, self._paths)
        self._replayer = ReplayEngine(self._paths)
        self._heartbeat = Heartbeat(
            self._transport, self._recorder, self._replayer, config.heartbeat_interval
        )
        self._running = False

    def run(self) -> None:
        """Main loop — poll for commands and dispatch."""
        self._running = True
        self._heartbeat.start()
        logger.info("Agent started. Data dir: %s", self._config.data_dir.resolve())

        try:
            while self._running:
                cmd = self._transport.poll_command()
                if cmd:
                    self._handle_command(cmd)
                time.sleep(self._config.ipc_poll_interval)
        except KeyboardInterrupt:
            logger.info("Agent interrupted")
        finally:
            self._shutdown()

    def _handle_command(self, cmd: AgentCommand) -> None:
        logger.info("Command received: %s (id=%s)", cmd.type, cmd.id)
        self._heartbeat.set_last_command_id(cmd.id)
        self._heartbeat.set_error(None)

        try:
            match cmd.type:
                case CommandType.START_RECORDING:
                    self._start_recording(cmd)
                case CommandType.PAUSE_RECORDING:
                    self._recorder.pause()
                case CommandType.RESUME_RECORDING:
                    self._recorder.resume()
                case CommandType.STOP_RECORDING:
                    self._recorder.stop()
                case CommandType.START_RUN:
                    self._start_run(cmd)
                case CommandType.ABORT_RUN:
                    self._replayer.abort()
                case CommandType.PING:
                    pass  # heartbeat will respond
                case _:
                    logger.warning("Unhandled command type: %s", cmd.type)
        except Exception as e:
            logger.exception("Error handling command %s", cmd.type)
            self._heartbeat.set_error(str(e))

    def _start_recording(self, cmd: AgentCommand) -> None:
        # Reset if previous recording completed
        if self._recorder.state == RecordingState.COMPLETED:
            self._recorder.reset()

        session_id = cmd.payload.get("session_id", f"sess_{uuid.uuid4().hex[:8]}")
        meta = SessionMeta(
            session_id=session_id,
            created_at=datetime.now(timezone.utc),
            purpose=cmd.payload.get("purpose", ""),
            apps=cmd.payload.get("apps", []),
            exceptions=cmd.payload.get("exceptions", []),
            exception_notes=cmd.payload.get("exception_notes"),
            has_sensitive_info=cmd.payload.get("has_sensitive_info", False),
        )
        self._recorder.start(session_id, meta)

    def _start_run(self, cmd: AgentCommand) -> None:
        run_id = cmd.payload.get("run_id", f"run_{uuid.uuid4().hex[:8]}")
        workflow_id = cmd.payload.get("workflow_id", "")
        if not workflow_id:
            raise ValueError("start_run requires workflow_id in payload")
        # Reset replayer if a previous run completed
        if not self._replayer.is_running:
            self._replayer.reset()
        self._replayer.start(run_id, workflow_id)

    def _shutdown(self) -> None:
        if self._recorder.state in (RecordingState.RECORDING, RecordingState.PAUSED):
            self._recorder.stop()
        self._heartbeat.stop()
        logger.info("Agent shutdown complete")


def main() -> None:
    config = get_config()
    agent = Agent(config)

    def _signal_handler(sig: int, frame: object) -> None:
        logger.info("Signal %d received, shutting down...", sig)
        agent._running = False

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    agent.run()


if __name__ == "__main__":
    main()

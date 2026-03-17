"""Agent configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings


class AgentConfig(BaseSettings):
    """Agent settings loaded from environment or config file."""

    model_config = {"env_prefix": "VF_"}

    data_dir: Path = Path("visionflow_data")
    ipc_poll_interval: float = 0.5  # seconds
    heartbeat_interval: float = 1.0  # seconds
    screenshot_quality: int = 85  # JPEG quality
    screenshot_max_bytes: int = 4 * 1024 * 1024  # 4MB resize threshold
    default_monitor: int = 0


def get_config() -> AgentConfig:
    return AgentConfig()

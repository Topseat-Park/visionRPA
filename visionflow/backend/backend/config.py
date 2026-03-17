"""Backend configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings


class BackendConfig(BaseSettings):
    model_config = {"env_prefix": "VF_"}

    data_dir: Path = Path("visionflow_data")
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    gemini_project: str = ""
    gemini_region: str = "asia-northeast3"
    gemini_credentials: str = ""


_config: BackendConfig | None = None


def get_config() -> BackendConfig:
    global _config
    if _config is None:
        _config = BackendConfig()
    return _config

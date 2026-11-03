from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUVIREL_", env_file=".env", extra="ignore")
    data_dir: Path = Path(".private/data")
    master_key: SecretStr
    admin_token: SecretStr
    public_url: str = "http://127.0.0.1:8000"
    session_seconds: int = Field(default=3600, ge=300, le=86400)
    media_limit_bytes: int = 512 * 1024**2
    spool_limit_bytes: int = 8 * 1024**3
    cache_limit_bytes: int = 4 * 1024**3
    job_history_limit_bytes: int = 512 * 1024**2
    reserve_free_bytes: int = 30 * 1024**3
    disk_high_water: float = Field(default=0.8, gt=0.1, lt=0.95)
    allowed_origins: list[str] = []
    max_video_seconds: int = 4 * 3600
    max_jobs_per_ticket: int = 2
    gpu: str = "T4"
    model_basic: str = "gemini-3.5-flash-lite"
    model_advanced: str = "gemini-3.8-flash"
    model_deepseek: str = "deepseek-flash"

    @field_validator("master_key", "admin_token")
    @classmethod
    def strong_secret(cls, value: SecretStr):
        if len(value.get_secret_value()) < 32:
            raise ValueError("Secret must contain at least 32 characters")
        return value

from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/channel_radar"
    gemini_api_key: str = ""
    collect_interval_minutes: int = 30
    app_env: str = "development"

    @field_validator("database_url")
    def adjust_database_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()

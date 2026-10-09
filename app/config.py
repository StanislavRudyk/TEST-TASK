

from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    database_url: str = "postgresql+asyncpg://localhost:5432/channel_radar"

    gemini_api_key: str = ""

    collect_interval_minutes: int = 30

    app_env: str = "development"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()

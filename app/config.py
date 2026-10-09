"""
Application settings loaded from environment variables.

All secrets come from .env (never committed).
Defaults are safe for local development.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://localhost:5432/channel_radar"

    # ── AI / LLM ─────────────────────────────────────────────
    gemini_api_key: str = ""

    # ── Scheduler ─────────────────────────────────────────────
    collect_interval_minutes: int = 30

    # ── App ───────────────────────────────────────────────────
    app_env: str = "development"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

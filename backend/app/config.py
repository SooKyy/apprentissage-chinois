from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Chinois PWA"
    database_url: str = "sqlite:///./chinois.db"
    secret_key: str = "change-this-long-random-secret"
    access_token_expire_days: int = 90
    admin_password: str = "change-me"
    backend_cors_origins: str = "http://localhost:5173"
    app_timezone: str = "Europe/Paris"
    day_rollover_hour: int = 4

    openrouter_api_key: str = ""
    openrouter_model: str = "deepseek/deepseek-v4.1-flash"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    tts_voice: str = "zh-CN-XiaoxiaoNeural"
    tts_cache_dir: str = "./tts_cache"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.backend_cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

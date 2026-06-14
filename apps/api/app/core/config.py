from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "info"

    canopy_api_key: str | None = None
    canopy_api_base_url: str = "https://rest.canopyapi.co"
    canopy_timeout_seconds: float = 30.0
    canopy_use_mock: bool = True

    tmapi_key: str | None = None
    tmapi_base_url: str = "https://tmapi.top"
    tmapi_use_mock: bool = True

    image_storage_dir: str = "./storage/images"
    clip_model_name: str = "ViT-B/32"
    clip_use_mock: bool = True

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

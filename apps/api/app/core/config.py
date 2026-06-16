from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "info"

    canopy_api_key: str | None = None
    canopy_api_base_url: str = "https://rest.canopyapi.co"
    canopy_timeout_seconds: float = 30.0
    canopy_use_mock: bool = True

    apify_api_token: str | None = None
    apify_api_base_url: str = "https://api.apify.com/v2"
    apify_timeout_seconds: float = 120.0
    apify_use_mock: bool = True
    apify_reverse_image_actor: str = ""
    apify_keyword_search_actor: str = "ghXSMZcW3GxsCrkiR"
    apify_reverse_image_destination: str = "1688"
    apify_search_limit: int = 20
    apify_keyword_limit: int = 3
    apify_detail_limit: int = 20

    siliconflow_api_key: str | None = None
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_model: str = "inclusionAI/Ling-flash-2.0"
    siliconflow_timeout_seconds: float = 30.0
    siliconflow_use_mock: bool = True

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
        env_file=(
            Path(__file__).resolve().parents[4] / ".env",
            ".env",
        ),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

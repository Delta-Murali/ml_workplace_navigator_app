"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Workplace Navigator"
    app_version: str = "0.1.0"
    debug: bool = False

    # OpenRouter AI
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-3.5-sonnet"

    # Azure Maps (optional)
    azure_maps_client_id: str = ""
    azure_maps_subscription_key: str = ""
    azure_maps_tileset_id: str = ""
    azure_maps_stateset_id: str = ""
    azure_maps_routeset_id: str = ""
    azure_maps_dataset_id: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

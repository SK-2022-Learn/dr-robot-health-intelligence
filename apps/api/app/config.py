"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized settings keep infrastructure choices out of business logic."""

    app_name: str = "Dr. Robot"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_url: str = "http://localhost:3000"
    database_url: str = "sqlite:///./data/dr_robot.db"
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = Field(default=15, ge=1, le=100)
    vector_provider: str = "pinecone"
    pinecone_api_key: str = ""
    pinecone_index: str = ""
    pinecone_namespace_prefix: str = "dr-robot"
    pinecone_timeout_seconds: float = Field(default=30, ge=1, le=120)
    embedding_provider: str = "ollama"
    ollama_embedding_model: str = ""
    embedding_timeout_seconds: float = Field(default=60, ge=1, le=300)
    chunk_size_chars: int = Field(default=1200, ge=200, le=10000)
    chunk_overlap_chars: int = Field(default=200, ge=0, le=2000)
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = ""
    ollama_timeout_seconds: float = Field(default=120, ge=1, le=600)
    agent_timeout_seconds: float = Field(default=150, ge=5, le=600)
    analytics_recent_window_days: int = Field(
        default=30,
        ge=1,
        le=365,
        validation_alias=AliasChoices("ANALYTICS_RECENT_WINDOW_DAYS", "RECENT_WINDOW_DAYS"),
    )
    analytics_baseline_window_days: int = Field(
        default=90,
        ge=1,
        le=730,
        validation_alias=AliasChoices("ANALYTICS_BASELINE_WINDOW_DAYS", "BASELINE_WINDOW_DAYS"),
    )
    analytics_stability_threshold_percent: float = Field(default=5.0, ge=0, le=100)
    analytics_min_recent_numeric_points: int = Field(default=2, ge=1, le=100)
    analytics_min_baseline_numeric_points: int = Field(default=2, ge=1, le=100)

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings instance per application process."""

    return Settings()

# api/app/config.py
from functools import lru_cache
from typing import Literal
from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    DATABASE_URL: PostgresDsn
    
    # Directus configuration (FIXED for Docker network)
    DIRECTUS_URL: str = "http://directus:8055"  # Internal Docker network
    DIRECTUS_PUBLIC_URL: str = "http://localhost:8054"  # External access (for docs)
    DIRECTUS_TOKEN: str = ""  # Access token for Directus assets
    
    ENVIRONMENT: Literal["development", "production", "testing"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    CORS_ORIGINS: str = "*"
    
    OPENAI_API_KEY: str = ""
    AI_MODEL: str = "gpt-4o-mini"
    AI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    AI_SIMILARITY_THRESHOLD_HIGH: float = 0.7
    AI_SIMILARITY_THRESHOLD_LOW: float = 0.3
    
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            return v
        return str(v)
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
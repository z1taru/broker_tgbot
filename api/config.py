from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Конфигурация API приложения"""
    DATABASE_URL: str
    VIDEO_BASE_URL: str = "http://localhost:8000"
    
    class Config:
        env_file = ".env"


settings = Settings()
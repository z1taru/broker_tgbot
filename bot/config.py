from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Конфигурация Telegram бота"""
    BOT_TOKEN: str
    DATABASE_URL: str
    API_BASE_URL: str = "http://api:8000"
    
    # Webhook настройки (для продакшена)
    WEBHOOK_ENABLED: bool = False
    WEBHOOK_URL: str = ""
    WEBHOOK_PATH: str = "/webhook"
    
    class Config:
        env_file = ".env"


settings = Settings()
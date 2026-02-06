from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool = Field(..., description="Статус выполнения запроса")
    data: T | None = Field(None, description="Данные ответа")
    message: str | None = Field(None, description="Сообщение")
    error_code: str | None = Field(None, description="Код ошибки")


class ErrorResponse(BaseModel):
    success: bool = Field(default=False)
    message: str = Field(..., description="Сообщение об ошибке")
    error_code: str | None = Field(None, description="Код ошибки")
    details: list[dict] | None = Field(None, description="Детали ошибок")


class HealthCheckResponse(BaseModel):
    status: str = Field(..., description="Статус сервиса")
    database: str = Field(..., description="Статус БД")
    version: str = Field(default="1.0.0", description="Версия API")
    environment: str = Field(..., description="Окружение")
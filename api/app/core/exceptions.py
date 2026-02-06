from typing import Any


class AppException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundException(AppException):
    def __init__(self, message: str = "Ресурс не найден", details: dict[str, Any] | None = None):
        super().__init__(message, status_code=404, details=details)


class DatabaseException(AppException):
    def __init__(self, message: str = "Ошибка базы данных", details: dict[str, Any] | None = None):
        super().__init__(message, status_code=500, details=details)


class ValidationException(AppException):
    def __init__(self, message: str = "Ошибка валидации данных", details: dict[str, Any] | None = None):
        super().__init__(message, status_code=422, details=details)
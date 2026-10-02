from fastapi import HTTPException, status


class BaseHTTPException(HTTPException):
    """
    Базовый класс для всех HTTP-исключений проекта.

    Позволяет создавать типизированные исключения с предопределенными
    статус-кодами и сообщениями по умолчанию. При инициализации можно
    передать специфический "detail", который переопределит дефолтный.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Internal Server Error"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            status_code=self.status_code,
            detail=detail or self.detail,
        )


class UnauthorizedHTTPException(BaseHTTPException):
    """Ошибка авторизации: доступ запрещен из-за отсутствия учетных данных."""

    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Unauthorized"


class ForbiddenHTTPException(BaseHTTPException):
    """Доступ запрещен: недостаточно прав для выполнения операции."""

    status_code = status.HTTP_403_FORBIDDEN
    detail = "Forbidden"


class NotFoundHTTPException(BaseHTTPException):
    """Запрошенный ресурс не найден."""

    status_code = status.HTTP_404_NOT_FOUND
    detail = "Not Found"


class ConflictHTTPException(BaseHTTPException):
    """Конфликт состояния: ресурс уже существует или занят."""

    status_code = status.HTTP_409_CONFLICT
    detail = "Conflict"


class ValidationHTTPException(BaseHTTPException):
    """Ошибка валидации данных: предоставленные данные не соответствуют требованиям."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "Validation Error"

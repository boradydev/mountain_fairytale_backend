"""
Исключения модуля авторизации.

ВАЖНО: Эти исключения намеренно отделены от исключений модуля сотрудников (employees),
даже если они описывают похожие ситуации (например, "пользователь не найден").
Это сделано для реализации требований безопасности: в контексте авторизации
мы должны возвращать 401 (Unauthorized) вместо 404 (Not Found), чтобы
злоумышленник не мог перебором узнать, существует ли пользователь в системе.
"""

from dataclasses import dataclass
from uuid import UUID

from src.domain.common.excs import DomainException


@dataclass(frozen=True, slots=True)
class InvalidCredentialsException(DomainException):
    pass


@dataclass(frozen=True, slots=True)
class AuthEmployeeNotFoundException(DomainException):
    employee_id: UUID


@dataclass(frozen=True, slots=True)
class AuthEmployeeNotFoundByUsernameException(DomainException):
    username: str


@dataclass(frozen=True, slots=True)
class AuthEmployeeDeactivateException(DomainException):
    employee_id: UUID

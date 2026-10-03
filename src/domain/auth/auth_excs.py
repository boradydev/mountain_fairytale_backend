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
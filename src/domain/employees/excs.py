from dataclasses import dataclass
from uuid import UUID

from src.domain.common.excs import DomainException


@dataclass(frozen=True, slots=True)
class InvalidCredentialsException(DomainException):
    pass


@dataclass(frozen=True, slots=True)
class EmployeeNotFoundException(DomainException):
    employee_id: UUID

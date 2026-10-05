from dataclasses import dataclass
from uuid import UUID

from src.domain.common.excs import DomainException


@dataclass(frozen=True, slots=True)
class EmployeeNotFoundException(DomainException):
    employee_id: UUID


@dataclass(frozen=True, slots=True)
class EmployeeNotFoundByUsernameException(DomainException):
    username: str


@dataclass(frozen=True, slots=True)
class EmployeeDeactivateException(DomainException):
    employee_id: UUID


@dataclass(frozen=True, slots=True)
class EmployeeDomainUpdateException(DomainException):
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class EmployeeUsernameAlreadyExistsException(DomainException):
    username: str

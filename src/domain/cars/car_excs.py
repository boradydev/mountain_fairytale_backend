from dataclasses import dataclass
from uuid import UUID

from src.domain.common.excs import DomainException


@dataclass(frozen=True, slots=True)
class CarNotFoundException(DomainException):
    car_id: UUID


@dataclass(frozen=True, slots=True)
class CarDeactivateException(DomainException):
    car_id: UUID


@dataclass(frozen=True, slots=True)
class CarNumberAlreadyExistsException(DomainException):
    number: str


@dataclass(frozen=True, slots=True)
class CarAlreadyActivateException(DomainException):
    number: str


@dataclass(frozen=True, slots=True)
class CarDomainUpdateException(DomainException):
    field: str
    message: str

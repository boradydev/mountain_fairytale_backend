from dataclasses import dataclass
from uuid import UUID

from src.domain.common.excs import DomainException


@dataclass(frozen=True, slots=True)
class DriverNotFoundException(DomainException):
    driver_id: UUID


@dataclass(frozen=True, slots=True)
class DriverDomainUpdateException(DomainException):
    field: str
    message: str

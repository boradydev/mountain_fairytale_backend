from dataclasses import dataclass
from uuid import UUID

from src.domain.common.excs import DomainException


@dataclass(frozen=True, slots=True)
class SalesRepresentativeNotFoundException(DomainException):
    sales_representative_id: UUID


@dataclass(frozen=True, slots=True)
class SalesRepresentativeDomainUpdateException(DomainException):
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class SalesRepresentativePhoneAlreadyExistsException(DomainException):
    phone: str

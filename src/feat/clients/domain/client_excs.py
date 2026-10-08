from dataclasses import dataclass
from uuid import UUID

from src.common.domain.excs import DomainException


@dataclass(frozen=True, slots=True)
class ClientNotFoundException(DomainException):
    client_id: UUID


@dataclass(frozen=True, slots=True)
class ClientDomainUpdateException(DomainException):
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class ClientPhoneAlreadyExistsException(DomainException):
    phone: str


@dataclass(frozen=True, slots=True)
class ClientRelatedEntityNotFoundException(DomainException):
    field: str
    entity_id: UUID

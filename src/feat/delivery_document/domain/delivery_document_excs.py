from dataclasses import dataclass
from uuid import UUID

from src.common.domain.excs import DomainException


@dataclass(frozen=True, slots=True)
class DeliveryDocumentNotFoundException(DomainException):
    delivery_document_id: UUID


@dataclass(frozen=True, slots=True)
class DeliveryDocumentUpdateException(DomainException):
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class DeliveryDocumentRelatedEntityNotFoundException(DomainException):
    field: str
    entity_id: UUID


@dataclass(frozen=True, slots=True)
class DeliveryDocumentPointClientAlreadyExistsException(DomainException):
    client_id: UUID


@dataclass(frozen=True, slots=True)
class DeliveryDocumentPointProductAlreadyExistsException(DomainException):
    product_id: UUID


@dataclass(frozen=True, slots=True)
class DeliveryDocumentLockedException(DomainException):
    delivery_document_id: UUID
    owner_name: str


@dataclass(frozen=True, slots=True)
class DeliveryDocumentEditLockNotFoundException(DomainException):
    delivery_document_id: UUID


@dataclass(frozen=True, slots=True)
class DeliveryDocumentEditLockNotOwnedException(DomainException):
    delivery_document_id: UUID
